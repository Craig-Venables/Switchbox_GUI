"""
Overview tab for device summary dashboard.

Combines yield heatmap with quick summary metrics and classification info.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QSplitter
)
from PyQt5.QtCore import Qt
from typing import Optional
import logging

from ..data.device_data_model import DeviceData
from .yield_heatmap_widget import YieldHeatmapWidget
from ..utils.color_themes import score_to_color, classification_to_color

logger = logging.getLogger(__name__)


class OverviewTab(QWidget):
    """
    Overview tab showing yield heatmap and device summary.
    
    Layout:
    - Top: Yield heatmap widget
    - Bottom: Summary cards (classification, metrics, best/worst sweeps)
    """
    
    def __init__(self, parent=None):
        """
        Initialize overview tab.
        
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
        
        # Create splitter for vertical split (visualizations on top, summary on bottom)
        splitter = QSplitter(Qt.Vertical)
        
        # Top: Horizontal splitter for heatmap and top device plots
        top_widget = QWidget()
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left: Yield heatmap
        self.heatmap_widget = YieldHeatmapWidget()
        top_layout.addWidget(self.heatmap_widget, stretch=1)
        
        # Right: Top memristive devices plots
        import matplotlib.pyplot as plt
        from ..utils.plot_utils import create_mpl_canvas
        
        top_devices_widget = QWidget()
        top_devices_layout = QVBoxLayout()
        top_devices_layout.setContentsMargins(0, 0, 0, 0)
        
        top_devices_label = QLabel("<b>Top Memristive Devices</b>")
        top_devices_label.setStyleSheet("padding: 5px;")
        top_devices_layout.addWidget(top_devices_label)
        
        self.top_devices_figure = plt.Figure(figsize=(4, 6), dpi=90)
        self.top_devices_canvas = create_mpl_canvas(top_devices_widget, self.top_devices_figure)
        top_devices_layout.addWidget(self.top_devices_canvas)
        
        top_devices_widget.setLayout(top_devices_layout)
        top_layout.addWidget(top_devices_widget, stretch=1)
        
        top_widget.setLayout(top_layout)
        splitter.addWidget(top_widget)
        
        # Bottom: Summary cards
        summary_widget = QWidget()
        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(0, 0, 0, 0)
        
        # Classification card
        self.classification_card = self._create_classification_card()
        summary_layout.addWidget(self.classification_card)
        
        # Key metrics card
        self.metrics_card = self._create_metrics_card()
        summary_layout.addWidget(self.metrics_card)
        
        # Best/worst sweeps card
        self.sweeps_card = self._create_sweeps_card()
        summary_layout.addWidget(self.sweeps_card)
        
        summary_widget.setLayout(summary_layout)
        splitter.addWidget(summary_widget)
        
        # Set initial sizes (visualizations larger than summary)
        splitter.setSizes([500, 200])
        
        layout.addWidget(splitter)
        self.setLayout(layout)
    
    def _create_classification_card(self) -> QGroupBox:
        """
        Create classification summary card.
        
        Returns:
            QGroupBox containing classification info
        """
        card = QGroupBox("Classification")
        layout = QVBoxLayout()
        
        self.class_type_label = QLabel("<i>No device selected</i>")
        self.class_type_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(self.class_type_label)
        
        self.class_score_label = QLabel("Score: --")
        self.class_score_label.setStyleSheet("font-size: 12pt;")
        layout.addWidget(self.class_score_label)
        
        self.class_confidence_label = QLabel("Confidence: --")
        layout.addWidget(self.class_confidence_label)
        
        layout.addStretch()
        card.setLayout(layout)
        return card
    
    def _create_metrics_card(self) -> QGroupBox:
        """
        Create key metrics summary card.
        
        Returns:
            QGroupBox containing key metrics
        """
        card = QGroupBox("Key Metrics")
        layout = QVBoxLayout()
        
        self.ron_label = QLabel("R<sub>ON</sub>: --")
        layout.addWidget(self.ron_label)
        
        self.roff_label = QLabel("R<sub>OFF</sub>: --")
        layout.addWidget(self.roff_label)
        
        self.ratio_label = QLabel("ON/OFF Ratio: --")
        layout.addWidget(self.ratio_label)
        
        self.switching_label = QLabel("Switching V: --")
        layout.addWidget(self.switching_label)
        
        layout.addStretch()
        card.setLayout(layout)
        return card
    
    def _create_sweeps_card(self) -> QGroupBox:
        """
        Create best/worst sweeps card.
        
        Returns:
            QGroupBox containing sweep info
        """
        card = QGroupBox("Sweeps")
        layout = QVBoxLayout()
        
        self.sweep_count_label = QLabel("Total Measurements: --")
        layout.addWidget(self.sweep_count_label)
        
        self.best_sweep_label = QLabel("Best: --")
        layout.addWidget(self.best_sweep_label)
        
        self.worst_sweep_label = QLabel("Worst: --")
        layout.addWidget(self.worst_sweep_label)
        
        layout.addStretch()
        card.setLayout(layout)
        return card
    
    def update_device(self, device: DeviceData):
        """
        Update overview tab with new device data.
        
        Args:
            device: DeviceData object
        """
        self.current_device = device
        
        # Update classification card
        classification = device.current_classification
        class_color = classification_to_color(classification.device_type)
        
        self.class_type_label.setText(
            f"<span style='color: {class_color};'>{classification.device_type}</span>"
        )
        self.class_score_label.setText(f"Score: {device.get_score_for_display()}")
        self.class_confidence_label.setText(f"Confidence: {classification.confidence:.1f}%")
        
        # Update metrics card
        metrics = device.metrics
        
        ron_text = f"{metrics.ron:.2e} Ω" if metrics.ron else "N/A"
        roff_text = f"{metrics.roff:.2e} Ω" if metrics.roff else "N/A"
        ratio_text = f"{metrics.on_off_ratio:.2f}" if metrics.on_off_ratio else "N/A"
        switching_text = f"{metrics.switching_voltage:.2f} V" if metrics.switching_voltage else "N/A"
        
        self.ron_label.setText(f"R<sub>ON</sub>: {ron_text}")
        self.roff_label.setText(f"R<sub>OFF</sub>: {roff_text}")
        self.ratio_label.setText(f"ON/OFF Ratio: {ratio_text}")
        self.switching_label.setText(f"Switching V: {switching_text}")
        
        # Update sweeps card
        num_measurements = len(device.measurements)
        self.sweep_count_label.setText(f"Total Measurements: {num_measurements}")
        
        if device.best_measurement is not None and device.best_measurement < num_measurements:
            best_file = device.measurements[device.best_measurement].file_path.name
            self.best_sweep_label.setText(f"Best: {best_file}")
        else:
            self.best_sweep_label.setText("Best: N/A")
        
        if device.worst_measurement is not None and device.worst_measurement < num_measurements:
            worst_file = device.measurements[device.worst_measurement].file_path.name
            self.worst_sweep_label.setText(f"Worst: {worst_file}")
        else:
            self.worst_sweep_label.setText("Worst: N/A")
        
        # Highlight device on heatmap
        self.heatmap_widget.highlight_device(device.device_id)
        
        logger.debug(f"Overview updated for device {device.device_id}")
    
    def load_devices(self, devices):
        """
        Load devices into heatmap and plot top memristive devices.
        
        Args:
            devices: List of DeviceData objects
        """
        self.heatmap_widget.load_devices(devices)
        self._plot_top_memristive_devices(devices)
    
    def _plot_top_memristive_devices(self, devices):
        """
        Plot I-V curves for top 3 memristive devices.
        
        Args:
            devices: List of DeviceData objects
        """
        import numpy as np
        from ..utils.color_themes import PLOT_COLORS
        
        # Clear the figure
        self.top_devices_figure.clear()
        
        # Filter for memristive devices and sort by score
        memristive_devices = [d for d in devices if 'mem' in d.current_classification.device_type.lower()]
        memristive_devices.sort(key=lambda d: d.memristivity_score, reverse=True)
        
        # Take top 3
        top_devices = memristive_devices[:3]
        
        if not top_devices:
            # No memristive devices found
            ax = self.top_devices_figure.add_subplot(111)
            ax.text(0.5, 0.5, 'No memristive devices found', 
                   ha='center', va='center', fontsize=10, color='gray',
                   transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            # Create subplots for each top device
            num_devices = len(top_devices)
            
            for idx, device in enumerate(top_devices):
                ax = self.top_devices_figure.add_subplot(num_devices, 1, idx + 1)
                
                # Get measurement data
                if device.measurements and len(device.measurements) > 0:
                    # Use first measurement or best if available
                    if device.best_measurement is not None and device.best_measurement < len(device.measurements):
                        meas = device.measurements[device.best_measurement]
                    else:
                        meas = device.measurements[0]
                    
                    voltage = np.array(meas.voltage) if meas.voltage else np.array([])
                    current = np.array(meas.current) if meas.current else np.array([])
                    
                    if len(voltage) > 0 and len(current) > 0:
                        # Plot I-V curve
                        color = PLOT_COLORS[idx % len(PLOT_COLORS)]
                        ax.plot(voltage, current, color=color, linewidth=1.5, alpha=0.8)
                        ax.set_ylabel('I (A)', fontsize=8)
                        ax.grid(True, alpha=0.3, linestyle='--')
                        
                        # Title with device ID and score
                        title = f"{device.device_id} ({device.memristivity_score:.0f} pts)"
                        ax.set_title(title, fontsize=9, fontweight='bold')
                        
                        # Only show x-label on bottom plot
                        if idx == num_devices - 1:
                            ax.set_xlabel('V (V)', fontsize=8)
                        
                        # Add zero lines
                        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5, alpha=0.5)
                        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5, alpha=0.5)
                    else:
                        ax.text(0.5, 0.5, 'No data', ha='center', va='center', 
                               fontsize=8, color='gray', transform=ax.transAxes)
                        ax.set_xticks([])
                        ax.set_yticks([])
                else:
                    ax.text(0.5, 0.5, 'No data', ha='center', va='center', 
                           fontsize=8, color='gray', transform=ax.transAxes)
                    ax.set_xticks([])
                    ax.set_yticks([])
        
        self.top_devices_figure.tight_layout(pad=1.0)
        self.top_devices_canvas.draw()
    
    def clear(self):
        """Clear the overview tab."""
        self.current_device = None
        self.class_type_label.setText("<i>No device selected</i>")
        self.class_score_label.setText("Score: --")
        self.class_confidence_label.setText("Confidence: --")
        self.ron_label.setText("R<sub>ON</sub>: --")
        self.roff_label.setText("R<sub>OFF</sub>: --")
        self.ratio_label.setText("ON/OFF Ratio: --")
        self.switching_label.setText("Switching V: --")
        self.sweep_count_label.setText("Total Measurements: --")
        self.best_sweep_label.setText("Best: --")
        self.worst_sweep_label.setText("Worst: --")
