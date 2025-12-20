"""
Validation Tool - Main orchestrator for classification validation and refinement.
Now includes interactive weight adjustment via user feedback.
"""

from typing import List, Dict, Optional
import json
from pathlib import Path

from .batch_processor import BatchProcessor
from .label_manager import LabelManager
from .parameter_tuner import ParameterTuner
from .metrics_calculator import MetricsCalculator
from .weight_adjuster import WeightAdjuster


class ClassificationValidator:
    """Main orchestrator for classification validation and refinement."""
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize validation tool.
        
        Args:
            data_dir: Base directory for storing labels and config. If None, uses module default.
        """
        if data_dir is None:
            data_dir = str(Path(__file__).parent / "data")

        self.label_manager = LabelManager()
        self.parameter_tuner = ParameterTuner()
        self.metrics_calculator = MetricsCalculator()
        self.weight_adjuster = WeightAdjuster(self.parameter_tuner)  # NEW: Weight adjustment
        self.processor = BatchProcessor(custom_weights=None)

        self.predictions: List[Dict] = []
        self.current_directory: Optional[str] = None

    def load_data(
        self,
        directory: str,
        recursive: bool = True,
        pattern: str = "*.txt",
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """
        Load and analyze all IV files in a directory.

        Args:
            directory: Directory to scan for IV files
            recursive: Whether to scan subdirectories
            pattern: File pattern to match
            progress_callback: Optional callback(processed, total, current_file)

        Returns:
            List of analysis results
        """
        self.current_directory = directory

        # Update processor with current weights
        weights = self.parameter_tuner.get_weights()
        self.processor = BatchProcessor(custom_weights=weights)

        # Process files
        results = self.processor.process_directory(
            directory=directory,
            recursive=recursive,
            pattern=pattern,
            progress_callback=progress_callback
        )

        self.predictions = results
        return results

    def get_predictions(self) -> List[Dict]:
        """Get current predictions."""
        return self.predictions.copy()

    def update_parameters(self, weights: Optional[Dict[str, float]] = None, 
                         thresholds: Optional[Dict[str, float]] = None) -> None:
        """
        Update parameters and recalculate predictions.

        Args:
            weights: Dictionary of weight name -> value
            thresholds: Dictionary of threshold name -> value
        """
        # Update tuner
        if weights:
            self.parameter_tuner.set_weights(weights)
        if thresholds:
            self.parameter_tuner.set_thresholds(thresholds)

        # Save config
        self.parameter_tuner.save()

        print("[VALIDATOR] Parameters updated. Recalculation required.")

    def provide_feedback(self, device_id: str, is_correct: bool, 
                        actual_class: str = None, reanalyze_all: bool = False) -> Dict:
        """
        Process user feedback on a classification (INTERACTIVE WEIGHT ADJUSTMENT).
        
        This is the KEY METHOD for the interactive tuning workflow:
        1. User reviews a classification
        2. Marks it correct/incorrect
        3. Weights are automatically adjusted
        4. Device is re-analyzed with new weights
        
        Args:
            device_id: ID of the device being reviewed
            is_correct: True if classification was correct
            actual_class: If incorrect, the correct device type ('memristive', 'capacitive', etc.)
            reanalyze_all: If True, re-analyze all devices with new weights (slower but shows global impact)
            
        Returns:
            Dictionary with:
            - 'success': bool
            - 'new_classification': dict (updated classification for this device)
            - 'weight_changes': dict (what weights were adjusted)
            - 'message': str (human-readable feedback)
        """
        # Find the prediction
        pred = next((p for p in self.predictions if p.get('device_id') == device_id), None)
        if not pred:
            return {
                'success': False,
                'message': f"Device {device_id} not found in predictions"
            }
        
        # Get analysis data
        analysis = pred.get('analysis')
        if not analysis or 'classification_features' not in analysis:
            return {
                'success': False,
                'message': "Device has no classification features"
            }
        
        features = analysis['classification_features']
        classification = analysis.get('classification', {})
        predicted_class = classification.get('device_type', 'unknown')
        
        # Adjust weights based on feedback
        if is_correct:
            adjustments = self.weight_adjuster.adjust_for_correct(features, predicted_class)
            message = f"Reinforced weights for correct '{predicted_class}' classification"
        else:
            if not actual_class:
                return {
                    'success': False,
                    'message': "Must provide actual_class when marking incorrect"
                }
            adjustments = self.weight_adjuster.adjust_for_incorrect(features, predicted_class, actual_class)
            message = f"Adjusted weights: decreased '{predicted_class}', increased '{actual_class}'"
        
        # Re-analyze this device with new weights
        new_analysis = self._reanalyze_device(device_id)
        
        # Optionally re-analyze all devices
        if reanalyze_all and self.current_directory:
            print("[VALIDATOR] Re-analyzing all devices with updated weights...")
            self.load_data(self.current_directory)
        
        return {
            'success': True,
            'new_classification': new_analysis,
            'weight_changes': adjustments,
            'message': message
        }

    def _reanalyze_device(self, device_id: str) -> Optional[Dict]:
        """
        Re-analyze a single device with current weights.
        
        Args:
            device_id: Device to re-analyze
            
        Returns:
            Updated analysis dict, or None if failed
        """
        # Find the device prediction
        pred = next((p for p in self.predictions if p.get('device_id') == device_id), None)
        if not pred:
            return None
        
        file_path = pred.get('file_path')
        if not file_path:
            return None
        
        # Re-process the file with current weights
        weights = self.parameter_tuner.get_weights()
        self.processor = BatchProcessor(custom_weights=weights)
        
        new_result = self.processor.process_file(file_path)
        
        if new_result and 'analysis' in new_result:
            # Update our predictions list
            for i, p in enumerate(self.predictions):
                if p.get('device_id') == device_id:
                    self.predictions[i] = new_result
                    break
            
            return new_result.get('analysis')
        
        return None

    def reanalyze_all_devices(self, progress_callback: Optional[callable] = None) -> int:
        """
        Re-analyze all devices with current weights.
        
        Args:
            progress_callback: Optional callback(processed, total, current_file)
            
        Returns:
            Number of devices successfully re-analyzed
        """
        if not self.current_directory:
            return 0
        
        self.load_data(self.current_directory, progress_callback=progress_callback)
        return len([p for p in self.predictions if p.get('analysis')])

    def get_weight_adjustment_history(self) -> List[Dict]:
        """Get history of all weight adjustments made during this session."""
        return self.weight_adjuster.get_adjustment_history()

    def undo_last_weight_adjustment(self) -> bool:
        """
        Undo the last weight adjustment.
        
        Returns:
            True if successful, False if no history
        """
        return self.weight_adjuster.undo_last_adjustment()

    def save_weights(self) -> None:
        """Manually save current weights to config file."""
        self.parameter_tuner.save()

    def reset_weights_to_defaults(self) -> None:
        """Reset all weights to default values."""
        self.parameter_tuner.reset_to_defaults()
        self.parameter_tuner.save()
        print("[VALIDATOR] Weights reset to defaults")
    
    def get_metrics(self, target_class: str = 'memristive') -> Dict:
        """
        Calculate classification metrics for display.
        
        Args:
            target_class: Class to calculate metrics for
            
        Returns:
            Dict with accuracy, precision, recall, etc.
        """
        # Get labels
        labels = self.label_manager.get_all_labels()
        
        if not labels:
            return {
                'accuracy': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0,
                'confusion_matrix': {},
                'labeled_count': 0,
                'total_count': len(self.predictions)
            }
        
        # Calculate accuracy
        accuracy_result = self.metrics_calculator.calculate_accuracy(
            self.predictions, labels, target_class
        )
        
        # Calculate confusion matrix
        confusion = self.metrics_calculator.confusion_matrix(
            self.predictions, labels
        )
        
        return {
            'accuracy': accuracy_result.get('accuracy', 0.0),
            'precision': accuracy_result.get('precision', 0.0),
            'recall': accuracy_result.get('recall', 0.0),
            'f1': accuracy_result.get('f1', 0.0),
            'confusion_matrix': confusion,
            'labeled_count': len(labels),
            'total_count': len(self.predictions),
            'tp': accuracy_result.get('tp', 0),
            'fp': accuracy_result.get('fp', 0),
            'fn': accuracy_result.get('fn', 0),
            'tn': accuracy_result.get('tn', 0),
        }
