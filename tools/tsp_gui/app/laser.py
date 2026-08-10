"""Oxxius laser connection helpers for the TSP GUI."""

from __future__ import annotations

from typing import List, Optional, Tuple

from .config import DEFAULT_LASER_BAUD, DEFAULT_LASER_PORT, DEFAULT_LASER_SAFE_POWER_MW


def list_com_ports() -> List[str]:
    ports: List[str] = []
    try:
        from serial.tools import list_ports

        ports = [p.device for p in list_ports.comports()]
    except Exception:
        pass
    if not ports:
        ports = [DEFAULT_LASER_PORT]
    elif DEFAULT_LASER_PORT not in ports:
        ports = [DEFAULT_LASER_PORT] + ports
    return ports


class LaserConnection:
    """Thin wrapper around OxxiusLaser with safe disconnect."""

    def __init__(self) -> None:
        self.laser = None
        self.port: Optional[str] = None
        self.baud: int = DEFAULT_LASER_BAUD
        self._connected = False

    @property
    def connected(self) -> bool:
        return bool(self._connected and self.laser is not None)

    def connect(
        self,
        port: str,
        baud: int = DEFAULT_LASER_BAUD,
        safe_power_mw: float = DEFAULT_LASER_SAFE_POWER_MW,
    ) -> Tuple[bool, str]:
        port = (port or "").strip()
        if not port:
            return False, "No COM port provided."
        self.disconnect()
        try:
            from Equipment.Laser_Controller.oxxius import OxxiusLaser

            laser = OxxiusLaser(
                port=port,
                baud=int(baud),
                safe_power_mw=safe_power_mw,
                verbose=False,
            )
            try:
                idn = laser.idn()
            except Exception:
                idn = port
            self.laser = laser
            self.port = port
            self.baud = int(baud)
            self._connected = True
            return True, f"Laser connected ({idn})"
        except Exception as e:
            self.laser = None
            self._connected = False
            return False, f"Laser connect failed: {e}"

    def disconnect(self) -> None:
        if self.laser is not None:
            try:
                self.laser.emission_off()
            except Exception:
                pass
            try:
                self.laser.close()
            except Exception:
                pass
        self.laser = None
        self._connected = False

    def emission_on(self) -> Tuple[bool, str]:
        if not self.connected:
            return False, "Laser not connected"
        try:
            self.laser.emission_on()
            return True, "Emission ON"
        except Exception as e:
            return False, str(e)

    def emission_off(self) -> Tuple[bool, str]:
        if not self.connected:
            return False, "Laser not connected"
        try:
            self.laser.emission_off()
            return True, "Emission OFF"
        except Exception as e:
            return False, str(e)

    def set_power_mw(self, power_mw: float) -> Tuple[bool, str]:
        if not self.connected:
            return False, "Laser not connected"
        try:
            self.laser.set_to_digital_power_control(float(power_mw))
            return True, f"Power set to {power_mw} mW"
        except Exception as e:
            try:
                self.laser.set_power(float(power_mw))
                return True, f"Power set to {power_mw} mW (fallback)"
            except Exception as e2:
                return False, f"{e}; {e2}"

    def pulse_on_ms(self, duration_ms: float) -> Tuple[bool, str]:
        if not self.connected:
            return False, "Laser not connected"
        try:
            self.laser.pulse_on_ms(float(duration_ms))
            return True, f"Pulse {duration_ms} ms done"
        except Exception as e:
            return False, str(e)

    def pulse_train(self, n: int, on_ms: float, off_ms: float, power_mw: Optional[float] = None) -> Tuple[bool, str]:
        if not self.connected:
            return False, "Laser not connected"
        try:
            self.laser.pulse_train(int(n), float(on_ms), float(off_ms), power_mw=power_mw)
            return True, f"Pulse train {n}× done"
        except Exception as e:
            return False, str(e)
