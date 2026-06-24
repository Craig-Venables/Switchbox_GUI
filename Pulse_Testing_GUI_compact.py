"""
Pulse Testing GUI — Compact Layout Launcher
===========================================

Launches the simplified compact pulse testing UI.

Usage:
    python Pulse_Testing_GUI_compact.py

Classic layout (unchanged):
    python TSP_Testing_GUI.py
"""

from __future__ import annotations

import tkinter as tk
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from gui.pulse_testing_gui import TSPTestingGUI


def main():
    root = tk.Tk()
    root.withdraw()
    app = TSPTestingGUI(root, layout="compact")
    root.mainloop()


if __name__ == "__main__":
    main()
