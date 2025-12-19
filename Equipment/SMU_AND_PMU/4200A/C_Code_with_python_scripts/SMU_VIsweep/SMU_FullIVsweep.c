/* USRLIB MODULE INFORMATION

	MODULE NAME: SMU_FullIVsweep
	MODULE RETURN TYPE: int 
	NUMBER OF PARMS: 7
	ARGUMENTS:
		Vhigh,	double,	Input,	5,	0,	200
		Vlow,	double,	Input,	-5,	-200,	0
		PointsPerSegment,	int,	Input,	10,	2,	1000
		Imeas,	D_ARRAY_T,	Output,	,	,	
		NumIPoints,	int,	Input,	41,	,	
		Vforce,	D_ARRAY_T,	Output,	,	,	
		NumVPoints,	int,	Input,	41,	,	
	INCLUDES:
#include "keithley.h"
	END USRLIB MODULE INFORMATION
*/
/* USRLIB MODULE HELP DESCRIPTION

SMU Full Voltage-Current Sweep Module
======================================

Performs a complete bidirectional IV sweep: 0V → Vhigh → 0V → Vlow → 0V

Pattern: 0V → Vhigh → 0V → Vlow → 0V
- Vhigh: Positive voltage limit (V), must be >= 0
- Vlow: Negative voltage limit (V), must be <= 0
- PointsPerSegment: Number of points per segment (excluding start point)
  Total points = 4 × PointsPerSegment + 1

Example: Vhigh=5V, Vlow=-5V, PointsPerSegment=10
  Segment 1: 0V → 5V (11 points)
  Segment 2: 5V → 0V (10 points, no duplicate 0V)
  Segment 3: 0V → -5V (10 points, no duplicate 0V)
  Segment 4: -5V → 0V (10 points)
  Total: 41 points

Each segment uses even voltage steps calculated as: vstep = (Vstop-Vstart) / (NumPoints-1)

END USRLIB MODULE HELP DESCRIPTION */
/* USRLIB MODULE PARAMETER LIST */
#include "keithley.h"

/* USRLIB MODULE MAIN FUNCTION */
int SMU_FullIVsweep( double Vhigh, double Vlow, int PointsPerSegment, double *Imeas, int NumIPoints, double *Vforce, int NumVPoints )
{
/* USRLIB MODULE CODE */
/* Full IV Sweep module

--------------

Performs a complete bidirectional IV sweep: 0V → Vhigh → 0V → Vlow → 0V

Uses the same incremental approach as SMU_VIsweep for even voltage steps.

Places forced voltage & measured current values (Vforce and Imeas) in output arrays.

Total points = 4 × PointsPerSegment + 1


*/

int i, status;
double v, vstep;
int expected_points;

/* Validate input parameters */
if ( Vhigh < 0.0 || Vlow > 0.0 )
{
    return( -1 );  /* Invalid voltage limits */
}

if ( NumIPoints != NumVPoints )
{
    return( -2 );  /* Array size mismatch */
}

if ( PointsPerSegment < 2 || PointsPerSegment > 1000 )
{
    return( -4 );  /* Invalid points per segment */
}

/* Calculate expected total points: 4 segments × PointsPerSegment + 1 starting point */
expected_points = 4 * PointsPerSegment + 1;

if ( NumIPoints != expected_points )
{
    return( -3 );  /* Array size doesn't match expected points */
}

/* Initialize arrays to zero */
for ( i = 0; i < NumIPoints; i++ )
{
    Imeas[i] = 0.0;
    Vforce[i] = 0.0;
}

i = 0;  /* Global point index */

/* ============================================
   SEGMENT 1: 0V → Vhigh
   ============================================ */
/* Use same formula as SMU_VIsweep: vstep = (Vstop-Vstart) / (NumPoints - 1)
   For this segment: Vstart=0V, Vstop=Vhigh, NumPoints=PointsPerSegment+1 */
vstep = (Vhigh - 0.0) / ((double)(PointsPerSegment + 1) - 1.0);  /* Same as SMU_VIsweep formula */
v = 0.0;  /* Start from 0V */

/* First point: 0V */
status = forcev(SMU1, v);
if ( status != 0 )
{
    forcev(SMU1, 0.0);
    return( -5 );
}
status = measi(SMU1, &Imeas[i]);
if ( status != 0 )
{
    forcev(SMU1, 0.0);
    return( -6 );
}
Vforce[i] = v;
i++;

/* Remaining points: 0V + vstep, 0V + 2*vstep, ..., Vhigh */
for ( ; i <= PointsPerSegment; i++ )
{
    v = v + vstep;  /* Incremental approach (same as SMU_VIsweep: v = v + vstep) */
    
    /* Ensure voltage doesn't exceed Vhigh due to rounding */
    if ( v > Vhigh ) v = Vhigh;
    
    status = forcev(SMU1, v);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -5 );
    }
    status = measi(SMU1, &Imeas[i]);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -6 );
    }
    Vforce[i] = v;
}

/* ============================================
   SEGMENT 2: Vhigh → 0V
   ============================================ */
/* Use same formula as SMU_VIsweep: vstep = (Vstop-Vstart) / (NumPoints - 1)
   For this segment: Vstart=Vhigh, Vstop=0V, we want PointsPerSegment points
   Since we skip the first point (Vhigh), we need PointsPerSegment-1 steps */
vstep = (0.0 - Vhigh) / ((double)PointsPerSegment - 1.0);  /* PointsPerSegment points = PointsPerSegment-1 steps */
v = Vhigh;  /* Start from Vhigh (Segment 1 ended here) */

/* Skip the first point (Vhigh) since it's already measured, start from next point */
for ( ; i < 2 * PointsPerSegment + 1; i++ )
{
    v = v + vstep;  /* Incremental approach (vstep is negative, so this decreases v) */
    
    /* Ensure voltage doesn't go below 0V due to rounding */
    if ( v < 0.0 ) v = 0.0;
    
    status = forcev(SMU1, v);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -5 );
    }
    status = measi(SMU1, &Imeas[i]);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -6 );
    }
    Vforce[i] = v;
}

/* ============================================
   SEGMENT 3: 0V → Vlow
   ============================================ */
/* Use same formula as SMU_VIsweep: vstep = (Vstop-Vstart) / (NumPoints - 1)
   For this segment: Vstart=0V, Vstop=Vlow (negative), we want PointsPerSegment points
   Since we skip the first point (0V), we need PointsPerSegment-1 steps */
vstep = (Vlow - 0.0) / ((double)PointsPerSegment - 1.0);  /* PointsPerSegment points = PointsPerSegment-1 steps */
v = 0.0;  /* Start from 0V (Segment 2 ended here) */

/* Skip the first point (0V) since it's already measured, start from next point */
for ( ; i < 3 * PointsPerSegment + 1; i++ )
{
    v = v + vstep;  /* Incremental approach (vstep is negative, so this goes negative) */
    
    /* Ensure voltage doesn't go below Vlow due to rounding */
    if ( v < Vlow ) v = Vlow;
    
    status = forcev(SMU1, v);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -5 );
    }
    status = measi(SMU1, &Imeas[i]);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -6 );
    }
    Vforce[i] = v;
}

/* ============================================
   SEGMENT 4: Vlow → 0V
   ============================================ */
/* Use same formula as SMU_VIsweep: vstep = (Vstop-Vstart) / (NumPoints - 1)
   For this segment: Vstart=Vlow (negative), Vstop=0V, we want PointsPerSegment points
   Since we skip the first point (Vlow), we need PointsPerSegment-1 steps */
vstep = (0.0 - Vlow) / ((double)PointsPerSegment - 1.0);  /* PointsPerSegment points = PointsPerSegment-1 steps */
v = Vlow;  /* Start from Vlow (Segment 3 ended here) */

/* Skip the first point (Vlow) since it's already measured, start from next point */
for ( ; i < 4 * PointsPerSegment + 1; i++ )
{
    v = v + vstep;  /* Incremental approach (vstep is positive, moving toward 0V) */
    
    /* Ensure voltage doesn't exceed 0V due to rounding */
    if ( v > 0.0 ) v = 0.0;
    
    status = forcev(SMU1, v);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -5 );
    }
    status = measi(SMU1, &Imeas[i]);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -6 );
    }
    Vforce[i] = v;
}

/* Ensure we end exactly at 0V (fix any floating point rounding) */
if ( v != 0.0 )
{
    v = 0.0;
    status = forcev(SMU1, v);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -5 );
    }
    status = measi(SMU1, &Imeas[i]);
    if ( status != 0 )
    {
        forcev(SMU1, 0.0);
        return( -6 );
    }
    Vforce[i] = v;
}


return( 0 ); /* Returns zero if execution Ok.*/

/* USRLIB MODULE END  */
} 		/* End SMU_FullIVsweep.c */

