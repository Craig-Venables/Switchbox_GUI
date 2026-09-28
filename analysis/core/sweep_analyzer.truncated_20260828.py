import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import math
from scipy import signal, integrate, optimize
from scipy.optimize import curve_fit
import warnings
import os
from datetime import datetime
from typing import List
import textwrap
from matplotlib.backends.backend_pdf import PdfPages

# ==================== DEBUG CONTROL ====================
# Set to True only when actively debugging. In normal use this should stay False
# so the console isn't flooded with diagnostic messages.
DEBUG_ENABLED = False

def debug_print(*args, **kwargs):
    """
    Lightweight debug logger for diagnostic messages.
    
    NOTE: Kept for future troubleshooting, but disabled by default via
    DEBUG_ENABLED=False to keep runtime output clean for end users.
    """
    if DEBUG_ENABLED:
        print(*args, **kwargs)

# Suppress expected numerical warnings that are handled by try-except blocks
warnings.filterwarnings('ignore', category=RuntimeWarning, message='invalid value encountered in log')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='invalid value encountered in divide')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='invalid value encountered in scalar divide')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='Mean of empty slice')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='Degrees of freedom <= 0')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='overflow encountered in power')
warnings.filterwarnings('ignore', category=optimize.OptimizeWarning, message='Covariance of the parameters could not be estimated')
# Suppress LAPACK warnings (DLASCLS errors)
warnings.filterwarnings('ignore', message='.*On entry to DLASCLS.*')


def read_data_file(file_path):
    """Load an IV (or pulse) text file as voltage, current[, time].

    Expected layout: whitespace-delimited columns after a one-line header.
    Returns (V, I, t) with t=None when only two columns are present, or
    (None, None, None) if the file cannot be read.
    """
    try:
        data = np.loadtxt(file_path, skiprows=1)
        if getattr(data, "ndim", 0) == 1:
            data = data.reshape(1, -1)
        if data.size == 0 or data.shape[1] < 2:
            return None, None, None
        v = data[:, 0]
        i = data[:, 1]
        t = data[:, 2] if data.shape[1] > 2 else None
        return v, i, t
    except Exception:
        try:
            data = np.loadtxt(file_path)
            if getattr(data, "ndim", 0) == 1:
                data = data.reshape(1, -1)
            if data.size == 0 or data.shape[1] < 2:
                return None, None, None
            v = data[:, 0]
            i = data[:, 1]
            t = data[:, 2] if data.shape[1] > 2 else None
            return v, i, t
        except Exception:
            return None, None, None


def _positive_finite(arr):
    """Filter a sequence to positive finite floats, skipping None/NaN/inf/<=0."""
    if arr is None:
        return []
    out = []
    for x in arr:
        if x is None:
            continue
        try:
            v = float(x)
        except (TypeError, ValueError):
            continue
        if np.isfinite(v) and v > 0:
            out.append(v)
    return out


def _finite_values(arr):
    """Filter a sequence to finite floats, skipping None/NaN/inf."""
    if arr is None:
        return []
    out = []
    for x in arr:
        if x is None:
            continue
        try:
            v = float(x)
        except (TypeError, ValueError):
            continue
        if np.isfinite(v):
            out.append(v)
    return out


def safe_mean(arr, default=0.0):
    """Safely compute mean, handling empty arrays, None, and invalid values."""
    cleaned = _finite_values(arr)
    if not cleaned:
        return default
    return float(np.mean(cleaned))


def safe_std(arr, default=0.0):
    """Safely compute standard deviation, handling empty arrays, None, and invalid values."""
    cleaned = _finite_values(arr)
    if len(cleaned) < 2:
        return default
    return float(np.std(cleaned))


def safe_var(arr, default=0.0):
    """Safely compute variance, handling empty arrays, None, and invalid values."""
    cleaned = _finite_values(arr)
    if len(cleaned) < 2:
        return default
    arr = np.array(cleaned)
    if len(arr) < 2:
        return default
    return float(np.var(arr))


class SweepAnalyzer:
    """
    Class for comprehensive analysis of memristor device measurements.
    Supports I-V characterization, pulse measurements, endurance, and retention testing.
    Includes theoretical model fitting and advanced device classification.
    """
    
    # ========================================================================
    # CLASSIFICATION TOGGLES - Configure behavior at class level
    # ========================================================================
    ENABLE_MEMCAPACITIVE_CLASSIFICATION = False  # Disabled: not a useful category for current datasets
    UNCERTAIN_THRESHOLD = 40.0  # Score below this → "uncertain" classification
    
    def __init__(
        self,
        voltage,
        current,
        time=None,
        measurement_type='iv_sweep',
        analysis_level='full',
        classification_weights=None,
        device_name=None,
        device_id=None,
        save_directory=None,
        cycle_number=None,
    ):
        """
        Initialize device analysis.

        Parameters:
        -----------
        voltage : array-like
            Applied voltage data
        current : array-like
            Measured current data
        time : array-like, optional
            Time data for pulse/retention measurements
        measurement_type : str
            Type of measurement: 'iv_sweep', 'pulse', 'endurance', 'retention'
        analysis_level : str
            Analysis depth. One of:
            - 'basic'         → fast: loop split + core metrics (Ron/Roff, ON/OFF, areas)
            - 'classification'→ basic + features + device classification
            - 'full'          → classification + conduction models + advanced metrics
            - 'research'      → full + extra diagnostics/statistics (NDR, kink voltage, loop similarity)
        classification_weights : dict, optional
            Custom classification weights. If None, uses default weights.
        device_name : str, optional
            Name/ID of the device being analyzed (for diagnostic output)
        """
        # Support original two-parameter call
        if isinstance(time, str):
            measurement_type = time
            time = None
        self.device_name = device_name  # Store device name for diagnostics
        self.voltage = self._ensure_1d_array(voltage)
        self.current = self._ensure_1d_array(current)
        self.time = self._ensure_1d_array(time) if time is not None else None
        self.measurement_type = self._detect_measurement_type(measurement_type)
        # Fallback: if a time-based type was requested/detected but time is missing, degrade to iv_sweep
        if self.time is None and self.measurement_type in {'pulse', 'retention'}:
            self.measurement_type = 'iv_sweep'
        self.analysis_level = analysis_level if analysis_level in {'basic','classification','full','research'} else 'full'
        self.classification_weights = classification_weights  # Store custom weights if provided
        self.process_loops()

        # Validate data
        if self.voltage is None or self.current is None or len(self.voltage) < 2:
            raise ValueError("Invalid input data: insufficient voltage/current points")

        # Ensure same length
        min_len = min(len(self.voltage), len(self.current))
        self.voltage = self.voltage[:min_len]
        self.current = self.current[:min_len]
        if self.time is not None:
            self.time = self.time[:min_len]

        try:
            self.num_loops = self.check_for_loops(self.voltage)
        except:
            print("error with loops")

        # Initialize lists to store the values for each metric
        self.ps_areas = []
        self.ng_areas = []
        self.areas = []
        self.normalized_areas = []
        self.ron = []
        self.roff = []
        self.von = []
        self.voff = []
        self.on_off = []
        self.r_02V = []  # resistance values at 0.2v
        self.r_05V = []  # resistance values at 0.5v

        # Device classification attributes
        self.device_type = None
        self.classification_confidence = 0.0
        self.classification_features = {}
        self.conduction_mechanism = None  # SCLC, Ohmic, etc.
        self.model_parameters = {}
        self.classification_breakdown = {}
        self.classification_explanation = {}
        self.classification_reasoning = ""  # Detailed explanation of classification
        self.classification_warnings = []  # Red flags for inconsistent features
        self.metrics_quarantined = False  # Hard flag: resistance metrics physically implausible
        self.quarantine_reasons = []  # Why metrics_quarantined was set
        self._last_ron_roff_meta = {}  # Diagnostics from most recent on_off_values call
        self.switching_strength = 0.0  # Continuous score 0-100 for switching quality
        
        # === ENHANCED CLASSIFICATION (Phase 1) ===
        # These are ADDITIONAL metrics that don't affect core classification
        self.memristivity_score = None  # 0-100 continuous score
        self.memristivity_breakdown = {}  # Contribution of each feature to score
        self.forming_stage = None  # Device forming timeline label (per sweep)
        self.yield_bucket = None  # 'formed' | 'forming' | 'none' (per sweep)
        self.adaptive_thresholds = {}  # Context-aware thresholds
        self.memory_window_quality = {}  # Detailed window quality metrics
        self.hysteresis_shape_features = {}  # Shape analysis
        self.enhanced_classification_enabled = True  # Can be disabled if needed
        
        # === DEVICE TRACKING (Phase 2) ===
        self.device_id = device_id
        self.cycle_number = cycle_number
        self.save_directory = save_directory
        self.device_history = None  # Historical data for this device (loaded on demand)

        # Additional memristor metrics
        self.switching_ratio = []  # Roff/Ron ratio
        self.rectification_ratio = []  # I(+V)/I(-V) ratio
        self.nonlinearity_factor = []  # Degree of I-V nonlinearity
        self.asymmetry_factor = []  # Device asymmetry
        self.power_consumption = []  # Average power per cycle
        self.energy_per_switch = []  # Energy required for switching
        self.compliance_current = None  # Current compliance detection
        self.window_margin = []  # (Roff - Ron) / Ron
        self.retention_score = 0.0  # Stability metric
        self.endurance_score = 0.0  # Cycle-to-cycle consistency

        # Pulse measurement metrics
        self.set_times = []
        self.reset_times = []
        self.set_voltages = []
        self.reset_voltages = []

        # Endurance/Retention specific metrics
        self.endurance_cycles = []
        self.retention_times = []
        self.state_degradation = []

        # Extra diagnostics (research level)
        self.switching_polarity = None  # 'bipolar'|'unipolar'|'unknown'
        self.ndr_index = None  # fraction of points with dI/dV < 0
        self.hysteresis_direction = None  # 'clockwise'|'counter_clockwise'|'none'
        self.kink_voltage = None  # estimated trap-filled limit voltage
        self.loop_similarity_score = None  # correlation between loops
        self.pinch_offset = None  # |I| near V≈0
        self.noise_floor = None  # std(I) at low |V|
        self.slope_exponent_stats = {}  # stats of n = dlogI/dlogV
        # Literature-style NDR shape metrics (I/Imax, primary negative-slope segment)
        self.ndr_norm_slope = None
        self.ndr_depth = None
        self.ndr_v_start = None
        self.ndr_v_end = None
        self.ndr_peak_to_valley = None
        self.ndr_segment_count = None
        self.last_report = None  # cache for the most recent generated report

        # Process based on measurement type
        device_info = f" [{self.device_name}]" if self.device_name else ""
        num_cycles = self._detect_cycles()
        debug_print(f"[DIAGNOSTIC]{device_info} Detected measurement type: {self.measurement_type} (cycles: {num_cycles})")
        
        if self.measurement_type == 'iv_sweep':
            self._process_iv_sweep()
        elif self.measurement_type == 'pulse':
            # Only run pulse path if time present; else gracefully degrade to IV
            if self.time is not None:
                self._process_pulse_measurement()
            else:
                self._process_iv_sweep()
        elif self.measurement_type == 'endurance':
            self._process_endurance_measurement()
        elif self.measurement_type == 'retention':
            # Only run retention path if time present; else gracefully degrade to IV
            if self.time is not None:
                self._process_retention_measurement()
            else:
                self._process_iv_sweep()

    def _ensure_1d_array(self, data):
        """Ensure data is a 1D numpy array"""
        if data is None:
            return None

        arr = np.asarray(data)

        # Handle different array shapes
        if arr.ndim == 0:
            # Scalar - convert to 1-element array
            return np.array([arr])
        elif arr.ndim == 1:
            return arr
        elif arr.ndim == 2:
            # 2D array - flatten or take first column
            if arr.shape[0] == 1:
                return arr[0]
            elif arr.shape[1] == 1:
                return arr[:, 0]
            else:
                # Multiple columns - just flatten
                return arr.flatten()
        else:
            # Higher dimensional - just flatten
            return arr.flatten()

    def _detect_measurement_type(self, suggested_type):
        """
        Automatically detect measurement type from data characteristics.

        Returns:
        --------
        str : Detected measurement type
        """
        if suggested_type != 'iv_sweep':
            return suggested_type

        # Check filename for hints
        # FS = Fast Sweep, ps/ns = picosecond/nanosecond sweep rates
        if self.device_name:
            name_lower = self.device_name.lower()
            has_fs_indicator = any(indicator in name_lower for indicator in ['fs', 'ps', 'ns', '-sweep', '_sweep'])
            debug_print(f"[DIAGNOSTIC] Filename check: '{self.device_name}' -> has IV sweep indicator: {has_fs_indicator}")
            if has_fs_indicator:
                # Filename indicates IV sweep, trust it
                debug_print(f"[DIAGNOSTIC] Forcing measurement type to 'iv_sweep' based on filename")
                return 'iv_sweep'
        else:
            debug_print(f"[DIAGNOSTIC] No device_name available for filename check")

        # Check if this might be a pulse measurement
        if self.time is not None:
            # Check for step-like voltage changes
            v_diff = np.diff(self.voltage)
            if len(v_diff) > 0:
                max_diff = np.max(np.abs(v_diff))
                median_diff = np.median(np.abs(v_diff))
                
                # Large step changes indicate pulse measurement
                if max_diff > 10 * median_diff and median_diff > 0:
                    return 'pulse'

            # Check for retention (constant voltage over time)
            # Retention has very few unique voltage values AND low voltage variation
            unique_voltages = len(np.unique(self.voltage))
            total_points = len(self.voltage)
            
            if unique_voltages < total_points / 10:
                # Few unique values - could be retention OR coarsely sampled IV sweep
                # Check voltage range to distinguish:
                # - Retention: typically holds 1-2 voltage levels (read voltages)
                # - IV Sweep: even with coarse sampling, should have varying voltage
                v_range = np.max(self.voltage) - np.min(self.voltage)
                v_std = np.std(self.voltage)
                
                # If voltage barely varies (std < 10% of range), it's retention
                # Otherwise, it's likely a coarsely sampled IV sweep
                if v_range > 0 and v_std < 0.1 * v_range:
                    return 'retention'
                # If we see very few unique values (<5) and they're discrete levels, it's retention
                elif unique_voltages < 5:
                    return 'retention'

        # Check for endurance vs IV sweep
        # Endurance: pulse-write-read pattern (discrete voltage levels with holds)
        # IV Sweep: continuous triangular/sinusoidal sweeping
        num_cycles = self._detect_cycles()
        
        if num_cycles > 10:
            # Check if this is continuous sweeping (IV) or discrete pulse pattern (endurance)
            # IV sweeps have smoothly varying voltage, endurance has step changes
            v_diff = np.abs(np.diff(self.voltage))
            
            # Calculate the variation in voltage differences
            # IV sweeps have consistent voltage steps (low variation)
            # Endurance/pulse has large jumps and plateaus (high variation)
            if len(v_diff) > 0:
                median_diff = np.median(v_diff)
                max_diff = np.max(v_diff)
                
                # If we see large voltage jumps (>5x median), likely endurance/pulse
                if max_diff > 5 * median_diff and median_diff > 0:
                    return 'endurance'
                
                # Check for plateaus (constant voltage regions)
                # Count points where voltage barely changes
                plateau_points = np.sum(v_diff < median_diff * 0.1) if median_diff > 0 else 0
                plateau_fraction = plateau_points / len(v_diff) if len(v_diff) > 0 else 0
                
                # If >30% of points are plateaus, likely endurance (pulse-hold pattern)
                if plateau_fraction > 0.3:
                    return 'endurance'
            
            # Otherwise, it's an IV sweep with many cycles (which is fine!)
            return 'iv_sweep'

        return 'iv_sweep'

    def _detect_cycles(self):
        """Detect number of measurement cycles."""
        # Look for zero crossings
        zero_crossings = np.where(np.diff(np.signbit(self.voltage)))[0]
        return len(zero_crossings) // 2

    def _process_iv_sweep(self):
        """Process standard I-V sweep measurements."""
        # Always compute core metrics first
        self.calculate_metrics_for_loops(self.split_v_data, self.split_c_data)

        # Conditional analysis based on analysis_level
        if self.analysis_level in {"classification", "full", "research"}:
            self._classify_device()

        if self.analysis_level in {"full", "research"}:
            self._fit_conduction_models()
            self._calculate_advanced_metrics()

        if self.analysis_level == "research":
            self._calculate_research_diagnostics()

    def _process_pulse_measurement(self):
        """
        Process pulse-based measurements for switching analysis.
        Extracts set/reset voltages, switching times, and energy.
        """
        if self.time is None:
            # No time available; do not fail, fall back to IV sweep metrics already computed
            return

        # Detect voltage pulses
        v_threshold = 0.5 * (np.max(self.voltage) - np.min(self.voltage))

        # Find pulse edges
        v_diff = np.diff(self.voltage)
        pulse_starts = np.where(np.abs(v_diff) > v_threshold)[0]

        for i in range(0, len(pulse_starts) - 1, 2):
            start_idx = pulse_starts[i]
            end_idx = pulse_starts[i + 1] if i + 1 < len(pulse_starts) else len(self.voltage) - 1

            # Extract pulse parameters
            pulse_v = self.voltage[start_idx:end_idx]
            pulse_i = self.current[start_idx:end_idx]
            pulse_t = self.time[start_idx:end_idx]

            # Determine if set or reset pulse
            if np.mean(pulse_v) > 0:
                self.set_voltages.append(np.mean(pulse_v))
                # Calculate switching time (time to reach 90% of final current)
                i_initial = pulse_i[0]
                i_final = pulse_i[-1]
                i_90 = i_initial + 0.9 * (i_final - i_initial)
                switch_idx = np.argmin(np.abs(pulse_i - i_90))
                self.set_times.append(pulse_t[switch_idx] - pulse_t[0])
            else:
                self.reset_voltages.append(np.mean(pulse_v))
                # Similar calculation for reset
                i_initial = pulse_i[0]
                i_final = pulse_i[-1]
                i_90 = i_initial + 0.9 * (i_final - i_initial)
                switch_idx = np.argmin(np.abs(pulse_i - i_90))
                self.reset_times.append(pulse_t[switch_idx] - pulse_t[0])

    def _process_endurance_measurement(self):
        """
        Process endurance measurements to analyze device stability over cycles.
        Tracks resistance states and switching parameters across multiple cycles.
        """
        # First process as regular I-V sweep to get cycle data
        self._process_iv_sweep()

        # Track evolution of key parameters
        self.endurance_cycles = list(range(len(self.ron)))

        # Calculate degradation metrics
        if len(self.ron) > 1:
            # Resistance state degradation (skip None sentinels)
            r0 = self.ron[0]
            rn = self.ron[-1]
            o0 = self.roff[0]
            on = self.roff[-1]
            w0 = self.on_off[0] if self.on_off else None
            wn = self.on_off[-1] if self.on_off else None
            ron_degradation = (
                (rn - r0) / r0
                if r0 is not None and rn is not None and r0 > 0
                else None
            )
            roff_degradation = (
                (on - o0) / o0
                if o0 is not None and on is not None and o0 > 0
                else None
            )
            window_degradation = (
                (wn - w0) / w0
                if w0 is not None and wn is not None and w0 > 0
                else None
            )

            self.state_degradation = {
                'ron_degradation': ron_degradation,
                'roff_degradation': roff_degradation,
                'window_degradation': window_degradation,
                'cycles_to_50_percent': self._calculate_cycles_to_failure(0.5),
                'cycles_to_90_percent': self._calculate_cycles_to_failure(0.9)
            }

    def _process_retention_measurement(self):
        """
        Process retention measurements to analyze state stability over time.
        Monitors resistance drift and state retention characteristics.
        """
        if self.time is None:
            # No time available; do not fail
            return

        # Calculate resistance over time
        resistance = np.abs(self.voltage / (self.current + 1e-12))

        # Fit retention model (logarithmic decay)
        try:
            # Validate data before fitting
            if len(self.time) < 3 or len(resistance) < 3:
                raise ValueError("Insufficient data points for retention fitting")
            if np.any(~np.isfinite(self.time)) or np.any(~np.isfinite(resistance)):
                raise ValueError("Non-finite values in time or resistance")
            if np.any(resistance <= 0):
                raise ValueError("Non-positive resistance values")
            if len(self.time) != len(resistance):
                raise ValueError("Time and resistance arrays must have same length")
            
            def retention_model(t, r0, alpha):
                return r0 * (1 + alpha * np.log(1 + t))

            # Suppress OptimizeWarning for this specific operation
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=optimize.OptimizeWarning)
                popt, _ = curve_fit(retention_model, self.time, resistance)

            self.retention_times = self.time
            self.state_degradation = {
                'initial_resistance': popt[0],
                'decay_rate': popt[1],
                'retention_time_90_percent': self._calculate_retention_time(0.9),
                'retention_time_50_percent': self._calculate_retention_time(0.5)
            }
        except Exception as e:
            device_info = f" [{self.device_name}]" if self.device_name else ""
            debug_print(f"[DIAGNOSTIC]{device_info} Warning: Could not fit retention model - {type(e).__name__}: {str(e)}")

    def _calculate_cycles_to_failure(self, failure_threshold):
        """
        Calculate number of cycles until device degrades to threshold.

        Parameters:
        -----------
        failure_threshold : float
            Fraction of initial performance (e.g., 0.5 for 50%)
        """
        if not self.on_off:
            return None

        initial_window = self.on_off[0]
        threshold_value = initial_window * failure_threshold

        for i, window in enumerate(self.on_off):
            if window < threshold_value:
                return i

        # Extrapolate if not reached
        if len(self.on_off) > 2:
            # Fit exponential decay
            cycles = np.array(range(len(self.on_off)))
            try:
                popt, _ = curve_fit(lambda x, a, b: a * np.exp(-b * x),
                                    cycles, self.on_off)
                # Solve for cycles to threshold
                cycles_to_failure = -np.log(threshold_value / popt[0]) / popt[1]
                return int(cycles_to_failure)
            except:
                return None
        return None

    def _calculate_retention_time(self, retention_threshold):
        """Calculate time until state decays to threshold."""
        # Similar implementation for retention time
        # Would need actual retention data to implement properly
        return None

    def _fit_conduction_models(self):
        """
        Fit various conduction models to identify transport mechanism.
        Models include: Ohmic, SCLC, Poole-Frenkel, Schottky, Tunneling
        """
        if len(self.voltage) < 10:
            return

        # Take positive voltage region for fitting
        pos_mask = self.voltage > 0.1
        if not np.any(pos_mask):
            return

        v_fit = self.voltage[pos_mask]
        i_fit = self.current[pos_mask]

        models = {}

        # 1. Ohmic conduction: I = V/R
        try:
            popt_ohmic, pcov = curve_fit(lambda v, r: v / r, v_fit, i_fit)
            i_pred_ohmic = v_fit / popt_ohmic[0]
            r2_ohmic = self._calculate_r2(i_fit, i_pred_ohmic)
            models['ohmic'] = {'R2': r2_ohmic, 'params': {'R': popt_ohmic[0]}}
        except:
            models['ohmic'] = {'R2': 0, 'params': {}}

            # 2. Space Charge Limited Current (SCLC): I ∝ V²
        try:
            # SCLC: I = (9/8) * ε * μ * V²/d³
            # For fitting: I = a * V²
            popt_sclc, pcov = curve_fit(lambda v, a: a * v ** 2, v_fit, i_fit)
            i_pred_sclc = popt_sclc[0] * v_fit ** 2
            r2_sclc = self._calculate_r2(i_fit, i_pred_sclc)
            models['sclc'] = {'R2': r2_sclc, 'params': {'a': popt_sclc[0]}}
        except:
            models['sclc'] = {'R2': 0, 'params': {}}

            # 3. Trap-filled SCLC: I ∝ V^n (n>2)
        try:
            def trap_sclc(v, a, n):
                return a * v ** n

            popt_trap, pcov = curve_fit(trap_sclc, v_fit, i_fit, p0=[1e-6, 3])
            i_pred_trap = trap_sclc(v_fit, *popt_trap)
            r2_trap = self._calculate_r2(i_fit, i_pred_trap)
            models['trap_sclc'] = {'R2': r2_trap, 'params': {'a': popt_trap[0], 'n': popt_trap[1]}}
        except:
            models['trap_sclc'] = {'R2': 0, 'params': {}}

            # 4. Poole-Frenkel emission: I ∝ V*exp(β*√V)
        try:
            # Validate data before processing
            if len(i_fit) < 3 or len(v_fit) < 3:
                raise ValueError("Insufficient data points")
            if np.any(v_fit <= 0) or np.any(i_fit <= 0):
                raise ValueError("Invalid voltage/current values")
            
            def poole_frenkel(v, a, beta):
                return a * v * np.exp(beta * np.sqrt(v))

            # Use log transformation for better fitting
            # Ensure positive values before log
            i_safe = np.maximum(i_fit, 1e-12)
            v_safe = np.maximum(v_fit, 1e-12)
            log_i = np.log(i_safe)
            log_v = np.log(v_safe)
            sqrt_v = np.sqrt(v_safe)
            
            # Check for valid values after transformation
            if np.any(~np.isfinite(log_i)) or np.any(~np.isfinite(log_v)) or np.any(~np.isfinite(sqrt_v)):
                raise ValueError("Non-finite values after transformation")
            
            # Linear fit in log space
            coeffs = np.polyfit(sqrt_v, log_i - log_v, 1)
            beta = coeffs[0]
            a = np.exp(coeffs[1])
            i_pred_pf = poole_frenkel(v_fit, a, beta)
            r2_pf = self._calculate_r2(i_fit, i_pred_pf)
            models['poole_frenkel'] = {'R2': r2_pf, 'params': {'a': a, 'beta': beta}}
        except:
            models['poole_frenkel'] = {'R2': 0, 'params': {}}

            # 5. Schottky emission: I ∝ T²*exp(-qΦ/kT)*exp(β*√V)
        try:
            # Validate data before processing
            if len(i_fit) < 3 or len(v_fit) < 3:
                raise ValueError("Insufficient data points")
            if np.any(v_fit <= 0) or np.any(i_fit <= 0):
                raise ValueError("Invalid voltage/current values")
            
            # Simplified Schottky at constant T: I ∝ exp(β*√V)
            def schottky(v, a, beta):
                return a * np.exp(beta * np.sqrt(v))

            # Ensure positive values before log
            i_safe = np.maximum(i_fit, 1e-12)
            v_safe = np.maximum(v_fit, 1e-12)
            log_i = np.log(i_safe)
            sqrt_v = np.sqrt(v_safe)
            
            # Check for valid values after transformation
            if np.any(~np.isfinite(log_i)) or np.any(~np.isfinite(sqrt_v)):
                raise ValueError("Non-finite values after transformation")
            
            coeffs = np.polyfit(sqrt_v, log_i, 1)
            beta = coeffs[0]
            a = np.exp(coeffs[1])
            i_pred_sch = schottky(v_fit, a, beta)
            r2_sch = self._calculate_r2(i_fit, i_pred_sch)
            models['schottky'] = {'R2': r2_sch, 'params': {'a': a, 'beta': beta}}
        except:
            models['schottky'] = {'R2': 0, 'params': {}}

            # 6. Fowler-Nordheim tunneling: I ∝ V²*exp(-b/V)
        try:
            # Validate data before processing
            if len(i_fit) < 3 or len(v_fit) < 3:
                raise ValueError("Insufficient data points")
            if np.any(v_fit == 0) or np.any(i_fit <= 0):
                raise ValueError("Invalid voltage/current values (zero voltage or negative current)")
            
            # F-N plot: ln(I/V²) vs 1/V should be linear
            v_safe = np.maximum(np.abs(v_fit), 1e-12)  # Avoid division by zero
            inv_v = 1 / v_safe
            i_safe = np.maximum(i_fit, 1e-12)
            i_v2_ratio = i_safe / (v_safe ** 2)
            ln_i_v2 = np.log(i_v2_ratio + 1e-12)
            
            # Check for valid values after transformation
            if np.any(~np.isfinite(inv_v)) or np.any(~np.isfinite(ln_i_v2)):
                raise ValueError("Non-finite values after transformation")
            
            coeffs = np.polyfit(inv_v, ln_i_v2, 1)
            b = -coeffs[0]
            a = np.exp(coeffs[1])
            i_pred_fn = a * v_fit ** 2 * np.exp(-b / v_fit)
            r2_fn = self._calculate_r2(i_fit, i_pred_fn)
            models['fowler_nordheim'] = {'R2': r2_fn, 'params': {'a': a, 'b': b}}
        except:
            models['fowler_nordheim'] = {'R2': 0, 'params': {}}

            # Determine best fitting model
        best_model = max(models.items(), key=lambda x: x[1]['R2']) if models else (None, {'R2': 0, 'params': {}})
        self.conduction_mechanism = best_model[0]
        self.model_parameters = best_model[1]
        self.all_model_fits = models

    def _calculate_r2(self, y_true, y_pred):
        """
        Calculate R-squared value for model fitting.

        R² = 1 - (SS_res / SS_tot)
        where SS_res = Σ(y_true - y_pred)²
              SS_tot = Σ(y_true - y_mean)²
        """
        ss_res = np.sum((y_true - y_pred) ** 2)
        # Safely compute mean for R² calculation
        y_mean = safe_mean(y_true, default=0.0)
        ss_tot = np.sum((y_true - y_mean) ** 2)
        return 1 - (ss_res / (ss_tot + 1e-12))

    def _check_noise(self):
        """Check if signal is dominated by noise."""
        if len(self.current) == 0: return True, "No Data"

        # Check 1: Absolute magnitude (Open Circuit / Noise floor)
        # Using 95th percentile to be robust against spikes
        max_current = np.percentile(np.abs(self.current), 95)
        if max_current < 1e-9: # 1 nA threshold
            return True, "Low Current (<1nA)"

        return False, ""

    def _weak_rectification_ratio(self):
        """
        Mean |I| asymmetry between positive and negative bias regions.
        More robust than single-point I(+V)/I(-V) on sub-nA forming sweeps.
        """
        pos_mask = self.voltage > 0.1
        neg_mask = self.voltage < -0.1
        if not (np.any(pos_mask) and np.any(neg_mask)):
            return 1.0

        pos_i = np.mean(np.abs(self.current[pos_mask]))
        neg_i = np.mean(np.abs(self.current[neg_mask]))
        if pos_i < 1e-15 and neg_i < 1e-15:
            return 1.0
        if pos_i >= neg_i:
            return pos_i / max(neg_i, 1e-15)
        return neg_i / max(pos_i, 1e-15)

    def _is_weak_rectifying_signal(self):
        """
        Sub-nA sweeps that still show diode-like polarity dependence.
        Typical of pre-forming / weakly conducting rectifying memristors.
        """
        if len(self.current) == 0:
            return False, 1.0

        p95 = np.percentile(np.abs(self.current), 95)
        if p95 >= 1e-9:
            return False, 1.0

        rect_ratio = self._weak_rectification_ratio()
        polarity_dependent = bool(self.classification_features.get('polarity_dependent'))
        i_range = float(np.max(self.current) - np.min(self.current))
        max_i = float(np.max(np.abs(self.current)))

        # Require clear asymmetry and measurable I-V span (not flat symmetric noise)
        structured = (
            polarity_dependent
            and rect_ratio >= 2.5
            and max_i > 0
            and i_range > 0.15 * max_i
        )
        return structured, rect_ratio

    def _is_formed_rectifying_signal(self):
        """
        Measurable-current diode-like devices (stable rectifying type, not just precursor).
        Distinct from memristive: strong polarity asymmetry without pinched switching.
        """
        if len(self.current) == 0:
            return False, 1.0

        p95 = np.percentile(np.abs(self.current), 95)
        if p95 < 1e-9:
            return False, 1.0

        rect_ratio = self._weak_rectification_ratio()
        feats = self.classification_features
        mean_on_off = safe_mean(self.on_off, default=1.0)

        if feats.get('pinched_hysteresis'):
            return False, rect_ratio
        if feats.get('double_zero_crossing', False):
            return False, rect_ratio

        # Switching + meaningful on/off normally suggests memristive, not
        # rectifying.  BUT: very high rectification (>10x) means the
        # apparent "switching" comes from polarity-dependent conduction,
        # so we should still allow rectifying classification.
        if (feats.get('switching_behavior') and mean_on_off > 4.0
                and rect_ratio < 10.0):
            return False, rect_ratio

        formed = (
            feats.get('polarity_dependent')
            and rect_ratio >= 5.0
            and not feats.get('pinched_hysteresis', False)
        )
        return formed, rect_ratio

    def _set_rectifying_classification(self, rect_ratio, *, tier='precursor'):
        """Apply rectifying device type (precursor sub-nA or formed diode)."""
        formed = tier == 'formed'
        self.classification_features['rectifying_tier'] = tier
        self.classification_features['rectification_ratio'] = rect_ratio
        self.classification_features['weak_rectifying'] = not formed
        self.classification_features['is_low_current'] = not formed
        self.classification_features['is_noisy'] = False

        if formed:
            self.classification_features['noise_reason'] = (
                f"Formed rectifying ({rect_ratio:.1f}x asymmetry)"
            )
            confidence = min(0.88, 0.72 + 0.02 * min(rect_ratio - 5.0, 10.0))
            reasoning = (
                f"Formed rectifying device ({rect_ratio:.1f}x I(+)/I(-) asymmetry); "
                "stable diode-like behaviour without memristive switching."
            )
            note = 'Legitimate rectifying device type; counts toward formed yield tier.'
        else:
            self.classification_features['noise_reason'] = (
                f"Low current, rectifying ({rect_ratio:.1f}x asymmetry)"
            )
            confidence = min(0.85, 0.70 + 0.03 * min(rect_ratio - 2.5, 5.0))
            reasoning = (
                f"Weak rectifying conduction below 1 nA (ratio {rect_ratio:.1f}x); "
                "likely pre-forming / polarity-dependent leak, not open circuit."
            )
            note = 'Useful forming precursor; track device over sweeps rather than discarding.'

        # Rectifying is a sub-category of memristive (polarity-dependent resistance).
        # Report as memristive; flag the rectifying character for downstream display.
        self.device_type = 'memristive'
        self.classification_features['rectifying_character'] = True
        self.classification_confidence = confidence
        self.classification_breakdown = {
            'memristive': round(confidence * 100),
            'memcapacitive': 0,
            'capacitive': 0,
            'conductive': 0,
            'ohmic': 0,
            'non_conductive': 0,
            'uncertain': 0,
        }
        self.classification_reasoning = reasoning
        self.classification_explanation = {
            'primary_reason': self.classification_features['noise_reason'],
            'device_type': 'memristive',
            'rectifying_character': True,
            'rectifying_tier': tier,
            'rectification_ratio': rect_ratio,
            'note': note,
        }
        self._calculate_rectifying_memristivity_score(rect_ratio, formed=formed)

    def _maybe_promote_to_formed_rectifying(self):
        """Reclassify conductive/ohmic/uncertain sweeps that are clearly diode-like."""
        if self.device_type in ('memristive', 'memcapacitive', 'non_conductive'):
            return False
        formed, rect_ratio = self._is_formed_rectifying_signal()
        if not formed:
            return False
        self._set_rectifying_classification(rect_ratio, tier='formed')
        return True

    def _calculate_rectifying_memristivity_score(self, rect_ratio, *, formed=False):
        """
        Memristivity score for rectifying devices.
        Precursor (sub-nA): rectification + polarity only, cap 40.
        Formed diode: higher cap (55) with conduction-level bonus.
        """
        breakdown = {}
        polarity_score = 12.0 if formed else 10.0
        breakdown['polarity_dependence'] = polarity_score

        rect_score = 0.0
        threshold = 5.0 if formed else 2.5
        if rect_ratio >= threshold:
            rect_score = min(30.0 if formed else 25.0, 10.0 + 5.0 * np.log10(rect_ratio / threshold))
        breakdown['rectification'] = rect_score

        if formed:
            p95 = np.percentile(np.abs(self.current), 95)
            if p95 >= 100e-9:
                conduction_score = 13.0
            elif p95 >= 10e-9:
                conduction_score = 10.0
            else:
                conduction_score = 6.0
            breakdown['conduction_level'] = conduction_score
            structure_score = 0.0
        else:
            conduction_score = 0.0
            structure_score = 5.0
            breakdown['weak_signal_structure'] = structure_score

        cap = 55.0 if formed else 40.0
        score = min(cap, polarity_score + rect_score + conduction_score + structure_score)
        self.memristivity_score = round(score, 1)
        self.memristivity_breakdown = breakdown
        self.classification_features['partial_memristivity'] = not formed
        return self.memristivity_score

    def _assign_forming_stage(self):
        """Label sweep position on the forming timeline."""
        dt = self.device_type or 'unknown'
        score = float(self.memristivity_score or 0)

        # If an abrupt current jump was detected, this is the actual forming sweep —
        # label it explicitly regardless of the general score tier.
        if self.classification_features.get('current_jump_detected', False):
            stage = 'forming_event'
            self.forming_stage = stage
            return stage

        if dt == 'memristive' and self.classification_features.get('rectifying_character', False):
            tier = self.classification_features.get('rectifying_tier', 'precursor')
            stage = 'formed_rectifying' if tier == 'formed' else 'precursor_rectifying'
        elif dt == 'memristive':
            if score >= 60:
                stage = 'formed_memristive'
            elif score >= 35:
                stage = 'forming_memristive'
            else:
                stage = 'weak_memristive'
        elif dt == 'memcapacitive':
            stage = 'forming_memcapacitive'
        elif dt == 'non_conductive':
            stage = 'unformed'
        elif dt in ('capacitive',):
            stage = 'unformed'
        elif dt == 'ohmic':
            stage = 'unformed'
        elif dt == 'conductive':
            # Distinguish a truly unformed conductive device from a post-forming
            # device cycling in its low-resistance state (LRS).  LRS indicators:
            #   • switching detected (device changes state)
            #   • current already in the µA range (> 100 nA p95)
            switching = self.classification_features.get('switching_behavior', False)
            i_level = float(np.percentile(np.abs(self.current), 95)) if len(self.current) > 0 else 0.0
            if switching and i_level > 1e-7:   # 100 nA threshold
                stage = 'lrs_cycling'
            else:
                stage = 'unformed'
        else:
            stage = 'unknown'

        self.forming_stage = stage
        return stage

    def _yield_bucket_for_sweep(self):
        """Per-sweep yield bucket for promising-device tracking."""
        dt = self.device_type or 'unknown'
        score = float(self.memristivity_score or 0)

        if dt == 'memristive':
            if self.classification_features.get('rectifying_character', False):
                if self.classification_features.get('rectifying_tier') == 'formed':
                    return 'formed'
                return 'forming'
            if score >= 50:
                return 'formed'
            return 'forming'
        if dt == 'memcapacitive':
            return 'forming'
        return 'none'

    def _finalize_forming_metadata(self):
        """Set forming_stage and yield_bucket on features + explanation."""
        self._assign_forming_stage()
        self.yield_bucket = self._yield_bucket_for_sweep()
        self.classification_features['forming_stage'] = self.forming_stage
        self.classification_features['yield_bucket'] = self.yield_bucket
        if isinstance(self.classification_explanation, dict):
            self.classification_explanation['forming_stage'] = self.forming_stage
            self.classification_explanation['yield_bucket'] = self.yield_bucket
            if self.memristivity_score is not None:
                self.classification_explanation['memristivity_score'] = self.memristivity_score

    def _classify_device(self):
        """
        Classify the device as memristive, capacitive, conductive, or ohmic.
        Based on I-V characteristics, hysteresis patterns, and conduction mechanisms.
        Uses configurable weights if provided, otherwise defaults.
        """
        try:
            device_info = f" [{self.device_name}]" if self.device_name else ""
            debug_print(f"\n[DIAGNOSTIC]{device_info} Starting classification...")
            
            # Extract classification features
            self.classification_features = self._extract_classification_features()
            
            # Check for noise
            is_noisy, noise_reason = self._check_noise()
            self.classification_features['is_noisy'] = is_noisy
            self.classification_features['noise_reason'] = noise_reason

            # === LOW-CURRENT STRUCTURED (WEAK RECTIFYING) ===
            weak_rectifying, rect_ratio = self._is_weak_rectifying_signal()
            if weak_rectifying:
                self._set_rectifying_classification(rect_ratio, tier='precursor')
                self._finalize_forming_metadata()
                return

            # === FORMED RECTIFYING (measurable current, diode-like) ===
            if not is_noisy:
                formed_rectifying, rect_ratio = self._is_formed_rectifying_signal()
                if formed_rectifying:
                    self._set_rectifying_classification(rect_ratio, tier='formed')
                    self._finalize_forming_metadata()
                    return

            # === NOISE / NON-CONDUCTIVE OVERRIDE ===
            if is_noisy:
                # Force critical features off so scoring cannot invent false memristive/capacitive types
                self.classification_features['has_hysteresis'] = False
                self.classification_features['switching_behavior'] = False
                self.classification_features['nonlinear_iv'] = False
                self.classification_features['pinched_hysteresis'] = False
                self.classification_features['double_zero_crossing'] = False

                self.device_type = 'non_conductive'
                self.classification_confidence = 0.85
                self.classification_breakdown = {
                    'memristive': 0,
                    'memcapacitive': 0,
                    'capacitive': 0,
                    'conductive': 0,
                    'ohmic': 0,
                    'non_conductive': 85,
                    'uncertain': 0,
                }
                self.classification_reasoning = (
                    f"Non-conductive (open circuit / noise floor): {noise_reason}"
                )
                self.classification_explanation = {
                    'primary_reason': noise_reason,
                    'device_type': 'non_conductive',
                    'note': 'Current below measurable switching range; not classifiable as memristive/ohmic/etc.',
                }
                self.classification_warnings.append(
                    f"Non-conductive device: {noise_reason}. Treat as open/noise, not uncertain."
                )
                self._finalize_forming_metadata()
                return
            # === ARTIFACT FILTERING ===
            # If pinched hysteresis is detected BUT device is linear with no switching,
            # it's likely measurement artifact, not true memristive behavior
            if (self.classification_features.get('pinched_hysteresis') and 
                self.classification_features.get('linear_iv') and 
                not self.classification_features.get('switching_behavior')):
                # This is likely an ohmic device with artifacts
                debug_print(f"[DIAGNOSTIC]{device_info} Artifact detected: pinched+linear+no_switching -> likely ohmic")
                self.classification_features['pinched_hysteresis'] = False
                # Keep has_hysteresis but mark as weak
                self.classification_features['artifact_hysteresis'] = True
                
            # === CONSISTENCY CHECK ===
            # If pinched loop is detected, hysteresis MUST be present (overriding area check)
            if self.classification_features.get('pinched_hysteresis'):
                self.classification_features['has_hysteresis'] = True

            # Get weights (use custom weights if provided, otherwise defaults)
            if self.classification_weights is None:
                weights = self._get_default_classification_weights()
            else:
                weights = self.classification_weights

            # Initialize scores for each device type
            scores = {
                'memristive': 0,
                'memcapacitive': 0,
                'capacitive': 0,
                'conductive': 0,
                'ohmic': 0,
                'uncertain': 0  # Added for low-confidence cases
            }

            # Score memristive characteristics (NOW CONFIGURABLE)
            if self.classification_features['has_hysteresis']:
                scores['memristive'] += weights.get('memristive_has_hysteresis', 25.0)
            if self.classification_features['pinched_hysteresis']:
                scores['memristive'] += weights.get('memristive_pinched_hysteresis', 30.0)
            if self.classification_features['switching_behavior']:
                # Switching matters, but by itself it is not enough:
                # many "closed" nonlinear curves look switch-like without any
                # hysteretic memory fingerprint.
                scores['memristive'] += weights.get('memristive_switching_behavior', 25.0)
                
                # Strong bonus only when switching is accompanied by an actual
                # memory signature (hysteresis or pinched loop).
                if (
                    self.classification_features['nonlinear_iv']
                    and (
                        self.classification_features['has_hysteresis']
                        or self.classification_features['pinched_hysteresis']
                    )
                ):
                    scores['memristive'] += weights.get('memristive_switching_plus_nonlinear_bonus', 20.0)
                    
            if self.classification_features['nonlinear_iv']:
                scores['memristive'] += weights.get('memristive_nonlinear_iv', 10.0)
            if self.classification_features['polarity_dependent']:
                scores['memristive'] += weights.get('memristive_polarity_dependent', 10.0)

            # Double zero crossing (figure-8) is a defining memristive
            # signature (Chua's fingerprint).  With memcapacitive
            # classification disabled this feature would otherwise
            # contribute nothing.  Give a stronger bonus when combined
            # with switching because the pair is highly specific.
            _has_dblx = self.classification_features.get('double_zero_crossing', False)
            if _has_dblx and self.classification_features.get('switching_behavior'):
                scores['memristive'] += weights.get('memristive_double_zero_crossing_with_switching', 15.0)
            elif _has_dblx:
                scores['memristive'] += weights.get('memristive_double_zero_crossing', 10.0)

            # === FORMING-EVENT BONUS ===
            # An abrupt current jump in the forward sweep is the direct
            # electrical signature of electroforming (filament creation).
            # It is highly specific to memristive behaviour and should push
            # an ambiguous score well above the uncertainty threshold.
            # The bonus scales with the magnitude of the jump to distinguish
            # a major forming event (>1000x) from a modest step (50-100x).
            if self.classification_features.get('current_jump_detected', False):
                jump_ratio = self.classification_features.get('current_jump_ratio', 1.0)
                if jump_ratio >= 1000:
                    jump_bonus = weights.get('memristive_bonus_forming_event_large', 35.0)
                elif jump_ratio >= 100:
                    jump_bonus = weights.get('memristive_bonus_forming_event_medium', 25.0)
                else:
                    jump_bonus = weights.get('memristive_bonus_forming_event_small', 15.0)
                scores['memristive'] += jump_bonus
                debug_print(
                    f"[DIAGNOSTIC]{device_info} Forming-event bonus applied: "
                    f"+{jump_bonus:.0f} (jump_ratio={jump_ratio:.1f}x, "
                    f"V_onset={self.classification_features.get('forming_voltage_onset', '?'):.2f}V)"
                )

            # --- On/off ratio & memory-signature awareness ---
            # A memristor can be ohmic/linear in each individual resistance
            # state yet switch between them.  Evidence of genuine state
            # changes (high symmetric on/off, or figure-8 double zero
            # crossing) means linear/ohmic penalties should not apply.
            #
            # Also: LRS / post-forming devices often show only a *small*
            # hysteresis loop (area below the adaptive detector) while
            # still switching ~≥1.5× between Ron/Roff at µA currents.
            # Treat that as memory evidence so they classify memristive
            # (weak) rather than conductive + hard −45 penalty.
            _mean_on_off = safe_mean(self.on_off, default=1.0)
            _i_p95 = (
                float(np.percentile(np.abs(self.current), 95))
                if len(self.current) > 0 else 0.0
            )

            # Guard: A strongly rectifying device (>10x polarity
            # asymmetry) can inflate on_off through rectification, not
            # state switching.
            _rect_ratio = self._weak_rectification_ratio()
            _is_strongly_rectifying = _rect_ratio > 10.0

            _lrs_modest_window = (
                self.classification_features.get('switching_behavior')
                and _mean_on_off >= 1.5
                and not _is_strongly_rectifying
                and _i_p95 > 1e-7  # same 100 nA floor as lrs_cycling
            )

            _has_memory_evidence = (
                self.classification_features.get('switching_behavior')
                and (
                    (_mean_on_off > 10 and not _is_strongly_rectifying)
                    or _has_dblx
                    or _lrs_modest_window
                )
            )

            if self.classification_features['linear_iv'] and not _has_memory_evidence:
                scores['memristive'] += weights.get('memristive_penalty_linear_iv', -20.0)
            if self.classification_features['ohmic_behavior'] and not _has_memory_evidence:
                scores['memristive'] += weights.get('memristive_penalty_ohmic', -30.0)

            # Switching without hysteresis/pinched signature -- severity
            # depends on evidence strength.  High symmetric on/off or a
            # figure-8 double zero crossing prove genuine resistive
            # switching even when the hysteresis loop area is below the
            # detector threshold.
            if (
                self.classification_features.get('switching_behavior')
                and not self.classification_features.get('has_hysteresis')
                and not self.classification_features.get('pinched_hysteresis')
            ):
                if _mean_on_off > 50 and not _is_strongly_rectifying:
                    scores['memristive'] += weights.get(
                        'memristive_bonus_switching_high_ratio', 20.0
                    )
                elif _has_dblx:
                    # Figure-8 IS a form of hysteresis (current follows
                    # different paths each direction) so no penalty.
                    pass
                elif _has_memory_evidence:
                    scores['memristive'] += weights.get(
                        'memristive_penalty_switching_moderate_ratio', -5.0
                    )
                    # LRS / small-loop: modest Ron↔Roff at µA currents is
                    # real memory even when loop area is below threshold.
                    # Bonus keeps memristive above UNCERTAIN_THRESHOLD.
                    if _lrs_modest_window:
                        scores['memristive'] += weights.get(
                            'memristive_bonus_lrs_modest_window', 30.0
                        )
                else:
                    scores['memristive'] += weights.get(
                        'memristive_penalty_switching_without_hysteresis', -45.0
                    )
            
            # === CRITICAL PENALTY: Missing core memristive features ===
            # A true memristor MUST have switching behavior (state change)
            # Without it, any hysteresis is likely artifact/capacitive
            if (self.classification_features.get('has_hysteresis') and 
                not self.classification_features.get('switching_behavior') and
                not self.classification_features.get('nonlinear_iv')):
                # Hysteresis without switching or nonlinearity = not memristive
                scores['memristive'] += weights.get('memristive_penalty_no_switching', -40.0)

            # Score capacitive characteristics (NOW CONFIGURABLE)
            if self.classification_features['has_hysteresis'] and not self.classification_features['pinched_hysteresis']:
                scores['capacitive'] += weights.get('capacitive_hysteresis_unpinched', 40.0)
            if self.classification_features['phase_shift'] > 45:
                scores['capacitive'] += weights.get('capacitive_phase_shift', 40.0)
            if self.classification_features['elliptical_hysteresis']:
                scores['capacitive'] += weights.get('capacitive_elliptical', 20.0)

            # Score memcapacitive characteristics (CONFIGURABLE - can be disabled)
            # CORRECTED LOGIC: Memcapacitors have DOUBLE zero crossing (not unpinched)
            # They show charge-dependent capacitance with butterfly/horizontal figure-8 pattern
            
            # Check if memcapacitive classification is enabled
            if self.ENABLE_MEMCAPACITIVE_CLASSIFICATION:
                # PRIMARY SIGNATURE: Double zero crossing (TWO crossings through origin per cycle)
                if self.classification_features.get('double_zero_crossing', False):
                    scores['memcapacitive'] += weights.get('memcapacitive_double_zero_crossing', 50.0)
            
                # SECONDARY: Phase shift indicates capacitive component
                if self.classification_features['phase_shift'] > 30: 
                     scores['memcapacitive'] += weights.get('memcapacitive_phase_shift', 20.0)
                
                # TERTIARY: Weak switching can be memcapacitive (charge-state dependent)
                if self.classification_features['switching_behavior']:
                     mean_onoff = safe_mean(self.on_off, default=1.0)
                     if mean_onoff > 2.0:
                         # Strong switching → penalize memcapacitive, favor memristive
                         scores['memcapacitive'] += weights.get('memcapacitive_penalty_strong_switching', -25.0)
                     else:
                         # Weak switching → could be memcapacitive
                         scores['memcapacitive'] += weights.get('memcapacitive_switching_behavior', 30.0)
                
                # Elliptical pattern (can indicate capacitive)
                if self.classification_features['elliptical_hysteresis']:
                    scores['memcapacitive'] += weights.get('memcapacitive_elliptical', 15.0)
                     
                if self.classification_features['nonlinear_iv']:
                     scores['memcapacitive'] += weights.get('memcapacitive_nonlinear_iv', 20.0)
                     
                # PENALTY: Single pinched crossing is memristive, NOT memcapacitive
                if self.classification_features['pinched_hysteresis']:
                     scores['memcapacitive'] += weights.get('memcapacitive_penalty_pinched', -30.0)
                
                # LEGACY support: Unpinched hysteresis (kept for backward compatibility but de-emphasized)
                # Only add points if NO double crossing detected (avoids double-counting)
                if (self.classification_features['has_hysteresis'] and 
                    not self.classification_features['pinched_hysteresis'] and
                    not self.classification_features.get('double_zero_crossing', False)):
                     scores['memcapacitive'] += weights.get('memcapacitive_hysteresis_unpinched', 20.0)  # Reduced from 40
            else:
                # Memcapacitive classification is DISABLED
                scores['memcapacitive'] = -999  # Force it to never win
                debug_print(f"[DIAGNOSTIC]{device_info} Memcapacitive classification is DISABLED")


            # Score conductive characteristics (updated per user requirements)
            # Conductive: Non-linear, non-ohmic, non-memristive, non-memcapacitive, non-capacitive
            # i.e., nonlinear but without hysteresis/switching (cannot be explained by capacitive or memristive)
            # When LRS/modest Ron-Roff switching is present, skip the no-hysteresis
            # conductive bonus — that pattern is better explained as weak memristive.
            if (
                not self.classification_features['has_hysteresis']
                and not _has_memory_evidence
            ):
                scores['conductive'] += weights.get('conductive_no_hysteresis', 30.0)
            if self.classification_features['nonlinear_iv'] and not self.classification_features['switching_behavior']:
                scores['conductive'] += weights.get('conductive_nonlinear_no_switching', 40.0)
            if self.conduction_mechanism in ['sclc', 'trap_sclc', 'poole_frenkel', 'schottky', 'fowler_nordheim']:
                scores['conductive'] += weights.get('conductive_advanced_mechanism', 30.0)

            # Bonus: switching present but no hysteresis loop detected.
            # Devices in a low-resistance state (LRS) or with abrupt threshold switching can
            # switch between states without showing a clear hysteresis loop in the IV curve.
            # Without this bonus, such devices score conductive=30 which falls below
            # UNCERTAIN_THRESHOLD=40 → they get misclassified as uncertain.
            # Skip when memory evidence already routes the sweep toward memristive.
            if (
                self.classification_features.get('switching_behavior', False)
                and not self.classification_features.get('has_hysteresis', False)
                and not self.classification_features.get('pinched_hysteresis', False)
                and not _has_memory_evidence
            ):
                scores['conductive'] += weights.get('conductive_has_switching', 15.0)

            # PENALTY: Reduce score if capacitive features are present (now using tunable weights)
            if self.classification_features['phase_shift'] > 30:
                scores['conductive'] += weights.get('conductive_penalty_phase_shift', -20.0)
            if self.classification_features['elliptical_hysteresis']:
                scores['conductive'] += weights.get('conductive_penalty_elliptical', -15.0)

            # === ENHANCED OHMIC SCORING SYSTEM ===
            # Score ohmic characteristics with graduated scoring for quality
            median_norm_area = float(np.median(np.abs(self.normalized_areas))) if self.normalized_areas else 0.0
            mean_on_off = safe_mean(self.on_off, default=1.0)
            has_compliance = self.compliance_current is not None and self.compliance_current > 0

            # Primary ohmic indicators
            is_linear = self.classification_features['linear_iv']
            is_ohmic_behavior = self.classification_features['ohmic_behavior']
            has_weak_hysteresis = self.classification_features.get('has_hysteresis', False) and median_norm_area < 1e-3
            has_strong_hysteresis = self.classification_features.get('has_hysteresis', False) and median_norm_area >= 1e-3
            no_switching = not self.classification_features['switching_behavior']
            
            # Graduated ohmic scoring system
            # 1. Strong ohmic: Linear + Ohmic behavior + No hysteresis
            if (is_linear and is_ohmic_behavior and 
                not self.classification_features['has_hysteresis'] and
                no_switching and mean_on_off < 1.5 and not has_compliance):
                scores['ohmic'] += weights.get('ohmic_strong', 80.0)
                
            # 2. Clear ohmic: Linear + No hysteresis + Small window
            elif (is_linear and not self.classification_features['has_hysteresis'] and
                  no_switching and median_norm_area < 1e-3 and mean_on_off < 1.5):
                scores['ohmic'] += weights.get('ohmic_clear', 70.0)
                
            # 3. Likely ohmic: Linear + Weak hysteresis (artifact) + No switching
            elif (is_linear and has_weak_hysteresis and no_switching and mean_on_off < 1.5):
                scores['ohmic'] += weights.get('ohmic_with_artifact', 60.0)
                
            # 4. Weak ohmic: Linear + Ohmic behavior but has some hysteresis
            elif (is_linear and is_ohmic_behavior and no_switching and mean_on_off < 2.0):
                scores['ohmic'] += weights.get('ohmic_weak', 40.0)
            
            # 5. Ohmic model support: If conduction model strongly indicates ohmic
            if (self.conduction_mechanism == 'ohmic' and 
                self.model_parameters.get('R2', 0) > 0.95):
                # Graduated bonus based on R² quality
                r2 = self.model_parameters.get('R2', 0)
                model_bonus = 20.0 if r2 > 0.98 else 15.0 if r2 > 0.95 else 10.0
                scores['ohmic'] += model_bonus
                
            # 6. Penalize ohmic if has strong features of other types (now using tunable weights)
            if has_strong_hysteresis and self.classification_features.get('switching_behavior'):
                scores['ohmic'] += weights.get('ohmic_penalty_strong_hysteresis_switching', -30.0)
            if self.classification_features.get('nonlinear_iv'):
                scores['ohmic'] += weights.get('ohmic_penalty_nonlinear', -20.0)

            # === COMPLIANCE-SATURATION PENALTY ===
            # Compliance current at ≥90% of max measured current means the hardware
            # limit was hit.  Switching features detected in such sweeps are unreliable
            # (the plateau looks like a HRS→LRS transition but is just the instrument).
            # Penalise memristive and conductive; note compliance_limited for review.
            max_i = float(np.max(np.abs(self.current))) if len(self.current) > 0 else 0.0
            compliance_saturated = (
                self.compliance_current is not None
                and self.compliance_current > 0
                and max_i > 0
                and (self.compliance_current / max_i) > 0.9
                and not self.classification_features.get('pinched_hysteresis', False)
                and safe_mean(self.on_off, default=1.0) < 10.0
            )
            if compliance_saturated:
                scores['memristive'] += weights.get('memristive_penalty_compliance_saturated', -25.0)
                scores['conductive'] += weights.get('conductive_penalty_compliance_saturated', -20.0)
                self.classification_features['compliance_limited'] = True
                debug_print(
                    f"[DIAGNOSTIC]{device_info} Compliance saturation penalty applied "
                    f"(compliance={self.compliance_current*1e6:.1f}µA, max_I={max_i*1e6:.1f}µA)"
                )
            else:
                self.classification_features['compliance_limited'] = False

            # === CAPACITIVE-LIKE TIE-BREAKER ===
            # Hysteresis without pinching and without any switching + significant phase shift
            # means the loop is most likely a capacitive artefact, not memory.
            # Apply an extra memristive penalty to prevent a borderline positive score
            # from accidentally winning over capacitive.
            if (
                self.classification_features.get('has_hysteresis', False)
                and not self.classification_features.get('pinched_hysteresis', False)
                and not self.classification_features.get('switching_behavior', False)
                and self.classification_features.get('phase_shift', 0) > 30
            ):
                scores['memristive'] += weights.get('memristive_penalty_capacitive_like', -30.0)
                debug_print(
                    f"[DIAGNOSTIC]{device_info} Capacitive-like tie-breaker applied "
                    f"(hysteresis+no_pinch+no_switching+phase_shift={self.classification_features['phase_shift']:.0f}°)"
                )

            # Keep breakdown and normalize to get confidence-style weights
            self.classification_breakdown = scores.copy()
            max_score = max(scores.values())
            total_score = sum(scores.values())
            
            # DIAGNOSTIC: Print scoring breakdown
            device_info = f" [{self.device_name}]" if self.device_name else ""
            debug_print(f"\n[DIAGNOSTIC]{device_info} Classification scores:")
            for device_type, score in scores.items():
                debug_print(f"  - {device_type}: {score:.1f}")
            debug_print(f"  - Total score: {total_score:.1f}, Max score: {max_score:.1f}")
            debug_print(f"  - Conduction mechanism: {self.conduction_mechanism}")

            # === UNCERTAIN CLASSIFICATION ===
            # If max score below threshold (default 40%), classify as "uncertain"
            if total_score == 0 or max_score < self.UNCERTAIN_THRESHOLD:
                self.device_type = 'uncertain'
                self.classification_confidence = min(max_score / 100.0, 1.0)
                debug_print(f"[DIAGNOSTIC]{device_info} !!! UNCERTAIN CLASSIFICATION !!!")
                if total_score == 0:
                    debug_print(f"[DIAGNOSTIC]{device_info}   Reason: All scores are 0 (no features detected)")
                else:
                    debug_print(f"[DIAGNOSTIC]{device_info}   Reason: Max score ({max_score:.1f}) is below threshold ({self.UNCERTAIN_THRESHOLD})")
                
                # For uncertain, note the top candidates
                sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                top_candidates = [f"{dtype} ({score:.1f})" for dtype, score in sorted_scores[:3] if score > 0]
                self.classification_reasoning = f"Uncertain classification - max score ({max_score:.1f}) below threshold ({self.UNCERTAIN_THRESHOLD}). Top candidates: {', '.join(top_candidates) if top_candidates else 'None'}"
            else:
                self.device_type = max(scores, key=scores.get)
                self.classification_confidence = min(max_score / 100.0, 1.0)
                debug_print(f"[DIAGNOSTIC]{device_info} Classification: {self.device_type} (confidence: {self.classification_confidence:.1%})")
            
            # === REALITY CHECK WARNINGS (Item 6) ===
            # Check for inconsistent features and raise red flags
            self._check_feature_consistency()


            # Provide a human-friendly explanation map
            self.classification_explanation = {
                'has_hysteresis': self.classification_features.get('has_hysteresis'),
                'pinched_hysteresis': self.classification_features.get('pinched_hysteresis'),
                'switching_behavior': self.classification_features.get('switching_behavior'),
                'switching_strength': self.classification_features.get('switching_strength', 0.0),
                'nonlinear_iv': self.classification_features.get('nonlinear_iv'),
                'polarity_dependent': self.classification_features.get('polarity_dependent'),
                'phase_shift': self.classification_features.get('phase_shift'),
                'elliptical_hysteresis': self.classification_features.get('elliptical_hysteresis'),
                'linear_iv': self.classification_features.get('linear_iv'),
                'ohmic_behavior': self.classification_features.get('ohmic_behavior'),
                'best_conduction_model': self.conduction_mechanism,
            }
            
            # === GENERATE DETAILED EXPLANATION (Item 8) ===
            if self.device_type != 'uncertain':
                self._generate_classification_explanation()

            # Promote conductive/ohmic/uncertain diode-like sweeps to formed rectifying
            self._maybe_promote_to_formed_rectifying()
            
            # === ENHANCED CLASSIFICATION (Phase 1) ===
            # Calculate additional metrics without affecting core classification
            if self.enhanced_classification_enabled:
                try:
                    self.calculate_enhanced_classification()
                except Exception as e:
                    # Silently fail - don't disrupt core classification
                    self.classification_warnings.append(f"Enhanced classification error: {str(e)}")

            self._finalize_forming_metadata()
                    
        except Exception as e:
            device_info = f" [{self.device_name}]" if self.device_name else ""
            debug_print(f"\n[DIAGNOSTIC]{device_info} !!! ERROR IN CLASSIFICATION !!!")
            debug_print(f"[DIAGNOSTIC]{device_info} Exception: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Set safe defaults
            self.device_type = 'uncertain'
            self.classification_confidence = 0.0
            self.classification_breakdown = {'memristive': 0, 'memcapacitive': 0, 'capacitive': 0, 'conductive': 0, 'ohmic': 0}
            self.classification_features = {}
            self.classification_explanation = {}

    def _check_feature_consistency(self):
        """
        Check for inconsistent features and raise warnings (red flags).
        This DOES NOT reduce confidence - just warns the user.
        
        Reality checks:
        - Switching contradicts ohmic
        - Linear contradicts memristive
        - Strong hysteresis with no switching
        - etc.
        """
        features = self.classification_features
        device_info = f" [{self.device_name}]" if self.device_name else ""
        
        # Red Flag 1: Classified as Memristive but NO switching behavior
        if self.device_type == 'memristive' and not features.get('switching_behavior', False):
            self.classification_warnings.append(
                f"⚠ RED FLAG: Classified as memristive but switching_behavior is False. "
                f"True memristors require resistance switching."
            )
        
        # Red Flag 2: Classified as Ohmic but has strong switching
        if self.device_type == 'ohmic' and features.get('switching_behavior', False):
            mean_onoff = safe_mean(self.on_off, default=1.0)
            if mean_onoff > 2.0:
                self.classification_warnings.append(
                    f"⚠ RED FLAG: Classified as ohmic but shows switching (ON/OFF={mean_onoff:.2f}). "
                    f"Ohmic devices should not switch states."
                )
        
        # Red Flag 3: Classified as Memristive but linear I-V.
        # For forming-stage devices the classifier fires on switching-only sweeps where
        # each resistance state is individually linear — that is expected physics and
        # generates a flood of noise in the review GUI.  Only emit the full RED FLAG for
        # formed devices (mem_score >= 60); emit a softer INFO note for forming ones.
        if self.device_type == 'memristive' and features.get('linear_iv', False):
            mem_sc = float(self.memristivity_score or 0)
            if mem_sc >= 60:
                self.classification_warnings.append(
                    "⚠ RED FLAG: Classified as memristive but I-V is linear. "
                    "Memristors typically show nonlinear I-V characteristics."
                )
            else:
                # forming_memristive / weak_memristive: device switches between two
                # roughly-linear resistance states — normal for early forming cycles.
                self.classification_warnings.append(
                    "INFO: Forming-stage memristive with linear per-state I-V "
                    "(device switches between linear resistance states — expected for early forming)."
                )
        
        # Red Flag 4: Strong hysteresis but no switching (might be capacitive/artifact)
        if (features.get('has_hysteresis', False) and 
            not features.get('switching_behavior', False) and
            self.device_type == 'memristive'):
            median_area = float(np.median(np.abs(self.normalized_areas))) if self.normalized_areas else 0.0
            if median_area > 1e-2:
                self.classification_warnings.append(
                    f"⚠ WARNING: Large hysteresis (area={median_area:.2e}) but no switching detected. "
                    f"May be capacitive or artifact."
                )
        
        # Red Flag 5: Pinched hysteresis but classified as something other than memristive
        if (features.get('pinched_hysteresis', False) and 
            self.device_type not in ['memristive', 'memcapacitive']):
            self.classification_warnings.append(
                f"⚠ WARNING: Pinched hysteresis detected (memristive fingerprint) but classified as {self.device_type}. "
                f"Consider if classification is correct."
            )
        
        # Red Flag 6: Compliance current detected (affects classification)
        if self.compliance_current is not None and self.compliance_current > 0:
            max_i = np.max(np.abs(self.current)) if len(self.current) > 0 else 0
            if max_i > 0 and self.compliance_current / max_i > 0.9:
                self.classification_warnings.append(
                    f"⚠ WARNING: Current compliance detected ({self.compliance_current*1e6:.2f}µA). "
                    f"This may affect switching behavior and classification accuracy."
                )
        
        # Red Flag 7: Very low data quality (SNR)
        if 'noise_floor' in self.adaptive_thresholds:
            max_i = np.max(np.abs(self.current)) if len(self.current) > 0 else 0
            noise = self.adaptive_thresholds['noise_floor']
            if max_i > 0 and noise > 0:
                snr = max_i / noise
                if snr < 20:
                    self.classification_warnings.append(
                        f"⚠ WARNING: Low SNR (≈{snr:.1f}). Signal may be affected by noise. "
                        f"Classification confidence may be reduced."
                    )

        # ---------------------------------------------------------------
        # POST-CLASSIFICATION OVERRIDES
        # Only applied for unambiguous contradictions where the physical
        # interpretation is clear.  Each override logs a warning so it
        # is visible during review.  The breakdown scores are NOT changed
        # here — only device_type and confidence, to preserve traceability.
        # ---------------------------------------------------------------

        # Override A: Classified memristive but has NO switching at all AND
        # the phase shift strongly suggests capacitive behaviour.
        # This catches hysteresis-only loops that beat the memristive score
        # through a combination of has_hysteresis + polarity bonuses.
        if (
            self.device_type == 'memristive'
            and not features.get('switching_behavior', False)
            and not features.get('pinched_hysteresis', False)
            and features.get('phase_shift', 0) > 45
        ):
            old_type = self.device_type
            self.device_type = 'capacitive'
            self.classification_confidence = min(self.classification_confidence, 0.55)
            self.classification_warnings.append(
                f"⚠ OVERRIDE A: Reclassified {old_type} → capacitive "
                "(no switching, no pinch, strong phase shift). "
                "Review if this is a true memristor."
            )
            debug_print(f"[DIAGNOSTIC]{device_info} Override A: memristive → capacitive")

        # Override B: Classified ohmic but shows clear state switching
        # (on/off > 5 AND pinched hysteresis detected).
        # Ohmic devices cannot switch resistance states.
        elif (
            self.device_type == 'ohmic'
            and features.get('pinched_hysteresis', False)
            and features.get('switching_behavior', False)
            and safe_mean(self.on_off, default=1.0) > 5.0
        ):
            breakdown = getattr(self, 'classification_breakdown', {})
            mem_score = breakdown.get('memristive', 0)
            old_type = self.device_type
            # Only flip if memristive score was competitive (2nd place)
            if mem_score > 30:
                self.device_type = 'memristive'
                self.classification_confidence = min(self.classification_confidence, 0.70)
                self.classification_warnings.append(
                    f"⚠ OVERRIDE B: Reclassified {old_type} → memristive "
                    f"(pinched+switching+on/off={safe_mean(self.on_off,default=1.0):.1f}x despite linear I-V). "
                    "Review if ohmic state-switching or forming."
                )
                debug_print(f"[DIAGNOSTIC]{device_info} Override B: ohmic → memristive")
            else:
                # Score gap is too large to flip — cap confidence and flag for review
                self.classification_confidence = min(self.classification_confidence, 0.50)
                self.classification_warnings.append(
                    f"⚠ OVERRIDE B (soft): Ohmic with pinched+switching detected; "
                    "memristive score too low to flip but confidence capped. Flag for review."
                )

        # Override C: Pinched hysteresis detected but winner is conductive.
        # Pinched loop is the Chua fingerprint — conductive should not win.
        # Cap confidence and flag for high-priority review; do NOT auto-flip
        # because the device may genuinely be in a conductive (LRS) state.
        elif (
            self.device_type == 'conductive'
            and features.get('pinched_hysteresis', False)
        ):
            self.classification_confidence = min(self.classification_confidence, 0.50)
            self.classification_warnings.append(
                "⚠ OVERRIDE C: Conductive + pinched hysteresis — confidence capped. "
                "Device may be in LRS (formed memristive). Flag for high-priority review."
            )
            debug_print(f"[DIAGNOSTIC]{device_info} Override C: conductive+pinched → confidence capped")

        debug_print(f"[DIAGNOSTIC]{device_info} Reality checks: {len(self.classification_warnings)} warnings raised")
    
    def _generate_classification_explanation(self):
        """
        Generate detailed explanation of WHY this classification was chosen.
        Includes primary indicators, concerns, and interpretation.
        """
        features = self.classification_features
        scores = self.classification_breakdown
        
        # Get top 3 scoring categories
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_3 = [(dtype, score) for dtype, score in sorted_scores[:3] if score > 0]
        
        explanation_parts = []
        
        # Header
        confidence_pct = self.classification_confidence * 100
        explanation_parts.append(f"Classification: {self.device_type.upper()} ({confidence_pct:.0f}%)")
        explanation_parts.append("")
        
        # Primary indicators (why this classification won)
        primary_indicators = []
        if self.device_type == 'memristive':
            if features.get('switching_behavior'):
                onoff = safe_mean(self.on_off, default=1.0)
                strength = features.get('switching_strength', 0)
                primary_indicators.append(f"✓ Switching behavior detected (ON/OFF: {onoff:.2f}, Strength: {strength:.0f}%)")
            if features.get('pinched_hysteresis'):
                primary_indicators.append(f"✓ Pinched hysteresis loop (memristive fingerprint)")
            if features.get('nonlinear_iv'):
                primary_indicators.append(f"✓ Nonlinear I-V characteristic")
            if features.get('has_hysteresis'):
                area = float(np.median(np.abs(self.normalized_areas))) if self.normalized_areas else 0
                primary_indicators.append(f"✓ Hysteresis present (area: {area:.2e})")
        
        elif self.device_type == 'ohmic':
            if features.get('linear_iv'):
                primary_indicators.append(f"✓ Linear I-V relationship")
            if features.get('ohmic_behavior'):
                primary_indicators.append(f"✓ Ohmic behavior at low voltages")
            if not features.get('has_hysteresis'):
                primary_indicators.append(f"✓ No hysteresis detected")
            elif features.get('has_hysteresis'):
                area = float(np.median(np.abs(self.normalized_areas))) if self.normalized_areas else 0
                if area < 1e-3:
                    primary_indicators.append(f"✓ Minimal hysteresis (area: {area:.2e}, likely artifact)")
        
        elif self.device_type == 'capacitive':
            if features.get('phase_shift', 0) > 30:
                primary_indicators.append(f"✓ Significant phase shift ({features['phase_shift']:.1f}°)")
            if features.get('elliptical_hysteresis'):
                primary_indicators.append(f"✓ Elliptical hysteresis pattern")
            if features.get('has_hysteresis') and not features.get('pinched_hysteresis'):
                primary_indicators.append(f"✓ Unpinched hysteresis loop")
        
        elif self.device_type == 'memcapacitive':
            if features.get('double_zero_crossing'):
                primary_indicators.append(f"✓ Double zero-crossing pattern")
            if features.get('phase_shift', 0) > 20:
                primary_indicators.append(f"✓ Capacitive component (phase shift: {features['phase_shift']:.1f}°)")
            if features.get('switching_behavior'):
                primary_indicators.append(f"✓ Weak switching (charge-dependent)")
        
        elif self.device_type == 'conductive':
            if features.get('nonlinear_iv'):
                primary_indicators.append(f"✓ Nonlinear I-V characteristic")
            if not features.get('has_hysteresis'):
                primary_indicators.append(f"✓ No hysteresis (non-memristive)")
            if self.conduction_mechanism and self.conduction_mechanism != 'ohmic':
                primary_indicators.append(f"✓ Advanced conduction: {self.conduction_mechanism}")
        
        if primary_indicators:
            explanation_parts.append("Primary Indicators:")
            explanation_parts.extend(primary_indicators)
            explanation_parts.append("")
        
        # Concerns (red flags or weak points)
        concerns = []
        if self.device_type == 'memristive':
            if not features.get('pinched_hysteresis'):
                concerns.append(f"⚠ No pinched hysteresis (non-ideal memristor)")
            if features.get('phase_shift', 0) > 20:
                concerns.append(f"⚠ Phase shift present ({features['phase_shift']:.1f}°) - capacitive component")
            if features.get('linear_iv'):
                concerns.append(f"⚠ I-V appears linear - unusual for memristors")
        
        if concerns:
            explanation_parts.append("Concerns:")
            explanation_parts.extend(concerns)
            explanation_parts.append("")
        
        # Interpretation
        interpretation = ""
        if self.device_type == 'memristive':
            if features.get('pinched_hysteresis') and features.get('switching_behavior'):
                interpretation = "Ideal memristive device with clean switching and pinched loop."
            elif features.get('switching_behavior') and not features.get('pinched_hysteresis'):
                interpretation = "Memristive device with non-ideal pinching. Possibly due to series resistance, parasitic capacitance, or contact effects."
            else:
                interpretation = "Classified as memristive but lacks strong indicators. Confidence is moderate."
        elif self.device_type == 'ohmic':
            if features.get('has_hysteresis'):
                interpretation = "Ohmic device with measurement artifacts (minor hysteresis). Essentially resistive behavior."
            else:
                interpretation = "Clean ohmic behavior - linear resistor."
        
        if interpretation:
            explanation_parts.append("Interpretation:")
            explanation_parts.append(interpretation)
            explanation_parts.append("")
        
        # Alternatives (if close competition)
        if len(top_3) > 1:
            runner_up_name, runner_up_score = top_3[1]
            if runner_up_score > confidence_pct * 0.6:  # Within 60% of winner
                explanation_parts.append(f"Alternative: {runner_up_name.title()} ({runner_up_score:.0f}%)")
        
        # Store as formatted string
        self.classification_reasoning = "\n".join(explanation_parts)
        
        debug_print(f"[DIAGNOSTIC] Classification explanation generated ({len(explanation_parts)} lines)")
    
    def _get_default_classification_weights(self):
        """
        Return default classification weights.
        Loads from JSON config file if available, otherwise uses hardcoded defaults.
        """
        # Try to load from JSON file first
        try:
            import os
            import json
            
            # Look for the weights file in Json_Files directory
            # Get the path relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(current_dir, '..', '..', 'Json_Files', 'classification_weights.json')
            json_path = os.path.normpath(json_path)
            
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    config = json.load(f)
                    weights = config.get('weights', {})
                    if weights:
                        return weights
        except Exception as e:
            # If loading fails, fall back to hardcoded defaults
            print(f"[WARNING] Could not load classification weights from JSON: {e}")
            print(f"[WARNING] Using hardcoded default weights")
        
        # Fallback: hardcoded default weights
        return {
            # Memristive
            'memristive_has_hysteresis': 25.0,
            'memristive_pinched_hysteresis': 30.0,
            'memristive_switching_behavior': 25.0,
            'memristive_switching_plus_nonlinear_bonus': 20.0,  # NEW v1.3: Bonus for switching + nonlinearity
            'memristive_nonlinear_iv': 10.0,
            'memristive_polarity_dependent': 10.0,
            'memristive_penalty_linear_iv': -20.0,
            'memristive_penalty_ohmic': -30.0,
            'memristive_penalty_switching_without_hysteresis': -45.0,
            'memristive_penalty_no_switching': -40.0,
            # Capacitive
            'capacitive_hysteresis_unpinched': 40.0,
            'capacitive_phase_shift': 40.0,
            'capacitive_elliptical': 20.0,
            # Memcapacitive (CORRECTED v1.4: Double zero crossing is THE signature)
            'memcapacitive_double_zero_crossing': 50.0,  # NEW v1.4: PRIMARY signature
            'memcapacitive_phase_shift': 20.0,
            'memcapacitive_switching_behavior': 30.0,
            'memcapacitive_penalty_strong_switching': -25.0,
            'memcapacitive_elliptical': 15.0,  # NEW v1.4: Elliptical pattern support
            'memcapacitive_nonlinear_iv': 20.0,
            'memcapacitive_penalty_pinched': -30.0,  # Increased from -20 (v1.4)
            'memcapacitive_hysteresis_unpinched': 20.0,  # Legacy, reduced from 40 (v1.4)
            # Conductive
            'conductive_no_hysteresis': 30.0,
            'conductive_nonlinear_no_switching': 40.0,
            'conductive_advanced_mechanism': 30.0,
            # Ohmic (Enhanced graduated scoring)
            'ohmic_strong': 80.0,           # Perfect ohmic: linear + ohmic behavior + no hysteresis
            'ohmic_clear': 70.0,            # Clear ohmic: linear + no hysteresis
            'ohmic_with_artifact': 60.0,    # Linear with weak hysteresis artifact
            'ohmic_weak': 40.0,             # Linear + ohmic behavior but some hysteresis
            # Legacy weights (kept for backwards compatibility if used in custom configs)
            'ohmic_linear_clean': 60.0,
            'ohmic_model_fit': 20.0,
        }

    def _calculate_advanced_metrics(self):
        """
        Calculate additional metrics for memristor characterization.
        Each metric is explained in detail within the calculation.
        """
        # Calculate metrics for each cycle
        for idx in range(len(self.split_v_data)):
            v_data = np.array(self.split_v_data[idx])
            i_data = np.array(self.split_c_data[idx])
            #print(i_data)

            # todo fix this , maybe fix splitting functions
            # Check if v_data is valid (not all zeros, has variation)
            if len(v_data) == 0 or len(i_data) == 0:
                # Skip empty data
                continue

            # Switching ratio (Roff/Ron)
            # This indicates the memory window - higher is better for digital memory
            # Typical good values: >10 for ReRAM, >100 for excellent devices
