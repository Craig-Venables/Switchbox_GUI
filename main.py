"""Main entry point for Switchbox GUI applications."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

import tkinter as tk

from Sample_GUI import SampleGUI


def _launch_tk(_sample_args: Sequence[str] | None = None) -> None:
    """Start the legacy Tkinter GUI."""
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()


def _launch_qt(sample_args: Sequence[str] | None = None) -> None:
    """Start the experimental PyQt6 GUI."""
    try:
        from PyQt6 import QtWidgets
    except Exception as exc:  # pragma: no cover - import guard
        print("Failed to import PyQt6; falling back to Tkinter.", file=sys.stderr)
        print(f"Import error: {exc}", file=sys.stderr)
        _launch_tk(sample_args)
        return

    from qt.sample_window import QtSampleWindow

    app = QtWidgets.QApplication(sys.argv)
    window = QtSampleWindow()
    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)


def main(
    argv: Sequence[str] | None = None,
    gui: Optional[str] = None,
) -> None:
    """Entry point for launching Tk or Qt GUI variants.

    Args:
        argv: Optional sequence of CLI-style arguments (defaults to sys.argv[1:]).
        gui: Optional override for GUI selection: ``"tk"`` or ``"qt"``.
             When provided, it takes precedence over command-line flags.
    """
    parser = argparse.ArgumentParser(description="Switchbox Measurement GUI launcher")
    parser.add_argument(
        "--qt",
        action="store_true",
        help="Launch the experimental PyQt6 interface instead of Tkinter.",
    )
    parser.add_argument(
        "--gui",
        choices=("tk", "qt"),
        help="Explicitly choose which GUI to launch.",
    )

    args, sample_args = parser.parse_known_args(argv)

    preferred_gui = None
    if gui:
        preferred_gui = gui.strip().lower()
        if preferred_gui not in {"tk", "qt"}:
            print(
                f"Unknown gui selection '{gui}', defaulting to Tkinter.",
                file=sys.stderr,
            )
            preferred_gui = "tk"
    elif args.gui:
        preferred_gui = args.gui
    elif args.qt:
        preferred_gui = "qt"
    else:
        preferred_gui = "tk"

    if preferred_gui == "qt":
        _launch_qt(sample_args)
    else:
        _launch_tk(sample_args)


if __name__ == "__main__":
    # Toggle this to "qt" to force the PyQt6 interface without command-line flags.
    DEFAULT_GUI = "tk"  # choices: "tk" or "qt"
    main(gui=DEFAULT_GUI)
