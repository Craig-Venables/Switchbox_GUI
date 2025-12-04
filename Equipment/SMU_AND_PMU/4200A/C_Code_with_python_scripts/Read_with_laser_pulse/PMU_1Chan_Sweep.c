/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_1Chan_Sweep
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 32
	ARGUMENTS:
		PulseWidthCh1,	double,	Input,	500e-9,	60e-9,	.999999
		RiseTimeCh1,	double,	Input,	100e-9,	20e-9,	.033
		FallTimeCh1,	double,	Input,	100e-9,	20e-9,	0.033
		Period,	double,	Input,	10e-6,	120e-9,	1
		DelayCh1,	double,	Input,	0,	0,	.999999
		SampleRate,	double,	Input,	200E6,	1000,	200E6
		MeasStartPerc,	double,	Input,	.75,	0,	1
		MeasStopPerc,	double,	Input,	0.90,	0,	1
		PulseAverage,	int,	Input,	1,	1,	10000
		LoadLineCh1,	int,	Input,	0,	0,	1
		DUTResCh1,	double,	Input,	1E6,	1,	1E6
		VRangeCh1,	double,	Input,	10,	5,	40
		IRangeCh1,	double,	Input,	.01,	100e-9,	.8
		StartVCh1,	double,	Input,	0,	-40,	40
		StopVCh1,	double,	Input,	5,	-40,	40
		StepVCh1,	double,	Input,	1,	-40,	40
		BaseVCh1,	double,	Input,	0,	-40,	40
		PMUMode,	int,	Input,	0,	0,	1
		Chan,	int,	Input,	1,	1,	2
		PMU_ID,	char *,	Input,	"PMU1",	,	
		V_Ampl_Ch1,	D_ARRAY_T,	Output,	,	,	
		V_Ampl_Ch1_Size,	int,	Input,	100,	1,	10000
		I_Ampl_Ch1,	D_ARRAY_T,	Output,	,	,	
		I_Ampl_Ch1_Size,	int,	Input,	100,	1,	10000
		V_Base_Ch1,	D_ARRAY_T,	Output,	,	,	
		V_Base_Ch1_Size,	int,	Input,	100,	1,	10000
		I_Base_Ch1,	D_ARRAY_T,	Output,	,	,	
		I_Base_Ch1_Size,	int,	Input,	100,	1,	10000
		TimeStamp_Ch1,	D_ARRAY_T,	Output,	,	,	
		TimeStamp_Ch1_Size,	int,	Input,	100,	1,	10000
		Status_Ch1,	I_ARRAY_T,	Output,	,	,	
		Status_Ch1_Size,	int,	Input,	100,	1,	10000
	INCLUDES:
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"

BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_1ChanSw(int numSweepPoints);
void FreeArrays_1ChanSw();

double *Chan1_V, *Chan1_I, *Chan1_T, *Chan1_Vhisheet, *Chan1_Ihisheet, *Chan1_Vlosheet, *Chan1_Ilosheet, *Chan1_Tsheet;
double dChan1_Vhisheet, dChan1_Ihisheet, dChan1_Vlosheet, dChan1_Ilosheet, dChan1_Tsheet;
unsigned long *Chan1_S, *Chan1_Ssheet;
int i;

	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: PMU_1Chan_Sweep
===============================

Description
-----------

Voltage amplitude Pulse IV sweep using 1 channel of the 4225-PMU. 

It returns voltage and current spot means for pulse amplitude and base.  

The purpose of this module is a functional programming reference to illustrate the 
basic commands necessary to perform a 1 channel Pulse IV (2-level pulse) sweep.

There are no power, current or voltage thresholds in this example.

Note:  Choose a SampleRate that does not require more than 1 million samples per 
I or V.  See descriptions below for additional information.

This routine is compatible with KXCI using the UL mode.

~~~~
               _____________             _
              /  PulseTop   \            |
             /               \           |
            /<--PulseWidth--->\  startV, stopV, stepV
           /                   \         |
  ________/                     \________|________baseV
  Delay     Rise            Fall 
  |<---------------Period------------------------>|
~~~~

Inputs
------
PulseWidthCh1 
: Pulse Width (Full Width Half Maximum) in seconds.
: Range: 60 ns to 999.999 ms

RiseTimeCh1	
: Pulse Rise Time (0 to 100%), in seconds.
: Note that slower transition times are slew rate limited, 
		so to reach the slowest transition time, the largest 
		voltage amplitude must be used.
: 10V Range: 20 ns to 33 ms
: 40V Range: 100 ns to 33 ms

FallTimeCh1	
: Pulse Fall Time (0 to 100%), in seconds.
: Note that slower transition times are slew rate limited, 
		so to reach the slowest transition time, the largest 
		voltage amplitude must be used.
: 10V Range: 20 ns to 33 ms
: 40V Range: 100 ns to 33 ms

Period		
: Pulse Period, in seconds:
: 10V Range: 120 ns to 1 s
: 40V Range: 280 ns to 1 s

DelayCh1	
: Pulse Delay (time before pulse rise time), in seconds: 10 ns to 
		999 ms

SampleRate	
: Samples per second, in steps of 200e6/n, where n is an integer.
		From 200e6 (200 MS/s max) to 1000 (1 kS/s):  200e6, 100e6, 
		66.6e6, 50e6, 40e6, 33.3e6, 28.57e6, 25e6 ...

MeasStartPerc	
: Start of the spot mean measure window in percent, where 0% is the
		start of the pulse top and 100% is the end of the pulse top.  Pulse
		top is the time of the pulse at the chosen amplitude.
: For example, a pulse width of 200 ns (FWHM) with rise and fall of 
		40 ns would give a pulse top time:
: pulse top = PW - 0.5 * rise - 0.5 * fall
: pulse top = 200 - 20 - 20 = 160 ns
: Typical value is 0.75 (75%).

MeasStopPerc	
: Stop of the spot mean measure window in percent, where 0% is the 
		start of the pulse top and 100% is the end of the pulse top. See 
		MeasStartPerc for description of the percentage and pulse top.
: Typical value is 0.9 (90%).

PulseAverage	
: Number of pulses to output and average together. This value is 
		typically used to provide a lower noise measurement through 
		additional averaging at a given pulse width.  For example, 
		if PulseAverage = 5, a burst (or train) of 5 pulses is output
		at each desired sweep level. 5 pulses would be output and the 
		samples between MeasStartPerc and MeasStopPerc for each 
		of the 5 pulses is averaged (meaned) into a single spot mean.

LoadLineCh1	
: Load Line effect Compensation enabled or disabled. LLE 
		compensation compensates for the voltage drop of the 50 &Omega; 
		output of the PMU channel due to current flowing through the 
		Device Under Test (DUT).  Enabling the LLE compensation increases 
		test time, but provides the desired sweep voltage at the DUT.
		To enable LLE compensation, set this parameter and PMUMode = 1.
: 1: Enabled
: 0: Disabled

DUTResCh1	
: Resistance of DUT connected to Ch 1 (&Omega;). This value is only 
		used when LLE Comp is disabled (LoadLineCh1 = 0). Set the DUTResCh1
		to match the resistance of the DUT.  Setting this value to represent
		the actual DUT impedance will greatly reduce the difference between 
		the programmed voltage and the voltage at the DUT due to load line
		effects.  This parameter is not meaningful when using a 4225-RPM 
		current measure range of 1 mA or lower.
: Range: 1 to 1e6 &Omega;

VRangeCh1	
: Voltage range for Ch 1.
: Note that maximum source voltage for a range is obtained only with 
		a high impedance DUT (roughly 100 k&Omega; and higher).
: Valid ranges: 10, 40

IRangeCh1	
: Current measure range for Ch 1. Valid ranges: 
: PMU 10V:  0.01, 0.2
: PMU 40V:  100e-6, 0.01, 0.8
: RPM 10V:  100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

StartVCh1	
: Start voltage for the amplitude sweep. Note that the programmed 
		voltage may not be reached if the DUT resistance is low.  
		Valid: 
: -10 to +10 for the 10V range
: -40 to +40 for the 40V range

StopVCh1	
: Stop voltage for the amplitude sweep. See StartVCh1 for details.

StepVCh1	
: Voltage step size for the amplitude sweep.
: Range:  1 mV (typical) to VRange

BaseVCh1	
: Base voltage for the pulse. Or, the voltage output between each 
		pulse. See StartVCh1 for maximums.

PMUMode	(int)	
: PMU Test Execution mode. Controls test execution. If Load Line 
		Effect compensation or thresholds (volt, current, power) are 
		desired, then set PMUMode = 1, otherwise use PMUMode = 0.  Note 
		that Mode = 0 will result in shorter test times, but only allows 
		fixed current ranges, no LLE comp and no IVP threshold comparisons.
: 0: Simple
: 1: Advanced

Chan	
: PMU channel number:
: Range: 1, 2.

PMU_ID	
: PMU number. PMU in lowest numbered slot (right-most PMU when 
		viewed from rear of 4200A chassis) is PMU1.

Outputs
-------

V_Ampl_Ch1	
: Voltage and current spot mean readings for the pulse amplitude.  

I_Ampl_Ch1	
: The location of these spot means within the pulse are determined 
		by MeasStartPerc and MeasStopPerc.

V_Base_Ch1	
: Voltage and current spot mean readings for the pulse base, 
   or I_Base_Ch1 time between the pulses.

TimeStamp_Ch1	
: Timestamp for the reading, based on the pulse period (not 
		total elapsed test time).

Status_Ch1	
: This argument is no longer supported. No data will be returned.

Return values
-------------
			 
Value  | Description
------ | -----------
0      | OK.
-122   | pulse_ranges(): Illegal value for parameter #7. Ensure that current measure
       | range is appropriate for the chosen voltage range.
-824   | pulse_exec(): Invalid pulse timing parameters.
       | One or more timing parameters (PulseWidthCh1, RiseTimeCh1, FallTimeCh1,
       | DelayCh1 or Period) are too small for the chosen VRangeCh1.
       | Increase the time of the appropriate parameters.
-829   | pulse_sweep_linear(): The sum of base and amplitude voltages (XX.XV)
       | exceeds maximum (YYV) for present range. The Base + Amplitude voltage
       | is too large for the chosen PMU voltage range. Check the BaseVCh1,
       | StartVCh1 and StopVCh1 for voltages that exceed VRangeCh1.
       | If necessary, increase VRangeCh1 to the maximum 40V range.
-17001 | Wrong card Id. Check PMU and SMU names
-17002 | Failure to assign card ID handle. Check PMU and/or SMU names
-17110 | Output array sizes are less than number of points in sweep.
	   | Increase output array sizes or decrease number of points in sweep.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "PMU_examples_ulib_internal.h"

BOOL LPTIsInCurrentConfiguration(char* hrid);
void AllocateArrays_1ChanSw(int numSweepPoints);
void FreeArrays_1ChanSw();

double *Chan1_V, *Chan1_I, *Chan1_T, *Chan1_Vhisheet, *Chan1_Ihisheet, *Chan1_Vlosheet, *Chan1_Ilosheet, *Chan1_Tsheet;
double dChan1_Vhisheet, dChan1_Ihisheet, dChan1_Vlosheet, dChan1_Ilosheet, dChan1_Tsheet;
unsigned long *Chan1_S, *Chan1_Ssheet;
int i;


/* USRLIB MODULE MAIN FUNCTION */
int PMU_1Chan_Sweep( double PulseWidthCh1, double RiseTimeCh1, double FallTimeCh1, double Period, double DelayCh1, double SampleRate, double MeasStartPerc, double MeasStopPerc, int PulseAverage, int LoadLineCh1, double DUTResCh1, double VRangeCh1, double IRangeCh1, double StartVCh1, double StopVCh1, double StepVCh1, double BaseVCh1, int PMUMode, int Chan, char *PMU_ID, double *V_Ampl_Ch1, int V_Ampl_Ch1_Size, double *I_Ampl_Ch1, int I_Ampl_Ch1_Size, double *V_Base_Ch1, int V_Base_Ch1_Size, double *I_Base_Ch1, int I_Base_Ch1_Size, double *TimeStamp_Ch1, int TimeStamp_Ch1_Size, int *Status_Ch1, int Status_Ch1_Size )
{
/* USRLIB MODULE CODE */
    int i;
    int status;
    int TestMode;
    int NumSweepPts;
    double elapsedt;
    int InstId = 0;
    int verbose = 0;

    //Set all global arrays to null
    Chan1_S = Chan1_Ssheet = NULL;
    Chan1_V = Chan1_I = Chan1_T = Chan1_Vhisheet = Chan1_Ihisheet = Chan1_Vlosheet = Chan1_Ilosheet = Chan1_Tsheet = NULL;


		 //printf not working in KXCI console need to have the Clarius Message Console Open!!!!!
verbose = 1;           //Enable printf messages to msgcon for troubleshooting
if (verbose)
           { printf("made it here 0"); 
	      printf("PMU ID value passed from Labview is %s ", PMU_ID);}


// this command checks to see if the PMU card is in the chassis
    if ( !LPTIsInCurrentConfiguration(PMU_ID) )
    { 
        printf("Instrument %s is not in system configuration", PMU_ID);
        return -ERR_PMU_EXAMPLES_WRONGCARDID;
    }

 
 if (verbose)
            printf("made it here 1");

    //Get handle, necessary for all following, commands for desired PMU
    getinstid(PMU_ID, &InstId);
    if ( -1 == InstId )
        return ERR_PMU_EXAMPLES_CARDHANDLEFAIL;

    if (verbose)
            printf("made it here 2");


    if (StepVCh1 == 0)
        NumSweepPts = 1;        
    else
        NumSweepPts = (int)((StopVCh1 - StartVCh1)/StepVCh1 + 1E-7 + 1);    //Add a fraction to handle round-off errors

                                                                            //Determine if return array sizes are big enough to contain
                                                                            //the desired number of sweep points (NumSweepPts)
    if (NumSweepPts > V_Ampl_Ch1_Size || NumSweepPts > I_Ampl_Ch1_Size || NumSweepPts > V_Base_Ch1_Size || NumSweepPts > I_Base_Ch1_Size ||
        NumSweepPts > TimeStamp_Ch1_Size || NumSweepPts > Status_Ch1_Size)
    {
        if (verbose)
            printf("PMU_IV_sweep_Example: One or more Output array size(s) < number of sweep points. Increase size of all Output arrays to be at least %d", NumSweepPts);
        return ERR_PMU_EXAMPLES_OUTPUT_ARRAY_TOO_SMALL;
    }


    //Size arrays based on required number of points, assume both pulse high (amplitude) and low (base) measurements are enabled
    AllocateArrays_1ChanSw(NumSweepPts);

    //Ensure that 4225-RPM (if attached) is in the pulse mode
    status = rpm_config(InstId, Chan, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status )
    {
        FreeArrays_1ChanSw();
        return status ;
    }

    // using RPM so set mode (not needed see status check above)
   // rpm_config(InstId, 1, KI_RPM_PATHWAY, KI_RPM_PULSE);

    //Rest the pulse card and puts into pulse mode. The reset is to default values, range, pulse period etc..
    status = pg2_init(InstId, PULSE_MODE_PULSE);
    if ( status )
    {
        FreeArrays_1ChanSw();
        return status ;
    }

    if ( verbose )
        printf("PMU_1Chan_Sweep_Ex: rpmconfig chan= %d, status= %d", Chan, status);

    //Set PMU to return actual values when measurement overflow occurs
    status = setmode(InstId, KI_LIM_MODE, KI_VALUE);
    if(status)
    {
        FreeArrays_1ChanSw();
        return status;
    }


    status = pulse_sample_rate(InstId, SampleRate);
    if(status)
    {
        FreeArrays_1ChanSw();
        return status;
    }

    if ( verbose )
        printf("PMU_1Chan_Sweep_Ex: Num sweep pts= %d, IRangeCh1= %g", NumSweepPts, IRangeCh1);

    //Set PMU source and measure ranges
    status = pulse_ranges(InstId, Chan, VRangeCh1, PULSE_MEAS_FIXED, VRangeCh1, PULSE_MEAS_FIXED, IRangeCh1);
    if ( status )
    {
        FreeArrays_1ChanSw();
        return status;
    }

    if (!LoadLineCh1 || !PMUMode)
    {
        status = pulse_load(InstId, Chan, DUTResCh1);
        if ( status )
        {
            FreeArrays_1ChanSw();
            return status;

        }
    }

    //Set base voltage of pulser for sweep type PULSE_AMPLITUDE_SP
    //When doing a base sweep (PULSE_BASE_SP), set amplitude with pulse_vhigh()
    //When sweeping a timing parameter (example, pulse width using PULSE_WIDTH_SP), setup pulse using pulse_train()
    status = pulse_vlow(InstId, Chan, BaseVCh1);
    if ( status )
    {
        FreeArrays_1ChanSw();
        return status;
    }

    status = pulse_burst_count(InstId, Chan, 1);
    if ( status )
    {
       FreeArrays_1ChanSw();
       return status;
    }

    status = pulse_source_timing(InstId, Chan, Period, DelayCh1, PulseWidthCh1, RiseTimeCh1, FallTimeCh1);
    if ( status )
    {
       FreeArrays_1ChanSw();
       return status;
    }

    status = pulse_meas_timing(InstId, Chan, MeasStartPerc, MeasStopPerc, PulseAverage);
    if ( status )
    {
        FreeArrays_1ChanSw();
        return status;
    }

    //pulse_meas_sm(Card, ch, Measuretype, acquireVHigh, acquireVLow, acquireIHigh, acquireILow, acquireTimeStamp, LLEComp)
    status = pulse_meas_sm(InstId, Chan, PULSE_ACQ_PBURST, TRUE, TRUE, TRUE, TRUE, TRUE, LoadLineCh1);
    if ( status )
    {
        FreeArrays_1ChanSw();
        return status;
    }

    //   ***************Configure sweep***********************
// Notes: pulse_sweep_linear (function below) and others are found in lptproto.h  which is in directory C:\s4200\sys\include
// some other commands in lptproto are below (note: LPTLib is a Linear Parametric Test Library), see LPT Library Programming Manual for full description of these
// functions and many others
// int WINAPI pulse_step_linear(INSTR_ID instrID, int chan, int sweepType, double start, double stop, double step);
// int WINAPI pulse_sweep_linear(INSTR_ID instrID, int chan, int sweepType, double start, double stop, double step);
// int WINAPI pulse_train(INSTR_ID instrID, int chan, double vbase, double vamplitude);
// int WINAPI pulse_source_timing(INSTR_ID instid, int chan, double period, double delay, double width, double rise, double fall);

// also note that keithley.h calls #include "kult_user.h"
 
   status = pulse_sweep_linear(InstId, Chan, PULSE_AMPLITUDE_SP, StartVCh1, StopVCh1, StepVCh1);
    if ( status )
    {
        FreeArrays_1ChanSw();
        return status;
    }

    //Enable output
    status = pulse_output(InstId, Chan, 1);
    if ( status )
    {
        FreeArrays_1ChanSw();
        return status;
    }

    //Set test execute mode to Simple (no current auto-ranging or LLEC) or Advanced
    if (PMUMode ==0)
        TestMode = PULSE_MODE_SIMPLE;
    else
        TestMode = PULSE_MODE_ADVANCED;

    //  ************Run the test**************
    status = pulse_exec(TestMode);
    if ( status )
    {
        FreeArrays_1ChanSw();
        return status;
    }

    //     **************Check for the test to be complete******************
    while(pulse_exec_status(&elapsedt) == 1)
     Sleep(100);

    //Test is complete, get the data
    status = pulse_fetch(InstId, Chan, 0, NumSweepPts*2-1, Chan1_V, Chan1_I, Chan1_T, Chan1_S);
    if ( status )
    {
       FreeArrays_1ChanSw();
       return status;
    }

    //Separate the pulse amplitude and pulse base measurements into different arrays
    for (i = 0; i<NumSweepPts; i++)
    {
        Chan1_Vhisheet[i] = Chan1_V[2*i];
            // check
        printf ("Vhisheet %f %f", Chan1_V[2*i],Chan1_Vhisheet[i]);
//        printf ("Vhisheet %f ", Chan1_Vhisheet[i]);


        Chan1_Ihisheet[i] = Chan1_I[2*i];
                 // check
        printf ("Ihisheet %f %f", Chan1_Ihisheet[i], Chan1_I[2*i]);

        Chan1_Tsheet[i] = Chan1_T[2*i];    
        // check
        printf ("Tsheet %f ", Chan1_Tsheet[i]);

                
        Chan1_Vlosheet[i] = Chan1_V[2*i+1];
        Chan1_Ilosheet[i] = Chan1_I[2*i+1];
        Chan1_Ssheet[i] = Chan1_S[2*i];

        //Copy results directly into the output arrays, so that this UTM
        //will work properly when called from KXCI
        V_Ampl_Ch1[i] = Chan1_Vhisheet[i];
        I_Ampl_Ch1[i] = Chan1_Ihisheet[i];
        V_Base_Ch1[i] = Chan1_Vlosheet[i];
        I_Base_Ch1[i] = Chan1_Ilosheet[i];
        TimeStamp_Ch1[i] = Chan1_Tsheet[i];
        Status_Ch1[i] = Chan1_Ssheet[i];
    }


// ***** Note: PostDataDoubleBuffer IS NOT COMPATIBALE with KXCI to call user libraries remotely (i.e. with UL command) - see manual,
// *****  need to use PostDataDouble. 
//  ***** Sometimes it seems to work but other times not

    //Post measurements to Clarius sheet in blocks, faster than using PostDataDouble() calls
  //  PostDataDoubleBuffer("V_Ampl_Ch1", Chan1_Vhisheet, NumSweepPts);
  //  PostDataDoubleBuffer("I_Ampl_Ch1", Chan1_Ihisheet, NumSweepPts);        
  //  PostDataDoubleBuffer("V_Base_Ch1", Chan1_Vlosheet, NumSweepPts);
  //  PostDataDoubleBuffer("I_Base_Ch1", Chan1_Ilosheet, NumSweepPts);        
  //  PostDataDoubleBuffer("TimeStamp_Ch1", Chan1_Tsheet, NumSweepPts);

  dChan1_Vhisheet=*Chan1_Vhisheet; dChan1_Ihisheet=*Chan1_Ihisheet; dChan1_Vlosheet=*Chan1_Vlosheet; dChan1_Ilosheet=*Chan1_Ilosheet; dChan1_Tsheet=*Chan1_Tsheet;

  
    if (verbose)
            {printf("made it here 4");
                         for(i=0; i<NumSweepPts; i++)
                {
                printf ("Vhisheet %f", Chan1_Vhisheet[i]);
                printf ("Ihisheet %f", Chan1_Ihisheet[i]);
                printf ("Tsheet %f", Chan1_Tsheet[i]);
                }
             }


    PostDataDouble("V_Ampl_Ch1", dChan1_Vhisheet);
    PostDataDouble("I_Ampl_Ch1", dChan1_Ihisheet);        
    PostDataDouble("V_Base_Ch1", dChan1_Vlosheet);
    PostDataDouble("I_Base_Ch1", dChan1_Ilosheet);        
    PostDataDouble("TimeStamp_Ch1", dChan1_Tsheet);


    //Avoid returning PMU channel status to Clarius, is not generally useful or easily interpreted
//    PostDataIntBuffer("Status_Ch1", Chan1_Ssheet, NumSweepPts);

    FreeArrays_1ChanSw();
    return 0;
}

void AllocateArrays_1ChanSw(int numSweepPoints)
{
    Chan1_V = (double *)calloc(numSweepPoints*2+1, sizeof(double));
    Chan1_I = (double *)calloc(numSweepPoints*2+1, sizeof(double));
    Chan1_T = (double *)calloc(numSweepPoints*2+1, sizeof(double));    
    Chan1_S = (unsigned long *)calloc(numSweepPoints*2+1, sizeof(unsigned long));    
    Chan1_Vhisheet = (double *)calloc(numSweepPoints+1, sizeof(double));
    Chan1_Ihisheet = (double *)calloc(numSweepPoints+1, sizeof(double));
    Chan1_Vlosheet = (double *)calloc(numSweepPoints+1, sizeof(double));
    Chan1_Ilosheet = (double *)calloc(numSweepPoints+1, sizeof(double));
    Chan1_Tsheet = (double *)calloc(numSweepPoints+1, sizeof(double));
    Chan1_Ssheet = (unsigned long *)calloc(numSweepPoints+1, sizeof(unsigned long));
}

void FreeArrays_1ChanSw()
{
    if (Chan1_V != NULL)
        free(Chan1_V);
    if (Chan1_I != NULL)
        free(Chan1_I);
    if (Chan1_T != NULL)
        free(Chan1_T);
    if (Chan1_S != NULL)
        free(Chan1_S);
    if (Chan1_Vhisheet != NULL)
        free(Chan1_Vhisheet);
    if (Chan1_Ihisheet != NULL)
        free(Chan1_Ihisheet);
    if (Chan1_Vlosheet != NULL)
        free(Chan1_Vlosheet);
    if (Chan1_Ilosheet != NULL)
        free(Chan1_Ilosheet);
    if (Chan1_Tsheet != NULL)
        free(Chan1_Tsheet);
    if (Chan1_Ssheet != NULL)
        free(Chan1_Ssheet);

/* USRLIB MODULE END  */
} 		/* End PMU_1Chan_Sweep.c */

