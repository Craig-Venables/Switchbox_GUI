import tkinter as tk
from tkinter import ttk, messagebox,simpledialog
import numpy as np
from PIL import Image, ImageTk
import json
import time
from Keithley2400 import Keithley2400Controller  # Import the Keithley class
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from AdaptiveMeasurement import AdaptiveMeasurement
from check_connection import CheckConnection
import sys
import string
import os
import re

#  todo set sweep meramiters to do single measurments when measuring one device, this then looks at the folder and saves
# the data with all the peramiters givewn and increases the numnber ie if 10-fs... exisits it makes it 11-


# import pySwitchbox

# TODO can i add a time to this so i can do endurance and retention

# TODO Sort saving of the files correctly? Device Name? Sample name?

#12 minuets


""" Classes for the Gui"""

# Load sample configuration from JSON file
sample_config = {
    "Cross_bar": {
        "sections": {"A": True, "B": True, "C": False, "D": True, "E": True, "F": False, "G": True, "H": True,
                     "I": True, "J": True, "K": True, "L": True},
        "devices": [str(i) for i in range(1, 11)]}}


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

        self.measurement_window = False

        # self.switchbox = pySwitchbox.Switchbox()


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

        if not self.measurement_window:
            sample_type = self.sample_type_var.get()
            section = self.section_var.get()

            # Filter devices belonging to the selected sample type
            selected_devices = [d for d in self.device_list if device_mapping[d]["sample"] == sample_type]

            if not selected_devices:
                messagebox.showwarning("Warning", "No devices found for this sample.")
                return
            self.measuremnt_gui = MeasurementGUI(self.root, sample_type, section, selected_devices, self)
            self.measurement_window = True
        else:
            self.measuremnt_gui.bring_to_top()

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
        # self.switchbox.activate(pins_arr)

        self.log_terminal(self.section_var.get() + self.device_var.get())
        if self.measurement_window:

            self.measuremnt_gui.current_index = self.current_index
            self.measuremnt_gui.update_variables()

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
        self.master.geometry("1600x550+200+100")
        self.sample_gui = sample_gui
        self.current_index = self.sample_gui.current_index



        # Device name's
        self.sample_type = sample_type
        self.section = section # redudntant i think
        self.device_list = device_list
        self.current_device = self.device_list[self.current_index]
        self.device_section_and_number = self.convert_to_name(self.current_index)
        self.display_index_section_number = self.current_device + "/" + self.device_section_and_number


        # Flags
        self.connected = False
        self.keithley = None  # Keithley instance
        self.adaptive_measurement = None
        self.single_device_flag = False
        self.stop_measurement_flag = False

        # Data storage
        self.measurement_data = {}  # Store measurement results

        # Load custom sweeps from JSON
        self.custom_sweeps = self.load_custom_sweeps("Custom_Sweeps.json")
        self.test_names = list(self.custom_sweeps.keys())

        # layout
        self.create_connection_section()
        self.create_mode_selection()
        self.create_sweep_parameters()
        self.create_status_box()
        self.create_custom_measurement_section()
        self.create_plot_section()
        self.create_plot_section2()

        # Adaptive Measurement Section
        self.adaptive_button = tk.Button(self.master, text="Adaptive Settings", command=self.open_adaptive_settings)
        self.adaptive_button.grid(row=9, column=0, columnspan=2, pady=10)

        # Adaptive Measurement Section
        self.adaptive_button = tk.Button(self.master, text="oh no", command=self.ohno)
        self.adaptive_button.grid(row=9, column=1, columnspan=2, pady=10)

        # Adaptive Measurement Section
        self.adaptive_button = tk.Button(self.master, text="Song", command=self.play_melody)
        self.adaptive_button.grid(row=10, column=1, columnspan=2, pady=10)

        self.connect_keithley()



    def update_variables(self):
        # update current device
        self.current_device = self.device_list[self.current_index]
        # Update number (ie device_11)
        self.device_section_and_number = self.convert_to_name(self.current_index)
        # Update section and number
        self.display_index_section_number = self.current_device + "/" + self.device_section_and_number
        self.device_var.config(text=self.display_index_section_number)
        print(self.convert_to_name(self.current_index))

    def measure_one_device(self):
        if self.adaptive_var.get():
            print("Measuring only one device")
            self.single_device_flag = True

            #self.sample_name.config(state="normal")
        else:
            print("Measuring all devices")
            self.single_device_flag = False

            #self.sample_name.config(state="disabled")

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
        self.canvas.get_tk_widget().grid(row=0, column=0, columnspan=5, sticky="nsew")

        # Configure the frame layout
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # Show last sweeps button
        self.show_results_button = tk.Button(frame, text="Show Last Sweeps", command=self.show_last_sweeps)
        self.show_results_button.grid(row=1, column=0, columnspan=1, pady=5)

        # Show last sweeps button
        self.show_results_button = tk.Button(frame, text="check_connection", command=self.check_connection)
        self.show_results_button.grid(row=1, column=1, columnspan=1, pady=5)

    def create_plot_section2(self):
        """Matplotlib figure for plotting"""
        frame = tk.LabelFrame(self.master, text="Last Measurement Plot", padx=5, pady=5)
        frame.grid(row=0, column=2, rowspan=5, padx=10, pady=5, sticky="nsew")

        self.figure2, self.ax2 = plt.subplots(figsize=(4, 3))
        self.ax2.set_title("Iv - All")
        self.ax2.set_xlabel("Voltage (V)")
        self.ax2.set_ylabel("Current (A)")
        self.figure2.tight_layout()  # Adjust layout

        self.canvas2 = FigureCanvasTkAgg(self.figure2, master=frame)
        self.canvas2.get_tk_widget().grid(row=0, column=0,pady=5, sticky="nsew")

        self.figure3, self.ax3 = plt.subplots(figsize=(4, 3))
        self.ax3.set_title("Log Plot - All")
        self.ax3.set_xlabel("Voltage (V)")
        self.ax3.set_ylabel("abs(Current (A))")
        self.ax3.set_yscale('log')
        self.figure3.tight_layout()  # Adjust layout

        self.canvas3 = FigureCanvasTkAgg(self.figure3, master=frame)
        self.canvas3.get_tk_widget().grid(row=0, column=1,pady=5 ,sticky="nsew")

        # Configure the frame layout
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)  # Ensure equal space for both plots
        frame.rowconfigure(0, weight=1)

        # Show last sweeps button
        self.show_results_button = tk.Button(frame, text="Ax1 Clear", command=lambda: self.clear_axis(2))
        self.show_results_button.grid(row=1, column=0, columnspan=1, pady=5)

        # Show last sweeps button
        self.show_results_button = tk.Button(frame, text="Ax2 Clear", command=lambda: self.clear_axis(3))
        self.show_results_button.grid(row=1, column=1, columnspan=1, pady=5)

    def clear_axis(self, axis):
        #todo make the clear work correctly
        if axis == 2:
            self.ax2.clear()
            self.canvas.draw()  # Redraw the canvas
            self.master.update_idletasks()
            self.master.update()
        if axis == 3:
            self.ax3.clear()
            self.canvas.draw()  # Redraw the canvas
            self.master.update_idletasks()
            self.master.update()

    def spare_button(self):
        print("spare")

    def create_custom_measurement_section(self):
        """Custom measurements section"""
        frame = tk.LabelFrame(self.master, text="Custom Measurements", padx=5, pady=5)
        frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Drop_down menu
        tk.Label(frame, text="Custom Measurement:").grid(row=0, column=0, sticky="w")
        self.custom_measurement_var = tk.StringVar(value=self.test_names[0] if self.test_names else "Test")
        self.custom_measurement_menu = ttk.Combobox(frame, textvariable=self.custom_measurement_var,
                                                    values=self.test_names)
        self.custom_measurement_menu.grid(row=0, column=1, padx=5)

        # compliance current Data entry
        tk.Label(frame, text="Icc (A):").grid(row=1, column=0, sticky="w")
        self.icc = tk.DoubleVar(value=0.01)
        tk.Entry(frame, textvariable=self.icc).grid(row=1, column=1)

        # Run button
        self.run_custom_button = tk.Button(frame, text="Run Custom", command=self.run_custom_measurement)
        self.run_custom_button.grid(row=2, column=0, columnspan=2, pady=5)

    def create_status_box(self):
        """Status box section"""
        frame = tk.LabelFrame(self.master, text="Status", padx=5, pady=5)
        frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

        self.status_box = tk.Label(frame, text="Status: Not Connected", relief=tk.SUNKEN, anchor="w", width=40)
        self.status_box.pack(fill=tk.X)

    def create_mode_selection(self):
        """Mode selection section"""
        frame = tk.LabelFrame(self.master, text="Mode Selection", padx=5, pady=5)
        frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        # Toggle switch: Measure one device
        tk.Label(frame, text="Measure One Device?").grid(row=0, column=0, sticky="w")
        self.adaptive_var = tk.IntVar(value=0)
        self.adaptive_switch = ttk.Checkbutton(frame,variable=self.adaptive_var,command=self.measure_one_device)
        self.adaptive_switch.grid(row=0, column=1, columnspan=1)


        tk.Label(frame, text="Current Device:").grid(row=1, column=0, sticky="w")
        self.device_var = tk.Label(frame, text=self.display_index_section_number, relief=tk.SUNKEN, anchor="w", width=20)
        self.device_var.grid(row=1, column=1, columnspan=1, sticky="ew")

        tk.Label(frame, text="Sample Name (for saving):").grid(row=2, column=0, sticky="w")
        self.sample_name_var = tk.StringVar()  # Use a StringVar
        self.sample_name = ttk.Entry(frame, textvariable=self.sample_name_var)
        self.sample_name.grid(row=2, column=1, columnspan=1, sticky="ew")

    def create_connection_section(self):
        """Keithley connection section"""
        frame = tk.LabelFrame(self.master, text="Keithley Connection", padx=5, pady=5)
        frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

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
        self.measure_button.grid(row=5, column=0, columnspan=1, pady=5)

        # stop button
        self.adaptive_button = tk.Button(frame, text="Stop Measurement!", command=self.close)
        self.adaptive_button.grid(row=5, column=1, columnspan=1, pady=10)


    def convert_to_name(self, device_number):
        if not (0 <= device_number <= 99):  # Adjusted range to start from 0
            print(device_number)
            raise ValueError("Device number must be between 0 and 99")

        # Define valid letters, excluding 'C' and 'J'
        valid_letters = [ch for ch in string.ascii_uppercase[:12] if ch not in {'C', 'J'}]

        index = device_number // 10  # Determine the letter group
        sub_number = (device_number % 10) + 1  # Determine the numeric suffix (1-10)

        # better name needed for these
        self.final_device_letter = valid_letters[index]
        self.final_device_number = sub_number



        return f"{valid_letters[index]}{sub_number}"

    def run_custom_measurement(self):

        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return

        if self.single_device_flag:
            response = messagebox.askquestion(
                "Did you choose the correct device?",
                "Please make sure the correct device is selected.\nClick 'Yes' if you are sure.\nIf not you will be "
                "saving over old data"
            )

            if response != 'yes':
                return

        # make sure it is on the top
        self.bring_to_top()

        # checks for sample name if not prompts user
        self.check_for_sample_name()


        selected_measurement = self.custom_measurement_var.get()
        print(f"Running custom measurement: {selected_measurement}")

        if selected_measurement in self.custom_sweeps:
            if self.current_device in self.device_list:
                start_index = self.device_list.index(self.current_device)
            else:
                start_index = 0  # Default to the first device if current one is not found

            device_count = len(self.device_list)

            for i in range(device_count):  # Ensure we process each device exactly once
                device = self.device_list[(start_index + i) % device_count]  # Wrap around when reaching the end

                self.status_box.config(text=f"Measuring {device}...")
                self.master.update()
                time.sleep(1)

                self.keithley.set_voltage(0, self.icc.get())  # Start at 0V
                self.keithley.enable_output(True)  # Enable output
                start = time.time()
                for key, params in self.custom_sweeps[selected_measurement].items():
                    if self.stop_measurement_flag:  # Check if stop was pressed
                        print("Measurement interrupted!")
                        break  # Exit measurement loop immediately

                    print("Working on device -", device, ": Measurement -", key)

                    # default values
                    start_v = params.get("start_v", 0)
                    stop_v = params.get("stop_v", 1)
                    sweeps = params.get("sweeps", 1)
                    step_v = params.get("step_v", 0.1)
                    step_delay = params.get("step_delay", 0.05)
                    sweep_type = params.get("Sweep_type", "FS")

                    # LED control
                    # Todo incorporate this into the code fully
                    led = params.get("LED", "OFF")
                    led_time = params.get("led_time", "10")
                    led_sweeps = params.get("led_sweeps", "2")



                    if sweep_type == "NS":
                        voltage_range = get_voltage_range(start_v, stop_v, step_v, sweep_type)
                        # print(sweep_type,voltage_range)
                        v_arr, c_arr = self.measure(voltage_range, sweeps, step_delay)
                    elif sweep_type == "PS":
                        voltage_range = get_voltage_range(start_v, stop_v, step_v, sweep_type)
                        # print(sweep_type,voltage_range)
                        v_arr, c_arr = self.measure(voltage_range, sweeps, step_delay)
                    elif sweep_type == "Endurance":
                        print("endurance")
                    elif sweep_type == "Retention":
                        print("retention")

                    else:  # sweep_type == "FS":
                        voltage_range = get_voltage_range(start_v, stop_v, step_v, sweep_type)
                        # print(sweep_type,voltage_range)
                        v_arr, c_arr = self.measure(voltage_range, sweeps, step_delay)

                    # this isnt being used yet i dont think
                    if device not in self.measurement_data:
                        self.measurement_data[device] = {}

                    self.measurement_data[device][key] = (v_arr, c_arr)

                    # todo wrap this into a function for use on other method!!!

                    # data arry to save
                    data = np.column_stack((v_arr, c_arr))

                    # creats save directory with the selected measurement device name letter and number
                    save_dir = f"Data_save_loc\\{self.sample_name}\\{self.final_device_letter}" \
                           f"\\{self.final_device_number}"

                    # make directory if dost exist.
                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)

                    name = f"{key}_{sweep_type}_{stop_v}v-{step_v}sv-{step_delay}sd-Py-{sweeps}"
                    file_path = f"{save_dir}\\{name}.txt"

                    if os.path.exists(file_path):
                        print("filepath already exisits")
                        messagebox.showerror("ERROR","file already exists, you should check before continueing as "
                                                     "this will overwrite")

                    np.savetxt(file_path, data, fmt="%0.18e", header="Voltage Current", comments="")

                    # show graphs on main display
                    self.graphs_show(v_arr,c_arr,key,stop_v)

                    # give time to sleep between measurements!
                    time.sleep(2)

                plot_filename_iv = f"{save_dir}\\All_graphs_IV.png"
                plot_filename_log = f"{save_dir}\\All_graphs_LOG.png"
                self.ax2.figure.savefig(plot_filename_iv,dpi=400)
                self.ax3.figure.savefig(plot_filename_log, dpi=400)
                self.ax2.clear()
                self.ax3.clear()
                self.keithley.enable_output(False)

                end = time.time()
                print("total time for ", selected_measurement, "=", end - start, " - ")

                if self.single_device_flag:
                    print("Measuring one device only")
                    break  # Exit measurement loop immediately

                self.sample_gui.next_device()
            self.status_box.config(text="Measurement Complete")
            messagebox.showinfo("Complete", "Measurements finished.")

        else:
            print("Selected measurement not found in JSON file.")

    def connect_keithley(self):
        """Connect to the Keithley SMU via GPIB"""
        address = self.address_var.get()
        try:
            self.keithley = Keithley2400Controller(address)
            self.connected = True
            self.status_box.config(text="Status: Connected")
            # messagebox.showinfo("Connection", f"Connected to: {address}")
            self.keithley.beep(4000, 0.2)
            time.sleep(0.2)
            self.keithley.beep(5000, 0.5)


        except Exception as e:
            self.connected = True
            messagebox.showerror("Error", f"Could not connect to device: {str(e)}")

    def start_measurement(self):
        """Start single measurementt on the device! """

        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return

        start_v = self.start_voltage.get()
        stop_v = self.voltage_high.get()
        sweeps = self.sweeps.get()
        step_v = self.step_size.get()
        sweep_type = "FS"
        step_delay = 0.05
        icc = self.icc.get()
        device_count = len(self.device_list)

        voltage_range = get_voltage_range(start_v, stop_v, step_v,sweep_type)
        self.stop_measurement_flag = False  # Reset the stop flag

        # make sure it is on the top
        self.bring_to_top()

        # checks for sample name if not prompts user
        self.check_for_sample_name()

        # checks for the current device and the index for start
        if self.current_device in self.device_list:
            start_index = self.device_list.index(self.current_device)
        else:
            # Default to the first device if current one is not found
            start_index = 0

        for i in range(device_count):
            # loop through all the device, looping to start
            device = self.device_list[(start_index + i) % device_count]  # Wrap around when reaching the end

            self.keithley.set_voltage(0, self.icc.get())  # Start at 0V
            self.keithley.enable_output(True)  # Enable output
            start = time.time()

            if self.stop_measurement_flag:  # Check if stop was pressed
                print("Measurement interrupted!")
                break  # Exit measurement loop immediately

            print("working on device - ", device)
            self.status_box.config(text=f"Measuring {device}...")
            self.master.update()

            self.keithley.set_voltage(0, icc)  # Start at 0V
            self.keithley.enable_output(True)  # Enable output

            time.sleep(1)

            # measure device
            v_arr, c_arr = self.measure(voltage_range, sweeps,step_delay)

            # save data to file
            data = np.column_stack((v_arr, c_arr))

            # creats save directory with the selected measurement device name letter and number
            save_dir = f"Data_save_loc\\{self.sample_name}\\{self.final_device_letter}" \
                       f"\\{self.final_device_number}"
            print(self.sample_name)
            # make directory if dost exist.
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            # find a way top extract key from previous device

            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            print(key)
            print(save_key)
            name = f"{save_key}_{sweep_type}_{stop_v}v-{step_v}sv-{step_delay}sd-Py-{sweeps}"
            file_path = f"{save_dir}\\{name}.txt"

            np.savetxt(file_path, data, fmt="%0.18e", header="Voltage Current", comments="")

            self.graphs_show(v_arr, c_arr, "1", stop_v)

            # Turn off output
            self.keithley.enable_output(False)

            if self.single_device_flag:  # Check if stop was pressed
                print("measuring one device only")
                break  # Exit measurement loop immediately

            # change device
            self.sample_gui.next_device()

        self.status_box.config(text="Measurement Complete")
        messagebox.showinfo("Complete", "Measurements finished.")

    def check_for_sample_name(self):
        # Get the current text from the Entry widget
        sample_name = self.sample_name_var.get().strip()

        if not sample_name:  # If empty string
            # Prompt the user for a sample name
            new_sample_name = simpledialog.askstring("Input", "Please enter a sample name:")

            if new_sample_name:  # If the user provided a name
                # Update the Entry widget with the new sample name
                self.sample_name_var.set(new_sample_name)
            else:
                # If the user canceled the dialog, set a default value
                self.sample_name_var.set("No_sample_given")
        else:
            # If the sample name is not empty, use the existing value
            sample_name = self.sample_name_var.get()
    def check_connection(self):
        self.connect_keithley()
        time.sleep(0.1)
        self.Check_connection_gui = CheckConnection(self.master,self.keithley)

    def graphs_show(self,v_arr,c_arr,key,stop_v):

        # plot on main screen! on #1
        self.ax.clear()
        self.ax.plot(v_arr, c_arr, marker='o', markersize=2, color='k')
        self.canvas.draw()

        # plot on main screen! on #2
        self.ax2.plot(v_arr, c_arr, marker='o', markersize=2, label=key + "_" + str(stop_v) + "v", alpha=0.8)
        self.ax2.legend(loc="best")
        self.ax3.plot(v_arr, np.abs(c_arr), marker='o', markersize=2, label=key + "_" + str(stop_v) + "v", alpha=0.8)
        self.ax3.legend(loc="best")
        self.canvas2.draw()
        self.canvas3.draw()
        self.master.update_idletasks()
        self.master.update()


    # keithley.sample_continuously()
    def measure(self, voltage_range, sweeps, step_delay):

        v_arr = []
        c_arr = []
        icc = self.icc.get()
        for sweep_num in range(int(sweeps)):
            # Loops through number of sweeps

            if self.stop_measurement_flag:  # Check if stop was pressed
                print("Measurement interrupted!")
                break  # Exit measurement loop immediately
            for v in voltage_range:
                self.keithley.set_voltage(v,icc)

                time.sleep(0.1)  # Allow measurement to settle

                # takes instantaneous measurement for the current NPLC = 1 (Medium intergration)
                current = self.keithley.measure_current()

                v_arr.append(v)
                c_arr.append(current[1])
                time.sleep(step_delay) # add step delay between measurments.
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

    def play_melody(self):
        """Plays a short melody using Keithley beep."""
        if not self.keithley:
            print("Keithley not connected, can't play melody!")
            return
        # star wars
        melody = [
            # Iconic opening (G-G-G-Eb)
            (392.00, 0.4), (392.00, 0.4), (392.00, 0.4), (311.13, 0.8),  # G4, G4, G4, Eb4
            # Response phrase (Bb-A-G-Eb)
            (466.16, 0.3), (440.00, 0.3), (392.00, 0.3), (311.13, 0.8),  # Bb4, A4, G4, Eb4
            # Repeat opening
            (392.00, 0.4), (392.00, 0.4), (392.00, 0.4), (311.13, 0.8),  # G4, G4, G4, Eb4
            # Descending line (Bb-A-G-F#-G)
            (466.16, 0.3), (440.00, 0.3), (392.00, 0.3), (369.99, 0.3), (392.00, 0.8),  # Bb4, A4, G4, F#4, G4
            # Final cadence (C5-Bb-A-G)
            (523.25, 0.4), (466.16, 0.4), (440.00, 0.4), (392.00, 1.0)  # C5, Bb4, A4, G4
        ]

        # Ode to Joy (Beethoven's 9th)
        melody = [
            (329.63, 0.4), (329.63, 0.4), (349.23, 0.4), (392.00, 0.4),
            (392.00, 0.4), (349.23, 0.4), (329.63, 0.4), (293.66, 0.4),
            (261.63, 0.4), (261.63, 0.4), (293.66, 0.4), (329.63, 0.8)]

        for freq, duration in melody:
            self.keithley.beep(freq, duration)
            time.sleep(duration * 0.8)  # Small gap between notes

        print("Melody finished!")

    def ohno(self):
        self.keithley.beep(150, 0.2)
        time.sleep(0.2)
        self.keithley.beep(100, 0.2)

    def close(self):
        if self.keithley:

            self.stop_measurement_flag = True  # Set stop flag to break loops
            self.keithley.beep(5000, 0.1)
            time.sleep(0.2)
            self.keithley.beep(4000, 0.1)
            # time.sleep(0.1)
            self.keithley.shutdown()
            print("closed")
            self.master.destroy()  # Closes the GUI window
            sys.exit()
        else:
            print("closed")
            sys.exit()

    def bring_to_top(self):
        # If the window is already open, bring it to the front
        self.master.lift()  # Bring the GUI window to the front
        self.master.focus()  # Focus the window (optional, makes it active)


def get_voltage_range(start_v, stop_v, step_v, sweep_type):
    def frange(start, stop, step):
        while start <= stop if step > 0 else start >= stop:
            yield round(start, 3)
            start += step

    # this method takes the readings twice at all ends of the ranges.
    if sweep_type == "NS":
        voltage_range = (list(frange(start_v, -stop_v, -step_v)) +
                         list(frange(-stop_v, start_v, step_v)))

        return voltage_range
    if sweep_type == "PS":
        voltage_range = (list(frange(start_v, stop_v, step_v)) +
                         list(frange(stop_v, start_v, -step_v)))

        return voltage_range
    else:
        voltage_range = (list(frange(start_v, stop_v, step_v)) +
                         list(frange(stop_v, -stop_v, -step_v)) +
                         list(frange(-stop_v, start_v, step_v)))

        return voltage_range


def extract_number_from_filename(filename):
    # Use regex to find the number at the start of the filename before the first '-'
    match = re.match(r'^(\d+)_', filename)
    if match:
        return int(match.group(1))
    return None


def find_largest_number_in_folder(folder_path):
    largest_number = None

    # Iterate over all files in the folder
    for filename in os.listdir(folder_path):
        number = extract_number_from_filename(filename)
        if number is not None:
            if largest_number is None or number > largest_number:
                largest_number = number

    return largest_number


if __name__ == "__main__":
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
