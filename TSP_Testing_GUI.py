"""
TSP Testing GUI - Standalone Launcher
=====================================

Shortcut launcher for the Pulse Testing GUI.

Usage:
    python TSP_Testing_GUI.py
    python TSP_Testing_GUI.py --layout compact
    python TSP_Testing_GUI.py --layout classic

Or double-click the file to open the GUI directly (classic layout).

Compact layout shortcut:
    python Pulse_Testing_GUI_compact.py
"""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="Multi-System Pulse Testing GUI")
    parser.add_argument(
        "--layout",
        choices=("classic", "compact"),
        default=None,
        help="UI layout (default: from Json_Files/tsp_gui_config.json or classic)",
    )
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()  # Hide root window

    app = TSPTestingGUI(root, layout=args.layout)

    root.mainloop()


if __name__ == "__main__":
    main()
