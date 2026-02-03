# def sequential_measure(self):
#     """Start sequential measurement in a separate thread."""
#     # if self.measurement_thread and self.measurement_thread.is_alive():
#     #     messagebox.showwarning("Warning", "Measurement already in progress!")
#     #     return
#
#     # Create plotter window first (in GUI thread)
#     measurement_type = self.Sequential_measurement_var.get()
#     if measurement_type == "Iv Sweep":
#         plot_type = "IV Sweep"
#     elif measurement_type == "Single Avg Measure":
#         plot_type = "Single Avg Measure"
#     else:
#         plot_type = "Unknown"
#
#     # Create plotter window
#     self.plotter = MeasurementPlotter(self.root, measurement_type=plot_type)
#     self.safe_plotter = ThreadSafePlotter(self.plotter)
#
#     # Start measurement in separate thread
#     self.measurement_thread = threading.Thread(
#         target=self._sequential_measure_thread,
#         daemon=True
#     )
#     self.measurement_thread.start()
#
#
# def _sequential_measure_thread(self):
#     """Actual measurement logic running in separate thread."""
#     try:
#         self.measuring = True
#         self.stop_measurement_flag = False
#
#         # Update GUI elements using thread-safe method
#         self.window.after(0, lambda: self.bring_to_top())
#         self.check_for_sample_name()
#
#         print(f"Running sequential measurement:")
#
#         measurement_type = self.Sequential_measurement_var.get()
#
#         if measurement_type == "Iv Sweep":
#             self._perform_iv_sweep()
#         elif measurement_type == "Single Avg Measure":
#             self._perform_avg_measure()
#
#     except Exception as e:
#         print(f"Error in measurement thread: {e}")
#         import traceback
#         traceback.print_exc()
#     finally:
#         self.measuring = False
#         # Update GUI in main thread
#         self.window.after(0, lambda: self.status_box.config(text="Measurement Complete"))
#         self.window.after(0, lambda: self.keithley.enable_output(False))
#
#
# def _perform_iv_sweep(self):
#     """Perform IV sweep measurement."""
#     count_pass = 1
#
#     for i in range(int(self.sequential_number_of_sweeps.get())):
#         print("Starting pass #", i + 1)
#         voltage = int(self.sq_voltage.get())
#         voltage_arr = get_voltage_range(0, voltage, 0.05, "FS")
#
#         self.stop_measurement_flag = False
#
#         if self.current_device in self.device_list:
#             start_index = self.device_list.index(self.current_device)
#         else:
#             start_index = 0
#
#         device_count = len(self.device_list)
#
#         for j in range(device_count):
#             if self.stop_measurement_flag:
#                 print("Measurement interrupted!")
#                 break
#
#             device = self.device_list[(start_index + j) % device_count]
#
#             # Update status in GUI thread
#             self.window.after(0, lambda d=device: self.status_box.config(text=f"Measuring {d}..."))
#
#             self.keithley.set_voltage(0, self.icc.get())
#             self.keithley.enable_output(True)
#
#             time.sleep(0.5)
#             v_arr, c_arr, timestamps = self.measure(voltage_arr)
#
#             # Add data to plotter (thread-safe)
#             if self.safe_plotter.is_active():
#                 device_display_name = f"Device_{j + 1}_{device}"
#                 self.safe_plotter.add_batch(
#                     device_display_name,
#                     v_arr,
#                     c_arr,
#                     timestamps
#                 )
#
#             # Save data
#             data = np.column_stack((v_arr, c_arr, timestamps))
#             save_dir = f"Data_save_loc\\Multiplexer_IV_sweep\\{self.sample_name_var.get()}\\{j + 1}"
#             if not os.path.exists(save_dir):
#                 os.makedirs(save_dir)
#
#             sweeps = 1
#             name = f"{count_pass}-FS-{voltage}v-{0.05}sv-{0.05}sd-Py-Sq-{sweeps}"
#             file_path = f"{save_dir}\\{name}.txt"
#             np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E",
#                        header="Voltage Current Time", comments="")
#
#             # Change device in GUI thread
#             self.window.after(0, self.sample_gui.next_device)
#             time.sleep(0.1)
#
#         count_pass += 1
#         time.sleep(self.sq_time_delay.get())
#
#
# def _perform_avg_measure(self):
#     """Perform average measurement."""
#     count_pass = 1
#
#     # Initialize data arrays
#     device_data = {}
#     start_time = time.time()
#
#     if self.current_device in self.device_list:
#         start_index = self.device_list.index(self.current_device)
#     else:
#         start_index = 0
#
#     device_count = len(self.device_list)
#
#     # Initialize arrays
#     for j in range(device_count):
#         device_idx = (start_index + j) % device_count
#         device = self.device_list[device_idx]
#         device_data[device] = {
#             'voltages': [],
#             'currents': [],
#             'std_errors': [],
#             'timestamps': [],
#             'temperatures': []
#         }
#
#     voltage = float(self.sq_voltage.get())
#     measurement_duration = self.measurement_duration_var.get()
#
#     # Main measurement loop
#     for i in range(int(self.sequential_number_of_sweeps.get())):
#         print(f"Starting pass #{i + 1}")
#         self.stop_measurement_flag = False
#
#         for j in range(device_count):
#             if self.stop_measurement_flag:
#                 print("Measurement interrupted! Saving current data...")
#                 self.save_averaged_data(device_data, self.sample_name_var.get(),
#                                         start_index, device_count, interrupted=True)
#                 return
#
#             device_idx = (start_index + j) % device_count
#             device = self.device_list[device_idx]
#             device_display_name = f"Device_{j + 1}_{device}"
#
#             # Update status in GUI thread
#             self.window.after(0, lambda d=device, p=i + 1:
#             self.status_box.config(text=f"Pass {p}: Measuring {d}..."))
#
#             # Calculate timestamp
#             measurement_timestamp = time.time() - start_time
#
#             # Perform averaged measurement
#             avg_current, std_error, temperature = self.measure_average_current(
#                 voltage, measurement_duration
#             )
#
#             # Add to plotter (thread-safe)
#             if self.safe_plotter.is_active():
#                 self.safe_plotter.add_data(
#                     device_display_name,
#                     measurement_timestamp,
#                     avg_current,
#                     time.time()
#                 )
#
#             # Store data
#             device_data[device]['voltages'].append(voltage)
#             device_data[device]['currents'].append(avg_current)
#             device_data[device]['std_errors'].append(std_error)
#             device_data[device]['timestamps'].append(measurement_timestamp)
#             if self.record_temp_var.get():
#                 device_data[device]['temperatures'].append(temperature)
#
#             # Log in GUI thread
#             self.window.after(0, lambda: self.log_terminal(
#                 f"Pass {i + 1}, Device {device}: V={voltage}V, "
#                 f"I_avg={avg_current:.3E}A, σ={std_error:.3E}A, "
#                 f"t={measurement_timestamp:.1f}s"
#             ))
#
#             # Change device in GUI thread
#             self.window.after(0, self.sample_gui.next_device)
#             time.sleep(0.1)
#
#         # Auto-save every 5 cycles
#         if (i + 1) % 5 == 0:
#             self.window.after(0, lambda: self.log_terminal(
#                 f"Auto-saving data after {i + 1} cycles..."
#             ))
#             self.save_averaged_data(device_data, self.sample_name_var.get(),
#                                     start_index, device_count, interrupted=False)
#
#         count_pass += 1
#
#         if i < int(self.sequential_number_of_sweeps.get()) - 1:
#             time.sleep(self.sq_time_delay.get())
#
#     # Save all data at the end
#     self.save_averaged_data(device_data, self.sample_name_var.get(),
#                             start_index, device_count, interrupted=False)
#
#
# def stop_sequential_measurement(self):
#     """Stop the measurement and keep plotter open."""
#     self.stop_measurement_flag = True
#     self.measuring = False
#
#     # Update plotter status
#     if self.plotter and self.plotter.window.winfo_exists():
#         self.plotter.status_label.config(text="Status: Measurement Stopped")
#
#     # Wait for thread to finish
#     if self.measurement_thread and self.measurement_thread.is_alive():
#         self.measurement_thread.join(timeout=2.0)
#
#
# def update_gui_element(self, func):
#     """Helper to update GUI elements from thread."""
#     self.window.after(0, func)
#
#
# def measure_average_current(self, voltage, duration):
#     """
#     Apply voltage and measure current for specified duration, then return average.
#
#     Args:
#         voltage: Voltage to apply (V)
#         duration: Time to measure for (seconds)
#
#     Returns:
#         tuple: (average_current, standard_error, temperature)
#     """
#     # todo add retention on graph
#
#     # Set voltage and enable output
#     self.keithley.set_voltage(voltage, self.icc.get())
#     self.keithley.enable_output(True)
#
#     # Allow settling time
#     time.sleep(0.1)
#
#     # Collect current measurements
#     current_readings = []
#     timestamps = []
#     start_time = time.time()
#
#     # Sample rate (adjust as needed)
#     sample_interval = 0.1  # 10 Hz sampling
#
#     while (time.time() - start_time) < duration:
#         if self.stop_measurement_flag:
#             break
#
#         current = self.keithley.measure_current()
#         current_readings.append(current[1])
#         timestamps.append(time.time() - start_time)
#
#         # Update status
#         elapsed = time.time() - start_time
#         self.status_box.config(
#             text=f"Measuring... {elapsed:.1f}/{duration}s"
#         )
#         self.master.update()
#
#         # Wait for next sample
#         time.sleep(sample_interval)
#
#     # Calculate statistics
#     if current_readings:
#         current_array = np.array(current_readings)
#         avg_current = np.mean(current_array)
#         std_dev = np.std(current_array)
#         std_error = std_dev / np.sqrt(len(current_array))
#     else:
#         avg_current = 0
#         std_error = 0
#
#     # Record temperature if enabled
#     temperature = 0  # Default value
#     if self.record_temp_var.get():
#         temperature = self.record_temperature()
#
#     # Disable output after measurement
#     self.keithley.enable_output(False)
#
#     return avg_current, std_error, temperature
