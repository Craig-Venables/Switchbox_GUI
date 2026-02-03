"""
Sample GUI – Device Selection and Sample Management
====================================================

Provides the primary interface for device selection, sample configuration, and
multiplexer routing. Users select devices from a visual map, configure sample
parameters, and launch the measurement interface.

Exports:
--------
- SampleGUI: Main window class. Use as ``SampleGUI(root)`` where root is a
  tk.Tk() instance.

Launches:
---------
- MeasurementGUI when user clicks "Start Measurement" with selected devices.
"""

from gui.sample_gui.main import SampleGUI

__all__ = ['SampleGUI']


