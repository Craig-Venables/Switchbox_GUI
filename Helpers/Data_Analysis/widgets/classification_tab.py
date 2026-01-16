"""
Classification tab for showing classification breakdown and decision details.

Displays score breakdown, decision tree, warnings, and feature indicators.
"""

import matplotlib.pyplot as plt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QGroupBox, QLabel, QSplitter
)
from PyQt5.QtCore import Qt
from typing import Optional
import logging

from ..data.device_data_model import DeviceData
from ..utils.plot_utils import create_mpl_canvas, plot_score_breakdown

logger = logging.getLogger(__name__)


class ClassificationTab(QWidget):
    """
    Classification tab showing score breakdown and classification details.
    
    Layout:
    - Top: Score breakdown bar chart
    - Middle: Decision tree/path visualization
    - Bottom: Warnings and red flags panel
    """
    
    def __init__(self, parent=None):
        """
        Initialize classification tab.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.current_device = None
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create splitter for vertical split
        splitter = QSplitter(Qt.Vertical)
        
        # Top: Score breakdown chart
        chart_widget = QWidget()
        chart_layout = QVBoxLayout()
        chart_layout.setContentsMargins(0, 0, 0, 0)
        
        self.figure = plt.Figure(figsize=(8, 4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = create_mpl_canvas(chart_widget, self.figure)
        chart_layout.addWidget(self.canvas)
        chart_widget.setLayout(chart_layout)
        
        splitter.addWidget(chart_widget)
        
        # Middle: Decision info
        decision_group = QGroupBox("Classification Decision")
        decision_layout = QVBoxLayout()
        
        self.decision_label = QLabel("<i>No device selected</i>")
        self.decision_label.setWordWrap(True)
        decision_layout.addWidget(self.decision_label)
        
        self.confidence_label = QLabel("Confidence: --")
        decision_layout.addWidget(self.confidence_label)
        
        decision_group.setLayout(decision_layout)
        splitter.addWidget(decision_group)
        
        # Bottom: Warnings panel
        warnings_group = QGroupBox("Warnings and Flags")
        warnings_layout = QVBoxLayout()
        
        self.warnings_text = QTextEdit()
        self.warnings_text.setReadOnly(True)
        self.warnings_text.setMaximumHeight(150)
        self.warnings_text.setStyleSheet("""
            QTextEdit {
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        warnings_layout.addWidget(self.warnings_text)
        
        warnings_group.setLayout(warnings_layout)
        splitter.addWidget(warnings_group)
        
        # Set initial sizes
        splitter.setSizes([300, 100, 150])
        
        layout.addWidget(splitter)
        self.setLayout(layout)
        
        # Show placeholder
        self._show_placeholder()
    
    def _show_placeholder(self):
        """Show placeholder when no device is selected."""
        self.ax.clear()
        self.ax.text(0.5, 0.5, 'No device selected', 
                    ha='center', va='center', fontsize=11, color='gray',
                    transform=self.ax.transAxes)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw()
        
        self.decision_label.setText("<i>No device selected</i>")
        self.confidence_label.setText("Confidence: --")
        self.warnings_text.setPlainText("No warnings to display.")
    
    def update_device(self, device: DeviceData):
        """
        Update classification tab with new device data.
        
        Args:
            device: DeviceData object
        """
        self.current_device = device
        
        # Update score breakdown chart
        self._update_score_breakdown(device)
        
        # Update decision info
        classification = device.current_classification
        self.decision_label.setText(
            f"<b>Classification:</b> {classification.device_type}<br>"
            f"<b>Score:</b> {device.memristivity_score:.1f} pts"
        )
        self.confidence_label.setText(f"<b>Confidence:</b> {classification.confidence:.1f}%")
        
        # Update warnings
        self._update_warnings(device)
        
        logger.debug(f"Classification updated for device {device.device_id}")
    
    def _update_score_breakdown(self, device: DeviceData):
        """
        Update score breakdown chart.
        
        Args:
            device: DeviceData object
        """
        self.ax.clear()
        
        # Get feature scores
        feature_scores = device.current_classification.feature_scores
        
        if feature_scores and len(feature_scores) > 0:
            # Plot score breakdown
            plot_score_breakdown(self.ax, feature_scores)
        else:
            # Show placeholder if no feature scores
            self.ax.text(0.5, 0.5, 'No feature score breakdown available', 
                        ha='center', va='center', fontsize=11, color='gray',
                        transform=self.ax.transAxes)
            self.ax.set_xticks([])
            self.ax.set_yticks([])
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def _update_warnings(self, device: DeviceData):
        """
        Update warnings panel.
        
        Args:
            device: DeviceData object
        """
        warnings = device.current_classification.warnings
        
        if warnings and len(warnings) > 0:
            # Format warnings
            warning_text = ""
            for i, warning in enumerate(warnings, 1):
                warning_text += f"⚠ {warning}\n"
            
            self.warnings_text.setPlainText(warning_text)
            
            # Style based on severity (all yellow for now)
            self.warnings_text.setStyleSheet("""
                QTextEdit {
                    background-color: #fff3cd;
                    border: 1px solid #ffc107;
                    border-radius: 3px;
                    padding: 5px;
                    color: #856404;
                }
            """)
        else:
            # No warnings
            self.warnings_text.setPlainText("✓ No warnings detected. Classification looks good!")
            self.warnings_text.setStyleSheet("""
                QTextEdit {
                    background-color: #d4edda;
                    border: 1px solid #28a745;
                    border-radius: 3px;
                    padding: 5px;
                    color: #155724;
                }
            """)
    
    def clear(self):
        """Clear the classification tab."""
        self.current_device = None
        self._show_placeholder()
