"""OpenCV USB camera capture."""

from __future__ import annotations

import sys
from typing import Optional, Tuple

import cv2
import numpy as np


class OpenCVCamera:
    def __init__(self, index: int = 0, resolution: Tuple[int, int] = (1280, 720), fps: int = 30) -> None:
        self.index = index
        self.resolution = resolution
        self.fps = fps
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> None:
        if sys.platform == "win32":
            self._cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self.index)
        else:
            self._cap = cv2.VideoCapture(self.index)
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError(f"Failed to open camera index {self.index}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> Optional[np.ndarray]:
        if not self.is_open():
            return None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        return frame

    def set_exposure(self, value: float) -> None:
        if not self.is_open():
            return
        self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25 if value >= 0 else 0.75)
        if value >= 0:
            self._cap.set(cv2.CAP_PROP_EXPOSURE, value)

    def set_gain(self, value: float) -> None:
        if not self.is_open():
            return
        self._cap.set(cv2.CAP_PROP_GAIN, float(value))

    def get_gain(self) -> Optional[float]:
        if not self.is_open():
            return None
        return float(self._cap.get(cv2.CAP_PROP_GAIN))

    def actual_resolution(self) -> Tuple[int, int]:
        if not self.is_open():
            return self.resolution
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return w, h
