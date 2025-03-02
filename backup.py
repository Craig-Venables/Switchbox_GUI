#
# class MeasurementGUI:
#     def __init__(self, master, sample_type, section, device_list,sample_gui):
#         self.master = tk.Toplevel(master)
#         self.master.title("Measurement Setup")
#         self.master.geometry("400x300")
#         self.sample_gui = sample_gui
#
#         self.sample_type = sample_type
#         self.section = section
#         self.device_list = device_list
#         self.connected = False
#         self.keithley = None  # Keithley instance
#
#         # UI Mode Selection (Custom or Preset)
#         tk.Label(self.master, text="Mode:").grid(row=0, column=0, sticky="w")
#         self.mode_var = tk.StringVar(value="Custom")
#         self.mode_menu = ttk.Combobox(self.master, textvariable=self.mode_var, values=["Custom", "Preset"])
#         self.mode_menu.grid(row=0, column=1)
#         self.mode_menu.bind("<<ComboboxSelected>>", self.toggle_mode)
#
#         # Preset Selection (Hidden by default)
#         self.preset_var = tk.StringVar(value="Select a Preset")
#         self.preset_menu = ttk.Combobox(self.master, textvariable=self.preset_var, values=[], state="disabled")
#         self.preset_menu.grid(row=1, column=1)
#
#         # Keithley Connection
#         tk.Label(self.master, text="GPIB Address:").grid(row=2, column=0, sticky="w")
#         self.address_var = tk.StringVar(value="GPIB0::24::INSTR")
#         self.address_entry = tk.Entry(self.master, textvariable=self.address_var)
#         self.address_entry.grid(row=2, column=1)
#
#         self.connect_button = tk.Button(self.master, text="Connect", command=self.connect_keithley)
#         self.connect_button.grid(row=2, column=2)
#
#         # Sweep Parameters
#         tk.Label(self.master, text="Start Voltage (V):").grid(row=3, column=0, sticky="w")
#         self.start_voltage = tk.DoubleVar(value=0)
#         self.start_entry = tk.Entry(self.master, textvariable=self.start_voltage)
#         self.start_entry.grid(row=3, column=1)
#
#         tk.Label(self.master, text="Voltage high (V):").grid(row=4, column=0, sticky="w")
#         self.voltage_high = tk.DoubleVar(value=1)
#         self.stop_entry = tk.Entry(self.master, textvariable=self.voltage_high)
#         self.stop_entry.grid(row=4, column=1)
#
#         tk.Label(self.master, text="Step Size (V):").grid(row=5, column=0, sticky="w")
#         self.step_size = tk.DoubleVar(value=0.1)
#         self.step_entry = tk.Entry(self.master, textvariable=self.step_size)
#         self.step_entry.grid(row=5, column=1)
#
#         tk.Label(self.master, text="Settle Time (s):").grid(row=6, column=0, sticky="w")
#         self.settle_time = tk.DoubleVar(value=0.2)
#         self.settle_entry = tk.Entry(self.master, textvariable=self.settle_time)
#         self.settle_entry.grid(row=6, column=1)
#
#         # Start Measurement Button
#         self.measure_button = tk.Button(self.master, text="Start Measurement", command=self.start_measurement)
#         self.measure_button.grid(row=7, column=0, columnspan=2, pady=10)
#
#         # Status Box
#         self.status_box = tk.Label(self.master, text="Status: Not Connected", relief=tk.SUNKEN)
#         self.status_box.grid(row=8, column=0, columnspan=3, pady=5)
#
#     def toggle_mode(self, event=None):
#         """Enable or disable inputs based on mode selection."""
#         mode = self.mode_var.get()
#         if mode == "Custom":
#             self.start_entry.config(state="normal")
#             self.stop_entry.config(state="normal")
#             self.step_entry.config(state="normal")
#             self.settle_entry.config(state="normal")
#             self.preset_menu.config(state="disabled")
#         else:  # Preset mode
#             self.start_entry.config(state="disabled")
#             self.stop_entry.config(state="disabled")
#             self.step_entry.config(state="disabled")
#             self.settle_entry.config(state="disabled")
#
#             # Update preset options
#             self.preset_menu.config(state="readonly")
#             self.preset_menu["values"] = ["Fast Sweep", "Slow Sweep", "High Voltage"]
#             self.preset_menu.current(0)  # Default to first preset
#             self.preset_menu.bind("<<ComboboxSelected>>", self.load_preset)
#
#     def load_preset(self, event=None):
#         """Load predefined values when a preset is selected."""
#         preset = self.preset_var.get()
#         if preset == "Fast Sweep":
#             self.start_voltage.set(0)
#             self.voltage_high.set(1)
#             self.step_size.set(0.1)
#             self.settle_time.set(0.2)
#         elif preset == "Slow Sweep":
#             self.start_voltage.set(0)
#             self.voltage_high.set(2)
#             self.step_size.set(0.05)
#             self.settle_time.set(1)
#         elif preset == "High Voltage":
#             self.start_voltage.set(0)
#             self.voltage_high.set(5)
#             self.step_size.set(0.5)
#             self.settle_time.set(0.5)
#
#         # # Keithley Connection
#         # tk.Label(self.master, text="GPIB Address:").grid(row=0, column=0, sticky="w")
#         # self.address_var = tk.StringVar(value="GPIB0::24::INSTR")
#         # self.address_entry = tk.Entry(self.master, textvariable=self.address_var)
#         # self.address_entry.grid(row=0, column=1)
#         #
#         # self.connect_button = tk.Button(self.master, text="Connect", command=self.connect_keithley)
#         # self.connect_button.grid(row=0, column=2)
#         #
#         # # Sweep Parameters
#         # tk.Label(self.master, text="Start Voltage (V):").grid(row=1, column=0, sticky="w")
#         # self.start_voltage = tk.DoubleVar(value=0)
#         # self.start_entry = tk.Entry(self.master, textvariable=self.start_voltage)
#         # self.start_entry.grid(row=1, column=1)
#         #
#         # tk.Label(self.master, text="Voltage high (V):").grid(row=2, column=0, sticky="w")
#         # self.voltage_high = tk.DoubleVar(value=1)
#         # self.stop_entry = tk.Entry(self.master, textvariable=self.voltage_high)
#         # self.stop_entry.grid(row=2, column=1)
#         #
#         # tk.Label(self.master, text="Step Size (V):").grid(row=3, column=0, sticky="w")
#         # self.step_size = tk.DoubleVar(value=0.1)
#         # self.step_entry = tk.Entry(self.master, textvariable=self.step_size)
#         # self.step_entry.grid(row=3, column=1)
#         #
#         # tk.Label(self.master, text="Settle_time (s):").grid(row=4, column=0, sticky="w")
#         # self.settle_time = tk.DoubleVar(value=0.2)
#         # self.settle_time = tk.Entry(self.master, textvariable=self.settle_time)
#         # self.settle_time.grid(row=4, column=1)
#         #
#         # # Start Measurement Button
#         # self.measure_button = tk.Button(self.master, text="Start Measurement", command=self.start_measurement)
#         # self.measure_button.grid(row=5, column=0, columnspan=2, pady=10)
#         #
#         # # Status Box
#         # self.status_box = tk.Label(self.master, text="Status: Not Connected", relief=tk.SUNKEN)
#         # self.status_box.grid(row=6, column=0, columnspan=3, pady=5)
#
#     def connect_keithley(self):
#         """Connect to the Keithley SMU via GPIB"""
#         address = self.address_var.get()
#         try:
#             self.keithley = Keithley2400(address)
#             self.connected = True
#             self.status_box.config(text="Status: Connected")
#             messagebox.showinfo("Connection", f"Connected to: {self.keithley.get_idn()}")
#         except Exception as e:
#             self.connected = True
#             messagebox.showerror("Error", f"Could not connect to device: {str(e)}")
#
#
#     def start_measurement(self):
#         """Start voltage sweeps on all devices"""
#         if not self.connected:
#             messagebox.showwarning("Warning", "Not connected to Keithley!")
#             return
#
#         start_v = self.start_voltage.get()
#         stop_v = self.voltage_high.get()
#         settle_time = self.settle_time.get()
#         step_v = self.step_size.get()
#
#         def frange(start, stop, step):
#             while start <= stop if step > 0 else start >= stop:
#                 yield round(start, 3)
#                 start += step
#
#         voltage_range = (list(frange(start_v, stop_v, step_v)) +
#                          list(frange(stop_v, -stop_v, -step_v)) +
#                          list(frange(-stop_v, start_v, step_v)))
#         # this method takes the readings twice at all ends of the ranges.
#
#         print(voltage_range)
#         # loops through the device's
#         for device in self.device_list:
#
#             # Add in here the line of code to change the device.
#             print("add code to change device here")
#             self.sample_gui.next_device()
#
#
#             self.status_box.config(text=f"Measuring {device}...")
#             self.master.update()
#
#             #self.keithley.set_voltage(0)  # Start at 0V
#             #self.keithley.enable_output(True)  # Enable output
#
#             # possibly change time sleep
#             time.sleep(0.5)
#
#             # Sweep through voltages
#             for v in voltage_range:
#                 print("uncomment out the kiethly stuffs")
#                 #self.keithley.set_voltage(v)
#                 time.sleep(0.2)  # Allow measurement to settle
#                 #current = self.keithley.measure_current()
#                 #self.log_data(device, v, current)
#
#
#             #self.keithley.enable_output(False)  # Turn off output
#
#         self.status_box.config(text="Measurement Complete")
#         messagebox.showinfo("Complete", "Measurements finished.")
#
#     def log_data(self, device, voltage, current):
#         """Log the measured data"""
#         with open("measurement_data.csv", "a") as file:
#             file.write(f"{device},{voltage},{current}\n")
#
#     @staticmethod
#     def frange(start, stop, step):
#         """Generate floating-point numbers within a range"""
#         while start <= stop:
#             yield start
#             start += step