/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_SMU_Sweep_Example
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 69
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
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
#define MaxSamplesPerAtoD 1000000
#define PulseAndSMUMode 0
#define PulseOnlyMode 1
#define SMUOnlyMode 2
extern void cleanUp( double *, double *, double *, double *,
              double *, double *, double *, double *, 
              double *, double *, double *, double *);
#pragma warning( disable: 4996 )
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

MODULE: PMU_SMU_Sweep_Example
=============================

Description
-----------

PMU_SMU_Sweep_Example is an example of How to use the PMU with a SMU. For example,
you could use this module to compare performing a test using a PMU to performing
that test with a SMU. This user module is based on the module "PMU_IV_Sweep_Example".

This example supports the 4225-RPM to perform switching or using the on-board 
relays of the SMUs.

How to use
----------
A voltage amplitude Pulse IV sweep is first performed using both channels of a 
single 4225-PMU card. Channel 1 outputs a pulse train of constant amplitude, 
while Channel 2 is swept.

Similarly, one SMU is used to provide a constant DC bias, while a second SMU is 
swept.

This module allows the user to perform only the Pulse IV test, or only the DC
test, or both. If both tests are performed, they are performed sequentially 
(first the Pulse IV, then the DC test).

This module can use either the on-card output relays or the RPMs (if present)
relays. This allows the 4225-PMU and the SMU to be connected simultaneously 
to the the DUT using a SMA T connector. The connectors required to use this 
module with the SMU and PMU connected together are in the 4200-PMU-PROBER-KIT.

If RPMs are present, this module will use the RPM to switch between the PMU 
and SMUs.

Before the Pulse IV test is performed, the output relay of the SMU is opened, 
or the RPM is switched to pulse mode in order to prevent the impedance of the SMU
from affecting the Pulse output. Similarly, before the DC test is performed, 
the output relay of the PMU is opened or the RPM (if present) is switched to 
SMU mode.

This routine allows for independent pulse width, rise, fall and delay 
parameters to be set for the 2 channels. Note that the period is the same 
for both channels. The measurement window is also the same for both channels 
and is set by the internal variables MeasStartPercCh1 and MeasStopPercCh1. 

By definition, the measure window for the spot mean will be within the pulse 
top of the gate, but this routine also checks to ensure that the spot mean is 
 within the pulse top of the drain. If the spot mean for the gate pulse 
top is not within the drain pulse top, an error will result. To fix the error,
adjust the timing parameters for the drain so that there is some overlap (in time)
between the gate and drain pulse tops.

The sample rate is automatically chosen to ensure that the maximum number of 
samples (stored on the card during the test) does not exceed 1,000,000 per 
A/D (4 A/Ds per card, for I & V on each of the 2 channels).

This uses Ch1 and Ch2. Ch1 is always the fixed amplitude sweep or constant 
DC bias terminal, and Ch2 is always the variable amplitude sweep (pulse or DC) 
terminal.

This routine is not compatible with KXCI (UL mode).

Note: The purpose of this module is to serve as a functional programming example to 
illustrate the basic commands or techniques necessary to perform a 1 channel 
2-level sweep with a DC test.


Illustration
------------
~~~~
                     (pulse top) 
                       +----+ -      +----+
                       |    | ^      |    |
                       |    | |      |    |
                       |    |(ampl)  |    |
              (pulse   |    | |      |    |
               base)   |    | v      |    |
      (base V)---------+    +---...--+    +--...--
~~~~

LLEC: Load Line Effect Compensation

Inputs
------

PulseWidthCh1	
: (double) Pulse width for channel 1.  
: Range: 60e-9 to 0.999999

RiseTimeCh1
: (double) Rise time for channel 1. 
: Range: 20e-9 to 0.033

FallTimeCh1	
: (double) Fall time for channel 1. 
: Range: 20e-9 to 0.033

DelayCh1	
: (double) Pulse delay for channel 1. 
: Range: 0 to 0.999999

PulseWidthCh2
: (double) Pulse width for channel 2. 
: Range: 60e-9 to 0.999999

RiseTimeCh2	
: (double) Rise time for channel 2. 
: Range: 20e-9 to 0.033

FallTimeCh2	
: (double) Fall time for channel 2. 
: Range: 20e-9 to 0.033

DelayCh2
: (double) Pulse delay for channel 2. 
: Range: 0 to 0.999999

Period
: (double) Pulse period (both channels). 
: Range: 80e-9 to 1

PulseAverage	
: (int) Number of pulses to average. 
: Range: 1 to 10000

LoadLineCh1	
: (int) PMU Load Line Effect Compensation for channel 1:
: 1: On
: 0: Off

LoadLineCh2
: (int) PMU Load Line Effect Compensation for channel 2:
: 1: On
: 0: Off

ResCh1		
: (double) Expected DUT resistance for channel 1.
           Value is used to determine correct output voltage if LLEC is turned off.
: Range: 1 to 1e6

ResCh2  
: (double) Expected DUT resistance for channel 1.
           Value is used to determine correct output voltage if LLEC is turned off. 
: Range: 1 to 1e6

AmplVCh1
: (double) Voltage amplitude (pulse height) for channel 1.
: Range: -40 to 40

BaseVCh1	
: (double) Pulse Base voltage for channel 1.
: Range: -40 to 40

StartVCh2
: (double) Starting pulse voltage amplitude for channel 2 pulse sweep. 
: Range: -40 to 40

StopVCh2	
: (double) Ending pulse voltage amplitude for channel 2 pulse sweep. 
: Range: -40 to 40

StepVCh2	
: (double) Pulse voltage amplitude step for channel 2 pulse sweep. 
: Range: 0.001 to 40

BaseVCh2	
: (double) Pulse base voltage for channel 2. Although channel 2 is swept, this value is fixed. 
: Range: -40 to 40

VRangeCh1
: (double) PMU voltage range for channel 1.
: Range: 5 to 40

IRangeCh1	
: (double) PMU current measure range for channel 1. 
: Range: 1e-6 to 0.8

LtdAutoCurrCh1
: (double) Limited current measurement ranging for PMU channel 1: 
: 1: On
: 0: Off

VRangeCh2	
: (double) PMU voltage range for channel 2. 
: Range: 10 or 40

IRangeCh2	
: (double) PMU current measurement range for channel 2.
: Range: 1e-6 to 0.8

LtdAutoCurrCh2	
: (double) Limited current measurement ranging for PMU channel 2:
: 1: On
: 0: Off

PMUMode
: (int) PMU Execution mode. Controls PMU execution mode.
        If you need autoranging, Load Line Effect compensation or thresholds (volt, current, power),
		set PMUMode = 1 (advanced mode), otherwise use PMUMode = 0 (simple mode).
		Note that PMUMode = 0 will result in shorter test times, but allows fixed
		current ranges and no LLE compensation and no IVP threshold comparisons. 
: 0: Simple
: 1: Advanced

SMU_Irange
: (double) SMU current range. 
: Ranges: 1e-9, 10e-9, 100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 10e-3, 100e-3, 1
: Note: 1e-9 and 10e-9 requires SMU Preamp and 1 A range only available on high power SMU.

SMU_Icomp 
: (double) SMU current compliance for Ch1SMU. This value must be > 10% of the above current range.

Ch1SMU_ID	
: Channel 1 SMU instrument name, such as "SMU1" (without quotes).
  Note that the SMU cannot be connected to an RPM, or a -233 error
  ("forcev(): Cannot force when not connected") will occur and the test will not run.
: Range: SMU1, SMU2, up to maximum SMUs in system.

Ch2SMU_ID
: Channel 2 SMU instrument name, such as "SMU2" (without quotes).
  Note that the SMU cannot be connected to an RPM, or a -233 error
  ("forcev(): Cannot force when not connected") will occur and the test will not run.
: Range: SMU1, SMU2, up to maximum SMUs in system.

PMU_ID
: PMU instrument name, such as "PMU1" (without quotes).
: Range:  PMU1 thru PMU4.

ExecMode
: (int) Execution mode:
: 0: Pulse & SMU test: Perform both Pulse I-V and DC test.
: 1: Pulse I-V Test only: Perform only the Pulse I-V test.
: 2: DC SMU Test only: Perform only the DC test.

Ch1_V_Ampl_Size
: (int) The sizes of the results.

The following inputs are arrays. These arrays must be all the same size and must
be large enough to accommodate all of the measurements.
The range for the arrays is 1 to 10000.
: Ch1_I_Ampl_Size  
: Ch1_V_Base_Size  
: Ch1_I_Base_Size  
: Ch2_V_Ampl_Size  
: Ch2_I_Ampl_Size 
: Ch2_V_Base_Size
: Ch2_I_Base_Size
: TimeStampAmpl_Ch1_Size
: TimeStampBase_Ch1_Size
: TimeStampAmpl_Ch2_Size
: TimeStampBase_Ch2_Size
: Status_Ch1_Size
: Status_Ch2_Size
: Ch2SMUVoltageSize
: Ch2SMUCurrentSize
: Ch1SMUVoltageSize
: Ch1SMUCurrentSize

Outputs
-------

Ch1_V_Ampl
: (double array) Measured pulse voltage amplitude (top) for channel 1.	

Ch1_I_Ampl
: (double array) Measured pulse current amplitude (top) for channel 1. 	

Ch1_V_Base
: (double array) Measured pulse base (bottom) voltage for channel 1.	

Ch1_I_Base
: (double array) Measured pulse base (bottom) current for channel 1.	

Ch2_V_Ampl	
: (double array) Measured pulse voltage amplitude (top) for channel 1.	

Ch2_I_Ampl
: (double array) Measured pulse current amplitude (top) for channel 2.	

Ch2_V_Base	
: (double array) Measured pulse base (bottom) voltage for channel 2.	

Ch2_I_Base	
: (double array) Measured pulse base (bottom) current for channel 2.	


TimeStampAmpl_Ch1  
TimeStampBase_Ch1
TimeStampAmpl_Ch2
TimeStampBase_Ch2	
: (double array) Timestamp for each pulse measurement.

Status_Ch1
: This argument is no longer supported. No data will be returned.

Status_Ch2
: This argument is no longer supported. No data will be returned.

Ch2_SMU_Voltage
: (double array) Measured DC voltage for channel 2. 	

Ch2_SMU_Current	 
: (double array) Measured DC current for channel 2.	

Ch1_SMU_Voltage
: (double array) Measured DC voltage for channel 1.

Ch1_SMU_Current	
: (double array) Measured DC current for channel 1.


Return values
-------------
			 
Value  | Description
------ | -----------
0      | OK.
-99    | Invalid Execution Mode.
-122   | pulse_ranges(): Illegal value for parameter #7.
       | Ensure that current measure range is appropriate for the chosen voltage range.
-233   | Cannot force when not connected. Ensure that specified SMU is not connected
       | through or associated with an RPM. If all SMUs are associated with RPM modules,
       | choose NONE to permit the test to run.
-829   | pulse_sweep_linear(): The sum of base and amplitude voltages (XX.XV) exceeds
       | maximum (YYV) for present range. The Base + Amplitude voltage is too large for
       | the chosen PMU voltage range. Check the BaseVCh1, StartVCh1 and StopVCh1 for
       | voltages that exceed VRangeCh1. If necessary, increase VRangeCh1 to the maximum 40V range.
-824   | pulse_exec(): Invalid pulse timing parameters. One or more timing parameters
       |(PulseWidthCh1, RiseTimeCh1, FallTimeCh1, DelayCh1 or Period) are too small
       | for the chosen VRangeCh1. Increase the time of the appropriate parameters.
-17001 | Wrong card Id. Check PMU and SMU names.
-17002 | Failure to assign card ID handle. Check PMU and/or SMU names.
-17100 | Gate Measure window outside of Drain Pulse top. Adjust gate measure window,
       | gate pulse timing, or drain pulse timing.
-17110 | Output array sizes are less than number of points in sweep.
	   | Increase output array sizes or decrease number of points in sweep.
< 0    | Various 4225-PMU Errors. See reference manual for more information.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
#define MaxSamplesPerAtoD 1000000
#define PulseAndSMUMode 0
#define PulseOnlyMode 1
#define SMUOnlyMode 2
extern void cleanUp( double *, double *, double *, double *,
              double *, double *, double *, double *, 
              double *, double *, double *, double *);
#pragma warning( disable: 4996 )

int PMU_SMU_Sweep_Example( double PulseWidthCh1, double RiseTimeCh1, double FallTimeCh1, double DelayCh1, double PulseWidthCh2, double RiseTimeCh2, double FallTimeCh2, double DelayCh2, double Period, int PulseAverage, int LoadLineCh1, int LoadLineCh2, double ResCh1, double ResCh2, double AmplVCh1, double BaseVCh1, double StartVCh2, double StopVCh2, double StepVCh2, double BaseVCh2, double VRangeCh1, double IRangeCh1, double LtdAutoCurrCh1, double VRangeCh2, double IRangeCh2, double LtdAutoCurrCh2, int PMUMode, double SMU_Irange, double SMU_Icomp, char *Ch1SMU_ID, char *Ch2SMU_ID, char *PMU_ID, int ExecMode, double *Ch1_V_Ampl, int Ch1_V_Ampl_Size, double *Ch1_I_Ampl, int Ch1_I_Ampl_Size, double *Ch1_V_Base, int Ch1_V_Base_Size, double *Ch1_I_Base, int Ch1_I_Base_Size, double *Ch2_V_Ampl, int Ch2_V_Ampl_Size, double *Ch2_I_Ampl, int Ch2_I_Ampl_Size, double *Ch2_V_Base, int Ch2_V_Base_Size, double *Ch2_I_Base, int Ch2_I_Base_Size, double *TimeStampAmpl_Ch1, int TimeStampAmpl_Ch1_Size, double *TimeStampBase_Ch1, int TimeStampBase_Ch1_Size, double *TimeStampAmpl_Ch2, int TimeStampAmpl_Ch2_Size, double *TimeStampBase_Ch2, int TimeStampBase_Ch2_Size, double *Status_Ch1, int Status_Ch1_Size, double *Status_Ch2, int Status_Ch2_Size, double *Ch2_SMU_Voltage, int Ch2SMUVoltageSize, double *Ch2_SMU_Current, int Ch2SMUCurrentSize, double *Ch1_SMU_Voltage, int Ch1SMUVoltageSize, double *Ch1_SMU_Current, int Ch1SMUCurrentSize )
{
/* USRLIB MODULE CODE */
    int status;
    int i;
    int NumSweepPts;
    int NumSamplesTopCh1; 
    int NumSamplesBaseCh1;
    int NumSamplesPeriodCh1;
    int NumSamplesSweepCh1;
    int NumTotalSamples;
    int InstId;
    int Ch1SMUId;
    int Ch2SMUId;
    int TestMode;
    int Stat;
    int CardChannel1 = 1;
    int CardChannel2 = 2;
    int ExecStatus = 0;
    int RPMstat1, RPMstat2;
    
    char ErrMsgChar[100];
    
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
    
    boolean SMUPresent; 
    boolean RPMPresent = FALSE;
    boolean verbose = FALSE;        // Print out status messages to Message
                                    // Console (type msgcon at command prompt)
    boolean memAllocated = FALSE;   // Memory allocated flag
        

    //Initialize variables
    SampleRate = 200E+6;
    RateFactor = 0.0;
    SMUPresent = FALSE;    

    if ( verbose )
        printf("PMU_SMU_Sweep_example: ======== New run =====");

    //Check: is requested PMU card in the chassis?
    if ( !LPTIsInCurrentConfiguration(PMU_ID) )
    {
        printf("Instrument %s is not in system configuration", PMU_ID);
        return ERR_PMU_EXAMPLES_WRONGCARDID;
    }

    //Convert card string into identifying instrument card number
    getinstid(PMU_ID, &InstId);
    if ( -1 == InstId )
    {
        return ERR_PMU_EXAMPLES_WRONGCARDID;
    }

    //Calculate the number of sweep points on the drain
    NumSweepPts = (int)(fabs((StopVCh2 - StartVCh2) / StepVCh2) + 1);

    //Determine if return array sizes are big enough to contain
    //the desired number of sweep points (NumSweepPts)
    if (NumSweepPts > Ch1_V_Ampl_Size || NumSweepPts > Ch1_I_Ampl_Size || NumSweepPts > Ch1_V_Base_Size || NumSweepPts > Ch1_I_Base_Size ||
        NumSweepPts > Ch2_V_Ampl_Size || NumSweepPts > Ch2_I_Ampl_Size || NumSweepPts > Ch2_V_Base_Size || NumSweepPts > Ch2_I_Base_Size ||
        NumSweepPts > TimeStampAmpl_Ch1_Size || NumSweepPts > TimeStampBase_Ch1_Size || NumSweepPts > TimeStampAmpl_Ch2_Size || NumSweepPts > TimeStampBase_Ch2_Size ||
        NumSweepPts > Status_Ch1_Size || NumSweepPts > Status_Ch2_Size || NumSweepPts > Ch2_V_Base_Size || NumSweepPts > Ch2_I_Base_Size ||
        NumSweepPts > Ch1SMUVoltageSize || NumSweepPts > Ch2SMUVoltageSize || NumSweepPts > Ch1SMUCurrentSize || NumSweepPts > Ch2SMUCurrentSize)
    {
        if (verbose)
            printf("PMU_IV_sweep_Example: One or more Output array size(s) < number of sweep points. Increase size of all Output arrays to be at least %d", NumSweepPts);
        return ERR_PMU_EXAMPLES_OUTPUT_ARRAY_TOO_SMALL;
    }

    // Check to see if RPMs are present. Since cannot query the 4200
    // for the presence of RPMs, try setting the current measure range
    // to a level only the RPM should have. Lack of an error indicates
    // the presence of RPMs.
    status = pg2_init(InstId, PULSE_MODE_PULSE);
    Stat = rpm_config(InstId, CardChannel1, KI_RPM_PATHWAY, KI_RPM_PULSE);
    Stat = rpm_config(InstId, CardChannel2, KI_RPM_PATHWAY, KI_RPM_PULSE);
    RPMstat1 = pulse_ranges(InstId, CardChannel1, 10.0, PULSE_MEAS_FIXED, 10.0, PULSE_MEAS_FIXED, 100e-6);
    RPMstat2 = pulse_ranges(InstId, CardChannel2, 10, PULSE_MEAS_FIXED, 10, PULSE_MEAS_FIXED, 100e-6);
    if (RPMstat1 >= 0 && RPMstat2 >= 0) RPMPresent = TRUE;

    if (verbose )
    {
        if (RPMPresent) printf("PMU_SMU_Sweep_Examples: using RPM switching.\n");
    }


    // Size arrays for all returned measurements based on required
    // number of points, assume both high and low measurements are enabled
    Ch1_V_All = (double *)calloc(NumSweepPts*2+1, sizeof(double));
    Ch1_I_All = (double *)calloc(NumSweepPts*2+1, sizeof(double));
    Ch1_T_All = (double *)calloc(NumSweepPts*2+1, sizeof(double));    
    Ch1_S_All = (unsigned long *)calloc(NumSweepPts*2+1, sizeof(unsigned long));    
    Ch2_V_All = (double *)calloc(NumSweepPts*2+1, sizeof(double));
    Ch2_I_All = (double *)calloc(NumSweepPts*2+1, sizeof(double));
    Ch2_T_All = (double *)calloc(NumSweepPts*2+1, sizeof(double));    
    Ch2_S_All = (unsigned long *)calloc(NumSweepPts*2+1, sizeof(unsigned long));    


    // Size arrays for individual pulse amplitude (High) and pulse base (Low)
    // readings, based on required number of points
    Ch1_V_High = (double *)calloc(NumSweepPts+1, sizeof(double));
    Ch1_I_High = (double *)calloc(NumSweepPts+1, sizeof(double));
    Ch1_V_Low = (double *)calloc(NumSweepPts+1, sizeof(double));
    Ch1_I_Low = (double *)calloc(NumSweepPts+1, sizeof(double));
    Ch1_T_High = (double *)calloc(NumSweepPts+1, sizeof(double));    
    Ch1_T_Low = (double *)calloc(NumSweepPts+1, sizeof(double));    
    Ch2_V_High = (double *)calloc(NumSweepPts+1, sizeof(double));
    Ch2_I_High = (double *)calloc(NumSweepPts+1, sizeof(double));
    Ch2_V_Low = (double *)calloc(NumSweepPts+1, sizeof(double));
    Ch2_I_Low = (double *)calloc(NumSweepPts+1, sizeof(double));
    Ch2_T_High = (double *)calloc(NumSweepPts+1, sizeof(double));    
    Ch2_T_Low = (double *)calloc(NumSweepPts+1, sizeof(double));    
    memAllocated = TRUE;

    // Initialize everyone to DBL_NAN so that we don't screw
    // up the plots in case a mode other than PulseAndSMUMode
    // is chosen
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
        if ( !LPTIsInCurrentConfiguration(Ch1SMU_ID) )
        {
            printf("PMU_SMU_Sweep_Example: Instrument %s is not in the system configuration", Ch1SMU_ID);
            if (memAllocated)
            {
                cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                        Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                        Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
            }
            return ERR_PMU_EXAMPLES_WRONGCARDID;
        }

        if ( !LPTIsInCurrentConfiguration(Ch2SMU_ID) )
        {
            printf("PMU_SMU_Sweep_Example: Instrument %s is not in system configuration", Ch2SMU_ID);
            if (memAllocated)
            {
                cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                        Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                        Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
            }

            return ERR_PMU_EXAMPLES_WRONGCARDID;
        }
        // Convert SMU card string into identifying instrument card number
        getinstid(Ch1SMU_ID, &Ch1SMUId);
        getinstid(Ch2SMU_ID, &Ch2SMUId);

        if ( -1 == Ch1SMUId || -1 == Ch2SMUId)
        {
            if (memAllocated)
            {
                cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                        Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                        Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
            }
            return -2;
        } else {            
            SMUPresent = TRUE;
        }

// Open the SMU output relays BEFORE starting the pulse test.
    if (!RPMPresent)
    {
       if (verbose ) printf("PMU_SMU_Sweep_Example: using SMU relays - pulse\n");
       Stat = setmode(Ch1SMUId, KI_SHIELD_RELAY_STATE, 0);
       Stat = setmode(Ch2SMUId, KI_SHIELD_RELAY_STATE, 0);
    } else {
       if (verbose ) printf("PMU_SMU_Sweep_Example: using RPM relays - pulse\n");
       Stat = rpm_config(InstId, CardChannel1, KI_RPM_PATHWAY, KI_RPM_PULSE);
       Stat = rpm_config(InstId, CardChannel2, KI_RPM_PATHWAY, KI_RPM_PULSE);
    }
    
    if ( verbose )
        printf("PMU_SMU_Sweep_Example: ExecMode is %i\n", ExecMode);
    
if ( ExecMode == PulseOnlyMode || ExecMode == PulseAndSMUMode )
{

// Perform the Pulse-IV test.
    status = pg2_init(InstId, PULSE_MODE_PULSE);
    if ( status )
    {
       if (memAllocated)
       {
           cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                   Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                   Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }


    //Calculate fundamental times: Pulse tops, measure start and stop
    //These are used below
    PulseTopTimeCh1 = PulseWidthCh1 - (0.5 * RiseTimeCh1) - (0.5 * FallTimeCh1);
    PulseTopMeasStartCh1 = DelayCh1 + RiseTimeCh1 + (PulseTopTimeCh1*MeasStartPercCh1);
    PulseTopMeasStopCh1 = DelayCh1 + RiseTimeCh1 + (PulseTopTimeCh1*MeasStopPercCh1);

    PulseTopTimeCh2 = PulseWidthCh2 - (0.5 * RiseTimeCh2) - (0.5 * FallTimeCh2);
    PulseTopStartTimeCh2 = DelayCh2 + RiseTimeCh2;
    PulseTopStopTimeCh2 = DelayCh2 + RiseTimeCh2 + PulseTopTimeCh2;       

    if ( verbose )
        printf("PMU_SMU_Sweep_Example: StrtMeas= %g s, StpMeas= %g s, StrtDrnTop= %g s, StpDrnTop= %g s", 
            PulseTopMeasStartCh1, PulseTopMeasStopCh1, PulseTopStartTimeCh2, PulseTopStopTimeCh2);

    if ( verbose )
        printf("PMU_SMU_Sweep_Example: Ch1StrtMeas%= %g perc, Ch1StpMeas%= %g perc",
           (PulseTopMeasStartCh1- DelayCh1 - RiseTimeCh1)/PulseTopTimeCh1, 
           (PulseTopMeasStopCh1- DelayCh1 - RiseTimeCh1)/PulseTopTimeCh1);

    // Determine if the gate measurement window for the pulse top is 
    // within the pulse top of the drain.  If not, error.

    if (PulseTopMeasStartCh1 < PulseTopStartTimeCh2 || 
        PulseTopMeasStartCh1 > PulseTopStopTimeCh2 || 
        PulseTopMeasStopCh1 < PulseTopStartTimeCh2 || 
        PulseTopMeasStopCh1 > PulseTopStopTimeCh2)
    {
        printf("PMU_SMU_Sweep_Example: Error, Meas window (%g to %g s) not within drain pulse top (%g s to %g s)", 
            PulseTopMeasStartCh1, PulseTopMeasStopCh1, PulseTopStartTimeCh2, PulseTopStopTimeCh2);
        sprintf(ErrMsgChar, "Measurement window (%g to %g s) not within drain pulse top (%g to %g s)", 
            PulseTopMeasStartCh1, PulseTopMeasStopCh1, PulseTopStartTimeCh2, PulseTopStopTimeCh2);
        logMsg(MF_Error, ERROR_STRING, ErrMsgChar); 
        if (memAllocated)
        {
            cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                    Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                    Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
        }
        return ERR_PMU_EXAMPLES_MEAS_EARLY;
    }

    // Calculate the Start & Stop measure window percentages for the 
    // Ch2, must be synchronous with Ch1
    MeasStartPercCh2 = (PulseTopMeasStartCh1 - DelayCh2 - RiseTimeCh2) / PulseTopTimeCh2;
    MeasStopPercCh2 = (PulseTopMeasStopCh1 - DelayCh2 - RiseTimeCh2) / PulseTopTimeCh2;

    if ( verbose )
        printf("PMU_SMU_Sweep_Example: Ch2StrtMeas%= %g perc, Ch2StpMeas%= %g perc", 
            MeasStartPercCh2, MeasStopPercCh2);

    // Calculate number of sample points (per A/D) required for the test
    // if total samples for the test > MaxSamplesPerAtoD, then set sample_rate to lower value
    // Max sample rate is 200E6, same rate used for both channels on card

    PulseBaseTimeCh1 = Period - PulseWidthCh1 - RiseTimeCh1 - FallTimeCh1;
    PulseTopMeasTimeCh1 = ((MeasStopPercCh1 - MeasStartPercCh1)* PulseTopTimeCh1);
    NumSamplesTopCh1 = (int)(PulseTopMeasTimeCh1/5e-9 + 1);
    PulseBaseMeasTimeCh1 = ((MeasStopPercCh1 - MeasStartPercCh1)* PulseBaseTimeCh1);
    NumSamplesBaseCh1 = (int)(PulseBaseMeasTimeCh1/5e-9 + 1);    
    NumSamplesPeriodCh1 = NumSamplesTopCh1 + NumSamplesBaseCh1;
    NumSamplesSweepCh1 = NumSweepPts * NumSamplesPeriodCh1;

    if ( verbose )
        printf("PMU_SMU_Sweep_Example: Ch1 PW= %g, PlsTop= %g, PlsBase= %g", 
            PulseWidthCh1, PulseTopTimeCh1, PulseBaseTimeCh1);

    if ( verbose )
        printf("PMU_SMU_Sweep_Example: #SmplPlsTopCh1= %d, #SmplbaseCh1= %d,#SmplPerCh1= %d, #SampSweep= %d", 
            NumSamplesTopCh1, NumSamplesBaseCh1, NumSamplesPeriodCh1, NumSamplesSweepCh1);

    if (NumSamplesSweepCh1 > MaxSamplesPerAtoD)
    {
        RateFactor = (int)((NumSamplesSweepCh1 / MaxSamplesPerAtoD) + 1);      
        SampleRate = (SampleRate / RateFactor);
        printf("Basic_SegArb:  NumSamplesSweepCh1 > MaxSamplesPerAtoD, Ratefactor= %d", RateFactor);
    }
    if ( verbose )
        printf("PMU_SMU_Sweep_Example: NumTtlSmpls= %d, SampleRate= %g", NumSamplesSweepCh1, SampleRate);

    NumTotalSamples = (int)((PulseTopMeasTimeCh1 + PulseBaseMeasTimeCh1) * SampleRate);    

    if ( verbose )
        printf("PMU_SMU_Sweep_Example: Using new sample rate, NumTotalSamples= %d, SampleRate= %g", 
            NumTotalSamples, SampleRate);


    status = pulse_sample_rate(InstId, SampleRate);
    if(status)
    {
        // Error
        
        if (memAllocated)
        {
           cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                   Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                   Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
        }
        return status;
    }

    //Set Ch1 source and measure ranges
    if (LtdAutoCurrCh1)
    {
        status = pulse_ranges(InstId, CardChannel1, VRangeCh1, PULSE_MEAS_FIXED, VRangeCh1, PULSE_MEAS_LTD_AUTO, IRangeCh1);
        if ( status )
        {
           // Error
           
           if (memAllocated)
           {
              cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                      Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                      Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
           }
           return status;
        }
    } else {
        status = pulse_ranges(InstId, CardChannel1, VRangeCh1, PULSE_MEAS_FIXED, VRangeCh1, PULSE_MEAS_FIXED, IRangeCh1);
        if ( status )
        {
           // Error
           
           if (memAllocated)
           {
              cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                      Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                      Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
           }
           return status;
        }
    }

    //Set Ch2 source and measure ranges
    if (LtdAutoCurrCh2)
    {
        status = pulse_ranges(InstId, CardChannel2, VRangeCh2, PULSE_MEAS_FIXED, VRangeCh2, PULSE_MEAS_LTD_AUTO, IRangeCh2);
        if ( status )
        {
           // Error
           
           if (memAllocated)
           {
              cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                      Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                      Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
           }
           return status;
        }
    } else {
        status = pulse_ranges(InstId, CardChannel2, VRangeCh2, PULSE_MEAS_FIXED, VRangeCh2, PULSE_MEAS_FIXED, IRangeCh2);
        if ( status ) 
        {
           // Error
           
           if (memAllocated)
           {
              cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                      Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                      Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
           }
           return status;
        }
    }

    //If load line effect compensation for the gate is disabled, set desired resistance
    if (!LoadLineCh1)
    {
        status = pulse_load(InstId, CardChannel1, ResCh1);
        if ( status )
        {
           // Error
           
           if (memAllocated)
           {
              cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                      Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                      Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
           }
           return status;
        }
    }

    //If load line effect compensation for the drain is disabled, set desired resistance
    if (!LoadLineCh2)
    {
        status = pulse_load(InstId, CardChannel2, ResCh2);
        if ( status )
        {
           // Error
           
           if (memAllocated)
           {
              cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                      Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                      Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
           }
           return status;
        }
    }

    //Set Ch1 pulse source timing
    status = pulse_source_timing(InstId, CardChannel1, Period, DelayCh1, PulseWidthCh1, RiseTimeCh1, FallTimeCh1);
    if ( status )
    {
       // Error
       
           if (memAllocated)
           {
              cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                      Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                      Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
           }
       return status;
    }

    //Set Ch2 pulse source timing
    status = pulse_source_timing(InstId, CardChannel2, Period, DelayCh2, PulseWidthCh2, RiseTimeCh2, FallTimeCh2);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }


    //Set Ch1 pulse measurement for spot means on pulse top and base
    status = pulse_meas_timing(InstId, CardChannel1, MeasStartPercCh1, MeasStopPercCh1, PulseAverage);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    //Set Ch2 pulse measurement for spot means on pulse top and base
    status = pulse_meas_timing(InstId, CardChannel2, MeasStartPercCh2, MeasStopPercCh2, PulseAverage);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    //Enable Ch1 spot mean measurements
    status = pulse_meas_sm(InstId, CardChannel1, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, TRUE, TRUE, LoadLineCh1);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    //Enable Ch2 spot mean measurements
    status = pulse_meas_sm(InstId, CardChannel2, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, TRUE, TRUE, LoadLineCh2);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }


    //Program drain base, necessary when performing Ch2 Amplitude sweep
    status = pulse_vlow(InstId, CardChannel2, BaseVCh2);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    //Configure pulse with fixed amplitude
    status = pulse_train(InstId, CardChannel1, BaseVCh1, AmplVCh1);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    status = pulse_sweep_linear(InstId, CardChannel2, PULSE_AMPLITUDE_SP, StartVCh2, StopVCh2, StepVCh2);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }


    status = pulse_output(InstId, CardChannel1, 1);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    status = pulse_output(InstId, CardChannel2, 1);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    if ( verbose )
        printf("PMU_SMU_Sweep_Example: Just prior to pulse_exec");

    //Set test execute mode to Simple or Advanced
    if (PMUMode ==0)
        TestMode = PULSE_MODE_SIMPLE;
    else
        TestMode = PULSE_MODE_ADVANCED;

    status = pulse_exec(TestMode);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    while(pulse_exec_status(&elapsedt) == 1);
     Sleep(100);

    if ( verbose )
        printf("PMU_SMU_Sweep_Example: Just after pulse_exec_status, test done, getting data");

    status = pulse_fetch(InstId, CardChannel1, 0, NumSweepPts*2, Ch1_V_All, Ch1_I_All, Ch1_T_All, Ch1_S_All);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    status = pulse_fetch(InstId, CardChannel2, 0, NumSweepPts*2, Ch2_V_All, Ch2_I_All, Ch2_T_All, Ch2_S_All);
    if ( status )
    {
       // Error
       
       if (memAllocated)
       {
          cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
                  Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
                  Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
       }
       return status;
    }

    // Pulse Amplitude(High) and Pulse Base (Low) readings are interleaved
    // Split Amplitude and Base spot means into individual arrays before posting to sheet
    for (i = 0; i<NumSweepPts; i++)
    {

       Ch1_V_High[i] = Ch1_V_All[2*i];
       Ch1_I_High[i] = Ch1_I_All[2*i];
       Ch1_T_High[i] = Ch1_T_All[2*i];            
       Ch1_V_Low[i] = Ch1_V_All[2*i+1];
       Ch1_I_Low[i] = Ch1_I_All[2*i+1];
       Ch1_T_Low[i] = Ch1_T_All[2*i+1];

       Ch2_V_High[i] = Ch2_V_All[2*i];
       Ch2_I_High[i] = Ch2_I_All[2*i];
       Ch2_T_High[i] = Ch2_T_All[2*i];            
       Ch2_V_Low[i] = Ch2_V_All[2*i+1];
       Ch2_I_Low[i] = Ch2_I_All[2*i+1];
       Ch2_T_Low[i] = Ch2_T_All[2*i+1];
           
    }

    if ( verbose )
    {
      for (i = 0; i<NumSweepPts; i++)
      {
         printf("PMU_SMU_Sweep_Example:  i= %d, Ch1Vfull= %g, Ch1Vhi= %g, Ch1Vlo= %g",
           i, Ch1_V_All[i], Ch1_V_High[i], Ch1_V_Low[i]);
         printf("PMU_SMU_Sweep_Example:  i= %d, Ch2Vfull= %g, Ch2Vhi= %g, Ch2Vlo= %g",
           i, Ch2_V_All[i], Ch2_V_High[i], Ch2_V_Low[i]);
      }
    }
}

if ( ExecMode == SMUOnlyMode || ExecMode == PulseAndSMUMode) {

    if ( verbose )
      printf("PMU_SMU_Sweep_Example: ExecMode is %i and we're about to perform the DC Test\n", ExecMode);
              
    // We've finished the Pulse-IV testing, now perform  the DC SMU test.
    // But first, open the PMU output relays and close the SMU output relays.
    if (!RPMPresent)
    {
       if (verbose ) printf("PMU_SMU_Sweep_Example: using SMU relays - SMU\n");

       Stat = setmode(Ch1SMUId, KI_SHIELD_RELAY_STATE, 1);
       Stat = setmode(Ch2SMUId, KI_SHIELD_RELAY_STATE, 1);
    } else {
       if (verbose ) printf("PMU_SMU_Sweep_Example: using SMU relays - SMU\n");

       Stat = rpm_config(InstId, CardChannel1, KI_RPM_PATHWAY, KI_RPM_SMU);
       Stat = rpm_config(InstId, CardChannel2, KI_RPM_PATHWAY, KI_RPM_SMU);
    }
    if (verbose)
    {
       printf("PMU_SMU_Sweep_Example: switch to SMU Mode status %d\n",Stat);
    }

    // Set the current ranges and limit for Channel 2
    limiti(Ch2SMUId, SMU_Icomp);
    rangei(Ch2SMUId, SMU_Irange);

    // Bias Ch1
    forcev(Ch1SMUId, AmplVCh1);

    // Sweep the drain
    rtfary(Ch2_SMU_Voltage);
    smeasi(Ch2SMUId, Ch2_SMU_Current);
    sintgi(Ch1SMUId, Ch1_SMU_Current);
    smeasv(Ch1SMUId, Ch1_SMU_Voltage);
    sweepv(Ch2SMUId, StartVCh2, StopVCh2, NumSweepPts-1, sweepdelay);
    inshld();

} 

if (ExecMode < 0 || ExecMode > 2)
{
    // Invalid Execution Mode
    ExecStatus = -99;
}


if (ExecStatus != -99 )
{
    // Return all the data.
    
    // Return data, first Pulse (if chosen), then SMU (if chosen)
    if (ExecMode == PulseAndSMUMode || ExecMode == PulseOnlyMode)
    {
        PostDataDoubleBuffer("Ch1_V_Ampl", Ch1_V_High, NumSweepPts);
        PostDataDoubleBuffer("Ch1_I_Ampl", Ch1_I_High, NumSweepPts);        
        PostDataDoubleBuffer("TimeStampAmpl_Ch1", Ch1_T_High, NumSweepPts);
        PostDataDoubleBuffer("Ch1_V_Base", Ch1_V_Low, NumSweepPts);
        PostDataDoubleBuffer("Ch1_I_Base", Ch1_I_Low, NumSweepPts);        
        PostDataDoubleBuffer("TimeStampBase_Ch1", Ch1_T_Low, NumSweepPts);
        PostDataDoubleBuffer("Ch2_V_Ampl", Ch2_V_High, NumSweepPts);
        PostDataDoubleBuffer("Ch2_I_Ampl", Ch2_I_High, NumSweepPts);        
        PostDataDoubleBuffer("TimeStampAmpl_Ch2", Ch2_T_High, NumSweepPts);
        PostDataDoubleBuffer("Ch2_V_Base", Ch2_V_Low, NumSweepPts);
        PostDataDoubleBuffer("Ch2_I_Base", Ch2_I_Low, NumSweepPts);        
        PostDataDoubleBuffer("TimeStampBase_Ch2", Ch2_T_Low, NumSweepPts);
    }

    if (ExecMode == PulseAndSMUMode || ExecMode == SMUOnlyMode)
    {
        PostDataDoubleBuffer("Ch2_SMU_Voltage", Ch2_SMU_Voltage, NumSweepPts);
        PostDataDoubleBuffer("Ch2_SMU_Current", Ch2_SMU_Current, NumSweepPts);
        PostDataDoubleBuffer("Ch1_SMU_Voltage", Ch1_SMU_Voltage, NumSweepPts);
        PostDataDoubleBuffer("Ch1_SMU_Current", Ch1_SMU_Current, NumSweepPts);
    }


    if (memAllocated)
    {
       cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
            Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
            Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
    }
    return 0;
} else {

    if (memAllocated)
    {
       cleanUp(Ch1_V_High, Ch1_I_High, Ch1_V_Low, Ch1_I_Low,
            Ch1_T_High, Ch1_T_Low, Ch2_V_High, Ch2_I_High, 
            Ch2_V_Low, Ch2_I_Low, Ch2_T_High, Ch2_T_Low);
    }
    return ExecStatus;
} // end for
} // end PMU_SMU_Sweep_Example

void cleanUp( double *Ch1_V_High, double *Ch1_I_High, double *Ch1_V_Low, double *Ch1_I_Low,
              double *Ch1_T_High, double *Ch1_T_Low, double *Ch2_V_High, double *Ch2_I_High, 
              double *Ch2_V_Low, double *Ch2_I_Low, double *Ch2_T_High, double *Ch2_T_Low)
{
    //Free memory for arrays
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

    // Put the instruments in a safe state
    devint();
    return;
/* USRLIB MODULE END  */
} 		/* End PMU_SMU_Sweep_Example.c */

