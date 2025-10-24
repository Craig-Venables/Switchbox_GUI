# Keithley 2450 SourceMeter Controller

## Overview

The `Keithley2450.py` module provides a Python interface for the Keithley 2450 SourceMeter with advanced TSP (Test Script Processor) capabilities for fast pulse measurements on memristors and other devices.

## Key Features

- **Multiple connectivity options**: USB, GPIB, and LAN
- **Voltage sourcing**: ±200V (±210V absolute maximum)
- **Current sourcing**: ±1A (±1.05A absolute maximum)
- **Fast TSP pulse execution**: On-instrument script processing eliminates Python communication delays
- **Pre-defined pulse patterns**: Potentiation, depression, read pulses for memristor characterization
- **Custom pulse sequences**: Flexible arbitrary waveform generation
- **Compatible with existing code**: Works with `iv_controller_manager.py`

## Quick Start

### Basic Connection

```python
from Equipment.SMU_AND_PMU.Keithley2450 import Keithley2450Controller

# Connect via USB
smu = Keithley2450Controller('USB0::0x05E6::0x2450::04517573::INSTR')

# Or via GPIB
smu = Keithley2450Controller('GPIB0::24::INSTR')

# Or via LAN
smu = Keithley2450Controller('TCPIP0::192.168.1.100::INSTR')
```

### Basic Voltage/Current Sourcing

```python
# Source 1.5V with 10mA compliance
smu.set_voltage(1.5, Icc=0.01)

# Measure current
current = smu.measure_current()
print(f"Current: {current*1e6:.3f} µA")

# Return to 0V and disable output
smu.set_voltage(0.0)
smu.enable_output(False)
```

### Fast Pulse Measurements

#### Single Read Pulse

```python
# Prepare for fast pulses
smu.prepare_for_pulses(Icc=0.1, v_range=20.0, autozero_off=True)

# Execute single read pulse (0.2V, 1ms)
result = smu.tsp_read_pulse(read_voltage=0.2, pulse_width=1e-3)
if result['status'] == 'SUCCESS':
    print(f"V: {result['voltages'][0]:.3f}V, I: {result['currents'][0]:.6e}A")

# Return to safe state
smu.finish_pulses()
```

#### Potentiation Pulse Train (SET)

```python
# Apply 10 SET pulses with read-after-write
result = smu.tsp_potentiation_pulse(
    voltage=2.0,           # Pulse amplitude (V)
    pulse_width=100e-6,    # 100 microseconds
    count=10,              # 10 pulses
    delay_between=1e-3,    # 1ms between pulses
    read_voltage=0.2       # Read at 0.2V after each pulse
)

if result['status'] == 'SUCCESS':
    print(f"Captured {result['points']} measurements")
    currents = result['currents']
    # Calculate resistance after each pulse
    resistances = [0.2/i if i != 0 else float('inf') for i in currents]
    print(f"Resistance: {resistances}")
```

#### Depression Pulse Train (RESET)

```python
# Apply 5 RESET pulses
result = smu.tsp_depression_pulse(
    voltage_neg=-1.5,      # Negative pulse for reset
    pulse_width=100e-6,
    count=5,
    delay_between=1e-3,
    read_voltage=0.2
)

if result['status'] == 'SUCCESS':
    print(f"Reset complete: {result['points']} measurements")
```

#### Custom Pulse Sequence

```python
# Create arbitrary pulse sequence
voltages = [0.5, 1.0, 1.5, 2.0, 1.5, 1.0, 0.5]
pulse_widths = [100e-6] * 7  # All 100µs
delays = [1e-3] * 7           # All 1ms

result = smu.tsp_pulse_train_custom(
    voltage_list=voltages,
    pulse_width_list=pulse_widths,
    delay_list=delays
)
```

#### Custom TSP Script

```python
# Execute arbitrary TSP code
custom_script = """
smu.source.func = smu.FUNC_DC_VOLTAGE
smu.source.level = 1.0
smu.source.output = smu.ON
delay(0.01)
local v = smu.measure.read()
local i = smu.measure.i()
print(string.format("DATA:%g,%g", v, i))
smu.source.output = smu.OFF
print("DONE")
"""

result = smu.execute_tsp_script(custom_script)
```

## Using with IV Controller Manager

The Keithley 2450 is integrated into the system's instrument manager:

```python
from Equipment.iv_controller_manager import IVControllerManager

# Create manager instance
manager = IVControllerManager(
    smu_type='Keithley 2450',
    address='USB0::0x05E6::0x2450::04517573::INSTR'
)

# Use unified API
manager.set_voltage(1.5, Icc=0.01)
current = manager.measure_current()
manager.enable_output(False)

# Access 2450-specific features
if hasattr(manager.instrument, 'tsp_potentiation_pulse'):
    result = manager.instrument.tsp_potentiation_pulse(2.0, 100e-6, 10)
```

## Testing the Controller

Run the built-in test script to verify functionality:

```bash
python Equipment/SMU_AND_PMU/Keithley2450.py
```

The test script will:
1. Connect to the instrument
2. Test basic SCPI operations (voltage/current sourcing)
3. Test pulse preparation
4. Test TSP pulse patterns (if you choose to run them)
5. Verify safe shutdown

**Important**: Update the `DEVICE_ADDRESS` variable in the test script to match your instrument.

## Specifications

| Parameter | Range | Notes |
|-----------|-------|-------|
| Voltage | ±200V | ±210V absolute max |
| Current | ±1A | ±1.05A absolute max |
| Min Pulse Width | 50µs | Recommended minimum |
| Measurement Speed | 0.01 NPLC | With autozero off |
| Connection | USB, GPIB, LAN | Auto-detect format |

## TSP Resources

- **TSP Toolkit**: [Download VSCode Extension](https://www.tek.com/en/products/software/tsp-toolkit-scripting-tool)
- **Manual**: `Equipment/manuals/Keithley 2450 manual.pdf`
- **Datasheet**: `Equipment/manuals/Keithley 2450 datasheet.pdf`

## Safety Notes

1. Always use appropriate compliance limits to protect devices
2. Start with low voltages and gradually increase
3. The `prepare_for_pulses()` method disables autozero for speed - restore it with `finish_pulses()`
4. Use `shutdown()` or `close()` to safely disable output before disconnecting
5. Monitor device under test for damage during pulse operations

## Common Issues

### Connection Errors

If you get "No device connected":
- Check the VISA address matches your instrument
- Verify USB/GPIB cable is connected
- Ensure instrument is powered on
- Try listing available resources:
  ```python
  import pyvisa
  rm = pyvisa.ResourceManager()
  print(rm.list_resources())
  ```

### TSP Script Errors

If TSP scripts fail:
- Check that pulses are not too fast (min 50µs)
- Ensure voltage/current limits are within instrument specs
- Verify timeout is sufficient for long pulse sequences
- Check for syntax errors in custom TSP scripts

### Measurement Issues

If measurements are unstable:
- Increase NPLC (reduce speed) for better accuracy
- Enable autozero for DC measurements
- Use 4-wire sensing for low-resistance devices
- Check for compliance (current limiting)

## Next Steps

1. **Test the connection**: Run the test script to verify communication
2. **Characterize your device**: Start with simple voltage sweeps
3. **Optimize pulse timing**: Find minimum pulse width for your application
4. **Create custom patterns**: Use TSP scripting for complex waveforms
5. **Integrate with GUI**: The controller works with existing measurement GUIs

## Support

For issues or questions:
- Check the Keithley 2450 manual for detailed command reference
- Review TSP examples in the manual
- Test with the built-in test script
- Verify instrument firmware is up to date

