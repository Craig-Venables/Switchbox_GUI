# self.master = tk.Toplevel(master)
        # self.master.title("Measurement Setup")
        # self.master.geometry("700x600")  # Increased width to accommodate new section
        # self.sample_gui = sample_gui
        # self.sample_type = sample_type
        # self.section = section
        # self.device_list = device_list
        # self.connected = False
        # self.keithley = None  # Keithley instance
        #
        # # Load custom sweeps from JSON
        # self.custom_sweeps = self.load_custom_sweeps("Custom_Sweeps.json")
        #
        # # UI Mode Selection (Custom or Preset)
        # tk.Label(self.master, text="Mode:").grid(row=0, column=0, sticky="w")
        # self.mode_var = tk.StringVar(value="Custom")
        # self.mode_menu = ttk.Combobox(self.master, textvariable=self.mode_var, values=["Custom", "Preset"])
        # self.mode_menu.grid(row=0, column=1)
        # self.mode_menu.bind("<<ComboboxSelected>>", self.toggle_mode)
        #
        # # Preset Selection (Hidden by default)
        # self.preset_var = tk.StringVar(value="Select a Preset")
        # self.preset_menu = ttk.Combobox(self.master, textvariable=self.preset_var, values=[], state="disabled")
        # self.preset_menu.grid(row=1, column=1)
        #
        # # Keithley Connection
        # tk.Label(self.master, text="GPIB Address:").grid(row=2, column=0, sticky="w")
        # self.address_var = tk.StringVar(value="GPIB0::24::INSTR")
        # self.address_entry = tk.Entry(self.master, textvariable=self.address_var)
        # self.address_entry.grid(row=2, column=1)
        # self.connect_button = tk.Button(self.master, text="Connect", command=self.connect_keithley)
        # self.connect_button.grid(row=2, column=2)
        #
        # # Sweep Parameters
        # tk.Label(self.master, text="Start Voltage (V):").grid(row=3, column=0, sticky="w")
        # self.start_voltage = tk.DoubleVar(value=0)
        # self.start_entry = tk.Entry(self.master, textvariable=self.start_voltage)
        # self.start_entry.grid(row=3, column=1)
        #
        # tk.Label(self.master, text="Voltage high (V):").grid(row=4, column=0, sticky="w")
        # self.voltage_high = tk.DoubleVar(value=1)
        # self.stop_entry = tk.Entry(self.master, textvariable=self.voltage_high)
        # self.stop_entry.grid(row=4, column=1)
        #f
        # tk.Label(self.master, text="Step Size (V):").grid(row=5, column=0, sticky="w")
        # self.step_size = tk.DoubleVar(value=0.1)
        # self.step_entry = tk.Entry(self.master, textvariable=self.step_size)
        # self.step_entry.grid(row=5, column=1)
        #
        # tk.Label(self.master, text="# Sweeps:").grid(row=6, column=0, sticky="w")
        # self.sweeps = tk.DoubleVar(value=1)
        # self.sweeps_entry = tk.Entry(self.master, textvariable=self.sweeps)
        # self.sweeps_entry.grid(row=6, column=1)
        #
        # # Start Measurement Button
        # self.measure_button = tk.Button(self.master, text="Start Measurement", command=self.start_measurement)
        # self.measure_button.grid(row=7, column=0, columnspan=2, pady=10)
        #
        # # Status Box
        # self.status_box = tk.Label(self.master, text="Status: Not Connected", relief=tk.SUNKEN)
        # self.status_box.grid(row=8, column=0, columnspan=3, pady=5)
        #
        # #todo change this too ato corect the ddown with the list from custom_sweeps.json
        # # Custom Measurements Section
        # tk.Label(self.master, text="Custom Measurement:").grid(row=0, column=3, padx=10, sticky="w")
        # self.custom_measurements = ["Test", "IV Curve", "Resistance Sweep", "Capacitance Test"]
        # self.custom_measurement_var = tk.StringVar(value=self.custom_measurements[0])
        # self.custom_measurement_menu = ttk.Combobox(self.master, textvariable=self.custom_measurement_var,
        #                                             values=self.custom_measurements)
        # self.custom_measurement_menu.grid(row=0, column=4, padx=10)
        #
        # self.run_custom_button = tk.Button(self.master, text="Run Custom", command=self.run_custom_measurement)
        # self.run_custom_button.grid(row=2, column=3, padx=10)
        #
        # # Matplotlib Figure for Plotting
        # self.figure, self.ax = plt.subplots(figsize=(4, 3))
        # self.ax.set_title("Measurement Plot")
        # self.ax.set_xlabel("Voltage (V)")
        # self.ax.set_ylabel("Current (Across Ito)")
        # self.canvas = FigureCanvasTkAgg(self.figure, master=self.master)
        # self.canvas.get_tk_widget().grid(row=3, column=5, rowspan=6, padx=10, pady=10)