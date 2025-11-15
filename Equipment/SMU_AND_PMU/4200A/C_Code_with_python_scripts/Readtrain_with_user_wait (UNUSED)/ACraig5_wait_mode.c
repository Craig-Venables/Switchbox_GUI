/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig5_wait_mode
	MODULE RETURN TYPE: void 
	NUMBER OF PARMS: 1
	ARGUMENTS:
		enable,	long,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->

Module: ACraig5_wait_mode
=========================

Description
-----------
Arms or disarms the manual wait gate used by ACraig5 retention routines. When
enabled, the waveform sequences pause just before execution until a matching
`ACraig5_wait_signal` call releases them.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"

extern volatile long g_acraig5_wait_enabled;
extern volatile long g_acraig5_user_ready;
#define a_craig5_wait_enabled g_acraig5_wait_enabled
#define a_craig5_user_ready   g_acraig5_user_ready

/* USRLIB MODULE MAIN FUNCTION */
__declspec( dllexport ) void ACraig5_wait_mode(long enable)
{
/* USRLIB MODULE CODE */
    if(enable)
    {
        g_acraig5_wait_enabled = 1;
        g_acraig5_user_ready = 0;
    }
    else
    {
        g_acraig5_wait_enabled = 0;
        g_acraig5_user_ready = 1;
    }
}

/* USRLIB MODULE END  */

