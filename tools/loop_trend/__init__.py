"""Find multi-loop IV files and plot how the positive and negative sides change."""

from .core import scan_folders


def run_gui():
    """Launch the loop-trend viewer."""
    import sys
    from PyQt5.QtWidgets import QApplication

    from .gui import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()
