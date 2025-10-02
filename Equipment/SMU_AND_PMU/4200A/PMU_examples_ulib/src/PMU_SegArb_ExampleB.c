/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_SegArb_ExampleB
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 50
	ARGUMENTS:
		VRangeCh1,	double,	Input,	10,	5,	40
		IRangeCh1,	double,	Input,	.01,	100e-9,	.8
		VRangeCh2,	double,	Input,	10,	5,	40
		IRangeCh2,	double,	Input,	.01,	100e-9,	.8
		NumWaveforms,	int,	Input,	1,	1,	1
		MeasType,	int,	Input,	1,	1,	2
		MeasSegStart,	double,	Input,	0,	0,	1.0
		MeasSegStop,	double,	Input,	1.0,	0,	1.0
		AcqType,	int,	Input,	0,	0,	0
		DUTResCh1,	double,	Input,	1E6,	1,	1E6
		DUTResCh2,	double,	Input,	1E6,	1,	1E6
		MaxSheetPoints,	int,	Input,	5000,	12,	30000
		NumSegments,	int,	Input,	6,	3,	2048
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
void AllocateArrays_SegArbExB(int NumberofSegments);
void FreeArrays_SegArbExB();

double *MeasStart, *MeasStop;
unsigned long *PulseMeasType;

#pragma warning( disable: 4996 )

	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: PMU_SegArb_ExampleB
===========================

Description
-----------
This module configures multi-segment waveform generation (Segment Arb) on 2
channels using a single 4225-PMU and measures and returns either waveform (V
and I versus time) or spot mean data for each segment that has measurement 
enabled.  

This routine defines a single Segment Arb sequence for each channel with 3 to 2048 
segments.  

Measurement type is either waveform or spot mean. When using waveform 
measure type, control the number of samples by the MaxSheetPoints parameter.

Parameters that are common to both channels:

* Number of segments 
* Segment timing 
* Measurement Type
* Measurement Window (measure start and stop within a segment)
* Trigger output

Per Channel parameters:

* Voltages
* Source range
* Measure range
* Solid-state relay control

Optional SMU available for voltage biasing of a device terminal that does 
not react to the pulse. For example, do not connect SMU to DUT drain, gate, 
or source of a transistor. Note that the SMU cannot be connected to an RPM, 
or a -233 error ("forcev(): Cannot force when not connected.") will occur.

This routine is not compatible with KXCI (UL mode).

This routine uses a different method to get the data from the PMU card 
into the Clarius Analyze sheet: pulse_measrt. The pulse_measrt() command allows the data 
to go directly from the card to the Analyze sheet, without the need to pull 
the data into the UTM before re-sending to the sheet. This simplifies 
the UTM code and reduces the time required to get lots of data from the 
card to the sheet, which is most beneficial when retrieving PMU waveform 
data. The pulse_measrt() command is not compatible with KXCI.

How to use
----------
Set appropriate values for all input parameters (as described in the below
section).

Both channels must have valid entries for all the parameters.

All input arrays must have the same size.

Start voltage values must match the stop voltage of the previous segment.

Output array size must be >= MaxSheetPoints

When a channel has a 4225-RPM connection and is set to a 4225-RPM I 
measure range, load line effect compensation is enabled for that channel.
When using a PMU I measure range, load line effect compensation (LLEC) 
is not available.

The Segment Arb mode does not provide current, voltage, or power thresholds.

If a test configuration will exceed the MaxSheetPoints or MaxSamplesPerAtoD, 
the sample rate for the card will be reduced to fit the results within the MaxSheetPoints.
This condition usually occurs for the waveform measurement type.

This example test supports internal triggering only (triggering inside 4200A 
chassis); no external trigger input is available. This example does support
trigger output via the SegTrigOut array (see description below).

Inputs
------

VRangeCh1	
: Voltage range for Ch 1
: Valid ranges: 10, 40
: Note that maximum voltage for a range is only reached 
		with a high impedance DUT (roughly 100 k&Omega; and higher).

IRangeCh1	
: Current measure range for Ch 1. Valid ranges: 
: PMU 10V:  0.01, 0.2
: PMU 20V:  100e-6, 0.01, 0.8
: RPM 10V:  100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

VRangeCh2	
: Voltage range for Ch 2
: Valid ranges: 10, 40
: Note that maximum voltage for a range is only reached 
		with a high impedance DUT (roughly 100 k&Omega; and higher).

IRangeCh2	
: Current measure range for Ch 2. Valid ranges: 
: PMU 10V:  0.01, 0.2
: PMU 20V:  100e-6, 0.01, 0.8
: RPM 10V:  100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

NumWaveforms	
: Number of waveforms to output. Must be set to 1.

MeasType		
: Measurement type for each segment set to measure:
: 1: Spot Mean
: 2: Sample (waveform)

MeasSegStart		
: Measure window start for segment, in decimal fraction.  				
: 		MeasSegStart < MeasSegStop.
: 		Minimum = 0

MeasSegStop		
: Measure window stop for segment, in decimal fraction
: 		MeasSegStop > MeasSegStart.
: 		Maximum = 1.0

AcqType		
: This parameter must be set to 0.

DUTResCh1	
: Resistance of DUT connected to Ch 1 (&Omega;). Setting this 
		value to represent the actual DUT impedance will greatly 
		reduce the difference between the programmed voltage
		and the voltage at the DUT due to load line effects.  
		This parameter is not meaningful when using a 4225-RPM 
		current measure range.
: Range: 1 to 1e6 &Omega;

DUTResCh2	
: Resistance of DUT connected to Ch 2 (&Omega;). Setting this 
		value to represent the actual DUT impedance will greatly 
		reduce the difference between the programmed voltage
		and the voltage at the DUT due to load line effects.  
		This parameter is not meaningful when using a 4225-RPM 
		current measure range.
: Range: 1 to 1e6 &Omega;

MaxSheetPoints	
: Maximum number of samples, or rows, of data to return to 
		the data sheet.
: Valid values: 12 to 30000

NumSegments	
: Number of segments in the Segment Arb waveform.
		Both channels have the same number of segments.
: Valid values:  3 to 2048 segments

SegTime		
: Time for each segment.
: Valid values: 20e-9 to 40 s in 10 ns steps

StartVCh1	
: Array of Segment Arb start voltage values for channel 1	.

StopVCh1	
: Array of Segment Arb stop voltage values for channel 1.	

StartVCh2	
: Array of Segment Arb start voltage values for channel 2.	

StopVCh2	
: Array of Segment Arb stop voltage values for channel 2.

MeasEnabled		
: Array of values for enabling measurement for each segment
  on both channels. See MeasType parameter, which sets whether
			spot mean or sample measurements are made:
: 0: No Measurement on segment
: 1: Measure this segment

SSRCtrlCh1	
: Array of Segment Arb SSR output relay control
		values for channel 1 (1 = closed, 2 = open)
		Using value = 2 for an array entry means 
		no pulse output for that segment.

SSRCtrlCh2	
: Array of Segment Arb SSR output relay control
		values for channel 2 (1 = closed, 2 = open)
		Using value = 2 for an array entry means 
		no pulse output for that segment.

SegTrigOut	
: Array of trigger values (1 or 0) to 
		output from the PMU trigger out 
		connector. This array must have the 
		same number of entries as all other 
		Segment Arb arrays and the first value in 
		SegTrigOut = 1, otherwise the test
		will not output the waveforms.
: Range:  0 or 1

SMU_V	
: (double) SMU voltage for biasing
			non-pulsed DUT terminal. For
			example, do not connect SMU to 
			transistor source terminal when
			pulsing gate and/or drain.
: Range:  -210 to +210 V

SMU_Irange		
: (double) SMU current range.
: Ranges: 10e-9, 100e-9, 1e-6,
				10e-6, 100e-6, 1e-3,
				10e-3, 100e-3, 1
: Note: 10e-9 requires Preamp and
			1 A range only available on high
			power SMU.

SMU_Icomp
: (double) SMU current compliance.
			This value must > 10% of the 
			above current range.

SMU_ID		
: SMU instrument name, such as "SMU1" (without quotes). For no
			SMU, use "NONE". Note that the SMU cannot be connected to an
			RPM, or a -233 error ("forcev(): Cannot force when not connected.")
			will occur.
: Range:  NONE, SMU1, SMU2, up to maximum SMUs in system.

PMU_ID	
: PMU number. PMU in lowest numbered
		(right-most PMU when viewed from rear
		of the 4200A chassis) is PMU1.

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
       | match previous segment stop value of yyV. Problem with Segment Arb 
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
       | If Vmax is < SegArb voltage requested, Error -846 will occur. Reduce
       | the requested voltage to allow test to run.
-17001 | Wrong card Id. Check PMU and SMU names.
-17002 | Failure to assign card ID handle. Check PMU and/or SMU names.

Example usage
-------------

Staircase voltage sweep

40 point dual sweep (21 steps from 0 to 2V, then 20 steps from 1.8 to 0V) 
with 20 us pulse tops and 200 ns transitions: 0.1, 0.2, 0.3, 0.4 up to 2, then 1.9, 1.8, 1.7 down to 0V

Segment Arb Staircase waveform with measure

~~~~

							  Top (at 2V)
								 __*_
										
						   ...etc       
					  __*_|               |__*_
					 |                         |
				 __*_|                         |__*_
				|                                   |
			__*_| Step width = 20 us                |__*_
		   |                                             |
	   __*_|   Rise time = 200 ns                        |__*_
	  |  ^                                                    |
  __*_|  |         Ch1 Dual Sweep (up/down)                   |__*_
	^    |
	|
~~~~
Measure here (at the "*") during settled part of pulse step (see MeasSegStart, MeasSegStop)
	 
~~~~
      
     __*___*____*____*____*_  ...etc   _*__...__*____*____*___*____*_
    |                                                                |
    |             Ch2 (drain) constant V bias                        |

    Ch1 sweeps
    Ch2 fixed bias (0.5V)
~~~~

If arrays are empty, or to reset them to this staircase sweep, type in
the values for the parameters, then copy and paste values below for each array:

      VRangeCh1: 10
      IRangeCh1: 0.001
      VRangeCh2: 10
      IRangeCh2: 0.001
      NumWaveforms: 1
      MeasType: 1  (1= Spot Mean, 2= waveform)
      MeasSegStart: 0.7 (spot mean window starts at 70% of segment time)
      MeasSegStop: 0.9 (spot mean window stops at 90% of segment time)
      AcqType: 1
      DUTResCh1: 1e6
      DUTResCh2: 1e6
      NumSheetPoints: 5000
      NumSegments: 82 (for dual sweep, set to 41 for up sweep only)

SegTime Array values:

      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9
      20e-6
      200e-9

StartVCh1 Array values:

      0.0
      0.0
      100e-3
      100e-3
      200e-3
      200e-3
      300e-3
      300e-3
      400e-3
      400e-3
      0.5
      0.5
      600e-3
      600e-3
      700e-3
      700e-3
      800e-3
      800e-3
      900e-3
      900e-3
      1.0
      1.0
      1.1
      1.1
      1.2
      1.2
      1.3
      1.3
      1.4
      1.4
      1.5
      1.5
      1.6
      1.6
      1.7
      1.7
      1.8
      1.8
      1.9
      1.9
      2.0
      2.0
      1.9
      1.9
      1.8
      1.8
      1.7
      1.7
      1.6
      1.6
      1.5
      1.5
      1.4
      1.4
      1.3
      1.3
      1.2
      1.2
      1.1
      1.1
      1.0
      1.0
      900e-3
      900e-3
      800e-3
      800e-3
      700e-3
      700e-3
      600e-3
      600e-3
      0.5
      0.5
      400e-3
      400e-3
      300e-3
      300e-3
      200e-3
      200e-3
      100e-3
      100e-3
      0.0
      0.0

StopVCh1 Array values:

      0.0
      100e-3
      100e-3
      200e-3
      200e-3
      300e-3
      300e-3
      400e-3
      400e-3
      0.5
      0.5
      600e-3
      600e-3
      700e-3
      700e-3
      800e-3
      800e-3
      900e-3
      900e-3
      1.0
      1.0
      1.1
      1.1
      1.2
      1.2
      1.3
      1.3
      1.4
      1.4
      1.5
      1.5
      1.6
      1.6
      1.7
      1.7
      1.8
      1.8
      1.9
      1.9
      2.0
      2.0
      1.9
      1.9
      1.8
      1.8
      1.7
      1.7
      1.6
      1.6
      1.5
      1.5
      1.4
      1.4
      1.3
      1.3
      1.2
      1.2
      1.1
      1.1
      1.0
      1.0
      900e-3
      900e-3
      800e-3
      800e-3
      700e-3
      700e-3
      600e-3
      600e-3
      0.5
      0.5
      400e-3
      400e-3
      300e-3
      300e-3
      200e-3
      200e-3
      100e-3
      100e-3
      0.0
      0.0
      0.0

StartVCh2 Array values:

      0.0
      0.0
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5

StopVCh2 Array values:

      0.0
      0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
	  0.5
	  0.5
	  0.5
	  0.5
      0.0

MeasEnabled

      1
	  0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
	  0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
	  0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
	  0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0

SSRCtrlCh1 array values:

      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1

SSRCtrlCh2 array values:

      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1
      1

SegTrigOut array values:

      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0
      1
      0

      SMU_V: 0
      SMU_Irange: 0.01
      SMU_Icomp: 0.01
      SMU_ID: [blank, no entry]
      PMU_ID: PMU1

      VMeasCh1_size, IMeasCh1_size
      VMeasCh2_size, IMeasCh2_size
      TimeOutput_size
      StatusCh1_size, StatusCh2_size: 10000

=======================================================================
***********************************************************************
=======================================================================

EXAMPLE SETTINGS FOR HYSTERESIS IV PULSE:
-------------------------------------------
This example uses the rise and fall of a pulse as the up and down sweep
to create a hysteresis IV curve.

The purpose of this routine is to allow for a relatively long stress at
he top of the pulse (up to 40s per segment, default uses 3 segments for
up to 120s), then compare the IV characteristics by measuring during the
pulse rise and fall.

Ch1 Pulse: 0 to 2V
~~~~

          _____stress time (60 ns to 40s per segment)___
         *    No measure on pulse top                   *                          
        *                                                *
       *                                                  *            
      * Rise & fall time                                   *
     *      minimum = 20 ns, maximum = 33 ms                *
    *                                                        *
___*            * = sample (waveform measure)                 *____

~~~~
Ch2 Constant Voltage Bias: 0.5V
~~~~
  _*******______________________________________________*******_
 |  *= measure      _=source only (no measure)                  |
_|                                                              |_
~~~~

Timing Adjustments are in the array "SegTime". Entries 2 and 6 (100E-6) in
the below example) are the rise and fall times. Use rise=fall for proper
graphing of IV hysteresis. To increase the time on the pulse top, the stress
time, increase the time in Entries 3, 4 and 5 (maximum is 40s, minimum is 60E-9 for
each entry).

If arrays are empty, or to reset them to this staircase sweep, type in
the values for the parameters, then copy and paste values below for each array:

      VRangeCh1: 10
      IRangeCh1: 0.001
      VRangeCh2: 10
      IRangeCh2: 0.001
      NumWaveforms: 1
      MeasType: 2  (1= Spot Mean, 2= waveform)
      MeasSegStart: 0.01 (sample window starts at 1% of segment time)
      MeasSegStop: 1.0 (spot mean window stops at 100% of segment time)
      AcqType: 1
      DUTResCh1: 1E6
      DUTResCh2: 1E6
      NumSheetPoints: 5000
      NumSegments: 7

SegTime Array values:

      2e-6
      100e-6
      10e-6
      10e-6
      10e-6
      100e-6
      2e-6

StartVCh1 Array values:

      0.0
      0.0
      1.5
      1.5
      1.5
      1.5
      0.0

StopVCh1 Array values:

      0.0
      1.5
      1.5
      1.5
      1.5
      0.0
      0.0

StartVCh2 Array values:

      0.0
      0.5
      0.5
      0.5
      0.5
      0.5
      0.5

StopVCh2 Array values:

      0.5
      0.5
      0.5
      0.5
      0.5
      0.5
      0.0

MeasEnabled

      0
      1
      0
      0
      0
      1
      0

SSRCtrlCh1 array values:

      1
      1
      1
      1
      1
      1
      1

SSRCtrlCh2 array values:
      1
      1
      1
      1
      1
      1
      1

SegTrigOut array values:

      0
      1
      0
      0
      0
      1
      0

SMU_V: 0

SMU_Irange: 0.01

SMU_Icomp: 0.01

SMU_ID: [blank, no entry]

PMU_ID: PMU1


VMeasCh1_size, IMeasCh1_size

VMeasCh2_size, IMeasCh2_size

TimeOutput_size

StatusCh1_size, StatusCh2_size: 10000

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_SegArbExB(int NumberofSegments);
void FreeArrays_SegArbExB();

double *MeasStart, *MeasStop;
unsigned long *PulseMeasType;

#pragma warning( disable: 4996 )


int PMU_SegArb_ExampleB( double VRangeCh1, double IRangeCh1, double VRangeCh2, double IRangeCh2, int NumWaveforms, int MeasType, double MeasSegStart, double MeasSegStop, int AcqType, double DUTResCh1, double DUTResCh2, int MaxSheetPoints, int NumSegments, double *SegTime, int SegTime_size, double *StartVCh1, int StartVCh1_size, double *StopVCh1, int StopVCh1_size, double *StartVCh2, int StartVCh2_size, double *StopVCh2, int StopVCh2_size, int *MeasEnabled, int MeasEnabled_size, int *SSRCtrlCh1, int SSRCtrlCh1_size, int *SSRCtrlCh2, int SSRCtrlCh2_size, int *SegTrigOut, int SegTrigOut_size, double SMU_V, double SMU_Irange, double SMU_Icomp, char *SMU_ID, char *PMU_ID, double *VMeasCh1, int VMeasCh1_size, double *IMeasCh1, int IMeasCh1_size, double *VMeasCh2, int VMeasCh2_size, double *IMeasCh2, int IMeasCh2_size, double *TimeOutput, int TimeOutput_size, int *StatusCh1, int StatusCh1_size, int *StatusCh2, int StatusCh2_size )
{
/* USRLIB MODULE CODE */
    int status, i;
    int InstId, SMUId;
    boolean SMUPresent;
    
    int verbose = 0;
    char ErrMsgChar[150];
    double NumTotalSamples,TestTotalSamples;
    int RateFactor;
    long SeqList[1], MeasureType;
    double t;
    double LoopCountList[1];
    double TotalSegTime, SampleRate;
    char ermessage[100];
    char No_SMU[10] = "NONE";
	
    //Initialize variables
    //verbose = 1;        //prints out status messages to Message Console (type msgcon at command prompt)
    TotalSegTime = 0.0;
    NumTotalSamples = 0;
    SampleRate = 200E+6;
    RateFactor = 0;
    SMUId = 0;
    SMUPresent = FALSE;

    //Set all global arrays to null
    MeasStart = MeasStop = NULL;
    PulseMeasType = NULL;

    //Check to see if requested PMU is in system
    if ( !LPTIsInCurrentConfiguration(PMU_ID) )
    {
        printf("Instrument %s is not in system configuration", PMU_ID);
        return -1;
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
            printf("PMU_SegArb_ExampleB: SMU string present, %s", SMU_ID);

        if ( !LPTIsInCurrentConfiguration(SMU_ID) )
        {
            printf("PMU_SegArb_ExampleB: Instrument %s is not in system configuration", PMU_ID);
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
            printf("PMU_SegArb_ExampleB: No SMU specified, SMU_ID = %s", SMU_ID);
    }

    //Ensure that 4225-RPMs (if attached) are in the pulse mode
    status = rpm_config(InstId, 1, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
    {
        return status ;
    }

    status = rpm_config(InstId, 2, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
    {
        return status ;
    }

    //Set PMU into Segment Arb mode
    status = pg2_init(InstId, PULSE_MODE_SARB);
    if ( status )
    {
        printf("SegArb_ExB Error: Pg2_init status= %d, PULSE_MODE_SARB= %d", status, PULSE_MODE_SARB);
        return status ;
    }

    if ( SMUPresent )
    {
        if ( verbose )
            printf("SegArb_ExB: SMU present, V= %g, Irange= %g", SMU_V, SMU_Irange);

        status = rangei(SMUId, SMU_Irange);
        if ( status )
        {
            return status ;
        }

        status = limiti(SMUId, SMU_Icomp);
        if ( status )
        {
            return status ;
        }

        status = forcev(SMUId, SMU_V);
        if ( status )
        {
            return status ;
        }
    }

    //Set PMU to return actual values when measurement overflow occurs
    status = setmode(InstId, KI_LIM_MODE, KI_VALUE);
    if ( status )
    {
        return status ;
    }

    //Program PMU with resistance of connected DUT 
    status = pulse_load(InstId, 1, DUTResCh1);
    if ( status )
    {
        printf("SegArb_ExB Error: Ch1 pulse_load status= %d", status);
        return status ;
    }
    status = pulse_load(InstId, 2, DUTResCh2);
    if ( status )
    {
        printf("SegArb_ExB Error: Ch2 pulse_load status= %d", status);
        return status ;
    }


    //Program the PMU voltage source and current measure ranges
    status = pulse_ranges(InstId, 1, VRangeCh1, PULSE_MEAS_FIXED, VRangeCh1, PULSE_MEAS_FIXED, IRangeCh1);
    if ( status )
    {
        printf("SegArb_ExB Error: Ch1 pulse_ranges status= %d", status);
        return status ;
    }

    status = pulse_ranges(InstId, 2, VRangeCh2, PULSE_MEAS_FIXED, VRangeCh2, PULSE_MEAS_FIXED, IRangeCh2);
    if ( status )
    {
        logMsgGet(ermessage, status);
        printf("SegArb_ExB: logMsgGet, string= %c20, status= %d", ermessage, status);
        printf("SegArb_ExB: Ch2 pulse_ranges status= %d", status);
        return status ;
    }
    
	    //Set size of arrays
    AllocateArrays_SegArbExB(NumSegments);

    //Calculate and set the sample rate for the PMU
    //Calculate total Segment Arb time

        for(i=0; i<NumSegments; i++)
        {
            TotalSegTime += (MeasEnabled[i] * SegTime[i] * (MeasSegStop - MeasSegStart));        
        if (verbose)
            {
                printf("SegArb_ExB: i= %d, TotalSegTm= %g, MzEn[%d]= %d, SegTime= %g, MzStrt= %g, MzStp= %g", i, TotalSegTime, i, MeasEnabled[i], SegTime[i], MeasSegStart, MeasSegStop);
                printf("SegArb_ExB: SegTime * MeasStart* MeasStop = %g", SegTime[i] * (MeasSegStop - MeasSegStart));
            }
        }
    

    if (verbose)
        printf("SegArb_ExB: TotalSegTime = %g, SampleRate= %g", TotalSegTime, SampleRate);


    //Calculate total samples, because PMU has a maximum of MaxSamplesPerAtoD (at the time of this UTM, 1 million samples)
    TestTotalSamples = (TotalSegTime * NumWaveforms * SampleRate);

    //if total samples for the test > MaxSamplesPerAtoD, then set sample_rate to lower value
    if ((TestTotalSamples) > MaxSamplesPerAtoD)
    {
        RateFactor = (int)((TestTotalSamples / MaxSamplesPerAtoD) + 1);      
        SampleRate = (SampleRate / RateFactor);
        if ( verbose )
            printf("SegArb_ExB: TestSamplesTimeCaptured (%g) > MaxSamplesPerAtoD (%d), Ratefactor= %d", TestTotalSamples, MaxSamplesPerAtoD, RateFactor);
    }

    //Calculate number of samples (rows in sheet)
    if (AcqType == 0)            //Discrete measurements for each waveform output
        NumTotalSamples = (TotalSegTime * NumWaveforms * SampleRate);    
    if (AcqType == 1)            //Average measurements across all waveforms output
        NumTotalSamples = (TotalSegTime * SampleRate);    

    if (verbose)
       printf("SegArb_ExB: TotalSegTime = %g, NumTotalSamples= %g, MaxSheetPts= %d", TotalSegTime, NumTotalSamples, MaxSheetPoints);


    //If number of samples is greater than the maximum number of rows in the sheet, set a lower sample rate
    if (NumTotalSamples > MaxSheetPoints)
    {
        RateFactor = (int)((NumTotalSamples / MaxSheetPoints) + 1);      
        SampleRate = (SampleRate / RateFactor);
        if (verbose)
            printf("SegArb_ExB:  NumSamples > MaxsheetPts, Ratefactor= %d", RateFactor);
    }

    if (verbose)
        printf("SegArb_ExB: NumTotalSamples= %g, MaxSheetPts= %d, SampleRate= %g", NumTotalSamples, MaxSheetPoints, SampleRate);
    NumTotalSamples = (int)(TotalSegTime * SampleRate);    
    if (verbose)
        printf("SegArb_ExB: Using new sample rate, NumTotalSamples= %g, SampleRate= %g", NumTotalSamples, SampleRate);

    status = pulse_sample_rate(InstId, (long)SampleRate);

    if (verbose)
        printf("SegArb_ExB: sample_rate status= %d", status);

    if ( status )
    {
        printf("SegArb_ExB Error: sample_rate status= %d", status);
        FreeArrays_SegArbExB();
        return status;
    }

    //Program number of Segment Arb waveforms to output
    status = pulse_burst_count(InstId, 1, 1);
    if ( status )
    {
        printf("SegArb_ExB Error: Ch1 burst count status= %d", status);
        FreeArrays_SegArbExB();
        return status ;
    }
    status = pulse_burst_count(InstId, 2, 1);
    if ( status )
    {
        printf("SegArb_ExB Error: Ch2 burst count status= %d", status);
        FreeArrays_SegArbExB();
        return status ;
    }

    //Set Array names so that data can be automatically returned to the data sheet
    status = pulse_measrt(InstId, 1, "VMeasCh1", "IMeasCh1", "TimeOutput", NULL);
    if ( status )
    {
        FreeArrays_SegArbExB();
        return status ;
    }

    status = pulse_measrt(InstId, 2, "VMeasCh2", "IMeasCh2", "", NULL);
    if ( status )
    {
        FreeArrays_SegArbExB();
        return status ;
    }
   
    //Fill Trigger and MeasType array for Segment Arb.  Ensure that first entry in Trigger Out array is 1.
    i = 0;
    SegTrigOut[i] = 1;

    //Populate Sequence List, only 1 sequence in this example, same for each channel
    SeqList[i] = 1;

    //Set number of waveforms to output.  Use Sequence Looping (instead of pulse_burst).
    LoopCountList[0] =  NumWaveforms;   

    //Determine and set measure type using system parameter names
    //MeasType = 1 for spot mean, MeasType = 2 for sample (waveform)
    //AcqType = 1 for Per burst (averaging), AcqType = 0 for Per Period (discrete values)
    if (MeasType == 1 && AcqType == 1)
        MeasureType = (long)PULSE_MEAS_SMEAN_BURST;            //Spot Mean per Burst (average spot means across repeated waveforms)
    if (MeasType == 1 && AcqType == 0)
        MeasureType = (long)PULSE_MEAS_SMEAN_PER;              //Spot Mean per Period (discrete, no average across multiple waveforms)
    if (MeasType == 2 && AcqType == 1)
        MeasureType = (long)PULSE_MEAS_WFM_BURST;              //Sample (Waveform) per Burst (average repeated waveforms together into single waveform)
    if (MeasType == 2 && AcqType == 0)
        MeasureType = (long)PULSE_MEAS_WFM_PER;                //Waveform per Period (discrete, no average across multiple waveforms)

    if (verbose)
        printf("SegArb_ExB: MeasureType= %d", MeasureType);

    //Fill Measure Type, start and stop arrays for the sequences
    for(i=0; i<NumSegments; i++)
    {
        PulseMeasType[i] = (long)(MeasureType * MeasEnabled[i]);
        MeasStart[i] = (double)(SegTime[i] * MeasSegStart);
        MeasStop[i] = (double)(SegTime[i] * MeasSegStop);
    }

    //Program Segment Arb Sequences (1 per channel)
    status = seg_arb_sequence(InstId,  1, 1,  NumSegments, StartVCh1, StopVCh1, SegTime, (long *)SegTrigOut, (long *)SSRCtrlCh1, PulseMeasType, MeasStart, MeasStop);
    if ( status )
    {
        printf("SegArb_ExB Error: Ch1 segarb sequence status= %d", status);
        FreeArrays_SegArbExB();
        return status;
    }
               
    status = seg_arb_sequence(InstId,  2, 1,  NumSegments, StartVCh2, StopVCh2, SegTime, (long *)SegTrigOut, (long *)SSRCtrlCh2, PulseMeasType, MeasStart, MeasStop);
    if ( status )
    {
        printf("SegArb_ExB Error: Ch2 segarb sequence status= %d", status);
        FreeArrays_SegArbExB();
        return status;
    }
    
    //Program Segment Arb Waveform (1 per channel)
    status = seg_arb_waveform(InstId, 1, 1, SeqList, LoopCountList);
    if ( status )
    {
        printf("SegArb_ExB Error: Ch1 segarb waveform status= %d", status);
        FreeArrays_SegArbExB();
        return status;
    }

    status = seg_arb_waveform(InstId, 2, 1, SeqList, LoopCountList);
    if ( status )
    {
        printf("SegArb_ExB Error: Ch2 segarb waveform status= %d", status);
        FreeArrays_SegArbExB();
        return status;
    }

    //Turn on outputs    
    status = pulse_output(InstId, 1, 1);
    if ( status )
    {
        FreeArrays_SegArbExB();        
        return status ;
    }

    status = pulse_output(InstId, 2, 1);
    if ( status )
    {
        FreeArrays_SegArbExB();        
        return status ;
    }

    if (verbose)
        printf("SegArb_ExB:  Just before pulse_exec");

    //Run test:  output Segment Arb waveform while measuring
    status = pulse_exec(PULSE_MODE_SIMPLE);
    if ( status )
    {
        printf("SegArb_ExB Error: attempting to run pulse_exec, status= %d", status);
        FreeArrays_SegArbExB();        
        return status ;
    }

    if (verbose)
        printf("SegArb_ExB:  Just after pulse_exec");

    if ( status )
           return status;
        while ( pulse_exec_status(&t) == 1 )
        {
            Sleep(100);
        }

    if ( SMUPresent )
    {
        if ( verbose )
            printf("SegArb_ExB: SMU present, setting voltage = 0");

        status = forcev(SMUId, 0);
        if ( status )
        {
            FreeArrays_SegArbExB();        
            return status ;
        }
    }

    FreeArrays_SegArbExB();
    return 0;
}

void AllocateArrays_SegArbExB(int NumberofSegments)
{
    //Allocate arrays for Segment Arb: trigger, measure type, measure start, measure stop.  
    PulseMeasType = (long *)calloc(NumberofSegments, sizeof(long));
    MeasStart = (double *)calloc(NumberofSegments, sizeof(double));
    MeasStop = (double *)calloc(NumberofSegments, sizeof(double));

}
void FreeArrays_SegArbExB()
{
    //Free memory for arrays before exiting UTM
    if (PulseMeasType != NULL)
        free(PulseMeasType);
    if (MeasStart != NULL)
        free(MeasStart);
    if (MeasStop != NULL)
        free(MeasStop);

/* USRLIB MODULE END  */
} 		/* End PMU_SegArb_ExampleB.c */

