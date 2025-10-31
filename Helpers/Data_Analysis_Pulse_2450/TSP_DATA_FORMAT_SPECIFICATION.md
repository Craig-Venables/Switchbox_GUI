# TSP Testing GUI Data Format Specification

This document describes the file format used by the TSP Testing GUI for saving pulse measurement data. This specification is intended for building plotting and analysis tools.

## Overview

Each TSP measurement creates **three files**:
1. **`.txt`** - Tab-delimited data file with metadata header
2. **`.png`** - Plot image (if available)
3. **`tsp_test_log.txt`** - Log file (shared across all tests in directory)

This specification focuses on the `.txt` data file format.

---

## File Structure

### 1. Metadata Header Section

All metadata is written as comments (lines starting with `#`) before the data section.

#### Header Structure (in order):

```
# ================================================================
# Keithley 2450 TSP Pulse Test: <test_name>
# ================================================================
# Timestamp: <YYYY-MM-DD HH:MM:SS>
# Sample: <sample_name>
# Device: <device_label>
# Instrument: Keithley 2450
# Address: <instrument_address>
#
# Test Parameters:
#   <param_key>: <param_value>
#   <param_key>: <param_value>
#   ... (one line per parameter)
#
# Hardware Limits: (if available)
#   min_pulse_width: <value> ms
#   max_voltage: <value> V
#   max_current_limit: <value> A
#
# Data Points: <number_of_data_points>
# Duration: <duration_in_seconds>
#
# User Notes: (if present)
#   <note_line_1>
#   <note_line_2>
#   ...
#
# ================================================================
# <column_headers>
```

#### Metadata Fields:

| Field | Description | Example |
|-------|-------------|---------|
| `test_name` | Name of the test pattern | `"Pulse-Read-Repeat"`, `"Potentiation-Depression Cycle"` |
| `timestamp` | When test was run | `"2025-10-31 14:30:22"` |
| `sample` | Sample identifier | `"Sample_1"`, `"UnknownSample"` |
| `device` | Device identifier | `"A1"`, `"B3"` |
| `instrument` | Always `"Keithley 2450"` | `"Keithley 2450"` |
| `address` | VISA resource address | `"USB0::0x05E6::0x2450::04496615::INSTR"` |
| `parameters` | Dictionary of test parameters | See Parameters section below |
| `hardware_limits` | Instrument safety limits | See Hardware Limits section |
| `notes` | User-added notes (multi-line) | Free-form text |

#### Test Parameters (varies by test type):

Common parameters include:
- `pulse_voltage` (V) - Voltage applied during pulse
- `pulse_width` (s or ms) - Duration of pulse
- `read_voltage` (V) - Voltage for read measurements
- `num_cycles` (int) - Number of measurement cycles
- `delay_between` (s or ms) - Delay between operations
- `clim` (A) - Current limit/compliance

**Note:** Parameter names and values vary by test type. All parameters are included in the metadata header.

---

### 2. Data Section

#### Column Structure

Data columns appear in this order:

1. **Measurement_Number** (int) - Sequential measurement index (0-based)
2. **Timestamp(s)** (float, scientific notation) - Time from test start (seconds)
3. **Voltage(V)** (float, scientific notation) - Applied/measured voltage
4. **Current(A)** (float, scientific notation) - Measured current
5. **Resistance(Ohm)** (float, scientific notation) - Calculated resistance (V/I)
6. **Additional columns** (varies by test type) - See Additional Columns section

#### Data Format

- **Delimiter:** Tab (`\t`)
- **Encoding:** UTF-8
- **Format specifications:**
  - Integer: `%d` (Measurement_Number only)
  - Float: `%0.6E` (all numeric columns, scientific notation)

#### Column Headers Format

Headers are written on a single line starting with `#`, using tab delimiter:
```
# Measurement_Number	Timestamp(s)	Voltage(V)	Current(A)	Resistance(Ohm)	[Additional columns...]
```

#### Data Rows

Each row represents one measurement point:
- Measurement number starts at 0
- Timestamp is relative to test start (0.0 = first measurement)
- All numeric values in scientific notation (e.g., `1.234567E-03`)
- Missing/invalid values may appear as `NaN`

**Example data row:**
```
0	0.000000E+00	2.000000E-01	1.234567E-06	1.620000E+05
```

---

### 3. Additional Columns (Test-Specific)

Different test types may include additional columns:

#### Common Additional Columns:

| Column Name | Type | Description | Example Test Types |
|-------------|------|-------------|-------------------|
| `Phase` | string | Operation phase | `"potentiation"`, `"depression"`, `"read"` |
| `Cycle_Number` | int | Cycle index (0-based) | Endurance, Multi-cycle tests |
| `Pulse_Widths` | float | Pulse width for this measurement | Width sweep tests |
| `Operation` | string | Type of operation | `"pulse"`, `"read"`, `"reset"` |

#### Column Detection:

- Additional columns appear after the standard 5 columns
- Column names are formatted with spaces and title case: `"Cycle Number"`, `"Pulse Widths"`
- String columns use format `%s`
- Numeric columns use format `%0.6E`

---

## File Naming Convention

### Simple Save Mode:
```
<test_name>-<index>_<test_details>-<timestamp>.txt
```

Example:
```
Pulse-Read-Repeat-001_1.5V_1ms-20251031_143022.txt
```

### Structured Save Mode:
```
<index>-<test_name_clean>-<test_details>-<timestamp>.txt
```

Example:
```
0-Pulse_Read_Repeat-1.5V_1ms-20251031_143022.txt
```

Where:
- `test_name_clean` = test name with spaces/hyphens replaced by underscores
- `test_details` = Key parameters like voltage, pulse width (max 3, separated by underscores)
- `timestamp` = `YYYYMMDD_HHMMSS`

---

## Test Types and Their Data Structure

### 1. Pulse-Read-Repeat
**Standard columns only:**
- Measurement_Number
- Timestamp(s)
- Voltage(V)
- Current(A)
- Resistance(Ohm)

**Pattern:** Initial Read → (Pulse → Read → Delay) × N

### 2. Multi-Pulse-Then-Read
**Standard columns only**

**Pattern:** Initial Read → (Pulse×N → Read×M) × Cycles

### 3. Width Sweep / Width Sweep (Full)
**Additional columns:**
- `Pulse Widths` (float) - Width used for this measurement

### 4. Potentiation-Depression Cycle
**Additional columns:**
- `Phase` (string) - `"potentiation"`, `"depression"`, or `"read"`)

### 5. Endurance Test
**Additional columns:**
- `Cycle Number` (int) - Which cycle this measurement belongs to
- `Phase` (string) - Operation type

### 6. Relaxation Tests
**Additional columns:**
- May include `Operation` (string) - `"pulse"`, `"read"`, etc.

---

## Reading the Files Programmatically

### Python Example:

```python
from pathlib import Path
import numpy as np
import re
from typing import Dict, List, Tuple, Any

def parse_tsp_file(filepath: Path) -> Tuple[np.ndarray, Dict[str, Any], List[str]]:
    """
    Parse a TSP measurement file.
    
    Returns:
        Tuple of (data_array, metadata_dict, column_headers)
    """
    metadata = {}
    headers = []
    data_rows = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Parse header
    header_end = None
    for i, line in enumerate(lines):
        if line.startswith('# ================================================================'):
            continue
        if line.startswith('# Keithley 2450 TSP Pulse Test:'):
            metadata['test_name'] = line.split(':', 1)[1].strip()
        elif line.startswith('# Timestamp:'):
            metadata['timestamp'] = line.split(':', 1)[1].strip()
        elif line.startswith('# Sample:'):
            metadata['sample'] = line.split(':', 1)[1].strip()
        elif line.startswith('# Device:'):
            metadata['device'] = line.split(':', 1)[1].strip()
        elif line.startswith('# Address:'):
            metadata['address'] = line.split(':', 1)[1].strip()
        elif line.startswith('#   ') and ':' in line:
            # Test parameter
            key, value = line[4:].split(':', 1)
            if 'parameters' not in metadata:
                metadata['parameters'] = {}
            metadata['parameters'][key.strip()] = value.strip()
        elif line.startswith('# Data Points:'):
            metadata['data_points'] = int(line.split(':')[1].strip())
        elif line.startswith('# Duration:'):
            duration_str = line.split(':')[1].strip()
            try:
                metadata['duration'] = float(duration_str.split()[0])
            except:
                metadata['duration'] = duration_str
        elif line.startswith('# ') and '\t' in line:
            # Column headers
            header_line = line[2:].strip()  # Remove '# '
            headers = header_line.split('\t')
            header_end = i
            break
    
    # Parse data (skip header, start after header line)
    for line in lines[header_end + 1:]:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Split by tab and convert to float
        values = line.split('\t')
        # First column is int (Measurement_Number), rest are float
        row = [int(values[0])] + [float(v) if v != 'NaN' else np.nan for v in values[1:]]
        data_rows.append(row)
    
    # Convert to numpy array
    data = np.array(data_rows)
    
    return data, metadata, headers

# Usage
filepath = Path("path/to/measurement.txt")
data, metadata, headers = parse_tsp_file(filepath)

# Access columns by index or name
measurement_numbers = data[:, 0]
timestamps = data[:, 1]
voltages = data[:, 2]
currents = data[:, 3]
resistances = data[:, 4]
```

---

## Plot File (PNG)

If available, a `.png` file with the same base name contains a matplotlib figure saved at 200 DPI with `bbox_inches='tight'`.

Plot types vary by test:
- Time series plots (resistance/current vs time)
- Width vs resistance plots
- Potentiation-depression hysteresis plots
- Endurance cycle plots

---

## Log File (tsp_test_log.txt)

Located in the same directory as data files. Format:
```
<timestamp>, <test_name>, <filename>, points=<num_points>
```

Example:
```
2025-10-31 14:30:22, Pulse-Read-Repeat, 0-Pulse_Read_Repeat-1.5V_1ms-20251031_143022.txt, points=200
```

Useful for listing all tests in a directory.

---

## Key Points for Plotting Tool Development

### 1. File Selection
- Look for `.txt` files in user-selected directories
- Optional: Parse `tsp_test_log.txt` for quick file listing

### 2. Data Preview
- Show metadata (test_name, sample, device, parameters)
- Display first/last few rows
- Show column count and names
- Display data statistics (min/max/mean for numeric columns)

### 3. Plotting Requirements
- **X-axis options:** Timestamp(s), Measurement_Number, or additional columns
- **Y-axis options:** Voltage(V), Current(A), Resistance(Ohm), or additional numeric columns
- **Multiple traces:** Overlay multiple files on same plot
- **Legend:** Use test_name + sample + device, or filename
- **Axes labels:** Automatically extract from column headers

### 4. Data Adjustments
- Filter by measurement number or timestamp ranges
- Normalize timestamps (align to zero or specific point)
- Apply mathematical transformations (log, sqrt, etc.)
- Calculate derived quantities (conductance, power, etc.)

### 5. Export to Origin
- Export selected data to Origin-compatible format
- Include metadata as worksheet notes or comments
- Preserve column headers and units
- Support both tab-delimited and Origin binary formats

---

## Example File Contents

### Minimal Example (Pulse-Read-Repeat):
```
# ================================================================
# Keithley 2450 TSP Pulse Test: Pulse-Read-Repeat
# ================================================================
# Timestamp: 2025-10-31 14:30:22
# Sample: Sample_1
# Device: A1
# Instrument: Keithley 2450
# Address: USB0::0x05E6::0x2450::04496615::INSTR
#
# Test Parameters:
#   pulse_voltage: 1.5
#   pulse_width: 0.001
#   read_voltage: 0.2
#   delay_between: 0.01
#   num_cycles: 100
#   clim: 0.0001
#
# Data Points: 201
# Duration: 2.010 s
#
# ================================================================
# Measurement_Number	Timestamp(s)	Voltage(V)	Current(A)	Resistance(Ohm)
0	0.000000E+00	2.000000E-01	1.234567E-06	1.620000E+05
1	1.000000E-02	2.000000E-01	1.245678E-06	1.605000E+05
2	2.100000E-02	1.500000E+00	1.234567E-03	1.215000E+03
...
```

---

## Validation Checklist for Plotting Tool

When implementing a plotting tool, ensure it can:

- [ ] Parse metadata header correctly
- [ ] Handle variable number of columns
- [ ] Distinguish between numeric and string columns
- [ ] Handle missing/NaN values gracefully
- [ ] Display data preview with metadata
- [ ] Support multiple file selection
- [ ] Plot multiple traces on same axes
- [ ] Allow axis selection (X and Y)
- [ ] Support data filtering/transformation
- [ ] Export to Origin-compatible format
- [ ] Handle different test types (with their additional columns)
- [ ] Display test parameters in legend or info panel
- [ ] Support log scale, normalization, and other plot adjustments
- [ ] Save plot configurations for reuse

---

## Notes for Implementation

1. **Column Detection:** Always read headers from the file - don't assume column order beyond the first 5 standard columns
2. **Metadata Parsing:** Test parameters may vary - parse dynamically, don't hardcode expected parameters
3. **Missing Data:** Handle NaN values appropriately in plots (skip or interpolate)
4. **String Columns:** Some tests have string columns (like "Phase") - these can be used for plot coloring/grouping
5. **File Encoding:** Always use UTF-8 encoding when reading/writing
6. **Tab Delimiter:** Data uses tabs, not spaces or commas
7. **Scientific Notation:** All floats are in scientific notation - handle display appropriately

---

**Last Updated:** 2025-10-31  
**Version:** 1.0

