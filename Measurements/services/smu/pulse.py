from __future__ import annotations

import time
from typing import Callable, Iterable, List, Optional, Tuple

from Measurements.sweep_config import SweepConfig

from .limits import VoltageRangeMode


class PulseSessionMixin:
    def begin_pulse_session(
        self,
        keithley,
        icc: float,
        *,
        v_range: float = 20.0,
        ovp: float = 21.0,
        use_remote_sense: bool = False,
        autozero_off: bool = True,
    ) -> None:
        """Prepare SMU once for a batch of pulses; caller should later call end_pulse_session."""
        try:
            keithley.prepare_for_pulses(
                Icc=float(icc),
                v_range=float(v_range),
                ovp=float(ovp),
                use_remote_sense=bool(use_remote_sense),
                autozero_off=bool(autozero_off),
            )
        except Exception:
            pass

    def end_pulse_session(
        self,
        keithley,
        icc: float,
        *,
        restore_autozero: bool = True,
    ) -> None:
        """Finish a pulse batch: return to 0 V, optionally restore autozero, disable output."""
        try:
            keithley.finish_pulses(Icc=float(icc), restore_autozero=bool(restore_autozero))
        except Exception:
            pass


class PulseMeasurementMixin:
    def run_pulse_measurement(
        self,
        *,
        keithley,
        pulse_voltage: float,
        pulse_width_ms: float,
        num_pulses: int,
        read_voltage: float = 0.1,
        inter_pulse_delay_s: float = 0.01,
        icc: float = 1e-4,
        smu_type: str = "Keithley 4200A",
        psu=None,
        led: bool = False,
        power: float = 1.0,
        optical=None,
        sequence: Optional[Iterable[str]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        validate_timing: bool = True,
        start_at_zero: bool = True,
        return_to_zero_at_end: bool = True,
        reset_should_stop: Optional[Callable[[], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Run pulse measurement using the unified API.

        Delegates to keithley.do_pulse_measurement() which routes to
        instrument-specific implementations automatically.
        """

        # Convert sequence to list if provided
        sequence_list = None
        if sequence is not None:
            try:
                sequence_list = list(sequence)
            except Exception:
                sequence_list = None

        # Use unified API
        if hasattr(keithley, "do_pulse_measurement"):
            return keithley.do_pulse_measurement(
                pulse_voltage=float(pulse_voltage),
                pulse_width_ms=float(pulse_width_ms),
                num_pulses=int(num_pulses),
                read_voltage=float(read_voltage),
                read_delay_ms=float(inter_pulse_delay_s * 1000.0),
                icc=float(icc),
                psu=psu,
                optical=optical,
                led=led,
                power=float(power),
                sequence=sequence_list,
                should_stop=should_stop,
                on_point=on_point,
                validate_timing=validate_timing,
            )
        else:
            raise RuntimeError(
                "keithley object does not support unified API (do_pulse_measurement). "
                "Expected IVControllerManager instance."
            )

    def run_pulse_measurement_debug(
        self,
        *,
        keithley,
        pulse_voltage: float,
        pulse_width_ms: float,
        read_voltage: float = 0.2,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        validate_timing: bool = True,
    ) -> dict:
        """Fire one pulse; capture V/I near pulse end and at read voltage (debug info)."""
        # Timing guard
        if validate_timing:
            limits = self.smu_limits.get_limits(smu_type)
            min_pulse_width = limits.get("min_pulse_width_ms", 1.0)
            if float(pulse_width_ms) < float(min_pulse_width):
                raise ValueError(
                    f"Pulse width {pulse_width_ms} ms is below minimum for {smu_type} ({min_pulse_width} ms)"
                )

        def _mv():
            try:
                v = keithley.measure_voltage()
                if isinstance(v, (list, tuple)):
                    return float(v[-1] if len(v) > 0 else float("nan"))
                return float(v)
            except Exception:
                return float("nan")

        def _mi():
            try:
                it = keithley.measure_current()
                return float(it[1]) if isinstance(it, (list, tuple)) and len(it) > 1 else float(it)
            except Exception:
                return float("nan")

        out = {
            "pulse_v_cmd": float(pulse_voltage),
            "pulse_v_meas": float("nan"),
            "pulse_i_meas": float("nan"),
            "read_v_meas": float("nan"),
            "read_i_meas": float("nan"),
            "pulse_width_ms": float(pulse_width_ms),
        }

        # Arm at 0 V to avoid spikes
        try:
            keithley.enable_output(True)
            keithley.set_voltage(0.0, icc)
        except Exception:
            pass

        # Pulse
        try:
            keithley.set_voltage(float(pulse_voltage), float(icc))
        except Exception:
            pass
        t0 = time.perf_counter()
        # Hold for requested width
        while (time.perf_counter() - t0) < (float(pulse_width_ms) / 1000.0):
            time.sleep(0.0005)
        # Sample V/I near end of pulse
        out["pulse_v_meas"] = _mv()
        out["pulse_i_meas"] = _mi()

        # Return to read voltage and sample
        try:
            keithley.set_voltage(float(read_voltage), float(icc))
        except Exception:
            pass
        time.sleep(0.002)
        out["read_v_meas"] = _mv()
        out["read_i_meas"] = _mi()

        # Do not force output off here; caller manages lifecycle
        return out

    def run_single_pulse_measurement(
        self,
        *,
        keithley,
        pulse_voltage: float,
        pulse_time_s: float,
        read_voltage: float = 0.1,
        icc: float = 1e-3,
        smu_type: str = "Keithley 2450",
    ) -> Tuple[float, float, float]:
        """
        Send a single pulse and return current measurements.

        Measures current both during the pulse and at read voltage.
        """

        def _mv():
            try:
                v = keithley.measure_voltage()
                if isinstance(v, (list, tuple)):
                    return float(v[-1] if len(v) > 0 else float("nan"))
                return float(v)
            except Exception:
                return float("nan")

        def _mi():
            try:
                it = keithley.measure_current()
                return float(it[1]) if isinstance(it, (list, tuple)) and len(it) > 1 else float(it)
            except Exception:
                return float("nan")

        # Start at 0V
        try:
            keithley.enable_output(True)
            keithley.set_voltage(0.0, icc)
            time.sleep(0.01)
        except Exception:
            pass

        # Apply pulse voltage
        try:
            keithley.set_voltage(float(pulse_voltage), float(icc))
        except Exception:
            pass

        # Hold for pulse duration and measure during pulse
        t0 = time.perf_counter()
        while (time.perf_counter() - t0) < float(pulse_time_s):
            time.sleep(0.0005)

        voltage_during = _mv()
        current_during = _mi()

        # Return to read voltage and measure
        try:
            keithley.set_voltage(float(read_voltage), float(icc))
        except Exception:
            pass
        time.sleep(0.002)
        current_at_read = _mi()

        return (voltage_during, current_during, current_at_read)

    def run_forming_measurement(
        self,
        *,
        keithley,
        start_voltage: float,
        start_time_s: float,
        pulses_per_step: int,
        time_increment_s: float,
        max_time_s: float,
        max_voltage: float,
        current_limit: float,
        target_current: float,
        read_voltage: float = 0.1,
        icc: float = 1e-3,
        smu_type: str = "Keithley 2450",
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float], dict]:
        """
        Run adaptive forming algorithm for memristors.
        """
        voltages: List[float] = []
        currents: List[float] = []
        timestamps: List[float] = []

        current_voltage = float(start_voltage)
        current_time = float(start_time_s)
        total_pulses = 0
        forming_successful = False
        voltage_increment = 0.5  # Default voltage increment (V)

        # Initialize at 0V
        try:
            keithley.enable_output(True)
            keithley.set_voltage(0.0, icc)
            time.sleep(0.01)
        except Exception:
            pass

        start_timestamp = time.perf_counter()

        while True:
            # Check stop condition
            if should_stop and should_stop():
                break

            # Check voltage limit
            if current_voltage > max_voltage:
                break

            # Send pulses_per_step pulses at current settings
            max_current_this_step = 0.0
            for pulse_idx in range(pulses_per_step):
                if should_stop and should_stop():
                    break

                # Apply pulse voltage
                try:
                    keithley.set_voltage(current_voltage, icc)
                except Exception:
                    pass

                # Hold for pulse duration
                t0 = time.perf_counter()
                while (time.perf_counter() - t0) < current_time:
                    time.sleep(0.0005)

                # Measure during pulse
                try:
                    v_pulse = keithley.measure_voltage()
                    i_pulse = keithley.measure_current()
                    if isinstance(v_pulse, (list, tuple)):
                        v_pulse = v_pulse[-1] if len(v_pulse) > 0 else current_voltage
                    if isinstance(i_pulse, (list, tuple)):
                        i_pulse = i_pulse[1] if len(i_pulse) > 1 else i_pulse[0]
                    v_pulse = float(v_pulse)
                    i_pulse = float(i_pulse)
                except Exception:
                    v_pulse = current_voltage
                    i_pulse = 0.0

                timestamp = time.perf_counter() - start_timestamp
                voltages.append(v_pulse)
                currents.append(i_pulse)
                timestamps.append(timestamp)

                if on_point:
                    try:
                        on_point(v_pulse, i_pulse, timestamp)
                    except Exception:
                        pass

                # Check current limit
                if abs(i_pulse) > current_limit:
                    metadata = {
                        "forming_successful": False,
                        "final_voltage": current_voltage,
                        "final_time": current_time,
                        "total_pulses": total_pulses + pulse_idx + 1,
                        "reason": "current_limit_exceeded",
                        "max_current": max(abs(i_pulse), max_current_this_step),
                    }
                    return (voltages, currents, timestamps, metadata)

                max_current_this_step = max(max_current_this_step, abs(i_pulse))

                # Return to read voltage and measure
                try:
                    keithley.set_voltage(read_voltage, icc)
                except Exception:
                    pass
                time.sleep(0.002)

                try:
                    i_read = keithley.measure_current()
                    if isinstance(i_read, (list, tuple)):
                        i_read = i_read[1] if len(i_read) > 1 else i_read[0]
                    i_read = float(i_read)
                except Exception:
                    i_read = 0.0

                timestamp_read = time.perf_counter() - start_timestamp
                voltages.append(read_voltage)
                currents.append(i_read)
                timestamps.append(timestamp_read)

                if on_point:
                    try:
                        on_point(read_voltage, i_read, timestamp_read)
                    except Exception:
                        pass

                max_current = max(abs(i_pulse), abs(i_read))
                if max_current >= target_current:
                    forming_successful = True
                    metadata = {
                        "forming_successful": True,
                        "final_voltage": current_voltage,
                        "final_time": current_time,
                        "total_pulses": total_pulses + pulse_idx + 1,
                        "reason": "target_current_reached",
                        "final_current": max_current,
                    }
                    return (voltages, currents, timestamps, metadata)

                max_current_this_step = max(max_current_this_step, abs(i_read))

            total_pulses += pulses_per_step

            # If not formed, increase time
            current_time += time_increment_s

            # If time exceeds max, reset time and increase voltage
            if current_time > max_time_s:
                current_time = float(start_time_s)
                current_voltage += voltage_increment

                if current_voltage > max_voltage:
                    metadata = {
                        "forming_successful": False,
                        "final_voltage": current_voltage - voltage_increment,
                        "final_time": max_time_s,
                        "total_pulses": total_pulses,
                        "reason": "max_voltage_reached",
                        "max_current": max_current_this_step,
                    }
                    return (voltages, currents, timestamps, metadata)

        metadata = {
            "forming_successful": forming_successful,
            "final_voltage": current_voltage,
            "final_time": current_time,
            "total_pulses": total_pulses,
            "reason": "max_limits_reached",
            "max_current": max_current_this_step if "max_current_this_step" in locals() else 0.0,
        }
        return (voltages, currents, timestamps, metadata)

    def run_pulsed_iv_sweep(
        self,
        *,
        keithley,
        start_v: float,
        stop_v: float,
        step_v: Optional[float] = None,
        num_steps: Optional[int] = None,
        pulse_width_ms: Optional[float] = None,
        vbase: float = 0.2,
        inter_step_delay_s: float = 0.0,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        validate_timing: bool = True,
        sweep_type: str = "FS",
        neg_stop_v: Optional[float] = None,
        reset_should_stop: Optional[Callable[[], None]] = None,
        manage_session: bool = True,
        collect_debug: bool = False,
    ) -> Tuple[List[float], List[float], List[float], Optional[List[dict]]]:
        """
        Run pulsed IV sweep. Always returns (v, i, t, dbg) with dbg=None when
        collect_debug=False. When collect_debug=True, dbg contains per-point
        debug records for saving to JSON.
        """
        if collect_debug:
            v_out, i_out, t_out, dbg = self._run_pulsed_iv_sweep_with_debug(
                keithley=keithley,
                start_v=start_v,
                stop_v=stop_v,
                step_v=step_v,
                num_steps=num_steps,
                pulse_width_ms=pulse_width_ms,
                vbase=vbase,
                inter_step_delay_s=inter_step_delay_s,
                icc=icc,
                smu_type=smu_type,
                should_stop=should_stop,
                on_point=on_point,
                validate_timing=validate_timing,
                sweep_type=sweep_type,
                neg_stop_v=neg_stop_v,
            )
            return v_out, i_out, t_out, dbg

        # Default pulse width if not provided
        if pulse_width_ms is None:
            try:
                pulse_width_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
            except Exception:
                pulse_width_ms = 1.0

        # Build voltage range for sweep
        if step_v is None and num_steps is None:
            step_v = 0.1  # Default step

        voltage_range = self.compute_voltage_range(
            float(start_v),
            float(stop_v),
            float(step_v) if step_v else 0.0,
            sweep_type,
            VoltageRangeMode.FIXED_STEP,
            neg_stop_v=neg_stop_v,
            num_steps=num_steps,
        )

        # Create SweepConfig
        config = SweepConfig(
            start_v=float(start_v),
            stop_v=float(stop_v),
            step_v=float(step_v) if step_v else 0.1,
            neg_stop_v=float(neg_stop_v) if neg_stop_v is not None else None,
            step_delay=float(inter_step_delay_s),
            sweep_type=sweep_type,
            sweeps=1,
            pause_s=0.0,
            icc=float(icc),
            voltage_list=list(voltage_range) if voltage_range is not None else None,
        )

        # Use unified API
        if hasattr(keithley, "do_pulsed_iv_sweep"):
            v_out, i_out, t_out = keithley.do_pulsed_iv_sweep(
                config=config,
                pulse_width_ms=float(pulse_width_ms),
                read_delay_ms=0.0,
                psu=None,
                optical=None,
                should_stop=should_stop,
                on_point=on_point,
                validate_timing=validate_timing,
            )
            return v_out, i_out, t_out, None

        v_out: List[float] = []
        i_out: List[float] = []
        t_out: List[float] = []
        t0 = time.perf_counter()

        for amp in voltage_range:
            if should_stop and should_stop():
                break
            _v, _i, _t = self.run_pulse_measurement(
                keithley=keithley,
                pulse_voltage=float(amp),
                pulse_width_ms=float(pulse_width_ms),
                num_pulses=1,
                read_voltage=float(vbase),
                inter_pulse_delay_s=0.0,
                icc=float(icc),
                smu_type=smu_type,
                should_stop=should_stop,
                validate_timing=validate_timing,
            )
            try:
                i_val = float(_i[-1]) if _i else float("nan")
            except Exception:
                i_val = float("nan")
            v_out.append(float(amp))
            i_out.append(i_val)
            t_out.append(time.time() - t0)
            if on_point:
                try:
                    on_point(float(amp), i_val, t_out[-1])
                except Exception:
                    pass
            if inter_step_delay_s and inter_step_delay_s > 0:
                time.sleep(max(0.0, float(inter_step_delay_s)))

        return v_out, i_out, t_out, None

    def _run_pulsed_iv_sweep_with_debug(
        self,
        *,
        keithley,
        start_v: float,
        stop_v: float,
        step_v: Optional[float] = None,
        num_steps: Optional[int] = None,
        pulse_width_ms: Optional[float] = None,
        vbase: float = 0.2,
        inter_step_delay_s: float = 0.0,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        validate_timing: bool = True,
        sweep_type: str = "FS",
        neg_stop_v: Optional[float] = None,
    ) -> Tuple[List[float], List[float], List[float], List[dict]]:
        """Internal: pulsed IV sweep with per-point debug records for saving to JSON."""

        def _linrange(v0: float, v1: float, step_opt: Optional[float], nsteps_opt: Optional[int]) -> List[float]:
            out: List[float] = []
            if step_opt is not None and float(step_opt) != 0.0:
                s = float(step_opt) if v1 >= v0 else -abs(float(step_opt))
                v = v0
                if s > 0:
                    while v <= v1 + 1e-12:
                        out.append(round(v, 6))
                        v += s
                else:
                    while v >= v1 - 1e-12:
                        out.append(round(v, 6))
                        v += s
            elif nsteps_opt is not None and int(nsteps_opt) > 1:
                n = int(nsteps_opt)
                step = (v1 - v0) / float(n - 1)
                out = [round(v0 + i * step, 6) for i in range(n)]
            else:
                out = [round(v0, 6)] if abs(v1 - v0) < 1e-15 else [round(v0, 6), round(v1, 6)]
            return out

        sv = float(start_v)
        ev = float(stop_v)
        if sweep_type == "PS":
            amps = _linrange(sv, ev, step_v, num_steps) + _linrange(ev, sv, step_v, num_steps)
        elif sweep_type == "NS":
            nv = -abs(neg_stop_v if neg_stop_v is not None else ev)
            amps = _linrange(sv, nv, step_v, num_steps) + _linrange(nv, sv, step_v, num_steps)
        elif sweep_type == "HS":
            midpoint = (sv + ev) / 2.0
            amps = _linrange(sv, midpoint, step_v, num_steps)
        else:
            nv = -abs(neg_stop_v if neg_stop_v is not None else ev)
            amps = (
                _linrange(sv, ev, step_v, num_steps)
                + _linrange(ev, nv, step_v, num_steps)
                + _linrange(nv, sv, step_v, num_steps)
            )

        if pulse_width_ms is None:
            try:
                pulse_width_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
            except Exception:
                pulse_width_ms = 1.0

        v_out: List[float] = []
        i_out: List[float] = []
        t_out: List[float] = []
        dbg: List[dict] = []
        t0 = time.perf_counter()

        try:
            keithley.enable_output(True)
            keithley.set_voltage(float(vbase), float(icc))
        except Exception:
            pass

        for amp in amps:
            if should_stop and should_stop():
                break
            rec = self.run_pulse_measurement_debug(
                keithley=keithley,
                pulse_voltage=float(amp),
                pulse_width_ms=float(pulse_width_ms),
                read_voltage=float(vbase),
                icc=float(icc),
                smu_type=smu_type,
                validate_timing=validate_timing,
            )
            dbg.append(rec)
            try:
                i_val = float(rec.get("read_i_meas", float("nan")))
            except Exception:
                i_val = float("nan")
            v_out.append(float(amp))
            i_out.append(i_val)
            t_out.append(time.time() - t0)
            if on_point:
                try:
                    on_point(float(amp), i_val, t_out[-1])
                except Exception:
                    pass
            if inter_step_delay_s and inter_step_delay_s > 0:
                time.sleep(max(0.0, float(inter_step_delay_s)))

        try:
            keithley.set_voltage(0.0, float(icc))
        except Exception:
            pass
        try:
            keithley.enable_output(False)
        except Exception:
            pass

        return v_out, i_out, t_out, dbg


__all__ = ["PulseSessionMixin", "PulseMeasurementMixin"]
