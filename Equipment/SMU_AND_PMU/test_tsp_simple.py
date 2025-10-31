import pyvisa
import time

rm = pyvisa.ResourceManager()
keithley = rm.open_resource("GPIB0::15::INSTR")

# Optional reset
keithley.write("*RST")
time.sleep(1)

# Combine script into one string to avoid line breaks between writes
tsp_script = """
loadscript SimpleSweep

function SimpleSweep()
    reset()
    smu.source.func = smu.FUNC_DC_VOLTAGE
    smu.measure.func = smu.FUNC_DC_CURRENT
    smu.source.rangev = 5
    smu.measure.rangei = 0.1
    smu.source.output = smu.ON

    for v = 0, 2, 0.5 do
        smu.source.levelv = v
        delay(0.1)
        local i = smu.measure.read()
        print(string.format("V=%.3f V, I=%.6f A", v, i))
    end

    smu.source.output = smu.OFF
end

endscript
"""

# Send the entire TSP script in one go
keithley.write(tsp_script)
time.sleep(0.5)