"""
Plot impedance data from SMaRT CSV exports.

Produces:
- |Z| vs frequency (log-log)
- Phase (degrees) vs frequency (semilog)
- Capacitance vs frequency (log-log)
- Nyquist plot (Im(Z) vs Re(Z)) if phase/magnitude available
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from .smart_loader import load_smart_csv, load_impedance_folder
except ImportError:
    from smart_loader import load_smart_csv, load_impedance_folder

# Default column names in SMaRT CSV / .dat
FREQ = "Frequency (Hz)"
MAG = "Impedance Magnitude (Ohms)"
PHASE = "Impedance Phase Degrees (')"
CAP = "Capacitance Magnitude (F)"


def _col(df: pd.DataFrame, standard_name: str) -> Optional[str]:
    """Return the actual column name in df that matches standard_name (exact or strip)."""
    for c in df.columns:
        if str(c).strip() == standard_name:
            return c
    return None


def _has_cols(df: pd.DataFrame, *names: str) -> bool:
    """Return True if df has all of the given standard column names."""
    return all(_col(df, n) is not None for n in names)


def _ensure_axes(ax: Optional[plt.Axes] = None) -> plt.Axes:
    if ax is None:
        _, ax = plt.subplots()
    return ax


def plot_magnitude_vs_frequency(
    df: pd.DataFrame,
    ax: Optional[plt.Axes] = None,
    label: Optional[str] = None,
    freq_col: str = FREQ,
    mag_col: str = MAG,
) -> plt.Axes:
    """Plot impedance magnitude |Z| vs frequency (log-log)."""
    ax = _ensure_axes(ax)
    fc = _col(df, freq_col) or freq_col
    mc = _col(df, mag_col) or mag_col
    if fc not in df.columns or mc not in df.columns:
        raise KeyError(f"Need columns {freq_col!r} and {mag_col!r}. Got: {list(df.columns)}")
    out = df[[fc, mc]].dropna()
    f = out[fc].values
    z = np.abs(out[mc].values)
    ax.loglog(f, z, ".-", label=label or "data")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("|Z| (Ω)")
    ax.grid(True, which="both", alpha=0.3)
    return ax


def plot_phase_vs_frequency(
    df: pd.DataFrame,
    ax: Optional[plt.Axes] = None,
    label: Optional[str] = None,
    freq_col: str = FREQ,
    phase_col: str = PHASE,
) -> plt.Axes:
    """Plot impedance phase (degrees) vs frequency (semilog)."""
    ax = _ensure_axes(ax)
    fc = _col(df, freq_col) or freq_col
    pc = _col(df, phase_col) or phase_col
    if fc not in df.columns or pc not in df.columns:
        raise KeyError(f"Need columns {freq_col!r} and {phase_col!r}. Got: {list(df.columns)}")
    out = df[[fc, pc]].dropna()
    ax.semilogx(out[fc].values, out[pc].values, ".-", label=label or "data")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Phase (°)")
    ax.grid(True, which="both", alpha=0.3)
    return ax


def plot_capacitance_vs_frequency(
    df: pd.DataFrame,
    ax: Optional[plt.Axes] = None,
    label: Optional[str] = None,
    freq_col: str = FREQ,
    cap_col: str = CAP,
) -> plt.Axes:
    """Plot capacitance vs frequency (log-log)."""
    ax = _ensure_axes(ax)
    fc = _col(df, freq_col) or freq_col
    cc = _col(df, cap_col) or cap_col
    if fc not in df.columns or cc not in df.columns:
        raise KeyError(f"Need columns {freq_col!r} and {cap_col!r}. Got: {list(df.columns)}")
    out = df[[fc, cc]].dropna()
    c = np.abs(out[cc].values)
    c = np.where(c <= 0, np.nan, c)
    ax.loglog(out[fc].values, c, ".-", label=label or "data")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("|C| (F)")
    ax.grid(True, which="both", alpha=0.3)
    return ax


def plot_nyquist(
    df: pd.DataFrame,
    ax: Optional[plt.Axes] = None,
    label: Optional[str] = None,
    freq_col: str = FREQ,
    mag_col: str = MAG,
    phase_col: str = PHASE,
) -> plt.Axes:
    """Plot Nyquist: -Im(Z) vs Re(Z). Z = |Z| * exp(j*phase_rad)."""
    ax = _ensure_axes(ax)
    mc = _col(df, mag_col) or mag_col
    pc = _col(df, phase_col) or phase_col
    if mc not in df.columns or pc not in df.columns:
        raise KeyError(f"Need columns {mag_col!r} and {phase_col!r} for Nyquist. Got: {list(df.columns)}")
    out = df[[mc, pc]].dropna()
    mag = np.abs(out[mc].values)
    phase_deg = out[pc].values
    phase_rad = np.deg2rad(phase_deg)
    re_z = mag * np.cos(phase_rad)
    im_z = mag * np.sin(phase_rad)
    ax.plot(re_z, -im_z, ".-", label=label or "data")
    ax.set_xlabel("Re(Z) (Ω)")
    ax.set_ylabel("-Im(Z) (Ω)")
    # Equal scale (1:1) on x and y so circles look circular
    xlo, xhi = ax.get_xlim()
    ylo, yhi = ax.get_ylim()
    lo = min(xlo, ylo)
    hi = max(xhi, yhi)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    return ax


def plot_all(
    df: pd.DataFrame,
    title: str = "Impedance",
    label: Optional[str] = None,
    show: bool = True,
) -> plt.Figure:
    """Create figure: |Z| vs f, and if present phase, C, Nyquist. Skips panels when columns missing.
    Returns the figure; if show=True (default), calls plt.show()."""
    panels = []
    if _has_cols(df, FREQ, MAG):
        panels.append(("|Z| vs f", lambda ax: plot_magnitude_vs_frequency(df, ax=ax, label=label)))
    if _has_cols(df, FREQ, PHASE):
        panels.append(("Phase vs f", lambda ax: plot_phase_vs_frequency(df, ax=ax, label=label)))
    if _has_cols(df, FREQ, CAP):
        panels.append(("C vs f", lambda ax: plot_capacitance_vs_frequency(df, ax=ax, label=label)))
    if _has_cols(df, MAG, PHASE):
        panels.append(("Nyquist", lambda ax: plot_nyquist(df, ax=ax, label=label)))

    if not panels:
        raise KeyError(f"No plottable columns. Need at least ({FREQ}, {MAG}). Got: {list(df.columns)}")

    n = len(panels)
    ncols = 2 if n > 1 else 1
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows), squeeze=False)
    axes_flat = axes.flat
    for i, (subtitle, plot_fn) in enumerate(panels):
        plot_fn(axes_flat[i])
        axes_flat[i].set_title(subtitle)
    for j in range(len(panels), len(axes_flat)):
        axes_flat[j].set_visible(False)
    fig.suptitle(title)
    plt.tight_layout()
    if show:
        plt.show()
    return fig


def plot_folder_comparison(
    data: Dict[str, pd.DataFrame],
    plot_type: str = "magnitude",
    figsize: tuple = (7, 5),
) -> plt.Figure:
    """
    Overlay multiple datasets (e.g. on/off state, different bias) on one plot.
    Skips datasets that don't have the required columns for plot_type.

    plot_type : one of "magnitude", "phase", "capacitance", "nyquist"
    """
    required = {
        "magnitude": (FREQ, MAG),
        "phase": (FREQ, PHASE),
        "capacitance": (FREQ, CAP),
        "nyquist": (MAG, PHASE),
    }
    if plot_type not in required:
        raise ValueError(f"plot_type must be magnitude|phase|capacitance|nyquist, got {plot_type}")

    fig, ax = plt.subplots(figsize=figsize)
    n_plotted = 0
    for name, df in data.items():
        if df.empty or not _has_cols(df, *required[plot_type]):
            continue
        if plot_type == "magnitude":
            plot_magnitude_vs_frequency(df, ax=ax, label=name)
        elif plot_type == "phase":
            plot_phase_vs_frequency(df, ax=ax, label=name)
        elif plot_type == "capacitance":
            plot_capacitance_vs_frequency(df, ax=ax, label=name)
        else:
            plot_nyquist(df, ax=ax, label=name)
        n_plotted += 1
    if n_plotted == 0:
        ax.text(0.5, 0.5, f"No datasets with required columns for {plot_type}", ha="center", va="center", transform=ax.transAxes)
    ax.legend()
    plt.tight_layout()
    return fig


def main(
    folder: Optional[Union[str, Path]] = None,
    csv_path: Optional[Union[str, Path]] = None,
    compare: bool = True,
) -> None:
    """
    Example entry point.

    - If folder is set: load all CSVs from folder and plot comparison (magnitude overlay).
    - If csv_path is set: load single file and call plot_all().
    - If compare is True and folder given: show magnitude overlay; else show full 2x2 for first file.
    """
    if csv_path:
        path = Path(csv_path)
        df = load_smart_csv(path)
        plot_all(df, title=path.stem, label=path.stem)
        return

    if not folder:
        raise ValueError("Provide either folder= or csv_path=")

    folder = Path(folder)
    data = load_impedance_folder(folder)

    if compare and len(data) > 1:
        fig = plot_folder_comparison(data, plot_type="magnitude")
        fig.suptitle(f"Impedance magnitude — {folder.name}")
        plt.show()
        fig2 = plot_folder_comparison(data, plot_type="nyquist")
        fig2.suptitle(f"Nyquist — {folder.name}")
        plt.show()
    else:
        name = next(iter(data))
        plot_all(data[name], title=name, label=name)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Plot SMaRT impedance CSV data")
    p.add_argument("path", type=str, help="Folder containing .csv files, or single .csv file")
    p.add_argument("--no-compare", action="store_true", help="If folder: plot full 2x2 for first file only")
    args = p.parse_args()
    path = Path(args.path)
    if path.is_file():
        main(csv_path=path)
    else:
        main(folder=path, compare=not args.no_compare)
