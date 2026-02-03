---
name: Enhanced Sample Analysis - DC Endurance & Plot Improvements
overview: Add DC endurance analysis, enhance IV dashboard to show full sweep with arrows, add resistance annotations, and track on/off ratio evolution. All integrated into existing file structure without GridSpec.
todos:
  - id: fix_iv_average_full_sweep
    content: Modify Helpers/plotting_core/iv_grid.py _plot_avg_with_arrows() to process full sweep instead of just first half - remove first-sweep detection logic
    status: completed
  - id: add_resistance_annotations
    content: Add _add_resistance_annotations() method to Helpers/plotting_core/unified_plotter.py and integrate into plot_basic() and plot_iv_dashboard()
    status: completed
  - id: create_dc_endurance_analyzer
    content: Create Helpers/Analysis/aggregators/dc_endurance_analyzer.py with DCEnduranceAnalyzer class based on Pandas_test code (extract current at voltages, plot current vs cycle, export CSV)
    status: completed
  - id: integrate_dc_endurance
    content: Modify comprehensive_analyzer.py to detect endurance data (≥10 sweeps) and call DCEnduranceAnalyzer, saving to sample_analysis/plots/endurance/{code_name}/
    status: completed
    dependencies:
      - create_dc_endurance_analyzer
  - id: add_onoff_evolution_plot
    content: Add plot_onoff_ratio_evolution() method to SampleAnalysisOrchestrator in sample_analyzer.py as plot 26
    status: completed
  - id: wire_sclc_commented
    content: Add SCLC plot generation code to comprehensive_analyzer.py but keep it commented out with clear notes explaining it is wired but not used
    status: completed
  - id: test_integration
    content: "Test complete workflow: verify IV dashboard shows full sweep, DC endurance generates for ≥10 sweeps, annotations appear, file structure matches existing patterns"
    status: completed
    dependencies:
      - fix_iv_average_full_sweep
      - add_resistance_annotations
      - integrate_dc_endurance
      - add_onoff_evolution_plot
---

# Enhanced Sample Analysis - DC Endurance & Plot Improvements

## Overview

Integrate DC endurance analysis from Pandas_test repository and enhance existing plots. Fix IV average to show full sweep (not just first half), add resistance annotations, and track on/off ratio evolution. All integrated into existing file structure.

## Analysis of Current State

### Existing IV Dashboard (`Helpers/plotting_core/iv_grid.py`):

- ✅ Has `_plot_avg_with_arrows()` but only processes first sweep (half sweep)
- ✅ 2x2 grid layout: Linear IV, Log IV, Averaged IV with arrows, Current vs Time
- ✅ Saves to device-level: `{sample_dir}/{section}/{device_num}/images/`

### Existing File Structure:

- Device plots: `{sample_dir}/{section}/{device_num}/images/`
- Sample plots: `{sample_dir}/sample_analysis/plots/{code_name}/`
- Origin data: `{sample_dir}/sample_analysis/plots/data_origin_formatted/{code_name}/`
- Analysis data: `{sample_dir}/sample_analysis/analysis/device_tracking/`

## Implementation Plan

### Phase 1: Fix IV Average to Show Full Sweep

**File**: `Helpers/plotting_core/iv_grid.py` (MODIFY)

**Current Issue**: `_plot_avg_with_arrows()` only processes first sweep (lines 136-194 detect first sweep and stop)

**Fix**:

1. Remove first-sweep detection logic (lines 144-184)
2. Process entire voltage/current array
3. Average all data points (not just first sweep)
4. Add arrows showing direction for complete sweep cycle

**Changes**:

```python
@staticmethod
def _plot_avg_with_arrows(ax, v: np.ndarray, i: np.ndarray, num_points: int, label: str):
    """
    Plot averaged IV with direction arrows for the FULL sweep.
    Processes entire voltage/current array, not just first half.
    """
    if len(v) < 2:
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("Current (A)")
        ax.grid(True, alpha=0.3)
        return
    
    # Process ENTIRE sweep (removed first-sweep detection)
    # Average all data points
    if num_points < 2:
        num_points = 2
    step = max(len(v) // num_points, 1)
    avg_v = [np.mean(v[j : j + step]) for j in range(0, len(v), step)]
    avg_i = [np.mean(i[j : j + step]) for j in range(0, len(i), step)]

    ax.scatter(avg_v, avg_i, c="b", marker="o", s=10, label=label or "Averaged (full sweep)")
    for k in range(1, len(avg_v)):
        ax.annotate(
            "",
            xy=(avg_v[k], avg_i[k]),
            xytext=(avg_v[k - 1], avg_i[k - 1]),
            arrowprops=dict(arrowstyle="->", color="red", lw=1),
        )
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current (A)")
    ax.grid(True, alpha=0.3)
    if label:
        ax.legend()
```

### Phase 2: Add Resistance Annotations to IV Plots

**File**: `Helpers/plotting_core/unified_plotter.py` (MODIFY)

Add annotations showing Ron, Roff, switching ratio on IV and Log IV plots:

1. **New Method**: `_add_resistance_annotations()`

   - Extract Ron, Roff, switching ratio from analysis data
   - Position Ron annotation at positive voltage region
   - Position Roff annotation at negative voltage region
   - Add switching ratio in corner
   - Style: bbox with background, positioned to avoid overlap

2. **Modify**: `plot_basic()` and `plot_iv_dashboard()`

   - Add optional `analysis_data` parameter
   - Call `_add_resistance_annotations()` when analysis data available
   - Pass through from `plot_conditional()` which already has analysis results

3. **Integration**: 

   - Used automatically when analysis data is available
   - Works in both real-time GUI and sample analysis

### Phase 3: DC Endurance Analyzer

**File**: `Helpers/Analysis/aggregators/dc_endurance_analyzer.py` (NEW)

Based on `Pandas_test/memristors/analysis.py` lines 478-608:

1. **Class**: `DCEnduranceAnalyzer`

   - Extract current values at specific voltages (0.1V, 0.15V, 0.2V) across cycles
   - Handle both positive and negative voltage sweeps
   - Identify ON/OFF states from forward/reverse sweeps
   - Generate plots and CSV exports

2. **Method**: `extract_current_at_voltages()`

   - Input: split voltage/current data (one array per cycle)
   - Extract current at 0.1V, 0.15V, 0.2V (and negative equivalents)
   - Identify forward (OFF) and reverse (ON) currents
   - Return structured dict: `{voltage: {cycle: [forward_current, reverse_current]}}`

3. **Method**: `plot_current_vs_cycle()`

   - Create 2-panel plot per voltage (positive and negative)
   - Show forward (OFF) and reverse (ON) currents vs cycle
   - Style matching Pandas_test: markers ('o'), grid, legend
   - Save individual plots

4. **Method**: `plot_endurance_summary()`

   - Create comprehensive multi-panel figure (num_voltages x 2)
   - All voltages in one figure for comparison
   - Style: figsize=(12, 4*num_voltages)

5. **Method**: `export_to_csv()`

   - Export current values to CSV
   - Columns: Cycle, Current_Forward_(OFF)_0.1V, Current_Reverse_(ON)_0.1V, etc.
   - Save to appropriate directory

6. **File Structure**:

   - Plots: `{sample_dir}/sample_analysis/plots/endurance/{code_name}/` (if code_name exists)
   - OR: `{sample_dir}/sample_analysis/plots/endurance/` (if no code_name filter)
   - CSV: `{sample_dir}/sample_analysis/plots/endurance/{code_name}/Data/` (matching existing pattern)
   - Individual plots: `{file_name}_plot_{voltage}V.png`
   - Summary plot: `{file_name}_final_plot.png`

### Phase 4: Integrate DC Endurance into Comprehensive Analyzer

**File**: `Helpers/Analysis/aggregators/comprehensive_analyzer.py` (MODIFY)

1. **Detection**:

   - In `plot_device_combined_sweeps()` or new method
   - Check if device has ≥10 sweeps (endurance threshold)
   - Detect by counting .txt files or checking sweep numbers

2. **Processing**:

   - Split sweeps into individual cycles
   - Call `DCEnduranceAnalyzer` for devices with endurance data
   - Save plots to `{sample_dir}/sample_analysis/plots/endurance/{code_name}/`
   - Save CSV to `{sample_dir}/sample_analysis/plots/endurance/{code_name}/Data/`

3. **Integration Point**:

   - Add to `run_comprehensive_analysis()` after device-level plots
   - Or integrate into `plot_device_combined_sweeps()` for each device

### Phase 5: On/Off Ratio Evolution Plot

**File**: `Helpers/Analysis/aggregators/sample_analyzer.py` (MODIFY)

Add new plot type to track on/off ratio changes over time:

1. **New Method**: `plot_onoff_ratio_evolution()`

   - Load device tracking data for all devices
   - Extract on/off ratios from each measurement in device history
   - Group by device ID
   - Plot: X-axis = measurement number/timestamp, Y-axis = on/off ratio
   - One line per device (or grouped by section)
   - Add trend indicators (improving/stable/degrading)
   - Log scale for Y-axis

2. **Integration**:

   - Add to `generate_all_plots()` as plot 26
   - Save as `26_onoff_ratio_evolution.png`
   - Only generate if devices have multiple measurements

3. **File Location**:

   - `{sample_dir}/sample_analysis/plots/{code_name}/26_onoff_ratio_evolution.png`
   - Matches existing plot numbering scheme

### Phase 6: SCLC Wiring (Commented Out)

**File**: `Helpers/Analysis/aggregators/comprehensive_analyzer.py` (MODIFY)

Add SCLC plot generation but keep it commented:

```python
# NOTE: SCLC plots are available but commented out per user request
# Uncomment when ready to use
# from plotting import SCLCFitPlotter
# 
# if device_is_memristive:
#     sclc_plotter = SCLCFitPlotter(save_dir=images_dir)
#     sclc_plotter.plot_sclc_fit(
#         voltage=voltage,
#         current=current,
#         device_label=device_id,
#         save_name=f"{device_id}_sclc_fit.png"
#     )
```

## File Structure Summary

### DC Endurance Output:

```
{sample_dir}/sample_analysis/plots/endurance/
├── {code_name}/                    # If code_name filter exists
│   ├── Data/
│   │   └── {file_name}_current_values_{voltage}V.csv
│   ├── {file_name}_plot_0.1V.png
│   ├── {file_name}_plot_0.15V.png
│   ├── {file_name}_plot_0.2V.png
│   └── {file_name}_final_plot.png
└── overall/                        # If no code_name filter
    └── (same structure)
```

### Device-Level Plots (Enhanced):

```
{sample_dir}/{section}/{device_num}/images/
├── {device_name}_iv_dashboard.png  # Now with full sweep arrows + annotations
└── (other existing plots)
```

### Sample-Level Plots (New):

```
{sample_dir}/sample_analysis/plots/{code_name}/
├── 01_memristivity_heatmap.png
├── ... (existing 25 plots)
└── 26_onoff_ratio_evolution.png   # NEW
```

## Key Implementation Details

### DC Endurance Detection:

- Check for ≥10 sweeps in device folder
- Or check if code_name contains "endurance" or "end"
- Extract cycles by splitting voltage/current arrays at sweep boundaries

### IV Average Full Sweep:

- Remove all first-sweep detection logic
- Process entire array
- Average into N points (default 12, configurable)
- Add arrows between all averaged points

### Resistance Annotations:

- Extract from analysis data: `analysis_data['resistance']['ron_mean']`, `roff_mean`, `switching_ratio_mean`
- Position annotations intelligently to avoid overlap
- Format: "Ron: 1.2e3 Ω" with appropriate units

## Testing Considerations

1. Test IV dashboard with full sweeps (should show complete cycle with arrows)
2. Test DC endurance with files containing ≥10 sweeps
3. Test DC endurance with files containing <10 sweeps (should skip)
4. Test resistance annotations with and without analysis data
5. Test on/off ratio evolution with devices having multiple measurements
6. Verify file structure matches existing patterns

## Success Criteria

- ✅ IV dashboard shows full sweep with arrows (not just first half)
- ✅ Resistance annotations appear on IV/log IV plots when analysis data available
- ✅ DC endurance plots generated for files with ≥10 sweeps
- ✅ DC endurance CSV data saved to appropriate Data/ subfolder
- ✅ On/off ratio evolution plot shows device trends over time
- ✅ All plots saved to locations matching existing file structure
- ✅ SCLC code present but commented out with clear notes
- ✅ No duplicate functionality (existing plots enhanced, not duplicated)