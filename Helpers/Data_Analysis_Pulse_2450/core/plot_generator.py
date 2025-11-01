"""
Plot Generator

Generates matplotlib plots for different TSP test types.
Handles data visualization, styling, and comparison.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .data_parser import TSPData
from .test_type_registry import get_registry


class PlotStyle:
    """Plot styling configuration"""
    
    # Default colors (colorblind-friendly palette)
    COLORS = [
        '#1f77b4',  # blue
        '#ff7f0e',  # orange
        '#2ca02c',  # green
        '#d62728',  # red
        '#9467bd',  # purple
        '#8c564b',  # brown
        '#e377c2',  # pink
        '#7f7f7f',  # gray
        '#bcbd22',  # olive
        '#17becf',  # cyan
    ]
    
    # Line styles
    LINE_STYLES = ['-', '--', '-.', ':']
    
    # Markers
    MARKERS = ['o', 's', '^', 'v', 'D', 'p', '*', 'h']
    
    def __init__(self):
        self.line_width = 2
        self.marker_size = 6
        self.grid = True
        self.legend = True
        self.grid_alpha = 0.3
        self.font_size = 10
        self.title_size = 12
        self.label_size = 11
        
        # Dark theme colors
        self.bg_color = '#2b2b2b'
        self.text_color = '#e0e0e0'
        self.grid_color = '#555555'
    
    def apply_to_figure(self, fig: Figure):
        """Apply dark theme to figure"""
        fig.patch.set_facecolor(self.bg_color)
    
    def apply_to_axes(self, ax: Axes):
        """Apply dark theme to axes"""
        ax.set_facecolor(self.bg_color)
        ax.tick_params(colors=self.text_color, labelsize=self.font_size)
        ax.spines['bottom'].set_color(self.text_color)
        ax.spines['top'].set_color(self.text_color)
        ax.spines['left'].set_color(self.text_color)
        ax.spines['right'].set_color(self.text_color)
        
        if self.grid:
            ax.grid(True, alpha=self.grid_alpha, color=self.grid_color)
        
        # Set label colors
        ax.xaxis.label.set_color(self.text_color)
        ax.yaxis.label.set_color(self.text_color)
        ax.title.set_color(self.text_color)
        
        # Set label sizes
        ax.xaxis.label.set_size(self.label_size)
        ax.yaxis.label.set_size(self.label_size)
        ax.title.set_size(self.title_size)


class PlotGenerator:
    """Generates plots for TSP data"""
    
    def __init__(self, style: Optional[PlotStyle] = None):
        self.style = style or PlotStyle()
        self.registry = get_registry()
    
    def create_figure(self, figsize: Tuple[int, int] = (10, 6)) -> Tuple[Figure, Axes]:
        """Create a new figure with dark theme"""
        fig, ax = plt.subplots(figsize=figsize)
        self.style.apply_to_figure(fig)
        self.style.apply_to_axes(ax)
        return fig, ax
    
    def plot_single(self, data: TSPData, fig: Optional[Figure] = None, 
                   ax: Optional[Axes] = None, color: Optional[str] = None,
                   label: Optional[str] = None) -> Tuple[Figure, Axes]:
        """
        Plot a single TSP dataset.
        
        Args:
            data: TSPData object
            fig: Existing figure (optional)
            ax: Existing axes (optional)
            color: Line color (optional)
            label: Legend label (optional)
        
        Returns:
            Figure and Axes objects
        """
        if fig is None or ax is None:
            fig, ax = self.create_figure()
        
        # Get plot type for this test
        plot_type = self.registry.get_plot_type(data.test_name)
        
        # Default label
        if label is None:
            label = data.get_display_name()
        
        # Default color
        if color is None:
            color = self.style.COLORS[0]
        
        # Generate appropriate plot based on type
        if plot_type == 'time_series':
            self._plot_time_series(ax, data, color, label)
        elif plot_type == 'width_vs_resistance':
            self._plot_width_sweep(ax, data, color, label)
        elif plot_type == 'pot_dep_cycle':
            self._plot_potentiation_depression(ax, data, color, label)
        elif plot_type == 'endurance':
            self._plot_endurance(ax, data, color, label)
        elif plot_type == 'relaxation_reads':
            self._plot_relaxation_reads(ax, data, color, label)
        elif plot_type == 'relaxation_all':
            self._plot_relaxation_all(ax, data, color, label)
        elif plot_type == 'range_finder':
            self._plot_range_finder(ax, data, color, label)
        elif plot_type == 'iv_sweep' or 'IV Sweep' in data.test_name:
            self._plot_iv_sweep(ax, data, color, label)
        else:
            # Default to time series
            self._plot_time_series(ax, data, color, label)
        
        if self.style.legend:
            legend = ax.legend(facecolor=self.style.bg_color, 
                             edgecolor=self.style.text_color,
                             labelcolor=self.style.text_color)
            legend.get_frame().set_alpha(0.9)
        
        fig.tight_layout()
        return fig, ax
    
    def plot_multiple(self, datasets: List[TSPData], 
                     figsize: Tuple[int, int] = (12, 7)) -> Tuple[Figure, Axes]:
        """
        Plot multiple datasets for comparison.
        
        Args:
            datasets: List of TSPData objects
            figsize: Figure size
        
        Returns:
            Figure and Axes objects
        """
        fig, ax = self.create_figure(figsize=figsize)
        
        for i, data in enumerate(datasets):
            color = self.style.COLORS[i % len(self.style.COLORS)]
            label = data.get_display_name()
            
            # Get key parameters for label
            key_params = data.get_key_parameters()
            if key_params:
                label += f" ({key_params})"
            
            self.plot_single(data, fig, ax, color, label)
        
        return fig, ax
    
    def _plot_time_series(self, ax: Axes, data: TSPData, color: str, label: str):
        """Plot time series (Timestamp vs Resistance)"""
        ax.plot(data.timestamps, data.resistances, 
               color=color, linewidth=self.style.line_width,
               marker='o', markersize=self.style.marker_size,
               label=label, markevery=max(1, len(data.timestamps)//50))
        
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Resistance (Ω)')
        ax.set_title(f'{data.test_name}')
        
        # Use log scale if resistance spans multiple orders of magnitude
        if len(data.resistances) > 0:
            r_min, r_max = np.nanmin(data.resistances), np.nanmax(data.resistances)
            if r_max / r_min > 100:
                ax.set_yscale('log')
    
    def _plot_width_sweep(self, ax: Axes, data: TSPData, color: str, label: str):
        """Plot width sweep (Pulse Width vs Resistance)"""
        # Extract pulse widths
        if 'Pulse Widths' in data.additional_data:
            pulse_widths = data.additional_data['Pulse Widths']
            
            # Group by pulse width
            unique_widths = np.unique(pulse_widths)
            
            for i, width in enumerate(unique_widths):
                mask = pulse_widths == width
                times = data.timestamps[mask]
                resistances = data.resistances[mask]
                
                if i == 0:
                    ax.plot(times, resistances, 
                           color=color, linewidth=self.style.line_width,
                           marker='o', markersize=self.style.marker_size,
                           label=label)
                else:
                    ax.plot(times, resistances, 
                           color=color, linewidth=self.style.line_width,
                           marker='o', markersize=self.style.marker_size)
            
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Resistance (Ω)')
            ax.set_title(f'{data.test_name} - Width Sweep')
        else:
            # Fallback to time series
            self._plot_time_series(ax, data, color, label)
    
    def _plot_potentiation_depression(self, ax: Axes, data: TSPData, color: str, label: str):
        """Plot potentiation-depression cycle"""
        # Check if Phase column exists
        if 'Phase' in data.additional_data:
            phases = data.additional_data['Phase']
            
            # Separate phases
            pot_mask = phases == 'Potentiation'
            dep_mask = phases == 'Depression'
            
            # Plot potentiation
            if np.any(pot_mask):
                pot_times = data.timestamps[pot_mask]
                pot_res = data.resistances[pot_mask]
                ax.plot(pot_times, pot_res,
                       color=color, linewidth=self.style.line_width,
                       marker='o', markersize=self.style.marker_size,
                       label=f'{label} (LRS→HRS)', markevery=max(1, len(pot_times)//30))
            
            # Plot depression
            if np.any(dep_mask):
                dep_times = data.timestamps[dep_mask]
                dep_res = data.resistances[dep_mask]
                # Slightly different color
                dep_color = self.style.COLORS[(self.style.COLORS.index(color) + 1) % len(self.style.COLORS)]
                ax.plot(dep_times, dep_res,
                       color=dep_color, linewidth=self.style.line_width,
                       marker='s', markersize=self.style.marker_size,
                       label=f'{label} (HRS→LRS)', markevery=max(1, len(dep_times)//30))
        else:
            # Fallback to time series
            self._plot_time_series(ax, data, color, label)
        
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Resistance (Ω)')
        ax.set_title('Potentiation-Depression Cycle')
    
    def _plot_endurance(self, ax: Axes, data: TSPData, color: str, label: str):
        """Plot endurance test (Cycle Number vs Resistance)"""
        if 'Cycle Number' in data.additional_data:
            cycle_numbers = data.additional_data['Cycle Number']
            ax.plot(cycle_numbers, data.resistances,
                   color=color, linewidth=self.style.line_width,
                   marker='o', markersize=self.style.marker_size,
                   label=label, markevery=max(1, len(cycle_numbers)//50))
            
            ax.set_xlabel('Cycle Number')
            ax.set_ylabel('Resistance (Ω)')
            ax.set_title('Endurance Test')
            ax.set_yscale('log')
        else:
            self._plot_time_series(ax, data, color, label)
    
    def _plot_relaxation_reads(self, ax: Axes, data: TSPData, color: str, label: str):
        """Plot relaxation after multi-pulse (only reads)"""
        # Plot time series with focus on read phase
        self._plot_time_series(ax, data, color, label)
        ax.set_title('Relaxation After Multi-Pulse (Reads Only)')
    
    def _plot_relaxation_all(self, ax: Axes, data: TSPData, color: str, label: str):
        """Plot relaxation after multi-pulse (pulses + reads)"""
        self._plot_time_series(ax, data, color, label)
        ax.set_title('Relaxation After Multi-Pulse (All Measurements)')
    
    def _plot_range_finder(self, ax: Axes, data: TSPData, color: str, label: str):
        """Plot current range finder"""
        ax.plot(data.measurement_numbers, np.abs(data.currents),
               color=color, linewidth=self.style.line_width,
               marker='o', markersize=self.style.marker_size,
               label=label)
        
        ax.set_xlabel('Measurement Number')
        ax.set_ylabel('|Current| (A)')
        ax.set_title('Current Range Finder')
        ax.set_yscale('log')
    
    def _plot_iv_sweep(self, ax: Axes, data: TSPData, color: str, label: str):
        """Plot IV sweep/hysteresis (Voltage vs Current)"""
        # Plot Voltage vs Current (hysteresis loop)
        ax.plot(data.voltages, data.currents,
               color=color, linewidth=self.style.line_width,
               marker='o', markersize=self.style.marker_size,
               label=label, markevery=max(1, len(data.voltages)//50))
        
        ax.set_xlabel('Voltage (V)')
        ax.set_ylabel('Current (A)')
        ax.set_title('IV Hysteresis Loop')
        ax.axhline(y=0, color='#666', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.axvline(x=0, color='#666', linestyle='--', linewidth=0.5, alpha=0.5)
    
    def save_figure(self, fig: Figure, filepath: Path, dpi: int = 300):
        """Save figure to file"""
        fig.savefig(filepath, dpi=dpi, facecolor=fig.get_facecolor(),
                   edgecolor='none', bbox_inches='tight')


# Module test
if __name__ == "__main__":
    print("Plot Generator - Module Test")
    print("=" * 60)
    
    from .data_parser import parse_tsp_file
    
    # Test with example file (if available)
    test_file = Path("../../Data_save_loc")
    if test_file.exists():
        txt_files = list(test_file.rglob("*.txt"))
        txt_files = [f for f in txt_files if not f.name.startswith("tsp_test_log")][:1]
        
        if txt_files:
            print(f"\nTesting with: {txt_files[0].name}")
            data = parse_tsp_file(txt_files[0])
            
            if data:
                generator = PlotGenerator()
                fig, ax = generator.plot_single(data)
                
                # Save test plot
                output_file = Path("test_plot.png")
                generator.save_figure(fig, output_file)
                print(f"✓ Test plot saved: {output_file}")
                plt.close(fig)
            else:
                print("✗ Failed to parse file")
        else:
            print("No test files found")
    else:
        print("Test data directory not found")

