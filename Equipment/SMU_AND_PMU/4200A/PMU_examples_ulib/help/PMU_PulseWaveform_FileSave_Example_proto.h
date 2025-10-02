/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_PulseWaveform_FileSave_Example
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 37
	ARGUMENTS:
		PulseTop,	double,	Input,	1e-6,	20e-9,	40
		RiseTime,	double,	Input,	100e-9,	20e-9,	.033
		FallTime,	double,	Input,	100e-9,	20e-9,	.033
		BaseTime,	double,	Input,	1e-6,	20e-9,	40
		DelayTime,	double,	Input,	100e-9,	20e-9,	40
		MaxSheetPoints,	long,	Input,	1000,	100,	32767
		MaxFilePoints,	long,	Input,	30000,	100,	1000000
		Ch1_VRange,	double,	Input,	10,	5,	40
		Ch1_IRange,	double,	Input,	0.200,	100e-9,	.8
		Ch1_V_Ampl,	double,	Input,	2,	-80,	+80
		Ch1_V_Base,	double,	Input,	0,	-40,	+40
		Ch2_VRange,	double,	Input,	10,	5,	40
		Ch2_IRange,	double,	Input,	0.200,	100e-9,	.8
		Ch2_StartV,	double,	Input,	1,	-80,	80
		Ch2_StopV,	double,	Input,	4,	-80,	80
		Ch2_StepV,	double,	Input,	1,	-80,	80
		Ch2_V_Base,	double,	Input,	0,	-40,	40
		Ch1_Res,	double,	Input,	1e6,	1,	1e6
		Ch2_Res,	double,	Input,	1e6,	1,	1e6
		SMU_V,	double,	Input,	0,	-210,	+210
		SMU_Irange,	double,	Input,	.01,	10e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		SMU_ID,	char *,	Input,	"NONE",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		SaveFile,	int,	Input,	1,	0,	1
		AppendTimeToFilename,	int,	Input,	0,	0,	1
		Filename,	char *,	Input,	"wavefrm_capture.csv",	,	
		TimeStamp,	D_ARRAY_T,	Output,	,	,	
		TimeStampSize,	int,	Input,	3000,	1,	32767
		Ch1_Vmeas,	D_ARRAY_T,	Output,	,	,	
		Ch1_VmeasSize,	int,	Input,	3000,	1,	32767
		Ch1_Imeas,	D_ARRAY_T,	Output,	,	,	
		Ch1_ImeasSize,	int,	Input,	3000,	1,	32767
		Ch2_Vmeas,	D_ARRAY_T,	Output,	,	,	
		Ch2_VmeasSize,	int,	Input,	3000,	1,	32767
		Ch2_Imeas,	D_ARRAY_T,	Output,	,	,	
		Ch2_ImeasSize,	int,	Input,	3000,	1,	32767
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
#include <time.h>

double *dstartv, *dstopv, *gstartv, *gstopv, *measstart, *measstop, *segtime;
long *ssrctrl, *meastypes, *trig;

void AllocateArrays_PMU_Wfm_File(int npts);
void FreeArrays_PMU_Wfm_File(void);
void FillSweepArrays_Wfm(double dstartV, double dstepV, double gbias, double gVlo, double dVlo, int numpts, double riset, double fallt, double pwidth, double baset, double delay);
BOOL LPTIsInCurrentConfiguration(char* hrid);
void GetPathFileExt(char*, char*, char*, char*);

#pragma warning( disable: 4996 )

	END USRLIB MODULE INFORMATION
*/
int PMU_PulseWaveform_FileSave_Example(double, double, double, double, double, long, long, double, double, double, double, double, double, double, double, double, double, double, double, double, double, double, char *, char *, int, int, char *, double *, int, double *, int, double *, int, double *, int, double *, int);
