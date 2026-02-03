"""
Layout Constants – Colors and Fonts
====================================

Shared visual constants for the measurement GUI layout. Sample_GUI-inspired
design with Segoe UI fonts and green accents.
"""

# Color scheme (Sample_GUI style)
COLOR_PRIMARY = "#4CAF50"  # Green for buttons/accents
COLOR_SECONDARY = "#888888"  # Gray for secondary text
COLOR_BG = "#f0f0f0"  # Light grey background
COLOR_BG_INFO = "#f0f0f0"  # Light gray for info boxes
COLOR_SUCCESS = "#4CAF50"  # Green for success states
COLOR_ERROR = "#F44336"  # Red for error states
COLOR_WARNING = "#FFA500"  # Orange for warnings
COLOR_INFO = "#569CD6"  # Blue for info

# Fonts (Sample_GUI style)
FONT_MAIN = ("Segoe UI", 9)
FONT_HEADING = ("Segoe UI", 10, "bold")
FONT_LARGE = ("Segoe UI", 12, "bold")
FONT_BUTTON = ("Segoe UI", 9, "bold")

# Dict exports for easy access
LAYOUT_COLORS = {
    "primary": COLOR_PRIMARY,
    "secondary": COLOR_SECONDARY,
    "bg": COLOR_BG,
    "bg_info": COLOR_BG_INFO,
    "success": COLOR_SUCCESS,
    "error": COLOR_ERROR,
    "warning": COLOR_WARNING,
    "info": COLOR_INFO,
}

LAYOUT_FONTS = {
    "main": FONT_MAIN,
    "heading": FONT_HEADING,
    "large": FONT_LARGE,
    "button": FONT_BUTTON,
}
