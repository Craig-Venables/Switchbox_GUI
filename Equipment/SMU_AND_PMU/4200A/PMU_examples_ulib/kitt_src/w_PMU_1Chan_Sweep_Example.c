#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_1Chan_Sweep_Example(double PulseWidthCh1, double RiseTimeCh1, double FallTimeCh1, double Period, double DelayCh1, double SampleRate, double MeasStartPerc, double MeasStopPerc, int PulseAverage, int LoadLineCh1, double DUTResCh1, double VRangeCh1, double IRangeCh1, double StartVCh1, double StopVCh1, double StepVCh1, double BaseVCh1, int PMUMode, int Chan, char * PMU_ID, double *V_Ampl_Ch1, int V_Ampl_Ch1_Size, double *I_Ampl_Ch1, int I_Ampl_Ch1_Size, double *V_Base_Ch1, int V_Base_Ch1_Size, double *I_Base_Ch1, int I_Base_Ch1_Size, double *TimeStamp_Ch1, int TimeStamp_Ch1_Size, int *Status_Ch1, int Status_Ch1_Size);

int w_PMU_1Chan_Sweep_Example(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	char *p19;
	double *p20 = (double *)malloc(sizeof(double)*I(21));
	double *p22 = (double *)malloc(sizeof(double)*I(23));
	double *p24 = (double *)malloc(sizeof(double)*I(25));
	double *p26 = (double *)malloc(sizeof(double)*I(27));
	double *p28 = (double *)malloc(sizeof(double)*I(29));
	int *p30 = (int *)malloc(sizeof(int)*I(31));
	int status;
	extern void *GetReusableParm(char *search_name, int *status);

	p19 = (char *)GetReusableParm(S(19), &status);
	if((p19 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(19));
		return(RP_ERROR);
	}

	if(!HardwareOffline)
		*ret = (int)PMU_1Chan_Sweep_Example(D(0), D(1), D(2), D(3), D(4), D(5), D(6), D(7), I(8), I(9), D(10), D(11), D(12), D(13), D(14), D(15), D(16), I(17), I(18), p19, p20, I(21), p22, I(23), p24, I(25), p26, I(27), p28, I(29), p30, I(31));

	add_result("PMU_1Chan_Sweep_Example", RETVAL_NAME, INT_P, ret, 1);
	add_result("PMU_1Chan_Sweep_Example", S(20), DOUBLE_P, p20, I(21));
	add_result("PMU_1Chan_Sweep_Example", S(22), DOUBLE_P, p22, I(23));
	add_result("PMU_1Chan_Sweep_Example", S(24), DOUBLE_P, p24, I(25));
	add_result("PMU_1Chan_Sweep_Example", S(26), DOUBLE_P, p26, I(27));
	add_result("PMU_1Chan_Sweep_Example", S(28), DOUBLE_P, p28, I(29));
	add_result("PMU_1Chan_Sweep_Example", S(30), INT_P, p30, I(31));
	return(0);
}
