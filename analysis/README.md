# Analysis Module

## Overview

The `Helpers/Analysis/` module provides comprehensive analysis tools for IV sweep data and sample-level analysis. All analysis functionality has been unified into this single module with a clear hierarchical structure.

---

## Module Structure

```
Helpers/Analysis/
├── core/                          # Fundamental analysis (no aggregation)
│   ├── sweep_analyzer.py         # Analyzes ONE sweep file (class: SweepAnalyzer)
│   └── __init__.py
├── aggregators/                   # Multi-level aggregators
│   ├── device_analyzer.py        # Aggregates sweeps for ONE device (placeholder)
│   ├── section_analyzer.py       # Aggregates devices in a section
│   ├── sample_analyzer.py        # Aggregates devices in a sample
│   ├── comprehensive_analyzer.py # Orchestrates all aggregators
│   └── __init__.py
├── api/                           # Public API wrappers (most commonly used)
│   ├── iv_sweep_analyzer.py      # Convenience wrapper (quick_analyze, analyze_sweep)
│   ├── iv_sweep_llm_analyzer.py  # Optional LLM analysis
│   └── __init__.py
├── utils/                         # Utility scripts
│   └── migrate_folder_structure.py
└── docs/                          # Documentation files
    ├── README.md (detailed usage)
    ├── ENHANCED_CLASSIFICATION_README.md
    └── IMPLEMENTATION_SUMMARY.md
```

---

## Quick Start

### Most Common Usage - Quick Analysis

```python
from analysis import quick_analyze

# After a sweep, analyze the data:
voltages = [...]  # Your voltage array
currents = [...]  # Your current array

results = quick_analyze(voltages, currents)
print(results['classification']['device_type'])  # e.g., 'memristive'

# With metadata:
results = quick_analyze(
    voltages, currents,
    metadata={'led_on': True, 'led_type': 'UV', 'temperature': 25.0}
)
```

### Analyze from File

```python
from analysis import analyze_sweep

data = analyze_sweep(file_path="sweep.txt")
print(data['classification']['device_type'])
print(data['resistance_metrics']['switching_ratio_mean'])
```

### Full Sample Analysis (GUI Button Equivalent)

```python
from analysis import ComprehensiveAnalyzer

# Analyze entire sample
analyzer = ComprehensiveAnalyzer(sample_directory="path/to/sample")
analyzer.run_comprehensive_analysis()

# This generates:
# - Device-level combined sweep plots
# - Section-level analysis
# - Sample-level analysis (12 plot types per code_name)
# - Overall sample analysis
# - Origin-ready data exports
```

---

## Module Hierarchy & Usage

### 1. Core Module (`core/`) - Fundamental Analysis

**Purpose**: Analyzes single sweeps (no aggregation)

**Main Class**: `SweepAnalyzer` (formerly `analyze_single_file`)

```python
from analysis import SweepAnalyzer

# Direct access to core analyzer
analyzer = SweepAnalyzer(
    voltage=voltages,
    current=currents,
    time=timestamps,  # optional
    analysis_level='full'  # 'basic', 'classification', 'full', 'research'
)

# Access results
device_type = analyzer.device_type
memristivity_score = analyzer.memristivity_score
resistance_metrics = analyzer.get_resistance_metrics()
```

**When to use**: When you need direct access to all methods and properties of the analyzer, or for custom analysis workflows.

---

### 2. Aggregators Module (`aggregators/`) - Multi-Level Analysis

#### DeviceAnalyzer (Future - Placeholder)

```python
from analysis import DeviceAnalyzer

# Will analyze all sweeps for a single device
# Currently placeholder - future implementation
analyzer = DeviceAnalyzer(device_directory="path/to/device")
results = analyzer.analyze_device()
```

#### SectionAnalyzer

```python
from analysis import SectionAnalyzer

# Analyze a section (letter folder)
analyzer = SectionAnalyzer(
    top_level_path="path/to/sample",
    section="A",  # Section letter
    sample_name="sample_name"
)
analyzer.analyze_section_sweeps()

# Generates:
# - Stacked sweep plots (first/second/third sweeps)
# - Statistical comparisons
# - Section-level summaries
```

#### SampleAnalysisOrchestrator

```python
from analysis import SampleAnalysisOrchestrator

# Analyze entire sample (100+ devices)
analyzer = SampleAnalysisOrchestrator(
    sample_directory="path/to/sample",
    code_name="St_v1"  # Optional: filter by code_name
)

device_count = analyzer.load_all_devices()  # Load tracking data
analyzer.generate_all_plots()  # Generate 12 plot types
analyzer.export_origin_data()  # Export Origin-ready data
```

**13 Plot Types Generated**:
1. Memristivity Score Heatmap
2. Conduction Mechanism Distribution
3. Memory Window Quality Distribution
4. Hysteresis Shape Radar
5. Enhanced Classification Scatter
6. Forming Progress Tracking
7. Warning Flag Summary
8. Research Diagnostics Scatter Matrix
9. Power & Energy Efficiency
10. Device Leaderboard
11. Spatial Distribution Maps
12. Forming Status Distribution
13. Device Size Comparison (comparing 100um, 200um, 400um device sizes)

**Plus 3 Specialized I-V Overlay Plots** (in `size_comparison/` folder):
- All memristive I-V curves grouped by size
- Top device per section grouped by size
- Top 5 devices overall grouped by size

#### ComprehensiveAnalyzer ⭐ **MAIN ENTRY POINT**

```python
from analysis import ComprehensiveAnalyzer

# One-stop comprehensive analysis
analyzer = ComprehensiveAnalyzer(sample_directory="path/to/sample")
analyzer.run_comprehensive_analysis()

# This automatically:
# 1. Discovers all code_names from files
# 2. Generates device-level combined plots
# 3. Runs section-level analysis
# 4. Runs sample-level analysis for each code_name
# 5. Runs overall sample analysis
```

**When to use**: This is the main entry point called by the "Run Full Sample Analysis" button in the GUI.

---

### 3. API Module (`api/`) - Convenience Wrappers

**Purpose**: Easy-to-use functions and classes for common tasks

#### quick_analyze() ⭐ **MOST COMMONLY USED**

```python
from analysis import quick_analyze

# Simplest way to analyze a sweep
results = quick_analyze(
    voltage=voltages,
    current=currents,
    time=timestamps,  # optional
    metadata={'device_name': 'A1', 'temperature': 25.0},  # optional
    analysis_level='full',  # 'basic', 'classification', 'full', 'research'
    device_id='sample_A_1',  # optional
    save_directory='path/to/save'  # optional
)

# Returns dictionary with:
# - classification: device_type, memristivity_score, etc.
# - resistance_metrics: Ron, Roff, switching_ratio, etc.
# - hysteresis: memory_window, pinched, etc.
# - quality: memory_window_quality, etc.
# - warnings: list of warning flags
```

#### analyze_sweep()

```python
from analysis import analyze_sweep

# Analyze from file path
data = analyze_sweep(
    file_path="sweep.txt",
    analysis_level='full',
    metadata={'led_on': True}
)
```

#### IVSweepAnalyzer Class

```python
from analysis import IVSweepAnalyzer

# For batch processing or when you need the analyzer instance
analyzer = IVSweepAnalyzer(analysis_level='full')

# Analyze multiple sweeps
data1 = analyzer.analyze_sweep(file_path="sweep1.txt")
data2 = analyzer.analyze_sweep(file_path="sweep2.txt")
```

#### IVSweepLLMAnalyzer (Optional)

```python
from analysis import IVSweepLLMAnalyzer

# Adds LLM-powered insights (slower, optional)
llm_analyzer = IVSweepLLMAnalyzer(
    analysis_level='full',
    llm_backend='ollama',  # or 'llama-cpp-python', 'transformers'
    llm_model='llama2'
)

result = llm_analyzer.analyze_with_insights(
    voltage=voltages,
    current=currents
)

print(result['llm_insights'])  # Natural language analysis
```

---

## GUI Button → Code Mapping

### "▶ Run Full Sample Analysis" Button

**Location**: `gui/measurement_gui/layout_builder.py:2707-2720`  
**Function**: `gui/measurement_gui/main.py:2858-3007` → `run_full_sample_analysis()`

**Equivalent Code**:
```python
from analysis import ComprehensiveAnalyzer

analyzer = ComprehensiveAnalyzer(sample_directory)
analyzer.set_log_callback(lambda msg: print(msg))  # Optional: progress logging
analyzer.run_comprehensive_analysis()
```

**Output**: `{sample_dir}/sample_analysis/`

---

### "Plot Current Device Graphs" Button

**Location**: `gui/measurement_gui/layout_builder.py:2729-2740`  
**Function**: `gui/measurement_gui/main.py:2522-2712` → `plot_all_device_graphs()`

**Equivalent Code**:
```python
from analysis import quick_analyze
from plotting import UnifiedPlotter
import numpy as np

# Load data from file
data = np.loadtxt(file_path, skiprows=1)
voltage = data[:, 0]
current = data[:, 1]
time = data[:, 2] if data.shape[1] > 2 else None

# Analyze
results = quick_analyze(voltage, current, time, analysis_level='full')

# Plot
plotter = UnifiedPlotter(save_dir=device_dir, auto_close=True)
plotter.plot_iv_dashboard(
    voltage=voltage,
    current=current,
    time=time,
    device_name=device_name,
    save_name=f"{device_name}_iv_dashboard.png"
)
```

**Output**: `{sample_dir}/{section}/{device_num}/images/`

---

### "Plot All Sample Graphs" Button

**Location**: `gui/measurement_gui/layout_builder.py:2743-2754`  
**Function**: `gui/measurement_gui/main.py:2715-2856` → `plot_all_sample_graphs()`

**Equivalent Code** (similar to above, but loops through all devices):
```python
from analysis import quick_analyze
from plotting import UnifiedPlotter

# Loop through all device folders
for section, device_num, device_dir in device_dirs:
    for txt_file in device_dir.glob('*.txt'):
        # Load, analyze, plot (same as above)
        ...
```

---

## Analysis Levels

The `analysis_level` parameter controls how much analysis is performed:

- **`'basic'`**: Fast, core metrics only (Ron, Roff, areas)
- **`'classification'`**: Adds device classification (memristive, ohmic, etc.)
- **`'full'`**: Adds conduction models and advanced metrics (default)
- **`'research'`**: Maximum detail with extra diagnostics

---

## Adding New Analysis

### Adding New Sweep-Level Metrics

**File**: `core/sweep_analyzer.py`  
**Class**: `SweepAnalyzer`

```python
# Add new method to SweepAnalyzer class
def calculate_my_new_metric(self):
    """Calculate custom metric."""
    # Your implementation
    return result
```

These will automatically be available via `quick_analyze()` wrapper.

---

### Adding New Sample-Level Plots

**File**: `aggregators/sample_analyzer.py`  
**Class**: `SampleAnalysisOrchestrator`

```python
# Add new plot method
def plot_my_new_analysis(self):
    """Generate new plot type."""
    # Your implementation
    # Save to self.plots_dir
    
# Add to generate_all_plots() method
def generate_all_plots(self):
    # ... existing plots ...
    self.plot_my_new_analysis()  # Add here
```

---

### Adding New Device-Level Analysis

**File**: `aggregators/device_analyzer.py`  
**Class**: `DeviceAnalyzer` (currently placeholder)

This is where you would implement comprehensive device-level analysis that combines all sweeps for a single device.

---

### Adding to Comprehensive Analysis

**File**: `aggregators/comprehensive_analyzer.py`  
**Class**: `ComprehensiveAnalyzer`

```python
def run_comprehensive_analysis(self):
    # ... existing analysis ...
    
    # Add your new analysis step
    self.my_new_analysis_step()
```

---

## Import Patterns

### Recommended Imports (Use These)

```python
# Most common - quick analysis
from analysis import quick_analyze

# Full sample analysis
from analysis import ComprehensiveAnalyzer

# Direct access to core analyzer
from analysis import SweepAnalyzer

# Sample-level analysis
from analysis import SampleAnalysisOrchestrator

# Section-level analysis
from analysis import SectionAnalyzer
```

### Avoid (Use Main Import Instead)

```python
# Don't do this (unless you need specific internal access):
from analysis.core.sweep_analyzer import SweepAnalyzer
from analysis.aggregators.comprehensive_analyzer import ComprehensiveAnalyzer

# Do this instead:
from analysis import SweepAnalyzer, ComprehensiveAnalyzer
```

---

## Output Structure

### Sample Analysis Output

```
{sample_dir}/
└── sample_analysis/
    ├── device_tracking/           # Device history JSON files
    │   └── {device_id}_history.json
    ├── device_research/           # Research-level analysis JSON files
    │   └── {device_id}/
    │       └── {filename}_research.json
    ├── plots/                     # Generated plots
    │   ├── {code_name}/           # Code-name specific plots
    │   │   └── 01_memristivity_heatmap.png
    │   │   └── 02_conduction_mechanisms.png
    │   │   └── ... (12 plot types)
    │   └── overall/               # Overall analysis plots
    ├── plots/data_origin_formatted/  # Origin-ready CSV files
    │   ├── {code_name}/
    │   └── overall/
    └── device_summaries/          # Device summary files
```

---

## Dependencies

### Internal Dependencies

```
ComprehensiveAnalyzer
    ├─> SectionAnalyzer
    │   └─> SweepAnalyzer (from core)
    └─> SampleAnalysisOrchestrator
        └─> (reads from device_tracking/)

IVSweepAnalyzer (api)
    └─> SweepAnalyzer (from core)

IVSweepLLMAnalyzer (api)
    └─> IVSweepAnalyzer (api)
```

### External Dependencies

- `Helpers/plotting_core/` - For plotting functionality
- `Json_Files/test_configurations.json` - For test type configurations
- `numpy`, `matplotlib`, `pandas` - Standard scientific Python libraries

---

## Examples

### Example 1: Quick Analysis After Measurement

```python
from analysis import quick_analyze

# After running a sweep
voltage_data = [...]  # From your measurement
current_data = [...]  # From your measurement

# Quick analysis
results = quick_analyze(voltage_data, current_data)

# Check if memristive
if results['classification']['device_type'] == 'memristive':
    print(f"Memristivity Score: {results['classification']['memristivity_score']}")
    print(f"Switching Ratio: {results['resistance_metrics']['switching_ratio_mean']}")
```

### Example 2: Full Sample Analysis

```python
from analysis import ComprehensiveAnalyzer

# Analyze entire sample (like clicking "Run Full Sample Analysis" button)
analyzer = ComprehensiveAnalyzer("C:/Data/sample_name")

# Optional: Set progress callback
def log_progress(message):
    print(f"[Analysis] {message}")

analyzer.set_log_callback(log_progress)

# Run comprehensive analysis
analyzer.run_comprehensive_analysis()

# Results saved to: {sample_dir}/sample_analysis/
```

### Example 3: Custom Analysis Workflow

```python
from analysis import SweepAnalyzer, SampleAnalysisOrchestrator

# Direct access to core analyzer for custom workflow
analyzer = SweepAnalyzer(voltage, current, analysis_level='research')

# Access all metrics
memristivity = analyzer.memristivity_score
conduction_mechanism = analyzer.dominant_conduction_mechanism
research_data = analyzer.get_research_summary()

# Use in custom workflow
if memristivity > 80:
    # Do something special for high-quality memristors
    ...
```

---

## Notes

- **Code Names**: Test types are extracted from filenames (position 6 after splitting by '-')
- **Filtering**: Analysis can be filtered by code_name or run on all measurements (overall)
- **Backward Compatibility**: Old import paths (`analysis`, `analysis`) no longer work - use `analysis` instead
- **Class Name Change**: `analyze_single_file` → `SweepAnalyzer` (all code updated)
- **File Name Change**: `single_file_metrics.py` → `sweep_analyzer.py`

---

## See Also

- `docs/README.md` - Detailed usage documentation for sweep analysis
- `docs/ENHANCED_CLASSIFICATION_README.md` - Enhanced classification system
- `docs/IMPLEMENTATION_SUMMARY.md` - Implementation details
- `../ANALYSIS_STRUCTURE.md` - Button mapping and detailed structure documentation

