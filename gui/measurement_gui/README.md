# Measurement GUI

Main measurement interface for IV/PMU/SMU measurements on device arrays. Provides comprehensive control over instrument connections, measurement configuration, real-time plotting, and data saving.

## Purpose

The Measurement GUI acts as the central hub for performing measurements. It provides a tabbed interface for configuring measurement parameters, connecting instruments, running measurements, and visualizing results in real-time.

## Key Features

- **Instrument Management**: Connect and configure SMU, PSU, and temperature controllers
- **IV Sweep Configuration**: Configure voltage/current sweeps with various modes
- **Custom Measurements**: Load and execute custom measurement sweeps from JSON files
- **Real-Time Plotting**: Live updates of voltage, current, and resistance plots
- **Sequential Measurements**: Automated measurement of multiple devices
- **Manual Test Controls**: Endurance, retention, and transient measurements
- **Data Saving**: Automatic file naming and data organization
- **Telegram Integration**: Notification support for long-running measurements
- **Optical Control**: LED and laser excitation control
- **Tool Launcher**: Access to specialized testing tools

## Entry Points

### Launched from Sample GUI
```python
# In SampleGUI, when user clicks "Start Measurement"
from gui.measurement_gui import MeasurementGUI

measurement_gui = MeasurementGUI(
    master=parent_window,
    sample_type="Cross_bar",
    section="A",
    device_list=["1", "2", "3"],
    sample_gui=self
)
```

### Direct Usage
```python
import tkinter as tk
from gui.measurement_gui import MeasurementGUI

root = tk.Toplevel()
gui = MeasurementGUI(
    master=root,
    sample_type="Cross_bar",
    section="A",
    device_list=["1", "2", "3"]
)
```

## Launches Other GUIs

The Measurement GUI can launch specialized tools:

### 1. Pulse Testing GUI
```python
# Access via "Pulse Testing" button
from gui.pulse_testing_gui import TSPTestingGUI
```

### 2. Connection Check GUI
```python
# Access via "Check Connection" button
from gui.connection_check_gui import CheckConnection
check_gui = CheckConnection(master=self.master, keithley=self.keithley)
```

### 3. Motor Control GUI
```python
# Access via "Motor Control" button
from gui.motor_control_gui import MotorControlWindow
window = MotorControlWindow()
```

### 4. Advanced Tests GUI
Access to advanced memristor tests (PPF, STDP, SRDP, transient decay).

### 5. Automated Tester GUI
Batch device testing workflows.

## Dependencies

### Core Dependencies
- `tkinter`: GUI framework
- `matplotlib`: Real-time plotting
- `numpy`: Numerical operations

### Project Dependencies
- `Measurments.measurement_services_smu`: SMU measurement service
- `Measurments.measurement_services_pmu`: PMU measurement service
- `Measurments.connection_manager`: Instrument connection management
- `Measurments.data_saver`: Data saving utilities
- `Equipment.managers.*`: Hardware managers (IV controller, PSU, temperature)
- `gui.measurement_gui.layout_builder`: UI layout construction
- `gui.measurement_gui.plot_panels`: Plotting components
- `gui.measurement_gui.plot_updaters`: Real-time plot updates

## File Structure

```
measurement_gui/
├── README.md                    # This file
├── __init__.py                  # Package exports (MeasurementGUI)
├── main.py                      # MeasurementGUI class (~3658 lines)
├── layout_builder.py            # UI layout construction
├── plot_panels.py               # Plotting components
├── plot_updaters.py             # Real-time plot updates
└── custom_measurements_builder.py  # Custom measurement UI builder
```

## Main Class

### `MeasurementGUI`

Main window class for measurement interface.

**Parameters**:
- `master`: Parent Tkinter window
- `sample_type`: Type of sample (e.g., "Cross_bar")
- `section`: Sample section identifier
- `device_list`: List of device IDs to measure
- `sample_gui`: Reference to SampleGUI (optional)

**Key Components**:
- `SMUAdapter`: Adapter layer for unified instrument API
- `connections`: `InstrumentConnectionManager` instance
- `measurement_service`: `MeasurementService` instance
- `layout_builder`: `MeasurementGUILayoutBuilder` instance
- `plot_panels`: `MeasurementPlotPanels` instance
- `plot_updaters`: `PlotUpdaters` instance

## Key Features Details

### 1. Instrument Connection
- Auto-connect on system selection
- Connection status indicators
- Multiple instrument support (SMU, PSU, temp controller)

### 2. Measurement Configuration
- **Sweep Types**: Full sweep (FS), half sweep (HS), etc.
- **Voltage Range Modes**: Fixed step, time-based, rate-based
- **Custom Measurements**: Load from JSON configuration files
- **Optical Control**: LED/laser integration

### 3. Real-Time Plotting
- Voltage vs Current plots
- Resistance plots
- Time-series data
- Live updates during measurement

### 4. Data Management
- Automatic file naming with timestamps
- Device and sample information in filenames
- Summary plots
- Data export formats

## Usage Flow

1. **Launch**: User selects devices in SampleGUI and clicks "Start Measurement"
2. **Connection**: GUI auto-connects to instruments based on system config
3. **Configuration**: User configures sweep parameters in tabs
4. **Measurement**: User clicks "Run" to start measurement
5. **Visualization**: Real-time plots update as data is collected
6. **Saving**: Data is automatically saved when measurement completes
7. **Next Device**: User can move to next device or close

## Relationships

```
MeasurementGUI (this module)
    ├─> Launched from: SampleGUI (gui.sample_gui)
    ├─> Launches: TSPTestingGUI (gui.pulse_testing_gui)
    ├─> Launches: CheckConnection (gui.connection_check_gui)
    ├─> Launches: MotorControlWindow (gui.motor_control_gui)
    ├─> Uses: MeasurementService (Measurments.measurement_services_smu)
    ├─> Uses: ConnectionManager (Measurments.connection_manager)
    └─> Uses: Equipment managers (Equipment.managers.*)
```

## Configuration

The Measurement GUI uses JSON configuration files from `Json_Files/`:
- **Custom sweep configurations**: Load custom measurement patterns
- **System configurations**: Instrument addresses and settings

## Examples

### Basic Usage
```python
from gui.measurement_gui import MeasurementGUI

gui = MeasurementGUI(
    master=parent_window,
    sample_type="Cross_bar",
    section="A",
    device_list=["1", "2", "3"]
)
```

### Accessing Instrument Connection
```python
# Instrument is available after connection
if gui.connected and gui.keithley:
    gui.keithley.set_voltage(1.0, 1e-3)
    current = gui.keithley.measure_current()
```

### Launching Specialized Tools
```python
# Connection check tool
from gui.connection_check_gui import CheckConnection
check = CheckConnection(master=gui.master, keithley=gui.keithley)

# Motor control
from gui.motor_control_gui import MotorControlWindow
motor_gui = MotorControlWindow()
```

## Architecture Notes

- **Separation of Concerns**: UI (main.py), layout (layout_builder.py), plotting (plot_panels.py), and updates (plot_updaters.py) are separated
- **Service Layer**: Business logic is in MeasurementService, not in GUI
- **Manager Pattern**: Instrument connections use ConnectionManager
- **Adapter Pattern**: SMUAdapter provides unified interface to different instruments

## Notes

- The Measurement GUI is the central hub for all measurement operations
- It coordinates between multiple instruments and measurement services
- Real-time plotting is optimized for performance during fast sweeps
- Data saving includes metadata for later analysis

