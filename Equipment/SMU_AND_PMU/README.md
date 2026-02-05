# SMU_AND_PMU Package

This package contains all SMU (Source Measure Unit) and PMU (Pulse Measurement Unit) controllers and scripts, organized by instrument model. **Pulse Testing** uses these modules via adapters in `Pulse_Testing/systems/`; see **Pulse_Testing/README.md** for the unified layout (adapter → script/controller paths per system).

## Package Structure

```
Equipment/SMU_AND_PMU/
├── __init__.py                      # Backward compatibility exports
├── README.md                        # This file
│
├── keithley2400/                    # Keithley 2400/2401
│   ├── __init__.py
│   ├── controller.py                # Keithley2400Controller
│   ├── scpi_scripts.py               # Keithley2400_SCPI_Scripts (pulse tests)
│   └── simulation_2400.py           # Simulation2400
│
├── keithley2450/                    # Keithley 2450 (all modes)
│   ├── __init__.py
│   ├── controller.py                # Keithley2450Controller (SPCI)
│   ├── tsp_controller.py            # Keithley2450_TSP (TSP mode - fastest)
│   ├── tsp_sim_controller.py        # Keithley2450_TSP_Sim (simulation)
│   ├── spci_controller.py           # Keithley2450_SPCI (SPCI mode)
│   ├── tsp_scripts.py               # Keithley2450_TSP_Scripts
│   └── tsp_sim_scripts.py           # Keithley2450_TSP_Sim_Scripts
│
├── keithley4200/                    # Keithley 4200A-SCS
│   ├── __init__.py
│   ├── controller.py                # Keithley4200AController, PMUDualChannel
│   ├── kxci_controller.py           # Keithley4200A_KXCI
│   └── kxci_scripts.py              # Keithley4200A_KXCI_Scripts
│
├── hp4140b/                         # HP4140B
│   ├── __init__.py
│   └── controller.py                # HP4140BController
│
├── 4200A/                           # 4200A examples, C code, docs
│   ├── C_Code_with_python_scripts/
│   ├── Controll_With_C/
│   └── Controll_With_python/
│
├── 2450 Info/                       # 2450 documentation
│   ├── KEITHLEY_2450_REFERENCE.md
│   └── TSP_ERRORS_AND_FIXES.md
│
└── [Backward compatibility wrappers - old root-level files]
```

## New Recommended Imports

### Keithley 2400/2401
```python
from Equipment.SMU_AND_PMU.keithley2400 import Keithley2400Controller
```

### Keithley 2450
```python
# Standard SPCI controller
from Equipment.SMU_AND_PMU.keithley2450 import Keithley2450Controller

# TSP controller (fastest, recommended for pulses)
from Equipment.SMU_AND_PMU.keithley2450 import Keithley2450_TSP

# TSP simulation controller
from Equipment.SMU_AND_PMU.keithley2450 import Keithley2450_TSP_Sim

# TSP scripts
from Equipment.SMU_AND_PMU.keithley2450.tsp_scripts import Keithley2450_TSP_Scripts
```

### Keithley 4200A
```python
# Main controller (SMU/PMU)
from Equipment.SMU_AND_PMU.keithley4200 import (
    Keithley4200AController,
    Keithley4200A_PMUDualChannel,
)

# KXCI controller
from Equipment.SMU_AND_PMU.keithley4200 import Keithley4200A_KXCI

# KXCI scripts
from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import Keithley4200A_KXCI_Scripts
```

### HP4140B
```python
from Equipment.SMU_AND_PMU.hp4140b import HP4140BController
```

## Backward Compatibility

All old import paths still work! The root-level files are compatibility wrappers.

### Old Imports (Still Work)
```python
# These still work exactly as before
from Equipment.SMU_AND_PMU.Keithley2400 import Keithley2400Controller
from Equipment.SMU_AND_PMU.Keithley2450_TSP import Keithley2450_TSP
from Equipment.SMU_AND_PMU.Keithley4200A import Keithley4200AController
from Equipment.SMU_AND_PMU.keithley2450_tsp_scripts import Keithley2450_TSP_Scripts
```

However, **new code should use the new import paths** as they're cleaner and more maintainable.

## Instrument Overview

### Keithley 2400/2401
- **Class**: `Keithley2400Controller`
- **Features**: Standard SMU, ±200V, ±1A
- **Interface**: GPIB, USB, LAN
- **Library**: PyMeasure

### Keithley 2450
- **Standard Controller**: `Keithley2450Controller` (SPCI mode)
- **TSP Controller**: `Keithley2450_TSP` (TSP mode - recommended for fast pulses)
- **Features**: ±200V, ±1A, touchscreen, TSP scripting
- **Fastest Mode**: TSP mode for sub-millisecond pulses
- **Scripts**: Pre-configured test patterns in `tsp_scripts.py`

### Keithley 4200A-SCS
- **Main Controller**: `Keithley4200AController` / `Keithley4200A_PMUDualChannel`
- **KXCI Controller**: `Keithley4200A_KXCI` (external C code control)
- **Features**: SMU + PMU channels, waveform capture, laser pulse integration
- **PMU**: Pulse Measurement Unit for accurate waveform capture
- **See**: `4200A/` directory for C code examples and documentation

### HP4140B
- **Class**: `HP4140BController`
- **Features**: Picoammeter/DC voltage source, GPIB interface
- **Use Case**: Very low current measurements (picoampere range)

## Usage Examples

### Basic SMU Control (Keithley 2400)
```python
from Equipment.SMU_AND_PMU.keithley2400 import Keithley2400Controller

smu = Keithley2400Controller('GPIB0::24::INSTR')
smu.set_voltage(1.0, Icc=0.01)  # 1V with 10mA compliance
current = smu.measure_current()
smu.close()
```

### Fast Pulse Testing (Keithley 2450 TSP)
```python
from Equipment.SMU_AND_PMU.keithley2450 import Keithley2450_TSP
from Equipment.SMU_AND_PMU.keithley2450.tsp_scripts import Keithley2450_TSP_Scripts

# Connect in TSP mode
tsp = Keithley2450_TSP('USB0::0x05E6::0x2450::04496615::INSTR')
scripts = Keithley2450_TSP_Scripts(tsp)

# Run pulse-read-repeat test
scripts.pulse_read_repeat(
    pulse_voltage=1.0,
    pulse_width=100e-6,
    read_voltage=0.2,
    num_cycles=100
)
```

### PMU Measurements (Keithley 4200A)
```python
from Equipment.SMU_AND_PMU.keithley4200 import Keithley4200A_PMUDualChannel

pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")
pmu.prepare_measure_at_voltage(
    amplitude_v=0.25,
    width_s=50e-6,
    period_s=200e-6,
    num_pulses=100
)
pmu.start()
pmu.wait()
data = pmu.fetch()
```

## Integration with Managers

All controllers are integrated via the `IVControllerManager`:

```python
from Equipment.managers.iv_controller import IVControllerManager

# Unified interface for all SMUs
iv_manager = IVControllerManager(
    smu_type="Keithley 2450",  # Or "Keithley 2401", "Hp4140b", etc.
    address="USB0::0x05E6::0x2450::04496615::INSTR"
)
```

See `Equipment/managers/iv_controller.py` for details.

## Notes

- **TSP Mode**: Keithley 2450 must be in TSP mode for `Keithley2450_TSP`. Switch via: MENU → System → Settings → Command Set → TSP
- **Lazy Imports**: Managers use lazy imports, so missing dependencies won't crash the application
- **ProxyClass**: Used by 4200A controllers, located at `Equipment/SMU_AND_PMU/ProxyClass.py`
- **Documentation**: See `4200A/` and `2450 Info/` directories for detailed documentation and examples

