#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_SMU_Sweep_Example(double PulseWidthCh1, double RiseTimeCh1, double FallTimeCh1, double DelayCh1, double PulseWidthCh2, double RiseTimeCh2, double FallTimeCh2, double DelayCh2, double Period, int PulseAverage, int LoadLineCh1, int LoadLineCh2, double ResCh1, double ResCh2, double AmplVCh1, double BaseVCh1, double StartVCh2, double StopVCh2, double StepVCh2, double BaseVCh2, double VRangeCh1, double IRangeCh1, double LtdAutoCurrCh1, double VRangeCh2, double IRangeCh2, double LtdAutoCurrCh2, int PMUMode, double SMU_Irange, double SMU_Icomp, char * Ch1SMU_ID, char * Ch2SMU_ID, char * PMU_ID, int ExecMode, double *Ch1_V_Ampl, int Ch1_V_Ampl_Size, double *Ch1_I_Ampl, int Ch1_I_Ampl_Size, double *Ch1_V_Base, int Ch1_V_Base_Size, double *Ch1_I_Base, int Ch1_I_Base_Size, double *Ch2_V_Ampl, int Ch2_V_Ampl_Size, double *Ch2_I_Ampl, int Ch2_I_Ampl_Size, double *Ch2_V_Base, int Ch2_V_Base_Size, double *Ch2_I_Base, int Ch2_I_Base_Size, double *TimeStampAmpl_Ch1, int TimeStampAmpl_Ch1_Size, double *TimeStampBase_Ch1, int TimeStampBase_Ch1_Size, double *TimeStampAmpl_Ch2, int TimeStampAmpl_Ch2_Size, double *TimeStampBase_Ch2, int TimeStampBase_Ch2_Size, double *Status_Ch1, int Status_Ch1_Size, double *Status_Ch2, int Status_Ch2_Size, double *Ch2_SMU_Voltage, int Ch2SMUVoltageSize, double *Ch2_SMU_Current, int Ch2SMUCurrentSize, double *Ch1_SMU_Voltage, int Ch1SMUVoltageSize, double *Ch1_SMU_Current, int Ch1SMUCurrentSize);

int w_PMU_SMU_Sweep_Example(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	char *p29;
	char *p30;
	char *p31;
	double *p33 = (double *)malloc(sizeof(double)*I(34));
	double *p35 = (double *)malloc(sizeof(double)*I(36));
	double *p37 = (double *)malloc(sizeof(double)*I(38));
	double *p39 = (double *)malloc(sizeof(double)*I(40));
	double *p41 = (double *)malloc(sizeof(double)*I(42));
	double *p43 = (double *)malloc(sizeof(double)*I(44));
	double *p45 = (double *)malloc(sizeof(double)*I(46));
	double *p47 = (double *)malloc(sizeof(double)*I(48));
	double *p49 = (double *)malloc(sizeof(double)*I(50));
	double *p51 = (double *)malloc(sizeof(double)*I(52));
	double *p53 = (double *)malloc(sizeof(double)*I(54));
	double *p55 = (double *)malloc(sizeof(double)*I(56));
	double *p57 = (double *)malloc(sizeof(double)*I(58));
	double *p59 = (double *)malloc(sizeof(double)*I(60));
	double *p61 = (double *)malloc(sizeof(double)*I(62));
	double *p63 = (double *)malloc(sizeof(double)*I(64));
	double *p65 = (double *)malloc(sizeof(double)*I(66));
	double *p67 = (double *)malloc(sizeof(double)*I(68));
	int status;
	extern void *GetReusableParm(char *search_name, int *status);

	p29 = (char *)GetReusableParm(S(29), &status);
	if((p29 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(29));
		return(RP_ERROR);
	}

	p30 = (char *)GetReusableParm(S(30), &status);
	if((p30 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(30));
		return(RP_ERROR);
	}

	p31 = (char *)GetReusableParm(S(31), &status);
	if((p31 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(31));
		return(RP_ERROR);
	}

	if(!HardwareOffline)
		*ret = (int)PMU_SMU_Sweep_Example(D(0), D(1), D(2), D(3), D(4), D(5), D(6), D(7), D(8), I(9), I(10), I(11), D(12), D(13), D(14), D(15), D(16), D(17), D(18), D(19), D(20), D(21), D(22), D(23), D(24), D(25), I(26), D(27), D(28), p29, p30, p31, I(32), p33, I(34), p35, I(36), p37, I(38), p39, I(40), p41, I(42), p43, I(44), p45, I(46), p47, I(48), p49, I(50), p51, I(52), p53, I(54), p55, I(56), p57, I(58), p59, I(60), p61, I(62), p63, I(64), p65, I(66), p67, I(68));

	add_result("PMU_SMU_Sweep_Example", RETVAL_NAME, INT_P, ret, 1);
	add_result("PMU_SMU_Sweep_Example", S(33), DOUBLE_P, p33, I(34));
	add_result("PMU_SMU_Sweep_Example", S(35), DOUBLE_P, p35, I(36));
	add_result("PMU_SMU_Sweep_Example", S(37), DOUBLE_P, p37, I(38));
	add_result("PMU_SMU_Sweep_Example", S(39), DOUBLE_P, p39, I(40));
	add_result("PMU_SMU_Sweep_Example", S(41), DOUBLE_P, p41, I(42));
	add_result("PMU_SMU_Sweep_Example", S(43), DOUBLE_P, p43, I(44));
	add_result("PMU_SMU_Sweep_Example", S(45), DOUBLE_P, p45, I(46));
	add_result("PMU_SMU_Sweep_Example", S(47), DOUBLE_P, p47, I(48));
	add_result("PMU_SMU_Sweep_Example", S(49), DOUBLE_P, p49, I(50));
	add_result("PMU_SMU_Sweep_Example", S(51), DOUBLE_P, p51, I(52));
	add_result("PMU_SMU_Sweep_Example", S(53), DOUBLE_P, p53, I(54));
	add_result("PMU_SMU_Sweep_Example", S(55), DOUBLE_P, p55, I(56));
	add_result("PMU_SMU_Sweep_Example", S(57), DOUBLE_P, p57, I(58));
	add_result("PMU_SMU_Sweep_Example", S(59), DOUBLE_P, p59, I(60));
	add_result("PMU_SMU_Sweep_Example", S(61), DOUBLE_P, p61, I(62));
	add_result("PMU_SMU_Sweep_Example", S(63), DOUBLE_P, p63, I(64));
	add_result("PMU_SMU_Sweep_Example", S(65), DOUBLE_P, p65, I(66));
	add_result("PMU_SMU_Sweep_Example", S(67), DOUBLE_P, p67, I(68));
	return(0);
}
