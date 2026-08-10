"""Lightweight sim pulse scripts (no MeasurementService / pymeasure)."""

from __future__ import annotations

import time
from typing import Any, Dict, List


class SimpleSimScripts:
    """Point-by-point pulse patterns on Keithley2450_TSP_Sim for GUI dry-runs."""

    def __init__(self, tsp_controller) -> None:
        self.tsp = tsp_controller

    def pulse_read_repeat(
        self,
        pulse_voltage: float = 1.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        delay_between: float = 10e-3,
        num_cycles: int = 10,
        clim: float = 100e-3,
    ) -> Dict[str, Any]:
        timestamps: List[float] = []
        voltages: List[float] = []
        currents: List[float] = []
        resistances: List[float] = []
        t0 = time.perf_counter()

        self.tsp.set_voltage(read_voltage, clim)
        i0 = self.tsp.measure_current() or 0.0
        timestamps.append(time.perf_counter() - t0)
        voltages.append(read_voltage)
        currents.append(i0)
        resistances.append(read_voltage / i0 if abs(i0) > 1e-18 else float("nan"))

        for _ in range(int(num_cycles)):
            self.tsp.voltage_pulse(pulse_voltage, pulse_width, clim=clim)
            self.tsp.set_voltage(read_voltage, clim)
            i = self.tsp.measure_current() or 0.0
            timestamps.append(time.perf_counter() - t0)
            voltages.append(read_voltage)
            currents.append(i)
            resistances.append(read_voltage / i if abs(i) > 1e-18 else float("nan"))
            if delay_between > 0:
                time.sleep(delay_between)

        try:
            self.tsp.enable_output(False)
        except Exception:
            pass

        return {
            "timestamps": timestamps,
            "voltages": voltages,
            "currents": currents,
            "resistances": resistances,
        }

    def multi_pulse_then_read(
        self,
        pulse_voltage: float = 1.5,
        num_pulses_per_read: int = 10,
        pulse_width: float = 1e-3,
        delay_between_pulses: float = 1e-3,
        read_voltage: float = 0.2,
        num_reads: int = 1,
        delay_between_reads: float = 10e-3,
        num_cycles: int = 5,
        delay_between_cycles: float = 10e-3,
        clim: float = 100e-6,
        **kwargs,
    ) -> Dict[str, Any]:
        timestamps: List[float] = []
        voltages: List[float] = []
        currents: List[float] = []
        resistances: List[float] = []
        t0 = time.perf_counter()
        for _ in range(int(num_cycles)):
            for _p in range(int(num_pulses_per_read)):
                self.tsp.voltage_pulse(pulse_voltage, pulse_width, clim=clim)
                if delay_between_pulses > 0:
                    time.sleep(delay_between_pulses)
            for _r in range(int(num_reads)):
                self.tsp.set_voltage(read_voltage, clim)
                i = self.tsp.measure_current() or 0.0
                timestamps.append(time.perf_counter() - t0)
                voltages.append(read_voltage)
                currents.append(i)
                resistances.append(read_voltage / i if abs(i) > 1e-18 else float("nan"))
                if delay_between_reads > 0:
                    time.sleep(delay_between_reads)
            if delay_between_cycles > 0:
                time.sleep(delay_between_cycles)
        try:
            self.tsp.enable_output(False)
        except Exception:
            pass
        return {
            "timestamps": timestamps,
            "voltages": voltages,
            "currents": currents,
            "resistances": resistances,
        }

    def endurance_test(
        self,
        set_voltage: float = 2.0,
        reset_voltage: float = -2.0,
        pulse_width: float = 1e-3,
        read_voltage: float = 0.3,
        num_cycles: int = 10,
        delay_between: float = 1e-3,
        clim: float = 1e-3,
        **kwargs,
    ) -> Dict[str, Any]:
        set_r: List[float] = []
        reset_r: List[float] = []
        for _ in range(int(num_cycles)):
            self.tsp.voltage_pulse(set_voltage, pulse_width, clim=clim)
            self.tsp.set_voltage(read_voltage, clim)
            i_set = self.tsp.measure_current() or 0.0
            set_r.append(read_voltage / i_set if abs(i_set) > 1e-18 else float("nan"))
            self.tsp.voltage_pulse(reset_voltage, pulse_width, clim=clim)
            self.tsp.set_voltage(read_voltage, clim)
            i_reset = self.tsp.measure_current() or 0.0
            reset_r.append(read_voltage / i_reset if abs(i_reset) > 1e-18 else float("nan"))
            if delay_between > 0:
                time.sleep(delay_between)
        try:
            self.tsp.enable_output(False)
        except Exception:
            pass
        return {"set_resistances": set_r, "reset_resistances": reset_r, "resistances": set_r}

    def multi_read_only(
        self,
        read_voltage: float = 0.2,
        num_reads: int = 20,
        delay_between: float = 10e-3,
        clim: float = 100e-6,
        **kwargs,
    ) -> Dict[str, Any]:
        timestamps: List[float] = []
        currents: List[float] = []
        resistances: List[float] = []
        voltages: List[float] = []
        t0 = time.perf_counter()
        self.tsp.set_voltage(read_voltage, clim)
        for _ in range(int(num_reads)):
            i = self.tsp.measure_current() or 0.0
            timestamps.append(time.perf_counter() - t0)
            currents.append(i)
            voltages.append(read_voltage)
            resistances.append(read_voltage / i if abs(i) > 1e-18 else float("nan"))
            if delay_between > 0:
                time.sleep(delay_between)
        try:
            self.tsp.enable_output(False)
        except Exception:
            pass
        return {
            "timestamps": timestamps,
            "voltages": voltages,
            "currents": currents,
            "resistances": resistances,
        }

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def _fallback(**params):
            # Prefer pulse_read_repeat-like params if present
            if "pulse_voltage" in params or "num_cycles" in params:
                return self.pulse_read_repeat(
                    pulse_voltage=float(params.get("pulse_voltage", params.get("set_voltage", 1.0))),
                    pulse_width=float(params.get("pulse_width", 1e-3)),
                    read_voltage=float(params.get("read_voltage", 0.2)),
                    delay_between=float(params.get("delay_between", params.get("delay_between_pulses", 1e-3))),
                    num_cycles=int(params.get("num_cycles", params.get("num_pulses", 5))),
                    clim=float(params.get("clim", 1e-3)),
                )
            return self.multi_read_only(
                read_voltage=float(params.get("read_voltage", 0.2)),
                num_reads=int(params.get("num_reads", 10)),
                delay_between=float(params.get("delay_between", 1e-3)),
                clim=float(params.get("clim", 1e-3)),
            )

        return _fallback
