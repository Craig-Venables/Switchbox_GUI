"""
Filament Jump Finder — find large current jumps (e.g. filament formation) in IV data.

GUI tool: sample folder → configurable threshold → first/all occurrence tables and plots,
CSV export, and Inspect dialog to include/exclude individual jumps.
"""

from typing import Optional

from .core import (
    find_jumps_in_curve,
    analyse_sample,
    get_first_and_all,
)
from .gui import MainWindow, InspectJumpsDialog


def run_gui(sample_path: Optional[str] = None):
    """Launch the Filament Jump Finder GUI. Optionally set initial sample folder."""
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = MainWindow()
    if sample_path:
        win.folder_edit.setText(sample_path)
    win.show()
    return app.exec_()


__all__ = [
    'find_jumps_in_curve',
    'analyse_sample',
    'get_first_and_all',
    'MainWindow',
    'InspectJumpsDialog',
    'run_gui',
]
