"""
Laser power meter equipment.

- PM100D: Thorlabs PM100D power meter (USB/SCPI).
- laser_power_calibration: Load calibration (apparent vs actual power) for use when configuring power.
"""

from .pm100d import (
    PM100D,
    DEFAULT_SERIAL,
    make_pm100d_resource,
    find_pm100d_resource,
)
from .laser_power_calibration import (
    load_calibration,
    get_actual_mw,
    get_setpoint_for_actual_mw,
    get_calibration_table,
)

__all__ = [
    "PM100D",
    "DEFAULT_SERIAL",
    "make_pm100d_resource",
    "find_pm100d_resource",
    "load_calibration",
    "get_actual_mw",
    "get_setpoint_for_actual_mw",
    "get_calibration_table",
]
