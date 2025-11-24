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

MODERNIZED VERSION:
- Supports dynamic show/hide of individual plots
- Larger display area with flexible grid layout
- Floating info overlay on main plots
- Graph visibility dropdown menu
"""

from __future__ import annotations

# Standard library imports
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Third-party imports
import numpy as np
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tkinter import ttk


PlotLine = Tuple[List[float], List[float]]


@dataclass
class MeasurementPlotPanels:
    """
    Build and manage all matplotlib plot panels embedded in the GUI.

    Attributes created here mirror the names used by the original monolithic
    GUI (`ax_rt_iv`, `canvas_all_logiv`, ...).  The method
    :meth:`attach_to` copies these attributes onto the caller so existing
    code continues to work while we complete the refactor.
    
    NEW: Supports dynamic visibility management and floating overlays
    """

    font_config: Dict[str, int] = field(
        default_factory=lambda: {"axis": 9, "title": 11, "ticks": 8}
    )
    figures: Dict[str, Figure] = field(default_factory=dict)
    axes: Dict[str, object] = field(default_factory=dict)
    canvases: Dict[str, FigureCanvasTkAgg] = field(default_factory=dict)
    lines: Dict[str, object] = field(default_factory=dict)
    last_sweep: PlotLine = field(default_factory=lambda: ([], []))
    
    # New attributes for modern layout
    plot_frames: Dict[str, tk.Frame] = field(default_factory=dict)
    plot_visibility: Dict[str, tk.BooleanVar] = field(default_factory=dict)
    overlay_label: Optional[tk.Label] = None
    main_container: Optional[tk.Frame] = None
    
    # Reference to GUI for context menu callbacks
    gui: Optional[object] = None

    # ------------------------------------------------------------------
    # Public construction API
    # ------------------------------------------------------------------
    def create_all_plots(self, graph_frame: tk.Misc, temp_enabled: bool) -> None:
        """Create every matplotlib panel and embed it inside ``graph_frame`` - LEGACY"""
        self.create_main_iv_plots(graph_frame)
        self.create_all_sweeps_plots(graph_frame)
        self.create_vi_logiv_plots(graph_frame)
        self.create_current_time_plot(graph_frame)
        self.create_temp_time_plot(graph_frame, temp_enabled=temp_enabled)
        self.create_endurance_retention_plots(graph_frame)
    
    def create_all_plots_modern(self, graph_frame: tk.Misc, temp_enabled: bool) -> None:
        """
        Create modern plot layout with dynamic visibility controls.
        This is the new entry point for the modernized GUI.
        """
        self.main_container = graph_frame
        
        # Create control bar at top with visibility dropdown
        control_bar = tk.Frame(graph_frame, bg='white', height=40)
        control_bar.pack(side='top', fill='x', padx=10, pady=(5, 0))
        control_bar.pack_propagate(False)
        
        tk.Label(control_bar, text="Visible Graphs:", font=("Segoe UI", 9, "bold"), bg='white').pack(side='left', padx=(0, 10))
        
        # Visibility controls button
        visibility_btn = tk.Button(
            control_bar,
            text="Select Graphs ▼",
            font=("Segoe UI", 9),
            command=lambda: self._show_visibility_menu(visibility_btn),
            bg='#f0f0f0',
            relief='raised',
            padx=10,
            pady=3
        )
        visibility_btn.pack(side='left')
        
        # Create container for plots with dynamic grid
        plot_container = tk.Frame(graph_frame, bg='white')
        plot_container.pack(side='top', fill='both', expand=True, padx=10, pady=10)
        
        # Initialize visibility states (IV and LogIV always visible by default)
        self.plot_visibility = {
            "rt_iv": tk.BooleanVar(value=True),
            "rt_logiv": tk.BooleanVar(value=True),
            "all_sweeps": tk.BooleanVar(value=False),
            "logilogv": tk.BooleanVar(value=False),
            "current_time": tk.BooleanVar(value=False),
            "temp_time": tk.BooleanVar(value=False),
            "endurance": tk.BooleanVar(value=False),
            "retention": tk.BooleanVar(value=False),
        }
        
        # Create all plot frames (initially hidden except IV/LogIV)
        self._create_modern_plot_panels(plot_container, temp_enabled)
        
        # Create floating overlay
        self._create_floating_overlay(plot_container)
        
        # Initial layout
        self._update_plot_layout()
    
    def _show_visibility_menu(self, button: tk.Widget) -> None:
        """Show dropdown menu for graph visibility selection"""
        menu = tk.Menu(button, tearoff=0)
        
        # Add checkboxes for each plot
        labels = {
            "rt_iv": "IV Plot (Real-time)",
            "rt_logiv": "Log IV Plot (Real-time)",
            "all_sweeps": "All Sweeps",
            "logilogv": "Log V vs Log I",
            "current_time": "Current vs Time",
            "temp_time": "Temperature vs Time",
            "endurance": "Endurance",
            "retention": "Retention",
        }
        
        for key, label in labels.items():
            if key in self.plot_visibility:
                menu.add_checkbutton(
                    label=label,
                    variable=self.plot_visibility[key],
                    command=self._update_plot_layout
                )
        
        # Show menu below button
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            menu.post(x, y)
        except:
            pass
    
    def _update_plot_layout(self) -> None:
        """Update the grid layout based on visibility settings"""
        # Hide all plots first
        for frame in self.plot_frames.values():
            frame.grid_forget()
        
        # Get visible plots
        visible = [key for key, var in self.plot_visibility.items() if var.get()]
        
        if not visible:
            return
        
        # Layout strategy: IV and LogIV get priority (larger, side by side if both visible)
        # Others fill in below in a 2-column grid
        
        row = 0
        col = 0
        
        # Priority plots (IV and LogIV) - always larger
        priority_plots = ["rt_iv", "rt_logiv"]
        priority_visible = [p for p in priority_plots if p in visible]
        
        if len(priority_visible) == 2:
            # Both IV and LogIV visible - side by side, large
            self.plot_frames["rt_iv"].grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))
            self.plot_frames["rt_logiv"].grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 5))
            row = 1
        elif len(priority_visible) == 1:
            # Only one priority plot - full width, large
            self.plot_frames[priority_visible[0]].grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 5))
            row = 1
        
        # Secondary plots - 2 column grid
        secondary_plots = [p for p in visible if p not in priority_visible]
        for i, plot_key in enumerate(secondary_plots):
            if plot_key in self.plot_frames:
                col = i % 2
                if col == 0 and i > 0:
                    row += 1
                pad_x = (0, 5) if col == 0 else (5, 0)
                self.plot_frames[plot_key].grid(row=row, column=col, sticky="nsew", padx=pad_x, pady=(0, 5))
        
        # Configure grid weights for responsive resizing
        if self.main_container:
            parent = list(self.plot_frames.values())[0].master
            parent.columnconfigure(0, weight=1)
            parent.columnconfigure(1, weight=1)
            # Priority row gets more weight
            parent.rowconfigure(0, weight=3)
            for r in range(1, row + 1):
                parent.rowconfigure(r, weight=1)
    
    def _create_modern_plot_panels(self, parent: tk.Frame, temp_enabled: bool) -> None:
        """Create all plot panels in modern layout"""
        # IV Plot
        frame_iv = tk.LabelFrame(parent, text="IV Plot", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        fig_iv, ax_iv = self._make_figure(title="IV", figsize=(5, 4))
        self._style_axis(ax_iv, "Voltage (V)", "Current (A)")
        canvas_iv = FigureCanvasTkAgg(fig_iv, master=frame_iv)
        canvas_iv.get_tk_widget().pack(fill='both', expand=True)
        line_iv, = ax_iv.plot([], [], marker=".", markersize=3)
        self._register("rt_iv", fig_iv, ax_iv, canvas_iv, line_iv)
        self.plot_frames["rt_iv"] = frame_iv
        
        # Log IV Plot
        frame_logiv = tk.LabelFrame(parent, text="Log IV Plot", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        fig_log, ax_log = self._make_figure(title="Log IV", figsize=(5, 4))
        ax_log.set_yscale("log")
        self._style_axis(ax_log, "Voltage (V)", "|Current| (A)")
        canvas_log = FigureCanvasTkAgg(fig_log, master=frame_logiv)
        canvas_log.get_tk_widget().pack(fill='both', expand=True)
        line_log, = ax_log.plot([], [], marker=".", markersize=3)
        self._register("rt_logiv", fig_log, ax_log, canvas_log, line_log)
        self.plot_frames["rt_logiv"] = frame_logiv
        
        # All Sweeps (combined IV and Log IV)
        frame_all = tk.LabelFrame(parent, text="All Sweeps", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        inner_frame = tk.Frame(frame_all, bg='white')
        inner_frame.pack(fill='both', expand=True)
        inner_frame.columnconfigure(0, weight=1)
        inner_frame.columnconfigure(1, weight=1)
        inner_frame.rowconfigure(0, weight=1)
        
        fig_all_iv, ax_all_iv = self._make_figure(title="IV - All", figsize=(4, 3))
        self._style_axis(ax_all_iv, "Voltage (V)", "Current (A)")
        canvas_all_iv = FigureCanvasTkAgg(fig_all_iv, master=inner_frame)
        canvas_all_iv.get_tk_widget().grid(row=0, column=0, sticky='nsew', padx=(0, 3))
        
        fig_all_log, ax_all_log = self._make_figure(title="Log IV - All", figsize=(4, 3))
        ax_all_log.set_yscale("log")
        self._style_axis(ax_all_log, "Voltage (V)", "|Current| (A)")
        canvas_all_log = FigureCanvasTkAgg(fig_all_log, master=inner_frame)
        canvas_all_log.get_tk_widget().grid(row=0, column=1, sticky='nsew', padx=(3, 0))
        
        btn_frame = tk.Frame(frame_all, bg='white')
        btn_frame.pack(fill='x', pady=(5, 0))
        tk.Button(btn_frame, text="Clear IV", command=lambda: self.clear_axis(2), font=("Segoe UI", 8)).pack(side='left', padx=3)
        tk.Button(btn_frame, text="Clear Log IV", command=lambda: self.clear_axis(3), font=("Segoe UI", 8)).pack(side='left', padx=3)
        
        self._register("all_iv", fig_all_iv, ax_all_iv, canvas_all_iv, None)
        self._register("all_logiv", fig_all_log, ax_all_log, canvas_all_log, None)
        self.plot_frames["all_sweeps"] = frame_all
        
        # Log V vs Log I
        frame_logilogv = tk.LabelFrame(parent, text="Log V vs Log I", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        fig_logilogv, ax_logilogv = self._make_figure(title="LogV vs LogI", figsize=(4, 3))
        ax_logilogv.set_xscale("log")
        ax_logilogv.set_yscale("log")
        self._style_axis(ax_logilogv, "|Voltage| (V)", "|Current| (A)")
        canvas_logilogv = FigureCanvasTkAgg(fig_logilogv, master=frame_logilogv)
        canvas_logilogv.get_tk_widget().pack(fill='both', expand=True)
        line_logilogv, = ax_logilogv.plot([], [], marker=".", color="r", markersize=3)
        self._register("rt_logilogv", fig_logilogv, ax_logilogv, canvas_logilogv, line_logilogv)
        self.plot_frames["logilogv"] = frame_logilogv
        
        # Current vs Time
        frame_ct = tk.LabelFrame(parent, text="Current vs Time", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        fig_ct, ax_ct = self._make_figure(title="Current vs Time", figsize=(4, 3))
        self._style_axis(ax_ct, "Time (s)", "Current (A)")
        canvas_ct = FigureCanvasTkAgg(fig_ct, master=frame_ct)
        canvas_ct.get_tk_widget().pack(fill='both', expand=True)
        line_ct, = ax_ct.plot([], [], marker=".", markersize=3)
        self._register("ct_rt", fig_ct, ax_ct, canvas_ct, line_ct)
        self.plot_frames["current_time"] = frame_ct
        
        # Temperature vs Time (if enabled)
        if temp_enabled:
            frame_tt = tk.LabelFrame(parent, text="Temperature vs Time", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
            fig_tt, ax_tt = self._make_figure(title="Temperature vs Time", figsize=(4, 3))
            self._style_axis(ax_tt, "Time (s)", "Temp (°C)")
            canvas_tt = FigureCanvasTkAgg(fig_tt, master=frame_tt)
            canvas_tt.get_tk_widget().pack(fill='both', expand=True)
            line_tt, = ax_tt.plot([], [], marker="x", markersize=3)
            self._register("tt_rt", fig_tt, ax_tt, canvas_tt, line_tt)
            self.plot_frames["temp_time"] = frame_tt
        
        # Endurance
        frame_end = tk.LabelFrame(parent, text="Endurance", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        fig_end, ax_end = self._make_figure(title="Endurance (ON/OFF)", figsize=(4, 3))
        self._style_axis(ax_end, "Cycle", "ON/OFF Ratio")
        canvas_end = FigureCanvasTkAgg(fig_end, master=frame_end)
        canvas_end.get_tk_widget().pack(fill='both', expand=True)
        self.endurance_ratios: List[float] = []
        self._register("endurance", fig_end, ax_end, canvas_end, None)
        self.plot_frames["endurance"] = frame_end
        
        # Retention
        frame_ret = tk.LabelFrame(parent, text="Retention", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        fig_ret, ax_ret = self._make_figure(title="Retention", figsize=(4, 3))
        ax_ret.set_xscale("log")
        ax_ret.set_yscale("log")
        self._style_axis(ax_ret, "Time (s)", "Current (A)")
        canvas_ret = FigureCanvasTkAgg(fig_ret, master=frame_ret)
        canvas_ret.get_tk_widget().pack(fill='both', expand=True)
        self.retention_times: List[float] = []
        self.retention_currents: List[float] = []
        self._register("retention", fig_ret, ax_ret, canvas_ret, None)
        self.plot_frames["retention"] = frame_ret
    
    def _create_floating_overlay(self, parent: tk.Frame) -> None:
        """Create a floating info overlay with light orange transparency"""
        overlay = tk.Label(
            parent,
            text="Sample: — | Device: — | Voltage: 0V | Loop: #1",
            font=("Segoe UI", 9, "bold"),
            bg='#ffe0b2',  # Light orange
            fg='#e65100',  # Dark orange text
            relief='solid',
            borderwidth=1,
            padx=12,
            pady=6
        )
        # Position at top-center
        overlay.place(relx=0.5, rely=0.01, anchor='n')
        
        self.overlay_label = overlay
    
    def update_overlay(self, sample_name: str = "—", device: str = "—", voltage: str = "0V", loop: str = "#1") -> None:
        """Update the floating overlay text"""
        if self.overlay_label:
            text = f"Sample: {sample_name} | Device: {device} | Voltage: {voltage} | Loop: {loop}"
            self.overlay_label.config(text=text)
    
    # ------------------------------------------------------------------
    # Conditional visibility helpers
    # ------------------------------------------------------------------
    def show_plot(self, plot_key: str) -> None:
        """Show a specific plot by setting its visibility to True"""
        if plot_key in self.plot_visibility:
            self.plot_visibility[plot_key].set(True)
            self._update_plot_layout()
    
    def hide_plot(self, plot_key: str) -> None:
        """Hide a specific plot by setting its visibility to False"""
        if plot_key in self.plot_visibility:
            self.plot_visibility[plot_key].set(False)
            self._update_plot_layout()
    
    def show_endurance_plot(self) -> None:
        """Show endurance plot when endurance test is running"""
        self.show_plot("endurance")
    
    def hide_endurance_plot(self) -> None:
        """Hide endurance plot when endurance test is complete"""
        self.hide_plot("endurance")
    
    def show_retention_plot(self) -> None:
        """Show retention plot when retention test is running"""
        self.show_plot("retention")
    
    def hide_retention_plot(self) -> None:
        """Hide retention plot when retention test is complete"""
        self.hide_plot("retention")
    
    def show_temp_plot(self) -> None:
        """Show temperature plot when temp measurements are active"""
        self.show_plot("temp_time")
    
    def hide_temp_plot(self) -> None:
        """Hide temperature plot when temp measurements are inactive"""
        self.hide_plot("temp_time")

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

    def reset_for_new_sweep(self, gui: Optional[object] = None) -> None:
        """Clear only individual real-time graphs between sweeps (keeps combined graphs)."""
        # Clear data buffers if GUI reference provided
        if gui is not None:
            if hasattr(gui, 'v_arr_disp'):
                gui.v_arr_disp.clear()
            if hasattr(gui, 'c_arr_disp'):
                gui.c_arr_disp.clear()
            if hasattr(gui, 't_arr_disp'):
                gui.t_arr_disp.clear()
            if hasattr(gui, 'c_arr_disp_abs'):
                gui.c_arr_disp_abs.clear()
        
        # Clear axes and recreate lines for individual graphs
        axis_configs = {
            "rt_iv": ("Voltage (V)", "Current (A)", None, None),
            "rt_logiv": ("Voltage (V)", "|Current| (A)", None, "log"),
            "rt_logilogv": ("|Voltage| (V)", "|Current| (A)", "log", "log"),
            "ct_rt": ("Time (s)", "Current (A)", None, None),
            "tt_rt": ("Time (s)", "Temp (°C)", None, None),
        }
        
        for name in ["rt_iv", "rt_logiv", "rt_logilogv", "ct_rt", "tt_rt"]:
            ax = self.axes.get(name)
            canvas = self.canvases.get(name)
            if ax is None or canvas is None:
                continue
            
            # Clear the entire axis
            ax.clear()
            
            # Reapply styling
            if name in axis_configs:
                xlabel, ylabel, xscale, yscale = axis_configs[name]
                self._style_axis(ax, xlabel, ylabel)
                if xscale == "log":
                    ax.set_xscale("log")
                if yscale == "log":
                    ax.set_yscale("log")
            
            # Recreate the line
            if name == "tt_rt":
                line, = ax.plot([], [], marker="x", markersize=3)
            elif name == "rt_logilogv":
                line, = ax.plot([], [], marker=".", color="r", markersize=3)
            else:
                line, = ax.plot([], [], marker=".", markersize=3)
            
            # Update the line reference
            self.lines[name] = line
            
            # Redraw
            canvas.draw()

        self.last_sweep = ([], [])

    def reset_for_new_run(self, gui: Optional[object] = None) -> None:
        """Clear live buffers and summary axes so a new run starts clean."""
        # Clear data buffers if GUI reference provided
        if gui is not None:
            if hasattr(gui, 'v_arr_disp'):
                gui.v_arr_disp.clear()
            if hasattr(gui, 'c_arr_disp'):
                gui.c_arr_disp.clear()
            if hasattr(gui, 't_arr_disp'):
                gui.t_arr_disp.clear()
            if hasattr(gui, 'c_arr_disp_abs'):
                gui.c_arr_disp_abs.clear()
        
        # Clear individual graphs using ax.clear()
        axis_configs = {
            "rt_iv": ("Voltage (V)", "Current (A)", None, None),
            "rt_logiv": ("Voltage (V)", "|Current| (A)", None, "log"),
            "rt_logilogv": ("|Voltage| (V)", "|Current| (A)", "log", "log"),
            "ct_rt": ("Time (s)", "Current (A)", None, None),
            "tt_rt": ("Time (s)", "Temp (°C)", None, None),
        }
        
        for name in ["rt_iv", "rt_logiv", "rt_logilogv", "ct_rt", "tt_rt"]:
            ax = self.axes.get(name)
            canvas = self.canvases.get(name)
            if ax is None or canvas is None:
                continue
            
            # Clear the entire axis
            ax.clear()
            
            # Reapply styling
            if name in axis_configs:
                xlabel, ylabel, xscale, yscale = axis_configs[name]
                self._style_axis(ax, xlabel, ylabel)
                if xscale == "log":
                    ax.set_xscale("log")
                if yscale == "log":
                    ax.set_yscale("log")
            
            # Recreate the line
            if name == "tt_rt":
                line, = ax.plot([], [], marker="x", markersize=3)
            elif name == "rt_logilogv":
                line, = ax.plot([], [], marker=".", color="r", markersize=3)
            else:
                line, = ax.plot([], [], marker=".", markersize=3)
            
            # Update the line reference
            self.lines[name] = line
            
            # Redraw
            canvas.draw()

        # Clear combined graphs (all sweeps) for a completely new run
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
        setattr(target, "_reset_plots_for_new_sweep", self.reset_for_new_sweep)
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
        
        # Context menu will be set up by layout_builder after gui is attached

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

