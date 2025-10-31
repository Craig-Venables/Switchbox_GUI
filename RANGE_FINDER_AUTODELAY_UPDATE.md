# Current Range Finder Autodelay Update - October 31, 2024

## Summary

Updated the `current_range_finder` function to:
1. **Use autodelay settings** based on Keithley 2450 specifications
2. **Show results in a popup GUI window** instead of just console output

## Changes Made

### 1. Autodelay Implementation (`keithley2450_tsp_scripts.py`)

#### New Helper Function: `_get_autodelay()`
- Looks up autodelay time based on current measurement range
- Supports both standard and high capacitance delays
- Supports voltage source and current source modes
- Returns delay time in seconds

**Autodelay Table** (from Keithley 2450 manual):
| Range | Voltage Source (ms) | Voltage Source High Cap (ms) | Current Source (ms) | Current Source High Cap (ms) |
|-------|---------------------|------------------------------|---------------------|----------------------------|
| 10 nA | 150 | 300 | 150 | 300 |
| 100 nA | 100 | 200 | 100 | 200 |
| 1 μA | 3 | 20 | 3 | 20 |
| 10 μA | 2 | 10 | 2 | 10 |
| 100 μA | 1 | 10 | 1 | 10 |
| 1 mA | 1 | 10 | 1 | 10 |
| 10 mA | 1 | 5 | 1 | 5 |
| 100 mA | 1 | 5 | 1 | 5 |
| 1 A | 1 | 5 | 2 | 5 |

#### Updated `current_range_finder()` Function
- Added `use_high_capacitance` parameter (default: False)
- Automatically calculates and applies autodelay for each range tested
- Sets both `smu.source.autodelay` and `smu.measure.autodelay` in TSP script
- Prints autodelay information during test execution

**Example output:**
```
[1/4] Testing range: 1000.0µA limit
    Using autodelay: 1.0ms (standard)
```

### 2. GUI Popup Window (`TSP_Testing_GUI.py`)

#### New Parameter
- Added `use_high_capacitance` checkbox to Current Range Finder test configuration
- Default: False (uses standard autodelay)

#### New Method: `_show_range_finder_popup()`
- Creates a modal popup window displaying:
  - **Recommendation section**: Shows the recommended range with key statistics
  - **Results table**: Scrollable table showing all tested ranges with:
    - Range limit (µA)
    - Mean current (µA)
    - Standard deviation (µA)
    - Coefficient of variation (CV %)
    - Min/Max current (µA)
    - Mean resistance (Ω)
    - Status (✓ OK, ✗ Neg, ★ RECOMMENDED)

**Popup Features:**
- Modal window (blocks interaction with main window until closed)
- Professional table layout with scrollbar
- Highlights recommended range
- Shows comprehensive statistics
- Easy to read format

#### Automatic Display
- Popup automatically appears after `current_range_finder` test completes
- Results are still plotted on the main canvas
- Console output is still available for debugging

## Usage

### In GUI:
1. Select "Current Range Finder" from test dropdown
2. Configure parameters:
   - Test Voltage (V)
   - Reads Per Range
   - Delay Between Reads (ms)
   - Ranges to Test (comma-separated, A)
   - **Use High Capacitance Autodelay** (checkbox) ← NEW
3. Click "Run Test"
4. After test completes, popup window automatically appears with results

### Programmatically:
```python
results = test_scripts.current_range_finder(
    test_voltage=0.2,
    num_reads_per_range=10,
    delay_between_reads=10e-3,
    current_ranges=[1e-3, 100e-6, 10e-6, 1e-6],
    use_high_capacitance=False  # NEW parameter
)

# Access results
recommended_range = results['recommended_range']
range_stats = results['range_stats']
```

## Benefits

1. **Proper Settling Time**: Autodelay ensures measurements are taken after sufficient settling time for each range
2. **Better Accuracy**: High capacitance option available for devices with large capacitance
3. **User-Friendly Results**: Popup window makes it easy to see recommended range at a glance
4. **Comprehensive Statistics**: All range statistics visible in organized table
5. **Professional Presentation**: Clean, readable format for sharing results

## Technical Details

### Autodelay Implementation
- Autodelay is set **per range** in the TSP script
- Both source and measure autodelay are configured
- Delay time is calculated based on the measurement range (i_range = clim * 1.2)
- Time values are converted from milliseconds (manual) to seconds (TSP)

### TSP Commands Used
```lua
smu.source.autodelay = {delay_time}  -- Voltage source autodelay
smu.measure.autodelay = {delay_time} -- Current measurement autodelay
```

### Popup Window Implementation
- Uses `tkinter.Toplevel` for modal popup
- `ttk.Treeview` for scrollable table
- Formatted display with proper units (µA, Ω)
- Highlights recommended range for easy identification

## Files Modified

1. `Equipment/SMU_AND_PMU/keithley2450_tsp_scripts.py`
   - Added `_get_autodelay()` helper function
   - Updated `current_range_finder()` to use autodelay

2. `TSP_Testing_GUI.py`
   - Added `use_high_capacitance` parameter to test config
   - Added `_show_range_finder_popup()` method
   - Updated `_run_test_thread()` to show popup for range finder

## Testing Recommendations

1. **Test with standard autodelay** (default):
   - Run range finder on a known device
   - Verify popup appears after test
   - Check that recommended range makes sense

2. **Test with high capacitance autodelay**:
   - Enable "Use High Capacitance Autodelay" checkbox
   - Run on device with large capacitance
   - Verify longer delays are used for low current ranges

3. **Verify autodelay values**:
   - Check console output for autodelay times
   - Confirm they match expected values from table
   - For 10 nA range: should show 150ms (standard) or 300ms (high cap)

4. **Test popup display**:
   - Verify table shows all tested ranges
   - Check that recommended range is highlighted
   - Confirm statistics are accurate
   - Test scrollbar if many ranges tested

## Notes

- Autodelay times are conservative (from Keithley manual) for reliable measurements
- High capacitance option should be used for devices with >100pF capacitance
- Popup window is modal - must close before continuing with other operations
- Results are still saved to console and can be saved to file as usual

