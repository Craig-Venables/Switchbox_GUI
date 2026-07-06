"""
Build TSP Data Analysis GUI (PyQt6) as a standalone onefile executable.

Usage (from repo root)::

    python tools/data_analysis_pulse_2450/build_exe.py

Output::

    tools/data_analysis_pulse_2450/dist/TSP_Data_Analysis.exe
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    tool_dir = Path(__file__).resolve().parent
    repo_root = tool_dir.parents[1]
    spec = tool_dir / "TSP_Data_Analysis.spec"
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

    # Optional Qt stack for this tool only
    try:
        import PyQt6  # noqa: F401
    except ImportError:
        print("Installing PyQt6 for data analysis tool...")
        req = tool_dir / "requirements.txt"
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req)],
            cwd=repo_root,
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
    subprocess.check_call(cmd, cwd=repo_root)
    out = tool_dir / "dist" / "TSP_Data_Analysis.exe"
    print(f"\nBuild complete: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
