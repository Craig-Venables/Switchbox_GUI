"""
Metrics Panel - View accuracy metrics and statistics.
"""

import tkinter as tk
from tkinter import ttk
import matplotlib
matplotlib.use('TkAgg')  # Set backend before importing pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
try:
    import seaborn as sns
    SEABORN_AVAILABLE = True
except ImportError:
    SEABORN_AVAILABLE = False


class MetricsPanel:
    """Panel for displaying validation metrics."""
    
    def __init__(self, parent, validator):
        """
        Initialize metrics panel.
        
        Args:
            parent: Parent widget (notebook)
            validator: ClassificationValidator instance
        """
        self.validator = validator
        
        self.frame = ttk.Frame(parent)
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI."""
        # Title
        title = tk.Label(
            self.frame,
            text="Validation Metrics",
            font=('Arial', 14, 'bold')
        )
        title.pack(pady=10)
        
        # Refresh button
        refresh_btn = ttk.Button(
            self.frame,
            text="Refresh Metrics",
            command=self.refresh
        )
        refresh_btn.pack(pady=5)
        
        # Main container
        main_container = ttk.Frame(self.frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - Summary metrics
        left_panel = ttk.Frame(main_container)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5)
        
        # Accuracy summary
        summary_frame = ttk.LabelFrame(left_panel, text="Accuracy Summary")
        summary_frame.pack(fill=tk.X, pady=5)
        
        self.accuracy_text = tk.Text(summary_frame, height=15, width=40, wrap=tk.WORD)
        self.accuracy_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Per-class metrics
        per_class_frame = ttk.LabelFrame(left_panel, text="Per-Class Metrics")
        per_class_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.per_class_text = tk.Text(per_class_frame, height=10, width=40, wrap=tk.WORD)
        self.per_class_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right panel - Plots
        right_panel = ttk.Frame(main_container)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Confusion matrix
        cm_frame = ttk.LabelFrame(right_panel, text="Confusion Matrix")
        cm_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.cm_fig, self.cm_ax = plt.subplots(figsize=(6, 5))
        self.cm_canvas = FigureCanvasTkAgg(self.cm_fig, cm_frame)
        self.cm_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Score distribution
        dist_frame = ttk.LabelFrame(right_panel, text="Score Distribution")
        dist_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.dist_fig, self.dist_ax = plt.subplots(figsize=(6, 4))
        self.dist_canvas = FigureCanvasTkAgg(self.dist_fig, dist_frame)
        self.dist_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def refresh(self):
        """Refresh all metrics."""
        metrics = self.validator.get_metrics()
        
        if not metrics or 'accuracy' not in metrics or metrics['accuracy'] is None:
            self.accuracy_text.delete('1.0', tk.END)
            self.accuracy_text.insert('1.0', "No labeled data available.\n\nPlease label some devices in the Review tab first.")
            self.per_class_text.delete('1.0', tk.END)
            self._plot_empty_confusion_matrix()
            self._plot_empty_distribution()
            return
        
        # Update accuracy summary
        accuracy = metrics['accuracy']
        self.accuracy_text.delete('1.0', tk.END)
        lines = [
            "OVERALL ACCURACY",
            "=" * 40,
            f"Accuracy: {accuracy['accuracy_percent']:.1f}%",
            f"Correct: {accuracy['correct']} / {accuracy['total']}",
            f"Incorrect: {accuracy['incorrect']}",
            f"Unlabeled: {accuracy['unlabeled']}",
            "",
            "THRESHOLD OPTIMIZATION",
            "=" * 40
        ]
        
        # Get threshold optimization
        opt = self.validator.get_threshold_optimization('memristive')
        if 'optimal_threshold' in opt:
            lines.extend([
                f"Optimal Threshold: {opt['optimal_threshold']:.1f}",
                f"Best F1 Score: {opt['best_f1']:.3f}",
                f"Precision: {opt['best_precision']:.3f}",
                f"Recall: {opt['best_recall']:.3f}"
            ])
        
        self.accuracy_text.insert('1.0', '\n'.join(lines))
        
        # Update per-class metrics
        per_class = metrics.get('per_class_metrics', {})
        self.per_class_text.delete('1.0', tk.END)
        
        if per_class:
            lines = ["PER-CLASS METRICS", "=" * 40, ""]
            for class_name, class_metrics in per_class.items():
                lines.extend([
                    f"{class_name.upper()}",
                    f"  Precision: {class_metrics['precision']:.3f}",
                    f"  Recall: {class_metrics['recall']:.3f}",
                    f"  F1 Score: {class_metrics['f1']:.3f}",
                    f"  Support: {class_metrics['support']}",
                    ""
                ])
            self.per_class_text.insert('1.0', '\n'.join(lines))
        
        # Plot confusion matrix
        self._plot_confusion_matrix(metrics.get('confusion_matrix', {}))
        
        # Plot score distribution
        self._plot_score_distribution(metrics.get('score_distribution', {}))
    
    def _plot_confusion_matrix(self, confusion_data):
        """Plot confusion matrix."""
        self.cm_ax.clear()
        
        if not confusion_data or 'matrix' not in confusion_data:
            self._plot_empty_confusion_matrix()
            return
        
        matrix = confusion_data['matrix']
        classes = confusion_data.get('classes', [])
        
        if matrix.size == 0:
            self._plot_empty_confusion_matrix()
            return
        
        # Plot heatmap
        if SEABORN_AVAILABLE:
            try:
                sns.heatmap(
                    matrix,
                    annot=True,
                    fmt='d',
                    cmap='Blues',
                    xticklabels=classes,
                    yticklabels=classes,
                    ax=self.cm_ax,
                    cbar_kws={'label': 'Count'}
                )
                self.cm_ax.set_xlabel('Actual')
                self.cm_ax.set_ylabel('Predicted')
                self.cm_ax.set_title('Confusion Matrix')
                self.cm_canvas.draw()
                return
            except Exception:
                pass
        
        # Fallback if seaborn not available or failed
        im = self.cm_ax.imshow(matrix, cmap='Blues', aspect='auto')
        self.cm_ax.set_xticks(range(len(classes)))
        self.cm_ax.set_xticklabels(classes)
        self.cm_ax.set_yticks(range(len(classes)))
        self.cm_ax.set_yticklabels(classes)
        self.cm_ax.set_xlabel('Actual')
        self.cm_ax.set_ylabel('Predicted')
        self.cm_ax.set_title('Confusion Matrix')
        plt.colorbar(im, ax=self.cm_ax)
        
        # Add text annotations
        for i in range(len(classes)):
            for j in range(len(classes)):
                self.cm_ax.text(j, i, int(matrix[i, j]), ha='center', va='center')
        
        self.cm_canvas.draw()
    
    def _plot_empty_confusion_matrix(self):
        """Plot empty confusion matrix placeholder."""
        self.cm_ax.clear()
        self.cm_ax.text(0.5, 0.5, "No labeled data available", 
                       ha='center', va='center', transform=self.cm_ax.transAxes)
        self.cm_ax.set_xticks([])
        self.cm_ax.set_yticks([])
        self.cm_canvas.draw()
    
    def _plot_score_distribution(self, dist_data):
        """Plot score distribution."""
        self.dist_ax.clear()
        
        if not dist_data:
            self._plot_empty_distribution()
            return
        
        correct_stats = dist_data.get('correct', {})
        incorrect_stats = dist_data.get('incorrect', {})
        
        if correct_stats.get('count', 0) == 0 and incorrect_stats.get('count', 0) == 0:
            self._plot_empty_distribution()
            return
        
        # Create histogram data
        all_scores = dist_data.get('all_scores', [])
        if not all_scores:
            self._plot_empty_distribution()
            return
        
        # Plot histograms
        correct_scores = [s for i, s in enumerate(all_scores) 
                         if i < correct_stats.get('count', 0)]
        incorrect_scores = [s for i, s in enumerate(all_scores) 
                           if i >= correct_stats.get('count', 0)]
        
        bins = np.linspace(0, 100, 21)
        
        if correct_scores:
            self.dist_ax.hist(correct_scores, bins=bins, alpha=0.6, label='Correct', color='green')
        if incorrect_scores:
            self.dist_ax.hist(incorrect_scores, bins=bins, alpha=0.6, label='Incorrect', color='red')
        
        self.dist_ax.set_xlabel('Memristivity Score')
        self.dist_ax.set_ylabel('Count')
        self.dist_ax.set_title('Score Distribution: Correct vs Incorrect')
        self.dist_ax.legend()
        self.dist_ax.grid(True, alpha=0.3)
        
        self.dist_canvas.draw()
    
    def _plot_empty_distribution(self):
        """Plot empty distribution placeholder."""
        self.dist_ax.clear()
        self.dist_ax.text(0.5, 0.5, "No labeled data available", 
                         ha='center', va='center', transform=self.dist_ax.transAxes)
        self.dist_ax.set_xticks([])
        self.dist_ax.set_yticks([])
        self.dist_canvas.draw()
