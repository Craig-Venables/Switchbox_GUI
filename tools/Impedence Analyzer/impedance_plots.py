"""
Plot impedance data from SMaRT CSV exports.

Produces:
- |Z| vs frequency (log-log)
- Phase (degrees) vs frequency (semilog)
- Capacitance vs frequency (log-log)
- Nyquist plot (Im(Z) vs Re(Z)) if phase/magnitude available
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

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


def _plot_with_trusted_region(
    ax: plt.Axes,
    f: np.ndarray,
    y: np.ndarray,
    scale: str,
    label: str,
    max_trusted_freq: Optional[float],
) -> None:
    """Plot y vs f; if max_trusted_freq set, plot f > max_trusted_freq in grey."""
    if max_trusted_freq is not None and f.size > 0:
        trusted = f <= max_trusted_freq
        untrusted = ~trusted
        if np.any(trusted):
            plot_fn = getattr(ax, scale)
            plot_fn(f[trusted], y[trusted], ".-", label=label)
        if np.any(untrusted):
            plot_fn = getattr(ax, scale)
            plot_fn(f[untrusted], y[untrusted], ".-", color="#888888", alpha=0.5, zorder=0, label="_nolegend_")
            if not getattr(ax, "_caution_legend_added", False):
                ax.plot([], [], color="#888888", alpha=0.5, linewidth=2, label="f > 1 MHz (caution)")
                ax._caution_legend_added = True
    else:
        plot_fn = getattr(ax, scale)
        plot_fn(f, y, ".-", label=label)


def plot_magnitude_vs_frequency(
    df: pd.DataFrame,
    ax: Optional[plt.Axes] = None,
    label: Optional[str] = None,
    freq_col: str = FREQ,
    mag_col: str = MAG,
    max_trusted_freq: Optional[float] = None,
) -> plt.Axes:
    """Plot impedance magnitude |Z| vs frequency (log-log). Data above max_trusted_freq is greyed out."""
    ax = _ensure_axes(ax)
    fc = _col(df, freq_col) or freq_col
    mc = _col(df, mag_col) or mag_col
    if fc not in df.columns or mc not in df.columns:
        raise KeyError(f"Need columns {freq_col!r} and {mag_col!r}. Got: {list(df.columns)}")
    out = df[[fc, mc]].dropna()
    f = out[fc].values
    z = np.abs(out[mc].values)
    _plot_with_trusted_region(ax, f, z, "loglog", label or "data", max_trusted_freq)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("|Z| (Ω)")
    # Log-scale axes use LogFormatter; do not use ticklabel_format(style='scientific')
    ax.grid(True, which="both", alpha=0.3)
    return ax


def plot_phase_vs_frequency(
    df: pd.DataFrame,
    ax: Optional[plt.Axes] = None,
    label: Optional[str] = None,
    freq_col: str = FREQ,
    phase_col: str = PHASE,
    max_trusted_freq: Optional[float] = None,
) -> plt.Axes:
    """Plot impedance phase (degrees) vs frequency (semilog). Data above max_trusted_freq is greyed out."""
    ax = _ensure_axes(ax)
    fc = _col(df, freq_col) or freq_col
    pc = _col(df, phase_col) or phase_col
    if fc not in df.columns or pc not in df.columns:
        raise KeyError(f"Need columns {freq_col!r} and {phase_col!r}. Got: {list(df.columns)}")
    out = df[[fc, pc]].dropna()
    f = out[fc].values
    y = out[pc].values
    _plot_with_trusted_region(ax, f, y, "semilogx", label or "data", max_trusted_freq)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Phase (°)")
    ax.ticklabel_format(style='scientific', scilimits=(0, 0), useMathText=True, axis='y')
    ax.grid(True, which="both", alpha=0.3)
    return ax


def plot_capacitance_vs_frequency(
    df: pd.DataFrame,
    ax: Optional[plt.Axes] = None,
    label: Optional[str] = None,
    freq_col: str = FREQ,
    cap_col: str = CAP,
    max_trusted_freq: Optional[float] = None,
) -> plt.Axes:
    """Plot capacitance vs frequency (log-log). Data above max_trusted_freq is greyed out."""
    ax = _ensure_axes(ax)
    fc = _col(df, freq_col) or freq_col
    cc = _col(df, cap_col) or cap_col
    if fc not in df.columns or cc not in df.columns:
        raise KeyError(f"Need columns {freq_col!r} and {cap_col!r}. Got: {list(df.columns)}")
    out = df[[fc, cc]].dropna()
    f = out[fc].values
    c = np.abs(out[cc].values)
    c = np.where(c <= 0, np.nan, c)
    _plot_with_trusted_region(ax, f, c, "loglog", label or "data", max_trusted_freq)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("|C| (F)")
    # Log-scale axes use LogFormatter; do not use ticklabel_format(style='scientific')
    ax.grid(True, which="both", alpha=0.3)
    return ax


def extract_nyquist_parameters(
    df: pd.DataFrame,
    freq_col: str = FREQ,
    mag_col: str = MAG,
    phase_col: str = PHASE,
) -> Dict[str, float]:
    """
    Extract quantitative parameters from Nyquist plot data.
    
    Returns dict with:
    - series_resistance_ohms: High-frequency intercept (rightmost Re(Z) where -Im(Z) ≈ 0)
    - parallel_resistance_ohms: Low-frequency intercept (leftmost Re(Z) where -Im(Z) ≈ 0)
    - peak_frequency_hz: Frequency at maximum -Im(Z)
    - relaxation_time_s: τ = 1/(2π × f_peak)
    """
    fc = _col(df, freq_col) or freq_col
    mc = _col(df, mag_col) or mag_col
    pc = _col(df, phase_col) or phase_col
    if mc not in df.columns or pc not in df.columns:
        raise KeyError(f"Need columns {mag_col!r} and {phase_col!r} for Nyquist extraction.")
    
    cols = [mc, pc]
    if fc in df.columns:
        cols.append(fc)
    out = df[cols].dropna()
    
    mag = np.abs(out[mc].values)
    phase_deg = out[pc].values
    phase_rad = np.deg2rad(phase_deg)
    re_z = mag * np.cos(phase_rad)
    im_z = mag * np.sin(phase_rad)
    neg_im_z = -im_z
    
    if fc in out.columns:
        f = out[fc].values
        # Sort by frequency for intercept finding
        idx_sorted = np.argsort(f)
        f_sorted = f[idx_sorted]
        re_z_sorted = re_z[idx_sorted]
        neg_im_z_sorted = neg_im_z[idx_sorted]
    else:
        f_sorted = None
        re_z_sorted = re_z
        neg_im_z_sorted = neg_im_z
    
    # Threshold for "near zero" imaginary component (1% of max)
    im_threshold = np.abs(neg_im_z_sorted).max() * 0.01 if len(neg_im_z_sorted) > 0 else 0
    
    # High-frequency intercept (series resistance): rightmost point where -Im(Z) < threshold
    # Or use max Re(Z) from highest frequencies if no zero crossing
    if f_sorted is not None and len(f_sorted) > 0:
        # Look at highest 20% of frequencies
        high_f_idx = np.where(f_sorted >= np.percentile(f_sorted, 80))[0]
        if len(high_f_idx) > 0:
            near_zero_high = np.where(np.abs(neg_im_z_sorted[high_f_idx]) < im_threshold)[0]
            if len(near_zero_high) > 0:
                series_r = re_z_sorted[high_f_idx[near_zero_high[-1]]]
            else:
                series_r = np.max(re_z_sorted[high_f_idx])
        else:
            series_r = np.max(re_z_sorted)
    else:
        # No frequency data: use rightmost point where -Im(Z) is small
        near_zero = np.where(np.abs(neg_im_z_sorted) < im_threshold)[0]
        if len(near_zero) > 0:
            series_r = re_z_sorted[near_zero[-1]]
        else:
            series_r = np.max(re_z_sorted)
    
    # Low-frequency intercept (parallel resistance): leftmost point where -Im(Z) < threshold
    # Or use min Re(Z) from lowest frequencies if no zero crossing
    if f_sorted is not None and len(f_sorted) > 0:
        # Look at lowest 20% of frequencies
        low_f_idx = np.where(f_sorted <= np.percentile(f_sorted, 20))[0]
        if len(low_f_idx) > 0:
            near_zero_low = np.where(np.abs(neg_im_z_sorted[low_f_idx]) < im_threshold)[0]
            if len(near_zero_low) > 0:
                parallel_r = re_z_sorted[low_f_idx[near_zero_low[0]]]
            else:
                parallel_r = np.min(re_z_sorted[low_f_idx])
        else:
            parallel_r = np.min(re_z_sorted)
    else:
        # No frequency data: use leftmost point where -Im(Z) is small
        near_zero = np.where(np.abs(neg_im_z_sorted) < im_threshold)[0]
        if len(near_zero) > 0:
            parallel_r = re_z_sorted[near_zero[0]]
        else:
            parallel_r = np.min(re_z_sorted)
    
    # Peak frequency: frequency at maximum -Im(Z)
    peak_idx = np.argmax(neg_im_z)
    if f_sorted is not None and len(f) > 0:
        peak_freq = f[peak_idx]
    else:
        peak_freq = np.nan
    
    # Relaxation time: τ = 1/(2π × f_peak)
    if np.isfinite(peak_freq) and peak_freq > 0:
        relaxation_time = 1.0 / (2.0 * np.pi * peak_freq)
    else:
        relaxation_time = np.nan
    
    return {
        "series_resistance_ohms": float(series_r) if np.isfinite(series_r) else np.nan,
        "parallel_resistance_ohms": float(parallel_r) if np.isfinite(parallel_r) else np.nan,
        "peak_frequency_hz": float(peak_freq) if np.isfinite(peak_freq) else np.nan,
        "relaxation_time_s": float(relaxation_time) if np.isfinite(relaxation_time) else np.nan,
    }


def plot_nyquist(
    df: pd.DataFrame,
    ax: Optional[plt.Axes] = None,
    label: Optional[str] = None,
    freq_col: str = FREQ,
    mag_col: str = MAG,
    phase_col: str = PHASE,
    max_trusted_freq: Optional[float] = None,
    extract_params: bool = False,
) -> Union[plt.Axes, Tuple[plt.Axes, Dict[str, float]]]:
    """
    Plot Nyquist: -Im(Z) vs Re(Z). Z = |Z| * exp(j*phase_rad). Points above max_trusted_freq are greyed out.
    
    If extract_params=True, extracts quantitative parameters and annotates the plot.
    Returns (ax, params_dict) if extract_params=True, else returns ax.
    """
    ax = _ensure_axes(ax)
    fc = _col(df, freq_col) or freq_col
    mc = _col(df, mag_col) or mag_col
    pc = _col(df, phase_col) or phase_col
    if mc not in df.columns or pc not in df.columns:
        raise KeyError(f"Need columns {mag_col!r} and {phase_col!r} for Nyquist. Got: {list(df.columns)}")
    cols = [mc, pc]
    if fc in df.columns:
        cols.append(fc)
    out = df[cols].dropna()
    mag = np.abs(out[mc].values)
    phase_deg = out[pc].values
    phase_rad = np.deg2rad(phase_deg)
    re_z = mag * np.cos(phase_rad)
    im_z = mag * np.sin(phase_rad)
    if max_trusted_freq is not None and fc in out.columns and out[fc].size > 0:
        f = out[fc].values
        trusted = f <= max_trusted_freq
        untrusted = ~trusted
        if np.any(trusted):
            ax.plot(re_z[trusted], -im_z[trusted], ".-", label=label or "data")
        if np.any(untrusted):
            ax.plot(re_z[untrusted], -im_z[untrusted], ".-", color="#888888", alpha=0.5, zorder=0, label="_nolegend_")
            if not getattr(ax, "_caution_legend_added", False):
                ax.plot([], [], color="#888888", alpha=0.5, linewidth=2, label="f > 1 MHz (caution)")
                ax._caution_legend_added = True
    else:
        ax.plot(re_z, -im_z, ".-", label=label or "data")
    ax.set_xlabel("Re(Z) (Ω)")
    ax.set_ylabel("-Im(Z) (Ω)")
    ax.ticklabel_format(style='scientific', scilimits=(0, 0), useMathText=True, axis='both')
    # Equal scale (1:1) on x and y so circles look circular
    xlo, xhi = ax.get_xlim()
    ylo, yhi = ax.get_ylim()
    lo = min(xlo, ylo)
    hi = max(xhi, yhi)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    
    params = None
    if extract_params:
        try:
            params = extract_nyquist_parameters(df, freq_col, mag_col, phase_col)
            # Annotate plot with parameters
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            x_range = xlim[1] - xlim[0]
            y_range = ylim[1] - ylim[0]
            
            # Position text box in upper right, avoiding data
            text_x = xlim[0] + 0.65 * x_range
            text_y = ylim[0] + 0.85 * y_range
            
            lines = []
            if np.isfinite(params["series_resistance_ohms"]):
                lines.append(f"R_s = {params['series_resistance_ohms']:.2e} Ω")
            if np.isfinite(params["parallel_resistance_ohms"]):
                lines.append(f"R_p = {params['parallel_resistance_ohms']:.2e} Ω")
            if np.isfinite(params["peak_frequency_hz"]):
                lines.append(f"f_peak = {params['peak_frequency_hz']:.2e} Hz")
            if np.isfinite(params["relaxation_time_s"]):
                lines.append(f"τ = {params['relaxation_time_s']:.2e} s")
            
            if lines:
                textstr = "\n".join(lines)
                props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
                ax.text(text_x, text_y, textstr, transform=ax.transData, fontsize=9,
                       verticalalignment='top', bbox=props)
        except Exception as e:
            print(f"Warning: Failed to extract Nyquist parameters: {e}")
            params = {}
    
    if extract_params:
        return ax, params
    return ax


def plot_all(
    df: pd.DataFrame,
    title: str = "Impedance",
    label: Optional[str] = None,
    show: bool = True,
    max_trusted_freq: Optional[float] = None,
) -> plt.Figure:
    """Create figure: |Z| vs f, and if present phase, C, Nyquist. Skips panels when columns missing.
    Data above max_trusted_freq (Hz) is greyed out. Returns the figure; if show=True (default), calls plt.show()."""
    panels = []
    if _has_cols(df, FREQ, MAG):
        panels.append(("|Z| vs f", lambda ax: plot_magnitude_vs_frequency(df, ax=ax, label=label, max_trusted_freq=max_trusted_freq)))
    if _has_cols(df, FREQ, PHASE):
        panels.append(("Phase vs f", lambda ax: plot_phase_vs_frequency(df, ax=ax, label=label, max_trusted_freq=max_trusted_freq)))
    if _has_cols(df, FREQ, CAP):
        panels.append(("C vs f", lambda ax: plot_capacitance_vs_frequency(df, ax=ax, label=label, max_trusted_freq=max_trusted_freq)))
    if _has_cols(df, MAG, PHASE):
        panels.append(("Nyquist", lambda ax: plot_nyquist(df, ax=ax, label=label, max_trusted_freq=max_trusted_freq)))

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
    figsize: tuple = (11, 7),
    max_trusted_freq: Optional[float] = None,
) -> plt.Figure:
    """
    Overlay multiple datasets (e.g. on/off state, different bias) on one plot.
    Skips datasets that don't have the required columns for plot_type.
    Data above max_trusted_freq (Hz) is greyed out.
    For many series (>10), legend is placed outside with smaller font.

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
            plot_magnitude_vs_frequency(df, ax=ax, label=name, max_trusted_freq=max_trusted_freq)
        elif plot_type == "phase":
            plot_phase_vs_frequency(df, ax=ax, label=name, max_trusted_freq=max_trusted_freq)
        elif plot_type == "capacitance":
            plot_capacitance_vs_frequency(df, ax=ax, label=name, max_trusted_freq=max_trusted_freq)
        else:
            plot_nyquist(df, ax=ax, label=name, max_trusted_freq=max_trusted_freq)
        n_plotted += 1
    if n_plotted == 0:
        ax.text(0.5, 0.5, f"No datasets with required columns for {plot_type}", ha="center", va="center", transform=ax.transAxes)
    if n_plotted > 10:
        ax.legend(fontsize="small", bbox_to_anchor=(1.02, 1), loc="upper left", ncol=1)
        plt.tight_layout(rect=(0, 0, 0.85, 1))
    else:
        ax.legend(fontsize="small")
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
