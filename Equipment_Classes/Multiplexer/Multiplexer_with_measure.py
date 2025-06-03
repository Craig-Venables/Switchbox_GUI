import tkinter as tk
from tkinter import ttk, messagebox
import time
import numpy as np
import sys
import os



from Multiplexer_Class import MultiplexerController
# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Now you can import the script
from Keithley2400 import Keithley2400Controller


# Example placeholders for your classes
class Keithley:
    def __init__(self):
        pass
    def set_voltage(self, v): pass
    def measure_current(self): return np.random.normal(0, 1e-6)
    def reset(self): pass

class MeasurementApp:
    def __init__(self, master):
        self.master = master
        master.title("Measurement Controller")

        self.keithley = Keithley2400Controller()
        self.mux = MultiplexerController()

        # GUI elements
        tk.Label(master, text="Mode:").grid(row=0, column=0, sticky=tk.W)
        self.mode_var = tk.StringVar()
        self.mode_select = ttk.Combobox(master, textvariable=self.mode_var, state="readonly")
        self.mode_select['values'] = ("IV", "Single measurement (averaged)")
        self.mode_select.current(0)
        self.mode_select.grid(row=0, column=1)

        tk.Label(master, text="Select Channels:").grid(row=1, column=0, sticky=tk.W)
        self.chan_vars = []
        chan_frame = tk.Frame(master)
        for i in range(10):
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(chan_frame, text=str(i), variable=var)
            cb.grid(row=0, column=i)
            self.chan_vars.append(var)
        chan_frame.grid(row=1, column=1, sticky=tk.W)

        tk.Label(master, text="Voltage Limit (V):").grid(row=2, column=0, sticky=tk.W)
        self.voltage_var = tk.DoubleVar()
        self.voltage_entry = tk.Entry(master, textvariable=self.voltage_var)
        self.voltage_entry.grid(row=2, column=1)
        self.voltage_var.set(1.0)

        # Delays
        tk.Label(master, text="Time delay (ms) between measurements:").grid(row=3, column=0, sticky=tk.W)
        self.delay_meas_var = tk.IntVar(value=100)
        self.delay_meas_entry = tk.Entry(master, textvariable=self.delay_meas_var)
        self.delay_meas_entry.grid(row=3, column=1)

        tk.Label(master, text="Time delay (ms) between switches:").grid(row=4, column=0, sticky=tk.W)
        self.delay_switch_var = tk.IntVar(value=100)
        self.delay_switch_entry = tk.Entry(master, textvariable=self.delay_switch_var)
        self.delay_switch_entry.grid(row=4, column=1)

        # Start button
        self.start_button = tk.Button(master, text="Start Measurement", command=self.start_measurement)
        self.start_button.grid(row=5, column=0, columnspan=2)

        # Output Box
        self.output_text = tk.Text(master, width=60, height=12)
        self.output_text.grid(row=6, column=0, columnspan=2)

    def start_measurement(self):
        try:
            mode = self.mode_var.get()
            voltage = float(self.voltage_var.get())
            d_meas = self.delay_meas_var.get() / 1000.0
            d_switch = self.delay_switch_var.get() / 1000.0
            selected_channels = [i for i, var in enumerate(self.chan_vars) if var.get()]
            if not selected_channels:
                messagebox.showerror("No Channels Selected", "Please select at least one channel.")
                return
        except Exception as e:
            messagebox.showerror("Input Error", str(e))
            return

        for channel in selected_channels:
            self.mux.select_channel(channel)
            self.log(f"\n[Channel {channel}] Selected, waiting {d_switch*1000:.0f} ms...")
            self.master.update()
            time.sleep(d_switch)

            if mode == "IV":
                self.do_iv_measurement(voltage, d_meas, channel)
            elif mode == "Single measurement (averaged)":
                self.do_single_averaged(d_meas, channel)
            else:
                self.log("Unknown mode.")

        self.keithley.reset()
        self.log("\nAll measurements completed.")

    def do_iv_measurement(self, vmax, d_meas, channel):
        n_points = 50
        v_list = np.concatenate([
            np.linspace(0, vmax, n_points),
            np.linspace(vmax, 0, n_points),
            np.linspace(0, -vmax, n_points),
            np.linspace(-vmax, 0, n_points),
        ])
        self.log(f"--- IV sweep (Channel {channel}) ---")
        for v in v_list:
            self.keithley.set_voltage(v)
            time.sleep(d_meas)
            i = self.keithley.measure_current()
            self.log(f"V={v:.3f} V, I={i:.3e} A")
            self.master.update()  # keep the GUI responsive

    def do_single_averaged(self, d_meas, channel):
        readings = []
        self.log(f"--- Averaged single measurement (Channel {channel}) ---")
        for n in range(100):
            i = self.keithley.measure_current()
            readings.append(i)
            self.master.update()
            time.sleep(d_meas)
        avg = np.mean(readings)
        std = np.std(readings)
        self.log(f"Averaged current: {avg:.3e} ± {std:.3e} A")

    def log(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)

# Run the GUI
if __name__ == '__main__':
    root = tk.Tk()
    app = MeasurementApp(root)
    root.mainloop()