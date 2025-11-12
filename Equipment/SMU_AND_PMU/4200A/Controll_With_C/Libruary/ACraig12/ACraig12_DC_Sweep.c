/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig12_DC_Sweep
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 17
	ARGUMENTS:
		SMU_low,	char *,	Input,	"SMU1",	,	
		SMU_high,	char *,	Input,	"SMU2",	,	
		compCH,	int,	Input,	1,	1,	2
		measCH,	int,	Input,	2,	1,	2
		irange,	double,	Input,	0.0,	0.0,	1
		ilimit,	double,	Input,	0.0,	0.0,	1
		stepTime,	double,	Input,	0.0,	0.0,	
		widthTime,	double,	Input,	0.001,	0.0,	
		vamp,	double,	Input,	1,	-10,	10
		vamp_pts,	int,	Input,	300,	10,	1000
		vforce,	D_ARRAY_T,	Output,	,	,	
		vforce_pts,	int,	Input,	300,	10,	1000
		imeasd,	D_ARRAY_T,	Output,	,	,	
		imeasd_pts,	int,	Input,	300,	10,	1000
		timed,	D_ARRAY_T,	Output,	,	,	
		timed_pts,	int,	Input,	300,	10,	1000
		ClariusDebug,	int,	Input,	0,	0,	1
INCLUDES:
#include "keithley.h"
#include "nvm.h"

	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
ACraig12_DC_Sweep: DC voltage sweep using SMUs (KXCI compatible)

This module performs a DC voltage sweep using two SMUs. It applies a voltage
signal that sweeps from 0V to a peak voltage (vamp) and back to 0V, measuring
current and voltage at each point. The SMUs are connected to the DUT through RPMs.

This is a KXCI-compatible version of the original dcSweep module. Data is returned
via output arrays instead of PostDataDoubleBuffer().

Inputs:
- SMU_low: SMU identifier for low side (e.g., "SMU1")
- SMU_high: SMU identifier for high side (e.g., "SMU2")
- compCH: Channel (1 or 2) to apply compliance
- measCH: Channel (1 or 2) to measure current
- irange: Current range (0.0 for AUTO)
- ilimit: Current limit (A)
- stepTime: Time for each sweep step (s)
- widthTime: Time to hold voltage at peak (s)
- vamp: Peak voltage (V, can be positive or negative)
- vamp_pts: Number of points in arrays
- vforce_pts: Size of vforce output array
- imeasd_pts: Size of imeasd output array
- timed_pts: Size of timed output array
- ClariusDebug: Enable debug output (1=enabled, 0=disabled)

Outputs:
- vforce: Array of forced voltages (V) - corrected for voltage drop
- imeasd: Array of measured currents (A)
- timed: Array of timestamps (s)

The sweep performs:
1. First sweep: 0V → vamp (upward sweep)
2. Hold at vamp for widthTime
3. Second sweep: vamp → 0V (downward sweep)

Data is returned via output arrays (KXCI compatible).

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "nvm.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

BOOL LPTIsInCurrentConfiguration(char* hrid);

/* USRLIB MODULE MAIN FUNCTION */
int ACraig12_DC_Sweep( 
    char *SMU_low, char *SMU_high, int compCH, int measCH, 
    double irange, double ilimit, double stepTime, double widthTime, 
    double vamp, int vamp_pts, 
    double *vforce, int vforce_pts, 
    double *imeasd, int imeasd_pts, 
    double *timed, int timed_pts,
    int ClariusDebug )
{
/* USRLIB MODULE CODE */
    int debug = 0;
    int SMU_low_Id, SMU_high_Id;
    int pts, i;
    double vmeasd[1000];
    double minTime = 0.0;
    double max_ilimit = 0.1;
    
    if (ClariusDebug == 1) { debug = 1; } else { debug = 0; }
    if(debug) printf("\n\nACraig12_DC_Sweep: starts\n");
    
    // Validate array sizes match
    if(vforce_pts != vamp_pts || imeasd_pts != vamp_pts || timed_pts != vamp_pts)
    {
        if(debug) printf("ERROR: Array sizes must match vamp_pts (%d)\n", vamp_pts);
        return -3;
    }
    
    // Validate array sizes are sufficient
    if(vforce_pts < vamp_pts || imeasd_pts < vamp_pts || timed_pts < vamp_pts)
    {
        if(debug) printf("ERROR: Output array sizes too small (need %d, got vforce=%d, imeasd=%d, timed=%d)\n", 
                         vamp_pts, vforce_pts, imeasd_pts, timed_pts);
        return -3;
    }
    
    // Initialize output arrays to zero
    for(i = 0; i < vforce_pts; i++)
    {
        vforce[i] = 0.0;
        imeasd[i] = 0.0;
        timed[i] = 0.0;
    }
    
    // Find High SMU
    getinstid(SMU_high, &SMU_high_Id);
    if (!LPTIsInCurrentConfiguration(SMU_high))
    {
        if(debug) printf("ERROR: SMU %s is not in system configuration\n", SMU_high);
        return -1;
    }
    
    // Find Low SMU
    getinstid(SMU_low, &SMU_low_Id);
    if (!LPTIsInCurrentConfiguration(SMU_low))
    {
        if(debug) printf("ERROR: SMU %s is not in system configuration\n", SMU_low);
        return -2;
    }
    
    if(fabs(ilimit) > max_ilimit)
    {
        if(debug) printf("ERROR: ilimit (%.6g) exceeds maximum (%.6g)\n", ilimit, max_ilimit);
        return -3;
    }
    
    // Initialize NVM using no PMUs
    initNVMST(0);
    
    setmode(SMU_low_Id, KI_LIM_MODE, KI_VALUE);
    setmode(SMU_high_Id, KI_LIM_MODE, KI_VALUE);
    
    if(stepTime < minTime) stepTime = 0.0;
    if(widthTime < minTime) widthTime = 0.0;
    
    if(debug) printf("Switching RPMs for SMU test\n");
    
    // Configure RPMs for SMU mode
    rpm_config(PMU1, 1, KI_RPM_PATHWAY, KI_RPM_SMU);
    rpm_config(PMU1, 2, KI_RPM_PATHWAY, KI_RPM_SMU);
    
    if(debug) printf("DC testing\n");
    
    // Set compliance limits on SMUs
    if(ilimit != 0.0) 
    {
        limiti(SMU_high_Id, ilimit);
        limiti(SMU_low_Id, ilimit);
        if(debug) printf("Set current limit to %.6g A\n", ilimit);
    }
    else
    {
        // Set limit to max current limit value
        limiti(SMU_high_Id, max_ilimit);
        limiti(SMU_low_Id, max_ilimit);
        if(debug) printf("Set current limit to max (%.6g A)\n", max_ilimit);
    }
    
    enable(TIMER1);
    
    pts = (int)(vamp_pts / 2.0) - 1;
    
    if(irange != 0)
    {  
        rangei(SMU_low_Id, irange);
        rangei(SMU_high_Id, irange);
        if(debug) printf("Set current range to %.6g A\n", irange);
    }
    else
    {
        setauto(SMU_high_Id);
        setauto(SMU_low_Id);
        if(debug) printf("Using AUTO current range\n");
    }
    
    // Initialize SMUs to 0V
    forcev(SMU_high_Id, 0.0);
    forcev(SMU_low_Id, 0.0);
    
    // Get forced voltage array
    rtfary(vforce);
    
    // Reset to 0V
    forcev(SMU_low_Id, 0.0);
    forcev(SMU_high_Id, 0.0);
    
    if(debug) printf("First sweep: 0V -> %.6g V (%d points)\n", vamp, pts);
    
    // Measure current
    if(1 == measCH)
        smeasi(SMU_low_Id, imeasd);
    else
        smeasi(SMU_high_Id, imeasd);
    
    // Get timestamps
    smeast(TIMER1, timed);
    
    // Get measured voltage
    smeasv(SMU_low_Id, vmeasd);
    
    // Perform upward sweep
    sweepv(SMU_high_Id, 0, vamp, pts, stepTime);
    
    // Hold at peak voltage
    if(widthTime > 0)
    {
        if(debug) printf("Holding at peak voltage for %.6g s\n", widthTime);
        rdelay(widthTime);
    }
    
    // Perform downward sweep
    if(debug) printf("Second sweep: %.6g V -> 0V (%d points)\n", vamp, vamp_pts - pts - 2);
    sweepv(SMU_high_Id, vamp, 0, vamp_pts - pts - 2, stepTime);
    
    // Return to 0V
    forcev(SMU_high_Id, 0.0);
    forcev(SMU_low_Id, 0.0);
    
    devint();
    
    // Process data: correct vforce for voltage drop and adjust current sign
    for(i = 0; i < vamp_pts - 1; i++ )
    {
        if(debug && (i < 5 || i >= vamp_pts - 6))
        {
            printf("Index: %d Time: %.6g Vforce: %.6g Vmeasd: %.6g IMeas: %.6g\n", 
                   i, timed[i], vforce[i], vmeasd[i], imeasd[i]);
        }
        
        // Correct forced voltage for voltage drop
        vforce[i] = vforce[i] - vmeasd[i];
        
        // Adjust current sign if measuring on CH1
        if(1 == measCH) imeasd[i] *= -1.0;
    }
    
    if(debug) printf("Done, switching RPMs back to PMU mode\n");
    
    // Switch RPMs back to PMU mode
    rpm_config(PMU1, 1, KI_RPM_PATHWAY, KI_RPM_PULSE);
    rpm_config(PMU1, 2, KI_RPM_PATHWAY, KI_RPM_PULSE);
    
    if(debug) 
    {
        printf("ACraig12_DC_Sweep: complete, returning %d data points\n", vamp_pts - 1);
        printf("Returning 0 (success)\n");
    }
    
    return 0;  // Return 0 on success (KXCI convention)
/* USRLIB MODULE END  */
} 		/* End ACraig12_DC_Sweep.c */


