"""
Color themes and styling for device analysis visualization.

This module provides consistent color schemes across the application for:
- Score-based gradients (green → yellow → red)
- Classification badge colors
- Heatmap colormaps
- Status icons
"""

import matplotlib.colors as mcolors
import matplotlib.cm as cm
from typing import Tuple, Dict


# Status icons for device quality indication
STATUS_ICONS: Dict[str, str] = {
    'good': '✓',      # Good quality device (high score, high confidence)
    'uncertain': '⚠',  # Uncertain classification
    'poor': '✗',      # Poor quality device
    'unknown': '?'    # Unknown/no data
}

# Standard plot colors for multi-line plots
PLOT_COLORS = [
    '#1f77b4',  # Blue
    '#ff7f0e',  # Orange
    '#2ca02c',  # Green
    '#d62728',  # Red
    '#9467bd',  # Purple
    '#8c564b',  # Brown
    '#e377c2',  # Pink
    '#7f7f7f',  # Gray
    '#bcbd22',  # Olive
    '#17becf'   # Cyan
]


def score_to_color(score: float, return_hex: bool = True) -> str:
    """
    Convert a score (0-100) to a color on green-yellow-red gradient.
    
    Uses a perceptually smooth gradient:
    - High scores (70-100): Green shades
    - Medium scores (40-70): Yellow/orange shades
    - Low scores (0-40): Red shades
    
    Args:
        score: Score value between 0 and 100
        return_hex: If True, return hex color string; if False, return RGB tuple
        
    Returns:
        Color as hex string (e.g., '#00FF00') or RGB tuple (r, g, b) in 0-1 range
    """
    # Clamp score to valid range
    score = max(0.0, min(100.0, score))
    
    # Normalize to 0-1 range
    normalized_score = score / 100.0
    
    # Use RdYlGn (Red-Yellow-Green) colormap, reversed so green is high
    colormap = cm.get_cmap('RdYlGn')
    rgba_color = colormap(normalized_score)
    
    if return_hex:
        # Convert to hex (ignore alpha channel)
        return mcolors.rgb2hex(rgba_color[:3])
    else:
        # Return RGB tuple
        return rgba_color[:3]


def classification_to_color(classification: str) -> str:
    """
    Get distinct badge color for each device classification type.
    
    Args:
        classification: Device type classification (e.g., 'memristive', 'ohmic')
        
    Returns:
        Hex color string for the classification
    """
    # Normalize classification to lowercase for matching
    classification_lower = classification.lower()
    
    # Classification color mapping
    colors = {
        'memristive': '#3498db',      # Blue
        'ohmic': '#95a5a6',           # Gray
        'capacitive': '#9b59b6',      # Purple
        'memcapacitive': '#e91e63',   # Magenta/Pink
        'conductive': '#e67e22',      # Orange
        'unknown': '#34495e',         # Dark gray
        'linear': '#7f8c8d',          # Light gray
        'nonlinear': '#f39c12',       # Golden
    }
    
    # Return matching color or default to dark gray for unknown types
    return colors.get(classification_lower, '#34495e')


def get_heatmap_colormap(name: str = 'viridis'):
    """
    Get matplotlib colormap for yield heatmap visualization.
    
    Args:
        name: Colormap name ('viridis', 'RdYlGn', 'plasma', etc.)
        
    Returns:
        Matplotlib colormap object
    """
    # For score-based heatmaps, use reversed RdYlGn so green is high
    if name == 'RdYlGn':
        return cm.get_cmap('RdYlGn')
    
    # Otherwise use specified colormap
    return cm.get_cmap(name)


def get_status_color(status: str) -> str:
    """
    Get color for status indicators.
    
    Args:
        status: Status type ('good', 'uncertain', 'poor', 'unknown')
        
    Returns:
        Hex color string
    """
    colors = {
        'good': '#27ae60',       # Green
        'uncertain': '#f39c12',  # Orange
        'poor': '#e74c3c',       # Red
        'unknown': '#95a5a6'     # Gray
    }
    return colors.get(status, '#95a5a6')


def get_feature_color(feature_score: float) -> str:
    """
    Get color for feature score bars (positive/negative contributions).
    
    Args:
        feature_score: Feature score value (can be positive or negative)
        
    Returns:
        Hex color string
    """
    if feature_score > 0:
        # Positive contribution - shades of green
        return '#27ae60'
    elif feature_score < 0:
        # Negative contribution - shades of red
        return '#e74c3c'
    else:
        # Neutral - gray
        return '#95a5a6'


# Dark theme colors for optional dark mode styling
DARK_THEME = {
    'background': '#1e1e1e',
    'foreground': '#ffffff',
    'grid': '#3e3e3e',
    'accent': '#3498db'
}

# Light theme colors (default)
LIGHT_THEME = {
    'background': '#ffffff',
    'foreground': '#000000',
    'grid': '#cccccc',
    'accent': '#3498db'
}
