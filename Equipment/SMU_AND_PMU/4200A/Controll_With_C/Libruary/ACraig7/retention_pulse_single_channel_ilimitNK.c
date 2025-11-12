/* USRLIB MODULE INFORMATION

	MODULE NAME: retention_pulse_single_channel_ilimitNK
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 36
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
		AuxCh,	long,	Input,	0,	0,	2
		AuxVRange,	double,	Input,	5,	5,	40
		AuxILimit,	double,	Input,	0.0,	0.0,	
		AuxVLow,	double,	Input,	0.0,	-20,	20
		AuxVHigh,	double,	Input,	1.0,	-20,	20
		AuxRiseTime,	double,	Input,	3e-8,	2e-8,	1
		AuxFallTime,	double,	Input,	3e-8,	2e-8,	1
		AuxPulseWidth,	double,	Input,	1e-6,	2e-8,	1
		AuxPreDelay,	double,	Input,	0.0,	0.0,	1
		AuxPostDelay,	double,	Input,	0.0,	0.0,	1
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

double *aux_startv = NULL;
double *aux_stopv = NULL;
double *aux_measstart = NULL;
double *aux_measstop = NULL;
double *aux_segtime = NULL;
long *aux_ssrctrl = NULL;
long *aux_meastypes = NULL;
long *aux_trig = NULL;
static int aux_capacity = 0;

static int not_init = 1;

void ret_AllocateMemoryILimit(int npts);
void ret_AllocateMeasArraysILimit(int npts);
void ret_FreeMemoryILimit(void);
double ret_Define_SegmentsILimit(double *v, double *t, int pts, double bias);
BOOL LPTIsInCurrentConfiguration(char* hrid);

__declspec( dllexport ) int ret_getRate(double ttime, int maxpts, int *apts, int *npts) ;

static void ret_AllocateAuxArrays(int segments);
static void ret_FreeAuxArrays(void);
static int ret_BuildAuxPulse(double vlow, double vhigh, double riseTime, double fallTime, double width, double preDelay, double postDelay);

int debug = 0;
int details = 0;
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: retention_pulse_single_channel_ilimitNK
=========================

Description
-----------
The purpose of this routine is to simplify the generation of segments using the PMU, and 
collect forced voltage and current values from both the ForceCh and MeasureCh channels. 
The basic scenario used is a connection of the ForceCh to the high side of the DUT while 
MeasureCh is connected to the low side of the DUT. The segments are created based on 
the settings provided by the operator within the 'Volts' and 'Times' input arrays, and measurements 
are returned via of the voltage(VF and VM) and current (IF and IM) output arrays for both channels.
An optional auxiliary channel can be driven with a user-defined seg_arb pulse (configured via the Aux*
parameters) to provide an additional source-only waveform.

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
:::::: Returns the actual number of collected data points.

AuxCh 
::::::: Optional auxiliary channel identifier. Set to 0 to disable the auxiliary waveform.

AuxVRange 
::::::: Voltage range applied to the auxiliary channel.

AuxILimit 
::::::: Current compliance for the auxiliary channel (0.0 disables limiting).

AuxVLow / AuxVHigh 
::::::: Voltage levels for the auxiliary pulse.

AuxRiseTime / AuxFallTime 
::::::: Edge durations for the auxiliary pulse.

AuxPulseWidth 
::::::: Width of the auxiliary pulse while at the high level.

AuxPreDelay / AuxPostDelay 
::::::: Time at the low level before and after the auxiliary pulse.

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
-141   | Error setting compliance for ForceCh
-142   | Error setting compliance for MeasureCh
-143   | Error setting compliance for AuxCh
-144   | Error in pulse_load for AuxCh
-145   | Error in pulse_ranges for AuxCh
-146   | Error in pulse_burst_count for AuxCh
-147   | Error in pulse_output for AuxCh
-148   | Error in seg_arb_sequence for AuxCh
-149   | Error in seg_arb_waveform for AuxCh
-212   | Error allocating auxiliary waveform buffers

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
int retention_pulse_single_channel_ilimitNK( char *InstrName, long ForceCh, double ForceVRange, double ForceIRange, double iFLimit, double iMLimit, long MeasureCh, double MeasureVRange, double MeasureIRange, long AuxCh, double AuxVRange, double AuxILimit, double AuxVLow, double AuxVHigh, double AuxRiseTime, double AuxFallTime, double AuxPulseWidth, double AuxPreDelay, double AuxPostDelay, int max_pts, double MeasureBias, double *Volts, int volts_size, double *Times, int times_size, double *VF, int vf_size, double *IF, int if_size, double *VM, int vm_size, double *IM, int im_size, double *T, int t_size, int *npts )
{
/* USRLIB MODULE CODE */
  int stat = 1;
  int status;
  INSTR_ID InstId;
  double t;
  int i, j;
  char mod[] = "retention_pulse_single_channel_ilimitNK";
  long SeqList[1] = {1};
  double LoopCountList[1] = {1};
  int numpts;
  int NumDataPts;
  double ttime;
  int allocate_pts = 0;
  int used_rate = 0;
  double ratio;
  long auxChLocal = AuxCh;
  double auxVRange = AuxVRange;
  double auxILimit = AuxILimit;
  double auxVLow = AuxVLow;
  double auxVHigh = AuxVHigh;
  double auxRiseTime = AuxRiseTime;
  double auxFallTime = AuxFallTime;
  double auxPulseWidth = AuxPulseWidth;
  double auxPreDelay = AuxPreDelay;
  double auxPostDelay = AuxPostDelay;
  int auxSegments = 0;

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

  //determine required number of points and required rate
  //number of points should not exceed user defined max_pts and function max: MAXPTS (10000)

  used_rate = ret_getRate(ttime, max_pts, &allocate_pts, &NumDataPts);
  if(0 > used_rate)
  {
     if(debug) printf("%s: used rate is invalid!\n", mod);
     stat = -33;
     goto RETURN;
  }

  ret_AllocateMeasArraysILimit(allocate_pts);

  if(auxChLocal == ForceCh)
  {
    if(debug) printf("%s: aux channel matches force channel; disabling aux pulse\n", mod);
    auxChLocal = 0;
  }
  // treat 0 or negative as disabled
  if(auxChLocal > 0)
  {
    ret_AllocateAuxArrays(5);
    if(aux_startv == NULL || aux_stopv == NULL || aux_segtime == NULL ||
       aux_trig == NULL || aux_ssrctrl == NULL || aux_meastypes == NULL ||
       aux_measstart == NULL || aux_measstop == NULL)
    {
      stat = -212;
      goto RETURN;
    }

    auxSegments = ret_BuildAuxPulse(auxVLow, auxVHigh, auxRiseTime, auxFallTime,
                                    auxPulseWidth, auxPreDelay, auxPostDelay);
    if(debug)
    {
      printf("%s: aux channel %ld, built %d segments (pre=%g, width=%g, post=%g)\n",
             mod, auxChLocal, auxSegments, auxPreDelay, auxPulseWidth, auxPostDelay);
      if(auxSegments > 0)
      {
        int dump = auxSegments < 5 ? auxSegments : 5;
        int s;
        for(s = 0; s < dump; ++s)
        {
          printf("%s: aux seg %d start=%g stop=%g time=%g measType=%ld ssr=%ld trig=%ld\n",
                 mod, s, aux_startv[s], aux_stopv[s], aux_segtime[s],
                 aux_meastypes[s], aux_ssrctrl[s], aux_trig[s]);
        }
      }
    }
    if(auxSegments <= 0)
    {
      if(debug) printf("%s: aux pulse has no segments; disabling aux channel\n", mod);
      auxChLocal = 0;
    }
  }
  else
  {
    auxSegments = 0;
  }

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

      if(auxChLocal > 0)
      {
          status = rpm_config(InstId, auxChLocal, KI_RPM_PATHWAY, KI_RPM_PULSE);
          if(status)
          {
              if(debug)printf("RPM init failed for AuxCh %ld (status %d); disabling aux pulse\n", auxChLocal, status);
              auxChLocal = 0;
              auxSegments = 0;
          }
          else if(debug)printf("RPM is initialized for AuxCh! %s (0 or null is good)\n", status);
      }

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
  if(auxChLocal > 0)
  {
    if(auxILimit == 0.0)
    {
        OpenLimit(InstId);
    }
    else
    {
        status = Set_RPM_ICompliance( InstId, auxChLocal, auxILimit);
         if(debug)printf("%s: called Set_RPM_ICompliance for AuxCh:%ld and limit %g. Returned:%d\n",
         mod, auxChLocal, auxILimit, status);
         if(status)
         {
             if(debug)printf("%s: AuxCh compliance failed (status %d); disabling aux pulse\n", mod, status);
             auxChLocal = 0;
             auxSegments = 0;
         }
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
    
  if(auxChLocal > 0)
    {
      if(not_init)
      {
          status = pulse_load(InstId, auxChLocal, 1e+6);
          if(status) { stat = -144; goto RETURN; }
      }

      status = pulse_ranges(InstId, auxChLocal, 
              auxVRange, PULSE_MEAS_FIXED, 
              auxVRange, PULSE_MEAS_FIXED, 
              ForceIRange);
      if(status) { stat = -145; goto RETURN; }

      if(not_init)
      {
          status = pulse_burst_count(InstId, auxChLocal, 1);
          if(status) { stat = -146; goto RETURN; }

          status = pulse_output(InstId, auxChLocal, 1);
          if(status) { stat = -147; goto RETURN; }
      }
    }
    
  status = pulse_sample_rate(InstId, used_rate);      
  if(status) if(status) { stat = -15; goto RETURN; }

// ****************************************************
  if (debug) printf(" Made it here 1\n");
  // problem is here with segtime

  int increm=0;
  if (debug) 
  {
  for (increm=0; increm<numpts; increm++)    //was 20 made 31 6 pulses .....but just for debugging purposes
       { 
        printf("increm: %d, seg time is %e \n",increm, segtime[increm]);
        }
   }
  //Perform Forcing on HIGH
  status = seg_arb_sequence(InstId,  ForceCh, 1,  
              numpts, fstartv, fstopv, 
              segtime, trig, ssrctrl, meastypes, 
              measstart, measstop);
  if(status) { stat = -16; goto RETURN; }

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
  if(auxChLocal > 0 && auxSegments > 0)
    {
      if(debug)
        printf("%s: programming aux seg_arb_sequence on channel %ld (%d segments)\n", mod, auxChLocal, auxSegments);
      status = seg_arb_sequence(InstId,  auxChLocal, 1,
                  auxSegments, aux_startv, aux_stopv,
                  aux_segtime, aux_trig, aux_ssrctrl, aux_meastypes,
                  aux_measstart, aux_measstop);
      if(status) { stat = -148; goto RETURN; }
    }

  status = seg_arb_waveform(InstId, ForceCh, 1, SeqList, LoopCountList);
  if(status) { stat = -18; goto RETURN; }

  if(ForceCh != MeasureCh && MeasureCh > 0)
    {
      status = seg_arb_waveform(InstId, MeasureCh, 1, SeqList, LoopCountList);
      if(status) { stat = -19; goto RETURN; }
    }
  if(auxChLocal > 0 && auxSegments > 0)
    {
      if(debug)
        printf("%s: programming aux seg_arb_waveform on channel %ld\n", mod, auxChLocal);
      status = seg_arb_waveform(InstId, auxChLocal, 1, SeqList, LoopCountList);
      if(status) { stat = -149; goto RETURN; }
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
  if(debug)
  {
    int dump = NumDataPts < 5 ? NumDataPts : 5;
    int k;
    printf("%s: force fetch returned %d points\n", mod, NumDataPts);
    for(k = 0; k < dump; ++k)
    {
      printf("%s: force pt %d: V=%g I=%g T=%g\n", mod, k, pulseV[k], pulseI[k], pulseT[k]);
    }
  }

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

    ret_FreeAuxArrays();
}

static void ret_AllocateAuxArrays(int segments)
{
    ret_FreeAuxArrays();

    if(segments <= 0)
    {
        aux_capacity = 0;
        return;
    }

    aux_capacity = segments;
    aux_startv = (double *)calloc(segments, sizeof(double));
    aux_stopv = (double *)calloc(segments, sizeof(double));
    aux_measstart = (double *)calloc(segments, sizeof(double));
    aux_measstop = (double *)calloc(segments, sizeof(double));
    aux_segtime = (double *)calloc(segments, sizeof(double));
    aux_trig = (long *)calloc(segments, sizeof(long));
    aux_ssrctrl = (long *)calloc(segments, sizeof(long));
    aux_meastypes = (long *)calloc(segments, sizeof(long));
}

static void ret_FreeAuxArrays(void)
{
    if(NULL != aux_startv) { free(aux_startv); aux_startv = NULL; }
    if(NULL != aux_stopv) { free(aux_stopv); aux_stopv = NULL; }
    if(NULL != aux_measstart) { free(aux_measstart); aux_measstart = NULL; }
    if(NULL != aux_measstop) { free(aux_measstop); aux_measstop = NULL; }
    if(NULL != aux_segtime) { free(aux_segtime); aux_segtime = NULL; }
    if(NULL != aux_trig) { free(aux_trig); aux_trig = NULL; }
    if(NULL != aux_ssrctrl) { free(aux_ssrctrl); aux_ssrctrl = NULL; }
    if(NULL != aux_meastypes) { free(aux_meastypes); aux_meastypes = NULL; }
    aux_capacity = 0;
}

static int ret_BuildAuxPulse(double vlow, double vhigh, double riseTime, double fallTime,
                             double width, double preDelay, double postDelay)
{
    int idx = 0;

    if(aux_capacity <= 0 || aux_startv == NULL || aux_stopv == NULL || aux_segtime == NULL ||
       aux_trig == NULL || aux_ssrctrl == NULL || aux_meastypes == NULL ||
       aux_measstart == NULL || aux_measstop == NULL)
    {
        return 0;
    }

#define ADD_AUX_SEG(duration, startV, stopV) \
    do { \
        if((duration) > 0.0 && idx < aux_capacity) { \
            aux_startv[idx] = (startV); \
            aux_stopv[idx] = (stopV); \
            aux_segtime[idx] = (duration); \
            aux_measstart[idx] = 0.0; \
            aux_measstop[idx] = 0.0; \
            aux_meastypes[idx] = 0; \
            aux_trig[idx] = 0; \
            aux_ssrctrl[idx] = 1; \
            idx++; \
        } \
    } while(0)

    ADD_AUX_SEG(preDelay, vlow, vlow);
    ADD_AUX_SEG(riseTime, vlow, vhigh);
    ADD_AUX_SEG(width, vhigh, vhigh);
    ADD_AUX_SEG(fallTime, vhigh, vlow);
    ADD_AUX_SEG(postDelay, vlow, vlow);

#undef ADD_AUX_SEG

    return idx;
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
        meastypes[i]= 3 ; 
        // chnage easurment type if voltage = 0 to save data headroom NOT YET IMPLIMENTED;
        // decicded to change start stop instead
      else
        meastypes[i] = 3;
      
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

  return usedrate;
/* USRLIB MODULE END  */
} 		/* End retention_pulse_single_channel_ilimitNK.c */

