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
from typing import Callable, Dict, Optional, List, Tuple, Any

import tkinter as tk
from tkinter import ttk, messagebox


@dataclass
class MeasurementGUILayoutBuilder:
    gui: object
    callbacks: Dict[str, Callable]
    widgets: Dict[str, tk.Widget] = field(default_factory=dict)
    _updating_system: bool = False  # Flag to prevent recursive updates
    
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
        
        # Set default value if systems exist
        if gui.systems and gui.systems[0] != "No systems available":
            gui.system_var.set(gui.systems[0])
        
        # Add trace to sync both dropdowns when StringVar changes
        # This will be called when either dropdown changes the StringVar
        # Store reference to this builder for the trace callback
        builder_ref = self
        def sync_system_dropdowns(*args):
            if builder_ref._updating_system:
                return
            builder_ref._updating_system = True
            try:
                selected = gui.system_var.get()
                if not selected:
                    return
                # Update top bar dropdown if value differs
                if hasattr(gui, 'system_dropdown') and gui.system_dropdown and selected in gui.system_dropdown['values']:
                    current_top = gui.system_dropdown.get()
                    if current_top != selected:
                        gui.system_dropdown.set(selected)
                # Update Setup tab dropdown if it exists and value differs
                if hasattr(gui, 'system_combo') and gui.system_combo and selected in gui.system_combo['values']:
                    current_setup = gui.system_combo.get()
                    if current_setup != selected:
                        gui.system_combo.set(selected)
            except Exception:
                # Silently ignore errors during sync to prevent crashes
                pass
            finally:
                builder_ref._updating_system = False
        
        gui.system_var.trace_add('write', sync_system_dropdowns)
        
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
        gui = self.gui
        
        # StringVar trace will automatically sync Setup tab dropdown
        # First load the system configuration (comprehensive update)
        load_system_cb = self.callbacks.get("load_system")
        if load_system_cb:
            load_system_cb()
        
        # Also call the system change callback for address updates
        system_change_cb = self.callbacks.get("on_system_change")
        if system_change_cb:
            system_change_cb(gui.system_var.get())
        
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
        self._create_notes_tab(notebook)
        
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
        
        # Mouse wheel scrolling - bind to canvas only (not global)
        def _on_mousewheel(event):
            # Check if canvas still exists before trying to scroll
            try:
                # Try to access canvas to verify it exists
                _ = canvas.winfo_id()
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except (tk.TclError, AttributeError):
                # Canvas has been destroyed, ignore the event
                pass
        # Bind only to this canvas, not globally
        canvas.bind("<MouseWheel>", _on_mousewheel)
        
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
        """Modern connection section for Setup tab with system builder"""
        gui = self.gui
        
        frame = tk.LabelFrame(
            parent,
            text="System Configuration & Instrument Connections",
            font=self.FONT_HEADING,
            bg=self.COLOR_BG,
            relief='solid',
            borderwidth=1,
            padx=15,
            pady=15
        )
        frame.pack(fill='x', padx=5, pady=5)
        
        # System Selector Section
        system_frame = tk.LabelFrame(frame, text="System Configuration", font=self.FONT_MAIN, bg=self.COLOR_BG, padx=10, pady=10)
        system_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(system_frame, text="Load System:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5, padx=(0, 10))
        
        # Load systems list
        if hasattr(gui, 'load_systems'):
            systems = gui.load_systems()
        else:
            systems = []
        if not systems or systems == ["No systems available"]:
            systems = []
        
        # Use existing system_var if it exists (from top bar), otherwise create new one
        if not hasattr(gui, 'system_var') or gui.system_var is None:
            gui.system_var = tk.StringVar(value=systems[0] if systems else "")
        else:
            # If system_var exists, make sure it has a valid value
            current_value = gui.system_var.get()
            if not current_value or current_value not in systems:
                if systems:
                    gui.system_var.set(systems[0])
        
        # Update top bar dropdown values if it exists
        if hasattr(gui, 'system_dropdown') and gui.system_dropdown:
            gui.system_dropdown['values'] = systems
        
        gui.system_combo = ttk.Combobox(system_frame, textvariable=gui.system_var, values=systems, 
                                        font=self.FONT_MAIN, width=25, state='readonly')
        gui.system_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(0, 10))
        
        # Unified handler that loads system (StringVar trace will sync dropdowns)
        def on_system_selected(event=None):
            if self._updating_system:
                return
            # Load the system configuration
            load_system_cb = self.callbacks.get("load_system")
            if load_system_cb:
                load_system_cb()
            # Also trigger system change for address updates
            system_change_cb = self.callbacks.get("on_system_change")
            if system_change_cb:
                system_change_cb(gui.system_var.get())
        
        gui.system_combo.bind('<<ComboboxSelected>>', on_system_selected)
        
        def on_load_button_click():
            # Load the system configuration (StringVar trace will sync dropdowns)
            load_system_cb = self.callbacks.get("load_system")
            if load_system_cb:
                load_system_cb()
            # Also trigger system change for address updates
            system_change_cb = self.callbacks.get("on_system_change")
            if system_change_cb:
                system_change_cb(gui.system_var.get())
        
        tk.Button(
            system_frame,
            text="Load",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg='white',
            command=on_load_button_click,
            padx=15
        ).grid(row=0, column=2, pady=5, padx=(0, 10))
        
        tk.Button(
            system_frame,
            text="Save As...",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg='white',
            command=self.callbacks.get("save_system", lambda: None),
            padx=15
        ).grid(row=0, column=3, pady=5)
        
        system_frame.columnconfigure(1, weight=1)
        
        # SMU/Keithley Section
        smu_frame = tk.LabelFrame(frame, text="SMU / Keithley", font=self.FONT_MAIN, bg=self.COLOR_BG, padx=10, pady=10)
        smu_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(smu_frame, text="Type:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5)
        smu_types = ['Keithley 2401', 'Keithley 2450', 'Keithley 2450 (Simulation)', 'Hp4140b', 'Keithley 4200A']
        gui.smu_type_var = tk.StringVar(value=getattr(gui, "SMU_type", smu_types[0]))
        gui.smu_type_combo = ttk.Combobox(smu_frame, textvariable=gui.smu_type_var, values=smu_types,
                                          font=self.FONT_MAIN, width=25, state='readonly')
        gui.smu_type_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 10))
        
        tk.Label(smu_frame, text="Address:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=1, column=0, sticky='w', pady=5)
        gui.keithley_address_var = tk.StringVar(value=getattr(gui, "keithley_address", ""))
        
        # Address combobox with refresh button
        address_frame = tk.Frame(smu_frame, bg=self.COLOR_BG)
        address_frame.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 5))
        
        gui.iv_address_combo = ttk.Combobox(address_frame, textvariable=gui.keithley_address_var, 
                                             font=self.FONT_MAIN, width=28)
        gui.iv_address_combo.grid(row=0, column=0, sticky='ew')
        gui.iv_address_combo['values'] = self._scan_visa_resources()
        gui.iv_address_combo.bind('<FocusOut>', lambda e: self._validate_and_identify_address(gui, 'smu'))
        gui.iv_address_combo.bind('<<ComboboxSelected>>', lambda e: self._validate_and_identify_address(gui, 'smu'))
        
        refresh_btn_smu = tk.Button(
            address_frame,
            text="🔄",
            font=("Arial", 10),
            bg=self.COLOR_BG,
            fg='black',
            relief='flat',
            command=lambda: self._refresh_address_combo(gui.iv_address_combo),
            padx=5
        )
        refresh_btn_smu.grid(row=0, column=1, padx=(5, 0))
        
        address_frame.columnconfigure(0, weight=1)
        gui.iv_address_entry = gui.iv_address_combo  # Keep for backward compatibility
        
        # Status indicator
        gui.smu_status_indicator = tk.Label(smu_frame, text="●", font=("Arial", 16), bg=self.COLOR_BG, fg='gray')
        gui.smu_status_indicator.grid(row=1, column=2, padx=(5, 5), sticky='w')
        
        # Test and Connect buttons
        button_frame_smu = tk.Frame(smu_frame, bg=self.COLOR_BG)
        button_frame_smu.grid(row=1, column=3, pady=5, padx=(0, 0))
        
        # Device info label (below address row)
        gui.smu_device_info = tk.Label(smu_frame, text="", font=("Segoe UI", 8), bg=self.COLOR_BG, fg='#666666')
        gui.smu_device_info.grid(row=2, column=1, columnspan=2, sticky='w', padx=(10, 0), pady=(2, 0))
        
        gui.iv_test_button = tk.Button(
            button_frame_smu,
            text="Test",
            font=self.FONT_BUTTON,
            bg='#FF9800',
            fg='white',
            command=lambda: self._test_connection(gui, 'smu'),
            padx=10
        )
        gui.iv_test_button.pack(side='left', padx=(0, 5))
        
        gui.iv_connect_button = tk.Button(
            button_frame_smu,
            text="Connect",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg='white',
            command=self.callbacks.get("connect_keithley"),
            padx=15
        )
        gui.iv_connect_button.pack(side='left')
        
        smu_frame.columnconfigure(1, weight=1)
        
        # PSU Section
        psu_frame = tk.LabelFrame(frame, text="Power Supply", font=self.FONT_MAIN, bg=self.COLOR_BG, padx=10, pady=10)
        psu_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(psu_frame, text="Type:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5)
        psu_types = ['Keithley 2220', 'None']
        gui.psu_type_var = tk.StringVar(value=getattr(gui, "psu_type", psu_types[0]))
        gui.psu_type_combo = ttk.Combobox(psu_frame, textvariable=gui.psu_type_var, values=psu_types,
                                          font=self.FONT_MAIN, width=25, state='readonly')
        gui.psu_type_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 10))
        
        tk.Label(psu_frame, text="Address:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=1, column=0, sticky='w', pady=5)
        gui.psu_address_var = tk.StringVar(value=getattr(gui, "psu_visa_address", ""))
        
        # Address combobox with refresh button
        address_frame_psu = tk.Frame(psu_frame, bg=self.COLOR_BG)
        address_frame_psu.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 5))
        
        gui.psu_address_combo = ttk.Combobox(address_frame_psu, textvariable=gui.psu_address_var, 
                                            font=self.FONT_MAIN, width=28)
        gui.psu_address_combo.grid(row=0, column=0, sticky='ew')
        gui.psu_address_combo['values'] = self._scan_visa_resources()
        gui.psu_address_combo.bind('<FocusOut>', lambda e: self._validate_and_identify_address(gui, 'psu'))
        gui.psu_address_combo.bind('<<ComboboxSelected>>', lambda e: self._validate_and_identify_address(gui, 'psu'))
        
        refresh_btn_psu = tk.Button(
            address_frame_psu,
            text="🔄",
            font=("Arial", 10),
            bg=self.COLOR_BG,
            fg='black',
            relief='flat',
            command=lambda: self._refresh_address_combo(gui.psu_address_combo),
            padx=5
        )
        refresh_btn_psu.grid(row=0, column=1, padx=(5, 0))
        
        address_frame_psu.columnconfigure(0, weight=1)
        gui.psu_address_entry = gui.psu_address_combo  # Keep for backward compatibility
        
        # Status indicator
        gui.psu_status_indicator = tk.Label(psu_frame, text="●", font=("Arial", 16), bg=self.COLOR_BG, fg='gray')
        gui.psu_status_indicator.grid(row=1, column=2, padx=(5, 5), sticky='w')
        
        # Test and Connect buttons
        button_frame_psu = tk.Frame(psu_frame, bg=self.COLOR_BG)
        button_frame_psu.grid(row=1, column=3, pady=5, padx=(0, 0))
        
        # Device info label (below address row)
        gui.psu_device_info = tk.Label(psu_frame, text="", font=("Segoe UI", 8), bg=self.COLOR_BG, fg='#666666')
        gui.psu_device_info.grid(row=2, column=1, columnspan=2, sticky='w', padx=(10, 0), pady=(2, 0))
        
        gui.psu_test_button = tk.Button(
            button_frame_psu,
            text="Test",
            font=self.FONT_BUTTON,
            bg='#FF9800',
            fg='white',
            command=lambda: self._test_connection(gui, 'psu'),
            padx=10
        )
        gui.psu_test_button.pack(side='left', padx=(0, 5))
        
        gui.psu_connect_button = tk.Button(
            button_frame_psu,
            text="Connect",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg='white',
            command=self.callbacks.get("connect_psu"),
            padx=15
        )
        gui.psu_connect_button.pack(side='left')
        
        psu_frame.columnconfigure(1, weight=1)
        
        # Temperature Controller Section
        temp_frame = tk.LabelFrame(frame, text="Temperature Controller", font=self.FONT_MAIN, bg=self.COLOR_BG, padx=10, pady=10)
        temp_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(temp_frame, text="Type:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5)
        temp_types = ['Auto-Detect', 'Lakeshore 335', 'Oxford ITC4', 'None']
        gui.temp_type_var = tk.StringVar(value=getattr(gui, "temp_controller_type", temp_types[0]))
        gui.temp_type_combo = ttk.Combobox(temp_frame, textvariable=gui.temp_type_var, values=temp_types,
                                          font=self.FONT_MAIN, width=25, state='readonly')
        gui.temp_type_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 10))
        
        tk.Label(temp_frame, text="Address:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=1, column=0, sticky='w', pady=5)
        gui.temp_address_var = tk.StringVar(value=getattr(gui, "temp_controller_address", ""))
        
        # Address combobox with refresh button (include serial for temp controllers)
        address_frame_temp = tk.Frame(temp_frame, bg=self.COLOR_BG)
        address_frame_temp.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 5))
        
        gui.temp_address_combo = ttk.Combobox(address_frame_temp, textvariable=gui.temp_address_var, 
                                              font=self.FONT_MAIN, width=28)
        gui.temp_address_combo.grid(row=0, column=0, sticky='ew')
        gui.temp_address_combo['values'] = self._scan_visa_resources(include_serial=True)
        gui.temp_address_combo.bind('<FocusOut>', lambda e: self._validate_and_identify_address(gui, 'temp'))
        gui.temp_address_combo.bind('<<ComboboxSelected>>', lambda e: self._validate_and_identify_address(gui, 'temp'))
        
        refresh_btn_temp = tk.Button(
            address_frame_temp,
            text="🔄",
            font=("Arial", 10),
            bg=self.COLOR_BG,
            fg='black',
            relief='flat',
            command=lambda: self._refresh_address_combo(gui.temp_address_combo, include_serial=True),
            padx=5
        )
        refresh_btn_temp.grid(row=0, column=1, padx=(5, 0))
        
        address_frame_temp.columnconfigure(0, weight=1)
        gui.temp_address_entry = gui.temp_address_combo  # Keep for backward compatibility
        
        # Status indicator
        gui.temp_status_indicator = tk.Label(temp_frame, text="●", font=("Arial", 16), bg=self.COLOR_BG, fg='gray')
        gui.temp_status_indicator.grid(row=1, column=2, padx=(5, 5), sticky='w')
        
        # Test and Connect buttons
        button_frame_temp = tk.Frame(temp_frame, bg=self.COLOR_BG)
        button_frame_temp.grid(row=1, column=3, pady=5, padx=(0, 0))
        
        # Device info label (below address row)
        gui.temp_device_info = tk.Label(temp_frame, text="", font=("Segoe UI", 8), bg=self.COLOR_BG, fg='#666666')
        gui.temp_device_info.grid(row=2, column=1, columnspan=2, sticky='w', padx=(10, 0), pady=(2, 0))
        
        gui.temp_test_button = tk.Button(
            button_frame_temp,
            text="Test",
            font=self.FONT_BUTTON,
            bg='#FF9800',
            fg='white',
            command=lambda: self._test_connection(gui, 'temp'),
            padx=10
        )
        gui.temp_test_button.pack(side='left', padx=(0, 5))
        
        gui.temp_connect_button = tk.Button(
            button_frame_temp,
            text="Connect",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg='white',
            command=self.callbacks.get("connect_temp"),
            padx=15
        )
        gui.temp_connect_button.pack(side='left')
        
        temp_frame.columnconfigure(1, weight=1)
        
        # Optical Excitation Section (Collapsible)
        self._build_optical_section(frame, gui)
        
        self.widgets["connection_section_modern"] = frame
    
    def _scan_visa_resources(self, include_serial: bool = False) -> List[str]:
        """Scan for available VISA resources (USB, GPIB, and optionally serial)
        
        Args:
            include_serial: If True, also include ASRL (serial) resources
            
        Returns:
            List of available resource addresses
        """
        devices = []
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
            
            # Filter for USB, GPIB, and optionally serial devices
            for res in resources:
                if res.startswith('USB') or res.startswith('GPIB'):
                    devices.append(res)
                elif include_serial and (res.startswith('ASRL') or res.startswith('COM')):
                    devices.append(res)
            
            # Sort for better UX
            devices.sort()
            
        except ImportError:
            print("PyVISA not available - cannot scan for devices")
        except Exception as e:
            print(f"Could not scan VISA resources: {e}")
        
        return devices
    
    def _refresh_address_combo(self, combo: ttk.Combobox, include_serial: bool = False) -> None:
        """Refresh the address combobox with current VISA resources
        
        Args:
            combo: The combobox to refresh
            include_serial: If True, include serial resources
        """
        current_value = combo.get()
        available_devices = self._scan_visa_resources(include_serial=include_serial)
        
        # Keep current value if it's not in the list
        if current_value and current_value not in available_devices:
            available_devices.insert(0, current_value)
        
        combo['values'] = available_devices
        
        # Restore current value if it was set
        if current_value:
            combo.set(current_value)
    
    def _validate_address_format(self, address: str) -> Tuple[bool, str]:
        """Validate address format
        
        Args:
            address: Address string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not address or not address.strip():
            return True, ""  # Empty is valid (optional field)
        
        address = address.strip()
        
        # Check for common valid patterns
        valid_patterns = [
            address.startswith('GPIB'),
            address.startswith('USB'),
            address.startswith('ASRL'),
            address.startswith('COM'),
            address.startswith('TCPIP'),
            address.startswith('192.168.'),  # IP address
            address.startswith('SIM'),  # Simulation
        ]
        
        if any(valid_patterns):
            return True, ""
        
        # Check if it looks like an IP:port
        if ':' in address and '.' in address.split(':')[0]:
            try:
                parts = address.split(':')
                if len(parts) == 2:
                    ip, port = parts
                    # Basic IP validation
                    ip_parts = ip.split('.')
                    if len(ip_parts) == 4:
                        all(int(p) >= 0 and int(p) <= 255 for p in ip_parts)
                        int(port)  # Validate port is numeric
                        return True, ""
            except:
                pass
        
        return False, "Invalid address format. Expected: GPIB0::X::INSTR, USB0::..., ASRLX::INSTR, COMX, or IP:PORT"
    
    def _query_device_idn(self, address: str, timeout_ms: int = 2000) -> Tuple[bool, str]:
        """Query device identification using *IDN?
        
        Args:
            address: VISA address
            timeout_ms: Timeout in milliseconds
            
        Returns:
            Tuple of (success, idn_string or error_message)
        """
        if not address or not address.strip():
            return False, "No address provided"
        
        address = address.strip()
        
        # Skip simulation addresses
        if address.upper().startswith('SIM'):
            return True, "Simulation Device"
        
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            resource = rm.open_resource(address)
            resource.timeout = timeout_ms
            
            try:
                idn = resource.query('*IDN?').strip()
                resource.close()
                return True, idn
            except Exception as e:
                resource.close()
                # Some devices might not support *IDN?, that's okay
                return False, f"Device doesn't respond to *IDN?: {str(e)[:50]}"
        except ImportError:
            return False, "PyVISA not available"
        except Exception as e:
            return False, f"Connection error: {str(e)[:50]}"
    
    def _validate_and_identify_address(self, gui: object, device_type: str) -> None:
        """Validate address format and attempt to identify device
        
        Args:
            gui: GUI instance
            device_type: 'smu', 'psu', or 'temp'
        """
        # Get address based on device type
        if device_type == 'smu':
            address_var = gui.keithley_address_var
            status_indicator = getattr(gui, 'smu_status_indicator', None)
            device_info = getattr(gui, 'smu_device_info', None)
        elif device_type == 'psu':
            address_var = gui.psu_address_var
            status_indicator = getattr(gui, 'psu_status_indicator', None)
            device_info = getattr(gui, 'psu_device_info', None)
        elif device_type == 'temp':
            address_var = gui.temp_address_var
            status_indicator = getattr(gui, 'temp_status_indicator', None)
            device_info = getattr(gui, 'temp_device_info', None)
        else:
            return
        
        address = address_var.get()
        
        # Validate format
        is_valid, error_msg = self._validate_address_format(address)
        
        if not is_valid:
            if status_indicator:
                status_indicator.config(fg='red', text="●")
            if device_info:
                device_info.config(text=error_msg, fg='red')
            return
        
        if not address or not address.strip():
            # Empty address is valid
            if status_indicator:
                status_indicator.config(fg='gray', text="●")
            if device_info:
                device_info.config(text="")
            return
        
        # Try to identify device (non-blocking, quick timeout)
        if status_indicator:
            status_indicator.config(fg='orange', text="●")  # Testing
        if device_info:
            device_info.config(text="Identifying device...", fg='#666666')
        
        # Use after() to avoid blocking UI
        def identify_async():
            success, result = self._query_device_idn(address, timeout_ms=1500)
            if success:
                if status_indicator:
                    status_indicator.config(fg='green', text="●")
                if device_info:
                    # Truncate long IDN strings
                    display_text = result if len(result) <= 60 else result[:57] + "..."
                    device_info.config(text=display_text, fg='green')
            else:
                if status_indicator:
                    status_indicator.config(fg='gray', text="●")
                if device_info:
                    device_info.config(text="", fg='#666666')
        
        # Schedule async identification
        if hasattr(gui, 'master'):
            gui.master.after(100, identify_async)
    
    def _test_connection(self, gui: object, device_type: str) -> None:
        """Test connection to device without full connection
        
        Args:
            gui: GUI instance
            device_type: 'smu', 'psu', or 'temp'
        """
        # Get address based on device type
        if device_type == 'smu':
            address_var = gui.keithley_address_var
            status_indicator = getattr(gui, 'smu_status_indicator', None)
            device_info = getattr(gui, 'smu_device_info', None)
            test_button = getattr(gui, 'iv_test_button', None)
        elif device_type == 'psu':
            address_var = gui.psu_address_var
            status_indicator = getattr(gui, 'psu_status_indicator', None)
            device_info = getattr(gui, 'psu_device_info', None)
            test_button = getattr(gui, 'psu_test_button', None)
        elif device_type == 'temp':
            address_var = gui.temp_address_var
            status_indicator = getattr(gui, 'temp_status_indicator', None)
            device_info = getattr(gui, 'temp_device_info', None)
            test_button = getattr(gui, 'temp_test_button', None)
        else:
            return
        
        address = address_var.get()
        
        if not address or not address.strip():
            if device_info:
                device_info.config(text="No address specified", fg='red')
            return
        
        # Disable button during test
        if test_button:
            test_button.config(state='disabled', text="Testing...")
        
        if status_indicator:
            status_indicator.config(fg='orange', text="●")
        if device_info:
            device_info.config(text="Testing connection...", fg='orange')
        
        def test_async():
            # Validate format first
            is_valid, error_msg = self._validate_address_format(address)
            if not is_valid:
                if status_indicator:
                    status_indicator.config(fg='red', text="●")
                if device_info:
                    device_info.config(text=error_msg, fg='red')
                if test_button:
                    test_button.config(state='normal', text="Test")
                return
            
            # Try to query device
            success, result = self._query_device_idn(address, timeout_ms=3000)
            
            if success:
                if status_indicator:
                    status_indicator.config(fg='green', text="●")
                if device_info:
                    display_text = result if len(result) <= 60 else result[:57] + "..."
                    device_info.config(text=f"✓ {display_text}", fg='green')
            else:
                if status_indicator:
                    status_indicator.config(fg='red', text="●")
                if device_info:
                    device_info.config(text=f"✗ {result}", fg='red')
            
            if test_button:
                test_button.config(state='normal', text="Test")
        
        # Schedule async test
        if hasattr(gui, 'master'):
            gui.master.after(100, test_async)
    
    def _build_optical_section(self, parent: tk.Misc, gui: object) -> None:
        """Build collapsible optical excitation configuration section"""
        # Container frame
        optical_container = tk.Frame(parent, bg=self.COLOR_BG)
        optical_container.pack(fill='x', pady=(0, 10))
        
        # Toggle button and label
        toggle_frame = tk.Frame(optical_container, bg=self.COLOR_BG)
        toggle_frame.pack(fill='x')
        
        gui.optical_expanded_var = tk.BooleanVar(value=False)
        
        # Collapsible frame (create first so we can reference it in lambda)
        optical_frame = tk.LabelFrame(optical_container, text="", font=self.FONT_MAIN, bg=self.COLOR_BG, padx=10, pady=10)
        optical_frame.pack_forget()  # Initially hidden
        
        toggle_btn = tk.Button(
            toggle_frame,
            text="▶",
            font=("Arial", 10),
            bg=self.COLOR_BG,
            fg='black',
            relief='flat',
            command=lambda: self._toggle_optical_section(gui, optical_frame, toggle_btn)
        )
        toggle_btn.pack(side='left', padx=(0, 5))
        
        tk.Label(toggle_frame, text="Optical Excitation (LED/Laser) - Optional", 
                font=self.FONT_MAIN, bg=self.COLOR_BG).pack(side='left')
        
        # Optical type
        tk.Label(optical_frame, text="Type:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5)
        optical_types = ['None', 'LED', 'Laser']
        gui.optical_type_var = tk.StringVar(value='None')
        gui.optical_type_combo = ttk.Combobox(optical_frame, textvariable=gui.optical_type_var, values=optical_types,
                                              font=self.FONT_MAIN, width=20, state='readonly')
        gui.optical_type_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 10))
        gui.optical_type_combo.bind('<<ComboboxSelected>>', 
                                   lambda e: self._update_optical_ui(gui, optical_frame))
        
        # LED-specific fields (initially hidden)
        gui.optical_led_frame = tk.Frame(optical_frame, bg=self.COLOR_BG)
        gui.optical_led_frame.grid(row=1, column=0, columnspan=3, sticky='ew', pady=5)
        
        # Laser-specific fields (initially hidden)
        gui.optical_laser_frame = tk.Frame(optical_frame, bg=self.COLOR_BG)
        gui.optical_laser_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=5)
        
        optical_frame.columnconfigure(1, weight=1)
        gui.optical_config_frame = optical_frame
        gui.optical_toggle_button = toggle_btn
    
    def _toggle_optical_section(self, gui: object, frame: tk.Frame, button: tk.Button) -> None:
        """Toggle visibility of optical configuration section"""
        if gui.optical_expanded_var.get():
            frame.pack_forget()
            button.config(text="▶")
            gui.optical_expanded_var.set(False)
        else:
            frame.pack(fill='x', pady=(0, 10))
            button.config(text="▼")
            gui.optical_expanded_var.set(True)
    
    def _update_optical_ui(self, gui: object, parent: tk.Frame) -> None:
        """Update optical UI based on selected type"""
        opt_type = gui.optical_type_var.get()
        
        # Hide all sub-frames
        for widget in gui.optical_led_frame.winfo_children():
            widget.destroy()
        for widget in gui.optical_laser_frame.winfo_children():
            widget.destroy()
        
        if opt_type == 'LED':
            # LED configuration
            tk.Label(gui.optical_led_frame, text="Units:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5)
            led_units = ['mA', 'V']
            gui.optical_led_units_var = tk.StringVar(value='mA')
            ttk.Combobox(gui.optical_led_frame, textvariable=gui.optical_led_units_var, values=led_units,
                        font=self.FONT_MAIN, width=15, state='readonly').grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_led_frame, text="Channels (e.g., 380nm:1,420nm:2):", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=1, column=0, sticky='w', pady=5)
            gui.optical_led_channels_var = tk.StringVar(value="380nm:1,420nm:2")
            ttk.Entry(gui.optical_led_frame, textvariable=gui.optical_led_channels_var, 
                     font=self.FONT_MAIN, width=30).grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_led_frame, text="Min:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=2, column=0, sticky='w', pady=5)
            gui.optical_led_min_var = tk.StringVar(value="0.0")
            ttk.Entry(gui.optical_led_frame, textvariable=gui.optical_led_min_var, 
                     font=self.FONT_MAIN, width=15).grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_led_frame, text="Max:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=2, column=2, sticky='w', pady=5, padx=(10, 0))
            gui.optical_led_max_var = tk.StringVar(value="30.0")
            ttk.Entry(gui.optical_led_frame, textvariable=gui.optical_led_max_var, 
                     font=self.FONT_MAIN, width=15).grid(row=2, column=3, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_led_frame, text="Default Channel:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=3, column=0, sticky='w', pady=5)
            gui.optical_led_default_channel_var = tk.StringVar(value="380nm")
            ttk.Entry(gui.optical_led_frame, textvariable=gui.optical_led_default_channel_var, 
                     font=self.FONT_MAIN, width=15).grid(row=3, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            gui.optical_led_frame.columnconfigure(1, weight=1)
            gui.optical_led_frame.pack(fill='x')
            
        elif opt_type == 'Laser':
            # Laser configuration
            tk.Label(gui.optical_laser_frame, text="Driver:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=0, column=0, sticky='w', pady=5)
            laser_drivers = ['Oxxius']
            gui.optical_laser_driver_var = tk.StringVar(value='Oxxius')
            ttk.Combobox(gui.optical_laser_frame, textvariable=gui.optical_laser_driver_var, values=laser_drivers,
                        font=self.FONT_MAIN, width=20, state='readonly').grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_laser_frame, text="Address:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=1, column=0, sticky='w', pady=5)
            gui.optical_laser_address_var = tk.StringVar(value="COM4")
            ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_address_var, 
                     font=self.FONT_MAIN, width=30).grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_laser_frame, text="Baud:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=2, column=0, sticky='w', pady=5)
            gui.optical_laser_baud_var = tk.StringVar(value="19200")
            ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_baud_var, 
                     font=self.FONT_MAIN, width=15).grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_laser_frame, text="Units:", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=3, column=0, sticky='w', pady=5)
            laser_units = ['mW']
            gui.optical_laser_units_var = tk.StringVar(value='mW')
            ttk.Combobox(gui.optical_laser_frame, textvariable=gui.optical_laser_units_var, values=laser_units,
                        font=self.FONT_MAIN, width=15, state='readonly').grid(row=3, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_laser_frame, text="Wavelength (nm):", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=4, column=0, sticky='w', pady=5)
            gui.optical_laser_wavelength_var = tk.StringVar(value="405")
            ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_wavelength_var, 
                     font=self.FONT_MAIN, width=15).grid(row=4, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_laser_frame, text="Min (mW):", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=5, column=0, sticky='w', pady=5)
            gui.optical_laser_min_var = tk.StringVar(value="0.0")
            ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_min_var, 
                     font=self.FONT_MAIN, width=15).grid(row=5, column=1, sticky='ew', pady=5, padx=(10, 10))
            
            tk.Label(gui.optical_laser_frame, text="Max (mW):", font=self.FONT_MAIN, bg=self.COLOR_BG).grid(row=5, column=2, sticky='w', pady=5, padx=(10, 0))
            gui.optical_laser_max_var = tk.StringVar(value="10.0")
            ttk.Entry(gui.optical_laser_frame, textvariable=gui.optical_laser_max_var, 
                     font=self.FONT_MAIN, width=15).grid(row=5, column=3, sticky='ew', pady=5, padx=(10, 10))
            
            gui.optical_laser_frame.columnconfigure(1, weight=1)
            gui.optical_laser_frame.pack(fill='x')
    
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
    # TAB 5: Notes
    # ------------------------------------------------------------------
    def _create_notes_tab(self, notebook: ttk.Notebook) -> None:
        """Create the Notes tab for device and sample notes"""
        gui = self.gui
        
        tab = tk.Frame(notebook, bg=self.COLOR_BG)
        notebook.add(tab, text="  Notes  ")
        
        # Configure grid - split view: left (current notes) and right (previous devices)
        tab.columnconfigure(0, weight=2)  # Left side - current notes (more space)
        tab.columnconfigure(1, weight=1)  # Right side - previous devices (less space)
        tab.rowconfigure(1, weight=1)
        
        # Control frame at top (spans both columns)
        control_frame = tk.Frame(tab, bg=self.COLOR_BG, padx=20, pady=10)
        control_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        control_frame.columnconfigure(1, weight=1)
        
        # Notes type selector
        tk.Label(control_frame, text="Notes Type:", font=self.FONT_HEADING, bg=self.COLOR_BG).grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        gui.notes_type_var = tk.StringVar(value="device")
        notes_type_frame = tk.Frame(control_frame, bg=self.COLOR_BG)
        notes_type_frame.grid(row=0, column=1, sticky="w")
        
        tk.Radiobutton(
            notes_type_frame,
            text="Device Notes",
            variable=gui.notes_type_var,
            value="device",
            font=self.FONT_MAIN,
            bg=self.COLOR_BG,
            command=lambda: self._switch_notes_type(gui, "device")
        ).pack(side="left", padx=5)
        
        tk.Radiobutton(
            notes_type_frame,
            text="Sample Notes",
            variable=gui.notes_type_var,
            value="sample",
            font=self.FONT_MAIN,
            bg=self.COLOR_BG,
            command=lambda: self._switch_notes_type(gui, "sample")
        ).pack(side="left", padx=5)
        
        # Save button
        save_btn = tk.Button(
            control_frame,
            text="Save Notes",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg="white",
            command=lambda: self._save_notes(gui),
            padx=15,
            pady=5
        )
        save_btn.grid(row=0, column=2, sticky="e", padx=(20, 0))
        gui.notes_save_button = save_btn
        
        # Status label
        gui.notes_status_label = tk.Label(
            control_frame,
            text="",
            font=self.FONT_MAIN,
            bg=self.COLOR_BG,
            fg=self.COLOR_SECONDARY
        )
        gui.notes_status_label.grid(row=0, column=3, sticky="e", padx=(10, 0))
        
        # LEFT SIDE - Current notes text area
        left_frame = tk.Frame(tab, bg=self.COLOR_BG)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 20))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)  # Text widget row
        
        # Toolbar with formatting and utility buttons
        toolbar_frame = tk.Frame(left_frame, bg=self.COLOR_BG, pady=5)
        toolbar_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        # Date/Time button
        date_btn = tk.Button(
            toolbar_frame,
            text="📅 Date/Time",
            font=self.FONT_MAIN,
            bg="#e3f2fd",
            fg="#1976d2",
            command=lambda: self._insert_datetime(gui),
            padx=8,
            pady=3
        )
        date_btn.pack(side="left", padx=2)
        
        # Measurement Details button
        meas_btn = tk.Button(
            toolbar_frame,
            text="📊 Measurement Details",
            font=self.FONT_MAIN,
            bg="#e3f2fd",
            fg="#1976d2",
            command=lambda: self._insert_measurement_details(gui),
            padx=8,
            pady=3
        )
        meas_btn.pack(side="left", padx=2)
        
        # Separator
        tk.Frame(toolbar_frame, bg="#ccc", width=1).pack(side="left", padx=5, fill="y", pady=2)
        
        # Bold button
        bold_btn = tk.Button(
            toolbar_frame,
            text="B",
            font=("Arial", 12, "bold"),
            bg="#f5f5f5",
            fg="black",
            command=lambda: self._toggle_bold(gui),
            padx=8,
            pady=3,
            width=3
        )
        bold_btn.pack(side="left", padx=2)
        
        # Italic button
        italic_btn = tk.Button(
            toolbar_frame,
            text="I",
            font=("Arial", 12, "italic"),
            bg="#f5f5f5",
            fg="black",
            command=lambda: self._toggle_italic(gui),
            padx=8,
            pady=3,
            width=3
        )
        italic_btn.pack(side="left", padx=2)
        
        # Text widget with scrollbar (enable undo/redo and formatting)
        gui.notes_text = tk.Text(
            left_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="white",
            fg="black",
            padx=10,
            pady=10,
            relief=tk.SOLID,
            borderwidth=1,
            undo=True,
            maxundo=50
        )
        gui.notes_text.grid(row=1, column=0, sticky="nsew")
        
        notes_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=gui.notes_text.yview)
        notes_scrollbar.grid(row=1, column=1, sticky="ns")
        gui.notes_text.configure(yscrollcommand=notes_scrollbar.set)
        
        # Info label with keyboard shortcuts hint
        info_label = tk.Label(
            left_frame,
            text="Auto-saves after 500ms of no typing. | Shortcuts: Ctrl+S (Save), Ctrl+D (Date/Time), Ctrl+Z (Undo), Ctrl+Y (Redo), Ctrl+B (Bold), Ctrl+I (Italic)",
            font=("Segoe UI", 8),
            bg=self.COLOR_BG,
            fg=self.COLOR_SECONDARY,
            anchor="w"
        )
        info_label.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        # RIGHT SIDE - Previous devices' notes
        right_frame = tk.Frame(tab, bg=self.COLOR_BG)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 20))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)
        
        # Get previous two devices
        previous_devices = self._get_previous_devices(gui)
        
        # Previous device 1 (most recent)
        if len(previous_devices) > 0:
            prev1_frame = tk.LabelFrame(right_frame, text=f"Previous Device 1: {previous_devices[0]['name']}", 
                                       font=self.FONT_MAIN, bg=self.COLOR_BG, padx=5, pady=5)
            prev1_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
            prev1_frame.columnconfigure(0, weight=1)
            prev1_frame.rowconfigure(0, weight=1)
            
            gui.prev_device1_text = tk.Text(
                prev1_frame,
                wrap=tk.WORD,
                font=("Consolas", 9),
                bg="white",
                fg="black",
                padx=8,
                pady=8,
                relief=tk.SOLID,
                borderwidth=1,
                height=15,
                undo=True,
                maxundo=50
            )
            gui.prev_device1_text.grid(row=0, column=0, sticky="nsew")
            
            prev1_scrollbar = ttk.Scrollbar(prev1_frame, orient="vertical", command=gui.prev_device1_text.yview)
            prev1_scrollbar.grid(row=0, column=1, sticky="ns")
            gui.prev_device1_text.configure(yscrollcommand=prev1_scrollbar.set)
            
            # Load notes for previous device 1
            self._load_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text)
            
            # Auto-save on focus loss and track changes
            gui.prev_device1_text.bind("<FocusOut>", lambda e: self._save_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text))
            gui.prev_device1_text.bind("<KeyRelease>", lambda e: self._mark_prev_device1_changed(gui))
        else:
            # Empty frame if no previous device
            empty_frame1 = tk.LabelFrame(right_frame, text="Previous Device 1: None", 
                                        font=self.FONT_MAIN, bg=self.COLOR_BG, padx=5, pady=5)
            empty_frame1.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
            tk.Label(empty_frame1, text="No previous device", font=self.FONT_MAIN, 
                    bg=self.COLOR_BG, fg=self.COLOR_SECONDARY).pack(pady=20)
            gui.prev_device1_text = None
        
        # Previous device 2 (second most recent)
        if len(previous_devices) > 1:
            prev2_frame = tk.LabelFrame(right_frame, text=f"Previous Device 2: {previous_devices[1]['name']}", 
                                       font=self.FONT_MAIN, bg=self.COLOR_BG, padx=5, pady=5)
            prev2_frame.grid(row=1, column=0, sticky="nsew")
            prev2_frame.columnconfigure(0, weight=1)
            prev2_frame.rowconfigure(0, weight=1)
            
            gui.prev_device2_text = tk.Text(
                prev2_frame,
                wrap=tk.WORD,
                font=("Consolas", 9),
                bg="white",
                fg="black",
                padx=8,
                pady=8,
                relief=tk.SOLID,
                borderwidth=1,
                height=15,
                undo=True,
                maxundo=50
            )
            gui.prev_device2_text.grid(row=0, column=0, sticky="nsew")
            
            prev2_scrollbar = ttk.Scrollbar(prev2_frame, orient="vertical", command=gui.prev_device2_text.yview)
            prev2_scrollbar.grid(row=0, column=1, sticky="ns")
            gui.prev_device2_text.configure(yscrollcommand=prev2_scrollbar.set)
            
            # Load notes for previous device 2
            self._load_previous_device_notes(gui, previous_devices[1], gui.prev_device2_text)
            
            # Auto-save on focus loss and track changes
            gui.prev_device2_text.bind("<FocusOut>", lambda e: self._save_previous_device_notes(gui, previous_devices[1], gui.prev_device2_text))
            gui.prev_device2_text.bind("<KeyRelease>", lambda e: self._mark_prev_device2_changed(gui))
        else:
            # Empty frame if no second previous device
            empty_frame2 = tk.LabelFrame(right_frame, text="Previous Device 2: None", 
                                        font=self.FONT_MAIN, bg=self.COLOR_BG, padx=5, pady=5)
            empty_frame2.grid(row=1, column=0, sticky="nsew")
            tk.Label(empty_frame2, text="No previous device", font=self.FONT_MAIN, 
                    bg=self.COLOR_BG, fg=self.COLOR_SECONDARY).pack(pady=20)
            gui.prev_device2_text = None
        
        # Load initial notes
        self._load_notes(gui)
        
        # Track last saved content for change detection
        gui.notes_last_saved = gui.notes_text.get("1.0", tk.END)
        gui.notes_changed = False
        if gui.prev_device1_text:
            gui.prev_device1_last_saved = gui.prev_device1_text.get("1.0", tk.END)
            gui.prev_device1_changed = False
        if gui.prev_device2_text:
            gui.prev_device2_last_saved = gui.prev_device2_text.get("1.0", tk.END)
            gui.prev_device2_changed = False
        
        # Auto-save on focus loss and every change (immediate save)
        gui.notes_text.bind("<FocusOut>", lambda e: self._auto_save_notes(gui))
        gui.notes_text.bind("<KeyRelease>", lambda e: self._on_notes_key_release(gui))
        
        # Keyboard shortcuts for Notes tab
        self._setup_notes_keyboard_shortcuts(gui, tab)
        
        # Auto-save on tab switch (CRITICAL - save before leaving Notes tab)
        def on_tab_change(event):
            try:
                current_tab_text = event.widget.tab('current')['text'].strip()
                if current_tab_text == 'Notes':
                    # Entering Notes tab - reload notes
                    self._load_notes(gui)
                    # Reload previous devices' notes (refresh the previous devices list)
                    previous_devices = self._get_previous_devices(gui)
                    if len(previous_devices) > 0 and hasattr(gui, 'prev_device1_text') and gui.prev_device1_text:
                        self._load_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text)
                        gui.prev_device1_last_saved = gui.prev_device1_text.get("1.0", tk.END)
                        # Update label with device name
                        prev1_frame = gui.prev_device1_text.master
                        if isinstance(prev1_frame, tk.LabelFrame):
                            prev1_frame.config(text=f"Previous Device 1: {previous_devices[0]['name']}")
                    if len(previous_devices) > 1 and hasattr(gui, 'prev_device2_text') and gui.prev_device2_text:
                        self._load_previous_device_notes(gui, previous_devices[1], gui.prev_device2_text)
                        gui.prev_device2_last_saved = gui.prev_device2_text.get("1.0", tk.END)
                        # Update label with device name
                        prev2_frame = gui.prev_device2_text.master
                        if isinstance(prev2_frame, tk.LabelFrame):
                            prev2_frame.config(text=f"Previous Device 2: {previous_devices[1]['name']}")
                else:
                    # Leaving Notes tab - FORCE SAVE immediately (user lost notes before)
                    if hasattr(gui, 'notes_text') and hasattr(gui, 'notes_type_var'):
                        self._save_notes(gui)  # Use _save_notes instead of _auto_save_notes for immediate save
                    # Save previous devices' notes
                    if hasattr(gui, 'prev_device1_text') and gui.prev_device1_text:
                        previous_devices = self._get_previous_devices(gui)
                        if len(previous_devices) > 0:
                            self._save_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text)
                    if hasattr(gui, 'prev_device2_text') and gui.prev_device2_text:
                        previous_devices = self._get_previous_devices(gui)
                        if len(previous_devices) > 1:
                            self._save_previous_device_notes(gui, previous_devices[1], gui.prev_device2_text)
            except Exception:
                pass  # Silently ignore errors during tab switching
        
        notebook.bind("<<NotebookTabChanged>>", on_tab_change)
        
        # Start periodic auto-save (every 10 seconds)
        self._start_auto_save_timer(gui)
        
        # Start polling for device changes in Sample_GUI (to auto-reload device notes)
        self._start_device_change_polling(gui)
        
        self.widgets["notes_tab"] = tab
    
    def _get_previous_devices(self, gui) -> List[Dict[str, Any]]:
        """Get the previous two devices from the same sample (e.g., if on A2, show A1; if on A3, show A2 and A1)"""
        previous_devices = []
        
        try:
            # Get current device identifier (A1, A2, etc.)
            current_device_id = None
            if hasattr(gui, 'device_section_and_number'):
                current_device_id = gui.device_section_and_number
            
            # Get sample name (D104, etc.)
            sample_name = None
            if hasattr(gui, 'sample_gui') and gui.sample_gui:
                sample_name = getattr(gui.sample_gui, 'current_device_name', None)
                if not sample_name:
                    sample_type_var = getattr(gui.sample_gui, 'sample_type_var', None)
                    if sample_type_var and hasattr(sample_type_var, 'get'):
                        sample_name = sample_type_var.get()
            
            if not sample_name:
                sample_name = getattr(gui, 'sample_name_var', None)
                if sample_name and hasattr(sample_name, 'get'):
                    sample_name = sample_name.get()
            
            if not current_device_id or not sample_name:
                return previous_devices
            
            # Get device list to find current device's position
            device_list = getattr(gui, 'device_list', [])
            if not device_list:
                return previous_devices
            
            # Find current device index in the list
            current_index = None
            for idx, device_key in enumerate(device_list):
                # Convert device key to identifier (A1, A2, etc.)
                if hasattr(gui, 'convert_to_name'):
                    device_identifier = gui.convert_to_name(idx)
                    if device_identifier == current_device_id:
                        current_index = idx
                        break
            
            if current_index is None:
                return previous_devices
            
            # Get previous devices by going backwards in the device list
            from pathlib import Path
            save_root = Path(getattr(gui, 'default_save_root', Path.home() / "Documents" / "Data_folder"))
            sample_folder = save_root / sample_name.replace(" ", "_")
            
            if not sample_folder.exists():
                return previous_devices
            
            # Look for previous devices in sequence (A1 if on A2, A2 and A1 if on A3, etc.)
            for offset in range(1, 3):  # Get previous 2 devices
                prev_index = current_index - offset
                if prev_index >= 0 and prev_index < len(device_list):
                    # Convert to device identifier
                    if hasattr(gui, 'convert_to_name'):
                        prev_device_id = gui.convert_to_name(prev_index)
                        # Build path: {save_root}/{sample_name}/{letter}/{number}/device_info.json
                        letter = prev_device_id[0] if len(prev_device_id) > 0 else "A"
                        number = prev_device_id[1:] if len(prev_device_id) > 1 else "1"
                        device_folder = sample_folder / letter / number
                        info_path = device_folder / "device_info.json"
                        
                        if info_path.exists():
                            try:
                                import json
                                with info_path.open("r", encoding="utf-8") as f:
                                    device_info = json.load(f)
                                    previous_devices.append({
                                        "name": prev_device_id,
                                        "folder": device_folder,
                                        "last_modified": device_info.get("last_modified", ""),
                                        "device_id": prev_device_id
                                    })
                            except Exception:
                                continue
                        else:
                            # Device folder exists but no notes yet - still add it
                            previous_devices.append({
                                "name": prev_device_id,
                                "folder": device_folder,
                                "last_modified": "",
                                "device_id": prev_device_id
                            })
            
        except Exception as e:
            print(f"Error getting previous devices: {e}")
        
        return previous_devices
    
    def _load_previous_device_notes(self, gui, device_info: Dict[str, Any], text_widget: tk.Text) -> None:
        """Load notes for a previous device"""
        try:
            # Disable undo temporarily while loading
            text_widget.config(undo=False)
            text_widget.delete("1.0", tk.END)
            
            # device_info["folder"] is already the device folder path
            info_path = device_info["folder"] / "device_info.json"
            if info_path.exists():
                import json
                with info_path.open("r", encoding="utf-8") as f:
                    device_data = json.load(f)
                    notes = device_data.get("notes", "")
                    if notes:
                        text_widget.insert("1.0", notes)
            # Re-enable undo and reset stack
            text_widget.config(undo=True)
            text_widget.edit_reset()
        except Exception as e:
            print(f"Error loading previous device notes: {e}")
            # Make sure undo is re-enabled even on error
            try:
                text_widget.config(undo=True)
            except:
                pass
    
    def _save_previous_device_notes(self, gui, device_info: Dict[str, Any], text_widget: tk.Text) -> None:
        """Save notes for a previous device"""
        try:
            notes_content = text_widget.get("1.0", tk.END).strip()
            info_path = device_info["folder"] / "device_info.json"
            
            # Load existing device_info or create new
            device_data = {}
            if info_path.exists():
                import json
                with info_path.open("r", encoding="utf-8") as f:
                    device_data = json.load(f)
            
            # Update notes and metadata
            from datetime import datetime
            device_data["notes"] = notes_content
            device_data["last_modified"] = datetime.now().isoformat(timespec='seconds')
            if "name" not in device_data:
                device_data["name"] = device_info["name"]
            if "created" not in device_data:
                device_data["created"] = datetime.now().isoformat(timespec='seconds')
            
            # Save
            import json
            with info_path.open("w", encoding="utf-8") as f:
                json.dump(device_data, f, indent=2)
        except Exception as e:
            print(f"Error saving previous device notes: {e}")
    
    def _mark_notes_changed(self, gui) -> None:
        """Mark that notes have been changed (for auto-save detection)"""
        if hasattr(gui, 'notes_text'):
            gui.notes_changed = True
    
    def _on_notes_key_release(self, gui) -> None:
        """Handle key release - mark changed and auto-save immediately"""
        self._mark_notes_changed(gui)
        # Auto-save immediately on change (debounced slightly)
        if hasattr(gui, '_notes_save_timer'):
            gui.master.after_cancel(gui._notes_save_timer)
        # Save after 500ms of no typing (debounce)
        gui._notes_save_timer = gui.master.after(500, lambda: self._auto_save_notes(gui))
    
    def _mark_prev_device1_changed(self, gui) -> None:
        """Mark that previous device 1 notes have been changed"""
        if hasattr(gui, 'prev_device1_text') and gui.prev_device1_text:
            gui.prev_device1_changed = True
    
    def _mark_prev_device2_changed(self, gui) -> None:
        """Mark that previous device 2 notes have been changed"""
        if hasattr(gui, 'prev_device2_text') and gui.prev_device2_text:
            gui.prev_device2_changed = True
    
    def _setup_notes_keyboard_shortcuts(self, gui, tab: tk.Frame) -> None:
        """Setup keyboard shortcuts for Notes tab: Ctrl+S (save), Ctrl+Z (undo), Ctrl+Y (redo)"""
        def get_focused_text_widget():
            """Get the currently focused text widget"""
            focused = gui.master.focus_get()
            if focused == gui.notes_text:
                return gui.notes_text
            elif hasattr(gui, 'prev_device1_text') and gui.prev_device1_text and focused == gui.prev_device1_text:
                return gui.prev_device1_text
            elif hasattr(gui, 'prev_device2_text') and gui.prev_device2_text and focused == gui.prev_device2_text:
                return gui.prev_device2_text
            return None
        
        def on_save(event):
            """Ctrl+S: Quick save notes"""
            text_widget = get_focused_text_widget()
            if text_widget == gui.notes_text:
                # Save main notes
                self._save_notes(gui)
                # Show quick save confirmation
                if hasattr(gui, 'notes_status_label'):
                    original_text = gui.notes_status_label.cget("text")
                    gui.notes_status_label.config(text="✓ Saved!", fg=self.COLOR_SUCCESS)
                    # Reset after 2 seconds
                    if hasattr(gui, 'master'):
                        gui.master.after(2000, lambda: gui.notes_status_label.config(text=original_text, fg=self.COLOR_INFO))
            elif text_widget == gui.prev_device1_text:
                # Save previous device 1 notes
                previous_devices = self._get_previous_devices(gui)
                if len(previous_devices) > 0:
                    self._save_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text)
            elif text_widget == gui.prev_device2_text:
                # Save previous device 2 notes
                previous_devices = self._get_previous_devices(gui)
                if len(previous_devices) > 1:
                    self._save_previous_device_notes(gui, previous_devices[1], gui.prev_device2_text)
            return "break"  # Prevent default behavior
        
        def on_undo(event):
            """Ctrl+Z: Undo"""
            text_widget = get_focused_text_widget()
            if text_widget:
                try:
                    text_widget.edit_undo()
                except tk.TclError:
                    pass  # No undo available
            return "break"
        
        def on_redo(event):
            """Ctrl+Y: Redo"""
            text_widget = get_focused_text_widget()
            if text_widget:
                try:
                    text_widget.edit_redo()
                except tk.TclError:
                    pass  # No redo available
            return "break"
        
        # Bind shortcuts to the master window (works when Notes tab is active)
        # Also bind to individual text widgets for better focus handling
        def on_datetime(event):
            """Ctrl+D: Insert date/time"""
            self._insert_datetime(gui)
            return "break"
        
        def on_bold(event):
            """Ctrl+B: Toggle bold"""
            self._toggle_bold(gui)
            return "break"
        
        def on_italic(event):
            """Ctrl+I: Toggle italic"""
            self._toggle_italic(gui)
            return "break"
        
        gui.notes_text.bind("<Control-s>", on_save)
        gui.notes_text.bind("<Control-S>", on_save)
        gui.notes_text.bind("<Control-d>", on_datetime)
        gui.notes_text.bind("<Control-D>", on_datetime)
        gui.notes_text.bind("<Control-z>", on_undo)
        gui.notes_text.bind("<Control-Z>", on_undo)
        gui.notes_text.bind("<Control-y>", on_redo)
        gui.notes_text.bind("<Control-Y>", on_redo)
        gui.notes_text.bind("<Control-b>", on_bold)
        gui.notes_text.bind("<Control-B>", on_bold)
        gui.notes_text.bind("<Control-i>", on_italic)
        gui.notes_text.bind("<Control-I>", on_italic)
        
        if hasattr(gui, 'prev_device1_text') and gui.prev_device1_text:
            gui.prev_device1_text.bind("<Control-s>", on_save)
            gui.prev_device1_text.bind("<Control-S>", on_save)
            gui.prev_device1_text.bind("<Control-z>", on_undo)
            gui.prev_device1_text.bind("<Control-Z>", on_undo)
            gui.prev_device1_text.bind("<Control-y>", on_redo)
            gui.prev_device1_text.bind("<Control-Y>", on_redo)
        
        if hasattr(gui, 'prev_device2_text') and gui.prev_device2_text:
            gui.prev_device2_text.bind("<Control-s>", on_save)
            gui.prev_device2_text.bind("<Control-S>", on_save)
            gui.prev_device2_text.bind("<Control-z>", on_undo)
            gui.prev_device2_text.bind("<Control-Z>", on_undo)
            gui.prev_device2_text.bind("<Control-y>", on_redo)
            gui.prev_device2_text.bind("<Control-Y>", on_redo)
    
    def _insert_datetime(self, gui) -> None:
        """Insert current date and time at cursor position"""
        from datetime import datetime
        dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        gui.notes_text.insert(tk.INSERT, dt_str)
    
    def _insert_measurement_details(self, gui) -> None:
        """Insert current measurement details from Measurement GUI or TSP Testing GUI"""
        details = []
        
        # Try to get details from TSP Testing GUI first (if open)
        tsp_details = self._get_tsp_testing_details(gui)
        if tsp_details:
            details.append("=== Pulse Testing Details ===")
            details.extend(tsp_details)
            details.append("")
        
        # Get details from Measurement GUI
        meas_details = self._get_measurement_gui_details(gui)
        if meas_details:
            if tsp_details:
                details.append("=== Measurement GUI Details ===")
            details.extend(meas_details)
        
        if not details:
            details.append("No active measurement parameters found.")
        
        # Insert at cursor position
        text_to_insert = "\n".join(details) + "\n\n"
        gui.notes_text.insert(tk.INSERT, text_to_insert)
    
    def _get_tsp_testing_details(self, gui) -> List[str]:
        """Get measurement details from TSP Testing GUI if it's open"""
        details = []
        try:
            # Check if TSP Testing GUI is open by searching all Toplevel windows
            # TSP Testing GUI is a Toplevel window
            root = gui.master.winfo_toplevel()
            tsp_gui = None
            
            # Search through all windows
            def find_tsp_window(widget):
                if isinstance(widget, tk.Toplevel):
                    try:
                        title = widget.title()
                        if 'Pulse Testing' in title or 'TSP' in title:
                            return widget
                    except:
                        pass
                # Check children
                for child in widget.winfo_children():
                    result = find_tsp_window(child)
                    if result:
                        return result
                return None
            
            tsp_gui = find_tsp_window(root)
            
            if tsp_gui:
                    
                    # Get test name
                    if hasattr(tsp_gui, 'test_var'):
                        test_name = tsp_gui.test_var.get()
                        if test_name:
                            details.append(f"Test Type: {test_name}")
                    
                    # Get parameters
                    if hasattr(tsp_gui, 'param_vars'):
                        params = {}
                        for param_name, param_info in tsp_gui.param_vars.items():
                            try:
                                var = param_info["var"]
                                param_type = param_info["type"]
                                value_str = var.get()
                                
                                if param_type == "list":
                                    params[param_name] = value_str
                                else:
                                    params[param_name] = value_str
                            except:
                                pass
                        
                        # Format key parameters
                        if 'pulse_voltage' in params:
                            details.append(f"Pulse Voltage: {params['pulse_voltage']} V")
                        if 'pulse_width' in params:
                            details.append(f"Pulse Width: {params['pulse_width']} ms")
                        if 'read_voltage' in params:
                            details.append(f"Read Voltage: {params['read_voltage']} V")
                        if 'num_cycles' in params:
                            details.append(f"Number of Cycles: {params['num_cycles']}")
                        if 'num_pulses' in params:
                            details.append(f"Number of Pulses: {params['num_pulses']}")
                        if 'set_voltage' in params:
                            details.append(f"SET Voltage: {params['set_voltage']} V")
                        if 'reset_voltage' in params:
                            details.append(f"RESET Voltage: {params['reset_voltage']} V")
                    
                    # Get device address
                    if hasattr(tsp_gui, 'addr_var'):
                        addr = tsp_gui.addr_var.get()
                        if addr:
                            details.append(f"Device Address: {addr}")
                    
                    # Get system
                    if hasattr(tsp_gui, 'current_system_name'):
                        system = tsp_gui.current_system_name
                        if system:
                            details.append(f"System: {system.upper()}")
        except Exception as e:
            print(f"Error getting TSP Testing details: {e}")
        
        return details
    
    def _get_measurement_gui_details(self, gui) -> List[str]:
        """Get measurement details from Measurement GUI"""
        details = []
        try:
            # Measurement type
            if hasattr(gui, 'excitation_var'):
                meas_type = gui.excitation_var.get()
                if meas_type:
                    details.append(f"Measurement Type: {meas_type}")
            
            # Sweep mode and type
            if hasattr(gui, 'sweep_mode_var'):
                sweep_mode = gui.sweep_mode_var.get()
                if sweep_mode:
                    details.append(f"Sweep Mode: {sweep_mode}")
            
            if hasattr(gui, 'sweep_type_var'):
                sweep_type = gui.sweep_type_var.get()
                if sweep_type:
                    details.append(f"Sweep Type: {sweep_type}")
            
            # Voltage parameters (try common attribute names)
            voltage_params = []
            for attr in ['start_voltage_var', 'stop_voltage_var', 'voltage_var', 'max_voltage_var']:
                if hasattr(gui, attr):
                    var = getattr(gui, attr)
                    if hasattr(var, 'get'):
                        val = var.get()
                        if val:
                            param_name = attr.replace('_var', '').replace('_', ' ').title()
                            voltage_params.append(f"{param_name}: {val} V")
            
            if voltage_params:
                details.extend(voltage_params)
            
            # Source mode
            if hasattr(gui, 'source_mode_var'):
                source_mode = gui.source_mode_var.get()
                if source_mode:
                    details.append(f"Source Mode: {source_mode}")
            
            # Device info
            if hasattr(gui, 'device_section_and_number'):
                device = gui.device_section_and_number
                if device:
                    details.append(f"Device: {device}")
            
            # Sample name
            if hasattr(gui, 'sample_name_var'):
                sample_name = gui.sample_name_var.get()
                if sample_name:
                    details.append(f"Sample: {sample_name}")
            
        except Exception as e:
            print(f"Error getting Measurement GUI details: {e}")
        
        return details
    
    def _toggle_bold(self, gui) -> None:
        """Toggle bold formatting for selected text or at cursor"""
        try:
            # Get current selection
            sel_start = gui.notes_text.index(tk.SEL_FIRST) if gui.notes_text.tag_ranges(tk.SEL) else gui.notes_text.index(tk.INSERT)
            sel_end = gui.notes_text.index(tk.SEL_LAST) if gui.notes_text.tag_ranges(tk.SEL) else gui.notes_text.index(tk.INSERT + " wordend")
            
            # Check if bold tag exists
            tags = gui.notes_text.tag_names(sel_start)
            if "bold" in tags:
                # Remove bold
                gui.notes_text.tag_remove("bold", sel_start, sel_end)
            else:
                # Add bold
                gui.notes_text.tag_add("bold", sel_start, sel_end)
                gui.notes_text.tag_config("bold", font=("Consolas", 10, "bold"))
        except Exception:
            # If no selection, just add bold tag at cursor for next typing
            gui.notes_text.tag_add("bold", tk.INSERT)
            gui.notes_text.tag_config("bold", font=("Consolas", 10, "bold"))
    
    def _toggle_italic(self, gui) -> None:
        """Toggle italic formatting for selected text or at cursor"""
        try:
            # Get current selection
            sel_start = gui.notes_text.index(tk.SEL_FIRST) if gui.notes_text.tag_ranges(tk.SEL) else gui.notes_text.index(tk.INSERT)
            sel_end = gui.notes_text.index(tk.SEL_LAST) if gui.notes_text.tag_ranges(tk.SEL) else gui.notes_text.index(tk.INSERT + " wordend")
            
            # Check if italic tag exists
            tags = gui.notes_text.tag_names(sel_start)
            if "italic" in tags:
                # Remove italic
                gui.notes_text.tag_remove("italic", sel_start, sel_end)
            else:
                # Add italic
                gui.notes_text.tag_add("italic", sel_start, sel_end)
                gui.notes_text.tag_config("italic", font=("Consolas", 10, "italic"))
        except Exception:
            # If no selection, just add italic tag at cursor for next typing
            gui.notes_text.tag_add("italic", tk.INSERT)
            gui.notes_text.tag_config("italic", font=("Consolas", 10, "italic"))
    
    def _start_device_change_polling(self, gui) -> None:
        """Poll for device changes (device_section_and_number) and auto-reload device notes"""
        def check_device_change():
            try:
                # Check if we're in device notes mode
                if hasattr(gui, 'notes_type_var') and gui.notes_type_var.get() == "device":
                    # Get current device identifier (A1, A2, etc.)
                    current_device_id = None
                    if hasattr(gui, 'device_section_and_number'):
                        current_device_id = gui.device_section_and_number
                    
                    # Track last known device identifier
                    if not hasattr(gui, '_last_polled_device_id'):
                        gui._last_polled_device_id = current_device_id
                    
                    # If device identifier changed, reload notes
                    if current_device_id != gui._last_polled_device_id:
                        gui._last_polled_device_id = current_device_id
                        # Save current notes before switching
                        self._save_notes(gui)
                        # Small delay to ensure save completes
                        gui.master.update_idletasks()
                        # Reload notes for new device
                        self._load_notes(gui)
                        
                        # Also reload previous devices (they may have changed - e.g., A1 when switching to A2)
                        previous_devices = self._get_previous_devices(gui)
                        if len(previous_devices) > 0 and hasattr(gui, 'prev_device1_text') and gui.prev_device1_text:
                            self._load_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text)
                            gui.prev_device1_last_saved = gui.prev_device1_text.get("1.0", tk.END)
                            # Update label
                            prev1_frame = gui.prev_device1_text.master
                            if isinstance(prev1_frame, tk.LabelFrame):
                                prev1_frame.config(text=f"Previous Device 1: {previous_devices[0]['name']}")
                        if len(previous_devices) > 1 and hasattr(gui, 'prev_device2_text') and gui.prev_device2_text:
                            self._load_previous_device_notes(gui, previous_devices[1], gui.prev_device2_text)
                            gui.prev_device2_last_saved = gui.prev_device2_text.get("1.0", tk.END)
                            # Update label
                            prev2_frame = gui.prev_device2_text.master
                            if isinstance(prev2_frame, tk.LabelFrame):
                                prev2_frame.config(text=f"Previous Device 2: {previous_devices[1]['name']}")
                        
                        if hasattr(gui, 'notes_status_label') and current_device_id:
                            gui.notes_status_label.config(
                                text=f"Switched to device: {current_device_id}",
                                fg=self.COLOR_INFO
                            )
            except Exception as e:
                print(f"Error polling device changes: {e}")
            
            # Poll every 500ms
            if hasattr(gui, 'master') and gui.master.winfo_exists():
                gui.master.after(500, check_device_change)
        
        # Start polling
        if hasattr(gui, 'master'):
            gui.master.after(500, check_device_change)
    
    def _start_auto_save_timer(self, gui) -> None:
        """Start the periodic auto-save timer (every 10 seconds)"""
        def check_and_save():
            try:
                # Check main notes
                if hasattr(gui, 'notes_text') and hasattr(gui, 'notes_changed'):
                    current_content = gui.notes_text.get("1.0", tk.END)
                    if hasattr(gui, 'notes_last_saved') and current_content != gui.notes_last_saved:
                        self._auto_save_notes(gui)
                        gui.notes_last_saved = current_content
                        gui.notes_changed = False
                
                # Check previous device 1
                if hasattr(gui, 'prev_device1_text') and gui.prev_device1_text:
                    current_content = gui.prev_device1_text.get("1.0", tk.END)
                    if hasattr(gui, 'prev_device1_last_saved') and current_content != gui.prev_device1_last_saved:
                        previous_devices = self._get_previous_devices(gui)
                        if len(previous_devices) > 0:
                            self._save_previous_device_notes(gui, previous_devices[0], gui.prev_device1_text)
                            gui.prev_device1_last_saved = current_content
                
                # Check previous device 2
                if hasattr(gui, 'prev_device2_text') and gui.prev_device2_text:
                    current_content = gui.prev_device2_text.get("1.0", tk.END)
                    if hasattr(gui, 'prev_device2_last_saved') and current_content != gui.prev_device2_last_saved:
                        previous_devices = self._get_previous_devices(gui)
                        if len(previous_devices) > 1:
                            self._save_previous_device_notes(gui, previous_devices[1], gui.prev_device2_text)
                            gui.prev_device2_last_saved = current_content
            except Exception as e:
                print(f"Auto-save check error: {e}")
            
            # Schedule next check (10 seconds)
            if hasattr(gui, 'master') and gui.master.winfo_exists():
                gui.master.after(10000, check_and_save)
        
        # Start the timer
        if hasattr(gui, 'master'):
            gui.master.after(10000, check_and_save)
    
    def _switch_notes_type(self, gui, notes_type: str) -> None:
        """Switch between device and sample notes"""
        # Force save current notes before switching (critical - user lost notes before)
        self._save_notes(gui)
        
        # Small delay to ensure save completes
        gui.master.update_idletasks()
        
        # Load the other type
        self._load_notes(gui)
    
    def _load_notes(self, gui) -> None:
        """Load notes from file based on current type"""
        notes_type = gui.notes_type_var.get()
        # Disable undo temporarily while loading
        gui.notes_text.config(undo=False)
        gui.notes_text.delete("1.0", tk.END)
        
        try:
            if notes_type == "device":
                # Load device notes from device_info.json
                # Use device_section_and_number (A1, A2, etc.) for individual device notes
                device_id = None
                sample_name = None
                
                # Get device identifier (A1, A2, etc.)
                if hasattr(gui, 'device_section_and_number'):
                    device_id = gui.device_section_and_number
                
                # Get sample name (D104, etc.) for folder structure
                if hasattr(gui, 'sample_gui') and gui.sample_gui:
                    sample_name = getattr(gui.sample_gui, 'current_device_name', None)
                    if not sample_name:
                        # Fallback to sample_type_var
                        sample_type_var = getattr(gui.sample_gui, 'sample_type_var', None)
                        if sample_type_var and hasattr(sample_type_var, 'get'):
                            sample_name = sample_type_var.get()
                
                # Also try from sample_name_var in Measurement GUI
                if not sample_name and hasattr(gui, 'sample_name_var'):
                    sample_name = gui.sample_name_var.get().strip()
                
                if device_id and sample_name:
                    from pathlib import Path
                    # Use the save root from Measurement_GUI
                    save_root = Path(getattr(gui, 'default_save_root', Path.home() / "Documents" / "Data_folder"))
                    # Folder structure: {save_root}/{sample_name}/{letter}/{number}/device_info.json
                    letter = device_id[0] if len(device_id) > 0 else "A"
                    number = device_id[1:] if len(device_id) > 1 else "1"
                    device_folder = save_root / sample_name.replace(" ", "_") / letter / number
                    info_path = device_folder / "device_info.json"
                    
                    if info_path.exists():
                        import json
                        with info_path.open("r", encoding="utf-8") as f:
                            device_info = json.load(f)
                            notes = device_info.get("notes", "")
                            if notes:
                                gui.notes_text.insert("1.0", notes)
                    gui.notes_status_label.config(text=f"Device: {device_id} (Sample: {sample_name})", fg=self.COLOR_INFO)
                elif device_id:
                    gui.notes_status_label.config(text=f"Device: {device_id} (No sample name)", fg=self.COLOR_WARNING)
                else:
                    gui.notes_status_label.config(text="No device selected", fg=self.COLOR_WARNING)
            else:
                # Load sample notes from sample_notes.json
                # Sample notes are for the whole sample (D104, etc.) - the name from device manager
                sample_name = None
                
                # First try: get from Sample_GUI's current_device_name (this is the sample name from device manager)
                if hasattr(gui, 'sample_gui') and gui.sample_gui:
                    sample_name = getattr(gui.sample_gui, 'current_device_name', None)
                
                # Fallback: try sample_name_var from Measurement GUI
                if not sample_name and hasattr(gui, 'sample_name_var'):
                    sample_name = gui.sample_name_var.get().strip()
                
                # Last fallback: sample_type_var (sample type, not the device name)
                if not sample_name and hasattr(gui, 'sample_gui') and gui.sample_gui:
                    sample_type_var = getattr(gui.sample_gui, 'sample_type_var', None)
                    if sample_type_var and hasattr(sample_type_var, 'get'):
                        sample_name = sample_type_var.get()
                
                if sample_name:
                    from pathlib import Path
                    # Use the save root from Measurement_GUI
                    save_root = Path(getattr(gui, 'default_save_root', Path.home() / "Documents" / "Data_folder"))
                    sample_folder = save_root / sample_name.replace(" ", "_")
                    notes_path = sample_folder / "sample_notes.json"
                    
                    if notes_path.exists():
                        import json
                        with notes_path.open("r", encoding="utf-8") as f:
                            notes_data = json.load(f)
                            notes = notes_data.get("notes", "")
                            if notes:
                                gui.notes_text.insert("1.0", notes)
                    gui.notes_status_label.config(text=f"Sample: {sample_name}", fg=self.COLOR_INFO)
                else:
                    gui.notes_status_label.config(text="No sample name set", fg=self.COLOR_WARNING)
        except Exception as e:
            print(f"Error loading notes: {e}")
            gui.notes_status_label.config(text=f"Error loading notes: {e}", fg=self.COLOR_ERROR)
        finally:
            # Re-enable undo and reset stack after loading
            try:
                gui.notes_text.config(undo=True)
                gui.notes_text.edit_reset()
            except:
                pass
    
    def _save_notes(self, gui) -> None:
        """Save notes to file"""
        notes_type = gui.notes_type_var.get()
        notes_content = gui.notes_text.get("1.0", tk.END).strip()
        
        try:
            from pathlib import Path
            from datetime import datetime
            import json
            
            # Use the save root from Measurement_GUI
            save_root = Path(getattr(gui, 'default_save_root', Path.home() / "Documents" / "Data_folder"))
            
            if notes_type == "device":
                # Save to device_info.json
                # Use device_section_and_number (A1, A2, etc.) for individual device notes
                device_id = None
                sample_name = None
                
                # Get device identifier (A1, A2, etc.)
                if hasattr(gui, 'device_section_and_number'):
                    device_id = gui.device_section_and_number
                
                # Get sample name (D104, etc.) for folder structure
                if hasattr(gui, 'sample_gui') and gui.sample_gui:
                    sample_name = getattr(gui.sample_gui, 'current_device_name', None)
                    if not sample_name:
                        # Fallback to sample_type_var
                        sample_type_var = getattr(gui.sample_gui, 'sample_type_var', None)
                        if sample_type_var and hasattr(sample_type_var, 'get'):
                            sample_name = sample_type_var.get()
                
                # Also try from sample_name_var in Measurement GUI
                if not sample_name and hasattr(gui, 'sample_name_var'):
                    sample_name = gui.sample_name_var.get().strip()
                
                if not device_id:
                    messagebox.showwarning("No Device", "No device is selected. Please select a device first.")
                    return
                
                if not sample_name:
                    messagebox.showwarning("No Sample", "No sample name is set. Please set a sample name first.")
                    return
                
                # Folder structure: {save_root}/{sample_name}/{letter}/{number}/device_info.json
                letter = device_id[0] if len(device_id) > 0 else "A"
                number = device_id[1:] if len(device_id) > 1 else "1"
                device_folder = save_root / sample_name.replace(" ", "_") / letter / number
                device_folder.mkdir(parents=True, exist_ok=True)
                info_path = device_folder / "device_info.json"
                
                # Load existing device_info or create new
                device_info = {}
                if info_path.exists():
                    with info_path.open("r", encoding="utf-8") as f:
                        device_info = json.load(f)
                
                # Update notes and metadata
                device_info["notes"] = notes_content
                device_info["last_modified"] = datetime.now().isoformat(timespec='seconds')
                if "name" not in device_info:
                    device_info["name"] = device_id
                if "created" not in device_info:
                    device_info["created"] = datetime.now().isoformat(timespec='seconds')
                
                # Save
                with info_path.open("w", encoding="utf-8") as f:
                    json.dump(device_info, f, indent=2)
                
                gui.notes_status_label.config(text=f"Device notes saved: {device_id}", fg=self.COLOR_SUCCESS)
            else:
                # Save to sample_notes.json
                # Sample notes are for the whole sample (D104, etc.) - the name from device manager
                sample_name = None
                
                # First try: get from Sample_GUI's current_device_name (this is the sample name from device manager)
                if hasattr(gui, 'sample_gui') and gui.sample_gui:
                    sample_name = getattr(gui.sample_gui, 'current_device_name', None)
                
                # Fallback: try sample_name_var from Measurement GUI
                if not sample_name and hasattr(gui, 'sample_name_var'):
                    sample_name = gui.sample_name_var.get().strip()
                
                # Last fallback: sample_type_var (sample type, not the device name)
                if not sample_name and hasattr(gui, 'sample_gui') and gui.sample_gui:
                    sample_type_var = getattr(gui.sample_gui, 'sample_type_var', None)
                    if sample_type_var and hasattr(sample_type_var, 'get'):
                        sample_name = sample_type_var.get()
                
                if not sample_name:
                    messagebox.showwarning("No Sample", "No sample name is set in Device Manager. Please set a device name (e.g., D104) in Sample GUI first.")
                    return
                
                sample_folder = save_root / sample_name.replace(" ", "_")
                sample_folder.mkdir(parents=True, exist_ok=True)
                notes_path = sample_folder / "sample_notes.json"
                
                # Create notes data structure
                notes_data = {
                    "sample_name": sample_name,
                    "notes": notes_content,
                    "last_modified": datetime.now().isoformat(timespec='seconds')
                }
                
                # Save
                with notes_path.open("w", encoding="utf-8") as f:
                    json.dump(notes_data, f, indent=2)
                
                gui.notes_status_label.config(text="Sample notes saved", fg=self.COLOR_SUCCESS)
            
            # Clear status after 3 seconds
            gui.master.after(3000, lambda: gui.notes_status_label.config(text=""))
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save notes: {e}")
            gui.notes_status_label.config(text=f"Error: {e}", fg=self.COLOR_ERROR)
    
    def _auto_save_notes(self, gui) -> None:
        """Auto-save notes without showing dialog"""
        try:
            notes_type = gui.notes_type_var.get()
            notes_content = gui.notes_text.get("1.0", tk.END).strip()
            
            from pathlib import Path
            from datetime import datetime
            import json
            
            # Use the save root from Measurement_GUI
            save_root = Path(getattr(gui, 'default_save_root', Path.home() / "Documents" / "Data_folder"))
            
            if notes_type == "device":
                device_name = None
                if hasattr(gui, 'sample_gui') and gui.sample_gui:
                    device_name = getattr(gui.sample_gui, 'current_device_name', None)
                
                if device_name:
                    device_folder = save_root / device_name.replace(" ", "_")
                    device_folder.mkdir(parents=True, exist_ok=True)
                    info_path = device_folder / "device_info.json"
                    
                    device_info = {}
                    if info_path.exists():
                        with info_path.open("r", encoding="utf-8") as f:
                            device_info = json.load(f)
                    
                    device_info["notes"] = notes_content
                    device_info["last_modified"] = datetime.now().isoformat(timespec='seconds')
                    if "name" not in device_info:
                        device_info["name"] = device_name
                    if "created" not in device_info:
                        device_info["created"] = datetime.now().isoformat(timespec='seconds')
                    
                    with info_path.open("w", encoding="utf-8") as f:
                        json.dump(device_info, f, indent=2)
            else:
                sample_name = None
                if hasattr(gui, 'sample_name_var'):
                    sample_name = gui.sample_name_var.get().strip()
                
                if not sample_name and hasattr(gui, 'sample_gui') and gui.sample_gui:
                    sample_name = getattr(gui.sample_gui, 'sample_type_var', None)
                    if sample_name and hasattr(sample_name, 'get'):
                        sample_name = sample_name.get()
                
                if sample_name:
                    sample_folder = save_root / sample_name.replace(" ", "_")
                    sample_folder.mkdir(parents=True, exist_ok=True)
                    notes_path = sample_folder / "sample_notes.json"
                    
                    notes_data = {
                        "sample_name": sample_name,
                        "notes": notes_content,
                        "last_modified": datetime.now().isoformat(timespec='seconds')
                    }
                    
                    with notes_path.open("w", encoding="utf-8") as f:
                        json.dump(notes_data, f, indent=2)
        except Exception as e:
            # Silently fail on auto-save
            print(f"Auto-save notes error: {e}")
    
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

