#
# Moku:Go Single Pulse Burst Generator
#
# This example demonstrates how to generate a single burst of square wave pulses with:
# - Pulse width: 100ns
# - Edge time: 16ns (shortest possible rise/fall time)
# - Burst mode: Single pulse or multiple pulses
#
# (c) 2024
#

from moku.instruments import WaveformGenerator
import time

# Replace with your Moku:Go's IP address
moku_ip = '192.168.0.45'  # Update if needed

# Connect to the Waveform Generator
wg = WaveformGenerator(moku_ip, force_connect=True)

# Configure Channel 1 for pulse generation
wg.generate_waveform(
    channel=1,
    type='Pulse',
    amplitude=2.0,         # Volts peak-to-peak (higher amplitude for better visibility)
    frequency=1000000,     # Hz (1 MHz - high frequency for fast pulses)
    offset=0.0,            # Volts (centered around 0V)
    pulse_width=100e-9,    # 100 nanoseconds pulse width
    edge_time=16e-9        # 16 nanoseconds (shortest possible rise/fall time)
)

# Configure burst mode for a single pulse
# Note: Burst parameters may need adjustment based on your Moku firmware version
wg.set_burst_mode(
    channel=1,
    burst_on=True,
    burst_count=1,        # Number of pulses in burst (1 = single pulse)
    burst_period=1e-3     # Period between bursts (1ms)
)

# Enable output on Channel 1
wg.enable_output(1, enable=True)

print("✅ Single pulse burst configured on Channel 1.")
print(f"   Pulse Width: 100ns")
print(f"   Edge Time: 16ns")
print(f"   Amplitude: 2.0 Vpp")
print(f"   Burst Count: 1 pulse")
print(f"   Burst Period: 1ms")

# Wait for user input before disabling
input("\nPress Enter to disable output and exit...")

# Disable output
wg.enable_output(1, enable=False)
print("Output disabled.")
