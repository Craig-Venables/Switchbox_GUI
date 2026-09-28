"""Thorlabs Kinesis Z axis for focus — lazy connect, no TLCamera import."""

from __future__ import annotations

import threading
from typing import Optional, Tuple

try:
    from pylablib.devices.Thorlabs.kinesis import KinesisMotor, list_kinesis_devices

    KINESIS_AVAILABLE = True
except ImportError:
    KinesisMotor = None  # type: ignore
    list_kinesis_devices = None  # type: ignore
    KINESIS_AVAILABLE = False


def list_stage_motors() -> list[tuple[str, str]]:
    """Return [(serial, description), ...] for connected Kinesis devices."""
    if not KINESIS_AVAILABLE or list_kinesis_devices is None:
        return []
    try:
        return [(str(serial), str(desc)) for serial, desc in list_kinesis_devices()]
    except Exception:
        return []


class ZMotorController:
    """Single-axis Z motor wrapper (connect only when requested)."""

    def __init__(
        self,
        serial: str,
        scale: int = 34304,
        z_min_mm: float = 0.0,
        z_max_mm: float = 25.0,
        speed_mm_s: float = 2.0,
        accel_mm_s2: float = 3.0,
    ) -> None:
        self.serial = serial.strip()
        self.scale = scale
        self.z_min_mm = z_min_mm
        self.z_max_mm = z_max_mm
        self.speed_mm_s = speed_mm_s
        self.accel_mm_s2 = accel_mm_s2
        self._motor: Optional[KinesisMotor] = None
        self._error: Optional[str] = None
        self._lock = threading.RLock()
        self._stop_requested = False

    def is_connected(self) -> bool:
        return self._motor is not None

    def last_error(self) -> Optional[str]:
        return self._error

    def connect(self) -> None:
        if not KINESIS_AVAILABLE:
            raise RuntimeError("pylablib Kinesis support is not available")
        if not self.serial:
            raise RuntimeError("Z motor serial is not configured")
        if self._motor is not None:
            return
        try:
            motor = KinesisMotor(self.serial, scale=self.scale)
            motor.setup_velocity(max_velocity=self.speed_mm_s, acceleration=self.accel_mm_s2)
            self._motor = motor
            self._error = None
        except Exception as exc:
            self._motor = None
            self._error = str(exc)
            hint = _connect_error_hint(self.serial, exc)
            raise RuntimeError(hint) from exc

    def disconnect(self) -> None:
        with self._lock:
            if self._motor is not None:
                try:
                    self._motor.close()
                except Exception:
                    pass
            self._motor = None

    def apply_motion(self, speed_mm_s: float, accel_mm_s2: float) -> None:
        self.speed_mm_s = speed_mm_s
        self.accel_mm_s2 = accel_mm_s2
        with self._lock:
            if self._motor is not None:
                self._motor.setup_velocity(max_velocity=speed_mm_s, acceleration=accel_mm_s2)

    def get_position_mm(self) -> Optional[float]:
        with self._lock:
            if self._motor is None:
                return None
            try:
                return float(self._motor.get_position())
            except Exception as exc:
                self._error = str(exc)
                return None

    def stop(self) -> None:
        self._stop_requested = True
        with self._lock:
            if self._motor is not None:
                try:
                    self._motor.stop()
                except Exception:
                    pass

    def move_relative_mm(self, delta_mm: float) -> None:
        with self._lock:
            motor = self._motor
            if motor is None:
                raise RuntimeError("Z motor is not connected")
            current = float(motor.get_position())
            target = current + delta_mm
            if target < self.z_min_mm - 1e-6 or target > self.z_max_mm + 1e-6:
                raise ValueError(f"Z target {target:.3f} mm out of range [{self.z_min_mm}, {self.z_max_mm}]")
            self._stop_requested = False
            motor.move_by(delta_mm)
            while motor.is_moving():
                if self._stop_requested:
                    motor.stop()
                    return

    def home(self) -> None:
        with self._lock:
            motor = self._motor
            if motor is None:
                raise RuntimeError("Z motor is not connected")
            self._stop_requested = False
            motor.home()
            motor.wait_move()
            end_z = float(motor.get_position())
            if abs(end_z - self.z_min_mm) > 0.01:
                delta = self.z_min_mm - end_z
                motor.move_by(delta)
                while motor.is_moving():
                    if self._stop_requested:
                        motor.stop()
                        return

    def state(self) -> Tuple[bool, str]:
        if self.is_connected():
            return True, "Connected"
        return False, self._error or "Not connected"


def _connect_error_hint(serial: str, exc: Exception) -> str:
    msg = str(exc).strip()
    available = list_stage_motors()
    if available:
        devices = ", ".join(f"{s} ({d})" for s, d in available)
        on_bus = any(s == serial for s, _ in available)
        if not on_bus:
            return (
                f"Motor {serial} not found on USB.\n\n"
                f"Connected now: {devices}\n\n"
                "Click Scan motors and pick the Z axis serial, or check power/USB."
            )
    if "Device Not Opened" in msg or "D2XX" in msg:
        return (
            f"Could not open motor {serial} ({msg}).\n\n"
            "Close Kenisis / Kinesis apps if open, then retry."
        )
    return f"Could not connect to {serial}: {msg}"
