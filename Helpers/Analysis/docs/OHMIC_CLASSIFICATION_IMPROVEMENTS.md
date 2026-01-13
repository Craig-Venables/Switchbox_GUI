# Ohmic Classification Improvements (v1.2)

## Problem Statement

The previous classification system was misclassifying ohmic (linear resistive) devices as memristive when they exhibited tiny hysteresis artifacts from measurement noise or instrumentation effects.

### Example of Misclassification

**Device**: `10-FS-1.5v-0.05sv-0.05sd-Py-St_v2-.txt`

**Old Classification**:
- **Predicted**: Memristive (35.0%)
- **Scores**:
  - Memristive: 35.0
  - Memcapacitive: -20.0
  - Capacitive: 0.0
  - Conductive: 0.0
  - **Ohmic: 0.0** ← Problem!

**Features**:
- Hysteresis: YES (artifact detection needed)
- Pinched Loop: YES (false positive)
- Switching: NO ← Critical missing feature
- Nonlinear I-V: NO ← Linear device
- Phase Shift: 0.0

**Analysis**: This device is clearly ohmic (linear, no switching, no nonlinearity), but was getting memristive points for having a tiny "pinched hysteresis loop" that's actually just a measurement artifact.

---

## Root Causes

### 1. Over-Sensitive Pinched Hysteresis Detection
The `_check_pinched_hysteresis()` function was detecting tiny artifacts as legitimate pinched loops, even on purely ohmic devices.

### 2. Insufficient Ohmic Scoring
The old system had only two ohmic scoring paths:
- `ohmic_linear_clean`: 60 points (very restrictive conditions)
- `ohmic_model_fit`: 20 points (model-dependent bonus)

This meant most linear devices scored 0 points for ohmic, losing to even weak memristive signals.

### 3. Missing Critical Penalty
There was no penalty for memristive classification when **switching behavior was absent**. A true memristor MUST show state switching - without it, any hysteresis is likely capacitive or artifact-based.

### 4. Weak Hysteresis Thresholding
The hysteresis detection used a single fixed threshold (`1e-3`), which couldn't distinguish between:
- Noise/artifacts (`<1e-4`)
- Weak but real hysteresis (`1e-4` to `1e-3`)
- Clear hysteresis (`>1e-3`)

---

## Solutions Implemented

### 1. Enhanced Pinched Hysteresis Detection

**File**: `sweep_analyzer.py`, line ~2166

**Changes**:
```python
# NEW: Minimum area requirement
min_area_for_pinched = 1e-4  # Very small but non-negligible

if median_norm_area < min_area_for_pinched:
    # Area too small - likely ohmic with artifact
    return False
```

**Impact**: Prevents ohmic devices with tiny artifacts from being classified as having pinched loops.

---

### 2. Graduated Ohmic Scoring System

**File**: `sweep_analyzer.py`, line ~808

**Old System** (2 levels):
- `ohmic_linear_clean`: 60 points (very restrictive)
- `ohmic_model_fit`: 20 points

**New System** (4 quality levels + model bonus):

#### Level 1: Strong Ohmic (80 points)
```python
'ohmic_strong': 80.0
```
**Criteria**: Linear + Ohmic behavior + No hysteresis + No switching + ON/OFF < 1.5 + No compliance

**Example**: Perfect resistor behavior

#### Level 2: Clear Ohmic (70 points)
```python
'ohmic_clear': 70.0
```
**Criteria**: Linear + No hysteresis + No switching + Small area (<1e-3) + ON/OFF < 1.5

**Example**: Clean resistive behavior, no artifacts

#### Level 3: Ohmic with Artifact (60 points)
```python
'ohmic_with_artifact': 60.0
```
**Criteria**: Linear + Weak hysteresis (artifact) + No switching + ON/OFF < 1.5

**Example**: Ohmic device with tiny measurement artifacts ← **Fixes your case!**

#### Level 4: Weak Ohmic (40 points)
```python
'ohmic_weak': 40.0
```
**Criteria**: Linear + Ohmic behavior + No switching + ON/OFF < 2.0 (but may have some hysteresis)

**Example**: Mostly ohmic but with minor deviations

#### Model Bonus (10-20 points)
Additional points if conduction mechanism model strongly indicates ohmic:
- R² > 0.98: +20 points
- R² > 0.95: +15 points
- Otherwise: +10 points

#### Penalties
- Strong hysteresis + switching: -30 points
- Nonlinear I-V: -20 points

---

### 3. Critical Memristive Penalty

**File**: `sweep_analyzer.py`, line ~761

**New Penalty**:
```python
'memristive_penalty_no_switching': -40.0
```

**Logic**:
```python
if (has_hysteresis and 
    not switching_behavior and
    not nonlinear_iv):
    scores['memristive'] -= 40.0
```

**Reasoning**: A true memristor MUST have switching behavior (state change). Without it, any detected hysteresis is:
- Capacitive (phase lag)
- Artifact (noise, instrumentation)
- NOT memristive

This penalty ensures that devices with "hysteresis" but no switching can't be classified as memristive.

---

### 4. Artifact Filtering in Classification

**File**: `sweep_analyzer.py`, line ~719

**New Logic**:
```python
# If pinched hysteresis is detected BUT device is linear with no switching,
# it's likely measurement artifact, not true memristive behavior
if (pinched_hysteresis and linear_iv and not switching_behavior):
    # This is likely an ohmic device with artifacts
    classification_features['pinched_hysteresis'] = False
    classification_features['artifact_hysteresis'] = True
```

**Impact**: Directly addresses your example case - prevents linear devices with tiny artifacts from getting memristive classification.

---

### 5. Multi-Level Hysteresis Thresholding

**File**: `sweep_analyzer.py`, line ~2153

**Old System**: Single threshold (`1e-3`)

**New System**: Multi-level with consistency checks

| Normalized Area | Classification | Action |
|-----------------|----------------|--------|
| < 1e-4 | Noise/Artifact | Return False |
| 1e-4 to 1e-3 | Borderline | Check consistency across cycles |
| 1e-3 to 1e-2 | Clear Hysteresis | Return True |
| > 1e-2 | Strong Hysteresis | Return True |

**Borderline Logic** (1e-4 to 1e-3):
```python
# If area is consistent (CV < 0.5), it's real
cv = np.std(areas) / (np.mean(areas) + 1e-20)
if cv < 0.5:
    return True  # Consistent = real
else:
    return False  # Inconsistent = noise
```

---

## Expected Results for Your Example

**Device**: `10-FS-1.5v-0.05sv-0.05sd-Py-St_v2-.txt`

### New Classification (Expected):

**Predicted**: **Ohmic (60-70%)** ← Fixed!

**Scores**:
- Memristive: -5.0 (25 hysteresis - 40 no_switching + 30 pinched[disabled by artifact filter])
- Memcapacitive: -20.0
- Capacitive: 0.0
- Conductive: 0.0
- **Ohmic: 60-70** ← **Now competitive!**

**Reasoning**:
1. **Artifact Detection**: Linear + No switching triggers artifact filter
   - Disables pinched hysteresis credit
   
2. **Ohmic Scoring**: Matches "ohmic_with_artifact" (60 points) or "ohmic_clear" (70 points)
   - Linear I-V: ✓
   - No switching: ✓
   - Weak/artifact hysteresis: ✓
   
3. **Memristive Penalties**:
   - `memristive_penalty_no_switching`: -40 points
   - `memristive_penalty_linear_iv`: -20 points
   - Total memristive score becomes negative or very low

4. **Final Winner**: Ohmic with highest positive score

---

## Validation Checklist

To test these improvements, run analysis on:

### Test Case 1: True Ohmic Device
- **Expected**: Ohmic (70-80%)
- **Features**: Linear, no hysteresis, no switching
- **Score**: ohmic_strong (80) or ohmic_clear (70)

### Test Case 2: Ohmic with Artifacts (Your Case)
- **Expected**: Ohmic (60-70%)
- **Features**: Linear, tiny hysteresis artifact, no switching
- **Score**: ohmic_with_artifact (60) or ohmic_clear (70)
- **Key**: Memristive penalty (-40) prevents misclassification

### Test Case 3: Weak Memristive Device
- **Expected**: Uncertain or Memristive (low confidence)
- **Features**: Small hysteresis, small switching (ON/OFF ~2-3)
- **Score**: Should still classify as memristive if switching present

### Test Case 4: Strong Memristive Device
- **Expected**: Memristive (70-100%)
- **Features**: Clear hysteresis, pinched, switching, nonlinear
- **Score**: Unaffected by changes (all criteria met)

---

## Configuration

All weights are configurable in `Json_Files/classification_weights.json`:

```json
{
    "version": "1.2",
    "weights": {
        // NEW: Critical penalty
        "memristive_penalty_no_switching": -40.0,
        
        // NEW: Graduated ohmic scoring
        "ohmic_strong": 80.0,
        "ohmic_clear": 70.0,
        "ohmic_with_artifact": 60.0,
        "ohmic_weak": 40.0,
        
        // Existing weights (unchanged)
        "memristive_has_hysteresis": 25.0,
        "memristive_pinched_hysteresis": 30.0,
        "memristive_switching_behavior": 25.0,
        ...
    }
}
```

### Customizing for Your Dataset

If you find ohmic devices are still being misclassified, you can adjust:

1. **Increase ohmic weights**:
   ```json
   "ohmic_with_artifact": 70.0  // Was 60.0
   ```

2. **Strengthen memristive penalties**:
   ```json
   "memristive_penalty_no_switching": -50.0  // Was -40.0
   ```

3. **Adjust artifact threshold** (in code):
   ```python
   min_area_for_pinched = 5e-4  // Was 1e-4 (more conservative)
   ```

---

## Implementation Summary

### Files Modified
1. **`Helpers/Analysis/core/sweep_analyzer.py`**
   - Enhanced `_classify_device()` (lines ~699-825)
   - Added artifact filtering logic
   - Implemented graduated ohmic scoring
   - Added critical memristive penalty
   - Improved `_estimate_hysteresis_present()` (lines ~2153-2178)
   - Enhanced `_check_pinched_hysteresis()` (lines ~2166-2213)

2. **`Json_Files/classification_weights.json`**
   - Added new weights for graduated ohmic system
   - Added `memristive_penalty_no_switching`
   - Updated version to 1.2
   - Documented changes in changelog

### Key Metrics
- **4 new ohmic quality levels** (vs 1 old level)
- **1 new critical penalty** for missing switching behavior
- **Multi-level hysteresis thresholds** (3 levels vs 1)
- **Artifact detection logic** prevents false positives

---

## Testing Recommendations

1. **Re-analyze your problematic dataset**
   ```python
   from Helpers.Analysis import analyze_sweep
   
   result = analyze_sweep("10-FS-1.5v-0.05sv-0.05sd-Py-St_v2-.txt")
   print(f"Type: {result['classification']['device_type']}")
   print(f"Confidence: {result['classification']['confidence']:.1%}")
   print(f"Scores: {result['classification']['breakdown']}")
   ```

2. **Check classification breakdown**
   - Look at `classification['breakdown']` to see scores for each type
   - Verify ohmic score is now competitive (60-80 range)
   - Verify memristive score is penalized (-5 to 15 range)

3. **Review warnings**
   ```python
   if 'warnings' in result['classification']:
       for warning in result['classification']['warnings']:
           print(f"Warning: {warning}")
   ```

4. **Validate with known devices**
   - Test on devices you know are ohmic
   - Test on devices you know are memristive
   - Ensure both are classified correctly

---

## Future Enhancements

Potential improvements for future versions:

1. **Adaptive Thresholds by Material**
   - Organic devices may have different artifact levels than oxide devices
   - Could add material-specific scoring profiles

2. **User Feedback System**
   - Already implemented in code (Phase 2)
   - Allows users to correct misclassifications
   - System learns from corrections

3. **Confidence Calibration**
   - Map scores to calibrated confidence levels
   - "Uncertain" classification for scores < 40

4. **Multi-Sweep Consensus**
   - Analyze multiple sweeps from same device
   - Use consensus classification to reduce artifact impact

---

## Questions or Issues?

If you continue to see ohmic devices misclassified as memristive:

1. **Check the normalized area** in your data
   - If > 1e-4, the hysteresis might be real (not artifact)
   - Consider if it's actually a weak memristive device

2. **Verify switching behavior** is truly absent
   - Check ON/OFF ratio: should be < 1.5 for ohmic
   - Check resistance at different voltages

3. **Adjust thresholds** in `classification_weights.json`
   - Increase ohmic weights
   - Strengthen penalties
   - See "Customizing" section above

4. **Enable diagnostics** for detailed analysis
   ```python
   # In sweep_analyzer.py, set:
   DEBUG_ENABLED = True
   ```
   This will print detailed classification reasoning to console.

---

## Version History

- **v1.0**: Original classification system
- **v1.1**: Initial ohmic improvements (increased weights, strengthened penalties)
- **v1.2**: **Current** - Comprehensive ohmic classification overhaul
  - Graduated ohmic scoring (4 levels)
  - Critical switching penalty
  - Artifact filtering
  - Multi-level hysteresis thresholds
  - Enhanced pinched loop detection

