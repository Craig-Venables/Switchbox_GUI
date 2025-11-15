"""
Pulse Pattern Visualizer
========================

Visualizes pulse patterns, laser timing, and read operations for pulse testing.
Shows a timeline view of voltage pulses, laser control signals, and measurement windows.

This module provides visualization capabilities for understanding timing relationships
in pulse testing patterns, especially for laser-assisted measurements.

Usage:
------
```python
from Pulse_Testing.pulse_pattern_visualizer import visualize_laser_and_read_pattern

# Quick visualization
timeline = visualize_laser_and_read_pattern(
    read_voltage=0.3,           # V
    read_width=0.5e-6,          # 0.5 µs
    read_period=2.0e-6,         # 2.0 µs
    num_reads=500,
    laser_voltage_high=1.5,     # V
    laser_width=10.0e-6,        # 10 µs
    laser_delay=5.0e-6,         # 5 µs delay
    show_plot=True,
    save_path='pattern.png'
)

# Or use the class directly for more control
from Pulse_Testing.pulse_pattern_visualizer import PulsePatternVisualizer

visualizer = PulsePatternVisualizer()
timeline = visualizer.generate_laser_and_read_pattern(...)
fig = visualizer.plot_pattern(timeline, title="My Pattern")
plt.show()
```
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class SignalSegment:
    """Represents a segment of a signal over time"""
    start_time: float
    end_time: float
    value: float
    label: Optional[str] = None


@dataclass
class PulsePatternTimeline:
    """Container for pulse pattern timeline data"""
    time_points: np.ndarray
    voltage_signal: np.ndarray
    laser_signal: np.ndarray
    read_windows: List[Tuple[float, float]]  # List of (start, end) tuples
    laser_pulses: List[Tuple[float, float]]  # List of (start, end) tuples


class PulsePatternVisualizer:
    """Visualizes pulse patterns with laser timing and read operations"""
    
    def __init__(self, time_resolution: float = 1e-9):
        """
        Initialize visualizer.
        
        Args:
            time_resolution: Time resolution for signal generation (default: 1ns)
        """
        self.time_resolution = time_resolution
    
    def generate_laser_and_read_pattern(
        self,
        read_voltage: float = 0.3,
        read_width: float = 0.5e-6,  # seconds
        read_period: float = 2.0e-6,  # seconds
        num_reads: int = 500,
        laser_voltage_high: float = 1.5,
        laser_voltage_low: float = 0.0,
        laser_width: float = 10.0e-6,  # seconds
        laser_delay: float = 5.0e-6,  # seconds (delay from start)
        laser_rise_time: float = 0.1e-6,  # seconds
        laser_fall_time: float = 0.1e-6,  # seconds
        total_duration: Optional[float] = None
    ) -> PulsePatternTimeline:
        """
        Generate timeline for laser_and_read pattern.
        
        Pattern: CH1 continuous reads, CH2 independent laser pulse
        
        Args:
            read_voltage: CH1 read voltage (V)
            read_width: CH1 read pulse width (s)
            read_period: CH1 read pulse period (s)
            num_reads: Number of read pulses
            laser_voltage_high: CH2 laser pulse voltage (V)
            laser_voltage_low: CH2 baseline voltage (V)
            laser_width: CH2 laser pulse width (s)
            laser_delay: CH2 delay before laser pulse starts (s)
            laser_rise_time: CH2 rise time (s)
            laser_fall_time: CH2 fall time (s)
            total_duration: Total duration to simulate (if None, auto-calculate)
        
        Returns:
            PulsePatternTimeline with signals and timing information
        """
        # Calculate total duration
        if total_duration is None:
            read_duration = num_reads * read_period
            laser_duration = laser_delay + laser_width + laser_fall_time
            total_duration = max(read_duration, laser_duration) * 1.1  # Add 10% margin
        
        # Generate time array
        num_points = int(total_duration / self.time_resolution) + 1
        time_points = np.linspace(0, total_duration, num_points)
        
        # Initialize signals
        voltage_signal = np.zeros_like(time_points)
        laser_signal = np.full_like(time_points, laser_voltage_low)
        
        # Generate read pulses (CH1)
        read_windows = []
        for i in range(num_reads):
            read_start = i * read_period
            read_end = read_start + read_width
            
            # Only process if within time range
            if read_start < total_duration:
                # Find indices for this read pulse
                start_idx = np.searchsorted(time_points, read_start)
                end_idx = np.searchsorted(time_points, read_end)
                
                # Set voltage during read pulse
                if end_idx <= len(voltage_signal):
                    voltage_signal[start_idx:end_idx] = read_voltage
                
                read_windows.append((read_start, read_end))
        
        # Generate laser pulse (CH2)
        laser_pulses = []
        laser_start = laser_delay
        laser_end = laser_start + laser_width
        laser_rise_end = laser_start + laser_rise_time
        laser_fall_start = laser_end - laser_fall_time
        
        if laser_end < total_duration:
            # Find indices for laser pulse segments
            start_idx = np.searchsorted(time_points, laser_start)
            rise_end_idx = np.searchsorted(time_points, laser_rise_end)
            fall_start_idx = np.searchsorted(time_points, laser_fall_start)
            end_idx = np.searchsorted(time_points, laser_end)
            
            # Rise edge (linear ramp)
            if rise_end_idx > start_idx and rise_end_idx <= len(laser_signal):
                num_rise_points = rise_end_idx - start_idx
                if num_rise_points > 0:
                    rise_ramp = np.linspace(laser_voltage_low, laser_voltage_high, num_rise_points)
                    laser_signal[start_idx:rise_end_idx] = rise_ramp
            
            # High plateau
            if fall_start_idx > rise_end_idx and fall_start_idx <= len(laser_signal):
                laser_signal[rise_end_idx:fall_start_idx] = laser_voltage_high
            
            # Fall edge (linear ramp)
            if end_idx > fall_start_idx and end_idx <= len(laser_signal):
                num_fall_points = end_idx - fall_start_idx
                if num_fall_points > 0:
                    fall_ramp = np.linspace(laser_voltage_high, laser_voltage_low, num_fall_points)
                    laser_signal[fall_start_idx:end_idx] = fall_ramp
            
            laser_pulses.append((laser_start, laser_end))
        
        return PulsePatternTimeline(
            time_points=time_points,
            voltage_signal=voltage_signal,
            laser_signal=laser_signal,
            read_windows=read_windows,
            laser_pulses=laser_pulses
        )
    
    def plot_pattern(
        self,
        timeline: PulsePatternTimeline,
        title: str = "Pulse Pattern Visualization",
        show_read_markers: bool = True,
        show_laser_markers: bool = True,
        figsize: Tuple[float, float] = (12, 8),
        save_path: Optional[str] = None
    ) -> Figure:
        """
        Plot pulse pattern timeline.
        
        Args:
            timeline: PulsePatternTimeline to plot
            title: Plot title
            show_read_markers: Show markers for read windows
            show_laser_markers: Show markers for laser pulses
            figsize: Figure size (width, height)
            save_path: Optional path to save figure
        
        Returns:
            matplotlib Figure object
        """
        fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)
        
        time_us = timeline.time_points * 1e6  # Convert to microseconds for display
        
        # Plot 1: Voltage Signal (Read Pulses)
        ax1 = axes[0]
        ax1.plot(time_us, timeline.voltage_signal, 'b-', linewidth=1.5, label='CH1 Read Voltage')
        ax1.fill_between(time_us, 0, timeline.voltage_signal, alpha=0.3, color='blue')
        ax1.set_ylabel('Voltage (V)', fontsize=11, fontweight='bold')
        ax1.set_title('CH1 Read Pulses', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right')
        
        # Mark read windows
        if show_read_markers and timeline.read_windows:
            for read_start, read_end in timeline.read_windows[:10]:  # Show first 10 for clarity
                read_start_us = read_start * 1e6
                read_end_us = read_end * 1e6
                ax1.axvspan(read_start_us, read_end_us, alpha=0.2, color='cyan', label='Read Window' if read_start == timeline.read_windows[0][0] else '')
                # Add vertical markers
                ax1.axvline(read_start_us, color='cyan', linestyle='--', alpha=0.5, linewidth=0.8)
                ax1.axvline(read_end_us, color='cyan', linestyle='--', alpha=0.5, linewidth=0.8)
        
        # Plot 2: Laser Signal
        ax2 = axes[1]
        ax2.plot(time_us, timeline.laser_signal, 'r-', linewidth=2, label='CH2 Laser Control')
        ax2.fill_between(time_us, timeline.laser_signal.min() * 0.1, timeline.laser_signal, 
                        where=(timeline.laser_signal > timeline.laser_signal.min() * 1.1),
                        alpha=0.4, color='red', label='Laser ON')
        ax2.set_ylabel('Voltage (V)', fontsize=11, fontweight='bold')
        ax2.set_title('CH2 Laser Control Signal', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper right')
        
        # Mark laser pulses
        if show_laser_markers and timeline.laser_pulses:
            for laser_start, laser_end in timeline.laser_pulses:
                laser_start_us = laser_start * 1e6
                laser_end_us = laser_end * 1e6
                ax2.axvspan(laser_start_us, laser_end_us, alpha=0.2, color='orange', label='Laser Pulse' if laser_start == timeline.laser_pulses[0][0] else '')
                # Add vertical markers
                ax2.axvline(laser_start_us, color='red', linestyle='--', alpha=0.7, linewidth=1.5)
                ax2.axvline(laser_end_us, color='red', linestyle='--', alpha=0.7, linewidth=1.5)
                # Add annotation
                mid_time = (laser_start_us + laser_end_us) / 2
                duration = laser_end_us - laser_start_us
                ax2.annotate(f'ON\n{duration:.2f} µs', 
                           xy=(mid_time, timeline.laser_signal.max() * 0.5),
                           ha='center', va='center', fontsize=9, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
        
        # Plot 3: Combined View (overlay)
        ax3 = axes[2]
        ax3_voltage = ax3.twinx()
        
        # Plot voltage on left y-axis
        line1 = ax3.plot(time_us, timeline.voltage_signal, 'b-', linewidth=1.5, label='CH1 Read Voltage', alpha=0.7)
        ax3.set_ylabel('Read Voltage (V)', fontsize=11, fontweight='bold', color='blue')
        ax3.tick_params(axis='y', labelcolor='blue')
        
        # Plot laser on right y-axis
        line2 = ax3_voltage.plot(time_us, timeline.laser_signal, 'r-', linewidth=2, label='CH2 Laser Control', alpha=0.8)
        ax3_voltage.set_ylabel('Laser Voltage (V)', fontsize=11, fontweight='bold', color='red')
        ax3_voltage.tick_params(axis='y', labelcolor='red')
        
        ax3.set_xlabel('Time (µs)', fontsize=11, fontweight='bold')
        ax3.set_title('Combined View: Read Pulses & Laser Signal', fontsize=12, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        
        # Combined legend
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax3.legend(lines, labels, loc='upper right')
        
        # Add vertical alignment lines to show timing relationships
        if timeline.laser_pulses and timeline.read_windows:
            # Draw vertical lines at key laser timing points
            for laser_start, laser_end in timeline.laser_pulses:
                laser_start_us = laser_start * 1e6
                laser_end_us = laser_end * 1e6
                for ax in axes:
                    ax.axvline(laser_start_us, color='red', linestyle=':', alpha=0.4, linewidth=1)
                    ax.axvline(laser_end_us, color='red', linestyle=':', alpha=0.4, linewidth=1)
        
        plt.suptitle(title, fontsize=14, fontweight='bold', y=0.995)
        plt.tight_layout(rect=[0, 0, 1, 0.99])
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Figure saved to: {save_path}")
        
        return fig
    
    def visualize_laser_and_read(
        self,
        **params
    ) -> Tuple[PulsePatternTimeline, Figure]:
        """
        Convenience method to generate and plot laser_and_read pattern.
        
        Args:
            **params: Parameters for generate_laser_and_read_pattern
        
        Returns:
            Tuple of (timeline, figure)
        """
        timeline = self.generate_laser_and_read_pattern(**params)
        
        # Create descriptive title
        title = f"Laser and Read Pattern: {params.get('num_reads', 500)} reads, "
        title += f"Laser ON for {params.get('laser_width', 10e-6)*1e6:.2f} µs "
        title += f"@ {params.get('laser_delay', 5e-6)*1e6:.2f} µs delay"
        
        fig = self.plot_pattern(timeline, title=title)
        
        return timeline, fig


# Convenience function for quick visualization
def visualize_laser_and_read_pattern(
    read_voltage: float = 0.3,
    read_width: float = 0.5e-6,
    read_period: float = 2.0e-6,
    num_reads: int = 500,
    laser_voltage_high: float = 1.5,
    laser_voltage_low: float = 0.0,
    laser_width: float = 10.0e-6,
    laser_delay: float = 5.0e-6,
    laser_rise_time: float = 0.1e-6,
    laser_fall_time: float = 0.1e-6,
    show_plot: bool = True,
    save_path: Optional[str] = None
) -> PulsePatternTimeline:
    """
    Quick visualization function for laser_and_read pattern.
    
    Args:
        read_voltage: CH1 read voltage (V)
        read_width: CH1 read pulse width (s)
        read_period: CH1 read pulse period (s)
        num_reads: Number of read pulses
        laser_voltage_high: CH2 laser pulse voltage (V)
        laser_voltage_low: CH2 baseline voltage (V)
        laser_width: CH2 laser pulse width (s)
        laser_delay: CH2 delay before laser pulse starts (s)
        laser_rise_time: CH2 rise time (s)
        laser_fall_time: CH2 fall time (s)
        show_plot: If True, display the plot
        save_path: Optional path to save figure
    
    Returns:
        PulsePatternTimeline object
    """
    visualizer = PulsePatternVisualizer()
    timeline, fig = visualizer.visualize_laser_and_read(
        read_voltage=read_voltage,
        read_width=read_width,
        read_period=read_period,
        num_reads=num_reads,
        laser_voltage_high=laser_voltage_high,
        laser_voltage_low=laser_voltage_low,
        laser_width=laser_width,
        laser_delay=laser_delay,
        laser_rise_time=laser_rise_time,
        laser_fall_time=laser_fall_time
    )
    
    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return timeline


if __name__ == "__main__":
    # Example usage
    timeline = visualize_laser_and_read_pattern(
        read_voltage=0.3,
        read_width=0.5e-6,  # 0.5 µs
        read_period=2.0e-6,  # 2.0 µs
        num_reads=100,  # Show first 100 reads
        laser_voltage_high=1.5,
        laser_voltage_low=0.0,
        laser_width=10.0e-6,  # 10 µs
        laser_delay=5.0e-6,  # 5 µs delay
        laser_rise_time=0.1e-6,  # 0.1 µs
        laser_fall_time=0.1e-6,  # 0.1 µs
        show_plot=True
    )
    
    print(f"\nGenerated pattern with:")
    print(f"  - {len(timeline.read_windows)} read windows")
    print(f"  - {len(timeline.laser_pulses)} laser pulse(s)")
    print(f"  - Total duration: {timeline.time_points[-1]*1e6:.2f} µs")

