"""
Import Keithley 2450 TSP stack without running Equipment.SMU_AND_PMU.__init__

The package __init__ eagerly imports Keithley2400 (pymeasure). This GUI only needs
TSP modules, so we load them by file path under the normal module names.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_KEITHLEY2450_DIR = _PROJECT_ROOT / "Equipment" / "SMU_AND_PMU" / "keithley2450"

_cached: Any = None


def _ensure_pkg(name: str, path: Path) -> None:
    if name in sys.modules and hasattr(sys.modules[name], "__path__"):
        return
    mod = types.ModuleType(name)
    mod.__path__ = [str(path)]
    mod.__package__ = name
    sys.modules[name] = mod


def _load_file(modname: str, filepath: Path):
    if modname in sys.modules and getattr(sys.modules[modname], "__file__", None) == str(filepath):
        return sys.modules[modname]
    spec = importlib.util.spec_from_file_location(modname, filepath)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {modname} from {filepath}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def load_tsp_stack() -> Tuple[Any, Any, Any]:
    """Return (Keithley2450_TSP, Keithley2450_TSP_Scripts, Keithley2450_TSP_Sim)."""
    global _cached
    if _cached is not None:
        return _cached

    _ensure_pkg("Equipment", _PROJECT_ROOT / "Equipment")
    _ensure_pkg("Equipment.SMU_AND_PMU", _PROJECT_ROOT / "Equipment" / "SMU_AND_PMU")
    _ensure_pkg("Equipment.SMU_AND_PMU.keithley2450", _KEITHLEY2450_DIR)

    tsp_mod = _load_file(
        "Equipment.SMU_AND_PMU.keithley2450.tsp_controller",
        _KEITHLEY2450_DIR / "tsp_controller.py",
    )
    scripts_mod = _load_file(
        "Equipment.SMU_AND_PMU.keithley2450.tsp_scripts",
        _KEITHLEY2450_DIR / "tsp_scripts.py",
    )
    sim_mod = _load_file(
        "Equipment.SMU_AND_PMU.keithley2450.tsp_sim_controller",
        _KEITHLEY2450_DIR / "tsp_sim_controller.py",
    )

    _cached = (
        tsp_mod.Keithley2450_TSP,
        scripts_mod.Keithley2450_TSP_Scripts,
        sim_mod.Keithley2450_TSP_Sim,
    )
    return _cached
