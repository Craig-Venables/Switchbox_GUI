import pyvisa
import time

def setup_staircase(rm, trig=True):
    # Open connection
    inst = rm.open_resource("USB0::0xF4EC::0x1102::SDG1XCDXXXXXXX::INSTR")
    inst.timeout = 5000

    print("Connected to:", inst.query("*IDN?"))

    # Reset
    inst.write("*RST")
    time.sleep(0.5)

    # Configure staircase waveform (as arbitrary list mode)
    # Example: 0 -> 1 -> 2 -> 3 -> 0 (simple up/down steps)
    waveform_points = [0, 1, 2, 3, 2, 1, 0]
    point_str = ",".join(map(str, waveform_points))

    inst.write("C1:BSWV WVTP,ARB")                  # Channel 1, arbitrary waveform
    inst.write("C1:ARWV NAME,STAIR,DATA," + point_str)
    inst.write("C1:BSWV FREQ,10,AMP,5,OFST,0")      # 10 Hz update, 5 Vpp, 0 V offset

    if trig:
        # External trigger mode
        inst.write("C1:TRIG:SOUR,EXT")              # Trigger source external
        inst.write("C1:TRIG:EDGE,RISE")             # Rising edge trigger
        inst.write("C1:TRIG:MODE,NORM")             # Normal (waits for trigger)
    else:
        # Free run
        inst.write("C1:TRIG:SOUR,INT")              # Internal trigger
        inst.write("C1:TRIG:MODE,CONT")             # Continuous running

    inst.write("C1:OUTP ON")
    print("Waveform armed. Trigger mode:", "EXT" if trig else "INT")
    return inst


if __name__ == "__main__":
    rm = pyvisa.ResourceManager()
    
    # Change to False for free-run
    trig = True  
    
    inst = setup_staircase(rm, trig=trig)

    if not trig:
        print("Free running staircase. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    inst.close()
    print("Closed connection.")
