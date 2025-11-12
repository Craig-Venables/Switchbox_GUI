/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig11_PMU_Waveform_Binary
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 41
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
		Ch2PatternSize,	int,	Input,	8,	1,	2048
		Ch2Pattern,	char *,	Input,	"10110100",	,	
		Ch2Delay,	double,	Input,	0.0,	0,	.999999
		Ch2Width,	double,	Input,	500e-9,	20e-9,	.999999
		Ch2Rise,	double,	Input,	100e-9,	20e-9,	.033
		Ch2Fall,	double,	Input,	100e-9,	20e-9,	.033
		Ch2Spacing,	double,	Input,	500e-9,	20e-9,	.999999
		Ch2Vlow,	double,	Input,	0.0,	-40,	40
		Ch2Vhigh,	double,	Input,	1.0,	-40,	40
		Ch2LoopCount,	double,	Input,	1.0,	1.0,	100000.0
		ClariusDebug,	int,	Input,	0,	0,	1
INCLUDES:
#include "keithley.h"
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
ACraig11_PMU_Waveform_Binary: PMU waveform capture on CH1 with binary pulse train on CH2 (KXCI compatible)

This module combines:
- CH1: Simple pulse commands for continuous waveform measurement (voltage/current vs time)
- CH2: Binary pulse train using seg_arb (sequence of 1s and 0s)

Uses pulse_fetch() instead of pulse_measrt() for KXCI compatibility.

CH1: Measures DUT voltage and current with waveform capture using simple pulse commands
CH2: Binary pulse train (no measurement) - generates sequence of high/low pulses based on pattern

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

Example with 1µs pulse width:
- Pulse starts at t=0 (after delay + rise)
- Measurement window: 0.4µs to 0.8µs (40-80% of 1µs)
- All samples within this window are averaged to produce one value per pulse
- This gives accurate resistance measurements by avoiding transient effects

The measurement window is hardcoded in the C code at:
  measurementStartFrac = 0.4  (40% of pulse width)
  measurementEndFrac = 0.8    (80% of pulse width)

CH2 BINARY PATTERN PARAMETERS:
==============================
CH2 generates a binary pulse train based on a pattern array of 0s and 1s.

Parameters:
- Ch2Pattern: Array of integers (0s and 1s) defining the binary pattern
  Example: [1,0,1,1,0,1,0,0] generates: HIGH-LOW-HIGH-HIGH-LOW-HIGH-LOW-LOW
- Ch2PatternSize: Length of pattern array (1-2048 bits)
- Ch2Delay: Delay before pattern starts in seconds (0 = no delay) - holds at 0V during delay
- Ch2Width: Pulse width for '1' bits in seconds (minimum 20ns) - duration of flat high
- Ch2Rise: Rise time in seconds (minimum 20ns) - transition time from low to high
- Ch2Fall: Fall time in seconds (minimum 20ns) - transition time from high to low
- Ch2Spacing: Spacing between bits in seconds (minimum 20ns) - flat low time after fall
- Ch2Vlow: Voltage level for '0' bits (typically 0V)
- Ch2Vhigh: Voltage level for '1' bits (typically 1V, 3.3V, or 5V)
- Ch2LoopCount: Number of times to repeat the entire pattern (default 1.0)

How it works:
- Delay segment: Hold at 0V for Ch2Delay (if > 0)
- Bit = 1: Rise to high (Ch2Rise) + flat high (Ch2Width) + fall to low (Ch2Fall) + spacing low (Ch2Spacing)
- Bit = 0: Fall to low (Ch2Fall, if needed) + flat low (Ch2Spacing)
- Each bit creates 2-4 segments depending on voltage transitions
- Pattern repeats Ch2LoopCount times

Example: Pattern [1,0,1] with Ch2Delay=5µs, Ch2Width=500ns, Ch2Rise=100ns, Ch2Fall=100ns, Ch2Spacing=500ns, Ch2Vlow=0V, Ch2Vhigh=1.5V:
- Delay: 0V flat (5µs)
- Bit 1: 0V->1.5V (100ns rise) + 1.5V flat (500ns) + 1.5V->0V (100ns fall) + 0V flat (500ns spacing)
- Bit 0: 0V flat (500ns spacing)
- Bit 1: 0V->1.5V (100ns rise) + 1.5V flat (500ns) + 1.5V->0V (100ns fall) + 0V flat (500ns spacing)
- Total pattern duration: ~7.2µs (5µs delay + 2.2µs pattern)

NOTE: CH2 should be enabled (Ch2Enable=1) even if not using it - disabling CH2 may cause pulse_exec to fail.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <math.h>  // For fmod, floor, ceil
#include <stdlib.h>  // For calloc, free
#include <string.h>  // For strlen

BOOL LPTIsInCurrentConfiguration(char* hrid);

/* USRLIB MODULE MAIN FUNCTION */
int ACraig11_PMU_Waveform_Binary( 
    double width, double rise, double fall, double delay, double period, 
    double voltsSourceRng, double currentMeasureRng, double DUTRes, 
    double startV, double stopV, double stepV, double baseV, 
    int acqType, int LLEComp, double preDataPct, double postDataPct, 
    int pulseAvgCnt, int burstCount, double SampleRate, int PMUMode, 
    int chan, char *PMU_ID, 
    double *V_Meas, int size_V_Meas, 
    double *I_Meas, int size_I_Meas, 
    double *T_Stamp, int size_T_Stamp, 
    int Ch2Enable, double Ch2VRange, 
    int Ch2PatternSize, char *Ch2Pattern,
    double Ch2Delay, double Ch2Width, double Ch2Rise, double Ch2Fall, double Ch2Spacing, double Ch2Vlow, double Ch2Vhigh, double Ch2LoopCount,
    int ClariusDebug )
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
    if(debug) printf("\n\nACraig11_PMU_Waveform_Binary: starts\n");
    
    // Validate Ch2PatternSize
    if (Ch2PatternSize < 1 || Ch2PatternSize > 2048)
    {
        if(debug) printf("ERROR: Ch2PatternSize (%d) must be between 1 and 2048\n", Ch2PatternSize);
        return -122;
    }
    
    // Parse Ch2Pattern string (e.g., "10110100") into array (only if CH2 enabled)
    long *patternArray = NULL;
    double ch2_min_seg_time = 20e-9;  // 20ns minimum segment time (used for CH2 segments)
    if (Ch2Enable)
    {
        // Validate Ch2Width, Ch2Rise, Ch2Fall, and Ch2Spacing
        if (Ch2Width < ch2_min_seg_time)
        {
            if(debug) printf("ERROR: Ch2Width (%.6g) must be >= %.6g s (20ns minimum)\n", Ch2Width, ch2_min_seg_time);
            return -122;
        }
        if (Ch2Rise < ch2_min_seg_time)
        {
            if(debug) printf("ERROR: Ch2Rise (%.6g) must be >= %.6g s (20ns minimum)\n", Ch2Rise, ch2_min_seg_time);
            return -122;
        }
        if (Ch2Fall < ch2_min_seg_time)
        {
            if(debug) printf("ERROR: Ch2Fall (%.6g) must be >= %.6g s (20ns minimum)\n", Ch2Fall, ch2_min_seg_time);
            return -122;
        }
        if (Ch2Spacing < ch2_min_seg_time)
        {
            if(debug) printf("ERROR: Ch2Spacing (%.6g) must be >= %.6g s (20ns minimum)\n", Ch2Spacing, ch2_min_seg_time);
            return -122;
        }
        
        // Parse Ch2Pattern string (e.g., "10110100") into array
        if (Ch2Pattern == NULL)
        {
            if(debug) printf("ERROR: Ch2Pattern string is NULL\n");
            return -122;
        }
        
        // Allocate temporary array for parsed pattern
        patternArray = (long *)calloc(Ch2PatternSize, sizeof(long));
        if (patternArray == NULL)
        {
            if(debug) printf("ERROR: Failed to allocate memory for pattern array\n");
            return -999;
        }
        
        // Parse string character by character
        int patternLen = strlen(Ch2Pattern);
        if (patternLen < Ch2PatternSize)
        {
            if(debug) printf("ERROR: Ch2Pattern string length (%d) < Ch2PatternSize (%d)\n", patternLen, Ch2PatternSize);
            free(patternArray);
            return -122;
        }
        
        // Convert string to array (each char '0' or '1' -> 0 or 1)
        for (i = 0; i < Ch2PatternSize; i++)
        {
            char c = Ch2Pattern[i];
            if (c == '0')
                patternArray[i] = 0;
            else if (c == '1')
                patternArray[i] = 1;
            else
            {
                if(debug) printf("ERROR: Ch2Pattern[%d] = '%c' (must be '0' or '1')\n", i, c);
                free(patternArray);
                return -122;
            }
        }
    }
    
    if(debug) 
    {
        printf("========================================\n");
        printf("ACraig11_PMU_Waveform_Binary:\n");
        printf("  CH1: Waveform measurement (acqType=%d, burstCount=%d)\n", acqType, burstCount);
        printf("  CH2: Binary pattern (size=%d, delay=%.6g s, width=%.6g s, rise=%.6g s, fall=%.6g s, spacing=%.6g s, loopCount=%.6g)\n",
               Ch2PatternSize, Ch2Delay, Ch2Width, Ch2Rise, Ch2Fall, Ch2Spacing, Ch2LoopCount);
        printf("  Pattern string: %s\n", Ch2Pattern);
        printf("  Pattern array: [");
        for (i = 0; i < Ch2PatternSize && i < 20; i++)
        {
            printf("%ld", patternArray[i]);
            if (i < Ch2PatternSize - 1 && i < 19) printf(",");
        }
        if (Ch2PatternSize > 20) printf("...");
        printf("]\n");
        printf("========================================\n");
    }

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
        printf("  CH2: Using seg_arb binary pattern (Ch2Enable=%d, Ch2PatternSize=%d)\n", Ch2Enable, Ch2PatternSize);
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
    // For seg_arb waveform measurement, use meastype=2 and measure full segment duration
    // Following working example: measstart=0, measstop=segtime for each segment
    int idx = 0;
    
    // Segment 0: Pre-delay (at baseV) - no measurement
    // If delay is 0, use minimum segment time to avoid invalid parameter
    double seg0_time = (delay > 0) ? delay : min_seg_time;
    ch1_startv[idx] = baseV; ch1_stopv[idx] = baseV; ch1_segtime[idx] = seg0_time;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 1;  // First segment triggers
    ch1_meastype[idx] = 0; ch1_measstart[idx] = 0.0; ch1_measstop[idx] = 0.0;  // No measurement
    idx++;
    
    // Segment 1: Rise (baseV -> startV) - measure full segment
    ch1_startv[idx] = baseV; ch1_stopv[idx] = startV; ch1_segtime[idx] = rise;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = 2;  // Waveform measurement (type 2, not 3!)
    ch1_measstart[idx] = 0.0;  // Start of segment
    ch1_measstop[idx] = rise;  // End of segment (full duration)
    idx++;
    
    // Segment 2: Width (at startV) - measure full segment (this is where 40-80% window will be extracted)
    ch1_startv[idx] = startV; ch1_stopv[idx] = startV; ch1_segtime[idx] = width;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = 2;  // Waveform measurement (type 2, not 3!)
    ch1_measstart[idx] = 0.0;  // Start of segment
    ch1_measstop[idx] = width;  // End of segment (full duration)
    idx++;
    
    // Segment 3: Fall (startV -> baseV) - measure full segment
    ch1_startv[idx] = startV; ch1_stopv[idx] = baseV; ch1_segtime[idx] = fall;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;
    ch1_meastype[idx] = 2;  // Waveform measurement (type 2, not 3!)
    ch1_measstart[idx] = 0.0;  // Start of segment
    ch1_measstop[idx] = fall;  // End of segment (full duration)
    idx++;
    
    // Segment 4: Post-delay (at baseV)
    // Ensure post_delay is at least minimum segment time (or 0 if period exactly matches pulse time)
    double seg4_time = (ch1_post_delay > 0) ? ch1_post_delay : min_seg_time;
    ch1_startv[idx] = baseV; ch1_stopv[idx] = baseV; ch1_segtime[idx] = seg4_time;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;  // Relays closed
    ch1_meastype[idx] = 0; ch1_measstart[idx] = 0.0; ch1_measstop[idx] = 0.0;
    idx++;
    
    // Segment 5: Final segment - ensure we end at 0V with relays closed
    ch1_startv[idx] = baseV; ch1_stopv[idx] = 0.0; ch1_segtime[idx] = min_seg_time;
    ch1_ssrctrl[idx] = 1; ch1_segtrigout[idx] = 0;  // Relays closed
    ch1_meastype[idx] = 0; ch1_measstart[idx] = 0.0; ch1_measstop[idx] = 0.0;
    
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
    if(debug) 
    {
        printf("Configuring seg_arb_sequence for CH%d (%d segments)...\n", chan, ch1_num_segments);
        printf("  pulserId=%d, channel=%d, sequenceNumber=1, numSegments=%d\n", pulserId, chan, ch1_num_segments);
        fflush(stdout);
    }
    
    status = seg_arb_sequence(pulserId, chan, 1, ch1_num_segments,
                              ch1_startv, ch1_stopv, ch1_segtime,
                              ch1_segtrigout, ch1_ssrctrl,
                              ch1_meastype, ch1_measstart, ch1_measstop);
    
    if(debug) 
    {
        printf("seg_arb_sequence CH1 returned: %d\n", status);
        fflush(stdout);
    }
    
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
        
        // Build CH2 segments from binary pattern
        // Each bit gets: transition (if voltage changed) + flat segment
        // Maximum segments: 2 per bit + 1 final = 2*Ch2PatternSize + 1
        // But we'll allocate dynamically based on actual pattern
        int max_ch2_segments = 2 * Ch2PatternSize + 2;  // Extra buffer for safety
        int actual_ch2_segments = max_ch2_segments;  // Will be updated after building
        
        // Allocate arrays for segments (use max size)
        double *ch2_startv = (double *)calloc(max_ch2_segments, sizeof(double));
        double *ch2_stopv = (double *)calloc(max_ch2_segments, sizeof(double));
        double *ch2_segtime = (double *)calloc(max_ch2_segments, sizeof(double));
        long *ch2_ssrctrl = (long *)calloc(max_ch2_segments, sizeof(long));
        long *ch2_segtrigout = (long *)calloc(max_ch2_segments, sizeof(long));
        long *ch2_meastype = (long *)calloc(max_ch2_segments, sizeof(long));
        double *ch2_measstart = (double *)calloc(max_ch2_segments, sizeof(double));
        double *ch2_measstop = (double *)calloc(max_ch2_segments, sizeof(double));
        
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
        
        // Build segments from pattern
        // Start with delay segment (if Ch2Delay > 0)
        // For each bit:
        //   - If bit = 1: rise to high + width (flat high) + fall to low + spacing (flat low)
        //   - If bit = 0: spacing (flat low) only
        double prev_voltage = 0.0;  // Start at 0V
        
        int seg_idx = 0;
        
        // Add delay segment at the beginning (if delay > 0)
        if (Ch2Delay > ch2_min_seg_time)
        {
            ch2_startv[seg_idx] = 0.0;
            ch2_stopv[seg_idx] = 0.0;  // Hold at 0V during delay
            ch2_segtime[seg_idx] = Ch2Delay;
            ch2_ssrctrl[seg_idx] = 1;
            ch2_segtrigout[seg_idx] = 1;  // First segment triggers
            ch2_meastype[seg_idx] = 0;
            ch2_measstart[seg_idx] = 0.0;
            ch2_measstop[seg_idx] = 0.0;
            seg_idx++;
            prev_voltage = 0.0;
        }
        
        for (i = 0; i < Ch2PatternSize; i++)
        {
            if (patternArray[i] == 1)  // Bit = 1: pulse high
            {
                // Rise: transition to high voltage (if not already high)
                if (fabs(prev_voltage - Ch2Vhigh) > 1e-6)
                {
                    ch2_startv[seg_idx] = prev_voltage;
                    ch2_stopv[seg_idx] = Ch2Vhigh;
                    ch2_segtime[seg_idx] = Ch2Rise;
                    ch2_ssrctrl[seg_idx] = 1;
                    ch2_segtrigout[seg_idx] = (seg_idx == 0) ? 1 : 0;
                    ch2_meastype[seg_idx] = 0;
                    ch2_measstart[seg_idx] = 0.0;
                    ch2_measstop[seg_idx] = 0.0;
                    seg_idx++;
                }
                
                // Flat top at high voltage (pulse width)
                ch2_startv[seg_idx] = Ch2Vhigh;
                ch2_stopv[seg_idx] = Ch2Vhigh;  // Flat
                ch2_segtime[seg_idx] = Ch2Width;
                ch2_ssrctrl[seg_idx] = 1;
                ch2_segtrigout[seg_idx] = (seg_idx == 0) ? 1 : 0;
                ch2_meastype[seg_idx] = 0;
                ch2_measstart[seg_idx] = 0.0;
                ch2_measstop[seg_idx] = 0.0;
                seg_idx++;
                
                // Fall: transition to low
                ch2_startv[seg_idx] = Ch2Vhigh;
                ch2_stopv[seg_idx] = Ch2Vlow;
                ch2_segtime[seg_idx] = Ch2Fall;
                ch2_ssrctrl[seg_idx] = 1;
                ch2_segtrigout[seg_idx] = 0;
                ch2_meastype[seg_idx] = 0;
                ch2_measstart[seg_idx] = 0.0;
                ch2_measstop[seg_idx] = 0.0;
                seg_idx++;
                
                // Spacing: flat low after fall
                ch2_startv[seg_idx] = Ch2Vlow;
                ch2_stopv[seg_idx] = Ch2Vlow;  // Flat
                ch2_segtime[seg_idx] = Ch2Spacing;
                ch2_ssrctrl[seg_idx] = 1;
                ch2_segtrigout[seg_idx] = 0;
                ch2_meastype[seg_idx] = 0;
                ch2_measstart[seg_idx] = 0.0;
                ch2_measstop[seg_idx] = 0.0;
                seg_idx++;
                
                prev_voltage = Ch2Vlow;
            }
            else  // Bit = 0: stay low (spacing only)
            {
                // Spacing: hold at low voltage
                if (fabs(prev_voltage - Ch2Vlow) > 1e-6)
                {
                    // Transition to low first (if needed)
                    ch2_startv[seg_idx] = prev_voltage;
                    ch2_stopv[seg_idx] = Ch2Vlow;
                    ch2_segtime[seg_idx] = Ch2Fall;  // Use fall time for transition to low
                    ch2_ssrctrl[seg_idx] = 1;
                    ch2_segtrigout[seg_idx] = (seg_idx == 0) ? 1 : 0;
                    ch2_meastype[seg_idx] = 0;
                    ch2_measstart[seg_idx] = 0.0;
                    ch2_measstop[seg_idx] = 0.0;
                    seg_idx++;
                }
                
                // Hold at low for spacing duration
                ch2_startv[seg_idx] = Ch2Vlow;
                ch2_stopv[seg_idx] = Ch2Vlow;  // Flat
                ch2_segtime[seg_idx] = Ch2Spacing;
                ch2_ssrctrl[seg_idx] = 1;
                ch2_segtrigout[seg_idx] = (seg_idx == 0) ? 1 : 0;
                ch2_meastype[seg_idx] = 0;
                ch2_measstart[seg_idx] = 0.0;
                ch2_measstop[seg_idx] = 0.0;
                seg_idx++;
                
                prev_voltage = Ch2Vlow;
            }
        }
        
        // Final segment: return to 0V
        if (fabs(prev_voltage) > 1e-6)  // Only add if not already at 0V
        {
            ch2_startv[seg_idx] = prev_voltage;
            ch2_stopv[seg_idx] = 0.0;
            ch2_segtime[seg_idx] = ch2_min_seg_time;  // Minimal time to return to 0V
            ch2_ssrctrl[seg_idx] = 1;  // Relays closed
            ch2_segtrigout[seg_idx] = 0;
            ch2_meastype[seg_idx] = 0;  // No measurement
            ch2_measstart[seg_idx] = 0.0;
            ch2_measstop[seg_idx] = 0.0;
            seg_idx++;
        }
        
        // Update actual segment count
        actual_ch2_segments = seg_idx;
        
        // Validate that at least one segment has segtrigout=1 (required for seg_arb)
        int has_trigger = 0;
        for (i = 0; i < actual_ch2_segments; i++)
        {
            if (ch2_segtrigout[i] == 1)
            {
                has_trigger = 1;
                break;
            }
        }
        if (!has_trigger && actual_ch2_segments > 0)
        {
            if(debug) printf("WARNING: No segment has segtrigout=1, setting first segment to trigger\n");
            ch2_segtrigout[0] = 1;
        }
        
        if(debug) 
        {
            printf("Built %d segments for CH2 binary pattern:\n", actual_ch2_segments);
            printf("  Delay segment: %s\n", (Ch2Delay > ch2_min_seg_time) ? "YES" : "NO");
            printf("  Has trigger segment: %s\n", has_trigger ? "YES" : "NO");
            for (i = 0; i < actual_ch2_segments && i < 10; i++) // Print first 10 segments
            {
                    printf("  Seg %d: %.6g V -> %.6g V, time=%.6g s, trig=%ld\n", 
                           i, ch2_startv[i], ch2_stopv[i], ch2_segtime[i], ch2_segtrigout[i]);
            }
            if (actual_ch2_segments > 10) printf("  ... (showing first 10 segments)\n");
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
        
        // Validate arrays are not NULL before calling seg_arb_sequence
        if (!ch2_startv || !ch2_stopv || !ch2_segtime || !ch2_segtrigout || 
            !ch2_ssrctrl || !ch2_meastype || !ch2_measstart || !ch2_measstop)
        {
            if(debug) 
            {
                printf("ERROR: CH2 segment arrays are NULL!\n");
                printf("  startv=%p, stopv=%p, segtime=%p\n", ch2_startv, ch2_stopv, ch2_segtime);
            }
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
        
        // Validate segment count
        if (actual_ch2_segments < 3 || actual_ch2_segments > 2048)
        {
            if(debug) printf("ERROR: actual_ch2_segments (%d) is invalid (must be 3-2048)\n", actual_ch2_segments);
            free(ch2_startv); free(ch2_stopv); free(ch2_segtime);
            free(ch2_ssrctrl); free(ch2_segtrigout); free(ch2_meastype);
            free(ch2_measstart); free(ch2_measstop);
            return -122;
        }
        
        if(debug) 
        {
            printf("About to call seg_arb_sequence:\n");
            printf("  pulserId=%d\n", pulserId);
            printf("  channel=%d\n", ch2);
            printf("  sequenceNumber=1\n");
            printf("  numSegments=%d\n", actual_ch2_segments);
            printf("  Array pointers valid: %s\n", 
                   (ch2_startv && ch2_stopv && ch2_segtime) ? "YES" : "NO");
            printf("  First segment: startV=%.6g, stopV=%.6g, time=%.6g, trigOut=%ld\n",
                   ch2_startv[0], ch2_stopv[0], ch2_segtime[0], ch2_segtrigout[0]);
            if (actual_ch2_segments > 1)
                printf("  Last segment: startV=%.6g, stopV=%.6g, time=%.6g, trigOut=%ld\n",
                       ch2_startv[actual_ch2_segments-1], ch2_stopv[actual_ch2_segments-1], 
                       ch2_segtime[actual_ch2_segments-1], ch2_segtrigout[actual_ch2_segments-1]);
            fflush(stdout);  // Force output before potentially blocking call
        }
        
        status = seg_arb_sequence(pulserId, ch2, 1, actual_ch2_segments,
                                  ch2_startv, ch2_stopv, ch2_segtime,
                                  ch2_segtrigout, ch2_ssrctrl,
                                  ch2_meastype, ch2_measstart, ch2_measstop);
        
        if(debug) 
        {
            printf("seg_arb_sequence returned: %d\n", status);
            fflush(stdout);
        }
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
            // Free allocated arrays on error
            free(ch2_startv);
            free(ch2_stopv);
            free(ch2_segtime);
            free(ch2_ssrctrl);
            free(ch2_segtrigout);
            free(ch2_meastype);
            free(ch2_measstart);
            free(ch2_measstop);
            return status;
        }
        
        // Configure seg_arb waveform (sequence 1, with specified loop count)
        // Loop count determines how many times the seg_arb sequence repeats
        // Validate Ch2LoopCount before using it
        // Check for NaN, infinity, or invalid values
        if (Ch2LoopCount != Ch2LoopCount || Ch2LoopCount < 1.0)  // NaN check: NaN != NaN is true
        {
            if(debug) 
            {
                if (Ch2LoopCount != Ch2LoopCount)
                    printf("ERROR: Ch2LoopCount is NaN (not a number)\n");
                else if (Ch2LoopCount < 1.0)
                    printf("ERROR: Ch2LoopCount (%.6g) must be >= 1.0\n", Ch2LoopCount);
            }
            // Free allocated arrays on error
            free(ch2_startv);
            free(ch2_stopv);
            free(ch2_segtime);
            free(ch2_ssrctrl);
            free(ch2_segtrigout);
            free(ch2_meastype);
            free(ch2_measstart);
            free(ch2_measstop);
            return -122;
        }
        
        // Check for infinity
        if (Ch2LoopCount > 1e10)
        {
            if(debug) printf("ERROR: Ch2LoopCount (%.6g) is too large (infinity?)\n", Ch2LoopCount);
            free(ch2_startv);
            free(ch2_stopv);
            free(ch2_segtime);
            free(ch2_ssrctrl);
            free(ch2_segtrigout);
            free(ch2_meastype);
            free(ch2_measstart);
            free(ch2_measstop);
            return -122;
        }
        
        // Ensure loop count is valid and at least 1.0
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
        double ch2_total_duration = ch2_total_time * valid_loop_count;
        
        if(debug) 
        {
            printf("CH2 binary pattern timing:\n");
            printf("  One cycle time: %.6g s (sum of %d segment times)\n", ch2_total_time, actual_ch2_segments);
            printf("  Loop count: %.6g (using %.6g)\n", Ch2LoopCount, valid_loop_count);
            printf("  Total CH2 duration: %.6g s\n", ch2_total_duration);
            printf("  CH1 measurement duration: %.6g s (%d pulses @ %.6g s period)\n", 
                   burstCount * period, burstCount, period);
        }
        
        if(debug) 
        {
            printf("Calling seg_arb_waveform:\n");
            printf("  pulserId=%d, channel=%d, numSequences=1\n", pulserId, ch2);
            printf("  seqList[0]=%ld\n", seqList[0]);
            printf("  loopCount[0]=%.6g\n", loopCount[0]);
            printf("  loopCount[0] is valid: %s\n", (loopCount[0] == loopCount[0] && loopCount[0] >= 1.0 && loopCount[0] <= 1e10) ? "YES" : "NO");
            fflush(stdout);  // Force output before potentially blocking call
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
            // Free allocated arrays on error
            free(ch2_startv);
            free(ch2_stopv);
            free(ch2_segtime);
            free(ch2_ssrctrl);
            free(ch2_segtrigout);
            free(ch2_meastype);
            free(ch2_measstart);
            free(ch2_measstop);
            return status;
        }
        
        // Free allocated arrays now (seg_arb_sequence has copied data to hardware)
        free(ch2_startv);
        free(ch2_stopv);
        free(ch2_segtime);
        free(ch2_ssrctrl);
        free(ch2_segtrigout);
        free(ch2_meastype);
        free(ch2_measstart);
        free(ch2_measstop);
        if(debug) printf("Freed CH2 segment arrays\n");
        
        if(debug) 
        {
            printf("CH2 binary pattern configured: %d segments, loop count=%.6g\n", 
                   actual_ch2_segments, valid_loop_count);
        }
    }

    // Set test execute mode to Simple or Advanced
    if (PMUMode ==0)
        TestMode = PULSE_MODE_SIMPLE;
    else
        TestMode = PULSE_MODE_ADVANCED;

    if(debug) printf("About to execute: TestMode=%d, CH1 burstCount=%d, CH2 enabled=%d\n", TestMode, burstCount, Ch2Enable);
    
    // Execute both channels together
    if(debug) printf("Executing pulses (CH1 simple + CH2 seg_arb)...\n");
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
    if (maxSamples > 100000) maxSamples = 100000;  // Maximum buffer size
    
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
    
    // Free patternArray if it was allocated
    if (patternArray != NULL)
    {
        free(patternArray);
    }
    
    if(debug) 
    {
        printf("Extracted %d averaged measurements (one per pulse from 40-80%% window).\n", outputIdx);
        printf("ACraig11_PMU_Waveform_Binary: complete, returning to KXCI\n");
    }

    return 0;
/* USRLIB MODULE END  */
} 		/* End ACraig10_PMU_Waveform_SegArb.c */

