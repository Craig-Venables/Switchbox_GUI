"""
Metrics tab for device metrics visualization and comparison.

Shows metrics charts, radar plots, and detailed metrics table.
"""

import numpy as np
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt
from typing import Optional
import logging

from ..data.device_data_model import DeviceData
from ..utils.plot_utils import create_mpl_canvas, plot_metrics_radar

logger = logging.getLogger(__name__)


class MetricsTab(QWidget):
    """
    Metrics tab showing charts, radar plot, and detailed metrics table.
    
    Layout: 2x2 grid
    - Top-left: Ron vs Roff scatter
    - Top-right: Switching ratio distribution
    - Bottom-left: Radar chart
    - Bottom-right: Metrics table
    """
    
    def __init__(self, parent=None):
        """
        Initialize metrics tab.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.current_device = None
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout =QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create matplotlib figure with 2x2 grid
        self.figure = plt.Figure(figsize=(10, 8), dpi=100)
        self.canvas = create_mpl_canvas(self, self.figure)
        
        # Create table widget
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(4)
        self.metrics_table.setHorizontalHeaderLabels(['Metric', 'Value', 'Unit', 'Status'])
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.metrics_table.setAlternatingRowColors(True)
        
        # Create layout: top = plots, bottom = table
        top_widget = QWidget()
        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self.canvas)
        top_widget.setLayout(top_layout)
        
        # Add to main layout
        layout.addWidget(top_widget, stretch=2)
        layout.addWidget(self.metrics_table, stretch=1)
        
        self.setLayout(layout)
        
        # Initialize subplots
        self.ax_ron_roff = self.figure.add_subplot(2, 2, 1)
        self.ax_ratio_dist = self.figure.add_subplot(2, 2, 2)
        self.ax_radar = self.figure.add_subplot(2, 2, 3, projection='polar')
        self.ax_placeholder = self.figure.add_subplot(2, 2, 4)
        
        self.figure.tight_layout(pad=2.0)
        
        # Show placeholder
        self._show_placeholder()
    
    def _show_placeholder(self):
        """Show placeholder when no device is selected."""
        for ax in [self.ax_ron_roff, self.ax_ratio_dist, self.ax_placeholder]:
            ax.clear()
            ax.text(0.5, 0.5, 'No device selected', 
                   ha='center', va='center', fontsize=11, color='gray',
                   transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        
        self.ax_radar.clear()
        self.ax_radar.text(0, 0, 'No data', ha='center', va='center', 
                          fontsize=11, color='gray')
        
        self.figure.tight_layout(pad=2.0)
        self.canvas.draw()
        
        # Clear table
        self.metrics_table.setRowCount(0)
    
    def update_device(self, device: DeviceData):
        """
        Update metrics tab with new device data.
        
        Args:
            device: DeviceData object
        """
        self.current_device = device
        
        # Clear axes
        for ax in [self.ax_ron_roff, self.ax_ratio_dist, self.ax_placeholder]:
            ax.clear()
        self.ax_radar.clear()
        
        # Plot 1: Ron vs Roff scatter
        self._plot_ron_roff_scatter(device)
        
        # Plot 2: Switching ratio distribution (placeholder for now)
        self._plot_ratio_distribution(device)
        
        # Plot 3: Radar chart
        self._plot_radar_chart(device)
        
        # Plot 4: Placeholder
        self.ax_placeholder.text(0.5, 0.5, 'Additional Metrics\n(Future Feature)', 
                                ha='center', va='center', fontsize=11, color='gray',
                                transform=self.ax_placeholder.transAxes)
        self.ax_placeholder.set_xticks([])
        self.ax_placeholder.set_yticks([])
        
        self.figure.tight_layout(pad=2.0)
        self.canvas.draw()
        
        # Update metrics table
        self._update_metrics_table(device)
        
        logger.debug(f"Metrics updated for device {device.device_id}")
    
    def _plot_ron_roff_scatter(self, device: DeviceData):
        """Plot Ron vs Roff scatter."""
        metrics = device.metrics
        
        if metrics.ron and metrics.roff:
            self.ax_ron_roff.scatter([metrics.ron], [metrics.roff], 
                                    s=100, c='#3498db', alpha=0.7, edgecolors='black')
            self.ax_ron_roff.set_xlabel('R_ON (Ω)', fontweight='bold')
            self.ax_ron_roff.set_ylabel('R_OFF (Ω)', fontweight='bold')
            self.ax_ron_roff.set_title('Resistance States', fontweight='bold')
            self.ax_ron_roff.set_xscale('log')
            self.ax_ron_roff.set_yscale('log')
            self.ax_ron_roff.grid(True, alpha=0.3, which='both')
            
            # Add diagonal line (1:1 ratio)
            min_val = min(metrics.ron, metrics.roff) * 0.5
            max_val = max(metrics.ron, metrics.roff) * 2
            self.ax_ron_roff.plot([min_val, max_val], [min_val, max_val], 
                                 'k--', alpha=0.3, label='1:1 line')
        else:
            self.ax_ron_roff.text(0.5, 0.5, 'No Ron/Roff data', 
                                 ha='center', va='center', fontsize=10, color='gray',
                                 transform=self.ax_ron_roff.transAxes)
    
    def _plot_ratio_distribution(self, device: DeviceData):
        """Plot switching ratio distribution (simplified for single device)."""
        metrics = device.metrics
        
        if metrics.on_off_ratio:
            # For single device, show bar with target line
            self.ax_ratio_dist.bar(['ON/OFF Ratio'], [metrics.on_off_ratio], 
                                  color='#27ae60', alpha=0.7, edgecolor='black')
            self.ax_ratio_dist.axhline(y=2, color='r', linestyle='--', 
                                      label='Min Target (2x)', alpha=0.5)
            self.ax_ratio_dist.axhline(y=10, color='orange', linestyle='--', 
                                      label='Good Target (10x)', alpha=0.5)
            self.ax_ratio_dist.set_ylabel('Ratio (Roff/Ron)', fontweight='bold')
            self.ax_ratio_dist.set_title('Switching Ratio', fontweight='bold')
            self.ax_ratio_dist.legend(fontsize=8)
            self.ax_ratio_dist.grid(True, alpha=0.3, axis='y')
        else:
            self.ax_ratio_dist.text(0.5, 0.5, 'No ratio data', 
                                   ha='center', va='center', fontsize=10, color='gray',
                                   transform=self.ax_ratio_dist.transAxes)
    
    def _plot_radar_chart(self, device: DeviceData):
        """Plot radar chart for multi-metric comparison."""
        # Normalize metrics to 0-1 scale for radar chart
        metrics_dict = {}
        
        m = device.metrics
        
        # Add available metrics (normalized)
        if m.on_off_ratio:
            # Normalize ratio: cap at 100, scale to 0-1
            metrics_dict['ON/OFF'] = min(m.on_off_ratio / 100.0, 1.0)
        
        if m.nonlinearity:
            metrics_dict['Nonlinearity'] = min(m.nonlinearity, 1.0)
        
        if device.memristivity_score > 0:
            metrics_dict['Score'] = device.memristivity_score / 100.0
        
        if device.current_classification.confidence > 0:
            metrics_dict['Confidence'] = device.current_classification.confidence / 100.0
        
        # Add placeholder metrics
        if len(metrics_dict) < 3:
            metrics_dict['Placeholder1'] = 0.5
            metrics_dict['Placeholder2'] = 0.3
        
        if len(metrics_dict) > 0:
            plot_metrics_radar(self.ax_radar, metrics_dict)
        else:
            self.ax_radar.text(0, 0, 'No metrics available', 
                              ha='center', va='center', fontsize=10, color='gray')
    
    def _update_metrics_table(self, device: DeviceData):
        """Update the metrics table with device data."""
        metrics = device.metrics
        
        # Clear table
        self.metrics_table.setRowCount(0)
        
        # Define metrics to display
        metrics_list = [
            ('R_ON', metrics.ron, 'Ω', self._get_status_ron(metrics.ron)),
            ('R_OFF', metrics.roff, 'Ω', self._get_status_roff(metrics.roff)),
            ('ON/OFF Ratio', metrics.on_off_ratio, '', self._get_status_ratio(metrics.on_off_ratio)),
            ('Switching Voltage', metrics.switching_voltage, 'V', ''),
            ('SET Voltage', metrics.set_voltage, 'V', ''),
            ('RESET Voltage', metrics.reset_voltage, 'V', ''),
            ('Hysteresis Area', metrics.hysteresis_area, 'A·V', ''),
            ('Nonlinearity', metrics.nonlinearity, '', ''),
            ('Memristivity Score', device.memristivity_score, 'pts', self._get_status_score(device.memristivity_score)),
            ('Classification', device.current_classification.device_type, '', ''),
        ]
        
        # Populate table
        for metric_name, value, unit, status in metrics_list:
            row = self.metrics_table.rowCount()
            self.metrics_table.insertRow(row)
            
            # Metric name
            self.metrics_table.setItem(row, 0, QTableWidgetItem(metric_name))
            
            # Value
            if value is not None and value != '':
                if isinstance(value, float):
                    value_str = f"{value:.2e}" if value < 0.01 or value > 1000 else f"{value:.3f}"
                else:
                    value_str = str(value)
            else:
                value_str = 'N/A'
            self.metrics_table.setItem(row, 1, QTableWidgetItem(value_str))
            
            # Unit
            self.metrics_table.setItem(row, 2, QTableWidgetItem(unit))
            
            # Status
            self.metrics_table.setItem(row, 3, QTableWidgetItem(status))
    
    def _get_status_ron(self, ron) -> str:
        """Get status icon for Ron value."""
        if ron is None:
            return ''
        if ron < 1e6:  # Less than 1 MΩ
            return '✓'
        elif ron < 10e6:  # Less than 10 MΩ
            return '⚠'
        else:
            return '✗'
    
    def _get_status_roff(self, roff) -> str:
        """Get status icon for Roff value."""
        if roff is None:
            return ''
        if roff > 10e6:  # Greater than 10 MΩ
            return '✓'
        elif roff > 1e6:  # Greater than 1 MΩ
            return '⚠'
        else:
            return '✗'
    
    def _get_status_ratio(self, ratio) -> str:
        """Get status icon for ON/OFF ratio."""
        if ratio is None:
            return ''
        if ratio > 10:
            return '✓'
        elif ratio > 2:
            return '⚠'
        else:
            return '✗'
    
    def _get_status_score(self, score) -> str:
        """Get status icon for memristivity score."""
        if score >= 70:
            return '✓'
        elif score >= 40:
            return '⚠'
        else:
            return '✗'
    
    def clear(self):
        """Clear the metrics tab."""
        self.current_device = None
        self._show_placeholder()
