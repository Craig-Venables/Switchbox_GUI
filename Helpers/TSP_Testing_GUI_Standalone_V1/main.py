"""
TSP Testing GUI - Standalone Entry Point
==========================================

This is the main entry point for running the TSP Testing GUI as a standalone application.
Run this file to launch the GUI for Keithley 2450 TSP pulse testing.

Usage:
    python main.py

Requirements:
    - Keithley 2450 SourceMeter in TSP mode
    - Python 3.7+ with required packages (see requirements.txt)
    - PyVISA for instrument communication

Author: Standalone version extracted from main project
Date: 2025-10-31
"""

import tkinter as tk
from gui.pulse_testing_gui import TSPTestingGUI


def main():
    """Main entry point for standalone TSP Testing GUI."""
    # Create root window
    root = tk.Tk()
    root.withdraw()  # Hide root window
    
    # Create and show TSP Testing GUI
    app = TSPTestingGUI(root)
    
    # Start main event loop
    root.mainloop()


if __name__ == "__main__":
    main()

