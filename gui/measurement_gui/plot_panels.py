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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
    recent_dots: Dict[str, object] = field(default_factory=dict)  # Red dots for most recent values
    
    # New attributes for modern layout
    plot_frames: Dict[str, tk.Frame] = field(default_factory=dict)
    plot_visibility: Dict[str, tk.BooleanVar] = field(default_factory=dict)
    overlay_label: Optional[tk.Label] = None
    main_container: Optional[tk.Frame] = None
    
    # Reference to GUI for context menu callbacks
    gui: Optional[object] = None
    
    # Graph activity terminal/log
    graph_terminal: Optional[tk.Text] = None
    graph_terminal_scrollbar: Optional[tk.Scrollbar] = None

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
            "endurance_current": tk.BooleanVar(value=False),
            "retention": tk.BooleanVar(value=False),
            "analysis_stats": tk.BooleanVar(value=False),  # Stats panel
            "pulse_table": tk.BooleanVar(value=False),  # Pulse history table
        }
        
        # Create all plot frames (initially hidden except IV/LogIV)
        self._create_modern_plot_panels(plot_container, temp_enabled)
        
        # Create floating overlay
        self._create_floating_overlay(plot_container)
        
        # Note: Graph activity terminal is created in the Graphing tab, not here
        # (Terminal was moved to Graphing tab per user request)
        
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
            "analysis_stats": "Analysis Statistics",
            "pulse_table": "Pulse Table",
        }
        
        for key, label in labels.items():
            if key in self.plot_visibility:
                menu.add_checkbutton(
                    label=label,
                    variable=self.plot_visibility[key],
                    command=lambda k=key: self._on_plot_visibility_changed(k)
                )
        
        # Show menu below button
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            menu.post(x, y)
        except:
            pass
    
    def _on_plot_visibility_changed(self, plot_key: str) -> None:
        """Handle plot visibility change, including stats panel toggle logic"""
        # Special handling for stats panel - hide floating window when panel is visible
        if plot_key == "analysis_stats" and self.gui:
            stats_visible = self.plot_visibility["analysis_stats"].get()
            if stats_visible and hasattr(self.gui, 'analysis_stats_window'):
                # Hide floating window when panel is shown
                if self.gui.analysis_stats_window:
                    self.gui.analysis_stats_window.hide()
        
        # Update layout
        self._update_plot_layout()
    
    def _update_plot_layout(self) -> None:
        """Update the grid layout based on visibility settings"""
        # Hide all plots first
        for frame in self.plot_frames.values():
            frame.grid_forget()
        
        # Get visible plots (exclude stats from grid layout - it will be handled separately if needed)
        visible = [key for key, var in self.plot_visibility.items() if var.get() and key != "analysis_stats"]
        stats_visible = self.plot_visibility.get("analysis_stats", tk.BooleanVar(value=False)).get()
        
        # Layout strategy: IV and LogIV get priority (larger, side by side if both visible)
        # Others fill in below in a 2-column grid
        # Stats panel goes to the right (column 2) and spans all rows vertically
        
        row = 0
        col = 0
        max_row = 0
        
        # Priority plots (IV and LogIV) - always larger
        priority_plots = ["rt_iv", "rt_logiv"]
        priority_visible = [p for p in priority_plots if p in visible]
        
        if len(priority_visible) == 2:
            # Both IV and LogIV visible - side by side, large
            self.plot_frames["rt_iv"].grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))
            self.plot_frames["rt_logiv"].grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 5))
            row = 1
            max_row = 0
        elif len(priority_visible) == 1:
            # Only one priority plot - full width, large
            self.plot_frames[priority_visible[0]].grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 5))
            row = 1
            max_row = 0
        
        # Secondary plots - 2 column grid
        secondary_plots = [p for p in visible if p not in priority_visible]
        for i, plot_key in enumerate(secondary_plots):
            if plot_key in self.plot_frames:
                col = i % 2
                if col == 0 and i > 0:
                    row += 1
                pad_x = (0, 5) if col == 0 else (5, 0)
                self.plot_frames[plot_key].grid(row=row, column=col, sticky="nsew", padx=pad_x, pady=(0, 5))
                max_row = max(max_row, row)
        
        # Add stats panel if visible - positioned to the right (column 2) and spans all rows
        if stats_visible and "analysis_stats" in self.plot_frames:
            # Calculate the total number of rows used by plots
            # If no plots are visible, stats panel should still span at least 1 row
            if max_row == 0 and len(visible) == 0:
                # No plots visible, stats panel takes full height
                rowspan = 1
            else:
                # Span from row 0 to max_row
                rowspan = max_row + 1
            
            self.plot_frames["analysis_stats"].grid(
                row=0, 
                column=2, 
                rowspan=rowspan,
                sticky="nsew", 
                padx=(10, 0), 
                pady=(0, 5)
            )
        
        # Configure grid weights for responsive resizing
        if self.main_container:
            parent = list(self.plot_frames.values())[0].master
            parent.columnconfigure(0, weight=1)
            parent.columnconfigure(1, weight=1)
            if stats_visible:
                # Stats panel column gets less weight (narrower) - half the previous width (75px)
                parent.columnconfigure(2, weight=0, minsize=75)
            else:
                # When stats are hidden, ensure column 2 doesn't take space
                parent.columnconfigure(2, weight=0, minsize=0)
            # Priority row gets more weight
            if max_row >= 0:
                parent.rowconfigure(0, weight=3)
                for r in range(1, max_row + 1):
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
        # Create red dot for most recent value
        recent_dot_iv, = ax_iv.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
        self._register("rt_iv", fig_iv, ax_iv, canvas_iv, line_iv)
        self.recent_dots["rt_iv"] = recent_dot_iv
        self.plot_frames["rt_iv"] = frame_iv
        
        # Log IV Plot
        frame_logiv = tk.LabelFrame(parent, text="Log IV Plot", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        fig_log, ax_log = self._make_figure(title="Log IV", figsize=(5, 4))
        ax_log.set_yscale("log")
        self._style_axis(ax_log, "Voltage (V)", "|Current| (A)")
        canvas_log = FigureCanvasTkAgg(fig_log, master=frame_logiv)
        canvas_log.get_tk_widget().pack(fill='both', expand=True)
        line_log, = ax_log.plot([], [], marker=".", markersize=3)
        # Create red dot for most recent value
        recent_dot_log, = ax_log.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
        self._register("rt_logiv", fig_log, ax_log, canvas_log, line_log)
        self.recent_dots["rt_logiv"] = recent_dot_log
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
        # Create red dot for most recent value
        recent_dot_logilogv, = ax_logilogv.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
        self._register("rt_logilogv", fig_logilogv, ax_logilogv, canvas_logilogv, line_logilogv)
        self.recent_dots["rt_logilogv"] = recent_dot_logilogv
        self.plot_frames["logilogv"] = frame_logilogv
        
        # Current vs Time
        frame_ct = tk.LabelFrame(parent, text="Current vs Time", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        fig_ct, ax_ct = self._make_figure(title="Current vs Time", figsize=(4, 3))
        self._style_axis(ax_ct, "Time (s)", "Current (A)")
        canvas_ct = FigureCanvasTkAgg(fig_ct, master=frame_ct)
        canvas_ct.get_tk_widget().pack(fill='both', expand=True)
        line_ct, = ax_ct.plot([], [], marker=".", markersize=3)
        # Create red dot for most recent value
        recent_dot_ct, = ax_ct.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
        self._register("ct_rt", fig_ct, ax_ct, canvas_ct, line_ct)
        self.recent_dots["ct_rt"] = recent_dot_ct
        self.plot_frames["current_time"] = frame_ct
        
        # Temperature vs Time (if enabled)
        if temp_enabled:
            frame_tt = tk.LabelFrame(parent, text="Temperature vs Time", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
            fig_tt, ax_tt = self._make_figure(title="Temperature vs Time", figsize=(4, 3))
            self._style_axis(ax_tt, "Time (s)", "Temp (°C)")
            canvas_tt = FigureCanvasTkAgg(fig_tt, master=frame_tt)
            canvas_tt.get_tk_widget().pack(fill='both', expand=True)
            line_tt, = ax_tt.plot([], [], marker="x", markersize=3)
            # Create red dot for most recent value
            recent_dot_tt, = ax_tt.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
            self._register("tt_rt", fig_tt, ax_tt, canvas_tt, line_tt)
            self.recent_dots["tt_rt"] = recent_dot_tt
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
        
        # Endurance Current (ON/OFF over time)
        frame_end_curr = tk.LabelFrame(parent, text="Endurance Current", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        fig_end_curr, ax_end_curr = self._make_figure(title="Endurance Current (ON/OFF)", figsize=(4, 3))
        ax_end_curr.set_yscale("log")
        self._style_axis(ax_end_curr, "Time (s)", "Current (A)")
        canvas_end_curr = FigureCanvasTkAgg(fig_end_curr, master=frame_end_curr)
        canvas_end_curr.get_tk_widget().pack(fill='both', expand=True)
        # Initialize endurance current tracking lists
        if not hasattr(self, 'endurance_on_times'):
            self.endurance_on_times: List[float] = []
            self.endurance_on_currents: List[float] = []
            self.endurance_off_times: List[float] = []
            self.endurance_off_currents: List[float] = []
        self._register("endurance_current", fig_end_curr, ax_end_curr, canvas_end_curr, None)
        self.plot_frames["endurance_current"] = frame_end_curr
        
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
        
        # Analysis Statistics Panel
        frame_stats = tk.LabelFrame(parent, text="Analysis Statistics", font=("Segoe UI", 9, "bold"), bg='white', padx=5, pady=5)
        # Create a text widget for stats display
        stats_text_frame = tk.Frame(frame_stats, bg='white')
        stats_text_frame.pack(fill='both', expand=True)
        
        # Text widget with scrollbar
        stats_scrollbar = ttk.Scrollbar(stats_text_frame)
        stats_scrollbar.pack(side='right', fill='y')
        
        self.stats_text = tk.Text(
            stats_text_frame,
            font=("Segoe UI", 8),
            bg='#ffe0b2',  # Light orange background
            fg='#e65100',  # Dark orange text
            wrap='word',
            relief='solid',
            borderwidth=1,
            padx=8,
            pady=8,
            yscrollcommand=stats_scrollbar.set
        )
        self.stats_text.pack(side='left', fill='both', expand=True)
        stats_scrollbar.config(command=self.stats_text.yview)
        
        # Store reference to stats frame
        self.plot_frames["analysis_stats"] = frame_stats
        self.stats_text_widget = self.stats_text  # For easy access
        
        # Pulse History Table
        frame_pulse_table = tk.Frame(parent, bg='white')
        # Control buttons frame
        pulse_control_frame = tk.Frame(frame_pulse_table, bg='white')
        pulse_control_frame.pack(fill='x', pady=(0, 5))
        
        tk.Label(pulse_control_frame, text="Pulse Table", font=("Segoe UI", 9, "bold"), bg='white').pack(side='left', padx=(0, 10))
        
        clear_pulse_btn = tk.Button(
            pulse_control_frame,
            text="Clear",
            font=("Segoe UI", 8),
            bg='#f44336',
            fg='white',
            activebackground='#d32f2f',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            pady=2,
            padx=8,
            command=lambda: self.gui._clear_pulse_history() if hasattr(self.gui, '_clear_pulse_history') else None
        )
        clear_pulse_btn.pack(side='left', padx=(0, 5))
        
        save_pulse_btn = tk.Button(
            pulse_control_frame,
            text="Save",
            font=("Segoe UI", 8),
            bg='#4CAF50',
            fg='white',
            activebackground='#388e3c',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            pady=2,
            padx=8,
            command=lambda: self.gui._save_pulse_history() if hasattr(self.gui, '_save_pulse_history') else None
        )
        save_pulse_btn.pack(side='left')
        
        # Text widget for pulse history (no border, simple)
        pulse_text_frame = tk.Frame(frame_pulse_table, bg='white')
        pulse_text_frame.pack(fill='both', expand=True)
        
        pulse_scrollbar = tk.Scrollbar(pulse_text_frame, orient='vertical')
        pulse_scrollbar.pack(side='right', fill='y')
        
        # Store reference on GUI for access from main.py
        if self.gui:
            self.gui.pulse_history_text = tk.Text(
                pulse_text_frame,
                font=("Consolas", 7),
                bg='white',
                fg='black',
                wrap='none',
                relief='flat',
                padx=5,
                pady=5,
                yscrollcommand=pulse_scrollbar.set,
                state='disabled'
            )
            self.gui.pulse_history_text.pack(side='left', fill='both', expand=True)
            pulse_scrollbar.config(command=self.gui.pulse_history_text.yview)
            
            # Initialize with empty message
            self.gui.pulse_history_text.config(state='normal')
            self.gui.pulse_history_text.insert('1.0', "No pulses recorded yet.\n")
            self.gui.pulse_history_text.config(state='disabled')
        
        self.plot_frames["pulse_table"] = frame_pulse_table
    
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
    
    def _create_graph_terminal(self, parent: tk.Misc) -> None:
        """Create a terminal widget at the bottom to show graph activity
        
        Note: This method detects whether the parent uses grid or pack layout
        and uses the appropriate geometry manager.
        """
        terminal_frame = tk.LabelFrame(
            parent,
            text="Graph Activity Log",
            font=("Segoe UI", 9, "bold"),
            bg='white',
            padx=5,
            pady=5
        )
        
        # Check if parent uses grid by checking for grid slaves
        uses_grid = False
        try:
            slaves = parent.grid_slaves()
            if slaves:
                uses_grid = True
        except:
            pass
        
        # Use appropriate geometry manager based on parent
        if uses_grid:
            # Parent uses grid - need to find the right row
            # For Graphing tab: tab has row 0 (title), row 1 (content_frame)
            # So terminal should go at row 2 of the tab
            try:
                # Check what rows are already used
                max_row = -1
                for child in parent.winfo_children():
                    try:
                        grid_info = child.grid_info()
                        row = grid_info.get('row', -1)
                        if isinstance(row, (int, str)) and str(row).isdigit():
                            max_row = max(max_row, int(row))
                    except:
                        pass
                
                # Add terminal at the next row after the highest used row
                terminal_row = max_row + 1
                terminal_frame.grid(row=terminal_row, column=0, sticky="ew", padx=10, pady=(10, 10))
                parent.rowconfigure(terminal_row, weight=0)  # Terminal row doesn't expand
            except Exception as e:
                # Fallback: try row 2 (for Graphing tab structure)
                try:
                    terminal_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(10, 10))
                    parent.rowconfigure(2, weight=0)
                except:
                    # Last resort: use pack (might fail but worth trying)
                    terminal_frame.pack(side='bottom', fill='x', padx=10, pady=(0, 10))
        else:
            # Parent uses pack - use pack
            terminal_frame.pack(side='bottom', fill='x', padx=10, pady=(0, 10))
        
        # Create text widget with scrollbar (always use pack inside terminal_frame)
        text_frame = tk.Frame(terminal_frame, bg='white')
        text_frame.pack(fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.graph_terminal = tk.Text(
            text_frame,
            font=("Consolas", 8),
            bg='#1e1e1e',  # Dark background
            fg='#d4d4d4',  # Light text
            wrap='word',
            relief='solid',
            borderwidth=1,
            padx=8,
            pady=8,
            height=4,  # Small height
            yscrollcommand=scrollbar.set,
            state='disabled'  # Read-only
        )
        self.graph_terminal.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.graph_terminal.yview)
        self.graph_terminal_scrollbar = scrollbar
        
        # Add initial message
        self.log_graph_activity("Graph Activity Log - Ready for sample analysis operations")
    
    def log_graph_activity(self, message: str) -> None:
        """Log a message to the graph activity terminal"""
        if not self.graph_terminal:
            return
        
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}\n"
            
            self.graph_terminal.config(state='normal')
            self.graph_terminal.insert('end', formatted_message)
            self.graph_terminal.see('end')  # Auto-scroll to bottom
            self.graph_terminal.config(state='disabled')
            
            # Limit to last 100 lines to prevent memory issues
            lines = self.graph_terminal.get('1.0', 'end').split('\n')
            if len(lines) > 100:
                self.graph_terminal.config(state='normal')
                self.graph_terminal.delete('1.0', f'{len(lines) - 100}.0')
                self.graph_terminal.config(state='disabled')
        except Exception:
            pass  # Don't crash if terminal logging fails
    
    def update_stats_panel(self, analysis_data: Dict[str, Any], analysis_level: str = "full") -> None:
        """
        Update the stats panel text widget with analysis data.
        
        Parameters:
        -----------
        analysis_data : dict
            Analysis data from IVSweepAnalyzer.analyze_sweep()
        analysis_level : str
            Analysis level: 'basic', 'classification', 'full', or 'research'
        """
        if not hasattr(self, 'stats_text') or not self.stats_text:
            return
        
        # Clear existing content
        self.stats_text.delete('1.0', tk.END)
        
        # Format stats based on analysis level
        lines = []
        
        # Device Info
        device_info = analysis_data.get('device_info', {})
        lines.append("=== Device Information ===")
        lines.append(f"Device: {device_info.get('name', 'N/A')}")
        lines.append(f"Type: {device_info.get('measurement_type', 'N/A')}")
        lines.append(f"Loops: {device_info.get('num_loops', 0)}")
        lines.append(f"Analysis Level: {analysis_level.upper()}")
        lines.append("")
        
        # Resistance Metrics
        res_metrics = analysis_data.get('resistance_metrics', {})
        lines.append("=== Resistance Metrics ===")
        lines.append(f"Ron (mean): {self._format_stat_value(res_metrics.get('ron_mean', 0), 'Ω')}")
        lines.append(f"Ron (std): {self._format_stat_value(res_metrics.get('ron_std', 0), 'Ω')}")
        lines.append(f"Roff (mean): {self._format_stat_value(res_metrics.get('roff_mean', 0), 'Ω')}")
        lines.append(f"Roff (std): {self._format_stat_value(res_metrics.get('roff_std', 0), 'Ω')}")
        lines.append(f"Switching Ratio: {self._format_stat_value(res_metrics.get('switching_ratio_mean', 0))}")
        lines.append(f"ON/OFF Ratio: {self._format_stat_value(res_metrics.get('on_off_ratio_mean', 0))}")
        lines.append("")
        
        # Voltage Metrics
        volt_metrics = analysis_data.get('voltage_metrics', {})
        lines.append("=== Voltage Metrics ===")
        lines.append(f"Von (mean): {self._format_stat_value(volt_metrics.get('von_mean', 0), 'V')}")
        lines.append(f"Voff (mean): {self._format_stat_value(volt_metrics.get('voff_mean', 0), 'V')}")
        lines.append(f"Max Voltage: {self._format_stat_value(volt_metrics.get('max_voltage', 0), 'V')}")
        lines.append("")
        
        # Hysteresis
        hyst_metrics = analysis_data.get('hysteresis_metrics', {})
        lines.append("=== Hysteresis ===")
        lines.append(f"Normalized Area: {self._format_stat_value(hyst_metrics.get('normalized_area_mean', 0))}")
        lines.append(f"Has Hysteresis: {'Yes' if hyst_metrics.get('has_hysteresis', False) else 'No'}")
        lines.append(f"Pinched: {'Yes' if hyst_metrics.get('pinched_hysteresis', False) else 'No'}")
        lines.append("")
        
        # Classification (if available)
        if analysis_level in ['classification', 'full', 'research']:
            class_data = analysis_data.get('classification', {})
            lines.append("=== Classification ===")
            lines.append(f"Device Type: {class_data.get('device_type', 'N/A')}")
            lines.append(f"Confidence: {self._format_stat_value(class_data.get('confidence', 0) * 100, '%', 1)}")
            
            # === ENHANCED: Memristivity Score ===
            memristivity_score = class_data.get('memristivity_score')
            if memristivity_score is not None:
                lines.append(f"Memristivity Score: {self._format_stat_value(memristivity_score, '/100', 1)}")
            
            lines.append(f"Conduction: {class_data.get('conduction_mechanism', 'N/A')}")
            if class_data.get('model_r2', 0) > 0:
                lines.append(f"Model R²: {self._format_stat_value(class_data.get('model_r2', 0), '', 3)}")
            lines.append("")
            
            # === ENHANCED: Memory Window Quality ===
            mw_quality = class_data.get('memory_window_quality', {})
            if mw_quality and mw_quality.get('available', True) and mw_quality.get('overall_quality_score'):
                lines.append("=== Memory Window Quality ===")
                lines.append(f"Quality Score: {self._format_stat_value(mw_quality.get('overall_quality_score', 0), '/100', 1)}")
                if 'avg_stability' in mw_quality:
                    lines.append(f"Stability: {self._format_stat_value(mw_quality.get('avg_stability', 0), '/100', 1)}")
                if 'separation_ratio' in mw_quality:
                    lines.append(f"Separation: {self._format_stat_value(mw_quality.get('separation_ratio', 0), '', 2)}")
                if 'reproducibility_score' in mw_quality:
                    lines.append(f"Reproducibility: {self._format_stat_value(mw_quality.get('reproducibility_score', 0), '/100', 1)}")
                lines.append("")
            
            # === ENHANCED: Hysteresis Shape Analysis ===
            hyst_shape = class_data.get('hysteresis_shape', {})
            if hyst_shape.get('has_hysteresis') and hyst_shape.get('figure_eight_quality'):
                lines.append("=== Hysteresis Shape ===")
                if 'figure_eight_quality' in hyst_shape:
                    lines.append(f"Figure-8 Quality: {self._format_stat_value(hyst_shape.get('figure_eight_quality', 0), '/100', 1)}")
                if 'lobe_asymmetry' in hyst_shape:
                    lines.append(f"Lobe Asymmetry: {self._format_stat_value(hyst_shape.get('lobe_asymmetry', 0), '', 3)}")
                if 'smoothness' in hyst_shape:
                    lines.append(f"Smoothness: {self._format_stat_value(hyst_shape.get('smoothness', 0), '/100', 1)}")
                lines.append("")
            
            # === ENHANCED: Warnings ===
            warnings = class_data.get('warnings', [])
            if warnings and len(warnings) > 0:
                lines.append("=== ⚠ Warnings ===")
                for warning in warnings[:5]:  # Show first 5 warnings
                    lines.append(f"• {warning}")
                lines.append("")
        
        # Performance (if available)
        if analysis_level in ['full', 'research']:
            perf_metrics = analysis_data.get('performance_metrics', {})
            lines.append("=== Performance ===")
            lines.append(f"Retention Score: {self._format_stat_value(perf_metrics.get('retention_score', 0), '', 3)}")
            lines.append(f"Endurance Score: {self._format_stat_value(perf_metrics.get('endurance_score', 0), '', 3)}")
            lines.append(f"Rectification: {self._format_stat_value(perf_metrics.get('rectification_ratio_mean', 1))}")
            lines.append(f"Non-linearity: {self._format_stat_value(perf_metrics.get('nonlinearity_mean', 0))}")
            if perf_metrics.get('power_consumption_mean', 0) > 0:
                lines.append(f"Power: {self._format_stat_value(perf_metrics.get('power_consumption_mean', 0), 'W')}")
            if perf_metrics.get('compliance_current') is not None:
                lines.append(f"Compliance: {self._format_stat_value(perf_metrics.get('compliance_current', 0), 'μA')}")
            lines.append("")
        
        # Research Diagnostics (if available)
        if analysis_level == 'research':
            research_data = analysis_data.get('research_diagnostics', {})
            if research_data:
                lines.append("=== Research Diagnostics ===")
                if research_data.get('switching_polarity'):
                    lines.append(f"Polarity: {research_data.get('switching_polarity', 'N/A')}")
                if research_data.get('ndr_index') is not None:
                    lines.append(f"NDR Index: {self._format_stat_value(research_data.get('ndr_index', 0))}")
                if research_data.get('hysteresis_direction'):
                    lines.append(f"Hyst. Direction: {research_data.get('hysteresis_direction', 'N/A')}")
                if research_data.get('loop_similarity_score') is not None:
                    lines.append(f"Loop Similarity: {self._format_stat_value(research_data.get('loop_similarity_score', 0), '', 3)}")
                if research_data.get('noise_floor') is not None:
                    lines.append(f"Noise Floor: {self._format_stat_value(research_data.get('noise_floor', 0), 'A')}")
                lines.append("")
        
        # Metadata (if available)
        metadata = device_info.get('metadata', {})
        if metadata:
            lines.append("=== Metadata ===")
            if metadata.get('led_on') is not None:
                lines.append(f"LED: {'ON' if metadata.get('led_on') else 'OFF'}")
            if metadata.get('led_type'):
                lines.append(f"LED Type: {metadata.get('led_type', 'N/A')}")
            if metadata.get('temperature') is not None:
                lines.append(f"Temperature: {self._format_stat_value(metadata.get('temperature', 0), '°C', 1)}")
            if metadata.get('humidity') is not None:
                lines.append(f"Humidity: {self._format_stat_value(metadata.get('humidity', 0), '%', 1)}")
        
        # Insert all lines (enable first, then disable)
        self.stats_text.config(state='normal')
        self.stats_text.delete('1.0', tk.END)
        self.stats_text.insert('1.0', '\n'.join(lines))
        self.stats_text.config(state='disabled')  # Make read-only
    
    def _format_stat_value(self, value: Any, unit: str = "", precision: int = 3) -> str:
        """Format a numeric value for display in stats panel"""
        if value is None:
            return "N/A"
        
        try:
            if isinstance(value, (int, float)):
                if abs(value) >= 1e6:
                    return f"{value/1e6:.{precision}f} M{unit}"
                elif abs(value) >= 1e3:
                    return f"{value/1e3:.{precision}f} k{unit}"
                elif abs(value) < 1e-3 and abs(value) > 0:
                    return f"{value*1e6:.{precision}f} μ{unit}"
                elif abs(value) < 1e-6 and abs(value) > 0:
                    return f"{value*1e9:.{precision}f} n{unit}"
                else:
                    return f"{value:.{precision}f} {unit}".strip()
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value) if value is not None else "N/A"
    
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
    
    def update_endurance_plot(self, ratios: List[float]) -> None:
        """Update endurance plot with new data"""
        if "endurance" not in self.axes:
            return
        
        self.endurance_ratios = ratios if ratios else []
        ax = self.axes["endurance"]
        canvas = self.canvases["endurance"]
        
        ax.clear()
        ax.set_title("Endurance (ON/OFF)")
        ax.set_xlabel("Cycle")
        ax.set_ylabel("ON/OFF Ratio")
        
        if self.endurance_ratios:
            ax.plot(
                range(1, len(self.endurance_ratios) + 1),
                self.endurance_ratios,
                marker="o",
                linestyle="-",
                linewidth=1.5,
                markersize=5
            )
            ax.grid(True, alpha=0.3)
            ax.relim()
            ax.autoscale()
        
        canvas.draw()
    
    def update_endurance_current_plot(
        self, 
        on_times: List[float], 
        on_currents: List[float],
        off_times: List[float],
        off_currents: List[float]
    ) -> None:
        """Update endurance current plot with ON and OFF currents over time"""
        if "endurance_current" not in self.axes:
            return
        
        self.endurance_on_times = on_times if on_times else []
        self.endurance_on_currents = on_currents if on_currents else []
        self.endurance_off_times = off_times if off_times else []
        self.endurance_off_currents = off_currents if off_currents else []
        
        ax = self.axes["endurance_current"]
        canvas = self.canvases["endurance_current"]
        
        ax.clear()
        ax.set_title("Endurance Current (ON/OFF)")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Current (A)")
        ax.set_yscale("log")
        
        # Plot ON currents
        if self.endurance_on_times and self.endurance_on_currents and len(self.endurance_on_times) == len(self.endurance_on_currents):
            # Filter out zeros and negative values for log scale
            valid_on_indices = [i for i in range(len(self.endurance_on_times))
                              if self.endurance_on_times[i] > 0 and self.endurance_on_currents[i] > 0]
            if valid_on_indices:
                valid_on_times = [self.endurance_on_times[i] for i in valid_on_indices]
                valid_on_currents = [self.endurance_on_currents[i] for i in valid_on_indices]
                ax.plot(
                    valid_on_times,
                    valid_on_currents,
                    marker="o",
                    linestyle="-",
                    linewidth=1.5,
                    markersize=4,
                    label="ON Current",
                    color="green"
                )
        
        # Plot OFF currents
        if self.endurance_off_times and self.endurance_off_currents and len(self.endurance_off_times) == len(self.endurance_off_currents):
            # Filter out zeros and negative values for log scale
            valid_off_indices = [i for i in range(len(self.endurance_off_times))
                                if self.endurance_off_times[i] > 0 and self.endurance_off_currents[i] > 0]
            if valid_off_indices:
                valid_off_times = [self.endurance_off_times[i] for i in valid_off_indices]
                valid_off_currents = [self.endurance_off_currents[i] for i in valid_off_indices]
                ax.plot(
                    valid_off_times,
                    valid_off_currents,
                    marker="s",
                    linestyle="-",
                    linewidth=1.5,
                    markersize=4,
                    label="OFF Current",
                    color="red"
                )
        
        if self.endurance_on_times or self.endurance_off_times:
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.relim()
            ax.autoscale()
        
        canvas.draw()
    
    def update_retention_plot(self, times: List[float], currents: List[float]) -> None:
        """Update retention plot with new data"""
        if "retention" not in self.axes:
            return
        
        self.retention_times = times if times else []
        self.retention_currents = currents if currents else []
        ax = self.axes["retention"]
        canvas = self.canvases["retention"]
        
        ax.clear()
        ax.set_title("Retention")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Current (A)")
        ax.set_xscale("log")
        ax.set_yscale("log")
        
        if self.retention_times and self.retention_currents and len(self.retention_times) == len(self.retention_currents):
            # Filter out zeros and negative values for log scale
            valid_indices = [i for i in range(len(self.retention_times)) 
                           if self.retention_times[i] > 0 and self.retention_currents[i] > 0]
            if valid_indices:
                valid_times = [self.retention_times[i] for i in valid_indices]
                valid_currents = [self.retention_currents[i] for i in valid_indices]
                ax.plot(
                    valid_times,
                    valid_currents,
                    marker="x",
                    linestyle="-",
                    linewidth=1.5,
                    markersize=5
                )
            ax.grid(True, alpha=0.3)
            ax.relim()
            ax.autoscale()
        
        canvas.draw()
    
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
        
        # Create red dots for most recent values (legacy plots)
        if "rt_iv" not in self.recent_dots:
            recent_dot_iv, = ax_iv.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
            self.recent_dots["rt_iv"] = recent_dot_iv
        if "rt_logiv" not in self.recent_dots:
            recent_dot_log, = ax_log.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
            self.recent_dots["rt_logiv"] = recent_dot_log

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
        # Create red dot for most recent value (legacy plot)
        recent_dot_logilogv, = ax_logilogv.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
        self._register("rt_logilogv", fig_logilogv, ax_logilogv, canvas_logilogv, line_logilogv)
        self.recent_dots["rt_logilogv"] = recent_dot_logilogv

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

        # Add endurance current ON/OFF over time plot
        fig_end_curr, ax_end_curr = self._make_figure(title="Endurance Current (ON/OFF)", figsize=(3, 2))
        ax_end_curr.set_yscale("log")
        self._style_axis(ax_end_curr, "Time (s)", "Current (A)")
        canvas_end_curr = FigureCanvasTkAgg(fig_end_curr, master=frame)
        canvas_end_curr.get_tk_widget().grid(row=1, column=0, columnspan=2, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        self.endurance_ratios: List[float] = []
        self.retention_times: List[float] = []
        self.retention_currents: List[float] = []
        
        # Track ON and OFF currents with timestamps for endurance
        self.endurance_on_times: List[float] = []
        self.endurance_on_currents: List[float] = []
        self.endurance_off_times: List[float] = []
        self.endurance_off_currents: List[float] = []

        self._register("endurance", fig_end, ax_end, canvas_end, None)
        self._register("retention", fig_ret, ax_ret, canvas_ret, None)
        self._register("endurance_current", fig_end_curr, ax_end_curr, canvas_end_curr, None)

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
        # Create red dot for most recent value (legacy plot)
        recent_dot_ct, = ax_ct.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
        self._register("ct_rt", fig_ct, ax_ct, canvas_ct, line_ct)
        self.recent_dots["ct_rt"] = recent_dot_ct

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
            # Create red dot for most recent value (legacy plot)
            recent_dot_tt, = ax_tt.plot([], [], marker="o", color="red", markersize=8, linestyle="None", zorder=10)
            self._register("tt_rt", fig_tt, ax_tt, canvas_tt, line_tt)
            self.recent_dots["tt_rt"] = recent_dot_tt
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
            # Log activity
            self.log_graph_activity(f"Added sweep to 'All Sweeps': {label} ({len(v_arr)} points)")

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
        for name in ["endurance_ratios", "retention_times", "retention_currents", 
                     "endurance_on_times", "endurance_on_currents", 
                     "endurance_off_times", "endurance_off_currents"]:
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

