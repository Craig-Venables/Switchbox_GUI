/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig8_single_channel_wave_aux
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 33
	ARGUMENTS:
		width,	double,	Input,	1e-6,	2e-8,	1
		rise,	double,	Input,	3e-8,	2e-8,	1
		fall,	double,	Input,	3e-8,	2e-8,	1
		delay,	double,	Input,	0,	0,	1
		period,	double,	Input,	5e-6,	1e-6,	1
		baseV,	double,	Input,	0,	-20,	20
		pulseV,	double,	Input,	1.5,	-20,	20
		numPulses,	int,	Input,	50,	1,	1000
		VRange,	double,	Input,	10,	5,	40
		IRange,	double,	Input,	1e-3,	100e-9,	0.8
		DUTRes,	double,	Input,	1e6,	1,	1e9
		sampleRate,	double,	Input,	5e7,	1e5,	2e8
		prePct,	double,	Input,	0.1,	0,	1
		postPct,	double,	Input,	0.1,	0,	1
		auxBaseV,	double,	Input,	0,	-20,	20
		auxPulseV,	double,	Input,	1.5,	-20,	20
		auxDelay,	double,	Input,	0,	0,	1
		auxWidth,	double,	Input,	1e-6,	2e-8,	1
		auxRise,	double,	Input,	3e-8,	2e-8,	1
		auxFall,	double,	Input,	3e-8,	2e-8,	1
		VF,	D_ARRAY_T,	Output,	,	,	
		VF_size,	int,	Input,	5000,	100,	30000
		IF,	D_ARRAY_T,	Output,	,	,	
		IF_size,	int,	Input,	5000,	100,	30000
		T,	D_ARRAY_T,	Output,	,	,	
		T_size,	int,	Input,	5000,	100,	30000
		npts,	int *,	Output,	,	,	
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

extern int debug;
extern BOOL LPTIsInCurrentConfiguration(char *hrid);


/* USRLIB MODULE MAIN FUNCTION */
int ACraig8_single_channel_wave_aux(
	double width,
	double rise,
	double fall,
	double delay,
	double period,
	double baseV,
	double pulseV,
	int numPulses,
	double VRange,
	double IRange,
	double DUTRes,
	double sampleRate,
	double prePct,
	double postPct,
	double auxBaseV,
	double auxPulseV,
	double auxDelay,
	double auxWidth,
	double auxRise,
	double auxFall,
	double *VF,
	int VF_size,
	double *IF,
	int IF_size,
	double *T,
	int T_size,
	int *npts,
	int ClariusDebug)
{
	char mod[] = "ACraig8_single_channel_wave_aux";
	int status = 0;
	INSTR_ID instId;
	double *waveV = NULL;
	double *waveI = NULL;
	double *waveT = NULL;
	long sampleCount = 0;
	int auxEnabled = 0;

	if (VF == NULL || IF == NULL || T == NULL || npts == NULL)
		return -200;

	if (VF_size <= 0 || IF_size <= 0 || T_size <= 0)
		return -200;

	*npts = 0;

	if (ClariusDebug)
		debug = 1;

	if (!LPTIsInCurrentConfiguration("PMU1")) {
		if (debug) printf("%s: PMU1 not available in current configuration\n", mod);
		return -17001;
	}

	getinstid("PMU1", &instId);
	if (-1 == instId) {
		if (debug) printf("%s: failed to obtain instrument ID\n", mod);
		return -17002;
	}

	auxEnabled = fabs(auxPulseV - auxBaseV) > 1e-9;

	status = rpm_config(instId, 1, KI_RPM_PATHWAY, KI_RPM_PULSE);
	if (status) return status;

	if (auxEnabled) {
		status = rpm_config(instId, 2, KI_RPM_PATHWAY, KI_RPM_PULSE);
		if (status) {
			if (debug) printf("%s: aux rpm_config failed (%d), disabling aux pulse\n", mod, status);
			auxEnabled = 0;
		}
	}

	status = pg2_init(instId, PULSE_MODE_PULSE);
	if (status) return status;

	if (IRange <= 0.0) IRange = 1e-3;
	if (sampleRate <= 0.0) sampleRate = 5e7;

	status = pulse_sample_rate(instId, sampleRate);
	if (status) return status;

	status = pulse_load(instId, 1, DUTRes > 0.0 ? DUTRes : 1e6);
	if (status) return status;

	status = pulse_ranges(instId, 1, VRange, PULSE_MEAS_FIXED, VRange, PULSE_MEAS_FIXED, IRange);
	if (status) return status;

	if (auxEnabled) {
		status = pulse_load(instId, 2, 1e6);
		if (status) auxEnabled = 0;
		if (auxEnabled) {
			status = pulse_ranges(instId, 2, VRange, PULSE_MEAS_FIXED, VRange, PULSE_MEAS_FIXED, IRange);
			if (status) auxEnabled = 0;
		}
		if (!auxEnabled && debug)
			printf("%s: auxiliary configuration failed, continuing without aux pulse\n", mod);
	}

	status = pulse_source_timing(instId, 1, period, delay, width, rise, fall);
	if (status) return status;

	status = pulse_vlow(instId, 1, baseV);
	if (status) return status;
	status = pulse_vhigh(instId, 1, pulseV);
	if (status) return status;

	status = pulse_meas_wfm(instId, 1, 0, TRUE, TRUE, TRUE, FALSE);
	if (status) return status;

	status = pulse_meas_timing(instId, 1, prePct, postPct, 1);
	if (status) return status;

	status = pulse_burst_count(instId, 1, numPulses > 0 ? numPulses : 1);
	if (status) return status;

	if (auxEnabled) {
		status = pulse_source_timing(instId, 2, period, auxDelay, auxWidth, auxRise, auxFall);
		if (status) auxEnabled = 0;
		if (auxEnabled) {
			status = pulse_vlow(instId, 2, auxBaseV);
			if (status) auxEnabled = 0;
		}
		if (auxEnabled) {
			status = pulse_vhigh(instId, 2, auxPulseV);
			if (status) auxEnabled = 0;
		}
		if (auxEnabled) {
			status = pulse_burst_count(instId, 2, numPulses > 0 ? numPulses : 1);
			if (status) auxEnabled = 0;
		}
		if (!auxEnabled && debug)
			printf("%s: auxiliary pulse timing setup failed, aux disabled\n", mod);
	}

	status = pulse_output(instId, 1, 1);
	if (status) return status;

	if (auxEnabled) {
		status = pulse_output(instId, 2, 1);
		if (status) auxEnabled = 0;
	}

	status = pulse_exec(PULSE_MODE_SIMPLE);
	if (status) return status;

	{
		double statusTime = 0.0;
		int guard = 0;
		while (pulse_exec_status(&statusTime) == 1 && guard < 1000) {
			Sleep(10);
			guard++;
		}
	}

	sampleCount = VF_size;
	if (IF_size < sampleCount) sampleCount = IF_size;
	if (T_size < sampleCount) sampleCount = T_size;

	if (sampleCount <= 0) return -200;

	waveV = (double *)calloc(sampleCount, sizeof(double));
	waveI = (double *)calloc(sampleCount, sizeof(double));
	waveT = (double *)calloc(sampleCount, sizeof(double));

	if (waveV == NULL || waveI == NULL || waveT == NULL) {
		if (waveV) free(waveV);
		if (waveI) free(waveI);
		if (waveT) free(waveT);
		return -210;
	}

	status = pulse_fetch(instId, 1, 0, sampleCount, waveV, waveI, waveT, NULL);
	if (status && status != -1407) {
		free(waveV);
		free(waveI);
		free(waveT);
		return status;
	}

	for (long idx = 0; idx < sampleCount; ++idx) {
		VF[idx] = waveV[idx];
		IF[idx] = waveI[idx];
		T[idx] = waveT[idx];
	}

	*npts = (int)sampleCount;

	free(waveV);
	free(waveI);
	free(waveT);

	return 0;
/* USRLIB MODULE END  */
}		/* End ACraig8_single_channel_wave_aux.c */*** End Patch
/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig8_single_channel_wave_aux
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 33
	ARGUMENTS:
		width,	double,	Input,	1e-6,	2e-8,	1
		rise,	double,	Input,	3e-8,	2e-8,	1
		fall,	double,	Input,	3e-8,	2e-8,	1
		delay,	double,	Input,	0.0,	0.0,	1
		period,	double,	Input,	5e-6,	1e-6,	1
		baseV,	double,	Input,	0.0,	-20,	20
		pulseV,	double,	Input,	1.5,	-20,	20
		numPulses,	int,	Input,	50,	1,	1000
		VRange,	double,	Input,	10.0,	5,	40
		IRange,	double,	Input,	1e-3,	100e-9,	0.8
		DUTRes,	double,	Input,	1e6,	1,	1e9
		sampleRate,	double,	Input,	5e7,	1e5,	2e8
		prePct,	double,	Input,	0.1,	0.0,	1.0
		postPct,	double,	Input,	0.1,	0.0,	1.0
		auxBaseV,	double,	Input,	0.0,	-20,	20
		auxPulseV,	double,	Input,	1.5,	-20,	20
		auxDelay,	double,	Input,	0.0,	0.0,	1
		auxWidth,	double,	Input,	1e-6,	2e-8,	1
		auxRise,	double,	Input,	3e-8,	2e-8,	1
		auxFall,	double,	Input,	3e-8,	2e-8,	1
		VF,	D_ARRAY_T,	Output,	,	,	
		VF_size,	int,	Input,	5000,	100,	30000
		IF,	D_ARRAY_T,	Output,	,	,	
		IF_size,	int,	Input,	5000,	100,	30000
		T,	D_ARRAY_T,	Output,	,	,	
		T_size,	int,	Input,	5000,	100,	30000
		npts,	int *,	Output,	,	,	
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

extern int debug;
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: ACraig8_single_channel_wave_aux
======================================

Description
-----------
Channel 1 (force/measure) generates a simple two-level pulse train and captures the
resulting voltage/current waveform. Channel 2 simultaneously sources an auxiliary
pulse (no measurement) for driving external equipment such as a laser trigger.

Inputs allow control of the primary pulse shape (rise/fall/width/period), sample rate,
and auxiliary pulse levels/timing.  Waveform samples (voltage/current vs. time) are returned
via the VF/IF/T arrays together with the number of valid points (npts).

Return values
-------------
Value | Description
------|------------
 0    | OK
-122  | Illegal value for parameter (forwarded from driver)
-141  | Error setting compliance on channel 1
-142  | Error setting compliance on channel 2
-200  | Output buffer too small for captured waveform

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

extern int debug;
extern BOOL LPTIsInCurrentConfiguration(char *hrid);

static void ac8_free(double *a, double *b, double *c);

/* USRLIB MODULE MAIN FUNCTION */
int ACraig8_single_channel_wave_aux(
	double width,
	double rise,
	double fall,
	double delay,
	double period,
	double baseV,
	double pulseV,
	int numPulses,
	double VRange,
	double IRange,
	double DUTRes,
	double sampleRate,
	double prePct,
	double postPct,
	double auxBaseV,
	double auxPulseV,
	double auxDelay,
	double auxWidth,
	double auxRise,
	double auxFall,
	double *VF,
	int VF_size,
	double *IF,
	int IF_size,
	double *T,
	int T_size,
	int *npts,
	int ClariusDebug)
{
	char mod[] = "ACraig8_single_channel_wave_aux";
	int status;
	INSTR_ID instId;
	long collected = 0;
	double *waveV = NULL;
	double *waveI = NULL;
	double *waveT = NULL;
	long fetchCount;
	int auxEnabled;

	if (VF == NULL || IF == NULL || T == NULL || npts == NULL)
		return -200;

	*npts = 0;
	if (VF_size <= 0 || IF_size <= 0 || T_size <= 0)
		return -200;

	if (ClariusDebug)
		debug = 1;

	if (!LPTIsInCurrentConfiguration("PMU1")) {
		if (debug) printf("%s: PMU1 not present in configuration\n", mod);
		return -17001;
	}

	getinstid("PMU1", &instId);
	if (-1 == instId) {
		if (debug) printf("%s: failed to get instrument id\n", mod);
		return -17002;
	}

	auxEnabled = fabs(auxPulseV - auxBaseV) > 1e-9;

	status = rpm_config(instId, 1, KI_RPM_PATHWAY, KI_RPM_PULSE);
	if (status) return status;

	if (auxEnabled) {
		status = rpm_config(instId, 2, KI_RPM_PATHWAY, KI_RPM_PULSE);
		if (status) return status;
	}

	status = pg2_init(instId, PULSE_MODE_PULSE);
	if (status) return status;

	if (IRange <= 0.0)
		IRange = 1e-3;

	if (sampleRate <= 0.0)
		sampleRate = 5e7;

	status = pulse_sample_rate(instId, sampleRate);
	if (status) return status;

	status = pulse_load(instId, 1, DUTRes > 0.0 ? DUTRes : 1e6);
	if (status) return status;

	status = pulse_ranges(instId, 1, VRange, PULSE_MEAS_FIXED, VRange, PULSE_MEAS_FIXED, IRange);
	if (status) return status;

	if (auxEnabled) {
		status = pulse_load(instId, 2, 1e6);
		if (status) return status;
		status = pulse_ranges(instId, 2, VRange, PULSE_MEAS_FIXED, VRange, PULSE_MEAS_FIXED, IRange);
		if (status) return status;
	}

	status = pulse_source_timing(instId, 1, period, delay, width, rise, fall);
	if (status) return status;

	status = pulse_vlow(instId, 1, baseV);
	if (status) return status;
	status = pulse_vhigh(instId, 1, pulseV);
	if (status) return status;

	status = pulse_meas_wfm(instId, 1, 0, TRUE, TRUE, TRUE, FALSE);
	if (status) return status;

	status = pulse_meas_timing(instId, 1, prePct, postPct, 1);
	if (status) return status;

	status = pulse_burst_count(instId, 1, numPulses > 0 ? numPulses : 1);
	if (status) return status;

	if (auxEnabled) {
		status = pulse_source_timing(instId, 2, period, auxDelay, auxWidth, auxRise, auxFall);
		if (status) return status;
		status = pulse_vlow(instId, 2, auxBaseV);
		if (status) return status;
		status = pulse_vhigh(instId, 2, auxPulseV);
		if (status) return status;
		status = pulse_burst_count(instId, 2, numPulses > 0 ? numPulses : 1);
		if (status) return status;
	}

	status = pulse_output(instId, 1, 1);
	if (status) return status;
	if (auxEnabled) {
		status = pulse_output(instId, 2, 1);
		if (status) return status;
	}

	status = pulse_exec(PULSE_MODE_SIMPLE);
	if (status) return status;

	{
		double t = 0.0;
		int guard = 0;
		while (pulse_exec_status(&t) == 1 && guard < 1000) {
			Sleep(10);
			guard++;
		}
	}

	fetchCount = (long)(VF_size < IF_size ? VF_size : IF_size);
	if (T_size < fetchCount)
		fetchCount = T_size;

	waveV = (double *)calloc(fetchCount, sizeof(double));
	waveI = (double *)calloc(fetchCount, sizeof(double));
	waveT = (double *)calloc(fetchCount, sizeof(double));
	if (waveV == NULL || waveI == NULL || waveT == NULL) {
		ac8_free(waveV, waveI, waveT);
		return -210;
	}

	status = pulse_fetch(instId, 1, 0, fetchCount, waveV, waveI, waveT, NULL);
	if (status && status != -1407) {
		ac8_free(waveV, waveI, waveT);
		return status;
	}

	collected = fetchCount;
	if (collected > VF_size) collected = VF_size;
	if (collected > IF_size) collected = IF_size;
	if (collected > T_size) collected = T_size;

	for (long idx = 0; idx < collected; ++idx) {
		VF[idx] = waveV[idx];
		IF[idx] = waveI[idx];
		T[idx] = waveT[idx];
	}
	*npts = (int)collected;

	ac8_free(waveV, waveI, waveT);
	return 0;
/* USRLIB MODULE END  */
}		/* End ACraig8_single_channel_wave_aux.c */

static void ac8_free(double *a, double *b, double *c)
{
	if (a) free(a);
	if (b) free(b);
	if (c) free(c);
}

