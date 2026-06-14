"""
Deprecated compatibility shim for ``Measurements``.

The canonical package is ``Measurements`` (correct spelling). This package
re-exports all submodules so older imports such as ``from Measurments.data_formats
import ...`` continue to work. Do not add new code here.
"""

from __future__ import annotations

import importlib
import sys
import warnings

_SUBMODULES = (
    "background_workers",
    "connection_manager",
    "data_formats",
    "data_saver",
    "data_utils",
    "json_config_validator",
    "measurement_context",
    "measurement_services_pmu",
    "measurement_services_smu",
    "optical_controller",
    "pulsed_measurement_runner",
    "sequential_runner",
    "single_measurement_runner",
    "source_modes",
    "special_measurement_runner",
    "sweep_config",
    "sweep_patterns",
    "telegram_coordinator",
)

warnings.warn(
    "Measurments is deprecated; import from Measurements instead.",
    DeprecationWarning,
    stacklevel=2,
)

for _name in _SUBMODULES:
    _target = importlib.import_module(f"Measurements.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _target

from Measurements import *  # noqa: F403

__all__ = list(getattr(importlib.import_module("Measurements"), "__all__", []))
