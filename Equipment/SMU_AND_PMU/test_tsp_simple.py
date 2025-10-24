import pyvisa
import time

# --- Connect to the Keithley 2450 over USB ---
rm = pyvisa.ResourceManager()
address = "USB0::0x05E6::0x2450::04496615::INSTR"  # replace with your USB resource
smu = rm.open_resource(address)
smu.write_termination = '\n'
smu.read_termination = '\n'
smu.timeout = 10000  # ms

print("Connected to:", smu.query("*IDN?"))

# Put instrument in remote mode
smu.write("SYST:REM")

# --- Upload TSP script via SCPI ---
script_name = "pulse_script"

# Delete old script if it exists
smu.write(f'SYSTem:SCRIPT:DELete "{script_name}"')

# Create new script
smu.write(f'SYSTem:SCRIPT:NEW "{script_name}"')

# Define the TSP lines (1 V, 2-second pulse)
script_lines = [
    "smu.source.func = smu.FUNC_DC_VOLTAGE",
    "smu.source.levelv = 1",
    "smu.source.output = smu.OUTPUT_ON",
    "delay(2)",                # hold pulse for 2 seconds
    "smu.source.levelv = 0",
    "smu.source.output = smu.OUTPUT_OFF"
]

# Add lines to the script
for line in script_lines:
    smu.write(f'SYSTem:SCRIPT:ADD "{script_name}","{line}"')

# Save the script
smu.write(f'SYSTem:SCRIPT:SAVE "{script_name}"')

# --- Run the TSP script internally ---
print(f"Running TSP script '{script_name}'...")
smu.write(f'SYSTem:SCRIPT:RUN "{script_name}"')

# Wait for script to finish
time.sleep(3)

# Optional: return front panel to local mode
smu.write("SYST:LOC")

# Close the connection
smu.close()
print("TSP script executed successfully over USB.")
