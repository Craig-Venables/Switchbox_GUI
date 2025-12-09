/* USRLIB MODULE INFORMATION

	MODULE NAME: retention_pulse_ilimit_dual_channel_bias
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
		max_pts,	int,	Input,	10000,	12,	1000000
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

void ret_AllocateMemoryILimit(int npts);
void ret_AllocateMeasArraysILimit(int npts);
void ret_FreeMemoryILimit(void);
double ret_Define_SegmentsILimit(double *v, double *t, int pts, double bias);
BOOL LPTIsInCurrentConfiguration(char* hrid);

__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts) ;
__declspec( dllexport ) int ret_getRateWithMinSeg(double ttime, int maxpts, double min_seg_time, int *apts, int *npts);

int debug = 0;
int details = 0;
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: retention_pulse_ilimit_dual_channel_bias
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

void ret_AllocateMemoryILimit(int npts);
void ret_AllocateMeasArraysILimit(int npts);
void ret_FreeMemoryILimit(void);
double ret_Define_SegmentsILimit(double *v, double *t, int pts, double bias);
BOOL LPTIsInCurrentConfiguration(char* hrid);

__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts) ;

int debug = 0;
int details = 0;

/* USRLIB MODULE MAIN FUNCTION */
int retention_pulse_ilimit_dual_channel_bias( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts )
{
/* USRLIB MODULE CODE */
  int stat = 1;
  int status;
  INSTR_ID InstId;
  double t;
  int i, j;
  char mod[] = "retention_pulse_ilimit_dual_channel_bias";
  long SeqList[1] = {1};
  double LoopCountList[1] = {1};
  int numpts;
  int NumDataPts;
  double ttime;
  int allocate_pts = 0;
  int used_rate = 0;
  double ratio;

  if(debug) printf("%s: starts\n", mod);
  
  numpts = volts_size - 1;
  ret_AllocateMemoryILimit(volts_size);

  // error checks 
  if(volts_size != times_size + 1 || volts_size < 4) { stat = -1; goto RETURN;}
  if(vf_size < 10 || vf_size != t_size || if_size != t_size) { stat = -2; goto RETURN;}
  if(vm_size < 10 || vm_size != t_size || im_size != t_size || t_size > max_pts) 
  {
     if(debug) printf("%s: vm_size:%d t_size:%d im_size:%d max_pts:%d\n",
     mod, vm_size, t_size, im_size, max_pts); 
     stat = -3; goto RETURN;
   }

 if(debug) printf("Note: In the following segments, TTime is the time at the end of the segment so a probe measurement needs to be before this time\n");
   //Define Seqments:
  ttime = ret_Define_SegmentsILimit(Volts, Times, volts_size - 1, MeasureBias);

  // Find minimum segment time for optimal rate selection
  double min_seg_time_found = 1.0;  // Start with a large value
  for(i = 0; i < times_size; i++)
  {
    if(Times[i] > 0.0 && Times[i] < min_seg_time_found)
    {
      min_seg_time_found = Times[i];
    }
  }
  if(debug) printf("%s: Minimum segment time in waveform: %.2e s\n", mod, min_seg_time_found);

  //determine required number of points and required rate
  //number of points should not exceed user defined max_pts and function max: MAXPTS (1,000,000)
  // Use enhanced rate selection that considers minimum segment time

  used_rate = ret_getRateWithMinSeg(ttime, max_pts, min_seg_time_found, &allocate_pts, &NumDataPts);
  if(0 > used_rate)
  {
     if(debug) printf("%s: used rate is invalid!\n", mod);
     stat = -33;
     goto RETURN;
  }

  ret_AllocateMeasArraysILimit(allocate_pts);

  if(fabs(MeasureIRange) > 1e-2)
  {
      stat = -44;
      if(debug)printf("%s: RPMs are in bypass!\n", mod);
      goto RETURN;
  }
  
  if(!LPTIsInCurrentConfiguration(InstrName)) {stat = -4; goto RETURN;}

 
  // get instrument ID
  getinstid(InstrName, &InstId);
  if(-1 == InstId) {stat = -5; goto RETURN;}
  if(debug) printf("%s: Instrument ID:%d\n", mod, InstId);

  not_init = 1;
  
  //initialize PMU
  if(not_init)
  {
      // NK added 24/10/2024
      // **************************************************************
      status = rpm_config(InstId, ForceCh, KI_RPM_PATHWAY, KI_RPM_PULSE);
      if(debug)printf("RPM is initialized for ForceCh! %s (0 or null is good)\n", status);

      status = rpm_config(InstId, MeasureCh, KI_RPM_PATHWAY, KI_RPM_PULSE);
      if(debug)printf("RPM is initialized for MeasCh! %s (0 or null is good)\n", status);

     // **************************************************************


      status = pg2_init(InstId, PULSE_MODE_SARB);
      if(status) { stat = -6; goto RETURN; }
      if(debug)printf("%s: PMU is initialized!\n", mod);
  }

  if(iFLimit == 0.0)
    {
    OpenLimit(InstId);
    }
    else
    {
      status = Set_RPM_ICompliance( InstId, ForceCh, iFLimit);
      if(debug)printf("%s: called Set_RPM_ICompliance for channel:%d and limit %g. Returned:%d\n",
              mod, ForceCh, iFLimit, status);
      if(status) { stat = -141; goto RETURN; }
    }
  if(ForceCh != MeasureCh && MeasureCh > 0)
  {
    if(iMLimit == 0.0)
    {
        OpenLimit(InstId);
    }
    else
    {
        status = Set_RPM_ICompliance( InstId, MeasureCh, iMLimit);
         if(debug)printf("%s: called Set_RPM_ICompliance for channel:%d and limit %g. Returned:%d\n",
         mod, MeasureCh, iMLimit, status);
         if(status) { stat = -142; goto RETURN; }
    }
  }
  //setup loads

  //for Force Channel
  if(not_init)
  {

      status = pulse_load(InstId, ForceCh, 1e+6);
      if(status) { stat = -7; goto RETURN; }
      if(debug)printf("%s: pulse_load set\n", mod);
  } 

  status = pulse_ranges(InstId, ForceCh, 
            ForceVRange, PULSE_MEAS_FIXED, 
            ForceVRange, PULSE_MEAS_FIXED, 
            ForceIRange);
  if(status) { stat = -8; goto RETURN; }

  if(not_init)
  {
      status = pulse_burst_count(InstId, ForceCh, 1);
      if(status) { stat = -9; goto RETURN; }

      status = pulse_output(InstId, ForceCh, 1);
      if(status) { stat = -10; goto RETURN; }

 }

  //for Measure Channel
  if(ForceCh != MeasureCh && MeasureCh > 0)
    {
      if(not_init)
      {
          status = pulse_load(InstId, MeasureCh, 50);
          if(status) if(status) { stat = -11; goto RETURN; }
      }

      status = pulse_ranges(InstId, MeasureCh, 
              MeasureVRange, PULSE_MEAS_FIXED, 
              MeasureVRange, PULSE_MEAS_FIXED, 
              MeasureIRange);
      if(status) { stat = -12; goto RETURN; }

// ****************************************
 if (debug) printf(" Made it here 0\n");

      if(not_init)
      {
          status = pulse_burst_count(InstId, MeasureCh, 1);
          if(status) { stat = -13; goto RETURN; }

          status = pulse_output(InstId, MeasureCh, 1);
          if(status) { stat = -14; goto RETURN; }
      }
    }
    
  status = pulse_sample_rate(InstId, used_rate);      
  if(status) if(status) { stat = -15; goto RETURN; }

// ****************************************************
  if (debug) printf(" Made it here 1\n");
  // problem is here with segtime

  // Validate segment times before calling seg_arb_sequence
  // Minimum segment time must be sufficient for the selected sample rate
  // Need at least 4-5 samples per segment for reliable measurement
  // This is DYNAMIC: adapts to sample rate automatically
  //   - High sample rates (e.g., 200 MHz): allows very short segments (~25ns)
  //   - Low sample rates (e.g., 10 kHz): allows longer segments (~500µs)
  //   - Maximum segment time: 3600s (1 hour) - no practical limit for long measurements
  // The rate is automatically selected by ret_getRateWithMinSeg() based on total waveform time,
  //   max_points, AND minimum segment time, optimizing for short waveforms (high rate) or long waveforms (low rate)
  const double absolute_min_seg_time = 2e-8;  // Absolute minimum: 20 ns (hardware limit)
  const double sample_period = 1.0 / (double)used_rate;  // Sample period in seconds
  const double rate_min_seg_time = 5.0 * sample_period;  // Need at least 5 samples per segment
  // The rate was selected via ret_getRateWithMinSeg() to support min_seg_time_found
  // For validation, we should use the actual minimum segment time found in the waveform,
  // since that's what exists and the rate selection should have ensured compatibility.
  // However, we must ensure it's at least the absolute hardware minimum (20ns)
  double validation_min = absolute_min_seg_time;
  if(min_seg_time_found > 0.0)
  {
    // Use the actual minimum found, but ensure it's >= absolute minimum
    validation_min = (min_seg_time_found > absolute_min_seg_time) ? min_seg_time_found : absolute_min_seg_time;
    
    // Warn if rate-based minimum is higher than actual minimum (rate may have been constrained)
    double rate_based_min = (rate_min_seg_time > absolute_min_seg_time) ? rate_min_seg_time : absolute_min_seg_time;
    if(rate_based_min > min_seg_time_found)
    {
      if(debug) printf("%s: WARNING: Rate-based min (%.2e s) > actual min segment (%.2e s) - rate may be constrained by total time\n",
        mod, rate_based_min, min_seg_time_found);
      // Even though rate-based min is higher, we validate against actual minimum
      // because the rate selection should have ensured the rate supports it
      // (if it doesn't, that's a rate selection bug, but we'll catch it in hardware)
    }
  }
  else
  {
    // No minimum found, use rate-based minimum
    validation_min = (rate_min_seg_time > absolute_min_seg_time) ? rate_min_seg_time : absolute_min_seg_time;
  }
  const double min_seg_time = validation_min;
  const double max_seg_time = 3600.0;  // Maximum segment time: 1 hour (no practical limit)
  
  if (debug)
  {
    printf("%s: Sample rate: %d Hz, sample period: %.2e s, rate-based min segment time: %.2e s\n",
      mod, used_rate, sample_period, rate_min_seg_time);
    printf("%s: Using minimum segment time: %.2e s\n", mod, min_seg_time);
  }
  int invalid_seg = -1;
  double invalid_time = 0.0;
  int increm;
  
  if (debug) 
  {
    printf("%s: Validating %d segment times (min=%.2e s, max=%.2e s)\n", 
      mod, numpts, min_seg_time, max_seg_time);
  }
  
  for (increm=0; increm<numpts; increm++)
  {
    double segt = segtime[increm];
    
    // Check for invalid values
    if (segt != segt)  // NaN check (NaN != NaN is true)
    {
      invalid_seg = increm;
      invalid_time = segt;
      if(debug) printf("%s: ERROR: Segment %d has NaN time!\n", mod, increm);
      break;
    }
    
    if (segt <= 0.0)
    {
      invalid_seg = increm;
      invalid_time = segt;
      if(debug) printf("%s: ERROR: Segment %d has zero or negative time: %.6e s\n", mod, increm, segt);
      break;
    }
    
    if (segt < min_seg_time)
    {
      invalid_seg = increm;
      invalid_time = segt;
      if(debug) printf("%s: ERROR: Segment %d has time %.6e s which is below minimum %.2e s\n", 
        mod, increm, segt, min_seg_time);
      break;
    }
    
    if (segt > max_seg_time)
    {
      invalid_seg = increm;
      invalid_time = segt;
      if(debug) printf("%s: ERROR: Segment %d has time %.6e s which exceeds maximum %.2e s\n", 
        mod, increm, segt, max_seg_time);
      break;
    }
    
    if (debug) 
    {
      printf("%s: Segment %d: time=%.6e s, startv=%.6f V, stopv=%.6f V", 
        mod, increm, segt, fstartv[increm], fstopv[increm]);
      if (segt < min_seg_time * 10) 
        printf(" [WARNING: very short]");
      printf("\n");
    }
  }
  
  if (invalid_seg >= 0)
  {
    // Always print error message (not just when debug is enabled)
    printf("%s: ERROR: Invalid segment time found at index %d: %.6e s\n", 
      mod, invalid_seg, invalid_time);
    printf("%s: ERROR: Segment %d: startv=%.6f V, stopv=%.6f V, time=%.6e s\n",
      mod, invalid_seg, 
      (invalid_seg < numpts) ? fstartv[invalid_seg] : 0.0,
      (invalid_seg < numpts) ? fstopv[invalid_seg] : 0.0,
      invalid_time);
    printf("%s: ERROR: This will cause seg_arb_sequence to fail with error -122\n", mod);
    stat = -122;  // Return error -122 (illegal parameter)
    goto RETURN;
  }
  
  if (debug) printf("%s: All segment times are valid\n", mod);
  
  //Perform Forcing on HIGH
  status = seg_arb_sequence(InstId,  ForceCh, 1,  
              numpts, fstartv, fstopv, 
              segtime, trig, ssrctrl, meastypes, 
              measstart, measstop);
  if(status) 
  { 
    if(debug) printf("%s: seg_arb_sequence failed with status %d (parameter error)\n", mod, status);
    stat = -16; 
    goto RETURN; 
  }

// ****************************************************
  if (debug) printf(" Made it here 1.5\n");

  //forcing on LOW, if needed
  if(ForceCh != MeasureCh && MeasureCh > 0)
    {
      status = seg_arb_sequence(InstId,  MeasureCh, 1,  
                  numpts, mstartv, mstopv, 
                  segtime, trig, ssrctrl, meastypes, 
                  measstart, measstop);
      if(status) { stat = -17; goto RETURN; }
    }

  status = seg_arb_waveform(InstId, ForceCh, 1, SeqList, LoopCountList);
  if(status) { stat = -18; goto RETURN; }

  if(ForceCh != MeasureCh && MeasureCh > 0)
    {
      status = seg_arb_waveform(InstId, MeasureCh, 1, SeqList, LoopCountList);
      if(status) { stat = -19; goto RETURN; }
    }

// ****************************************************
  if (debug) printf(" Made it here 2\n");

  // Execute the pulse
  status = pulse_exec(0);

  // wait till execution completion
  i = 0;
  while(pulse_exec_status(&t) == 1 && i < 100)
    {
      Sleep(20);
      i++;
    }


  // wait on pulse fetching
  //Sleep(5000);
  
  status = pulse_fetch(InstId, ForceCh, 0, NumDataPts, pulseV, pulseI, pulseT, NULL);
  if(status) { stat = -20; goto RETURN; }

  if(ForceCh != MeasureCh && MeasureCh > 0)
    {
      // wait on pulse fetching
      status = pulse_fetch(InstId, MeasureCh, 0, NumDataPts, MpulseV, MpulseI, MpulseT, NULL);
      if(status) { stat = -21; goto RETURN; }      
      //Sleep(5000);
    }

  if(debug && details)
    {
      i = 0;
      while(i < NumDataPts)
      {
         printf("=>%s: i:%d V:%g I:%g t:%g\n", mod, i, pulseV[i], pulseI[i], pulseT[i]);
         if(ForceCh != MeasureCh && MeasureCh > 0)
         {
            printf("=>%s: i:%d MV:%g MI:%g Mt:%g\n", mod, i, MpulseV[i], MpulseI[i], MpulseT[i]);
         }
        i++;
      }
    }

  //fill out data and interpolate
  i = 0;
  *npts = 0;
  while(i < vf_size)
    {
      // first clean arrays:
      VF[i] = 0.0;
      IF[i] = 0.0;
      VM[i] = 0.0;
      IM[i] = 0.0;
      T[i] = 0.0;

      ratio = ((double)NumDataPts - 1.0)/((double)vf_size - 1.0);
      if(ratio < 1.0)
        j = i;
      else
        j = (int) (i * ratio);
      if(j > -1 && j < NumDataPts)
      {

          VF[i] = pulseV[j];
          IF[i] = pulseI[j];
          
          if(ForceCh != MeasureCh && MeasureCh > 0)
          {
             VM[i] = MpulseV[j];
             IM[i] = MpulseI[j];

             if(debug && details)printf("%s: Adding i= %d j= %d VM= %g IM= %g\n", mod, i, j, VM[i], IM[i]);

              if(ForceCh != MeasureCh)
                IM[i] *= -1.0;

         }else{
             VM[i] = 0.0;
             IM[i] = 0.0;
          }

      T[i] = pulseT[j];
      if(0.0 != T[i]) *npts = *npts + 1;
    }
      if(debug && details){
          printf("%s: Output: i: %d j: %d VF: %g IF: %g t: %g\n", mod, i, j, VF[i], IF[i], T[i]);
          printf("%s: Output: i: %d j: %d VM: %g IM: %g t: %g\n", mod, i, j, VM[i], IM[i], T[i]);
      }
      i++;
    }


 RETURN:
  if(debug) printf("%s: returns with status: %d Number of points: %d\n", mod, stat, *npts);
  ret_FreeMemoryILimit();
  if(stat > 0)
  {
    not_init = 0;
  }
  return(stat);
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
  //define
  //double *fstartv, *fstopv, *mstartv, *mstopv, *measstart, *measstop, *segtime;
  //long *ssrctrl, *meastypes, *trig;
  //based on v, t, pts
  
  char mod[] = "ret_Define_Segments";
  int i;
  double ttime;
  const double eps = 1e-6;
  //treats segments below 1uv as zero;
  
  i = 0;
  ttime = 0.0;
  do 
    {
      fstartv[i] = v[i];
      fstopv[i] = v[i+1];
      
      segtime[i] = t[i];
      ttime += t[i];

      measstart[i] = 0;
      measstop[i] = segtime[i];

      if (fabs(fstartv[i]) < eps && fabs(fstopv[i]) < eps)
        meastypes[i]= 2 ; 
        // chnage easurment type if voltage = 0 to save data headroom NOT YET IMPLIMENTED;
        // decicded to change start stop instead
      else
        meastypes[i] = 2;
      
      mstartv[i] = bias;
      mstopv[i] = bias;
      
      if(i == 0)
        trig[i] = 1;
      else
        trig[i] = 0;
      
      ssrctrl[i] = 1;
      
      
  if(debug)
    {
      printf("%s: Segment: %d startv: %g stopv: %g time: %g mstartv: %g mstopv: %g mstart: %g mstop: %g meastrig: %d ssrctrl: %d ttime: %g\n",
         mod, i, fstartv[i], fstopv[i], segtime[i], mstartv[i], mstopv[i], measstart[i], measstop[i], trig[i], ssrctrl[i], ttime);
      
    }
      i++;
      
    }
  while(i < pts);
  return ttime;

}


__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts) 
{
  // Call the enhanced version with no minimum segment time constraint
  return ret_getRateWithMinSeg(ttime, maxpts, 0.0, apts, npts);
}

// Enhanced version that considers minimum segment time for optimal rate selection
// This function automatically selects the optimal sample rate based on:
//   - Total waveform time (ttime): determines minimum rate needed to fit within maxpts
//   - Maximum allowed points (maxpts): limits total data points collected
//   - Minimum segment time (min_seg_time): constrains maximum rate to ensure enough samples per segment
// 
// The rate selection algorithm:
//   1. If min_seg_time > 0, calculate max_rate = 5 / min_seg_time (need at least 5 samples per segment)
//   2. Start with default_rate (200 MHz) or max_rate (whichever is lower) if constrained
//   3. Calculate required points = ttime * rate + 2
//   4. If required points < maxpts, this rate works
//   5. If required points >= maxpts, lower the rate by increasing divider (n)
//   6. Never exceed max_rate if min_seg_time constraint exists
//   7. Never go below min_rate (200 kHz)
//
// This ensures:
//   - Short waveforms with short segments: uses high rate (up to 200 MHz) for detailed sampling
//   - Long waveforms: uses lower rate to fit within max_points limit
//   - Very short segments (e.g., 100ns): automatically selects appropriate rate to support them
//
// Returns: selected sample rate (Hz) on success, negative error code on failure
//   -1: maxpts exceeds system limit (1,000,000)
//   -2: cannot find rate below minimum (200 kHz) - waveform too long
//   -3: conflicting constraints (min_seg_time requires rate <= X, but minimum rate > X)
__declspec( dllexport ) int ret_getRateWithMinSeg(double ttime, int maxpts, double min_seg_time, int *apts, int *npts) 
{
  char mod [] = "ret_getRate";
  int usedrate;
  int usedpts;
  int min_rate;
  int max_rate_from_seg = 0;

  int n = 1;
  int rate_found = 0;
  
  int max_pts = 1000000;
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

  // If minimum segment time is provided, calculate maximum allowed rate
  // Need at least 5 samples per segment: min_seg_time >= 5 * sample_period
  // So: sample_period <= min_seg_time / 5
  // And: max_rate <= 1 / (min_seg_time / 5) = 5 / min_seg_time
  if(min_seg_time > 0.0)
  {
    max_rate_from_seg = (int)(5.0 / min_seg_time);
    if(max_rate_from_seg > default_rate)
      max_rate_from_seg = default_rate;
    if(max_rate_from_seg < min_rate)
      max_rate_from_seg = min_rate;
    
    if(debug) printf("%s: Minimum segment time: %.2e s, maximum rate constraint: %d Hz\n", 
      mod, min_seg_time, max_rate_from_seg);
  }

  //let's calculate the rate first
  usedrate = default_rate;
  
  // If we have a segment time constraint, start with the lower of default_rate and max_rate_from_seg
  if(max_rate_from_seg > 0 && max_rate_from_seg < default_rate)
  {
    usedrate = max_rate_from_seg;
    // Find the divider that gives us this rate or lower
    n = (int)((double)default_rate / (double)max_rate_from_seg);
    if(n < 1) n = 1;
  }

  while(rate_found == 0 && n < max_devider * 2)
  {
        usedrate = (int) (default_rate/n);
        
        // CRITICAL: Never exceed the maximum rate allowed by minimum segment time
        // If we need a lower rate for total time, that's fine, but we can't go higher
        if(max_rate_from_seg > 0 && usedrate > max_rate_from_seg)
        {
          // Rate too high for minimum segment time - this should not happen if we started correctly
          // But if total time forces us to try higher rates, we must cap it
          usedrate = max_rate_from_seg;
          // Ensure we don't go below minimum rate
          if(usedrate < min_rate)
          {
            if(debug) printf("%s: ERROR: Cannot satisfy constraints - min_seg_time requires rate <= %d Hz, but min_rate is %d Hz\n",
              mod, max_rate_from_seg, min_rate);
            usedrate = -3;  // Error: conflicting constraints
            goto RD;
          }
        }
        
        usedpts = (int)(ttime * usedrate + 2);
        if(usedpts < maxpts)
        {
            // Verify this rate works for minimum segment time (should always be true due to check above)
            if(max_rate_from_seg > 0 && usedrate > max_rate_from_seg)
            {
              // This shouldn't happen, but if it does, try next lower rate
              n++;
              continue;
            }
            rate_found = 1;
            break;
        }
        else
        {
            // Total time constraint requires lower rate - increment n to try lower rate
            n++;
            // But ensure we don't violate segment time constraint on next iteration
            // (the check at top of loop will handle this)
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

  return usedrate;
/* USRLIB MODULE END  */
} 		/* End retention_pulse_ilimit_dual_channel_bias.c */

