import os
from pathlib import Path
from typing import Iterable, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import seaborn as sns
except Exception:
    sns = None

from .base import PlotManager


class HDF5StylePlotter:
    """Statistical plots for multi-device analysis (concentration, yield, spacing, etc.)."""

    def __init__(self, save_dir: Optional[Path] = None, auto_close: bool = True):
        self.manager = PlotManager(save_dir=save_dir, auto_close=auto_close)

    # Basic scatter plots -------------------------------------------------
    def plot_concentration_yield(self, x: Sequence, y: Sequence, title_suffix: str = ""):
        fig = plt.figure(figsize=(15, 10))
        x_ser = pd.to_numeric(pd.Series(x), errors="coerce")
        y_ser = pd.to_numeric(pd.Series(y), errors="coerce")
        mask = x_ser.notna() & y_ser.notna()
        plt.scatter(x_ser[mask], y_ser[mask])
        plt.xlabel("Concentration")
        plt.ylabel("Yield")
        plt.title(f"Concentration vs Yield {title_suffix}".strip())
        plt.xticks(
            [0.001, 0.005, 0.05, 1, 0.07, 0.2, 2, 4, 0.4, 0.1],
            ["0.001", "0.005", "0.05", "1", "0.07", "0.2", "2", "4", "0.4", "0.1"],
        )
        return fig

    def plot_concentration_yield_labels(self, x: Sequence, y: Sequence, labels: Iterable[str], title_suffix: str = ""):
        fig = plt.figure(figsize=(15, 10))
        x_ser = pd.to_numeric(pd.Series(x), errors="coerce")
        y_ser = pd.to_numeric(pd.Series(y), errors="coerce")
        labels = list(labels)
        mask = (x_ser.notna() & y_ser.notna()).values
        x_f = x_ser[mask]
        y_f = y_ser[mask]
        labels_f = [labels[i] for i, m in enumerate(mask) if m]
        plt.scatter(x_f, y_f)
        plt.xlabel("Concentration")
        plt.ylabel("Yield")
        plt.title(f"Concentration vs Yield {title_suffix}".strip())
        plt.xticks(
            [0.001, 0.005, 0.05, 1, 0.07, 0.2, 2, 4, 0.4, 0.1, 0.01],
            ["0.001", "0.005", "0.05", "1", "0.07", "0.2", "2", "4", "0.4", "0.1", "0.01"],
        )
        labels_filtered = [lab.split("-")[0] for lab in labels_f]
        for i in range(len(x_f)):
            plt.text(x_f.iloc[i], y_f.iloc[i], labels_filtered[i], fontsize=8, ha="right", va="bottom")
        return fig

    def plot_concentration_spacing(self, x: Sequence, y: Sequence, title_suffix: str = ""):
        fig = plt.figure(figsize=(15, 10))
        x_ser = pd.to_numeric(pd.Series(x), errors="coerce")
        y_ser = pd.to_numeric(pd.Series(y), errors="coerce")
        mask = x_ser.notna() & y_ser.notna()
        plt.scatter(x_ser[mask], y_ser[mask])
        plt.xlabel("Concentration")
        plt.ylabel("Spacing")
        plt.title(f"Concentration vs Spacing {title_suffix}".strip())
        plt.xticks(
            [0.001, 0.005, 0.05, 1, 0.07, 0.2, 2, 4, 0.4, 0.1],
            ["0.001", "0.005", "0.05", "1", "0.07", "0.2", "2", "4", "0.4", "0.1"],
        )
        return fig

    def plot_spacing_yield(self, x: Sequence, y: Sequence, title_suffix: str = "", with_labels: bool = False, labels=None):
        fig = plt.figure(figsize=(15, 10))
        x_ser = pd.to_numeric(pd.Series(x), errors="coerce")
        y_ser = pd.to_numeric(pd.Series(y), errors="coerce")
        labels = list(labels) if labels is not None else []
        if with_labels:
            mask = (x_ser.notna() & y_ser.notna() & (y_ser != 0)).values
            x_ser = x_ser[mask]
            y_ser = y_ser[mask]
            labels = [labels[i] for i, m in enumerate(mask) if m]
        else:
            mask = x_ser.notna() & y_ser.notna()
            x_ser = x_ser[mask]
            y_ser = y_ser[mask]

        plt.scatter(x_ser, y_ser)
        plt.xlabel("Spacing")
        plt.ylabel("Yield")
        plt.title(f"Spacing vs Yield {title_suffix}".strip())
        if with_labels and labels:
            for i in range(len(x_ser)):
                plt.text(x_ser.iloc[i], y_ser.iloc[i], labels[i], fontsize=8, ha="right", va="bottom")
        return fig

    def spacing_yield_concentration_3d(
        self, x: Sequence, y: Sequence, yields: Sequence, labels: Sequence[str], title_suffix: str = ""
    ):
        x = np.array(x)
        y = np.array(y)
        yields = np.array(yields)
        labels = np.array(labels)
        mask = yields != 0
        x_filtered = x[mask]
        y_filtered = y[mask]
        z_filtered = yields[mask]
        labels_filtered = labels[mask]

        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.scatter(x_filtered, y_filtered, z_filtered, c="r")
        ax.set_xlabel("Concentration")
        ax.set_ylabel("Spacing (nm)")
        ax.set_zlabel("Yield")
        ax.set_title(f"3D Spacing, Yield, Concentration {title_suffix}".strip())
        # Optional labels can be re-enabled if desired
        _ = labels_filtered  # keep variable for future use
        return fig

    # Seaborn-based plots -----------------------------------------------
    def facet_concentration_yield_by_polymer(self, df: pd.DataFrame, title_suffix: str = ""):
        if sns is None:
            print("Seaborn not available; skipping facet_concentration_yield_by_polymer")
            return None
        df = df.copy()
        df["Np Concentration"] = pd.to_numeric(df["Np Concentration"], errors="coerce")
        df["Yield"] = pd.to_numeric(df["Yield"], errors="coerce")
        df = df.dropna(subset=["Np Concentration", "Yield"])
        if "Polymer" not in df.columns:
            return None
        g = sns.relplot(
            data=df,
            x="Np Concentration",
            y="Yield",
            col="Polymer",
            kind="scatter",
            col_wrap=3,
            height=4,
            facet_kws={"sharex": False, "sharey": True},
        )
        g.set_titles("{col_name}")
        g.fig.suptitle(f"Concentration vs Yield by Polymer {title_suffix}".strip(), y=1.03)
        return g.fig

    def facet_spacing_yield_by_polymer(self, df: pd.DataFrame, title_suffix: str = ""):
        if sns is None:
            print("Seaborn not available; skipping facet_spacing_yield_by_polymer")
            return None
        df = df.copy()
        if "Polymer" not in df.columns:
            return None
        df["Qd Spacing (nm)"] = pd.to_numeric(df["Qd Spacing (nm)"], errors="coerce")
        df["Yield"] = pd.to_numeric(df["Yield"], errors="coerce")
        df = df.dropna(subset=["Qd Spacing (nm)", "Yield"])
        g = sns.relplot(
            data=df,
            x="Qd Spacing (nm)",
            y="Yield",
            col="Polymer",
            kind="scatter",
            col_wrap=3,
            height=4,
            facet_kws={"sharex": False, "sharey": True},
        )
        g.set_titles("{col_name}")
        g.fig.suptitle(f"Spacing vs Yield by Polymer {title_suffix}".strip(), y=1.03)
        return g.fig

    def correlation_heatmap(self, df: pd.DataFrame):
        if sns is None:
            print("Seaborn not available; skipping correlation_heatmap")
            return None
        numeric_cols = ["Yield", "Np Concentration", "Qd Spacing (nm)", "Volume Fraction", "Volume Fraction %", "Weight Fraction"]
        avail = [c for c in numeric_cols if c in df.columns]
        if not avail:
            return None
        data = df[avail].apply(pd.to_numeric, errors="coerce")
        corr = data.corr()
        fig = plt.figure(figsize=(8, 6))
        sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", vmin=-1, vmax=1)
        plt.title("Correlation Heatmap")
        plt.tight_layout()
        return fig

    def pairplot_numeric(self, df: pd.DataFrame):
        if sns is None:
            print("Seaborn not available; skipping pairplot_numeric")
            return None
        numeric_cols = ["Yield", "Np Concentration", "Qd Spacing (nm)", "Volume Fraction", "Volume Fraction %", "Weight Fraction"]
        avail = [c for c in numeric_cols if c in df.columns]
        if len(avail) < 2:
            return None
        data = df[avail].apply(pd.to_numeric, errors="coerce").dropna()
        g = sns.pairplot(data, diag_kind="kde")
        g.fig.suptitle("Pairplot of Numeric Variables", y=1.02)
        return g.fig

    def violin_yield_by_polymer(self, df: pd.DataFrame):
        if sns is None:
            print("Seaborn not available; skipping violin_yield_by_polymer")
            return None
        if "Polymer" not in df.columns:
            return None
        data = df[["Polymer", "Yield"]].copy()
        data["Yield"] = pd.to_numeric(data["Yield"], errors="coerce")
        data = data.dropna()
        fig = plt.figure(figsize=(10, 6))
        sns.violinplot(data=data, x="Polymer", y="Yield")
        plt.title("Yield distribution by Polymer")
        plt.xticks(rotation=45)
        plt.tight_layout()
        return fig

    def box_yield_by_polymer(self, df: pd.DataFrame):
        if sns is None:
            print("Seaborn not available; skipping box_yield_by_polymer")
            return None
        if "Polymer" not in df.columns:
            return None
        data = df[["Polymer", "Yield"]].copy()
        data["Yield"] = pd.to_numeric(data["Yield"], errors="coerce")
        data = data.dropna()
        fig = plt.figure(figsize=(10, 6))
        sns.boxplot(data=data, x="Polymer", y="Yield")
        plt.title("Yield boxplot by Polymer")
        plt.xticks(rotation=45)
        plt.tight_layout()
        return fig

    # Convenience --------------------------------------------------------
    def save(self, fig, name: str, subdir: Optional[str] = None):
        if self.manager.save_dir is None:
            raise ValueError("save_dir must be set to save figures")
        return self.manager.save(fig, name, subdir=subdir)


