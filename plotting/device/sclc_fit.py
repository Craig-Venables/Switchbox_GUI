from pathlib import Path
from typing import Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

# Disable LaTeX/math text globally for this module
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.default'] = 'regular'
matplotlib.rcParams['axes.formatter.use_mathtext'] = False
matplotlib.rcParams['axes.formatter.min_exponent'] = 0
matplotlib.rcParams['axes.unicode_minus'] = False

from ..core.base import PlotManager
from ..core.formatters import plain_log_formatter


class SCLCFitPlotter:
    """
    SCLC-style fit plot with separate positive and negative voltage panels.

    - Left panel: V > 0 branch with log10(I) vs log10(V) and slope fits.
    - Right panel: V < 0 branch with same analysis.
    - Each panel has its own global fit, windowed target-slope fits, and optional ref slope.
    """

    def __init__(self, save_dir: Optional[Path] = None, figsize: Tuple[int, int] = (10, 10)):
        self.manager = PlotManager(save_dir=save_dir)
        self.figsize = figsize

    def plot_sclc_fit(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        title: str = "",
        device_label: str = "",
        ref_slope: float = 2.0,
        target_slopes: Tuple[float, ...] = (1.0, 2.0, 3.0),
        high_slope_min: Optional[float] = 4.0,
        min_points: int = 8,
        save_name: Optional[str] = None,
    ):
        # Disable LaTeX to prevent parsing errors in background threads
        plt.rcParams['text.usetex'] = False
        plt.rcParams['mathtext.default'] = 'regular'
        plt.rcParams['axes.formatter.use_mathtext'] = False

        v = np.asarray(voltage, dtype=float)
        i = np.asarray(current, dtype=float)

        # Stacked 2x1 so each panel gets full width and half the figure height
        fig, (ax_pos, ax_neg) = plt.subplots(2, 1, figsize=self.figsize)
        if title:
            fig.suptitle(title)

        for ax, positive in [(ax_pos, True), (ax_neg, False)]:
            ax.xaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
            ax.yaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
            ax.set_xlabel("|V| (V)")
            ax.set_ylabel("|I| (A)")
            ax.set_title("SCLC V>0" if positive else "SCLC V<0")
            ax.grid(True, which="both", alpha=0.3)
            self._plot_sclc_one_polarity(
                ax, v, i, positive=positive,
                device_label=device_label,
                ref_slope=ref_slope,
                target_slopes=target_slopes,
                high_slope_min=high_slope_min,
                min_points=min_points,
            )
            ax.legend(loc="best", fontsize=7)

        try:
            fig.tight_layout()
        except Exception:
            pass
        if save_name:
            if self.manager.save_dir is None:
                raise ValueError("save_dir must be set to save figures")
            self.manager.save(fig, save_name)
        return fig, (ax_pos, ax_neg)

    def _plot_sclc_one_polarity(
        self,
        ax,
        v: np.ndarray,
        i: np.ndarray,
        positive: bool,
        device_label: str = "",
        ref_slope: float = 2.0,
        target_slopes: Tuple[float, ...] = (1.0, 2.0, 3.0),
        high_slope_min: Optional[float] = 4.0,
        min_points: int = 8,
    ):
        """Plot SCLC log-log and fits for one polarity (V>0 or V<0)."""
        if positive:
            mask = (v >= 0.1) & np.isfinite(v) & np.isfinite(i) & (np.abs(i) > 0)
        else:
            mask = (v <= -0.1) & np.isfinite(v) & np.isfinite(i) & (np.abs(i) > 0)
        v_b = np.abs(v[mask])
        i_b = np.abs(i[mask])

        if len(v_b) == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.loglog([1e-2, 1], [1e-12, 1e-12], "w")
            return

        ax.loglog(v_b, i_b, "ko", markersize=4, label=device_label or "data")

        if len(v_b) >= 2:
            slope, r2, v_fit, i_fit = self._fit_line(v_b, i_b)
            ax.loglog(v_fit, i_fit, "r-", label=f"global m={slope:.2f} R²={r2:.2f}")

        if len(v_b) >= min_points:
            log_v = np.log10(v_b)
            log_i = np.log10(i_b)
            colors = ["b", "g", "m", "c"]
            for idx, target in enumerate(target_slopes):
                best = self._best_window(log_v, log_i, target, min_points=min_points)
                if best is None:
                    continue
                s_idx, e_idx, slope_t, r2_t = best
                v_seg = v_b[s_idx:e_idx]
                i_seg = i_b[s_idx:e_idx]
                v_fit = np.logspace(np.log10(v_seg.min()), np.log10(v_seg.max()), 100)
                i_fit = i_seg[0] * (v_fit / v_seg[0]) ** slope_t
                ax.loglog(
                    v_fit,
                    i_fit,
                    f"{colors[idx % len(colors)]}-",
                    label=f"~m={target:g} m={slope_t:.2f} R²={r2_t:.2f}",
                    alpha=0.8,
                )
            if high_slope_min is not None:
                hi = self._best_window(log_v, log_i, target=None, min_points=min_points, min_slope=high_slope_min)
                if hi is not None:
                    s_idx, e_idx, slope_h, r2_h = hi
                    v_seg = v_b[s_idx:e_idx]
                    i_seg = i_b[s_idx:e_idx]
                    v_fit = np.logspace(np.log10(v_seg.min()), np.log10(v_seg.max()), 100)
                    i_fit = i_seg[0] * (v_fit / v_seg[0]) ** slope_h
                    ax.loglog(
                        v_fit,
                        i_fit,
                        "y-",
                        label=f"high m={slope_h:.2f} R²={r2_h:.2f}",
                        alpha=0.8,
                    )

        if ref_slope is not None and len(v_b) > 0:
            v_ref0 = v_b.min()
            i_ref0 = i_b[0]
            v_ref = np.logspace(np.log10(v_ref0), np.log10(v_b.max()), 50)
            i_ref = i_ref0 * (v_ref / v_ref0) ** ref_slope
            ax.loglog(v_ref, i_ref, "k--", alpha=0.4, label=f"ref m={ref_slope:g}")

    @staticmethod
    def _fit_line(v: np.ndarray, i: np.ndarray):
        log_v = np.log10(v)
        log_i = np.log10(i)
        slope, intercept = np.polyfit(log_v, log_i, 1)
        y_fit = slope * log_v + intercept
        ss_res = np.sum((log_i - y_fit) ** 2)
        ss_tot = np.sum((log_i - np.mean(log_i)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
        v_fit = np.logspace(np.log10(v.min()), np.log10(v.max()), 200)
        i_fit = 10 ** (slope * np.log10(v_fit) + intercept)
        return slope, r2, v_fit, i_fit

    @staticmethod
    def _best_window(
        log_v: np.ndarray,
        log_i: np.ndarray,
        target: Optional[float],
        min_points: int = 8,
        min_slope: Optional[float] = None,
    ):
        n = len(log_v)
        best = None
        best_score = float("inf")
        for start in range(0, n - min_points + 1):
            for end in range(start + min_points, n + 1):
                lv = log_v[start:end]
                li = log_i[start:end]
                slope, intercept = np.polyfit(lv, li, 1)
                y_fit = slope * lv + intercept
                ss_res = np.sum((li - y_fit) ** 2)
                ss_tot = np.sum((li - np.mean(li)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
                # Enforce minimum slope if requested
                if min_slope is not None and slope < min_slope:
                    continue

                if target is not None:
                    score = abs(slope - target) + max(0.0, 1 - r2)
                else:
                    score = max(0.0, 1 - r2)  # prioritize fit quality for high-slope search

                if score < best_score:
                    best_score = score
                    best = (start, end, slope, r2)
        return best

