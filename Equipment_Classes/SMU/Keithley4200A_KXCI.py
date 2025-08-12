from __future__ import annotations

import socket
import time
from typing import Optional


class Keithley4200A_KXCI:
    """Moved from Equipment_Classes/Keithley4200A_KXCI.py. See original for full docstring."""

    def __init__(
        self,
        address: str = "192.168.1.100:1225",
        timeout_s: float = 5.0,
        connect: bool = True,
    ) -> None:
        host, port = self._parse_address(address)
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.sock: Optional[socket.socket] = None

        self.cmd_enable_output = "OUTP {enable}"
        self.cmd_set_voltage = "SET_V {voltage} {icc}"
        self.cmd_set_current = "SET_I {current} {vcc}"
        self.cmd_measure_voltage = "MEAS_V?"
        self.cmd_measure_current = "MEAS_I?"

        if connect:
            self._connect()

    def _parse_address(self, address: str):
        if ":" in address:
            host, port_str = address.split(":", 1)
            return host, int(port_str)
        address = address.replace("TCPIP0::", "").replace("::SOCKET", "")
        parts = address.split("::")
        if len(parts) >= 2:
            return parts[0], int(parts[1])
        return address, 1225

    def _connect(self) -> None:
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
            self.sock.settimeout(self.timeout_s)
            time.sleep(0.05)
        except Exception as exc:
            self.sock = None
            raise ConnectionError(f"Failed to connect to 4200A KXCI at {self.host}:{self.port}: {exc}")

    def _send_and_recv(self, cmd: str) -> str:
        if not self.sock:
            raise ConnectionError("Not connected to 4200A KXCI")
        try:
            data = (cmd + "\0").encode("ascii")
            self.sock.sendall(data)
            chunks = []
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                if b"\x00" in chunk:
                    before, _sep, _after = chunk.partition(b"\x00")
                    chunks.append(before)
                    break
                chunks.append(chunk)
                if sum(len(c) for c in chunks) > 1_000_000:
                    break
            return b"".join(chunks).decode(errors="ignore").strip()
        except socket.timeout:
            return ""
        except Exception as exc:
            raise ConnectionError(f"KXCI I/O error: {exc}")

    def set_voltage(self, voltage: float, Icc: float = 1e-3):
        cmd = self.cmd_set_voltage.format(voltage=voltage, icc=Icc)
        return self._send_and_recv(cmd)

    def set_current(self, current: float, Vcc: float = 10.0):
        cmd = self.cmd_set_current.format(current=current, vcc=Vcc)
        return self._send_and_recv(cmd)

    def measure_voltage(self):
        resp = self._send_and_recv(self.cmd_measure_voltage)
        try:
            return float(resp)
        except Exception:
            try:
                return float(str(resp).split("=")[-1])
            except Exception:
                return float("nan")

    def measure_current(self):
        resp = self._send_and_recv(self.cmd_measure_current)
        try:
            return (None, float(resp))
        except Exception:
            try:
                return (None, float(str(resp).split("=")[-1]))
            except Exception:
                return (None, float("nan"))

    def enable_output(self, enable: bool = True):
        cmd = self.cmd_enable_output.format(enable=1 if enable else 0)
        return self._send_and_recv(cmd)

    def shutdown(self):
        try:
            self.set_voltage(0.0, Icc=1e-3)
        except Exception:
            pass
        self.enable_output(False)

    def beep(self, frequency: float = 1000, duration: float = 0.2):
        try:
            return self._send_and_recv(f"BEEP {int(frequency)} {duration}")
        except Exception:
            return None

    def get_idn(self) -> str:
        return f"Keithley 4200A KXCI @ {self.host}:{self.port}"

    def close(self):
        try:
            self.shutdown()
        except Exception:
            pass
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


