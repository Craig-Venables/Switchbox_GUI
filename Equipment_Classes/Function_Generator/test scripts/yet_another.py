import numpy as np
import pyvisa

# Connect to the function generator
rm = pyvisa.ResourceManager()
fg = rm.open_resource("USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR")

# Parameters
amplitude = 1.0  # Volts
offset = 0.0
samples_per_bit = 1000  # resolution of each bit
sequence = [1, 1, 1, 0]  # the "1010" bit pattern

# Build waveform
wave = []
for bit in sequence:
    wave.extend([bit] * samples_per_bit)
wave = np.array(wave, dtype=np.float32)

# Normalize to [-1,1] for ARB upload
wave = 2 * (wave - np.min(wave)) / (np.max(wave) - np.min(wave)) - 1

# Convert to 14-bit integers for SDG
wave_int = ((wave + 1) * (16383/2)).astype(np.uint16)

# Pack into binary
binblock = wave_int.tobytes()
header = f"DATA:DAC VOLATILE,{len(wave_int)},".encode()

# Send waveform
fg.write_raw(header + binblock)

# Use the uploaded waveform
fg.write("C1:BSWV WVTP,ARB")        # set channel 1 to arbitrary
fg.write("C1:ARWV NAME,VOLATILE")   # use volatile memory
fg.write(f"C1:BSWV AMP,{amplitude},OFST,{offset}")  # amplitude and offset

# Enable output
fg.write("C1:OUTP ON")
