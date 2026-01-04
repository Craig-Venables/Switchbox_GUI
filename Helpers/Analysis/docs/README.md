# IV Analysis Module

Fast and comprehensive analysis tools for IV sweep measurements with optional LLM-powered insights.

---

## About `single_file_metrics.py`

The `single_file_metrics.py` module provides the core analysis engine for IV sweep measurements. It contains the `analyze_single_file` class, which is a comprehensive tool for analyzing memristor and other electronic device measurements.

### Overview

The `analyze_single_file` class performs detailed analysis of current-voltage (I-V) characteristics, supporting multiple measurement types:
- **IV Sweeps**: Standard forward/reverse voltage sweeps
- **Pulse Measurements**: Time-resolved switching analysis
- **Endurance Testing**: Multi-cycle stability analysis
- **Retention Testing**: State stability over time

### Key Capabilities

1. **Loop Detection & Splitting**: Automatically detects and splits multiple measurement loops from continuous data
2. **Resistance Metrics**: Calculates Ron (ON resistance), Roff (OFF resistance), switching ratios, and window margins
3. **Hysteresis Analysis**: Quantifies hysteresis area, pinched hysteresis detection, and shape characterization
4. **Device Classification**: Classifies devices as memristive, capacitive, conductive, or ohmic based on I-V characteristics
5. **Conduction Mechanism Fitting**: Fits theoretical models (Ohmic, SCLC, Poole-Frenkel, Schottky, Fowler-Nordheim, etc.) to identify transport mechanisms
6. **Performance Metrics**: Calculates retention scores, endurance scores, power consumption, and energy per switch
7. **Advanced Diagnostics**: Research-level metrics including NDR index, switching polarity, kink voltage, and loop similarity

### Analysis Levels

The class supports four analysis levels, allowing you to balance speed vs. detail:

- **`'basic'`**: Fast core metrics (Ron/Roff, areas, ON/OFF ratios) - ~1-2 seconds
- **`'classification'`**: Basic + device type classification - ~2-3 seconds  
- **`'full'`**: Classification + conduction models + advanced metrics - ~3-5 seconds (recommended)
- **`'research'`**: Full + extra diagnostics (NDR, kink voltage, loop similarity) - ~5-10 seconds

### Class Structure

The `analyze_single_file` class is initialized with voltage and current data, and optionally time data and measurement type. Upon initialization, it:
1. Validates and preprocesses input data
2. Detects and splits measurement loops
3. Calculates core metrics for each loop
4. Performs classification (if enabled)
5. Fits conduction models (if enabled)
6. Calculates advanced metrics (if enabled)

### Main Attributes

After analysis, the class instance contains numerous attributes with calculated metrics:

**Resistance Metrics:**
- `ron`, `roff`: Lists of ON/OFF resistances for each loop
- `switching_ratio`: Roff/Ron ratio for each loop
- `on_off`: ON/OFF ratio for each loop
- `window_margin`: Resistance window stability metric

**Voltage Metrics:**
- `von`, `voff`: ON/OFF switching voltages
- `r_02V`, `r_05V`: Resistance at specific voltages (0.2V, 0.5V)

**Hysteresis Metrics:**
- `ps_areas`, `ng_areas`: Positive/negative voltage area under curves
- `areas`: Total hysteresis area
- `normalized_areas`: Area normalized by voltage range

**Classification:**
- `device_type`: Classified type (memristive/capacitive/conductive/ohmic)
- `classification_confidence`: Confidence score (0-1)
- `classification_features`: Features used for classification
- `classification_explanation`: Explanation of classification decision

**Conduction Models:**
- `conduction_mechanism`: Best-fitting model name
- `model_parameters`: Fitted parameters and R² value
- `all_model_fits`: All attempted model fits with R² values

**Performance:**
- `retention_score`: State retention quality (0-1)
- `endurance_score`: Cycle-to-cycle consistency (0-1)
- `power_consumption`: Average power per cycle
- `energy_per_switch`: Energy required for switching
- `rectification_ratio`: I(+V)/I(-V) asymmetry
- `nonlinearity_factor`: Degree of I-V nonlinearity
- `asymmetry_factor`: Device asymmetry metric

**Research Diagnostics** (research level only):
- `switching_polarity`: Bipolar/unipolar switching type
- `ndr_index`: Negative differential resistance index
- `hysteresis_direction`: Clockwise/counter-clockwise
- `kink_voltage`: Trap-filled limit voltage estimate
- `loop_similarity_score`: Correlation between loops
- `pinch_offset`: Current magnitude near V≈0
- `noise_floor`: Current noise level

### Helper Functions

The module also includes utility functions:

- **`read_data_file(file_path)`**: Reads voltage, current, and optional time data from a text file
- **`zero_division_check(x, y)`**: Safe division with zero handling
- **`compare_devices(device_files, output_file)`**: Batch comparison of multiple devices, outputs Excel file
- **`batch_process_directory(directory_path, pattern)`**: Process all matching files in a directory, generates plots and reports
- **`generate_latex_table(analyzer, caption)`**: Generate LaTeX table code for publication

---

## Device Size Analysis

The sample analyzer includes device size-based analysis, comparing memristivity and I-V characteristics across different device sizes:

- **200x200um**: Sections a, d, h, k
- **100x100um**: Sections b, e, i, l
- **400x400um**: Sections c, j (optional - only included if present)

### Main Plot: Device Size Comparison (Plot 13)

A comprehensive comparison showing:
- Memristivity score distributions (box plots)
- Switching ratio distributions (box plots)
- Device type distribution by size (stacked bar chart)
- Mean metrics comparison (bar chart)

**Note**: The plot dynamically adjusts to show only size groups that have devices. If only 100um and 200um are present, only those are shown. 400um is included only if devices of that size are present.

### Specialized I-V Overlay Plots

Located in `plots/{code_name}/size_comparison/`:

1. **memristive_iv_overlays_by_size.png**: All memristive device I-V curves overlaid, grouped by size (separate subplot for each size). All subplots use the same locked axis ranges.

2. **top_device_per_section_by_size.png**: Top 1 device from each section folder, grouped by size. Up to 4 curves per size (one per section). All subplots use locked axes.

3. **top5_devices_by_size.png**: Top 5 devices overall (across all sections), grouped by size. Up to 5 curves per size. All subplots use locked axes.

**Features**:
- Dynamic subplot layout (only creates subplots for sizes with data)
- Locked axes across all subplots for direct comparison
- Automatic I-V data loading from device sweep files
- Handles missing data gracefully (skips devices/sizes with no data)

### Size Data Export

The `device_size_comparison.csv` file (in `data_origin_formatted/{code_name}/`) contains:
- Device_ID, Section, Device_Size, Area_um2
- Memristivity_Score, Device_Type, Switching_Ratio
- Memory_Window_Quality, Ron_Mean, Roff_Mean, etc.

---

## Quick Start - After a Sweep (Simplest!)

**Just pass your voltage and current arrays - that's it!**

```python
from Helpers.IV_Analysis import quick_analyze

# Your sweep returns voltage and current arrays
voltages, currents = run_your_sweep()

# One line - get all analysis results
results = quick_analyze(voltages, currents)

# Access results
print(results['classification']['device_type'])
print(results['resistance_metrics']['switching_ratio_mean'])
print(results['resistance_metrics']['ron_mean'])
```

**With metadata (LED state, temperature, etc.):**
```python
results = quick_analyze(
    voltages, currents,
    metadata={'led_on': True, 'led_type': 'UV', 'temperature': 25.0}
)
```

### Alternative: From File

```python
from Helpers.IV_Analysis import analyze_sweep

# One-line analysis - get all data back
data = analyze_sweep(file_path="sweep.txt")

print(data['classification']['device_type'])
print(data['resistance_metrics']['switching_ratio_mean'])
```

---

## Using `single_file_metrics.py` Directly

For more control and direct access to all metrics, you can use the `analyze_single_file` class directly.

### Basic Usage

```python
from Helpers.IV_Analysis.single_file_metrics import analyze_single_file

# Load your data
voltage = [...]  # Your voltage array
current = [...]  # Your current array

# Create analyzer instance (automatically processes data)
analyzer = analyze_single_file(voltage, current)

# Access calculated metrics
print(f"Device Type: {analyzer.device_type}")
print(f"Mean Ron: {np.mean(analyzer.ron):.2e} Ω")
print(f"Mean Roff: {np.mean(analyzer.roff):.2e} Ω")
print(f"Switching Ratio: {np.mean(analyzer.switching_ratio):.1f}")
print(f"Number of Loops: {analyzer.num_loops}")
```

### With Analysis Level Control

```python
# Fast basic analysis (no classification)
analyzer = analyze_single_file(
    voltage, current,
    analysis_level='basic'
)

# Full analysis with classification and conduction models (recommended)
analyzer = analyze_single_file(
    voltage, current,
    analysis_level='full'
)

# Research-level with all diagnostics
analyzer = analyze_single_file(
    voltage, current,
    analysis_level='research'
)
```

### With Time Data (Pulse/Retention Measurements)

```python
# For pulse measurements
analyzer = analyze_single_file(
    voltage, current, time,
    measurement_type='pulse'
)

# Access pulse-specific metrics
print(f"Set Times: {analyzer.set_times}")
print(f"Reset Times: {analyzer.reset_times}")
print(f"Set Voltages: {analyzer.set_voltages}")
print(f"Reset Voltages: {analyzer.reset_voltages}")

# For retention measurements
analyzer = analyze_single_file(
    voltage, current, time,
    measurement_type='retention'
)

# Access retention metrics
if analyzer.state_degradation:
    print(f"Initial Resistance: {analyzer.state_degradation['initial_resistance']}")
    print(f"Decay Rate: {analyzer.state_degradation['decay_rate']}")
```

### Reading from File

```python
from Helpers.IV_Analysis.single_file_metrics import read_data_file, analyze_single_file

# Read data from file
voltage, current, time = read_data_file("measurement.txt")

# Analyze
analyzer = analyze_single_file(voltage, current, time)
```

### Accessing All Metrics

```python
analyzer = analyze_single_file(voltage, current, analysis_level='full')

# Resistance metrics
print(f"Ron: {analyzer.ron}")  # List of Ron for each loop
print(f"Roff: {analyzer.roff}")  # List of Roff for each loop
print(f"Switching Ratio: {analyzer.switching_ratio}")
print(f"Window Margin: {analyzer.window_margin}")

# Voltage metrics
print(f"Von: {analyzer.von}")
print(f"Voff: {analyzer.voff}")
print(f"Resistance at 0.2V: {analyzer.r_02V}")
print(f"Resistance at 0.5V: {analyzer.r_05V}")

# Hysteresis metrics
print(f"Positive Areas: {analyzer.ps_areas}")
print(f"Negative Areas: {analyzer.ng_areas}")
print(f"Total Areas: {analyzer.areas}")
print(f"Normalized Areas: {analyzer.normalized_areas}")

# Classification
print(f"Device Type: {analyzer.device_type}")
print(f"Confidence: {analyzer.classification_confidence}")
print(f"Features: {analyzer.classification_features}")

# Conduction mechanism
print(f"Conduction Mechanism: {analyzer.conduction_mechanism}")
print(f"Model R²: {analyzer.model_parameters.get('R2', 0)}")
print(f"Model Parameters: {analyzer.model_parameters.get('params', {})}")

# Performance metrics
print(f"Retention Score: {analyzer.retention_score}")
print(f"Endurance Score: {analyzer.endurance_score}")
print(f"Power Consumption: {analyzer.power_consumption}")
print(f"Energy per Switch: {analyzer.energy_per_switch}")
print(f"Rectification Ratio: {analyzer.rectification_ratio}")
print(f"Nonlinearity Factor: {analyzer.nonlinearity_factor}")

# Research diagnostics (research level only)
if analyzer.analysis_level == 'research':
    print(f"Switching Polarity: {analyzer.switching_polarity}")
    print(f"NDR Index: {analyzer.ndr_index}")
    print(f"Hysteresis Direction: {analyzer.hysteresis_direction}")
    print(f"Kink Voltage: {analyzer.kink_voltage}")
    print(f"Loop Similarity: {analyzer.loop_similarity_score}")
```

### Getting Summary Reports

```python
analyzer = analyze_single_file(voltage, current, analysis_level='full')

# Get formatted text summary
summary = analyzer.get_research_summary()
print(summary)

# Get summary statistics dictionary
stats = analyzer.get_summary_stats()
print(f"Mean Ron: {stats['mean_ron']:.2e} ± {stats['std_ron']:.2e} Ω")
print(f"Mean Roff: {stats['mean_roff']:.2e} ± {stats['std_roff']:.2e} Ω")
print(f"CV of ON/OFF Ratio: {stats['cv_on_off_ratio']}")
```

### Exporting Results

```python
analyzer = analyze_single_file(voltage, current)

# Export metrics to CSV
analyzer.export_metrics("device_metrics.csv")

# Generate plots (if plot methods are available)
analyzer.plot_device_analysis(save_path="device_analysis.png")
analyzer.plot_conduction_analysis(save_path="conduction_analysis.png")
```

### Batch Processing

```python
from Helpers.IV_Analysis.single_file_metrics import batch_process_directory

# Process all .txt files in a directory
results = batch_process_directory(
    directory_path="./measurements",
    pattern="*.txt"
)

# Results include:
# - Individual analysis plots
# - Individual metrics CSV files
# - Individual summary text files
# - Comparison Excel file (device_comparison.xlsx)
```

### Comparing Multiple Devices

```python
from Helpers.IV_Analysis.single_file_metrics import compare_devices

# Compare multiple device files
device_files = [
    "device1.txt",
    "device2.txt",
    "device3.txt"
]

comparison_df = compare_devices(
    device_files,
    output_file="device_comparison.xlsx"
)

# The Excel file contains:
# - Sheet 1: Detailed comparison of all metrics
# - Sheet 2: Summary statistics
```

### Getting Resistance at Specific Voltage

```python
analyzer = analyze_single_file(voltage, current)

# Get resistance at specific voltage (e.g., 0.2V)
resistance_at_02V = analyzer.get_resistance_at_voltage(0.2)
print(f"Resistance at 0.2V: {resistance_at_02V} Ω")
```

### Generating LaTeX Tables for Publications

```python
from Helpers.IV_Analysis.single_file_metrics import generate_latex_table

analyzer = analyze_single_file(voltage, current, analysis_level='research')

# Generate LaTeX table code
latex_code = generate_latex_table(
    analyzer,
    caption="Memristor Device Characterization Results"
)

# Save to file
with open("table.tex", "w") as f:
    f.write(latex_code)
```

### Handling Multiple Loops

The class automatically detects and splits multiple measurement loops:

```python
analyzer = analyze_single_file(voltage, current)

print(f"Number of loops detected: {analyzer.num_loops}")

# Access metrics for each loop
for i in range(analyzer.num_loops):
    print(f"Loop {i+1}:")
    print(f"  Ron: {analyzer.ron[i]:.2e} Ω")
    print(f"  Roff: {analyzer.roff[i]:.2e} Ω")
    print(f"  Switching Ratio: {analyzer.switching_ratio[i]:.1f}")
    print(f"  Normalized Area: {analyzer.normalized_areas[i]:.4f}")

# Get statistics across all loops
print(f"Mean Switching Ratio: {np.mean(analyzer.switching_ratio):.1f}")
print(f"Std Switching Ratio: {np.std(analyzer.switching_ratio):.1f}")
```

### Error Handling

```python
from Helpers.IV_Analysis.single_file_metrics import analyze_single_file

try:
    analyzer = analyze_single_file(voltage, current)
except ValueError as e:
    print(f"Invalid data: {e}")
except Exception as e:
    print(f"Analysis error: {e}")
```

---

### With Metadata

```python
from Helpers.IV_Analysis import IVSweepAnalyzer

analyzer = IVSweepAnalyzer(analysis_level='full')

metadata = {
    'led_on': True,
    'led_type': 'UV',
    'led_wavelength': 365,
    'temperature': 25.0
}

data = analyzer.analyze_sweep(
    file_path="sweep.txt",
    metadata=metadata
)
```

### With LLM Insights (Optional, Slower)

```python
from Helpers.IV_Analysis import IVSweepLLMAnalyzer

# Initialize with LLM backend
analyzer = IVSweepLLMAnalyzer(
    analysis_level='full',
    llm_backend='ollama',
    llm_model='llama2'
)

# Extract data (fast)
data = analyzer.analyze_sweep(file_path="sweep.txt")

# Get LLM insights (slower, optional)
insights = analyzer.get_llm_insights()
print(insights)
```

---

## Key Methods in `single_file_metrics.py`

### Core Processing Methods

**`__init__(voltage, current, time=None, measurement_type='iv_sweep', analysis_level='full')`**
- Initializes the analyzer and automatically processes the data
- Validates input data and ensures proper formatting
- Detects measurement type if not specified
- Splits data into individual loops
- Calculates metrics based on the specified analysis level

**`process_loops()`**
- Automatically detects and splits multiple measurement loops
- Handles both single sweeps and multi-cycle measurements
- Uses pattern recognition and turning point detection

**`calculate_metrics_for_loops(split_v_data, split_c_data)`**
- Core method that calculates all metrics for each detected loop
- Computes areas, resistances, voltages, and ON/OFF values
- Called automatically during initialization

### Classification Methods

**`_classify_device()`**
- Classifies device as memristive, capacitive, conductive, or ohmic
- Uses extracted features and decision rules
- Sets `device_type`, `classification_confidence`, and `classification_features`
- Only runs for analysis levels 'classification', 'full', or 'research'

**`_extract_classification_features()`**
- Extracts key features from I-V data for classification
- Features include: hysteresis presence, pinched hysteresis, linearity, polarity dependence
- Returns dictionary of feature values

**`_check_pinched_hysteresis()`**
- Detects if hysteresis loop is "pinched" (passes through origin)
- Key indicator of memristive behavior
- Returns boolean and quality score

### Conduction Model Fitting

**`_fit_conduction_models()`**
- Fits multiple theoretical conduction models to I-V data
- Models tested: Ohmic, SCLC, Trap-filled SCLC, Poole-Frenkel, Schottky, Fowler-Nordheim
- Selects best model based on R² value
- Only runs for analysis levels 'full' or 'research'

**`_calculate_r2(y_true, y_pred)`**
- Calculates R-squared value for model fitting
- Measures goodness of fit (0-1, higher is better)

### Advanced Metrics

**`_calculate_advanced_metrics()`**
- Calculates performance metrics beyond basic resistance
- Includes: rectification ratio, nonlinearity, asymmetry, power, energy
- Only runs for analysis levels 'full' or 'research'

**`_calculate_research_diagnostics()`**
- Calculates research-level diagnostics
- Includes: switching polarity, NDR index, kink voltage, loop similarity
- Only runs for analysis level 'research'

### Measurement Type Processing

The analyzer supports four measurement types, each with specialized processing:

**`_process_iv_sweep()`** - Standard I-V Sweep
- Standard forward/reverse voltage sweep measurements
- Calculates all standard metrics (resistance, hysteresis, classification)
- Default processing method
- Most common measurement type
- **Outputs**: Ron, Roff, hysteresis areas, device classification, conduction models

**`_process_pulse_measurement()`** - Pulse Measurements
- Time-resolved switching analysis
- Requires time data in addition to voltage/current
- Extracts set/reset times and voltages
- Calculates switching speeds and energy
- **Outputs**: Set/reset times, set/reset voltages, switching energy, pulse characteristics
- **Use case**: Analyzing switching speed and dynamics

**`_process_endurance_measurement()`** - Endurance Testing
- Multi-cycle stability analysis
- Tracks device performance over many cycles
- Calculates degradation rates and lifetime projections
- **Outputs**: Degradation metrics, cycles to failure (50%, 90%), window degradation
- **Use case**: Reliability testing, lifetime estimation

**`_process_retention_measurement()`** - Retention Testing
- State stability over time
- Requires time data
- Fits retention decay models (logarithmic decay)
- Calculates retention times
- **Outputs**: Initial resistance, decay rate, retention time (50%, 90%)
- **Use case**: Memory retention analysis, state stability

### Utility Methods

**`get_research_summary()`**
- Returns formatted text summary of all metrics
- Organized by category (classification, resistance, performance, etc.)
- Suitable for reports and documentation

**`get_summary_stats()`**
- Returns dictionary with mean and standard deviation of key metrics
- Includes coefficient of variation for variability assessment
- Useful for statistical analysis

**`get_resistance_at_voltage(target_voltage)`**
- Gets resistance value at a specific voltage
- Useful for comparing devices at standard voltages (e.g., 0.2V, 0.5V)

**`export_metrics(filename)`**
- Exports all calculated metrics to CSV file
- Includes per-loop values and device-level classifications
- Useful for further analysis in Excel/Python

**`plot_device_analysis(save_path=None)`**
- Generates comprehensive device analysis plots
- Shows I-V curves, hysteresis, and key metrics
- Can save to file or display

**`plot_conduction_analysis(save_path=None)`**
- Generates plots showing conduction model fits
- Compares different models visually
- Useful for understanding transport mechanisms

### Loop Detection and Splitting

**`check_for_loops(v_data)`**
- Detects number of measurement loops in voltage data
- Uses zero-crossing detection

**`split_loops(v_data, c_data)`**
- Splits continuous data into individual loops
- Returns separate arrays for each loop

**`detect_and_split_loops(v_data, c_data)`**
- Advanced loop detection using multiple methods
- Handles various sweep patterns

### Area Calculations

**`area_under_curves(v_data, c_data)`**
- Calculates area under I-V curves
- Separates positive and negative voltage regions
- Returns: positive area, negative area, total area, normalized area
- Normalized area = total area / voltage range (useful for comparison)

**`on_off_values(voltage_data, current_data)`**
- Calculates Ron, Roff, Von, Voff for a single loop
- Uses threshold-based method (20% of max voltage)
- Returns resistance and voltage values

### Helper Functions

**`read_data_file(file_path)`**
- Reads measurement data from text file
- Supports 2-column (V, I) or 3-column (V, I, T) formats
- Returns voltage, current, and optional time arrays

**`compare_devices(device_files, output_file)`**
- Batch comparison of multiple device files
- Generates Excel file with comparison table
- Includes summary statistics sheet

**`batch_process_directory(directory_path, pattern)`**
- Processes all matching files in a directory
- Generates plots, CSV files, and summaries for each
- Creates comparison Excel file
- Returns list of results

**`generate_latex_table(analyzer, caption)`**
- Generates LaTeX table code from analyzer results
- Suitable for publications
- Includes key metrics in formatted table

---

## Architecture

The module is split into two classes:

1. **IVSweepAnalyzer** - Fast data extraction (always use this first)
2. **IVSweepLLMAnalyzer** - Extends IVSweepAnalyzer with LLM insights (optional)

This design allows you to:
- Extract data quickly without LLM overhead
- Add LLM insights only when needed
- Reuse extracted data for multiple LLM queries

## Key Features

- **Fast Data Extraction**: Extract all metrics without LLM processing
- **Flexible Input**: Accept file paths OR direct voltage/current data
- **Metadata Support**: Include LED state, temperature, humidity, etc.
- **Multiple Measurement Types**: IV sweeps, pulse, endurance, retention
- **Optional LLM Insights**: Add natural language analysis when needed
- **Comprehensive Metrics**: All metrics from analyze_single_file

## Analysis Levels Explained

The `analysis_level` parameter controls how much detail is extracted. Choose based on your needs:

### `'basic'` - Fast Core Metrics
**Speed**: Fastest (~1-2 seconds)  
**Use when**: You just need basic resistance values quickly

**Provides**:
- **Resistance Metrics**: Ron, Roff (mean and std)
- **Voltage Metrics**: Von, Voff, voltage ranges
- **Hysteresis Metrics**: Normalized area, total area, has hysteresis
- **Basic Performance**: Retention score, endurance score
- **Summary Statistics**: Basic statistical summaries

**Missing**: Device classification, conduction mechanisms, advanced diagnostics

---

### `'classification'` - Device Type Identification
**Speed**: Fast (~2-3 seconds)  
**Use when**: You need to know what type of device it is

**Provides**: Everything from `'basic'` PLUS:
- **Device Classification**: Device type (memristive, capacitive, conductive, ohmic)
- **Classification Confidence**: How confident the classification is (0-1)
- **Classification Features**: Key features used for classification
- **Classification Explanation**: Why it was classified this way

**Missing**: Conduction mechanism models, advanced diagnostics

---

### `'full'` - Comprehensive Analysis (Recommended)
**Speed**: Moderate (~3-5 seconds)  
**Use when**: You want complete analysis for most use cases (default)

**Provides**: Everything from `'classification'` PLUS:
- **Conduction Mechanism**: Identified mechanism (Ohmic, Schottky, Poole-Frenkel, etc.)
- **Model Fit Quality**: R² value for conduction model fitting
- **Advanced Performance Metrics**:
  - Rectification ratio
  - Nonlinearity factor
  - Asymmetry factor
  - Power consumption
  - Energy per switch
  - Compliance current
- **Window Margin**: Resistance window stability
- **Detailed Performance**: Additional performance metrics
- **Validation Results**: Memristor behavior validation checks

**Missing**: Research-level diagnostics

---

### `'research'` - Maximum Detail
**Speed**: Slower (~5-10 seconds)  
**Use when**: You need every possible metric for research/publication

**Provides**: Everything from `'full'` PLUS:
- **Research Diagnostics**:
  - Switching polarity (bipolar/unipolar)
  - NDR (Negative Differential Resistance) index
  - Hysteresis direction
  - Kink voltage (if present)
  - Loop similarity score
  - Pinch offset
  - Noise floor
- **Advanced Degradation Metrics**: (for endurance/retention)
  - Degradation rates
  - Lifetime projections
  - Decay analysis

---

## Quick Comparison Table

| Feature | basic | classification | full | research |
|---------|-------|----------------|------|----------|
| Ron, Roff | ✅ | ✅ | ✅ | ✅ |
| Device Type | ❌ | ✅ | ✅ | ✅ |
| Conduction Mechanism | ❌ | ❌ | ✅ | ✅ |
| Performance Metrics | Basic | Basic | Full | Full |
| Research Diagnostics | ❌ | ❌ | ❌ | ✅ |
| Speed | Fastest | Fast | Moderate | Slower |

## Recommendation

- **Most use cases**: Use `'full'` (default) - best balance of speed and detail
- **Quick checks**: Use `'basic'` for fastest results
- **Research/publication**: Use `'research'` for maximum detail
- **Batch processing**: Use `'classification'` or `'basic'` for speed

## Performance

- **Data Extraction**: Fast (~seconds for typical sweeps)
  - `basic`: ~1-2 seconds
  - `classification`: ~2-3 seconds
  - `full`: ~3-5 seconds
  - `research`: ~5-10 seconds
- **LLM Analysis**: Slower (depends on model size, ~10-60 seconds)

**Recommendation**: Always extract data first, then optionally get LLM insights.

## Examples

See `example_usage.py` for complete examples.

---

## Phase 2: Device Tracking & Feedback

### Device Evolution Tracking

Track device performance over time to detect degradation:

```python
from Helpers.IV_Analysis import quick_analyze

# Run analysis with device tracking
results = quick_analyze(
    voltage, current,
    device_id="MyChip_A_1",  # Unique device identifier
    cycle_number=10,         # Current measurement number
    save_directory="/path/to/data"  # Where to save tracking data
)

# Get evolution summary
analyzer = IVSweepAnalyzer()
data = analyzer.analyze_sweep(voltage, current, device_id="MyChip_A_1", save_directory="/path/to/data")
evolution = analyzer.get_device_evolution_summary()

print(f"Total measurements: {evolution['total_measurements']}")
print(f"Memristivity trend: {evolution['memristivity_trend']['trend']}")
print(f"Ron drift: {evolution['resistance_trend']['ron_drift_percent']:.1f}%")
```

**Automatic degradation detection** - warnings are added if:
- Memristivity score declining (>20%)
- Switching ratio degraded (>50%)
- Resistance drift (>50%)
- Classification changed
- Lost pinched hysteresis

Tracking data saved to: `{save_directory}/device_tracking/{device_id}_history.json`

### User Feedback System

Correct classifications and learn from mistakes:

```python
from Helpers.IV_Analysis import IVSweepAnalyzer

analyzer = IVSweepAnalyzer()
results = analyzer.analyze_sweep(
    voltage, current,
    device_id="MyChip_A_1",
    save_directory="/path/to/data"
)

# Auto-classification says "memristive", but you know it's capacitive
analyzer.save_feedback(
    user_classification="capacitive",
    user_notes="Obvious capacitive hysteresis, not pinched"
)

# Find similar devices
similar = analyzer.get_similar_devices(max_results=5)
for device in similar:
    print(f"Device {device['device_id']}: {device['user_classification']} (similarity: {device['similarity']:.0%})")

# Check overall accuracy
stats = analyzer.get_feedback_accuracy_stats()
print(f"Classification accuracy: {stats['accuracy_percent']:.1f}%")
print("Common misclassifications:")
for pattern, count in stats['common_mismatches']:
    print(f"  {pattern}: {count} occurrences")
```

Feedback saved to: `{save_directory}/classification_feedback/feedback_database.json`

### Phase 2 Features Summary

**Device Tracking**:
- ✅ Automatic history logging
- ✅ Degradation detection (6 indicators)
- ✅ Trend analysis
- ✅ Evolution summaries

**User Feedback**:
- ✅ Classification corrections
- ✅ Similar device search
- ✅ Accuracy statistics
- ✅ Mismatch patterns

**Storage**:
- All data saved to user-specified directory (NOT code directory)
- JSON format for easy parsing
- Append-only logs (never overwrites)

---

## Enhanced Classification (Phase 1 + 2)

### Memristivity Score (0-100)

Continuous scoring replacing binary classification:

```python
results = quick_analyze(voltage, current)

score = results['classification']['memristivity_score']
breakdown = results['classification']['memristivity_breakdown']

print(f"Memristivity Score: {score}/100")
for feature, points in breakdown.items():
    if points > 0:
        print(f"  {feature}: {points:.1f} points")
```

**Scoring**:
- Pinched hysteresis: 30 pts
- Hysteresis quality: 20 pts
- Switching behavior: 20 pts
- Memory window: 15 pts
- Nonlinearity: 10 pts
- Polarity dependence: 5 pts

### Memory Window Quality

6 sub-metrics (0-100 each):

```python
quality = results['classification']['memory_window_quality']

print(f"Overall Quality: {quality['overall_quality_score']}/100")
print(f"State Stability: {quality['avg_stability']}/100")
print(f"Separation Ratio: {quality['separation_ratio']}")
print(f"Reproducibility: {quality['reproducibility']}/100")
```

### Hysteresis Shape Analysis

Detailed shape characterization:

```python
shape = results['classification']['hysteresis_shape']

print(f"Figure-8 Quality: {shape['figure_eight_quality']}/100")
print(f"Lobe Asymmetry: {shape['lobe_asymmetry']}")
if 'num_kinks_detected' in shape:
    print(f"Kinks Detected: {shape['num_kinks_detected']} (trapping indicators)")
```

### Warnings System

Non-blocking warnings for issues:

```python
warnings = results['classification']['warnings']

for warning in warnings:
    print(f"⚠ {warning}")

# Example warnings:
# ⚠ Voltage asymmetry detected: Set=2.10V, Reset=1.45V
# ⚠ Low SNR detected (SNR≈8.2)
# ⚠ DEVICE DEGRADATION DETECTED (over 15 measurements):
#   • Memristivity score declined 85.3 → 62.1
#   • Ron drift: 45.2% change
```

### Adaptive Thresholds

Context-aware classification:

```python
thresholds = results['classification']['adaptive_thresholds']

print(f"Voltage range: {thresholds['voltage_range']}V")
print(f"Noise floor: {thresholds['noise_floor']:.2e}A")
print(f"Confidence penalty: {thresholds['confidence_penalty']}")
```

Automatically adjusts for:
- Voltage range (scales expected hysteresis)
- Current magnitude (noise floor)
- Data resolution
- Measurement conditions

---

## Understanding the Metrics

### Resistance Metrics

**Ron (ON Resistance)**
- Low resistance state of the device
- Measured at low voltage (typically near 0V)
- Lower values indicate better ON state conductivity
- Units: Ohms (Ω)

**Roff (OFF Resistance)**
- High resistance state of the device
- Measured at low voltage (typically near 0V)
- Higher values indicate better OFF state isolation
- Units: Ohms (Ω)

**Switching Ratio (Roff/Ron)**
- Ratio of OFF to ON resistance
- Higher values indicate better memory window
- Typical memristors: 10-1000x
- Critical for memory applications

**ON/OFF Ratio**
- Same as switching ratio (Roff/Ron)
- Alternative naming convention

**Window Margin**
- Normalized resistance window: (Roff - Ron) / Ron
- Measures separation between states
- Higher values indicate better state separation

### Voltage Metrics

**Von (ON Voltage)**
- Voltage at which device switches to ON state
- Set voltage for memristors
- Units: Volts (V)

**Voff (OFF Voltage)**
- Voltage at which device switches to OFF state
- Reset voltage for memristors
- Units: Volts (V)

**Resistance at Specific Voltages (r_02V, r_05V)**
- Resistance measured at 0.2V and 0.5V
- Useful for comparing devices at standard read voltages
- Important for memory read operations

### Hysteresis Metrics

**Positive Area (ps_areas)**
- Area under I-V curve in positive voltage region
- Measures energy stored/released during positive sweep
- Units: V·A (Volt-Amperes)

**Negative Area (ng_areas)**
- Area under I-V curve in negative voltage region
- Measures energy stored/released during negative sweep
- Units: V·A (Volt-Amperes)

**Total Area (areas)**
- Sum of positive and negative areas
- Total hysteresis area
- Larger values indicate stronger hysteresis

**Normalized Area (normalized_areas)**
- Total area divided by voltage range
- Allows comparison between devices with different voltage ranges
- Dimensionless metric

### Classification Metrics

**Device Type**
- Classified type: 'memristive', 'capacitive', 'conductive', 'ohmic'
- Based on I-V characteristics and hysteresis patterns

**Classification Confidence**
- Confidence score (0-1) in the classification
- Higher values indicate more certain classification
- Values >0.7 are typically reliable

**Memristivity Score** (Enhanced Classification)
- Continuous score (0-100) indicating memristive behavior strength
- Replaces binary classification with continuous metric
- Breakdown shows contribution of each feature

### Conduction Mechanism

**Conduction Mechanism**
- Identified transport mechanism:
  - 'ohmic': Linear I-V (I = V/R)
  - 'sclc': Space Charge Limited Current (I ∝ V²)
  - 'trap_sclc': Trap-filled SCLC (I ∝ V^n, n>2)
  - 'poole_frenkel': Poole-Frenkel emission
  - 'schottky': Schottky emission
  - 'fowler_nordheim': Fowler-Nordheim tunneling

**Model R²**
- Goodness of fit for conduction model (0-1)
- Higher values indicate better fit
- R² > 0.95 typically indicates good fit

### Performance Metrics

**Retention Score**
- State retention quality (0-1)
- Higher values indicate better state stability
- Based on resistance drift and state consistency

**Endurance Score**
- Cycle-to-cycle consistency (0-1)
- Higher values indicate better reproducibility
- Based on variability across multiple cycles

**Rectification Ratio**
- I(+V) / I(-V) ratio
- Measures device asymmetry
- Values >1 indicate rectifying behavior

**Nonlinearity Factor**
- Degree of I-V nonlinearity
- Higher values indicate more nonlinear behavior
- Important for memristor applications

**Asymmetry Factor**
- Device asymmetry metric
- Measures difference between positive and negative sweeps
- Higher values indicate more asymmetric behavior

**Power Consumption**
- Average power per cycle
- Units: Watts (W)
- Important for energy-efficient applications

**Energy per Switch**
- Energy required for switching operation
- Units: Joules (J)
- Critical for low-power applications

### Research Diagnostics (Research Level Only)

**Switching Polarity**
- 'bipolar': Requires opposite polarity for set/reset
- 'unipolar': Same polarity for set/reset
- 'unknown': Cannot be determined

**NDR Index**
- Negative Differential Resistance index
- Fraction of points with dI/dV < 0
- Higher values indicate NDR behavior

**Hysteresis Direction**
- 'clockwise': Clockwise hysteresis loop
- 'counter_clockwise': Counter-clockwise loop
- 'none': No hysteresis

**Kink Voltage**
- Estimated trap-filled limit voltage
- Voltage where trap-filled SCLC transitions occur
- Units: Volts (V)

**Loop Similarity Score**
- Correlation between different measurement loops
- Higher values indicate better reproducibility
- Range: 0-1

**Pinch Offset**
- Current magnitude near V≈0
- Measures how "pinched" the hysteresis is
- Lower values indicate better pinching

**Noise Floor**
- Standard deviation of current at low voltages
- Measures measurement noise level
- Units: Amperes (A)

---

## All Available Metrics

```python
results = quick_analyze(voltage, current, device_id="test", save_directory="./data")

# Device info
results['device_info']['name']
results['device_info']['measurement_type']
results['device_info']['num_loops']

# Classification (core + enhanced)
results['classification']['device_type']  # memristive/capacitive/conductive/ohmic
results['classification']['confidence']
results['classification']['memristivity_score']  # 0-100 (Phase 1)
results['classification']['memory_window_quality']  # {...} (Phase 1)
results['classification']['hysteresis_shape']  # {...} (Phase 1)
results['classification']['warnings']  # [...] (Phase 1)

# Resistance
results['resistance_metrics']['ron_mean']
results['resistance_metrics']['roff_mean']
results['resistance_metrics']['switching_ratio_mean']
results['resistance_metrics']['on_off_ratio_mean']

# Voltage
results['voltage_metrics']['von_mean']
results['voltage_metrics']['voff_mean']
results['voltage_metrics']['max_voltage']

# Hysteresis
results['hysteresis_metrics']['normalized_area_mean']
results['hysteresis_metrics']['has_hysteresis']
results['hysteresis_metrics']['pinched_hysteresis']

# Performance
results['performance_metrics']['retention_score']
results['performance_metrics']['endurance_score']
results['performance_metrics']['power_consumption_mean']

# Tracking (Phase 2)
analyzer.get_device_evolution_summary()
analyzer.get_similar_devices()
analyzer.get_feedback_accuracy_stats()
```

---

## API Reference

### `quick_analyze()`
Simplest one-line analysis.

**Parameters**:
- `voltage`, `current` (required): Data arrays
- `time` (optional): Time data for pulse measurements
- `metadata` (optional): Dict with LED state, temperature, etc.
- `analysis_level` (default='full'): 'basic'/'classification'/'full'/'research'
- `device_id` (optional): Unique device ID for tracking (Phase 2)
- `cycle_number` (optional): Measurement number (Phase 2)
- `save_directory` (optional): Where to save tracking data (Phase 2)

**Returns**: Complete analysis dictionary

### `IVSweepAnalyzer`
Full-featured analyzer class.

**Methods**:
- `analyze_sweep()`: Run analysis
- `get_device_evolution_summary()`: Get tracking data (Phase 2)
- `save_feedback(user_class, notes)`: Save correction (Phase 2)
- `get_similar_devices(max_results)`: Find similar devices (Phase 2)
- `get_feedback_accuracy_stats()`: Get accuracy stats (Phase 2)

---

## File Structure

```
data_directory/
├── device_tracking/              # Phase 2: Device history
│   ├── MyChip_A_1_history.json
│   ├── MyChip_A_2_history.json
│   └── ...
├── classification_feedback/       # Phase 2: User corrections
│   └── feedback_database.json
└── sweep_analysis/                # Phase 1: Analysis results
    ├── sweep_001_analysis.txt
    ├── sweep_002_analysis.txt
    └── ...
```

**Important**: All data saved to user-specified directory (NOT code directory).

