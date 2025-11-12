/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig13_PMU_Waveform_FlexSegArb
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 40
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
		baseV,	double,	Input,	0,	-40,	40
		acqType,	int,	Input,	1,	0,	1
		LLEComp,	int,	Input,	0,	0,	1
		preDataPct,	double,	Input,	.2,	0,	1.0
		postDataPct,	double,	Input,	.2,	0,	1.0
		pulseAvgCnt,	int,	Input,	1,	1,	10000
		burstCount,	int,	Input,	50,	1,	100000
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
		Ch2Enable,	int,	Input,	0,	0,	1
		Ch2VRange,	double,	Input,	10,	5,	40
		Ch2NumSegments,	int,	Input,	5,	3,	2048
		Ch2StartV,	char *,	Input,	"0,0,0",	,	
		Ch2StopV,	char *,	Input,	"0,0,0",	,	
		Ch2SegTime,	char *,	Input,	"1E-6,1E-6,1E-6",	,	
		Ch2SSRCtrl,	char *,	Input,	"1,1,1",	,	
		Ch2SegTrigOut,	char *,	Input,	"1,0,0",	,	
		Ch2MeasType,	char *,	Input,	"0,0,0",	,	
		Ch2MeasStart,	char *,	Input,	"0,0,0",	,	
		Ch2MeasStop,	char *,	Input,	"0,0,0",	,	
		Ch2LoopCount,	double,	Input,	1.0,	1.0,	100000.0
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
ACraig13_PMU_Waveform_FlexSegArb: PMU waveform capture on CH1 with flexible seg_arb waveform on CH2 (KXCI compatible)

This module combines:
- CH1: Simple pulse parameters converted to seg_arb for continuous waveform measurement
- CH2: Flexible seg_arb waveform with segments designed in Python and passed as arrays

CH1 segments are auto-built from simple pulse parameters (delay, rise, width, fall, period).
CH2 segments are provided as arrays from Python, allowing complete flexibility in waveform design.

MEASUREMENT WINDOW (40-80% of Pulse Width):
===========================================
When acqType=1 (average mode), the module extracts one averaged measurement per pulse
from a specific time window within each pulse. This window is set to 40-80% of the
pulse width, measured from the start of the pulse flat-top (after rise time).

Why 40-80%?
- Avoids transition regions: The first 40% excludes the rise time transition and
  any settling/ringing that may occur at the start of the pulse
- Avoids fall transition: The last 20% (80-100%) excludes the fall time transition
  and any pre-fall settling effects
- Stable region: The 40-80% window captures the most stable, flat portion of the
  pulse where voltage and current have fully settled

CH2 FLEXIBLE SEG_ARB PARAMETERS:
- Ch2NumSegments: Number of segments (3-2048)
- Ch2StartV[]: Array of start voltages for each segment
- Ch2StopV[]: Array of stop voltages for each segment  
- Ch2SegTime[]: Array of segment durations (minimum 20ns per segment)
- Ch2SSRCtrl[]: Array of SSR control (1=closed, 0=open)
- Ch2SegTrigOut[]: Array of trigger outputs (1=trigger, 0=no trigger). First segment MUST have segtrigout=1
- Ch2MeasType[]: Array of measurement types (0=no measure, 2=waveform)
- Ch2MeasStart[]: Array of measurement start times within each segment
- Ch2MeasStop[]: Array of measurement stop times within each segment

CRITICAL REQUIREMENTS:
- Segment voltages must be continuous: stopV[i] == startV[i+1]
- First segment MUST have Ch2SegTrigOut[0] = 1
- All segment times must be >= 20ns (minimum segment time)
- Ch2LoopCount must be >= 1.0

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <math.h>  // For fabs
#include <stdlib.h>  // For calloc, free
#include <string.h>  // For strtok, strtod

BOOL LPTIsInCurrentConfiguration(char* hrid);

// Helper function to parse comma-separated string into array
static int parse_array_string(const char *str, double *array, int max_size)
{
    if (str == NULL || array == NULL || max_size <= 0)
        return 0;
    
    char *str_copy = (char *)calloc(strlen(str) + 1, sizeof(char));
    if (str_copy == NULL)
        return 0;
    
    strcpy(str_copy, str);
    
    int count = 0;
    char *token = strtok(str_copy, ",");
    while (token != NULL && count < max_size)
    {
        array[count] = strtod(token, NULL);
        count++;
        token = strtok(NULL, ",");
    }
    
    free(str_copy);
    return count;
}

// Helper function to parse comma-separated string into long array
static int parse_array_string_long(const char *str, long *array, int max_size)
{
    if (str == NULL || array == NULL || max_size <= 0)
        return 0;
    
    char *str_copy = (char *)calloc(strlen(str) + 1, sizeof(char));
    if (str_copy == NULL)
        return 0;
    
    strcpy(str_copy, str);
    
    int count = 0;
    char *token = strtok(str_copy, ",");
    while (token != NULL && count < max_size)
    {
        array[count] = (long)strtod(token, NULL);
        count++;
        token = strtok(NULL, ",");
    }
    
    free(str_copy);
    return count;
}

/* USRLIB MODULE MAIN FUNCTION */
int ACraig13_PMU_Waveform_FlexSegArb( 
    double width, double rise, double fall, double delay, double period, 
    double voltsSourceRng, double currentMeasureRng, double DUTRes, 
    double startV, double stopV, double stepV, double baseV, 
    int acqType, int LLEComp, double preDataPct, double postDataPct, 
    int pulseAvgCnt, int burstCount, double SampleRate, int PMUMode, 
    int chan, char *PMU_ID, 
    double *V_Meas, int size_V_Meas, 
    double *I_Meas, int size_I_Meas, 
    double *T_Stamp, int size_T_Stamp, 
    int Ch2Enable, double Ch2VRange, int Ch2NumSegments,
    char *Ch2StartV,
    char *Ch2StopV,
    char *Ch2SegTime,
    char *Ch2SSRCtrl,
    char *Ch2SegTrigOut,
    char *Ch2MeasType,
    char *Ch2MeasStart,
    char *Ch2MeasStop,
    double Ch2LoopCount,
    int ClariusDebug )
{
/* USRLIB MODULE CODE */
    int debug = 0;
    double t;
    int status; 
    int pulserId;
    int TestMode;
    double DIFF = 1.0e-9;
    int i, j;
    
    double *waveformV = NULL;
    double *waveformI = NULL;
    double *waveformT = NULL;

    if (ClariusDebug == 1) { debug = 1; } else { debug = 0; }
    if(debug) printf("\n\nACraig13_PMU_Waveform_FlexSegArb: starts\n");

    if ( !LPTIsInCurrentConfiguration(PMU_ID) )
    {
        if(debug) printf("Instrument %s is not in system configuration\n", PMU_ID);
        return -17001;
    }

    getinstid(PMU_ID, &pulserId);
    if ( -1 == pulserId )
    {
        if(debug) printf("Failed to get instrument ID\n");
        return -17002;
    }

    // Support single pulse (when stopV == startV and stepV == 0.0)
    double dSweeps;
    if (fabs(stopV - startV) < DIFF)
    {
        if (stepV == 0.0)
        {
            dSweeps = 1;
        }
        else
        {
            if(debug) printf("Invalid sweep parameters: startV==stopV but stepV!=0\n");
            return -844;
        }
    }
    else
    {
        if (stepV == 0)
        {
            if(debug) printf("Invalid sweep parameters: startV!=stopV but stepV==0\n");
            return -844;
        }
        dSweeps = (fabs((stopV - startV) / stepV) + 0.5) + 1;
        if (dSweeps > 65536)
        {
            if(debug) printf("Too many sweep points: %g\n", dSweeps);
            return -831;
        }
    }

    if(debug) printf("Number of sweep points: %g\n", dSweeps);

    // Ensure that 4225-RPMs (if attached) are in pulse mode for CH1
    status = rpm_config(pulserId, chan, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status && debug )
       printf("rpm_config CH1 returned: %d\n", status);

    // Put card into SARB mode (required for seg_arb functions)
    int pulse_mode = PULSE_MODE_SARB;
    if(debug) 
    {
        printf("========================================\n");
        printf("PMU Initialization:\n");
        printf("  CH1: Using seg_arb (auto-build from simple pulse params)\n");
        printf("  CH2: Using seg_arb (flexible, segments from Python)\n");
        printf("  Selected mode=%d (SARB - REQUIRED for seg_arb)\n", pulse_mode);
        printf("========================================\n");
    }
    
    status = pg2_init(pulserId, pulse_mode);
    if ( status )
    {
        if(debug) 
        {
            printf("ERROR: pg2_init failed!\n");
            printf("  Requested mode=%d (%s)\n", pulse_mode,
                   (pulse_mode == PULSE_MODE_SARB) ? "SARB" : "PULSE");
            printf("  Error code: %d\n", status);
        }
        return status;
    }
    
    if(debug) printf("SUCCESS: pg2_init completed (SARB mode)\n");

    // Set PMU to return actual values when measurement overflow occurs
    status = setmode(pulserId, KI_LIM_MODE, KI_VALUE);
    if ( status )
    {
        if(debug) printf("setmode failed: %d\n", status);
        return status;
    }

    // Validate period meets PMU requirements
    double min_required_period = delay + width + rise + fall;
    double min_off_time = 40e-9;
    double required_period_for_off_time = delay + width + 0.5 * (rise + fall) + min_off_time;
    double pmu_min_period = (voltsSourceRng <= 10.0) ? 120e-9 : 280e-9;
    
    double actual_min_period = (min_required_period > required_period_for_off_time) ? 
                                min_required_period : required_period_for_off_time;
    if (actual_min_period < pmu_min_period)
        actual_min_period = pmu_min_period;
    
    if (period < actual_min_period)
    {
        if(debug) printf("WARNING: period (%.6g) < minimum required (%.6g), adjusting to %.6g...\n", 
                         period, actual_min_period, actual_min_period);
        period = actual_min_period;
    }
    
    double off_time = period - delay - width - 0.5 * (rise + fall);
    if (off_time < min_off_time)
    {
        if(debug) printf("ERROR: Off-time (%.6g) < minimum (40ns) even after adjustment!\n", off_time);
        return -824;
    }
    
    if ( debug )
        printf("CH1: Chan= %d, delay= %g, period= %g (final), PW= %g, Rise= %g, Fall= %g\n", 
               chan, delay, period, width, rise, fall);

    // ============================================================
    // CH1 Setup for seg_arb waveform (with measurement)
    // ============================================================
    
    if(debug) 
    {
        printf("========================================\n");
        printf("CH1 seg_arb Configuration (auto-build from simple pulse params):\n");
        printf("  BaseV=%.6g V, StartV=%.6g V, StopV=%.6g V, StepV=%.6g V\n", baseV, startV, stopV, stepV);
        printf("  Width=%.6g s, Rise=%.6g s, Fall=%.6g s, Delay=%.6g s\n", width, rise, fall, delay);
        printf("  Period=%.6g s, BurstCount=%d\n", period, burstCount);
        printf("========================================\n");
    }
    
    // Set sample rate (applies to both channels)
    status = pulse_sample_rate(pulserId, SampleRate);
    if ( status )
    {
        if(debug) printf("pulse_sample_rate failed: %d\n", status);
        return status;
    }
    
    // Set load for CH1
    if (!LLEComp || !PMUMode)
    {
        status = pulse_load(pulserId, chan, DUTRes);
        if ( status )
        {
            if(debug) printf("pulse_load CH1 failed: %d\n", status);
            return status;
        }
    }
    
    // Set ranges for CH1
    status = pulse_ranges(pulserId, chan, voltsSourceRng, PULSE_MEAS_FIXED, voltsSourceRng, PULSE_MEAS_FIXED, currentMeasureRng);
    if ( status )
    {
        if(debug) printf("pulse_ranges CH1 failed: %d\n", status);
        return status;
    }
    
    // Set burst count for CH1 (required before seg_arb)
    status = pulse_burst_count(pulserId, chan, 1);
    if ( status )
    {
        if(debug) printf("pulse_burst_count CH1 failed: %d\n", status);
        return status;
    }
    
    // Enable CH1 output (required before seg_arb)
    status = pulse_output(pulserId, chan, 1);
    if ( status )
    {
        if(debug) printf("pulse_output CH1 failed: %d\n", status);
        return status;
    }
    
    // Minimum segment time for seg_arb (20ns minimum)
    double min_seg_time = 20e-9;
    
    // Calculate post-delay to complete the period
    double ch1_pulse_time = delay + rise + width + fall;
    double ch1_post_delay = period - ch1_pulse_time;
    if (ch1_post_delay < 0)
    {
        if(debug) printf("ERROR: CH1 period (%.6g) < pulse time (%.6g)\n", period, ch1_pulse_time);
        return -122;
    }
    
    // Validate all segment times meet minimum requirements
    if (delay < 0 || (delay > 0 && delay < min_seg_time))
    {
        if(debug) printf("WARNING: CH1 delay (%.6g) < minimum (%.6g), adjusting to %.6g\n", delay, min_seg_time, min_seg_time);
        delay = (delay < 0) ? 0.0 : min_seg_time;
    }
    if (rise < min_seg_time)
    {
        if(debug) printf("ERROR: CH1 rise (%.6g) < minimum (%.6g)\n", rise, min_seg_time);
        return -122;
    }
    if (width < min_seg_time)
    {
        if(debug) printf("ERROR: CH1 width (%.6g) < minimum (%.6g)\n", width, min_seg_time);
        return -122;
    }
    if (fall < min_seg_time)
    {
        if(debug) printf("ERROR: CH1 fall (%.6g) < minimum (%.6g)\n", fall, min_seg_time);
        return -122;
    }
    if (ch1_post_delay > 0 && ch1_post_delay < min_seg_time)
    {
        if(debug) printf("WARNING: CH1 post_delay (%.6g) < minimum (%.6g), adjusting to %.6g\n", ch1_post_delay, min_seg_time, min_seg_time);
        ch1_post_delay = min_seg_time;
        period = ch1_pulse_time + ch1_post_delay;
    }
    
    // Build CH1 segments: preDelay (delay) + rise + width + fall + postDelay + final 0V segment
    int ch1_num_segments = 6;
    double *ch1_startv = (double *)calloc(ch1_num_segments, sizeof(double));
    double *ch1_stopv = (double *)calloc(ch1_num_segments, sizeof(double));
    double *ch1_segtime = (double *)calloc(ch1_num_segments, sizeof(double));
    long *ch1_ssrctrl = (long *)calloc(ch1_num_segments, sizeof(long));
    long *ch1_segtrigout = (long *)calloc(ch1_num_segments, sizeof(long));
    long *ch1_meastype = (long *)calloc(ch1_num_segments, sizeof(long));
    double *ch1_measstart = (double *)calloc(ch1_num_segments, sizeof(double));
    double *ch1_measstop = (double *)calloc(ch1_num_segments, sizeof(double));
    
    if (!ch1_startv || !ch1_stopv || !ch1_segtime || !ch1_ssrctrl || 
        !ch1_segtrigout || !ch1_meastype || !ch1_measstart || !ch1_measstop)
    {
        if(debug) printf("ERROR: Failed to allocate memory for CH1 segments\n");
        if (ch1_startv) free(ch1_startv);
        if (ch1_stopv) free(ch1_stopv);
        if (ch1_segtime) free(ch1_segtime);
        if (ch1_ssrctrl) free(ch1_ssrctrl);
        if (ch1_segtrigout) free(ch1_segtrigout);
        if (ch1_meastype) free(ch1_meastype);
        if (ch1_measstart) free(ch1_measstart);
        if (ch1_measstop) free(ch1_measstop);
        return -999;
    }
    
    // Build CH1 segments
    int idx = 0;
    
    // Segment 0: Pre-delay (at baseV) - no measurement
    double seg0_time = (delay > 0) ? delay : min_seg_time;
    ch1_startv[idx] = baseV; ch1_stopv[idx] = baseV; ch1_segtime[idx] = seg0_time;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 1;  // First segment triggers
    ch1_meastype[idx] = 0; ch1_measstart[idx] = 0.0; ch1_measstop[idx] = 0.0;
    idx++;
    
    // Segment 1: Rise (baseV -> startV) - measure full segment
    ch1_startv[idx] = baseV; ch1_stopv[idx] = startV; ch1_segtime[idx] = rise;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = 2;  // Waveform measurement
    ch1_measstart[idx] = 0.0;
    ch1_measstop[idx] = rise;
    idx++;
    
    // Segment 2: Width (at startV) - measure full segment
    ch1_startv[idx] = startV; ch1_stopv[idx] = startV; ch1_segtime[idx] = width;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = 2;  // Waveform measurement
    ch1_measstart[idx] = 0.0;
    ch1_measstop[idx] = width;
    idx++;
    
    // Segment 3: Fall (startV -> baseV) - measure full segment
    ch1_startv[idx] = startV; ch1_stopv[idx] = baseV; ch1_segtime[idx] = fall;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = 2;  // Waveform measurement
    ch1_measstart[idx] = 0.0;
    ch1_measstop[idx] = fall;
    idx++;
    
    // Segment 4: Post-delay (at baseV)
    double seg4_time = (ch1_post_delay > 0) ? ch1_post_delay : min_seg_time;
    ch1_startv[idx] = baseV; ch1_stopv[idx] = baseV; ch1_segtime[idx] = seg4_time;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = 0; ch1_measstart[idx] = 0.0; ch1_measstop[idx] = 0.0;
    idx++;
    
    // Segment 5: Final segment - ensure we end at 0V with relays closed
    ch1_startv[idx] = baseV; ch1_stopv[idx] = 0.0; ch1_segtime[idx] = min_seg_time;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = 0; ch1_measstart[idx] = 0.0; ch1_measstop[idx] = 0.0;
    
    // Configure seg_arb sequence for CH1
    if(debug) printf("Configuring seg_arb_sequence for CH%d (%d segments)...\n", chan, ch1_num_segments);
    
    status = seg_arb_sequence(pulserId, chan, 1, ch1_num_segments,
                              ch1_startv, ch1_stopv, ch1_segtime,
                              ch1_segtrigout, ch1_ssrctrl,
                              ch1_meastype, ch1_measstart, ch1_measstop);
    if ( status )
    {
        if(debug) printf("ERROR: seg_arb_sequence CH1 failed: %d\n", status);
        free(ch1_startv); free(ch1_stopv); free(ch1_segtime);
        free(ch1_ssrctrl); free(ch1_segtrigout); free(ch1_meastype);
        free(ch1_measstart); free(ch1_measstop);
        return status;
    }
    
    // Configure seg_arb waveform for CH1 (loop count = burstCount)
    long ch1_seqList[1] = {1};
    double ch1_loopCount[1] = {(double)burstCount};
    
    status = seg_arb_waveform(pulserId, chan, 1, ch1_seqList, ch1_loopCount);
    if ( status )
    {
        if(debug) printf("ERROR: seg_arb_waveform CH1 failed: %d\n", status);
        free(ch1_startv); free(ch1_stopv); free(ch1_segtime);
        free(ch1_ssrctrl); free(ch1_segtrigout); free(ch1_meastype);
        free(ch1_measstart); free(ch1_measstop);
        return status;
    }
    
    // Free CH1 segment arrays
    free(ch1_startv); free(ch1_stopv); free(ch1_segtime);
    free(ch1_ssrctrl); free(ch1_segtrigout); free(ch1_meastype);
    free(ch1_measstart); free(ch1_measstop);
    
    if(debug) printf("Configured CH1 for %d pulses with waveform capture\n", burstCount);

    // ============================================================
    // CH2 Setup for flexible seg_arb waveform (segments from Python)
    // ============================================================
    if (Ch2Enable)
    {
        int ch2 = (chan == 1) ? 2 : 1;
        
        if(debug) 
        {
            printf("========================================\n");
            printf("CH2 Flexible seg_arb Configuration:\n");
            printf("  Ch2NumSegments: %d\n", Ch2NumSegments);
            printf("  Ch2VRange: %.6g V\n", Ch2VRange);
            printf("  Ch2LoopCount: %.6g\n", Ch2LoopCount);
            printf("========================================\n");
        }
        
        // Validate CH2 segment count
        if (Ch2NumSegments < 3 || Ch2NumSegments > 2048)
        {
            if(debug) printf("ERROR: Ch2NumSegments (%d) must be between 3 and 2048\n", Ch2NumSegments);
            return -122;
        }
        
        // Validate segment strings are not NULL
        if (Ch2StartV == NULL || Ch2StopV == NULL || Ch2SegTime == NULL ||
            Ch2SSRCtrl == NULL || Ch2SegTrigOut == NULL || Ch2MeasType == NULL ||
            Ch2MeasStart == NULL || Ch2MeasStop == NULL)
        {
            if(debug) printf("ERROR: CH2 segment strings are NULL\n");
            return -122;
        }
        
        // Parse segment strings into arrays
        double *ch2_startv = (double *)calloc(Ch2NumSegments, sizeof(double));
        double *ch2_stopv = (double *)calloc(Ch2NumSegments, sizeof(double));
        double *ch2_segtime = (double *)calloc(Ch2NumSegments, sizeof(double));
        long *ch2_ssrctrl = (long *)calloc(Ch2NumSegments, sizeof(long));
        long *ch2_segtrigout = (long *)calloc(Ch2NumSegments, sizeof(long));
        long *ch2_meastype = (long *)calloc(Ch2NumSegments, sizeof(long));
        double *ch2_measstart = (double *)calloc(Ch2NumSegments, sizeof(double));
        double *ch2_measstop = (double *)calloc(Ch2NumSegments, sizeof(double));
        
        if (!ch2_startv || !ch2_stopv || !ch2_segtime || !ch2_ssrctrl ||
            !ch2_segtrigout || !ch2_meastype || !ch2_measstart || !ch2_measstop)
        {
            if(debug) printf("ERROR: Failed to allocate memory for CH2 segment arrays\n");
            if (ch2_startv) free(ch2_startv);
            if (ch2_stopv) free(ch2_stopv);
            if (ch2_segtime) free(ch2_segtime);
            if (ch2_ssrctrl) free(ch2_ssrctrl);
            if (ch2_segtrigout) free(ch2_segtrigout);
            if (ch2_meastype) free(ch2_meastype);
            if (ch2_measstart) free(ch2_measstart);
            if (ch2_measstop) free(ch2_measstop);
            return -999;
        }
        
        // Parse strings
        int parsed_startv = parse_array_string(Ch2StartV, ch2_startv, Ch2NumSegments);
        int parsed_stopv = parse_array_string(Ch2StopV, ch2_stopv, Ch2NumSegments);
        int parsed_segtime = parse_array_string(Ch2SegTime, ch2_segtime, Ch2NumSegments);
        int parsed_ssrctrl = parse_array_string_long(Ch2SSRCtrl, ch2_ssrctrl, Ch2NumSegments);
        int parsed_segtrigout = parse_array_string_long(Ch2SegTrigOut, ch2_segtrigout, Ch2NumSegments);
        int parsed_meastype = parse_array_string_long(Ch2MeasType, ch2_meastype, Ch2NumSegments);
        int parsed_measstart = parse_array_string(Ch2MeasStart, ch2_measstart, Ch2NumSegments);
        int parsed_measstop = parse_array_string(Ch2MeasStop, ch2_measstop, Ch2NumSegments);
        
        if (parsed_startv != Ch2NumSegments || parsed_stopv != Ch2NumSegments ||
            parsed_segtime != Ch2NumSegments || parsed_ssrctrl != Ch2NumSegments ||
            parsed_segtrigout != Ch2NumSegments || parsed_meastype != Ch2NumSegments ||
            parsed_measstart != Ch2NumSegments || parsed_measstop != Ch2NumSegments)
        {
            if(debug) printf("ERROR: Failed to parse CH2 segment strings (expected %d values)\n", Ch2NumSegments);
            free(ch2_startv); free(ch2_stopv); free(ch2_segtime);
            free(ch2_ssrctrl); free(ch2_segtrigout); free(ch2_meastype);
            free(ch2_measstart); free(ch2_measstop);
            return -122;
        }
        
        // Validate segment times meet minimum (20ns)
        for (i = 0; i < Ch2NumSegments; i++)
        {
            if (ch2_segtime[i] < min_seg_time)
            {
                if(debug) printf("ERROR: CH2 segment %d time (%.6g) < minimum (%.6g)\n", i, ch2_segtime[i], min_seg_time);
                free(ch2_startv); free(ch2_stopv); free(ch2_segtime);
                free(ch2_ssrctrl); free(ch2_segtrigout); free(ch2_meastype);
                free(ch2_measstart); free(ch2_measstop);
                return -122;
            }
        }
        
        // Validate first segment has trigger
        if (ch2_segtrigout[0] != 1)
        {
            if(debug) printf("WARNING: CH2 first segment does not have segtrigout=1, fixing...\n");
            ch2_segtrigout[0] = 1;
        }
        
        // Validate loop count
        if (Ch2LoopCount <= 0 || Ch2LoopCount < 1.0)
        {
            if(debug) printf("ERROR: Ch2LoopCount (%.6g) must be >= 1.0\n", Ch2LoopCount);
            return -122;
        }
        
        // Ensure RPM in pulse mode for CH2
        status = rpm_config(pulserId, ch2, KI_RPM_PATHWAY, KI_RPM_PULSE);
        if ( status && debug )
           printf("rpm_config CH2 returned: %d\n", status);
        
        // Set load for CH2
        status = pulse_load(pulserId, ch2, 1e6);
        if ( status )
        {
            if(debug) printf("pulse_load CH2 failed: %d\n", status);
            return status;
        }
        
        // Set ranges for CH2
        status = pulse_ranges(pulserId, ch2, Ch2VRange, PULSE_MEAS_FIXED, Ch2VRange, PULSE_MEAS_FIXED, 0.01);
        if ( status )
        {
            if(debug) printf("pulse_ranges CH2 failed: %d\n", status);
            return status;
        }
        
        // Set burst count for CH2
        status = pulse_burst_count(pulserId, ch2, 1);
        if ( status )
        {
            if(debug) printf("pulse_burst_count CH2 failed: %d\n", status);
            return status;
        }
        
        // Enable CH2 output
        status = pulse_output(pulserId, ch2, 1);
        if ( status )
        {
            if(debug) printf("pulse_output CH2 failed: %d\n", status);
            return status;
        }
        
        // Configure seg_arb sequence for CH2
        if(debug) 
        {
            printf("Configuring seg_arb_sequence for CH%d (%d segments)...\n", ch2, Ch2NumSegments);
            printf("  First segment: %.6g V -> %.6g V, time=%.6g s\n", 
                   ch2_startv[0], ch2_stopv[0], ch2_segtime[0]);
        }
        
        status = seg_arb_sequence(pulserId, ch2, 1, Ch2NumSegments,
                                  ch2_startv, ch2_stopv, ch2_segtime,
                                  ch2_segtrigout, ch2_ssrctrl,
                                  ch2_meastype, ch2_measstart, ch2_measstop);
        if ( status )
        {
            if(debug) 
            {
                printf("ERROR: seg_arb_sequence CH2 failed: %d\n", status);
                if (status == -804)
                    printf("  Error -804: seg_arb function not valid in present pulse mode\n");
            }
            return status;
        }
        
        // Configure seg_arb waveform for CH2
        long seqList[1] = {1};
        double loopCount[1] = {Ch2LoopCount};
        
        if(debug) 
        {
            printf("Configuring seg_arb_waveform for CH%d (loop count=%.6g)...\n", ch2, Ch2LoopCount);
        }
        
        status = seg_arb_waveform(pulserId, ch2, 1, seqList, loopCount);
        if ( status )
        {
            if(debug) printf("ERROR: seg_arb_waveform CH2 failed: %d\n", status);
            return status;
        }
        
        if(debug) printf("CH2 seg_arb configured: %d segments, loop count=%.6g\n", Ch2NumSegments, Ch2LoopCount);
        
        // Free parsed arrays
        free(ch2_startv);
        free(ch2_stopv);
        free(ch2_segtime);
        free(ch2_ssrctrl);
        free(ch2_segtrigout);
        free(ch2_meastype);
        free(ch2_measstart);
        free(ch2_measstop);
    }

    // Set test execute mode
    if (PMUMode == 0)
        TestMode = PULSE_MODE_SIMPLE;
    else
        TestMode = PULSE_MODE_ADVANCED;

    if(debug) printf("Executing pulses (CH1 + CH2)...\n");
    
    // Execute both channels together
    status = pulse_exec(TestMode);
    if (status)
    {
        if(debug) printf("pulse_exec failed: %d\n", status);
        return status;
    }

    // Wait until test is complete
    i = 0;
    while ( pulse_exec_status(&t) == 1 && i < 200 )
    {
        Sleep(100);
        i++;
    }
    
    if (i >= 200)
    {
        if(debug) printf("ERROR: Pulse execution timed out after 20 seconds\n");
        return -998;
    }
    
    if(debug) printf("Pulse execution complete after %d waits (%.1f seconds)\n", i, i * 0.1);

    Sleep(50);  // Small delay to ensure data is ready
    
    // Turn off CH2 if it was enabled
    if (Ch2Enable)
    {
        int ch2 = (chan == 1) ? 2 : 1;
        status = pulse_output(pulserId, ch2, 0);
        if(debug) printf("CH2 output disabled\n");
    }
    
    // ============================================================
    // Fetch waveform and extract averaged values per pulse
    // ============================================================
    
    // Calculate expected number of samples
    double total_measurement_time = period * burstCount;
    int expectedSamples = (int)(total_measurement_time * SampleRate + 1);
    
    int maxSamples = expectedSamples;
    if (maxSamples < 100) maxSamples = 100;
    if (maxSamples > 100000) maxSamples = 100000;
    
    waveformV = (double *)calloc(maxSamples, sizeof(double));
    waveformI = (double *)calloc(maxSamples, sizeof(double));
    waveformT = (double *)calloc(maxSamples, sizeof(double));
    
    if (waveformV == NULL || waveformI == NULL || waveformT == NULL)
    {
        if(debug) printf("Failed to allocate memory for waveform buffers\n");
        if (waveformV) free(waveformV);
        if (waveformI) free(waveformI);
        if (waveformT) free(waveformT);
        return -999;
    }
    
    if(debug) 
    {
        printf("Fetching waveform:\n");
        printf("  Total measurement time: %.6g s\n", total_measurement_time);
        printf("  Expected samples: %d\n", expectedSamples);
        printf("  Buffer size: %d\n", maxSamples);
    }
    
    // Fetch waveform data
    status = pulse_fetch(pulserId, chan, 0, maxSamples-1, waveformV, waveformI, waveformT, NULL);
    if (status)
    {
        if(debug) printf("pulse_fetch failed with error: %d\n", status);
        free(waveformV);
        free(waveformI);
        free(waveformT);
        return status;
    }
    
    // Find actual number of samples
    int numWaveformSamples = 0;
    for (i = 0; i < maxSamples; i++)
    {
        if (waveformT[i] == 0.0 && i > 0) break;
        numWaveformSamples++;
    }
    
    if(debug) printf("Fetched %d waveform samples, extracting averaged values per pulse...\n", numWaveformSamples);
    
    // Extract one averaged value per pulse (from 40-80% of pulse width)
    int outputIdx = 0;
    double measurementStartFrac = 0.4;
    double measurementEndFrac = 0.8;
    double voltageThreshold = fabs(startV) * 0.5;
    
    int pulseStartIdx = -1;
    int pulseEndIdx = -1;
    int pulseNum = 0;
    
    for (i = 0; i < numWaveformSamples && pulseNum < burstCount && outputIdx < size_V_Meas; i++)
    {
        // Detect pulse start
        if (pulseStartIdx < 0 && fabs(waveformV[i]) > voltageThreshold)
        {
            pulseStartIdx = i;
        }
        
        // Detect pulse end
        if (pulseStartIdx >= 0 && fabs(waveformV[i]) < voltageThreshold)
        {
            pulseEndIdx = i;
            
            int pulseWidthSamples = pulseEndIdx - pulseStartIdx;
            int measStartSample = pulseStartIdx + (int)(pulseWidthSamples * measurementStartFrac);
            int measEndSample = pulseStartIdx + (int)(pulseWidthSamples * measurementEndFrac);
            
            if (measEndSample > pulseEndIdx) measEndSample = pulseEndIdx;
            if (measStartSample < pulseStartIdx) measStartSample = pulseStartIdx;
            
            // Average samples in measurement window
            double sumV = 0.0, sumI = 0.0, sumT = 0.0;
            int count = 0;
            
            for (j = measStartSample; j <= measEndSample && j < numWaveformSamples; j++)
            {
                sumV += waveformV[j];
                sumI += waveformI[j];
                sumT += waveformT[j];
                count++;
            }
            
            if (count > 0)
            {
                V_Meas[outputIdx] = sumV / count;
                I_Meas[outputIdx] = sumI / count;
                T_Stamp[outputIdx] = sumT / count;
                outputIdx++;
            }
            
            pulseNum++;
            pulseStartIdx = -1;
            pulseEndIdx = -1;
        }
    }
    
    if(debug) printf("Threshold-based detection found %d pulses (expected %d)\n", outputIdx, burstCount);
    
    // If we didn't find enough pulses, try alternative: assume evenly spaced pulses
    if (outputIdx < burstCount && numWaveformSamples > 0)
    {
        if(debug) printf("Only found %d pulses via threshold detection, trying evenly-spaced detection...\n", outputIdx);
        
        // Reset output
        for (i = 0; i < outputIdx; i++)
        {
            V_Meas[i] = 0.0;
            I_Meas[i] = 0.0;
            T_Stamp[i] = 0.0;
        }
        outputIdx = 0;
        
        // Use time-based detection assuming pulses are evenly spaced
        double totalTime = waveformT[numWaveformSamples-1] - waveformT[0];
        double estimatedPeriod = totalTime / burstCount;
        
        if(debug) printf("Estimated period: %.6g s (total time: %.6g s)\n", estimatedPeriod, totalTime);
        
        for (int pulseIdx = 0; pulseIdx < burstCount && outputIdx < size_V_Meas; pulseIdx++)
        {
            double pulseStartTime = waveformT[0] + pulseIdx * estimatedPeriod;
            double measStartTime = pulseStartTime + delay + rise + width * measurementStartFrac;
            double measEndTime = pulseStartTime + delay + rise + width * measurementEndFrac;
            
            double sumV = 0.0, sumI = 0.0, sumT = 0.0;
            int count = 0;
            
            for (i = 0; i < numWaveformSamples; i++)
            {
                if (waveformT[i] >= measStartTime && waveformT[i] <= measEndTime)
                {
                    sumV += waveformV[i];
                    sumI += waveformI[i];
                    sumT += waveformT[i];
                    count++;
                }
            }
            
            if (count > 0)
            {
                V_Meas[outputIdx] = sumV / count;
                I_Meas[outputIdx] = sumI / count;
                T_Stamp[outputIdx] = sumT / count;
                outputIdx++;
            }
        }
    }
    
    // Zero out remaining array elements
    for (i = outputIdx; i < size_V_Meas && i < size_I_Meas && i < size_T_Stamp; i++)
    {
        V_Meas[i] = 0.0;
        I_Meas[i] = 0.0;
        T_Stamp[i] = 0.0;
    }
    
    free(waveformV);
    free(waveformI);
    free(waveformT);
    
    if(debug) 
    {
        printf("Extracted %d averaged measurements (one per pulse from 40-80%% window).\n", outputIdx);
        printf("ACraig13_PMU_Waveform_FlexSegArb: complete, returning to KXCI\n");
    }

    return 0;
/* USRLIB MODULE END  */
} 		/* End ACraig13_PMU_Waveform_FlexSegArb.c */

