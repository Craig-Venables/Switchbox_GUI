# TSP Data Analysis Tool

A PyQt6-based application for analyzing and plotting Keithley 2450 TSP (Test Script Processor) pulse test data.

## Features

### File Browser & Data Loading
- Browse folders containing TSP data files
- Recent folders list for quick access
- Filter files by test type
- Real-time file preview with metadata and thumbnail plots
- Multi-select files for comparison
- Support for multiple file formats (TSP, PMU Simple, Endurance, IV Sweep)

### Interactive Plotting
- Interactive matplotlib canvas with zoom/pan
- Plot multiple datasets for comparison
- Dataset visibility toggle (double-click)
- Real-time plot customization:
  - Line width (0.5-5.0)
  - Marker size (0-12)
  - Grid on/off
  - Legend on/off
  - Log scale toggle
- Dark theme optimized for long viewing
- Resizable splitter for better control panel visibility

### Data Processing
- **Crop**: Set start/end points to focus on specific range
- **Normalize**: Scale to 0-1 range for comparison
- **Y-axis offset**: Add offset to separate curves
- **Manual axis ranges**: Set min/max with auto-scale toggle

### Background & Export
- Custom background color picker
- Transparent background export option
- Auto text/grid color adjustment
- **Export formats**:
  - PNG (standard & transparent, 300 DPI)
  - PDF (standard & transparent, 150 DPI)
  - TXT (column format with headers, units, and metadata comments)
  - CSV (statistics export)

### Annotations
- Add text boxes, arrows, circles, rectangles
- Click-to-position on plot
- Customizable colors and styles
- Help dialog with step-by-step instructions

### Statistics Panel
- **Basic Statistics**: Mean, median, std dev, min, max, range
- **Change Analysis**: Initial/final values, total change, percent change
- **Relaxation Time**: Exponential fitting with R² goodness-of-fit
  - Automatic detection for relaxation tests
  - Handles both growth and decay processes
  - See [RELAXATION_TIME_EXPLANATION.md](RELAXATION_TIME_EXPLANATION.md) for details
- **HRS/LRS Detection**: For switching/endurance tests
  - High/Low Resistance State means
  - Switching window calculation
  - On/Off ratio
- **Display Options**:
  - Toggleable stats box on graph
  - Checkboxes to select which stats to show
  - 8 position options (upper right, lower left, etc.)
- **Export**: Export all statistics to CSV

## Installation

1. **Install Python 3.8 or higher**

2. **Install dependencies:**
   ```bash
   cd Data_Analysis_Pulse_2450
   pip install -r requirements.txt
   ```

## Quick Start

1. **Launch the application:**
   ```bash
   python main.py
   ```

2. **Browse to your data folder:**
   - Click "Browse..." or select a recent folder
   - Files are automatically loaded and parsed

3. **Select files:**
   - Click files to select them (Ctrl+Click for multiple)
   - Use the filter dropdown to show specific test types
   - View file preview in the right panel

4. **Plot data:**
   - Click "📊 Plot Selected Files"
   - Use toolbar to zoom/pan
   - Double-click datasets to toggle visibility

5. **Customize:**
   - Adjust line width, marker size, grid, legend
   - Change background color or use transparent export
   - Crop data, normalize, or add Y-offset
   - Set manual axis ranges if needed

6. **Add annotations:**
   - Choose annotation type
   - Click on plot to position
   - Customize color and style

7. **Calculate statistics:**
   - Click "📊 Calculate Statistics"
   - Check "Show Stats on Graph" to display
   - Select which stats to show with checkboxes
   - Export stats to CSV

8. **Export:**
   - PNG/PDF: Plot images (with or without background)
   - TXT: Processed data in column format
   - CSV: Calculated statistics

## File Structure

```
Data_Analysis_Pulse_2450/
├── main.py                          # Entry point
├── requirements.txt                 # Dependencies
├── README.md                        # This file
├── TSP_DATA_FORMAT_SPECIFICATION.md # Data format specification
├── RELAXATION_TIME_EXPLANATION.md   # Detailed tau explanation
├── STATISTICS_USAGE_GUIDE.md        # Statistics usage guide
├── TODO_REMAINING_FEATURES.md      # Future features roadmap
├── gui/
│   ├── main_window.py              # Main application window
│   ├── file_browser_tab.py         # File browsing tab
│   ├── plotting_tab.py             # Plotting and analysis tab
│   ├── label_editor_dialog.py     # Label editor dialog
│   └── plot_annotations.py         # Annotation tools
├── core/
│   ├── data_parser.py              # TSP file parser
│   ├── test_type_registry.py       # Test type management
│   ├── plot_generator.py           # Plot generation
│   └── statistics.py              # Statistical calculations
├── utils/
│   └── settings.py                 # Application settings
└── resources/
    └── test_types.json             # Test type registry
```

## Configuration Files

### test_types.json

Located in `resources/test_types.json`, this file defines known test types and their characteristics. It's automatically created on first run with defaults.

You can edit this file to add new test types or modify existing ones.

### settings.json

Application settings are stored in `settings.json` including:
- Window size and position
- Recent folders
- Plot preferences
- Theme settings

## Supported Test Types

- Pulse-Read-Repeat
- Multi-Pulse-Then-Read
- Width Sweep / Width Sweep (Full)
- Potentiation-Depression Cycle
- Potentiation Only / Depression Only
- Endurance Test
- Pulse-Multi-Read
- Multi-Read Only
- Relaxation After Multi-Pulse
- Current Range Finder
- IV Sweep (Hysteresis)
- PMU Pulse-Read

## Data Format

See [TSP_DATA_FORMAT_SPECIFICATION.md](TSP_DATA_FORMAT_SPECIFICATION.md) for detailed information about the TSP data file format.

The tool supports multiple formats:
- **TSP Format**: Standard format with metadata headers
- **PMU Simple**: Time, Voltage, Current, Resistance columns
- **Endurance**: Iteration-based endurance test data
- **IV Sweep**: Voltage-Current hysteresis measurements

## Documentation

### For Users
- **[TSP_DATA_FORMAT_SPECIFICATION.md](TSP_DATA_FORMAT_SPECIFICATION.md)**: Detailed data format specification
- **[RELAXATION_TIME_EXPLANATION.md](RELAXATION_TIME_EXPLANATION.md)**: How tau is calculated and what it means
- **[STATISTICS_USAGE_GUIDE.md](STATISTICS_USAGE_GUIDE.md)**: Comprehensive statistics feature guide

### For Developers
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)**: Architecture, current state, and how to extend the project
- **[TODO_REMAINING_FEATURES.md](TODO_REMAINING_FEATURES.md)**: Future development roadmap

## Known Issues

- Annotation system may have positioning issues (under investigation)

## Future Enhancements

- Origin graph format export
- Multiple plot layouts (2x1, 2x2, etc.)
- Per-dataset color customization
- Plot templates and presets
- Multi-axis plotting (R + I on same graph)
- Batch processing for multiple files
- Initial read reference normalization

---

**Version:** 1.1  
**Last Updated:** 2025-11-01  
**Status:** Production Ready ✅
