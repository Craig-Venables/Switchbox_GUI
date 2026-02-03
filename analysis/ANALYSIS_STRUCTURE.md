# Sample Analysis Structure & Button Mapping

## Overview

This document maps the **Sample Analysis** tab buttons in the Measurement GUI to their underlying analysis functions, explains the analysis module structure, and identifies deprecated code for potential removal.

---

## GUI Button → Function Mapping

### Location: `gui/measurement_gui/layout_builder.py` → `_create_graphing_tab()`

The **Sample Analysis** tab contains three main action buttons:

### 1. **"▶ Run Full Sample Analysis"** Button
- **GUI Location**: `gui/measurement_gui/layout_builder.py:2707-2720`
- **Command**: `gui.run_full_sample_analysis`
- **Function**: `gui/measurement_gui/main.py:2858-3007` → `run_full_sample_analysis()`

**What it does:**
1. Checks for existing analysis data in `sample_analysis/device_tracking/`
2. If no tracking data exists, runs **retroactive analysis** on raw `.txt` files:
   - Function: `_run_retroactive_analysis()` (lines 3377-3540)
   - Uses: `analysis.quick_analyze()` to generate device tracking/research data
3. Runs **comprehensive analysis**:
   - Imports: `analysis.ComprehensiveAnalyzer`
   - Calls: `comprehensive.run_comprehensive_analysis()`

**Output Location**: `{sample_dir}/sample_analysis/`

**Generated Outputs:**
- Device-level combined sweep plots (in each device's `images/` folder)
- Section-level analysis (stacked sweeps & stats)
- Sample-level analysis for each code_name (12 plot types per code_name)
- Overall sample analysis (all measurements combined)
- Origin-ready data exports

---

### 2. **"Plot Current Device Graphs"** Button
- **GUI Location**: `gui/measurement_gui/layout_builder.py:2729-2740`
- **Command**: `gui.plot_all_device_graphs`
- **Function**: `gui/measurement_gui/main.py:2522-2712` → `plot_all_device_graphs()`

**What it does:**
1. Gets current device from GUI (device letter + number)
2. Finds all `.txt` measurement files in that device's folder
3. For each file:
   - Loads data (voltage, current, time)
   - Runs: `analysis.quick_analyze()` with `analysis_level='full'`
   - Uses: `plotting.UnifiedPlotter` to generate:
     - Dashboard plots (`plot_iv_dashboard()`)
     - Conduction mechanism plots (if memristive)
     - SCLC fit plots (if memristive)

**Output Location**: `{sample_dir}/{section}/{device_num}/images/`

**Note**: This is for **retroactive plotting** of old data, separate from automatic plotting during measurements.

---

### 3. **"Plot All Sample Graphs"** Button
- **GUI Location**: `gui/measurement_gui/layout_builder.py:2743-2754`
- **Command**: `gui.plot_all_sample_graphs`
- **Function**: `gui/measurement_gui/main.py:2715-2856` → `plot_all_sample_graphs()`

**What it does:**
1. Scans entire sample directory for all device folders (`{section}/{device_num}/`)
2. For each device folder:
   - Finds all `.txt` measurement files
   - Loads data and runs: `analysis.quick_analyze()` with `analysis_level='full'`
   - Uses: `plotting.UnifiedPlotter.plot_iv_dashboard()` to generate dashboard plots

**Output Location**: `{sample_dir}/{section}/{device_num}/images/`

**Note**: This generates **device-level dashboard plots** for every device in the sample. It does NOT generate the comprehensive sample-level analysis plots (those are done by "Run Full Sample Analysis").

---

## Analysis Module Structure

### Core Modules

#### 1. **`analysis/` (aggregators)** - Sample-Level Analysis

##### `comprehensive_analyzer.py` ⭐ **MAIN ENTRY POINT**
- **Class**: `ComprehensiveAnalyzer`
- **Purpose**: One-stop orchestrator for all analysis types
- **Called by**: `run_full_sample_analysis()` button
- **Key Methods**:
  - `discover_all_code_names()` - Scans files to find all test types (code_names)
  - `get_valid_code_names()` - Filters to code_names in `test_configurations.json`
  - `plot_device_combined_sweeps()` - Device-level plots using `sweep_combinations` from config
  - `run_comprehensive_analysis()` - Main orchestrator that:
    1. Discovers code_names
    2. Generates device-level combined plots
    3. Runs section-level analysis
    4. Runs sample-level analysis for each code_name
    5. Runs overall sample analysis (no filter)

**Where to add new analysis**: Add new methods to this class, or call them from `run_comprehensive_analysis()`

---

##### `sample_analyzer.py` - Sample-Level Statistics & Plots
- **Class**: `SampleAnalysisOrchestrator`
- **Purpose**: Generates 12 advanced plot types for entire samples (100+ devices)
- **Called by**: `ComprehensiveAnalyzer.run_comprehensive_analysis()`
- **Key Methods**:
  - `load_all_devices()` - Loads device tracking data from `sample_analysis/device_tracking/`
  - `generate_all_plots()` - Generates 12 plot types:
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
  - `export_origin_data()` - Exports Origin-ready data files

**Where to add new plots**: Add new plot methods (e.g., `plot_new_analysis()`) and call them in `generate_all_plots()`

**Output**: `{sample_dir}/sample_analysis/plots/{code_name}/` or `plots/overall/`

---

##### `section_analyzer.py` - Section-Level Analysis
- **Class**: `SectionAnalyzer`
- **Purpose**: Analyzes sections (letter folders) with stacked sweep plots and statistics
- **Called by**: `ComprehensiveAnalyzer.run_comprehensive_analysis()`
- **Key Methods**:
  - `analyze_section_sweeps()` - Generates stacked plots (first/second/third sweeps) and stats
- **Uses**: `analysis.single_file_metrics.analyze_single_file` for individual file analysis

**Output**: `{sample_dir}/sample_analysis/sections/{section}/`

---

##### `migrate_folder_structure.py` - Migration Utility
- **Purpose**: Migrates old folder structure to new unified `sample_analysis/` structure
- **Status**: Utility script, not called by GUI buttons
- **Usage**: Run manually or import `migrate_sample()` function

---

#### 2. **`analysis/` (API and core)** - Single File Analysis

##### `iv_sweep_analyzer.py` - Fast Analysis Wrapper
- **Functions**:
  - `quick_analyze()` ⭐ **MOST USED** - Quick analysis with metadata support
  - `analyze_sweep()` - Analysis from file path
- **Class**: `IVSweepAnalyzer` - Fast data extraction wrapper

**Used by**:
- `run_full_sample_analysis()` → `_run_retroactive_analysis()` (for retroactive analysis)
- `plot_all_device_graphs()` (for plotting)
- `plot_all_sample_graphs()` (for plotting)
- All measurement functions during live measurements

---

##### `single_file_metrics.py` - Core Analysis Engine
- **Class**: `analyze_single_file` (4505 lines - very comprehensive)
- **Purpose**: Deep analysis engine with classification, research-level metrics, etc.
- **Used by**: 
  - `section_analyzer.py` (imported as `AnalyzeSingleFile`)
  - `iv_sweep_analyzer.py` (wraps this)

**Where to add new metrics**: Add methods to `analyze_single_file` class

---

##### `iv_sweep_llm_analyzer.py` - LLM Insights (Optional)
- **Class**: `IVSweepLLMAnalyzer`
- **Purpose**: Adds LLM-powered insights to analysis
- **Status**: Optional, slower, not used by GUI buttons

---

#### 3. **`plotting/`** - Plotting Utilities
- **Main Class**: `UnifiedPlotter`
- **Used by**: 
  - `plot_all_device_graphs()` - For device-level plots
  - `plot_all_sample_graphs()` - For device-level plots
- **Key Methods**:
  - `plot_iv_dashboard()` - Dashboard plots
  - Conduction mechanism plots
  - SCLC fit plots

---

## Data Flow

### Full Sample Analysis Flow

```
User clicks "Run Full Sample Analysis"
    ↓
run_full_sample_analysis()
    ↓
Check for device_tracking data
    ↓
If missing: _run_retroactive_analysis()
    ├─> Scans raw .txt files
    ├─> quick_analyze() for each file
    └─> Saves to sample_analysis/device_tracking/ and device_research/
    ↓
ComprehensiveAnalyzer.run_comprehensive_analysis()
    ├─> Discover code_names from files
    ├─> For each device: plot_device_combined_sweeps()
    ├─> For each section: SectionAnalyzer.analyze_section_sweeps()
    ├─> For each code_name: SampleAnalysisOrchestrator
    │   ├─> load_all_devices()
    │   ├─> generate_all_plots() (12 plot types)
    │   └─> export_origin_data()
    └─> Overall analysis (no code_name filter)
```

### Plotting Buttons Flow

```
User clicks "Plot Current Device Graphs" or "Plot All Sample Graphs"
    ↓
plot_all_device_graphs() or plot_all_sample_graphs()
    ↓
For each .txt file:
    ├─> Load data (voltage, current, time)
    ├─> quick_analyze(analysis_level='full')
    └─> UnifiedPlotter.plot_iv_dashboard()
```

---

## Where to Add New Analysis

### Adding New Sample-Level Analysis

**Option 1: Add to ComprehensiveAnalyzer** (Recommended for orchestration)
- File: `Helpers/Sample_Analysis/comprehensive_analyzer.py`
- Add new method to `ComprehensiveAnalyzer` class
- Call it from `run_comprehensive_analysis()` method

**Option 2: Add to SampleAnalysisOrchestrator** (For new plot types)
- File: `Helpers/Sample_Analysis/sample_analyzer.py`
- Add new plot method (e.g., `plot_my_new_analysis()`)
- Add it to `generate_all_plots()` method (currently has 12 plots)

**Option 3: Add to SectionAnalyzer** (For section-level analysis)
- File: `Helpers/Sample_Analysis/section_analyzer.py`
- Add new method to `SectionAnalyzer` class
- Call it from `ComprehensiveAnalyzer.run_comprehensive_analysis()`

### Adding New Single-File Metrics

- File: `Helpers/IV_Analysis/single_file_metrics.py`
- Add new methods to `analyze_single_file` class
- These will automatically be available via `quick_analyze()` wrapper

### Adding New Plot Types

- File: `Helpers/plotting_core/unified_plotter.py`
- Add new plot methods to `UnifiedPlotter` class
- These can be called from plotting buttons or analysis functions

---

## Deprecated/Unused Code

### ⚠️ **Potentially Deprecated - Review for Removal**

#### 1. **`archive/Switchbox_Data_Analysis_and_Graphing/`** (formerly `Helpers/Switchbox_Data_Analysis_and_Graphing - Copy/`)
- **Status**: Archived (Phase 1 refactoring)
- **Location**: Moved to `archive/Switchbox_Data_Analysis_and_Graphing/`
- **Note**: Functionality superseded by `analysis`, `analysis`, and
  `plotting`. See `archive/README.md` for details.

---

#### 2. **`Helpers/Maps_Create/old_legacy/`**
- **Status**: Marked as "old_legacy"
- **Recommendation**: **Review and likely remove** if not needed

---

#### 3. **`Helpers/ITO_Analysis/old/`**
- **Status**: Contains old analysis results
- **Recommendation**: **Keep if needed for reference**, otherwise archive/remove

---

#### 4. **`Helpers/Sample_Analysis/migrate_folder_structure.py`**
- **Status**: Migration utility script
- **Recommendation**: **Keep** - Useful for migrating old data structures, but not called by GUI

---

### ✅ **Currently Used Code**

All files in:
- `Helpers/Sample_Analysis/` (except `migrate_folder_structure.py` which is utility)
- `Helpers/IV_Analysis/` (all files are used)
- `Helpers/plotting_core/` (used by plotting buttons)

---

## File Dependencies

### Sample_Analysis Dependencies
```
comprehensive_analyzer.py
    ├─> section_analyzer.py
    │   └─> analysis.single_file_metrics.analyze_single_file
    └─> sample_analyzer.py
        └─> (reads from sample_analysis/device_tracking/ and device_research/)
```

### IV_Analysis Dependencies
```
iv_sweep_analyzer.py
    └─> single_file_metrics.py (analyze_single_file class)

iv_sweep_llm_analyzer.py
    └─> iv_sweep_analyzer.py
```

### GUI Dependencies
```
gui/measurement_gui/main.py
    ├─> analysis.quick_analyze (for retroactive analysis & plotting)
    └─> analysis.ComprehensiveAnalyzer

gui/measurement_gui/layout_builder.py
    └─> (creates buttons that call main.py methods)
```

---

## Summary

### Quick Reference: Button → Analysis

| Button | Function | Main Analysis Module | Output Location |
|--------|----------|---------------------|-----------------|
| **Run Full Sample Analysis** | `run_full_sample_analysis()` | `ComprehensiveAnalyzer` | `sample_analysis/` |
| **Plot Current Device Graphs** | `plot_all_device_graphs()` | `UnifiedPlotter` + `quick_analyze()` | `{section}/{device}/images/` |
| **Plot All Sample Graphs** | `plot_all_sample_graphs()` | `UnifiedPlotter` + `quick_analyze()` | `{section}/{device}/images/` |

### Key Files for Adding New Analysis

1. **Sample-level plots**: `Helpers/Sample_Analysis/sample_analyzer.py` → `generate_all_plots()`
2. **Orchestration logic**: `Helpers/Sample_Analysis/comprehensive_analyzer.py` → `run_comprehensive_analysis()`
3. **Single-file metrics**: `Helpers/IV_Analysis/single_file_metrics.py` → `analyze_single_file` class
4. **Device-level plots**: `Helpers/plotting_core/unified_plotter.py` → `UnifiedPlotter` class

---

## Notes

- The `sample_analysis/` folder structure is unified and contains:
  - `device_tracking/` - Device history JSON files
  - `device_research/` - Research-level analysis JSON files
  - `plots/` - All generated plots (organized by code_name or "overall")
  - `device_summaries/` - Device summary files
  - `analysis/sweeps/` - Individual sweep analysis files

- Code names (test types) are extracted from filenames (position 6 after splitting by '-')
- Analysis can be filtered by code_name or run on all measurements (overall)

