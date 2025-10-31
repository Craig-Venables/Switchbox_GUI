# TSP Testing GUI Standalone - Setup Complete ✓

This standalone version of the TSP Testing GUI has been successfully created and is ready to use!

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Test imports (optional):**
   ```bash
   python test_imports.py
   ```

3. **Run the GUI:**
   ```bash
   python main.py
   ```

## What's Included

### Core Files
- `main.py` - Entry point for running the GUI
- `TSP_Testing_GUI.py` - Main GUI implementation (unchanged, works standalone)

### Equipment Controllers
- `Equipment/SMU_AND_PMU/Keithley2450_TSP.py` - TSP instrument controller
- `Equipment/SMU_AND_PMU/keithley2450_tsp_scripts.py` - Test script implementations
  - ✅ Fixed: Changed relative import to absolute import for standalone use

### Data Utilities
- `Measurments/data_formats.py` - Data formatting and file saving utilities

### Configuration
- `Json_Files/tsp_gui_config.json` - Default terminal settings
- `Json_Files/tsp_gui_save_config.json` - Save location preferences  
- `Json_Files/tsp_test_presets.json` - Test parameter presets

### Package Structure
- All `__init__.py` files created to make packages importable
- Directory structure matches original for compatibility

## Changes Made

1. ✅ Created standalone folder structure
2. ✅ Copied all necessary files
3. ✅ Fixed relative import in `keithley2450_tsp_scripts.py`:
   - Changed: `from .Keithley2450_TSP import Keithley2450_TSP`
   - To: `from Equipment.SMU_AND_PMU.Keithley2450_TSP import Keithley2450_TSP`
4. ✅ Created `__init__.py` files for all packages
5. ✅ Created `main.py` entry point
6. ✅ Created minimal `requirements.txt` with only essential dependencies
7. ✅ Created comprehensive `README.md` with usage instructions

## Testing

Run the test script to verify everything works:
```bash
python test_imports.py
```

If all imports succeed, you're ready to use the GUI!

## Important Notes

- The instrument **must be in TSP mode** (not SCPI mode)
- All imports use absolute paths (e.g., `Equipment.SMU_AND_PMU.*`)
- Configuration files use relative paths and will work from the standalone folder
- The GUI is fully functional and independent of the main project

## Next Steps

1. Ensure your Keithley 2450 is connected and in TSP mode
2. Run `python main.py` to launch the GUI
3. Enter your instrument address and connect
4. Start running tests!

---

**Created:** October 31, 2025  
**Status:** Ready for use ✓

