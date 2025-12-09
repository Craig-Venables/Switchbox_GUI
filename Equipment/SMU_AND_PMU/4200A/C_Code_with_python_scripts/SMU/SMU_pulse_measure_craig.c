/* USRLIB MODULE INFORMATION

	MODULE NAME: SMU_pulse_measure_craig
	MODULE RETURN TYPE: double 
	NUMBER OF PARMS: 9
	ARGUMENTS:
		initialize,	int,	Input,	0,	0,	1
		logMessages,	int,	Input,	1,	0,	1
		widthTime,	double,	Input,	1e-4,	40e-9,	480
		Amplitude,	double,	Input,	1.0,	-20,	20
		Irange,	double,	Input,	1e-2,	0.0,	1
		Icomp,	double,	Input,	0.0,	-10e-3,	10e-3
		biasV,	double,	Input,	0.2,	-20,	20
		biasHold,	double,	Input,	1e-3,	40e-9,	480
		measResistance,	double *,	Output,	,	,	
	INCLUDES:
#include "keithley.h"
#include "nvm.h"

	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">

Module: SMU_pulse_measure_craig
===================

Description
-----------
Note: In the test it is assumed that RPM1 is linked with SMU1 and RPM2 is linked with SMU2.

It is assumed that RPM1 (Channel 1) is connected to the side of the DUT with higher
capacitance, such as chuck, substrate, which is usually a *lower/bottom side*.

RPM2 (Channel 2) should be connected on the opposite side, which is usually is
*top side* to minimize parasitic current transients.

RPM2 forces 0 V and is used to measure current. Voltage bias polarities should
be applied, as if bias is applied from the top to simulate standard SMU/DC testing.

Polarities of the forced bias and measured current are inverted in the code.

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
#include "nvm.h"


/* USRLIB MODULE MAIN FUNCTION */
double SMU_pulse_measure_craig( int initialize, int logMessages, double widthTime, double Amplitude, double Irange, double Icomp, double biasV, double biasHold, double *measResistance )
{
/* USRLIB MODULE CODE */


// ************** NOTE: DO NOT TRY TO COMPILE WITH KXCI OPEN, it always give linker errors    **********************

        char mod[] = "SMU_pulse_measure_craig";
        int stat = -1, j;
        int SMU1;
        double riseTime=1e-7; //default = 1e-4, Min=40e-9,Max=1
        double compCH=1; // sets the compliance channel, default = 1, Min=1,Max=1
        int error=0;
        double vsat,isat,resistance=0;

    measResistance=&resistance; //so clarius console message can be turned off and a value is still returned



    if (logMessages)
    {
   // printf("\n");
    printf("\n Hello - Pulse Measurement \n");
    printf("Initialize  = %i (1=yes, 0=no)\n",initialize);
    printf("Print Log Messages  = %i (1=yes, 0=no)\n",logMessages);
    printf("Pulse Width (s) = %f \n",widthTime);
    printf("Amplitude (V) = %f \n",Amplitude);
    printf("Current Range = %f \n",Irange);
    printf("Compliance current = %f \n",Icomp);
    printf("Bias V (pre/post) = %f \n",biasV);
    printf("Bias hold (s) = %f \n",biasHold);

    }

    //Setup NVM structures
        NVMS *nvm;
                
    //CHECK INPUTS FOR ERRORS!
      if (logMessages) nlog("%s: input checking\n", mod);


        //Check if risetime violates slew rate of 500us/V
        if (riseTime > fabs(Amplitude * .0005)) {
                if (logMessages) nlogErr("%s: Unattainable slew rate\n", mod);
                stat = SLEW_RATE_ERROR;
                if (logMessages) printf("Unattainable slew rate : quitting measurement\n");
                error=1;
                goto RETURN;
        }

        //make sure minimum widths are 20 ns
        if (widthTime < 2e-8) widthTime = 2e-8;
        if (biasHold  < 2e-8) biasHold  = 2e-8;

        if (fabs(Irange) > 0.01) {
                if (logMessages)nlog("%s: Irange (%g) was set to 0.2\n", mod, Irange);
                Irange = 0.2;
        }

 //STOP CHECKING INPUTS

 //use SMU to apply pulse and measure
    //    enable(TIMER1);
        //Set high SMU
        getinstid("SMU1", &SMU1);

        if (!LPTIsInCurrentConfiguration("SMU1"))
                return(-1);

        //Find Low SMU
        // no second SMU as using GNDU
        //getinstid("SMU2", &SMU2);

        //if (!LPTIsInCurrentConfiguration("SMU1"))
          //      return(-2);

        setmode(SMU1, KI_LIM_MODE, KI_VALUE); // tells SMU to return an indicator or actual value when in limit or over range
      //setmode(SMU2, KI_LIM_MODE, KI_VALUE);


        //switch matrix:

        
if (initialize==1)  {
//only needed if SMU is connected through the RPMS
// rpm_config(PMU1, 1, KI_RPM_PATHWAY, KI_RPM_SMU);
// rpm_config(PMU1, 2, KI_RPM_PATHWAY, KI_RPM_SMU);
 }


        
//set compliance current
        if (Icomp != 0.0) {
                if (1 == compCH)
                    limiti(SMU1, Icomp);
               // else
                //    limiti(SMU2, Icomp);
                }
                
//set current range 
        if (Irange != 0.0) {
                        rangei(SMU1, Irange);
                 //       rangei(SMU2, Irange);
                }

// pre-bias hold
pulsev(SMU1, biasV, biasHold);

// use mpulse to do a pulse and measure at the same time
int mpulse_success;
mpulse_success=mpulse(SMU1,Amplitude,widthTime, &vsat, &isat);      // mpulse (instr id, pulse_amplitude, pulse_duration, double * v_meas, double * i_meas)
resistance=vsat/isat;

// post-bias hold
pulsev(SMU1, biasV, biasHold);



if (logMessages) printf(" mpulse_success = %i \n",mpulse_success);
if (logMessages) printf("Vsat= %f \n",vsat);
if (logMessages) printf("Isat= %E \n",isat);
if (logMessages) printf("Resistance = %E \n",vsat/isat);


// just apply pulse with no measurement (Set / Reset)
//pulsev(SMU1,Amplitude, widthTime);


        //Sweep Completed Successfully
stat = TEST_SUCCESS;


return resistance; 

RETURN:
        //printNVMST();
        if (logMessages) nlog("%s: exiting with status: %d\n", mod, stat);
        if (error==1) {return 0;} else 
          {
          return resistance;   //returns actual resistance based on the measured voltage
          // char buffer[21];
          // sprintf(buffer,"%.3e",vsat/isat);
          // return buffer;  
          }
        return resistance; 
/* USRLIB MODULE END  */
} 		/* End SMU_pulse_measure_craig.c */

