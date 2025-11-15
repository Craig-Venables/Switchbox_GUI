/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig5_wait_signal
	MODULE RETURN TYPE: void 
	NUMBER OF PARMS: 1
	ARGUMENTS:
		ready,	long,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->

Module: ACraig5_wait_signal
===========================

Description
-----------
Sets or clears the user-ready flag for the ACraig5 wait gate. Setting the flag
to 1 allows an armed waveform to execute; clearing it forces the sequence to
pause until readiness is asserted again.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"

extern volatile long g_acraig5_wait_enabled;
extern volatile long g_acraig5_user_ready;
#define a_craig5_wait_enabled g_acraig5_wait_enabled
#define a_craig5_user_ready   g_acraig5_user_ready

/* USRLIB MODULE MAIN FUNCTION */
__declspec( dllexport ) void ACraig5_wait_signal(long ready)
{
/* USRLIB MODULE CODE */
    g_acraig5_user_ready = ready ? 1 : 0;
}

/* USRLIB MODULE END  */

