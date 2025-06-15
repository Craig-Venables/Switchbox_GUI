import pyvisa
import time
import numpy as np


class Lakeshore335Controller:
    """
    Class to control Lakeshore Model 335 Temperature Controller via GPIB.
    Default GPIB address is 12.
    """

    def __init__(self, gpib_address=12, timeout=5000):
        """
        Initialize connection to Lakeshore 335.

        Args:
            gpib_address: GPIB address (default: 12)
            timeout: Communication timeout in milliseconds (default: 5000)
        """
        try:
            self.rm = pyvisa.ResourceManager()
            self.address = f'GPIB0::{gpib_address}::INSTR'
            self.device = self.rm.open_resource(self.address)
            self.device.timeout = timeout

            # Clear any errors
            self.device.clear()

            # Test connection
            idn = self.get_idn()
            print(f"Connected to: {idn}")

            if "335" not in idn:
                print("Warning: Device may not be a Lakeshore 335")

        except Exception as e:
            print(f"Error connecting to Lakeshore 335: {e}")
            self.device = None

    def get_idn(self):
        """Get instrument identification string."""
        if self.device:
            return self.device.query("*IDN?").strip()
        return "Not connected"

    def reset(self):
        """Reset the instrument to default settings."""
        if self.device:
            self.device.write("*RST")
            time.sleep(2)  # Allow time for reset

    def get_temperature(self, channel='A'):
        """
        Read temperature from specified channel.

        Args:
            channel: 'A' or 'B' (default: 'A')

        Returns:
            float: Temperature in Kelvin
        """
        if self.device:
            try:
                temp = float(self.device.query(f"KRDG? {channel}").strip())
                return temp
            except Exception as e:
                print(f"Error reading temperature: {e}")
                return None
        return None

    def get_temperature_celsius(self, channel='A'):
        """
        Read temperature in Celsius.

        Args:
            channel: 'A' or 'B' (default: 'A')

        Returns:
            float: Temperature in Celsius
        """
        temp_k = self.get_temperature(channel)
        if temp_k is not None:
            return temp_k - 273.15
        return None

    def get_sensor_reading(self, channel='A'):
        """
        Get raw sensor reading.

        Args:
            channel: 'A' or 'B' (default: 'A')

        Returns:
            float: Sensor reading in sensor units
        """
        if self.device:
            try:
                reading = float(self.device.query(f"SRDG? {channel}").strip())
                return reading
            except Exception as e:
                print(f"Error reading sensor: {e}")
                return None
        return None

    def get_setpoint(self, output=1):
        """
        Get temperature setpoint for specified output.

        Args:
            output: Output number (1 or 2)

        Returns:
            float: Setpoint temperature in Kelvin
        """
        if self.device:
            try:
                setpoint = float(self.device.query(f"SETP? {output}").strip())
                return setpoint
            except Exception as e:
                print(f"Error reading setpoint: {e}")
                return None
        return None

    def set_setpoint(self, temperature, output=1):
        """
        Set temperature setpoint for specified output.

        Args:
            temperature: Target temperature in Kelvin
            output: Output number (1 or 2)
        """
        if self.device:
            try:
                self.device.write(f"SETP {output},{temperature:.3f}")
                time.sleep(0.1)
                # Verify setpoint was set
                actual = self.get_setpoint(output)
                if actual is not None:
                    print(f"Setpoint {output} set to {actual:.3f} K")
            except Exception as e:
                print(f"Error setting setpoint: {e}")

    def get_heater_output(self, output=1):
        """
        Get heater output percentage.

        Args:
            output: Output number (1 or 2)

        Returns:
            float: Heater output percentage (0-100)
        """
        if self.device:
            try:
                heater = float(self.device.query(f"HTR? {output}").strip())
                return heater
            except Exception as e:
                print(f"Error reading heater output: {e}")
                return None
        return None

    def get_heater_range(self, output=1):
        """
        Get heater range setting.

        Args:
            output: Output number (1 or 2)

        Returns:
            int: Heater range (0=Off, 1=Low, 2=Medium, 3=High)
        """
        if self.device:
            try:
                range_val = int(self.device.query(f"RANGE? {output}").strip())
                return range_val
            except Exception as e:
                print(f"Error reading heater range: {e}")
                return None
        return None

    def set_heater_range(self, range_val, output=1):
        """
        Set heater range.

        Args:
            range_val: 0=Off, 1=Low, 2=Medium, 3=High
            output: Output number (1 or 2)
        """
        if self.device:
            if range_val not in [0, 1, 2, 3]:
                print("Invalid range value. Use 0=Off, 1=Low, 2=Medium, 3=High")
                return

            try:
                self.device.write(f"RANGE {output},{range_val}")
                time.sleep(0.1)
                print(f"Heater range set to {['Off', 'Low', 'Medium', 'High'][range_val]}")
            except Exception as e:
                print(f"Error setting heater range: {e}")

    def get_control_mode(self, output=1):
        """
        Get control mode for specified output.

        Args:
            output: Output number (1 or 2)

        Returns:
            tuple: (mode, input, powerup_enable)
                mode: 1=Manual PID, 2=Zone, 3=Open Loop, 4=AutoTune PID, 5=AutoTune PI, 6=AutoTune P
                input: A or B
                powerup_enable: 0=Off, 1=On
        """
        if self.device:
            try:
                response = self.device.query(f"OUTMODE? {output}").strip()
                parts = response.split(',')
                mode = int(parts[0])
                input_channel = parts[1]
                powerup = int(parts[2])
                return mode, input_channel, powerup
            except Exception as e:
                print(f"Error reading control mode: {e}")
                return None, None, None
        return None, None, None

    def set_control_mode(self, mode, input_channel='A', powerup_enable=1, output=1):
        """
        Set control mode for specified output.

        Args:
            mode: 1=Manual PID, 2=Zone, 3=Open Loop
            input_channel: 'A' or 'B'
            powerup_enable: 0=Off, 1=On
            output: Output number (1 or 2)
        """
        if self.device:
            try:
                self.device.write(f"OUTMODE {output},{mode},{input_channel},{powerup_enable}")
                time.sleep(0.1)
                print(f"Control mode set for output {output}")
            except Exception as e:
                print(f"Error setting control mode: {e}")

    def get_pid(self, output=1):
        """
        Get PID parameters for specified output.

        Args:
            output: Output number (1 or 2)

        Returns:
            tuple: (P, I, D) values
        """
        if self.device:
            try:
                response = self.device.query(f"PID? {output}").strip()
                parts = response.split(',')
                p = float(parts[0])
                i = float(parts[1])
                d = float(parts[2])
                return p, i, d
            except Exception as e:
                print(f"Error reading PID values: {e}")
                return None, None, None
        return None, None, None

    def set_pid(self, p, i, d, output=1):
        """
        Set PID parameters for specified output.

        Args:
            p: Proportional gain
            i: Integral gain
            d: Derivative gain
            output: Output number (1 or 2)
        """
        if self.device:
            try:
                self.device.write(f"PID {output},{p:.1f},{i:.1f},{d:.1f}")
                time.sleep(0.1)
                print(f"PID values set for output {output}: P={p}, I={i}, D={d}")
            except Exception as e:
                print(f"Error setting PID values: {e}")

    def wait_for_temperature(self, target_temp, channel='A', tolerance=0.5,
                             timeout=600, check_interval=5):
        """
        Wait for temperature to reach target within tolerance.

        Args:
            target_temp: Target temperature in Kelvin
            channel: Temperature channel to monitor ('A' or 'B')
            tolerance: Acceptable deviation from target (K)
            timeout: Maximum wait time in seconds
            check_interval: Time between checks in seconds

        Returns:
            bool: True if temperature reached, False if timeout
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            current_temp = self.get_temperature(channel)
            if current_temp is None:
                print("Error reading temperature")
                return False

            deviation = abs(current_temp - target_temp)
            print(f"Current: {current_temp:.2f}K, Target: {target_temp:.2f}K, "
                  f"Deviation: {deviation:.2f}K")

            if deviation <= tolerance:
                print(f"Temperature reached: {current_temp:.2f}K")
                return True

            time.sleep(check_interval)

        print(f"Timeout: Temperature did not reach {target_temp}K within {timeout}s")
        return False

    def get_all_temperatures(self):
        """
        Get temperatures from all channels.

        Returns:
            dict: Dictionary with channel temperatures
        """
        temps = {}
        for channel in ['A', 'B']:
            temp_k = self.get_temperature(channel)
            temp_c = self.get_temperature_celsius(channel)
            temps[channel] = {
                'kelvin': temp_k,
                'celsius': temp_c
            }
        return temps

    def close(self):
        """Close connection to the instrument."""
        if self.device:
            self.device.close()
            print("Connection to Lakeshore 335 closed.")


# Example usage and integration with your existing code
if __name__ == "__main__":
    # Test the controller
    lakeshore = Lakeshore335Controller(gpib_address=12)

    if lakeshore.device:
        # Get current temperatures
        temps = lakeshore.get_all_temperatures()
        print(f"Channel A: {temps['A']['celsius']:.2f}°C")
        print(f"Channel B: {temps['B']['celsius']:.2f}°C")

        # Set a setpoint
        lakeshore.set_setpoint(300, output=1)  # 300K = 26.85°C

        # Get heater status
        heater = lakeshore.get_heater_output(1)
        print(f"Heater output: {heater:.1f}%")

        lakeshore.close()