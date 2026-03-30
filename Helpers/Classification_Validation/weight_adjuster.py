"""
Weight Adjuster - Adaptive weight adjustment based on user feedback.

Implements a simple gradient-based approach where:
- Correct feedback: Slightly reinforce weights that led to correct classification
- Incorrect feedback: Decrease weights for wrong class, increase weights for correct class
"""

from typing import Dict, Tuple
from .parameter_tuner import ParameterTuner


class WeightAdjuster:
    """Handles adaptive adjustment of classification weights based on user feedback."""
    
    def __init__(self, parameter_tuner: ParameterTuner):
        """
        Initialize weight adjuster.
        
        Args:
            parameter_tuner: ParameterTuner instance to modify
        """
        self.tuner = parameter_tuner
        self.history = []  # Track adjustments for analysis/undo
        
    def adjust_for_correct(self, features: Dict[str, any], predicted_class: str) -> Dict[str, float]:
        """
        Reinforce weights when classification was correct.
        
        Uses gentle positive adjustment to active feature weights.
        
        Args:
            features: Classification features dict (from classification_features)
            predicted_class: The device type that was correctly predicted
            
        Returns:
            Dict of weight adjustments made
        """
        learning_rate = self.tuner.get_learning_rate()
        adjustments = {}
        
        # Gentle reinforcement (half of normal learning rate)
        reinforcement = learning_rate * 0.5
        
        # Map features to weight names
        feature_to_weight = self._get_feature_to_weight_mapping(predicted_class)
        
        for feature_name, weight_key in feature_to_weight.items():
            # Check if this feature contributed to the classification
            if feature_name in features:
                feature_value = features[feature_name]
                
                # Handle boolean features
                if isinstance(feature_value, bool) and feature_value:
                    adjustments[weight_key] = reinforcement
                # Handle numeric features (e.g., phase_shift)
                elif isinstance(feature_value, (int, float)) and feature_value > 0:
                    adjustments[weight_key] = reinforcement
        
        # Apply adjustments
        self._apply_adjustments(adjustments, "correct", predicted_class, predicted_class)
        
        return adjustments
    
    def adjust_for_incorrect(self, features: Dict[str, any], 
                            predicted_class: str, actual_class: str) -> Dict[str, float]:
        """
        Adjust weights when classification was incorrect (MULTI-WEIGHT APPROACH).
        
        Strategy:
        1. Decrease weights that contributed to the WRONG prediction
        2. Increase weights that match the CORRECT classification
        
        Args:
            features: Classification features dict
            predicted_class: The incorrectly predicted device type
            actual_class: The correct device type
            
        Returns:
            Dict of weight adjustments made
        """
        learning_rate = self.tuner.get_learning_rate()
        adjustments = {}
        
        # Step 1: DECREASE weights for wrong class
        wrong_feature_map = self._get_feature_to_weight_mapping(predicted_class)
        for feature_name, weight_key in wrong_feature_map.items():
            if feature_name in features:
                feature_value = features[feature_name]
                
                if isinstance(feature_value, bool) and feature_value:
                    # This feature incorrectly contributed to wrong classification
                    adjustments[weight_key] = -learning_rate
                elif isinstance(feature_value, (int, float)) and feature_value > 0:
                    adjustments[weight_key] = -learning_rate
        
        # Step 2: INCREASE weights for correct class
        correct_feature_map = self._get_feature_to_weight_mapping(actual_class)
        for feature_name, weight_key in correct_feature_map.items():
            if feature_name in features:
                feature_value = features[feature_name]
                
                if isinstance(feature_value, bool) and feature_value:
                    # This feature should have contributed more to correct classification
                    current_adjustment = adjustments.get(weight_key, 0)
                    adjustments[weight_key] = current_adjustment + learning_rate
                elif isinstance(feature_value, (int, float)) and feature_value > 0:
                    current_adjustment = adjustments.get(weight_key, 0)
                    adjustments[weight_key] = current_adjustment + learning_rate
        
        # Apply adjustments
        self._apply_adjustments(adjustments, "incorrect", predicted_class, actual_class)
        
        return adjustments
    
    def _get_feature_to_weight_mapping(self, device_class: str) -> Dict[str, str]:
        """
        Map classification features to weight keys for a given device class.
        
        Args:
            device_class: 'memristive', 'capacitive', 'conductive', or 'ohmic'
            
        Returns:
            Dict mapping feature names to weight keys
        """
        mappings = {
            'memristive': {
                'has_hysteresis': 'memristive_has_hysteresis',
                'pinched_hysteresis': 'memristive_pinched_hysteresis',
                'switching_behavior': 'memristive_switching_behavior',
                'nonlinear_iv': 'memristive_nonlinear_iv',
                'polarity_dependent': 'memristive_polarity_dependent',
                'linear_iv': 'memristive_penalty_linear_iv',
                'ohmic_behavior': 'memristive_penalty_ohmic',
            },
            'capacitive': {
                'hysteresis_unpinched': 'capacitive_hysteresis_unpinched',
                'phase_shift': 'capacitive_phase_shift',
                'elliptical_hysteresis': 'capacitive_elliptical',
            },
            'memcapacitive': {
                'has_hysteresis': 'memcapacitive_hysteresis_unpinched',
                'switching_behavior': 'memcapacitive_switching_behavior',
                'nonlinear_iv': 'memcapacitive_nonlinear_iv',
                'phase_shift': 'memcapacitive_phase_shift',
                'pinched_hysteresis': 'memcapacitive_penalty_pinched',
            },
            'conductive': {
                'no_hysteresis': 'conductive_no_hysteresis',
                'nonlinear_no_switching': 'conductive_nonlinear_no_switching',
                'advanced_mechanism': 'conductive_advanced_mechanism',
            },
            'ohmic': {
                'linear_clean': 'ohmic_linear_clean',
                'model_fit': 'ohmic_model_fit',
            }
        }
        
        return mappings.get(device_class, {})
    
    def _apply_adjustments(self, adjustments: Dict[str, float], 
                          feedback_type: str, predicted: str, actual: str) -> None:
        """
        Apply weight adjustments to the parameter tuner.
        
        Args:
            adjustments: Dict of weight_key -> delta
            feedback_type: 'correct' or 'incorrect'
            predicted: Predicted class
            actual: Actual class
        """
        if not adjustments:
            return
            
        for weight_key, delta in adjustments.items():
            try:
                self.tuner.adjust_weight(weight_key, delta)
            except ValueError:
                # Weight key doesn't exist, skip it
                print(f"[WEIGHT_ADJUSTER] Warning: Unknown weight {weight_key}")
                continue
        
        # Record in history
        self.history.append({
            'type': feedback_type,
            'predicted': predicted,
            'actual': actual,
            'adjustments': adjustments.copy()
        })
        
        # Save updated weights
        self.tuner.save()
        
        print(f"[WEIGHT_ADJUSTER] Applied {len(adjustments)} weight adjustments ({feedback_type})")
    
    def get_adjustment_history(self) -> list:
        """Get history of all weight adjustments."""
        return self.history.copy()
    
    def undo_last_adjustment(self) -> bool:
        """
        Undo the last weight adjustment.
        
        Returns:
            True if successful, False if no history
        """
        if not self.history:
            return False
        
        last = self.history.pop()
        
        # Reverse the adjustments
        for weight_key, delta in last['adjustments'].items():
            try:
                self.tuner.adjust_weight(weight_key, -delta)
            except ValueError:
                continue
        
        self.tuner.save()
        print(f"[WEIGHT_ADJUSTER] Undid last adjustment")
        return True
