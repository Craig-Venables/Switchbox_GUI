"""Paths and defaults for the standalone 2450 TSP GUI."""

from pathlib import Path
import json
from typing import Any, Dict

TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parents[1]
JSON_DIR = TOOL_ROOT / "Json_Files"
DATA_DIR = TOOL_ROOT / "data"
SETTINGS_PATH = JSON_DIR / "tsp_gui_settings.json"

WINDOW_TITLE = "2450 TSP Pulse GUI"
WINDOW_GEOMETRY = "1280x860"

# Keithley 2450 USB VISA defaults
DEFAULT_USB_ADDRESS = "USB0::0x05E6::0x2450::04496615::INSTR"
SIM_ADDRESS = "SIM::KEITHLEY2450"
USB_VENDOR_HINT = "0x05E6"
USB_MODEL_HINT = "0x2450"

# Oxxius laser defaults
DEFAULT_LASER_PORT = "COM4"
DEFAULT_LASER_BAUD = 19200
DEFAULT_LASER_SAFE_POWER_MW = 10.0

DEFAULT_TERMINALS = "front"
DEFAULT_TIMEOUT_MS = 10000

# GUI time unit for electrical pulse params (2450 scripts expect seconds)
TIME_UNIT = "ms"
TIME_TO_SECONDS = 1e-3

TIME_PARAM_KEYS = frozenset({
    "pulse_width",
    "delay_between",
    "delay_between_pulses",
    "delay_between_reads",
    "delay_before_read",
    "delay_between_cycles",
    "post_read_interval",
    "reset_width",
    "delay_between_voltages",
    "delay_between_levels",
})

# Already in seconds in the UI (optical / duration fields)
SECONDS_PARAM_KEYS = frozenset({
    "total_time_s",
    "optical_pulse_duration_s",
    "optical_pulse_period_s",
    "sample_interval_s",
    "duration_s",
    "laser_delay_s",
    "measurement_init_time_s",
    "delay_between_runs_s",
    "time_between_patterns_s",
})


def ensure_dirs() -> None:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> Dict[str, Any]:
    ensure_dirs()
    if not SETTINGS_PATH.exists():
        return {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(settings: Dict[str, Any]) -> None:
    ensure_dirs()
    merged = load_settings()
    merged.update(settings)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
