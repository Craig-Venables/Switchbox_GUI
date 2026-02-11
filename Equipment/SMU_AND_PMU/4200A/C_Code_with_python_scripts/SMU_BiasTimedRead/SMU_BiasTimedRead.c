/* USRLIB MODULE INFORMATION

	MODULE NAME: SMU_BiasTimedRead
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 9
	ARGUMENTS:
		Vforce,	double,	Input,	0.2,	-200,	200
		Duration_s,	double,	Input,	10.0,	0.001,	3600
		SampleInterval_s,	double,	Input,	0.02,	0.001,	10.0
		Ilimit,	double,	Input,	0.0001,	1e-9,	1.0
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumPoints,	int,	Input,	500,	1,	100000
		Timestamps,	D_ARRAY_T,	Output,	,	,
		NumPointsTimestamps,	int,	Input,	500,	1,	100000
		Irange_A,	double,	Input,	0.0,	0.0,	1.0
	INCLUDES:
#include "keithley.h"
#include <Windows.h>
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION

SMU Bias Timed Read Module
==========================

Applies a constant voltage (bias) for a fixed duration and samples current
at a fixed interval. Used for optical+read tests where the host coordinates
laser pulsing while the instrument collects current data.

Pattern: forcev(Vforce) -> measure continuously for Duration_s (max NumPoints samples) -> forcev(0)
        Samples are taken at intervals of approximately SampleInterval_s, but measurement stops
        when Duration_s is reached (or NumPoints limit hit). This ensures exact duration control
        while maximizing the number of points collected.

- Vforce: DC voltage to apply (V), range -200 to 200
- Duration_s: Total time to hold bias and measure (s). Measurement stops when this duration is reached.
- SampleInterval_s: Target time between current samples (s). Minimum 0.001 (1 ms) enforced.
              Actual interval may be slightly longer due to measi() overhead, but measurement
              will continue until Duration_s is reached to maximize points collected.
- Ilimit: Current compliance limit (A)
- Imeas: Output array of measured currents (A), up to NumPoints samples
- NumPoints: Maximum number of samples (safety limit, prevents array overflow)
- Timestamps: Output array of timestamps (s), relative to measurement start
- NumPointsTimestamps: Size of Timestamps array (should equal NumPoints)
- Irange_A: Current measurement range (A). 0 = auto (instrument chooses); >0 = fixed range for faster
            uniform sampling and/or better accuracy (e.g. 1e-6 = 1 uA). Must be <= Ilimit if set.

Return codes: 0 = OK, -1 = invalid params, -5 = forcev failed, -6 = measi failed, -7 = limiti failed

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <Windows.h>

/* USRLIB MODULE MAIN FUNCTION */
int SMU_BiasTimedRead( double Vforce, double Duration_s, double SampleInterval_s, double Ilimit, double *Imeas, int NumPoints, double *Timestamps, int NumPointsTimestamps, double Irange_A )
{
/* USRLIB MODULE CODE */
/* Bias Timed Read module

--------------

Applies Vforce and measures current continuously for Duration_s seconds.
Samples are taken at intervals of approximately SampleInterval_s, but measurement
stops when Duration_s is reached (or NumPoints limit is hit), ensuring exact
duration control while maximizing points collected.
Fills Imeas[0..n-1] and Timestamps[0..n-1] where n <= NumPoints is the actual
number of samples collected. At end ramps to 0 V.

*/

int i, status;
int check_interval_ms;
LARGE_INTEGER freq, start_time, current_time;
double time_elapsed_s;
double next_sample_target_s;

/* Validate input parameters */
if ( Duration_s <= 0.0 || Duration_s > 3600.0 )
{
    return( -1 );  /* Invalid duration */
}
if ( SampleInterval_s < 0.001 )
{
    SampleInterval_s = 0.001;  /* Minimum 1 ms for Sleep() */
}
if ( SampleInterval_s > 10.0 )
{
    return( -1 );  /* Invalid sample interval */
}
if ( NumPoints < 1 || NumPoints > 100000 )
{
    return( -1 );  /* Invalid NumPoints */
}
if ( NumPointsTimestamps < 1 || NumPointsTimestamps > 100000 )
{
    return( -1 );  /* Invalid NumPointsTimestamps */
}
if ( NumPointsTimestamps != NumPoints )
{
    return( -1 );  /* Timestamps array size must match NumPoints */
}

/* Pre-calculate check interval for duration monitoring (check every 10ms or SampleInterval, whichever is smaller) */
check_interval_ms = (int)(SampleInterval_s * 1000.0 + 0.5);
if ( check_interval_ms < 1 ) check_interval_ms = 1;
if ( check_interval_ms > 10 ) check_interval_ms = 10;  /* Check at least every 10ms to catch Duration_s accurately */

/* Initialize output arrays to zero */
for ( i = 0; i < NumPoints; i++ )
{
    Imeas[i] = 0.0;
    Timestamps[i] = 0.0;
}

/* Get high-resolution timer frequency */
QueryPerformanceFrequency(&freq);
if ( freq.QuadPart == 0 )
{
    /* Fallback: use low-resolution timer if QPC not available */
    freq.QuadPart = 1000;  /* Assume 1 ms resolution */
}

/* Set current compliance limit */
status = limiti(SMU1, Ilimit);
if ( status != 0 )
{
    forcev(SMU1, 0.0);
    return( -7 );  /* limiti failed */
}

/* Optional: fix current measurement range. Irange_A > 0: set fixed range (faster uniform sampling
   at high R, better accuracy when chosen to match expected current). Irange_A == 0: auto range. */
if ( Irange_A > 0.0 )
{
    double irange = Irange_A;
    if ( irange > Ilimit )
        irange = Ilimit;   /* Do not set range above compliance */
    status = rangei(SMU1, irange);
    /* Ignore rangei failure; instrument may not support or may use auto-range */
}

/* Optional: set fast integration for sampling (0.01 PLC) */
status = setmode(SMU1, KI_INTGPLC, 0.01);
/* Ignore setmode failure; continue with default */

/* Apply bias voltage */
status = forcev(SMU1, Vforce);
if ( status != 0 )
{
    forcev(SMU1, 0.0);
    return( -5 );  /* forcev failed */
}

/* Capture start time (after bias is applied) */
QueryPerformanceCounter(&start_time);

/* Measure first point immediately (no initial delay) */
i = 0;
QueryPerformanceCounter(&current_time);
time_elapsed_s = (double)(current_time.QuadPart - start_time.QuadPart) / (double)freq.QuadPart;
Timestamps[i] = time_elapsed_s;

status = measi(SMU1, &Imeas[i]);
if ( status != 0 )
{
    forcev(SMU1, 0.0);
    return( -6 );  /* measi failed */
}
i++;

/* Continue measuring until Duration_s is reached or NumPoints limit hit */
while ( i < NumPoints )
{
    /* Calculate when next sample should be taken (based on SampleInterval_s) */
    next_sample_target_s = (double)i * SampleInterval_s;
    
    /* Sleep in small increments until it's time for next sample or Duration_s is reached */
    while ( 1 )
    {
        QueryPerformanceCounter(&current_time);
        time_elapsed_s = (double)(current_time.QuadPart - start_time.QuadPart) / (double)freq.QuadPart;
        
        /* Stop if Duration_s has been reached */
        if ( time_elapsed_s >= Duration_s )
        {
            break;  /* Exit inner loop, will exit outer loop too */
        }
        
        /* Check if it's time for the next sample */
        if ( time_elapsed_s >= next_sample_target_s )
        {
            /* Time to take next sample */
            Timestamps[i] = time_elapsed_s;
            status = measi(SMU1, &Imeas[i]);
            if ( status != 0 )
            {
                forcev(SMU1, 0.0);
                return( -6 );  /* measi failed */
            }
            i++;
            break;  /* Exit inner loop to recalculate next_sample_target_s for next iteration */
        }
        
        /* Sleep a small amount before checking again */
        Sleep(check_interval_ms);
    }
    
    /* Check if Duration_s has been reached (exit outer loop) */
    if ( time_elapsed_s >= Duration_s )
    {
        break;  /* Duration reached, stop measuring */
    }
}

/* Ramp to 0 V and leave output safe */
status = forcev(SMU1, 0.0);
if ( status != 0 )
{
    return( -5 );
}

return( 0 ); /* Returns zero if execution Ok.*/

/* USRLIB MODULE END  */
} 		/* End SMU_BiasTimedRead.c */
