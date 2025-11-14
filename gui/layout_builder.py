"""
Tkinter layout construction helpers.
===================================

`MeasurementGUILayoutBuilder` encapsulates the Tkinter widget construction that
used to live inside `Measurement_GUI.py`.  By injecting the GUI instance we can
populate the same attributes (Tk variables, widgets) without leaving the main
class cluttered with layout code.

This version features a modernized Sample_GUI inspired design with:
- Tabbed notebook interface (ttk.Notebook)
- Sample_GUI color scheme and fonts (Segoe UI, #4CAF50 accents)
- LEFT controls panel with collapsible sections
- RIGHT large graph display area
- Top control bar with system selector and utility buttons
- Bottom status bar
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

import tkinter as tk
from tkinter import ttk, messagebox


@dataclass
class MeasurementGUILayoutBuilder:
    gui: object
    callbacks: Dict[str, Callable]
    widgets: Dict[str, tk.Widget] = field(default_factory=dict)
    
    # Sample_GUI color scheme
    COLOR_PRIMARY = "#4CAF50"  # Green for buttons/accents
    COLOR_SECONDARY = "#888888"  # Gray for secondary text
    COLOR_BG = "#f0f0f0"  # Light grey background
    COLOR_BG_INFO = "#f0f0f0"  # Light gray for info boxes
    COLOR_SUCCESS = "#4CAF50"  # Green for success states
    COLOR_ERROR = "#F44336"  # Red for error states
    COLOR_WARNING = "#FFA500"  # Orange for warnings
    COLOR_INFO = "#569CD6"  # Blue for info
    
    # Fonts (Sample_GUI style)
    FONT_MAIN = ("Segoe UI", 9)
    FONT_HEADING = ("Segoe UI", 10, "bold")
    FONT_LARGE = ("Segoe UI", 12, "bold")
    FONT_BUTTON = ("Segoe UI", 9, "bold")

    def build_all_panels(
        self,
        left_frame: tk.Misc,
        middle_frame: tk.Misc,
        top_frame: Optional[tk.Misc] = None,
    ) -> None:
        """Legacy compatibility - redirect to new tabbed structure"""
        # For backwards compatibility, we still accept these frames but will
        # replace them with the new tabbed structure
        pass
    
    def build_modern_layout(self, master_window: tk.Misc) -> None:
        """
        Build the new modern tabbed layout with Sample_GUI styling.
        This is the main entry point for the new design.
        """
        gui = self.gui
        
        # Configure master window
        master_window.title("IV Measurement System")
        master_window.geometry("1920x1080")
        master_window.configure(bg=self.COLOR_BG)  # Light grey background like Sample_GUI
        
        # Configure grid weights for responsive layout
        master_window.columnconfigure(0, weight=1)
        master_window.rowconfigure(0, weight=0)  # Top bar - fixed height
        master_window.rowconfigure(1, weight=1)  # Main content - expands
        master_window.rowconfigure(2, weight=0)  # Status bar - fixed height
        
        # Build the three main sections
        self._build_top_control_bar(master_window)
        self._build_tabbed_content(master_window)
        self._build_bottom_status_bar(master_window)
    
    # ------------------------------------------------------------------
    # Top Control Bar (System selector, utility buttons)
    # ------------------------------------------------------------------
    def _build_top_control_bar(self, parent: tk.Misc) -> None:
        """Create the top control bar with system dropdown and utility buttons"""
        gui = self.gui
        
        frame = tk.Frame(parent, bg=self.COLOR_BG, height=60)
        frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        frame.grid_propagate(False)
        
        # Left side: System selector
        left_section = tk.Frame(frame, bg=self.COLOR_BG)
        left_section.pack(side='left', fill='y')
        
        tk.Label(left_section, text="System:", font=self.FONT_HEADING, bg=self.COLOR_BG).pack(side='left', padx=(0, 5))
        
        gui.systems = gui.load_systems()
        gui.system_var = tk.StringVar()
        system_dropdown = ttk.Combobox(
            left_section,
            textvariable=gui.system_var,
            values=gui.systems,
            state="readonly",
            font=self.FONT_MAIN,
            width=25
        )
        system_dropdown.pack(side='left', padx=5)
        system_dropdown.bind("<<ComboboxSelected>>", lambda e: self._on_system_change_and_connect())
        gui.system_dropdown = system_dropdown
        
        # Connection status indicator
        gui.connection_status_label = tk.Label(
            left_section,
            text="● Disconnected",
            font=self.FONT_MAIN,
            fg=self.COLOR_ERROR,
            bg=self.COLOR_BG
        )
        gui.connection_status_label.pack(side='left', padx=10)
        
        # Middle section: Current device display
        middle_section = tk.Frame(frame, bg=self.COLOR_BG)
        middle_section.pack(side='left', fill='y', padx=20)
        
        device_info_frame = tk.Frame(middle_section, bg='#e8f5e9', relief='solid', borderwidth=1, padx=12, pady=4)
        device_info_frame.pack(side='left')
        
        tk.Label(device_info_frame, text="Device:", font=("Segoe UI", 9), bg='#e8f5e9', fg='#2e7d32').pack(side='left', padx=(0, 5))
        gui.device_var = tk.Label(
            device_info_frame,
            text=getattr(gui, "display_index_section_number", "A1"),
            font=("Segoe UI", 9, "bold"),
            bg='#e8f5e9',
            fg='#1b5e20'
        )
        gui.device_var.pack(side='left')
        
        # Right side: Utility buttons
        right_section = tk.Frame(frame, bg=self.COLOR_BG)
        right_section.pack(side='right', fill='y')
        
        # Motor Control button
        motor_btn = tk.Button(
            right_section,
            text="Motor Control",
            font=self.FONT_BUTTON,
            command=self.callbacks.get("open_motor_control"),
            bg='#2196f3',  # Blue
            fg='white',
            activebackground='#1976d2',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            padx=12,
            pady=6
        )
        motor_btn.pack(side='left', padx=5)
        gui.motor_control_button = motor_btn
        
        # Check Connection button
        check_btn = tk.Button(
            right_section,
            text="Check Connection",
            font=self.FONT_BUTTON,
            command=self.callbacks.get("check_connection"),
            bg='#2196f3',  # Blue
            fg='white',
            activebackground='#1976d2',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            padx=12,
            pady=6
        )
        check_btn.pack(side='left', padx=5)
        gui.check_connection_button = check_btn
        
        # Pulse Testing button (opens TSP GUI)
        pulse_btn = tk.Button(
            right_section,
            text="Pulse Testing",
            font=self.FONT_BUTTON,
            command=lambda: self._open_pulse_testing(),
            bg=self.COLOR_BG,
            relief='raised',
            padx=10,
            pady=5
        )
        pulse_btn.pack(side='left', padx=5)
        gui.pulse_testing_button = pulse_btn
        
        self.widgets["top_control_bar"] = frame
    
    def _on_system_change_and_connect(self) -> None:
        """Handle system change and attempt auto-connect"""
        # First call the existing system change callback
        system_change_cb = self.callbacks.get("on_system_change")
        if system_change_cb:
            system_change_cb(self.gui.system_var.get())
        
        # Then attempt to auto-connect
        self._auto_connect_instruments()
    
    def _auto_connect_instruments(self) -> None:
        """Automatically connect to instruments after system selection"""
        gui = self.gui
        
        # Update status to connecting
        if hasattr(gui, 'connection_status_label'):
            gui.connection_status_label.config(text="● Connecting...", fg=self.COLOR_WARNING)
            gui.master.update()
        
        # Connect Keithley/SMU
        connect_keithley_cb = self.callbacks.get("connect_keithley")
        if connect_keithley_cb:
            try:
                connect_keithley_cb()
            except Exception as e:
                print(f"Auto-connect Keithley failed: {e}")
        
        # Connect PSU if needed
        if hasattr(gui, 'psu_needed') and gui.psu_needed:
            connect_psu_cb = self.callbacks.get("connect_psu")
            if connect_psu_cb:
                try:
                    connect_psu_cb()
                except Exception as e:
                    print(f"Auto-connect PSU failed: {e}")
        
        # Connect Temp Controller if needed
        connect_temp_cb = self.callbacks.get("connect_temp")
        if connect_temp_cb and hasattr(gui, 'temp_controller_address'):
            try:
                connect_temp_cb()
            except Exception as e:
                print(f"Auto-connect Temp failed: {e}")
        
        # Update status based on connection success
        if hasattr(gui, 'connection_status_label'):
            if hasattr(gui, 'connected') and gui.connected:
                gui.connection_status_label.config(text="● Connected", fg=self.COLOR_SUCCESS)
            else:
                gui.connection_status_label.config(text="● Connection Failed", fg=self.COLOR_ERROR)
    
    def _open_pulse_testing(self) -> None:
        """Open the TSP/Pulse Testing GUI"""
        try:
            from TSP_Testing_GUI import TSPTestingGUI
            TSPTestingGUI(self.gui.master)
        except Exception as e:
            print(f"Failed to open Pulse Testing GUI: {e}")
            messagebox.showerror("Error", f"Could not open Pulse Testing GUI:\n{e}")
    
    # ------------------------------------------------------------------
    # Tabbed Content Area
    # ------------------------------------------------------------------
    def _build_tabbed_content(self, parent: tk.Misc) -> None:
        """Create the main tabbed notebook"""
        gui = self.gui
        
        # Create notebook (tabbed interface)
        notebook = ttk.Notebook(parent)
        notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        gui.main_notebook = notebook
        
        # Create tabs
        self._create_measurements_tab(notebook)
        self._create_advanced_tests_tab(notebook)
        self._create_setup_tab(notebook)
        self._create_custom_measurements_tab(notebook)
        
        self.widgets["notebook"] = notebook
    
    # ------------------------------------------------------------------
    # TAB 1: Measurements (Main tab)
    # ------------------------------------------------------------------
    def _create_measurements_tab(self, notebook: ttk.Notebook) -> None:
        """
        Create the main Measurements tab with:
        - LEFT: Control panels (collapsible)
        - RIGHT: Large graph display area
        """
        gui = self.gui
        
        tab = tk.Frame(notebook, bg=self.COLOR_BG)
        notebook.add(tab, text="  Measurements  ")
        
        # Configure grid: LEFT column (controls), RIGHT column (graphs)
        tab.columnconfigure(0, weight=0, minsize=400)  # LEFT panel - fixed width
        tab.columnconfigure(1, weight=1)  # RIGHT panel - expands
        tab.rowconfigure(0, weight=1)
        
        # LEFT PANEL - Controls (scrollable)
        left_panel = self._create_scrollable_panel(tab)
        # Grid the container (not the scrollable_frame itself)
        left_panel._container.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        
        # Build collapsible sections in LEFT panel (add to scrollable_frame)
        self._build_mode_selection_modern(left_panel)
        self._build_sweep_parameters_collapsible(left_panel)
        self._build_sequential_controls_collapsible(left_panel)
        self._build_custom_measurement_quick_select(left_panel)
        self._build_telegram_bot_collapsible(left_panel)
        
        # RIGHT PANEL - Graphs (will be populated by plot_panels)
        right_panel = tk.Frame(tab, bg=self.COLOR_BG)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)
        
        # Store right panel for graph attachment
        gui.measurements_graph_panel = right_panel
        
        self.widgets["measurements_tab"] = tab
        self.widgets["measurements_left_panel"] = left_panel
        self.widgets["measurements_right_panel"] = right_panel
    
    def _create_scrollable_panel(self, parent: tk.Misc) -> tk.Frame:
        """Create a scrollable frame for control panels
        
        Returns the scrollable_frame that widgets should be added to.
        The container frame (with canvas and scrollbar) is stored as an attribute
        and should be gridded/packed by the caller.
        """
        # Create container frame to hold canvas and scrollbar
        container = tk.Frame(parent, bg=self.COLOR_BG)
        
        # Create canvas and scrollbar inside container
        canvas = tk.Canvas(container, bg=self.COLOR_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.COLOR_BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar into container (not parent)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Store container reference in scrollable_frame for caller to grid
        scrollable_frame._container = container
        
        return scrollable_frame
    
    def _build_mode_selection_modern(self, parent: tk.Misc) -> None:
        """Mode selection section with modern collapsible styling"""
        gui = self.gui
        
        container = tk.Frame(parent, bg=self.COLOR_BG)
        container.pack(fill='x', padx=5, pady=5)
        
        # Header with consistent theme
        header_frame = tk.Frame(container, bg='#e3f2fd', relief='raised', borderwidth=1, cursor='hand2')
        header_frame.pack(fill='x')
        
        is_expanded = tk.BooleanVar(value=False)  # Start collapsed
        arrow_label = tk.Label(header_frame, text="►", bg='#e3f2fd', font=self.FONT_HEADING, fg='#1976d2')
        arrow_label.pack(side='left', padx=8)
        
        tk.Label(header_frame, text="Sample & Save Settings", font=self.FONT_HEADING, bg='#e3f2fd', fg='#1565c0').pack(side='left', pady=8)
        
        # Content frame - start hidden (collapsed)
        content_frame = tk.Frame(container, bg=self.COLOR_BG, relief='solid', borderwidth=1, padx=12, pady=12)
        # Don't pack initially - it's collapsed
        
        def toggle_collapse():
            if is_expanded.get():
                content_frame.pack_forget()
                arrow_label.config(text="►")
                is_expanded.set(False)
            else:
                content_frame.pack(fill='x')
                arrow_label.config(text="▼")
                is_expanded.set(True)
        
        header_frame.bind("<Button-1>", lambda e: toggle_collapse())
        arrow_label.bind("<Button-1>", lambda e: toggle_collapse())
        
        # Single device mode with styled checkbox
        checkbox_frame = tk.Frame(content_frame, bg=self.COLOR_BG)
        checkbox_frame.pack(fill='x', pady=(0, 12))
        
        gui.adaptive_var = tk.IntVar(value=1)
        cb_label_frame = tk.Frame(checkbox_frame, bg='#e8f5e9', relief='solid', borderwidth=1, padx=10, pady=6)
        cb_label_frame.pack(fill='x')
        
        ttk.Checkbutton(
            cb_label_frame,
            text="Measure One Device",
            variable=gui.adaptive_var,
            command=self.callbacks.get("measure_one_device")
        ).pack(side='left')
        
        tk.Label(cb_label_frame, text="(Single device mode)", font=("Segoe UI", 8), bg='#e8f5e9', fg='#2e7d32').pack(side='left', padx=(10, 0))
        
        # Sample Name
        tk.Label(content_frame, text="Sample Name:", font=self.FONT_MAIN, bg=self.COLOR_BG, fg='#424242').pack(anchor='w', pady=(0, 2))
        
        gui.sample_name_var = tk.StringVar()
        # Auto-populate from Sample_GUI's current_device_name if available
        if hasattr(gui, 'sample_gui') and gui.sample_gui and hasattr(gui.sample_gui, 'current_device_name'):
            device_name = getattr(gui.sample_gui, 'current_device_name', None)
            if device_name:
                gui.sample_name_var.set(device_name)
        gui.sample_name_entry = ttk.Entry(content_frame, textvariable=gui.sample_name_var, font=self.FONT_MAIN)
        gui.sample_name_entry.pack(fill='x', pady=(0, 10))
        
        # Additional Info
        tk.Label(content_frame, text="Additional Info:", font=self.FONT_MAIN, bg=self.COLOR_BG, fg='#424242').pack(anchor='w', pady=(0, 2))
        
        gui.additional_info_var = tk.StringVar()
        gui.additional_info_entry = ttk.Entry(content_frame, textvariable=gui.additional_info_var, font=self.FONT_MAIN)
        gui.additional_info_entry.pack(fill='x', pady=(0, 10))
        
        # Separator
        ttk.Separator(content_frame, orient='horizontal').pack(fill='x', pady=10)
        
        # Custom save location with styled checkbox
        gui.use_custom_save_var = tk.BooleanVar(value=False)
        gui.custom_save_location_var = tk.StringVar(value="")
        gui.custom_save_location = None
        
        tk.Checkbutton(
            content_frame,
            text="Use custom save location",
            variable=gui.use_custom_save_var,
            command=self.callbacks.get("on_custom_save_toggle"),
            bg=self.COLOR_BG,
            font=self.FONT_MAIN,
            fg='#424242'
        ).pack(anchor='w', pady=(0, 8))
        
        save_frame = tk.Frame(content_frame, bg=self.COLOR_BG)
        save_frame.pack(fill='x')
        save_frame.columnconfigure(0, weight=1)
        
        gui.save_path_entry = tk.Entry(
            save_frame,
            textvariable=gui.custom_save_location_var,
            state="disabled",
            font=self.FONT_MAIN,
            relief='solid',
            borderwidth=1
        )
        gui.save_path_entry.grid(row=0, column=0, sticky='ew', padx=(0, 8))
        
        browse_btn = tk.Button(
            save_frame,
            text="Browse...",
            command=self.callbacks.get("browse_save"),
            font=self.FONT_BUTTON,
            bg='#2196f3',
            fg='white',
            relief='raised',
            padx=12,
            pady=4,
            state="disabled"
        )
        browse_btn.grid(row=0, column=1)
        gui.save_browse_button = browse_btn
        
        # Load saved preferences
        if hasattr(gui, '_load_save_location_config'):
            gui._load_save_location_config()
        
        self.widgets["mode_selection"] = container
    
    def _build_sweep_parameters_collapsible(self, parent: tk.Misc) -> None:
        """Sweep parameters in a collapsible frame with improved styling"""
        gui = self.gui
        
        # Create collapsible container - use system default to match TSP Testing GUI
        container = tk.Frame(parent)
        container.pack(fill='x', padx=5, pady=5)
        
        # Collapsible header with consistent theme
        header_frame = tk.Frame(container, bg='#e3f2fd', relief='raised', borderwidth=1, cursor='hand2')
        header_frame.pack(fill='x')
        
        # Expand/collapse state
        is_expanded = tk.BooleanVar(value=True)
        arrow_label = tk.Label(header_frame, text="▼", bg='#e3f2fd', font=self.FONT_HEADING, fg='#1976d2')
        arrow_label.pack(side='left', padx=8)
        
        tk.Label(header_frame, text="⚡ Sweep Parameters", font=self.FONT_HEADING, bg='#e3f2fd', fg='#1565c0').pack(side='left', pady=8)
        
        # Content frame - no border/frame for seamless integration
        # Use grey background to match Sample_GUI (#f0f0f0)
        content_frame = tk.Frame(container, bg='#f0f0f0', padx=10, pady=10)
        content_frame.pack(fill='x')
        # Configure grid for sweep parameters that use grid layout
        content_frame.columnconfigure(1, weight=1)
        
        def toggle_collapse():
            if is_expanded.get():
                content_frame.pack_forget()
                arrow_label.config(text="►")
                is_expanded.set(False)
            else:
                content_frame.pack(fill='x')
                arrow_label.config(text="▼")
                is_expanded.set(True)
        
        header_frame.bind("<Button-1>", lambda e: toggle_collapse())
        arrow_label.bind("<Button-1>", lambda e: toggle_collapse())
        
        # Store reference for external population (will be called by create_sweep_parameters)
        gui.sweep_parameters_frame = content_frame
        
        self.widgets["sweep_parameters_collapsible"] = container
    
    def _build_sequential_controls_collapsible(self, parent: tk.Misc) -> None:
        """Sequential measurements in a collapsible frame"""
        gui = self.gui
        
        container = tk.Frame(parent, bg=self.COLOR_BG)
        container.pack(fill='x', padx=5, pady=5)
        
        # Header with consistent theme
        header_frame = tk.Frame(container, bg='#e3f2fd', relief='raised', borderwidth=1, cursor='hand2')
        header_frame.pack(fill='x')
        
        is_expanded = tk.BooleanVar(value=False)  # Collapsed by default
        arrow_label = tk.Label(header_frame, text="►", bg='#e3f2fd', font=self.FONT_HEADING, fg='#1976d2')
        arrow_label.pack(side='left', padx=8)
        
        tk.Label(header_frame, text="🔁 Sequential Measurements", font=self.FONT_HEADING, bg='#e3f2fd', fg='#1565c0').pack(side='left', pady=8)
        
        # Content
        content_frame = tk.Frame(container, bg=self.COLOR_BG, relief='solid', borderwidth=1, padx=10, pady=10)
        
        def toggle_collapse():
            if is_expanded.get():
                content_frame.pack_forget()
                arrow_label.config(text="►")
                is_expanded.set(False)
            else:
                content_frame.pack(fill='x')
                arrow_label.config(text="▼")
                is_expanded.set(True)
        
        header_frame.bind("<Button-1>", lambda e: toggle_collapse())
        arrow_label.bind("<Button-1>", lambda e: toggle_collapse())
        
        # Build sequential controls content
        self._populate_sequential_controls(content_frame)
        
        self.widgets["sequential_controls_collapsible"] = container
    
    def _populate_sequential_controls(self, parent: tk.Frame) -> None:
        """Populate sequential measurement controls"""
        gui = self.gui
        
        # Mode selector
        tk.Label(parent, text="Mode:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=2)
        existing_mode = getattr(gui, "Sequential_measurement_var", "Iv Sweep")
        if hasattr(existing_mode, "get"):
            existing_mode = existing_mode.get()
        gui.Sequential_measurement_var = tk.StringVar(value=existing_mode or "Iv Sweep")
        mode_menu = ttk.Combobox(
            parent,
            textvariable=gui.Sequential_measurement_var,
            values=["Iv Sweep", "Single Avg Measure"],
            state="readonly",
            font=self.FONT_MAIN,
            width=18
        )
        mode_menu.grid(row=0, column=1, sticky='ew', pady=2)
        
        # Number of passes
        tk.Label(parent, text="# Passes:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=1, column=0, sticky='w', pady=2)
        gui.sequential_number_of_sweeps = tk.IntVar(value=getattr(gui, "sequential_number_of_sweeps", 100))
        tk.Entry(parent, textvariable=gui.sequential_number_of_sweeps, font=self.FONT_MAIN, width=18).grid(row=1, column=1, sticky='w', pady=2)
        
        # Voltage limit
        tk.Label(parent, text="Voltage Limit (V):", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=2, column=0, sticky='w', pady=2)
        gui.sq_voltage = tk.DoubleVar(value=1.0)
        tk.Entry(parent, textvariable=gui.sq_voltage, font=self.FONT_MAIN, width=18).grid(row=2, column=1, sticky='w', pady=2)
        
        # Delay between passes
        tk.Label(parent, text="Delay (s):", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=3, column=0, sticky='w', pady=2)
        gui.sq_time_delay = tk.DoubleVar(value=1.0)
        tk.Entry(parent, textvariable=gui.sq_time_delay, font=self.FONT_MAIN, width=18).grid(row=3, column=1, sticky='w', pady=2)
        
        # Duration per device
        tk.Label(parent, text="Duration/Device (s):", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=4, column=0, sticky='w', pady=2)
        gui.measurement_duration_var = tk.DoubleVar(value=1.0)
        duration_entry = tk.Entry(parent, textvariable=gui.measurement_duration_var, font=self.FONT_MAIN, width=18)
        duration_entry.grid(row=4, column=1, sticky='w', pady=2)
        
        # Live plotting checkbox
        gui.live_plot_enabled = tk.BooleanVar(value=True)
        tk.Checkbutton(
            parent,
            text="Enable live plotting",
            variable=gui.live_plot_enabled,
            bg=self.COLOR_BG,
            font=self.FONT_MAIN
        ).grid(row=5, column=0, columnspan=2, sticky='w', pady=5)
        
        # Buttons with improved styling
        btn_frame = tk.Frame(parent, bg=self.COLOR_BG)
        btn_frame.grid(row=6, column=0, columnspan=2, sticky='ew', pady=5)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
        start_btn = tk.Button(
            btn_frame,
            text="Start Sequential",
            font=("Segoe UI", 10, "bold"),
            bg='#4CAF50',  # Green
            fg='white',
            activebackground='#388e3c',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            pady=8,
            command=self.callbacks.get("start_sequential_measurement")
        )
        start_btn.grid(row=0, column=0, sticky='ew', padx=(0, 3))
        
        stop_btn = tk.Button(
            btn_frame,
            text="Stop",
            font=("Segoe UI", 10, "bold"),
            bg='#f44336',  # Red
            fg='white',
            activebackground='#d32f2f',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            pady=8,
            command=self.callbacks.get("stop_sequential_measurement")
        )
        stop_btn.grid(row=0, column=1, sticky='ew', padx=(3, 0))
        
        parent.columnconfigure(1, weight=1)
    
    def _build_custom_measurement_quick_select(self, parent: tk.Misc) -> None:
        """Quick custom measurement selector (collapsible)"""
        gui = self.gui
        
        container = tk.Frame(parent, bg=self.COLOR_BG)
        container.pack(fill='x', padx=5, pady=5)
        
        # Header with consistent theme
        header_frame = tk.Frame(container, bg='#e3f2fd', relief='raised', borderwidth=1, cursor='hand2')
        header_frame.pack(fill='x')
        
        is_expanded = tk.BooleanVar(value=False)  # Collapsed by default
        arrow_label = tk.Label(header_frame, text="►", bg='#e3f2fd', font=self.FONT_HEADING, fg='#1976d2')
        arrow_label.pack(side='left', padx=8)
        
        tk.Label(header_frame, text="🔬 Custom Measurement", font=self.FONT_HEADING, bg='#e3f2fd', fg='#1565c0').pack(side='left', pady=8)
        
        # Content
        content_frame = tk.Frame(container, bg=self.COLOR_BG, relief='solid', borderwidth=1, padx=10, pady=10)
        
        def toggle_collapse():
            if is_expanded.get():
                content_frame.pack_forget()
                arrow_label.config(text="►")
                is_expanded.set(False)
            else:
                content_frame.pack(fill='x')
                arrow_label.config(text="▼")
                is_expanded.set(True)
        
        header_frame.bind("<Button-1>", lambda e: toggle_collapse())
        arrow_label.bind("<Button-1>", lambda e: toggle_collapse())
        
        # Content
        test_names = getattr(gui, "test_names", [])
        default_test = test_names[0] if test_names else "Test"
        gui.custom_measurement_var = tk.StringVar(value=default_test)
        
        tk.Label(content_frame, text="Select Test:", font=self.FONT_MAIN, bg=self.COLOR_BG).pack(anchor='w', pady=(0, 5))
        gui.custom_measurement_menu = ttk.Combobox(
            content_frame,
            textvariable=gui.custom_measurement_var,
            values=test_names,
            state="readonly" if test_names else "disabled",
            font=self.FONT_MAIN
        )
        gui.custom_measurement_menu.pack(fill='x', pady=(0, 10))
        
        # Run and edit buttons
        btn_frame = tk.Frame(content_frame, bg=self.COLOR_BG)
        btn_frame.pack(fill='x')
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
        gui.run_custom_button = tk.Button(
            btn_frame,
            text="Run Custom",
            font=("Segoe UI", 10, "bold"),
            bg='#4CAF50',  # Green (consistent with Start)
            fg='white',
            activebackground='#388e3c',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            pady=8,
            command=self.callbacks.get("start_custom_measurement_thread")
        )
        gui.run_custom_button.grid(row=0, column=0, sticky='ew', padx=(0, 3))
        
        edit_btn = tk.Button(
            btn_frame,
            text="Edit Sweeps",
            font=self.FONT_BUTTON,
            bg='#2196f3',  # Blue (consistent theme)
            fg='white',
            activebackground='#1976d2',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            pady=6,
            command=self.callbacks.get("open_sweep_editor")
        )
        edit_btn.grid(row=0, column=1, sticky='ew', padx=(3, 0))
        
        # Pause button
        gui.pause_button_custom = tk.Button(
            content_frame,
            text="Pause",
            font=self.FONT_BUTTON,
            bg='#ff9800',  # Orange (pause/warning color)
            fg='white',
            activebackground='#f57c00',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            pady=6,
            command=self.callbacks.get("toggle_custom_pause")
        )
        gui.pause_button_custom.pack(fill='x', pady=(5, 0))
        
        self.widgets["custom_measurement_quick"] = container
    
    def _build_telegram_bot_collapsible(self, parent: tk.Misc) -> None:
        """Telegram messaging section (collapsible)"""
        gui = self.gui
        
        container = tk.Frame(parent, bg=self.COLOR_BG)
        container.pack(fill='x', padx=5, pady=5)
        
        # Header with consistent theme
        header_frame = tk.Frame(container, bg='#e3f2fd', relief='raised', borderwidth=1, cursor='hand2')
        header_frame.pack(fill='x')
        
        is_expanded = tk.BooleanVar(value=False)  # Collapsed by default
        arrow_label = tk.Label(header_frame, text="►", bg='#e3f2fd', font=self.FONT_HEADING, fg='#1976d2')
        arrow_label.pack(side='left', padx=8)
        
        tk.Label(header_frame, text="📱 Telegram Messaging", font=self.FONT_HEADING, bg='#e3f2fd', fg='#1565c0').pack(side='left', pady=8)
        
        # Content
        content_frame = tk.Frame(container, bg=self.COLOR_BG, relief='solid', borderwidth=1, padx=10, pady=10)
        
        def toggle_collapse():
            if is_expanded.get():
                content_frame.pack_forget()
                arrow_label.config(text="►")
                is_expanded.set(False)
            else:
                content_frame.pack(fill='x')
                arrow_label.config(text="▼")
                is_expanded.set(True)
        
        header_frame.bind("<Button-1>", lambda e: toggle_collapse())
        arrow_label.bind("<Button-1>", lambda e: toggle_collapse())
        
        # Content
        current_value = getattr(gui, "get_messaged_var", 0)
        if hasattr(current_value, "get"):
            get_value = int(current_value.get())
        else:
            get_value = int(bool(current_value))
        gui.get_messaged_var = tk.IntVar(value=get_value)
        
        ttk.Checkbutton(
            content_frame,
            text="Enable Telegram Bot",
            variable=gui.get_messaged_var
        ).pack(anchor='w', pady=(0, 10))
        
        tk.Label(content_frame, text="Operator:", font=self.FONT_MAIN, bg=self.COLOR_BG).pack(anchor='w', pady=(0, 5))
        
        names = list(getattr(gui, "names", []))
        default_name = "Choose name" if names else "No_Name"
        gui.selected_user = tk.StringVar(value=default_name)
        gui.messaging_user_menu = ttk.Combobox(
            content_frame,
            textvariable=gui.selected_user,
            values=names,
            state="readonly" if names else "disabled",
            font=self.FONT_MAIN
        )
        gui.messaging_user_menu.pack(fill='x')
        
        # Bind callbacks
        update_cb = self.callbacks.get("update_messaging_info") or getattr(gui, "update_messaging_info", None)
        if update_cb:
            gui.messaging_user_menu.bind("<<ComboboxSelected>>", update_cb)
        
        self.widgets["telegram_bot"] = container
    
    # ------------------------------------------------------------------
    # TAB 2: Advanced Tests
    # ------------------------------------------------------------------
    def _create_advanced_tests_tab(self, notebook: ttk.Notebook) -> None:
        """Create the Advanced Tests tab (Endurance, Retention, etc.)"""
        gui = self.gui
        
        tab = tk.Frame(notebook, bg=self.COLOR_BG)
        notebook.add(tab, text="  Advanced Tests  ")
        
        # Scrollable content
        content = self._create_scrollable_panel(tab)
        content._container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Build endurance and retention controls
        self._build_manual_endurance_retention(content)
        
        self.widgets["advanced_tests_tab"] = tab
    
    # ------------------------------------------------------------------
    # TAB 3: Connection/Setup
    # ------------------------------------------------------------------
    def _create_setup_tab(self, notebook: ttk.Notebook) -> None:
        """Create the Setup tab (connections and configuration)"""
        gui = self.gui
        
        tab = tk.Frame(notebook, bg=self.COLOR_BG)
        notebook.add(tab, text="  Setup  ")
        
        # Scrollable content
        content = self._create_scrollable_panel(tab)
        content._container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Connection controls
        self._build_connection_section_modern(content)
        
        self.widgets["setup_tab"] = tab
    
    def _build_connection_section_modern(self, parent: tk.Misc) -> None:
        """Modern connection section for Setup tab"""
        gui = self.gui
        
        frame = tk.LabelFrame(
            parent,
            text="Instrument Connections",
            font=self.FONT_HEADING,
            bg=self.COLOR_BG,
            relief='solid',
            borderwidth=1,
            padx=15,
            pady=15
        )
        frame.pack(fill='x', padx=5, pady=5)
        
        # SMU/Keithley
        smu_frame = tk.LabelFrame(frame, text="SMU / Keithley", font=self.FONT_MAIN, bg=self.COLOR_BG, padx=10, pady=10)
        smu_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(smu_frame, text="GPIB Address:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5)
        gui.keithley_address_var = tk.StringVar(value=getattr(gui, "keithley_address", ""))
        gui.iv_address_entry = ttk.Entry(smu_frame, textvariable=gui.keithley_address_var, font=self.FONT_MAIN, width=30)
        gui.iv_address_entry.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 10))
        
        gui.iv_connect_button = tk.Button(
            smu_frame,
            text="Connect",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg='white',
            command=self.callbacks.get("connect_keithley"),
            padx=15
        )
        gui.iv_connect_button.grid(row=0, column=2, pady=5)
        
        smu_frame.columnconfigure(1, weight=1)
        
        # PSU
        psu_frame = tk.LabelFrame(frame, text="Power Supply", font=self.FONT_MAIN, bg=self.COLOR_BG, padx=10, pady=10)
        psu_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(psu_frame, text="GPIB Address:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5)
        gui.psu_address_var = tk.StringVar(value=getattr(gui, "psu_visa_address", ""))
        gui.psu_address_entry = ttk.Entry(psu_frame, textvariable=gui.psu_address_var, font=self.FONT_MAIN, width=30)
        gui.psu_address_entry.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 10))
        
        gui.psu_connect_button = tk.Button(
            psu_frame,
            text="Connect",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg='white',
            command=self.callbacks.get("connect_psu"),
            padx=15
        )
        gui.psu_connect_button.grid(row=0, column=2, pady=5)
        
        psu_frame.columnconfigure(1, weight=1)
        
        # Temperature Controller
        temp_frame = tk.LabelFrame(frame, text="Temperature Controller", font=self.FONT_MAIN, bg=self.COLOR_BG, padx=10, pady=10)
        temp_frame.pack(fill='x')
        
        tk.Label(temp_frame, text="GPIB Address:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5)
        gui.temp_address_var = tk.StringVar(value=getattr(gui, "temp_controller_address", ""))
        gui.temp_address_entry = ttk.Entry(temp_frame, textvariable=gui.temp_address_var, font=self.FONT_MAIN, width=30)
        gui.temp_address_entry.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 10))
        
        gui.temp_connect_button = tk.Button(
            temp_frame,
            text="Connect",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg='white',
            command=self.callbacks.get("connect_temp"),
            padx=15
        )
        gui.temp_connect_button.grid(row=0, column=2, pady=5)
        
        temp_frame.columnconfigure(1, weight=1)
        
        self.widgets["connection_section_modern"] = frame
    
    # ------------------------------------------------------------------
    # TAB 4: Custom Measurements (full interface)
    # ------------------------------------------------------------------
    def _create_custom_measurements_tab(self, notebook: ttk.Notebook) -> None:
        """Create the Custom Measurements tab with builder and visualizations"""
        gui = self.gui
        
        tab = tk.Frame(notebook, bg=self.COLOR_BG)
        notebook.add(tab, text="  Custom Measurements  ")
        
        # Import and create the custom measurements builder
        try:
            from gui.custom_measurements_builder import CustomMeasurementsBuilder
            
            # Create the builder with the tab as parent
            builder = CustomMeasurementsBuilder(
                parent=tab,
                gui_instance=gui,
                json_path="Json_Files/Custom_Sweeps.json"
            )
            
            # Store reference for later access
            gui.custom_measurements_builder = builder
            
        except Exception as e:
            # Fallback to simple interface if builder fails to load
            print(f"Failed to load custom measurements builder: {e}")
            content = self._create_scrollable_panel(tab)
            content._container.pack(fill='both', expand=True, padx=20, pady=20)
            self._build_custom_measurement_section(content)
        
        self.widgets["custom_measurements_tab"] = tab
    
    # ------------------------------------------------------------------
    # Bottom Status Bar
    # ------------------------------------------------------------------
    def _build_bottom_status_bar(self, parent: tk.Misc) -> None:
        """Create the bottom status bar"""
        gui = self.gui
        
        frame = tk.Frame(parent, bg=self.COLOR_BG_INFO, height=30, relief='sunken', borderwidth=1)
        frame.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        frame.grid_propagate(False)
        
        # Left side: Connection status
        left_section = tk.Frame(frame, bg=self.COLOR_BG_INFO)
        left_section.pack(side='left', fill='y', padx=10)
        
        gui.status_bar_connection = tk.Label(
            left_section,
            text="SMU: Disconnected",
            font=self.FONT_MAIN,
            bg=self.COLOR_BG_INFO,
            fg=self.COLOR_SECONDARY
        )
        gui.status_bar_connection.pack(side='left', padx=(0, 15))
        
        # Middle: Device count
        middle_section = tk.Frame(frame, bg=self.COLOR_BG_INFO)
        middle_section.pack(side='left', fill='y')
        
        device_count = len(getattr(gui, 'device_list', []))
        gui.status_bar_devices = tk.Label(
            middle_section,
            text=f"Devices: {device_count}",
            font=self.FONT_MAIN,
            bg=self.COLOR_BG_INFO,
            fg=self.COLOR_SECONDARY
        )
        gui.status_bar_devices.pack(side='left', padx=15)
        
        # Right side: Status message
        right_section = tk.Frame(frame, bg=self.COLOR_BG_INFO)
        right_section.pack(side='right', fill='y', padx=10)
        
        gui.status_bar_message = tk.Label(
            right_section,
            text="Ready",
            font=self.FONT_MAIN,
            bg=self.COLOR_BG_INFO,
            fg=self.COLOR_SUCCESS
        )
        gui.status_bar_message.pack(side='right')
        
        self.widgets["bottom_status_bar"] = frame

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------
    def _build_connection_section(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Keithley Connection", padx=5, pady=5)
        frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="Choose System:").grid(row=0, column=0, sticky="w")
        gui.systems = gui.load_systems()
        gui.system_var = tk.StringVar()
        system_dropdown = tk.OptionMenu(
            frame,
            gui.system_var,
            *gui.systems,
            command=self.callbacks.get("on_system_change"),
        )
        system_dropdown.grid(row=0, column=1, columnspan=2, sticky="ew")
        gui.system_dropdown = system_dropdown

        # SMU
        gui.iv_label = tk.Label(frame, text="GPIB Address - IV:")
        gui.iv_label.grid(row=1, column=0, sticky="w")
        gui.keithley_address_var = tk.StringVar(value=getattr(gui, "keithley_address", ""))
        gui.iv_address_entry = tk.Entry(frame, textvariable=gui.keithley_address_var)
        gui.iv_address_entry.grid(row=1, column=1)
        gui.iv_connect_button = tk.Button(frame, text="Connect", command=self.callbacks.get("connect_keithley"))
        gui.iv_connect_button.grid(row=1, column=2)

        # PSU
        gui.psu_label = tk.Label(frame, text="GPIB Address - PSU:")
        gui.psu_label.grid(row=2, column=0, sticky="w")
        gui.psu_address_var = tk.StringVar(value=getattr(gui, "psu_visa_address", ""))
        gui.psu_address_entry = tk.Entry(frame, textvariable=gui.psu_address_var)
        gui.psu_address_entry.grid(row=2, column=1)
        gui.psu_connect_button = tk.Button(frame, text="Connect", command=self.callbacks.get("connect_psu"))
        gui.psu_connect_button.grid(row=2, column=2)

        # Temperature controller
        gui.temp_label = tk.Label(frame, text="GPIB Address - Temp:")
        gui.temp_label.grid(row=3, column=0, sticky="w")
        gui.temp_address_var = tk.StringVar(value=getattr(gui, "temp_controller_address", ""))
        gui.temp_address_entry = tk.Entry(frame, textvariable=gui.temp_address_var)
        gui.temp_address_entry.grid(row=3, column=1)
        gui.temp_connect_button = tk.Button(frame, text="Connect", command=self.callbacks.get("connect_temp"))
        gui.temp_connect_button.grid(row=3, column=2)

        self.widgets["connection_frame"] = frame

    def _build_mode_selection(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Mode Selection", padx=5, pady=5)
        frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        gui.measure_one_device_label = tk.Label(frame, text="Measure One Device?")
        gui.measure_one_device_label.grid(row=0, column=0, sticky="w")
        gui.adaptive_var = tk.IntVar(value=1)
        gui.adaptive_switch = ttk.Checkbutton(
            frame,
            variable=gui.adaptive_var,
            command=self.callbacks.get("measure_one_device"),
        )
        gui.adaptive_switch.grid(row=0, column=1)

        gui.current_device_label = tk.Label(frame, text="Current Device:")
        gui.current_device_label.grid(row=1, column=0, sticky="w")
        gui.device_var = tk.Label(
            frame,
            text=getattr(gui, "display_index_section_number", ""),
            relief=tk.SUNKEN,
            anchor="w",
            width=20,
        )
        gui.device_var.grid(row=1, column=1, sticky="ew")

        gui.sample_name_label = tk.Label(frame, text="Sample Name (for saving):")
        gui.sample_name_label.grid(row=2, column=0, sticky="w")
        gui.sample_name_var = tk.StringVar()
        gui.sample_name_entry = ttk.Entry(frame, textvariable=gui.sample_name_var)
        gui.sample_name_entry.grid(row=2, column=1, sticky="ew")

        gui.additional_info_label = tk.Label(frame, text="Additional Info:")
        gui.additional_info_label.grid(row=3, column=0, sticky="w")
        gui.additional_info_var = tk.StringVar()
        gui.additional_info_entry = ttk.Entry(frame, textvariable=gui.additional_info_var)
        gui.additional_info_entry.grid(row=3, column=1, sticky="ew")

        save_location_frame = tk.Frame(frame)
        save_location_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        frame.columnconfigure(1, weight=1)

        gui.use_custom_save_var = tk.BooleanVar(value=False)
        gui.custom_save_location_var = tk.StringVar(value="")
        gui.custom_save_location = None

        tk.Checkbutton(
            save_location_frame,
            text="Use custom save location",
            variable=gui.use_custom_save_var,
            command=self.callbacks.get("on_custom_save_toggle"),
        ).grid(row=0, column=0, sticky="w")

        save_path_frame = tk.Frame(save_location_frame)
        save_path_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        save_path_frame.columnconfigure(0, weight=1)

        gui.save_path_entry = tk.Entry(
            save_path_frame,
            textvariable=gui.custom_save_location_var,
            state="disabled",
            width=40,
        )
        gui.save_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        browse_btn = tk.Button(save_path_frame, text="Browse...", command=self.callbacks.get("browse_save"))
        browse_btn.configure(state="disabled")
        browse_btn.grid(row=0, column=1)
        gui.save_browse_button = browse_btn

        # Load saved preference
        gui._load_save_location_config()

        self.widgets["mode_frame"] = frame

    def _build_top_banner(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="", padx=10, pady=10)
        frame.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(10, 5))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        title_label = tk.Label(
            frame,
            text="CRAIG'S CRAZY FUN IV CONTROL PANEL",
            font=("Helvetica", 12, "bold"),
            fg="black",
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=5, sticky="w")

        info_frame = tk.Frame(frame)
        info_frame.grid(row=1, column=0, columnspan=4, sticky="ew")
        info_frame.columnconfigure([0, 1, 2, 3, 4], weight=1)

        gui.device_label = tk.Label(info_frame, text="Device: XYZ", font=("Helvetica", 12))
        gui.device_label.grid(row=1, column=0, padx=10, sticky="w")

        gui.voltage_label = tk.Label(info_frame, text="Voltage: 1.23 V", font=("Helvetica", 12))
        gui.voltage_label.grid(row=1, column=1, padx=10, sticky="w")

        gui.loop_label = tk.Label(info_frame, text="Loop: 5", font=("Helvetica", 12))
        gui.loop_label.grid(row=1, column=2, padx=10, sticky="w")

        open_motor_cb = self.callbacks.get("open_motor_control")
        gui.motor_control_button = tk.Button(
            info_frame,
            text="Motor Control",
            command=open_motor_cb,
            state=tk.NORMAL if open_motor_cb else tk.DISABLED,
        )
        gui.motor_control_button.grid(row=1, column=3, columnspan=1, pady=5)

        check_conn_cb = self.callbacks.get("check_connection")
        gui.check_connection_button = tk.Button(
            info_frame,
            text="check_connection",
            command=check_conn_cb,
            state=tk.NORMAL if check_conn_cb else tk.DISABLED,
        )
        gui.check_connection_button.grid(row=1, column=4, columnspan=1, pady=5)

        gui._status_updates_active = True
        gui.master.after(250, gui._status_update_tick)

        self.widgets["top_banner"] = frame

    def _build_signal_messaging(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Telegram Messaging", padx=5, pady=5)
        frame.grid(row=8, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="Enable Telegram Bot").grid(row=0, column=0, sticky="w")
        current_value = getattr(gui, "get_messaged_var", 0)
        if hasattr(current_value, "get"):
            get_value = int(current_value.get())
        else:
            get_value = int(bool(current_value))
        gui.get_messaged_var = tk.IntVar(value=get_value)
        gui.get_messaged_switch = ttk.Checkbutton(frame, variable=gui.get_messaged_var)
        gui.get_messaged_switch.grid(row=0, column=1, padx=5, sticky="w")

        tk.Label(frame, text="Operator").grid(row=1, column=0, sticky="w")
        names = list(getattr(gui, "names", []))
        default_name = "Choose name" if names else "No_Name"
        gui.selected_user = tk.StringVar(value=default_name)
        gui.messaging_user_menu = ttk.Combobox(
            frame,
            textvariable=gui.selected_user,
            values=names,
            state="readonly" if names else "disabled",
        )
        gui.messaging_user_menu.grid(row=1, column=1, padx=5, sticky="ew")

        update_cb = self.callbacks.get("update_messaging_info") or getattr(gui, "update_messaging_info", None)
        if update_cb:
            gui.messaging_user_menu.bind("<<ComboboxSelected>>", update_cb)
            gui.get_messaged_switch.configure(command=lambda: update_cb(None))
        else:
            gui.get_messaged_switch.configure(state=tk.DISABLED)

        try:
            frame.lift()
        except Exception:
            pass

        frame.columnconfigure(1, weight=1)
        self.widgets["signal_messaging"] = frame

    def _build_manual_endurance_retention(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Manual Endurance / Retention", padx=5, pady=5)
        frame.grid(row=6, column=0, padx=10, pady=5, sticky="ew")

        end_frame = tk.Frame(frame)
        end_frame.grid(row=0, column=0, sticky="nw", padx=(0, 10))
        ret_frame = tk.Frame(frame)
        ret_frame.grid(row=0, column=1, sticky="ne")

        tk.Label(end_frame, text="Endurance").grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(end_frame, text="SET V").grid(row=1, column=0, sticky="w")
        end_set_default = getattr(gui, "end_set_v", 1.5)
        if hasattr(end_set_default, "get"):
            end_set_default = end_set_default.get()
        gui.end_set_v = tk.DoubleVar(value=end_set_default or 1.5)
        tk.Entry(end_frame, textvariable=gui.end_set_v, width=8).grid(row=1, column=1, sticky="w")

        tk.Label(end_frame, text="RESET V").grid(row=2, column=0, sticky="w")
        end_reset_default = getattr(gui, "end_reset_v", -1.5)
        if hasattr(end_reset_default, "get"):
            end_reset_default = end_reset_default.get()
        gui.end_reset_v = tk.DoubleVar(value=end_reset_default or -1.5)
        tk.Entry(end_frame, textvariable=gui.end_reset_v, width=8).grid(row=2, column=1, sticky="w")

        tk.Label(end_frame, text="Pulse (ms)").grid(row=3, column=0, sticky="w")
        end_pulse_default = getattr(gui, "end_pulse_ms", 10)
        if hasattr(end_pulse_default, "get"):
            end_pulse_default = end_pulse_default.get()
        gui.end_pulse_ms = tk.DoubleVar(value=end_pulse_default or 10)
        tk.Entry(end_frame, textvariable=gui.end_pulse_ms, width=8).grid(row=3, column=1, sticky="w")

        tk.Label(end_frame, text="Cycles").grid(row=4, column=0, sticky="w")
        end_cycles_default = getattr(gui, "end_cycles", 100)
        if hasattr(end_cycles_default, "get"):
            end_cycles_default = end_cycles_default.get()
        gui.end_cycles = tk.IntVar(value=end_cycles_default or 100)
        tk.Entry(end_frame, textvariable=gui.end_cycles, width=8).grid(row=4, column=1, sticky="w")

        tk.Label(end_frame, text="Read V").grid(row=5, column=0, sticky="w")
        end_read_default = getattr(gui, "end_read_v", 0.2)
        if hasattr(end_read_default, "get"):
            end_read_default = end_read_default.get()
        gui.end_read_v = tk.DoubleVar(value=end_read_default or 0.2)
        tk.Entry(end_frame, textvariable=gui.end_read_v, width=8).grid(row=5, column=1, sticky="w")

        start_endurance_cb = self.callbacks.get("start_manual_endurance") or getattr(gui, "start_manual_endurance", None)
        tk.Button(
            end_frame,
            text="Start Endurance",
            command=start_endurance_cb,
            state=tk.NORMAL if start_endurance_cb else tk.DISABLED,
        ).grid(row=6, column=0, columnspan=2, pady=(4, 0), sticky="w")

        tk.Label(ret_frame, text="Retention").grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(ret_frame, text="SET V").grid(row=1, column=0, sticky="w")
        ret_set_default = getattr(gui, "ret_set_v", 1.5)
        if hasattr(ret_set_default, "get"):
            ret_set_default = ret_set_default.get()
        gui.ret_set_v = tk.DoubleVar(value=ret_set_default or 1.5)
        tk.Entry(ret_frame, textvariable=gui.ret_set_v, width=8).grid(row=1, column=1, sticky="w")

        tk.Label(ret_frame, text="SET Time (ms)").grid(row=2, column=0, sticky="w")
        ret_set_ms_default = getattr(gui, "ret_set_ms", 10)
        if hasattr(ret_set_ms_default, "get"):
            ret_set_ms_default = ret_set_ms_default.get()
        gui.ret_set_ms = tk.DoubleVar(value=ret_set_ms_default or 10)
        tk.Entry(ret_frame, textvariable=gui.ret_set_ms, width=8).grid(row=2, column=1, sticky="w")

        tk.Label(ret_frame, text="Read V").grid(row=3, column=0, sticky="w")
        ret_read_default = getattr(gui, "ret_read_v", 0.2)
        if hasattr(ret_read_default, "get"):
            ret_read_default = ret_read_default.get()
        gui.ret_read_v = tk.DoubleVar(value=ret_read_default or 0.2)
        tk.Entry(ret_frame, textvariable=gui.ret_read_v, width=8).grid(row=3, column=1, sticky="w")

        tk.Label(ret_frame, text="Every (s)").grid(row=4, column=0, sticky="w")
        ret_every_default = getattr(gui, "ret_every_s", 10.0)
        if hasattr(ret_every_default, "get"):
            ret_every_default = ret_every_default.get()
        gui.ret_every_s = tk.DoubleVar(value=ret_every_default or 10.0)
        tk.Entry(ret_frame, textvariable=gui.ret_every_s, width=8).grid(row=4, column=1, sticky="w")

        tk.Label(ret_frame, text="# Points").grid(row=5, column=0, sticky="w")
        ret_points_default = getattr(gui, "ret_points", 30)
        if hasattr(ret_points_default, "get"):
            ret_points_default = ret_points_default.get()
        gui.ret_points = tk.IntVar(value=ret_points_default or 30)
        tk.Entry(ret_frame, textvariable=gui.ret_points, width=8).grid(row=5, column=1, sticky="w")

        ret_estimate_default = getattr(gui, "ret_estimate_var", "Total: ~300 s")
        if hasattr(ret_estimate_default, "get"):
            ret_estimate_default = ret_estimate_default.get()
        gui.ret_estimate_var = tk.StringVar(value=ret_estimate_default or "Total: ~300 s")
        tk.Label(ret_frame, textvariable=gui.ret_estimate_var, fg="grey").grid(row=6, column=0, columnspan=2, sticky="w")

        start_retention_cb = self.callbacks.get("start_manual_retention") or getattr(gui, "start_manual_retention", None)
        tk.Button(
            ret_frame,
            text="Start Retention",
            command=start_retention_cb,
            state=tk.NORMAL if start_retention_cb else tk.DISABLED,
        ).grid(row=7, column=0, columnspan=2, pady=(4, 0), sticky="w")

        led_frame = tk.Frame(frame)
        led_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        tk.Label(led_frame, text="LED:").pack(side="left")

        manual_led_power_default = getattr(gui, "manual_led_power", 1.0)
        if hasattr(manual_led_power_default, "get"):
            manual_led_power_default = manual_led_power_default.get()
        gui.manual_led_power = tk.DoubleVar(value=manual_led_power_default or 1.0)
        tk.Entry(led_frame, textvariable=gui.manual_led_power, width=8).pack(side="left", padx=(4, 4))

        gui.manual_led_on = getattr(gui, "manual_led_on", False)
        toggle_led_cb = self.callbacks.get("toggle_manual_led") or getattr(gui, "toggle_manual_led", None)
        gui.manual_led_btn = tk.Button(
            led_frame,
            text="LED ON" if gui.manual_led_on else "LED OFF",
            command=toggle_led_cb,
            state=tk.NORMAL if toggle_led_cb else tk.DISABLED,
        )
        gui.manual_led_btn.pack(side="left")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        self.widgets["manual_endurance_retention"] = frame

    def build_sequential_controls(self, parent: tk.Misc) -> None:
        self._build_sequential_controls(parent)

    def _build_sequential_controls(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Sequential Measurements", padx=5, pady=5)
        frame.grid(row=5, column=0, padx=10, pady=5, sticky="ew")

        existing_mode = getattr(gui, "Sequential_measurement_var", "Iv Sweep")
        if hasattr(existing_mode, "get"):
            existing_mode = existing_mode.get()
        gui.Sequential_measurement_var = tk.StringVar(value=existing_mode or "Iv Sweep")
        mode_menu = ttk.Combobox(
            frame,
            textvariable=gui.Sequential_measurement_var,
            values=["Iv Sweep", "Single Avg Measure"],
            state="readonly",
        )
        mode_menu.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tk.Label(frame, text="Mode:").grid(row=0, column=0, sticky="w")

        existing_sweeps = getattr(gui, "sequential_number_of_sweeps", 100)
        if hasattr(existing_sweeps, "get"):
            try:
                existing_sweeps = existing_sweeps.get()
            except Exception:
                existing_sweeps = 100
        try:
            sweeps_value = int(existing_sweeps)
        except Exception:
            sweeps_value = 100
        gui.sequential_number_of_sweeps = tk.IntVar(value=max(1, sweeps_value))
        tk.Label(frame, text="# Passes:").grid(row=1, column=0, sticky="w")
        sweeps_entry = tk.Entry(frame, textvariable=gui.sequential_number_of_sweeps, width=10)
        sweeps_entry.grid(row=1, column=1, sticky="w")

        existing_voltage = getattr(gui, "sq_voltage", 1.0)
        if hasattr(existing_voltage, "get"):
            try:
                existing_voltage = existing_voltage.get()
            except Exception:
                existing_voltage = 1.0
        try:
            voltage_value = float(existing_voltage)
        except Exception:
            voltage_value = 1.0
        gui.sq_voltage = tk.DoubleVar(value=voltage_value)
        tk.Label(frame, text="Voltage Limit (V):").grid(row=2, column=0, sticky="w")
        tk.Entry(frame, textvariable=gui.sq_voltage, width=10).grid(row=2, column=1, sticky="w")

        existing_delay = getattr(gui, "sq_time_delay", 1.0)
        if hasattr(existing_delay, "get"):
            try:
                existing_delay = existing_delay.get()
            except Exception:
                existing_delay = 1.0
        try:
            delay_value = float(existing_delay)
        except Exception:
            delay_value = 1.0
        gui.sq_time_delay = tk.DoubleVar(value=max(0.0, delay_value))
        tk.Label(frame, text="Delay Between Passes (s):").grid(row=3, column=0, sticky="w")
        tk.Entry(frame, textvariable=gui.sq_time_delay, width=10).grid(row=3, column=1, sticky="w")

        existing_duration = getattr(gui, "measurement_duration_var", 1.0)
        if hasattr(existing_duration, "get"):
            try:
                existing_duration = existing_duration.get()
            except Exception:
                existing_duration = 1.0
        try:
            duration_value = float(existing_duration)
        except Exception:
            duration_value = 1.0
        gui.measurement_duration_var = tk.DoubleVar(value=max(0.0, duration_value))
        tk.Label(frame, text="Duration per Device (s):").grid(row=4, column=0, sticky="w")
        duration_entry = tk.Entry(frame, textvariable=gui.measurement_duration_var, width=10)
        duration_entry.grid(row=4, column=1, sticky="w")

        existing_live_plot = getattr(gui, "live_plot_enabled", None)
        if not isinstance(existing_live_plot, tk.BooleanVar):
            gui.live_plot_enabled = tk.BooleanVar(
                value=bool(existing_live_plot) if existing_live_plot is not None else True
            )
        else:
            gui.live_plot_enabled = existing_live_plot
        tk.Checkbutton(
            frame,
            text="Enable live plotting",
            variable=gui.live_plot_enabled,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

        start_cb = self.callbacks.get("start_sequential_measurement") or getattr(
            gui, "sequential_measure", None
        )
        stop_cb = self.callbacks.get("stop_sequential_measurement") or getattr(
            gui, "set_measurment_flag_true", None
        )

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(6, 0), sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        start_state = tk.NORMAL if callable(start_cb) else tk.DISABLED
        stop_state = tk.NORMAL if callable(stop_cb) else tk.DISABLED

        tk.Button(btn_frame, text="Start Sequential", command=start_cb, state=start_state).grid(
            row=0, column=0, padx=(0, 4), sticky="ew"
        )
        tk.Button(btn_frame, text="Stop", command=stop_cb, state=stop_state).grid(
            row=0, column=1, padx=(4, 0), sticky="ew"
        )

        def _update_duration_state(*_: object) -> None:
            mode = gui.Sequential_measurement_var.get()
            if mode == "Single Avg Measure":
                duration_entry.configure(state="normal")
            else:
                duration_entry.configure(state="disabled")

        mode_menu.bind("<<ComboboxSelected>>", _update_duration_state)
        _update_duration_state()

        frame.columnconfigure(1, weight=1)
        self.widgets["sequential_controls"] = frame

    def _build_custom_measurement_section(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Custom Measurements", padx=5, pady=5)
        frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="Custom Measurement:").grid(row=0, column=0, sticky="w")
        test_names = getattr(gui, "test_names", [])
        default_test = test_names[0] if test_names else "Test"
        gui.custom_measurement_var = tk.StringVar(value=default_test)
        gui.custom_measurement_menu = ttk.Combobox(
            frame,
            textvariable=gui.custom_measurement_var,
            values=test_names,
            state="readonly" if test_names else "disabled",
        )
        gui.custom_measurement_menu.grid(row=0, column=1, padx=5)

        start_cb = self.callbacks.get("start_custom_measurement_thread") or getattr(gui, "start_custom_measurement", None)
        gui.run_custom_button = tk.Button(
            frame,
            text="Run Custom",
            command=start_cb,
            state=tk.NORMAL if start_cb else tk.DISABLED,
        )
        gui.run_custom_button.grid(row=1, column=0, columnspan=2, pady=5)

        def toggle_pause() -> None:
            toggle_cb = self.callbacks.get("toggle_custom_pause") or getattr(gui, "toggle_custom_pause", None)
            if not toggle_cb:
                return
            new_state = toggle_cb()
            try:
                gui.pause_button_custom.config(text="Resume" if new_state else "Pause")
            except Exception:
                pass

        gui.pause_button_custom = tk.Button(frame, text="Pause", width=10, command=toggle_pause)
        gui.pause_button_custom.grid(row=2, column=0, padx=5, pady=2, sticky="w")

        edit_cb = self.callbacks.get("open_sweep_editor") or getattr(gui, "open_sweep_editor_popup", None)
        tk.Button(
            frame,
            text="Edit Sweeps",
            command=edit_cb,
            state=tk.NORMAL if edit_cb else tk.DISABLED,
        ).grid(row=2, column=1, padx=5, pady=2, sticky="w")

        frame.columnconfigure(1, weight=1)
        self.widgets["custom_measurements"] = frame


def _self_test() -> None:
    """Basic smoke-test to ensure panels build without raising."""
    root = tk.Tk()
    root.withdraw()

    class _DummyGUI:
        def __init__(self, master: tk.Tk) -> None:
            self.master = master
            self.names = []

        def load_systems(self):
            return ["System 1"]

        def _load_save_location_config(self):
            return None

        def _status_update_tick(self):
            return None

    dummy = _DummyGUI(root)
    left = tk.Frame(root)
    middle = tk.Frame(root)
    top = tk.Frame(root)

    builder = MeasurementGUILayoutBuilder(
        gui=dummy,
        callbacks={
            "connect_keithley": lambda: None,
            "connect_psu": lambda: None,
            "connect_temp": lambda: None,
            "measure_one_device": lambda: None,
            "on_system_change": lambda _: None,
            "on_custom_save_toggle": lambda: None,
            "browse_save": lambda: None,
            "open_motor_control": lambda: None,
            "check_connection": lambda: None,
        },
    )
    builder.build_all_panels(left, middle, top)

    assert "top_banner" in builder.widgets

    root.destroy()


if __name__ == "__main__":  # pragma: no cover - developer smoke test
    _self_test()

