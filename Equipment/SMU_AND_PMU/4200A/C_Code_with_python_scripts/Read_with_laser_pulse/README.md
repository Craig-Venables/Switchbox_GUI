# PMU Read with Laser Pulse (SegArb) Measurement Module

> **⚠️ IMPORTANT: Dual-Channel Mode Required**
> 
> This module operates in **dual-channel mode** using PMU channels 1 and 2:
> - **Channel 1 (Measurement Channel)**: Performs continuous voltage/current measurements on the device
> - **Channel 2 (Laser Channel)**: Generates laser pulse waveforms using seg_arb (independent timing)
> 
> Ensure proper connections are made before running measurements.

## Overview

This module implements a **dual-channel measurement system** for studying device response to laser pulses using the Keithley 4200A-SCS Programmable Measurement Unit (PMU). The system combines:

- **CH1**: Continuous waveform measurement using seg_arb (auto-built from simple pulse parameters)
- **CH2**: Independent laser pulse generation using seg_arb (can be auto-built or manually defined)

**Key Advantage**: CH2 period is **completely independent** of CH1 period, allowing flexible laser pulse timing relative to measurement pulses.

This measurement pattern is essential for studying:
- **Photo-induced effects** in optoelectronic devices
- **Laser-assisted switching** in memristors
- **Time-resolved photoconductivity** measurements
- **Synchronized optical-electrical** characterization

---

## Waveform Structure

### Channel 1 (Measurement Channel)

CH1 generates continuous measurement pulses:

```
CH1 Waveform (Measurement Pulses):
═══════════════════════════════════════════════════════════════════════════════

Voltage (V)
    │
startV ─┐     ┌──┐     ┌──┐     ┌──┐     ┌──┐     ┌──┐
        │     │  │     │  │     │  │     │  │     │  │
        │     │  │     │  │     │  │     │  │     │  │
 baseV ─┼──┐  │  │  ┌──│  │  ┌──│  │  ┌──│  │  ┌──│  │  ┌──
        │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
   0V ──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴───> Time
        │
        │
   DELAY  RISE  WIDTH  FALL  POST-DELAY  (repeated burstCount times)

Measurement Window: 40-80% of pulse width (stable region)
```

### Channel 2 (Laser Channel)

CH2 generates a single laser pulse (or repeated pulses) with independent timing:

```
CH2 Waveform (Laser Pulse):
═══════════════════════════════════════════════════════════════════════════════

Voltage (V)
    │
Vhigh ─┐     ┌──┐
       │     │  │
       │     │  │
 Vlow ─┼──┐  │  │  ┌──
       │  │  │  │  │
   0V ─┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴───> Time
       │
       │
   PRE-DELAY  RISE  WIDTH  FALL  POST-DELAY

Note: CH2 timing is completely independent of CH1!
```

### Synchronized Operation

Both channels execute simultaneously via `pulse_exec()`, but operate independently:

```
Timeline:
═══════════════════════════════════════════════════════════════════════════════

CH1: │─P1─│─P2─│─P3─│─P4─│─P5─│─P6─│─P7─│─P8─│─P9─│─P10─│
     │    │    │    │    │    │    │    │    │    │     │
CH2: │─────────────LASER PULSE─────────────│
     │                                    │
     └────────────────────────────────────┘
     CH2Period (delay before laser pulse)
     
CH1 period: Independent (e.g., 2µs)
CH2 period: Independent (e.g., 10µs delay before pulse)
```

---

## Measurement Window (40-80% of Pulse Width)

When `acqType=1` (average mode, default), the module extracts **one averaged measurement per pulse** from a specific time window within each CH1 pulse.

### Why 40-80%?

- **Avoids transition regions**: The first 40% excludes the rise time transition and any settling/ringing at the start of the pulse
- **Avoids fall transition**: The last 20% (80-100%) excludes the fall time transition and any pre-fall settling effects
- **Stable region**: The 40-80% window captures the most stable, flat portion of the pulse where voltage and current have fully settled

### Example

With 1µs pulse width:
- Pulse starts at t=0 (after delay + rise)
- Measurement window: **0.4µs to 0.8µs** (40-80% of 1µs)
- All samples within this window are averaged to produce one value per pulse
- This gives accurate resistance measurements by avoiding transient effects

**Note**: The measurement window is hardcoded in the C code:
```c
measurementStartFrac = 0.4  (40% of pulse width)
measurementEndFrac = 0.8    (80% of pulse width)
```

To modify these values, edit the C source file.

---

## Key Parameters

### CH1 (Measurement Channel) Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `--width` | Pulse width (s) | 40e-9 to 0.999999 | 0.5e-6 |
| `--rise` | Rise time (s) | 20e-9 to 0.033 | 100e-9 |
| `--fall` | Fall time (s) | 20e-9 to 0.033 | 100e-9 |
| `--delay` | Pre-pulse delay (s) | 0 to 0.999999 | 0 |
| `--period` | Pulse period (s) | 120e-9 to 1.0* | 0.5e-6 |
| `--start-v` | Start voltage (V) | -40 to 40 | 1.0 |
| `--stop-v` | Stop voltage (V) | -40 to 40 | 1.0 |
| `--step-v` | Step voltage (V) | -40 to 40 | 0.0 |
| `--base-v` | Base voltage (V) | -40 to 40 | 0.0 |
| `--burst-count` | Number of pulses | 1 to 100000 | 500 |
| `--acq-type` | Acquisition type | 0 or 1 | 1 |
| `--sample-rate` | Sample rate (Sa/s) | 1 to 200e6 | 200e6 |

*Minimum period depends on voltage range: 120ns (≤10V) or 280ns (>10V)

### CH2 (Laser Channel) Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `--ch2-enable` | Enable CH2 | 0 or 1 | 1 |
| `--ch2-vrange` | Voltage range (V) | 5 to 40 | 10.0 |
| `--ch2-vlow` | Low voltage (V) | -40 to 40 | 0.0 |
| `--ch2-vhigh` | High voltage (V) | -40 to 40 | 1.5 |
| `--ch2-width` | Pulse width (s) | 40e-9 to 0.999999 | 10e-6 |
| `--ch2-rise` | Rise time (s) | 20e-9 to 0.033 | 100e-9 |
| `--ch2-fall` | Fall time (s) | 20e-9 to 0.033 | 100e-9 |
| `--ch2-period` | Delay before pulse (s) | 100e-9 to 1.0 | 5e-6 |
| `--ch2-loop-count` | Number of repetitions | 1.0 to 100000.0 | 1.0 |

### Instrument Configuration

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `--volts-source-rng` | CH1 voltage range (V) | 5 to 40 | 10.0 |
| `--current-measure-rng` | CH1 current range (A) | 100e-9 to 0.8 | 0.00001 |
| `--dut-res` | DUT resistance (Ohm) | 1 to 10e6 | 1e6 |
| `--array-size` | Output array size | 100 to 32767 | 0 (auto) |
| `--chan` | PMU channel | 1 or 2 | 1 |
| `--pmu-id` | PMU instrument ID | - | "PMU1" |

---

## System Limits and Constraints

### Array Size Limits

| Array Type | Minimum | Maximum | Default |
|------------|---------|---------|---------|
| `V_Meas[]`, `I_Meas[]`, `T_Stamp[]` | 100 | 32767 | 3000 |
| CH2 segment arrays (if manual mode) | 3 | 2048 | 10 |

**Auto-sizing**:
- If `--array-size=0` (auto):
  - `acqType=1` (average): `array_size = burst_count` (one value per pulse)
  - `acqType=0` (discrete): `array_size = min(period × sample_rate × burst_count + 100, 10000)`

### Total Sample Limits

| Constraint | Limit | Description |
|------------|-------|-------------|
| **Total samples per A/D test** | ≤ **1,000,000** | Hardware limit (4225-PMU specification) |
| **Total samples per sweep** | ≤ 65536 | `pointsPerWfm × dSweeps ≤ 65536` (for voltage sweeps only) |
| **Sweep points** | ≤ 65536 | Maximum number of voltage steps |
| **Points per waveform** | Calculated | `period × SampleRate + 1` |

**Maximum Measurement Duration** (at different sample rates):
- **200 MSa/s**: 5 ms (1,000,000 ÷ 200,000,000)
- **100 MSa/s**: 10 ms
- **50 MSa/s**: 20 ms
- **10 MSa/s**: 100 ms
- **1 MSa/s**: 1 second

**Example Calculation** (for voltage sweeps):
- `period = 1e-6 s`, `SampleRate = 200e6 Sa/s`
- `pointsPerWfm = 1e-6 × 200e6 + 1 = 201 points`
- Maximum sweeps: `65536 / 201 ≈ 326 sweeps`

### Timing Constraints

| Parameter | Minimum | Description |
|-----------|---------|-------------|
| **Segment time** | 20e-9 s (20ns) | Minimum time for any seg_arb segment |
| **CH1 period** | 120e-9 s (10V range) | Minimum period for CH1 |
| | 280e-9 s (40V range) | Minimum period for CH1 (higher range) |
| **Off-time** | 40e-9 s (40ns) | Minimum time between pulses |
| **Rise/Fall time** | 20e-9 s (20ns) | Minimum transition time |

**Period Validation**:
The system automatically validates and adjusts the period:
```
min_required_period = max(
    delay + width + rise + fall,
    delay + width + 0.5×(rise + fall) + 40e-9,
    120e-9 (or 280e-9 for 40V range)
)
```

If the requested period is too small, it will be automatically adjusted to the minimum.

### CH2 Segment Limits

| Parameter | Minimum | Maximum | Description |
|-----------|---------|---------|-------------|
| **Ch2NumSegments** | 3 | 2048 | Number of segments (manual mode) |
| **Ch2LoopCount** | 1.0 | 100000.0 | Number of times to repeat sequence |

**Auto-build mode** (`Ch2NumSegments=0`):
- Automatically builds 6 segments from simple pulse parameters
- No manual segment arrays needed

### Sample Rate Limits

| Parameter | Minimum | Maximum | Default |
|-----------|---------|---------|---------|
| **Sample rate** | 1 Sa/s | 200e6 Sa/s | 200e6 Sa/s |

**Note**: Higher sample rates provide better time resolution but increase memory requirements and may hit the 65536 total sample limit faster.

### Burst Count Limits

| Parameter | Minimum | Maximum | Default |
|-----------|---------|---------|---------|
| **burst_count** | 1 | 100000 | 500 |

**Memory consideration**: With `acqType=1`, output array size should be ≥ `burst_count` (one value per pulse).

---

## Usage Examples

### Basic Laser-Assisted Measurement

CH1 reads at 2µs period, CH2 pulses laser 5µs into measurement:

```bash
python Read_With_Laser_Pulse_SegArb_Python.py \
    --gpib-address GPIB0::17::INSTR \
    --burst-count 50 \
    --period 2e-6 \
    --ch2-period 5e-6 \
    --ch2-width 1e-6 \
    --ch2-vhigh 1.5
```

### High-Resolution Time-Resolved Study

```bash
python Read_With_Laser_Pulse_SegArb_Python.py \
    --burst-count 100 \
    --period 1e-6 \
    --width 500e-9 \
    --rise 50e-9 \
    --fall 50e-9 \
    --ch2-period 2e-6 \
    --ch2-width 500e-9 \
    --ch2-rise 50e-9 \
    --ch2-fall 50e-9 \
    --ch2-vhigh 2.0 \
    --sample-rate 200e6 \
    --acq-type 1
```

### Full Waveform Capture (Discrete Mode)

Capture full waveform instead of averaged values:

```bash
python Read_With_Laser_Pulse_SegArb_Python.py \
    --burst-count 10 \
    --period 10e-6 \
    --acq-type 0 \
    --array-size 10000 \
    --ch2-enable 1 \
    --ch2-period 5e-6
```

### Dry Run (Command Generation Only)

```bash
python Read_With_Laser_Pulse_SegArb_Python.py \
    --dry-run \
    --burst-count 50 \
    --period 2e-6 \
    --ch2-period 10e-6
```

---

## Output Data

### Acquisition Modes

#### Mode 1: Average (`acqType=1`, default)
- **Output**: One averaged value per pulse
- **Array size**: Should be ≥ `burst_count`
- **Measurement window**: 40-80% of pulse width
- **Use case**: Fast measurements, resistance tracking

#### Mode 0: Discrete (`acqType=0`)
- **Output**: Full waveform (all samples)
- **Array size**: Should be ≥ `period × sample_rate × burst_count`
- **Use case**: Detailed waveform analysis, transient studies

### Output Arrays

1. **`V_Meas[]`** (Parameter 23): Measured voltage
2. **`I_Meas[]`** (Parameter 25): Measured current
3. **`T_Stamp[]`** (Parameter 27): Timestamp for each measurement

### Calculated Values

- **Resistance**: `R = V_Meas / I_Meas` (calculated in Python)
- **Conductance**: Inverse of resistance (if needed)

---

## Technical Implementation

### Architecture

1. **Python Script** (`Read_With_Laser_Pulse_SegArb_Python.py`):
   - Builds EX command with all parameters
   - Communicates with instrument via KXCI
   - Retrieves data using GP (Get Parameter) commands
   - Calculates resistance and generates plots

2. **C Module** (`Read_With_Laser_Pulse_SegArb.c`):
   - Converts CH1 simple pulse parameters to seg_arb segments
   - Builds CH2 seg_arb waveform (auto-build or manual)
   - Executes both channels simultaneously
   - Extracts measurements from 40-80% window
   - Returns averaged or full waveform data

3. **PMU Hardware**:
   - CH1: Measurement channel with waveform capture
   - CH2: Laser pulse channel (source only, no measurement)

### Key Features

- **Independent Channel Timing**: CH1 and CH2 operate with completely independent periods
- **Seg_Arb Based**: Both channels use seg_arb for precise waveform control
- **Auto-Build Mode**: CH1 and CH2 can auto-build segments from simple parameters
- **Flexible Measurement**: Supports both averaged (per-pulse) and full waveform capture
- **Measurement Window**: Automatic 40-80% window extraction for stable measurements

### CH1 Seg_Arb Auto-Build

CH1 automatically builds 6 segments from simple pulse parameters:

```
Segment 0: Pre-delay (at baseV) - no measurement
Segment 1: Rise (baseV → startV) - full segment measurement
Segment 2: Width (at startV) - full segment measurement (40-80% extracted here)
Segment 3: Fall (startV → baseV) - full segment measurement
Segment 4: Post-delay (at baseV) - no measurement
Segment 5: Final 0V segment - ensures clean ending
```

### CH2 Seg_Arb Auto-Build

When `Ch2NumSegments=0`, CH2 automatically builds 6 segments:

```
Segment 0: Pre-delay (Ch2Period delay) - at Ch2Vlow
Segment 1: Rise (Ch2Vlow → Ch2Vhigh)
Segment 2: Width (at Ch2Vhigh) - laser pulse duration
Segment 3: Fall (Ch2Vhigh → Ch2Vlow)
Segment 4: Post-delay (at Ch2Vlow)
Segment 5: Final 0V segment
```

**Loop Count**: `Ch2LoopCount` determines how many times the sequence repeats (default: 1.0 for single pulse).

---

## C Program Architecture and Data Flow

### Overview of the System Architecture

```
Python Script (Read_With_Laser_Pulse_SegArb_Python.py)
    ↓ [EX command via KXCI/GPIB]
C Module (Read_With_Laser_Pulse_SegArb.c)
    ↓ [seg_arb segments]
PMU Hardware (CH1 + CH2)
    ↓ [Raw measurements]
C Module (data extraction)
    ↓ [GP parameters]
Python Script
```

### Step-by-Step Execution Flow

#### 1. **Python Script: Command Generation**

The Python script builds an `EX` command:

```python
EX A_Ch1Read_Ch2Laser_Pulse Read_With_Laser_Pulse_SegArb(
    width, rise, fall, delay, period, ...,
    "", array_size, "", array_size, "", array_size,  # Output arrays
    Ch2Enable, Ch2VRange, Ch2Vlow, Ch2Vhigh, ...,
    Ch2NumSegments, "", 10, "", 10, ..., Ch2LoopCount, ...
)
```

#### 2. **C Module: Initialization**

- Validates instrument configuration
- Checks sweep parameters (max 65536 total samples)
- Initializes PMU in **SARB mode** (required for seg_arb)
- Configures RPMs (if attached) for pulse mode

#### 3. **CH1 Seg_Arb Setup**

**a) Parameter Validation**:
- Validates period meets minimum requirements
- Adjusts period if too small
- Validates all segment times ≥ 20ns

**b) Segment Building**:
```c
// Auto-build 6 segments from simple pulse parameters
ch1_num_segments = 6;
ch1_startv[0] = baseV; ch1_stopv[0] = baseV;  // Pre-delay
ch1_startv[1] = baseV; ch1_stopv[1] = startV; // Rise
ch1_startv[2] = startV; ch1_stopv[2] = startV; // Width (measurement here)
ch1_startv[3] = startV; ch1_stopv[3] = baseV;  // Fall
ch1_startv[4] = baseV; ch1_stopv[4] = baseV;   // Post-delay
ch1_startv[5] = baseV; ch1_stopv[5] = 0.0;     // Final 0V
```

**c) Measurement Configuration**:
- Sets `meastype=2` (waveform measurement) for segments 1-3
- Configures `measstart=0.0`, `measstop=segtime` for full segment capture
- Measurement window (40-80%) extracted during data processing

**d) Waveform Configuration**:
```c
seg_arb_sequence(pulserId, chan, 1, ch1_num_segments, ...);
seg_arb_waveform(pulserId, chan, 1, seqList, loopCount);
// loopCount = burst_count (repeats sequence burst_count times)
```

#### 4. **CH2 Seg_Arb Setup**

**a) Auto-Build Mode** (`Ch2NumSegments=0`):
```c
// Build 6 segments from simple pulse parameters
ch2_startv[0] = Ch2Vlow;  // Pre-delay (Ch2Period)
ch2_startv[1] = Ch2Vlow; ch2_stopv[1] = Ch2Vhigh;  // Rise
ch2_startv[2] = Ch2Vhigh;  // Width (laser pulse)
ch2_startv[3] = Ch2Vhigh; ch2_stopv[3] = Ch2Vlow;  // Fall
ch2_startv[4] = Ch2Vlow;  // Post-delay
ch2_startv[5] = 0.0;  // Final 0V
```

**b) Manual Mode** (`Ch2NumSegments ≥ 3`):
- Uses provided segment arrays directly
- Validates array sizes ≥ `Ch2NumSegments`
- Supports up to 2048 segments for complex waveforms

**c) Waveform Configuration**:
```c
seg_arb_sequence(pulserId, ch2, 1, actual_ch2_segments, ...);
seg_arb_waveform(pulserId, ch2, 1, seqList, loopCount);
// loopCount = Ch2LoopCount (repeats sequence Ch2LoopCount times)
```

#### 5. **Execution**

```c
pulse_exec(TestMode);  // Executes both channels simultaneously
while(pulse_exec_status(&t) == 1) { Sleep(100); }  // Wait for completion
```

#### 6. **Data Acquisition**

**a) Waveform Fetch**:
```c
// Calculate expected samples
total_measurement_time = period * burst_count;
expectedSamples = total_measurement_time * SampleRate + 1;
maxSamples = min(expectedSamples, 1000000);  // Cap at 1M (hardware limit)

// Fetch full waveform
pulse_fetch(pulserId, chan, 0, maxSamples-1, 
            waveformV, waveformI, waveformT, NULL);
```

**b) Data Extraction** (for `acqType=1`):

**Method 1: Threshold-Based Detection**:
```c
// Detect pulses by voltage threshold
for each pulse:
    pulseStartIdx = first sample where |V| > threshold
    pulseEndIdx = first sample where |V| < threshold after pulseStartIdx
    
    // Extract 40-80% window
    pulseWidthSamples = pulseEndIdx - pulseStartIdx;
    measStartSample = pulseStartIdx + 0.4 * pulseWidthSamples;
    measEndSample = pulseStartIdx + 0.8 * pulseWidthSamples;
    
    // Average samples in window
    V_Meas[outputIdx] = average(waveformV[measStartSample:measEndSample]);
    I_Meas[outputIdx] = average(waveformI[measStartSample:measEndSample]);
    T_Stamp[outputIdx] = average(waveformT[measStartSample:measEndSample]);
```

**Method 2: Time-Based Detection** (fallback):
```c
// If threshold detection fails, use evenly-spaced assumption
estimatedPeriod = totalTime / burst_count;
for each pulse:
    pulseStartTime = waveformT[0] + pulseIdx * estimatedPeriod;
    measStartTime = pulseStartTime + delay + rise + width * 0.4;
    measEndTime = pulseStartTime + delay + rise + width * 0.8;
    
    // Average all samples in time window
    V_Meas[outputIdx] = average(waveformV where T in [measStartTime, measEndTime]);
```

#### 7. **Data Transfer Back to Python**

**Parameter Mapping**:
```
Parameter 23 = V_Meas[] (measured voltages)
Parameter 25 = I_Meas[] (measured currents)
Parameter 27 = T_Stamp[] (measurement timestamps)
```

**Python Retrieval**:
```python
voltage = controller._query_gp(23, num_points)
current = controller._query_gp(25, num_points)
time_axis = controller._query_gp(27, num_points)
```

---

## Memory Management

### C Module Memory

- **CH1 segment arrays**: Allocated dynamically (6 segments)
- **CH2 segment arrays**: Allocated dynamically if auto-build mode, or uses provided arrays
- **Waveform buffers**: Allocated based on `expectedSamples` (capped at 1M samples - hardware limit)
- **Output arrays**: Provided by caller (Python via KXCI), C module writes to them

### Memory Limits

| Buffer Type | Maximum Size | Typical Size |
|-------------|--------------|--------------|
| Waveform buffers | **1,000,000 samples** (hardware limit) | `period × SampleRate × burst_count` |
| Output arrays | 32,767 elements | `burst_count` (average mode) or `10000` (discrete) |
| CH2 segment arrays | 2048 segments | 6 (auto-build) or user-defined |

**Note**: The hardware limit is 1 million samples per A/D test. At 200 MSa/s, this allows up to **5 ms** measurement duration. For longer measurements, reduce the sample rate.

---

## Error Handling

### Common Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `-17001` | Instrument not in configuration | Check PMU_ID |
| `-17002` | Failed to get instrument ID | Verify instrument connection |
| `-804` | seg_arb not valid in current mode | Ensure SARB mode is used |
| `-122` | Invalid parameter | Check segment times (≥20ns), loop count (≥1.0) |
| `-824` | Off-time too small | Increase period or reduce pulse width |
| `-831` | Too many samples | Reduce `burst_count` or `period` |
| `-844` | Invalid sweep parameters | Check startV, stopV, stepV |
| `-998` | Execution timeout | Check instrument status |

### Validation Points

1. **Period validation**: Automatically adjusts if too small
2. **Segment time validation**: All segments must be ≥ 20ns
3. **Array size validation**: Output arrays must be large enough
4. **Total sample validation**: `pointsPerWfm × dSweeps ≤ 65536`
5. **CH2 loop count validation**: Must be ≥ 1.0

---

## Performance Considerations

### Sample Rate vs. Memory

- **Higher sample rate**: Better time resolution, but more memory required
- **Lower sample rate**: Less memory, but may miss fast transients
- **Recommendation**: Use 200 MHz for fast pulses (<1µs), lower rates for slower pulses

### Array Sizing Strategy

**For average mode** (`acqType=1`):
- Set `array_size = burst_count` (one value per pulse)
- Memory efficient, fast processing

**For discrete mode** (`acqType=0`):
- Set `array_size = period × sample_rate × burst_count + margin`
- Full waveform capture, more memory required
- Watch for 65536 total sample limit

### Timing Optimization

- **Minimum period**: Use the smallest valid period to maximize measurement rate
- **CH2 timing**: Set `Ch2Period` to desired delay before laser pulse (independent of CH1)
- **Segment times**: Keep all segment times ≥ 20ns to avoid validation errors

---

## Important Notes

### Channel Assignment

- **CH1**: Always used for measurement (voltage/current capture)
- **CH2**: Always used for laser pulse (source only, no measurement)
- Both channels must be properly connected to the device

### Measurement Window

- The 40-80% window is **hardcoded** in the C source
- To change it, edit:
  ```c
  measurementStartFrac = 0.4;  // Change to desired start fraction
  measurementEndFrac = 0.8;    // Change to desired end fraction
  ```

### CH2 Loop Count

- **Single pulse**: `Ch2LoopCount = 1.0` (default)
- **Repeated pulses**: Set `Ch2LoopCount` to desired number of repetitions
- **Auto-calculation**: Python can auto-calculate to match CH1 duration (set `--ch2-loop-count 0`)

### SARB Mode Requirement

- **Both channels** use seg_arb, so PMU **must** be in SARB mode
- The C code automatically sets `PULSE_MODE_SARB` during initialization
- If you see error `-804`, the PMU is not in SARB mode

---

## Files

- **`Read_With_Laser_Pulse_SegArb_Python.py`**: Python script for measurement execution
- **`Read_With_Laser_Pulse_SegArb.c`**: C module implementing waveform generation and data extraction
- **`README.md`**: This documentation file

---

## References

- Keithley 4200A-SCS User Manual
- KXCI (Keithley eXternal Control Interface) Documentation
- PMU Programming Guide
- Seg_Arb Waveform Programming Reference

---

## Troubleshooting

### Common Issues

1. **Error -804 (seg_arb not valid)**:
   - **Cause**: PMU not in SARB mode
   - **Solution**: C code should auto-set SARB mode, but check initialization

2. **Too few measurements returned**:
   - **Cause**: Array size too small or threshold detection failed
   - **Solution**: Increase `array_size` or check voltage levels

3. **Period too small error**:
   - **Cause**: Requested period < minimum (120ns or 280ns)
   - **Solution**: System auto-adjusts, but increase period if needed

4. **Total samples exceed maximum**:
   - **Cause**: `period × SampleRate × burst_count > 1,000,000` (hardware limit)
   - **Solution**: Reduce `burst_count`, `period`, or `SampleRate`
   - **Note**: At 200 MSa/s, maximum duration is 5 ms. For longer measurements, reduce sample rate.

5. **CH2 not firing**:
   - **Cause**: `Ch2Enable=0` or `Ch2LoopCount < 1.0`
   - **Solution**: Set `--ch2-enable 1` and `--ch2-loop-count 1.0` (or higher)

### Debug Mode

Enable detailed logging:

```bash
python Read_With_Laser_Pulse_SegArb_Python.py \
    --clarius-debug 1 \
    --burst-count 10 \
    ...
```

This will print:
- Segment details for both channels
- Timing calculations
- Measurement window extraction
- Data processing steps

---

## Summary of System Limits

| Category | Limit | Notes |
|----------|-------|-------|
| **Output arrays** | 100-32767 | V_Meas, I_Meas, T_Stamp |
| **CH2 segments** | 3-2048 | Manual mode only |
| **Total samples** | ≤ 1,000,000 | Hardware limit per A/D test (4225-PMU) |
| **Sweep points** | ≤ 65536 | Maximum voltage steps (for voltage sweeps) |
| **Segment time** | ≥ 20ns | Minimum for any segment |
| **CH1 period** | ≥ 120ns (10V) | Minimum period |
| | ≥ 280ns (40V) | Minimum period (higher range) |
| **Sample rate** | 1-200 MHz | Maximum 200 MHz |
| **Burst count** | 1-100000 | Maximum pulses |
| **CH2 loop count** | ≥ 1.0 | Minimum repetitions |

These limits ensure stable operation and prevent memory overflow errors.

