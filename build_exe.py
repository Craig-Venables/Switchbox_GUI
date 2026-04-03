"""
Build Switchbox_GUI using PyInstaller and repository-root ``build_exe.spec``.

Usage (from repository root)::

    python build_exe.py

Output (onedir)::

    dist/Switchbox_GUI/Switchbox_GUI.exe

See Documents/build/BUILD_INSTRUCTIONS.md and Documents/build/BUILD_MODULES.md.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    spec = root / "build_exe.spec"
    if not spec.is_file():
        print(f"Error: missing {spec}")
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
    print(f"\nBuild complete: {root / 'dist' / 'Switchbox_GUI' / 'Switchbox_GUI.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
