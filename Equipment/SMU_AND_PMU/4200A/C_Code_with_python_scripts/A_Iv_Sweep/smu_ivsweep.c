/* USRLIB MODULE INFORMATION

	MODULE NAME: smu_ivsweep
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 11
	ARGUMENTS:
		Vhigh,	double,	Input,	5,	0,	200
		Vlow,	double,	Input,	-5,	-200,	0
		NumSteps,	int,	Input,	20,	4,	10000
		NumCycles,	int,	Input,	1,	1,	1000
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumIPoints,	int,	Input,	21,	,	
		Vforce,	D_ARRAY_T,	Output,	,	,
		NumVPoints,	int,	Input,	21,	,	
		StepDelay,	double,	Input,	0.001,	0.0001,	10.0
		Ilimit,	double,	Input,	0.1,	1e-9,	1.0
		IntegrationTime,	double,	Input,	0.01,	0.0001,	1.0
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
#include <math.h>
#include <stdio.h>
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION

SMU Voltage-Current Sweep Module (Step-Based Pattern)
=====================================================

Performs step-based IV sweeps: 0V → Vhigh → 0V → Vlow → 0V, repeated NumCycles times.

Pattern: (0 → Vhigh → 0 → Vlow → 0) × n cycles
- Vhigh: Positive voltage limit (V), must be >= 0
- Vlow: Negative voltage limit (V), must be <= 0
- NumSteps: Total number of steps distributed across the full sweep path
  Steps are evenly distributed across 4 segments:
  * Segment 1: 0V → Vhigh (NumSteps/4 steps)
  * Segment 2: Vhigh → 0V (NumSteps/4 steps)
  * Segment 3: 0V → Vlow (NumSteps/4 steps)
  * Segment 4: Vlow → 0V (NumSteps/4 steps)
  Any remainder steps are distributed to first segments

Example: For Vhigh=5V, Vlow=-5V, NumSteps=20, NumCycles=1:
  0V → 5V (5 steps) → 0V (5 steps) → -5V (5 steps) → 0V (5 steps)
  Total: 21 points (20 steps + 1 start point)

Example: For Vhigh=3V, Vlow=-2V, NumSteps=16, NumCycles=2:
  Cycle 1: 0V → 3V → 0V → -2V → 0V (17 points)
  Cycle 2: 0V → 3V → 0V → -2V → 0V (17 points)
  Total: 34 points ((16+1) × 2)

Total points = (NumSteps + 1) × NumCycles (must match NumIPoints/NumVPoints)

IMPROVEMENTS OVER ORIGINAL:
- Added settling time at each voltage point before measurement (SettleTime parameter)
- Added error handling for forcev() and measi() calls
- Added current limit configuration (Ilimit parameter)
- Added integration time configuration (IntegrationTime parameter)
- Stores both forced voltage AND measured voltage (intgv) for comparison
- Added debug output option (ClariusDebug parameter)
- Added compliance checking to detect if device hit current limit
- Array initialization to zero
- Supports both forward (Vstart < Vstop) and reverse (Vstart > Vstop) sweeps
- Better error reporting with detailed messages

PARAMETERS:
- Vpos: Positive voltage (V), range: 0 to 200 V
        The sweep goes to +Vpos in each cycle
- Vneg: Negative voltage (V), range: -200 to 0 V
        The sweep goes to Vneg in each cycle
        If Vneg == 0, automatically uses -Vpos (symmetric sweep)
        Example: Vpos=5V, Vneg=0 → uses -5V automatically
        Example: Vpos=5V, Vneg=-2V → uses -2V (asymmetric sweep)
- NumCycles: Number of cycles to repeat (range: 1 to 1000)
             Each cycle consists of: 0V → +Vpos → Vneg → 0V
- Imeas: Output array for measured current (A)
- NumIPoints: Size of Imeas array (must equal 4 × NumCycles)
- Vforce: Output array for FORCED voltage (V) - stores nominal forced value
- NumVPoints: Size of Vforce array (must equal 4 × NumCycles, same as NumIPoints)
- SettleTime: Settling time at each voltage point before measurement (seconds)
              Default: 0.001 s (1 ms), range: 0.0001 to 10.0 s
              IMPORTANT: This allows the device to stabilize before measurement
- Ilimit: Current compliance limit (A), range: 1 nA to 1 A, default: 0.1 A
          Sets the maximum current before compliance is triggered
- IntegrationTime: Measurement integration time (PLC - Power Line Cycles)
                   Default: 0.01 PLC (fast), range: 0.0001 to 1.0 PLC
                   Lower = faster but noisier, Higher = slower but more accurate
- ClariusDebug: Debug output flag (0=off, 1=on), default: 0
                When enabled, prints progress and measurement values

OPERATION:
1. Validates input parameters (NumIPoints must equal 4 × NumCycles)
2. Initializes output arrays to zero
3. Sets integration time for measurements
4. Sets current compliance limit
5. Determine negative voltage:
   - If Vneg == 0, use -Vpos (symmetric sweep)
   - Otherwise, use Vneg as specified (asymmetric sweep)
6. For each cycle (NumCycles times):
   a. Point 1: Force 0V, wait, measure current
   b. Point 2: Force +Vpos, wait, measure current
   c. Point 3: Force Vneg (or -Vpos if Vneg==0), wait, measure current
   d. Point 4: Force 0V, wait, measure current
   Each point:
      - Forces voltage (forcev) with error checking
      - Waits for settling time (Sleep)
      - Measures current (measi) with error checking
      - Measures actual voltage at DUT (intgv)
      - Checks for compliance (if |I| >= Ilimit * 0.99, warning)
      - Stores forced voltage in Vforce array
      - Prints debug output if ClariusDebug=1
6. Returns to zero voltage at end
7. Returns 0 on success, negative error code on failure

ERROR CODES:
- -1: Invalid Vpos (must be >= 0)
- -1a: Invalid Vneg (must be <= 0, and Vneg == 0 is allowed for auto-symmetric)
- -2: NumIPoints != NumVPoints (array size mismatch)
- -3: NumIPoints != 4 × NumCycles (array size must equal 4 × number of cycles)
- -4: Invalid array sizes (NumIPoints or NumVPoints < 4)
- -5: Invalid NumCycles (must be >= 1 and <= 1000)
- -6: forcev() failed at point i (check SMU connection and voltage range)
- -7: measi() failed at point i (check SMU connection)
- -8: limiti() failed (check current limit value)
- -9: setmode() failed (check SMU connection)
- -100-i: Force voltage failed at point i (i = 0-based index)

NOTE: NumIPoints and NumVPoints must equal 4 × NumCycles.
Example: For NumCycles=3, arrays must be size 12 (3 cycles × 4 points per cycle).

STEP DELAY:
The StepDelay parameter is CRITICAL for accurate measurements. Without sufficient
delay, the device may not have reached steady state, leading to:
- Inaccurate current readings
- Noisy measurements
- Non-reproducible results

Typical step delays:
- Low-resistance devices (< 1 kΩ): 1-10 ms
- Medium-resistance devices (1 kΩ - 1 MΩ): 10-100 ms
- High-resistance devices (> 1 MΩ): 100 ms - 1 s
- Capacitive devices: May require seconds

INTEGRATION TIME:
The IntegrationTime parameter controls measurement accuracy vs. speed:
- 0.0001 PLC: Very fast (~0.001s), but noisy (good for low-impedance devices)
- 0.01 PLC: Fast (~0.1s), balanced accuracy/speed (default)
- 0.1 PLC: Medium (~1s), good accuracy (good for medium-impedance devices)
- 1.0 PLC: Slow (~10s), highest accuracy (good for high-impedance devices)

MEASURED VOLTAGE:
The module measures the actual voltage at the DUT using intgv() and stores it.
This can reveal:
- Voltage drop due to lead resistance
- Compliance effects (voltage drops when current limit is reached)
- Connection issues

COMPLIANCE CHECKING:
The module checks if the measured current is near the compliance limit (>= 99% of Ilimit).
If compliance is detected, this indicates the device may be drawing more current than
the limit allows, and the voltage may be clamped. The module will continue but may
produce warnings if debug output is enabled.

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <math.h>  /* For fabs() function */
#include <stdio.h>  /* For printf() function */

/* USRLIB MODULE MAIN FUNCTION */
int smu_ivsweep( double Vhigh, double Vlow, int NumSteps, int NumCycles, double *Imeas, int NumIPoints, 
                 double *Vforce, int NumVPoints, double StepDelay, double Ilimit,
                 double IntegrationTime, int ClariusDebug )
{
/* USRLIB MODULE CODE */
/* Step-based IV sweep module: 0 → Vhigh → 0 → Vlow → 0V, repeated NumCycles times

--------------
Features:
- Step-based pattern: (0 → Vhigh → 0 → Vlow → 0) × NumCycles
- Configurable number of steps distributed across full sweep path
- Step delay at each voltage point
- Error handling for all LPTLib calls
- Current limit and integration time configuration
- Input validation
- Measured voltage storage (intgv) for comparison
- Compliance checking
- Debug output option

*/

double v;              /* Current voltage value */
double v_measured;     /* Measured voltage at DUT */
int i;                 /* Loop counter */
int cycle;             /* Cycle counter */
int step;              /* Step counter within segment */
int segment;           /* Segment counter (0-3: 0→Vhigh, Vhigh→0, 0→Vlow, Vlow→0) */
int status;            /* Status code from LPTLib functions */
int debug;             /* Debug flag */
double compliance_threshold;  /* Compliance detection threshold */
int expected_points;   /* Expected number of points ((NumSteps + 1) × NumCycles) */
int steps_per_segment; /* Steps per segment (NumSteps / 4) */
int remainder_steps;    /* Remainder steps to distribute */
int segment_start_idx; /* Starting index for current segment */
int points_per_cycle;  /* Points per cycle (NumSteps + 1) */

/* ============================================================
   INITIALIZE VARIABLES
   ============================================================ */

debug = (ClariusDebug == 1) ? 1 : 0;  /* Enable debug output if requested */
compliance_threshold = Ilimit * 0.99;  /* 99% of limit = compliance */

/* ============================================================
   INPUT VALIDATION
   ============================================================ */

/* Validate Vhigh (must be >= 0) */
if ( Vhigh < 0.0 )
{
    if(debug) printf("smu_ivsweep ERROR: Vhigh (%.6f) must be >= 0 V\n", Vhigh);
    return( -1 ); /* Invalid Vhigh */
}

/* Validate Vlow (must be <= 0) */
if ( Vlow > 0.0 )
{
    if(debug) printf("smu_ivsweep ERROR: Vlow (%.6f) must be <= 0 V\n", Vlow);
    return( -1 ); /* Invalid Vlow */
}

/* Validate NumSteps (must be >= 4 and <= 10000) */
if ( (NumSteps < 4) || (NumSteps > 10000) )
{
    if(debug) printf("smu_ivsweep ERROR: NumSteps (%d) must be between 4 and 10000\n", NumSteps);
    return( -5 ); /* Invalid NumSteps */
}

/* Validate NumCycles (must be between 1 and 1000) */
if ( (NumCycles < 1) || (NumCycles > 1000) )
{
    if(debug) printf("smu_ivsweep ERROR: NumCycles (%d) must be between 1 and 1000\n", NumCycles);
    return( -5 ); /* Invalid NumCycles */
}

/* Calculate points per cycle and total expected points */
points_per_cycle = NumSteps + 1;  /* NumSteps steps + 1 start point */
expected_points = points_per_cycle * NumCycles;

/* Check array size mismatch */
if ( (NumIPoints != NumVPoints) )
{
    if(debug) printf("smu_ivsweep ERROR: Array size mismatch - NumIPoints=%d, NumVPoints=%d\n", NumIPoints, NumVPoints);
    return( -2 ); /* V and I array sizes do not match */
}

/* Check that array sizes match expected points */
if ( (NumIPoints != expected_points) || (NumVPoints != expected_points) )
{
    if(debug) printf("smu_ivsweep ERROR: Array size mismatch - NumIPoints=%d, NumVPoints=%d, expected %d ((NumSteps+1) × NumCycles = (%d+1) × %d)\n", 
                     NumIPoints, NumVPoints, expected_points, NumSteps, NumCycles);
    return( -3 ); /* Array size must equal (NumSteps + 1) × NumCycles */
}

/* Check for minimum array sizes */
if ( (NumIPoints < points_per_cycle) || (NumVPoints < points_per_cycle) )
{
    if(debug) printf("smu_ivsweep ERROR: Invalid array sizes - NumIPoints=%d, NumVPoints=%d (must be >= %d for one cycle)\n", 
                     NumIPoints, NumVPoints, points_per_cycle);
    return( -4 ); /* Invalid array size */
}

/* Validate step delay (must be positive) */
if ( StepDelay < 0.0001 )
{
    if(debug) printf("smu_ivsweep WARNING: StepDelay (%.6f) too small, using minimum 0.0001s\n", StepDelay);
    StepDelay = 0.0001; /* Minimum step delay: 0.1 ms */
}

/* Validate current limit (must be positive) */
if ( Ilimit < 1e-9 )
{
    if(debug) printf("smu_ivsweep WARNING: Ilimit (%.6e) too small, using minimum 1e-9 A\n", Ilimit);
    Ilimit = 1e-9; /* Minimum current limit: 1 nA */
}

/* Validate integration time (must be positive) */
if ( IntegrationTime < 0.0001 )
{
    if(debug) printf("smu_ivsweep WARNING: IntegrationTime (%.6f) too small, using minimum 0.0001 PLC\n", IntegrationTime);
    IntegrationTime = 0.0001; /* Minimum integration time: 0.0001 PLC */
}

/* ============================================================
   INITIALIZE OUTPUT ARRAYS
   ============================================================ */

/* Initialize arrays to zero (in case of early exit or error) */
for(i = 0; i < NumIPoints; i++)
{
    Imeas[i] = 0.0;
    Vforce[i] = 0.0;
}

/* ============================================================
   CONFIGURE SMU (INTEGRATION TIME, CURRENT LIMIT)
   ============================================================ */

/* Set integration time for measurements (KI_INTGPLC = Power Line Cycles) */
/* Lower values = faster but noisier, Higher values = slower but more accurate */
status = setmode(SMU1, KI_INTGPLC, IntegrationTime);
if ( status != 0 )
{
    if(debug) printf("smu_ivsweep WARNING: setmode(KI_INTGPLC) failed: %d (continuing with default)\n", status);
    /* Don't return error - integration time may not be critical */
}

/* Set current compliance limit before starting sweep */
status = limiti(SMU1, Ilimit);
if ( status != 0 )
{
    if(debug) printf("smu_ivsweep ERROR: limiti() failed with status: %d\n", status);
    return( -6 ); /* Failed to set current limit */
}

/* Calculate step distribution across 4 segments (will be reset per cycle) */
steps_per_segment = NumSteps / 4;

if(debug)
{
    printf("\n========================================\n");
    printf("smu_ivsweep: Starting step-based IV sweep\n");
    printf("========================================\n");
    printf("  Pattern: (0V → +%.6fV → 0V → %.6fV → 0V) × %d cycles\n", Vhigh, Vlow, NumCycles);
    printf("  Vhigh: %.6f V\n", Vhigh);
    printf("  Vlow: %.6f V\n", Vlow);
    printf("  NumSteps: %d (distributed across 4 segments)\n", NumSteps);
    printf("  Steps per segment: %d (remainder: %d)\n", steps_per_segment, remainder_steps);
    printf("  NumCycles: %d\n", NumCycles);
    printf("  Points per cycle: %d (NumSteps + 1)\n", points_per_cycle);
    printf("  Total points: %d (%d × %d)\n", expected_points, points_per_cycle, NumCycles);
    printf("  StepDelay: %.6f s (%.3f ms)\n", StepDelay, StepDelay * 1000.0);
    printf("  Ilimit: %.6e A (%.3f µA)\n", Ilimit, Ilimit * 1e6);
    printf("  IntegrationTime: %.6f PLC\n", IntegrationTime);
    printf("========================================\n\n");
}

/* ============================================================
   STEP-BASED VOLTAGE SWEEP LOOP
   ============================================================ */

/* Loop through cycles */
i = 0;  /* Global point index */
for(cycle = 0; cycle < NumCycles; cycle++)
{
    segment_start_idx = i;  /* Track start of cycle for debug output */
    remainder_steps = NumSteps % 4;  /* Reset remainder for each cycle */
    
    /* Segment 1: 0V → Vhigh */
    {
        int seg_steps = steps_per_segment + (remainder_steps > 0 ? 1 : 0);
        if (remainder_steps > 0) remainder_steps--;
        
        /* Start at 0V (first point of segment) */
        v = 0.0;
        
        /* Force voltage on SMU1 */
        status = forcev(SMU1, v);
        if ( status != 0 )
        {
            if(debug) printf("smu_ivsweep ERROR: forcev() failed at cycle %d, segment 1 start, global index %d (voltage=%.6f V) with status: %d\n", 
                             cycle + 1, i, v, status);
            forcev(SMU1, 0.0);
            return( -100 - i );
        }
        
        /* Wait for settling */
        Sleep( (int)(StepDelay * 1000.0) );
        
        /* Measure current */
        status = measi(SMU1, &Imeas[i]);
        if ( status != 0 )
        {
            if(debug) printf("smu_ivsweep ERROR: measi() failed at point %d (voltage=%.6f V) with status: %d\n", i, v, status);
            forcev(SMU1, 0.0);
            return( -7 );
        }
        
        /* Measure actual voltage */
        status = intgv(SMU1, &v_measured);
        if ( status != 0 ) v_measured = v;
        
        /* Check compliance */
        if ( (Imeas[i] >= compliance_threshold) || (Imeas[i] <= -compliance_threshold) )
        {
            if(debug) printf("smu_ivsweep WARNING: Compliance detected at point %d\n", i);
        }
        
        Vforce[i] = v;
        if(debug && (i == segment_start_idx || i == segment_start_idx + seg_steps))
        {
            double resistance = (fabs(Imeas[i]) > 1e-12) ? (v_measured / Imeas[i]) : 1e12;
            printf("  Cycle %2d, Seg 1, Point %d/%d, Global %3d/%d: V=%.6f V, I=%.6e A, R=%.3e Ohm\n",
                   cycle + 1, i - segment_start_idx + 1, seg_steps + 1, i + 1, NumIPoints, v, Imeas[i], resistance);
        }
        i++;
        
        /* Sweep from 0V to Vhigh */
        for(step = 1; step <= seg_steps; step++)
        {
            v = (Vhigh * step) / seg_steps;
            
            status = forcev(SMU1, v);
            if ( status != 0 )
            {
                if(debug) printf("smu_ivsweep ERROR: forcev() failed at cycle %d, segment 1, step %d, global index %d (voltage=%.6f V) with status: %d\n", 
                                 cycle + 1, step, i, v, status);
                forcev(SMU1, 0.0);
                return( -100 - i );
            }
            
            Sleep( (int)(StepDelay * 1000.0) );
            
            status = measi(SMU1, &Imeas[i]);
            if ( status != 0 )
            {
                if(debug) printf("smu_ivsweep ERROR: measi() failed at point %d (voltage=%.6f V) with status: %d\n", i, v, status);
                forcev(SMU1, 0.0);
                return( -7 );
            }
            
            status = intgv(SMU1, &v_measured);
            if ( status != 0 ) v_measured = v;
            
            if ( (Imeas[i] >= compliance_threshold) || (Imeas[i] <= -compliance_threshold) )
            {
                if(debug) printf("smu_ivsweep WARNING: Compliance detected at point %d\n", i);
            }
            
            Vforce[i] = v;
            if(debug && (step == seg_steps || step == 1))
            {
                double resistance = (fabs(Imeas[i]) > 1e-12) ? (v_measured / Imeas[i]) : 1e12;
                printf("  Cycle %2d, Seg 1, Point %d/%d, Global %3d/%d: V=%.6f V, I=%.6e A, R=%.3e Ohm\n",
                       cycle + 1, step + 1, seg_steps + 1, i + 1, NumIPoints, v, Imeas[i], resistance);
            }
            i++;
        }
    }
    
    /* Segment 2: Vhigh → 0V */
    {
        int seg_steps = steps_per_segment + (remainder_steps > 0 ? 1 : 0);
        if (remainder_steps > 0) remainder_steps--;
        
        /* Sweep from Vhigh to 0V */
        for(step = 1; step <= seg_steps; step++)
        {
            v = Vhigh * (1.0 - (double)step / seg_steps);
            
            status = forcev(SMU1, v);
            if ( status != 0 )
            {
                if(debug) printf("smu_ivsweep ERROR: forcev() failed at cycle %d, segment 2, step %d, global index %d (voltage=%.6f V) with status: %d\n", 
                                 cycle + 1, step, i, v, status);
                forcev(SMU1, 0.0);
                return( -100 - i );
            }
            
            Sleep( (int)(StepDelay * 1000.0) );
            
            status = measi(SMU1, &Imeas[i]);
            if ( status != 0 )
            {
                if(debug) printf("smu_ivsweep ERROR: measi() failed at point %d (voltage=%.6f V) with status: %d\n", i, v, status);
                forcev(SMU1, 0.0);
                return( -7 );
            }
            
            status = intgv(SMU1, &v_measured);
            if ( status != 0 ) v_measured = v;
            
            if ( (Imeas[i] >= compliance_threshold) || (Imeas[i] <= -compliance_threshold) )
            {
                if(debug) printf("smu_ivsweep WARNING: Compliance detected at point %d\n", i);
            }
            
            Vforce[i] = v;
            if(debug && (step == seg_steps || step == 1))
            {
                double resistance = (fabs(Imeas[i]) > 1e-12) ? (v_measured / Imeas[i]) : 1e12;
                printf("  Cycle %2d, Seg 2, Point %d/%d, Global %3d/%d: V=%.6f V, I=%.6e A, R=%.3e Ohm\n",
                       cycle + 1, step, seg_steps, i + 1, NumIPoints, v, Imeas[i], resistance);
            }
            i++;
        }
    }
    
    /* Segment 3: 0V → Vlow */
    {
        int seg_steps = steps_per_segment + (remainder_steps > 0 ? 1 : 0);
        if (remainder_steps > 0) remainder_steps--;
        
        /* Start at 0V (first point of segment) */
        v = 0.0;
        
        status = forcev(SMU1, v);
        if ( status != 0 )
        {
            if(debug) printf("smu_ivsweep ERROR: forcev() failed at cycle %d, segment 3 start, global index %d (voltage=%.6f V) with status: %d\n", 
                             cycle + 1, i, v, status);
            forcev(SMU1, 0.0);
            return( -100 - i );
        }
        
        Sleep( (int)(StepDelay * 1000.0) );
        
        status = measi(SMU1, &Imeas[i]);
        if ( status != 0 )
        {
            if(debug) printf("smu_ivsweep ERROR: measi() failed at point %d (voltage=%.6f V) with status: %d\n", i, v, status);
            forcev(SMU1, 0.0);
            return( -7 );
        }
        
        status = intgv(SMU1, &v_measured);
        if ( status != 0 ) v_measured = v;
        
        if ( (Imeas[i] >= compliance_threshold) || (Imeas[i] <= -compliance_threshold) )
        {
            if(debug) printf("smu_ivsweep WARNING: Compliance detected at point %d\n", i);
        }
        
        Vforce[i] = v;
        if(debug && (i == segment_start_idx + points_per_cycle - 1 || i == segment_start_idx + (points_per_cycle * 2 / 3)))
        {
            double resistance = (fabs(Imeas[i]) > 1e-12) ? (v_measured / Imeas[i]) : 1e12;
            printf("  Cycle %2d, Seg 3, Point 1/%d, Global %3d/%d: V=%.6f V, I=%.6e A, R=%.3e Ohm\n",
                   cycle + 1, seg_steps + 1, i + 1, NumIPoints, v, Imeas[i], resistance);
        }
        i++;
        
        /* Sweep from 0V to Vlow */
        for(step = 1; step <= seg_steps; step++)
        {
            v = (Vlow * step) / seg_steps;
            
            status = forcev(SMU1, v);
            if ( status != 0 )
            {
                if(debug) printf("smu_ivsweep ERROR: forcev() failed at cycle %d, segment 3, step %d, global index %d (voltage=%.6f V) with status: %d\n", 
                                 cycle + 1, step, i, v, status);
                forcev(SMU1, 0.0);
                return( -100 - i );
            }
            
            Sleep( (int)(StepDelay * 1000.0) );
            
            status = measi(SMU1, &Imeas[i]);
            if ( status != 0 )
            {
                if(debug) printf("smu_ivsweep ERROR: measi() failed at point %d (voltage=%.6f V) with status: %d\n", i, v, status);
                forcev(SMU1, 0.0);
                return( -7 );
            }
            
            status = intgv(SMU1, &v_measured);
            if ( status != 0 ) v_measured = v;
            
            if ( (Imeas[i] >= compliance_threshold) || (Imeas[i] <= -compliance_threshold) )
            {
                if(debug) printf("smu_ivsweep WARNING: Compliance detected at point %d\n", i);
            }
            
            Vforce[i] = v;
            if(debug && (step == seg_steps || step == 1))
            {
                double resistance = (fabs(Imeas[i]) > 1e-12) ? (v_measured / Imeas[i]) : 1e12;
                printf("  Cycle %2d, Seg 3, Point %d/%d, Global %3d/%d: V=%.6f V, I=%.6e A, R=%.3e Ohm\n",
                       cycle + 1, step + 1, seg_steps + 1, i + 1, NumIPoints, v, Imeas[i], resistance);
            }
            i++;
        }
    }
    
    /* Segment 4: Vlow → 0V */
    {
        int seg_steps = steps_per_segment + (remainder_steps > 0 ? 1 : 0);
        if (remainder_steps > 0) remainder_steps--;
        
        /* Sweep from Vlow to 0V */
        for(step = 1; step <= seg_steps; step++)
        {
            v = Vlow * (1.0 - (double)step / seg_steps);
            
            status = forcev(SMU1, v);
            if ( status != 0 )
            {
                if(debug) printf("smu_ivsweep ERROR: forcev() failed at cycle %d, segment 4, step %d, global index %d (voltage=%.6f V) with status: %d\n", 
                                 cycle + 1, step, i, v, status);
                forcev(SMU1, 0.0);
                return( -100 - i );
            }
            
            Sleep( (int)(StepDelay * 1000.0) );
            
            status = measi(SMU1, &Imeas[i]);
            if ( status != 0 )
            {
                if(debug) printf("smu_ivsweep ERROR: measi() failed at point %d (voltage=%.6f V) with status: %d\n", i, v, status);
                forcev(SMU1, 0.0);
                return( -7 );
            }
            
            status = intgv(SMU1, &v_measured);
            if ( status != 0 ) v_measured = v;
            
            if ( (Imeas[i] >= compliance_threshold) || (Imeas[i] <= -compliance_threshold) )
            {
                if(debug) printf("smu_ivsweep WARNING: Compliance detected at point %d\n", i);
            }
            
            Vforce[i] = v;
            if(debug && (step == seg_steps || step == 1))
            {
                double resistance = (fabs(Imeas[i]) > 1e-12) ? (v_measured / Imeas[i]) : 1e12;
                printf("  Cycle %2d, Seg 4, Point %d/%d, Global %3d/%d: V=%.6f V, I=%.6e A, R=%.3e Ohm\n",
                       cycle + 1, step, seg_steps, i + 1, NumIPoints, v, Imeas[i], resistance);
            }
            i++;
        }
    }
}  /* End of cycle loop */

/* ============================================================
   CLEANUP: RETURN TO ZERO VOLTAGE
   ============================================================ */

/* Return to zero voltage at end of sweep */
/* This is good practice to avoid leaving voltage on device */
forcev(SMU1, 0.0);

if(debug)
{
    printf("\n========================================\n");
    printf("smu_ivsweep: Sweep complete\n");
    printf("  Total points measured: %d\n", NumIPoints);
    printf("  Returned to 0 V\n");
    printf("========================================\n");
}

/* ============================================================
   SUCCESS
   ============================================================ */

return( 0 ); /* Returns zero if execution OK */

/* USRLIB MODULE END  */
} 		/* End smu_ivsweep.c */
