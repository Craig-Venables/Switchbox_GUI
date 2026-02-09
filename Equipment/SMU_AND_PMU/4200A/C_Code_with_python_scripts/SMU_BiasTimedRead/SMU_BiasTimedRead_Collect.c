/* USRLIB MODULE INFORMATION

	MODULE NAME: SMU_BiasTimedRead_Collect
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 4
	ARGUMENTS:
		Duration_s,	double,	Input,	10.0,	0.001,	3600
		SampleInterval_s,	double,	Input,	0.02,	0.001,	10.0
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumPoints,	int,	Input,	500,	1,	100000
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

Return codes: 0 = OK, -1 = invalid params, -6 = measi failed, -5 = forcev failed

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <Windows.h>

/* USRLIB MODULE MAIN FUNCTION */
int SMU_BiasTimedRead_Collect( double Duration_s, double SampleInterval_s, double *Imeas, int NumPoints )
{
/* USRLIB MODULE CODE */
int i, status;
int delay_ms;

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

/* Pre-calculate delay in milliseconds (minimum 1 ms for Windows Sleep) */
delay_ms = (int)(SampleInterval_s * 1000.0 + 0.5);
if ( delay_ms < 1 ) delay_ms = 1;

/* Initialize output array to zero */
for ( i = 0; i < NumPoints; i++ )
{
    Imeas[i] = 0.0;
}

/* Sample current at each interval (bias and setmode already applied by Start) */
for ( i = 0; i < NumPoints; i++ )
{
    Sleep(delay_ms);
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
