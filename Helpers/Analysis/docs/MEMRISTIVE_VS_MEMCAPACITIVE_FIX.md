# Memristive vs Memcapacitive Classification Fix (v1.3)

## Problem Statement

Devices with **switching behavior + nonlinearity** were being misclassified as **Memcapacitive** instead of **Memristive** when they didn't pass exactly through zero voltage.

### Example Case

**Device**: `11-FS-2.5v-0.05sv-0.05sd-Py-St_v1-3.txt`

**Old Classification** (v1.2):
```
Predicted: Memcapacitive (50.0%)

Scores:
  Memristive: 45.0      ← Should win!
  Memcapacitive: 50.0   ← Wrong winner
  
Features:
  Hysteresis: no        ← Fails area threshold
  Pinched Loop: no      ← Doesn't pass through zero
  Switching: YES        ← KEY MEMRISTIVE FEATURE!
  Nonlinear I-V: YES    ← KEY MEMRISTIVE FEATURE!
  Phase Shift: 17.7°    ← Not high enough for capacitive
```

**Analysis**: This device clearly shows **state-dependent resistance** (switching + nonlinearity), which is THE defining characteristic of a memristor. The fact that it doesn't pass exactly through zero shouldn't disqualify it - real memristors often have:
- Series resistance
- Contact effects
- Measurement offsets
- Non-ideal electrodes

These prevent perfect zero crossing but don't change the fundamental memristive behavior.

---

## Root Causes

### 1. Area Threshold Doesn't Scale
**Problem**: Fixed threshold of `1e-4` doesn't work for devices with currents ranging from 1e-9 to 1e-3.

**Example**: 
- Device A: 1 mA current → normalized area might be 1e-3 (detected)
- Device B: 1 nA current → same hysteresis loop → normalized area 1e-9 (missed!)

### 2. Switching Not Prioritized
**Problem**: Switching behavior (THE defining memristive feature) was weighted equally with hysteresis and pinched loop.

**Result**: Devices with switching but no pinched loop scored lower than devices with pinched loop but no switching.

### 3. Memcapacitive Competition
**Problem**: Memcapacitive scoring didn't penalize strong switching, allowing it to compete with memristive classification.

**Logic Error**: Memcapacitors can show *weak* switching (gradual state change), but *strong* switching (ON/OFF > 2) is distinctly memristive.

### 4. Pinched Check Too Strict
**Problem**: Required current at V=0 to be < 5% of max current.

**Issue**: Real devices with series resistance or contact effects don't pass exactly through zero, even though they're clearly memristive.

---

## Solutions Implemented (v1.3)

### 1. **Adaptive Area Thresholds** ✓

**Location**: `_estimate_hysteresis_present()` and `_check_pinched_hysteresis()`

**Change**: Thresholds now scale with current magnitude using `sqrt(I_max / 1mA)`:

```python
# Calculate adaptive threshold
max_current = np.percentile(np.abs(self.current), 99)
current_scale = np.sqrt(max_current / 1e-3)  # Scale factor
current_scale = max(0.01, min(100, current_scale))  # Clamp

# Adaptive thresholds
threshold_very_weak = 1e-4 * current_scale
threshold_weak = 1e-3 * current_scale
threshold_medium = 1e-2 * current_scale
```

**Impact**: Devices with 1 nA to 1 mA currents now have proportional thresholds.

---

### 2. **Switching Priority Bonus** ✓

**Location**: Memristive scoring in `_classify_device()`

**New Weight**: `memristive_switching_plus_nonlinear_bonus = 20.0`

**Logic**:
```python
if switching_behavior AND nonlinear_iv:
    memristive_score += 20  # BONUS for the core memristive signature
```

**Impact**: 
- Device with switching + nonlinearity: **65 points** (25 + 10 + 20 bonus)
- Device with just hysteresis + pinched: **55 points** (25 + 30)

**Result**: Switching devices now properly dominate classification!

---

### 3. **Memcapacitive Strong Switching Penalty** ✓

**Location**: Memcapacitive scoring in `_classify_device()`

**New Weight**: `memcapacitive_penalty_strong_switching = -25.0`

**Logic**:
```python
if switching_behavior:
    mean_onoff = np.mean(on_off_ratios)
    if mean_onoff > 2.0:  # Strong switching
        memcapacitive_score -= 25  # PENALTY
    else:  # Weak switching (ON/OFF < 2)
        memcapacitive_score += 30  # OK for memcapacitive
```

**Impact**: Devices with ON/OFF > 2 now strongly favor memristive over memcapacitive.

---

### 4. **Relaxed Pinched Hysteresis Check** ✓

**Location**: `_check_pinched_hysteresis()`

**Changes**:
1. **Adaptive threshold**: 10% for switching devices (was 5% for all)
2. **Adaptive minimum area**: 10x more lenient for switching devices
3. **Context-aware**: Considers switching strength when evaluating pinch quality

**Code**:
```python
# Check for strong switching
has_strong_switching = mean_onoff > 2.0

# Adaptive threshold
if has_strong_switching:
    pinch_threshold = 0.10  # 10% - relaxed for switching devices
else:
    pinch_threshold = 0.05  # 5% - strict for non-switching

# Adaptive minimum area
min_area = adaptive_base_area
if has_strong_switching:
    min_area *= 0.1  # 10x more lenient
```

**Impact**: Devices with strong switching behavior pass pinched check even without perfect zero crossing.

---

## Expected Results

### For Your Device (`11-FS-2.5v-0.05sv-0.05sd-Py-St_v1-3.txt`)

**New Classification** (v1.3):
```
Predicted: Memristive (65-85%)  ✓

Scores:
  Memristive: 65-85     ← WINNER! ✓
    Base: 25 (switching) + 10 (nonlinear)
    BONUS: +20 (switching + nonlinear combination)
    Pinched: +30 (now passes with relaxed threshold)
  
  Memcapacitive: 25     ← Properly penalized
    Base: 30 (switching) - 25 (strong switching penalty)
  
Features:
  Switching: YES        ✓ Properly weighted!
  Nonlinear I-V: YES    ✓ Bonus applied!
  Pinched Loop: YES     ✓ Relaxed threshold passes!
  Phase Shift: 17.7°    (not high enough for capacitive)
```

**Reasoning**:
1. **Switching + Nonlinearity**: +20 bonus → 65 points total
2. **Relaxed pinched check**: Now passes → +30 points → **85 points total**
3. **Memcapacitive penalty**: Strong switching penalized → 25 points only

---

## Current Scaling Examples

### Device A: High Current (1 mA)
- Max current: 1e-3 A
- Scale factor: sqrt(1e-3 / 1e-3) = 1.0
- Threshold: 1e-4 * 1.0 = **1e-4** (baseline)

### Device B: Medium Current (1 μA)
- Max current: 1e-6 A
- Scale factor: sqrt(1e-6 / 1e-3) = 0.032
- Threshold: 1e-4 * 0.032 = **3.2e-6** (32x lower)

### Device C: Low Current (1 nA)
- Max current: 1e-9 A
- Scale factor: sqrt(1e-9 / 1e-3) = 1e-3
- Threshold: 1e-4 * 1e-3 = **1e-7** (1000x lower)
- Note: Clamped to minimum 0.01 → actual threshold = **1e-6**

**Result**: All devices now have proportional thresholds appropriate for their current range!

---

## Scoring Summary (v1.3)

### Memristive Path
| Feature | Score | Notes |
|---------|-------|-------|
| Hysteresis | +25 | If present |
| Pinched Loop | +30 | Relaxed to 10% for switching devices |
| Switching | +25 | Base score |
| **Switching + Nonlinear** | **+20** | **NEW BONUS** |
| Nonlinear I-V | +10 | Additional if not covered by bonus |
| Polarity Dependent | +10 | Bipolar switching |
| **Max Possible** | **120** | With all features |

### Memcapacitive Path
| Feature | Score | Notes |
|---------|-------|-------|
| Unpinched Hysteresis | +40 | Must not be pinched |
| Weak Switching (ON/OFF < 2) | +30 | Gradual state change |
| **Strong Switching (ON/OFF > 2)** | **-25** | **NEW PENALTY** |
| Nonlinear I-V | +20 | |
| Phase Shift > 30° | +20 | Capacitive signature |
| Pinched Loop | -20 | Penalty |

---

## Key Improvements

### ✓ **Switching is King**
Switching behavior is now properly recognized as THE defining memristive feature. Devices with switching + nonlinearity get a strong bonus.

### ✓ **Adaptive to Current Range**
Thresholds scale from 1 nA to 1 mA devices using sqrt scaling. No more fixed thresholds!

### ✓ **Real-World Tolerance**
Pinched hysteresis check relaxed to 10% for switching devices, accommodating series resistance and contact effects.

### ✓ **No More Competition**
Memcapacitive classification properly penalized when strong switching present. Can't compete with memristive anymore.

---

## Testing

### Quick Test
```python
from Helpers.Analysis.core.sweep_analyzer import SweepAnalyzer
import numpy as np

# Load your data
data = np.loadtxt("11-FS-2.5v-0.05sv-0.05sd-Py-St_v1-3.txt", skiprows=1)
voltage = data[:, 0]
current = data[:, 1]

# Analyze
analyzer = SweepAnalyzer(voltage, current, analysis_level='classification')

# Check results
print(f"Type: {analyzer.device_type}")
print(f"Confidence: {analyzer.classification_confidence:.1%}")
print(f"Scores: {analyzer.classification_breakdown}")
print(f"\nKey Features:")
print(f"  Switching: {analyzer.classification_features['switching_behavior']}")
print(f"  Nonlinear: {analyzer.classification_features['nonlinear_iv']}")
print(f"  Pinched: {analyzer.classification_features['pinched_hysteresis']}")
```

### Expected Output
```
Type: memristive
Confidence: 70-85%
Scores: {'memristive': 65-85, 'memcapacitive': 25, ...}

Key Features:
  Switching: True
  Nonlinear: True
  Pinched: True (or False but still wins due to bonus)
```

---

## Additional Suggestions

### 1. **Check Other Classification Issues**

Run analysis on your full dataset and look for:

**Ohmic devices classified as memristive**:
```python
# Should see: ohmic score 60-80, memristive score negative or low
```

**Capacitive devices classified as memristive**:
```python
# Should see: high phase shift (>45°), unpinched hysteresis
```

**Conductive devices (nonlinear, no hysteresis)**:
```python
# Should see: nonlinear but no switching or hysteresis
```

### 2. **Fine-Tune Switching Threshold**

Current threshold: ON/OFF > 2.0 for "strong switching"

If you find devices with ON/OFF = 1.5-2.0 being misclassified, adjust:
```json
// In classification_weights.json
"memcapacitive_strong_switching_threshold": 1.5  // Lower = stricter
```

### 3. **Adjust Bonus Weight**

If switching devices still lose to hysteresis-only devices:
```json
"memristive_switching_plus_nonlinear_bonus": 30.0  // Increase from 20
```

### 4. **Monitor Normalized Area Values**

Add diagnostic output to see if thresholds are working:
```python
# Enable debug mode
DEBUG_ENABLED = True  # In sweep_analyzer.py line 17

# Then check console output for:
# [DIAGNOSTIC] Normalized area: X.XXe-X, threshold: Y.YYe-Y
```

---

## Version History

- **v1.0**: Original classification system
- **v1.1**: Ohmic improvements (increased weights, strengthened penalties)
- **v1.2**: Graduated ohmic scoring, artifact detection, area thresholds
- **v1.3**: **Current** - Switching priority, adaptive thresholds, memcapacitive fix
  - NEW: `memristive_switching_plus_nonlinear_bonus` (+20)
  - NEW: `memcapacitive_penalty_strong_switching` (-25)
  - FIXED: Adaptive area thresholds scale with current (sqrt)
  - FIXED: Pinched check relaxed to 10% for switching devices
  - FIXED: Memcapacitive can't compete with memristive when switching present

---

## Files Modified

1. **`Helpers/Analysis/core/sweep_analyzer.py`**
   - `_classify_device()`: Added switching+nonlinear bonus, memcapacitive penalty
   - `_estimate_hysteresis_present()`: Adaptive area thresholds
   - `_check_pinched_hysteresis()`: Relaxed threshold for switching devices
   - `_get_default_classification_weights()`: New weights added

2. **`Json_Files/classification_weights.json`**
   - Version bumped to 1.3
   - Added new weights
   - Updated notes and changelog

3. **Documentation**
   - `MEMRISTIVE_VS_MEMCAPACITIVE_FIX.md` (this file)
   - Updated `OHMIC_CLASSIFICATION_IMPROVEMENTS.md` with v1.3 reference

