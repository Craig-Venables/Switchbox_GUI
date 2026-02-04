"""
Oscilloscope Pulse GUI Configuration
====================================

GUI constants, colors, and style defaults. Persisted config (pulse_voltage, etc.)
is managed by ConfigManager and pulse_gui_config.json.
"""

from __future__ import annotations

COLORS = {
    "bg": "#f0f0f0",
    "accent": "#e6f3ff",
    "header": "#1565c0",
    "fg_secondary": "#555",
    "fg_status": "#333333",
    "warning_bg": "#fff3cd",
    "warning_fg": "#856404",
    "error_fg": "#d32f2f",
    "success_fg": "#1b5e20",
    "tooltip_bg": "#ffffe0",
}

# Default theme and font
THEME = "clam"
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 9
FONT_HEADER_SIZE = 11
FONT_SMALL = 8
