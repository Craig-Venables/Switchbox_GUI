from pymeasure.instruments.keithley import Keithley2400
import time
"""https://pymeasure.readthedocs.io/en/latest/api/instruments/keithley/keithley2400.html#pymeasure.instruments.keithley.Keithley2400.compliance_current"""


class Keithley2400Controller:
    def __init__(self, gpib_address='GPIB0::24::INSTR', timeout=5):
        """Initialize connection to Keithley 2400 via PyMeasure."""
        try:
            self.device = Keithley2400(gpib_address)
            self.device.adapter.connection.timeout = timeout * 1000  # Convert to milliseconds
            self.device.reset()  # Reset the instrument
            print(f"Connected to: {self.get_idn()}")

            print(self.get_idn())
        except Exception as e:
            print("Error initializing Keithley 2400:", e)
            self.device = None

    def get_idn(self):
        """Query and return the device identity string."""
        return self.device.id if self.device else "No Device Connected"

    def check_errors(self):
        """Check instrument error status."""
        return self.device.ask('SYST:ERR?') if self.device else "No Device Connected"

    def set_voltage(self, voltage, Icc=0.1):
        """Set output voltage and enable source mode."""
        if self.device:

            self.device.apply_voltage(voltage_range=20, compliance_current=Icc)  # Set compliance current
            self.device.source_voltage = voltage

    def set_current(self, current, Vcc = 10):
        """Set output current and enable source mode."""
        if self.device:
            self.device.apply_current(current_range=10e-3, compliance_voltage=Vcc)  # Set compliance voltage
            self.device.source_current = current

    def measure_voltage(self):
        """Measure and return voltage."""
        return self.device.voltage if self.device else None

    def measure_current(self):
        """Measure and return current."""
        return self.device.current if self.device else None

    def enable_output(self, enable=True):
        """Enable or disable output."""
        if self.device:
            self.device.enable_source() if enable else self.device.disable_source()

    def beep(self, frequency=1000, duration=0.5):
        """Make the instrument beep."""
        if self.device:
            self.device.write(f'SYST:BEEP {frequency}, {duration}')

    def voltage_ramp(self, target_voltage, steps=30, pause=0.02):
        """Ramp voltage gradually to avoid sudden spikes."""
        if not self.device:
            print("No Device Connected.")
            return
        current_voltage = self.device.source_voltage
        voltage_step = (target_voltage - current_voltage) / steps

        for i in range(steps):
            self.device.source_voltage = current_voltage + (i + 1) * voltage_step
            time.sleep(pause)

    def shutdown(self):
        """Ramp current to 0 mA and disable output."""
        if self.device:
            self.device.source_current = 0
            self.device.disable_source()

    def close(self):
        """Close connection to the instrument."""
        if self.device:
            self.device.shutdown()
            print("Connection closed.")

# Example Usage
if __name__ == "__main__":
    keithley = Keithley2400Controller()  # Connect to the device
    print("Device ID:", keithley.device.id)  # Check connection

    # Test beep function using PyMeasure interface
    keithley.beep(100, 0.5)
    keithley.beep(1000, 0.5)
    keithley.beep(10000, 0.5)
    keithley.beep(100000, 0.5)

    keithley.close()