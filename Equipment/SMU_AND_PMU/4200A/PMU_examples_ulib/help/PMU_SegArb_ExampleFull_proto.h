/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_SegArb_ExampleFull
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 65
	ARGUMENTS:
		VRangeCh1,	double,	Input,	10,	5,	40
		IRangeCh1,	double,	Input,	.01,	100e-9,	.8
		VRangeCh2,	double,	Input,	10,	5,	40
		IRangeCh2,	double,	Input,	.01,	100e-9,	.8
		AcqType,	int,	Input,	0,	0,	0
		DUTResCh1,	double,	Input,	1E6,	1,	1E6
		DUTResCh2,	double,	Input,	1E6,	1,	1E6
		MaxSheetPoints,	int,	Input,	10000,	12,	30000
		SegTime,	D_ARRAY_T,	Input,	,	,	
		SegTime_size,	int,	Input,	20,	3,	2048
		StartVCh1,	D_ARRAY_T,	Input,	,	,	
		StartVCh1_size,	int,	Input,	20,	3,	2048
		StopVCh1,	D_ARRAY_T,	Input,	,	,	
		StopVCh1_size,	int,	Input,	20,	3,	2048
		StartVCh2,	D_ARRAY_T,	Input,	,	,	
		StartVCh2_size,	int,	Input,	20,	3,	2048
		StopVCh2,	D_ARRAY_T,	Input,	,	,	
		StopVCh2_size,	int,	Input,	20,	3,	2048
		MeasEnabled,	I_ARRAY_T,	Input,	,	,	
		MeasEnabled_size,	int,	Input,	20,	3,	2048
		SSRCtrlCh1,	I_ARRAY_T,	Input,	,	,	
		SSRCtrlCh1_size,	int,	Input,	20,	3,	2048
		SSRCtrlCh2,	I_ARRAY_T,	Input,	,	,	
		SSRCtrlCh2_size,	int,	Input,	20,	3,	2048
		SegTrigOut,	I_ARRAY_T,	Input,	,	,	
		SegTrigOut_size,	int,	Input,	20,	3,	2048
		SegMeasType,	I_ARRAY_T,	Input,	,	,	
		SegMeasType_size,	int,	Input,	20,	3,	2048
		SegMeasStart,	D_ARRAY_T,	Input,	,	,	
		SegMeasStart_size,	int,	Input,	20,	3,	2048
		SegMeasStop,	D_ARRAY_T,	Input,	,	,	
		SegMeasStop_size,	int,	Input,	20,	3,	2048
		SeqList,	I_ARRAY_T,	Input,	,	,	
		SeqList_size,	int,	Input,	20,	1,	512
		SeqStartSeg,	I_ARRAY_T,	Input,	,	,	
		SeqStartSeg_size,	int,	Input,	20,	1,	512
		SeqStopSeg,	I_ARRAY_T,	Input,	,	,	
		SeqStopSeg_size,	int,	Input,	20,	1,	512
		SeqListCh1,	I_ARRAY_T,	Input,	,	,	
		SeqListCh1_size,	int,	Input,	20,	1,	512
		SeqListCh2,	I_ARRAY_T,	Input,	,	,	
		SeqListCh2_size,	int,	Input,	20,	1,	512
		SeqLoopsCh1,	D_ARRAY_T,	Input,	,	,	
		SeqLoopsCh1_size,	int,	Input,	,	,	
		SeqLoopsCh2,	D_ARRAY_T,	Input,	,	,	
		SeqLoopsCh2_size,	int,	Input,	,	,	
		SMU_V,	double,	Input,	0,	-210,	+210
		SMU_Irange,	double,	Input,	.01,	10e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		SMU_ID,	char *,	Input,	"NONE",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		VMeasCh1,	D_ARRAY_T,	Output,	,	,	
		VMeasCh1_size,	int,	Input,	10000,	100,	30000
		IMeasCh1,	D_ARRAY_T,	Output,	,	,	
		IMeasCh1_size,	int,	Input,	10000,	100,	30000
		VMeasCh2,	D_ARRAY_T,	Output,	,	,	
		VMeasCh2_size,	int,	Input,	10000,	12,	30000
		IMeasCh2,	D_ARRAY_T,	Output,	,	,	
		IMeasCh2_size,	int,	Input,	10000,	12,	30000
		TimeOutput,	D_ARRAY_T,	Output,	,	,	
		TimeOutput_size,	int,	Input,	10000,	12,	30000
		StatusCh1,	I_ARRAY_T,	Output,	,	,	
		StatusCh1_size,	int,	Input,	10000,	12,	30000
		StatusCh2,	I_ARRAY_T,	Output,	,	,	
		StatusCh2_size,	int,	Input,	10000,	12,	30000
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_SegArbExF(int NumberofSegments);
void FreeArrays_SegArbExF();

unsigned long *PulseMeasType;

#pragma warning( disable: 4996 )

	END USRLIB MODULE INFORMATION
*/
int PMU_SegArb_ExampleFull(double, double, double, double, int, double, double, int, double *, int, double *, int, double *, int, double *, int, double *, int, int *, int, int *, int, int *, int, int *, int, int *, int, double *, int, double *, int, int *, int, int *, int, int *, int, int *, int, int *, int, double *, int, double *, int, double, double, double, char *, char *, double *, int, double *, int, double *, int, double *, int, double *, int, int *, int, int *, int);
