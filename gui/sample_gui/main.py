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

from gui.sample_gui.config import (
    BASE_DIR,
    device_maps,
    get_or_build_device_map,
    load_device_mapping,
    pin_mapping,
    resolve_default_save_root,
    sample_config,
)
from gui.sample_gui.quick_scan_controller import QuickScanController
from gui.sample_gui.device_manager_controller import DeviceManagerController
from gui.sample_gui.terminal_log_controller import TerminalLogController
from gui.sample_gui.device_status_controller import DeviceStatusController
from gui.sample_gui.telegram_controller import TelegramController
from gui.sample_gui.routing_controller import RoutingController
from gui.sample_gui.selection_controller import SelectionController
from gui.sample_gui.status_store import StatusStore


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
        self.multiplexer_type: str = "Manual"
        self.current_device_map: str = "Cross_bar"
        self.pyswitchbox: bool = False
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

        # Domain controllers (logic extracted from this orchestrator)
        self.status_store = StatusStore(self)
        self.selection = SelectionController(self)
        self.routing = RoutingController(self)
        self.quick_scan_ctrl = QuickScanController(self)
        self.device_status_ctrl = DeviceStatusController(self)
        self.device_mgr = DeviceManagerController(self)
        self.terminal_log = TerminalLogController(self)
        self.telegram_ctrl = TelegramController(self)
        self._load_telegram_bots()

        # =========================
        # TOP CONTROL BAR
        # =========================
        from gui.sample_gui.ui import create_top_control_bar
        create_top_control_bar(self)

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
        from gui.sample_gui.ui import (
            create_canvas_section,
            create_device_selection_panel,
            create_terminal_log,
            create_status_bar,
            create_device_manager_ui,
            create_quick_scan_ui,
        )
        create_device_manager_ui(self)
        create_canvas_section(self)
        create_device_selection_panel(self)
        create_terminal_log(self)
        create_quick_scan_ui(self)
        create_status_bar(self)

        # =========================
        # INITIALIZATION
        # =========================
        # Initialize original_image to None to prevent AttributeError
        self.original_image = None
        self.tk_img = None
        
        # Set default values WITHOUT triggering callbacks yet
        self.Multiplexer_type_var.set("Manual")
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

    def _update_quick_scan_background(self, image: Image.Image) -> None:
        self.quick_scan_ctrl.update_background(image)

    def _lerp_current(self, ratio: float) -> float:
        """Return a current value between min and max using logarithmic interpolation."""
        ratio_clamped = max(0.0, min(1.0, ratio))
        min_i = max(self.quick_scan_min_current, 1e-20)
        max_i = max(self.quick_scan_max_current, min_i * 10)
        log_min = math.log10(min_i)
        log_max = math.log10(max_i)
        return 10 ** (log_min + ratio_clamped * (log_max - log_min))

    def _current_to_color(self, current_a: float) -> str:
        return self.quick_scan_ctrl.current_to_color(current_a)

    def _redraw_quick_scan_overlay(self) -> None:
        self.quick_scan_ctrl.redraw_overlay()

    def _draw_quick_scan_overlay_on(self, target_canvas: Optional[tk.Canvas], tag: str,
                                    canvas_width: int, canvas_height: int) -> None:
        self.quick_scan_ctrl._draw_quick_scan_overlay_on(target_canvas, tag)

    def _draw_status_overlay_on(self, target_canvas: Optional[tk.Canvas], tag: str,
                                canvas_width: int, canvas_height: int) -> None:
        self.quick_scan_ctrl._draw_status_overlay_on(target_canvas, tag)

    def start_quick_scan(self) -> None:
        self.quick_scan_ctrl.start()

    def stop_quick_scan(self) -> None:
        self.quick_scan_ctrl.stop()

    def _quick_scan_worker(self, voltage: float, settle_time: float) -> None:
        self.quick_scan_ctrl._worker(voltage, settle_time)

    def _measure_device_current(self, controller: "Keithley2400Controller", voltage: float) -> Optional[float]:
        return self.quick_scan_ctrl._measure_device_current(controller, voltage)

    def _simulate_quick_scan_current(self, device: str, voltage: float) -> float:
        return self.quick_scan_ctrl._simulate_current(device, voltage)

    def _highlight_quick_scan_device(self, device: str, idx: int) -> None:
        self.quick_scan_ctrl._highlight_device(device, idx)

    def _store_quick_scan_result(self, device: str, current: Optional[float]) -> None:
        self.quick_scan_ctrl._store_result(device, current)

    def _load_telegram_bots(self) -> None:
        self.telegram_ctrl.load_bots()

    def _update_telegram_bot(self) -> None:
        self.telegram_ctrl.update_bot()

    def _capture_canvas_image(self) -> Optional[Path]:
        return self.telegram_ctrl.capture_canvas_image()

    def _send_telegram_notification(self, aborted: bool) -> None:
        self.telegram_ctrl.send_quick_scan_notification(aborted)

    def _finalize_quick_scan(self, aborted: bool) -> None:
        self.quick_scan_ctrl._finalize(aborted)

    def _set_quick_scan_buttons(self, running: bool) -> None:
        self.quick_scan_ctrl._set_buttons(running)

    def _set_quick_scan_status(self, text: str) -> None:
        self.quick_scan_ctrl._set_status(text)

    def _log_quick_scan(self, message: str) -> None:
        self.quick_scan_ctrl._log(message)

    def _format_current(self, current: Optional[float]) -> str:
        return QuickScanController._format_current(current)

    def save_quick_scan_results(self) -> None:
        self.quick_scan_ctrl.save_results()

    def load_quick_scan_results(self) -> None:
        self.quick_scan_ctrl.load_results()

    def _load_quick_scan_for_sample(self, sample: str, silent: bool = True) -> bool:
        return self.quick_scan_ctrl.load_for_sample(sample, silent=silent)

    def _get_quick_scan_storage_dir(self, sample: str) -> Path:
        return self.status_store.get_quick_scan_storage_dir(sample)

    def update_device_checkboxes(self) -> None:
        self.selection.update_device_checkboxes()

    def select_all_devices(self) -> None:
        self.selection.select_all_devices()

    def deselect_all_devices(self) -> None:
        self.selection.deselect_all_devices()

    def invert_selection(self) -> None:
        self.selection.invert_selection()

    def update_selected_devices(self) -> None:
        self.selection.update_selected_devices()

    def _update_status_bar(self) -> None:
        self.selection._update_status_bar()

    def update_canvas_selection_highlights(self) -> None:
        self.selection.update_canvas_selection_highlights()

    def canvas_ctrl_click(self, event: Any) -> None:
        self.selection.canvas_ctrl_click(event)

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
        return DeviceStatusController.status_color(status)

    def show_device_status_menu(self, event: Any, device: str) -> None:
        self.device_status_ctrl.show_menu(event, device)

    def mark_selected_devices(self, status: str) -> None:
        self.device_status_ctrl.mark_selected(status)

    def mark_device_status(self, device: str, status: Optional[str], quick: bool = True) -> None:
        self.device_status_ctrl.mark_device(device, status, quick=quick)

    def _update_device_status(self, device: str, manual_status: str, notes: str = "") -> None:
        self.device_status_ctrl.update_device(device, manual_status, notes=notes)

    def show_device_status_info(self, device: str) -> None:
        self.device_status_ctrl.show_info(device)

    def apply_threshold_to_undefined(self) -> None:
        self.device_status_ctrl.apply_threshold_to_undefined()

    def _save_device_status(self) -> None:
        self.status_store.save_device_status()

    def _save_device_status_excel(self, path: Path) -> None:
        self.status_store.save_device_status_excel(path)

    def _load_device_status(self) -> None:
        self.status_store.load_device_status()

    def export_device_status_excel(self) -> None:
        self.device_status_ctrl.export_excel()

    # ==========================
    # DEVICE MANAGEMENT
    # ==========================

    def get_device_folder(self, device_name: Optional[str] = None) -> Path:
        return self.device_mgr.get_folder(device_name)

    def set_current_device(self) -> None:
        self.device_mgr.set_current_device()

    def clear_current_device(self) -> None:
        self.device_mgr.clear_current_device()

    def save_device_info(self) -> None:
        self.device_mgr.save_device_info()

    def load_selected_device(self) -> None:
        self.device_mgr.load_selected_device()

    def load_device(self, device_name: str) -> None:
        self.device_mgr.load_device(device_name)

    def refresh_device_list(self) -> None:
        self.device_mgr.refresh_device_list()

    def update_device_info_display(self) -> None:
        self.device_mgr.update_info_display()

    # ==========================
    # TERMINAL LOG MANAGEMENT
    # ==========================

    def log_terminal(self, message: str, level: str = "INFO") -> None:
        self.terminal_log.log(message, level)

    def _apply_terminal_filter(self) -> None:
        self.terminal_log.apply_filter()

    def clear_terminal(self) -> None:
        self.terminal_log.clear()

    def export_terminal_log(self) -> None:
        self.terminal_log.export()

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
        self.routing.update_multiplexer(event)

    def load_image(self, sample: str) -> None:
        """Load image into canvas set up to add others later simply."""
        image_path: Optional[Path] = None
        if sample == 'Cross_bar':
            image_path = BASE_DIR / "resources" / "sample_information" / "memristor.png"
        elif sample == 'Device_Array_10':
            image_path = BASE_DIR / "resources" / "sample_information" / "Multiplexer_10_OUT.jpg"
        elif sample == '15x15mm':
            image_path = BASE_DIR / "resources" / "sample_information" / "15mmx15mm.JPG"
        elif sample == 'Generic_Grid':
            # Placeholder image: blank canvas with light grid and device cells
            mapping = get_or_build_device_map(sample)
            self.original_image = Image.new("RGB", (600, 500), "white")
            draw = ImageDraw.Draw(self.original_image)
            # Draw faint device rectangles and grid
            for bounds in mapping.values():
                x_min = bounds.get("x_min", 0)
                y_min = bounds.get("y_min", 0)
                x_max = bounds.get("x_max", 600)
                y_max = bounds.get("y_max", 500)
                draw.rectangle([x_min, y_min, x_max, y_max], outline="#cccccc", width=1)
            img = self.original_image
            try:
                self.tk_img = ImageTk.PhotoImage(img)
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
                self.log_terminal(f"Loaded generic grid for {sample}", "SUCCESS")
                if hasattr(self, 'quick_scan_canvas'):
                    self._update_quick_scan_background(img)
                self.update_canvas_selection_highlights()
                self._redraw_quick_scan_overlay()
            except Exception as e:
                self.log_terminal(f"Error loading generic grid: {e}", "ERROR")
                self.original_image = None
                self.tk_img = None
            return

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
        # Use get_or_build_device_map so Generic_Grid and other config-only samples work
        mapping = get_or_build_device_map(current_device_map)
        self.current_map_name = current_device_map
        self.device_mapping = mapping
        self.current_map_map = mapping
        self.device_maps_list = list(device_maps.keys())
        self.device_list = list(mapping.keys())
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
        if sample == "Generic_Grid":
            self.log_terminal("Generic_Grid: use Manual multiplexer; Quick Scan is for multiplexed samples only.", "INFO")

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
        self.routing.change_relays()

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
