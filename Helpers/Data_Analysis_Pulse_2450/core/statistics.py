"""
Statistical analysis functions for TSP data.
Includes basic statistics, HRS/LRS detection, and relaxation time fitting.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.optimize import curve_fit
from scipy.signal import find_peaks


class DataStatistics:
    """Calculate statistics for measurement data"""
    
    def __init__(self, x_data: np.ndarray, y_data: np.ndarray, 
                 data_label: str = "Data", test_type: str = "unknown"):
        """
        Initialize with data arrays
        
        Args:
            x_data: X-axis data (typically time)
            y_data: Y-axis data (typically resistance, current, etc.)
            data_label: Label for this dataset
            test_type: Type of test (relaxation, endurance, etc.)
        """
        self.x_data = np.array(x_data)
        self.y_data = np.array(y_data)
        self.label = data_label
        self.test_type = test_type
        
    def basic_stats(self) -> Dict[str, float]:
        """Calculate basic statistics"""
        return {
            'Mean': np.mean(self.y_data),
            'Median': np.median(self.y_data),
            'Std Dev': np.std(self.y_data),
            'Min': np.min(self.y_data),
            'Max': np.max(self.y_data),
            'Range': np.ptp(self.y_data),  # peak-to-peak
            'Count': len(self.y_data)
        }
    
    def hrs_lrs_stats(self, threshold_percentile: float = 50.0) -> Dict[str, float]:
        """
        Detect HRS (High Resistance State) and LRS (Low Resistance State)
        
        Args:
            threshold_percentile: Percentile to use as threshold (default: 50 = median)
        
        Returns:
            Dictionary with HRS, LRS values and switching window
        """
        threshold = np.percentile(self.y_data, threshold_percentile)
        
        hrs_values = self.y_data[self.y_data > threshold]
        lrs_values = self.y_data[self.y_data <= threshold]
        
        stats = {}
        
        if len(hrs_values) > 0:
            stats['HRS Mean'] = np.mean(hrs_values)
            stats['HRS Std'] = np.std(hrs_values)
        else:
            stats['HRS Mean'] = np.nan
            stats['HRS Std'] = np.nan
            
        if len(lrs_values) > 0:
            stats['LRS Mean'] = np.mean(lrs_values)
            stats['LRS Std'] = np.std(lrs_values)
        else:
            stats['LRS Mean'] = np.nan
            stats['LRS Std'] = np.nan
        
        if len(hrs_values) > 0 and len(lrs_values) > 0:
            stats['Switching Window'] = stats['HRS Mean'] - stats['LRS Mean']
            stats['On/Off Ratio'] = stats['HRS Mean'] / stats['LRS Mean'] if stats['LRS Mean'] != 0 else np.inf
        else:
            stats['Switching Window'] = np.nan
            stats['On/Off Ratio'] = np.nan
            
        return stats
    
    def relaxation_time(self, initial_guess_tau: Optional[float] = None) -> Dict[str, float]:
        """
        Calculate relaxation time from exponential fit (handles both growth and decay)
        
        Fits: y(t) = y_inf + (y_0 - y_inf) * exp(-t/tau)
        Works for both:
        - Decay: y_0 > y_inf (decreasing)
        - Growth: y_0 < y_inf (increasing)
        
        Tau (τ) is the time constant with units matching the X-axis:
        - If X-axis is Time (s), then tau is in seconds
        - Tau represents the time for ~63% of the total change to occur
        - Tau is always positive (time constant)
        
        Calculation method:
        1. Detects growth vs decay from initial/final values
        2. Estimates initial tau from 63% point
        3. Performs nonlinear least-squares curve fitting (scipy.optimize.curve_fit)
        4. Returns tau, fit quality (R²), and error estimates
        
        Args:
            initial_guess_tau: Initial guess for tau in X-axis units (if None, estimates from data)
        
        Returns:
            Dictionary with fit parameters and relaxation time
        """
        if len(self.x_data) < 4:
            return {
                'Tau (Relaxation Time)': np.nan,
                'Y_infinity': np.nan,
                'Y_0': np.nan,
                'R_squared': np.nan,
                'Fit Success': False,
                'Error': 'Insufficient data points'
            }
        
        # Detect growth vs decay
        y_0_initial = self.y_data[0]
        y_inf_initial = self.y_data[-1]
        is_growth = y_inf_initial > y_0_initial
        
        # Define exponential relaxation function
        def exp_relax(t, y_inf, y_0, tau):
            # This works for both growth and decay
            # For decay: y_0 > y_inf, so (y_0 - y_inf) > 0
            # For growth: y_0 < y_inf, so (y_0 - y_inf) < 0, exp goes to 0, so y approaches y_inf from below
            return y_inf + (y_0 - y_inf) * np.exp(-t / tau)
        
        # Initial parameter guesses
        y_0_guess = y_0_initial
        y_inf_guess = y_inf_initial
        
        # Ensure we have a reasonable initial guess for tau
        if initial_guess_tau is None:
            # Estimate tau as the time to reach ~63% of the change
            delta_y = abs(y_inf_guess - y_0_guess)
            if delta_y > 0:
                target_y = y_0_guess + 0.63 * (y_inf_guess - y_0_guess) if is_growth else y_0_guess - 0.63 * abs(y_inf_guess - y_0_guess)
                
                # Find closest point
                idx = np.argmin(np.abs(self.y_data - target_y))
                initial_guess_tau = abs(self.x_data[idx]) if self.x_data[idx] != 0 else 1.0
            else:
                initial_guess_tau = self.x_data[-1] / 3.0 if len(self.x_data) > 0 else 1.0
        
        # Ensure positive initial guess
        initial_guess_tau = abs(initial_guess_tau)
        
        p0 = [y_inf_guess, y_0_guess, initial_guess_tau]
        
        try:
            # Perform curve fitting
            # Set bounds based on data range
            y_min = np.nanmin(self.y_data)
            y_max = np.nanmax(self.y_data)
            y_range = y_max - y_min
            
            popt, pcov = curve_fit(
                exp_relax, 
                self.x_data, 
                self.y_data, 
                p0=p0,
                maxfev=10000,
                bounds=([
                    y_min - abs(y_range),  # y_inf lower bound
                    y_min - abs(y_range),  # y_0 lower bound
                    0.0001  # tau lower bound (must be positive)
                ], [
                    y_max + abs(y_range),  # y_inf upper bound
                    y_max + abs(y_range),  # y_0 upper bound
                    self.x_data[-1] * 20 if len(self.x_data) > 0 else 1e6  # tau upper bound
                ])
            )
            
            y_inf_fit, y_0_fit, tau_fit = popt
            
            # Ensure tau is positive (take absolute value if needed)
            # Sometimes fitting can produce negative tau, especially for growth
            tau_fit = abs(tau_fit)
            
            # Calculate R-squared
            y_pred = exp_relax(self.x_data, y_inf_fit, y_0_fit, tau_fit)
            ss_res = np.sum((self.y_data - y_pred) ** 2)
            ss_tot = np.sum((self.y_data - np.mean(self.y_data)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            # Calculate standard errors
            try:
                perr = np.sqrt(np.diag(pcov))
                tau_error = abs(perr[2]) if len(perr) > 2 else np.nan
            except:
                tau_error = np.nan
            
            # Determine relaxation type for display
            relaxation_type = "Growth" if y_inf_fit > y_0_fit else "Decay"
            
            # Build fit function string
            if is_growth:
                fit_func = f'y = {y_inf_fit:.3e} - ({abs(y_inf_fit - y_0_fit):.3e}) * exp(-t / {tau_fit:.3e})'
            else:
                fit_func = f'y = {y_inf_fit:.3e} + ({abs(y_0_fit - y_inf_fit):.3e}) * exp(-t / {tau_fit:.3e})'
            
            return {
                'Tau (Relaxation Time)': tau_fit,
                'Tau Error': tau_error,
                'Y_infinity': y_inf_fit,
                'Y_0': y_0_fit,
                'R_squared': r_squared,
                'Relaxation Type': relaxation_type,
                'Fit Success': True,
                'Fit Function': fit_func
            }
            
        except Exception as e:
            return {
                'Tau (Relaxation Time)': np.nan,
                'Y_infinity': np.nan,
                'Y_0': np.nan,
                'R_squared': np.nan,
                'Fit Success': False,
                'Error': str(e)
            }
    
    def initial_read_stats(self) -> Dict[str, float]:
        """Calculate statistics relative to initial read (first point)"""
        if len(self.y_data) == 0:
            return {
                'Initial Value': np.nan,
                'Final Value': np.nan,
                'Total Change': np.nan,
                'Percent Change': np.nan
            }
        
        initial = self.y_data[0]
        final = self.y_data[-1]
        delta = final - initial
        percent = (delta / initial * 100) if initial != 0 else np.nan
        
        return {
            'Initial Value': initial,
            'Final Value': final,
            'Total Change (ΔY)': delta,
            'Percent Change (%)': percent
        }
    
    def peak_detection(self, prominence: float = 0.1) -> Dict[str, any]:
        """
        Detect peaks in the data
        
        Args:
            prominence: Required prominence of peaks (relative to data range)
        
        Returns:
            Dictionary with peak information
        """
        data_range = np.ptp(self.y_data)
        min_prominence = prominence * data_range
        
        peaks, properties = find_peaks(self.y_data, prominence=min_prominence)
        valleys, _ = find_peaks(-self.y_data, prominence=min_prominence)
        
        return {
            'Num Peaks': len(peaks),
            'Num Valleys': len(valleys),
            'Peak Positions': self.x_data[peaks].tolist() if len(peaks) > 0 else [],
            'Peak Values': self.y_data[peaks].tolist() if len(peaks) > 0 else [],
            'Valley Positions': self.x_data[valleys].tolist() if len(valleys) > 0 else [],
            'Valley Values': self.y_data[valleys].tolist() if len(valleys) > 0 else []
        }
    
    def all_stats(self, include_relaxation: bool = True, 
                  include_hrs_lrs: bool = False) -> Dict[str, float]:
        """
        Calculate all relevant statistics
        
        Args:
            include_relaxation: Whether to calculate relaxation time (can be slow)
            include_hrs_lrs: Whether to calculate HRS/LRS stats
        
        Returns:
            Combined dictionary of all statistics
        """
        stats = {}
        
        # Always include basic stats
        stats.update(self.basic_stats())
        
        # Always include initial read stats
        stats.update(self.initial_read_stats())
        
        # Optional: HRS/LRS for endurance/switching data
        if include_hrs_lrs:
            stats.update(self.hrs_lrs_stats())
        
        # Optional: Relaxation time (can be computationally expensive)
        # Calculate if explicitly requested, or if test type suggests relaxation
        if include_relaxation or 'relaxation' in self.test_type.lower():
            relax_stats = self.relaxation_time()
            if relax_stats.get('Fit Success', False):
                stats['Tau (Relaxation Time)'] = relax_stats['Tau (Relaxation Time)']
                stats['Tau R²'] = relax_stats['R_squared']
                # Add relaxation type if available
                if 'Relaxation Type' in relax_stats:
                    stats['Relaxation Type'] = relax_stats['Relaxation Type']
        
        return stats


def format_stat_value(name: str, value: any, precision: int = 3) -> str:
    """
    Format a statistic value for display
    
    Args:
        name: Name of the statistic
        value: Value to format (can be float, int, or string)
        precision: Number of significant figures (for numeric values)
    
    Returns:
        Formatted string
    """
    # Handle string values (e.g., "Relaxation Type")
    if isinstance(value, str):
        return f"{name}: {value}"
    
    # Handle numeric values
    if isinstance(value, (int, float)):
        if np.isnan(value):
            return f"{name}: N/A"
        elif np.isinf(value):
            return f"{name}: ∞"
        elif abs(value) > 1000 or (abs(value) < 0.01 and value != 0):
            return f"{name}: {value:.{precision}e}"
        else:
            return f"{name}: {value:.{precision}f}"
    
    # Fallback for other types
    return f"{name}: {value}"


def calculate_multi_dataset_stats(datasets: List[Tuple[np.ndarray, np.ndarray, str]]) -> Dict[str, Dict[str, float]]:
    """
    Calculate statistics for multiple datasets
    
    Args:
        datasets: List of (x_data, y_data, label) tuples
    
    Returns:
        Dictionary mapping label to statistics dictionary
    """
    results = {}
    
    for x_data, y_data, label in datasets:
        stats_calc = DataStatistics(x_data, y_data, label)
        results[label] = stats_calc.all_stats()
    
    return results

