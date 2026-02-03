"""
Measurement GUI - Compatibility Wrapper

This file provides backward compatibility by importing from the new
location at gui.measurement_gui.main.

All functionality is now provided by gui.measurement_gui.main.MeasurementGUI.
"""

from __future__ import annotations

# Import from the new location
from gui.measurement_gui import MeasurementGUI

# Re-export for backward compatibility
__all__ = ['MeasurementGUI']
