#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_1Chan_Waveform_Example(double width, double rise, double fall, double delay, double period, double voltsSourceRng, double currentMeasureRng, double DUTRes, double startV, double stopV, double stepV, double baseV, int acqType, int LLEComp, double preDataPct, double postDataPct, int pulseAvgCnt, double SampleRate, int PMUMode, int chan, char * PMU_ID, double *V_Meas, int size_V_Meas, double *I_Meas, int size_I_Meas, double *T_Stamp, int size_T_Stamp, int *Status, int size_Status);

int w_PMU_1Chan_Waveform_Example(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	char *p20;
	double *p21 = (double *)malloc(sizeof(double)*I(22));
	double *p23 = (double *)malloc(sizeof(double)*I(24));
	double *p25 = (double *)malloc(sizeof(double)*I(26));
	int *p27 = (int *)malloc(sizeof(int)*I(28));
	int status;
	extern void *GetReusableParm(char *search_name, int *status);

	p20 = (char *)GetReusableParm(S(20), &status);
	if((p20 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(20));
		return(RP_ERROR);
	}

	if(!HardwareOffline)
		*ret = (int)PMU_1Chan_Waveform_Example(D(0), D(1), D(2), D(3), D(4), D(5), D(6), D(7), D(8), D(9), D(10), D(11), I(12), I(13), D(14), D(15), I(16), D(17), I(18), I(19), p20, p21, I(22), p23, I(24), p25, I(26), p27, I(28));

	add_result("PMU_1Chan_Waveform_Example", RETVAL_NAME, INT_P, ret, 1);
	add_result("PMU_1Chan_Waveform_Example", S(21), DOUBLE_P, p21, I(22));
	add_result("PMU_1Chan_Waveform_Example", S(23), DOUBLE_P, p23, I(24));
	add_result("PMU_1Chan_Waveform_Example", S(25), DOUBLE_P, p25, I(26));
	add_result("PMU_1Chan_Waveform_Example", S(27), INT_P, p27, I(28));
	return(0);
}
