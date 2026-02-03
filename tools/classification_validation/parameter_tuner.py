"""
Parameter Tuner - Adjust scoring weights and classification thresholds.
"""

import json
import os
from typing import Dict, Optional
from pathlib import Path


class ParameterTuner:
    """Manager for classification scoring weights and thresholds."""
    
    # Default scoring weights - synchronized with single_file_metrics.py
    # These weights are used when calculating device classification scores
    DEFAULT_WEIGHTS = {
        # === MEMRISTIVE CLASSIFICATION ===
        # Positive indicators
        'memristive_has_hysteresis': 25.0,
        'memristive_pinched_hysteresis': 30.0,
        'memristive_switching_behavior': 25.0,
        'memristive_nonlinear_iv': 10.0,
        'memristive_polarity_dependent': 10.0,
        
        # Penalties (negative weights to prevent false positives)
        'memristive_penalty_linear_iv': -20.0,
        'memristive_penalty_ohmic': -30.0,
        
        # === CAPACITIVE CLASSIFICATION ===
        'capacitive_hysteresis_unpinched': 40.0,  # hysteresis but not pinched
        'capacitive_phase_shift': 40.0,            # phase_shift > 45
        'capacitive_elliptical': 20.0,
        
        # === MEMCAPACITIVE CLASSIFICATION ===
        # User definition: High capacitive (unpinched) + High memristive (switching/nonlinear)
        'memcapacitive_hysteresis_unpinched': 40.0, # Primary capacitive trait
        'memcapacitive_switching_behavior': 30.0,   # Primary memristive trait
        'memcapacitive_nonlinear_iv': 20.0,         # Secondary memristive trait
        'memcapacitive_phase_shift': 20.0,          # Secondary capacitive trait
        'memcapacitive_penalty_pinched': -20.0,     # Penalty: Pinched is usually pure memristor
        
        # === CONDUCTIVE CLASSIFICATION ===
        'conductive_no_hysteresis': 30.0,
        'conductive_nonlinear_no_switching': 40.0,
        'conductive_advanced_mechanism': 30.0,     # SCLC, Poole-Frenkel, etc.
        
        # === OHMIC CLASSIFICATION ===
        'ohmic_linear_clean': 60.0,                # linear + no hysteresis + small window
        'ohmic_model_fit': 20.0,                   # ohmic model with R² > 0.98
        
        # === LEARNING PARAMETERS ===
        'adjustment_learning_rate': 5.0,           # How much to adjust weights per feedback
    }

    # Default thresholds
    DEFAULT_THRESHOLDS = {
        'memristive_min_score': 60.0,
        'high_confidence_min': 70.0,
        'device_type_memristive_min': 60.0,  # Score threshold for memristive classification
        'uncertain_threshold': 30.0,          # Below this score, classification is uncertain
    }

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize parameter tuner.

        Args:
            config_file: Path to JSON config file. If None, uses default location.
        """
        if config_file is None:
            # Default to data/config.json in this module's directory
            base_dir = Path(__file__).parent
            config_file = str(base_dir / "data" / "config.json")

        self.config_file = config_file
        self.weights: Dict[str, float] = self.DEFAULT_WEIGHTS.copy()
        self.thresholds: Dict[str, float] = self.DEFAULT_THRESHOLDS.copy()

        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

        # Load existing config
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.weights = config.get('weights', self.DEFAULT_WEIGHTS.copy())
                    self.thresholds = config.get('thresholds', self.DEFAULT_THRESHOLDS.copy())
                print(f"[CONFIG] Loaded configuration from {self.config_file}")
            except Exception as e:
                print(f"[CONFIG] Error loading config: {e}, using defaults")
                self.weights = self.DEFAULT_WEIGHTS.copy()
                self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        else:
            # Use defaults
            self.weights = self.DEFAULT_WEIGHTS.copy()
            self.thresholds = self.DEFAULT_THRESHOLDS.copy()

    def save(self) -> None:
        """Save configuration to file."""
        try:
            config = {
                'weights': self.weights,
                'thresholds': self.thresholds
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"[CONFIG] Saved configuration to {self.config_file}")
        except Exception as e:
            print(f"[CONFIG] Error saving config: {e}")
            raise

    def get_weights(self) -> Dict[str, float]:
        """Get current scoring weights."""
        return self.weights.copy()

    def set_weights(self, weights: Dict[str, float]) -> None:
        """
        Update scoring weights.

        Args:
            weights: Dictionary of weight name -> value
        """
        # Validate weights
        for key, value in weights.items():
            if key not in self.DEFAULT_WEIGHTS:
                print(f"[CONFIG] Warning: Unknown weight '{key}', ignoring")
                continue
            if not isinstance(value, (int, float)):
                raise ValueError(f"Weight '{key}' must be a number")

        self.weights.update(weights)

    def set_weight(self, name: str, value: float) -> None:
        """Set a single weight."""
        if name not in self.DEFAULT_WEIGHTS:
            raise ValueError(f"Unknown weight: {name}")
        self.weights[name] = float(value)

    def adjust_weight(self, name: str, delta: float) -> None:
        """
        Adjust a weight by a delta value.
        
        Args:
            name: Weight name
            delta: Amount to add to the weight (can be negative)
        """
        if name not in self.DEFAULT_WEIGHTS:
            raise ValueError(f"Unknown weight: {name}")
        self.weights[name] = self.weights.get(name, self.DEFAULT_WEIGHTS[name]) + delta

    def get_thresholds(self) -> Dict[str, float]:
        """Get current classification thresholds."""
        return self.thresholds.copy()

    def set_thresholds(self, thresholds: Dict[str, float]) -> None:
        """
        Update classification thresholds.

        Args:
            thresholds: Dictionary of threshold name -> value
        """
        self.thresholds.update(thresholds)

    def set_threshold(self, name: str, value: float) -> None:
        """Set a single threshold."""
        self.thresholds[name] = float(value)

    def reset_to_defaults(self) -> None:
        """Reset all parameters to default values."""
        self.weights = self.DEFAULT_WEIGHTS.copy()
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()

    def get_total_weight_sum(self) -> float:
        """Get sum of all weights (for normalization if needed)."""
        return sum(self.weights.values())

    def normalize_weights(self) -> None:
        """Normalize weights so they sum to 100 (maintains relative proportions)."""
        total = self.get_total_weight_sum()
        if total > 0:
            scale = 100.0 / total
            for key in self.weights:
                self.weights[key] *= scale

    def get_learning_rate(self) -> float:
        """Get the current learning rate for weight adjustments."""
        return self.weights.get('adjustment_learning_rate', 5.0)
    
    def set_learning_rate(self, rate: float) -> None:
        """Set the learning rate for weight adjustments."""
        if rate <= 0:
            raise ValueError("Learning rate must be positive")
        self.weights['adjustment_learning_rate'] = float(rate)
