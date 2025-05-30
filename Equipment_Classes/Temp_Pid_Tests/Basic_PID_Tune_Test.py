import pyvisa
from pyvisa.constants import StopBits, Parity
import time
import matplotlib.pyplot as plt

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

    # def set_heater_sensor(self,num = '2'):
    #     return self.inst.query(f'H{num}').strip()

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



def parse_resp(resp):
    try:
        val_str = resp.lstrip("R")
        val = int(val_str) / 10
        return val
    except:
        return float('nan')

def run_pid_test(itc, P, I, D, set_temp, max_duration=600, tolerance=0.5):
    print(f"\n--- Testing PID: P={P}, I={I}, D={D} ---")

    # Set PID values
    itc.set_prop_band(P)
    itc.set_integral_time(I)
    itc.set_deriv_action_time(D)
    itc.set_temperature(set_temp)

    # Live plot setup
    plt.clf()
    fig, ax = plt.subplots()
    line_temp, = ax.plot([], [], label="Sensor 2 Temp")
    line_setp, = ax.plot([], [], label="Setpoint", linestyle='--')
    ax.legend()
    plt.title(f"P={P}, I={I}, D={D}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Temperature (°C)")
    plt.ion()

    times, temps, setpoints = [], [], []
    t0 = time.time()

    while time.time() - t0 < max_duration:
        now = time.time() - t0
        t_raw = itc.read_param(2)
        s_raw = itc.read_param(0)
        t_val = parse_resp(t_raw.replace("+", "").replace("-", "-"))
        s_val = parse_resp(s_raw.replace("+", "").replace("-", "-"))

        times.append(now)
        temps.append(t_val)
        setpoints.append(s_val)

        print(f"Time={now:.1f}s Temp={t_val:.2f}°C Set={s_val:.2f}°C")

        # Plot update
        line_temp.set_data(times, temps)
        line_setp.set_data(times, setpoints)
        ax.relim()
        ax.autoscale_view()
        plt.pause(0.01)

        # Exit early if stable
        if len(temps) > 30 and all(abs(t - set_temp) < tolerance for t in temps[-10:]):
            print("System settled.")

            break

        time.sleep(1)

    try:
        plt.savefig(f"pid_test_P{P}_I{I}_D{D}.png")
    except:
        print("unable to save")


    plt.close()

    # Performance metrics
    overshoot = max(temps) - set_temp
    settle_time = times[-1]
    print(f"➡️ Overshoot: {overshoot:.2f}°C | Settle time: {settle_time:.1f}s")
    return {"P": P, "I": I, "D": D, "overshoot": overshoot, "settle_time": settle_time}

def wait_for_cooldown(itc, cool_temp=25, interval=30):
    print("\n🌡️ Cooling down...")
    while True:
        itc.set_deriv_action_time(00)
        itc.set_temperature(0)
        t_raw = itc.read_param(2)
        t_val = parse_resp(t_raw.replace("+", "").replace("-", "-"))
        print(f"Current Temp: {t_val:.2f}°C")
        if t_val <= cool_temp:
            print("✅ Cool enough. Continuing.")
            break
        time.sleep(interval)

import pyvisa
from pyvisa.constants import StopBits, Parity
import time
import matplotlib.pyplot as plt
import itertools
import csv


if __name__ == "__main__":
    itc = OxfordITC4(port='ASRL12::INSTR')


    # Set remote and prepare heater
    itc.set_control_mode(3)
    itc.set_display_param(2)
    itc.set_auto_manual_heater_gas(0)
    itc.set_sensor(2)
    itc.set_max_heater_volts(200)  # 400 max in "1=0.1v"
    itc.set_auto_manual_heater_gas(1)
    itc.start_stop_sweep("0")

    # PID grid to try
    P_vals = [0.8]
    I_vals = [10,20]
    D_vals = [0]
    set_temp = 40
    cool_temp = 25

    results = []

    for P, I, D in itertools.product(P_vals, I_vals, D_vals):
        result = run_pid_test(itc, P, I, D, set_temp=set_temp)
        results.append(result)

        wait_for_cooldown(itc, cool_temp=cool_temp)

    # Save CSV
    with open("pid_tuning_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    # Select best PID (simple score: lower is better)
    best = min(results, key=lambda r: (r["overshoot"]**2 + r["settle_time"]))
    print(f"\n✅ Best PID Settings:\nP={best['P']}  I={best['I']}  D={best['D']}")

    itc.close()
    plt.ioff()
    plt.show()
