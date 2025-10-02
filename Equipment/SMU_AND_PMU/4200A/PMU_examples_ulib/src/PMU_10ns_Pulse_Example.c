/* USRLIB MODULE INFORMATION

	MODULE NAME: PMU_10ns_Pulse_Example
	MODULE RETURN TYPE: int
	NUMBER OF PARMS: 2
	ARGUMENTS:
		pmu_ch,	int,	Input,	1,	1,	2
		pmu_id,	int,	Input,	1,	1,	2
	INCLUDES:
#include "keithley.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION
<!--MarkdownExtra-->
<link rel="stylesheet" type="text/css" href="file:///C:/s4200/sys/help/InfoPane/stylesheet.css">
Module: PMU_10ns_Pulse_Example
==================
Description
------------
This module sets up the PMU to continuously output pulses with 10ns 
pulse widths. The PMU is in standard pulse mode with the pulse levels 
set at -1V and 1V. This module is intended as a demonstration tool. 

To view output, a scope should be connected. For systems with no RPMs,
the scope should be connected to Ch1 or Ch2 of the PMU. For systems with 
RPMs, the scope should be connected to the force terminal of the desired 
RPM.

For more information, see the Technical Note: Generating 10ns 
Pulse Widths Using the 4225-PMU, located in the Learning Center under
General Application Notes, White Papers and Technical Notes.

Pulse Settings
--------------
The following settings are set in the code. 

Setting       | Value
-------       | -----
Load          | 50ohm
Current Limit | 200mA
Rise Time     | 10ns
Fall Time     | 10ns
Pulse Delay   | 0s
Voltage Range | 5V
Low Voltage   | -1V
High Voltage  | 1V
Period        | 20ns
Width         | 10ns

Inputs
-------
pmu_id
: (int) desired PMU, 1 for PMU1 and 2 for PMU2

pmu_ch
: (int) desired channel, 1 for Ch1 (RPM 1) and 2 for Ch2 (RPM 2)

Return Values
---------------
Value | Description
------|-------------
0     | Test Successful

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"
BOOL LPTIsInCurrentConfiguration(char* hrid);
/* USRLIB MODULE MAIN FUNCTION */
int PMU_10ns_Pulse_Example( int pmu_ch, int pmu_id )
{
/* USRLIB MODULE CODE */
	
	//Pulse Settings
	double setLoad = 50.0;
	double setCurrent = 0.2;
	double setRise = 1e-8;
	double setFall = 1e-8;
	double setDelay = 0.0;
	double setRange = 5.0;
	double setVLow = -1;
	double setVHigh = 1; 
	double setPeriod = 2e-8;
	double setWidth = 1e-8;


	//Find PMU ID
	if (pmu_id == 2) pmu_id = PMU2;
	else pmu_id = PMU1;
	
	//Establish Status Bit
	int status = 0;
	
	//Set RPM to pulse mode - Does nothing if RPMs are not connected
	status = rpm_config(pmu_id, pmu_ch, KI_RPM_PATHWAY, KI_RPM_PULSE);
		if (status != 0) return status;
	
	//Set up the pulse
	status = pg2_init(pmu_id, 0);                             // set to 2 level pulse mode
			if (status != 0) return status;
	status = pulse_init(pmu_id);							  // reset to defaults
			if (status != 0) return status;
	status = pulse_load(pmu_id, pmu_ch, setLoad);		      // set pulse load (ohms)
			if (status != 0) return status;
	status = pulse_current_limit(pmu_id, pmu_ch, setCurrent); // set current limit
			if (status != 0) return status;
	status = pulse_rise(pmu_id, pmu_ch, setRise);	          // set rise time (t)
			if (status != 0) return status;
	status = pulse_fall(pmu_id, pmu_ch, setFall);	          // set fall time (t)
			if (status != 0) return status;
	status = pulse_delay(pmu_id, pmu_ch, setDelay);		      // set pulse delay (s)
			if (status != 0) return status;
	status = pulse_range(pmu_id, pmu_ch, setRange);	          // set voltage range (v)
			if (status != 0) return status;
	status = pulse_vlow(pmu_id, pmu_ch, setVLow);	          // set pulse low volts (v)
			if (status != 0) return status;
	status = pulse_vhigh(pmu_id, pmu_ch, setVHigh);	          // set pulse high volts (v)
			if (status != 0) return status;
	status = pulse_period(pmu_id, setPeriod);				  // set period (t)
			if (status != 0) return status;
	status = pulse_width(pmu_id, pmu_ch, setWidth);	          // set pulse width (t)
	
	//Output the pulse
	status = pulse_output(pmu_id, pmu_ch, 1); //Turn the PMU on
			if (status != 0) return status;
	status = pulse_trig(pmu_id, 1);           //Set to continuously trigger
			if (status != 0) return status;
	status = pulse_output(pmu_id, pmu_ch, 0); //Turn the PMU off
			if (status != 0) return status;

return(OK);
/* USRLIB MODULE END  */
} 		/* End PMU_10ns_Pulse_Example.c */

