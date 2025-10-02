#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_IV_sweep_Example(double PulseWidthGate, double RiseTimeGate, double FallTimeGate, double DelayGate, double PulseWidthDrain, double RiseTimeDrain, double FallTimeDrain, double DelayDrain, double Period, double MeasStartGate, double MeasStopGate, int PulseAverage, int LoadLineGate, int LoadLineDrain, double ResGate, double ResDrain, double AmplVGate, double BaseVGate, double StartVDrain, double StopVDrain, double StepVDrain, double BaseVDrain, double VRangeGate, double IRangeGate, int LtdAutoCurrGate, double VRangeDrain, double IRangeDrain, int LtdAutoCurrDrain, int GateCh, int DrainCh, double ThresholdCurrGate, double ThresholdVoltGate, double ThresholdPwrGate, double ThresholdCurrDrain, double ThresholdVoltDrain, double ThresholdPwrDrain, int PMUMode, double SMU_V, double SMU_Irange, double SMU_Icomp, char * SMU_ID, char * PMU_ID, double *Gate_V_Ampl, int Gate_V_Ampl_Size, double *Gate_I_Ampl, int Gate_I_Ampl_Size, double *Gate_V_Base, int Gate_V_Base_Size, double *Gate_I_Base, int Gate_I_Base_Size, double *Drain_V_Ampl, int Drain_V_Ampl_Size, double *Drain_I_Ampl, int Drain_I_Ampl_Size, double *Drain_V_Base, int Drain_V_Base_Size, double *Drain_I_Base, int Drain_I_Base_Size, double *TimeStampAmpl_Gate, int TimeStampAmpl_Gate_Size, double *TimeStampBase_Gate, int TimeStampBase_Gate_Size, double *TimeStampAmpl_Drain, int TimeStampAmpl_Drain_Size, double *TimeStampBase_Drain, int TimeStampBase_Drain_Size);

int w_PMU_IV_sweep_Example(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	char *p40;
	char *p41;
	double *p42 = (double *)malloc(sizeof(double)*I(43));
	double *p44 = (double *)malloc(sizeof(double)*I(45));
	double *p46 = (double *)malloc(sizeof(double)*I(47));
	double *p48 = (double *)malloc(sizeof(double)*I(49));
	double *p50 = (double *)malloc(sizeof(double)*I(51));
	double *p52 = (double *)malloc(sizeof(double)*I(53));
	double *p54 = (double *)malloc(sizeof(double)*I(55));
	double *p56 = (double *)malloc(sizeof(double)*I(57));
	double *p58 = (double *)malloc(sizeof(double)*I(59));
	double *p60 = (double *)malloc(sizeof(double)*I(61));
	double *p62 = (double *)malloc(sizeof(double)*I(63));
	double *p64 = (double *)malloc(sizeof(double)*I(65));
	int status;
	extern void *GetReusableParm(char *search_name, int *status);

	p40 = (char *)GetReusableParm(S(40), &status);
	if((p40 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(40));
		return(RP_ERROR);
	}

	p41 = (char *)GetReusableParm(S(41), &status);
	if((p41 == NULL) && (status < 0))
	{
		outputf("\"%s\" ", S(41));
		return(RP_ERROR);
	}

	if(!HardwareOffline)
		*ret = (int)PMU_IV_sweep_Example(D(0), D(1), D(2), D(3), D(4), D(5), D(6), D(7), D(8), D(9), D(10), I(11), I(12), I(13), D(14), D(15), D(16), D(17), D(18), D(19), D(20), D(21), D(22), D(23), I(24), D(25), D(26), I(27), I(28), I(29), D(30), D(31), D(32), D(33), D(34), D(35), I(36), D(37), D(38), D(39), p40, p41, p42, I(43), p44, I(45), p46, I(47), p48, I(49), p50, I(51), p52, I(53), p54, I(55), p56, I(57), p58, I(59), p60, I(61), p62, I(63), p64, I(65));

	add_result("PMU_IV_sweep_Example", RETVAL_NAME, INT_P, ret, 1);
	add_result("PMU_IV_sweep_Example", S(42), DOUBLE_P, p42, I(43));
	add_result("PMU_IV_sweep_Example", S(44), DOUBLE_P, p44, I(45));
	add_result("PMU_IV_sweep_Example", S(46), DOUBLE_P, p46, I(47));
	add_result("PMU_IV_sweep_Example", S(48), DOUBLE_P, p48, I(49));
	add_result("PMU_IV_sweep_Example", S(50), DOUBLE_P, p50, I(51));
	add_result("PMU_IV_sweep_Example", S(52), DOUBLE_P, p52, I(53));
	add_result("PMU_IV_sweep_Example", S(54), DOUBLE_P, p54, I(55));
	add_result("PMU_IV_sweep_Example", S(56), DOUBLE_P, p56, I(57));
	add_result("PMU_IV_sweep_Example", S(58), DOUBLE_P, p58, I(59));
	add_result("PMU_IV_sweep_Example", S(60), DOUBLE_P, p60, I(61));
	add_result("PMU_IV_sweep_Example", S(62), DOUBLE_P, p62, I(63));
	add_result("PMU_IV_sweep_Example", S(64), DOUBLE_P, p64, I(65));
	return(0);
}
