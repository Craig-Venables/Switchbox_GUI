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

def floats_to_int16_block(samples, vmin=-5.0, vmax=5.0):
    """
    Map float voltages [vmin, vmax] -> signed int16 [-32768,32767] (big-endian)
    """
    clipped = np.clip(samples, vmin, vmax)
    scaled = ((clipped - vmin) / (vmax - vmin)) * (32767 - (-32768)) + (-32768)
    int_samples = np.array(np.round(scaled), dtype=np.int16)
    return int_samples.byteswap().tobytes()  # big-endian

def make_ieee4882_block(data_bytes):
    """
    Wrap binary data into IEEE-488.2 definite-length block header.
    """
    data_len = len(data_bytes)
    len_str = str(data_len)
    header = b'#' + str(len(len_str)).encode('ascii') + len_str.encode('ascii')
    return header + data_bytes

def upload_pattern(resource_str, channel=1, arb_name="BITPATTERN", pattern="1010",
                   num_points_per_bit=1000, amplitude=1.0, offset=0.0,
                   vmin=-5.0, vmax=5.0):
    """
    Upload a binary pattern as an arbitrary waveform to Siglent SDG1032X.
    """
    samples = pattern_to_waveform(pattern, num_points_per_bit, amplitude, offset)
    print(f"Generated waveform: min={samples.min()}, max={samples.max()}, points={len(samples)}")

    data_bytes = floats_to_int16_block(samples, vmin, vmax)
    block = make_ieee4882_block(data_bytes)

    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(resource_str)
    inst.timeout = 5000  # ms

    # Upload binary block
    scpi_cmd = f":SOUR{channel}:DATA:ARB {arb_name},"
    inst.write_raw(scpi_cmd.encode('ascii') + block)
    time.sleep(0.5)

    # Assign waveform and enable output
    inst.write(f":SOUR{channel}:FUNC ARB")
    inst.write(f":SOUR{channel}:FUNC:ARB {arb_name}")
    inst.write(f":OUTP{channel} ON")

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
    OFFSET = 0.0
    VMIN, VMAX = -5.0, 5.0

    upload_pattern(VISA_ADDRESS, CHANNEL, "BITPATTERN", PATTERN,
                   NUM_POINTS_PER_BIT, AMPLITUDE, OFFSET, VMIN, VMAX)


#resource = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR" 