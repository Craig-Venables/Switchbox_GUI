/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_1Chan_Waveform_Example
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 29
	ARGUMENTS:
		width,	double,	Input,	500e-9,	40e-9,	.999999
		rise,	double,	Input,	100e-9,	20e-9,	.033
		fall,	double,	Input,	100e-9,	20e-9,	.033
		delay,	double,	Input,	0.0,	0,	.999999
		period,	double,	Input,	1e-6,	120e-9,	1
		voltsSourceRng,	double,	Input,	10,	5,	40
		currentMeasureRng,	double,	Input,	.01,	100e-9,	.8
		DUTRes,	double,	Input,	1E6,	1,	10e6
		startV,	double,	Input,	0,	-40,	40
		stopV,	double,	Input,	5,	-40,	40
		stepV,	double,	Input,	1,	-40,	40
		baseV,	double,	Input,	0,	-40,	
		acqType,	int,	Input,	1,	0,	1
		LLEComp,	int,	Input,	0,	0,	1
		preDataPct,	double,	Input,	.2,	0,	1.0
		postDataPct,	double,	Input,	.2,	0,	1.0
		pulseAvgCnt,	int,	Input,	1,	1,	10000
		SampleRate,	double,	Input,	200e6,	1,	200e6
		PMUMode,	int,	Input,	0,	0,	1
		chan,	int,	Input,	1,	1,	2
		PMU_ID,	char *,	Input,	"PMU1",	,	
		V_Meas,	D_ARRAY_T,	Output,	,	,	
		size_V_Meas,	int,	Input,	3000,	100,	32767
		I_Meas,	D_ARRAY_T,	Output,	,	,	
		size_I_Meas,	int,	Input,	3000,	100,	32767
		T_Stamp,	D_ARRAY_T,	Output,	,	,	
		size_T_Stamp,	int,	Input,	3000,	100,	32767
		Status,	I_ARRAY_T,	Output,	,	,	
		size_Status,	int,	Input,	3000,	100,	32767
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: PMU_1Chan_Waveform_Example
==================================

Description
-----------

Voltage amplitude Pulse IV waveform capture using one channel of the 4225-PMU. 

It returns voltage and current samples versus time for a single channel.

The module will capture a sweep of pulses, or a single pulse. For a single pulse, 
set startV = stopV with stepV = 0. Only fixed current measure ranging is 
supported.

The purpose of this module is a functional programming reference to illustrate 
the basic commands necessary to perform a 1 channel Pulse IV (2-level pulse) 
sweep with waveform capture.

This routine uses a different method to get the data from the PMU card into 
the Clarius sheet: pulse_measrt. pulse_measrt() command allows the data to go 
directly from the card to the Clarius sheet, without the need to pull the data 
into the UTM before re-sending to the sheet.  This simplifies the UTM code 
and reduces the time required to get lots of data from the card to the sheet, 
which is most beneficial when retrieving PMU waveform data.  The pulse_measrt()
command is not compatible with KXCI.

~~~~
               _____________             _
              /  PulseTop   \            |
             /               \           |
            /<--PulseWidth--->\  startV, stopV, stepV
           /                   \         |
  ________/                     \________|________baseV
  Delay     Rise           Fall 
  |<---------------Period------------------------>|
~~~~

This module does not provide spot means.

Note: Choose a SampleRate that does not require more than the array size of the
returned measurements (parameters: (V_Meas, I_Meas, T_stamp). See descriptions 
below for additional information.

Inputs
------

width
: (double) The width of the pulse.
: 10V Range: 60 ns to 999.999 ms
: 40V Range: 140 ns to 999.999 ms

rise
: (double) Rise time of the pulse, 0 to 100%
: 10V Range:  20 ns to 33 ms (at maximum amplitude)
: 40V Range:  100 ns to 33 ms (at maximum amplitude)

fall
: (double) Fall time of the pulse, 0 to 100%
: 10V Range:  20 ns to 33 ms (at maximum amplitude)
: 40V Range:  100 ns to 33 ms (at maximum amplitude)

delay	
: (double) Time before pulse rise time (see diagram above). 
: Range:  10 ns to 999 ms

period			
: (double) Pulse Period (see diagram).
: 10V Range: 120 ns to 1 s
: 40V Range: 280 ns (40V) to 1 s

voltsSourceRng		
: (int) Pulse voltage source range. The maximum voltage of the
			range is available into a high impedance only (1 M&Omega;)
: Range: 10, 40

currentMeasureRng	
: (int) PMU current measure range. Available I measure 
			ranges are specific to the PMU voltage source range and 
			the presence of a connected 4225-RPM:                                                          																	
: PMU 10V:  0.01, 0.2
: PMU 40V:  100e-6, 0.01, 0.8
: RPM 10V:  100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

DUTRes
: Resistance of DUT connected to the specified channel (&Omega;). 
			This value is only used when LLE Comp is disabled (LLEComp 
			= 0). Set the DUTResCh1 to match the resistance of the DUT.
			Setting this value to represent the actual DUT impedance will 
			greatly reduce the difference between the programmed voltage
			and the voltage at the DUT due to load line effects. This 
			parameter is not meaningful when using a 4225-RPM current 
			measure range 1 mA or lower.
: Range: 1 to 1e6 &Omega;

startV			
: (double) Starting voltage for the sweep.

stopV 			
: (double) Final voltage for the sweep.

stepV		
: (double) Voltage Step size for the sweep.  For a single step
				(no sweep), set startV = stopV and stepV = 0.

baseV			
: (double) The base voltage of the pulse (see diagram above).

acqType 
: (int) User selection to indicate the measurement data return type:
: 0: Discrete samples
: 1: Average

LLEComp		
: Load Line effect Compensation enabled or disabled. LLE 
		compensation compensates for the voltage drop of the 50 &Omega; 
		output of the PMU channel due to current flowing through the 
		Device Under Test (DUT). Enabling the LLE compensation increases 
		test time, but provides the desired sweep voltage at the DUT.
		To enable LLE compensation, set this parameter and PMUMode = 1.
: 1: Enabled
: 0: Disabled

preDataPct 		
: (double)Specifies how many additional samples are captured
			before the pulse rise time, as a percentage of the total pulse
			time (0.5 * rise + width + 0.5 * fall).
: 0 is 0%. 1.0 is 100%. 0.5 is 50%. Typical is 0.2 (20%).

postDataPct 	
: (double)Specifies how many additional samples are captured
			after the pulse fall time, as a percentage of the total pulse
			time (0.5 * rise + width + 0.5 * fall).
: 0 is 0%.  1.0 is 100%.  0.5 is 50%. Typical is 0.2 (20%).

pulseAvgCnt 	
: (int) The number of pulse periods/bursts sourced and 
				measured.

SampleRate
: (double) PMU A/D Sample Rate (1000 Sa/s to 200E6 Sa/s)

PMUMode			
: (int) PMU Test Execution mode. Controls test execution. If
			auto-ranging, Load Line Effect compensation or thresholds (volt,
			current, power) are needed, then set PMUMode = 1, otherwise
			use PMUMode = 0. Note that Mode = 0 will result in shorter
			test times, but allows fixed current ranges and no LLE comp
			and no IVP threshold comparisons.
: 0: Simple
: 1: Advanced

chan 			
: (int) The PMU channel number to use.

PMU_ID 		
: (char *) The string Id that specifies the PMU.
			Example: PMU1

Outputs
-------
Output measurement values for the channels in question:

* V_Meas
* I_Meas
* T_Stamp
* Status - This argument is no longer supported. No data will be returned.

Return values
-------------
			 
Value  | Description
------ | -----------
0	   | OK.
-122   | Illegal value for parameter.
	   | example: pulse_ranges(): Illegal value for parameter #7. Ensure that 
       | current measure range is appropriate for the chosen voltage range.
-824   | pulse_exec(): Invalid pulse timing parameters. One or more timing parameters
       | (PulseWidthCh1, RiseTimeCh1, FallTimeCh1, DelayCh1 or Period) are too small for the chosen VRangeCh1.
	   | Increase the time of the appropriate parameters.
-829   | pulse_sweep_linear(): The sum of base and amplitude voltages (XX.XV)
       | exceeds maximum (YYV) for present range. The Base + Amplitude voltage is too large
       | for the chosen PMU voltage range. Check the BaseVCh1, StartVCh1 and StopVCh1 for
       | voltages that exceed VRangeCh1. If necessary, increase VRangeCh1 to the maximum 40V range.
-831   | Exceeded maximum number of samples per channel. Decrease SampleRate or number of waveforms for the test.
-835   | Using the specified sample rate, some pulse timing parameters are too short for a measurement.
       | Increase the value of SampleRate parameter.
-844   | Invalid Start, Stop, or Step Value entered.
       | For single pulse, make sure Start = Stop and Step = 0. 
-17001 | Wrong card Id. Check PMU and SMU names.
-17002 | Failure to assign card Id handle. Check PMU and/or SMU names.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);

int PMU_1Chan_Waveform_Example( double width, double rise, double fall, double delay, double period, double voltsSourceRng, double currentMeasureRng, double DUTRes, double startV, double stopV, double stepV, double baseV, int acqType, int LLEComp, double preDataPct, double postDataPct, int pulseAvgCnt, double SampleRate, int PMUMode, int chan, char *PMU_ID, double *V_Meas, int size_V_Meas, double *I_Meas, int size_I_Meas, double *T_Stamp, int size_T_Stamp, int *Status, int size_Status )
{
/* USRLIB MODULE CODE */
    double t;
    int status; 
    int pulserId;
    int TestMode;
    int modStatus = 0;
    int startIndex = 0;
    int returnValCount = 0;
    int sweepType = PULSE_AMPLITUDE_SP;
    int verbose = 0;
    double dSweeps;
    double pointsPerWfm;
	double DIFF = 1.0e-9;

//    verbose = 1;        //print out status messages to Message Console (type msgcon at command prompt)

    if ( !LPTIsInCurrentConfiguration(PMU_ID) )
    {
        printf("Instrument %s is not in system configuration", PMU_ID);
        return ERR_PMU_EXAMPLES_WRONGCARDID;
    }

    getinstid(PMU_ID, &pulserId);
    if ( -1 == pulserId )
        return ERR_PMU_EXAMPLES_CARDHANDLEFAIL;

	//Support the single pulse (when stopV == startV and stepV == 0.0)
    //Verify total number of points for whole test (should be less than 65536)
	//	First check if the single pulse is setup to run
	if (fabs(stopV - startV) < DIFF)
	{
		if (stepV == 0.0)
		{
			dSweeps = 1;
		}
		else
		{
			return PMU_INVALID_START_STEP_STEP;
		}
	}
	else
	{
		if (stepV == 0)
		{
			return PMU_INVALID_START_STEP_STEP;
		}
		dSweeps = (fabs((stopV - startV) / stepV) + 0.5) + 1;
		if (dSweeps > 65536)
		{
			return PMU_MAX_SAMPLES_ERROR;
		}
		pointsPerWfm = period * SampleRate + 1;
		if (pointsPerWfm*dSweeps > 65536)
		{
			return PMU_MAX_SAMPLES_ERROR;
		}
	}

    //Ensure that 4225-RPMs (if attached) are in the pulse mode
    status = rpm_config(pulserId, chan, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
       return status;

    //Put card into pulse mode
    status = pg2_init(pulserId, PULSE_MODE_PULSE);
    if ( status )
        return status;

    //Set PMU to return actual values when measurement overflow occurs
    status = setmode(pulserId, KI_LIM_MODE, KI_VALUE);
    if ( status )
        return status;

    //Set PMU source and measure ranges
    status = pulse_ranges(pulserId, chan, voltsSourceRng, PULSE_MEAS_FIXED, voltsSourceRng, PULSE_MEAS_FIXED, currentMeasureRng);
    if ( status )
        return status;

    if ( verbose )
        printf("1chan_waveform: Chan= %d, delay= %g, period= %g, PW= %g, Rise= %g", chan, delay, period, width, rise);

    status = pulse_source_timing(pulserId, chan, period, delay, width, rise, fall);
    if ( status )
        return status;

    status = pulse_limits(pulserId, chan, voltsSourceRng, currentMeasureRng, voltsSourceRng*currentMeasureRng);
    if ( status )
        return status;

    status = pulse_sample_rate(pulserId, SampleRate);
    if ( status )
        return status;

    if (!LLEComp || !PMUMode)
    {
        status = pulse_load(pulserId, chan, DUTRes);
        if ( status )
            return status;
    }

    //Set pulse_vhigh(), which is necessary if sweepType = PULSE_BASE_SP
    status = pulse_vhigh(pulserId, chan, startV);
    if ( status )
        return status;

    //Set pulse_vlow(), which is necessary if sweepType = PULSE_AMPLITUDE_SP
    status = pulse_vlow(pulserId, chan, baseV);
    if ( status )
        return status;

    status = pulse_sweep_linear(pulserId, chan, sweepType, startV, stopV, stepV);
    if ( status )
        return status;

    status = pulse_meas_wfm(pulserId, chan, acqType, TRUE, TRUE, TRUE, LLEComp);
    if ( status )
        return status;

    //Set values for extra data before pulse rise time and after pulse fall time
    status = pulse_meas_timing(pulserId, chan, preDataPct, postDataPct, pulseAvgCnt);
    if ( status )
        return status;

    //Set Array names so that data can be automatically returned to the Clarius data sheet
    //NOTE:  pulse_measrt() is not compatible with KXCI UL mode
    status = pulse_measrt(pulserId, chan, "V_Meas", "I_Meas", "T_Stamp", NULL);
    if ( status )
       return status ;
        
    // Turn on the pulser output.
    status = pulse_output(pulserId, chan, 1);
    if ( status )
        return status;

    //Set test execute mode to Simple or Advanced
    if (PMUMode ==0)
        TestMode = PULSE_MODE_SIMPLE;
    else
        TestMode = PULSE_MODE_ADVANCED;

    //Run the test
    status = pulse_exec(TestMode);
    if (status)
        return status;

    //Wait until test is complete
    while ( pulse_exec_status(&t) == 1 )
        Sleep(100);

    return 0;
/* USRLIB MODULE END  */
} 		/* End PMU_1Chan_Waveform_Example.c */

