"""Pixel scale calibration and config persistence."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CalibrationState:
    mode: str = "pixel_only"  # "two_point" | "pixel_only"
    um_per_pixel: Optional[float] = None
    reference_distance_um: float = 100.0
    point_a: Optional[Tuple[float, float]] = None
    point_b: Optional[Tuple[float, float]] = None

    def is_calibrated(self) -> bool:
        return self.mode == "two_point" and self.um_per_pixel is not None and self.um_per_pixel > 0

    def pixel_distance(self) -> Optional[float]:
        if self.point_a is None or self.point_b is None:
            return None
        dx = self.point_b[0] - self.point_a[0]
        dy = self.point_b[1] - self.point_a[1]
        dist = math.hypot(dx, dy)
        return dist if dist > 0 else None

    def compute_scale(self) -> Optional[float]:
        px = self.pixel_distance()
        if px is None or self.reference_distance_um <= 0:
            return None
        return self.reference_distance_um / px

    def apply_two_point(self) -> bool:
        scale = self.compute_scale()
        if scale is None:
            self.um_per_pixel = None
            return False
        self.um_per_pixel = scale
        self.mode = "two_point"
        return True

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.point_a is not None:
            data["point_a"] = list(self.point_a)
        if self.point_b is not None:
            data["point_b"] = list(self.point_b)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalibrationState":
        point_a = data.get("point_a")
        point_b = data.get("point_b")
        return cls(
            mode=str(data.get("mode", "pixel_only")),
            um_per_pixel=data.get("um_per_pixel"),
            reference_distance_um=float(data.get("reference_distance_um", 100.0)),
            point_a=tuple(point_a) if point_a else None,
            point_b=tuple(point_b) if point_b else None,
        )


@dataclass
class AppConfig:
    camera_backend: str = "uc480"
    camera_index: int = 0
    camera_serial: str = ""
    resolution: List[int] = field(default_factory=lambda: [1280, 720])
    exposure: float = -6.0
    camera_gain: float = 1.0
    gain_boost: bool = False
    calibration: CalibrationState = field(default_factory=CalibrationState)
    roi_half_size_px: int = 30
    background_subtract: bool = True
    analysis_fps: int = 10
    display_zoom: float = 1.0
    click_magnification: float = 8.0
    manual_spot_center: bool = False
    spot_center_x: Optional[float] = None
    spot_center_y: Optional[float] = None
    sensor_roi_width: int = 256
    sensor_roi_height: int = 256
    z_motor_serial: str = "27254172"
    z_motor_scale: int = 34304
    z_min_mm: float = 0.0
    z_max_mm: float = 25.0
    z_jog_step_mm: float = 0.05
    z_speed_mm_s: float = 2.0
    z_accel_mm_s2: float = 3.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_backend": self.camera_backend,
            "camera_index": self.camera_index,
            "camera_serial": self.camera_serial,
            "resolution": self.resolution,
            "exposure": self.exposure,
            "camera_gain": self.camera_gain,
            "gain_boost": self.gain_boost,
            "calibration": self.calibration.to_dict(),
            "stage": {
                "z_motor_serial": self.z_motor_serial,
                "z_motor_scale": self.z_motor_scale,
                "z_min_mm": self.z_min_mm,
                "z_max_mm": self.z_max_mm,
                "z_jog_step_mm": self.z_jog_step_mm,
                "z_speed_mm_s": self.z_speed_mm_s,
                "z_accel_mm_s2": self.z_accel_mm_s2,
            },
            "analysis": {
                "roi_half_size_px": self.roi_half_size_px,
                "background_subtract": self.background_subtract,
                "analysis_fps": self.analysis_fps,
                "display_zoom": self.display_zoom,
                "click_magnification": self.click_magnification,
                "manual_spot_center": self.manual_spot_center,
                "spot_center_x": self.spot_center_x,
                "spot_center_y": self.spot_center_y,
                "sensor_roi_width": self.sensor_roi_width,
                "sensor_roi_height": self.sensor_roi_height,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        analysis = data.get("analysis", {})
        stage = data.get("stage", {})
        cal = CalibrationState.from_dict(data.get("calibration", {}))
        resolution = data.get("resolution", [1280, 720])
        return cls(
            camera_backend=str(data.get("camera_backend", "uc480")),
            camera_index=int(data.get("camera_index", 0)),
            camera_serial=str(data.get("camera_serial", "")),
            resolution=list(resolution),
            exposure=float(data.get("exposure", -6.0)),
            camera_gain=float(data.get("camera_gain", 1.0)),
            gain_boost=bool(data.get("gain_boost", False)),
            calibration=cal,
            roi_half_size_px=int(analysis.get("roi_half_size_px", 30)),
            background_subtract=bool(analysis.get("background_subtract", True)),
            analysis_fps=int(analysis.get("analysis_fps", 10)),
            display_zoom=float(analysis.get("display_zoom", 1.0)),
            click_magnification=float(
                analysis.get(
                    "click_magnification",
                    max(2.0, float(analysis.get("display_zoom", 8.0))),
                )
            ),
            manual_spot_center=bool(analysis.get("manual_spot_center", False)),
            spot_center_x=analysis.get("spot_center_x"),
            spot_center_y=analysis.get("spot_center_y"),
            sensor_roi_width=int(analysis.get("sensor_roi_width", 256)),
            sensor_roi_height=int(analysis.get("sensor_roi_height", 256)),
            z_motor_serial=str(stage.get("z_motor_serial", "27254172")),
            z_motor_scale=int(stage.get("z_motor_scale", 34304)),
            z_min_mm=float(stage.get("z_min_mm", 0.0)),
            z_max_mm=float(stage.get("z_max_mm", 25.0)),
            z_jog_step_mm=float(stage.get("z_jog_step_mm", 0.05)),
            z_speed_mm_s=float(stage.get("z_speed_mm_s", 2.0)),
            z_accel_mm_s2=float(stage.get("z_accel_mm_s2", 3.0)),
        )


def default_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "beam_width_config.json"


def load_config(path: Optional[Path] = None) -> AppConfig:
    cfg_path = path or default_config_path()
    if not cfg_path.exists():
        return AppConfig()
    with open(cfg_path, "r", encoding="utf-8") as f:
        return AppConfig.from_dict(json.load(f))


def save_config(config: AppConfig, path: Optional[Path] = None) -> None:
    cfg_path = path or default_config_path()
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2)
