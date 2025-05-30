import pyvisa
from pyvisa.constants import StopBits, Parity
import time
import matplotlib.pyplot as plt
import threading
import threading
import time
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
class OxfordITC4:
    def __init__(self, port='ASRL12::INSTR', baudrate=9600, timeout=2000):
        self.rm = pyvisa.ResourceManager('@py')
        self.inst = self.rm.open_resource(port)
        self.inst.baud_rate = baudrate
        self.inst.data_bits = 8
        self.inst.stop_bits = StopBits.one
        self.inst.parity = Parity.none
        self.inst.write_termination = '\r'
        self.inst.read_termination = '\r'
        self.inst.timeout = timeout




    # MONITOR COMMANDS
    def set_control_mode(self, mode="3"):
        """C0=LOCAL, C1=REMOTE, C2=LOCK, C3=REMOTE/UNLOCK"""
        return self.inst.query(f'C{mode}').strip()

    def define_com_protocol(self, proto):
        return self.inst.query(f'D{proto}').strip()

    def read_param(self, n):
        return self.inst.query(f'R{n}').strip()

    def unlock(self, key):
        """Unlock for I and SYSTEM commands"""
        return self.inst.query(str(key)).strip()

    def read_version(self):
        return self.inst.query('V').strip()

    def examine_status(self):
        return self.inst.query('X').strip()

    # CONTROL COMMANDS (Requires remote/unlocked)
    def set_auto_manual_heater_gas(self, mode='0'):
        """ HEATER/GAS
        A0=MAN/MAN, A1=AUTO/MAN, A2 = MAN/AUTO, A3 =AUTO/AUTO etc."""
        return self.inst.query(f'A{mode}').strip()

    def set_deriv_action_time(self, value):
        return self.inst.query(f'D{value}').strip()

    def set_display_param(self, n):
        return self.inst.query(f'F{n}').strip()

    def set_gas_flow(self, value):
        return self.inst.query(f'G{value}').strip()

    def set_sensor(self, sensor_num = '2'):
        return self.inst.query(f'H{sensor_num}').strip()

    def set_integral_time(self, value):
        return self.inst.query(f'I{value}').strip()

    def set_max_heater_volts(self, value):
        return self.inst.query(f'M{value}').strip()

    def set_output_volt_manual(self, value):
        return self.inst.query(f'N{value}').strip()

    def set_prop_band(self, value):
        return self.inst.query(f'P{value}').strip()

    def start_stop_sweep(self, action):
        return self.inst.query(f'S{action}').strip()

    def set_temperature(self, temp_c):
        """Set temperature in deg C, in tenths, as an integer."""
        n = int(round(temp_c * 10))
        cmd = f'T{n}'
        return self.inst.query(cmd).strip()

    # SYSTEM COMMANDS (require unlock)
    def load_lineariser_table(self, n):
        return self.inst.query(f'L{n}').strip()

    def load_entire_ram(self):
        return self.inst.query('S').strip()

    def dump_entire_ram(self):
        return self.inst.query('Z').strip()

    def set_isobus_address(self, address):
        return self.inst.query(f'!{address}').strip()

    # Utility
    def close(self):
        self.inst.close()
        self.rm.close()
def parse_temp(resp):
    try:
        val_str = resp.lstrip("R+")
        if val_str.startswith("-"):
            val = -int(val_str[1:])
        else:
            val = int(val_str)
        return val / 10.0
    except Exception:
        return float('nan')

class ITC4GUI:
    def __init__(self, itc):
        self.itc = itc
        self.running = True

        # Data buffers
        self.times = []
        self.temps = []
        self.setpoints = []
        self.t0 = time.time()

        # Set up Tkinter
        self.root = tk.Tk()
        self.root.title("Oxford ITC4 Controller")

        # Setpoint Entry
        tk.Label(self.root, text="Setpoint (°C):").grid(row=0, column=0, sticky="e")
        self.setpoint_entry = tk.Entry(self.root, width=10)
        self.setpoint_entry.grid(row=0, column=1)
        tk.Button(self.root, text="Set", command=self.set_setpoint).grid(row=0, column=2)

        # PID Entries
        tk.Label(self.root, text="P:").grid(row=1, column=0, sticky="e")
        self.P_entry = tk.Entry(self.root, width=7)
        self.P_entry.grid(row=1, column=1)
        tk.Label(self.root, text="I:").grid(row=1, column=2, sticky="e")
        self.I_entry = tk.Entry(self.root, width=7)
        self.I_entry.grid(row=1, column=3)
        tk.Label(self.root, text="D:").grid(row=1, column=4, sticky="e")
        self.D_entry = tk.Entry(self.root, width=7)
        self.D_entry.grid(row=1, column=5)
        tk.Button(self.root, text="Send PID", command=self.send_pid).grid(row=1, column=6)

        # Live info
        self.current_label = tk.Label(self.root, text="Temp: --  Setpoint: --")
        self.current_label.grid(row=2, column=0, columnspan=7)

        # Matplotlib Figure
        self.fig, self.ax = plt.subplots(figsize=(6,3))
        self.line_temp, = self.ax.plot([], [], label='Temperature', color='blue')
        self.line_setp, = self.ax.plot([], [], label='Setpoint', color='red', linestyle='--')
        self.ax.legend()
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Temperature (°C)")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().grid(row=10, column=0, columnspan=7)

        # Start polling thread
        threading.Thread(target=self.polling_loop, daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def polling_loop(self):
        while self.running:
            now = time.time() - self.t0
            temp_raw = self.itc.read_param(2)
            setp_raw = self.itc.read_param(0)
            temp = parse_temp(temp_raw)
            setp = parse_temp(setp_raw)
            self.times.append(now)
            self.temps.append(temp)
            self.setpoints.append(setp)
            # Limit history for RAM
            if len(self.times) > 2000:
                self.times, self.temps, self.setpoints = self.times[-200:], self.temps[-200:], self.setpoints[-200:]
            # Update plot
            self.line_temp.set_data(self.times, self.temps)
            self.line_setp.set_data(self.times, self.setpoints)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()
            # Update live label
            self.current_label.config(text=f"Temp: {temp:.2f} °C   Setpoint: {setp:.2f} °C")
            time.sleep(1)  # Sampling interval

    def set_setpoint(self):
        try:
            val = float(self.setpoint_entry.get())
            print("Setting setpoint to", val)
            self.itc.set_temperature(val)
        except Exception as e:
            print("Setpoint error:", e)

    def send_pid(self):
        try:
            P = float(self.P_entry.get())
            I = float(self.I_entry.get())
            D = float(self.D_entry.get())
            print(f"Setting PID: P={P}, I={I}, D={D}")
            self.itc.set_prop_band(P)
            self.itc.set_integral_time(I)
            self.itc.set_deriv_action_time(D)
        except Exception as e:
            print("PID error:", e)

    def on_close(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    # YOUR DEVICE SETUP AND CLASS HERE
    # Example:
    itc = OxfordITC4(port='ASRL12::INSTR')
    itc.set_control_mode(3)
    itc.set_display_param(2)
    itc.set_auto_manual_heater_gas(0)
    itc.set_max_heater_volts(200)
    itc.set_sensor(2)
    itc.set_auto_manual_heater_gas(1)
    itc.start_stop_sweep("0")
    itc.set_temperature(30.0)
    # --- launch GUI ---
    ITC4GUI(itc)
    itc.close()