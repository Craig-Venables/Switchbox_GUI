"""Alias entry point for the Solartron SI 1260 GUI."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gui import main

if __name__ == "__main__":
    raise SystemExit(main())
