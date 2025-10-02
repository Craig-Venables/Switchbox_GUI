/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_ScopeShot_Example
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 71
	ARGUMENTS:
		PW_Gate,	double,	Input,	200e-9,	60e-9,	.999999
		RiseTimeGate,	double,	Input,	40e-9,	20e-9,	0.033
		FallTimeGate,	double,	Input,	40e-9,	20e-9,	0.033
		DelayGate,	double,	Input,	100e-9,	0,	.999999
		PW_Drain,	double,	Input,	300e-9,	60e-9,	.999999
		RiseTimeDrain,	double,	Input,	100e-9,	20e-9,	.033
		FallTimeDrain,	double,	Input,	100e-9,	20e-9,	.033
		DelayDrain,	double,	Input,	100e-9,	0,	.999999
		Period,	double,	Input,	5e-6,	120e-9,	1
		MeasStartGate,	double,	Input,	0.65,	0,	1
		MeasStopGate,	double,	Input,	0.80,	0,	1
		PulseAverage,	int,	Input,	1,	1,	10000
		LoadLineGate,	int,	Input,	1,	0,	1
		LoadLineDrain,	int,	Input,	1,	0,	1
		ResGate,	double,	Input,	1e6,	1,	1e6
		ResDrain,	double,	Input,	1e6,	1,	1e6
		AmplVGate,	double,	Input,	1,	-40,	40
		BaseVGate,	double,	Input,	0,	-40,	40
		AmplVDrain,	double,	Input,	2,	-40,	40
		BaseVDrain,	double,	Input,	0,	-40,	40
		VRangeGate,	double,	Input,	10,	5,	40
		IRangeGate,	double,	Input,	0.01,	1e-7,	.8
		LtdAuto_I_Gate,	double,	Input,	0,	0,	1
		VRangeDrain,	double,	Input,	10,	5,	40
		IRangeDrain,	double,	Input,	0.2,	1e-7,	.8
		LtdAuto_I_Drn,	double,	Input,	0,	0,	1
		GateCh,	int,	Input,	1,	1,	2
		DrainCh,	int,	Input,	2,	1,	2
		MaxSheetRows,	int,	Input,	3000,	100,	32767
		Thrshld_I_Gate,	double,	Input,	1,	1e-12,	1
		ThresholdVoltGate,	double,	Input,	40,	0,	42
		ThresholdPwrGate,	double,	Input,	8,	1e-12,	10
		ThresholdCurrDrain,	double,	Input,	1,	1e-12,	1
		ThresholdVoltDrain,	double,	Input,	40,	0,	42
		ThresholdPwrDrain,	double,	Input,	8,	0,	10
		PrePulse,	double,	Input,	.2,	0,	1
		PostPulse,	double,	Input,	.2,	0,	1
		PMUMode,	int,	Input,	0,	0,	1
		SMU_V,	double,	Input,	0,	-210,	+210
		SMU_Irange,	double,	Input,	.01,	10e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		SMU_ID,	char *,	Input,	"NONE",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		Gate_TimeStamp,	D_ARRAY_T,	Output,	,	,	
		Gate_TimeStamp_Size,	int,	Input,	3000,	,	32767
		Gate_V,	D_ARRAY_T,	Output,	,	,	
		Gate_V_Size,	int,	Input,	3000,	,	32767
		Gate_I,	D_ARRAY_T,	Output,	,	,	
		Gate_I_Size,	int,	Input,	3000,	,	32767
		Drain_TimeStamp,	D_ARRAY_T,	Output,	,	,	
		Drain_TimeStamp_Size,	int,	Input,	3000,	,	32767
		Drain_V,	D_ARRAY_T,	Output,	,	,	
		Drain_V_Size,	int,	Input,	3000,	,	32767
		Drain_I,	D_ARRAY_T,	Output,	,	,	
		Drain_I_Size,	int,	Input,	3000,	,	32767
		SpotMean_StartWind,	D_ARRAY_T,	Output,	,	,	
		SpotMean_StartWind_Size,	int,	Input,	1,	,	
		SpotMean_StopWind,	D_ARRAY_T,	Output,	,	,	
		SpotMean_StopWind_Size,	int,	Input,	1,	,	
		Gate_V_Ampl_SM,	D_ARRAY_T,	Output,	,	,	
		Gate_V_Ampl_SM_Size,	int,	Input,	1,	,	
		Gate_I_Ampl_SM,	D_ARRAY_T,	Output,	,	,	
		Gate_I_Ampl_SM_Size,	int,	Input,	1,	,	
		Drain_V_Ampl_SM,	D_ARRAY_T,	Output,	,	,	
		Drain_V_Ampl_SM_Size,	int,	Input,	1,	,	
		Drain_I_Ampl_SM,	D_ARRAY_T,	Output,	,	,	
		Drain_I_Ampl_SM_Size,	int,	Input,	1,	,	
		Status_Gate,	I_ARRAY_T,	Output,	,	,	
		Status_Gate_Size,	int,	Input,	1,	,	
		Status_Drain,	I_ARRAY_T,	Output,	,	,	
		Status_Drain_Size,	int,	Input,	1,	,	
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_PMU_ScpSht(int NumPts);
void FreeArrays_PMU_ScpSht();

double *GateV_All = NULL, *GateI_All = NULL, *GateT_All = NULL;
double *DrainV_All = NULL, *DrainI_All = NULL, *DrainT_All = NULL;

unsigned long *GateS_All = NULL, *DrainS_All = NULL;

#pragma warning( disable: 4996 )

	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->

<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: PMU_ScopeShot_Example
=============================

Description
-----------

Pulse IV waveform capture using 2 channels of a single 4225-PMU card. The 
Gate channel outputs a pulse train (no change in pulse base or amplitude),
while the Drain channel outputs a swept pulse amplitude.

This module allows for more control of the PMU than with pulsed I-V in an ITM:
different pulse timing parameters.

This routine allows for independent pulse width, rise, fall and delay parameters 
to be set for the 2 channels. Note that the period is the same for both channels. 
The measurement window is also the same for both channels and is set by 
MeasStartGate and MeasStopGate (more information in INPUTS below).

Optional SMU available for voltage biasing of a device terminal that does 
not react to the pulse. For example, do not connect SMU to DUT drain, gate, 
or source of a transistor. Note that the SMU cannot be connected to an RPM, 
or a -233 error ("forcev(): Cannot force when not connected.") will occur.

This routine returns data with a method compatible with KXCI (UL mode).

~~~~
                         ______**__              _
                        /          \             |
                       / DrainPulse \            |
                      /              \           |
                     /<--PulseWidth-->\        AmplVDrain
                    /     PW_Drain     \         |
  _________________/                    \________|________BaseVDrain
  DelayDrain  RiseTimeDrain    FallTimeDrain 
~~~~

~~~~
                     __________**______              _
                    /                  \             |
                   /    Gate Pulse      \            |
                  /                      \           |
                 /<------PulseWidth------>\        AmplVGate
                /          PW_Gate         \         |
  _____________/                            \________|________BaseVGate
  DelayGate  RiseTimeGate            FallTimeGate 
  |<---------------Period------------------------------------>|
   ** = Measure window
~~~~

This routine also approximates the spot mean measurement at the top, settled 
portion of the pulse. The returned spot means for the 2 channels are 
synchronous. By definition, the measure window for the spot mean will be within 
the pulse top of the gate pulse, but this routine requires that the spot mean 
is also within the pulse top of the drain.  

If the spot mean for the gate pulse top is not within the drain pulse top, 
an error will result and the test will not run. To fix the error, adjust the
timing parameters for the drain so that there is some overlap (in time) 
between the gate and drain pulse tops.

The sample rate is automatically chosen to ensure that the maximum number of 
samples (stored on the card during the test) does not exceed MaxSheetRows per 
A/D (4 A/Ds per card, for I & V on each of the 2 channels). It also adjusts 
the sample rate to ensure that the maximum number of samples multiplied by 
the PulseAverage (number of pulses to output) does not exceed the maximum 
samples per A/D per test of 1,000,000.

To capture pre-pulse points before the rising edge of the pulse, set 
DelayGate > 0 and DelayDrain > 0, as well as PrePulse and PostPulse >= 0.2.

This routine attempt to keep the number of samples returned for both channels 
equal, but rounding errors may cause a slight mismatch between the two channels.

This uses Gate and Drain naming convention, but any 2 channel sweep test may 
use this routine.

Inputs
------

PW_Gate
: (double) Pulse Width of gate channel (FWHM), in seconds.
: Range: 60e-9 to 0.999999 s

RiseTimeGate		
: (double) Fall Time of gate channel (0 to 100%), in seconds.
			Note that slower transition times are slew rate limited, 
			so to reach the slowest transition time, the largest 
			voltage amplitude must be used.
: Range: 20e-9 to 0.033 s

FallTimeGate		
: (double) Fall Time of gate channel (0 to 100%), in seconds.
			Note that slower transition times are slew rate limited, 
			so to reach the slowest transition time, the largest 
			voltage amplitude must be used.
: Range: 20e-9 to 0.033 s

DelayGate		
: (double) Delay time for gate channel, in seconds. Useful
			for aligning gate and drain pulses of differing widths.
: Range: 0 to 0.999999 s.

PW_Drain	
: (double) Pulse Width of drain channel (FWHM), in seconds.
: Range: 60e-9 to 0.999999 s

RiseTimeDrain	
: (double) Fall Time of drain channel (0 to 100%), in seconds.
			Note that slower transition times are slew rate limited, 
			so to reach the slowest transition time, the largest 
			voltage amplitude must be used.
: Range: 20e-9 to 0.033 s

FallTimeDrain	
: (double) Fall Time of drain channel (0 to 100%), in seconds.
			Note that slower transition times are slew rate limited, 
			so to reach the slowest transition time, the largest 
			voltage amplitude must be used.
: Range: 20e-9 to 0.033 s

DelayDrain		
: (double) Delay time for drain channel, in seconds. Useful
			for aligning gate and drain pulses of differing widths.
: Range: 0 to 0.999999 s.

Period			
: (double) Pulse period for both gate and drain, in seconds.
: Range: 120e-9 to 1 s.

MeasStartGate		
: (double) Start of measure window for gate spot mean, 
			as percentage of pulse top (see diagram above).
: Range: 0.001 to 0.99, 

MeasStopGate		
: (double) End of measure window for gate spot mean, 
			as percentage of pulse top (see diagram above).
: Range: 0.001 to 0.99.

PulseAverage		
: Number of pulses to output and average together.
: Range: 1 to 10000.

LoadLineGate		
: Load Line Effect Compensation for the Gate terminal
			LLEC is an algorithm that compensates for the output
			resistance of the PMU, or PMU+RPM. Enabling LLEC will
			permit the source voltage across the DUT to match
			the programmed voltages. This is primarily important on
			high current terminals like a tranisistor drain:
: 1: LLEC enabled
: 0: LLEC disabled

LoadLineDrain	
: Load Line Effect Compensation for the Drain terminal
			LLEC is an algorithm that compensates for the output
			resistance of the PMU, or PMU+RPM. Enabling LLEC will
			permit the source voltage across the DUT to match
			the programmed voltages. This is primarily important on
			high current terminals like a tranisistor drain:
: 1: LLEC enabled
: 0: LLEC disabled

ResGate
: (double) Range: 1 to 1e6

ResDrain
: (double) Range: 1 to 1e6

AmplVGate
: (double) Pulse Voltage Amplitude of Gate (height from base voltage).

BaseVGate
: (double) Base voltage (DC offset) for Gate.

AmplVDrain
: (double) Pulse Voltage Amplitude of Drain (height from base voltage).

BaseVDrain
: (double) Base voltage (DC offset) for Drain.

VRangeGate
: (double) Gate Voltage:
: Range: (+/-) 10 or (+/-) 40

IRangeGate
: (double) Gate (PMU Ch 1) Current Measure Range.
  Note that available ranges differ based on Voltage Range and if an RPM is connected.

LtdAuto_I_Gate
: (double) Range: 0 to 1

VRangeDrain
: (double) Drain Voltage:
: Range: (+/-) 10 or (+/-) 40

IRangeDrain
: (double) Drain (PMU Ch 2) Current Measure Range.
  Note that available ranges differ based on Voltage Range and if an RPM is connected.

LtdAuto_I_Drn
: (double) Range: 0 to 1

GateCh
: (int) Range: 1 or 2

DrainCh
: (int) Range: 1 or 2

MaxSheetRows
: (int) Determines the maximum number of samples for the waveform.

Thrshld_I_Gate
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

PrePulse
: (double) Amount of waveform to
			capture before the pulse rising
			edge. This value is a percent-
			age of the total pulse time,
			where total_pulse_time = 
			0.5 * rise + PW + 0.5 * fall.
			Pulse delay (either DelayGate 
			or DelayDrain) must be large
			enough to permit the pre-
			waveform to be captured. This
			value has no impact on the 
			spot mean measurements determined
			by MeasStartPercGate and
			MeasStopPercGate.
: Range: 0 to 1

PostPulse	
: (double) Amount of waveform to
			capture before the pulse rising
			edge. This value is a percentage
    		of the total pulse time,
			where total_pulse_time = 
			0.5 * rise + PW + 0.5 * fall.
			Pulse period must be long
			enough to permit the
			pre-waveform to be captured. This
			value has no impact on the 
			spot mean measurements determined
			by MeasStartPercGate and
			MeasStopPercGate.
: Range: 0 to 1

PMUMode			
: (int) PMU Test Execution mode. Controls test execution. If
			auto-ranging, Load Line Effect compensation or thresholds 
			(volt, current, power) are desired, then set PMUMode = 1, 
			otherwise use PMUMode = 0.  Note that Mode = 0 will result in
			shorter test times, but permits only fixed current ranges and 
			no LLE comp and no IVP threshold comparisons:
: 0: Simple
: 1: Advanced

SMU_V		
: (double) SMU voltage for biasing non-pulsed DUT terminal. For
			example, do not connect SMU to transistor source terminal when
			pulsing gate and/or drain.
: Range: -210 to +210 V

SMU_Irange		
: (double) SMU current range. 
: Ranges: 10e-9, 100e-9, 1e-6,
				10e-6, 100e-6, 1e-3,
				10e-3, 100e-3, 1
: Note: 10e-9 requires pramplifier and
			1 A range only available on high
			power SMU.

SMU_Icomp	
: (double) SMU current compliance. This value must > 10% 
			of the SMU_Irange value.

SMU_ID		
: SMU instrument name, such as "SMU1" (without quotes). For no
			SMU, use "NONE". Note that the SMU cannot be connected to an
			RPM, or a -233 error ("forcev(): Cannot force when not connected.")
			will occur.
: Range: NONE, SMU1, SMU2, up to maximum SMUs in system.

PMU_ID	
: PMU instrument name, such as "PMU1" (without quotes).
: Range:  PMU1 thru PMU4.

Outputs
-------
* Status output argument is no longer supported. No data will be returned.

Name                    | Type      | Type   | Value| - | Value
----------------------  | --------- | ------ | ---- | - | -----
Gate_TimeStamp          | D_ARRAY_T | Output |      |   | 	
Gate_TimeStamp_Size     | int       | Input  | 3000 |   | 32767
GateV                   | D_ARRAY_T | Output |      |   |
GateV_Size              | int       | Input  | 3000 |   | 32767
Gate_I                  | D_ARRAY_T | Output |      |   |	
Gate_I_Size             | int       | Input  | 3000 |   | 32767
Drain_TimeStamp         | D_ARRAY_T | Output |      |   | 	
Drain_TimeStamp_Size    | int       | Input  | 3000 |   | 32767
Drain_V                 | D_ARRAY_T | Output |      |   |
Drain_V_Size            | int       | Input  | 3000 |   | 32767
Drain_I                 | D_ARRAY_T | Output |      |   | 
Drain_I_Size            | int       | Input  | 3000 |   | 32767
SpotMean_StartWind      | D_ARRAY_T | Output |      |   | 	
SpotMean_StartWind_Size | int       | Input  | 	1   |   | 
SpotMean_StopWind       | D_ARRAY_T | Output |      |   |
SpotMean_StopWind_Size  | int       | Input  |  1   |   |	
Gate_V_Ampl_SM          | D_ARRAY_T | Output |      |   |	
Gate_V_Ampl_SM_Size     | int       | Input  |  1   |   |	
Gate_I_Ampl_SM          | D_ARRAY_T | Output |      |   | 		
Gate_I_Ampl_SM_Size     | int       | Input  |  1   |   |		
Drain_V_Ampl_SM         | D_ARRAY_T | Output |      |   | 	
Drain_V_Ampl_SM_Size    | int       | Input  |  1   |   |
Drain_I_Ampl_SM         | D_ARRAY_T | Output |      |   | 	
Drain_I_Ampl_SM_Size    | int       | Input  |  1   |   |		
*Status_Gate             | D_ARRAY_T | Output |      |   | 	
Status_Gate_Size        | int       | Input  | 3000 |   |32767
*Status_Drain            | D_ARRAY_T | Output |      |   | 	
Status_Drain_Size       | int       | Input  | 3000 |   | 32767


Return values
-------------
			 
Value  | Description
------ | -----------
0      | OK.
-122   | pulse_ranges(): Illegal value for parameter #7.
       | Ensure that current measure range is appropriate for the chosen voltage range.
-233   | Cannot force when not connected. Ensure that specified SMU is not
       | connected through or associated with an RPM.
       | If all SMUs are associated with RPM modules,
       | choose NONE to permit the test to run.
-829   | pulse_sweep_linear(): The sum of base and amplitude voltages (XX.XV)
       | exceeds maximum (YYV) for present range. The Base + Amplitude voltage is too
       | large for the chosen PMU voltage range. Check the BaseVCh1, StartVCh1 and StopVCh1
       | for voltages that exceed VRangeCh1. If necessary, increase VRangeCh1 to the maximum 40V range.
-824   | pulse_exec(): Invalid pulse timing parameters. One or more timing parameters
       | (PulseWidthCh1, RiseTimeCh1, FallTimeCh1, DelayCh1 or Period) are too small
       | for the chosen VRangeCh1. Increase the time of the appropriate parameters.
-17001 | Wrong card Id. Check PMU and SMU names.
-17002 | Failure to assign card ID handle. Check PMU and/or SMU names.
-17100 | Gate Measure window outside of Drain Pulse top.  Adjust gate measure window,
       | gate pulse timing, or drain pulse timing.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_PMU_ScpSht(int NumPts);
void FreeArrays_PMU_ScpSht();

double *GateV_All = NULL, *GateI_All = NULL, *GateT_All = NULL;
double *DrainV_All = NULL, *DrainI_All = NULL, *DrainT_All = NULL;

unsigned long *GateS_All = NULL, *DrainS_All = NULL;

#pragma warning( disable: 4996 )


int PMU_ScopeShot_Example( double PW_Gate, double RiseTimeGate, double FallTimeGate, double DelayGate, double PW_Drain, double RiseTimeDrain, double FallTimeDrain, double DelayDrain, double Period, double MeasStartGate, double MeasStopGate, int PulseAverage, int LoadLineGate, int LoadLineDrain, double ResGate, double ResDrain, double AmplVGate, double BaseVGate, double AmplVDrain, double BaseVDrain, double VRangeGate, double IRangeGate, double LtdAuto_I_Gate, double VRangeDrain, double IRangeDrain, double LtdAuto_I_Drn, int GateCh, int DrainCh, int MaxSheetRows, double Thrshld_I_Gate, double ThresholdVoltGate, double ThresholdPwrGate, double ThresholdCurrDrain, double ThresholdVoltDrain, double ThresholdPwrDrain, double PrePulse, double PostPulse, int PMUMode, double SMU_V, double SMU_Irange, double SMU_Icomp, char *SMU_ID, char *PMU_ID, double *Gate_TimeStamp, int Gate_TimeStamp_Size, double *Gate_V, int Gate_V_Size, double *Gate_I, int Gate_I_Size, double *Drain_TimeStamp, int Drain_TimeStamp_Size, double *Drain_V, int Drain_V_Size, double *Drain_I, int Drain_I_Size, double *SpotMean_StartWind, int SpotMean_StartWind_Size, double *SpotMean_StopWind, int SpotMean_StopWind_Size, double *Gate_V_Ampl_SM, int Gate_V_Ampl_SM_Size, double *Gate_I_Ampl_SM, int Gate_I_Ampl_SM_Size, double *Drain_V_Ampl_SM, int Drain_V_Ampl_SM_Size, double *Drain_I_Ampl_SM, int Drain_I_Ampl_SM_Size, int *Status_Gate, int Status_Gate_Size, int *Status_Drain, int Status_Drain_Size )
{
/* USRLIB MODULE CODE */
    int status;
    double TimePulseGate, TimePulseDrain;
    double TimePulse, TimeCaptured;
    double Gate_V_SM, Gate_I_SM; 
    double Drain_V_SM, Drain_I_SM;    
    int NumSamplesTimeCaptured;
    int NumSamplesFetchGate;
    int NumSamplesFetchDrain;

    int verbose = 0;
    int TestMode;
    char ErrMsgChar[150];
    char No_SMU[10] = "NONE";
 
    

    //Gate measure timing parameters
    double PulseTopTimeGate;
    double PulseTopMeasStartGate, PulseTopMeasStopGate;

    //Drain measure timing parameters
    double PulseTopTimeDrain;
    double PulseTopStartTimeDrain, PulseTopStopTimeDrain;

    double MeasStartPercGate, MeasStopPercGate;
    double MeasStartPercDrain, MeasStopPercDrain;

    double RateFactor, SampleRate;
    double TimeBeforePulse, TimeAfterPulse;
    double BeforePulseExtraPerc, AfterPulseExtraPerc;
    double BeforePulseExtraPercGate, AfterPulseExtraPercGate;
    double BeforePulseExtraPercDrain, AfterPulseExtraPercDrain;
    int InstId, SMUId;
    int i, j;
    double elapsedt;
    boolean SMUPresent;
    
    //Initialize variables
    j = 0;
    Gate_V_SM = 0;
    Gate_I_SM = 0;
    Drain_V_SM = 0;
    Drain_I_SM = 0;
    SampleRate = 200E+6;
    RateFactor = 0.0;    
    SMUId = 0;
    SMUPresent = FALSE;
    MeasStartPercGate = MeasStartGate;
    MeasStopPercGate = MeasStopGate;
    BeforePulseExtraPerc = PrePulse;
    AfterPulseExtraPerc = PostPulse;
//    verbose = 1;        //prints out status messages to Message Console (type msgcon at command prompt)

    if ( verbose )
        printf("PMU_ScopeShot: ======== New run =====");

    //Check: is requested PMU card in the chassis?
    if ( !LPTIsInCurrentConfiguration(PMU_ID) )
    {
        printf("Instrument %s is not in system configuration", PMU_ID);
        return ERR_PMU_EXAMPLES_WRONGCARDID;
    }

    //Convert PMU card string into identifying instrument card number
    getinstid(PMU_ID, &InstId);
    if ( -1 == InstId )
        return -2;

    //Check: is a SMU ID set (SMUx or NONE)?  If a SMU string, is in the the chassis?
    if ( _stricmp(SMU_ID, No_SMU) )
    {
        if ( verbose )
            printf("PMU_ScopeShot_Example: SMU string present, %s", SMU_ID);

        if ( !LPTIsInCurrentConfiguration(SMU_ID) )
        {
            printf("PMU_ScopeShot_Example: Instrument %s is not in system configuration", PMU_ID);
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
            printf("PMU_ScopeShot_Example: No SMU specified, SMU_ID = %s", SMU_ID);
    }

    //Ensure that 4225-RPM (if attached) is in the pulse mode
    status = rpm_config(InstId, GateCh, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
        return status ;

    status = rpm_config(InstId, DrainCh, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
        return status ;

    status = pg2_init(InstId, PULSE_MODE_PULSE);
    if ( status )
       return status ;

    if ( SMUPresent )
    {
        if ( verbose )
            printf("PMU_ScopeShot: SMU present, V= %g, Irange= %g", SMU_V, SMU_Irange);

        status = rangei(SMUId, SMU_Irange);
        if ( status )
            return status ;

        status = limiti(SMUId, SMU_Icomp);
        if ( status )
            return status ;

        status = forcev(SMUId, SMU_V);
        if ( status )
            return status ;
    }

    //Determine if return array sizes are big enough to contain
    //the desired number of rows (from MaxSheetPoints)
    if (MaxSheetRows > Gate_TimeStamp_Size || MaxSheetRows > Gate_V_Size || MaxSheetRows > Gate_I_Size || MaxSheetRows > Drain_TimeStamp_Size || MaxSheetRows > Drain_V_Size || MaxSheetRows > Drain_I_Size || MaxSheetRows > Status_Gate_Size  || MaxSheetRows > Status_Drain_Size)
    {
        if (verbose)
            printf("PMU_ScopeShot: One or more Output array size(s) < MaxSheetRows. Increase size of all Output arrays to be at least %d", MaxSheetRows);
        sprintf(ErrMsgChar, "One or more Output array size(s) < MaxSheetRows. Increase size of all Output arrays to be at least %d.", MaxSheetRows);
        logMsg(MF_Error, ERROR_STRING, ErrMsgChar); 
        return ERR_PMU_EXAMPLES_OUTPUT_ARRAY_TOO_SMALL;
    }


    //Calcuate fundamental times: Pulse tops, measure start and stop
    //These are used below
    PulseTopTimeGate = PW_Gate - (0.5 * RiseTimeGate) - (0.5 * FallTimeGate);
    PulseTopMeasStartGate = DelayGate + RiseTimeGate + (PulseTopTimeGate*MeasStartPercGate);
    PulseTopMeasStopGate = DelayGate + RiseTimeGate + (PulseTopTimeGate*MeasStopPercGate);

    PulseTopTimeDrain = PW_Drain - (0.5 * RiseTimeDrain) - (0.5 * FallTimeDrain);
    PulseTopStartTimeDrain = DelayDrain + RiseTimeDrain;
    PulseTopStopTimeDrain = DelayDrain + RiseTimeDrain + PulseTopTimeDrain;       

    if ( verbose )
        printf("PMU_ScopeShot: StrtMeas= %g s, StpMeas= %g s, StrtDrnTop= %g s, StpDrnTop= %g s", PulseTopMeasStartGate, PulseTopMeasStopGate, PulseTopStartTimeDrain, PulseTopStopTimeDrain);

    if ( verbose )
        printf("PMU_ScopeShot: GateStrtMeas%= %g perc, GateStpMeas%= %g perc", (PulseTopMeasStartGate- DelayGate - RiseTimeGate)/PulseTopTimeGate, (PulseTopMeasStopGate- DelayGate - RiseTimeGate)/PulseTopTimeGate);

    //Determine if the gate measurement window for the pulse top is 
    //within the pulse top of the drain.  If not, error and stop running the UTM.

    if (PulseTopMeasStartGate < PulseTopStartTimeDrain || PulseTopMeasStartGate > PulseTopStopTimeDrain || PulseTopMeasStopGate < PulseTopStartTimeDrain || PulseTopMeasStopGate > PulseTopStopTimeDrain)
    {
        printf("PMU_ScopeShot: Error, Meas window (%g to %g s) not within drain pulse top (%g s to %g s)", PulseTopMeasStartGate, PulseTopMeasStopGate, PulseTopStartTimeDrain, PulseTopStopTimeDrain);
        sprintf(ErrMsgChar, "Measurement window (%g to %g s) not within drain pulse top (%g to %g s)", PulseTopMeasStartGate, PulseTopMeasStopGate, PulseTopStartTimeDrain, PulseTopStopTimeDrain);
        logMsg(MF_Error, ERROR_STRING, ErrMsgChar); 
        return ERR_PMU_EXAMPLES_MEAS_EARLY;
    }

    //Calculate the Start & Stop measure window percentages for the 
    //Drain, must be synchronous with Gate
    MeasStartPercDrain = (PulseTopMeasStartGate - DelayDrain - RiseTimeDrain) / PulseTopTimeDrain;
    MeasStopPercDrain = (PulseTopMeasStopGate - DelayDrain - RiseTimeDrain) / PulseTopTimeDrain;

    if ( verbose )
        printf("PMU_ScopeShot: DrainStrtMeas%= %g perc, DrainStpMeas%= %g perc", MeasStartPercDrain, MeasStopPercDrain);

    //Calculate the Time for each pulse (rise + pulse top + fall)
    TimePulseGate = PulseTopTimeGate + FallTimeGate + FallTimeGate;
    TimePulseDrain = PulseTopTimeDrain + FallTimeDrain + FallTimeDrain;

    if ( verbose )
        printf("PMU_ScopeShot: GatePlsTime= %g, DrainPslTime= %g", TimePulseGate, TimePulseDrain);

    //Determine widest pulse, which will set overall time capture of pulse for both channels
    if (TimePulseGate >= TimePulseDrain)
        TimePulse = TimePulseGate;
    else
        TimePulse = TimePulseDrain;        

    //Calculate the extra time to capture before and after the pulse    
    TimeBeforePulse = BeforePulseExtraPerc * TimePulse;
    TimeAfterPulse = AfterPulseExtraPerc * TimePulse;

    //Calculate total time that is captured
    TimeCaptured = TimePulse + TimeBeforePulse + TimeAfterPulse;

    if ( verbose )
        printf("PMU_Scopeshot: TtlTimeWfm= %g, Pulse= %g, BfrPls= %g, AftrPls= %g", TimeCaptured, TimePulse, TimeBeforePulse, TimeAfterPulse);

    if ( verbose )
        printf("PMU_Scopeshot: PlsTm= %g, GatePls= %g, Extra Time for Gate= %g", TimePulse, TimePulseGate, (0.5 * (TimePulse - TimePulseGate))/TimePulseGate);

    //Calculate percentages of extra waveform to capture, unique to gate and drain
    //To make each waveform have the same number of samples
    //The last term (0.5 + (TimePulse - TimePulseGate or Drain)/TimePulseGate or Drain
    //adds the extra points (equally to pre- and post-) for unequal
    //pulse widths.  Note that for the widest pulse (TimePulse - TimePulseGate or Drain) = 0, 
    //so nothing is added to the wider pulse (except for the specified PrePulse and PostPulse)
    BeforePulseExtraPercGate = TimeBeforePulse / TimePulseGate + (0.5 * (TimePulse - TimePulseGate))/TimePulseGate;
    AfterPulseExtraPercGate = TimeAfterPulse / TimePulseGate + (0.5 * (TimePulse - TimePulseGate))/TimePulseGate;    
    BeforePulseExtraPercDrain = TimeBeforePulse / TimePulseDrain + (0.5 * (TimePulse - TimePulseDrain))/TimePulseDrain;
    AfterPulseExtraPercDrain = TimeAfterPulse / TimePulseDrain + (0.5 * (TimePulse - TimePulseDrain))/TimePulseDrain;    

    //Ensure that no pre- or post-pulse data is > 100 % (1.0), necessary for Clarius 8.0 release
    if (BeforePulseExtraPercGate > 1.0)
        BeforePulseExtraPercGate = 1.0;
    if (AfterPulseExtraPercGate > 1.0)
        AfterPulseExtraPercGate = 1.0;
    if (BeforePulseExtraPercDrain > 1.0)
        BeforePulseExtraPercDrain = 1.0;
    if (AfterPulseExtraPercDrain > 1.0)
        AfterPulseExtraPercDrain = 1.0;

    if ( verbose )
        printf("PMU_Scopeshot: GatePre= %g, GatePost= %g, DrnPre= %g, DrnPost= %g", BeforePulseExtraPercGate, AfterPulseExtraPercGate, BeforePulseExtraPercDrain, AfterPulseExtraPercDrain);

    //Calculate number of sample points (per A/D) required for the test
    //Max sample rate is 200E6, same rate used for both channels on card
    NumSamplesTimeCaptured = (int)(TimeCaptured * SampleRate);

    if ( verbose )
        printf("PMU_ScopeShot: Ch1 PW= %g, PlsTop= %g", PW_Gate, PulseTopTimeGate);

    //if total samples for the test > MaxSamplesPerAtoD, then set sample_rate to lower value
    if ((NumSamplesTimeCaptured * PulseAverage) > MaxSamplesPerAtoD)
    {
        RateFactor = (int)((NumSamplesTimeCaptured / MaxSamplesPerAtoD) + 1);      
        SampleRate = (SampleRate / RateFactor);
        if ( verbose )
            printf("PMU_ScopeShot:  NumSamplesTimeCaptured > MaxSamplesPerAtoD, Ratefactor= %d", RateFactor);
    }

    if (NumSamplesTimeCaptured > MaxSheetRows)
    {
        RateFactor = (int)((NumSamplesTimeCaptured / MaxSheetRows) + 1);      
        SampleRate = (SampleRate / RateFactor);
        if ( verbose )
            printf("PMU_ScopeShot:  NumSamplesTimeCaptured > MaxSheetRows, Ratefactor= %d", RateFactor);
    }

    //Calculate total number of samples for the required capture time, with final sample rate
    NumSamplesTimeCaptured  = (int)(TimeCaptured * SampleRate);    

    //Size arrays appropriately
    AllocateArrays_PMU_ScpSht(NumSamplesTimeCaptured);

    if ( verbose )
        printf("PMU_ScopeShot: NumTtlSmpls= %d, SampleRate= %g", NumSamplesTimeCaptured, SampleRate);

    //Set PMU to return actual values when measurement overflow occurs
    status = setmode(InstId, KI_LIM_MODE, KI_VALUE);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    //Set the PMU sample rate
    status = pulse_sample_rate(InstId, SampleRate);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    if ( verbose )
        printf("PMU_ScopeShot: Using new sample rate, NumTotalSamples= %d, SampleRate= %g", NumSamplesTimeCaptured, SampleRate);

    //Set Gate source and measure ranges
    if (LtdAuto_I_Gate)
    {
        //Set source range and auto-range for I measure
        status = pulse_ranges(InstId, GateCh, VRangeGate, PULSE_MEAS_FIXED, VRangeGate, PULSE_MEAS_LTD_AUTO, IRangeGate);
        if ( status )
        {
            FreeArrays_PMU_ScpSht();
            return status ;
        }
    }
    else
    {
        //Set source range and fixed range for I measure
        status = pulse_ranges(InstId, GateCh, VRangeGate, PULSE_MEAS_FIXED, VRangeGate, PULSE_MEAS_FIXED, IRangeGate);
        if ( status )
        {
            FreeArrays_PMU_ScpSht();
            return status ;
        }
    }

    //Set Drain source and measure ranges
    if (LtdAuto_I_Drn)
    {
        status = pulse_ranges(InstId, DrainCh, VRangeDrain, PULSE_MEAS_FIXED, VRangeDrain, PULSE_MEAS_LTD_AUTO, IRangeDrain);
        if ( status )
        {
            FreeArrays_PMU_ScpSht();
            return status ;
        }
    }
    else
    {
        status = pulse_ranges(InstId, DrainCh, VRangeDrain, PULSE_MEAS_FIXED, VRangeDrain, PULSE_MEAS_FIXED, IRangeDrain);
        if ( status )
        {
            FreeArrays_PMU_ScpSht();
            return status ;
        }
    }

    //If load line effect compensation for the gate is disabled and PMU execution mode = 0 (simple), set desired resistance
    if (!LoadLineGate || !PMUMode)
    {
        status = pulse_load(InstId, GateCh, ResGate);
        if ( status )
        {
            FreeArrays_PMU_ScpSht();
            return status ;
        }
    }

    //If load line effect compensation for the drain is disabled and PMU execution mode = 0 (simple), set desired resistance
    if (!LoadLineDrain || !PMUMode)
    {
        status = pulse_load(InstId, DrainCh, ResDrain);
        if ( status )
        {
            FreeArrays_PMU_ScpSht();
            return status ;
        }
    }

    //Set Gate pulse source timing
    status = pulse_source_timing(InstId, GateCh, Period, DelayGate, PW_Gate, RiseTimeGate, FallTimeGate);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    //Set Drain pulse source timing
    status = pulse_source_timing(InstId, DrainCh, Period, DelayDrain, PW_Drain, RiseTimeDrain, FallTimeDrain);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    //Set test-ending thresholds.  Note these are not hardware limits, but
    //test thresholds.  After the burst of pulses (count = PulseAverage),
    //the PMU will compare to the below settings. If the "limit" is reached
    //or exceeded, then the test will end.  Power = V * I
    status = pulse_limits(InstId, GateCh, ThresholdVoltGate, Thrshld_I_Gate, ThresholdPwrGate);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    status = pulse_limits(InstId, DrainCh, ThresholdVoltDrain, ThresholdCurrDrain, ThresholdPwrDrain);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    if ( verbose )
        printf("PMU_ScpShot: Gate StrtPerc= %g, StpPerc= %g", BeforePulseExtraPerc, AfterPulseExtraPerc);

    //Program the pulse base voltage, necessary when sweeping amplitude
    status = pulse_vlow(InstId, GateCh, BaseVGate);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    status = pulse_vhigh(InstId, GateCh, AmplVGate + BaseVGate);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    status = pulse_sweep_linear(InstId, GateCh, PULSE_AMPLITUDE_SP, AmplVGate, AmplVGate, 0.0);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    //Program the pulse base voltage
    status = pulse_vlow(InstId, DrainCh, BaseVDrain);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    status = pulse_vhigh(InstId, DrainCh, AmplVDrain + BaseVDrain);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    status = pulse_sweep_linear(InstId, DrainCh, PULSE_AMPLITUDE_SP, AmplVDrain, AmplVDrain, 0.0);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    //Enable Gate waveform measurements
    status = pulse_meas_wfm(InstId, GateCh, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, LoadLineGate);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    //Enable Drain waveform measurements
    status = pulse_meas_wfm(InstId, DrainCh, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, LoadLineDrain);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

//    status = pulse_meas_timing(InstId, GateCh, BeforePulseExtraPercGate, AfterPulseExtraPercGate, PulseAverage);
    status = pulse_meas_timing(InstId, GateCh, BeforePulseExtraPercGate, AfterPulseExtraPercGate, PulseAverage);
    if ( status )
    {
        printf("PMU_Scopshot:  pulse_meas_timing error:  Gate, PreData= %g, PostData= %g, NumPls= %d", BeforePulseExtraPercGate, AfterPulseExtraPercGate, PulseAverage);
        FreeArrays_PMU_ScpSht();
        return status ;
     }

    //Set Drain pulse measurement for span of pulse to be captured
//    status = pulse_meas_timing(InstId, DrainCh, BeforePulseExtraPercDrain, AfterPulseExtraPercDrain, PulseAverage);
    status = pulse_meas_timing(InstId, DrainCh, BeforePulseExtraPercDrain, AfterPulseExtraPercDrain, PulseAverage);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    status = pulse_output(InstId, GateCh, 1);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    status = pulse_output(InstId, DrainCh, 1);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    if ( verbose )
        printf("PMU_ScopeShot: Just prior to pulse_exec");

    //Set test execute mode to Simple or Advanced
    if (PMUMode ==0)
        TestMode = PULSE_MODE_SIMPLE;
    else
        TestMode = PULSE_MODE_ADVANCED;

    status = pulse_exec(TestMode);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    //Wait until test is finished
    while(pulse_exec_status(&elapsedt) == 1)
     Sleep(100);

    if ( verbose )
        printf("PMU_ScopeShot: Just after pulse_exec_status, test done, getting data");

    status = pulse_chan_status(InstId, GateCh, &NumSamplesFetchGate);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    status = pulse_chan_status(InstId, DrainCh, &NumSamplesFetchDrain);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    if ( verbose )
        printf("PMU_ScopeShot: pulse_chan_status: Num Gate Samples= %d, Num Drain Samples= %d", NumSamplesFetchGate, NumSamplesFetchDrain);

    //Retrieve data
    status = pulse_fetch(InstId, GateCh, 0, NumSamplesFetchGate, GateV_All, GateI_All, GateT_All, GateS_All);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    //Calculate spot means
    for (i = 0; i<NumSamplesFetchGate; i++)
    {
        if (GateT_All[i] >= PulseTopMeasStartGate && GateT_All[i] <= PulseTopMeasStopGate)
        {
            Gate_V_SM += GateV_All[i];
            Gate_I_SM += GateI_All[i];
            j++;
            if (verbose)
                printf("PMU_ScopeShot: i= %d, j= %d, Time= %g, Vg= %g, Ig= %g Gate running V= %g, I= %g", i, j, GateT_All[i], GateV_All[i], GateI_All[i], Gate_V_SM, Gate_I_SM);
        }
    }

    //Calculate spot mean (average) by taking the total value and dividing by the number (j) of samples totaled
    Gate_V_SM /= j;
    Gate_I_SM /= j;

    if (verbose)
        printf("PMU_ScopeShot: Gate Spot Means: V= %g, I= %g", Gate_V_SM, Gate_I_SM);


    //Fetch Drain waveform data
    status = pulse_fetch(InstId, DrainCh, 0, NumSamplesFetchDrain, DrainV_All, DrainI_All, DrainT_All, DrainS_All);
    if ( status )
    {
        FreeArrays_PMU_ScpSht();
        return status ;
    }

    if (verbose)
        printf("PMU_ScopeShot: Gate Num samples= %d, Drain Num samples= %d", NumSamplesFetchGate, NumSamplesFetchDrain);

    //Calculate Drain spot mean for V and I
    j = 0;
    for (i = 0; i<NumSamplesFetchDrain; i++)
    {
//        if (DrainT_All[i] >= PulseTopMeasStartGate && DrainT_All[i] < PulseTopMeasStopGate)
        if (DrainT_All[i] >= PulseTopMeasStartGate && DrainT_All[i] <= PulseTopMeasStopGate)
        {
            Drain_V_SM += DrainV_All[i];
            Drain_I_SM += DrainI_All[i];
            j++;
            if (verbose)
                printf("PMU_ScopeShot: i= %d, j= %d, Time= %g, Vd= %g, Id= %g Drain running V= %g, I= %g", i, j, DrainT_All[i], DrainV_All[i], DrainI_All[i], Drain_V_SM, Drain_I_SM);
        }
    }

    //Calculate spot mean (average) by taking the total value and dividing by the number (j) of samples totaled
    Drain_V_SM /= j;
    Drain_I_SM /= j;

    if (verbose)
        printf("PMU_ScopeShot: Drain Spot Means: V= %g, I= %g", Drain_V_SM, Drain_I_SM);

    //Copy to output arrays so this routine may be called from KXCI (using UL mode)
    for(i=0;i<NumSamplesFetchGate;++i)
    {
        Gate_V[i] = GateV_All[i];
        Gate_I[i] = GateI_All[i];
        Gate_TimeStamp[i] = GateT_All[i];

//        Status_Gate[i] = GateS_All[i];
//        Status_Drain[i] = DrainS_All[i];
        Drain_V[i] = DrainV_All[i];
        Drain_I[i] = DrainI_All[i];
        Drain_TimeStamp[i] = DrainT_All[i];
    }

    //Copy to outputs so this routine may be called from KXCI (using UL mode)
    *Gate_V_Ampl_SM = Gate_V_SM;
    *Gate_I_Ampl_SM = Gate_I_SM;
    *SpotMean_StartWind = PulseTopMeasStartGate;
    *SpotMean_StopWind = PulseTopMeasStopGate;
    *Drain_V_Ampl_SM = Drain_V_SM;
    *Drain_I_Ampl_SM = Drain_I_SM;
    
    //Post data arrays to Clarius Sheet
    PostDataDoubleBuffer("Gate_V", GateV_All, NumSamplesFetchGate);
    PostDataDoubleBuffer("Gate_I", GateI_All, NumSamplesFetchGate);        
    PostDataDoubleBuffer("Gate_TimeStamp", GateT_All, NumSamplesFetchGate);
    //Avoid returning PMU channel status to Clarius, is not generally useful or easily interpreted
//   PostDataIntBuffer("Status_Gate", GateS_All, NumSamplesFetchGate);

    PostDataDoubleBuffer("Drain_V", DrainV_All, NumSamplesFetchDrain);
    PostDataDoubleBuffer("Drain_I", DrainI_All, NumSamplesFetchDrain);        
    PostDataDoubleBuffer("Drain_TimeStamp", DrainT_All, NumSamplesFetchDrain);
    //Avoid returning PMU channel status to Clarius, is not generally useful or easily interpreted
//    PostDataIntBuffer("Status_Drain", DrainS_All, NumSamplesFetchDrain);

    //Post data scalars (spot means, timing window start & stop) to Clarius Sheet
    PostDataDouble("Gate_V_Ampl_SM", Gate_V_SM);
    PostDataDouble("Gate_I_Ampl_SM", Gate_I_SM);
    PostDataDouble("SpotMean_StartWind", PulseTopMeasStartGate);
    PostDataDouble("SpotMean_StopWind", PulseTopMeasStopGate);
    PostDataDouble("Drain_V_Ampl_SM", Drain_V_SM);
    PostDataDouble("Drain_I_Ampl_SM", Drain_I_SM);


    if ( SMUPresent )
    {
        if ( verbose )
            printf("PMU_ScopeShot: SMU present, setting voltage = 0");

        status = forcev(SMUId, 0);
        if ( status )
        {
            FreeArrays_PMU_ScpSht();
            return status ;
        }

    }

    FreeArrays_PMU_ScpSht();
    return 0;

}

void AllocateArrays_PMU_ScpSht(int NumPts)
{
    //Allocate arrays for Seg-arb: trigger, measure type, measure start, measure stop.  
    GateV_All = (double *)calloc(NumPts+2, sizeof(double));
    GateI_All = (double *)calloc(NumPts+2, sizeof(double));
    GateT_All = (double *)calloc(NumPts+2, sizeof(double));    
    GateS_All = (unsigned long *)calloc(NumPts+2, sizeof(unsigned long));    
    DrainV_All = (double *)calloc(NumPts+2, sizeof(double));
    DrainI_All = (double *)calloc(NumPts+2, sizeof(double));
    DrainT_All = (double *)calloc(NumPts+2, sizeof(double));    
    DrainS_All = (unsigned long *)calloc(NumPts+2, sizeof(unsigned long));    


}
void FreeArrays_PMU_ScpSht()
{
    //Free memory for arrays before exiting UTM
    if (GateV_All != NULL)
        free(GateV_All);
    if (GateI_All != NULL)
        free(GateI_All);
    if (GateT_All != NULL)
        free(GateT_All);
    if (GateS_All != NULL)
        free(GateS_All);
    if (DrainV_All != NULL)
        free(DrainV_All);
    if (DrainI_All != NULL)
        free(DrainI_All);
    if (DrainT_All != NULL)
        free(DrainT_All);
    if (DrainS_All != NULL)
        free(DrainS_All);

/* USRLIB MODULE END  */
} 		/* End PMU_ScopeShot_Example.c */

