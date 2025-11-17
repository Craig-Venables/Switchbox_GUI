/* USRLIB MODULE INFORMATION

	MODULE NAME: pmu_potentiation_depression
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
		NumbMeasPulses,	int,	Input,	8,	1,	1000
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

double *VFret = NULL;
double *IFret = NULL;
double *VMret = NULL;
double *IMret = NULL;
double *Tret = NULL;

void AllocateArraysPotDep(int pts);
void FreeArraysPotDep();

int ACraig1_retention_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);
__declspec( dllexport ) int ret_getRateWithMinSeg(double ttime, int maxpts, double min_seg_time, int *apts, int *npts);

extern int debug;
extern int details;

extern int retention_pulse_ilimit_dual_channel(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: pmu_potentiation_depression
==================

Description
-----------
This module implements a ((read,(pulse)xn,(read)xn), -((read,(pulse)xn,(read)xn)))xn pattern for
potentiation and depression cycling. The waveform consists of alternating potentiation and depression cycles.

This pattern is used for testing device response to alternating positive and negative programming pulses,
useful for studying potentiation (conductance increase) and depression (conductance decrease) behavior.

Waveform Structure:
------------------
For each cycle pair (NumCycles pairs):
  1. Potentiation Cycle:
     - Read measurement
     - NumPulsesPerGroup pulses in sequence (positive PulseV): RISE → TOP (PulseWidth) → FALL → DELAY
     - NumReads reads in sequence: RISE → TOP (measWidth) → FALL → DELAY
  2. Depression Cycle:
     - Read measurement
     - NumPulsesPerGroup pulses in sequence (negative -PulseV): RISE → TOP (PulseWidth) → FALL → DELAY
     - NumReads reads in sequence: RISE → TOP (measWidth) → FALL → DELAY

Total measurements = 2*NumCycles + 2*NumCycles*NumReads (one read per potentiation + one read per depression + reads after pulses)

Input and output parameters
---------------------------

See pmu_retention_dual_channel for parameter descriptions. Key differences:
- NumInitialMeasPulses: Number of cycle pairs (M) - renamed to NumCycles (1-100)
- NumPulses: Number of reads per cycle (N) - renamed to NumReads (1-100)
- NumbMeasPulses: Number of pulses per cycle (N) - renamed to NumPulsesPerGroup (1-100)

Output arrays must be sized to accommodate: 2*NumCycles*(1 + NumReads) measurements

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

double *VFret = NULL;
double *IFret = NULL;
double *VMret = NULL;
double *IMret = NULL;
double *Tret = NULL;

void AllocateArraysPotDep(int pts);
void FreeArraysPotDep();

int ACraig1_retention_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);
__declspec( dllexport ) int ret_getRateWithMinSeg(double ttime, int maxpts, double min_seg_time, int *apts, int *npts);

extern int debug;
extern int details;

extern int retention_pulse_ilimit_dual_channel(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);

/* USRLIB MODULE MAIN FUNCTION */
int pmu_potentiation_depression( double riseTime, double resetV, double resetWidth, double resetDelay, double measV, double measWidth, double measDelay, double setWidth, double setFallTime, double setDelay, double setStartV, double setStopV, int steps, double IRange, int max_points, double *setR, int setR_size, double *resetR, int resetR_size, double *setV, int setV_size, double *setI, int setI_size, int iteration, double *out1, int out1_size, char *out1_name, double *out2, int out2_size, char *out2_name, double *PulseTimes, int PulseTimesSize, int NumbMeasPulses, int NumInitialMeasPulses, int NumPulses, double PulseWidth, double PulseV, double PulseRiseTime, double PulseFallTime, double PulseDelay, int ClariusDebug )
{
/* USRLIB MODULE CODE */
  char mod[] = "pmu_potentiation_depression";
  char inst[] = "PMU1";
  int i, stat;
  double *times = NULL;
  double *volts = NULL;
  int times_count = 0;
  int volts_count = 0;

  double *measMinTime = NULL;
  double *measMaxTime = NULL;
  double *measOffMinTime = NULL;
  double *measOffMaxTime = NULL;
  int recordedProbeCount = 0;
  int probeCapacity = 0;

  int numpts;
  int npts;
  double vbias, resss;
  double ttime;
  int used_pts;
  int used_rate;
   
  double ratio = 0.4; // defines window where to do measurements

  double forceVRange;
  double measVRange;

  // Use maximum of resetV and PulseV for voltage range (need to account for both +PulseV and -PulseV)
  forceVRange = fabs(PulseV);  // Use absolute value since we'll use both +PulseV and -PulseV
  if (forceVRange < 1.0) forceVRange = 1.0;
  measVRange = 1.0;

  // Repurpose parameters for new pattern:
  // NumInitialMeasPulses → NumCycles (M cycles)
  // NumPulses → NumReads (N reads per cycle)
  // NumbMeasPulses → NumPulsesPerGroup (N pulses per cycle)
  int NumCycles = NumInitialMeasPulses;
  int NumReads = NumPulses;
  int NumPulsesPerGroup = NumbMeasPulses;

  // Validate NumCycles (number of cycles)
  if (NumCycles < 1)
  {
    if(debug) printf("%s: NumCycles (NumInitialMeasPulses) must be at least 1 (got %d)\n", mod, NumCycles);
    stat = -213;
    goto RETS;
  }

  // Validate NumReads (number of reads per cycle)
  if (NumReads < 1)
  {
    if(debug) printf("%s: NumReads (NumPulses) must be at least 1 (got %d)\n", mod, NumReads);
    stat = -213;
    goto RETS;
  }

  // Validate NumPulsesPerGroup (number of pulses per cycle)
  if (NumPulsesPerGroup < 1)
  {
    if(debug) printf("%s: NumPulsesPerGroup (NumbMeasPulses) must be at least 1 (got %d)\n", mod, NumPulsesPerGroup);
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
  // Pattern: ((Read, (Pulse)xn, (Read)xn), -(Read, (Pulse)xn, (Read)xn)) × NumCycles
  // Each cycle pair (potentiation + depression):
  //   Potentiation: 1 read (5 segments) + NumPulsesPerGroup pulses (4 segments each) + NumReads reads (5 segments each)
  //   Depression: 1 read (5 segments) + NumPulsesPerGroup pulses (4 segments each) + NumReads reads (5 segments each)
  int calc_times_count = 2;  // initial delay + rise
  
  // Each cycle pair: 2 reads + (NumPulsesPerGroup * 4) * 2 + (NumReads * 5) * 2
  // = 2*5 + 2*(NumPulsesPerGroup * 4) + 2*(NumReads * 5)
  calc_times_count += NumCycles * (2 * 5 + 2 * (NumPulsesPerGroup * 4) + 2 * (NumReads * 5));
  
  // Add safety margin (10% or minimum 10 segments)
  int safety_margin = calc_times_count / 10;
  if (safety_margin < 10) safety_margin = 10;
  
  times_count = calc_times_count + safety_margin;
  volts_count = times_count + 1;

  if(debug) printf("%s: Allocating waveform buffers - calculated:%d + margin:%d = times_count:%d volts_count:%d (NumCycles:%d, NumReads:%d, NumPulsesPerGroup:%d)\n", 
    mod, calc_times_count, safety_margin, times_count, volts_count, NumCycles, NumReads, NumPulsesPerGroup);

  times = (double *)calloc(times_count, sizeof(double));
  volts = (double *)calloc(volts_count, sizeof(double));
  if(times == NULL || volts == NULL)
  {
    if(debug) printf("%s: Unable to allocate segment buffers (times:%d volts:%d)\n", mod, times_count, volts_count);
    stat = -210;
    goto RETS;
  }

  // Probe capacity: 2*NumCycles (one read per potentiation + one per depression) + 2*NumCycles*NumReads (reads after pulses)
  // = 2*NumCycles*(1 + NumReads)
  probeCapacity = 2 * NumCycles * (1 + NumReads);
  if (PulseTimes == NULL || setV == NULL || setI == NULL)
  {
    if(debug) printf("%s: Output buffers must not be NULL\n", mod);
    stat = -202;
    goto RETS;
  }

  measMinTime = (double *)calloc(probeCapacity, sizeof(double));
  measMaxTime = (double *)calloc(probeCapacity, sizeof(double));
  measOffMinTime = (double *)calloc(probeCapacity, sizeof(double));
  measOffMaxTime = (double *)calloc(probeCapacity, sizeof(double));
  if(measMinTime == NULL || measMaxTime == NULL || measOffMinTime == NULL || measOffMaxTime == NULL)
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

  // Initialize starting voltage (volts[0] must be set before first segment)
  volts[0] = 0.0;

  // Initial delay and rise time
  times[segIdx] = resetDelay;
  ttime += times[segIdx];
  volts[segIdx] = 0.0;  // Start voltage of first delay segment
  segIdx++;

  times[segIdx] = riseTime;
  ttime += times[segIdx];
  volts[segIdx] = 0.0;
  segIdx++;

  // ****************
  // Cycle Pairs: ((Read, (Pulse)xn, (Read)xn), -(Read, (Pulse)xn, (Read)xn)) × NumCycles
  // ****************
  int cyclePairIdx;
  for (cyclePairIdx = 0; cyclePairIdx < NumCycles; cyclePairIdx++)
  {
    if(debug) printf("\n%s: ===== CYCLE PAIR %d/%d ===== (segIdx=%d)\n", 
      mod, cyclePairIdx+1, NumCycles, segIdx);
    
    // ****************
    // POTENTIATION CYCLE: Read → (Pulse)xn → (Read)xn
    // ****************
    if(debug) printf("\n%s: ===== POTENTIATION CYCLE %d =====\n", mod, cyclePairIdx+1);
    
    // Potentiation: Initial read
    if(recordedProbeCount >= probeCapacity)
    {
      if(debug) printf("%s: Probe capacity exceeded while recording potentiation read in cycle pair %d\n", mod, cyclePairIdx+1);
      stat = -205;
      goto RETS;
    }
    if(debug) printf("\n%s: Potentiation %d - INITIAL READ\n", mod, cyclePairIdx+1);
    
    // RISE: Transition from 0V to measV over riseTime
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    if(debug) printf("%s: Pot %d Read RISE: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cyclePairIdx+1, segIdx, 0.0, segIdx, riseTime);
    segIdx++;
    volts[segIdx] = measV;  // END voltage of RISE
    if(debug) printf("%s: Pot %d Read RISE: End v[%d]=%.6fV\n",
      mod, cyclePairIdx+1, segIdx, measV);

    // TOP: Measurement pulse width at measV
    int potInitialProbeIdx = recordedProbeCount;
    measMinTime[potInitialProbeIdx] = ttime + ratio * measWidth; 
    measMaxTime[potInitialProbeIdx] = ttime + measWidth * 0.9;
    if(debug)printf("Pot %d initial read measMinTime[%d]= %g; measMaxTime[%d]= %g\n", 
      cyclePairIdx+1, potInitialProbeIdx, measMinTime[potInitialProbeIdx], potInitialProbeIdx, measMaxTime[potInitialProbeIdx] );
    recordedProbeCount++;
    
    times[segIdx] = measWidth;
    ttime += times[segIdx];
    volts[segIdx] = measV;  // Stay at measV during measurement window
    segIdx++;
    volts[segIdx] = measV;  // END voltage (same as start = flat top)

    // FALL delay at measV (setFallTime) - optional settling time
    times[segIdx] = setFallTime;
    ttime += times[segIdx];
    volts[segIdx] = measV;
    segIdx++;

    // FALL: Transition from measV to 0V over riseTime
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    segIdx++;
    volts[segIdx] = 0.0;  // END voltage of FALL (now at 0V)

    // DELAY: Delay at 0V after read, before pulses
    double potDelayStart = ttime;
    times[segIdx] = measDelay;
    ttime += times[segIdx];
    if(debug) printf("%s: Pot %d Read DELAY AT 0V: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cyclePairIdx+1, segIdx, 0.0, segIdx, measDelay);
    segIdx++;
    volts[segIdx] = 0.0;  // END voltage of delay segment (flat at 0V) - CRITICAL: must be set AFTER increment
    if(debug) printf("%s: Pot %d Read DELAY AT 0V: End v[%d]=%.6fV\n",
      mod, cyclePairIdx+1, segIdx, 0.0);
    measOffMinTime[potInitialProbeIdx] = potDelayStart + ratio * measDelay;
    measOffMaxTime[potInitialProbeIdx] = potDelayStart + measDelay * 0.9;
    if(debug) printf("%s: Pot %d initial read offset window[%d] = (%g, %g)\n",
      mod, cyclePairIdx+1, potInitialProbeIdx, measOffMinTime[potInitialProbeIdx], measOffMaxTime[potInitialProbeIdx]);

    // Potentiation: NumPulsesPerGroup pulses in sequence (positive PulseV)
    int pulseIdx;
    for (pulseIdx = 0; pulseIdx < NumPulsesPerGroup; pulseIdx++)
    {
      if(debug) printf("\n%s: Pot %d - PULSE %d/%d (positive)\n", mod, cyclePairIdx+1, pulseIdx+1, NumPulsesPerGroup);
      
      // RISE: Transition from 0V to PulseV over PulseRiseTime
      volts[segIdx] = 0.0;  // START voltage
      times[segIdx] = PulseRiseTime;
      ttime += times[segIdx];
      if(debug) printf("%s: Pot %d Pulse %d - RISE: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, 0.0, segIdx, PulseRiseTime);
      segIdx++;
      volts[segIdx] = PulseV;  // END voltage (positive)
      if(debug) printf("%s: Pot %d Pulse %d - RISE: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, PulseV);

      // TOP: Flat segment at PulseV for PulseWidth duration
      times[segIdx] = PulseWidth;
      ttime += times[segIdx];
      if(debug) printf("%s: Pot %d Pulse %d - TOP: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, PulseV, segIdx, PulseWidth);
      segIdx++;
      volts[segIdx] = PulseV;  // END voltage (same as start = flat top)
      if(debug) printf("%s: Pot %d Pulse %d - TOP: End v[%d]=%.6fV (flat top)\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, PulseV);

      // FALL: Transition from PulseV to 0V over PulseFallTime
      times[segIdx] = PulseFallTime;
      ttime += times[segIdx];
      if(debug) printf("%s: Pot %d Pulse %d - FALL: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, PulseV, segIdx, PulseFallTime);
      segIdx++;
      volts[segIdx] = 0.0;  // END voltage of FALL (now at 0V)
      if(debug) printf("%s: Pot %d Pulse %d - FALL: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, 0.0);

      // DELAY: Delay at 0V after pulse (before next pulse or reads)
      times[segIdx] = PulseDelay;
      ttime += times[segIdx];
      if(debug) printf("%s: Pot %d Pulse %d - DELAY AT 0V: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, 0.0, segIdx, PulseDelay);
      segIdx++;
      volts[segIdx] = 0.0;  // END voltage of delay segment (flat at 0V) - CRITICAL: must be set AFTER increment
      if(debug) printf("%s: Pot %d Pulse %d - DELAY AT 0V: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, 0.0);
    }

    // Potentiation: NumReads reads in sequence
    int readIdx;
    for (readIdx = 0; readIdx < NumReads; readIdx++)
    {
      if(debug) printf("\n%s: Pot %d - READ %d/%d\n", mod, cyclePairIdx+1, readIdx+1, NumReads);
      
      // RISE: Transition from 0V to measV over riseTime
      times[segIdx] = riseTime;
      ttime += times[segIdx];
      if(debug) printf("%s: Pot %d Read %d - RISE: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, 0.0, segIdx, riseTime);
      segIdx++;
      volts[segIdx] = measV;  // END voltage of RISE
      if(debug) printf("%s: Pot %d Read %d - RISE: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, measV);

      // TOP: Measurement pulse width at measV
      if(recordedProbeCount >= probeCapacity)
      {
        if(debug) printf("%s: Probe capacity exceeded while recording read %d in potentiation %d\n", mod, readIdx+1, cyclePairIdx+1);
        stat = -205;
        goto RETS;
      }
      int potReadProbeIdx = recordedProbeCount;
      measMinTime[potReadProbeIdx] = ttime + ratio * measWidth; 
      measMaxTime[potReadProbeIdx] = ttime + measWidth * 0.9;
      if(debug)printf("Pot %d Read %d measMinTime[%d]= %g; measMaxTime[%d]= %g\n", 
        cyclePairIdx+1, readIdx+1, potReadProbeIdx, measMinTime[potReadProbeIdx], potReadProbeIdx, measMaxTime[potReadProbeIdx] );
      recordedProbeCount++;
      
      times[segIdx] = measWidth;
      ttime += times[segIdx];
      volts[segIdx] = measV;  // Stay at measV during measurement window
      segIdx++;

      // FALL delay at measV (setFallTime) - optional settling time
      times[segIdx] = setFallTime;
      ttime += times[segIdx];
      volts[segIdx] = measV;
      segIdx++;

      // FALL: Transition from measV to 0V over riseTime
      times[segIdx] = riseTime;
      ttime += times[segIdx];
      if(debug) printf("%s: Pot %d Read %d - FALL: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, measV, segIdx, riseTime);
      segIdx++;
      volts[segIdx] = 0.0;  // END voltage of FALL (now at 0V)
      if(debug) printf("%s: Pot %d Read %d - FALL: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, 0.0);

      // DELAY: Delay at 0V after read (before next read or depression cycle)
      double potReadDelayStart = ttime;
      times[segIdx] = measDelay;
      ttime += times[segIdx];
      if(debug) printf("%s: Pot %d Read %d - DELAY AT 0V: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, 0.0, segIdx, measDelay);
      segIdx++;
      volts[segIdx] = 0.0;  // END voltage of delay segment (flat at 0V) - CRITICAL: must be set AFTER increment
      if(debug) printf("%s: Pot %d Read %d - DELAY AT 0V: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, 0.0);
      measOffMinTime[potReadProbeIdx] = potReadDelayStart + ratio * measDelay;
      measOffMaxTime[potReadProbeIdx] = potReadDelayStart + measDelay * 0.9;
      if(debug) printf("%s: Pot %d Read %d offset window[%d] = (%g, %g)\n",
        mod, cyclePairIdx+1, readIdx+1, potReadProbeIdx, measOffMinTime[potReadProbeIdx], measOffMaxTime[potReadProbeIdx]);
    }

    // ****************
    // DEPRESSION CYCLE: Read → (Pulse)xn → (Read)xn (with negative pulses)
    // ****************
    if(debug) printf("\n%s: ===== DEPRESSION CYCLE %d =====\n", mod, cyclePairIdx+1);
    
    // Depression: Initial read
    if(recordedProbeCount >= probeCapacity)
    {
      if(debug) printf("%s: Probe capacity exceeded while recording depression read in cycle pair %d\n", mod, cyclePairIdx+1);
      stat = -205;
      goto RETS;
    }
    if(debug) printf("\n%s: Depression %d - INITIAL READ\n", mod, cyclePairIdx+1);
    
    // RISE: Transition from 0V to measV over riseTime
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    if(debug) printf("%s: Dep %d Read RISE: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cyclePairIdx+1, segIdx, 0.0, segIdx, riseTime);
    segIdx++;
    volts[segIdx] = measV;  // END voltage of RISE
    if(debug) printf("%s: Dep %d Read RISE: End v[%d]=%.6fV\n",
      mod, cyclePairIdx+1, segIdx, measV);

    // TOP: Measurement pulse width at measV
    int depInitialProbeIdx = recordedProbeCount;
    measMinTime[depInitialProbeIdx] = ttime + ratio * measWidth; 
    measMaxTime[depInitialProbeIdx] = ttime + measWidth * 0.9;
    if(debug)printf("Dep %d initial read measMinTime[%d]= %g; measMaxTime[%d]= %g\n", 
      cyclePairIdx+1, depInitialProbeIdx, measMinTime[depInitialProbeIdx], depInitialProbeIdx, measMaxTime[depInitialProbeIdx] );
    recordedProbeCount++;
    
    times[segIdx] = measWidth;
    ttime += times[segIdx];
    volts[segIdx] = measV;  // Stay at measV during measurement window
    segIdx++;
    volts[segIdx] = measV;  // END voltage (same as start = flat top)

    // FALL delay at measV (setFallTime) - optional settling time
    times[segIdx] = setFallTime;
    ttime += times[segIdx];
    volts[segIdx] = measV;
    segIdx++;

    // FALL: Transition from measV to 0V over riseTime
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    segIdx++;
    volts[segIdx] = 0.0;  // END voltage of FALL (now at 0V)

    // DELAY: Delay at 0V after read, before pulses
    double depDelayStart = ttime;
    times[segIdx] = measDelay;
    ttime += times[segIdx];
    if(debug) printf("%s: Dep %d Read DELAY AT 0V: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cyclePairIdx+1, segIdx, 0.0, segIdx, measDelay);
    segIdx++;
    volts[segIdx] = 0.0;  // END voltage of delay segment (flat at 0V) - CRITICAL: must be set AFTER increment
    if(debug) printf("%s: Dep %d Read DELAY AT 0V: End v[%d]=%.6fV\n",
      mod, cyclePairIdx+1, segIdx, 0.0);
    measOffMinTime[depInitialProbeIdx] = depDelayStart + ratio * measDelay;
    measOffMaxTime[depInitialProbeIdx] = depDelayStart + measDelay * 0.9;
    if(debug) printf("%s: Dep %d initial read offset window[%d] = (%g, %g)\n",
      mod, cyclePairIdx+1, depInitialProbeIdx, measOffMinTime[depInitialProbeIdx], measOffMaxTime[depInitialProbeIdx]);

    // Depression: NumPulsesPerGroup pulses in sequence (negative -PulseV)
    for (pulseIdx = 0; pulseIdx < NumPulsesPerGroup; pulseIdx++)
    {
      if(debug) printf("\n%s: Dep %d - PULSE %d/%d (negative)\n", mod, cyclePairIdx+1, pulseIdx+1, NumPulsesPerGroup);
      
      // RISE: Transition from 0V to -PulseV over PulseRiseTime
      volts[segIdx] = 0.0;  // START voltage
      times[segIdx] = PulseRiseTime;
      ttime += times[segIdx];
      if(debug) printf("%s: Dep %d Pulse %d - RISE: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, 0.0, segIdx, PulseRiseTime);
      segIdx++;
      volts[segIdx] = -PulseV;  // END voltage (negative)
      if(debug) printf("%s: Dep %d Pulse %d - RISE: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, -PulseV);

      // TOP: Flat segment at -PulseV for PulseWidth duration
      times[segIdx] = PulseWidth;
      ttime += times[segIdx];
      if(debug) printf("%s: Dep %d Pulse %d - TOP: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, -PulseV, segIdx, PulseWidth);
      segIdx++;
      volts[segIdx] = -PulseV;  // END voltage (same as start = flat top)
      if(debug) printf("%s: Dep %d Pulse %d - TOP: End v[%d]=%.6fV (flat top)\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, -PulseV);

      // FALL: Transition from -PulseV to 0V over PulseFallTime
      times[segIdx] = PulseFallTime;
      ttime += times[segIdx];
      if(debug) printf("%s: Dep %d Pulse %d - FALL: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, -PulseV, segIdx, PulseFallTime);
      segIdx++;
      volts[segIdx] = 0.0;  // END voltage of FALL (now at 0V)
      if(debug) printf("%s: Dep %d Pulse %d - FALL: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, 0.0);

      // DELAY: Delay at 0V after pulse (before next pulse or reads)
      times[segIdx] = PulseDelay;
      ttime += times[segIdx];
      if(debug) printf("%s: Dep %d Pulse %d - DELAY AT 0V: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, 0.0, segIdx, PulseDelay);
      segIdx++;
      volts[segIdx] = 0.0;  // END voltage of delay segment (flat at 0V) - CRITICAL: must be set AFTER increment
      if(debug) printf("%s: Dep %d Pulse %d - DELAY AT 0V: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, pulseIdx+1, segIdx, 0.0);
    }

    // Depression: NumReads reads in sequence
    for (readIdx = 0; readIdx < NumReads; readIdx++)
    {
      if(debug) printf("\n%s: Dep %d - READ %d/%d\n", mod, cyclePairIdx+1, readIdx+1, NumReads);
      
      // RISE: Transition from 0V to measV over riseTime
      times[segIdx] = riseTime;
      ttime += times[segIdx];
      if(debug) printf("%s: Dep %d Read %d - RISE: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, 0.0, segIdx, riseTime);
      segIdx++;
      volts[segIdx] = measV;  // END voltage of RISE
      if(debug) printf("%s: Dep %d Read %d - RISE: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, measV);

      // TOP: Measurement pulse width at measV
      if(recordedProbeCount >= probeCapacity)
      {
        if(debug) printf("%s: Probe capacity exceeded while recording read %d in depression %d\n", mod, readIdx+1, cyclePairIdx+1);
        stat = -205;
        goto RETS;
      }
      int depReadProbeIdx = recordedProbeCount;
      measMinTime[depReadProbeIdx] = ttime + ratio * measWidth; 
      measMaxTime[depReadProbeIdx] = ttime + measWidth * 0.9;
      if(debug)printf("Dep %d Read %d measMinTime[%d]= %g; measMaxTime[%d]= %g\n", 
        cyclePairIdx+1, readIdx+1, depReadProbeIdx, measMinTime[depReadProbeIdx], depReadProbeIdx, measMaxTime[depReadProbeIdx] );
      recordedProbeCount++;
      
      times[segIdx] = measWidth;
      ttime += times[segIdx];
      volts[segIdx] = measV;  // Stay at measV during measurement window
      segIdx++;

      // FALL delay at measV (setFallTime) - optional settling time
      times[segIdx] = setFallTime;
      ttime += times[segIdx];
      volts[segIdx] = measV;
      segIdx++;

      // FALL: Transition from measV to 0V over riseTime
      times[segIdx] = riseTime;
      ttime += times[segIdx];
      if(debug) printf("%s: Dep %d Read %d - FALL: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, measV, segIdx, riseTime);
      segIdx++;
      volts[segIdx] = 0.0;  // END voltage of FALL (now at 0V)
      if(debug) printf("%s: Dep %d Read %d - FALL: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, 0.0);

      // DELAY: Delay at 0V after read (before next read or next cycle pair)
      double depReadDelayStart = ttime;
      times[segIdx] = measDelay;
      ttime += times[segIdx];
      if(debug) printf("%s: Dep %d Read %d - DELAY AT 0V: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, 0.0, segIdx, measDelay);
      segIdx++;
      volts[segIdx] = 0.0;  // END voltage of delay segment (flat at 0V) - CRITICAL: must be set AFTER increment
      if(debug) printf("%s: Dep %d Read %d - DELAY AT 0V: End v[%d]=%.6fV\n",
        mod, cyclePairIdx+1, readIdx+1, segIdx, 0.0);
      measOffMinTime[depReadProbeIdx] = depReadDelayStart + ratio * measDelay;
      measOffMaxTime[depReadProbeIdx] = depReadDelayStart + measDelay * 0.9;
      if(debug) printf("%s: Dep %d Read %d offset window[%d] = (%g, %g)\n",
        mod, cyclePairIdx+1, readIdx+1, depReadProbeIdx, measOffMinTime[depReadProbeIdx], measOffMaxTime[depReadProbeIdx]);
    }
  }
  
  if(debug) printf("%s: All cycles complete (segIdx=%d, recordedProbeCount=%d)\n", mod, segIdx, recordedProbeCount);

  // Final voltage point
  volts[segIdx] = 0.0;
  int NewVoltsSize = segIdx + 1;
  int NewTimesSize = segIdx;

  // Find minimum segment time for optimal rate selection
  double min_seg_time_found = 1.0;  // Start with a large value
  for(i = 0; i < NewTimesSize; i++)
  {
    if(times[i] > 0.0 && times[i] < min_seg_time_found)
    {
      min_seg_time_found = times[i];
    }
  }
  if(debug) printf("%s: Minimum segment time in waveform: %.2e s\n", mod, min_seg_time_found);

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

  if(NewVoltsSize > volts_count || NewTimesSize > times_count)
  {
    if(debug) printf("%s: Computed waveform size (times:%d volts:%d) exceeds allocated capacity (times:%d volts:%d)\n", 
      mod, NewTimesSize, NewVoltsSize, times_count, volts_count);
    stat = -211;
    goto RETS;
  }

/* ------end of all pulses----------  */

  // Use enhanced rate selection that considers minimum segment time
  used_rate = ret_getRateWithMinSeg(ttime, max_points, min_seg_time_found, &used_pts, &npts);
  if(debug) printf("%s: for requested time:%g and max_points:%d number of points to allocate:%d\n",
   mod, ttime, max_points, used_pts);

  AllocateArraysPotDep(used_pts);
  if(VFret == NULL || IFret == NULL || VMret == NULL || IMret == NULL || Tret == NULL)
  {
    if(debug) printf("%s: Unable to allocate measurement buffers of size %d\n", mod, used_pts);
    stat = -207;
    goto RETS;
  }

// we aren't sweeping the set Voltage for this pattern so the following code should not do anything
// note steps here is the sweep on the set Voltage, it is 1 
  //do a sweep
  for(i = 0; i < steps; i++)
    {
      // correct voltage array:
      if(steps > 1)
    vbias = setStartV + i * (setStopV - setStartV)/(steps - 1);
      else
    vbias = setStartV;

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
      // Get probe measurements (initial read + reads after each pulse)
      // *******************
      // Get the actual data time range to validate measurement windows
      double data_start_time = (numpts > 0) ? Tret[0] : 0.0;
      double data_end_time = (numpts > 0) ? Tret[numpts - 1] : 0.0;
      if(debug) printf("%s: Data time range: %.6e to %.6e seconds (numpts=%d)\n", 
        mod, data_start_time, data_end_time, numpts);
      
      int ProbeResNumb=0;
      for (ProbeResNumb=0; ProbeResNumb<recordedProbeCount;ProbeResNumb++)  
      {
        // Validate measurement window exists and is within data range
        // Check if window times are valid (non-zero and in correct order)
        if(measMinTime[ProbeResNumb] <= 0.0 || measMaxTime[ProbeResNumb] <= 0.0 || 
           measMinTime[ProbeResNumb] >= measMaxTime[ProbeResNumb])
        {
          if(debug) printf("%s: WARNING: Probe %d has invalid measurement window [%.6e, %.6e] - skipping\n",
            mod, ProbeResNumb, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb]);
          // Set default values for invalid probes
          setV[ProbeResNumb] = 0.0;
          setI[ProbeResNumb] = 0.0;
          resetR[ProbeResNumb] = 1e4/IRange;  // Very high resistance
          PulseTimes[ProbeResNumb] = 0.0;
          continue;  // Skip this probe
        }
        
        // Check if window is within data range
        if(measMinTime[ProbeResNumb] < data_start_time || measMaxTime[ProbeResNumb] > data_end_time)
        {
          if(debug) printf("%s: WARNING: Probe %d measurement window [%.6e, %.6e] is outside data range [%.6e, %.6e] - skipping\n",
            mod, ProbeResNumb, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], data_start_time, data_end_time);
          // Set default values for invalid probes
          setV[ProbeResNumb] = 0.0;
          setI[ProbeResNumb] = 0.0;
          resetR[ProbeResNumb] = 1e4/IRange;  // Very high resistance
          PulseTimes[ProbeResNumb] = 0.0;
          continue;  // Skip this probe
        }
        
        // Get current from MEASURE channel (channel 2) during the measurement window
        double probeMeasCurrent = 0.0;
        stat = ret_find_value(IMret, Tret, numpts, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &probeMeasCurrent);
        if(debug) printf("\nProbe Number: %d \n %s: Measurement channel current=%g in time interval (seconds): %g and %g\n", 
          ProbeResNumb, mod, probeMeasCurrent, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb]);
        if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe current (returned %d, current=%g) - measurement window may be outside data range\n", 
            mod, stat, probeMeasCurrent);
          // Set default values instead of failing
          setV[ProbeResNumb] = 0.0;
          setI[ProbeResNumb] = 0.0;
          resetR[ProbeResNumb] = 1e4/IRange;
          PulseTimes[ProbeResNumb] = 0.0;
          continue;  // Skip this probe and continue
        }

        // Get offset current from MEASURE channel during the zero-volt delay window
        double probeMeasOffsetCurrent = 0.0;
        // Validate offset window is within data range
        if(measOffMinTime[ProbeResNumb] >= data_start_time && measOffMaxTime[ProbeResNumb] <= data_end_time)
        {
          stat = ret_find_value(IMret, Tret, numpts, measOffMinTime[ProbeResNumb], measOffMaxTime[ProbeResNumb], &probeMeasOffsetCurrent);
          if(stat < 0)
          {
            if(debug)printf("%s: Error in finding probe offset current (returned %d) - using 0.0 as offset\n", mod, stat);
            probeMeasOffsetCurrent = 0.0;  // Use zero offset if window is invalid
          }
        }
        else
        {
          if(debug) printf("%s: WARNING: Probe %d offset window [%.6e, %.6e] is outside data range - using 0.0 as offset\n",
            mod, ProbeResNumb, measOffMinTime[ProbeResNumb], measOffMaxTime[ProbeResNumb]);
          probeMeasOffsetCurrent = 0.0;  // Use zero offset if window is invalid
        }
        if(debug) printf("%s: Probe %d offset current=%g in time interval (seconds): %g and %g\n",
          mod, ProbeResNumb, probeMeasOffsetCurrent, measOffMinTime[ProbeResNumb], measOffMaxTime[ProbeResNumb]);

        double netProbeCurrent = probeMeasCurrent - probeMeasOffsetCurrent;

        // Get voltage from FORCE channel (channel 1) for the same window
        double probeVoltage = 0.0;
        stat = ret_find_value(VFret, Tret, numpts, measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &probeVoltage);
        if(stat < 0)
        {
          if(debug)printf("%s: Error in finding probe voltage value (returned %d, voltage=%g) - measurement window may be outside data range\n", 
            mod, stat, probeVoltage);
          // Set default values instead of failing
          setV[ProbeResNumb] = 0.0;
          setI[ProbeResNumb] = 0.0;
          resetR[ProbeResNumb] = 1e4/IRange;
          PulseTimes[ProbeResNumb] = 0.0;
          continue;  // Skip this probe and continue
        }
        setV[ProbeResNumb] = probeVoltage;  // Store voltage
        if(debug)printf("%s: setV[%d] = %g V\n", mod, ProbeResNumb, probeVoltage);

        // Calculate resistance: R = V / (I - Ioffset)
        if (fabs(netProbeCurrent) > 1e-12)  // Avoid division by zero
        {
          double resistance = fabs(probeVoltage / netProbeCurrent);
          if(resistance > 1e4/IRange) 
            resistance = 1e4/IRange;
          resetR[ProbeResNumb] = resistance;  // Store resistance (reusing resetR array)
          if(debug)printf("%s: Probe %d resistance = %g Ohms (V=%g V, I=%g A, Ioff=%g A)\n", 
            mod, ProbeResNumb, resistance, probeVoltage, netProbeCurrent, probeMeasOffsetCurrent);
        }
        else
        {
          resetR[ProbeResNumb] = 1e4/IRange;  // Very high resistance
          if(debug)printf("%s: Probe %d current too small, setting resistance to max\n", mod, ProbeResNumb);
        }

        // Store current
        setI[ProbeResNumb] = netProbeCurrent;  // Store offset-compensated current
        if(debug)printf("%s: setI[%d] = %g A (net, raw=%g A, offset=%g A)\n", 
          mod, ProbeResNumb, netProbeCurrent, probeMeasCurrent, probeMeasOffsetCurrent);

        // Return pulse times as an array
        PulseTimes[ProbeResNumb]=(measMaxTime[ProbeResNumb]+measMinTime[ProbeResNumb])/2;
      }

int looper;
 if(debug)
  { 
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
  if(measOffMinTime != NULL) free(measOffMinTime);
  if(measOffMaxTime != NULL) free(measOffMaxTime);
  FreeArraysPotDep();
  return stat;
}



__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size)
{
    int i, j;
    double ratio;
    extern int debug;
    extern int details;

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

void AllocateArraysPotDep(int pts)
{
   VFret = (double *)calloc(pts, sizeof(double));
   IFret = (double *)calloc(pts, sizeof(double));
   VMret = (double *)calloc(pts, sizeof(double));
   IMret = (double *)calloc(pts, sizeof(double));
   Tret = (double *)calloc(pts, sizeof(double));

   if(VFret == NULL || IFret == NULL || VMret == NULL || IMret == NULL || Tret == NULL)
   {
      FreeArraysPotDep();
   }
}


/* ----------------  */

void FreeArraysPotDep()
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
} 		/* End pmu_potentiation_depression.c */

