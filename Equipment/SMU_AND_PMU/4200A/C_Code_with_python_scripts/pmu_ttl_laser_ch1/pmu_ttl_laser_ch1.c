/* USRLIB MODULE INFORMATION

	MODULE NAME: pmu_ttl_laser_ch1
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 16
	ARGUMENTS:
		mode,	int,	Input,	0,	0,	4
		vhigh,	double,	Input,	5.0,	0.0,	5.0
		vlow,	double,	Input,	0.0,	0.0,	5.0
		rise,	double,	Input,	100e-9,	20e-9,	0.033
		fall,	double,	Input,	100e-9,	20e-9,	0.033
		width,	double,	Input,	10e-6,	40e-9,	0.999999
		period,	double,	Input,	100e-6,	120e-9,	1.0
		startPeriod,	double,	Input,	100e-6,	120e-9,	1.0
		endPeriod,	double,	Input,	1e-3,	120e-9,	1.0
		numPulses,	int,	Input,	1,	1,	500
		delayBefore,	double,	Input,	0.0,	0.0,	10.0
		vrange,	double,	Input,	10.0,	5.0,	40.0
		PMU_ID,	char *,	Input,	"PMU1",	,
		ClariusDebug,	int,	Input,	0,	0,	1
		cdStartWidth,	double,	Input,	0.0,	0.0,	0.999999
		cdEndWidth,	double,	Input,	0.0,	0.0,	0.999999
	INCLUDES:
#include "keithley.h"
#include <stdlib.h>
#include <math.h>
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION

pmu_ttl_laser_ch1 — CH1-only TTL laser gate via Segment ARB (KXCI)

Drives PMU channel 1 as a binary TTL gate for an external laser driver.
No measurement on the PMU; pair with SMU BiasTimedRead for resistance.

Modes:
  0 = single pulse   (width + rise/fall; period unused)
  1 = pulse train    (numPulses × width at period)
  2 = cool-down linear      (width AND period ramp start->end)
  3 = cool-down exponential (width/period = start * (end/start)^f)
  4 = cool-down quadratic   (width/period = start + (end-start)*f^2)
  Cool-down: pulse 0 is IDENTICAL to a single/train pulse (width == "width",
  the on-time already known to reach the laser). From pulse 1 onward, BOTH
  the pulse width AND the period taper together from cdStartWidth (default:
  "width" itself, if cdStartWidth <= 0) down to cdEndWidth (default:
  MIN_WIDTH = 40 ns, the true hardware floor, if cdEndWidth <= 0), following
  the selected decay shape — i.e. progressively smaller, more widely spaced
  pulses. Anchoring the taper's start to "width" (instead of a fixed ns-scale
  constant) means pulse count/width/spacing all scale with whatever "width"
  is set to.

Safety: vhigh must stay within 0..5 V (standard TTL into laser gate).
CH2 is programmed to hold 0 V in software only — leave CH2 physically unconnected.

NOTE: Windows.h is NOT listed in USRLIB INCLUDES (avoids conflicting-types
when this module shares a library with SMU Collect). Sleep is declared below.

Return codes:
  0     OK
  -1    invalid parameters
  -2    instrument not in configuration
  -3    getinstid failed
  -4    memory allocation failed
  -5    too many segments
  other LPT / pulse status codes from pg2_init / seg_arb_* / pulse_exec

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <stdlib.h>
#include <math.h>

void __stdcall Sleep(unsigned long dwMilliseconds);

#define MIN_SEG_TIME   20e-9
#define MIN_WIDTH      40e-9
#define MAX_SEGMENTS   2048
#define MAX_PULSES     500
#define MAX_VHIGH      5.0
/* See pmu_laser_smu_run.c — PMU 200 mA range, not RPM 10 mA. */
#define TTL_IRANGE     0.2
#define TTL_LOAD_OHM   1.0e6

static double clamp_min_seg(double t)
{
    if (t < MIN_SEG_TIME)
        return MIN_SEG_TIME;
    return t;
}

static void free_seg_arrays(
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

/* Cool-down per-pulse WIDTH: pulse 0 == start (the confirmed-working "width"
   by default), tapering down to end (MIN_WIDTH by default) over n pulses,
   following the same start/end interpolation as the period ramp (mode
   2=linear, 3=exponential, 4=quadratic). Mirrors waveform.py's
   cooldown_value_at()/cooldown_widths() exactly so the C-generated train
   matches the Python-side preview. */
static double ttl_cooldown_width(
    int i, int n, double orig, double cdStartWidth, double cdEndWidth, int mode)
{
    double start_w = (cdStartWidth > 0.0) ? cdStartWidth : orig;
    double end_w = (cdEndWidth > 0.0) ? cdEndWidth : MIN_WIDTH;
    double f;
    double w;

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

    if (w < MIN_WIDTH)
        w = MIN_WIDTH;
    return w;
}

/* Append one segment; returns 0 on success, -5 if full. */
static int add_seg(
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
    segtime[i] = clamp_min_seg(t);
    ssrctrl[i] = 1;
    segtrigout[i] = trig ? 1 : 0;
    meastype[i] = PULSE_MEAS_NONE;
    measstart[i] = 0.0;
    measstop[i] = 0.0;
    (*idx)++;
    return 0;
}

/* USRLIB MODULE MAIN FUNCTION */
int pmu_ttl_laser_ch1(
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
    double cdStartWidth,
    double cdEndWidth)
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

    if (debug)
        printf("\npmu_ttl_laser_ch1: start mode=%d vhigh=%.4g width=%.4g\n",
               mode, vhigh, width);

    if (mode < 0 || mode > 4)
        return -1;
    if (vhigh < 0.0 || vhigh > MAX_VHIGH)
        return -1;
    if (numPulses < 1)
        return -1;
    if (numPulses > MAX_PULSES)
        return -1;
    if (width < MIN_WIDTH)
        return -1;
    if (rise < MIN_SEG_TIME || fall < MIN_SEG_TIME)
        return -1;

    rise_t = clamp_min_seg(rise);
    fall_t = clamp_min_seg(fall);
    width_t = clamp_min_seg(width);
    delay_t = (delayBefore > 0.0) ? delayBefore : 0.0;
    n_pulses = (mode == 0) ? 1 : numPulses;

    if (mode == 1)
    {
        period_t = period;
        if (period_t < (rise_t + width_t + fall_t + MIN_SEG_TIME))
            period_t = rise_t + width_t + fall_t + MIN_SEG_TIME;
    }
    else if (mode >= 2)
    {
        /* Cool-down widths taper cdStartWidth -> cdEndWidth (defaulting to
           width_t -> MIN_WIDTH), NOT a constant width_t — validate
           start_p/end_p against the actual (possibly much smaller) per-
           pulse widths they'll be paired with, not the full "width". */
        double cd_start_w = (cdStartWidth > 0.0) ? cdStartWidth : width_t;
        double cd_end_w = (cdEndWidth > 0.0) ? cdEndWidth : MIN_WIDTH;
        if (cd_end_w > cd_start_w)
            cd_end_w = cd_start_w;
        start_p = startPeriod;
        end_p = endPeriod;
        /* Auto-bump (don't hard-fail): EX args may arrive slightly short of
           the legal minimum after limited-precision formatting on the host. */
        if (start_p < (rise_t + cd_start_w + fall_t + MIN_SEG_TIME))
            start_p = rise_t + cd_start_w + fall_t + MIN_SEG_TIME;
        if (end_p < (rise_t + cd_end_w + fall_t + MIN_SEG_TIME))
            end_p = rise_t + cd_end_w + fall_t + MIN_SEG_TIME;
    }
    else
    {
        period_t = rise_t + width_t + fall_t + MIN_SEG_TIME;
        start_p = period_t;
        end_p = period_t;
    }

    /* Estimate segment count: delay + per pulse (rise+width+fall+off) + final */
    n_seg = 2; /* delay placeholder + final */
    if (delay_t <= 0.0)
        n_seg = 1; /* only final after pulses; delay skipped */
    n_seg = 1 + (n_pulses * 4) + 1; /* pre-delay + 4*n + final */
    if (n_seg > MAX_SEGMENTS)
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
        free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                        meastype, measstart, measstop);
        return -4;
    }

    idx = 0;
    /* Pre-delay at vlow (always at least MIN_SEG so first trig is valid) */
    if (add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                meastype, measstart, measstop,
                vlow, vlow,
                (delay_t > 0.0) ? delay_t : MIN_SEG_TIME,
                1) != 0)
    {
        free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                        meastype, measstart, measstop);
        return -5;
    }

    total_dur = (delay_t > 0.0) ? delay_t : MIN_SEG_TIME;

    for (i = 0; i < n_pulses; i++)
    {
        double this_period;
        if (mode >= 2)
        {
            /* Cool-down: pulse WIDTH tapers cdStartWidth -> cdEndWidth
               (default: width_t -> MIN_WIDTH) in lock-step with the period
               ramp below, so both on-time and off-time shrink/expand
               together over the train — see ttl_cooldown_width(). */
            this_width = ttl_cooldown_width(i, n_pulses, width_t,
                                             cdStartWidth, cdEndWidth, mode);
            if (n_pulses == 1)
                this_period = start_p;
            else
            {
                double f = (double)i / (double)(n_pulses - 1);
                if (mode == 3) /* exponential */
                    this_period = (start_p > 0.0) ? start_p * pow(end_p / start_p, f) : end_p;
                else if (mode == 4) /* quadratic */
                    this_period = start_p + (end_p - start_p) * (f * f);
                else /* linear (mode 2) */
                    this_period = start_p + (end_p - start_p) * f;
            }
        }
        else if (mode == 1)
        {
            this_width = width_t;
            this_period = period_t;
        }
        else
        {
            this_width = width_t;
            this_period = rise_t + width_t + fall_t + MIN_SEG_TIME;
        }

        off_t = this_period - (rise_t + this_width + fall_t);
        if (off_t < MIN_SEG_TIME)
            off_t = MIN_SEG_TIME;

        /* rise */
        if (add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                    meastype, measstart, measstop,
                    vlow, vhigh, rise_t, 0) != 0)
            goto seg_overflow;
        /* width HIGH */
        if (add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                    meastype, measstart, measstop,
                    vhigh, vhigh, this_width, 0) != 0)
            goto seg_overflow;
        /* fall */
        if (add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                    meastype, measstart, measstop,
                    vhigh, vlow, fall_t, 0) != 0)
            goto seg_overflow;
        /* off / expanding gap */
        if (add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                    meastype, measstart, measstop,
                    vlow, vlow, off_t, 0) != 0)
            goto seg_overflow;

        total_dur += rise_t + this_width + fall_t + off_t;
    }

    /* Final settle at 0 V */
    if (add_seg(&idx, n_seg, startv, stopv, segtime, ssrctrl, segtrigout,
                meastype, measstart, measstop,
                vlow, 0.0, MIN_SEG_TIME, 0) != 0)
        goto seg_overflow;
    total_dur += MIN_SEG_TIME;

    if (debug)
        printf("Built %d segments, total duration ≈ %.6g s\n", idx, total_dur);

    status = rpm_config(pulserId, chan, KI_RPM_PATHWAY, KI_RPM_PULSE);
    if (status && debug)
        printf("rpm_config CH1: %d\n", status);

    status = pg2_init(pulserId, PULSE_MODE_SARB);
    if (status)
    {
        if (debug)
            printf("pg2_init failed: %d\n", status);
        free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                        meastype, measstart, measstop);
        return status;
    }

    status = pulse_load(pulserId, chan, TTL_LOAD_OHM);
    if (status && debug)
        printf("pulse_load CH1: %d\n", status);

    status = pulse_ranges(pulserId, chan, vrange, PULSE_MEAS_FIXED, vrange,
                          PULSE_MEAS_FIXED, TTL_IRANGE);
    if (status && debug)
        printf("pulse_ranges CH1 (irange=%.3g): %d\n", TTL_IRANGE, status);

    status = pulse_burst_count(pulserId, chan, 1);
    if (status && debug)
        printf("pulse_burst_count CH1: %d\n", status);

    status = pulse_output(pulserId, chan, 1);
    if (status)
    {
        free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                        meastype, measstart, measstop);
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
        free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                        meastype, measstart, measstop);
        return status;
    }

    seqList[0] = 1;
    loopCount[0] = 1.0;
    status = seg_arb_waveform(pulserId, chan, 1, seqList, loopCount);
    if (status)
    {
        free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                        meastype, measstart, measstop);
        return status;
    }

    free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                    meastype, measstart, measstop);
    startv = stopv = segtime = NULL;
    ssrctrl = segtrigout = meastype = NULL;
    measstart = measstop = NULL;

    /* Hold CH2 at 0 V for matching duration (some chassis require both channels) */
    {
        double ch2_startv[3], ch2_stopv[3], ch2_segtime[3];
        double ch2_measstart[3], ch2_measstop[3];
        long ch2_ssr[3], ch2_trig[3], ch2_meas[3];
        long ch2_seq[1];
        double ch2_loop[1];
        double hold = (total_dur > MIN_SEG_TIME) ? total_dur : MIN_SEG_TIME;

        rpm_config(pulserId, ch2, KI_RPM_PATHWAY, KI_RPM_PULSE);
        pulse_load(pulserId, ch2, TTL_LOAD_OHM);
        pulse_ranges(pulserId, ch2, vrange, PULSE_MEAS_FIXED, vrange,
                     PULSE_MEAS_FIXED, TTL_IRANGE);
        pulse_burst_count(pulserId, ch2, 1);
        pulse_output(pulserId, ch2, 1);

        ch2_startv[0] = 0.0; ch2_stopv[0] = 0.0; ch2_segtime[0] = hold;
        ch2_ssr[0] = 1; ch2_trig[0] = 1; ch2_meas[0] = PULSE_MEAS_NONE;
        ch2_measstart[0] = 0.0; ch2_measstop[0] = 0.0;

        ch2_startv[1] = 0.0; ch2_stopv[1] = 0.0; ch2_segtime[1] = MIN_SEG_TIME;
        ch2_ssr[1] = 1; ch2_trig[1] = 0; ch2_meas[1] = PULSE_MEAS_NONE;
        ch2_measstart[1] = 0.0; ch2_measstop[1] = 0.0;

        ch2_startv[2] = 0.0; ch2_stopv[2] = 0.0; ch2_segtime[2] = MIN_SEG_TIME;
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
        printf("pmu_ttl_laser_ch1: done\n");
    return 0;

seg_overflow:
    free_seg_arrays(startv, stopv, segtime, ssrctrl, segtrigout,
                    meastype, measstart, measstop);
    return -5;

/* USRLIB MODULE END  */
}
