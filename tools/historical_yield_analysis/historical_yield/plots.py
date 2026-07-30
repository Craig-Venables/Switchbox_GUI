"""Thesis-ready plots for historical yield analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .models import CATEGORY_DISPLAY


LogFn = Callable[[str], None]

# Stack order for composition plots (memristive first visually at bottom)
COMPOSITION_ORDER = [
    "memristive",
    "ohmic",
    "capacitive",
    "conductive",
    "non_conductive",
    "mem_capacitive",
    "intermittent",
    "other",
]

# Colour map used when shading points by sample number (early -> late devices).
AGE_CMAP = "viridis"

# Familiar discrete concentration ticks carried over from the legacy analysis.
LEGACY_CONCENTRATION_TICKS = [0.0, 0.001, 0.005, 0.01, 0.05, 0.07, 0.1, 0.2, 0.4, 1, 2, 4]


def concentration_ticks(values: Sequence[float], log_x: bool = False) -> List[float]:
    """Legacy concentration ticks trimmed to the range of ``values``."""
    present = [float(v) for v in values]
    if not present:
        return []
    lo, hi = min(present), max(present)
    ticks = [t for t in LEGACY_CONCENTRATION_TICKS if lo - 1e-12 <= t <= hi + 1e-12]
    return [t for t in ticks if t > 0] if log_x else ticks

COMPOSITION_COLORS = {
    "memristive": "#2ca02c",
    "ohmic": "#ff7f0e",
    "capacitive": "#1f77b4",
    "conductive": "#d62728",
    "non_conductive": "#7f7f7f",
    "mem_capacitive": "#9467bd",
    "intermittent": "#8c564b",
    "other": "#e377c2",
}


def _save_figure(fig: plt.Figure, output_dir: Path, stem: str, formats: Sequence[str]) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for fmt in formats:
        path = output_dir / f"{stem}.{fmt}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        paths.append(path)
    plt.close(fig)
    return paths


def plot_yield_timeline(
    sample_df: pd.DataFrame,
    output_dir: Path,
    *,
    formats: Sequence[str] = ("png", "svg", "pdf"),
    title: str = "Strict memristive yield vs sample ID",
    log_fn: LogFn = print,
) -> List[Path]:
    if sample_df.empty:
        log_fn("[plots] yield timeline skipped — empty sample dataframe")
        return []
    fig, ax = plt.subplots(figsize=(14, 6))
    x = sample_df["sample_number"].to_numpy()
    y = sample_df["strict_yield_pct"].to_numpy()
    ax.plot(x, y, marker="o", linestyle="-", color="#2ca02c", label="Strict yield (%)")
    ax.set_xlabel("Sample number (D#)")
    ax.set_ylabel("Strict memristive yield (%)")
    ax.set_title(title)
    ax.set_ylim(-2, 105)
    ax.grid(True, alpha=0.3)
    # sparse labels
    labels = sample_df["sample_id"].tolist()
    if len(labels) <= 40:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=90, fontsize=8)
    else:
        step = max(len(labels) // 30, 1)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(labels[::step], rotation=90, fontsize=8)
    fig.tight_layout()
    paths = _save_figure(fig, output_dir, "yield_vs_sample_id", formats)
    log_fn(f"[plots] wrote yield timeline ({len(paths)} files)")
    return paths


def plot_composition_timeline(
    sample_df: pd.DataFrame,
    output_dir: Path,
    *,
    formats: Sequence[str] = ("png", "svg", "pdf"),
    title: str = "Classification composition vs sample ID",
    log_fn: LogFn = print,
) -> List[Path]:
    if sample_df.empty:
        log_fn("[plots] composition timeline skipped — empty sample dataframe")
        return []
    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(len(sample_df))
    bottoms = np.zeros(len(sample_df))
    for cat in COMPOSITION_ORDER:
        col = f"pct_{cat}"
        if col not in sample_df.columns:
            continue
        vals = sample_df[col].fillna(0).to_numpy()
        if np.allclose(vals, 0):
            continue
        ax.bar(
            x,
            vals,
            bottom=bottoms,
            width=0.9,
            color=COMPOSITION_COLORS.get(cat, "#333333"),
            label=CATEGORY_DISPLAY.get(cat, cat),
        )
        bottoms = bottoms + vals
    ax.set_ylabel("Share of classified devices (%)")
    ax.set_xlabel("Sample ID")
    ax.set_title(title)
    ax.set_ylim(0, 105)
    labels = sample_df["sample_id"].tolist()
    if len(labels) <= 40:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=90, fontsize=8)
    else:
        step = max(len(labels) // 30, 1)
        ax.set_xticks(x[::step])
        ax.set_xticklabels([labels[i] for i in range(0, len(labels), step)], rotation=90, fontsize=8)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=8)
    fig.tight_layout()
    paths = _save_figure(fig, output_dir, "composition_vs_sample_id", formats)
    log_fn(f"[plots] wrote composition timeline ({len(paths)} files)")
    return paths


def plot_concentration_yield(
    sample_df: pd.DataFrame,
    output_dir: Path,
    *,
    formats: Sequence[str] = ("png", "svg", "pdf"),
    label_points: bool = True,
    log_x: bool = False,
    color_by_age: bool = False,
    title: str = "Concentration vs strict memristive yield",
    log_fn: LogFn = print,
) -> List[Path]:
    if sample_df.empty:
        log_fn("[plots] concentration-yield skipped — empty sample dataframe")
        return []
    df = sample_df.dropna(subset=["concentration_mgml"]).copy()
    if df.empty:
        log_fn("[plots] concentration-yield skipped — no concentration values")
        return []
    dropped = 0
    if log_x:
        positive = df["concentration_mgml"].astype(float) > 0
        dropped = int((~positive).sum())
        df = df[positive]
        if df.empty:
            log_fn("[plots] concentration-yield (log) skipped — no positive concentrations")
            return []
    fig, ax = plt.subplots(figsize=(12, 7))
    if color_by_age and "sample_number" in df.columns:
        scatter = ax.scatter(
            df["concentration_mgml"],
            df["strict_yield_pct"],
            c=df["sample_number"],
            cmap=AGE_CMAP,
            s=80,
            edgecolors="k",
            linewidths=0.4,
            alpha=0.9,
        )
        fig.colorbar(scatter, ax=ax).set_label("Sample number (early → late)")
    else:
        ax.scatter(
            df["concentration_mgml"],
            df["strict_yield_pct"],
            s=80,
            c="#1f77b4",
            edgecolors="k",
            linewidths=0.4,
            alpha=0.85,
        )
    if label_points:
        for _, row in df.iterrows():
            ax.annotate(
                str(row["sample_id"]),
                (row["concentration_mgml"], row["strict_yield_pct"]),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=7,
            )
    ticks = concentration_ticks(df["concentration_mgml"].tolist(), log_x=log_x)
    if log_x:
        ax.set_xscale("log")
        if ticks:
            ax.set_xticks(ticks)
            # Rotate: neighbouring decades such as 0.05 / 0.07 sit very close together.
            ax.set_xticklabels([f"{t:g}" for t in ticks], rotation=45, ha="right", fontsize=8)
        ax.set_xlabel("Np concentration (mg/ml, log scale)")
    else:
        if ticks:
            ax.set_xticks(ticks)
        ax.set_xlabel("Np concentration (mg/ml); Stock = 0")
    ax.set_ylabel("Strict memristive yield (%)")
    ax.set_title(f"{title}  (Stock/0 hidden: {dropped})" if dropped else title)
    ax.set_ylim(-2, 105)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    stem = "concentration_vs_yield_logx" if log_x else "concentration_vs_yield"
    paths = _save_figure(fig, output_dir, stem, formats)
    log_fn(f"[plots] wrote {stem} ({len(paths)} files)")
    return paths


def plot_concentration_yield_by_polymer(
    sample_df: pd.DataFrame,
    output_dir: Path,
    *,
    formats: Sequence[str] = ("png", "svg", "pdf"),
    title: str = "Concentration vs yield by polymer",
    log_fn: LogFn = print,
) -> List[Path]:
    if sample_df.empty:
        return []
    df = sample_df.dropna(subset=["concentration_mgml"]).copy()
    if df.empty or "polymer" not in df.columns:
        return []
    polymers = [p for p in sorted(df["polymer"].dropna().unique())]
    if not polymers:
        # single axes fallback
        return plot_concentration_yield(
            sample_df, output_dir, formats=formats, title=title, log_fn=log_fn
        )

    n = len(polymers)
    ncols = min(3, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows), squeeze=False)
    for i, polymer in enumerate(polymers):
        r, c = divmod(i, ncols)
        ax = axes[r][c]
        sub = df[df["polymer"] == polymer]
        ax.scatter(sub["concentration_mgml"], sub["strict_yield_pct"], s=60, alpha=0.85)
        for _, row in sub.iterrows():
            ax.annotate(
                str(row["sample_id"]),
                (row["concentration_mgml"], row["strict_yield_pct"]),
                textcoords="offset points",
                xytext=(3, 3),
                fontsize=6,
            )
        ax.set_title(str(polymer))
        ax.set_xlabel("Concentration (mg/ml)")
        ax.set_ylabel("Yield (%)")
        ax.set_ylim(-2, 105)
        ax.grid(True, alpha=0.3)
    # hide unused axes
    for j in range(n, nrows * ncols):
        r, c = divmod(j, ncols)
        axes[r][c].axis("off")
    fig.suptitle(title)
    fig.tight_layout()
    paths = _save_figure(fig, output_dir, "concentration_vs_yield_by_polymer", formats)
    log_fn(f"[plots] wrote polymer-faceted concentration plot ({len(paths)} files)")
    return paths


def generate_all_plots(
    sample_df: pd.DataFrame,
    output_dir: Path,
    *,
    formats: Sequence[str] = ("png", "svg", "pdf"),
    log_fn: LogFn = print,
) -> List[Path]:
    paths: List[Path] = []
    paths.extend(plot_yield_timeline(sample_df, output_dir, formats=formats, log_fn=log_fn))
    paths.extend(plot_composition_timeline(sample_df, output_dir, formats=formats, log_fn=log_fn))
    paths.extend(
        plot_concentration_yield(
            sample_df, output_dir, formats=formats, color_by_age=True, log_fn=log_fn
        )
    )
    paths.extend(
        plot_concentration_yield(
            sample_df,
            output_dir,
            formats=formats,
            log_x=True,
            color_by_age=True,
            log_fn=log_fn,
        )
    )
    paths.extend(
        plot_concentration_yield_by_polymer(sample_df, output_dir, formats=formats, log_fn=log_fn)
    )
    return paths
