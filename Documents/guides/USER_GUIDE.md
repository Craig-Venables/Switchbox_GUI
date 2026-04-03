# User Guide - Using the Modular Utilities

This guide shows how to use the modular utilities for measurements, sweeps, optical control, and data formatting.

---

## Quick Start Examples

### 1. Basic IV Sweep with Optical Control

```python
from Measurments.source_modes import SourceMode, apply_source, measure_result
from Measurments.sweep_patterns import build_sweep_values, SweepType
from Measurments.optical_controller import OpticalController
from Measurments.data_utils import safe_measure_current

# Setup
optical_ctrl = OpticalController(optical=laser, psu=psu)
voltages = build_sweep_values(0, 1, 0.1, SweepType.FULL)

# Measurement loop
optical_ctrl.enable(power=1.5)
for v in voltages:
    apply_source(keithley, SourceMode.VOLTAGE, v, compliance=1e-3)
    time.sleep(0.05)
    current = safe_measure_current(keithley)
    # ... store data ...
optical_ctrl.disable()
```

---

## Core Utilities

### Data Normalization

**Problem:** Instruments return different formats (tuples, lists, floats)

**Solution:**
```python
from Measurments.data_utils import safe_measure_current, safe_measure_voltage

# Always returns float, handles all instrument types
current = safe_measure_current(keithley)
voltage = safe_measure_voltage(keithley)
```

**Replaces:**
```python
# OLD - scattered everywhere
current_tuple = keithley.measure_current()
current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
```

---

### Optical/LED Control

**Problem:** Different light sources require different control methods

**Solution:**
```python
from Measurments.optical_controller import OpticalController

# Works with laser OR PSU LED automatically
optical_ctrl = OpticalController(optical=laser, psu=psu)
optical_ctrl.enable(power=1.5)
# ... measurement ...
optical_ctrl.disable()

# Or use context manager (auto-disables)
with OpticalController(optical=laser, psu=psu) as ctrl:
    ctrl.enable(1.5)
    # ... measurement ...
    # Automatically disabled here
```

**Replaces:**
```python
# OLD - repeated if-statements
if optical is not None:
    optical.set_enabled(True)
elif psu is not None:
    psu.led_on_380(power)
```

---

### Source Modes (Voltage/Current)

**Feature:** Source voltage OR current, measure the other

**Voltage Mode (Traditional):**
```python
from Measurments.source_modes import SourceMode, apply_source, measure_result

apply_source(keithley, SourceMode.VOLTAGE, 1.0, compliance=1e-3)
current = measure_result(keithley, SourceMode.VOLTAGE)
```

**Current Mode (NEW!):**
```python
# Source current, measure voltage
apply_source(keithley, SourceMode.CURRENT, 1e-6, compliance=10.0)
voltage = measure_result(keithley, SourceMode.CURRENT)
```

**Using Config Object:**
```python
from Measurments.source_modes import SourceModeConfig, SourceMode

config = SourceModeConfig(SourceMode.CURRENT, 1e-6, 10.0)
config.apply(keithley)
measurement = config.measure(keithley)
```

---

### Sweep Patterns

**Generate any sweep pattern:**
```python
from Measurments.sweep_patterns import build_sweep_values, SweepType

# Full sweep (start → stop → start)
voltages = build_sweep_values(0, 1, 0.1, SweepType.FULL)

# Positive only
voltages = build_sweep_values(0, 1, 0.1, SweepType.POSITIVE)

# Triangle (with negative)
voltages = build_sweep_values(0, 1, 0.1, SweepType.TRIANGLE, neg_stop=-1)

# Negative only
voltages = build_sweep_values(-1, 0, 0.1, SweepType.NEGATIVE)
```

**Replaces:**
```python
# OLD - duplicated logic
if sweep_type == "PS":
    v_list = list(np.arange(start, stop, step))
elif sweep_type == "FS":
    forward = list(np.arange(start, stop, step))
    reverse = list(np.arange(stop, start, -step))
    v_list = forward + reverse
# ... many more cases ...
```

---

### Multiplexer Routing

**Unified interface for all multiplexer types:**
```python
from Equipment.multiplexer_manager import MultiplexerManager

# Create once (in __init__)
mpx = MultiplexerManager.create(
    "Pyswitchbox",  # or "Electronic_Mpx"
    pin_mapping=pin_mapping
)

# Use anywhere
mpx.route_to_device(device_name, device_index)

# Or with context manager (auto-disconnect)
from Equipment.multiplexer_manager import MultiplexerContext

with MultiplexerContext(mpx, device_name, device_index):
    # ... measurement ...
```

**Replaces:**
```python
# OLD - if-statements everywhere
if self.multiplexer_type == "Pyswitchbox":
    pins = get_device_pins(device)
    # ...
elif self.multiplexer_type == "Electronic_Mpx":
    self.mpx.select_channel(device_number)
# ...
```

---

### Data Formatting

**Consistent file output:**
```python
from Measurments.data_formats import DataFormatter, save_measurement_data
import numpy as np

formatter = DataFormatter()

# Format IV data
data, header, fmt = formatter.format_iv_data(
    timestamps=np.array([...]),
    voltages=np.array([...]),
    currents=np.array([...]),
    temperatures=np.array([...])  # Optional
)

# Save to file
from pathlib import Path
save_measurement_data(Path("data.txt"), data, header, fmt)
```

**File Naming:**
```python
from Measurments.data_formats import FileNamer

namer = FileNamer()

# Generate filename
filename = namer.create_iv_filename(
    device="A1",
    voltage=1.0,
    measurement_type="sweep",
    status="complete"
)
# → "Device_1_A1_1.0V_sweep_complete_20251014_123045.txt"

# Get device folder
folder = namer.get_device_folder("MySample", "A1", "IV_sweeps")
# → Path("Data_save_loc/MySample/A/1/IV_sweeps")
```

---

## Complete Example: Generic IV Sweep

```python
from Measurments.source_modes import SourceMode, apply_source, measure_result
from Measurments.sweep_patterns import build_sweep_values, SweepType
from Measurments.optical_controller import OpticalController
from Measurments.data_utils import safe_measure_current
from Measurments.data_formats import DataFormatter, save_measurement_data
import time
import numpy as np
from pathlib import Path

def run_iv_sweep(keithley, optical, psu, start_v, stop_v, step_v, sweep_type, icc, led_power=1.5):
    """Complete IV sweep with all utilities."""
    
    # Build voltage list - one line!
    voltages = build_sweep_values(start_v, stop_v, step_v, sweep_type)
    
    # Light control - unified interface
    optical_ctrl = OpticalController(optical=optical, psu=psu)
    optical_ctrl.enable(led_power)
    
    # Measure - clean and simple
    v_arr, c_arr, timestamps = [], [], []
    start_time = time.perf_counter()
    
    try:
        for v in voltages:
            apply_source(keithley, SourceMode.VOLTAGE, v, icc)
            time.sleep(0.1)
            current = safe_measure_current(keithley)
            v_arr.append(v)
            c_arr.append(current)
            timestamps.append(time.perf_counter() - start_time)
    finally:
        # Auto-cleanup
        apply_source(keithley, SourceMode.VOLTAGE, 0, icc)
        optical_ctrl.disable()
    
    return np.array(timestamps), np.array(v_arr), np.array(c_arr)
```

**Benefits:**
- ✅ 40% fewer lines
- ✅ No duplicated logic
- ✅ Easy to add features
- ✅ Clear, readable code

---

## Testing

Each module includes built-in tests:

```bash
python -m Measurments.data_utils
python -m Measurments.optical_controller
python -m Measurments.source_modes
python -m Measurments.sweep_patterns
python -m Equipment.multiplexer_manager
python -m Measurments.data_formats
```

All should print "All tests passed!" ✓

---

## Migration Checklist

When refactoring existing code:

- [ ] Replace tuple normalization with `safe_measure_*()` functions
- [ ] Replace optical/LED if-blocks with `OpticalController`
- [ ] Replace voltage/current source with `apply_source()` / `measure_result()`
- [ ] Replace sweep pattern logic with `build_sweep_values()`
- [ ] Replace multiplexer routing with `MultiplexerManager`
- [ ] Replace data formatting with `DataFormatter`

---

## Import Cheat Sheet

```python
# Data utilities
from Measurments.data_utils import (
    safe_measure_current,
    safe_measure_voltage,
    normalize_measurement
)

# Optical control
from Measurments.optical_controller import OpticalController

# Source modes
from Measurments.source_modes import (
    SourceMode,
    apply_source,
    measure_result,
    get_axis_labels
)

# Sweep patterns
from Measurments.sweep_patterns import (
    build_sweep_values,
    SweepType
)

# Multiplexer
from Equipment.multiplexer_manager import (
    MultiplexerManager,
    MultiplexerContext
)

# Data formatting
from Measurments.data_formats import (
    DataFormatter,
    FileNamer,
    save_measurement_data
)
```

---

---

## Conditional Memristive Testing

### Overview

Conditional testing is an intelligent workflow that automatically screens all devices with a quick test, analyzes them for memristive behavior, and then conditionally runs additional tests only on promising devices. This saves significant time by avoiding expensive tests on non-functional devices.

### How It Works

1. **Quick Screening**: Runs a fast test (e.g., 0-2.8V IV sweep) on all devices
2. **Analysis**: Each device is analyzed to determine memristivity score (0-100)
3. **Conditional Execution**: 
   - Devices with score ≥ 60: Run basic memristive test
   - Devices with score ≥ 80: Run high-quality test
   - If re-evaluation enabled: Re-check score after basic test, run high-quality if improved
4. **Final Test** (optional): After all devices complete, select best devices and run final test (e.g., laser test)

### Configuration

Configure conditional testing in the **Advanced Tests** tab:

1. **Thresholds**: Set score thresholds (default: 60 for basic, 80 for high-quality)
2. **Quick Test**: Select custom sweep for quick screening
3. **Basic Test**: Select custom sweep for basic memristive characterization
4. **High Quality Test**: Select custom sweep for advanced testing
5. **Re-evaluation**: Enable to re-check score after basic test
6. **Include Memcapacitive**: Toggle whether memcapacitive devices qualify
7. **Final Test**: Configure final test that runs on best devices
   - Selection mode: "top_x" or "all_above_score"
   - Parameters: Top X count, minimum score threshold
   - Final test: Custom sweep to run (e.g., laser test)

### Running Conditional Testing

**From Advanced Tests Tab:**
1. Configure all settings
2. Click **Save Config** to save configuration
3. Click **Run Conditional Testing**

**From Measurements Tab:**
1. Expand **Conditional Testing** section
2. Click **Load Config** to load saved configuration
3. Click **Run Conditional**

### Final Test Options

The final test runs after all devices complete their conditional tests:

- **Top X Mode**: Selects top X devices above minimum score (e.g., top 5 devices with score ≥ 80)
- **All Above Score Mode**: Selects all devices above minimum score (e.g., all devices with score ≥ 80)

**Safety**: A confirmation dialog appears before running final test, showing which devices will be tested. This is important for potentially damaging tests (e.g., laser).

### Example Workflow

1. Configure quick test: "Quick_Screen_2.8V" (0-2.8V, 1 sweep)
2. Set thresholds: Basic = 60, High Quality = 80
3. Configure basic test: "Basic_Memristive_Characterization"
4. Configure high-quality test: "Advanced_Memristive_Test"
5. Enable final test: Top 3 devices with score ≥ 80, run "Laser_Damage_Test"
6. Run conditional testing
7. System automatically:
   - Screens all devices
   - Runs basic test on devices with score ≥ 60
   - Runs high-quality test on devices with score ≥ 80
   - Re-evaluates and upgrades if score improves
   - At end, runs laser test on top 3 devices

### Tips

- Use a fast, simple sweep for quick test (minimize time per device)
- Adjust thresholds based on your device population
- Enable re-evaluation if devices may improve during basic test
- Use final test for expensive or potentially damaging tests
- Save different configurations for different scenarios

For detailed configuration options, see **[JSON_CONFIG_GUIDE.md](JSON_CONFIG_GUIDE.md)**.

---

## Additional Resources

- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - One-page cheat sheet
- **[JSON_CONFIG_GUIDE.md](JSON_CONFIG_GUIDE.md)** - JSON configuration guide for automated testing

