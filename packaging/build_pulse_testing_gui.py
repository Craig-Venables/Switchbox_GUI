"""
Build Pulse Testing GUI executables using PyInstaller.

Usage (from repository root)::

    python packaging/build_pulse_testing_gui.py           # classic (TSP_Testing_GUI)
    python packaging/build_pulse_testing_gui.py --compact # compact layout only
    python packaging/build_pulse_testing_gui.py --all     # both classic and compact

Outputs (onedir)::

    dist/Pulse_Testing_GUI/Pulse_Testing_GUI.exe
    dist/Pulse_Testing_GUI_Compact/Pulse_Testing_GUI_Compact.exe

Distribute each entire folder (including ``_internal``).
Editable JSON configs are created beside the executable on first run.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _check_python_version() -> int | None:
    if sys.version_info[:3] == (3, 10, 0):
        print(
            "Error: Python 3.10.0 breaks PyInstaller analysis (dis.get_instructions bug).\n"
            "Install Python 3.10.11+ (e.g. winget install Python.Python.3.10), then either:\n"
            "  py -3.10 -m venv .venv-build && .venv-build\\Scripts\\pip install -r requirements.txt pyinstaller\n"
            "  .venv-build\\Scripts\\python packaging/build_pulse_testing_gui.py\n"
            "or recreate your main .venv with Python 3.10.11+."
        )
        return 1
    return None


def _ensure_pyinstaller(repo_root: Path) -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            cwd=repo_root,
        )


def _run_spec(repo_root: Path, spec: Path) -> None:
    if not spec.is_file():
        raise FileNotFoundError(f"missing {spec}")
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


def main() -> int:
    packaging_dir = Path(__file__).resolve().parent
    repo_root = packaging_dir.parent
    parser = argparse.ArgumentParser(description="Build Pulse Testing GUI executables")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--compact",
        action="store_true",
        help="Build compact layout only (Pulse_Testing_GUI_Compact.exe)",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Build both classic and compact executables",
    )
    args = parser.parse_args()

    err = _check_python_version()
    if err:
        return err

    classic_spec = packaging_dir / "build_pulse_testing_gui.spec"
    compact_spec = packaging_dir / "build_pulse_testing_gui_compact.spec"
    classic_entry = repo_root / "TSP_Testing_GUI.py"
    compact_entry = repo_root / "Pulse_Testing_GUI_compact.py"

    if args.compact:
        targets = [("compact", compact_spec, compact_entry)]
    elif args.all:
        targets = [
            ("classic", classic_spec, classic_entry),
            ("compact", compact_spec, compact_entry),
        ]
    else:
        targets = [("classic", classic_spec, classic_entry)]

    for _name, _spec, entry in targets:
        if not entry.is_file():
            print(f"Error: missing {entry}")
            return 1

    _ensure_pyinstaller(repo_root)

    outputs: list[Path] = []
    try:
        for name, spec, _entry in targets:
            print(f"\n=== Building {name} ===")
            _run_spec(repo_root, spec)
            if name == "classic":
                outputs.append(repo_root / "dist" / "Pulse_Testing_GUI" / "Pulse_Testing_GUI.exe")
            else:
                outputs.append(
                    repo_root / "dist" / "Pulse_Testing_GUI_Compact" / "Pulse_Testing_GUI_Compact.exe"
                )
    except subprocess.CalledProcessError:
        return 1
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    print("\nBuild complete:")
    for out in outputs:
        print(f"  {out}")
    print("\nCopy each dist/.../ folder when distributing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
