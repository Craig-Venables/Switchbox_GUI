/* USRLIB MODULE INFORMATION

	MODULE NAME: SMU_BiasTimedRead
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 6
	ARGUMENTS:
		Vforce,	double,	Input,	0.2,	-200,	200
		Duration_s,	double,	Input,	10.0,	0.001,	3600
		SampleInterval_s,	double,	Input,	0.02,	0.001,	10.0
		Ilimit,	double,	Input,	0.0001,	1e-9,	1.0
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumPoints,	int,	Input,	500,	1,	100000
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

Pattern: forcev(Vforce) -> loop NumPoints times: Sleep(SampleInterval_s), measi() -> forcev(0)

- Vforce: DC voltage to apply (V), range -200 to 200
- Duration_s: Total time to hold bias (s). NumPoints × SampleInterval_s should not exceed this.
- SampleInterval_s: Time between current samples (s). Minimum 0.001 (1 ms) enforced.
- Ilimit: Current compliance limit (A)
- Imeas: Output array of measured currents (A)
- NumPoints: Number of current samples to take (size of Imeas)

Return codes: 0 = OK, -1 = invalid params, -5 = forcev failed, -6 = measi failed, -7 = limiti failed

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <Windows.h>

/* USRLIB MODULE MAIN FUNCTION */
int SMU_BiasTimedRead( double Vforce, double Duration_s, double SampleInterval_s, double Ilimit, double *Imeas, int NumPoints )
{
/* USRLIB MODULE CODE */
/* Bias Timed Read module

--------------

Applies Vforce for the duration, samples current every SampleInterval_s,
fills Imeas[0..NumPoints-1]. At end ramps to 0 V.

*/

int i, status;
int delay_ms;

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

/* Pre-calculate delay in milliseconds (minimum 1 ms for Windows Sleep) */
delay_ms = (int)(SampleInterval_s * 1000.0 + 0.5);
if ( delay_ms < 1 ) delay_ms = 1;

/* Initialize output array to zero */
for ( i = 0; i < NumPoints; i++ )
{
    Imeas[i] = 0.0;
}

/* Set current compliance limit */
status = limiti(SMU1, Ilimit);
if ( status != 0 )
{
    forcev(SMU1, 0.0);
    return( -7 );  /* limiti failed */
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

/* Sample current at each interval */
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
} 		/* End SMU_BiasTimedRead.c */
