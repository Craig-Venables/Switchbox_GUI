"""
Sample GUI - Device Selection and Sample Management
===================================================

Purpose:
--------
Main entry point for device selection and sample management. Provides a visual
interface to browse device maps, select devices to test, control multiplexer
routing, and launch measurement interfaces.

Key Features:
-------------
- Visual device map/image viewer with click-to-select devices
- Device status tracking (working, failed, untested)
- Multiplexer routing control (PySwitchbox, Electronic Mpx)
- Quick scan functionality for rapid device testing
- Sample configuration and device mapping
- Data persistence (device status, sample info)

Entry Points:
-------------
- Primary: Launched from main.py
  ```python
  root = tk.Tk()
  app = SampleGUI(root)
  root.mainloop()
  ```

Launches:
---------
- MeasurementGUI: When user selects devices and clicks "Start Measurement"
  - Passes: sample_type, section, device_list, sample_gui reference

Dependencies:
-------------
- Measurement_GUI: For launching measurement interface
- Equipment.multiplexer_manager: Multiplexer control
- Equipment.Multiplexers: Multiplexer implementations
- Json_Files/pin_mapping.json: Device pin mappings
- Json_Files/mapping.json: Device layout mappings

Relationships:
-------------
Sample_GUI (this file)
    └─> MeasurementGUI
            └─> TSP_Testing_GUI, Check_Connection_GUI, etc.

Usage Flow:
-----------
1. User starts application (main.py)
2. Sample_GUI displays device map
3. User selects devices to test
4. User clicks "Start Measurement"
5. Sample_GUI launches MeasurementGUI with selected devices
6. User can return to Sample_GUI to select different devices

File Structure:
---------------
- ~3200 lines
- Main class: SampleGUI
- Key methods: device selection, multiplexer control, quick scan
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw
import json
import math
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
import time
import random
import os
import csv

from gui.measurement_gui import MeasurementGUI
from Equipment.Multiplexers.Multiplexer_10_OUT.Multiplexer_Class import MultiplexerController

# Import new multiplexer manager
from Equipment.managers.multiplexer import MultiplexerManager

try:
    from Equipment.SMU_AND_PMU import Keithley2400Controller
except Exception:
    Keithley2400Controller = None

if TYPE_CHECKING:
    # Placeholders for optional typing-only dependencies
    from typing import Protocol
    class Thresholds(Protocol):
        probe_voltage_v: float
        probe_duration_s: float
        probe_sample_hz: float
        working_current_a: float
        forming_voltages_v: List[float]
        forming_compliance_a: float
        forming_cooldown_s: float
        hyst_budget: float
        hyst_profiles: List[Any]
        endurance_cycles: int
        pulse_width_s: float
        retention_times_s: List[float]
        max_voltage_v: float
        max_compliance_a: float

# Get project root (go up from gui/sample_gui/ to project root)
_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]  # gui/sample_gui/main.py -> gui -> root
BASE_DIR: Path = _PROJECT_ROOT

# Load sample configuration from JSON file
sample_config = {
    "Cross_bar": {
        "sections": {"A": True, "B": True, "C": False, "D": True, "E": True, "F": False, "G": True, "H": True,
                     "I": True, "J": True, "K": True, "L": True},
        "devices": [str(i) for i in range(1, 11)]},
    "Device_Array_10": {
        "sections": {"A": True},
        "devices": [str(i) for i in range(1, 11)]},
    "15x15mm": {
        "sections": {"A": True, "B": True, "C": True, "D": True},
        "devices": [str(i) for i in range(1, 10)]}}

multiplexer_types = {'Pyswitchbox': {}, 'Electronic_Mpx': {}, 'Manual': {}}


# Function to load device mapping from JSON file
def load_device_mapping(filename: Optional[str] = None) -> Dict[str, Any]:
    try:
        mapping_path = (BASE_DIR / "Json_Files" / "pin_mapping.json") if filename is None else Path(filename)
        with mapping_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {mapping_path}.")
        return {}
    except json.JSONDecodeError:
        print("Error: JSON file is not formatted correctly.")
        return {}


pin_mapping: Dict[str, Any] = load_device_mapping()

# Load device mapping
with (BASE_DIR / "Json_Files" / "mapping.json").open("r", encoding="utf-8") as f:
    device_maps: Dict[str, Any] = json.load(f)


def resolve_default_save_root() -> Path:
    """
    Determine the default base directory for measurement data.
    
    Preference order:
    1. OneDrive commercial root (environment-provided) → Documents → Data_folder
    2. Explicit %USERPROFILE%/OneDrive - The University of Nottingham/Documents/Data_folder
    3. Local %USERPROFILE%/Documents/Data_folder
    
    The folder is created on demand.
    """
    home = Path.home()
    candidates: List[Path] = []
    
    for env_key in ("OneDriveCommercial", "OneDrive"):
        env_path = os.environ.get(env_key)
        if env_path:
            root = Path(env_path)
            candidates.append(root / "Documents")
    
    candidates.append(home / "OneDrive - The University of Nottingham" / "Documents")
    candidates.append(home / "Documents")
    
    for documents_path in candidates:
        try:
            root_exists = documents_path.parent.exists()
            if not root_exists:
                continue
            documents_path.mkdir(parents=True, exist_ok=True)
            target = documents_path / "Data_folder"
            target.mkdir(parents=True, exist_ok=True)
            return target
        except Exception:
            continue
    
    # Fallback to local Documents if all else fails
    fallback = home / "Documents" / "Data_folder"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


class SampleGUI:
    """Device selection and routing GUI with enhanced status tracking."""
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.root.title("Device Selection & Quick Scan")
        self.root.geometry("1100x850")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)  # Top bar
        self.root.rowconfigure(1, weight=1)  # Notebook
        self.root.rowconfigure(2, weight=0)  # Status bar

        # Defaults
        self.multiplexer_type: str = "Pyswitchbox"
        self.current_device_map: str = "Cross_bar"
        self.pyswitchbox: bool = True
        self.Electronic_Mpx: bool = False

        # Device label mappings
        self.device_labels: List[str] = []
        self.device_labels_by_key: Dict[str, str] = {}
        self.device_keys_by_label: Dict[str, str] = {}
        self.device_section_number_by_key: Dict[str, Tuple[str, Optional[int]]] = {}

        self.update_device_type(self.current_device_map)
        self.current_index: int = 0  # Index of currently selected device

        # Selected devices tracking
        self.selected_devices: Set[str] = set()  # Store selected device names
        self.selected_indices: List[int] = []  # Store indices of selected devices
        self.current_selected_index: int = 0  # Index within selected devices

        # Device status tracking (new)
        self.device_status: Dict[str, Dict[str, Any]] = {}  # Device status database
        self.status_icons = {"working": "✓", "broken": "✗", "undefined": "?"}
        
        # Current device name (e.g., "D104")
        self.current_device_name: Optional[str] = None
        self.device_info: Dict[str, Any] = {}  # Device metadata
        
        # Flags
        self.measurement_window: bool = False

        # Child GUI registry for propagating changes
        self._child_guis: List[Any] = []  # List of registered child GUI instances

        # Initialize multiplexer manager (will be set properly in update_multiplexer)
        self.mpx_manager = None
        
        # Quick scan configuration defaults
        self.quick_scan_min_current = 1e-10
        self.quick_scan_max_current = 1e-6
        self.quick_scan_threshold = 1e-7  # Threshold for auto classification
        self.quick_scan_running = False
        self.quick_scan_abort = threading.Event()
        self.quick_scan_thread: Optional[threading.Thread] = None
        self.quick_scan_metadata: Dict[str, Any] = {}
        self.quick_scan_results: Dict[str, float] = {}
        
        # Overlay toggles
        self.show_quick_scan_overlay = tk.BooleanVar(value=True)
        self.show_status_overlay = tk.BooleanVar(value=False)
        
        # Terminal filter
        self.terminal_filter = tk.StringVar(value="All")
        
        # Telegram variables
        self.telegram_enabled = tk.BooleanVar(value=False)
        self.telegram_bot_name_var = tk.StringVar(value="")
        self.telegram_bot: Optional[Any] = None
        self.telegram_bots: Dict[str, Dict[str, str]] = {}  # {name: {token, chatid}}
        self._load_telegram_bots()

        # =========================
        # TOP CONTROL BAR
        # =========================
        self._create_top_control_bar()

        # =========================
        # NOTEBOOK TABS
        # =========================
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Device Selection Tab
        self.device_selection_frame = ttk.Frame(self.notebook)
        self.device_selection_frame.grid_columnconfigure(0, weight=3)  # Canvas area
        self.device_selection_frame.grid_columnconfigure(1, weight=1)  # Device selection
        self.device_selection_frame.grid_rowconfigure(0, weight=1)  # Main area
        self.device_selection_frame.grid_rowconfigure(1, weight=0)  # Terminal

        # Quick Scan Results Tab
        self.quick_scan_frame = ttk.Frame(self.notebook)
        self.quick_scan_frame.grid_columnconfigure(0, weight=1)
        self.quick_scan_frame.grid_rowconfigure(0, weight=0)  # Control frame - fixed height
        self.quick_scan_frame.grid_rowconfigure(1, weight=0)  # Overlay frame - fixed height
        self.quick_scan_frame.grid_rowconfigure(2, weight=1)  # Canvas frame - expands
        self.quick_scan_frame.grid_rowconfigure(3, weight=0)  # Log frame - fixed height

        # Device Manager Tab
        self.device_manager_tab = ttk.Frame(self.notebook)
        self.device_manager_tab.grid_columnconfigure(0, weight=1)
        self.device_manager_tab.grid_rowconfigure(0, weight=1)

        # Add tabs in desired order: Device Selection (main), Device Manager, Quick Scan Results
        self.notebook.add(self.device_selection_frame, text="Device Selection")
        self.notebook.add(self.device_manager_tab, text="Device Manager")
        self.notebook.add(self.quick_scan_frame, text="Quick Scan Results")

        # =========================
        # BUILD UI SECTIONS
        # =========================
        self._create_device_manager_ui()
        self._create_canvas_section()
        self._create_device_selection_panel()
        self._create_terminal_log()
        self._init_quick_scan_ui()

        # =========================
        # BOTTOM STATUS BAR
        # =========================
        self._create_status_bar()

        # =========================
        # INITIALIZATION
        # =========================
        # Initialize original_image to None to prevent AttributeError
        self.original_image = None
        self.tk_img = None
        
        # Set default values WITHOUT triggering callbacks yet
        self.Multiplexer_type_var.set("Pyswitchbox")
        self.sample_type_var.set("Cross_bar")
        
        # Now manually trigger initialization in the correct order
        try:
            self.update_multiplexer(None)
        except Exception as e:
            print(f"Warning during multiplexer init: {e}")
        
        try:
            self.update_dropdowns(None)
        except Exception as e:
            print(f"Warning during dropdown init: {e}")

    def _create_top_control_bar(self) -> None:
        """Create the top control bar with dropdowns and measure button."""
        control_bar = ttk.Frame(self.root, relief=tk.RAISED, borderwidth=1)
        control_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Multiplexer Type
        ttk.Label(control_bar, text="Multiplexer:").pack(side="left", padx=(5, 2))
        self.Multiplexer_type_var = tk.StringVar()
        self.Multiplexer_dropdown = ttk.Combobox(
            control_bar,
            textvariable=self.Multiplexer_type_var,
            values=list(multiplexer_types.keys()),
            width=15,
            state="readonly"
        )
        self.Multiplexer_dropdown.pack(side="left", padx=(0, 10))
        self.Multiplexer_dropdown.bind("<<ComboboxSelected>>", self.update_multiplexer)
        
        # Sample Type
        ttk.Label(control_bar, text="Type:").pack(side="left", padx=(5, 2))
        self.sample_type_var = tk.StringVar()
        self.sample_dropdown = ttk.Combobox(
            control_bar,
            textvariable=self.sample_type_var,
            values=list(sample_config.keys()),
            width=15,
            state="readonly"
        )
        self.sample_dropdown.pack(side="left", padx=(0, 10))
        self.sample_dropdown.bind("<<ComboboxSelected>>", self.update_dropdowns)
        
        # Current Device Name Display
        ttk.Label(control_bar, text="Device:").pack(side="left", padx=(5, 2))
        self.device_name_label = tk.Label(
            control_bar,
            text="No Device",
            font=("Segoe UI", 9, "bold"),
            fg="#888888",
            relief=tk.SUNKEN,
            padx=10
        )
        self.device_name_label.pack(side="left", padx=(0, 10))
        
        # Section
        ttk.Label(control_bar, text="Section:").pack(side="left", padx=(5, 2))
        self.section_var = tk.StringVar()
        self.section_dropdown = ttk.Combobox(
            control_bar,
            textvariable=self.section_var,
            width=10,
            state="readonly"
        )
        self.section_dropdown.pack(side="left", padx=(0, 10))
        self.section_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)
        
        # Device Number
        ttk.Label(control_bar, text="Device:").pack(side="left", padx=(5, 2))
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(
            control_bar,
            textvariable=self.device_var,
            width=10,
            state="readonly"
        )
        self.device_dropdown.pack(side="left", padx=(0, 20))
        self.device_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)
        
        # Spacer
        ttk.Frame(control_bar).pack(side="left", expand=True)
        
        # Help button
        help_btn = tk.Button(
            control_bar,
            text="Help / Guide",
            command=self._show_help,
            bg="#1565c0",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=5,
            relief=tk.RAISED,
            cursor="hand2"
        )
        help_btn.pack(side="right", padx=5)
        
        # Measure Button (accent color)
        self.measure_button = tk.Button(
            control_bar,
            text="Measure Selected Devices",
            command=self.open_measurement_window,
            bg="#4CAF50",  # Green accent
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=5,
            relief=tk.RAISED,
            borderwidth=2,
            cursor="hand2"
        )
        self.measure_button.pack(side="right", padx=10)

    def _create_device_manager_ui(self) -> None:
        """Create the Device Manager tab UI."""
        # Main container
        main_frame = ttk.Frame(self.device_manager_tab, padding=20)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=2)
        main_frame.grid_rowconfigure(1, weight=1)
        
        # ===== LEFT COLUMN: Current Device =====
        left_frame = ttk.LabelFrame(main_frame, text="Current Device", padding=15)
        left_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        
        # Device name input
        ttk.Label(left_frame, text="Device Name:").grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        name_frame = ttk.Frame(left_frame)
        name_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        self.device_name_entry = ttk.Entry(name_frame, font=("Segoe UI", 12), width=20)
        self.device_name_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttk.Button(
            name_frame,
            text="Set Device",
            command=self.set_current_device,
            width=12
        ).pack(side="left")
        
        # Device info display
        info_frame = ttk.LabelFrame(left_frame, text="Device Information", padding=10)
        info_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        left_frame.grid_rowconfigure(2, weight=1)
        
        self.device_info_text = tk.Text(
            info_frame,
            height=15,
            width=35,
            font=("Consolas", 9),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.device_info_text.pack(fill="both", expand=True)
        
        # Action buttons
        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Save Device Info",
            command=self.save_device_info,
            width=15
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="Clear Device",
            command=self.clear_current_device,
            width=15
        ).pack(side="left", padx=5)
        
        # ===== RIGHT COLUMN: Device List =====
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Filter frame
        filter_frame = ttk.LabelFrame(right_frame, text="Quick Select Devices", padding=10)
        filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ttk.Label(filter_frame, text="Filter by Sample Type:").pack(side="left", padx=5)
        
        self.device_filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.device_filter_var,
            values=["All"] + list(sample_config.keys()),
            width=15,
            state="readonly"
        )
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_device_list())
        
        ttk.Button(
            filter_frame,
            text="Refresh",
            command=self.refresh_device_list,
            width=10
        ).pack(side="left", padx=5)
        
        # Device list
        list_frame = ttk.LabelFrame(right_frame, text="Saved Devices", padding=10)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Create Treeview for device list
        columns = ("name", "sample_type", "last_modified", "status")
        self.device_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="tree headings",
            selectmode="browse"
        )
        
        self.device_tree.heading("#0", text="")
        self.device_tree.heading("name", text="Device Name")
        self.device_tree.heading("sample_type", text="Sample Type")
        self.device_tree.heading("last_modified", text="Last Modified")
        self.device_tree.heading("status", text="Status")
        
        self.device_tree.column("#0", width=0, stretch=False)
        self.device_tree.column("name", width=150)
        self.device_tree.column("sample_type", width=120)
        self.device_tree.column("last_modified", width=150)
        self.device_tree.column("status", width=100)
        
        self.device_tree.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbar for list
        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.device_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.device_tree.configure(yscrollcommand=tree_scroll.set)
        
        # Bind double-click to load device
        self.device_tree.bind("<Double-Button-1>", lambda e: self.load_selected_device())
        
        # Load button
        ttk.Button(
            right_frame,
            text="Load Selected Device",
            command=self.load_selected_device,
            width=20
        ).grid(row=2, column=0, pady=(10, 0))
        
        # Initial refresh
        self.refresh_device_list()
        
        # Initialize device info display
        self.update_device_info_display()

    def _create_canvas_section(self) -> None:
        """Create the canvas section with navigation controls."""
        canvas_container = ttk.Frame(self.device_selection_frame)
        canvas_container.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_rowconfigure(1, weight=0)
        canvas_container.grid_columnconfigure(0, weight=1)
        
        # Canvas for device image
        canvas_frame = ttk.LabelFrame(canvas_container, text="Device Map", padding=5)
        canvas_frame.grid(row=0, column=0, sticky="nsew")
        
        self.canvas = tk.Canvas(
            canvas_frame,
            width=600,
            height=500,
            bg="white",
            highlightbackground="black",
            highlightthickness=1
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<Control-Button-1>", self.canvas_ctrl_click)
        self.canvas.bind("<Button-3>", self.canvas_right_click)  # Right-click for status menu
        
        # Navigation bar
        nav_bar = ttk.Frame(canvas_container)
        nav_bar.grid(row=1, column=0, sticky="ew", pady=5)
        
        # Previous button
        self.prev_button = ttk.Button(nav_bar, text="◄ Previous", command=self.prev_device, width=12)
        self.prev_button.pack(side="left", padx=5)
        
        # Info box
        self.info_box = tk.Label(
            nav_bar,
            text="Current Device: None",
            relief=tk.SUNKEN,
            font=("Segoe UI", 10),
            bg="#f0f0f0",
            padx=10,
            pady=5
        )
        self.info_box.pack(side="left", expand=True, fill="x", padx=5)
        
        # Next button
        self.next_button = ttk.Button(nav_bar, text="Next ►", command=self.next_device, width=12)
        self.next_button.pack(side="left", padx=5)
        
        # Route button
        self.change_button = ttk.Button(
            nav_bar,
            text="Route to Device",
            command=self.change_relays,
            width=15
        )
        self.change_button.pack(side="left", padx=5)
        
        # Clear button
        self.clear_button = ttk.Button(nav_bar, text="Clear", command=self.clear_canvas, width=10)
        self.clear_button.pack(side="left", padx=5)

    def _create_device_selection_panel(self) -> None:
        """Create the device selection panel with checkboxes and status indicators."""
        selection_container = ttk.LabelFrame(
            self.device_selection_frame,
            text="Device Selection",
            padding=5
        )
        selection_container.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        selection_container.grid_rowconfigure(1, weight=1)
        selection_container.grid_columnconfigure(0, weight=1)
        
        # Button frame
        button_frame = ttk.Frame(selection_container)
        button_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Select All",
            command=self.select_all_devices,
            width=10
        ).pack(side="left", padx=2)
        
        ttk.Button(
            button_frame,
            text="Clear",
            command=self.deselect_all_devices,
            width=10
        ).pack(side="left", padx=2)
        
        ttk.Button(
            button_frame,
            text="Invert",
            command=self.invert_selection,
            width=10
        ).pack(side="left", padx=2)
        
        # Status marking button
        button_frame2 = ttk.Frame(selection_container)
        button_frame2.grid(row=2, column=0, sticky="ew", pady=5)
        
        ttk.Label(button_frame2, text="Mark Selected:").pack(side="left", padx=5)
        
        ttk.Button(
            button_frame2,
            text="✓ Working",
            command=lambda: self.mark_selected_devices("working"),
            width=10
        ).pack(side="left", padx=2)
        
        ttk.Button(
            button_frame2,
            text="✗ Broken",
            command=lambda: self.mark_selected_devices("broken"),
            width=10
        ).pack(side="left", padx=2)
        
        ttk.Button(
            button_frame2,
            text="? Reset",
            command=lambda: self.mark_selected_devices("undefined"),
            width=10
        ).pack(side="left", padx=2)
        
        # Scrollable checkbox list
        scroll_frame = ttk.Frame(selection_container)
        scroll_frame.grid(row=1, column=0, sticky="nsew")
        
        canvas = tk.Canvas(scroll_frame, width=250, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.device_checkboxes: Dict[str, tk.Checkbutton] = {}
        self.checkbox_vars: Dict[str, tk.BooleanVar] = {}
        self.device_status_labels: Dict[str, tk.Label] = {}
        
        # Status label
        self.selection_status = tk.Label(
            selection_container,
            text="Selected: 0/0",
            font=("Segoe UI", 9, "bold"),
            fg="#4CAF50"
        )
        self.selection_status.grid(row=3, column=0, pady=5)

    def _create_terminal_log(self) -> None:
        """Create the terminal log section with color coding and filtering."""
        terminal_container = ttk.LabelFrame(
            self.device_selection_frame,
            text="Activity Log",
            padding=5
        )
        terminal_container.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        terminal_container.grid_rowconfigure(0, weight=1)
        terminal_container.grid_columnconfigure(0, weight=1)
        
        # Control frame
        control_frame = ttk.Frame(terminal_container)
        control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        ttk.Label(control_frame, text="Filter:").pack(side="left", padx=5)
        
        filter_combo = ttk.Combobox(
            control_frame,
            textvariable=self.terminal_filter,
            values=["All", "Info", "Success", "Warning", "Error"],
            width=10,
            state="readonly"
        )
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_terminal_filter())
        
        ttk.Button(
            control_frame,
            text="Clear Log",
            command=self.clear_terminal,
            width=10
        ).pack(side="left", padx=5)
        
        ttk.Button(
            control_frame,
            text="Export Log",
            command=self.export_terminal_log,
            width=10
        ).pack(side="left", padx=5)
        
        # Text widget with scrollbar
        text_frame = ttk.Frame(terminal_container)
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        self.terminal_output = tk.Text(
            text_frame,
            height=6,
            width=100,
            state=tk.DISABLED,
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.terminal_output.grid(row=0, column=0, sticky="nsew")
        
        terminal_scrollbar = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.terminal_output.yview
        )
        terminal_scrollbar.grid(row=0, column=1, sticky="ns")
        self.terminal_output.configure(yscrollcommand=terminal_scrollbar.set)
        
        # Configure color tags
        self.terminal_output.tag_config("INFO", foreground="#569CD6")
        self.terminal_output.tag_config("SUCCESS", foreground="#4CAF50")
        self.terminal_output.tag_config("WARNING", foreground="#FFA500")
        self.terminal_output.tag_config("ERROR", foreground="#F44336")
        self.terminal_output.tag_config("TIMESTAMP", foreground="#888888")
        
        self.terminal_messages: List[Tuple[str, str, str]] = []  # (timestamp, level, message)

    def _create_status_bar(self) -> None:
        """Create the bottom status bar."""
        status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        status_bar.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        # Multiplexer status
        self.mpx_status_label = tk.Label(
            status_bar,
            text="Multiplexer: Not Connected",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.mpx_status_label.pack(side="left", padx=10)
        
        # Device count
        self.device_count_label = tk.Label(
            status_bar,
            text="Devices: 0 selected / 0 total",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.device_count_label.pack(side="left", padx=10)
        
        # Spacer
        ttk.Frame(status_bar).pack(side="left", expand=True)
        
        # Theme toggle (placeholder for future)
        self.theme_label = tk.Label(
            status_bar,
            text="☀ Light Mode",
            font=("Segoe UI", 9),
            fg="#888888",
            cursor="hand2"
        )
        self.theme_label.pack(side="right", padx=10)
        # self.theme_label.bind("<Button-1>", lambda e: self.toggle_theme())  # Future implementation

    def _init_quick_scan_ui(self) -> None:
        """Set up widgets for the Quick Scan tab with overlay controls."""
        # Control frame row 1 - Scan parameters
        control_frame = ttk.Frame(self.quick_scan_frame, padding=(10, 10))
        control_frame.grid(row=0, column=0, sticky="ew")
        control_frame.columnconfigure(9, weight=1)

        ttk.Label(control_frame, text="Voltage (V):").grid(row=0, column=0, padx=(0, 5))
        self.quick_scan_voltage_var = tk.DoubleVar(value=0.2)
        self.quick_scan_voltage_spin = ttk.Spinbox(
            control_frame,
            from_=0.0,
            to=5.0,
            increment=0.05,
            textvariable=self.quick_scan_voltage_var,
            width=8
        )
        self.quick_scan_voltage_spin.grid(row=0, column=1, padx=(0, 10))

        ttk.Label(control_frame, text="Settle (s):").grid(row=0, column=2, padx=(0, 5))
        self.quick_scan_settle_var = tk.DoubleVar(value=0.2)
        self.quick_scan_settle_spin = ttk.Spinbox(
            control_frame,
            from_=0.0,
            to=5.0,
            increment=0.05,
            textvariable=self.quick_scan_settle_var,
            width=8
        )
        self.quick_scan_settle_spin.grid(row=0, column=3, padx=(0, 10))

        ttk.Label(control_frame, text="Threshold (A):").grid(row=0, column=4, padx=(0, 5))
        self.quick_scan_threshold_var = tk.StringVar(value="1.0e-7")
        threshold_spin = ttk.Spinbox(
            control_frame,
            from_=1e-12,
            to=1e-3,
            increment=1e-8,
            textvariable=self.quick_scan_threshold_var,
            width=12
        )
        threshold_spin.grid(row=0, column=5, padx=(0, 10))
        threshold_spin.bind("<Return>", lambda e: self._update_threshold_from_var())
        threshold_spin.bind("<FocusOut>", lambda e: self._update_threshold_from_var())

        self.quick_scan_run_button = ttk.Button(control_frame, text="Run Scan", command=self.start_quick_scan)
        self.quick_scan_run_button.grid(row=0, column=6, padx=5)

        self.quick_scan_stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_quick_scan, state=tk.DISABLED)
        self.quick_scan_stop_button.grid(row=0, column=7, padx=5)

        self.quick_scan_save_button = ttk.Button(control_frame, text="Save", command=self.save_quick_scan_results, state=tk.DISABLED)
        self.quick_scan_save_button.grid(row=0, column=8, padx=5)

        self.quick_scan_load_button = ttk.Button(control_frame, text="Load", command=self.load_quick_scan_results)
        self.quick_scan_load_button.grid(row=0, column=9, padx=5, sticky="w")

        self.quick_scan_status = ttk.Label(control_frame, text="Status: Idle")
        self.quick_scan_status.grid(row=0, column=10, padx=(10, 0), sticky="w")
        
        # Control frame row 2 - Overlay controls (separate row!)
        overlay_frame = ttk.Frame(self.quick_scan_frame, padding=(10, 5, 10, 5))
        overlay_frame.grid(row=1, column=0, sticky="ew")
        
        ttk.Label(overlay_frame, text="Overlays:").pack(side="left", padx=5)
        
        ttk.Checkbutton(
            overlay_frame,
            text="Show Quick Scan Results",
            variable=self.show_quick_scan_overlay,
            command=self._redraw_quick_scan_overlay
        ).pack(side="left", padx=5)
        
        ttk.Checkbutton(
            overlay_frame,
            text="Show Device Status",
            variable=self.show_status_overlay,
            command=self._redraw_quick_scan_overlay
        ).pack(side="left", padx=5)
        
        ttk.Button(
            overlay_frame,
            text="Apply Threshold to Undefined",
            command=self.apply_threshold_to_undefined,
            width=25
        ).pack(side="left", padx=10)
        
        ttk.Button(
            overlay_frame,
            text="Export Status to Excel",
            command=self.export_device_status_excel,
            width=20
        ).pack(side="left", padx=5)

        # Canvas frame - row 3
        canvas_frame = ttk.Frame(self.quick_scan_frame, padding=(10, 0, 10, 10))
        canvas_frame.grid(row=2, column=0, sticky="nsew")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        # Canvas at larger size (600x500) for better visibility
        self.quick_scan_canvas = tk.Canvas(
            canvas_frame,
            width=600,
            height=500,
            bg="white",
            highlightbackground="black"
        )
        self.quick_scan_canvas.grid(row=0, column=0, sticky="nsew")

        legend_frame = ttk.Frame(canvas_frame)
        legend_frame.grid(row=0, column=1, padx=(10, 0), sticky="ns")
        ttk.Label(legend_frame, text="Current Legend").grid(row=0, column=0, pady=(0, 5))
        legend_canvas = tk.Canvas(legend_frame, width=30, height=200, highlightthickness=0)
        legend_canvas.grid(row=1, column=0, sticky="ns")
        for i in range(200):
            color_ratio = i / 199
            current = self._lerp_current(color_ratio)
            color = self._current_to_color(current)
            legend_canvas.create_line(0, 199 - i, 30, 199 - i, fill=color)
        ttk.Label(legend_frame, text="≤1e-10 A").grid(row=2, column=0, pady=(5, 0))
        ttk.Label(legend_frame, text="≥1e-6 A").grid(row=3, column=0, pady=(0, 5))
        
        # Telegram controls below legend
        telegram_frame = ttk.LabelFrame(legend_frame, text="Telegram", padding=5)
        telegram_frame.grid(row=4, column=0, pady=(10, 0), sticky="ew")
        
        ttk.Label(telegram_frame, text="Bot:").grid(row=0, column=0, sticky="w", pady=2)
        bot_names = list(self.telegram_bots.keys())
        telegram_bot_combo = ttk.Combobox(
            telegram_frame,
            textvariable=self.telegram_bot_name_var,
            values=bot_names,
            width=18,
            state="readonly"
        )
        telegram_bot_combo.grid(row=1, column=0, sticky="ew", pady=2)
        if bot_names:
            self.telegram_bot_name_var.set(bot_names[0])
        telegram_bot_combo.bind("<<ComboboxSelected>>", lambda e: self._update_telegram_bot())
        
        ttk.Checkbutton(
            telegram_frame,
            text="Enable Notifications",
            variable=self.telegram_enabled,
            command=self._update_telegram_bot
        ).grid(row=2, column=0, sticky="w", pady=(5, 0))
        
        telegram_frame.columnconfigure(0, weight=1)

        # Log frame - row 4
        log_frame = ttk.Frame(self.quick_scan_frame, padding=(10, 0, 10, 10))
        log_frame.grid(row=3, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.quick_scan_log = tk.Text(log_frame, height=8, state=tk.DISABLED)
        self.quick_scan_log.grid(row=0, column=0, sticky="nsew")

        quick_scan_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.quick_scan_log.yview)
        quick_scan_scrollbar.grid(row=0, column=1, sticky="ns")
        self.quick_scan_log.configure(yscrollcommand=quick_scan_scrollbar.set)

        self.quick_scan_canvas_image: Optional[ImageTk.PhotoImage] = None
        self.quick_scan_overlay_items: Dict[str, int] = {}
        self.quick_scan_results: Dict[str, float] = {}

    def _update_quick_scan_background(self, image: Image.Image) -> None:
        """Update the base image shown on the quick scan canvas."""
        if not hasattr(self, 'quick_scan_canvas') or self.quick_scan_canvas is None:
            return
        self.quick_scan_canvas.delete("all")
        # Resize image to match quick scan canvas size (600x500) - zoomed in
        quick_scan_img = image.resize((600, 500))
        self.quick_scan_base_image = quick_scan_img.copy()
        self.quick_scan_canvas_image = ImageTk.PhotoImage(self.quick_scan_base_image)
        self.quick_scan_canvas.create_image(0, 0, anchor="nw", image=self.quick_scan_canvas_image)
        self._redraw_quick_scan_overlay()

    def _lerp_current(self, ratio: float) -> float:
        """Return a current value between min and max using logarithmic interpolation."""
        ratio_clamped = max(0.0, min(1.0, ratio))
        min_i = max(self.quick_scan_min_current, 1e-20)
        max_i = max(self.quick_scan_max_current, min_i * 10)
        log_min = math.log10(min_i)
        log_max = math.log10(max_i)
        return 10 ** (log_min + ratio_clamped * (log_max - log_min))

    def _current_to_color(self, current_a: float) -> str:
        """Map a measured current to a color between dark red and green."""
        min_i = max(self.quick_scan_min_current, 1e-20)
        max_i = max(self.quick_scan_max_current, min_i * 10)
        log_min = math.log10(min_i)
        log_max = math.log10(max_i)
        denom = log_max - log_min if log_max != log_min else 1e-9
        if current_a <= 0:
            ratio = 0.0
        else:
            ratio = (math.log10(max(current_a, min_i)) - log_min) / denom
        ratio = max(0.0, min(1.0, ratio))
        # Bright gradient: red -> orange -> green
        if ratio <= 0.5:
            local = ratio / 0.5
            start = (255, 0, 0)       # red
            end = (255, 140, 0)       # orange
        else:
            local = (ratio - 0.5) / 0.5
            start = (255, 140, 0)     # orange
            end = (0, 255, 0)         # green
        r = int(start[0] + (end[0] - start[0]) * local)
        g = int(start[1] + (end[1] - start[1]) * local)
        b = int(start[2] + (end[2] - start[2]) * local)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _redraw_quick_scan_overlay(self) -> None:
        """Draw or update current overlays for the quick scan canvases."""
        self._draw_quick_scan_overlay_on(
            self.quick_scan_canvas if hasattr(self, "quick_scan_canvas") else None,
            "overlay",
            canvas_width=600,  # Original canvas width
            canvas_height=500
        )
        self._draw_quick_scan_overlay_on(
            self.canvas if hasattr(self, "canvas") else None,
            "quick_scan_overlay",
            canvas_width=600,
            canvas_height=500
        )
        self._draw_status_overlay_on(
            self.canvas if hasattr(self, "canvas") else None,
            "status_overlay",
            canvas_width=600,
            canvas_height=500
        )

    def _draw_quick_scan_overlay_on(self, target_canvas: Optional[tk.Canvas], tag: str, 
                                    canvas_width: int, canvas_height: int) -> None:
        """Draw quick scan overlay rectangles on the provided canvas."""
        if target_canvas is None:
            return
        target_canvas.delete(tag)
        
        # Check if quick scan overlay is enabled
        if not self.show_quick_scan_overlay.get():
            return
            
        if not getattr(self, "original_image", None):
            return
            
        orig_width, orig_height = self.original_image.size
        scale_x = orig_width / canvas_width
        scale_y = orig_height / canvas_height

        for device, bounds in self.device_mapping.items():
            current = self.quick_scan_results.get(device)
            if current is None:
                continue
            if isinstance(current, float) and math.isnan(current):
                continue
            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y
            color = self._current_to_color(current)
            target_canvas.create_rectangle(
                x_min,
                y_min,
                x_max,
                y_max,
                fill=color,
                outline="",
                stipple="gray50",  # Semi-transparent effect
                tags=tag
            )

    def _draw_status_overlay_on(self, target_canvas: Optional[tk.Canvas], tag: str,
                                canvas_width: int, canvas_height: int) -> None:
        """Draw device status overlay on the canvas."""
        if target_canvas is None:
            return
        target_canvas.delete(tag)
        
        # Check if status overlay is enabled
        if not self.show_status_overlay.get():
            return
            
        if not getattr(self, "original_image", None):
            return
            
        orig_width, orig_height = self.original_image.size
        scale_x = orig_width / canvas_width
        scale_y = orig_height / canvas_height

        for device, bounds in self.device_mapping.items():
            status_info = self.device_status.get(device, {})
            manual_status = status_info.get("manual_status", "undefined")
            
            # Only draw for manually classified devices
            if manual_status == "undefined":
                continue
                
            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y
            
            # Solid color for manual classification
            if manual_status == "working":
                color = "#4CAF50"  # Green
            elif manual_status == "broken":
                color = "#F44336"  # Red
            else:
                continue
                
            target_canvas.create_rectangle(
                x_min,
                y_min,
                x_max,
                y_max,
                fill=color,
                outline="",
                stipple="gray75",  # Semi-transparent effect
                tags=tag
            )

    def start_quick_scan(self) -> None:
        """Start the quick scan routine across all devices."""
        if self.quick_scan_running:
            return
        if self.mpx_manager is None:
            messagebox.showwarning("Multiplexer", "Multiplexer manager not initialized.")
            return
        if not getattr(self, "device_list", None):
            messagebox.showwarning("Devices", "No devices available to scan.")
            return
        try:
            voltage = float(self.quick_scan_voltage_var.get())
        except (tk.TclError, ValueError, TypeError):
            messagebox.showerror("Quick Scan", "Voltage value is invalid.")
            return

        try:
            settle_time = max(0.0, float(self.quick_scan_settle_var.get()))
        except (tk.TclError, ValueError, TypeError):
            messagebox.showerror("Quick Scan", "Settle time value is invalid.")
            return

        self.quick_scan_abort.clear()
        self.quick_scan_running = True
        self.quick_scan_results.clear()
        self._redraw_quick_scan_overlay()
        self._set_quick_scan_buttons(running=True)
        self._set_quick_scan_status("Running")
        self._log_quick_scan("Starting quick scan...")

        self.quick_scan_thread = threading.Thread(
            target=self._quick_scan_worker,
            args=(voltage, settle_time),
            daemon=True
        )
        self.quick_scan_thread.start()

    def stop_quick_scan(self) -> None:
        if self.quick_scan_running:
            self.quick_scan_abort.set()
            self._log_quick_scan("Stop requested. Finishing current device...")

    def _quick_scan_worker(self, voltage: float, settle_time: float) -> None:
        controller = None
        instrument_ready = False
        if Keithley2400Controller is not None:
            try:
                controller = Keithley2400Controller()
                if getattr(controller, "device", None):
                    instrument_ready = True
                    self._run_on_ui(lambda: self._log_quick_scan("Keithley 2400 connected for quick scan."))
                else:
                    controller = None
            except Exception as exc:
                controller = None
                self._run_on_ui(lambda: self._log_quick_scan(f"Instrument unavailable, using simulation. ({exc})"))
        else:
            self._run_on_ui(lambda: self._log_quick_scan("Instrument driver not available, using simulation."))

        if not instrument_ready:
            controller = None

        if controller:
            try:
                controller.set_voltage(0.0)
            except Exception:
                pass

        for idx, device in enumerate(self.device_list):
            if self.quick_scan_abort.is_set():
                break

            self._run_on_ui(lambda d=device, i=idx: self._highlight_quick_scan_device(d, i))

            try:
                routed = self.mpx_manager.route_to_device(device, idx)
            except Exception as exc:
                self._run_on_ui(lambda msg=f"Routing failed for {self.get_device_label(device)}: {exc}": self._log_quick_scan(msg))
                continue

            if not routed:
                self._run_on_ui(lambda msg=f"Routing failed for {self.get_device_label(device)}.": self._log_quick_scan(msg))
                continue

            time.sleep(settle_time)  # Allow time for relays to settle

            if self.quick_scan_abort.is_set():
                break

            if controller:
                current = self._measure_device_current(controller, voltage)
            else:
                current = self._simulate_quick_scan_current(device, voltage)

            self._run_on_ui(lambda d=device, value=current: self._store_quick_scan_result(d, value))
            label = self.get_device_label(device)
            self._run_on_ui(lambda l=label, value=current: self._log_quick_scan(f"{l}: {self._format_current(value)}"))

        aborted = self.quick_scan_abort.is_set()

        if controller:
            try:
                controller.set_voltage(0.0)
                time.sleep(0.05)
                controller.enable_output(False)
            except Exception:
                pass

        self._run_on_ui(lambda: self._finalize_quick_scan(aborted))

    def _measure_device_current(self, controller: "Keithley2400Controller", voltage: float) -> Optional[float]:
        try:
            controller.set_voltage(voltage)
            time.sleep(0.1)
            current = controller.measure_current()
            controller.set_voltage(0.0)
            return float(current) if current is not None else None
        except Exception as exc:
            self._run_on_ui(lambda msg=f"Measurement error: {exc}": self._log_quick_scan(msg))
            return None

    def _simulate_quick_scan_current(self, device: str, voltage: float) -> float:
        rng = random.Random()
        rng.seed(f"{device}:{round(voltage, 3)}")
        failure_floor = min(self.quick_scan_min_current * 0.1, 1e-11)

        if rng.random() < 0.25:
            return rng.uniform(failure_floor, self.quick_scan_min_current * 0.25)

        log_min = math.log10(max(self.quick_scan_min_current, 1e-12))
        log_max = math.log10(max(self.quick_scan_max_current, log_min + 1e-6))
        span = log_max - log_min
        biased = rng.random() ** 0.5
        return 10 ** (log_min + span * biased)

    def _highlight_quick_scan_device(self, device: str, idx: int) -> None:
        label = self.get_device_label(device)
        self.current_index = idx
        self.device_var.set(label)
        self.info_box.config(text=f"Current Device: {label}")
        try:
            self.update_highlight(device)
        except Exception:
            pass
        self._set_quick_scan_status(f"Scanning {label}")

    def _store_quick_scan_result(self, device: str, current: Optional[float]) -> None:
        self.quick_scan_results[device] = current
        self._redraw_quick_scan_overlay()

    # ==========================
    # TELEGRAM INTEGRATION
    # ==========================

    def _load_telegram_bots(self) -> None:
        """Load Telegram bot configurations from messaging_data.json."""
        config_path = BASE_DIR / "Json_Files" / "messaging_data.json"
        self.telegram_bots = {}
        
        try:
            with config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                for name, info in data.items():
                    if isinstance(info, dict):
                        token = str(info.get("token", "") or "")
                        chatid = str(info.get("chatid", info.get("chat_id", "")) or "")
                        if token and chatid:
                            self.telegram_bots[str(name)] = {"token": token, "chatid": chatid}
        except FileNotFoundError:
            pass  # File doesn't exist, that's okay
        except Exception as e:
            print(f"Failed to load Telegram bot config: {e}")

    def _update_telegram_bot(self) -> None:
        """Update or create Telegram bot instance based on current settings."""
        if not self.telegram_enabled.get():
            self.telegram_bot = None
            return
        
        bot_name = self.telegram_bot_name_var.get().strip()
        if not bot_name or bot_name not in self.telegram_bots:
            self.telegram_bot = None
            return
        
        bot_config = self.telegram_bots[bot_name]
        token = bot_config.get("token", "").strip()
        chat_id = bot_config.get("chatid", "").strip()
        
        if not token or not chat_id:
            self.telegram_bot = None
            return
        
        try:
            from Notifications import TelegramBot
            self.telegram_bot = TelegramBot(token, chat_id)
            self._log_quick_scan(f"Telegram bot '{bot_name}' initialized")
        except Exception as e:
            self.telegram_bot = None
            self._log_quick_scan(f"Failed to initialize Telegram bot '{bot_name}': {e}")

    def _capture_canvas_image(self) -> Optional[Path]:
        """Capture the quick scan canvas with heat map overlay as an image file."""
        if not hasattr(self, 'quick_scan_base_image') or self.quick_scan_base_image is None:
            return None
        
        try:
            # Start with the base image
            canvas_image = self.quick_scan_base_image.copy()
            
            # Convert to RGBA if needed for transparency
            if canvas_image.mode != 'RGBA':
                canvas_image = canvas_image.convert('RGBA')
            
            # Create overlay layer
            overlay = Image.new('RGBA', canvas_image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Get scaling factors
            # Device bounds are in original image coordinates, need to scale to quick scan canvas (600x500)
            orig_width, orig_height = self.original_image.size if hasattr(self, 'original_image') and self.original_image else (600, 500)
            quick_scan_width = 600
            quick_scan_height = 500
            scale_x = orig_width / quick_scan_width
            scale_y = orig_height / quick_scan_height
            
            # Draw quick scan overlay if enabled
            if self.show_quick_scan_overlay.get() and hasattr(self, 'device_mapping'):
                for device, bounds in self.device_mapping.items():
                    current = self.quick_scan_results.get(device)
                    if current is None or (isinstance(current, float) and math.isnan(current)):
                        continue
                    
                    # Calculate device bounds on canvas
                    x_min_raw = bounds["x_min"] / scale_x
                    x_max_raw = bounds["x_max"] / scale_x
                    y_min_raw = bounds["y_min"] / scale_y
                    y_max_raw = bounds["y_max"] / scale_y
                    
                    # Ensure min < max (handle cases where coordinates might be reversed)
                    x_min = int(min(x_min_raw, x_max_raw))
                    x_max = int(max(x_min_raw, x_max_raw))
                    y_min = int(min(y_min_raw, y_max_raw))
                    y_max = int(max(y_min_raw, y_max_raw))
                    
                    # Skip if invalid bounds
                    if x_min >= x_max or y_min >= y_max:
                        continue
                    
                    # Clamp to image bounds
                    x_min = max(0, min(x_min, canvas_image.width - 1))
                    x_max = max(1, min(x_max, canvas_image.width))
                    y_min = max(0, min(y_min, canvas_image.height - 1))
                    y_max = max(1, min(y_max, canvas_image.height))
                    
                    # Get color for this current value
                    color = self._current_to_color(current)
                    # Convert hex color to RGBA
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                    overlay_color = (r, g, b, 128)  # Semi-transparent
                    
                    # Draw rectangle on overlay
                    draw.rectangle([x_min, y_min, x_max, y_max], fill=overlay_color)
            
            # Draw device status overlay if enabled
            if self.show_status_overlay.get() and hasattr(self, 'device_mapping'):
                for device, bounds in self.device_mapping.items():
                    status_info = self.device_status.get(device, {})
                    manual_status = status_info.get("manual_status", "undefined")
                    
                    if manual_status == "undefined":
                        continue
                    
                    # Calculate device bounds on canvas
                    x_min_raw = bounds["x_min"] / scale_x
                    x_max_raw = bounds["x_max"] / scale_x
                    y_min_raw = bounds["y_min"] / scale_y
                    y_max_raw = bounds["y_max"] / scale_y
                    
                    # Ensure min < max (handle cases where coordinates might be reversed)
                    x_min = int(min(x_min_raw, x_max_raw))
                    x_max = int(max(x_min_raw, x_max_raw))
                    y_min = int(min(y_min_raw, y_max_raw))
                    y_max = int(max(y_min_raw, y_max_raw))
                    
                    # Skip if invalid bounds
                    if x_min >= x_max or y_min >= y_max:
                        continue
                    
                    # Clamp to image bounds
                    x_min = max(0, min(x_min, canvas_image.width - 1))
                    x_max = max(1, min(x_max, canvas_image.width))
                    y_min = max(0, min(y_min, canvas_image.height - 1))
                    y_max = max(1, min(y_max, canvas_image.height))
                    
                    if manual_status == "working":
                        overlay_color = (76, 175, 80, 192)  # Green, more opaque
                    elif manual_status == "broken":
                        overlay_color = (244, 67, 54, 192)  # Red, more opaque
                    else:
                        continue
                    
                    draw.rectangle([x_min, y_min, x_max, y_max], fill=overlay_color)
            
            # Composite overlay onto base image
            final_image = Image.alpha_composite(canvas_image, overlay)
            # Convert back to RGB for saving
            final_image = final_image.convert('RGB')
            
            # Create file path
            save_root = resolve_default_save_root()
            if self.current_device_name:
                device_folder = self.get_device_folder()
                device_folder.mkdir(parents=True, exist_ok=True)
                image_path = device_folder / f"quick_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            else:
                sample = self.sample_type_var.get()
                sample_dir = save_root / sample.replace(" ", "_")
                sample_dir.mkdir(parents=True, exist_ok=True)
                image_path = sample_dir / f"quick_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            # Save image
            final_image.save(image_path, 'PNG')
            
            return image_path
            
        except Exception as e:
            self._log_quick_scan(f"Failed to capture canvas image: {e}")
            return None

    def _send_telegram_notification(self, aborted: bool) -> None:
        """Send Telegram notification when quick scan completes."""
        if not self.telegram_enabled.get() or self.telegram_bot is None:
            return
        
        try:
            sample = self.sample_type_var.get()
            device_name = self.current_device_name or "Unknown Device"
            voltage = self.quick_scan_voltage_var.get()
            
            status = "Aborted" if aborted else "Complete"
            device_count = len(self.quick_scan_results)
            
            # Count working vs non-working devices
            working_count = 0
            non_working_count = 0
            for device, current in self.quick_scan_results.items():
                if current is None or (isinstance(current, float) and math.isnan(current)):
                    continue
                if current >= self.quick_scan_threshold:
                    working_count += 1
                else:
                    non_working_count += 1
            
            # Escape markdown special characters to avoid parsing errors
            def escape_markdown(text: str) -> str:
                """Escape markdown special characters that cause parsing issues."""
                # Only escape characters that commonly cause issues in our messages
                # Underscores are the main culprit (e.g., "Cross_bar")
                # Don't escape dots/minuses in numbers (e.g., "1.000e-07")
                text = text.replace('_', '\\_')  # Underscore for italics
                text = text.replace('*', '\\*')  # Asterisk for bold
                text = text.replace('[', '\\[')  # Square brackets for links
                text = text.replace(']', '\\]')
                return text
            
            message = (
                f"Quick Scan {status}\n\n"
                f"Device: {escape_markdown(device_name)}\n"
                f"Sample Type: {escape_markdown(sample)}\n"
                f"Voltage: {voltage} V\n"
                f"Threshold: {escape_markdown(f'{self.quick_scan_threshold:.3e}')} A\n"
                f"Devices Scanned: {device_count}\n"
                f"Working: {working_count}\n"
                f"Non-Working: {non_working_count}"
            )
            
            self.telegram_bot.send_message(message)
            
            # Capture and send canvas image
            image_path = self._capture_canvas_image()
            if image_path and image_path.exists():
                caption = f"Quick Scan Heat Map - {escape_markdown(device_name)} ({escape_markdown(sample)})"
                self.telegram_bot.send_image(str(image_path), caption)
                self._log_quick_scan("Sent Telegram notification with image")
            else:
                self._log_quick_scan("Sent Telegram notification (image capture failed)")
                
        except Exception as e:
            self._log_quick_scan(f"Failed to send Telegram notification: {e}")

    def _finalize_quick_scan(self, aborted: bool) -> None:
        self.quick_scan_running = False
        status = "Aborted" if aborted else "Complete"
        self._set_quick_scan_status(status)
        self._set_quick_scan_buttons(running=False)
        if self.quick_scan_results:
            self.quick_scan_save_button.config(state=tk.NORMAL)
            
            # Automatically update device status for undefined devices
            voltage = self.quick_scan_voltage_var.get()
            updated_count = 0
            for device, current in self.quick_scan_results.items():
                if current is None or (isinstance(current, float) and math.isnan(current)):
                    continue
                    
                # Get or create device status
                if device not in self.device_status:
                    self.device_status[device] = {
                        "auto_classification": "unknown",
                        "manual_status": "undefined",
                        "last_current_a": None,
                        "test_voltage_v": None,
                        "last_tested": None,
                        "notes": "",
                        "measurement_count": 0,
                        "quick_scan_history": []
                    }
                
                # Update auto classification based on threshold
                auto_class = "working" if current >= self.quick_scan_threshold else "not-working"
                self.device_status[device]["auto_classification"] = auto_class
                self.device_status[device]["last_current_a"] = current
                self.device_status[device]["test_voltage_v"] = voltage
                self.device_status[device]["last_tested"] = datetime.now().isoformat(timespec='seconds')
                
                # Add to quick scan history
                history_entry = {
                    "timestamp": datetime.now().isoformat(timespec='seconds'),
                    "current_a": current,
                    "voltage_v": voltage
                }
                if "quick_scan_history" not in self.device_status[device]:
                    self.device_status[device]["quick_scan_history"] = []
                self.device_status[device]["quick_scan_history"].append(history_entry)
                
                updated_count += 1
            
            if updated_count > 0:
                self._save_device_status()
                self._log_quick_scan(f"Updated status for {updated_count} device(s)")
        
        self._log_quick_scan(f"Quick scan {status.lower()}.")
        
        # Send Telegram notification if enabled
        if not aborted:  # Only send on completion, not abort
            self._send_telegram_notification(aborted)

    def _set_quick_scan_buttons(self, running: bool) -> None:
        run_state = tk.DISABLED if running else tk.NORMAL
        stop_state = tk.NORMAL if running else tk.DISABLED
        self.quick_scan_run_button.config(state=run_state)
        self.quick_scan_stop_button.config(state=stop_state)
        if running:
            self.quick_scan_save_button.config(state=tk.DISABLED)
        elif self.quick_scan_results:
            self.quick_scan_save_button.config(state=tk.NORMAL)
        else:
            self.quick_scan_save_button.config(state=tk.DISABLED)

    def _set_quick_scan_status(self, text: str) -> None:
        self.quick_scan_status.config(text=f"Status: {text}")

    def _log_quick_scan(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.quick_scan_log.config(state=tk.NORMAL)
        self.quick_scan_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.quick_scan_log.config(state=tk.DISABLED)
        self.quick_scan_log.see(tk.END)

    def _format_current(self, current: Optional[float]) -> str:
        if current is None or (isinstance(current, float) and math.isnan(current)):
            return "n/a"
        return f"{current:.3e} A"

    def save_quick_scan_results(self) -> None:
        if self.quick_scan_running:
            messagebox.showinfo("Quick Scan", "Please wait for the scan to finish before saving.")
            return
        if not self.quick_scan_results:
            messagebox.showwarning("Quick Scan", "No quick scan data to save.")
            return

        sample = self.sample_type_var.get()
        if not sample:
            messagebox.showwarning("Quick Scan", "Select a sample before saving.")
            return

        storage_dir = self._get_quick_scan_storage_dir(sample)
        storage_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().isoformat(timespec='seconds')
        voltage = float(self.quick_scan_voltage_var.get())

        payload = {
            "sample": sample,
            "voltage_v": voltage,
            "timestamp": timestamp,
            "device_count": len(self.quick_scan_results),
            "results": []
        }

        for device_key in self.device_list:
            current = self.quick_scan_results.get(device_key)
            if current is not None and isinstance(current, float) and math.isnan(current):
                current = None
            payload["results"].append({
                "device_key": device_key,
                "device_label": self.get_device_label(device_key),
                "current_a": current
            })

        json_path = storage_dir / "quick_scan.json"
        csv_path = storage_dir / "quick_scan.csv"

        try:
            with json_path.open("w", encoding="utf-8") as fp:
                json.dump(payload, fp, indent=2)
        except Exception as exc:
            messagebox.showerror("Quick Scan", f"Failed to save JSON: {exc}")
            return

        try:
            import csv
            with csv_path.open("w", newline="", encoding="utf-8") as fp:
                writer = csv.writer(fp)
                writer.writerow(["device_key", "device_label", "current_a", "voltage_v", "timestamp"])
                for entry in payload["results"]:
                    writer.writerow([
                        entry["device_key"],
                        entry["device_label"],
                        "" if entry["current_a"] is None else f"{entry['current_a']:.6e}",
                        f"{voltage:.6f}",
                        timestamp
                    ])
        except Exception as exc:
            messagebox.showerror("Quick Scan", f"Failed to save CSV: {exc}")
            return

        self.quick_scan_metadata = {
            "sample": sample,
            "voltage_v": voltage,
            "timestamp": timestamp,
            "paths": {"json": str(json_path), "csv": str(csv_path)}
        }
        self._log_quick_scan(f"Saved quick scan to {json_path.name} and {csv_path.name}.")
        self._set_quick_scan_status("Saved")

    def load_quick_scan_results(self) -> None:
        sample = self.sample_type_var.get()
        if not sample:
            messagebox.showwarning("Quick Scan", "Select a sample before loading data.")
            return
        if not self._load_quick_scan_for_sample(sample, silent=False):
            messagebox.showinfo("Quick Scan", f"No saved quick scan data for sample '{sample}'.")

    def _load_quick_scan_for_sample(self, sample: str, silent: bool = True) -> bool:
        storage_dir = self._get_quick_scan_storage_dir(sample)
        json_path = storage_dir / "quick_scan.json"
        if not json_path.exists():
            if not silent:
                self._log_quick_scan("No saved quick scan data found.")
            return False

        try:
            with json_path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
        except Exception as exc:
            if not silent:
                messagebox.showerror("Quick Scan", f"Failed to load quick scan JSON: {exc}")
            return False

        results = {}
        for entry in payload.get("results", []):
            key = entry.get("device_key")
            current = entry.get("current_a")
            if key is not None:
                results[key] = current

        self.quick_scan_results = results
        self.quick_scan_metadata = {
            "sample": payload.get("sample", sample),
            "voltage_v": payload.get("voltage_v"),
            "timestamp": payload.get("timestamp"),
            "paths": {"json": str(json_path)}
        }
        if payload.get("voltage_v") is not None:
            try:
                self.quick_scan_voltage_var.set(float(payload["voltage_v"]))
            except Exception:
                pass
        self._redraw_quick_scan_overlay()
        self._set_quick_scan_buttons(running=False)
        if results:
            self.quick_scan_save_button.config(state=tk.NORMAL)
        status_label = payload.get("timestamp", "Loaded")
        self._set_quick_scan_status(f"Loaded {status_label}")
        if not silent:
            self._log_quick_scan(f"Loaded quick scan data from {json_path.name}.")
        return True

    def _get_quick_scan_storage_dir(self, sample: str) -> Path:
        # Use device folder if device is set
        if self.current_device_name:
            try:
                return self.get_device_folder()
            except ValueError:
                pass
        
        # Fallback to old behavior
        safe_sample = sample.replace(" ", "_")
        return BASE_DIR / "Data_maps" / safe_sample

    def update_device_checkboxes(self) -> None:
        """Update the device checkboxes based on current device list with status indicators."""
        # Clear existing checkboxes
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.device_checkboxes.clear()
        self.checkbox_vars.clear()
        self.device_status_labels.clear()

        # Create new checkboxes with status indicators
        for i, device in enumerate(self.device_list):
            label = self.get_device_label(device)
            var = tk.BooleanVar(value=True)  # Default to selected
            
            # Create frame for checkbox + status
            row_frame = ttk.Frame(self.scrollable_frame)
            row_frame.grid(row=i, column=0, sticky='w', pady=1)
            
            cb = tk.Checkbutton(
                row_frame,
                text=label,
                variable=var,
                command=self.update_selected_devices
            )
            cb.pack(side="left")
            
            # Status indicator label
            status_info = self.device_status.get(device, {})
            manual_status = status_info.get("manual_status", "undefined")
            icon = self.status_icons.get(manual_status, "?")
            
            status_label = tk.Label(
                row_frame,
                text=icon,
                font=("Segoe UI", 10, "bold"),
                fg=self._get_status_color(manual_status),
                width=2
            )
            status_label.pack(side="left", padx=(5, 0))
            
            # Bind right-click to status menu
            cb.bind("<Button-3>", lambda e, d=device: self.show_device_status_menu(e, d))
            status_label.bind("<Button-3>", lambda e, d=device: self.show_device_status_menu(e, d))

            self.device_checkboxes[device] = cb
            self.checkbox_vars[device] = var
            self.device_status_labels[device] = status_label
            self.selected_devices.add(device)

        self.update_selected_devices()

    def select_all_devices(self) -> None:
        """Select all devices"""
        for var in self.checkbox_vars.values():
            var.set(True)
        self.update_selected_devices()

    def deselect_all_devices(self) -> None:
        """Deselect all devices"""
        for var in self.checkbox_vars.values():
            var.set(False)
        self.update_selected_devices()

    def invert_selection(self) -> None:
        """Invert device selection"""
        for var in self.checkbox_vars.values():
            var.set(not var.get())
        self.update_selected_devices()

    def update_selected_devices(self) -> None:
        """Update the list of selected devices"""
        self.selected_devices.clear()
        self.selected_indices.clear()

        for device, var in self.checkbox_vars.items():
            if var.get():
                self.selected_devices.add(device)
                # Find index of device in device_list
                if device in self.device_list:
                    self.selected_indices.append(self.device_list.index(device))

        # Sort indices
        self.selected_indices.sort()

        # Update status
        total = len(self.device_list)
        selected = len(self.selected_devices)
        self.selection_status.config(text=f"Selected: {selected}/{total}")

        # Update canvas highlights
        self.update_canvas_selection_highlights()
        
        # Update status bar and measure button
        self._update_status_bar()

        # Log selection
        friendly_selected = [self.get_device_label(self.device_list[idx]) for idx in self.selected_indices]
        selection_text = ", ".join(friendly_selected[:5])  # Show first 5
        if len(friendly_selected) > 5:
            selection_text += f" ... (+{len(friendly_selected)-5} more)"
        if not selection_text:
            selection_text = "None"
        self.log_terminal(f"Selected devices: {selection_text}", "INFO")
        
        # Notify child GUIs of device selection change
        selected_device_list = [self.device_list[i] for i in self.selected_indices]
        self._notify_child_guis('device_selection', selected_devices=selected_device_list, selected_indices=self.selected_indices.copy())

    def _update_status_bar(self) -> None:
        """Update the status bar with current device counts."""
        total = len(self.device_list) if hasattr(self, 'device_list') else 0
        selected = len(self.selected_devices)
        
        # Update device count label
        if hasattr(self, 'device_count_label'):
            self.device_count_label.config(text=f"Devices: {selected} selected / {total} total")
        
        # Update measure button text
        if hasattr(self, 'measure_button'):
            if selected > 0:
                self.measure_button.config(text=f"Measure {selected} Selected Device{'s' if selected != 1 else ''}")
            else:
                self.measure_button.config(text="Measure Selected Devices")

    def update_canvas_selection_highlights(self) -> None:
        """Update visual indicators on canvas for selected devices"""
        # Remove existing selection highlights
        self.canvas.delete("selection")

        if not hasattr(self, 'original_image') or self.original_image is None:
            return
            
        orig_width, orig_height = self.original_image.size
        scale_x = orig_width / 600
        scale_y = orig_height / 500

        for device, bounds in self.device_mapping.items():
            if device in self.selected_devices:
                x_min = bounds["x_min"] / scale_x
                x_max = bounds["x_max"] / scale_x
                y_min = bounds["y_min"] / scale_y
                y_max = bounds["y_max"] / scale_y

                # Draw green rectangle for selected devices
                self.canvas.create_rectangle(
                    x_min, y_min, x_max, y_max,
                    outline="#4CAF50", width=2, tags="selection"
                )

    def canvas_ctrl_click(self, event: Any) -> None:
        """Handle Ctrl+Click for device selection toggle"""
        if not hasattr(self, 'original_image') or self.original_image is None:
            return
            
        orig_width, orig_height = self.original_image.size
        scale_x = orig_width / 600
        scale_y = orig_height / 500

        for device, bounds in self.device_mapping.items():
            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y

            if x_min <= event.x <= x_max and y_min <= event.y <= y_max:
                # Toggle device selection
                if device in self.checkbox_vars:
                    current_value = self.checkbox_vars[device].get()
                    self.checkbox_vars[device].set(not current_value)
                    self.update_selected_devices()
                break

    def canvas_right_click(self, event: Any) -> None:
        """Handle right-click for device status menu"""
        if not hasattr(self, 'original_image') or self.original_image is None:
            return
            
        orig_width, orig_height = self.original_image.size
        scale_x = orig_width / 600
        scale_y = orig_height / 500

        for device, bounds in self.device_mapping.items():
            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y

            if x_min <= event.x <= x_max and y_min <= event.y <= y_max:
                self.show_device_status_menu(event, device)
                break

    # ==========================
    # DEVICE STATUS MANAGEMENT
    # ==========================

    def _get_status_color(self, status: str) -> str:
        """Get color for device status."""
        colors = {
            "working": "#4CAF50",  # Green
            "broken": "#F44336",   # Red
            "undefined": "#888888"  # Gray
        }
        return colors.get(status, "#888888")

    def show_device_status_menu(self, event: Any, device: str) -> None:
        """Show context menu for device status marking."""
        menu = tk.Menu(self.root, tearoff=0)
        label = self.get_device_label(device)
        
        menu.add_command(
            label=f"Device {label}",
            state=tk.DISABLED,
            font=("Segoe UI", 9, "bold")
        )
        menu.add_separator()
        
        menu.add_command(
            label="✓ Mark as Working",
            command=lambda: self.mark_device_status(device, "working", quick=True)
        )
        menu.add_command(
            label="✗ Mark as Broken",
            command=lambda: self.mark_device_status(device, "broken", quick=True)
        )
        menu.add_command(
            label="? Mark as Undefined",
            command=lambda: self.mark_device_status(device, "undefined", quick=True)
        )
        menu.add_separator()
        menu.add_command(
            label="Add/Edit Note...",
            command=lambda: self.mark_device_status(device, None, quick=False)
        )
        menu.add_separator()
        menu.add_command(
            label="View Status Info",
            command=lambda: self.show_device_status_info(device)
        )
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def mark_selected_devices(self, status: str) -> None:
        """Mark all selected devices with given status."""
        if not self.selected_devices:
            messagebox.showwarning("No Selection", "No devices selected.")
            return
        
        for device in self.selected_devices:
            self.mark_device_status(device, status, quick=True)
        
        count = len(self.selected_devices)
        self.log_terminal(f"Marked {count} device(s) as {status}", "SUCCESS")

    def mark_device_status(self, device: str, status: Optional[str], quick: bool = True) -> None:
        """Mark device with manual status. If quick=False, open dialog for notes."""
        label = self.get_device_label(device)
        
        if not quick:
            # Open dialog for detailed marking with notes
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Device Status: {label}")
            dialog.geometry("400x300")
            dialog.transient(self.root)
            dialog.grab_set()
            
            ttk.Label(dialog, text=f"Device: {label}", font=("Segoe UI", 10, "bold")).pack(pady=10)
            
            # Status selection
            status_frame = ttk.Frame(dialog)
            status_frame.pack(pady=10)
            
            ttk.Label(status_frame, text="Status:").grid(row=0, column=0, padx=5)
            status_var = tk.StringVar(value=status or "undefined")
            ttk.Radiobutton(status_frame, text="✓ Working", variable=status_var, value="working").grid(row=0, column=1, padx=5)
            ttk.Radiobutton(status_frame, text="✗ Broken", variable=status_var, value="broken").grid(row=0, column=2, padx=5)
            ttk.Radiobutton(status_frame, text="? Undefined", variable=status_var, value="undefined").grid(row=0, column=3, padx=5)
            
            # Notes
            ttk.Label(dialog, text="Notes:").pack(anchor="w", padx=20)
            notes_text = tk.Text(dialog, height=8, width=45, wrap=tk.WORD)
            notes_text.pack(padx=20, pady=5)
            
            # Pre-fill existing notes
            existing_notes = self.device_status.get(device, {}).get("notes", "")
            if existing_notes:
                notes_text.insert("1.0", existing_notes)
            
            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
            
            def save_status():
                final_status = status_var.get()
                notes = notes_text.get("1.0", tk.END).strip()
                self._update_device_status(device, final_status, notes=notes)
                dialog.destroy()
            
            ttk.Button(button_frame, text="Save", command=save_status, width=12).pack(side="left", padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=12).pack(side="left", padx=5)
            
            dialog.wait_window()
        else:
            # Quick mark without notes
            if status:
                self._update_device_status(device, status)

    def _update_device_status(self, device: str, manual_status: str, notes: str = "") -> None:
        """Update device status in the database and UI."""
        label = self.get_device_label(device)
        
        # Get or create status entry
        if device not in self.device_status:
            self.device_status[device] = {
                "auto_classification": "unknown",
                "manual_status": "undefined",
                "last_current_a": None,
                "test_voltage_v": None,
                "last_tested": None,
                "notes": "",
                "measurement_count": 0,
                "quick_scan_history": []
            }
        
        # Update status
        self.device_status[device]["manual_status"] = manual_status
        if notes:
            self.device_status[device]["notes"] = notes
        
        # Update timestamp
        self.device_status[device]["last_tested"] = datetime.now().isoformat(timespec='seconds')
        
        # Update UI
        if device in self.device_status_labels:
            icon = self.status_icons.get(manual_status, "?")
            color = self._get_status_color(manual_status)
            self.device_status_labels[device].config(text=icon, fg=color)
        
        # Save to disk (auto-saves notes and status to JSON and Excel)
        self._save_device_status()
        
        # Log the update
        if notes:
            self.log_terminal(f"Device {label}: Status updated to '{manual_status}' with notes (auto-saved)", "SUCCESS")
        else:
            self.log_terminal(f"Device {label}: Status updated to '{manual_status}' (auto-saved)", "SUCCESS")
        
        # Update overlays
        self._redraw_quick_scan_overlay()

    def show_device_status_info(self, device: str) -> None:
        """Show detailed status information for a device."""
        label = self.get_device_label(device)
        status_info = self.device_status.get(device, {})
        
        auto_class = status_info.get("auto_classification", "unknown")
        manual_status = status_info.get("manual_status", "undefined")
        last_current = status_info.get("last_current_a")
        test_voltage = status_info.get("test_voltage_v")
        last_tested = status_info.get("last_tested", "Never")
        notes = status_info.get("notes", "No notes")
        meas_count = status_info.get("measurement_count", 0)
        
        info_text = (
            f"Device: {label}\n\n"
            f"Auto Classification: {auto_class}\n"
            f"Manual Status: {manual_status}\n"
            f"Last Current: {f'{last_current:.3e} A' if last_current else 'N/A'}\n"
            f"Test Voltage: {f'{test_voltage} V' if test_voltage else 'N/A'}\n"
            f"Last Tested: {last_tested}\n"
            f"Measurement Count: {meas_count}\n\n"
            f"Notes:\n{notes}"
        )
        
        messagebox.showinfo(f"Device Status: {label}", info_text)

    def apply_threshold_to_undefined(self) -> None:
        """Apply current threshold to classify undefined devices based on quick scan results."""
        classified_count = 0
        
        for device in self.device_list:
            status_info = self.device_status.get(device, {})
            manual_status = status_info.get("manual_status", "undefined")
            
            # Only affect undefined devices
            if manual_status == "undefined":
                current = self.quick_scan_results.get(device)
                if current is not None:
                    auto_class = "working" if current >= self.quick_scan_threshold else "not-working"
                    
                    # Update auto classification only
                    if device not in self.device_status:
                        self.device_status[device] = {
                            "auto_classification": auto_class,
                            "manual_status": "undefined",
                            "last_current_a": current,
                            "test_voltage_v": self.quick_scan_voltage_var.get(),
                            "last_tested": datetime.now().isoformat(timespec='seconds'),
                            "notes": "",
                            "measurement_count": 0,
                            "quick_scan_history": []
                        }
                    else:
                        self.device_status[device]["auto_classification"] = auto_class
                        self.device_status[device]["last_current_a"] = current
                        self.device_status[device]["test_voltage_v"] = self.quick_scan_voltage_var.get()
                    
                    classified_count += 1
        
        if classified_count > 0:
            self._save_device_status()
            self._redraw_quick_scan_overlay()
            self.log_terminal(f"Applied threshold to {classified_count} undefined device(s)", "SUCCESS")
        else:
            messagebox.showinfo("Threshold", "No undefined devices to classify.")

    def _save_device_status(self) -> None:
        """Save device status to JSON and Excel files."""
        # Use device folder if device is set, otherwise use sample folder
        if self.current_device_name:
            try:
                save_dir = self.get_device_folder()
            except ValueError:
                return
        else:
            sample = self.sample_type_var.get()
            if not sample:
                return
            save_root = resolve_default_save_root()
            save_dir = save_root / sample.replace(" ", "_")
        
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON
        json_path = save_dir / "device_status.json"
        try:
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(self.device_status, f, indent=2)
        except Exception as e:
            self.log_terminal(f"Failed to save device status JSON: {e}", "ERROR")
        
        # Save Excel
        self._save_device_status_excel(save_dir / "device_status.xlsx")

    def _save_device_status_excel(self, path: Path) -> None:
        """Save device status to Excel file using csv module (readable by Excel)."""
        try:
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Device", "Auto Classification", "Manual Status", "Last Current (A)",
                    "Test Voltage (V)", "Last Tested", "Measurement Count", "Notes"
                ])
                
                for device in self.device_list:
                    label = self.get_device_label(device)
                    status_info = self.device_status.get(device, {})
                    
                    writer.writerow([
                        label,
                        status_info.get("auto_classification", "unknown"),
                        status_info.get("manual_status", "undefined"),
                        f"{status_info.get('last_current_a', 0):.3e}" if status_info.get("last_current_a") else "",
                        status_info.get("test_voltage_v", ""),
                        status_info.get("last_tested", ""),
                        status_info.get("measurement_count", 0),
                        status_info.get("notes", "")
                    ])
        except Exception as e:
            self.log_terminal(f"Failed to save Excel: {e}", "ERROR")

    def _load_device_status(self) -> None:
        """Load device status from JSON file."""
        sample = self.sample_type_var.get()
        if not sample:
            return
        
        save_root = resolve_default_save_root()
        sample_dir = save_root / sample.replace(" ", "_")
        json_path = sample_dir / "device_status.json"
        
        if not json_path.exists():
            self.log_terminal("No saved device status found", "INFO")
            return
        
        try:
            with json_path.open("r", encoding="utf-8") as f:
                self.device_status = json.load(f)
            self.log_terminal(f"Loaded device status from {json_path.name}", "SUCCESS")
            
            # Update UI
            if hasattr(self, 'device_status_labels'):
                for device, status_label in self.device_status_labels.items():
                    status_info = self.device_status.get(device, {})
                    manual_status = status_info.get("manual_status", "undefined")
                    icon = self.status_icons.get(manual_status, "?")
                    color = self._get_status_color(manual_status)
                    status_label.config(text=icon, fg=color)
        except Exception as e:
            self.log_terminal(f"Failed to load device status: {e}", "ERROR")

    def export_device_status_excel(self) -> None:
        """Export device status to Excel file (user-initiated)."""
        sample = self.sample_type_var.get()
        if not sample:
            messagebox.showwarning("Export", "No sample selected.")
            return
        
        save_root = resolve_default_save_root()
        sample_dir = save_root / sample.replace(" ", "_")
        sample_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = sample_dir / f"device_status_export_{timestamp}.csv"
        
        self._save_device_status_excel(export_path)
        
        messagebox.showinfo("Export Complete", f"Device status exported to:\n{export_path}")
        self.log_terminal(f"Exported device status to {export_path.name}", "SUCCESS")

    # ==========================
    # DEVICE MANAGEMENT
    # ==========================

    def get_device_folder(self, device_name: Optional[str] = None) -> Path:
        """Get the folder path for a specific device."""
        save_root = resolve_default_save_root()
        name = device_name or self.current_device_name
        if not name:
            raise ValueError("No device name specified")
        return save_root / name.replace(" ", "_")

    def set_current_device(self) -> None:
        """Set the current device name from user input."""
        device_name = self.device_name_entry.get().strip()
        
        if not device_name:
            messagebox.showwarning("Device Name", "Please enter a device name (e.g., D104)")
            return
        
        # Sanitize device name to allow broader characters (convert disallowed ones to '_')
        import re
        cleaned_name = re.sub(r'[^A-Za-z0-9_\-\.\(\)% ]+', '_', device_name)
        if cleaned_name != device_name:
            messagebox.showinfo(
                "Device Name Adjusted",
                f"Some characters in '{device_name}' were not allowed.\n"
                f"The device name has been adjusted to:\n{cleaned_name}"
            )
            device_name = cleaned_name
        
        self.current_device_name = device_name
        
        # Notify child GUIs of device name change
        self._notify_child_guis('device_name', device_name=device_name)
        
        # Create device folder
        device_folder = self.get_device_folder()
        device_folder.mkdir(parents=True, exist_ok=True)
        
        # Update device info
        sample_type = self.sample_type_var.get()
        self.device_info = {
            "name": device_name,
            "sample_type": sample_type,
            "created": datetime.now().isoformat(timespec='seconds'),
            "last_modified": datetime.now().isoformat(timespec='seconds'),
            "notes": ""
        }
        
        # Save device info
        self.save_device_info()
        
        # Update UI
        self.device_name_label.config(text=device_name, fg="#4CAF50")
        self.update_device_info_display()
        self.log_terminal(f"Set current device to: {device_name}", "SUCCESS")
        
        # Refresh device list
        self.refresh_device_list()

    def clear_current_device(self) -> None:
        """Clear the current device."""
        if messagebox.askyesno("Clear Device", "Are you sure you want to clear the current device?"):
            self.current_device_name = None
            self.device_info = {}
            self.device_name_entry.delete(0, tk.END)
            self.device_name_label.config(text="No Device", fg="#888888")
            self.update_device_info_display()
            self.log_terminal("Cleared current device", "INFO")
            # Notify child GUIs that device name was cleared
            self._notify_child_guis('device_name', device_name=None)

    def save_device_info(self) -> None:
        """Save device information to JSON file."""
        if not self.current_device_name:
            messagebox.showwarning("No Device", "No device is currently set.")
            return
        
        device_folder = self.get_device_folder()
        device_folder.mkdir(parents=True, exist_ok=True)
        
        # Update last modified
        self.device_info["last_modified"] = datetime.now().isoformat(timespec='seconds')
        
        # Save device info
        info_path = device_folder / "device_info.json"
        try:
            with info_path.open("w", encoding="utf-8") as f:
                json.dump(self.device_info, f, indent=2)
            self.log_terminal(f"Saved device info for {self.current_device_name}", "SUCCESS")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save device info: {e}")
            self.log_terminal(f"Error saving device info: {e}", "ERROR")

    def load_selected_device(self) -> None:
        """Load the device selected in the tree view."""
        selection = self.device_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a device from the list.")
            return
        
        item = self.device_tree.item(selection[0])
        device_name = item["values"][0]  # First column is device name
        
        self.load_device(device_name)

    def load_device(self, device_name: str) -> None:
        """Load a device and all its data."""
        device_folder = self.get_device_folder(device_name)
        
        if not device_folder.exists():
            messagebox.showerror("Device Not Found", f"Device folder not found: {device_folder}")
            return
        
        # Load device info
        info_path = device_folder / "device_info.json"
        if info_path.exists():
            try:
                with info_path.open("r", encoding="utf-8") as f:
                    self.device_info = json.load(f)
                
                self.current_device_name = device_name
                self.device_name_entry.delete(0, tk.END)
                self.device_name_entry.insert(0, device_name)
                self.device_name_label.config(text=device_name, fg="#4CAF50")
                
                # Notify child GUIs of device name change
                self._notify_child_guis('device_name', device_name=device_name)
                
                # Update sample type if stored
                if "sample_type" in self.device_info:
                    self.sample_type_var.set(self.device_info["sample_type"])
                    self.update_dropdowns(None)
                
                # Load device status
                status_path = device_folder / "device_status.json"
                if status_path.exists():
                    with status_path.open("r", encoding="utf-8") as f:
                        self.device_status = json.load(f)
                    self.log_terminal(f"Loaded device status for {device_name}", "SUCCESS")
                
                # Load quick scan results
                quick_scan_path = device_folder / "quick_scan.json"
                if quick_scan_path.exists():
                    with quick_scan_path.open("r", encoding="utf-8") as f:
                        scan_data = json.load(f)
                        results = {}
                        for entry in scan_data.get("results", []):
                            key = entry.get("device_key")
                            current = entry.get("current_a")
                            if key is not None:
                                results[key] = current
                        self.quick_scan_results = results
                        self._redraw_quick_scan_overlay()
                    self.log_terminal(f"Loaded quick scan results for {device_name}", "SUCCESS")
                
                self.update_device_info_display()
                self.log_terminal(f"Loaded device: {device_name}", "SUCCESS")
                
                # Update checkboxes with loaded status
                if hasattr(self, 'device_status_labels'):
                    for device, status_label in self.device_status_labels.items():
                        status_info = self.device_status.get(device, {})
                        manual_status = status_info.get("manual_status", "undefined")
                        icon = self.status_icons.get(manual_status, "?")
                        color = self._get_status_color(manual_status)
                        status_label.config(text=icon, fg=color)
                
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load device: {e}")
                self.log_terminal(f"Error loading device {device_name}: {e}", "ERROR")
        else:
            messagebox.showerror("Device Info Missing", f"Device info file not found: {info_path}")

    def refresh_device_list(self) -> None:
        """Refresh the list of saved devices."""
        # Clear existing items
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        save_root = resolve_default_save_root()
        if not save_root.exists():
            return
        
        filter_type = self.device_filter_var.get()
        
        # Scan for device folders
        for device_folder in save_root.iterdir():
            if not device_folder.is_dir():
                continue
            
            info_path = device_folder / "device_info.json"
            if not info_path.exists():
                continue
            
            try:
                with info_path.open("r", encoding="utf-8") as f:
                    info = json.load(f)
                
                device_name = info.get("name", device_folder.name)
                sample_type = info.get("sample_type", "Unknown")
                last_modified = info.get("last_modified", "Unknown")
                
                # Apply filter
                if filter_type != "All" and sample_type != filter_type:
                    continue
                
                # Determine status
                status_path = device_folder / "device_status.json"
                if status_path.exists():
                    status = "Has Data"
                else:
                    status = "New"
                
                # Add to tree
                self.device_tree.insert(
                    "",
                    "end",
                    values=(device_name, sample_type, last_modified, status)
                )
                
            except Exception as e:
                print(f"Error reading device {device_folder.name}: {e}")

    def update_device_info_display(self) -> None:
        """Update the device info text display."""
        self.device_info_text.config(state=tk.NORMAL)
        self.device_info_text.delete("1.0", tk.END)
        
        if not self.current_device_name:
            self.device_info_text.insert("1.0", "No device currently set.\n\nEnter a device name and click 'Set Device' to begin.")
        else:
            info_lines = [
                f"Device Name: {self.device_info.get('name', 'Unknown')}",
                f"Sample Type: {self.device_info.get('sample_type', 'Unknown')}",
                f"Created: {self.device_info.get('created', 'Unknown')}",
                f"Last Modified: {self.device_info.get('last_modified', 'Unknown')}",
                ""
            ]
            
            # Load device notes from notes.json (using sample name, not sample_type)
            sample_name = self.current_device_name  # Current device name is the sample name (D104)
            if sample_name:
                try:
                    sample_folder = resolve_default_save_root() / sample_name.replace(" ", "_")
                    notes_path = sample_folder / "notes.json"
                    if notes_path.exists():
                        with notes_path.open("r", encoding="utf-8") as f:
                            notes_data = json.load(f)
                            
                            # Display sample notes FIRST if available
                            sample_notes = notes_data.get("Sample_Notes", "")
                            if sample_notes:
                                info_lines.extend([
                                    "Sample Notes:",
                                    sample_notes,
                                    "",
                                    "=" * 50,
                                    ""
                                ])
                            
                            # Then display device notes
                            info_lines.append("Device Notes:")
                            device_notes_dict = notes_data.get("device", {})
                            if device_notes_dict:
                                # Display notes for each device
                                for device_id, device_notes in sorted(device_notes_dict.items()):
                                    if device_notes.strip():  # Only show devices with notes
                                        info_lines.extend([
                                            f"\n{device_id}:",
                                            device_notes,
                                            ""
                                        ])
                            else:
                                info_lines.append("No device notes found.")
                except Exception as e:
                    print(f"Error loading notes from notes.json: {e}")
                    import traceback
                    traceback.print_exc()
                    info_lines.append("Error loading notes from notes.json")
            
            self.device_info_text.insert("1.0", "\n".join(info_lines))
        
        self.device_info_text.config(state=tk.DISABLED)

    # ==========================
    # TERMINAL LOG MANAGEMENT
    # ==========================

    def log_terminal(self, message: str, level: str = "INFO") -> None:
        """Log message to terminal with color coding and timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.terminal_messages.append((timestamp, level, message))
        
        # Apply filter
        if self.terminal_filter.get() != "All" and level != self.terminal_filter.get().upper():
            return
        
        self.terminal_output.config(state=tk.NORMAL)
        self.terminal_output.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
        self.terminal_output.insert(tk.END, f"{message}\n", level.upper())
        self.terminal_output.config(state=tk.DISABLED)
        self.terminal_output.see(tk.END)

    def _apply_terminal_filter(self) -> None:
        """Reapply terminal filter to show only relevant messages."""
        filter_value = self.terminal_filter.get()
        
        self.terminal_output.config(state=tk.NORMAL)
        self.terminal_output.delete("1.0", tk.END)
        
        for timestamp, level, message in self.terminal_messages:
            if filter_value == "All" or level == filter_value.upper():
                self.terminal_output.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
                self.terminal_output.insert(tk.END, f"{message}\n", level.upper())
        
        self.terminal_output.config(state=tk.DISABLED)
        self.terminal_output.see(tk.END)

    def clear_terminal(self) -> None:
        """Clear terminal output."""
        self.terminal_output.config(state=tk.NORMAL)
        self.terminal_output.delete("1.0", tk.END)
        self.terminal_output.config(state=tk.DISABLED)
        self.terminal_messages.clear()

    def export_terminal_log(self) -> None:
        """Export terminal log to file."""
        save_root = resolve_default_save_root()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = save_root / f"terminal_log_{timestamp}.txt"
        
        try:
            with log_path.open("w", encoding="utf-8") as f:
                for ts, level, msg in self.terminal_messages:
                    f.write(f"[{ts}] [{level}] {msg}\n")
            messagebox.showinfo("Export Complete", f"Log exported to:\n{log_path}")
            self.log_terminal(f"Exported log to {log_path.name}", "SUCCESS")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export log: {e}")

    # ==========================
    # OVERLAY MANAGEMENT
    # ==========================

    def _update_threshold_from_var(self) -> None:
        """Update threshold value from StringVar."""
        try:
            value = float(self.quick_scan_threshold_var.get())
            if value > 0:
                self.quick_scan_threshold = value
                self.log_terminal(f"Threshold updated to {value:.3e} A", "INFO")
        except ValueError:
            messagebox.showerror("Invalid Value", "Please enter a valid scientific notation (e.g., 1.0e-7)")
            self.quick_scan_threshold_var.set(f"{self.quick_scan_threshold:.1e}")

    def update_multiplexer(self, event: Optional[Any]) -> None:
        self.multiplexer_type = self.Multiplexer_type_var.get()
        
        # Use new MultiplexerManager to create appropriate adapter
        try:
            if self.multiplexer_type == "Pyswitchbox":
                self.mpx_manager = MultiplexerManager.create(
                    "Pyswitchbox",
                    pin_mapping=pin_mapping
                )
                self.log_terminal("Initiated Pyswitchbox via MultiplexerManager", "SUCCESS")
                self.mpx_status_label.config(text=f"Multiplexer: {self.multiplexer_type} Connected", fg="#4CAF50")
            elif self.multiplexer_type == "Electronic_Mpx":
                # Try to create with real hardware, fall back to simulation if needed
                try:
                    self.mpx = MultiplexerController(simulation_mode=False)
                    self.log_terminal("Initiated Electronic_Mpx with real hardware", "SUCCESS")
                except Exception as e:
                    self.log_terminal(f"Hardware not available, using simulation mode", "WARNING")
                    self.mpx = MultiplexerController(simulation_mode=True)
                
                self.mpx_manager = MultiplexerManager.create(
                    "Electronic_Mpx",
                    controller=self.mpx
                )
                self.mpx_status_label.config(text=f"Multiplexer: {self.multiplexer_type} Connected", fg="#4CAF50")
            elif self.multiplexer_type == "Manual":
                # Manual mode: no hardware initialization, user manually moves probes
                self.mpx_manager = None
                self.log_terminal("Manual mode activated - no multiplexer routing, manual probe movement required", "SUCCESS")
                self.mpx_status_label.config(text="Multiplexer: Manual Mode", fg="#FF9800")
            else:
                self.log_terminal("Unknown multiplexer type", "ERROR")
                self.mpx_status_label.config(text="Multiplexer: Unknown Type", fg="#F44336")
        except Exception as e:
            self.log_terminal(f"Error initializing multiplexer: {e}", "ERROR")
            self.mpx_status_label.config(text="Multiplexer: Error", fg="#F44336")

    def load_image(self, sample: str) -> None:
        """Load image into canvas set up to add others later simply."""
        image_path: Optional[Path] = None
        if sample == 'Cross_bar':
            image_path = BASE_DIR / "Helpers" / "Sample_Infomation" / "memristor.png"
        elif sample == 'Device_Array_10':
            image_path = BASE_DIR / "Helpers" / "Sample_Infomation" / "Multiplexer_10_OUT.jpg"
        elif sample == '15x15mm':
            image_path = BASE_DIR / "Helpers" / "Sample_Infomation" / "15mmx15mm.JPG"

        if image_path is None:
            self.log_terminal(f"No image path defined for sample: {sample}", "WARNING")
            return
            
        if not image_path.exists():
            self.log_terminal(f"Image file not found: {image_path}", "ERROR")
            self.original_image = None
            self.tk_img = None
            self.canvas.delete("all")
            if hasattr(self, 'quick_scan_canvas'):
                self.quick_scan_canvas.delete("all")
            return

        try:
            self.original_image = Image.open(image_path)
            img = self.original_image.resize((600, 500))
            self.tk_img = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
            self.log_terminal(f"Loaded image for {sample}", "SUCCESS")

            if hasattr(self, 'quick_scan_canvas'):
                self._update_quick_scan_background(img)

            # Redraw selection highlights
            self.update_canvas_selection_highlights()
            self._redraw_quick_scan_overlay()
        except Exception as e:
            self.log_terminal(f"Error loading image: {e}", "ERROR")
            self.original_image = None
            self.tk_img = None

    def update_device_type(self, current_device_map: str) -> None:
        # all maps from dict
        self.current_map_name = current_device_map
        self.device_mapping = device_maps[current_device_map]
        self.current_map_map = device_maps[current_device_map]
        self.device_maps_list = list(device_maps.keys())
        self.device_list = list(device_maps[current_device_map].keys())  # Dictionary of devices
        self._build_device_name_mapping()
        # Update device checkboxes when device type changes
        if hasattr(self, 'device_checkboxes'):
            self.update_device_checkboxes()

    def _build_device_name_mapping(self) -> None:
        """Build mapping between device keys and user-facing labels (e.g., A1)."""
        self.device_labels = []
        self.device_labels_by_key = {}
        self.device_keys_by_label = {}
        self.device_section_number_by_key = {}

        section_counts: Dict[str, int] = {}
        for device_key in self.device_list:
            info = self.device_mapping.get(device_key, {})
            section_raw = info.get("section", "")
            section = str(section_raw) if section_raw is not None else ""

            if section:
                section_counts[section] = section_counts.get(section, 0) + 1
                number = section_counts[section]
                label = f"{section}{number}"
            else:
                number = None
                section = ""
                label = device_key

            if label in self.device_keys_by_label:
                suffix = len(self.device_labels) + 1
                label = f"{label}_{suffix}"

            self.device_labels.append(label)
            self.device_labels_by_key[device_key] = label
            self.device_keys_by_label[label] = device_key
            self.device_section_number_by_key[device_key] = (section, number)

    def get_device_label(self, device_key: str) -> str:
        """Return the user-facing label for a device key."""
        return self.device_labels_by_key.get(device_key, device_key)

    def get_device_section_and_number(self, device_key: str) -> Tuple[str, Optional[int]]:
        """Return the (section, number) tuple for a device key."""
        return self.device_section_number_by_key.get(device_key, ("", None))

    def get_device_key_from_label(self, label: str) -> Optional[str]:
        """Resolve a user-facing label back to a device key."""
        return self.device_keys_by_label.get(label)

    def convert_to_name(self, identifier: Any) -> str:
        """Provide Measurement GUI compatible label lookup by index or device key."""
        if isinstance(identifier, str):
            return self.get_device_label(identifier)
        if isinstance(identifier, int):
            if 0 <= identifier < len(self.device_list):
                device_key = self.device_list[identifier]
                return self.get_device_label(device_key)
            return f"device_{identifier + 1}"
        return str(identifier)

    def update_dropdowns(self, event: Optional[Any]) -> None:
        sample = self.sample_type_var.get()
        self.log_terminal(f"Sample chosen: {sample}", "INFO")
        
        # Load image FIRST before updating device type
        # This ensures the canvas has an image before any drawing happens
        self.load_image(sample)
        
        # Now update device type (which triggers checkbox updates)
        self.update_device_type(sample)

        if sample in sample_config:
            sections = sample_config[sample]["sections"]
            self.section_dropdown["values"] = list(sections.keys())
            self.section_dropdown.set("")

            # Disable certain sections (keeping them visible)
            self.section_dropdown["state"] = "readonly"

            # Update device numbers
            self.device_dropdown["values"] = self.device_labels
            self.device_dropdown.set("")

            self.device = self.device_var.get()
            
            # Load device status for this sample
            self._load_device_status()
            
            # Load quick scan results
            if not self._load_quick_scan_for_sample(sample, silent=True):
                self.quick_scan_results.clear()
            
            # Notify child GUIs of sample type change
            self._notify_child_guis('sample_type', sample_type=sample)
            
            self._redraw_quick_scan_overlay()
            if hasattr(self, 'quick_scan_save_button'):
                self.quick_scan_save_button.config(state=tk.DISABLED)
            self._set_quick_scan_status("Idle")
            
            # Update status bar
            self._update_status_bar()

    def prev_device(self) -> None:
        """Move to the previous device in the selected devices list"""
        if not self.selected_indices:
            self.log_terminal("No devices selected")
            return

        # Find current device's position in selected devices
        current_device = self.device_list[self.current_index]
        if self.current_index in self.selected_indices:
            idx_in_selected = self.selected_indices.index(self.current_index)
            # Move to previous selected device
            idx_in_selected = (idx_in_selected - 1) % len(self.selected_indices)
            self.current_index = self.selected_indices[idx_in_selected]
        else:
            # If current device is not selected, move to first selected device
            self.current_index = self.selected_indices[0] if self.selected_indices else 0

        new_device = self.device_list[self.current_index]
        label = self.get_device_label(new_device)
        self.log_terminal(f"Previous device: {label}")

        # Update the displayed device information
        self.device_var.set(label)
        self.info_box.config(text=f"Current Device: {label}")

        # Update the highlight
        self.update_highlight(new_device)

    def next_device(self) -> None:
        """Move to the next device in the selected devices list"""
        if not self.selected_indices:
            self.log_terminal("No devices selected")
            return

        # Find current device's position in selected devices
        current_device = self.device_list[self.current_index]
        if self.current_index in self.selected_indices:
            idx_in_selected = self.selected_indices.index(self.current_index)
            # Move to next selected device
            idx_in_selected = (idx_in_selected + 1) % len(self.selected_indices)
            self.current_index = self.selected_indices[idx_in_selected]
        else:
            # If current device is not selected, move to first selected device
            self.current_index = self.selected_indices[0] if self.selected_indices else 0

        new_device = self.device_list[self.current_index]
        label = self.get_device_label(new_device)
        self.log_terminal(f"Next device: {label}")

        # Update the displayed device information
        self.device_var.set(label)
        self.info_box.config(text=f"Current Device: {label}")

        # Update the highlight
        self.update_highlight(new_device)

    def canvas_click(self, event: Any) -> None:
        if not hasattr(self, 'original_image') or self.original_image is None:
            return
            
        orig_width, orig_height = self.original_image.size
        scaled_width, scaled_height = 600, 500
        # Compute the scaling factors
        scale_x = orig_width / scaled_width
        scale_y = orig_height / scaled_height

        for i, (device, bounds) in enumerate(self.device_mapping.items()):
            # Scale down the bounding box coordinates to match canvas size
            x_min_scaled = bounds["x_min"] / scale_x
            x_max_scaled = bounds["x_max"] / scale_x
            y_min_scaled = bounds["y_min"] / scale_y
            y_max_scaled = bounds["y_max"] / scale_y

            if x_min_scaled <= event.x <= x_max_scaled and y_min_scaled <= event.y <= y_max_scaled:
                # Remove previous highlights
                self.canvas.delete("highlight")

                # Update index
                self.current_index = i  # Now it holds the current index of the device

                label = self.get_device_label(device)
                self.device_var.set(label)
                self.sample_type_var.set(bounds["sample"])
                self.section_var.set(bounds["section"])
                self.info_box.config(text=f"Current Device: {label}")

                # Draw a rectangle around the clicked device
                self.canvas.create_rectangle(
                    x_min_scaled, y_min_scaled, x_max_scaled, y_max_scaled,
                    outline="#009dff", width=3, tags="highlight"
                )
                break

    def update_highlight(self, device: str) -> None:
        # Clear any existing highlights
        self.canvas.delete("highlight")

        # Get the device bounds
        bounds = self.device_mapping.get(device, None)
        if bounds and hasattr(self, 'original_image') and self.original_image is not None:
            orig_width, orig_height = self.original_image.size
            scaled_width, scaled_height = 600, 500
            # Compute the scaling factors
            scale_x = orig_width / scaled_width
            scale_y = orig_height / scaled_height

            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y

            # Draw a new rectangle
            self.canvas.create_rectangle(x_min, y_min, x_max, y_max, outline="#009dff", width=3, tags="highlight")

    def _show_no_devices_dialog(self) -> None:
        """Show dialog when no devices are selected (called after tab switch).
        Note: Device name check has already been handled before this is called."""
        response = messagebox.askyesnocancel(
            "No Devices Selected",
            "No devices are currently selected for measurement.\n\n"
            "Would you like to:\n"
            "• Yes: Stay on Device Manager to select/create devices\n"
            "• No: Skip and continue anyway (measurements will use current device)\n"
            "• Cancel: Return to device selection",
            icon='question'
        )
        if response is None:  # Cancel
            self.notebook.select(0)  # Return to Device Selection tab
            return
        elif response is False:  # No - skip and continue anyway
            self.notebook.select(0)  # Return to Device Selection tab
            
            # Continue with opening measurement window (incorporated logic)
            sample_type = self.sample_type_var.get()
            section = self.section_var.get()
            selected_device_list = []  # Empty list

            self.change_relays()
            print("")
            print("Selected devices: []")
            if self.current_device_name:
                print(f"Current Device: {self.current_device_name}")
            else:
                print("Current Device: None (measurements will be saved to sample folder)")
            print("")
            
            # Open measurement window with empty device list
            self.measuremnt_gui = MeasurementGUI(self.root, sample_type, section, selected_device_list, self)
            self.measurement_window = True
            # Register the measurement GUI to receive updates
            self.register_child_gui(self.measuremnt_gui)
        else:  # Yes - stay on Device Manager tab
            return
    
    def _on_measurement_window_closed(self) -> None:
        """Called when measurement window is closed - reset flags"""
        self.measurement_window = False
        # Remove from registry if it exists
        if hasattr(self, 'measuremnt_gui') and self.measuremnt_gui in self._child_guis:
            self._child_guis.remove(self.measuremnt_gui)
        self.measuremnt_gui = None
    
    def register_child_gui(self, child_gui: Any) -> None:
        """Register a child GUI to receive sample/device change notifications."""
        if child_gui not in self._child_guis:
            self._child_guis.append(child_gui)
    
    def unregister_child_gui(self, child_gui: Any) -> None:
        """Unregister a child GUI from receiving notifications."""
        if child_gui in self._child_guis:
            self._child_guis.remove(child_gui)
    
    def _notify_child_guis(self, change_type: str, **kwargs) -> None:
        """Notify all registered child GUIs of a change.
        
        Args:
            change_type: Type of change ('sample_type', 'section', 'device_name', 'device_selection')
            **kwargs: Additional data about the change
        """
        # Clean up any dead references
        self._child_guis = [
            gui for gui in self._child_guis 
            if gui is not None and (hasattr(gui, 'master') and gui.master.winfo_exists() if hasattr(gui, 'master') else True)
        ]
        
        # Notify all registered child GUIs
        for child_gui in self._child_guis:
            try:
                if hasattr(child_gui, 'on_sample_gui_change'):
                    child_gui.on_sample_gui_change(change_type, **kwargs)
            except Exception as e:
                print(f"Error notifying child GUI {child_gui}: {e}")
    
    def _show_help(self) -> None:
        """Display a help window with usage instructions."""
        help_win = tk.Toplevel(self.root)
        help_win.title("Sample GUI Guide")
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
        
        tk.Label(scrollable_frame, text="Sample GUI Guide", 
                font=("Segoe UI", 16, "bold"), bg="#f0f0f0", fg="#1565c0").pack(**pad)
        
        tk.Label(scrollable_frame, text="1. Overview", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame, 
                text="This is the main entry point for device selection and sample management.\n"
                      "It provides a visual interface to browse device maps, select devices to test,\n"
                      "control multiplexer routing, and launch measurement interfaces.",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="2. Getting Started", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Select multiplexer type and sample type from dropdowns\n"
                      "• Click on devices in the map to select them\n"
                      "• Use device selection panel to navigate devices\n"
                      "• Click 'Measure Selected Devices' to start measurements\n"
                      "• Use Quick Scan for rapid device testing",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="3. Features", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Visual Device Map: Click-to-select devices on image\n"
                      "• Device Status Tracking: Mark devices as working/failed/untested\n"
                      "• Multiplexer Control: Route signals to selected devices\n"
                      "• Quick Scan: Rapidly test multiple devices\n"
                      "• Device Manager: Organize and manage device information",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="4. Tabs", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame,
                text="• Device Selection: Main interface for selecting devices\n"
                      "• Device Manager: Manage device information and status\n"
                      "• Quick Scan Results: View results from quick scan tests",
                justify="left", bg="#f0f0f0").pack(**pad)
        
        tk.Label(scrollable_frame, text="Video Tutorial", font=("Segoe UI", 12, "bold"), 
                bg="#f0f0f0", fg="#d32f2f").pack(**pad)
        tk.Label(scrollable_frame,
                text="Video tutorials and additional resources will be added here.",
                justify="left", bg="#f0f0f0", fg="#666").pack(**pad)

    def open_measurement_window(self) -> None:
        """Open the measurement window. Checks device name first, then device selection."""
        # Check if window exists and is still valid
        if self.measurement_window and hasattr(self, 'measuremnt_gui') and self.measuremnt_gui:
            try:
                # Check if the window still exists
                if hasattr(self.measuremnt_gui, 'master') and self.measuremnt_gui.master.winfo_exists():
                    # Window exists, bring it to top
                    self.measuremnt_gui.bring_to_top()
                    return
                else:
                    # Window was destroyed, reset flags
                    self._on_measurement_window_closed()
            except (tk.TclError, AttributeError):
                # Window doesn't exist, reset flags
                self._on_measurement_window_closed()
        
        # Window doesn't exist, create a new one
        if not self.measurement_window:
            sample_type = self.sample_type_var.get()
            section = self.section_var.get()

            # FIRST: Check if device name is set
            if not self.current_device_name:
                # Switch to Device Manager tab first (make it visible)
                self.notebook.select(1)  # Device Manager tab is at index 1
                self.root.update_idletasks()  # Process pending display updates
                self.root.update()  # Force UI update to show the tab switch
                
                # Small delay to ensure tab is visible before showing dialog
                self.root.after(100, lambda: self._show_no_device_name_dialog())
                return

            # SECOND: Check if devices are selected
            selected_device_list = [self.device_list[i] for i in self.selected_indices]

            if not selected_device_list:
                # Switch to Device Manager tab first (make it visible)
                self.notebook.select(1)  # Device Manager tab is at index 1
                self.root.update_idletasks()  # Process pending display updates
                self.root.update()  # Force UI update to show the tab switch
                
                # Small delay to ensure tab is visible before showing dialog
                self.root.after(100, lambda: self._show_no_devices_dialog())
                return

            # Both device name and device selection are set - proceed with measurement
            self.change_relays()
            print("")
            print("Selected devices:")
            print([self.get_device_label(device) for device in selected_device_list])
            if self.current_device_name:
                print(f"Current Device: {self.current_device_name}")
            print("")
            
            # TODO: Pass device_name to MeasurementGUI for device-specific saving
            # For now, MeasurementGUI can access it via self.current_device_name
            self.measuremnt_gui = MeasurementGUI(self.root, sample_type, section, selected_device_list, self)
            self.measurement_window = True
            # Register the measurement GUI to receive updates
            self.register_child_gui(self.measuremnt_gui)
        else:
            self.measuremnt_gui.bring_to_top()
    
    def _show_no_device_name_dialog(self) -> None:
        """Show dialog when no device name is set (called after tab switch)."""
        response = messagebox.askyesnocancel(
            "No Device Name Set",
            "No device name is currently set. Measurements will be saved to the sample folder.\n\n"
            "Would you like to:\n"
            "• Yes: Stay on Device Manager to set a device name\n"
            "• No: Continue anyway without setting a device name\n"
            "• Cancel: Return to device selection",
            icon='question'
        )
        if response is None:  # Cancel
            self.notebook.select(0)  # Return to Device Selection tab
            return
        elif response is False:  # No - continue anyway without device name
            self.notebook.select(0)  # Return to Device Selection tab
            
            # Check if devices are selected
            selected_device_list = [self.device_list[i] for i in self.selected_indices]
            
            if not selected_device_list:
                # No devices selected either - show device selection dialog
                self.notebook.select(1)  # Go back to Device Manager
                self.root.update_idletasks()
                self.root.update()
                self.root.after(100, lambda: self._show_no_devices_dialog())
                return
            
            # Devices are selected, continue with measurement
            sample_type = self.sample_type_var.get()
            section = self.section_var.get()
            
            self.change_relays()
            print("")
            print("Selected devices:")
            print([self.get_device_label(device) for device in selected_device_list])
            print("Current Device: None (measurements will be saved to sample folder)")
            print("")
            
            # Open measurement window without device name
            self.measuremnt_gui = MeasurementGUI(self.root, sample_type, section, selected_device_list, self)
            self.measurement_window = True
            # Register the measurement GUI to receive updates
            self.register_child_gui(self.measuremnt_gui)
        else:  # Yes - stay on Device Manager tab to set device name
            return

    def update_info_box(self, event: Optional[Any] = None) -> None:
        selected_device = self.device_var.get()
        device_key = self.get_device_key_from_label(selected_device) if selected_device else None

        if device_key and device_key in self.device_list:
            idx = self.device_list.index(device_key)
            if idx != self.current_index:
                self.current_index = idx
            device_meta = self.device_mapping.get(device_key, {})
            section = device_meta.get("section")
            sample = device_meta.get("sample")
            if sample:
                self.sample_type_var.set(sample)
            if section:
                self.section_var.set(section)
            if hasattr(self, 'original_image'):
                try:
                    self.update_highlight(device_key)
                except Exception:
                    pass

        selected_sample = self.sample_type_var.get()
        selected_section = self.section_var.get()
        device_text = f"Current Device: {selected_sample} - {selected_section} - {selected_device}"
        self.info_box.config(text=device_text)
        
        # Notify child GUIs of section/device change
        self._notify_child_guis('section', section=selected_section, device=selected_device)

    def change_relays(self) -> None:
        """Change relays for the current device using MultiplexerManager"""
        current_device = self.device_list[self.current_index]

        # Check if current device is in selected devices
        label = self.get_device_label(current_device)

        if current_device not in self.selected_devices:
            self.log_terminal(f"Warning: Device {label} is not selected")
            response = messagebox.askyesno("Device Not Selected",
                                           f"Device {label} is not in the selected list. Continue anyway?")
            if not response:
                return

        # Use unified multiplexer manager interface
        if self.multiplexer_type == "Manual":
            # Manual mode: just log and update GUI state, no actual routing
            self.log_terminal(f"Manual mode: Device {label} selected (manually move probes to this device)", "INFO")
            # Update measurement window if open
            if self.measurement_window:
                self.measuremnt_gui.current_index = self.current_index
                self.measuremnt_gui.update_variables()
        elif self.mpx_manager is not None:
            self.log_terminal(f"Routing to {label} via {self.multiplexer_type}")
            success = self.mpx_manager.route_to_device(current_device, self.current_index)
            
            if success:
                self.log_terminal(f"Successfully routed to {label}")
            else:
                self.log_terminal(f"Failed to route to {label}")
            
            # Update measurement window if open
            if self.measurement_window:
                self.measuremnt_gui.current_index = self.current_index
                self.measuremnt_gui.update_variables()
        else:
            self.log_terminal("Multiplexer manager not initialized")
            print("Error: Multiplexer manager is None")

    def clear_canvas(self) -> None:
        self.canvas.delete("all")
        self.log_terminal("Canvas cleared")
        # Reload the image and selection highlights
        if hasattr(self, 'sample_type_var'):
            sample = self.sample_type_var.get()
            if sample:
                self.load_image(sample)

    def _pump_test_logs(self):
        """Transfer messages from worker queue to terminal in UI thread."""
        drained = False
        try:
            while True:
                msg = self.test_log_queue.get_nowait()
                drained = True
                self.log_terminal(msg)
        except queue.Empty:
            pass
        if self.tests_running:
            self.root.after(100, self._pump_test_logs)
        elif drained:
            # Final drain
            self.root.after(100, self._pump_test_logs)

    def start_automated_tests(self):
        if self.tests_running:
            messagebox.showinfo("Tests", "Automated tests are already running.")
            return
        selected_device_list = [self.device_list[i] for i in self.selected_indices]
        if not selected_device_list:
            messagebox.showwarning("Warning", "No devices selected for automated testing.")
            return
        if Keithley2400Controller is None:
            messagebox.showerror("Instrument", "Keithley2400Controller not available. Connect instrument and retry.")
            return

        self.tests_running = True
        self.abort_tests_flag = False
        self.test_log_queue.put("Starting automated tests...")
        self._pump_test_logs()

        worker = threading.Thread(target=self._run_automated_tests_worker, args=(selected_device_list,), daemon=True)
        worker.start()

    def stop_automated_tests(self):
        if self.tests_running:
            self.abort_tests_flag = True
            self.test_log_queue.put("Abort requested. Stopping after current step...")

    def _run_on_ui(self, func):
        """Run a callable on the Tk UI thread and wait for completion."""
        evt = threading.Event()
        def wrapper():
            try:
                func()
            finally:
                evt.set()
        self.root.after(0, wrapper)
        evt.wait()

    def _route_to_device_on_ui(self, device_name):
        # Set selection and route relays in UI thread
        if device_name in self.device_list:
            idx = self.device_list.index(device_name)
            self.current_index = idx
            self.device_var.set(self.get_device_label(device_name))
            self.update_highlight(device_name)
            self.change_relays()

    def open_preferences_dialog(self):
        # Minimal dialog to view/save thresholds (read-only preview for now)
        t = load_thresholds()
        info = (
            f"Probe: {t.probe_voltage_v} V for {t.probe_duration_s}s @ {t.probe_sample_hz} Hz\n"
            f"Working I threshold: {t.working_current_a} A\n"
            f"Forming steps: {t.forming_voltages_v}, comp={t.forming_compliance_a} A, cooldown={t.forming_cooldown_s}s\n"
            f"Hyst budget: {t.hyst_budget}, profiles: {len(t.hyst_profiles)}\n"
            f"Endurance cycles: {t.endurance_cycles}, pulse width: {t.pulse_width_s}s\n"
            f"Retention times: {t.retention_times_s}\n"
            f"Safety: Vmax={t.max_voltage_v} V, Imax={t.max_compliance_a} A\n"
        )
        messagebox.showinfo("Test Preferences (read-only preview)", info)

    def _run_automated_tests_worker(self, devices):
        try:
            inst = Keithley2400Controller()
            if not getattr(inst, 'device', None):
                self.test_log_queue.put("Instrument not connected. Aborting tests.")
                return
            driver = MeasurementDriver(inst, abort_flag=lambda: self.abort_tests_flag)
            runner = TestRunner(driver, Thresholds())

            results_dir = BASE_DIR / "results"
            results_dir.mkdir(exist_ok=True)

            for device in devices:
                if self.abort_tests_flag:
                    break
                self.test_log_queue.put(f"Routing to device {device}...")
                self._run_on_ui(lambda d=device: self._route_to_device_on_ui(d))
                if self.abort_tests_flag:
                    break
                self.test_log_queue.put(f"Probing and testing {device}...")

                # Live plotting callback
                on_sample = None
                try:
                    if self.live_plot_var.get() and hasattr(self, 'measuremnt_gui'):
                        plotter = getattr(self.measuremnt_gui, 'plotter', None)
                        if plotter and hasattr(plotter, 'thread_safe'):
                            on_sample = plotter.thread_safe.callback_sink(device)
                except Exception:
                    on_sample = None

                # Patch callbacks for this device if available
                if on_sample is not None:
                    orig_dc_hold = driver.dc_hold
                    orig_sweep = driver.triangle_sweep
                    def dc_hold_cb(voltage_v, duration_s, sample_hz, compliance_a):
                        return orig_dc_hold(voltage_v, duration_s, sample_hz, compliance_a, on_sample=on_sample)
                    def triangle_cb(v_min, v_max, step_v, dwell_s, cycles, compliance_a):
                        return orig_sweep(v_min, v_max, step_v, dwell_s, cycles, compliance_a, on_sample=on_sample)
                    driver.dc_hold = dc_hold_cb  # type: ignore
                    driver.triangle_sweep = triangle_cb  # type: ignore

                outcome, artifacts = runner.run_device(device)
                # Persist summary
                out_path = results_dir / f"{device}_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                try:
                    with out_path.open('w', encoding='utf-8') as f:
                        json.dump(outcome.__dict__, f, indent=2)
                except Exception as e:
                    self.test_log_queue.put(f"Failed to save results for {device}: {e}")
                # Persist best IV curve if available
                try:
                    best = artifacts.get("best_iv")
                    if best:
                        csv_path = results_dir / f"{device}_best_iv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        with csv_path.open('w', encoding='utf-8') as f:
                            f.write("V,I,t\n")
                            for v, i, t in zip(best.voltage, best.current, best.timestamps):
                                f.write(f"{v},{i},{t}\n")
                except Exception as e:
                    self.test_log_queue.put(f"Failed to save best IV for {device}: {e}")
                # Append to summary CSV
                try:
                    import csv
                    summary_path = results_dir / "summary.csv"
                    write_header = not summary_path.exists()
                    with summary_path.open('a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        if write_header:
                            writer.writerow(["device_id","status","formed","probe_current_a","hyst_area",
                                             "endurance_on_off","retention_alpha","timestamp"])
                        writer.writerow([
                            device,
                            "WORKING" if outcome.is_working else "NON-WORKING",
                            outcome.formed,
                            f"{outcome.probe_current_a:.3e}",
                            f"{(outcome.hyst_area or 0):.3e}",
                            f"{(outcome.endurance_on_off or 0):.3f}",
                            f"{(outcome.retention_alpha or 0):.3f}",
                            datetime.now().isoformat(timespec='seconds')
                        ])
                except Exception as e:
                    self.test_log_queue.put(f"Failed to update summary.csv for {device}: {e}")
                # Log brief summary
                status = "WORKING" if outcome.is_working else "NON-WORKING"
                formed = " (formed)" if outcome.formed else ""
                extra = []
                if outcome.hyst_area is not None:
                    extra.append(f"hyst_area={outcome.hyst_area:.2e}")
                if outcome.endurance_on_off is not None:
                    extra.append(f"end_on/off~{outcome.endurance_on_off:.2f}")
                if outcome.retention_alpha is not None:
                    extra.append(f"ret_alpha~{outcome.retention_alpha:.2f}")
                extra_str = (", " + ", ".join(extra)) if extra else ""
                self.test_log_queue.put(
                    f"{device}: {status}{formed}, I_probe={outcome.probe_current_a:.2e} A{extra_str}")

            self.test_log_queue.put("Automated tests completed.")
        except Exception as e:
            self.test_log_queue.put(f"Error during automated tests: {e}")
        finally:
            self.tests_running = False

    def Change_image(self, sample):
        self.log_terminal("change image sample")

    def get_selected_devices(self):
        """Return list of currently selected devices"""
        return [self.device_list[i] for i in self.selected_indices]

    def cycle_through_selected_devices(self):
        """Generator to cycle through only selected devices"""
        if not self.selected_indices:
            self.log_terminal("No devices selected for cycling")
            return

        while True:
            for idx in self.selected_indices:
                device = self.device_list[idx]
                self.current_index = idx
                label = self.get_device_label(device)
                self.device_var.set(label)
                self.info_box.config(text=f"Current Device: {label}")
                self.info_box.config(text=f"Current Device: {label}")
                self.update_highlight(device)
                self.change_relays()
                yield device


# Main execution
if __name__ == "__main__":
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
