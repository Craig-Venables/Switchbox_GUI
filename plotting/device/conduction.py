from pathlib import Path
from typing import Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter, ScalarFormatter

# Disable LaTeX/math text globally for this module
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.default'] = 'regular'
matplotlib.rcParams['axes.formatter.use_mathtext'] = False
matplotlib.rcParams['axes.formatter.min_exponent'] = 0
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['mathtext.fontset'] = 'dejavusans'  # Use non-math font

from ..core.base import PlotManager
from ..core.formatters import plain_log_formatter


class ConductionPlotter:
    """
    Create conduction mechanism panels (SCLC, Schottky, Poole–Frenkel) alongside standard IV.

    Grid layout (2x2):
    - (0, 0) Linear IV
    - (0, 1) Log-Log IV (SCLC style)
    - (1, 0) Schottky: ln(I) vs sqrt(V)
    - (1, 1) Poole–Frenkel: ln(I/V) vs sqrt(V)
    """

    def __init__(
        self,
        save_dir: Optional[Path] = None,
        figsize: Tuple[int, int] = (12, 9),
        target_slopes: Tuple[float, ...] = (1.0, 2.0, 3.0),
        high_slope_min: Optional[float] = 4.0,
        min_points: int = 8,
        enable_loglog_overlays: bool = True,
        enable_schottky_overlays: bool = True,
        enable_pf_overlays: bool = True,
        target_slopes_schottky: Tuple[float, ...] = (1.0,),
        target_slopes_pf: Tuple[float, ...] = (1.0,),
        schottky_slope_bounds: Optional[Tuple[float, float]] = None,
        pf_slope_bounds: Optional[Tuple[float, float]] = None,
    ):
        self.manager = PlotManager(save_dir=save_dir)
        self.figsize = figsize
        self.target_slopes = target_slopes
        self.high_slope_min = high_slope_min
        self.min_points = min_points
        self.enable_loglog_overlays = enable_loglog_overlays
        self.enable_schottky_overlays = enable_schottky_overlays
        self.enable_pf_overlays = enable_pf_overlays
        self.target_slopes_schottky = target_slopes_schottky
        self.target_slopes_pf = target_slopes_pf
        self.schottky_slope_bounds = schottky_slope_bounds
        self.pf_slope_bounds = pf_slope_bounds

    def plot_conduction_grid(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
        title: str = "",
        device_label: str = "",
        save_name: Optional[str] = None,
    ):
        # Disable LaTeX to prevent parsing errors in background threads
        plt.rcParams['text.usetex'] = False
        plt.rcParams['mathtext.default'] = 'regular'
        plt.rcParams['axes.formatter.use_mathtext'] = False
        
        v = np.asarray(voltage, dtype=float)
        i = np.asarray(current, dtype=float)

        fig, axes = plt.subplots(2, 2, figsize=self.figsize)
        # Explicitly disable math text parsing on all axes
        for ax in axes.flat:
            ax.xaxis.get_major_formatter().set_useMathText(False)
            ax.yaxis.get_major_formatter().set_useMathText(False)
        if title:
            fig.suptitle(title)

        # Linear IV
        ax_lin = axes[0, 0]
        ax_lin.plot(v, i, "o-", markersize=2, label=device_label or "IV")
        ax_lin.set_xlabel("Voltage (V)")
        ax_lin.set_ylabel("Current (A)")
        if device_label:
            ax_lin.legend()
        ax_lin.grid(True, alpha=0.3)

        # Log-Log (SCLC friendly) with optional slope windows
        ax_loglog = axes[0, 1]
        self._plot_loglog_with_windows(ax_loglog, v, i, device_label)
        ax_loglog.set_xlabel("|Voltage| (V)")
        ax_loglog.set_ylabel("|Current| (A)")
        # Force plain text formatters for log scales - use custom formatter to avoid math text parsing errors
        # Create formatters that explicitly disable math text
        x_formatter = FuncFormatter(plain_log_formatter)
        y_formatter = FuncFormatter(plain_log_formatter)
        ax_loglog.xaxis.set_major_formatter(x_formatter)
        ax_loglog.yaxis.set_major_formatter(y_formatter)
        # Ensure math text is disabled on these axes
        if hasattr(x_formatter, 'set_useMathText'):
            x_formatter.set_useMathText(False)
        if hasattr(y_formatter, 'set_useMathText'):
            y_formatter.set_useMathText(False)
        ax_loglog.grid(True, which="both", alpha=0.3)

        # Schottky: ln(I) vs sqrt(V)
        ax_schottky = axes[1, 0]
        pos_mask = v > 0
        if np.any(pos_mask):
            sqrt_v = np.sqrt(v[pos_mask])
            i_pos = np.abs(i[pos_mask])
            ax_schottky.semilogy(sqrt_v, i_pos, "ko", markersize=3)
            # Force plain text formatter for log scale - use custom formatter to avoid math text parsing errors
            y_formatter = FuncFormatter(plain_log_formatter)
            ax_schottky.yaxis.set_major_formatter(y_formatter)
            # Ensure math text is disabled
            if hasattr(y_formatter, 'set_useMathText'):
                y_formatter.set_useMathText(False)
            if self.enable_schottky_overlays:
                self._overlay_linear_windows(
                    ax_schottky,
                    sqrt_v,
                    np.log(i_pos),
                    targets=self.target_slopes_schottky,
                    label_prefix="Schottky",
                    slope_bounds=self.schottky_slope_bounds,
                )
        ax_schottky.set_xlabel("sqrt(V) (V^0.5)")
        ax_schottky.set_ylabel("|I| (A)")
        ax_schottky.set_title("Schottky plot")
        ax_schottky.grid(True, alpha=0.3)

        # Poole–Frenkel: ln(I/V) vs sqrt(V)
        ax_pf = axes[1, 1]
        if np.any(pos_mask):
            safe_v = v[pos_mask]
            safe_i = i[pos_mask]
            with np.errstate(divide="ignore", invalid="ignore"):
                pf_y = np.abs(safe_i / safe_v)
            sqrt_v = np.sqrt(safe_v)
            ax_pf.semilogy(sqrt_v, pf_y, "ko", markersize=3)
            # Force plain text formatter for log scale - use custom formatter to avoid math text parsing errors
            y_formatter = FuncFormatter(plain_log_formatter)
            ax_pf.yaxis.set_major_formatter(y_formatter)
            # Ensure math text is disabled
            if hasattr(y_formatter, 'set_useMathText'):
                y_formatter.set_useMathText(False)
            if self.enable_pf_overlays:
                self._overlay_linear_windows(
                    ax_pf,
                    sqrt_v,
                    np.log(pf_y),
                    targets=self.target_slopes_pf,
                    label_prefix="PF",
                    slope_bounds=self.pf_slope_bounds,
                )
        ax_pf.set_xlabel("sqrt(V) (V^0.5)")
        ax_pf.set_ylabel("|I/V| (A/V)")
        ax_pf.set_title("Poole-Frenkel plot")
        ax_pf.grid(True, alpha=0.3)

        # Before saving, ensure all axes have math text disabled
        for ax in axes.flat:
            for axis in [ax.xaxis, ax.yaxis]:
                formatter = axis.get_major_formatter()
                if hasattr(formatter, 'set_useMathText'):
                    formatter.set_useMathText(False)
                # Also disable on minor formatter
                minor_formatter = axis.get_minor_formatter()
                if hasattr(minor_formatter, 'set_useMathText'):
                    minor_formatter.set_useMathText(False)
        
        # Disable math text globally before tight_layout and save
        plt.rcParams['axes.formatter.use_mathtext'] = False
        plt.rcParams['text.usetex'] = False
        
        try:
            fig.tight_layout()
        except Exception as e:
            # If tight_layout fails due to math text, try without it
            print(f"[CONDUCTION PLOT] Warning: tight_layout failed, saving without it: {e}")
        
        if save_name:
            if self.manager.save_dir is None:
                raise ValueError("save_dir must be set to save figures")
            try:
                self.manager.save(fig, save_name)
            except (ValueError, Exception) as e:
                # If save fails due to math text parsing, try saving with explicit math text disabled
                if 'ParseException' in str(type(e)) or 'mathtext' in str(e).lower():
                    # Force disable math text one more time
                    for ax in axes.flat:
                        for axis in [ax.xaxis, ax.yaxis]:
                            formatter = axis.get_major_formatter()
                            if hasattr(formatter, 'set_useMathText'):
                                formatter.set_useMathText(False)
                    # Try saving again
                    self.manager.save(fig, save_name)
                else:
                    raise
        return fig, axes

    def _plot_loglog_with_windows(self, ax, v: np.ndarray, i: np.ndarray, device_label: str):
        v_abs = np.abs(v)
        i_abs = np.abs(i)
        # Filter: voltage >= 0.1V (user requirement: don't show data below 0.1V or -0.2V)
        mask = (v_abs >= 0.1) & (i_abs > 0) & np.isfinite(v_abs) & np.isfinite(i_abs)
        v_plot = v_abs[mask]
        i_plot = i_abs[mask]
        ax.loglog(v_plot, i_plot, "ko", markersize=3, label=device_label or "Log-Log IV")

        if self.enable_loglog_overlays and len(v_plot) >= self.min_points:
            log_v = np.log10(v_plot)
            log_i = np.log10(i_plot)
            colors = ["b", "g", "m", "c"]
            for idx, target in enumerate(self.target_slopes):
                best = self._best_window(log_v, log_i, target=target, min_points=self.min_points)
                if best:
                    s_idx, e_idx, slope_t, r2_t = best
                    v_seg = v_plot[s_idx:e_idx]
                    i_seg = i_plot[s_idx:e_idx]
                    v_fit = np.logspace(np.log10(v_seg.min()), np.log10(v_seg.max()), 100)
                    i_fit = i_seg[0] * (v_fit / v_seg[0]) ** slope_t
                    ax.loglog(
                        v_fit,
                        i_fit,
                        f"{colors[idx % len(colors)]}-",
                        alpha=0.8,
                        label=f"~m={target:g} fit m={slope_t:.2f}, R²={r2_t:.2f}",
                    )

            if self.high_slope_min is not None:
                hi = self._best_window(log_v, log_i, target=None, min_points=self.min_points, min_slope=self.high_slope_min)
                if hi:
                    s_idx, e_idx, slope_h, r2_h = hi
                    v_seg = v_plot[s_idx:e_idx]
                    i_seg = i_plot[s_idx:e_idx]
                    v_fit = np.logspace(np.log10(v_seg.min()), np.log10(v_seg.max()), 100)
                    i_fit = i_seg[0] * (v_fit / v_seg[0]) ** slope_h
                    ax.loglog(v_fit, i_fit, "y-", alpha=0.8, label=f"high m={slope_h:.2f}, R²={r2_h:.2f}")

        if device_label:
            ax.legend()

    @staticmethod
    def _overlay_linear_fit(ax, x: np.ndarray, y_log: np.ndarray, label: str):
        if len(x) < 2 or not np.all(np.isfinite(y_log)):
            return
        slope, intercept = np.polyfit(x, y_log, 1)
        y_fit = slope * x + intercept
        ax.semilogy(x, np.exp(y_fit), "-", label=f"{label} m={slope:.2f}")
        ax.legend()

    def _overlay_linear_windows(
        self,
        ax,
        x: np.ndarray,
        y_log: np.ndarray,
        targets: Tuple[float, ...],
        label_prefix: str,
        slope_bounds: Optional[Tuple[float, float]] = None,
    ):
        if len(x) < self.min_points or not np.all(np.isfinite(y_log)):
            return
        colors = ["b", "g", "m", "c"]
        # Targeted fits
        for idx, tgt in enumerate(targets):
            best = self._best_window_linear(x, y_log, target=tgt, min_points=self.min_points)
            if best is None:
                continue
            s_idx, e_idx, slope, r2 = best
            x_seg = x[s_idx:e_idx]
            y_seg = y_log[s_idx:e_idx]
            x_fit = np.linspace(x_seg.min(), x_seg.max(), 50)
            y_fit = slope * x_fit + (y_seg[0] - slope * x_seg[0])
            ax.semilogy(
                x_fit,
                np.exp(y_fit),
                f"{colors[idx % len(colors)]}-",
                alpha=0.8,
                label=f"{label_prefix} ~m={tgt:g} fit m={slope:.2f}, R²={r2:.2f}",
            )

        # Best-in-range fit (if requested and not already covered)
        if slope_bounds is not None:
            best = self._best_window_linear_range(x, y_log, slope_bounds, min_points=self.min_points)
            if best is not None:
                s_idx, e_idx, slope, r2 = best
                x_seg = x[s_idx:e_idx]
                y_seg = y_log[s_idx:e_idx]
                x_fit = np.linspace(x_seg.min(), x_seg.max(), 50)
                y_fit = slope * x_fit + (y_seg[0] - slope * x_seg[0])
                ax.semilogy(
                    x_fit,
                    np.exp(y_fit),
                    "y-",
                    alpha=0.8,
                    label=f"{label_prefix} best [{slope_bounds[0]}, {slope_bounds[1]}] m={slope:.2f}, R²={r2:.2f}",
                )

        ax.legend()

    @staticmethod
    def _best_window_linear(x: np.ndarray, y_log: np.ndarray, target: float, min_points: int = 8):
        n = len(x)
        best = None
        best_score = float("inf")
        for start in range(0, n - min_points + 1):
            for end in range(start + min_points, n + 1):
                xs = x[start:end]
                ys = y_log[start:end]
                slope, intercept = np.polyfit(xs, ys, 1)
                y_fit = slope * xs + intercept
                ss_res = np.sum((ys - y_fit) ** 2)
                ss_tot = np.sum((ys - np.mean(ys)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
                score = abs(slope - target) + max(0.0, 1 - r2)
                if score < best_score:
                    best_score = score
                    best = (start, end, slope, r2)
        return best

    @staticmethod
    def _best_window_linear_range(x: np.ndarray, y_log: np.ndarray, bounds: Tuple[float, float], min_points: int = 8):
        n = len(x)
        best = None
        best_score = -float("inf")  # maximize R² within bounds
        lo, hi = bounds
        mid = 0.5 * (lo + hi)
        for start in range(0, n - min_points + 1):
            for end in range(start + min_points, n + 1):
                xs = x[start:end]
                ys = y_log[start:end]
                slope, intercept = np.polyfit(xs, ys, 1)
                if slope < lo or slope > hi:
                    continue
                y_fit = slope * xs + intercept
                ss_res = np.sum((ys - y_fit) ** 2)
                ss_tot = np.sum((ys - np.mean(ys)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
                # prioritize R², then closeness to mid of range
                score = r2 - 0.05 * abs(slope - mid)
                if score > best_score:
                    best_score = score
                    best = (start, end, slope, r2)
        return best

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
                if min_slope is not None and slope < min_slope:
                    continue
                y_fit = slope * lv + intercept
                ss_res = np.sum((li - y_fit) ** 2)
                ss_tot = np.sum((li - np.mean(li)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
                if target is not None:
                    score = abs(slope - target) + max(0.0, 1 - r2)
                else:
                    score = max(0.0, 1 - r2)
                if score < best_score:
                    best_score = score
                    best = (start, end, slope, r2)
        return best

