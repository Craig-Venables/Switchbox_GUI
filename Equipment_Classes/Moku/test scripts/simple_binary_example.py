#
# Simple Binary Data Example for Moku:Go
#
# Quick demonstration of sending "1111,0000,0101" pattern
# with 100ns bit period and 1μs spacing.
#
# (c) 2024
#

from moku.instruments import ArbitraryWaveformGenerator
import numpy as np

# Configuration for "1111,0000,0101" pattern
MOKU_IP = '192.168.0.45'
HIGH_VOLTAGE = 3.3
BIT_PERIOD = 100e-9    # 100ns per bit
SEQUENCE_SPACING = 1e-6  # 1μs between sequences
SAMPLES_PER_BIT = 10

# Binary pattern to send
BINARY_PATTERN = "111100000101"  # 1111,0000,0101 combined

def create_simple_waveform():
    """Create waveform for the binary pattern."""
    sample_rate = SAMPLES_PER_BIT / BIT_PERIOD

    # Convert binary string to voltage levels
    voltages = []
    for bit in BINARY_PATTERN:
        if bit == '1':
            voltages.append(HIGH_VOLTAGE)
        else:
            voltages.append(0.0)

    # Create samples for each bit
    waveform_data = []
    for voltage in voltages:
        bit_samples = [voltage] * SAMPLES_PER_BIT
        waveform_data.extend(bit_samples)

    # Convert to numpy array and normalize
    waveform_array = np.array(waveform_data)
    waveform_array = waveform_array / HIGH_VOLTAGE  # Normalize to [-1, 1]

    return waveform_array, sample_rate

def main():
    print("🔢 Simple Binary Transmission: 1111,0000,0101")
    print(f"Target: {MOKU_IP}")
    print(f"Pattern: {BINARY_PATTERN}")
    print(f"High Voltage: {HIGH_VOLTAGE}V")
    print(f"Bit Period: {BIT_PERIOD*1e9:.0f}ns")
    print(f"Sequence Spacing: {SEQUENCE_SPACING*1e6:.0f}μs")

    # Create waveform
    waveform_data, sample_rate = create_simple_waveform()

    print(f"\nWaveform created:")
    print(f"   Length: {len(waveform_data)} samples")
    print(".1f")
    # Connect and transmit
    awg = ArbitraryWaveformGenerator(MOKU_IP, force_connect=True)

    # Send the binary pattern
    # Calculate frequency for arbitrary waveform (repetitions per second)
    waveform_length = len(waveform_data)
    frequency = 1e6 / waveform_length  # Default frequency in Hz

    awg.generate_waveform(
        channel=1,
        sample_rate='Auto',  # Let Moku choose optimal rate
        lut_data=waveform_data.tolist(),
        frequency=frequency,
        amplitude=HIGH_VOLTAGE,
        offset=0.0,
        interpolation=True
    )

    awg.enable_output(1, enable=True)

    print("\n✅ Binary pattern transmission active!")
    print("   Pattern: 1111,0000,0101")
    print("   Press Ctrl+C to stop")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")

    awg.enable_output(1, enable=False)
    print("✅ Transmission stopped.")

if __name__ == "__main__":
    main()
