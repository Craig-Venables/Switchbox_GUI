"""
Console helper for running bundled Python scripts inside a frozen Switchbox build.

Usage (frozen release layout)::

    tools_bin\\Switchbox_ScriptRunner.exe <path-to-script.py> [script args...]

The script path is typically under the PyInstaller bundle (``_MEIPASS``).
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print("Usage: Switchbox_ScriptRunner <script.py> [args...]", file=sys.stderr)
        return 2

    script = Path(args[0]).resolve()
    if not script.is_file():
        print(f"Script not found: {script}", file=sys.stderr)
        return 1

    sys.argv = [str(script), *args[1:]]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
