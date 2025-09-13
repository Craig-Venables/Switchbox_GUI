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
from moku.instruments import WaveformGenerator
import numpy as np

# Configuration
MOKU_IP = '192.168.0.45'        # Your Moku:Go IP address

# Simple pulse-train controls
# Set the voltage level of the pulse (Volts), the pulse width, and the period
# Fastest possible pulses are attempted by selecting the highest supported sample rate
HIGH_VOLTAGE = 1.0               # Pulse HIGH level in Volts
PULSE_WIDTH = 100e-9               # Pulse width (seconds)
PULSE_PERIOD = 200e-9            # Time between pulse starts (seconds)
USE_MAX_SAMPLE_RATE = True       # If True, select the highest supported sample rate

# Option: use built-in Pulse generator for faster edges
USE_PULSE_GENERATOR = True
EDGE_TIME = 16e-9                # Minimum edge time supported by Moku:Go Pulse

def create_pulse_train_waveform(pulse_width, period, high_voltage, desired_rate=float('inf')):
    """
    Create a single-cycle pulse-train waveform (one pulse per cycle) and compute
    the playback frequency so that the effective sample rate is maximized.

    Returns:
    - waveform_data: numpy array of normalized values in [0, 1]
    - sample_rate_setting: string label for the AWG sample rate (e.g., '1.25Gs')
    - actual_rate: numeric sample rate in samples/second corresponding to the setting
    - frequency: waveform playback frequency in Hz so that S = N * f
    """
    if period <= 0:
        raise ValueError("PULSE_PERIOD must be > 0")
    if pulse_width <= 0:
        raise ValueError("PULSE_WIDTH must be > 0")
    if pulse_width >= period:
        raise ValueError("PULSE_WIDTH must be smaller than PULSE_PERIOD")

    # Choose closest supported sample rate to the desired (defaults to highest)
    sample_rate_setting, actual_rate = calculate_optimal_sample_rate(1e12 if USE_MAX_SAMPLE_RATE else desired_rate)
    if actual_rate is None:
        # Fallback: highest supported for Moku:Go subset
        actual_rate = 125e6

    # Compute integer sample counts based on desired period
    high_samples = max(1, int(round(pulse_width * actual_rate)))
    total_samples = max(high_samples + 1, int(round(period * actual_rate)))
    if total_samples <= high_samples:
        total_samples = high_samples + 1
    low_samples = total_samples - high_samples

    # Build normalized waveform: 1.0 for high, 0.0 baseline for low
    waveform_array = np.concatenate([
        np.ones(high_samples, dtype=float),
        np.zeros(low_samples, dtype=float)
    ])

    # Set playback frequency so that S = N * f
    frequency = actual_rate / float(total_samples)

    return waveform_array, sample_rate_setting, actual_rate, frequency

def calculate_optimal_sample_rate(desired_rate):
    """
    Find the closest supported sample rate for Moku AWG.
    Supported rates: ['Auto', '1.25Gs', '1Gs', '625Ms', '500Ms', '312.5Ms',
                     '250Ms', '125Ms', '62.5Ms', '31.25Ms', '15.625Ms']
    """
    # Moku:Go supported AWG sample rates (subset)
    supported_rates = {
        'Auto': None,  # Let Moku choose
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

def transmit_pulse_train():
    """Main function to transmit a simple pulse-train with fastest possible edges."""

    print("🔢 Moku:Go Pulse-Train Transmitter")
    print("=" * 50)
    print(f"Target IP: {MOKU_IP}")
    print(f"High Voltage: {HIGH_VOLTAGE} V")
    print(f"Pulse Width: {PULSE_WIDTH*1e9:.1f} ns")
    print(f"Pulse Period: {PULSE_PERIOD*1e9:.1f} ns")
    print(f"Use Max Sample Rate: {USE_MAX_SAMPLE_RATE}")
    print(f"Use Built-in Pulse Gen: {USE_PULSE_GENERATOR}")
    print()

    if USE_PULSE_GENERATOR:
        # Use built-in Pulse waveform for sharper edges
        print("\n🔌 Connecting to Moku:Go Pulse Generator...")
        try:
            wg = WaveformGenerator(MOKU_IP, force_connect=True, connect_timeout=10)
            print("✅ Connected successfully!")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return

        print("📤 Configuring pulse waveform...")
        # Map voltage to amplitude/offset so low=0V, high=HIGH_VOLTAGE
        amplitude = HIGH_VOLTAGE
        offset = HIGH_VOLTAGE / 2.0
        frequency = 1.0 / PULSE_PERIOD
        try:
            wg.generate_waveform(
                channel=1,
                type='Pulse',
                amplitude=amplitude,
                frequency=frequency,
                offset=offset,
                pulse_width=PULSE_WIDTH,
                edge_time=EDGE_TIME
            )
            wg.enable_output(1, enable=True)
            print("✅ Pulse waveform active on Channel 1")
            print(f"   Edge time set to {EDGE_TIME*1e9:.1f} ns (min)")
        except Exception as e:
            print(f"❌ Pulse configuration failed: {e}")
            return
    else:
        # Create waveform data for AWG LUT
        print("📊 Creating waveform data...")
        try:
            waveform_data, sample_rate_setting, actual_rate, frequency = create_pulse_train_waveform(
                PULSE_WIDTH, PULSE_PERIOD, HIGH_VOLTAGE
            )
        except Exception as e:
            print(f"❌ Failed to create waveform: {e}")
            return

        print(f"   Waveform length: {len(waveform_data)} samples")
        print(f"   Using sample-rate setting: {sample_rate_setting}")
        print(f"   Effective sample rate: {actual_rate/1e6:.3f} MSa/s")
        print(f"   Playback frequency: {frequency/1e6:.3f} MHz")
        print(f"   Time resolution: {1.0/actual_rate*1e9:.3f} ns/sample")

        # Connect to Arbitrary Waveform Generator
        print(f"\n🔌 Connecting to Moku:Go AWG at {MOKU_IP}...")
        try:
            awg = ArbitraryWaveformGenerator(MOKU_IP, force_connect=True, connect_timeout=10)
            print("✅ Connected successfully!")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return

        # Generate waveform
        print("📤 Generating waveform...")
        try:
            # Some API versions expect sample_rate as a string like '125Ms'. Use the setting label.
            awg.generate_waveform(
                channel=1,
                sample_rate=sample_rate_setting,
                lut_data=waveform_data.tolist(),
                frequency=frequency,
                amplitude=HIGH_VOLTAGE,
                offset=0.0,
                interpolation=False
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

    print("\n✅ Pulse train transmission active!")
    print("   Channel 1 output enabled")
    print("   Press Ctrl+C to stop transmission")

    try:
        # Keep transmitting until interrupted
        while True:
            pass
    except KeyboardInterrupt:
        print("\n🛑 Stopping transmission...")

    # Disable output
    try:
        if USE_PULSE_GENERATOR:
            wg.enable_output(1, enable=False)
        else:
            awg.enable_output(1, enable=False)
        print("✅ Output disabled. Safe to disconnect.")
    except Exception:
        pass

if __name__ == "__main__":
    transmit_pulse_train()
