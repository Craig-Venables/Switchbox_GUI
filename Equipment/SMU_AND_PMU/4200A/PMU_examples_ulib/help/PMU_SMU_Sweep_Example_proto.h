/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_SMU_Sweep_Example
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 69
	ARGUMENTS:
		PulseWidthCh1,	double,	Input,	1e-6,	60e-9,	.999999
		RiseTimeCh1,	double,	Input,	40e-9,	20e-9,	0.033
		FallTimeCh1,	double,	Input,	40e-9,	20e-9,	0.033
		DelayCh1,	double,	Input,	0,	0,	.999999
		PulseWidthCh2,	double,	Input,	1e-6,	60e-9,	.999999
		RiseTimeCh2,	double,	Input,	100e-9,	20e-9,	.033
		FallTimeCh2,	double,	Input,	100e-9,	20e-9,	.033
		DelayCh2,	double,	Input,	0,	0,	.999999
		Period,	double,	Input,	2e-6,	80e-9,	1
		PulseAverage,	int,	Input,	1,	1,	10000
		LoadLineCh1,	int,	Input,	0,	0,	1
		LoadLineCh2,	int,	Input,	0,	0,	1
		ResCh1,	double,	Input,	1e6,	1,	1e6
		ResCh2,	double,	Input,	1E6,	1,	1E6
		AmplVCh1,	double,	Input,	2,	-40,	40
		BaseVCh1,	double,	Input,	0,	-40,	40
		StartVCh2,	double,	Input,	0,	-40,	40
		StopVCh2,	double,	Input,	5,	-40,	40
		StepVCh2,	double,	Input,	0.1,	.001,	40
		BaseVCh2,	double,	Input,	0,	-40,	40
		VRangeCh1,	double,	Input,	10,	5,	40
		IRangeCh1,	double,	Input,	0.01,	1e-7,	.8
		LtdAutoCurrCh1,	double,	Input,	0,	0,	1
		VRangeCh2,	double,	Input,	10,	5,	40
		IRangeCh2,	double,	Input,	0.2,	1e-7,	.8
		LtdAutoCurrCh2,	double,	Input,	0,	0,	1
		PMUMode,	int,	Input,	0,	0,	2
		SMU_Irange,	double,	Input,	.01,	1e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		Ch1SMU_ID,	char *,	Input,	"SMU1",	,	
		Ch2SMU_ID,	char *,	Input,	"SMU2",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		ExecMode,	int,	Input,	0,	0,	2
		Ch1_V_Ampl,	D_ARRAY_T,	Output,	,	,	
		Ch1_V_Ampl_Size,	int,	Input,	100,	1,	10000
		Ch1_I_Ampl,	D_ARRAY_T,	Output,	,	,	
		Ch1_I_Ampl_Size,	int,	Input,	100,	1,	10000
		Ch1_V_Base,	D_ARRAY_T,	Output,	,	,	
		Ch1_V_Base_Size,	int,	Input,	100,	1,	10000
		Ch1_I_Base,	D_ARRAY_T,	Output,	,	,	
		Ch1_I_Base_Size,	int,	Input,	100,	1,	10000
		Ch2_V_Ampl,	D_ARRAY_T,	Output,	,	,	
		Ch2_V_Ampl_Size,	int,	Input,	100,	1,	10000
		Ch2_I_Ampl,	D_ARRAY_T,	Output,	,	,	
		Ch2_I_Ampl_Size,	int,	Input,	100,	1,	10000
		Ch2_V_Base,	D_ARRAY_T,	Output,	,	,	
		Ch2_V_Base_Size,	int,	Input,	100,	1,	10000
		Ch2_I_Base,	D_ARRAY_T,	Output,	,	,	
		Ch2_I_Base_Size,	int,	Input,	100,	1,	10000
		TimeStampAmpl_Ch1,	D_ARRAY_T,	Output,	,	,	
		TimeStampAmpl_Ch1_Size,	int,	Input,	100,	1,	10000
		TimeStampBase_Ch1,	D_ARRAY_T,	Output,	,	,	
		TimeStampBase_Ch1_Size,	int,	Input,	100,	1,	10000
		TimeStampAmpl_Ch2,	D_ARRAY_T,	Output,	,	,	
		TimeStampAmpl_Ch2_Size,	int,	Input,	100,	1,	10000
		TimeStampBase_Ch2,	D_ARRAY_T,	Output,	,	,	
		TimeStampBase_Ch2_Size,	int,	Input,	100,	1,	10000
		Status_Ch1,	D_ARRAY_T,	Output,	,	,	
		Status_Ch1_Size,	int,	Input,	100,	1,	10000
		Status_Ch2,	D_ARRAY_T,	Output,	,	,	
		Status_Ch2_Size,	int,	Input,	100,	1,	10000
		Ch2_SMU_Voltage,	D_ARRAY_T,	Output,	,	,	
		Ch2SMUVoltageSize,	int,	Input,	100,	1,	10000
		Ch2_SMU_Current,	D_ARRAY_T,	Output,	,	,	
		Ch2SMUCurrentSize,	int,	Input,	100,	1,	10000
		Ch1_SMU_Voltage,	D_ARRAY_T,	Output,	,	,	
		Ch1SMUVoltageSize,	int,	Input,	100,	1,	10000
		Ch1_SMU_Current,	D_ARRAY_T,	Output,	,	,	
		Ch1SMUCurrentSize,	int,	Input,	100,	1,	10000
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
#define MaxSamplesPerAtoD 1000000
#define PulseAndSMUMode 0
#define PulseOnlyMode 1
#define SMUOnlyMode 2
extern void cleanUp( double *, double *, double *, double *,
              double *, double *, double *, double *, 
              double *, double *, double *, double *);
#pragma warning( disable: 4996 )
	END USRLIB MODULE INFORMATION
*/
int PMU_SMU_Sweep_Example(double, double, double, double, double, double, double, double, double, int, int, int, double, double, double, double, double, double, double, double, double, double, double, double, double, double, int, double, double, char *, char *, char *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int);
