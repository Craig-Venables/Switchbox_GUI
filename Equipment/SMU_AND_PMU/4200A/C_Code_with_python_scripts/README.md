# Keithley 4200A-SCS PMU Measurement Modules

> **⚠️ IMPORTANT: Dual-Channel Mode Required**
> 
> Most modules in this folder operate in **dual-channel mode** using PMU channels 1 and 2. Both channels must be connected to your device:
> - **Channel 1 (Force Channel)**: Applies voltage to the device
> - **Channel 2 (Measure Channel)**: Measures current through the device
> 
> Ensure proper connections are made before running measurements.

## Overview

This folder contains a collection of **Python scripts and C modules** for performing advanced memristor and resistive memory device characterization using the Keithley 4200A-SCS Programmable Measurement Unit (PMU). The modules implement various measurement patterns essential for studying device behavior, including:

- **Resistance stability** and temporal drift
- **Programming response** to voltage pulses
- **Retention degradation** over time
- **Potentiation-depression** cycling (synaptic plasticity)
- **Laser-assisted switching** and photoconductivity
- **Read disturb** effects

All modules follow a consistent architecture: **Python scripts** build commands, **C modules** generate waveforms and process data, and **low-level drivers** interface with the PMU hardware.

---

## System Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PYTHON SCRIPT LAYER                          │
│  (run_*.py files)                                               │
│  • Parse command-line arguments                                  │
│  • Build EX command string                                       │
│  • Connect to instrument via KXCI/GPIB                           │
│  • Send EX command to execute C module                           │
│  • Query GP parameters to retrieve data                          │
│  • Process and display results                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ [EX command via KXCI/GPIB]
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                    C MODULE LAYER                               │
│  (*_dual_channel.c files)                                       │
│  • Validate input parameters                                     │
│  • Allocate memory for waveform segments                        │
│  • Generate voltage/time arrays for seg_arb_sequence            │
│  • Record measurement window times                               │
│  • Call low-level driver to execute waveform                    │
│  • Extract voltage/current from measurement windows             │
│  • Calculate resistance (R = V/I)                               │
│  • Populate output arrays (setV, setI, PulseTimes)              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ [Waveform segments]
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│              LOW-LEVEL DRIVER LAYER                             │
│  (*_ilimit*.c files)                                            │
│  • Configure PMU channels (ForceCh, MeasureCh)                   │
│  • Set voltage/current ranges                                    │
│  • Enforce current limits                                        │
│  • Execute waveform via seg_arb_sequence                        │
│  • Acquire raw voltage/current data at hardware sample rate     │
│  • Store data in global arrays (VFret, IFret, VMret, IMret, Tret)│
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ [Hardware commands]
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│              KEITHLEY 4200A-SCS PMU HARDWARE                    │
│  • Generate voltage waveforms                                    │
│  • Measure voltage and current                                   │
│  • Return raw measurement data                                   │
└─────────────────────────────────────────────────────────────────┘
                       │
                       │ [Raw measurements]
                       ↓
              [Data flows back up through layers]
```

### Communication Protocol: KXCI (Keithley eXternal Control Interface)

All communication between Python and the C modules uses **KXCI** over **GPIB**:

1. **EX Command**: Execute C module
   ```
   EX A_Read_Train module_name(param1, param2, ..., paramN)
   ```
   - Sends parameters to C module
   - Executes waveform generation and measurement
   - Returns error code (0 = success, negative = error)

2. **GP Command**: Get Parameter (retrieve output data)
   ```
   GP parameter_number array_size
   ```
   - Queries output arrays from C module
   - Returns array of values (voltage, current, timestamps, etc.)
   - Parameter numbers are fixed for each output (e.g., 20 = setV, 22 = setI)

3. **UL/DE Commands**: User Library mode
   ```
   UL  (enter User Library mode)
   DE  (exit User Library mode)
   ```
   - Required before executing EX commands
   - Must exit before querying GP parameters

---

## Module Descriptions

### 1. Readtrain Module
**Location**: `Readtrain/`  
**Python Script**: `run_readtrain_dual_channel.py`  
**C Module**: `readtrain_dual_channel.c`  
**Low-Level Driver**: `read_train_ilimit.c`

**Purpose**: Performs a sequence of consecutive measurement pulses (reads) to monitor device resistance over time without applying programming pulses.

**Waveform Pattern**: 
- Initial delay → Read #1 → Read #2 → Read #3 → ... → Read #N
- All pulses are measurement pulses at `measV` (typically 0.3-0.5V)
- Total measurements: `NumbMeasPulses + 2`

**Use Cases**:
- Resistance stability over time
- Read disturb effects
- Baseline resistance monitoring
- Temporal drift studies

**Output Data**:
- `setV` (GP parameter 20): Measured voltages
- `setI` (GP parameter 22): Measured currents
- `PulseTimes` (GP parameter 31): Timestamps

---

### 2. Retention Module
**Location**: `retention/`  
**Python Script**: `run_pmu_retention.py`  
**C Module**: `pmu_retention_dual_channel.c`  
**Low-Level Driver**: `retention_pulse_ilimit_dual_channel.c`

**Purpose**: Performs initial baseline measurements, applies programming pulses to set device state, and then monitors resistance changes over time (retention degradation).

**Waveform Pattern**:
1. **Initial Measurements** (`NumInitialMeasPulses`): Baseline reads before programming
2. **Programming Pulses** (`NumPulses`): High voltage pulses to program device state
3. **Retention Measurements** (`NumbMeasPulses`): Periodic reads after programming

**Use Cases**:
- Data retention in resistive memory
- Resistance drift over time after programming
- State stability of programmed devices
- Retention failure mechanisms

**Output Data**:
- `setV` (GP parameter 20): Measured voltages
- `setI` (GP parameter 22): Measured currents
- `PulseTimes` (GP parameter 30): Timestamps
- `out1` (GP parameter 31): Debug output (force voltage)

---

### 3. Potentiation-Depression Module
**Location**: `potentiation_depression/`  
**Python Script**: `pmu_potentiation_depression.py`  
**C Module**: `pmu_potentiation_depression.c`  
**Low-Level Driver**: `retention_pulse_ilimit_dual_channel.c`

**Purpose**: Alternates between potentiation cycles (positive voltage pulses that increase conductance) and depression cycles (negative voltage pulses that decrease conductance).

**Waveform Pattern**:
- **Potentiation Cycle**: Initial read → N pulses at +PulseV → N reads
- **Depression Cycle**: Initial read → N pulses at -PulseV → N reads
- Repeats for `NumCycles` cycle pairs

**Use Cases**:
- Synaptic plasticity in neuromorphic computing
- Conductance modulation behavior
- Bipolar switching characteristics
- Potentiation/depression asymmetry

**Output Data**:
- `setV` (GP parameter 20): Measured voltages
- `setI` (GP parameter 22): Measured currents
- `out1` (GP parameter 25): Configurable output signal
- `PulseTimes` (GP parameter 31): Timestamps

---

### 4. Pulse-Read Interleaved Module
**Location**: `pmu_pulse_read_interleaved/`  
**Python Script**: `run_pmu_potentiation_depression.py`  
**C Module**: `pmu_pulse_read_interleaved.c`  
**Low-Level Driver**: `retention_pulse_ilimit_dual_channel.c`

**Purpose**: Performs an initial baseline read, followed by cycles where multiple programming pulses are applied, then multiple read measurements are performed.

**Waveform Pattern**:
1. **Initial Read**: Single baseline measurement
2. **Cycles**: ((Pulse)xn, (Read)xn) × NumCycles
   - Each cycle: N pulses at PulseV → N reads at measV

**Use Cases**:
- Device programming response to multiple consecutive pulses
- Resistance evolution after pulse sequences
- Cumulative programming effects
- Read stability after programming

**Output Data**:
- `setV` (GP parameter 20): Measured voltages
- `setI` (GP parameter 22): Measured currents
- `out1` (GP parameter 25): Configurable output signal
- `PulseTimes` (GP parameter 31): Timestamps

---

### 5. Read with Laser Pulse Module
**Location**: `Read_with_laser_pulse/`  
**Python Script**: `Read_With_Laser_Pulse_SegArb_Python.py`  
**C Module**: `Pull from 4200 this is wrong.c`

**Purpose**: Combines continuous measurement pulses on CH1 with independent laser pulse generation on CH2, allowing synchronized optical-electrical characterization.

**Waveform Pattern**:
- **CH1 (Measurement)**: Continuous measurement pulses (auto-built from parameters)
- **CH2 (Laser)**: Independent laser pulse waveform (can be auto-built or manually defined)
- **Key Feature**: CH2 period is completely independent of CH1 period

**Use Cases**:
- Photo-induced effects in optoelectronic devices
- Laser-assisted switching in memristors
- Time-resolved photoconductivity measurements
- Synchronized optical-electrical characterization

**Output Data**:
- `setV` (GP parameter 20): Measured voltages
- `setI` (GP parameter 22): Measured currents
- `PulseTimes` (GP parameter 31): Timestamps
- Measurement window: 40-80% of pulse width (stable region)

---

### 6. Read with Binary Waveform Module
**Location**: `Read_With_Binary_waveform/`  
**Python Script**: `Read_With_Binary_waveform.py`  
**C Module**: `ACraig11_PMU_Waveform_Binary.c`

**Purpose**: Generates binary (on/off) waveforms for device characterization.

**Waveform Pattern**: Binary voltage levels (high/low) with configurable timing.

**Use Cases**:
- Binary switching characterization
- Digital waveform generation
- On/off state measurements

---

### 7. Readtrain with User Wait Module (UNUSED)
**Location**: `Readtrain_with_user_wait (UNUSED)/`  
**Python Script**: `run_pmu_readtrain with wait.py`  
**C Module**: `ACraig5_PMU_retention.c`  
**Low-Level Driver**: `ACraig5_retention_pulse_ilimitNK.c`  
**Wait Modules**: `ACraig5_wait_mode.c`, `ACraig5_wait_signal.c`

**Purpose**: Implements readtrain pattern with user-controlled wait functionality, allowing measurement to pause until user sends ready signal.

**Waveform Pattern**: Same as Readtrain, but with wait gate after initial measurements.

**Status**: **UNUSED** - Provided for reference only. Use standard Readtrain module for active development.

---

### 8. Ignore---pulsetrain+laser(no seg arb) Module
**Location**: `Ignore---pulsetrain+laser(no seg arb)/`  
**Python Script**: `ACraig8_single_channel_wave_aux.py`  
**C Module**: `ACraig8_single_channel_wave_aux.c`

**Purpose**: Legacy module for pulsetrain with laser (not using seg_arb). Marked for ignore.

**Status**: **IGNORED** - Legacy code, not actively maintained.

---

## How Data is Retrieved

### Step-by-Step Data Flow

1. **Python Script Builds Command**:
   ```python
   command = f"EX A_Read_Train module_name({param1}, {param2}, ..., {paramN})"
   ```

2. **Python Sends EX Command**:
   ```python
   controller._enter_ul_mode()  # Enter User Library mode
   controller._execute_ex_command(command)  # Execute C module
   ```

3. **C Module Executes**:
   - Generates waveform segments
   - Calls low-level driver to execute waveform
   - Extracts voltage/current from measurement windows
   - Calculates resistance
   - Populates output arrays in memory

4. **Python Queries GP Parameters**:
   ```python
   set_v = controller._query_gp(20, array_size)  # Get setV array
   set_i = controller._query_gp(22, array_size)  # Get setI array
   pulse_times = controller._query_gp(31, array_size)  # Get PulseTimes array
   ```

5. **KXCI Transfers Data**:
   - KXCI reads data from C module memory
   - Transfers array values over GPIB
   - Returns data to Python as list of floats

6. **Python Processes Data**:
   ```python
   resistance = [v / i for v, i in zip(set_v, set_i)]  # Calculate resistance
   # Display, plot, or save results
   ```

### Parameter Number Mapping

Each output parameter has a fixed parameter number:

| Parameter | GP # | Description |
|-----------|------|-------------|
| `setV` | 20 | Measured voltages at each measurement point |
| `setI` | 22 | Measured currents at each measurement point |
| `PulseTimes` | 30 or 31 | Timestamps for each measurement point (varies by module) |
| `out1` | 25 or 31 | Debug/configurable output (varies by module) |
| `out2` | 28 | Debug output: Time array (T) |
| `setR` | 16 | Calculated resistances (legacy, use setV/setI) |
| `resetR` | 18 | Legacy output (not used in most modules) |

**Note**: Parameter numbers may vary slightly between modules. Check individual module READMEs for exact mappings.

---

## High-Level C Code Architecture

### Common Structure Across All Modules

All C modules follow a similar architecture:

#### 1. **Module Header** (USRLIB MODULE INFORMATION)
```c
/* USRLIB MODULE INFORMATION
   MODULE NAME: module_name
   MODULE RETURN TYPE: int
   NUMBER OF PARMS: N
   ARGUMENTS:
      param1, type, Input/Output, default, min, max
      ...
*/
```
- Defines module interface
- Lists all input/output parameters
- Specifies parameter types, defaults, and ranges

#### 2. **Global Data Arrays**
```c
double *VFret = NULL;  // Force channel voltage
double *IFret = NULL;  // Force channel current
double *VMret = NULL;  // Measure channel voltage
double *IMret = NULL;  // Measure channel current
double *Tret = NULL;   // Time array
```
- Allocated in low-level driver
- Store raw measurement data from hardware
- Shared between low-level driver and C module

#### 3. **Main Module Function**
```c
int module_name(param1, param2, ..., paramN)
{
    // 1. Parameter validation
    // 2. Memory allocation for waveform segments
    // 3. Waveform generation (voltage/time arrays)
    // 4. Measurement window recording
    // 5. Call low-level driver
    // 6. Data extraction from measurement windows
    // 7. Resistance calculation
    // 8. Populate output arrays
    // 9. Return error code
}
```

#### 4. **Waveform Generation**

All modules use `seg_arb_sequence` to generate waveforms:

```c
// Build voltage and time arrays
double *volts = (double *)calloc(volts_count, sizeof(double));
double *times = (double *)calloc(times_count, sizeof(double));

// Define segments: seg_arb creates segment i from v[i] to v[i+1] over t[i]
volts[0] = 0.0;      // START voltage
times[0] = delay;    // Duration
volts[1] = measV;    // END voltage (becomes START for next segment)
times[1] = measWidth; // Duration
volts[2] = measV;    // END voltage (flat top)
// ... continue for all segments

// Execute waveform
low_level_driver(inst, ForceCh, MeasureCh, volts, times, ...);
```

**Key Concept**: `seg_arb_sequence` creates segments from `v[i]` (START) to `v[i+1]` (END) over `t[i]` (duration). To create a flat top, set `v[i] = v[i+1] = PulseV` and `t[i] = PulseWidth`.

#### 5. **Measurement Window Extraction**

All modules extract measurements from specific time windows:

```c
// Record measurement window (40-90% of pulse width)
double ratio = 0.4;  // Measurement window start (40%)
measMinTime[i] = ttime + ratio * measWidth;
measMaxTime[i] = ttime + measWidth * 0.9;  // 90% of pulse width

// Later, extract voltage/current from window
double probeVoltage = 0.0;
ret_find_value(VMret, Tret, numpts, measMinTime[i], measMaxTime[i], &probeVoltage);
```

**Why 40-90%?**: Ensures measurements are taken during stable flat-top portion, avoiding transients at pulse edges.

#### 6. **Low-Level Driver Interface**

All modules call low-level drivers with this pattern:

```c
int low_level_driver(
    char *InstrName,           // "PMU1"
    long ForceCh,              // Channel 1 (force)
    double ForceVRange,        // Voltage range for force channel
    double ForceIRange,        // Current range for force channel
    long MeasureCh,            // Channel 2 (measure)
    double MeasureVRange,      // Voltage range for measure channel
    double MeasureIRange,      // Current range for measure channel
    int max_pts,               // Maximum data points
    double MeasureBias,        // Measurement bias voltage
    double *Volts,             // Voltage array for waveform
    int volts_size,            // Size of voltage array
    double *Times,             // Time array for waveform
    int times_size,            // Size of time array
    double *VF, int vf_size,  // Output: Force voltage
    double *IF, int if_size,   // Output: Force current
    double *VM, int vm_size,   // Output: Measure voltage
    double *IM, int im_size,   // Output: Measure current
    double *T, int t_size,     // Output: Time array
    int *npts                  // Output: Actual number of points acquired
);
```

#### 7. **Resistance Calculation**

All modules calculate resistance using actual measured voltage:

```c
// Get voltage at measurement probe (actual measured voltage)
double probeVoltage = 0.0;
stat = ret_find_value(VMret, Tret, numpts, measMinTime[i], measMaxTime[i], &probeVoltage);

// Get current at measurement probe
double probeCurrent = 0.0;
stat = ret_find_value(IMret, Tret, numpts, measMinTime[i], measMaxTime[i], &probeCurrent);

// Calculate resistance: R = V / I (use actual measured voltage, not intended voltage)
if (fabs(probeCurrent) > 1e-12)  // Avoid division by zero
{
    double resistance = fabs(probeVoltage / probeCurrent);
    setR[i] = resistance;
}
```

**Critical**: Always use `probeVoltage` (actual measured voltage) for resistance calculation, not `measV` (intended measurement voltage).

#### 8. **Output Array Population**

All modules populate output arrays that Python queries via GP parameters:

```c
// Store measured values
setV[i] = probeVoltage;  // Measured voltage
setI[i] = probeCurrent;  // Measured current
PulseTimes[i] = measMinTime[i];  // Timestamp
```

### Low-Level Driver Architecture

All low-level drivers follow this pattern:

1. **Channel Configuration**:
   ```c
   // Configure force channel (CH1)
   pmu_forcev_range(inst, ForceCh, ForceVRange);
   pmu_forcei_range(inst, ForceCh, ForceIRange);
   pmu_ilimit(inst, ForceCh, iFLimit);
   
   // Configure measure channel (CH2)
   pmu_forcev_range(inst, MeasureCh, MeasureVRange);
   pmu_forcei_range(inst, MeasureCh, MeasureIRange);
   pmu_ilimit(inst, MeasureCh, iMLimit);
   ```

2. **Waveform Execution**:
   ```c
   // Execute waveform using seg_arb_sequence
   seg_arb_sequence(inst, ForceCh, volts, times, volts_size, ...);
   ```

3. **Data Acquisition**:
   ```c
   // Acquire raw data at hardware sample rate
   pmu_trigger(inst, ForceCh);
   pmu_trigger(inst, MeasureCh);
   
   // Read data into global arrays
   pmu_fetch(inst, ForceCh, VFret, IFret, numpts);
   pmu_fetch(inst, MeasureCh, VMret, IMret, numpts);
   ```

4. **Memory Management**:
   ```c
   // Allocate global arrays based on max_points
   VFret = (double *)calloc(max_points, sizeof(double));
   IFret = (double *)calloc(max_points, sizeof(double));
   VMret = (double *)calloc(max_points, sizeof(double));
   IMret = (double *)calloc(max_points, sizeof(double));
   Tret = (double *)calloc(max_points, sizeof(double));
   ```

### Helper Functions

Common helper functions used across modules:

1. **`ret_find_value()` / `read_train_find_value()`**:
   - Extracts average value from array within time window
   - Used to get voltage/current from measurement windows

2. **`ret_getRate()` / `read_train_getRate()`**:
   - Calculates optimal sample rate based on total waveform duration and max_points
   - Ensures hardware limits are not exceeded

3. **`ret_report_values()` / `read_train_report_values()`**:
   - Debug function to report time array values
   - Used when debug mode is enabled

---

## System Limits and Constraints

### Hardware Limits (Keithley 4200A-SCS 4225-PMU)

- **Maximum Samples per A/D Test**: 1,000,000 samples
- **Maximum Sample Rate**: 200 MSa/s
- **Minimum Segment Time**: 20 ns (2e-8 s)
- **Maximum Segment Time**: 1 s
- **Voltage Range**: -20 V to +20 V
- **Current Range**: 100 nA to 0.8 A

### Software Limits

- **Maximum `max_points`**: 30,000 (default, can be increased to 1,000,000)
- **Maximum Array Sizes**: Varies by module (typically 1,000-3,000 measurements)
- **Measurement Window**: 40-90% of pulse width (ratio = 0.4)

### Memory Usage

- **Raw Data Arrays**: ~240 MB for 1M samples (5 arrays × 1M × 8 bytes)
- **Waveform Segments**: Varies by module (typically 100-4,000 segments)
- **Output Arrays**: ~24-26 KB per 1,000 measurements (3 arrays × 1,000 × 8 bytes)

---

## Getting Started

### Prerequisites

1. **Keithley 4200A-SCS** with PMU installed
2. **GPIB Connection** to computer
3. **Python 3.x** with `pyvisa` installed
4. **C Modules Compiled** and loaded into Keithley 4200A (USRLIB)

### Basic Usage

1. **Navigate to module directory**:
   ```bash
   cd Equipment/SMU_AND_PMU/C_Code_with_python_scripts/Readtrain
   ```

2. **Run Python script**:
   ```bash
   python run_readtrain_dual_channel.py --gpib-address GPIB0::17::INSTR --numb-meas-pulses 10
   ```

3. **Check individual module READMEs** for detailed usage examples and parameters.

### Common Parameters

Most modules share these common parameters:

- `--gpib-address`: GPIB address (default: `GPIB0::17::INSTR`)
- `--meas-v`: Measurement voltage (typically 0.3-0.5V)
- `--meas-width`: Measurement pulse width (typically 2e-6 s)
- `--max-points`: Maximum data points (default: 10000, max: 30000 or 1000000)
- `--dry-run`: Print command without executing

---

## Troubleshooting

### No Data Returned

- **Check array sizes**: Ensure output array sizes match expected number of measurements
- **Verify GP parameters**: Check that correct parameter numbers are being queried
- **Check hardware connection**: Ensure PMU channels 1 and 2 are properly connected
- **Verify UL mode**: Ensure User Library mode is entered before EX command

### Incorrect Resistance Values

- **Verify measurement voltage**: Check that `measV` is appropriate (typically 0.3-0.5V)
- **Check current range**: Ensure `IRange` is set correctly
- **Verify measurement window**: Measurements are taken at 40-90% of pulse width
- **Check for division by zero**: Very small currents may cause issues

### Hardware Errors

- **Check dual-channel mode**: Both CH1 and CH2 must be connected
- **Verify voltage/current ranges**: Ensure ranges are appropriate for your device
- **Check current limits**: Device may be drawing too much current
- **Verify sample rate**: May need to reduce `max_points` for longer measurements

### Measurement Duration Too Short

- **Increase `max_points`**: Maximum is 30,000 (default) or 1,000,000 (hardware limit)
- **Reduce sample rate**: Driver automatically adjusts, but reducing `max_points` forces lower rate
- **Reduce number of pulses**: Fewer pulses = shorter total duration = more samples per pulse

---

## Module-Specific Documentation

Each module has its own detailed README with:
- Waveform ASCII art
- Complete parameter descriptions
- Usage examples
- Technical implementation details
- C program architecture
- System limits and constraints
- Troubleshooting guides

**See individual module directories for detailed documentation.**

---

## File Structure

```
C_Code_with_python_scripts/
├── README.md (this file)
├── Readtrain/
│   ├── README.md
│   ├── run_readtrain_dual_channel.py
│   ├── readtrain_dual_channel.c
│   └── read_train_ilimit.c
├── retention/
│   ├── README.md
│   ├── run_pmu_retention.py
│   ├── pmu_retention_dual_channel.c
│   └── retention_pulse_ilimit_dual_channel.c
├── potentiation_depression/
│   ├── README.md
│   ├── pmu_potentiation_depression.py
│   ├── pmu_potentiation_depression.c
│   └── retention_pulse_ilimit_dual_channel.c
├── pmu_pulse_read_interleaved/
│   ├── README.md
│   ├── run_pmu_potentiation_depression.py
│   ├── pmu_pulse_read_interleaved.c
│   └── retention_pulse_ilimit_dual_channel.c
├── Read_with_laser_pulse/
│   ├── README.md
│   ├── Read_With_Laser_Pulse_SegArb_Python.py
│   └── Pull from 4200 this is wrong.c
├── Read_With_Binary_waveform/
│   ├── Read_With_Binary_waveform.py
│   └── ACraig11_PMU_Waveform_Binary.c
├── Readtrain_with_user_wait (UNUSED)/
│   ├── README.md
│   ├── run_pmu_readtrain with wait.py
│   ├── ACraig5_PMU_retention.c
│   ├── ACraig5_retention_pulse_ilimitNK.c
│   ├── ACraig5_wait_mode.c
│   └── ACraig5_wait_signal.c
└── Ignore---pulsetrain+laser(no seg arb)/
    ├── ACraig8_single_channel_wave_aux.py
    └── ACraig8_single_channel_wave_aux.c
```

---

## See Also

- **Keithley 4200A-SCS Documentation**: Official instrument documentation
- **KXCI Reference**: Keithley eXternal Control Interface documentation
- **Individual Module READMEs**: Detailed documentation for each module

---

## Notes

- All modules require **dual-channel mode** (CH1 and CH2 connected)
- Measurement windows are **40-90% of pulse width** to avoid transients
- Resistance is calculated using **actual measured voltage**, not intended voltage
- Maximum hardware limit is **1,000,000 samples** per A/D test
- Default `max_points` is **30,000** for reasonable data retrieval speed

---

## Version History

- **2025-01-XX**: Initial comprehensive documentation
- All modules follow consistent architecture and data flow patterns

