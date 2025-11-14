# Keithley 4200A Test Implementation Status

## Overview
This document tracks which tests are currently working, which need C code modifications, and what implementation strategy to follow.

---

## ✅ Currently Working Tests

These tests are **fully functional** and can be used immediately:

1. **`relaxation_after_multi_pulse`** ✅
   - Pattern: 1×Read → N×Pulse → N×Read (measure reads only)
   - C Module: `readtrain_dual_channel.c`
   - Status: Working

2. **`pulse_multi_read`** ✅
   - Pattern: N pulses then many reads
   - C Module: Uses existing readtrain/retention modules
   - Status: Working

3. **`multi_read_only`** ✅
   - Pattern: Just reads, no pulses
   - C Module: Uses existing read modules
   - Status: Working

4. **`multi_pulse_then_read`** ⚠️ PARTIAL
   - Pattern: (Pulse×N → Read×M) × Cycles
   - C Module: Uses retention/readtrain modules
   - **LIMITATION**: Currently limited to 8 reads per cycle (hardcoded in C)
   - Status: Works but needs modification to support N reads (1 to N)

5. **`width_sweep_with_reads`** ⚠️ PARTIAL
   - Pattern: For each width: (Read→Pulse→Read)×N, Reset
   - C Module: Uses retention modules
   - **LIMITATION**: Currently calls C code once per width, but needs to:
     - Call C code multiple times (once per width)
     - Wait for response each time
     - Store data between calls
   - Status: Works but needs Python-side loop implementation

---

## ❌ Tests Requiring New C Code

These tests **cannot be implemented** with current C modules and need new C code:

### 1. **`pulse_read_repeat`** ⚠️ CAN USE RETENTION MODULE
   - **Required Pattern**: Initial Read → (Pulse → Read → Delay) × N
   - **Current Limitation**: `pmu_retention_dual_channel.c` has min 8 requirement for `NumbMeasPulses`
   - **Solution Options**:
     - **Option A (Quick)**: Remove min-8 check in C code, use retention module in Python loop:
       - Call retention module N times with: `NumInitialMeasPulses=1` (first call only), `NumPulses=1`, `NumbMeasPulses=1`
       - Less efficient (N C calls) but works immediately
     - **Option B (Better)**: Modify retention C code to support interleaved pattern:
       - Add parameter to interleave pulses and reads: (Pulse→Read) × N instead of (All Pulses → All Reads)
       - Single C call, more efficient
   - **Priority**: HIGH (basic test pattern)
   - **Recommended**: Start with Option A, then Option B for efficiency

### 2. **`width_sweep_with_all_measurements`** ❌
   - **Required Pattern**: Width sweep with pulse peak current measurements
   - **Current Limitation**: No C module measures pulse peak currents during width sweep
   - **What's Needed**: 
     - Either modify existing width sweep C code to measure pulse peaks
     - Or create new module that includes pulse measurement capability
   - **Priority**: MEDIUM

### 3. **`relaxation_after_multi_pulse_with_pulse_measurement`** ❌
   - **Required Pattern**: 1×Read → N×Pulse(measured) → N×Read
   - **Current Limitation**: Existing relaxation module doesn't measure pulse peaks
   - **What's Needed**: 
     - Modify `readtrain_dual_channel.c` to measure pulse peak currents
     - Or create variant that includes pulse measurement
   - **Priority**: MEDIUM

### 4. **`current_range_finder`** ❌
   - **Required Pattern**: Test multiple current ranges, recommend best
   - **Current Limitation**: No C module for range testing
   - **What's Needed**: 
     - New C module or Python-side loop calling existing read modules with different ranges
   - **Priority**: LOW

---

## 🔧 Tests Needing Python-Side Modifications

These tests work but need Python wrapper improvements:

### 1. **`multi_pulse_then_read`** - Allow N reads (currently limited to 8)
   - **Current**: C module hardcodes 8 reads
   - **Solution Options**:
     - **Option A**: Modify C module to accept `num_reads` parameter (1-1000)
     - **Option B**: Python-side loop: call C module multiple times if N > 8
   - **Recommendation**: Option A (modify C) is cleaner

### 2. **`width_sweep_with_reads`** - Loop over widths
   - **Current**: Python calls C once with all widths
   - **Solution**: Python-side loop:
     ```python
     for width in pulse_widths:
         result = call_c_module(width=width, ...)
         store_data(result)
         wait_for_completion()
     ```
   - **Status**: Needs implementation in `keithley4200_kxci_scripts.py`

---

## 📋 Available C Modules

### Existing C Modules in `Equipment/SMU_AND_PMU/4200_C_Code/`:

1. **`pmu_retention_dual_channel.c`**
   - Pattern: Initial reads → Pulse sequence → Retention reads
   - Supports: 8-1000 retention measurements
   - Used by: `retention_test`, `relaxation_after_multi_pulse`

2. **`readtrain_dual_channel.c`**
   - Pattern: Read train (multiple reads)
   - Used by: `relaxation_after_multi_pulse`, `pulse_multi_read`

3. **`retention_pulse_ilimit_dual_channel.c`**
   - Low-level PMU control with current limits
   - Used internally by retention modules

4. **`read_train_ilimit.c`**
   - Low-level read train with current limits
   - Used internally by readtrain modules

---

## 🎯 Implementation Strategy Recommendations

Based on your requirements, here are two viable approaches:

### **Option 1: Custom Seg_Arb Builder (Python → C)**
**Pros:**
- Maximum flexibility - can create any waveform pattern
- Single C module handles all patterns
- Python builds waveform arrays, sends to C

**Cons:**
- More complex C code (needs seg_arb array builder)
- More complex Python code (needs waveform generator)

**Implementation:**
- Create: `custom_segarb_dual_channel.c`
- Python builds arrays: `[voltage1, voltage2, ..., voltageN]`, `[time1, time2, ..., timeN]`
- C module uses `seg_arb_sequence()` to generate waveform
- Supports any pattern: Read→Pulse→Read→Delay, etc.

### **Option 2: Simple (Read + Pulse×N + Read×M) Script**
**Pros:**
- Simpler C code (fixed pattern)
- Easier to understand and debug
- Faster to implement

**Cons:**
- Less flexible (only handles one pattern)
- May need multiple C modules for different patterns

**Implementation:**
- Create: `pulse_read_repeat_dual_channel.c`
- Pattern: Initial Read → (Pulse → Read → Delay) × N
- Parameters: `num_cycles`, `pulse_v`, `pulse_width`, `read_v`, `read_width`, `delay`
- Single C call handles entire sequence

### **Recommended Approach: Hybrid**

1. **Short-term (Quick Wins)**:
   - Create `pulse_read_repeat_dual_channel.c` for basic pulse-read-repeat pattern
   - Modify `readtrain_dual_channel.c` to accept `num_reads` parameter (remove 8-read limit)
   - Add Python-side loop for `width_sweep_with_reads`

2. **Long-term (Flexibility)**:
   - Create `custom_segarb_dual_channel.c` for arbitrary waveforms
   - Python waveform builder that generates seg_arb arrays
   - Can handle any future test pattern requirements

---

## 📝 Required C Modules (Priority Order)

### **HIGH PRIORITY**

1. **Modify `pmu_retention_dual_channel.c` for `pulse_read_repeat`**
   - **Option A (Quick Fix)**: Remove min-8 requirement
     - Change line 266: `if (NumbMeasPulses < 2)` → `if (NumbMeasPulses < 1)`
     - Change line 39 in C header: `NumbMeasPulses, int, Input, 8, 8, 1000` → `NumbMeasPulses, int, Input, 1, 1, 1000`
     - Change Python validation: `if not (8 <= self.num_pulses <= 1000):` → `if not (1 <= self.num_pulses <= 1000):`
     - Use in Python loop: Call retention module N times with `NumPulses=1`, `NumbMeasPulses=1`
   - **Option B (Better)**: Add interleaved mode parameter
     - Add parameter: `interleaved_mode` (0=default retention, 1=interleaved pulse-read)
     - When interleaved: Pattern becomes Initial Read → (Pulse → Read) × N
     - Single C call, more efficient
   - **Priority**: HIGH (basic test pattern)

### **MEDIUM PRIORITY**

2. **`readtrain_dual_channel_variable_reads.c`** (or modify existing)
   - Modify to accept `num_reads` parameter (1-1000, not hardcoded to 8)
   - Used by: `multi_pulse_then_read`

3. **`relaxation_with_pulse_measurement.c`**
   - Pattern: 1×Read → N×Pulse(measured) → N×Read
   - Measure pulse peak currents during pulse sequence
   - Based on: `readtrain_dual_channel.c` with pulse measurement added

### **LOW PRIORITY**

4. **`current_range_finder.c`**
   - Test multiple current ranges
   - Recommend best range based on stability
   - Can also be done in Python (loop over ranges)

---

## 🔄 Python-Side Changes Needed

### In `keithley4200_kxci_scripts.py`:

1. **`width_sweep_with_reads()`** - Add loop:
   ```python
   all_results = []
   for width in pulse_widths:
       result = call_retention_module(width=width, ...)
       all_results.append(result)
       # Wait for completion
   return combine_results(all_results)
   ```

2. **`multi_pulse_then_read()`** - Handle N reads:
   - If `num_reads <= 8`: Call C module once
   - If `num_reads > 8`: Call C module multiple times or modify C to accept N

---

## 📊 Summary Table

| Test Name | Status | C Module Needed | Python Changes Needed |
|-----------|--------|----------------|----------------------|
| `relaxation_after_multi_pulse` | ✅ Working | None | None |
| `pulse_multi_read` | ✅ Working | None | None |
| `multi_read_only` | ✅ Working | None | None |
| `pulse_read_repeat` | ❌ Not Working | **NEW: `pulse_read_repeat_dual_channel.c`** | None |
| `multi_pulse_then_read` | ⚠️ Partial (8-read limit) | Modify existing or **NEW** | Handle N reads |
| `width_sweep_with_reads` | ⚠️ Partial | None | **Add loop over widths** |
| `width_sweep_with_all_measurements` | ❌ Not Working | **NEW: with pulse measurement** | None |
| `relaxation_after_multi_pulse_with_pulse_measurement` | ❌ Not Working | **NEW: with pulse measurement** | None |
| `current_range_finder` | ❌ Not Working | Optional (can do in Python) | Loop over ranges |

---

## 🚀 Next Steps

1. **Immediate**: Create `pulse_read_repeat_dual_channel.c` (HIGH priority)
2. **Short-term**: Modify `readtrain_dual_channel.c` to accept `num_reads` parameter
3. **Short-term**: Add Python loop for `width_sweep_with_reads`
4. **Medium-term**: Create `relaxation_with_pulse_measurement.c`
5. **Long-term**: Consider `custom_segarb_dual_channel.c` for maximum flexibility

---

## 📚 Reference C Modules

- **Template**: `pmu_retention_dual_channel.c` - Good starting point for new modules
- **Read Pattern**: `readtrain_dual_channel.c` - Shows read-only patterns
- **Low-level**: `retention_pulse_ilimit_dual_channel.c` - Shows current limit handling

