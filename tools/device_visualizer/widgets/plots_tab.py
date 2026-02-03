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
        
        # Plot 4: Time series (if time data available) or voltage/current vs index
        if measurement.time is not None and len(measurement.time) > 0:
            self._plot_timeseries(np.array(measurement.time), voltage, current)
        else:
            # Fallback: plot voltage and current vs index
            self._plot_timeseries_fallback(voltage, current)
        
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
    
    def _plot_timeseries(self, time: np.ndarray, voltage: np.ndarray, current: np.ndarray):
        """
        Plot time series data showing voltage and current over time.
        
        Args:
            time: Time array
            voltage: Voltage array
            current: Current array
        """
        # Use twin axes for voltage and current
        ax1 = self.ax_timeseries
        ax2 = ax1.twinx()
        
        # Plot voltage on left axis
        color1 = '#3498db'
        ax1.plot(time, voltage, color=color1, linewidth=1.5, label='Voltage', alpha=0.8)
        ax1.set_xlabel('Time (s)', fontweight='bold')
        ax1.set_ylabel('Voltage (V)', fontweight='bold', color=color1)
        ax1.tick_params(axis='y', labelcolor=color1)
        ax1.grid(True, alpha=0.3)
        
        # Plot current on right axis
        color2 = '#e74c3c'
        ax2.plot(time, current, color=color2, linewidth=1.5, label='Current', alpha=0.8)
        ax2.set_ylabel('Current (A)', fontweight='bold', color=color2)
        ax2.tick_params(axis='y', labelcolor=color2)
        
        # Set title
        ax1.set_title('Time Series: Voltage & Current', fontweight='bold')
        
        # Add legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='best', fontsize=8)
    
    def _plot_timeseries_fallback(self, voltage: np.ndarray, current: np.ndarray):
        """
        Plot voltage and current vs index when time data is not available.
        
        Args:
            voltage: Voltage array
            current: Current array
        """
        # Use twin axes for voltage and current
        ax1 = self.ax_timeseries
        ax2 = ax1.twinx()
        
        indices = np.arange(len(voltage))
        
        # Plot voltage on left axis
        color1 = '#3498db'
        ax1.plot(indices, voltage, color=color1, linewidth=1.5, label='Voltage', alpha=0.8)
        ax1.set_xlabel('Data Point Index', fontweight='bold')
        ax1.set_ylabel('Voltage (V)', fontweight='bold', color=color1)
        ax1.tick_params(axis='y', labelcolor=color1)
        ax1.grid(True, alpha=0.3)
        
        # Plot current on right axis
        color2 = '#e74c3c'
        ax2.plot(indices, current, color=color2, linewidth=1.5, label='Current', alpha=0.8)
        ax2.set_ylabel('Current (A)', fontweight='bold', color=color2)
        ax2.tick_params(axis='y', labelcolor=color2)
        
        # Set title
        ax1.set_title('Voltage & Current vs Index', fontweight='bold')
        
        # Add legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='best', fontsize=8)
    
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
