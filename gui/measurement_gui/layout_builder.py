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

# Standard library imports
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import webbrowser
import subprocess
import sys
import os
import json

# Third-party imports
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

# Get project root (go up from gui/measurement_gui/ to project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # gui/measurement_gui/layout_builder.py -> gui -> root

# Import shared layout constants
from .layout.constants import (
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_BG,
    COLOR_BG_INFO,
    COLOR_SUCCESS,
    COLOR_ERROR,
    COLOR_WARNING,
    COLOR_INFO,
    FONT_MAIN,
    FONT_HEADING,
    FONT_LARGE,
    FONT_BUTTON,
)


@dataclass
class MeasurementGUILayoutBuilder:
    gui: object
    callbacks: Dict[str, Callable]
    widgets: Dict[str, tk.Widget] = field(default_factory=dict)
    _updating_system: bool = False  # Flag to prevent recursive updates
    
    # Layout constants (from layout.constants; exposed as class attrs for compatibility)
    COLOR_PRIMARY = COLOR_PRIMARY
    COLOR_SECONDARY = COLOR_SECONDARY
    COLOR_BG = COLOR_BG
    COLOR_BG_INFO = COLOR_BG_INFO
    COLOR_SUCCESS = COLOR_SUCCESS
    COLOR_ERROR = COLOR_ERROR
    COLOR_WARNING = COLOR_WARNING
    COLOR_INFO = COLOR_INFO
    FONT_MAIN = FONT_MAIN
    FONT_HEADING = FONT_HEADING
    FONT_LARGE = FONT_LARGE
    FONT_BUTTON = FONT_BUTTON

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
        
        # Note: Context menus for plot canvases are set up in main.py after plots are created
    
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
        
        # Set default to "Please Select System" (should be first in list)
        if gui.systems and gui.systems[0] == "Please Select System":
            gui.system_var.set("Please Select System")
        elif gui.systems and gui.systems[0] != "No systems available":
            # Fallback if "Please Select System" not in list
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
        
        # Analysis Controls section (between connection status and device)
        analysis_section = tk.Frame(left_section, bg=self.COLOR_BG)
        analysis_section.pack(side='left', fill='y', padx=10)
        
        # Enable Analysis Toggle
        tk.Label(analysis_section, text="Analysis:", font=self.FONT_MAIN, bg=self.COLOR_BG).pack(side='left', padx=(0, 5))
        gui.analysis_enabled = tk.BooleanVar(value=False)  # Default: disabled
        analysis_checkbox = tk.Checkbutton(analysis_section, variable=gui.analysis_enabled, bg=self.COLOR_BG)
        analysis_checkbox.pack(side='left', padx=(0, 5))
        
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
        
        # Classification display (updated after each measurement)
        gui.classification_label = tk.Label(
            device_info_frame,
            text="",
            font=("Segoe UI", 9),
            bg='#e8f5e9',
            fg=self.COLOR_PRIMARY
        )
        gui.classification_label.pack(side='left', padx=(5, 0))
        
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
        
        # Device Visualizer button (opens Qt5 visualization app)
        visualizer_btn = tk.Button(
            right_section,
            text="Device Visualizer",
            font=self.FONT_BUTTON,
            command=lambda: self._open_device_visualizer(),
            bg=self.COLOR_BG,
            relief='raised',
            padx=10,
            pady=5
        )
        visualizer_btn.pack(side='left', padx=5)
        gui.device_visualizer_button = visualizer_btn
        
        # Oscilloscope Pulse button
        scope_btn = tk.Button(
            right_section,
            text="Oscilloscope Pulse",
            font=self.FONT_BUTTON,
            command=self.callbacks.get("open_oscilloscope_pulse"),
            bg=self.COLOR_BG,
            relief='raised',
            padx=10,
            pady=5
        )
        scope_btn.pack(side='left', padx=5)
        gui.oscilloscope_pulse_button = scope_btn
        
        # Help / Guide button (far right)
        help_btn = tk.Button(
            right_section,
            text="Help / Guide",
            font=self.FONT_BUTTON,
            command=lambda: self._show_help(gui),
            bg='#1565c0',  # Darker blue
            fg='white',
            activebackground='#0d47a1',
            activeforeground='white',
            relief='raised',
            cursor='hand2',
            padx=12,
            pady=6
        )
        help_btn.pack(side='left', padx=5)
        gui.help_button = help_btn
        
        self.widgets["top_control_bar"] = frame
    
    def _on_system_change_and_connect(self) -> None:
        """Handle system change and automatically connect to SMU"""
        gui = self.gui
        
        selected_system = gui.system_var.get()
        # Don't do anything if "Please Select System" is selected
        if not selected_system or selected_system == "Please Select System":
            return
        
        # StringVar trace will automatically sync Setup tab dropdown
        # First load the system configuration (comprehensive update)
        load_system_cb = self.callbacks.get("load_system")
        if load_system_cb:
            load_system_cb()
        
        # Also call the system change callback for address updates
        system_change_cb = self.callbacks.get("on_system_change")
        if system_change_cb:
            system_change_cb(selected_system)
        
        # Automatically connect to SMU after system is selected
        # Use a small delay to ensure system configuration is fully loaded
        gui.master.after(100, self._auto_connect_instruments)
    
    def _auto_connect_instruments(self) -> None:
        """Automatically connect to instruments after system selection"""
        gui = self.gui
        
        # Use MeasurementGUI helper if available (handles status updates/logging)
        auto_connect_func = getattr(gui, "auto_connect_current_system", None)
        used_custom_method = False
        smu_connected = False
        if callable(auto_connect_func):
            used_custom_method = True
            smu_connected = auto_connect_func()
        else:
            # Update status to connecting if no helper
            if hasattr(gui, 'connection_status_label'):
                gui.connection_status_label.config(text="● Connecting...", fg=self.COLOR_WARNING)
                try:
                    gui.master.update()
                except Exception:
                    pass
            
            # Connect Keithley/SMU
            connect_keithley_cb = self.callbacks.get("connect_keithley")
            if connect_keithley_cb:
                try:
                    connect_keithley_cb()
                    smu_connected = getattr(gui, 'connected', False)
                except RuntimeError as e:
                    error_str = str(e)
                    if "IVControllerManager dependency not available" in error_str:
                        print(f"⚠️  WARNING: Auto-connect Keithley failed - IVControllerManager dependency not available")
                        print(f"   {error_str}")
                    else:
                        print(f"⚠️  WARNING: Auto-connect Keithley failed: {e}")
                except Exception as e:
                    print(f"⚠️  WARNING: Auto-connect Keithley failed: {e}")
        
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
        
        # Update status label if helper didn't already handle it
        if not used_custom_method and hasattr(gui, 'connection_status_label'):
            if smu_connected:
                gui.connection_status_label.config(text="● Connected", fg=self.COLOR_SUCCESS)
            else:
                gui.connection_status_label.config(text="● Connection Failed", fg=self.COLOR_ERROR)
    
    def _open_pulse_testing(self) -> None:
        """Open the TSP/Pulse Testing GUI"""
        open_cb = getattr(self.gui, "open_pulse_testing_gui", None)
        if callable(open_cb):
            open_cb()
            return
        try:
            from gui.pulse_testing_gui import TSPTestingGUI
            TSPTestingGUI(self.gui.master)
        except Exception as e:
            print(f"Failed to open Pulse Testing GUI: {e}")
            messagebox.showerror("Error", f"Could not open Pulse Testing GUI:\n{e}")
    
    def _open_device_visualizer(self) -> None:
        """Open the Device Analysis Visualizer Qt5 application"""
        open_cb = getattr(self.gui, "open_device_visualizer", None)
        if callable(open_cb):
            open_cb()
            return
        # Fallback if method doesn't exist
        try:
            from tools.device_visualizer.device_visualizer_app import launch_visualizer
            launch_visualizer()
        except Exception as e:
            print(f"Failed to open Device Visualizer: {e}")
            messagebox.showerror("Error", f"Could not open Device Visualizer:\n{e}")
    
    def _show_help(self, gui: object) -> None:
        """Display a help window with usage instructions."""
        help_win = tk.Toplevel(gui.master)
        help_win.title("Measurement GUI Guide")
        help_win.geometry("800x700")
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
        
        tk.Label(scrollable_frame, text="Measurement GUI Guide", 
                font=("Segoe UI", 16, "bold"), bg="#f0f0f0", fg="#1565c0").pack(**pad)
        
        tk.Label(scrollable_frame, text="1. Overview", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame, 
                text="This is the main measurement interface for IV/PMU/SMU measurements on device arrays.\n"
                      "It provides comprehensive control over instrument connections, measurement\n"
                      "configuration, real-time plotting, and data saving.",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="2. Getting Started", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Select your measurement system from the dropdown in the top bar\n"
                      "• Configure instrument connections in the Setup tab\n"
                      "• Set measurement parameters in the Measurements tab\n"
                      "• Click 'Start Measurement' to begin\n"
                      "• Monitor progress in real-time plots",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="3. Key Features", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• IV Sweeps: Standard voltage sweeps with current measurement\n"
                      "• Custom Measurements: Load pre-configured sweeps from JSON\n"
                      "• Sequential Measurements: Test multiple devices automatically\n"
                      "• Conditional Testing: Smart workflow that screens devices and runs tests only on memristive devices\n"
                      "• Pulse Testing: Fast pulse characterization (opens separate GUI)\n"
                      "• Real-time Plotting: Live voltage, current, and resistance plots\n"
                      "• Data Saving: Automatic file naming and organization",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="4. Utility Buttons", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Motor Control: Control XY stage for laser positioning\n"
                      "• Check Connection: Verify electrical connections before testing\n"
                      "• Pulse Testing: Open advanced pulse testing interface",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="5. Conditional Memristive Testing", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0", fg="#e65100").pack(**pad)
        tk.Label(scrollable_frame,
                text="Smart workflow that automatically screens devices and runs tests only on memristive devices.\n\n"
                      "Workflow:\n"
                      "1. Quick Test: Runs fast screening test (e.g., 0-2.8V sweep) on all devices\n"
                      "2. Analysis: Each device analyzed for memristivity score (0-100)\n"
                      "3. Conditional Tests:\n"
                      "   • Score ≥ 60: Run basic memristive test\n"
                      "   • Score ≥ 80: Run high-quality test\n"
                      "   • Re-evaluation: Re-check after basic test, upgrade if score improves\n"
                      "4. Final Test (optional): After all devices complete, select best devices and run final test\n\n"
                      "Configuration:\n"
                      "• Access from Advanced Tests tab or Measurements tab\n"
                      "• Set thresholds (default: 60 for basic, 80 for high-quality)\n"
                      "• Select custom sweeps for quick test, basic test, and high-quality test\n"
                      "• Configure final test with selection mode:\n"
                      "  - 'top_x': Select top X devices above minimum score\n"
                      "  - 'all_above_score': Select all devices above minimum score\n"
                      "• Toggle re-evaluation and memcapacitive inclusion\n"
                      "• Save configuration for reuse\n\n"
                      "Safety: Final test shows confirmation dialog before running (important for potentially\n"
                      "damaging tests like laser).",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="6. Additional Resources", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• USER_GUIDE.md: Complete usage guide\n"
                      "• JSON_CONFIG_GUIDE.md: Detailed configuration reference\n"
                      "• QUICK_REFERENCE.md: One-page cheat sheet\n\n"
                      "All documentation files are in the Documents/ folder.",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="7. Video Tutorials", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0", fg="#d32f2f").pack(**pad)
        
        # Video tutorial section
        video_frame = ttk.Frame(scrollable_frame)
        video_frame.pack(**pad, fill='x')
        
        # Helper function to open videos
        def open_video(video_path_or_url: str) -> None:
            """Open video file or URL in default application/browser."""
            try:
                if video_path_or_url.startswith(('http://', 'https://')):
                    # Open URL in default browser
                    webbrowser.open(video_path_or_url)
                else:
                    # Open local file with default application
                    video_path = Path(video_path_or_url)
                    if not video_path.is_absolute():
                        # If relative path, assume it's in a Videos folder in project root
                        video_path = _PROJECT_ROOT / "Videos" / video_path_or_url
                    
                    if video_path.exists():
                        if sys.platform == "win32":
                            os.startfile(str(video_path))
                        elif sys.platform == "darwin":  # macOS
                            subprocess.run(["open", str(video_path)])
                        else:  # Linux
                            subprocess.run(["xdg-open", str(video_path)])
                    else:
                        messagebox.showerror("Video Not Found", 
                                            f"Video file not found:\n{video_path}\n\n"
                                            f"Please ensure the video file is in the 'Videos' folder.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open video:\n{str(e)}")
        
        # Load video configuration from JSON file
        video_config_path = _PROJECT_ROOT / "Json_Files" / "help_videos.json"
        video_config = []
        
        try:
            if video_config_path.exists():
                with open(video_config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    video_config = config_data.get("videos", [])
        except Exception as e:
            # If JSON loading fails, show error but continue
            print(f"Warning: Could not load video config: {e}")
        
        if video_config:
            for video_item in video_config:
                video_title = video_item.get("title", "Untitled Video")
                video_path = video_item.get("path", "")
                video_desc = video_item.get("description", "")
                
                if not video_path:
                    continue
                
                # Create button frame for each video
                btn_frame = ttk.Frame(video_frame)
                btn_frame.pack(side='top', fill='x', pady=5)
                
                # Video button
                btn = tk.Button(
                    btn_frame,
                    text=f"▶ {video_title}",
                    font=("Segoe UI", 10, "bold"),
                    bg="#4CAF50",
                    fg="white",
                    activebackground="#45a049",
                    activeforeground="white",
                    relief='raised',
                    cursor='hand2',
                    padx=15,
                    pady=8,
                    command=lambda v=video_path: open_video(v)
                )
                btn.pack(side='left', padx=(0, 10))
                
                # Description label
                if video_desc:
                    desc_label = tk.Label(
                        btn_frame,
                        text=video_desc,
                        font=("Segoe UI", 9),
                        bg="#f0f0f0",
                        fg="#666",
                        justify='left'
                    )
                    desc_label.pack(side='left', fill='x', expand=True)
        else:
            tk.Label(video_frame,
                    text="No video tutorials configured.\n"
                         "To add videos, edit Json_Files/help_videos.json\n"
                         "See the file for examples and instructions.",
                    justify="left", bg="#f0f0f0", fg="#666").pack(**pad)
        
        tk.Label(scrollable_frame,
                text="\nNote: Videos can be local files (place in Videos/ folder) or online URLs (YouTube, Vimeo, etc.).\n"
                     "Edit Json_Files/help_videos.json to add or modify video tutorials.",
                justify="left", bg="#f0f0f0", fg="#666", font=("Segoe UI", 9)).pack(**pad)
    
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
        from .layout.tab_measurements import build_measurements_tab
        from .layout.tab_advanced_tests import build_advanced_tests_tab
        from .layout.tab_setup import build_setup_tab
        from .layout.tab_custom_measurements import build_custom_measurements_tab
        from .layout.tab_notes import build_notes_tab
        build_measurements_tab(self, notebook)
        build_advanced_tests_tab(self, notebook)
        build_setup_tab(self, notebook)
        build_custom_measurements_tab(self, notebook)
        build_notes_tab(self, notebook)
        from .layout.tab_stats import build_stats_tab
        build_stats_tab(self, notebook)  # NEW: Device tracking stats
        from .layout.tab_graphing import build_graphing_tab
        build_graphing_tab(self, notebook)  # NEW: Sample analysis and plotting
        from .layout.tab_custom_sweeps import build_custom_sweeps_graphing_tab
        build_custom_sweeps_graphing_tab(self, notebook)  # NEW: Custom sweeps graphing
        
        self.widgets["notebook"] = notebook
    
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
        from .layout.sections import build_mode_selection
        build_mode_selection(self, parent)

    def _build_sweep_parameters_collapsible(self, parent: tk.Misc) -> None:
        from .layout.sections import build_sweep_parameters
        build_sweep_parameters(self, parent)

    def _build_pulse_parameters_collapsible(self, parent: tk.Misc) -> None:
        from .layout.sections import build_pulse_parameters
        build_pulse_parameters(self, parent)

    def _build_sequential_controls_collapsible(self, parent: tk.Misc) -> None:
        from .layout.sections import build_sequential_controls
        build_sequential_controls(self, parent)

    def _build_custom_measurement_quick_select(self, parent: tk.Misc) -> None:
        from .layout.sections import build_custom_measurement_quick
        build_custom_measurement_quick(self, parent)

    def _build_conditional_testing_quick_select(self, parent: tk.Misc) -> None:
        from .layout.sections import build_conditional_testing_quick
        build_conditional_testing_quick(self, parent)

    def _build_telegram_bot_collapsible(self, parent: tk.Misc) -> None:
        from .layout.sections import build_telegram_bot
        build_telegram_bot(self, parent)

    def _build_connection_section_modern(self, parent: tk.Misc) -> None:
        from .layout.sections import build_connection_section_modern
        build_connection_section_modern(self, parent)

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
        from .layout.sections.optical import build_optical_section
        build_optical_section(parent, gui)

    def _toggle_optical_section(self, gui: object, frame: tk.Frame, button: tk.Button) -> None:
        from .layout.sections.optical import toggle_optical_section
        toggle_optical_section(gui, frame, button)

    def _update_optical_ui(self, gui: object, parent: tk.Frame) -> None:
        from .layout.sections.optical import update_optical_ui
        update_optical_ui(gui, parent)

    def _get_previous_devices(self, gui) -> List[Dict[str, Any]]:
        from .layout import notes_helpers
        return notes_helpers.get_previous_devices(gui)

    def _load_previous_device_notes(self, gui, device_info: Dict[str, Any], text_widget: tk.Text) -> None:
        from .layout import notes_helpers
        notes_helpers.load_previous_device_notes(self, gui, device_info, text_widget)

    def _save_previous_device_notes(self, gui, device_info: Dict[str, Any], text_widget: tk.Text) -> None:
        from .layout import notes_helpers
        notes_helpers.save_previous_device_notes(self, gui, device_info, text_widget)

    def _mark_notes_changed(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.mark_notes_changed(gui)

    def _on_notes_key_release(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.on_notes_key_release(self, gui)

    def _mark_prev_device1_changed(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.mark_prev_device1_changed(gui)

    def _setup_notes_keyboard_shortcuts(self, gui, tab: tk.Frame) -> None:
        from .layout import notes_helpers
        notes_helpers.setup_notes_keyboard_shortcuts(self, gui, tab)

    def _insert_datetime(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.insert_datetime(gui)

    def _insert_measurement_details(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.insert_measurement_details(self, gui)

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
        from .layout import notes_helpers
        notes_helpers.toggle_bold(gui)

    def _toggle_italic(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.toggle_italic(gui)

    def _start_device_change_polling(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.start_device_change_polling(self, gui)

    def _start_sample_change_polling(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.start_sample_change_polling(self, gui)

    def _start_auto_save_timer(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.start_auto_save_timer(self, gui)

    def _load_notes(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.load_notes(self, gui)

    def _save_notes(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.save_notes(self, gui)

    def _get_sample_name(self, gui) -> Optional[str]:
        from .layout import notes_helpers
        return notes_helpers.get_sample_name(gui)

    def _get_notes_file_path(self, gui, sample_name: str) -> Path:
        from .layout import notes_helpers
        return notes_helpers.get_notes_file_path(gui, sample_name)

    def _load_notes_data(self, gui, sample_name: str) -> dict:
        from .layout import notes_helpers
        return notes_helpers.load_notes_data(gui, sample_name)

    def _save_notes_data(self, gui, sample_name: str, notes_data: dict) -> None:
        from .layout import notes_helpers
        notes_helpers.save_notes_data(gui, sample_name, notes_data)

    def _load_sample_notes(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.load_sample_notes(self, gui)

    def _save_sample_notes(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.save_sample_notes(self, gui)

    def _mark_sample_notes_changed(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.mark_sample_notes_changed(gui)

    def _save_all_notes(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.save_all_notes(self, gui)

    def _auto_save_notes(self, gui) -> None:
        from .layout import notes_helpers
        notes_helpers.auto_save_notes(self, gui)

    def _setup_plot_context_menus(self, gui) -> None:
        """Set up right-click context menus on all plot canvases for quick notes"""
        if not hasattr(gui, 'plot_panels'):
            return
        
        # Set up context menu on all canvases
        for canvas_key, canvas in gui.plot_panels.canvases.items():
            if canvas:
                self._add_context_menu_to_canvas(gui, canvas)
    
    def _add_context_menu_to_canvas(self, gui, canvas: Any) -> None:
        """Add right-click context menu to a matplotlib canvas"""
        def show_context_menu(event):
            """Show context menu on right-click"""
            menu = tk.Menu(gui.master, tearoff=0)
            menu.add_command(
                label="Quick Notes - Device",
                command=lambda: self._open_quick_notes_dialog(gui, "device")
            )
            menu.add_command(
                label="Quick Notes - Sample",
                command=lambda: self._open_quick_notes_dialog(gui, "sample")
            )
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        
        # Get the Tkinter widget from the matplotlib canvas
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.bind("<Button-3>", show_context_menu)  # Button-3 is right-click on Windows/Linux
        canvas_widget.bind("<Button-2>", show_context_menu)  # Button-2 is right-click on Mac (middle button, but some use it)
    
    def _open_quick_notes_dialog(self, gui, notes_type: str) -> None:
        """Open a quick notes dialog for device or sample notes"""
        from datetime import datetime
        
        # Get measurement info
        measurement_number = getattr(gui, 'measurment_number', None) or getattr(gui, 'sweep_num', None) or "N/A"
        measurement_type = "Unknown"
        
        # Try to get measurement type from various sources
        if hasattr(gui, 'excitation_var'):
            try:
                measurement_type = gui.excitation_var.get() or "Unknown"
            except:
                pass
        
        if measurement_type == "Unknown" and hasattr(gui, 'Sequential_measurement_var'):
            try:
                measurement_type = gui.Sequential_measurement_var.get() or "Unknown"
            except:
                pass
        
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create dialog window
        dialog = tk.Toplevel(gui.master)
        dialog.title(f"Quick Notes - {'Device' if notes_type == 'device' else 'Sample'}")
        dialog.geometry("600x400")
        dialog.configure(bg=self.COLOR_BG)
        
        # Info frame at top
        info_frame = tk.Frame(dialog, bg=self.COLOR_BG, padx=10, pady=10)
        info_frame.pack(fill="x")
        
        info_text = f"Measurement #{measurement_number} | Type: {measurement_type} | Time: {timestamp}"
        tk.Label(
            info_frame,
            text=info_text,
            font=self.FONT_MAIN,
            bg=self.COLOR_BG,
            fg=self.COLOR_SECONDARY
        ).pack(anchor="w")
        
        # Notes text area
        text_frame = tk.Frame(dialog, bg=self.COLOR_BG)
        text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        notes_text = tk.Text(
            text_frame,
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
        notes_text.pack(fill="both", expand=True)
        
        # Pre-populate with header
        header = f"[Measurement #{measurement_number} | {measurement_type} | {timestamp}]\n"
        notes_text.insert("1.0", header)
        notes_text.mark_set(tk.INSERT, "end-1c")  # Move cursor to end
        
        # Buttons frame
        button_frame = tk.Frame(dialog, bg=self.COLOR_BG, padx=10, pady=10)
        button_frame.pack(fill="x")
        
        def save_notes():
            """Save notes to file (called on close or save button)"""
            notes_content = notes_text.get("1.0", tk.END).strip()
            
            # Only save if there's actual content (not just the header)
            header = f"[Measurement #{measurement_number} | {measurement_type} | {timestamp}]\n"
            if notes_content.strip() == header.strip():
                # Only header, no actual notes - skip saving
                return
            
            if notes_type == "device":
                from .layout import notes_helpers
                device_id = getattr(gui, 'device_section_and_number', None)
                sample_name = notes_helpers.get_sample_name(gui)
                if device_id and sample_name:
                    notes_data = notes_helpers.load_notes_data(gui, sample_name)
                    if "device" not in notes_data:
                        notes_data["device"] = {}
                    
                    # Append new notes to existing device notes
                    existing_notes = notes_data["device"].get(device_id, "")
                    if existing_notes:
                        notes_data["device"][device_id] = existing_notes + "\n\n" + notes_content
                    else:
                        notes_data["device"][device_id] = notes_content
                    
                    notes_helpers.save_notes_data(gui, sample_name, notes_data)
                    # Update the main notes text widget if it exists
                    if hasattr(gui, 'notes_text'):
                        current_content = gui.notes_text.get("1.0", tk.END).strip()
                        if current_content:
                            gui.notes_text.insert(tk.END, "\n\n" + notes_content)
                        else:
                            gui.notes_text.insert("1.0", notes_content)
                        gui.notes_last_saved = gui.notes_text.get("1.0", tk.END)
            else:
                from .layout import notes_helpers
                sample_name = notes_helpers.get_sample_name(gui)
                if sample_name:
                    notes_data = notes_helpers.load_notes_data(gui, sample_name)
                    existing_notes = notes_data.get("Sample_Notes", "")
                    
                    if existing_notes:
                        notes_data["Sample_Notes"] = existing_notes + "\n\n" + notes_content
                    else:
                        notes_data["Sample_Notes"] = notes_content
                    
                    notes_helpers.save_notes_data(gui, sample_name, notes_data)
                    # Update the sample notes text widget if it exists
                    if hasattr(gui, 'sample_notes_text'):
                        current_content = gui.sample_notes_text.get("1.0", tk.END).strip()
                        if current_content:
                            gui.sample_notes_text.insert(tk.END, "\n\n" + notes_content)
                        else:
                            gui.sample_notes_text.insert("1.0", notes_content)
                        gui.sample_notes_last_saved = gui.sample_notes_text.get("1.0", tk.END)
        
        def on_close():
            """Save notes and close dialog - auto-save on close"""
            save_notes()
            dialog.destroy()
        
        def save_and_close():
            """Save notes and close dialog (explicit save button)"""
            save_notes()
            dialog.destroy()
        
        # Close button (auto-saves on close)
        close_btn = tk.Button(
            button_frame,
            text="Close",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg="white",
            command=on_close,
            padx=20,
            pady=5
        )
        close_btn.pack(side="right")
        
        # Bind window close protocol to auto-save
        dialog.protocol("WM_DELETE_WINDOW", on_close)
        
        # Focus on text widget
        notes_text.focus_set()
    
    # ------------------------------------------------------------------
    # Bottom Status Bar
    # ------------------------------------------------------------------
    def _build_bottom_status_bar(self, parent: tk.Misc) -> None:
        from .layout.sections.status_bar import build_bottom_status_bar
        build_bottom_status_bar(self, parent)

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------
    def _build_manual_endurance_retention(self, parent: tk.Misc) -> None:
        from .layout.sections.advanced_tests import build_manual_endurance_retention as _build
        _build(self, parent)

    def _build_conditional_testing_section(self, parent: tk.Misc) -> None:
        from .layout.sections.advanced_tests import build_conditional_testing_section as _build
        _build(self, parent)

    def _update_conditional_testing_controls(self, gui) -> None:
        from .layout.conditional_config_helpers import update_conditional_testing_controls
        update_conditional_testing_controls(self, gui)

    def _update_final_test_controls(self, gui) -> None:
        from .layout.conditional_config_helpers import update_final_test_controls
        update_final_test_controls(self, gui)

    def _load_conditional_config(self, gui) -> None:
        from .layout.conditional_config_helpers import load_conditional_config
        load_conditional_config(self, gui)

    def _save_conditional_config(self, gui) -> None:
        from .layout.conditional_config_helpers import save_conditional_config
        save_conditional_config(self, gui)

    def _build_custom_measurement_section(self, parent: tk.Misc) -> None:
        from .layout.sections import build_custom_measurement_section
        build_custom_measurement_section(self, parent)


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
    builder.build_modern_layout(root)

    assert "notebook" in builder.widgets
    assert "top_control_bar" in builder.widgets

    root.destroy()


if __name__ == "__main__":  # pragma: no cover - developer smoke test
    _self_test()

