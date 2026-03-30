# Enhanced Classification System (Phase 1)

## Overview

This document describes the **Phase 1** implementation of the Enhanced Classification System for IV sweep analysis. This system provides **additional** classification metrics without modifying the core classification logic, making it safe to use alongside existing analysis.

**Key principle**: All enhancements are **additive** - they provide extra information but don't change how devices are classified in the core system.

## What's New?

### 1. Memristivity Score (0-100) ⭐

A **continuous score** that quantifies how memristive a device is, replacing binary classification with a nuanced assessment.

**Scoring breakdown**:
- **Pinched hysteresis**: 30 points (memristive fingerprint)
- **Hysteresis quality**: 20 points (area, consistency)
- **Switching behavior**: 20 points (ON/OFF ratio)
- **Memory window quality**: 15 points (state separation)
- **Nonlinearity**: 10 points (deviation from ohmic)
- **Polarity dependence**: 5 points (bipolar switching)

**Benefits**:
- Track device quality over time
- Compare devices quantitatively
- Detect degradation
- Identify "borderline" devices

**Example usage**:
```python
analyzer = IVSweepAnalyzer(analysis_level='full')
data = analyzer.analyze_sweep(voltage=v, current=i)

print(f"Memristivity Score: {data['classification']['memristivity_score']:.1f}/100")
# Output: Memristivity Score: 85.5/100

# See breakdown
breakdown = data['classification']['memristivity_breakdown']
for feature, score in breakdown.items():
    print(f"  {feature}: {score:.1f}")
```

---

### 2. Adaptive Thresholds 🎯

Context-aware thresholds that adjust based on measurement conditions:

**Adjusts for**:
- **Voltage range**: Higher voltages → larger expected hysteresis
- **Compliance current**: Affects ON/OFF ratio expectations
- **Data resolution**: More points → tighter thresholds
- **Current magnitude**: Scales noise floor estimates
- **Organic devices**: Relaxed variability tolerance (future)

**Benefits**:
- Fewer false positives/negatives
- Better handling of low-voltage measurements
- Accounts for experimental limitations

**Accessed via**:
```python
thresholds = data['classification']['adaptive_thresholds']
print(f"Voltage range: {thresholds['voltage_range']:.2f}V")
print(f"Hysteresis threshold: {thresholds['hysteresis_area_min']:.2e}")
print(f"Noise floor: {thresholds['noise_floor']:.2e}A")
```

---

### 3. Memory Window Quality Assessment 📊

Detailed evaluation of the memory window with 6 sub-metrics:

**Metrics**:
1. **Stability score (0-100)**: How flat/consistent are ON/OFF states?
2. **Separation quality**: Distance between states relative to noise
3. **Reproducibility (0-100)**: Cycle-to-cycle consistency
4. **Switching voltage efficiency**: Lower is better
5. **State retention**: Do states persist?
6. **Analog capability**: Detects intermediate states

**Overall quality score**: Weighted combination (0-100)

**Benefits**:
- Identify high-quality vs marginal devices
- Optimize fabrication processes
- Select best devices for applications

**Example**:
```python
mw = data['classification']['memory_window_quality']
print(f"Overall Quality: {mw['overall_quality_score']:.1f}/100")
print(f"State Stability: {mw['avg_stability']:.1f}/100")
print(f"Separation Ratio: {mw['separation_ratio']:.2f}")
print(f"Reproducibility: {mw['reproducibility']:.1f}/100")
```

---

### 4. Hysteresis Shape Analysis 🔍

Detailed characterization of hysteresis loop morphology:

**Features**:
- **Figure-eight quality (0-100)**: How well does it cross at origin?
- **Lobe asymmetry**: Set vs reset differences
- **Smoothness**: Detects kinks/steps (trapping indicators)
- **Width variation**: Measures at multiple current levels
- **Lobe area ratio**: Quantifies asymmetry

**Benefits**:
- Identify trapping mechanisms
- Detect device asymmetry
- Characterize switching dynamics
- Understand physical processes

**Example**:
```python
shape = data['classification']['hysteresis_shape']
if shape['has_hysteresis']:
    print(f"Figure-8 Quality: {shape['figure_eight_quality']:.1f}/100")
    print(f"Lobe Asymmetry: {shape['lobe_asymmetry']:.3f}")
    if 'num_kinks_detected' in shape:
        print(f"Kinks detected: {shape['num_kinks_detected']} (possible trapping)")
```

---

### 5. Warning System ⚠️

Non-blocking warnings for potential issues:

**Checks**:
- **Voltage symmetry**: Set ≠ reset voltage
- **Current sanity**: Too high/low, poor SNR
- **Physical plausibility**: Unrealistic resistance, power
- **Speed characteristics**: Fast sweeps with hysteresis (capacitive?)

**Benefits**:
- Early detection of measurement issues
- Device quality flags
- Guidance for troubleshooting

**Example**:
```python
warnings = data['classification']['warnings']
for warning in warnings:
    print(f"⚠ {warning}")

# Example output:
# ⚠ Voltage asymmetry detected: Set=2.10V, Reset=1.45V (ratio=1.45)
# ⚠ Low SNR detected (SNR≈8.2). Signal may be dominated by noise.
```

---

## How to Use

### Basic Usage (No Changes Needed)

The enhanced classification runs **automatically** whenever you analyze data. No code changes needed!

```python
from Helpers.IV_Analysis import quick_analyze

# Your existing code works as-is
data = quick_analyze(voltage=v, current=i, analysis_level='full')

# Core classification unchanged
print(data['classification']['device_type'])  # 'memristive', 'capacitive', etc.

# NEW: Enhanced metrics available
print(data['classification']['memristivity_score'])  # 85.5
print(data['classification']['memory_window_quality'])  # {...}
```

### Accessing Enhanced Metrics

All enhanced metrics are in the `classification` section:

```python
classification = data['classification']

# Core (unchanged)
device_type = classification['device_type']
confidence = classification['confidence']

# Enhanced (new)
memristivity_score = classification['memristivity_score']
memristivity_breakdown = classification['memristivity_breakdown']
memory_window_quality = classification['memory_window_quality']
hysteresis_shape = classification['hysteresis_shape']
adaptive_thresholds = classification['adaptive_thresholds']
warnings = classification['warnings']
```

### Disabling Enhanced Classification

If you need to disable it (for speed or compatibility):

```python
from Helpers.IV_Analysis.single_file_metrics import analyze_single_file

analyzer = analyze_single_file(voltage, current)
analyzer.enhanced_classification_enabled = False  # Disable before classification
# Run your analysis...
```

---

## GUI Integration

### Analysis Stats Window

The floating stats window now displays:
- **Memristivity Score** (next to confidence)
- **Memory Window Quality** section
- **Hysteresis Shape** section (if hysteresis present)
- **Warnings** section (if any)

### Saved Analysis Files

The `{sweep_name}_analysis.txt` files now include:
- Memristivity score breakdown
- Memory window quality metrics
- Hysteresis shape features
- All warnings

Location: `{data_directory}/sweep_analysis/{sweep_name}_analysis.txt`

---

## What's NOT Changed

✅ **Core classification logic**: Untouched
✅ **Existing attributes**: All preserved
✅ **File formats**: Same output structure
✅ **API compatibility**: Fully backward compatible
✅ **Performance**: Minimal overhead (~5-10ms)

---

## Implementation Details

### File Modifications

1. **`Helpers/IV_Analysis/single_file_metrics.py`**:
   - Added new attributes in `__init__()` (lines ~86-100)
   - Added 9 new methods (lines ~2583-3100):
     - `calculate_enhanced_classification()`
     - `_calculate_memristivity_score()`
     - `_calculate_adaptive_thresholds()`
     - `_assess_memory_window_quality()`
     - `_analyze_hysteresis_shape()`
     - `_check_voltage_symmetry()`
     - `_check_current_sanity()`
     - `_validate_physical_plausibility()`
     - `_infer_speed_characteristics()`
   - Modified `_classify_device()` to call enhanced classification (lines ~567-573)

2. **`Helpers/IV_Analysis/iv_sweep_analyzer.py`**:
   - Added enhanced metrics to output dictionary (lines ~254-260)

3. **`gui/measurement_gui/main.py`**:
   - Updated `_save_analysis_results()` to include enhanced metrics (lines ~912-977)

4. **`gui/measurement_gui/analysis_stats_window.py`**:
   - Updated `_update_content()` to display enhanced metrics (lines ~308-349)

### Performance Impact

- **Computation time**: ~5-10ms per sweep (negligible)
- **Memory overhead**: ~5KB per device (6 new dictionaries)
- **File size increase**: ~500 bytes per analysis file

---

## Future Phases

### Phase 2: Device Context & Tracking

- **Device Evolution Tracking**: Monitor degradation over time
- **User Feedback System**: Learn from corrections
- **Historical Comparison**: Compare to previous measurements

### Phase 3: Advanced Analysis (Optional)

- **Multi-Cycle Statistical Confidence**: Variance analysis
- **Multi-Parameter Clustering**: Find similar devices
- **Conduction Mechanism Cross-Validation**: Check consistency

### Phase 4: Material-Specific Models

- **Organic/Polymer Profiles**: Relaxed variability, lower currents
- **Oxide RRAM Profiles**: Tighter specs, forming detection
- **PCM Profiles**: Threshold switching, large R-changes
- **Custom Profiles**: User-defined material characteristics

---

## Testing

### Test with Your Devices

Run a measurement with analysis enabled:

1. Enable analysis in GUI (checkbox)
2. Run standard IV sweep
3. Check `sweep_analysis/` folder for results
4. Verify memristivity score makes sense
5. Review any warnings

### Expected Behavior

**Memristive device**:
- Score: 60-100
- High figure-8 quality (>80)
- Good window quality (>60)
- Few or no warnings

**Capacitive device**:
- Score: 10-40
- Warnings about non-pinched hysteresis
- May flag fast sweep rate

**Ohmic device**:
- Score: 0-10
- Warnings about low switching ratio
- Linear I-V noted

---

## Troubleshooting

### Issue: All scores are 0 or None

**Cause**: Enhanced classification disabled or failed
**Solution**: Check `analyzer.enhanced_classification_enabled = True`

### Issue: Scores seem wrong

**Cause**: Unusual device characteristics
**Solution**: Check warnings - they often explain why

### Issue: Too many warnings

**Cause**: Marginal device or measurement issues
**Solution**: Warnings are informational - review and decide if critical

---

## Support & Questions

For issues or questions about the enhanced classification:

1. Check warnings in the analysis output
2. Review the memristivity score breakdown
3. Compare adaptive thresholds to your measurement conditions
4. Open an issue in the repository

---

## Version History

- **v1.0 (Phase 1)**: Initial implementation
  - Memristivity score
  - Adaptive thresholds
  - Memory window quality
  - Hysteresis shape analysis
  - Warning system

---

## Credits

Developed for organic/polymer memristor research. Optimized for devices with high variability and low currents.

Special considerations:
- Organic devices: High cycle-to-cycle variability accepted
- Low current operation: Noise-aware thresholds
- Small switching regions: Adaptive scaling
- Unusual behaviors: Informational warnings, not blocking
