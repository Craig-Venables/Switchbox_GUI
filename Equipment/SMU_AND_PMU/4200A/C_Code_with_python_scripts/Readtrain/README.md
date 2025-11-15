# PMU Readtrain Measurement Module

> **⚠️ IMPORTANT: Dual-Channel Mode Required**
> 
> This module operates in **dual-channel mode** using PMU channels 1 and 2. Both channels must be connected to your device:
> - **Channel 1 (Force Channel)**: Applies voltage to the device
> - **Channel 2 (Measure Channel)**: Measures current through the device
> 
> Ensure proper connections are made before running measurements.

```
VOLTAGE WAVEFORM - READTRAIN PATTERN
═══════════════════════════════════════════════════════════════════════════════

Voltage (V)
    │
measV ─┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐
       │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
   0V ─┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴───> Time
       │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
       │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
       └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘
       Read  Read  Read  Read  Read  Read  Read  Read  Read  Read
        #1   #2   #3   #4   #5   #6   #7   #8   #9   #10

LEGEND:
  ────  = Voltage transition (rise/fall time)
  ││││  = Flat top (measurement window at measV)
  ┌──┐  = Measurement pulse (read pulse)
  └──┘  = Measurement pulse (read pulse)

NOTES:
  • All pulses are measurement pulses (reads) at measV (typically 0.3-0.5V)
  • Total measurements: NumbMeasPulses + 2 (baseline + second read + measurement pulses)
  • Pattern: Initial delay → Read #1 → Read #2 → Read #3 → ... → Read #N
  • Each read: 0V → measV (riseTime) → measV (measWidth) → 0V (riseTime) → delay (measDelay)
```

## Overview

This module implements a **readtrain measurement pattern** for memristor devices using the Keithley 4200A-SCS Programmable Measurement Unit (PMU). The pattern performs a sequence of consecutive measurement pulses (reads) to monitor device resistance over time without applying programming pulses.

This measurement pattern is essential for studying:
- **Resistance stability** over time
- **Read disturb** effects (resistance changes due to repeated reads)
- **Baseline resistance** monitoring
- **Temporal drift** in device characteristics

---

## Waveform Structure

The measurement consists of **NumbMeasPulses + 2** total measurement pulses:

1. **Initial Read #1** (baseline measurement)
2. **Initial Read #2** (second baseline measurement)
3. **Measurement Pulses #3 through #(NumbMeasPulses+2)** (sequential reads)

### Detailed Segment Structure

Each measurement pulse follows this pattern:

1. **RISE**: 0V → measV (over `riseTime`)
2. **TOP**: Hold at measV for `measWidth` (measurement window)
3. **FALL**: measV → measV (over `setFallTime`, optional settling)
4. **FALL**: measV → 0V (over `riseTime`)
5. **DELAY**: Hold at 0V for `measDelay`

The measurement window is defined as **40-90%** of the `measWidth` duration (ratio = 0.4), ensuring measurements are taken during the stable flat-top portion of the pulse.

---

## Parameters

### Input Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `riseTime` | double | 3e-8 s | 2e-8 to 1 s | Rise/fall time for measurement pulses |
| `resetV` | double | 4 V | -20 to 20 V | Legacy parameter (not used in readtrain) |
| `resetWidth` | double | 1e-6 s | 2e-8 to 1 s | Legacy parameter (not used in readtrain) |
| `resetDelay` | double | 1e-6 s | 2e-8 to 1 s | Initial delay before first measurement |
| `measV` | double | 0.5 V | -20 to 20 V | Measurement voltage (read pulse amplitude) |
| `measWidth` | double | 2e-6 s | 2e-8 to 1 s | Measurement pulse width (flat top duration) |
| `measDelay` | double | 1e-6 s | 2e-8 to 1 s | Delay between measurement pulses |
| `setWidth` | double | 1e-6 s | 2e-8 to 1 s | Legacy parameter (not used in readtrain) |
| `setFallTime` | double | 3e-8 s | 2e-8 to 1 s | Optional settling time at measV before fall |
| `setDelay` | double | 1e-6 s | 2e-8 to 1 s | Legacy parameter (not used in readtrain) |
| `setStartV` | double | 0 V | -20 to 20 V | Legacy parameter (not used in readtrain) |
| `setStopV` | double | 4 V | -20 to 20 V | Legacy parameter (not used in readtrain) |
| `steps` | int | 5 | 1+ | Legacy parameter (forced to 1 internally) |
| `IRange` | double | 1e-2 A | 100e-9 to 0.8 A | Current range for measurements |
| `max_points` | int | 10000 | 12 to 30000 | Maximum number of data points to acquire |
| `NumbMeasPulses` | int | 8 | 8 to 1000 | Number of measurement pulses (total = NumbMeasPulses + 2) |
| `ClariusDebug` | int | 0 | 0 to 1 | Enable debug output (1 = enabled) |

### Output Parameters

| Parameter | GP # | Type | Description |
|-----------|------|------|-------------|
| `setV` | 20 | D_ARRAY_T | Measured voltages at each measurement point |
| `setI` | 22 | D_ARRAY_T | Measured currents at each measurement point |
| `PulseTimes` | 31 | D_ARRAY_T | Timestamps for each measurement point |
| `setR` | 16 | D_ARRAY_T | Calculated resistances (legacy, use setV/setI) |
| `resetR` | 18 | D_ARRAY_T | Legacy output (not used in readtrain) |
| `out1` | 25 | D_ARRAY_T | Debug output: Force voltage (VF) |
| `out2` | 28 | D_ARRAY_T | Debug output: Time array (T) |

**Note**: The actual measurement data is in `setV` (parameter 20) and `setI` (parameter 22). Resistance can be calculated as `R = V/I`.

---

## Usage Examples

### Basic Readtrain (8 measurement pulses)

```python
python run_readtrain_dual_channel.py \
    --gpib-address GPIB0::17::INSTR \
    --numb-meas-pulses 8 \
    --meas-v 0.5 \
    --meas-width 2e-6
```

### Extended Readtrain (100 measurement pulses)

```python
python run_readtrain_dual_channel.py \
    --gpib-address GPIB0::17::INSTR \
    --numb-meas-pulses 100 \
    --meas-v 0.3 \
    --meas-width 2e-6 \
    --meas-delay 1e-6 \
    --max-points 30000
```

### Dry Run (print command without executing)

```python
python run_readtrain_dual_channel.py --dry-run --numb-meas-pulses 10
```

---

## Output Data

The module returns arrays containing:

- **Voltage values** (`setV`): Measured voltage at each measurement point
- **Current values** (`setI`): Measured current at each measurement point
- **Timestamps** (`PulseTimes`): Time of each measurement relative to waveform start
- **Resistance** (calculated): `R = |V| / |I|` for each measurement point

**Array Sizes**: Total measurements = `NumbMeasPulses + 2`
- First measurement: Baseline read #1
- Second measurement: Baseline read #2
- Measurements 3 through (NumbMeasPulses+2): Sequential read pulses

---

## Technical Implementation

### C Module: `readtrain_dual_channel.c`

The C module generates a waveform using `seg_arb_sequence` with the following structure:

1. **Initial Setup**: Allocates arrays for voltage/time segments and measurement windows
2. **Waveform Generation**: Creates segments for each measurement pulse
3. **Hardware Execution**: Calls `read_train_pulseNK()` (via `read_train_ilimit()`) to execute waveform
4. **Data Extraction**: Extracts voltage and current from measurement windows (40-90% of measWidth)
5. **Resistance Calculation**: Computes `R = |V| / |I|` for each measurement point
6. **Output**: Populates output arrays via `GP` parameters

### Low-Level Driver: `read_train_ilimit.c`

The low-level driver (`read_train_ilimit`) handles:
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
Python Script (run_readtrain_dual_channel.py)
    ↓ [EX command via KXCI/GPIB]
C Module (readtrain_dual_channel.c)
    ↓ [Waveform segments]
Low-Level Driver (read_train_ilimit.c)
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
   - Sends `EX A_Read_Train readtrain_dual_channel(...)` command
   - Waits for execution completion

3. **C Module Execution** (`readtrain_dual_channel.c`):
   - Validates input parameters
   - Allocates memory for waveform segments and measurement windows
   - Generates voltage/time arrays for `seg_arb_sequence`:
     - Initial delay segment
     - For each of (NumbMeasPulses + 2) measurement pulses:
       - RISE segment: 0V → measV (riseTime)
       - TOP segment: measV → measV (measWidth)
       - FALL segment: measV → measV (setFallTime, optional)
       - FALL segment: measV → 0V (riseTime)
       - DELAY segment: 0V → 0V (measDelay)
   - Records measurement window times (40-90% of measWidth)
   - Calls `read_train_pulseNK()` to execute waveform

4. **Low-Level Driver Execution** (`read_train_ilimit.c`):
   - Configures PMU channels (ForceCh=1, MeasureCh=2)
   - Sets voltage/current ranges based on measV and IRange
   - Executes waveform via `seg_arb_sequence` with voltage/time arrays
   - Acquires raw voltage and current data at hardware sample rate
   - Stores data in global arrays: `VFret`, `IFret`, `VMret`, `IMret`, `Tret`

5. **Data Extraction** (back in C module):
   - For each measurement window:
     - Calls `read_train_find_value()` to extract voltage from `VMret` array
     - Calls `read_train_find_value()` to extract current from `IMret` array
     - Calculates resistance: `R = |V| / |I|`
     - Stores results in output arrays: `setV`, `setI`, `PulseTimes`

6. **Data Transfer to Python**:
   - Python script queries `GP` parameters:
     - `GP 20 N` → `setV` array (N = setV_size)
     - `GP 22 N` → `setI` array (N = setI_size)
     - `GP 31 N` → `PulseTimes` array (N = PulseTimesSize)
   - KXCI transfers data from C module memory to Python
   - Python processes and displays results

### Memory Management

- **Waveform Arrays**: Allocated dynamically based on `NumbMeasPulses`
  - `times[]`: Segment durations (size = 20 + 4*(NumbMeasPulses-2))
  - `volts[]`: Segment voltages (size = times_count + 1)
- **Measurement Windows**: Allocated for `NumbMeasPulses + 2` measurements
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
3. **Sequential Reads**: All pulses are measurement pulses (no programming), ideal for read disturb studies
4. **Legacy Parameters**: Maintains compatibility with older code while ignoring unused parameters

---

## System Limits and Constraints

### Array Size Limits

- **Maximum `NumbMeasPulses`**: 1000 (total measurements = 1002)
- **Maximum `max_points`**: 30,000 (hardware acquisition limit)
- **Minimum `NumbMeasPulses`**: 8 (enforced by C code)
- **Output Array Sizes**: Must be ≥ `NumbMeasPulses + 2`

### Timing Limits

- **Minimum Segment Time**: 20 ns (hardware limit: 2e-8 s)
- **Maximum Segment Time**: 1 s
- **Measurement Window**: 40-90% of `measWidth` (ratio = 0.4)
- **Total Waveform Duration**: 
  ```
  TotalTime ≈ resetDelay + (NumbMeasPulses + 2) × (riseTime + measWidth + setFallTime + riseTime + measDelay)
  ```

### Voltage/Current Limits

- **Voltage Range**: -20 V to +20 V
- **Current Range**: 100 nA to 0.8 A (set via `IRange`)
- **Measurement Voltage (`measV`)**: Typically 0.3-0.5 V (low voltage to avoid programming)

### Sampling Limits

- **Maximum Sample Rate**: 200 MSa/s (hardware limit)
- **Maximum Samples per A/D Test**: 1,000,000 samples (hardware limit)
- **Automatic Rate Adjustment**: Driver adjusts sample rate based on `max_points` and total waveform duration
- **Minimum Samples**: 12 (hardware requirement)

### Memory Limits

- **Waveform Segments**: Maximum ~4000 segments (for NumbMeasPulses = 1000)
- **Raw Data Arrays**: ~240 MB for 1M samples (5 arrays × 1M × 8 bytes)
- **Output Arrays**: ~24 KB for 1002 measurements (3 arrays × 1002 × 8 bytes)

### Total Sample Limits

- **Hardware Limit**: 1,000,000 samples per A/D test (Keithley 4200A-SCS 4225-PMU specification)
- **Practical Limit**: 30,000 samples (default `max_points`) for reasonable data retrieval speed
- **Measurement Duration**: 
  - At 200 MSa/s: Up to 5 ms total waveform duration
  - At 10 MSa/s: Up to 100 ms total waveform duration
  - At 1 MSa/s: Up to 1 s total waveform duration

**Recommendation**: For longer measurement sequences, reduce sample rate or use fewer measurement pulses.

---

## Troubleshooting

### No Data Returned

- **Check array sizes**: Ensure `setV_size`, `setI_size`, and `PulseTimesSize` are ≥ `NumbMeasPulses + 2`
- **Verify GP parameters**: Check that parameters 20, 22, and 31 are being queried correctly
- **Check hardware connection**: Ensure PMU channels 1 and 2 are properly connected

### Incorrect Resistance Values

- **Verify measurement voltage**: Check that `measV` is appropriate for your device (typically 0.3-0.5V)
- **Check current range**: Ensure `IRange` is set correctly (too high = poor resolution, too low = saturation)
- **Verify measurement window**: Measurements are taken at 40-90% of `measWidth` (ensure this is during stable portion)

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

- **`run_readtrain_dual_channel.py`**: Python script for executing measurements
- **`readtrain_dual_channel.c`**: C module implementing waveform generation and data processing
- **`read_train_ilimit.c`**: Low-level driver for PMU hardware control

---

## See Also

- **Retention Module**: For measurements with programming pulses followed by retention reads
- **Potentiation-Depression Module**: For alternating positive/negative programming pulses
- **Pulse-Read Interleaved Module**: For pulse-read-pulse-read patterns

