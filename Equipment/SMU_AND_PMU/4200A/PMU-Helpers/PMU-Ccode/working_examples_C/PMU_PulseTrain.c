/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_PulseTrain
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 35
	ARGUMENTS:
		riseTime,	double,	Input,	3e-8,	2e-8,	1
		resetV,	double,	Input,	4,	-20,	20
		resetWidth,	double,	Input,	1e-6,	2e-8,	1
		resetDelay,	double,	Input,	1e-6,	2e-8,	1
		measV,	double,	Input,	0.5,	-20,	20
		measWidth,	double,	Input,	2e-6,	2e-8,	1
		measDelay,	double,	Input,	1e-6,	2e-8,	1
		setWidth,	double,	Input,	1e-6,	2e-8,	1
		setFallTime,	double,	Input,	3e-8,	2e-8,	1
		setDelay,	double,	Input,	1e-6,	2e-8,	1
		setStartV,	double,	Input,	0,	-20,	20
		setStopV,	double,	Input,	4,	-20,	20
		steps,	int,	Input,	5,	1,	
		IRange,	double,	Input,	1e-2,	100e-9,	.8
		max_points,	int,	Input,	10000,	12,	30000
		setR,	D_ARRAY_T,	Output,	,	,	
		setR_size,	int,	Input,	5,	1,	30000
		resetR,	D_ARRAY_T,	Output,	,	,	
		resetR_size,	int,	Input,	5,	1,	30000
		setV,	D_ARRAY_T,	Output,	,	,	
		setV_size,	int,	Input,	5,	1,	30000
		setI,	D_ARRAY_T,	Output,	,	,	
		setI_size,	int,	Input,	5,	1,	30000
		iteration,	int,	Input,	5,	1,	
		out1,	D_ARRAY_T,	Output,	,	,	
		out1_size,	int,	Input,	200,	1,	30000
		out1_name,	char *,	Input,	"VF",	,	
		out2,	D_ARRAY_T,	Output,	,	,	
		out2_size,	int,	Input,	200,	1,	30000
		out2_name,	char *,	Input,	"T",	,	
		PulseTimes,	D_ARRAY_T,	Output,	,	,	
		PulseTimes_size,	int,	Input,	12,	1,	20
		PulseTrainSequence,	char *,	Input,	"10101",	,	
		NumbPulses,	int,	Input,	4,	1,	8
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"

double *VFret = NULL;   //renamed to VFret to stop clash with endurance, ret is for retention, so should be changed again to pulse
double *IFret = NULL;    //renamed stop clash with endurance
double *VMret = NULL;     //renamed stop clash with endurance
double *IMret = NULL;     //renamed stop clash with endurance
double *Tret = NULL;      //renamed stop clash with endurance

void AllocateArraysPulseTrain(int pts);
void FreeArraysPulseTrain();

int PulseTrain_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

extern int debug;
extern int details;

extern int PulseTrain_pulse_ilimitNK(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: PMU_PulseTrain
==================

Description
-----------
The purpose of this routine is to provide an example of how the PMUs might be implemented 
in the characterization of PRAM memory elements. The routine allows specification of 4 pulses 
in one waveform:  RESET, MEASURE, SET, and MEASURE. The parameters of these pulses 
are determined by the user, and the SET pulse amplitude can be swept to generate RI and IV charts.

This routine also allows for the output debug information on voltages/currents for 
both PMU channels for any iteration of the sweep.

Input and output parameters
---------------------------

riseTime 
: The rise/fall fimes for RESET pulse in the waveform. (s)
		
resetV 
: The voltage used to reset PRAM to high resistance state. (V)
		
resetWidth 
: The width of the RESET pulse. Width, in this case,
  is defined as length of the flat portion on the top of the pulse. (s)
		
resetDelay 
: The delay on both sides of the RESET pulse. (s)
		
measV 
: The voltage value used to measure post SET/RESET resistance. (V)
		
measWidth 
: The width of the measure pulse. Width, in this case,
  is defined as length of the flat portion on the top of the pulse. (s)
		
measDelay 
: The rise/fall time and delay around measure pulse. (s)
		
setWidth 
: The width of the SET pulse. Width, in this case, is defined as
  length of the flat portion on the top of the pulse. (s)
		
setFallTime
: The fall and rise time for the set pulse. (s)
		
setDelay 
: The delay around set pulse. (s)
		
setStartV 
: The voltage at which SET Voltage sweep starts. (V)
		
setStopV 
: The voltage at which SET Voltage sweep stops. (V)
		
steps 
: The number of points in the sweep.
		
IRange 
: The current range for the measurements.

max_points 
: The maximum number of points. Default maximum number of points is 30000,
  though it is suggested the operator use smaller number to improve data
  retrieval speed. The routine will automatically adjust the sampling rate.
		
setR 
: The output array of SET resistance.
		
setR_size 
: The size of SET resistances. Should be equal to number of points in the sweep.
		
resetR 
: The output array of RESET resistance.
		
resetR_size 
: The size of RESET resistances. Should be equal to number of points in the sweep.
		
setV 
: The output array of SET voltages.
		
setV_size 
: The size of SET voltages. Should be equal to number of points in the sweep.
		
setI 
: The output array of SET currents.
		
setI_size 
: The size of SET currents. Should be equal to number of points in the sweep.
		
iteration 
: The iteration number in the sweep at which debug wave profiles are collected.
				
out1 
: The array of debug data.
		
out1_size 
: The array size of out1.  

out1_name 
: The debug parameter option. Valid selections are found within the following string:
  "VF|VM|IF|IM|T". For instance, if the user wishes to see reports for just the information
  for VF and IF data, the string should be set up as 'VF|IF'. 

: Letters stand for: 
* First char: V - Voltage, I - Current, T - Time
* Second char: F - force, M - measure

out2 
: The array of debug data.
		
out2_size
: The array size of out2. Should be equal to out1_size.

out2_name 
: The debug parameter option. Valid selections are found within the following string:
  "VF|VM|IF|IM|T". For instance, if the user wishes to see reports for just the information
  for VF and IF data, the string should be set up as 'VF|IF'.

: Letters stand for: 
* First char: V - Voltage, I - Current, T - Time
* Second char: F - force, M - measure

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"

double *VFret = NULL;   //renamed to VFret to stop clash with endurance, ret is for retention, so should be changed again to pulse
double *IFret = NULL;    //renamed stop clash with endurance
double *VMret = NULL;     //renamed stop clash with endurance
double *IMret = NULL;     //renamed stop clash with endurance
double *Tret = NULL;      //renamed stop clash with endurance

void AllocateArraysPulseTrain(int pts);
void FreeArraysPulseTrain();

int PulseTrain_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

extern int debug;
extern int details;

extern int PulseTrain_pulse_ilimitNK(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);

/* USRLIB MODULE MAIN FUNCTION */
int PMU_PulseTrain( double riseTime, double resetV, double resetWidth, double resetDelay, double measV, double measWidth, double measDelay, double setWidth, double setFallTime, double setDelay, double setStartV, double setStopV, int steps, double IRange, int max_points, double *setR, int setR_size, double *resetR, int resetR_size, double *setV, int setV_size, double *setI, int setI_size, int iteration, double *out1, int out1_size, char *out1_name, double *out2, int out2_size, char *out2_name, double *PulseTimes, int PulseTimes_size, char *PulseTrainSequence, int NumbPulses, int ClariusDebug )
{
/* USRLIB MODULE CODE */
  char mod[] = "PMU_PulseTrain";
  char inst[] = "PMU1";
  int i, stat;
  double times[60]; // original value was 20, it should be fine if this is a large number
  double volts[60];    // original was 21 [for some unknown reason there is a extra value stored for volt when making up the seg_arb waveform

//  18th Jan 2025 create an array of measMinTime and measMaxTime so that we know where to find measured I and V values in waveform
double measMinTime[60];    
double measMaxTime[60]; 


  // IMPORTANT: be careful of array sizes in pram_sweep_ilimitNK.c
  //   e.g.  for (increm=0; increm<29; increm++)   
  // not the above example is really only for debugging purposes

  int numpts;
  int npts;
  double vbias, resss;
  double ttime;
  int used_pts;
  int used_rate;
   
  double setMinTime, setMaxTime, resetMinTime, resetMaxTime, ivMin, ivMax; //times for finding data
  double setMinTimeOff, setMaxTimeOff, resetMinTimeOff, resetMaxTimeOff;
  double ratio = 0.4; // defines window where to do measurements

  double forceVRange;
  double measVRange;

  forceVRange = fabs(resetV);
  measVRange = 1.0;

  if (ClariusDebug==1) {debug=1;} else {debug=0;};
  if(debug) printf("\n\n\n%s: starts\n", mod);
  int size_pulse_array=0;
  size_pulse_array=strlen(PulseTrainSequence); // need to remove null ptr
  if(debug)printf("Pulse Sequence is %s with length %d\n ", PulseTrainSequence,size_pulse_array);
  
  if (size_pulse_array!=NumbPulses) {
       printf("pulse sequence must of length %d with the format i.e. 00000,10101,11111 \n ", NumbPulses);
      stat = -1;
      goto RETS;
       }


   if(debug)printf("Pulse Sequence is %s \n ", PulseTrainSequence);


//  *****************************
// we need setI and setV to be at least size 2 as measurement before and after pulse
// so have commneted this check out as other steps=1 would not enable the inititate array loop to iterate enough
// normally setV and setI array length is set in labview through setI_size and setV_size, should be set to 12
/*  
   if(steps < 1 || steps != setR_size || steps != resetR_size || steps != setV_size || steps != setI_size || out1_size != out2_size)
    {
      if(debug)printf("%s: Wrong sizes of arrays!\n", mod);
      stat = -1;
      goto RETS;
    }
*/
    
steps=12; // force step size here so arrays initialized correctly and then set back to 1
  // initialize arrays:
  for(i = 0; i < steps; i++)
    {
      setR[i] = 0.0;
      resetR[i] = 0.0;
      setI[i] = 0.0;
      setV[i] = 0.0;
      out1[i]= 0.0;  //added 27/02/2025
      out2[i]= 0.0;  //added 27/02/2025
      }

  // initialize arrays [need 7 measurement for 5 pulses, 1 at beginning, 1 after each pulse, 1 at the end]
     for(i = 0; i < (NumbPulses+2); i++)
   {
    PulseTimes[i]=0.0;
   }
i=0;  //reset to zero as also used in other loops for iteration   
   
steps=1; //   ************** setting back to 1. it needs to be 1 otherwise the large loop won't run below...
         // although step=0 is passed it is not used in the code until now
         //  steps is used here steps determine how many time the large loop runs and therefore how many resetR and set R value in the old program that just collect 1 value for each tieration  *******

      
ttime = 0;  // total time

  //setup a time array:
  // use this as a baseline current in case there is any offset
  resetMinTimeOff = ttime + ratio * resetDelay;  // note; ratio is defined as the window to do measurement and is set to 0.4
  resetMaxTimeOff = ttime + resetDelay * 0.9;
  
  times[0] = resetDelay; //was reset Delay
  ttime += times[0];
  volts[0] = 0.0;

  times[1] = riseTime;
  ttime += times[1];
  volts[1] = 0.0; 

 // ****************
// first pulse is a measurement pulse

  // set up time for resistor measurements to get data back later
  // note these are used to determine the voltage and current value from the many points in the wave
  // I have added an array also but for now use these original values also as called by various functions
  // note ratio = 0.4
  resetMinTime = ttime + ratio * measWidth;  // note this is called reset but should really be measMinTime[0], just keep for other parts of the program see lines below
  resetMaxTime = ttime + measWidth * 0.9;
  // also have these times in an array 
  measMinTime[0] = ttime + ratio * measWidth; 
  measMaxTime[0] = ttime + measWidth * 0.9;
  if(debug)printf("measMinTime[0]= %g; measMaxTime[0]= %g\n", measMinTime[0], measMaxTime[0] );

  times[2] = measWidth; //was resetWidth
  ttime += times[2];
  volts[2] = measV;   //was resetV

  times[3] = riseTime;  // there is no fallTime only a setFallTime but it doesn't matter as riseTime is the same as fallTime in this case
  ttime += times[3];
  volts[3] = measV;   //was resetV

  times[4] = measDelay; //was reset Delay
  ttime += times[4];
  volts[4] = measV;  // not going to zero as want to do a measurement 
  
  times[5] = riseTime;  //don't need this was measDelay, just make it short
  ttime += times[5];
  volts[5] = measV;  // not going to zero as want to do a measurement 

  times[6] = riseTime;  //don't need this was measDelay, just make it short
  ttime += times[6];
  volts[6] = measV;  // not going to zero as want to do a measurement 

/* ----------------  */
// START pulse sequence

// below we add the pulses, 
// note: depending on the number of measurements you need to change arrays and iterations in the other two programs, search 20 and 21

int NumberRepeatedPulses=NumbPulses; // Number of Reset Pulses is user defined
int SegmentIterationNumb=7;
int SequenceNumber=0; // 1st value in the array has index 0
for (SegmentIterationNumb=7; SegmentIterationNumb< (7+(NumberRepeatedPulses*4));SegmentIterationNumb+=4)
  {
  if(debug) printf("1st number in the iteration is %d \n",SegmentIterationNumb);

  times[SegmentIterationNumb] = riseTime;
  ttime += times[SegmentIterationNumb];
  volts[SegmentIterationNumb] = measV;  // not going to zero as want to do a measurement 

  times[SegmentIterationNumb+1] = resetWidth;
  ttime += times[SegmentIterationNumb+1];
  printf("pulse %d is %c \n", SequenceNumber, PulseTrainSequence[SequenceNumber]);
  if ('1'==PulseTrainSequence[SequenceNumber]) {if(debug) printf("yes a 1\n"); volts[SegmentIterationNumb+1] = resetV;} else {if(debug) printf("yes a 0\n"); volts[SegmentIterationNumb+1] = measV;};

  times[SegmentIterationNumb+2] = setFallTime;  // was measDelay
  ttime += times[SegmentIterationNumb+2];
  if ('1'==PulseTrainSequence[SequenceNumber]) {volts[SegmentIterationNumb+2] = resetV;} else {volts[SegmentIterationNumb+2] = measV;};


  // the "large" pulse is finished now do a measurement
  // measurement times to get data back later
  measMinTime[SequenceNumber+1] = ttime + ratio * (measWidth); 
  measMaxTime[SequenceNumber+1] = ttime + (measWidth * 0.9);  


  times[SegmentIterationNumb+3] = measWidth+resetDelay;  // was measDelay
  ttime += times[SegmentIterationNumb+3];
  volts[SegmentIterationNumb+3] = measV;  // not going to zero as want to do a measurement 

  if(debug) printf("last filled segment number in iteration of the loop is %d \n",SegmentIterationNumb+3);

  SequenceNumber++;
 }


// note: SegmentIterationNumb in the loop is increased but then For loop exist
if(debug) printf("Final segment iteration in the loop is %d, should be another 4\n",SegmentIterationNumb);
// volts[SegmentIterationNumb] = 0.0; // should be iteration 7 + (n*4)= 27 for 4 pulses in the sequence

// end of of pulse sequence

/* ----------------  */
// last pulse (number six for 4 pulses in the sequence is a measurement pulse)

// SegmentIterationNumb should be 23
  times[SegmentIterationNumb] = riseTime;   //was measDelay
  ttime += times[SegmentIterationNumb];
  volts[SegmentIterationNumb] = measV;  // not going to zero as want to do a measurement 

  // measurement times to get data back later
  if(debug) printf("Sequence Number is %d\n",SequenceNumber); //is 4 here so need to increases by 1
  measMinTime[SequenceNumber+1] = ttime + ratio * measWidth; 
  measMaxTime[SequenceNumber+1] = ttime + measWidth * 0.9;

  times[SegmentIterationNumb+1] = measWidth;
  ttime += times[SegmentIterationNumb+1];
  volts[SegmentIterationNumb+1]=measV; 

  times[SegmentIterationNumb+2] = setFallTime; //was measDelay
  ttime += times[SegmentIterationNumb+2];
  volts[SegmentIterationNumb+2]=measV;  

  times[SegmentIterationNumb+3] = measDelay;
  ttime += times[SegmentIterationNumb+3];  //should be 26 [for four pulses]
  volts[SegmentIterationNumb+3] = 0.0;

  times[SegmentIterationNumb+4] = 500e-9; //new 26/02/2025
  ttime += times[SegmentIterationNumb+4];//new 26/02/2025
  volts[SegmentIterationNumb+4] = 0.0; // need this in original programm hmmmmm no seg time associated with this! might need to add on this after deciding upon the number of pulses

  times[SegmentIterationNumb+5] = 500e-9; //new 26/02/2025
  ttime += times[SegmentIterationNumb+5];//new 26/02/2025
volts[SegmentIterationNumb+5] = 0.0; // extra one added as manual has two zeros at then end!
if(debug) printf("Before setting NewVoltsSize, SegementIterationNumb+5 is %d\n\n",SegmentIterationNumb+5);

// SegmentIterationNumb+5 is now 28 [for four pulses]
// 
int NewVoltsSize=SegmentIterationNumb+6; // add another as arrays start at 0, so number is 28, and TimeSize is 1 less so 27 it is critical these sizes are correct otherwise it crashes 
if(debug) printf("NewVoltsSize is %d\n\n",NewVoltsSize);


/* ------end of all pulses----------  */

  used_rate = ret_getRate(ttime, max_points, &used_pts, &npts);
  if(debug) printf("%s: for requested time:%g and max_points:%d number of points to allocate:%d\n",
   mod, ttime, max_points, used_pts);

  AllocateArraysPulseTrain(used_pts);

// ****************************
// ****Important make sure steps is 1 in the labview code otherwise this routine won't run
// ********************************
// we aren't sweeping the set Voltage for this PulseTrain but PulseTrain_pulse_ilimitNK is called within this loop that can increase the setV for the setV sweep
// make sure steps is 1 in the labview code otherwise it will sweep

  //do a sweep
  for(i = 0; i < steps; i++)
    {
      // correct voltage array:
      if(steps > 1)
    vbias = setStartV + i * (setStopV - setStartV)/(steps - 1);
      else
    vbias = setStartV;

  //    volts[12] = vbias; //not needed as Set is not sweeped in this code
  //    volts[13] = vbias;

/* ------------------------------------------------------------------------------------------  */
// this calls PulseTrain_pulse_ilimitNK in "PulseTrain_pulse_ilimitNK.c", it sets Force Channel to 1 and Measurement Channel 2 (2nd and 7th parameter)
// and collects forced voltage and current values from both the ForceCh and MeasureCh channels.
// The segments are created based on the settings provided by the operator within the 'Volts' and 'Times' input arrays, and measurements 
// are returned via of the voltage(VF and VM) and current (IF and IM) output arrays for both channels.

      stat = PulseTrain_pulse_ilimitNK
    ( inst, 
      (long) 1, forceVRange, IRange, 
      0.0, 0.0,
      (long) 2, measVRange, IRange, max_points, 0.0, 
      volts, NewVoltsSize, times, NewVoltsSize-1, 
      VFret, used_pts, IFret, used_pts, VMret, used_pts, 
      IMret, used_pts, Tret, used_pts, &numpts 
      );

 //note:  The iteration number in the sweep at which debug wave profiles are collected.
 // note: this code isn't needed
 // start of print debug information

      /*
     if(iteration == i + 1)
     {    
         if(debug) printf("%s: Reporting %s and %s\n", mod, out1_name, out2_name);

         // no need to report (debug) out1 values for the PulseTrain program so this code should not do anything   
         //let's report values for out1
          if(0 == strcmp(out1_name, "VF"))
          {
              ret_report_values(VFret, numpts, out1, out1_size);            
          }
          else if(0 == strcmp(out1_name, "IF"))
          {
              ret_report_values(IFret, numpts, out1, out1_size);            
          }
          else if(0 == strcmp(out1_name, "VM"))
          {
              ret_report_values(VMret, numpts, out1, out1_size);            
          }
          else if(0 == strcmp(out1_name, "IM"))
          {
              ret_report_values(IMret, numpts, out1, out1_size);            
          }
          else          
          {
              ret_report_values(Tret, numpts, out1, out1_size);            
          } 
         //let's report values for out2
          if(0 == strcmp(out2_name, "VF"))
          {
              ret_report_values(VFret, numpts, out2, out2_size);            
          }
          else if(0 == strcmp(out2_name, "IF"))
          {
              ret_report_values(IFret, numpts, out2, out2_size);            
          }
          else if(0 == strcmp(out2_name, "VM"))
          {
              ret_report_values(VMret, numpts, out2, out2_size);            
          }
          else if(0 == strcmp(out2_name, "IM"))
          {
              ret_report_values(IMret, numpts, out2, out2_size);            
          }
          else          
          {
              ret_report_values(Tret, numpts, out2, out2_size);            
          } 
     }

      if(stat < 0)
        {
          if(debug)printf("%s: Error in PulseTrain_pulseNK on %d iteration\n", mod, i);
          stat = -90;
          goto RETS;
        }
*/ 
// end of print debug information
      // *******************
      // Get set resistance
      // *******************

      // this code is not needed as we don't get the set resistance
 /*    
      stat = ret_find_value(IMret, Tret, numpts, setMinTime, setMaxTime, &resss);
      if(debug) printf("%s: Average Current=%g for SET in time interval (seconds): %g and %g\n", mod, resss, setMinTime, setMaxTime);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding set resistance\n", mod);
          stat = -91;
          goto RETS;
        }
      setR[i] = resss;

      stat = ret_find_value(IMret, Tret, numpts, setMinTimeOff, setMaxTimeOff, &resss);
      if(debug) printf("%s: Average Offset Current=%g for SET in time interval (seconds): %g and %g \n (Note: just one Off value is for all probe measurements and this is at the beginning of the sequence)\n", mod, resss, setMinTimeOff, setMaxTimeOff);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding set resistance\n", mod);
          stat = -91;
          goto RETS;
        }
      setR[i] = fabs(measV/(setR[i] - resss));
      if(setR[i] > 1e4/IRange) 
        setR[i] = 1e4/IRange;
      if(debug)printf("%s: setR[%d] = %g\n", mod, i, resss);
 */
      
      // *******************
      // Was get reset resistance now it is the initial resistance before each probe resistance resetMinTime,resetMaxTime
      // note the value of i is for the old program which allow the Set to be swept i times, here i=0 as only 1 iteration
      // *******************
      stat = ret_find_value(IMret, Tret, numpts, resetMinTime, resetMaxTime, &resss);
      if(debug) printf("\n\n ********* Initial Device Resistance Before Pulses *********\n");
      if(debug) printf("%s: Average Current=%g in the Initial Device Measurement with V=measV over time interval (seconds): %g and %g\n", mod, resss, resetMinTime, resetMaxTime);
        if(stat < 0)
        {
          if(debug)printf("%s: Error in finding initial resistance\n", mod);
          stat = -92;
          goto RETS;
        }
      resetR[i] = resss;   //coders have re-used this variable, as here it is a current but further down it is a resistance (after removing the off state curren) 

  // this part used to get the off current so that it could give a more accurate values for the resistance
  // not really needed now
      stat = ret_find_value(IMret, Tret, numpts, resetMinTimeOff, resetMaxTimeOff, &resss);
      if(debug) printf("%s: ********* Off Current Properties *********\n",mod);
      if(debug) printf("%s: Average OFF Current=%g for before measurements in time interval (seconds): %g and %g\n (Note: just one Off value is used for all probe measurements and this is at the beginning of the sequence)\n", mod, resss, resetMinTimeOff, resetMaxTimeOff);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding reset resistance\n", mod);
          stat = -92;
          goto RETS;
        }
      resetR[i] = fabs(measV/(resetR[i] - resss));  //previously a current, now changed to a resistance
      if(resetR[i] > 1e4/IRange) 
        resetR[i] = 1e4/IRange;
          

      if(debug)printf("\n\n ********* Resistance Before High Voltage Pulses (Note: will be the same as Prob[0] below *********\n");
      if(debug)printf("%s: Resistance[%d]  (including allowance for Offset Current) = %g\n", mod, i, resetR[i]);

      //current and voltage
      stat = ret_find_value(VFret, Tret, numpts, resetMinTime, resetMaxTime, &resss);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding voltage value\n", mod);
          stat = -93;
          goto RETS;
        }
      setV[i] = resss;
      if(debug)printf("%s: setV[%d] = %g\n", mod, i, resss);
    

    //  stat = ret_find_value(IFret, Tret, numpts, resetMinTime, resetMaxTime, &resss);
      stat = ret_find_value(IMret, Tret, numpts, resetMinTime, resetMaxTime, &resss);

      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding current value\n", mod);
          stat = -94;
          goto RETS;
        }
        
          setI[i] = resss;
      if(debug)printf("%s: setI[%d] = %g\n", mod, i, resss);
      if(debug)printf("%s: Probe Resistance[%d] [note include offset current] = %g\n", mod, i, setV[i]/setI[i]);


// new code 19th Jan 2025
// *******************
// Get probe resistances
// *******************
if(debug) printf("\n\n *********   Getting Probe Resistances *********\n");

int ProbeResNumb=0;

// changed ProbeResNumb, was 11 then 6 (for 4 pulses) then NumbPulses+2 (now user defined)as just want to get the start and end resistance and resistance after each pulse, so 6 altogether
for (ProbeResNumb=0; ProbeResNumb<(NumbPulses+2);ProbeResNumb++)  
    {
      stat = ret_find_value(IMret, Tret, numpts, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &resss);
      if(debug) printf("\n\n Probe Number: %d \n %s Average Current=%g for RESET in time interval (seconds): %g and %g\n",ProbeResNumb, mod, resss, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb]);
        if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe resistance\n", mod);
          stat = -92;
          goto RETS;
        }
      //resetR[i] = resss;
      resetR[ProbeResNumb] = resss;   // here this is a current, later it changes to a resistance


    // not sure if this bit is needed
    // think it remove the baseline current/resistance as fabs(measV/(resetR[i] - resss));
    // ***** 
      stat = ret_find_value(IMret, Tret, numpts, resetMinTimeOff, resetMaxTimeOff, &resss);
      if(debug) printf("%s: Average OFF Current=%g for RESET in time interval (seconds): %g and %g\n", mod, resss, resetMinTimeOff, resetMaxTimeOff);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe resistance\n", mod);
          stat = -92;
          goto RETS;
        }
      //resetR[i] = fabs(measV/(resetR[i] - resss));
      resetR[ProbeResNumb] = fabs(measV/(resetR[ProbeResNumb] - resss));  // was a current before and now a resistance

      // if(resetR[i] > 1e4/IRange)  resetR[i] = 1e4/IRange;
      if(resetR[ProbeResNumb] > 1e4/IRange)  resetR[ProbeResNumb] = 1e4/IRange;

      //  *****   
      if(debug)printf("%s: resetR[%d] = %g\n", mod, ProbeResNumb, resss);

      //current and voltage
      //get voltage
      stat = ret_find_value(VFret, Tret, numpts, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &resss);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe voltage value\n", mod);
          stat = -93;
          goto RETS;
        }
      // setV[i] = resss; 
       setV[ProbeResNumb] = resss;         // can use the array of setV values to store the data
      if(debug)printf("%s: setV[%d] = %g\n", mod, ProbeResNumb, resss);

      // get current
      // initially this was IFret i.e. the current measured on the Force channel, changed this to IMret, the current measured on the sense channel
      stat = ret_find_value(IMret, Tret, numpts, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &resss);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe current value\n", mod);
          stat = -94;
          goto RETS;
        }
      // setI[i] = resss;
       setI[ProbeResNumb] = resss;         // can use the array of setI values to store the data
      if(debug)printf("%s: setI[%d] = %g\n", mod, ProbeResNumb, resss);

      // print out resistance
      if(debug)printf("%s: Probe Resistance[%d] = %g\n", mod, ProbeResNumb, setV[ProbeResNumb]/setI[ProbeResNumb]);


      // return pulse times as an array
      PulseTimes[ProbeResNumb]=(measMaxTime[ProbeResNumb]+measMinTime[ProbeResNumb])/2;
      
     }   // end of loop to determine the probe measurements

if(debug)printf("\n\n");
int looper=0;
 if(debug)
  { 
  // changed "looper<11" from 11 to 6 (now NumbPulses+2 as user defined) as want start and end resistance and resistance after each pulse
  for (looper=0; looper<(NumbPulses+2);looper++) {
    printf("PulseTimes %d: %g\n",looper, PulseTimes[looper]);    }
  }


} // *************** this is a damn big loop! carries out the Set Sweep and call to define the segment and actions

  stat = 1; // measurement successfuly carried out return a success value
  if(debug) printf("********* Success ************\n"); 

  RETS:
  FreeArraysPulseTrain();
  if(debug) printf("********* Exiting ****** with status %d ******\n",stat); 
  return stat;
}



__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size)
{
    int i, j;
    double ratio;
    extern int debug;
    extern int details;

    //****************** modifed by NK 25 Oct 24
    //details=1;
    //******************
    
    char mod[] = "report_values";
    if(out_size < 1 || numpts < 1)
        return;

    ratio = (((double)numpts - 1.0)/((double)out_size - 1.0));
    for(i = 0; i < out_size; i++)
    {
        j = (int)(ratio * i);
        out[i] = T[j];
        if(debug && details)printf("%s: out[%d,%d] = %g\n", mod, i, j, out[i]);
    }
    if(debug && details)printf("%s: numpts:%d\n", mod, numpts);
}

/* ----------------  */

// renamed function below so it doesn't clash with the same function in endurance and to be stand-alone
void AllocateArraysPulseTrain(int pts)
{
   if(debug) printf("Allocating Arrays - Number of pts is %d \n\n",pts);
   VFret = (double *)calloc(pts, sizeof(double));
   IFret = (double *)calloc(pts, sizeof(double));
   VMret = (double *)calloc(pts, sizeof(double));
   IMret = (double *)calloc(pts, sizeof(double));
   Tret = (double *)calloc(pts, sizeof(double));
}


/* ----------------  */

// renamed function below so it doesn't clash with the same function in endurance and to be stand-alone
void FreeArraysPulseTrain()
{
  if(debug) printf("Freeing Arrays\n\n");
   if(NULL != VFret) free(VFret);
   if(NULL != IFret) free(IFret);
   if(NULL != VMret) free(VMret);
   if(NULL != IMret) free(IMret);
   if(NULL != Tret) free(Tret);
}

__declspec( dllexport ) int ret_find_value (double *vals, double *t, int pts, double start, double stop, double *result)
{
  int stat = -1;
  double sum = 0;
  int i = 0;
  int actpts = 0;
  
 *result = -999.0;

  while(i < pts && t[i] <= stop)
    {
      if(t[i] >= start)
    {
      sum += vals[i];
      actpts ++;
    }
      i++;
    }
  
  if(actpts > 0)
    {
      *result = sum/actpts;
      stat = 1;
    }
  
  return stat;

/* USRLIB MODULE END  */
} 		/* End PMU_PulseTrain.c */

