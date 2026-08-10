/* USRLIB MODULE INFORMATION

	MODULE NAME: pmu_laser_smu_stream
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 30
	ARGUMENTS:
		Vforce,	double,	Input,	0.2,	-200,	200
		Ilimit,	double,	Input,	0.0001,	1e-9,	1.0
		mode,	int,	Input,	0,	0,	4
		vhigh,	double,	Input,	5.0,	0.0,	5.0
		vlow,	double,	Input,	0.0,	0.0,	5.0
		rise,	double,	Input,	100e-9,	20e-9,	0.033
		fall,	double,	Input,	100e-9,	20e-9,	0.033
		width,	double,	Input,	10e-6,	40e-9,	40.0
		period,	double,	Input,	100e-6,	120e-9,	40.0
		startPeriod,	double,	Input,	100e-6,	120e-9,	40.0
		endPeriod,	double,	Input,	1e-3,	120e-9,	40.0
		numPulses,	int,	Input,	1,	1,	500
		delayBefore,	double,	Input,	0.0,	0.0,	10.0
		vrange,	double,	Input,	10.0,	5.0,	40.0
		PMU_ID,	char *,	Input,	"PMU1",	,
		ClariusDebug,	int,	Input,	0,	0,	1
		SampleInterval_s,	double,	Input,	0.05,	0.001,	10.0
		FireNow,	int,	Input,	0,	0,	1
		StopNow,	int,	Input,	0,	0,	1
		SmuPulseNow,	int,	Input,	0,	0,	1
		SmuPulseV,	double,	Input,	2.0,	-200,	200
		SmuPulseWidth,	double,	Input,	0.001,	1e-6,	40.0
		cdStartWidth,	double,	Input,	0.0,	0.0,	40.0
		cdEndWidth,	double,	Input,	0.0,	0.0,	40.0
		cdSequence,	char *,	Input,	"0",	,
		Irange,	double,	Input,	0.0,	0.0,	1.0
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumPoints,	int,	Input,	20,	1,	100000
		Timestamps,	D_ARRAY_T,	Output,	,	,	
		NumPointsTimestamps,	int,	Input,	20,	1,	100000
	INCLUDES:
#include "keithley.h"
#include <stdlib.h>
#include <math.h>
#include <string.h>
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION

pmu_laser_smu_stream — ONE CHUNK of a live/manual-fire PMU CH1 TTL laser +
SMU continuous read loop, driven repeatedly (in a Python loop) over a SINGLE
persistent KXCI/GPIB session.

WHY A "CHUNK" MODULE INSTEAD OF ONE LONG EX CALL:
KXCI/GPIB is strictly one command at a time and synchronous — while an EX
call is executing, the client is blocked and cannot send another command
(e.g. "fire the laser now") until it returns. There is no interrupt/abort
mechanism available here. So true "press a button anytime, mid-measurement"
firing is not possible with a single long EX call.

Instead, the Python side calls this module repeatedly in a tight loop, each
call reading a short chunk (NumPoints samples at SampleInterval_s). Before
each call, Python checks whether the user pressed "Fire Now" and, if so,
sets FireNow=1 for that one call. This module then:
  1. Re-asserts SMU bias (forcev) — REQUIRED every call. Per hardware
     testing (see pmu_laser_smu_run.c), the SMU source does not stay
     "operational" across separate top-level EX/UL invocations, so forcev()
     must immediately precede measi() within the SAME call, every time. Irange (SMU1 current MEASUREMENT range, separate
     from the Ilimit compliance) is re-asserted here too: 0.0 = autorange
     (default/historical behaviour), > 0.0 = fixed range (rangei()) for
     lower-noise/faster, more consistent readings once you know roughly
     what current to expect. Invalid values are silently snapped to the
     nearest hardware range by the LPT driver.
  1b. If SmuPulseNow: apply one SMU voltage pulse (pulsev at SmuPulseV for
     SmuPulseWidth), then forcev back to Vforce (read bias). Use this for
     electrical SET/RESET of the DUT while the live read continues — sign
     of SmuPulseV selects polarity (e.g. +2 V / -2 V).
  2. If FireNow: build + fire the PMU CH1 TTL Segment ARB waveform (same
     single/train/cool-down shapes as pmu_laser_smu_run), then continue
     into this same chunk's sample loop so the transient is caught.
  3. Sample SMU current for NumPoints points at SampleInterval_s.
  4. Return WITHOUT ramping the SMU to 0 V, so the bias stays continuous
     between chunks (no periodic force-down/force-up glitches). The SMU
     is only ramped to 0 V when the caller sends StopNow=1.

SmuPulseNow and FireNow may both be 1 in the same chunk (SMU pulse first,
then laser TTL, then samples).

Fire-button latency = up to one chunk duration (NumPoints * SampleInterval_s)
— i.e. how long Python is blocked waiting on the CURRENT chunk's EX call
before it can send the next one with FireNow=1. Smaller chunks = lower
latency but more per-chunk GPIB overhead / more frequent tiny bias
re-assert; pick a chunk duration that's a reasonable compromise (e.g.
0.2-1 s) in the GUI.

Timestamps returned are CHUNK-LOCAL (0 .. NumPoints*SampleInterval_s), i.e.
relative to the start of THIS call's sample loop. The Python side keeps a
running master-timeline offset and adds it to each chunk's local timestamps.
If a chunk fired, the pulse happened at chunk-local t=0 (right after bias
re-assert, before this chunk's own samples) — Python already knows the
pulse's exact shape/duration from the waveform preview (same math as the
C segment-time calc), so no extra output is needed to report pulse timing.

Modes (same as pmu_laser_smu_run): 0 = single, 1 = train,
  2 = cool-down linear, 3 = exponential, 4 = quadratic.
  Cool-down (Blu-ray-style under TTL): pulse 0 is a full-Width WRITE
  (identical to single). Pulses 1..N are a dense multipulse cool-down
  tail whose on-time decays cdStartWidth -> cdEndWidth (defaults:
  0.1*width -> MIN_WIDTH=40 ns if <=0), packed at near-minimum legal
  period per pulse. Python plans numPulses / cd* so the cool-down span
  is a chosen % of Width.

StopNow=1: skip everything else, just forcev(SMU1, 0.0) and return 0. Use
this as the final call when the user clicks "Stop streaming" to safely
ramp the SMU down. (All other params are ignored when StopNow=1, but must
still be supplied with valid values for USRLIB argument parsing.)

KNOWN ARTIFACT: because STEP 1 re-asserts forcev()/limiti()/setmode() at
the top of every chunk (required — see STEP 1 comment below), some samples
(observed on GST phase-change films) show a small relaxation transient
right after each re-assert that decays over the rest of the chunk, then
resets at the next chunk boundary — a periodic sawtooth/"triangle" ripple
in Imeas synced exactly to NumPoints, riding on top of the real underlying
drift. Larger NumPoints (Python: bigger "Chunk size (s)") means fewer
re-asserts per unit time and more settling time per chunk, which reduces
both how often it happens and its size relative to the real signal — at
the cost of slower FireNow response (Python side is blocked for the whole
chunk duration). If a real fix is wanted, the likely place is inserting an
untimed settle delay (a few discarded measi() calls or a short Sleep())
between STEP 1's forcev() and STEP 3's timestamped sample loop.

Return codes:
  0     OK
  -1    invalid parameters (SampleInterval_s/NumPoints OR — only checked
        when FireNow=1 — PMU pulse params)
  -2    PMU instrument not in configuration (check PMU_ID vs KCON)
  -3    getinstid failed for PMU_ID
  -4    memory allocation failed
  -5    too many Segment ARB segments (reduce numPulses)
  other RAW LPT status code from limiti/forcev/measi/rpm_config/pg2_init/
        pulse_ranges/pulse_output/seg_arb_sequence/seg_arb_waveform/pulse_exec

No Windows.h in INCLUDES (shared-library conflict). Sleep declared locally.

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <stdlib.h>
#include <math.h>
#include <string.h>

void __stdcall Sleep(unsigned long dwMilliseconds);

#define STREAM_MIN_SEG_TIME   20e-9
#define STREAM_MIN_WIDTH      40e-9
#define STREAM_MAX_SEGMENTS   2048
#define STREAM_MAX_PULSES     500
#define STREAM_MAX_VHIGH      5.0
/* See pmu_laser_smu_run.c — PMU 200 mA range, not RPM 10 mA. */
#define STREAM_TTL_IRANGE     0.2
#define STREAM_TTL_LOAD_OHM   1.0e6

static double stream_clamp_min_seg(double t)
{
    if (t < STREAM_MIN_SEG_TIME)
        return STREAM_MIN_SEG_TIME;
    return t;
}

static void stream_free_seg_arrays(
    double *startv, double *stopv, double *segtime,
    long *ssrctrl, long *segtrigout, long *meastype,
    double *measstart, double *measstop)
{
    if (startv) free(startv);
    if (stopv) free(stopv);
    if (segtime) free(segtime);
    if (ssrctrl) free(ssrctrl);
    if (segtrigout) free(segtrigout);
    if (meastype) free(meastype);
    if (measstart) free(measstart);
    if (measstop) free(measstop);
}

/* Cool-down TAIL per-pulse WIDTH (index i over n cool-down pulses — does
   NOT include the leading write pulse). Defaults: start = 0.1*orig,
   end = MIN_WIDTH. Mirrors waveform.py cooldown_widths(). */
static double stream_cooldown_width(
    int i, int n, double orig, double cdStartWidth, double cdEndWidth, int mode)
{
    double start_w = (cdStartWidth > 0.0) ? cdStartWidth : (0.1 * orig);
    double end_w = (cdEndWidth > 0.0) ? cdEndWidth : STREAM_MIN_WIDTH;
    double f;
    double w;

    if (start_w < STREAM_MIN_WIDTH)
        start_w = STREAM_MIN_WIDTH;
    if (start_w > orig)
        start_w = orig;
    if (end_w > start_w)
        end_w = start_w;
    if (n <= 1)
        return start_w;

    f = (double)i / (double)(n - 1);
    if (mode == 3) /* exponential */
        w = (start_w > 0.0) ? start_w * pow(end_w / start_w, f) : end_w;
    else if (mode == 4) /* quadratic */
        w = start_w + (end_w - start_w) * (f * f);
    else /* linear (mode 2) */
        w = start_w + (end_w - start_w) * f;

    if (w < STREAM_MIN_WIDTH)
        w = STREAM_MIN_WIDTH;
    return w;
}

/* Parse cdSequence "delay:width;delay:width;..." into arrays.
   delays[j] = OFF before cool-down pulse j (after write for j==0).
   widths[j] = on-time of cool-down pulse j.
   Returns number of cool-down pulses (0 if empty / "0"). */
static int stream_parse_cd_sequence(
    const char *seq, double *widths, double *delays, int max_n)
{
    const char *p;
    int n = 0;

    if (!seq || !seq[0])
        return 0;
    if (seq[0] == '0' && seq[1] == '\0')
        return 0;

    p = seq;
    while (*p && n < max_n)
    {
        char *end = NULL;
        double d, w;

        while (*p == ' ' || *p == '\t' || *p == ';')
            p++;
        if (!*p)
            break;
        d = strtod(p, &end);
        if (end == p)
            break;
        p = end;
        if (*p != ':')
            break;
        p++;
        w = strtod(p, &end);
        if (end == p)
            break;
        p = end;
        if (w < STREAM_MIN_WIDTH)
            w = STREAM_MIN_WIDTH;
        if (d < STREAM_MIN_SEG_TIME)
            d = STREAM_MIN_SEG_TIME;
        delays[n] = d;
        widths[n] = w;
        n++;
        if (*p == ';')
            p++;
    }
    return n;
}

/* Append one segment; returns 0 on success, -5 if full. */
static int stream_add_seg(
    int *idx, int max_n,
    double *startv, double *stopv, double *segtime,
    long *ssrctrl, long *segtrigout, long *meastype,
    double *measstart, double *measstop,
    double v0, double v1, double t, int trig)
{
    int i;
    if (*idx >= max_n)
        return -5;
    i = *idx;
    startv[i] = v0;
    stopv[i] = v1;
    segtime[i] = stream_clamp_min_seg(t);
    ssrctrl[i] = 1;
    segtrigout[i] = trig ? 1 : 0;
    meastype[i] = PULSE_MEAS_NONE;
    measstart[i] = 0.0;
    measstop[i] = 0.0;
    (*idx)++;
    return 0;
}

/* Build + fire the PMU CH1 TTL Segment ARB waveform (single/train/cool-down),
   identical shape math to pmu_laser_smu_run.c. Returns 0 on success, or a
   negative/raw-LPT error code on failure. SMU is NOT touched here. */
static int stream_fire_pmu(
    int mode, double vhigh, double vlow, double rise, double fall,
    double width, double period, double startPeriod, double endPeriod,
    int numPulses, double delayBefore, double vrange,
    double cdStartWidth, double cdEndWidth, char *cdSequence,
    char *PMU_ID, int debug)
{
    int status;
    int pulserId;
    int chan = 1;
    int ch2 = 2;
    int i;
    int n_pulses;
    int n_seg;
    int idx;
    double rise_t, fall_t, width_t, delay_t;
    double period_t, start_p, end_p;
    double this_width;
    double off_t;
    double total_dur;
    double cd_w[STREAM_MAX_PULSES];
    double cd_d[STREAM_MAX_PULSES];
    int n_cd_seq = 0;
    double *startv = NULL;
    double *stopv = NULL;
    double *segtime = NULL;
    long *ssrctrl = NULL;
    long *segtrigout = NULL;
    long *meastype = NULL;
    double *measstart = NULL;
    double *measstop = NULL;
    long seqList[1];
    double loopCount[1];
    double t_status;

    rise_t = stream_clamp_min_seg(rise);
    fall_t = stream_clamp_min_seg(fall);
    width_t = stream_clamp_min_seg(width);
    delay_t = (delayBefore > 0.0) ? delayBefore : 0.0;
    n_pulses = (mode == 0) ? 1 : numPulses;

    if (mode == 1)
    {
        period_t = period;
        if (period_t < (rise_t + width_t + fall_t + STREAM_MIN_SEG_TIME))
            period_t = rise_t + width_t + fall_t + STREAM_MIN_SEG_TIME;
    }
    else if (mode >= 2)
    {
        /* Explicit cool-down sequence: write + (width:delay) pairs from cdSequence.
           Legacy cdStartWidth/cdEndWidth/startPeriod/endPeriod ignored for shape. */
        (void)cdStartWidth;
        (void)cdEndWidth;
        (void)startPeriod;
        (void)endPeriod;
        n_cd_seq = stream_parse_cd_sequence(cdSequence, cd_w, cd_d, STREAM_MAX_PULSES - 1);
        n_pulses = 1 + n_cd_seq;
        start_p = rise_t + width_t + fall_t + STREAM_MIN_SEG_TIME;
        end_p = start_p;
    }
    else
    {
        period_t = rise_t + width_t + fall_t + STREAM_MIN_SEG_TIME;
        start_p = period_t;
        end_p = period_t;
    }

    n_seg = 1 + (n_pulses * 4) + 1;
    if (n_seg > STREAM_MAX_SEGMENTS)
        return -5;

    if (!LPTIsInCurrentConfiguration(PMU_ID))
    {
        if (debug)
            printf("Instrument %s not in configuration\n", PMU_ID);
        return -2;
    }

    getinstid(PMU_ID, &pulserId);
    if (pulserId == -1)
        return -3;

    startv = (double *)calloc(n_seg, sizeof(double));
    stopv = (double *)calloc(n_seg, sizeof(double));
    segtime = (double *)calloc(n_seg, sizeof(double));
    ssrctrl = (long *)calloc(n_seg, sizeof(long));
    segtrigout = (long *)calloc(n_seg, sizeof(long));
    meastype = (long *)calloc(n_seg, sizeof(long));
    measstart = (double *)calloc(n_seg, sizeof(double));
    measstop = (double *)calloc(n_seg, sizeof(double));
    if (!startv || !stopv || !segtime || !ssrctrl || !segtrigout ||
        !meastype || !measstart || !measstop)
    {
        stream_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                                meastype, measstart, measstop);
        return -4;
    }

    idx = 0;
    if (stream_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                        meastype, measstart, measstop,
                        vlow, vlow,
                        (delay_t > 0.0) ? delay_t : STREAM_MIN_SEG_TIME,
                        1) != 0)
    {
        stream_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                                meastype, measstart, measstop);
        return -5;
    }

    total_dur = (delay_t > 0.0) ? delay_t : STREAM_MIN_SEG_TIME;

    for (i = 0; i < n_pulses; i++)
    {
        if (mode >= 2)
        {
            /* Pulse 0 = write; first delay = gap after write. */
            if (i == 0)
            {
                this_width = width_t;
                off_t = (n_cd_seq > 0) ? cd_d[0] : STREAM_MIN_SEG_TIME;
            }
            else
            {
                int j = i - 1;
                this_width = cd_w[j];
                if (this_width < STREAM_MIN_WIDTH)
                    this_width = STREAM_MIN_WIDTH;
                if (j + 1 < n_cd_seq)
                    off_t = cd_d[j + 1];
                else
                    off_t = STREAM_MIN_SEG_TIME;
                if (off_t < STREAM_MIN_SEG_TIME)
                    off_t = STREAM_MIN_SEG_TIME;
            }
        }
        else if (mode == 1)
        {
            this_width = width_t;
            off_t = period_t - (rise_t + this_width + fall_t);
            if (off_t < STREAM_MIN_SEG_TIME)
                off_t = STREAM_MIN_SEG_TIME;
        }
        else
        {
            this_width = width_t;
            off_t = STREAM_MIN_SEG_TIME;
        }

        if (stream_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                            meastype, measstart, measstop,
                            vlow, vhigh, rise_t, 0) != 0)
            goto stream_seg_overflow;
        if (stream_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                            meastype, measstart, measstop,
                            vhigh, vhigh, this_width, 0) != 0)
            goto stream_seg_overflow;
        if (stream_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                            meastype, measstart, measstop,
                            vhigh, vlow, fall_t, 0) != 0)
            goto stream_seg_overflow;
        if (stream_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                            meastype, measstart, measstop,
                            vlow, vlow, off_t, 0) != 0)
            goto stream_seg_overflow;

        total_dur += rise_t + this_width + fall_t + off_t;
    }

    if (stream_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                        meastype, measstart, measstop,
                        vlow, 0.0, STREAM_MIN_SEG_TIME, 0) != 0)
        goto stream_seg_overflow;
    total_dur += STREAM_MIN_SEG_TIME;

    if (debug)
        printf("stream_fire_pmu: %d segments, total duration ~= %.6g s\n", idx, total_dur);

    status = rpm_config(pulserId, chan, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if (status && debug)
        printf("rpm_config CH1: %d\n", status);

    status = pg2_init(pulserId, PULSE_MODE_SARB);
    if (status)
    {
        stream_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                                meastype, measstart, measstop);
        return status;
    }

    status = pulse_load(pulserId, chan, STREAM_TTL_LOAD_OHM);
    if (status && debug)
        printf("pulse_load CH1: %d\n", status);

    status = pulse_ranges(pulserId, chan, vrange, PULSE_MEAS_FIXED, vrange,
                          PULSE_MEAS_FIXED, STREAM_TTL_IRANGE);
    if (status && debug)
        printf("pulse_ranges CH1 (irange=%.3g): %d\n", STREAM_TTL_IRANGE, status);

    status = pulse_burst_count(pulserId, chan, 1);
    if (status && debug)
        printf("pulse_burst_count CH1: %d\n", status);

    status = pulse_output(pulserId, chan, 1);
    if (status)
    {
        stream_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                                meastype, measstart, measstop);
        return status;
    }

    status = seg_arb_sequence(pulserId, chan, 1, idx,
                               startv, stopv, segtime,
                               segtrigout, ssrctrl,
                               meastype, measstart, measstop);
    if (status)
    {
        stream_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                                meastype, measstart, measstop);
        return status;
    }

    seqList[0] = 1;
    loopCount[0] = 1.0;
    status = seg_arb_waveform(pulserId, chan, 1, seqList, loopCount);
    if (status)
    {
        stream_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                                meastype, measstart, measstop);
        return status;
    }

    stream_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                            meastype, measstart, measstop);
    startv = stopv = segtime = NULL;
    ssrctrl = segtrigout = meastype = NULL;
    measstart = measstop = NULL;

    /* Hold CH2 at 0 V for matching duration (some chassis require both
       channels). CH2 is left physically unconnected -- software-only. */
    {
        double ch2_startv[3], ch2_stopv[3], ch2_segtime[3];
        double ch2_measstart[3], ch2_measstop[3];
        long ch2_ssr[3], ch2_trig[3], ch2_meas[3];
        long ch2_seq[1];
        double ch2_loop[1];
        double hold = (total_dur > STREAM_MIN_SEG_TIME) ? total_dur : STREAM_MIN_SEG_TIME;

        rpm_config(pulserId, ch2, KI_RPM_PATHWAY, KI_RPM_PULSE);
        pulse_load(pulserId, ch2, STREAM_TTL_LOAD_OHM);
        pulse_ranges(pulserId, ch2, vrange, PULSE_MEAS_FIXED, vrange,
                     PULSE_MEAS_FIXED, STREAM_TTL_IRANGE);
        pulse_burst_count(pulserId, ch2, 1);
        pulse_output(pulserId, ch2, 1);

        ch2_startv[0] = 0.0; ch2_stopv[0] = 0.0; ch2_segtime[0] = hold;
        ch2_ssr[0] = 1; ch2_trig[0] = 1; ch2_meas[0] = PULSE_MEAS_NONE;
        ch2_measstart[0] = 0.0; ch2_measstop[0] = 0.0;

        ch2_startv[1] = 0.0; ch2_stopv[1] = 0.0; ch2_segtime[1] = STREAM_MIN_SEG_TIME;
        ch2_ssr[1] = 1; ch2_trig[1] = 0; ch2_meas[1] = PULSE_MEAS_NONE;
        ch2_measstart[1] = 0.0; ch2_measstop[1] = 0.0;

        ch2_startv[2] = 0.0; ch2_stopv[2] = 0.0; ch2_segtime[2] = STREAM_MIN_SEG_TIME;
        ch2_ssr[2] = 1; ch2_trig[2] = 0; ch2_meas[2] = PULSE_MEAS_NONE;
        ch2_measstart[2] = 0.0; ch2_measstop[2] = 0.0;

        status = seg_arb_sequence(pulserId, ch2, 1, 3,
                                   ch2_startv, ch2_stopv, ch2_segtime,
                                   ch2_trig, ch2_ssr,
                                   ch2_meas, ch2_measstart, ch2_measstop);
        if (status == 0)
        {
            ch2_seq[0] = 1;
            ch2_loop[0] = 1.0;
            seg_arb_waveform(pulserId, ch2, 1, ch2_seq, ch2_loop);
        }
    }

    status = pulse_exec(PULSE_MODE_SIMPLE);
    if (status)
    {
        pulse_output(pulserId, chan, 0);
        pulse_output(pulserId, ch2, 0);
        return status;
    }

    i = 0;
    while (pulse_exec_status(&t_status) == 1 && i < 60000)
    {
        Sleep(1);
        i++;
    }

    pulse_output(pulserId, chan, 0);
    pulse_output(pulserId, ch2, 0);
    return 0;

stream_seg_overflow:
    stream_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                            meastype, measstart, measstop);
    return -5;
}

/* USRLIB MODULE MAIN FUNCTION */
int pmu_laser_smu_stream(
    double Vforce,
    double Ilimit,
    int mode,
    double vhigh,
    double vlow,
    double rise,
    double fall,
    double width,
    double period,
    double startPeriod,
    double endPeriod,
    int numPulses,
    double delayBefore,
    double vrange,
    char *PMU_ID,
    int ClariusDebug,
    double SampleInterval_s,
    int FireNow,
    int StopNow,
    int SmuPulseNow,
    double SmuPulseV,
    double SmuPulseWidth,
    double cdStartWidth,
    double cdEndWidth,
    char *cdSequence,
    double Irange,
    double *Imeas,
    int NumPoints,
    double *Timestamps,
    int NumPointsTimestamps)
{
/* USRLIB MODULE CODE */
    int debug = (ClariusDebug == 1) ? 1 : 0;
    int status;
    int i;
    int delay_ms;

    /* ================= StopNow: ramp SMU to 0 V and return immediately ===== */
    if (StopNow)
    {
        forcev(SMU1, 0.0);
        return 0;
    }

    /* ---- Validate SMU chunk params up front (fail fast) ---- */
    if ( SampleInterval_s < 0.001 )
        SampleInterval_s = 0.001;
    if ( SampleInterval_s > 10.0 )
        return -1;
    if ( NumPoints < 1 || NumPoints > 100000 )
        return -1;
    if ( NumPointsTimestamps < 1 || NumPointsTimestamps > 100000 )
        return -1;
    if ( NumPointsTimestamps != NumPoints )
        return -1;

    /* ---- Validate SMU set/reset pulse params only if pulsing ---- */
    if (SmuPulseNow)
    {
        if (SmuPulseWidth < 1e-6 || SmuPulseWidth > 40.0)
            return -1;
        if (SmuPulseV < -200.0 || SmuPulseV > 200.0)
            return -1;
    }

    /* ---- Validate PMU pulse params only if we're actually firing ---- */
    if (FireNow)
    {
        if (mode < 0 || mode > 4)
            return -1;
        if (vhigh < 0.0 || vhigh > STREAM_MAX_VHIGH)
            return -1;
        if (numPulses < 1 || numPulses > STREAM_MAX_PULSES)
            return -1;
        if (width < 40e-9)
            return -1;
        if (rise < STREAM_MIN_SEG_TIME || fall < STREAM_MIN_SEG_TIME)
            return -1;
    }

    if (debug)
        printf("\npmu_laser_smu_stream: Vforce=%.4g FireNow=%d SmuPulseNow=%d NumPoints=%d\n",
               Vforce, FireNow, SmuPulseNow, NumPoints);

    /* ================= STEP 1: re-assert SMU bias (every call, required) === */
    status = limiti(SMU1, Ilimit);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return status;
    }

    /* Irange = 0.0 -> autorange (rangei's own convention); Irange > 0.0 ->
       fixed measurement range. Non-fatal: an unsupported value just snaps
       to the nearest hardware range rather than failing the whole chunk. */
    status = rangei(SMU1, Irange);
    (void)status; /* non-fatal */

    status = setmode(SMU1, KI_INTGPLC, 0.01);
    (void)status; /* non-fatal */

    status = forcev(SMU1, Vforce);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return status;
    }

    /* ================= STEP 1b: optional SMU set/reset voltage pulse ======== */
    if (SmuPulseNow)
    {
        if (debug)
            printf("SmuPulse: %.4g V for %.6g s, then back to Vforce=%.4g\n",
                   SmuPulseV, SmuPulseWidth, Vforce);
        /* pulsev holds Amplitude for Width; SMU stays at Amplitude after. */
        status = pulsev(SMU1, SmuPulseV, SmuPulseWidth);
        if (status != 0)
            return status;
        status = forcev(SMU1, Vforce);
        if (status != 0)
            return status;
    }

    /* ================= STEP 2: fire PMU CH1 TTL pulse, if requested ========= */
    if (FireNow)
    {
        status = stream_fire_pmu(mode, vhigh, vlow, rise, fall, width, period,
                                  startPeriod, endPeriod, numPulses, delayBefore,
                                  vrange, cdStartWidth, cdEndWidth, cdSequence,
                                  PMU_ID, debug);
        if (status != 0)
        {
            /* Leave SMU biased (don't ramp down) so streaming can continue;
               caller will see the error and can decide what to do. */
            return status;
        }
    }

    /* ================= STEP 3: sample this chunk (source stays operational,
       since forcev() above was in THIS SAME call) ============================ */
    delay_ms = (int)(SampleInterval_s * 1000.0 + 0.5);
    if ( delay_ms < 1 ) delay_ms = 1;

    for ( i = 0; i < NumPoints; i++ )
    {
        Imeas[i] = 0.0;
        Timestamps[i] = 0.0;
    }

    for ( i = 0; i < NumPoints; i++ )
    {
        Sleep( (unsigned long)delay_ms );
        /* Chunk-local timestamp; Python adds a running master-timeline offset. */
        Timestamps[i] = ( (double)(i + 1) ) * SampleInterval_s;

        status = measi(SMU1, &Imeas[i]);
        if ( status != 0 )
        {
            /* Leave SMU biased; caller decides whether to retry/stop. */
            return status;
        }
    }

    /* Deliberately NOT ramping SMU to 0 V here -- bias stays continuous
       between chunks. Caller sends StopNow=1 to ramp down when done. */
    if (debug)
        printf("pmu_laser_smu_stream: chunk done\n");
    return 0;

/* USRLIB MODULE END  */
}
