"""
Utilities module for Device Analysis Visualizer.

This module provides utility functions and constants for plotting and styling.
It includes matplotlib/Qt5 integration helpers and color schemes for consistent
visualization across the application.
"""

from .plot_utils import (
    create_mpl_canvas,
    create_mpl_toolbar,
    plot_iv_curve,
    plot_hysteresis_with_cycles,
    plot_resistance_vs_voltage,
    plot_metrics_radar,
    plot_score_breakdown,
    style_plot_for_dark_theme
)
from .color_themes import (
    score_to_color,
    classification_to_color,
    get_heatmap_colormap,
    STATUS_ICONS,
    PLOT_COLORS
)

__all__ = [
    'create_mpl_canvas',
    'create_mpl_toolbar',
    'plot_iv_curve',
    'plot_hysteresis_with_cycles',
    'plot_resistance_vs_voltage',
    'plot_metrics_radar',
    'plot_score_breakdown',
    'style_plot_for_dark_theme',
    'score_to_color',
    'classification_to_color',
    'get_heatmap_colormap',
    'STATUS_ICONS',
    'PLOT_COLORS'
]
