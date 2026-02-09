/* USRLIB MODULE INFORMATION

	MODULE NAME: SMU_BiasTimedRead_Start
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 2
	ARGUMENTS:
		Vforce,	double,	Input,	0.2,	-200,	200
		Ilimit,	double,	Input,	0.0001,	1e-9,	1.0
	INCLUDES:
#include "keithley.h"
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION

SMU Bias Timed Read - Start (Phase 1: apply bias, then return for sync)
=======================================================================

Applies Vforce and sets Ilimit. Returns as soon as bias is applied so the
host can synchronise the laser (or other equipment) to "measurement ready".
Follow with SMU_BiasTimedRead_Collect to perform the sampling loop.

Used with SMU_BiasTimedRead_Collect for optical+read tests: host waits for
this return, sets t0, starts laser, then runs Collect in parallel.

- Vforce: DC voltage to apply (V), range -200 to 200
- Ilimit: Current compliance limit (A)

Return codes: 0 = OK, -5 = forcev failed, -7 = limiti failed

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"

/* USRLIB MODULE MAIN FUNCTION */
int SMU_BiasTimedRead_Start( double Vforce, double Ilimit )
{
/* USRLIB MODULE CODE */
int status;

/* Set current compliance limit */
status = limiti(SMU1, Ilimit);
if ( status != 0 )
{
    forcev(SMU1, 0.0);
    return( -7 );  /* limiti failed */
}

/* Set fast integration for sampling (0.01 PLC) so measi works in Collect */
status = setmode(SMU1, KI_INTGPLC, 0.01);
/* Ignore setmode failure; continue with default */

/* Apply bias voltage - when this returns, host knows we are "ready" */
status = forcev(SMU1, Vforce);
if ( status != 0 )
{
    forcev(SMU1, 0.0);
    return( -5 );  /* forcev failed */
}

return( 0 );  /* Ready: bias applied, host can start laser and then call Collect */

/* USRLIB MODULE END  */
} 		/* End SMU_BiasTimedRead_Start.c */
