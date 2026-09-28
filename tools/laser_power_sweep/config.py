"""Persist laser power sweep GUI settings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

CONFIG_PATH = Path(__file__).resolve().parent / "laser_power_sweep_config.json"


@dataclass
class AppConfig:
    control_mode: str = "digital_mw"  # digital_mw | ttl_current_pct
    laser_port: str = "COM4"
    laser_baud: int = 19200
    pm_serial: str = ""
    wavelength_nm: float = 0.0
    save_dir: str = ""
    setpoint_mode: str = "list"  # list | ramp
    setpoint_list: str = "0.5, 1, 2, 5, 10, 20, 30, 40"
    current_list: str = "10, 20, 30, 40, 50, 60, 70, 80, 90, 100"
    ramp_start_mw: float = 0.5
    ramp_step_mw: float = 0.5
    ramp_max_mw: float = 40.0
    ramp_start_pct: float = 10.0
    ramp_step_pct: float = 10.0
    ramp_max_pct: float = 100.0
    abort_threshold_mw: float = 40.0
    max_setpoint_mw: float = 50.0
    max_current_pct: float = 100.0
    settle_s: float = 1.5
    num_samples: int = 10
    sample_interval_s: float = 0.2
    fwhm_um: float = 0.0
    e2_um: float = 0.0
    focus_scan_dir: str = r"C:\Users\ppxcv1\Desktop\laser_fit\on ito"
    focus_scan_z_mm: float = 0.0
    spot_source: str = "manual"  # manual | focus_scan
    meter_zeroed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        cfg = cls()
        int_keys = {"laser_baud", "num_samples"}
        float_keys = {
            "wavelength_nm",
            "ramp_start_mw",
            "ramp_step_mw",
            "ramp_max_mw",
            "ramp_start_pct",
            "ramp_step_pct",
            "ramp_max_pct",
            "abort_threshold_mw",
            "max_setpoint_mw",
            "max_current_pct",
            "settle_s",
            "sample_interval_s",
            "fwhm_um",
            "e2_um",
            "focus_scan_z_mm",
        }
        bool_keys = {"meter_zeroed"}
        for key, value in data.items():
            if not hasattr(cfg, key):
                continue
            if key == "fwhm_x_um" and "fwhm_um" not in data:
                setattr(cfg, "fwhm_um", float(value))
                continue
            if key == "fwhm_y_um":
                continue
            if key in int_keys:
                setattr(cfg, key, int(value))
            elif key in float_keys:
                setattr(cfg, key, float(value))
            elif key in bool_keys:
                setattr(cfg, key, bool(value))
            else:
                setattr(cfg, key, value)
        return cfg


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return AppConfig.from_dict(data)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return AppConfig()


def save_config(config: AppConfig) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2)
