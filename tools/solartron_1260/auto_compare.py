"""
Rebuild Origin-ready compare CSVs + overlay plots for a Solartron_1260 device leaf.

Called automatically after each measurement export. Also usable standalone:

  python -m tools.solartron_1260.auto_compare "D:\\...\\Solartron_1260"
"""

from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd

_BIAS_RE = re.compile(r"_?VB([pm])(\d+(?:\.\d+)?)", re.IGNORECASE)


@dataclass
class Series:
    label: str
    bias_v: Optional[float]
    path: Path
    df: pd.DataFrame


def parse_bias_v(stem: str) -> Optional[float]:
    m = _BIAS_RE.search(stem)
    if not m:
        return None
    sign = -1.0 if m.group(1).lower() == "m" else 1.0
    return sign * float(m.group(2))


def bias_col_label(bias_v: float) -> str:
    return f"{bias_v:+.3f}V"


def series_label(stem: str, bias_v: Optional[float]) -> str:
    base = _BIAS_RE.sub("", stem)
    base = re.sub(r"_+", "_", base).strip("_") or stem
    if bias_v is None:
        return base
    return f"{base}_{bias_col_label(bias_v)}"


def _numeric(df: pd.DataFrame, col: str) -> np.ndarray:
    if col not in df.columns:
        return np.full(len(df), np.nan)
    return pd.to_numeric(df[col], errors="coerce").to_numpy()


def collect_series(root: Path) -> List[Series]:
    found: List[Series] = []
    used_labels: set[str] = set()
    root = Path(root)

    for path in sorted(root.rglob("origin_data/*.csv")):
        stem_l = path.stem.lower()
        if stem_l.endswith("_open") or stem_l.endswith("_short"):
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "Frequency_Hz" not in df.columns:
            continue

        bias = parse_bias_v(path.stem)
        label = series_label(path.stem, bias)
        if label in used_labels:
            label = f"{path.parent.parent.name}_{label}"
        n = 2
        base = label
        while label in used_labels:
            label = f"{base}_{n}"
            n += 1
        used_labels.add(label)
        found.append(Series(label=label, bias_v=bias, path=path, df=df))

    found.sort(key=lambda s: (s.bias_v if s.bias_v is not None else 999.0, s.label))
    return found


def build_long(series_list: List[Series]) -> pd.DataFrame:
    frames = []
    for s in series_list:
        chunk = s.df.copy()
        chunk.insert(0, "Dataset", s.label)
        chunk.insert(1, "Bias_V", s.bias_v if s.bias_v is not None else np.nan)
        chunk.insert(2, "Source_File", s.path.name)
        frames.append(chunk)
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["Bias_V", "Dataset", "Frequency_Hz"]).reset_index(drop=True)


def build_origin_compare_csvs(
    series_list: List[Series],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Wide tables for Origin overlays.

    Z_Imag_Ohms in Solartron Origin CSVs is already -Im(Z).
    """
    n_max = max(len(s.df) for s in series_list)

    def _pad(a: np.ndarray) -> np.ndarray:
        out = np.full(n_max, np.nan)
        out[: len(a)] = a
        return out

    c_vs_f = pd.DataFrame()
    bode = pd.DataFrame()
    zreal_vs_f = pd.DataFrame()
    zimag_vs_f = pd.DataFrame()
    nyq: dict[str, np.ndarray] = {}

    for s in series_list:
        tag = s.label
        freq = _numeric(s.df, "Frequency_Hz")
        zreal = _numeric(s.df, "Z_Real_Ohms")
        # stored Z_Imag is already -Im(Z)
        neg_zimag = _numeric(s.df, "Z_Imag_Ohms")

        part_c = pd.DataFrame(
            {
                "Frequency_Hz": freq,
                f"Capacitance_F_{tag}": _numeric(s.df, "Capacitance_F"),
            }
        )
        c_vs_f = part_c if c_vs_f.empty else c_vs_f.merge(part_c, on="Frequency_Hz", how="outer")

        part_b = pd.DataFrame(
            {
                "Frequency_Hz": freq,
                f"Z_Magnitude_Ohms_{tag}": _numeric(s.df, "Z_Magnitude_Ohms"),
                f"Phase_deg_{tag}": _numeric(s.df, "Phase_deg"),
            }
        )
        bode = part_b if bode.empty else bode.merge(part_b, on="Frequency_Hz", how="outer")

        part_zr = pd.DataFrame(
            {
                "Frequency_Hz": freq,
                f"Z_Real_{tag}": zreal,
            }
        )
        zreal_vs_f = (
            part_zr if zreal_vs_f.empty else zreal_vs_f.merge(part_zr, on="Frequency_Hz", how="outer")
        )

        part_zi = pd.DataFrame(
            {
                "Frequency_Hz": freq,
                f"-Z_Imag_{tag}": neg_zimag,
            }
        )
        zimag_vs_f = (
            part_zi if zimag_vs_f.empty else zimag_vs_f.merge(part_zi, on="Frequency_Hz", how="outer")
        )

        nyq[f"Z_Real_{tag}"] = _pad(zreal)
        nyq[f"-Z_Imag_{tag}"] = _pad(neg_zimag)
        nyq[f"Frequency_Hz_{tag}"] = _pad(freq)

    c_vs_f = c_vs_f.sort_values("Frequency_Hz").reset_index(drop=True)
    bode = bode.sort_values("Frequency_Hz").reset_index(drop=True)
    zreal_vs_f = zreal_vs_f.sort_values("Frequency_Hz").reset_index(drop=True)
    zimag_vs_f = zimag_vs_f.sort_values("Frequency_Hz").reset_index(drop=True)
    return c_vs_f, bode, pd.DataFrame(nyq), zreal_vs_f, zimag_vs_f


def _equalize_nyquist_axes(ax, x, y, *, pad: float = 0.05) -> None:
    """Match X/Y axis span (same length) with 1:1 aspect for Nyquist."""
    xv = np.asarray(x, dtype=float).ravel()
    yv = np.asarray(y, dtype=float).ravel()
    mask = np.isfinite(xv) & np.isfinite(yv)
    xv, yv = xv[mask], yv[mask]
    if xv.size == 0:
        return
    xmin, xmax = float(np.min(xv)), float(np.max(xv))
    ymin, ymax = float(np.min(yv)), float(np.max(yv))
    xmid = 0.5 * (xmin + xmax)
    ymid = 0.5 * (ymin + ymax)
    half = 0.5 * max(xmax - xmin, ymax - ymin, 1e-30) * (1.0 + pad)
    ax.set_xlim(xmid - half, xmid + half)
    ax.set_ylim(ymid - half, ymid + half)
    ax.set_aspect("equal", adjustable="box")


def _safe_filename(label: str) -> str:
    """Filesystem-safe name for EISSA .txt files."""
    cleaned = "".join(c if c.isalnum() or c in "-+._" else "_" for c in label)
    return cleaned.strip("._") or "spectrum"


def write_eis_analyser_txt(df: pd.DataFrame, path: Path) -> Path:
    """
    Write one EIS Spectrum Analyser (eissa1.exe) data file.

    Format (http://www.abc.chemistry.bsu.by/vi/analyser/open.html):
      n
       ReZ1  -ImZ1  Freq1
       ...
      Frequency descending; Z_Imag_Ohms in Origin CSVs is already -Im(Z).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    work = pd.DataFrame(
        {
            "ReZ": pd.to_numeric(df["Z_Real_Ohms"], errors="coerce"),
            "NegImZ": pd.to_numeric(df["Z_Imag_Ohms"], errors="coerce"),
            "Freq": pd.to_numeric(df["Frequency_Hz"], errors="coerce"),
        }
    ).dropna()
    work = work[work["Freq"] > 0]
    work = work.sort_values("Freq", ascending=False).reset_index(drop=True)

    n = len(work)
    lines = [str(n)]
    for row in work.itertuples(index=False):
        lines.append(
            f" {row.ReZ:.14E}  {row.NegImZ:.14E}  {row.Freq:.14E}"
        )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def export_eis_analyser_folder(series_list: List[Series], leaf: Path) -> Path:
    """
    Rebuild <leaf>/eis_analyser/*.txt — one spectrum per file for eissa1.exe.
    Clears the folder first so removed runs do not linger.
    """
    out = Path(leaf) / "eis_analyser"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    used: set[str] = set()
    for s in series_list:
        stem = _safe_filename(s.label)
        name = f"{stem}.txt"
        if name in used:
            k = 2
            while f"{stem}_{k}.txt" in used:
                k += 1
            name = f"{stem}_{k}.txt"
        used.add(name)
        write_eis_analyser_txt(s.df, out / name)
    return out


def _save_plots(series_list: List[Series], out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []

    fig, ax = plt.subplots(figsize=(8, 5))
    for s in series_list:
        f = pd.to_numeric(s.df["Frequency_Hz"], errors="coerce")
        c = pd.to_numeric(s.df["Capacitance_F"], errors="coerce")
        ax.semilogx(f, c, marker=".", markersize=3, linewidth=1.2, label=s.label)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Capacitance (F)")
    ax.set_title("Capacitance vs Frequency (all datasets)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best", fontsize=7)
    fig.tight_layout()
    p = out_dir / "combined_C_vs_f.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    fig, (ax_m, ax_p) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    for s in series_list:
        f = pd.to_numeric(s.df["Frequency_Hz"], errors="coerce")
        mag = pd.to_numeric(s.df["Z_Magnitude_Ohms"], errors="coerce")
        phase = pd.to_numeric(s.df["Phase_deg"], errors="coerce")
        ax_m.loglog(f, mag, marker=".", markersize=3, linewidth=1.2, label=s.label)
        ax_p.semilogx(f, phase, marker=".", markersize=3, linewidth=1.2, label=s.label)
    ax_m.set_ylabel("|Z| (Ω)")
    ax_m.set_title("Bode (all datasets)")
    ax_m.grid(True, which="both", alpha=0.3)
    ax_m.legend(loc="best", fontsize=7)
    ax_p.set_xlabel("Frequency (Hz)")
    ax_p.set_ylabel("Phase (deg)")
    ax_p.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    p = out_dir / "combined_bode_mag_phase.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    # Frequency (X) vs Z' (Y)
    fig, ax = plt.subplots(figsize=(8, 5))
    for s in series_list:
        f = pd.to_numeric(s.df["Frequency_Hz"], errors="coerce")
        zr = pd.to_numeric(s.df["Z_Real_Ohms"], errors="coerce")
        ax.semilogx(f, zr, marker=".", markersize=3, linewidth=1.2, label=s.label)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Z' (Ω)")
    ax.set_title("Real impedance vs Frequency (all datasets)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best", fontsize=7)
    fig.tight_layout()
    p = out_dir / "combined_Zreal_vs_f.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    # Frequency (X) vs -Z'' (Y) — Origin Z_Imag is already -Im(Z)
    fig, ax = plt.subplots(figsize=(8, 5))
    for s in series_list:
        f = pd.to_numeric(s.df["Frequency_Hz"], errors="coerce")
        zi = pd.to_numeric(s.df["Z_Imag_Ohms"], errors="coerce")
        ax.semilogx(f, zi, marker=".", markersize=3, linewidth=1.2, label=s.label)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("-Z'' (Ω)")
    ax.set_title("Imaginary impedance vs Frequency (all datasets)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best", fontsize=7)
    fig.tight_layout()
    p = out_dir / "combined_Zimag_vs_f.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    all_zr: list[np.ndarray] = []
    all_zi: list[np.ndarray] = []
    for s in series_list:
        zr = pd.to_numeric(s.df["Z_Real_Ohms"], errors="coerce").to_numpy()
        zi = pd.to_numeric(s.df["Z_Imag_Ohms"], errors="coerce").to_numpy()
        ax.plot(zr, zi, marker=".", markersize=3, linewidth=1.0, label=s.label)
        all_zr.append(zr)
        all_zi.append(zi)
    ax.set_xlabel("Z' (Ω)")
    ax.set_ylabel("-Z'' (Ω)")
    ax.set_title("Nyquist (all datasets)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=7)
    _equalize_nyquist_axes(ax, np.concatenate(all_zr), np.concatenate(all_zi))
    fig.tight_layout()
    p = out_dir / "combined_nyquist.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    return saved


def refresh_device_compare(
    solartron_leaf: Path,
    *,
    quiet: bool = False,
) -> Optional[Path]:
    """
    Rebuild compare outputs for every origin_data CSV under a device Solartron_1260 folder.

    Writes under <leaf>/origin_compare/:
      all_datasets_long, C_vs_f, bode, Zreal_vs_f, Zimag_vs_f, nyquist
    <leaf>/combined_plots/*.png overlays
    <leaf>/eis_analyser/*.txt for EIS Spectrum Analyser (eissa1.exe)

    Returns the origin_compare directory, or None if nothing to combine.
    """
    leaf = Path(solartron_leaf)
    if not leaf.is_dir():
        return None

    series_list = collect_series(leaf)
    if not series_list:
        if not quiet:
            print(f"auto_compare: no origin_data CSVs under {leaf}")
        return None

    if not quiet:
        print(f"auto_compare: {len(series_list)} dataset(s) in {leaf}")
        for s in series_list:
            print(f"  {s.label}")

    long_df = build_long(series_list)
    c_vs_f, bode, nyquist, zreal_vs_f, zimag_vs_f = build_origin_compare_csvs(series_list)

    out_dir = leaf / "origin_compare"
    plots_dir = leaf / "combined_plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    long_df.to_csv(out_dir / "all_datasets_long.csv", index=False, na_rep="")
    c_vs_f.to_csv(out_dir / "origin_compare_C_vs_f.csv", index=False, na_rep="")
    bode.to_csv(out_dir / "origin_compare_bode.csv", index=False, na_rep="")
    nyquist.to_csv(out_dir / "origin_compare_nyquist.csv", index=False, na_rep="")
    zreal_vs_f.to_csv(out_dir / "origin_compare_Zreal_vs_f.csv", index=False, na_rep="")
    zimag_vs_f.to_csv(out_dir / "origin_compare_Zimag_vs_f.csv", index=False, na_rep="")
    _save_plots(series_list, plots_dir)
    eissa_dir = export_eis_analyser_folder(series_list, leaf)

    if not quiet:
        print(f"auto_compare: wrote {out_dir}")
        print(f"auto_compare: wrote {plots_dir}")
        print(f"auto_compare: wrote {eissa_dir} ({len(series_list)} .txt)")
    return out_dir


def refresh_compare_for_run(run_dir: Path, *, quiet: bool = True) -> Optional[Path]:
    """Given a run folder (.../Solartron_1260/<N>-...), refresh its parent leaf."""
    run_dir = Path(run_dir)
    leaf = run_dir.parent
    if leaf.name != "Solartron_1260":
        # still try parent — layout may vary slightly
        leaf = run_dir.parent
    try:
        return refresh_device_compare(leaf, quiet=quiet)
    except Exception as exc:
        if not quiet:
            print(f"auto_compare failed: {exc}")
        return None


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Usage: python auto_compare.py <Solartron_1260 folder>")
        return 2
    refresh_device_compare(Path(args[0]), quiet=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
