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

        print("setting up system")
        # set up
        self.set_control_mode(3) # UNLOCK system
        self.set_display_param(2) # set display to read sensor 2
        self.set_auto_manual_heater_gas(0) # set heater manual
        self.set_sensor(2) # set heater to 2

        self.set_max_heater_volts(200) # 400 max in "1=0.1v"
        self.set_auto_manual_heater_gas(1) # SET HEATER TOO AUTO
        self.start_stop_sweep("0") # Stop any sweeps that may start
        temp = self.read_param(2)
        print("Current temperature:", temp)
        print("Setting temperature to 0C:", self.set_temperature(35))

        # Set pid controlls
        self.set_prop_band(1.8)
        self.set_integral_time(30) #x10 for some reason
        self.set_deriv_action_time(10) # 0 saw 0.2 overshoot
        print("system ready")


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

        # Just add these methods at the end:

    def get_temperature_celsius(self, channel='A'):
        """Wrapper to match the common interface"""
        # Channel mapping: A=1, B=2, C=3
        channel_map = {'A': 1, 'B': 2, 'C': 3}
        sensor = channel_map.get(channel.upper(), 2)  # Default to sensor 2

        temp_raw = self.read_param(sensor)
        try:
            # Parse response (e.g., "R+00253" -> 25.3°C)
            val_str = temp_raw.lstrip("R").replace("+", "").replace("-", "-")
            temp_c = int(val_str) / 10
            return temp_c
        except:
            return 25.0

    def get_idn(self):
        """Get identification string"""
        return f"Oxford ITC4 - {self.read_version()}"

    # Utility
    def close(self):
        self.inst.close()
        self.rm.close()


# --------- TEST SCRIPT ---------
if __name__ == "__main__":
    itc = OxfordITC4(port='ASRL12::INSTR')  # Change ASRL12::INSTR to your correct port




    # # UNLOCK system
    # itc.set_control_mode(3)
    #
    # # set display to read sensor 2
    # itc.set_display_param(2)
    #
    # # set heater manual
    # itc.set_auto_manual_heater_gas(0)
    #
    # # set heater to 2
    # print(itc.set_sensor(2))
    #
    # # SET HEATER TOO AUTO
    # itc.set_auto_manual_heater_gas(1)
    #
    # # Stop any sweeps that may start
    # itc.start_stop_sweep("0")
    #
    # t = itc.read_param(2)
    # print("Reading current temperature:",t)
    #
    # # set pid controlls
    # itc.set_prop_band(0.8)
    # itc.set_integral_time(0.4)
    # itc.set_deriv_action_time(0.3)

    # Quick test: Set temperature to 30C
    #print("Setting temperature to xC:", itc.set_temperature(0))

    # this massively overshoots the intended tempriture


    # --- Plotting Setup ---
    import matplotlib.pyplot as plt

    times = []
    temps = []
    setpoints = []

    plt.ion()  # Turn on interactive mode
    fig, ax = plt.subplots()
    line_temp, = ax.plot([], [], label="Sensor 2 Temp")
    line_setp, = ax.plot([], [], label="Setpoint", linestyle='--')
    ax.legend()
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Temperature (°C)")
    t0 = time.time()

    x = True
    while x:
        now = time.time() - t0

        # Read/parse temperature and setpoint
        def parse_resp(resp):
            try:
                # e.g. R+00253
                val_str = resp.lstrip("R")
                val = int(val_str) / 10
                return val
            except:
                return float('nan')

        t_raw = itc.read_param(2)
        setp_raw = itc.read_param(0)
        t_val = parse_resp(t_raw.replace("+", "").replace("-", "-"))
        setp_val = parse_resp(setp_raw.replace("+", "").replace("-", "-"))

        # Store for plot
        times.append(now)
        temps.append(t_val)
        setpoints.append(setp_val)

        # Print values
        print(f"Current temperature: {t_val} °C")
        print(f"Set temperature: {setp_val} °C")

        # Update plot
        line_temp.set_data(times, temps)
        line_setp.set_data(times, setpoints)
        ax.relim()
        ax.autoscale_view()
        plt.pause(0.01)

        time.sleep(1)

    itc.close()
    plt.ioff()
    plt.show()

