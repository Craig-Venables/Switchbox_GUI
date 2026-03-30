"""
TSP Data Analysis Tool - Main Entry Point

A PyQt6-based application for analyzing and plotting Keithley 2450 TSP pulse test data.

Usage:
    python main.py
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from gui.main_window import MainWindow


def main():
    """Main entry point"""
    # Create application
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("TSP Data Analysis Tool")
    app.setOrganizationName("TSP_Analysis")
    app.setOrganizationDomain("tsp-analysis.local")
    
    # Set style
    app.setStyle("Fusion")
    
    # Enable high DPI scaling
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    print("=" * 60)
    print("TSP Data Analysis Tool")
    print("=" * 60)
    print("\nStarting application...")
    print("Loading modules...")
    
    try:
        main()
    except Exception as e:
        print(f"\nERROR: Application failed to start")
        print(f"Reason: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

