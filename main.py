"""
Switchbox GUI – Main Entry Point
================================

Launches the Sample GUI (device selection and sample management).

Usage:
    python main.py
"""

import tkinter as tk
from gui.sample_gui import SampleGUI


if __name__ == "__main__":
    import multiprocessing
    import sys

    multiprocessing.freeze_support()
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
