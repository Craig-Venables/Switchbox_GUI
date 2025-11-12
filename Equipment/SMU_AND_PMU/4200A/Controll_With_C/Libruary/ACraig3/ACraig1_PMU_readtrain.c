/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig1_PMU_readtrain
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 19
	ARGUMENTS:
		riseTime,	double,	Input,	3e-8,	2e-8,	1
		measV,	double,	Input,	0.3,	-20,	20
		measWidth,	double,	Input,	1e-6,	2e-8,	1
		measDelay,	double,	Input,	1e-6,	2e-8,	1
		numPulses,	int,	Input,	12,	1,	200
		triggerPulse,	int,	Input,	1,	1,	200
		iRange,	double,	Input,	1e-4,	100e-9,	0.8
		max_points,	int,	Input,	10000,	12,	30000
		readV,	D_ARRAY_T,	Output,	,	,	
		readV_size,	int,	Input,	12,	1,	30000
		readI,	D_ARRAY_T,	Output,	,	,	
		readI_size,	int,	Input,	12,	1,	30000
		PulseTimes,	D_ARRAY_T,	Output,	,	,	
		PulseTimes_size,	int,	Input,	12,	1,	30000
		out1,	D_ARRAY_T,	Output,	,	,	
		out1_size,	int,	Input,	12,	1,	30000
		out1_name,	char *,	Input,	"VF",	,	
		iteration,	int,	Input,	1,	1,	1000
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

double *VFread = NULL;
double *IFread = NULL;
double *VMread = NULL;
double *IMread = NULL;
double *Tread  = NULL;

void AllocateArraysRead(int pts);
void FreeArraysRead(void);

int ACraig1_retention_pulse_ilimitNK(char *InstrName,
                                     long ForceCh,
                                     double ForceVRange,
                                     double ForceIRange,
                                     double iFLimit,
                                     double iMLimit,
                                     long MeasureCh,
                                     double MeasureVRange,
                                     double MeasureIRange,
                                     int max_pts,
                                     double MeasureBias,
                                     double *Volts,
                                     int volts_size,
                                     double *Times,
                                     int times_size,
                                     double *VF,
                                     int vf_size,
                                     double *IF,
                                     int if_size,
                                     double *VM,
                                     int vm_size,
                                     double *IM,
                                     int im_size,
                                     double *T,
                                     int t_size,
                                     int *npts);

__declspec(dllexport) int ret_find_value(double *vals, double *t, int pts,
                                         double start, double stop,
                                         double *result);
__declspec(dllexport) void ret_report_values(double *T, int numpts,
                                             double *out, int out_size);
__declspec(dllexport) int ret_getRate(double ttime, int maxpts,
                                      int *apts, int *npts);
void ret_set_trigger_override(int segmentIndex);

extern int debug;
extern int details;
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
Module: ACraig1_PMU_readtrain
=============================

Description
-----------
Creates a sequence of read-only pulses (rise->measure->fall->delay) with no
reset/set pulses. A designated measurement plateau sends the hardware trigger,
and each plateau is averaged to produce read voltage/current values. Use this
to extend read-only retention sampling without the overhead of the full
retention waveform.

Parameters
----------
- **riseTime**: Rise/fall time for each pulse edge (s).
- **measV**: Measurement voltage applied during each plateau (V).
- **measWidth**: Duration of the plateau (s).
- **measDelay**: Delay at zero between pulses (s).
- **numPulses**: Number of read pulses to generate.
- **triggerPulse**: 1-based index of the pulse that should issue the
  hardware trigger.
- **iRange**: Current range used for both measure and force channels (A).
- **max_points**: Maximum points allowed for data acquisition.
- **readV/readI**: Output arrays for averaged voltage/current per pulse.
- **PulseTimes**: Output array of midpoint times used for averaging.
- **out1**: Optional debug array (e.g., "VF" to copy voltages).
- **iteration**: Iteration index (included for parity with other modules).
- **ClariusDebug**: Enables verbose logging when set to 1.

All output arrays must be sized to at least `numPulses`.
	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

double *VFread = NULL;
double *IFread = NULL;
double *VMread = NULL;
double *IMread = NULL;
double *Tread  = NULL;

void AllocateArraysRead(int pts);
void FreeArraysRead(void);

int ACraig1_retention_pulse_ilimitNK(char *InstrName,
                                     long ForceCh,
                                     double ForceVRange,
                                     double ForceIRange,
                                     double iFLimit,
                                     double iMLimit,
                                     long MeasureCh,
                                     double MeasureVRange,
                                     double MeasureIRange,
                                     int max_pts,
                                     double MeasureBias,
                                     double *Volts,
                                     int volts_size,
                                     double *Times,
                                     int times_size,
                                     double *VF,
                                     int vf_size,
                                     double *IF,
                                     int if_size,
                                     double *VM,
                                     int vm_size,
                                     double *IM,
                                     int im_size,
                                     double *T,
                                     int t_size,
                                     int *npts);

__declspec(dllexport) int ret_find_value(double *vals, double *t, int pts,
                                         double start, double stop,
                                         double *result);
__declspec(dllexport) void ret_report_values(double *T, int numpts,
                                             double *out, int out_size);
__declspec(dllexport) int ret_getRate(double ttime, int maxpts,
                                      int *apts, int *npts);
void ret_set_trigger_override(int segmentIndex);

extern int debug;
extern int details;

/* USRLIB MODULE MAIN FUNCTION */
int ACraig1_PMU_readtrain( double riseTime, double measV, double measWidth, double measDelay, int numPulses, int triggerPulse, double iRange, int max_points, double *readV, int readV_size, double *readI, int readI_size, double *PulseTimes, int PulseTimes_size, double *out1, int out1_size, char *out1_name, int iteration, int ClariusDebug )
{
/* USRLIB MODULE CODE */
  const char *mod = "ACraig1_PMU_readtrain";
  const double window_low  = 0.5;
  const double window_high = 0.7;
  const double forceVRange = fabs(measV) > 0 ? fabs(measV) : 1.0;
  const double measVRange  = 1.0;

  double *times = NULL;
  double *volts = NULL;
  double *measMinTime = NULL;
  double *measMaxTime = NULL;
  int *plateauSegment = NULL;

  int seg = 0;
  int plateauCount = 0;
  int totalProbes = numPulses;
  int totalSegments;
  int triggerSegment = -1;

  double ttime = 0.0;
  int used_pts = 0;
  int npts = 0;
  int status = 1;
  double result = 0.0;

  if (numPulses < 1)
    return -10;
  if (triggerPulse < 1 || triggerPulse > numPulses)
    return -11;
  if (readV_size < numPulses || readI_size < numPulses ||
      PulseTimes_size < numPulses || out1_size < numPulses)
    return -12;

  totalSegments = (numPulses * 4) + 1;

  times = (double *)calloc(totalSegments, sizeof(double));
  volts = (double *)calloc(totalSegments + 1, sizeof(double));
  measMinTime = (double *)calloc(totalProbes, sizeof(double));
  measMaxTime = (double *)calloc(totalProbes, sizeof(double));
  plateauSegment = (int *)calloc(totalProbes, sizeof(int));

  if (!times || !volts || !measMinTime || !measMaxTime || !plateauSegment)
  {
    status = -13;
    goto CLEANUP;
  }

  debug = ClariusDebug ? 1 : 0;

  volts[0] = 0.0;

  times[seg] = measDelay;
  ttime += times[seg];
  volts[seg + 1] = 0.0;
  seg++;

  for (int i = 0; i < numPulses; ++i)
  {
    times[seg] = riseTime;
    volts[seg + 1] = measV;
    ttime += times[seg];
    seg++;

    plateauSegment[plateauCount] = seg;
    measMinTime[plateauCount] = ttime + window_low * measWidth;
    measMaxTime[plateauCount] = ttime + window_high * measWidth;
    if (PulseTimes)
      PulseTimes[plateauCount] = (measMinTime[plateauCount] +
                                  measMaxTime[plateauCount]) / 2.0;

    times[seg] = measWidth;
    volts[seg + 1] = measV;
    ttime += times[seg];
    seg++;
    plateauCount++;

    times[seg] = riseTime;
    volts[seg + 1] = 0.0;
    ttime += times[seg];
    seg++;

    times[seg] = measDelay;
    volts[seg + 1] = 0.0;
    ttime += times[seg];
    seg++;
  }

  int used_rate = ret_getRate(ttime, max_points, &used_pts, &npts);
  if (used_rate < 0)
  {
    status = -14;
    goto CLEANUP;
  }

  AllocateArraysRead(used_pts);
  if (!VFread || !IFread || !IMread || !Tread)
  {
    status = -15;
    goto CLEANUP;
  }

  triggerSegment = plateauSegment[triggerPulse - 1];
  ret_set_trigger_override(triggerSegment);

  status = ACraig1_retention_pulse_ilimitNK("PMU1",
                                            (long)1,
                                            forceVRange,
                                            iRange,
                                            0.0,
                                            0.0,
                                            (long)2,
                                            measVRange,
                                            iRange,
                                            max_points,
                                            0.0,
                                            volts,
                                            seg + 1,
                                            times,
                                            seg,
                                            VFread,
                                            used_pts,
                                            IFread,
                                            used_pts,
                                            VMread,
                                            used_pts,
                                            IMread,
                                            used_pts,
                                            Tread,
                                            used_pts,
                                            &npts);

  ret_set_trigger_override(-1);

  if (status < 0)
  {
    status = -16;
    goto CLEANUP;
  }

  {
    int samples = (npts < used_pts) ? npts : used_pts;

    for (int i = 0; i < totalProbes; ++i)
    {
      if (i < readV_size)
      {
        if (ret_find_value(VFread, Tread, samples,
                           measMinTime[i], measMaxTime[i], &result) < 0)
          readV[i] = 0.0;
        else
          readV[i] = result;
      }

      if (i < readI_size)
      {
        if (ret_find_value(IMread, Tread, samples,
                           measMinTime[i], measMaxTime[i], &result) < 0)
          readI[i] = 0.0;
        else
          readI[i] = result;
      }

      if (PulseTimes && i < PulseTimes_size)
        PulseTimes[i] = (measMinTime[i] + measMaxTime[i]) / 2.0;

      if (out1 && out1_name && out1_name[0] != '\0' && i < out1_size)
      {
        if (strcmp(out1_name, "VF") == 0)
          out1[i] = readV[i];
        else if (strcmp(out1_name, "IM") == 0)
          out1[i] = readI[i];
        else
          out1[i] = 0.0;
      }
    }
  }

  status = 1;

CLEANUP:
  FreeArraysRead();

  if (times) free(times);
  if (volts) free(volts);
  if (measMinTime) free(measMinTime);
  if (measMaxTime) free(measMaxTime);
  if (plateauSegment) free(plateauSegment);

  return status;
}

void AllocateArraysRead(int pts)
{
  VFread = (double *)calloc(pts, sizeof(double));
  IFread = (double *)calloc(pts, sizeof(double));
  VMread = (double *)calloc(pts, sizeof(double));
  IMread = (double *)calloc(pts, sizeof(double));
  Tread  = (double *)calloc(pts, sizeof(double));

  if (!VFread || !IFread || !VMread || !IMread || !Tread)
    FreeArraysRead();
}

void FreeArraysRead(void)
{
  if (VFread) { free(VFread); VFread = NULL; }
  if (IFread) { free(IFread); IFread = NULL; }
  if (VMread) { free(VMread); VMread = NULL; }
  if (IMread) { free(IMread); IMread = NULL; }
  if (Tread)  { free(Tread);  Tread  = NULL; }
/* USRLIB MODULE END  */
} 		/* End ACraig1_PMU_readtrain.c */

