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

from .conduction import _DEFAULT_LENGTH_M, _DEFAULT_AREA_M2, _compute_e_j, _split_forward_return


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
        length_m: Optional[float] = None,
        area_m2: Optional[float] = None,
    ):
        # Disable LaTeX to prevent parsing errors in background threads
        plt.rcParams['text.usetex'] = False
        plt.rcParams['mathtext.default'] = 'regular'
        plt.rcParams['axes.formatter.use_mathtext'] = False

        v = np.asarray(voltage, dtype=float)
        i = np.asarray(current, dtype=float)
        len_m = length_m if length_m is not None else _DEFAULT_LENGTH_M
        area = area_m2 if area_m2 is not None else _DEFAULT_AREA_M2
        e_arr, j_arr = _compute_e_j(v, i, len_m, area)

        # Stacked 2x1 so each panel gets full width and half the figure height
        fig, (ax_pos, ax_neg) = plt.subplots(2, 1, figsize=self.figsize)
        if title:
            fig.suptitle(title)

        for ax, positive in [(ax_pos, True), (ax_neg, False)]:
            ax.xaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
            ax.yaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
            ax.set_xlabel("|E| (V/m)")
            ax.set_ylabel("|J| (A/m^2)")
            ax.set_title("SCLC V>0" if positive else "SCLC V<0")
            ax.grid(True, which="both", alpha=0.3)
            self._plot_sclc_one_polarity(
                ax, v, i, e_arr, j_arr, positive=positive,
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
        e_arr: np.ndarray,
        j_arr: np.ndarray,
        positive: bool,
        device_label: str = "",
        ref_slope: float = 2.0,
        target_slopes: Tuple[float, ...] = (1.0, 2.0, 3.0),
        high_slope_min: Optional[float] = 4.0,
        min_points: int = 8,
    ):
        """Plot SCLC log J vs log E. Forward (0->x): full fits. Return (x->0): m=1 only."""
        if positive:
            mask = (v >= 0.1) & np.isfinite(v) & np.isfinite(i) & (j_arr > 0) & np.isfinite(e_arr)
        else:
            mask = (v <= -0.1) & np.isfinite(v) & np.isfinite(i) & (j_arr > 0) & np.isfinite(e_arr)
        idx_fwd, idx_ret = _split_forward_return(v, mask)
        e_fwd = e_arr[idx_fwd]
        j_fwd = j_arr[idx_fwd]
        e_ret = e_arr[idx_ret]
        j_ret = j_arr[idx_ret]

        if len(e_fwd) == 0 and len(e_ret) == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.loglog([1e2, 1e8], [1e-8, 1e-8], "w")
            return

        lbl = (device_label or "data")
        if len(e_fwd) > 0:
            order = np.argsort(e_fwd)
            e_fwd, j_fwd = e_fwd[order], j_fwd[order]
            ax.loglog(e_fwd, j_fwd, "ko", markersize=4, label=lbl + " fwd")
            if len(e_fwd) >= 2:
                slope, r2, e_fit, j_fit = self._fit_line(e_fwd, j_fwd)
                ax.loglog(e_fit, j_fit, "r-", label=f"global m={slope:.2f} R²={r2:.2f}")
            if len(e_fwd) >= min_points:
                log_e = np.log10(e_fwd)
                log_j = np.log10(j_fwd)
                mid = len(log_e) // 2
                colors = ["b", "g", "m", "c"]
                for half_name, (le, lj) in [
                    ("low", (log_e[:mid], log_j[:mid])),
                    ("high", (log_e[mid:], log_j[mid:])),
                ]:
                    if len(le) < min_points:
                        continue
                    for idx, target in enumerate(target_slopes):
                        best = self._best_window(le, lj, target, min_points=min_points)
                        if best is None:
                            continue
                        s_idx, e_idx, slope_t, r2_t = best
                        e_seg = e_fwd[:mid][s_idx:e_idx] if half_name == "low" else e_fwd[mid:][s_idx:e_idx]
                        j_seg = j_fwd[:mid][s_idx:e_idx] if half_name == "low" else j_fwd[mid:][s_idx:e_idx]
                        e_fit = np.logspace(np.log10(e_seg.min()), np.log10(e_seg.max()), 100)
                        j_fit = j_seg[0] * (e_fit / e_seg[0]) ** slope_t
                        ax.loglog(
                            e_fit, j_fit, f"{colors[idx % len(colors)]}-",
                            label=f"{half_name} ~m={target:g} m={slope_t:.2f} R²={r2_t:.2f}",
                            alpha=0.8,
                        )
                    if high_slope_min is not None:
                        hi = self._best_window(le, lj, target=None, min_points=min_points, min_slope=high_slope_min)
                        if hi is not None:
                            s_idx, e_idx, slope_h, r2_h = hi
                            e_seg = e_fwd[:mid][s_idx:e_idx] if half_name == "low" else e_fwd[mid:][s_idx:e_idx]
                            j_seg = j_fwd[:mid][s_idx:e_idx] if half_name == "low" else j_fwd[mid:][s_idx:e_idx]
                            e_fit = np.logspace(np.log10(e_seg.min()), np.log10(e_seg.max()), 100)
                            j_fit = j_seg[0] * (e_fit / e_seg[0]) ** slope_h
                            ax.loglog(e_fit, j_fit, "y-", label=f"{half_name} high m={slope_h:.2f} R²={r2_h:.2f}", alpha=0.8)
        if len(e_ret) > 0:
            order = np.argsort(e_ret)
            e_ret, j_ret = e_ret[order], j_ret[order]
            ax.loglog(e_ret, j_ret, "o", color="gray", markersize=2, alpha=0.6, label=lbl + " ret")
            if len(e_ret) >= min_points:
                best = self._best_window(np.log10(e_ret), np.log10(j_ret), target=1.0, min_points=min_points)
                if best is not None:
                    s_idx, e_idx, slope_t, r2_t = best
                    e_seg, j_seg = e_ret[s_idx:e_idx], j_ret[s_idx:e_idx]
                    e_fit = np.logspace(np.log10(e_seg.min()), np.log10(e_seg.max()), 100)
                    j_fit = j_seg[0] * (e_fit / e_seg[0]) ** slope_t
                    ax.loglog(e_fit, j_fit, "c-", alpha=0.7, label=f"ret m=1 m={slope_t:.2f} R²={r2_t:.2f}")

        if ref_slope is not None and (len(e_fwd) > 0 or len(e_ret) > 0):
            e_all = np.concatenate((e_fwd, e_ret)) if len(e_fwd) > 0 and len(e_ret) > 0 else (e_fwd if len(e_fwd) > 0 else e_ret)
            j_all = np.concatenate((j_fwd, j_ret)) if len(e_fwd) > 0 and len(e_ret) > 0 else (j_fwd if len(j_fwd) > 0 else j_ret)
            i0 = np.argmin(e_all)
            e_ref0, j_ref0 = e_all[i0], j_all[i0]
            e_ref = np.logspace(np.log10(e_ref0), np.log10(e_all.max()), 50)
            j_ref = j_ref0 * (e_ref / e_ref0) ** ref_slope
            ax.loglog(e_ref, j_ref, "k--", alpha=0.4, label=f"ref m={ref_slope:g}")

    @staticmethod
    def _fit_line(x: np.ndarray, y: np.ndarray):
        """Fit log10(y) vs log10(x); return slope, r2, x_fit, y_fit."""
        log_x = np.log10(x)
        log_y = np.log10(y)
        slope, intercept = np.polyfit(log_x, log_y, 1)
        y_fit = slope * log_x + intercept
        ss_res = np.sum((log_y - y_fit) ** 2)
        ss_tot = np.sum((log_y - np.mean(log_y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
        x_fit = np.logspace(np.log10(x.min()), np.log10(x.max()), 200)
        y_fit_arr = 10 ** (slope * np.log10(x_fit) + intercept)
        return slope, r2, x_fit, y_fit_arr

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

