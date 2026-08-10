"""
2450 TSP Pulse GUI — standalone entry point
===========================================

Keithley 2450 pulse testing over TSP (USB) with optional Oxxius laser.

Usage (from repo root):
    python tools/tsp_gui/main.py

Requirements:
    - 2450 front-panel Command Set = TSP
    - USB VISA connection
    - Optional: Oxxius laser on a COM port
"""

from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap: tools/tsp_gui -> repo root on sys.path for Equipment / Pulse_Testing
_TOOL_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _TOOL_ROOT.parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# Allow `from app...` when running this file directly
if str(_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOL_ROOT))


def main() -> None:
    import tkinter as tk
    from app.gui import TSP2450App

    root = tk.Tk()
    app = TSP2450App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
