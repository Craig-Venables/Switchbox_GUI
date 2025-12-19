from pathlib import Path
from typing import Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

from .base import PlotManager


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
        ax.plot(v, np.abs(i), "o-", markersize=2, label=label or "IV |log|")
        ax.set_yscale("log")
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("|Current| (A)")
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
        Plot averaged IV with direction arrows, using only the first sweep.
        
        Detects multiple sweeps by looking for voltage direction changes and
        extracts only the first sweep to avoid messy overlapping arrows.
        """
        # Extract first sweep only
        if len(v) < 2:
            # Not enough data
            ax.set_xlabel("Voltage (V)")
            ax.set_ylabel("Current (A)")
            ax.grid(True, alpha=0.3)
            return
        
        # Detect sweep boundaries by looking for voltage direction changes
        # A sweep typically goes: start -> max/min -> back to start
        # Look for the point where voltage starts going back (direction reversal)
        dv = np.diff(v)
        
        # Find the first significant direction reversal
        # This happens when the sign of dv changes significantly
        first_sweep_end = len(v)
        
        if len(dv) > 2:
            # Find where voltage direction changes (sweep reversal)
            # Look for point where voltage starts returning to starting point
            initial_direction = np.sign(dv[0]) if abs(dv[0]) > 1e-10 else 0
            
            if initial_direction != 0:
                # Find first point where direction changes significantly
                for idx in range(1, len(dv)):
                    current_direction = np.sign(dv[idx]) if abs(dv[idx]) > 1e-10 else 0
                    # If direction reversed and we're moving back toward the start
                    if current_direction != 0 and current_direction != initial_direction:
                        # Check if we're actually returning (voltage moving back toward start)
                        start_voltage = v[0]
                        current_voltage = v[idx]
                        # If we've passed the start point or are clearly reversing
                        if (initial_direction > 0 and current_voltage < start_voltage) or \
                           (initial_direction < 0 and current_voltage > start_voltage):
                            first_sweep_end = idx + 1
                            break
                    # Also check if we've reached a local extremum and started returning
                    elif idx > 5:  # Need some points to establish trend
                        # Check if we've hit a peak/valley and are returning
                        if initial_direction > 0:
                            # Positive sweep: look for maximum then decrease
                            if v[idx] < v[idx-1] and v[idx-1] > np.max(v[:idx-1]):
                                first_sweep_end = idx + 1
                                break
                        else:
                            # Negative sweep: look for minimum then increase
                            if v[idx] > v[idx-1] and v[idx-1] < np.min(v[:idx-1]):
                                first_sweep_end = idx + 1
                                break
        
        # Use only the first sweep
        v_first = v[:first_sweep_end]
        i_first = i[:first_sweep_end]
        
        if len(v_first) < 2:
            # Fallback: use all data if first sweep detection failed
            v_first = v
            i_first = i
        
        # Now average the first sweep data
        if num_points < 2:
            num_points = 2
        step = max(len(v_first) // num_points, 1)
        avg_v = [np.mean(v_first[j : j + step]) for j in range(0, len(v_first), step)]
        avg_i = [np.mean(i_first[j : j + step]) for j in range(0, len(i_first), step)]

        ax.scatter(avg_v, avg_i, c="b", marker="o", s=10, label=label or "Averaged (1st sweep)")
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

