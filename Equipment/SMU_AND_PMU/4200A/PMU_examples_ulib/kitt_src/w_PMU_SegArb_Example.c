#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_SegArb_Example(double VRangeCh1, double IRangeCh1, double VRangeCh2, double IRangeCh2, int NumWaveforms, double DUTResCh1, double DUTResCh2, int MaxSheetPoints, int NumSegments, double *SegTime, int SegTime_size, double *StartVCh1, int StartVCh1_size, double *StopVCh1, int StopVCh1_size, double *StartVCh2, int StartVCh2_size, double *StopVCh2, int StopVCh2_size, int *SSRCtrlCh1, int SSRCtrlCh1_size, int *SSRCtrlCh2, int SSRCtrlCh2_size, int *SegTrigOut, int SegTrigOut_size, double SMU_V, double SMU_Irange, double SMU_Icomp, char * SMU_ID, char * PMU_ID, double *VMeasCh1, int VMeasCh1_size, double *IMeasCh1, int IMeasCh1_size, double *VMeasCh2, int VMeasCh2_size, double *IMeasCh2, int IMeasCh2_size, double *TimeOutput, int TimeOutput_size, int *StatusCh1, int StatusCh1_size, int *StatusCh2, int StatusCh2_size);

int w_PMU_SegArb_Example(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	double *p9;
	double *p11;
	double *p13;
	double *p15;
	double *p17;
	int *p19;
	int *p21;
	int *p23;
	char *p28;
	char *p29;
	double *p30 = (double *)malloc(sizeof(double)*I(31));
	double *p32 = (double *)malloc(sizeof(double)*I(33));
	double *p34 = (double *)malloc(sizeof(double)*I(35));
	double *p36 = (double *)malloc(sizeof(double)*I(37));
	double *p38 = (double *)malloc(sizeof(double)*I(39));
	int *p40 = (int *)malloc(sizeof(int)*I(41));
	int *p42 = (int *)malloc(sizeof(int)*I(43));
	int status;
	extern void *GetReusableParm(char *search_name, int *status);

	p9 = (double *)GetReusableParm(S(9), &status);
	if((p9 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(9));
		return(RP_ERROR);
	}

	p11 = (double *)GetReusableParm(S(11), &status);
	if((p11 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(11));
		return(RP_ERROR);
	}

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

	p19 = (int *)GetReusableParm(S(19), &status);
	if((p19 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(19));
		return(RP_ERROR);
	}

	p21 = (int *)GetReusableParm(S(21), &status);
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

	p28 = (char *)GetReusableParm(S(28), &status);
	if((p28 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(28));
		return(RP_ERROR);
	}

	p29 = (char *)GetReusableParm(S(29), &status);
	if((p29 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(29));
		return(RP_ERROR);
	}

	if(!HardwareOffline)
		*ret = (int)PMU_SegArb_Example(D(0), D(1), D(2), D(3), I(4), D(5), D(6), I(7), I(8), p9, I(10), p11, I(12), p13, I(14), p15, I(16), p17, I(18), p19, I(20), p21, I(22), p23, I(24), D(25), D(26), D(27), p28, p29, p30, I(31), p32, I(33), p34, I(35), p36, I(37), p38, I(39), p40, I(41), p42, I(43));

	add_result("PMU_SegArb_Example", RETVAL_NAME, INT_P, ret, 1);
	add_result("PMU_SegArb_Example", S(30), DOUBLE_P, p30, I(31));
	add_result("PMU_SegArb_Example", S(32), DOUBLE_P, p32, I(33));
	add_result("PMU_SegArb_Example", S(34), DOUBLE_P, p34, I(35));
	add_result("PMU_SegArb_Example", S(36), DOUBLE_P, p36, I(37));
	add_result("PMU_SegArb_Example", S(38), DOUBLE_P, p38, I(39));
	add_result("PMU_SegArb_Example", S(40), INT_P, p40, I(41));
	add_result("PMU_SegArb_Example", S(42), INT_P, p42, I(43));
	return(0);
}
