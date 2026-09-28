"""Plot device yield against polymer fraction and phase separation.

The dataset is a small labelled table kept in this file. Figures are written
to output/ next to this script.
"""

import io
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

DATA = """
Sample,yield,concentration,polymer,separation
79,3,0.1,3,30.65
80,81,0.1,2,26.44
81,0,0.07,3,35.76
82,80,0.07,2,32.12
83,67,0.05,3,41.49
84,20,0.05,2,36.73
87,5,0.05,3,41.49
89,50,0.05,2,36.73
"""


def main() -> None:
    df = pd.read_csv(io.StringIO(DATA.strip()))
    OUTPUT_DIR.mkdir(exist_ok=True)
    np.random.seed(42)

    plt.figure(figsize=(6.5, 5.2))
    sns.boxplot(
        data=df,
        x="polymer",
        y="yield",
        hue="polymer",
        palette="Pastel1",
        width=0.42,
        zorder=1,
        legend=False,
    )
    for _, row in df.iterrows():
        x_val = 0 if row["polymer"] == 2 else 1
        jitter = np.random.uniform(-0.05, 0.05)
        plt.scatter(x_val + jitter, row["yield"], color="black", edgecolor="white", s=80, zorder=3)
        plt.text(
            x_val + jitter + 0.06,
            row["yield"],
            f"S{int(row['Sample'])}",
            fontsize=9,
            verticalalignment="center",
            zorder=4,
            fontweight="bold",
        )

    plt.title("Yield by Polymer Percentage (with Sample Labels)")
    plt.xlabel("Polymer (%)")
    plt.ylabel("Yield (%)")
    plt.xticks([0, 1], ["2%", "3%"])
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.xlim(-0.60, 1.60)
    plt.ylim(-14, 114)
    plt.tight_layout(pad=1.1)
    polymer_path = OUTPUT_DIR / "yield_by_polymer_labeled.png"
    plt.savefig(polymer_path, dpi=150, bbox_inches="tight", pad_inches=0.25)
    plt.close()

    plt.figure(figsize=(7, 5))
    sns.scatterplot(
        data=df,
        x="separation",
        y="yield",
        hue="polymer",
        size="concentration",
        palette="Set1",
        sizes=(60, 200),
        alpha=0.8,
    )
    for _, row in df.iterrows():
        plt.text(
            row["separation"] + 0.5,
            row["yield"] - 1,
            f"S{int(row['Sample'])}",
            fontsize=9,
            verticalalignment="center",
            fontweight="bold",
        )

    plt.title("Device Yield vs. Internal Phase Separation")
    plt.xlabel("Separation (nm)")
    plt.ylabel("Yield (%)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.xlim(24, 45)
    plt.ylim(-10, 110)
    plt.legend(title="Variables", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    separation_path = OUTPUT_DIR / "yield_vs_separation.png"
    plt.savefig(separation_path, dpi=150)
    plt.close()

    print(f"Saved {polymer_path}")
    print(f"Saved {separation_path}")


if __name__ == "__main__":
    main()
