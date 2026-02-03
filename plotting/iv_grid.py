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
        sample_name: str = "",
        section: str = "",
        device_num: str = "",
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
        # Build sweep title from sample info if available
        sweep_title_parts = [p for p in [sample_name, section, device_num] if p]
        sweep_title = " - ".join(sweep_title_parts) if sweep_title_parts else device_label
        self._plot_avg_with_arrows(ax_avg, v, i, arrows_points, device_label, sweep_title)

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
    def _plot_avg_with_arrows(ax, v: np.ndarray, i: np.ndarray, num_points: int, label: str, sweep_title: str = ""):
        """
        Plot a SINGLE complete sweep with direction arrows.
        
        Detects one complete sweep cycle from the data and plots it with arrows
        showing the sweep direction throughout the full cycle.
        
        A complete bipolar sweep goes: 0 → +V → 0 → -V → 0
        Each loop has 2 "returns to zero" - we detect these to find loop boundaries.
        """
        if len(v) < 2:
            # Not enough data
            ax.set_xlabel("Voltage (V)")
            ax.set_ylabel("Current (A)")
            ax.grid(True, alpha=0.3)
            return
        
        # Find voltage range to set zero tolerance
        v_range = np.max(np.abs(v))
        zero_tolerance = v_range * 0.05 if v_range > 0 else 0.01  # 5% of range or 10mV
        
        # Find all "zero regions" - where voltage returns to near 0
        # Group consecutive near-zero points into single zero regions
        zero_regions = []  # List of (start_idx, end_idx) for each zero region
        in_zero_region = False
        region_start = 0
        
        for idx in range(len(v)):
            is_near_zero = np.abs(v[idx]) < zero_tolerance
            
            if is_near_zero and not in_zero_region:
                # Starting a new zero region
                in_zero_region = True
                region_start = idx
            elif not is_near_zero and in_zero_region:
                # Ending a zero region
                in_zero_region = False
                zero_regions.append((region_start, idx - 1))
        
        # Don't forget the last region if we ended in one
        if in_zero_region:
            zero_regions.append((region_start, len(v) - 1))
        
        # Calculate number of complete loops
        # Each loop: 0 → +V → 0 → -V → 0 has 2 zero returns (plus start)
        # So for N loops, we have ~2N+1 zero regions (first zero, then 2 per loop)
        # Actually: start_zero, mid_zero, end_zero for 1 loop = 3 regions
        # For 2 loops: start, mid1, end1/start2, mid2, end2 = 5 regions (but end1=start2)
        # So: num_loops = (num_zero_regions - 1) / 2 if num_zero_regions >= 3
        
        if len(zero_regions) >= 3:
            # We have at least one complete loop
            # First loop ends at the 3rd zero region (index 2)
            # Use the END of the 3rd zero region as the sweep end
            sweep_end = zero_regions[2][1] + 1  # +1 to include the last point
            sweep_v = v[:sweep_end]
            sweep_i = i[:sweep_end]
        elif len(zero_regions) >= 2:
            # Partial sweep - use up to second zero region
            sweep_end = zero_regions[1][1] + 1
            sweep_v = v[:sweep_end]
            sweep_i = i[:sweep_end]
        else:
            # No clear zero structure - fall back to direction change detection
            direction_changes = []
            for idx in range(2, len(v)):
                prev_dir = v[idx - 1] - v[idx - 2]
                curr_dir = v[idx] - v[idx - 1]
                if prev_dir * curr_dir < 0 and abs(prev_dir) > 1e-10 and abs(curr_dir) > 1e-10:
                    direction_changes.append(idx)
            
            if len(direction_changes) >= 4:
                # 4 direction changes = 1 complete bipolar sweep
                sweep_end = direction_changes[3]
                sweep_v = v[:sweep_end]
                sweep_i = i[:sweep_end]
            elif len(direction_changes) >= 2:
                sweep_end = direction_changes[1]
                sweep_v = v[:sweep_end]
                sweep_i = i[:sweep_end]
            else:
                # No structure detected - use all data
                sweep_v = v
                sweep_i = i
        
        # Now plot this single sweep with arrows
        if num_points < 2:
            num_points = 12
        
        # Sample points evenly from the sweep for arrows
        n_points = min(num_points, len(sweep_v))
        indices = np.linspace(0, len(sweep_v) - 1, n_points, dtype=int)
        
        sampled_v = sweep_v[indices]
        sampled_i = sweep_i[indices]

        ax.scatter(sampled_v, sampled_i, c="b", marker="o", s=15, label=label or "Single sweep")
        for k in range(1, len(sampled_v)):
            ax.annotate(
                "",
                xy=(sampled_v[k], sampled_i[k]),
                xytext=(sampled_v[k - 1], sampled_i[k - 1]),
                arrowprops=dict(arrowstyle="->", color="red", lw=1.2),
            )
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("Current (A)")
        ax.grid(True, alpha=0.3)
        if label:
            ax.legend()

