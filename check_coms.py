import pyvisa

# Initialize resource manager
rm = pyvisa.ResourceManager()
instruments = rm.list_resources()
print("Available instruments:", instruments)

# Open connection to Keithley_sim.py (Update GPIB address if needed)
try:
    keithley = rm.open_resource('GPIB0::24::INSTR')
    keithley.timeout = 5000  # Set timeout to 5 seconds
    keithley.write('*RST')  # Reset Keithley_sim.py to a known state

    # Query identification to confirm connection
    idn = keithley.query('*IDN?')
    print("Connected to:", idn)

    # Check instrument status
    error_status = keithley.query('SYST:ERR?')
    print("Error Status:", error_status)

    # Perform a simple voltage measurement (adjust for your use case)
    keithley.write('MEAS:VOLT?')  # Request voltage measurement
    voltage = keithley.read()
    print("Measured Voltage:", voltage)

except pyvisa.errors.VisaIOError as e:
    print("VISA Error:", e)
except Exception as e:
    print("General Error:", e)
finally:
    keithley.close()  # Always close connection
    print("Connection closed.")