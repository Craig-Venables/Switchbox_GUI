#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_PulseWaveform_FileSave_Example(double PulseTop, double RiseTime, double FallTime, double BaseTime, double DelayTime, long MaxSheetPoints, long MaxFilePoints, double Ch1_VRange, double Ch1_IRange, double Ch1_V_Ampl, double Ch1_V_Base, double Ch2_VRange, double Ch2_IRange, double Ch2_StartV, double Ch2_StopV, double Ch2_StepV, double Ch2_V_Base, double Ch1_Res, double Ch2_Res, double SMU_V, double SMU_Irange, double SMU_Icomp, char * SMU_ID, char * PMU_ID, int SaveFile, int AppendTimeToFilename, char * Filename, double *TimeStamp, int TimeStampSize, double *Ch1_Vmeas, int Ch1_VmeasSize, double *Ch1_Imeas, int Ch1_ImeasSize, double *Ch2_Vmeas, int Ch2_VmeasSize, double *Ch2_Imeas, int Ch2_ImeasSize);

int w_PMU_PulseWaveform_FileSave_Example(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	char *p22;
	char *p23;
	char *p26;
	double *p27 = (double *)malloc(sizeof(double)*I(28));
	double *p29 = (double *)malloc(sizeof(double)*I(30));
	double *p31 = (double *)malloc(sizeof(double)*I(32));
	double *p33 = (double *)malloc(sizeof(double)*I(34));
	double *p35 = (double *)malloc(sizeof(double)*I(36));
	int status;
	extern void *GetReusableParm(char *search_name, int *status);

	p22 = (char *)GetReusableParm(S(22), &status);
	if((p22 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(22));
		return(RP_ERROR);
	}

	p23 = (char *)GetReusableParm(S(23), &status);
	if((p23 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(23));
		return(RP_ERROR);
	}

	p26 = (char *)GetReusableParm(S(26), &status);
	if((p26 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(26));
		return(RP_ERROR);
	}

	if(!HardwareOffline)
		*ret = (int)PMU_PulseWaveform_FileSave_Example(D(0), D(1), D(2), D(3), D(4), L(5), L(6), D(7), D(8), D(9), D(10), D(11), D(12), D(13), D(14), D(15), D(16), D(17), D(18), D(19), D(20), D(21), p22, p23, I(24), I(25), p26, p27, I(28), p29, I(30), p31, I(32), p33, I(34), p35, I(36));

	add_result("PMU_PulseWaveform_FileSave_Example", RETVAL_NAME, INT_P, ret, 1);
	add_result("PMU_PulseWaveform_FileSave_Example", S(27), DOUBLE_P, p27, I(28));
	add_result("PMU_PulseWaveform_FileSave_Example", S(29), DOUBLE_P, p29, I(30));
	add_result("PMU_PulseWaveform_FileSave_Example", S(31), DOUBLE_P, p31, I(32));
	add_result("PMU_PulseWaveform_FileSave_Example", S(33), DOUBLE_P, p33, I(34));
	add_result("PMU_PulseWaveform_FileSave_Example", S(35), DOUBLE_P, p35, I(36));
	return(0);
}
