import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import math
from scipy import signal, integrate
from scipy.optimize import curve_fit
import warnings


class analyze_single_file:
    """ Class for taking voltage and current data and returning all information from a sample, for later use. """

    def __init__(self, voltage, current):
        self.voltage = np.array(voltage)
        self.current = np.array(current)

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

        # New attributes for device classification
        self.device_type = None
        self.classification_confidence = 0.0
        self.classification_features = {}

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

        # Determine number of sweeps
        self.num_loops = self.check_for_loops(voltage)

        # Split into single sweeps
        self.split_v_data, self.split_c_data = self.split_loops(voltage, current)

        # Get metrics
        self.calculate_metrics_for_loops(self.split_v_data, self.split_c_data)

        # Classify device type
        self._classify_device()

        # Calculate advanced metrics
        self._calculate_advanced_metrics()

    def _classify_device(self):
        """
        Classify the device as memristive, capacitive, conductive, or uncertain.
        Based on I-V characteristics and hysteresis patterns.
        """
        # Extract classification features
        self.classification_features = self._extract_classification_features()

        # Initialize scores for each device type
        scores = {
            'memristive': 0,
            'capacitive': 0,
            'conductive': 0
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

        # Score capacitive characteristics
        if self.classification_features['has_hysteresis'] and not self.classification_features['pinched_hysteresis']:
            scores['capacitive'] += 30
        if self.classification_features['phase_shift'] > 45:
            scores['capacitive'] += 40
        if self.classification_features['elliptical_hysteresis']:
            scores['capacitive'] += 30

        # Score conductive (resistive) characteristics
        if self.classification_features['linear_iv']:
            scores['conductive'] += 50
        if not self.classification_features['has_hysteresis']:
            scores['conductive'] += 30
        if self.classification_features['ohmic_behavior']:
            scores['conductive'] += 20

        # Determine device type
        max_score = max(scores.values())
        total_score = sum(scores.values())

        if total_score == 0 or max_score < 30:
            self.device_type = 'uncertain'
            self.classification_confidence = 0.0
        else:
            self.device_type = max(scores, key=scores.get)
            self.classification_confidence = max_score / 100.0

    def _extract_classification_features(self):
        """Extract features for device classification."""
        features = {}

        # Check for hysteresis
        features['has_hysteresis'] = np.mean(self.normalized_areas) > 0.01 if self.normalized_areas else False

        # Check for pinched hysteresis (memristive fingerprint)
        features['pinched_hysteresis'] = self._check_pinched_hysteresis()

        # Check for switching behavior
        if self.on_off:
            features['switching_behavior'] = any(ratio > 2 for ratio in self.on_off if ratio > 0)
        else:
            features['switching_behavior'] = False

        # Check I-V linearity
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

    def _check_pinched_hysteresis(self):
        """Check if the I-V curve shows pinched hysteresis at origin."""
        # Find currents near zero voltage
        threshold = 0.05 * max(abs(self.voltage.max()), abs(self.voltage.min()))
        near_zero_mask = np.abs(self.voltage) < threshold

        if np.any(near_zero_mask):
            currents_near_zero = self.current[near_zero_mask]
            max_current = np.max(np.abs(self.current))
            if max_current > 0:
                # Check if current is also near zero at zero voltage
                return np.mean(np.abs(currents_near_zero)) < 0.1 * max_current
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

    def _calculate_advanced_metrics(self):
        """Calculate additional metrics for memristor characterization."""
        # Calculate metrics for each cycle
        for idx in range(len(self.split_v_data)):
            v_data = np.array(self.split_v_data[idx])
            i_data = np.array(self.split_c_data[idx])

            # Switching ratio (Roff/Ron)
            if idx < len(self.ron) and self.ron[idx] > 0:
                ratio = self.roff[idx] / self.ron[idx]
                self.switching_ratio.append(ratio)
            else:
                self.switching_ratio.append(1.0)

            # Window margin
            # Window margin
            if idx < len(self.ron) and self.ron[idx] > 0:
                margin = (self.roff[idx] - self.ron[idx]) / self.ron[idx]
                self.window_margin.append(margin)
            else:
                self.window_margin.append(0.0)

            # Rectification ratio
            rect_ratio = self._calculate_rectification_ratio(v_data, i_data)
            self.rectification_ratio.append(rect_ratio)

            # Nonlinearity factor
            nonlin = self._calculate_nonlinearity(v_data, i_data)
            self.nonlinearity_factor.append(nonlin)

            # Asymmetry factor
            asym = self._calculate_asymmetry(v_data, i_data)
            self.asymmetry_factor.append(asym)

            # Power consumption
            power = np.mean(np.abs(v_data * i_data))
            self.power_consumption.append(power)

            # Energy per switch
            if idx < len(self.von) and idx < len(self.voff):
                energy = self._calculate_switching_energy(v_data, i_data,
                                                          self.von[idx], self.voff[idx])
                self.energy_per_switch.append(energy)

        # Calculate overall device metrics
        self._calculate_retention_score()
        self._calculate_endurance_score()

        # Detect compliance current
        self.compliance_current = self._detect_compliance_current()

    def _calculate_rectification_ratio(self, voltage, current):
        """Calculate rectification ratio I(+V)/I(-V)."""
        # Use voltages at ±0.5V or ±half of max voltage
        v_ref = min(0.5, 0.5 * np.max(np.abs(voltage)))

        # Find currents at positive and negative reference voltages
        pos_idx = np.argmin(np.abs(voltage - v_ref))
        neg_idx = np.argmin(np.abs(voltage + v_ref))

        i_pos = abs(current[pos_idx])
        i_neg = abs(current[neg_idx])

        if i_neg > 1e-12:
            return i_pos / i_neg
        else:
            return 1.0

    def _calculate_nonlinearity(self, voltage, current):
        """Calculate degree of I-V nonlinearity."""
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
        """Calculate device asymmetry between positive and negative sweeps."""
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

    def _calculate_switching_energy(self, voltage, current, v_on, v_off):
        """Calculate energy required for switching."""
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

                # Use trapezoidal integration over time
                # Assuming constant voltage sweep rate
                dt = 1.0  # Normalized time
                energy = np.trapz(np.abs(power), dx=dt)
                return energy
        except:
            pass
        return 0.0

    def _calculate_retention_score(self):
        """Calculate retention stability score based on resistance variation."""
        if len(self.ron) > 1 and len(self.roff) > 1:
            # Calculate coefficient of variation for Ron and Roff
            cv_ron = np.std(self.ron) / (np.mean(self.ron) + 1e-10)
            cv_roff = np.std(self.roff) / (np.mean(self.roff) + 1e-10)

            # Retention score (lower CV is better)
            self.retention_score = 1.0 / (1.0 + cv_ron + cv_roff)
        else:
            self.retention_score = 0.0

    def _calculate_endurance_score(self):
        """Calculate endurance score based on cycle-to-cycle consistency."""
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
                if len(values) > 1 and np.mean(values) > 0:
                    cv = np.std(values) / np.mean(values)
                    consistency = 1.0 / (1.0 + cv)
                    consistency_scores.append(consistency)

            if consistency_scores:
                self.endurance_score = np.mean(consistency_scores)
            else:
                self.endurance_score = 0.0
        else:
            self.endurance_score = 0.0

    def _detect_compliance_current(self):
        """Detect current compliance if present."""
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

    def get_memristor_performance_metrics(self):
        """
        Get comprehensive performance metrics for memristor evaluation.
        Returns a dictionary with all relevant metrics.
        """
        metrics = {
            'device_type': self.device_type,
            'classification_confidence': self.classification_confidence,
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

    def plot_device_analysis(self, save_path=None):
        """Generate comprehensive plots for device analysis."""
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle(f'Device Analysis - Type: {self.device_type} (Confidence: {self.classification_confidence:.2f})')

        # Plot 1: I-V characteristics
        ax1 = axes[0, 0]
        ax1.plot(self.voltage, self.current * 1e6, 'b-', linewidth=2)
        ax1.set_xlabel('Voltage (V)')
        ax1.set_ylabel('Current (μA)')
        ax1.set_title('I-V Characteristics')
        ax1.grid(True, alpha=0.3)

        # Plot 2: Resistance vs Voltage
        ax2 = axes[0, 1]
        resistance = np.abs(self.voltage / (self.current + 1e-12))
        ax2.semilogy(self.voltage, resistance, 'r-', linewidth=2)
        ax2.set_xlabel('Voltage (V)')
        ax2.set_ylabel('Resistance (Ω)')
        ax2.set_title('Resistance vs Voltage')
        ax2.grid(True, alpha=0.3)

        # Plot 3: Hysteresis loops
        ax3 = axes[0, 2]
        for i in range(min(3, len(self.split_v_data))):
            ax3.plot(self.split_v_data[i], np.array(self.split_c_data[i]) * 1e6,
                     label=f'Cycle {i + 1}', alpha=0.7)
        ax3.set_xlabel('Voltage (V)')
        ax3.set_ylabel('Current (μA)')
        ax3.set_title('Individual Cycles')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Plot 4: Metrics evolution
        ax4 = axes[1, 0]
        if len(self.on_off) > 1:
            cycles = range(1, len(self.on_off) + 1)
            ax4.plot(cycles, self.on_off, 'go-', label='On/Off Ratio')
            ax4.set_xlabel('Cycle')
            ax4.set_ylabel('On/Off Ratio')
            ax4.set_title('Switching Ratio Evolution')
            ax4.grid(True, alpha=0.3)

        # Plot 5: Power consumption
        ax5 = axes[1, 1]
        if self.power_consumption:
            cycles = range(1, len(self.power_consumption) + 1)
            ax5.plot(cycles, np.array(self.power_consumption) * 1e6, 'mo-')
            ax5.set_xlabel('Cycle')
            ax5.set_ylabel('Power (μW)')
            ax5.set_title('Power Consumption')
            ax5.grid(True, alpha=0.3)

        # Plot 6: Classification features
        ax6 = axes[1, 2]
        features = ['Hysteresis', 'Pinched', 'Switching', 'Nonlinear', 'Linear']
        values = [
            self.classification_features.get('has_hysteresis', 0),
            self.classification_features.get('pinched_hysteresis', 0),
            self.classification_features.get('switching_behavior', 0),
            self.classification_features.get('nonlinear_iv', 0),
            self.classification_features.get('linear_iv', 0)
        ]
        ax6.bar(features, values)
        ax6.set_title('Classification Features')
        ax6.set_ylim([0, 1.2])

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()

    def get_device_summary(self):
        """Get a text summary of the device analysis."""
        summary = f"""
    Device Classification: {self.device_type} 
    (Confidence: {self.classification_confidence:.2%})
    Key Metrics:
    - Number of cycles: {self.num_loops}
    - Average On/Off Ratio: {np.mean(self.on_off):.2f}
    - Average Switching Ratio (Roff/Ron): {np.mean(self.switching_ratio):.2f}
    - Retention Score: {self.retention_score:.2f}
    - Endurance Score: {self.endurance_score:.2f}
    
    Performance Indicators:
    - Power Consumption: {np.mean(self.power_consumption) * 1e6:.2f} μW
    - Nonlinearity Factor: {np.mean(self.nonlinearity_factor):.2f}
    - Asymmetry Factor: {np.mean(self.asymmetry_factor):.2f}
    - Compliance Current: {self.compliance_current * 1e6:.2f} μA""" if self.compliance_current else "Not detected"

        return summary

        return summary

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

        # Add device classification
        metrics_dict['device_type'] = [self.device_type] * len(self.ps_areas)
        metrics_dict['classification_confidence'] = [self.classification_confidence] * len(self.ps_areas)

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
            area = np.trapz(current, voltage)
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

        # blue - green
        # red - yellow

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
        # Return the calculated Ron and Roff values and on and off voltages
        return resistance_on_value, resistance_off_value, voltage_on_value, voltage_off_value

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
        metrics['weight_update_linearity'] = 1 - np.mean(self.nonlinearity_factor)

        # Symmetry factor (important for weight updates)
        metrics['symmetry_factor'] = 1 - np.mean(self.asymmetry_factor)

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

        return metrics


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

        return voltage, current
    except Exception as e:
        print(f"Error reading file {file_path}: {str(e)}")
        return None, None


if __name__ == "__main__":
    # Example usage
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

        # Export metrics
        sfa.export_metrics("device_metrics.csv")


# # Basic usage
# voltage, current = read_data_file("your_data.txt")
# analyzer = analyze_single_file(voltage, current)
#
# # Check device type
# print(f"Device type: {analyzer.device_type}")
# print(f"Confidence: {analyzer.classification_confidence:.2%}")
#
# # Get comprehensive metrics
# metrics = analyzer.get_memristor_performance_metrics()
# for key, value in metrics.items():
#     print(f"{key}: {value}")
#
# # Validate memristor behavior
# validation = analyzer.validate_memristor_behavior()
# if validation['overall_score'] > 0.75:
#     print("Device shows strong memristive behavior")
#
# # For neuromorphic applications
# if analyzer.device_type == 'memristive':
#     neuro_metrics = analyzer.get_neuromorphic_metrics()
#     print(f"Synaptic weight range: {neuro_metrics['synaptic_weight_range']}")
#     print(f"Energy per switch: {neuro_metrics['energy_efficiency']} pJ")
#
# # Generate analysis plots
# analyzer.plot_device_analysis(save_path="device_analysis.png")