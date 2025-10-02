/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_1Chan_Sweep_Example
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 32
	ARGUMENTS:
		PulseWidthCh1,	double,	Input,	500e-9,	60e-9,	.999999
		RiseTimeCh1,	double,	Input,	100e-9,	20e-9,	.033
		FallTimeCh1,	double,	Input,	100e-9,	20e-9,	0.033
		Period,	double,	Input,	10e-6,	120e-9,	1
		DelayCh1,	double,	Input,	0,	0,	.999999
		SampleRate,	double,	Input,	200E6,	1000,	200E6
		MeasStartPerc,	double,	Input,	.75,	0,	1
		MeasStopPerc,	double,	Input,	0.90,	0,	1
		PulseAverage,	int,	Input,	1,	1,	10000
		LoadLineCh1,	int,	Input,	0,	0,	1
		DUTResCh1,	double,	Input,	1E6,	1,	1E6
		VRangeCh1,	double,	Input,	10,	5,	40
		IRangeCh1,	double,	Input,	.01,	100e-9,	.8
		StartVCh1,	double,	Input,	0,	-40,	40
		StopVCh1,	double,	Input,	5,	-40,	40
		StepVCh1,	double,	Input,	1,	-40,	40
		BaseVCh1,	double,	Input,	0,	-40,	40
		PMUMode,	int,	Input,	0,	0,	1
		Chan,	int,	Input,	1,	1,	2
		PMU_ID,	char *,	Input,	"PMU1",	,	
		V_Ampl_Ch1,	D_ARRAY_T,	Output,	,	,	
		V_Ampl_Ch1_Size,	int,	Input,	100,	1,	10000
		I_Ampl_Ch1,	D_ARRAY_T,	Output,	,	,	
		I_Ampl_Ch1_Size,	int,	Input,	100,	1,	10000
		V_Base_Ch1,	D_ARRAY_T,	Output,	,	,	
		V_Base_Ch1_Size,	int,	Input,	100,	1,	10000
		I_Base_Ch1,	D_ARRAY_T,	Output,	,	,	
		I_Base_Ch1_Size,	int,	Input,	100,	1,	10000
		TimeStamp_Ch1,	D_ARRAY_T,	Output,	,	,	
		TimeStamp_Ch1_Size,	int,	Input,	100,	1,	10000
		Status_Ch1,	I_ARRAY_T,	Output,	,	,	
		Status_Ch1_Size,	int,	Input,	100,	1,	10000
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_1ChanSw(int numSweepPoints);
void FreeArrays_1ChanSw();

double *Chan1_V, *Chan1_I, *Chan1_T, *Chan1_Vhisheet, *Chan1_Ihisheet, *Chan1_Vlosheet, *Chan1_Ilosheet, *Chan1_Tsheet;
unsigned long *Chan1_S, *Chan1_Ssheet;
	END USRLIB MODULE INFORMATION
*/
int PMU_1Chan_Sweep_Example(double, double, double, double, double, double, double, double, int, int, double, double, double, double, double, double, double, int, int, char *, double *, int, double *, int, double *, int, double *, int, double *, int, int *, int);
