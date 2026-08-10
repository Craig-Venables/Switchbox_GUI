"""
PyVISA driver for the Solartron SI 1260 Impedance/Gain-Phase Analyzer.

Verified on-bench (see diagnose_gpib.py):
  Terminator: CRLF (\\r\\n)
  Measure path: OP2,1 → CZ0 → FR → VA → SI → read
  Response: F,R,X,error,limits  e.g. +1.0000000E+03,-2.59E+08,-1.42E+08,0,00

SW is "sweep enable", NOT a measure-and-return query (1260 manual).
"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence, Tuple

import pyvisa
from pyvisa import constants as visa_const


DEFAULT_GPIB_ADDRESS = "GPIB0::8::INSTR"
DEFAULT_TIMEOUT_MS = 60000
# Bench-verified: manual example uses cr/lf; diagnose passed with CRLF
DEFAULT_TERMINATOR = "crlf"


def list_visa_resources(backend: Optional[str] = None) -> Tuple[str, ...]:
    """Return available VISA resource strings (also prints them for convenience)."""
    rm = pyvisa.ResourceManager() if backend is None else pyvisa.ResourceManager(backend)
    try:
        resources = tuple(rm.list_resources())
    finally:
        rm.close()
    print("Available VISA resources:")
    if resources:
        for r in resources:
            print(f"  {r}")
    else:
        print("  (none found)")
    return resources


def prefer_solartron_address(resources: Sequence[str]) -> str:
    """Pick GPIB0::8 if present, else first GPIB resource, else default."""
    resources = list(resources)
    if DEFAULT_GPIB_ADDRESS in resources:
        return DEFAULT_GPIB_ADDRESS
    for r in resources:
        if "GPIB" in r.upper() and "::8::" in r:
            return r
    for r in resources:
        if r.upper().startswith("GPIB"):
            return r
    return DEFAULT_GPIB_ADDRESS


class Solartron1260:
    """Minimal GPIB control for frequency-point impedance reads on the SI 1260."""

    def __init__(
        self,
        address: str = DEFAULT_GPIB_ADDRESS,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        backend: Optional[str] = None,
        terminator: str = DEFAULT_TERMINATOR,
    ) -> None:
        self.address = address
        self.timeout_ms = int(timeout_ms)
        self.backend = backend
        self.terminator = (terminator or DEFAULT_TERMINATOR).lower().strip()
        self._rm: Optional[pyvisa.ResourceManager] = None
        self._instr = None
        self._configured = False

    @property
    def connected(self) -> bool:
        return self._instr is not None

    def connect(self) -> None:
        """Open the instrument and apply communication settings."""
        if self.connected:
            return
        try:
            self._rm = (
                pyvisa.ResourceManager()
                if self.backend is None
                else pyvisa.ResourceManager(self.backend)
            )
            print("Available VISA resources:")
            for r in self._rm.list_resources():
                print(f"  {r}")
            self._instr = self._rm.open_resource(self.address)
            self._apply_io_settings()
            try:
                self._instr.clear()
            except Exception:
                pass
            time.sleep(0.2)
            self._configured = False
        except Exception as exc:
            self.close()
            raise ConnectionError(
                f"Failed to open Solartron 1260 at {self.address!r}: {exc}\n"
                "Tip: use GPIB0::8::INSTR and Terminator=CRLF (bench-verified)."
            ) from exc

    def _apply_io_settings(self) -> None:
        instr = self._require()
        instr.timeout = self.timeout_ms
        try:
            instr.send_end = True
        except Exception:
            pass
        try:
            instr.query_delay = 0.05
        except Exception:
            pass

        term = self.terminator
        if term in ("eoi", "none", ""):
            instr.write_termination = ""
            instr.read_termination = ""
        elif term in ("lf", "\\n", "\n"):
            instr.write_termination = "\n"
            instr.read_termination = "\n"
        elif term in ("cr", "\\r", "\r"):
            instr.write_termination = "\r"
            instr.read_termination = "\r"
        elif term in ("crlf", "\\r\\n", "cr/lf"):
            instr.write_termination = "\r\n"
            instr.read_termination = "\r\n"
        elif term in (";", "semicolon"):
            instr.write_termination = ";"
            instr.read_termination = ";"
        else:
            instr.write_termination = "\r\n"
            instr.read_termination = "\r\n"

    def set_timeout_ms(self, timeout_ms: int) -> None:
        self.timeout_ms = int(timeout_ms)
        if self._instr is not None:
            self._instr.timeout = self.timeout_ms

    def close(self) -> None:
        """Close the instrument connection safely."""
        if self._instr is not None:
            try:
                self._instr.close()
            except Exception:
                pass
            self._instr = None
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception:
                pass
            self._rm = None
        self._configured = False

    def __enter__(self) -> "Solartron1260":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _require(self):
        if self._instr is None:
            raise RuntimeError("Solartron 1260 is not connected. Call connect() first.")
        return self._instr

    def write(self, cmd: str) -> None:
        self._require().write(cmd)

    def read(self) -> str:
        instr = self._require()
        try:
            return str(instr.read()).strip()
        except pyvisa.VisaIOError as exc:
            if getattr(exc, "error_code", None) != visa_const.StatusCode.error_timeout:
                raise
            raise TimeoutError(
                "VISA timeout while reading from the Solartron 1260.\n"
                "Bench-verified path: Terminator=CRLF, measure with SI (not SW).\n"
                f"Original error: {exc}"
            ) from exc

    def query(self, cmd: str, delay_s: float = 0.0) -> str:
        self.write(cmd)
        if delay_s > 0:
            time.sleep(float(delay_s))
        return self.read()

    def configure(
        self,
        ac_amplitude_v: float = 0.1,
        dc_bias_v: float = 0.0,
        *,
        single_sine: bool = True,
    ) -> None:
        """
        Prepare GPIB data path and generator levels.

        OT1   — GPIB output terminator CR LF + EOI
        OS0   — comma separator
        OP2,1 — send all readings to GPIB
        CZ0   — impedance coordinates R, X
        VA x  — AC amplitude (volts)
        VB x  — DC bias (volts), range about ±40.95 V
        """
        del single_sine  # retained for API compatibility; SI is always single-shot
        for cmd in ("OT1", "OS0", "OP2,1", "CZ0"):
            self.write(cmd)
            time.sleep(0.05)
        self.write(f"VA {float(ac_amplitude_v)}")
        time.sleep(0.05)
        self.set_bias(dc_bias_v)
        self._configured = True

    def set_bias(self, dc_bias_v: float) -> None:
        """VB <v>: set generator DC bias in volts (−40.95 … +40.95)."""
        v = float(dc_bias_v)
        if v < -40.95 or v > 40.95:
            raise ValueError(f"DC bias {v} V out of Solartron range ±40.95 V")
        self.write(f"VB {v}")
        time.sleep(0.1)

    def set_frequency(self, frequency_hz: float) -> None:
        """FR <f>: set the generator / measurement frequency in Hz."""
        self.write(f"FR {float(frequency_hz)}")

    def measure_impedance(self) -> Tuple[float, float]:
        """
        Take one single measurement and return (R, X) in ohms.

        SI — Single measurement (manual §7.6.2 / §8 direct actions).
        Response line: frequency, R, X, error, limits
        """
        if not self._configured:
            self.configure()
        # SI starts the measurement; generator leaves BREAK when measuring
        raw = self.query("SI", delay_s=0.5)
        return parse_rx_response(raw)

    def measure_at_frequency(
        self,
        frequency_hz: float,
        settle_s: float = 0.3,
    ) -> Tuple[float, float]:
        """Set frequency, wait for settle, then SI + read R,X."""
        if not self._configured:
            self.configure()
        self.set_frequency(frequency_hz)
        if settle_s > 0:
            time.sleep(float(settle_s))
        return self.measure_impedance()


def parse_rx_response(raw: str) -> Tuple[float, float]:
    """
    Parse a Solartron ASCII result line into (R, X).

    Manual GPIB format (comma separator): F, a/R, b/X, error, limits
    Legacy 2-value replies are also accepted as R,X.
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("Empty response from Solartron measurement.")
    parts: List[str] = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    numbers: List[float] = []
    for p in parts:
        try:
            numbers.append(float(p))
        except ValueError:
            continue
    if len(numbers) >= 5:
        # F, R, X, error, limits
        return numbers[1], numbers[2]
    if len(numbers) >= 3:
        # F, R, X  (no error fields)
        return numbers[1], numbers[2]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    raise ValueError(f"Could not parse R,X from Solartron response: {raw!r}")


def format_resource_list(resources: Sequence[str]) -> str:
    if not resources:
        return "(none found)"
    return "\n".join(resources)
