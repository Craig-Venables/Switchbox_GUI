"""Camera discovery helpers."""

from __future__ import annotations

import sys
from typing import List

import cv2

from .opencv_source import OpenCVCamera
from .thorlabs_source import THORLABS_AVAILABLE, list_thorlabs_serials
from .uc480_source import UC480_AVAILABLE, list_uc480_cameras


def list_opencv_devices(max_index: int = 6) -> List[dict]:
    devices: List[dict] = []
    try:
        from pygrabber.dshow_graph import FilterGraph

        names = FilterGraph().get_input_devices()
        for index, name in enumerate(names):
            devices.append({"index": index, "name": name, "backend": "opencv"})
        return devices
    except ImportError:
        pass

    for index in range(max_index):
        if sys.platform == "win32":
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(index)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            devices.append(
                {
                    "index": index,
                    "name": f"Camera {index} ({w}×{h})",
                    "backend": "opencv",
                }
            )
        cap.release()
    return devices


def recommend_backend() -> str:
    uc480 = list_uc480_cameras()
    if uc480:
        return "uc480"
    if list_opencv_devices():
        return "opencv"
    if THORLABS_AVAILABLE and list_thorlabs_serials():
        return "thorlabs"
    return "uc480"
