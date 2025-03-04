import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
from PIL import Image, ImageTk
import json
import time
from Keithley2400 import Keithley2400  # Import the Keithley class
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from AdaptiveMeasurement import AdaptiveMeasurement
import pySwitchbox

""" Classes for the Gui"""

# Load sample configuration from JSON file
sample_config = {
    "Cross_bar": {
        "sections": {"A": True, "B": True, "C": False, "D": True, "E": True, "F": False, "G": True, "H": True,
                     "I": True, "J": True, "K": True, "L": True},
        "devices": [str(i) for i in range(1, 11)]
    }

}


# Function to load device mapping from JSON file
def load_device_mapping(filename="pin_mapping.json"):
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        print("Error: JSON file not found.")
        return {}
    except json.JSONDecodeError:
        print("Error: JSON file is not formatted correctly.")
        return {}


pin_mapping = load_device_mapping()

# Load device mapping
with open("mapping.json", "r") as f:
    device_mapping = json.load(f)


class SampleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Device Viewer")
        self.root.geometry("650x600")

        # list of all devices
        self.device_mapping = device_mapping  # Dictionary of devices
        self.device_list = list(device_mapping.keys())  # Ordered list of device names
        self.current_index = 0  # Index of currently selected device

        self.switchbox = pySwitchbox.Switchbox()

        # Sample Type Dropdown
        tk.Label(root, text="Sample type").grid(row=0, column=0, sticky='w')
        self.sample_type_var = tk.StringVar()
        self.sample_dropdown = ttk.Combobox(root, textvariable=self.sample_type_var, values=list(sample_config.keys()))
        self.sample_dropdown.grid(row=0, column=1)
        self.sample_dropdown.bind("<<ComboboxSelected>>", self.update_dropdowns)

        # Section Dropdown
        tk.Label(root, text="Section").grid(row=1, column=0, sticky='w')
        self.section_var = tk.StringVar()
        self.section_dropdown = ttk.Combobox(root, textvariable=self.section_var)
        self.section_dropdown.grid(row=1, column=1)

        # Device Number Dropdown
        tk.Label(root, text="Device Number").grid(row=2, column=0, sticky='w')
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(root, textvariable=self.device_var)
        self.device_dropdown.grid(row=2, column=1)

        # Information Box
        self.info_box = tk.Label(root, text="Current Device: None", relief=tk.SUNKEN, width=30)
        self.info_box.grid(row=3, column=0, columnspan=2, pady=10)

        # Navigation Buttons
        self.prev_button = tk.Button(root, text="<", command=self.prev_device)
        self.prev_button.grid(row=4, column=0, pady=2)

        self.clear_button = tk.Button(root, text="Clear", command=self.clear_canvas)
        self.clear_button.grid(row=5, column=1, pady=2)

        self.change_button = tk.Button(root, text="Go", command=self.change_relays)
        self.change_button.grid(row=5, column=0, pady=2)

        self.next_button = tk.Button(root, text=">", command=self.next_device)
        self.next_button.grid(row=4, column=1, pady=2)

        # Canvas for Image
        self.canvas = tk.Canvas(root, width=400, height=400, bg="white", highlightbackground="black")
        self.canvas.grid(row=0, column=2, rowspan=5, padx=10)
        self.canvas.bind("<Button-1>", self.canvas_click)

        # Terminal Output
        self.terminal_output = tk.Text(root, height=5, width=80, state=tk.DISABLED)
        self.terminal_output.grid(row=6, column=0, columnspan=3, pady=10)

        # Bind section and device selection to update_info_box
        self.section_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)
        self.device_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)

        # Measurement Button
        self.measure_button = tk.Button(root, text="Measure Devices", command=self.open_measurement_window)
        self.measure_button.grid(row=7, column=0, columnspan=2, pady=10)

        # Placeholder for clicked points
        # self.electrode_points = []
        # Load image

    def load_image(self, sample):
        """ Load imgae into canvas set up to add others later simply """

        if sample == 'Cross_bar':
            sample = "Sample_images/memristor.png"
            self.original_image = Image.open(sample)
            img = self.original_image.resize((400, 400))

            self.tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        if sample == 'Sample 2':
            self.log_terminal("no image for selection")
            # clear image?

    def update_dropdowns(self, event):
        sample = self.sample_type_var.get()
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
            # self.Change_image(sample)

    def prev_device(self):

        # Move to the next device in the list
        self.current_index = (self.current_index - 1) % len(self.device_list)
        new_device = self.device_list[self.current_index]
        self.log_terminal("Previous device")

        # Update the displayed device information
        self.device_var.set(new_device)
        self.info_box.config(text=f"Current Device: {new_device}")

        # Update the highlight
        self.update_highlight(new_device)

    def next_device(self):
        # Move to the next device in the list
        self.current_index = (self.current_index + 1) % len(self.device_list)
        new_device = self.device_list[self.current_index]
        self.log_terminal("Next device")
        # Update the displayed device information
        self.device_var.set(new_device)
        self.info_box.config(text=f"Current Device: {new_device}")

        # Update the highlight
        self.update_highlight(new_device)

    def canvas_click(self, event):
        # print(event)

        orig_width, orig_height = self.original_image.size
        scaled_width, scaled_height = 400, 400
        # Compute the scaling factors
        scale_x = orig_width / scaled_width
        scale_y = orig_height / scaled_height

        # for device, bounds in device_mapping.items():
        for i, (device, bounds) in enumerate(device_mapping.items()):

            # Scale down the bounding box coordinates to match canvas size
            x_min_scaled = bounds["x_min"] / scale_x
            x_max_scaled = bounds["x_max"] / scale_x
            y_min_scaled = bounds["y_min"] / scale_y
            y_max_scaled = bounds["y_max"] / scale_y

            # debugging when not devices not working once clicked
            # print(event.x, event.y)
            # print(event.x*scale_x,event.y*scale_y)

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
                # self.device = device

    def update_highlight(self, device):
        # Clear any existing highlights
        self.canvas.delete("highlight")

        # Get the device bounds
        bounds = device_mapping.get(device, None)
        if bounds:
            scale_x = 1198 / 400  # Adjust based on your scaling factor
            scale_y = 1199 / 400

            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y

            # Draw a new rectangle
            self.canvas.create_rectangle(x_min, y_min, x_max, y_max, outline="red", width=2, tags="highlight")

    def open_measurement_window(self):
        sample_type = self.sample_type_var.get()
        section = self.section_var.get()

        # Filter devices belonging to the selected sample type
        selected_devices = [d for d in self.device_list if device_mapping[d]["sample"] == sample_type]

        if not selected_devices:
            messagebox.showwarning("Warning", "No devices found for this sample.")
            return

        MeasurementGUI(self.root, sample_type, section, selected_devices, self)

    def update_info_box(self, event=None):
        selected_sample = self.sample_type_var.get()
        selected_section = self.section_var.get()
        selected_device = self.device_var.get()
        device_text = f"Current Device: {selected_sample} - {selected_section} - {selected_device}"
        self.info_box.config(text=device_text)

    def change_relays(self):

        def get_device_pins(device_name):
            if device_name in pin_mapping:
                # print(device_name,pin_mapping)
                return pin_mapping[device_name]["pins"]
            else:
                print(f"Warning: {device_name} not found in mapping.")
                return None

        self.log_terminal("changing relays too")
        self.log_terminal(self.device_list[self.current_index])

        # current device
        # print(self.device_list[self.current_index])

        # gives pins in array
        pins_arr = get_device_pins(self.device_list[self.current_index])
        self.switchbox.activate(pins_arr)

        self.log_terminal(self.section_var.get() + self.device_var.get())

    def clear_canvas(self):
        self.canvas.delete("all")
        # self.electrode_points.clear()
        self.log_terminal("Canvas cleared")

    def log_terminal(self, message):
        self.terminal_output.config(state=tk.NORMAL)
        self.terminal_output.insert(tk.END, message + "\n")
        self.terminal_output.config(state=tk.DISABLED)
        self.terminal_output.see(tk.END)

    def Change_image(self, sample):
        self.log_terminal("change image sample")


class MeasurementGUI:
    def __init__(self, master, sample_type, section, device_list, sample_gui):
        self.master = tk.Toplevel(master)
        self.master.title("Measurement Setup")
        self.master.geometry("800x600")  # Increased width to accommodate new section
        self.sample_gui = sample_gui
        self.sample_type = sample_type
        self.section = section
        self.device_list = device_list
        self.connected = False
        self.keithley = None  # Keithley instance
        self.adaptive_measurement = None

        self.measurement_data = {}  # Store measurement results

        # Load custom sweeps from JSON
        self.custom_sweeps = self.load_custom_sweeps("Custom_Sweeps.json")
        self.test_names = list(self.custom_sweeps.keys())

        # layout
        self.create_mode_selection()
        self.create_connection_section()
        self.create_sweep_parameters()
        self.create_status_box()
        self.create_custom_measurement_section()
        self.create_plot_section()

        # Show last sweeps button
        self.show_results_button = tk.Button(self.master, text="Show Last Sweeps", command=self.show_last_sweeps)
        self.show_results_button.grid(row=3, column=0, columnspan=2)

        # Adaptive Measurement Section
        self.adaptive_button = tk.Button(self.master, text="Adaptive Settings", command=self.open_adaptive_settings)
        self.adaptive_button.grid(row=9, column=0, columnspan=2, pady=10)

    def open_adaptive_settings(self):
        if self.adaptive_measurement is None or not self.adaptive_measurement.master.winfo_exists():
            self.adaptive_measurement = AdaptiveMeasurement(self.master)

    def show_last_sweeps(self):
        """Creates a new window showing the last measurement for each device"""
        results_window = tk.Toplevel(self.master)
        results_window.title("Last Measurement for Each Device")
        results_window.geometry("800x600")

        figure, axes = plt.subplots(10, 10, figsize=(10, 10))  # 10x10 grid
        figure.tight_layout()
        figure.subplots_adjust(wspace=0.1, hspace=0.1)

        # Store the figure and axes for future updates
        self.figure = figure
        self.axes = axes
        self.results_window = results_window

        for i, (device, measurements) in enumerate(self.measurement_data.items()):
            if i >= 100:
                break  # Limit to 100 devices

            row, col = divmod(i, 10)  # Convert index to 10x10 grid position
            ax = self.axes[row, col]
            last_key = list(measurements.keys())[-1]  # Get the last sweep key
            v_arr, c_arr = measurements[last_key]

            ax.plot(v_arr, c_arr, marker="o", markersize=1)
            # ax.set_title(f"Device {device}", fontsize=5)

            # Add labels to axes (you can adjust the label text and font size)
            # ax.set_xlabel('Voltage (V)', fontsize=6)  # X-axis label
            # ax.set_ylabel('Current (A)', fontsize=6)  # Y-axis label

            # Make tick labels visible and set font size
            ax.tick_params(axis='x', labelsize=2)  # X-axis tick labels font size
            ax.tick_params(axis='y', labelsize=2)  # Y-axis tick labels font size

            # Optionally, set limits or show minor ticks if needed
            ax.set_xticks(np.linspace(min(v_arr), max(v_arr), 2))  # Adjust the number of ticks
            ax.set_yticks(np.linspace(min(c_arr), max(c_arr), 2))  # Adjust the number of ticks

            ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
            ax.set_title(f"Device {device}", fontsize=6)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.results_window)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.draw()

        # Start automatic update
        self.update_last_sweeps()

    def update_last_sweeps(self):
        """Automatically updates the plot every 1000ms"""
        # Re-draw the latest data on the axes
        for i, (device, measurements) in enumerate(self.measurement_data.items()):
            if i >= 100:
                break  # Limit to 100 devices

            row, col = divmod(i, 10)  # Convert index to 10x10 grid position
            ax = self.axes[row, col]
            last_key = list(measurements.keys())[-1]  # Get the last sweep key
            v_arr, c_arr = measurements[last_key]
            ax.clear()  # Clear the old plot
            ax.plot(v_arr, c_arr, marker="o", markersize=1)

            # # Add labels to axes (you can adjust the label text and font size)
            # ax.set_xlabel('Voltage (V)', fontsize=6)  # X-axis label
            # ax.set_ylabel('Current (A)', fontsize=6)  # Y-axis label

            # Make tick labels visible and set font size
            ax.tick_params(axis='x', labelsize=6)  # X-axis tick labels font size
            ax.tick_params(axis='y', labelsize=6)  # Y-axis tick labels font size

            # Optionally, set limits or show minor ticks if needed
            ax.set_xticks(np.linspace(min(v_arr), max(v_arr), 3))  # Adjust the number of ticks
            ax.set_yticks(np.linspace(min(c_arr), max(c_arr), 3))  # Adjust the number of ticks

            ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
            ax.set_title(f"Device {device}", fontsize=6)

        self.canvas.draw()  # Redraw the canvas with the new data

        # Set the next update ( or 10 seconds)
        self.master.after(10000, self.update_last_sweeps)

    def create_plot_section(self):
        """Matplotlib figure for plotting"""
        frame = tk.LabelFrame(self.master, text="Last Measurement Plot", padx=5, pady=5)
        frame.grid(row=0, column=1, rowspan=5, padx=10, pady=5, sticky="nsew")

        self.figure, self.ax = plt.subplots(figsize=(4, 3))
        self.ax.set_title("Measurement Plot")
        self.ax.set_xlabel("Voltage (V)")
        self.ax.set_ylabel("Current (A)")

        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def create_custom_measurement_section(self):
        """Custom measurements section"""
        frame = tk.LabelFrame(self.master, text="Custom Measurements", padx=5, pady=5)
        frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # self.test_names = ["Test", "IV Curve", "Resistance Sweep", "Capacitance Test"]
        tk.Label(frame, text="Custom Measurement:").grid(row=0, column=0, sticky="w")
        self.custom_measurement_var = tk.StringVar(value=self.test_names[0] if self.test_names else "Test")
        self.custom_measurement_menu = ttk.Combobox(frame, textvariable=self.custom_measurement_var,
                                                    values=self.test_names)
        self.custom_measurement_menu.grid(row=0, column=1, padx=5)

        self.run_custom_button = tk.Button(frame, text="Run Custom", command=self.run_custom_measurement)
        self.run_custom_button.grid(row=1, column=0, columnspan=2, pady=5)

    def create_status_box(self):
        """Status box section"""
        frame = tk.LabelFrame(self.master, text="Status", padx=5, pady=5)
        frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

        self.status_box = tk.Label(frame, text="Status: Not Connected", relief=tk.SUNKEN, anchor="w", width=40)
        self.status_box.pack(fill=tk.X)

    def create_mode_selection(self):
        """Mode selection section"""
        frame = tk.LabelFrame(self.master, text="Mode Selection", padx=5, pady=5)
        frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="Mode:").grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="Custom")
        self.mode_menu = ttk.Combobox(frame, textvariable=self.mode_var, values=["Custom", "Preset"])
        self.mode_menu.grid(row=0, column=1)
        self.mode_menu.bind("<<ComboboxSelected>>", self.toggle_mode)

        self.preset_var = tk.StringVar(value="Select a Preset")
        self.preset_menu = ttk.Combobox(frame, textvariable=self.preset_var, values=[], state="disabled")
        self.preset_menu.grid(row=1, column=1)

    def create_connection_section(self):
        """Keithley connection section"""
        frame = tk.LabelFrame(self.master, text="Keithley Connection", padx=5, pady=5)
        frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="GPIB Address:").grid(row=0, column=0, sticky="w")
        self.address_var = tk.StringVar(value="GPIB0::24::INSTR")
        self.address_entry = tk.Entry(frame, textvariable=self.address_var)
        self.address_entry.grid(row=0, column=1)

        self.connect_button = tk.Button(frame, text="Connect", command=self.connect_keithley)
        self.connect_button.grid(row=0, column=2)

    def create_sweep_parameters(self):
        """Sweep parameter section"""
        frame = tk.LabelFrame(self.master, text="Sweep Parameters", padx=5, pady=5)
        frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="Start Voltage (V):").grid(row=0, column=0, sticky="w")
        self.start_voltage = tk.DoubleVar(value=0)
        tk.Entry(frame, textvariable=self.start_voltage).grid(row=0, column=1)

        tk.Label(frame, text="Voltage High (V):").grid(row=1, column=0, sticky="w")
        self.voltage_high = tk.DoubleVar(value=1)
        tk.Entry(frame, textvariable=self.voltage_high).grid(row=1, column=1)

        tk.Label(frame, text="Step Size (V):").grid(row=2, column=0, sticky="w")
        self.step_size = tk.DoubleVar(value=0.1)
        tk.Entry(frame, textvariable=self.step_size).grid(row=2, column=1)

        tk.Label(frame, text="# Sweeps:").grid(row=3, column=0, sticky="w")
        self.sweeps = tk.DoubleVar(value=1)
        tk.Entry(frame, textvariable=self.sweeps).grid(row=3, column=1)
        # todo add compliance current as a way to limit the V
        tk.Label(frame, text="Icc:").grid(row=4, column=0, sticky="w")
        self.icc = tk.DoubleVar(value=0.01)
        tk.Entry(frame, textvariable=self.icc).grid(row=4, column=1)

        self.measure_button = tk.Button(frame, text="Start Measurement", command=self.start_measurement)
        self.measure_button.grid(row=5, column=0, columnspan=2, pady=5)

    def toggle_mode(self, event=None):
        """Enable or disable inputs based on mode selection."""
        mode = self.mode_var.get()
        if mode == "Custom":
            self.start_entry.config(state="normal")
            self.stop_entry.config(state="normal")
            self.step_entry.config(state="normal")
            self.sweeps_entry.config(state="normal")
            self.preset_menu.config(state="disabled")
        else:  # Preset mode
            self.start_entry.config(state="disabled")
            self.stop_entry.config(state="disabled")
            self.step_entry.config(state="disabled")
            self.sweeps_entry.config(state="disabled")

            # Update preset options
            self.preset_menu.config(state="readonly")
            self.preset_menu["values"] = ["Fast Sweep", "Slow Sweep", "High Voltage"]
            self.preset_menu.current(0)  # Default to first preset
            self.preset_menu.bind("<<ComboboxSelected>>", self.load_preset)

    def load_preset(self, event=None):
        """Load predefined values when a preset is selected."""
        preset = self.preset_var.get()
        if preset == "Fast Sweep":
            self.start_voltage.set(0)
            self.voltage_high.set(1)
            self.step_size.set(0.1)
            self.sweeps.set(1)
        elif preset == "Slow Sweep":
            self.start_voltage.set(0)
            self.voltage_high.set(2)
            self.step_size.set(0.05)
            self.sweeps.set(1)
        elif preset == "High Voltage":
            self.start_voltage.set(0)
            self.voltage_high.set(5)
            self.step_size.set(0.5)
            self.sweeps.set(1)

    def run_custom_measurement(self):

        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return

        selected_measurement = self.custom_measurement_var.get()
        print(f"Running custom measurement: {selected_measurement}")
        if selected_measurement in self.custom_sweeps:

            for device in self.device_list:
                # Loop through devices
                self.status_box.config(text=f"Measuring {device}...")
                self.master.update()
                time.sleep(1)

                self.keithley.set_voltage(0)  # Start at 0V
                self.keithley.enable_output(True)  # Enable output

                for key, params in self.custom_sweeps[selected_measurement].items():

                    print("working on device -", device, ": Measurment -", key)

                    start_v = params.get("start_v", 0)
                    stop_v = params.get("stop_v", 1)
                    sweeps = params.get("sweeps", 1)
                    step_v = params.get("step_v", 0.1)

                    voltage_range = get_voltage_range(start_v, stop_v, step_v)
                    v_arr, c_arr = self.measure(voltage_range, sweeps)

                    # Ensure the device exists in measurement_data
                    if device not in self.measurement_data:
                        self.measurement_data[device] = {}  # Initialize with an empty dictionary

                    self.measurement_data[device][key] = (v_arr, c_arr)

                    # print(v_arr,c_arr)

                    # save data to file
                    data = np.column_stack((v_arr, c_arr))
                    file_path = "Data_save_loc\\" f"{selected_measurement}_{device}_{key}.txt"
                    np.savetxt(file_path, data, fmt="%0.18e", header="Voltage Current", comments="")

                    # voltages = [start_v + i * step_v for i in range(int((stop_v - start_v) / step_v) + 1)]
                    # currents = [v * 1e-6 for v in voltages]  # Simulated data
                    self.ax.clear()
                    self.ax.plot(v_arr, c_arr, marker='o')
                    self.ax.set_title("Measurement Plot")
                    self.ax.set_xlabel("Voltage (V)")
                    self.ax.set_ylabel("Current (A)")
                    self.canvas.draw()

                # Turn off output
                self.keithley.enable_output(False)
                # switch to next device
                self.sample_gui.next_device()
        else:
            print("Selected measurement not found in JSON file.")

    def connect_keithley(self):
        """Connect to the Keithley SMU via GPIB"""
        address = self.address_var.get()
        try:
            self.keithley = Keithley2400(address)
            self.connected = True
            self.status_box.config(text="Status: Connected")
            messagebox.showinfo("Connection", f"Connected to: {self.keithley.get_idn()}")
        except Exception as e:
            self.connected = True
            messagebox.showerror("Error", f"Could not connect to device: {str(e)}")

    def start_measurement(self):
        """Start voltage sweeps on all devices"""
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return

        start_v = self.start_voltage.get()
        stop_v = self.voltage_high.get()
        sweeps = self.sweeps.get()
        step_v = self.step_size.get()

        voltage_range = get_voltage_range(start_v, stop_v, step_v)

        # loops through the device's
        for device in self.device_list:
            print("working on device - ", device)
            self.status_box.config(text=f"Measuring {device}...")
            self.master.update()

            self.keithley.set_voltage(0)  # Start at 0V
            self.keithley.enable_output(True)  # Enable output

            # time between devices , needs to allow for relay to change
            time.sleep(1)

            # measure device
            v_arr, c_arr = self.measure(voltage_range, sweeps)

            # save data to file
            data = np.column_stack((v_arr, c_arr))
            file_path = "Data_save_loc\\" f"Simple_measurment_{device}_.txt"
            np.savetxt(file_path, data, fmt="%0.18e", header="Voltage Current", comments="")

            self.ax.clear()
            self.ax.plot(v_arr, c_arr, marker='o')
            self.ax.set_title("Measurement Plot")
            self.ax.set_xlabel("Voltage (V)")
            self.ax.set_ylabel("Current (A)")
            self.canvas.draw()

            # Turn off output
            self.keithley.enable_output(False)
            # change device
            self.sample_gui.next_device()

        self.status_box.config(text="Measurement Complete")
        messagebox.showinfo("Complete", "Measurements finished.")

    def measure(self, voltage_range, sweeps):

        # Sweep through voltages
        for sweep_num in range(int(sweeps)):
            v_arr = []
            c_arr = []
            # print("uncomment out the kiethly stuffs")
            for v in voltage_range:
                self.keithley.set_voltage(v)
                time.sleep(0.2)  # Allow measurement to settle
                current = self.keithley.measure_current()
                v_arr.append(v)

                c_arr.append(current)
            # save the data outside this function!
            return v_arr, c_arr

    def load_custom_sweeps(self, filename):
        try:
            with open(filename, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            print("Custom sweeps file not found.")
            return {}
        except json.JSONDecodeError:
            print("Error decoding JSON file.")
            return {}


def get_voltage_range(start_v, stop_v, step_v):
    def frange(start, stop, step):
        while start <= stop if step > 0 else start >= stop:
            yield round(start, 3)
            start += step

    voltage_range = (list(frange(start_v, stop_v, step_v)) +
                     list(frange(stop_v, -stop_v, -step_v)) +
                     list(frange(-stop_v, start_v, step_v)))
    # this method takes the readings twice at all ends of the ranges.
    return voltage_range


if __name__ == "__main__":
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
