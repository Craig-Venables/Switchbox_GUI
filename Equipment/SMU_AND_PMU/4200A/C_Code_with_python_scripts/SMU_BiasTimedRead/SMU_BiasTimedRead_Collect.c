/* USRLIB MODULE INFORMATION

	MODULE NAME: SMU_BiasTimedRead_Collect
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 6
	ARGUMENTS:
		Duration_s,	double,	Input,	10.0,	0.001,	3600
		SampleInterval_s,	double,	Input,	0.02,	0.001,	10.0
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumPoints,	int,	Input,	500,	1,	100000
		Timestamps,	D_ARRAY_T,	Output,	,	,
		NumPointsTimestamps,	int,	Input,	500,	1,	100000
	INCLUDES:
#include "keithley.h"
#include <Windows.h>
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION

SMU Bias Timed Read - Collect (Phase 2: sample loop, then ramp down)
====================================================================

Assumes SMU_BiasTimedRead_Start has already been called (bias is applied).
Samples current at SampleInterval_s, fills Imeas, then ramps to 0 V.

Call after host has received Start return and started laser (or other sync).

- Duration_s: Not used; kept for parameter compatibility. NumPoints * SampleInterval_s defines length.
- SampleInterval_s: Time between current samples (s). Minimum 0.001 (1 ms).
- Imeas: Output array of measured currents (A)
- NumPoints: Number of current samples
- Timestamps: Output array of timestamps (s), relative to measurement start
- NumPointsTimestamps: Size of Timestamps array (should equal NumPoints)

Return codes: 0 = OK, -1 = invalid params, -6 = measi failed, -5 = forcev failed

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <Windows.h>

/* USRLIB MODULE MAIN FUNCTION */
int SMU_BiasTimedRead_Collect( double Duration_s, double SampleInterval_s, double *Imeas, int NumPoints, double *Timestamps, int NumPointsTimestamps )
{
/* USRLIB MODULE CODE */
int i, status;
int delay_ms;
LARGE_INTEGER freq, start_time, current_time;
double time_elapsed_s;

/* Validate input parameters */
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

/* Pre-calculate delay in milliseconds (minimum 1 ms for Windows Sleep) */
delay_ms = (int)(SampleInterval_s * 1000.0 + 0.5);
if ( delay_ms < 1 ) delay_ms = 1;

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

/* Capture start time (beginning of sampling loop) */
QueryPerformanceCounter(&start_time);

/* Sample current at each interval (bias and setmode already applied by Start) */
for ( i = 0; i < NumPoints; i++ )
{
    Sleep(delay_ms);
    
    /* Capture timestamp for this sample */
    QueryPerformanceCounter(&current_time);
    time_elapsed_s = (double)(current_time.QuadPart - start_time.QuadPart) / (double)freq.QuadPart;
    Timestamps[i] = time_elapsed_s;
    
    status = measi(SMU1, &Imeas[i]);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -6 );  /* measi failed */
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
} 		/* End SMU_BiasTimedRead_Collect.c */
