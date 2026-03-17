"""
Compare one or more analog-control calibration CSVs measured at different
device/sample positions against a common reference (sample bottom).

It:
  - Loads a reference CSV (no glass / baseline) and one or more "through"
    CSVs (glass, ITO, etc.) that share the same (power_limit_mw, voltage_v)
    grid.
  - For each through CSV:
      * Computes transmission = through / reference and % drop.
      * Prints per-limit and overall statistics and saves them to a text file.
      * Creates a scatter plot: reference vs through, with y=x (no loss).
  - Additionally, produces a combined scatter plot showing all through cases
    together for easy comparison.

Defaults:
  - Reference (no glass):   analog_control/at_sample_btm/analog_power_calibration.csv
  - Through sample (glass): analog_control/at_device (through sample)/analog_power_calibration.csv
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REF_DIR = BASE_DIR / "at_sample_btm"
THROUGH_DIR = BASE_DIR / "at_device (through sample)"
REF_CSV = REF_DIR / "analog_power_calibration.csv"
THROUGH_CSV = THROUGH_DIR / "analog_power_calibration.csv"
OUT_DIR = BASE_DIR / "comparisons"


def _load_pair(
    ref_csv: Path,
    through_csv: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    required = {"power_limit_mw", "voltage_v", "measured_mw"}

    if not ref_csv.exists():
        raise FileNotFoundError(f"Reference CSV not found: {ref_csv}")
    if not through_csv.exists():
        raise FileNotFoundError(f"Through-sample CSV not found: {through_csv}")

    ref = pd.read_csv(ref_csv)
    thr = pd.read_csv(through_csv)

    missing_ref = required - set(ref.columns)
    missing_thr = required - set(thr.columns)
    if missing_ref:
        raise ValueError(f"Reference CSV missing columns {missing_ref} in {ref_csv}")
    if missing_thr:
        raise ValueError(f"Through-sample CSV missing columns {missing_thr} in {through_csv}")

    # Use power_limit + voltage as a key and inner-join so we only compare
    # points present in both.
    ref_keyed = ref.set_index(["power_limit_mw", "voltage_v"]).sort_index()
    thr_keyed = thr.set_index(["power_limit_mw", "voltage_v"]).sort_index()
    both = ref_keyed.join(
        thr_keyed[["measured_mw"]],
        how="inner",
        lsuffix="_ref",
        rsuffix="_thr",
    ).reset_index()

    if both.empty:
        raise ValueError("No overlapping (power_limit_mw, voltage_v) points between the two CSVs.")

    return ref, both


def _label_for_csv(csv_path: Path) -> str:
    """Generate a short label from a CSV path (e.g., 'through_sample', 'ITO')."""
    parent = csv_path.parent.name
    stem = csv_path.stem
    # Prefer folder name if it's informative
    if parent and parent not in (BASE_DIR.name, "analog_control"):
        return parent.replace(" ", "_")
    return stem.replace("analog_power_calibration", "").strip("_") or "through"


def _analyze_one(
    ref_csv: Path,
    through_csv: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, str, str]:
    """
    Run the analysis for a single through CSV.

    Returns:
      - df: aligned dataframe with ref/through/measures
      - valid: subset with valid points
      - summary_path: path to the written txt summary
      - label: short label for this through dataset
    """
    print(f"\n=== Comparing reference vs {through_csv} ===")

    _, df = _load_pair(ref_csv, through_csv)

    # Rename columns for clarity
    df = df.rename(
        columns={
            "measured_mw_ref": "power_ref_mw",
            "measured_mw_thr": "power_through_mw",
        }
    )

    # Compute transmission and % drop, ignoring zeros/negatives for ratios
    mask_valid = (df["power_ref_mw"] > 0) & (df["power_through_mw"] >= 0)
    df["transmission"] = df["power_through_mw"] / df["power_ref_mw"]
    df["percent_drop"] = (1.0 - df["transmission"]) * 100.0

    valid = df[mask_valid].copy()

    # Prepare text summary for both console and file
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    label = _label_for_csv(through_csv)
    summary_lines: List[str] = []
    summary_lines.append(f"Reference CSV (no glass):   {ref_csv}")
    summary_lines.append(f"Through-sample CSV ({label}): {through_csv}")

    if valid.empty:
        msg = "No valid (non-zero reference) points to compute transmission."
        print(msg)
        summary_lines.append(msg)
    else:
        overall_trans = valid["transmission"].mean()
        overall_drop = valid["percent_drop"].mean()
        print("\n=== Overall transmission statistics ===")
        print(f"Mean transmission: {overall_trans*100:.2f} %")
        print(f"Mean % drop:       {overall_drop:.2f} %")
        summary_lines.append("")
        summary_lines.append("=== Overall transmission statistics ===")
        summary_lines.append(f"Mean transmission: {overall_trans*100:.2f} %")
        summary_lines.append(f"Mean % drop:       {overall_drop:.2f} %")

        print("\nPer power-limit statistics:")
        summary_lines.append("")
        summary_lines.append("Per power-limit statistics:")
        for pl, sub in valid.groupby("power_limit_mw"):
            t = sub["transmission"].mean()
            d = sub["percent_drop"].mean()
            line = f"  Limit {pl:6.1f} mW: transmission {t*100:6.2f} %, drop {d:6.2f} %"
            print(line)
            summary_lines.append(line)

    # Write summary to text file
    summary_path = OUT_DIR / f"through_vs_bottom_summary_{_label_for_csv(through_csv)}.txt"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    # Scatter plot: reference vs through, with y=x line (per material)
    fig, ax = plt.subplots(figsize=(10, 10))

    for pl, sub in df.groupby("power_limit_mw"):
        ax.scatter(
            sub["power_ref_mw"],
            sub["power_through_mw"],
            s=10,
            alpha=0.7,
            label=f"{pl:.1f} mW limit",
        )

    max_ref = df["power_ref_mw"].max()
    max_thr = df["power_through_mw"].max()
    max_val = max(max_ref, max_thr) * 1.05
    ax.plot([0, max_val], [0, max_val], "k--", alpha=0.5, label="y = x (no loss)")

    ax.set_xlabel("Power at sample bottom (mW)")
    ax.set_ylabel(f"Power through sample ({label}) (mW)")
    ax.set_title(f"Through-sample vs bottom power ({label})")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Power limit")
    plt.tight_layout()

    out_png = OUT_DIR / f"through_vs_bottom_scatter_{label}.png"
    fig.savefig(out_png, dpi=300)
    plt.close(fig)

    print(f"Saved comparison plot to: {out_png}")
    print(f"Saved numerical summary to: {summary_path}")

    return df, valid, str(summary_path), label


def main() -> int:
    # CLI:
    #   compare_through_vs_bottom.py ref.csv glass.csv ito.csv ...
    # If only ref is omitted, use default ref and default "through sample".
    if len(sys.argv) >= 3:
        ref_csv = Path(sys.argv[1])
        through_csvs = [Path(p) for p in sys.argv[2:]]
    else:
        ref_csv = REF_CSV
        # Default "through" list: glass, plus optionally ITO if present later.
        through_csvs = [THROUGH_CSV]

    if not ref_csv.is_absolute():
        ref_csv = BASE_DIR / ref_csv
    through_abs: List[Path] = []
    for p in through_csvs:
        if not p.is_absolute():
            p = BASE_DIR / p
        through_abs.append(p)

    print(f"Reference CSV (no glass): {ref_csv}")

    # Run per-material analysis
    per_material_data: Dict[str, pd.DataFrame] = {}
    for t_csv in through_abs:
        if not t_csv.exists():
            print(f"Skipping missing through-sample CSV: {t_csv}")
            continue
        try:
            df, _, _, label = _analyze_one(ref_csv, t_csv)
            per_material_data[label] = df
        except Exception as e:
            print(f"Error analyzing {t_csv}: {e}")

    if not per_material_data:
        print("No valid through-sample datasets processed.")
        return 1

    # Combined scatter: reference vs through for all materials
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 10))

    for label, df in per_material_data.items():
        ax.scatter(
            df["power_ref_mw"],
            df["power_through_mw"],
            s=10,
            alpha=0.6,
            label=label,
        )

    # y = x line
    all_ref = pd.concat([df["power_ref_mw"] for df in per_material_data.values()])
    all_thr = pd.concat([df["power_through_mw"] for df in per_material_data.values()])
    max_val = max(all_ref.max(), all_thr.max()) * 1.05
    ax.plot([0, max_val], [0, max_val], "k--", alpha=0.5, label="y = x (no loss)")

    ax.set_xlabel("Power at sample bottom (mW)")
    ax.set_ylabel("Power through sample (mW)")
    ax.set_title("Through-sample vs bottom power (all materials)")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Material / position")
    plt.tight_layout()

    combined_png = OUT_DIR / "through_vs_bottom_scatter_all_materials.png"
    fig.savefig(combined_png, dpi=300)
    plt.show()

    print(f"\nSaved combined comparison plot to: {combined_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

