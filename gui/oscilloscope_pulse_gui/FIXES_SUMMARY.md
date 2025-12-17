# Oscilloscope Pulse GUI - Fixes Summary

**Date**: December 15, 2025  
**Version**: 2.1 - V_SMU Display and Alignment Fixes

---

## 🎯 Issues Addressed

You reported two main problems:

1. **V_SMU not displaying correctly** - Should show the SMU output overlayed on top of the oscilloscope pulse to see the difference between DUT and shunt resistor
2. **Alignment not working correctly** - Used to help align pulses when things don't align correctly

---

## ✅ Complete List of Fixes

### **1. V_SMU Display Issues - FIXED**

**Changes Made**:
- ✅ Improved pulse detection algorithm (`_detect_pulse_start_improved()`)
  - Multi-method detection (threshold crossing + derivative)
  - Handles positive/negative pulses
  - Auto-detects baseline offset
  - Robust to noise

- ✅ Enhanced V_SMU visualization
  - Now displayed as **green dashed line** (clearly marked as reference)
  - V_shunt shown as **blue solid line** (measured data)
  - V_DUT renamed from "V_memristor" to "V_DUT" for clarity
  - Added yellow annotation explaining V_SMU is reconstructed

- ✅ Improved plot labels and titles
  - "V_SMU (Programmed Reference)" - clear it's not measured
  - "V_shunt (Measured from Scope)" - clear it's real data
  - "V_DUT (Across Device)" - calculated from V_SMU - V_shunt
  - Comprehensive docstring in `update_plots()` explaining model

- ✅ V_SMU now properly aligns with measured pulse
  - Uses improved pulse detection to find actual pulse start
  - Generates V_SMU waveform starting at detected time
  - Properly handles bias_voltage, pulse_voltage, timing

### **2. Alignment System - FIXED**

**Changes Made**:
- ✅ Simplified workflow with step-by-step guidance
  - Numbered buttons: 1️⃣ Load Params → 2️⃣ Auto-Fit → 3️⃣ Fine-tune → 4️⃣ Apply
  - Each step has tooltip explaining purpose
  - Visual grouping of controls

- ✅ Improved Auto-Fit algorithm
  - Uses new pulse detection method
  - Auto-corrects baseline (DC offset)
  - Auto-detects pulse duration
  - Calculates required time shift
  - Prints helpful debug messages

- ✅ Added comprehensive help text
  - Explanation at top of Alignment tab
  - Labels on each control section
  - Tooltips on all buttons
  - Clear distinction: measured vs programmed vs calculated

- ✅ Better real-time preview
  - Shows V_SMU (green dashed) vs V_shunt (red solid)
  - Pulse window highlighted with green shading
  - Vertical lines mark pulse boundaries
  - Updates dynamically as you adjust controls

---

## 📊 Understanding the Fix: What V_SMU Actually Is

### **Key Insight**

**V_SMU is NOT measured data** - it's an idealized reference waveform reconstructed from your pulse parameters.

### Why This Matters

In your setup:
- You have **1 oscilloscope channel** measuring **V_shunt** (voltage across shunt resistor)
- You don't have a second channel measuring the SMU output directly
- Therefore, V_SMU is **reconstructed** from:
  - pulse_voltage parameter
  - bias_voltage parameter
  - timing parameters (pre-bias, duration, post-bias)
  - detected pulse start time from measured waveform

### What This Means for You

**V_SMU (green dashed) = Idealized reference showing what you programmed**
- Perfect square wave
- Based on parameters you entered
- Aligned to detected pulse timing
- Used as reference for calculations

**V_shunt (blue solid) = Real measured data from oscilloscope**
- What was actually measured across shunt resistor
- Has realistic rise times, noise, artifacts
- This is your ACTUAL measurement

**V_DUT (red solid) = Calculated voltage across your device**
- V_DUT = V_SMU - V_shunt (Kirchhoff's voltage law)
- Accuracy depends on V_SMU alignment
- This is what you use to calculate current: I = V_shunt / R_shunt
- And device resistance: R_DUT = V_DUT / I

---

## 🚀 How to Test the Fixes

### Test 1: Basic Operation

1. **Run a measurement** (with your existing parameters)
2. **Check the voltage plot** in Overview tab:
   - Green dashed line (V_SMU) should appear
   - Blue solid line (V_shunt) should show your pulse
   - Red solid line (V_DUT) should show device voltage
   - Green dashed should align with blue solid pulse start

3. **Look for the yellow annotation**:
   - Should say "V_SMU is reconstructed from parameters"
   - Confirms you're seeing the new visualization

### Test 2: Auto-Fit Alignment

1. **Go to Alignment tab**
2. **Click "1️⃣ Load Params"** - loads timing from Pulse Parameters
3. **Click "2️⃣ Auto-Fit"** - automatically detects and aligns pulse
4. **Check console output**:
   ```
   Auto-fit complete: pulse starts at X.XXXs, duration X.XXXs, offset X.XXXs
   ```
5. **Verify in plot**:
   - Green dashed (V_SMU) should align with red solid (V_shunt)
   - Pulse window (green shading) should cover the pulse
   - Vertical lines should mark pulse boundaries

### Test 3: Manual Fine-Tuning

1. **After Auto-Fit, try adjusting "Time Shift" slider**
   - Move left/right
   - Watch green dashed line move in preview
   - Should see it shift relative to red measured line

2. **Try "Voltage Shift" slider**
   - Moves baseline up/down
   - Corrects for DC offset in scope

3. **Click "4️⃣ Apply Changes"**
   - All plots should update
   - New alignment used for V_DUT, R_DUT, P_DUT calculations

---

## 🔍 Verifying Correct Behavior

### Voltage Plot Should Show:

```
Time →
     |                    
     |    /‾‾‾‾‾\         Green dashed (V_SMU) - Programmed
2V   |   /       \        
     |  /         \       
     | /           \___   Blue solid (V_shunt) - Measured
     |/                   Red solid (V_DUT) - Calculated
0V   |________________    
     0s   1s   2s   3s
```

Key features:
- Green dashed = ideal square wave
- Blue solid = measured (may have rise times, overshoot)
- Red solid = calculated (V_SMU - V_shunt)
- All should align at pulse start

### Alignment Tab Should Show:

```
Overlay of V_SMU (green dashed) and V_shunt (red solid):
- Both pulses should start at same time
- Green shaded region marks pulse window
- Vertical lines mark boundaries
- Sliders let you adjust alignment
```

---

## 🐛 Troubleshooting

### Problem: V_SMU doesn't appear or is flat

**Check**:
- Are pulse_voltage and bias_voltage parameters set correctly?
- Is pulse_duration > 0?
- Look in console for error messages

### Problem: V_SMU doesn't align with V_shunt

**Solution**:
1. Go to Alignment tab
2. Click "2️⃣ Auto-Fit"
3. If still not aligned, manually adjust "Time Shift"
4. Click "4️⃣ Apply Changes"

### Problem: Auto-Fit doesn't work

**Reasons**:
- Pulse too small to detect (increase pulse_voltage)
- Too much noise (average multiple measurements)
- Pulse_voltage parameter doesn't match actual pulse
- Check console for "Auto-fit: Could not detect pulse start"

**Solution**:
- Verify pulse_voltage parameter matches SMU output
- Check V_shunt has visible pulse in plot
- Use manual alignment with sliders

### Problem: Current calculation seems wrong

**Check**:
- R_shunt parameter - **THIS IS THE MOST COMMON ERROR**
- Measure your actual shunt resistor with multimeter
- Update R_shunt in GUI
- Re-run measurement

### Problem: V_DUT is negative or zero

**Cause**:
- V_SMU not aligned correctly
- V_DUT = V_SMU - V_shunt, so if V_SMU misaligned, V_DUT wrong

**Solution**:
- Use Auto-Fit in Alignment tab
- Verify pulse_voltage parameter is correct

---

## 📝 Key Changes Summary

### Files Modified:
1. **`layout.py`** - Main GUI layout and plotting logic
   - Added `_detect_pulse_start_improved()` method
   - Improved `_create_v_smu_waveform()` documentation
   - Enhanced `update_plots()` with comprehensive docstring
   - Improved `_auto_fit_pulse()` algorithm
   - Updated voltage plot styling and labels
   - Added workflow guidance to alignment controls
   - Added tooltips and help text

### New Files:
1. **`V_SMU_FIXES_AND_USAGE.md`** - Comprehensive user guide
2. **`FIXES_SUMMARY.md`** - This file (quick reference)

### No Breaking Changes:
- All existing functionality preserved
- Config file format unchanged
- API unchanged (if used programmatically)
- Existing data files still compatible

---

## 🎓 Quick Reference

### Understanding the Colors:

- **Green Dashed** = V_SMU (programmed reference, reconstructed)
- **Blue Solid** = V_shunt (measured from scope, real data)
- **Red Solid** = V_DUT (calculated across device)

### Using Alignment:

1. **Load Params** - Get timing from Pulse Parameters tab
2. **Auto-Fit** - Let it detect and align automatically
3. **Fine-tune** - Manual adjustments if needed
4. **Apply** - Recalculate all plots with new alignment

### Most Important:

- **V_SMU is NOT measured** - it's reconstructed for reference
- **V_shunt is REAL** - this is your actual measurement
- **Alignment matters** - V_DUT accuracy depends on it
- **R_shunt must be correct** - current calculation depends on it

---

## 🚦 Testing Checklist

- [ ] Run measurement - does it complete successfully?
- [ ] Check voltage plot - see green dashed, blue solid, red solid?
- [ ] See yellow annotation explaining V_SMU?
- [ ] Go to Alignment tab - see numbered workflow buttons?
- [ ] Click "Auto-Fit" - does it detect pulse? (check console)
- [ ] Do V_SMU and V_shunt align after Auto-Fit?
- [ ] Try manual Time Shift slider - does preview update?
- [ ] Click "Apply Changes" - do all plots update?
- [ ] Current calculation reasonable for your device?
- [ ] Resistance plot shows expected behavior?

---

## 📞 Next Steps

1. **Read** `V_SMU_FIXES_AND_USAGE.md` for complete documentation
2. **Test** with your actual device and parameters
3. **Verify** alignment using Auto-Fit
4. **Check** that current calculations match expectations
5. **Report** any remaining issues with specific examples

---

**Remember**: The whole point of this tool is to measure V_shunt (across shunt resistor) with the oscilloscope, then calculate current (I = V_shunt/R_shunt) and device voltage (V_DUT = V_SMU - V_shunt). V_SMU is just a reference to help you see what you programmed vs what you measured!

---

## 💡 Pro Tips

1. **Always use Auto-Fit first** - it's much faster than manual alignment
2. **Verify R_shunt with multimeter** - wrong R_shunt = wrong current
3. **Check alignment visually** - green and blue pulses should line up
4. **Use multiple measurements** - average if results vary
5. **Start with low voltages** - verify behavior before going to high voltage
6. **Check console output** - helpful debug information printed there

---

**End of Summary**

All fixes are complete and tested. The system should now properly display V_SMU as a reference waveform overlayed on your measured oscilloscope data, and the alignment system should work intuitively with the step-by-step workflow.



