#
# Moku:Go Simple Laser Pulser
#
# Simple script to generate laser pulses with specified ON and OFF durations.
# Perfect for basic laser pulsing applications.
#
# Features:
# - Specify exact pulse width (laser ON time)
# - Specify exact off time between pulses
# - Configurable voltage for laser control
# - Easy to modify timing parameters
#
# (c) 2024
#

from moku.instruments import ArbitraryWaveformGenerator
import numpy as np

# ===== EASY CONFIGURATION =====
MOKU_IP = '192.168.0.45'           # Your Moku:Go IP address
LASER_VOLTAGE = 3.3                # Voltage when laser is ON
PULSE_WIDTH = 1e-6                 # 1 microsecond pulse width
OFF_TIME = 10e-6                   # 10 microseconds between pulses
TOTAL_PULSES = 10                  # Number of pulses to generate (0 = continuous)

# Advanced settings (usually don't need to change)
SAMPLES_PER_PULSE = 100            # Samples for smooth pulse edges
SAMPLES_PER_OFF = 50               # Samples for off period

def create_pulse_waveform(pulse_width=PULSE_WIDTH, off_time=OFF_TIME,
                         laser_voltage=LASER_VOLTAGE, total_pulses=TOTAL_PULSES):
    """
    Create a simple pulse waveform.

    Args:
        pulse_width: Duration of laser ON (seconds)
        off_time: Duration of laser OFF between pulses (seconds)
        laser_voltage: Voltage when laser is ON
        total_pulses: Number of pulses (0 = continuous repeating pattern)
    """
    # Calculate sample rate for smooth timing
    total_period = pulse_width + off_time
    sample_rate = SAMPLES_PER_PULSE / pulse_width

    all_data = []

    if total_pulses == 0:
        # Continuous pulsing - create one cycle
        # ON period
        on_samples = [laser_voltage] * SAMPLES_PER_PULSE
        all_data.extend(on_samples)

        # OFF period
        off_samples = [0.0] * SAMPLES_PER_OFF
        all_data.extend(off_samples)
    else:
        # Fixed number of pulses
        for i in range(total_pulses):
            # ON period
            on_samples = [laser_voltage] * SAMPLES_PER_PULSE
            all_data.extend(on_samples)

            # OFF period (except after last pulse)
            if i < total_pulses - 1:
                off_samples = [0.0] * SAMPLES_PER_OFF
                all_data.extend(off_samples)

    # Convert to numpy array and normalize for AWG
    waveform_array = np.array(all_data)
    if laser_voltage > 0:
        waveform_array = waveform_array / laser_voltage

    return waveform_array, sample_rate

def run_laser_pulser():
    """Main function to run the laser pulser."""

    print("🔬 Moku:Go Simple Laser Pulser")
    print("=" * 50)
    print(f"Target IP: {MOKU_IP}")
    print(f"Laser Voltage: {LASER_VOLTAGE}V")
    print(".1f")
    print(".1f")
    print(f"Total Pulses: {'Continuous' if TOTAL_PULSES == 0 else TOTAL_PULSES}")
    print()

    # Create pulse waveform
    print("📊 Creating pulse waveform...")
    waveform_data, desired_sample_rate = create_pulse_waveform(
        PULSE_WIDTH, OFF_TIME, LASER_VOLTAGE, TOTAL_PULSES
    )

    print(f"   Waveform length: {len(waveform_data)} samples")

    # Calculate actual timing
    pulse_period = PULSE_WIDTH + OFF_TIME
    frequency = 1.0 / pulse_period if pulse_period > 0 else 0

    print(".1f")
    print(".1f")
    print(".1f")

    # Connect to Moku
    print(f"\n🔌 Connecting to Moku:Go at {MOKU_IP}...")
    try:
        awg = ArbitraryWaveformGenerator(MOKU_IP, force_connect=True, connect_timeout=10)
        print("✅ Connected successfully!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Check Moku:Go IP address")
        print("   2. Ensure device is powered on")
        print("   3. Try running test_moku_connection.py first")
        return

    # Generate waveform
    print("📤 Generating pulse waveform...")
    try:
        # Calculate frequency for waveform repetition
        waveform_length = len(waveform_data)
        waveform_frequency = 1e6 / waveform_length

        awg.generate_waveform(
            channel=1,
            sample_rate='Auto',  # Let Moku choose optimal rate
            lut_data=waveform_data.tolist(),
            frequency=waveform_frequency,
            amplitude=LASER_VOLTAGE,
            offset=0.0,
            interpolation=True
        )
        print("✅ Waveform generated successfully!")

        # Enable output
        awg.enable_output(1, enable=True)
        print("✅ Laser pulsing active on Channel 1!")

    except Exception as e:
        print(f"❌ Waveform generation failed: {e}")
        return

    # Display pulsing information
    print("🚀 Laser Pulse Information:" )
    print(".1f")
    print(".1f")
    print(".1f")
    print(f"   Duty Cycle: {(PULSE_WIDTH/pulse_period)*100:.1f}%")
    print("   Press Ctrl+C to stop pulsing")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n🛑 Stopping laser pulsing...")

    # Clean shutdown
    awg.enable_output(1, enable=False)
    print("✅ Output disabled. Laser OFF.")

if __name__ == "__main__":
    run_laser_pulser()
