/* SMU Voltage-Current Linear Sweep Module
 *
 * Purpose:
 * --------
 * This module performs a simple linear voltage-current (IV) sweep using the SMU
 * (Source Measurement Unit) of the Keithley 4200A-SCS. It sweeps linearly from
 * Vstart to Vstop with a specified number of points, forcing voltage and
 * measuring current at each step.
 *
 * Operation:
 * ----------
 * 1. Validates input parameters (Vstart != Vstop, array sizes match)
 * 2. Calculates voltage step size: vstep = (Vstop - Vstart) / (NumVPoints - 1)
 * 3. Loops through NumPoints:
 *    - Forces voltage using forcev(SMU1, v)
 *    - Measures current using measi(SMU1, &Imeas[i])
 *    - Stores forced voltage in Vforce[i]
 *    - Increments voltage by vstep
 * 4. Returns 0 on success, negative error code on failure
 *
 * Parameters:
 * -----------
 * - Vstart: Starting voltage (V), range: -200 to 200 V
 * - Vstop: Stopping voltage (V), range: -200 to 200 V
 * - Imeas: Output array for measured current (A), size NumIPoints
 * - NumIPoints: Size of Imeas array (must equal NumVPoints)
 * - Vforce: Output array for forced voltage (V), size NumVPoints
 * - NumVPoints: Size of Vforce array (must equal NumIPoints)
 *
 * Note: For n increments, specify n+1 array size (for both NumIPoints and NumVPoints).
 * Example: For 10 voltage steps from 0V to 5V, use NumPoints = 11.
 *
 * Error Codes:
 * ------------
 * - -1: Vstart == Vstop (sweep range is zero)
 * - -2: NumIPoints != NumVPoints (array size mismatch)
 * - 0: Success
 */

/* USRLIB MODULE INFORMATION

	MODULE NAME: SMU_VIsweep
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 6
	ARGUMENTS:
		Vstart,	double,	Input,	0,	-200,	200
		Vstop,	double,	Input,	5,	-200,	200
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumIPoints,	int,	Input,	11,	,	
		Vforce,	D_ARRAY_T,	Output,	,	,	
		NumVPoints,	int,	Input,	11,	,	
	INCLUDES:
#include "keithley.h"
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION

	END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"

/* USRLIB MODULE MAIN FUNCTION */
int SMU_VIsweep( double Vstart, double Vstop, double *Imeas, int NumIPoints, double *Vforce, int NumVPoints )
{
/* USRLIB MODULE CODE */
/* VSweep module

--------------

Sweeps through specified V range & measures I, using specified number of points.

Places forced voltage & measured current values (Vforce and Imeas) in output arrays.

NOTE For n increments, specify n+1 array size (for both NumIPoints and NumVPoints).


*/

double vstep, v; /* Declaration of module internal variables. */

int i;

if ( (Vstart == Vstop) ) /* Stops execution and returns -1 if */

return( -1 ); /* sweep range is zero. */


if ( (NumIPoints != NumVPoints) ) /* Stops execution and returns -2 if */

return( -2 ); /* V and I array sizes do not match. */


vstep = (Vstop-Vstart) / (NumVPoints -1); /* Calculates V-increment size. */


for(i=0, v = Vstart; i < NumIPoints; i++) /* Loops through specified number of */

/* points. */

{

forcev(SMU1, v); /* LPTLib function forceX, which forces a V or I. */

measi(SMU1, &Imeas[i]); /* LPTLib function measX, which measures a V or I. */

/* Be sure to specify the *address* of the array. */


Vforce[i] = v; /* Returns Vforce array for display in UTM Sheet. */


v = v + vstep; /* Increments the forced voltage. */

}


return( 0 ); /* Returns zero if execution Ok.*/
/* USRLIB MODULE END  */
} 		/* End SMU_VIsweep.c */


