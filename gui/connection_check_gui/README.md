# Connection Check GUI

Real-time connection verification tool that applies a small DC bias and monitors current in real-time. Useful for checking if probes are making good contact before running measurements.

## Purpose

The Connection Check GUI is a focused, single-purpose tool for verifying electrical connections. It applies a small DC bias and plots current in real-time, with audio alerts when current exceeds a threshold. This is particularly useful when lowering probes onto devices, as it provides immediate feedback when contact is made.

## Key Features

- **Real-Time Current Monitoring**: Live current vs time plotting
- **Audio Alerts**: Instrument beeps when current exceeds threshold
- **Adjustable Threshold**: Configurable current threshold (default: 1e-9 A)
- **Alert Modes**: Single beep or continuous beeping
- **Data Recording**: Stores all measurement data for analysis
- **Graph Saving**: Export plots to PNG/PDF/JPEG
- **Simple Interface**: Focused, easy-to-use design

## Entry Points

### Launched from Measurement GUI
```python
# In MeasurementGUI, user clicks "Check Connection" button
from gui.connection_check_gui import CheckConnection

check_gui = CheckConnection(
    master=self.master,
    keithley=self.keithley
)
```

### Direct Usage
```python
import tkinter as tk
from gui.connection_check_gui import CheckConnection
from unittest.mock import MagicMock

root = tk.Tk()
# Note: Requires a keithley instance with measurement methods
mock_keithley = MagicMock()  # Or use real instrument
check_gui = CheckConnection(root, mock_keithley)
root.mainloop()
```

## Dependencies

### Core Dependencies
- `tkinter`: GUI framework
- `matplotlib`: Real-time plotting
- `threading`: Background measurement loop

### Project Dependencies
- Requires a Keithley instrument instance with:
  - `set_voltage(voltage, icc)`
  - `enable_output(enabled)`
  - `measure_current()` → float or tuple
  - `beep(frequency, duration)`
  - `shutdown()`

## File Structure

```
connection_check_gui/
├── README.md           # This file
├── __init__.py         # Package exports (CheckConnection)
└── main.py             # CheckConnection class (~413 lines)
```

## Main Class

### `CheckConnection`

Popup window class for connection verification.

**Parameters**:
- `master`: Parent Tkinter window (tk.Misc)
- `keithley`: Keithley instrument instance (Any)

**Key Attributes**:
- `current_threshold_a`: Current threshold for alerts (default: 1e-9 A)
- `make_sound_var`: Enable/disable sound alerts
- `continuous_sound_var`: Single vs continuous beeping
- `time_data`: List of time values
- `current_data`: List of current values

**Key Methods**:
- `create_ui()`: Build the user interface
- `start_measurement_loop()`: Start background measurement thread
- `measurement_loop()`: Worker thread that measures current
- `on_spike_detected()`: Handle current threshold crossing
- `update_plot()`: Update real-time plot
- `save_graph()`: Export plot to file
- `close_window()`: Clean up and close

## Usage Flow

1. **Launch**: GUI opens from MeasurementGUI or standalone
2. **Setup**: GUI automatically applies 0.2V bias and enables output
3. **Monitoring**: Background thread continuously measures current
4. **Alert**: When current exceeds threshold, instrument beeps
5. **Visual Feedback**: Plot updates in real-time with threshold line
6. **Reset**: User can reset alert to detect another connection
7. **Save**: User can save the plot for documentation
8. **Close**: Window closes and instrument output is disabled

## Alert Configuration

### Single Beep Mode (Default)
- Beeps once when threshold is first crossed
- Alert flag prevents repeated beeping
- User must reset to detect next connection

### Continuous Beep Mode
- Beeps on every reading that exceeds threshold
- Useful for noisy signals or multiple contacts
- Alert flag is ignored in this mode

### Threshold Adjustment
- Default: 1e-9 A (1 nA)
- User can adjust threshold value
- Threshold change resets alert flag
- Update button applies new threshold

## Examples

### Basic Usage from Measurement GUI
```python
# In MeasurementGUI class
def check_connection(self):
    from gui.connection_check_gui import CheckConnection
    
    if not self.keithley:
        messagebox.showerror("Error", "Please connect to instrument first")
        return
    
    check_gui = CheckConnection(
        master=self.master,
        keithley=self.keithley
    )
```

### Custom Threshold
```python
check_gui = CheckConnection(master, keithley)
# User adjusts threshold in GUI
# Or programmatically:
check_gui.current_threshold_a = 1e-8  # 10 nA
check_gui.update_threshold()
```

### Accessing Measurement Data
```python
# After measurement
time_data = check_gui.time_data
current_data = check_gui.current_data
# Process data as needed
```

## Real-Time Plot Features

- **Current vs Time**: Log-scale Y-axis for wide dynamic range
- **Threshold Line**: Red dashed line showing alert threshold
- **Connection Marker**: Green marker when above threshold
- **Current Display**: Text overlay showing current value
- **Auto-Scaling**: X-axis scales with measurement duration

## Configuration

### Default Settings
- Bias Voltage: 0.2 V
- Compliance Current: 0.1 A
- Measurement Interval: 0.2 s
- Threshold: 1e-9 A (1 nA)
- Sound Enabled: Yes (by default)

### Adjustable Settings
- Sound alert on/off
- Continuous vs single beep mode
- Current threshold value
- Plot save location and format

## Relationships

```
CheckConnection (this module)
    └─> Launched from: MeasurementGUI (gui.measurement_gui)
    └─> Uses: Keithley instrument from MeasurementGUI
```

## Notes

- **Instrument Requirement**: Requires a working Keithley instrument instance
- **Thread Safety**: Measurement loop runs in background thread
- **Current Format**: Handles both float (2400/2450) and tuple (4200A) returns
- **Cleanup**: Automatically disables output and cleans up on close
- **Standalone Testing**: Can be tested with mock instrument for development

## Troubleshooting

### No Current Reading
- Verify instrument is connected
- Check that output is enabled
- Verify bias voltage is applied
- Check probe contact

### Alert Not Triggering
- Verify threshold is appropriate for expected current
- Check that sound alerts are enabled
- Reset alert if in single-beep mode
- Verify instrument beep functionality

### Plot Not Updating
- Check that measurement thread is running
- Verify instrument connection is stable
- Check for exceptions in console output

## Use Cases

1. **Probe Lowering**: Monitor current while lowering probes onto device
2. **Connection Verification**: Verify probe contact before measurement
3. **Contact Quality**: Assess connection quality via current magnitude
4. **Short Detection**: Identify shorts between probes
5. **Open Detection**: Confirm when probes are not making contact

