"""
Metrics Calculator - Calculate accuracy, confusion matrix, and other validation metrics.
"""

import numpy as np
from typing import List, Dict, Optional
from collections import defaultdict


class MetricsCalculator:
    """Calculate validation metrics for classification predictions."""
    
    VALID_LABELS = ['memristive', 'ohmic', 'capacitive', 'conductive']
    
    def __init__(self):
        """Initialize metrics calculator."""
        pass
    
    def calculate_accuracy(
        self, 
        predictions: List[Dict], 
        labels: Dict[str, str]
    ) -> Dict[str, any]:
        """
        Calculate overall accuracy.
        
        Args:
            predictions: List of prediction dicts with 'device_id' and 'analysis'
            labels: Dictionary mapping device_id -> ground truth label
            
        Returns:
            Dictionary with accuracy metrics
        """
        if not predictions or not labels:
            return {
                'accuracy': 0.0,
                'total': 0,
                'correct': 0,
                'incorrect': 0,
                'unlabeled': len(predictions)
            }
        
        correct = 0
        total = 0
        unlabeled = 0
        
        for pred in predictions:
            device_id = pred.get('device_id')
            if not device_id:
                continue
            
            # Check if labeled
            if device_id not in labels:
                unlabeled += 1
                continue
            
            # Get prediction
            analysis = pred.get('analysis')
            if not analysis or 'classification' not in analysis:
                continue
            
            predicted_type = analysis['classification'].get('device_type', 'unknown')
            true_label = labels[device_id]
            
            # Normalize labels
            predicted_type = predicted_type.lower() if predicted_type else 'unknown'
            true_label = true_label.lower() if true_label else 'unknown'
            
            total += 1
            if predicted_type == true_label:
                correct += 1
        
        accuracy = correct / total if total > 0 else 0.0
        
        return {
            'accuracy': accuracy,
            'total': total,
            'correct': correct,
            'incorrect': total - correct,
            'unlabeled': unlabeled,
            'accuracy_percent': accuracy * 100
        }
    
    def confusion_matrix(
        self, 
        predictions: List[Dict], 
        labels: Dict[str, str]
    ) -> Dict[str, any]:
        """
        Generate confusion matrix.
        
        Args:
            predictions: List of prediction dicts
            labels: Dictionary mapping device_id -> ground truth label
            
        Returns:
            Dictionary with:
            - 'matrix': 2D numpy array (rows=predicted, cols=actual)
            - 'classes': List of class names in order
            - 'counts': Dict of (predicted, actual) -> count
        """
        classes = self.VALID_LABELS.copy()
        matrix = np.zeros((len(classes), len(classes)), dtype=int)
        counts = defaultdict(int)
        
        for pred in predictions:
            device_id = pred.get('device_id')
            if not device_id or device_id not in labels:
                continue
            
            analysis = pred.get('analysis')
            if not analysis or 'classification' not in analysis:
                continue
            
            predicted_type = analysis['classification'].get('device_type', 'unknown').lower()
            true_label = labels[device_id].lower()
            
            if predicted_type not in classes:
                predicted_type = 'unknown'
            if true_label not in classes:
                continue  # Skip invalid labels
            
            pred_idx = classes.index(predicted_type) if predicted_type in classes else -1
            true_idx = classes.index(true_label)
            
            if pred_idx >= 0:
                matrix[pred_idx, true_idx] += 1
                counts[(predicted_type, true_label)] += 1
        
        return {
            'matrix': matrix,
            'classes': classes,
            'counts': dict(counts)
        }
    
    def per_class_metrics(
        self, 
        predictions: List[Dict], 
        labels: Dict[str, str]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate precision, recall, and F1 score per class.
        
        Args:
            predictions: List of prediction dicts
            labels: Dictionary mapping device_id -> ground truth label
            
        Returns:
            Dictionary mapping class -> {'precision': float, 'recall': float, 'f1': float, 'support': int}
        """
        confusion = self.confusion_matrix(predictions, labels)
        matrix = confusion['matrix']
        classes = confusion['classes']
        
        metrics = {}
        
        for i, class_name in enumerate(classes):
            # True positives: predicted=class, actual=class
            tp = matrix[i, i]
            
            # False positives: predicted=class, actual!=class
            fp = matrix[i, :].sum() - tp
            
            # False negatives: predicted!=class, actual=class
            fn = matrix[:, i].sum() - tp
            
            # True negatives: predicted!=class, actual!=class
            tn = matrix.sum() - tp - fp - fn
            
            # Calculate metrics
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            support = int(tp + fn)  # Total actual instances of this class
            
            metrics[class_name] = {
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'support': support,
                'tp': int(tp),
                'fp': int(fp),
                'fn': int(fn)
            }
        
        return metrics
    
    def score_distribution(
        self, 
        predictions: List[Dict], 
        labels: Dict[str, str]
    ) -> Dict[str, any]:
        """
        Analyze score distribution for correct vs incorrect predictions.
        
        Useful for finding optimal threshold.
        
        Args:
            predictions: List of prediction dicts
            labels: Dictionary mapping device_id -> ground truth label
            
        Returns:
            Dictionary with score statistics
        """
        correct_scores = []
        incorrect_scores = []
        memristive_correct = []
        memristive_incorrect = []
        
        for pred in predictions:
            device_id = pred.get('device_id')
            if not device_id or device_id not in labels:
                continue
            
            analysis = pred.get('analysis')
            if not analysis or 'classification' not in analysis:
                continue
            
            classification = analysis['classification']
            score = classification.get('memristivity_score', 0)
            predicted_type = classification.get('device_type', 'unknown').lower()
            true_label = labels[device_id].lower()
            
            is_correct = predicted_type == true_label
            
            if is_correct:
                correct_scores.append(score)
                if true_label == 'memristive':
                    memristive_correct.append(score)
            else:
                incorrect_scores.append(score)
                if predicted_type == 'memristive' and true_label != 'memristive':
                    memristive_incorrect.append(score)
        
        def stats(scores):
            if not scores:
                return {'mean': 0, 'std': 0, 'min': 0, 'max': 0, 'median': 0, 'count': 0}
            arr = np.array(scores)
            return {
                'mean': float(np.mean(arr)),
                'std': float(np.std(arr)),
                'min': float(np.min(arr)),
                'max': float(np.max(arr)),
                'median': float(np.median(arr)),
                'count': len(scores)
            }
        
        return {
            'correct': stats(correct_scores),
            'incorrect': stats(incorrect_scores),
            'memristive_correct': stats(memristive_correct),
            'memristive_incorrect': stats(memristive_incorrect),
            'all_scores': correct_scores + incorrect_scores
        }
    
    def threshold_optimization(
        self, 
        predictions: List[Dict], 
        labels: Dict[str, str],
        target_class: str = 'memristive'
    ) -> Dict[str, any]:
        """
        Find optimal threshold for a target class.
        
        Tests different thresholds and returns the one with best F1 score.
        
        Args:
            predictions: List of prediction dicts
            labels: Dictionary mapping device_id -> ground truth label
            target_class: Class to optimize threshold for (default: 'memristive')
            
        Returns:
            Dictionary with optimal threshold and metrics
        """
        # Get all scores and true labels
        scores = []
        true_labels = []
        
        for pred in predictions:
            device_id = pred.get('device_id')
            if not device_id or device_id not in labels:
                continue
            
            analysis = pred.get('analysis')
            if not analysis or 'classification' not in analysis:
                continue
            
            score = analysis['classification'].get('memristivity_score', 0)
            true_label = labels[device_id].lower()
            
            scores.append(score)
            true_labels.append(true_label)
        
        if not scores:
            return {'optimal_threshold': 60.0, 'best_f1': 0.0, 'tested_thresholds': []}
        
        # Test thresholds from 0 to 100
        thresholds = np.arange(0, 101, 5)
        results = []
        
        for threshold in thresholds:
            # Classify based on threshold
            predicted = ['memristive' if s >= threshold else 'other' for s in scores]
            
            # Calculate metrics
            tp = sum(1 for p, t in zip(predicted, true_labels) if p == 'memristive' and t == target_class)
            fp = sum(1 for p, t in zip(predicted, true_labels) if p == 'memristive' and t != target_class)
            fn = sum(1 for p, t in zip(predicted, true_labels) if p != 'memristive' and t == target_class)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            results.append({
                'threshold': float(threshold),
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'tp': tp,
                'fp': fp,
                'fn': fn
            })
        
        # Find best threshold (highest F1)
        best = max(results, key=lambda x: x['f1'])
        
        return {
            'optimal_threshold': best['threshold'],
            'best_f1': best['f1'],
            'best_precision': best['precision'],
            'best_recall': best['recall'],
            'tested_thresholds': results
        }
