# Quick Reference Card

One-page cheat sheet for the new modular utilities.

---

## 🔧 Data Normalization

```python
from Measurments.data_utils import safe_measure_current, safe_measure_voltage

# Instead of complex tuple checking:
current = safe_measure_current(keithley)  # Always returns float
voltage = safe_measure_voltage(keithley)  # Always returns float
```

---

## 💡 Optical Control

```python
from Measurments.optical_controller import OpticalController

# One interface for all light sources
optical_ctrl = OpticalController(optical=laser, psu=psu)
optical_ctrl.enable(power=1.5)
# ... measurement ...
optical_ctrl.disable()

# Or use context manager (auto-cleanup)
with OpticalController(optical=laser, psu=psu) as ctrl:
    ctrl.enable(1.5)
    # ... measurement ...
```

---

## ⚡ Source Modes

```python
from Measurments.source_modes import SourceMode, apply_source, measure_result

# Voltage mode (traditional)
apply_source(keithley, SourceMode.VOLTAGE, 1.0, compliance=1e-3)
current = measure_result(keithley, SourceMode.VOLTAGE)

# Current mode (NEW!)
apply_source(keithley, SourceMode.CURRENT, 1e-6, compliance=10.0)
voltage = measure_result(keithley, SourceMode.CURRENT)
```

---

## 📊 Sweep Patterns

```python
from Measurments.sweep_patterns import build_sweep_values, SweepType

# Generate any sweep pattern
voltages = build_sweep_values(
    start=0, 
    stop=1, 
    step=0.1, 
    sweep_type=SweepType.FULL  # or POSITIVE, NEGATIVE, TRIANGLE
)
```

**Sweep Types:**
- `SweepType.POSITIVE` - Start → Stop
- `SweepType.FULL` - Start → Stop → Start
- `SweepType.TRIANGLE` - Start → Stop → Negative → Start
- `SweepType.NEGATIVE` - Negative sweep

---

## 🔀 Multiplexer Routing

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

---

## 📁 Data Formatting

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

---

## 📝 File Naming

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

## 🎯 Complete Example

```python
from Measurments.source_modes import SourceMode, apply_source, measure_result
from Measurments.sweep_patterns import build_sweep_values, SweepType
from Measurments.optical_controller import OpticalController
from Measurments.data_utils import safe_measure_current

# Setup
optical_ctrl = OpticalController(optical=laser, psu=psu)
voltages = build_sweep_values(0, 1, 0.1, SweepType.FULL)

# Measure
optical_ctrl.enable(1.5)
for v in voltages:
    apply_source(keithley, SourceMode.VOLTAGE, v, 1e-3)
    i = safe_measure_current(keithley)
    # ... store data ...
optical_ctrl.disable()
```

---

## 🔄 Migration Patterns

### Pattern 1: Tuple Normalization
```python
# OLD (34 duplicates)
current_tuple = keithley.measure_current()
current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)

# NEW (1 line)
current = safe_measure_current(keithley)
```

### Pattern 2: Optical Control
```python
# OLD (26 duplicates)
if optical is not None:
    optical.set_enabled(True)
elif psu is not None:
    psu.led_on_380(power)

# NEW (1 line)
OpticalController(optical, psu).enable(power)
```

### Pattern 3: Sweep Generation
```python
# OLD (7 duplicates)
if sweep_type == "FS":
    forward = list(np.arange(start, stop, step))
    reverse = list(np.arange(stop, start, -step))
    v_list = forward + reverse
# ... many more cases ...

# NEW (1 line)
v_list = build_sweep_values(start, stop, step, SweepType.FULL)
```

---

## 📚 Import Cheat Sheet

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

## ✅ Testing

```bash
# Test each module
python -m Measurments.data_utils
python -m Measurments.optical_controller
python -m Measurments.source_modes
python -m Measurments.sweep_patterns
python -m Equipment.multiplexer_manager
python -m Measurments.data_formats
```

All should print "All tests passed!" ✓

---

## ⚡ Conditional Testing

Smart workflow that screens devices and runs tests only on memristive devices:

**Configuration** (`Json_Files/conditional_test_config.json`):
- Quick test: Fast screening (e.g., 0-2.8V sweep)
- Thresholds: Score ≥60 for basic test, ≥80 for high-quality test
- Re-evaluation: Check score after basic test, run high-quality if improved
- Final test: Run on best devices after all complete (e.g., laser test)

**Selection Modes**:
- `"top_x"`: Top X devices above threshold
- `"all_above_score"`: All devices above threshold

**Usage**:
1. Configure in **Advanced Tests** tab
2. Save configuration
3. Run from **Advanced Tests** or **Measurements** tab

---

## 🚀 Next Steps

1. ✅ Understand this reference
2. ✅ Try one example from IMPLEMENTATION_EXAMPLES.md
3. ✅ Refactor one function using USAGE_GUIDE.md
4. ✅ Use utilities in all new code

---

**Keep this reference handy while coding!**

