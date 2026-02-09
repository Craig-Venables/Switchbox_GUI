"""
Quick plot of laser power calibration CSV: applied (set_mw) vs actual (measured_mw).

Usage:
  python plot_laser_calibration.py [path_to.csv]
  python plot_laser_calibration.py   # uses latest calibration CSV in this folder
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

OUTPUT_DIR = Path(__file__).resolve().parent
FILENAME_PREFIX = "laser_power_calibration"


def plot_calibration_csv(csv_path: Path) -> None:
    """Plot set_mw (applied) vs measured_mw (actual) from calibration CSV."""
    df = pd.read_csv(csv_path)
    if "set_mw" not in df.columns or "measured_mw" not in df.columns:
        raise ValueError(f"CSV must have 'set_mw' and 'measured_mw' columns. Got: {list(df.columns)}")

    fig, ax = plt.subplots()
    ax.plot(df["set_mw"], df["measured_mw"], "o-", label="Measured", markersize=4)
    max_mw = max(df["set_mw"].max(), df["measured_mw"].max())
    ax.plot([0, max_mw], [0, max_mw], "k--", alpha=0.6, label="Ideal (set = measured)")
    ax.set_xlabel("Applied / set (mW)")
    ax.set_ylabel("Actual / measured (mW)")
    ax.set_title(f"Laser power calibration: {csv_path.name}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal")
    plt.tight_layout()
    plt.show()


def main() -> None:
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
        if not csv_path.is_absolute():
            csv_path = OUTPUT_DIR / csv_path
    else:
        candidates = sorted(OUTPUT_DIR.glob(f"{FILENAME_PREFIX}_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            print(f"No {FILENAME_PREFIX}_*.csv found in {OUTPUT_DIR}")
            sys.exit(1)
        csv_path = candidates[0]
        print(f"Using latest: {csv_path.name}")

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    plot_calibration_csv(csv_path)


if __name__ == "__main__":
    main()
