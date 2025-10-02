#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_SegArb_ExampleB(double VRangeCh1, double IRangeCh1, double VRangeCh2, double IRangeCh2, int NumWaveforms, int MeasType, double MeasSegStart, double MeasSegStop, int AcqType, double DUTResCh1, double DUTResCh2, int MaxSheetPoints, int NumSegments, double *SegTime, int SegTime_size, double *StartVCh1, int StartVCh1_size, double *StopVCh1, int StopVCh1_size, double *StartVCh2, int StartVCh2_size, double *StopVCh2, int StopVCh2_size, int *MeasEnabled, int MeasEnabled_size, int *SSRCtrlCh1, int SSRCtrlCh1_size, int *SSRCtrlCh2, int SSRCtrlCh2_size, int *SegTrigOut, int SegTrigOut_size, double SMU_V, double SMU_Irange, double SMU_Icomp, char * SMU_ID, char * PMU_ID, double *VMeasCh1, int VMeasCh1_size, double *IMeasCh1, int IMeasCh1_size, double *VMeasCh2, int VMeasCh2_size, double *IMeasCh2, int IMeasCh2_size, double *TimeOutput, int TimeOutput_size, int *StatusCh1, int StatusCh1_size, int *StatusCh2, int StatusCh2_size);

int w_PMU_SegArb_ExampleB(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	double *p13;
	double *p15;
	double *p17;
	double *p19;
	double *p21;
	int *p23;
	int *p25;
	int *p27;
	int *p29;
	char *p34;
	char *p35;
	double *p36 = (double *)malloc(sizeof(double)*I(37));
	double *p38 = (double *)malloc(sizeof(double)*I(39));
	double *p40 = (double *)malloc(sizeof(double)*I(41));
	double *p42 = (double *)malloc(sizeof(double)*I(43));
	double *p44 = (double *)malloc(sizeof(double)*I(45));
	int *p46 = (int *)malloc(sizeof(int)*I(47));
	int *p48 = (int *)malloc(sizeof(int)*I(49));
	int status;
	extern void *GetReusableParm(char *search_name, int *status);

	p13 = (double *)GetReusableParm(S(13), &status);
	if((p13 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(13));
		return(RP_ERROR);
	}

	p15 = (double *)GetReusableParm(S(15), &status);
	if((p15 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(15));
		return(RP_ERROR);
	}

	p17 = (double *)GetReusableParm(S(17), &status);
	if((p17 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(17));
		return(RP_ERROR);
	}

	p19 = (double *)GetReusableParm(S(19), &status);
	if((p19 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(19));
		return(RP_ERROR);
	}

	p21 = (double *)GetReusableParm(S(21), &status);
	if((p21 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(21));
		return(RP_ERROR);
	}

	p23 = (int *)GetReusableParm(S(23), &status);
	if((p23 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(23));
		return(RP_ERROR);
	}

	p25 = (int *)GetReusableParm(S(25), &status);
	if((p25 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(25));
		return(RP_ERROR);
	}

	p27 = (int *)GetReusableParm(S(27), &status);
	if((p27 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(27));
		return(RP_ERROR);
	}

	p29 = (int *)GetReusableParm(S(29), &status);
	if((p29 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(29));
		return(RP_ERROR);
	}

	p34 = (char *)GetReusableParm(S(34), &status);
	if((p34 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(34));
		return(RP_ERROR);
	}

	p35 = (char *)GetReusableParm(S(35), &status);
	if((p35 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(35));
		return(RP_ERROR);
	}

	if(!HardwareOffline)
		*ret = (int)PMU_SegArb_ExampleB(D(0), D(1), D(2), D(3), I(4), I(5), D(6), D(7), I(8), D(9), D(10), I(11), I(12), p13, I(14), p15, I(16), p17, I(18), p19, I(20), p21, I(22), p23, I(24), p25, I(26), p27, I(28), p29, I(30), D(31), D(32), D(33), p34, p35, p36, I(37), p38, I(39), p40, I(41), p42, I(43), p44, I(45), p46, I(47), p48, I(49));

	add_result("PMU_SegArb_ExampleB", RETVAL_NAME, INT_P, ret, 1);
	add_result("PMU_SegArb_ExampleB", S(36), DOUBLE_P, p36, I(37));
	add_result("PMU_SegArb_ExampleB", S(38), DOUBLE_P, p38, I(39));
	add_result("PMU_SegArb_ExampleB", S(40), DOUBLE_P, p40, I(41));
	add_result("PMU_SegArb_ExampleB", S(42), DOUBLE_P, p42, I(43));
	add_result("PMU_SegArb_ExampleB", S(44), DOUBLE_P, p44, I(45));
	add_result("PMU_SegArb_ExampleB", S(46), INT_P, p46, I(47));
	add_result("PMU_SegArb_ExampleB", S(48), INT_P, p48, I(49));
	return(0);
}
