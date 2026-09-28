/* USRLIB MODULE INFORMATION

	MODULE NAME: pmu_laser_smu_run
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 27
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
		Duration_s,	double,	Input,	10.0,	0.001,	3600
		SampleInterval_s,	double,	Input,	0.02,	0.001,	10.0
		NumPrePoints,	int,	Input,	0,	0,	100000
		cdStartWidth,	double,	Input,	0.0,	0.0,	40.0
		cdEndWidth,	double,	Input,	0.0,	0.0,	40.0
		cdSequence,	char *,	Input,	"0",	,
		Irange,	double,	Input,	0.0,	0.0,	1.0
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumPoints,	int,	Input,	500,	1,	100000
		Timestamps,	D_ARRAY_T,	Output,	,	,	
		NumPointsTimestamps,	int,	Input,	500,	1,	100000
	INCLUDES:
#include "keithley.h"
#include <stdlib.h>
#include <math.h>
#include <string.h>
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION

pmu_laser_smu_run — SMU bias + PMU CH1 TTL laser pulse + SMU timed read, ALL
IN ONE EX CALL.

WHY THIS MODULE EXISTS (root cause of prior failures):
Splitting this test into three separate EX calls (pmu_laser_smu_start ->
pmu_ttl_laser_ch1 -> pmu_laser_smu_collect) failed on hardware with measi()
returning LPT error -160 ("Measurement cannot be performed because the
source is not operational"). Each top-level EX/UL invocation from KXCI is
its own execution context; the SMU's forcev() from Start did not remain
"operational" once that EX call returned and a separate EX call began. This
module inlines all three steps (bias -> pulse -> measure -> ramp down) into
ONE continuous C function / ONE EX call so the SMU source is never torn
down between operations.

Sequence (all inline, one call):
  1. limiti(SMU1, Ilimit); rangei(SMU1, Irange); setmode(SMU1, KI_INTGPLC, 0.01);
     forcev(SMU1, Vforce)
  2. Sample NumPrePoints BASELINE points at SampleInterval_s (laser still off)
  3. Build + fire PMU CH1 Segment ARB TTL waveform (single/train/cool-down),
     via RPM pathway KI_RPM_PULSE (CH2 held at 0V, physically unconnected).
     Drive: pulse_load(1e6) + pulse_ranges(..., irange=0.2) so the PMU
     200 mA path is used — not the RPM 10 mA range (which sags under load).
  4. Sample (NumPoints - NumPrePoints) more points at SampleInterval_s
  5. forcev(SMU1, 0.0) to leave the output safe

Timestamps convention: t = 0 is the instant the PMU fire step begins (i.e.
the same t = 0 reference used by the waveform preview / laser_on_intervals
on the Python side, so no extra shift is needed there). Pre-pulse baseline
samples get NEGATIVE timestamps counting back from t = 0; post-pulse
samples get POSITIVE timestamps starting at +SampleInterval_s. Imeas /
Timestamps are ONE combined array of length NumPoints: indices
[0, NumPrePoints) are the pre-pulse baseline, indices
[NumPrePoints, NumPoints) are the post-pulse read.

Modes (same as pmu_ttl_laser_ch1):
  0 = single pulse, 1 = pulse train
  2 = cool-down linear, 3 = exponential, 4 = quadratic
  Cool-down (Blu-ray-style under TTL): pulse 0 is a full-Width WRITE
  (identical to single). Pulses 1..N are a dense multipulse cool-down
  tail whose on-time decays cdStartWidth -> cdEndWidth (defaults:
  0.1*width -> MIN_WIDTH=40 ns if <=0), packed at near-minimum legal
  period per pulse. Python plans numPulses / cd* so the cool-down span
  is a chosen % of Width.

Irange: SMU1 current MEASUREMENT range (separate from Ilimit, the compliance
limit). Irange = 0.0 -> autorange (instrument picks a range per reading,
the historical/default behaviour). Irange > 0.0 -> fixed range (rangei()),
which gives lower-noise / faster, more consistent readings once you know
roughly what current to expect, at the cost of clipping if the real
current exceeds that range. Invalid/unsupported values are silently
snapped to the nearest hardware range by the LPT driver.

Return codes:
  0     OK
  -1    invalid parameters (SMU collect params OR PMU pulse params)
  -2    PMU instrument not in configuration (check PMU_ID vs KCON)
  -3    getinstid failed for PMU_ID
  -4    memory allocation failed
  -5    too many Segment ARB segments (reduce numPulses)
  other RAW LPT status code from limiti/forcev/measi/rpm_config/pg2_init/
        pulse_ranges/pulse_output/seg_arb_sequence/seg_arb_waveform/pulse_exec
        — look it up in the Keithley LPT Library reference (kiXXXX / error
        code table) to see exactly what failed.

No Windows.h in INCLUDES (shared-library conflict). Sleep declared locally.
Timestamps are synthetic: (i+1)*SampleInterval_s.

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <stdlib.h>
#include <math.h>

void __stdcall Sleep(unsigned long dwMilliseconds);

#define RUN_MIN_SEG_TIME   20e-9
#define RUN_MIN_WIDTH      40e-9
#define RUN_MAX_SEGMENTS   2048
#define RUN_MAX_PULSES     500
#define RUN_MAX_VHIGH      5.0

/* TTL drive: use PMU 10V 200 mA range (0.2), NOT RPM max 10 mA (0.01).
   RPM 10 mA + ~50 ohm source Z sags Vpeak into many laser TTL/MOD inputs
   while a 1 Mohm scope probe still shows a "good looking" pulse. */
#define RUN_TTL_IRANGE     0.2
#define RUN_TTL_LOAD_OHM   1.0e6

static double run_clamp_min_seg(double t)
{
    if (t < RUN_MIN_SEG_TIME)
        return RUN_MIN_SEG_TIME;
    return t;
}

static void run_free_seg_arrays(
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
static double run_cooldown_width(
    int i, int n, double orig, double cdStartWidth, double cdEndWidth, int mode)
{
    double start_w = (cdStartWidth > 0.0) ? cdStartWidth : (0.1 * orig);
    double end_w = (cdEndWidth > 0.0) ? cdEndWidth : RUN_MIN_WIDTH;
    double f;
    double w;

    if (start_w < RUN_MIN_WIDTH)
        start_w = RUN_MIN_WIDTH;
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

    if (w < RUN_MIN_WIDTH)
        w = RUN_MIN_WIDTH;
    return w;
}

/* Parse cdSequence "delay:width;delay:width;..." into arrays.
   delays[j] = OFF before cool-down pulse j (after write for j==0).
   widths[j] = on-time of cool-down pulse j.
   Returns number of cool-down pulses (0 if empty / "0"). */
static int run_parse_cd_sequence(
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
        if (w < RUN_MIN_WIDTH)
            w = RUN_MIN_WIDTH;
        if (d < RUN_MIN_SEG_TIME)
            d = RUN_MIN_SEG_TIME;
        delays[n] = d;
        widths[n] = w;
        n++;
        if (*p == ';')
            p++;
    }
    return n;
}

/* Append one segment; returns 0 on success, -5 if full. */
static int run_add_seg(
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
    segtime[i] = run_clamp_min_seg(t);
    ssrctrl[i] = 1;
    segtrigout[i] = trig ? 1 : 0;
    meastype[i] = PULSE_MEAS_NONE;
    measstart[i] = 0.0;
    measstop[i] = 0.0;
    (*idx)++;
    return 0;
}

/* USRLIB MODULE MAIN FUNCTION */
int pmu_laser_smu_run(
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
    double Duration_s,
    double SampleInterval_s,
    int NumPrePoints,
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
    double cd_w[RUN_MAX_PULSES];
    double cd_d[RUN_MAX_PULSES];
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
    int delay_ms;

    (void)Duration_s;

    /* ---- Validate SMU collect params up front (fail fast, no hardware touched) ---- */
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
    if ( NumPrePoints < 0 || NumPrePoints > NumPoints )
        return -1;

    /* ---- Validate PMU pulse params up front ---- */
    if (mode < 0 || mode > 4)
        return -1;
    if (vhigh < 0.0 || vhigh > RUN_MAX_VHIGH)
        return -1;
    if (numPulses < 1 || numPulses > RUN_MAX_PULSES)
        return -1;
    if (width < 40e-9)
        return -1;
    if (rise < RUN_MIN_SEG_TIME || fall < RUN_MIN_SEG_TIME)
        return -1;

    if (debug)
        printf("\npmu_laser_smu_run: Vforce=%.4g Ilimit=%.4g mode=%d vhigh=%.4g width=%.4g\n",
               Vforce, Ilimit, mode, vhigh, width);

    /* ================= STEP 1: SMU bias ON (stays on for the whole call) ================= */
    status = limiti(SMU1, Ilimit);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return status;
    }

    /* Irange = 0.0 -> autorange (rangei's own convention); Irange > 0.0 ->
       fixed measurement range. Non-fatal: an unsupported value just snaps
       to the nearest hardware range rather than failing the whole run. */
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

    /* ================= STEP 2: pre-pulse SMU baseline samples (laser still off) ============ */
    delay_ms = (int)(SampleInterval_s * 1000.0 + 0.5);
    if ( delay_ms < 1 ) delay_ms = 1;

    for ( i = 0; i < NumPoints; i++ )
    {
        Imeas[i] = 0.0;
        Timestamps[i] = 0.0;
    }

    for ( i = 0; i < NumPrePoints; i++ )
    {
        Sleep( (unsigned long)delay_ms );
        /* Negative timestamps counting back to t=0 (laser fire instant) */
        Timestamps[i] = -((double)(NumPrePoints - i)) * SampleInterval_s;

        status = measi(SMU1, &Imeas[i]);
        if ( status != 0 )
        {
            forcev(SMU1, 0.0);
            return status;
        }
    }

    if (debug)
        printf("pmu_laser_smu_run: %d baseline samples done, firing PMU\n", NumPrePoints);

    /* ================= STEP 3: build + fire PMU CH1 TTL Segment ARB ================= */
    rise_t = run_clamp_min_seg(rise);
    fall_t = run_clamp_min_seg(fall);
    width_t = run_clamp_min_seg(width);
    delay_t = (delayBefore > 0.0) ? delayBefore : 0.0;
    n_pulses = (mode == 0) ? 1 : numPulses;

    if (mode == 1)
    {
        period_t = period;
        if (period_t < (rise_t + width_t + fall_t + RUN_MIN_SEG_TIME))
            period_t = rise_t + width_t + fall_t + RUN_MIN_SEG_TIME;
    }
    else if (mode >= 2)
    {
        /* Explicit cool-down sequence: write + (width:delay) pairs from cdSequence.
           Legacy cdStartWidth/cdEndWidth/startPeriod/endPeriod ignored for shape. */
        (void)cdStartWidth;
        (void)cdEndWidth;
        (void)startPeriod;
        (void)endPeriod;
        n_cd_seq = run_parse_cd_sequence(cdSequence, cd_w, cd_d, RUN_MAX_PULSES - 1);
        n_pulses = 1 + n_cd_seq;
        start_p = rise_t + width_t + fall_t + RUN_MIN_SEG_TIME;
        end_p = start_p;
    }
    else
    {
        period_t = rise_t + width_t + fall_t + RUN_MIN_SEG_TIME;
        start_p = period_t;
        end_p = period_t;
    }

    n_seg = 1 + (n_pulses * 4) + 1; /* pre-delay + 4*n + final */
    if (n_seg > RUN_MAX_SEGMENTS)
    {
        forcev(SMU1, 0.0);
        return -5;
    }

    if (!LPTIsInCurrentConfiguration(PMU_ID))
    {
        if (debug)
            printf("Instrument %s not in configuration\n", PMU_ID);
        forcev(SMU1, 0.0);
        return -2;
    }

    getinstid(PMU_ID, &pulserId);
    if (pulserId == -1)
    {
        forcev(SMU1, 0.0);
        return -3;
    }

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
        run_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                             meastype, measstart, measstop);
        forcev(SMU1, 0.0);
        return -4;
    }

    idx = 0;
    if (run_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                     meastype, measstart, measstop,
                     vlow, vlow,
                     (delay_t > 0.0) ? delay_t : RUN_MIN_SEG_TIME,
                     1) != 0)
    {
        run_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                             meastype, measstart, measstop);
        forcev(SMU1, 0.0);
        return -5;
    }

    total_dur = (delay_t > 0.0) ? delay_t : RUN_MIN_SEG_TIME;

    for (i = 0; i < n_pulses; i++)
    {
        if (mode >= 2)
        {
            /* Pulse 0 = write; offs[0] = first sequence delay (gap after write).
               Then each cool-down pulse; trailing OFF = next delay (or min). */
            if (i == 0)
            {
                this_width = width_t;
                off_t = (n_cd_seq > 0) ? cd_d[0] : RUN_MIN_SEG_TIME;
            }
            else
            {
                int j = i - 1;
                this_width = cd_w[j];
                if (this_width < RUN_MIN_WIDTH)
                    this_width = RUN_MIN_WIDTH;
                if (j + 1 < n_cd_seq)
                    off_t = cd_d[j + 1];
                else
                    off_t = RUN_MIN_SEG_TIME;
                if (off_t < RUN_MIN_SEG_TIME)
                    off_t = RUN_MIN_SEG_TIME;
            }
        }
        else if (mode == 1)
        {
            this_width = width_t;
            off_t = period_t - (rise_t + this_width + fall_t);
            if (off_t < RUN_MIN_SEG_TIME)
                off_t = RUN_MIN_SEG_TIME;
        }
        else
        {
            this_width = width_t;
            off_t = RUN_MIN_SEG_TIME;
        }

        if (run_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                         meastype, measstart, measstop,
                         vlow, vhigh, rise_t, 0) != 0)
            goto run_seg_overflow;
        if (run_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                         meastype, measstart, measstop,
                         vhigh, vhigh, this_width, 0) != 0)
            goto run_seg_overflow;
        if (run_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                         meastype, measstart, measstop,
                         vhigh, vlow, fall_t, 0) != 0)
            goto run_seg_overflow;
        if (run_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                         meastype, measstart, measstop,
                         vlow, vlow, off_t, 0) != 0)
            goto run_seg_overflow;

        total_dur += rise_t + this_width + fall_t + off_t;
    }

    if (run_add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                     meastype, measstart, measstop,
                     vlow, 0.0, RUN_MIN_SEG_TIME, 0) != 0)
        goto run_seg_overflow;
    total_dur += RUN_MIN_SEG_TIME;

    if (debug)
        printf("Built %d segments, total duration ~= %.6g s\n", idx, total_dur);

    status = rpm_config(pulserId, chan, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if (status && debug)
        printf("rpm_config CH1: %d\n", status);

    status = pg2_init(pulserId, PULSE_MODE_SARB);
    if (status)
    {
        if (debug)
            printf("pg2_init failed: %d\n", status);
        run_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                             meastype, measstart, measstop);
        forcev(SMU1, 0.0);
        return status;
    }

    /* High-Z load assumption for TTL gate (matches ACraig10 laser CH2).
       Required before seg_arb; does NOT boost into a 50 ohm termination —
       if Vpeak still sags with laser connected, use a TTL buffer. */
    status = pulse_load(pulserId, chan, RUN_TTL_LOAD_OHM);
    if (status && debug)
        printf("pulse_load CH1: %d\n", status);

    status = pulse_ranges(pulserId, chan, vrange, PULSE_MEAS_FIXED, vrange,
                          PULSE_MEAS_FIXED, RUN_TTL_IRANGE);
    if (status && debug)
        printf("pulse_ranges CH1 (irange=%.3g): %d\n", RUN_TTL_IRANGE, status);

    status = pulse_burst_count(pulserId, chan, 1);
    if (status && debug)
        printf("pulse_burst_count CH1: %d\n", status);

    status = pulse_output(pulserId, chan, 1);
    if (status)
    {
        run_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                             meastype, measstart, measstop);
        forcev(SMU1, 0.0);
        return status;
    }

    status = seg_arb_sequence(pulserId, chan, 1, idx,
                               startv, stopv, segtime,
                               segtrigout, ssrctrl,
                               meastype, measstart, measstop);
    if (status)
    {
        if (debug)
            printf("seg_arb_sequence CH1 failed: %d\n", status);
        run_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                             meastype, measstart, measstop);
        forcev(SMU1, 0.0);
        return status;
    }

    seqList[0] = 1;
    loopCount[0] = 1.0;
    status = seg_arb_waveform(pulserId, chan, 1, seqList, loopCount);
    if (status)
    {
        run_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                             meastype, measstart, measstop);
        forcev(SMU1, 0.0);
        return status;
    }

    run_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                         meastype, measstart, measstop);
    startv = stopv = segtime = NULL;
    ssrctrl = segtrigout = meastype = NULL;
    measstart = measstop = NULL;

    /* Hold CH2 at 0 V for matching duration (some chassis require both channels).
       CH2 is left physically unconnected -- this is software-only bookkeeping. */
    {
        double ch2_startv[3], ch2_stopv[3], ch2_segtime[3];
        double ch2_measstart[3], ch2_measstop[3];
        long ch2_ssr[3], ch2_trig[3], ch2_meas[3];
        long ch2_seq[1];
        double ch2_loop[1];
        double hold = (total_dur > RUN_MIN_SEG_TIME) ? total_dur : RUN_MIN_SEG_TIME;

        rpm_config(pulserId, ch2, KI_RPM_PATHWAY, KI_RPM_PULSE);
        pulse_load(pulserId, ch2, RUN_TTL_LOAD_OHM);
        pulse_ranges(pulserId, ch2, vrange, PULSE_MEAS_FIXED, vrange,
                     PULSE_MEAS_FIXED, RUN_TTL_IRANGE);
        pulse_burst_count(pulserId, ch2, 1);
        pulse_output(pulserId, ch2, 1);

        ch2_startv[0] = 0.0; ch2_stopv[0] = 0.0; ch2_segtime[0] = hold;
        ch2_ssr[0] = 1; ch2_trig[0] = 1; ch2_meas[0] = PULSE_MEAS_NONE;
        ch2_measstart[0] = 0.0; ch2_measstop[0] = 0.0;

        ch2_startv[1] = 0.0; ch2_stopv[1] = 0.0; ch2_segtime[1] = RUN_MIN_SEG_TIME;
        ch2_ssr[1] = 1; ch2_trig[1] = 0; ch2_meas[1] = PULSE_MEAS_NONE;
        ch2_measstart[1] = 0.0; ch2_measstop[1] = 0.0;

        ch2_startv[2] = 0.0; ch2_stopv[2] = 0.0; ch2_segtime[2] = RUN_MIN_SEG_TIME;
        ch2_ssr[2] = 1; ch2_trig[2] = 0; ch2_meas[2] = PULSE_MEAS_NONE;
        ch2_measstart[2] = 0.0; ch2_measstop[2] = 0.0;

        status = seg_arb_sequence(pulserId, ch2, 1, 3,
                                   ch2_startv, ch2_stopv, ch2_segtime,
                                   ch2_trig, ch2_ssr,
                                   ch2_meas, ch2_measstart, ch2_measstop);
        if (status && debug)
            printf("seg_arb_sequence CH2 (hold): %d\n", status);
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
        if (debug)
            printf("pulse_exec failed: %d\n", status);
        pulse_output(pulserId, chan, 0);
        pulse_output(pulserId, ch2, 0);
        forcev(SMU1, 0.0);
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

    if (debug)
        printf("pmu_laser_smu_run: PMU pulse done, starting post-pulse SMU sample loop\n");

    /* ================= STEP 4: post-pulse SMU samples (source is still on) ================= */
    for ( i = NumPrePoints; i < NumPoints; i++ )
    {
        Sleep( (unsigned long)delay_ms );
        /* Positive timestamps counting up from t=0 (laser fire instant) */
        Timestamps[i] = ( (double)(i - NumPrePoints + 1) ) * SampleInterval_s;

        status = measi(SMU1, &Imeas[i]);
        if ( status != 0 )
        {
            forcev(SMU1, 0.0);
            return status;
        }
    }

    /* ================= STEP 5: ramp SMU to 0 V ================= */
    status = forcev(SMU1, 0.0);
    if ( status != 0 )
        return status;

    if (debug)
        printf("pmu_laser_smu_run: done\n");
    return 0;

run_seg_overflow:
    run_free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                         meastype, measstart, measstop);
    forcev(SMU1, 0.0);
    return -5;

/* USRLIB MODULE END  */
}
