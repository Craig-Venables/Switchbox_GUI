# GUI Package

This package contains all GUI modules for the Switchbox Measurement System, organized by application functionality.

## Overview

The GUI package provides a modular, organized structure for all user interfaces in the measurement system. Each GUI module is self-contained with its own components, utilities, and documentation.

## Package Structure

```
gui/
├── README.md                    # This file
├── __init__.py                  # Package exports
├── sample_gui/                  # Device selection and sample management
│   ├── README.md
│   ├── __init__.py
│   └── main.py                  # SampleGUI class
├── measurement_gui/             # Main measurement interface
│   ├── README.md
│   ├── __init__.py
│   ├── main.py                  # MeasurementGUI class
│   ├── layout_builder.py        # UI layout construction
│   ├── plot_panels.py           # Plotting components
│   ├── plot_updaters.py         # Real-time plot updates
│   └── custom_measurements_builder.py  # Custom measurement UI
├── pulse_testing_gui/           # Pulse testing interface
│   ├── README.md
│   ├── __init__.py
│   ├── main.py                  # TSPTestingGUI class
│   └── pulse_testing/           # Pulse testing utilities
├── motor_control_gui/           # Motor control and laser positioning
│   ├── README.md
│   ├── __init__.py
│   └── main.py                  # MotorControlWindow class
├── connection_check_gui/        # Connection verification tool
│   ├── README.md
│   ├── __init__.py
│   └── main.py                  # CheckConnection class
└── components/                  # Shared GUI components
```

## GUI Modules

### 1. Sample GUI (`sample_gui/`)
**Purpose**: Main entry point for device selection and sample management.

**Key Features**:
- Visual device map with click-to-select
- Device status tracking
- Multiplexer routing control
- Quick scan functionality
- Sample configuration

**See**: [sample_gui/README.md](sample_gui/README.md)

### 2. Measurement GUI (`measurement_gui/`)
**Purpose**: Central measurement interface for IV/PMU/SMU measurements.

**Key Features**:
- Instrument connection management
- IV sweep configuration and execution
- Real-time plotting
- Custom measurement sweeps
- Launches specialized tools

**See**: [measurement_gui/README.md](measurement_gui/README.md)

### 3. Pulse Testing GUI (`pulse_testing_gui/`)
**Purpose**: Fast pulse testing interface for Keithley instruments.

**Key Features**:
- Pulse-read-repeat tests
- Width sweeps
- Potentiation/depression cycles
- Endurance testing
- Multi-system support (2450, 4200A)

**See**: [pulse_testing_gui/README.md](pulse_testing_gui/README.md)

### 4. Motor Control GUI (`motor_control_gui/`)
**Purpose**: XY stage motor control with laser positioning.

**Key Features**:
- Interactive position map
- Jog controls
- Position presets
- Raster scanning
- Function generator integration

**See**: [motor_control_gui/README.md](motor_control_gui/README.md)

### 5. Connection Check GUI (`connection_check_gui/`)
**Purpose**: Real-time connection verification tool.

**Key Features**:
- Real-time current monitoring
- Audio alerts
- Adjustable thresholds
- Data recording

**See**: [connection_check_gui/README.md](connection_check_gui/README.md)

## Application Flow

```
main.py
  └─> SampleGUI (sample_gui/)
        └─> MeasurementGUI (measurement_gui/)
              ├─> TSPTestingGUI (pulse_testing_gui/)
              ├─> CheckConnection (connection_check_gui/)
              ├─> MotorControlWindow (motor_control_gui/)
              ├─> AdvancedTestsGUI
              └─> AutomatedTesterGUI
```

## Usage

### Importing GUI Modules

```python
# Import from package
from gui.sample_gui import SampleGUI
from gui.measurement_gui import MeasurementGUI
from gui.pulse_testing_gui import TSPTestingGUI
from gui.motor_control_gui import MotorControlWindow
from gui.connection_check_gui import CheckConnection

# Backward compatibility (root-level wrappers)
from Sample_GUI import SampleGUI
from Motor_Controll_GUI import MotorControlWindow
from Check_Connection_GUI import CheckConnection
```

### Running Individual GUIs

```python
# Sample GUI (main entry point)
import tkinter as tk
from gui.sample_gui import SampleGUI

root = tk.Tk()
app = SampleGUI(root)
root.mainloop()
```

## Dependencies

### Core Dependencies
- `tkinter`: GUI framework (Python standard library)
- `matplotlib`: Plotting and visualization
- `numpy`: Numerical operations

### Project Dependencies
- `Equipment.*`: Hardware control modules
- `Measurements.*`: Measurement services and utilities
- `Json_Files/`: Configuration and mapping files

## Architecture Principles

1. **Modularity**: Each GUI is self-contained in its own package
2. **Separation of Concerns**: UI construction, plotting, and business logic are separated
3. **Backward Compatibility**: Root-level wrapper files maintain old import paths
4. **Clear Dependencies**: Each module explicitly documents its dependencies
5. **Reusability**: Shared components are in `components/` directory

## Development Guidelines

1. **New GUI Modules**: Create a new subdirectory in `gui/` with:
   - `__init__.py` (exports main class)
   - `main.py` (main GUI class)
   - `README.md` (documentation)

2. **Imports**: Always use `gui.*` paths in new code
3. **Backward Compatibility**: Create root-level wrapper for old import paths
4. **Documentation**: Update this README and module READMEs when adding features

## Testing

Each GUI module can be run standalone for testing:

```python
# Test individual GUI
python -m gui.sample_gui.main
python -m gui.measurement_gui.main
python -m gui.pulse_testing_gui.main
python -m gui.motor_control_gui.main
python -m gui.connection_check_gui.main
```

## Notes

- The `components/` directory contains shared GUI components used across modules
- Root-level wrapper files (e.g., `Sample_GUI.py`) provide backward compatibility
- All GUI modules follow a consistent structure and documentation format

