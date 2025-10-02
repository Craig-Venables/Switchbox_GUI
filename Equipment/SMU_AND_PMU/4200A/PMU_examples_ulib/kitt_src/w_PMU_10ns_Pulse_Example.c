#include <COM_usrlib.h>
__declspec(dllimport)
extern int HardwareOffline;
extern void outputf(char *fmt, ...);

int PMU_10ns_Pulse_Example(int pmu_ch, int pmu_id);

int w_PMU_10ns_Pulse_Example(callinfo_t *callinfo)
{
	int*ret = (int*)malloc(sizeof(int));
	if(!HardwareOffline)
		*ret = (int)PMU_10ns_Pulse_Example(I(0), I(1));

	add_result("PMU_10ns_Pulse_Example", RETVAL_NAME, INT_P, ret, 1);
	return(0);
}
