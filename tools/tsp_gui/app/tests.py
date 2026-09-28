"""2450-only test catalog for the TSP GUI."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .config import SECONDS_PARAM_KEYS, TIME_PARAM_KEYS, TIME_TO_SECONDS

OPTICAL_FUNCTIONS = frozenset({
    "optical_read_pulsed_light",
    "optical_pulse_train_read",
    "optical_pulse_train_pattern_read",
    "optical_binary_sweep",
    "optical_pattern_repeat",
})

# Tests supported by Keithley2450_TSP_Scripts but missing/filtered in shared GUI defs
_EXTRA_2450: Dict[str, Dict[str, Any]] = {
    "Pulse then Read": {
        "function": "pulse_then_read",
        "description": "Pattern: (Pulse → Delay → Read) × N",
        "params": {
            "pulse_voltage": {"default": 1.0, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "delay_after_pulse": {"default": 1.0, "label": "Delay After Pulse (ms)", "type": "float"},
            "num_cycles": {"default": 10, "label": "Number of Cycles", "type": "int"},
            "clim": {"default": 1e-3, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    "Varying Width Pulses": {
        "function": "varying_width_pulses",
        "description": "Multiple pulse widths; pulses_per_width at each width",
        "params": {
            "pulse_voltage": {"default": 1.0, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_widths": {"default": "1e-3,5e-3,10e-3", "label": "Pulse Widths (comma-separated, s)", "type": "list"},
            "pulses_per_width": {"default": 5, "label": "Pulses Per Width", "type": "int"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "width_vs_resistance",
    },
    "Retention (2450)": {
        "function": "retention_test",
        "description": "Pulse once, then read at listed intervals (s). TSP + PC-timed reads.",
        "params": {
            "pulse_voltage": {"default": 2.0, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "read_intervals": {"default": "1,10,100", "label": "Read intervals (comma-separated, s)", "type": "list"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    "Voltage Amplitude Sweep": {
        "function": "voltage_amplitude_sweep",
        "description": "Sweep pulse amplitude at fixed width",
        "params": {
            "pulse_voltage_start": {"default": 0.5, "label": "Start Voltage (V)", "type": "float"},
            "pulse_voltage_stop": {"default": 2.5, "label": "Stop Voltage (V)", "type": "float"},
            "pulse_voltage_step": {"default": 0.1, "label": "Step (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_voltage": {"default": 5, "label": "Pulses Per Voltage", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 1.0, "label": "Reset Width (ms)", "type": "float"},
            "delay_between_voltages": {"default": 1000.0, "label": "Delay Between Voltages (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    "ISPP": {
        "function": "ispp_test",
        "description": "Incremental step pulse programming until switch / max voltage",
        "params": {
            "start_voltage": {"default": 0.5, "label": "Start Voltage (V)", "type": "float"},
            "voltage_step": {"default": 0.05, "label": "Voltage Step (V)", "type": "float"},
            "max_voltage": {"default": 3.0, "label": "Max Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "resistance_threshold_factor": {"default": 0.5, "label": "Resistance Threshold Factor", "type": "float"},
            "max_pulses": {"default": 100, "label": "Max Pulses", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    "Switching Threshold": {
        "function": "switching_threshold_test",
        "description": "Find minimum voltage to switch (SET or RESET)",
        "params": {
            "direction": {"default": "set", "label": "Direction (set/reset)", "type": "str"},
            "start_voltage": {"default": 0.5, "label": "Start Voltage (V)", "type": "float"},
            "voltage_step": {"default": 0.05, "label": "Voltage Step (V)", "type": "float"},
            "max_voltage": {"default": 3.0, "label": "Max Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "resistance_threshold_factor": {"default": 0.5, "label": "Resistance Threshold Factor", "type": "float"},
            "num_pulses_per_voltage": {"default": 3, "label": "Pulses Per Voltage", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
    "Multilevel Programming": {
        "function": "multilevel_programming",
        "description": "Program toward target resistance levels",
        "params": {
            "target_levels": {"default": "1e4,1e5,1e6", "label": "Target R levels (Ohm, comma-sep)", "type": "list"},
            "pulse_voltage": {"default": 1.5, "label": "Pulse Voltage (V)", "type": "float"},
            "pulse_width": {"default": 1.0, "label": "Pulse Width (ms)", "type": "float"},
            "read_voltage": {"default": 0.2, "label": "Read Voltage (V)", "type": "float"},
            "num_pulses_per_level": {"default": 5, "label": "Pulses Per Level", "type": "int"},
            "delay_between": {"default": 10.0, "label": "Delay Between (ms)", "type": "float"},
            "reset_voltage": {"default": -1.0, "label": "Reset Voltage (V)", "type": "float"},
            "reset_width": {"default": 1.0, "label": "Reset Width (ms)", "type": "float"},
            "delay_between_levels": {"default": 1000.0, "label": "Delay Between Levels (ms)", "type": "float"},
            "clim": {"default": 100e-6, "label": "Current Limit (A)", "type": "float"},
        },
        "plot_type": "time_series",
    },
}

# delay_after_pulse is also a time param in ms
TIME_PARAM_KEYS_LOCAL = TIME_PARAM_KEYS | frozenset({"delay_after_pulse"})


def get_2450_test_definitions() -> Dict[str, Dict[str, Any]]:
    """Return display-name → definition for keithley2450 only (no 4200-only params)."""
    from Pulse_Testing.test_definitions import get_test_definitions_for_gui

    raw = get_test_definitions_for_gui("keithley2450")
    cleaned: Dict[str, Dict[str, Any]] = {}
    for name, defn in raw.items():
        params = {}
        for key, meta in (defn.get("params") or {}).items():
            if meta.get("4200a_only"):
                continue
            params[key] = dict(meta)
        cleaned[name] = {
            "function": defn["function"],
            "description": defn.get("description", ""),
            "params": params,
            "plot_type": defn.get("plot_type", "time_series"),
            "optical": defn["function"] in OPTICAL_FUNCTIONS,
        }

    for name, defn in _EXTRA_2450.items():
        entry = {
            "function": defn["function"],
            "description": defn.get("description", ""),
            "params": {k: dict(v) for k, v in defn["params"].items()},
            "plot_type": defn.get("plot_type", "time_series"),
            "optical": False,
        }
        cleaned[name] = entry

    return cleaned


def split_electrical_optical(
    defs: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    electrical = {k: v for k, v in defs.items() if not v.get("optical")}
    optical = {k: v for k, v in defs.items() if v.get("optical")}
    return electrical, optical


def convert_params_for_2450(raw_params: Dict[str, Any]) -> Dict[str, Any]:
    """Convert GUI values to script units (ms → s for timing keys)."""
    out: Dict[str, Any] = {}
    for key, value in raw_params.items():
        if key in SECONDS_PARAM_KEYS:
            out[key] = value
        elif key in TIME_PARAM_KEYS_LOCAL and isinstance(value, (int, float)):
            out[key] = float(value) * TIME_TO_SECONDS
        elif key in ("pulse_widths", "read_intervals", "target_levels"):
            if isinstance(value, str):
                out[key] = [float(x.strip()) for x in value.split(",") if x.strip()]
            else:
                out[key] = value
        else:
            out[key] = value
    out.pop("plot_y_axis", None)
    return out


def default_params(defn: Dict[str, Any]) -> Dict[str, Any]:
    params = {}
    for key, meta in (defn.get("params") or {}).items():
        params[key] = meta.get("default")
    return params


def electrical_display_names() -> List[str]:
    electrical, _ = split_electrical_optical(get_2450_test_definitions())
    return list(electrical.keys())


def optical_display_names() -> List[str]:
    _, optical = split_electrical_optical(get_2450_test_definitions())
    return list(optical.keys())
