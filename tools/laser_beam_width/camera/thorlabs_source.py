"""Optional Thorlabs TLCamera backend via pylablib."""

from __future__ import annotations

import os
from typing import List, Optional

import numpy as np

try:
    import pylablib as pll
    from pylablib.devices import Thorlabs

    THORLABS_AVAILABLE = True
except ImportError:
    THORLABS_AVAILABLE = False


def list_thorlabs_serials() -> List[str]:
    if not THORLABS_AVAILABLE:
        return []
    try:
        return list(Thorlabs.list_cameras_tlcam())
    except Exception:
        return []


class ThorlabsCamera:
    def __init__(self, serial: str = "") -> None:
        self.serial = serial or None
        self._camera = None

    def open(self) -> None:
        if not THORLABS_AVAILABLE:
            raise RuntimeError("pylablib is not installed. pip install pylablib")
        dll_override = os.environ.get("THORLABS_TLCAM_DLL_DIR")
        if dll_override:
            pll.par["devices/dlls/thorlabs_tlcam"] = dll_override
        self._camera = Thorlabs.ThorlabsTLCamera(serial=self.serial)
        self._camera.start_acquisition()

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
        if not self.is_open():
            return None
        try:
            frame = self._camera.get_frame(timeout=1.0)
            if isinstance(frame, tuple) and len(frame) >= 1:
                frame = frame[0]
            arr = np.array(frame)
            if arr.ndim == 2:
                return cv2_gray_to_bgr(arr)
            return arr
        except Exception:
            return None

    def set_exposure(self, value: float) -> None:
        if not self.is_open():
            return
        if value >= 0 and hasattr(self._camera, "set_exposure"):
            try:
                self._camera.set_exposure(value * 1e-6)
            except Exception:
                pass


def cv2_gray_to_bgr(gray: np.ndarray) -> np.ndarray:
    import cv2

    if gray.dtype != np.uint8:
        g = gray.astype(np.float32)
        g = g - g.min()
        mx = g.max()
        if mx > 0:
            g = g / mx * 255.0
        gray = g.astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
