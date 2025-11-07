# Keithley-Memstress Modules Analysis

## Overview
These modules from the `keithley-memstress` repository are **USRLIB modules** (like your existing `PMU_PulseTrain` and `PMU_retention`). They use the **NVM (Non-Volatile Memory) library** which you have at `G:\userlib\nvm\src`. They can be compiled and called via KXCI just like your existing functions.

---

## Module 1: `chris_man_retention.c`

### What it does:
- **Time-based retention test**: Performs a single reset pulse, then periodically measures resistance over a specified time period (minutes)
- Runs in a loop: repeatedly measures resistance at intervals until the time limit is reached
- Each measurement cycle: applies a reset pulse, then measures resistance at `resTestV`
- Returns: resistance values over time, timestamps

### Key Features:
- Continuous monitoring over hours/days
- Time limit specified in minutes (`time_limit` parameter)
- Uses Windows system time to track elapsed time
- Can optionally measure resistance before starting (`takeRmeas`)

### Parameters:
```c
int chris_man_retention(
    double riseTime,        // Voltage ramp time
    double widthTime,       // Pulse width at full voltage
    double delayTime,       // Delay before/after pulse
    int complianceCH,       // SMU channel for compliance
    double resetV,          // Reset pulse voltage (negative for ReRAM)
    double Irange,          // Current measurement range
    double resetIcomp,      // Current compliance during reset
    double resTestV,        // Voltage for resistance measurement
    int takeRmeas,          // 1=measure resistance, 0=don't
    int useSmu,             // 1=use SMU, 0=use PMU
    int *pts,               // Output: number of points
    double *resetResistance,// Output: resistance after reset
    int time_limit,         // Time limit in MINUTES
    double *TimeRES,        // Output: time array
    double *Out_size,       // Output: size info
    int Out_size_val        // Size of output arrays
)
```

### Can it be adapted?
**YES!** This is already a USRLIB module. You can:
1. Compile it (ensure `nvm.h` is accessible from `G:\userlib\nvm\src`)
2. Load it on the 4200A
3. Call it via KXCI: `EX Python_Controlled_PMU_Craig chris_man_retention(...)`
4. Query output arrays via GP commands

**Note**: You already implemented a Python version (`long_term_retention_test()`) that calls `pmu_retention_simple()` repeatedly. This C version runs entirely on the 4200A, which may be more efficient for long tests.

---

## Module 2: `chris_man_reramSweep.c`

### What it does:
- **Double sweep test**: Performs a reset pulse followed by a set pulse, capturing full waveforms
- Can perform multiple iterations (`numIter` parameter)
- Measures resistance before and after each pulse
- Returns: voltage/current/time arrays for the entire waveform, plus resistance values

### Key Features:
- Full waveform capture (V-I curves)
- Configurable number of iterations
- Can optionally skip resistance measurements on some iterations
- Supports both PMU and SMU modes
- Can loop with voltage increments (`loopNum`, `stepIncrement`)

### Parameters:
```c
int chris_man_reramSweep(
    double riseTime, double widthTime, double delayTime,
    int complianceCH,
    double resetV, double setV,        // Reset and set voltages
    double Irange,
    double resetIcomp, double setIcomp,// Current compliance
    double resTestV,
    int takeRmeas, int useSmu,
    double numIter,                    // Number of iterations
    double *Vforce, int Vforce_size,  // Output arrays
    double *Imeas, int Imeas_size,
    double *Time, int Time_size,
    int *pts,
    double *resetResistance,
    double *setResistance,
    double *initResistance,
    int loopNum,                       // Number of loops
    double stepIncrement               // Voltage increment per loop
)
```

### Can it be adapted?
**YES!** This is a USRLIB module. Useful for:
- IV characterization
- Set/reset switching behavior
- Waveform analysis

---

## Module 3: `chris_man_reramEndurance.c`

### What it does:
- **Endurance testing**: Runs multiple cycles of set/reset pulses and tracks resistance degradation
- Performs `max_loops` total cycles (can be very large, e.g., 1e12)
- Measures resistance `fatigue_count` times during the test
- Returns: resistance values vs. cycle number

### Key Features:
- High cycle count testing (endurance)
- Tracks resistance degradation over time
- Can run for millions/billions of cycles
- Internally calls `reramSweep()` function from NVM library

### Parameters:
```c
int chris_man_reramEndurance(
    double riseTime, double widthTime, double delayTime,
    int useSmu, int complianceCH,
    double resetV, double setV,
    double Irange,
    double resetIcomp, double setIcomp,
    double resTestV,
    double max_loops,                  // Total cycles (can be huge)
    double *resetRes,                  // Output: resistance arrays
    double *setRes,
    double *initRes,
    double *Vforce,                    // Output: voltage arrays
    char *debug_out,                   // Debug output
    double *debug_double,
    double *Time
)
```

### Can it be adapted?
**YES!** This is a USRLIB module. Essential for:
- Reliability testing
- Endurance characterization
- Lifetime estimation

---

## Module 4: `chris_man_memstress.c`

### What it does:
- **Stress testing**: Similar to reramSweep but with additional stress/verification features
- Performs set/reset sweeps with zone checking
- Includes verifying pulses to check device state
- Tracks resistance differences and pulse counts

### Key Features:
- Stress testing with verification
- Zone-based testing (voltage zones)
- Can perform multiple loops with increments
- More advanced than basic reramSweep

### Parameters:
```c
int chris_man_memstress(
    double riseTime, double widthTime, double delayTime,
    int complianceCH,
    double resetV, double Vin,         // Input voltage
    double Irange,
    double resetIcomp,
    double resTestV,
    int takeRmeas,
    int *pts,
    double *resetResistance,
    double *Out_size,
    int Out_size_val,
    double zone_low, double zone_high, // Voltage zones
    double stepIncrement,
    double *Vforce,
    int *Verifying_pulses,             // Output: verification pulse count
    double *Resistance_diff,           // Output: resistance differences
    int loop_num                       // Number of loops
)
```

### Can it be adapted?
**YES!** This is a USRLIB module. Useful for:
- Advanced stress testing
- Zone-based characterization
- Verification testing

---

## How to Adapt These Modules

### Step 1: Compilation Setup
1. Ensure `nvm.h` header is accessible (from `G:\userlib\nvm\src`)
2. Link against the NVM library functions (they're in the same directory)
3. Compile as USRLIB modules (same process as `PMU_PulseTrain.c`)

### Step 2: Module Loading
1. Load the compiled modules onto the 4200A using KULT (Keithley User Library Tool)
2. Assign them to a library name (e.g., `Python_Controlled_PMU_Craig`)

### Step 3: Python Wrapper Functions
Create Python wrapper functions in `Keithley4200A_KXCI.py` similar to `pmu_retention_test()`:

```python
def chris_man_retention(self, riseTime, widthTime, delayTime, complianceCH, 
                        resetV, Irange, resetIcomp, resTestV, takeRmeas, 
                        useSmu, time_limit, TimeRES_size, Out_size_val):
    """
    Time-based retention test using NVM library.
    
    Returns:
        dict: Contains 'pts', 'resetResistance', 'TimeRES', 'Out_size', 'success'
    """
    # Enter UL mode
    # Build EX command
    # Execute
    # Query output arrays via GP commands
    # Exit UL mode
    # Return results
```

### Step 4: Key Differences from Your Existing Code

| Your Code | keithley-memstress Modules |
|-----------|---------------------------|
| Uses `retention_pulse_ilimitNK()` directly | Uses NVM library (`initNVMST()`, `pulse_test()`) |
| Manual segment building | NVM structures handle waveform setup |
| Direct `seg_arb_sequence`/`seg_arb_waveform` | Abstracted through NVM library |
| Simpler, more direct | More features, Windows time support |

### Step 5: Advantages of Using These Modules

1. **More features**: Built-in endurance testing, stress testing, zone checking
2. **Time tracking**: Windows system time for accurate long-term tests
3. **Proven reliability**: Used in production environments
4. **Rich output**: More diagnostic information

### Step 6: Potential Challenges

1. **NVM library dependency**: Must compile with NVM library linked
2. **Header file location**: Need to ensure `nvm.h` is found during compilation
3. **Function signatures**: May need to adjust parameter formatting for KXCI
4. **Output array sizes**: Need to match Python expectations

---

## Recommendation

Since you already have:
- `PMU_retention.c` (working example)
- `PMU_RetentionSimple.c` (your simpler version)
- `long_term_retention_test()` Python function (time-based testing)

**For `chris_man_retention.c`**: 
- Consider using it if you want the test to run entirely on the 4200A (no Python loop overhead)
- Your Python version is already working and may be easier to debug/modify

**For `chris_man_reramSweep.c`**:
- **Highly recommended** - This provides IV characterization you don't currently have
- Useful for understanding switching behavior

**For `chris_man_reramEndurance.c`**:
- **Highly recommended** - Essential for endurance/reliability testing
- Your current code doesn't have this capability

**For `chris_man_memstress.c`**:
- Useful if you need advanced stress testing with verification
- Less critical than endurance and sweep

---

## Next Steps

1. **Test compilation**: Try compiling one module (e.g., `chris_man_reramSweep.c`) to verify NVM library linking works
2. **Create wrapper**: Start with `chris_man_reramSweep` as it's most straightforward
3. **Add to test script**: Add test functions to `test_keithley4200a_kxci.py`
4. **Iterate**: Once one works, adapt the others




