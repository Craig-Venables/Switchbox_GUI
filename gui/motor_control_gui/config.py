"""
Motor Control GUI Configuration
===============================

GUI constants, colors, defaults, and predefined connection options.
Hardware constants (velocity, acceleration, VISA addresses) come from
Equipment.Motor_Controll.config.
"""

from __future__ import annotations

from pathlib import Path

# Re-export hardware config for convenience
import Equipment.Motor_Controll.config as _hw_config  # noqa: F401

COLORS = {
    "bg_dark": "#f0f0f0",
    "bg_medium": "#f0f0f0",
    "bg_light": "#ffffff",
    "fg_primary": "#000000",
    "fg_secondary": "#888888",
    "accent_blue": "#569CD6",
    "accent_green": "#4CAF50",
    "accent_red": "#F44336",
    "accent_yellow": "#FFA500",
    "grid_light": "#cccccc",
    "grid_dark": "#999999",
}

PRESETS_FILE = Path("motor_presets.json")

DEFAULT_CANVAS_SIZE = 500
DEFAULT_WORLD_RANGE = 25.0
DEFAULT_AMPLITUDE = 0.4

# Predefined FG VISA addresses
FG_ADDRESSES = [
    "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR",
    _hw_config.LASER_USB,
    "USB0::0xF4EC::0x1103::INSTR",
    "TCPIP0::192.168.1.100::INSTR",
]

# Predefined laser port/baud combinations
LASER_CONFIGS = [
    {"port": "COM4", "baud": "19200"},
    {"port": "COM4", "baud": "38400"},
    {"port": "COM3", "baud": "38400"},
    {"port": "COM3", "baud": "19200"},
    {"port": "COM5", "baud": "38400"},
    {"port": "COM5", "baud": "19200"},
]
