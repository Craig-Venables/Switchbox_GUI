"""
Device Analysis Visualizer - Main Application Entry Point

Standalone Qt5 application for visualizing device analysis data.

Usage:
    # From command line
    python device_visualizer_app.py [--sample /path/to/sample]
    
    # From Python code
    from tools.device_visualizer import launch_visualizer
    launch_visualizer(sample_path='/path/to/sample')
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import QApplication

# Handle both direct execution and module import
try:
    from .widgets.main_window import MainWindow
except ImportError:
    # Running as script, add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from Data_Analysis.widgets.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def launch_visualizer(sample_path: Optional[str] = None) -> int:
    """
    Launch the Device Analysis Visualizer application.
    
    This is the main entry point for the application. It creates the Qt
    application instance, initializes the main window, and optionally
    loads a sample if provided.
    
    Args:
        sample_path: Optional path to sample folder to auto-load
        
    Returns:
        Application exit code (0 for success)
        
    Example:
        >>> from tools.device_visualizer import launch_visualizer
        >>> launch_visualizer('/path/to/my/sample')
    """
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Device Analysis Visualizer")
    app.setOrganizationName("Switchbox GUI")
    
    # Set application style
    app.setStyle('Fusion')  # Modern cross-platform style
    
    # Create main window
    logger.info("Initializing Device Analysis Visualizer...")
    main_window = MainWindow()
    main_window.show()
    
    # Auto-load sample if provided
    if sample_path:
        sample_path_obj = Path(sample_path)
        if sample_path_obj.exists():
            logger.info(f"Auto-loading sample: {sample_path}")
            main_window.sample_selector.set_sample(sample_path)
        else:
            logger.warning(f"Sample path does not exist: {sample_path}")
    
    # Enter Qt event loop
    logger.info("Application started")
    exit_code = app.exec_()
    
    logger.info(f"Application exited with code {exit_code}")
    return exit_code


def main():
    """
    Main function for command-line execution.
    
    Parses command-line arguments and launches the application.
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Device Analysis Visualizer - Qt5 Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch with no sample (use File > Open Sample)
  python device_visualizer_app.py
  
  # Launch and auto-load a sample
  python device_visualizer_app.py --sample /path/to/sample
  
  # Enable debug logging
  python device_visualizer_app.py --debug --sample /path/to/sample
        """
    )
    
    parser.add_argument(
        '--sample', '-s',
        type=str,
        default=None,
        help='Path to sample folder to auto-load on startup'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Launch application
    sys.exit(launch_visualizer(args.sample))


# Entry point for direct execution
if __name__ == '__main__':
    main()
