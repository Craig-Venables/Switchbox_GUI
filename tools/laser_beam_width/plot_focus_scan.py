#!/usr/bin/env python3
"""Plot beam width vs Z focus from saved beam_width snapshots."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


def _parse_z_mm(folder_name: str) -> Optional[float]:
    match = re.search(r"([\d.]+)", folder_name.replace(",", "."))
    return float(match.group(1)) if match else None


def rate_fit(fit: Dict[str, Any]) -> str:
    if not fit:
        return "No data"
    r2_min = min(float(fit.get("r2_x", 0)), float(fit.get("r2_y", 0)))
    r2_2d = float(fit.get("r2_2d", 0))
    ok = bool(fit.get("ok", False))
    sat = float(fit.get("saturation_pct", 0))
    snr = float(fit.get("snr", 0))

    if ok and r2_min >= 0.95 and r2_2d >= 0.90:
        return "Excellent"
    if ok:
        return "Good"
    if r2_min >= 0.85 and sat < 5.0 and snr >= 5.0:
        return "Marginal"
    if r2_min >= 0.75:
        return "Weak"
    return "Poor"


RATING_COLORS = {
    "Excellent": "#16a34a",
    "Good": "#22c55e",
    "Marginal": "#f59e0b",
    "Weak": "#f97316",
    "Poor": "#ef4444",
    "No data": "#6b7280",
}


def load_focus_scan(root: Path) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        z_mm = _parse_z_mm(folder.name)
        if z_mm is None:
            continue
        json_files = sorted(folder.glob("beam_width_*.json"))
        if not json_files:
            continue
        meta_path = json_files[-1]
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        fit = meta.get("fit") or {}
        cal = meta.get("calibration") or {}
        um_per_px = cal.get("um_per_pixel")
        stamp = meta_path.stem.replace("beam_width_", "")
        png = meta_path.with_suffix(".png")

        def um(name: str) -> Optional[float]:
            if um_per_px is None:
                return None
            val = fit.get(name)
            return float(val) * float(um_per_px) if val is not None else None

        row = {
            "z_mm": z_mm,
            "folder": folder.name,
            "timestamp": stamp,
            "png": str(png) if png.exists() else "",
            "rating": rate_fit(fit),
            "ok": bool(fit.get("ok", False)),
            "message": fit.get("message", ""),
            "r2_x": float(fit.get("r2_x", np.nan)),
            "r2_y": float(fit.get("r2_y", np.nan)),
            "r2_2d": float(fit.get("r2_2d", np.nan)),
            "r2_min": min(float(fit.get("r2_x", 0)), float(fit.get("r2_y", 0))),
            "snr": float(fit.get("snr", np.nan)),
            "saturation_pct": float(fit.get("saturation_pct", np.nan)),
            "fwhm_x_um": um("fwhm_x_px"),
            "fwhm_y_um": um("fwhm_y_px"),
            "major_fwhm_um": um("major_fwhm_px"),
            "minor_fwhm_um": um("minor_fwhm_px"),
            "mean_fwhm_um": np.mean([v for v in (um("fwhm_x_px"), um("fwhm_y_px")) if v is not None])
            if um_per_px
            else np.nan,
            "e2_mean_um": np.mean([v for v in (um("e2_x_px"), um("e2_y_px")) if v is not None])
            if um_per_px
            else np.nan,
            "ellipticity": (
                float(fit["major_fwhm_px"]) / max(float(fit["minor_fwhm_px"]), 1e-9)
                if fit.get("major_fwhm_px") and fit.get("minor_fwhm_px")
                else np.nan
            ),
            "um_per_pixel": um_per_px,
        }
        rows.append(row)

    if not rows:
        raise FileNotFoundError(f"No beam_width_*.json found under {root}")
    df = pd.DataFrame(rows).sort_values("z_mm").reset_index(drop=True)
    return df


def _crop_to_analysis_roi(img: np.ndarray, *, margin_frac: float = 0.06) -> np.ndarray:
    """Crop a saved snapshot to the analysis ROI rectangle (teal box in overlay)."""
    rgb = img[..., :3]
    if rgb.dtype != np.uint8:
        rgb = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    # ROI outline: BGR (180, 120, 0) -> RGB (0, 120, 180)
    target = np.array([0, 120, 180], dtype=np.int16)
    mask = np.all(np.abs(rgb.astype(np.int16) - target) <= 35, axis=2)
    ys, xs = np.where(mask)
    if xs.size < 4:
        h, w = rgb.shape[:2]
        side = min(h, w) // 3
        cy, cx = h // 2, w // 2
        return img[max(0, cy - side) : cy + side, max(0, cx - side) : cx + side]
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    mx = int((x1 - x0) * margin_frac)
    my = int((y1 - y0) * margin_frac)
    h, w = rgb.shape[:2]
    x0, y0 = max(0, x0 - mx), max(0, y0 - my)
    x1, y1 = min(w, x1 + mx + 1), min(h, y1 + my + 1)
    return img[y0:y1, x0:x1]


def _parabolic_best_focus(z: np.ndarray, w: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Return (z_best_mm, w_min_um, fitted_curve)."""
    coef = np.polyfit(z, w, 2)
    z_fine = np.linspace(z.min(), z.max(), 200)
    w_fine = np.polyval(coef, z_fine)
    if coef[0] > 0:
        z_best = -coef[1] / (2 * coef[0])
        w_min = float(np.polyval(coef, z_best))
    else:
        idx = int(np.argmin(w))
        z_best = float(z[idx])
        w_min = float(w[idx])
    return float(z_best), w_min, w_fine


def plot_focus_scan(df: pd.DataFrame, out_dir: Path, title: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "focus_scan_summary.csv", index=False)

    z = df["z_mm"].values
    colors = [RATING_COLORS.get(r, "#888") for r in df["rating"]]

    fig = plt.figure(figsize=(15, 13))
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)
    gs = GridSpec(
        3,
        3,
        figure=fig,
        height_ratios=[1.05, 0.95, 1.45],
        hspace=0.62,
        wspace=0.38,
        top=0.93,
        bottom=0.05,
        left=0.07,
        right=0.97,
    )

    # --- FWHM vs focus ---
    ax1 = fig.add_subplot(gs[0, 0:2])
    ax1.plot(z, df["major_fwhm_um"], "o-", color="#2563eb", label="Major FWHM", lw=1.5, ms=6)
    ax1.plot(z, df["minor_fwhm_um"], "s-", color="#7c3aed", label="Minor FWHM", lw=1.5, ms=5)
    ax1.plot(z, df["mean_fwhm_um"], "D-", color="#0f766e", label="Mean FWHM", lw=2, ms=5)
    for xi, yi, c, r in zip(z, df["mean_fwhm_um"], colors, df["rating"]):
        ax1.scatter([xi], [yi], c=[c], s=80, zorder=5, edgecolors="k", linewidths=0.4)
    if df["mean_fwhm_um"].notna().all() and len(z) >= 3:
        z_best, w_min, _ = _parabolic_best_focus(z, df["mean_fwhm_um"].values)
        if z.min() <= z_best <= z.max():
            ax1.axvline(z_best, color="#dc2626", ls="--", lw=1.2, alpha=0.8)
            ax1.annotate(
                f"Best focus ≈ {z_best:.2f} mm\nFWHM ≈ {w_min:.1f} µm",
                xy=(z_best, w_min),
                xytext=(20, 28),
                textcoords="offset points",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.35", fc="white", alpha=0.9),
                arrowprops=dict(arrowstyle="->", color="#dc2626", lw=0.8),
            )
    ax1.set_xlabel("Z position (mm)")
    ax1.set_ylabel("FWHM (µm)")
    ax1.set_title("Spot size vs focus")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="best", fontsize=8)

    # --- 1/e² vs focus ---
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.plot(z, df["e2_mean_um"], "o-", color="#0369a1", lw=1.5)
    for xi, yi, c in zip(z, df["e2_mean_um"], colors):
        ax2.scatter([xi], [yi], c=[c], s=60, zorder=5, edgecolors="k", linewidths=0.4)
    ax2.set_xlabel("Z (mm)")
    ax2.set_ylabel("Mean 1/e² (µm)")
    ax2.set_title("1/e² diameter")
    ax2.grid(True, alpha=0.3)

    # --- R² ---
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(z, df["r2_x"], "o-", label="R² X", ms=5)
    ax3.plot(z, df["r2_y"], "s-", label="R² Y", ms=5)
    ax3.plot(z, df["r2_2d"], "^-", label="R² 2D", ms=5)
    ax3.axhline(0.85, color="#ef4444", ls=":", lw=1, label="Threshold 0.85")
    ax3.set_ylim(0, 1.02)
    ax3.set_xlabel("Z (mm)")
    ax3.set_ylabel("R²")
    ax3.set_title("Gaussian fit quality")
    ax3.legend(fontsize=7)
    ax3.grid(True, alpha=0.3)

    # --- Ellipticity ---
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(z, df["ellipticity"], "o-", color="#b45309", lw=1.5)
    ax4.axhline(1.0, color="#666", ls="--", lw=0.8)
    ax4.set_xlabel("Z (mm)")
    ax4.set_ylabel("Major / minor FWHM")
    ax4.set_title("Ellipticity (1 = round)")
    ax4.grid(True, alpha=0.3)

    # --- SNR ---
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.semilogy(z, df["snr"], "o-", color="#059669", lw=1.5)
    ax5.set_xlabel("Z (mm)")
    ax5.set_ylabel("SNR")
    ax5.set_title("Signal / noise")
    ax5.grid(True, alpha=0.3)

    # --- Rating table ---
    ax6 = fig.add_subplot(gs[2, 0:2])
    ax6.axis("off")
    table_data = []
    for _, row in df.iterrows():
        table_data.append(
            [
                f"{row['z_mm']:.1f}",
                row["rating"],
                "✓" if row["ok"] else "✗",
                f"{row['r2_min']:.3f}",
                f"{row['mean_fwhm_um']:.1f}",
                f"{row['ellipticity']:.2f}",
                row["message"][:40],
            ]
        )
    col_labels = ["Z mm", "Fit", "OK", "R² min", "FWHM µm", "Ellip.", "Note"]
    table = ax6.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    table.scale(1, 1.15)
    for i, row in enumerate(df.itertuples()):
        rating = row.rating
        table[(i + 1, 1)].set_facecolor(RATING_COLORS.get(rating, "#eee"))
    ax6.set_title("Per-position fit summary", pad=12, y=1.02)

    # --- Legend + best focus text ---
    ax7 = fig.add_subplot(gs[2, 2])
    ax7.axis("off")
    legend_items = [Patch(facecolor=c, label=k) for k, c in RATING_COLORS.items() if k != "No data"]
    ax7.legend(handles=legend_items, loc="upper center", title="Fit rating", fontsize=8, frameon=True)
    best_idx = int(df["mean_fwhm_um"].idxmin())
    best = df.loc[best_idx]
    lines = [
        "Best measured focus:",
        f"  Z = {best['z_mm']:.2f} mm",
        f"  Mean FWHM = {best['mean_fwhm_um']:.1f} µm",
        f"  Rating = {best['rating']}",
        "",
        f"N positions: {len(df)}",
        f"Good+ fits: {(df['rating'].isin(['Excellent','Good'])).sum()}",
    ]
    if df["mean_fwhm_um"].notna().all() and len(z) >= 3:
        z_best, w_min, _ = _parabolic_best_focus(z, df["mean_fwhm_um"].values)
        lines.extend(["", f"Parabolic est.: Z≈{z_best:.2f} mm", f"  FWHM≈{w_min:.1f} µm"])
    ax7.text(
        0.05,
        0.42,
        "\n".join(lines),
        va="top",
        ha="left",
        fontsize=9,
        family="monospace",
        transform=ax7.transAxes,
    )

    fig.savefig(out_dir / "focus_scan_report.png", dpi=160, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)

    # --- Spot montage ---
    pngs = [(row.z_mm, row.png, row.rating, row.mean_fwhm_um) for row in df.itertuples() if row.png]
    if pngs:
        n = len(pngs)
        cols = min(5, n)
        rows_n = int(np.ceil(n / cols))
        fig2, axes = plt.subplots(
            rows_n,
            cols,
            figsize=(2.8 * cols, 2.8 * rows_n),
            constrained_layout=True,
        )
        fig2.suptitle(f"{title} — spot images (ROI crop)", fontsize=12, y=1.02)
        axes_flat = np.atleast_1d(axes).flatten()
        for ax, (z_mm, path, rating, w) in zip(axes_flat, pngs):
            img = _crop_to_analysis_roi(plt.imread(path))
            ax.imshow(img)
            ax.set_title(f"Z={z_mm:.1f} mm\nFWHM≈{w:.1f} µm [{rating}]", fontsize=8, pad=4)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(0.5)
                spine.set_color("#ccc")
        for ax in axes_flat[len(pngs) :]:
            ax.axis("off")
        fig2.savefig(out_dir / "focus_scan_montage.png", dpi=150, bbox_inches="tight", pad_inches=0.2)
        plt.close(fig2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot beam width vs Z from saved snapshots")
    parser.add_argument("data_dir", type=Path, help="Folder with subfolders per Z (e.g. 9.5mm/)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output folder (default: <data_dir>/analysis)",
    )
    parser.add_argument("-t", "--title", default=None, help="Plot title")
    args = parser.parse_args()

    data_dir = args.data_dir.expanduser().resolve()
    out_dir = (args.output or data_dir / "analysis").resolve()
    title = args.title or f"Focus scan — {data_dir.name}"

    df = load_focus_scan(data_dir)
    plot_focus_scan(df, out_dir, title)
    print(f"Loaded {len(df)} positions")
    print(df[["z_mm", "rating", "mean_fwhm_um", "r2_min", "ok"]].to_string(index=False))
    print(f"\nSaved to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
