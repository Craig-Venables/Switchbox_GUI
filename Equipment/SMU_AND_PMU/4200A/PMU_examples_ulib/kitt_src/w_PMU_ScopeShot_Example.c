#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_ScopeShot_Example(double PW_Gate, double RiseTimeGate, double FallTimeGate, double DelayGate, double PW_Drain, double RiseTimeDrain, double FallTimeDrain, double DelayDrain, double Period, double MeasStartGate, double MeasStopGate, int PulseAverage, int LoadLineGate, int LoadLineDrain, double ResGate, double ResDrain, double AmplVGate, double BaseVGate, double AmplVDrain, double BaseVDrain, double VRangeGate, double IRangeGate, double LtdAuto_I_Gate, double VRangeDrain, double IRangeDrain, double LtdAuto_I_Drn, int GateCh, int DrainCh, int MaxSheetRows, double Thrshld_I_Gate, double ThresholdVoltGate, double ThresholdPwrGate, double ThresholdCurrDrain, double ThresholdVoltDrain, double ThresholdPwrDrain, double PrePulse, double PostPulse, int PMUMode, double SMU_V, double SMU_Irange, double SMU_Icomp, char * SMU_ID, char * PMU_ID, double *Gate_TimeStamp, int Gate_TimeStamp_Size, double *Gate_V, int Gate_V_Size, double *Gate_I, int Gate_I_Size, double *Drain_TimeStamp, int Drain_TimeStamp_Size, double *Drain_V, int Drain_V_Size, double *Drain_I, int Drain_I_Size, double *SpotMean_StartWind, int SpotMean_StartWind_Size, double *SpotMean_StopWind, int SpotMean_StopWind_Size, double *Gate_V_Ampl_SM, int Gate_V_Ampl_SM_Size, double *Gate_I_Ampl_SM, int Gate_I_Ampl_SM_Size, double *Drain_V_Ampl_SM, int Drain_V_Ampl_SM_Size, double *Drain_I_Ampl_SM, int Drain_I_Ampl_SM_Size, int *Status_Gate, int Status_Gate_Size, int *Status_Drain, int Status_Drain_Size);

int w_PMU_ScopeShot_Example(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	char *p41;
	char *p42;
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
	int *p67 = (int *)malloc(sizeof(int)*I(68));
	int *p69 = (int *)malloc(sizeof(int)*I(70));
	int status;
	extern void *GetReusableParm(char *search_name, int *status);

	p41 = (char *)GetReusableParm(S(41), &status);
	if((p41 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(41));
		return(RP_ERROR);
	}

	p42 = (char *)GetReusableParm(S(42), &status);
	if((p42 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(42));
		return(RP_ERROR);
	}

	if(!HardwareOffline)
		*ret = (int)PMU_ScopeShot_Example(D(0), D(1), D(2), D(3), D(4), D(5), D(6), D(7), D(8), D(9), D(10), I(11), I(12), I(13), D(14), D(15), D(16), D(17), D(18), D(19), D(20), D(21), D(22), D(23), D(24), D(25), I(26), I(27), I(28), D(29), D(30), D(31), D(32), D(33), D(34), D(35), D(36), I(37), D(38), D(39), D(40), p41, p42, p43, I(44), p45, I(46), p47, I(48), p49, I(50), p51, I(52), p53, I(54), p55, I(56), p57, I(58), p59, I(60), p61, I(62), p63, I(64), p65, I(66), p67, I(68), p69, I(70));

	add_result("PMU_ScopeShot_Example", RETVAL_NAME, INT_P, ret, 1);
	add_result("PMU_ScopeShot_Example", S(43), DOUBLE_P, p43, I(44));
	add_result("PMU_ScopeShot_Example", S(45), DOUBLE_P, p45, I(46));
	add_result("PMU_ScopeShot_Example", S(47), DOUBLE_P, p47, I(48));
	add_result("PMU_ScopeShot_Example", S(49), DOUBLE_P, p49, I(50));
	add_result("PMU_ScopeShot_Example", S(51), DOUBLE_P, p51, I(52));
	add_result("PMU_ScopeShot_Example", S(53), DOUBLE_P, p53, I(54));
	add_result("PMU_ScopeShot_Example", S(55), DOUBLE_P, p55, I(56));
	add_result("PMU_ScopeShot_Example", S(57), DOUBLE_P, p57, I(58));
	add_result("PMU_ScopeShot_Example", S(59), DOUBLE_P, p59, I(60));
	add_result("PMU_ScopeShot_Example", S(61), DOUBLE_P, p61, I(62));
	add_result("PMU_ScopeShot_Example", S(63), DOUBLE_P, p63, I(64));
	add_result("PMU_ScopeShot_Example", S(65), DOUBLE_P, p65, I(66));
	add_result("PMU_ScopeShot_Example", S(67), INT_P, p67, I(68));
	add_result("PMU_ScopeShot_Example", S(69), INT_P, p69, I(70));
	return(0);
}
