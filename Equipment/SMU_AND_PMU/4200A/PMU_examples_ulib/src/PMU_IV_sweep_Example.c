/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_IV_sweep_Example
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 66
	ARGUMENTS:
		PulseWidthGate,	double,	Input,	200e-9,	60e-9,	.999999
		RiseTimeGate,	double,	Input,	40e-9,	20e-9,	0.033
		FallTimeGate,	double,	Input,	40e-9,	20e-9,	0.033
		DelayGate,	double,	Input,	0,	0,	.999999
		PulseWidthDrain,	double,	Input,	300e-9,	60e-9,	.999999
		RiseTimeDrain,	double,	Input,	100e-9,	20e-9,	.033
		FallTimeDrain,	double,	Input,	100e-9,	20e-9,	.033
		DelayDrain,	double,	Input,	0,	0,	.999999
		Period,	double,	Input,	5e-6,	80e-9,	1
		MeasStartGate,	double,	Input,	0.65,	0,	1
		MeasStopGate,	double,	Input,	0.80,	0,	1
		PulseAverage,	int,	Input,	1,	1,	10000
		LoadLineGate,	int,	Input,	1,	0,	1
		LoadLineDrain,	int,	Input,	1,	0,	1
		ResGate,	double,	Input,	1e6,	1,	1e6
		ResDrain,	double,	Input,	1E6,	1,	1E6
		AmplVGate,	double,	Input,	2,	-40,	40
		BaseVGate,	double,	Input,	0,	-40,	40
		StartVDrain,	double,	Input,	0,	-40,	40
		StopVDrain,	double,	Input,	5,	-40,	40
		StepVDrain,	double,	Input,	1,	.001,	40
		BaseVDrain,	double,	Input,	0,	-40,	40
		VRangeGate,	double,	Input,	10,	5,	40
		IRangeGate,	double,	Input,	0.01,	1e-7,	.8
		LtdAutoCurrGate,	int,	Input,	0,	0,	1
		VRangeDrain,	double,	Input,	10,	5,	40
		IRangeDrain,	double,	Input,	0.2,	1e-7,	.8
		LtdAutoCurrDrain,	int,	Input,	0,	0,	1
		GateCh,	int,	Input,	1,	1,	2
		DrainCh,	int,	Input,	2,	1,	2
		ThresholdCurrGate,	double,	Input,	1,	1e-12,	1
		ThresholdVoltGate,	double,	Input,	40,	0,	42
		ThresholdPwrGate,	double,	Input,	8,	1e-12,	10
		ThresholdCurrDrain,	double,	Input,	1,	1e-12,	1
		ThresholdVoltDrain,	double,	Input,	40,	0,	42
		ThresholdPwrDrain,	double,	Input,	8,	0,	10
		PMUMode,	int,	Input,	0,	0,	1
		SMU_V,	double,	Input,	0,	-210,	210
		SMU_Irange,	double,	Input,	.01,	10e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		SMU_ID,	char *,	Input,	"NONE",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		Gate_V_Ampl,	D_ARRAY_T,	Output,	,	,	
		Gate_V_Ampl_Size,	int,	Input,	100,	,	10000
		Gate_I_Ampl,	D_ARRAY_T,	Output,	,	,	
		Gate_I_Ampl_Size,	int,	Input,	100,	,	10000
		Gate_V_Base,	D_ARRAY_T,	Output,	,	,	
		Gate_V_Base_Size,	int,	Input,	100,	,	10000
		Gate_I_Base,	D_ARRAY_T,	Output,	,	,	
		Gate_I_Base_Size,	int,	Input,	100,	,	10000
		Drain_V_Ampl,	D_ARRAY_T,	Output,	,	,	
		Drain_V_Ampl_Size,	int,	Input,	100,	,	10000
		Drain_I_Ampl,	D_ARRAY_T,	Output,	,	,	
		Drain_I_Ampl_Size,	int,	Input,	100,	,	10000
		Drain_V_Base,	D_ARRAY_T,	Output,	,	,	
		Drain_V_Base_Size,	int,	Input,	100,	,	10000
		Drain_I_Base,	D_ARRAY_T,	Output,	,	,	
		Drain_I_Base_Size,	int,	Input,	100,	,	10000
		TimeStampAmpl_Gate,	D_ARRAY_T,	Output,	,	,	
		TimeStampAmpl_Gate_Size,	int,	Input,	100,	,	10000
		TimeStampBase_Gate,	D_ARRAY_T,	Output,	,	,	
		TimeStampBase_Gate_Size,	int,	Input,	100,	,	10000
		TimeStampAmpl_Drain,	D_ARRAY_T,	Output,	,	,	
		TimeStampAmpl_Drain_Size,	int,	Input,	100,	,	10000
		TimeStampBase_Drain,	D_ARRAY_T,	Output,	,	,	
		TimeStampBase_Drain_Size,	int,	Input,	100,	,	10000
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
#define MaxSamplesPerAtoD 1000000
void AllocateArrays_PMU_IV_Sw(int NumberofSegments);
void FreeArrays_PMU_IV_Sw();

double *Gate_V_All = NULL, *Gate_I_All = NULL, *Gate_T_All = NULL;
double *Gate_V_High = NULL, *Gate_I_High = NULL, *Gate_T_High = NULL;    
double *Gate_V_Low = NULL, *Gate_I_Low = NULL, *Gate_T_Low = NULL;    
double *Drain_V_All = NULL, *Drain_I_All = NULL, *Drain_T_All = NULL;
double *Drain_V_High = NULL, *Drain_I_High = NULL,*Drain_T_High = NULL;    
double *Drain_V_Low = NULL, *Drain_I_Low = NULL, *Drain_T_Low = NULL;    
unsigned long *Gate_S_All = NULL, *Drain_S_All = NULL;


#pragma warning( disable: 4996 )
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: PMU_IV_sweep_Example
============================

Description
-----------

The purpose of this module is a functional programming reference to illustrate
the basic LPT commands necessary to do a single Vd-Id sweep.

This module performs a voltage amplitude Pulse IV sweep using 2 channels of a 
single 4225-PMU card. One channel sweeps (Drain), while the other uses a fixed 
pulse amplitude (Gate).

This routine allows for independent pulse width, rise, fall and delay 
parameters to be set for the 2 channels. Note that the period is the same for 
both channels. 

Also note that the recommended minimum pulse width and rise/fall times vary 
by current measure range. Lower measure ranges should have wider pulses, or 
unexpected results may occur.

The measurement window is also the same for both channels and is set by 
MeasStartPercGate and MeasStopPercGate (more information in INPUTS below).  
By definition, the measure window for the spot mean will be within the pulse 
top of the gate, but this routine also checks to ensure that the spot mean
is also within the pulse top of the drain. If the spot mean for the gate pulse 
top is not within the drain pulse top, an error results. To fix the 
error, adjust the timing parameters for the drain so that there is some overlap 
(in time) between the gate and drain pulse tops.

Optional SMU available for voltage biasing of a device terminal that does 
not react to the pulse. For example, do not connect SMU to DUT drain, gate, 
or source of a transistor. Note that the SMU cannot be connected to an RPM, 
or a -233 error ("forcev(): Cannot force when not connected.") will occur.

The sample rate is automatically chosen to ensure that the maximum number of 
samples (stored on the card during the test) does not exceed 1,000,000 per A
/D (4 A/Ds per card, for I & V on each of the 2 channels).

This uses Gate and Drain naming convention, but any 2 channel sweep test may use 
this routine.

This routine is compatible with KXCI using the UL mode.

How to use
----------

Connect the Channel 1 of the PMU to the Gate (RPM is optional). Connect 
Channel 2 of the PMU to the DUT Drain (RPM optional).

Set the parameters, explained below.  

Run, or Append, the test. View data values in the Analyze sheet and view data curves in 
the Analyze graph.

Inputs
------

PulseWidthGate	
: (double) Pulse Width for Gate (FWHM):
: 10 V range: 60 ns to 0.99999 s
: 40 V range: 140 ns to 0.99999 s

RiseTimeGate	
: (double) Rise time (0 to 100%) for the Gate:
: 10 V range: 20 ns to 33 ms (slew-rate limited)
: 40 V range:  100 ns to 33 ms (slew-rate limited)

FallTimeGate	
: (double) Range: Fall time (0 to 100%) for the Gate:
: 10 V range: 20 ns to 33 ms (slew-rate limited)
: 40 V range:  100 ns to 33 ms (slew-rate limited)

DelayGate		
: (double) Delay time (time before pulse) for the Gate:
: 10 V & 40 V: 20 ns to 0.99999 s.

PulseWidthDrain	
: (double) Pulse Width for Drain (FWHM):
: 10 V range: 60 ns to 0.99999 s
: 40 V range: 140 ns to 0.99999 s

RiseTimeDrain		
: (double) Rise time (0 to 100%) for the Drain:
: 10 V range: 20 ns to 33 ms (slew-rate limited)
: 40 V range:  100 ns to 33 ms (slew-rate limited)

FallTimeDrain		
: (double) Fall time (0 to 100%) for the Drain:
: 10 V range: 20 ns to 33 ms (slew-rate limited)
: 40 V range:  100 ns to 33 ms (slew-rate limited)

DelayDrain			
: (double) Delay time (time before pulse) for the Drain:
: 10 V & 40 V: 20 ns to 0.99999 s.

Period				
: (double) Pulse Period time (Both Gate and Drain share the same period time.)
: 10 V range: 140 ns to 1 s
: 40 V range: 280 ns to 1 s

MeasStartGate	
: Start of the spot mean measure window in decimal proportion, 
		where 0.00 is the start of the pulse top and 1.00 is the end 
		of the pulse top.  Pulse top is the time of the pulse at the 
		chosen amplitude. For example, a pulse width of 200 ns (FWHM) 
		with rise and fall of 40 ns would give a pulse top time:
		pulse top = PW - 0.5 * rise - 0.5 * fall
		pulse top = 200 - 20 - 20 = 160 ns
: Typical value is 0.75 (75%).

MeasStopGate
: Stop of the spot mean measure window in decimal proportion, 
		where 0.00 is the start of the pulse top and 1.00 is the end 
		of the pulse top. Pulse top is the time of the pulse at the 
		chosen amplitude. For example, a pulse width of 200 ns (FWHM) 
		with rise and fall of 40 ns would give a pulse top time.
: Typical value is 0.9 (90%).

PulseAverage	
: (int) Number of pulses to source and measure.

LoadLineGate		
: (int) Check to enable Load Line Effect Compensation (LLEC) on the Gate terminal of the test device.

LoadLineDrain		
: (int) Check to enable Load Line Effect Compensation (LLEC) on the Drain terminal of the test device.

ResGate			
: (double) Range: 1 to 1e6

ResDrain		
: (double) Range: 1 to 1e6

AmplVGate		
: (double) Pulse Voltage Amplitude of Gate (height from base voltage).

BaseVGate		
: (double) Base voltage (DC offset) for Gate.

StartVDrain		
: (double) Starting voltage for Drain amplitude sweep.

StopVDrain		
: (double) Final voltage for Drain amplitude sweep.

StepVDrain		
: (double) Voltage step size for Drain amplitude sweep.

BaseVDrain		
: (double) Base voltage (DC offset) for Drain.

VRangeGate		
: (double) Gate Voltage:
: Range: (+/-) 10V or (+/-) 40V.

IRangeGate		
: (double) Gate Current Measure Range. Note that available ranges differ based on Voltage Range and if an RPM is connected.

LtdAutoCurrGate		
: (double) Check to enable Limited Auto Range for the Gate.

VRangeDrain		
: (double) Drain Voltage Range:
: (+/-) 10V or (+/-) 40V.

IRangeDrain		
: (double) Drain Current Measure Range. Note that available ranges differ based on Voltage Range and if an RPM is connected.

LtdAutoCurrDrain	
: (double) Check to enable Limited Auto Range for the Drain.

GateCh			
: (int) Range: 1 or 2

DrainCh			
: (int) Range: 1 or 2

ThresholdCurrGate	
: (double) Range: 1e-12 to 1

ThresholdVoltGate	
: (double) Range: 0 to 42

ThresholdPwrGate	
: (double) Range: 1e-12 to 10

ThresholdCurrDrain	
: (double) Range: 1e-12 to 1

ThresholdVoltDrain	
: (double) Range: 0 to 42

ThresholdPwrDrain	
: (double) Range: 0 to 10

PMUMode	
: (int)	PMU Test Execution mode. Controls test execution. If Load Line 
		Effect compensation or thresholds (volt, current, power) are 
		desired, then set PMUMode = 1, otherwise use PMUMode = 0.  Note 
		that Mode = 0 will result in shorter test times, but only allows 
		fixed current ranges, no LLE comp and no IVP threshold comparisons.
: 0: Simple
: 1: Advanced

SMU_V		
: (double) SMU voltage for biasing non-pulsed DUT terminal. For
			example, do not connect SMU to transistor source terminal when
			pulsing gate and/or drain.
: Range: -210 to +210 V

SMU_Irange		
: (double) SMU current range. 
: Ranges: 10e-9, 100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 10e-3, 
			100e-3, 1
: Note: 10e-9 requires preamplifier and 1 A range only available 
			on high power SMU.

SMU_Icomp		
: (double) SMU current compliance. This value must > 10% of the 
			above current range.

SMU_ID		
: SMU instrument name, such as "SMU1" (without quotes). For no
			SMU, use "NONE". Note that the SMU cannot be connected to an
			RPM, or a -233 error ("forcev(): Cannot force when not connected.")
			will occur.
: Range:  NONE, SMU1, SMU2, up to maximum SMUs in system.


PMU_ID		
: PMU instrument name, such as "PMU1" (without quotes).
			Range:  PMU1 thru PMU4.

Return values
-------------
			 
Value  | Description
------ | -----------
0      | OK.
-122   | pulse_ranges(): Illegal value for parameter #7. Ensure that current measure
       | range is appropriate for the chosen voltage range.
-233   | Cannot force when not connected. Ensure that specified SMU is not connected
       | through or associated with an RPM. If all SMUs are associated with RPM modules,
       | choose NONE to permit the test to run.
-829   | pulse_sweep_linear(): The sum of base and amplitude voltages (XX.XV)
       | exceeds maximum (YYV) for present range. The Base + Amplitude voltage
       | is too large for the chosen PMU voltage range. Check the BaseVCh1, StartVCh1
       | and StopVCh1 for voltages that exceed VRangeCh1. If necessary, increase VRangeCh1 to the maximum 40V range.
-824   | pulse_exec(): Invalid pulse timing parameters.
       | One or more timing parameters (PulseWidthCh1, RiseTimeCh1, FallTimeCh1,
       | DelayCh1 or Period) are too small for the chosen VRangeCh1.
       | Increase the time of the appropriate parameters.
-17001 | Wrong card Id. Check PMU and SMU names.
-17002 | Failure to assign card ID handle. Check PMU and/or SMU names.
-17100 | Gate Measure window outside of Drain Pulse top.
       | Adjust gate measure window, gate pulse timing, or drain pulse timing.
-17110 | Output array sizes are less than number of points in sweep.
	   | Increase output array sizes or decrease number of points in sweep.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
#define MaxSamplesPerAtoD 1000000
void AllocateArrays_PMU_IV_Sw(int NumberofSegments);
void FreeArrays_PMU_IV_Sw();

double *Gate_V_All = NULL, *Gate_I_All = NULL, *Gate_T_All = NULL;
double *Gate_V_High = NULL, *Gate_I_High = NULL, *Gate_T_High = NULL;    
double *Gate_V_Low = NULL, *Gate_I_Low = NULL, *Gate_T_Low = NULL;    
double *Drain_V_All = NULL, *Drain_I_All = NULL, *Drain_T_All = NULL;
double *Drain_V_High = NULL, *Drain_I_High = NULL,*Drain_T_High = NULL;    
double *Drain_V_Low = NULL, *Drain_I_Low = NULL, *Drain_T_Low = NULL;    
unsigned long *Gate_S_All = NULL, *Drain_S_All = NULL;


#pragma warning( disable: 4996 )

int PMU_IV_sweep_Example( double PulseWidthGate, double RiseTimeGate, double FallTimeGate, double DelayGate, double PulseWidthDrain, double RiseTimeDrain, double FallTimeDrain, double DelayDrain, double Period, double MeasStartGate, double MeasStopGate, int PulseAverage, int LoadLineGate, int LoadLineDrain, double ResGate, double ResDrain, double AmplVGate, double BaseVGate, double StartVDrain, double StopVDrain, double StepVDrain, double BaseVDrain, double VRangeGate, double IRangeGate, int LtdAutoCurrGate, double VRangeDrain, double IRangeDrain, int LtdAutoCurrDrain, int GateCh, int DrainCh, double ThresholdCurrGate, double ThresholdVoltGate, double ThresholdPwrGate, double ThresholdCurrDrain, double ThresholdVoltDrain, double ThresholdPwrDrain, int PMUMode, double SMU_V, double SMU_Irange, double SMU_Icomp, char *SMU_ID, char *PMU_ID, double *Gate_V_Ampl, int Gate_V_Ampl_Size, double *Gate_I_Ampl, int Gate_I_Ampl_Size, double *Gate_V_Base, int Gate_V_Base_Size, double *Gate_I_Base, int Gate_I_Base_Size, double *Drain_V_Ampl, int Drain_V_Ampl_Size, double *Drain_I_Ampl, int Drain_I_Ampl_Size, double *Drain_V_Base, int Drain_V_Base_Size, double *Drain_I_Base, int Drain_I_Base_Size, double *TimeStampAmpl_Gate, int TimeStampAmpl_Gate_Size, double *TimeStampBase_Gate, int TimeStampBase_Gate_Size, double *TimeStampAmpl_Drain, int TimeStampAmpl_Drain_Size, double *TimeStampBase_Drain, int TimeStampBase_Drain_Size )
{
/* USRLIB MODULE CODE */
    int i;
    int status;
    int NumSweepPts;
    int NumSamplesTopGate, NumSamplesBaseGate;
    int NumSamplesPeriodGate, NumSamplesSweepGate;
    int NumTotalSamples;
    int verbose = 0;
    char ErrMsgChar[256];
    char No_SMU[10] = "NONE";

    //Gate measure timing parameters
    double PulseTopTimeGate, PulseBaseTimeGate;
    double PulseTopMeasTimeGate, PulseBaseMeasTimeGate;
    double PulseTopMeasStartGate, PulseTopMeasStopGate;

    //Drain measure timing parameters
    double PulseTopTimeDrain;
    double PulseTopStartTimeDrain, PulseTopStopTimeDrain;
    double MeasStartPercGate, MeasStopPercGate;
    double MeasStartPercDrain, MeasStopPercDrain;

    int TestMode;
    int InstId, SMUId;
    double elapsedt;
    double RateFactor, SampleRate;
    boolean SMUPresent;    

    //Initialize variables
    SampleRate = 200E+6;
    RateFactor = 0.0;
    SMUPresent = FALSE;    
    MeasStartPercGate = MeasStartGate;   
    MeasStopPercGate = MeasStopGate;
//    verbose = 1;        //print out status messages to Message Console (type msgcon at command prompt)

    if ( verbose )
        printf("PMU_IV_Sweep: ======== New run =====");

    //Check: is requested PMU card in the chassis?
    if ( !LPTIsInCurrentConfiguration(PMU_ID) )
    {
        printf("Instrument %s is not in system configuration", PMU_ID);
        return -1;
    }

    //Convert card string into identifying instrument card number
    getinstid(PMU_ID, &InstId);
    if ( -1 == InstId )
        return -2;

    if ( verbose )
        printf("PMU_IV_sweep: Just before SMU presence check");

    //Check: is a SMU ID set (SMUx or NONE)?  If a SMU string, is in the the chassis?
    if ( _stricmp(SMU_ID, No_SMU) )
    {
        if ( verbose )
            printf("PMU_IV_sweep: SMU string present, %s", SMU_ID);

        if ( !LPTIsInCurrentConfiguration(SMU_ID) )
        {
            printf("PMU_IV_sweep: Instrument %s is not in system configuration", PMU_ID);
            return ERR_PMU_EXAMPLES_WRONGCARDID;
        }

        //Convert SMU card string into identifying instrument card number
        getinstid(SMU_ID, &SMUId);
        if ( -1 == SMUId )
            return -2;
        SMUPresent = TRUE;
    }
    else    //NONE specified, do not use SMU in this test
    {
        SMUPresent = FALSE;
        if ( verbose )
            printf("PMU_IV_sweep: No SMU specified, SMU_ID = %s", SMU_ID);
    }

    //Calculate the number of sweep points on the drain
    NumSweepPts = (int)((StopVDrain - StartVDrain) / StepVDrain + 1);

    //Determine if return array sizes are big enough to contain
    //the desired number of sweep points (NumSweepPts)
    if (NumSweepPts > Gate_V_Ampl_Size || NumSweepPts > Gate_I_Ampl_Size || NumSweepPts > Gate_V_Base_Size || NumSweepPts > Gate_I_Base_Size || 
        NumSweepPts > Drain_V_Ampl_Size || NumSweepPts > Drain_I_Ampl_Size || NumSweepPts > Drain_V_Base_Size || NumSweepPts > Drain_I_Base_Size)
    {
        if (verbose)
            printf("PMU_IV_sweep_Example: One or more Output array size(s) < number of sweep points. Increase size of all Output arrays to be at least %d", NumSweepPts);
        sprintf(ErrMsgChar, "One or more Output array size(s) < number of sweep points. Increase size of all Output arrays to be at least %d.", NumSweepPts);
        logMsg(MF_Error, ERROR_STRING, ErrMsgChar);
        return ERR_PMU_EXAMPLES_OUTPUT_ARRAY_TOO_SMALL;
    }

    //Initialize return data arrays
    memset(Gate_V_Ampl, 0, Gate_V_Ampl_Size*sizeof(double));
    memset(Gate_I_Ampl, 0, Gate_I_Ampl_Size*sizeof(double));
    memset(Gate_V_Base, 0, Gate_V_Base_Size*sizeof(double));
    memset(Gate_I_Base, 0, Gate_I_Base_Size*sizeof(double));
    memset(Drain_V_Ampl, 0, Drain_V_Ampl_Size*sizeof(double));
    memset(Drain_I_Ampl, 0, Drain_I_Ampl_Size*sizeof(double));
    memset(Drain_V_Base, 0, Drain_V_Base_Size*sizeof(double));
    memset(Drain_I_Base, 0, Drain_I_Base_Size*sizeof(double));

    //Allocate arrays for the measurement data
    AllocateArrays_PMU_IV_Sw(NumSweepPts);

    //Ensure that 4225-RPM (if attached) is in the pulse mode
    status = rpm_config(InstId, GateCh, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    status = rpm_config(InstId, DrainCh, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    status = pg2_init(InstId, PULSE_MODE_PULSE);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    if ( SMUPresent )
    {
        if ( verbose )
            printf("PMU_IV_sweep: SMU present, V= %g, Irange= %g", SMU_V, SMU_Irange);

        status = rangei(SMUId, SMU_Irange);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }

        status = limiti(SMUId, SMU_Icomp);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }

        if ( verbose )
            printf("PMU_IV_sweep: SMU present, forcing V= %g", SMU_V);
        status = forcev(SMUId, SMU_V);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }
    }

    //Calcuate fundament times: Pulse tops, measure start and stop
    //These are used below
    PulseTopTimeGate = PulseWidthGate - (0.5 * RiseTimeGate) - (0.5 * FallTimeGate);
    PulseTopMeasStartGate = DelayGate + RiseTimeGate + (PulseTopTimeGate*MeasStartPercGate);
    PulseTopMeasStopGate = DelayGate + RiseTimeGate + (PulseTopTimeGate*MeasStopPercGate);

    PulseTopTimeDrain = PulseWidthDrain - (0.5 * RiseTimeDrain) - (0.5 * FallTimeDrain);
    PulseTopStartTimeDrain = DelayDrain + RiseTimeDrain;
    PulseTopStopTimeDrain = DelayDrain + RiseTimeDrain + PulseTopTimeDrain;       

    if ( verbose )
        printf("PMU_IV_Sweep: StrtMeas= %g s, StpMeas= %g s, StrtDrnTop= %g s, StpDrnTop= %g s", PulseTopMeasStartGate, PulseTopMeasStopGate, PulseTopStartTimeDrain, PulseTopStopTimeDrain);

    if ( verbose )
        printf("PMU_IV_Sweep: GateStrtMeas%= %g perc, GateStpMeas%= %g perc", (PulseTopMeasStartGate- DelayGate - RiseTimeGate)/PulseTopTimeGate, (PulseTopMeasStopGate- DelayGate - RiseTimeGate)/PulseTopTimeGate);

    //Determine if the gate measurement window for the pulse top is 
    //within the pulse top of the drain.  If not, error.

    if (PulseTopMeasStartGate < PulseTopStartTimeDrain || PulseTopMeasStartGate > PulseTopStopTimeDrain || PulseTopMeasStopGate < PulseTopStartTimeDrain || PulseTopMeasStopGate > PulseTopStopTimeDrain)
    {
        printf("PMU_IV_Sweep: Error, Meas window (%g to %g s) not within drain pulse top (%g s to %g s)", PulseTopMeasStartGate, PulseTopMeasStopGate, PulseTopStartTimeDrain, PulseTopStopTimeDrain);
        sprintf(ErrMsgChar, "Measurement window (%g to %g s) not within drain pulse top (%g to %g s)", PulseTopMeasStartGate, PulseTopMeasStopGate, PulseTopStartTimeDrain, PulseTopStopTimeDrain);
        logMsg(MF_Error, ERROR_STRING, ErrMsgChar); 
        return ERR_PMU_EXAMPLES_MEAS_EARLY;
    }

    //Calculate the Start & Stop measure window percentages for the 
    //Drain, must be synchronous with Gate
    MeasStartPercDrain = (PulseTopMeasStartGate - DelayDrain - RiseTimeDrain) / PulseTopTimeDrain;
    MeasStopPercDrain = (PulseTopMeasStopGate - DelayDrain - RiseTimeDrain) / PulseTopTimeDrain;

    if ( verbose )
        printf("PMU_IV_Sweep: DrainStrtMeas%= %g perc, DrainStpMeas%= %g perc", MeasStartPercDrain, MeasStopPercDrain);

    //Calculate number of sample points (per A/D) required for the test
    //if total samples for the test > MaxSamplesPerAtoD, then set sample_rate to lower value
    //Max sample rate is 200E6, same rate used for both channels on card

    PulseBaseTimeGate = Period - PulseWidthGate - 0.5*(RiseTimeGate - FallTimeGate) - DelayGate;
    PulseTopMeasTimeGate = ((MeasStopPercGate - MeasStartPercGate)* PulseTopTimeGate);
    NumSamplesTopGate = (int)(PulseTopMeasTimeGate/5e-9 + 1E-7 + 1);
    PulseBaseMeasTimeGate = ((MeasStopPercGate - MeasStartPercGate)* PulseBaseTimeGate);
    NumSamplesBaseGate = (int)(PulseBaseMeasTimeGate/5e-9 + 1E-7 + 1);    
    NumSamplesPeriodGate = NumSamplesTopGate + NumSamplesBaseGate;
    NumSamplesSweepGate = NumSweepPts * NumSamplesPeriodGate;

    if ( verbose )
        printf("PMU_IV_Sweep: Ch1 PW= %g, PlsTop= %g, PlsBase= %g", PulseWidthGate, PulseTopTimeGate, PulseBaseTimeGate);

    if ( verbose )
        printf("PMU_IV_Sweep: #SmplPlsTopCh1= %d, #SmplbaseGate= %d,#SmplPerGate= %d, #SampSweep= %d", NumSamplesTopGate, NumSamplesBaseGate, NumSamplesPeriodGate, NumSamplesSweepGate);

    if (NumSamplesSweepGate > MaxSamplesPerAtoD)
    {
        RateFactor = (int)((NumSamplesSweepGate / MaxSamplesPerAtoD) + 1);      
        SampleRate = (SampleRate / RateFactor);
        printf("Basic_SegArb:  NumSamplesSweepGate > MaxSamplesPerAtoD, Ratefactor= %d", RateFactor);
    }

    if ( verbose )
        printf("PMU_IV_Sweep: NumTtlSmpls= %d, SampleRate= %g", NumSamplesSweepGate, SampleRate);

    NumTotalSamples = (int)((PulseTopMeasTimeGate + PulseBaseMeasTimeGate) * SampleRate);    

    if ( verbose )
        printf("PMU_IV_Sweep: Using new sample rate, NumTotalSamples= %d, SampleRate= %g", NumTotalSamples, SampleRate);

    //Set PMU to return actual values when measurement overflow occurs
    status = setmode(InstId, KI_LIM_MODE, KI_VALUE);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    status = pulse_sample_rate(InstId, SampleRate);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //Set Gate source and measure ranges
    if (LtdAutoCurrGate)
    {
        status = pulse_ranges(InstId, GateCh, VRangeGate, PULSE_MEAS_FIXED, VRangeGate, PULSE_MEAS_LTD_AUTO, IRangeGate);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }
    }
    else
    {
        status = pulse_ranges(InstId, GateCh, VRangeGate, PULSE_MEAS_FIXED, VRangeGate, PULSE_MEAS_FIXED, IRangeGate);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }
    }

    //Set Drain source and measure ranges
    if (LtdAutoCurrDrain)
    {
        status = pulse_ranges(InstId, DrainCh, VRangeDrain, PULSE_MEAS_FIXED, VRangeDrain, PULSE_MEAS_LTD_AUTO, IRangeDrain);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }
    }
    else
    {
        status = pulse_ranges(InstId, DrainCh, VRangeDrain, PULSE_MEAS_FIXED, VRangeDrain, PULSE_MEAS_FIXED, IRangeDrain);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }
    }

    //If load line effect compensation for the gate is disabled, set desired resistance
    if (!LoadLineGate || !PMUMode)
    {
        status = pulse_load(InstId, GateCh, ResGate);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }
    }

    //If load line effect compensation for the drain is disabled, set desired resistance
    if (!LoadLineDrain || !PMUMode)
    {
        status = pulse_load(InstId, DrainCh, ResDrain);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }
    }

    //Set Gate pulse source timing
    status = pulse_source_timing(InstId, GateCh, Period, DelayGate, PulseWidthGate, RiseTimeGate, FallTimeGate);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //Set Drain pulse source timing
    status = pulse_source_timing(InstId, DrainCh, Period, DelayDrain, PulseWidthDrain, RiseTimeDrain, FallTimeDrain);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //Set test-ending thresholds.  Note these are not hardware limits, but
    //test thresholds.  After the burst of pulses (count = PulseAverage),
    //the PMU will compare to the below settings. If the "limit" is reached
    //or exceeded, then the test will end.  Power = V * I
    status = pulse_limits(InstId, GateCh, ThresholdVoltGate, ThresholdCurrGate, ThresholdPwrGate);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    status = pulse_limits(InstId, DrainCh, ThresholdVoltDrain, ThresholdCurrDrain, ThresholdPwrDrain);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //Set Gate pulse measurement for spot means on pulse top and base
    status = pulse_meas_timing(InstId, GateCh, MeasStartPercGate, MeasStopPercGate, PulseAverage);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //Set Drain pulse measurement for spot means on pulse top and base
    status = pulse_meas_timing(InstId, DrainCh, MeasStartPercDrain, MeasStopPercDrain, PulseAverage);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //Enable Gate spot mean measurements
    //example pulse_meas_sm(Card, ch, Measuretype, acquireVHigh, acquireVLow, acquireIHigh, acquireILow, acquireTimeStamp, LLEComp)
    status = pulse_meas_sm(InstId, GateCh, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, TRUE, TRUE, LoadLineGate);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //Enable Drain spot mean measurements
    //example pulse_meas_sm(Card, ch, Measuretype, acquireVHigh, acquireVLow, acquireIHigh, acquireILow, acquireTimeStamp, LLEComp)
    status = pulse_meas_sm(InstId, DrainCh, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, TRUE, TRUE, LoadLineDrain);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //Program drain base, necessary when performing Drain Amplitude sweep
    status = pulse_vlow(InstId, DrainCh, BaseVDrain);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    status = pulse_train(InstId, GateCh, BaseVGate, AmplVGate);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    status = pulse_sweep_linear(InstId, DrainCh, PULSE_AMPLITUDE_SP, StartVDrain, StopVDrain, StepVDrain);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    status = pulse_output(InstId, GateCh, 1);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    status = pulse_output(InstId, DrainCh, 1);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    if ( verbose )
        printf("PMU_IV_Sweep: Just prior to pulse_exec");

    //Set test execute mode to Simple or Advanced
    if (PMUMode ==0)
        TestMode = PULSE_MODE_SIMPLE;
    else
        TestMode = PULSE_MODE_ADVANCED;

    //Run the test
    status = pulse_exec(TestMode);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //wait for test to be complete
    while(pulse_exec_status(&elapsedt) == 1)
     Sleep(100);

    if ( verbose )
       printf("PMU_IV_Sweep: Just after pulse_exec_status, test done, getting data");

    //Retrieve the measurements
    status = pulse_fetch(InstId, GateCh, 0, NumSweepPts*2, Gate_V_All, Gate_I_All, Gate_T_All, Gate_S_All);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    status = pulse_fetch(InstId, DrainCh, 0, NumSweepPts*2, Drain_V_All, Drain_I_All, Drain_T_All, Drain_S_All);
    if ( status )
    {
        FreeArrays_PMU_IV_Sw();
        return status;
    }

    //Separate the pulse amplitude (high) and pulse base (low) measurements into different arrays
    for (i = 0; i<NumSweepPts; i++)
    {
        Gate_V_High[i] = Gate_V_All[2*i];
        Gate_I_High[i] = Gate_I_All[2*i];
        Gate_T_High[i] = Gate_T_All[2*i];            
        Gate_V_Low[i] = Gate_V_All[2*i+1];
        Gate_I_Low[i] = Gate_I_All[2*i+1];
        Gate_T_Low[i] = Gate_T_All[2*i+1];

        Drain_V_High[i] = Drain_V_All[2*i];
        Drain_I_High[i] = Drain_I_All[2*i];
        Drain_T_High[i] = Drain_T_All[2*i];            
        Drain_V_Low[i] = Drain_V_All[2*i+1];
        Drain_I_Low[i] = Drain_I_All[2*i+1];
        Drain_T_Low[i] = Drain_T_All[2*i+1];

        // Copy to output arrays, so that KXCI can access the measurements
        Gate_V_Ampl[i] = Gate_V_High[i];
        Gate_I_Ampl[i] = Gate_I_High[i];
        TimeStampAmpl_Gate[i] =  Gate_T_High[i];          
        Gate_V_Base[i] = Gate_V_Low[i];
        Gate_I_Base[i] = Gate_I_Low[i];
        TimeStampBase_Gate[i] = Gate_T_Low[i];
            
        Drain_V_Ampl[i] = Drain_V_High[i];
        Drain_I_Ampl[i] = Drain_I_High[i];
        TimeStampAmpl_Drain[i] = Drain_T_High[i];            
        Drain_V_Base[i] = Drain_V_Low[i];
        Drain_I_Base[i] = Drain_I_Low[i];
        TimeStampBase_Drain[i] = Drain_T_Low[i];
    
    }

    if ( verbose )
        for (i = 0; i<NumSweepPts; i++)
        {
            printf("PMU_IV_Sweep:  i= %d, GateVfull= %g, GateVhi= %g, GateVlo= %g", i, Gate_V_All[i], Gate_V_High[i], Gate_V_Low[i]);
            printf("PMU_IV_Sweep:  i= %d, DrainVfull= %g, DrainVhi= %g, DrainVlo= %g", i, Drain_V_All[i], Drain_V_High[i], Drain_V_Low[i]);
        }

    //Post the data to the Clarius sheet
    PostDataDoubleBuffer("Gate_V_Ampl", Gate_V_High, NumSweepPts);
    PostDataDoubleBuffer("Gate_I_Ampl", Gate_I_High, NumSweepPts);        
    PostDataDoubleBuffer("TimeStampAmpl_Gate", Gate_T_High, NumSweepPts);
    PostDataDoubleBuffer("Gate_V_Base", Gate_V_Low, NumSweepPts);
    PostDataDoubleBuffer("Gate_I_Base", Gate_I_Low, NumSweepPts);        
    PostDataDoubleBuffer("TimeStampBase_Gate", Gate_T_Low, NumSweepPts);

    PostDataDoubleBuffer("Drain_V_Ampl", Drain_V_High, NumSweepPts);
    PostDataDoubleBuffer("Drain_I_Ampl", Drain_I_High, NumSweepPts);        
    PostDataDoubleBuffer("TimeStampAmpl_Drain", Drain_T_High, NumSweepPts);
    PostDataDoubleBuffer("Drain_V_Base", Drain_V_Low, NumSweepPts);
    PostDataDoubleBuffer("Drain_I_Base", Drain_I_Low, NumSweepPts);        
    PostDataDoubleBuffer("TimeStampBase_Drain", Drain_T_Low, NumSweepPts);

    if ( SMUPresent )
    {
        if ( verbose )
            printf("PMU_ScopeShot: SMU present, setting voltage = 0");
       
        status = forcev(SMUId, 0);
        if ( status )
        {
            FreeArrays_PMU_IV_Sw();
            return status;
        }
    }

    FreeArrays_PMU_IV_Sw();
    return 0;
}

void AllocateArrays_PMU_IV_Sw(int NumPts)
{
    //Allocate arrays for Seg-arb: trigger, measure type, measure start, measure stop.  
    //Size arrays for all returned measurements based on required number of points, assume both high and low measurements are enabled
    Gate_V_All = (double *)calloc(NumPts*2+1, sizeof(double));
    Gate_I_All = (double *)calloc(NumPts*2+1, sizeof(double));
    Gate_T_All = (double *)calloc(NumPts*2+1, sizeof(double));    
    Gate_S_All = (unsigned long *)calloc(NumPts*2+1, sizeof(unsigned long));    
    Drain_V_All = (double *)calloc(NumPts*2+1, sizeof(double));
    Drain_I_All = (double *)calloc(NumPts*2+1, sizeof(double));
    Drain_T_All = (double *)calloc(NumPts*2+1, sizeof(double));    
    Drain_S_All = (unsigned long *)calloc(NumPts*2+1, sizeof(unsigned long));    

    //Size arrays for individual pulse amplitude (High) and pulse base (Low)
    //readings, based on required number of points
    Gate_V_High = (double *)calloc(NumPts+1, sizeof(double));
    Gate_I_High = (double *)calloc(NumPts+1, sizeof(double));
    Gate_V_Low = (double *)calloc(NumPts+1, sizeof(double));
    Gate_I_Low = (double *)calloc(NumPts+1, sizeof(double));
    Gate_T_High = (double *)calloc(NumPts+1, sizeof(double));    
    Gate_T_Low = (double *)calloc(NumPts+1, sizeof(double));    
    Drain_V_High = (double *)calloc(NumPts+1, sizeof(double));
    Drain_I_High = (double *)calloc(NumPts+1, sizeof(double));
    Drain_V_Low = (double *)calloc(NumPts+1, sizeof(double));
    Drain_I_Low = (double *)calloc(NumPts+1, sizeof(double));
    Drain_T_High = (double *)calloc(NumPts+1, sizeof(double));    
    Drain_T_Low = (double *)calloc(NumPts+1, sizeof(double));    

}
void FreeArrays_PMU_IV_Sw()
{
    //Free memory for arrays before exiting UTM
    if (Gate_V_High != NULL)
        free(Gate_V_High);
    if (Gate_I_High != NULL)
        free(Gate_I_High);
    if (Gate_V_Low != NULL)
        free(Gate_V_Low);
    if (Gate_I_Low != NULL)
        free(Gate_I_Low);
    if (Gate_T_High != NULL)
        free(Gate_T_High);
    if (Gate_T_Low != NULL)
        free(Gate_T_Low);
    if (Drain_V_High != NULL)
        free(Drain_V_High);
    if (Drain_I_High != NULL)
        free(Drain_I_High);
    if (Drain_V_Low != NULL)
        free(Drain_V_Low);
    if (Drain_I_Low != NULL)
        free(Drain_I_Low);
    if (Drain_T_High != NULL)
        free(Drain_T_High);
    if (Drain_T_Low != NULL)
        free(Drain_T_Low);
    
/* USRLIB MODULE END  */
} 		/* End PMU_IV_sweep_Example.c */

