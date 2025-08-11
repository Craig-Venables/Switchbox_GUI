from __future__ import annotations

import time
import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple, Optional

import numpy as np


class InstrumentAborted(Exception):
    pass


@dataclass
class MeasurementResult:
    voltage: np.ndarray
    current: np.ndarray
    timestamps: np.ndarray


class MeasurementDriver:
    """Thin driver to wrap a source-measure instrument.

    This class assumes an external instrument providing methods to set voltage/current,
    set compliance, and read current. Replace `instrument` with your own controller
    (e.g., `Keithley2400Controller`) and wire methods appropriately.
    """

    def __init__(self, instrument, abort_flag: Callable[[], bool] | None = None):
        self.instrument = instrument
        self.abort_flag = abort_flag or (lambda: False)

    # --- Low-level helpers ---
    def set_voltage_mode(self, compliance_a: float):
        # For Keithley2400Controller we call apply_voltage via set_voltage(0, Icc)
        self.instrument.set_voltage(0.0, Icc=compliance_a)
        self.instrument.enable_output(True)

    def set_voltage_value(self, voltage_v: float):
        self.instrument.set_voltage(voltage_v)

    def read_current(self) -> float:
        return float(self.instrument.measure_current())

    def disable(self):
        self.instrument.enable_output(False)

    # --- Measurement patterns ---
    def dc_hold(self, voltage_v: float, duration_s: float, sample_hz: int,
                compliance_a: float,
                on_sample: Optional[Callable[[float, float, float], None]] = None) -> MeasurementResult:
        self.set_voltage_mode(compliance_a=compliance_a)
        self.set_voltage_value(voltage_v)
        n = max(1, int(duration_s * sample_hz))
        dt = 1.0 / sample_hz if sample_hz > 0 else duration_s

        voltages: List[float] = []
        currents: List[float] = []
        times: List[float] = []
        t0 = time.perf_counter()
        for i in range(n):
            if self.abort_flag():
                self.disable()
                raise InstrumentAborted()
            v = voltage_v
            i_a = self.read_current()
            t = time.perf_counter() - t0
            voltages.append(v)
            currents.append(i_a)
            times.append(t)
            if on_sample is not None:
                try:
                    on_sample(v, i_a, t)
                except Exception:
                    pass
            time.sleep(dt)
        self.disable()
        return MeasurementResult(np.array(voltages), np.array(currents), np.array(times))

    def triangle_sweep(self, v_min: float, v_max: float, step_v: float, dwell_s: float,
                        cycles: int, compliance_a: float,
                        on_sample: Optional[Callable[[float, float, float], None]] = None) -> MeasurementResult:
        self.set_voltage_mode(compliance_a=compliance_a)
        voltages: List[float] = []
        currents: List[float] = []
        times: List[float] = []
        t0 = time.perf_counter()

        def sweep_once():
            for v in np.concatenate([
                np.arange(0, v_max + step_v, step_v),
                np.arange(v_max, v_min - step_v, -step_v),
                np.arange(v_min, 0 - step_v, step_v)
            ]):
                if self.abort_flag():
                    self.disable()
                    raise InstrumentAborted()
                self.set_voltage_value(float(v))
                time.sleep(dwell_s)
                i_a = self.read_current()
                voltages.append(float(v))
                currents.append(i_a)
                t = time.perf_counter() - t0
                times.append(t)
                if on_sample is not None:
                    try:
                        on_sample(float(v), i_a, t)
                    except Exception:
                        pass

        for _ in range(max(1, cycles)):
            sweep_once()

        self.disable()
        return MeasurementResult(np.array(voltages), np.array(currents), np.array(times))

    # Simple pulse endurance loop: returns list of (i_on, i_off)
    def endurance_pulses(self, set_v: float, reset_v: float, width_s: float,
                          read_v: float, cycles: int, compliance_a: float,
                          on_cycle: Optional[Callable[[int, float, float, float], None]] = None) -> List[Tuple[float, float]]:
        self.set_voltage_mode(compliance_a=compliance_a)
        results: List[Tuple[float, float]] = []
        for idx in range(max(1, cycles)):
            if self.abort_flag():
                break
            # SET
            self.set_voltage_value(set_v)
            time.sleep(width_s)
            # Read ON
            self.set_voltage_value(read_v)
            time.sleep(0.005)
            i_on = self.read_current()
            # RESET
            self.set_voltage_value(reset_v)
            time.sleep(width_s)
            # Read OFF
            self.set_voltage_value(read_v)
            time.sleep(0.005)
            i_off = self.read_current()
            results.append((i_on, i_off))
            if on_cycle is not None:
                try:
                    ratio = (abs(i_on) + 1e-12) / (abs(i_off) + 1e-12)
                    on_cycle(idx + 1, i_on, i_off, ratio)
                except Exception:
                    pass
        self.disable()
        return results

    # Timed reads for retention
    def retention_reads(self, read_v: float, times_s: List[float], compliance_a: float,
                         on_read: Optional[Callable[[float, float], None]] = None) -> List[float]:
        self.set_voltage_mode(compliance_a=compliance_a)
        currents: List[float] = []
        start = time.perf_counter()
        for t_target in times_s:
            if self.abort_flag():
                break
            # Busy wait minimal sleep to target time from start
            while (time.perf_counter() - start) < t_target:
                time.sleep(0.005)
            self.set_voltage_value(read_v)
            time.sleep(0.01)
            i = self.read_current()
            currents.append(i)
            if on_read is not None:
                try:
                    on_read(t_target, i)
                except Exception:
                    pass
        self.disable()
        return currents


