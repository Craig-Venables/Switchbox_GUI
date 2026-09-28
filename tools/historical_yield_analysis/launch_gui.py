#!/usr/bin/env python
"""Launch the Historical Device Yield Analysis GUI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from historical_yield.config import load_config
from historical_yield.gui import run_app


def main() -> int:
    config = load_config()
    return run_app(config)


if __name__ == "__main__":
    raise SystemExit(main())
