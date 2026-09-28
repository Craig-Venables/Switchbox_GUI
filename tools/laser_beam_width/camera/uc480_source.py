"""Thorlabs uc480 / uEye camera via pylablib + ThorCam SDK."""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

try:
    from pylablib.devices import uc480 as uc480_mod

    UC480_AVAILABLE = True
except ImportError:
    UC480_AVAILABLE = False
    uc480_mod = None  # type: ignore


def list_uc480_cameras() -> List[dict]:
    if not UC480_AVAILABLE:
        return []
    try:
        cameras = uc480_mod.list_cameras(backend="uc480")
        return [
            {
                "cam_id": c.cam_id,
                "model": c.model,
                "serial": c.serial_number,
                "in_use": c.in_use,
            }
            for c in cameras
        ]
    except Exception:
        return []


def _to_bgr(frame: np.ndarray) -> np.ndarray:
    from analysis.preprocessing import normalize_frame_shape

    frame = normalize_frame_shape(np.asarray(frame))
    if frame.ndim == 2:
        if frame.dtype != np.uint8:
            arr = frame.astype(np.float32)
            arr -= arr.min()
            mx = arr.max()
            if mx > 0:
                arr = arr / mx * 255.0
            frame = arr.astype(np.uint8)
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.dtype != np.uint8:
        frame = np.clip(frame, 0, 255).astype(np.uint8)
    if frame.shape[2] == 1:
        return cv2.cvtColor(frame[:, :, 0], cv2.COLOR_GRAY2BGR)
    return frame


class UC480Camera:
    """Wrapper for pylablib UC480Camera (ThorCam / uc480.dll)."""

    def __init__(self, cam_id: Optional[int] = None, serial: str = "") -> None:
        self.cam_id = cam_id
        self.serial = serial
        self._camera = None

    def open(self) -> None:
        if not UC480_AVAILABLE:
            raise RuntimeError(
                "pylablib uc480 support is not available. Install pylablib and ThorCam."
            )
        cameras = list_uc480_cameras()
        if not cameras:
            raise RuntimeError(
                "No Thorlabs uc480 camera found. Install ThorCam and check the USB connection."
            )
        target = None
        if self.serial:
            target = next((c for c in cameras if c["serial"] == self.serial), None)
        elif self.cam_id is not None:
            target = next((c for c in cameras if c["cam_id"] == self.cam_id), None)
        else:
            target = cameras[0]

        if target is None:
            raise RuntimeError("Requested uc480 camera was not found.")
        if target["in_use"]:
            raise RuntimeError(
                f"Thorlabs camera {target['model']} (serial {target['serial']}) is already in use.\n"
                "Close ThorCam, this app, or any other program using the camera, then retry."
            )

        self.cam_id = target["cam_id"]
        self.serial = target["serial"]
        # cam_id=0 means "first available camera" in pylablib.
        self._camera = uc480_mod.UC480Camera(cam_id=0)

        try:
            self._camera.set_color_mode("mono8")
        except Exception:
            pass
        try:
            self._camera.set_trigger_mode("int")
        except Exception:
            pass
        self._camera.start_acquisition()

    def verify_frames(self, timeout_s: float = 3.0) -> bool:
        """Return True if at least one frame can be read."""
        import time

        deadline = time.time() + timeout_s
        while time.time() < deadline:
            frame = self._read_raw()
            if frame is not None:
                return True
            time.sleep(0.1)
        return False

    def _read_raw(self) -> Optional[np.ndarray]:
        if not self.is_open():
            return None
        try:
            frame = self._camera.read_newest_image()
            if frame is not None:
                return np.asarray(frame)
            status = self._camera.get_frames_status()
            if status.unread > 0:
                frame = self._camera.read_oldest_image()
                if frame is not None:
                    return np.asarray(frame)
            try:
                frame = self._camera.grab(nframes=1, frame_timeout=0.2)
                if isinstance(frame, tuple):
                    frame = frame[0]
                if frame is not None:
                    return np.asarray(frame)
            except Exception:
                pass
        except Exception:
            pass
        return None

    def close(self) -> None:
        if self._camera is None:
            return
        try:
            self._camera.stop_acquisition()
        except Exception:
            pass
        try:
            self._camera.close()
        except Exception:
            pass
        self._camera = None

    def is_open(self) -> bool:
        return self._camera is not None

    def read(self) -> Optional[np.ndarray]:
        frame = self._read_raw()
        if frame is None:
            return None
        return _to_bgr(frame)

    def set_exposure(self, seconds: float) -> Optional[float]:
        if not self.is_open() or seconds <= 0:
            return None
        try:
            return float(self._camera.set_exposure(seconds))
        except Exception:
            return None

    def get_exposure(self) -> Optional[float]:
        if not self.is_open():
            return None
        try:
            return float(self._camera.get_frame_timings().exposure)
        except Exception:
            return None

    def get_gains(self) -> Optional[Tuple[float, float, float, float]]:
        if not self.is_open():
            return None
        try:
            return tuple(float(v) for v in self._camera.get_gains())
        except Exception:
            return None

    def get_max_gain(self) -> Optional[float]:
        if not self.is_open():
            return None
        try:
            return float(self._camera.get_max_gains()[0])
        except Exception:
            return None

    def set_master_gain(self, gain: float) -> None:
        if not self.is_open():
            return
        try:
            self._camera.set_gains(master=float(gain))
        except Exception:
            pass

    def get_gain_boost(self) -> Optional[bool]:
        if not self.is_open():
            return None
        try:
            return bool(self._camera.get_gain_boost())
        except Exception:
            return None

    def set_gain_boost(self, enabled: bool) -> None:
        if not self.is_open():
            return
        try:
            self._camera.set_gain_boost(bool(enabled))
        except Exception:
            pass

    def read_grayscale(self) -> Optional[np.ndarray]:
        frame = self._read_raw()
        if frame is None:
            return None
        from analysis.preprocessing import normalize_frame_shape

        gray = normalize_frame_shape(frame)
        if gray.dtype == np.uint8:
            return gray
        if gray.dtype == np.uint16:
            return gray
        arr = gray.astype(np.float32)
        if arr.max() <= 255:
            return np.clip(arr, 0, 255).astype(np.uint8)
        return arr

    def actual_resolution(self) -> Tuple[int, int]:
        if not self.is_open():
            return (0, 0)
        try:
            w, h = self._camera.get_detector_size()
            return int(w), int(h)
        except Exception:
            return (0, 0)

    def device_label(self) -> str:
        if not self.is_open():
            return "uc480"
        try:
            info = self._camera.get_device_info()
            return f"{info.model} ({info.serial_number})"
        except Exception:
            return "uc480"

    def set_sensor_roi(
        self,
        center_x: float,
        center_y: float,
        roi_width: int,
        roi_height: int,
    ) -> Tuple[int, int]:
        """Crop the sensor readout (hardware zoom). Returns new (width, height)."""
        if not self.is_open():
            raise RuntimeError("Camera is not open")
        det_w, det_h = self._camera.get_detector_size()
        roi_width = max(64, min(int(roi_width), det_w))
        roi_height = max(64, min(int(roi_height), det_h))
        hstart = max(0, int(round(center_x - roi_width / 2.0)))
        vstart = max(0, int(round(center_y - roi_height / 2.0)))
        hend = min(det_w, hstart + roi_width)
        vend = min(det_h, vstart + roi_height)
        hstart = max(0, hend - roi_width)
        vstart = max(0, vend - roi_height)
        self._camera.stop_acquisition()
        self._camera.set_roi(hstart, hend, vstart, vend)
        self._camera.start_acquisition()
        return self.actual_resolution()

    def reset_sensor_roi(self) -> Tuple[int, int]:
        if not self.is_open():
            raise RuntimeError("Camera is not open")
        det_w, det_h = self._camera.get_detector_size()
        self._camera.stop_acquisition()
        self._camera.set_roi(0, det_w, 0, det_h)
        self._camera.start_acquisition()
        return self.actual_resolution()
