"""Smoke test for Thorlabs uc480 camera capture."""

from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from camera import list_opencv_devices, list_uc480_cameras
from camera.uc480_source import UC480Camera


def main() -> int:
    print("=== uc480 smoke test ===")
    print("uc480 cameras:", list_uc480_cameras())
    print("opencv devices:", list_opencv_devices())

    cameras = list_uc480_cameras()
    if not cameras:
        print("FAIL: no uc480 camera detected")
        return 1

    cam = UC480Camera(serial=cameras[0]["serial"])
    try:
        cam.open()
        print("OK: opened", cam.device_label(), cam.actual_resolution())
        ok = cam.verify_frames(timeout_s=5.0)
        if not ok:
            print("FAIL: camera opened but no frames in 5 s")
            print("Try: close ThorCam, replug USB, open camera in ThorCam once, remove lens cap")
            return 2
        frame = cam.read()
        print("OK: frame", frame.shape, frame.dtype, f"mean={frame.mean():.1f}")
        out = _ROOT / "_test_uc480_frame.jpg"
        import cv2

        cv2.imwrite(str(out), frame)
        print("OK: saved", out)
        return 0
    finally:
        cam.close()


if __name__ == "__main__":
    raise SystemExit(main())
