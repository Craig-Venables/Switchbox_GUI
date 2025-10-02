/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_10ns_Pulse_Example
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 2
	ARGUMENTS:
		pmu_ch,	int,	Input,	1,	1,	2
		pmu_id,	int,	Input,	1,	1,	2
	INCLUDES:
#include "keithley.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
	END USRLIB MODULE INFORMATION
*/
int PMU_10ns_Pulse_Example(int, int);
