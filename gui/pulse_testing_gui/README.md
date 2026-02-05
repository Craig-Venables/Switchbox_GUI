# Pulse Testing GUI

Fast, buffer-based pulse testing interface with real-time visualization for Keithley instruments. Supports both Keithley 2450 (TSP-based) and Keithley 4200A-SCS (KXCI-based) systems.

## Purpose

The Pulse Testing GUI provides a specialized interface for pulse-based measurements on memristive devices. It automatically detects and routes tests to the appropriate measurement system based on device address, supporting both Keithley 2450 TSP scripts and Keithley 4200A KXCI-based measurements.

## Key Features

- **Multi-System Support**: Automatic detection of 2450 vs 4200A systems
- **Pulse-Read-Repeat Tests**: Fast pulsing with readout after each pulse
- **Width Sweeps**: Characterize device response vs pulse width
- **Potentiation/Depression**: Train devices with alternating pulses
- **Endurance Testing**: Long-term cycling tests
- **Real-Time Visualization**: Live plots during measurement
- **Test Parameter Configuration**: Flexible test setup
- **Data Saving**: Customizable save locations with metadata

## Entry Points

### Standalone Mode
```python
import tkinter as tk
from gui.pulse_testing_gui import TSPTestingGUI

root = tk.Tk()
gui = TSPTestingGUI(
    root,
    device_address="USB0::0x05E6::0x2450::04496615::INSTR"
)
root.mainloop()
```

### Launched from Measurement GUI
```python
# User clicks "Pulse Testing" button in MeasurementGUI
# Internal code:
from gui.pulse_testing_gui import TSPTestingGUI
pulse_gui = TSPTestingGUI(master, device_address=address)
```

## Dependencies

### Core Dependencies
- `tkinter`: GUI framework
- `matplotlib`: Real-time plotting
- `numpy`: Numerical operations

### Project Dependencies
- `Pulse_Testing.system_wrapper`: System detection and routing
- `Pulse_Testing.test_capabilities`: Which system supports which test (single source of truth)
- `Pulse_Testing.test_definitions`: Test display names, params, descriptions, plot types (GUI metadata)
- `Equipment.SMU_AND_PMU.Keithley2450_TSP`: 2450 TSP interface
- `Equipment.SMU_AND_PMU.keithley2450_tsp_scripts`: 2450 test scripts
- `Equipment.SMU_AND_PMU.keithley4200_kxci_scripts`: 4200A KXCI scripts
- `Measurements.data_formats`: Data formatting and saving

## File Structure

```
pulse_testing_gui/
├── README.md           # This file
├── __init__.py         # Package exports (TSPTestingGUI)
├── config.py           # Paths, config file names, window geometry
├── logic.py            # get_available_devices(), run_test_worker() for device scan and test run
├── main.py             # TSPTestingGUI: layout wiring, callbacks, save; delegates to ui/ and plot_handlers
├── plot_handlers.py    # plot_by_type() + all _plot_* result-plot implementations
├── ui/
│   ├── __init__.py     # Exports build_* and PulseDiagramHelper
│   ├── connection.py       # build_connection_section, toggle_connection_section
│   ├── test_selection.py   # build_test_selection_section
│   ├── diagram_section.py  # build_pulse_diagram_section
│   ├── parameters.py       # build_parameters_section
│   ├── status_section.py   # build_status_section
│   ├── plot_section.py     # build_plot_section
│   ├── pulse_diagram.py    # PulseDiagramHelper (pulse pattern preview _draw_*)
│   └── tabs_optical.py         # Optical tab (Oxxius laser pulsing)
└── (Pulse_Testing/    # Backend: test_definitions, test_capabilities, system_wrapper, systems/)
```

Tabs: **Manual Testing** | **Automated Testing** | **Optical** (Oxxius laser ms-scale pulsing).

## Refactor summary

- **Backend**: Test list and params in `Pulse_Testing/test_definitions.py`; per-system support in `test_capabilities.py`. Adding a test or system is documented in `Pulse_Testing/README.md`.
- **GUI**: `config.py` for paths/geometry; `logic.py` for device scan and `run_test_worker()`; `plot_handlers` holds `plot_by_type()` and all `_plot_*` implementations; `ui/` holds section builders (connection, test_selection, diagram_section, parameters, status_section, plot_section) and `PulseDiagramHelper` in `ui/pulse_diagram.py`; `ui/tabs_optical` is the Optical tab (Oxxius laser pulsing). Main wires layout (calls build_*), handles callbacks, save, and run flow.

## Adding a new test or system

- **New test**: Add it in the **Pulse_Testing** backend (see `Pulse_Testing/README.md`): `test_capabilities.py`, `test_definitions.py`, and the system implementations. The GUI will show it automatically for systems that support it.
- **New system**: Add a new system class in `Pulse_Testing/systems/`, register it in `system_wrapper.py`, and add a row in `test_capabilities.SYSTEM_CAPABILITIES`. The GUI filters the test list by current system, so only supported tests appear.

## Main Class

### `TSPTestingGUI`

Main window class for pulse testing interface.

**Parameters**:
- `master`: Parent Tkinter window
- `device_address`: VISA address of instrument (optional)
- `sample_name`: Sample identifier (optional)
- `device_label`: Device label (optional)

**Key Methods**:
- `connect_device()`: Connect to measurement system
- `disconnect_device()`: Disconnect from system
- `run_test()`: Execute selected test
- `update_plot()`: Update real-time plots
- `save_data()`: Save measurement data

## Supported Tests

### 1. Pulse-Read-Repeat
Apply a pulse, then read the state. Repeat for specified number of cycles.

### 2. Multi-Pulse-Then-Read
Apply multiple pulses in sequence, then read once.

### 3. Width Sweep
Sweep pulse width while keeping amplitude constant.

### 4. Potentiation/Depression Cycle
Alternate between potentiation (set) and depression (reset) pulses.

### 5. Endurance Test
Long-term cycling test with periodic readout.

### 6. Custom Tests
User-defined test patterns via configuration.

## System Detection

The GUI automatically detects the measurement system:

### Keithley 2450 Detection
- VISA address contains "2450"
- Uses TSP script-based measurements
- Terminal selection (front/rear)

### Keithley 4200A Detection
- VISA address matches 4200A pattern
- Uses KXCI-based measurements
- Full parameter access

## Usage Flow

1. **Launch**: GUI opens (standalone or from MeasurementGUI)
2. **Connection**: User enters device address or uses auto-detect
3. **System Detection**: GUI identifies system type (2450/4200A)
4. **Test Selection**: User selects test from available tests
5. **Configuration**: User configures test parameters
6. **Execution**: User clicks "Run" to start test
7. **Visualization**: Real-time plots update during test
8. **Saving**: Data is saved automatically or on user request

## Relationships

```
TSPTestingGUI (this module)
    ├─> Can be launched from: MeasurementGUI (gui.measurement_gui)
    ├─> Can be standalone
    └─> Uses SystemWrapper to route to:
            ├─> Keithley 2450 system (TSP scripts)
            └─> Keithley 4200A system (KXCI scripts)
```

## Examples

### Standalone Usage
```python
import tkinter as tk
from gui.pulse_testing_gui import TSPTestingGUI

root = tk.Tk()
gui = TSPTestingGUI(
    root,
    device_address="USB0::0x05E6::0x2450::04496615::INSTR",
    sample_name="Sample_A",
    device_label="D1"
)
root.mainloop()
```

### Launching from Measurement GUI
```python
# In MeasurementGUI class
def open_pulse_testing(self):
    from gui.pulse_testing_gui import TSPTestingGUI
    pulse_gui = TSPTestingGUI(
        self.master,
        device_address=self.keithley_address,
        sample_name=self.sample_name,
        device_label=self.device_label
    )
```

### Running a Test Programmatically
```python
# After GUI is created and device is connected
gui.system_var.set("keithley2450")  # Select system
gui.test_function_var.set("Pulse-Read-Repeat")  # Select test
gui.configure_test_parameters(...)  # Set parameters
gui.run_test()  # Execute test
```

## Configuration

Test parameters can be configured via the GUI or JSON files:
- Pulse amplitude and width
- Read voltage/current
- Number of cycles
- Delay times
- Terminal selection (for 2450)

## Notes

- The GUI automatically adapts available tests based on connected system
- Real-time plotting is optimized for fast pulse measurements
- Data saving includes test configuration metadata
- Supports both TSP and KXCI measurement paradigms
- Terminal selection (front/rear) is important for 2450 measurements

