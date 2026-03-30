# Connection Check Standalone Application

A standalone GUI application for checking electrical connections using a Keithley 2400 Source Measure Unit (SMU).

## Features

- Real-time current monitoring with live plot
- Configurable threshold alerts (default: 1e-9 A)
- Audio alerts when connection is detected
- Save plots to PNG, PDF, or JPEG
- Simple GPIB address input on startup

## Installation

### Option 1: Run as Python Script

1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   pip install -r requirements_standalone.txt
   ```
3. Run the application:
   ```bash
   python Connection_Check_Standalone.py
   ```

### Option 2: Create Executable

1. Install all dependencies (see Option 1)
2. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
3. Create executable:
   ```bash
   pyinstaller --onefile --windowed Connection_Check_Standalone.py
   ```
4. The executable will be in the `dist` folder

### Option 3: Create Executable with Icon (Optional)

1. Prepare an icon file (`icon.ico`)
2. Run:
   ```bash
   pyinstaller --onefile --windowed --icon=icon.ico Connection_Check_Standalone.py
   ```

## Usage

1. **Start the application** - The GPIB address dialog will appear
2. **Enter GPIB address** - Default is `GPIB0::24::INSTR`
   - Common formats:
     - GPIB: `GPIB0::24::INSTR`
     - USB: `USB0::0x05E6::0x2450::MY********::INSTR`
     - TCP/IP: `TCPIP0::192.168.1.100::inst0::INSTR`
3. **Connection check** - Once connected, the GUI will:
   - Apply 0.2V bias
   - Continuously measure current
   - Plot current vs time on a log scale
   - Beep when current exceeds threshold
4. **Adjust settings**:
   - Enable/disable sound alerts
   - Set continuous beep mode
   - Adjust threshold value
   - Reset alert after detection
5. **Save graph** - Click "Save Graph" to export the plot

## Hardware Requirements

- Keithley 2400 SMU
- GPIB, USB, or Ethernet connection to PC
- Appropriate drivers installed (NI-VISA or PyVISA-py)

## Troubleshooting

### Connection Issues

- **"No device found"**: Check GPIB address and ensure instrument is powered on
- **"Timeout error"**: Increase timeout value or check cable connections
- **"PyVISA error"**: Ensure PyVISA-py or NI-VISA drivers are installed

### GUI Issues

- **Window doesn't appear**: Check if tkinter is installed
- **Plot not updating**: Check console for error messages
- **Beep not working**: Verify instrument connection is active

### Creating Executable

- **Large file size**: This is normal - PyInstaller bundles Python and all dependencies
- **Antivirus warnings**: Some antivirus software flags PyInstaller executables - this is usually a false positive
- **Missing DLL errors**: Ensure all dependencies are installed before creating executable

## Notes

- The application applies a small bias (0.2V) continuously while running
- Current threshold is set to 1e-9 A by default but can be adjusted
- The plot uses a logarithmic scale for better visibility
- All measurement data is stored in memory and can be saved as a graph

## File Structure

```
standalone_folder/
├── Connection_Check_Standalone.py    # Main application file
├── requirements_standalone.txt      # Python dependencies
└── README_Standalone.md             # This file
```

