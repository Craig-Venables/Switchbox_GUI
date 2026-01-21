---
name: Conditional plotting for measurement types
overview: "Modify the graph plotting system to generate measurement-type-specific plots: IV dashboard (default), Endurance plots (cycle vs resistance, cycle vs ON/OFF ratio), and Retention plots (log-log and linear time vs current, time vs resistance)."
todos:
  - id: "1"
    content: Add measurement_type parameter to _plot_measurement_in_background method
    status: completed
  - id: "2"
    content: Update run_custom_measurement to pass measurement_type to plotting function
    status: completed
  - id: "3"
    content: Create plot_endurance_analysis function in UnifiedPlotter (or new EndurancePlotter class)
    status: completed
  - id: "4"
    content: Create plot_retention_analysis function in UnifiedPlotter (or new RetentionPlotter class)
    status: completed
  - id: "5"
    content: Implement cycle detection logic for endurance data parsing
    status: completed
  - id: "6"
    content: "Implement endurance plotting: Cycle vs Resistance (SET/RESET) and Cycle vs ON/OFF Ratio"
    status: completed
  - id: "7"
    content: "Implement retention plotting: Log-log Time vs Current, Linear Time vs Current, Time vs Resistance"
    status: completed
  - id: "8"
    content: Update conditional logic in _plot_measurement_in_background to call appropriate plotting functions
    status: completed
---

# Conditional Plotting Based on Measurement Type

## Overview

Currently, `_plot_measurement_in_background` always plots IV dashboard regardless of measurement type. We need to:

1. Detect measurement type (IV, Endurance, Retention)
2. Generate appropriate plots for each type
3. Save plots to the Graphs folder with appropriate filenames

## Files to Modify

### 1. `gui/measurement_gui/main.py`

- **`_plot_measurement_in_background` method (line ~1679)**: Add `measurement_type` parameter and conditional plotting logic
- **`run_custom_measurement` method (line ~7908)**: Pass `measurement_type` to `_plot_measurement_in_background`

### 2. `Helpers/plotting_core/unified_plotter.py` (or create new plotter)

- Add methods for endurance and retention plotting:
  - `plot_endurance_analysis()`: Cycle vs Resistance (SET/RESET), Cycle vs ON/OFF Ratio
  - `plot_retention_analysis()`: Log-log Time vs Current, Linear Time vs Current, Time vs Resistance

## Implementation Details

### Measurement Type Detection

- In `run_custom_measurement`, `measurement_type` is already extracted from params (line 7424-7437)
- Pass this to `_plot_measurement_in_background` as a new parameter

### Endurance Plotting

**Data Structure**: Endurance measurements save `Time(s) Current(A) Voltage(V)` with pattern:

- SET_pulse → SET_read → RESET_pulse → RESET_read (repeated for cycles)
- Read measurements occur at `read_voltage` (typically 0.2V)

**Plots to Generate**:

1. **Cycle vs Resistance (SET and RESET)**: 

   - Extract cycles by detecting read measurements (voltage ≈ read_voltage)
   - Separate SET reads (even indices) and RESET reads (odd indices)
   - Calculate resistance: R = V_read / I_read
   - Plot cycle number vs resistance for both states

2. **Cycle vs ON/OFF Ratio**:

   - Calculate ratio: I_ON / I_OFF for each cycle
   - Plot cycle number vs ratio

**Challenges**: Need to parse the data pattern to identify cycles. May need to use params (read_voltage, cycles) or detect pattern from data.

### Retention Plotting

**Data Structure**: Retention measurements save `Time(s) Current(A) Voltage(V)` with pattern:

- SET pulse → multiple reads at increasing time intervals

**Plots to Generate**:

1. **Log-Log: Time vs Current**: Log scale on both axes
2. **Linear: Time vs Current**: Linear scale
3. **Time vs Resistance**: Calculate R = V_read / I_read, plot vs time

### Plotting Function Structure

```python
def _plot_measurement_in_background(
    self,
    voltage,
    current,
    timestamps,
    save_dir: str,
    device_name: str,
    sweep_number: int,
    is_memristive: Optional[bool] = None,
    filename: Optional[str] = None,
    measurement_type: str = "IV"  # NEW parameter
) -> None:
    # Conditional plotting based on measurement_type
    if measurement_type == "Endurance":
        # Plot endurance-specific graphs
    elif measurement_type == "Retention":
        # Plot retention-specific graphs
    else:  # IV or default
        # Plot IV dashboard (current behavior)
```

## New Plotting Functions Needed

### In `Helpers/plotting_core/unified_plotter.py`:

- `plot_endurance_analysis(voltage, current, timestamps, read_voltage, cycles, ...)`
- `plot_retention_analysis(voltage, current, timestamps, ...)`

Or create new plotter classes:

- `EndurancePlotter` in `Helpers/plotting_core/endurance.py`
- `RetentionPlotter` in `Helpers/plotting_core/retention.py`

## Data Parsing Strategy

### For Endurance:

- Option 1: Use params passed from measurement (read_voltage, cycles) to identify read measurements
- Option 2: Detect pattern in data (voltage ≈ read_voltage indicates read measurement)
- Group reads into cycles (every 2 reads = 1 cycle: SET_read, RESET_read)

### For Retention:

- All data points after SET pulse are reads
- Use timestamps directly for time axis
- Calculate resistance from voltage/current

## File Naming

- Endurance: `{filename}_endurance_cycle_resistance.png`, `{filename}_endurance_onoff_ratio.png`
- Retention: `{filename}_retention_loglog.png`, `{filename}_retention_linear.png`, `{filename}_retention_resistance.png`
- IV: Keep existing `{filename}_iv_dashboard.png`

## Testing Considerations

- Test with actual endurance/retention measurement data
- Verify cycle detection works correctly
- Ensure plots are saved to correct Graphs folder
- Check that IV measurements still work as before