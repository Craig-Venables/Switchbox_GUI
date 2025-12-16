"""
Main entry point for Classification Validation Tool.

Run this script to launch the GUI for testing and refining classification parameters.
"""

import tkinter as tk
import sys
from pathlib import Path

# Add project root to path if needed
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from Helpers.Classification_Validation.gui.main_window import ValidationToolGUI


def main():
    """Launch the validation tool GUI."""
    root = tk.Tk()
    root.geometry("1200x800")
    
    app = ValidationToolGUI(root)
    app.run()


if __name__ == "__main__":
    main()
