from pathlib import Path
from typing import Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

from .base import PlotManager


class SCLCFitPlotter:
    """
    Simple SCLC-style fit plot on a separate figure.

    - Uses positive voltage branch only.
    - Fits log10(I) vs log10(V) to estimate slope (m) and R².
    - Optionally searches for the best-fitting windows near target slopes (e.g. 1, 2, 3).
    - Shows scatter, fitted line, and reference slope guides.
    """

    def __init__(self, save_dir: Optional[Path] = None, figsize: Tuple[int, int] = (7, 6)):
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
        v = np.asarray(voltage, dtype=float)
        i = np.asarray(current, dtype=float)

        mask = (v > 0) & np.isfinite(v) & np.isfinite(i) & (np.abs(i) > 0)
        v_pos = v[mask]
        i_pos = np.abs(i[mask])

        fig, ax = plt.subplots(figsize=self.figsize)
        if title:
            fig.suptitle(title)

        ax.loglog(v_pos, i_pos, "ko", markersize=4, label=device_label or "data")

        # Global fit on all positive points
        if len(v_pos) >= 2:
            slope, r2, v_fit, i_fit = self._fit_line(v_pos, i_pos)
            ax.loglog(v_fit, i_fit, "r-", label=f"global m={slope:.2f}, R²={r2:.2f}")
        else:
            ax.text(0.5, 0.5, "Insufficient positive-V points", ha="center", va="center", transform=ax.transAxes)

        # Windowed fits near target slopes (pick best window per target)
        if len(v_pos) >= min_points:
            log_v = np.log10(v_pos)
            log_i = np.log10(i_pos)
            colors = ["b", "g", "m", "c"]
            for idx, target in enumerate(target_slopes):
                best = self._best_window(log_v, log_i, target, min_points=min_points)
                if best is None:
                    continue
                s_idx, e_idx, slope_t, r2_t = best
                v_seg = v_pos[s_idx:e_idx]
                i_seg = i_pos[s_idx:e_idx]
                v_fit = np.logspace(np.log10(v_seg.min()), np.log10(v_seg.max()), 100)
                i_fit = i_seg[0] * (v_fit / v_seg[0]) ** slope_t
                ax.loglog(
                    v_fit,
                    i_fit,
                    f"{colors[idx % len(colors)]}-",
                    label=f"~m={target:g} fit m={slope_t:.2f}, R²={r2_t:.2f}",
                    alpha=0.8,
                )

            # Optional high-slope search (e.g., >4)
            if high_slope_min is not None:
                hi = self._best_window(log_v, log_i, target=None, min_points=min_points, min_slope=high_slope_min)
                if hi is not None:
                    s_idx, e_idx, slope_h, r2_h = hi
                    v_seg = v_pos[s_idx:e_idx]
                    i_seg = i_pos[s_idx:e_idx]
                    v_fit = np.logspace(np.log10(v_seg.min()), np.log10(v_seg.max()), 100)
                    i_fit = i_seg[0] * (v_fit / v_seg[0]) ** slope_h
                    ax.loglog(
                        v_fit,
                        i_fit,
                        "y-",
                        label=f"high-slope m={slope_h:.2f}, R²={r2_h:.2f}",
                        alpha=0.8,
                    )

        # Reference slope guide through first point
        if ref_slope is not None and len(v_pos) > 0:
            v_ref0 = v_pos.min()
            i_ref0 = i_pos[0]
            v_ref = np.logspace(np.log10(v_ref0), np.log10(v_pos.max()), 50)
            i_ref = i_ref0 * (v_ref / v_ref0) ** ref_slope
            ax.loglog(v_ref, i_ref, "k--", alpha=0.4, label=f"ref m={ref_slope:g}")

        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("|Current| (A)")
        ax.set_title("SCLC-style log-log fit")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend()

        fig.tight_layout()
        if save_name:
            if self.manager.save_dir is None:
                raise ValueError("save_dir must be set to save figures")
            self.manager.save(fig, save_name)
        return fig, ax

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

