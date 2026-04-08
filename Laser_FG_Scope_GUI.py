"""
Laser FG Scope GUI — Standalone Launcher
==========================================
Coordinates:
  • Keithley 4200 SMU  (passive DC bias)
  • Oxxius LBX-405 Laser  (DM1 TTL-gate mode)
  • Siglent SDG1032X  (timing master — fires laser via TTL, triggers scope via SYNC OUT)
  • Tektronix TBS1000C  (oscilloscope — captures device response)

Usage:
    python Laser_FG_Scope_GUI.py

See gui/laser_fg_scope_gui/README.md for wiring and safety information.
"""

import sys
import os

# Ensure the project root is on sys.path when running directly
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import tkinter as tk
from gui.laser_fg_scope_gui import LaserFGScopeGUI

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()           # hide the unused root window

    app = LaserFGScopeGUI(root)
    app.focus_force()

    root.mainloop()
