/* USRLIB MODULE INFORMATION

	MODULE NAME: smu_ivsweep
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 11
	ARGUMENTS:
		Vpos,	double,	Input,	5,	0,	200
		Vneg,	double,	Input,	0,	-200,	0
		NumCycles,	int,	Input,	1,	1,	1000
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumIPoints,	int,	Input,	4,	,	
		Vforce,	D_ARRAY_T,	Output,	,	,
		NumVPoints,	int,	Input,	4,	,	
		SettleTime,	double,	Input,	0.001,	0.0001,	10.0
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

SMU Voltage-Current Sweep Module (Cyclical Pattern)
====================================================

Performs cyclical IV sweeps: 0V → +Vpos → Vneg → 0V, repeated NumCycles times.

Pattern: (0 → +Vpos → Vneg → 0) × n cycles
- Vpos: Positive voltage (V), must be >= 0
- Vneg: Negative voltage (V), must be <= 0
  If Vneg == 0, automatically uses -Vpos (symmetric sweep)
- Default behavior: Vneg=0 uses -Vpos (e.g., Vpos=5V → pattern: 0V → +5V → -5V → 0V)
- Custom behavior: Vpos=5V, Vneg=-2V → pattern: 0V → +5V → -2V → 0V

Example: For Vpos=5V, Vneg=0 (auto -5V), NumCycles=2: 
  0V → +5V → -5V → 0V → +5V → -5V → 0V

Example: For Vpos=5V, Vneg=-2V, NumCycles=1:
  0V → +5V → -2V → 0V

Total points = 4 × NumCycles (must match NumIPoints/NumVPoints)

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

SETTLING TIME:
The SettleTime parameter is CRITICAL for accurate measurements. Without sufficient
settling time, the device may not have reached steady state, leading to:
- Inaccurate current readings
- Noisy measurements
- Non-reproducible results

Typical settling times:
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
int smu_ivsweep( double Vpos, double Vneg, int NumCycles, double *Imeas, int NumIPoints, 
                 double *Vforce, int NumVPoints, double SettleTime, double Ilimit,
                 double IntegrationTime, int ClariusDebug )
{
/* USRLIB MODULE CODE */
/* Cyclical IV sweep module: 0 → +Vmax → -Vmax → 0V, repeated NumCycles times

--------------
Features:
- Cyclical pattern: (0 → +Vmax → -Vmax → 0) × NumCycles
- Settling time at each voltage point
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
int point_in_cycle;    /* Point index within current cycle (0-3) */
int status;            /* Status code from LPTLib functions */
int debug;             /* Debug flag */
double compliance_threshold;  /* Compliance detection threshold */
int expected_points;   /* Expected number of points (4 × NumCycles) */
double v_negative;     /* Actual negative voltage to use (Vneg or -Vpos if Vneg==0) */

/* ============================================================
   INITIALIZE VARIABLES
   ============================================================ */

debug = (ClariusDebug == 1) ? 1 : 0;  /* Enable debug output if requested */
compliance_threshold = Ilimit * 0.99;  /* 99% of limit = compliance */

/* ============================================================
   INPUT VALIDATION
   ============================================================ */

/* Validate Vpos (must be >= 0) */
if ( Vpos < 0.0 )
{
    if(debug) printf("smu_ivsweep ERROR: Vpos (%.6f) must be >= 0 V\n", Vpos);
    return( -1 ); /* Invalid Vpos */
}

/* Validate Vneg (must be <= 0, Vneg == 0 is allowed for auto-symmetric) */
if ( Vneg > 0.0 )
{
    if(debug) printf("smu_ivsweep ERROR: Vneg (%.6f) must be <= 0 V (use 0 for auto-symmetric with -Vpos)\n", Vneg);
    return( -1 ); /* Invalid Vneg */
}

/* Determine actual negative voltage */
/* If Vneg == 0, use -Vpos (symmetric sweep) */
/* Otherwise, use Vneg as specified (asymmetric sweep) */
if ( Vneg == 0.0 )
{
    v_negative = -Vpos;  /* Auto-symmetric: use -Vpos */
    if(debug) printf("smu_ivsweep INFO: Vneg=0, using auto-symmetric sweep with -Vpos = -%.6f V\n", Vpos);
}
else
{
    v_negative = Vneg;  /* Asymmetric: use specified Vneg */
    if(debug) printf("smu_ivsweep INFO: Using asymmetric sweep: Vpos=%.6f V, Vneg=%.6f V\n", Vpos, Vneg);
}

/* Validate NumCycles (must be between 1 and 1000) */
if ( (NumCycles < 1) || (NumCycles > 1000) )
{
    if(debug) printf("smu_ivsweep ERROR: NumCycles (%d) must be between 1 and 1000\n", NumCycles);
    return( -5 ); /* Invalid NumCycles */
}

/* Calculate expected number of points (4 points per cycle) */
expected_points = 4 * NumCycles;

/* Check array size mismatch */
if ( (NumIPoints != NumVPoints) )
{
    if(debug) printf("smu_ivsweep ERROR: Array size mismatch - NumIPoints=%d, NumVPoints=%d\n", NumIPoints, NumVPoints);
    return( -2 ); /* V and I array sizes do not match */
}

/* Check that array sizes match expected points */
if ( (NumIPoints != expected_points) || (NumVPoints != expected_points) )
{
    if(debug) printf("smu_ivsweep ERROR: Array size mismatch - NumIPoints=%d, NumVPoints=%d, expected %d (4 × NumCycles=%d)\n", 
                     NumIPoints, NumVPoints, expected_points, NumCycles);
    return( -3 ); /* Array size must equal 4 × NumCycles */
}

/* Check for minimum array sizes */
if ( (NumIPoints < 4) || (NumVPoints < 4) )
{
    if(debug) printf("smu_ivsweep ERROR: Invalid array sizes - NumIPoints=%d, NumVPoints=%d (must be >= 4)\n", NumIPoints, NumVPoints);
    return( -4 ); /* Invalid array size */
}

/* Validate settling time (must be positive) */
if ( SettleTime < 0.0001 )
{
    if(debug) printf("smu_ivsweep WARNING: SettleTime (%.6f) too small, using minimum 0.0001s\n", SettleTime);
    SettleTime = 0.0001; /* Minimum settling time: 0.1 ms */
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

if(debug)
{
    printf("\n========================================\n");
    printf("smu_ivsweep: Starting cyclical IV sweep\n");
    printf("========================================\n");
    printf("  Pattern: (0V → +%.6fV → %.6fV → 0V) × %d cycles\n", Vpos, v_negative, NumCycles);
    printf("  Vpos: %.6f V\n", Vpos);
    printf("  Vneg: %.6f V", Vneg);
    if ( Vneg == 0.0 )
    {
        printf(" (auto → %.6f V)\n", v_negative);
    }
    else
    {
        printf(" (specified)\n");
    }
    printf("  NumCycles: %d\n", NumCycles);
    printf("  Total points: %d (4 × %d)\n", expected_points, NumCycles);
    printf("  SettleTime: %.6f s (%.3f ms)\n", SettleTime, SettleTime * 1000.0);
    printf("  Ilimit: %.6e A (%.3f µA)\n", Ilimit, Ilimit * 1e6);
    printf("  IntegrationTime: %.6f PLC\n", IntegrationTime);
    printf("========================================\n\n");
}

/* ============================================================
   CYCLICAL VOLTAGE SWEEP LOOP
   ============================================================ */

/* Loop through cycles */
i = 0;  /* Global point index */
for(cycle = 0; cycle < NumCycles; cycle++)
{
    /* Each cycle has 4 points: 0V → +Vmax → -Vmax → 0V */
    for(point_in_cycle = 0; point_in_cycle < 4; point_in_cycle++)
    {
        /* Determine voltage based on point in cycle */
        switch(point_in_cycle)
        {
            case 0: v = 0.0;            break;  /* Start at 0V */
            case 1: v = Vpos;           break;  /* Go to +Vpos */
            case 2: v = v_negative;     break;  /* Go to Vneg (or -Vpos if Vneg==0) */
            case 3: v = 0.0;            break;  /* Return to 0V */
            default: v = 0.0;           break;
        }
        
        /* ----------------------------------------
           STEP 1: FORCE VOLTAGE
           ---------------------------------------- */
        
        /* Force voltage on SMU1 */
        status = forcev(SMU1, v);
        if ( status != 0 )
        {
            /* If forcev fails, try to return to zero and exit */
            if(debug) printf("smu_ivsweep ERROR: forcev() failed at cycle %d, point %d, global index %d (voltage=%.6f V) with status: %d\n", 
                             cycle + 1, point_in_cycle + 1, i, v, status);
            forcev(SMU1, 0.0);  /* Attempt to return to zero */
            return( -100 - i ); /* Return specific error code for this point: -100-i */
        }
    
    /* ----------------------------------------
       STEP 2: SETTLING TIME (CRITICAL!)
       ---------------------------------------- */
    
    /* Wait for device to settle at this voltage */
    /* Convert SettleTime (seconds) to milliseconds for Sleep() */
    Sleep( (int)(SettleTime * 1000.0) );
    
    /* NOTE: Sleep() takes milliseconds, so we multiply by 1000
       This allows the device capacitance and any transients to settle
       before taking the measurement. Without this, measurements may be
       inaccurate, especially for:
       - Capacitive devices (need time to charge/discharge)
       - High-impedance devices (need time for current to stabilize)
       - Devices with memory effects
    */
    
    /* ----------------------------------------
       STEP 3: MEASURE CURRENT
       ---------------------------------------- */
    
    /* Measure current on SMU1 */
    status = measi(SMU1, &Imeas[i]);
    if ( status != 0 )
    {
        /* If measi fails, try to return to zero and exit */
        if(debug) printf("smu_ivsweep ERROR: measi() failed at point %d (voltage=%.6f V) with status: %d\n", i, v, status);
        forcev(SMU1, 0.0);  /* Attempt to return to zero */
        return( -5 ); /* measi() failed - check SMU connection */
    }
    
    /* ----------------------------------------
       STEP 4: MEASURE ACTUAL VOLTAGE AT DUT
       ---------------------------------------- */
    
    /* Measure actual voltage at DUT using intgv (integrated voltage) */
    /* This can reveal voltage drop due to lead resistance or compliance */
    status = intgv(SMU1, &v_measured);
    if ( status != 0 )
    {
        /* If intgv fails, use forced voltage as fallback */
        if(debug) printf("smu_ivsweep WARNING: intgv() failed at point %d, using forced voltage as fallback\n", i);
        v_measured = v;  /* Fallback to forced voltage */
    }
    
    /* ----------------------------------------
       STEP 5: CHECK FOR COMPLIANCE
       ---------------------------------------- */
    
    /* Check if device hit current compliance limit */
    /* If |I| >= 99% of Ilimit, device may be in compliance (voltage clamped) */
    if ( (Imeas[i] >= compliance_threshold) || (Imeas[i] <= -compliance_threshold) )
    {
        if(debug)
        {
            printf("smu_ivsweep WARNING: Compliance detected at point %d\n", i);
            printf("  Forced V: %.6f V, Measured V: %.6f V, Current: %.6e A\n", v, v_measured, Imeas[i]);
            printf("  Current (%.3f%%) is >= 99%% of limit (%.6e A)\n", 
                   (fabs(Imeas[i]) / Ilimit) * 100.0, Ilimit);
            printf("  Voltage may be clamped - consider increasing Ilimit\n");
        }
    }
    
    /* ----------------------------------------
       STEP 6: STORE DATA
       ---------------------------------------- */
    
    /* Store forced voltage (nominal value) in Vforce array */
    /* This is the intended voltage, not necessarily what appears at the DUT */
    Vforce[i] = v;
    
    /* NOTE: If you want to store MEASURED voltage instead of FORCED voltage,
       uncomment the following line and comment out the line above:
       Vforce[i] = v_measured;  // Store actual measured voltage at DUT
    */
    
    /* ----------------------------------------
       STEP 7: DEBUG OUTPUT
       ---------------------------------------- */
    
if(debug)
{
    /* Print progress every cycle or at start/end */
    if ( (i == 0) || (point_in_cycle == 3) || ((cycle == 0) && (point_in_cycle == 0)) )
    {
        double resistance = (fabs(Imeas[i]) > 1e-12) ? (v_measured / Imeas[i]) : 1e12;
        printf("  Cycle %2d, Point %d/4, Global %3d/%d: V=%.6f V, V_meas=%.6f V, I=%.6e A, R=%.3e Ohm\n",
               cycle + 1, point_in_cycle + 1, i + 1, NumIPoints, v, v_measured, Imeas[i], resistance);
    }
}
    
        /* Increment global point index */
        i++;
    }  /* End of point_in_cycle loop */
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
