"""
Optional V–I–time and current–time–iteration plots.

Not wired into the main dashboard flow; use when required via
UnifiedPlotter.plot_vi_time_3d(), plot_vi_stacked_slices(), or
plot_current_time_iteration_3d().
"""

from pathlib import Path
from typing import Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

matplotlib.rcParams["text.usetex"] = False
matplotlib.rcParams["mathtext.default"] = "regular"
matplotlib.rcParams["axes.formatter.use_mathtext"] = False
matplotlib.rcParams["axes.formatter.min_exponent"] = 0
matplotlib.rcParams["axes.unicode_minus"] = False

from ..core.base import PlotManager
from ..core.formatters import plain_linear_formatter
from ..core.style import get_figsize


def plot_vi_time_3d(
    voltage: Sequence[float],
    current: Sequence[float],
    time: Optional[Sequence[float]] = None,
    title: str = "V–I–time (3D)",
    device_label: str = "",
    figsize: Optional[Tuple[float, float]] = None,
    save_dir: Optional[Path] = None,
    save_name: Optional[str] = None,
):
    """
    Optional 3D plot: X=voltage, Y=current, Z=time (or index if time is None).

    Not called automatically. Use when you want to see the IV trajectory
    in (voltage, current, time/iteration) space.

    Returns:
        matplotlib Figure. If save_dir and save_name are set, also saves to file.
    """
    v, i = np.asarray(voltage, dtype=float), np.asarray(current, dtype=float)
    n = min(len(v), len(i))
    v, i = v[:n], i[:n]
    z = np.asarray(time, dtype=float)[:n] if time is not None and len(time) >= n else np.arange(n, dtype=float)
    if figsize is None:
        figsize = get_figsize("single")
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection="3d")
    ax.plot(v, i, z, "b-", linewidth=1.2, alpha=0.8)
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current (A)")
    ax.set_zlabel("Time (s)" if time is not None else "Index")
    if title or device_label:
        ax.set_title(f"{title} {device_label}".strip())
    if save_dir and save_name:
        manager = PlotManager(save_dir=Path(save_dir))
        manager.save(fig, save_name)
    return fig


def plot_vi_stacked_slices(
    voltage: Sequence[float],
    current: Sequence[float],
    time: Optional[Sequence[float]] = None,
    num_slices: int = 5,
    title: str = "V–I by time/iteration slice",
    device_label: str = "",
    figsize: Optional[Tuple[float, float]] = None,
    save_dir: Optional[Path] = None,
    save_name: Optional[str] = None,
):
    """
    Optional stacked 2D plot: one V–I subplot per time/iteration slice.

    Not called automatically. Slices are evenly spaced over the z range
    (time or index); each panel shows V vs I for points in that slice.

    Returns:
        matplotlib Figure. If save_dir and save_name are set, also saves to file.
    """
    v, i = np.asarray(voltage, dtype=float), np.asarray(current, dtype=float)
    n = min(len(v), len(i))
    v, i = v[:n], i[:n]
    z = np.asarray(time, dtype=float)[:n] if time is not None and len(time) >= n else np.arange(n, dtype=float)
    num_slices = max(1, min(num_slices, n))
    edges = np.linspace(z.min(), z.max(), num_slices + 1)
    slice_idx = np.digitize(z, edges[1:-1], right=False)
    slice_idx = np.clip(slice_idx, 0, num_slices - 1)
    if figsize is None:
        w, h = get_figsize("single")
        figsize = (w, max(h, 3 * num_slices))
    fig, axes = plt.subplots(num_slices, 1, figsize=figsize, sharex=True, sharey=True)
    if num_slices == 1:
        axes = [axes]
    for k, ax in enumerate(axes):
        mask = slice_idx == k
        if np.any(mask):
            ax.plot(v[mask], i[mask], "o-", markersize=2, linewidth=1)
        z_lo, z_hi = edges[k], edges[k + 1]
        z_label = "Time" if time is not None else "Index"
        ax.set_ylabel("Current (A)")
        ax.set_title(f"{z_label} [{z_lo:.2g}, {z_hi:.2g})")
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel("Voltage (V)")
    if title or device_label:
        fig.suptitle(f"{title} {device_label}".strip())
    for ax in axes:
        ax.xaxis.set_major_formatter(FuncFormatter(plain_linear_formatter))
        ax.yaxis.set_major_formatter(FuncFormatter(plain_linear_formatter))
    try:
        fig.tight_layout()
    except Exception:
        pass
    if save_dir and save_name:
        manager = PlotManager(save_dir=Path(save_dir))
        manager.save(fig, save_name)
    return fig


def plot_current_time_iteration_3d(
    current: Sequence[float],
    time: Optional[Sequence[float]] = None,
    iteration: Optional[Sequence[float]] = None,
    title: str = "Current vs time & iteration (3D)",
    device_label: str = "",
    figsize: Optional[Tuple[float, float]] = None,
    save_dir: Optional[Path] = None,
    save_name: Optional[str] = None,
):
    """
    Optional 3D plot: X=time, Y=iteration, Z=current.

    Not called automatically. Use when you want to see current as a function
    of time and iteration (e.g. sweep number or point index). If time or
    iteration is not provided, index is used for that axis.

    Returns:
        matplotlib Figure. If save_dir and save_name are set, also saves to file.
    """
    i = np.asarray(current, dtype=float)
    n = len(i)
    t = np.asarray(time, dtype=float)[:n] if time is not None and len(time) >= n else np.arange(n, dtype=float)
    it = np.asarray(iteration, dtype=float)[:n] if iteration is not None and len(iteration) >= n else np.arange(n, dtype=float)
    if figsize is None:
        figsize = get_figsize("single")
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection="3d")
    ax.plot(t, it, i, "b-", linewidth=1.2, alpha=0.8)
    ax.set_xlabel("Time (s)" if time is not None else "Index")
    ax.set_ylabel("Iteration" if iteration is not None else "Index")
    ax.set_zlabel("Current (A)")
    if title or device_label:
        ax.set_title(f"{title} {device_label}".strip())
    if save_dir and save_name:
        manager = PlotManager(save_dir=Path(save_dir))
        manager.save(fig, save_name)
    return fig
