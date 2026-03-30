"""
Plots tab for I-V curves, hysteresis, and resistance visualization.

Displays comprehensive I-V characterization plots for the selected device.
"""

import numpy as np
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from typing import Optional
import logging

from ..data.device_data_model import DeviceData
from ..utils.plot_utils import (
    create_mpl_canvas, create_mpl_toolbar,
    plot_hysteresis_with_cycles, plot_resistance_vs_voltage
)

logger = logging.getLogger(__name__)


class PlotsTab(QWidget):
    """
    Plots tab showing I-V curves, hysteresis, and resistance plots.
    
    Layout: 2x2 grid of subplots
    - Top-left: Main I-V hysteresis plot
    - Top-right: Resistance vs Voltage
    - Bottom-left: Cycle  overlay comparison
    - Bottom-right: Time series or placeholder
    """
    
    def __init__(self, parent=None):
        """
        Initialize plots tab.
        
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
        
        # Create matplotlib figure with 2x2 subplots
        self.figure = plt.Figure(figsize=(10, 8), dpi=100)
        self.canvas = create_mpl_canvas(self, self.figure)
        
        # Create toolbar
        self.toolbar = create_mpl_toolbar(self.canvas, self)
        
        # Add widgets to layout
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        self.setLayout(layout)
        
        # Initialize subplots
        self.ax_hysteresis = self.figure.add_subplot(2, 2, 1)
        self.ax_resistance = self.figure.add_subplot(2, 2, 2)
        self.ax_cycles = self.figure.add_subplot(2, 2, 3)
        self.ax_timeseries = self.figure.add_subplot(2, 2, 4)
        
        self.figure.tight_layout(pad=2.0)
        
        # Show placeholder
        self._show_placeholder()
    
    def _show_placeholder(self):
        """Show placeholder text when no device is selected."""
        for ax in [self.ax_hysteresis, self.ax_resistance, self.ax_cycles, self.ax_timeseries]:
            ax.clear()
            ax.text(0.5, 0.5, 'No device selected', 
                   ha='center', va='center', fontsize=11, color='gray',
                   transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        
        self.figure.tight_layout(pad=2.0)
        self.canvas.draw()
    
    def update_device(self, device: DeviceData):
        """
        Update plots with new device data.
        
        Args:
            device: DeviceData object
        """
        self.current_device = device
        
        # Check if device has measurement data
        if len(device.measurements) == 0:
            self._show_no_data()
            return
        
        # Get first measurement for plotting (or best measurement if available)
        if device.best_measurement is not None and device.best_measurement < len(device.measurements):
            measurement = device.measurements[device.best_measurement]
        else:
            measurement = device.measurements[0]
        
        # Convert to numpy arrays
        voltage = np.array(measurement.voltage) if measurement.voltage else np.array([])
        current = np.array(measurement.current) if measurement.current else np.array([])
        
        if len(voltage) == 0 or len(current) == 0:
            self._show_no_data()
            return
        
        # Clear axes
        for ax in [self.ax_hysteresis, self.ax_resistance, self.ax_cycles, self.ax_timeseries]:
            ax.clear()
        
        # Plot 1: I-V Hysteresis
        plot_hysteresis_with_cycles(self.ax_hysteresis, voltage, current)
        
        # Plot 2: Resistance vs Voltage
        plot_resistance_vs_voltage(self.ax_resistance, voltage, current, log_scale=True)
        
        # Plot 3: Cycle overlay (if multiple measurements available)
        if len(device.measurements) > 1:
            self._plot_cycle_overlay(device)
        else:
            # Just show single measurement
            self.ax_cycles.plot(voltage, current, color='#3498db', linewidth=1.5)
            self.ax_cycles.set_xlabel('Voltage (V)', fontweight='bold')
            self.ax_cycles.set_ylabel('Current (A)', fontweight='bold')
            self.ax_cycles.set_title('Measurement Data', fontweight='bold')
            self.ax_cycles.grid(True, alpha=0.3)
        
        # Plot 4: Time series or placeholder
        self._plot_timeseries_placeholder()
        
        self.figure.tight_layout(pad=2.0)
        self.canvas.draw()
        
        logger.debug(f"Plots updated for device {device.device_id}")
    
    def _plot_cycle_overlay(self, device: DeviceData):
        """
        Plot overlay of multiple measurement cycles.
        
        Args:
            device: DeviceData object
        """
        from ..utils.color_themes import PLOT_COLORS
        
        # Plot up to 5 measurements
        num_to_plot = min(5, len(device.measurements))
        
        for i in range(num_to_plot):
            measurement = device.measurements[i]
            voltage = np.array(measurement.voltage) if measurement.voltage else np.array([])
            current = np.array(measurement.current) if measurement.current else np.array([])
            
            if len(voltage) > 0 and len(current) > 0:
                color = PLOT_COLORS[i % len(PLOT_COLORS)]
                label = f"Meas {i+1}"
                self.ax_cycles.plot(voltage, current, label=label, 
                                  color=color, linewidth=1.5, alpha=0.7)
        
        self.ax_cycles.set_xlabel('Voltage (V)', fontweight='bold')
        self.ax_cycles.set_ylabel('Current (A)', fontweight='bold')
        self.ax_cycles.set_title('Measurement Overlay', fontweight='bold')
        self.ax_cycles.legend(loc='best', fontsize=8)
        self.ax_cycles.grid(True, alpha=0.3)
        
        # Add zero lines
        self.ax_cycles.axhline(y=0, color='k', linestyle='-', linewidth=0.5, alpha=0.5)
        self.ax_cycles.axvline(x=0, color='k', linestyle='-', linewidth=0.5, alpha=0.5)
    
    def _plot_timeseries_placeholder(self):
        """Plot placeholder for time series (not yet implemented)."""
        self.ax_timeseries.text(0.5, 0.5, 'Time Series\n(Future Feature)', 
                               ha='center', va='center', fontsize=11, color='gray',
                               transform=self.ax_timeseries.transAxes)
        self.ax_timeseries.set_title('Time Series Analysis', fontweight='bold')
        self.ax_timeseries.set_xticks([])
        self.ax_timeseries.set_yticks([])
    
    def _show_no_data(self):
        """Show message when device has no measurement data."""
        for ax in [self.ax_hysteresis, self.ax_resistance, self.ax_cycles, self.ax_timeseries]:
            ax.clear()
            ax.text(0.5, 0.5, 'No measurement data available', 
                   ha='center', va='center', fontsize=11, color='gray',
                   transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        
        self.figure.tight_layout(pad=2.0)
        self.canvas.draw()
    
    def clear(self):
        """Clear the plots tab."""
        self.current_device = None
        self._show_placeholder()
