"""
Validation Tool - Main orchestrator for classification validation and refinement.
"""

from typing import List, Dict, Optional
import json
from pathlib import Path

from .batch_processor import BatchProcessor
from .label_manager import LabelManager
from .parameter_tuner import ParameterTuner
from .metrics_calculator import MetricsCalculator


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
    
    def update_parameters(self, weights: Optional[Dict[str, float]] = None, thresholds: Optional[Dict[str, float]] = None) -> None:
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
        
        # Recalculate predictions with new weights
        if self.current_directory and self.predictions:
            # Re-process with new weights
            custom_weights = self.parameter_tuner.get_weights()
            self.processor = BatchProcessor(custom_weights=custom_weights)
            
            # Re-analyze all files
            print("[VALIDATOR] Recalculating predictions with new parameters...")
            total = len(self.predictions)
            for idx, pred in enumerate(self.predictions, 1):
                filepath = pred.get('file_path')
                if filepath:
                    try:
                        new_result = self.processor.process_file(filepath)
                        if new_result and new_result.get('analysis'):
                            pred['analysis'] = new_result['analysis']
                        if idx % 10 == 0:
                            print(f"[VALIDATOR] Recalculated {idx}/{total}...")
                    except Exception as e:
                        print(f"[VALIDATOR] Error recalculating {filepath}: {e}")
            
            print(f"[VALIDATOR] Recalculation complete: {total} files processed")
    
    def get_metrics(self) -> Dict[str, any]:
        """
        Get current accuracy metrics.
        
        Returns:
            Dictionary with all metrics
        """
        labels = self.label_manager.get_all_labels()
        
        if not labels:
            return {
                'accuracy': None,
                'message': 'No labels available. Please label some devices first.'
            }
        
        accuracy = self.metrics_calculator.calculate_accuracy(self.predictions, labels)
        confusion = self.metrics_calculator.confusion_matrix(self.predictions, labels)
        per_class = self.metrics_calculator.per_class_metrics(self.predictions, labels)
        score_dist = self.metrics_calculator.score_distribution(self.predictions, labels)
        
        return {
            'accuracy': accuracy,
            'confusion_matrix': confusion,
            'per_class_metrics': per_class,
            'score_distribution': score_dist
        }
    
    def get_threshold_optimization(self, target_class: str = 'memristive') -> Dict[str, any]:
        """
        Get optimal threshold recommendation.
        
        Args:
            target_class: Class to optimize for (default: 'memristive')
            
        Returns:
            Dictionary with optimal threshold and metrics
        """
        labels = self.label_manager.get_all_labels()
        if not labels:
            return {'error': 'No labels available'}
        
        return self.metrics_calculator.threshold_optimization(
            self.predictions, 
            labels, 
            target_class
        )
    
    def export_results(self, output_file: str, format: str = 'json') -> None:
        """
        Export predictions, labels, and metrics to file.
        
        Args:
            output_file: Output file path
            format: Export format ('json' or 'csv')
        """
        labels = self.label_manager.get_all_labels()
        metrics = self.get_metrics()
        weights = self.parameter_tuner.get_weights()
        thresholds = self.parameter_tuner.get_thresholds()
        
        if format.lower() == 'json':
            export_data = {
                'predictions': self.predictions,
                'labels': labels,
                'metrics': metrics,
                'weights': weights,
                'thresholds': thresholds,
                'total_files': len(self.predictions),
                'labeled_count': len(labels)
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        elif format.lower() == 'csv':
            import csv
            import pandas as pd
            
            rows = []
            for pred in self.predictions:
                device_id = pred.get('device_id', '')
                file_path = pred.get('file_path', '')
                analysis = pred.get('analysis', {})
                error = pred.get('error')
                
                if error:
                    rows.append({
                        'device_id': device_id,
                        'file_path': file_path,
                        'error': error,
                        'predicted_type': None,
                        'memristivity_score': None,
                        'true_label': labels.get(device_id, ''),
                        'correct': None
                    })
                    continue
                
                classification = analysis.get('classification', {}) if analysis else {}
                predicted_type = classification.get('device_type', 'unknown')
                score = classification.get('memristivity_score', 0)
                true_label = labels.get(device_id, '')
                correct = 'Yes' if predicted_type == true_label else 'No' if true_label else ''
                
                rows.append({
                    'device_id': device_id,
                    'file_path': file_path,
                    'error': None,
                    'predicted_type': predicted_type,
                    'memristivity_score': score,
                    'true_label': true_label,
                    'correct': correct
                })
            
            df = pd.DataFrame(rows)
            df.to_csv(output_file, index=False)
        
        print(f"[VALIDATOR] Exported results to {output_file}")
    
    def get_device_details(self, device_id: str) -> Optional[Dict]:
        """
        Get detailed information for a specific device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Dictionary with device details or None if not found
        """
        for pred in self.predictions:
            if pred.get('device_id') == device_id:
                result = pred.copy()
                result['true_label'] = self.label_manager.get_label(device_id)
                return result
        return None
    
    def get_unlabeled_devices(self) -> List[Dict]:
        """Get list of devices that haven't been labeled yet."""
        labeled_ids = set(self.label_manager.get_all_labels().keys())
        return [
            pred for pred in self.predictions 
            if pred.get('device_id') not in labeled_ids and pred.get('analysis')
        ]
    
    def get_labeled_devices(self) -> List[Dict]:
        """Get list of devices that have been labeled."""
        labeled_ids = set(self.label_manager.get_all_labels().keys())
        return [
            pred for pred in self.predictions 
            if pred.get('device_id') in labeled_ids and pred.get('analysis')
        ]
