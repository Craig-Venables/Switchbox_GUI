from __future__ import annotations

import math
import random


class FakeMemristorInstrument:
    """A simulated instrument for offline testing.

    Modes:
      - 'ohmic': linear I = V/R
      - 'memristive': exhibits hysteresis with state-dependent conductance
      - 'forming': starts ohmic-low until a voltage threshold then switches to memristive
    """

    def __init__(self, mode: str = 'memristive'):
        self.mode = mode
        self.enabled = False
        self.voltage_v = 0.0
        self.state = 0.0  # internal state for memristive behavior
        self.formed = mode != 'forming'
        self.R_ohmic = 1e9

    # Minimal API to match Keithley2400Controller usage pattern
    def set_voltage(self, voltage, Icc=50e-6):
        self.voltage_v = float(voltage)

    def enable_output(self, enable=True):
        self.enabled = enable

    def measure_current(self):
        v = self.voltage_v if self.enabled else 0.0
        # Forming behavior
        if not self.formed and abs(v) > 2.0:
            self.formed = True
            self.mode = 'memristive'
        if self.mode == 'ohmic':
            return v / self.R_ohmic + random.gauss(0, 1e-12)
        elif self.mode == 'memristive':
            # simple hysteresis via state integration
            self.state += 0.01 * v - 0.001 * self.state
            g = 1e-7 + 2e-6 * (1 / (1 + math.exp(-self.state)))
            return g * v + random.gauss(0, 1e-12)
        elif self.mode == 'forming':
            return v / self.R_ohmic + random.gauss(0, 1e-12)
        return 0.0

import pyvisa
import time

# Initialize VISA resource manager
rm = pyvisa.ResourceManager()

# Replace this with the actual resource name from rm.list_resources()
keithley = rm.open_resource("USB0::0x05E6::0x2220::9210734::INSTR")

# Set channel (1 or 2, depending on where your LED is connected)
CHANNEL = 1
VOLTAGE = 2.5  # Adjust to your LED's requirements
CURRENT_LIMIT = 0.5  # Set a safe limit to protect the LED

# Configure the power supply
keithley.write(f"INST CH{CHANNEL}")  # Select channel
keithley.write(f"VOLT {VOLTAGE}")  # Set voltage
keithley.write(f"CURR {CURRENT_LIMIT}")  # Set current limit

while True:
    command = input("Enter 'ON' to turn LED on, 'OFF' to turn it off, 'EXIT' to quit: ").strip().upper()

    if command == "ON":
        keithley.write("OUTP ON")  # Enable output
        print("LED ON")
    elif command == "OFF":
        keithley.write("OUTP OFF")  # Disable output
        print("LED OFF")
    elif command == "EXIT":
        break
    else:
        print("Invalid command. Use 'ON', 'OFF', or 'EXIT'.")

# Turn off output and close connection
keithley.write("OUTP OFF")
keithley.close()
print("Connection closed.")
