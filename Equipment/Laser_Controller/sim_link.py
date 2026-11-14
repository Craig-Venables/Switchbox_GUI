"""Shared state between the laser simulator and the 4200 SMU simulator.

Optical tests turn the laser on and off on one thread while the SMU samples
current on another. Both simulators read and write this object so a laser
pulse changes the current the SMU reports. No hardware is touched.
"""

from __future__ import annotations

import threading


class LaserLink:
    """Thread-safe laser emission flag and power setpoint (mW)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._emitting = False
        self._power_mw = 0.0

    def set_power_mw(self, power_mw: float) -> None:
        with self._lock:
            self._power_mw = float(power_mw)

    def set_emitting(self, emitting: bool, power_mw: float | None = None) -> None:
        with self._lock:
            self._emitting = bool(emitting)
            if power_mw is not None:
                self._power_mw = float(power_mw)

    def snapshot(self) -> tuple[bool, float]:
        """Return ``(emitting, power_mw)``."""
        with self._lock:
            return self._emitting, self._power_mw


_link = LaserLink()


def get_laser_link() -> LaserLink:
    """Process-wide link used by the laser simulator and the 4200 SMU simulator."""
    return _link
