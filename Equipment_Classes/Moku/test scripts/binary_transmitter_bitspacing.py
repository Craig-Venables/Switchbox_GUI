#
# Moku:Go Binary Data Transmitter
#
# This script sends binary data patterns using the Arbitrary Waveform Generator.
# Perfect for laser-based optical communication or digital signal transmission.
#
# Features:
# - Send binary patterns like "1111,0000,0101"
# - Configurable bit period and sequence spacing
# - 0V baseline, user-defined voltage for HIGH bits
# - Optimized for laser control applications
#
# (c) 2024
#

from moku.instruments import ArbitraryWaveformGenerator
import numpy as np

# Configuration
MOKU_IP = '192.168.0.45'        # Your Moku:Go IP address
HIGH_VOLTAGE = 3.3               # Voltage for HIGH bits (1)
BIT_PERIOD = 100e-9              # 100ns per bit
BIT_SPACING = 100e-6              # 10ns spacing between individual bits
SEQUENCE_SPACING = 1e-6          # 1μs between sequences
SAMPLES_PER_BIT = 10           # Samples per bit for smooth edges
SAMPLES_PER_SPACING = 10          # Samples for bit spacing

# Binary data patterns to transmit (comma-separated)
BINARY_PATTERNS = [
    "1111",      # Pattern 1
    "1110",      # Pattern 2
    "1100",      # Pattern 2
    "1000",      # Pattern 2    
    "0000",      # Pattern 2

]

def binary_string_to_voltage_levels(binary_string, high_voltage=HIGH_VOLTAGE):
    """
    Convert binary string to voltage levels.
    0 = 0V (baseline)
    1 = high_voltage
    """
    voltages = []
    for bit in binary_string:
        if bit == '1':
            voltages.append(high_voltage)
        elif bit == '0':
            voltages.append(0.0)
        else:
            raise ValueError(f"Invalid bit '{bit}'. Only '0' and '1' allowed.")
    return voltages

def create_waveform_data(patterns, bit_period=BIT_PERIOD, bit_spacing=BIT_SPACING,
                        sequence_spacing=SEQUENCE_SPACING, samples_per_bit=SAMPLES_PER_BIT,
                        samples_per_spacing=SAMPLES_PER_SPACING, high_voltage=HIGH_VOLTAGE):
    """
    Create waveform data for AWG from binary patterns with spacing between individual bits.

    Returns:
    - waveform_data: numpy array of voltage values
    - sample_rate: required sample rate for AWG
    """
    # Calculate sample rate based on bit period and spacing
    total_bit_time = bit_period + bit_spacing
    sample_rate = samples_per_bit / bit_period  # Samples per second

    all_data = []

    for i, pattern in enumerate(patterns):
        if i > 0:  # Add spacing between sequences (except for first)
            spacing_samples = int(sequence_spacing * sample_rate)
            all_data.extend([0.0] * spacing_samples)  # Baseline during spacing

        # Convert pattern to voltage levels
        voltages = binary_string_to_voltage_levels(pattern, high_voltage)

        # Create samples for each bit with spacing between bits
        for j, voltage in enumerate(voltages):
            if j > 0:  # Add spacing between individual bits
                spacing_samples = [0.0] * samples_per_spacing  # Low voltage during bit spacing
                all_data.extend(spacing_samples)

            # Create samples for this bit
            bit_samples = [voltage] * samples_per_bit
            all_data.extend(bit_samples)

    # Convert to numpy array and normalize for AWG (-1 to 1 range)
    waveform_array = np.array(all_data)

    # Normalize: scale so max voltage becomes 1.0, baseline stays 0
    if high_voltage > 0:
        waveform_array = waveform_array / high_voltage

    return waveform_array, sample_rate

def calculate_optimal_sample_rate(desired_rate):
    """
    Find the closest supported sample rate for Moku AWG.
    Supported rates: ['Auto', '1.25Gs', '1Gs', '625Ms', '500Ms', '312.5Ms',
                     '250Ms', '125Ms', '62.5Ms', '31.25Ms', '15.625Ms']
    """
    supported_rates = {
        'Auto': None,  # Let Moku choose
        '1.25Gs': 1.25e9,
        '1Gs': 1e9,
        '625Ms': 625e6,
        '500Ms': 500e6,
        '312.5Ms': 312.5e6,
        '250Ms': 250e6,
        '125Ms': 125e6,
        '62.5Ms': 62.5e6,
        '31.25Ms': 31.25e6,
        '15.625Ms': 15.625e6
    }

    # Find closest supported rate
    closest_rate = 'Auto'
    min_diff = float('inf')

    for rate_name, rate_value in supported_rates.items():
        if rate_value is None:
            continue
        diff = abs(rate_value - desired_rate)
        if diff < min_diff:
            min_diff = diff
            closest_rate = rate_name

    return closest_rate, supported_rates[closest_rate]

def transmit_binary_data():
    """Main function to transmit binary data patterns."""

    print("🔢 Moku:Go Binary Data Transmitter")
    print("=" * 50)
    print(f"Target IP: {MOKU_IP}")
    print(f"High Voltage: {HIGH_VOLTAGE}V")
    print(f"Bit Period: {BIT_PERIOD*1e9:.0f}ns")
    print(f"Bit Spacing: {BIT_SPACING*1e9:.0f}ns")
    print(f"Sequence Spacing: {SEQUENCE_SPACING*1e6:.0f}μs")
    print(f"Samples per Bit: {SAMPLES_PER_BIT}")
    print(f"Samples per Spacing: {SAMPLES_PER_SPACING}")
    print(f"Patterns: {BINARY_PATTERNS}")
    print()

    # Create waveform data
    print("📊 Creating waveform data...")
    waveform_data, desired_sample_rate = create_waveform_data(
        BINARY_PATTERNS, BIT_PERIOD, BIT_SPACING, SEQUENCE_SPACING,
        SAMPLES_PER_BIT, SAMPLES_PER_SPACING, HIGH_VOLTAGE
    )

    print(f"   Waveform length: {len(waveform_data)} samples")
    print(".1f")
    # Get optimal sample rate
    sample_rate_setting, actual_rate = calculate_optimal_sample_rate(desired_sample_rate)
    if actual_rate:
        print(".1f")
        print(f"   Using setting: {sample_rate_setting}")

    # Connect to Arbitrary Waveform Generator
    print(f"\n🔌 Connecting to Moku:Go AWG at {MOKU_IP}...")
    try:
        awg = ArbitraryWaveformGenerator(MOKU_IP, force_connect=True, connect_timeout=10)
        print("✅ Connected successfully!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n🔧 Troubleshooting tips:")
        print("   1. Verify Moku:Go IP address is correct")
        print(f"   2. Check if {MOKU_IP} is reachable from this computer")
        print("   3. Ensure Moku:Go is powered on and connected to network")
        print("   4. Try different IP addresses (192.168.1.x, 192.168.0.x)")
        print("   5. Check firewall settings")
        return

    # Generate waveform
    print("📤 Generating waveform...")
    # Calculate frequency for arbitrary waveform (repetitions per second)
    waveform_length = len(waveform_data)
    frequency = 1e6 / waveform_length  # Default frequency in Hz

    try:
        awg.generate_waveform(
            channel=1,
            sample_rate=sample_rate_setting,
            lut_data=waveform_data.tolist(),
            frequency=frequency,
            amplitude=HIGH_VOLTAGE,  # Scale factor for the normalized data
            offset=0.0,              # Keep baseline at 0V
            interpolation=True       # Smooth transitions
        )
        print("✅ Waveform generated successfully!")

        # Enable output
        awg.enable_output(1, enable=True)
        print("✅ Output enabled on Channel 1")

    except Exception as e:
        print(f"❌ Waveform generation failed: {e}")
        print("   This might be due to:")
        print("   - Invalid waveform parameters")
        print("   - Moku:Go firmware limitations")
        print("   - Network connectivity issues")
        return

    print("\n✅ Binary data transmission active!")
    print("   Channel 1 output enabled")
    print("   Press Ctrl+C to stop transmission")

    # Calculate and display timing info
    total_bits = sum(len(p) for p in BINARY_PATTERNS)
    total_bit_gaps = sum(len(p) - 1 for p in BINARY_PATTERNS)  # Gaps between bits within patterns
    sequence_time = (total_bits * BIT_PERIOD) + (total_bit_gaps * BIT_SPACING) + ((len(BINARY_PATTERNS) - 1) * SEQUENCE_SPACING)
    frequency = 1.0 / sequence_time if sequence_time > 0 else 0

    print("\n⏱️  Timing Information:")
    print(".1f")
    print(".1f")
    print(".1f")
    try:
        # Keep transmitting until interrupted
        while True:
            pass
    except KeyboardInterrupt:
        print("\n🛑 Stopping transmission...")

    # Disable output
    awg.enable_output(1, enable=False)
    print("✅ Output disabled. Safe to disconnect.")

if __name__ == "__main__":
    transmit_binary_data()
