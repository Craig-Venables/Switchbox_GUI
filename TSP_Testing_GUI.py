"""
TSP Testing GUI - Compatibility Wrapper

This file provides backward compatibility by importing from the new
location at gui.pulse_testing_gui.main.

All functionality is now provided by gui.pulse_testing_gui.main.TSPTestingGUI.

This wrapper is kept for standalone testing purposes. To run the GUI standalone:
    python -c "from TSP_Testing_GUI import TSPTestingGUI; import tkinter as tk; root = tk.Tk(); root.withdraw(); app = TSPTestingGUI(root); root.mainloop()"

Or use the wrapper directly:
    from TSP_Testing_GUI import TSPTestingGUI
"""

from __future__ import annotations

# Import from the new location
from gui.pulse_testing_gui import TSPTestingGUI

# Re-export for backward compatibility
__all__ = ['TSPTestingGUI']
