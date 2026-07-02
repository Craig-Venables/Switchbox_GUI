"""
Measurement GUI – Main Measurement Interface
=============================================

Exports MeasurementGUI (lazy-loaded to avoid pulling heavy dependencies on import).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui.measurement_gui.main import MeasurementGUI

__all__ = ["MeasurementGUI", "SMUAdapter"]


def __getattr__(name: str) -> object:
    if name == "MeasurementGUI":
        from gui.measurement_gui.main import MeasurementGUI as _MeasurementGUI
        return _MeasurementGUI
    if name == "SMUAdapter":
        from gui.measurement_gui.smu_adapter import SMUAdapter as _SMUAdapter
        return _SMUAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
