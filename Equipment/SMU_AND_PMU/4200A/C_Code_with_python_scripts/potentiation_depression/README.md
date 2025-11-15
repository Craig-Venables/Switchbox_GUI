# PMU Potentiation-Depression Measurement Module

> **⚠️ IMPORTANT: Dual-Channel Mode Required**
> 
> This module operates in **dual-channel mode** using PMU channels 1 and 2. Both channels must be connected to your device:
> - **Channel 1 (Force Channel)**: Applies voltage to the device
> - **Channel 2 (Measure Channel)**: Measures current through the device
> 
> Ensure proper connections are made before running measurements.

```
VOLTAGE WAVEFORM - ONE CYCLE PAIR (Potentiation + Depression)
═══════════════════════════════════════════════════════════════════════════════

Voltage (V)
    │
+PulseV ─┐     ┌──┐     ┌──┐     ┌──┐
         │     │  │     │  │     │  │
         │     │  │     │  │     │  │
 measV ──┼──┐  │  │  ┌──│  │  ┌──│  │  ┌─
         │  │  │  │  │  │  │  │  │  │  │  │
    0V ──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴───> Time
         │  
         │
-PulseV ─┘  


LEGEND:
  ────  = Voltage transition (rise/fall time)
  ││││  = Flat top (pulse width or measurement window)
  ┌──┐  = Positive programming pulse (+PulseV) for potentiation
  └──┘  = Negative programming pulse (-PulseV) for depression
  ──┐   = Read measurement pulse (at measV, typically 0.3V)
  ──┘   = Read measurement pulse (at measV, typically 0.3V)

NOTES:
  • Potentiation pulses: Positive voltage (+PulseV) increases device conductance
  • Depression pulses: Negative voltage (-PulseV) decreases device conductance
  • Read measurements: Small voltage (measV) to measure resistance without programming
  • Each cycle: Initial read → N pulses → N reads (where N = NumPulsesPerGroup or NumReads)
```

## Overview

This module implements a **potentiation-depression cycling measurement pattern** for memristor devices using the Keithley 4200A-SCS Programmable Measurement Unit (PMU). The pattern alternates between **potentiation cycles** (positive voltage pulses that increase device conductance) and **depression cycles** (negative voltage pulses that decrease device conductance).

This measurement pattern is essential for studying:
- **Synaptic plasticity** in neuromorphic computing devices
- **Conductance modulation** behavior in resistive switching memories
- **Bipolar switching** characteristics of memristors
- **Potentiation/depression asymmetry** in artificial synapses

---

## Waveform Structure

The measurement consists of **cycle pairs**, where each pair contains one potentiation cycle followed by one depression cycle:

```
For each cycle pair (NumCycles pairs):
  ┌─────────────────────────────────────────────────┐
  │ POTENTIATION CYCLE (Positive Pulses)            │
  ├─────────────────────────────────────────────────┤
  │ 1. Initial Read (baseline before pulses)       │
  │ 2. NumPulsesPerGroup pulses at +PulseV          │
  │    Each pulse: 0V → +PulseV → 0V               │
  │ 3. NumReads read measurements                  │
  │    Each read: 0V → measV → 0V                  │
  │                                                 │
  │ DEPRESSION CYCLE (Negative Pulses)              │
  ├─────────────────────────────────────────────────┤
  │ 1. Initial Read (baseline before pulses)        │
  │ 2. NumPulsesPerGroup pulses at -PulseV         │
  │    Each pulse: 0V → -PulseV → 0V               │
  │ 3. NumReads read measurements                  │
  │    Each read: 0V → measV → 0V                  │
  └─────────────────────────────────────────────────┘
```

### Detailed Segment Structure

#### Potentiation Cycle

1. **Initial Read Measurement**:
   - RISE: 0V → measV (over `riseTime`)
   - TOP: Hold at measV for `measWidth` (measurement window)
   - FALL delay: Optional settling time `setFallTime` at measV
   - FALL: measV → 0V (over `riseTime`)
   - DELAY: Hold at 0V for `measDelay`

2. **Programming Pulses** (repeated `NumPulsesPerGroup` times):
   - RISE: 0V → +PulseV (over `pulseRiseTime`)
   - TOP: Hold at +PulseV for `pulseWidth` (flat top)
   - FALL: +PulseV → 0V (over `pulseFallTime`)
   - DELAY: Hold at 0V for `pulseDelay`

3. **Read Measurements** (repeated `NumReads` times):
   - RISE: 0V → measV (over `riseTime`)
   - TOP: Hold at measV for `measWidth` (measurement window)
   - FALL delay: Optional settling time `setFallTime` at measV
   - FALL: measV → 0V (over `riseTime`)
   - DELAY: Hold at 0V for `measDelay`

#### Depression Cycle

Same structure as potentiation cycle, but:
- Programming pulses use **-PulseV** (negative voltage) instead of +PulseV
- All other parameters remain the same

---

## Measurement Points

The module records measurements at specific points in the waveform:

1. **Initial read before potentiation pulses** (1 per cycle pair)
2. **Reads after potentiation pulses** (`NumReads` per cycle pair)
3. **Initial read before depression pulses** (1 per cycle pair)
4. **Reads after depression pulses** (`NumReads` per cycle pair)

**Total measurements per cycle pair**: `2 + 2 × NumReads = 2 × (1 + NumReads)`

**Total measurements for all cycles**: `2 × NumCycles × (1 + NumReads)`

---

## Key Parameters

### Cycle Control Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `--num-cycles` | Number of cycle pairs (M) | 1-100 | 5 |
| `--num-reads` | Number of reads per cycle (N) | 1-100 | 5 |
| `--num-pulses-per-group` | Number of pulses per cycle (N) | 1-100 | 10 |

### Pulse Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `--pulse-v` | Pulse voltage amplitude (positive for potentiation, automatically negated for depression) | -20 to 20 V | 2.0 V |
| `--pulse-width` | Flat top duration of pulse | 2e-8 to 1 s | 1e-6 s |
| `--pulse-rise-time` | Rise time from 0V to pulse voltage | 2e-8 to 1 s | 1e-7 s |
| `--pulse-fall-time` | Fall time from pulse voltage to 0V | 2e-8 to 1 s | 1e-7 s |
| `--pulse-delay` | Delay at 0V after each pulse | 2e-8 to 1 s | 1e-6 s |

**Note**: Depression cycles automatically use `-PulseV` (negative of the specified pulse voltage).

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

### Basic Potentiation-Depression Cycle

Run 3 cycle pairs with 2 reads per cycle and 2 pulses per cycle:

```bash
python run_pmu_pulse_read_interleaved.py \
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
- 3 potentiation cycles (each with 2 positive pulses + 2 reads)
- 3 depression cycles (each with 2 negative pulses + 2 reads)
- Total: 18 measurements (3×2 initial reads + 3×2×2 post-pulse reads)

### High-Resolution Synaptic Plasticity Study

For detailed synaptic behavior analysis:

```bash
python run_pmu_pulse_read_interleaved.py \
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
python run_pmu_pulse_read_interleaved.py \
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
Measurement Index | Cycle Type | Position
------------------|------------|--------------------------
0                 | Pot        | Initial read
1..NumReads       | Pot        | After pulses (read 1..N)
NumReads+1        | Dep        | Initial read
NumReads+2..2*NumReads+1 | Dep | After pulses (read 1..N)
... (repeated for each cycle pair)
```

---

## Technical Implementation

### Architecture

1. **Python Script** (`run_pmu_pulse_read_interleaved.py`):
   - Builds EX command with all parameters
   - Communicates with instrument via KXCI (Keithley eXternal Control Interface)
   - Retrieves data using GP (Get Parameter) commands
   - Calculates resistance and generates plots

2. **C Module** (`pmu_potentiation_depression.c`):
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
| `NumInitialMeasPulses` | `NumCycles` | Number of cycle pairs |
| `NumPulses` | `NumReads` | Number of reads per cycle |
| `NumbMeasPulses` | `NumPulsesPerGroup` | Number of pulses per cycle |

---

## Important Notes

### Voltage Polarity

- **Potentiation cycles**: Use `+PulseV` (positive voltage)
- **Depression cycles**: Use `-PulseV` (negative voltage, automatically negated)
- The `--pulse-v` parameter should be specified as a **positive value**; the module automatically applies the negative for depression cycles

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
Total measurements = 2 × NumCycles × (1 + NumReads)
```

For example:
- `NumCycles = 5`, `NumReads = 5` → 60 measurements
- `NumCycles = 10`, `NumReads = 10` → 220 measurements

---

## Troubleshooting

### Common Issues

1. **Incorrect voltage/resistance values**:
   - ✅ Fixed: Now uses actual measured voltage for resistance calculation
   - ✅ Fixed: Correct GP parameter numbers (20, 22, 25, 31)

2. **Array size errors**:
   - Ensure `setV_size`, `setI_size`, and `PulseTimesSize` are ≥ total measurements
   - Check that `total_probes` calculation matches expected count

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
python run_pmu_pulse_read_interleaved.py \
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

This section provides a detailed explanation of how the C module (`pmu_potentiation_depression.c`) works and how data flows through the system.

### Overview of the System Architecture

The measurement system consists of three main layers:

```
Python Script (run_pmu_pulse_read_interleaved.py)
    ↓ [EX command via KXCI/GPIB]
C Module (pmu_potentiation_depression.c)
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
EX A_pulse_read_grouped_multi pmu_potentiation_depression(
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

When `pmu_potentiation_depression()` is called:

**a) Parameter Repurposing:**
```c
int NumCycles = NumInitialMeasPulses;        // Number of cycle pairs
int NumReads = NumPulses;                    // Reads per cycle
int NumPulsesPerGroup = NumbMeasPulses;      // Pulses per cycle
```

**b) Validation:**
- Checks all timing parameters are within valid ranges (2e-8 to 1.0 seconds)
- Validates cycle counts (1-100)
- Ensures output arrays are properly sized

**c) Memory Allocation:**
- Calculates required waveform size dynamically based on pattern
- Allocates `times[]` and `volts[]` arrays for waveform segments
- Allocates `measMinTime[]` and `measMaxTime[]` for measurement windows

#### 3. **C Module: Waveform Generation**

The module builds the waveform by creating segments sequentially:

**Segment Structure:**
Each segment requires:
- **START voltage** (`volts[segIdx]`)
- **Time duration** (`times[segIdx]`)
- **END voltage** (`volts[segIdx+1]`)

**Example: Positive Pulse Segment**
```c
// RISE segment
volts[segIdx] = 0.0;              // Start at 0V
times[segIdx] = PulseRiseTime;     // Duration
segIdx++;
volts[segIdx] = PulseV;            // End at +PulseV

// TOP segment (flat top)
times[segIdx] = PulseWidth;        // Hold at PulseV
segIdx++;
volts[segIdx] = PulseV;            // Stay at PulseV

// FALL segment
times[segIdx] = PulseFallTime;
segIdx++;
volts[segIdx] = 0.0;              // Back to 0V

// DELAY segment
times[segIdx] = PulseDelay;
segIdx++;
volts[segIdx] = 0.0;              // Hold at 0V
```

**Measurement Window Recording:**
During read segments, the module records measurement windows:
```c
measMinTime[recordedProbeCount] = ttime + ratio * measWidth;  // 40% into window
measMaxTime[recordedProbeCount] = ttime + measWidth * 0.9;     // 90% into window
recordedProbeCount++;
```

This defines the time window where voltage/current will be extracted from the raw data.

#### 4. **Low-Level Driver: Hardware Control**

The C module calls `retention_pulse_ilimit_dual_channel()` which:

**a) Segment Definition:**
```c
ret_Define_SegmentsILimit(Volts, Times, numpts, MeasureBias);
```
- Converts voltage/time arrays into PMU segment format
- Creates `fstartv[]`, `fstopv[]`, `segtime[]` arrays
- Sets up measurement windows for each segment

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

**b) Resistance Calculation:**
```c
double resistance = fabs(probeVoltage / probeCurrent);
// Uses actual measured voltage, not intended measV
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
else if (strcmp(out1_name, "IM") == 0)
    ret_report_values(IMret, numpts, out1, out1_size);  // Measure current
// ... etc
```

The `ret_report_values()` function downsamples the raw data to fit the output array size.

#### 6. **Data Transfer Back to Python**

**KXCI Parameter System:**
The Keithley 4200A uses a parameter-based system where output arrays are accessible via GP (Get Parameter) commands. Parameters are numbered sequentially starting from 1.

**Parameter Mapping:**
```
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
out1 = controller._query_gp(25, total_probes)    # Get out1 array
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
- **Measurement arrays**: Allocated based on sampling rate and total time
- **Output arrays**: Provided by caller (Python via KXCI), C module writes to them
- All temporary arrays are freed before returning

**Data Flow:**
```
C Module allocates: times[], volts[], measMinTime[], measMaxTime[]
    ↓
Low-level driver allocates: pulseV[], pulseI[], pulseT[], MpulseV[], MpulseI[], MpulseT[]
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
2. **Array size validation**: Ensures output arrays are large enough
3. **Segment validation**: Checks for invalid times (< 2e-8s, NaN, etc.)
4. **Hardware status**: Checks instrument connection and initialization
5. **Data extraction**: Handles missing or invalid measurement windows

**Error Codes:**
- Negative return values indicate errors
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
- Default maximum rate: 200 MHz (divisible down to minimum)

**Data Reduction:**
- Raw data may contain thousands of points
- Output arrays are typically much smaller (e.g., 60 measurements)
- `ret_report_values()` performs linear downsampling/interpolation

### Key Design Decisions

1. **Dual-Channel Architecture**: 
   - Force channel (1) applies voltage
   - Measure channel (2) measures current
   - Allows accurate current measurement without voltage drop

2. **Segment-Based Waveform**:
   - Each transition is an explicit segment
   - Ensures clean square waveforms with flat tops
   - Precise timing control

3. **Time Window Extraction**:
   - Measurements taken during stable portion of read pulse
   - Avoids transients at edges
   - Uses 40%-90% of measurement window

4. **Parameter-Based Output**:
   - KXCI system allows flexible data retrieval
   - Python can query only needed parameters
   - Supports multiple output signals simultaneously

---

## System Limits and Constraints

### Array Size Limits

| Array Type | Minimum | Maximum | Typical |
|------------|---------|---------|---------|
| `setV[]`, `setI[]`, `resetR[]`, `PulseTimes[]` | 1 | 30000 | `2 × NumCycles × (1 + NumReads)` |
| `out1[]`, `out2[]` | 1 | 30000 | 200 (out2 default) |

**Calculation**:
```
Total measurements = 2 × NumCycles × (1 + NumReads)
```

**Examples**:
- `NumCycles = 5`, `NumReads = 5` → 60 measurements
- `NumCycles = 10`, `NumReads = 10` → 220 measurements
- `NumCycles = 100`, `NumReads = 100` → 20,200 measurements (approaching limit)

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
| **NumCycles** | 1 | 100 | Number of cycle pairs |
| **NumReads** | 1 | 100 | Number of reads per cycle |
| **NumPulsesPerGroup** | 1 | 100 | Number of pulses per cycle |

**Maximum total measurements**:
- With maximum parameters: `2 × 100 × (1 + 100) = 20,200 measurements`
- This approaches the 30,000 array size limit

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
- **`pmu_potentiation_depression.c`**: C module implementing waveform generation
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

These fixes ensure accurate voltage and resistance measurements.

