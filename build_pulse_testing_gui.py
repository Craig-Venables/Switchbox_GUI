"""
Build Pulse Testing GUI using PyInstaller and ``build_pulse_testing_gui.spec``.

Usage (from repository root)::

    python build_pulse_testing_gui.py

Output (onedir)::

    dist/Pulse_Testing_GUI/Pulse_Testing_GUI.exe

Distribute the entire ``dist/Pulse_Testing_GUI/`` folder (including ``_internal``).
Editable JSON configs are created beside the executable on first run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    spec = root / "build_pulse_testing_gui.spec"
    entry = root / "TSP_Testing_GUI.py"
    if not spec.is_file():
        print(f"Error: missing {spec}")
        return 1
    if not entry.is_file():
        print(f"Error: missing {entry}")
        return 1

    if sys.version_info[:3] == (3, 10, 0):
        print(
            "Error: Python 3.10.0 breaks PyInstaller analysis (dis.get_instructions bug).\n"
            "Install Python 3.10.11+ (e.g. winget install Python.Python.3.10), then either:\n"
            "  py -3.10 -m venv .venv-build && .venv-build\\Scripts\\pip install -r requirements.txt pyinstaller\n"
            "  .venv-build\\Scripts\\python build_pulse_testing_gui.py\n"
            "or recreate your main .venv with Python 3.10.11+."
        )
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            cwd=root,
        )

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec),
        "--clean",
        "--noconfirm",
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=root)
    out = root / "dist" / "Pulse_Testing_GUI" / "Pulse_Testing_GUI.exe"
    print(f"\nBuild complete: {out}")
    print("Copy the whole dist/Pulse_Testing_GUI/ folder when distributing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
