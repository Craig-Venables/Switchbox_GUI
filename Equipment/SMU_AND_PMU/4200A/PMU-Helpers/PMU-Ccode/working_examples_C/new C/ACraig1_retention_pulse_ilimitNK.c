/* USRLIB MODULE INFORMATION

	MODULE NAME: ACraig1_retention_pulse_ilimitNK
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 26
	ARGUMENTS:
		InstrName,	char *,	Input,	"PMU1",	,	
		ForceCh,	long,	Input,	1,	1,	2
		ForceVRange,	double,	Input,	5,	5,	40
		ForceIRange,	double,	Input,	1e-2,	100e-9,	.8
		iFLimit,	double,	Input,	1e-2,	0.0,	
		iMLimit,	double,	Input,	1e-3,	0.0,	
		MeasureCh,	long,	Input,	2,	1,	2
		MeasureVRange,	double,	Input,	5,	5,	40
		MeasureIRange,	double,	Input,	1e-2,	100e-9,	.8
		max_pts,	int,	Input,	10000,	12,	30000
		MeasureBias,	double,	Input,	0.0,	-20,	20
		Volts,	D_ARRAY_T,	Input,	0.0,	-20,	20
		volts_size,	int,	Input,	100,	3,	2048
		Times,	D_ARRAY_T,	Input,	1e-7,	2e-8,	1
		times_size,	int,	Input,	100,	3,	2048
		VF,	D_ARRAY_T,	Output,	,	,	
		vf_size,	int,	Input,	100,	12,	30000
		IF,	D_ARRAY_T,	Output,	,	,	
		if_size,	int,	Input,	100,	12,	30000
		VM,	D_ARRAY_T,	Output,	,	,	
		vm_size,	int,	Input,	100,	12,	30000
		IM,	D_ARRAY_T,	Output,	,	,	
		im_size,	int,	Input,	100,	12,	30000
		T,	D_ARRAY_T,	Output,	,	,	
		t_size,	int,	Input,	100,	12,	30000
		npts,	int *,	Output,	,	,	
	INCLUDES:
#include "keithley.h"

double *fstartv = NULL;
double *fstopv = NULL;
double *mstartv = NULL; 
double *mstopv = NULL; 
double *measstart = NULL;
double *measstop = NULL;
double *segtime = NULL;
long *ssrctrl = NULL;
long *meastypes = NULL;
long *trig = NULL;

double *pulseV = NULL;
double *pulseI = NULL; 
double *pulseT = NULL;
double *MpulseV = NULL;
double *MpulseI = NULL;
double *MpulseT = NULL;

static int not_init = 1;
static int trigger_override_segment = -1;

void ret_set_trigger_override(int segmentIndex)
{
    trigger_override_segment = segmentIndex;
}
 
void ret_AllocateMemoryILimit(int npts);
void ret_AllocateMeasArraysILimit(int npts);
void ret_FreeMemoryILimit(void);
double ret_Define_SegmentsILimit(double *v, double *t, int pts, double bias);
BOOL LPTIsInCurrentConfiguration(char* hrid);

__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts) ;

int debug = 0;
int details = 0;
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: ACraig1_retention_pulse_ilimitNK
=========================

Description
-----------
The purpose of this routine is to simplify the generation of segments using the PMU, and 
collect forced voltage and current values from both the ForceCh and MeasureCh channels. 
The basic scenario used is a connection of the ForceCh to the high side of the DUT while 
MeasureCh is connected to the low side of the DUT. The segments are created based on 
the settings provided by the operator within the 'Volts' and 'Times' input arrays, and measurements 
are returned via of the voltage(VF and VM) and current (IF and IM) output arrays for both channels.

Input and output parameters
---------------------------

InstrName 
: Defines the pulser to be implemented. For instance, 'PMU1'.

ForceCh 
: The PMU channel that will be used to force the segment voltage pattern to the DUT.

ForceVRange 
: The voltage range to be used by the ForceCh channel.
: Note that maximum voltage for a range is possible only with a high impedance DUT 
		 (roughly 100 k&Omega; and higher).
: Valid ranges: 10, 40

ForceIRange 
: The current range to be used by the ForceCh channel. Valid ranges: 
: PMU 10V:  0.01, 0.2
: PMU 20V:  100e-6, 0.01, 0.8
: RPM 10V:  100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

iFLimit 
: The current limit for segment forcing channel.
  Current limiting is disabled if the value is set to 0.0 or if the value
  is greater than or equal to the value of ForceIRange. (A)

iMLimit 
: The current limit for the measuring channel. Current limiting  is disabled
  if the value is set to 0.0 or if the value is greater than or equal to the
  value of MeasureIRange. (A)

MeasureCh 
: The PMU channel that will be used for current measurements.
  Note that MeasureCh can be the as ForceCh, in which case the
  force and measure will occur on only one channel.

MeasureVRange 
: The voltage range to be used by the MeasureCh channel.
: Note that maximum voltage for a range is possible only with a high impedance DUT 
  (roughly 100 k&Omega; and higher).
: Valid ranges: 10, 40

MeasureIRange 
: The current range to be used by the MeasureCh channel. Valid ranges:
: PMU 10V:  0.01, 0.2
: PMU 20V:  100e-6, 0.01, 0.8
: RPM 10V:  100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 0.01

max_pts 
: The maximum points to be used for data collection. Recommended 10000.

MeasureBias 
: The voltage bias to be applied on the low (MeasureCh) side.
  This paramenter will be ignored if the force and measure channels are set to the same value. (V)

Volts 
: The array of voltage values corresponding to the points of the segment profile. (V)

volts_size 
: Indicates the size of Volts array. 

Times 
: The array of time values corresponding to the points of the segment profile.  (s)

times_size 
: Indicates the size of Time array. Should be = volts_size - 1.

VF
: The output array that returns the set of measured voltage values from the ForceCh. (V)

vf_size 
: Defines the size of VF array.

IF 
: The output array that returns the set of measured current values from the ForceCh. (A)

if_size 
: Defines the size of IF array. Should be the same as vf_size.

VM 
: The output array that returns the set of measured current values from the MeasureCh. (A)

vm_size 
: Defines the size of VF array. Should be the same as vf_size.

IM 
: The output array that returns the set of measured current values from the MeasureCh. (A)

im_size 
: Defines the size of IM array. Should be the same as vf_size.

T
: The output array that returns the set of time values from the ForceCh. (s)

t_size 
: Defines the size of T array. Should be the same as vf_size.

npts 
: Returns the actual number of collected data points.

Return values
-------------
			 
Value  | Description
------ | -----------
0      | OK.
-1     | Error in volts_size, it should be > 3
-2     | Error in vf_size, if_size, t_size; vf_size should be > 10; vf_size == t_size == if_size
-3     | Error in vm_size, im_size, t_size; vm_size should be > 10; vm_size == t_size == im_size
-4     | Cannot get InstrName from LPTIsInCurrentConfiguration()
-5     | Error getting InstId from getinstid()
-6     | Error in pg2_init
-7     | Error in pulse_load for ForceCh
-8     | Error in pulse_ranges for ForceCh
-9     | Error in pulse_burst_count for ForceCh
-10    | Error in pulse_output for ForceCh
-11    | Error in pulse_load for MeasureCh
-12    | Error in pulse_ranges for MeasureCh
-13    | Error in pulse_burst_count for MeasureCh
-14    | Error in pulse_output for MeasureCh
-15    | Error in pulse_sample_rate for MeasureCh
-16    | Error in seq_arb_sequence for ForceCh
-17    | Error in seq_arb_sequence for MeasureCh
-18    | Error in seq_arb_waveform for ForceCh
-19    | Error in seq_arb_waveform for MeasureCh
-20    | Error in pulse_fetch for ForceCh
-21    | Error in pulse_fetch for MeasureCh
-22    | Max_pts if too large

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"

double *fstartv = NULL;
double *fstopv = NULL;
double *mstartv = NULL; 
double *mstopv = NULL; 
double *measstart = NULL;
double *measstop = NULL;
double *segtime = NULL;
long *ssrctrl = NULL;
long *meastypes = NULL;
long *trig = NULL;

double *pulseV = NULL;
double *pulseI = NULL; 
double *pulseT = NULL;
double *MpulseV = NULL;
double *MpulseI = NULL;
double *MpulseT = NULL;

static int not_init = 1;
static int trigger_override_segment = -1;

void ret_set_trigger_override(int segmentIndex)
{
    trigger_override_segment = segmentIndex;
}
 
void ret_AllocateMemoryILimit(int npts)
{
    fstartv = (double *)calloc(npts, sizeof(double));
    fstopv  = (double *)calloc(npts, sizeof(double));
    mstartv  = (double *)calloc(npts, sizeof(double));
    mstopv  = (double *)calloc(npts, sizeof(double));
    measstart  = (double *)calloc(npts, sizeof(double));
    measstop  = (double *)calloc(npts, sizeof(double));
    segtime              = (double *)calloc(npts, sizeof(double));
    
    trig  = (long *)calloc(npts, sizeof(long));
    ssrctrl  = (long *)calloc(npts, sizeof(long));
    meastypes  = (long *)calloc(npts, sizeof(long));
}

void ret_AllocateMeasArraysILimit(int npts)
{
    pulseV = (double *) calloc(npts, sizeof(double));
    pulseI = (double *) calloc(npts, sizeof(double));
    pulseT = (double *) calloc(npts, sizeof(double));

    MpulseV = (double *) calloc(npts, sizeof(double));
    MpulseI = (double *) calloc(npts, sizeof(double));
    MpulseT = (double *) calloc(npts, sizeof(double));
}


void ret_FreeMemoryILimit(void)
{
    if(NULL != fstartv) free(fstartv);
    if(NULL != fstopv) free(fstopv);
    if(NULL != mstartv) free(mstartv);
    if(NULL != mstopv) free(mstopv);
    if(NULL != measstart) free(measstart);
    if(NULL != measstop) free(measstop);
    if(NULL != segtime) free(segtime);
    
    if(NULL != trig) free(trig);
    if(NULL != ssrctrl) free(ssrctrl);
    if(NULL != meastypes) free(meastypes);

    if(NULL != pulseV) free(pulseV);
    if(NULL != pulseI) free(pulseI);
    if(NULL != pulseT) free(pulseT);

    if(NULL != MpulseV) free(MpulseV);
    if(NULL != MpulseI) free(MpulseI);
    if(NULL != MpulseT) free(MpulseT);
}

double ret_Define_SegmentsILimit(double *v, double *t, int pts, double bias)
{
  char mod[] = "ret_Define_Segments";
  int i = 0;
  double ttime = 0.0;
  const double eps = 1e-6;

  do 
    {
      fstartv[i] = v[i];
      fstopv[i] = v[i+1];
      
      segtime[i] = t[i];
      ttime += t[i];

      measstart[i] = 0;
      measstop[i]  = segtime[i];

      if (fabs(fstartv[i]) < eps && fabs(fstopv[i]) < eps)
        meastypes[i] = 2;
      else
        meastypes[i] = 2;
      
      mstartv[i] = bias;
      mstopv[i]  = bias;
      
      if(trigger_override_segment >= 0)
        trig[i] = (i == trigger_override_segment) ? 1 : 0;
      else if(i == 0)
        trig[i] = 1;
      else
        trig[i] = 0;
      
      ssrctrl[i] = 1;
      
      if(debug)
      {
        printf("%s: Segment %d startv:%g stopv:%g time:%g\n",
               mod, i, fstartv[i], fstopv[i], segtime[i]);
      }
      i++;
      
    }
  while(i < pts);
  return ttime;

}


__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts) 
{
  char mod [] = "ret_getRate";
  int usedrate;
  int usedpts;
  int min_rate;

  int n = 1;
  int rate_found = 0;
  
  int max_pts = 30000;
  int default_rate = 200000000;
  int max_devider = 1000;

  
  min_rate = (int) default_rate/max_devider;

  *apts = 0;
  *npts = 0;
  usedrate = -1;
  
  if(maxpts > max_pts)
  {
      if(debug) printf("%s: Requested Number of points %d > of allowed %d\n", mod, maxpts, max_pts);
      goto RD;
  }

  //let's calculate the rate first
  usedrate = default_rate;

  while(rate_found == 0 && n < max_devider * 2)
  {
        usedrate = (int) (default_rate/n);
        usedpts = (int)(ttime * usedrate + 2);
        if(usedpts < maxpts)
        {
            rate_found = 1;
            break;
        }
        else
        {
            n++;
        }
  }

  if(usedrate < min_rate)
  {
        if(debug) printf("%s: rate (%d) is too small (< %d)\n", mod, usedrate, min_rate);
        usedrate = -2;
        goto RD;
  } 
  
  *apts = usedpts;
  *npts = (int) (ttime * usedrate + 0.5);

  RD:
  if(debug)printf("%s: used rate: %d used pts: %d allocate pts: %d maximum points: %d\n", mod, usedrate, *npts, *apts, maxpts);

  RETURN:
  if(debug) printf("%s: returns with status: %d Number of points: %d\n", mod, stat, *npts);
  trigger_override_segment = -1;
  ret_FreeMemoryILimit();

  return usedrate;
/* USRLIB MODULE END  */
} 		/* End ACraig1_retention_pulse_ilimitNK.c */

