import pyvisa

"""https://pymeasure.readthedocs.io/en/latest/api/instruments/keithley/keithley2400.html#pymeasure.instruments.keithley.Keithley2400.compliance_current"""

class Keithley2400:
    def __init__(self, gpib_address='GPIB0::24::INSTR', timeout=5000):
        """Initialize connection to Keithley 2400."""
        self.gpib_address = gpib_address
        self.rm = pyvisa.ResourceManager()

        try:
            self.device = self.rm.open_resource(self.gpib_address)
            self.device.timeout = timeout  # Set timeout (default 5s)
            self.device.write('*RST')  # Reset instrument
            print(f"Connected to: {self.get_idn()}")
        except pyvisa.errors.VisaIOError as e:
            print("VISA Error:", e)
            self.device = None
        except Exception as e:
            print("General Error:", e)
            self.device = None

        # keithley.apply_current()  # Sets up to source current
        # keithley.source_current_range = 10e-3  # Sets the source current range to 10 mA
        # keithley.compliance_voltage = 10  # Sets the compliance voltage to 10 V
        # keithley.source_current = 0  # Sets the source current to 0 mA
        # keithley.enable_source()  # Enables the source output
        #
        # keithley.measure_voltage()  # Sets up to measure voltage
        #
        # keithley.ramp_to_current(5e-3)  # Ramps the current to 5 mA
        # print(keithley.voltage)  # Prints the voltage in Volts
        #
        # keithley.shutdown()  # Ramps the current to 0 mA and disables output

        # ramp_to_voltage(target_voltage, steps=30, pause=0.02)
    def beep(self,frequency,duration):
        self.device.beep(frequency,duration)

    def voltage_ramp(self,target_voltage, steps=30, pause=0.02):
        "set voltage ramp"
        self.device.ramp_to_voltage(target_voltage, steps=30, pause=0.02)

    def get_idn(self):
        """Query and return the device identity string."""
        return self.device.query('*IDN?') if self.device else "No Device Connected"

    def check_errors(self):
        """Check and return instrument error status."""
        return self.device.query('SYST:ERR?') if self.device else "No Device Connected"

    def measure_voltage(self):
        """Measure and return voltage."""
        if self.device:
            self.device.write('MEAS:VOLT?')
            return float(self.device.read())
        return None

    def measure_current(self):
        """Measure and return the current reading."""
        response = self.device.query(":READ?")  # Query instead of read() for better handling
        values = response.strip().split(",")  # Split by comma
        try:
            current = float(values[1])  # The second value usually corresponds to current
            return current
        except (IndexError, ValueError):
            raise ValueError(f"Unexpected response format: {response}")

    def set_voltage(self, voltage):
        """Set output voltage."""
        if self.device:
            self.device.write(f'SOUR:VOLT {voltage}')
            #print(f"Voltage set to {voltage}V.")

    def set_current(self, current):
        """Set output current."""
        if self.device:
            self.device.write(f'SOUR:CURR {current}')
            print(f"Current set to {current}A.")

    def enable_output(self, enable=True):
        """Enable or disable output."""
        if self.device:
            state = 1 if enable else 0
            self.device.write(f'OUTP {state}')
            #print(f"Output {'Enabled' if enable else 'Disabled'}.")

    def close(self):
        """Close connection to the instrument."""
        if self.device:
            self.device.close()
            print("Connection closed.")

    def shutdown(self):
        """ Ramps the current to 0 mA and disables output"""
        self.device.shutdown()

# Example Usage
if __name__ == "__main__":
    keithley = Keithley2400()
    print(keithley.get_idn())  # Check connection
    print("Error Status:", keithley.check_errors())

    keithley.set_voltage(5)  # Set voltage to 5V
    print("Measured Voltage:", keithley.measure_voltage())

    keithley.enable_output(False)  # Disable output
    keithley.close()  # Close connection
