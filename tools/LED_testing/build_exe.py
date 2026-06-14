"""
Build a standalone GUI executable for the LED testing tool (PyInstaller).

Requires: pyserial installed in the same environment (same as ``main.py``).

Usage (from repo root or this directory):

    python tools/LED_testing/build_exe.py

Uses ``LEDTesting.spec`` in this folder. Output:
``tools/LED_testing/dist/LEDTesting.exe`` (Windows) or ``dist/LEDTesting`` (Unix).
"""

from __future__ import annotations

import os
import subprocess
import sys


def build_exe() -> bool:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    spec_name = "LEDTesting.spec"
    exe_name = "LEDTesting"

    if not os.path.exists(spec_name):
        print(f"Error: {spec_name} not found in {script_dir}")
        return False
    if not os.path.exists("main.py"):
        print(f"Error: main.py not found in {script_dir}")
        return False

    try:
        import PyInstaller  # noqa: F401

        print("PyInstaller found.")
    except ImportError:
        print("PyInstaller not found. Installing...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "pyinstaller"],
            )
            print("PyInstaller installed successfully.")
        except subprocess.CalledProcessError as exc:
            print(f"Failed to install PyInstaller: {exc}")
            return False

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        spec_name,
    ]

    print("\n" + "=" * 60)
    print("Building LED testing executable...")
    print("=" * 60)
    print(f"Working directory: {script_dir}")
    print(f"Spec: {spec_name}")
    print(f"Output name: {exe_name}")
    print("=" * 60 + "\n")

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        print(f"\nBuild failed: {exc}\n")
        return False
    except OSError as exc:
        print(f"\nUnexpected error: {exc}\n")
        return False

    dist_name = "LEDTesting.exe" if sys.platform == "win32" else exe_name
    exe_path = os.path.join("dist", dist_name)
    abs_path = os.path.abspath(exe_path)
    print("\n" + "=" * 60)
    print("Build complete.")
    print("=" * 60)
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"Executable: {abs_path}")
        print(f"Size: {size_mb:.2f} MB")
    else:
        print(f"Warning: expected file not found: {abs_path}")
    print("=" * 60 + "\n")
    return True


if __name__ == "__main__":
    sys.exit(0 if build_exe() else 1)
