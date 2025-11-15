"""
Sample GUI - Compatibility Wrapper

This file provides backward compatibility by importing from the new
location at gui.sample_gui.main.

All functionality is now provided by gui.sample_gui.main.SampleGUI.
"""

from __future__ import annotations

# Import from the new location
from gui.sample_gui import SampleGUI

# Re-export for backward compatibility
__all__ = ['SampleGUI']
