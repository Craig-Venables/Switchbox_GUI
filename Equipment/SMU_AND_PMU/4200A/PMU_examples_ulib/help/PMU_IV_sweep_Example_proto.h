/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_IV_sweep_Example
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 66
	ARGUMENTS:
		PulseWidthGate,	double,	Input,	200e-9,	60e-9,	.999999
		RiseTimeGate,	double,	Input,	40e-9,	20e-9,	0.033
		FallTimeGate,	double,	Input,	40e-9,	20e-9,	0.033
		DelayGate,	double,	Input,	0,	0,	.999999
		PulseWidthDrain,	double,	Input,	300e-9,	60e-9,	.999999
		RiseTimeDrain,	double,	Input,	100e-9,	20e-9,	.033
		FallTimeDrain,	double,	Input,	100e-9,	20e-9,	.033
		DelayDrain,	double,	Input,	0,	0,	.999999
		Period,	double,	Input,	5e-6,	80e-9,	1
		MeasStartGate,	double,	Input,	0.65,	0,	1
		MeasStopGate,	double,	Input,	0.80,	0,	1
		PulseAverage,	int,	Input,	1,	1,	10000
		LoadLineGate,	int,	Input,	1,	0,	1
		LoadLineDrain,	int,	Input,	1,	0,	1
		ResGate,	double,	Input,	1e6,	1,	1e6
		ResDrain,	double,	Input,	1E6,	1,	1E6
		AmplVGate,	double,	Input,	2,	-40,	40
		BaseVGate,	double,	Input,	0,	-40,	40
		StartVDrain,	double,	Input,	0,	-40,	40
		StopVDrain,	double,	Input,	5,	-40,	40
		StepVDrain,	double,	Input,	1,	.001,	40
		BaseVDrain,	double,	Input,	0,	-40,	40
		VRangeGate,	double,	Input,	10,	5,	40
		IRangeGate,	double,	Input,	0.01,	1e-7,	.8
		LtdAutoCurrGate,	int,	Input,	0,	0,	1
		VRangeDrain,	double,	Input,	10,	5,	40
		IRangeDrain,	double,	Input,	0.2,	1e-7,	.8
		LtdAutoCurrDrain,	int,	Input,	0,	0,	1
		GateCh,	int,	Input,	1,	1,	2
		DrainCh,	int,	Input,	2,	1,	2
		ThresholdCurrGate,	double,	Input,	1,	1e-12,	1
		ThresholdVoltGate,	double,	Input,	40,	0,	42
		ThresholdPwrGate,	double,	Input,	8,	1e-12,	10
		ThresholdCurrDrain,	double,	Input,	1,	1e-12,	1
		ThresholdVoltDrain,	double,	Input,	40,	0,	42
		ThresholdPwrDrain,	double,	Input,	8,	0,	10
		PMUMode,	int,	Input,	0,	0,	1
		SMU_V,	double,	Input,	0,	-210,	210
		SMU_Irange,	double,	Input,	.01,	10e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		SMU_ID,	char *,	Input,	"NONE",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		Gate_V_Ampl,	D_ARRAY_T,	Output,	,	,	
		Gate_V_Ampl_Size,	int,	Input,	100,	,	10000
		Gate_I_Ampl,	D_ARRAY_T,	Output,	,	,	
		Gate_I_Ampl_Size,	int,	Input,	100,	,	10000
		Gate_V_Base,	D_ARRAY_T,	Output,	,	,	
		Gate_V_Base_Size,	int,	Input,	100,	,	10000
		Gate_I_Base,	D_ARRAY_T,	Output,	,	,	
		Gate_I_Base_Size,	int,	Input,	100,	,	10000
		Drain_V_Ampl,	D_ARRAY_T,	Output,	,	,	
		Drain_V_Ampl_Size,	int,	Input,	100,	,	10000
		Drain_I_Ampl,	D_ARRAY_T,	Output,	,	,	
		Drain_I_Ampl_Size,	int,	Input,	100,	,	10000
		Drain_V_Base,	D_ARRAY_T,	Output,	,	,	
		Drain_V_Base_Size,	int,	Input,	100,	,	10000
		Drain_I_Base,	D_ARRAY_T,	Output,	,	,	
		Drain_I_Base_Size,	int,	Input,	100,	,	10000
		TimeStampAmpl_Gate,	D_ARRAY_T,	Output,	,	,	
		TimeStampAmpl_Gate_Size,	int,	Input,	100,	,	10000
		TimeStampBase_Gate,	D_ARRAY_T,	Output,	,	,	
		TimeStampBase_Gate_Size,	int,	Input,	100,	,	10000
		TimeStampAmpl_Drain,	D_ARRAY_T,	Output,	,	,	
		TimeStampAmpl_Drain_Size,	int,	Input,	100,	,	10000
		TimeStampBase_Drain,	D_ARRAY_T,	Output,	,	,	
		TimeStampBase_Drain_Size,	int,	Input,	100,	,	10000
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
#define MaxSamplesPerAtoD 1000000
void AllocateArrays_PMU_IV_Sw(int NumberofSegments);
void FreeArrays_PMU_IV_Sw();

double *Gate_V_All = NULL, *Gate_I_All = NULL, *Gate_T_All = NULL;
double *Gate_V_High = NULL, *Gate_I_High = NULL, *Gate_T_High = NULL;    
double *Gate_V_Low = NULL, *Gate_I_Low = NULL, *Gate_T_Low = NULL;    
double *Drain_V_All = NULL, *Drain_I_All = NULL, *Drain_T_All = NULL;
double *Drain_V_High = NULL, *Drain_I_High = NULL,*Drain_T_High = NULL;    
double *Drain_V_Low = NULL, *Drain_I_Low = NULL, *Drain_T_Low = NULL;    
unsigned long *Gate_S_All = NULL, *Drain_S_All = NULL;


#pragma warning( disable: 4996 )
	END USRLIB MODULE INFORMATION
*/
int PMU_IV_sweep_Example(double, double, double, double, double, double, double, double, double, double, double, int, int, int, double, double, double, double, double, double, double, double, double, double, int, double, double, int, int, int, double, double, double, double, double, double, int, double, double, double, char *, char *, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int, double *, int);
