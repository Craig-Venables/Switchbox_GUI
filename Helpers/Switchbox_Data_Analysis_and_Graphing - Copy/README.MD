# Switchbox Data Analysis and Graphing

Comprehensive analysis toolkit for memristor device measurements at the sample, section, device, and sweep levels. This codebase has been cleaned and optimized for integration into larger analysis systems.

## Overview

The toolkit supports:
- **Sample-level orchestration** via `Main.py` - Coordinates analysis across multiple sections
- **Section aggregation, plotting, and statistics** via `data_analyzer.py` - Analyzes sections with predesigned sweep configurations
- **Single-sweep/device characterization** via `single_file_metrics.py` - Comprehensive I–V, pulse, endurance, and retention analysis
- **Test configuration management** via `test_configurations.json` - Defines sweep combinations and main sweeps for different test types

The code is robust with legacy data (I–V only) and newer measurements (with time). When `time` is missing, analysis gracefully falls back to I–V-only.

## Features

- **Modular Design**: Clean, well-documented classes that can be integrated into other systems
- **Comprehensive Documentation**: Detailed docstrings for all classes and methods
- **System-Agnostic**: No hardcoded paths; all parameters are configurable
- **Predesigned Sweep Support**: Works with predefined sweep configurations from JSON files
- **Multiple Analysis Levels**: From basic metrics to advanced research diagnostics

## Quick Start

### Installation

1) Install Python 3.9+ and dependencies:
```bash
pip install numpy pandas matplotlib seaborn scipy
```

### Data Structure

Prepare your data directory structure:
```
<ROOT> / <SampleName> / <Section> / <DeviceNumber> / <sweep files>
```
Example: `C:\...\Data_save_loc\D104\A\1\1-FS-...txt`

### Usage

#### Command Line Interface

Run sample analysis:
```bash
python Main.py "<ROOT>" "<SampleName>"
```

Or with custom sections:
```bash
python Main.py "<ROOT>" "<SampleName>" --sections A B D E
```

#### Programmatic Usage

For integration into other systems:

```python
from Main import SampleAnalyzer

# Initialize analyzer
analyzer = SampleAnalyzer(
    top_level_path="path/to/data",
    sections=['A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L']  # Optional
)

# Analyze a sample
analyzer.analyze_sample("D104")
```

By default, `Main.py` enumerates sections A,B,D,E,F,G,H,I,K,L and:
- Categorizes sweeps by test type and voltage
- Plots by type and voltage
- Extracts main-sweep stats per device
- Generates section statistics, comparisons, and an HTML report

Outputs are written under `<ROOT>/<SampleName>/<Section>/plots_combined/statistics/` and `<ROOT>/<SampleName>/sample_summary/`.

## Module Documentation

### Single-file Analyzer (`single_file_metrics.py`)

The `analyze_single_file` class provides comprehensive device characterization for individual sweep files.

**Initialization:**
```python
from single_file_metrics import analyze_single_file

analyzer = analyze_single_file(
    voltage,                    # array-like: Applied voltage data
    current,                    # array-like: Measured current data
    time=None,                  # array-like, optional: Time data for pulse/retention
    measurement_type='iv_sweep', # str: 'iv_sweep', 'pulse', 'endurance', 'retention'
    analysis_level='full'       # str: 'basic', 'classification', 'full', 'research'
)
```

**Key Features:**
- **Analysis levels**: 
  - `basic`: Fast loop split + core metrics (Ron/Roff, ON/OFF, areas)
  - `classification`: Basic + features + device classification
  - `full`: Classification + conduction models + advanced metrics
  - `research`: Full + extra diagnostics (NDR, kink voltage, loop similarity)
- **Measurement types**: `iv_sweep`, `pulse`, `endurance`, `retention` (auto-detects; falls back to I–V if time is missing)
- **Outputs**: Classification (with confidence and explanation), conduction model fits, advanced metrics, research diagnostics
- **Plotting**: `plot_device_analysis()` for summary panels, `plot_conduction_analysis()` for model diagnostics

**Key Methods:**
- `get_summary_stats()`: Returns dictionary of device statistics
- `get_classification_report()`: Returns device type classification with confidence
- `get_memristor_performance_metrics()`: Returns performance metrics for memristive devices
- `validate_memristor_behavior()`: Validates if device exhibits memristive behavior

### Section Analyzer (`data_analyzer.py`)

The `DataAnalyzer` class handles section-level analysis with predesigned sweep configurations.

**Initialization:**
```python
from data_analyzer import DataAnalyzer

analyzer = DataAnalyzer(
    top_level_path="path/to/data",  # Root directory containing sample data
    section="A",                     # Section identifier
    sample_name="D104",             # Sample/substrate name
    config_path="test_configurations.json"  # Optional: path to config file
)
```

**Key Features:**
- Detects test types from filenames, categorizes sweeps
- Plots by type and by voltage
- Extracts per-device stats (using the single-file analyzer when available)
- Produces robust statistics plots that handle empty/non-positive values
- **Outputs**:
  - `device_stats.csv`: Per-device summary metrics
  - Violin/box plots across devices for key metrics
  - Pairplot for metric relationships
  - Correlation matrix (PNG + CSV)
  - Device leaderboard (CSV) with performance scores
  - Section summary PDF bundling all plots
  - Augmented section quality with memristive yield

**Main Method:**
```python
device_stats, metrics, quality_metrics = analyzer.analyze_section_sweeps(
    sample_name, section, quality_metrics
)
```

### Sample Analyzer (`Main.py`)

The `SampleAnalyzer` class orchestrates analysis across multiple sections of a sample.

**Initialization:**
```python
from Main import SampleAnalyzer

analyzer = SampleAnalyzer(
    top_level_path="path/to/data",
    sections=['A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L']  # Optional
)
```

**Key Features:**
- Coordinates section-level analysis
- Aggregates results across sections
- Generates sample-wide summary reports and visualizations
- Creates quality heatmaps and comparison plots

### Test Configuration (`test_configurations.json`)

Defines sweep combinations and main sweeps for different test types. Each test type specifies:
- `sweep_combinations`: List of sweep number combinations with titles
- `main_sweep`: Integer indicating the main sweep for device characterization

Example:
```json
{
    "St_v1": {
        "sweep_combinations": [
            {"sweeps": [1, 19], "title": "Same voltage sweep before and after forming"},
            {"sweeps": [10], "title": "Main Sweep"}
        ],
        "main_sweep": 10
    }
}
```

## Reports and Artifacts

Per Section (`<Section>/plots_combined/statistics/`):
- `device_stats.csv`: per-device summary metrics
- `<metric>_comparison.png`: bar charts (auto log/linear)
- `main_sweeps_comparison.png`: overlay of main sweeps
- `correlation_matrix.png` and `correlation_matrix.csv`
- `violin_plots.png`, `box_plots.png`, `pairplot.png`
- `device_leaderboard.csv`
- `section_summary.pdf`

Sample Summary (`<SampleName>/sample_summary/`):
- `quality_metrics.csv` and `report.html`
- Section comparison plots and correlation heatmap

## Integration Guide

This codebase has been cleaned and optimized for integration into larger analysis systems:

1. **No Hardcoded Paths**: All paths are passed as parameters
2. **Modular Classes**: Each class can be instantiated and used independently
3. **Comprehensive Docstrings**: All classes and methods are fully documented
4. **Configurable**: Test configurations are loaded from JSON files
5. **Error Handling**: Graceful degradation when data is missing or malformed

### Example Integration

```python
from Main import SampleAnalyzer
from data_analyzer import DataAnalyzer

# Option 1: Full sample analysis
sample_analyzer = SampleAnalyzer(top_level_path="/path/to/data")
sample_analyzer.analyze_sample("D104")

# Option 2: Section-level analysis only
section_analyzer = DataAnalyzer(
    top_level_path="/path/to/data",
    section="A",
    sample_name="D104"
)
quality_metrics = {}
device_stats, metrics, quality_metrics = section_analyzer.analyze_section_sweeps(
    "D104", "A", quality_metrics
)

# Option 3: Single file analysis
from single_file_metrics import analyze_single_file
import numpy as np

voltage, current = np.loadtxt("sweep_file.txt", skiprows=1, unpack=True)
analyzer = analyze_single_file(voltage, current, analysis_level='full')
stats = analyzer.get_summary_stats()
```

## Notes

- The program treats compliance-limited plateaus carefully in classification and linearity checks to avoid false-ohmic conclusions.
- If time data are unavailable, pulse/retention paths degrade to I–V-only analysis without failing.
- All classes are designed to work with predesigned sweep configurations defined in `test_configurations.json`.
- The code has been cleaned of redundant code, commented-out sections, and hardcoded paths for better maintainability.

## Citation

Memristor pinched hysteresis I–V loop illustrations for reference: [`link`](https://www.researchgate.net/figure/Pinched-hysteresis-loop-of-memristor-represents-the-Current-Voltage-characteristics-of-a_fig1_279068568).
