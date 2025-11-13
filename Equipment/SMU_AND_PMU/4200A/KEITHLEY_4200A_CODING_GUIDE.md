# Keithley 4200A Coding Guide: C and Python

This document consolidates important information for coding with the Keithley 4200A-SCS PMU (Pulse Measure Unit) in C and Python via KXCI (Keithley External Control Interface).

## Table of Contents

1. [Overview](#overview)
2. [KXCI Command Structure](#kxci-command-structure)
3. [C Module Structure (USRLIB)](#c-module-structure-usrlib)
4. [Parameter Passing](#parameter-passing)
5. [Array Handling](#array-handling)
6. [Error Codes](#error-codes)
7. [Timing Constraints](#timing-constraints)
8. [Common Patterns](#common-patterns)
9. [Python Runner Patterns](#python-runner-patterns)
10. [Important Gotchas](#important-gotchas)

---

## Overview

The Keithley 4200A-SCS uses **KXCI (Keithley External Control Interface)** for external control. This allows calling C functions (User Library modules) from Python via GPIB.

**Key Concepts:**
- **KXCI**: Protocol for external control over GPIB
- **UL Mode**: User Library mode - must be entered before EX commands
- **EX Command**: Execute a C function (User Library module)
- **GP Command**: Get Parameter - retrieve output array data
- **USRLIB Module**: C function that can be called via KXCI

**Communication Flow:**
```
Python → GPIB → Keithley 4200A → C Module → Hardware → Data → Python
```

---

## KXCI Command Structure

### Entering UL Mode

Before executing any EX commands, you must enter User Library (UL) mode:

```python
# Python
inst.write("UL")
time.sleep(0.03)  # Wait 30ms
```

### EX Command Format

**Syntax:**
```
EX <LibraryName> <FunctionName>(<param1>,<param2>,...,<paramN>)
```

**Example:**
```
EX ACraig11 ACraig11_PMU_Waveform_Binary(5.00E-7,1.00E-7,1.00E-7,0,5.00E-7,10,1.00E-5,1.00E+6,1.5,1.5,0,0,1,0,1.00E-1,1.00E-1,1,100,2.00E+8,0,1,PMU1,,100,,100,,100,1,10,8,10110100,0,5.00E-7,1.00E-7,1.00E-7,5.00E-7,0,1.5,1,1)
```

**Response:**
- Success: Returns integer (usually `0` for success, `1` for completion, negative for errors)
- Error: Returns error string

### GP Command Format

**Syntax:**
```
GP <parameter_number>
```

**Example:**
```
GP 23  # Get parameter 23 (first output array)
```

**Response:**
- Returns comma-separated values: `1.234,5.678,9.012,...`
- Empty arrays return empty string or `0`

**Important:**
- Parameter numbers are **1-based** (first parameter = 1)
- Output arrays are passed as empty strings (`""`) in EX command
- Array sizes come **immediately after** the array parameter
- For string arrays, pass as single string without commas (e.g., `"10110100"`)

### Exiting UL Mode

```python
# Python
inst.write("DE")
time.sleep(0.03)  # Wait 30ms
```

---

## C Module Structure (USRLIB)

### Required Metadata Block

Every C module must start with a metadata block that KXCI uses to parse parameters:

```c
/* USRLIB MODULE INFORMATION

	MODULE NAME: YourModuleName
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 41
	ARGUMENTS:
		param1,	type,	Input,	default,	min,	max
		param2,	type,	Input,	default,	min,	max
		...
		outputArray,	D_ARRAY_T,	Output,	,	,	
		outputArraySize,	int,	Input,	100,	1,	32767
	INCLUDES:
#include "keithley.h"
	END USRLIB MODULE INFORMATION
*/
```

### Parameter Types

- **`double`**: Floating-point number
- **`int`**: Integer
- **`char *`**: String (e.g., `"PMU1"`, `"SMU1"`)
- **`D_ARRAY_T`**: Output array (always `double *` in function signature)
- **`long`**: Long integer (sometimes used instead of `int`)

### Parameter Direction

- **`Input`**: Parameter passed TO the module
- **`Output`**: Array returned FROM the module (via GP command)

### Function Signature

The C function signature must match the metadata exactly:

```c
int YourModuleName(
    double param1, int param2, char *PMU_ID,
    double *outputArray, int outputArraySize,
    int ClariusDebug
)
{
    // Function body
    return 0;  // 0 = success (KXCI convention)
}
```

### Critical Rules

1. **`NUMBER OF PARMS`** must match the total number of parameters in the function signature
2. **Parameter order** in metadata must match function signature exactly
3. **Array sizes** must come immediately after their arrays
4. **Output arrays** are passed as empty strings (`""`) in EX command
5. **Return value**: Use `0` for success (KXCI convention)

---

## Parameter Passing

### Parameter Formatting (Python)

**Floats:**
- Small values (< 1.0): Scientific notation: `1.00E-7`
- Large values (>= 1.0, < 1e6): Standard notation: `1.5`, `10.0`
- Very large values: Scientific notation: `2.00E+8`
- Zero: `"0"`

**Example Python function:**
```python
def format_param(value: float | int | str) -> str:
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        if value >= 1.0 and value < 1e6:
            if value == int(value):
                return str(int(value))
            return f"{value:.10g}".rstrip('0').rstrip('.')
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)
```

**Integers:**
- Pass as-is: `"1"`, `"100"`, `"0"`

**Strings:**
- Pass as-is: `"PMU1"`, `"SMU1"`, `"10110100"` (no quotes in EX command)

**Arrays:**
- Output arrays: Pass as empty string `""`
- Array sizes: Pass as integer string (e.g., `"100"`)
- String arrays: Pass as single concatenated string (e.g., `"10110100"`)

### Building EX Commands

**Example:**
```python
def build_ex_command(width, rise, fall, pmu_id, array_size, debug):
    params = [
        format_param(width),      # 1: double
        format_param(rise),       # 2: double
        format_param(fall),       # 3: double
        pmu_id,                   # 4: char * (no quotes)
        "",                       # 5: output array (empty)
        format_param(array_size), # 6: array size
        format_param(debug),       # 7: int
    ]
    return f"EX ACraig11 ACraig11_PMU_Waveform_Binary({','.join(params)})"
```

**Critical:**
- **No spaces** after commas
- **No quotes** around strings (except in Python string literal)
- **Empty strings** for output arrays
- **Exact parameter count** must match `NUMBER OF PARMS`

---

## Array Handling

### Output Arrays in C

Output arrays are allocated by KXCI and passed as pointers:

```c
int YourModule(
    double *V_Meas, int size_V_Meas,  // Output array + size
    double *I_Meas, int size_I_Meas,  // Output array + size
    double *T_Stamp, int size_T_Stamp // Output array + size
)
{
    // Write data to arrays
    for (int i = 0; i < size_V_Meas && i < num_points; i++)
    {
        V_Meas[i] = voltage_data[i];
        I_Meas[i] = current_data[i];
        T_Stamp[i] = time_data[i];
    }
    
    // Zero out remaining elements
    for (int i = num_points; i < size_V_Meas; i++)
    {
        V_Meas[i] = 0.0;
        I_Meas[i] = 0.0;
        T_Stamp[i] = 0.0;
    }
    
    return 0;
}
```

### Retrieving Arrays in Python

**GP Command:**
```python
def safe_query(gp_param: int, num_points: int, name: str) -> List[float]:
    """Query GP parameter and parse array values."""
    query = f"GP {gp_param}"
    response = inst.query(query).strip()
    
    # Parse comma-separated values
    values = []
    for part in response.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(float(part))
        except ValueError:
            pass
    return values

# Usage
voltage = safe_query(23, 100, "voltage")  # Parameter 23, 100 points
current = safe_query(25, 100, "current")  # Parameter 25, 100 points
```

**Parameter Numbering:**
- Parameters are **1-based** (first parameter = 1)
- Output arrays are counted as parameters
- Example: If `V_Meas` is parameter 23, query with `GP 23`

**Finding Parameter Numbers:**
- Count parameters in order from the C function signature
- Output arrays count as parameters (even though passed as `""`)
- Array sizes count as separate parameters

**Example:**
```c
int Function(
    double width,           // Param 1
    double rise,            // Param 2
    char *PMU_ID,          // Param 3
    double *V_Meas,        // Param 4 (output array, passed as "")
    int size_V_Meas,       // Param 5 (array size)
    double *I_Meas,        // Param 6 (output array, passed as "")
    int size_I_Meas        // Param 7 (array size)
)
```

To retrieve `V_Meas`: `GP 4`
To retrieve `I_Meas`: `GP 6`

### Array Size Considerations

- **Always validate** array sizes before writing
- **Zero out** unused array elements
- **Trim trailing zeros** in Python after retrieval
- **Handle NaN values** (some modules initialize arrays to NaN)

---

## Error Codes

### Common Error Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `0` | Success | Normal completion |
| `1` | Completion | Measurement completed (some modules use 1 instead of 0) |
| `-122` | Illegal parameter | Invalid parameter value (e.g., timing < minimum, invalid range) |
| `-804` | seg_arb function not valid | PMU not in SARB mode when calling seg_arb functions |
| `-824` | Invalid pulse timing | Period/width/rise/fall don't meet PMU constraints |
| `-831` | Too many samples | Requested samples exceed hardware limit (65536) |
| `-844` | Invalid sweep parameters | startV/stopV/stepV combination invalid |
| `-998` | Timeout | Pulse execution timed out (usually > 20 seconds) |
| `-999` | Memory allocation failed | `calloc()` or `malloc()` failed |
| `-17001` | Wrong card ID | PMU/SMU not in system configuration |
| `-17002` | Card handle fail | Failed to get instrument ID |
| `-17100` | Measurement window error | Measurement window outside pulse top |
| `-17110` | Output array too small | Array size < number of data points |

### Error Handling Pattern

**C Code:**
```c
if (status)
{
    if(debug) printf("ERROR: Operation failed: %d\n", status);
    // Cleanup allocated memory
    if (allocated_arrays)
    {
        free(array1);
        free(array2);
    }
    return status;  // Return error code
}
```

**Python Code:**
```python
return_value, error_msg = controller.execute_ex(command)

if error_msg:
    print(f"[ERROR] Command failed: {error_msg}")
    return

if return_value != 0:
    print(f"[ERROR] Return value is {return_value}")
    if return_value == -122:
        print("  -122: Illegal parameter (check timing constraints)")
    elif return_value == -804:
        print("  -804: seg_arb function requires SARB mode")
    return
```

---

## Timing Constraints

### PMU Pulse Timing Requirements

**Minimum Period:**
- **10V range**: `period >= 120ns`
- **40V range**: `period >= 280ns`
- **General**: `period >= delay + width + rise + fall`

**Minimum Off-Time:**
```
period - delay - width - 0.5*(rise + fall) >= 40ns
```

**Minimum Segment Time (seg_arb):**
- **20ns** minimum for any segment
- Applies to: rise, fall, width, delay, spacing

**Rise/Fall Times:**
- **Minimum**: 20ns (hardware limit)
- **Maximum**: 33ms (for simple pulses)
- **Practical minimum**: 100ns (for reliable operation)

**Pulse Width:**
- **Minimum**: Depends on rise/fall times
- **Practical minimum**: `rise + fall + 20ns` (typically ~220ns)

### Period Calculation

**Formula:**
```c
double min_required_period = delay + width + rise + fall;
double min_off_time = 40e-9;  // 40ns
double required_period_for_off_time = delay + width + 0.5*(rise + fall) + min_off_time;
double pmu_min_period = (voltsSourceRng <= 10.0) ? 120e-9 : 280e-9;

double actual_min_period = max(min_required_period, required_period_for_off_time, pmu_min_period);
```

**Example:**
- `delay = 0`, `width = 500ns`, `rise = 100ns`, `fall = 100ns`, `VRange = 10V`
- `min_required_period = 0 + 500ns + 100ns + 100ns = 700ns`
- `required_for_off_time = 0 + 500ns + 0.5*(100ns+100ns) + 40ns = 640ns`
- `pmu_min_period = 120ns`
- `actual_min_period = max(700ns, 640ns, 120ns) = 700ns`

### CH1/CH2 Period Constraint

**CRITICAL:** Both CH1 and CH2 **MUST share the same period**. This is a hardware limitation.

**Implications:**
- CH2 pulse must fit within one period: `CH2_width + CH2_rise + CH2_fall + 40ns <= period`
- If CH2 pulse is longer than period, CH2 configuration will fail with `-122`
- CH2 delay determines **when** it fires (can be > period to fire after N pulses)

**Workaround for Long CH2 Pulses:**
- Use CH2 as trigger (short pulse, e.g., 100ns)
- Connect CH2 output to external function generator (FG) trigger input
- Configure FG to generate longer pulse (e.g., 10µs) when triggered

---

## Common Patterns

### C Module Initialization Pattern

```c
int YourModule(/* parameters */)
{
    int debug = 0;
    int status;
    int pulserId;
    
    if (ClariusDebug == 1) { debug = 1; } else { debug = 0; }
    if(debug) printf("\n\nYourModule: starts\n");
    
    // Validate instrument is in configuration
    if (!LPTIsInCurrentConfiguration(PMU_ID))
    {
        if(debug) printf("Instrument %s is not in system configuration\n", PMU_ID);
        return -17001;
    }
    
    // Get instrument ID
    getinstid(PMU_ID, &pulserId);
    if (-1 == pulserId)
    {
        if(debug) printf("Failed to get instrument ID\n");
        return -17002;
    }
    
    // Initialize PMU
    status = pg2_init(pulserId, PULSE_MODE_PULSE);  // or PULSE_MODE_SARB
    if (status)
    {
        if(debug) printf("pg2_init failed: %d\n", status);
        return status;
    }
    
    // ... rest of code ...
    
    return 0;  // Success
}
```

### Data Retrieval Pattern (pulse_fetch)

```c
// Allocate temporary buffers
double *waveformV = (double *)calloc(maxSamples, sizeof(double));
double *waveformI = (double *)calloc(maxSamples, sizeof(double));
double *waveformT = (double *)calloc(maxSamples, sizeof(double));

// Fetch waveform data
status = pulse_fetch(pulserId, chan, 0, maxSamples-1, waveformV, waveformI, waveformT, NULL);
if (status)
{
    if(debug) printf("pulse_fetch failed: %d\n", status);
    free(waveformV); free(waveformI); free(waveformT);
    return status;
}

// Process data and copy to output arrays
for (int i = 0; i < num_points && i < size_V_Meas; i++)
{
    V_Meas[i] = waveformV[i];
    I_Meas[i] = waveformI[i];
    T_Stamp[i] = waveformT[i];
}

// Zero out remaining elements
for (int i = num_points; i < size_V_Meas; i++)
{
    V_Meas[i] = 0.0;
    I_Meas[i] = 0.0;
    T_Stamp[i] = 0.0;
}

// Free temporary buffers
free(waveformV);
free(waveformI);
free(waveformT);
```

### seg_arb Pattern

```c
// CRITICAL: Must be in SARB mode for seg_arb functions
int pulse_mode = PULSE_MODE_SARB;
status = pg2_init(pulserId, pulse_mode);
if (status) return status;

// Build segments
double *startv = (double *)calloc(num_segments, sizeof(double));
double *stopv = (double *)calloc(num_segments, sizeof(double));
double *segtime = (double *)calloc(num_segments, sizeof(double));
long *segtrigout = (long *)calloc(num_segments, sizeof(long));
long *ssrctrl = (long *)calloc(num_segments, sizeof(long));
long *meastype = (long *)calloc(num_segments, sizeof(long));
double *measstart = (double *)calloc(num_segments, sizeof(double));
double *measstop = (double *)calloc(num_segments, sizeof(double));

// CRITICAL: First segment MUST have segtrigout=1
segtrigout[0] = 1;

// Configure sequence
status = seg_arb_sequence(pulserId, chan, 1, num_segments,
                          startv, stopv, segtime,
                          segtrigout, ssrctrl,
                          meastype, measstart, measstop);
if (status) {
    // Cleanup and return error
    free(startv); free(stopv); free(segtime);
    // ... free other arrays ...
    return status;
}

// Configure waveform (loop count)
long seqList[1] = {1};
double loopCount[1] = {burst_count};
status = seg_arb_waveform(pulserId, chan, 1, seqList, loopCount);
if (status) {
    // Cleanup and return error
    return status;
}

// Free arrays (seg_arb_sequence copies data to hardware)
free(startv); free(stopv); free(segtime);
// ... free other arrays ...
```

### Pulse Execution Pattern

```c
// Set test execute mode
int TestMode;
if (PMUMode == 0)
    TestMode = PULSE_MODE_SIMPLE;
else
    TestMode = PULSE_MODE_ADVANCED;

// Execute pulses
status = pulse_exec(TestMode);
if (status) {
    if(debug) printf("pulse_exec failed: %d\n", status);
    return status;
}

// Wait for completion
int i = 0;
double elapsedt;
while (pulse_exec_status(&elapsedt) == 1 && i < 200)
{
    Sleep(100);  // Wait 100ms
    i++;
}

if (i >= 200)
{
    if(debug) printf("ERROR: Pulse execution timed out after 20 seconds\n");
    return -998;
}

// Small delay to ensure data is ready
Sleep(50);  // 50ms
```

---

## Python Runner Patterns

### KXCIClient Class Pattern

```python
class KXCIClient:
    def __init__(self, gpib_address: str, timeout: float):
        self.gpib_address = gpib_address
        self.timeout_ms = int(timeout * 1000)
        self.rm = None
        self.inst = None
        self._ul_mode_active = False
    
    def connect(self) -> bool:
        import pyvisa
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(self.gpib_address)
        self.inst.timeout = self.timeout_ms
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"
        idn = self.inst.query("*IDN?").strip()
        print(f"[OK] Connected to: {idn}")
        return True
    
    def _enter_ul_mode(self) -> bool:
        if self.inst is None:
            return False
        self.inst.write("UL")
        time.sleep(0.03)  # 30ms delay
        self._ul_mode_active = True
        return True
    
    def _exit_ul_mode(self) -> bool:
        if self.inst is None or not self._ul_mode_active:
            self._ul_mode_active = False
            return True
        self.inst.write("DE")
        time.sleep(0.03)
        self._ul_mode_active = False
        return True
    
    def execute_ex(self, command: str) -> tuple[Optional[int], Optional[str]]:
        if not self._ul_mode_active:
            if not self._enter_ul_mode():
                return None, "Failed to enter UL mode"
        
        try:
            self.inst.write(command)
            time.sleep(0.03)  # 30ms delay
            response = self.inst.read().strip()
            try:
                return_value = int(response)
                return return_value, None
            except ValueError:
                return None, response
        except Exception as exc:
            return None, str(exc)
    
    def safe_query(self, gp_param: int, num_points: int, name: str) -> List[float]:
        """Query GP parameter and parse array values."""
        if not self._ul_mode_active:
            if not self._enter_ul_mode():
                return []
        
        try:
            query = f"GP {gp_param}"
            response = self.inst.query(query).strip()
            
            values = []
            for part in response.split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    val = float(part)
                    if val == val:  # NaN check
                        values.append(val)
                except ValueError:
                    pass
            return values
        except Exception as exc:
            print(f"[WARN] Failed to query GP {gp_param} ({name}): {exc}")
            return []
    
    def disconnect(self):
        try:
            if self._ul_mode_active:
                self._exit_ul_mode()
            if self.inst is not None:
                self.inst.close()
            if self.rm is not None:
                self.rm.close()
        finally:
            self.inst = None
            self.rm = None
            self._ul_mode_active = False
```

### Measurement Execution Pattern

```python
def run_measurement(args, enable_plot: bool):
    # Build EX command
    command = build_ex_command(/* parameters */)
    
    # Connect
    controller = KXCIClient(gpib_address=args.gpib_address, timeout=args.timeout)
    
    try:
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        # Execute EX command
        return_value, error_msg = controller.execute_ex(command)
        
        if error_msg:
            print(f"[ERROR] Command failed: {error_msg}")
            return
        
        if return_value != 0:
            print(f"[ERROR] Return value is {return_value} (expected 0)")
            return
        
        print("[OK] Return value is 0 (success)")
        
        # Retrieve data
        print("\n[KXCI] Retrieving data...")
        time.sleep(0.2)  # Give instrument time to prepare data
        
        voltage = controller.safe_query(23, num_points, "voltage")
        current = controller.safe_query(25, num_points, "current")
        time_axis = controller.safe_query(27, num_points, "time")
        
        # Trim trailing zeros
        last_valid = len(voltage)
        for idx in range(len(voltage) - 1, -1, -1):
            if (abs(time_axis[idx]) > 1e-12 or 
                abs(voltage[idx]) > 1e-12 or 
                abs(current[idx]) > 1e-12):
                last_valid = idx + 1
                break
        
        voltage = voltage[:last_valid]
        current = current[:last_valid]
        time_axis = time_axis[:last_valid]
        
        # Process data...
        
    finally:
        controller.disconnect()
```

---

## Important Gotchas

### 1. Parameter Order is Critical

**KXCI parses parameters by position**, not by name. The order in your EX command **MUST match** the C function signature exactly.

**Wrong:**
```python
# C function: int func(double width, double rise, double fall)
params = [format_param(rise), format_param(width), format_param(fall)]  # WRONG ORDER!
```

**Right:**
```python
params = [format_param(width), format_param(rise), format_param(fall)]  # CORRECT ORDER
```

### 2. Array Size Must Come Before Array (Sometimes)

For **input arrays**, the size parameter typically comes **before** the array:

```c
// C metadata
Ch2PatternSize,	int,	Input,	8,	1,	2048
Ch2Pattern,	char *,	Input,	"10110100",	,	
```

**Python:**
```python
params = [
    format_param(ch2_pattern_size),  # Size FIRST
    ''.join(str(b) for b in ch2_pattern),  # Array SECOND
]
```

### 3. Output Arrays are Empty Strings

Output arrays are passed as **empty strings** (`""`) in EX commands:

```python
params = [
    format_param(width),
    "",                    # V_Meas output array (empty!)
    format_param(100),    # size_V_Meas
    "",                    # I_Meas output array (empty!)
    format_param(100),    # size_I_Meas
]
```

### 4. String Arrays Must Be Single Parameter

If passing a string array (e.g., binary pattern), pass as **single concatenated string**:

**Wrong:**
```python
params = ["1", "0", "1", "1"]  # Counts as 4 parameters!
```

**Right:**
```python
params = ["1011"]  # Single string parameter
```

### 5. Parameter Count Must Match Exactly

The `NUMBER OF PARMS` in metadata **MUST equal** the total number of parameters in the function signature, including:
- All input parameters
- All output arrays (count as parameters)
- All array sizes (count as parameters)

**Example:**
```c
// Function signature has 7 parameters:
int func(double a, double b, char *id, double *out1, int size1, double *out2, int size2)

// NUMBER OF PARMS must be 7
```

### 6. Return Value Convention

- **KXCI convention**: Return `0` for success
- **Some modules**: Return `1` for completion (legacy)
- **Always check**: Both `0` and `1` may indicate success depending on module

### 7. UL Mode Must Be Active

**Always enter UL mode** before EX commands:
```python
if not controller._ul_mode_active:
    controller._enter_ul_mode()
```

### 8. Timing Delays

**Required delays:**
- After entering UL mode: `time.sleep(0.03)` (30ms)
- After EX command: `time.sleep(0.03)` (30ms)
- After GP query: `time.sleep(0.03)` (30ms)
- Before data retrieval: `time.sleep(0.2)` (200ms) - give instrument time to prepare

### 9. seg_arb Requires SARB Mode

**CRITICAL:** `seg_arb_sequence()` and `seg_arb_waveform()` **only work** in `PULSE_MODE_SARB`:

```c
// WRONG - will fail with -804
status = pg2_init(pulserId, PULSE_MODE_PULSE);
status = seg_arb_sequence(...);  // ERROR -804!

// RIGHT
status = pg2_init(pulserId, PULSE_MODE_SARB);
status = seg_arb_sequence(...);  // OK
```

### 10. First Segment Must Trigger

For `seg_arb_sequence()`, the **first segment MUST have `segtrigout=1`**:

```c
segtrigout[0] = 1;  // REQUIRED - first segment triggers
```

### 11. Segment Voltages Must Be Continuous

For `seg_arb_sequence()`, segment voltages must be continuous:
- `stopV[i] == startV[i+1]` (end of segment i = start of segment i+1)

### 12. Memory Management

**Always free allocated memory:**
```c
double *array = (double *)calloc(size, sizeof(double));
// ... use array ...
free(array);  // REQUIRED - prevent memory leaks
```

### 13. NaN Initialization

Some modules initialize output arrays to `DBL_NAN`. Filter these in Python:

```python
values = [v for v in values if v == v]  # Remove NaN (NaN != NaN is True)
```

### 14. Trailing Zeros

Output arrays may have trailing zeros. Trim them:

```python
last_valid = len(values)
for idx in range(len(values) - 1, -1, -1):
    if abs(values[idx]) > 1e-12:
        last_valid = idx + 1
        break
values = values[:last_valid]
```

### 15. GP Query Retry Logic

GP queries can timeout. Implement retry logic:

```python
def safe_query(gp_param: int, num_points: int, name: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return controller.safe_query(gp_param, num_points, name)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            else:
                print(f"[WARN] Failed after {max_retries} attempts: {e}")
                return []
    return []
```

---

## Measurement Window (40-80% Rule)

Many modules use a **40-80% measurement window** for averaging:

**Why 40-80%?**
- **Avoids transition regions**: First 40% excludes rise time and settling
- **Avoids fall transition**: Last 20% (80-100%) excludes fall time
- **Stable region**: Captures the most stable, flat portion of the pulse

**Implementation:**
```c
double measurementStartFrac = 0.4;  // 40% of pulse width
double measurementEndFrac = 0.8;    // 80% of pulse width

// Calculate measurement window
double pulse_start_time = delay + rise;
double meas_start_time = pulse_start_time + width * measurementStartFrac;
double meas_end_time = pulse_start_time + width * measurementEndFrac;

// Average samples within this window
```

---

## Common Function Patterns

### PMU Initialization

```c
// Check instrument exists
if (!LPTIsInCurrentConfiguration(PMU_ID))
    return -17001;

// Get instrument ID
getinstid(PMU_ID, &pulserId);
if (-1 == pulserId)
    return -17002;

// Initialize PMU mode
status = pg2_init(pulserId, PULSE_MODE_PULSE);  // or PULSE_MODE_SARB
if (status) return status;

// Set mode
status = setmode(pulserId, KI_LIM_MODE, KI_VALUE);
if (status) return status;

// Configure RPM (if using)
status = rpm_config(pulserId, chan, KI_RPM_PATHWAY, KI_RPM_PULSE);
if (status && debug) printf("rpm_config returned: %d\n", status);
```

### Simple Pulse Configuration

```c
// Set ranges
status = pulse_ranges(pulserId, chan, voltsSourceRng, PULSE_MEAS_FIXED, 
                      voltsSourceRng, PULSE_MEAS_FIXED, currentMeasureRng);
if (status) return status;

// Set load
status = pulse_load(pulserId, chan, DUTRes);
if (status) return status;

// Set timing
status = pulse_source_timing(pulserId, chan, period, delay, width, rise, fall);
if (status) return status;

// Configure measurement
status = pulse_meas_sm(pulserId, chan, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, TRUE, TRUE, LLEComp);
if (status) return status;

status = pulse_meas_timing(pulserId, chan, measStartPerc, measStopPerc, pulseAvgCnt);
if (status) return status;

// Configure sweep
status = pulse_sweep_linear(pulserId, chan, PULSE_AMPLITUDE_SP, startV, stopV, stepV);
if (status) return status;

// Enable output
status = pulse_output(pulserId, chan, 1);
if (status) return status;
```

### Data Fetching

```c
// Wait for completion
while (pulse_exec_status(&elapsedt) == 1)
{
    Sleep(100);
}

// Small delay
Sleep(50);

// Fetch data
status = pulse_fetch(pulserId, chan, startIdx, stopIdx, 
                     waveformV, waveformI, waveformT, NULL);
if (status) return status;
```

---

## Best Practices

### C Module Best Practices

1. **Always validate parameters** before use
2. **Check array sizes** before writing
3. **Initialize output arrays** to zero or NaN
4. **Free all allocated memory** before returning
5. **Return 0 on success** (KXCI convention)
6. **Use debug flag** for verbose output
7. **Validate instrument configuration** before proceeding
8. **Handle errors gracefully** with cleanup

### Python Runner Best Practices

1. **Always enter UL mode** before EX commands
2. **Check return values** (0 or 1 may indicate success)
3. **Implement retry logic** for GP queries
4. **Trim trailing zeros** from arrays
5. **Filter NaN values** if present
6. **Handle timeouts** gracefully
7. **Disconnect properly** (exit UL mode, close connection)
8. **Use descriptive parameter names** in comments
9. **Validate array sizes** match expected data
10. **Print debug information** for troubleshooting

---

## Quick Reference

### EX Command Template
```
EX <Library> <Function>(<param1>,<param2>,...,<paramN>)
```

### GP Query Template
```
GP <parameter_number>
```

### Parameter Formatting
- Float: `1.00E-7` (scientific) or `1.5` (standard)
- Int: `100`
- String: `PMU1` (no quotes in command)
- Array: `""` (empty string)

### Common Return Values
- `0`: Success
- `-122`: Illegal parameter
- `-804`: seg_arb requires SARB mode
- `-824`: Invalid timing
- `-17001`: Instrument not configured
- `-17002`: Failed to get instrument ID

### Timing Minimums
- Period: 120ns (10V) or 280ns (40V)
- Off-time: 40ns
- Segment time: 20ns (seg_arb)
- Rise/Fall: 20ns (hardware), 100ns (practical)

---

## Additional Resources

- **Keithley 4200A-SCS Reference Manual**: Official documentation
- **KXCI Programming Guide**: KXCI command reference
- **Working Examples**: See `ACraig2`, `ACraig9`, `ACraig10`, `ACraig11` modules
- **Python Runners**: See `run_acraig*.py` files for Python patterns

---

**Last Updated**: Based on codebase analysis of ACraig modules (ACraig2 through ACraig12)



