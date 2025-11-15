# PMU Pulse-Read Interleaved Measurement Module

> **⚠️ IMPORTANT: Dual-Channel Mode Required**
> 
> This module operates in **dual-channel mode** using PMU channels 1 and 2. Both channels must be connected to your device:
> - **Channel 1 (Force Channel)**: Applies voltage to the device
> - **Channel 2 (Measure Channel)**: Measures current through the device
> 
> Ensure proper connections are made before running measurements.

```
VOLTAGE WAVEFORM - ONE CYCLE (Pulses + Reads)
═══════════════════════════════════════════════════════════════════════════════

Voltage (V)
    │
PulseV ─┐     ┌──┐     ┌──┐     ┌──┐     ┌──┐     ┌──┐     ┌──┐     ┌──┐
        │     │  │     │  │     │  │     │  │     │  │     │  │     │  │
        │     │  │     │  │     │  │     │  │     │  │     │  │     │  │
 measV ─┼──┐  │  │  ┌──│  │  ┌──│  │  ┌──│  │  ┌──│  │  ┌──│  │  ┌──│  │  ┌──
        │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
   0V ──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴───> Time
        │
        │
        │
   INITIAL READ    PULSE 1  PULSE 2  READ 1  READ 2  READ 3  ... (repeated for each cycle)


LEGEND:
  ────  = Voltage transition (rise/fall time)
  ││││  = Flat top (pulse width or measurement window)
  ┌──┐  = Programming pulse (PulseV) for device programming
  ──┐   = Read measurement pulse (at measV, typically 0.3V)
  ──┘   = Read measurement pulse (at measV, typically 0.3V)

NOTES:
  • Initial read: Baseline measurement before any programming pulses
  • Programming pulses: Apply voltage (PulseV) to modify device state
  • Read measurements: Small voltage (measV) to measure resistance without programming
  • Each cycle: N pulses → N reads (where N = NumPulsesPerGroup and NumReads)
```

## Overview

This module implements a **pulse-read interleaved measurement pattern** for memristor devices using the Keithley 4200A-SCS Programmable Measurement Unit (PMU). The pattern consists of an initial baseline read measurement, followed by cycles where multiple programming pulses are applied, then multiple read measurements are performed.

This measurement pattern is essential for studying:
- **Device programming response** to multiple consecutive pulses
- **Resistance evolution** after pulse sequences
- **Cumulative programming effects** in resistive switching memories
- **Read stability** after programming operations

---

## Waveform Structure

The measurement consists of two main sections:

```
1. Initial Read:
   ┌─────────────────────────────────────────────────┐
   │ Single baseline read measurement before cycles   │
   │ READ: 0V → measV → 0V                            │
   └─────────────────────────────────────────────────┘

2. Cycles: ((Pulse)xn, (Read)xn) × NumCycles
   ┌─────────────────────────────────────────────────┐
   │ For each cycle:                                 │
   │ 1. NumPulsesPerGroup pulses at PulseV           │
   │    Each pulse: 0V → PulseV → 0V                 │
   │ 2. NumReads read measurements                   │
   │    Each read: 0V → measV → 0V                  │
   └─────────────────────────────────────────────────┘
```

### Detailed Segment Structure

#### Initial Read Measurement

1. **RISE**: 0V → measV (over `riseTime`)
2. **TOP**: Hold at measV for `measWidth` (measurement window)
3. **FALL delay**: Optional settling time `setFallTime` at measV
4. **FALL**: measV → 0V (over `riseTime`)
5. **DELAY**: Hold at 0V for `measDelay`

#### Programming Pulses (repeated `NumPulsesPerGroup` times per cycle)

1. **RISE**: 0V → PulseV (over `pulseRiseTime`)
2. **TOP**: Hold at PulseV for `pulseWidth` (flat top)
3. **FALL**: PulseV → 0V (over `pulseFallTime`)
4. **DELAY**: Hold at 0V for `pulseDelay`

#### Read Measurements (repeated `NumReads` times per cycle)

1. **RISE**: 0V → measV (over `riseTime`)
2. **TOP**: Hold at measV for `measWidth` (measurement window)
3. **FALL delay**: Optional settling time `setFallTime` at measV
4. **FALL**: measV → 0V (over `riseTime`)
5. **DELAY**: Hold at 0V for `measDelay`

---

## Measurement Points

The module records measurements at specific points in the waveform:

1. **Initial read** before any cycles (1 measurement)
2. **Reads after pulses** in each cycle (`NumReads` per cycle)

**Total measurements**: `1 + NumCycles × NumReads`

For example:
- `NumCycles = 3`, `NumReads = 2` → 1 + 3×2 = 7 measurements
- `NumCycles = 5`, `NumReads = 5` → 1 + 5×5 = 26 measurements

---

## Key Parameters

### Cycle Control Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `--num-cycles` | Number of cycles (M) | 1-100 | 5 |
| `--num-reads` | Number of reads per cycle (N) | 1-100 | 5 |
| `--num-pulses-per-group` | Number of pulses per cycle (N) | 1-100 | 10 |

### Pulse Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `--pulse-v` | Pulse voltage amplitude | -20 to 20 V | 2.0 V |
| `--pulse-width` | Flat top duration of pulse | 2e-8 to 1 s | 1e-6 s |
| `--pulse-rise-time` | Rise time from 0V to pulse voltage | 2e-8 to 1 s | 1e-7 s |
| `--pulse-fall-time` | Fall time from pulse voltage to 0V | 2e-8 to 1 s | 1e-7 s |
| `--pulse-delay` | Delay at 0V after each pulse | 2e-8 to 1 s | 1e-6 s |

### Measurement Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `--meas-v` | Measurement voltage (applied during reads) | -20 to 20 V | 0.3 V |
| `--meas-width` | Measurement pulse width (duration at measV) | 2e-8 to 1 s | 0.1e-6 s |
| `--meas-delay` | Delay at 0V after each read | 2e-8 to 1 s | 2e-6 s |
| `--rise-time` | Rise/fall time for read pulses | 2e-8 to 1 s | 1e-7 s |
| `--set-fall-time` | Optional settling time at measV before fall | 2e-8 to 1 s | 1e-7 s |

### Instrument Configuration

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `--i-range` | Current measurement range | 100e-9 to 0.8 A | 1e-4 A |
| `--max-points` | Maximum data points to collect | 12-30000 | 10000 |
| `--gpib-address` | VISA resource string | - | GPIB0::17::INSTR |
| `--timeout` | VISA timeout in seconds | - | 30.0 s |

---

## Usage Examples

### Basic Pulse-Read Pattern

Run 3 cycles with 2 reads per cycle and 2 pulses per cycle:

```bash
python run_pmu_potentiation_depression.py \
    --gpib-address GPIB0::17::INSTR \
    --num-cycles 3 \
    --num-reads 2 \
    --num-pulses-per-group 2 \
    --pulse-v 4.0 \
    --pulse-width 1e-6 \
    --pulse-rise-time 1e-7 \
    --pulse-fall-time 1e-7 \
    --pulse-delay 1e-6 \
    --meas-v 0.3 \
    --meas-width 2e-6
```

This will generate:
- 1 initial read measurement
- 3 cycles (each with 2 pulses + 2 reads)
- Total: 7 measurements (1 initial + 3×2 reads)

### High-Resolution Programming Study

For detailed programming behavior analysis:

```bash
python run_pmu_potentiation_depression.py \
    --num-cycles 10 \
    --num-reads 5 \
    --num-pulses-per-group 20 \
    --pulse-v 3.5 \
    --pulse-width 500e-9 \
    --pulse-rise-time 50e-9 \
    --pulse-fall-time 50e-9 \
    --pulse-delay 500e-9 \
    --meas-v 0.2 \
    --meas-width 1e-6 \
    --meas-delay 1e-6 \
    --i-range 1e-4
```

### Dry Run (Command Generation Only)

Generate and print the EX command without executing:

```bash
python run_pmu_potentiation_depression.py \
    --dry-run \
    --num-cycles 3 \
    --num-reads 2 \
    --num-pulses-per-group 2
```

---

## Output Data

The script returns several arrays containing measurement data:

### Primary Output Arrays

1. **`set_v`** (Parameter 20): Measured voltage at each measurement point
2. **`set_i`** (Parameter 22): Measured current at each measurement point
3. **`pulse_times`** (Parameter 31): Timestamp for each measurement (seconds)
4. **`out1`** (Parameter 25): Additional output signal (configurable: VF, IF, VM, IM, or T)

### Calculated Values

- **Resistance**: Calculated as `R = |V_measured| / I_measured` for each point
- **Conductance**: Inverse of resistance (if needed)

### Data Organization

The data arrays are organized in the following order:

```
Measurement Index | Position
------------------|--------------------------
0                 | Initial read (before cycles)
1..NumReads        | Cycle 1 reads (after pulses)
NumReads+1..2*NumReads | Cycle 2 reads (after pulses)
... (repeated for each cycle)
```

---

## Technical Implementation

### Architecture

1. **Python Script** (`run_pmu_potentiation_depression.py`):
   - Builds EX command with all parameters
   - Communicates with instrument via KXCI (Keithley eXternal Control Interface)
   - Retrieves data using GP (Get Parameter) commands
   - Calculates resistance and generates plots

2. **C Module** (`pmu_pulse_read_interleaved.c`):
   - Generates waveform segments using `seg_arb_sequence`
   - Executes waveform on PMU channels 1 (force) and 2 (measure)
   - Extracts measurements from time windows
   - Calculates resistance using actual measured voltage

3. **Low-Level Driver** (`retention_pulse_ilimit_dual_channel.c`):
   - Handles PMU hardware control
   - Manages dual-channel measurements
   - Implements current limiting
   - Collects raw voltage/current/time data

### Key Features

- **Dual-Channel Measurement**: Uses PMU channel 1 for forcing and channel 2 for measurement
- **Precise Timing**: All segments use explicit START and END voltage points for clean waveforms
- **Current Limiting**: Configurable current limits for device protection
- **Flexible Output**: Configurable output signals (VF, IF, VM, IM, T)
- **Debug Mode**: Detailed waveform generation logging available

### Parameter Mapping

The module repurposes legacy parameter names for clarity:

| Legacy Parameter | New Meaning | Description |
|-----------------|-------------|-------------|
| `NumInitialMeasPulses` | `NumCycles` | Number of cycles |
| `NumPulses` | `NumReads` | Number of reads per cycle |
| `NumbMeasPulses` | `NumPulsesPerGroup` | Number of pulses per cycle |

---

## Important Notes

### Measurement Timing

- Measurements are taken during the `measWidth` window at `measV`
- The measurement window is centered at `ratio × measWidth` (where `ratio = 0.4`)
- Actual measurement time: `measMinTime` to `measMaxTime` (40% to 90% of measWidth)

### Resistance Calculation

- Resistance is calculated using the **actual measured voltage** (not the intended `measV`)
- Formula: `R = |V_measured| / I_measured`
- Very small currents (< 1e-12 A) result in maximum resistance value
- Resistance is capped at `1e4 / IRange` to prevent overflow

### Array Sizing

Ensure output arrays are sized to accommodate:
```
Total measurements = 1 + NumCycles × NumReads
```

For example:
- `NumCycles = 5`, `NumReads = 5` → 26 measurements
- `NumCycles = 10`, `NumReads = 10` → 101 measurements

---

## Troubleshooting

### Common Issues

1. **Incorrect voltage/resistance values**:
   - ✅ Fixed: Now uses actual measured voltage for resistance calculation
   - ✅ Fixed: Correct GP parameter numbers (20, 22, 25, 31)

2. **Array size errors**:
   - Ensure `setV_size`, `setI_size`, and `PulseTimesSize` are ≥ total measurements
   - Check that `total_probe_count()` calculation matches expected count: `1 + NumCycles × NumReads`

3. **Waveform generation errors**:
   - Verify all timing parameters are within valid ranges (2e-8 to 1 s)
   - Check that `pulseRiseTime` and `pulseFallTime` are sufficient for clean transitions
   - Ensure `pulseWidth` is long enough for device response

4. **Measurement timing issues**:
   - Increase `measWidth` if measurements are unstable
   - Adjust `setFallTime` for better settling before measurement
   - Check that `measDelay` provides sufficient recovery time

### Debug Mode

Enable detailed logging:

```bash
python run_pmu_potentiation_depression.py \
    --clarius-debug 1 \
    --num-cycles 1 \
    ...
```

This will print:
- Waveform segment details
- Measurement window times
- Voltage/current values at each probe
- Resistance calculations

---

## C Program Architecture and Data Flow

This section provides a detailed explanation of how the C module (`pmu_pulse_read_interleaved.c`) works and how data flows through the system.

### Overview of the System Architecture

The measurement system consists of three main layers:

```
Python Script (run_pmu_potentiation_depression.py)
    ↓ [EX command via KXCI/GPIB]
C Module (pmu_pulse_read_interleaved.c)
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

### Step-by-Step Execution Flow

#### 1. **Python Script: Command Generation**

The Python script builds an `EX` command string that calls the C module:

```python
EX A_pulse_read_grouped_multi pmu_pulse_read_interleaved(
    riseTime, resetV, resetWidth, ..., 
    "", setV_size, "", setI_size, ..., 
    "", PulseTimesSize, ...
)
```

**Key Points:**
- Output arrays are passed as empty strings (`""`) - they are allocated by the C module
- Array sizes immediately follow each output array parameter
- Parameters are 1-based when queried later (first parameter = 1)

#### 2. **C Module: Initialization and Validation**

When `pmu_pulse_read_interleaved()` is called:

**a) Parameter Repurposing:**
```c
int NumCycles = NumInitialMeasPulses;        // Number of cycles
int NumReads = NumPulses;                    // Reads per cycle
int NumPulsesPerGroup = NumbMeasPulses;      // Pulses per cycle
```

**b) Validation:**
- Checks all timing parameters are within valid ranges (2e-8 to 1.0 seconds)
- Validates cycle counts (1-100)
- Ensures output arrays are properly sized

**c) Memory Allocation:**
- Calculates required waveform size dynamically based on pattern
- Pattern: Initial Read (5 segments) + Cycles × (NumPulsesPerGroup × 4 + NumReads × 5 segments)
- Allocates `times[]` and `volts[]` arrays for waveform segments
- Allocates `measMinTime[]` and `measMaxTime[]` for measurement windows
- Probe capacity: `1 + NumCycles × NumReads` measurements

#### 3. **C Module: Waveform Generation**

The module builds the waveform by creating segments sequentially:

**Segment Structure:**
Each segment requires:
- **START voltage** (`volts[segIdx]`)
- **Time duration** (`times[segIdx]`)
- **END voltage** (`volts[segIdx+1]`)

**Example: Initial Read Segment**
```c
// RISE segment
volts[segIdx] = 0.0;              // Start at 0V
times[segIdx] = riseTime;         // Duration
segIdx++;
volts[segIdx] = measV;           // End at measV

// TOP segment (measurement window)
times[segIdx] = measWidth;        // Hold at measV
measMinTime[0] = ttime + ratio * measWidth;  // 40% into window
measMaxTime[0] = ttime + measWidth * 0.9;    // 90% into window
recordedProbeCount++;
ttime += times[segIdx];
segIdx++;
volts[segIdx] = measV;            // Stay at measV

// FALL delay segment
times[segIdx] = setFallTime;
ttime += times[segIdx];
segIdx++;
volts[segIdx] = measV;

// FALL segment
times[segIdx] = riseTime;
ttime += times[segIdx];
segIdx++;
volts[segIdx] = 0.0;             // Back to 0V

// DELAY segment
times[segIdx] = measDelay;
ttime += times[segIdx];
segIdx++;
volts[segIdx] = 0.0;             // Hold at 0V
```

**Example: Programming Pulse Segment**
```c
// RISE segment
volts[segIdx] = 0.0;              // Start at 0V
times[segIdx] = PulseRiseTime;    // Duration
segIdx++;
volts[segIdx] = PulseV;           // End at PulseV

// TOP segment (flat top)
times[segIdx] = PulseWidth;       // Hold at PulseV
segIdx++;
volts[segIdx] = PulseV;           // Stay at PulseV

// FALL segment
times[segIdx] = PulseFallTime;
segIdx++;
volts[segIdx] = 0.0;             // Back to 0V

// DELAY segment
times[segIdx] = PulseDelay;
segIdx++;
volts[segIdx] = 0.0;             // Hold at 0V
```

**Measurement Window Recording:**
During read segments (initial and cycle reads), the module records measurement windows:
```c
measMinTime[recordedProbeCount] = ttime + ratio * measWidth;  // 40% into window
measMaxTime[recordedProbeCount] = ttime + measWidth * 0.9;     // 90% into window
recordedProbeCount++;
```

This defines the time window where voltage/current will be extracted from the raw data.

**Waveform Pattern Generation:**
```c
// Initial delay and rise time
times[segIdx] = resetDelay;
ttime += times[segIdx];
segIdx++;
times[segIdx] = riseTime;
ttime += times[segIdx];
segIdx++;

// Initial read measurement (5 segments)
// ... (as shown above)

// Cycles: ((Pulse)xn, (Read)xn) × NumCycles
for (cycleIdx = 0; cycleIdx < NumCycles; cycleIdx++)
{
    // NumPulsesPerGroup pulses in sequence
    for (pulseIdx = 0; pulseIdx < NumPulsesPerGroup; pulseIdx++)
    {
        // RISE → TOP → FALL → DELAY (4 segments per pulse)
    }
    
    // NumReads reads in sequence
    for (readIdx = 0; readIdx < NumReads; readIdx++)
    {
        // RISE → TOP (with measurement window) → FALL delay → FALL → DELAY (5 segments per read)
        // Records measurement window during TOP segment
    }
}
```

#### 4. **Low-Level Driver: Hardware Control**

The C module calls `retention_pulse_ilimit_dual_channel()` which:

**a) Segment Definition:**
```c
ret_Define_SegmentsILimit(Volts, Times, numpts, MeasureBias);
```
- Converts voltage/time arrays into PMU segment format
- Creates `fstartv[]`, `fstopv[]`, `segtime[]` arrays
- Sets up measurement windows for each segment
- Validates segment times (minimum 2e-8 seconds, no NaN, no zero/negative)

**b) Hardware Initialization:**
```c
pg2_init(InstId, PULSE_MODE_SARB);           // Initialize PMU
pulse_load(InstId, ForceCh, 1e+6);           // Set load impedance
pulse_ranges(InstId, ForceCh, ...);          // Set voltage/current ranges
pulse_burst_count(InstId, ForceCh, 1);       // Single burst
pulse_output(InstId, ForceCh, 1);            // Enable output
```

**c) Waveform Loading:**
```c
seg_arb_sequence(InstId, ForceCh, 1, numpts, 
                 fstartv, fstopv, segtime, ...);  // Load segments to ForceCh
seg_arb_sequence(InstId, MeasureCh, 1, numpts, 
                 mstartv, mstopv, segtime, ...);  // Load segments to MeasureCh
seg_arb_waveform(InstId, ForceCh, 1, ...);       // Configure waveform execution
```

**d) Execution:**
```c
pulse_exec(0);                                 // Start waveform execution
while(pulse_exec_status(&t) == 1) { ... }     // Wait for completion
```

**e) Data Acquisition:**
```c
pulse_fetch(InstId, ForceCh, 0, NumDataPts, 
            pulseV, pulseI, pulseT, NULL);     // Fetch ForceCh data
pulse_fetch(InstId, MeasureCh, 0, NumDataPts, 
            MpulseV, MpulseI, MpulseT, NULL);  // Fetch MeasureCh data
```

This returns raw arrays:
- `pulseV[]`, `pulseI[]`, `pulseT[]`: Force channel (channel 1) data
- `MpulseV[]`, `MpulseI[]`, `MpulseT[]`: Measure channel (channel 2) data

#### 5. **C Module: Data Extraction and Processing**

After the low-level driver returns, the C module processes the raw data:

**a) Time Window Extraction:**
For each measurement point, the module extracts voltage and current from the raw data:

```c
// Extract current from measurement window
ret_find_value(IMret, Tret, numpts, 
               measMinTime[ProbeResNumb], 
               measMaxTime[ProbeResNumb], 
               &probeCurrent);
// Returns average current in the time window

// Extract voltage from measurement window
ret_find_value(VMret, Tret, numpts, 
               measMinTime[ProbeResNumb], 
               measMaxTime[ProbeResNumb], 
               &probeVoltage);
// Returns average voltage in the time window
```

The `ret_find_value()` function:
- Searches through the time array (`Tret`) to find points within the window
- Averages all values in the `vals` array that fall within `[start, stop]` time range
- Returns the average value via the `result` pointer

**b) Resistance Calculation:**
```c
// Get voltage FIRST (needed for resistance calculation)
double probeVoltage = 0.0;
stat = ret_find_value(VMret, Tret, numpts, 
                     measMinTime[ProbeResNumb], 
                     measMaxTime[ProbeResNumb], 
                     &probeVoltage);
setV[ProbeResNumb] = probeVoltage;  // Store measured voltage

// Calculate resistance: R = V / I (use actual measured voltage, not measV)
if (fabs(probeCurrent) > 1e-12)  // Avoid division by zero
{
    double resistance = fabs(probeVoltage / probeCurrent);
    if(resistance > 1e4/IRange) 
        resistance = 1e4/IRange;  // Cap at maximum
    resetR[ProbeResNumb] = resistance;  // Store resistance
}
else
{
    resetR[ProbeResNumb] = 1e4/IRange;  // Very high resistance
}
```

**c) Data Storage:**
```c
setV[ProbeResNumb] = probeVoltage;           // Store measured voltage
setI[ProbeResNumb] = probeCurrent;           // Store measured current
resetR[ProbeResNumb] = resistance;           // Store calculated resistance
PulseTimes[ProbeResNumb] = (measMaxTime[ProbeResNumb] + 
                            measMinTime[ProbeResNumb]) / 2;  // Store timestamp
```

**d) Output Array Population:**
The module also populates `out1[]` and `out2[]` arrays based on requested signals:
```c
if (strcmp(out1_name, "VF") == 0)
    ret_report_values(VFret, numpts, out1, out1_size);  // Force voltage
else if (strcmp(out1_name, "IF") == 0)
    ret_report_values(IFret, numpts, out1, out1_size);  // Force current
else if (strcmp(out1_name, "VM") == 0)
    ret_report_values(VMret, numpts, out1, out1_size);  // Measure voltage
else if (strcmp(out1_name, "IM") == 0)
    ret_report_values(IMret, numpts, out1, out1_size);  // Measure current
else
    ret_report_values(Tret, numpts, out1, out1_size);    // Time array
```

The `ret_report_values()` function downsamples the raw data to fit the output array size using linear interpolation:
```c
ratio = ((double)numpts - 1.0) / ((double)out_size - 1.0);
for(i = 0; i < out_size; i++)
{
    j = (int)(ratio * i);  // Map output index to input index
    out[i] = T[j];         // Copy value
}
```

#### 6. **Data Transfer Back to Python**

**KXCI Parameter System:**
The Keithley 4200A uses a parameter-based system where output arrays are accessible via GP (Get Parameter) commands. Parameters are numbered sequentially starting from 1.

**Parameter Mapping:**
```
Parameter 18 = Return value (status code)
Parameter 20 = setV[] (measured voltages)
Parameter 22 = setI[] (measured currents)
Parameter 25 = out1[] (configurable output signal)
Parameter 31 = PulseTimes[] (measurement timestamps)
```

**Python Retrieval:**
```python
# Enter UL (User Library) mode
controller._enter_ul_mode()

# Execute EX command (runs C module)
controller._execute_ex_command(command)

# Query output arrays using GP commands
set_v = controller._query_gp(20, total_probes)    # Get setV array
set_i = controller._query_gp(22, total_probes)    # Get setI array
out1 = controller._query_gp(25, total_probes)     # Get out1 array
pulse_times = controller._query_gp(31, total_probes)  # Get PulseTimes array
```

**GP Command Format:**
```
GP <parameter_number> <count>
```

The instrument returns comma-separated values:
```
1.234,5.678,9.012,...
```

**Python Parsing:**
The `_parse_gp_response()` function:
1. Strips whitespace and "PARAM VALUE=" prefixes
2. Splits on commas or semicolons
3. Converts each value to float
4. Returns as a list

### Memory Management

**C Module Memory:**
- **Waveform arrays**: Allocated dynamically based on calculated size
  - `times[]`: Segment time durations
  - `volts[]`: Segment voltage points (one more than times for end point)
- **Measurement arrays**: Allocated based on sampling rate and total time
  - `VFret[]`, `IFret[]`, `VMret[]`, `IMret[]`, `Tret[]`: Raw measurement data
- **Measurement windows**: Allocated based on probe count
  - `measMinTime[]`, `measMaxTime[]`: Time windows for each measurement
- **Output arrays**: Provided by caller (Python via KXCI), C module writes to them
  - `setV[]`, `setI[]`, `resetR[]`, `PulseTimes[]`, `out1[]`, `out2[]`
- All temporary arrays are freed before returning

**Data Flow:**
```
C Module allocates: times[], volts[], measMinTime[], measMaxTime[]
    ↓
Low-level driver allocates: 
    - Segment arrays: fstartv[], fstopv[], segtime[], mstartv[], mstopv[]
    - Measurement arrays: pulseV[], pulseI[], pulseT[], MpulseV[], MpulseI[], MpulseT[]
    ↓
C Module allocates measurement buffers: VFret[], IFret[], VMret[], IMret[], Tret[]
    ↓
Low-level driver fills: pulseV[], pulseI[], pulseT[], MpulseV[], MpulseI[], MpulseT[]
    ↓
C Module copies to: VFret[], IFret[], VMret[], IMret[], Tret[]
    ↓
C Module extracts data → writes to: setV[], setI[], resetR[], PulseTimes[], out1[], out2[]
    ↓
Python queries via GP commands → receives comma-separated values
    ↓
Python parses and stores in lists/arrays
```

### Error Handling

**Validation Points:**
1. **Parameter validation**: Before waveform generation
   - Timing parameters: 2e-8 to 1.0 seconds
   - Cycle counts: 1-100
   - Voltage ranges: -20 to 20 V
2. **Array size validation**: Ensures output arrays are large enough
   - Checks `PulseTimesSize`, `setV_size`, `setI_size` ≥ `1 + NumCycles × NumReads`
3. **Segment validation**: Checks for invalid times (< 2e-8s, NaN, zero/negative)
   - Performed in `retention_pulse_ilimit_dual_channel()` before `seg_arb_sequence()`
4. **Hardware status**: Checks instrument connection and initialization
   - `LPTIsInCurrentConfiguration()`: Verifies instrument is available
   - `getinstid()`: Gets instrument ID
   - `pg2_init()`: Initializes PMU
5. **Data extraction**: Handles missing or invalid measurement windows
   - `ret_find_value()` returns error if no points found in window
   - Division by zero protection in resistance calculation

**Error Codes:**
- Negative return values indicate errors
- Common error codes:
  - `-202`: Output buffers are NULL
  - `-203`: Unable to allocate measurement window buffers
  - `-204`: Output buffer sizes too small
  - `-205`: Probe capacity exceeded
  - `-207`: Unable to allocate measurement buffers
  - `-210`: Unable to allocate segment buffers
  - `-211`: Computed waveform size exceeds allocated capacity
  - `-213`: Invalid cycle/read/pulse counts
  - `-214` to `-217`: Invalid timing parameters
  - `-90`, `-92`, `-93`: Data extraction errors
- Python script checks return value and reports errors
- Debug mode provides detailed error messages

### Performance Considerations

**Sampling Rate Calculation:**
The `ret_getRate()` function calculates optimal sampling rate:
```c
used_rate = ret_getRate(ttime, max_points, &allocate_pts, &NumDataPts);
```
- Balances total time vs. maximum points constraint
- Ensures sufficient resolution for measurement windows
- Default maximum rate: 200 MHz (divisible down to minimum 200 kHz)
- Algorithm:
  1. Start with maximum rate (200 MHz)
  2. Divide rate by increasing factors until `ttime × rate < max_points`
  3. Allocate `ttime × rate + 2` points (safety margin)
  4. Return actual number of points collected

**Data Reduction:**
- Raw data may contain thousands of points (e.g., 10,000 points)
- Output arrays are typically much smaller (e.g., 26 measurements)
- `ret_report_values()` performs linear downsampling/interpolation
- Measurement extraction uses time window averaging (not downsampling)

### Key Design Decisions

1. **Dual-Channel Architecture**: 
   - Force channel (1) applies voltage
   - Measure channel (2) measures current
   - Allows accurate current measurement without voltage drop
   - Enables Kelvin sensing for precise measurements

2. **Segment-Based Waveform**:
   - Each transition is an explicit segment
   - Ensures clean square waveforms with flat tops
   - Precise timing control
   - Segments defined by START voltage, END voltage, and duration

3. **Time Window Extraction**:
   - Measurements taken during stable portion of read pulse
   - Avoids transients at edges (40%-90% of measurement window)
   - Uses averaging over time window for noise reduction
   - Window recorded during waveform generation, extracted during processing

4. **Parameter-Based Output**:
   - KXCI system allows flexible data retrieval
   - Python can query only needed parameters
   - Supports multiple output signals simultaneously
   - Reduces data transfer overhead

5. **Dynamic Memory Allocation**:
   - Waveform size calculated based on pattern parameters
   - Safety margin added to prevent buffer overflows
   - All arrays freed before returning
   - Prevents memory leaks

---

## System Limits and Constraints

### Array Size Limits

| Array Type | Minimum | Maximum | Typical |
|------------|---------|---------|---------|
| `setV[]`, `setI[]`, `resetR[]`, `PulseTimes[]` | 1 | 30000 | `1 + NumCycles × NumReads` |
| `out1[]`, `out2[]` | 1 | 30000 | 200 (out2 default) |

**Calculation**:
```
Total measurements = 1 + NumCycles × NumReads
```

**Examples**:
- `NumCycles = 5`, `NumReads = 5` → 26 measurements
- `NumCycles = 10`, `NumReads = 10` → 101 measurements
- `NumCycles = 100`, `NumReads = 100` → 10,001 measurements
- `NumCycles = 100`, `NumReads = 200` → 20,001 measurements (approaching limit)

### Timing Constraints

| Parameter | Minimum | Maximum | Description |
|-----------|---------|---------|-------------|
| **Segment time** | 2e-8 s (20ns) | 1.0 s | Minimum time for any segment |
| **Pulse width** | 2e-8 s | 1.0 s | Programming pulse duration |
| **Pulse rise/fall time** | 2e-8 s | 1.0 s | Transition times |
| **Measurement width** | 2e-8 s | 1.0 s | Read pulse duration |
| **All delays** | 2e-8 s | 1.0 s | Delay between segments |

**Note**: All timing parameters must be ≥ 20ns to meet PMU hardware requirements.

### Cycle and Count Limits

| Parameter | Minimum | Maximum | Description |
|-----------|---------|---------|-------------|
| **NumCycles** | 1 | 100 | Number of cycles |
| **NumReads** | 1 | 100 | Number of reads per cycle |
| **NumPulsesPerGroup** | 1 | 100 | Number of pulses per cycle |

**Maximum total measurements**:
- With maximum parameters: `1 + 100 × 100 = 10,001 measurements`
- Well within the 30,000 array size limit

### Voltage and Current Limits

| Parameter | Minimum | Maximum | Description |
|-----------|---------|---------|-------------|
| **Pulse voltage** | -20 V | 20 V | Programming pulse amplitude |
| **Measurement voltage** | -20 V | 20 V | Read pulse voltage |
| **Current range** | 100e-9 A | 0.8 A | Measurement current range |
| **Voltage range** | 5 V | 40 V | PMU voltage range setting |

### Sampling and Data Points

| Parameter | Minimum | Maximum | Default |
|-----------|---------|---------|---------|
| **max_points** | 12 | 30000 | 10000 |
| **Sample rate** | Calculated | 200 MHz | Auto-calculated |

**Sampling Rate Calculation**:
- System automatically calculates optimal rate based on total waveform time
- Maximum rate: 200 MHz (divisible down to minimum)
- Ensures sufficient resolution for measurement windows (40%-90% of measWidth)

### Memory Considerations

**Waveform Arrays**:
- Allocated dynamically based on calculated waveform size
- Size depends on: `NumCycles`, `NumReads`, `NumPulsesPerGroup`, and timing parameters
- Pattern: Initial Read (5 segments) + Cycles × (NumPulsesPerGroup × 4 + NumReads × 5 segments)
- Safety margin added (10% or minimum 10 segments)

**Measurement Arrays**:
- Allocated based on sampling rate and total time
- Typical size: 10,000 points (can be up to 30,000)
- Memory freed after data extraction

**Output Arrays**:
- Provided by Python via KXCI
- Must be sized to accommodate total measurements
- C module writes directly to these arrays

### Performance Limits

**Total Waveform Time**:
- No explicit maximum, but limited by:
  - Array sizes (30,000 measurements max)
  - Memory availability
  - Instrument timeout settings

**Measurement Extraction**:
- Time window extraction uses averaging (not downsampling)
- Window: 40%-90% of measWidth (stable region)
- Avoids transients at pulse edges

---

## Files

- **`run_pmu_potentiation_depression.py`**: Python script for measurement execution
- **`pmu_pulse_read_interleaved.c`**: C module implementing waveform generation
- **`retention_pulse_ilimit_dual_channel.c`**: Low-level PMU control functions
- **`README.md`**: This documentation file

---

## References

- Keithley 4200A-SCS User Manual
- KXCI (Keithley eXternal Control Interface) Documentation
- PMU Programming Guide

---

## Recent Fixes (2025)

1. **Fixed GP parameter numbers**: 
   - `out1` now correctly queried from parameter 25 (was 31)
   - `PulseTimes` now correctly queried from parameter 31 (was 30)

2. **Fixed resistance calculation**:
   - Now uses actual measured voltage (`probeVoltage`) instead of intended voltage (`measV`)
   - Voltage is retrieved before resistance calculation to ensure correct values
   - Reordered code to get voltage first, then calculate resistance

These fixes ensure accurate voltage and resistance measurements.

