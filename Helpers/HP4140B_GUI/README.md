# HP4140B Simple Control GUI

A simple, user-friendly interface for controlling the HP4140B pA Meter/DC Voltage Source.

## Features

- **Automatic connection** on startup
- **Voltage sweep control** with configurable parameters
- **Full/Half sweep** options (direction based on step sign)
- **Real-time plotting** (linear and log I vs V)
- **Automatic data saving** with incrementing sample numbers
- **Remembers last save location**

## Requirements

Install the required packages:

```bash
pip install pyvisa numpy matplotlib tkinter
```

**Note:** `tkinter` is usually included with Python on Windows and Linux. On macOS, you may need to install it separately.

## Usage

### Running the GUI (Standalone)

1. Navigate to this folder:
   ```bash
   cd Helpers/HP4140B_GUI
   ```

2. Run the GUI:
   ```bash
   python hp4140b_gui.py
   ```
   
   OR use the launcher script:
   ```bash
   python run_gui.py
   ```

### Running from Project Root

You can also run it from the project root:
```bash
python Helpers/HP4140B_GUI/hp4140b_gui.py
```

### Connection

- The GUI will automatically attempt to connect on startup
- Default GPIB address: `GPIB0::17::INSTR`
- You can change the address in the GUI and click "Connect"

### Measurement Parameters

- **Voltage (V)**: Target voltage for the sweep (default: 0.5V)
- **Step (V)**: Voltage step size (default: 0.001V)
  - Positive step = upward sweep (0 → +voltage)
  - Negative step = downward sweep (0 → -voltage)
- **Current Limit (A)**: Current compliance limit (default: 1e-3A)
- **dV/dt (V/s)**: Voltage ramp rate (default: 0.1 V/s)
- **Sweep Type**:
  - **Full**: Goes from 0 → voltage → 0 (triangle sweep)
  - **Half**: Goes from 0 → voltage only (one direction)

### Data Saving

- Default save location: `Documents/data`
- You can browse and change the save location
- Files are saved as: `sample_XXXX_timestamp.txt`
- Sample numbers auto-increment
- Last save location is remembered for next session

### Files

- `hp4140b_gui.py`: Main GUI application
- `hp4140b_controller.py`: HP4140B controller module
- `hp4140b_config.json`: Configuration file (created automatically)
- `README.md`: This file

## Troubleshooting

### Connection Issues

If the instrument doesn't connect:
1. Check GPIB address is correct
2. Verify instrument is powered on
3. Check GPIB cable is connected
4. Ensure GPIB interface is properly configured (NI-VISA drivers installed)

### Measurement Issues

- If measurements fail, check current limit is appropriate
- Verify voltage range is within instrument capabilities
- Check step size is reasonable (not too small or too large)

## Standalone Operation

This GUI is designed to work standalone within this folder. All necessary files are included:
- `hp4140b_controller.py`: Controller module
- `hp4140b_gui.py`: Main GUI application

The GUI will create a config file (`hp4140b_config.json`) in the same folder to store settings.

## Notes

- The HP4140B uses proprietary GPIB commands (not SCPI)
- Commands require newline termination
- Typical GPIB address is 17 (configurable via DIP switches)
- The instrument ramps to zero and disables output on shutdown

