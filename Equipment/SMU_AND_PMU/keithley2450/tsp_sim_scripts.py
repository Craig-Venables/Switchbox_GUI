"""
Keithley 2450 Script Helpers (Simulation)
=========================================

This module offers a lightweight mirror of ``keithley2450_tsp_scripts`` that
operates on the in-memory ``Keithley2450_TSP_Sim`` driver.  Only a subset of the
original TSP script entry points is implemented – enough to cover common GUI
workflows (pulse → read patterns, potentiation/depression, endurance,
retention, amplitude/width sweeps, etc.).

Any method not yet ported raises ``NotImplementedError`` with a short message so
callers can fall back or skip gracefully.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from Measurements.measurement_services_smu import MeasurementService

from Equipment.SMU_AND_PMU.keithley2450.tsp_sim_controller import (
    Keithley2450_TSP_Sim,
    MemristorParameters,
)
from Equipment.SMU_AND_PMU.keithley2450.tsp_scripts import (
    MAX_CURRENT_LIMIT,
    MAX_DELAY,
    MAX_PULSE_WIDTH,
    MAX_VOLTAGE,
    MIN_CURRENT_LIMIT,
    MIN_DELAY,
    MIN_PULSE_WIDTH,
    MIN_VOLTAGE,
)


class Keithley2450_TSP_Sim_Scripts:
    """Python-native reimplementation of key TSP scripts for the simulator."""

    def __init__(self, tsp_controller: Keithley2450_TSP_Sim) -> None:
        if not isinstance(tsp_controller, Keithley2450_TSP_Sim):
            raise TypeError("Keithley2450_TSP_Sim_Scripts requires a simulation controller")
        self.tsp = tsp_controller
        self.measurement_service = MeasurementService()

    # ------------------------------------------------------------------ #
    # Validation / formatting helpers
    # ------------------------------------------------------------------ #
    def _validate_and_clamp(
        self,
        name: str,
        value: float,
        min_val: float,
        max_val: float,
    ) -> float:
        clamped = max(min_val, min(max_val, value))
        if not math.isclose(clamped, value, rel_tol=1e-12, abs_tol=1e-12):
            print(f"⚠️  WARNING: {name} {value} adjusted to {clamped} "
                  f"(allowed range [{min_val}, {max_val}])")
        return clamped

    def _validate_pulse_width(self, width: float) -> float:
        return self._validate_and_clamp("pulse_width", float(width), MIN_PULSE_WIDTH, MAX_PULSE_WIDTH)

    def _validate_voltage(self, voltage: float) -> float:
        mag = self._validate_and_clamp("voltage", abs(float(voltage)), MIN_VOLTAGE, MAX_VOLTAGE)
        return mag if voltage >= 0 else -mag

    def _validate_current_limit(self, clim: float) -> float:
        return self._validate_and_clamp("current_limit", abs(float(clim)), MIN_CURRENT_LIMIT, MAX_CURRENT_LIMIT)

    def _validate_delay(self, delay: float) -> float:
        return self._validate_and_clamp("delay", float(delay), MIN_DELAY, MAX_DELAY)

    def _format_results(
        self,
        timestamps: Sequence[float],
        voltages: Sequence[float],
        currents: Sequence[float],
        *,
        extras: Optional[Dict[str, Sequence[float]]] = None,
    ) -> Dict[str, List[float]]:
        vol = [float(v) for v in voltages]
        cur = [float(i) for i in currents]
        res = [
            (v / i) if abs(i) > 1e-12 else float("inf")
            for v, i in zip(vol, cur)
        ]
        result: Dict[str, List[float]] = {
            "timestamps": [float(t) for t in timestamps],
            "voltages": vol,
            "currents": cur,
            "resistances": res,
        }
        if extras:
            for key, values in extras.items():
                result[key] = [float(v) for v in values]
        return result

    # ------------------------------------------------------------------ #
    # Script equivalents (implemented subset)
    # ------------------------------------------------------------------ #
    def pulse_read_repeat(
        self,
        pulse_voltage: float = 1.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        delay_between: float = 10e-3,
        num_cycles: int = 10,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        """
        Simulate (Pulse → Read → Delay) × ``num_cycles``.
        """
        pv = self._validate_voltage(pulse_voltage)
        pw = self._validate_pulse_width(pulse_width)
        rv = self._validate_voltage(read_voltage)
        delay = self._validate_delay(delay_between)
        icc = self._validate_current_limit(clim)

        v_arr, c_arr, t_arr = self.measurement_service.run_pulse_measurement(
            keithley=self.tsp,
            pulse_voltage=pv,
            pulse_width_ms=pw * 1e3,
            num_pulses=int(max(1, num_cycles)),
            read_voltage=rv,
            inter_pulse_delay_s=delay,
            icc=icc,
            smu_type="Keithley 2450",
            validate_timing=False,
        )
        return self._format_results(t_arr, v_arr, c_arr)

    def pulse_then_read(
        self,
        pulse_voltage: float = 1.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        delay_after_pulse: float = 1e-3,
        num_cycles: int = 10,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        pv = self._validate_voltage(pulse_voltage)
        pw = self._validate_pulse_width(pulse_width)
        rv = self._validate_voltage(read_voltage)
        delay = self._validate_delay(delay_after_pulse)
        icc = self._validate_current_limit(clim)

        v_arr, c_arr, t_arr = self.measurement_service.run_pulse_measurement(
            keithley=self.tsp,
            pulse_voltage=pv,
            pulse_width_ms=pw * 1e3,
            num_pulses=int(max(1, num_cycles)),
            read_voltage=rv,
            inter_pulse_delay_s=delay,
            icc=icc,
            smu_type="Keithley 2450",
            validate_timing=False,
        )
        return self._format_results(t_arr, v_arr, c_arr)

    def varying_width_pulses(
        self,
        pulse_voltage: float = 1.0,
        pulse_widths: Optional[Iterable[float]] = None,
        pulses_per_width: int = 5,
        read_voltage: float = 0.2,
        delay_between: float = 10e-3,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        widths = list(pulse_widths or [50e-6, 100e-6, 500e-6, 1e-3])
        widths = [self._validate_pulse_width(w) for w in widths]
        pv = self._validate_voltage(pulse_voltage)
        rv = self._validate_voltage(read_voltage)
        delay = self._validate_delay(delay_between)
        icc = self._validate_current_limit(clim)

        all_t: List[float] = []
        all_v: List[float] = []
        all_i: List[float] = []
        labels: List[float] = []
        time_offset = 0.0

        for width in widths:
            v_arr, c_arr, t_arr = self.measurement_service.run_pulse_measurement(
                keithley=self.tsp,
                pulse_voltage=pv,
                pulse_width_ms=width * 1e3,
                num_pulses=int(max(1, pulses_per_width)),
                read_voltage=rv,
                inter_pulse_delay_s=delay,
                icc=icc,
                smu_type="Keithley 2450",
                validate_timing=False,
            )
            shifted_t = [time_offset + t for t in t_arr]
            all_t.extend(shifted_t)
            all_v.extend(v_arr)
            all_i.extend(c_arr)
            labels.extend([width] * len(v_arr))
            if t_arr:
                time_offset = shifted_t[-1] + delay

        return self._format_results(all_t, all_v, all_i, extras={"pulse_widths": labels})

    def potentiation_depression_cycle(
        self,
        set_voltage: float = 2.0,
        reset_voltage: float = -2.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        steps: int = 20,
        num_cycles: int = 1,
        delay_between: float = 10e-3,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        sv = self._validate_voltage(set_voltage)
        rv = self._validate_voltage(reset_voltage)
        pw = self._validate_pulse_width(pulse_width)
        vread = self._validate_voltage(read_voltage)
        delay = self._validate_delay(delay_between)
        icc = self._validate_current_limit(clim)

        phases, currents, times, voltages = self.measurement_service.run_pot_dep(
            keithley=self.tsp,
            set_voltage=sv,
            reset_voltage=rv,
            pulse_width_ms=pw * 1e3,
            cycles=int(max(1, num_cycles)),
            read_voltage=vread,
            relax_s=delay,
            pulses_per_phase=int(max(1, steps)),
            icc=icc,
            smu_type="Keithley 2450",
            return_raw=True,
        )
        return self._format_results(times, voltages, currents, extras={"phase": phases})

    def potentiation_only(
        self,
        set_voltage: float = 2.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        num_pulses: int = 20,
        delay_between: float = 10e-3,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        data = self.potentiation_depression_cycle(
            set_voltage=set_voltage,
            reset_voltage=0.0,
            pulse_width=pulse_width,
            read_voltage=read_voltage,
            steps=num_pulses,
            num_cycles=1,
            delay_between=delay_between,
            clim=clim,
        )
        phases = data.pop("phase", [1] * len(data["timestamps"]))
        mask = [ph >= 0 for ph in phases]
        return self._filter_results(data, mask)

    def depression_only(
        self,
        reset_voltage: float = -2.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        num_pulses: int = 20,
        delay_between: float = 10e-3,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        data = self.potentiation_depression_cycle(
            set_voltage=0.0,
            reset_voltage=reset_voltage,
            pulse_width=pulse_width,
            read_voltage=read_voltage,
            steps=num_pulses,
            num_cycles=1,
            delay_between=delay_between,
            clim=clim,
        )
        phases = data.pop("phase", [-1] * len(data["timestamps"]))
        mask = [ph <= 0 for ph in phases]
        return self._filter_results(data, mask)

    def endurance_test(
        self,
        set_voltage: float = 2.0,
        reset_voltage: float = -2.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        num_cycles: int = 100,
        delay_between: float = 10e-3,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        sv = self._validate_voltage(set_voltage)
        rv = self._validate_voltage(reset_voltage)
        pw = self._validate_pulse_width(pulse_width)
        vread = self._validate_voltage(read_voltage)
        delay = self._validate_delay(delay_between)
        icc = self._validate_current_limit(clim)

        v_arr, c_arr, t_arr = self.measurement_service.run_endurance(
            keithley=self.tsp,
            set_voltage=sv,
            reset_voltage=rv,
            pulse_width_s=pw,
            num_cycles=int(max(1, num_cycles)),
            read_voltage=vread,
            inter_cycle_delay_s=delay,
            icc=icc,
            smu_type="Keithley 2450",
        )
        return self._format_results(t_arr, v_arr, c_arr)

    def retention_test(
        self,
        pulse_voltage: float = 2.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        read_intervals: Optional[Iterable[float]] = None,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        pv = self._validate_voltage(pulse_voltage)
        pw = self._validate_pulse_width(pulse_width)
        rv = self._validate_voltage(read_voltage)
        icc = self._validate_current_limit(clim)
        intervals = list(read_intervals or [1, 10, 100, 1000])

        v_arr, c_arr, t_arr = self.measurement_service.run_retention(
            keithley=self.tsp,
            set_voltage=pv,
            set_time_s=pw,
            read_voltage=rv,
            repeat_delay_s=intervals[0] if intervals else 1.0,
            number=len(intervals),
            icc=icc,
            smu_type="Keithley 2450",
        )
        return self._format_results(t_arr, v_arr, c_arr)

    def voltage_amplitude_sweep(
        self,
        pulse_voltage_start: float = 0.5,
        pulse_voltage_stop: float = 2.5,
        pulse_voltage_step: float = 0.1,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        num_pulses_per_voltage: int = 5,
        delay_between: float = 10e-3,
        reset_voltage: float = -1.0,
        reset_width: float = 1e-3,
        delay_between_voltages: float = 1.0,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        start = self._validate_voltage(pulse_voltage_start)
        stop = self._validate_voltage(pulse_voltage_stop)
        step = float(pulse_voltage_step)
        pw = self._validate_pulse_width(pulse_width)
        rv = self._validate_voltage(read_voltage)
        delay = self._validate_delay(delay_between)
        reset_v = self._validate_voltage(reset_voltage)
        reset_w = self._validate_pulse_width(reset_width)
        icc = self._validate_current_limit(clim)

        v_out, i_out, t_out, _ = self.measurement_service.run_pulsed_iv_sweep(
            keithley=self.tsp,
            start_v=start,
            stop_v=stop,
            step_v=step,
            pulse_width_ms=pw * 1e3,
            vbase=rv,
            inter_step_delay_s=delay_between_voltages,
            icc=icc,
            smu_type="Keithley 2450",
            sweep_type="FS",
            manage_session=True,
        )

        # Between voltage levels, optionally apply a reset pulse.
        if reset_width > 0:
            self.tsp.voltage_pulse(reset_v, reset_w, icc)
            self.tsp.advance_time(delay)

        return self._format_results(t_out, v_out, i_out)

    def ispp_test(
        self,
        start_voltage: float = 0.5,
        voltage_step: float = 0.05,
        max_voltage: float = 3.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        target_resistance: Optional[float] = None,
        resistance_threshold_factor: float = 0.5,
        max_pulses: int = 100,
        delay_between: float = 10e-3,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        start = self._validate_voltage(start_voltage)
        step = float(voltage_step)
        stop = self._validate_voltage(max_voltage)
        pw = self._validate_pulse_width(pulse_width)
        rv = self._validate_voltage(read_voltage)
        icc = self._validate_current_limit(clim)
        target_current = 1.0 / target_resistance if target_resistance else 1e-5

        amps, currents, times = self.measurement_service.run_ispp(
            keithley=self.tsp,
            start_v=start,
            stop_v=stop,
            step_v=step,
            vbase=rv,
            pulse_width_ms=pw * 1e3,
            target_current_a=target_current * resistance_threshold_factor,
            inter_step_delay_s=delay_between,
            icc=icc,
            smu_type="Keithley 2450",
        )
        return self._format_results(times, amps, currents)

    def switching_threshold_test(
        self,
        direction: str = "set",
        start_voltage: float = 0.5,
        voltage_step: float = 0.05,
        max_voltage: float = 3.0,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        resistance_threshold_factor: float = 0.5,
        num_pulses_per_voltage: int = 3,
        delay_between: float = 10e-3,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        v_low = start_voltage if direction.lower() != "reset" else -abs(max_voltage)
        v_high = max_voltage if direction.lower() != "reset" else -abs(start_voltage)
        pw = self._validate_pulse_width(pulse_width)
        rv = self._validate_voltage(read_voltage)
        icc = self._validate_current_limit(clim)
        target_current = 1.0 / resistance_threshold_factor if resistance_threshold_factor else 1e-5

        volts, currents, times = self.measurement_service.run_threshold_search(
            keithley=self.tsp,
            v_low=self._validate_voltage(v_low),
            v_high=self._validate_voltage(v_high),
            vbase=rv,
            pulse_width_ms=pw * 1e3,
            target_current_a=target_current,
            max_iters=max(1, num_pulses_per_voltage),
            icc=icc,
            smu_type="Keithley 2450",
        )
        return self._format_results(times, volts, currents)

    def pulse_train_varying_amplitudes(
        self,
        pulse_voltages: Optional[Iterable[float]] = None,
        pulse_width: float = 100e-6,
        read_voltage: float = 0.2,
        num_repeats: int = 1,
        delay_between: float = 10e-3,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        voltages = [self._validate_voltage(v) for v in (pulse_voltages or [1.0, -1.0])]
        pw = self._validate_pulse_width(pulse_width)
        rv = self._validate_voltage(read_voltage)
        delay = self._validate_delay(delay_between)
        icc = self._validate_current_limit(clim)

        all_v: List[float] = []
        all_i: List[float] = []
        all_t: List[float] = []
        labels: List[float] = []
        time_offset = 0.0

        for _ in range(max(1, num_repeats)):
            for amplitude in voltages:
                v_arr, c_arr, t_arr = self.measurement_service.run_pulse_measurement(
                    keithley=self.tsp,
                    pulse_voltage=amplitude,
                    pulse_width_ms=pw * 1e3,
                    num_pulses=1,
                    read_voltage=rv,
                    inter_pulse_delay_s=delay,
                    icc=icc,
                    smu_type="Keithley 2450",
                    validate_timing=False,
                )
                shifted_t = [time_offset + t for t in t_arr]
                all_t.extend(shifted_t)
                all_v.extend(v_arr)
                all_i.extend(c_arr)
                labels.extend([amplitude] * len(v_arr))
                if t_arr:
                    time_offset = shifted_t[-1] + delay
        return self._format_results(all_t, all_v, all_i, extras={"pulse_voltage": labels})

    def multi_read_only(
        self,
        read_voltage: float = 0.2,
        num_reads: int = 100,
        delay_between: float = 100e-3,
        clim: float = 100e-3,
    ) -> Dict[str, List[float]]:
        rv = self._validate_voltage(read_voltage)
        delay = self._validate_delay(delay_between)
        icc = self._validate_current_limit(clim)

        timestamps: List[float] = []
        voltages: List[float] = []
        currents: List[float] = []
        t = 0.0

        self.tsp.enable_output(True)
        self.tsp.set_voltage(rv, icc)
        for _ in range(max(1, num_reads)):
            self.tsp.advance_time(0.001)
            voltage = self.tsp.measure_voltage()
            current = self.tsp.measure_current()
            timestamps.append(t)
            voltages.append(voltage)
            currents.append(current)
            t += delay
            self.tsp.advance_time(delay)

        self.tsp.set_voltage(0.0, icc)
        self.tsp.enable_output(False)
        return self._format_results(timestamps, voltages, currents)

    # ------------------------------------------------------------------ #
    # Unimplemented helpers fall back with explicit message
    # ------------------------------------------------------------------ #
    def pulse_multi_read(self, *args, **kwargs):
        raise NotImplementedError("pulse_multi_read is not yet implemented for the simulator")

    def relaxation_after_multi_pulse(self, *args, **kwargs):
        raise NotImplementedError("relaxation_after_multi_pulse is not yet implemented for the simulator")

    def relaxation_after_multi_pulse_with_pulse_measurement(self, *args, **kwargs):
        raise NotImplementedError("relaxation_after_multi_pulse_with_pulse_measurement is not yet implemented for the simulator")

    def width_sweep_with_reads(self, *args, **kwargs):
        raise NotImplementedError("width_sweep_with_reads is not yet implemented for the simulator")

    def width_sweep_with_all_measurements(self, *args, **kwargs):
        raise NotImplementedError("width_sweep_with_all_measurements is not yet implemented for the simulator")

    def current_range_finder(self, *args, **kwargs):
        raise NotImplementedError("current_range_finder is not yet implemented for the simulator")

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #
    def _filter_results(self, data: Dict[str, List[float]], mask: List[bool]) -> Dict[str, List[float]]:
        filtered: Dict[str, List[float]] = {}
        for key, values in data.items():
            filtered[key] = [v for v, include in zip(values, mask) if include]
        return filtered


__all__ = [
    "Keithley2450_TSP_Sim_Scripts",
    "MemristorParameters",
]


