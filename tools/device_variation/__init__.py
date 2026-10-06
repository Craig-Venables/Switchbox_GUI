"""Compare pre- and post-forming IV curves using a filament jump finder session."""

from typing import Optional

from .core import (
    NORM_LOG,
    NORM_MAX,
    NORM_RAW,
    NORM_READ,
    load_folder_paths,
    load_jump_session,
    summarize_compare,
    summarize_sample,
)


def run_gui(session_path: Optional[str] = None):
    """Launch the device variation viewer. Optionally open a jump-finder session."""
    import sys
    from PyQt5.QtWidgets import QApplication

    from .gui import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow()
    if session_path:
        win.load_session_path(session_path)
    win.show()
    return app.exec_()


__all__ = [
    "NORM_LOG",
    "NORM_MAX",
    "NORM_RAW",
    "NORM_READ",
    "load_folder_paths",
    "load_jump_session",
    "summarize_compare",
    "summarize_sample",
    "run_gui",
]
