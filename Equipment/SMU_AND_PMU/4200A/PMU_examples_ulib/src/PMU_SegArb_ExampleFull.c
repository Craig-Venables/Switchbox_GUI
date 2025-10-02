/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_SegArb_ExampleFull
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 65
	ARGUMENTS:
		VRangeCh1,	double,	Input,	10,	5,	40
		IRangeCh1,	double,	Input,	.01,	100e-9,	.8
		VRangeCh2,	double,	Input,	10,	5,	40
		IRangeCh2,	double,	Input,	.01,	100e-9,	.8
		AcqType,	int,	Input,	0,	0,	0
		DUTResCh1,	double,	Input,	1E6,	1,	1E6
		DUTResCh2,	double,	Input,	1E6,	1,	1E6
		MaxSheetPoints,	int,	Input,	10000,	12,	30000
		SegTime,	D_ARRAY_T,	Input,	,	,	
		SegTime_size,	int,	Input,	20,	3,	2048
		StartVCh1,	D_ARRAY_T,	Input,	,	,	
		StartVCh1_size,	int,	Input,	20,	3,	2048
		StopVCh1,	D_ARRAY_T,	Input,	,	,	
		StopVCh1_size,	int,	Input,	20,	3,	2048
		StartVCh2,	D_ARRAY_T,	Input,	,	,	
		StartVCh2_size,	int,	Input,	20,	3,	2048
		StopVCh2,	D_ARRAY_T,	Input,	,	,	
		StopVCh2_size,	int,	Input,	20,	3,	2048
		MeasEnabled,	I_ARRAY_T,	Input,	,	,	
		MeasEnabled_size,	int,	Input,	20,	3,	2048
		SSRCtrlCh1,	I_ARRAY_T,	Input,	,	,	
		SSRCtrlCh1_size,	int,	Input,	20,	3,	2048
		SSRCtrlCh2,	I_ARRAY_T,	Input,	,	,	
		SSRCtrlCh2_size,	int,	Input,	20,	3,	2048
		SegTrigOut,	I_ARRAY_T,	Input,	,	,	
		SegTrigOut_size,	int,	Input,	20,	3,	2048
		SegMeasType,	I_ARRAY_T,	Input,	,	,	
		SegMeasType_size,	int,	Input,	20,	3,	2048
		SegMeasStart,	D_ARRAY_T,	Input,	,	,	
		SegMeasStart_size,	int,	Input,	20,	3,	2048
		SegMeasStop,	D_ARRAY_T,	Input,	,	,	
		SegMeasStop_size,	int,	Input,	20,	3,	2048
		SeqList,	I_ARRAY_T,	Input,	,	,	
		SeqList_size,	int,	Input,	20,	1,	512
		SeqStartSeg,	I_ARRAY_T,	Input,	,	,	
		SeqStartSeg_size,	int,	Input,	20,	1,	512
		SeqStopSeg,	I_ARRAY_T,	Input,	,	,	
		SeqStopSeg_size,	int,	Input,	20,	1,	512
		SeqListCh1,	I_ARRAY_T,	Input,	,	,	
		SeqListCh1_size,	int,	Input,	20,	1,	512
		SeqListCh2,	I_ARRAY_T,	Input,	,	,	
		SeqListCh2_size,	int,	Input,	20,	1,	512
		SeqLoopsCh1,	D_ARRAY_T,	Input,	,	,	
		SeqLoopsCh1_size,	int,	Input,	,	,	
		SeqLoopsCh2,	D_ARRAY_T,	Input,	,	,	
		SeqLoopsCh2_size,	int,	Input,	,	,	
		SMU_V,	double,	Input,	0,	-210,	+210
		SMU_Irange,	double,	Input,	.01,	10e-9,	1
		SMU_Icomp,	double,	Input,	.01,	0,	1
		SMU_ID,	char *,	Input,	"NONE",	,	
		PMU_ID,	char *,	Input,	"PMU1",	,	
		VMeasCh1,	D_ARRAY_T,	Output,	,	,	
		VMeasCh1_size,	int,	Input,	10000,	100,	30000
		IMeasCh1,	D_ARRAY_T,	Output,	,	,	
		IMeasCh1_size,	int,	Input,	10000,	100,	30000
		VMeasCh2,	D_ARRAY_T,	Output,	,	,	
		VMeasCh2_size,	int,	Input,	10000,	12,	30000
		IMeasCh2,	D_ARRAY_T,	Output,	,	,	
		IMeasCh2_size,	int,	Input,	10000,	12,	30000
		TimeOutput,	D_ARRAY_T,	Output,	,	,	
		TimeOutput_size,	int,	Input,	10000,	12,	30000
		StatusCh1,	I_ARRAY_T,	Output,	,	,	
		StatusCh1_size,	int,	Input,	10000,	12,	30000
		StatusCh2,	I_ARRAY_T,	Output,	,	,	
		StatusCh2_size,	int,	Input,	10000,	12,	30000
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_SegArbExF(int NumberofSegments);
void FreeArrays_SegArbExF();

unsigned long *PulseMeasType;

#pragma warning( disable: 4996 )

	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: PMU_SegArb_ExampleFull
==============================

Description
-----------
This module configures multi-sequence, multi-segment waveform generation 
(Segment ARB) on 2 channels using a single 4225-PMU and measures and returns 
either waveform (V and I vs time) or spot mean data for each segment that has 
measurement enabled. It also provides a voltage bias by controlling one 4200 
SMU (SMU must not be connected to a 4225-RPM, or a -233 error will occur and 
the test will not run).

This routine is similar to PMU_SegArbExampleB, but this routine adds multiple 
Segment ARB sequences with 3-2048 segments. Each sequence can be looped to make 
a more complicated Segment Arb Waveform. 

Measurement type is either waveform and/or spot mean for the entire test. When 
using waveform measure type, control the number of samples by the MaxSheetPoints 
parameter.

Parameters that a common to both channels:

* Number of segments 
* Segment timing 
* Trigger control 
* Measurement Type
* Measurement Window (measure start and stop within a segment)

Per Channel parameters:

* Voltages
* Source range
* Measure range
* Solid-state relay control. 

This is a two-channel test and each channel must match the other for overall 
timing. This means that the sequence 1 for Channel 1 must have the same number of 
segments and timine as Channel 2. This is also true for each sequence in the test.

Optional SMU available for voltage biasing of a device terminal that does 
not react to the pulse. For example, do not connect SMU to DUT drain, gate, 
or source of a transistor. Note that the SMU cannot be connected to an RPM, 
or a -233 error ("forcev(): Cannot force when not connected.") will occur.

This routine is not compatible with KXCI (UL mode).

This routine uses a different method to get the data from the PMU card into the
Clarius Analyze sheet: pulse_measrt. pulse_measrt() command allows the data to go directly 
from the card to the Analyze sheet, without the need to pull the data into the UTM 
before re-sending to the sheet. This simplifies the UTM code and reduces the 
time required to get lots of data from the card to the sheet, which is most 
beneficial when retrieving PMU waveform data.  The pulse_measrt() command is 
not compatible with KXCI.

How to use
----------
Set appropriate values to all input parameters(as described in the below
section).

Both channels must have valid entries for all the parameters.

All input arrays must have the same size.

Start voltage values must match the stop voltage of the previous segment.

Output array size must be >= MaxSheetPoints

When a channel has a 4225-RPM connection and is set to a 4225-RPM I 
measure range, load line effect compensation is enabled for that channel.
When using a PMU I measure range, load line effect compensation (LLEC) 
is not available.

The Segment ARB mode does not provide current, voltage or power thresholds.

If a test configuration will exceed the MaxSheetPoints or MaxSamplesPerAtoD, 
the sample rate for the card will be reduced to fit the results within the 
MaxSheetPoints. This condition usually occurs for the waveform measurement type.

This example test supports internal triggering only (triggering inside 4200 
chassis); no external trigger input is available.  This example does support
trigger output via the SegTrigOut array (see description below).

Inputs
------

VRangeCh1	
: Voltage range for Ch 1.
: Valid ranges: 10, 40
: Note that maximum voltage for a range is available only with 
		a high impedance DUT (roughly 100 k&Omega; and higher).

IRangeCh1	
: Current measure range for Ch 1. Valid ranges: 
: PMU 10V:  0.01, 0.2
: PMU 20V:  100e-6, 0.01, 0.8
: RPM 10V:  100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

VRangeCh2	
: Voltage range for Ch 2.
: Valid ranges: 10, 40
: Note that maximum voltage for a range is available only 
		with a high impedance DUT (roughly 100 k&Omega; and higher).

IRangeCh2	
: Current measure range for Ch 2. Valid ranges: 
: PMU 10V:  0.01, 0.2
: PMU 20V:  100e-6, 0.01, 0.8
: RPM: 100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

AcqType	
: This parameter must be set to 0.

DUTResCh1	
: Resistance of DUT connected to Ch 1 (&Omega;). Setting this value 
		to represent the actual DUT impedance will greatly reduce the
		difference between the programmed voltage and the voltage at 
		the DUT due to load line effects. This parameter is not 
		meaningful when using a 4225-RPM current measure range.
: Range: 1 to 1e6 &Omega;

DUTResCh2	
: Resistance of DUT connected to Ch 2 (&Omega;). Setting this value 
		to represent the actual DUT impedance will greatly reduce the
		difference between the programmed voltage and the voltage at 
		the DUT due to load line effects. This parameter is not 
		meaningful when using a 4225-RPM current measure range.
: Range: 1 to 1e6 &Omega;

MaxSheetPoints	
: Maximum number of samples, or rows, of data to return to the 
		data sheet.
: Valid values: 12 to 30000

SegTime		
: Time for each segment
: Valid values:  20e-9 to 40 s in 10 ns steps

StartVCh1	
: Array of seg-arb start voltage values for channel 1. Note that
		the start voltage must match the stop voltage of the previous 
		segment.

StopVCh1	
: Array of seg-arb stop voltage values for channel 1.

StartVCh2	
: Array of seg-arb start voltage values for channel 2. Note that
		the start voltage must match the stop voltage of the previous 
		segment.

StopVCh2	
: Array of seg-arb stop voltage values for channel 2.

MeasEnabled	
: Array of values for enabling measurement for each segment on 
		both channels. See MeasType parameter which sets whether
		spot mean or sample measurements are made:
: 0: No Measurement on segment
: 1: Measure this segment

SSRCtrlCh1	
: Array of seg-arb SSR output relay control values for channel 1:
: 1: Close
: 2: Open (means no pulse output for that segment)

SSRCtrlCh2
: Array of seg-arb SSR output relay control values for channel 2:
: 1: Close
: 2: Open (means no pulse output for that segment)

SegTrigOut	
: Array of trigger values (1 or 0) to output from the PMU trigger 
		out connector. This array must have the same number of entries 
		as all other Segment Arb arrays and the first value in SegTrigOut = 1, 
		otherwise the test will not output the waveforms.
: Range:  0 or 1

SegMeasType
: Array of measure types

SegMeasStart
: Array of measure starts

SegMeasStop
: Array of measure stops

SeqList  	
: Array of defined segment sequences.

SeqList_size   	
: Number of defined sequences.

SeqStartSeg  	
: Array of starting segments per each sequence. Defines the 
		first segment of the sequence in array of seqments.

SeqStartSeg_size   
: Number of defined sequences. Must be equal to SeqList_size.

SeqStopSeg   	
: Array of the last segments per each sequence. Defines the 
		last segment of the sequence in array of seqments.

SeqStopSeg_size 	
: Number of defined sequences. Must be equal to SeqList_size.

SeqListCh1   
: Array of sequences selected for Ch1 from SeqList. Same sequence 
		from SeqList can appear more than once in this list.

SeqListCh1_size   
: Number of sequences selected for Ch1 from SeqList.

SeqListCh2   	
: Array of sequences selected for Ch2 from SeqList. Same sequence 
		from SeqList can appear more than once in this list.

SeqListCh2_size 	
: Number of sequences selected for Ch2 from SeqList. Must 
			be equal to SeqListCh1_size.

SeqLoopsCh1   
: Array of loop counts for sequences selected for Ch1 from SeqList.

SeqLoopsCh1_size   
: Number of loops for sequences selected for Ch1 from SeqList.
        Must be equal to SeqListCh1_size.

SeqLoopsCh2   
: Array of loop counts for sequences selected for Ch2 from SeqList.

		SeqLoopsCh1_size,	int,	Input,	,	,	

SeqLoopsCh2_size   
: Number of loops for sequences selected for Ch2 from SeqList.
        Must be equal to SeqListCh1_size.

SMU_V		
: (double) SMU voltage for biasing a non-pulsed DUT 
		terminal.  For 	example, do not connect SMU to a transistor 
		source terminal when pulsing gate and/or drain.
: Range:  -210 to +210 V

SMU_Irange		
: (double) SMU current range.
: Ranges: 10e-9, 100e-9, 1e-6, 10e-6, 100e-6, 1e-3,
				10e-3, 100e-3, 1
: Note: 10e-9 requires Preamp and 1A range only 
			available on high power SMU.

SMU_Icomp		
: (double) SMU current compliance. This value must > 10% 
			of the above current range.

SMU_ID	
: SMU instrument name, such as "SMU1" (without quotes).  For no
			SMU, use "NONE". Note that the SMU cannot be connected
			to an RPM, or a -233 error ("forcev(): Cannot force 
			when not connected.") will occur.
: Range:  NONE, SMU1, SMU2, up to maximum SMUs in system.

PMU_ID		
: PMU number. PMU in lowest numbered (right-most PMU when viewed 
		from rear of 4200 chassis) is PMU1.

Outputs
-------
VMeasCh1
: (double) Measured Voltage on Channel 1

IMeasCh1
: (double) Measured Current on Channel 1

VMeasCh2
: (double) Measured Voltage on Channel 2

IMeasCh2	
: (double) Measured Current on Channel 2

TimeOutput	
: (double) Time values for each sample

StatusCh1	
: This argument is no longer supported. No data will be returned.

StatusCh2	
: This argument is no longer supported. No data will be returned.

Return values
-------------
			 
Value  | Description
------ | -----------
0      | OK.
-122   | Illegal value for parameter.
	   | example: pulse_ranges(): Illegal value for parameter #7. Ensure that 
       | current measure range is appropriate for the chosen voltage range.
-233   | Cannot force when not connected. Ensure that specified SMU is not 
       | connected through or associated with an RPM. If all SMUs are associated 
       | with RPM modules, choose NONE to permit the test to run.
-804   | Usually caused by PMU V source and I measure range setting conflict.  
       | See above for valid combinations.
-820   | seg_arb_sequence(): PMU segment start value xxV at index 1 does not
       | match previous segment stop value of yyV. Problem with Segment ARB 
       | voltage definition. Review start or stop voltages. Check to see if 
       | StartV matches previous StopV. Check to see if any voltages > VRange.
-835   | seg_arb_sequence(): Using the specified sample rate of xxxxx samples/s, 
       | the time (yyyy) for sequence 1 is too short for a measurement. This means
       | that there is a segment with a time duration too short to permit any
       | samples to be made with the chosen sample rate of xxxxx samples/s. 
       | There must be at least 1 sample per measured segment. Increase the 
       | permitted number of samples by increasing the value for MaxSheetPoints, 
       | or increase the time duration of all segments with time yyyy.
-846   | seg_arb_sequence(): Maximum Source Voltage Reached: Requested voltage 
       | across DUT resistance exceeds maximum voltage available. Ensure that all 
       | voltages are < PMU Voltage Range (VRangeCh1 and VRangeCh2). When the 
       | DUT Resistance is set to a lower value (< 1 k&Omega;), also check that
       | the voltage is still possible by calculating Imax and Vmax.
       | Imax = V source range/(50 &Omega; + DUT Resistance)
       | Vmax = Imax * DUT Resistance
       | If Vmax is < SegARB voltage requested Error -846 will occur. Reduce
       | the requested voltage to allow test to run.
-17001 | Wrong card Id. Check PMU and SMU names.
-17002 | Failure to assign card ID handle. Check PMU and/or SMU names.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_SegArbExF(int NumberofSegments);
void FreeArrays_SegArbExF();

unsigned long *PulseMeasType;

#pragma warning( disable: 4996 )


int PMU_SegArb_ExampleFull( double VRangeCh1, double IRangeCh1, double VRangeCh2, double IRangeCh2, int AcqType, double DUTResCh1, double DUTResCh2, int MaxSheetPoints, double *SegTime, int SegTime_size, double *StartVCh1, int StartVCh1_size, double *StopVCh1, int StopVCh1_size, double *StartVCh2, int StartVCh2_size, double *StopVCh2, int StopVCh2_size, int *MeasEnabled, int MeasEnabled_size, int *SSRCtrlCh1, int SSRCtrlCh1_size, int *SSRCtrlCh2, int SSRCtrlCh2_size, int *SegTrigOut, int SegTrigOut_size, int *SegMeasType, int SegMeasType_size, double *SegMeasStart, int SegMeasStart_size, double *SegMeasStop, int SegMeasStop_size, int *SeqList, int SeqList_size, int *SeqStartSeg, int SeqStartSeg_size, int *SeqStopSeg, int SeqStopSeg_size, int *SeqListCh1, int SeqListCh1_size, int *SeqListCh2, int SeqListCh2_size, double *SeqLoopsCh1, int SeqLoopsCh1_size, double *SeqLoopsCh2, int SeqLoopsCh2_size, double SMU_V, double SMU_Irange, double SMU_Icomp, char *SMU_ID, char *PMU_ID, double *VMeasCh1, int VMeasCh1_size, double *IMeasCh1, int IMeasCh1_size, double *VMeasCh2, int VMeasCh2_size, double *IMeasCh2, int IMeasCh2_size, double *TimeOutput, int TimeOutput_size, int *StatusCh1, int StatusCh1_size, int *StatusCh2, int StatusCh2_size )
{
/* USRLIB MODULE CODE */
    int status, i, j;
    int InstId, SMUId;
    boolean SMUPresent;

    int MeasType = 1;
    
    int verbose = 0;
    char ErrMsgChar[150];
    double NumTotalSamples,TestTotalSamples;
    int RateFactor;
    long MeasureType;
    double t;
    double TotalSegTime, TotalSegTimeCh2, SampleRate;
    char ermessage[100];
    double* seqMeasTime;
    int segmIndex, sequenceNumber, segmentCount;
    int NumSegments = SegTime_size;
    int NumWaveforms = 1;
    int seqIndex;
    char No_SMU[10] = "NONE";
	long SeqCh1List[512], SeqCh2List[512];

    //Initialize variables
//    verbose = 1;        //prints out status messages to Message Console (type msgcon at command prompt)
    TotalSegTime = 0.0;
    NumTotalSamples = 0;
    SampleRate = 200E+6;
    RateFactor = 0;
    SMUId = 0;
    SMUPresent = FALSE;

    //Set all global arrays to null
    PulseMeasType = NULL;

    //Check to see if requested PMU is in system
    if ( !LPTIsInCurrentConfiguration(PMU_ID) )
    {
        printf("Instrument %s is not in system configuration", PMU_ID);
        return -1;
    }

    //Check if input arrays are equal size
    if (NumSegments != SegTime_size || NumSegments != StartVCh1_size || NumSegments != StopVCh1_size || NumSegments != StartVCh2_size || NumSegments != StopVCh2_size || NumSegments != MeasEnabled_size || NumSegments != SSRCtrlCh1_size || NumSegments != SSRCtrlCh2_size || NumSegments != SegTrigOut_size)
    {
        sprintf(ErrMsgChar, "One or more segment input array size(s) != NumSegments (= %d).", NumSegments);
        logMsg(MF_Error, ERROR_STRING, ErrMsgChar); 
        return ERR_PMU_EXAMPLES_OUTPUT_ARRAY_TOO_SMALL;
    }

    if (SeqList_size != SeqStartSeg_size || SeqList_size != SeqStopSeg_size)
    {
        sprintf(ErrMsgChar, "Segment sequence input array sizes are not equal.");
        logMsg(MF_Error, ERROR_STRING, ErrMsgChar); 
        return ERR_PMU_EXAMPLES_OUTPUT_ARRAY_TOO_SMALL;
    }

    //Determine if return array sizes are big enough to contain
    //the desired number of rows (from MaxSheetPoints)
    if (MaxSheetPoints > VMeasCh1_size || MaxSheetPoints > IMeasCh1_size || MaxSheetPoints > VMeasCh2_size || MaxSheetPoints > IMeasCh2_size || MaxSheetPoints >  TimeOutput_size || MaxSheetPoints > StatusCh1_size  || MaxSheetPoints > StatusCh2_size)
    {
        if (verbose)
            printf("One or more Output array size(s) < MaxSheetPoints. Increase size of all Output arrays to be at least %d", MaxSheetPoints);
        sprintf(ErrMsgChar, "One or more Output array size(s) < MaxSheetPoints. Increase size of all Output arrays to be at least %d.", MaxSheetPoints);
        logMsg(MF_Error, ERROR_STRING, ErrMsgChar); 
        return ERR_PMU_EXAMPLES_OUTPUT_ARRAY_TOO_SMALL;
    }

    //Get internal handle for PMU        
    getinstid(PMU_ID, &InstId);
    if ( -1 == InstId )
        return -2;

    //Check: is a SMU ID set (SMUx or NONE)?  If a SMU string, is in the the chassis?
    if ( _stricmp(SMU_ID, No_SMU) )
    {
        if ( verbose )
            printf("SegArb_ExFull: SMU string present, %s", SMU_ID);

        if ( !LPTIsInCurrentConfiguration(SMU_ID) )
        {
            printf("SegArb_ExFull: Instrument %s is not in system configuration", PMU_ID);
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
            printf("SegArb_ExFull: No SMU specified, SMU_ID = %s", SMU_ID);
    }
    
    //Ensure that 4225-RPMs (if attached) are in the pulse mode
    status = rpm_config(InstId, 1, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
        return status ;

    status = rpm_config(InstId, 2, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
        return status ;

    //Set PMU into Seg-Arb mode
    status = pg2_init(InstId, PULSE_MODE_SARB);
    if ( status )
    {
        printf("SegArb_ExFull Error: Pg2_init status= %d, PULSE_MODE_SARB= %d", status, PULSE_MODE_SARB);
        return status ;
    }

    if ( SMUPresent )
    {
        if ( verbose )
            printf("SegArb_ExFull: SMU present, V= %g, Irange= %g", SMU_V, SMU_Irange);

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
        return status ;

    //Program PMU with resistance of connected DUT 
    status = pulse_load(InstId, 1, DUTResCh1);
    if ( status )
    {
        printf("SegArb_ExFull Error: Ch1 pulse_load status= %d", status);
        return status ;
    }
    status = pulse_load(InstId, 2, DUTResCh2);
    if ( status )
    {
        printf("SegArb_ExFull Error: Ch2 pulse_load status= %d", status);
        return status ;
    }


    //Program the PMU voltage source and current measure ranges
    status = pulse_ranges(InstId, 1, VRangeCh1, PULSE_MEAS_FIXED, VRangeCh1, PULSE_MEAS_FIXED, IRangeCh1);
    if ( status )
    {
        printf("SegArb_ExFull Error: Ch1 pulse_ranges status= %d", status);
        return status ;
    }

    status = pulse_ranges(InstId, 2, VRangeCh2, PULSE_MEAS_FIXED, VRangeCh2, PULSE_MEAS_FIXED, IRangeCh2);
    if ( status )
    {
        logMsgGet(ermessage, status);
        printf("SegArb_ExFull: logMsgGet, string= %c20, status= %d", ermessage, status);
        printf("SegArb_ExFull: Ch2 pulse_ranges status= %d", status);
        return status ;
    }
    
    //Calculate and set the sample rate for the PMU
    //Calculate total Seg-Arb time
    seqMeasTime = (double *)calloc(SeqList_size, sizeof(double));
    for (i=0; i<SeqList_size; i++)
    {
        seqMeasTime[i] = 0;
        if (SeqStartSeg[i] <= 0 || SeqStopSeg[i] <= SeqStartSeg[i] || SeqStartSeg[i] >= NumSegments || SeqStopSeg[i] > NumSegments)
            continue;

        //SeqStartSeg SeqStopSeg indexes are 1 based (actual elements in array 0 based)
        for(j=(SeqStartSeg[i]-1); j<SeqStopSeg[i]; j++)
        {
            seqMeasTime[i] += (MeasEnabled[j] * SegTime[j] * (SegMeasStop[j] - SegMeasStart[j]));        
        }
    }
    for (i=0; i<SeqListCh1_size; i++)
    {
		SeqCh1List[i] = (long)SeqListCh1[i];
        //SeqListCh1[i] is 1 based 
        seqIndex = SeqListCh1[i] - 1;
        if (seqIndex >= 0 && seqIndex < SeqList_size)
        {
            TotalSegTime += SeqLoopsCh1[i] * seqMeasTime[seqIndex];
        }
    }
    TotalSegTimeCh2 = 0;
    for (i=0; i<SeqListCh2_size; i++)
    {
		SeqCh2List[i] = (long)SeqListCh2[i];
		//SeqListCh2[i] is 1 based 
        seqIndex = SeqListCh2[i] - 1;
        if (seqIndex >= 0 && seqIndex < SeqList_size)
        {
            TotalSegTimeCh2 += SeqLoopsCh2[i] * seqMeasTime[seqIndex];
        }
    }
    free(seqMeasTime);

    if (fabs(TotalSegTime - TotalSegTimeCh2) > 0.01*TotalSegTime)
    {
        printf("SegArb_ExFull: Segment sequencies for Ch1 and Ch2 must be the same time duration.");
        return -1;
    }

    if (verbose)
        printf("SegArb_ExFull: TotalSegTime = %g, SampleRate= %g", TotalSegTime, SampleRate);

    //Calculate total samples, because PMU has a maximum of MaxSamplesPerAtoD (at the time of this UTM, 1 million samples)
    TestTotalSamples = (TotalSegTime * NumWaveforms * SampleRate);

    //if total samples for the test > MaxSamplesPerAtoD, then set sample_rate to lower value
    if ((TestTotalSamples) > MaxSamplesPerAtoD)
    {
        RateFactor = (int)((TestTotalSamples / MaxSamplesPerAtoD) + 1);      
        SampleRate = (SampleRate / RateFactor);
        if ( verbose )
            printf("SegArb_ExFull: TestSamplesTimeCaptured (%g) > MaxSamplesPerAtoD (%d), Ratefactor= %d", TestTotalSamples, MaxSamplesPerAtoD, RateFactor);
    }

    //Calculate number of samples (rows in sheet)
    if (AcqType == 0)            //Discrete measurements for each waveform output
        NumTotalSamples = (TotalSegTime * NumWaveforms * SampleRate);    
    if (AcqType == 1)            //Average measurements across all waveforms output
        NumTotalSamples = (TotalSegTime * SampleRate);    

    if (verbose)
       printf("SegArb_ExFull: TotalSegTime = %g, NumTotalSamples= %g, MaxSheetPts= %d", TotalSegTime, NumTotalSamples, MaxSheetPoints);


    //If number of samples is greater than the maximum number of rows in the sheet, set a lower sample rate
    if (NumTotalSamples > MaxSheetPoints)
    {
        RateFactor = (int)((NumTotalSamples / MaxSheetPoints) + 1);      
        SampleRate = (SampleRate / RateFactor);
        if (verbose)
            printf("SegArb_ExFull:  NumSamples > MaxsheetPts, Ratefactor= %d", RateFactor);
    }

    if (verbose)
        printf("SegArb_ExFull: NumTotalSamples= %g, MaxSheetPts= %d, SampleRate= %g", NumTotalSamples, MaxSheetPoints, SampleRate);

    NumTotalSamples = (int)(TotalSegTime * SampleRate);    
    if (verbose)
        printf("SegArb_ExFull: Using new sample rate, NumTotalSamples= %g, SampleRate= %g", NumTotalSamples, SampleRate);

    status = pulse_sample_rate(InstId, (long)SampleRate);

    if (verbose)
        printf("SegArb_ExFull: sample_rate status= %d", status);

    if ( status )
    {
        printf("SegArb_ExFull Error: sample_rate status= %d", status);
        return status;
    }

    //Program number of Seg-Arb waveforms to output
    status = pulse_burst_count(InstId, 1, NumWaveforms);
    if ( status )
    {
        printf("SegArb_ExFull Error: Ch1 burst count status= %d", status);
        return status ;
    }
    status = pulse_burst_count(InstId, 2, NumWaveforms);
    if ( status )
    {
        printf("SegArb_ExFull Error: Ch2 burst count status= %d", status);
        return status ;
    }

    //Set Array names so that data can be automatically returned to the data sheet
    status = pulse_measrt(InstId, 1, "VMeasCh1", "IMeasCh1", "TimeOutput", NULL);
    if ( status )
        return status ;

    status = pulse_measrt(InstId, 2, "VMeasCh2", "IMeasCh2", "", NULL);
    if ( status )
        return status ;
   
    //Fill Trigger and MeasType array for Segment ARB.  Ensure that first entry in Trigger Out array is 1.
    SegTrigOut[0] = 1;

    //Set size of arrays
    AllocateArrays_SegArbExF(NumSegments);

    //Fill Measure Type, start and stop arrays for the segments
    for(i=0; i<NumSegments; i++)
    {
        //Determine and set measure type using system parameter names
        //MeasType = 1 for spot mean, MeasType = 2 for sample (waveform)
        //AcqType = 1 for Per burst (averaging), AcqType = 0 for Per Period (discrete values)
        if (SegMeasType[i] == 1 && AcqType == 1)
            MeasureType = PULSE_MEAS_SMEAN_BURST;            //Spot Mean per Burst (average spot means across repeated waveforms)
        else if (SegMeasType[i] == 1 && AcqType == 0)
            MeasureType = PULSE_MEAS_SMEAN_PER;              //Spot Mean per Period (discrete, no average across multiple waveforms)
        else if (SegMeasType[i] == 2 && AcqType == 1)
            MeasureType = PULSE_MEAS_WFM_BURST;              //Sample (Waveform) per Burst (average repeated waveforms together into single waveform)
        else if (SegMeasType[i] == 2 && AcqType == 0)
            MeasureType = PULSE_MEAS_WFM_PER;                //Waveform per Period (discrete, no average across multiple waveforms)

        if (verbose)
            printf("SegArb_ExFull: MeasureType= %d", MeasureType);

        PulseMeasType[i] = MeasureType * MeasEnabled[i];
        //Adjust segment start & stop time values in place (don't create separate arrays)
        SegMeasStart[i] *= SegTime[i];
        SegMeasStop[i] *= SegTime[i];
    }

    //SARB sequencies for the Ch1
    for (i=0; i<SeqList_size; i++)
    {
        sequenceNumber = i+1;
        segmIndex = SeqStartSeg[i] - 1;
        segmentCount = SeqStopSeg[i] - segmIndex;
        if (segmIndex < 0 || segmentCount < 0 || segmIndex > NumSegments || (segmIndex + segmentCount) > NumSegments)
        {
            printf("SegArb_ExFull Error: Corrupted Ch1 segarb sequence definition");
            FreeArrays_SegArbExF();
            return -1;
        }

        status = seg_arb_sequence(InstId,  1, sequenceNumber,  segmentCount, &StartVCh1[segmIndex], &StopVCh1[segmIndex], &SegTime[segmIndex], 
                                    (long *)&SegTrigOut[segmIndex], (long *)&SSRCtrlCh1[segmIndex], &PulseMeasType[segmIndex], &SegMeasStart[segmIndex], &SegMeasStop[segmIndex]);
        if ( status )
        {
            printf("SegArb_ExFull Error: Ch1 segarb sequence status= %d", status);
            FreeArrays_SegArbExF();
            return status;
        }
    }

    //Program Segment ARB Waveform (1 per channel)
    status = seg_arb_waveform(InstId, 1, SeqListCh1_size, SeqCh1List, SeqLoopsCh1);
    if ( status )
    {
        printf("SegArb_ExFull Error: Ch1 segarb waveform status= %d", status);
        FreeArrays_SegArbExF();
        return status;
    }

    //SARB sequencies for the Ch2
    for (i=0; i<SeqList_size; i++)
    {
        sequenceNumber = i+1;
        segmIndex = SeqStartSeg[i] - 1;
        segmentCount = SeqStopSeg[i] - segmIndex;
        if (segmIndex < 0 || segmentCount < 0 || segmIndex > NumSegments || (segmIndex + segmentCount) > NumSegments)
        {
            printf("SegArb_ExFull Error: Corrupted Ch2 segarb sequence definition");
            FreeArrays_SegArbExF();
            return -1;
        }

        status = seg_arb_sequence(InstId,  2, sequenceNumber,  segmentCount, &StartVCh2[segmIndex], &StopVCh2[segmIndex], &SegTime[segmIndex], 
                                    (long *)&SegTrigOut[segmIndex], (long *)&SSRCtrlCh2[segmIndex], &PulseMeasType[segmIndex], &SegMeasStart[segmIndex], &SegMeasStop[segmIndex]);
        if ( status )
        {
            printf("SegArb_ExFull Error: Ch2 segarb sequence status= %d", status);
            FreeArrays_SegArbExF();
            return status;
        }
    }
    
    status = seg_arb_waveform(InstId, 2, SeqListCh2_size, SeqCh2List, SeqLoopsCh2);
    if ( status )
    {
        printf("SegArb_ExFull Error: Ch2 segarb waveform status= %d", status);
        FreeArrays_SegArbExF();
        return status;
    }

    //Turn on outputs    
    status = pulse_output(InstId, 1, 1);
    if ( status )
    {
        FreeArrays_SegArbExF();        
        return status ;
    }

    status = pulse_output(InstId, 2, 1);
    if ( status )
    {
        FreeArrays_SegArbExF();        
        return status ;
    }

    if (verbose)
        printf("SegArb_ExFull:  Just before pulse_exec");

    //Run test:  output Segment ARB waveform while measuring
    status = pulse_exec(PULSE_MODE_SIMPLE);
    if ( status )
    {
        printf("SegArb_ExFull Error: attempting to run pulse_exec, status= %d", status);
        FreeArrays_SegArbExF();        
        return status ;
    }

    if (verbose)
        printf("SegArb_ExFull:  Just after pulse_exec");

    if ( status )
           return status;
        while ( pulse_exec_status(&t) == 1 )
        {
            Sleep(100);
        }

    if ( SMUPresent )
    {
        if ( verbose )
            printf("SegArb_ExFull: SMU present, setting voltage = 0");

        status = forcev(SMUId, 0);
        if ( status )
        {
            FreeArrays_SegArbExF();        
            return status ;
        }
    }

    FreeArrays_SegArbExF();
    return 0;
}

void AllocateArrays_SegArbExF(int NumberofSegments)
{
    //Allocate arrays for Segment ARB: measure type only so far.  
    PulseMeasType = (long *)calloc(NumberofSegments, sizeof(long));
}
void FreeArrays_SegArbExF()
{
    //Free memory for arrays before exiting UTM
    if (PulseMeasType != NULL)
        free(PulseMeasType);

/* USRLIB MODULE END  */
} 		/* End PMU_SegArb_ExampleFull.c */

