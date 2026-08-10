"""
Headless Solartron 1260 sweep engine (no UI).

Callable from the PyQt5 GUI or a future sequence/automation runner.
"""

from __future__ import annotations

import math
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
import pandas as pd

_TOOL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TOOL_DIR.parent.parent
_IMPEDANCE_DIR = _TOOL_DIR.parent / "impedance_analyzer"
for _p in (str(_IMPEDANCE_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from calibration import (  # noqa: E402
    CAP,
    FREQ,
    MAG,
    PHASE,
    apply_open_short_correction,
)

from instrument import (  # noqa: E402
    DEFAULT_GPIB_ADDRESS,
    DEFAULT_TERMINATOR,
    DEFAULT_TIMEOUT_MS,
    Solartron1260,
)

ProgressCallback = Callable[[int, int, dict], None]
CancelFlag = threading.Event


@dataclass
class SweepConfig:
    gpib_address: str = DEFAULT_GPIB_ADDRESS
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    terminator: str = DEFAULT_TERMINATOR  # always CRLF on this bench
    f_start_hz: float = 100.0
    f_stop_hz: float = 1.0e6
    points_per_decade: int = 5
    ac_amplitude_v: float = 0.1
    dc_bias_v: float = 0.0
    settle_s: float = 0.3
    sample_name: str = "sample"
    save_dir: str = ""


def parse_bias_list(
    start_v: float,
    stop_v: float,
    step_v: float,
) -> List[float]:
    """Inclusive linear bias list from start→stop with step (sign follows direction)."""
    start = float(start_v)
    stop = float(stop_v)
    step = float(step_v)
    if step == 0:
        raise ValueError("Bias step cannot be zero.")
    # Auto-correct step sign to move from start toward stop
    if stop >= start and step < 0:
        step = abs(step)
    if stop < start and step > 0:
        step = -abs(step)
    vals: List[float] = []
    x = start
    # Guard against float drift
    for _ in range(10001):
        vals.append(round(x, 6))
        if (step > 0 and x >= stop - 1e-12) or (step < 0 and x <= stop + 1e-12):
            break
        x += step
    else:
        raise ValueError("Bias list too long (>10000 points); check start/stop/step.")
    if vals[-1] != round(stop, 6):
        vals.append(round(stop, 6))
    # Deduplicate while preserving order
    out: List[float] = []
    for v in vals:
        if not out or abs(out[-1] - v) > 1e-9:
            out.append(v)
    return out


@dataclass
class SweepResult:
    """One completed frequency sweep (open, short, or device)."""

    role: str  # "open" | "short" | "device" | "device_only"
    frequencies_hz: np.ndarray
    r_ohm: np.ndarray
    x_ohm: np.ndarray
    cs_f: np.ndarray
    cp_f: np.ndarray
    z_mag_ohm: np.ndarray
    phase_deg: np.ndarray
    config: SweepConfig
    corrected: Optional["SweepResult"] = None
    dc_bias_v: float = 0.0

    def to_dataframe(self) -> pd.DataFrame:
        """DataFrame with SMaRT-style columns used by impedance_analyzer helpers."""
        n = len(self.frequencies_hz)
        return pd.DataFrame(
            {
                FREQ: self.frequencies_hz,
                MAG: self.z_mag_ohm,
                PHASE: self.phase_deg,
                CAP: np.abs(self.cp_f),
                "R_Ohms": self.r_ohm,
                "X_Ohms": self.x_ohm,
                "Cs_F": self.cs_f,
                "Cp_F": self.cp_f,
                "Bias_V": np.full(n, float(self.dc_bias_v)),
            }
        )

    def point_dict(self, index: int) -> dict:
        return {
            "index": index,
            "frequency_hz": float(self.frequencies_hz[index]),
            "r_ohm": float(self.r_ohm[index]),
            "x_ohm": float(self.x_ohm[index]),
            "cs_f": float(self.cs_f[index]),
            "cp_f": float(self.cp_f[index]),
            "z_mag_ohm": float(self.z_mag_ohm[index]),
            "phase_deg": float(self.phase_deg[index]),
        }


@dataclass
class CalibrationStore:
    open_result: Optional[SweepResult] = None
    short_result: Optional[SweepResult] = None
    device_result: Optional[SweepResult] = None


def n_points_from_ppd(f_start: float, f_stop: float, points_per_decade: int) -> int:
    """Total log-spaced points including endpoints: round(ppd × decades) + 1."""
    if points_per_decade < 1:
        raise ValueError("points_per_decade must be >= 1")
    if f_start <= 0 or f_stop <= 0:
        raise ValueError("Frequencies must be positive")
    decades = abs(math.log10(float(f_stop) / float(f_start)))
    n = int(round(points_per_decade * decades)) + 1
    return max(n, 2)


def logspace_frequencies(
    f_start: float,
    f_stop: float,
    points_per_decade: int,
) -> np.ndarray:
    n_points = n_points_from_ppd(f_start, f_stop, points_per_decade)
    return np.logspace(np.log10(f_start), np.log10(f_stop), n_points)


def capacitance_from_rx(
    frequency_hz: float, r_ohm: float, x_ohm: float
) -> tuple[float, float]:
    """
    Series and parallel capacitance from R, X.

    Cs = -1 / (ω X) when X < 0
    Cp = -X / (ω (R² + X²)) when X < 0
    Otherwise NaN (inductive / non-capacitive).
    """
    omega = 2.0 * math.pi * float(frequency_hz)
    if x_ohm < 0 and omega > 0:
        cs = -1.0 / (omega * x_ohm)
        denom = omega * (r_ohm * r_ohm + x_ohm * x_ohm)
        cp = -x_ohm / denom if denom != 0 else float("nan")
        return cs, cp
    return float("nan"), float("nan")


def _arrays_from_points(
    frequencies: List[float],
    r_vals: List[float],
    x_vals: List[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    f = np.asarray(frequencies, dtype=float)
    r = np.asarray(r_vals, dtype=float)
    x = np.asarray(x_vals, dtype=float)
    cs = np.empty_like(f)
    cp = np.empty_like(f)
    for i in range(len(f)):
        cs[i], cp[i] = capacitance_from_rx(f[i], r[i], x[i])
    z_mag = np.hypot(r, x)
    phase = np.rad2deg(np.arctan2(x, r))
    return f, r, x, cs, cp, z_mag, phase


class SweepEngine:
    """Owns the instrument connection and open/short/device calibration store."""

    def __init__(self) -> None:
        self.instrument: Optional[Solartron1260] = None
        self.store = CalibrationStore()
        self._cancel = threading.Event()

    @property
    def connected(self) -> bool:
        return self.instrument is not None and self.instrument.connected

    def connect(self, config: SweepConfig) -> List[str]:
        self.disconnect()
        instr = Solartron1260(
            address=config.gpib_address,
            timeout_ms=config.timeout_ms,
            terminator=DEFAULT_TERMINATOR,  # CRLF only (bench-verified)
        )
        resources: List[str] = []
        try:
            rm = __import__("pyvisa").ResourceManager()
            resources = list(rm.list_resources())
            rm.close()
        except Exception:
            resources = []
        instr.connect()
        try:
            instr.configure(
                ac_amplitude_v=config.ac_amplitude_v,
                dc_bias_v=config.dc_bias_v,
            )
        except Exception as exc:
            instr.close()
            raise ConnectionError(
                f"Opened {config.gpib_address} but setup commands timed out / failed: {exc}\n"
                "Use GPIB0::8::INSTR, CRLF terminator, timeout ≥ 15000 ms."
            ) from exc
        self.instrument = instr
        return resources

    def disconnect(self) -> None:
        if self.instrument is not None:
            self.instrument.close()
            self.instrument = None

    def request_cancel(self) -> None:
        self._cancel.set()

    def clear_cancel(self) -> None:
        self._cancel.clear()

    def clear_calibration(self) -> None:
        self.store = CalibrationStore()

    def run_sweep(
        self,
        config: SweepConfig,
        role: str,
        *,
        progress: Optional[ProgressCallback] = None,
        reconfigure: bool = True,
    ) -> SweepResult:
        """
        Run a log frequency sweep.

        role: "open" | "short" | "device" | "device_only"
        """
        if not self.connected or self.instrument is None:
            raise RuntimeError("Not connected to the Solartron 1260.")

        self.clear_cancel()
        freqs = logspace_frequencies(
            config.f_start_hz, config.f_stop_hz, config.points_per_decade
        )
        instr = self.instrument

        instr.set_timeout_ms(config.timeout_ms)
        if reconfigure:
            instr.configure(
                ac_amplitude_v=config.ac_amplitude_v,
                dc_bias_v=config.dc_bias_v,
            )
        else:
            instr.set_bias(config.dc_bias_v)

        r_vals: List[float] = []
        x_vals: List[float] = []
        f_done: List[float] = []

        try:
            n = len(freqs)
            for i, f in enumerate(freqs):
                if self._cancel.is_set():
                    raise InterruptedError("Sweep cancelled by user.")
                try:
                    r, x = instr.measure_at_frequency(float(f), settle_s=config.settle_s)
                except Exception as exc:
                    raise TimeoutError(
                        f"Timeout/error at f={float(f):.6g} Hz (point {i + 1}/{n}): {exc}"
                    ) from exc
                f_done.append(float(f))
                r_vals.append(float(r))
                x_vals.append(float(x))
                cs, cp = capacitance_from_rx(f, r, x)
                z_mag = math.hypot(r, x)
                phase = math.degrees(math.atan2(x, r))
                if progress is not None:
                    progress(
                        i + 1,
                        n,
                        {
                            "frequency_hz": float(f),
                            "r_ohm": float(r),
                            "x_ohm": float(x),
                            "cs_f": float(cs),
                            "cp_f": float(cp),
                            "z_mag_ohm": float(z_mag),
                            "phase_deg": float(phase),
                            "bias_v": float(config.dc_bias_v),
                        },
                    )
        except Exception:
            # Keep instrument open for retry; caller may disconnect
            raise

        f_arr, r_arr, x_arr, cs_arr, cp_arr, z_arr, ph_arr = _arrays_from_points(
            f_done, r_vals, x_vals
        )
        result = SweepResult(
            role=role,
            frequencies_hz=f_arr,
            r_ohm=r_arr,
            x_ohm=x_arr,
            cs_f=cs_arr,
            cp_f=cp_arr,
            z_mag_ohm=z_arr,
            phase_deg=ph_arr,
            config=config,
            dc_bias_v=float(config.dc_bias_v),
        )

        if role == "open":
            self.store.open_result = result
        elif role == "short":
            self.store.short_result = result
        elif role in ("device", "device_only"):
            if (
                role == "device"
                and self.store.open_result is not None
                and self.store.short_result is not None
            ):
                result.corrected = apply_correction(
                    result, self.store.open_result, self.store.short_result
                )
            self.store.device_result = result

        return result

    def run_bias_series(
        self,
        config: SweepConfig,
        biases_v: List[float],
        role: str = "device_only",
        *,
        progress: Optional[ProgressCallback] = None,
        bias_progress: Optional[Callable[[int, int, float], None]] = None,
    ) -> List[SweepResult]:
        """
        Automation: for each DC bias, set VB and run a full frequency sweep.

        Open/short calibration (if present) is reused for role="device".
        """
        if not biases_v:
            raise ValueError("Bias list is empty.")
        results: List[SweepResult] = []
        n_bias = len(biases_v)
        for bi, bias in enumerate(biases_v):
            if self._cancel.is_set():
                raise InterruptedError("Bias series cancelled by user.")
            if bias_progress is not None:
                bias_progress(bi + 1, n_bias, float(bias))
            cfg = SweepConfig(**{**config.__dict__, "dc_bias_v": float(bias)})
            # Reconfigure on first point; afterward only change VB inside run_sweep
            result = self.run_sweep(
                cfg,
                role,
                progress=progress,
                reconfigure=(bi == 0),
            )
            results.append(result)
        return results


def apply_correction(
    device: SweepResult,
    open_res: SweepResult,
    short_res: SweepResult,
) -> SweepResult:
    """Apply open/short correction; return a SweepResult with corrected Z and C."""
    corrected_df = apply_open_short_correction(
        device.to_dataframe(),
        open_res.to_dataframe(),
        short_res.to_dataframe(),
    )
    f = corrected_df[FREQ].to_numpy(dtype=float)
    mag = corrected_df[MAG].to_numpy(dtype=float)
    phase = corrected_df[PHASE].to_numpy(dtype=float)
    phase_rad = np.deg2rad(phase)
    r = mag * np.cos(phase_rad)
    x = mag * np.sin(phase_rad)
    cs = np.empty_like(f)
    cp = np.empty_like(f)
    for i in range(len(f)):
        cs[i], cp[i] = capacitance_from_rx(f[i], r[i], x[i])
    # Prefer capacitance from correction (admittance) when available
    if CAP in corrected_df.columns:
        cap_mag = np.abs(corrected_df[CAP].to_numpy(dtype=float))
        # Keep sign convention via Cp when X<0 else NaN; use |C| from correction as Cp when finite
        cp = np.where(np.isfinite(cap_mag), cap_mag, cp)

    return SweepResult(
        role="device_corrected",
        frequencies_hz=f,
        r_ohm=r,
        x_ohm=x,
        cs_f=cs,
        cp_f=cp,
        z_mag_ohm=mag,
        phase_deg=phase,
        config=device.config,
        dc_bias_v=float(device.dc_bias_v),
    )


def result_from_rx_arrays(
    role: str,
    frequencies_hz: np.ndarray,
    r_ohm: np.ndarray,
    x_ohm: np.ndarray,
    config: SweepConfig,
) -> SweepResult:
    f, r, x, cs, cp, z, ph = _arrays_from_points(
        list(map(float, frequencies_hz)),
        list(map(float, r_ohm)),
        list(map(float, x_ohm)),
    )
    return SweepResult(
        role=role,
        frequencies_hz=f,
        r_ohm=r,
        x_ohm=x,
        cs_f=cs,
        cp_f=cp,
        z_mag_ohm=z,
        phase_deg=ph,
        config=config,
        dc_bias_v=float(config.dc_bias_v),
    )


def bias_tag(bias_v: float) -> str:
    """Filesystem-safe bias label, e.g. VB+1.500 / VB-0.250."""
    return f"VB{bias_v:+.3f}".replace("+", "p").replace("-", "m")
