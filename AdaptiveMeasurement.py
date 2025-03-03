import tkinter as tk
from tkinter import ttk
import numpy as np
import time


class AdaptiveMeasurement:
    def __init__(self, master):
        self.master = tk.Toplevel(master)
        self.master.title("Adaptive Measurement Setup")
        self.master.geometry("400x300")

        # Parameters Section
        tk.Label(self.master, text="Adaptive Parameters").grid(row=0, column=0, columnspan=2)

        tk.Label(self.master, text="Resistance Limit (Ohms):").grid(row=1, column=0, sticky="w")
        self.resistance_limit = tk.DoubleVar(value=1e6)
        self.resistance_entry = tk.Entry(self.master, textvariable=self.resistance_limit)
        self.resistance_entry.grid(row=1, column=1)

        tk.Label(self.master, text="Max Compliance (A):").grid(row=2, column=0, sticky="w")
        self.compliance_limit = tk.DoubleVar(value=1e-6)
        self.compliance_entry = tk.Entry(self.master, textvariable=self.compliance_limit)
        self.compliance_entry.grid(row=2, column=1)

        tk.Label(self.master, text="Capacitive Threshold:").grid(row=3, column=0, sticky="w")
        self.capacitive_threshold = tk.DoubleVar(value=0.1)
        self.capacitive_entry = tk.Entry(self.master, textvariable=self.capacitive_threshold)
        self.capacitive_entry.grid(row=3, column=1)

        # Enable Adaptive Mode
        self.adaptive_mode = tk.BooleanVar(value=False)
        self.adaptive_check = tk.Checkbutton(self.master, text="Enable Adaptive Mode", variable=self.adaptive_mode)
        self.adaptive_check.grid(row=4, column=0, columnspan=2)

        # Save Settings Button
        self.save_button = tk.Button(self.master, text="Save Settings", command=self.save_settings)
        self.save_button.grid(row=5, column=0, columnspan=2, pady=10)

    def save_settings(self):
        settings = {
            "resistance_limit": self.resistance_limit.get(),
            "compliance_limit": self.compliance_limit.get(),
            "capacitive_threshold": self.capacitive_threshold.get(),
            "adaptive_mode": self.adaptive_mode.get()
        }
        print("Adaptive Measurement Settings Saved:", settings)

# import numpy as np
# import tkinter as tk
# from tkinter import ttk
#
#
# class AdaptiveMeasurement:
#     def __init__(self, parent, update_callback):
#         """
#         Adaptive measurement module for analyzing completed sweeps and adjusting future sweeps.
#         :param parent: The parent Tkinter window.
#         :param update_callback: Function to update the main GUI with new parameters.
#         """
#
#         self.parent = parent
#         self.update_callback = update_callback
#         self.adaptive_enabled = tk.BooleanVar(value=False)
#         self.resistance_threshold = tk.DoubleVar(value=1e6)  # Example: 1 MΩ threshold
#         self.compliance_limit = tk.DoubleVar(value=1e-6)  # Example: 1 µA compliance
#         self.history = []  # Stores previous sweep results
#
#         self.create_gui()
#
#     def create_gui(self):
#         """Creates the Adaptive Measurement settings panel."""
#         self.window = tk.Toplevel(self.parent)
#         self.window.title("Adaptive Measurement Settings")
#         self.window.geometry("400x300")
#
#         ttk.Label(self.window, text="Enable Adaptive Mode:").grid(row=0, column=0, sticky="w")
#         ttk.Checkbutton(self.window, variable=self.adaptive_enabled).grid(row=0, column=1, sticky="w")
#
#         ttk.Label(self.window, text="Resistance Threshold (Ω):").grid(row=1, column=0, sticky="w")
#         ttk.Entry(self.window, textvariable=self.resistance_threshold).grid(row=1, column=1)
#
#         ttk.Label(self.window, text="Compliance Limit (A):").grid(row=2, column=0, sticky="w")
#         ttk.Entry(self.window, textvariable=self.compliance_limit).grid(row=2, column=1)
#
#         ttk.Button(self.window, text="Save Settings", command=self.save_settings).grid(row=3, column=0, columnspan=2,
#                                                                                        pady=10)
#
#     def save_settings(self):
#         """Saves adaptive settings and closes the window."""
#         print(f"Adaptive Enabled: {self.adaptive_enabled.get()}")
#         print(f"Resistance Threshold: {self.resistance_threshold.get()} Ω")
#         print(f"Compliance Limit: {self.compliance_limit.get()} A")
#         self.window.destroy()
#
#     def analyze_sweep(self, voltages, currents):
#         """Analyzes a completed sweep and determines adjustments for the next sweep."""
#         resistance = self.calculate_resistance(voltages, currents)
#         self.history.append(resistance)
#         print(f"Measured Resistance: {resistance:.2e} Ω")
#
#         if self.adaptive_enabled.get():
#             new_params = self.decide_next_sweep(resistance)
#             self.update_callback(new_params)  # Send adjustments to GUI
#
#     def calculate_resistance(self, voltages, currents):
#         """Estimates resistance from voltage and current data."""
#         avg_resistance = np.mean(np.divide(voltages, currents, where=(currents != 0)))
#         return avg_resistance
#
#     def decide_next_sweep(self, resistance):
#         """Determines adjustments for the next sweep based on resistance results."""
#         new_params = {}
#         if resistance > self.resistance_threshold.get():
#             print("Resistance too high, increasing voltage range.")
#             new_params = {"start_v": 0, "stop_v": 2, "step_v": 0.2}
#         elif resistance < self.resistance_threshold.get() / 10:
#             print("Resistance too low, decreasing voltage range.")
#             new_params = {"start_v": 0, "stop_v": 0.5, "step_v": 0.05}
#         return new_params
