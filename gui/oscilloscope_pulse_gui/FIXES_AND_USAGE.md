# Oscilloscope Pulse GUI - Fixes and Usage Guide

## Critical Fixes Applied

### 1. **Scope Reconnection Bug (CRITICAL)**
**Problem**: The code was reconnecting to the oscilloscope AFTER the pulse was sent, which cleared the captured waveform buffer.

**Fix**: Removed the reconnection logic in the acquisition phase (lines 400-463). The scope now:
- Connects once during setup
- Gets armed for single-shot acquisition
- Captures the pulse when it triggers
- Reads the waveform from the existing connection (no reconnect)

**Impact**: This was preventing ANY waveform capture. Now waveforms are properly captured and displayed.

---

### 2. **High-Resolution Configuration**
**Problem**: Record length and timebase calculations were not optimized for maximum resolution.

**Fixes**:
- **Record Length**: Now explicitly sets to maximum (20k points for TBS1000C)
- **Timebase**: Automatically calculates optimal timebase to capture the full measurement window:
  ```
  timebase = (pre_delay + pulse_duration + post_delay) × 1.2 / 10 divisions
  ```
- **Sample Rate**: Displays actual sample rate and resolution achieved
- **Validation**: Warns if user-specified timebase is too small

**Result**: 20,000 points captured over the full pulse window for maximum resolution.

---

### 3. **Acquisition Mode Configuration**
**Problem**: Acquisition mode was not explicitly set, could be in continuous mode.

**Fix**: Explicitly configures scope for:
- `SAMPLE` mode (not averaging or peak detect)
- `SEQUENCE` (single-shot) mode
- Proper trigger holdoff to prevent re-triggering

---

### 4. **Improved Trigger Configuration**
**Enhancements**:
- Trigger level: 20% of pulse voltage (adjustable via `trigger_ratio` parameter)
- Trigger position: Set to 40% from left edge to capture pre-pulse baseline
- Holdoff: Set to full measurement time + buffer to prevent false triggers
- Better voltage scale estimation based on shunt resistance and expected current

---

## How to Use for Reliable High-Resolution Measurements

### Basic Setup

1. **Connections**:
   ```
   [SMU Hi] → [Memristor] → [Shunt Resistor] → [SMU Lo/GND]
                                    ↓
                              [Scope CH1]
                              [Scope GND] → [SMU Lo/GND]
   ```

2. **GUI Configuration**:
   - **Scope Address**: `USB0::0x0699::0x03C4::C023684::INSTR` (or your TBS1000C address)
   - **Scope Type**: `Tektronix TBS1000C`
   - **Scope Channel**: `CH1`
   - **Record Length**: `20` (k points) - **Set to 20 for maximum resolution**
   - **Auto-configure scope**: ✓ Checked (recommended)

3. **Pulse Parameters**:
   - **Pulse Voltage**: Your desired voltage (e.g., `-1V`)
   - **Pulse Duration**: Duration in seconds (e.g., `1.0` for 1 second)
   - **Pre-Pulse Delay**: Time before pulse (e.g., `0.1` = 100ms)
   - **Post-Pulse Hold**: Time after pulse (e.g., `0.1` = 100ms)
   - **Current Compliance**: Safety limit (e.g., `0.001` = 1mA)

4. **Measurement Settings**:
   - **R_shunt**: Your shunt resistor value in Ohms (e.g., `100E3` = 100kΩ)

---

### Achieving Maximum Resolution

**The scope captures a fixed time window with a fixed number of points. Resolution = points / time.**

#### Example 1: 1-second pulse
```
Pre-delay:    0.1 s
Pulse:        1.0 s
Post-delay:   0.1 s
Total:        1.2 s

Timebase (auto): 1.2 × 1.2 / 10 = 0.144 s/div
Time window:     0.144 × 10 = 1.44 s
Points:          20,000
Sample interval: 1.44 / 20000 = 72 µs
Sample rate:     13,889 Sa/s
```

#### Example 2: 10ms pulse (higher resolution)
```
Pre-delay:    0.1 s
Pulse:        0.01 s (10ms)
Post-delay:   0.1 s
Total:        0.21 s

Timebase (auto): 0.21 × 1.2 / 10 = 0.0252 s/div
Time window:     0.252 s
Points:          20,000
Sample interval: 0.252 / 20000 = 12.6 µs
Sample rate:     79,365 Sa/s
```

**Key Insight**: Shorter pulses = higher sample rate with same 20k points!

---

### Optimizing for Your Application

#### For High Temporal Resolution (Fast Switching)
- **Use shorter pulses** (10ms - 100ms)
- **Minimize pre/post delays** (keep just enough to see baseline)
- **Set Record Length to 20** (maximum)
- **Auto-configure scope**: ✓

Result: ~10µs - 50µs sample intervals

#### For Long Pulses (Slow Dynamics)
- **Use longer pulses** (1s - 10s)
- **Set Record Length to 20** (still use maximum)
- **Consider manual timebase** if you need to zoom into a specific portion

Result: ~50µs - 500µs sample intervals

---

### Timebase Calculation Details

The tool automatically calculates timebase as:
```python
total_time = pre_delay + pulse_duration + post_delay
timebase = (total_time × 1.2) / 10.0  # 20% margin, 10 divisions
time_window = timebase × 10.0
```

**Override if needed**: You can manually set `Timebase (s/div)` in the GUI, but the tool will warn you if it's too small.

**Validation**:
```
✓ time_window >= total_measurement_time
✗ time_window < total_measurement_time → WARNING displayed
```

---

### Voltage Scale Auto-Calculation

The tool estimates the voltage scale based on:
```python
# Estimate shunt voltage: V_shunt ≈ V_pulse × R_shunt / (R_shunt + R_device)
# Assume R_device ~ 100Ω for memristor
estimated_v_shunt = pulse_voltage × (shunt_r / (shunt_r + 100))
v_scale = (estimated_v_shunt × 1.2) / 4.0  # 4 divisions with 20% headroom
```

**Override if needed**: Set `Voltage Scale (V/div)` in the GUI if auto-calculation is incorrect.

---

### Trigger Configuration

**Automatic Settings**:
- **Trigger Level**: 20% of pulse voltage (adjustable via `trigger_ratio` in JSON config)
- **Trigger Slope**: `RISING` for positive pulses, `FALLING` for negative pulses
- **Trigger Position**: 40% from left edge (captures 4 divisions of pre-pulse baseline)
- **Trigger Holdoff**: Full measurement time + 0.1s (prevents re-triggering)

**Why these values**:
- 20% threshold: Sensitive enough to catch pulse start, high enough to avoid noise
- 40% position: Shows pre-pulse baseline for reference while capturing full pulse
- Holdoff: Prevents multiple triggers during long pulses

---

## Measurement Flow

### What Happens When You Click "Start Measurement"

1. **Connection Phase** (if not connected):
   - Connects to oscilloscope
   - Connects to SMU

2. **Configuration Phase**:
   - Sets acquisition mode: SAMPLE, SEQUENCE (single-shot)
   - Enables CH1, DC coupling
   - Sets record length: 20,000 points
   - Calculates and sets optimal timebase
   - Sets voltage scale
   - Configures trigger (level, slope, position, holdoff)
   - **Arms scope** for single-shot capture

3. **Pulse Execution Phase**:
   - Waits for pre-pulse delay (scope is armed and waiting for trigger)
   - **SMU sends pulse** → **Scope triggers and captures**
   - Holds for post-pulse time
   - Turns off SMU

4. **Acquisition Phase**:
   - Reads waveform from scope (**no reconnection!**)
   - Displays: time window, sample rate, number of points captured

5. **Processing Phase**:
   - Calculates current: `I = V_shunt / R_shunt`
   - Calculates memristor voltage: `V_memristor = V_SMU - V_shunt`
   - Calculates resistance: `R = V_memristor / I`
   - Calculates power: `P = V_memristor × I`
   - Updates all plots

6. **Save Phase** (if auto-save enabled):
   - Saves data to configured directory
   - Includes all derived quantities and statistics

---

## Troubleshooting

### "No waveform captured" or "0 points"
**Causes**:
- Scope didn't trigger (pulse too small or trigger level too high)
- Timing issue (scope not armed before pulse)

**Solutions**:
1. Check trigger level (lower it if needed via `trigger_ratio` in config)
2. Check connections (scope CH1 → shunt → GND)
3. Increase pulse voltage
4. Check scope is powered on and connected

---

### "Waveform looks wrong" or "Clipped"
**Causes**:
- Voltage scale too small (signal exceeds scope range)
- Voltage scale too large (signal is tiny)

**Solutions**:
1. Check auto-calculated voltage scale in console output
2. Manually set `Voltage Scale (V/div)` in GUI
3. Verify shunt resistor value is correct

---

### "Resolution is too low"
**Causes**:
- Record length < 20k
- Pulse duration + delays too long relative to desired resolution

**Solutions**:
1. **Set Record Length to 20** (maximum)
2. Reduce pre/post delays to minimum needed
3. Consider shorter pulse if application allows
4. Calculate required timebase: `timebase = desired_resolution × points / 10`

---

### "Time window doesn't cover full pulse"
**Causes**:
- Manually set timebase too small
- Total measurement time very long

**Solutions**:
1. Let tool auto-calculate timebase (leave field empty)
2. If manual, ensure: `timebase × 10 ≥ (pre_delay + duration + post_delay)`
3. Check console for WARNING messages about timebase

---

## Configuration File (pulse_gui_config.json)

Key parameters you might want to adjust:

```json
{
  "record_length": "20",          // ALWAYS set to 20 for max resolution
  "auto_configure_scope": true,   // Let tool configure scope automatically
  "trigger_ratio": 0.2,           // Trigger at 20% of pulse voltage
  "r_shunt": "100E3",             // Your shunt resistor value (Ohms)
  "auto_save": true,              // Auto-save data after each measurement
  "simulation_mode": false        // Set to true for testing without hardware
}
```

---

## Advanced: Understanding TBS1000C Limitations

The Tektronix TBS1000C has hardware limitations:

- **Maximum Record Length**: 20,000 points (this tool uses maximum)
- **Maximum Sample Rate**: ~1 GSa/s (in normal mode)
- **Effective Sample Rate**: Depends on timebase setting
  ```
  sample_rate = record_length / time_window
  ```

**Example**:
```
Timebase:     1 ms/div
Time window:  10 ms
Record length: 20,000 points
Sample rate:  20,000 / 0.01 = 2 MSa/s
```

**For higher sample rates**: You MUST use shorter time windows (shorter pulses + delays).

---

## Testing the Tool

### 1. Simulation Mode
Set `simulation_mode: true` in config or check "🔧 Simulation Mode" in GUI.
- Tests without hardware
- Generates realistic memristor switching waveform
- Verifies plotting and data processing

### 2. Loopback Test
Connect scope CH1 directly to SMU output:
```
[SMU Hi] → [Resistor ~1kΩ] → [Scope CH1] → [SMU Lo/Scope GND]
```
- Should see clean square pulse
- Voltage should match SMU setting
- Tests trigger and timing

### 3. Real Measurement
Connect your device + shunt:
- Start with small voltage (1V)
- Check waveform quality
- Verify current calculation makes sense
- Gradually increase voltage

---

## Console Output Interpretation

When you run a measurement, look for:

```
✓ Auto-configuring oscilloscope for high-resolution capture...
    Acquisition mode: SAMPLE (single-shot)
    Channel CH1: Enabled, DC coupling
    Record length: 20000 points (max resolution)
    Timebase: 0.144000 s/div (144.000 ms/div)
    Total window: 1.440000 s
    Sample interval: 7.200000e-05 s
    Sample rate: 13888.889 Sa/s
    Resolution: 20000 points over 1.2000s pulse
    Voltage scale: 0.0050 V/div
    Trigger position: -0.144000s (40% from left edge)
    Trigger: CH1 @ 0.2000V
    Trigger slope: RISING
    Trigger holdoff: 1.3000s
  ✓ Scope configured for high-resolution capture
```

**Key metrics**:
- **Record length**: Should be 20000
- **Sample interval**: Your temporal resolution
- **Sample rate**: Points per second
- **Time window**: Must cover your measurement (pre + pulse + post)

---

## Summary of Best Practices

1. ✅ **Always set Record Length to 20** (maximum resolution)
2. ✅ **Use Auto-configure scope** (let tool optimize settings)
3. ✅ **Minimize pre/post delays** for faster sample rates
4. ✅ **Check console output** to verify settings
5. ✅ **Verify time window covers full pulse** (tool warns if not)
6. ✅ **Use correct R_shunt value** (critical for current calculation)
7. ✅ **Test with simulation mode** before hardware
8. ✅ **Start with low voltages** and work up

---

## Contact / Issues

If you encounter problems:

1. Check console output for warnings/errors
2. Verify connections and addresses
3. Test in simulation mode
4. Check this guide for troubleshooting steps
5. Review the walkthrough.md file for additional context

---

**Author**: AI Assistant  
**Date**: December 2025  
**Version**: 2.0 (After critical bug fixes)

