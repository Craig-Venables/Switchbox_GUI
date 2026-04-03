# Optical Tests Update Summary

## Overview
Added NEW optical test for **laser pattern control with continuous SMU read**. This allows you to control which laser pulses fire (using binary pattern like "11010") while the SMU reads continuously at a constant voltage.

**Key Point**: The electrical "Pulse Train with Varying Amplitudes" test is for memristor SET/RESET programming (electrical voltage pulses). For laser testing with continuous read, use the new **"Optical: Laser Pattern + Continuous Read"** test.

## Key Changes

### 1. **Renamed "Pulse Train with Varying Amplitudes" → "⚡ Electrical Pulse Train (Memristor Programming)"**
**File**: `Pulse_Testing/test_definitions.py`

- **Type**: ⚡ **SMU ELECTRICAL SET/RESET pulses** (NO laser, NO continuous read)
- **Purpose**: Sends electrical voltage pulses for memristor programming (1.5V, -2V, etc.)
- **NOT for optical testing**: This test is for electrical programming, not laser experiments
- **Updated Description**: Clearly states this is for "memristor programming" and directs users to optical tests for laser work

### 2. **Added "laser_delay_s" Parameter to ALL Optical Tests**
**Files**: 
- `Pulse_Testing/test_definitions.py`
- `gui/pulse_testing_gui/optical_runner.py`

Added `laser_delay_s` parameter to:
- **"Optical Read (Pulsed Light)"**: Default 1.0s
- **"Optical Pulse Train + Read"**: Default 1.0s
- **"Optical Pulse Train with Pattern + Read"**: Default 1.0s (NEW test)

**Purpose**: Allows user to delay laser start after SMU begins reading, ensuring proper synchronization.

**Implementation**:
- **2450/2400 Systems**: Laser firing starts after `laser_delay_s` seconds
- **4200A System**: Thread-based coordination with `laser_delay_s` controlling when laser fires after SMU starts

### 3. **NEW TEST: "🔬 Optical: Laser Pattern + Continuous Read"** ⭐
**Function**: `optical_pulse_train_pattern_read`

**✅ THIS IS THE TEST YOU WANT FOR LASER EXPERIMENTS!**

**Description**: 
- 🔬 SMU reads continuously at constant voltage (e.g., 0.2V)
- Oxxius laser fires pulses based on binary pattern
- **Pattern Control**: `1`=fire laser, `0`=skip pulse (e.g., `11111` = all 5 pulses, `10101` = alternating, `10000` = first only)
- **Workflow**: SMU starts reading → wait `laser_delay_s` → fire laser pulses per pattern → continue reading

**Parameters**:
- `read_voltage`: Constant SMU read voltage (V)
- `num_laser_pulses`: Number of pulse slots (pattern length must match)
- `laser_pattern`: Binary pattern (e.g., "11111", "10101")
- `laser_delay_s`: Delay before laser starts (s)
- `optical_on_ms`: Laser on duration when pattern is '1' (ms)
- `optical_off_ms`: Time between pulse slots (ms)
- `duration_s`: Total test duration (s)
- `sample_interval_s`: SMU sampling interval (s)
- `clim`: Current limit (A)

**Error Handling**:
- Validates pattern length matches `num_laser_pulses`
- Shows clear error: "Laser pattern has X digit(s) but Number of laser pulse slots is Y. Remove/Add Z digit(s)."
- Validates pattern contains only '0' and '1' characters

### 4. **Updated Test Descriptions**
All optical test descriptions now:
- Use 🔬 emoji to clearly identify optical (laser + SMU) tests
- Explicitly state workflow: "SMU starts reading → (wait laser_delay) → laser fires → continue reading"
- Clarify requirements: "Requires: SMU connected (Connection) and Oxxius laser connected (Laser Control)"

## Files Modified

### Core Files
1. **`Pulse_Testing/test_definitions.py`**
   - Updated "Pulse Train with Varying Amplitudes" description (clarify SMU-only)
   - Added `laser_delay_s` to "Optical Read (Pulsed Light)"
   - Added `laser_delay_s` to "Optical Pulse Train + Read"
   - Added new test "Optical Pulse Train with Pattern + Read"

2. **`Pulse_Testing/test_capabilities.py`**
   - Added `optical_pulse_train_pattern_read` to `ALL_TEST_FUNCTIONS`
   - Enabled for all systems (keithley2450, keithley4200a, keithley2400)

3. **`gui/pulse_testing_gui/optical_runner.py`**
   - Added `optical_pulse_train_pattern_read` to `OPTICAL_TEST_FUNCTIONS`
   - Updated `run_optical_test()` to handle new function
   - Added `_run_optical_pulse_train_pattern_read()` implementation
   - Updated `_run_optical_4200()` to use `laser_delay_s` parameter
   - Updated `_run_optical_read_pulsed_light()` to support `laser_delay_s`
   - Updated `_run_optical_pulse_train_read()` to support `laser_delay_s`

## Test Comparison

| Test Name | SMU Behavior | Laser Used? | Pattern Control | Use For |
|-----------|--------------|-------------|-----------------|---------|
| **⚡ Electrical Pulse Train (Memristor)** | Sends voltage pulses | ❌ NO | ✅ Binary (11010) | Memristor programming |
| **Optical Read (Pulsed Light)** | Continuous read | ✅ YES | ❌ (periodic) | Laser pulses at fixed intervals |
| **Optical Pulse Train + Read** | Continuous read | ✅ YES | ❌ (all N pulses) | N consecutive laser pulses |
| **🔬 Optical: Laser Pattern + Read** ⭐ (NEW) | **Continuous read** | ✅ **YES** | ✅ **Binary (11010)** | **Control which laser pulses fire!** |

## Usage Examples

### Example 1: Electrical Memristor Programming (NOT for optical experiments)
```
Test: "⚡ Electrical Pulse Train (Memristor Programming)"
num_pulses: 5
pulse_pattern: "11010"
pulse_voltage: 2.0V
→ Result: SMU sends electrical voltage pulses (2V, 2V, 0V, 2V, 0V) for SET/RESET
⚠️ This is NOT what you want for laser experiments!
```

### Example 2: Optical Laser Pattern + Continuous Read ⭐ (WHAT YOU WANT!)
```
Test: "🔬 Optical: Laser Pattern + Continuous Read"
read_voltage: 0.2V  (SMU reads continuously at this voltage)
num_laser_pulses: 5
laser_pattern: "11010"
optical_on_ms: 100
→ Result: SMU reads at 0.2V continuously, laser fires 100ms pulses at slots 0,1,3 (skip 2,4)
✅ This is the correct test for laser experiments!
```

### Example 3: Optical Pulse Train with Pattern (alternate syntax)
```
Test: "Optical Pulse Train with Pattern + Read"
num_laser_pulses: 5
laser_pattern: "11010"
laser_delay_s: 1.0
optical_on_ms: 100
optical_off_ms: 200
→ Result: SMU reads continuously, laser fires 100ms pulses at t=1.0s, 1.3s, 1.9s (skip slots 2,4)
```

### Example 3: Delayed Laser Pulsing
```
Test: "Optical Read (Pulsed Light)"
laser_delay_s: 2.0
optical_pulse_duration_s: 0.2
optical_pulse_period_s: 1.0
total_time_s: 10.0
→ Result: SMU starts reading at t=0, laser fires first pulse at t=2.0s, then every 1.0s
```

## Backward Compatibility
✅ All existing tests remain unchanged
✅ `laser_delay_s` has default value (1.0s for 4200A, 0.0s for 2450/2400)
✅ Existing presets will work (new parameter uses default if not present)

## Testing Checklist
- [ ] Test "Pulse Train with Varying Amplitudes" (SMU electrical, no laser)
- [ ] Test "Optical Read (Pulsed Light)" with laser_delay_s
- [ ] Test "Optical Pulse Train + Read" with laser_delay_s
- [ ] Test "Optical Pulse Train with Pattern + Read" (NEW)
  - [ ] Pattern "11111" (all pulses)
  - [ ] Pattern "10101" (alternating)
  - [ ] Pattern "10000" (first only)
  - [ ] Validation: pattern length mismatch
- [ ] Test on Keithley 2450/2400 (direct laser control)
- [ ] Test on Keithley 4200A (thread-based coordination)
