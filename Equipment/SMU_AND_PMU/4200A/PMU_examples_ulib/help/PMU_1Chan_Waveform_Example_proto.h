/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_1Chan_Waveform_Example
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 29
	ARGUMENTS:
		width,	double,	Input,	500e-9,	40e-9,	.999999
		rise,	double,	Input,	100e-9,	20e-9,	.033
		fall,	double,	Input,	100e-9,	20e-9,	.033
		delay,	double,	Input,	0.0,	0,	.999999
		period,	double,	Input,	1e-6,	120e-9,	1
		voltsSourceRng,	double,	Input,	10,	5,	40
		currentMeasureRng,	double,	Input,	.01,	100e-9,	.8
		DUTRes,	double,	Input,	1E6,	1,	10e6
		startV,	double,	Input,	0,	-40,	40
		stopV,	double,	Input,	5,	-40,	40
		stepV,	double,	Input,	1,	-40,	40
		baseV,	double,	Input,	0,	-40,	
		acqType,	int,	Input,	1,	0,	1
		LLEComp,	int,	Input,	0,	0,	1
		preDataPct,	double,	Input,	.2,	0,	1.0
		postDataPct,	double,	Input,	.2,	0,	1.0
		pulseAvgCnt,	int,	Input,	1,	1,	10000
		SampleRate,	double,	Input,	200e6,	1,	200e6
		PMUMode,	int,	Input,	0,	0,	1
		chan,	int,	Input,	1,	1,	2
		PMU_ID,	char *,	Input,	"PMU1",	,	
		V_Meas,	D_ARRAY_T,	Output,	,	,	
		size_V_Meas,	int,	Input,	3000,	100,	32767
		I_Meas,	D_ARRAY_T,	Output,	,	,	
		size_I_Meas,	int,	Input,	3000,	100,	32767
		T_Stamp,	D_ARRAY_T,	Output,	,	,	
		size_T_Stamp,	int,	Input,	3000,	100,	32767
		Status,	I_ARRAY_T,	Output,	,	,	
		size_Status,	int,	Input,	3000,	100,	32767
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
	END USRLIB MODULE INFORMATION
*/
int PMU_1Chan_Waveform_Example(double, double, double, double, double, double, double, double, double, double, double, double, int, int, double, double, int, double, int, int, char *, double *, int, double *, int, double *, int, int *, int);
