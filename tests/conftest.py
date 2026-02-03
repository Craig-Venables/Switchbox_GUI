"""Pytest configuration helpers for the Switchbox GUI project.

This module ensures that the project root is placed on ``sys.path`` before any
tests execute.  Running ``pytest`` directly (instead of ``python -m pytest``)
otherwise omits the repository root, leading to ``ModuleNotFoundError`` for
project packages such as ``Measurements``.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_root_on_path() -> None:
    """Insert the repository root at the front of ``sys.path`` if needed."""
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


_ensure_project_root_on_path()


