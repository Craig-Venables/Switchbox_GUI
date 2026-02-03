"""
Parameter Tuner - Adjust scoring weights and classification thresholds.
"""

import json
import os
from typing import Dict, Optional
from pathlib import Path


class ParameterTuner:
    """Manage and apply custom scoring weights and thresholds."""
    
    # Default weights from single_file_metrics.py
    # Note: breakdown uses 'memory_window' not 'memory_window_quality'
    DEFAULT_WEIGHTS = {
        'pinched_hysteresis': 30.0,
        'hysteresis_quality': 20.0,
        'switching_behavior': 20.0,
        'memory_window': 15.0,  # Note: actual breakdown key is 'memory_window'
        'nonlinearity': 10.0,
        'polarity_dependence': 5.0
    }
    
    # Default thresholds
    DEFAULT_THRESHOLDS = {
        'memristive_min_score': 60.0,
        'high_confidence_min': 70.0,
        'device_type_memristive_min': 60.0  # Score threshold for memristive classification
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
            if not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"Weight '{key}' must be a non-negative number")
        
        self.weights.update(weights)
    
    def set_weight(self, name: str, value: float) -> None:
        """Set a single weight."""
        if name not in self.DEFAULT_WEIGHTS:
            raise ValueError(f"Unknown weight: {name}")
        if value < 0:
            raise ValueError(f"Weight must be non-negative")
        self.weights[name] = float(value)
    
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

