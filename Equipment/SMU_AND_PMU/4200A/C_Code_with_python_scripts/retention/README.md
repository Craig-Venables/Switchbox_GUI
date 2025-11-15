# PMU Retention Measurement Module

> **⚠️ IMPORTANT: Dual-Channel Mode Required**
> 
> This module operates in **dual-channel mode** using PMU channels 1 and 2. Both channels must be connected to your device:
> - **Channel 1 (Force Channel)**: Applies voltage to the device
> - **Channel 2 (Measure Channel)**: Measures current through the device
> 
> Ensure proper connections are made before running measurements.

```
VOLTAGE WAVEFORM - RETENTION PATTERN
═══════════════════════════════════════════════════════════════════════════════

Voltage (V)
    │
PulseV ─┐     ┌──┐     ┌──┐     ┌──┐     ┌──┐
        │     │  │     │  │     │  │     │  │
        │     │  │     │  │     │  │     │  │
measV ──┼──┐  │  │  ┌──│  │  ┌──│  │  ┌──│  │  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐
        │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
   0V ──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴───> Time
        │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
        │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
        └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘
        Init  Pulse Pulse Pulse Pulse Pulse  Ret   Ret   Ret   Ret   Ret
        Read  #1   #2   #3   #4   #5        #1    #2    #3    #4    #5

LEGEND:
  ────  = Voltage transition (rise/fall time)
  ││││  = Flat top (pulse width or measurement window)
  ┌──┐  = Programming pulse (at PulseV, typically 2-5V)
  └──┘  = Measurement pulse (at measV, typically 0.3-0.5V)

NOTES:
  • Initial measurements: Baseline reads before programming (NumInitialMeasPulses)
  • Programming pulses: High voltage pulses to program device state (NumPulses)
  • Retention measurements: Reads after programming to track degradation (NumbMeasPulses)
  • Total measurements: NumInitialMeasPulses + NumbMeasPulses
```

## Overview

This module implements a **retention measurement pattern** for memristor devices using the Keithley 4200A-SCS Programmable Measurement Unit (PMU). The pattern performs initial baseline measurements, applies programming pulses to set the device state, and then monitors resistance changes over time (retention degradation).

This measurement pattern is essential for studying:
- **Data retention** in resistive memory devices
- **Resistance drift** over time after programming
- **State stability** of programmed memristor devices
- **Retention failure** mechanisms and time-to-failure

---

## Waveform Structure

The measurement consists of three main sections:

1. **Initial Measurement Pulses** (`NumInitialMeasPulses`): Baseline resistance reads before programming
2. **Programming Pulse Sequence** (`NumPulses`): Multiple programming pulses to set device state
3. **Retention Measurement Pulses** (`NumbMeasPulses`): Periodic reads after programming to track degradation

### Detailed Segment Structure

#### Initial Measurement Pulses

Each initial measurement pulse follows this pattern:

1. **RISE**: 0V → measV (over `riseTime`)
2. **TOP**: Hold at measV for `measWidth` (measurement window)
3. **FALL**: measV → measV (over `riseTime`, optional settling)
4. **FALL**: measV → 0V (over `riseTime`)
5. **DELAY**: Hold at 0V for `measDelay`

#### Programming Pulse Sequence

Each programming pulse consists of 4 segments:

1. **RISE**: 0V → PulseV (over `PulseRiseTime`)
2. **TOP**: Hold at PulseV for `PulseWidth` (flat top duration)
3. **FALL**: PulseV → 0V (over `PulseFallTime`)
4. **WAIT**: Hold at 0V for `PulseDelay` (delay between pulses)

**Critical Design**: The `seg_arb_sequence` function creates segments from `v[i]` (START) to `v[i+1]` (END) over `t[i]`. To create a flat top, we set:
- `v[i] = PulseV` (START voltage)
- `t[i] = PulseWidth` (duration)
- `v[i+1] = PulseV` (END voltage, same as START)

This ensures a clean square waveform with a flat top.

#### Retention Measurement Pulses

Each retention measurement pulse follows the same pattern as initial measurements:

1. **RISE**: 0V → measV (over `riseTime`)
2. **TOP**: Hold at measV for `measWidth` (measurement window)
3. **FALL**: measV → measV (over `riseTime`, optional settling)
4. **FALL**: measV → 0V (over `riseTime`)
5. **DELAY**: Hold at 0V for `measDelay`

The measurement window is defined as **40-90%** of the `measWidth` duration (ratio = 0.4), ensuring measurements are taken during the stable flat-top portion of the pulse.

---

## Parameters

### Input Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `riseTime` | double | 3e-8 s | 2e-8 to 1 s | Rise/fall time for measurement pulses |
| `resetV` | double | 4 V | -20 to 20 V | Legacy parameter (not used) |
| `resetWidth` | double | 1e-6 s | 2e-8 to 1 s | Legacy parameter (not used) |
| `resetDelay` | double | 1e-6 s | 2e-8 to 1 s | Initial delay before first measurement |
| `measV` | double | 0.5 V | -20 to 20 V | Measurement voltage (read pulse amplitude) |
| `measWidth` | double | 2e-6 s | 2e-8 to 1 s | Measurement pulse width (flat top duration) |
| `measDelay` | double | 1e-6 s | 2e-8 to 1 s | Delay between measurement pulses |
| `setWidth` | double | 1e-6 s | 2e-8 to 1 s | Legacy parameter (not used) |
| `setFallTime` | double | 3e-8 s | 2e-8 to 1 s | Optional settling time at measV before fall |
| `setDelay` | double | 1e-6 s | 2e-8 to 1 s | Legacy parameter (not used) |
| `setStartV` | double | 0 V | -20 to 20 V | Legacy parameter (not used) |
| `setStopV` | double | 4 V | -20 to 20 V | Legacy parameter (not used) |
| `steps` | int | 5 | 1+ | Legacy parameter (forced to 1 internally) |
| `IRange` | double | 1e-2 A | 100e-9 to 0.8 A | Current range for measurements |
| `max_points` | int | 10000 | 12 to 30000 | Maximum number of data points to acquire |
| `NumInitialMeasPulses` | int | 1 | 1 to 100 | Number of initial baseline measurements |
| `NumPulses` | int | 5 | 1 to 100 | Number of programming pulses |
| `PulseWidth` | double | 1e-6 s | 2e-8 to 1 s | Programming pulse width (flat top duration) |
| `PulseV` | double | 4 V | -20 to 20 V | Programming pulse voltage amplitude |
| `PulseRiseTime` | double | 3e-8 s | 2e-8 to 1 s | Rise time for programming pulse |
| `PulseFallTime` | double | 3e-8 s | 2e-8 to 1 s | Fall time for programming pulse |
| `PulseDelay` | double | 1e-6 s | 2e-8 to 1 s | Delay between programming pulses |
| `NumbMeasPulses` | int | 8 | 8 to 1000 | Number of retention measurement pulses |
| `ClariusDebug` | int | 0 | 0 to 1 | Enable debug output (1 = enabled) |

### Output Parameters

| Parameter | GP # | Type | Description |
|-----------|------|------|-------------|
| `setV` | 20 | D_ARRAY_T | Measured voltages at each measurement point |
| `setI` | 22 | D_ARRAY_T | Measured currents at each measurement point |
| `PulseTimes` | 30 | D_ARRAY_T | Timestamps for each measurement point |
| `out1` | 31 | D_ARRAY_T | Debug output: Force voltage (VF) |
| `setR` | 16 | D_ARRAY_T | Calculated resistances (legacy, use setV/setI) |
| `resetR` | 18 | D_ARRAY_T | Legacy output (not used) |
| `out2` | 28 | D_ARRAY_T | Debug output: Time array (T) |

**Note**: The actual measurement data is in `setV` (parameter 20) and `setI` (parameter 22). Resistance can be calculated as `R = V/I`. Total measurements = `NumInitialMeasPulses + NumbMeasPulses`.

---

## Usage Examples

### Basic Retention Measurement (5 programming pulses, 50 retention reads)

```python
python run_pmu_retention.py \
    --gpib-address GPIB0::17::INSTR \
    --num-initial-meas-pulses 2 \
    --num-pulses-seq 5 \
    --pulse-v 4.0 \
    --pulse-width 1e-6 \
    --pulse-rise-time 1e-7 \
    --pulse-fall-time 1e-7 \
    --pulse-delay 1e-6 \
    --num-pulses 50 \
    --meas-v 0.3 \
    --meas-width 2e-6
```

### Extended Retention Study (10 programming pulses, 200 retention reads)

```python
python run_pmu_retention.py \
    --gpib-address GPIB0::17::INSTR \
    --num-initial-meas-pulses 3 \
    --num-pulses-seq 10 \
    --pulse-v 5.0 \
    --pulse-width 2e-6 \
    --pulse-rise-time 1e-7 \
    --pulse-fall-time 1e-7 \
    --pulse-delay 2e-6 \
    --num-pulses 200 \
    --meas-v 0.3 \
    --meas-width 2e-6 \
    --meas-delay 1e-6 \
    --max-points 30000
```

### Dry Run (print command without executing)

```python
python run_pmu_retention.py --dry-run --num-pulses-seq 5 --num-pulses 50
```

---

## Output Data

The module returns arrays containing:

- **Voltage values** (`setV`): Measured voltage at each measurement point
- **Current values** (`setI`): Measured current at each measurement point
- **Timestamps** (`PulseTimes`): Time of each measurement relative to waveform start
- **Resistance** (calculated): `R = |V| / |I|` for each measurement point

**Array Sizes**: Total measurements = `NumInitialMeasPulses + NumbMeasPulses`
- First `NumInitialMeasPulses` measurements: Initial baseline reads
- Remaining `NumbMeasPulses` measurements: Retention reads after programming

---

## Technical Implementation

### C Module: `pmu_retention_dual_channel.c`

The C module generates a waveform using `seg_arb_sequence` with the following structure:

1. **Initial Setup**: Allocates arrays for voltage/time segments and measurement windows
2. **Initial Measurements**: Generates segments for `NumInitialMeasPulses` baseline reads
3. **Programming Pulses**: Generates segments for `NumPulses` programming pulses (4 segments each)
4. **Retention Measurements**: Generates segments for `NumbMeasPulses` retention reads
5. **Hardware Execution**: Calls `ACraig1_retention_pulseNK()` (via `retention_pulse_ilimit_dual_channel()`) to execute waveform
6. **Data Extraction**: Extracts voltage and current from measurement windows (40-90% of measWidth)
7. **Resistance Calculation**: Computes `R = |V| / |I|` for each measurement point
8. **Output**: Populates output arrays via `GP` parameters

### Low-Level Driver: `retention_pulse_ilimit_dual_channel.c`

The low-level driver (`retention_pulse_ilimit_dual_channel`) handles:
- PMU channel configuration (ForceCh=1, MeasureCh=2)
- Voltage/current range selection
- Current limit enforcement
- Hardware waveform execution via `seg_arb_sequence`
- Raw data acquisition and storage

---

## C Program Architecture and Data Flow

### Overview of the System Architecture

The measurement system consists of three main layers:

```
Python Script (run_pmu_retention.py)
    ↓ [EX command via KXCI/GPIB]
C Module (pmu_retention_dual_channel.c)
    ↓ [Waveform segments]
Low-Level Driver (retention_pulse_ilimit_dual_channel.c)
    ↓ [Hardware commands]
Keithley 4200A-SCS PMU Hardware
    ↓ [Raw measurements]
Low-Level Driver
    ↓ [Processed data]
C Module
    ↓ [GP parameters]
Python Script
```

### Step-by-Step Execution

1. **Python Script Initialization**:
   - Parses command-line arguments
   - Builds `EX` command string with all parameters
   - Connects to instrument via KXCI/GPIB

2. **Command Transmission**:
   - Enters UL (User Library) mode
   - Sends `EX A_Read_Train pmu_retention_dual_channel(...)` command
   - Waits for execution completion

3. **C Module Execution** (`pmu_retention_dual_channel.c`):
   - Validates input parameters
   - Allocates memory for waveform segments and measurement windows
   - Generates voltage/time arrays for `seg_arb_sequence`:
     - Initial delay segment
     - For each of `NumInitialMeasPulses` initial measurements:
       - RISE: 0V → measV (riseTime)
       - TOP: measV → measV (measWidth)
       - FALL: measV → measV (riseTime, optional)
       - FALL: measV → 0V (riseTime)
       - DELAY: 0V → 0V (measDelay)
     - For each of `NumPulses` programming pulses:
       - RISE: 0V → PulseV (PulseRiseTime)
       - TOP: PulseV → PulseV (PulseWidth)
       - FALL: PulseV → 0V (PulseFallTime)
       - WAIT: 0V → 0V (PulseDelay)
     - For each of `NumbMeasPulses` retention measurements:
       - RISE: 0V → measV (riseTime)
       - TOP: measV → measV (measWidth)
       - FALL: measV → measV (riseTime, optional)
       - FALL: measV → 0V (riseTime)
       - DELAY: 0V → 0V (measDelay)
   - Records measurement window times (40-90% of measWidth)
   - Calls `ACraig1_retention_pulseNK()` to execute waveform

4. **Low-Level Driver Execution** (`retention_pulse_ilimit_dual_channel.c`):
   - Configures PMU channels (ForceCh=1, MeasureCh=2)
   - Sets voltage/current ranges based on PulseV, measV, and IRange
   - Executes waveform via `seg_arb_sequence` with voltage/time arrays
   - Acquires raw voltage and current data at hardware sample rate
   - Stores data in global arrays: `VFret`, `IFret`, `VMret`, `IMret`, `Tret`

5. **Data Extraction** (back in C module):
   - For each measurement window (initial + retention):
     - Calls `ret_find_value()` to extract voltage from `VMret` array
     - Calls `ret_find_value()` to extract current from `IMret` array
     - Calculates resistance: `R = |V| / |I|`
     - Stores results in output arrays: `setV`, `setI`, `PulseTimes`

6. **Data Transfer to Python**:
   - Python script queries `GP` parameters:
     - `GP 20 N` → `setV` array (N = total_probes)
     - `GP 22 N` → `setI` array (N = total_probes)
     - `GP 30 N` → `PulseTimes` array (N = total_probes)
     - `GP 31 N` → `out1` array (N = total_probes, debug)
   - KXCI transfers data from C module memory to Python
   - Python processes and displays results

### Memory Management

- **Waveform Arrays**: Allocated dynamically based on `NumInitialMeasPulses`, `NumPulses`, and `NumbMeasPulses`
  - `times[]`: Segment durations
  - `volts[]`: Segment voltages
- **Measurement Windows**: Allocated for `NumInitialMeasPulses + NumbMeasPulses` measurements
  - `measMinTime[]`: Start time of each measurement window
  - `measMaxTime[]`: End time of each measurement window
- **Raw Data Arrays**: Allocated in low-level driver based on `max_points`
  - `VFret[]`: Force channel voltage (size = max_points)
  - `IFret[]`: Force channel current (size = max_points)
  - `VMret[]`: Measure channel voltage (size = max_points)
  - `IMret[]`: Measure channel current (size = max_points)
  - `Tret[]`: Time array (size = max_points)
- **Output Arrays**: Provided by Python script (pre-allocated)
  - `setV[]`: Measured voltages (size = setV_size)
  - `setI[]`: Measured currents (size = setI_size)
  - `PulseTimes[]`: Timestamps (size = PulseTimesSize)

### Error Handling

- **Parameter Validation**: Checks array sizes, parameter ranges, and required values
- **Memory Allocation**: Verifies successful allocation before use
- **Hardware Errors**: Returns negative error codes on failure
- **Data Extraction**: Handles cases where measurement windows fall outside acquired data

### Key Design Decisions

1. **Measurement Window (40-90%)**: Ensures measurements are taken during stable flat-top portion, avoiding transients
2. **Dual-Channel Mode**: Separates force and measure channels for accurate current measurement
3. **Flat-Top Pulses**: Programming pulses use explicit START/END voltage points to ensure clean square waveforms
4. **Separate Initial/Retention Measurements**: Allows tracking of baseline state before programming and degradation after programming

---

## System Limits and Constraints

### Array Size Limits

- **Maximum `NumInitialMeasPulses`**: 100
- **Maximum `NumPulses`**: 100
- **Maximum `NumbMeasPulses`**: 1000
- **Total Measurements**: `NumInitialMeasPulses + NumbMeasPulses` (maximum 1100)
- **Maximum `max_points`**: 30,000 (hardware acquisition limit)
- **Output Array Sizes**: Must be ≥ `NumInitialMeasPulses + NumbMeasPulses`

### Timing Limits

- **Minimum Segment Time**: 20 ns (hardware limit: 2e-8 s)
- **Maximum Segment Time**: 1 s
- **Measurement Window**: 40-90% of `measWidth` (ratio = 0.4)
- **Total Waveform Duration**: 
  ```
  TotalTime ≈ resetDelay 
            + NumInitialMeasPulses × (riseTime + measWidth + riseTime + measDelay)
            + NumPulses × (PulseRiseTime + PulseWidth + PulseFallTime + PulseDelay)
            + NumbMeasPulses × (riseTime + measWidth + riseTime + measDelay)
  ```

### Voltage/Current Limits

- **Voltage Range**: -20 V to +20 V
- **Current Range**: 100 nA to 0.8 A (set via `IRange`)
- **Programming Voltage (`PulseV`)**: Typically 2-5 V (device-dependent)
- **Measurement Voltage (`measV`)**: Typically 0.3-0.5 V (low voltage to avoid programming)

### Sampling Limits

- **Maximum Sample Rate**: 200 MSa/s (hardware limit)
- **Maximum Samples per A/D Test**: 1,000,000 samples (hardware limit)
- **Automatic Rate Adjustment**: Driver adjusts sample rate based on `max_points` and total waveform duration
- **Minimum Samples**: 12 (hardware requirement)

### Memory Limits

- **Waveform Segments**: Maximum ~4000 segments (for NumPulses = 100, NumbMeasPulses = 1000)
- **Raw Data Arrays**: ~240 MB for 1M samples (5 arrays × 1M × 8 bytes)
- **Output Arrays**: ~26 KB for 1100 measurements (3 arrays × 1100 × 8 bytes)

### Total Sample Limits

- **Hardware Limit**: 1,000,000 samples per A/D test (Keithley 4200A-SCS 4225-PMU specification)
- **Practical Limit**: 30,000 samples (default `max_points`) for reasonable data retrieval speed
- **Measurement Duration**: 
  - At 200 MSa/s: Up to 5 ms total waveform duration
  - At 10 MSa/s: Up to 100 ms total waveform duration
  - At 1 MSa/s: Up to 1 s total waveform duration

**Recommendation**: For longer retention studies, reduce sample rate or use fewer measurement pulses.

---

## Troubleshooting

### No Data Returned

- **Check array sizes**: Ensure `setV_size`, `setI_size`, and `PulseTimesSize` are ≥ `NumInitialMeasPulses + NumbMeasPulses`
- **Verify GP parameters**: Check that parameters 20, 22, and 30 are being queried correctly
- **Check hardware connection**: Ensure PMU channels 1 and 2 are properly connected

### Incorrect Resistance Values

- **Verify measurement voltage**: Check that `measV` is appropriate for your device (typically 0.3-0.5V)
- **Check current range**: Ensure `IRange` is set correctly (too high = poor resolution, too low = saturation)
- **Verify measurement window**: Measurements are taken at 40-90% of `measWidth` (ensure this is during stable portion)

### Programming Pulses Not Working

- **Check pulse voltage**: Ensure `PulseV` is appropriate for your device (typically 2-5V)
- **Verify pulse width**: Ensure `PulseWidth` is sufficient for device programming (typically 1-10 µs)
- **Check current limits**: Device may be drawing too much current during programming (check `IRange`)

### Measurement Duration Too Short

- **Increase `max_points`**: Maximum is 30,000 (or 1,000,000 for hardware limit)
- **Reduce sample rate**: Driver automatically adjusts, but you can reduce `max_points` to force lower rate
- **Reduce number of pulses**: Fewer pulses = shorter total duration = more samples per pulse

### Hardware Errors

- **Check dual-channel mode**: Both CH1 and CH2 must be connected
- **Verify voltage/current ranges**: Ensure ranges are appropriate for your device
- **Check current limits**: Device may be drawing too much current (check `IRange` and device characteristics)

---

## Files

- **`run_pmu_retention.py`**: Python script for executing measurements
- **`pmu_retention_dual_channel.c`**: C module implementing waveform generation and data processing
- **`retention_pulse_ilimit_dual_channel.c`**: Low-level driver for PMU hardware control

---

## See Also

- **Readtrain Module**: For simple sequential read measurements without programming
- **Potentiation-Depression Module**: For alternating positive/negative programming pulses
- **Pulse-Read Interleaved Module**: For pulse-read-pulse-read patterns

