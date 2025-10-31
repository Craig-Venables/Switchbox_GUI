# Keithley 2450 SourceMeter - Complete Reference

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Connection and Setup](#connection-and-setup)
4. [Pulse Methods](#pulse-methods)
5. [Buffer-Based Operations](#buffer-based-operations)
6. [Speed Optimization](#speed-optimization)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)
9. [Reference Tables](#reference-tables)

---

## Overview

The Keithley 2450 SourceMeter is a precision instrument capable of sourcing and measuring voltage and current. This document covers the Python interface implementation with emphasis on fast pulse measurements for device characterization, particularly memristors.

### Specifications

| Parameter | Range | Notes |
|-----------|-------|-------|
| Voltage | ±200V | ±210V absolute max |
| Current | ±1A | ±1.05A absolute max |
| Min Pulse Width | 50µs | TSP mode |
| Min Pulse Width | 2ms | SCPI mode |
| Connection | USB, GPIB, LAN | Auto-detect format |

### Key Features

- Multiple connectivity options (USB, GPIB, LAN)
- Fast TSP (Test Script Processor) pulse execution
- Buffer-based measurement for data acquisition
- Pre-defined pulse patterns for device characterization
- Compatible with instrument manager architecture

---

## Architecture

The implementation provides two distinct approaches for pulse generation, each suited to different timing requirements.

### SCPI Mode (Keithley2450.py)

Standard SCPI commands sent from Python over USB/GPIB/LAN.

**Advantages:**
- Simple integration with existing code
- No scripting knowledge required
- Easier debugging (commands visible in communication logs)
- Standard interface consistent with other instruments

**Limitations:**
- Cannot pulse reliably below 2ms
- Higher timing jitter (±100µs)
- Multiple commands introduce latency

**Best For:**
- Pulse widths greater than 1ms
- Standard DC measurements
- Simple integration requirements

### TSP Mode (Keithley2450_TSP.py)

Lua-based scripts executed on the instrument processor.

**Advantages:**
- Fast pulses down to 50µs
- Accurate timing (±10µs)
- Low latency (script runs on instrument)
- Complex sequences without PC communication delays

**Limitations:**
- Requires understanding of TSP/Lua syntax
- Separate file to import
- Debugging more complex

**Best For:**
- Pulse widths less than 1ms
- Maximum speed and accuracy requirements
- Complex waveform generation

### Buffer-Based Architecture

The current implementation uses SCPI buffer-based pulsing (similar to K2461) for better compatibility with existing workflows. This approach:

- Uses SimpleLoop trigger model with hardware delays
- Stores measurement data in instrument buffers
- Retrieves data in batches for efficiency
- Provides granular control over pulse and measurement timing

---

## Connection and Setup

### Basic Connection

```python
from Equipment.SMU_AND_PMU.Keithley2450 import Keithley2450Controller

# USB connection
smu = Keithley2450Controller('USB0::0x05E6::0x2450::04517573::INSTR')

# GPIB connection
smu = Keithley2450Controller('GPIB0::24::INSTR')

# LAN connection
smu = Keithley2450Controller('TCPIP0::192.168.1.100::INSTR')

# Verify connection
print(smu.get_idn())
print(smu.check_errors())
```

### Finding Instrument Address

```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
```

### Safe Shutdown

Always properly close connections to ensure output is disabled:

```python
smu.shutdown()  # Ramp to 0V and disable output
smu.close()     # Close VISA connection
```

---

## Pulse Methods

### Method Selection Decision Tree

```
Need to pulse?
│
├─ Pulse width > 1ms?
│  │
│  ├─ YES → Use SCPI buffer-based methods
│  │         prepare_pulsing_voltage() + send_pulse()
│  │
│  └─ NO → Use TSP methods (if available)
│            Import TSP_Pulses class
│            tsp.voltage_pulse()
│
└─ Need measurement during pulse?
   │
   ├─ YES → Use TSP pulse_with_measurement()
   │         or buffer-based prepare_measure_n()
   │
   └─ NO → Use SCPI or TSP depending on width
```

### SCPI Pulse Methods

#### Voltage Pulse Configuration

```python
prepare_pulsing_voltage(voltage: float, width: float, clim: float = 100e-3)
```
Configure voltage pulse parameters. The pulse is executed when `send_pulse()` is called.

Parameters:
- voltage: Pulse amplitude in volts
- width: Pulse width in seconds (minimum ~2ms for SCPI)
- clim: Current compliance limit in amps

#### Current Pulse Configuration

```python
prepare_pulsing_current(current: float, width: float, vlim: float = 40)
```
Configure current pulse parameters.

Parameters:
- current: Pulse amplitude in amps
- width: Pulse width in seconds
- vlim: Voltage compliance limit in volts

#### Custom Sweep

```python
prepare_customsweep_currentpulse(sweep_list: List[float], width: float, 
                                 nsweeps: int, delay: float, vlim: float = 40,
                                 meason: int = 1, range: float = 0.2)
```
Configure custom current pulse sweep with list of values.

#### Pulse Execution

```python
send_pulse()
```
Execute the configured pulse. Uses SimpleLoop trigger model with hardware timing.

### TSP Pulse Methods

When using TSP, import the separate class:

```python
from Equipment.SMU_AND_PMU.Keithley2450_TSP import TSP_Pulses

tsp = TSP_Pulses(keithley)
```

#### Available TSP Methods

```python
# Single voltage pulse
tsp.voltage_pulse(1.0, 100e-6, clim=0.1)

# Single current pulse
tsp.current_pulse(10e-3, 100e-6, vlim=20)

# Pulse with measurement
v, i = tsp.pulse_with_measurement(1.0, 100e-6, clim=0.1)
resistance = v / i

# Pulse train (multiple pulses)
tsp.pulse_train(1.0, 100e-6, count=10, delay_between=1e-3, clim=0.1)
```

### Performance Comparison

| Pulse Width | Recommended Method | Expected Accuracy |
|-------------|-------------------|-------------------|
| 10ms - 1s | SCPI | ±100µs |
| 1ms - 10ms | SCPI | ±100µs |
| 100µs - 1ms | TSP | ±10µs |
| 50µs - 100µs | TSP | ±10µs |
| <50µs | External generator | N/A |

---

## Buffer-Based Operations

Buffer-based operations provide efficient data collection for sweeps and repeated measurements.

### Measurement Configuration

#### N-Point Buffer Measurement

```python
prepare_measure_n(current: float, num: int, nplc: float = 2)
```
Prepare buffer for N measurements in 4-wire mode.

Parameters:
- current: Probe current in amps
- num: Number of measurement points
- nplc: Number of power line cycles (affects speed vs noise)

Usage pattern:
```python
k2450.prepare_measure_n(10e-6, 10, nplc=2)
k2450.trigger()
time_arr, voltage, current = k2450.read_buffer(10)
```

#### Single Point Measurement

```python
prepare_measure_one(current: float, nplc: float = 2, four_wire: bool = True)
```
Prepare for single measurements (2 or 4-wire).

Usage pattern:
```python
k2450.prepare_measure_one(10e-6, nplc=2)
current, voltage = k2450.read_one()
```

#### 4-Wire Probing

```python
enable_4_wire_probe(current: float, nplc: float = 2, vlim: float = 1)
```
Enable 4-wire sensing and turn output on. Use for low resistance measurements (< 1kΩ).

```python
k2450.enable_4_wire_probe(10e-6, nplc=2, vlim=1.0)
# Take measurements...
k2450.disable_probe_current()
```

#### 2-Wire Probing

```python
enable_2_wire_probe(current: float, nplc: float = 2, vlim: float = 1)
```
Enable 2-wire sensing and turn output on. Use for higher resistance measurements.

### Triggering and Reading

#### Trigger Buffer Measurement

```python
trigger()
```
Start measurement configured by `prepare_measure_n()`. Waits for completion.

#### Read Buffer

```python
read_buffer(num: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]
```
Read N points from buffer after trigger. Returns (time, voltage, current) as numpy arrays.

Data format: `[source0, read0, time0, source1, read1, time1, ...]`
- time: relative timestamp in seconds
- voltage: measured voltage in volts
- current: source current in amps

#### Read Single Point

```python
read_one() -> Tuple[float, float]
```
Measure and read single value immediately. Returns (current, voltage).

#### Fetch Single Point

```python
fetch_one() -> Tuple[float, float]
```
Read previously triggered measurement. Returns (voltage, current).
Note the reversed order compared to read_one().

#### Get Trace

```python
get_trace(num: int, check_period: float = 10) -> Tuple[np.ndarray, np.ndarray, np.ndarray]
```
Wait for sweep completion, then retrieve data. Returns (time, voltage, current).

### Output Control

```python
enable_probe_current()   # Turn output on
disable_probe_current()  # Turn output off
enable_output(state)     # General output control
```

### Buffer Names

The implementation uses two buffer names:
- **"mybuffer"**: Used for N-point measurements (prepare_measure_n)
- **"defbuffer1"**: Used for single-point measurements and pulses

---

## Speed Optimization

The default instrument settings prioritize accuracy over speed. For fast measurements, apply these optimizations:

### Key Optimizations

**1. Use Fixed Ranges (instead of autorange)**
```python
smu.source.range = 2       # Lock to 2V range
smu.measure.range = 10e-6  # Lock to 10µA range
```

**2. Disable Autozero**
```python
smu.measure.autozero.enable = smu.OFF
```

**3. Reduce NPLC**
```python
smu.measure.nplc = 0.01  # Fast measurements
# Use higher values (2-10) for accuracy
```

### TSP Fast Mode

TSP pulse methods automatically apply speed optimizations:

```python
# Fast mode ON by default
tsp.voltage_pulse(1.0, 100e-6, clim=0.1)

# Fast mode OFF for maximum accuracy
tsp.voltage_pulse(1.0, 100e-6, clim=0.1, fast=False)
```

### Range Selection

#### Voltage Source Ranges

| Range | Best for voltage |
|-------|------------------|
| 0.2V | 0V to ±0.2V |
| 2V | 0.2V to ±2V |
| 20V | 2V to ±20V |
| 200V | 20V to ±200V |

#### Current Measurement Ranges

| Range | Best for current |
|-------|------------------|
| 10nA | < 10nA |
| 100nA | 10nA - 100nA |
| 1µA | 100nA - 1µA |
| 10µA | 1µA - 10µA |
| 100µA | 10µA - 100µA |
| 1mA | 100µA - 1mA |
| 10mA | 1mA - 10mA |
| 100mA | 10mA - 100mA |
| 1A | 100mA - 1A |

### Speed vs Accuracy Trade-offs

| Setting | Speed | Accuracy | When to Use |
|---------|-------|----------|-------------|
| Fixed range + fast NPLC | Fastest | ±0.5% | Fast pulses, relative measurements |
| Autorange + slow NPLC | Slow | ±0.01% | Precision measurements |
| Fixed range + slow NPLC | Fast | ±0.02% | Good balance |

### NPLC Reference Table

| NPLC | Speed | Use Case |
|------|-------|----------|
| 0.001 | Fastest (16µs @ 60Hz) | Ultra-fast pulses, transient measurements |
| 0.01 | Very fast (166µs) | Fast pulses |
| 0.2 | Fast | General fast measurements |
| 1 | Standard | Normal measurements |
| 2 | Accurate | Default, good noise rejection |
| 10 | Very accurate | High precision DC |
| 100-200 | Slowest | Maximum accuracy |

---

## Usage Examples

### Example 1: Single Voltage Pulse

```python
from Equipment.SMU_AND_PMU.Keithley2450 import Keithley2450Controller

k2450 = Keithley2450Controller('USB0::0x05E6::0x2450::04496615::INSTR')

# Configure and send 5ms pulse
k2450.prepare_pulsing_voltage(voltage=1.0, width=5e-3, clim=0.1)
k2450.send_pulse()

k2450.close()
```

### Example 2: Pulse Loop with Measurements

Memristor characterization pattern - apply pulses and measure resistance change.

```python
import time
import numpy as np

# Pulse parameters
pulse_current = 0.01e-3  # 10µA
pulse_width = 1e-3       # 1ms
number_of_pulses = 5

# Measurement parameters
probe_current = 10e-6    # 10µA
nplc = 2
num_measurements = 10

for n in range(number_of_pulses):
    # Send pulse
    k2450.prepare_pulsing_current(pulse_current, pulse_width)
    k2450.send_pulse()
    time.sleep(0.2)  # Settling time
    
    # Measure with buffer
    k2450.prepare_measure_n(probe_current, num_measurements, nplc)
    k2450.trigger()
    
    # Read buffer
    time_arr, v, c = k2450.read_buffer(num_measurements)
    resistance = np.mean(v / c)
    print(f"Pulse {n+1}: R = {resistance:.2e} Ω")

k2450.disable_probe_current()
```

### Example 3: IV Sweep with 4-Wire Sensing

Low resistance measurement with 4-wire configuration.

```python
import numpy as np

# Enable 4-wire sensing
k2450.enable_4_wire_probe(current=0, nplc=2, vlim=2.0)

# Sweep current from 0 to 100µA
currents = np.linspace(0, 100e-6, 20)
voltages = []
measured_currents = []

for current in currents:
    k2450.set_current(current, Vcc=2.0)
    time.sleep(0.05)  # Settling time
    
    c, v = k2450.read_one()
    voltages.append(v)
    measured_currents.append(c)
    print(f"I={c:.9f}A, V={v:.6f}V, R={v/c:.2e}Ω")

k2450.disable_probe_current()

# Calculate average resistance
resistance = np.mean(np.array(voltages) / np.array(measured_currents))
print(f"Average resistance: {resistance:.2e} Ω")
```

### Example 4: Repeated Single-Point Measurements

Monitoring resistance over time.

```python
# Enable 2-wire probing
k2450.enable_2_wire_probe(current=10e-6, nplc=1, vlim=1.0)

# Take multiple readings
for i in range(20):
    c, v = k2450.read_one()
    resistance = v / c
    print(f"Reading {i+1}: R={resistance:.2e}Ω")
    time.sleep(0.05)

k2450.disable_probe_current()
```

### Example 5: Memristor SET/RESET (TSP)

Fast pulse sequences for memristor switching.

```python
from Equipment.SMU_AND_PMU.Keithley2450 import Keithley2450Controller
from Equipment.SMU_AND_PMU.Keithley2450_TSP import TSP_Pulses

keithley = Keithley2450Controller('USB0::0x05E6::0x2450::04496615::INSTR')
tsp = TSP_Pulses(keithley)

# SET operation: positive pulse
print("SET operation...")
v, i = tsp.pulse_with_measurement(2.0, 100e-6, clim=0.1)
r_set = v / i
print(f"SET resistance: {r_set:.2e} Ω")

time.sleep(0.1)

# RESET operation: negative pulse
print("RESET operation...")
v, i = tsp.pulse_with_measurement(-2.0, 100e-6, clim=0.1)
r_reset = v / i
print(f"RESET resistance: {r_reset:.2e} Ω")

keithley.close()
```

### Example 6: Custom Pulse Sequence

Arbitrary waveform generation with varying amplitudes.

```python
# Create arbitrary pulse sequence
voltages = [0.5, 1.0, 1.5, 2.0, 1.5, 1.0, 0.5]

for voltage in voltages:
    k2450.prepare_pulsing_voltage(voltage, 2e-3, clim=0.1)
    k2450.send_pulse()
    time.sleep(0.01)
    
    # Measure after each pulse
    k2450.prepare_measure_one(10e-6, nplc=1)
    c, v = k2450.read_one()
    print(f"Pulse {voltage}V: measured {v:.6f}V, {c:.9f}A")

k2450.disable_probe_current()
```

### Example 7: Using with IV Controller Manager

Integration with the instrument manager system.

```python
from Equipment.iv_controller_manager import IVControllerManager

# Create manager instance
manager = IVControllerManager(
    smu_type='Keithley 2450',
    address='USB0::0x05E6::0x2450::04496615::INSTR'
)

# Use unified API
manager.set_voltage(1.5, Icc=0.01)
current = manager.measure_current()
manager.enable_output(False)

# Access 2450-specific features
if hasattr(manager.instrument, 'prepare_pulsing_voltage'):
    manager.instrument.prepare_pulsing_voltage(1.0, 5e-3, clim=0.1)
    manager.instrument.send_pulse()

manager.close()
```

---

## Troubleshooting

### Connection Issues

**Problem:** "No device connected" error

**Solutions:**
- Verify VISA address matches your instrument
- Check USB/GPIB cable connection
- Ensure instrument is powered on
- List available resources:
  ```python
  import pyvisa
  rm = pyvisa.ResourceManager()
  print(rm.list_resources())
  ```

### Pulse Timing Issues

**Problem:** Pulses not executing at expected width

**SCPI Mode:**
- Minimum pulse width is approximately 2ms
- For shorter pulses, use TSP methods
- Check oscilloscope to verify actual pulse width

**TSP Mode:**
- Minimum pulse width is approximately 50µs
- Ensure fast mode optimizations are enabled
- Verify no SCPI commands are being mixed with TSP

**Solutions:**
```python
# Verify pulse timing on oscilloscope
tsp.voltage_pulse(1.0, 100e-6)
# Scope should show: 100µs ± 10µs pulse width
```

### Measurement Issues

**Problem:** Measurements are unstable or noisy

**Solutions:**
- Increase NPLC for better noise rejection:
  ```python
  k2450.prepare_measure_n(10e-6, 10, nplc=5)  # Slower but more accurate
  ```
- Enable autozero for DC measurements:
  ```python
  k2450.device.write("SENS:VOLT:AZER ON")
  ```
- Use 4-wire sensing for low resistance:
  ```python
  k2450.enable_4_wire_probe(10e-6, nplc=2, vlim=1.0)
  ```
- Check for compliance (current limiting):
  ```python
  print(k2450.check_errors())
  ```

**Problem:** Nil or zero measurements

**Solutions:**
- Check output is enabled
- Add delay before measurement
- Verify measurement range is appropriate
- Enable autorange temporarily for diagnosis

### TSP-Specific Issues

**Problem:** Error -285 (TSP Syntax Error)

**Cause:** SCPI commands sent while in TSP mode

**Solution:**
- Ensure proper mode switching
- Don't mix SCPI and TSP commands
- Use mode guards when available

**Problem:** Error 1408 (Script Already Exists)

**Cause:** Trying to load a script that's already in memory

**Solution:**
```python
# Clear all scripts before loading
tsp.clear_all_scripts()
```

**Problem:** Error -286 (Runtime Error)

**Cause:** Nil values in measurements or string formatting

**Solution:**
- Add nil checks in custom TSP scripts
- Ensure measurement readings are valid before use
- Add delay before measurements

### Buffer Issues

**Problem:** Buffer overflow or incomplete data

**Solutions:**
- Check buffer size limitations (typically 100k points)
- Clear buffers before new measurements:
  ```python
  k2450.device.write("TRAC:CLE 'mybuffer'")
  ```
- Increase timeout for long sweeps:
  ```python
  k2450.device.timeout = 30000  # 30 seconds
  ```

### Compliance Issues

**Problem:** Compliance (current or voltage limiting) occurs

**Solutions:**
- Increase compliance limits:
  ```python
  k2450.prepare_pulsing_voltage(1.0, 5e-3, clim=0.5)  # Increase from 0.1A
  ```
- Check device characteristics
- Monitor for device damage
- Use lower source values

### Performance Issues

**Problem:** Measurements slower than expected

**Solutions:**
- Reduce NPLC:
  ```python
  k2450.prepare_measure_n(10e-6, 10, nplc=0.1)  # Faster
  ```
- Disable autozero for speed:
  ```python
  k2450.device.write("SENS:VOLT:AZER OFF")
  ```
- Use fixed ranges instead of autorange
- For pulses <1ms, switch to TSP methods

### Error Checking

Always check for instrument errors after operations:

```python
# Check for errors
error_msg = k2450.check_errors()
print(error_msg)  # Should be "0, No error" if OK

# Common error codes:
# -285: TSP syntax error (mixing SCPI with TSP mode)
# -286: TSP runtime error (nil values)
# 1408: Script already exists
# 5004: Measurement overflow (compliance)
```

---

## Reference Tables

### Current Sourcing Ranges

| Application | Typical Current | Notes |
|------------|----------------|-------|
| Minimum | 1nA (1e-9 A) | Noise floor limit |
| Maximum | 1A (1.05A absolute max) | Check device rating |
| Pulse current | 10µA to 10mA (10e-6 to 10e-3 A) | Typical memristor operation |
| Probe current | 1µA to 100µA (1e-6 to 100e-6 A) | Read operations |

### Voltage Sourcing Ranges

| Application | Typical Voltage | Notes |
|------------|----------------|-------|
| Minimum | 100µV | Resolution limited |
| Maximum | 200V (±210V absolute max) | Use caution |
| Pulse voltage | 0.5V to 5V | Typical memristor operation |
| Compliance | Set 10-20% above expected | Protect device |

### Pulse Width Ranges

| Mode | Minimum | Typical | Maximum | Notes |
|------|---------|---------|---------|-------|
| TSP | 50µs | 100µs to 1ms | Limited by memory | Best accuracy |
| SCPI | 2ms | 10ms to 100ms | Limited by timeout | Simpler implementation |

### Common Workflows Summary

| Workflow | Methods Used |
|----------|-------------|
| Single pulse + measurement | prepare_pulsing_voltage + send_pulse + read_one |
| Pulse loop with buffer | Loop: send_pulse + prepare_measure_n + trigger + read_buffer |
| IV sweep (4-wire) | enable_4_wire_probe + loop: set_current + read_one |
| Continuous monitoring | enable_2_wire_probe + loop: read_one |
| Fast pulse sequence (TSP) | tsp.voltage_pulse or pulse_with_measurement |

### Testing Checklist

Hardware verification steps:
- [ ] Connection test (get_idn, check_errors)
- [ ] Basic voltage/current sourcing
- [ ] Single voltage pulse
- [ ] Single current pulse
- [ ] Pulse loop with buffer measurements
- [ ] IV sweep with 4-wire sensing
- [ ] Repeated single-point measurements
- [ ] Buffer data format verification
- [ ] External trigger (if used)
- [ ] TSP pulse methods (if using fast pulses)

### Testing the Implementation

Run the built-in test script to verify functionality:

```bash
python Equipment/SMU_AND_PMU/Keithley2450.py
```

The test script will guide through various operations and verify instrument communication.

Update the `DEVICE_ADDRESS` variable in the test script to match your instrument.

---

## Resources

### Documentation
- Manual: `Equipment/manuals/Keithley 2450 manual.pdf`
- Datasheet: `Equipment/manuals/Keithley 2450 datasheet.pdf`

### Tools
- TSP Toolkit: [Download VSCode Extension](https://www.tek.com/en/products/software/tsp-toolkit-scripting-tool)

### Related Files
- `Keithley2450.py` - Main SCPI controller implementation
- `Keithley2450_TSP.py` - TSP pulse methods for fast operation
- `iv_controller_manager.py` - Instrument manager integration

---

## Safety and Best Practices

1. Always set appropriate compliance limits to protect devices under test
2. Start with low voltages and gradually increase
3. Monitor device under test for damage during pulse operations
4. Use `shutdown()` or `close()` to safely disable output before disconnecting
5. Add settling delays between pulse and measurement operations
6. Test incrementally - verify single operations before complex sequences
7. Check errors frequently during development
8. Use 4-wire sensing for accurate low resistance measurements
9. Keep NPLC high (2-10) for development, reduce only when speed is critical
10. Document pulse parameters and device response for reproducibility

---

This reference guide consolidates information from multiple documentation sources. For specific implementation details, refer to the source code in `Keithley2450.py` and `Keithley2450_TSP.py`.

Last updated: 2025-10-29

