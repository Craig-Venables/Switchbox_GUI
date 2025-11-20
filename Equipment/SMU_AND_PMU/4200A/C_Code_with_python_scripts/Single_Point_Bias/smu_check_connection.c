/* USRLIB MODULE INFORMATION

	MODULE NAME: smu_check_connection
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 11
	ARGUMENTS:
		BiasVoltage,	double,	Input,	0.2,	-200,	200
		SampleInterval,	double,	Input,	0.1,	0.0001,	10
		SettleTime,	double,	Input,	0.01,	0.0001,	10
		Ilimit,	double,	Input,	0.01,	1e-9,	1
		IntegrationTime,	double,	Input,	0.01,	0.0001,	1
		Ibuffer,	D_ARRAY_T,	Output,	,	,	
		NumISamples,	int,	Input,	256,	4,	4096
		Vbuffer,	D_ARRAY_T,	Output,	,	,	
		NumVSamples,	int,	Input,	256,	4,	4096
		MaxSamples,	int,	Input,	1000,	1,	100000
		ClariusDebug,	int,	Input,	0,	0,	1
	INCLUDES:
#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
	END USRLIB MODULE INFORMATION
*/

/* USRLIB MODULE HELP DESCRIPTION

Continuous SMU Bias Monitor
===========================

Applies a fixed DC bias (default 0.2 V) and measures current for MaxSamples
iterations. Measurements are stored in circular buffers (Ibuffer / Vbuffer).
The module runs to completion and returns, allowing the host to poll buffers
via GP commands after execution.

The module performs MaxSamples measurements, storing them in circular buffers.
If MaxSamples exceeds the buffer size, older samples are overwritten.

Recommended host workflow:
1. Execute EX command with desired MaxSamples (e.g., 1000 for continuous monitoring).
2. Module runs to completion (takes approximately MaxSamples × SampleInterval seconds).
3. After module returns, issue GP commands to read buffers.
4. For continuous operation, repeatedly call the module with new MaxSamples values.

Note: This module must return to allow host interaction. For truly continuous
operation, call it repeatedly from Python with appropriate MaxSamples values.

END USRLIB MODULE HELP DESCRIPTION */

#include "keithley.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static void sleep_seconds(double seconds)
{
    if (seconds <= 0.0)
    {
        return;
    }

    /* Sleep() expects milliseconds. Guard against overflow */
    long ms = (long)(seconds * 1000.0);
    if (ms < 1)
    {
        ms = 1;
    }
    Sleep(ms);
}

int smu_check_connection(double BiasVoltage,
                         double SampleInterval,
                         double SettleTime,
                         double Ilimit,
                         double IntegrationTime,
                         double *Ibuffer,
                         int NumISamples,
                         double *Vbuffer,
                         int NumVSamples,
                         int MaxSamples,
                         int ClariusDebug)
{
    int status;
    int debug;
    int write_index = 0;
    int sample_count = 0;
    double measured_current = 0.0;
    double measured_voltage = 0.0;
    const double compliance_threshold = Ilimit * 0.99;

    debug = (ClariusDebug == 1) ? 1 : 0;

    if (BiasVoltage < -200.0 || BiasVoltage > 200.0)
    {
        if (debug)
            printf("smu_check_connection ERROR: BiasVoltage (%.6f) out of range [-200, 200]\n", BiasVoltage);
        return -1;
    }

    if (SampleInterval < 0.0001)
    {
        if (debug)
            printf("smu_check_connection INFO: SampleInterval too small, using 0.0001s\n");
        SampleInterval = 0.0001;
    }

    if (SettleTime < 0.0001)
    {
        if (debug)
            printf("smu_check_connection INFO: SettleTime too small, using 0.0001s\n");
        SettleTime = 0.0001;
    }

    if (Ilimit < 1e-9)
    {
        if (debug)
            printf("smu_check_connection INFO: Ilimit too small, using 1e-9 A\n");
        Ilimit = 1e-9;
    }

    if (IntegrationTime < 0.0001)
    {
        if (debug)
            printf("smu_check_connection INFO: IntegrationTime too small, using 0.0001 PLC\n");
        IntegrationTime = 0.0001;
    }

    if (NumISamples <= 0 || NumVSamples <= 0)
    {
        if (debug)
            printf("smu_check_connection ERROR: Buffer sizes must be positive\n");
        return -2;
    }

    if (NumISamples != NumVSamples)
    {
        if (debug)
            printf("smu_check_connection ERROR: I and V buffer sizes must match (I=%d, V=%d)\n", NumISamples, NumVSamples);
        return -3;
    }

    if (MaxSamples < 1)
    {
        if (debug)
            printf("smu_check_connection ERROR: MaxSamples must be >= 1\n");
        return -4;
    }

    /* Initialize buffers */
    memset(Ibuffer, 0, sizeof(double) * NumISamples);
    memset(Vbuffer, 0, sizeof(double) * NumVSamples);

    status = setmode(SMU1, KI_INTGPLC, IntegrationTime);
    if (status != 0 && debug)
    {
        printf("smu_check_connection WARNING: setmode(KI_INTGPLC) failed: %d\n", status);
    }

    status = limiti(SMU1, Ilimit);
    if (status != 0)
    {
        if (debug)
            printf("smu_check_connection ERROR: limiti() failed with status %d\n", status);
        return -5;
    }

    if (debug)
    {
        printf("\n================ smu_check_connection ================\n");
        printf("  BiasVoltage     : %.6f V\n", BiasVoltage);
        printf("  SampleInterval  : %.6f s\n", SampleInterval);
        printf("  SettleTime      : %.6f s\n", SettleTime);
        printf("  Ilimit          : %.6e A\n", Ilimit);
        printf("  IntegrationTime : %.6f PLC\n", IntegrationTime);
        printf("  Buffer Size     : %d samples\n", NumISamples);
        printf("======================================================\n");
    }

    for (sample_count = 0; sample_count < MaxSamples; sample_count++)
    {
        status = forcev(SMU1, BiasVoltage);
        if (status != 0)
        {
            if (debug)
                printf("smu_check_connection ERROR: forcev() failed with status %d\n", status);
            forcev(SMU1, 0.0);
            return -6;
        }

        sleep_seconds(SettleTime);

        status = measi(SMU1, &measured_current);
        if (status != 0)
        {
            if (debug)
                printf("smu_check_connection ERROR: measi() failed with status %d\n", status);
            forcev(SMU1, 0.0);
            return -7;
        }

        status = intgv(SMU1, &measured_voltage);
        if (status != 0)
        {
            if (debug)
                printf("smu_check_connection WARNING: intgv() failed, using forced voltage\n");
            measured_voltage = BiasVoltage;
        }

        if (fabs(measured_current) >= compliance_threshold && debug)
        {
            printf("smu_check_connection WARNING: Compliance hit (|I|=%.6e A)\n", measured_current);
        }

        Ibuffer[write_index] = measured_current;
        Vbuffer[write_index] = measured_voltage;

        write_index++;
        if (write_index >= NumISamples)
        {
            write_index = 0;
        }

        if (debug && (sample_count % 100 == 0 || sample_count == MaxSamples - 1))
        {
            printf("Sample %d/%d: V=%.6f V, I=%.6e A, idx=%d\n",
                   sample_count + 1, MaxSamples, measured_voltage, measured_current, write_index);
        }

        sleep_seconds(SampleInterval);
    }

    forcev(SMU1, 0.0);
    if (debug)
        printf("smu_check_connection INFO: Output disabled, returning\n");

    return 0;
}


