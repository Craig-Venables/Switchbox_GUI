"""
TSP Testing GUI - Standalone Launcher
=====================================

Shortcut launcher for the Pulse Testing GUI.

Usage:
    python TSP_Testing_GUI.py

Or double-click the file to open the GUI directly.

This file provides a quick way to launch the Pulse Testing GUI
without needing to navigate through other parts of the application.
"""

from __future__ import annotations

import tkinter as tk
import sys
from pathlib import Path

# Add project root to path if needed
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Import from the new location
from gui.pulse_testing_gui import TSPTestingGUI

# Re-export for backward compatibility
__all__ = ['TSPTestingGUI']


def main():
    """Launch the TSP Testing GUI"""
    root = tk.Tk()
    root.withdraw()  # Hide root window
    
    # Create and show the GUI
    app = TSPTestingGUI(root)
    
    # Start the event loop
    root.mainloop()


if __name__ == "__main__":
    main()
