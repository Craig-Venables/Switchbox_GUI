"""
Filament Jump Finder — find large current jumps (e.g. filament formation) in IV data.

GUI: multi-folder load → live ratio / voltage window → mark Jump / Not a jump →
Compare yield (all + memristive) → Save Session / Save for Origin.
"""

from typing import Optional

from .core import (
    find_jumps_in_curve,
    analyse_sample,
    load_sample,
    load_folder,
    load_folders,
    filter_jumps,
    get_first_and_all,
    jump_decision_key,
    compute_yield_summary,
    DETECTION_FLOOR_RATIO,
)
from .gui import MainWindow, InspectJumpsDialog
from .origin_export import (
    export_origin_files,
    load_review_json,
    save_session,
    load_session,
    ORIGIN_DIR_NAME,
)


def run_gui(sample_path: Optional[str] = None):
    """Launch the Filament Jump Finder GUI. Optionally preload one folder."""
    import sys
    from pathlib import Path
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = MainWindow()
    if sample_path:
        p = Path(sample_path)
        win.folder_edit.setText(str(p))
        if p.is_dir():
            win._folder_paths = [p]
            win._refresh_folder_list()
            win._reload_folders()
    win.show()
    return app.exec_()


__all__ = [
    'find_jumps_in_curve',
    'analyse_sample',
    'load_sample',
    'load_folder',
    'load_folders',
    'filter_jumps',
    'get_first_and_all',
    'jump_decision_key',
    'compute_yield_summary',
    'DETECTION_FLOOR_RATIO',
    'export_origin_files',
    'load_review_json',
    'save_session',
    'load_session',
    'ORIGIN_DIR_NAME',
    'MainWindow',
    'InspectJumpsDialog',
    'run_gui',
]
