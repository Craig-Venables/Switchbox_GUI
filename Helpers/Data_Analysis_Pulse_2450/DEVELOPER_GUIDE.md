# Developer Guide - TSP Data Analysis Tool

**Purpose:** This guide helps new developers or AI assistants understand the project architecture, current state, and how to extend functionality.

**Last Updated:** 2025-11-01  
**Current Version:** 1.1

---

## Project Overview

This is a PyQt6-based desktop application for analyzing and visualizing TSP (Test Script Processor) pulse test data from Keithley 2450 instruments. It supports file browsing, interactive plotting, statistical analysis, and data export.

### Key Technologies
- **GUI Framework:** PyQt6
- **Plotting:** Matplotlib
- **Data Processing:** NumPy, SciPy (for curve fitting)
- **File I/O:** Standard library (text parsing)

---

## Architecture

### Directory Structure

```
Data_Analysis_Pulse_2450/
├── main.py                    # Application entry point
├── core/                      # Core business logic
│   ├── data_parser.py        # File format parsing
│   ├── plot_generator.py    # Plot creation
│   ├── statistics.py        # Statistical calculations
│   └── test_type_registry.py # Test type management
├── gui/                      # User interface
│   ├── main_window.py       # Main window and tab container
│   ├── file_browser_tab.py  # File selection UI
│   ├── plotting_tab.py      # Plotting and controls UI
│   ├── label_editor_dialog.py # Label editing dialog
│   └── plot_annotations.py  # Annotation system
└── utils/                    # Utilities
    └── settings.py          # Settings persistence
```

### Data Flow

1. **File Selection** (`file_browser_tab.py`)
   - User browses folder → Files loaded
   - Files parsed by `data_parser.py` → Creates `TSPData` objects
   - Files displayed in list with previews
   - Selected files passed to plotting tab

2. **Plotting** (`plotting_tab.py`)
   - Receives list of `TSPData` objects
   - Creates plot using `plot_generator.py`
   - Applies user settings (crop, normalize, offset)
   - Updates plot in real-time

3. **Statistics** (`plotting_tab.py` + `statistics.py`)
   - User clicks "Calculate Statistics"
   - Creates `DataStatistics` objects for each dataset
   - Calculates stats (basic, relaxation time, HRS/LRS)
   - Displays in stats box on graph

---

## Core Classes

### TSPData (`core/data_parser.py`)

**Purpose:** Container for parsed measurement data

**Key Attributes:**
```python
- filepath: Path          # Original file location
- filename: str           # Filename
- test_name: str          # Test type name
- sample: str             # Sample identifier
- device: str             # Device identifier
- parameters: Dict        # Test parameters (pulse width, voltage, etc.)
- timestamps: np.ndarray  # Time data
- voltages: np.ndarray   # Voltage data
- currents: np.ndarray   # Current data
- resistances: np.ndarray # Resistance data
- additional_data: Dict   # Extra columns (varies by test type)
```

**Key Methods:**
- `get_display_name()` → Returns formatted name for UI
- `get_key_parameters()` → Returns important params as string
- `get_column(name)` → Gets data column by name

### DataStatistics (`core/statistics.py`)

**Purpose:** Calculate statistics for measurement data

**Key Methods:**
- `basic_stats()` → Mean, median, std dev, min, max, range
- `relaxation_time()` → Exponential fit, returns tau (time constant)
- `hrs_lrs_stats()` → HRS/LRS detection for switching tests
- `initial_read_stats()` → Change relative to initial value
- `all_stats()` → Combines all relevant stats

**Relaxation Time Calculation:**
- Fits: `y(t) = y∞ + (y₀ - y∞) × exp(-t/τ)`
- Handles both growth and decay
- Returns tau (units match X-axis), R², and fit quality

### PlotGenerator (`core/plot_generator.py`)

**Purpose:** Generate matplotlib plots for different test types

**Key Methods:**
- `plot_single(data, fig, ax, color, label)` → Plot one dataset
- `plot_multiple(datasets, figsize)` → Plot multiple datasets
- Various `_plot_*` methods for specific test types

**Test Type → Plot Type Mapping:**
- Handled by `test_type_registry.py`
- Maps test names to plot functions
- Auto-detects appropriate plot style

---

## Adding New Test Types

### Step 1: Update Test Type Registry

**File:** `resources/test_types.json`

Add new entry:
```json
{
  "Your Test Name": {
    "description": "Brief description",
    "plot_type": "time_series|width_vs_resistance|pot_dep_cycle|endurance|relaxation_reads|relaxation_all|range_finder|iv_sweep",
    "expected_columns": ["Measurement_Number", "Timestamp(s)", "Voltage(V)", "Current(A)", "Resistance(Ohm)"],
    "key_parameters": ["param1", "param2"]
  }
}
```

**Plot Types Available:**
- `time_series` - Standard time vs resistance/current
- `width_vs_resistance` - Pulse width on X-axis
- `pot_dep_cycle` - Potentiation-depression cycle
- `endurance` - Endurance test visualization
- `relaxation_reads` - Relaxation with read points
- `relaxation_all` - Full relaxation curve
- `range_finder` - Current range finder
- `iv_sweep` - IV hysteresis (Voltage vs Current)

### Step 2: Add Parser Support (if new file format)

**File:** `core/data_parser.py`

1. Add format detection in `detect_file_format()`:
```python
def detect_file_format(lines: List[str], filename: str) -> str:
    # ... existing detection ...
    if 'your_format_indicator' in filename.lower():
        return 'your_format'
```

2. Create parser function:
```python
def parse_your_format(data: TSPData, lines: List[str]) -> Optional[TSPData]:
    """Parse your custom format"""
    try:
        # Extract metadata
        # Parse data columns
        # Populate TSPData object
        return data
    except Exception as e:
        print(f"Error parsing your format: {e}")
        return None
```

3. Add to routing in `parse_tsp_file()`:
```python
format_type = detect_file_format(lines, filepath.name)
if format_type == 'your_format':
    return parse_your_format(data, lines)
```

### Step 3: Add Plot Function (if needed)

**File:** `core/plot_generator.py`

If standard plot types don't work, add custom plot method:
```python
def _plot_your_test(self, ax: Axes, data: TSPData, color: str, label: str):
    """Plot your custom test type"""
    x_data = data.timestamps  # or appropriate X-axis
    y_data = data.resistances  # or appropriate Y-axis
    
    ax.plot(x_data, y_data, color=color, label=label, ...)
    ax.set_xlabel('Your X Label')
    ax.set_ylabel('Your Y Label')
```

Update `plot_single()` to route to your function:
```python
elif plot_type == 'your_plot_type':
    self._plot_your_test(ax, data, color, label)
```

---

## Adding New Statistics

**File:** `core/statistics.py`

### Step 1: Add Calculation Method

```python
def your_new_stat(self) -> Dict[str, float]:
    """Calculate your custom statistic"""
    # Your calculation logic
    return {
        'Stat Name': calculated_value,
        'Another Stat': another_value
    }
```

### Step 2: Integrate into all_stats()

```python
def all_stats(self, include_relaxation: bool = True, 
              include_hrs_lrs: bool = False,
              include_your_stat: bool = False) -> Dict[str, float]:
    stats = {}
    # ... existing stats ...
    
    if include_your_stat:
        stats.update(self.your_new_stat())
    
    return stats
```

### Step 3: Add to UI

**File:** `gui/plotting_tab.py`

1. Add checkbox in statistics section:
```python
stat_options = [
    # ... existing options ...
    "Your New Stat",
]

for stat_name in stat_options:
    cb = QCheckBox(stat_name)
    # ...
```

2. Update calculation call:
```python
stats = stats_calc.all_stats(
    include_relaxation=include_relaxation,
    include_hrs_lrs=include_hrs_lrs,
    include_your_stat=True  # Add this
)
```

---

## Adding New Export Formats

**File:** `gui/plotting_tab.py`

### Export Plot Image

Method: `export_plot(format: str, transparent: bool)`

Already supports PNG/PDF. To add new format:
```python
if format == 'svg':
    self.figure.savefig(file_path, dpi=dpi, format='svg', ...)
```

### Export Data

Method: `export_data()`

Currently exports TXT (tab-delimited). To add CSV export:
```python
def export_data_csv(self):
    # Use pandas or csv module
    # Write headers, units, comments rows
    # Write data rows
```

---

## Current Implementation Status

### ✅ Completed Features

**File Parsing:**
- TSP format (full metadata)
- PMU Simple format (Time, V, I, R)
- Endurance format (Iteration-based)
- IV Sweep format (Hysteresis)

**Plotting:**
- All test types supported
- Interactive zoom/pan
- Multiple datasets
- Customizable appearance
- Dark theme

**Data Processing:**
- Crop (start/end points)
- Normalize (0-1 range)
- Y-offset
- Manual axis ranges

**Statistics:**
- Basic stats (mean, median, std dev, etc.)
- Relaxation time fitting (exponential)
- HRS/LRS detection
- Stats box overlay on graph

**Export:**
- PNG (with/without background)
- PDF (with/without background)
- TXT (column format with metadata)
- CSV (statistics only)

**UI Features:**
- File browser with previews
- Label editor
- Annotation tools
- Statistics panel
- Resizable layout

### 🚧 Known Issues

- Annotation system positioning may need refinement
- Some edge cases in file parsing for non-standard formats

### 📋 Planned Features (See TODO_REMAINING_FEATURES.md)

- Origin export format
- Multi-panel layouts
- Batch processing
- Multi-axis plotting (R + I together)
- Initial read reference normalization

---

## Code Patterns & Conventions

### Error Handling

Most parsing functions return `None` on failure:
```python
try:
    # Parse logic
    return parsed_data
except Exception as e:
    print(f"Error: {e}")
    return None
```

Callers check for `None`:
```python
data = parse_tsp_file(filepath)
if data is None:
    # Handle error
    continue
```

### Data Processing

Processing preserves original data by creating copies:
```python
def process_data(self, data: TSPData, ...) -> TSPData:
    processed = copy.deepcopy(data)  # Don't modify original
    # Apply transformations
    return processed
```

### Settings Management

Uses singleton pattern:
```python
from utils.settings import get_settings

settings = get_settings()
settings.set('key', value)
settings.save()
```

### UI Updates

Plot updates are triggered by signals:
```python
self.some_control.valueChanged.connect(self.update_plot)
```

Use `QApplication.processEvents()` if needed for long operations.

---

## Testing

**Test File:** `test_app.py`

Run to test core components:
```bash
python test_app.py
```

Tests:
- File parsing
- Data structure
- Statistics calculation
- Plot generation

**Manual Testing Checklist:**
1. Load various file formats
2. Plot multiple datasets
3. Apply processing (crop, normalize, offset)
4. Calculate statistics
5. Export plots and data
6. Test annotations

---

## Debugging Tips

### Common Issues

**1. File Not Parsing:**
- Check file format detection in `detect_file_format()`
- Verify parser is called in routing
- Add print statements to see where it fails

**2. Statistics Not Calculating:**
- Verify test type contains "relaxation" for relaxation time
- Check data has enough points (minimum 4 for tau)
- Look at R² value (low = poor fit)

**3. Plot Not Showing:**
- Check dataset visibility (double-click to toggle)
- Verify data arrays have values (not empty)
- Check log scale settings

**4. Export Failing:**
- Check file permissions
- Verify path exists
- Check disk space

### Debug Mode

Add debug prints:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or use print statements:
```python
print(f"DEBUG: Processing {len(data)} points")
```

---

## Extending for New Use Cases

### Example: Adding Peak Detection

1. Add method to `DataStatistics`:
```python
def peak_detection(self, prominence=0.1):
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(self.y_data, prominence=...)
    return {'Peaks': peaks, ...}
```

2. Add to UI checkboxes
3. Display in stats box
4. Export to CSV

### Example: Adding Data Smoothing

1. Add smoothing method to `PlottingTab`:
```python
def smooth_data(self, data: TSPData, window=5):
    from scipy.signal import savgol_filter
    smoothed = savgol_filter(data.resistances, window, 3)
    # Create new TSPData with smoothed values
```

2. Add UI toggle/control
3. Apply in `process_data()` or before plotting

---

## File Format Details

See `TSP_DATA_FORMAT_SPECIFICATION.md` for:
- TSP file structure
- Metadata fields
- Column definitions
- Supported formats

---

## Key Dependencies

```txt
PyQt6>=6.4.0        # GUI framework
numpy>=1.21.0       # Numerical computing
scipy>=1.7.0        # Scientific computing (curve fitting)
matplotlib>=3.5.0   # Plotting
```

---

## Quick Reference

**Main Entry Point:**
- `main.py` → Creates QApplication, shows MainWindow

**Core Parsing:**
- `core/data_parser.py` → `parse_tsp_file()` returns `TSPData`

**Plotting:**
- `core/plot_generator.py` → `PlotGenerator.plot_single()` or `plot_multiple()`

**Statistics:**
- `core/statistics.py` → `DataStatistics` class methods

**UI:**
- `gui/main_window.py` → Main container
- `gui/plotting_tab.py` → Most user interactions happen here

**Settings:**
- `utils/settings.py` → Singleton settings manager
- Saved in `settings.json`

---

## Questions? Issues?

1. Check existing code for similar functionality
2. Review test files for examples
3. Check TODO_REMAINING_FEATURES.md for planned work
4. Look at similar test types for patterns

**Remember:** The codebase is modular - most additions only require changes in one or two files.

---

**This guide is a living document. Update it as the project evolves.**


