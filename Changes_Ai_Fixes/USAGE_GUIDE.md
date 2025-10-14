# Usage Guide for Modular Utilities

This guide shows how to integrate the new modular utilities into your existing codebase.

---

## Quick Start

### 1. Data Normalization

**Replace this:**
```python
# OLD - scattered everywhere
current_tuple = keithley.measure_current()
current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
```

**With this:**
```python
# NEW - clean and simple
from Measurments.data_utils import safe_measure_current

current = safe_measure_current(keithley)
```

---

### 2. Optical/LED Control

**Replace this:**
```python
# OLD - repeated 26 times!
if optical is not None:
    optical.set_enabled(True)
elif psu is not None:
    psu.led_on_380(power)

# ... measurement ...

if optical is not None:
    optical.set_enabled(False)
elif psu is not None:
    psu.led_off_380()
```

**With this:**
```python
# NEW - one place for all light sources
from Measurments.optical_controller import OpticalController

optical_ctrl = OpticalController(optical=optical, psu=psu)
optical_ctrl.enable(power=1.5)

# ... measurement ...

optical_ctrl.disable()

# Or use context manager (auto-disables):
with OpticalController(optical=optical, psu=psu) as ctrl:
    ctrl.enable(1.5)
    # ... measurement ...
# Automatically disabled here
```

---

### 3. Source Modes (Voltage/Current)

**Replace this:**
```python
# OLD - voltage mode only
keithley.set_voltage(voltage, icc)
current = keithley.measure_current()
```

**With this (supports both modes):**
```python
# NEW - mode-agnostic
from Measurments.source_modes import SourceMode, apply_source, measure_result

# Voltage mode
apply_source(keithley, SourceMode.VOLTAGE, 1.0, compliance=1e-3)
current = measure_result(keithley, SourceMode.VOLTAGE)

# Current mode
apply_source(keithley, SourceMode.CURRENT, 1e-6, compliance=10.0)
voltage = measure_result(keithley, SourceMode.CURRENT)
```

**Or use the config object:**
```python
from Measurments.source_modes import SourceModeConfig, SourceMode

config = SourceModeConfig(SourceMode.CURRENT, 1e-6, 10.0)
config.apply(keithley)
measurement = config.measure(keithley)
```

---

### 4. Sweep Patterns

**Replace this:**
```python
# OLD - duplicated logic
if sweep_type == "PS":
    v_list = list(np.arange(start, stop, step))
elif sweep_type == "FS":
    forward = list(np.arange(start, stop, step))
    reverse = list(np.arange(stop, start, -step))
    v_list = forward + reverse
# ... etc
```

**With this:**
```python
# NEW - all patterns in one place
from Measurments.sweep_patterns import build_sweep_values, SweepType

v_list = build_sweep_values(
    start=0, 
    stop=1, 
    step=0.1, 
    sweep_type=SweepType.FULL
)
```

---

### 5. Multiplexer Routing

**Replace this:**
```python
# OLD - if-statements everywhere
if self.multiplexer_type == "Pyswitchbox":
    pins = get_device_pins(device)
    # self.switchbox.activate(pins)
elif self.multiplexer_type == "Electronic_Mpx":
    self.mpx.select_channel(device_number)
elif self.multiplexer_type == "Multiplexer_10_OUT":
    # ...
```

**With this:**
```python
# NEW - unified interface
from Equipment.multiplexer_manager import MultiplexerManager

# Create manager once (in __init__)
self.mpx_manager = MultiplexerManager.create(
    self.multiplexer_type,
    pin_mapping=pin_mapping,  # for Pyswitchbox
    controller=self.mpx        # for Electronic_Mpx
)

# Use anywhere - single line!
self.mpx_manager.route_to_device(device_name, device_index)
```

---

### 6. Data Formatting

**Replace this:**
```python
# OLD - different formats everywhere
if self.record_temp_var.get():
    data = np.column_stack((timestamps, temperatures, voltages, currents, ...))
    header = "Time(s)\tTemperature(C)\tVoltage(V)\t..."
    fmt = "%0.3E\t%0.3E\t%0.3E\t..."
else:
    data = np.column_stack((timestamps, voltages, currents, ...))
    header = "Time(s)\tVoltage(V)\tCurrent(A)\t..."
    fmt = "%0.3E\t%0.3E\t%0.3E"

np.savetxt(filepath, data, fmt=fmt, header=header, comments="# ")
```

**With this:**
```python
# NEW - consistent formatting
from Measurments.data_formats import DataFormatter, save_measurement_data

formatter = DataFormatter()
data, header, fmt = formatter.format_iv_data(
    timestamps=timestamps,
    voltages=voltages,
    currents=currents,
    temperatures=temperatures  # Optional
)

save_measurement_data(filepath, data, header, fmt)
```

---

## Example: Refactoring a Measurement Function

### Before (scattered if-statements):

```python
def run_iv_sweep(self, keithley, optical, psu, led, power, start_v, stop_v, step_v, sweep_type, icc):
    # Build voltage list
    if sweep_type == "PS":
        v_list = list(np.arange(start_v, stop_v, step_v))
    elif sweep_type == "FS":
        forward = list(np.arange(start_v, stop_v, step_v))
        reverse = list(np.arange(stop_v, start_v, -step_v))
        v_list = forward + reverse
    
    # Enable light
    if optical is not None:
        optical.set_enabled(True)
    elif psu is not None:
        psu.led_on_380(power)
    
    # Measure
    v_arr, c_arr = [], []
    for v in v_list:
        keithley.set_voltage(v, icc)
        time.sleep(0.1)
        current_tuple = keithley.measure_current()
        current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
        v_arr.append(v)
        c_arr.append(current)
    
    # Disable light
    if optical is not None:
        optical.set_enabled(False)
    elif psu is not None:
        psu.led_off_380()
    
    return v_arr, c_arr
```

### After (clean and modular):

```python
from Measurments.optical_controller import OpticalController
from Measurments.source_modes import SourceMode, apply_source, measure_result
from Measurments.sweep_patterns import build_sweep_values
from Measurments.data_utils import safe_measure_current

def run_iv_sweep(self, keithley, optical, psu, led, power, start_v, stop_v, step_v, sweep_type, icc):
    # Build voltage list - one line!
    v_list = build_sweep_values(start_v, stop_v, step_v, sweep_type)
    
    # Light control - unified interface
    optical_ctrl = OpticalController(optical=optical, psu=psu)
    optical_ctrl.enable(power)
    
    # Measure - clean and simple
    v_arr, c_arr = [], []
    for v in v_list:
        apply_source(keithley, SourceMode.VOLTAGE, v, icc)
        time.sleep(0.1)
        current = safe_measure_current(keithley)
        v_arr.append(v)
        c_arr.append(current)
    
    # Auto-cleanup
    optical_ctrl.disable()
    
    return v_arr, c_arr
```

**Benefits:**
- ✅ 40% fewer lines
- ✅ No duplicated logic
- ✅ Easy to add new features (e.g., current source mode)
- ✅ Clear, readable code

---

## Migration Checklist

For each measurement function:

- [ ] Replace tuple normalization with `safe_measure_*()` functions
- [ ] Replace optical/LED if-blocks with `OpticalController`
- [ ] Replace voltage/current source with `apply_source()` / `measure_result()`
- [ ] Replace sweep pattern logic with `build_sweep_values()`
- [ ] Replace multiplexer routing with `MultiplexerManager`
- [ ] Replace data formatting with `DataFormatter`

---

## Testing Your Changes

After refactoring, verify:

1. **Functional equivalence:** Same results as before
2. **Edge cases:** Handle errors gracefully
3. **Backward compatibility:** Existing code still works

```python
# Test normalization
from Measurments.data_utils import normalize_measurement

assert normalize_measurement(1.5) == 1.5
assert normalize_measurement((None, 1.5)) == 1.5
assert normalize_measurement([1.0, 2.0]) == 2.0

# Test sweep patterns
from Measurments.sweep_patterns import build_sweep_values, SweepType

values = build_sweep_values(0, 1, 0.5, SweepType.FULL)
assert values == [0.0, 0.5, 1.0, 0.5, 0.0]
```

---

## Need Help?

- Each module has built-in tests: `python -m Measurments.data_utils`
- Check docstrings for detailed examples
- See REFACTORING_SUMMARY.md for architecture overview

