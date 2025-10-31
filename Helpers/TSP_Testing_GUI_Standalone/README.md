# TSP Testing GUI - Standalone Version

This is a standalone version of the TSP Testing GUI for Keithley 2450 SourceMeter devices. It has been extracted from the main Switchbox_GUI project and includes all necessary files to run independently.You need to put the 2450 in TSP mode before this will work

## Purpose

This GUI provides fast, buffer-based pulse testing with real-time visualization for the Keithley 2450 SourceMeter using TSP (Test Script Processor) commands. It supports a wide variety of test patterns including:

- Pulse-Read-Repeat patterns
- Multi-pulse sequences
- Width sweeps
- Potentiation-Depression cycles
- Endurance testing
- Relaxation characterization
- And more...

## Requirements

- **Python 3.7 or higher**
- **Keithley 2450 SourceMeter** in TSP mode
- **PyVISA** and **PyVISA-py** for instrument communication
- Required Python packages (see `requirements.txt`)

## Installation

1. **Clone or download this repository**

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Ensure your Keithley 2450 is in TSP mode:**
   - On the instrument: MENU → System → Settings → Command Set → TSP
   - The GUI will not work if the instrument is in SCPI mode

## Usage

1. **Connect your Keithley 2450** via USB, GPIB, or Ethernet

2. **Run the GUI:**
   ```bash
   python main.py
   ```

3. **In the GUI:**
   - Enter or detect your instrument address (e.g., `USB0::0x05E6::0x2450::04496615::INSTR`)
   - Click "Connect" to establish connection
   - Select a test pattern from the dropdown
   - Configure test parameters
   - Click "Run Test" to execute

## Configuration Files

The GUI uses JSON configuration files stored in the `Json_Files/` directory:

- `tsp_gui_config.json` - Default terminal settings (front/rear)
- `tsp_gui_save_config.json` - Save location preferences
- `tsp_test_presets.json` - Test parameter presets

These files are created automatically with defaults if they don't exist.

## File Structure

```
TSP_Testing_GUI_Standalone/
├── main.py                          # Entry point - run this to start the GUI
├── TSP_Testing_GUI.py               # Main GUI implementation
├── Equipment/                       # Instrument controllers
│   ├── __init__.py
│   └── SMU_AND_PMU/
│       ├── __init__.py
│       ├── Keithley2450_TSP.py     # TSP instrument controller
│       └── keithley2450_tsp_scripts.py  # Test script implementations
├── Measurments/                     # Data formatting utilities
│   ├── __init__.py
│   └── data_formats.py              # Data formatting and file saving
├── Json_Files/                      # Configuration files
│   ├── tsp_gui_config.json
│   ├── tsp_gui_save_config.json
│   └── tsp_test_presets.json
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

## Features

- **Fast TSP-based pulse generation** - Pulses as short as 50µs
- **Real-time visualization** - Live plotting during test execution
- **Comprehensive test patterns** - 15+ different test types
- **Data saving** - Automatic saving with metadata headers
- **Test presets** - Save and load test parameter configurations
- **Error diagnostics** - Built-in error checking and reporting

## Troubleshooting

**"Could not connect to instrument"**
- Ensure instrument is powered on
- Check VISA resource address is correct
- Verify instrument is in **TSP mode** (not SCPI mode)
- Check USB/GPIB/Ethernet cable connection

**"Script already exists" errors**
- The GUI automatically clears scripts, but if you see this, try disconnecting and reconnecting

**Import errors**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Verify you're running from the correct directory

## Notes

- All test data is saved automatically with comprehensive metadata
- The GUI supports both structured (sample/device) and simple save locations
- Test presets can be saved and loaded for reproducible experiments
- The instrument must remain in TSP mode throughout use

## License

This standalone version maintains the same license and usage terms as the original project.

## Version

- **Version:** 1.0 (Standalone)
- **Date:** October 31, 2025
- **Extracted from:** Switchbox_GUI main project

