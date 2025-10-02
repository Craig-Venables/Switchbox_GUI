#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_SegArb_ExampleFull(double VRangeCh1, double IRangeCh1, double VRangeCh2, double IRangeCh2, int AcqType, double DUTResCh1, double DUTResCh2, int MaxSheetPoints, double *SegTime, int SegTime_size, double *StartVCh1, int StartVCh1_size, double *StopVCh1, int StopVCh1_size, double *StartVCh2, int StartVCh2_size, double *StopVCh2, int StopVCh2_size, int *MeasEnabled, int MeasEnabled_size, int *SSRCtrlCh1, int SSRCtrlCh1_size, int *SSRCtrlCh2, int SSRCtrlCh2_size, int *SegTrigOut, int SegTrigOut_size, int *SegMeasType, int SegMeasType_size, double *SegMeasStart, int SegMeasStart_size, double *SegMeasStop, int SegMeasStop_size, int *SeqList, int SeqList_size, int *SeqStartSeg, int SeqStartSeg_size, int *SeqStopSeg, int SeqStopSeg_size, int *SeqListCh1, int SeqListCh1_size, int *SeqListCh2, int SeqListCh2_size, double *SeqLoopsCh1, int SeqLoopsCh1_size, double *SeqLoopsCh2, int SeqLoopsCh2_size, double SMU_V, double SMU_Irange, double SMU_Icomp, char * SMU_ID, char * PMU_ID, double *VMeasCh1, int VMeasCh1_size, double *IMeasCh1, int IMeasCh1_size, double *VMeasCh2, int VMeasCh2_size, double *IMeasCh2, int IMeasCh2_size, double *TimeOutput, int TimeOutput_size, int *StatusCh1, int StatusCh1_size, int *StatusCh2, int StatusCh2_size);

int w_PMU_SegArb_ExampleFull(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	double *p8;
	double *p10;
	double *p12;
	double *p14;
	double *p16;
	int *p18;
	int *p20;
	int *p22;
	int *p24;
	int *p26;
	double *p28;
	double *p30;
	int *p32;
	int *p34;
	int *p36;
	int *p38;
	int *p40;
	double *p42;
	double *p44;
	char *p49;
	char *p50;
	double *p51 = (double *)malloc(sizeof(double)*I(52));
	double *p53 = (double *)malloc(sizeof(double)*I(54));
	double *p55 = (double *)malloc(sizeof(double)*I(56));
	double *p57 = (double *)malloc(sizeof(double)*I(58));
	double *p59 = (double *)malloc(sizeof(double)*I(60));
	int *p61 = (int *)malloc(sizeof(int)*I(62));
	int *p63 = (int *)malloc(sizeof(int)*I(64));
	int status;
	extern void *GetReusableParm(char *search_name, int *status);

	p8 = (double *)GetReusableParm(S(8), &status);
	if((p8 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(8));
		return(RP_ERROR);
	}

	p10 = (double *)GetReusableParm(S(10), &status);
	if((p10 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(10));
		return(RP_ERROR);
	}

	p12 = (double *)GetReusableParm(S(12), &status);
	if((p12 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(12));
		return(RP_ERROR);
	}

	p14 = (double *)GetReusableParm(S(14), &status);
	if((p14 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(14));
		return(RP_ERROR);
	}

	p16 = (double *)GetReusableParm(S(16), &status);
	if((p16 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(16));
		return(RP_ERROR);
	}

	p18 = (int *)GetReusableParm(S(18), &status);
	if((p18 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(18));
		return(RP_ERROR);
	}

	p20 = (int *)GetReusableParm(S(20), &status);
	if((p20 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(20));
		return(RP_ERROR);
	}

	p22 = (int *)GetReusableParm(S(22), &status);
	if((p22 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(22));
		return(RP_ERROR);
	}

	p24 = (int *)GetReusableParm(S(24), &status);
	if((p24 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(24));
		return(RP_ERROR);
	}

	p26 = (int *)GetReusableParm(S(26), &status);
	if((p26 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(26));
		return(RP_ERROR);
	}

	p28 = (double *)GetReusableParm(S(28), &status);
	if((p28 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(28));
		return(RP_ERROR);
	}

	p30 = (double *)GetReusableParm(S(30), &status);
	if((p30 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(30));
		return(RP_ERROR);
	}

	p32 = (int *)GetReusableParm(S(32), &status);
	if((p32 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(32));
		return(RP_ERROR);
	}

	p34 = (int *)GetReusableParm(S(34), &status);
	if((p34 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(34));
		return(RP_ERROR);
	}

	p36 = (int *)GetReusableParm(S(36), &status);
	if((p36 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(36));
		return(RP_ERROR);
	}

	p38 = (int *)GetReusableParm(S(38), &status);
	if((p38 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(38));
		return(RP_ERROR);
	}

	p40 = (int *)GetReusableParm(S(40), &status);
	if((p40 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(40));
		return(RP_ERROR);
	}

	p42 = (double *)GetReusableParm(S(42), &status);
	if((p42 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(42));
		return(RP_ERROR);
	}

	p44 = (double *)GetReusableParm(S(44), &status);
	if((p44 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(44));
		return(RP_ERROR);
	}

	p49 = (char *)GetReusableParm(S(49), &status);
	if((p49 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(49));
		return(RP_ERROR);
	}

	p50 = (char *)GetReusableParm(S(50), &status);
	if((p50 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(50));
		return(RP_ERROR);
	}

	if(!HardwareOffline)
		*ret = (int)PMU_SegArb_ExampleFull(D(0), D(1), D(2), D(3), I(4), D(5), D(6), I(7), p8, I(9), p10, I(11), p12, I(13), p14, I(15), p16, I(17), p18, I(19), p20, I(21), p22, I(23), p24, I(25), p26, I(27), p28, I(29), p30, I(31), p32, I(33), p34, I(35), p36, I(37), p38, I(39), p40, I(41), p42, I(43), p44, I(45), D(46), D(47), D(48), p49, p50, p51, I(52), p53, I(54), p55, I(56), p57, I(58), p59, I(60), p61, I(62), p63, I(64));

	add_result("PMU_SegArb_ExampleFull", RETVAL_NAME, INT_P, ret, 1);
	add_result("PMU_SegArb_ExampleFull", S(51), DOUBLE_P, p51, I(52));
	add_result("PMU_SegArb_ExampleFull", S(53), DOUBLE_P, p53, I(54));
	add_result("PMU_SegArb_ExampleFull", S(55), DOUBLE_P, p55, I(56));
	add_result("PMU_SegArb_ExampleFull", S(57), DOUBLE_P, p57, I(58));
	add_result("PMU_SegArb_ExampleFull", S(59), DOUBLE_P, p59, I(60));
	add_result("PMU_SegArb_ExampleFull", S(61), INT_P, p61, I(62));
	add_result("PMU_SegArb_ExampleFull", S(63), INT_P, p63, I(64));
	return(0);
}
