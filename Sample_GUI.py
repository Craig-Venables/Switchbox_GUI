"""Sample GUI

Tkinter-based interface to browse/select devices on an image map, manage
device selections, control multiplexer routing, and launch the
`MeasurementGUI` for measurements on the selected subset.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import json
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

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
    "Multiplexer_10_OUT": {
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
        self.root.geometry("1000x650")

        # Defaults
        self.multiplexer_type: str = "Pyswitchbox"
        self.current_device_map: str = "Cross_bar"
        self.pyswitchbox: bool = True
        self.Electronic_Mpx: bool = False
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
        tk.Label(root, text="Multiplexer").grid(row=0, column=0, sticky='w')
        self.Multiplexer_type_var = tk.StringVar()
        self.Multiplexer_dropdown = ttk.Combobox(root, textvariable=self.Multiplexer_type_var,
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
        tk.Label(root, text="Sample type").grid(row=1, column=0, sticky='w')
        self.sample_type_var = tk.StringVar()
        self.sample_dropdown = ttk.Combobox(root, textvariable=self.sample_type_var, values=list(sample_config.keys()))
        self.sample_dropdown.grid(row=1, column=1)
        self.sample_dropdown.bind("<<ComboboxSelected>>", self.update_dropdowns)
        

        # Section Dropdown
        tk.Label(root, text="Section").grid(row=2, column=0, sticky='w')
        self.section_var = tk.StringVar()
        self.section_dropdown = ttk.Combobox(root, textvariable=self.section_var)
        self.section_dropdown.grid(row=2, column=1)
        # Section Entry
        # tk.Label(root, text="Section").grid(row=2, column=0, sticky='w')
        # self.section_var = tk.StringVar()
        # self.section_entry = tk.Entry(root, textvariable=self.section_var)
        # self.section_entry.grid(row=2, column=1)

        # Device Number Dropdown
        tk.Label(root, text="Device Number").grid(row=3, column=0, sticky='w')
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(root, textvariable=self.device_var)
        self.device_dropdown.grid(row=3, column=1)

        # Information Box
        self.info_box = tk.Label(root, text="Current Device: None", relief=tk.SUNKEN, width=30)
        self.info_box.grid(row=4, column=0, columnspan=2, pady=10)

        # Navigation Buttons
        self.prev_button = tk.Button(root, text="<", command=self.prev_device)
        self.prev_button.grid(row=5, column=0, pady=2)

        self.clear_button = tk.Button(root, text="Clear", command=self.clear_canvas)
        self.clear_button.grid(row=6, column=1, pady=2)

        self.change_button = tk.Button(root, text="Go", command=self.change_relays)
        self.change_button.grid(row=6, column=0, pady=2)

        self.next_button = tk.Button(root, text=">", command=self.next_device)
        self.next_button.grid(row=5, column=1, pady=2)

        # Canvas for Image
        self.canvas = tk.Canvas(root, width=400, height=400, bg="white", highlightbackground="black")
        self.canvas.grid(row=0, column=2, rowspan=5, padx=10)
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<Control-Button-1>", self.canvas_ctrl_click)  # Ctrl+Click for selection

        # Device Selection Frame
        self.create_device_selection_frame()

        # Terminal Output
        self.terminal_output = tk.Text(root, height=5, width=80, state=tk.DISABLED)
        self.terminal_output.grid(row=7, column=0, columnspan=4, pady=10)

        # Bind section and device selection to update_info_box
        self.section_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)
        self.device_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)

        # Measurement Button
        self.measure_button = tk.Button(root, text="Measure Devices", command=self.open_measurement_window)
        self.measure_button.grid(row=8, column=0, columnspan=2, pady=10)

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

    def create_device_selection_frame(self) -> None:
        """Create a frame with checkboxes for device selection."""
        # Main frame for device selection
        selection_frame = tk.LabelFrame(self.root, text="Device Selection", padx=5, pady=5)
        selection_frame.grid(row=0, column=3, rowspan=6, padx=10, sticky='nsew')

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
            var = tk.BooleanVar(value=True)  # Default to selected
            cb = tk.Checkbutton(self.scrollable_frame, text=device, variable=var,
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
        self.log_terminal(f"Selected devices: {', '.join(sorted(self.selected_devices))}")

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
                self.mpx = MultiplexerController()
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
        if sample == 'Cross_bar':
            sample = BASE_DIR /"Helpers" /"Sample_Infomation" / "memristor.png"
            self.original_image = Image.open(sample)
            img = self.original_image.resize((400, 400))
            self.tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        if sample == 'Multiplexer_10_OUT':
            sample = BASE_DIR / "Helpers" / "Sample_Infomation" / "Multiplexer_10_OUT.jpg"
            self.original_image = Image.open(sample)
            img = self.original_image.resize((400, 400))
            self.tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        # Redraw selection highlights
        self.update_canvas_selection_highlights()

    def update_device_type(self, current_device_map: str) -> None:
        # all maps from dict
        self.current_map_name = current_device_map
        self.device_mapping = device_maps[current_device_map]
        self.current_map_map = device_maps[current_device_map]
        self.device_maps_list = list(device_maps.keys())
        self.device_list = list(device_maps[current_device_map].keys())  # Dictionary of devices
        # Update device checkboxes when device type changes
        if hasattr(self, 'device_checkboxes'):
            self.update_device_checkboxes()

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
            self.device_dropdown["values"] = sample_config[sample]["devices"]
            self.device_dropdown.set("")

            # Call do_something when sample changes
            self.load_image(sample)
            self.device = self.device_var.get()

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
        self.log_terminal(f"Previous device: {new_device}")

        # Update the displayed device information
        self.device_var.set(new_device)
        self.info_box.config(text=f"Current Device: {new_device}")

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
        self.log_terminal(f"Next device: {new_device}")

        # Update the displayed device information
        self.device_var.set(new_device)
        self.info_box.config(text=f"Current Device: {new_device}")

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

                self.device_var.set(device)
                self.sample_type_var.set(bounds["sample"])
                self.section_var.set(bounds["section"])
                self.info_box.config(text=f"Current Device: {device}")

                # Draw a rectangle around the clicked device
                self.canvas.create_rectangle(
                    x_min_scaled, y_min_scaled, x_max_scaled, y_max_scaled,
                    outline="red", width=2, tags="highlight"
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
            self.canvas.create_rectangle(x_min, y_min, x_max, y_max, outline="red", width=2, tags="highlight")

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
            print(selected_device_list)
            print("")
            self.measuremnt_gui = MeasurementGUI(self.root, sample_type, section, selected_device_list, self)
            self.measurement_window = True
        else:
            self.measuremnt_gui.bring_to_top()

    def update_info_box(self, event: Optional[Any] = None) -> None:
        selected_sample = self.sample_type_var.get()
        selected_section = self.section_var.get()
        selected_device = self.device_var.get()
        device_text = f"Current Device: {selected_sample} - {selected_section} - {selected_device}"
        self.info_box.config(text=device_text)

    def change_relays(self) -> None:
        """Change relays for the current device using MultiplexerManager"""
        current_device = self.device_list[self.current_index]

        # Check if current device is in selected devices
        if current_device not in self.selected_devices:
            self.log_terminal(f"Warning: Device {current_device} is not selected")
            response = messagebox.askyesno("Device Not Selected",
                                           f"Device {current_device} is not in the selected list. Continue anyway?")
            if not response:
                return

        # Use unified multiplexer manager interface
        if self.mpx_manager is not None:
            self.log_terminal(f"Routing to {current_device} via {self.multiplexer_type}")
            success = self.mpx_manager.route_to_device(current_device, self.current_index)
            
            if success:
                self.log_terminal(f"Successfully routed to {current_device}")
            else:
                self.log_terminal(f"Failed to route to {current_device}")
            
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
            self.device_var.set(device_name)
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
                self.device_var.set(device)
                self.info_box.config(text=f"Current Device: {device}")
                self.info_box.config(text=f"Current Device: {device}")
                self.update_highlight(device)
                self.change_relays()
                yield device


# Main execution
if __name__ == "__main__":
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
