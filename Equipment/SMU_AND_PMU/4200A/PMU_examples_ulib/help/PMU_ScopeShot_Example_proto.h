/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_ScopeShot_Example
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 71
	ARGUMENTS:
		PW_Gate,	double,	Input,	200e-9,	60e-9,	.999999
		RiseTimeGate,	double,	Input,	40e-9,	20e-9,	0.033
		FallTimeGate,	double,	Input,	40e-9,	20e-9,	0.033
		DelayGate,	double,	Input,	100e-9,	0,	.999999
		PW_Drain,	double,	Input,	300e-9,	60e-9,	.999999
		RiseTimeDrain,	double,	Input,	100e-9,	20e-9,	.033
		FallTimeDrain,	double,	Input,	100e-9,	20e-9,	.033
		DelayDrain,	double,	Input,	100e-9,	0,	.999999
		Period,	double,	Input,	5e-6,	120e-9,	1
		MeasStartGate,	double,	Input,	0.65,	0,	1
		MeasStopGate,	double,	Input,	0.80,	0,	1
		PulseAverage,	int,	Input,	1,	1,	10000
		LoadLineGate,	int,	Input,	1,	0,	1
		LoadLineDrain,	int,	Input,	1,	0,	1
		ResGate,	double,	Input,	1e6,	1,	1e6
		ResDrain,	double,	Input,	1e6,	1,	1e6
		AmplVGate,	double,	Input,	1,	-40,	40
		BaseVGate,	double,	Input,	0,	-40,	40
		AmplVDrain,	double,	Input,	2,	-40,	40
		BaseVDrain,	double,	Input,	0,	-40,	40
		VRangeGate,	double,	Input,	10,	5,	40
		IRangeGate,	double,	Input,	0.01,	1e-7,	.8
		LtdAuto_I_Gate,	double,	Input,	0,	0,	1
		VRangeDrain,	double,	Input,	10,	5,	40
		IRangeDrain,	double,	Input,	0.2,	1e-7,	.8
		LtdAuto_I_Drn,	double,	Input,	0,	0,	1
		GateCh,	int,	Input,	1,	1,	2
		DrainCh,	int,	Input,	2,	1,	2
		MaxSheetRows,	int,	Input,	3000,	100,	32767
		Thrshld_I_Gate,	double,	Input,	1,	1e-12,	1
		ThresholdVoltGate,	double,	Input,	40,	0,	42
		ThresholdPwrGate,	double,	Input,	8,	1e-12,	10
		ThresholdCurrDrain,	double,	Input,	1,	1e-12,	1
		ThresholdVoltDrain,	double,	Input,	40,	0,	42
		ThresholdPwrDrain,	double,	Input,	8,	0,	10
		PrePulse,	double,	Input,	.2,	0,	1
		PostPulse,	double,	Input,	.2,	0,	1
		PMUMode,	int,	Input,	0,	0,	1
		SMU_V,	double,	Input,	0,	-210,	+210
		SMU_Irange,	double,	Input,	.01,	10e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		SMU_ID,	char *,	Input,	"NONE",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		Gate_TimeStamp,	D_ARRAY_T,	Output,	,	,	
		Gate_TimeStamp_Size,	int,	Input,	3000,	,	32767
		Gate_V,	D_ARRAY_T,	Output,	,	,	
		Gate_V_Size,	int,	Input,	3000,	,	32767
		Gate_I,	D_ARRAY_T,	Output,	,	,	
		Gate_I_Size,	int,	Input,	3000,	,	32767
		Drain_TimeStamp,	D_ARRAY_T,	Output,	,	,	
		Drain_TimeStamp_Size,	int,	Input,	3000,	,	32767
		Drain_V,	D_ARRAY_T,	Output,	,	,	
		Drain_V_Size,	int,	Input,	3000,	,	32767
		Drain_I,	D_ARRAY_T,	Output,	,	,	
		Drain_I_Size,	int,	Input,	3000,	,	32767
		SpotMean_StartWind,	D_ARRAY_T,	Output,	,	,	
		SpotMean_StartWind_Size,	int,	Input,	1,	,	
		SpotMean_StopWind,	D_ARRAY_T,	Output,	,	,	
		SpotMean_StopWind_Size,	int,	Input,	1,	,	
		Gate_V_Ampl_SM,	D_ARRAY_T,	Output,	,	,	
		Gate_V_Ampl_SM_Size,	int,	Input,	1,	,	
		Gate_I_Ampl_SM,	D_ARRAY_T,	Output,	,	,	
		Gate_I_Ampl_SM_Size,	int,	Input,	1,	,	
		Drain_V_Ampl_SM,	D_ARRAY_T,	Output,	,	,	
		Drain_V_Ampl_SM_Size,	int,	Input,	1,	,	
		Drain_I_Ampl_SM,	D_ARRAY_T,	Output,	,	,	
		Drain_I_Ampl_SM_Size,	int,	Input,	1,	,	
		Status_Gate,	I_ARRAY_T,	Output,	,	,	
		Status_Gate_Size,	int,	Input,	1,	,	
		Status_Drain,	I_ARRAY_T,	Output,	,	,	
		Status_Drain_Size,	int,	Input,	1,	,	
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_PMU_ScpSht(int NumPts);
void FreeArrays_PMU_ScpSht();

double *GateV_All = NULL, *GateI_All = NULL, *GateT_All = NULL;
double *DrainV_All = NULL, *DrainI_All = NULL, *DrainT_All = NULL;

unsigned long *GateS_All = NULL, *DrainS_All = NULL;

#pragma warning( disable: 4996 )

	END USRLIB MODULE INFORMATION
*/
int PMU_ScopeShot_Example(double, double, double, double, double, double, double, double, double, double, double, int, int, int, double, double, double, double, double, double, double, double, double, double, double, double, int, int, int, double, double, double, double, double, double, double, double, int, double, double, double, char *, char *, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, int *, int, int *, int);
