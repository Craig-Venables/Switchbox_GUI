# PMU Readtrain with User Wait Module

> **⚠️ IMPORTANT: This Module is UNUSED**
> 
> This module is marked as **UNUSED** and is provided for reference only. It implements a readtrain pattern with user-controlled wait functionality, allowing the measurement to pause until the user explicitly sends a ready signal. This prevents stray TTL signals during setup.
> 
> **For active development, use the standard Readtrain module instead.**

> **⚠️ IMPORTANT: Dual-Channel Mode Required**
> 
> This module operates in **dual-channel mode** using PMU channels 1 and 2. Both channels must be connected to your device:
> - **Channel 1 (Force Channel)**: Applies voltage to the device
> - **Channel 2 (Measure Channel)**: Measures current through the device
> 
> Ensure proper connections are made before running measurements.

```
VOLTAGE WAVEFORM - READTRAIN WITH USER WAIT PATTERN
═══════════════════════════════════════════════════════════════════════════════

Voltage (V)
    │
measV ─┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐
       │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
   0V ─┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴───> Time
       │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
       │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
       └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘  └──┘
       Read  Read  Read  Read  Read  Read  Read  Read  Read  Read
        #1   #2   #3   #4   #5   #6   #7   #8   #9   #10
       [WAIT GATE] ← User sends ready signal here

LEGEND:
  ────  = Voltage transition (rise/fall time)
  ││││  = Flat top (measurement window at measV)
  ┌──┐  = Measurement pulse (read pulse)
  └──┘  = Measurement pulse (read pulse)
  [WAIT GATE] = Pause point where measurement waits for user signal

NOTES:
  • All pulses are measurement pulses (reads) at measV (typically 0.3-0.5V)
  • Pattern: Initial delay → Read #1 → Read #2 → ... → [WAIT] → Read #3 → ...
  • Wait gate allows user to pause measurement for setup/configuration
  • User must send ready signal to continue measurement
```

## Overview

This module implements a **readtrain measurement pattern with user-controlled wait functionality** for memristor devices using the Keithley 4200A-SCS Programmable Measurement Unit (PMU). The pattern performs a sequence of consecutive measurement pulses (reads) with the ability to pause and wait for a user signal before continuing.

**Key Feature**: The wait gate allows the measurement to pause at a specified point, preventing stray TTL signals during setup or device configuration. The user must explicitly send a ready signal to continue the measurement.

**Status**: This module is **UNUSED** and provided for reference only. For active development, use the standard Readtrain module.

---

## Waveform Structure

The measurement consists of **NumbMeasPulses + 2** total measurement pulses, with an optional wait gate:

1. **Initial Read #1** (baseline measurement)
2. **Initial Read #2** (second baseline measurement)
3. **[WAIT GATE]** - Measurement pauses here, waiting for user ready signal
4. **Measurement Pulses #3 through #(NumbMeasPulses+2)** (sequential reads)

### Detailed Segment Structure

Each measurement pulse follows this pattern:

1. **RISE**: 0V → measV (over `riseTime`)
2. **TOP**: Hold at measV for `measWidth` (measurement window)
3. **FALL**: measV → measV (over `setFallTime`, optional settling)
4. **FALL**: measV → 0V (over `riseTime`)
5. **DELAY**: Hold at 0V for `measDelay`

The measurement window is defined as **40-90%** of the `measWidth` duration (ratio = 0.4), ensuring measurements are taken during the stable flat-top portion of the pulse.

### Wait Gate Functionality

The wait gate is implemented using:
- **`ACraig5_wait_mode.c`**: Configures wait mode behavior
- **`ACraig5_wait_signal.c`**: Handles user ready signal

When the wait gate is active:
1. Measurement pauses at the specified point
2. Hardware waits for user signal (typically TTL or software trigger)
3. User sends ready signal to continue
4. Measurement resumes with remaining pulses

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
| `WaitMode` | int | 0 | 0 to 1 | Enable wait gate (1 = enabled) |

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

### Basic Readtrain with Wait (8 measurement pulses)

```python
python run_pmu_readtrain\ with\ wait.py \
    --gpib-address GPIB0::17::INSTR \
    --numb-meas-pulses 8 \
    --meas-v 0.5 \
    --meas-width 2e-6 \
    --wait-mode 1
```

### Extended Readtrain with Wait (100 measurement pulses)

```python
python run_pmu_readtrain\ with\ wait.py \
    --gpib-address GPIB0::17::INSTR \
    --numb-meas-pulses 100 \
    --meas-v 0.3 \
    --meas-width 2e-6 \
    --meas-delay 1e-6 \
    --max-points 30000 \
    --wait-mode 1
```

### Dry Run (print command without executing)

```python
python run_pmu_readtrain\ with\ wait.py --dry-run --numb-meas-pulses 10 --wait-mode 1
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
- Measurements 3 through (NumbMeasPulses+2): Sequential read pulses (after wait gate)

---

## Technical Implementation

### C Module: `ACraig5_PMU_retention.c`

The C module generates a waveform using `seg_arb_sequence` with the following structure:

1. **Initial Setup**: Allocates arrays for voltage/time segments and measurement windows
2. **Waveform Generation**: Creates segments for each measurement pulse
3. **Wait Gate Integration**: Inserts wait gate after initial measurements (if enabled)
4. **Hardware Execution**: Calls `ACraig5_retention_pulseNK()` (via `ACraig5_retention_pulse_ilimitNK()`) to execute waveform
5. **Data Extraction**: Extracts voltage and current from measurement windows (40-90% of measWidth)
6. **Resistance Calculation**: Computes `R = |V| / |I|` for each measurement point
7. **Output**: Populates output arrays via `GP` parameters

### Wait Gate Modules

- **`ACraig5_wait_mode.c`**: Configures wait mode behavior and gate position
- **`ACraig5_wait_signal.c`**: Handles user ready signal reception and processing

### Low-Level Driver: `ACraig5_retention_pulse_ilimitNK.c`

The low-level driver (`ACraig5_retention_pulse_ilimitNK`) handles:
- PMU channel configuration (ForceCh=1, MeasureCh=2)
- Voltage/current range selection
- Current limit enforcement
- Hardware waveform execution via `seg_arb_sequence`
- Wait gate integration
- Raw data acquisition and storage

---

## C Program Architecture and Data Flow

### Overview of the System Architecture

The measurement system consists of four main layers:

```
Python Script (run_pmu_readtrain with wait.py)
    ↓ [EX command via KXCI/GPIB]
C Module (ACraig5_PMU_retention.c)
    ↓ [Waveform segments + Wait gate]
Wait Gate Modules (ACraig5_wait_mode.c, ACraig5_wait_signal.c)
    ↓ [User signal handling]
Low-Level Driver (ACraig5_retention_pulse_ilimitNK.c)
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
   - Builds `EX` command string with all parameters (including `WaitMode`)
   - Connects to instrument via KXCI/GPIB

2. **Command Transmission**:
   - Enters UL (User Library) mode
   - Sends `EX +24 ACraig5_PMU_retention(...)` command
   - Waits for execution completion

3. **C Module Execution** (`ACraig5_PMU_retention.c`):
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
   - Inserts wait gate after initial measurements (if `WaitMode = 1`)
   - Records measurement window times (40-90% of measWidth)
   - Calls `ACraig5_retention_pulseNK()` to execute waveform

4. **Wait Gate Execution** (if enabled):
   - Measurement pauses at specified point
   - `ACraig5_wait_mode.c` configures wait behavior
   - `ACraig5_wait_signal.c` waits for user ready signal
   - User sends ready signal (TTL or software trigger)
   - Measurement resumes with remaining pulses

5. **Low-Level Driver Execution** (`ACraig5_retention_pulse_ilimitNK.c`):
   - Configures PMU channels (ForceCh=1, MeasureCh=2)
   - Sets voltage/current ranges based on measV and IRange
   - Executes waveform via `seg_arb_sequence` with voltage/time arrays
   - Handles wait gate integration
   - Acquires raw voltage and current data at hardware sample rate
   - Stores data in global arrays: `VFret`, `IFret`, `VMret`, `IMret`, `Tret`

6. **Data Extraction** (back in C module):
   - For each measurement window:
     - Calls `ret_find_value()` to extract voltage from `VMret` array
     - Calls `ret_find_value()` to extract current from `IMret` array
     - Calculates resistance: `R = |V| / |I|`
     - Stores results in output arrays: `setV`, `setI`, `PulseTimes`

7. **Data Transfer to Python**:
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
- **Wait Gate Timeout**: Handles cases where user signal is not received (if timeout configured)
- **Data Extraction**: Handles cases where measurement windows fall outside acquired data

### Key Design Decisions

1. **Measurement Window (40-90%)**: Ensures measurements are taken during stable flat-top portion, avoiding transients
2. **Dual-Channel Mode**: Separates force and measure channels for accurate current measurement
3. **Wait Gate Position**: Placed after initial measurements to allow setup before main measurement sequence
4. **User Signal**: Typically TTL or software trigger, allowing flexible integration with external systems

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
- **Wait Gate Duration**: Unlimited (waits for user signal)
- **Total Waveform Duration**: 
  ```
  TotalTime ≈ resetDelay 
            + (NumbMeasPulses + 2) × (riseTime + measWidth + setFallTime + riseTime + measDelay)
            + WaitGateDuration (if enabled)
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

### Wait Gate Not Working

- **Check WaitMode**: Ensure `WaitMode = 1` is set in command
- **Verify wait signal**: Check that user ready signal is being sent correctly
- **Check wait gate position**: Verify wait gate is placed at correct point in waveform
- **Timeout issues**: If timeout is configured, ensure signal is sent within timeout period

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

- **`run_pmu_readtrain with wait.py`**: Python script for executing measurements with wait gate
- **`run_acraig5_retention_wait.py`**: Alternative Python script for ACraig5 retention with wait
- **`ACraig5_PMU_retention.c`**: C module implementing waveform generation and data processing
- **`ACraig5_retention_pulse_ilimitNK.c`**: Low-level driver for PMU hardware control
- **`ACraig5_wait_mode.c`**: Wait gate mode configuration
- **`ACraig5_wait_signal.c`**: User ready signal handling

---

## See Also

- **Readtrain Module**: Standard readtrain module without wait functionality (recommended for active use)
- **Retention Module**: For measurements with programming pulses followed by retention reads
- **Potentiation-Depression Module**: For alternating positive/negative programming pulses

---

## Status

**This module is UNUSED and provided for reference only.** For active development, use the standard Readtrain module (`Equipment/SMU_AND_PMU/C_Code_with_python_scripts/Readtrain/`).

