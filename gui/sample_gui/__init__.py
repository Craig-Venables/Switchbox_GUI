"""
Sample GUI – Device Selection and Sample Management
====================================================

Exports SampleGUI (lazy-loaded to avoid pulling MeasurementGUI on submodule import).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI

__all__ = ["SampleGUI"]


def __getattr__(name: str) -> object:
    if name == "SampleGUI":
        from gui.sample_gui.main import SampleGUI as _SampleGUI
        return _SampleGUI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
