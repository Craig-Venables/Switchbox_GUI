/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig12_PMU_SMU_Sweep
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 70
	ARGUMENTS:
		PulseWidthCh1,	double,	Input,	1e-6,	60e-9,	.999999
		RiseTimeCh1,	double,	Input,	40e-9,	20e-9,	0.033
		FallTimeCh1,	double,	Input,	40e-9,	20e-9,	0.033
		DelayCh1,	double,	Input,	0,	0,	.999999
		PulseWidthCh2,	double,	Input,	1e-6,	60e-9,	.999999
		RiseTimeCh2,	double,	Input,	100e-9,	20e-9,	.033
		FallTimeCh2,	double,	Input,	100e-9,	20e-9,	.033
		DelayCh2,	double,	Input,	0,	0,	.999999
		Period,	double,	Input,	2e-6,	80e-9,	1
		PulseAverage,	int,	Input,	1,	1,	10000
		LoadLineCh1,	int,	Input,	0,	0,	1
		LoadLineCh2,	int,	Input,	0,	0,	1
		ResCh1,	double,	Input,	1e6,	1,	1e6
		ResCh2,	double,	Input,	1E6,	1,	1E6
		AmplVCh1,	double,	Input,	2,	-40,	40
		BaseVCh1,	double,	Input,	0,	-40,	40
		StartVCh2,	double,	Input,	0,	-40,	40
		StopVCh2,	double,	Input,	5,	-40,	40
		StepVCh2,	double,	Input,	0.1,	.001,	40
		BaseVCh2,	double,	Input,	0,	-40,	40
		VRangeCh1,	double,	Input,	10,	5,	40
		IRangeCh1,	double,	Input,	0.01,	1e-7,	.8
		LtdAutoCurrCh1,	double,	Input,	0,	0,	1
		VRangeCh2,	double,	Input,	10,	5,	40
		IRangeCh2,	double,	Input,	0.2,	1e-7,	.8
		LtdAutoCurrCh2,	double,	Input,	0,	0,	1
		PMUMode,	int,	Input,	0,	0,	2
		SMU_Irange,	double,	Input,	.01,	1e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		Ch1SMU_ID,	char *,	Input,	"SMU1",	,	
		Ch2SMU_ID,	char *,	Input,	"SMU2",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		ExecMode,	int,	Input,	0,	0,	2
		Ch1_V_Ampl,	D_ARRAY_T,	Output,	,	,	
		Ch1_V_Ampl_Size,	int,	Input,	100,	1,	10000
		Ch1_I_Ampl,	D_ARRAY_T,	Output,	,	,	
		Ch1_I_Ampl_Size,	int,	Input,	100,	1,	10000
		Ch1_V_Base,	D_ARRAY_T,	Output,	,	,	
		Ch1_V_Base_Size,	int,	Input,	100,	1,	10000
		Ch1_I_Base,	D_ARRAY_T,	Output,	,	,	
		Ch1_I_Base_Size,	int,	Input,	100,	1,	10000
		Ch2_V_Ampl,	D_ARRAY_T,	Output,	,	,	
		Ch2_V_Ampl_Size,	int,	Input,	100,	1,	10000
		Ch2_I_Ampl,	D_ARRAY_T,	Output,	,	,	
		Ch2_I_Ampl_Size,	int,	Input,	100,	1,	10000
		Ch2_V_Base,	D_ARRAY_T,	Output,	,	,	
		Ch2_V_Base_Size,	int,	Input,	100,	1,	10000
		Ch2_I_Base,	D_ARRAY_T,	Output,	,	,	
		Ch2_I_Base_Size,	int,	Input,	100,	1,	10000
		TimeStampAmpl_Ch1,	D_ARRAY_T,	Output,	,	,	
		TimeStampAmpl_Ch1_Size,	int,	Input,	100,	1,	10000
		TimeStampBase_Ch1,	D_ARRAY_T,	Output,	,	,	
		TimeStampBase_Ch1_Size,	int,	Input,	100,	1,	10000
		TimeStampAmpl_Ch2,	D_ARRAY_T,	Output,	,	,	
		TimeStampAmpl_Ch2_Size,	int,	Input,	100,	1,	10000
		TimeStampBase_Ch2,	D_ARRAY_T,	Output,	,	,	
		TimeStampBase_Ch2_Size,	int,	Input,	100,	1,	10000
		Status_Ch1,	D_ARRAY_T,	Output,	,	,	
		Status_Ch1_Size,	int,	Input,	100,	1,	10000
		Status_Ch2,	D_ARRAY_T,	Output,	,	,	
		Status_Ch2_Size,	int,	Input,	100,	1,	10000
		Ch2_SMU_Voltage,	D_ARRAY_T,	Output,	,	,	
		Ch2SMUVoltageSize,	int,	Input,	100,	1,	10000
		Ch2_SMU_Current,	D_ARRAY_T,	Output,	,	,	
		Ch2SMUCurrentSize,	int,	Input,	100,	1,	10000
		Ch1_SMU_Voltage,	D_ARRAY_T,	Output,	,	,	
		Ch1SMUVoltageSize,	int,	Input,	100,	1,	10000
		Ch1_SMU_Current,	D_ARRAY_T,	Output,	,	,	
		Ch1SMUCurrentSize,	int,	Input,	100,	1,	10000
		ClariusDebug,	int,	Input,	0,	0,	1
INCLUDES:
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <float.h>

BOOL LPTIsInCurrentConfiguration(char* hrid);

#define MaxSamplesPerAtoD 1000000
#define PulseAndSMUMode 0
#define PulseOnlyMode 1
#define SMUOnlyMode 2

#define ERR_PMU_EXAMPLES_WRONGCARDID -17001
#define ERR_PMU_EXAMPLES_CARDHANDLEFAIL -17002
#define ERR_PMU_EXAMPLES_OUTPUT_ARRAY_TOO_SMALL -17110
#define ERR_PMU_EXAMPLES_MEAS_EARLY -17100

	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
ACraig12_PMU_SMU_Sweep: Combined PMU pulse and SMU DC sweep (KXCI compatible)

This module performs both PMU pulse I-V measurements and SMU DC measurements,
allowing comparison between pulse and DC characteristics. It supports three
execution modes:
- Mode 0 (PulseAndSMUMode): Perform both PMU pulse test and SMU DC test
- Mode 1 (PulseOnlyMode): Perform only PMU pulse test
- Mode 2 (SMUOnlyMode): Perform only SMU DC test

PMU Pulse Test:
- CH1: Fixed amplitude pulse train (constant voltage)
- CH2: Swept amplitude pulse train (voltage sweep)
- Both channels measure voltage and current at pulse top and base
- Uses spot mean measurements (65-80% of pulse top)

SMU DC Test:
- CH1 SMU: Fixed DC bias
- CH2 SMU: Swept DC voltage
- Measures DC voltage and current

This is a KXCI-compatible version that returns data via output arrays instead
of PostDataDoubleBuffer().

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */

int ACraig12_PMU_SMU_Sweep( 
    double PulseWidthCh1, double RiseTimeCh1, double FallTimeCh1, double DelayCh1, 
    double PulseWidthCh2, double RiseTimeCh2, double FallTimeCh2, double DelayCh2, 
    double Period, int PulseAverage, int LoadLineCh1, int LoadLineCh2, 
    double ResCh1, double ResCh2, double AmplVCh1, double BaseVCh1, 
    double StartVCh2, double StopVCh2, double StepVCh2, double BaseVCh2, 
    double VRangeCh1, double IRangeCh1, double LtdAutoCurrCh1, 
    double VRangeCh2, double IRangeCh2, double LtdAutoCurrCh2, 
    int PMUMode, double SMU_Irange, double SMU_Icomp, 
    char *Ch1SMU_ID, char *Ch2SMU_ID, char *PMU_ID, int ExecMode, 
    double *Ch1_V_Ampl, int Ch1_V_Ampl_Size, 
    double *Ch1_I_Ampl, int Ch1_I_Ampl_Size, 
    double *Ch1_V_Base, int Ch1_V_Base_Size, 
    double *Ch1_I_Base, int Ch1_I_Base_Size, 
    double *Ch2_V_Ampl, int Ch2_V_Ampl_Size, 
    double *Ch2_I_Ampl, int Ch2_I_Ampl_Size, 
    double *Ch2_V_Base, int Ch2_V_Base_Size, 
    double *Ch2_I_Base, int Ch2_I_Base_Size, 
    double *TimeStampAmpl_Ch1, int TimeStampAmpl_Ch1_Size, 
    double *TimeStampBase_Ch1, int TimeStampBase_Ch1_Size, 
    double *TimeStampAmpl_Ch2, int TimeStampAmpl_Ch2_Size, 
    double *TimeStampBase_Ch2, int TimeStampBase_Ch2_Size, 
    double *Status_Ch1, int Status_Ch1_Size, 
    double *Status_Ch2, int Status_Ch2_Size, 
    double *Ch2_SMU_Voltage, int Ch2SMUVoltageSize, 
    double *Ch2_SMU_Current, int Ch2SMUCurrentSize, 
    double *Ch1_SMU_Voltage, int Ch1SMUVoltageSize, 
    double *Ch1_SMU_Current, int Ch1SMUCurrentSize,
    int ClariusDebug )
{
/* USRLIB MODULE CODE */
    int debug = 0;
    int status;
    int i;
    int NumSweepPts;
    int NumSamplesTopCh1; 
    int NumSamplesBaseCh1;
    int NumSamplesPeriodCh1;
    int NumSamplesSweepCh1;
    int InstId;
    int Ch1SMUId;
    int Ch2SMUId;
    int TestMode;
    int Stat;
    int CardChannel1 = 1;
    int CardChannel2 = 2;
    int ExecStatus = 0;
    int RPMstat1, RPMstat2;
    
    double *Ch1_V_All; 
    double *Ch1_I_All;
    double *Ch1_T_All;
    double *Ch1_V_High;
    double *Ch1_I_High;
    double *Ch1_T_High;
    double *Ch1_V_Low;
    double *Ch1_I_Low;
    double *Ch1_T_Low;
    double *Ch2_V_All;
    double *Ch2_I_All;
    double *Ch2_T_All;
    double *Ch2_V_High;
    double *Ch2_I_High;
    double *Ch2_T_High;
    double *Ch2_V_Low;
    double *Ch2_I_Low;
    double *Ch2_T_Low;
    double sweepdelay = 0.0;
    double RateFactor;
    double SampleRate;
    double elapsedt;
    
    //Ch1 measure timing parameters
    double PulseTopTimeCh1;
    double PulseBaseTimeCh1;
    double PulseTopMeasTimeCh1;
    double PulseBaseMeasTimeCh1;
    double PulseTopMeasStartCh1;
    double PulseTopMeasStopCh1;
    
    //Ch2 measure timing parameters
    double PulseTopTimeCh2;
    double PulseTopStartTimeCh2;
    double PulseTopStopTimeCh2;
    
    double MeasStartPercCh2;
    double MeasStopPercCh2;
    double MeasStartPercCh1 = 0.65;
    double MeasStopPercCh1 = 0.80;
    
    unsigned long *Ch1_S_All;
    unsigned long *Ch2_S_All;
    
    int SMUPresent;
    int RPMPresent = 0;
    int memAllocated = 0;
    
    if (ClariusDebug == 1) { debug = 1; } else { debug = 0; }
    if(debug) printf("\n\nACraig12_PMU_SMU_Sweep: starts\n");
    
    //Initialize variables
    SampleRate = 200E+6;
    RateFactor = 0.0;
    SMUPresent = 0;
    
    // Initialize output arrays to NaN (will be overwritten with actual data)
    for(i = 0; i < Ch1_V_Ampl_Size; i++)
    {
        Ch1_V_Ampl[i] = DBL_NAN;
        Ch1_I_Ampl[i] = DBL_NAN;
        Ch1_V_Base[i] = DBL_NAN;
        Ch1_I_Base[i] = DBL_NAN;
        TimeStampAmpl_Ch1[i] = DBL_NAN;
        TimeStampBase_Ch1[i] = DBL_NAN;
        Status_Ch1[i] = DBL_NAN;
    }
    for(i = 0; i < Ch2_V_Ampl_Size; i++)
    {
        Ch2_V_Ampl[i] = DBL_NAN;
        Ch2_I_Ampl[i] = DBL_NAN;
        Ch2_V_Base[i] = DBL_NAN;
        Ch2_I_Base[i] = DBL_NAN;
        TimeStampAmpl_Ch2[i] = DBL_NAN;
        TimeStampBase_Ch2[i] = DBL_NAN;
        Status_Ch2[i] = DBL_NAN;
    }
    for(i = 0; i < Ch1SMUVoltageSize; i++)
    {
        Ch1_SMU_Voltage[i] = DBL_NAN;
        Ch1_SMU_Current[i] = DBL_NAN;
    }
    for(i = 0; i < Ch2SMUVoltageSize; i++)
    {
        Ch2_SMU_Voltage[i] = DBL_NAN;
        Ch2_SMU_Current[i] = DBL_NAN;
    }
    
    //Check: is requested PMU card in the chassis?
    if (!LPTIsInCurrentConfiguration(PMU_ID))
    {
        if(debug) printf("Instrument %s is not in system configuration\n", PMU_ID);
        return ERR_PMU_EXAMPLES_WRONGCARDID;
    }
    
    //Convert card string into identifying instrument card number
    getinstid(PMU_ID, &InstId);
    if (-1 == InstId)
    {
        if(debug) printf("Failed to get PMU instrument ID\n");
        return ERR_PMU_EXAMPLES_CARDHANDLEFAIL;
    }
    
    //Calculate the number of sweep points on the drain
    NumSweepPts = (int)(fabs((StopVCh2 - StartVCh2) / StepVCh2) + 1);
    
    if(debug) printf("Number of sweep points: %d\n", NumSweepPts);
    
    //Determine if return array sizes are big enough
    if (NumSweepPts > Ch1_V_Ampl_Size || NumSweepPts > Ch1_I_Ampl_Size || NumSweepPts > Ch1_V_Base_Size || NumSweepPts > Ch1_I_Base_Size ||
        NumSweepPts > Ch2_V_Ampl_Size || NumSweepPts > Ch2_I_Ampl_Size || NumSweepPts > Ch2_V_Base_Size || NumSweepPts > Ch2_I_Base_Size ||
        NumSweepPts > TimeStampAmpl_Ch1_Size || NumSweepPts > TimeStampBase_Ch1_Size || NumSweepPts > TimeStampAmpl_Ch2_Size || NumSweepPts > TimeStampBase_Ch2_Size ||
        NumSweepPts > Status_Ch1_Size || NumSweepPts > Status_Ch2_Size ||
        NumSweepPts > Ch1SMUVoltageSize || NumSweepPts > Ch2SMUVoltageSize || NumSweepPts > Ch1SMUCurrentSize || NumSweepPts > Ch2SMUCurrentSize)
    {
        if(debug) printf("ERROR: One or more Output array size(s) < number of sweep points (%d)\n", NumSweepPts);
        return ERR_PMU_EXAMPLES_OUTPUT_ARRAY_TOO_SMALL;
    }
    
    // Check to see if RPMs are present
    status = pg2_init(InstId, PULSE_MODE_PULSE);
    Stat = rpm_config(InstId, CardChannel1, KI_RPM_PATHWAY, KI_RPM_PULSE);
    Stat = rpm_config(InstId, CardChannel2, KI_RPM_PATHWAY, KI_RPM_PULSE);
    RPMstat1 = pulse_ranges(InstId, CardChannel1, 10.0, PULSE_MEAS_FIXED, 10.0, PULSE_MEAS_FIXED, 100e-6);
    RPMstat2 = pulse_ranges(InstId, CardChannel2, 10, PULSE_MEAS_FIXED, 10, PULSE_MEAS_FIXED, 100e-6);
    if (RPMstat1 >= 0 && RPMstat2 >= 0) {
        RPMPresent = 1;
        if(debug) printf("RPMs detected\n");
    }
    
    // Size arrays for all returned measurements
    Ch1_V_All = (double *)calloc(NumSweepPts * 2 + 1, sizeof(double));
    Ch1_I_All = (double *)calloc(NumSweepPts * 2 + 1, sizeof(double));
    Ch1_T_All = (double *)calloc(NumSweepPts * 2 + 1, sizeof(double));
    Ch1_S_All = (unsigned long *)calloc(NumSweepPts * 2 + 1, sizeof(unsigned long));
    Ch2_V_All = (double *)calloc(NumSweepPts * 2 + 1, sizeof(double));
    Ch2_I_All = (double *)calloc(NumSweepPts * 2 + 1, sizeof(double));
    Ch2_T_All = (double *)calloc(NumSweepPts * 2 + 1, sizeof(double));
    Ch2_S_All = (unsigned long *)calloc(NumSweepPts * 2 + 1, sizeof(unsigned long));
    
    Ch1_V_High = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch1_I_High = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch1_V_Low = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch1_I_Low = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch1_T_High = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch1_T_Low = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch2_V_High = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch2_I_High = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch2_V_Low = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch2_I_Low = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch2_T_High = (double *)calloc(NumSweepPts + 1, sizeof(double));
    Ch2_T_Low = (double *)calloc(NumSweepPts + 1, sizeof(double));
    memAllocated = 1;
    
    // Initialize to NaN
    for (i = 0; i < NumSweepPts; i++)
    {
        Ch1_V_High[i] = DBL_NAN;
        Ch1_I_High[i] = DBL_NAN;
        Ch1_T_High[i] = DBL_NAN;
        Ch1_V_Low[i] = DBL_NAN;
        Ch1_I_Low[i] = DBL_NAN;
        Ch1_T_Low[i] = DBL_NAN;
        Ch2_V_High[i] = DBL_NAN;
        Ch2_I_High[i] = DBL_NAN;
        Ch2_T_High[i] = DBL_NAN;
        Ch2_V_Low[i] = DBL_NAN;
        Ch2_I_Low[i] = DBL_NAN;
        Ch2_T_Low[i] = DBL_NAN;
        Ch2_SMU_Voltage[i] = DBL_NAN;
        Ch2_SMU_Current[i] = DBL_NAN;
        Ch1_SMU_Voltage[i] = DBL_NAN;
        Ch1_SMU_Current[i] = DBL_NAN;
    }
    
    //Check to make sure desired SMU is in the chassis
    if (!LPTIsInCurrentConfiguration(Ch1SMU_ID))
    {
        if(debug) printf("Instrument %s is not in the system configuration\n", Ch1SMU_ID);
        goto cleanup_error;
    }
    
    if (!LPTIsInCurrentConfiguration(Ch2SMU_ID))
    {
        if(debug) printf("Instrument %s is not in system configuration\n", Ch2SMU_ID);
        goto cleanup_error;
    }
    
    // Convert SMU card string into identifying instrument card number
    getinstid(Ch1SMU_ID, &Ch1SMUId);
    getinstid(Ch2SMU_ID, &Ch2SMUId);
    
    if (-1 == Ch1SMUId || -1 == Ch2SMUId)
    {
        if(debug) printf("Failed to get SMU instrument IDs\n");
        goto cleanup_error;
    } 
    else {
        SMUPresent = 1;
    }
    
    // Open the SMU output relays BEFORE starting the pulse test
    if (!RPMPresent)
    {
        if(debug) printf("Using SMU relays - pulse mode\n");
        Stat = setmode(Ch1SMUId, KI_SHIELD_RELAY_STATE, 0);
        Stat = setmode(Ch2SMUId, KI_SHIELD_RELAY_STATE, 0);
    } else {
        if(debug) printf("Using RPM relays - pulse mode\n");
        Stat = rpm_config(InstId, CardChannel1, KI_RPM_PATHWAY, KI_RPM_PULSE);
        Stat = rpm_config(InstId, CardChannel2, KI_RPM_PATHWAY, KI_RPM_PULSE);
    }
    
    if(debug) printf("ExecMode is %d (0=Pulse+SMU, 1=Pulse only, 2=SMU only)\n", ExecMode);
    
    if (ExecMode == PulseOnlyMode || ExecMode == PulseAndSMUMode)
    {
        //Perform the Pulse-IV test
        status = pg2_init(InstId, PULSE_MODE_PULSE);
        if (status)
        {
            if(debug) printf("pg2_init failed: %d\n", status);
            goto cleanup_error;
        }
        
        //Calculate fundamental times
        PulseTopTimeCh1 = PulseWidthCh1 - (0.5 * RiseTimeCh1) - (0.5 * FallTimeCh1);
        PulseTopMeasStartCh1 = DelayCh1 + RiseTimeCh1 + (PulseTopTimeCh1 * MeasStartPercCh1);
        PulseTopMeasStopCh1 = DelayCh1 + RiseTimeCh1 + (PulseTopTimeCh1 * MeasStopPercCh1);
        
        PulseTopTimeCh2 = PulseWidthCh2 - (0.5 * RiseTimeCh2) - (0.5 * FallTimeCh2);
        PulseTopStartTimeCh2 = DelayCh2 + RiseTimeCh2;
        PulseTopStopTimeCh2 = DelayCh2 + RiseTimeCh2 + PulseTopTimeCh2;
        
        if(debug) {
            printf("Ch1 Meas window: %.6g to %.6g s\n", PulseTopMeasStartCh1, PulseTopMeasStopCh1);
            printf("Ch2 Pulse top: %.6g to %.6g s\n", PulseTopStartTimeCh2, PulseTopStopTimeCh2);
        }
        
        // Validate measurement window is within drain pulse top
        if (PulseTopMeasStartCh1 < PulseTopStartTimeCh2 || 
            PulseTopMeasStartCh1 > PulseTopStopTimeCh2 || 
            PulseTopMeasStopCh1 < PulseTopStartTimeCh2 || 
            PulseTopMeasStopCh1 > PulseTopStopTimeCh2)
        {
            if(debug) printf("ERROR: Meas window (%.6g to %.6g s) not within drain pulse top (%.6g to %.6g s)\n",
                PulseTopMeasStartCh1, PulseTopMeasStopCh1, PulseTopStartTimeCh2, PulseTopStopTimeCh2);
            ExecStatus = ERR_PMU_EXAMPLES_MEAS_EARLY;
            goto cleanup_error;
        }
        
        // Calculate Ch2 measurement window percentages
        MeasStartPercCh2 = (PulseTopMeasStartCh1 - DelayCh2 - RiseTimeCh2) / PulseTopTimeCh2;
        MeasStopPercCh2 = (PulseTopMeasStopCh1 - DelayCh2 - RiseTimeCh2) / PulseTopTimeCh2;
        
        if(debug) printf("Ch2 Meas window: %.6g%% to %.6g%%\n", MeasStartPercCh2*100, MeasStopPercCh2*100);
        
        // Calculate sample rate
        PulseBaseTimeCh1 = Period - PulseWidthCh1 - RiseTimeCh1 - FallTimeCh1;
        PulseTopMeasTimeCh1 = ((MeasStopPercCh1 - MeasStartPercCh1)* PulseTopTimeCh1);
        NumSamplesTopCh1 = (int)(PulseTopMeasTimeCh1 / 5e-9 + 1);
        PulseBaseMeasTimeCh1 = ((MeasStopPercCh1 - MeasStartPercCh1)* PulseBaseTimeCh1);
        NumSamplesBaseCh1 = (int)(PulseBaseMeasTimeCh1 / 5e-9 + 1);
        NumSamplesPeriodCh1 = NumSamplesTopCh1 + NumSamplesBaseCh1;
        NumSamplesSweepCh1 = NumSweepPts * NumSamplesPeriodCh1;
        
        if (NumSamplesSweepCh1 > MaxSamplesPerAtoD)
        {
            RateFactor = (int)((NumSamplesSweepCh1 / MaxSamplesPerAtoD) + 1);
            SampleRate = (SampleRate / RateFactor);
            if(debug) printf("Reducing sample rate by factor %d to %.6g Hz\n", (int)RateFactor, SampleRate);
        }
        
        status = pulse_sample_rate(InstId, SampleRate);
        if(status) {
            if(debug) printf("pulse_sample_rate failed: %d\n", status);
            goto cleanup_error;
        }
        
        //Set Ch1 source and measure ranges
        if (LtdAutoCurrCh1)
        {
            status = pulse_ranges(InstId, CardChannel1, VRangeCh1, PULSE_MEAS_FIXED, VRangeCh1, PULSE_MEAS_LTD_AUTO, IRangeCh1);
        } 
        else 
        {
            status = pulse_ranges(InstId, CardChannel1, VRangeCh1, PULSE_MEAS_FIXED, VRangeCh1, PULSE_MEAS_FIXED, IRangeCh1);
        }
        if (status) {
            if(debug) printf("pulse_ranges CH1 failed: %d\n", status);
            goto cleanup_error;
        }
        
        //Set Ch2 source and measure ranges
        if (LtdAutoCurrCh2)
        {
            status = pulse_ranges(InstId, CardChannel2, VRangeCh2, PULSE_MEAS_FIXED, VRangeCh2, PULSE_MEAS_LTD_AUTO, IRangeCh2);
        } 
        else 
        {
            status = pulse_ranges(InstId, CardChannel2, VRangeCh2, PULSE_MEAS_FIXED, VRangeCh2, PULSE_MEAS_FIXED, IRangeCh2);
        }
        if (status) {
            if(debug) printf("pulse_ranges CH2 failed: %d\n", status);
            goto cleanup_error;
        }
        
        //Set load line effect compensation
        if (!LoadLineCh1)
        {
            status = pulse_load(InstId, CardChannel1, ResCh1);
            if (status) {
                if(debug) printf("pulse_load CH1 failed: %d\n", status);
                goto cleanup_error;
            }
        }
        
        if (!LoadLineCh2)
        {
            status = pulse_load(InstId, CardChannel2, ResCh2);
            if (status) {
                if(debug) printf("pulse_load CH2 failed: %d\n", status);
                goto cleanup_error;
            }
        }
        
        //Set pulse source timing
        status = pulse_source_timing(InstId, CardChannel1, Period, DelayCh1, PulseWidthCh1, RiseTimeCh1, FallTimeCh1);
        if (status) {
            if(debug) printf("pulse_source_timing CH1 failed: %d\n", status);
            goto cleanup_error;
        }
        
        status = pulse_source_timing(InstId, CardChannel2, Period, DelayCh2, PulseWidthCh2, RiseTimeCh2, FallTimeCh2);
        if (status) {
            if(debug) printf("pulse_source_timing CH2 failed: %d\n", status);
            goto cleanup_error;
        }
        
        //Enable spot mean measurements
        status = pulse_meas_sm(InstId, CardChannel1, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, TRUE, TRUE, LoadLineCh1);
        if (status) {
            if(debug) printf("pulse_meas_sm CH1 failed: %d\n", status);
            goto cleanup_error;
        }
        
        status = pulse_meas_sm(InstId, CardChannel2, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, TRUE, TRUE, LoadLineCh2);
        if (status) {
            if(debug) printf("pulse_meas_sm CH2 failed: %d\n", status);
            goto cleanup_error;
        }
        
        //Set pulse measurement timing
        status = pulse_meas_timing(InstId, CardChannel1, MeasStartPercCh1, MeasStopPercCh1, PulseAverage);
        if (status) {
            if(debug) printf("pulse_meas_timing CH1 failed: %d\n", status);
            goto cleanup_error;
        }
        
        status = pulse_meas_timing(InstId, CardChannel2, MeasStartPercCh2, MeasStopPercCh2, PulseAverage);
        if (status) {
            if(debug) printf("pulse_meas_timing CH2 failed: %d\n", status);
            goto cleanup_error;
        }
        
        //Program drain base
        status = pulse_vlow(InstId, CardChannel2, BaseVCh2);
        if (status) {
            if(debug) printf("pulse_vlow CH2 failed: %d\n", status);
            goto cleanup_error;
        }
        
        //Configure pulse trains
        status = pulse_train(InstId, CardChannel1, BaseVCh1, AmplVCh1);
        if (status) {
            if(debug) printf("pulse_train CH1 failed: %d\n", status);
            goto cleanup_error;
        }
        
        status = pulse_sweep_linear(InstId, CardChannel2, PULSE_AMPLITUDE_SP, StartVCh2, StopVCh2, StepVCh2);
        if (status) {
            if(debug) printf("pulse_sweep_linear CH2 failed: %d\n", status);
            goto cleanup_error;
        }
        
        status = pulse_output(InstId, CardChannel1, 1);
        if (status) {
            if(debug) printf("pulse_output CH1 failed: %d\n", status);
            goto cleanup_error;
        }
        
        status = pulse_output(InstId, CardChannel2, 1);
        if (status) {
            if(debug) printf("pulse_output CH2 failed: %d\n", status);
            goto cleanup_error;
        }
        
        //Set test execute mode
        if (PMUMode == 0) {
            TestMode = PULSE_MODE_SIMPLE;
        }
        else {
            TestMode = PULSE_MODE_ADVANCED;
        }
        
        if(debug) printf("Executing pulse test (mode=%d)...\n", TestMode);
        status = pulse_exec(TestMode);
        if (status) {
            if(debug) printf("pulse_exec failed: %d\n", status);
            goto cleanup_error;
        }
        
        while(pulse_exec_status(&elapsedt) == 1) {
            Sleep(100);
        }
        
        if(debug) printf("Pulse test complete, fetching data...\n");
        
        // Fetch PMU data
        status = pulse_fetch(InstId, CardChannel1, 0, NumSweepPts*2, Ch1_V_All, Ch1_I_All, Ch1_T_All, Ch1_S_All);
        if (status) {
            if(debug) printf("pulse_fetch CH1 failed: %d\n", status);
            goto cleanup_error;
        }
        
        status = pulse_fetch(InstId, CardChannel2, 0, NumSweepPts*2, Ch2_V_All, Ch2_I_All, Ch2_T_All, Ch2_S_All);
        if (status) {
            if(debug) printf("pulse_fetch CH2 failed: %d\n", status);
            goto cleanup_error;
        }
        
        // De-interleave amplitude and base measurements
        for (i = 0; i < NumSweepPts; i++)
        {
            Ch1_V_High[i] = Ch1_V_All[2*i];
            Ch1_I_High[i] = Ch1_I_All[2*i];
            Ch1_T_High[i] = Ch1_T_All[2*i];
            Ch1_V_Low[i] = Ch1_V_All[2*i+1];
            Ch1_I_Low[i] = Ch1_I_All[2*i+1];
            Ch1_T_Low[i] = Ch1_T_All[2*i+1];
            
            Ch2_V_High[i] = Ch2_V_All[2*i];
            Ch2_I_High[i] = Ch2_V_All[2*i];
            Ch2_T_High[i] = Ch2_T_All[2*i];
            Ch2_V_Low[i] = Ch2_V_All[2*i+1];
            Ch2_I_Low[i] = Ch2_V_All[2*i+1];
            Ch2_T_Low[i] = Ch2_T_All[2*i+1];
        }
        
        // Copy to output arrays
        for (i = 0; i < NumSweepPts && i < Ch1_V_Ampl_Size; i++)
        {
            Ch1_V_Ampl[i] = Ch1_V_High[i];
            Ch1_I_Ampl[i] = Ch1_I_High[i];
            Ch1_V_Base[i] = Ch1_V_Low[i];
            Ch1_I_Base[i] = Ch1_I_Low[i];
            TimeStampAmpl_Ch1[i] = Ch1_T_High[i];
            TimeStampBase_Ch1[i] = Ch1_T_Low[i];
        }
        for (i = 0; i < NumSweepPts && i < Ch2_V_Ampl_Size; i++)
        {
            Ch2_V_Ampl[i] = Ch2_V_High[i];
            Ch2_I_Ampl[i] = Ch2_I_High[i];
            Ch2_V_Base[i] = Ch2_V_Low[i];
            Ch2_I_Base[i] = Ch2_I_Low[i];
            TimeStampAmpl_Ch2[i] = Ch2_T_High[i];
            TimeStampBase_Ch2[i] = Ch2_T_Low[i];
        }
        
        if(debug) printf("PMU pulse data copied to output arrays\n");
    }
    
    if ( ExecMode == SMUOnlyMode || ExecMode == PulseAndSMUMode)
    {
        if(debug) printf("Performing SMU DC test...\n");
        
        // Switch to SMU mode
        if (!RPMPresent)
        {
            if(debug) printf("Using SMU relays - SMU mode\n");
            Stat = setmode(Ch1SMUId, KI_SHIELD_RELAY_STATE, 1);
            Stat = setmode(Ch2SMUId, KI_SHIELD_RELAY_STATE, 1);
        } 
        else 
        {
            if(debug) printf("Using RPM relays - SMU mode\n");
            Stat = rpm_config(InstId, CardChannel1, KI_RPM_PATHWAY, KI_RPM_SMU);
            Stat = rpm_config(InstId, CardChannel2, KI_RPM_PATHWAY, KI_RPM_SMU);
        }
        
        // Set SMU ranges and limits
        limiti(Ch2SMUId, SMU_Icomp);
        rangei(Ch2SMUId, SMU_Irange);
        
        // Bias Ch1
        forcev(Ch1SMUId, AmplVCh1);
        
        // Perform SMU sweep
        rtfary(Ch2_SMU_Voltage);
        smeasi(Ch2SMUId, Ch2_SMU_Current);
        sintgi(Ch1SMUId, Ch1_SMU_Current);
        smeasv(Ch1SMUId, Ch1_SMU_Voltage);
        sweepv(Ch2SMUId, StartVCh2, StopVCh2, NumSweepPts-1, sweepdelay);
        inshld();
        
        if(debug) printf("SMU DC test complete, data in output arrays\n");
    }
    
    if (ExecMode < 0 || ExecMode > 2)
    {
        if(debug) printf("ERROR: Invalid ExecMode (%d)\n", ExecMode);
        ExecStatus = -99;
        goto cleanup_error;
    }
    
    // Cleanup and return
    if (memAllocated)
    {
        free(Ch1_V_All);
        free(Ch1_I_All);
        free(Ch1_T_All);
        free(Ch1_S_All);
        free(Ch2_V_All);
        free(Ch2_I_All);
        free(Ch2_T_All);
        free(Ch2_S_All);
        free(Ch1_V_High);
        free(Ch1_I_High);
        free(Ch1_V_Low);
        free(Ch1_I_Low);
        free(Ch1_T_High);
        free(Ch1_T_Low);
        free(Ch2_V_High);
        free(Ch2_I_High);
        free(Ch2_V_Low);
        free(Ch2_I_Low);
        free(Ch2_T_High);
        free(Ch2_T_Low);
    }
    
    if(debug) printf("ACraig12_PMU_SMU_Sweep: complete, returning 0 (success)\n");
    return 0;
    
cleanup_error:
    if (memAllocated)
    {
        free(Ch1_V_All);
        free(Ch1_I_All);
        free(Ch1_T_All);
        free(Ch1_S_All);
        free(Ch2_V_All);
        free(Ch2_I_All);
        free(Ch2_T_All);
        free(Ch2_S_All);
        free(Ch1_V_High);
        free(Ch1_I_High);
        free(Ch1_V_Low);
        free(Ch1_I_Low);
        free(Ch1_T_High);
        free(Ch1_T_Low);
        free(Ch2_V_High);
        free(Ch2_I_High);
        free(Ch2_V_Low);
        free(Ch2_I_Low);
        free(Ch2_T_High);
        free(Ch2_T_Low);
    }
    devint();
    return (ExecStatus != 0) ? ExecStatus : status;
/* USRLIB MODULE END  */
} 		/* End ACraig12_PMU_SMU_Sweep.c */

