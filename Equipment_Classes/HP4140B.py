import pyvisa
import time
import numpy as np


class HP4140BController:
    def __init__(self, gpib_address='GPIB0::17::INSTR', timeout=5):
        """Initialize connection to HP4140B via PyVISA."""
        try:
            self.rm = pyvisa.ResourceManager()
            self.device = self.rm.open_resource(gpib_address)
            self.device.timeout = timeout * 1000  # Convert to milliseconds

            # Reset and configure the instrument
            self.device.write('*RST')
            time.sleep(1)
            self.device.write('*CLS')  # Clear status

            print(f"Connected to: {self.get_idn()}")

        except Exception as e:
            print("Error initializing HP4140B:", e)
            self.device = None

    def get_idn(self):
        """Query and return the device identity string."""
        try:
            return self.device.query('*IDN?').strip() if self.device else "No Device Connected"
        except:
            return "HP4140B (ID query not supported)"

    def check_errors(self):
        """Check instrument error status."""
        try:
            return self.device.query('*ESR?') if self.device else "No Device Connected"
        except:
            return "Error query not supported"

    def set_voltage(self, voltage, compliance_current=0.1):
        """Set output voltage and compliance current."""
        if self.device:
            # Set SMU1 to voltage source mode
            self.device.write('CN 1')  # Channel 1
            self.device.write('DV 1,0,{},{}'.format(voltage, compliance_current))
            self.device.write('DI 1')  # Set to immediate execution

    def set_current(self, current, compliance_voltage=10):
        """Set output current and compliance voltage."""
        if self.device:
            # Set SMU1 to current source mode
            self.device.write('CN 1')  # Channel 1
            self.device.write('DI 1,0,{},{}'.format(current, compliance_voltage))
            self.device.write('DV 1')  # Set to immediate execution

    def measure_voltage(self):
        """Measure and return voltage."""
        if not self.device:
            return None
        try:
            self.device.write('TV 1,0')  # Trigger voltage measurement on channel 1
            result = self.device.query('DO 1').strip()
            # Parse the result - HP4140B returns status,voltage,current
            parts = result.split(',')
            if len(parts) >= 2:
                return float(parts[1])
            return None
        except Exception as e:
            print(f"Error measuring voltage: {e}")
            return None

    def measure_current(self):
        """Measure and return current."""
        if not self.device:
            return None
        try:
            self.device.write('TI 1,0')  # Trigger current measurement on channel 1
            result = self.device.query('DO 1').strip()
            # Parse the result - HP4140B returns status,voltage,current
            parts = result.split(',')
            if len(parts) >= 3:
                return float(parts[2])
            return None
        except Exception as e:
            print(f"Error measuring current: {e}")
            return None

    def measure_both(self):
        """Measure and return both voltage and current."""
        if not self.device:
            return None, None
        try:
            self.device.write('TV 1,0; TI 1,0')  # Trigger both measurements
            result = self.device.query('DO 1').strip()
            parts = result.split(',')
            if len(parts) >= 3:
                return float(parts[1]), float(parts[2])  # voltage, current
            return None, None
        except Exception as e:
            print(f"Error measuring: {e}")
            return None, None

    def enable_output(self, enable=True):
        """Enable or disable output."""
        if self.device:
            if enable:
                self.device.write('CN 1')  # Enable channel 1
            else:
                self.device.write('CL 1')  # Disable channel 1

    def beep(self, frequency=1000, duration=0.5):
        """Make the instrument beep (if supported)."""
        if self.device:
            try:
                # HP4140B may not support beep, but we can try
                self.device.write('BEEP')
            except:
                print("Beep not supported on this instrument")

    def voltage_ramp(self, target_voltage, steps=30, pause=0.02, compliance_current=0.1):
        """Ramp voltage gradually to avoid sudden spikes."""
        if not self.device:
            print("No Device Connected.")
            return

        # Get current voltage by measuring
        current_voltage = self.measure_voltage()
        if current_voltage is None:
            current_voltage = 0

        voltage_step = (target_voltage - current_voltage) / steps

        for i in range(steps):
            new_voltage = current_voltage + (i + 1) * voltage_step
            self.set_voltage(new_voltage, compliance_current)
            time.sleep(pause)

    def current_ramp(self, target_current, steps=30, pause=0.02, compliance_voltage=10):
        """Ramp current gradually to avoid sudden spikes."""
        if not self.device:
            print("No Device Connected.")
            return

        # Get current by measuring
        current_current = self.measure_current()
        if current_current is None:
            current_current = 0

        current_step = (target_current - current_current) / steps

        for i in range(steps):
            new_current = current_current + (i + 1) * current_step
            self.set_current(new_current, compliance_voltage)
            time.sleep(pause)

    def iv_sweep(self, start_voltage, stop_voltage, points=101, compliance_current=0.1, delay=0.01):
        """Perform an I-V sweep and return voltage and current arrays."""
        if not self.device:
            print("No Device Connected.")
            return None, None

        voltages = np.linspace(start_voltage, stop_voltage, points)
        measured_voltages = []
        measured_currents = []

        self.enable_output(True)

        try:
            for voltage in voltages:
                self.set_voltage(voltage, compliance_current)
                time.sleep(delay)
                v_meas, i_meas = self.measure_both()
                if v_meas is not None and i_meas is not None:
                    measured_voltages.append(v_meas)
                    measured_currents.append(i_meas)
                else:
                    measured_voltages.append(voltage)
                    measured_currents.append(0)

        except KeyboardInterrupt:
            print("Sweep interrupted by user")
        finally:
            self.shutdown()

        return np.array(measured_voltages), np.array(measured_currents)

    def shutdown(self):
        """Ramp to 0V and disable output."""
        if self.device:
            try:
                # Ramp voltage to 0 safely
                self.voltage_ramp(0, steps=10, pause=0.1)
                time.sleep(0.5)
                self.enable_output(False)
                print("Output disabled and ramped to 0V")
            except Exception as e:
                print(f"Error during shutdown: {e}")

    def close(self):
        """Close connection to the instrument."""
        if self.device:
            self.shutdown()
            self.device.close()
            self.rm.close()
            print("Connection closed.")


# Example Usage
if __name__ == "__main__":
    hp4140b = HP4140BController(gpib_address='GPIB0::17::INSTR')  # Adjust address as needed

    if hp4140b.device:
        print("Device ID:", hp4140b.get_idn())

        # Enable output
        hp4140b.enable_output(True)

        # Set voltage and measure current
        hp4140b.set_voltage(1.0, compliance_current=0.01)  # 1V with 10mA compliance
        time.sleep(0.1)

        voltage = hp4140b.measure_voltage()
        current = hp4140b.measure_current()
        print(f"Voltage: {voltage}V, Current: {current}A")

        # Perform a simple I-V sweep
        print("Performing I-V sweep...")
        voltages, currents = hp4140b.iv_sweep(-1, 1, points=21, compliance_current=0.01)

        if voltages is not None:
            print("Sweep completed. Sample data:")
            for i in range(0, len(voltages), 5):  # Print every 5th point
                print(f"V: {voltages[i]:.3f}V, I: {currents[i] * 1000:.3f}mA")

    hp4140b.close()