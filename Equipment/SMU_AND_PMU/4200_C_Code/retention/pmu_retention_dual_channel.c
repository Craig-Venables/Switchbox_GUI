/* USRLIB MODULE INFORMATION

	MODULE NAME: pmu_retention_dual_channel
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 42
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
		NumbMeasPulses,	int,	Input,	8,	8,	1000
		NumInitialMeasPulses,	int,	Input,	1,	1,	100
		NumPulses,	int,	Input,	5,	1,	100
		PulseWidth,	double,	Input,	1e-6,	2e-8,	1
		PulseV,	double,	Input,	4,	-20,	20
		PulseRiseTime,	double,	Input,	3e-8,	2e-8,	1
		PulseFallTime,	double,	Input,	3e-8,	2e-8,	1
		PulseDelay,	double,	Input,	1e-6,	2e-8,	1
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

double *VFret = NULL;   //renamed to VFret to stop clash with endurance
double *IFret = NULL;    //renamed stop clash with endurance
double *VMret = NULL;     //renamed stop clash with endurance
double *IMret = NULL;     //renamed stop clash with endurance
double *Tret = NULL;      //renamed stop clash with endurance

void AllocateArraysRetention(int pts);
void FreeArraysRetention();

int ACraig1_retention_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

extern int debug;
extern int details;

extern int ACraig1_retention_pulse_ilimitNK(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: pmu_retention_dual_channel
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
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

double *VFret = NULL;   //renamed to VFret to stop clash with endurance
double *IFret = NULL;    //renamed stop clash with endurance
double *VMret = NULL;     //renamed stop clash with endurance
double *IMret = NULL;     //renamed stop clash with endurance
double *Tret = NULL;      //renamed stop clash with endurance

void AllocateArraysRetention(int pts);
void FreeArraysRetention();

int ACraig1_retention_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

extern int debug;
extern int details;

extern int retention_pulse_ilimit_dual_channel(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);

/* USRLIB MODULE MAIN FUNCTION */
int pmu_retention_dual_channel( double riseTime, double resetV, double resetWidth, double resetDelay, double measV, double measWidth, double measDelay, double setWidth, double setFallTime, double setDelay, double setStartV, double setStopV, int steps, double IRange, int max_points, double *setR, int setR_size, double *resetR, int resetR_size, double *setV, int setV_size, double *setI, int setI_size, int iteration, double *out1, int out1_size, char *out1_name, double *out2, int out2_size, char *out2_name, double *PulseTimes, int PulseTimesSize, int NumbMeasPulses, int NumInitialMeasPulses, int NumPulses, double PulseWidth, double PulseV, double PulseRiseTime, double PulseFallTime, double PulseDelay, int ClariusDebug )
{
/* USRLIB MODULE CODE */
  char mod[] = "pmu_retention_dual_channel";
  char inst[] = "PMU1";
  int i, stat;
  double *times = NULL;
  double *volts = NULL;
  int times_count = 0;
  int volts_count = 0;

  double *measMinTime = NULL;
  double *measMaxTime = NULL;
  int recordedProbeCount = 0;
  int probeCapacity = 0;


  // IMPORTANT: need to increase array size in pram_sweep_ilimitNK.c

  int numpts;
  int npts;
  double vbias, resss;
  double ttime;
  int used_pts;
  int used_rate;
   
  double ratio = 0.4; // defines window where to do measurements

  double forceVRange;
  double measVRange;

  // Use maximum of resetV and PulseV for voltage range
  forceVRange = fabs(resetV) > fabs(PulseV) ? fabs(resetV) : fabs(PulseV);
  if (forceVRange < 1.0) forceVRange = 1.0;
  measVRange = 1.0;

  if (NumbMeasPulses < 2)
  {
    if(debug) printf("%s: NumbMeasPulses must be at least 2 (got %d)\n", mod, NumbMeasPulses);
    stat = -201;
    goto RETS;
  }

  if (NumInitialMeasPulses < 1)
  {
    if(debug) printf("%s: NumInitialMeasPulses must be at least 1 (got %d)\n", mod, NumInitialMeasPulses);
    stat = -212;
    goto RETS;
  }

  if (NumPulses < 1)
  {
    if(debug) printf("%s: NumPulses must be at least 1 (got %d)\n", mod, NumPulses);
    stat = -213;
    goto RETS;
  }

  if (PulseWidth < 2e-8 || PulseWidth > 1.0)
  {
    if(debug) printf("%s: PulseWidth must be between 2e-8 and 1.0 (got %g)\n", mod, PulseWidth);
    stat = -214;
    goto RETS;
  }

  if (PulseRiseTime < 2e-8 || PulseRiseTime > 1.0)
  {
    if(debug) printf("%s: PulseRiseTime must be between 2e-8 and 1.0 (got %g)\n", mod, PulseRiseTime);
    stat = -215;
    goto RETS;
  }

  if (PulseFallTime < 2e-8 || PulseFallTime > 1.0)
  {
    if(debug) printf("%s: PulseFallTime must be between 2e-8 and 1.0 (got %g)\n", mod, PulseFallTime);
    stat = -216;
    goto RETS;
  }

  if (PulseDelay < 2e-8 || PulseDelay > 1.0)
  {
    if(debug) printf("%s: PulseDelay must be between 2e-8 and 1.0 (got %g)\n", mod, PulseDelay);
    stat = -217;
    goto RETS;
  }

  // Calculate waveform size dynamically:
  // - Initial delay/rise: 2 segments
  // - Each initial measurement pulse: 4 segments (width, rise, delay, rise)
  // - Pulse sequence: Each pulse has 4 segments (rise, width, fall, delay)
  //   For NumPulses pulses: rise + width + fall + delay (between pulses, except last)
  // Calculate exact segment count needed
  int calc_times_count = 2;  // initial delay + rise
  
  // Initial measurement pulses: Each has 4 segments (width, rise, delay, rise)
  calc_times_count += 4 * NumInitialMeasPulses;
  
  // Pulse sequence: Each pulse has 4 segments (RISE, TOP, FALL, WAIT)
  if (NumPulses > 0)
  {
    calc_times_count += 4 * NumPulses;
  }
  
  // Retention measurement pulses: Each has 6 segments (delay, rise, width, fallDelay, fall, delay)
  calc_times_count += 6 * NumbMeasPulses;
  
  // Add safety margin (10% or minimum 10 segments) to avoid allocation issues
  int safety_margin = calc_times_count / 10;
  if (safety_margin < 10) safety_margin = 10;
  
  times_count = calc_times_count + safety_margin;
  volts_count = times_count + 1;

  if(debug) printf("%s: Allocating waveform buffers - calculated:%d + margin:%d = times_count:%d volts_count:%d (InitialMeas:%d NumPulses:%d RetMeas:%d)\n", 
    mod, calc_times_count, safety_margin, times_count, volts_count, NumInitialMeasPulses, NumPulses, NumbMeasPulses);

  times = (double *)calloc(times_count, sizeof(double));
  volts = (double *)calloc(volts_count, sizeof(double));
  if(times == NULL || volts == NULL)
  {
    if(debug) printf("%s: Unable to allocate segment buffers (times:%d volts:%d)\n", mod, times_count, volts_count);
    stat = -210;
    goto RETS;
  }

  // Probe capacity: initial measurements + retention measurements (no probes for pulse sequence)
  probeCapacity = NumInitialMeasPulses + NumbMeasPulses;
  if (PulseTimes == NULL || setV == NULL || setI == NULL)
  {
    if(debug) printf("%s: Output buffers must not be NULL\n", mod);
    stat = -202;
    goto RETS;
  }

  measMinTime = (double *)calloc(probeCapacity, sizeof(double));
  measMaxTime = (double *)calloc(probeCapacity, sizeof(double));
  if(measMinTime == NULL || measMaxTime == NULL)
  {
    if(debug) printf("%s: Unable to allocate measurement window buffers (capacity %d)\n", mod, probeCapacity);
    stat = -203;
    goto RETS;
  }

  if (PulseTimesSize < probeCapacity || setV_size < probeCapacity || setI_size < probeCapacity)
  {
    if(debug) printf("%s: Output buffer sizes too small. Required: %d (PulseTimes/setV/setI)\n", mod, probeCapacity);
    stat = -204;
    goto RETS;
  }

  for(i = 0; i < PulseTimesSize; ++i)
  {
    PulseTimes[i] = 0.0;
  }

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
  for(i = 0; i < steps && i < setR_size; i++)
    {
      setR[i] = 0.0;
    }
  for(i = 0; i < steps && i < resetR_size; i++)
    {
      resetR[i] = 0.0;
    }
  for(i = 0; i < steps && i < setI_size; i++)
    {
      setI[i] = 0.0;
    }
  for(i = 0; i < steps && i < setV_size; i++)
    {
      setV[i] = 0.0;
    }
steps=1;
      
  ttime = 0;
  int segIdx = 0;  // segment index for times/volts arrays

  // Initial delay and rise time
  times[segIdx] = resetDelay;
  ttime += times[segIdx];
  volts[segIdx] = 0.0;
  segIdx++;

  times[segIdx] = riseTime;
  ttime += times[segIdx];
  volts[segIdx] = 0.0;
  segIdx++;

  // ****************
  // Initial measurement pulses (user definable)
  // ****************
  int initMeasIdx;
  for (initMeasIdx = 0; initMeasIdx < NumInitialMeasPulses; initMeasIdx++)
  {
    if(recordedProbeCount >= probeCapacity)
    {
      if(debug) printf("%s: Probe capacity exceeded while recording initial measurement window %d\n", mod, initMeasIdx);
      stat = -205;
      goto RETS;
    }
    measMinTime[recordedProbeCount] = ttime + ratio * measWidth; 
    measMaxTime[recordedProbeCount] = ttime + measWidth * 0.9; 
    if(debug)printf("Initial measMinTime[%d]= %g; measMaxTime[%d]= %g\n", recordedProbeCount, measMinTime[recordedProbeCount], recordedProbeCount, measMaxTime[recordedProbeCount] );
    recordedProbeCount++;

    times[segIdx] = measWidth;
    ttime += times[segIdx];
    volts[segIdx] = measV;
    segIdx++;

    times[segIdx] = riseTime;
    ttime += times[segIdx];
    volts[segIdx] = measV;
    segIdx++;

    times[segIdx] = measDelay;
    ttime += times[segIdx];
    volts[segIdx] = 0.0;
    segIdx++;

    // Small delay between pulses
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    volts[segIdx] = 0.0;
    segIdx++;
  }

  // ****************
  // Pulse sequence: Multiple pulses in a row (user definable)
  // Each pulse consists of 4 segments: RISE, TOP, FALL, WAIT
  // CRITICAL: seg_arb creates segment i from v[i] (START) to v[i+1] (END) over t[i]
  // So we must: set START voltage v[i], set time t[i], increment, then set END voltage v[i+1]
  // ****************
  int pulseIdx;
  for (pulseIdx = 0; pulseIdx < NumPulses; pulseIdx++)
  {
    if(debug) printf("\n%s: ===== PULSE %d/%d ===== (segIdx=%d)\n", 
      mod, pulseIdx+1, NumPulses, segIdx);
    
    // RISE: Transition from 0V to PulseV over PulseRiseTime
    // Segment goes from v[segIdx] (0V) to v[segIdx+1] (PulseV) over t[segIdx]
    volts[segIdx] = 0.0;  // START voltage (already 0V from previous segment, but explicit)
    times[segIdx] = PulseRiseTime;
    ttime += times[segIdx];
    if(debug) printf("%s: Pulse %d - RISE: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, pulseIdx+1, segIdx, 0.0, segIdx, PulseRiseTime);
    segIdx++;
    volts[segIdx] = PulseV;  // END voltage
    if(debug) printf("%s: Pulse %d - RISE: End v[%d]=%.6fV\n",
      mod, pulseIdx+1, segIdx, PulseV);

    // TOP: Flat segment at PulseV for PulseWidth duration
    // Segment goes from v[segIdx] (PulseV) to v[segIdx+1] (PulseV) over t[segIdx]
    times[segIdx] = PulseWidth;
    ttime += times[segIdx];
    if(debug) printf("%s: Pulse %d - TOP: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, pulseIdx+1, segIdx, PulseV, segIdx, PulseWidth);
    segIdx++;
    volts[segIdx] = PulseV;  // END voltage (same as start = flat top)
    if(debug) printf("%s: Pulse %d - TOP: End v[%d]=%.6fV (flat top)\n",
      mod, pulseIdx+1, segIdx, PulseV);

    // FALL: Transition from PulseV to 0V over PulseFallTime
    // Segment goes from v[segIdx] (PulseV) to v[segIdx+1] (0V) over t[segIdx]
    times[segIdx] = PulseFallTime;
    ttime += times[segIdx];
    if(debug) printf("%s: Pulse %d - FALL: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, pulseIdx+1, segIdx, PulseV, segIdx, PulseFallTime);
    segIdx++;
    volts[segIdx] = 0.0;  // END voltage
    if(debug) printf("%s: Pulse %d - FALL: End v[%d]=%.6fV\n",
      mod, pulseIdx+1, segIdx, 0.0);

    // WAIT: Delay at 0V before next pulse over PulseDelay
    // Segment goes from v[segIdx] (0V) to v[segIdx+1] (0V) over t[segIdx]
    times[segIdx] = PulseDelay;
    ttime += times[segIdx];
    if(debug) printf("%s: Pulse %d - WAIT: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, pulseIdx+1, segIdx, 0.0, segIdx, PulseDelay);
    segIdx++;
    volts[segIdx] = 0.0;  // END voltage (same as start = flat delay)
    if(debug) printf("%s: Pulse %d - WAIT: End v[%d]=%.6fV (delay at 0V)\n",
      mod, pulseIdx+1, segIdx, 0.0);
  }
  
  if(debug) printf("%s: Pulse sequence complete (segIdx=%d)\n", mod, segIdx);

  // ****************
  // Retention measurement pulses
  // ****************
  // Use the original pattern: set times[segIdx] then volts[segIdx], then increment
  // This works because: segment i goes from v[i] to v[i+1] over t[i]
  // So setting times[segIdx] and volts[segIdx] before increment creates:
  //   segment (segIdx): from v[segIdx] to v[segIdx+1] over t[segIdx]
  //   where v[segIdx] was set before, v[segIdx+1] = volts[segIdx] (just set)
  //   and t[segIdx] = times[segIdx] (just set)
  
  int retMeasIdx;
  for (retMeasIdx = 0; retMeasIdx < NumbMeasPulses; retMeasIdx++)
  {
    // Delay before measurement pulse
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    volts[segIdx] = 0.0;
    segIdx++;

    // Rise to measurement voltage
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    volts[segIdx] = measV;
    segIdx++;

    // Measurement pulse width at measV
    times[segIdx] = measWidth;
    if(recordedProbeCount >= probeCapacity)
    {
      if(debug) printf("%s: Probe capacity exceeded while recording retention measurement window %d\n", mod, retMeasIdx);
      stat = -205;
      goto RETS;
    }
    measMinTime[recordedProbeCount] = ttime + ratio * measWidth; 
    measMaxTime[recordedProbeCount] = ttime + measWidth * 0.9;
    if(debug)printf("Retention measMinTime[%d]= %g; measMaxTime[%d]= %g\n", recordedProbeCount, measMinTime[recordedProbeCount], recordedProbeCount, measMaxTime[recordedProbeCount] );
    recordedProbeCount++;
    ttime += times[segIdx];
    volts[segIdx] = measV;
    segIdx++;

    // Fall delay at measV (setFallTime)
    times[segIdx] = setFallTime;
    ttime += times[segIdx];
    volts[segIdx] = measV;
    segIdx++;

    // Fall to 0V (using riseTime for fall time)
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    volts[segIdx] = 0.0;
    segIdx++;

    // Delay at 0V before next measurement
    times[segIdx] = measDelay;
    ttime += times[segIdx];
    volts[segIdx] = 0.0;
    segIdx++;
  }

  // Final voltage point
  volts[segIdx] = 0.0;
  int NewVoltsSize = segIdx + 1;
  int NewTimesSize = segIdx;

  // Validate all segment times before passing to ret_Define_SegmentsILimit
  if(debug)
  {
    printf("%s: Validating waveform before passing to ret_Define_SegmentsILimit:\n", mod);
    printf("%s:   NewTimesSize=%d, NewVoltsSize=%d\n", mod, NewTimesSize, NewVoltsSize);
    printf("%s:   times_count=%d, volts_count=%d\n", mod, times_count, volts_count);
    
    // Check for zero or invalid times
    int invalid_count = 0;
    for(i = 0; i < NewTimesSize; i++)
    {
      if(times[i] <= 0.0 || times[i] != times[i])  // Zero, negative, or NaN
      {
        if(invalid_count < 10)  // Limit output
        {
          printf("%s:   ERROR: times[%d]=%.9e (invalid!)\n", mod, i, times[i]);
        }
        invalid_count++;
      }
    }
    if(invalid_count > 0)
    {
      printf("%s:   Found %d invalid time segments!\n", mod, invalid_count);
    }
    else
    {
      printf("%s:   All time segments are valid\n", mod);
    }
  }

  if(debug) 
  {
    printf("%s: Waveform generation complete - used %d time segments, %d voltage points (allocated: %d times, %d volts)\n", 
      mod, NewTimesSize, NewVoltsSize, times_count, volts_count);
    
    // Print waveform segments for diagnosis (focus on pulse sequence area)
    // Calculate pulse sequence start index (after initial delay + initial measurements)
    int pulseStartIdx = 2 + 4 * NumInitialMeasPulses + 1;  // Start of pulse sequence
    int pulseEndIdx = pulseStartIdx + 4 * NumPulses;  // End of pulse sequence
    
    printf("\n%s: === WAVEFORM SEGMENTS (pulse sequence area) ===\n", mod);
    printf("%s: Segment | Time (s)     | Voltage (V) | StartV -> EndV | Description\n", mod);
    printf("%s: --------+--------------+-------------+----------------+------------\n", mod);
    
    int segPrintIdx;
    for(segPrintIdx = 0; segPrintIdx < NewTimesSize && segPrintIdx < pulseEndIdx + 5; segPrintIdx++)
    {
      const char* desc = "";
      double startV = (segPrintIdx > 0) ? volts[segPrintIdx - 1] : 0.0;
      double endV = volts[segPrintIdx];
      
      if(segPrintIdx < pulseStartIdx)
        desc = "Initial setup";
      else if(segPrintIdx >= pulseStartIdx && segPrintIdx < pulseEndIdx)
      {
        int pulseNum = (segPrintIdx - pulseStartIdx) / 4;
        int segInPulse = (segPrintIdx - pulseStartIdx) % 4;
        if(segInPulse == 0) desc = "PULSE RISE";
        else if(segInPulse == 1) desc = "PULSE TOP";
        else if(segInPulse == 2) desc = "PULSE FALL";
        else desc = "PULSE WAIT";
      }
      else
        desc = "Retention measurements";
        
      printf("%s: %7d | %12.9f | %11.6f | %7.3f -> %7.3f | %s\n", 
        mod, segPrintIdx, times[segPrintIdx], endV, startV, endV, desc);
    }
    printf("\n");
  }

  if(NewVoltsSize > volts_count || NewTimesSize > times_count)
  {
    if(debug) printf("%s: Computed waveform size (times:%d volts:%d) exceeds allocated capacity (times:%d volts:%d)\n", 
      mod, NewTimesSize, NewVoltsSize, times_count, volts_count);
    stat = -211;
    goto RETS;
  }


/* ------end of all pulses----------  */

  used_rate = ret_getRate(ttime, max_points, &used_pts, &npts);
  if(debug) printf("%s: for requested time:%g and max_points:%d number of points to allocate:%d\n",
   mod, ttime, max_points, used_pts);

  AllocateArraysRetention(used_pts);
  if(VFret == NULL || IFret == NULL || VMret == NULL || IMret == NULL || Tret == NULL)
  {
    if(debug) printf("%s: Unable to allocate measurement buffers of size %d\n", mod, used_pts);
    stat = -207;
    goto RETS;
  }

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
// this calls retention_pulse_ilimit_dual_channel in "retention_pulse_ilimit_dual_channel.c", it sets Force Channel to 1 and Measurement Channel 2 (2nd and 7th parameter)
// and collects forced voltage and current values from both the ForceCh and MeasureCh channels.
// The segments are created based on the settings provided by the operator within the 'Volts' and 'Times' input arrays, and measurements 
// are returned via of the voltage(VF and VM) and current (IF and IM) output arrays for both channels.

      stat = retention_pulse_ilimit_dual_channel
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
      // Get probe measurements (initial reads + retention reads)
      // *******************
      int ProbeResNumb=0;
      for (ProbeResNumb=0; ProbeResNumb<recordedProbeCount;ProbeResNumb++)  
      {
        // Get current at measurement probe
        double probeCurrent = 0.0;
        stat = ret_find_value(IMret, Tret, numpts, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &probeCurrent);
        if(debug) printf("\nProbe Number: %d \n %s: Average Current=%g in time interval (seconds): %g and %g\n", 
          ProbeResNumb, mod, probeCurrent, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb]);
        if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe current\n", mod);
          stat = -92;
          goto RETS;
        }

        // Calculate resistance: R = V / I
        if (fabs(probeCurrent) > 1e-12)  // Avoid division by zero
        {
          double resistance = fabs(measV / probeCurrent);
          if(resistance > 1e4/IRange) 
            resistance = 1e4/IRange;
          resetR[ProbeResNumb] = resistance;  // Store resistance (reusing resetR array)
          if(debug)printf("%s: Probe %d resistance = %g Ohms\n", mod, ProbeResNumb, resistance);
        }
        else
        {
          resetR[ProbeResNumb] = 1e4/IRange;  // Very high resistance
          if(debug)printf("%s: Probe %d current too small, setting resistance to max\n", mod, ProbeResNumb);
        }

        // Get voltage at measurement probe
        double probeVoltage = 0.0;
        stat = ret_find_value(VMret, Tret, numpts, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &probeVoltage);
        if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe voltage value\n", mod);
          stat = -93;
          goto RETS;
        }
        setV[ProbeResNumb] = probeVoltage;  // Store voltage
        if(debug)printf("%s: setV[%d] = %g V\n", mod, ProbeResNumb, probeVoltage);

        // Store current
        setI[ProbeResNumb] = probeCurrent;  // Store current
        if(debug)printf("%s: setI[%d] = %g A\n", mod, ProbeResNumb, probeCurrent);

        // Return pulse times as an array
        PulseTimes[ProbeResNumb]=(measMaxTime[ProbeResNumb]+measMinTime[ProbeResNumb])/2;
      }

int looper;
 if(debug)
  { 
  //was loop<11
  for (looper=0; looper<recordedProbeCount;looper++) {
    printf("PulseTimes %d: %g\n",looper, PulseTimes[looper]);    }
  }
} 

  stat = 1;

  RETS:
  if(times != NULL) free(times);
  if(volts != NULL) free(volts);
  if(measMinTime != NULL) free(measMinTime);
  if(measMaxTime != NULL) free(measMaxTime);
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

   if(VFret == NULL || IFret == NULL || VMret == NULL || IMret == NULL || Tret == NULL)
   {
      FreeArraysRetention();
   }
}


/* ----------------  */

// renamed function below so it doesn't clash with the same function in endurance and to be stand-alone
void FreeArraysRetention()
{
   if(NULL != VFret) { free(VFret); VFret = NULL; }
   if(NULL != IFret) { free(IFret); IFret = NULL; }
   if(NULL != VMret) { free(VMret); VMret = NULL; }
   if(NULL != IMret) { free(IMret); IMret = NULL; }
   if(NULL != Tret) { free(Tret); Tret = NULL; }
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
} 		/* End pmu_retention_dual_channel.c */

