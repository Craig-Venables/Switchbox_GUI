"""
TSP Testing GUI - Multi-System Pulse Testing Interface
========================================================

Purpose:
--------
Fast, buffer-based pulse testing GUI with real-time visualization for Keithley
instruments. Supports both Keithley 2450 (TSP-based) and Keithley 4200A-SCS
(KXCI-based) systems. Automatically routes tests to the appropriate measurement
system based on device address.

Key Features:
-------------
- Pulse-read-repeat tests
- Width sweeps (pulse width characterization)
- Potentiation/depression cycles
- Endurance testing
- Real-time plotting and visualization
- Automatic system detection (2450 vs 4200A)
- Test parameter configuration
- Data saving with customizable locations

Entry Points:
-------------
1. Standalone mode:
   ```python
   root = tk.Tk()
   gui = TSPTestingGUI(root, device_address="USB0::0x05E6::0x2450::04496615::INSTR")
   root.mainloop()
   ```

2. Launched from MeasurementGUI:
   - User clicks "Pulse Testing" button in MeasurementGUI
   - Passes device address and context (sample name, device label)

Dependencies:
-------------
- Pulse_Testing.system_wrapper: System detection and routing
- Pulse_Testing.test_capabilities: Test availability checking
- Equipment.SMU_AND_PMU.Keithley2450_TSP: 2450 TSP interface
- Equipment.SMU_AND_PMU.keithley2450_tsp_scripts: 2450 test scripts
- Equipment.SMU_AND_PMU.keithley4200_kxci_scripts: 4200A KXCI scripts
- Measurements.data_formats: Data formatting and saving

Relationships:
-------------
TSP_Testing_GUI (this file)
    ├─> Can be launched from MeasurementGUI
    ├─> Can be standalone
    └─> Uses SystemWrapper to route to:
            ├─> Keithley 2450 system
            └─> Keithley 4200A system

Test Functions:
---------------
Defined in Pulse_Testing.test_definitions (filtered by system via test_capabilities).
- Pulse-Read-Repeat, Multi-Pulse-Then-Read, Width Sweep, Potentiation/Depression, Endurance, etc.

File Structure:
---------------
- main.py: TSPTestingGUI, create_ui, tabs (Manual, Automated, Optical)
- config.py: Paths, config file names, window geometry
- logic.py: get_available_devices(), run_test_worker() (device scan, test execution)
- plot_handlers.py: plot_by_type() dispatch for result plotting
- ui/: tabs_optical (Optical tab – Oxxius laser pulsing); more sections can be extracted here
"""

# Ensure project root is on sys.path for imports when running directly
import sys
from pathlib import Path
import math

# Project root and path (must set before importing rest of project)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from gui.pulse_testing_gui import config

import threading
import time
import os
import json
import subprocess
from typing import Optional, List, Union
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import numpy as np

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# Legacy imports kept for compatibility - use backward-compatible imports
from Equipment.SMU_AND_PMU import Keithley2450_TSP, keithley2450_tsp_scripts
Keithley2450_TSP_Scripts = keithley2450_tsp_scripts.Keithley2450_TSP_Scripts if hasattr(keithley2450_tsp_scripts, 'Keithley2450_TSP_Scripts') else None

# New modular pulse testing system
from Pulse_Testing.system_wrapper import SystemWrapper, detect_system_from_address, get_default_address_for_system
from Pulse_Testing.test_capabilities import is_test_supported, get_test_explanation
from Pulse_Testing.test_definitions import TEST_FUNCTIONS, get_test_definitions_for_gui

from .ui import (
    build_connection_section,
    build_test_selection_section,
    build_pulse_diagram_section,
    build_parameters_section,
    build_status_section,
    build_plot_section,
    build_optical_tab,
)
from .ui.pulse_diagram import PulseDiagramHelper
from Measurements.data_formats import TSPDataFormatter, FileNamer, save_tsp_measurement


# Standalone utility function for independent operation
def find_largest_number_in_folder(folder: Union[str, Path]) -> Optional[int]:
    """
    Return the largest numeric prefix found in folder filenames.
    
    Scans existing files in the folder to find the largest numeric prefix
    (e.g., "5-test.txt" -> 5). Used for sequential file numbering.
    
    Args:
        folder: Path to folder to scan
        
    Returns:
        Largest number found, or None if no numeric prefixes found
    """
    try:
        entries = os.listdir(folder)
    except (FileNotFoundError, OSError):
        return None
    
    max_idx: Optional[int] = None
    for name in entries:
        try:
            # Extract prefix before first hyphen
            prefix = name.split("-", 1)[0]
            value = int(prefix)
            if max_idx is None or value > max_idx:
                max_idx = value
        except (ValueError, IndexError):
            continue
    
    return max_idx


# Test definitions imported from backend; use get_test_definitions_for_gui(system_name) for filtered list
class TSPTestingGUI(tk.Toplevel):
    """Multi-System Pulse Testing GUI
    
    Supports Keithley 2450 (TSP) and Keithley 4200A-SCS (KXCI).
    Automatically routes tests to appropriate system based on device address.
    """
    
    def __init__(
        self,
        master,
        device_address: str = "GPIB0::17::INSTR",
        provider=None,
        sample_name: Optional[str] = None,
        device_label: Optional[str] = None,
        custom_save_base: Optional[Union[str, Path]] = None,
    ):
        super().__init__(master)
        self.title("Multi-System Pulse Testing")
        self.geometry(config.WINDOW_GEOMETRY)
        self.resizable(True, True)
        
        # State
        self.tsp = None
        self.test_scripts = None  # Legacy - kept for backward compatibility
        self.provider = provider
        self.device_address = device_address or "GPIB0::17::INSTR"
        self.current_test = None
        self.test_running = False
        self.test_thread = None
        self.last_results = None
        
        # New modular system wrapper
        self.system_wrapper = SystemWrapper()
        self.current_system_name = None  # Track which system is connected
        
        # Context from provider or caller
        if isinstance(sample_name, str) and sample_name.strip():
            self.sample_name = sample_name.strip()
        else:
            self.sample_name = "UnknownSample"
        if isinstance(device_label, str) and device_label.strip():
            self.device_label = device_label.strip()
        else:
            self.device_label = "UnknownDevice"
        
        # Save location - load from config
        if custom_save_base:
            self.custom_base_path = Path(custom_save_base)
            self._custom_base_from_provider = True
        else:
            self.custom_base_path = self._load_custom_save_location()
            self._custom_base_from_provider = False
        
        # Simple save location (for TSP GUI independent mode)
        self.use_simple_save_var = tk.BooleanVar(value=False)
        self.simple_save_path_var = tk.StringVar()
        self.simple_save_path = None
        self._load_simple_save_config()
        if self._custom_base_from_provider:
            self.use_simple_save_var.set(False)
            self.simple_save_path = None
            self.simple_save_path_var.set("")
        
        # Internal scheduling handles
        self._context_poll_job = None
        
        # Create UI
        self.create_ui()
        # Start syncing provider context (sample/device/custom path)
        self._poll_context()
        
        # Auto-connect disabled - user must manually connect
    
    def create_ui(self):
        """Create the main UI layout with tabbed interface"""
        # Main container
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel: Controls with scrollbar
        left_container = tk.Frame(main_frame, width=500)  # Increased width slightly
        left_container.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        left_container.pack_propagate(False)
        
        # Create scrollable canvas for left panel
        left_canvas = tk.Canvas(left_container, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left_panel = tk.Frame(left_canvas)
        
        # Create window in canvas for the frame
        left_canvas_window = left_canvas.create_window((0, 0), window=left_panel, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        # Configure scrollable region and update canvas window width
        def update_scroll_region(event=None):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
            # Update canvas window width to match canvas width
            canvas_width = left_canvas.winfo_width()
            if canvas_width > 1:  # Only update if canvas has been rendered
                left_canvas.itemconfig(left_canvas_window, width=canvas_width)
        
        left_panel.bind("<Configure>", update_scroll_region)
        left_canvas.bind("<Configure>", lambda e: left_canvas.itemconfig(left_canvas_window, width=e.width))
        
        # Pack scrollbar and canvas
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind mousewheel to canvas (for Windows)
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        left_canvas.bind("<MouseWheel>", _on_mousewheel)
        # Also bind to the frame for better responsiveness
        left_panel.bind("<MouseWheel>", lambda e: left_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # Right panel: Visualizations
        right_panel = tk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Top bar with help button
        top_bar = tk.Frame(left_panel, bg="#e6f3ff", pady=5, padx=10)
        top_bar.pack(fill=tk.X, pady=(0, 5))
        top_bar.columnconfigure(0, weight=1)
        
        title_label = tk.Label(
            top_bar,
            text="TSP Pulse Testing",
            font=("Segoe UI", 11, "bold"),
            bg="#e6f3ff",
            fg="#1565c0"
        )
        title_label.grid(row=0, column=0, sticky="w")
        
        help_btn = tk.Button(
            top_bar,
            text="Help / Guide",
            command=self._show_help,
            bg="#1565c0",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=2
        )
        help_btn.grid(row=0, column=1, sticky="e", padx=(10, 0))
        
        # Connection section at top (always visible)
        self.create_connection_section(left_panel)
        
        # Create tabbed notebook for different testing modes
        self.notebook = ttk.Notebook(left_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tabs
        self.manual_tab = tk.Frame(self.notebook)
        self.automated_tab = tk.Frame(self.notebook)
        self.optical_tab = tk.Frame(self.notebook)
        self.notebook.add(self.manual_tab, text="  Manual Testing  ")
        self.notebook.add(self.automated_tab, text="  Automated Testing  ")
        self.notebook.add(self.optical_tab, text="  Optical  ")
        # Populate tabs
        self.create_manual_testing_tab(self.manual_tab)
        self.create_automated_testing_tab(self.automated_tab)
        build_optical_tab(self.optical_tab, self)
        
        # Right panel sections
        self.create_pulse_diagram_section(right_panel)
        self.create_plot_section(right_panel)
        
        # Bottom control bar under right panel (under live plot)
        self.create_bottom_control_bar(right_panel)
    
    def create_manual_testing_tab(self, parent):
        """Create the manual testing tab with test selection, parameters, and controls"""
        # Parameters section MUST be created first (before test_selection calls on_test_selected)
        self.create_parameters_section(parent)
        
        # Test selection section (this calls on_test_selected which needs params_frame)
        self.create_test_selection_section(parent)
        
        # Status section (control buttons moved to bottom bar)
        self.create_status_section(parent)
    
    def create_automated_testing_tab(self, parent):
        """Create the automated testing tab for automated pulse characterization"""
        # Test type selection
        test_frame = tk.LabelFrame(parent, text="Automated Test Type", padx=5, pady=5)
        test_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(test_frame, text="Test Type:", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        
        self.auto_test_var = tk.StringVar()
        auto_test_types = [
            "Retention Pulse Optimization",
            "Voltage Sweep Characterization", 
            "Pulse Width Sweep",
            "Endurance Cycling Matrix"
        ]
        auto_test_combo = ttk.Combobox(test_frame, textvariable=self.auto_test_var,
                                       values=auto_test_types, state="readonly", width=35)
        auto_test_combo.pack(fill=tk.X, pady=5)
        auto_test_combo.current(0)
        
        # Description
        tk.Label(test_frame, text="Description:", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(5,0))
        self.auto_desc_text = tk.Text(test_frame, height=3, wrap=tk.WORD, bg="#f0f0f0", 
                                      relief=tk.FLAT, font=("TkDefaultFont", 9))
        self.auto_desc_text.pack(fill=tk.X, pady=2)
        self.auto_desc_text.insert(1.0, "Automatically test retention characteristics across different pulse parameters to find optimal settings.")
        self.auto_desc_text.config(state=tk.DISABLED)
        
        # Parameter ranges
        ranges_frame = tk.LabelFrame(parent, text="Parameter Ranges", padx=5, pady=5)
        ranges_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Voltage range
        volt_frame = tk.Frame(ranges_frame)
        volt_frame.pack(fill=tk.X, pady=2)
        tk.Label(volt_frame, text="Voltage Range (V):", width=20, anchor="w").pack(side=tk.LEFT)
        tk.Label(volt_frame, text="Start:").pack(side=tk.LEFT, padx=(5,2))
        self.auto_volt_start_var = tk.StringVar(value="0.5")
        tk.Entry(volt_frame, textvariable=self.auto_volt_start_var, width=8).pack(side=tk.LEFT, padx=2)
        tk.Label(volt_frame, text="End:").pack(side=tk.LEFT, padx=(5,2))
        self.auto_volt_end_var = tk.StringVar(value="5.0")
        tk.Entry(volt_frame, textvariable=self.auto_volt_end_var, width=8).pack(side=tk.LEFT, padx=2)
        tk.Label(volt_frame, text="Step:").pack(side=tk.LEFT, padx=(5,2))
        self.auto_volt_step_var = tk.StringVar(value="0.5")
        tk.Entry(volt_frame, textvariable=self.auto_volt_step_var, width=8).pack(side=tk.LEFT, padx=2)
        
        # Pulse width range
        width_frame = tk.Frame(ranges_frame)
        width_frame.pack(fill=tk.X, pady=2)
        tk.Label(width_frame, text="Pulse Width Range (s):", width=20, anchor="w").pack(side=tk.LEFT)
        tk.Label(width_frame, text="Start:").pack(side=tk.LEFT, padx=(5,2))
        self.auto_width_start_var = tk.StringVar(value="0.5")
        tk.Entry(width_frame, textvariable=self.auto_width_start_var, width=8).pack(side=tk.LEFT, padx=2)
        tk.Label(width_frame, text="End:").pack(side=tk.LEFT, padx=(5,2))
        self.auto_width_end_var = tk.StringVar(value="5.0")
        tk.Entry(width_frame, textvariable=self.auto_width_end_var, width=8).pack(side=tk.LEFT, padx=2)
        tk.Label(width_frame, text="Step:").pack(side=tk.LEFT, padx=(5,2))
        self.auto_width_step_var = tk.StringVar(value="0.5")
        tk.Entry(width_frame, textvariable=self.auto_width_step_var, width=8).pack(side=tk.LEFT, padx=2)
        
        # Cycles per test point
        cycles_frame = tk.Frame(ranges_frame)
        cycles_frame.pack(fill=tk.X, pady=2)
        tk.Label(cycles_frame, text="Cycles per Test Point:", width=20, anchor="w").pack(side=tk.LEFT)
        self.auto_cycles_var = tk.StringVar(value="10")
        tk.Entry(cycles_frame, textvariable=self.auto_cycles_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Delay between tests (for device relaxation)
        delay_frame = tk.Frame(ranges_frame)
        delay_frame.pack(fill=tk.X, pady=2)
        tk.Label(delay_frame, text="Delay Between Tests (s):", width=20, anchor="w").pack(side=tk.LEFT)
        self.auto_delay_var = tk.StringVar(value="5.0")
        tk.Entry(delay_frame, textvariable=self.auto_delay_var, width=10).pack(side=tk.LEFT, padx=5)
        tk.Label(delay_frame, text="(for device relaxation)", font=("TkDefaultFont", 8), fg="gray").pack(side=tk.LEFT, padx=5)
        
        # Test matrix preview
        matrix_frame = tk.LabelFrame(parent, text="Test Matrix Preview", padx=5, pady=5)
        matrix_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.auto_matrix_text = tk.Text(matrix_frame, height=4, wrap=tk.WORD, bg="#f0f0f0",
                                        relief=tk.FLAT, font=("Courier", 8))
        self.auto_matrix_text.pack(fill=tk.X)
        self.auto_matrix_text.insert(1.0, "Test matrix will be calculated based on parameter ranges.\nExample: 10 voltages × 10 widths = 100 test points")
        self.auto_matrix_text.config(state=tk.DISABLED)
        
        # Control buttons
        control_frame = tk.LabelFrame(parent, text="Control", padx=5, pady=5)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.auto_run_btn = tk.Button(control_frame, text="▶  START AUTOMATED TEST", 
                                       command=self._run_automated_test,
                                       bg="#28a745", fg="white", font=("TkDefaultFont", 12, "bold"),
                                       height=2, relief=tk.RAISED, bd=3, cursor="hand2",
                                       state=tk.DISABLED)  # Disabled until implemented
        self.auto_run_btn.pack(fill=tk.X, pady=(0, 5))
        
        # Progress section
        progress_frame = tk.LabelFrame(parent, text="Progress", padx=5, pady=5)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.auto_progress_var = tk.StringVar(value="Ready to start automated testing")
        tk.Label(progress_frame, textvariable=self.auto_progress_var, 
                font=("TkDefaultFont", 9)).pack(anchor="w")
        
        self.auto_progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
        self.auto_progress_bar.pack(fill=tk.X, pady=5)
        
        # Results summary
        results_frame = tk.LabelFrame(parent, text="Results Summary", padx=5, pady=5)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.auto_results_text = tk.Text(results_frame, height=8, wrap=tk.WORD, bg="black", 
                                         fg="lime", font=("Courier", 8))
        self.auto_results_text.pack(fill=tk.BOTH, expand=True)
        self.auto_results_text.insert(1.0, "Automated test results will appear here...\n")
        self.auto_results_text.config(state=tk.DISABLED)
        
        # Export button (moved to bottom bar, keep reference for later)
        # export_btn = tk.Button(control_frame, text="📊 Export Results", 
        #                       command=self._export_automated_results,
        #                       font=("TkDefaultFont", 9), state=tk.DISABLED)
        # export_btn.pack(fill=tk.X, pady=(5, 0))
    
    def _run_automated_test(self):
        """Placeholder for automated test execution"""
        messagebox.showinfo("Not Implemented", 
                          "Automated testing functionality will be implemented in a future update.")
    
    def _export_automated_results(self):
        """Placeholder for exporting automated test results"""
        messagebox.showinfo("Not Implemented",
                          "Results export functionality will be implemented in a future update.")
    
    def create_bottom_control_bar(self, parent):
        """Create clean bottom control bar with context-aware buttons"""
        # Bottom bar frame with clean styling
        bottom_bar = tk.Frame(parent, bg="#f5f5f5", relief=tk.RAISED, bd=1)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)
        
        # Inner frame for padding
        inner_frame = tk.Frame(bottom_bar, bg="#f5f5f5")
        inner_frame.pack(fill=tk.X, padx=10, pady=6)
        
        # Top row: Main action buttons
        button_row = tk.Frame(inner_frame, bg="#f5f5f5")
        button_row.pack(fill=tk.X, pady=(0, 4))
        
        # Run button - prominent but not huge
        self.run_btn = tk.Button(button_row, text="▶ RUN", command=self.run_test,
                                bg="#28a745", fg="white", font=("TkDefaultFont", 10, "bold"),
                                relief=tk.FLAT, bd=0, padx=20, pady=6, cursor="hand2")
        self.run_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Stop button
        self.stop_btn = tk.Button(button_row, text="⏹ STOP", command=self.stop_test,
                                 bg="#dc3545", fg="white", font=("TkDefaultFont", 10),
                                 relief=tk.FLAT, bd=0, padx=15, pady=6, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Save button
        self.save_btn = tk.Button(button_row, text="💾 SAVE", command=self.manual_save_with_notes,
                                 bg="#007bff", fg="white", font=("TkDefaultFont", 10),
                                 relief=tk.FLAT, bd=0, padx=15, pady=6, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        # Analysis button
        analysis_btn = tk.Button(button_row, text="📊 ANALYSIS", command=self.open_data_analysis,
                                bg="#FF9800", fg="white", font=("TkDefaultFont", 10),
                                relief=tk.FLAT, bd=0, padx=15, pady=6)
        analysis_btn.pack(side=tk.LEFT, padx=5)
        
        # Bottom row: Options and settings (underneath buttons)
        options_row = tk.Frame(inner_frame, bg="#f5f5f5")
        options_row.pack(fill=tk.X)
        
        # Auto-save checkbox
        self.auto_save_var = tk.BooleanVar(value=True)
        auto_save_check = tk.Checkbutton(options_row, text="Auto-save",
                                        variable=self.auto_save_var,
                                        bg="#f5f5f5", font=("TkDefaultFont", 9),
                                        relief=tk.FLAT, bd=0)
        auto_save_check.pack(side=tk.LEFT, padx=(0, 15))
        
        # Filename suffix entry (compact)
        tk.Label(options_row, text="Suffix:", bg="#f5f5f5",
                font=("TkDefaultFont", 9)).pack(side=tk.LEFT, padx=(0, 2))
        self.filename_suffix_var = tk.StringVar()
        suffix_entry = tk.Entry(options_row, textvariable=self.filename_suffix_var,
                               font=("TkDefaultFont", 9), width=15, relief=tk.FLAT, bd=1)
        suffix_entry.pack(side=tk.LEFT, padx=(0, 15))
        
        # Notes text (compact, single line)
        tk.Label(options_row, text="Notes:", bg="#f5f5f5",
                font=("TkDefaultFont", 9)).pack(side=tk.LEFT, padx=(0, 2))
        self.notes_text = tk.Text(options_row, height=1, width=30, wrap=tk.NONE,
                                 font=("TkDefaultFont", 9), relief=tk.FLAT, bd=1)
        self.notes_text.pack(side=tk.LEFT, padx=0)
        self.notes_text.insert(1.0, "Add notes...")
        
        # Bind tab change to update button states
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _on_tab_changed(self, event=None):
        """Update bottom bar controls based on active tab"""
        current_tab = self.notebook.index(self.notebook.select())
        
        if current_tab == 0:  # Manual Testing tab
            # Show manual testing controls
            self.run_btn.config(text="▶ RUN", command=self.run_test)
        elif current_tab == 1:  # Automated Testing tab
            # Show automated testing controls
            self.run_btn.config(text="▶ START AUTO TEST", command=self._run_automated_test)



    def create_connection_section(self, parent):
        """Connection controls (built by ui.connection)."""
        build_connection_section(parent, self)

    def _show_help(self):
        """Display a help window with usage instructions."""
        help_win = tk.Toplevel(self)
        help_win.title("TSP Pulse Testing Guide")
        help_win.geometry(config.HELP_WINDOW_GEOMETRY)
        help_win.configure(bg="#f0f0f0")
        
        # Scrollable Content
        canvas = tk.Canvas(help_win, bg="#f0f0f0")
        scrollbar = ttk.Scrollbar(help_win, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Content
        pad = {'padx': 20, 'pady': 10, 'anchor': 'w'}
        
        tk.Label(scrollable_frame, text="TSP Pulse Testing Guide", 
                font=("Segoe UI", 16, "bold"), bg="#f0f0f0", fg="#1565c0").pack(**pad)
        
        tk.Label(scrollable_frame, text="1. Overview", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame, 
                text="This GUI provides fast, buffer-based pulse testing with real-time visualization\n"
                      "for Keithley instruments. Supports both Keithley 2450 (TSP-based) and\n"
                      "Keithley 4200A-SCS (KXCI-based) systems.",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="2. Getting Started", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Select your system type (2450 or 4200A)\n"
                      "• Enter device address or use auto-detect\n"
                      "• Choose test type from Manual Testing tab\n"
                      "• Configure pulse parameters\n"
                      "• Click 'Start Test' to begin\n"
                      "• Monitor results in real-time plots",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="3. Test Types", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Pulse-Read-Repeat: Single pulse followed by read\n"
                      "• Multi-Pulse-Then-Read: Multiple pulses then read\n"
                      "• Width Sweep: Characterize pulse width dependence\n"
                      "• Potentiation/Depression: Training cycles\n"
                      "• Endurance Test: Long-term cycling",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="4. Features", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Automatic system detection from device address\n"
                      "• Real-time plotting and visualization\n"
                      "• Customizable save locations\n"
                      "• Test parameter presets\n"
                      "• Automated testing workflows",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="Video Tutorial", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0", fg="#d32f2f").pack(**pad)
        tk.Label(scrollable_frame,
                text="Video tutorials and additional resources will be added here.",
                justify="left", bg="#f0f0f0", fg="#666").pack(**pad)
    
    def create_test_selection_section(self, parent):
        """Test type selection (built by ui.test_selection)."""
        build_test_selection_section(parent, self)

    def create_pulse_diagram_section(self, parent):
        """Pulse pattern diagram (built by ui.diagram_section)."""
        build_pulse_diagram_section(parent, self)

    def create_parameters_section(self, parent):
        """Parameter inputs (built by ui.parameters)."""
        build_parameters_section(parent, self)

    def create_control_buttons_section(self, parent):
        """Run/Stop/Save buttons"""
        frame = tk.LabelFrame(parent, text="Control", padx=5, pady=5)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Run button - large and prominent
        self.run_btn = tk.Button(frame, text="▶  RUN TEST", command=self.run_test, 
                                 bg="#28a745", fg="white", font=("TkDefaultFont", 12, "bold"),
                                 height=2, relief=tk.RAISED, bd=3, cursor="hand2")
        self.run_btn.pack(fill=tk.X, pady=(0, 5))
        
        # Secondary buttons
        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        self.stop_btn = tk.Button(btn_frame, text="⏹ Stop", command=self.stop_test, 
                                  bg="#dc3545", fg="white", state=tk.DISABLED, font=("TkDefaultFont", 9))
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 2), fill=tk.X, expand=True)
        
        self.save_btn = tk.Button(btn_frame, text="💾 Manual Save", command=self.manual_save_with_notes, 
                                  state=tk.DISABLED, font=("TkDefaultFont", 9))
        self.save_btn.pack(side=tk.LEFT, padx=(2, 2), fill=tk.X, expand=True)
        
        # Data Analysis button
        analysis_btn = tk.Button(btn_frame, text="📊 Analysis", command=self.open_data_analysis, 
                                bg="#FF9800", fg="white", font=("TkDefaultFont", 9))
        analysis_btn.pack(side=tk.LEFT, padx=(2, 0), fill=tk.X, expand=True)
        
        # Auto-save toggle
        auto_save_frame = tk.Frame(frame)
        auto_save_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.auto_save_var = tk.BooleanVar(value=True)  # Default: auto-save enabled
        auto_save_check = tk.Checkbutton(auto_save_frame, text="🔄 Auto-save data after test completion",
                                        variable=self.auto_save_var, font=("TkDefaultFont", 9))
        auto_save_check.pack(anchor="w")
        
        # Filename suffix section
        suffix_frame = tk.LabelFrame(frame, text="📝 Filename Suffix (optional - added to filename)", padx=5, pady=5)
        suffix_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.filename_suffix_var = tk.StringVar()
        suffix_entry = tk.Entry(suffix_frame, textvariable=self.filename_suffix_var, 
                               font=("TkDefaultFont", 9), width=30)
        suffix_entry.pack(fill=tk.X, padx=2, pady=2)
        tk.Label(suffix_frame, text="Example: 'test1', 'batchA', 'highTemp'", 
                font=("TkDefaultFont", 7), fg="gray").pack(anchor="w", padx=2)
        
        # Notes section
        notes_frame = tk.LabelFrame(frame, text="📝 Test Notes (optional - saved with data)", padx=5, pady=5)
        notes_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.notes_text = tk.Text(notes_frame, height=3, wrap=tk.WORD, font=("TkDefaultFont", 9))
        self.notes_text.pack(fill=tk.X)
        self.notes_text.insert(1.0, "Add notes about this test here...")
    
    def create_status_section(self, parent):
        """Status/log display (built by ui.status_section)."""
        build_status_section(parent, self)

    def create_plot_section(self, parent):
        """Matplotlib plot area (built by ui.plot_section)."""
        build_plot_section(parent, self)

    def auto_connect(self):
        """Auto-connect on startup"""
        # Update context from provider (like PMU GUI does)
        self._sync_context_from_provider()
        
        # Try to get device address from provider (if Measurement GUI has one)
        if self.provider:
            try:
                # Check if provider has keithley_address_var (from Measurement GUI)
                addr_var = getattr(self.provider, 'keithley_address_var', None)
                if addr_var is not None:
                    addr = addr_var.get()
                    if addr and addr.strip():
                        self.addr_var.set(addr)
                        self.log(f"Using device address from provider: {addr}")
            except Exception as e:
                self.log(f"Could not get address from provider: {e}")
        
        # Try to connect
        self.connect_device()
    
    def _sync_context_from_provider(self):
        """Align sample/device context and save preferences with provider."""
        try:
            if self.provider is not None:
                sn = getattr(self.provider, 'sample_name_var', None)
                name = None
                if sn is not None and hasattr(sn, 'get'):
                    try:
                        name = sn.get().strip()
                    except Exception:
                        name = None
                if not name and hasattr(self.provider, 'sample_gui') and self.provider.sample_gui:
                    fallback = getattr(self.provider.sample_gui, 'current_device_name', None)
                    if fallback:
                        name = str(fallback).strip()
                if name:
                    self.sample_name = name

                device_section = getattr(self.provider, 'device_section_and_number', None)
                letter = getattr(self.provider, 'final_device_letter', None)
                number = getattr(self.provider, 'final_device_number', None)
                if device_section:
                    self.device_label = str(device_section)
                elif letter and number:
                    self.device_label = f"{letter}{number}"

                use_custom = getattr(self.provider, 'use_custom_save_var', None)
                use_custom_enabled = bool(use_custom and hasattr(use_custom, 'get') and use_custom.get())
                if use_custom_enabled:
                    custom_path = getattr(self.provider, 'custom_save_location', None)
                    if custom_path:
                        self.custom_base_path = Path(custom_path)
                        sample_from_path = Path(custom_path).name
                        if sample_from_path:
                            self.sample_name = sample_from_path
                        self.use_simple_save_var.set(False)
                        self.simple_save_path = None
                        self.simple_save_path_var.set("")
        except Exception:
            pass
        finally:
            if hasattr(self, 'context_var'):
                self.context_var.set(f"Sample: {self.sample_name}  |  Device: {self.device_label}")

    def _poll_context(self):
        """Poll provider for updated sample name and device (like PMU GUI)"""
        self._sync_context_from_provider()
        self._context_poll_job = self.after(500, self._poll_context)

    def destroy(self):
        """Ensure scheduled context polling stops when window closes."""
        job = getattr(self, "_context_poll_job", None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass
            self._context_poll_job = None
        super().destroy()
    
    def _load_custom_save_location(self) -> Optional[Path]:
        """Load custom save location from config file"""
        config_file = config.SAVE_LOCATION_CONFIG_FILE
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    use_custom = data.get('use_custom_save', False)
                    custom_path = data.get('custom_save_path', '')
                    if use_custom and custom_path:
                        return Path(custom_path)
        except Exception as e:
            print(f"Could not load save location config: {e}")
        return None  # None means use default
    
    def load_default_terminals(self) -> str:
        """Load default terminal setting from config file"""
        config_file = config.TSP_GUI_CONFIG_FILE
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    terminals = data.get('default_terminals', 'front')
                    if terminals.lower() in ['front', 'rear']:
                        return terminals.lower()
        except Exception as e:
            print(f"Could not load terminal config: {e}")
        return 'front'  # Default to front
    
    def save_terminal_default(self):
        """Save current terminal selection as default"""
        config_file = config.TSP_GUI_CONFIG_FILE
        try:
            data = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
            data['default_terminals'] = self.terminals_var.get()
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
            self.log(f"💾 Default terminals saved: {self.terminals_var.get().upper()}")
        except Exception as e:
            self.log(f"⚠️ Could not save terminal config: {e}")
    
    def _on_simple_save_toggle(self):
        """Handle simple save checkbox toggle"""
        if self.use_simple_save_var.get():
            self.simple_save_entry.config(state="normal")
            # Enable browse button
            for widget in self.simple_save_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="normal")
            # If no path set, prompt for one
            if not self.simple_save_path_var.get():
                self._browse_simple_save()
        else:
            self.simple_save_entry.config(state="disabled")
            # Disable browse button
            for widget in self.simple_save_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="disabled")
            self.simple_save_path = None
            self.simple_save_path_var.set("")
        
        # Save preference
        self._save_simple_save_config()
    
    def _browse_simple_save(self):
        """Open folder picker for simple save location"""
        from tkinter import filedialog
        folder = filedialog.askdirectory(
            title="Choose Simple Save Location",
            mustexist=False
        )
        if folder:
            self.simple_save_path = Path(folder)
            self.simple_save_path_var.set(str(self.simple_save_path))
            # Save preference
            self._save_simple_save_config()
    
    def _load_simple_save_config(self):
        """Load simple save location preference from config file"""
        config_file = config.TSP_GUI_SAVE_CONFIG_FILE
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    use_simple = data.get('use_simple_save', False)
                    simple_path = data.get('simple_save_path', '')
                    self.use_simple_save_var.set(use_simple)
                    if use_simple and simple_path:
                        self.simple_save_path = Path(simple_path)
                        self.simple_save_path_var.set(simple_path)
        except Exception as e:
            print(f"Could not load simple save config: {e}")
    
    def _save_simple_save_config(self):
        """Save simple save location preference to config file"""
        config_file = config.TSP_GUI_SAVE_CONFIG_FILE
        try:
            data = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
            data['use_simple_save'] = self.use_simple_save_var.get()
            data['simple_save_path'] = str(self.simple_save_path) if self.simple_save_path else ""
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Could not save simple save config: {e}")
    
    def _get_available_devices(self) -> List[str]:
        """Scan and return list of available USB and GPIB devices (via logic module)."""
        from gui.pulse_testing_gui import logic
        return logic.get_available_devices(self.device_address)
    
    def _refresh_devices(self):
        """Refresh the device dropdown list"""
        available_devices = self._get_available_devices()
        current_selection = self.addr_var.get()
        
        # Update combobox values
        if current_selection not in available_devices:
            available_devices.insert(0, current_selection)
        self.addr_combo['values'] = available_devices
        
        self.log(f"🔄 Refreshed device list: {len(available_devices)} device(s) found")
    
    def _auto_detect_system(self):
        """Auto-detect system from current address"""
        address = self.addr_var.get()
        detected = detect_system_from_address(address)
        if detected:
            self.system_var.set(detected)
            self.log(f"🔍 Auto-detected system: {detected}")
        else:
            self.log(f"⚠️ Could not auto-detect system from address: {address}")
            messagebox.showinfo("Auto-Detect", 
                              f"Could not detect system from address.\n"
                              f"Please select manually or use a recognized format.")
    
    def _on_system_changed(self):
        """When system changes, update device address to system default"""
        system_name = self.system_var.get()
        default_addr = get_default_address_for_system(system_name)
        if default_addr:
            self.addr_var.set(default_addr)
            # Update available devices list
            available_devices = self._get_available_devices()
            if default_addr not in available_devices:
                available_devices.insert(0, default_addr)
            self.addr_combo['values'] = available_devices
            self.log(f"🔧 Auto-populated device address for {system_name}: {default_addr}")
        
        # Update current_system_name for parameter unit conversion
        # (even if not connected, this affects default display units)
        if not self.system_wrapper.is_connected():
            self.current_system_name = system_name
        
        # Refresh parameters to show correct units (ms for 2450, µs for 4200A)
        if hasattr(self, 'test_var') and self.test_var.get():
            self.populate_parameters()
    
    def _update_system_detection(self):
        """Update system selection when address changes (optional - user can override)"""
        # Only auto-detect if user hasn't manually changed system
        # For now, we'll allow address to suggest system but not force it
        # User can use the "🔍 Auto" button if they want auto-detection
        pass
    
    def connect_device(self):
        """Connect to measurement system (supports multiple systems)"""
        try:
            address = self.addr_var.get()
            system_name = self.system_var.get()
            
            # Auto-detect system if not explicitly set or if address changed
            detected = detect_system_from_address(address)
            if detected and detected != system_name:
                # Update system selection if auto-detection differs
                self.system_var.set(detected)
                system_name = detected
                self.log(f"Auto-detected system: {system_name}")
            
            self.log(f"Connecting to {address}...")
            self.log(f"System: {system_name}")
            
            # Connect using system wrapper
            connected_system = self.system_wrapper.connect(
                address=address,
                system_name=system_name,
                terminals=self.terminals_var.get()
                if system_name in ('keithley2450', 'keithley2450_sim') else None,
            )
            
            self.current_system_name = connected_system
            idn = self.system_wrapper.get_idn()
            
            # Legacy compatibility: maintain old tsp/test_scripts if 2450
            if connected_system in ('keithley2450', 'keithley2450_sim'):
                system = self.system_wrapper.current_system
                self.tsp = getattr(system, 'tsp_controller', None)
                self.test_scripts = getattr(system, 'test_scripts', None)
            else:
                self.tsp = None
                self.test_scripts = None
            
            terminals_text = (
                f" ({self.terminals_var.get().upper()})"
                if connected_system in ('keithley2450', 'keithley2450_sim')
                else ""
            )
            self.conn_status_var.set(f"Connected: {system_name.upper()} - {idn}{terminals_text}")
            self.log(f"✓ Connected: {idn}")
            if connected_system in ('keithley2450', 'keithley2450_sim'):
                self.log(f"✓ Terminals: {self.terminals_var.get().upper()}")
            
            # Update unit selector based on connected system
            if hasattr(self, 'time_unit_var'):
                default_unit = "µs" if connected_system in ('keithley4200a',) else "ms"
                self.previous_unit = getattr(self, 'previous_unit', default_unit)
                self.time_unit_var.set(default_unit)
                self.previous_unit = default_unit
            
            # Update test list based on capabilities - this greys out unsupported tests
            self._update_test_list_capabilities()
            
            # Check current test and update button state (this will refresh parameters with correct units)
            self.on_test_selected(None)
            
            self.run_btn.config(state=tk.NORMAL)
            
        except Exception as e:
            self.conn_status_var.set("Connection Failed")
            self.log(f"❌ Connection error: {e}")
            messagebox.showerror("Connection Error", str(e))
    
    def disconnect_device(self):
        """Disconnect from device"""
        # Disconnect using system wrapper
        if self.system_wrapper.is_connected():
            try:
                self.system_wrapper.disconnect()
                self.log("✓ Disconnected")
            except:
                pass
        
        # Legacy cleanup
        if self.tsp:
            try:
                self.tsp.close()
            except:
                pass
            self.tsp = None
            self.test_scripts = None
        
        self.current_system_name = None
        self.conn_status_var.set("Disconnected")
        self.run_btn.config(state=tk.DISABLED)
        
        # Reset test list (enable all tests when disconnected)
        self._update_test_list_capabilities()
    
    def _update_test_list_capabilities(self):
        """Update test list to only show tests supported for current system (from test_capabilities + test_definitions)."""
        if not hasattr(self, 'test_combo'):
            return  # GUI not fully initialized yet

        system_name = self.current_system_name if self.current_system_name else None
        definitions = get_test_definitions_for_gui(system_name)
        test_values = list(definitions.keys())
        
        # Store current selection
        current_selection = self.test_var.get()
        
        # Update combobox values (this will trigger capability checking)
        self.test_combo['values'] = test_values
        
        # Restore selection if it exists
        if current_selection in test_values:
            self.test_var.set(current_selection)
        elif test_values:
            self.test_var.set(test_values[0])
        
        # Update enabled state and appearance based on capabilities
        # Note: Tkinter combobox doesn't support individual item styling easily,
        # so we'll handle capability checking in on_test_selected instead
    
    def on_test_selected(self, event):
        """Update UI when test is selected"""
        test_name = self.test_var.get()
        if test_name not in TEST_FUNCTIONS:
            return
        
        test_info = TEST_FUNCTIONS[test_name]
        test_function = test_info["function"]
        
        # Check if test is supported by current system
        system_name = self.current_system_name
        is_supported = True
        unsupported_msg = None
        
        if system_name:
            is_supported = is_test_supported(system_name, test_function)
            if not is_supported:
                unsupported_msg = get_test_explanation(system_name, test_function)
        
        # Update description (add warning if unsupported)
        self.desc_text.config(state=tk.NORMAL)
        self.desc_text.delete(1.0, tk.END)
        description = test_info["description"]
        if not is_supported and unsupported_msg:
            description = f"⚠️ NOT SUPPORTED: {unsupported_msg}\n\n{description}"
        self.desc_text.insert(1.0, description)
        if not is_supported:
            # Make text grayed out
            self.desc_text.tag_add("unsupported", "1.0", tk.END)
            self.desc_text.tag_config("unsupported", foreground="gray")
        self.desc_text.config(state=tk.DISABLED)
        
        # Disable/enable run button based on support
        if not is_supported:
            self.run_btn.config(state=tk.DISABLED, bg="gray", cursor="arrow")
            self.log(f"⚠️ Test '{test_name}' not supported by {system_name}")
        elif self.system_wrapper.is_connected():
            self.run_btn.config(state=tk.NORMAL, bg="#28a745", cursor="hand2")
        
        # Update parameters
        self.populate_parameters()
        
        # Update pulse diagram
        self.update_pulse_diagram()
    
    def _on_unit_changed(self):
        """Handle unit dropdown changes - preserve current values and convert units"""
        # Determine if we're using 4200A (needed for conversion logic)
        is_4200a = self.current_system_name in ('keithley4200a',)
        
        # Save current parameter values before repopulating
        saved_values = {}
        if hasattr(self, 'param_vars') and self.param_vars:
            # Get the new unit (what was just selected)
            if hasattr(self, 'time_unit_var'):
                new_unit = self.time_unit_var.get()
            else:
                new_unit = 'µs' if is_4200a else 'ms'
            
            # Get the old unit (what it was before the change)
            old_unit = getattr(self, 'previous_unit', None)
            if old_unit is None:
                # Fallback to system default
                old_unit = 'µs' if is_4200a else 'ms'
            
            # Update previous_unit for next time
            self.previous_unit = new_unit
            
            # Unit conversion factors to seconds
            unit_to_seconds = {
                'ns': 1e-9,
                'µs': 1e-6,
                'ms': 1e-3,
                's': 1.0
            }
            
            time_params = ['pulse_width', 'delay_between', 'delay_between_pulses', 
                          'delay_between_reads', 'delay_before_read', 'delay_between_cycles', 
                          'post_read_interval', 'reset_width', 'delay_between_voltages', 
                          'delay_between_levels']
            read_pulse_params = ['read_width', 'read_delay', 'read_rise_time']
            
            for param_name, param_info in self.param_vars.items():
                try:
                    var = param_info["var"]
                    param_type = param_info["type"]
                    is_time_param = param_info.get("is_time_param", False)
                    
                    if param_type == "float":
                        value_str = var.get()
                        if value_str:  # Only save if there's a value
                            value = float(value_str)
                            
                            # Convert from old unit to new unit
                            if param_name in read_pulse_params and is_4200a:
                                # For 4200A read pulse params, they're always in µs
                                # Convert: old_unit → seconds → µs → new_unit
                                old_to_sec = unit_to_seconds.get(old_unit, 1e-3)
                                sec_to_new = 1.0 / unit_to_seconds.get(new_unit, 1e-3)
                                # If old unit was µs, value is already in µs
                                if old_unit == 'µs':
                                    value_in_us = value
                                else:
                                    # Convert from old unit to µs
                                    value_in_seconds = value * old_to_sec
                                    value_in_us = value_in_seconds / 1e-6
                                # Convert from µs to new unit
                                value_in_seconds = value_in_us * 1e-6
                                saved_values[param_name] = value_in_seconds * sec_to_new
                            elif param_name == 'delay_before_read' and is_4200a:
                                # Similar handling for delay_before_read (always in µs for 4200A)
                                if old_unit == 'µs':
                                    value_in_us = value
                                else:
                                    old_to_sec = unit_to_seconds.get(old_unit, 1e-3)
                                    value_in_seconds = value * old_to_sec
                                    value_in_us = value_in_seconds / 1e-6
                                # Convert from µs to new unit
                                value_in_seconds = value_in_us * 1e-6
                                sec_to_new = 1.0 / unit_to_seconds.get(new_unit, 1e-3)
                                saved_values[param_name] = value_in_seconds * sec_to_new
                            elif is_time_param or param_name in time_params:
                                # Regular time parameter: convert from old unit to new unit
                                old_to_sec = unit_to_seconds.get(old_unit, 1e-3)
                                sec_to_new = 1.0 / unit_to_seconds.get(new_unit, 1e-3)
                                value_in_seconds = value * old_to_sec
                                saved_values[param_name] = value_in_seconds * sec_to_new
                            else:
                                saved_values[param_name] = value
                    elif param_type == "int":
                        value_str = var.get()
                        if value_str:
                            saved_values[param_name] = int(value_str)
                    elif param_type == "bool":
                        saved_values[param_name] = var.get()
                except (ValueError, AttributeError):
                    # Skip invalid values
                    pass
        
        # Repopulate parameters (this will create new fields with defaults)
        self.populate_parameters()
        
        # Restore saved values (converted to new unit)
        if saved_values and hasattr(self, 'param_vars'):
            for param_name, value in saved_values.items():
                if param_name in self.param_vars:
                    try:
                        self.param_vars[param_name]["var"].set(str(value))
                    except (KeyError, AttributeError):
                        pass
        
        self.update_pulse_diagram()

    def populate_parameters(self):
        """Populate parameter inputs based on selected test"""
        # Check if test_var exists yet (might not during initial UI creation)
        if not hasattr(self, 'test_var'):
            return
        
        # Clear existing
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        self.param_vars.clear()
        
        test_name = self.test_var.get()
        if test_name not in TEST_FUNCTIONS:
            return
        
        params = TEST_FUNCTIONS[test_name]["params"]
        row = 0
        
        # Add warning disclaimer for Current Range Finder
        if test_name == "Current Range Finder":
            warning_frame = tk.Frame(self.params_frame, bg="red", relief=tk.RAISED, bd=2)
            warning_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
            
            warning_text = (
                "⚠️ WARNING: This test has known issues and needs fixing!\n"
                "• Graph displays incorrect data\n"
                "• Warning: 'range_stats' column length mismatch (e.g., 2 vs 20)\n"
                "• SMU does not set the measurement range correctly\n"
                "• Source limit errors (5076/5077) may occur\n"
                "Do not rely on results from this test until fixed."
            )
            
            warning_label = tk.Label(warning_frame, text=warning_text, 
                                    bg="red", fg="white", font=("TkDefaultFont", 9, "bold"),
                                    justify=tk.LEFT, wraplength=400)
            warning_label.pack(padx=5, pady=5)
            
            row += 1
        
        # Check if current system is 4200A (use µs instead of ms)
        is_4200a = self.current_system_name in ('keithley4200a',)
        # Time parameters that should be in µs for 4200A
        time_params = ['pulse_width', 'delay_between', 'delay_between_pulses', 
                      'delay_between_reads', 'delay_before_read', 'delay_between_cycles', 'post_read_interval',
                      'reset_width', 'delay_between_voltages', 'delay_between_levels']
        
        # Default values for 4200A (in µs) - different from 2450 defaults
        # For 4200A, we want 1 µs for pulse_width and delays, not 1000 µs (1 ms)
        defaults_4200a = {
            'pulse_width': 1.0,  # 1 µs (matches example: 1e-6 s = 1 µs)
            'delay_between': 10.0,  # 10 µs (for pulse_read_repeat, matches example: 1e-6 s = 1 µs for pulse_delay)
            'delay_between_cycles': 10.0,  # 10 µs
            'delay_between_pulses': 1.0,  # 1 µs
            'delay_between_reads': 10.0,  # 10 µs
            'delay_before_read': 0.02,  # 0.02 µs = 20 ns (minimum allowed by 4200A)
            'read_width': 0.5,  # 0.5 µs (matches example: 0.5e-6 s = 0.5 µs)
            'read_delay': 1.0,  # 1 µs (matches example: 1e-6 s = 1 µs)
            'read_rise_time': 0.1,  # 0.1 µs (matches example: 1e-7 s = 0.1 µs)
            'post_read_interval': 1.0,  # 1 µs
            'reset_width': 1.0,  # 1 µs
            'delay_between_voltages': 1000.0,  # 1000 µs = 1 ms
            'delay_between_levels': 1000.0,  # 1000 µs = 1 ms
        }

        if hasattr(self, 'time_unit_var'):
            selected_unit = self.time_unit_var.get()
        else:
            selected_unit = 'µs' if is_4200a else 'ms'

        unit_to_seconds = {
            'ns': 1e-9,
            'µs': 1e-6,
            'ms': 1e-3,
            's': 1.0
        }

        def extract_unit(label):
            import re
            match = re.search(r'\(([^)]+)\)', label)
            if not match:
                return None
            token = match.group(1).lower()
            if 'ns' in token:
                return 'ns'
            if 'µs' in token or 'us' in token:
                return 'µs'
            if 'ms' in token:
                return 'ms'
            if 's' in token:
                return 's'
            return None

        # Categorize parameters into sections
        pulse_params = []
        read_params = []
        general_params = []
        other_params = []
        
        # Define parameter categories
        pulse_keywords = ['pulse', 'set_voltage', 'reset_voltage', 'laser_voltage']
        read_keywords = ['read', 'meas']
        general_keywords = ['num_cycles', 'num_pulses', 'num_reads', 'steps', 'delay_between_cycles', 
                           'delay_between_widths', 'delay_between_voltages', 'delay_between_levels']
        other_keywords = ['clim', 'enable_debug', 'sample_rate', 'volts_source', 'current_measure', 
                         'pulse_widths', 'pulse_voltage_step']
        
        for param_name, param_info in params.items():
            # Skip 4200A-only parameters if not using 4200A
            if param_info.get("4200a_only", False) and not is_4200a:
                continue
            
            # Categorize parameter
            param_lower = param_name.lower()
            if any(keyword in param_lower for keyword in pulse_keywords):
                pulse_params.append((param_name, param_info))
            elif any(keyword in param_lower for keyword in read_keywords):
                read_params.append((param_name, param_info))
            elif any(keyword in param_lower for keyword in general_keywords):
                general_params.append((param_name, param_info))
            else:
                other_params.append((param_name, param_info))
        
        # Helper function to add a parameter row
        def add_param_row(param_name, param_info, current_row):
            # Handle checkbox/boolean parameters
            if param_info.get("type") == "bool" or param_info.get("type") == "checkbox":
                default_value = param_info.get("default", False)
                var = tk.BooleanVar(value=default_value)
                checkbox = tk.Checkbutton(self.params_frame, text=param_info["label"], variable=var)
                checkbox.grid(row=current_row, column=0, columnspan=2, sticky="w", padx=5, pady=2)
                # Store checkbox variable
                self.param_vars[param_name] = {
                    "var": var,
                    "type": "bool",
                    "is_time_param": False,
                    "original_label": param_info["label"]
                }
                return current_row + 1
            
            # Adjust label and default for 4200A time parameters
            label = param_info["label"]
            default_value = param_info["default"]
            
            if param_name in time_params:
                import re
                base_unit = extract_unit(label) or ('µs' if is_4200a else 'ms')
                # Replace unit in parentheses, handling cases like "(ms)", "(µs)", "(ms) [4200A only]", etc.
                if '(' in label:
                    # Match pattern like "(ms)", "(µs)", "(ms) [4200A only]", etc.
                    # Replace the first occurrence of unit in parentheses with the selected unit
                    # This handles "Delay Before Read (ms)" -> "Delay Before Read (µs)"
                    label = re.sub(r'\([^)]*\)', f'({selected_unit})', label, count=1)
                else:
                    label = f"{label} ({selected_unit})"
                if isinstance(default_value, (int, float)):
                    if is_4200a and param_name in defaults_4200a:
                        base_seconds = defaults_4200a[param_name] * 1e-6
                    else:
                        base_seconds = default_value * unit_to_seconds.get(base_unit, 1.0)
                    default_value = base_seconds / unit_to_seconds.get(selected_unit, 1e-3)
            # Label
            tk.Label(self.params_frame, text=label, anchor="w").grid(
                row=current_row, column=0, sticky="w", padx=5, pady=2)
            
            # Entry
            var = tk.StringVar(value=str(default_value))
            entry = tk.Entry(self.params_frame, textvariable=var, width=20)
            entry.grid(row=current_row, column=1, sticky="ew", padx=5, pady=2)
            
            # Bind entry to update diagram when changed
            var.trace_add("write", lambda *args: self.update_pulse_diagram())
            
            # Store original label and whether this is a time param for 4200A
            self.param_vars[param_name] = {
                "var": var, 
                "type": param_info["type"],
                "is_time_param": param_name in time_params,
                "original_label": param_info["label"]
            }
            return current_row + 1
        
        # Helper function to add a section header
        def add_section_header(title, current_row):
            # Add separator line
            separator = tk.Frame(self.params_frame, height=2, bg="gray", relief=tk.SUNKEN)
            separator.grid(row=current_row, column=0, columnspan=2, sticky="ew", padx=5, pady=(8, 4))
            current_row += 1
            # Add section title
            header = tk.Label(self.params_frame, text=title, font=("TkDefaultFont", 9, "bold"), 
                            anchor="w", bg="#e0e0e0", relief=tk.RAISED, bd=1)
            header.grid(row=current_row, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 4))
            current_row += 1
            return current_row
        
        # Display parameters in organized sections
        # Pulse Parameters Section
        if pulse_params:
            row = add_section_header("⚡ Pulse Parameters", row)
            for param_name, param_info in pulse_params:
                row = add_param_row(param_name, param_info, row)
        
        # Read Parameters Section
        if read_params:
            row = add_section_header("📖 Read Parameters", row)
            for param_name, param_info in read_params:
                row = add_param_row(param_name, param_info, row)
        
        # General/Cycle Parameters Section
        if general_params:
            row = add_section_header("🔄 Cycle & Timing Parameters", row)
            for param_name, param_info in general_params:
                row = add_param_row(param_name, param_info, row)
        
        # Other Parameters Section
        if other_params:
            row = add_section_header("⚙️ Other Parameters", row)
            for param_name, param_info in other_params:
                row = add_param_row(param_name, param_info, row)
        
        self.params_frame.columnconfigure(1, weight=1)
        
        # Update preset dropdown for new test type
        if hasattr(self, 'preset_dropdown'):
            self.update_preset_dropdown()
    
    def get_test_parameters(self):
        """Extract and validate parameters"""
        params = {}
        time_params = ['pulse_width', 'delay_between', 'delay_between_pulses', 
                      'delay_between_reads', 'delay_before_read', 'delay_between_cycles', 
                      'post_read_interval', 'reset_width', 'delay_between_voltages', 
                      'delay_between_levels']
        
        read_pulse_params = ['read_width', 'read_delay', 'read_rise_time']
        laser_params = ['read_period', 'laser_width', 'laser_delay', 'laser_rise_time', 'laser_fall_time']
        # Parameters that 4200A expects in µs (not seconds)
        # These are converted to µs in the GUI, so the wrapper should NOT convert them again
        params_4200a_in_us = ['pulse_width', 'delay_between_pulses', 'delay_between_cycles', 'delay_between', 
                              'delay_between_reads', 'reset_width']
        is_4200a = self.current_system_name in ('keithley4200a',)
        
        if hasattr(self, 'time_unit_var'):
            selected_unit = self.time_unit_var.get()
        else:
            selected_unit = 'µs' if is_4200a else 'ms'
        
        unit_to_seconds = {
            'ns': 1e-9,
            'µs': 1e-6,
            'ms': 1e-3,
            's': 1.0
        }
        
        def to_seconds(value):
            return value * unit_to_seconds.get(selected_unit, 1e-3)
        
        def to_microseconds(value):
            factor = unit_to_seconds.get(selected_unit, 1e-3)
            return (value * factor) / 1e-6
        
        for param_name, param_info in self.param_vars.items():
            var = param_info["var"]
            param_type = param_info["type"]
            is_time_param = param_info.get("is_time_param", False)
            
            try:
                if param_type == "bool":
                    params[param_name] = var.get()
                elif param_type == "int":
                    params[param_name] = int(var.get())
                elif param_type == "float":
                    value = float(var.get())
                    if param_name in read_pulse_params and is_4200a:
                        params[param_name] = to_microseconds(value)
                    elif param_name in laser_params and is_4200a:
                        # Laser parameters are labeled in µs, convert to µs for 4200A
                        params[param_name] = to_microseconds(value)
                    elif param_name == 'delay_before_read' and is_4200a:
                        # Convert to µs and enforce minimum of 0.02 µs (20 ns) for 4200A
                        delay_us = to_microseconds(value)
                        if delay_us < 0.02:
                            delay_us = 0.02  # Minimum allowed by 4200A (2e-8 seconds = 20 ns)
                        params[param_name] = delay_us
                    elif param_name in params_4200a_in_us and is_4200a:
                        # For 4200A, these parameters need to be in µs (will be converted to seconds in system wrapper)
                        param_us = to_microseconds(value)
                        # Enforce minimum of 0.02 µs (20 ns) for pulse_delay and similar parameters
                        if param_name in ['delay_between_pulses', 'pulse_width'] and param_us < 0.02:
                            param_us = 0.02  # Minimum allowed by 4200A (2e-8 seconds = 20 ns)
                        params[param_name] = param_us
                        # Debug: print conversion for verification
                        print(f"[GUI] {param_name}: {value} {selected_unit} → {param_us:.2f} µs")
                    elif is_time_param:
                        params[param_name] = to_seconds(value)
                    else:
                        params[param_name] = value
                elif param_type == "list":
                    params[param_name] = [float(x.strip()) for x in var.get().split(",")]
                else:
                    params[param_name] = var.get()
            except Exception as e:
                raise ValueError(f"Invalid value for {param_name}: {e}")
        
        return params
    def run_test(self):
        """Start test in background thread"""
        if not self.system_wrapper.is_connected():
            messagebox.showerror("Error", "Not connected to device")
            return
        
        if self.test_running:
            messagebox.showwarning("Warning", "Test already running")
            return
        
        # Check if test is supported
        test_name = self.test_var.get()
        test_info = TEST_FUNCTIONS[test_name]
        test_function = test_info["function"]
        
        if self.current_system_name and not is_test_supported(self.current_system_name, test_function):
            explanation = get_test_explanation(self.current_system_name, test_function)
            messagebox.showwarning(
                "Test Not Supported",
                f"Test '{test_name}' is not supported by {self.current_system_name}.\n\n{explanation}"
            )
            return
        
        # Get parameters
        try:
            params = self.get_test_parameters()
        except Exception as e:
            messagebox.showerror("Parameter Error", str(e))
            return
        
        # Clear previous results so failures don't re-use stale data
        self.last_results = None
        
        # UI state
        self.test_running = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.DISABLED)
        self.log(f"▶ Starting: {test_name}")
        
        # Run in thread
        self.test_thread = threading.Thread(target=self._run_test_thread, 
                                             args=(test_info, params), daemon=True)
        self.test_thread.start()
    
    def _run_test_thread(self, test_info, params):
        """Execute test in background using logic.run_test_worker; schedule GUI updates on main thread."""
        from gui.pulse_testing_gui import logic

        func_name = test_info["function"]

        def progress_callback(partial_results):
            try:
                self.last_results = partial_results
                self.last_results["test_name"] = self.test_var.get()
                self.last_results["params"] = params
                self.last_results["plot_type"] = test_info["plot_type"]
                self.after(0, self._plot_incremental)
            except Exception:
                pass

        self.log(f"Executing {func_name} on {self.current_system_name}...")
        start_time = time.time()
        results, err = logic.run_test_worker(
            self.system_wrapper, func_name, params,
            progress_callback=progress_callback if func_name in (
                "smu_endurance", "smu_retention", "smu_retention_with_pulse_measurement"
            ) else None,
        )

        if err is not None:
            self.last_results = None
            self.log(f"❌ Test error: {err}")
            import traceback
            traceback.print_exc()
            self.after(0, lambda: messagebox.showerror("Test Error", str(err)))
            self.after(0, self._test_finished)
            return

        elapsed = time.time() - start_time
        self.log(f"✓ Test complete in {elapsed:.2f}s")
        self.log(f"  {len(results['timestamps'])} measurements")

        self.last_results = results
        self.last_results["test_name"] = self.test_var.get()
        self.last_results["params"] = params
        self.last_results["plot_type"] = test_info["plot_type"]

        if func_name == "current_range_finder":
            def show_popup():
                try:
                    self._show_range_finder_popup(results)
                except Exception as e:
                    self.log(f"⚠️ Could not show range finder popup: {e}")
                    import traceback
                    traceback.print_exc()
            self.after(100, show_popup)

        def plot_and_finish():
            try:
                self.plot_results()
                self.after(100, self._test_finished)
            except Exception as e:
                self.log(f"❌ Plot error: {e}")
                self._test_finished()
        self.after(0, plot_and_finish)
    
    def stop_test(self):
        """Stop running test"""
        # TSP tests run entirely on instrument, so can't easily stop
        self.log("⚠ Test runs on instrument - wait for completion")
    
    def _test_finished(self):
        """Clean up after test and auto-save (if enabled)"""
        self.test_running = False
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.NORMAL if self.last_results else tk.DISABLED)
        
        # Auto-save data after successful test (if enabled)
        if self.last_results and self.auto_save_var.get():
            try:
                self.log("💾 Auto-saving data...")
                success = self.save_data(show_dialog=False)
                if success:
                    self.log("✓ Data automatically saved")
                else:
                    self.log("⚠ Auto-save failed - use Manual Save button")
            except Exception as e:
                self.log(f"❌ Auto-save error: {e}")
                import traceback
                traceback.print_exc()
        elif self.last_results and not self.auto_save_var.get():
            self.log("ℹ Auto-save disabled - use Manual Save to save data")
        else:
            self.log("⚠ No data to save")
    
    def _plot_incremental(self):
        """Update plot incrementally for real-time updates (e.g., SMU retention)"""
        if not self.last_results:
            return
        try:
            self.ax.clear()
            from gui.pulse_testing_gui import plot_handlers
            plot_handlers.plot_by_type(self, self.last_results.get('plot_type', 'time_series'))
            self.canvas.draw()
        except Exception:
            pass

    def plot_results(self):
        """Plot test results (dispatches by plot_type via plot_handlers)."""
        if not self.last_results:
            return
        self.ax.clear()
        try:
            from gui.pulse_testing_gui import plot_handlers
            plot_handlers.plot_by_type(self, self.last_results.get('plot_type', 'time_series'))
            self.canvas.draw()
        except Exception as e:
            self.log(f"Plot error: {e}")
    
    
    def save_data(self, show_dialog=False, extra_notes=None):
        """Save test results automatically using standardized format
        
        Args:
            show_dialog: If True, show success dialog (for manual saves)
            extra_notes: Additional notes to include in metadata
        """
        if not self.last_results:
            if show_dialog:
                messagebox.showwarning("No Data", "No test results to save")
            return False
        
        try:
            formatter = TSPDataFormatter()
            
            # PRIORITY 1: If provider (Measurement GUI) is available, use its default save structure
            # This matches where SMU measurements are saved: [default_save_root]/[sample_name]/[section]/[device_number]/
            use_provider_default = False
            default_save_root = None
            sample_name = None
            device_section = None
            
            if self.provider is not None:
                # Get default save root (same as Measurement GUI uses for SMU measurements)
                default_save_root = getattr(self.provider, 'default_save_root', None)
                
                # Get sample name from provider
                sn = getattr(self.provider, 'sample_name_var', None)
                if sn is not None:
                    try:
                        sample_name = sn.get().strip()
                    except Exception:
                        pass
                
                # Fallback: try sample_gui's current_device_name
                if not sample_name and hasattr(self.provider, 'sample_gui') and self.provider.sample_gui:
                    sample_name = getattr(self.provider.sample_gui, 'current_device_name', None)
                
                # Get device section and number
                device_section = getattr(self.provider, 'device_section_and_number', None)
                
                # Check if we have all required info to use provider's default structure
                if default_save_root and sample_name and device_section:
                    use_provider_default = True
            
            # PRIORITY 2: Use provider's default save structure (matches SMU measurement location)
            if use_provider_default and default_save_root and sample_name and device_section:
                # Extract section (letter) and device number from device_section (e.g., "H4" -> "H" and "4")
                section = device_section[0] if len(device_section) > 0 else "A"
                device_num = device_section[1:] if len(device_section) > 1 else "1"
                
                # Build path: [default_save_root]/[sample_name]/[section]/[device_number]/Pulse_measurements
                # This matches exactly where SMU measurements are saved
                save_dir = Path(default_save_root) / sample_name / section / device_num / "Pulse_measurements"
                save_dir.mkdir(parents=True, exist_ok=True)
                
                # Get next index for sequential numbering
                max_num = find_largest_number_in_folder(str(save_dir))
                index = 0 if max_num is None else max_num + 1
                
                # Update device_label and sample_name for display
                self.device_label = device_section
                self.sample_name = sample_name
            else:
                # PRIORITY 3: Check if simple save mode is enabled (only if no provider location)
                if self.use_simple_save_var.get() and self.simple_save_path:
                    # Simple save: everything in one folder (standalone mode only)
                    save_dir = Path(self.simple_save_path)
                    save_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Get next index for sequential numbering (simple mode)
                    max_num = find_largest_number_in_folder(str(save_dir))
                    index = 0 if max_num is None else max_num + 1
                else:
                    # PRIORITY 4: Use default structure (FileNamer)
                    # If sample name is still unknown, try to get from provider or use default
                    if self.sample_name == "UnknownSample" and self.provider is not None:
                        sn = getattr(self.provider, 'sample_name_var', None)
                        if sn is not None:
                            provider_sample_name = sn.get().strip()
                            if provider_sample_name:
                                self.sample_name = provider_sample_name
                    
                    # When using custom base, sample_name is not used in path, but we still need to pass something
                    namer = FileNamer(base_dir=self.custom_base_path)
                    save_dir = namer.get_device_folder(
                        sample_name=self.sample_name,
                        device=self.device_label if self.device_label != "UnknownDevice" else "A1",
                        subfolder="Pulse_measurements"
                    )
                    save_dir.mkdir(parents=True, exist_ok=True)
                    index = namer.get_next_index(save_dir)
            
            # Create test details string with key parameters (max 3)
            test_name = self.last_results['test_name']
            params = self.last_results.get('params', {})
            test_details = self._generate_test_details(params)
            
            # Get filename suffix if provided
            filename_suffix = self.filename_suffix_var.get().strip()
            # Sanitize suffix: remove invalid filename characters
            if filename_suffix:
                import re
                filename_suffix = re.sub(r'[<>:"/\\|?*]', '_', filename_suffix)
                filename_suffix = filename_suffix.replace(' ', '_')
                suffix_str = f"-{filename_suffix}" if filename_suffix else ""
            else:
                suffix_str = ""
            
            # Create filename
            # Use simple mode naming only if using simple save AND no provider default structure
            using_simple_save_mode = (self.use_simple_save_var.get() and self.simple_save_path 
                                     and not use_provider_default)
            
            if using_simple_save_mode:
                # Simple mode: number at start, then test name + details + suffix + timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                test_clean = test_name.replace(" ", "_").replace("-", "_")
                details_str = f"-{test_details}" if test_details else ""
                filename = f"{index}-{test_clean}{details_str}{suffix_str}-{timestamp}.txt"
            else:
                # Structured mode: use FileNamer, then add suffix before extension
                namer = FileNamer(base_dir=self.custom_base_path)
                filename = namer.create_tsp_filename(test_name, index, extension="txt", test_details=test_details)
                # Add suffix before file extension
                if suffix_str:
                    filename = filename.rsplit('.', 1)[0] + suffix_str + '.' + filename.rsplit('.', 1)[1]
            
            filepath = save_dir / filename
            
            # Get notes from text widget
            notes = self.notes_text.get(1.0, tk.END).strip()
            if notes == "Add notes about this test here...":
                notes = ""
            if extra_notes:
                notes = f"{notes}\n{extra_notes}" if notes else extra_notes
            
            # Extract sample name for metadata
            # Priority: 1) From provider's default structure (already set), 2) From provider's sample_name_var, 3) Current sample_name
            sample_name_for_metadata = self.sample_name
            
            # If using provider's default structure, sample_name is already set correctly above
            # Otherwise, try to get from provider's sample_name_var
            if sample_name_for_metadata == "UnknownSample" and self.provider is not None:
                sn = getattr(self.provider, 'sample_name_var', None)
                if sn is not None:
                    try:
                        provider_sample_name = sn.get().strip()
                        if provider_sample_name:
                            sample_name_for_metadata = provider_sample_name
                    except Exception:
                        pass
                
                # Fallback: try sample_gui's current_device_name
                if sample_name_for_metadata == "UnknownSample" and hasattr(self.provider, 'sample_gui') and self.provider.sample_gui:
                    fallback_name = getattr(self.provider.sample_gui, 'current_device_name', None)
                    if fallback_name:
                        sample_name_for_metadata = str(fallback_name).strip()
            
            # Prepare metadata
            metadata = {
                'sample': sample_name_for_metadata,
                'device': self.device_label,
                'instrument': 'Keithley 2450',  # Default, will be updated below
                'address': self.addr_var.get() if hasattr(self, 'addr_var') else 'N/A',
                'test_index': index,
                'notes': notes,
            }
            
            # Add hardware limits from system wrapper if available
            if self.system_wrapper.is_connected():
                try:
                    limits = self.system_wrapper.get_hardware_limits()
                    if limits:
                        # Format limits for metadata
                        metadata['hardware_limits'] = {
                            'min_pulse_width': f"{limits.get('min_pulse_width', 0)*1e3:.3f} ms",
                            'max_voltage': f"{limits.get('max_voltage', 0)} V",
                            'max_current_limit': f"{limits.get('max_current_limit', 0)} A",
                        }
                        metadata['instrument'] = f"{self.current_system_name.upper()}" if self.current_system_name else "Unknown"
                except:
                    pass
            # Legacy fallback for compatibility
            elif hasattr(self, 'test_scripts') and self.test_scripts:
                try:
                    metadata['hardware_limits'] = {
                        'min_pulse_width': f"{self.test_scripts.MIN_PULSE_WIDTH*1e3:.3f} ms",
                        'max_voltage': f"{self.test_scripts.MAX_VOLTAGE} V",
                        'max_current_limit': f"{self.test_scripts.MAX_CURRENT_LIMIT} A",
                    }
                    metadata['instrument'] = 'Keithley 2450'
                except:
                    pass
            
            # Format data using standardized formatter
            data, header, fmt, full_metadata = formatter.format_tsp_data(
                data_dict=self.last_results,
                test_name=test_name,
                params=self.last_results.get('params', {}),
                metadata=metadata
            )
            
            # Ensure plot is updated before saving
            if hasattr(self, 'fig') and self.fig is not None:
                self.canvas.draw_idle()
                self.master.update_idletasks()
            
            # Save using standardized function (saves .txt, .png, and log)
            success = save_tsp_measurement(
                filepath=filepath,
                data=data,
                header=header,
                fmt=fmt,
                metadata=full_metadata,
                save_plot=self.fig if hasattr(self, 'fig') else None
            )
            
            if success:
                # Display full filepath for easy finding
                plot_path = filepath.with_suffix('.png')
                abs_save_dir = filepath.parent.resolve()
                abs_data_path = filepath.resolve()
                abs_plot_path = plot_path.resolve()
                
                self.log(f"✓ Saved to: {filepath}")
                self.log(f"📁 Save folder: {abs_save_dir}")
                self.log(f"   Data file: {filepath.name}")
                self.log(f"   Plot file: {plot_path.name}")
                
                # Print to console with full absolute paths
                print(f"\n{'='*70}")
                print(f"[PulseTesting] Data saved successfully!")
                print(f"[PulseTesting] Save location: {abs_save_dir}")
                print(f"[PulseTesting] Data file: {abs_data_path}")
                print(f"[PulseTesting] Plot file: {abs_plot_path}")
                print(f"{'='*70}\n")
                if show_dialog:
                    messagebox.showinfo("Success", 
                        f"Test #{index} saved successfully!\n\n"
                        f"Location:\n{filepath.parent}\n\n"
                        f"Files:\n"
                        f"  • {filepath.name}\n"
                        f"  • {filepath.with_suffix('.png').name}")
                return True
            else:
                raise Exception("Save function returned False")
                
        except Exception as e:
            self.log(f"❌ Save error: {e}")
            if show_dialog:
                messagebox.showerror("Save Error", str(e))
            import traceback
            traceback.print_exc()
            return False
    
    def manual_save_with_notes(self):
        """Manually save data with current notes"""
        self.save_data(show_dialog=True)
    
    def open_data_analysis(self):
        """Open the TSP Data Analysis Tool"""
        try:
            # Get the path to the analysis tool
            # TSP_Testing_GUI.py is in the root, so parent is the root directory
            analysis_script = Path(__file__).resolve().parents[2] / "tools" / "data_analysis_pulse_2450" / "main.py"
            
            if not analysis_script.exists():
                messagebox.showerror("Analysis Tool Not Found", 
                    f"Could not find analysis tool at:\n{analysis_script}\n\n"
                    "Please ensure the tools/data_analysis_pulse_2450 folder exists.")
                return
            
            # Launch the analysis tool in a separate process
            # Use pythonw on Windows to avoid showing console window
            if sys.platform == "win32":
                # Try pythonw first, fallback to python if pythonw doesn't exist
                python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                if not Path(python_exe).exists():
                    python_exe = sys.executable
                # CREATE_NO_WINDOW flag to hide console window on Windows
                try:
                    subprocess.Popen([python_exe, str(analysis_script)],
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                except AttributeError:
                    # Fallback if CREATE_NO_WINDOW is not available
                    subprocess.Popen([python_exe, str(analysis_script)])
            else:
                subprocess.Popen([sys.executable, str(analysis_script)])
            
            self.log("📊 Opening TSP Data Analysis Tool...")
            
        except Exception as e:
            self.log(f"❌ Error opening analysis tool: {e}")
            messagebox.showerror("Error", f"Could not open analysis tool:\n{e}")
    
    def _show_range_finder_popup(self, results: dict):
        """Show popup window with range finder results and recommendations"""
        try:
            popup = tk.Toplevel(self.master)
            popup.title("Current Range Finder Results")
            popup.geometry(config.RANGE_FINDER_POPUP_GEOMETRY)
            popup.transient(self.master)
            popup.grab_set()
        except Exception as e:
            self.log(f"⚠️ Error creating popup window: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Main frame with padding
        main_frame = ttk.Frame(popup, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Current Range Finder Results", 
                                font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Get range stats
        range_stats = results.get('range_stats', [])
        recommended_range = results.get('recommended_range', None)
        
        if not range_stats:
            ttk.Label(main_frame, text="No range statistics available", 
                     foreground="red").pack()
            ttk.Button(main_frame, text="Close", command=popup.destroy).pack(pady=10)
            return
        
        # Recommendation section
        rec_frame = ttk.LabelFrame(main_frame, text="Recommendation", padding="10")
        rec_frame.pack(fill=tk.X, pady=(0, 10))
        
        if recommended_range:
            rec_text = f"✓ RECOMMENDED RANGE: {recommended_range*1e6:.1f} µA"
            # Find the stats for recommended range
            rec_stats = next((s for s in range_stats if s['range_limit'] == recommended_range), None)
            if rec_stats:
                rec_text += f"\n\n• Mean Current: {rec_stats['mean_current']*1e6:.3f} µA"
                rec_text += f"\n• Stability (CV): {rec_stats['cv_percent']:.2f}%"
                rec_text += f"\n• Mean Resistance: {rec_stats['mean_resistance']:.2e} Ω"
                rec_text += f"\n• No negative readings"
                if rec_stats['has_negative']:
                    rec_text += " ⚠️ (Actually has negatives - check data)"
        else:
            rec_text = "⚠ No ideal range found - check your device/connections"
        
        rec_label = ttk.Label(rec_frame, text=rec_text, font=("Arial", 10))
        rec_label.pack(anchor=tk.W)
        
        # Results table
        table_frame = ttk.LabelFrame(main_frame, text="All Ranges Tested", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create treeview for table
        columns = ("Range", "Mean Current", "Std Dev", "CV %", "Min", "Max", "Resistance", "Status")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=len(range_stats))
        
        # Configure columns
        tree.heading("Range", text="Range Limit (µA)")
        tree.heading("Mean Current", text="Mean (µA)")
        tree.heading("Std Dev", text="Std Dev (µA)")
        tree.heading("CV %", text="CV %")
        tree.heading("Min", text="Min (µA)")
        tree.heading("Max", text="Max (µA)")
        tree.heading("Resistance", text="Resistance (Ω)")
        tree.heading("Status", text="Status")
        
        tree.column("Range", width=100, anchor=tk.CENTER)
        tree.column("Mean Current", width=100, anchor=tk.CENTER)
        tree.column("Std Dev", width=90, anchor=tk.CENTER)
        tree.column("CV %", width=70, anchor=tk.CENTER)
        tree.column("Min", width=90, anchor=tk.CENTER)
        tree.column("Max", width=90, anchor=tk.CENTER)
        tree.column("Resistance", width=120, anchor=tk.CENTER)
        tree.column("Status", width=80, anchor=tk.CENTER)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Populate table
        try:
            for stats in range_stats:
                status = "✓ OK" if not stats['has_negative'] else "✗ Neg"
                if recommended_range and stats['range_limit'] == recommended_range:
                    status = "★ REC"
                
                # Format resistance
                if stats['mean_resistance'] >= 1e12:
                    res_str = ">1e12"
                elif stats['mean_resistance'] >= 1e6:
                    res_str = f"{stats['mean_resistance']:.2e}"
                else:
                    res_str = f"{stats['mean_resistance']:.2f}"
                
                values = (
                    f"{stats['range_limit']*1e6:.1f}",
                    f"{stats['mean_current']*1e6:.3f}",
                    f"{stats['std_current']*1e6:.3f}",
                    f"{stats['cv_percent']:.2f}",
                    f"{stats['min_current']*1e6:.3f}",
                    f"{stats['max_current']*1e6:.3f}",
                    res_str,
                    status
                )
                
                item = tree.insert("", tk.END, values=values)
                
                # Highlight recommended range
                if recommended_range and stats['range_limit'] == recommended_range:
                    tree.set(item, "Status", "★ RECOMMENDED")
        except Exception as e:
            self.log(f"⚠️ Error populating range finder table: {e}")
            import traceback
            traceback.print_exc()
            ttk.Label(table_frame, text=f"Error displaying table: {e}", 
                     foreground="red").pack()
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Close", command=popup.destroy).pack()
    
    def _generate_test_details(self, params: dict) -> str:
        """
        Generate test details string for filename (max 3 most important parameters).
        
        Args:
            params: Test parameters dictionary
        
        Returns:
            str: Formatted test details (e.g., "1.5V_100us_10cyc")
        """
        details = []
        
        # Voltage (if present)
        if 'pulse_voltage' in params:
            v = params['pulse_voltage']
            details.append(f"{abs(v):.1f}V")
        elif 'set_voltage' in params:
            # For SMU endurance tests
            v = params['set_voltage']
            details.append(f"{abs(v):.1f}V")
        
        # Pulse width/duration - VITAL for retention and endurance tests
        # Check for SMU retention/endurance duration parameters first (these are in seconds)
        if 'pulse_duration' in params:
            # SMU retention test: pulse_duration is in seconds
            pd = params['pulse_duration']
            if pd >= 1.0:
                details.append(f"{pd:.1f}s")
            elif pd >= 1e-3:
                details.append(f"{pd*1e3:.0f}ms")
            else:
                details.append(f"{pd*1e6:.0f}us")
        elif 'set_duration' in params or 'reset_duration' in params:
            # SMU endurance test: set_duration and reset_duration are in seconds
            # Use set_duration as primary (most important), include reset if different
            if 'set_duration' in params:
                sd = params['set_duration']
                if sd >= 1.0:
                    details.append(f"{sd:.1f}s")
                elif sd >= 1e-3:
                    details.append(f"{sd*1e3:.0f}ms")
                else:
                    details.append(f"{sd*1e6:.0f}us")
            # If reset_duration is different and significant, could add it, but keep max 3 params
        elif 'pulse_width' in params:
            # Regular PMU tests: pulse_width is in microseconds
            pw = params['pulse_width']
            if pw >= 1e-3:
                details.append(f"{pw*1e3:.0f}ms")
            else:
                details.append(f"{pw*1e6:.0f}us")
        
        # Number of pulses/cycles/reads (pick one that exists)
        for key in ['num_pulses', 'num_cycles', 'num_reads']:
            if key in params:
                val = params[key]
                short_name = key.split('_')[1][:3]  # "pul", "cyc", "rea"
                details.append(f"{val}{short_name}")
                break  # Only include one count parameter
        
        return "_".join(details[:3])  # Max 3 parameters
    
    def update_pulse_diagram(self):
        """Update the pulse pattern diagram based on selected test and parameters"""
        if not hasattr(self, 'diagram_ax'):
            return
        if not hasattr(self, 'test_var'):
            return
        
        test_name = self.test_var.get()
        if test_name not in TEST_FUNCTIONS:
            self.diagram_ax.clear()
            self.diagram_ax.text(0.5, 0.5, "Select a test", ha='center', va='center')
            self.diagram_canvas.draw()
            return
        
        try:
            is_4200a = self.current_system_name in ('keithley4200a',)
            time_params = ['pulse_width', 'delay_between', 'delay_between_pulses', 
                          'delay_between_reads', 'delay_before_read', 'delay_between_cycles', 
                          'post_read_interval', 'reset_width', 'delay_between_voltages', 
                          'delay_between_levels']
            read_pulse_params = ['read_width', 'read_delay', 'read_rise_time']
            laser_params = ['read_period', 'laser_width', 'laser_delay', 'laser_rise_time', 'laser_fall_time']
            if hasattr(self, 'time_unit_var'):
                selected_unit = self.time_unit_var.get()
            else:
                selected_unit = "µs" if is_4200a else "ms"
            unit_to_seconds = {"ns": 1e-9, "µs": 1e-6, "ms": 1e-3, "s": 1.0}
            conversion_factor = unit_to_seconds.get(selected_unit, 1e-3)
            
            params = {}
            for key, info in self.param_vars.items():
                try:
                    val = info["var"].get()
                    if info["type"] == "float":
                        value = float(val)
                        is_time_param = info.get("is_time_param", False)
                        if key in read_pulse_params and is_4200a:
                            if selected_unit == "ns":
                                params[key] = (value / 1000.0) * 1e-6
                            elif selected_unit == "µs":
                                params[key] = value * 1e-6
                            elif selected_unit == "ms":
                                params[key] = (value * 1000.0) * 1e-6
                            elif selected_unit == "s":
                                params[key] = (value * 1e6) * 1e-6
                            else:
                                params[key] = value * 1e-6
                        elif key in laser_params or is_time_param or key in time_params:
                            params[key] = value * conversion_factor
                        else:
                            params[key] = value
                    elif info["type"] == "int":
                        params[key] = int(val)
                    elif info["type"] == "list":
                        params[key] = [float(x.strip()) for x in val.split(",")]
                    else:
                        params[key] = val
                except Exception:
                    if info["type"] == "float":
                        params[key] = 1.0
                    elif info["type"] == "int":
                        params[key] = 1
                    else:
                        params[key] = ""
            
            self.pulse_diagram_helper.draw(test_name, params, self.current_system_name)
            self.diagram_canvas.draw()
        except Exception as e:
            self.diagram_ax.clear()
            self.diagram_ax.text(0.5, 0.5, f"Diagram error:\n{str(e)}", ha='center', va='center', fontsize=8)
            self.diagram_canvas.draw()
    
    def log(self, message):
        """Add message to status log"""
        if not getattr(self, "status_text", None):
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.update_idletasks()

    # ===== PRESET MANAGEMENT =====
    
    def load_presets_from_file(self):
        """Load presets from JSON file"""
        preset_file = config.TSP_TEST_PRESETS_FILE
        if preset_file.exists():
            try:
                import json
                with open(preset_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading presets: {e}")
                return {}
        return {}
    
    def save_presets_to_file(self):
        """Save presets to JSON file"""
        preset_file = config.TSP_TEST_PRESETS_FILE
        preset_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            import json
            with open(preset_file, 'w') as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            print(f"Error saving presets: {e}")
            messagebox.showerror("Save Error", f"Could not save presets: {e}")
    
    def update_preset_dropdown(self):
        """Update preset dropdown for current test type"""
        test_name = self.test_var.get()
        presets_for_test = self.presets.get(test_name, {})
        preset_names = list(presets_for_test.keys())
        
        self.preset_dropdown['values'] = preset_names
        if preset_names:
            self.preset_var.set("")  # Clear selection
        else:
            self.preset_var.set("")
    
    def save_preset(self):
        """Save current parameters as a preset"""
        test_name = self.test_var.get()
        
        # Ask for preset name
        preset_name = tk.simpledialog.askstring(
            "Save Preset",
            f"Enter preset name for '{test_name}':",
            parent=self
        )
        
        if not preset_name:
            return
        
        # Get current parameters - save raw display values (before conversion)
        # This ensures values load back correctly regardless of system/unit
        params = {}
        for param_name, param_info in self.param_vars.items():
            var = param_info["var"]
            param_type = param_info["type"]
            
            try:
                if param_type == "bool":
                    params[param_name] = var.get()
                elif param_type == "int":
                    params[param_name] = int(var.get())
                elif param_type == "float":
                    params[param_name] = float(var.get())
                elif param_type == "list":
                    params[param_name] = var.get()
                else:
                    params[param_name] = var.get()
            except Exception as e:
                messagebox.showerror("Error", f"Invalid parameter {param_name}: {e}")
                return
        
        # Store preset
        if test_name not in self.presets:
            self.presets[test_name] = {}
        
        self.presets[test_name][preset_name] = params
        
        # Save to file
        self.save_presets_to_file()
        
        # Update dropdown
        self.update_preset_dropdown()
        self.preset_var.set(preset_name)
        
        self.log(f"✓ Saved preset: '{preset_name}'")
        messagebox.showinfo("Saved", f"Preset '{preset_name}' saved successfully!")
    
    def load_preset(self):
        """Load selected preset"""
        test_name = self.test_var.get()
        preset_name = self.preset_var.get()
        
        if not preset_name:
            return
        
        # Get preset parameters
        presets_for_test = self.presets.get(test_name, {})
        params = presets_for_test.get(preset_name)
        
        if not params:
            messagebox.showwarning("Not Found", f"Preset '{preset_name}' not found")
            return
        
        # Load parameters into GUI - values are saved as raw display values
        # so we can set them directly without conversion
        for param_name, value in params.items():
            if param_name in self.param_vars:
                var = self.param_vars[param_name]["var"]
                param_type = self.param_vars[param_name]["type"]
                
                # Format value appropriately
                if param_type == "bool":
                    var.set(value)
                elif param_type == "int":
                    var.set(str(int(value)))
                elif param_type == "float":
                    var.set(str(value))
                elif param_type == "list":
                    if isinstance(value, str):
                        var.set(value)
                    else:
                        var.set(",".join(str(v) for v in value))
                else:
                    var.set(str(value))
        
        self.log(f"✓ Loaded preset: '{preset_name}'")
        self.update_pulse_diagram()
    
    def delete_preset(self):
        """Delete selected preset"""
        test_name = self.test_var.get()
        preset_name = self.preset_var.get()
        
        if not preset_name:
            messagebox.showwarning("No Selection", "Please select a preset to delete")
            return
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", 
                                   f"Delete preset '{preset_name}'?"):
            return
        
        # Delete preset
        if test_name in self.presets and preset_name in self.presets[test_name]:
            del self.presets[test_name][preset_name]
            
            # Remove test entry if no presets left
            if not self.presets[test_name]:
                del self.presets[test_name]
            
            # Save to file
            self.save_presets_to_file()
            
            # Update dropdown
            self.update_preset_dropdown()
            
            self.log(f"✓ Deleted preset: '{preset_name}'")
            messagebox.showinfo("Deleted", f"Preset '{preset_name}' deleted")
        else:
            messagebox.showerror("Error", "Preset not found")


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide root window
    app = TSPTestingGUI(root)
    root.mainloop()

