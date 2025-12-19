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


def safe_mean(arr, default=0.0):
    """Safely compute mean, handling empty arrays and invalid values."""
    if arr is None or len(arr) == 0:
        return default
    arr = np.array(arr)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return default
    return float(np.mean(arr))


def safe_std(arr, default=0.0):
    """Safely compute standard deviation, handling empty arrays and invalid values."""
    if arr is None or len(arr) == 0:
        return default
    arr = np.array(arr)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2:
        return default
    return float(np.std(arr))


def safe_var(arr, default=0.0):
    """Safely compute variance, handling empty arrays and invalid values."""
    if arr is None or len(arr) == 0:
        return default
    arr = np.array(arr)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2:
        return default
    return float(np.var(arr))


class analyze_single_file:
    """
    Class for comprehensive analysis of memristor device measurements.
    Supports I-V characterization, pulse measurements, endurance, and retention testing.
    Includes theoretical model fitting and advanced device classification.
    """

    def __init__(self, voltage, current, time=None, measurement_type='iv_sweep', analysis_level='full'):
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
        """
        # Support original two-parameter call
        if isinstance(time, str):
            measurement_type = time
            time = None
        self.voltage = self._ensure_1d_array(voltage)
        self.current = self._ensure_1d_array(current)
        self.time = self._ensure_1d_array(time) if time is not None else None
        self.measurement_type = self._detect_measurement_type(measurement_type)
        # Fallback: if a time-based type was requested/detected but time is missing, degrade to iv_sweep
        if self.time is None and self.measurement_type in {'pulse', 'retention'}:
            self.measurement_type = 'iv_sweep'
        self.analysis_level = analysis_level if analysis_level in {'basic','classification','full','research'} else 'full'
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
        
        # === ENHANCED CLASSIFICATION (Phase 1) ===
        # These are ADDITIONAL metrics that don't affect core classification
        self.memristivity_score = None  # 0-100 continuous score
        self.memristivity_breakdown = {}  # Contribution of each feature to score
        self.adaptive_thresholds = {}  # Context-aware thresholds
        self.memory_window_quality = {}  # Detailed window quality metrics
        self.hysteresis_shape_features = {}  # Shape analysis
        self.classification_warnings = []  # Physical plausibility warnings
        self.enhanced_classification_enabled = True  # Can be disabled if needed
        
        # === DEVICE TRACKING (Phase 2) ===
        self.device_id = None  # Unique device identifier
        self.cycle_number = None  # Current cycle/measurement number
        self.save_directory = None  # Where to save tracking data
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
        self.last_report = None  # cache for the most recent generated report

        # Process based on measurement type
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

        # Check if this might be a pulse measurement
        if self.time is not None:
            # Check for step-like voltage changes
            v_diff = np.diff(self.voltage)
            if np.max(np.abs(v_diff)) > 10 * np.median(np.abs(v_diff)):
                return 'pulse'

            # Check for long constant voltage periods (retention)
            if len(np.unique(self.voltage)) < len(self.voltage) / 10:
                return 'retention'

        # Check for multiple cycles (endurance)
        if self._detect_cycles() > 10:
            return 'endurance'

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
            # Resistance state degradation
            ron_degradation = (self.ron[-1] - self.ron[0]) / self.ron[0] if self.ron[0] > 0 else 0
            roff_degradation = (self.roff[-1] - self.roff[0]) / self.roff[0] if self.roff[0] > 0 else 0

            self.state_degradation = {
                'ron_degradation': ron_degradation,
                'roff_degradation': roff_degradation,
                'window_degradation': (self.on_off[-1] - self.on_off[0]) / self.on_off[0] if self.on_off[0] > 0 else 0,
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
        except:
            print("Warning: Could not fit retention model")

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

    def _classify_device(self):
        """
        Classify the device as memristive, capacitive, conductive, or ohmic.
        Based on I-V characteristics, hysteresis patterns, and conduction mechanisms.
        """
        # Extract classification features
        self.classification_features = self._extract_classification_features()

        # Initialize scores for each device type
        scores = {
            'memristive': 0,
            'capacitive': 0,
            'conductive': 0,
            'ohmic': 0
        }

        # Score memristive characteristics
        if self.classification_features['has_hysteresis']:
            scores['memristive'] += 25
        if self.classification_features['pinched_hysteresis']:
            scores['memristive'] += 30
        if self.classification_features['switching_behavior']:
            scores['memristive'] += 25
        if self.classification_features['nonlinear_iv']:
            scores['memristive'] += 10
        if self.classification_features['polarity_dependent']:
            scores['memristive'] += 10

        # PENALTIES: Prevent linear/ohmic devices from being classified as memristors
        if self.classification_features['linear_iv']:
            scores['memristive'] -= 20
        if self.classification_features['ohmic_behavior']:
            scores['memristive'] -= 30

        # Score capacitive characteristics
        if self.classification_features['has_hysteresis'] and not self.classification_features['pinched_hysteresis']:
            scores['capacitive'] += 40
        if self.classification_features['phase_shift'] > 45:
            scores['capacitive'] += 40
        if self.classification_features['elliptical_hysteresis']:
            scores['capacitive'] += 20

        # Score conductive characteristics (non-ohmic)
        if not self.classification_features['has_hysteresis']:
            scores['conductive'] += 30
        if self.classification_features['nonlinear_iv'] and not self.classification_features['switching_behavior']:
            scores['conductive'] += 40
        if self.conduction_mechanism in ['sclc', 'trap_sclc', 'poole_frenkel', 'schottky', 'fowler_nordheim']:
            scores['conductive'] += 30

        # Score ohmic characteristics (guarded to avoid false-ohmic due to compliance or small-signal linearity)
        median_norm_area = float(np.median(np.abs(self.normalized_areas))) if self.normalized_areas else 0.0
        mean_on_off = safe_mean(self.on_off, default=1.0)
        has_compliance = self.compliance_current is not None and self.compliance_current > 0

        # Only consider ohmic if: linear_iv AND no clear hysteresis AND small memory window AND no compliance plateau
        if (self.classification_features['linear_iv']
            and not self.classification_features['has_hysteresis']
            and not self.classification_features['switching_behavior']
            and median_norm_area < 1e-3
            and mean_on_off < 1.5
            and not has_compliance):
            scores['ohmic'] += 60
        # Additional support for ohmic if model fit indicates ohmic strongly and still passes guards
        if (self.conduction_mechanism == 'ohmic'
            and self.model_parameters.get('R2', 0) > 0.98
            and median_norm_area < 1e-3
            and mean_on_off < 1.5
            and not has_compliance):
            scores['ohmic'] += 20

        # Keep breakdown and normalize to get confidence-style weights
        self.classification_breakdown = scores.copy()
        max_score = max(scores.values())
        total_score = sum(scores.values())

        if total_score == 0 or max_score < 30:
            self.device_type = 'uncertain'
            self.classification_confidence = 0.0
        else:
            self.device_type = max(scores, key=scores.get)
            self.classification_confidence = max_score / 100.0

        # Provide a human-friendly explanation map
        self.classification_explanation = {
            'has_hysteresis': self.classification_features.get('has_hysteresis'),
            'pinched_hysteresis': self.classification_features.get('pinched_hysteresis'),
            'switching_behavior': self.classification_features.get('switching_behavior'),
            'nonlinear_iv': self.classification_features.get('nonlinear_iv'),
            'polarity_dependent': self.classification_features.get('polarity_dependent'),
            'phase_shift': self.classification_features.get('phase_shift'),
            'elliptical_hysteresis': self.classification_features.get('elliptical_hysteresis'),
            'linear_iv': self.classification_features.get('linear_iv'),
            'ohmic_behavior': self.classification_features.get('ohmic_behavior'),
            'best_conduction_model': self.conduction_mechanism,
        }
        
        # === ENHANCED CLASSIFICATION (Phase 1) ===
        # Calculate additional metrics without affecting core classification
        if self.enhanced_classification_enabled:
            try:
                self.calculate_enhanced_classification()
            except Exception as e:
                # Silently fail - don't disrupt core classification
                self.classification_warnings.append(f"Enhanced classification error: {str(e)}")

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
            if idx < len(self.ron) and self.ron[idx] > 0:
                ratio = self.roff[idx] / self.ron[idx]
                self.switching_ratio.append(ratio)
            else:
                self.switching_ratio.append(1.0)

            # Window margin: (Roff - Ron) / Ron
            # Normalized memory window - indicates how much the resistance changes
            # Values >1 indicate >100% change in resistance
            if idx < len(self.ron) and self.ron[idx] > 0:
                margin = (self.roff[idx] - self.ron[idx]) / self.ron[idx]
                self.window_margin.append(margin)
            else:
                self.window_margin.append(0.0)

            # Rectification ratio: I(+V) / I(-V)
            # Indicates diode-like behavior - symmetric devices have ratio ~1
            # Asymmetric devices (diode-like) have ratio >10
            rect_ratio = self._calculate_rectification_ratio(v_data, i_data)
            self.rectification_ratio.append(rect_ratio)

            # Nonlinearity factor
            # Measures deviation from linear I-V relationship
            # 0 = perfectly linear (resistor), 1 = highly nonlinear
            nonlin = self._calculate_nonlinearity(v_data, i_data)
            self.nonlinearity_factor.append(nonlin)

            # Asymmetry factor
            # Measures difference between positive and negative voltage response
            # 0 = perfectly symmetric, 1 = completely asymmetric
            asym = self._calculate_asymmetry(v_data, i_data)
            self.asymmetry_factor.append(asym)

            # Power consumption
            # Average power dissipated during operation (W)
            # Lower is better for low-power applications
            power = np.mean(np.abs(v_data * i_data))
            self.power_consumption.append(power)

            # Energy per switch
            # Total energy required to switch device state (J)
            # Critical for neuromorphic and low-power applications
            if idx < len(self.von) and idx < len(self.voff):
                energy = self._calculate_switching_energy(v_data, i_data,
                                                          self.von[idx], self.voff[idx])
                self.energy_per_switch.append(energy)

        # Calculate overall device metrics
        self._calculate_retention_score()
        self._calculate_endurance_score()

        # Detect compliance current
        self.compliance_current = self._detect_compliance_current()

    def _calculate_research_diagnostics(self):
        """Compute additional diagnostics for deep research analysis."""
        try:
            v = np.asarray(self.voltage)
            i = np.asarray(self.current)
            if len(v) < 5:
                return

            # Noise floor at low |V|
            low_mask = np.abs(v) < 0.05 * max(1e-9, np.max(np.abs(v)))
            if np.any(low_mask):
                self.noise_floor = float(np.std(i[low_mask]))

            # Pinch offset near zero (mean |I| around V≈0)
            near0 = np.abs(v) < 0.02 * (np.max(np.abs(v)) + 1e-12)
            if np.any(near0):
                self.pinch_offset = float(np.mean(np.abs(i[near0])))

            # Hysteresis direction via signed area
            try:
                signed_area = float(np.trapezoid(i, v))
                if signed_area > 0:
                    self.hysteresis_direction = 'counter_clockwise'
                elif signed_area < 0:
                    self.hysteresis_direction = 'clockwise'
                else:
                    self.hysteresis_direction = 'none'
            except Exception:
                pass

            # Negative differential resistance index (fraction of dI/dV < 0)
            try:
                di = np.diff(i)
                dv = np.diff(v)
                slope = di / (dv + 1e-18)
                self.ndr_index = float(np.mean(slope < 0))
            except Exception:
                pass

            # Switching polarity (very heuristic): compare |Von| vs |Voff|
            if self.von and self.voff:
                if (np.mean(self.von) > 0 and np.mean(self.voff) < 0) or (np.mean(self.von) < 0 and np.mean(self.voff) > 0):
                    self.switching_polarity = 'bipolar'
                else:
                    self.switching_polarity = 'unipolar'

            # Kink voltage estimate: where local slope exponent n = dlogI/dlogV spikes
            try:
                pos = v > 0
                if np.sum(pos) > 10:
                    vp = v[pos]
                    ip = np.abs(i[pos]) + 1e-18
                    logv = np.log(vp + 1e-18)
                    logi = np.log(ip)
                    n = np.gradient(logi) / (np.gradient(logv) + 1e-18)
                    self.slope_exponent_stats = {
                        'mean_n': float(np.mean(n)),
                        'std_n': float(np.std(n)),
                        'max_n': float(np.max(n)),
                    }
                    # Peak position (rough estimate)
                    peak_idx = int(np.argmax(n))
                    self.kink_voltage = float(vp[peak_idx])
            except Exception:
                pass

            # Loop similarity between first two loops (correlation of re-sampled I(V))
            try:
                if len(self.split_v_data) >= 2:
                    v1 = np.asarray(self.split_v_data[0])
                    i1 = np.asarray(self.split_c_data[0])
                    v2 = np.asarray(self.split_v_data[1])
                    i2 = np.asarray(self.split_c_data[1])
                    common_v = np.linspace(max(v1.min(), v2.min()), min(v1.max(), v2.max()), 200)
                    if common_v.size > 10:
                        i1i = np.interp(common_v, v1, i1)
                        i2i = np.interp(common_v, v2, i2)
                        c = np.corrcoef(i1i, i2i)[0, 1]
                        self.loop_similarity_score = float(c)
            except Exception:
                pass
        except Exception:
            pass

    def _calculate_retention_score(self):
        """
        Calculate retention stability score based on resistance variation.

        Retention score = 1 / (1 + CV_Ron + CV_Roff)
        where CV = coefficient of variation = std/mean

        Score interpretation:
        - 1.0 = perfect retention (no variation)
        - 0.5 = moderate retention
        - <0.3 = poor retention
        """
        if len(self.ron) > 1 and len(self.roff) > 1:
            # Calculate coefficient of variation for Ron and Roff
            mean_ron = safe_mean(self.ron, default=1e10)
            mean_roff = safe_mean(self.roff, default=1e10)
            std_ron = safe_std(self.ron, default=0.0)
            std_roff = safe_std(self.roff, default=0.0)
            cv_ron = std_ron / (mean_ron + 1e-10)
            cv_roff = std_roff / (mean_roff + 1e-10)

            # Retention score (lower CV is better)
            self.retention_score = 1.0 / (1.0 + cv_ron + cv_roff)
        else:
            self.retention_score = 0.0

    def _calculate_endurance_score(self):
        """
        Calculate endurance score based on cycle-to-cycle consistency.

        Combines consistency of multiple parameters:
        - Hysteresis area consistency
        - On/Off ratio consistency
        - Ron/Roff consistency

        Score interpretation:
        - 1.0 = perfect endurance (no degradation)
        - 0.5 = moderate endurance
        - <0.3 = poor endurance
        """
        if len(self.normalized_areas) > 1:
            # Check consistency of key parameters across cycles
            metrics = {
                'area': self.normalized_areas,
                'on_off': self.on_off,
                'ron': self.ron,
                'roff': self.roff
            }

            consistency_scores = []
            for metric_name, values in metrics.items():
                mean_val = safe_mean(values, default=0.0)
                if len(values) > 1 and mean_val > 0:
                    std_val = safe_std(values, default=0.0)
                    cv = std_val / mean_val
                    consistency = 1.0 / (1.0 + cv)
                    consistency_scores.append(consistency)

            if consistency_scores:
                self.endurance_score = safe_mean(consistency_scores, default=0.0)
            else:
                self.endurance_score = 0.0
        else:
            self.endurance_score = 0.0

    def _calculate_switching_energy(self, voltage, current, v_on, v_off):
        """
        Calculate energy required for switching between states.

        Energy = ∫ V(t) * I(t) dt over switching region

        This represents the energy cost of changing device state.
        Lower energy is better for low-power applications.

        Returns:
        --------
        float : Energy in Joules
        """
        try:
            # Find indices corresponding to switching events
            on_idx = np.argmin(np.abs(voltage - v_on))
            off_idx = np.argmin(np.abs(voltage - v_off))

            # Ensure proper ordering
            if on_idx > off_idx:
                on_idx, off_idx = off_idx, on_idx

            # Integrate power over switching region
            if off_idx > on_idx + 1:
                v_switch = voltage[on_idx:off_idx + 1]
                i_switch = current[on_idx:off_idx + 1]
                power = v_switch * i_switch

                # Use trapezoidal integration
                # Assuming constant voltage sweep rate
                dt = 1.0  # Normalized time
                energy = np.trapezoid(np.abs(power), dx=dt)
                return energy
        except:
            pass
        return 0.0

    def plot_conduction_analysis(self, save_path=None):
        """Plot I-V data with fitted conduction models for mechanism identification."""
        if not hasattr(self, 'all_model_fits') or not self.all_model_fits:
            print("No conduction model fits available. Run full/research analysis level.")
            return

        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle(f'Conduction Mechanism Analysis - Best Fit: {self.conduction_mechanism}')

        # Get positive voltage data for plotting
        pos_mask = self.voltage > 0.1
        if not np.any(pos_mask):
            print("No positive voltage data for plotting")
            return

        v_pos = self.voltage[pos_mask]
        i_pos = self.current[pos_mask]

        # Plot 1: Linear scale with all models
        ax1 = axes[0, 0]
        ax1.plot(v_pos, i_pos * 1e6, 'ko', label='Data', markersize=4)

        # Plot fitted models
        v_fit = np.linspace(v_pos.min(), v_pos.max(), 100)
        colors = ['r', 'b', 'g', 'm', 'c', 'y']

        for idx, (model_name, model_data) in enumerate(self.all_model_fits.items()):
            if model_data['R2'] > 0.5:  # Only plot reasonable fits
                i_model = self._evaluate_model(model_name, v_fit, model_data['params'])
                ax1.plot(v_fit, i_model * 1e6, colors[idx % len(colors)],
                         label=f'{model_name} (R²={model_data["R2"]:.3f})', linewidth=2)

        ax1.set_xlabel('Voltage (V)')
        ax1.set_ylabel('Current (μA)')
        ax1.set_title('Linear Scale I-V with Model Fits')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Log-log plot (for power law detection)
        ax2 = axes[0, 1]
        ax2.loglog(v_pos, np.abs(i_pos), 'ko', markersize=4)
        ax2.set_xlabel('Voltage (V)')
        ax2.set_ylabel('|Current| (A)')
        ax2.set_title('Log-Log Plot (Power Law Detection)')
        ax2.grid(True, alpha=0.3)

        # Add slope indicators
        if self.all_model_fits['sclc']['R2'] > 0.7:
            # Add reference slopes
            v_ref = np.array([v_pos.min(), v_pos.max()])
            ax2.loglog(v_ref, 1e-8 * v_ref, 'r--', label='Slope = 1 (Ohmic)', alpha=0.5)
            ax2.loglog(v_ref, 1e-10 * v_ref ** 2, 'b--', label='Slope = 2 (SCLC)', alpha=0.5)
            if 'n' in self.all_model_fits['trap_sclc']['params']:
                n = self.all_model_fits['trap_sclc']['params']['n']
                ax2.loglog(v_ref, 1e-12 * v_ref ** n, 'g--',
                           label=f'Slope = {n:.1f} (Trap SCLC)', alpha=0.5)
            ax2.legend()

        # Plot 3: Schottky plot - ln(I) vs sqrt(V)
        ax3 = axes[0, 2]
        sqrt_v = np.sqrt(v_pos)
        ax3.semilogy(sqrt_v, np.abs(i_pos), 'ko', markersize=4)
        ax3.set_xlabel('√V (V^0.5)')
        ax3.set_ylabel('|Current| (A)')
        ax3.set_title('Schottky Plot: ln(I) vs √V')
        ax3.grid(True, alpha=0.3)

        # Plot 4: Poole-Frenkel plot - ln(I/V) vs sqrt(V)
        ax4 = axes[1, 0]
        ax4.semilogy(sqrt_v, np.abs(i_pos / v_pos), 'ko', markersize=4)
        ax4.set_xlabel('√V (V^0.5)')
        ax4.set_ylabel('|Current/Voltage| (A/V)')
        ax4.set_title('Poole-Frenkel Plot: ln(I/V) vs √V')
        ax4.grid(True, alpha=0.3)

        # Plot 5: Fowler-Nordheim plot - ln(I/V²) vs 1/V
        ax5 = axes[1, 1]
        inv_v = 1 / v_pos
        i_v2 = np.abs(i_pos) / v_pos ** 2
        valid_mask = i_v2 > 0
        if np.any(valid_mask):
            ax5.semilogy(inv_v[valid_mask], i_v2[valid_mask], 'ko', markersize=4)
            ax5.set_xlabel('1/V (V⁻¹)')
            ax5.set_ylabel('|Current/V²| (A/V²)')
            ax5.set_title('Fowler-Nordheim Plot: ln(I/V²) vs 1/V')
            ax5.grid(True, alpha=0.3)

        # Plot 6: Model comparison bar chart
        ax6 = axes[1, 2]
        models = list(self.all_model_fits.keys())
        r2_values = [self.all_model_fits[m]['R2'] for m in models]
        bars = ax6.bar(range(len(models)), r2_values)

        # Color best fit differently
        best_idx = models.index(self.conduction_mechanism)
        bars[best_idx].set_color('red')

        ax6.set_xticks(range(len(models)))
        ax6.set_xticklabels(models, rotation=45, ha='right')
        ax6.set_ylabel('R² Value')
        ax6.set_title('Model Fitting Quality')
        ax6.set_ylim([0, 1.1])
        ax6.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()

    def _evaluate_model(self, model_name, voltage, params):
        """Evaluate conduction model at given voltages."""
        if model_name == 'ohmic':
            return voltage / params.get('R', 1e6)
        elif model_name == 'sclc':
            return params.get('a', 0) * voltage ** 2
        elif model_name == 'trap_sclc':
            return params.get('a', 0) * voltage ** params.get('n', 2)
        elif model_name == 'poole_frenkel':
            return params.get('a', 0) * voltage * np.exp(params.get('beta', 0) * np.sqrt(voltage))
        elif model_name == 'schottky':
            return params.get('a', 0) * np.exp(params.get('beta', 0) * np.sqrt(voltage))
        elif model_name == 'fowler_nordheim':
            return params.get('a', 0) * voltage ** 2 * np.exp(-params.get('b', 1) / voltage)
        else:
            return np.zeros_like(voltage)

    def get_research_summary(self):
        """
        Generate comprehensive summary for research documentation.
        Includes all key metrics, classifications, and model fits.
        """
        # Build a robust compliance current line that never collapses the block
        comp_str = (
            f"- Compliance Current: {self.compliance_current * 1e6:.2f} μA"
            if (self.compliance_current is not None and self.compliance_current != 0)
            else "- Compliance Current: Not detected"
        )

        summary = f"""
=== DEVICE CHARACTERIZATION SUMMARY ===

Measurement Type: {self.measurement_type}
Number of Cycles: {self.num_loops}

DEVICE CLASSIFICATION:
- Type: {self.device_type}
- Confidence: {self.classification_confidence:.1%}
- Conduction Mechanism: {self.conduction_mechanism}
- Model R²: {self.model_parameters.get('R2', 0):.3f}

SWITCHING CHARACTERISTICS:
- Mean Ron: {safe_mean(self.ron, default=0.0):.2e} Ω (σ = {safe_std(self.ron, default=0.0):.2e})
- Mean Roff: {safe_mean(self.roff, default=0.0):.2e} Ω (σ = {safe_std(self.roff, default=0.0):.2e})
- Mean Switching Ratio: {safe_mean(self.switching_ratio, default=1.0):.1f}
- Mean Window Margin: {safe_mean(self.window_margin, default=0.0):.1f}

PERFORMANCE METRICS:
- Retention Score: {self.retention_score:.3f}
- Endurance Score: {self.endurance_score:.3f}
- Rectification Ratio: {np.mean(self.rectification_ratio):.2f}
- Nonlinearity Factor: {np.mean(self.nonlinearity_factor):.3f}
- Asymmetry Factor: {np.mean(self.asymmetry_factor):.3f}

POWER CHARACTERISTICS:
- Mean Power: {np.mean(self.power_consumption) * 1e6:.2f} μW
- Energy/Switch: {np.mean(self.energy_per_switch) * 1e12:.2f} pJ
{comp_str}
"""

        # Add model-specific parameters
        if self.conduction_mechanism and self.model_parameters.get('params'):
            summary += f"\n\nCONDUCTION MODEL PARAMETERS ({self.conduction_mechanism}):"
            for param, value in self.model_parameters['params'].items():
                summary += f"\n- {param}: {value:.3e}"

        # Add pulse measurement results if available
        if self.measurement_type == 'pulse' and self.set_times:
            summary += f"\n\nPULSE CHARACTERISTICS:"
            summary += f"\n- Mean Set Time: {np.mean(self.set_times) * 1e9:.1f} ns"
            summary += f"\n- Mean Reset Time: {np.mean(self.reset_times) * 1e9:.1f} ns"
            summary += f"\n- Mean Set Voltage: {np.mean(self.set_voltages):.2f} V"
            summary += f"\n- Mean Reset Voltage: {np.mean(self.reset_voltages):.2f} V"

        # Add endurance results if available
        if self.measurement_type == 'endurance' and self.state_degradation:
            summary += f"\n\nENDURANCE CHARACTERISTICS:"
            summary += f"\n- Ron Degradation: {self.state_degradation.get('ron_degradation', 0) * 100:.1f}%"
            summary += f"\n- Roff Degradation: {self.state_degradation.get('roff_degradation', 0) * 100:.1f}%"
            summary += f"\n- Window Degradation: {self.state_degradation.get('window_degradation', 0) * 100:.1f}%"
            if self.state_degradation.get('cycles_to_50_percent'):
                summary += f"\n- Projected 50% Lifetime: {self.state_degradation['cycles_to_50_percent']} cycles"

        return summary

    def get_resistance_at_voltage(self, target_voltage):
        try:
            idx = np.abs(self.voltage - target_voltage).argmin()
            if abs(self.voltage[idx] - target_voltage) < 0.01:
                result = zero_division_check(abs(self.voltage[idx]), abs(self.current[idx]))
                return result
            return None
        except Exception as e:
            print(f"Error calculating resistance at {target_voltage}V: {str(e)}")
            return None

    def export_metrics(self, filename):
        """Export calculated metrics to CSV file."""
        # Basic metrics dictionary
        metrics_dict = {
            'ps_areas': self.ps_areas,
            'ng_areas': self.ng_areas,
            'areas': self.areas,
            'normalized_areas': self.normalized_areas,
            'ron': self.ron,
            'roff': self.roff,
            'von': self.von,
            'voff': self.voff,
            'on_off': self.on_off,
            'r_02V': self.r_02V,
            'r_05V': self.r_05V
        }

        # Add new metrics to export
        if self.switching_ratio:
            metrics_dict['switching_ratio'] = self.switching_ratio
        if self.window_margin:
            metrics_dict['window_margin'] = self.window_margin
        if self.rectification_ratio:
            metrics_dict['rectification_ratio'] = self.rectification_ratio
        if self.nonlinearity_factor:
            metrics_dict['nonlinearity_factor'] = self.nonlinearity_factor
        if self.asymmetry_factor:
            metrics_dict['asymmetry_factor'] = self.asymmetry_factor
        if self.power_consumption:
            metrics_dict['power_consumption'] = self.power_consumption
        if self.energy_per_switch:
            metrics_dict['energy_per_switch'] = self.energy_per_switch

        # Add device classification and conduction model
        metrics_dict['device_type'] = [self.device_type] * len(self.ps_areas)
        metrics_dict['classification_confidence'] = [self.classification_confidence] * len(self.ps_areas)
        metrics_dict['conduction_mechanism'] = [self.conduction_mechanism] * len(self.ps_areas)

        # Add analysis_level for traceability
        metrics_dict['analysis_level'] = [self.analysis_level] * len(self.ps_areas)

        df = pd.DataFrame(metrics_dict)
        df.to_csv(filename, index=False)

    def get_summary_stats(self):
        """
        Return summary statistics of key metrics including means and standard deviations.

        Returns:
            dict: Dictionary containing mean and standard deviation for key metrics
        """
        summary = {
            # Resistance metrics
            'mean_ron': np.mean(self.ron),
            'std_ron': np.std(self.ron),
            'mean_roff': np.mean(self.roff),
            'std_roff': np.std(self.roff),

            # On/Off ratio metrics
            'mean_on_off_ratio': np.mean(self.on_off),
            'std_on_off_ratio': np.std(self.on_off),

            # Area metrics
            'total_area': np.sum(self.areas),
            'avg_normalized_area': np.mean(self.normalized_areas),
            'std_normalized_area': np.std(self.normalized_areas),

            # Resistance at specific voltages
            'mean_r_02V': np.mean([x for x in self.r_02V if x is not None]),
            'std_r_02V': np.std([x for x in self.r_02V if x is not None]),
            'mean_r_05V': np.mean([x for x in self.r_05V if x is not None]),
            'std_r_05V': np.std([x for x in self.r_05V if x is not None]),

            # General device metrics
            'num_loops': self.num_loops,
            'max_current': np.max(np.abs(self.current)),
            'max_voltage': np.max(np.abs(self.voltage)),

            # Coefficient of variation (CV = std/mean) for key metrics
            'cv_on_off_ratio': np.std(self.on_off) / np.mean(self.on_off) if np.mean(self.on_off) != 0 else None,
            'cv_normalized_area': np.std(self.normalized_areas) / np.mean(self.normalized_areas) if np.mean(
                self.normalized_areas) != 0 else None,
        }

        # Add new metrics to summary
        summary.update({
            'device_type': self.device_type,
            'classification_confidence': self.classification_confidence,
            'conduction_mechanism': self.conduction_mechanism,
            'analysis_level': self.analysis_level,
            'mean_switching_ratio': np.mean(self.switching_ratio) if self.switching_ratio else None,
            'mean_window_margin': np.mean(self.window_margin) if self.window_margin else None,
            'mean_rectification_ratio': np.mean(self.rectification_ratio) if self.rectification_ratio else None,
            'mean_nonlinearity': np.mean(self.nonlinearity_factor) if self.nonlinearity_factor else None,
            'mean_asymmetry': np.mean(self.asymmetry_factor) if self.asymmetry_factor else None,
            'mean_power_consumption': np.mean(self.power_consumption) if self.power_consumption else None,
            'retention_score': self.retention_score,
            'endurance_score': self.endurance_score,
            'compliance_current': self.compliance_current
        })

        return summary

    def calculate_metrics_for_loops(self, split_v_data, split_c_data):
        '''
        Calculate various metrics for each split array of voltage and current data.
        anything that needs completing on loops added in here

        Parameters:
        - split_v_data (list of lists): List containing split voltage arrays
        - split_c_data (list of lists): List containing split current arrays

        Returns:
        - ps_areas (list): List of PS areas for each split array
        - ng_areas (list): List of NG areas for each split array
        - areas (list): List of total areas for each split array
        - normalized_areas (list): List of normalized areas for each split array
        '''

        # Handle case where split_loops returns single arrays instead of list of arrays
        if isinstance(split_v_data, np.ndarray):
            split_v_data = [split_v_data]
            split_c_data = [split_c_data]

        # Loop through each split array
        for idx in range(len(split_v_data)):
            sub_v_array = split_v_data[idx]
            sub_c_array = split_c_data[idx]

            # Call the area_under_curves function for the current split arrays
            ps_area, ng_area, area, norm_area = self.area_under_curves(sub_v_array, sub_c_array)

            # Append the values to their respective lists
            self.ps_areas.append(ps_area)
            self.ng_areas.append(ng_area)
            self.areas.append(area)
            self.normalized_areas.append(norm_area)

            # caclulate the on and off volatge and resistance
            r_on, r_off, v_on, v_off = self.on_off_values(sub_v_array, sub_c_array)

            self.ron.append(float(r_on))
            self.roff.append(float(r_off))
            self.von.append(float(v_on))
            self.voff.append(float(v_off))
            self.on_off.append(float(r_off / r_on) if r_on > 0 else 0)  # Fixed: should be Roff/Ron

            # get resistance values at 0.2V (For conductivity)
            self.r_02V.append(self.get_resistance_at_voltage(0.2))
            self.r_05V.append(self.get_resistance_at_voltage(0.5))

    def area_under_curves(self, v_data, c_data):
        """
        only run this for an individual sweep
        :return: ps_area_enclosed,ng_area_enclosed,total_area_enclosed
        """

        def area_under_curve(voltage, current):
            """
            Calculate the area under the curve given voltage and current data.
            """
            voltage = np.array(voltage)
            current = np.array(current)
            # Calculate the area under the curve using the trapezoidal rule
            area = np.trapezoid(current, voltage)
            return area

        # finds v max and min
        v_max, v_min = self.bounds(v_data)

        # creates dataframe of the sweep in sections
        df_sections = self.split_data_in_sect(v_data, c_data, v_max, v_min)

        # calculate the area under the curve for each section
        sect1_area = abs(area_under_curve(df_sections.get('voltage_ps_sect1'), df_sections.get('current_ps_sect1')))
        sect2_area = abs(area_under_curve(df_sections.get('voltage_ps_sect2'), df_sections.get('current_ps_sect2')))
        sect3_area = abs(area_under_curve(df_sections.get('voltage_ng_sect1'), df_sections.get('current_ng_sect1')))
        sect4_area = abs(area_under_curve(df_sections.get('voltage_ng_sect2'), df_sections.get('current_ng_sect2')))

        ps_area_enclosed = abs(sect2_area) - abs(sect1_area)
        ng_area_enclosed = abs(sect3_area) - abs(sect4_area)
        area_enclosed = ps_area_enclosed + ng_area_enclosed
        norm_area_enclosed = area_enclosed / (abs(v_max) + abs(v_min))

        # added nan check as causes issues later if not a value
        if math.isnan(norm_area_enclosed):
            norm_area_enclosed = 0
        if math.isnan(ps_area_enclosed):
            ps_area_enclosed = 0
        if math.isnan(ng_area_enclosed):
            ng_area_enclosed = 0
        if math.isnan(area_enclosed):
            area_enclosed = 0

        return ps_area_enclosed, ng_area_enclosed, area_enclosed, norm_area_enclosed

    def on_off_values(self, voltage_data, current_data):
        """
        Calculates r on off and v on off values for an individual device
        """
        # Initialize default values
        resistance_on_value = 0
        resistance_off_value = 0
        voltage_on_value = 0
        voltage_off_value = 0

        # Convert to numpy arrays if needed
        voltage_data = np.array(voltage_data)
        current_data = np.array(current_data)

        # Get the maximum voltage value
        max_voltage = round(max(voltage_data), 1) if len(voltage_data) > 0 else 0

        # Catch edge case for just negative sweep only
        if max_voltage == 0:
            max_voltage = abs(round(min(voltage_data), 1)) if len(voltage_data) > 0 else 0

        if max_voltage == 0:
            return 0, 0, 0, 0

        # Set the threshold value to 0.2 times the maximum voltage
        threshold = round(0.2 * max_voltage, 2)

        # Filter the voltage and current data to include values within the threshold
        filtered_voltage = []
        filtered_current = []
        for index in range(len(voltage_data)):
            if -threshold < voltage_data[index] < threshold:
                filtered_voltage.append(voltage_data[index])
                filtered_current.append(current_data[index])

        resistance_magnitudes = []
        for idx in range(len(filtered_voltage)):
            if filtered_voltage[idx] != 0 and filtered_current[idx] != 0:
                resistance_magnitudes.append(abs(filtered_voltage[idx] / filtered_current[idx]))

        if not resistance_magnitudes:
            # Handle the case when the list is empty
            print("Warning: No valid resistance values found.")
            return 0, 0, 0, 0

        # Store the minimum and maximum resistance values (Ron is lower, Roff is higher)
        resistance_on_value = min(resistance_magnitudes)
        resistance_off_value = max(resistance_magnitudes)

        # Calculate the gradients for each data point
        gradients = []
        for idx in range(len(voltage_data) - 1):
            if voltage_data[idx + 1] - voltage_data[idx] != 0:
                gradients.append(
                    (current_data[idx + 1] - current_data[idx]) / (voltage_data[idx + 1] - voltage_data[idx]))

        if gradients:
            # Find the maximum and minimum gradient values
            half_point = int(len(gradients) / 2)
            if half_point > 0:
                max_gradient = max(gradients[:half_point])
                min_gradient = min(gradients)

                # Use the maximum and minimum gradient values to determine the on and off voltages
                for idx in range(len(gradients)):
                    if gradients[idx] == max_gradient:
                        voltage_off_value = voltage_data[idx]
                    if gradients[idx] == min_gradient:
                        voltage_on_value = voltage_data[idx]

        # Return the calculated Ron and Roff values and on and off voltages
        return resistance_on_value, resistance_off_value, voltage_on_value, voltage_off_value

    def detect_and_split_loops(self, v_data, c_data):
        """
        Detect number of loops and split data accordingly.
        A loop is defined as a complete voltage sweep cycle (e.g., 0→Vmax→0→Vmin→0)
        """
        if len(v_data) < 4:  # Too few points to form a loop
            return 1, [v_data], [c_data]

        # Method 1: Detect zero crossings and turning points
        loops_info = self._detect_loops_by_pattern(v_data)

        # Method 2: If pattern detection fails, use turning points
        if not loops_info['valid']:
            loops_info = self._detect_loops_by_turning_points(v_data)

        # Split the data based on detected loop boundaries
        split_v, split_c = self._split_by_boundaries(v_data, c_data, loops_info['boundaries'])

        return loops_info['num_loops'], split_v, split_c

    def _detect_loops_by_pattern(self, v_data):
        """
        Detect loops by looking for complete voltage sweep patterns.
        A typical pattern might be: 0 → +V → 0 → -V → 0
        """
        v_array = np.array(v_data)

        # Find zero crossings
        zero_crossings = []
        for i in range(1, len(v_array)):
            if (v_array[i - 1] * v_array[i] < 0) or (abs(v_array[i]) < 1e-9 and abs(v_array[i - 1]) > 1e-9):
                zero_crossings.append(i)

        # Find turning points (where derivative changes sign)
        turning_points = []
        if len(v_array) > 2:
            dv = np.diff(v_array)
            for i in range(1, len(dv)):
                if dv[i - 1] * dv[i] < 0:  # Sign change in derivative
                    turning_points.append(i)

        # Detect loop pattern
        # For a standard bipolar sweep: start → +max → 0 → -max → 0 (end)
        # This gives us 2 turning points and 2-3 zero crossings per loop

        # Estimate number of loops
        if len(turning_points) >= 2:
            # Each complete loop typically has 2 major turning points
            estimated_loops = max(1, len(turning_points) // 2)
        else:
            estimated_loops = 1

        # Find loop boundaries
        boundaries = [0]  # Start of first loop

        # Method: Look for return to near-zero voltage after excursions
        near_zero_indices = np.where(np.abs(v_array) < 0.01 * np.max(np.abs(v_array)))[0]

        if len(near_zero_indices) > 2:
            # Group nearby zero crossings
            groups = []
            current_group = [near_zero_indices[0]]

            for idx in near_zero_indices[1:]:
                if idx - current_group[-1] < 10:  # Within 10 points
                    current_group.append(idx)
                else:
                    groups.append(int(np.mean(current_group)))
                    current_group = [idx]
            groups.append(int(np.mean(current_group)))

            # Use groups as potential boundaries
            for g in groups[1:-1]:  # Exclude first and last
                boundaries.append(g)

        boundaries.append(len(v_array))  # End of last loop

        # Validate boundaries
        if len(boundaries) - 1 != estimated_loops:
            return {'valid': False, 'num_loops': 1, 'boundaries': [0, len(v_array)]}

        return {
            'valid': True,
            'num_loops': len(boundaries) - 1,
            'boundaries': boundaries
        }

    def _detect_loops_by_turning_points(self, v_data):
        """
        Fallback method: detect loops by major turning points in voltage.
        """
        v_array = np.array(v_data)

        # Smooth the data to reduce noise
        if len(v_array) > 10:
            from scipy.ndimage import uniform_filter1d
            v_smooth = uniform_filter1d(v_array, size=5, mode='nearest')
        else:
            v_smooth = v_array

        # Find all local maxima and minima
        peaks = []
        valleys = []

        for i in range(1, len(v_smooth) - 1):
            if v_smooth[i] > v_smooth[i - 1] and v_smooth[i] > v_smooth[i + 1]:
                peaks.append(i)
            elif v_smooth[i] < v_smooth[i - 1] and v_smooth[i] < v_smooth[i + 1]:
                valleys.append(i)

        # Combine and sort turning points
        turning_points = sorted(peaks + valleys)

        # Estimate loops based on turning points
        if len(turning_points) >= 4:
            # For bipolar sweep: +peak, -valley, +peak, -valley = 1 loop
            estimated_loops = max(1, len(turning_points) // 4)
        else:
            estimated_loops = 1

        # Create evenly spaced boundaries
        boundaries = []
        points_per_loop = len(v_array) // estimated_loops

        for i in range(estimated_loops + 1):
            boundaries.append(min(i * points_per_loop, len(v_array)))

        return {
            'valid': True,
            'num_loops': estimated_loops,
            'boundaries': boundaries
        }

    def _split_by_boundaries(self, v_data, c_data, boundaries):
        """
        Split data according to detected boundaries.
        """
        split_v = []
        split_c = []

        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]

            if end > start:  # Ensure valid range
                split_v.append(v_data[start:end])
                split_c.append(c_data[start:end])

        # If no valid splits, return original data as single loop
        if not split_v:
            split_v = [v_data]
            split_c = [c_data]

        return split_v, split_c

    def check_for_loops_advanced(self, v_data):
        """
        Advanced loop detection that handles various sweep patterns.
        Returns the number of complete loops in the data.
        """
        if len(v_data) < 4:
            return 1

        v_array = np.array(v_data)

        # Method 1: Detect by counting complete cycles through zero
        zero_crossings = 0
        for i in range(1, len(v_array)):
            if v_array[i - 1] * v_array[i] < 0:  # Sign change
                zero_crossings += 1

        # Method 2: Detect by voltage range repetitions
        v_max = np.max(v_array)
        v_min = np.min(v_array)
        v_range = v_max - v_min

        # Count how many times we hit near max/min values
        near_max_count = np.sum(np.abs(v_array - v_max) < 0.1 * v_range)
        near_min_count = np.sum(np.abs(v_array - v_min) < 0.1 * v_range)

        # Method 3: Detect by finding repeating patterns
        pattern_loops = self._detect_pattern_repetitions(v_array)

        # Combine methods to estimate loops
        if zero_crossings >= 4:
            # Bipolar sweep: typically 4 zero crossings per loop
            loops_by_zeros = zero_crossings // 4
        else:
            loops_by_zeros = 1

        if near_max_count >= 2 and near_min_count >= 2:
            # Each loop should visit max and min at least once
            loops_by_extrema = min(near_max_count, near_min_count) // 2
        else:
            loops_by_extrema = 1

        # Use the most reliable estimate
        estimated_loops = max(loops_by_zeros, loops_by_extrema, pattern_loops)

        return max(1, estimated_loops)  # At least 1 loop

    def _detect_pattern_repetitions(self, v_array):
        """
        Detect if the voltage pattern repeats.
        """
        n = len(v_array)

        # Try different pattern lengths
        for pattern_length in range(n // 4, n // 2):
            if n % pattern_length == 0:
                num_repetitions = n // pattern_length

                # Check if pattern repeats
                is_repeating = True
                for i in range(pattern_length):
                    for j in range(1, num_repetitions):
                        if abs(v_array[i] - v_array[i + j * pattern_length]) > 0.01:
                            is_repeating = False
                            break
                    if not is_repeating:
                        break

                if is_repeating:
                    return num_repetitions

        return 1

    # Updated method to use in your class
    def process_loops(self):
        """
        Main method to detect and split loops.
        """
        # Detect loops and split data
        self.num_loops, self.split_v_data, self.split_c_data = self.detect_and_split_loops(
            self.voltage, self.current
        )

        # Validate splits
        if len(self.split_v_data) != self.num_loops:
            print(f"Warning: Expected {self.num_loops} loops but got {len(self.split_v_data)} splits")
            self.num_loops = len(self.split_v_data)

        # Ensure each split has enough data points
        valid_splits_v = []
        valid_splits_c = []

        for v_split, c_split in zip(self.split_v_data, self.split_c_data):
            if len(v_split) >= 10:  # Minimum points for meaningful analysis
                valid_splits_v.append(v_split)
                valid_splits_c.append(c_split)
            else:
                print(f"Warning: Dropping split with only {len(v_split)} points")

        if valid_splits_v:
            self.split_v_data = valid_splits_v
            self.split_c_data = valid_splits_c
            self.num_loops = len(valid_splits_v)
        else:
            # If no valid splits, keep original data as single loop
            self.split_v_data = [self.voltage]
            self.split_c_data = [self.current]
            self.num_loops = 1

    def check_for_loops(self, v_data):
        """
        :param v_data:
        :return: number of loops for given data set
        """
        # looks at max voltage and min voltage if they are seen more than twice it classes it as a loop
        # checks for the number of zeros 3 = single loop
        num_max = 0
        num_min = 0
        num_zero = 0
        max_v, min_v = self.bounds(v_data)
        max_v_2 = max_v / 2
        min_v_2 = min_v / 2

        # 4 per sweep
        for value in v_data:
            if abs(value - max_v_2) < 1e-6:
                num_max += 1
            if abs(value - min_v_2) < 1e-6:
                num_min += 1
            if abs(value) < 1e-6:
                num_zero += 1

        if num_max + num_min == 4:
            return 1
        if num_max + num_min == 2:
            return 0.5
        else:
            loops = (num_max + num_min) / 4
            return max(loops, 1)  # Ensure at least 1 loop

    def split_loops(self, v_data, c_data):
        """ splits the looped data and outputs each sweep as another array coppied from data"""

        if self.num_loops == 1:
            return v_data, c_data

        total_length = len(v_data)  # Assuming both v_data and c_data have the same length
        size = int(total_length / self.num_loops)  # Calculate the size based on the number of loops

        # Handle the case when the division leaves the remainder
        if total_length % self.num_loops != 0:
            size += 1

        split_v_data = [v_data[i:i + size] for i in range(0, total_length, size)]
        split_c_data = [c_data[i:i + size] for i in range(0, total_length, size)]
        #print(split_v_data,split_c_data)
        return split_v_data, split_c_data

    def bounds(self, data):
        """
        :param data:
        :return: max and min values of given array max,min
        """
        return np.max(data), np.min(data)

    def split_data_in_sect(self, voltage, current, v_max, v_min):
        # splits the data into sections and calculates the area under the curve for how "memristive" a device is.
        zipped_data = list(zip(voltage, current))

        positive = [(v, c) for v, c in zipped_data if 0 <= v <= v_max]
        negative = [(v, c) for v, c in zipped_data if v_min <= v <= 0]

        # Find the maximum length among the sections
        max_len = max(len(positive), len(negative))

        # Split positive section into two equal parts
        positive1 = positive[:max_len // 2]
        positive2 = positive[max_len // 2:]

        # Split negative section into two equal parts
        negative3 = negative[:max_len // 2]
        negative4 = negative[max_len // 2:]

        # Find the maximum length among the four sections
        max_len = max(len(positive1), len(positive2), len(negative3), len(negative4))

        # Calculate the required padding for each section
        pad_positive1 = max_len - len(positive1)
        pad_positive2 = max_len - len(positive2)
        pad_negative3 = max_len - len(negative3)
        pad_negative4 = max_len - len(negative4)

        # Limit the padding to the length of the last value for each section
        last_positive1 = positive1[-1] if positive1 else (0, 0)
        last_positive2 = positive2[-1] if positive2 else (0, 0)
        last_negative3 = negative3[-1] if negative3 else (0, 0)
        last_negative4 = negative4[-1] if negative4 else (0, 0)

        positive1 += [last_positive1] * pad_positive1
        positive2 += [last_positive2] * pad_positive2
        negative3 += [last_negative3] * pad_negative3
        negative4 += [last_negative4] * pad_negative4

        # Create DataFrame for device
        sections = {
            'voltage_ps_sect1': [v for v, _ in positive1],
            'current_ps_sect1': [c for _, c in positive1],
            'voltage_ps_sect2': [v for v, _ in positive2],
            'current_ps_sect2': [c for _, c in positive2],
            'voltage_ng_sect1': [v for v, _ in negative3],
            'current_ng_sect1': [c for _, c in negative3],
            'voltage_ng_sect2': [v for v, _ in negative4],
            'current_ng_sect2': [c for _, c in negative4],
        }

        df_sections = pd.DataFrame(sections)
        return df_sections

    # Additional helper methods from the enhanced version

    def _extract_classification_features(self):
        """Extract features for device classification."""
        features = {}

        # Detect compliance early for downstream logic
        if self.compliance_current is None:
            self.compliance_current = self._detect_compliance_current()

        # Check for hysteresis with robust estimator
        features['has_hysteresis'] = self._estimate_hysteresis_present()

        # Check for pinched hysteresis (memristive fingerprint)
        features['pinched_hysteresis'] = self._check_pinched_hysteresis()

        # Check for switching behavior
        if self.on_off:
            features['switching_behavior'] = any(ratio > 2 for ratio in self.on_off if ratio > 0)
        else:
            features['switching_behavior'] = False

        # Check I-V linearity (robust to compliance region)
        features['linear_iv'], features['nonlinear_iv'] = self._check_linearity()

        # Check for ohmic behavior at low voltages
        features['ohmic_behavior'] = self._check_ohmic_behavior()

        # Check polarity dependence
        features['polarity_dependent'] = self._check_polarity_dependence()

        # Calculate phase shift (for capacitive detection)
        features['phase_shift'] = self._calculate_phase_shift()

        # Check for elliptical hysteresis pattern
        features['elliptical_hysteresis'] = self._check_elliptical_pattern()

        return features

    def _estimate_hysteresis_present(self):
        """Robust check for hysteresis presence using normalized loop areas."""
        if not self.normalized_areas:
            return False
        areas = np.abs(np.asarray(self.normalized_areas))
        if areas.size == 0:
            return False
        # Adaptive threshold: accept small areas while guarding noise
        # Base threshold tuned low to avoid false negatives
        base_threshold = 1e-3
        median_area = float(np.median(areas))
        return median_area > base_threshold

    def _check_pinched_hysteresis(self):
        """
        Check if the I-V curve shows pinched hysteresis at origin.
        Requires the loop to be 'closed' at V=0 (current -> 0).
        """
        # Find currents strictly near zero voltage
        v_abs_max = max(abs(self.voltage.max()), abs(self.voltage.min()))
        threshold_v = 0.02 * v_abs_max  # Tightened to 2% of voltage range
        
        near_zero_mask = np.abs(self.voltage) < threshold_v

        if np.any(near_zero_mask):
            currents_near_zero = self.current[near_zero_mask]
            
            # Robust max current (95th percentile to ignore spikes)
            if len(self.current) > 0:
                max_current = np.percentile(np.abs(self.current), 99)
            else:
                max_current = 0
            
            if max_current > 1e-12: # Avoid division by zero
                # Calculate the "gap" at zero (mean absolute current at V~0)
                mean_zero_current = np.mean(np.abs(currents_near_zero))
                
                # Ratio of (Current at Zero) / (Max Current)
                # For a Memristor, this should be ~0.
                # For a Capacitor, this is I_cap / I_total, which is significant.
                zero_ratio = mean_zero_current / max_current
                
                # Strict threshold: Must be less than 5% of max current to be considered "pinched"
                return zero_ratio < 0.05
                
        return False

    def _check_linearity(self):
        """Check if I-V relationship is linear."""
        if len(self.voltage) < 3:
            return False, True

        # Remove any NaN or inf values
        valid_mask = np.isfinite(self.voltage) & np.isfinite(self.current)
        if not np.any(valid_mask):
            return False, True

        v_clean = self.voltage[valid_mask]
        i_clean = self.current[valid_mask]

        # Exclude probable compliance-limited region (flat current at high |V|)
        try:
            high_v_mask = np.abs(v_clean) > 0.8 * np.max(np.abs(v_clean))
            if np.sum(high_v_mask) > 5:
                high_curr = i_clean[high_v_mask]
                if np.mean(np.abs(high_curr)) > 0:
                    flat = np.std(high_curr) / (np.mean(np.abs(high_curr)) + 1e-18) < 0.05
                    if flat:
                        v_clean = v_clean[~high_v_mask]
                        i_clean = i_clean[~high_v_mask]
        except Exception:
            pass

        # Perform linear regression
        try:
            coeffs = np.polyfit(v_clean, i_clean, 1)
            poly = np.poly1d(coeffs)
            y_pred = poly(v_clean)

            # Calculate R-squared
            ss_res = np.sum((i_clean - y_pred) ** 2)
            ss_tot = np.sum((i_clean - np.mean(i_clean)) ** 2)
            r_squared = 1 - (ss_res / (ss_tot + 1e-10))

            is_linear = r_squared > 0.95
            return is_linear, not is_linear
        except:
            return False, True

    def _check_ohmic_behavior(self):
        """Check for ohmic behavior at low voltages."""
        # Check linearity at low voltages (< 0.1V)
        low_v_mask = np.abs(self.voltage) < 0.1
        if np.sum(low_v_mask) < 5:
            return False

        low_v = self.voltage[low_v_mask]
        low_i = self.current[low_v_mask]

        # Check if passes through origin
        origin_test = np.abs(np.mean(low_i[np.abs(low_v) < 0.01])) < 1e-9 if np.any(np.abs(low_v) < 0.01) else True

        # Check linearity in low voltage region
        try:
            coeffs = np.polyfit(low_v, low_i, 1)
            poly = np.poly1d(coeffs)
            y_pred = poly(low_v)

            ss_res = np.sum((low_i - y_pred) ** 2)
            ss_tot = np.sum((low_i - np.mean(low_i)) ** 2)
            r_squared = 1 - (ss_res / (ss_tot + 1e-10))

            return r_squared > 0.9 and origin_test
        except:
            return False

    def _check_polarity_dependence(self):
        """Check if device shows different behavior for positive and negative voltages."""
        pos_mask = self.voltage > 0.1
        neg_mask = self.voltage < -0.1

        if np.any(pos_mask) and np.any(neg_mask):
            # Calculate average conductance for positive and negative regions
            pos_conductance = np.mean(np.abs(self.current[pos_mask] / self.voltage[pos_mask]))
            neg_conductance = np.mean(np.abs(self.current[neg_mask] / self.voltage[neg_mask]))

            # Check for significant difference
            avg_conductance = (pos_conductance + neg_conductance) / 2
            if avg_conductance > 0:
                return abs(pos_conductance - neg_conductance) / avg_conductance > 0.2
        return False

    def _calculate_phase_shift(self):
        """Calculate phase shift between voltage and current (for capacitive detection)."""
        if len(self.voltage) < 10:
            return 0

        try:
            # For a single sweep, analyze the phase relationship
            # Normalize signals
            v_norm = (self.voltage - np.mean(self.voltage)) / (np.std(self.voltage) + 1e-10)
            i_norm = (self.current - np.mean(self.current)) / (np.std(self.current) + 1e-10)

            # Use Hilbert transform to calculate instantaneous phase
            analytic_v = signal.hilbert(v_norm)
            analytic_i = signal.hilbert(i_norm)

            phase_v = np.unwrap(np.angle(analytic_v))
            phase_i = np.unwrap(np.angle(analytic_i))

            # Calculate average phase difference
            phase_diff = np.mean(np.abs(phase_v - phase_i))

            # Convert to degrees
            phase_shift_deg = np.degrees(phase_diff) % 180

            return phase_shift_deg
        except:
            return 0

    def _check_elliptical_pattern(self):
        """Check if the I-V curve forms an elliptical pattern (capacitive characteristic)."""
        if len(self.split_v_data) == 0:
            return False

        try:
            # Use the first complete loop
            v_loop = np.array(self.split_v_data[0])
            i_loop = np.array(self.split_c_data[0])

            if len(v_loop) < 10:
                return False

            # Calculate the centroid
            v_center = np.mean(v_loop)
            i_center = np.mean(i_loop)

            # Shift to center
            v_shifted = v_loop - v_center
            i_shifted = i_loop - i_center

            # Calculate covariance matrix
            cov_matrix = np.cov(v_shifted, i_shifted)

            # Get eigenvalues
            eigenvalues = np.linalg.eigvals(cov_matrix)

            # Check if both eigenvalues are positive and similar (elliptical)
            if min(eigenvalues) > 0:
                eccentricity = 1 - min(eigenvalues) / max(eigenvalues)
                # Elliptical if eccentricity is moderate (not too circular, not too linear)
                return 0.3 < eccentricity < 0.8

        except:
            pass

        return False

    def _calculate_rectification_ratio(self, voltage, current):
        """
        Calculate rectification ratio I(+V)/I(-V).

        This metric indicates diode-like behavior:
        - Ratio ~1: Symmetric device
        - Ratio >10: Strong rectification (diode-like)
        - Ratio <0.1: Reverse rectification
        """
        # Use voltages at ±0.5V or ±half of max voltage
        v_ref = min(0.5, 0.5 * np.max(np.abs(voltage)))

        # Find currents at positive and negative reference voltages
        pos_idx = np.argmin(np.abs(voltage - v_ref))
        neg_idx = np.argmin(np.abs(voltage + v_ref))
        # print("voltage" ,voltage)
        # print("index ",pos_idx,neg_idx)
        i_pos = abs(current[pos_idx])
        i_neg = abs(current[neg_idx])

        if i_neg > 1e-12:
            return i_pos / i_neg
        else:
            return 1.0

    def _calculate_nonlinearity(self, voltage, current):
        """
        Calculate degree of I-V nonlinearity.

        Compares linear fit vs polynomial fit:
        - 0 = perfectly linear (ideal resistor)
        - 1 = highly nonlinear (typical memristor)

        Higher values indicate stronger memristive behavior.
        """
        if len(voltage) < 4:
            return 0.0

        try:
            # Remove zero voltage point to avoid singularity
            non_zero_mask = np.abs(voltage) > 1e-6
            v_nz = voltage[non_zero_mask]
            i_nz = current[non_zero_mask]

            if len(v_nz) < 4:
                return 0.0

            # Fit linear model
            coeffs_1 = np.polyfit(v_nz, i_nz, 1)
            linear_fit = np.poly1d(coeffs_1)
            linear_pred = linear_fit(v_nz)

            # Fit polynomial model (3rd order)
            coeffs_3 = np.polyfit(v_nz, i_nz, min(3, len(v_nz) - 1))
            poly_fit = np.poly1d(coeffs_3)
            poly_pred = poly_fit(v_nz)

            # Calculate nonlinearity as improvement of polynomial over linear fit
            linear_error = np.sum((i_nz - linear_pred) ** 2)
            poly_error = np.sum((i_nz - poly_pred) ** 2)

            if linear_error > 0:
                nonlinearity = 1 - (poly_error / linear_error)
                return max(0, min(1, nonlinearity))
            else:
                return 0.0
        except:
            return 0.0

    def _calculate_asymmetry(self, voltage, current):
        """
        Calculate device asymmetry between positive and negative sweeps.

        Asymmetry = |I(+V) - I(-V)| / (I(+V) + I(-V))

        Values:
        - 0 = perfectly symmetric
        - 1 = completely asymmetric

        Important for neuromorphic applications where symmetric updates are desired.
        """
        # Separate positive and negative branches
        pos_mask = voltage > 0.1 * np.max(voltage)
        neg_mask = voltage < 0.1 * np.min(voltage)

        if np.any(pos_mask) and np.any(neg_mask):
            # Calculate average absolute current in each branch
            avg_pos = np.mean(np.abs(current[pos_mask]))
            avg_neg = np.mean(np.abs(current[neg_mask]))

            # Asymmetry factor
            if avg_pos + avg_neg > 0:
                asymmetry = abs(avg_pos - avg_neg) / (avg_pos + avg_neg)
                return asymmetry
        return 0.0

    def _detect_compliance_current(self):
        """
        Detect current compliance if present.

        Current compliance is a safety limit that prevents device damage.
        Detected by looking for current saturation at high voltages.

        Returns current value where saturation occurs, or None if not detected.
        """
        # Look for current saturation
        max_current = np.max(np.abs(self.current))

        # Check if current plateaus at high voltages
        high_v_mask = np.abs(self.voltage) > 0.8 * np.max(np.abs(self.voltage))

        if np.sum(high_v_mask) > 5:
            high_v_currents = self.current[high_v_mask]

            # Check if currents are relatively constant (within 5%)
            current_std = np.std(high_v_currents)
            current_mean = np.mean(np.abs(high_v_currents))

            if current_mean > 0 and current_std / current_mean < 0.05:
                return current_mean

        return None

    def plot_device_analysis(self, save_path=None):
        """Generate comprehensive plots for device analysis."""
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle(
            f'Device Analysis - Type: {self.device_type} (Confidence: {self.classification_confidence:.2f})')

        # Plot 1: I-V characteristics
        ax1 = axes[0, 0]
        ax1.plot(self.voltage, self.current * 1e6, 'b-', linewidth=2)
        ax1.set_xlabel('Voltage (V)')
        ax1.set_ylabel('Current (μA)')
        ax1.set_title('I-V Characteristics')
        ax1.grid(True, alpha=0.3)

        # Add annotations for key voltages
        if self.von and self.voff:
            ax1.axvline(x=np.mean(self.von), color='g', linestyle='--', alpha=0.5,
                        label=f'Von={np.mean(self.von):.2f}V')
            ax1.axvline(x=np.mean(self.voff), color='r', linestyle='--', alpha=0.5,
                        label=f'Voff={np.mean(self.voff):.2f}V')
            ax1.legend()

        # Plot 2: Resistance vs Voltage
        ax2 = axes[0, 1]
        resistance = np.abs(self.voltage / (self.current + 1e-12))
        ax2.semilogy(self.voltage, resistance, 'r-', linewidth=2)
        ax2.set_xlabel('Voltage (V)')
        ax2.set_ylabel('Resistance (Ω)')
        ax2.set_title('Resistance vs Voltage')
        ax2.grid(True, alpha=0.3)

        # Plot 3: Hysteresis loops overlay (with sweep direction arrows placed outside the loop)
        ax3 = axes[0, 2]
        for i in range(min(5, len(self.split_v_data))):
            vcyc = np.asarray(self.split_v_data[i])
            icyc = np.asarray(self.split_c_data[i]) * 1e6
            ax3.plot(vcyc, icyc, label=f'Cycle {i + 1}', alpha=0.7)

            # Add direction arrows along the path, outside of the loop envelope
            try:
                if len(vcyc) > 10:
                    # Downsample indices for arrows
                    num_arrows = 6
                    idxs = np.linspace(1, len(vcyc) - 2, num_arrows).astype(int)

                    # Compute local tangents
                    dv = np.gradient(vcyc)
                    di = np.gradient(icyc)

                    # Offset direction perpendicular to the tangent to place arrows outside
                    for j, k in enumerate(idxs):
                        # Tangent vector (dv, di), normal vector (-di, dv)
                        t_v, t_i = dv[k], di[k]
                        n_v, n_i = -t_i, t_v
                        norm = np.hypot(n_v, n_i) + 1e-12
                        n_v /= norm
                        n_i /= norm

                        # Scale offset based on data range
                        off_scale_v = 0.02 * (np.max(vcyc) - np.min(vcyc) + 1e-12)
                        off_scale_i = 0.05 * (np.max(icyc) - np.min(icyc) + 1e-12)

                        # Determine outward side by comparing to loop centroid
                        vc, ic = np.mean(vcyc), np.mean(icyc)
                        dir_sign = np.sign((vcyc[k] - vc) * n_v + (icyc[k] - ic) * n_i)
                        n_v *= dir_sign
                        n_i *= dir_sign

                        # Arrow base point offset outside
                        x0 = vcyc[k] + n_v * off_scale_v
                        y0 = icyc[k] + n_i * off_scale_i

                        # Arrow direction along path
                        dx = t_v
                        dy = t_i

                        ax3.annotate('',
                                      xy=(x0 + dx * 0.02, y0 + dy * 0.02),
                                      xytext=(x0, y0),
                                      arrowprops=dict(arrowstyle='->', color='gray', lw=1, alpha=0.8))
            except Exception:
                pass
        ax3.set_xlabel('Voltage (V)')
        ax3.set_ylabel('Current (μA)')
        ax3.set_title('Cycle Overlay')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Plot 4: Metrics evolution
        ax4 = axes[1, 0]
        if len(self.switching_ratio) > 1:
            cycles = range(1, len(self.switching_ratio) + 1)
            ax4.plot(cycles, self.switching_ratio, 'go-', label='Switching Ratio')
            ax4.set_xlabel('Cycle')
            ax4.set_ylabel('Roff/Ron')
            ax4.set_title('Switching Ratio Evolution')
            ax4.grid(True, alpha=0.3)

            # Add trend line
            z = np.polyfit(cycles, self.switching_ratio, 1)
            p = np.poly1d(z)
            ax4.plot(cycles, p(cycles), "r--", alpha=0.5, label='Trend')
            ax4.legend()

        # Plot 5: Classification scores
        ax5 = axes[1, 1]
        if hasattr(self, 'classification_features'):
            features = ['Hysteresis', 'Pinched', 'Switching', 'Linear', 'Ohmic']
            values = [
                float(self.classification_features.get('has_hysteresis', 0)),
                float(self.classification_features.get('pinched_hysteresis', 0)),
                float(self.classification_features.get('switching_behavior', 0)),
                float(self.classification_features.get('linear_iv', 0)),
                float(self.classification_features.get('ohmic_behavior', 0))
            ]
            bars = ax5.bar(features, values)
            ax5.set_title('Device Characteristics')
            ax5.set_ylim([0, 1.2])
            ax5.set_ylabel('Present (1) / Absent (0)')

            # Color code bars
            for i, bar in enumerate(bars):
                if values[i] > 0.5:
                    bar.set_color('green')
                else:
                    bar.set_color('red')

        # Plot 6: Performance metrics radar chart
        ax6 = axes[1, 2]
        categories = ['Retention', 'Endurance', 'Nonlinearity',
                      'Window\nMargin', 'Power\nEfficiency']

        # Normalize metrics to 0-1 scale
        values = [
            self.retention_score,
            self.endurance_score,
            np.mean(self.nonlinearity_factor) if self.nonlinearity_factor else 0,
            min(np.mean(self.window_margin) / 10, 1) if self.window_margin else 0,  # Normalize to 10x
            1 - min(np.mean(self.power_consumption) / 1e-3, 1) if self.power_consumption else 0  # Normalize to 1mW
        ]

        # Create radar chart
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False)
        values = values + values[:1]  # Complete the circle
        angles = np.concatenate([angles, [angles[0]]])

        ax6.plot(angles, values, 'o-', linewidth=2)
        ax6.fill(angles, values, alpha=0.25)
        ax6.set_xticks(angles[:-1])
        ax6.set_xticklabels(categories)
        ax6.set_ylim(0, 1)
        ax6.set_title('Performance Metrics')
        ax6.grid(True)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()


    def get_memristor_performance_metrics(self):
        """
        Get comprehensive performance metrics for memristor evaluation.
        Returns a dictionary with all relevant metrics.
        """
        metrics = {
            'device_type': self.device_type,
            'classification_confidence': self.classification_confidence,
            'conduction_mechanism': self.conduction_mechanism,
            'switching_ratio_mean': np.mean(self.switching_ratio) if self.switching_ratio else 0,
            'window_margin_mean': np.mean(self.window_margin) if self.window_margin else 0,
            'rectification_ratio_mean': np.mean(self.rectification_ratio) if self.rectification_ratio else 1,
            'nonlinearity_mean': np.mean(self.nonlinearity_factor) if self.nonlinearity_factor else 0,
            'asymmetry_mean': np.mean(self.asymmetry_factor) if self.asymmetry_factor else 0,
            'power_consumption_mean': np.mean(self.power_consumption) if self.power_consumption else 0,
            'energy_per_switch_mean': np.mean(self.energy_per_switch) if self.energy_per_switch else 0,
            'retention_score': self.retention_score,
            'endurance_score': self.endurance_score,
            'compliance_current': self.compliance_current,
            'has_pinched_hysteresis': self.classification_features.get('pinched_hysteresis', False),
            'has_switching_behavior': self.classification_features.get('switching_behavior', False)
        }

        return metrics


    def validate_memristor_behavior(self):
        """
        Validate if the device exhibits true memristive behavior based on
        theoretical memristor characteristics.

        Returns:
            dict: Validation results with pass/fail for each criterion
        """
        validation_results = {
            'pinched_hysteresis': False,
            'zero_crossing': False,
            'frequency_dependent': False,  # Would need multiple frequencies
            'non_volatile': False,
            'switching_behavior': False,
            'overall_score': 0
        }

        # Check for pinched hysteresis
        validation_results['pinched_hysteresis'] = self.classification_features.get('pinched_hysteresis', False)

        # Check for zero crossing
        zero_v_mask = np.abs(self.voltage) < 0.01
        if np.any(zero_v_mask):
            zero_currents = np.abs(self.current[zero_v_mask])
            validation_results['zero_crossing'] = np.mean(zero_currents) < 0.01 * np.max(np.abs(self.current))

        # Check for switching behavior
        validation_results['switching_behavior'] = any(ratio > 2 for ratio in self.switching_ratio)

        # Check for non-volatile behavior (retention)
        validation_results['non_volatile'] = self.retention_score > 0.7

        # Calculate overall score
        passed_tests = sum([
            validation_results['pinched_hysteresis'],
            validation_results['zero_crossing'],
            validation_results['switching_behavior'],
            validation_results['non_volatile']
        ])
        validation_results['overall_score'] = passed_tests / 4.0

        return validation_results


    def get_neuromorphic_metrics(self):
        """
        Calculate metrics relevant for neuromorphic computing applications.

        Returns:
            dict: Neuromorphic-specific metrics
        """
        metrics = {
            'synaptic_weight_range': 0,
            'weight_update_linearity': 0,
            'symmetry_factor': 0,
            'dynamic_range': 0,
            'state_retention': 0,
            'energy_efficiency': 0
        }

        # Synaptic weight range (conductance range)
        if self.ron and self.roff:
            g_max = 1 / min(self.ron)
            g_min = 1 / max(self.roff)
            metrics['synaptic_weight_range'] = g_max / g_min if g_min > 0 else 0

        # Weight update linearity (how linear is the resistance change)
        metrics['weight_update_linearity'] = 1 - np.mean(self.nonlinearity_factor) if self.nonlinearity_factor else 0

        # Symmetry factor (important for weight updates)
        metrics['symmetry_factor'] = 1 - np.mean(self.asymmetry_factor) if self.asymmetry_factor else 0

        # Dynamic range
        if len(self.current) > 0:
            i_max = np.max(np.abs(self.current))
            i_min = np.min(np.abs(self.current[self.current != 0]))
            metrics['dynamic_range'] = 20 * np.log10(i_max / i_min) if i_min > 0 else 0

        # State retention
        metrics['state_retention'] = self.retention_score

        # Energy efficiency (pJ per switch)
        if self.energy_per_switch:
            # Convert to pJ
            metrics['energy_efficiency'] = np.mean(self.energy_per_switch) * 1e12
        else:
            metrics['energy_efficiency'] = 0

        return metrics


    def get_device_summary(self):
        """Get a text summary of the device analysis."""
        summary = f"""
    Device Classification: {self.device_type} (Confidence: {self.classification_confidence:.2%})
    
    Key Metrics:
    - Number of cycles: {self.num_loops}
    - Average On/Off Ratio: {np.mean(self.on_off):.2f}
    - Average Switching Ratio (Roff/Ron): {np.mean(self.switching_ratio):.2f} if self.switching_ratio else 0
    - Retention Score: {self.retention_score:.2f}
    - Endurance Score: {self.endurance_score:.2f}
    
    Performance Indicators:
    - Power Consumption: {np.mean(self.power_consumption) * 1e6:.2f} μW if self.power_consumption else 0
    - Nonlinearity Factor: {np.mean(self.nonlinearity_factor):.2f} if self.nonlinearity_factor else 0
    - Asymmetry Factor: {np.mean(self.asymmetry_factor):.2f} if self.asymmetry_factor else 0
    - Compliance Current: {self.compliance_current * 1e6:.2f} μA" if self.compliance_current else "Not detected" """

        return summary


    def get_classification_report(self):
        """Return a structured classification report with evidence."""
        return {
            'device_type': self.device_type,
            'confidence': self.classification_confidence,
            'breakdown': self.classification_breakdown,
            'features': self.classification_features,
            'explanation': self.classification_explanation,
            'conduction_mechanism': self.conduction_mechanism,
            'model_fit_r2': self.model_parameters.get('R2', 0) if isinstance(self.model_parameters, dict) else 0,
        }

    def get_results(self, level=None):
        """
        Retrieve results at a requested analysis level.
        Levels:
          - 'basic': minimal metrics and summary
          - 'classification': includes classification report
          - 'full': adds conduction model metrics and performance metrics
          - 'research': adds deep diagnostics
        """
        effective_level = level or self.analysis_level
        out = {
            'summary': self.get_summary_stats(),
        }

        if effective_level in {'classification', 'full', 'research'}:
            out['classification'] = self.get_classification_report()
            out['validation'] = self.validate_memristor_behavior()

        if effective_level in {'full', 'research'}:
            out['performance'] = self.get_memristor_performance_metrics()

        if effective_level == 'research':
            out['diagnostics'] = {
                'switching_polarity': self.switching_polarity,
                'ndr_index': self.ndr_index,
                'hysteresis_direction': self.hysteresis_direction,
                'kink_voltage': self.kink_voltage,
                'loop_similarity_score': self.loop_similarity_score,
                'pinch_offset': self.pinch_offset,
                'noise_floor': self.noise_floor,
                'slope_exponent_stats': self.slope_exponent_stats,
            }

        return out

    def create_report(self, output_dir=None, base_name=None, save=True, include_plots=True, include_latex=True, create_pdf=True):
        """
        Create a comprehensive report object for this single device/file.

        Parameters
        ----------
        output_dir : str or None
            Directory to save artefacts (plots, CSV, LaTeX). If None and save=True, uses current directory.
        base_name : str or None
            Base filename stem to use for artefacts. If None, generates from timestamp (e.g., 'report_YYYYmmdd_HHMMSS').
        save : bool
            If True, saves plots, CSV metrics, and LaTeX table to disk.
        include_plots : bool
            If True, generates analysis and conduction plots and includes their paths in the report.
        include_latex : bool
            If True, includes LaTeX table text in the report and optionally saves to file when save=True.

        Returns
        -------
        dict
            A serializable report containing all calculated info that can be aggregated later across devices.
        """
        # Prepare filesystem context
        if base_name is None:
            base_name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if output_dir is None:
            output_dir = os.getcwd()
        if save and not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Always produce summary; add other sections per current analysis level
        results = self.get_results(level=self.analysis_level)

        # Prepare artefact paths
        analysis_png = os.path.join(output_dir, f"{base_name}_analysis.png") if (save and include_plots) else None
        conduction_png = os.path.join(output_dir, f"{base_name}_conduction.png") if (save and include_plots) else None
        csv_path = os.path.join(output_dir, f"{base_name}_metrics.csv") if save else None
        tex_path = os.path.join(output_dir, f"{base_name}_table.tex") if (save and include_latex) else None
        pdf_path = os.path.join(output_dir, f"{base_name}_report.pdf") if (save and create_pdf) else None

        # Generate plots if requested
        plot_paths = {}
        if include_plots:
            try:
                self.plot_device_analysis(save_path=analysis_png if save else None)
                plot_paths['device_analysis'] = analysis_png if save else None
            except Exception as _:
                plot_paths['device_analysis'] = None
            try:
                self.plot_conduction_analysis(save_path=conduction_png if save else None)
                plot_paths['conduction_analysis'] = conduction_png if save else None
            except Exception as _:
                plot_paths['conduction_analysis'] = None

        # Export metrics CSV if requested
        if save and csv_path is not None:
            try:
                self.export_metrics(csv_path)
            except Exception as _:
                csv_path = None

        # Generate LaTeX table text
        latex_table = None
        if include_latex:
            try:
                latex_table = generate_latex_table(self)
                if save and tex_path is not None and latex_table:
                    with open(tex_path, 'w', encoding='utf-8') as f:
                        f.write(latex_table)
            except Exception as _:
                latex_table = None

        # Research summary (human‑readable)
        try:
            research_summary = self.get_research_summary()
        except Exception:
            research_summary = None

        # Optionally compose a multi-page PDF report (text + images)
        if pdf_path is not None:
            try:
                with PdfPages(pdf_path) as pdf:
                    # Helpers for consistent text pages without overlap
                    def _format_block(title: str, lines: List[str]):
                        fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
                        ax = fig.add_axes([0.06, 0.06, 0.88, 0.88])
                        ax.axis('off')
                        fig.suptitle(title, fontsize=14, y=0.98)
                        y = 0.95
                        line_height = 0.022
                        for line in lines:
                            if y < 0.06 + line_height:
                                pdf.savefig(fig)
                                plt.close(fig)
                                fig = plt.figure(figsize=(8.27, 11.69))
                                ax = fig.add_axes([0.06, 0.06, 0.88, 0.88])
                                ax.axis('off')
                                fig.suptitle(title + " (cont.)", fontsize=14, y=0.98)
                                y = 0.95
                            ax.text(0.02, y, line, ha='left', va='top', fontsize=9, family='monospace')
                            y -= line_height
                        pdf.savefig(fig)
                        plt.close(fig)

                    def _dict_to_lines(title: str, d: dict, omit_zero: bool = True) -> List[str]:
                        lines: List[str] = [f"{title}:"]
                        for k, v in d.items():
                            # Omit None, empty, False, and numeric zeros when requested
                            if v is None:
                                continue
                            if isinstance(v, (list, tuple, dict)) and len(v) == 0:
                                continue
                            if isinstance(v, bool):
                                if not v:
                                    continue
                                sval = "True"
                            elif isinstance(v, (int, float, np.integer, np.floating)):
                                fv = float(v)
                                if omit_zero and abs(fv) == 0.0:
                                    continue
                                sval = f"{fv:.6g}"
                            else:
                                sval = str(v)
                            lines.append(f"  {k}: {sval}")
                        return lines

                    # Compose references
                    classification = results.get('classification', {}) if isinstance(results, dict) else {}
                    perf = results.get('performance', {}) if isinstance(results, dict) else {}
                    summary_stats = results.get('summary', {}) if isinstance(results, dict) else {}
                    validation = results.get('validation', {}) if isinstance(results, dict) else {}
                    neuro = None
                    try:
                        neuro = self.get_neuromorphic_metrics()
                    except Exception:
                        neuro = None

                    # Page 1+: Single info page (omit None/0/False entries), auto-continue if long
                    device_type = classification.get('device_type', getattr(self, 'device_type', None)) or self.device_type
                    conf = classification.get('confidence', getattr(self, 'classification_confidence', None)) or self.classification_confidence
                    mechanism = classification.get('conduction_mechanism', getattr(self, 'conduction_mechanism', None)) or self.conduction_mechanism
                    model_r2 = self.model_parameters.get('R2', 0) if isinstance(self.model_parameters, dict) else 0

                    overview_lines: List[str] = ["Overview:"]
                    overview_lines.append(f"  Analysis level: {self.analysis_level}")
                    if device_type:
                        overview_lines.append(f"  Device type: {device_type}")
                    if isinstance(conf, (int, float)) and conf != 0:
                        overview_lines.append(f"  Classification confidence: {conf:.1%}")
                    if mechanism:
                        overview_lines.append(f"  Conduction mechanism: {mechanism}")
                    if model_r2:
                        overview_lines.append(f"  Model R²: {model_r2:.3f}")

                    combined_lines: List[str] = []
                    combined_lines.extend(overview_lines)
                    if summary_stats:
                        combined_lines.extend(_dict_to_lines('Summary Statistics', summary_stats, omit_zero=True))
                    if perf:
                        combined_lines.extend(_dict_to_lines('Performance Metrics', perf, omit_zero=True))
                    if validation:
                        combined_lines.extend(_dict_to_lines('Memristor Behavior Validation', validation, omit_zero=True))
                    if neuro:
                        combined_lines.extend(_dict_to_lines('Neuromorphic Computing Metrics', neuro, omit_zero=True))

                    _format_block('Memristor Device Report', combined_lines)

                    # Analysis figure page
                    if analysis_png and os.path.isfile(analysis_png):
                        fig = plt.figure(figsize=(11.69, 8.27))  # landscape
                        ax = fig.add_axes([0, 0, 1, 1])
                        ax.axis('off')
                        try:
                            img = plt.imread(analysis_png)
                            ax.imshow(img)
                        except Exception:
                            ax.text(0.5, 0.5, f"Could not load image: {analysis_png}", ha='center', va='center')
                        pdf.savefig(fig)
                        plt.close(fig)

                    # Conduction figure page
                    if conduction_png and os.path.isfile(conduction_png):
                        fig = plt.figure(figsize=(11.69, 8.27))
                        ax = fig.add_axes([0, 0, 1, 1])
                        ax.axis('off')
                        try:
                            img = plt.imread(conduction_png)
                            ax.imshow(img)
                        except Exception:
                            ax.text(0.5, 0.5, f"Could not load image: {conduction_png}", ha='center', va='center')
                        pdf.savefig(fig)
                        plt.close(fig)

                    # Omit LaTeX text page to keep the report concise as requested
            except Exception:
                pdf_path = None

        report = {
            'analysis_level': self.analysis_level,
            'results': results,  # nested: summary, classification/validation/performance/diagnostics as available
            'artefacts': {
                'plots': plot_paths,
                'csv_metrics_path': csv_path,
                'latex_table_path': tex_path,
                'pdf_report_path': pdf_path,
            },
            'latex_table': latex_table,
            'research_summary': research_summary,
        }

        self.last_report = report
        return report

    def get_last_report(self):
        """Return the last report object created by create_report(), or None if not created yet."""
        return getattr(self, 'last_report', None)
    
    # ========================================================================
    # ENHANCED CLASSIFICATION SYSTEM (Phase 1)
    # ========================================================================
    # These methods provide ADDITIONAL analysis without changing core classification
    # They calculate continuous scores, adaptive thresholds, and detailed quality metrics
    # for improved device characterization, especially for organic/polymer devices
    #
    # TODO: Future Enhancement - Material/Fabrication Context
    # --------------------------------------------------------
    # Add optional 'material_type' parameter: 'organic', 'oxide', 'PCM', 'chalcogenide', etc.
    # Each material type could have:
    # - Optimized thresholds and expected behaviors
    # - Material-specific scoring weights
    # - Known variability ranges
    #
    # Example implementation:
    #   material_profiles = {
    #       'organic': {
    #           'expected_current_range': (1e-12, 1e-3),
    #           'variability_tolerance': 'high',  # More relaxed cycle-to-cycle variance
    #           'typical_voltage_range': (0.5, 5.0),
    #           'score_weights': {'pinched': 0.25, 'hysteresis': 0.30, ...}  # Adjusted for organics
    #       },
    #       'oxide_rram': {
    #           'expected_current_range': (1e-9, 1e-2),
    #           'variability_tolerance': 'low',  # Expect consistent behavior
    #           'forming_expected': True,
    #           'typical_voltage_range': (0.5, 3.0),
    #           'score_weights': {'pinched': 0.35, 'switching': 0.30, ...}
    #       },
    #       'pcm': {
    #           'threshold_switching': True,
    #           'large_resistance_change': True,
    #           'typical_voltage_range': (1.0, 5.0),
    #       }
    #   }
    #
    # This would enable:
    # - More accurate classification for diverse material systems
    # - Automatic flagging of behavior inconsistent with material type
    # - Database of expected behaviors for comparison
    # - Publication-ready material-specific benchmarking
    
    def calculate_enhanced_classification(self, save_directory=None, device_id=None, cycle_number=None):
        """
        Calculate all enhanced classification metrics.
        This is the main entry point for Phase 1 features.
        
        Parameters:
        -----------
        save_directory : str, optional
            Directory where analysis results are saved (for logging/tracking)
        device_id : str, optional
            Unique device identifier for tracking evolution
        cycle_number : int, optional
            Current cycle/measurement number
            
        Returns:
        --------
        dict : Enhanced classification data
        """
        if not self.enhanced_classification_enabled:
            return {}
        
        # Store for Phase 2 tracking
        self.save_directory = save_directory
        self.device_id = device_id
        self.cycle_number = cycle_number
        
        try:
            # Phase 1.1: Calculate memristivity score (0-100)
            self._calculate_memristivity_score()
            
            # Phase 1.2: Calculate adaptive thresholds
            self._calculate_adaptive_thresholds()
            
            # Phase 1.3: Assess memory window quality
            self._assess_memory_window_quality()
            
            # Phase 1.4: Analyze hysteresis shape
            self._analyze_hysteresis_shape()
            
            # Phase 4: Informational checks (warnings only)
            self._check_voltage_symmetry()
            self._check_current_sanity()
            self._validate_physical_plausibility()
            self._infer_speed_characteristics()
            
            # === PHASE 2: Device tracking ===
            if device_id and save_directory:
                self._save_device_measurement()
                self._analyze_device_evolution()
            
            return {
                'memristivity_score': self.memristivity_score,
                'memristivity_breakdown': self.memristivity_breakdown,
                'memory_window_quality': self.memory_window_quality,
                'hysteresis_shape': self.hysteresis_shape_features,
                'adaptive_thresholds': self.adaptive_thresholds,
                'warnings': self.classification_warnings
            }
        except Exception as e:
            self.classification_warnings.append(f"Enhanced classification failed: {str(e)}")
            return {}
    
    def _calculate_memristivity_score(self):
        """
        Calculate continuous memristivity score (0-100).
        
        This provides a more nuanced assessment than discrete categories.
        Useful for tracking device quality, comparing devices, and detecting degradation.
        
        Scoring breakdown:
        - Pinched hysteresis: 30 points (memristive fingerprint)
        - Hysteresis quality: 20 points (area, consistency)
        - Switching behavior: 20 points (ON/OFF ratio)
        - Memory window quality: 15 points (state separation)
        - Nonlinearity: 10 points (deviation from ohmic)
        - Polarity dependence: 5 points (bipolar switching)
        """
        score = 0.0
        breakdown = {}
        
        # 1. Pinched hysteresis (30 points max)
        if self.classification_features.get('pinched_hysteresis', False):
            pinched_score = 30.0
            # Bonus for quality of pinching (low current at V≈0)
            if hasattr(self, 'pinch_offset') and self.pinch_offset is not None:
                max_current = np.max(np.abs(self.current))
                if max_current > 0:
                    pinch_quality = 1.0 - min(self.pinch_offset / max_current, 1.0)
                    pinched_score *= (0.7 + 0.3 * pinch_quality)  # 70-100% of score
        elif self.classification_features.get('has_hysteresis', False):
            pinched_score = 10.0  # Some credit for hysteresis even if not pinched
        else:
            pinched_score = 0.0
        breakdown['pinched_hysteresis'] = pinched_score
        score += pinched_score
        
        # 2. Hysteresis quality (20 points max)
        hysteresis_quality = 0.0
        if self.normalized_areas:
            areas = np.abs(np.asarray(self.normalized_areas))
            median_area = float(np.median(areas))
            
            # Score based on normalized area (log scale)
            if median_area > 1e-3:
                # Scale: 1e-3 → 0 points, 1e-1 → 20 points, >1 → 20 points
                area_score = min(20.0, 20.0 * np.log10(median_area / 1e-3) / 2.0)
                hysteresis_quality += max(0, area_score)
                
            # Consistency bonus (low variance across cycles)
            if len(areas) > 1:
                consistency = 1.0 - min(np.std(areas) / (np.mean(areas) + 1e-10), 1.0)
                hysteresis_quality *= (0.8 + 0.2 * consistency)  # Up to 20% bonus
        breakdown['hysteresis_quality'] = hysteresis_quality
        score += hysteresis_quality
        
        # 3. Switching behavior (20 points max)
        switching_score = 0.0
        if self.on_off and len(self.on_off) > 0:
            mean_ratio = np.mean([r for r in self.on_off if r > 0])
            # Score based on ON/OFF ratio (log scale)
            # 1.5 → 0 pts, 10 → 15 pts, 100 → 20 pts, >1000 → 20 pts
            if mean_ratio > 1.5:
                switching_score = min(20.0, 15.0 * np.log10(mean_ratio / 1.5) / np.log10(10))
        breakdown['switching_behavior'] = switching_score
        score += switching_score
        
        # 4. Memory window quality (15 points max) - will be refined in _assess_memory_window_quality
        window_score = 0.0
        if self.ron and self.roff:
            ron_mean = np.mean([r for r in self.ron if r > 0])
            roff_mean = np.mean([r for r in self.roff if r > 0])
            if ron_mean > 0:
                window_margin = (roff_mean - ron_mean) / ron_mean
                # 0.5 → 5 pts, 1 → 10 pts, 10 → 15 pts
                if window_margin > 0.5:
                    window_score = min(15.0, 10.0 + 5.0 * np.log10(window_margin / 0.5) / np.log10(20))
        breakdown['memory_window'] = window_score
        score += window_score
        
        # 5. Nonlinearity (10 points max)
        nonlinearity_score = 0.0
        if self.classification_features.get('nonlinear_iv', False):
            nonlinearity_score = 10.0
            # Reduce if it's just capacitive nonlinearity
            if self.classification_features.get('elliptical_hysteresis', False):
                nonlinearity_score *= 0.5
        breakdown['nonlinearity'] = nonlinearity_score
        score += nonlinearity_score
        
        # 6. Polarity dependence (5 points max)
        polarity_score = 0.0
        if self.classification_features.get('polarity_dependent', False):
            polarity_score = 5.0
        breakdown['polarity_dependence'] = polarity_score
        score += polarity_score
        
        # Store results
        self.memristivity_score = round(score, 1)
        self.memristivity_breakdown = breakdown
        
        return self.memristivity_score
    
    def _calculate_adaptive_thresholds(self):
        """
        Calculate context-aware thresholds for classification.
        
        Adjusts thresholds based on:
        - Voltage range (higher V → larger expected hysteresis area)
        - Compliance current (affects ON/OFF expectations)
        - Number of data points (resolution)
        - Current magnitude (noise floor)
        - Organic device characteristics (if flagged)
        """
        thresholds = {}
        
        # Base voltage range
        v_range = np.max(np.abs(self.voltage))
        thresholds['voltage_range'] = v_range
        
        # Adaptive hysteresis area threshold
        # Base: 1e-3 for ±1V, scale with V²
        base_area_threshold = 1e-3
        thresholds['hysteresis_area_min'] = base_area_threshold * (v_range ** 2)
        
        # Adaptive ON/OFF ratio threshold
        # Base: 2.0 for standard devices
        # Relaxed to 1.5 for organic (more variable)
        base_onoff_threshold = 2.0
        thresholds['on_off_ratio_min'] = base_onoff_threshold
        
        # Noise floor estimate (based on current magnitude)
        if len(self.current) > 0:
            # Use lowest 10% of currents as noise estimate
            sorted_currents = np.sort(np.abs(self.current))
            noise_floor = np.mean(sorted_currents[:max(1, len(sorted_currents) // 10)])
            thresholds['noise_floor'] = noise_floor
            
            # Minimum switching current (10x noise floor)
            thresholds['min_switching_current'] = noise_floor * 10
        
        # Resolution-dependent confidence
        n_points = len(self.voltage)
        thresholds['data_points'] = n_points
        if n_points < 50:
            thresholds['confidence_penalty'] = 0.7  # Reduce confidence for low-res data
        elif n_points > 200:
            thresholds['confidence_penalty'] = 1.0  # Full confidence for high-res
        else:
            thresholds['confidence_penalty'] = 0.7 + 0.3 * (n_points - 50) / 150
        
        # Compliance detection impact
        if self.compliance_current is not None and self.compliance_current > 0:
            thresholds['compliance_detected'] = True
            thresholds['compliance_current'] = self.compliance_current
        else:
            thresholds['compliance_detected'] = False
        
        self.adaptive_thresholds = thresholds
        return thresholds
    
    def _assess_memory_window_quality(self):
        """
        Evaluate quality of memory window in detail.
        
        Metrics:
        - Stability: How flat/consistent are ON/OFF states?
        - Separation: Distance between states relative to noise
        - Reproducibility: Variance across cycles
        - Efficiency: Switching voltage magnitude
        - State retention: Do states persist?
        - Analog capability: Detects intermediate states
        """
        quality = {}
        
        if not self.ron or not self.roff:
            self.memory_window_quality = {'available': False}
            return
        
        ron_array = np.array([r for r in self.ron if r > 0])
        roff_array = np.array([r for r in self.roff if r > 0])
        
        if len(ron_array) == 0 or len(roff_array) == 0:
            self.memory_window_quality = {'available': False}
            return
        
        # 1. Stability score (0-100): low variance = stable
        ron_stability = 100.0 * (1.0 - min(np.std(ron_array) / (np.mean(ron_array) + 1e-10), 1.0))
        roff_stability = 100.0 * (1.0 - min(np.std(roff_array) / (np.mean(roff_array) + 1e-10), 1.0))
        quality['ron_stability'] = round(ron_stability, 1)
        quality['roff_stability'] = round(roff_stability, 1)
        quality['avg_stability'] = round((ron_stability + roff_stability) / 2, 1)
        
        # 2. Separation quality
        ron_mean = np.mean(ron_array)
        roff_mean = np.mean(roff_array)
        separation_ratio = roff_mean / ron_mean if ron_mean > 0 else 1.0
        quality['separation_ratio'] = round(separation_ratio, 2)
        
        # Separation relative to noise
        if 'noise_floor' in self.adaptive_thresholds:
            noise = self.adaptive_thresholds['noise_floor']
            # SNR = (Roff - Ron) / noise_equivalent
            delta_r = abs(roff_mean - ron_mean)
            # Convert resistance difference to current difference at 0.1V
            if delta_r > 0:
                snr_estimate = (0.1 / ron_mean - 0.1 / roff_mean) / (noise + 1e-20)
                quality['separation_snr'] = round(abs(snr_estimate), 1)
        
        # 3. Reproducibility (cycle-to-cycle consistency)
        if len(ron_array) > 1:
            ron_cv = np.std(ron_array) / (np.mean(ron_array) + 1e-10)  # Coefficient of variation
            roff_cv = np.std(roff_array) / (np.mean(roff_array) + 1e-10)
            reproducibility = 100.0 * (1.0 - min((ron_cv + roff_cv) / 2, 1.0))
            quality['reproducibility'] = round(reproducibility, 1)
        
        # 4. Switching voltage efficiency
        if self.von and self.voff:
            von_mean = np.mean([abs(v) for v in self.von if v != 0])
            voff_mean = np.mean([abs(v) for v in self.voff if v != 0])
            quality['set_voltage'] = round(von_mean, 3)
            quality['reset_voltage'] = round(voff_mean, 3)
            quality['avg_switching_voltage'] = round((von_mean + voff_mean) / 2, 3)
        
        # 5. Analog capability (detect intermediate states)
        # Check if there are distinct intermediate resistance values
        all_resistances = np.concatenate([ron_array, roff_array])
        if len(all_resistances) > 4:
            # Simple check: are there values between Ron and Roff?
            r_min = min(ron_mean, roff_mean)
            r_max = max(ron_mean, roff_mean)
            intermediate = all_resistances[(all_resistances > r_min * 1.2) & 
                                          (all_resistances < r_max * 0.8)]
            if len(intermediate) > 0:
                quality['analog_states_detected'] = True
                quality['num_intermediate_states'] = len(intermediate)
            else:
                quality['analog_states_detected'] = False
        
        # 6. Overall quality score (0-100)
        overall = (quality.get('avg_stability', 0) * 0.4 +
                  min(separation_ratio * 10, 100) * 0.3 +
                  quality.get('reproducibility', 0) * 0.3)
        quality['overall_quality_score'] = round(overall, 1)
        
        self.memory_window_quality = quality
        return quality
    
    def _analyze_hysteresis_shape(self):
        """
        Detailed analysis of hysteresis loop shape.
        
        Features:
        - Lobe asymmetry: Different shapes for set vs reset
        - Smoothness: Detect kinks/steps (trapping indicators)
        - Width variation: Measure at multiple current levels
        - Figure-eight quality: How well does it cross at origin?
        - Lobe area ratio: Set/Reset lobe comparison
        """
        features = {}
        
        if not self.classification_features.get('has_hysteresis', False):
            features['has_hysteresis'] = False
            self.hysteresis_shape_features = features
            return features
        
        features['has_hysteresis'] = True
        
        # Analyze first loop in detail (if multiple loops, average later)
        if len(self.split_v_data) > 0 and len(self.split_c_data) > 0:
            v_data = np.array(self.split_v_data[0])
            i_data = np.array(self.split_c_data[0])
            
            if len(v_data) < 4:
                self.hysteresis_shape_features = features
                return features
            
            # 1. Figure-eight quality (0-100)
            # Check how well it crosses at V≈0
            v_threshold = 0.05 * np.max(np.abs(v_data))
            near_zero = np.abs(v_data) < v_threshold
            if np.any(near_zero):
                i_near_zero = i_data[near_zero]
                max_i = np.max(np.abs(i_data))
                if max_i > 0:
                    crossing_quality = 100.0 * (1.0 - min(np.mean(np.abs(i_near_zero)) / max_i, 1.0))
                    features['figure_eight_quality'] = round(crossing_quality, 1)
            
            # 2. Split into positive and negative voltage lobes
            pos_mask = v_data > 0
            neg_mask = v_data < 0
            
            if np.any(pos_mask) and np.any(neg_mask):
                # Positive lobe area (set)
                v_pos = v_data[pos_mask]
                i_pos = i_data[pos_mask]
                if len(v_pos) > 2:
                    area_pos = abs(np.trapz(i_pos, v_pos))
                else:
                    area_pos = 0
                
                # Negative lobe area (reset)
                v_neg = v_data[neg_mask]
                i_neg = i_data[neg_mask]
                if len(v_neg) > 2:
                    area_neg = abs(np.trapz(i_neg, v_neg))
                else:
                    area_neg = 0
                
                features['positive_lobe_area'] = area_pos
                features['negative_lobe_area'] = area_neg
                
                # Lobe asymmetry (0 = symmetric, 1 = completely asymmetric)
                if area_pos + area_neg > 0:
                    asymmetry = abs(area_pos - area_neg) / (area_pos + area_neg)
                    features['lobe_asymmetry'] = round(asymmetry, 3)
                    features['lobe_area_ratio'] = round(area_pos / (area_neg + 1e-20), 2)
            
            # 3. Smoothness analysis (detect kinks/steps)
            # Calculate second derivative to find abrupt changes
            if len(v_data) > 5:
                # Use voltage derivative w.r.t. current (dV/dI)
                dv = np.diff(v_data)
                di = np.diff(i_data)
                # Avoid division by zero
                mask = np.abs(di) > 1e-15
                if np.any(mask):
                    dvdi = np.zeros_like(di)
                    dvdi[mask] = dv[mask] / di[mask]
                    
                    # Look for abrupt changes (kinks)
                    if len(dvdi) > 1:
                        smoothness = np.std(dvdi[np.isfinite(dvdi)])
                        features['smoothness_metric'] = round(float(smoothness), 6)
                        
                        # Detect kinks (points where dV/dI changes rapidly)
                        if len(dvdi) > 3:
                            d2vdi2 = np.diff(dvdi[np.isfinite(dvdi)])
                            threshold = 3 * np.std(d2vdi2) if len(d2vdi2) > 0 else 0
                            kinks = np.sum(np.abs(d2vdi2) > threshold) if threshold > 0 else 0
                            features['num_kinks_detected'] = int(kinks)
            
            # 4. Hysteresis width at different current levels
            # Measure horizontal distance between up/down sweeps
            widths = []
            i_levels = np.linspace(np.min(i_data), np.max(i_data), 5)[1:-1]  # 3 levels
            
            for i_level in i_levels:
                # Find V where I crosses this level going up and down
                crossings = []
                for i in range(len(i_data) - 1):
                    if (i_data[i] - i_level) * (i_data[i+1] - i_level) < 0:
                        # Linear interpolation
                        v_cross = v_data[i] + (v_data[i+1] - v_data[i]) * \
                                 (i_level - i_data[i]) / (i_data[i+1] - i_data[i] + 1e-20)
                        crossings.append(v_cross)
                
                if len(crossings) >= 2:
                    width = max(crossings) - min(crossings)
                    widths.append(width)
            
            if widths:
                features['avg_hysteresis_width'] = round(np.mean(widths), 6)
                features['width_variation'] = round(np.std(widths), 6)
        
        self.hysteresis_shape_features = features
        return features
    
    def _check_voltage_symmetry(self):
        """
        Analyze voltage-dependent behavior (informational only).
        
        Checks:
        - Set vs reset voltage ratio
        - Positive vs negative behavior differences
        - Bipolar vs unipolar classification
        """
        if not hasattr(self, 'von') or not hasattr(self, 'voff'):
            return
        
        if self.von and self.voff:
            von_mean = np.mean([abs(v) for v in self.von if v != 0])
            voff_mean = np.mean([abs(v) for v in self.voff if v != 0])
            
            if von_mean > 0 and voff_mean > 0:
                ratio = von_mean / voff_mean
                if ratio < 0.7 or ratio > 1.3:
                    self.classification_warnings.append(
                        f"Voltage asymmetry detected: Set={von_mean:.2f}V, Reset={voff_mean:.2f}V (ratio={ratio:.2f})"
                    )
    
    def _check_current_sanity(self):
        """
        Validate current magnitudes (warning system, doesn't block classification).
        
        Checks:
        - Is switching region above noise floor?
        - Is SNR adequate?
        - Are currents in reasonable range?
        """
        if len(self.current) == 0:
            return
        
        max_i = np.max(np.abs(self.current))
        min_i = np.min(np.abs(self.current[self.current != 0])) if np.any(self.current != 0) else 0
        
        # Check for extremely small currents
        if max_i < 1e-12:
            self.classification_warnings.append(
                f"Very low current detected (max={max_i:.2e}A). Check connections and compliance settings."
            )
        
        # Check for extremely large currents (possible short)
        if max_i > 1:
            self.classification_warnings.append(
                f"Very high current detected (max={max_i:.2e}A). Possible short circuit or damaged device."
            )
        
        # Check SNR
        if 'noise_floor' in self.adaptive_thresholds:
            noise = self.adaptive_thresholds['noise_floor']
            snr = max_i / (noise + 1e-20)
            if snr < 10:
                self.classification_warnings.append(
                    f"Low SNR detected (SNR≈{snr:.1f}). Signal may be dominated by noise."
                )
        
        # Check for switching region visibility
        if self.on_off:
            max_ratio = max(self.on_off) if self.on_off else 1.0
            if max_ratio < 1.2:
                self.classification_warnings.append(
                    f"Very small resistance change detected (max ratio={max_ratio:.2f}). "
                    f"Switching may not be significant."
                )
    
    def _validate_physical_plausibility(self):
        """
        Check for physically reasonable values (warning system).
        
        Checks:
        - Resistance in reasonable range (1e-2 to 1e12 Ω)
        - Switching voltage reasonable (< 100V for organics, < 10V typical)
        - Power dissipation realistic
        """
        # Check resistance ranges
        if self.ron:
            ron_mean = np.mean([r for r in self.ron if r > 0])
            if ron_mean < 1e-2:
                self.classification_warnings.append(
                    f"Unusually low ON resistance ({ron_mean:.2e}Ω). Check measurement setup."
                )
            elif ron_mean > 1e12:
                self.classification_warnings.append(
                    f"Extremely high ON resistance ({ron_mean:.2e}Ω). Device may be damaged or not forming."
                )
        
        if self.roff:
            roff_mean = np.mean([r for r in self.roff if r > 0])
            if roff_mean > 1e15:
                self.classification_warnings.append(
                    f"Extremely high OFF resistance ({roff_mean:.2e}Ω). Approaching open circuit."
                )
        
        # Check switching voltages
        v_max = np.max(np.abs(self.voltage))
        if v_max > 50:
            self.classification_warnings.append(
                f"High switching voltage ({v_max:.1f}V). Unusual for most memristive devices."
            )
        
        # Check power dissipation
        if len(self.voltage) > 0 and len(self.current) > 0:
            power = np.abs(self.voltage * self.current)
            max_power = np.max(power)
            avg_power = np.mean(power)
            
            if max_power > 1:
                self.classification_warnings.append(
                    f"High power dissipation (max={max_power:.2e}W). Risk of thermal damage."
                )
    
    def _infer_speed_characteristics(self):
        """
        Extract frequency/speed hints from data (informational only).
        
        If time data is available:
        - Calculate sweep rate
        - Correlate hysteresis with speed
        - Flag if behavior suggests capacitive component
        """
        if self.time is None or len(self.time) < 2:
            return
        
        # Calculate sweep rate
        dt = np.diff(self.time)
        dv = np.diff(self.voltage)
        
        # Avoid division by zero
        valid_dt = dt[dt > 0]
        valid_dv = dv[dt > 0]
        
        if len(valid_dt) > 0:
            sweep_rates = np.abs(valid_dv / valid_dt)
            avg_sweep_rate = np.mean(sweep_rates)
            
            # Store as informational
            if not hasattr(self, 'speed_characteristics'):
                self.speed_characteristics = {}
            
            self.speed_characteristics['avg_sweep_rate'] = round(avg_sweep_rate, 6)
            self.speed_characteristics['unit'] = 'V/s'
            
            # If sweep is very fast and hysteresis is large, might be capacitive
            if avg_sweep_rate > 1.0 and self.classification_features.get('has_hysteresis', False):
                if not self.classification_features.get('pinched_hysteresis', False):
                    self.classification_warnings.append(
                        f"Fast sweep rate ({avg_sweep_rate:.2f}V/s) with non-pinched hysteresis "
                        f"suggests capacitive contribution."
                    )
    
    # ========================================================================
    # DEVICE TRACKING SYSTEM (Phase 2)
    # ========================================================================
    # Track device performance over time, detect degradation, enable comparisons
    
    def _save_device_measurement(self):
        """
        Save current measurement to device history.
        Creates/appends to device_history.json in save_directory.
        """
        if not self.device_id or not self.save_directory:
            return
        
        try:
            import json
            import os
            from datetime import datetime
            
            # Create tracking directory in sample_analysis structure
            # self.save_directory is the sample-level directory
            tracking_dir = os.path.join(self.save_directory, "sample_analysis", "device_tracking")
            os.makedirs(tracking_dir, exist_ok=True)
            
            # Device history file
            history_file = os.path.join(tracking_dir, f"{self.device_id}_history.json")
            
            # Load existing history
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    history = json.load(f)
            else:
                history = {
                    'device_id': self.device_id,
                    'created': datetime.now().isoformat(),
                    'measurements': []
                }
            
            # Create measurement record
            measurement = {
                'timestamp': datetime.now().isoformat(),
                'cycle_number': self.cycle_number,
                'classification': {
                    'device_type': self.device_type,
                    'confidence': float(self.classification_confidence),
                    'memristivity_score': float(self.memristivity_score) if self.memristivity_score else None,
                    'conduction_mechanism': self.conduction_mechanism,
                },
                'resistance': {
                    'ron_mean': float(np.mean(self.ron)) if self.ron and len(self.ron) > 0 else None,
                    'roff_mean': float(np.mean(self.roff)) if self.roff and len(self.roff) > 0 else None,
                    'switching_ratio': float(np.mean(self.switching_ratio)) if self.switching_ratio and len(self.switching_ratio) > 0 else None,
                    'on_off_ratio': float(np.mean(self.on_off)) if self.on_off and len(self.on_off) > 0 else None,
                },
                'voltage': {
                    'von_mean': float(np.mean(self.von)) if self.von and len(self.von) > 0 else None,
                    'voff_mean': float(np.mean(self.voff)) if self.voff and len(self.voff) > 0 else None,
                    'max_voltage': float(np.max(np.abs(self.voltage))) if self.voltage is not None and len(self.voltage) > 0 else None,
                },
                'hysteresis': {
                    'has_hysteresis': self.classification_features.get('has_hysteresis', False),
                    'pinched': self.classification_features.get('pinched_hysteresis', False),
                    'normalized_area': float(np.mean(self.normalized_areas)) if self.normalized_areas and len(self.normalized_areas) > 0 else None,
                },
                'quality': {
                    'memory_window_quality': self.memory_window_quality.get('overall_quality_score') if self.memory_window_quality else None,
                    'stability': self.memory_window_quality.get('avg_stability') if self.memory_window_quality else None,
                },
                'warnings': self.classification_warnings.copy() if self.classification_warnings else []
            }
            
            # Append to history
            history['measurements'].append(measurement)
            history['last_updated'] = datetime.now().isoformat()
            history['total_measurements'] = len(history['measurements'])
            
            # Convert numpy types for JSON serialization
            def convert_for_json(obj):
                if isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {key: convert_for_json(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_for_json(item) for item in obj]
                return obj
            
            serializable_history = convert_for_json(history)
            
            # Save
            with open(history_file, 'w') as f:
                json.dump(serializable_history, f, indent=2)
            
        except Exception as e:
            self.classification_warnings.append(f"Device tracking save failed: {str(e)}")
    
    def _load_device_history(self):
        """Load device history from file."""
        if not self.device_id or not self.save_directory:
            return None
        
        try:
            import json
            import os
            
            tracking_dir = os.path.join(self.save_directory, "device_tracking")
            history_file = os.path.join(tracking_dir, f"{self.device_id}_history.json")
            
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception:
            return None
    
    def _analyze_device_evolution(self):
        """
        Analyze device evolution over time.
        Detects degradation, drift, and changes in behavior.
        """
        # Load history
        self.device_history = self._load_device_history()
        
        if not self.device_history or len(self.device_history.get('measurements', [])) < 2:
            return  # Need at least 2 measurements to compare
        
        try:
            measurements = self.device_history['measurements']
            
            # Get recent measurements (last 10)
            recent = measurements[-10:]
            
            # Extract trends
            memristivity_scores = [m['classification']['memristivity_score'] for m in recent 
                                  if m['classification']['memristivity_score'] is not None]
            ron_values = [m['resistance']['ron_mean'] for m in recent 
                         if m['resistance']['ron_mean'] is not None]
            roff_values = [m['resistance']['roff_mean'] for m in recent 
                          if m['resistance']['roff_mean'] is not None]
            switching_ratios = [m['resistance']['switching_ratio'] for m in recent 
                               if m['resistance']['switching_ratio'] is not None]
            
            # Detect degradation
            degradation_flags = []
            
            # 1. Memristivity score declining
            if len(memristivity_scores) >= 3:
                if memristivity_scores[-1] < memristivity_scores[0] * 0.8:
                    degradation_flags.append(f"Memristivity score declined {memristivity_scores[0]:.1f} → {memristivity_scores[-1]:.1f}")
            
            # 2. Switching ratio declining
            if len(switching_ratios) >= 3:
                if switching_ratios[-1] < switching_ratios[0] * 0.5:
                    degradation_flags.append(f"Switching ratio degraded by >50%")
            
            # 3. Ron increasing (resistance drift)
            if len(ron_values) >= 3:
                ron_change = (ron_values[-1] - ron_values[0]) / (ron_values[0] + 1e-20)
                if abs(ron_change) > 0.5:
                    degradation_flags.append(f"Ron drift: {ron_change*100:.1f}% change")
            
            # 4. Roff decreasing (losing OFF state)
            if len(roff_values) >= 3:
                roff_change = (roff_values[-1] - roff_values[0]) / (roff_values[0] + 1e-20)
                if roff_change < -0.5:
                    degradation_flags.append(f"Roff declining: {abs(roff_change)*100:.1f}% decrease")
            
            # 5. Classification changed
            current_type = self.device_type
            previous_types = [m['classification']['device_type'] for m in recent[-5:]]
            if previous_types and previous_types[0] != current_type:
                degradation_flags.append(f"Classification changed: {previous_types[0]} → {current_type}")
            
            # 6. Losing pinched hysteresis
            current_pinched = self.classification_features.get('pinched_hysteresis', False)
            previous_pinched = [m['hysteresis']['pinched'] for m in recent[-5:] 
                              if m['hysteresis']['pinched'] is not None]
            if previous_pinched and previous_pinched[0] and not current_pinched:
                degradation_flags.append("Lost pinched hysteresis (memristive fingerprint)")
            
            # Add warnings
            if degradation_flags:
                self.classification_warnings.append(
                    f"⚠ DEVICE DEGRADATION DETECTED (over {len(measurements)} measurements):"
                )
                for flag in degradation_flags:
                    self.classification_warnings.append(f"  • {flag}")
            
        except Exception as e:
            self.classification_warnings.append(f"Evolution analysis failed: {str(e)}")
    
    def get_device_evolution_summary(self):
        """
        Get summary of device evolution.
        
        Returns:
        --------
        dict : Evolution summary with trends and statistics
        """
        if not self.device_history:
            self.device_history = self._load_device_history()
        
        if not self.device_history or len(self.device_history.get('measurements', [])) < 1:
            return {'available': False, 'message': 'No history available'}
        
        try:
            measurements = self.device_history['measurements']
            
            # Extract all data
            memristivity_scores = [m['classification']['memristivity_score'] for m in measurements 
                                  if m['classification']['memristivity_score'] is not None]
            classifications = [m['classification']['device_type'] for m in measurements]
            ron_values = [m['resistance']['ron_mean'] for m in measurements 
                         if m['resistance']['ron_mean'] is not None]
            roff_values = [m['resistance']['roff_mean'] for m in measurements 
                          if m['resistance']['roff_mean'] is not None]
            
            summary = {
                'available': True,
                'total_measurements': len(measurements),
                'first_measurement': measurements[0]['timestamp'],
                'last_measurement': measurements[-1]['timestamp'],
                'classification_history': {
                    'most_common': max(set(classifications), key=classifications.count) if classifications else None,
                    'changes': len(set(classifications)),
                    'current': classifications[-1] if classifications else None,
                },
                'memristivity_trend': {
                    'first': memristivity_scores[0] if memristivity_scores else None,
                    'last': memristivity_scores[-1] if memristivity_scores else None,
                    'mean': float(np.mean(memristivity_scores)) if memristivity_scores else None,
                    'std': float(np.std(memristivity_scores)) if memristivity_scores else None,
                    'trend': 'declining' if (memristivity_scores and len(memristivity_scores) > 1 and 
                                            memristivity_scores[-1] < memristivity_scores[0] * 0.9) else 'stable',
                },
                'resistance_trend': {
                    'ron_drift_percent': ((ron_values[-1] - ron_values[0]) / (ron_values[0] + 1e-20) * 100) if len(ron_values) > 1 else 0,
                    'roff_drift_percent': ((roff_values[-1] - roff_values[0]) / (roff_values[0] + 1e-20) * 100) if len(roff_values) > 1 else 0,
                },
            }
            
            return summary
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    # ========================================================================
    # USER FEEDBACK SYSTEM (Phase 2)
    # ========================================================================
    # Allow users to correct classifications and learn from them
    
    def save_classification_feedback(self, user_classification, user_notes=""):
        """
        Save user feedback on classification.
        
        Parameters:
        -----------
        user_classification : str
            User's correction: 'memristive', 'capacitive', 'conductive', 'ohmic', 'uncertain'
        user_notes : str
            Optional notes explaining the correction
        """
        if not self.device_id or not self.save_directory:
            return
        
        try:
            import json
            import os
            from datetime import datetime
            
            # Create feedback directory
            feedback_dir = os.path.join(self.save_directory, "classification_feedback")
            os.makedirs(feedback_dir, exist_ok=True)
            
            feedback_file = os.path.join(feedback_dir, "feedback_database.json")
            
            # Load existing feedback
            if os.path.exists(feedback_file):
                with open(feedback_file, 'r') as f:
                    feedback_db = json.load(f)
            else:
                feedback_db = {'feedback_entries': []}
            
            # Create feedback entry
            entry = {
                'timestamp': datetime.now().isoformat(),
                'device_id': self.device_id,
                'cycle_number': self.cycle_number,
                'auto_classification': self.device_type,
                'auto_confidence': float(self.classification_confidence),
                'auto_memristivity_score': float(self.memristivity_score) if self.memristivity_score else None,
                'user_classification': user_classification,
                'user_notes': user_notes,
                'features': {
                    'has_hysteresis': self.classification_features.get('has_hysteresis'),
                    'pinched_hysteresis': self.classification_features.get('pinched_hysteresis'),
                    'switching_behavior': self.classification_features.get('switching_behavior'),
                    'nonlinear_iv': self.classification_features.get('nonlinear_iv'),
                    'ron_mean': float(np.mean(self.ron)) if self.ron and len(self.ron) > 0 else None,
                    'roff_mean': float(np.mean(self.roff)) if self.roff and len(self.roff) > 0 else None,
                    'switching_ratio': float(np.mean(self.switching_ratio)) if self.switching_ratio and len(self.switching_ratio) > 0 else None,
                },
                'mismatch': user_classification != self.device_type,
            }
            
            # Add to database
            feedback_db['feedback_entries'].append(entry)
            feedback_db['last_updated'] = datetime.now().isoformat()
            feedback_db['total_entries'] = len(feedback_db['feedback_entries'])
            
            # Convert numpy types for JSON serialization
            def convert_for_json(obj):
                if isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {key: convert_for_json(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_for_json(item) for item in obj]
                return obj
            
            serializable_db = convert_for_json(feedback_db)
            
            # Save
            with open(feedback_file, 'w') as f:
                json.dump(serializable_db, f, indent=2)
            
            return True
        except Exception as e:
            self.classification_warnings.append(f"Feedback save failed: {str(e)}")
            return False
    
    @staticmethod
    def load_feedback_database(save_directory):
        """
        Load the feedback database.
        
        Parameters:
        -----------
        save_directory : str
            Directory containing the feedback database
            
        Returns:
        --------
        dict : Feedback database
        """
        try:
            import json
            import os
            
            feedback_file = os.path.join(save_directory, "classification_feedback", "feedback_database.json")
            
            if os.path.exists(feedback_file):
                with open(feedback_file, 'r') as f:
                    return json.load(f)
            return {'feedback_entries': []}
        except Exception:
            return {'feedback_entries': []}
    
    def get_similar_classified_devices(self, max_results=5):
        """
        Find devices with similar features in feedback database.
        
        Parameters:
        -----------
        max_results : int
            Maximum number of similar devices to return
            
        Returns:
        --------
        list : Similar devices with their user classifications
        """
        if not self.save_directory:
            return []
        
        try:
            feedback_db = self.load_feedback_database(self.save_directory)
            
            if not feedback_db.get('feedback_entries'):
                return []
            
            # Current device features
            current_features = {
                'has_hysteresis': self.classification_features.get('has_hysteresis', False),
                'pinched_hysteresis': self.classification_features.get('pinched_hysteresis', False),
                'switching_behavior': self.classification_features.get('switching_behavior', False),
                'nonlinear_iv': self.classification_features.get('nonlinear_iv', False),
                'memristivity_score': self.memristivity_score or 0,
            }
            
            # Calculate similarity scores
            similarities = []
            for entry in feedback_db['feedback_entries']:
                entry_features = entry.get('features', {})
                
                # Feature matching score (boolean features)
                feature_match = 0
                for key in ['has_hysteresis', 'pinched_hysteresis', 'switching_behavior', 'nonlinear_iv']:
                    if entry_features.get(key) == current_features.get(key):
                        feature_match += 1
                
                # Memristivity score similarity
                entry_score = entry.get('auto_memristivity_score', 0) or 0
                score_diff = abs(entry_score - current_features['memristivity_score'])
                score_similarity = 1.0 - min(score_diff / 100.0, 1.0)
                
                # Combined similarity (70% features, 30% score)
                total_similarity = (feature_match / 4.0) * 0.7 + score_similarity * 0.3
                
                similarities.append({
                    'device_id': entry['device_id'],
                    'auto_classification': entry['auto_classification'],
                    'user_classification': entry['user_classification'],
                    'user_notes': entry.get('user_notes', ''),
                    'similarity': total_similarity,
                    'timestamp': entry['timestamp'],
                })
            
            # Sort by similarity and return top N
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:max_results]
        
        except Exception as e:
            self.classification_warnings.append(f"Similar device search failed: {str(e)}")
            return []
    
    def analyze_feedback_accuracy(self):
        """
        Analyze classification accuracy based on user feedback.
        
        Returns:
        --------
        dict : Accuracy statistics and common misclassifications
        """
        if not self.save_directory:
            return {'available': False}
        
        try:
            feedback_db = self.load_feedback_database(self.save_directory)
            
            if not feedback_db.get('feedback_entries'):
                return {'available': False, 'message': 'No feedback data'}
            
            entries = feedback_db['feedback_entries']
            
            # Calculate accuracy
            total = len(entries)
            correct = sum(1 for e in entries if not e.get('mismatch', True))
            accuracy = correct / total if total > 0 else 0
            
            # Find common misclassifications
            mismatches = [e for e in entries if e.get('mismatch', False)]
            mismatch_patterns = {}
            for m in mismatches:
                pattern = f"{m['auto_classification']} → {m['user_classification']}"
                mismatch_patterns[pattern] = mismatch_patterns.get(pattern, 0) + 1
            
            # Sort by frequency
            common_mismatches = sorted(mismatch_patterns.items(), key=lambda x: x[1], reverse=True)
            
            return {
                'available': True,
                'total_feedback': total,
                'correct_classifications': correct,
                'accuracy': accuracy,
                'accuracy_percent': accuracy * 100,
                'common_mismatches': common_mismatches[:5],  # Top 5
                'needs_improvement': accuracy < 0.8,
            }
        except Exception as e:
            return {'available': False, 'error': str(e)}





def zero_division_check(x, y):
    try:
        return x / y
    except ZeroDivisionError:  # Specifically catch ZeroDivisionError
        return 0
    except TypeError:  # Handle type errors (non-numeric inputs)
        raise TypeError("Inputs must be numeric")


def read_data_file(file_path):
    try:
        data = np.loadtxt(file_path, skiprows=1)
        voltage = data[:, 0]
        current = data[:, 1]

        # Check if time column exists
        time = data[:, 2] if data.shape[1] > 2 else None

        # Return two values for backward compatibility
        if time is None:
            return voltage, current
        else:
            return voltage, current, time
    except Exception as e:
        print(f"Error reading file {file_path}: {str(e)}")
        return None, None  # Return two values for compatibility

######
# extras
#####

def compare_devices(device_files, output_file='device_comparison.xlsx'):
    """
    Compare multiple devices and generate comparison report.

    Parameters:
    -----------
    device_files : list of str
        List of file paths to analyze
    output_file : str
        Output Excel file for comparison results
    """
    results = []

    for file_path in device_files:
        print(f"Analyzing {file_path}...")
        voltage, current, time = read_data_file(file_path)

        if voltage is not None:
            analyzer = analyze_single_file(voltage, current, time)

            # Collect key metrics
            metrics = {
                'File': file_path,
                'Device Type': analyzer.device_type,
                'Classification Confidence': analyzer.classification_confidence,
                'Conduction Mechanism': analyzer.conduction_mechanism,
                'Model R²': analyzer.model_parameters.get('R2', 0),
                'Mean Ron (Ω)': np.mean(analyzer.ron),
                'Mean Roff (Ω)': np.mean(analyzer.roff),
                'Mean Switching Ratio': np.mean(analyzer.switching_ratio),
                'Mean Window Margin': np.mean(analyzer.window_margin),
                'Retention Score': analyzer.retention_score,
                'Endurance Score': analyzer.endurance_score,
                'Mean Power (μW)': np.mean(analyzer.power_consumption) * 1e6,
                'Mean Energy/Switch (pJ)': np.mean(
                    analyzer.energy_per_switch) * 1e12 if analyzer.energy_per_switch else 0,
                'Rectification Ratio': np.mean(analyzer.rectification_ratio),
                'Nonlinearity Factor': np.mean(analyzer.nonlinearity_factor),
                'Asymmetry Factor': np.mean(analyzer.asymmetry_factor),
                'Compliance Current (μA)': analyzer.compliance_current * 1e6 if analyzer.compliance_current else 0
            }

            results.append(metrics)

    # Create comparison DataFrame
    comparison_df = pd.DataFrame(results)

    # Save to Excel with formatting
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        comparison_df.to_excel(writer, sheet_name='Device Comparison', index=False)

        # Add a summary sheet
        summary_data = {
            'Metric': ['Total Devices', 'Memristive Devices', 'Average Switching Ratio',
                       'Best Retention Score', 'Best Endurance Score'],
            'Value': [
                len(results),
                sum(1 for r in results if r['Device Type'] == 'memristive'),
                comparison_df['Mean Switching Ratio'].mean(),
                comparison_df['Retention Score'].max(),
                comparison_df['Endurance Score'].max()
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

    print(f"Comparison saved to {output_file}")
    return comparison_df


def batch_process_directory(directory_path, pattern='*.txt'):
    """
    Process all data files in a directory matching pattern.

    Parameters:
    -----------
    directory_path : str
        Path to directory containing data files
    pattern : str
        File pattern to match (default: '*.txt')
    """
    import glob
    import os

    files = glob.glob(os.path.join(directory_path, pattern))
    print(f"Found {len(files)} files to process")

    results = []
    for file_path in files:
        try:
            print(f"Processing {os.path.basename(file_path)}...")
            voltage, current, time = read_data_file(file_path)

            if voltage is not None:
                analyzer = analyze_single_file(voltage, current, time)

                # Save individual analysis
                base_name = os.path.splitext(os.path.basename(file_path))[0]

                # Save plots
                analyzer.plot_device_analysis(
                    save_path=os.path.join(directory_path, f'{base_name}_analysis.png')
                )
                analyzer.plot_conduction_analysis(
                    save_path=os.path.join(directory_path, f'{base_name}_conduction.png')
                )

                # Save metrics
                analyzer.export_metrics(
                    os.path.join(directory_path, f'{base_name}_metrics.csv')
                )

                # Save summary
                with open(os.path.join(directory_path, f'{base_name}_summary.txt'), 'w') as f:
                    f.write(analyzer.get_research_summary())

                results.append({
                    'file': file_path,
                    'analyzer': analyzer,
                    'success': True
                })
            else:
                results.append({
                    'file': file_path,
                    'analyzer': None,
                    'success': False
                })

        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            results.append({
                'file': file_path,
                'analyzer': None,
                'success': False,
                'error': str(e)
            })

    # Generate comparison report
    successful_files = [r['file'] for r in results if r['success']]
    if successful_files:
        compare_devices(successful_files,
                        output_file=os.path.join(directory_path, 'device_comparison.xlsx'))

    return results


def generate_latex_table(analyzer, caption="Device Characterization Results"):
    """
    Generate LaTeX table code for publication.

    Parameters:
    -----------
    analyzer : analyze_single_file
        Analyzer instance with results
    caption : str
        Table caption

    Returns:
    --------
    str : LaTeX table code
    """
    latex_code = r"""
\begin{table}[htbp]
\centering
\caption{""" + caption + r"""}
\begin{tabular}{ll}
\hline
\textbf{Parameter} & \textbf{Value} \\
\hline
Device Type & """ + analyzer.device_type + r""" \\
Classification Confidence & """ + f"{analyzer.classification_confidence:.1%}" + r""" \\
Conduction Mechanism & """ + analyzer.conduction_mechanism.replace('_', ' ').title() + r""" \\
Model $R^2$ & """ + f"{analyzer.model_parameters.get('R2', 0):.3f}" + r""" \\
\hline
$R_{\text{on}}$ & """ + f"{np.mean(analyzer.ron):.2e} $\pm$ {np.std(analyzer.ron):.2e}" + r""" $\Omega$ \\
$R_{\text{off}}$ & """ + f"{np.mean(analyzer.roff):.2e} $\pm$ {np.std(analyzer.roff):.2e}" + r""" $\Omega$ \\
Switching Ratio & """ + f"{np.mean(analyzer.switching_ratio):.1f} $\pm$ {np.std(analyzer.switching_ratio):.1f}" + r""" \\
Window Margin & """ + f"{np.mean(analyzer.window_margin):.1f} $\pm$ {np.std(analyzer.window_margin):.1f}" + r""" \\
\hline
Retention Score & """ + f"{analyzer.retention_score:.3f}" + r""" \\
Endurance Score & """ + f"{analyzer.endurance_score:.3f}" + r""" \\
Power Consumption & """ + f"{np.mean(analyzer.power_consumption) * 1e6:.2f}" + r""" $\mu$W \\
Energy per Switch & """ + f"{np.mean(analyzer.energy_per_switch) * 1e12:.2f}" + r""" pJ \\
\hline
\end{tabular}
\label{tab:device_characterization}
\end{table}
"""

    return latex_code


# # Example usage for research workflow
# if __name__ == "__main__":
#     # Single file analysis
#     print("=== SINGLE FILE ANALYSIS ===")
#     voltage, current, time = read_data_file("G - 10 - 34.txt")
#     if voltage is not None:
#         analyzer = analyze_single_file(voltage, current, time)
#         print(analyzer.get_research_summary())
#
#         # Generate LaTeX table for publication
#         print("\n=== LATEX TABLE ===")
#         print(generate_latex_table(analyzer))
#
#     # Batch processing example
#     # print("\n=== BATCH PROCESSING ===")
#     # results = batch_process_directory("./data/", pattern="*.txt")
#
#     # Compare specific devices
#     # print("\n=== DEVICE COMPARISON ===")
#     # device_files = ["device1.txt", "device2.txt", "device3.txt"]
#     # comparison_df = compare_devices(device_files)

# if __name__ == "__main__":
#     # Example usage for standard I-V measurement
#     voltage, current, time = read_data_file("G - 10 - 34.txt")
#     if voltage is not None and current is not None:
#         # Analyze the device
#         sfa = analyze_single_file(voltage, current, time)
#
#         # Print comprehensive summary
#         print(sfa.get_research_summary())
#
#         # Generate analysis plots
#         sfa.plot_device_analysis()
#
#         # Plot conduction mechanism analysis
#         sfa.plot_conduction_analysis()
#
#         # Export metrics
#         sfa.export_metrics("device_metrics.csv")
#
#         # Example for pulse measurement
#         print("\n=== PULSE MEASUREMENT EXAMPLE ===")
#         # If you have pulse data, specify measurement type
#         # pulse_analyzer = analyze_single_file(voltage, current, time, measurement_type='pulse')
#
#         # Example for endurance measurement
#         print("\n=== ENDURANCE MEASUREMENT EXAMPLE ===")
#         # endurance_analyzer = analyze_single_file(voltage, current, time, measurement_type='endurance')
#
#         # Example for comparing devices
#         print("\n=== DEVICE COMPARISON ===")
#         # You can create multiple analyzers and compare their metrics
#
#         # Get key metrics for comparison
#         key_metrics = {
#             'Device': 'G-10-34',
#             'Type': sfa.device_type,
#             'Mechanism': sfa.conduction_mechanism,
#             'Switching Ratio': np.mean(sfa.switching_ratio),
#             'Retention Score': sfa.retention_score,
#             'Endurance Score': sfa.endurance_score,
#             'Power (μW)': np.mean(sfa.power_consumption) * 1e6
#         }
#
#         print("\nKey Metrics for Device Comparison:")
#         for metric, value in key_metrics.items():
#             if isinstance(value, float):
#                 print(f"  {metric}: {value:.3f}")
#             else:
#                 print(f"  {metric}: {value}")

if __name__ == "__main__":
    # Example usage (original style - two parameters)
    voltage, current = read_data_file("G - 10 - 34.txt")
    if voltage is not None and current is not None:
        # Analyze the device
        sfa = analyze_single_file(voltage, current)

        # Print device classification
        print(f"Device Type: {sfa.device_type}")
        print(f"Classification Confidence: {sfa.classification_confidence:.2%}")

        # Get summary statistics
        summary = sfa.get_summary_stats()
        print("\nSummary Statistics:")
        for key, value in summary.items():
            if value is not None:
                print(f"  {key}: {value}")

        # Get performance metrics
        perf_metrics = sfa.get_memristor_performance_metrics()
        print("\nPerformance Metrics:")
        for key, value in perf_metrics.items():
            if value is not None:
                print(f"  {key}: {value}")

        # Validate memristor behavior
        validation = sfa.validate_memristor_behavior()
        print("\nMemristor Behavior Validation:")
        for key, value in validation.items():
            print(f"  {key}: {value}")

        # Get neuromorphic metrics if device is memristive
        if sfa.device_type == 'memristive':
            neuro_metrics = sfa.get_neuromorphic_metrics()
            print("\nNeuromorphic Computing Metrics:")
            for key, value in neuro_metrics.items():
                print(f"  {key}: {value}")

        # Generate plots
        sfa.plot_device_analysis()

        # Plot conduction mechanism analysis
        sfa.plot_conduction_analysis()

        # Export metrics
        sfa.export_metrics("device_metrics.csv")

        # Print research summary
        print("\n" + "=" * 50)
        print(sfa.get_research_summary())

        # Generate LaTeX table for publication
        print("\n=== LATEX TABLE ===")
        print(generate_latex_table(sfa))

    # Example with time data (if available)
    print("\n" + "=" * 50)
    print("Checking for time-based measurements...")

    # Try reading with time data
    result = read_data_file("G - 10 - 34.txt")
    if len(result) == 3:
        voltage, current, time = result
        if time is not None:
            print("Time data found - analyzing as pulse/retention measurement")
            pulse_analyzer = analyze_single_file(voltage, current, time)
            print(pulse_analyzer.get_research_summary())

    # Batch processing example (commented out - uncomment to use)
    """
    print("\n=== BATCH PROCESSING ===")
    results = batch_process_directory("./data/", pattern="*.txt")
    """

    # Device comparison example (commented out - uncomment to use)
    """
    print("\n=== DEVICE COMPARISON ===")
    device_files = ["device1.txt", "device2.txt", "device3.txt"]
    comparison_df = compare_devices(device_files)
    print(comparison_df)
    """