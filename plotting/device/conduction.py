from pathlib import Path
from typing import Optional, Sequence, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
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


# Nominal defaults for J-E conversion when length/area not provided
_DEFAULT_LENGTH_M = 100e-9   # 100 nm
_DEFAULT_AREA_M2 = 100e-12   # 100 um^2


def _compute_e_j(
    v: np.ndarray,
    i: np.ndarray,
    length_m: float,
    area_m2: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute electric field E (V/m) and current density J (A/m^2) from V, I."""
    v_abs = np.abs(v)
    i_abs = np.abs(i)
    with np.errstate(divide="ignore", invalid="ignore"):
        e = np.where(v_abs > 0, v_abs / length_m, np.nan)
        j = np.where(i_abs > 0, i_abs / area_m2, np.nan)
    return e, j


def _split_forward_return(v: np.ndarray, mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Split masked indices into forward (0->x or 0->-x) and return (x->0 or -x->0) legs.
    Returns (indices_forward, indices_return) for indexing into original arrays.
    """
    indices = np.where(mask)[0]
    if len(indices) == 0:
        return np.array([], dtype=int), np.array([], dtype=int)
    v_masked = np.abs(v[indices])
    imax = np.argmax(v_masked)
    return indices[: imax + 1], indices[imax + 1 :]


class ConductionPlotter:
    """
    Create conduction mechanism panels (SCLC, Schottky, Poole-Frenkel, Fowler-Nordheim) alongside standard IV.

    Grid layout: 5 rows x 2 cols; each panel has full cell space and fittings.
    - Row 0: Linear IV (left) | Log IV (right)
    - Row 1: Log-Log (SCLC) V>0 | V<0  [J vs E]
    - Row 2: Schottky V>0 | V<0  [ln J vs sqrt E]
    - Row 3: Poole-Frenkel V>0 | V<0  [ln(J/E) vs sqrt E]
    - Row 4: Fowler-Nordheim V>0 | V<0  [ln(J/E^2) vs 1/E]
    """

    def __init__(
        self,
        save_dir: Optional[Path] = None,
        figsize: Tuple[int, int] = (14, 20),
        target_slopes: Tuple[float, ...] = (1.0, 2.0, 3.0),
        high_slope_min: Optional[float] = 4.0,
        min_points: int = 8,
        enable_loglog_overlays: bool = True,
        enable_schottky_overlays: bool = True,
        enable_pf_overlays: bool = True,
        enable_fn_overlays: bool = True,
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
        self.enable_fn_overlays = enable_fn_overlays
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

        # 5 rows x 2 cols: row 0 = IV; rows 1–4 = conduction panels (SCLC, Schottky, PF, FN)
        fig = plt.figure(figsize=self.figsize)
        gs = GridSpec(5, 2, figure=fig)

        # Row 0: Linear IV (left) | Log IV (right)
        ax_lin = fig.add_subplot(gs[0, 0])
        ax_lin.plot(v, i, "o-", markersize=2, label=device_label or "IV")
        ax_lin.set_xlabel("Voltage (V)")
        ax_lin.set_ylabel("Current (A)")
        if device_label:
            ax_lin.legend()
        ax_lin.grid(True, alpha=0.3)

        ax_log = fig.add_subplot(gs[0, 1])
        ax_log.plot(v, np.abs(i), "o-", markersize=2, label=device_label or "IV |log|")
        ax_log.set_yscale("log")
        ax_log.set_xlabel("Voltage (V)")
        ax_log.set_ylabel("|Current| (A)")
        ax_log.yaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
        if device_label:
            ax_log.legend()
        ax_log.grid(True, which="both", alpha=0.3)

        # Row 1: Log-Log (SCLC) V>0 | V<0 — J vs E
        ax_logpos = fig.add_subplot(gs[1, 0])
        ax_logneg = fig.add_subplot(gs[1, 1])
        self._plot_loglog_one_polarity(
            ax_logpos, v, i, e_arr, j_arr, positive=True, device_label=device_label
        )
        self._plot_loglog_one_polarity(
            ax_logneg, v, i, e_arr, j_arr, positive=False, device_label=device_label
        )
        ax_logpos.set_title("Log-Log (SCLC) V>0")
        ax_logneg.set_title("Log-Log (SCLC) V<0")
        for ax in (ax_logpos, ax_logneg):
            ax.set_xlabel("|E| (V/m)")
            ax.set_ylabel("|J| (A/m^2)")
            ax.xaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
            ax.yaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
            ax.grid(True, which="both", alpha=0.3)

        # Row 2: Schottky V>0 | V<0 — ln J vs sqrt E
        ax_schpos = fig.add_subplot(gs[2, 0])
        ax_schneg = fig.add_subplot(gs[2, 1])
        self._plot_schottky_one_polarity(ax_schpos, v, i, e_arr, j_arr, positive=True)
        self._plot_schottky_one_polarity(ax_schneg, v, i, e_arr, j_arr, positive=False)
        ax_schpos.set_title("Schottky V>0")
        ax_schneg.set_title("Schottky V<0")
        for ax in (ax_schpos, ax_schneg):
            ax.set_xlabel("sqrt(E) ((V/m)^0.5)")
            ax.set_ylabel("J (A/m^2)")
            ax.yaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
            ax.grid(True, alpha=0.3)

        # Row 3: Poole-Frenkel V>0 | V<0 — ln(J/E) vs sqrt E
        ax_pfpos = fig.add_subplot(gs[3, 0])
        ax_pfneg = fig.add_subplot(gs[3, 1])
        self._plot_pf_one_polarity(ax_pfpos, v, i, e_arr, j_arr, positive=True)
        self._plot_pf_one_polarity(ax_pfneg, v, i, e_arr, j_arr, positive=False)
        ax_pfpos.set_title("Poole-Frenkel V>0")
        ax_pfneg.set_title("Poole-Frenkel V<0")
        for ax in (ax_pfpos, ax_pfneg):
            ax.set_xlabel("sqrt(E) ((V/m)^0.5)")
            ax.set_ylabel("J/E (A/(V*m))")
            ax.yaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
            ax.grid(True, alpha=0.3)

        # Row 4: Fowler-Nordheim V>0 | V<0 — ln(J/E^2) vs 1/E
        ax_fnpos = fig.add_subplot(gs[4, 0])
        ax_fnneg = fig.add_subplot(gs[4, 1])
        self._plot_fn_one_polarity(ax_fnpos, v, i, e_arr, j_arr, positive=True)
        self._plot_fn_one_polarity(ax_fnneg, v, i, e_arr, j_arr, positive=False)
        ax_fnpos.set_title("Fowler-Nordheim V>0")
        ax_fnneg.set_title("Fowler-Nordheim V<0")
        for ax in (ax_fnpos, ax_fnneg):
            ax.set_xlabel("1/E (m/V)")
            ax.set_ylabel("ln(J/E^2)")
            ax.grid(True, alpha=0.3)

        if title:
            fig.suptitle(title)

        # Collect all axes for formatter cleanup and return (flat array for backward compatibility)
        axes = np.array([
            ax_lin, ax_log, ax_logpos, ax_logneg,
            ax_schpos, ax_schneg, ax_pfpos, ax_pfneg,
            ax_fnpos, ax_fnneg,
        ])

        for ax in axes.flat:
            for axis in [ax.xaxis, ax.yaxis]:
                formatter = axis.get_major_formatter()
                if hasattr(formatter, 'set_useMathText'):
                    formatter.set_useMathText(False)
                minor_formatter = axis.get_minor_formatter()
                if hasattr(minor_formatter, 'set_useMathText'):
                    minor_formatter.set_useMathText(False)

        plt.rcParams['axes.formatter.use_mathtext'] = False
        plt.rcParams['text.usetex'] = False
        try:
            fig.tight_layout()
        except Exception:
            print("[CONDUCTION PLOT] Warning: tight_layout failed, continuing without it.")

        if save_name:
            if self.manager.save_dir is None:
                raise ValueError("save_dir must be set to save figures")
            try:
                self.manager.save(fig, save_name)
            except (ValueError, Exception) as e:
                if 'ParseException' in str(type(e)) or 'mathtext' in str(e).lower():
                    for ax in axes.flat:
                        for axis in [ax.xaxis, ax.yaxis]:
                            formatter = axis.get_major_formatter()
                            if hasattr(formatter, 'set_useMathText'):
                                formatter.set_useMathText(False)
                    self.manager.save(fig, save_name)
                else:
                    raise
        return fig, axes

    def _plot_loglog_one_polarity(
        self,
        ax,
        v: np.ndarray,
        i: np.ndarray,
        e_arr: np.ndarray,
        j_arr: np.ndarray,
        positive: bool,
        device_label: str = "",
    ):
        """Plot log-log (SCLC) for one polarity. Forward (0->x): full fits. Return (x->0): m=1 only."""
        if positive:
            mask = (v >= 0.1) & (np.abs(i) > 0) & np.isfinite(v) & np.isfinite(i) & np.isfinite(e_arr) & (j_arr > 0)
        else:
            mask = (v <= -0.1) & (np.abs(i) > 0) & np.isfinite(v) & np.isfinite(i) & np.isfinite(e_arr) & (j_arr > 0)
        idx_fwd, idx_ret = _split_forward_return(v, mask)
        e_fwd = e_arr[idx_fwd]
        j_fwd = j_arr[idx_fwd]
        e_ret = e_arr[idx_ret]
        j_ret = j_arr[idx_ret]
        if len(e_fwd) == 0 and len(e_ret) == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.loglog([1e2, 1e8], [1e-8, 1e-8], "w")
            return
        lbl = (device_label or "Log-Log") + (" V>0" if positive else " V<0")
        if len(e_fwd) > 0:
            order = np.argsort(e_fwd)
            e_fwd, j_fwd = e_fwd[order], j_fwd[order]
            ax.loglog(e_fwd, j_fwd, "ko", markersize=3, label=lbl + " fwd")
            if self.enable_loglog_overlays and len(e_fwd) >= self.min_points:
                log_e = np.log10(e_fwd)
                log_j = np.log10(j_fwd)
                mid = len(log_e) // 2
                colors = ["b", "g", "m", "c"]
                for half_name, (le, lj) in [
                    ("low", (log_e[:mid], log_j[:mid])),
                    ("high", (log_e[mid:], log_j[mid:])),
                ]:
                    if len(le) < self.min_points:
                        continue
                    for idx, target in enumerate(self.target_slopes):
                        best = self._best_window(le, lj, target=target, min_points=self.min_points)
                        if best:
                            s_idx, e_idx, slope_t, r2_t = best
                            e_seg = e_fwd[:mid][s_idx:e_idx] if half_name == "low" else e_fwd[mid:][s_idx:e_idx]
                            j_seg = j_fwd[:mid][s_idx:e_idx] if half_name == "low" else j_fwd[mid:][s_idx:e_idx]
                            e_fit = np.logspace(np.log10(e_seg.min()), np.log10(e_seg.max()), 100)
                            j_fit = j_seg[0] * (e_fit / e_seg[0]) ** slope_t
                            ax.loglog(
                                e_fit, j_fit, f"{colors[idx % len(colors)]}-",
                                alpha=0.8, label=f"{half_name} ~m={target:g} m={slope_t:.2f} R²={r2_t:.2f}",
                            )
                    if self.high_slope_min is not None:
                        hi = self._best_window(le, lj, target=None, min_points=self.min_points, min_slope=self.high_slope_min)
                        if hi:
                            s_idx, e_idx, slope_h, r2_h = hi
                            e_seg = e_fwd[:mid][s_idx:e_idx] if half_name == "low" else e_fwd[mid:][s_idx:e_idx]
                            j_seg = j_fwd[:mid][s_idx:e_idx] if half_name == "low" else j_fwd[mid:][s_idx:e_idx]
                            e_fit = np.logspace(np.log10(e_seg.min()), np.log10(e_seg.max()), 100)
                            j_fit = j_seg[0] * (e_fit / e_seg[0]) ** slope_h
                            ax.loglog(e_fit, j_fit, "y-", alpha=0.8, label=f"{half_name} high m={slope_h:.2f} R²={r2_h:.2f}")
        if len(e_ret) > 0:
            order = np.argsort(e_ret)
            e_ret, j_ret = e_ret[order], j_ret[order]
            ax.loglog(e_ret, j_ret, "o", color="gray", markersize=2, alpha=0.6, label=lbl + " ret")
            if self.enable_loglog_overlays and len(e_ret) >= self.min_points:
                best = self._best_window(np.log10(e_ret), np.log10(j_ret), target=1.0, min_points=self.min_points)
                if best:
                    s_idx, e_idx, slope_t, r2_t = best
                    e_seg, j_seg = e_ret[s_idx:e_idx], j_ret[s_idx:e_idx]
                    e_fit = np.logspace(np.log10(e_seg.min()), np.log10(e_seg.max()), 100)
                    j_fit = j_seg[0] * (e_fit / e_seg[0]) ** slope_t
                    ax.loglog(e_fit, j_fit, "c-", alpha=0.7, label=f"ret m=1 m={slope_t:.2f} R²={r2_t:.2f}")
        ax.legend(loc="best", fontsize=7)

    def _plot_schottky_one_polarity(
        self, ax, v: np.ndarray, i: np.ndarray, e_arr: np.ndarray, j_arr: np.ndarray, positive: bool
    ):
        """Plot Schottky ln(J) vs sqrt(E). Forward: full fits. Return: m=1 only."""
        if positive:
            mask = (v > 0) & (j_arr > 0) & np.isfinite(e_arr)
        else:
            mask = (v < 0) & (j_arr > 0) & np.isfinite(e_arr)
        if not np.any(mask):
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            return
        idx_fwd, idx_ret = _split_forward_return(v, mask)
        for seg_name, idx in [("fwd", idx_fwd), ("ret", idx_ret)]:
            if len(idx) == 0:
                continue
            sqrt_e = np.sqrt(e_arr[idx])
            j_b = j_arr[idx]
            order = np.argsort(sqrt_e)
            sqrt_e = sqrt_e[order]
            j_b = j_b[order]
            kwargs = {"markersize": 3 if seg_name == "fwd" else 2, "alpha": 0.6 if seg_name == "ret" else 1.0,
                      "label": "Sch fwd" if seg_name == "fwd" else "Sch ret"}
            if seg_name == "ret":
                kwargs["color"] = "gray"
            ax.semilogy(sqrt_e, j_b, "ko" if seg_name == "fwd" else "o", **kwargs)
            if self.enable_schottky_overlays and len(sqrt_e) >= self.min_points:
                with np.errstate(divide="ignore", invalid="ignore"):
                    log_j = np.log(np.maximum(j_b, 1e-300))
                if seg_name == "fwd":
                    self._overlay_linear_windows_split(
                        ax, sqrt_e, log_j, targets=self.target_slopes_schottky, label_prefix="Sch",
                        slope_bounds=self.schottky_slope_bounds,
                    )
                else:
                    self._overlay_linear_m1_only(ax, sqrt_e, log_j, label_prefix="Sch ret")
        ax.legend(loc="best", fontsize=7)

    def _plot_pf_one_polarity(
        self, ax, v: np.ndarray, i: np.ndarray, e_arr: np.ndarray, j_arr: np.ndarray, positive: bool
    ):
        """Plot Poole-Frenkel ln(J/E) vs sqrt(E). Forward: full fits. Return: m=1 only."""
        if positive:
            mask = (v > 0) & (e_arr > 0) & (j_arr > 0) & np.isfinite(e_arr)
        else:
            mask = (v < 0) & (e_arr > 0) & (j_arr > 0) & np.isfinite(e_arr)
        if not np.any(mask):
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            return
        idx_fwd, idx_ret = _split_forward_return(v, mask)
        for seg_name, idx in [("fwd", idx_fwd), ("ret", idx_ret)]:
            if len(idx) == 0:
                continue
            e_b = e_arr[idx]
            j_b = j_arr[idx]
            with np.errstate(divide="ignore", invalid="ignore"):
                pf_y = j_b / e_b
            sqrt_e = np.sqrt(e_b)
            order = np.argsort(sqrt_e)
            sqrt_e, pf_y = sqrt_e[order], pf_y[order]
            kwargs = {"markersize": 3 if seg_name == "fwd" else 2, "alpha": 0.6 if seg_name == "ret" else 1.0,
                      "label": "PF fwd" if seg_name == "fwd" else "PF ret"}
            if seg_name == "ret":
                kwargs["color"] = "gray"
            ax.semilogy(sqrt_e, pf_y, "ko" if seg_name == "fwd" else "o", **kwargs)
            if self.enable_pf_overlays and len(sqrt_e) >= self.min_points:
                with np.errstate(divide="ignore", invalid="ignore"):
                    log_pf_y = np.log(np.maximum(pf_y, 1e-300))
                if seg_name == "fwd":
                    self._overlay_linear_windows_split(
                        ax, sqrt_e, log_pf_y, targets=self.target_slopes_pf, label_prefix="PF",
                        slope_bounds=self.pf_slope_bounds,
                    )
                else:
                    self._overlay_linear_m1_only(ax, sqrt_e, log_pf_y, label_prefix="PF ret")
        ax.legend(loc="best", fontsize=7)

    def _plot_fn_one_polarity(
        self, ax, v: np.ndarray, i: np.ndarray, e_arr: np.ndarray, j_arr: np.ndarray, positive: bool
    ):
        """Plot Fowler-Nordheim ln(J/E^2) vs 1/E. Forward: full fits. Return: single fit."""
        if positive:
            mask = (v > 0) & (e_arr > 0) & (j_arr > 0) & np.isfinite(e_arr)
        else:
            mask = (v < 0) & (e_arr > 0) & (j_arr > 0) & np.isfinite(e_arr)
        if not np.any(mask):
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            return
        idx_fwd, idx_ret = _split_forward_return(v, mask)
        for seg_name, idx in [("fwd", idx_fwd), ("ret", idx_ret)]:
            if len(idx) == 0:
                continue
            e_b = e_arr[idx]
            j_b = j_arr[idx]
            with np.errstate(divide="ignore", invalid="ignore"):
                inv_e = 1.0 / e_b
                ln_j_e2 = np.log((j_b / (e_b ** 2)))
            order = np.argsort(inv_e)
            inv_e, ln_j_e2 = inv_e[order], ln_j_e2[order]
            kwargs = {"markersize": 3 if seg_name == "fwd" else 2, "alpha": 0.6 if seg_name == "ret" else 1.0,
                      "label": "FN fwd" if seg_name == "fwd" else "FN ret"}
            if seg_name == "ret":
                kwargs["color"] = "gray"
            ax.plot(inv_e, ln_j_e2, "ko" if seg_name == "fwd" else "o", **kwargs)
            if self.enable_fn_overlays and len(inv_e) >= self.min_points:
                if seg_name == "fwd":
                    self._overlay_fn_linear_split(ax, inv_e, ln_j_e2)
                else:
                    self._overlay_fn_linear_single(ax, inv_e, ln_j_e2, label="FN ret")
        ax.legend(loc="best", fontsize=7)

    def _overlay_linear_m1_only(self, ax, x: np.ndarray, y_log: np.ndarray, label_prefix: str = ""):
        """Single m=1 fit on whole segment (for return leg)."""
        if len(x) < self.min_points or not np.all(np.isfinite(y_log)):
            return
        best = self._best_window_linear(x, y_log, target=1.0, min_points=self.min_points)
        if best is None:
            return
        s_idx, e_idx, slope, r2 = best
        x_seg, y_seg = x[s_idx:e_idx], y_log[s_idx:e_idx]
        x_fit = np.linspace(x_seg.min(), x_seg.max(), 50)
        y_fit = slope * x_fit + (y_seg[0] - slope * x_seg[0])
        ax.semilogy(x_fit, np.exp(y_fit), "c-", alpha=0.7, label=f"{label_prefix} m=1 m={slope:.2f} R²={r2:.2f}")

    def _overlay_fn_linear_single(self, ax, x: np.ndarray, y: np.ndarray, label: str = "FN ret"):
        """Single linear fit for FN return leg."""
        if len(x) < self.min_points or not np.all(np.isfinite(y)):
            return
        slope, intercept = np.polyfit(x, y, 1)
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
        x_fit = np.linspace(x.min(), x.max(), 50)
        y_fit = slope * x_fit + intercept
        ax.plot(x_fit, y_fit, "c-", alpha=0.7, label=f"{label} m={slope:.2e} R²={r2:.2f}")

    @staticmethod
    def _overlay_linear_fit(ax, x: np.ndarray, y_log: np.ndarray, label: str):
        if len(x) < 2 or not np.all(np.isfinite(y_log)):
            return
        slope, intercept = np.polyfit(x, y_log, 1)
        y_fit = slope * x + intercept
        ax.semilogy(x, np.exp(y_fit), "-", label=f"{label} m={slope:.2f}")
        ax.legend()

    def _overlay_linear_windows_split(
        self,
        ax,
        x: np.ndarray,
        y_log: np.ndarray,
        targets: Tuple[float, ...],
        label_prefix: str,
        slope_bounds: Optional[Tuple[float, float]] = None,
    ):
        """Overlay linear fits on lower and upper halves of data separately."""
        if len(x) < self.min_points or not np.all(np.isfinite(y_log)):
            return
        mid = len(x) // 2
        colors = ["b", "g", "m", "c"]
        for half_name, (x_h, y_h) in [("low", (x[:mid], y_log[:mid])), ("high", (x[mid:], y_log[mid:]))]:
            if len(x_h) < self.min_points:
                continue
            for idx, tgt in enumerate(targets):
                best = self._best_window_linear(x_h, y_h, target=tgt, min_points=self.min_points)
                if best is None:
                    continue
                s_idx, e_idx, slope, r2 = best
                x_seg = x_h[s_idx:e_idx]
                y_seg = y_h[s_idx:e_idx]
                x_fit = np.linspace(x_seg.min(), x_seg.max(), 50)
                y_fit = slope * x_fit + (y_seg[0] - slope * x_seg[0])
                ax.semilogy(
                    x_fit,
                    np.exp(y_fit),
                    f"{colors[idx % len(colors)]}-",
                    alpha=0.8,
                    label=f"{label_prefix} {half_name} ~m={tgt:g} m={slope:.2f}, R²={r2:.2f}",
                )
            if slope_bounds is not None:
                best = self._best_window_linear_range(x_h, y_h, slope_bounds, min_points=self.min_points)
                if best is not None:
                    s_idx, e_idx, slope, r2 = best
                    x_seg = x_h[s_idx:e_idx]
                    y_seg = y_h[s_idx:e_idx]
                    x_fit = np.linspace(x_seg.min(), x_seg.max(), 50)
                    y_fit = slope * x_fit + (y_seg[0] - slope * x_seg[0])
                    ax.semilogy(
                        x_fit,
                        np.exp(y_fit),
                        "y-",
                        alpha=0.8,
                        label=f"{label_prefix} {half_name} best m={slope:.2f}, R²={r2:.2f}",
                    )
        ax.legend()

    def _overlay_fn_linear_split(self, ax, x: np.ndarray, y: np.ndarray):
        """Overlay best linear fit on lower and upper halves for Fowler-Nordheim (ln(J/E^2) vs 1/E)."""
        if len(x) < self.min_points or not np.all(np.isfinite(y)):
            return
        mid = len(x) // 2
        for half_name, (x_h, y_h) in [("low", (x[:mid], y[:mid])), ("high", (x[mid:], y[mid:]))]:
            if len(x_h) < self.min_points:
                continue
            best = self._best_window_linear_range(
                x_h, y_h, (-1e10, 1e10), min_points=self.min_points
            )
            if best is not None:
                s_idx, e_idx, slope, r2 = best
                x_seg, y_seg = x_h[s_idx:e_idx], y_h[s_idx:e_idx]
            else:
                slope, intercept = np.polyfit(x_h, y_h, 1)
                y_fit = slope * x_h + intercept
                ss_res = np.sum((y_h - y_fit) ** 2)
                ss_tot = np.sum((y_h - np.mean(y_h)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
                x_seg, y_seg = x_h, y_h
            x_fit = np.linspace(x_seg.min(), x_seg.max(), 50)
            y_fit = slope * x_fit + (y_seg[0] - slope * x_seg[0])
            ax.plot(
                x_fit,
                y_fit,
                "b-" if half_name == "low" else "g-",
                alpha=0.8,
                label=f"FN {half_name} m={slope:.2e}, R²={r2:.2f}",
            )

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

