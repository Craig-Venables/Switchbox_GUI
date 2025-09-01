import numpy as np
import pyvisa
import time

def pattern_to_waveform(pattern="1010", num_points_per_bit=1000, amplitude=1.0, offset=0.0):
    """
    Convert a binary string (pattern) into waveform samples.
    1 -> high, 0 -> low.
    """
    waveform = []
    for bit in pattern:
        level = amplitude if bit == "1" else 0.0
        waveform.extend([level + offset] * num_points_per_bit)
    return np.array(waveform)

def upload_pattern(resource_str, channel=1, arb_name="BITPATTERN", pattern="1010",
                   num_points_per_bit=1000, amplitude=1.0, offset=0.0,
                   vmin=-5.0, vmax=5.0):
    """
    Upload a binary pattern as an arbitrary waveform to Siglent SDG1032X.
    """
    samples = pattern_to_waveform(pattern, num_points_per_bit, amplitude, offset)
    print(f"Generated waveform: min={samples.min()}, max={samples.max()}, points={len(samples)}")

    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(resource_str)
    inst.timeout = 5000  # ms

    # Convert samples to comma-separated string format expected by Siglent
    data_str = ",".join([str(val) for val in samples])
    
    # Use correct Siglent SDG1032X commands
    pref = f"C{channel}:"
    
    # Upload waveform data using correct ARB command format
    inst.write(f"{pref}ARWV NAME,{arb_name},DATA,{data_str}")
    time.sleep(0.1)
    
    # Set ARB waveform type
    inst.write(f"{pref}BSWV WVTP,ARB")
    
    # Select the uploaded waveform (index 0 for first user waveform)
    inst.write(f"{pref}ARWV INDEX,5")
    
    # Enable output
    inst.write(f"{pref}OUTP ON")

    # Check instrument error queue
    try:
        err = inst.query("SYST:ERR?").strip()
        print("SYST:ERR? ->", err)
    except Exception:
        pass

    print(f"Pattern '{pattern}' uploaded and output enabled on channel {channel}.")
    return inst

if __name__ == "__main__":
    # MODIFY THESE FOR YOUR SETUP
    VISA_ADDRESS = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"   # replace with your SDG1032X address
    CHANNEL = 1
    PATTERN = "1010"  # your bit pattern
    NUM_POINTS_PER_BIT = 2000
    AMPLITUDE = 1.0
    OFFSET = 1.0
    VMIN, VMAX = -0, 5.0

    upload_pattern(VISA_ADDRESS, CHANNEL, "BITPATTERN", PATTERN,
                   NUM_POINTS_PER_BIT, AMPLITUDE, OFFSET, VMIN, VMAX)


#resource = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR" 