"""Hardware drivers for Tylan FC-2901V mass flow controller.

The FC-2901V uses a 15-pin D-sub ANALOG interface — there is no RS-232.
Refer to config.json for the full pinout.  Two backends are provided:

  NIDAQDriver   – NI USB-6001 (or any NI-DAQmx-compatible board)
  ArduinoDriver – Arduino running tools/MASS_FLOW/arduino_firmware/firmware.ino

Switch backends by editing "driver" in config.json (or via the dashboard UI).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional


class DriverError(RuntimeError):
    """Raised on driver-level hardware or communication failures."""


class AbstractMFCDriver(ABC):
    """Minimal interface every backend must implement."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def set_setpoint_sccm(self, value: float) -> None: ...

    @abstractmethod
    def read_flow_sccm(self) -> float: ...

    @abstractmethod
    def set_output_enabled(self, enabled: bool) -> None:
        """Enable (valve open / control mode) or disable (valve closed)."""

    @staticmethod
    @abstractmethod
    def list_devices() -> List[str]:
        """Return available device identifiers for UI enumeration."""


# ---------------------------------------------------------------------------
# NI-DAQmx backend
# ---------------------------------------------------------------------------

class NIDAQDriver(AbstractMFCDriver):
    """NI-DAQmx backend.

    Uses:
      - One AO channel  → 0-5 V setpoint to MFC pin 5
      - One AI channel  ← 0-5 V flow signal from MFC pin 9
      - One DIO channel → TTL valve-OFF to MFC pin 14
                          (True = valve enabled; False = valve closed)
    """

    def __init__(
        self,
        device_name: str = "Dev1",
        ao_channel: str = "ao0",
        ai_channel: str = "ai0",
        do_valve_off_channel: str = "port0/line0",
        full_scale_sccm: float = 200.0,
    ) -> None:
        self.device_name = device_name
        self.ao_channel = ao_channel
        self.ai_channel = ai_channel
        self.do_valve_off_channel = do_valve_off_channel
        self.full_scale_sccm = float(full_scale_sccm)

        self._ao_task = None
        self._ai_task = None
        self._do_task = None
        self._connected = False

    @staticmethod
    def list_devices() -> List[str]:
        try:
            import nidaqmx
            system = nidaqmx.system.System.local()
            return [dev.name for dev in system.devices]
        except Exception:
            return []

    def connect(self) -> None:
        try:
            import nidaqmx
            from nidaqmx.constants import TerminalConfiguration

            if self._connected:
                self.close()

            ao_path = f"{self.device_name}/{self.ao_channel}"
            ai_path = f"{self.device_name}/{self.ai_channel}"
            do_path = f"{self.device_name}/{self.do_valve_off_channel}"

            self._ao_task = nidaqmx.Task()
            self._ao_task.ao_channels.add_ao_voltage_chan(
                ao_path, min_val=0.0, max_val=5.0
            )
            self._ao_task.start()
            self._ao_task.write(0.0)  # setpoint = 0 on connect

            self._ai_task = nidaqmx.Task()
            self._ai_task.ai_channels.add_ai_voltage_chan(
                ai_path,
                terminal_config=TerminalConfiguration.RSE,
                min_val=0.0,
                max_val=5.0,
            )

            self._do_task = nidaqmx.Task()
            self._do_task.do_channels.add_do_chan(do_path)
            self._do_task.start()
            self._do_task.write(True)  # valve enabled on connect

            self._connected = True

        except DriverError:
            raise
        except Exception as exc:
            self.close()
            raise DriverError(f"NI-DAQmx connect failed: {exc}") from exc

    def close(self) -> None:
        for task in (self._ao_task, self._ai_task, self._do_task):
            try:
                if task is not None:
                    task.close()
            except Exception:
                pass
        self._ao_task = None
        self._ai_task = None
        self._do_task = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _sccm_to_voltage(self, sccm: float) -> float:
        return max(0.0, min(float(sccm) / self.full_scale_sccm * 5.0, 5.0))

    def _voltage_to_sccm(self, voltage: float) -> float:
        return max(0.0, float(voltage) / 5.0 * self.full_scale_sccm)

    def set_setpoint_sccm(self, value: float) -> None:
        if not self._connected:
            raise DriverError("Not connected.")
        self._ao_task.write(self._sccm_to_voltage(value))

    def read_flow_sccm(self) -> float:
        if not self._connected:
            raise DriverError("Not connected.")
        try:
            voltage = float(self._ai_task.read())
        except Exception as exc:
            raise DriverError(f"AI read failed: {exc}") from exc
        return self._voltage_to_sccm(voltage)

    def set_output_enabled(self, enabled: bool) -> None:
        if not self._connected:
            raise DriverError("Not connected.")
        self._do_task.write(bool(enabled))


# ---------------------------------------------------------------------------
# Arduino backend
# ---------------------------------------------------------------------------

class ArduinoDriver(AbstractMFCDriver):
    """Arduino firmware serial backend.

    The Arduino mediates between the PC and the FC-2901V analog signals using:
      - MCP4725 I2C DAC (12-bit) for 0-5 V setpoint output
      - analogRead  (10-bit)     for 0-5 V flow input
      - digital pin              for valve-OFF TTL

    Firmware: tools/MASS_FLOW/arduino_firmware/firmware.ino

    Serial protocol (115200 8N1, \\r\\n terminated):
      S:<sccm>\\r\\n   -> set setpoint; Arduino replies OK\\r\\n
      R\\r\\n           -> read flow;    Arduino replies F:<sccm>\\r\\n
      O:<0|1>\\r\\n    -> valve-off;    Arduino replies OK\\r\\n  (0=close, 1=normal)
      ?\\r\\n           -> identity;     Arduino replies FC2901V_CTRL\\r\\n
    """

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 115200,
        timeout_s: float = 0.5,
        full_scale_sccm: float = 200.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout_s = timeout_s
        self.full_scale_sccm = float(full_scale_sccm)
        self._serial = None

    @staticmethod
    def list_devices() -> List[str]:
        try:
            from serial.tools import list_ports
            return [p.device for p in list_ports.comports()]
        except Exception:
            return []

    def connect(self) -> None:
        import serial as _serial_module
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._serial = _serial_module.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout_s,
                write_timeout=self.timeout_s,
            )
            import time
            time.sleep(2.0)  # wait for Arduino reset after DTR toggle
            self._serial.reset_input_buffer()
            self._serial.write(b"?\r\n")
            response = self._serial.readline().decode("ascii", errors="ignore").strip()
            if "FC2901V_CTRL" not in response:
                self._serial.close()
                self._serial = None
                raise DriverError(
                    f"Unexpected Arduino response: {response!r}. "
                    "Expected 'FC2901V_CTRL'. Check firmware and port."
                )
        except DriverError:
            raise
        except Exception as exc:
            if self._serial:
                try:
                    self._serial.close()
                except Exception:
                    pass
                self._serial = None
            raise DriverError(f"Arduino connect failed: {exc}") from exc

    def close(self) -> None:
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None

    @property
    def is_connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def _send(self, cmd: str) -> str:
        if not self.is_connected:
            raise DriverError("Not connected.")
        self._serial.write(f"{cmd}\r\n".encode("ascii"))
        return self._serial.readline().decode("ascii", errors="ignore").strip()

    def set_setpoint_sccm(self, value: float) -> None:
        clamped = max(0.0, min(float(value), self.full_scale_sccm))
        resp = self._send(f"S:{clamped:.3f}")
        if not resp.startswith("OK"):
            raise DriverError(f"Setpoint command failed: {resp!r}")

    def read_flow_sccm(self) -> float:
        resp = self._send("R")
        if not resp.startswith("F:"):
            raise DriverError(f"Unexpected flow response: {resp!r}")
        return float(resp[2:])

    def set_output_enabled(self, enabled: bool) -> None:
        resp = self._send(f"O:{'1' if enabled else '0'}")
        if not resp.startswith("OK"):
            raise DriverError(f"Valve command failed: {resp!r}")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_driver_from_config(config: dict) -> AbstractMFCDriver:
    driver_type = str(config.get("driver", "nidaq")).lower()
    full_scale = float(config.get("full_scale_sccm", 200.0))

    if driver_type == "nidaq":
        ni = config.get("nidaq", {})
        return NIDAQDriver(
            device_name=ni.get("device_name", "Dev1"),
            ao_channel=ni.get("ao_setpoint_channel", "ao0"),
            ai_channel=ni.get("ai_flow_channel", "ai0"),
            do_valve_off_channel=ni.get("do_valve_off_channel", "port0/line0"),
            full_scale_sccm=full_scale,
        )
    elif driver_type == "arduino":
        ard = config.get("arduino", {})
        return ArduinoDriver(
            port=ard.get("port", "COM3"),
            baudrate=int(ard.get("baudrate", 115200)),
            timeout_s=float(ard.get("timeout_s", 0.5)),
            full_scale_sccm=full_scale,
        )
    else:
        raise ValueError(
            f"Unknown driver type {driver_type!r}. Use 'nidaq' or 'arduino'."
        )


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config_path: Path, config: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
