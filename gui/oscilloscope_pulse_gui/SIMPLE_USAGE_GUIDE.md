# Oscilloscope Pulse GUI - Simple Usage Guide

**Version**: 2.2 - Simplified Manual Workflow  
**Date**: December 15, 2025

---

## 🎯 What This Tool Does

This tool helps you:
1. Send a pulse from your SMU (Keithley 4200A)
2. Capture it on your oscilloscope
3. Analyze the voltage and calculate current across your device

**Key Point**: You control the oscilloscope settings manually. The GUI just reads what's on screen and does the math.

---

## 🔌 Hardware Setup

### Wiring

```
SMU+ → [Your Device] → [Shunt Resistor] → SMU-
                              ↓
                        [Scope CH1 probe]
                        [Scope GND] → SMU-
```

**Critical**: Measure **ACROSS the shunt resistor**, not before it!

### Equipment Checklist
- ✅ Keithley 4200A SMU connected (GPIB)
- ✅ Oscilloscope connected (USB)
- ✅ BNC cables or probes properly connected
- ✅ Know your shunt resistor value (measure with DMM!)

---

## 📋 Step-by-Step Workflow

### Step 1: Set Up Oscilloscope MANUALLY 🔧

On your oscilloscope front panel:
- **Timebase**: Set to capture full pulse
  - Example: for 1 second pulse → 500 ms/div or 1 s/div
- **V/div**: Set appropriate for your signal
  - Example: for ~mV signals → 50 mV/div or 100 mV/div
  - Example: for ~V signals → 500 mV/div or 1 V/div
- **Trigger**: Set trigger level and mode
  - Use AUTO or NORMAL mode
  - Set trigger level above baseline
- **Channel**: Make sure CH1 is enabled

**Don't worry about perfect settings** - you can adjust and re-read!

### Step 2: Connect to Instruments 🔌

In the GUI:
1. **Select System**: Choose your 4200A config from dropdown
2. **Click "🔌 Connect SMU"**
3. Wait for green "SMU: Connected" status
4. **Enter Scope Address**: e.g., `USB0::0x0699::0x03C4::C023684::INSTR`

### Step 3: Set Pulse Parameters ⚡

Enter your desired pulse:
- **Pulse Voltage (V)**: e.g., `2.0` (absolute level, not relative)
  - Can be **negative** for RESET pulses: e.g., `-2.0`
  - Can be **positive** for SET pulses: e.g., `+2.0`
- **Pulse Duration (s)**: e.g., `1.0` (1 second)
- **Bias Voltage (V)**: e.g., `0.2` (pre/post bias level)
  - Usually small and positive, or 0
- **Pre-Bias Time (s)**: e.g., `1.0` (hold at bias before pulse)
- **Post-Bias Time (s)**: e.g., `0.0` (hold at bias after pulse, or 0 for 4200A)
- **Current Compliance (A)**: e.g., `0.001` (1 mA safety limit)
- **R_shunt (Ω)**: **CRITICAL!** Enter your actual resistor value (e.g., `100000` for 100kΩ)

### Step 4: Send Pulse 🚀

1. **Click "2️⃣ Send Pulse"**
2. Wait for pulse to complete (~3-5 seconds)
3. **Look at your oscilloscope screen** - do you see the pulse?

### Step 5: Check Oscilloscope 👀

On the scope screen, you should see:
- Baseline before pulse (bias voltage level)
- Sharp rise to pulse level
- Flat pulse (or changing if device switches)
- Return to baseline after pulse

**If you don't see pulse or it looks wrong:**
- Adjust scope timebase (too fast? too slow?)
- Adjust V/div (signal too small? clipping?)
- Check trigger settings (not triggering?)
- Re-run pulse with "2️⃣ Send Pulse"

### Step 6: Read & Analyze 📊

Once you're happy with the scope display:
1. **Click "4️⃣ Read & Analyze"**
2. GUI reads the waveform from scope
3. Automatically calculates:
   - **V_shunt**: What the scope measured (blue line)
   - **V_SMU**: What you programmed the SMU to do (green dashed line)
   - **V_DUT**: Voltage across your device (red line) = V_SMU - V_shunt
   - **Current**: I = V_shunt / R_shunt
4. Plot shows all three overlayed

### Step 7: Save Data 💾

If you want to save:
1. **Click "💾 Save Data"**
2. Choose filename
3. Data saved with:
   - Time array
   - V_SMU, V_shunt, V_DUT
   - Calculated current
   - All parameters

---

## 📊 Understanding the Plot

### What You See

The plot shows **three voltage traces overlayed**:

**Green Dashed Line (V_SMU)**:
- What you **programmed** the SMU to output
- Reconstructed from your pulse parameters
- Idealized reference (perfect square wave)
- NOT directly measured!

**Blue Solid Line (V_shunt)**:
- What the **oscilloscope actually measured**
- Real data with rise times, noise, etc.
- This is your ground truth!

**Red Solid Line (V_DUT)**:
- Voltage **across your device**
- Calculated: V_DUT = V_SMU - V_shunt
- Used with current to calculate resistance

### Metrics Shown

Bottom left of plot shows:
- **Peak I**: Maximum current during measurement
- **Mean I**: Average current (excluding zeros)
- **R_shunt**: Your resistor value (for reference)

---

## ➖ Working with Negative Pulses

### Negative Pulse Basics

**Positive Pulse** (SET operation):
- Pulse Voltage: `+2.0 V`
- Current flows forward through device
- All values positive in plot

**Negative Pulse** (RESET operation):
- Pulse Voltage: `-2.0 V`
- Current flows backward through device
- V_SMU, V_shunt, V_DUT, Current all negative
- **This is correct!**

### What to Expect

For a **-2.0 V pulse** with **0.2 V bias**:

**On Scope Screen**:
- Bias: small positive signal (~20 mV)
- Pulse: **negative signal** (e.g., -200 mV)
- Return to bias: small positive again

**In GUI Plot**:
- **V_SMU (green)**: 0 → 0.2V → **-2.0V** → 0.2V → 0
- **V_shunt (blue)**: small positive → **negative dip** → small positive
- **V_DUT (red)**: calculated, should be negative during pulse
- **Current**: **negative** (flows opposite direction)

### Sign Convention

```
Positive Pulse:           Negative Pulse:
V_SMU:    +2.0 V          V_SMU:    -2.0 V
V_shunt:  +200 mV         V_shunt:  -200 mV
Current:  +2.0 µA         Current:  -2.0 µA
V_DUT:    +1.8 V          V_DUT:    -1.8 V
Power:    +3.6 µW         Power:    +3.6 µW (still positive!)
```

**Note**: Power (V × I) is **positive** for both because voltage and current have the same sign (both pos or both neg).

### Troubleshooting Negative Pulses

**Problem**: Current shows positive when pulse is negative

**Cause**: Scope connected backward or polarity issue

**Solution**: Check wiring, current should match voltage polarity

---

## ⚠️ Common Issues & Solutions

### Issue: "Can't see pulse on scope"

**Causes**:
- Timebase too fast (pulse off-screen)
- Timebase too slow (pulse too narrow to see)
- V/div wrong (signal too small or clipping)
- Not triggering

**Solutions**:
1. Start with slow timebase (1 s/div) and work down
2. Set V/div to auto-scale or start high
3. Use AUTO trigger mode
4. Check wiring - is scope connected?

### Issue: "V_shunt way different than expected"

**Causes**:
- Wrong measurement point (not across shunt)
- Scope probe attenuation mismatch (1× vs 10×)
- Vertical offset on scope channel

**Solutions**:
1. Verify probe is across shunt resistor
2. Check CH1 probe setting (should match physical probe)
3. Check CH1 offset (should be 0 V usually)
4. Use DMM to verify voltage during DC bias

### Issue: "Current calculation seems wrong"

**Cause**: Wrong R_shunt value (most common!)

**Solution**:
1. **Measure your actual resistor with DMM**
2. Update R_shunt field in GUI
3. Re-run "4️⃣ Read & Analyze"

### Issue: "V_SMU doesn't align with V_shunt"

**Cause**: Pulse timing detection off or parameters wrong

**Solution**:
1. Verify pulse parameters match what you actually sent
2. Check that pulse is visible in blue trace
3. V_SMU is just a reference - V_shunt is the real data!

---

## 🎓 Tips & Best Practices

### For Best Results

1. **Measure R_shunt with DMM first** - most important!
2. **Start with low voltages** (0.5 V) to test setup
3. **Use appropriate R_shunt**:
   - For µA currents: 100 kΩ (gives ~100 mV signal)
   - For mA currents: 1-10 kΩ (gives ~10-100 mV signal)
4. **Check scope probe setting matches physical probe**
5. **Use AUTO trigger mode** on scope for easy capture

### Workflow Tips

1. **First time setup**:
   - Send pulse, adjust scope until you see it clearly
   - Save good scope settings for next time
2. **Multiple measurements**:
   - No need to reconnect each time
   - Just click "2️⃣ Send Pulse" → check → "4️⃣ Read & Analyze" → repeat
3. **Comparing measurements**:
   - Save each one with descriptive filename
   - Plot them together in Excel/Origin/Python later

### Debugging Strategy

If things look wrong:
1. **Simplify**: Replace device with known resistor (1 kΩ)
2. **Verify**: Check voltage with DMM during bias
3. **Compare**: Does DMM agree with scope?
4. **Isolate**: Test each part (SMU, scope, wiring) separately

---

## 📐 Example: Typical Memristor Measurement

### Parameters
```
Pulse Voltage: 2.0 V
Pulse Duration: 1.0 s
Bias Voltage: 0.2 V
Pre-Bias Time: 1.0 s
Post-Bias Time: 0.0 s
Current Compliance: 1 mA
R_shunt: 100 kΩ
```

### Scope Settings
```
Timebase: 500 ms/div (captures ~5 seconds total)
V/div: 200 mV/div (for ~100 mV signal)
Trigger: AUTO, rising edge, level = 50 mV
Channel: CH1, DC coupling, 1× probe
```

### Expected Results

**On Scope Screen**:
- Bias period: ~20 mV baseline (0.2 V bias / high R device ≈ 0.2 µA × 100kΩ)
- Pulse period: ~200 mV (2.0 V pulse / still high R)
- If device switches: signal may increase (resistance drops)

**In GUI Plot**:
- V_SMU (green): clean square 0.2V → 2.0V → 0.2V
- V_shunt (blue): measured scope data, slightly noisy
- V_DUT (red): ~1.8-1.98 V (most voltage across high-R device)
- Current: ~0.2-2 µA (depending on device R)

---

## 🚫 What This Tool Does NOT Do

- ❌ Does **not** auto-configure the oscilloscope (you do it manually)
- ❌ Does **not** measure V_SMU directly (it's reconstructed from parameters)
- ❌ Does **not** work well for very low currents (<1 nA) without TIA amplifier
- ❌ Does **not** replace proper device characterization (use it for quick pulse testing)

---

## 📞 Quick Reference Card

### Hardware
```
SMU+ → Device → Shunt → SMU-
                   ↓
              Scope CH1
```

### GUI Workflow
```
1. Set scope manually (timebase, V/div, trigger)
2. Connect SMU
3. Enter pulse params & R_shunt
4. Click "Send Pulse"
5. Check scope screen
6. Click "Read & Analyze"
7. View overlay plot
8. Save if needed
```

### Key Parameters
- **R_shunt**: MUST match actual resistor
- **Pulse Voltage**: Absolute level (not relative)
- **Scope Channel**: Usually CH1

### Troubleshooting Priority
1. Check R_shunt value (DMM)
2. Check scope probe setting (1× or 10×)
3. Check measurement point (across shunt?)
4. Verify pulse visible on scope

---

## ✅ Checklist: Before First Use

- [ ] Read this guide
- [ ] Measure R_shunt with DMM
- [ ] Connect hardware correctly
- [ ] Test with known resistor first
- [ ] Verify scope shows signal
- [ ] Start with low voltage (0.5 V)
- [ ] Check calculated current makes sense

---

**That's it!** Simple workflow, no fancy auto-config, just pulse → capture → analyze.

For questions or issues, check console output for error messages.

---

**End of Guide**

