"""
Test Definitions - GUI metadata for pulse tests
================================================

Built from ``test_registry.py`` (edit tests THERE, not here). This module keeps the
dict shape the GUI has always used:

    TEST_FUNCTIONS[display_name] = {function, description, params, plot_type, only_for_systems}

Use get_test_definitions_for_gui(system_name) to get definitions filtered by
current system so only available tests appear.
"""

import copy
from typing import Dict, List, Any, Optional

from .test_registry import visible_tests


# Dropdown order by backend function name (derived from registry list order).
TEST_DISPLAY_ORDER: List[str] = list(dict.fromkeys(t.function for t in visible_tests()))

# Old GUI labels → new (presets / saved configs)
TEST_DISPLAY_NAME_ALIASES: Dict[str, str] = {
    "Endurance Test": "Endurance",
    "PMU Retention Test": "Retention",
    "Pulse-Read-Repeat": "Read → Write → Read",
    "Multi-Pulse-Then-Read": "Pulse Train → Read",
    "Pulse-Multi-Read": "Pulse → Multi-Read",
    "Multi-Read Only": "Read Only",
    "Width Sweep": "Pulse Width Sweep",
    "Width Sweep (Full)": "Pulse Width Sweep (+ I)",
    "Potentiation-Depression Cycle": "Pot / Dep Cycle",
    "Potentiation Only": "Potentiation",
    "Depression Only": "Depression",
    "Relaxation After Multi-Pulse": "Relaxation",
    "Relaxation After Multi-Pulse With Pulse Measurement": "Relaxation (+ Pulse I)",
    "Laser and Read": "Laser + Read",
    "⚠️ SMU Slow Pulse Measure": "SMU: Slow Pulse",
    "⚠️ SMU Endurance": "SMU: Endurance",
    "⚠️ SMU Retention": "SMU: Retention",
    "⚠️ SMU Retention (Pulse Measured)": "SMU: Retention (+ Pulse I)",
    "⚡ Electrical Pulse Train (Memristor Programming)": "Electrical Pulse Train",
    "🔦 Optical Read (Pulsed Light)": "Optical: Pulsed Read",
    "🔦 Optical Pulse Train + Read": "Optical: Pulse Train + Read",
    "🔦 Continuous Read with Laser Pulse Pattern": "Optical: Pattern + Read",
    "🔦 Binary Pattern Sweep": "Optical: Binary Sweep",
    "🔦 Pattern Repeat": "Optical: Pattern Repeat",
}


def canonical_test_display_name(name: str) -> str:
    """Map legacy display name to current TEST_FUNCTIONS key."""
    return TEST_DISPLAY_NAME_ALIASES.get(name, name)


# Legacy preset names → current tsp_test_presets.json keys (within each test bucket).
PRESET_NAME_ALIASES: Dict[str, str] = {
    "PMU 2-cycle smoke": "DUT 10cyc @ 1us",
    "PMU 8-read smoke": "DUT 20 reads @ 1us program",
    "PMU 1us write (scope validated)": "DUT 1us write",
    "PMU 100ns write": "DUT 100ns write",
    "DUT 50-cycle (1us)": "DUT 20cyc @ 1us (max burst)",
    "DUT 100-cycle (1us)": "DUT 20cyc @ 1us (max burst)",
    "DUT 100 retention reads (may exceed burst limit)": "Stress 100 reads (may exceed burst limit)",
    "DUT 20 program pulses / 30 reads": "DUT 20 program / 30 reads",
    "DUT min gaps 20ns (reads+pulses)": "DUT min gaps 20ns",
    "DUT program @ 1us / 20 reads": "DUT 20 reads @ 1us program",
    "Limit max reads (200) — may exceed burst limit": "Stress 100 reads (may exceed burst limit)",
}


def canonical_preset_name(name: str) -> str:
    return PRESET_NAME_ALIASES.get(name, name)


def migrate_presets_dict(presets: Dict[str, Any]) -> Dict[str, Any]:
    """Rename preset buckets and preset keys when loading JSON saved under old names."""
    out: Dict[str, Any] = {}
    for old_name, preset_map in presets.items():
        new_name = canonical_test_display_name(old_name)
        bucket = out.setdefault(new_name, {})
        if isinstance(preset_map, dict):
            for preset_name, preset_values in preset_map.items():
                bucket[canonical_preset_name(preset_name)] = preset_values
    return out


def _definition_from_spec(spec) -> Dict[str, Any]:
    return {
        "function": spec.function,
        "description": spec.description,
        "params": copy.deepcopy(dict(spec.params)),
        "plot_type": spec.plot_type,
        "only_for_systems": sorted(spec.systems),
    }


# Display name -> { function, description, params, plot_type, only_for_systems }
TEST_FUNCTIONS: Dict[str, Dict[str, Any]] = {
    spec.display_name: _definition_from_spec(spec) for spec in visible_tests()
}

# PMU interleaved tests: per-test IRange (EX parameter), shown when keithley4200_pmu is selected.
_PMU_I_RANGE_PARAM: Dict[str, Any] = {
    "default": 1e-4,
    "label": "PMU Current Range (A)",
    "type": "float",
    "4200a_only": True,
}

try:
    from Pulse_Testing.pmu_channel_wiring import PMU_INTERLEAVED_DUT_2CH

    for _defn in TEST_FUNCTIONS.values():
        _func = _defn.get("function", "")
        if _func in PMU_INTERLEAVED_DUT_2CH and "i_range" not in _defn.get("params", {}):
            _defn.setdefault("params", {})["i_range"] = dict(_PMU_I_RANGE_PARAM)
except ImportError:
    pass


def get_test_definitions_for_gui(
    system_name: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Return test definitions for the GUI, optionally filtered by current system.

    If system_name is given, only tests whose registry ``systems`` include it
    are returned, in registry order. If system_name is None,
    all defined tests are returned (e.g. before any system is connected).

    Args:
        system_name: Current system (e.g. 'keithley2450', 'keithley4200_pmu', 'keithley4200_smu', 'keithley2400')
                    or None to return all definitions.

    Returns:
        Dict mapping display name -> { function, description, params, plot_type, ... }
    """
    if system_name is None:
        return dict(TEST_FUNCTIONS)
    return {
        name: defn
        for name, defn in TEST_FUNCTIONS.items()
        if system_name in defn["only_for_systems"]
    }


def get_display_name_for_function(function_key: str) -> Optional[str]:
    """Return the display name for a test function key, or None if not found."""
    for display_name, defn in TEST_FUNCTIONS.items():
        if defn.get("function") == function_key:
            return display_name
    return None
