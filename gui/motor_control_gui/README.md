# Motor Control GUI

Advanced motor control GUI with laser positioning for Thorlabs Kinesis XY motors. Features interactive canvas with real-time position tracking, visual feedback, and integrated function generator controls.

## Purpose

The Motor Control GUI provides comprehensive control over XY stage motors for laser positioning applications. It combines motor control, laser power management, and visual feedback in a modern, professional interface.

## Key Features

- **Interactive Canvas**: Click-to-move functionality with visual position marker
- **Real-Time Position Display**: Live updates of X/Y position
- **Jog Controls**: Arrow key and button-based movement with adjustable step size
- **Velocity & Acceleration Settings**: Configurable motor parameters
- **Position Presets**: Save and recall frequently used positions
- **Go-To-Position**: Direct coordinate input for precise positioning
- **Raster Scanning**: Automated scanning patterns for device mapping
- **Function Generator Integration**: Laser power control via FG interface
- **Keyboard Shortcuts**: Quick access to common operations
- **Camera Feed Placeholder**: Prepared for future camera integration

## Entry Points

### Standalone Mode
```python
import tkinter as tk
from gui.motor_control_gui import MotorControlWindow

root = tk.Tk()
window = MotorControlWindow()
window.run()
```

### Launched from Measurement GUI
```python
# In MeasurementGUI, user clicks "Motor Control" button
from gui.motor_control_gui import MotorControlWindow
window = MotorControlWindow()
# window.run() is not needed when launched from another GUI
```

## Dependencies

### Core Dependencies
- `tkinter`: GUI framework (Python standard library)
- `pylablib`: Thorlabs Kinesis motor control (optional)

### Project Dependencies
- `Equipment.Motor_Controll.Kenisis_motor_control`: Motor controller implementation
- `Equipment.Motor_Controll.config`: Motor configuration constants
- `Equipment.managers.function_generator`: Function generator manager (optional)

## File Structure

```
motor_control_gui/
├── README.md           # This file
├── __init__.py         # Package exports (MotorControlWindow)
└── main.py             # MotorControlWindow class (~1532 lines)
```

## Main Class

### `MotorControlWindow`

Main window class for motor control interface.

**Parameters**:
- `function_generator`: Optional FunctionGenerator instance
- `default_amplitude_volts`: Initial amplitude value for FG (default: 0.4)
- `canvas_size_pixels`: Canvas size in pixels (default: 500)
- `world_range_units`: Movement range in mm (default: 50.0)

**Key Methods**:
- `_on_connect()`: Connect to motors
- `_on_disconnect()`: Disconnect from motors
- `_on_jog()`: Move motor by step amount
- `_on_goto()`: Move to specified coordinates
- `_on_home()`: Home both motors to (0,0)
- `_on_canvas_click()`: Handle canvas click to move to position
- `_save_preset()`: Save current position as preset
- `_goto_preset()`: Move to saved preset position
- `_start_scan()`: Start raster scan pattern
- `_on_fg_connect()`: Connect to function generator
- `_on_apply_amplitude()`: Apply DC voltage to laser

## Usage Flow

1. **Launch**: GUI opens with disconnected motors
2. **Connection**: User clicks "Connect Motors" to initialize motors
3. **Homing**: User clicks "Home" to establish reference position (0,0)
4. **Positioning**: User can:
   - Click on canvas to move to position
   - Use jog controls (buttons or arrow keys)
   - Enter coordinates in "Go To Position"
   - Select a preset position
5. **Laser Control**: User connects FG and controls laser power
6. **Scanning**: User configures and runs raster scans

## Motor Control Features

### Jog Controls
- Arrow keys or on-screen buttons
- Adjustable step size (default: 1.0 mm)
- Directional movement (X+, X-, Y+, Y-)
- Home button returns to origin

### Position Presets
- Save current position with custom name
- List of saved presets
- Quick navigation to preset positions
- Delete unused presets

### Motor Settings
- Maximum velocity (mm/s)
- Acceleration (mm/s²)
- Settings applied to motors on connection

### Raster Scanning
- Configurable X/Y distances
- Adjustable raster count
- Horizontal or vertical direction
- Useful for device mapping

## Function Generator Integration

The GUI includes function generator controls for laser power management:

- **VISA Address**: Auto-detect or manual entry
- **Connection**: Connect/disconnect to FG
- **Output Control**: Enable/disable laser output
- **DC Voltage**: Set laser power level
- **Status Display**: Connection and output status

## Keyboard Shortcuts

- **Arrow Keys**: Jog motors (if connected)
- **H**: Home motors
- **G**: Go to entered position
- **S**: Save current position as preset
- **Ctrl+Q**: Quit application

## Examples

### Basic Usage
```python
import tkinter as tk
from gui.motor_control_gui import MotorControlWindow

root = tk.Tk()
window = MotorControlWindow()
window.run()
```

### With Function Generator
```python
from gui.motor_control_gui import MotorControlWindow

# Optional: provide function generator instance
window = MotorControlWindow(
    function_generator=my_fg,
    default_amplitude_volts=0.5,
    canvas_size_pixels=600,
    world_range_units=60.0
)
```

### Programmatic Control
```python
window = MotorControlWindow()

# Connect motors
window._on_connect()

# Move to position
window.var_goto_x.set("25.0")
window.var_goto_y.set("30.0")
window._on_goto()

# Save preset
window._save_preset()
```

## Configuration

Motor settings are stored in:
- **`Equipment/Motor_Controll/config.py`**: Default velocity, acceleration, VISA addresses
- **`motor_presets.json`**: Saved position presets (in current directory)

## Notes

- Motors must be connected before any movement operations
- Homing is recommended after connection to establish reference
- The canvas coordinate system has Y=0 at the bottom
- Function generator integration is optional (requires pyvisa)
- Motor driver (pylablib) is optional - GUI disables controls if unavailable
- Camera feed section is a placeholder for future implementation

## Troubleshooting

### Motors Won't Connect
- Check that pylablib is installed
- Verify motor controllers are powered and connected
- Check USB connections

### Position Not Updating
- Ensure motors are connected and homed
- Check motor controller initialization for errors
- Verify motor communication

### Canvas Click Not Working
- Ensure motors are connected
- Check that clicked position is within world range
- Verify motor movement is enabled

