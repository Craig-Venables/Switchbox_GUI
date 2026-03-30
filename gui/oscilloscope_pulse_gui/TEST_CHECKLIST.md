# Oscilloscope Pulse GUI - Test Validation Checklist

## Pre-Testing Setup

- [ ] Python environment is set up with required packages (numpy, matplotlib, tkinter, pyvisa)
- [ ] VISA drivers are installed (NI-VISA or similar)
- [ ] Tektronix TBS1000C oscilloscope is powered on
- [ ] SMU (Keithley) is powered on and connected
- [ ] USB cables are connected to PC

---

## Test 1: Simulation Mode (No Hardware Required)

**Purpose**: Verify GUI, plotting, and data processing work without hardware.

### Steps:
1. [ ] Open the GUI: `python gui/oscilloscope_pulse_gui/main.py`
2. [ ] Check "🔧 Simulation Mode" checkbox
3. [ ] Set parameters:
   - Pulse Voltage: `1.0` V
   - Pulse Duration: `0.1` s
   - Pre-Pulse Delay: `0.1` s
   - Current Compliance: `0.001` A
   - R_shunt: `50` Ω
   - Record Length: `20` k
4. [ ] Click "▶ Start Measurement"
5. [ ] Wait for completion (~0.3 seconds)

### Expected Results:
- [ ] Status shows "Pulsing..." → "Acquiring data..." → "Done."
- [ ] Overview tab shows 4 plots:
  - Voltage Breakdown (V_SMU, V_shunt, V_memristor)
  - Current (smooth curve)
  - Resistance (shows memristor switching)
  - Power (bell-shaped curve)
- [ ] All plots show data (no blank plots)
- [ ] Time axis starts at 0 and covers ~0.3s
- [ ] Resistance plot shows transition from high to low resistance
- [ ] No errors in console

### Console Output Should Include:
```
✓ Auto-configuring oscilloscope for high-resolution capture...
    Record length: 5000 points
    Timebase: ...
    Sample rate: ...
```

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Test 2: Oscilloscope Connection

**Purpose**: Verify oscilloscope can be detected and connected.

### Steps:
1. [ ] Uncheck "🔧 Simulation Mode"
2. [ ] Verify Scope Address is correct (e.g., `USB0::0x0699::0x03C4::C023684::INSTR`)
3. [ ] Set Scope Type: `Tektronix TBS1000C`
4. [ ] Click "Refresh" next to Scope Address to scan for devices
5. [ ] If found, address should appear in dropdown

### Expected Results:
- [ ] No connection errors in console
- [ ] Scope is detected (if "Refresh" clicked)
- [ ] No error popups

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Test 3: SMU Connection

**Purpose**: Verify SMU can be connected.

### Steps:
1. [ ] Select System: `keithley4200a` (or your system)
2. [ ] Verify SMU Address is correct (e.g., `GPIB0::17::INSTR`)
3. [ ] Click "🔌 Connect SMU"
4. [ ] Wait for connection

### Expected Results:
- [ ] SMU status changes from "SMU: Not Connected" (red) → "SMU: Connected (KEITHLEY4200A)" (green)
- [ ] Success popup: "Connected to [IDN string]"
- [ ] No errors in console

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Test 4: Loopback Test (Oscilloscope Only)

**Purpose**: Test oscilloscope capture without device. Connect SMU directly to scope to verify trigger and acquisition.

### Physical Setup:
```
[SMU Hi] → [1kΩ Resistor] → [Scope CH1 Probe Tip]
[SMU Lo] → [Scope CH1 Probe Ground]
```

### GUI Settings:
- Pulse Voltage: `1.0` V
- Pulse Duration: `0.1` s
- Pre-Pulse Delay: `0.1` s
- Post-Pulse Hold: `0.1` s
- Current Compliance: `0.01` A (10mA - safe for 1kΩ)
- R_shunt: `1000` Ω (our test resistor)
- Record Length: `20` k
- Auto-configure scope: ✓ Checked
- Scope Channel: `CH1`

### Steps:
1. [ ] Set up physical connections as above
2. [ ] Configure GUI parameters
3. [ ] Click "▶ Start Measurement"
4. [ ] Observe console output during measurement
5. [ ] Wait for completion

### Expected Results:
- [ ] Console shows:
  ```
  ✓ Auto-configuring oscilloscope for high-resolution capture...
      Record length: 20000 points (max resolution)
      Timebase: 0.036000 s/div (36.000 ms/div)
      Total window: 0.360000 s
      Sample rate: 55555.556 Sa/s
      Resolution: 20000 points over 0.3000s pulse
  ```
- [ ] Console shows:
  ```
  Reading waveform from oscilloscope (already armed and triggered)...
    ✓ Captured 20000 points.
    Time window: 0.360000 s
    Sample interval: 1.800000e-05 s
    Effective sample rate: 55555.556 Sa/s
  ```
- [ ] Plots show:
  - V_shunt: Square pulse at ~1mV (1V / 1kΩ = 1mA × 1kΩ = 1V signal - wait, this is direct connection, should be 1V)
  - Actually, with direct connection, V_shunt = V_SMU = 1V
  - Current: 1mA flat during pulse (1V / 1kΩ)
  - Power: ~1mW during pulse
- [ ] No reconnection messages in console (CRITICAL!)
- [ ] Time axis shows full 0.3s window
- [ ] Clean square pulse (no ringing, no noise)

**Critical Check**: Console should NOT show:
```
❌ "Reconnecting to oscilloscope..." (THIS IS THE BUG WE FIXED!)
```

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Test 5: Real Device Measurement

**Purpose**: Test with actual memristor + shunt configuration.

### Physical Setup:
```
[SMU Hi] → [Memristor] → [Shunt Resistor] → [SMU Lo]
                              ↓
                        [Scope CH1]
                        [Scope GND] → [SMU Lo]
```

### GUI Settings:
- Pulse Voltage: `-1.0` V (or your device spec)
- Pulse Duration: `1.0` s (or your desired duration)
- Pre-Pulse Delay: `0.1` s
- Post-Pulse Hold: `0.1` s
- Current Compliance: `0.001` A (adjust for your device)
- R_shunt: `100000` Ω (100kΩ - adjust for your shunt)
- Record Length: `20` k
- Auto-configure scope: ✓ Checked
- Scope Channel: `CH1`

### Steps:
1. [ ] Set up physical connections
2. [ ] Start with LOW voltage (e.g., 0.5V) for safety
3. [ ] Configure GUI parameters
4. [ ] Click "▶ Start Measurement"
5. [ ] Observe console output
6. [ ] Check plots
7. [ ] Gradually increase voltage if needed

### Expected Results:
- [ ] Console shows configuration:
  ```
  ✓ Auto-configuring oscilloscope for high-resolution capture...
      Record length: 20000 points (max resolution)
      Timebase: [calculated based on your settings]
      Sample rate: [calculated] Sa/s
      Resolution: 20000 points over [total_time]s pulse
  ```
- [ ] Console shows acquisition:
  ```
  Reading waveform from oscilloscope (already armed and triggered)...
    ✓ Captured 20000 points.
    Time window: [time] s
    Effective sample rate: [rate] Sa/s
  ```
- [ ] Plots show:
  - V_shunt: Voltage across shunt (proportional to current)
  - V_memristor: Applied voltage minus shunt drop
  - Current: Smooth curve (derived from V_shunt / R_shunt)
  - Resistance: Memristor resistance over time (may show switching)
  - Power: Power dissipation curve
- [ ] All plots show realistic data (no spikes, no NaN, no flatlines)
- [ ] Time axis covers full measurement window
- [ ] Data makes physical sense

### Data Validation:
- [ ] Current calculation: `I = V_shunt / R_shunt` looks reasonable
- [ ] Resistance: `R = V_memristor / I` is in expected range (kΩ - MΩ)
- [ ] Power: `P = V_memristor × I` makes sense
- [ ] No large spikes or artifacts
- [ ] Switching behavior visible (if memristor switches)

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Test 6: Resolution Verification

**Purpose**: Verify we're actually getting 20k points at high resolution.

### Test 6a: Long Pulse (Low Sample Rate)
**Settings**:
- Pulse Duration: `10.0` s
- Pre/Post Delay: `0.1` s each
- Record Length: `20` k

**Expected**:
- [ ] Time window: ~12 s
- [ ] Sample rate: ~1,667 Sa/s
- [ ] Sample interval: ~600 µs
- [ ] 20,000 points captured

### Test 6b: Short Pulse (High Sample Rate)
**Settings**:
- Pulse Duration: `0.01` s (10 ms)
- Pre/Post Delay: `0.05` s each
- Record Length: `20` k

**Expected**:
- [ ] Time window: ~0.132 s
- [ ] Sample rate: ~152,000 Sa/s
- [ ] Sample interval: ~6.6 µs
- [ ] 20,000 points captured

### Verification:
- [ ] Both tests capture exactly 20,000 points
- [ ] Short pulse has higher sample rate (as expected)
- [ ] Console accurately reports these metrics

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Test 7: Trigger Validation

**Purpose**: Ensure trigger works reliably for different pulse polarities.

### Test 7a: Positive Pulse
- Pulse Voltage: `+1.0` V
- Trigger Slope: `RISING` (should auto-select)
- [ ] Measurement completes successfully
- [ ] Pulse appears in plot starting at ~0.1s (pre-delay)

### Test 7b: Negative Pulse
- Pulse Voltage: `-1.0` V
- Trigger Slope: `FALLING` (should auto-select)
- [ ] Measurement completes successfully
- [ ] Pulse appears in plot starting at ~0.1s (pre-delay)

### Test 7c: Trigger Sensitivity
- Pulse Voltage: `0.1` V (very small)
- [ ] Measurement completes (or shows sensible error if too small)
- [ ] If fails, check console for trigger warnings

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Test 8: Timebase Validation

**Purpose**: Verify timebase warnings work correctly.

### Test 8a: Auto Timebase (Recommended)
- Leave "Timebase (s/div)" field EMPTY
- Pulse Duration: `1.0` s, Pre: `0.1`, Post: `0.1`
- [ ] Tool auto-calculates timebase
- [ ] Console shows: "Timebase: [value] s/div (auto-calculated)"
- [ ] Full pulse captured in plots

### Test 8b: Manual Timebase (Sufficient)
- Set "Timebase (s/div)": `0.2` (200 ms/div)
- Pulse Duration: `1.0` s, Pre: `0.1`, Post: `0.1`
- Total window: `0.2 × 10 = 2.0s` (sufficient for 1.2s pulse)
- [ ] No warnings in console
- [ ] Full pulse captured

### Test 8c: Manual Timebase (Insufficient) ⚠️
- Set "Timebase (s/div)": `0.01` (10 ms/div)
- Pulse Duration: `1.0` s, Pre: `0.1`, Post: `0.1`
- Total window: `0.01 × 10 = 0.1s` (NOT sufficient for 1.2s pulse!)
- [ ] **Warning appears in console**:
  ```
  ⚠️ WARNING: Timebase too small!
     Current window: 0.1000s, Required: 1.2000s
     Recommended: 0.144000 s/div
  ```
- [ ] Tool overrides with recommended value (or measurement fails gracefully)

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Test 9: Data Save Functionality

**Purpose**: Verify data can be saved and loaded.

### Steps:
1. [ ] Complete a measurement (any test above)
2. [ ] Click "💾 Save" button
3. [ ] Choose filename: `test_pulse.txt`
4. [ ] Save file
5. [ ] Open `test_pulse.txt` in text editor

### Expected Results:
- [ ] File contains header with:
  - Timestamp
  - Device/Sample info
  - Measurement parameters
  - Calculated statistics (initial/final resistance, peak power, etc.)
- [ ] File contains data table:
  ```
  Time(s)  V_SMU(V)  V_shunt(V)  V_memristor(V)  Current(A)  R_memristor(Ω)  Power(W)
  [data rows...]
  ```
- [ ] All columns have data (no blank columns)
- [ ] Statistics make sense (resistance in kΩ-MΩ range, etc.)

### Test Auto-Save:
1. [ ] Check "Auto-save after measurement" checkbox
2. [ ] Run measurement
3. [ ] Check save directory (shown at top of GUI)
4. [ ] File is automatically created with timestamp filename

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Test 10: Stress Test

**Purpose**: Verify tool works reliably over multiple measurements.

### Steps:
1. [ ] Run 5 consecutive measurements with same settings
2. [ ] Run 5 measurements with different pulse durations
3. [ ] Run 5 measurements with different voltages

### Expected Results:
- [ ] All measurements complete successfully
- [ ] No memory leaks or slowdowns
- [ ] Data is consistent between runs
- [ ] No scope connection errors
- [ ] No SMU errors

**Status**: ✅ Pass / ❌ Fail  
**Notes**: _______________________________________________

---

## Critical Validation Checklist

### ✅ Must Pass:
- [ ] **Test 1** (Simulation Mode) - Verifies GUI works
- [ ] **Test 4** (Loopback Test) - Verifies oscilloscope capture works
- [ ] **Test 5** (Real Device) - Verifies full measurement chain
- [ ] **Console never shows "Reconnecting to oscilloscope..."** (critical bug check)
- [ ] **20,000 points captured** (resolution check)

### ⚠️ Should Pass:
- [ ] Test 2 (Scope Connection)
- [ ] Test 3 (SMU Connection)
- [ ] Test 6 (Resolution Verification)
- [ ] Test 7 (Trigger Validation)
- [ ] Test 8 (Timebase Validation)

### Nice to Have:
- [ ] Test 9 (Data Save)
- [ ] Test 10 (Stress Test)

---

## Known Issues to Watch For

### Issue 1: "No waveform captured"
**Symptoms**: Plots are empty, console shows "Captured 0 points"  
**Possible Causes**:
- Trigger level too high (pulse didn't reach threshold)
- Scope not armed before pulse
- Wrong channel selected
- Connections incorrect

**Debug Steps**:
1. Check console for trigger settings
2. Lower trigger_ratio in config (default 0.2 → try 0.1)
3. Verify physical connections
4. Test in simulation mode first

---

### Issue 2: "Waveform looks wrong"
**Symptoms**: Strange voltage levels, unexpected shape  
**Possible Causes**:
- Wrong R_shunt value entered
- Voltage scale incorrect
- Probe attenuation (if using 10x probe)

**Debug Steps**:
1. Verify R_shunt matches physical resistor
2. Check voltage scale in console output
3. Ensure using 1x probe (not 10x)

---

### Issue 3: "Low resolution"
**Symptoms**: Fewer than 20,000 points captured  
**Possible Causes**:
- Record Length not set to 20 in GUI
- Scope hardware limitation
- Acquisition mode incorrect

**Debug Steps**:
1. Set "Points (k)" to `20` in GUI
2. Check console for "Record length: 20000 points"
3. Verify scope is TBS1000C (supports 20k)

---

## Test Results Summary

**Date**: _______________  
**Tester**: _______________  
**Hardware**:
- Oscilloscope Model: _______________
- SMU Model: _______________
- Device Under Test: _______________
- Shunt Resistor: _______________

**Overall Status**: ✅ Pass / ⚠️ Pass with Issues / ❌ Fail

**Critical Issues Found**:
1. _______________________________________________
2. _______________________________________________
3. _______________________________________________

**Non-Critical Issues**:
1. _______________________________________________
2. _______________________________________________

**Recommendations**:
_______________________________________________
_______________________________________________
_______________________________________________

**Approved for Use**: ☐ Yes ☐ No ☐ With Conditions

**Signature**: _______________  **Date**: _______________

---

**End of Test Checklist**

