/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_retention
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 33
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
		PulseTimesSize,	int,	Input,	12,	1,	20
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"

double *VFret = NULL;   //renamed to VFret to stop clash with endurance
double *IFret = NULL;    //renamed stop clash with endurance
double *VMret = NULL;     //renamed stop clash with endurance
double *IMret = NULL;     //renamed stop clash with endurance
double *Tret = NULL;      //renamed stop clash with endurance

void AllocateArraysRetention(int pts);
void FreeArraysRetention();

int retention_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

extern int debug;
extern int details;

extern int retention_pulse_ilimitNK(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: PMU_retention
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

double *VFret = NULL;   //renamed to VFret to stop clash with endurance
double *IFret = NULL;    //renamed stop clash with endurance
double *VMret = NULL;     //renamed stop clash with endurance
double *IMret = NULL;     //renamed stop clash with endurance
double *Tret = NULL;      //renamed stop clash with endurance

void AllocateArraysRetention(int pts);
void FreeArraysRetention();

int retention_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

extern int debug;
extern int details;

extern int retention_pulse_ilimitNK(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);

/* USRLIB MODULE MAIN FUNCTION */
int PMU_retention( double riseTime, double resetV, double resetWidth, double resetDelay, double measV, double measWidth, double measDelay, double setWidth, double setFallTime, double setDelay, double setStartV, double setStopV, int steps, double IRange, int max_points, double *setR, int setR_size, double *resetR, int resetR_size, double *setV, int setV_size, double *setI, int setI_size, int iteration, double *out1, int out1_size, char *out1_name, double *out2, int out2_size, char *out2_name, double *PulseTimes, int PulseTimesSize, int ClariusDebug )
{
/* USRLIB MODULE CODE */
  char mod[] = "PMU_retention";
  char inst[] = "PMU1";
  int i, stat;
  double times[100]; // was 52, increased to allow up to 20 repeated measurements: 20 + (20*4) = 100
  double volts[101];    // was 53, increased to allow up to 20 repeated measurements: 20 + (20*4) + 1 = 101

//  18th Jan 2025 create an array of measMinTime and measMaxTime so that we know where find I and V in waveform
double measMinTime[25]; // was 12, increased to allow up to 20 repeated measurements + initial + reset measurement + 2 extra
double measMaxTime[25]; // was 12, increased to allow up to 20 repeated measurements + initial + reset measurement + 2 extra


  // IMPORTANT: need to increase array size in pram_sweep_ilimitNK.c

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
  if(debug)printf("\n\n%s: starts\n", mod);

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
      PulseTimes[i]=0.0;
    }
steps=1;
      
  ttime = 0;

  //setup a time array:

  times[0] = resetDelay; //was reset Delay
  ttime += times[0];
  volts[0] = 0.0;

  times[1] = riseTime;
  ttime += times[1];
  volts[1] = 0.0; 

 // ****************
// first pulse is a measurement pulse
  measMinTime[0] = ttime + ratio * measWidth; 
  measMaxTime[0] = ttime + measWidth * 0.9;

  times[2] = measWidth; //was resetWidth
  ttime += times[2];
  volts[2] = measV;   //was resetV

  times[3] = riseTime;  // there is no fallTime only a setFallTime but it doesn't matter as riseTime is the same as fallTime in this case
  ttime += times[3];
  volts[3] = measV;   //was resetV

  times[4] = measDelay; //was reset Delay
  ttime += times[4];
  volts[4] = 0.0;

  resetMinTimeOff = ttime + ratio * measDelay;  // note; ratio is defined as the window to do measurement and is set to 0.4
  resetMaxTimeOff = ttime + measDelay * 0.9;
  

 if(debug)printf("measMinTime[0]= %g; measMaxTime[0]= %g\n", measMinTime[0], measMaxTime[0] );

  times[5] = riseTime;  //don't need this was measDelay, just make it short
  ttime += times[5];
  volts[5] = 0.0;

  times[6] = riseTime;  //don't need this was measDelay, just make it short
  ttime += times[6];
  volts[6] = 0.0;

  // set up time for resistor measurements
  // note these are used to determine the voltage and current value from the many points in the wave
 // resetMinTime = ttime + ratio * measWidth;  // note this is called reset but should really be measMinTime[0]
 // resetMaxTime = ttime + measWidth * 0.9;
//measMinTime[0] = ttime + ratio * measWidth; 
//measMaxTime[0] = ttime + measWidth * 0.9;

/* ----------------  */
// second pulse is a reset pulse

  times[7] = resetWidth; //was measWidth
  ttime += times[7];
  volts[7] = resetV;  //was measV

  times[8] = resetDelay; //was measDelay
  ttime += times[8];
  volts[8] = resetV;     //was measV

  times[9] = resetDelay; //was measDelay
  ttime += times[9];
  volts[9] = 0.0;


  times[10] = measDelay; // was setDelay
  ttime += times[10];
  volts[10] = 0.0;
    
  times[11] = riseTime;   // no measFallTime but can use this
  ttime += times[11];
  volts[11] = 0.0;

  // set where measure I/V
//  ivMin = ttime + ratio * resetWidth;   //was setWidth
 // ivMax = ttime + resetWidth;            //was setWidth

//change 18th Jan 2025
resetMinTime = ttime + ratio * resetWidth; 
resetMaxTime  = ttime + resetWidth;  


/* ----------------  */
// 3rd pulse is a measurement pulse 

  times[12] = riseTime;    // no measFallTime but can use this
  ttime += times[12];
  volts[12] = 0.0;


  times[13] = measWidth;    //was setWidth
measMinTime[1] = ttime + ratio * measWidth; 
measMaxTime[1] = ttime + measWidth * 0.9;
  ttime += times[13];
  volts[13] = measV;          // was 0.0


  times[14] = setFallTime;   //was setDelay
  ttime += times[14];
  volts[14] = measV; // this is correct, can't set zero 

  setMinTimeOff = ttime + ratio * measDelay;
  setMaxTimeOff = ttime + measDelay * 0.9;

  times[15] = measDelay;   //was measDelay
  ttime += times[15];
  volts[15] = 0.0;


  // set up time for resistor measurements
//  setMinTime = ttime + ratio * measWidth;
//  setMaxTime = ttime + measWidth * 0.9;

/* ----------------  */
// fourth pulse is a measurement pulse

  times[16] = riseTime;   //was measDelay
  ttime += times[16];
  volts[16] = 0.0;

  times[17] = measWidth;
measMinTime[2] = ttime + ratio * measWidth; 
measMaxTime[2] = ttime + measWidth * 0.9;
  ttime += times[17];
  volts[17] = measV;

  times[18] = setFallTime; //was measDelay
  ttime += times[18];
  volts[18] = measV;

  times[19] = measDelay;
  ttime += times[19];
  volts[19] = 0.0;

  //volts[20] = 0.0; // hmmmmm no seg time associated with this! might need to add on this after deciding upon the number of pulses



/* ----------------  */
// below we add the remainder of the more repeated measurements, there are 12 pulse in total, 1st is a measurement probe, 2nd is pulse, the remaining 10 are probes 

// note: depending on the number of measurements you need to change arrays and iterations in the other two programs, search 20 and 21


// NumberRepeatedMeasurements is hardcoded to 16 for repeated measurements
int NumberRepeatedMeasurements = 16;
int MeasurementIteration;
int PulseIterationNum=1;
for (MeasurementIteration=20; MeasurementIteration< (20+(NumberRepeatedMeasurements*4));MeasurementIteration+=4)
{
  if(debug) printf("%d \n",MeasurementIteration);

  times[MeasurementIteration] = riseTime;
  ttime += times[MeasurementIteration];
  volts[MeasurementIteration] = 0;

  times[MeasurementIteration+1] = measWidth;
measMinTime[2+PulseIterationNum] = ttime + ratio * measWidth; 
measMaxTime[2+PulseIterationNum] = ttime + measWidth * 0.9;
PulseIterationNum++;

  ttime += times[MeasurementIteration+1];
  volts[MeasurementIteration+1] = measV;

  times[MeasurementIteration+2] = setFallTime;  // was measDelay
  ttime += times[MeasurementIteration+2];
  volts[MeasurementIteration+2] = measV;

  times[MeasurementIteration+3] = measDelay;  // was measDelay
  ttime += times[MeasurementIteration+3];
  volts[MeasurementIteration+3] = 0.0;

  //volts[MeasurementIteration+3] = 0.0;

  if(debug) printf("2nd last segment iteration is %d \n",MeasurementIteration+3);

}
if(debug) printf("Final segment iteration is %d \n",MeasurementIteration);
volts[MeasurementIteration] = 0.0; // should be iteration 20 + (n*4): 35 for 5 loops

int NewVoltsSize=MeasurementIteration+1;  // note: number of voltages no longer 21


/* ------end of all pulses----------  */

  used_rate = ret_getRate(ttime, max_points, &used_pts, &npts);
  if(debug) printf("%s: for requested time:%g and max_points:%d number of points to allocate:%d\n",
   mod, ttime, max_points, used_pts);

  AllocateArraysRetention(used_pts);

// we aren't sweeping the set Voltage for this Retention so the following code should no do anything
// note steps here is the sweep on the set Voltage, it is 1 
  //do a sweep
  for(i = 0; i < steps; i++)
    {
      // correct voltage array:
      if(steps > 1)
    vbias = setStartV + i * (setStopV - setStartV)/(steps - 1);
      else
    vbias = setStartV;

     // volts[12] = vbias;
    //  volts[13] = vbias;

/* ------------------------------------------------------------------------------------------  */
// this calls retention_pulse_ilimitNK in "retention_pulse_ilimitNK.c", it sets Force Channel to 1 and Measurement Channel 2 (2nd and 7th parameter)
// and collects forced voltage and current values from both the ForceCh and MeasureCh channels.
// The segments are created based on the settings provided by the operator within the 'Volts' and 'Times' input arrays, and measurements 
// are returned via of the voltage(VF and VM) and current (IF and IM) output arrays for both channels.

      stat = retention_pulse_ilimitNK
    ( inst, 
      (long) 1, forceVRange, IRange, 
      0.0, 0.0,
      (long) 2, measVRange, IRange, max_points, 0.0, 
      volts, NewVoltsSize, times, NewVoltsSize-1, 
      VFret, used_pts, IFret, used_pts, VMret, used_pts, 
      IMret, used_pts, Tret, used_pts, &numpts 
      );
      
     if(iteration == i + 1)
     {    
         if(debug) printf("%s: Reporting %s and %s\n", mod, out1_name, out2_name);

         // no need to report (debug) out1 values for the retention program so this code should no do anything   
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
          if(debug)printf("%s: Error in retention_pulseNK on %d iteration\n", mod, i);
          stat = -90;
          goto RETS;
        }

      // *******************
      // Get set resistance
      // *******************

      // this code is not needed as we don't get the set resistance
      
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
      if(debug) printf("%s: Average Offset Current=%g for SET in time interval (seconds): %g and %g\n", mod, resss, setMinTimeOff, setMaxTimeOff);
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
      
      // *******************
      // Get reset resistance
      // note the value of i is for the old program which allow the Set to be swept i times, here i=0 as only 1 iteration
      // *******************
      stat = ret_find_value(IMret, Tret, numpts, resetMinTime, resetMaxTime, &resss);
      if(debug) printf("%s: Average Current=%g for RESET in time interval (seconds): %g and %g\n", mod, resss, resetMinTime, resetMaxTime);
        if(stat < 0)
        {
          if(debug)printf("%s: Error in finding reset resistance\n", mod);
          stat = -92;
          goto RETS;
        }
      resetR[i] = resss;

      stat = ret_find_value(IMret, Tret, numpts, resetMinTimeOff, resetMaxTimeOff, &resss);
      if(debug) printf("%s: Average OFF Current=%g for RESET in time interval (seconds): %g and %g\n", mod, resss, resetMinTimeOff, resetMaxTimeOff);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding reset resistance\n", mod);
          stat = -92;
          goto RETS;
        }
      resetR[i] = fabs(measV/(resetR[i] - resss));
      if(resetR[i] > 1e4/IRange) 
        resetR[i] = 1e4/IRange;
          
      if(debug)printf("%s: resetR[%d] = %g\n", mod, i, resss);

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

      stat = ret_find_value(IFret, Tret, numpts, resetMinTime, resetMaxTime, &resss);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding current value\n", mod);
          stat = -94;
          goto RETS;
        }
      setI[i] = resss;
      if(debug)printf("%s: setI[%d] = %g\n", mod, i, resss);

// new code 18th Jan 2025
// *******************
// Get probe resistances
// *******************
int ProbeResNumb=0;

// Loop through all probe measurements: initial + reset + NumberRepeatedMeasurements
// Limit to array sizes to avoid out-of-bounds access
int maxProbeMeasurements = (NumberRepeatedMeasurements + 3);
if (maxProbeMeasurements > setV_size) maxProbeMeasurements = setV_size;
if (maxProbeMeasurements > setI_size) maxProbeMeasurements = setI_size;
if (maxProbeMeasurements > resetR_size) maxProbeMeasurements = resetR_size;
if (maxProbeMeasurements > PulseTimesSize) maxProbeMeasurements = PulseTimesSize;

for (ProbeResNumb=0; ProbeResNumb<maxProbeMeasurements;ProbeResNumb++)  
    {
      stat = ret_find_value(IMret, Tret, numpts, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &resss);
      if(debug) printf("\nProbe Number: %d \n %s: Average Current=%g for RESET in time interval (seconds): %g and %g\n", ProbeResNumb, mod, resss, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb]);
        if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe resistance\n", mod);
          stat = -92;
          goto RETS;
        }
      // Store in resetR array, but only if within bounds
      if (ProbeResNumb < resetR_size) {
        resetR[ProbeResNumb] = resss;
      }

    // not sure if this bit is needed, something to do with the end of the 1st pulse
    // think it might remove the baseline resistance as fabs(measV/(resetR[i] - resss));
    // ***** 
      stat = ret_find_value(IMret, Tret, numpts, resetMinTimeOff, resetMaxTimeOff, &resss);
      if(debug) printf("%s: Average OFF Current=%g for RESET in time interval (seconds): %g and %g\n", mod, resss, resetMinTimeOff, resetMaxTimeOff);
      if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe resistance\n", mod);
          stat = -92;
          goto RETS;
        }
      if (ProbeResNumb < resetR_size) {
        resetR[ProbeResNumb] = fabs(measV/(resetR[ProbeResNumb] - resss));
        if(resetR[ProbeResNumb] > 1e4/IRange) 
          resetR[ProbeResNumb] = 1e4/IRange;
      }
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
      if (ProbeResNumb < setV_size) {
        setV[ProbeResNumb] = resss;         // can use the array of setV values to store the data
      }
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
      if (ProbeResNumb < setI_size) {
        setI[ProbeResNumb] = resss;         // can use the array of setI values to store the data
      }
      if(debug)printf("%s: setI[%d] = %g\n\n", mod, ProbeResNumb, resss);

      // return pulse times as an array
      if (ProbeResNumb < PulseTimesSize) {
        PulseTimes[ProbeResNumb]=(measMaxTime[ProbeResNumb]+measMinTime[ProbeResNumb])/2;
      }
      
     }   // end of loop to determine the probe measurements

int looper;
int maxLoops = (NumberRepeatedMeasurements+3);
if (maxLoops > PulseTimesSize) maxLoops = PulseTimesSize;
 if(debug)
  { 
  for (looper=0; looper<maxLoops;looper++) {
    printf("PulseTimes %d: %g\n",looper, PulseTimes[looper]);    }
  }
} 

  stat = 1;

  RETS:
  FreeArraysRetention();
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
void AllocateArraysRetention(int pts)
{
   VFret = (double *)calloc(pts, sizeof(double));
   IFret = (double *)calloc(pts, sizeof(double));
   VMret = (double *)calloc(pts, sizeof(double));
   IMret = (double *)calloc(pts, sizeof(double));
   Tret = (double *)calloc(pts, sizeof(double));
}


/* ----------------  */

// renamed function below so it doesn't clash with the same function in endurance and to be stand-alone
void FreeArraysRetention()
{
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
} 		/* End PMU_retention.c */

