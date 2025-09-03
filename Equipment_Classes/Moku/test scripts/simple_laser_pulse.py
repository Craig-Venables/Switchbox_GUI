#
# Moku:Go Simple Laser Pulse Controller
#
# Generates square wave pulses optimized for laser control:
# - Baseline: 0V (laser OFF)
# - Peak: Configurable voltage (laser ON)
# - Pulse width: 100ns
# - Edge time: 16ns (shortest possible)
#
# (c) 2024
#

from moku.instruments import WaveformGenerator

# Configuration - Change these values as needed
MOKU_IP = '192.168.0.45'      # Your Moku:Go IP address
LASER_VOLTAGE = 3.3           # Peak voltage for laser (adjust for your laser)
FREQUENCY = 1000              # Pulse frequency in Hz

# Pulse timing (fixed for your requirements)
PULSE_WIDTH = 100e-9          # 100 nanoseconds
EDGE_TIME = 16e-9            # 16 nanoseconds (minimum)

def main():
    # Calculate waveform parameters for proper laser control
    # offset = LASER_VOLTAGE/2 ensures baseline=0V and peak=LASER_VOLTAGE
    offset = LASER_VOLTAGE / 2.0
    amplitude = LASER_VOLTAGE

    print("🔬 Starting Moku:Go Laser Pulse Controller")
    print(f"   Target: {MOKU_IP}")
    print(f"   Laser Voltage: {LASER_VOLTAGE}V")
    print(f"   Frequency: {FREQUENCY} Hz")
    print(f"   Pulse Width: {PULSE_WIDTH*1e9:.0f}ns")
    print(f"   Edge Time: {EDGE_TIME*1e9:.0f}ns")

    # Connect to Moku
    wg = WaveformGenerator(MOKU_IP, force_connect=True)

    # Configure laser pulse
    wg.generate_waveform(
        channel=1,
        type='Pulse',
        amplitude=amplitude,
        frequency=FREQUENCY,
        offset=offset,
        pulse_width=PULSE_WIDTH,
        edge_time=EDGE_TIME
    )

    # Enable output
    wg.enable_output(1, enable=True)

    print("✅ Laser pulse active!")
    print("   • 0V baseline (laser OFF)")
    print(f"   • {LASER_VOLTAGE}V peak (laser ON)")
    print("   • Press Ctrl+C to stop")

    try:
        # Keep running until interrupted
        while True:
            pass
    except KeyboardInterrupt:
        print("\n🛑 Stopping laser pulse...")

    # Clean shutdown
    wg.enable_output(1, enable=False)
    print("✅ Output disabled. Safe to disconnect.")

if __name__ == "__main__":
    main()
