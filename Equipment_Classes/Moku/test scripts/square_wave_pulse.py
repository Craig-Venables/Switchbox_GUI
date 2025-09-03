#
# Moku:Go Square Wave Pulse Generator
#
# This example demonstrates how to generate a square wave pulse with:
# - Pulse width: 100ns
# - Edge time: 16ns (shortest possible rise/fall time)
#
# (c) 2024
#

from moku.instruments import WaveformGenerator

# Replace with your Moku:Go's IP address
moku_ip = '192.168.0.45'  # Update if needed

# Connect to the Waveform Generator
wg = WaveformGenerator(moku_ip, force_connect=True)

# Configure Channel 1 to output a square wave pulse
wg.generate_waveform(
    channel=1,
    type='Pulse',
    amplitude=1.0,         # Volts peak-to-peak
    frequency=10000,       # Hz (10 kHz - adjust as needed for your application)
    offset=0.0,            # Volts (centered around 0V)
    pulse_width=100e-9,    # 100 nanoseconds pulse width
    edge_time=16e-9        # 16 nanoseconds (shortest possible rise/fall time)
)

# Enable output on Channel 1
wg.enable_output(1, enable=True)

print("✅ Square wave pulse (100ns width, 16ns edge time) is now active on Channel 1.")
print(f"   Frequency: 10 kHz")
print(f"   Pulse Width: 100ns")
print(f"   Edge Time: 16ns")
print(f"   Amplitude: 1.0 Vpp")
print(f"   Offset: 0.0 V")
