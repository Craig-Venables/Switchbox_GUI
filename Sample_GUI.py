"""Sample GUI

Tkinter-based interface to browse/select devices on an image map, manage
device selections, control multiplexer routing, and launch the
`MeasurementGUI` for measurements on the selected subset.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import json
import math
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
import time
import random

from Measurement_GUI import MeasurementGUI
from Equipment.Multiplexers.Multiplexer_10_OUT.Multiplexer_Class import MultiplexerController

# Import new multiplexer manager
from Equipment.multiplexer_manager import MultiplexerManager

try:
    from Equipment.SMU_AND_PMU.Keithley2400 import Keithley2400Controller
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

BASE_DIR: Path = Path(__file__).resolve().parent

# Load sample configuration from JSON file
sample_config = {
    "Cross_bar": {
        "sections": {"A": True, "B": True, "C": False, "D": True, "E": True, "F": False, "G": True, "H": True,
                     "I": True, "J": True, "K": True, "L": True},
        "devices": [str(i) for i in range(1, 11)]},
    "Device_Array_10": {
        "sections": {"A": True},
        "devices": [str(i) for i in range(1, 11)]}}

multiplexer_types = {'Pyswitchbox': {}, 'Electronic_Mpx': {}}


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


class SampleGUI:
    """Device selection and routing GUI."""
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.root.title("Device Viewer")
        self.root.geometry("1200x700")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Primary notebook layout
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.device_manager_frame = ttk.Frame(self.notebook)
        self.device_manager_frame.grid_columnconfigure(0, weight=0)
        self.device_manager_frame.grid_columnconfigure(1, weight=0)
        self.device_manager_frame.grid_columnconfigure(2, weight=0)
        self.device_manager_frame.grid_columnconfigure(3, weight=1)
        self.device_manager_frame.grid_rowconfigure(7, weight=1)
        self.device_manager_frame.grid_rowconfigure(8, weight=0)

        self.quick_scan_frame = ttk.Frame(self.notebook)
        self.quick_scan_frame.grid_columnconfigure(0, weight=1)
        self.quick_scan_frame.grid_rowconfigure(0, weight=1)

        self.notebook.add(self.device_manager_frame, text="Device Manager")
        self.notebook.add(self.quick_scan_frame, text="Quick Scan")

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

        # Flags
        self.pyswitchbox = True
        self.Electronic_Mpx = False
        self.measurement_window: bool = False

        # print(self.device_maps_list)
        # print(self.device_list)

        # initialise switchbox
        # self.switchbox = pySwitchbox.Switchbox()
        
        # Initialize multiplexer manager (will be set properly in update_multiplexer)
        self.mpx_manager = None

        # Multiplexer Type Dropdown
        tk.Label(self.device_manager_frame, text="Multiplexer").grid(row=0, column=0, sticky='w')
        self.Multiplexer_type_var = tk.StringVar()
        self.Multiplexer_dropdown = ttk.Combobox(self.device_manager_frame, textvariable=self.Multiplexer_type_var,
                                                 values=list(multiplexer_types.keys()))
        self.Multiplexer_dropdown.grid(row=0, column=1)
        self.Multiplexer_dropdown.bind("<<ComboboxSelected>>", self.update_multiplexer)
        # Set default multiplexer selection
        try:
            self.Multiplexer_type_var.set("Pyswitchbox")
            # Optionally initialise behavior for default
            self.update_multiplexer(None)
        except Exception:
            pass

        # Sample Type Dropdown
        tk.Label(self.device_manager_frame, text="Sample type").grid(row=1, column=0, sticky='w')
        self.sample_type_var = tk.StringVar()
        self.sample_dropdown = ttk.Combobox(self.device_manager_frame, textvariable=self.sample_type_var, values=list(sample_config.keys()))
        self.sample_dropdown.grid(row=1, column=1)
        self.sample_dropdown.bind("<<ComboboxSelected>>", self.update_dropdowns)
        

        # Section Dropdown
        tk.Label(self.device_manager_frame, text="Section").grid(row=2, column=0, sticky='w')
        self.section_var = tk.StringVar()
        self.section_dropdown = ttk.Combobox(self.device_manager_frame, textvariable=self.section_var)
        self.section_dropdown.grid(row=2, column=1)
        # Section Entry
        # tk.Label(root, text="Section").grid(row=2, column=0, sticky='w')
        # self.section_var = tk.StringVar()
        # self.section_entry = tk.Entry(root, textvariable=self.section_var)
        # self.section_entry.grid(row=2, column=1)

        # Device Number Dropdown
        tk.Label(self.device_manager_frame, text="Device Number").grid(row=3, column=0, sticky='w')
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(self.device_manager_frame, textvariable=self.device_var)
        self.device_dropdown.grid(row=3, column=1)

        # Information Box
        self.info_box = tk.Label(self.device_manager_frame, text="Current Device: None", relief=tk.SUNKEN, width=30)
        self.info_box.grid(row=4, column=0, columnspan=2, pady=10)

        # Navigation Buttons
        self.prev_button = tk.Button(self.device_manager_frame, text="<", command=self.prev_device)
        self.prev_button.grid(row=5, column=0, pady=2)

        self.clear_button = tk.Button(self.device_manager_frame, text="Clear", command=self.clear_canvas)
        self.clear_button.grid(row=6, column=1, pady=2)

        self.change_button = tk.Button(self.device_manager_frame, text="Go", command=self.change_relays)
        self.change_button.grid(row=6, column=0, pady=2)

        self.next_button = tk.Button(self.device_manager_frame, text=">", command=self.next_device)
        self.next_button.grid(row=5, column=1, pady=2)

        # Canvas for Image
        self.canvas = tk.Canvas(self.device_manager_frame, width=400, height=400, bg="white", highlightbackground="black")
        self.canvas.grid(row=0, column=2, rowspan=5, padx=10)
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<Control-Button-1>", self.canvas_ctrl_click)  # Ctrl+Click for selection

        # Device Selection Frame
        self.create_device_selection_frame()

        # Terminal Output
        self.terminal_output = tk.Text(self.device_manager_frame, height=5, width=80, state=tk.DISABLED)
        self.terminal_output.grid(row=7, column=0, columnspan=4, pady=10, sticky="nsew")

        # Measurement Button
        self.measure_button = tk.Button(self.device_manager_frame, text="Measure Devices", command=self.open_measurement_window)
        self.measure_button.grid(row=8, column=0, columnspan=2, pady=10)

        # Quick scan configuration defaults
        self.quick_scan_min_current = 1e-10
        self.quick_scan_max_current = 1e-6
        self.quick_scan_running = False
        self.quick_scan_abort = threading.Event()
        self.quick_scan_thread: Optional[threading.Thread] = None
        self.quick_scan_metadata: Dict[str, Any] = {}

        # Initialize quick scan tab UI
        self._init_quick_scan_ui()

        # Bind section and device selection to update_info_box
        self.section_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)
        self.device_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)

        # Automated Tests controls moved to Measurement GUI
        
        
        # Set default sample selection and apply
        try:
            # Use the key name as defined in sample_config
            self.sample_type_var.set("Cross_bar")
            self.update_dropdowns(None)
        except Exception:
            pass
        # Placeholder for clicked points
        # self.electrode_points = []

    def _init_quick_scan_ui(self) -> None:
        """Set up widgets for the Quick Scan tab."""
        control_frame = ttk.Frame(self.quick_scan_frame, padding=(10, 10))
        control_frame.grid(row=0, column=0, sticky="ew")
        control_frame.columnconfigure(8, weight=1)

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

        self.quick_scan_run_button = ttk.Button(control_frame, text="Run Scan", command=self.start_quick_scan)
        self.quick_scan_run_button.grid(row=0, column=4, padx=5)

        self.quick_scan_stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_quick_scan, state=tk.DISABLED)
        self.quick_scan_stop_button.grid(row=0, column=5, padx=5)

        self.quick_scan_save_button = ttk.Button(control_frame, text="Save", command=self.save_quick_scan_results, state=tk.DISABLED)
        self.quick_scan_save_button.grid(row=0, column=6, padx=5)

        self.quick_scan_load_button = ttk.Button(control_frame, text="Load", command=self.load_quick_scan_results)
        self.quick_scan_load_button.grid(row=0, column=7, padx=5, sticky="w")

        self.quick_scan_status = ttk.Label(control_frame, text="Status: Idle")
        self.quick_scan_status.grid(row=0, column=8, padx=(10, 0), sticky="w")

        canvas_frame = ttk.Frame(self.quick_scan_frame, padding=(10, 0, 10, 10))
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        self.quick_scan_canvas = tk.Canvas(
            canvas_frame,
            width=400,
            height=400,
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

        log_frame = ttk.Frame(self.quick_scan_frame, padding=(10, 0, 10, 10))
        log_frame.grid(row=2, column=0, sticky="nsew")
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
        if self.quick_scan_canvas is None:
            return
        self.quick_scan_canvas.delete("all")
        self.quick_scan_base_image = image.copy()
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
        self._draw_quick_scan_overlay_on(self.quick_scan_canvas if hasattr(self, "quick_scan_canvas") else None, "overlay")
        self._draw_quick_scan_overlay_on(self.canvas if hasattr(self, "canvas") else None, "quick_scan_overlay")

    def _draw_quick_scan_overlay_on(self, target_canvas: Optional[tk.Canvas], tag: str) -> None:
        """Draw quick scan overlay rectangles on the provided canvas."""
        if target_canvas is None:
            return
        target_canvas.delete(tag)
        if not getattr(self, "original_image", None):
            return
        orig_width, orig_height = self.original_image.size
        scale_x = orig_width / 400
        scale_y = orig_height / 400

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

    def _finalize_quick_scan(self, aborted: bool) -> None:
        self.quick_scan_running = False
        status = "Aborted" if aborted else "Complete"
        self._set_quick_scan_status(status)
        self._set_quick_scan_buttons(running=False)
        if self.quick_scan_results:
            self.quick_scan_save_button.config(state=tk.NORMAL)
        self._log_quick_scan(f"Quick scan {status.lower()}.")

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
        safe_sample = sample.replace(" ", "_")
        return BASE_DIR / "Data_maps" / safe_sample

    def create_device_selection_frame(self) -> None:
        """Create a frame with checkboxes for device selection."""
        # Main frame for device selection
        selection_frame = tk.LabelFrame(self.device_manager_frame, text="Device Selection", padx=5, pady=5)
        selection_frame.grid(row=0, column=3, rowspan=6, padx=10, sticky='nsew')
        selection_frame.grid_columnconfigure(0, weight=1)
        selection_frame.grid_rowconfigure(1, weight=1)

        # Buttons frame
        button_frame = tk.Frame(selection_frame)
        button_frame.pack(fill='x', pady=(0, 5))

        tk.Button(button_frame, text="Select All", command=self.select_all_devices).pack(side='left', padx=2)
        tk.Button(button_frame, text="Deselect All", command=self.deselect_all_devices).pack(side='left', padx=2)
        tk.Button(button_frame, text="Invert", command=self.invert_selection).pack(side='left', padx=2)

        # Scrollable frame for checkboxes
        canvas = tk.Canvas(selection_frame, width=150, height=300)
        scrollbar = ttk.Scrollbar(selection_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.device_checkboxes: Dict[str, tk.Checkbutton] = {}
        self.checkbox_vars: Dict[str, tk.BooleanVar] = {}

        # Status label
        self.selection_status = tk.Label(selection_frame, text="Selected: 0/0")
        self.selection_status.pack(pady=5)

        self.scrollable_frame = scrollable_frame

    def update_device_checkboxes(self) -> None:
        """Update the device checkboxes based on current device list."""
        # Clear existing checkboxes
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.device_checkboxes.clear()
        self.checkbox_vars.clear()

        # Create new checkboxes
        for i, device in enumerate(self.device_list):
            label = self.get_device_label(device)
            var = tk.BooleanVar(value=True)  # Default to selected
            cb = tk.Checkbutton(self.scrollable_frame, text=label, variable=var,
                                command=self.update_selected_devices)
            cb.grid(row=i, column=0, sticky='w')

            self.device_checkboxes[device] = cb
            self.checkbox_vars[device] = var
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

        # Log selection
        friendly_selected = [self.get_device_label(self.device_list[idx]) for idx in self.selected_indices]
        selection_text = ", ".join(friendly_selected) if friendly_selected else "None"
        self.log_terminal(f"Selected devices: {selection_text}")

    def update_canvas_selection_highlights(self) -> None:
        """Update visual indicators on canvas for selected devices"""
        # Remove existing selection highlights
        self.canvas.delete("selection")

        if hasattr(self, 'original_image'):
            orig_width, orig_height = self.original_image.size
            scale_x = orig_width / 400
            scale_y = orig_height / 400

            for device, bounds in self.device_mapping.items():
                if device in self.selected_devices:
                    x_min = bounds["x_min"] / scale_x
                    x_max = bounds["x_max"] / scale_x
                    y_min = bounds["y_min"] / scale_y
                    y_max = bounds["y_max"] / scale_y

                    # Draw green rectangle for selected devices
                    self.canvas.create_rectangle(
                        x_min, y_min, x_max, y_max,
                        outline="green", width=1, tags="selection"
                    )

    def canvas_ctrl_click(self, event: Any) -> None:
        """Handle Ctrl+Click for device selection toggle"""
        if hasattr(self, 'original_image'):
            orig_width, orig_height = self.original_image.size
            scale_x = orig_width / 400
            scale_y = orig_height / 400

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

    def update_multiplexer(self, event: Optional[Any]) -> None:
        self.multiplexer_type = self.Multiplexer_type_var.get()
        print("Multiplexer set to:", self.multiplexer_type)
        
        # Use new MultiplexerManager to create appropriate adapter
        try:
            if self.multiplexer_type == "Pyswitchbox":
                self.mpx_manager = MultiplexerManager.create(
                    "Pyswitchbox",
                    pin_mapping=pin_mapping
                )
                print("Initiated Pyswitchbox via MultiplexerManager")
            elif self.multiplexer_type == "Electronic_Mpx":
                # Try to create with real hardware, fall back to simulation if needed
                try:
                    self.mpx = MultiplexerController(simulation_mode=False)
                    print("Initiated Electronic_Mpx with real hardware")
                except Exception as e:
                    print(f"Hardware not available, using simulation mode: {e}")
                    self.mpx = MultiplexerController(simulation_mode=True)
                    print("Initiated Electronic_Mpx in simulation mode")
                
                self.mpx_manager = MultiplexerManager.create(
                    "Electronic_Mpx",
                    controller=self.mpx
                )
                print("Initiated Electronic_Mpx via MultiplexerManager")
            else:
                print("Unknown multiplexer type")
        except Exception as e:
            print(f"Error initializing multiplexer: {e}")

    def load_image(self, sample: str) -> None:
        """ Load image into canvas set up to add others later simply """
        image_path: Optional[Path] = None
        if sample == 'Cross_bar':
            image_path = BASE_DIR / "Helpers" / "Sample_Infomation" / "memristor.png"
        elif sample == 'Device_Array_10':
            image_path = BASE_DIR / "Helpers" / "Sample_Infomation" / "Multiplexer_10_OUT.jpg"

        if image_path is None or not image_path.exists():
            self.original_image = None
            self.tk_img = None
            self.canvas.delete("all")
            self.quick_scan_canvas.delete("all")
            return

        self.original_image = Image.open(image_path)
        img = self.original_image.resize((400, 400))
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        self._update_quick_scan_background(img)

        # Redraw selection highlights
        self.update_canvas_selection_highlights()
        self._redraw_quick_scan_overlay()

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
        print("Sample chosen:", sample)
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

            # Call do_something when sample changes
            self.load_image(sample)
            self.device = self.device_var.get()
            if not self._load_quick_scan_for_sample(sample, silent=True):
                self.quick_scan_results.clear()
                self._redraw_quick_scan_overlay()
                self.quick_scan_save_button.config(state=tk.DISABLED)
                self._set_quick_scan_status("Idle")

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
        mapname = self.current_map_name
        #print(mapname)
        #print(self.current_map_map)

        orig_width, orig_height = self.original_image.size
        scaled_width, scaled_height = 400, 400
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

    def update_highlight(self, device: str) -> None:
        # Clear any existing highlights
        self.canvas.delete("highlight")

        # Get the device bounds
        bounds = self.device_mapping.get(device, None)
        if bounds:
            orig_width, orig_height = self.original_image.size
            scaled_width, scaled_height = 400, 400
            # Compute the scaling factors
            scale_x = orig_width / scaled_width
            scale_y = orig_height / scaled_height

            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y

            # Draw a new rectangle
            self.canvas.create_rectangle(x_min, y_min, x_max, y_max, outline="#009dff", width=3, tags="highlight")

    def open_measurement_window(self) -> None:
        if not self.measurement_window:
            sample_type = self.sample_type_var.get()
            section = self.section_var.get()

            # Pass only selected devices to measurement window
            selected_device_list = [self.device_list[i] for i in self.selected_indices]

            if not selected_device_list:
                messagebox.showwarning("Warning", "No devices selected for measurement.")
                return

            self.change_relays()
            print("")
            print("Selected devices:")
            print([self.get_device_label(device) for device in selected_device_list])
            print("")
            self.measuremnt_gui = MeasurementGUI(self.root, sample_type, section, selected_device_list, self)
            self.measurement_window = True
        else:
            self.measuremnt_gui.bring_to_top()

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
        if self.mpx_manager is not None:
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

    def log_terminal(self, message: str) -> None:
        self.terminal_output.config(state=tk.NORMAL)
        self.terminal_output.insert(tk.END, message + "\n")
        self.terminal_output.config(state=tk.DISABLED)
        self.terminal_output.see(tk.END)

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
