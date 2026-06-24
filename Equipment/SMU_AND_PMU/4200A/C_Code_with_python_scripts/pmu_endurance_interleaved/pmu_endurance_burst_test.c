/* USRLIB MODULE INFORMATION

	MODULE NAME: pmu_endurance_burst_test
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
		PulseTimesSize,	int,	Input,	12,	1,	30000
		NumbMeasPulses,	int,	Input,	8,	1,	1000
		NumInitialMeasPulses,	int,	Input,	1,	1,	100
		NumPulses,	int,	Input,	5,	1,	1000
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
#include "pmu_burst_common.h"

static double *VFret = NULL;
static double *IFret = NULL;
static double *VMret = NULL;
static double *IMret = NULL;
static double *Tret = NULL;

static void AllocateArraysInterleaved(int pts);
static void FreeArraysInterleaved(void);

static int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
static void ret_report_values(double *T, int numpts, double *out, int out_size);
extern int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

extern int debug;
extern int details;

extern int retention_pulse_ilimit_dual_channel(char* InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double* Volte, int volts_size, double* Times, int times_size, double* VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double* IM, int im_size, double* T, int t_size, int* npts);
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
Module: pmu_endurance_burst_test
==================
Experimental: same EX signature as pmu_endurance_interleaved but NumPulses is TOTAL
cycles (1-1000). Builds one continuous seg-arb waveform when segment count allows
(up to ~350 segments per retention_pulse call, ~19 cycles); larger counts split into
back-to-back internal sub-bursts within the same EX (burst 2+ skips Initial Read).
	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pmu_burst_common.h"

static double *VFret = NULL;
static double *IFret = NULL;
static double *VMret = NULL;
static double *IMret = NULL;
static double *Tret = NULL;

static void AllocateArraysInterleaved(int pts);
static void FreeArraysInterleaved(void);
static int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result);
static void ret_report_values(double *T, int numpts, double *out, int out_size);

extern int debug;
extern int details;

extern int retention_pulse_ilimit_dual_channel(
    char *InstrName, long ForceCh, double ForceVRange, double ForceIRange,
    double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange,
    double MeasureIRange, int max_pts, double MeasureBias, double *Volte,
    int volts_size, double *Times, int times_size, double *VF, int vf_size,
    double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size,
    double *T, int t_size, int *npts);

extern int ret_getRate(double ttime, int maxpts, int *apts, int *npts);

typedef struct {
  double riseTime;
  double resetV;
  double resetDelay;
  double measV;
  double measWidth;
  double measDelay;
  double setFallTime;
  double setStopV;
  double PulseWidth;
  double PulseV;
  double PulseRiseTime;
  double PulseFallTime;
  double PulseDelay;
  double IRange;
  int max_points;
  double ratio;
} EnduranceBurstParams;

/* Build one internal burst waveform; returns probe count or negative error. */
static int build_endurance_burst_waveform(
    EnduranceBurstParams *p,
    int numCyclesThisBurst,
    int skipInitialRead,
    double *times,
    int times_count,
    double *volts,
    int volts_count,
    double *measMinTime,
    double *measMaxTime,
    int measCapacity,
    double *outTtime,
    int *outSegIdx)
{
  char mod[] = "pmu_endurance_burst_test";
  int segIdx = 0;
  int recordedProbeCount = 0;
  double ttime = 0.0;
  int cycleIdx;
  int half;
  double progV;
  int calc_times_count;
  int i;

  if (numCyclesThisBurst < 1)
    return -213;

  calc_times_count = skipInitialRead ? 0 : (2 + 4);
  calc_times_count += 18 * numCyclesThisBurst;

  if (calc_times_count > times_count)
  {
    if (debug)
      printf("%s: burst waveform needs %d segments, allocated %d\n", mod, calc_times_count, times_count);
    return -211;
  }

  ttime = 0.0;
  segIdx = 0;

  if (!skipInitialRead)
  {
    times[segIdx] = p->resetDelay;
    ttime += times[segIdx];
    volts[segIdx] = 0.0;
    segIdx++;

    times[segIdx] = p->riseTime;
    ttime += times[segIdx];
    volts[segIdx] = 0.0;
    segIdx++;

    if (recordedProbeCount >= measCapacity)
      return -205;
    measMinTime[recordedProbeCount] = ttime + p->ratio * p->measWidth;
    measMaxTime[recordedProbeCount] = ttime + p->measWidth * 0.9;
    recordedProbeCount++;

    times[segIdx] = p->measWidth;
    ttime += times[segIdx];
    volts[segIdx] = p->measV;
    segIdx++;

    times[segIdx] = p->riseTime;
    ttime += times[segIdx];
    volts[segIdx] = p->measV;
    segIdx++;

    times[segIdx] = p->measDelay;
    ttime += times[segIdx];
    volts[segIdx] = 0.0;
    segIdx++;

    times[segIdx] = p->riseTime;
    ttime += times[segIdx];
    volts[segIdx] = 0.0;
    segIdx++;
  }

  for (cycleIdx = 0; cycleIdx < numCyclesThisBurst; cycleIdx++)
  {
    for (half = 0; half < 2; half++)
    {
      progV = (half == 0) ? p->PulseV : p->setStopV;

      volts[segIdx] = 0.0;
      times[segIdx] = p->PulseRiseTime;
      ttime += times[segIdx];
      segIdx++;
      volts[segIdx] = progV;

      times[segIdx] = p->PulseWidth;
      ttime += times[segIdx];
      segIdx++;
      volts[segIdx] = progV;

      times[segIdx] = p->PulseFallTime;
      ttime += times[segIdx];
      segIdx++;
      volts[segIdx] = 0.0;

      times[segIdx] = p->PulseDelay;
      ttime += times[segIdx];
      segIdx++;
      volts[segIdx] = 0.0;

      times[segIdx] = p->riseTime;
      ttime += times[segIdx];
      segIdx++;
      volts[segIdx] = p->measV;

      times[segIdx] = p->measWidth;
      if (recordedProbeCount >= measCapacity)
        return -205;
      measMinTime[recordedProbeCount] = ttime + p->ratio * p->measWidth;
      measMaxTime[recordedProbeCount] = ttime + p->measWidth * 0.9;
      recordedProbeCount++;
      ttime += times[segIdx];
      segIdx++;
      volts[segIdx] = p->measV;

      times[segIdx] = p->setFallTime;
      ttime += times[segIdx];
      segIdx++;
      volts[segIdx] = p->measV;

      times[segIdx] = p->riseTime;
      ttime += times[segIdx];
      segIdx++;
      volts[segIdx] = 0.0;

      if (half == 1)
      {
        times[segIdx] = p->measDelay;
        ttime += times[segIdx];
        segIdx++;
        volts[segIdx] = 0.0;
      }
    }
  }

  volts[segIdx] = 0.0;

  for (i = 0; i < segIdx; i++)
  {
    if (times[i] <= 0.0 || times[i] != times[i])
      return -122;
  }

  if (segIdx + 1 > volts_count || segIdx > times_count)
    return -211;

  *outTtime = ttime;
  *outSegIdx = segIdx;
  return recordedProbeCount;
}

static int execute_burst_extract_probes(
    EnduranceBurstParams *p,
    double *times,
    int NewTimesSize,
    double *volts,
    int NewVoltsSize,
    double *measMinTime,
    double *measMaxTime,
    int recordedProbeCount,
    double timeOffset,
    int outProbeOffset,
    double *setV,
    double *setI,
    double *resetR,
    double *PulseTimes,
    int outCapacity,
    double forceVRange,
    double measVRange,
    double burstTtime,
    double *outLastPulseTime)
{
  char mod[] = "pmu_endurance_burst_test";
  char inst[] = "PMU1";
  int stat;
  int used_pts;
  int used_rate;
  int npts;
  int numpts;
  int ProbeResNumb;
  double probeCurrent;
  double probeVoltage;
  double resistance;
  double pulseTime;

  if (outProbeOffset + recordedProbeCount > outCapacity)
    return -204;

  used_rate = ret_getRate(burstTtime, p->max_points, &used_pts, &npts);
  if (used_rate <= 0)
    return -207;
  if (debug)
    printf("%s: sub-burst duration %g s, used_pts %d, rate %d Hz, re-arm=%s\n",
           mod, burstTtime, used_pts, used_rate, outProbeOffset > 0 ? "yes" : "first");

  AllocateArraysInterleaved(used_pts);
  if (VFret == NULL || IFret == NULL || VMret == NULL || IMret == NULL || Tret == NULL)
    return -207;

  {
    int eff_max_pts = used_pts + 64;
    if (eff_max_pts < 256)
      eff_max_pts = 256;
    if (eff_max_pts > p->max_points)
      eff_max_pts = p->max_points;

    stat = retention_pulse_ilimit_dual_channel(
        inst,
        (long)1, forceVRange, p->IRange,
        0.0, 0.0,
        (long)2, measVRange, p->IRange, eff_max_pts, 0.0,
        volts, NewVoltsSize, times, NewVoltsSize - 1,
        VFret, used_pts, IFret, used_pts, VMret, used_pts,
        IMret, used_pts, Tret, used_pts, &numpts);
  }

  if (stat < 0)
  {
    if (debug)
      printf("%s: retention_pulse_ilimit_dual_channel failed %d\n", mod, stat);
    FreeArraysInterleaved();
    return -90;
  }

  for (ProbeResNumb = 0; ProbeResNumb < recordedProbeCount; ProbeResNumb++)
  {
    int outIdx = outProbeOffset + ProbeResNumb;

    probeCurrent = 0.0;
    stat = ret_find_value(IMret, Tret, numpts,
                          measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &probeCurrent);
    if (stat < 0)
    {
      FreeArraysInterleaved();
      return -92;
    }

    if (fabs(probeCurrent) > 1e-12)
    {
      resistance = fabs(p->measV / probeCurrent);
      if (resistance > 1e4 / p->IRange)
        resistance = 1e4 / p->IRange;
    }
    else
    {
      resistance = 1e4 / p->IRange;
    }
    resetR[outIdx] = resistance;

    probeVoltage = 0.0;
    stat = ret_find_value(VMret, Tret, numpts,
                          measMinTime[ProbeResNumb], measMaxTime[ProbeResNumb], &probeVoltage);
    if (stat < 0)
    {
      FreeArraysInterleaved();
      return -93;
    }

    setV[outIdx] = probeVoltage;
    setI[outIdx] = probeCurrent;
    pulseTime = (measMaxTime[ProbeResNumb] + measMinTime[ProbeResNumb]) / 2.0 + timeOffset;
    PulseTimes[outIdx] = pulseTime;
    *outLastPulseTime = pulseTime;
  }

  FreeArraysInterleaved();
  return recordedProbeCount;
}

/* USRLIB MODULE MAIN FUNCTION */
int pmu_endurance_burst_test(
    double riseTime, double resetV, double resetWidth, double resetDelay,
    double measV, double measWidth, double measDelay,
    double setWidth, double setFallTime, double setDelay,
    double setStartV, double setStopV, int steps, double IRange, int max_points,
    double *setR, int setR_size, double *resetR, int resetR_size,
    double *setV, int setV_size, double *setI, int setI_size,
    int iteration, double *out1, int out1_size, char *out1_name,
    double *out2, int out2_size, char *out2_name,
    double *PulseTimes, int PulseTimesSize,
    int NumbMeasPulses, int NumInitialMeasPulses, int NumPulses,
    double PulseWidth, double PulseV, double PulseRiseTime, double PulseFallTime,
    double PulseDelay, int ClariusDebug)
{
/* USRLIB MODULE CODE */
  char mod[] = "pmu_endurance_burst_test";
  int stat = 1;
  int i;
  int totalCycles;
  int cyclesDone = 0;
  int burstNum = 0;
  int probeIdx = 0;
  double timeOffset = 0.0;
  double lastPulseTime = 0.0;
  int totalProbes;
  double forceVRange;
  double measVRange = 1.0;
  EnduranceBurstParams bp;

  double *times = NULL;
  double *volts = NULL;
  double *measMinTime = NULL;
  double *measMaxTime = NULL;
  int burstMeasCap;
  int times_count;
  int volts_count;
  int nBurst;
  int skipInitial;
  int recordedProbeCount;
  int NewVoltsSize;
  int NewTimesSize;
  int segIdx;
  double ttime;

  if (ClariusDebug == 1)
    debug = 1;
  else
    debug = 0;

  totalCycles = NumPulses;
  if (totalCycles < 1 || totalCycles > 1000)
  {
    if (debug)
      printf("%s: NumPulses (total cycles) must be 1-1000 (got %d)\n", mod, totalCycles);
    return -213;
  }

  totalProbes = 1 + 2 * totalCycles;
  if (PulseTimes == NULL || setV == NULL || setI == NULL || resetR == NULL)
    return -202;
  if (PulseTimesSize < totalProbes || setV_size < totalProbes || setI_size < totalProbes
      || resetR_size < totalProbes)
    return -204;

  if (PulseWidth < 2e-8 || PulseRiseTime < 2e-8 || PulseFallTime < 2e-8 || PulseDelay < 2e-8)
    return -122;

  forceVRange = fabs(PulseV);
  if (fabs(setStopV) > forceVRange)
    forceVRange = fabs(setStopV);
  if (fabs(resetV) > forceVRange)
    forceVRange = fabs(resetV);
  if (forceVRange < 1.0)
    forceVRange = 1.0;

  bp.riseTime = riseTime;
  bp.resetV = resetV;
  bp.resetDelay = resetDelay;
  bp.measV = measV;
  bp.measWidth = measWidth;
  bp.measDelay = measDelay;
  bp.setFallTime = setFallTime;
  bp.setStopV = setStopV;
  bp.PulseWidth = PulseWidth;
  bp.PulseV = PulseV;
  bp.PulseRiseTime = PulseRiseTime;
  bp.PulseFallTime = PulseFallTime;
  bp.PulseDelay = PulseDelay;
  bp.IRange = IRange;
  bp.max_points = max_points;
  bp.ratio = 0.4;

  for (i = 0; i < PulseTimesSize; ++i)
    PulseTimes[i] = 0.0;
  for (i = 0; i < setV_size; ++i)
    setV[i] = setI[i] = 0.0;

  if (debug)
    printf("%s: totalCycles=%d totalProbes=%d seg_budget=%d max_cycles_one_waveform=%d\n",
           mod, totalCycles, totalProbes, PMU_MAX_SEG_PER_BURST,
           pmu_max_endurance_cycles_per_burst(0));

  /* Prefer one continuous waveform (no inter-burst PMU idle) when segment count allows. */
  if (pmu_endurance_seg_estimate(totalCycles, 0) <= PMU_MAX_SEG_PER_BURST)
  {
    int nBurst = totalCycles;
    int burstMeasCap = pmu_endurance_probes_this_burst(nBurst, 0);
    int times_count = pmu_endurance_seg_estimate(nBurst, 0) + 20;
    int volts_count = times_count + 1;
    int recordedProbeCount;
    int NewVoltsSize;
    int NewTimesSize;
    int segIdx;
    double ttime;

    times = (double *)calloc(times_count, sizeof(double));
    volts = (double *)calloc(volts_count, sizeof(double));
    measMinTime = (double *)calloc(burstMeasCap, sizeof(double));
    measMaxTime = (double *)calloc(burstMeasCap, sizeof(double));
    if (times == NULL || volts == NULL || measMinTime == NULL || measMaxTime == NULL)
      return -210;

    if (debug)
      printf("%s: single continuous waveform (%d cycles, %d probes)\n",
             mod, nBurst, burstMeasCap);

    recordedProbeCount = build_endurance_burst_waveform(
        &bp, nBurst, 0,
        times, times_count, volts, volts_count,
        measMinTime, measMaxTime, burstMeasCap, &ttime, &segIdx);

    if (recordedProbeCount < 0)
    {
      stat = recordedProbeCount;
      goto CLEAN_BURST;
    }

    NewTimesSize = segIdx;
    NewVoltsSize = segIdx + 1;

    stat = execute_burst_extract_probes(
        &bp, times, NewTimesSize, volts, NewVoltsSize,
        measMinTime, measMaxTime, recordedProbeCount,
        0.0, 0,
        setV, setI, resetR, PulseTimes, totalProbes,
        forceVRange, measVRange, ttime, &lastPulseTime);

    if (stat < 0)
      goto CLEAN_BURST;

    burstNum = 1;
    probeIdx = stat;
    cyclesDone = nBurst;
    goto FINISH_BURST_TEST;
  }

  while (cyclesDone < totalCycles)
  {
    int remaining = totalCycles - cyclesDone;

    skipInitial = (burstNum > 0) ? 1 : 0;
    nBurst = pmu_max_endurance_cycles_per_burst(skipInitial);
    if (nBurst > remaining)
      nBurst = remaining;

    burstMeasCap = pmu_endurance_probes_this_burst(nBurst, skipInitial);
    times_count = pmu_endurance_seg_estimate(nBurst, skipInitial) + 20;
    volts_count = times_count + 1;

    times = (double *)calloc(times_count, sizeof(double));
    volts = (double *)calloc(volts_count, sizeof(double));
    measMinTime = (double *)calloc(burstMeasCap, sizeof(double));
    measMaxTime = (double *)calloc(burstMeasCap, sizeof(double));
    if (times == NULL || volts == NULL || measMinTime == NULL || measMaxTime == NULL)
    {
      stat = -210;
      goto CLEAN_BURST;
    }

    if (debug)
      printf("%s: internal sub-burst %d: cycles %d..%d nBurst=%d skipInitial=%d probes=%d\n",
             mod, burstNum + 1, cyclesDone + 1, cyclesDone + nBurst, nBurst, skipInitial, burstMeasCap);

    recordedProbeCount = build_endurance_burst_waveform(
        &bp, nBurst, skipInitial,
        times, times_count, volts, volts_count,
        measMinTime, measMaxTime, burstMeasCap, &ttime, &segIdx);

    if (recordedProbeCount < 0)
    {
      stat = recordedProbeCount;
      goto CLEAN_BURST;
    }

    NewTimesSize = segIdx;
    NewVoltsSize = segIdx + 1;

    stat = execute_burst_extract_probes(
        &bp, times, NewTimesSize, volts, NewVoltsSize,
        measMinTime, measMaxTime, recordedProbeCount,
        timeOffset, probeIdx,
        setV, setI, resetR, PulseTimes, totalProbes,
        forceVRange, measVRange, ttime, &lastPulseTime);

    if (stat < 0)
      goto CLEAN_BURST;

    probeIdx += recordedProbeCount;
    timeOffset = lastPulseTime;
    cyclesDone += nBurst;
    burstNum++;

    free(times);
    times = NULL;
    free(volts);
    volts = NULL;
    free(measMinTime);
    measMinTime = NULL;
    free(measMaxTime);
    measMaxTime = NULL;
  }

FINISH_BURST_TEST:
  if (times != NULL)
    free(times);
  if (volts != NULL)
    free(volts);
  if (measMinTime != NULL)
    free(measMinTime);
  if (measMaxTime != NULL)
    free(measMaxTime);
  times = NULL;
  volts = NULL;
  measMinTime = NULL;
  measMaxTime = NULL;

  if (debug)
    printf("%s: complete %d burst(s), %d probes (expected %d), stat=%d\n",
           mod, burstNum, probeIdx, totalProbes, stat);

  if (stat < 0)
    return stat;
  if (probeIdx < 1)
    return -90;
  if (probeIdx != totalProbes && debug)
    printf("%s: WARNING probe count %d != expected %d\n", mod, probeIdx, totalProbes);

  return 1;

CLEAN_BURST:
  if (times != NULL)
    free(times);
  if (volts != NULL)
    free(volts);
  if (measMinTime != NULL)
    free(measMinTime);
  if (measMaxTime != NULL)
    free(measMaxTime);
  FreeArraysInterleaved();
  return stat;
}

static void ret_report_values(double *T, int numpts, double *out, int out_size)
{
  int i, j;
  double ratio;

  if (out_size < 1 || numpts < 1)
    return;
  ratio = (((double)numpts - 1.0) / ((double)out_size - 1.0));
  for (i = 0; i < out_size; i++)
  {
    j = (int)(ratio * i);
    out[i] = T[j];
  }
}

static void AllocateArraysInterleaved(int pts)
{
  VFret = (double *)calloc(pts, sizeof(double));
  IFret = (double *)calloc(pts, sizeof(double));
  VMret = (double *)calloc(pts, sizeof(double));
  IMret = (double *)calloc(pts, sizeof(double));
  Tret = (double *)calloc(pts, sizeof(double));
  if (VFret == NULL || IFret == NULL || VMret == NULL || IMret == NULL || Tret == NULL)
    FreeArraysInterleaved();
}

static void FreeArraysInterleaved(void)
{
  if (VFret != NULL) { free(VFret); VFret = NULL; }
  if (IFret != NULL) { free(IFret); IFret = NULL; }
  if (VMret != NULL) { free(VMret); VMret = NULL; }
  if (IMret != NULL) { free(IMret); IMret = NULL; }
  if (Tret != NULL) { free(Tret); Tret = NULL; }
}

static int ret_find_value(double *vals, double *t, int pts, double start, double stop, double *result)
{
  int stat = -1;
  double sum = 0.0;
  int i = 0;
  int actpts = 0;

  *result = -999.0;
  while (i < pts && t[i] <= stop)
  {
    if (t[i] >= start)
    {
      sum += vals[i];
      actpts++;
    }
    i++;
  }
  if (actpts > 0)
  {
    *result = sum / actpts;
    stat = 1;
  }
  return stat;
}

/* USRLIB MODULE END */
