"""
Laser FG Scope GUI — Persistent settings (JSON).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .config import (
    DEFAULT_FG_ADDRESS, DEFAULT_SCOPE_ADDRESS, DEFAULT_4200_ADDRESS,
    DEFAULT_LASER_PORT, DEFAULT_LASER_BAUD,
    DEFAULT_LASER_POWER_MW, DEFAULT_BIAS_V, DEFAULT_BIAS_COMPLIANCE,
    DEFAULT_PULSE_HIGH_V, DEFAULT_PULSE_LOW_V,
    DEFAULT_PULSE_WIDTH_NS, DEFAULT_PULSE_RATE_HZ, DEFAULT_BURST_COUNT,
    DEFAULT_SCOPE_CHANNEL, DEFAULT_TIMEBASE_US, DEFAULT_TRIG_LEVEL_V,
    DEFAULT_VOLTS_PER_DIV, DEFAULT_CAPTURE_WAIT_S,
    DEFAULT_ARB_SAMPLE_RATE_MSPS,
    DEFAULT_SAVE_FOLDER, DEFAULT_AUTO_SAVE,
)

_CONFIG_FILENAME = "laser_fg_scope_config.json"


class ConfigManager:
    """Load and save GUI settings to a JSON file beside this package."""

    _DEFAULTS: Dict[str, Any] = {
        # connections
        "fg_address":     DEFAULT_FG_ADDRESS,
        "scope_address":  DEFAULT_SCOPE_ADDRESS,
        "smu_address":    DEFAULT_4200_ADDRESS,
        "laser_port":     DEFAULT_LASER_PORT,
        "laser_baud":     DEFAULT_LASER_BAUD,
        # laser
        "laser_power_mw": DEFAULT_LASER_POWER_MW,
        # bias
        "bias_v":          DEFAULT_BIAS_V,
        "bias_compliance": DEFAULT_BIAS_COMPLIANCE,
        # FG — simple pulse
        "fg_mode":         "simple",   # "simple" or "arb"
        "pulse_high_v":    DEFAULT_PULSE_HIGH_V,
        "pulse_low_v":     DEFAULT_PULSE_LOW_V,
        "pulse_width_ns":  DEFAULT_PULSE_WIDTH_NS,
        "pulse_rate_hz":   DEFAULT_PULSE_RATE_HZ,
        "burst_count":     DEFAULT_BURST_COUNT,
        # FG — ARB
        "arb_sample_rate_msps": DEFAULT_ARB_SAMPLE_RATE_MSPS,
        "arb_segments":    [["H", 100], ["L", 400]],  # [level, duration_ns]
        # scope
        "scope_channel":   DEFAULT_SCOPE_CHANNEL,
        "timebase_us":     DEFAULT_TIMEBASE_US,
        "trig_level_v":    DEFAULT_TRIG_LEVEL_V,
        "volts_per_div":   DEFAULT_VOLTS_PER_DIV,
        "auto_configure_scope": True,
        "capture_wait_s":  DEFAULT_CAPTURE_WAIT_S,
        # save
        "simple_save_path": DEFAULT_SAVE_FOLDER,
        "auto_save":        DEFAULT_AUTO_SAVE,
    }

    def __init__(self, config_file: str = _CONFIG_FILENAME) -> None:
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        self._path = os.path.join(pkg_dir, config_file)

    def load(self) -> Dict[str, Any]:
        """Return config dict, filling missing keys with defaults.

        Priority (highest first):
          1. Our own saved JSON
          2. Scope values from oscilloscope_pulse_gui saved config
          3. Built-in defaults
        """
        cfg = self._DEFAULTS.copy()

        # Pre-fill scope values from oscilloscope_pulse_gui if we have no saved config yet
        if not os.path.exists(self._path):
            osc_cfg = self._load_oscilloscope_pulse_cfg()
            if osc_cfg:
                # Map oscilloscope_pulse_gui keys → our keys
                if osc_cfg.get("scope_address"):
                    cfg["scope_address"] = osc_cfg["scope_address"]
                if osc_cfg.get("scope_channel"):
                    cfg["scope_channel"] = int(osc_cfg["scope_channel"])
                if osc_cfg.get("trigger_level") is not None:
                    cfg["trig_level_v"] = float(osc_cfg["trigger_level"])
                if osc_cfg.get("timebase_scale") is not None:
                    # oscilloscope_pulse_gui stores seconds/div; we use µs/div
                    cfg["timebase_us"] = float(osc_cfg["timebase_scale"]) * 1e6
                if osc_cfg.get("volts_per_div") is not None:
                    cfg["volts_per_div"] = float(osc_cfg["volts_per_div"])

        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    saved = json.load(fh)
                cfg.update(saved)
            except Exception as exc:
                print(f"[ConfigManager] Could not load config: {exc}")
        return cfg

    @staticmethod
    def _load_oscilloscope_pulse_cfg() -> Dict[str, Any]:
        """Load saved config from oscilloscope_pulse_gui (for scope defaults)."""
        try:
            osc_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "oscilloscope_pulse_gui", "pulse_gui_config.json",
            )
            osc_path = os.path.normpath(osc_path)
            if os.path.exists(osc_path):
                with open(osc_path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
        except Exception:
            pass
        return {}

    def save(self, cfg: Dict[str, Any]) -> None:
        """Write config dict to JSON."""
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh, indent=4)
        except Exception as exc:
            print(f"[ConfigManager] Could not save config: {exc}")
