# Sample GUI

Device selection and sample management interface - the main entry point for the measurement system.

## Purpose

The Sample GUI provides a visual interface to browse device maps, select devices to test, control multiplexer routing, and launch measurement interfaces. It serves as the primary entry point for users to interact with the measurement system.

## Key Features

- **Visual Device Map**: Image viewer with click-to-select device functionality
- **Device Status Tracking**: Track working, failed, and untested devices
- **Multiplexer Control**: Control PySwitchbox and Electronic Mpx routing
- **Quick Scan**: Rapid device testing functionality
- **Sample Configuration**: Manage sample types and device mappings
- **Data Persistence**: Save and load device status and sample information
- **Generic_Grid (no-design mode)**: Run measurements on small arrays without a bespoke sample image or mapping file; uses a simple grid layout and Manual multiplexer

## Entry Points

### Primary Entry Point
Launched from `main.py`:

```python
import tkinter as tk
from gui.sample_gui import SampleGUI

root = tk.Tk()
app = SampleGUI(root)
root.mainloop()
```

### Programmatic Usage
```python
from gui.sample_gui import SampleGUI

# Create GUI instance
sample_gui = SampleGUI(master_window)
```

## Launching Measurement GUI

The Sample GUI launches the Measurement GUI when users select devices and click "Start Measurement":

```python
# Internal flow in SampleGUI
measurement_gui = MeasurementGUI(
    master=parent_window,
    sample_type="Cross_bar",
    section="A",
    device_list=["1", "2", "3"],
    sample_gui=self
)
```

## Dependencies

### Core Dependencies
- `tkinter`: GUI framework
- `matplotlib`: Image display and visualization
- `PIL/Pillow`: Image processing

### Project Dependencies
- `gui.measurement_gui`: For launching measurement interface
- `Equipment.managers.multiplexer`: Multiplexer control
- `Equipment.Multiplexers.*`: Multiplexer implementations
- `Json_Files/pin_mapping.json`: Device pin mappings
- `Json_Files/mapping.json`: Device layout mappings

## File Structure

```
sample_gui/
├── README.md           # This file
├── __init__.py         # Package exports (SampleGUI)
└── main.py             # SampleGUI class implementation
```

## Main Class

### `SampleGUI`

Main window class for device selection and sample management.

**Parameters**:
- `master`: Parent Tkinter window (typically `tk.Tk()` root)

**Key Methods**:
- `load_device_map()`: Load and display device mapping image
- `select_device()`: Handle device selection
- `start_measurement()`: Launch MeasurementGUI with selected devices
- `update_device_status()`: Update device status display
- `quick_scan()`: Run quick scan on selected devices

## Usage Flow

1. **Application Start**: User runs `main.py`
2. **Sample Selection**: User selects sample type and loads device map
3. **Device Selection**: User clicks on devices in the map or uses device list
4. **Configuration**: User configures measurement parameters
5. **Launch Measurement**: User clicks "Start Measurement" → launches `MeasurementGUI`
6. **Data Persistence**: Device status and sample info are saved automatically

## Generic_Grid (no-design / quick measurements)

When you have a sample with **no predefined design** (no device map image or `mapping.json` entry), you can still run quick measurements using the **Generic_Grid** sample type:

1. Set **Multiplexer** to **Manual** (no hardware routing; you move probes by hand).
2. Set **Type** to **Generic_Grid**.
3. A placeholder grid image and a small array of virtual devices (e.g. 12 in a 3×4 grid) are generated automatically. Use the device list and selection checkboxes to track which devices you are probing.
4. Open **Measurement GUI** as usual; tests run with manual probe movement. `change_relays()` in Manual mode only logs that you should move probes to the selected device.
5. **Quick Scan** is intended for multiplexed samples and requires a real multiplexer; it is not used in this no-design mode.

If you later create a proper device map or image for the sample, you can add it via `Json_Files/mapping.json` and a corresponding sample type so that the normal image-based workflow applies.

## Relationships

```
SampleGUI (this module)
    └─> MeasurementGUI (gui.measurement_gui)
            ├─> TSPTestingGUI
            ├─> CheckConnection
            ├─> MotorControlWindow
            └─> AdvancedTestsGUI
```

## Configuration Files

The Sample GUI uses configuration files from `Json_Files/`:

- **`pin_mapping.json`**: Maps device IDs to pin numbers for multiplexer control
- **`mapping.json`**: Defines device layout and positions in the device map image

## Examples

### Basic Usage
```python
import tkinter as tk
from gui.sample_gui import SampleGUI

# Create and run GUI
root = tk.Tk()
app = SampleGUI(root)
root.mainloop()
```

### Integration with Other Components
```python
from gui.sample_gui import SampleGUI
from gui.measurement_gui import MeasurementGUI

# Sample GUI launches measurement GUI internally
sample_gui = SampleGUI(master)
# User interaction triggers:
# measurement_gui = MeasurementGUI(...)
```

## Notes

- The Sample GUI is the main entry point for the entire measurement system
- It maintains references to launched GUIs for coordinated operation
- Device status is persisted across sessions
- Supports multiple sample types (Cross_bar, Device_Array_10, 15x15mm, Generic_Grid)

