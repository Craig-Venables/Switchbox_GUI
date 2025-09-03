#
# Moku:Go Laser Pulse Controller
#
# This example demonstrates how to generate square wave pulses for laser control with:
# - Baseline: 0V (laser OFF)
# - Peak: User-defined voltage (laser ON)
# - Pulse width: 100ns
# - Edge time: 16ns (shortest possible rise/fall time)
#
# (c) 2024
#

from moku.instruments import WaveformGenerator

# Replace with your Moku:Go's IP address
moku_ip = '192.168.0.45'  # Update if needed

# Laser control parameters
LASER_VOLTAGE = 5.0  # Volts - Peak voltage for laser ON (adjust as needed)
PULSE_WIDTH = 100e-9  # 100 nanoseconds
EDGE_TIME = 16e-9     # 16 nanoseconds (minimum)

# Calculate waveform parameters for laser control
# For laser control: baseline at 0V, peak at LASER_VOLTAGE
offset = LASER_VOLTAGE / 2.0  # Centers the pulse so baseline is 0V
amplitude = LASER_VOLTAGE     # Peak-to-peak amplitude

# Connect to the Waveform Generator
wg = WaveformGenerator(moku_ip, force_connect=True)

# Configure Channel 1 for laser pulse generation
wg.generate_waveform(
    channel=1,
    type='Pulse',
    amplitude=amplitude,    # Peak-to-peak voltage
    frequency=10000,        # Hz (10 kHz - adjust as needed)
    offset=offset,          # Centers pulse: baseline=0V, peak=LASER_VOLTAGE
    pulse_width=PULSE_WIDTH,# 100 nanoseconds
    edge_time=EDGE_TIME     # 16 nanoseconds (shortest possible)
)

# Enable output on Channel 1
wg.enable_output(1, enable=True)

print("✅ Laser pulse control configured on Channel 1.")
print(f"   Baseline: 0V (Laser OFF)")
print(f"   Peak: {LASER_VOLTAGE}V (Laser ON)")
print(f"   Pulse Width: {PULSE_WIDTH*1e9:.0f}ns")
print(f"   Edge Time: {EDGE_TIME*1e9:.0f}ns")
print(f"   Frequency: 10 kHz")
print(f"   Waveform: offset={offset:.1f}V, amplitude={amplitude:.1f}Vpp")

# Optional: Configure burst mode for single pulses
# wg.set_burst_mode(channel=1, burst_on=True, burst_count=1, burst_period=1e-3)

print("\n💡 To change the laser voltage, modify LASER_VOLTAGE at the top of this script.")
print("💡 For continuous pulsing, the current setup works.")
print("💡 For single pulses, uncomment the set_burst_mode line above.")
