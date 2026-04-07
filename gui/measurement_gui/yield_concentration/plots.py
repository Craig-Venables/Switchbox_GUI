"""
Yield and Concentration Plots
================================

Two public plot generators:

``generate_sample_level_plots(sample_df, output_dir, ...)``
    Cross-sample comparison plots. Each point = one sample/substrate.
    Requires columns: sample_name, sample_yield, Np Concentration,
    Qd Spacing (nm), Polymer, Volume Fraction %.

``generate_device_level_plots(device_df, output_dir, ...)``
    Per-device detail plots. Each point = one pixel/device.
    Requires columns: device_id, sample_name, yield, classification_type,
    avg_resistance_first_sweep, Np Concentration, Qd Spacing (nm), Polymer.

Plots that require columns which are entirely NaN are skipped with a warning.
"""

from __future__ import annotations

import os
from typing import Callable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import seaborn as sns
    _HAS_SNS = True
except ImportError:
    _HAS_SNS = False

_TYPE_COLOURS = {
    "memristive": "#4CAF50",
    "ohmic": "#2196F3",
    "capacitive": "#FF9800",
    "half-sweep": "#9C27B0",
    "unknown": "#9E9E9E",
}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def generate_sample_level_plots(
    sample_df: pd.DataFrame,
    output_dir: str,
    title_suffix: str = "",
    analysis_mode: str = "device",
    log_fn: Callable[[str], None] = print,
) -> list[str]:
    """Generate cross-sample comparison plots (one point = one substrate).

    Returns list of created PNG paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    created: list[str] = []

    def _save(fig: plt.Figure, name: str) -> None:
        path = os.path.join(output_dir, name)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        created.append(path)

    def _col_ok(*cols: str) -> bool:
        for c in cols:
            if c not in sample_df.columns or sample_df[c].dropna().empty:
                log_fn(f"[YIELD PLOTS] Skipping sample plot: '{c}' missing or all-NaN")
                return False
        return True

    df = sample_df.copy()

    if str(analysis_mode).lower().startswith("sample"):
        return _generate_sample_focused_plots(df, output_dir, _col_ok, _save, title_suffix, log_fn)

    # Concentration scatter — linear
    if _col_ok("Np Concentration", "sample_yield"):
        fig, ax = plt.subplots(figsize=(11, 7))
        ax.scatter(df["Np Concentration"], df["sample_yield"], alpha=0.8, s=80, edgecolors="k", linewidths=0.5)
        if "sample_name" in df.columns:
            for _, row in df.dropna(subset=["Np Concentration", "sample_yield"]).iterrows():
                label = str(row["sample_name"]).split("-")[0]
                ax.annotate(label, (row["Np Concentration"], row["sample_yield"]),
                            fontsize=7, ha="left", va="bottom", textcoords="offset points", xytext=(4, 2))
        ax.set_xlabel("Np Concentration (mg/ml)")
        ax.set_ylabel("Yield (fraction)")
        ax.set_title(f"Concentration vs Yield (linear x){title_suffix}")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
        _save(fig, "sample_concentration_yield_linear.png")

    # Concentration scatter — log x
    if _col_ok("Np Concentration", "sample_yield"):
        pos = df[df["Np Concentration"] > 0].copy()
        if not pos.empty:
            fig, ax = plt.subplots(figsize=(11, 7))
            ax.scatter(pos["Np Concentration"], pos["sample_yield"], alpha=0.8, s=80, edgecolors="k", linewidths=0.5)
            if "sample_name" in pos.columns:
                for _, row in pos.dropna(subset=["Np Concentration", "sample_yield"]).iterrows():
                    label = str(row["sample_name"]).split("-")[0]
                    ax.annotate(label, (row["Np Concentration"], row["sample_yield"]),
                                fontsize=7, ha="left", va="bottom", textcoords="offset points", xytext=(4, 2))
            ax.set_xscale("log")
            ax.set_xlabel("Np Concentration (mg/ml) [log scale]")
            ax.set_ylabel("Yield (fraction)")
            ax.set_title(f"Concentration vs Yield (log x){title_suffix}")
            ax.set_ylim(-0.05, 1.05)
            ax.grid(True, alpha=0.3, which="both")
            _save(fig, "sample_concentration_yield_log.png")

    # Spacing vs Yield
    if _col_ok("Qd Spacing (nm)", "sample_yield"):
        fig, ax = plt.subplots(figsize=(11, 7))
        ax.scatter(df["Qd Spacing (nm)"], df["sample_yield"], alpha=0.8, s=80, edgecolors="k", linewidths=0.5)
        if "sample_name" in df.columns:
            for _, row in df.dropna(subset=["Qd Spacing (nm)", "sample_yield"]).iterrows():
                label = str(row["sample_name"]).split("-")[0]
                ax.annotate(label, (row["Qd Spacing (nm)"], row["sample_yield"]),
                            fontsize=7, ha="left", va="bottom", textcoords="offset points", xytext=(4, 2))
        ax.set_xlabel("Qd Spacing (nm)")
        ax.set_ylabel("Yield (fraction)")
        ax.set_title(f"Spacing vs Yield{title_suffix}")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
        _save(fig, "sample_spacing_yield.png")

    # 3D
    if _col_ok("Np Concentration", "Qd Spacing (nm)", "sample_yield"):
        sub = df.dropna(subset=["Np Concentration", "Qd Spacing (nm)", "sample_yield"]).copy()
        sub = sub[sub["Np Concentration"] > 0]
        if not sub.empty:
            try:
                fig = plt.figure(figsize=(12, 8))
                ax3d = fig.add_subplot(111, projection="3d")
                sc = ax3d.scatter(
                    np.log10(sub["Np Concentration"].astype(float)),
                    sub["Qd Spacing (nm)"].astype(float),
                    sub["sample_yield"].astype(float),
                    c=sub["sample_yield"].astype(float), cmap="viridis", alpha=0.9, s=60,
                )
                fig.colorbar(sc, ax=ax3d, label="Yield")
                ax3d.set_xlabel("log10(Np Conc.)")
                ax3d.set_ylabel("Qd Spacing (nm)")
                ax3d.set_zlabel("Yield")
                ax3d.set_title(f"3D: Concentration vs Spacing vs Yield{title_suffix}")
                _save(fig, "sample_3d_concentration_spacing_yield.png")
            except Exception as exc:
                log_fn(f"[YIELD PLOTS] 3D plot failed: {exc}")

    if not _HAS_SNS:
        log_fn("[YIELD PLOTS] seaborn not available — skipping facet/violin/box/heatmap")
        return created

    # Facet: Concentration vs Yield by Polymer
    if _col_ok("Np Concentration", "sample_yield", "Polymer"):
        sub = df.dropna(subset=["Np Concentration", "sample_yield", "Polymer"]).copy()
        sub["Np Concentration"] = pd.to_numeric(sub["Np Concentration"], errors="coerce")
        sub["sample_yield"] = pd.to_numeric(sub["sample_yield"], errors="coerce")
        sub = sub.dropna(subset=["Np Concentration", "sample_yield"])
        if not sub.empty and len(sub["Polymer"].unique()) >= 2:
            try:
                g = sns.FacetGrid(sub, col="Polymer", col_wrap=3, height=4, sharex=False, sharey=True)
                g.map(plt.scatter, "Np Concentration", "sample_yield", alpha=0.8)
                g.set_axis_labels("Np Concentration (mg/ml)", "Yield")
                g.fig.suptitle(f"Concentration vs Yield by Polymer{title_suffix}", y=1.02)
                g.tight_layout()
                path = os.path.join(output_dir, "sample_facet_concentration_yield_by_polymer.png")
                g.savefig(path, dpi=150, bbox_inches="tight")
                plt.close("all")
                created.append(path)
            except Exception as exc:
                log_fn(f"[YIELD PLOTS] Facet conc/yield by polymer: {exc}")

    # Facet: Spacing vs Yield by Polymer
    if _col_ok("Qd Spacing (nm)", "sample_yield", "Polymer"):
        sub = df.dropna(subset=["Qd Spacing (nm)", "sample_yield", "Polymer"]).copy()
        sub["Qd Spacing (nm)"] = pd.to_numeric(sub["Qd Spacing (nm)"], errors="coerce")
        sub["sample_yield"] = pd.to_numeric(sub["sample_yield"], errors="coerce")
        sub = sub.dropna(subset=["Qd Spacing (nm)", "sample_yield"])
        if not sub.empty and len(sub["Polymer"].unique()) >= 2:
            try:
                g = sns.FacetGrid(sub, col="Polymer", col_wrap=3, height=4, sharex=False, sharey=True)
                g.map(plt.scatter, "Qd Spacing (nm)", "sample_yield", alpha=0.8)
                g.set_axis_labels("Qd Spacing (nm)", "Yield")
                g.fig.suptitle(f"Spacing vs Yield by Polymer{title_suffix}", y=1.02)
                g.tight_layout()
                path = os.path.join(output_dir, "sample_facet_spacing_yield_by_polymer.png")
                g.savefig(path, dpi=150, bbox_inches="tight")
                plt.close("all")
                created.append(path)
            except Exception as exc:
                log_fn(f"[YIELD PLOTS] Facet spacing/yield by polymer: {exc}")

    # Violin: Yield distribution by Polymer
    if _col_ok("Polymer", "sample_yield"):
        sub = df.dropna(subset=["Polymer", "sample_yield"]).copy()
        sub["sample_yield"] = pd.to_numeric(sub["sample_yield"], errors="coerce")
        if len(sub["Polymer"].unique()) >= 2:
            try:
                fig, ax = plt.subplots(figsize=(10, 6))
                sns.violinplot(data=sub, x="Polymer", y="sample_yield", ax=ax)
                ax.set_title(f"Yield distribution by Polymer{title_suffix}")
                ax.set_ylabel("Yield (fraction)")
                plt.xticks(rotation=30, ha="right")
                _save(fig, "sample_violin_yield_by_polymer.png")
            except Exception as exc:
                log_fn(f"[YIELD PLOTS] Violin: {exc}")

    # Box: Yield by Polymer
    if _col_ok("Polymer", "sample_yield"):
        sub = df.dropna(subset=["Polymer", "sample_yield"]).copy()
        sub["sample_yield"] = pd.to_numeric(sub["sample_yield"], errors="coerce")
        if len(sub["Polymer"].unique()) >= 2:
            try:
                fig, ax = plt.subplots(figsize=(10, 6))
                sns.boxplot(data=sub, x="Polymer", y="sample_yield", ax=ax)
                ax.set_title(f"Yield boxplot by Polymer{title_suffix}")
                ax.set_ylabel("Yield (fraction)")
                plt.xticks(rotation=30, ha="right")
                _save(fig, "sample_box_yield_by_polymer.png")
            except Exception as exc:
                log_fn(f"[YIELD PLOTS] Box: {exc}")

    # Correlation heatmap
    numeric_cols = ["sample_yield", "Np Concentration", "Qd Spacing (nm)", "Volume Fraction %"]
    avail = [c for c in numeric_cols if c in df.columns]
    if len(avail) >= 2:
        try:
            data_num = df[avail].apply(pd.to_numeric, errors="coerce").dropna(how="all")
            corr = data_num.corr()
            if not corr.empty and corr.shape[0] >= 2:
                fig, ax = plt.subplots(figsize=(max(6, len(avail) * 1.5), max(5, len(avail) * 1.2)))
                sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", vmin=-1, vmax=1, ax=ax)
                ax.set_title(f"Sample Correlation Heatmap{title_suffix}")
                _save(fig, "sample_correlation_heatmap.png")
        except Exception as exc:
            log_fn(f"[YIELD PLOTS] Heatmap: {exc}")

    return created


def _generate_sample_focused_plots(
    df: pd.DataFrame,
    output_dir: str,
    col_ok_fn: Callable[..., bool],
    save_fn: Callable[[plt.Figure, str], None],
    title_suffix: str,
    log_fn: Callable[[str], None],
) -> list[str]:
    """Generate whole-sample comparison plots for sample-focused mode."""
    created: list[str] = []

    # Rebind save helper to track created plots in this function
    def _save(fig: plt.Figure, name: str) -> None:
        save_fn(fig, name)
        created.append(name)

    # Yield vs concentration
    if col_ok_fn("Np Concentration", "sample_yield"):
        sub = df.dropna(subset=["Np Concentration", "sample_yield"]).copy()
        if not sub.empty:
            fig, ax = plt.subplots(figsize=(11, 7))
            ax.scatter(
                sub["Np Concentration"], sub["sample_yield"],
                alpha=0.85, s=85, edgecolors="k", linewidths=0.5
            )
            if "sample_name" in sub.columns:
                for _, row in sub.iterrows():
                    ax.annotate(
                        str(row["sample_name"]),
                        (row["Np Concentration"], row["sample_yield"]),
                        fontsize=7,
                        textcoords="offset points",
                        xytext=(4, 2),
                    )
            ax.set_xlabel("Np Concentration (mg/ml)")
            ax.set_ylabel("Yield (fraction)")
            ax.set_title(f"Sample-focused: Yield vs Concentration{title_suffix}")
            ax.set_ylim(-0.05, 1.05)
            ax.grid(True, alpha=0.3)
            _save(fig, "sample_focus_yield_vs_concentration.png")

    # Resistance summary (mean + median) vs concentration
    if col_ok_fn("Np Concentration") and (
        col_ok_fn("resistance_mean") or col_ok_fn("resistance_median")
    ):
        sub = df.dropna(subset=["Np Concentration"]).copy()
        if not sub.empty:
            fig, ax = plt.subplots(figsize=(11, 7))
            if "resistance_mean" in sub.columns and not sub["resistance_mean"].dropna().empty:
                ax.scatter(
                    sub["Np Concentration"], sub["resistance_mean"],
                    label="Mean Resistance", alpha=0.8, s=70
                )
            if "resistance_median" in sub.columns and not sub["resistance_median"].dropna().empty:
                ax.scatter(
                    sub["Np Concentration"], sub["resistance_median"],
                    label="Median Resistance", alpha=0.8, s=70, marker="s"
                )
            ax.set_xlabel("Np Concentration (mg/ml)")
            ax.set_ylabel("Resistance (Ohm)")
            ax.set_yscale("log")
            ax.set_title(f"Sample-focused: Resistance Summary vs Concentration{title_suffix}")
            ax.grid(True, alpha=0.3, which="both")
            ax.legend(loc="best")
            _save(fig, "sample_focus_resistance_vs_concentration.png")

    # Classification composition stacked bar
    class_cols = [
        ("pct_memristive", "Memristive", _TYPE_COLOURS.get("memristive", "#4CAF50")),
        ("pct_ohmic", "Ohmic", _TYPE_COLOURS.get("ohmic", "#2196F3")),
        ("pct_capacitive", "Capacitive", _TYPE_COLOURS.get("capacitive", "#FF9800")),
        ("pct_half_sweep", "Half-sweep", _TYPE_COLOURS.get("half-sweep", "#9C27B0")),
        ("pct_unknown", "Unknown", _TYPE_COLOURS.get("unknown", "#9E9E9E")),
        ("pct_other", "Other", "#607D8B"),
    ]
    present = [c for c, _, _ in class_cols if c in df.columns and not df[c].dropna().empty]
    if "sample_name" in df.columns and present:
        sub = df.dropna(subset=["sample_name"]).copy()
        if not sub.empty:
            x = np.arange(len(sub))
            bottom = np.zeros(len(sub), dtype=float)
            fig, ax = plt.subplots(figsize=(max(10, len(sub) * 0.35), 6))
            for col, label, colour in class_cols:
                if col not in sub.columns:
                    continue
                vals = pd.to_numeric(sub[col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
                if np.all(vals == 0):
                    continue
                ax.bar(x, vals, bottom=bottom, label=label, color=colour)
                bottom += vals
            ax.set_xticks(x)
            ax.set_xticklabels(sub["sample_name"], rotation=50, ha="right", fontsize=7)
            ax.set_ylabel("Classification Composition (%)")
            ax.set_ylim(0, 100)
            ax.set_title(f"Sample-focused: Classification Mix by Sample{title_suffix}")
            ax.legend(loc="upper right", fontsize=8)
            ax.grid(True, axis="y", alpha=0.25)
            plt.tight_layout()
            _save(fig, "sample_focus_classification_mix_stacked.png")

    # Expanded correlation heatmap
    if _HAS_SNS:
        numeric_cols = [
            "sample_yield",
            "Np Concentration",
            "Qd Spacing (nm)",
            "Volume Fraction %",
            "resistance_mean",
            "resistance_median",
            "resistance_std",
            "pct_memristive",
            "pct_ohmic",
            "pct_capacitive",
            "pct_half_sweep",
            "pct_unknown",
            "pct_other",
        ]
        avail = [c for c in numeric_cols if c in df.columns]
        if len(avail) >= 2:
            try:
                data_num = df[avail].apply(pd.to_numeric, errors="coerce").dropna(how="all")
                corr = data_num.corr()
                if not corr.empty and corr.shape[0] >= 2:
                    fig, ax = plt.subplots(figsize=(max(7, len(avail) * 0.7), max(6, len(avail) * 0.6)))
                    sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", vmin=-1, vmax=1, ax=ax)
                    ax.set_title(f"Sample-focused Correlation Heatmap{title_suffix}")
                    _save(fig, "sample_focus_correlation_heatmap.png")
            except Exception as exc:
                log_fn(f"[YIELD PLOTS] Sample-focused heatmap: {exc}")
    else:
        log_fn("[YIELD PLOTS] seaborn not available — skipping sample-focused heatmap")

    return [os.path.join(output_dir, name) for name in created]


def generate_device_level_plots(
    device_df: pd.DataFrame,
    output_dir: str,
    title_suffix: str = "",
    analysis_mode: str = "device",
    log_fn: Callable[[str], None] = print,
) -> list[str]:
    """Generate per-device plots. Each point = one pixel/device.

    Returns list of created PNG paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    created: list[str] = []

    def _save(fig: plt.Figure, name: str) -> None:
        path = os.path.join(output_dir, name)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        created.append(path)

    def _col_ok(*cols: str) -> bool:
        for c in cols:
            if c not in device_df.columns or device_df[c].dropna().empty:
                log_fn(f"[YIELD PLOTS] Skipping device plot: '{c}' missing or all-NaN")
                return False
        return True

    df = device_df.copy()
    sample_focused_mode = str(analysis_mode).lower().startswith("sample")

    # Device label column: use "sample_name/section/device_number" or device_id
    if "sample_name" in df.columns and "device_number" in df.columns:
        df["_label"] = df["sample_name"].astype(str) + "_" + df.get("section", pd.Series([""] * len(df))).astype(str) + df["device_number"].astype(str)
    elif "device_id" in df.columns:
        df["_label"] = df["device_id"]
    else:
        df["_label"] = df.index.astype(str)

    # Device yield vs device name
    if _col_ok("yield"):
        sub = df.dropna(subset=["yield"]).copy()
        if not sub.empty:
            fig, ax = plt.subplots(figsize=(max(10, len(sub) * 0.25), 5.5))
            jitter = np.random.default_rng(123).uniform(-0.03, 0.03, size=len(sub))
            ax.scatter(
                range(len(sub)),
                sub["yield"].astype(float) + jitter,
                alpha=0.65,
                edgecolors="k",
                linewidths=0.35,
                s=45,
            )
            ax.set_xticks(range(len(sub)))
            ax.set_xticklabels(sub["_label"], rotation=60, ha="right", fontsize=6)
            ax.set_ylabel("Yield (binary, jittered)")
            ax.set_title(f"Device Yield vs Device Name{title_suffix}")
            ax.set_yticks([0, 1])
            ax.set_yticklabels(["Non-memristive (0)", "Memristive (1)"])
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            _save(fig, "device_yield_vs_device_name.png")

    # In sample-focused mode, keep device-level output minimal and
    # return after producing the requested yield-vs-device view.
    if sample_focused_mode:
        return created

    # Resistance vs Device (all)
    if _col_ok("avg_resistance_first_sweep"):
        res_df = df.dropna(subset=["avg_resistance_first_sweep"]).copy()
        if not res_df.empty:
            fig, ax = plt.subplots(figsize=(max(10, len(res_df) * 0.25), 6))
            ax.scatter(range(len(res_df)), res_df["avg_resistance_first_sweep"], alpha=0.7, edgecolors="k", linewidths=0.5)
            ax.set_xticks(range(len(res_df)))
            ax.set_xticklabels(res_df["_label"], rotation=60, ha="right", fontsize=6)
            ax.set_ylabel("Average Resistance (Ω)")
            ax.set_title(f"First-Sweep Resistance per Device (0–0.1 V){title_suffix}")
            ax.set_yscale("log")
            ax.grid(True, alpha=0.3, which="both")
            plt.tight_layout()
            _save(fig, "device_resistance_all.png")

    # Resistance vs Device by classification type
    if _col_ok("avg_resistance_first_sweep") and "classification_type" in df.columns:
        res_df = df.dropna(subset=["avg_resistance_first_sweep"]).copy()
        if not res_df.empty:
            fig, ax = plt.subplots(figsize=(max(10, len(res_df) * 0.25), 6))
            for ctype, group in res_df.groupby("classification_type"):
                colour = _TYPE_COLOURS.get(str(ctype).lower(), "#9E9E9E")
                idx = [res_df.index.get_loc(i) for i in group.index]
                ax.scatter(idx, group["avg_resistance_first_sweep"],
                           label=str(ctype), alpha=0.75, color=colour, edgecolors="k", linewidths=0.4, s=60)
            ax.set_xticks(range(len(res_df)))
            ax.set_xticklabels(res_df["_label"], rotation=60, ha="right", fontsize=6)
            ax.set_ylabel("Average Resistance (Ω)")
            ax.set_title(f"First-Sweep Resistance per Device — by Type{title_suffix}")
            ax.set_yscale("log")
            ax.legend(title="Classification", loc="best", fontsize=8)
            ax.grid(True, alpha=0.3, which="both")
            plt.tight_layout()
            _save(fig, "device_resistance_by_type.png")

    # Resistance vs Concentration (all devices — multiple points per concentration)
    if _col_ok("Np Concentration", "avg_resistance_first_sweep"):
        res_df = df.dropna(subset=["Np Concentration", "avg_resistance_first_sweep"]).copy()
        if not res_df.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(res_df["Np Concentration"], res_df["avg_resistance_first_sweep"],
                       alpha=0.6, edgecolors="k", linewidths=0.4, s=50)
            ax.set_xlabel("Np Concentration (mg/ml)")
            ax.set_ylabel("Average Resistance (Ω)")
            ax.set_title(f"Resistance vs Concentration — all devices (0–0.1 V){title_suffix}")
            ax.set_yscale("log")
            ax.grid(True, alpha=0.3, which="both")
            _save(fig, "device_resistance_vs_concentration.png")

    # Resistance vs Concentration by classification type
    if _col_ok("Np Concentration", "avg_resistance_first_sweep") and "classification_type" in df.columns:
        res_df = df.dropna(subset=["Np Concentration", "avg_resistance_first_sweep"]).copy()
        if not res_df.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            for ctype, group in res_df.groupby("classification_type"):
                colour = _TYPE_COLOURS.get(str(ctype).lower(), "#9E9E9E")
                ax.scatter(group["Np Concentration"], group["avg_resistance_first_sweep"],
                           label=str(ctype), alpha=0.75, color=colour, edgecolors="k", linewidths=0.4, s=60)
            ax.set_xlabel("Np Concentration (mg/ml)")
            ax.set_ylabel("Average Resistance (Ω)")
            ax.set_title(f"Resistance vs Concentration — by Type{title_suffix}")
            ax.set_yscale("log")
            ax.legend(title="Classification", loc="best", fontsize=8)
            ax.grid(True, alpha=0.3, which="both")
            _save(fig, "device_resistance_vs_concentration_by_type.png")

    # Device-level yield vs concentration (binary — memristive=1 / other=0)
    if _col_ok("Np Concentration", "yield"):
        sub = df.dropna(subset=["Np Concentration", "yield"]).copy()
        if not sub.empty:
            fig, ax = plt.subplots(figsize=(10, 5))
            jitter = np.random.default_rng(42).uniform(-0.015, 0.015, size=len(sub))
            ax.scatter(sub["Np Concentration"], sub["yield"].astype(float) + jitter,
                       alpha=0.5, edgecolors="k", linewidths=0.3, s=40)
            ax.set_xlabel("Np Concentration (mg/ml)")
            ax.set_ylabel("Yield (binary, jittered)")
            ax.set_title(f"Device yield vs Concentration{title_suffix}")
            ax.set_yticks([0, 1])
            ax.set_yticklabels(["Non-memristive (0)", "Memristive (1)"])
            ax.grid(True, alpha=0.3)
            _save(fig, "device_yield_vs_concentration.png")

    if not _HAS_SNS:
        log_fn("[YIELD PLOTS] seaborn not available — skipping correlation heatmap")
        return created

    # Device-level correlation heatmap
    numeric_cols = ["yield", "Np Concentration", "Qd Spacing (nm)", "Volume Fraction %",
                    "avg_resistance_first_sweep"]
    avail = [c for c in numeric_cols if c in df.columns]
    if len(avail) >= 2:
        try:
            data_num = df[avail].apply(pd.to_numeric, errors="coerce").dropna(how="all")
            corr = data_num.corr()
            if not corr.empty and corr.shape[0] >= 2:
                fig, ax = plt.subplots(figsize=(max(6, len(avail) * 1.5), max(5, len(avail) * 1.2)))
                sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", vmin=-1, vmax=1, ax=ax)
                ax.set_title(f"Device-Level Correlation Heatmap{title_suffix}")
                _save(fig, "device_correlation_heatmap.png")
        except Exception as exc:
            log_fn(f"[YIELD PLOTS] Device heatmap: {exc}")

    return created


# Keep old name as alias for backwards compat
def generate_all_plots(df: pd.DataFrame, output_dir: str, sample_name: str = "",
                       log_fn: Callable[[str], None] = print) -> list[str]:
    return generate_device_level_plots(df, output_dir,
                                       title_suffix=f" — {sample_name}" if sample_name else "",
                                       log_fn=log_fn)
