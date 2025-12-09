/* USRLIB MODULE INFORMATION

	MODULE NAME: pmu_pulse_read_interleaved_bias
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

void AllocateArraysInterleaved(int pts);
void FreeArraysInterleaved();

int ACraig1_retention_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

extern int debug;
extern int details;

extern int retention_pulse_ilimit_dual_channel_bias(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: pmu_pulse_read_interleaved_bias
==================

Description
-----------
This module implements a read, (pulse, read)xn pattern for interleaved pulse and read operations.
The waveform consists of:
1. Initial read measurement
2. For each cycle: Pulse → Read

This pattern is useful for pulse-read-repeat tests where you want to measure the device state
immediately after each programming pulse.

Waveform Structure:
------------------
1. Initial Read: Baseline measurement before any pulses
2. For NumPulses cycles:
   - Pulse: RISE → TOP (PulseWidth) → FALL → DELAY
   - Read: RISE → TOP (measWidth) → FALL → DELAY

Total measurements = 1 (initial) + NumPulses (after each pulse) = NumPulses + 1

Input and output parameters
---------------------------

See pmu_retention_dual_channel for parameter descriptions. Key differences:
- NumPulses: Number of (pulse, read) cycles (1-100)
- NumbMeasPulses: Not used in this pattern (kept for compatibility)
- NumInitialMeasPulses: Not used in this pattern (kept for compatibility)

Output arrays must be sized to accommodate: NumPulses + 1 measurements

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

void AllocateArraysInterleaved(int pts);
void FreeArraysInterleaved();

int ACraig1_retention_pulseNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts );

__declspec( dllexport ) int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
__declspec( dllexport ) void ret_report_values(double *T, int numpts, double *out, int out_size);
__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

extern int debug;
extern int details;

extern int retention_pulse_ilimit_dual_channel_bias(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);

/* USRLIB MODULE MAIN FUNCTION */
int pmu_pulse_read_interleaved_bias( double riseTime, double resetV, double resetWidth, double resetDelay, double measV, double measWidth, double measDelay, double setWidth, double setFallTime, double setDelay, double setStartV, double setStopV, int steps, double IRange, int max_points, double *setR, int setR_size, double *resetR, int resetR_size, double *setV, int setV_size, double *setI, int setI_size, int iteration, double *out1, int out1_size, char *out1_name, double *out2, int out2_size, char *out2_name, double *PulseTimes, int PulseTimesSize, int NumbMeasPulses, int NumInitialMeasPulses, int NumPulses, double PulseWidth, double PulseV, double PulseRiseTime, double PulseFallTime, double PulseDelay, int ClariusDebug )
{
/* USRLIB MODULE CODE */
  char mod[] = "pmu_pulse_read_interleaved_bias";
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

  int numpts;
  int npts;
  double vbias, resss;
  double ttime;
  int used_pts;
  int used_rate;
   
  double ratio = 0.4; // defines window where to do measurements

  /* baseline holds measV for all resting segments */
  double baseline = measV;

  double forceVRange;
  double measVRange;

  // Use maximum of resetV and PulseV for voltage range
  forceVRange = fabs(resetV) > fabs(PulseV) ? fabs(resetV) : fabs(PulseV);
  if (forceVRange < 1.0) forceVRange = 1.0;
  measVRange = 1.0;

  // Validate NumPulses (number of pulse-read cycles)
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
  // Pattern: Initial Read → (Pulse → Read) × NumPulses
  // Initial Read: 4 segments (delay, rise, width, fall, delay)
  // Each (Pulse → Read) cycle: 
  //   Pulse: 4 segments (rise, width, fall, delay)
  //   Read: 4 segments (rise, width, fall, delay)
  int calc_times_count = 2;  // initial delay + rise
  
  // Initial read: 4 segments (width, rise, delay, rise)
  calc_times_count += 4;
  
  // Each (Pulse → Read) cycle: 8 segments (4 for pulse + 4 for read)
  calc_times_count += 8 * NumPulses;
  
  // Add safety margin (10% or minimum 10 segments)
  int safety_margin = calc_times_count / 10;
  if (safety_margin < 10) safety_margin = 10;
  
  times_count = calc_times_count + safety_margin;
  volts_count = times_count + 1;

  if(debug) printf("%s: Allocating waveform buffers - calculated:%d + margin:%d = times_count:%d volts_count:%d (NumPulses:%d)\n", 
    mod, calc_times_count, safety_margin, times_count, volts_count, NumPulses);

  times = (double *)calloc(times_count, sizeof(double));
  volts = (double *)calloc(volts_count, sizeof(double));
  if(times == NULL || volts == NULL)
  {
    if(debug) printf("%s: Unable to allocate segment buffers (times:%d volts:%d)\n", mod, times_count, volts_count);
    stat = -210;
    goto RETS;
  }

  // Probe capacity: 1 initial read + NumPulses reads after pulses = NumPulses + 1
  probeCapacity = NumPulses + 1;
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
  volts[segIdx] = baseline;
  segIdx++;

  times[segIdx] = riseTime;
  ttime += times[segIdx];
  volts[segIdx] = baseline;
  segIdx++;

  // ****************
  // Initial read measurement
  // ****************
  if(recordedProbeCount >= probeCapacity)
  {
    if(debug) printf("%s: Probe capacity exceeded while recording initial read\n", mod);
    stat = -205;
    goto RETS;
  }
  measMinTime[recordedProbeCount] = ttime + ratio * measWidth; 
  measMaxTime[recordedProbeCount] = ttime + measWidth * 0.9; 
  if(debug)printf("Initial read measMinTime[%d]= %g; measMaxTime[%d]= %g\n", recordedProbeCount, measMinTime[recordedProbeCount], recordedProbeCount, measMaxTime[recordedProbeCount] );
  recordedProbeCount++;

  // Read pulse: width at measV
  times[segIdx] = measWidth;
  ttime += times[segIdx];
  volts[segIdx] = measV;
  segIdx++;

  // Rise time (transition from measV to measV - flat top)
  times[segIdx] = riseTime;
  ttime += times[segIdx];
  volts[segIdx] = measV;
  segIdx++;

  // Delay after read
  times[segIdx] = measDelay;
  ttime += times[segIdx];
  volts[segIdx] = baseline;
  segIdx++;

  // Small delay before pulse sequence
  times[segIdx] = riseTime;
  ttime += times[segIdx];
  volts[segIdx] = baseline;
  segIdx++;

  // ****************
  // Interleaved (Pulse → Read) cycles
  // ****************
  int cycleIdx;
  for (cycleIdx = 0; cycleIdx < NumPulses; cycleIdx++)
  {
    if(debug) printf("\n%s: ===== CYCLE %d/%d (Pulse → Read) ===== (segIdx=%d)\n", 
      mod, cycleIdx+1, NumPulses, segIdx);
    
    // ****************
    // PULSE: RISE → TOP → FALL → DELAY
    // ****************
    
    // RISE: Transition from baseline to PulseV over PulseRiseTime
    volts[segIdx] = baseline;  // START voltage
    times[segIdx] = PulseRiseTime;
    ttime += times[segIdx];
    if(debug) printf("%s: Cycle %d - PULSE RISE: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cycleIdx+1, segIdx, 0.0, segIdx, PulseRiseTime);
    segIdx++;
    volts[segIdx] = PulseV;  // END voltage
    if(debug) printf("%s: Cycle %d - PULSE RISE: End v[%d]=%.6fV\n",
      mod, cycleIdx+1, segIdx, PulseV);

    // TOP: Flat segment at PulseV for PulseWidth duration
    times[segIdx] = PulseWidth;
    ttime += times[segIdx];
    if(debug) printf("%s: Cycle %d - PULSE TOP: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cycleIdx+1, segIdx, PulseV, segIdx, PulseWidth);
    segIdx++;
    volts[segIdx] = PulseV;  // END voltage (same as start = flat top)
    if(debug) printf("%s: Cycle %d - PULSE TOP: End v[%d]=%.6fV (flat top)\n",
      mod, cycleIdx+1, segIdx, PulseV);

    // FALL: Transition from PulseV to baseline over PulseFallTime
    times[segIdx] = PulseFallTime;
    ttime += times[segIdx];
    if(debug) printf("%s: Cycle %d - PULSE FALL: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cycleIdx+1, segIdx, PulseV, segIdx, PulseFallTime);
    segIdx++;
    volts[segIdx] = baseline;  // END voltage of FALL (now at baseline)
    if(debug) printf("%s: Cycle %d - PULSE FALL: End v[%d]=%.6fV\n",
      mod, cycleIdx+1, segIdx, baseline);

    // DELAY: Delay at baseline after pulse, before read (read delay)
    // CRITICAL: In ret_Define_SegmentsILimit, segment i goes from v[i] to v[i+1] over t[i]
    // So for delay: v[segIdx] must be baseline (start), v[segIdx+1] must be baseline (end), t[segIdx] = PulseDelay
    // Pattern: times[segIdx] = delay, volts[segIdx] stays baseline, then segIdx++, then set volts[segIdx] = baseline
    times[segIdx] = PulseDelay;
    ttime += times[segIdx];
    if(debug) printf("%s: Cycle %d - DELAY AT baseline (read delay): Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cycleIdx+1, segIdx, baseline, segIdx, PulseDelay);
    segIdx++;
    volts[segIdx] = baseline;  // END voltage of delay segment (flat at baseline) - CRITICAL: must be set AFTER increment
    if(debug) printf("%s: Cycle %d - DELAY AT baseline: End v[%d]=%.6fV (flat delay at baseline before read)\n",
      mod, cycleIdx+1, segIdx, baseline);

    // ****************
    // READ: RISE → TOP (read width) → FALL → DELAY
    // ****************
    
    // RISE: Transition from baseline to measV over riseTime
    // Segment goes from v[segIdx] (baseline, from delay end) to v[segIdx+1] (measV) over t[segIdx]
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    if(debug) printf("%s: Cycle %d - READ RISE: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cycleIdx+1, segIdx, baseline, segIdx, riseTime);
    segIdx++;
    volts[segIdx] = measV;  // END voltage of RISE
    if(debug) printf("%s: Cycle %d - READ RISE: End v[%d]=%.6fV\n",
      mod, cycleIdx+1, segIdx, measV);

    // TOP: Measurement pulse width at measV (read width - delay at measV)
    times[segIdx] = measWidth;
    if(recordedProbeCount >= probeCapacity)
    {
      if(debug) printf("%s: Probe capacity exceeded while recording read after pulse %d\n", mod, cycleIdx+1);
      stat = -205;
      goto RETS;
    }
    measMinTime[recordedProbeCount] = ttime + ratio * measWidth; 
    measMaxTime[recordedProbeCount] = ttime + measWidth * 0.9;
    if(debug)printf("Read after pulse %d measMinTime[%d]= %g; measMaxTime[%d]= %g\n", 
      cycleIdx+1, recordedProbeCount, measMinTime[recordedProbeCount], recordedProbeCount, measMaxTime[recordedProbeCount] );
    recordedProbeCount++;
    ttime += times[segIdx];
    volts[segIdx] = measV;  // Stay at measV during measurement window
    segIdx++;

    // FALL delay at measV (setFallTime) - optional settling time
    times[segIdx] = setFallTime;
    ttime += times[segIdx];
    volts[segIdx] = measV;
    segIdx++;

    // FALL: Transition from measV to baseline over riseTime
    times[segIdx] = riseTime;
    ttime += times[segIdx];
    if(debug) printf("%s: Cycle %d - READ FALL: Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cycleIdx+1, segIdx, measV, segIdx, riseTime);
    segIdx++;
    volts[segIdx] = baseline;  // END voltage of FALL (now at baseline)
    if(debug) printf("%s: Cycle %d - READ FALL: End v[%d]=%.6fV\n",
      mod, cycleIdx+1, segIdx, baseline);

    // DELAY: Delay at baseline after read, before next cycle (delay between cycles)
    // CRITICAL: In ret_Define_SegmentsILimit, segment i goes from v[i] to v[i+1] over t[i]
    // So for delay: v[segIdx] must be baseline (start), v[segIdx+1] must be baseline (end), t[segIdx] = measDelay
    // Pattern: times[segIdx] = delay, volts[segIdx] stays baseline, then segIdx++, then set volts[segIdx] = baseline
    times[segIdx] = measDelay;
    ttime += times[segIdx];
    if(debug) printf("%s: Cycle %d - DELAY AT baseline (between cycles): Start v[%d]=%.6fV, time t[%d]=%.9fs\n",
      mod, cycleIdx+1, segIdx, baseline, segIdx, measDelay);
    segIdx++;
    volts[segIdx] = baseline;  // END voltage of delay segment (flat at baseline) - CRITICAL: must be set AFTER increment
    if(debug) printf("%s: Cycle %d - DELAY AT baseline: End v[%d]=%.6fV (flat delay at baseline before next cycle)\n",
      mod, cycleIdx+1, segIdx, baseline);
  }
  
  if(debug) printf("%s: Interleaved cycles complete (segIdx=%d)\n", mod, segIdx);

  // Final voltage point
  volts[segIdx] = baseline;
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

  AllocateArraysInterleaved(used_pts);
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
// this calls retention_pulse_ilimit_dual_channel_bias in "retention_pulse_ilimit_dual_channel_bias.c", it sets Force Channel to 1 and Measurement Channel 2 (2nd and 7th parameter)
// and collects forced voltage and current values from both the ForceCh and MeasureCh channels.
// The segments are created based on the settings provided by the operator within the 'Volts' and 'Times' input arrays, and measurements 
// are returned via of the voltage(VF and VM) and current (IF and IM) output arrays for both channels.

      stat = retention_pulse_ilimit_dual_channel_bias
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
  FreeArraysInterleaved();
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

void AllocateArraysInterleaved(int pts)
{
   VFret = (double *)calloc(pts, sizeof(double));
   IFret = (double *)calloc(pts, sizeof(double));
   VMret = (double *)calloc(pts, sizeof(double));
   IMret = (double *)calloc(pts, sizeof(double));
   Tret = (double *)calloc(pts, sizeof(double));

   if(VFret == NULL || IFret == NULL || VMret == NULL || IMret == NULL || Tret == NULL)
   {
      FreeArraysInterleaved();
   }
}


/* ----------------  */

void FreeArraysInterleaved()
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
} 		/* End pmu_pulse_read_interleaved_bias.c */

