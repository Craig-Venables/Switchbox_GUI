import pyvisa
import time


class Keithley2220_Powersupply:
    """ simple class for controlling the PSU """
    def __init__(self, visa_address):
        """Initialize the Keithley 2220-30-1 Power Supply with a specified address."""
        self.rm = pyvisa.ResourceManager()
        self.instrument = None

        try:
            self.instrument = self.rm.open_resource(visa_address)
            self.instrument.timeout = 5000  # Set timeout to 5 seconds
            print(f"Connected to PSU: {self.get_id()}")
        except Exception as e:
            print(f"Failed to connect to {visa_address}: {e}")

        self.remote()

    def get_id(self):
        """Query the power supply identity."""
        return self.instrument.query("*IDN?").strip()

    def reset(self):
        """Reset the power supply to default settings."""
        self.instrument.write("*RST")
        print("Power supply reset.")

    def set_voltage(self, channel, voltage):
        """Set voltage for a specific channel (1 or 2)."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write(f"VOLT {voltage}")

    def set_current(self, channel, current):
        """Set current limit for a specific channel."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write(f"CURR {current}")
        print(f"Set current limit on CH{channel} to {current}A")

    def get_voltage(self, channel):
        """Read the set voltage of a specific channel."""
        self.instrument.write(f"INST CH{channel}")
        return float(self.instrument.query("VOLT?"))

    def get_current(self, channel):
        """Read the set current limit of a specific channel."""
        self.instrument.write(f"INST CH{channel}")
        return float(self.instrument.query("CURR?"))

    def get_output_voltage(self, channel):
        """Read the actual measured output voltage."""
        self.instrument.write(f"INST CH{channel}")
        return float(self.instrument.query("MEAS:VOLT?"))

    def get_output_current(self, channel):
        """Read the actual measured output current."""
        self.instrument.write(f"INST CH{channel}")
        return float(self.instrument.query("MEAS:CURR?"))

    def enable_channel(self, channel):
        """Enable output on a specific channel."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write("OUTP ON")

    def disable_channel(self, channel):
        """Disable output on a specific channel."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write("OUTP OFF")

    def is_output_on(self, channel):
        """Check if the output is enabled for a specific channel."""
        self.instrument.write(f"INST CH{channel}")
        return bool(int(self.instrument.query("OUTP?")))

    def set_overvoltage_protection(self, channel, voltage):
        """Set overvoltage protection (OVP) for a channel."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write(f"VOLT:PROT {voltage}")
        print(f"Set OVP on CH{channel} to {voltage}V")

    def enable_ovp(self, channel):
        """Enable overvoltage protection (OVP) for a channel."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write("VOLT:PROT:STAT ON")
        print(f"OVP enabled on CH{channel}")

    def disable_ovp(self, channel):
        """Disable overvoltage protection (OVP) for a channel."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write("VOLT:PROT:STAT OFF")
        print(f"OVP disabled on CH{channel}")

    def set_ocp(self, channel, current):
        """Set overcurrent protection (OCP) level."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write(f"CURR:PROT {current}")
        print(f"Set OCP on CH{channel} to {current}A")

    def enable_ocp(self, channel):
        """Enable overcurrent protection (OCP) for a channel."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write("CURR:PROT:STAT ON")
        print(f"OCP enabled on CH{channel}")

    def disable_ocp(self, channel):
        """Disable overcurrent protection (OCP) for a channel."""
        self.instrument.write(f"INST CH{channel}")
        self.instrument.write("CURR:PROT:STAT OFF")
        print(f"OCP disabled on CH{channel}")

    def close(self):
        """Close the connection to the power supply."""
        self.instrument.close()
        print("Connection closed.")

    def remote(self):
        self.instrument.write("SYST:REM")

    def led_on_380(self, power):
        power = min(max(power, 0.01), 1.0)
        max_voltage = 3.45
        min_voltage = 3.0
        diff = max_voltage - min_voltage
        applied_v = min_voltage + (power * diff)
        self.set_voltage(1, applied_v)
        self.enable_channel(1)
        print("applied_v", applied_v)

    def led_off_380(self):
        self.disable_channel(1)

if __name__ == "__main__":
    visa_address = "USB0::0x05E6::0x2220::9210734::INSTR"
    psu = Keithley2220_Powersupply(visa_address)
    if psu.instrument:
        psu.set_voltage(1, 3)
        psu.set_current(1, 0.5)
        psu.enable_channel(1)
        time.sleep(2)
        print("Output Voltage CH1:", psu.get_output_voltage(1))
        print("Output Current CH1:", psu.get_output_current(1))
        psu.disable_channel(1)
        psu.close()

