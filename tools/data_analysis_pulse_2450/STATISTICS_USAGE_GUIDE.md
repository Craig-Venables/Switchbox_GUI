# Statistics Feature - Usage Guide

## Overview

The Statistics Panel provides comprehensive statistical analysis for TSP measurement data, including:
- Basic statistics (mean, median, std dev, min, max, range)
- Change analysis (initial value, final value, total change, percent change)
- **Relaxation time fitting** (exponential decay/growth with R² goodness-of-fit)
- HRS/LRS detection for switching/endurance tests
- Switching window and On/Off ratio calculations

## Quick Start

### 1. Load and Plot Data
- Browse to your data folder
- Select files to analyze
- Click "📊 Plot Selected Files"

### 2. Calculate Statistics
- Click the **"📊 Calculate Statistics"** button in the Statistics panel
- The tool automatically:
  - Detects test types (relaxation, endurance, etc.)
  - Applies appropriate statistical methods
  - Fits exponential curves for relaxation tests
  - Detects HRS/LRS states for switching tests

### 3. Display Statistics on Graph
1. Check the **"Show Stats on Graph"** checkbox
2. Select which statistics to display using the checkboxes:
   - **Basic:** Mean, Median, Std Dev, Min, Max, Range
   - **Change:** Initial Value, Final Value, Total Change (ΔY), Percent Change (%)
   - **Relaxation:** Tau (Relaxation Time), Tau R² (fit quality)
   - **Switching:** HRS Mean, LRS Mean, Switching Window, On/Off Ratio
3. Choose position from dropdown:
   - Upper Right (default)
   - Upper Left
   - Lower Right
   - Lower Left
   - Center Right
   - Center Left
   - Upper Center
   - Lower Center

### 4. Export Statistics
- Click **"💾 Export Stats to CSV"** to save all statistics
- Opens in Excel or any spreadsheet software
- Includes all datasets and all calculated statistics

## Relaxation Time Fitting

### What is Relaxation Time?

Relaxation time (τ, tau) is the time constant for exponential decay or growth processes. The tool fits your data to:

```
y(t) = y∞ + (y₀ - y∞) × exp(-t/τ)
```

Where:
- **y₀** = Initial value (at t=0)
- **y∞** = Final equilibrium value (at t→∞)
- **τ** = Relaxation time constant
- **R²** = Coefficient of determination (fit quality, 0-1)

### Interpretation

- **Tau (τ)**: Time for ~63% of the change to occur
  - Larger τ = Slower relaxation
  - Smaller τ = Faster relaxation
- **R² value**: How well the fit matches your data
  - R² > 0.95: Excellent fit
  - R² > 0.90: Good fit
  - R² < 0.90: Poor fit (may not be exponential)

### Automatic Detection

The tool automatically performs relaxation time fitting when:
- Test type name contains "relaxation"
- You click "Calculate Statistics"

### Tips for Relaxation Time

1. **Ensure good data quality**: Noisy data produces poor fits
2. **Check R² value**: Low R² means data may not be exponential
3. **Use data cropping**: Remove initial transients or late-stage noise
4. **Compare tau values**: Useful for comparing different conditions/samples

## HRS/LRS Detection

For endurance, potentiation, depression, and switching tests:

- **HRS (High Resistance State)**: Resistance values above median
- **LRS (Low Resistance State)**: Resistance values below median
- **Switching Window**: HRS Mean - LRS Mean (larger = better)
- **On/Off Ratio**: HRS Mean / LRS Mean (higher = better)

## Advanced Usage

### Combining with Data Processing

Calculate statistics **after** applying:
1. **Crop**: Focus on specific time ranges
2. **Normalize**: Compare different scales
3. **Offset**: Statistics calculated on offset data

**Important:** Recalculate statistics after changing data processing settings!

### Multi-Dataset Comparison

When multiple datasets are visible:
- Statistics are calculated for each dataset separately
- Stats box shows all datasets (if space allows)
- Export CSV for easy comparison in spreadsheet

### Positioning the Stats Box

If the stats box overlaps your data:
1. Change position from dropdown (try different corners)
2. Temporarily hide legend
3. Adjust axis ranges to create space
4. Export to PNG and add stats in image editor

## Statistical Methods

### Basic Statistics
- **Mean**: Average value (Σy/n)
- **Median**: Middle value (50th percentile)
- **Std Dev**: Standard deviation (√(Σ(y-mean)²/(n-1)))
- **Min/Max**: Minimum and maximum values
- **Range**: Max - Min (peak-to-peak)

### Change Statistics
- **Initial Value**: First data point (y[0])
- **Final Value**: Last data point (y[-1])
- **Total Change**: Final - Initial (ΔY)
- **Percent Change**: (ΔY / Initial) × 100%

### Relaxation Time
- **Method**: Nonlinear least-squares curve fitting (scipy.optimize.curve_fit)
- **Function**: Exponential decay/growth
- **Initial guess**: Estimated from 63% point
- **Bounds**: Prevents unrealistic parameter values
- **Error estimation**: Standard error from covariance matrix

### HRS/LRS Detection
- **Threshold**: Median (50th percentile)
- **HRS**: All values > threshold
- **LRS**: All values ≤ threshold
- **Stats**: Mean and standard deviation for each state

## Troubleshooting

### "No Data" Error
- **Problem**: No datasets loaded
- **Solution**: Select and plot files first

### "No Visible Data" Error
- **Problem**: All datasets are hidden
- **Solution**: Double-click datasets in list to show them

### "No Statistics Calculated" (Export)
- **Problem**: Haven't calculated statistics yet
- **Solution**: Click "Calculate Statistics" button first

### Relaxation Time = NaN
- **Possible causes**:
  1. Too few data points (need at least 4)
  2. Data doesn't follow exponential decay/growth
  3. Fit failed to converge
- **Solutions**:
  - Check your data quality
  - Try cropping to remove non-exponential regions
  - Verify this is actually a relaxation process

### HRS/LRS = NaN
- **Problem**: No values above or below threshold
- **Solution**: This test may not have switching behavior

### Stats Box Not Visible
- **Check**:
  1. "Show Stats on Graph" is checked
  2. At least one stat checkbox is selected
  3. Statistics have been calculated
  4. Stats box isn't positioned off-screen

## Example Workflows

### Workflow 1: Relaxation Time Analysis
```
1. Load relaxation test data
2. Plot → Calculate Statistics
3. Check "Tau (Relaxation Time)" and "Tau R²"
4. Enable "Show Stats on Graph"
5. Compare tau values across samples
6. Export stats to CSV for plotting
```

### Workflow 2: Endurance Test Analysis
```
1. Load endurance test data
2. Calculate Statistics
3. Check "HRS Mean", "LRS Mean", "Switching Window"
4. Enable stats display
5. Look for degradation (decreasing window over time)
6. Export for tracking over multiple runs
```

### Workflow 3: Multi-Sample Comparison
```
1. Load multiple samples (same test type)
2. Plot all → Calculate Statistics
3. Select relevant stats for comparison
4. Position stats box to not overlap data
5. Export plot (with stats) to PNG
6. Export stats to CSV for detailed comparison
```

## Tips & Best Practices

1. **Calculate stats on final data**: Apply all processing first, then calculate
2. **Use CSV export**: Better for detailed analysis than reading from graph
3. **Check R² for fits**: Low R² = poor fit = unreliable tau
4. **Crop wisely**: Remove transients but keep exponential region
5. **Position strategically**: Move stats box to empty regions of plot
6. **Select only needed stats**: Too many stats = cluttered display
7. **Compare similar tests**: Statistics most meaningful when comparing same test type
8. **Document processing**: Note crop/normalize settings when exporting

## Keyboard Shortcuts

- **Ctrl+S**: Save plot (stats included if visible)
- *More shortcuts coming in future updates*

---

**Need Help?**
- Click the **"?"** button next to Statistics header
- Check [README.md](README.md) for general usage
- See [TODO_REMAINING_FEATURES.md](TODO_REMAINING_FEATURES.md) for planned enhancements

**Last Updated:** 2025-11-01  
**Version:** 1.1



