"""
Measurement GUI – Main Measurement Interface
=============================================

Main interface for IV/PMU/SMU measurements on device arrays. Provides instrument
connection management, sweep configuration, real-time plotting, and data saving.
Typically launched from Sample GUI when the user starts a measurement.

Exports:
--------
- MeasurementGUI: Main window class. Requires sample_type, section, device_list,
  and optionally sample_gui reference.

Components:
-----------
- layout_builder:  Tabbed UI construction
- plot_panels:     Real-time plotting widgets
- plot_updaters:   Plot update logic
"""

from gui.measurement_gui.main import MeasurementGUI

__all__ = ['MeasurementGUI']


