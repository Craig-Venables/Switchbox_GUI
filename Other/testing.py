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
