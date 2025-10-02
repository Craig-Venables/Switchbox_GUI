/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_PulseWaveform_FileSave_Example
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 37
	ARGUMENTS:
		PulseTop,	double,	Input,	1e-6,	20e-9,	40
		RiseTime,	double,	Input,	100e-9,	20e-9,	.033
		FallTime,	double,	Input,	100e-9,	20e-9,	.033
		BaseTime,	double,	Input,	1e-6,	20e-9,	40
		DelayTime,	double,	Input,	100e-9,	20e-9,	40
		MaxSheetPoints,	long,	Input,	1000,	100,	32767
		MaxFilePoints,	long,	Input,	30000,	100,	1000000
		Ch1_VRange,	double,	Input,	10,	5,	40
		Ch1_IRange,	double,	Input,	0.200,	100e-9,	.8
		Ch1_V_Ampl,	double,	Input,	2,	-80,	+80
		Ch1_V_Base,	double,	Input,	0,	-40,	+40
		Ch2_VRange,	double,	Input,	10,	5,	40
		Ch2_IRange,	double,	Input,	0.200,	100e-9,	.8
		Ch2_StartV,	double,	Input,	1,	-80,	80
		Ch2_StopV,	double,	Input,	4,	-80,	80
		Ch2_StepV,	double,	Input,	1,	-80,	80
		Ch2_V_Base,	double,	Input,	0,	-40,	40
		Ch1_Res,	double,	Input,	1e6,	1,	1e6
		Ch2_Res,	double,	Input,	1e6,	1,	1e6
		SMU_V,	double,	Input,	0,	-210,	+210
		SMU_Irange,	double,	Input,	.01,	10e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		SMU_ID,	char *,	Input,	"NONE",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		SaveFile,	int,	Input,	1,	0,	1
		AppendTimeToFilename,	int,	Input,	0,	0,	1
		Filename,	char *,	Input,	"wavefrm_capture.csv",	,	
		TimeStamp,	D_ARRAY_T,	Output,	,	,	
		TimeStampSize,	int,	Input,	3000,	1,	32767
		Ch1_Vmeas,	D_ARRAY_T,	Output,	,	,	
		Ch1_VmeasSize,	int,	Input,	3000,	1,	32767
		Ch1_Imeas,	D_ARRAY_T,	Output,	,	,	
		Ch1_ImeasSize,	int,	Input,	3000,	1,	32767
		Ch2_Vmeas,	D_ARRAY_T,	Output,	,	,	
		Ch2_VmeasSize,	int,	Input,	3000,	1,	32767
		Ch2_Imeas,	D_ARRAY_T,	Output,	,	,	
		Ch2_ImeasSize,	int,	Input,	3000,	1,	32767
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
#include <time.h>

double *dstartv, *dstopv, *gstartv, *gstopv, *measstart, *measstop, *segtime;
long *ssrctrl, *meastypes, *trig;

void AllocateArrays_PMU_Wfm_File(int npts);
void FreeArrays_PMU_Wfm_File(void);
void FillSweepArrays_Wfm(double dstartV, double dstepV, double gbias, double gVlo, double dVlo, int numpts, double riset, double fallt, double pwidth, double baset, double delay);
BOOL LPTIsInCurrentConfiguration(char* hrid);
void GetPathFileExt(char*, char*, char*, char*);

#pragma warning( disable: 4996 )

	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->

<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: PMU_PulseWaveform_FileSave_Example
==========================================

Description
-----------

This module allows for a long pulse or time capture (40 s pulse width maximum, 120 s total waveform capture) 
of an entire pulse to a csv file using both channels of a single 4225-PMU and the Segment ARB mode. 
In addition to optionally saving the waveform to a file, a time-averaged version is available in the Analyze sheet.  

Since this module uses the Seg Arb mode, it does not allow range-changing or 
Load Line Effect compensation.

Both channels use the same timing values, but allow different voltages for 
both the pulse amplitude and base. To output a DC waveform, set 
V_Ampl = V_Base.

Ch1_parameter is Channel 1 of the specified PMU. Ch2_parameter is Channel 2 
of the specified PMU.

Channel 2 may be swept.  To output a single (non-swept) drain pulse waveform, 
set Ch2_StartV= Ch2_StopV (value for Ch2_StepV does not matter in this case).

Optional SMU available for voltage biasing of a device terminal that does 
not react to the pulse.  For example, do not connect SMU to DUT drain, gate, 
or source of a transistor. Note that the SMU cannot be connected to an RPM, 
or a -233 error ("forcev(): Cannot force when not connected.") will occur.

This data return method in this routine is not compatible with KXCI (using 
the UL mode).

file path = C:\s4200\kiuser\export\wavefrm_capture.csv

~~~~
                 _____________ Ch1_V_Ampl  or Ch2_StartV, Ch2_StopV, Ch2_StepV
                /  PulseTop   \
               /               \ 
              /                 \
             /                   \
  __________/                     \__________Ch1_V_Base or Ch2_V_Base
   DelayTime   RiseT           FallT   BaseTime
~~~~

Inputs
------

PulseTop	
: Pulse Top (see ASCII diagram above) in seconds: 20 ns to 40 s

RiseTime
: Rise time (0 to 100%) of the pulse. Note there is a maximum 
		rise time of 33 ms, which is available only at the largest 
		pulse amplitude:
:		10V Range: -10 to +10 (into 1 M&Omega;)
:		40V Range: -40 to +40 (into 1 M&Omega;)
:		Available settings: 20 ns to 33 ms
:		Note that the longer times are only
		available at larger pulse amplitudes.

FallTime	
: See RiseTime for details.

BaseTime	
: Time at the base voltage after the pulse. Note that this 
		time is not the period.
: Period = DelayTime + BaseTime + 0.5 * RiseTime + 
		0.5 * FallTime + PulseWidth
: Available settings: 20 ns to 40 s

DelayTime	
: Time before pulse, at base voltage.
: Available settings: 20 ns to 40 s

MaxSheetPoints	
: Maximum number of rows in the sheet. This value is for each 
		measurement type, not the total of all measurements per test.
		When the number of data points is greater than MaxSheetPoints, 
		averaging is used to reduce the number of points put
		in the sheet.
: Range: 100 to 32,768

MaxFilePoints
: Maximum number of samples for each measurement to be saved to the file.
: Range: 100 to 1,000,000

Ch1_VRange	
: Voltage Source range for Channel 1 of the PMU. Voltage is 
		the maximum voltage possible into a high impedance DUT.
: Valid: 10, 40

Ch1_IRange
: Fixed current measure range for Channel 1 of the PMU. Valid 
		ranges are specific to each voltage source range and to the 
		4225-RPM (if connected).
: PMU 10V: 0.01, 0.2
: PMU 40V: 100e-6, 0.01, 0.8
: RPM 10V: 100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

Ch1_V_Ampl
: Voltage amplitude of the pulse for channel 1. Amplitude is relative
   to Ch1_V_Base. Valid voltages are specific to 
		the source range and incorporate the effects of Ch1_Res.  
		(Ch1_V_Ampl + Ch1_V_Base) must be l< Ch1_VRange.
: 10V range PMU(or RPM): -20 to +20
: 40V range: -80 to +80

Ch1_V_Base
: Base voltage for Ch1 pulse. This is the voltage level 
		in-between the pulses, also may be called the DC offset.
: 10V range PMU(or RPM): -10 to +10
: 40V range: -40 to +40

Ch2_VRange	
: Voltage Source range for Channel 1 of the PMU. Voltage 
		is the maximum voltage possible into a high impedance DUT.
: Valid: 10, 40

Ch2_IRange
: Fixed current measure range for Channel 2 of the PMU.  
		Valid ranges are specific to each voltage source range 
		and to the 4225-RPM (if connected).
: PMU 10V: 0.01, 0.2
: PMU 40V: 100e-6, 0.01, 0.8
: RPM 10V: 100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

Ch2_StartV	
: Start voltage amplitude for the amplitude sweep on Channel 2.
		(Ch2_StartV + Ch2_V_Base) must be less than Ch2_VRange.
: 10V range PMU(or RPM): -20 to +20
: 40V range: -80 to +80

Ch2_StopV	
: Stop voltage amplitude for the amplitude sweep on Channel 2.
		(Ch2_StopV + Ch2_V_Base) must be less than Ch2_VRange.
: 10V range PMU(or RPM): -20 to +20
: 40V range: -80 to +80	

Ch2_StepV	
: Step voltage size for amplitude sweep on Channel 2.
: 10V range PMU(or RPM): -20 to +20
: 40V range: -80 to +80	

Ch2_V_Base	
: Base voltage for Ch2 pulse. This is the voltage level 
		in-between the pulses, also may be called the DC offset.
: 10V range PMU(or RPM): -10 to +10
: 40V range: -40 to +40	

Ch1_Res		
: Resistance of the device terminal attached to channel 1
		(&Omega;). Set this value to the DUT resistance, if known, 
		to allow the PMU to calculate the correct voltage to output 
		to match the desired voltages given in Ch1_V_Ampl and 
		Ch1_V_Base. Note that resistances < 1e6 will not allow 
		voltage values < VRange to be specified (an error -846 
		will be reported).
: Range: 1 to 1e6
		
Ch2_Res	
: Resistance of the device terminal attached to channel 2, 
		(&Omega;). Set this value to the DUT resistance, if known, 
		to allow the PMU to calculate the correct voltage to output 
		to match the desired voltages given in Ch2_V_Ampl and 
		Ch2_V_Base. Note that resistances < 1e6 will not allow 
		voltage values < VRange to be specified (an error -846 will 
		be reported).
: Range: 1 to 1e6

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
: Note: 10e-9 requires preamplifier and 1 A range only 
			available on high power SMU.

SMU_Icomp	
: (double) SMU current compliance. This value must > 10% of the 
			above current range.

SMU_ID		
: SMU instrument name, such as "SMU1" (without quotes).  
		For no SMU, use "NONE". Note that the SMU cannot be 
		connected to an RPM, or a -233 error ("forcev(): Cannot 
		force when not connected.") will occur.
: Range:  NONE, SMU1, SMU2, up to maximum SMUs in system.

PMU_ID	
: PMU number. PMU in lowest numbered (right-most PMU when viewed 
		from rear of 4200 chassis) is PMU1.

SaveFile	
: Sets whether the .csv file is saved to disk:
: 0: File not saved
: 1: File saved

AppendTimeToFilename
: Adds the file saved test time to the file. Useful when saving
			many waveforms in succession:
: 1: Enabled
: 0: Disabled

Filename
: Name of the file.

TimeStampSize	
: Size for Output arrays.  Ensure that all arrays have the same
size and it must be >= MaxSheetPoints.

Ch2_VmeasSize	
: Size for Output arrays.  Ensure that all arrays have the same
size and it must be >= MaxSheetPoints.

Ch2_ImeasSize	
: Size for Output arrays.  Ensure that all arrays have the same
size and it must be >= MaxSheetPoints.
	
Ch1_VmeasSize
: Size for Output arrays.  Ensure that all arrays have the same
size and it must be >= MaxSheetPoints.

Ch1_ImeasSize
: Size for Output arrays.  Ensure that all arrays have the same
size and it must be >= MaxSheetPoints.

Outputs
-------

TimeStamp	
: (double) Time stamps for waveform measurements

Ch2_Vmeas		
: (double) Measured Voltage on Drain Channel

Ch2_Imeas		
: (double) Measured Currnt on Drain Channel

Ch1_Vmeas		
: (double) Measured Voltage on Gate Channel

Ch1_Imeas		
: (double) Measured Current on Gate Channel


Return values
-------------
			 
Value  | Description
------ | -----------
0      | OK.
-122   | pulse_ranges(): Illegal value for parameter #7. Ensure that current
       | measure range is appropriate for the chosen voltage range.
-233   | Cannot force when not connected. Ensure that specified SMU is not
       | connected through or associated with an RPM. If all SMUs are associated
       | with RPM modules, choose NONE to permit the test to run.
-804   | Usually caused by PMU V source and I measure range setting conflict.
       | See above for valid combinations.
-820   | seg_arb_sequence(): PMU segment start value xxV at index 1 does not match
       | previous segment stop value of yyV. Problem with Segment ARB voltage definition.
       | Review start or stop voltages. Check to see if StartV matches previous StopV.
       | Check to see if any voltages > VRange.
-835   | seg_arb_sequence(): Using the specified sample rate of xxxxx samples/s,
       | the time (yyyy) for sequence 1 is too short for a measurement.
       | This means that there is a segment with a time duration too short to
       | permit any samples to be made with the chosen sample rate of xxxxx samples/s.
       | There must be at least 1 sample per measured segment.
       | Increase the permitted number of samples by increasing the value for MaxSheetPoints,
       | or increase the time duration of all segments with time yyyy.
-846   | seg_arb_sequence(): Maximum Source Voltage Reached: Requested voltage across
       | DUT resistance exceeds maximum voltage available. Ensure that all voltages are
       | < PMU Voltage Range (VRangeCh1 and VRangeCh2). When the DUT Resistance is
       | set to a lower value (< 1 k&Omega;), also check that the voltage is still possible
       | by calculating Imax and Vmax. Imax = V source range/(50 &Omega; + DUT Resistance)
       | Vmax = Imax * DUT Resistance. If Vmax is < SegARB voltage requested Error -846 will occur.
       | Reduce the requested voltage to allow test to run.
-17001 | Wrong card Id. Check PMU and SMU names
-17002 | Failure to assign card Id handle. Check PMU and/or SMU names

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
#include <time.h>

double *dstartv, *dstopv, *gstartv, *gstopv, *measstart, *measstop, *segtime;
long *ssrctrl, *meastypes, *trig;

void AllocateArrays_PMU_Wfm_File(int npts);
void FreeArrays_PMU_Wfm_File(void);
void FillSweepArrays_Wfm(double dstartV, double dstepV, double gbias, double gVlo, double dVlo, int numpts, double riset, double fallt, double pwidth, double baset, double delay);
BOOL LPTIsInCurrentConfiguration(char* hrid);
void GetPathFileExt(char*, char*, char*, char*);

#pragma warning( disable: 4996 )


int PMU_PulseWaveform_FileSave_Example( double PulseTop, double RiseTime, double FallTime, double BaseTime, double DelayTime, long MaxSheetPoints, long MaxFilePoints, double Ch1_VRange, double Ch1_IRange, double Ch1_V_Ampl, double Ch1_V_Base, double Ch2_VRange, double Ch2_IRange, double Ch2_StartV, double Ch2_StopV, double Ch2_StepV, double Ch2_V_Base, double Ch1_Res, double Ch2_Res, double SMU_V, double SMU_Irange, double SMU_Icomp, char *SMU_ID, char *PMU_ID, int SaveFile, int AppendTimeToFilename, char *Filename, double *TimeStamp, int TimeStampSize, double *Ch1_Vmeas, int Ch1_VmeasSize, double *Ch1_Imeas, int Ch1_ImeasSize, double *Ch2_Vmeas, int Ch2_VmeasSize, double *Ch2_Imeas, int Ch2_ImeasSize )
{
/* USRLIB MODULE CODE */
    int status, NumDataPts, PtsPerPulse;
    int verbose = 0;
    int NumSweepPts, TotalPts;
    double t;
    long SeqList[1] = {1};
    double LoopCountList[1] = {1};
    int InstId, SMUId;
    boolean SMUPresent;
    int GateCh = 1;
    int DrainCh = 2;

    long RateFactor;
    double SampleRate;
    double GateBias;
    double *Ch1_Vmeas_Sheet, *Ch1_Imeas_Sheet, *GateT_Sheet;
    double *Ch2_Vmeas_Sheet, *Ch2_Imeas_Sheet, *DrainT_Sheet;
    double *Ch1_Vmeas_File, *Ch1_Imeas_File, *GateT_File;
    double *Ch2_Vmeas_File, *Ch2_Imeas_File, *DrainT_File;
    unsigned long *DrainS_File, *GateS_File;
    double Ch1_Vmeas_Accum, Ch1_Imeas_Accum;
    double Ch2_Vmeas_Accum, Ch2_Imeas_Accum;
    int j, k, l;
    int decimatedSize = MaxSheetPoints;
    int numDecimatedMeans;
    int numLeftoverPoints;
    char vcol[32], icol[32];
    char vcolg[32], icolg[32];
    char No_SMU[10] = "NONE";

    //Initialize variables
//    verbose = 1;        //prints out status messages to Message Console (type msgcon at command prompt)
    SampleRate = 200e6;
    SMUId = 0;
    SMUPresent = FALSE;

    //Allocate arrays to hold the measurements for the Clarius Sheet
    Ch1_Vmeas_Sheet = (double *)calloc(Ch1_VmeasSize, sizeof(double));
    Ch1_Imeas_Sheet = (double *)calloc(Ch1_ImeasSize, sizeof(double));
    GateT_Sheet = (double *)calloc(TimeStampSize, sizeof(double));
    Ch2_Vmeas_Sheet = (double *)calloc(Ch2_VmeasSize, sizeof(double));
    Ch2_Imeas_Sheet = (double *)calloc(Ch2_ImeasSize, sizeof(double));
    DrainT_Sheet = (double *)calloc(TimeStampSize, sizeof(double));

    //Check: is requested PMU card in the chassis?
    if ( !LPTIsInCurrentConfiguration(PMU_ID) )
    {
        printf("Instrument %s is not in system configuration", PMU_ID);
        return -1;
    }

    //Convert PMU card string into identifying instrument card number        
    getinstid(PMU_ID, &InstId);
    if(-1 == InstId)
        return -2;

    //Check: is a SMU ID set (SMUx or NONE)?  If a SMU string, is in the the chassis?
    if ( _stricmp(SMU_ID, No_SMU) )
    {
        if ( verbose )
            printf("PMU_PulseWaveform_FileSave: SMU string present, %s", SMU_ID);

        if ( !LPTIsInCurrentConfiguration(SMU_ID) )
        {
            printf("PMU_PulseWaveform_FileSave: Instrument %s is not in system configuration", PMU_ID);
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
            printf("PMU_PulseWaveform_FileSave: No SMU specified, SMU_ID = %s", SMU_ID);
    }


    //Calculate number of sweep steps
    NumSweepPts = (int)((Ch2_StopV - Ch2_StartV)/Ch2_StepV + 1E-7 + 1);        //Add small amount to account for rounding
    TotalPts = NumSweepPts;

    if ( verbose )
        printf("TotalPts= %d, NumSweepPts= %d", TotalPts, NumSweepPts);

    //Allocate arrays for the measurement data
    AllocateArrays_PMU_Wfm_File(NumSweepPts * 4 + 1);

    if ( verbose )
        printf("Before pg2_init");

    //Ensure that 4225-RPM (if attached) is in the pulse mode
    status = rpm_config(InstId, GateCh, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
    {
        return status ;
    }

    status = rpm_config(InstId, DrainCh, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
    {
        return status ;
    }

    //Put PMU into Segment Arb mode
    status = pg2_init(InstId, PULSE_MODE_SARB);
    if ( status )
      return status;

    //Check for SMU in test, then configure
    if ( SMUPresent )
    {
        if ( verbose )
            printf("PMU_Pulse_Wfm_File: SMU present, V= %g, Irange= %g", SMU_V, SMU_Irange);

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

    //Set PMU to return actual values when measurement overflow occurs
    status = setmode(InstId, KI_LIM_MODE, KI_VALUE);
    if ( status )
      return status;

    
    if ( verbose )
        printf("Before Gate pulse_load");
    //Set test device resistance
    status = pulse_load(InstId, GateCh, Ch1_Res);
    if ( status )
      return status;

    if ( verbose )
        printf("Before Drain pulse_load");
    status = pulse_load(InstId, DrainCh, Ch2_Res);
    if ( status )
      return status;

    if ( verbose )
        printf("Before Gate pulse_ranges");

    //Set PMU source and measure ranges
    status = pulse_ranges(InstId, GateCh, Ch1_VRange, PULSE_MEAS_FIXED, Ch1_VRange, PULSE_MEAS_FIXED, Ch1_IRange);
    if ( status )
      return status;

    if ( verbose )
        printf("Before Drain pulse_ranges");

    status = pulse_ranges(InstId, DrainCh, Ch2_VRange, PULSE_MEAS_FIXED, Ch2_VRange, PULSE_MEAS_FIXED, Ch2_IRange);
    if ( status )
      return status;

    if ( verbose )
        printf("Before Gate pulse_burst_count");

    //Set number of pulses (Seg-Arb waveforms) to output
    status = pulse_burst_count(InstId, GateCh, 1);
    if ( status )
      return status;

    status = pulse_burst_count(InstId, DrainCh, 1);
    if ( status )
      return status;

    //Enable output
    status = pulse_output(InstId, GateCh, 1);
    if ( status )
      return status;

    status = pulse_output(InstId, DrainCh, 1);
    if ( status )
      return status;

    //Calculate gate bias value
    GateBias = Ch1_V_Ampl + Ch1_V_Base;

    //Calculate number of samples in 1 waveform
    PtsPerPulse = (int)((PulseTop + BaseTime + RiseTime + FallTime) / (1/SampleRate) + 0.5);

    //Calculate total number of samples, accounting for the sweep steps
    NumDataPts = NumSweepPts * PtsPerPulse + (int)(DelayTime / (1/SampleRate) + 0.5);

    if (verbose)
        printf("PMU_PulseWfm:  PtsPerPulse= %d, NumDataPts= %d", PtsPerPulse, NumDataPts);

    //Determine sample rate to get up to the specified MaxFilePoints (per A/D)
    if (NumDataPts > MaxFilePoints)
    {
        RateFactor = (int)((NumDataPts / MaxFilePoints) + 1);      
        SampleRate = (SampleRate / RateFactor);
        if ( verbose )
            printf("PMU_PulseWfm:  NumDataPts (%d) > MaxFilePts (%d), Ratefctr= %d, SampleRate= %g", NumDataPts, MaxFilePoints, RateFactor, SampleRate);
    }

    //Set PMU sample rate
    status = pulse_sample_rate(InstId, (long)SampleRate);
    if ( status )
      return status;

    if ( verbose )
        printf("PMU_PulseWfm:  Just programmed SampleRate to %d", (long)SampleRate);

    //Recalculate number of points, after determining actual Sample Rate
    PtsPerPulse = (int)((PulseTop + BaseTime + RiseTime + FallTime) / (1/SampleRate) + 0.5);
    NumDataPts = NumSweepPts * PtsPerPulse + (int)(DelayTime / (1/SampleRate) + 0.5);

    if (verbose)
        printf("PMU_PulseWfm:  After SampleRate set, PtsPerPulse= %d, NumDataPts= %d", PtsPerPulse, NumDataPts);

    //Is time-based decimation required for the sheet data?
    if ( NumDataPts > decimatedSize )
    {
        if ( verbose )
            printf("PMU_PulseWfm: decimatedSize= %d", decimatedSize);
        numDecimatedMeans = NumDataPts/decimatedSize;
        numLeftoverPoints = NumDataPts - (numDecimatedMeans * decimatedSize);
        //If there are leftover points (that is, if NumDataPts/decimatedSize is not an integer)
        //then increment the number of points in each mean (that is, increment numDecimatedMeans)
        //then recalculate the decimated size.  Note that any leftover points after this are not 
        //carried to the Clarius sheet
        if (numLeftoverPoints > 0)
        {
            numDecimatedMeans++;
            decimatedSize = NumDataPts / numDecimatedMeans;
        }
    }
    else    //Decimation not required
    {
        numDecimatedMeans = 1;
        decimatedSize = NumDataPts;
        numLeftoverPoints = 0;
    }

    if ( verbose )
        printf("PMU_PulseWfm: NumDataPts= %d, decSize= %d, numDecMeans= %d, leftover= %d, actualLeftover= %d", NumDataPts, decimatedSize, numDecimatedMeans, numLeftoverPoints, NumDataPts - (decimatedSize * numDecimatedMeans));

    //Allocate arrays to hold the measurements fetched from the PMU
    Ch1_Vmeas_File = (double *)calloc(NumDataPts+1, sizeof(double));
    Ch1_Imeas_File = (double *)calloc(NumDataPts+1, sizeof(double));
    GateT_File = (double *)calloc(NumDataPts+1, sizeof(double));
    GateS_File = (unsigned long *)calloc(NumDataPts+1, sizeof(int));
    Ch2_Vmeas_File = (double *)calloc(NumDataPts+1, sizeof(double));
    Ch2_Imeas_File = (double *)calloc(NumDataPts+1, sizeof(double));
    DrainT_File = (double *)calloc(NumDataPts+1, sizeof(double));
    DrainS_File = (unsigned long *)calloc(NumDataPts+1, sizeof(int));

    if ( verbose )
        printf("PMU_PulseWfm: NumSweepPts= %d, PtsPerPulse= %d", NumSweepPts, PtsPerPulse);
   
    //Put appropriate values into the segment arb arrays for the desired pulse shape
    FillSweepArrays_Wfm(Ch2_StartV, Ch2_StepV, GateBias, Ch1_V_Base, Ch2_V_Base, NumSweepPts, RiseTime, FallTime, PulseTop, BaseTime, DelayTime);

    if ( verbose )
        printf("PMU_PulseWfm: About to program sequences");

    //Set up sequence (pulse) for Gate
    status = seg_arb_sequence(InstId,  GateCh, 1,  NumSweepPts*4+1, gstartv, gstopv, segtime, trig, ssrctrl, meastypes, measstart, measstop);
    if ( status )
       return status;
        
    status = seg_arb_sequence(InstId, DrainCh, 1, NumSweepPts*4+1, dstartv, dstopv, segtime, trig, ssrctrl, meastypes, measstart, measstop);
    if ( status )
       return status;

    //Configure Seg-Arb waveform
    status = seg_arb_waveform(InstId, GateCh, 1, SeqList, LoopCountList);
    if ( status )
       return status;

    status = seg_arb_waveform(InstId, DrainCh, 1, SeqList, LoopCountList);
    if ( status )
       return status;

    if ( verbose )
        printf("PMU_PulseWfm: run pulse_exec");

    //Run the test
    status = pulse_exec(PULSE_MODE_SIMPLE);
    if ( status )
       return status;

    //Wait for test to finish
    while ( pulse_exec_status(&t) == 1 )
    {
        Sleep(100);
    }

    if ( verbose )
        printf("PMU_PulseWfm: begin Gate pulse_fetch, NumDataPts = %d", NumDataPts);

    //Retrieve measurements
    status = pulse_fetch(InstId, GateCh, 0, NumDataPts, Ch1_Vmeas_File, Ch1_Imeas_File, GateT_File, GateS_File);
    if ( status )
       return status;

    if ( verbose )
        printf("PMU_PulseWfm: begin Drain pulse_fetch, NumDataPts = %d", NumDataPts);

    status = pulse_fetch(InstId, DrainCh, 0, NumDataPts, Ch2_Vmeas_File, Ch2_Imeas_File, DrainT_File, DrainS_File);
    if ( status )
       return status;

    if ( verbose )
        printf("PMU_PulseWfm: decimatedSize= %d, numDecimatedMeans= %d", decimatedSize, numDecimatedMeans);
    
    for ( k=0; k<decimatedSize; k++ )
    {
        Ch1_Vmeas_Accum = 0.0;
        Ch1_Imeas_Accum = 0.0;
        Ch2_Vmeas_Accum = 0.0;
        Ch2_Imeas_Accum = 0.0;

        for ( l=0; l<numDecimatedMeans; l++ )
        {
            Ch1_Vmeas_Accum += Ch1_Vmeas_File[k*numDecimatedMeans + l];
            Ch1_Imeas_Accum += Ch1_Imeas_File[k*numDecimatedMeans + l];
            Ch2_Vmeas_Accum += Ch2_Vmeas_File[k*numDecimatedMeans + l];
            Ch2_Imeas_Accum += Ch2_Imeas_File[k*numDecimatedMeans + l];
        }
    
        Ch1_Vmeas_Sheet[k] = Ch1_Vmeas_Accum/numDecimatedMeans;
        Ch1_Imeas_Sheet[k] = Ch1_Imeas_Accum/numDecimatedMeans;
        GateT_Sheet[k] = GateT_File[k*numDecimatedMeans];
        Ch2_Vmeas_Sheet[k] = Ch2_Vmeas_Accum/numDecimatedMeans;
        Ch2_Imeas_Sheet[k] = Ch2_Imeas_Accum/numDecimatedMeans;
        DrainT_Sheet[k] = DrainT_File[k*numDecimatedMeans];
    }
    
    sprintf(vcol, "Ch2_Vmeas");
    sprintf(icol, "Ch2_Imeas");

    if ( verbose )
        printf("PMU_PulseWfm: Posting Drain Data");

    //Post data to Clarius sheet
    PostDataDoubleBuffer("TimeStamp", DrainT_Sheet, decimatedSize);
    PostDataDoubleBuffer(vcol, Ch2_Vmeas_Sheet, decimatedSize);
    PostDataDoubleBuffer(icol, Ch2_Imeas_Sheet, decimatedSize);
    
    sprintf(vcolg, "Ch1_Vmeas");
    sprintf(icolg, "Ch1_Imeas");

    if ( verbose )
        printf("PMU_PulseWfm: Posting Gate Data");

    PostDataDoubleBuffer(vcolg, Ch1_Vmeas_Sheet, decimatedSize);
    PostDataDoubleBuffer(icolg, Ch1_Imeas_Sheet, decimatedSize);

    //Save all data to file, no decimation
    if ( SaveFile )
    {
        FILE *f;
        char fn[128];
        char errMsg[100];
        char tmpFilename[256];
        char date[80] = "\0";
        char path[256] = "\0";
        char tmppath[256] = "\0";
        char name[256] = "\0";
        char ext[256] = "\0";

        strcpy(tmpFilename, Filename);

        GetPathFileExt(tmpFilename, path, name, ext);
        if ( verbose )
            printf("PMU_PulseWfm: path= %s, name= %s, ext= %s", path, name, ext);

        if ( AppendTimeToFilename )
        {
            time_t rawtime;
            struct tm *timeinfo;

            time(&rawtime);
            timeinfo = localtime(&rawtime);

            strftime(date, 80, "_%Y%m%d_%H%M%S", timeinfo);
        }

        // check for path...
        if ( !strlen(path) )
        {
            strcpy(path, "C:\\S4200\\kiuser\\export");
        }
        else
        {
            if ( !strstr(path, "\\\\") )
            {
                int i=0;
                char *p = path;
                // need to make "\" --> "\\"
                while ( *p != '\0' )
                {
                    tmppath[i++] = *p++;
                    if ( *p == '\\' )
                        tmppath[i++] = '\\';
                }
                
                strcpy(path, tmppath);
            }
        }

        // check for name...
        if ( !strlen(name) )
            strcpy(name, "wavefrm_capture");
            
        // check for extension...
        if ( !strlen(ext) )
            strcpy(ext, "csv");

        sprintf(fn, "%s\\%s%s.%s", path, name, date, ext);
        f = fopen(fn, "w");
        if ( f != NULL )
        {
            if ( verbose )
                printf("PMU_PulseWfm: Posting to file:  %s", fn);
            fprintf(f, "Time, Ch1_Vmeas, Ch1_Imeas, GateS, Ch2_Vmeas, Ch2_Imeas, DrainS\n");
            for ( j= 0; j<NumDataPts; j++ )
            {
               fprintf(f, "%g, %g, %g, %08x, %g, %g, %08x\n", DrainT_File[j], Ch1_Vmeas_File[j], Ch1_Imeas_File[j], GateS_File[j], Ch2_Vmeas_File[j], Ch2_Imeas_File[j], DrainS_File[j]);
            }

            fclose(f);

            if ( verbose )
                printf("PMU_PulseWfm: Done Posting to file");
        }
        else
        {
            sprintf(errMsg, "Could not open file for writing!  (%s)", fn);
            logMsg(MF_Error, ERROR_STRING, errMsg); 
        }
    }

    if ( SMUPresent )
    {
        if ( verbose )
            printf("PMU_PulseWfm: SMU present, setting voltage = 0");

        status = forcev(SMUId, 0);
        if ( status )
            return status ;
    }

    if ( verbose )
        printf("PMU_PulseWfm: before FreeBird");
    FreeArrays_PMU_Wfm_File();
    if ( verbose )
        printf("PMU_PulseWfm: after FreeBird");

    if ( verbose )
        printf("PMU_PulseWfm: before frees");
    free(Ch1_Vmeas_Sheet);
    free(Ch1_Imeas_Sheet);
    free(GateT_Sheet);
    free(Ch2_Vmeas_Sheet);
    free(Ch2_Imeas_Sheet);
    free(DrainT_Sheet);
    free(Ch1_Vmeas_File);
    free(Ch1_Imeas_File);
    free(GateT_File);
    free(GateS_File);
    free(Ch2_Vmeas_File);
    free(Ch2_Imeas_File);
    free(DrainT_File);
    free(DrainS_File);

    if ( verbose )
        printf("PMU_PulseWfm: after all frees");

    return OK;
}

void AllocateArrays_PMU_Wfm_File(int npts)
{
    dstartv = (double *)calloc(npts, sizeof(double));
    dstopv  = (double *)calloc(npts, sizeof(double));
    gstartv  = (double *)calloc(npts, sizeof(double));
    gstopv  = (double *)calloc(npts, sizeof(double));
    measstart  = (double *)calloc(npts, sizeof(double));
    measstop  = (double *)calloc(npts, sizeof(double));
    segtime  = (double *)calloc(npts, sizeof(double));
    
    trig  = (long *)calloc(npts, sizeof(long));
    ssrctrl  = (long *)calloc(npts, sizeof(long));
    meastypes  = (long *)calloc(npts, sizeof(long));
}

void FreeArrays_PMU_Wfm_File(void)
{
    free(dstartv);
    free(dstopv);
    free(gstartv);
    free(gstopv);
    free(measstart);
    free(measstop);
    free(segtime);
    
    free(trig);
    free(ssrctrl);
    free(meastypes);
}

void FillSweepArrays_Wfm(double dstartV, double dstepV, double gbias, double gVlo, double dVlo, int numpts, double riset, double fallt, double ptop, double baset, double delay)
{
    int TotalPts, i;
    double sweepval;

    TotalPts = numpts * 4 + 1;
    sweepval = dstartV;

    for(i=0; i<TotalPts; i++)
        ssrctrl[i] = 1;

    i=0;
//    dstartv[i] = gstartv[i] = 0;
//    dstopv[i] = dVlo;
//    gstopv[i] = gVlo;
//    segtime[i] = 100e-9;
//    measstart[i] = 0;
//    measstop[i] = 100e-9;
//    trig[i] = 1;
//    meastypes[i] = PULSE_MEAS_WFM_PER;

//    i=1;
    dstartv[i] = dVlo;
    gstartv[i] = gVlo;
    dstopv[i] = dVlo;
    gstopv[i] = gVlo;
    segtime[i] = delay;
    measstart[i] = 0;
    measstop[i] = delay;
    trig[i] = 1;
    meastypes[i] = PULSE_MEAS_WFM_PER;

    for(i=1; i<TotalPts-2; i+=4)
    {
        // rise time segment
        dstartv[i] = dVlo;
        gstartv[i] = gVlo;
        dstopv[i] = sweepval + dVlo;
        gstopv[i] = gbias + gVlo;
        segtime[i] = riset;
        measstart[i] = 0;
        measstop[i] = riset;
        trig[i] = 0;
        meastypes[i] = PULSE_MEAS_WFM_PER;

        // pulse top segment
        dstartv[i+1] = sweepval + dVlo;
        dstopv[i+1] = sweepval  + dVlo;
        gstartv[i+1] = gbias + gVlo;
        gstopv[i+1] = gbias + gVlo;
        segtime[i+1] = ptop;
        measstart[i+1] = 0;
        measstop[i+1] = ptop;
        trig[i+1] = 0;
        meastypes[i+1] = PULSE_MEAS_WFM_PER;

        // fall time segment
        dstartv[i+2] = sweepval  + dVlo;
        dstopv[i+2] = dVlo;
        gstartv[i+2] = gbias + gVlo;
        gstopv[i+2] = gVlo;
        segtime[i+2] = fallt;
        measstart[i+2] = 0;
        measstop[i+2] = fallt;
        trig[i+2] = 0;
        meastypes[i+2] = PULSE_MEAS_WFM_PER;

        // off time segment
        dstartv[i+3] = dVlo;
        dstopv[i+3] = dVlo;
        gstartv[i+3] = gVlo;
        gstopv[i+3] = gVlo;
        measstart[i+3] = 0;
        segtime[i+3] = baset;
        measstop[i+3] = baset;
        trig[i+3] = 0;
        meastypes[i+3] = PULSE_MEAS_WFM_PER;

        sweepval += dstepV;
    }

//   i = TotalPts-1;
//   dstartv[i] = dVlo;
//   dstopv[i] = 0;
//   gstartv[i] = gVlo;
//   gstopv[i] = 0;
//   measstart[i] = 0;
//   segtime[i] = 100e-9;
//   measstop[i] = 100e-9;
//   trig[i] = 0;
//   meastypes[i] = PULSE_MEAS_WFM_PER;

/* USRLIB MODULE END  */
} 		/* End PMU_PulseWaveform_FileSave_Example.c */

