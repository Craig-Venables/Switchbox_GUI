"""
Thorlabs PM100D Laser Power Meter Controller

Controls a Thorlabs PM100D power meter via USB using PyVISA and SCPI.
Default device: PM100D with serial number P0031757.

Supports:
- Power measurement (W or mW)
- Wavelength setting/query for sensor correction
- Identity and status queries
- Context manager (with block) for connection lifecycle

Requires: pyvisa, and NI-VISA or pyvisa-py backend.
"""

from __future__ import annotations

import pyvisa
from typing import Optional

# Thorlabs USB VID/PID for PM100D
THORLABS_PM100_VID = "0x1313"
THORLABS_PM100_PID = "0x8078"

# Default serial number for this lab unit
DEFAULT_SERIAL = "P0031757"


def make_pm100d_resource(serial: str = DEFAULT_SERIAL) -> str:
    """Build VISA resource string for a Thorlabs PM100D by serial number."""
    return f"USB0::{THORLABS_PM100_VID}::{THORLABS_PM100_PID}::{serial}::INSTR"


class PM100D:
    """
    Controller for Thorlabs PM100D laser power meter (SCPI over USB).
    """

    def __init__(
        self,
        resource: Optional[str] = None,
        serial: Optional[str] = None,
        timeout_ms: int = 5000,
    ):
        """
        Initialize the PM100D controller (does not connect until connect() is called).

        Args:
            resource: Full VISA resource string (e.g. 'USB0::0x1313::0x8078::P0031757::INSTR').
                      If None, uses serial to build resource (default serial P0031757).
            serial: Serial number (e.g. 'P0031757'). Ignored if resource is set.
            timeout_ms: VISA I/O timeout in milliseconds.
        """
        if resource is not None:
            self.resource = resource
        else:
            self.resource = make_pm100d_resource(serial or DEFAULT_SERIAL)
        self.timeout_ms = timeout_ms
        self._rm: Optional[pyvisa.ResourceManager] = None
        self._inst: Optional[pyvisa.resources.MessageBasedResource] = None

    def connect(self, resource: Optional[str] = None) -> bool:
        """
        Open connection to the power meter.

        Args:
            resource: Optional override for VISA resource. If provided, updates self.resource.

        Returns:
            True if connection and IDN query succeed, False otherwise.
        """
        if resource is not None:
            self.resource = resource
        try:
            self._rm = pyvisa.ResourceManager()
            self._inst = self._rm.open_resource(self.resource)
            self._inst.timeout = self.timeout_ms
            self._inst.write_termination = "\n"
            self._inst.read_termination = "\n"
            # Verify communication
            self._inst.query("*IDN?")
            return True
        except pyvisa.errors.VisaIOError as e:
            if self._rm:
                try:
                    self._rm.close()
                except Exception:
                    pass
            self._rm = None
            self._inst = None
            raise RuntimeError(
                f"Failed to connect to PM100D at {self.resource}: {e}"
            ) from e

    def close(self) -> None:
        """Close the VISA connection and release the resource manager."""
        if self._inst:
            try:
                self._inst.close()
            except Exception:
                pass
            self._inst = None
        if self._rm:
            try:
                self._rm.close()
            except Exception:
                pass
            self._rm = None

    def _query(self, cmd: str) -> str:
        """Send SCPI query and return response string."""
        if self._inst is None:
            raise RuntimeError("PM100D not connected; call connect() first.")
        return self._inst.query(cmd).strip()

    def _write(self, cmd: str) -> None:
        """Send SCPI command (no response)."""
        if self._inst is None:
            raise RuntimeError("PM100D not connected; call connect() first.")
        self._inst.write(cmd)

    def __enter__(self) -> "PM100D":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------- Identity and status -------------------------

    def idn(self) -> str:
        """Return instrument identification (*IDN?)."""
        return self._query("*IDN?")

    # ------------------------- Power measurement -------------------------

    def measure_power_w(self) -> float:
        """
        Perform a power measurement and return value in watts.

        Returns:
            Power in watts (float).
        """
        return float(self._query("MEASure:POWer?"))

    def measure_power_mw(self) -> float:
        """
        Perform a power measurement and return value in milliwatts.

        Returns:
            Power in mW (float).
        """
        return self.measure_power_w() * 1000.0

    # ------------------------- Wavelength (sensor correction) -------------------------

    def get_wavelength_nm(self) -> float:
        """Return current wavelength setting for power correction (nm)."""
        return float(self._query("SENSe:CORRection:WAVelength?"))

    def set_wavelength_nm(self, nm: float) -> None:
        """Set wavelength for power correction (photodiode response)."""
        self._write(f"SENSe:CORRection:WAVelength {nm}")

    # ------------------------- Configuration (optional) -------------------------

    def configure_power(self) -> None:
        """Configure the meter for power measurement (CONFigure:POWer)."""
        self._write("CONFigure:POWer")

    def zero(self) -> None:
        """Perform zero calibration (zero the sensor with no light)."""
        self._write("CALibration:ZERO")


def find_pm100d_resource(serial: Optional[str] = None) -> Optional[str]:
    """
    Search for a PM100D on USB and return its VISA resource string.

    Args:
        serial: If provided, match this serial number (e.g. 'P0031757'); otherwise
                return the first PM100D found.

    Returns:
        Resource string if found, else None.
    """
    try:
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
    except Exception:
        return None
    target_serial = (serial or DEFAULT_SERIAL).upper()
    if not target_serial.startswith("P"):
        target_serial = "P" + target_serial
    for r in resources:
        if "0x1313" in r and "0x8078" in r and "INSTR" in r:
            if serial is None:
                return r
            # Resource format: ...::P0031757::INSTR
            if target_serial in r.upper():
                return r
    return None


if __name__ == "__main__":
    # Simple test: connect, read current power, print it
    resource = find_pm100d_resource()
    if not resource:
        print("No PM100D found on USB.")
        raise SystemExit(1)
    with PM100D(resource=resource) as pm:
        print("IDN:", pm.idn())
        power_mw = pm.measure_power_mw()
        print(f"Current power: {power_mw:.4f} mW")
