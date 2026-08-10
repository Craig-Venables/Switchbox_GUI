"""
Origin-ready CSV export and preview figure saving for Solartron sweeps.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_TOOL_DIR = Path(__file__).resolve().parent
_IMPEDANCE_DIR = _TOOL_DIR.parent / "impedance_analyzer"
if str(_IMPEDANCE_DIR) not in sys.path:
    sys.path.insert(0, str(_IMPEDANCE_DIR))

from impedance_plots import (  # noqa: E402
    equalize_nyquist_axes,
    plot_capacitance_vs_frequency,
    plot_magnitude_vs_frequency,
    plot_nyquist,
    plot_phase_vs_frequency,
)
from origin_export import export_origin_csv, export_origin_csv_with_corrected  # noqa: E402

from auto_compare import refresh_compare_for_run  # noqa: E402
from engine import SweepResult, bias_tag  # noqa: E402
from paths import allocate_run_directory, sanitize_notes  # noqa: E402


def _auto_compare_safe(run_dir: Path) -> None:
    """Refresh device-level Origin compare CSVs/plots; never fail the save."""
    try:
        refresh_compare_for_run(run_dir, quiet=True)
    except Exception:
        pass


def ensure_run_directory(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    (run_dir / "origin_data").mkdir(parents=True, exist_ok=True)
    (run_dir / "graphs").mkdir(parents=True, exist_ok=True)
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    return run_dir


def save_full_csv(result: SweepResult, path: Path) -> Path:
    """Write a lab-notes CSV including R, X, Cs, Cp."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = result.to_dataframe()
    df.to_csv(path, index=False)
    return path


def save_origin_csv(
    result: SweepResult,
    path: Path,
    corrected: Optional[SweepResult] = None,
) -> Path:
    """Write Origin graph-ready CSV (optionally with corrected columns)."""
    path = Path(path)
    df = result.to_dataframe()
    if corrected is not None:
        return export_origin_csv_with_corrected(df, path, df_corrected=corrected.to_dataframe())
    return export_origin_csv(df, path)


def save_preview_figures(
    result: SweepResult,
    graphs_dir: Path,
    *,
    stem: str = "device",
    corrected: Optional[SweepResult] = None,
) -> Tuple[Path, Path, Path]:
    """Save C vs f, Bode (|Z| + phase), and Nyquist PNGs."""
    graphs_dir = Path(graphs_dir)
    graphs_dir.mkdir(parents=True, exist_ok=True)
    plot_src = corrected if corrected is not None else result
    df = plot_src.to_dataframe()

    fig_c, ax_c = plt.subplots(figsize=(6, 4))
    plot_capacitance_vs_frequency(df, ax=ax_c, label=stem)
    ax_c.set_title("Capacitance vs Frequency")
    ax_c.legend(loc="best")
    fig_c.tight_layout()
    c_path = graphs_dir / f"{stem}_C_vs_f.png"
    fig_c.savefig(c_path, dpi=150, bbox_inches="tight")
    plt.close(fig_c)

    fig_b, (ax_m, ax_p) = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
    plot_magnitude_vs_frequency(df, ax=ax_m, label=stem)
    plot_phase_vs_frequency(df, ax=ax_p, label=stem)
    ax_m.set_title("Bode")
    ax_m.legend(loc="best")
    fig_b.tight_layout()
    bode_path = graphs_dir / f"{stem}_bode_mag_phase.png"
    fig_b.savefig(bode_path, dpi=150, bbox_inches="tight")
    plt.close(fig_b)

    fig_n, ax_n = plt.subplots(figsize=(5, 5))
    plot_nyquist(df, ax=ax_n, label=stem)
    ax_n.set_title("Nyquist")
    ax_n.legend(loc="best")
    fig_n.tight_layout()
    # Re-apply after tight_layout so X/Y spans stay matched
    equalize_nyquist_axes(ax_n)
    nyq_path = graphs_dir / f"{stem}_nyquist.png"
    fig_n.savefig(nyq_path, dpi=150, bbox_inches="tight")
    plt.close(fig_n)

    return c_path, bode_path, nyq_path


def write_run_meta(run_dir: Path, meta: Dict[str, Any]) -> Path:
    path = Path(run_dir) / "meta.json"
    payload = dict(meta)
    payload.setdefault("saved_at", datetime.now().isoformat(timespec="seconds"))
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _stem_with_notes(safe_sample: str, notes: str, bias_part: Optional[str] = None) -> str:
    parts = [safe_sample]
    if notes:
        parts.append(notes)
    if bias_part:
        parts.append(bias_part)
    return "_".join(parts)


def export_run_bundle(
    result: SweepResult,
    *,
    save_root: Path,
    sample: str,
    section: str,
    device: str,
    kind: str = "device",
    notes: str = "",
    open_result: Optional[SweepResult] = None,
    short_result: Optional[SweepResult] = None,
    run_dir: Optional[Path] = None,
    include_bias_in_name: bool = True,
    meta_extra: Optional[Dict[str, Any]] = None,
    auto_compare: bool = True,
) -> Path:
    """
    Save under:
      <root>/<sample>/<section>/<device>/Solartron_1260/<N>-<kind>_<timestamp>/
    Optional notes (e.g. hrs_after_55) go into folder kind and CSV stems.
    """
    note = sanitize_notes(notes)
    kind_name = f"{kind}_{note}" if note else kind

    if run_dir is None:
        run_dir, run_index, safe_sample = allocate_run_directory(
            save_root, sample, section, device, kind=kind_name
        )
    else:
        run_dir = ensure_run_directory(run_dir)
        run_index = -1
        safe_sample = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in (sample or "sample")
        )

    bias_part = bias_tag(result.dc_bias_v) if include_bias_in_name else None
    stem = _stem_with_notes(safe_sample, note, bias_part)
    open_short_stem = _stem_with_notes(safe_sample, note, None)

    corrected = result.corrected
    save_origin_csv(
        result,
        run_dir / "origin_data" / f"{stem}.csv",
        corrected=corrected,
    )
    save_full_csv(result, run_dir / "raw" / f"{stem}_full.csv")
    if corrected is not None:
        save_full_csv(corrected, run_dir / "raw" / f"{stem}_corrected_full.csv")
    if open_result is not None:
        save_full_csv(open_result, run_dir / "raw" / f"{open_short_stem}_open.csv")
        save_origin_csv(open_result, run_dir / "origin_data" / f"{open_short_stem}_open.csv")
    if short_result is not None:
        save_full_csv(short_result, run_dir / "raw" / f"{open_short_stem}_short.csv")
        save_origin_csv(short_result, run_dir / "origin_data" / f"{open_short_stem}_short.csv")

    save_preview_figures(
        result,
        run_dir / "graphs",
        stem=stem,
        corrected=corrected,
    )

    cfg = result.config
    meta: Dict[str, Any] = {
        "sample": safe_sample,
        "section": section,
        "device": device,
        "run_index": run_index,
        "kind": kind_name,
        "notes": note,
        "role": result.role,
        "dc_bias_v": float(result.dc_bias_v),
        "gpib_address": cfg.gpib_address,
        "f_start_hz": cfg.f_start_hz,
        "f_stop_hz": cfg.f_stop_hz,
        "points_per_decade": cfg.points_per_decade,
        "ac_amplitude_v": cfg.ac_amplitude_v,
        "settle_s": cfg.settle_s,
        "timeout_ms": cfg.timeout_ms,
        "n_points": int(len(result.frequencies_hz)),
    }
    if meta_extra:
        meta.update(meta_extra)
    write_run_meta(run_dir, meta)
    if auto_compare:
        _auto_compare_safe(run_dir)
    return run_dir


def export_bias_series_bundle(
    results: list,
    *,
    save_root: Path,
    sample: str,
    section: str,
    device: str,
    notes: str = "",
    open_result: Optional[SweepResult] = None,
    short_result: Optional[SweepResult] = None,
    meta_extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Save all bias sweeps into one allocated run folder."""
    note = sanitize_notes(notes)
    kind_name = f"bias_series_{note}" if note else "bias_series"
    run_dir, run_index, safe_sample = allocate_run_directory(
        save_root, sample, section, device, kind=kind_name
    )
    for i, result in enumerate(results):
        export_run_bundle(
            result,
            save_root=save_root,
            sample=sample,
            section=section,
            device=device,
            kind="bias_series",
            notes=note,
            open_result=open_result if i == 0 else None,
            short_result=short_result if i == 0 else None,
            run_dir=run_dir,
            include_bias_in_name=True,
            auto_compare=False,  # once after full series
            meta_extra={
                **(meta_extra or {}),
                "run_index": run_index,
                "bias_index": i + 1,
                "n_biases": len(results),
                "sample": safe_sample,
                "notes": note,
            },
        )
    # Series-level meta (overwrites per-file last write — keep summary)
    if results:
        cfg = results[-1].config
        write_run_meta(
            run_dir,
            {
                "sample": safe_sample,
                "section": section,
                "device": device,
                "run_index": run_index,
                "kind": kind_name,
                "notes": note,
                "biases_v": [float(r.dc_bias_v) for r in results],
                "gpib_address": cfg.gpib_address,
                "f_start_hz": cfg.f_start_hz,
                "f_stop_hz": cfg.f_stop_hz,
                "points_per_decade": cfg.points_per_decade,
                "ac_amplitude_v": cfg.ac_amplitude_v,
                "settle_s": cfg.settle_s,
                "timeout_ms": cfg.timeout_ms,
                **(meta_extra or {}),
            },
        )
    _auto_compare_safe(run_dir)
    return run_dir
