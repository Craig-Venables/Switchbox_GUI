"""Compare the first sweep, and later forming metrics, across devices and samples."""


def run_gui():
    """Launch the first-sweep comparison window."""
    import sys
    from PyQt5.QtWidgets import QApplication

    from .gui import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()
