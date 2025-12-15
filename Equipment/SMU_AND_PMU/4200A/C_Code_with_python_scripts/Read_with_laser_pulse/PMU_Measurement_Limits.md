# PMU 1-Channel Measurement: Duration & Speed Limits

## Overview

This document details the measurement duration and speed capabilities of the Keithley 4200A 4225-PMU single-channel measurement system. The PMU has a **hardware limit of 1,000,000 samples per A/D test**, which constrains the maximum measurement duration based on the selected sample rate.

---

## Maximum Speed (Sample Rate)

| Parameter | Minimum | Maximum | Notes |
|-----------|---------|----------|-------|
| **Sample Rate** | 1,000 Sa/s (1 kS/s) | 200,000,000 Sa/s (200 MSa/s) | Hardware limit |
| **Sample Rate Steps** | - | 200e6/n (n = integer) | Must be integer divisor of 200 MHz |
| **Common Rates** | 1 kS/s, 10 kS/s, 100 kS/s, 1 MSa/s, 10 MSa/s, 50 MSa/s, 100 MSa/s, 200 MSa/s | - | - |

### Sample Rate Formula
The sample rate must be: `200e6 / n` where `n` is an integer.

**Examples:**
- 200 MSa/s (n=1)
- 100 MSa/s (n=2)
- 66.6 MSa/s (n=3)
- 50 MSa/s (n=4)
- 40 MSa/s (n=5)
- 33.3 MSa/s (n=6)
- 28.57 MSa/s (n=7)
- 25 MSa/s (n=8)
- ... down to 1 kS/s minimum

---

## Maximum Measurement Duration

The maximum measurement duration is **constrained by the 1,000,000 sample hardware limit**:

| Sample Rate | Maximum Duration | Example Use Case |
|-------------|------------------|------------------|
| **200 MSa/s** | **5 ms** | Fast transient capture, short pulses |
| **100 MSa/s** | **10 ms** | High-speed pulses |
| **50 MSa/s** | **20 ms** | Medium-speed waveforms |
| **10 MSa/s** | **100 ms** | Moderate duration measurements |
| **1 MSa/s** | **1 second** | Longer measurements |
| **100 kS/s** | **10 seconds** | Slow processes |
| **10 kS/s** | **100 seconds** | Very slow processes |
| **1 kS/s** | **1,000 seconds (~16.7 min)** | Long-term monitoring |

### Duration Calculation Formula

```
Maximum Duration = 1,000,000 samples ÷ Sample Rate
```

**Example Calculations:**
- At 200 MSa/s: `1,000,000 ÷ 200,000,000 = 0.005 s = 5 ms`
- At 10 MSa/s: `1,000,000 ÷ 10,000,000 = 0.1 s = 100 ms`
- At 1 kS/s: `1,000,000 ÷ 1,000 = 1,000 s = 16.67 minutes`

---

## Timing Constraints

| Parameter | Minimum | Maximum | Description |
|-----------|---------|---------|-------------|
| **Period** | 120 ns (10V range)<br>280 ns (40V range) | 1 second | Pulse period |
| **Pulse Width** | 60 ns | 999.999 ms | Full Width Half Maximum (FWHM) |
| **Rise/Fall Time** | 20 ns | 33 ms | Transition time (0-100%) |
| **Delay** | 0 | 999 ms | Pre-pulse delay |
| **Segment Time** | 20 ns | 1 second | For seg_arb mode |

### Period Validation

The system automatically validates and adjusts the period:

```
min_required_period = max(
    delay + width + rise + fall,
    delay + width + 0.5×(rise + fall) + 40e-9,
    120e-9 (or 280e-9 for 40V range)
)
```

If the requested period is too small, it will be automatically adjusted to the minimum.

---

## Practical Examples

### Example 1: Fast Measurement (200 MSa/s)
- **Sample Rate**: 200 MSa/s
- **Max Duration**: 5 ms
- **Max Samples**: 1,000,000
- **Use Case**: Fast transients, short pulses, high-speed switching

### Example 2: Medium Duration (10 MSa/s)
- **Sample Rate**: 10 MSa/s
- **Max Duration**: 100 ms
- **Max Samples**: 1,000,000
- **Use Case**: Multiple pulses, moderate speed measurements

### Example 3: Long Measurement (1 kS/s)
- **Sample Rate**: 1 kS/s
- **Max Duration**: 1,000 seconds (~16.7 minutes)
- **Max Samples**: 1,000,000
- **Use Case**: Slow processes, long-term monitoring, retention measurements

---

## Additional Constraints

### 1. Array Size Limits

| Array Type | Minimum | Maximum | Notes |
|------------|---------|---------|-------|
| **Output Arrays** (V_Meas, I_Meas, T_Stamp) | 100 | 32,767 | KXCI limit |
| **Hardware Acquisition** | 12 | 1,000,000 | Hardware limit |
| **Practical Limit** | - | ~30,000 | For reasonable data transfer speed |

### 2. Burst Count Limits

- **PMU_1Chan_Sweep**: Limited by sweep points (up to 10,000)
- **ACraig10**: Up to 100,000 bursts (but limited by total samples)
- **Total measurements**: Must fit within 1,000,000 sample limit

### 3. Memory Considerations

**Full Waveform Mode:**
- ~24 MB per 1M samples (3 arrays × 1M × 8 bytes)
- Raw data arrays: ~240 MB for 1M samples (5 arrays × 1M × 8 bytes)

**Spot Mean Mode:**
- Much smaller (pre-averaged by hardware)
- Output arrays: ~26 KB for 1,100 measurements (3 arrays × 1,100 × 8 bytes)

### 4. Sweep Limitations

For voltage sweeps:
- **Maximum sweep points**: ≤ 65,536
- **Points per waveform**: `period × SampleRate + 1`
- **Total samples per sweep**: `pointsPerWfm × dSweeps ≤ 65,536`

**Example:**
- `period = 1e-6 s`, `SampleRate = 200e6 Sa/s`
- `pointsPerWfm = 1e-6 × 200e6 + 1 = 201 points`
- Maximum sweeps: `65,536 / 201 ≈ 326 sweeps`

---

## Speed vs Duration Trade-offs

| Goal | Sample Rate | Max Duration | Trade-off |
|------|-------------|--------------|-----------|
| **Maximum Speed** | 200 MSa/s | 5 ms | Short duration only |
| **Maximum Duration** | 1 kS/s | ~16.7 min | Slow sampling |
| **Balanced** | 10 MSa/s | 100 ms | Good resolution + reasonable duration |

---

## Recommendations

### For Long Measurements (>100 ms)
1. **Reduce sample rate** (e.g., 10 kS/s for 100 s duration)
2. **Use spot mean mode** (hardware averaging) instead of full waveform
3. **Consider multiple shorter acquisitions** if continuous monitoring needed
4. **Use burst mode** with averaging to reduce data transfer

### For Fast Measurements (<5 ms)
1. **Use maximum 200 MSa/s** for best time resolution
2. **Keep total duration ≤ 5 ms** to stay within sample limit
3. **Use full waveform mode** for detailed capture
4. **Minimize number of pulses** to maximize samples per pulse

### For Balanced Measurements
1. **10 MSa/s** provides good balance: 100 ms duration with 10 ns resolution
2. **50 MSa/s** for 20 ms duration with 20 ns resolution
3. **Adjust based on signal characteristics** (rise time, pulse width, etc.)

---

## Measurement Modes Comparison

### Hardware Spot Mean Mode (PMU_1Chan_Sweep)
- **Averaging**: Done by PMU hardware
- **Data Transfer**: Pre-averaged spot means (smaller)
- **Speed**: Faster (less data to transfer)
- **Flexibility**: Measurement window set via `MeasStartPerc`/`MeasStopPerc`
- **Use Case**: Voltage sweeps, IV curves

### Software Waveform Mode (ACraig10)
- **Averaging**: Done in software after fetching full waveform
- **Data Transfer**: Full waveform samples (larger)
- **Speed**: Slower (more data to transfer)
- **Flexibility**: Can adjust measurement window in post-processing
- **Use Case**: Continuous waveform capture, detailed analysis

---

## Key Takeaways

1. **Hardware Limit**: 1,000,000 samples per A/D test (fixed)
2. **Maximum Speed**: 200 MSa/s (5 ms max duration)
3. **Maximum Duration**: ~16.7 minutes at 1 kS/s
4. **Trade-off**: Higher speed = shorter duration, lower speed = longer duration
5. **Practical Limit**: ~30,000 samples for reasonable data transfer speed
6. **Minimum Period**: 120 ns (10V range) or 280 ns (40V range)

---

## References

- Keithley 4200A-SCS 4225-PMU Hardware Specification
- PMU_1Chan_Sweep.c - Hardware spot mean measurement
- ACraig10_PMU_Waveform_SegArb.c - Software waveform measurement
- Read_With_Laser_Pulse_SegArb_Python.py - Python wrapper example

---

## Notes

- All timing parameters must be ≥ 20 ns to meet PMU hardware requirements
- Sample rate must be integer divisor of 200 MHz
- For voltage sweeps, total samples = `pointsPerWfm × numSweeps` must be ≤ 65,536
- Single-channel mode (CH1 force + measure) may show current range saturation issues
- Consider dual-channel mode (CH1 force, CH2 measure) for accurate current measurement if CH2 is available







