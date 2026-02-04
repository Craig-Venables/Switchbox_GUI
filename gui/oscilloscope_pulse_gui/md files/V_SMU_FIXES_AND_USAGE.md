# V_SMU Display and Alignment Fixes - User Guide

**Date**: December 15, 2025  
**Version**: 2.1

---

## 🎯 What Was Fixed

### **Problem 1: V_SMU Not Displaying Correctly**

**Issue**: V_SMU was not showing correctly and didn't align with the measured oscilloscope pulse.

**Root Causes**:
1. V_SMU was an idealized reconstruction from parameters, but users expected to see actual SMU output
2. Pulse timing detection was unreliable, causing misalignment
3. Labels and documentation didn't clearly explain what V_SMU represents
4. No clear visual distinction between measured vs. calculated data

**Fixes Applied**:
1. ✅ **Improved Pulse Detection Algorithm**
   - Added `_detect_pulse_start_improved()` method with multiple detection strategies
   - Uses threshold crossing + derivative analysis for robust detection
   - Handles both positive and negative pulses correctly
   - Auto-detects baseline offset for DC level correction

2. ✅ **Enhanced V_SMU Generation**
   - Clearer documentation explaining V_SMU is reconstructed (not measured)
   - Uses detected pulse timing from measured waveform for better alignment
   - Properly handles bias_voltage, pulse_voltage, and timing windows

3. ✅ **Improved Visualization**
   - V_SMU displayed as **green dashed line** (clearly marked as reference)
   - V_shunt displayed as **blue solid line** (measured data from scope)
   - V_DUT displayed as **red solid line** (calculated across device)
   - Added yellow annotation: "V_SMU is reconstructed from parameters (not measured)"
   - Updated plot titles with clear explanations

4. ✅ **Better Labeling**
   - Changed confusing names: "V_memristor" → "V_DUT" (voltage across device)
   - Clear titles: "V_SMU (Programmed Reference)" vs "V_shunt (Measured from Scope)"
   - Added comprehensive docstring in `update_plots()` explaining measurement model

---

### **Problem 2: Alignment System Didn't Work Correctly**

**Issue**: Alignment controls were confusing and didn't work intuitively.

**Root Causes**:
1. Too many timing parameters without clear workflow
2. No guidance on which controls to use when
3. Auto-fit algorithm was unreliable
4. Unclear relationship between main parameters and alignment parameters

**Fixes Applied**:
1. ✅ **Simplified Workflow with Step-by-Step Guidance**
   ```
   Step 1: Load Params → Step 2: Auto-Fit → Step 3: Fine-tune → Step 4: Apply
   ```
   - Numbered buttons (1️⃣, 2️⃣, 3️⃣, 4️⃣) guide user through process
   - Each button has tooltip explaining its purpose
   - Clear visual grouping of controls

2. ✅ **Improved Auto-Fit Algorithm**
   - Uses new `_detect_pulse_start_improved()` method
   - Auto-detects and corrects baseline offset (zero_offset)
   - Auto-detects pulse duration from waveform
   - Calculates required time shift for alignment
   - Prints helpful debug messages

3. ✅ **Added Help Text and Tooltips**
   - Help text at top explains what alignment does
   - Tooltips on all buttons
   - Explanatory labels on timing and offset sections
   - Visual distinction between "programmed" vs "measured" data

4. ✅ **Better Visual Feedback**
   - Alignment tab shows both V_SMU and V_shunt overlayed
   - Pulse window highlighted with green shaded region
   - Vertical lines mark pulse start/end
   - Preview updates in real-time as you adjust controls

---

## 📊 Understanding the Measurement Model

### Circuit Configuration

```
[SMU Hi] → [Device Under Test] → [Shunt Resistor] → [SMU Lo]
                                         ↓
                                  [Oscilloscope CH1]
                                  [Scope GND] → [SMU Lo]
```

### What We Measure

- **V_shunt**: Voltage across shunt resistor (measured by oscilloscope)
  - This is the ONLY direct measurement we have
  - Blue solid line in plots

### What We Calculate

- **I** (Current): `I = V_shunt / R_shunt`
  - Ohm's law applied to measured voltage
  - Accurate because R_shunt is known and stable

- **V_DUT** (Voltage across device): `V_DUT = V_SMU - V_shunt`
  - Kirchhoff's voltage law: total voltage = device voltage + shunt voltage
  - Red solid line in plots

- **R_DUT** (Device resistance): `R_DUT = V_DUT / I`
  - Ohm's law applied to calculated values
  - Shows device resistance over time

- **P_DUT** (Power dissipated): `P_DUT = V_DUT × I`
  - Power dissipated in device only (not shunt)

### What is V_SMU?

**V_SMU is NOT measured** - it's reconstructed from pulse parameters:

```
V_SMU = {
    0 V               (before pre-bias)
    bias_voltage      (during pre-bias)
    pulse_voltage     (during pulse)
    bias_voltage      (during post-bias)
    0 V               (after post-bias)
}
```

**Why reconstruct V_SMU?**
- We only have 1 oscilloscope channel (measuring V_shunt)
- V_SMU provides a reference to see what we PROGRAMMED vs what we MEASURED
- Helps identify issues: if V_shunt doesn't match expected shape, something is wrong
- Useful for alignment and validation

**Limitations**:
- V_SMU is idealized (perfect square wave)
- Real SMU output may have:
  - Rise/fall times
  - Overshoot/ringing
  - Noise
  - Settling time
- For exact SMU output, you'd need a 2-channel scope

---

## 🎯 How to Use the Improved System

### Basic Measurement Workflow

1. **Set Up Hardware**
   ```
   Connect: SMU → Device → Shunt → SMU
   Connect: Oscilloscope CH1 across Shunt
   Connect: Oscilloscope GND to SMU Lo
   ```

2. **Configure Parameters**
   - Pulse Voltage: Your desired voltage (e.g., 2V)
   - Pulse Duration: How long to pulse (e.g., 1s)
   - Bias Voltage: Pre/post bias level (e.g., 0.2V)
   - Pre-Bias Time: Time before pulse (e.g., 1s)
   - Post-Bias Time: Time after pulse (e.g., 0s for 4200A)
   - R_shunt: Your actual shunt resistor value (CRITICAL!)

3. **Run Measurement**
   - Click "▶ Start Measurement"
   - Wait for completion
   - Check plots - V_shunt (blue) should show clean pulse

4. **Verify Results**
   - V_shunt matches expected amplitude?
   - V_SMU (green dashed) aligns with V_shunt?
   - Current calculation makes sense?
   - If not aligned, use Alignment tab

---

### Using the Alignment Tab

**When to Use**:
- V_SMU (green dashed) doesn't line up with V_shunt (blue solid)
- Pulse timing detection failed
- Need to fine-tune alignment manually
- Want to see how programmed vs measured compare

**Step-by-Step Workflow**:

1. **Click "1️⃣ Load Params"**
   - Loads timing from Pulse Parameters tab
   - Sets pre-bias time, pulse duration, post-bias time
   - Provides starting point for alignment

2. **Click "2️⃣ Auto-Fit"**
   - Automatically detects pulse in measured waveform
   - Corrects baseline offset (DC level)
   - Aligns V_SMU to detected pulse
   - Prints detection results to console
   - **Try this first before manual adjustment!**

3. **Fine-Tune Manually (if needed)**
   - **Time Shift slider**: Move V_SMU left/right to align with pulse start
   - **Voltage Shift slider**: Adjust baseline level if V_shunt is offset
   - **Timing sliders**: Adjust pulse duration, pre-bias, post-bias if needed
   - Preview updates in real-time

4. **Click "4️⃣ Apply Changes"**
   - Recalculates all plots with new alignment
   - Updates Overview and individual tabs
   - New values used for V_DUT, R_DUT, P_DUT calculations

**Tips**:
- Auto-Fit works best with clean signals (good SNR)
- If Auto-Fit fails, check console for error messages
- Start with small manual adjustments (±0.1s time shift)
- Use "↻ Reset All" to start over

---

### Troubleshooting Guide

#### **Problem: V_SMU and V_shunt don't align**

**Symptoms**:
- Green dashed line (V_SMU) starts at wrong time
- Pulse shapes don't overlap properly

**Solutions**:
1. Use Alignment tab → Click "2️⃣ Auto-Fit"
2. If Auto-Fit doesn't work:
   - Check pulse is visible in plot
   - Verify pulse_voltage parameter is correct
   - Manually adjust "Time Shift" slider
   - Check "Voltage Shift" if baseline is offset

#### **Problem: V_shunt looks wrong**

**Symptoms**:
- Unexpected amplitude
- Wrong polarity
- No pulse visible

**Solutions**:
1. **Check R_shunt value** - MOST COMMON ERROR
   - Verify resistor value with multimeter
   - Update "R_shunt" parameter in GUI
   - Remember: V_shunt should be small (mV to V range)

2. **Check scope connections**
   - CH1 probe connected across shunt
   - GND connected to SMU Lo

3. **Check scope settings**
   - Voltage scale appropriate for signal
   - Timebase covers full pulse
   - Trigger working properly

#### **Problem: Current calculation seems wrong**

**Symptoms**:
- Current too high/low
- Current negative when should be positive

**Solutions**:
1. **Verify R_shunt** - Current = V_shunt / R_shunt
   - If R_shunt is 10x wrong, current will be 10x wrong!
   - Use actual measured resistor value

2. **Check V_shunt polarity**
   - If V_shunt is negative when expected positive, check:
     - Scope probe orientation
     - SMU output polarity
     - Device orientation

3. **Check for measurement artifacts**
   - Noise spikes
   - Scope offset error
   - Use "Voltage Shift" in Alignment tab to correct DC offset

#### **Problem: V_DUT is negative or zero**

**Symptoms**:
- V_DUT (red line) shows negative values
- V_DUT close to zero during pulse

**Solutions**:
1. **Check V_SMU alignment**
   - V_DUT = V_SMU - V_shunt
   - If V_SMU is misaligned, V_DUT will be wrong
   - Use Auto-Fit to correct alignment

2. **Verify pulse_voltage parameter**
   - Must match what SMU actually outputs
   - Check SMU front panel or software

3. **Check if device is functioning**
   - If device has very low resistance, most voltage drops across shunt
   - V_DUT will be very small
   - This is normal for low-resistance devices

---

## 📈 Example: Typical Good Measurement

### Parameters Used
```
Pulse Voltage: 2.0 V
Pulse Duration: 1.0 s
Bias Voltage: 0.2 V
Pre-Bias Time: 1.0 s
Post-Bias Time: 0.0 s (4200A uses pre-bias for both)
R_shunt: 100 kΩ
```

### Expected Results

**Voltage Plot**:
- V_SMU (green dashed): 0V → 0.2V (pre-bias) → 2.0V (pulse) → 0.2V → 0V
- V_shunt (blue solid): Small signal (mV range), similar shape
- V_DUT (red solid): ~2V during pulse (most voltage across device)

**Current Plot**:
- Smooth curve
- Amplitude: µA to mA range (depends on device)
- Shape follows pulse

**Resistance Plot**:
- May show memristor switching (high → low or low → high)
- Values: kΩ to MΩ range typical
- Annotated with initial/final resistance

**Power Plot**:
- Peak during pulse
- Smooth curve
- Annotated with peak power

**Console Output**:
```
Auto-fit complete: pulse starts at 1.000000s, duration 1.000000s, offset 0.000000s
✓ Captured 20000 points
✓ Measurement Complete
```

---

## 🔧 Advanced: Understanding the Code Changes

### Key Functions Modified

1. **`_detect_pulse_start_improved()`** (NEW)
   - Multi-method pulse detection
   - Handles positive and negative pulses
   - Baseline correction
   - Robust to noise

2. **`_create_v_smu_waveform()`** (IMPROVED)
   - Better documentation
   - Clearer parameter names
   - Proper bias/pulse voltage handling

3. **`update_plots()`** (IMPROVED)
   - Comprehensive docstring explaining measurement model
   - Better pulse detection integration
   - Clearer variable names (v_memristor → v_DUT)

4. **`_auto_fit_pulse()`** (IMPROVED)
   - Uses new detection algorithm
   - Auto-corrects baseline
   - Prints debug information

5. **Plot styling** (IMPROVED)
   - Dashed vs solid lines
   - Color coding (green=programmed, blue=measured, red=calculated)
   - Annotations explaining what each trace represents

### New Features

- Real-time alignment preview
- Step-by-step workflow guidance
- Tooltips on all controls
- Better error messages
- Debug output for troubleshooting

---

## 📝 Important Notes

### What V_SMU Represents

**V_SMU is a REFERENCE waveform**, not a measurement:
- ✅ Use it to verify pulse timing is correct
- ✅ Use it to see if measured pulse matches expected shape
- ✅ Use it for alignment and validation
- ❌ Don't expect it to match real SMU output exactly (it's idealized)
- ❌ Don't use it for precise timing analysis (use V_shunt for that)

### Accuracy Considerations

**Most Accurate**:
- I (current): Calculated from measured V_shunt and known R_shunt
- V_shunt: Direct oscilloscope measurement

**Depends on Alignment**:
- V_DUT: Requires accurate V_SMU alignment
- R_DUT: Depends on both I and V_DUT accuracy
- P_DUT: Depends on both I and V_DUT accuracy

**Best Practices**:
1. Always use Auto-Fit for consistent alignment
2. Verify R_shunt value with multimeter
3. Check alignment visually in Alignment tab
4. Use multiple measurements and average if critical
5. For precise device characterization, consider 2-channel scope to measure both V_SMU and V_shunt

---

## 🚀 Quick Reference Card

### Running a Measurement
1. Connect hardware (SMU → Device → Shunt → SMU, Scope across Shunt)
2. Set pulse parameters (voltage, duration, timing, R_shunt)
3. Click "▶ Start Measurement"
4. Verify plots look reasonable
5. If misaligned, go to Alignment tab

### Using Alignment Tab
1. Click "1️⃣ Load Params" (loads from Pulse Parameters tab)
2. Click "2️⃣ Auto-Fit" (automatic detection and alignment)
3. Fine-tune manually if needed (Time Shift, Voltage Shift sliders)
4. Click "4️⃣ Apply Changes" (recalculate with new alignment)

### Verifying Results
- V_shunt (blue) should show clean pulse shape
- V_SMU (green dashed) should align with V_shunt start time
- V_DUT (red) should be positive during pulse
- Current should make sense given device resistance
- Resistance plot should show device behavior

### Common Mistakes
- ❌ Wrong R_shunt value → Wrong current calculation
- ❌ Not using Auto-Fit → V_SMU misaligned
- ❌ Expecting V_SMU to be measured → It's calculated!
- ❌ Ignoring alignment → Wrong V_DUT/R_DUT/P_DUT

---

## 📞 Getting Help

If measurements still don't look right:

1. **Check Console Output**
   - Error messages
   - Pulse detection results
   - Scope configuration

2. **Use Simulation Mode**
   - Test GUI without hardware
   - Verify plotting works
   - Check calculations

3. **Test with Known Resistor**
   - Replace device with known resistor
   - V_shunt should match Ohm's law
   - Validates measurement chain

4. **Check Physical Connections**
   - Multimeter resistance check
   - Scope probe check
   - Cable continuity

---

**End of Guide**

For more detailed information, see:
- `FIXES_AND_USAGE.md` - Original scope configuration guide
- `TEST_CHECKLIST.md` - Comprehensive testing procedures
- `walkthrough.md.resolved` - Historical context

**Remember**: V_SMU is a reconstructed reference, not measured data. The real measured signal is V_shunt (blue). Use alignment to make V_SMU match V_shunt for accurate calculations!







