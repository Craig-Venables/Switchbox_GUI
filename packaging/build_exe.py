"""
Build Switchbox_GUI using PyInstaller and ``packaging/build_exe.spec``.

Usage (from repository root)::

    python packaging/build_exe.py

Output (onedir)::

    dist/Switchbox_GUI/Switchbox_GUI.exe

See Documents/build/BUILD_INSTRUCTIONS.md and Documents/build/BUILD_MODULES.md.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    if sys.version_info[:3] == (3, 10, 0):
        print(
            "Error: Python 3.10.0 breaks PyInstaller analysis.\n"
            "Use Python 3.10.11+ or 3.11+ (see Documents/build/BUILD_INSTRUCTIONS.md)."
        )
        return 1

    packaging_dir = Path(__file__).resolve().parent
    repo_root = packaging_dir.parent
    spec = packaging_dir / "build_exe.spec"
    if not spec.is_file():
        print(f"Error: missing {spec}")
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            cwd=repo_root,
        )

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec),
        "--noconfirm",
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=repo_root)
    print(f"\nBuild complete: {repo_root / 'dist' / 'Switchbox_GUI' / 'Switchbox_GUI.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
