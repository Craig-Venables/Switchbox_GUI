/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig10_PMU_Waveform_SegArb
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 55
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
		Ch2Vlow,	double,	Input,	0.0,	-40,	40
		Ch2Vhigh,	double,	Input,	1.0,	-40,	40
		Ch2Width,	double,	Input,	1e-6,	40e-9,	.999999
		Ch2Rise,	double,	Input,	100e-9,	20e-9,	.033
		Ch2Fall,	double,	Input,	100e-9,	20e-9,	.033
		Ch2Period,	double,	Input,	10e-6,	100e-9,	1
		Ch2NumSegments,	int,	Input,	0,	0,	2048
		Ch2StartV,	D_ARRAY_T,	Input,	,	,	
		Ch2StartV_size,	int,	Input,	10,	3,	2048
		Ch2StopV,	D_ARRAY_T,	Input,	,	,	
		Ch2StopV_size,	int,	Input,	10,	3,	2048
		Ch2SegTime,	D_ARRAY_T,	Input,	,	,	
		Ch2SegTime_size,	int,	Input,	10,	3,	2048
		Ch2SSRCtrl,	I_ARRAY_T,	Input,	,	,	
		Ch2SSRCtrl_size,	int,	Input,	10,	3,	2048
		Ch2SegTrigOut,	I_ARRAY_T,	Input,	,	,	
		Ch2SegTrigOut_size,	int,	Input,	10,	3,	2048
		Ch2MeasType,	I_ARRAY_T,	Input,	,	,	
		Ch2MeasType_size,	int,	Input,	10,	3,	2048
		Ch2MeasStart,	D_ARRAY_T,	Input,	,	,	
		Ch2MeasStart_size,	int,	Input,	10,	3,	2048
		Ch2MeasStop,	D_ARRAY_T,	Input,	,	,	
		Ch2MeasStop_size,	int,	Input,	10,	3,	2048
		Ch2LoopCount,	double,	Input,	1.0,	1.0,	100000.0
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
ACraig10_PMU_Waveform_SegArb: PMU waveform capture on CH1 with seg_arb waveform on CH2 (KXCI compatible)

This module combines:
- CH1: Simple pulse commands for continuous waveform measurement (voltage/current vs time)
- CH2: Segmented arbitrary (seg_arb) waveform for complex pulse sequences

Uses pulse_fetch() instead of pulse_measrt() for KXCI compatibility.

CH1: Measures DUT voltage and current with waveform capture using simple pulse commands
CH2: Optional seg_arb waveform (no measurement) for complex pulse sequences

KEY DIFFERENCES FROM ACraig9:
- CH2 uses seg_arb_sequence/seg_arb_waveform instead of simple pulse commands
- CH2 can have up to 2048 segments for complex waveforms
- CH2 timing is defined by segment times, not period/delay/width
- Both channels execute together via pulse_exec() but operate independently

CH2 SEG_ARB PARAMETERS (TWO MODES):

MODE 1: Simple Pulse Parameters (Auto-build segments)
- Ch2Vlow, Ch2Vhigh: Pulse voltage levels
- Ch2Width: Pulse width
- Ch2Rise, Ch2Fall: Rise and fall times
- Ch2Period: Period between pulses (independent of CH1!)
- Ch2NumSegments: Set to 0 to use auto-build mode
- Ch2LoopCount: Number of times to repeat (auto-calculated to match CH1 duration)

MODE 2: Manual Segments (Advanced)
- Ch2NumSegments: Number of segments (3-2048)
- Ch2StartV[]: Array of start voltages for each segment
- Ch2StopV[]: Array of stop voltages for each segment  
- Ch2SegTime[]: Array of segment durations
- Ch2SSRCtrl[]: Array of SSR control (1=closed, 0=open)
- Ch2SegTrigOut[]: Array of trigger outputs (1=trigger, 0=no trigger)
- Ch2MeasType[]: Array of measurement types (0=no measure, 3=waveform)
- Ch2MeasStart[]: Array of measurement start times within each segment
- Ch2MeasStop[]: Array of measurement stop times within each segment

NOTE: CH2 should be enabled (Ch2Enable=1) even if not using it - disabling CH2 may cause pulse_exec to fail.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"

/* USRLIB MODULE MAIN FUNCTION */
int ACraig10_PMU_Waveform_SegArb( double width, double rise, double fall, double delay, double period, double voltsSourceRng, double currentMeasureRng, double DUTRes, double startV, double stopV, double stepV, double baseV, int acqType, int LLEComp, double preDataPct, double postDataPct, int pulseAvgCnt, int burstCount, double SampleRate, int PMUMode, int chan, char *PMU_ID, double *V_Meas, int size_V_Meas, double *I_Meas, int size_I_Meas, double *T_Stamp, int size_T_Stamp, int Ch2Enable, double Ch2VRange, double Ch2Vlow, double Ch2Vhigh, double Ch2Width, double Ch2Rise, double Ch2Fall, double Ch2Period, int Ch2NumSegments, double *Ch2StartV, int Ch2StartV_size, double *Ch2StopV, int Ch2StopV_size, double *Ch2SegTime, int Ch2SegTime_size, int *Ch2SSRCtrl, int Ch2SSRCtrl_size, int *Ch2SegTrigOut, int Ch2SegTrigOut_size, int *Ch2MeasType, int Ch2MeasType_size, double *Ch2MeasStart, int Ch2MeasStart_size, double *Ch2MeasStop, int Ch2MeasStop_size, double Ch2LoopCount, int ClariusDebug )
{
/* USRLIB MODULE CODE */
    int debug = 0;
    double t;
    int status; 
    int pulserId;
    int TestMode;
    int sweepType = PULSE_AMPLITUDE_SP;
    double dSweeps;
    double pointsPerWfm;
    double DIFF = 1.0e-9;
    int i, j;
    
    double *waveformV = NULL;
    double *waveformI = NULL;
    double *waveformT = NULL;

    if (ClariusDebug == 1) { debug = 1; } else { debug = 0; }
    if(debug) printf("\n\nACraig10_PMU_Waveform_SegArb: starts\n");

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
        pointsPerWfm = period * SampleRate + 1;
        if (pointsPerWfm*dSweeps > 65536)
        {
            if(debug) printf("Total samples exceed maximum\n");
            return -831;
        }
    }

    if(debug) printf("Number of sweep points: %g\n", dSweeps);

    // Ensure that 4225-RPMs (if attached) are in pulse mode for CH1
    status = rpm_config(pulserId, chan, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if ( status && debug )
       printf("rpm_config CH1 returned: %d\n", status);

    // Put card into pulse mode
    // NOTE: Both CH1 and CH2 now use seg_arb, so we MUST use PULSE_MODE_SARB
    // seg_arb functions are only valid in SARB mode
    // ALWAYS use SARB mode (both channels use seg_arb)
    int pulse_mode = PULSE_MODE_SARB;
    if(debug) 
    {
        printf("========================================\n");
        printf("PMU Initialization:\n");
        printf("  CH1: Using seg_arb (auto-build from simple pulse params)\n");
        printf("  CH2: Using seg_arb (Ch2Enable=%d, Ch2NumSegments=%d)\n", Ch2Enable, Ch2NumSegments);
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
    
    if(debug) 
    {
        printf("SUCCESS: pg2_init completed\n");
        printf("  Mode set to: %d (SARB - seg_arb ready for both channels)\n", pulse_mode);
    }

    // Set PMU to return actual values when measurement overflow occurs
    status = setmode(pulserId, KI_LIM_MODE, KI_VALUE);
    if ( status )
    {
        if(debug) printf("setmode failed: %d\n", status);
        return status;
    }

    // Set PMU source and measure ranges for CH1
    status = pulse_ranges(pulserId, chan, voltsSourceRng, PULSE_MEAS_FIXED, voltsSourceRng, PULSE_MEAS_FIXED, currentMeasureRng);
    if ( status )
    {
        if(debug) printf("pulse_ranges CH1 failed: %d\n", status);
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
    
    if(debug) 
    {
        printf("Period validation:\n");
        printf("  Requested period: %.6g s\n", period);
        printf("  Actual minimum required: %.6g s\n", actual_min_period);
    }
    
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
    // Convert simple pulse parameters to seg_arb segments
    // Build segments: preDelay + rise + width + fall + postDelay
    
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
    double min_seg_time = 20e-9;  // 20ns minimum segment time
    
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
        // Recalculate period to accommodate minimum post_delay
        period = ch1_pulse_time + ch1_post_delay;
    }
    
    // Build CH1 segments: preDelay (delay) + rise + width + fall + postDelay + final 0V segment
    // Need 6 segments to ensure we end at 0V with relays closed
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
    // For seg_arb waveform measurement, use appropriate PULSE_MEAS_* constants
    // Following working example: measstart=0, measstop=segtime for each segment
    int idx = 0;
    // Determine measurement type based on acqType:
    // - acqType == 1: PULSE_MEAS_WFM_BURST (Waveform per Burst - averages all repeated waveforms together)
    // - acqType == 0: PULSE_MEAS_WFM_PER (Waveform per Period - discrete waveforms, one per period)
    // NOTE: Both are WAVEFORM measurements (full sampled data), NOT spot mean (single value per segment)
    // For spot mean, we would use PULSE_MEAS_SMEAN_BURST or PULSE_MEAS_SMEAN_PER instead
    long waveform_meas_type = (acqType == 1) ? PULSE_MEAS_WFM_BURST : PULSE_MEAS_WFM_PER; 
    
    // Segment 0: Pre-delay (at baseV) - no measurement
    // If delay is 0, use minimum segment time to avoid invalid parameter
    double seg0_time = (delay > 0) ? delay : min_seg_time;
    ch1_startv[idx] = baseV; ch1_stopv[idx] = baseV; ch1_segtime[idx] = seg0_time;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 1;  // First segment triggers
    ch1_meastype[idx] = PULSE_MEAS_NONE; ch1_measstart[idx] = 0.0; ch1_measstop[idx] = 0.0;  // No measurement
    idx++;
    
    // Segment 1: Rise (baseV -> startV) - measure full segment
    ch1_startv[idx] = baseV; ch1_stopv[idx] = startV; ch1_segtime[idx] = rise;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = waveform_meas_type;
    ch1_measstart[idx] = 0.0;  // Start of segment
    ch1_measstop[idx] = rise;  // End of segment (full duration)
    idx++;
    
    // Segment 2: Width (at startV) - measure full segment (this is where 40-80% window will be extracted)
    ch1_startv[idx] = startV; ch1_stopv[idx] = startV; ch1_segtime[idx] = width;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = waveform_meas_type;
    ch1_measstart[idx] = 0.0;  // Start of segment
    ch1_measstop[idx] = width;  // End of segment (full duration)
    idx++;
    
    // Segment 3: Fall (startV -> baseV) - measure full segment
    ch1_startv[idx] = startV; ch1_stopv[idx] = baseV; ch1_segtime[idx] = fall;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = waveform_meas_type;
    ch1_measstart[idx] = 0.0;  // Start of segment
    ch1_measstop[idx] = fall;  // End of segment (full duration)
    idx++;
    
    // Segment 4: Post-delay (at baseV)
    // Ensure post_delay is at least minimum segment time (or 0 if period exactly matches pulse time)
    double seg4_time = (ch1_post_delay > 0) ? ch1_post_delay : min_seg_time;
    ch1_startv[idx] = baseV; ch1_stopv[idx] = baseV; ch1_segtime[idx] = seg4_time;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;  // Relays closed
    ch1_meastype[idx] = PULSE_MEAS_NONE; ch1_measstart[idx] = 0.0; ch1_measstop[idx] = 0.0;
    idx++;
    
    // Segment 5: Final segment - ensure we end at 0V with relays closed
    ch1_startv[idx] = baseV; ch1_stopv[idx] = 0.0; ch1_segtime[idx] = min_seg_time;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;  // Relays closed
    ch1_meastype[idx] = PULSE_MEAS_NONE; ch1_measstart[idx] = 0.0; ch1_measstop[idx] = 0.0;
    
    if(debug) 
    {
        printf("Built %d segments for CH1:\n", ch1_num_segments);
        printf("  Validating segment times (min=%.6g s):\n", min_seg_time);
        for (i = 0; i < ch1_num_segments; i++)
        {
            printf("  Seg %d: %.6g V -> %.6g V, time=%.6g s", 
                   i, ch1_startv[i], ch1_stopv[i], ch1_segtime[i]);
            if (ch1_segtime[i] < min_seg_time)
                printf(" [ERROR: < min!]");
            else if (ch1_segtime[i] == 0)
                printf(" [ERROR: zero!]");
            else
                printf(" [OK]");
            printf(", meas=%ld (%.6g-%.6g)\n", 
                   ch1_meastype[i], ch1_measstart[i], ch1_measstop[i]);
        }
    }
    
    // Final validation: ensure all segment times are valid
    for (i = 0; i < ch1_num_segments; i++)
    {
        if (ch1_segtime[i] <= 0 || ch1_segtime[i] < min_seg_time)
        {
            if(debug) printf("ERROR: CH1 segment %d has invalid time: %.6g s (min=%.6g s)\n", i, ch1_segtime[i], min_seg_time);
            free(ch1_startv); free(ch1_stopv); free(ch1_segtime);
            free(ch1_ssrctrl); free(ch1_segtrigout); free(ch1_meastype);
            free(ch1_measstart); free(ch1_measstop);
            return -122;
        }
    }
    
    // Configure seg_arb sequence for CH1
    if(debug) printf("Configuring seg_arb_sequence for CH%d (%d segments)...\n", chan, ch1_num_segments);
    
    status = seg_arb_sequence(pulserId, chan, 1, ch1_num_segments,
                              ch1_startv, ch1_stopv, ch1_segtime,
                              ch1_segtrigout, ch1_ssrctrl,
                              ch1_meastype, ch1_measstart, ch1_measstop);
    if ( status )
    {
        if(debug) 
        {
            printf("ERROR: seg_arb_sequence CH1 failed: %d\n", status);
            if (status == -804)
                printf("  Error -804: seg_arb function not valid in present pulse mode\n");
        }
        free(ch1_startv); free(ch1_stopv); free(ch1_segtime);
        free(ch1_ssrctrl); free(ch1_segtrigout); free(ch1_meastype);
        free(ch1_measstart); free(ch1_measstop);
        return status;
    }
    
    // Configure seg_arb waveform for CH1 (loop count = burstCount)
    long ch1_seqList[1] = {1};
    double ch1_loopCount[1] = {(double)burstCount};
    
    if(debug) printf("Configuring seg_arb_waveform for CH%d (loop count=%d)...\n", chan, burstCount);
    
    status = seg_arb_waveform(pulserId, chan, 1, ch1_seqList, ch1_loopCount);
    if ( status )
    {
        if(debug) printf("ERROR: seg_arb_waveform CH1 failed: %d\n", status);
        free(ch1_startv); free(ch1_stopv); free(ch1_segtime);
        free(ch1_ssrctrl); free(ch1_segtrigout); free(ch1_meastype);
        free(ch1_measstart); free(ch1_measstop);
        return status;
    }
    
    if(debug) 
    {
        printf("CH1 seg_arb configured: %d segments, loop count=%d\n", ch1_num_segments, burstCount);
        printf("  Total CH1 duration: %.6g s (%d pulses @ %.6g s period)\n", 
               burstCount * period, burstCount, period);
    }
    
    // Also set load resistance to help PMU optimize current measurement
    if (!LLEComp || !PMUMode)
    {
        status = pulse_load(pulserId, chan, DUTRes);
        if (status)
        {
            if(debug) printf("WARNING: pulse_load CH1 failed: %d (may affect current measurement)\n", status);
            // Don't return error, as pulse_load might not be critical for all configurations
        }
        else if(debug)
        {
            printf("Configured CH1 load resistance: %.2e Ohms (helps optimize current measurement)\n", DUTRes);
        }
    }
    
    // Free CH1 segment arrays (seg_arb_sequence has copied data to hardware)
    free(ch1_startv); free(ch1_stopv); free(ch1_segtime);
    free(ch1_ssrctrl); free(ch1_segtrigout); free(ch1_meastype);
    free(ch1_measstart); free(ch1_measstop);
    
    if(debug) printf("Configured CH1 for %d pulses with waveform capture (acqType=%d)\n", burstCount, acqType);

    // ============================================================
    // CH2 Setup for seg_arb waveform (no measurement)
    // ============================================================
    if (Ch2Enable)
    {
        int ch2 = (chan == 1) ? 2 : 1;  // Use the other channel
        
        // Allocate temporary arrays for auto-built segments if needed
        double *ch2_startv = NULL;
        double *ch2_stopv = NULL;
        double *ch2_segtime = NULL;
        long *ch2_ssrctrl = NULL;
        long *ch2_segtrigout = NULL;
        long *ch2_meastype = NULL;
        double *ch2_measstart = NULL;
        double *ch2_measstop = NULL;
        int actual_ch2_segments = Ch2NumSegments;
        int auto_build = 0;
        
        // MODE 1: Auto-build segments from simple pulse parameters
        if (Ch2NumSegments == 0)
        {
            auto_build = 1;
            actual_ch2_segments = 6;  // preDelay + rise + width + fall + postDelay + final 0V segment
            
            // Simple approach: Ch2Period is the delay before pulse starts
            // Just extend the first segment time to create the delay
            double ch2_min_seg_time = 20e-9;  // 20ns minimum segment time
            double ch2_pre_delay = (Ch2Period > ch2_min_seg_time) ? Ch2Period : ch2_min_seg_time;
            double ch2_post_delay = ch2_min_seg_time;  // Minimal post-delay after pulse
            
            if(debug) 
            {
                printf("Auto-building CH2 seg_arb segments (single pulse mode):\n");
                printf("  Vlow=%.6g V, Vhigh=%.6g V\n", Ch2Vlow, Ch2Vhigh);
                printf("  Width=%.6g s, Rise=%.6g s, Fall=%.6g s\n", Ch2Width, Ch2Rise, Ch2Fall);
                printf("  Pre-delay (Ch2Period)=%.6g s (pulse starts %.6g s into measurement)\n", ch2_pre_delay, ch2_pre_delay);
                printf("  Post-delay=%.6g s\n", ch2_post_delay);
            }
            
            // Allocate arrays
            ch2_startv = (double *)calloc(actual_ch2_segments, sizeof(double));
            ch2_stopv = (double *)calloc(actual_ch2_segments, sizeof(double));
            ch2_segtime = (double *)calloc(actual_ch2_segments, sizeof(double));
            ch2_ssrctrl = (long *)calloc(actual_ch2_segments, sizeof(long));
            ch2_segtrigout = (long *)calloc(actual_ch2_segments, sizeof(long));
            ch2_meastype = (long *)calloc(actual_ch2_segments, sizeof(long));
            ch2_measstart = (double *)calloc(actual_ch2_segments, sizeof(double));
            ch2_measstop = (double *)calloc(actual_ch2_segments, sizeof(double));
            
            if (!ch2_startv || !ch2_stopv || !ch2_segtime || !ch2_ssrctrl || 
                !ch2_segtrigout || !ch2_meastype || !ch2_measstart || !ch2_measstop)
            {
                if(debug) printf("ERROR: Failed to allocate memory for CH2 segments\n");
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
            
            // Build segments: preDelay + rise + width + fall + postDelay + final 0V
            int idx = 0;
            ch2_startv[idx] = Ch2Vlow; ch2_stopv[idx] = Ch2Vlow; ch2_segtime[idx] = ch2_pre_delay;
            ch2_ssrctrl[idx] = 1; ch2_segtrigout[idx] = (idx == 0) ? 1 : 0;
            ch2_meastype[idx] = 0; ch2_measstart[idx] = 0.0; ch2_measstop[idx] = 0.0;
            idx++;
            
            ch2_startv[idx] = Ch2Vlow; ch2_stopv[idx] = Ch2Vhigh; ch2_segtime[idx] = Ch2Rise;
            ch2_ssrctrl[idx] = 1; ch2_segtrigout[idx] = 0;
            ch2_meastype[idx] = 0; ch2_measstart[idx] = 0.0; ch2_measstop[idx] = 0.0;
            idx++;
            
            ch2_startv[idx] = Ch2Vhigh; ch2_stopv[idx] = Ch2Vhigh; ch2_segtime[idx] = Ch2Width;
            ch2_ssrctrl[idx] = 1; ch2_segtrigout[idx] = 0;
            ch2_meastype[idx] = 0; ch2_measstart[idx] = 0.0; ch2_measstop[idx] = 0.0;
            idx++;
            
            ch2_startv[idx] = Ch2Vhigh; ch2_stopv[idx] = Ch2Vlow; ch2_segtime[idx] = Ch2Fall;
            ch2_ssrctrl[idx] = 1; ch2_segtrigout[idx] = 0;
            ch2_meastype[idx] = 0; ch2_measstart[idx] = 0.0; ch2_measstop[idx] = 0.0;
            idx++;
            
            ch2_startv[idx] = Ch2Vlow; ch2_stopv[idx] = Ch2Vlow; ch2_segtime[idx] = ch2_post_delay;
            ch2_ssrctrl[idx] = 1; ch2_segtrigout[idx] = 0;  // Relays closed
            ch2_meastype[idx] = 0; ch2_measstart[idx] = 0.0; ch2_measstop[idx] = 0.0;
            idx++;
            
            // Segment 5: Final segment - ensure we end at 0V with relays closed
            ch2_startv[idx] = Ch2Vlow; ch2_stopv[idx] = 0.0; ch2_segtime[idx] = ch2_min_seg_time;
            ch2_ssrctrl[idx] = 1; ch2_segtrigout[idx] = 0;  // Relays closed
            ch2_meastype[idx] = 0; ch2_measstart[idx] = 0.0; ch2_measstop[idx] = 0.0;
            
            // For single pulse mode, loop count should be 1.0 (set by Python)
            // No need to auto-calculate
            
            if(debug) 
            {
                printf("Built %d segments for CH2:\n", actual_ch2_segments);
                for (i = 0; i < actual_ch2_segments; i++)
                {
                    printf("  Seg %d: %.6g V -> %.6g V, time=%.6g s\n", 
                           i, ch2_startv[i], ch2_stopv[i], ch2_segtime[i]);
                }
            }
        }
        // MODE 2: Use provided segment arrays
        else
        {
            if(debug) printf("Setting up CH%d for seg_arb waveform (%d segments - manual mode)\n", ch2, Ch2NumSegments);
            
            // Validate CH2 segment arrays
            if (Ch2NumSegments < 3 || Ch2NumSegments > 2048)
            {
                if(debug) printf("ERROR: Ch2NumSegments (%d) must be between 3 and 2048\n", Ch2NumSegments);
                return -122;
            }
            
            if (Ch2StartV_size < Ch2NumSegments || Ch2StopV_size < Ch2NumSegments || 
                Ch2SegTime_size < Ch2NumSegments || Ch2SSRCtrl_size < Ch2NumSegments ||
                Ch2SegTrigOut_size < Ch2NumSegments || Ch2MeasType_size < Ch2NumSegments ||
                Ch2MeasStart_size < Ch2NumSegments || Ch2MeasStop_size < Ch2NumSegments)
            {
                if(debug) printf("ERROR: CH2 segment arrays too small (need %d elements)\n", Ch2NumSegments);
                return -122;
            }
            
            // Use provided arrays
            ch2_startv = Ch2StartV;
            ch2_stopv = Ch2StopV;
            ch2_segtime = Ch2SegTime;
            ch2_ssrctrl = Ch2SSRCtrl;
            ch2_segtrigout = Ch2SegTrigOut;
            ch2_meastype = Ch2MeasType;
            ch2_measstart = Ch2MeasStart;
            ch2_measstop = Ch2MeasStop;
        }
        
        // Ensure RPM in pulse mode for CH2
        status = rpm_config(pulserId, ch2, KI_RPM_PATHWAY, KI_RPM_PULSE);
        if ( status && debug )
           printf("rpm_config CH2 returned: %d\n", status);
        
        // Set load for CH2 (required before seg_arb)
        status = pulse_load(pulserId, ch2, 1e6);  // High impedance load
        if ( status )
        {
            if(debug) printf("pulse_load CH2 failed: %d\n", status);
            return status;
        }
        
        // Set ranges for CH2 (no current measurement needed for seg_arb source-only)
        status = pulse_ranges(pulserId, ch2, Ch2VRange, PULSE_MEAS_FIXED, Ch2VRange, PULSE_MEAS_FIXED, 0.01);
        if ( status )
        {
            if(debug) printf("pulse_ranges CH2 failed: %d\n", status);
            return status;
        }
        
        // Set burst count for CH2 (required before seg_arb)
        status = pulse_burst_count(pulserId, ch2, 1);
        if ( status )
        {
            if(debug) printf("pulse_burst_count CH2 failed: %d\n", status);
            return status;
        }
        
        // Enable CH2 output (required before seg_arb)
        status = pulse_output(pulserId, ch2, 1);
        if ( status )
        {
            if(debug) printf("pulse_output CH2 failed: %d\n", status);
            return status;
        }
        
        // Configure seg_arb sequence for CH2
        // Note: seg_arb_sequence parameters:
        //   pulserId, channel, sequenceNumber, numSegments,
        //   startV[], stopV[], segTime[], trigOut[], ssrCtrl[],
        //   measType[], measStart[], measStop[]
        if(debug) 
        {
            printf("Configuring seg_arb_sequence for CH%d (%d segments)...\n", ch2, actual_ch2_segments);
            printf("  PMU should be in SARB mode (pulse_mode=%d)\n", pulse_mode);
            printf("  First segment: %.6g V -> %.6g V, time=%.6g s\n", 
                   ch2_startv[0], ch2_stopv[0], ch2_segtime[0]);
        }
        
        // CRITICAL: Verify we're in SARB mode (required for seg_arb functions)
        if(debug) 
        {
            printf("========================================\n");
            printf("CH2 seg_arb Configuration Check:\n");
            printf("  pulse_mode variable=%d\n", pulse_mode);
            printf("  PULSE_MODE_SARB constant=%d\n", PULSE_MODE_SARB);
            printf("  Ch2Enable=%d\n", Ch2Enable);
            printf("  Mode match: %s\n", (pulse_mode == PULSE_MODE_SARB) ? "YES ✓" : "NO ✗");
            printf("========================================\n");
        }
        
        if (pulse_mode != PULSE_MODE_SARB)
        {
            if(debug) 
            {
                printf("ERROR: PMU not in SARB mode!\n");
                printf("  Current pulse_mode=%d\n", pulse_mode);
                printf("  Required PULSE_MODE_SARB=%d\n", PULSE_MODE_SARB);
                printf("  Ch2Enable=%d (should trigger SARB mode)\n", Ch2Enable);
                printf("  This will cause seg_arb_sequence to fail with -804\n");
            }
            return -804;  // Return the same error code that seg_arb would return
        }
        
        status = seg_arb_sequence(pulserId, ch2, 1, actual_ch2_segments,
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
                printf("  Current pulse_mode=%d (should be %d for SARB)\n", pulse_mode, PULSE_MODE_SARB);
                printf("  Check that segment voltages are continuous (startV[i] == stopV[i-1])\n");
                printf("  Check that first SegTrigOut[0] == 1\n");
            }
            return status;
        }
        
        // Configure seg_arb waveform (sequence 1, with specified loop count)
        // Loop count determines how many times the seg_arb sequence repeats
        // Validate Ch2LoopCount before using it
        if (Ch2LoopCount <= 0 || Ch2LoopCount < 1.0)
        {
            if(debug) printf("ERROR: Ch2LoopCount (%.6g) must be >= 1.0\n", Ch2LoopCount);
            // Free auto-allocated arrays on error
            if (auto_build)
            {
                if (ch2_startv) free(ch2_startv);
                if (ch2_stopv) free(ch2_stopv);
                if (ch2_segtime) free(ch2_segtime);
                if (ch2_ssrctrl) free(ch2_ssrctrl);
                if (ch2_segtrigout) free(ch2_segtrigout);
                if (ch2_meastype) free(ch2_meastype);
                if (ch2_measstart) free(ch2_measstart);
                if (ch2_measstop) free(ch2_measstop);
            }
            return -122;
        }
        
        // Ensure loop count is at least 1.0 and is a valid number
        double valid_loop_count = Ch2LoopCount;
        if (valid_loop_count < 1.0) valid_loop_count = 1.0;
        
        long seqList[1] = {1};
        double loopCount[1] = {valid_loop_count};
        
        if(debug) 
        {
            printf("Configuring seg_arb_waveform for CH%d:\n", ch2);
            printf("  Original Ch2LoopCount: %.6g\n", Ch2LoopCount);
            printf("  Using loop count: %.6g\n", valid_loop_count);
        }
        
        // Calculate total CH2 waveform time for reference
        double ch2_total_time = 0.0;
        for (i = 0; i < actual_ch2_segments; i++)
        {
            ch2_total_time += ch2_segtime[i];
        }
        double ch2_effective_period = ch2_total_time;  // Period = one cycle time
        double ch2_total_duration = ch2_total_time * valid_loop_count;
        
        if(debug) 
        {
            printf("CH2 seg_arb timing:\n");
            printf("  One cycle time: %.6g s (sum of %d segment times)\n", ch2_total_time, actual_ch2_segments);
            printf("  Loop count: %.6g (using %.6g)\n", Ch2LoopCount, valid_loop_count);
            printf("  Total CH2 duration: %.6g s\n", ch2_total_duration);
            printf("  CH1 measurement duration: %.6g s (%d pulses @ %.6g s period)\n", 
                   burstCount * period, burstCount, period);
            if (auto_build)
                printf("  CH2 pulse period: %.6g s (independent of CH1!)\n", Ch2Period);
        }
        
        if(debug) 
        {
            printf("Calling seg_arb_waveform:\n");
            printf("  pulserId=%d, channel=%d, numSequences=1\n", pulserId, ch2);
            printf("  seqList[0]=%ld\n", seqList[0]);
            printf("  loopCount[0]=%.6g\n", loopCount[0]);
        }
        
        status = seg_arb_waveform(pulserId, ch2, 1, seqList, loopCount);
        if ( status )
        {
            if(debug) 
            {
                printf("ERROR: seg_arb_waveform CH2 failed: %d\n", status);
                printf("  Parameter 5 (loopCount[0]) = %.6g\n", loopCount[0]);
                if (loopCount[0] <= 0)
                    printf("  ERROR: loopCount must be > 0!\n");
                if (loopCount[0] < 1.0)
                    printf("  ERROR: loopCount must be >= 1.0!\n");
            }
            // Free auto-allocated arrays on error
            if (auto_build)
            {
                if (ch2_startv) free(ch2_startv);
                if (ch2_stopv) free(ch2_stopv);
                if (ch2_segtime) free(ch2_segtime);
                if (ch2_ssrctrl) free(ch2_ssrctrl);
                if (ch2_segtrigout) free(ch2_segtrigout);
                if (ch2_meastype) free(ch2_meastype);
                if (ch2_measstart) free(ch2_measstart);
                if (ch2_measstop) free(ch2_measstop);
            }
            return status;
        }
        
        // Free auto-allocated arrays now (seg_arb_sequence has copied data to hardware)
        if (auto_build)
        {
            free(ch2_startv);
            free(ch2_stopv);
            free(ch2_segtime);
            free(ch2_ssrctrl);
            free(ch2_segtrigout);
            free(ch2_meastype);
            free(ch2_measstart);
            free(ch2_measstop);
            if(debug) printf("Freed auto-allocated CH2 segment arrays\n");
        }
        
        // CH2 output already enabled before seg_arb_sequence, no need to enable again
        
        if(debug) 
        {
            printf("CH2 seg_arb configured: %d segments\n", actual_ch2_segments);
            if (!auto_build)  // Only print segment details if using manual mode
            {
                printf("  First segment: %.6g V -> %.6g V, time=%.6g s\n", 
                       Ch2StartV[0], Ch2StopV[0], Ch2SegTime[0]);
                if (actual_ch2_segments > 1)
                    printf("  Last segment: %.6g V -> %.6g V, time=%.6g s\n", 
                           Ch2StartV[actual_ch2_segments-1], Ch2StopV[actual_ch2_segments-1], Ch2SegTime[actual_ch2_segments-1]);
            }
        }
    }

    // CRITICAL: In seg_arb mode, measurement is controlled by meastype[] in seg_arb_sequence()
    // DO NOT call pulse_meas_wfm() or pulse_meas_sm() - these are for simple pulse mode only
    // The Python minimum working example confirms: seg_arb uses meas_type[] array, not pulse_meas_*()
    // Our meastype[] is already set to PULSE_MEAS_WFM_PER or PULSE_MEAS_WFM_BURST for measured segments
    // and PULSE_MEAS_NONE for non-measured segments, which is correct.
    if(debug) 
    {
        printf("Seg_arb mode: Measurement controlled by meastype[] in seg_arb_sequence()\n");
        printf("  NOT using pulse_meas_wfm() - that's for simple pulse mode only\n");
    }

    // Set test execute mode to Simple or Advanced
    if (PMUMode ==0)
        TestMode = PULSE_MODE_SIMPLE;
    else
        TestMode = PULSE_MODE_ADVANCED;

    if(debug) printf("About to execute: TestMode=%d, CH1 burstCount=%d, CH2 enabled=%d\n", TestMode, burstCount, Ch2Enable);
    
    // Execute both channels together
    if(debug) printf("Executing pulses (CH1 seg_arb + CH2 seg_arb)...\n");
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

    // Small delay to ensure measurement data is ready (working examples sometimes have commented Sleep here)
    Sleep(50);  // 50ms delay to ensure data is ready
    
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
    
    // Calculate expected number of samples based on total measurement time
    // For seg_arb with loop count, total time = period * burstCount
    double total_measurement_time = period * burstCount;
    int expectedSamples = (int)(total_measurement_time * SampleRate + 1);
    
    // Allocate temporary buffers for full waveform
    // Use expected samples, not pulse_chan_status (which can be unreliable)
    int maxSamples = expectedSamples;
    if (maxSamples < 100) maxSamples = 100;  // Minimum buffer size
    if (maxSamples > 100000) maxSamples = 1000000;  // Maximum buffer size:  changed 0 added to make it million
    
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
        printf("  Sample rate: %.6g Hz\n", SampleRate);
        printf("  Expected samples: %d\n", expectedSamples);
        printf("  Buffer size: %d\n", maxSamples);
        printf("  Fetching (StartIndex=0, StopIndex=%d)...\n", maxSamples-1);
    }
    
    // Fetch waveform data - use maxSamples-1 as StopIndex (pulse_fetch is inclusive)
    // IMPORTANT: pulse_fetch returns MEASURED voltage and current from the specified channel
    // For single-channel mode (CH1), this is the measured voltage at the DUT and current through the DUT
    // For dual-channel mode, you would fetch separately from ForceCh and MeasureCh
    if(debug) printf("Fetching data from CH%d (single-channel mode: force + measure)\n", chan);
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
    
    if(debug) 
    {
        printf("Fetched %d waveform samples, extracting averaged values per pulse...\n", numWaveformSamples);
        printf("\n[DEBUG] Data acquisition summary:\n");
        printf("  Channel: CH%d (single-channel mode: CH1 both forces and measures)\n", chan);
        printf("  Measurement type: meastype=2 (waveform measurement enabled in seg_arb)\n");
        printf("  Current measurement range: %.6e A (%.1f µA)\n", currentMeasureRng, currentMeasureRng*1e6);
        printf("  pulse_load(DUTRes=%.0f): Internal load impedance setting\n", DUTRes);
        printf("  waveformV[]: MEASURED voltage at DUT terminal (from pulse_fetch)\n");
        printf("  waveformI[]: MEASURED current through DUT (from pulse_fetch)\n");
        
        if(numWaveformSamples > 0)
        {
            // Check current statistics
            double minI = waveformI[0], maxI = waveformI[0], sumI = 0.0;
            for(i = 0; i < numWaveformSamples; i++)
            {
                if(waveformI[i] < minI) minI = waveformI[i];
                if(waveformI[i] > maxI) maxI = waveformI[i];
                sumI += waveformI[i];
            }
            double avgI = sumI / numWaveformSamples;
            double currentRange = maxI - minI;
            
            printf("\n[DEBUG] Current statistics:\n");
            printf("  Min current: %.6e A (%.3f µA)\n", minI, minI*1e6);
            printf("  Max current: %.6e A (%.3f µA)\n", maxI, maxI*1e6);
            printf("  Avg current: %.6e A (%.3f µA)\n", avgI, avgI*1e6);
            printf("  Current range (max-min): %.6e A (%.3f nA)\n", currentRange, currentRange*1e9);
            printf("  Measurement range: %.6e A (%.1f µA)\n", currentMeasureRng, currentMeasureRng*1e6);
            
            // Calculate expected current for a 100kΩ resistor at 1V
            double expected_current_100k = 1.0 / 100000.0;  // 10µA
            printf("\n[DEBUG] Expected vs Measured Current:\n");
            printf("  For 100kΩ @ 1V: Expected = %.3f µA\n", expected_current_100k*1e6);
            printf("  Measured average = %.3f µA\n", avgI*1e6);
            printf("  Ratio (measured/expected) = %.1f\n", avgI / expected_current_100k);
            
            if(fabs(avgI) > 10.0 * expected_current_100k)
            {
                printf("  ⚠️  CRITICAL: Measured current is >10x expected for 100kΩ!\n");
                printf("     This strongly suggests pulse_fetch() in single-channel seg_arb mode\n");
                printf("     is returning SOURCE/FORCED current, not MEASURED DUT current!\n");
                printf("     \n");
                printf("     SOLUTION: Single-channel seg_arb mode may not support accurate\n");
                printf("     current measurement. Consider:\n");
                printf("     1. Using dual-channel mode (CH1 force, CH2 measure) if possible\n");
                printf("     2. Using simple pulse mode instead of seg_arb for CH1\n");
                printf("     3. Verifying physical connections (4-wire vs 2-wire)\n");
            }
            
            // Check if current is suspiciously close to range limit
            if(fabs(avgI) > 0.8 * currentMeasureRng)
            {
                printf("  ⚠️  WARNING: Current (%.3f µA) is >80%% of range (%.1f µA)!\n", avgI*1e6, currentMeasureRng*1e6);
                printf("     This suggests current might be range-limited/saturated!\n");
                printf("     Try a LOWER current range to see if current changes.\n");
            }
            
            if(currentRange < 1e-12)
            {
                printf("  ⚠️  WARNING: Current shows NO variation (range < 1pA)!\n");
                printf("     All samples are identical: %.6e A\n", avgI);
                printf("     This suggests current might be:\n");
                printf("     - Range-limited/saturated at range limit\n");
                printf("     - Measurement artifact, not real DUT current\n");
                printf("     - Leakage current being measured\n");
            }
            
            printf("\n  First sample: V=%.6f V, I=%.6e A (%.3f µA), t=%.6e s\n", 
                   waveformV[0], waveformI[0], waveformI[0]*1e6, waveformT[0]);
            printf("  Sample 10: V=%.6f V, I=%.6e A (%.3f µA), t=%.6e s\n", 
                   (numWaveformSamples > 10) ? waveformV[10] : 0.0,
                   (numWaveformSamples > 10) ? waveformI[10] : 0.0,
                   (numWaveformSamples > 10) ? waveformI[10]*1e6 : 0.0,
                   (numWaveformSamples > 10) ? waveformT[10] : 0.0);
        }
        
        printf("\n  ⚠️  SINGLE-CHANNEL MODE CURRENT MEASUREMENT LIMITATION:\n");
        printf("     This script uses CH1 for BOTH forcing and measuring (single-channel mode)\n");
        printf("     because CH2 is needed for the laser pulse.\n");
        printf("     \n");
        printf("     ISSUE: Current appears to scale with range setting, suggesting range saturation:\n");
        printf("     - 100nA range → ~108nA current (108%% of range)\n");
        printf("     - 1µA range → ~1.09µA current (109%% of range)\n");
        printf("     This indicates current is being clamped at range limit, not real DUT current!\n");
        printf("     \n");
        printf("     RECOMMENDATION:\n");
        printf("     - If possible, use dual-channel mode (CH1 force, CH2 measure) like other scripts\n");
        printf("     - If CH2 must be used for laser, consider:\n");
        printf("       1. Using a different setup where laser doesn't need CH2\n");
        printf("       2. Accepting that single-channel current may be range-limited\n");
        printf("       3. Verifying connections (CH1 Force/Measure to DUT, CH1 Sense/Ground)\n");
        printf("     \n");
        printf("     Minimum valid current range: 100nA (1e-7 A)\n");
        printf("     Maximum valid current range: 0.8 A\n");
    }
    
    // Calculate baseline/offset current when voltage is near zero (for offset compensation)
    // This is critical for accurate measurements with open circuits or high-impedance devices
    double baseline_current_offset = 0.0;
    int baseline_count = 0;
    double baseline_current_sum = 0.0;
    
    for(i = 0; i < numWaveformSamples; i++)
    {
        // Measure offset during zero-volt periods (voltage < 0.1V)
        if(fabs(waveformV[i]) < 0.1)
        {
            baseline_current_sum += waveformI[i];
            baseline_count++;
        }
    }
    
    if(baseline_count > 0)
    {
        baseline_current_offset = baseline_current_sum / baseline_count;
        if(debug)
        {
            printf("\n[DEBUG] Offset compensation:\n");
            printf("  Baseline current (when |V| < 0.1V): %.6e A (from %d samples)\n", baseline_current_offset, baseline_count);
            if(fabs(baseline_current_offset) > 1e-9)
            {
                printf("  ⚠️  Non-zero baseline current detected - will compensate\n");
            }
        }
    }
    else
    {
        if(debug) printf("[DEBUG] Warning: No zero-volt samples found for baseline measurement\n");
    }
    
    // Debug: Print first few raw samples to check what we're getting
    if(debug && numWaveformSamples > 5)
    {
        printf("\n[DEBUG] First 5 raw waveform samples (before offset compensation):\n");
        printf("  Sample  V_measured(V)  I_measured(A)  I_compensated(A)  Time(s)\n");
        for(i = 0; i < 5 && i < numWaveformSamples; i++)
        {
            double compensated_current = waveformI[i] - baseline_current_offset;
            printf("  %d      %.6f       %.6e    %.6e    %.6e\n", 
                   i, waveformV[i], waveformI[i], compensated_current, waveformT[i]);
        }
    }
    
    // Extract one averaged value per pulse (from 40-80% of pulse width)
    int outputIdx = 0;
    double measurementStartFrac = 0.5;
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
            
            // Average samples in measurement window (with offset compensation)
            double sumV = 0.0, sumI = 0.0, sumT = 0.0;
            int count = 0;
            
            for (j = measStartSample; j <= measEndSample && j < numWaveformSamples; j++)
            {
                sumV += waveformV[j];
                // Subtract baseline/offset current for accurate measurement
                sumI += (waveformI[j] - baseline_current_offset);
                sumT += waveformT[j];
                count++;
            }
            
            if (count > 0)
            {
                V_Meas[outputIdx] = sumV / count;
                I_Meas[outputIdx] = sumI / count;  // Already compensated
                T_Stamp[outputIdx] = sumT / count;
                
                if(debug && outputIdx < 5)
                {
                    double raw_avg_current = 0.0;
                    for (j = measStartSample; j <= measEndSample && j < numWaveformSamples; j++)
                    {
                        raw_avg_current += waveformI[j];
                    }
                    raw_avg_current /= count;
                    printf("[DEBUG] Pulse %d: V=%.6f V, I_raw=%.6e A, I_offset=%.6e A, I_net=%.6e A\n",
                           outputIdx, V_Meas[outputIdx], raw_avg_current, baseline_current_offset, I_Meas[outputIdx]);
                }
                
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
                    // Subtract baseline/offset current for accurate measurement
                    sumI += (waveformI[i] - baseline_current_offset);
                    sumT += waveformT[i];
                    count++;
                }
            }
            
            if (count > 0)
            {
                V_Meas[outputIdx] = sumV / count;
                I_Meas[outputIdx] = sumI / count;  // Already compensated
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
        printf("ACraig10_PMU_Waveform_SegArb: complete, returning to KXCI\n");
    }

    return 0;
/* USRLIB MODULE END  */
} 		/* End ACraig10_PMU_Waveform_SegArb.c */

