import pyvisa
import time
import numpy as np


class Lakeshore335Controller:
    """
    Class to control Lakeshore Model 335 Temperature Controller via GPIB.
    Default GPIB address is 12.
    """

    def __init__(self, gpib_address=17, timeout=5000):
        """
        Initialize connection to Lakeshore 335.
        """
        try:
            self.rm = pyvisa.ResourceManager()
            self.address = f'GPIB0::{gpib_address}::INSTR'
            self.device = self.rm.open_resource(self.address)
            self.device.timeout = timeout
            self.device.clear()
            idn = self.get_idn()
            print(f"Connected to: {idn}")
            if "335" not in idn:
                print("Warning: Device may not be a Lakeshore 335")
        except Exception as e:
            print(f"Error connecting to Lakeshore 335: {e}")
            self.device = None

    def get_idn(self):
        if self.device:
            return self.device.query("*IDN?").strip()
        return "Not connected"

    def reset(self):
        if self.device:
            self.device.write("*RST")
            time.sleep(2)

    def get_temperature(self, channel='A'):
        if self.device:
            try:
                return float(self.device.query(f"KRDG? {channel}").strip())
            except Exception as e:
                print(f"Error reading temperature: {e}")
                return None
        return None

    def get_temperature_celsius(self, channel='A'):
        temp_k = self.get_temperature(channel)
        if temp_k is not None:
            return temp_k - 273.15
        return None

    def get_sensor_reading(self, channel='A'):
        if self.device:
            try:
                return float(self.device.query(f"SRDG? {channel}").strip())
            except Exception as e:
                print(f"Error reading sensor: {e}")
                return None
        return None

    def get_setpoint(self, output=1):
        if self.device:
            try:
                return float(self.device.query(f"SETP? {output}").strip())
            except Exception as e:
                print(f"Error reading setpoint: {e}")
                return None
        return None

    def set_setpoint(self, temperature, output=1):
        if self.device:
            try:
                self.device.write(f"SETP {output},{temperature:.3f}")
                time.sleep(0.1)
            except Exception as e:
                print(f"Error setting setpoint: {e}")

    def get_heater_output(self, output=1):
        if self.device:
            try:
                return float(self.device.query(f"HTR? {output}").strip())
            except Exception as e:
                print(f"Error reading heater output: {e}")
                return None
        return None

    def get_heater_range(self, output=1):
        if self.device:
            try:
                return int(self.device.query(f"RANGE? {output}").strip())
            except Exception as e:
                print(f"Error reading heater range: {e}")
                return None
        return None

    def set_heater_range(self, range_val, output=1):
        if self.device:
            if range_val not in [0, 1, 2, 3]:
                print("Invalid range value. Use 0=Off, 1=Low, 2=Medium, 3=High")
                return
            try:
                self.device.write(f"RANGE {output},{range_val}")
                time.sleep(0.1)
            except Exception as e:
                print(f"Error setting heater range: {e}")

    def get_control_mode(self, output=1):
        if self.device:
            try:
                response = self.device.query(f"OUTMODE? {output}").strip()
                parts = response.split(',')
                return int(parts[0]), parts[1], int(parts[2])
            except Exception as e:
                print(f"Error reading control mode: {e}")
                return None, None, None
        return None, None, None

    def set_control_mode(self, mode, input_channel='A', powerup_enable=1, output=1):
        if self.device:
            try:
                self.device.write(f"OUTMODE {output},{mode},{input_channel},{powerup_enable}")
                time.sleep(0.1)
            except Exception as e:
                print(f"Error setting control mode: {e}")

    def get_pid(self, output=1):
        if self.device:
            try:
                response = self.device.query(f"PID? {output}").strip()
                parts = response.split(',')
                return float(parts[0]), float(parts[1]), float(parts[2])
            except Exception as e:
                print(f"Error reading PID values: {e}")
                return None, None, None
        return None, None, None

    def set_pid(self, p, i, d, output=1):
        if self.device:
            try:
                self.device.write(f"PID {output},{p:.1f},{i:.1f},{d:.1f}")
                time.sleep(0.1)
            except Exception as e:
                print(f"Error setting PID values: {e}")

    def wait_for_temperature(self, target_temp, channel='A', tolerance=0.5, timeout=600, check_interval=5):
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            current_temp = self.get_temperature(channel)
            if current_temp is None:
                print("Error reading temperature")
                return False
            deviation = abs(current_temp - target_temp)
            if deviation <= tolerance:
                return True
            time.sleep(check_interval)
        return False

    def get_all_temperatures(self):
        temps = {}
        for channel in ['A', 'B']:
            temp_k = self.get_temperature(channel)
            temp_c = self.get_temperature_celsius(channel)
            temps[channel] = {'kelvin': temp_k, 'celsius': temp_c}
        return temps

    def close(self):
        if self.device:
            self.device.close()
            print("Connection to Lakeshore 335 closed.")



