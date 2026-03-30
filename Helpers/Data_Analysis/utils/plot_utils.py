"""
Matplotlib/Qt5 integration utilities for plotting.

This module provides helper functions for creating matplotlib plots and
embedding them in Qt5 widgets using FigureCanvasQTAgg.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from typing import Optional, List, Dict, Any, Tuple
from PyQt5.QtWidgets import QWidget


def create_mpl_canvas(parent: Optional[QWidget] = None, 
                      figure: Optional[Figure] = None,
                      dpi: int = 100) -> FigureCanvasQTAgg:
    """
    Create a matplotlib canvas widget for Qt5 integration.
    
    Args:
        parent: Parent Qt widget
        figure: Existing matplotlib Figure, or None to create new one
        dpi: DPI for the figure
        
    Returns:
        FigureCanvasQTAgg widget containing the matplotlib figure
    """
    if figure is None:
        figure = Figure(figsize=(8, 6), dpi=dpi)
    
    canvas = FigureCanvasQTAgg(figure)
    canvas.setParent(parent)
    
    return canvas


def create_mpl_toolbar(canvas: FigureCanvasQTAgg, 
                       parent: QWidget) -> NavigationToolbar2QT:
    """
    Create matplotlib navigation toolbar for a canvas.
    
    Args:
        canvas: FigureCanvasQTAgg widget
        parent: Parent Qt widget
        
    Returns:
        NavigationToolbar2QT widget
    """
    toolbar = NavigationToolbar2QT(canvas, parent)
    return toolbar


def plot_iv_curve(ax: Axes, 
                  voltage: np.ndarray, 
                  current: np.ndarray,
                  label: str = "I-V Curve",
                  color: Optional[str] = None,
                  linewidth: float = 1.5,
                  **kwargs) -> None:
    """
    Plot standard I-V curve on given axes.
    
    Args:
        ax: Matplotlib axes to plot on
        voltage: Voltage array
        current: Current array
        label: Line label for legend
        color: Line color (hex or name), None for auto
        linewidth: Line width
        **kwargs: Additional arguments passed to ax.plot()
    """
    ax.plot(voltage, current, label=label, color=color, linewidth=linewidth, **kwargs)
    ax.set_xlabel('Voltage (V)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Current (A)', fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='best', framealpha=0.9)


def plot_hysteresis_with_cycles(ax: Axes,
                                voltage: np.ndarray,
                                current: np.ndarray,
                                cycles: Optional[List[Tuple[int, int]]] = None,
                                colors: Optional[List[str]] = None) -> None:
    """
    Plot I-V hysteresis with multiple cycle overlays.
    
    Args:
        ax: Matplotlib axes to plot on
        voltage: Voltage array
        current: Current array
        cycles: List of (start_idx, end_idx) tuples for each cycle
        colors: List of colors for each cycle (optional)
    """
    if cycles is None or len(cycles) == 0:
        # Plot as single curve
        plot_iv_curve(ax, voltage, current, label="Hysteresis Loop")
    else:
        # Plot each cycle separately
        from .color_themes import PLOT_COLORS
        
        if colors is None:
            colors = PLOT_COLORS
        
        for i, (start, end) in enumerate(cycles):
            v_cycle = voltage[start:end]
            i_cycle = current[start:end]
            color = colors[i % len(colors)]
            ax.plot(v_cycle, i_cycle, label=f"Cycle {i+1}", 
                   color=color, linewidth=1.5, alpha=0.8)
    
    ax.set_xlabel('Voltage (V)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Current (A)', fontsize=11, fontweight='bold')
    ax.set_title('I-V Hysteresis', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='best', framealpha=0.9, fontsize=9)
    
    # Add zero lines for reference
    ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5, alpha=0.5)
    ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5, alpha=0.5)


def plot_resistance_vs_voltage(ax: Axes,
                               voltage: np.ndarray,
                               current: np.ndarray,
                               log_scale: bool = True,
                               min_current: float = 1e-12) -> None:
    """
    Plot resistance vs voltage (R = V/I).
    
    Args:
        ax: Matplotlib axes to plot on
        voltage: Voltage array
        current: Current array
        log_scale: Use log scale for resistance axis
        min_current: Minimum current threshold to avoid division by zero
    """
    # Calculate resistance, avoiding division by very small currents
    with np.errstate(divide='ignore', invalid='ignore'):
        resistance = np.abs(voltage) / np.abs(current)  # Use absolute values
    
    # Filter out invalid values (infinite, NaN, too small currents)
    valid_mask = (np.abs(current) > min_current) & np.isfinite(resistance)
    v_valid = voltage[valid_mask]
    r_valid = resistance[valid_mask]
    
    if len(v_valid) > 0:
        ax.plot(v_valid, r_valid, color='#3498db', linewidth=1.5, marker='.', 
               markersize=3, alpha=0.7)
        
        ax.set_xlabel('Voltage (V)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Resistance (Ω)', fontsize=11, fontweight='bold')
        ax.set_title('Resistance vs Voltage', fontsize=12, fontweight='bold')
        
        if log_scale:
            ax.set_yscale('log')
        
        ax.grid(True, alpha=0.3, linestyle='--', which='both')
    else:
        ax.text(0.5, 0.5, 'No valid resistance data', 
               ha='center', va='center', transform=ax.transAxes)


def plot_metrics_radar(ax: Axes, metrics_dict: Dict[str, float]) -> None:
    """
    Create radar chart for multi-metric comparison.
    
    Args:
        ax: Matplotlib axes (must be polar projection)
        metrics_dict: Dictionary of metric names and normalized values (0-1)
    """
    if len(metrics_dict) == 0:
        ax.text(0.5, 0.5, 'No metrics available', 
               ha='center', va='center', transform=ax.transAxes)
        return
    
    # Prepare data
    categories = list(metrics_dict.keys())
    values = list(metrics_dict.values())
    
    # Ensure values are in 0-1 range
    values = [max(0, min(1, v)) for v in values]
    
    # Number of variables
    N = len(categories)
    
    # Compute angle for each axis
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    
    # Complete the circle
    values += values[:1]
    angles += angles[:1]
    
    # Plot
    ax.plot(angles, values, 'o-', linewidth=2, color='#3498db')
    ax.fill(angles, values, alpha=0.25, color='#3498db')
    
    # Fix axis to go in the right order
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=9)
    
    # Set y-axis limits
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(['25%', '50%', '75%', '100%'], fontsize=8)
    
    ax.grid(True, alpha=0.3)
    ax.set_title('Metrics Radar', fontsize=12, fontweight='bold', pad=20)


def plot_score_breakdown(ax: Axes, score_dict: Dict[str, float]) -> None:
    """
    Create horizontal bar chart for classification score breakdown.
    
    Args:
        ax: Matplotlib axes to plot on
        score_dict: Dictionary of feature names and their score contributions
    """
    if len(score_dict) == 0:
        ax.text(0.5, 0.5, 'No score data available', 
               ha='center', va='center', transform=ax.transAxes)
        return
    
    # Sort by absolute value
    sorted_items = sorted(score_dict.items(), key=lambda x: abs(x[1]), reverse=True)
    features = [item[0] for item in sorted_items]
    scores = [item[1] for item in sorted_items]
    
    # Color bars based on positive/negative contribution
    from .color_themes import get_feature_color
    colors = [get_feature_color(score) for score in scores]
    
    # Create horizontal bar chart
    y_pos = np.arange(len(features))
    ax.barh(y_pos, scores, color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(features, fontsize=9)
    ax.set_xlabel('Score Contribution', fontsize=11, fontweight='bold')
    ax.set_title('Classification Score Breakdown', fontsize=12, fontweight='bold')
    
    # Add zero line
    ax.axvline(x=0, color='k', linestyle='-', linewidth=1)
    ax.grid(True, alpha=0.3, axis='x', linestyle='--')
    
    # Invert y-axis so highest scores are at top
    ax.invert_yaxis()


def style_plot_for_dark_theme(ax: Axes) -> None:
    """
    Apply dark theme styling to a matplotlib axes.
    
    Args:
        ax: Matplotlib axes to style
    """
    from .color_themes import DARK_THEME
    
    ax.set_facecolor(DARK_THEME['background'])
    ax.spines['bottom'].set_color(DARK_THEME['foreground'])
    ax.spines['top'].set_color(DARK_THEME['foreground'])
    ax.spines['left'].set_color(DARK_THEME['foreground'])
    ax.spines['right'].set_color(DARK_THEME['foreground'])
    ax.tick_params(colors=DARK_THEME['foreground'])
    ax.xaxis.label.set_color(DARK_THEME['foreground'])
    ax.yaxis.label.set_color(DARK_THEME['foreground'])
    ax.title.set_color(DARK_THEME['foreground'])
    
    # Update grid color
    ax.grid(True, alpha=0.2, color=DARK_THEME['grid'])
