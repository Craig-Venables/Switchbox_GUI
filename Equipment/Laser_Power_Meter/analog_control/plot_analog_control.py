"""
Plot analog-control laser calibration CSVs: measured power vs analog voltage
for each programmed power-limit curve, all on the same axes.

Usage:
  python plot_analog_control.py            # uses latest CSV in this folder
  python plot_analog_control.py file.csv   # plot a specific CSV
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


OUTPUT_DIR = Path(__file__).resolve().parent


def _plot_one_axes(ax, df: pd.DataFrame, title: str) -> None:
    """Helper to plot measured_mw vs voltage_v for each power_limit_mw on given axes."""
    for pl, sub in df.groupby("power_limit_mw"):
        sub_sorted = sub.sort_values("voltage_v")

        # Base style: slightly smaller markers
        is_default_limit = abs(pl - 100.0) < 1e-6
        line_kwargs = {
            "marker": "o",
            "linestyle": "-",
            "markersize": 2,  # smaller dots
            "label": f"{pl:.1f} mW limit",
        }
        if is_default_limit:
            # Make the 100 mW limit stand out
            line_kwargs["linewidth"] = 2.0

        line = ax.plot(
            sub_sorted["voltage_v"],
            sub_sorted["measured_mw"],
            **line_kwargs,
        )[0]

        # If this curve is truncated by the 50 mW safety limit, extend it
        # linearly out to 2.5 V as a dashed extrapolated segment (no legend).
        try:
            max_meas = float(sub_sorted["measured_mw"].max())
        except ValueError:
            continue
        if max_meas >= 50.0 and sub_sorted["voltage_v"].max() < 2.5 and len(sub_sorted) >= 2:
            v_last = float(sub_sorted["voltage_v"].iloc[-1])
            p_last = float(sub_sorted["measured_mw"].iloc[-1])
            v_prev = float(sub_sorted["voltage_v"].iloc[-2])
            p_prev = float(sub_sorted["measured_mw"].iloc[-2])
            if v_last > v_prev:
                slope = (p_last - p_prev) / (v_last - v_prev)
                v_extrap = 2.5
                p_extrap = p_last + slope * (v_extrap - v_last)
                ax.plot(
                    [v_last, v_extrap],
                    [p_last, p_extrap],
                    linestyle="--",
                    linewidth=1.0,
                    alpha=0.6,
                    color=line.get_color(),
                )

    ax.set_xlabel("Analog control voltage (V)")
    ax.set_ylabel("Measured power (mW)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(title="Power limit (solid = measured, dashed = extrapolated)")


def plot_analog_csv(csv_path: Path) -> None:
    """Plot several views of measured_mw vs voltage_v and save PNGs."""
    df = pd.read_csv(csv_path)
    required = {"power_limit_mw", "voltage_v", "measured_mw"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV must have columns {required}. Missing: {missing}")

    # Only plot up to 2.5 V
    df = df[df["voltage_v"] <= 2.5].copy()

    stem = csv_path.stem

    # 1) View limited to 0–50 mW
    fig1, ax1 = plt.subplots(figsize=(16, 9))
    _plot_one_axes(ax1, df, f"{stem} (0–50 mW)")
    ax1.set_ylim(0, 50)
    fig1.tight_layout()
    png1 = csv_path.with_name(f"{stem}_0-50mW.png")
    fig1.savefig(png1, dpi=300)

    # 2) Full-power view (auto y-limits)
    fig2, ax2 = plt.subplots(figsize=(16, 9))
    _plot_one_axes(ax2, df, f"{stem} (full range)")
    fig2.tight_layout()
    png2 = csv_path.with_name(f"{stem}_full.png")
    fig2.savefig(png2, dpi=300)

    # 3) Zoomed view 0–0.5 V
    fig3, ax3 = plt.subplots(figsize=(16, 9))
    _plot_one_axes(ax3, df, f"{stem} (0–0.5 V zoom)")
    ax3.set_xlim(0, 0.5)
    ax3.set_ylim(0, 10)
    fig3.tight_layout()
    png3 = csv_path.with_name(f"{stem}_0-0.5V.png")
    fig3.savefig(png3, dpi=300)

    # Optionally show the last figure interactively
    plt.show()


def main() -> None:
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
        if not csv_path.is_absolute():
            csv_path = OUTPUT_DIR / csv_path
    else:
        candidates = sorted(
            OUTPUT_DIR.glob("analog_power_calibration*.csv"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            print(f"No analog_power_calibration*.csv found in {OUTPUT_DIR}")
            raise SystemExit(1)
        csv_path = candidates[0]
        print(f"Using latest: {csv_path.name}")

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        raise SystemExit(1)

    plot_analog_csv(csv_path)


if __name__ == "__main__":
    main()

