"""Load TSP pulse files via tools/data_analysis_pulse_2450 parser."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PULSE_TOOL = _REPO_ROOT / "tools" / "data_analysis_pulse_2450"

# Canonical analysis families
FAMILY_ENDURANCE = "endurance"
FAMILY_POT_DEP = "pot_dep"
FAMILY_POT_ONLY = "pot_only"
FAMILY_DEP_ONLY = "dep_only"
FAMILY_MULTI_READ = "multi_read"
FAMILY_READ_ONLY = "read_only"
FAMILY_PULSE_TRAIN = "pulse_train"
FAMILY_READ_REPEAT = "read_repeat"
FAMILY_WIDTH_SWEEP = "width_sweep"
FAMILY_RELAXATION = "relaxation"
FAMILY_RETENTION = "retention"
FAMILY_LASER_READ = "laser_read"
FAMILY_RANGE_FINDER = "range_finder"
FAMILY_SLOW_PULSE = "slow_pulse"
FAMILY_IV_SWEEP = "iv_sweep"
FAMILY_UNSUPPORTED = "unsupported"

SUPPORTED_FAMILIES = {
    FAMILY_ENDURANCE,
    FAMILY_POT_DEP,
    FAMILY_POT_ONLY,
    FAMILY_DEP_ONLY,
    FAMILY_MULTI_READ,
    FAMILY_READ_ONLY,
    FAMILY_PULSE_TRAIN,
    FAMILY_READ_REPEAT,
    FAMILY_WIDTH_SWEEP,
    FAMILY_RELAXATION,
    FAMILY_RETENTION,
    FAMILY_LASER_READ,
    FAMILY_RANGE_FINDER,
    FAMILY_SLOW_PULSE,
    FAMILY_IV_SWEEP,
}

_ALIAS_TO_FAMILY = {
    # Endurance
    "endurance": FAMILY_ENDURANCE,
    "endurance test": FAMILY_ENDURANCE,
    "smu endurance": FAMILY_ENDURANCE,
    "smu: endurance": FAMILY_ENDURANCE,
    # Pot / dep cycle
    "pot / dep cycle": FAMILY_POT_DEP,
    "pot dep cycle": FAMILY_POT_DEP,
    "potentiation depression cycle": FAMILY_POT_DEP,
    "potentiation-depression cycle": FAMILY_POT_DEP,
    "pot_dep_cycle": FAMILY_POT_DEP,
    # Pot / dep only
    "potentiation": FAMILY_POT_ONLY,
    "potentiation only": FAMILY_POT_ONLY,
    "depression": FAMILY_DEP_ONLY,
    "depression only": FAMILY_DEP_ONLY,
    # Multi-read / read only
    "pulse multi read": FAMILY_MULTI_READ,
    "pulse-multi-read": FAMILY_MULTI_READ,
    "pulse_multi_read": FAMILY_MULTI_READ,
    "pulse → multi-read": FAMILY_MULTI_READ,
    "pulse multi-read": FAMILY_MULTI_READ,
    "multi read only": FAMILY_READ_ONLY,
    "multi-read only": FAMILY_READ_ONLY,
    "read only": FAMILY_READ_ONLY,
    # Pulse train / multi-pulse then read
    "pulse train read": FAMILY_PULSE_TRAIN,
    "pulse train": FAMILY_PULSE_TRAIN,
    "pulse_train_read": FAMILY_PULSE_TRAIN,
    "pulse train → read": FAMILY_PULSE_TRAIN,
    "multi pulse then read": FAMILY_PULSE_TRAIN,
    "multi-pulse-then-read": FAMILY_PULSE_TRAIN,
    "electrical pulse train": FAMILY_PULSE_TRAIN,
    # Read → write → read
    "pulse read repeat": FAMILY_READ_REPEAT,
    "pulse-read-repeat": FAMILY_READ_REPEAT,
    "pulse_read_repeat": FAMILY_READ_REPEAT,
    "read → write → read": FAMILY_READ_REPEAT,
    "read write read": FAMILY_READ_REPEAT,
    # Width sweep
    "width sweep": FAMILY_WIDTH_SWEEP,
    "width sweep (full)": FAMILY_WIDTH_SWEEP,
    "pulse width sweep": FAMILY_WIDTH_SWEEP,
    "pulse width sweep (+ i)": FAMILY_WIDTH_SWEEP,
    "width_sweep": FAMILY_WIDTH_SWEEP,
    # Relaxation
    "relaxation": FAMILY_RELAXATION,
    "relaxation after multi pulse": FAMILY_RELAXATION,
    "relaxation after multi-pulse": FAMILY_RELAXATION,
    "relaxation (+ pulse i)": FAMILY_RELAXATION,
    "relaxation after multi pulse with pulse measurement": FAMILY_RELAXATION,
    # Retention
    "retention": FAMILY_RETENTION,
    "pmu retention test": FAMILY_RETENTION,
    "smu retention": FAMILY_RETENTION,
    "smu: retention": FAMILY_RETENTION,
    "smu retention (pulse measured)": FAMILY_RETENTION,
    "smu: retention (+ pulse i)": FAMILY_RETENTION,
    # Laser
    "laser and read": FAMILY_LASER_READ,
    "laser + read": FAMILY_LASER_READ,
    "laser_and_read": FAMILY_LASER_READ,
    # Range finder
    "current range finder": FAMILY_RANGE_FINDER,
    "range finder": FAMILY_RANGE_FINDER,
    # Slow pulse
    "smu slow pulse measure": FAMILY_SLOW_PULSE,
    "smu: slow pulse": FAMILY_SLOW_PULSE,
    "smu slow pulse": FAMILY_SLOW_PULSE,
    # IV in pulse folder
    "iv sweep (hysteresis)": FAMILY_IV_SWEEP,
    "iv sweep": FAMILY_IV_SWEEP,
    "iv_sweep": FAMILY_IV_SWEEP,
    # PMU pulse-read → treat like read_repeat time series
    "pmu pulse-read": FAMILY_READ_REPEAT,
    "pmu pulse read": FAMILY_READ_REPEAT,
}


def _ensure_pulse_tool_on_path() -> None:
    tool = str(_PULSE_TOOL)
    if tool not in sys.path:
        sys.path.insert(0, tool)


def load_tsp(filepath: Path | str):
    """Parse a pulse .txt file into TSPData (or None)."""
    _ensure_pulse_tool_on_path()
    from core.data_parser import parse_tsp_file  # type: ignore

    return parse_tsp_file(Path(filepath))


def _normalize_token(text: str) -> str:
    t = text.strip().lower()
    # strip warning emoji / symbols often in SMU names
    for ch in ("⚠", "️", "⚡", "🔦", "→", "➡", "–", "—", "_", "-", "/", "(", ")", "+"):
        t = t.replace(ch, " ")
    return " ".join(t.split())


def classify_pulse_family(test_name: str = "", filename: str = "") -> str:
    """Return family constant or FAMILY_UNSUPPORTED."""
    candidates = []
    if test_name:
        candidates.append(_normalize_token(test_name))
    if filename:
        stem = Path(filename).stem
        parts = stem.split("-", 2)
        if len(parts) >= 2 and parts[0].isdigit():
            candidates.append(_normalize_token(parts[1]))
        candidates.append(_normalize_token(stem))

    for cand in candidates:
        if cand in _ALIAS_TO_FAMILY:
            return _ALIAS_TO_FAMILY[cand]

    for cand in candidates:
        if "endurance" in cand:
            return FAMILY_ENDURANCE
        if "width" in cand and "sweep" in cand:
            return FAMILY_WIDTH_SWEEP
        if "relax" in cand:
            return FAMILY_RELAXATION
        if "retention" in cand:
            return FAMILY_RETENTION
        if "laser" in cand:
            return FAMILY_LASER_READ
        if "range" in cand and "finder" in cand:
            return FAMILY_RANGE_FINDER
        if "slow" in cand and "pulse" in cand:
            return FAMILY_SLOW_PULSE
        if cand.startswith("iv") or "hysteresis" in cand:
            return FAMILY_IV_SWEEP
        if "potentiation" in cand and "depression" not in cand and "dep" not in cand:
            return FAMILY_POT_ONLY
        if "depression" in cand and "pot" not in cand:
            return FAMILY_DEP_ONLY
        if "pot" in cand and "dep" in cand:
            return FAMILY_POT_DEP
        if "read" in cand and "only" in cand:
            return FAMILY_READ_ONLY
        if "read" in cand and "write" in cand and "read" in cand:
            return FAMILY_READ_REPEAT
        if "train" in cand:
            return FAMILY_PULSE_TRAIN
        if "multi" in cand and "read" in cand:
            return FAMILY_MULTI_READ
        if "pulse" in cand and "read" in cand and "repeat" in cand:
            return FAMILY_READ_REPEAT
    return FAMILY_UNSUPPORTED


def get_operation_column(tsp_data) -> Optional[Any]:
    for key in list(tsp_data.additional_data.keys()):
        kl = key.lower()
        if "operation" in kl or "pulse type" in kl or "pulse_type" in kl:
            return tsp_data.additional_data[key]
    return None


def get_phase_column(tsp_data) -> Optional[Any]:
    for key in list(tsp_data.additional_data.keys()):
        if "phase" in key.lower():
            return tsp_data.additional_data[key]
    return None


def get_cycle_column(tsp_data) -> Optional[Any]:
    for key in list(tsp_data.additional_data.keys()):
        if "cycle" in key.lower():
            return tsp_data.additional_data[key]
    return None


def get_width_column(tsp_data) -> Optional[Any]:
    for key in list(tsp_data.additional_data.keys()):
        kl = key.lower()
        if "width" in kl:
            return tsp_data.additional_data[key]
    return None
