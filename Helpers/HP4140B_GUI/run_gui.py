"""
Simple launcher script for HP4140B GUI

This script can be run directly to launch the HP4140B GUI.
It handles import paths to work both standalone and from the project root.

Usage:
    python run_gui.py
    OR
    python hp4140b_gui.py
"""

import sys
from pathlib import Path

# Add current directory to path to ensure local imports work
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import and run the GUI
from hp4140b_gui import main

if __name__ == "__main__":
    main()

