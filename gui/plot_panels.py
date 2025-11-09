"""
Matplotlib plot panel helpers.
==============================

`MeasurementPlotPanels` centralises all matplotlib/Tkinter widget creation
that previously lived inside `Measurement_GUI.py`.  The class exposes the
same axes/figure attributes the legacy GUI relied on, so the main window can
delegate widget construction and gradually shrink to orchestration logic.

The module also provides small maintenance utilities (clear plots, remember
last sweep, reset state) that make it easier to add verification tests or
port the GUI to another toolkit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


PlotLine = Tuple[List[float], List[float]]


@dataclass
class MeasurementPlotPanels:
    """
    Build and manage all matplotlib plot panels embedded in the GUI.

    Attributes created here mirror the names used by the original monolithic
    GUI (`ax_rt_iv`, `canvas_all_logiv`, ...).  The method
    :meth:`attach_to` copies these attributes onto the caller so existing
    code continues to work while we complete the refactor.
    """

    font_config: Dict[str, int] = field(
        default_factory=lambda: {"axis": 7, "title": 9, "ticks": 6}
    )
    figures: Dict[str, Figure] = field(default_factory=dict)
    axes: Dict[str, object] = field(default_factory=dict)
    canvases: Dict[str, FigureCanvasTkAgg] = field(default_factory=dict)
    lines: Dict[str, object] = field(default_factory=dict)
    last_sweep: PlotLine = field(default_factory=lambda: ([], []))

    # ------------------------------------------------------------------
    # Public construction API
    # ------------------------------------------------------------------
    def create_all_plots(self, graph_frame: tk.Misc, temp_enabled: bool) -> None:
        """Create every matplotlib panel and embed it inside ``graph_frame``."""
        self.create_main_iv_plots(graph_frame)
        self.create_all_sweeps_plots(graph_frame)
        self.create_vi_logiv_plots(graph_frame)
        self.create_current_time_plot(graph_frame)
        self.create_temp_time_plot(graph_frame, temp_enabled=temp_enabled)
        self.create_endurance_retention_plots(graph_frame)

    # Individual panels -------------------------------------------------
    def create_main_iv_plots(self, parent: tk.Misc) -> None:
        frame = tk.LabelFrame(parent, text="Current Measurement", padx=4, pady=3)
        frame.grid(row=0, column=0, columnspan=2, padx=4, pady=3, sticky="nsew")

        fig_iv, ax_iv = self._make_figure(title="IV")
        self._style_axis(ax_iv, "Voltage (V)", "Current (A)")

        canvas_iv = FigureCanvasTkAgg(fig_iv, master=frame)
        canvas_iv.get_tk_widget().grid(row=0, column=0, columnspan=5, sticky="nsew")

        fig_log, ax_log = self._make_figure(title="Log IV")
        ax_log.set_yscale("log")
        self._style_axis(ax_log, "Voltage (V)", "|Current| (A)")

        canvas_log = FigureCanvasTkAgg(fig_log, master=frame)
        canvas_log.get_tk_widget().grid(row=0, column=5, columnspan=5, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        line_iv, = ax_iv.plot([], [], marker=".")
        line_log, = ax_log.plot([], [], marker=".")

        self._register("rt_iv", fig_iv, ax_iv, canvas_iv, line_iv)
        self._register("rt_logiv", fig_log, ax_log, canvas_log, line_log)

    def create_all_sweeps_plots(self, parent: tk.Misc) -> None:
        frame = tk.LabelFrame(parent, text="Last Measurement Plot", padx=4, pady=3)
        frame.grid(row=1, column=0, padx=4, pady=3, sticky="nsew")

        fig_all_iv, ax_all_iv = self._make_figure(title="Iv - All")
        self._style_axis(ax_all_iv, "Voltage (V)", "Current (A)")
        fig_all_iv.tight_layout()
        canvas_all_iv = FigureCanvasTkAgg(fig_all_iv, master=frame)
        canvas_all_iv.get_tk_widget().grid(row=0, column=0, pady=5, sticky="nsew")

        fig_all_log, ax_all_log = self._make_figure(title="Log Plot - All")
        ax_all_log.set_yscale("log")
        self._style_axis(ax_all_log, "Voltage (V)", "|Current| (A)")
        fig_all_log.tight_layout()
        canvas_all_log = FigureCanvasTkAgg(fig_all_log, master=frame)
        canvas_all_log.get_tk_widget().grid(row=0, column=1, pady=5, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)

        tk.Button(frame, text="Ax1 Clear", command=lambda: self.clear_axis(2)).grid(row=1, column=0, pady=2)
        tk.Button(frame, text="Ax2 Clear", command=lambda: self.clear_axis(3)).grid(row=1, column=1, pady=2)

        self._register("all_iv", fig_all_iv, ax_all_iv, canvas_all_iv, None)
        self._register("all_logiv", fig_all_log, ax_all_log, canvas_all_log, None)

    def create_vi_logiv_plots(self, parent: tk.Misc) -> None:
        frame = tk.LabelFrame(parent, text="Log V / Log I", padx=4, pady=3)
        frame.grid(row=1, column=1, padx=4, pady=3, sticky="nsew")

        fig_logilogv, ax_logilogv = self._make_figure(title="LogV vs LogI")
        ax_logilogv.set_xscale("log")
        ax_logilogv.set_yscale("log")
        self._style_axis(ax_logilogv, "|Voltage| (V)", "|Current| (A)")

        canvas_logilogv = FigureCanvasTkAgg(fig_logilogv, master=frame)
        canvas_logilogv.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        line_logilogv, = ax_logilogv.plot([], [], marker=".", color="r")
        self._register("rt_logilogv", fig_logilogv, ax_logilogv, canvas_logilogv, line_logilogv)

    def create_endurance_retention_plots(self, parent: tk.Misc) -> None:
        frame = tk.LabelFrame(parent, text="Endurance & Retention", padx=4, pady=3)
        frame.grid(row=3, column=0, columnspan=2, padx=4, pady=3, sticky="nsew")

        fig_end, ax_end = self._make_figure(title="Endurance (ON/OFF)", figsize=(3, 2))
        self._style_axis(ax_end, "Cycle", "ON/OFF Ratio")
        canvas_end = FigureCanvasTkAgg(fig_end, master=frame)
        canvas_end.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        fig_ret, ax_ret = self._make_figure(title="Retention", figsize=(3, 2))
        ax_ret.set_xscale("log")
        ax_ret.set_yscale("log")
        self._style_axis(ax_ret, "Time (s)", "Current (A)")
        canvas_ret = FigureCanvasTkAgg(fig_ret, master=frame)
        canvas_ret.get_tk_widget().grid(row=0, column=1, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)

        self.endurance_ratios: List[float] = []
        self.retention_times: List[float] = []
        self.retention_currents: List[float] = []

        self._register("endurance", fig_end, ax_end, canvas_end, None)
        self._register("retention", fig_ret, ax_ret, canvas_ret, None)

    def create_current_time_plot(self, parent: tk.Misc) -> None:
        frame = tk.LabelFrame(parent, text="Current vs Time", padx=4, pady=3)
        frame.grid(row=2, column=0, padx=4, pady=3, sticky="nsew")

        fig_ct, ax_ct = self._make_figure(title="Current_time", figsize=(3, 2))
        self._style_axis(ax_ct, "Time (s)", "Current (A)")

        canvas_ct = FigureCanvasTkAgg(fig_ct, master=frame)
        canvas_ct.get_tk_widget().grid(row=0, column=0, columnspan=2, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        line_ct, = ax_ct.plot([], [], marker=".")
        self._register("ct_rt", fig_ct, ax_ct, canvas_ct, line_ct)

    def create_temp_time_plot(self, parent: tk.Misc, temp_enabled: bool) -> None:
        frame = tk.LabelFrame(parent, text="Temperature vs Time", padx=4, pady=3)
        frame.grid(row=2, column=1, padx=4, pady=3, sticky="nsew")

        if temp_enabled:
            fig_tt, ax_tt = self._make_figure(title="Temp time Plot", figsize=(2, 1))
            self._style_axis(ax_tt, "Time (s)", "Temp (°C)")

            canvas_tt = FigureCanvasTkAgg(fig_tt, master=frame)
            canvas_tt.get_tk_widget().grid(row=0, column=0, sticky="nsew")

            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)

            line_tt, = ax_tt.plot([], [], marker="x")
            self._register("tt_rt", fig_tt, ax_tt, canvas_tt, line_tt)
        else:
            label = tk.Label(frame, text="Temp plot disabled", fg="grey")
            label.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            # Clean any previous registration
            self._unregister("tt_rt")

    # ------------------------------------------------------------------
    # Plot maintenance helpers
    # ------------------------------------------------------------------
    def clear_axis(self, axis: int) -> None:
        """Clear one of the 'All sweeps' axes by index (legacy behaviour)."""
        if axis == 2:
            ax = self.axes.get("all_iv")
            canvas = self.canvases.get("all_iv")
        elif axis == 3:
            ax = self.axes.get("all_logiv")
            canvas = self.canvases.get("all_logiv")
        else:
            return
        if ax and canvas:
            ax.clear()
            if axis == 2:
                self._style_axis(ax, "Voltage (V)", "Current (A)")
            elif axis == 3:
                ax.set_yscale("log")
                self._style_axis(ax, "Voltage (V)", "|Current| (A)")
            canvas.draw()

    def graphs_show(self, v_arr: Sequence[float], c_arr: Sequence[float], key: str, stop_v: float) -> None:
        """Add a completed sweep onto the 'all sweeps' panels."""
        self.last_sweep = (list(v_arr), list(c_arr))
        ax_all_iv = self.axes.get("all_iv")
        ax_all_logiv = self.axes.get("all_logiv")
        if ax_all_iv and ax_all_logiv:
            label = f"{key}_{stop_v}v"
            ax_all_iv.plot(v_arr, c_arr, marker="o", markersize=2, label=label, alpha=0.8)
            ax_all_iv.legend(loc="best", fontsize="5")
            ax_all_logiv.plot(v_arr, np.abs(c_arr), marker="o", markersize=2, label=label, alpha=0.8)
            ax_all_logiv.legend(loc="best", fontsize="5")
            self.canvases["all_iv"].draw()
            self.canvases["all_logiv"].draw()

    def reset_for_new_run(self) -> None:
        """Clear live buffers and summary axes so a new run starts clean."""
        for name in ["rt_iv", "rt_logiv", "rt_logilogv", "ct_rt", "tt_rt"]:
            line = self.lines.get(name)
            canvas = self.canvases.get(name)
            if line is not None:
                line.set_data([], [])
                if canvas:
                    canvas.draw()

        for key in ["all_iv", "all_logiv"]:
            ax = self.axes.get(key)
            canvas = self.canvases.get(key)
            if ax and canvas:
                ax.clear()
                if key == "all_logiv":
                    ax.set_yscale("log")
                canvas.draw()

        self.last_sweep = ([], [])

    # ------------------------------------------------------------------
    # Legacy attribute attachment
    # ------------------------------------------------------------------
    def attach_to(self, target: object) -> None:
        """
        Copy legacy attributes onto ``target`` (usually the main GUI).
        """
        for name in self._legacy_attributes():
            if hasattr(self, name):
                setattr(target, name, getattr(self, name))
        # Convenience aliases for legacy method names
        setattr(target, "graphs_show", self.graphs_show)
        setattr(target, "_reset_plots_for_new_run", self.reset_for_new_run)
        setattr(target, "clear_axis", self.clear_axis)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _make_figure(self, title: str, figsize: Tuple[int, int] = (3, 3)) -> Tuple[Figure, object]:
        fig = Figure(figsize=figsize)
        ax = fig.add_subplot(111)
        ax.set_title(title, fontsize=self.font_config["title"])
        return fig, ax

    def _style_axis(self, ax: object, xlabel: str, ylabel: str) -> None:
        axis_font = self.font_config.get("axis", 7)
        tick_font = self.font_config.get("ticks", max(axis_font - 1, 5))
        ax.set_xlabel(xlabel, fontsize=axis_font)
        ax.set_ylabel(ylabel, fontsize=axis_font)
        ax.tick_params(axis="both", labelsize=tick_font)

    def _register(
        self,
        key: str,
        figure: Figure,
        axis: object,
        canvas: FigureCanvasTkAgg,
        line: Optional[object],
    ) -> None:
        self.figures[key] = figure
        self.axes[key] = axis
        self.canvases[key] = canvas
        if line is not None:
            self.lines[key] = line
        setattr(self, f"figure_{key}", figure)
        setattr(self, f"ax_{key}", axis)
        setattr(self, f"canvas_{key}", canvas)
        if line is not None:
            setattr(self, f"line_{key}", line)

    def _unregister(self, key: str) -> None:
        for store, prefix in (
            (self.figures, "figure_"),
            (self.axes, "ax_"),
            (self.canvases, "canvas_"),
            (self.lines, "line_"),
        ):
            if key in store:
                del store[key]
            attr = f"{prefix}{key}"
            if hasattr(self, attr):
                delattr(self, attr)

    def _legacy_attributes(self) -> Iterable[str]:
        """Names that should survive on the legacy GUI object."""
        attrs = [
            # Main IV plots
            "figure_rt_iv", "ax_rt_iv", "canvas_rt_iv", "line_rt_iv",
            "figure_rt_logiv", "ax_rt_logiv", "canvas_rt_logiv", "line_rt_logiv",
            # All sweeps
            "figure_all_iv", "ax_all_iv", "canvas_all_iv",
            "figure_all_logiv", "ax_all_logiv", "canvas_all_logiv",
            # Log V / Log I
            "figure_rt_logilogv", "ax_rt_logilogv", "canvas_rt_logilogv", "line_rt_logilogv",
            # Endurance / retention
            "figure_endurance", "ax_endurance", "canvas_endurance",
            "figure_retention", "ax_retention", "canvas_retention",
            # Current / resistance time
            "figure_ct_rt", "ax_ct_rt", "canvas_ct_rt", "line_ct_rt",
        ]
        # Temperature plot attributes are optional
        for name in ["figure_tt_rt", "ax_tt_rt", "canvas_tt_rt", "line_tt_rt"]:
            if hasattr(self, name):
                attrs.append(name)
        # Manual data holders
        for name in ["endurance_ratios", "retention_times", "retention_currents"]:
            if hasattr(self, name):
                attrs.append(name)
        return attrs


# ----------------------------------------------------------------------
# Lightweight diagnostics
# ----------------------------------------------------------------------
def _self_test() -> Dict[str, int]:
    """
    Instantiate the panels in a hidden Tk root to ensure the builder works.
    """
    root = tk.Tk()
    root.withdraw()
    panels = MeasurementPlotPanels()
    try:
        panels.create_all_plots(root, temp_enabled=True)
        counts = {"figures": len(panels.figures), "axes": len(panels.axes)}
    finally:
        root.destroy()
    return counts


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    import json

    print(json.dumps(_self_test(), indent=2))

