"""
Central style for all plotting in the application.
Change dpi, figsize, fonts, or colors here to affect every graph.
"""

from typing import Dict, Tuple

# Default DPI for saved figures (publication-style)
DEFAULT_DPI = 300

# Figsize presets: (width_inches, height_inches)
FIGSIZE_SINGLE = (12, 8)
FIGSIZE_DOUBLE = (14, 6)
FIGSIZE_GRID_2x2 = (14, 10)
FIGSIZE_GRID_2x2_LARGE = (16, 12)
FIGSIZE_GRID_1x3 = (18, 6)
FIGSIZE_DASHBOARD = (18, 12)
FIGSIZE_POLAR = (8, 8)
FIGSIZE_LEADERBOARD = (12, 8)  # height scales with device count
FIGSIZE_HEATMAP = (12, 10)
FIGSIZE_SCATTER = (12, 10)
FIGSIZE_BAR = (12, 6)  # height can scale with number of bars

# Font sizes
FONT_AXIS = 9
FONT_TITLE = 11
FONT_TICKS = 8
FONT_LEGEND = 8
FONT_SUPTITLE = 12


def get_dpi() -> int:
    """Default DPI for saving figures."""
    return DEFAULT_DPI


def get_figsize(name: str) -> Tuple[float, float]:
    """Return (width, height) for a named preset."""
    presets: Dict[str, Tuple[float, float]] = {
        "single": FIGSIZE_SINGLE,
        "double": FIGSIZE_DOUBLE,
        "grid_2x2": FIGSIZE_GRID_2x2,
        "grid_2x2_large": FIGSIZE_GRID_2x2_LARGE,
        "grid_1x3": FIGSIZE_GRID_1x3,
        "dashboard": FIGSIZE_DASHBOARD,
        "polar": FIGSIZE_POLAR,
        "leaderboard": FIGSIZE_LEADERBOARD,
        "heatmap": FIGSIZE_HEATMAP,
        "scatter": FIGSIZE_SCATTER,
        "bar": FIGSIZE_BAR,
    }
    return presets.get(name, FIGSIZE_SINGLE)


def get_font_sizes() -> Dict[str, int]:
    """Return dict of axis, title, ticks, legend, suptitle font sizes."""
    return {
        "axis": FONT_AXIS,
        "title": FONT_TITLE,
        "ticks": FONT_TICKS,
        "legend": FONT_LEGEND,
        "suptitle": FONT_SUPTITLE,
    }
