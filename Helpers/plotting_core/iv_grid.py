from pathlib import Path
from typing import Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

# Disable LaTeX/math text globally for this module to prevent parsing errors
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.default'] = 'regular'
matplotlib.rcParams['axes.formatter.use_mathtext'] = False
matplotlib.rcParams['axes.formatter.min_exponent'] = 0
matplotlib.rcParams['axes.unicode_minus'] = False

from .base import PlotManager


def plain_log_formatter(x, pos):
    """
    Format log scale values as plain text without math symbols.
    Avoids matplotlib math text parsing errors.
    """
    if x <= 0:
        return '0'
    # Use scientific notation for very small/large numbers
    if x < 0.01 or x > 1000:
        return f'{x:.2e}'
    # For normal range, use decimal
    if x < 1:
        return f'{x:.3f}'
    return f'{x:.1f}'


class IVGridPlotter:
    """
    Create 2x2 IV dashboard plots.

    Layout:
    - (0, 0) Linear I-V
    - (0, 1) Log |I| vs V
    - (1, 0) Averaged I-V with direction arrows
    - (1, 1) Current vs time (or index if time unavailable)
    """

    def __init__(self, save_dir: Optional[Path] = None, figsize: Tuple[int, int] = (12, 9)):
        self.manager = PlotManager(save_dir=save_dir)
        self.figsize = figsize

    def plot_grid(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        time: Optional[Sequence[float]] = None,
        title: Optional[str] = None,
        device_label: str = "",
        arrows_points: int = 12,
        save_name: Optional[str] = None,
    ):
        v = np.asarray(voltage, dtype=float)
        i = np.asarray(current, dtype=float)
        t = np.asarray(time, dtype=float) if time is not None else None

        fig, axes = plt.subplots(2, 2, figsize=self.figsize)
        if title:
            fig.suptitle(title)

        ax_lin = axes[0, 0]
        self._plot_linear(ax_lin, v, i, device_label)

        ax_log = axes[0, 1]
        self._plot_log(ax_log, v, i, device_label)

        # Bottom-left: averaged IV with arrows
        ax_avg = axes[1, 0]
        self._plot_avg_with_arrows(ax_avg, v, i, arrows_points, device_label)

        # Bottom-right: current vs time/index
        ax_time = axes[1, 1]
        self._plot_current_time(ax_time, i, t, device_label)

        fig.tight_layout()
        if save_name:
            if self.manager.save_dir is None:
                raise ValueError("save_dir must be set to save figures")
            self.manager.save(fig, save_name)
        return fig, axes

    @staticmethod
    def _plot_linear(ax, v: np.ndarray, i: np.ndarray, label: str):
        ax.plot(v, i, "o-", markersize=2, label=label or "IV")
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("Current (A)")
        if label:
            ax.legend()
        ax.grid(True, alpha=0.3)

    @staticmethod
    def _plot_log(ax, v: np.ndarray, i: np.ndarray, label: str):
        # Disable LaTeX to prevent parsing errors
        plt.rcParams['text.usetex'] = False
        plt.rcParams['mathtext.default'] = 'regular'
        plt.rcParams['axes.formatter.use_mathtext'] = False
        
        ax.plot(v, np.abs(i), "o-", markersize=2, label=label or "IV |log|")
        ax.set_yscale("log")
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("|Current| (A)")
        # Force plain text formatters for log scale to avoid math text parsing errors
        ax.yaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
        if label:
            ax.legend()
        ax.grid(True, which="both", alpha=0.3)

    @staticmethod
    def _plot_current_time(ax, i: np.ndarray, t: Optional[np.ndarray], label: str):
        if t is not None and len(t) == len(i):
            ax.plot(t, i, "r-", label=label or "Current vs time", linewidth=1.2)
            ax.set_xlabel("Time (s)")
        else:
            ax.plot(np.arange(len(i)), i, "r-", label=label or "Current index", linewidth=1.2)
            ax.set_xlabel("Index")
        ax.set_ylabel("Current (A)")
        if label:
            ax.legend()
        ax.grid(True, alpha=0.3)

    @staticmethod
    def _plot_avg_with_arrows(ax, v: np.ndarray, i: np.ndarray, num_points: int, label: str):
        """
        Plot averaged IV with direction arrows for the FULL sweep.
        
        Processes entire voltage/current array, not just first half.
        Averages all data points and adds arrows showing sweep direction throughout.
        """
        if len(v) < 2:
            # Not enough data
            ax.set_xlabel("Voltage (V)")
            ax.set_ylabel("Current (A)")
            ax.grid(True, alpha=0.3)
            return
        
        # Process ENTIRE sweep (removed first-sweep detection)
        # Average all data points
        if num_points < 2:
            num_points = 2
        step = max(len(v) // num_points, 1)
        avg_v = [np.mean(v[j : j + step]) for j in range(0, len(v), step)]
        avg_i = [np.mean(i[j : j + step]) for j in range(0, len(i), step)]

        ax.scatter(avg_v, avg_i, c="b", marker="o", s=10, label=label or "Averaged (full sweep)")
        for k in range(1, len(avg_v)):
            ax.annotate(
                "",
                xy=(avg_v[k], avg_i[k]),
                xytext=(avg_v[k - 1], avg_i[k - 1]),
                arrowprops=dict(arrowstyle="->", color="red", lw=1),
            )
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("Current (A)")
        ax.grid(True, alpha=0.3)
        if label:
            ax.legend()

