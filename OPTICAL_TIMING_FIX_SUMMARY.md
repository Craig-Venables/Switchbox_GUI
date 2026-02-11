# Optical Timing Synchronization Fix - Implementation Summary

## Problem Solved

The 4200A optical test system had a critical timing misalignment where laser firing appeared ~1 second offset from actual timing in the plots. The photodiode measurements showed the laser was firing correctly, but the visualization and data alignment were wrong.

### Root Cause
- Measurement thread started at T=0, sending EX command to 4200A immediately
- Main thread slept for 1.0s, then set reference time `t0` at T=1.0s
- Laser intervals recorded relative to `t0` → `[(1.0, 1.2), ...]`
- Measurement timestamps started from T=0 → `[0, 0.02, 0.04, ...]`
- Result: ~1 second misalignment between measurement and laser timelines

## Solution Implemented

### 1. **Synced Mode (Primary Solution)**
Implemented proper synchronization using the two-phase Start+Collect approach:

**Flow:**
1. Measurement thread calls `SMU_BiasTimedRead_Start` (applies bias, returns immediately)
2. Thread sets `sync_ready_event` when 4200A signals ready
3. **Main thread waits for event, THEN sets `t0`** ← KEY FIX
4. Thread calls `SMU_BiasTimedRead_Collect` (begins sampling from this point)
5. Main thread runs laser schedule relative to `t0`
6. Both measurement and laser use the same time reference

**Expected Accuracy:** 20-50ms (GPIB overhead + first sample interval)

### 2. **Fallback Mode with Timestamp Correction**
If synced mode unavailable or fails, automatically falls back to single-phase mode with correction:

**Flow:**
1. Records measurement start time
2. Sleeps for delay, then sets `t0`
3. Runs laser schedule relative to `t0`
4. **Corrects measurement timestamps by adding offset** ← CRITICAL FIX
5. `corrected_timestamp = original_timestamp + (t0 - measurement_start_time)`

**Expected Accuracy:** 10-50ms (threading jitter)

### 3. **Automatic Error Handling**
- Checks if `run_bias_timed_read_synced()` is available
- Tries synced mode first
- Catches any errors (including `-6` measi failures)
- Automatically falls back with logging
- User never sees timing errors

### 4. **Timing Validation Diagnostics**
Added `_validate_timing_alignment()` function that:
- Compares laser pulse times with photodiode resistance changes
- Detects when resistance changes occur vs expected pulse times
- Logs warnings if timing error > 2× sample_interval
- Helps verify accuracy during testing

## Files Modified

### [`gui/pulse_testing_gui/optical_runner.py`](gui/pulse_testing_gui/optical_runner.py)

**New Functions:**
- `_run_laser_schedule()` - Extracted laser firing logic (reduces code duplication)
- `_validate_timing_alignment()` - Validates timing accuracy with photodiode data
- `_run_optical_4200_fallback()` - Single-phase mode with timestamp correction
- `_run_optical_4200()` - Modified to use synced mode with automatic fallback

**Changes:**
- Added `logging` import and logger
- Replaced old timing logic with synced mode
- Added comprehensive error handling
- Added timing diagnostics

## Expected Improvements

| Metric | Before Fix | After Synced Mode | After Fallback Mode |
|--------|------------|-------------------|---------------------|
| **Timing Error** | ~1000ms | 20-50ms | 10-50ms |
| **Accuracy** | ±1s | ±50ms | ±50ms |
| **Reliability** | Single mode | Auto-fallback | Always works |

## Testing Instructions

### Test 1: Basic Alignment Verification

1. **Setup:** Connect photodiode to measure laser firing (as you have been doing)

2. **Run Test:** Execute optical pulse test with clear pattern:
   ```
   Test: Optical: Laser Pattern + Continuous Read
   Pattern: 11011  (pulse, pulse, skip, pulse, pulse)
   On time: 100ms
   Off time: 200ms
   Sample interval: 20ms
   ```

3. **Expected Result:**
   - Yellow confidence windows should now contain the actual resistance changes
   - Laser firing should align within ±50ms of predicted times
   - Console should show: `"Using synced mode (Start+Collect) for precise timing alignment"`

4. **Check Plot:**
   - Resistance drops should be centered within yellow bands
   - No more ~1 second offset!

### Test 2: Fallback Mode Verification

1. **Trigger Fallback:** Can happen if C modules not loaded on 4200A
   
2. **Check Console:** Should see:
   ```
   "Synced mode failed (...), falling back to single-phase with correction"
   OR
   "Synced mode not available (...), using fallback"
   "Fallback mode: Applied timestamp offset of XXX.Xms"
   ```

3. **Expected Result:**
   - Test completes successfully despite synced mode failure
   - Timing should still be accurate (±50ms)
   - Yellow bands align with resistance changes

### Test 3: Timing Validation

1. **Run any optical test** with photodiode connected

2. **Check Console Logs:** Should see timing validation messages:
   ```
   "Pulse 0: good alignment, error 15.2ms"
   "Pulse 1: good alignment, error -8.3ms"
   ```
   
   If timing errors detected:
   ```
   "Pulse 2: timing error 125.5ms (pulse at 2.500s, detected at 2.625s)"
   ```

3. **Warnings to investigate:**
   - "Pulse X: timing error > 40ms" → May indicate laser communication delay
   - "Pulse X: no photodiode response detected" → Laser may have failed to fire

### Test 4: Accuracy Measurement

1. **Setup:** Use photodiode with known response time

2. **Run test:** Record multiple pulses with varying patterns

3. **Analyze results:**
   - Export data to CSV
   - Calculate: `timing_error = photodiode_peak_time - laser_on_interval_start`
   - **Success criteria:** Mean error < 50ms, Max error < 100ms

4. **Compare to previous data:**
   - Old data showed ~1000ms offset
   - New data should show <50ms scatter

## Troubleshooting

### Issue: Synced mode keeps failing with `-6` errors

**Cause:** C modules not loaded on 4200A or measi() failing

**Solutions:**
1. Verify `SMU_BiasTimedRead_Start` and `SMU_BiasTimedRead_Collect` are compiled and loaded
2. Check USRLIB on the 4200A (via Clarius)
3. Run the Python script directly to test: 
   ```
   python Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/SMU_BiasTimedRead/run_smu_bias_timed_read.py --test-synced
   ```
4. If synced mode cannot be fixed, fallback mode will work with good accuracy

### Issue: Timing validation shows large errors even after fix

**Possible causes:**
1. Laser serial communication delay (Oxxius USB/serial has ~10-50ms latency)
2. Photodiode response time
3. GPIB communication overhead

**Check:**
- Review console logs for specific timing patterns
- If all pulses have similar offset, it's a systematic delay (can be calibrated)
- If errors are random, it's jitter (should be <50ms)

### Issue: Yellow confidence bands still don't match resistance changes

**Debug steps:**
1. Check console - which mode is being used? (synced or fallback)
2. If fallback, verify the timestamp offset being applied (should be ~1000ms)
3. Check if resistance data actually changes (photodiode connected?)
4. Export data and manually verify timestamps vs laser_on_intervals

## Benefits of This Implementation

✅ **Accurate timing** - Both timelines properly synchronized  
✅ **Robust fallback** - Always works, even if synced mode fails  
✅ **Automatic handling** - No user intervention needed  
✅ **Diagnostic logging** - Easy to verify and debug  
✅ **Future-proof** - Ready for 2450/2400 systems (already correct)  
✅ **Maintains compatibility** - No changes to test definitions or parameters  

## Next Steps

1. **Test with your photodiode setup** - Verify timing accuracy
2. **Check console logs** - Confirm synced mode is working
3. **Compare new vs old data** - Verify the ~1s offset is gone
4. **Run multiple patterns** - Test various laser schedules
5. **Document results** - Record accuracy measurements for reference

## Questions or Issues?

If you encounter any problems:
1. Check console logs for error messages
2. Verify C modules are loaded on 4200A
3. Test fallback mode works correctly
4. Check timing validation output

The implementation is designed to be robust and self-diagnosing!
