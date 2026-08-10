"""2450-only optical test runners (SMU bias + PC-timed Oxxius laser)."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

OPTICAL_TEST_FUNCTIONS = (
    "optical_read_pulsed_light",
    "optical_pulse_train_read",
    "optical_pulse_train_pattern_read",
    "optical_binary_sweep",
    "optical_pattern_repeat",
)

ProgressCb = Optional[Callable[[str], None]]


def _optical_on_to_seconds(val: float) -> float:
    if 0 < val <= 2:
        return val
    return val / 1000.0


def _apply_laser_power(laser, params: dict) -> None:
    power_mw = None
    try:
        p = params.get("optical_laser_power_mw")
        if p is not None:
            power_mw = float(p)
    except (TypeError, ValueError):
        pass
    if power_mw is None:
        return
    try:
        laser.set_to_digital_power_control(power_mw)
    except Exception:
        try:
            laser.set_power(power_mw)
        except Exception:
            pass
    try:
        from Equipment.Laser_Power_Meter.laser_power_calibration import get_actual_mw, load_calibration

        cal = load_calibration()
        params["optical_laser_power_true_mw"] = get_actual_mw(cal, power_mw)
    except Exception:
        params["optical_laser_power_true_mw"] = None


def run_optical_test(
    system,
    laser,
    func_name: str,
    params: dict,
    progress: ProgressCb = None,
    save_run_cb: Optional[Callable] = None,
    stop_flag=None,
) -> Tuple[Optional[Any], Optional[Exception]]:
    if func_name not in OPTICAL_TEST_FUNCTIONS:
        return None, ValueError(f"Unknown optical test: {func_name}")
    if laser is None:
        return None, RuntimeError("Laser not connected")
    if system is None or not system.is_connected():
        return None, RuntimeError("SMU not connected")
    if not hasattr(system, "source_voltage_for_optical") or not hasattr(system, "measure_current_once"):
        return None, RuntimeError("SMU adapter missing optical API")

    params = dict(params)
    _apply_laser_power(laser, params)

    try:
        if func_name == "optical_binary_sweep":
            return (
                run_binary_sweep(system, laser, params, progress, save_run_cb, stop_flag),
                None,
            )
        if func_name == "optical_pattern_repeat":
            return (
                run_pattern_repeat(system, laser, params, progress, save_run_cb, stop_flag),
                None,
            )
        if func_name == "optical_read_pulsed_light":
            return _run_optical_read_pulsed_light(system, laser, params), None
        if func_name == "optical_pulse_train_read":
            return _run_optical_pulse_train_read(system, laser, params), None
        if func_name == "optical_pulse_train_pattern_read":
            return _run_optical_pulse_train_pattern_read(system, laser, params), None
    except Exception as e:
        return None, e
    return None, ValueError(f"Unknown optical test: {func_name}")


def _run_optical_read_pulsed_light(system, laser, params: dict) -> Dict[str, Any]:
    read_voltage = float(params.get("read_voltage", 0.2))
    total_time_s = float(params.get("total_time_s", 10.0))
    optical_pulse_duration_s = float(params.get("optical_pulse_duration_s", 0.2))
    optical_pulse_period_s = float(params.get("optical_pulse_period_s", 1.0))
    sample_interval_s = float(params.get("sample_interval_s", 0.02))
    clim = float(params.get("clim", 1e-3))
    laser_delay_s = float(params.get("laser_delay_s", 0.0))
    current_range_a = float(params.get("current_range_a", 0.0))

    if current_range_a > 0 and hasattr(system, "tsp_controller") and system.tsp_controller:
        try:
            system.tsp_controller.set_current_measurement_range(current_range_a)
        except Exception:
            pass

    system.source_voltage_for_optical(read_voltage, clim)
    t0 = time.perf_counter()
    timestamps: List[float] = []
    currents: List[float] = []
    laser_on_intervals: List[Tuple[float, float]] = []
    next_pulse_t = laser_delay_s
    next_read_t = 0.0

    try:
        while True:
            elapsed = time.perf_counter() - t0
            if elapsed >= total_time_s:
                break
            if next_pulse_t < total_time_s and elapsed >= next_pulse_t:
                t_start = time.perf_counter()
                laser.pulse_on_ms(optical_pulse_duration_s * 1000.0)
                t_end = time.perf_counter()
                laser_on_intervals.append((t_start - t0, t_end - t0))
                next_pulse_t += optical_pulse_period_s
            if elapsed >= next_read_t:
                t_sec, i = system.measure_current_once()
                timestamps.append(t_sec - t0)
                currents.append(i)
                next_read_t += sample_interval_s
            next_event = min(next_pulse_t, next_read_t, total_time_s)
            sleep_s = max(0, min(sample_interval_s * 0.25, next_event - (time.perf_counter() - t0)))
            if sleep_s > 0:
                time.sleep(sleep_s)
    finally:
        try:
            laser.emission_off()
        except Exception:
            pass
        system.source_output_off()

    voltages = [read_voltage] * len(timestamps)
    resistances = [v / i if i and abs(i) > 1e-18 else float("nan") for v, i in zip(voltages, currents)]
    return {
        "timestamps": timestamps,
        "voltages": voltages,
        "currents": currents,
        "resistances": resistances,
        "laser_on_intervals": laser_on_intervals,
    }


def _run_optical_pulse_train_read(system, laser, params: dict) -> Dict[str, Any]:
    read_voltage = float(params.get("read_voltage", 0.2))
    optical_on_ms = float(params.get("optical_on_ms", 100.0))
    optical_off_ms = float(params.get("optical_off_ms", 100.0))
    on_seconds = _optical_on_to_seconds(optical_on_ms)
    off_seconds = _optical_on_to_seconds(optical_off_ms)
    n_optical_pulses = int(params.get("n_optical_pulses", 5))
    duration_s = float(params.get("duration_s", 5.0))
    sample_interval_s = float(params.get("sample_interval_s", 0.02))
    clim = float(params.get("clim", 1e-3))
    laser_delay_s = float(params.get("laser_delay_s", 0.0))

    system.source_voltage_for_optical(read_voltage, clim)
    t0 = time.perf_counter()
    timestamps: List[float] = []
    currents: List[float] = []
    laser_on_intervals: List[Tuple[float, float]] = []
    next_read_t = 0.0
    pulse_period_s = on_seconds + off_seconds

    try:
        for pulse_idx in range(n_optical_pulses):
            pulse_start = laser_delay_s + pulse_idx * pulse_period_s
            while True:
                elapsed = time.perf_counter() - t0
                if elapsed >= pulse_start or elapsed >= duration_s:
                    break
                if elapsed >= next_read_t:
                    t_sec, i = system.measure_current_once()
                    timestamps.append(t_sec - t0)
                    currents.append(i)
                    next_read_t += sample_interval_s
                time.sleep(max(0, min(sample_interval_s * 0.25, pulse_start - elapsed)))
            if (time.perf_counter() - t0) >= duration_s:
                break
            t_start = time.perf_counter()
            laser.emission_on()
            time.sleep(on_seconds)
            laser.emission_off()
            t_end = time.perf_counter()
            laser_on_intervals.append((t_start - t0, t_end - t0))
            next_read_t = max(next_read_t, t_end - t0)
            time.sleep(off_seconds)

        while (time.perf_counter() - t0) < duration_s:
            elapsed = time.perf_counter() - t0
            if elapsed >= next_read_t:
                t_sec, i = system.measure_current_once()
                timestamps.append(t_sec - t0)
                currents.append(i)
                next_read_t += sample_interval_s
            time.sleep(max(0, min(sample_interval_s, t0 + duration_s - time.perf_counter())))
    finally:
        try:
            laser.emission_off()
        except Exception:
            pass
        system.source_output_off()

    voltages = [read_voltage] * len(timestamps)
    resistances = [v / i if i and abs(i) > 1e-18 else float("nan") for v, i in zip(voltages, currents)]
    return {
        "timestamps": timestamps,
        "voltages": voltages,
        "currents": currents,
        "resistances": resistances,
        "laser_on_intervals": laser_on_intervals,
    }


def _run_optical_pulse_train_pattern_read(system, laser, params: dict) -> Dict[str, Any]:
    read_voltage = float(params.get("read_voltage", 0.2))
    optical_on_ms = float(params.get("optical_on_ms", 100.0))
    optical_off_ms = float(params.get("optical_off_ms", 100.0))
    on_seconds = _optical_on_to_seconds(optical_on_ms)
    off_seconds = _optical_on_to_seconds(optical_off_ms)
    pattern_raw = str(params.get("laser_pattern", "1011")).strip()
    duration_s = float(params.get("duration_s", 5.0))
    sample_interval_s = float(params.get("sample_interval_s", 0.02))
    clim = float(params.get("clim", 1e-3))
    laser_delay_s = float(params.get("laser_delay_s", 0.0))
    pattern_repeats = max(1, int(params.get("pattern_repeats", 1)))
    time_between_patterns_s = float(params.get("time_between_patterns_s", 0.0))

    pattern = "".join(c for c in pattern_raw if c in "01")
    if not pattern:
        raise ValueError("Laser pattern is empty. Use 1s and 0s (e.g. 1011).")

    pulse_schedule = [i for i, c in enumerate(pattern) if c == "1"]
    pulse_period_s = on_seconds + off_seconds
    pattern_duration_s = len(pattern) * pulse_period_s
    wait_between_repeats_s = time_between_patterns_s if time_between_patterns_s > 0 else pulse_period_s

    system.source_voltage_for_optical(read_voltage, clim)
    t0 = time.perf_counter()
    timestamps: List[float] = []
    currents: List[float] = []
    laser_on_intervals: List[Tuple[float, float]] = []
    next_read_t = 0.0

    try:
        for repeat in range(pattern_repeats):
            repeat_start = laser_delay_s + repeat * (pattern_duration_s + wait_between_repeats_s)
            for slot_idx in pulse_schedule:
                pulse_start = repeat_start + slot_idx * pulse_period_s
                while True:
                    elapsed = time.perf_counter() - t0
                    if elapsed >= pulse_start or elapsed >= duration_s:
                        break
                    if elapsed >= next_read_t:
                        t_sec, i = system.measure_current_once()
                        timestamps.append(t_sec - t0)
                        currents.append(i)
                        next_read_t += sample_interval_s
                    time.sleep(max(0, min(sample_interval_s * 0.25, pulse_start - elapsed)))
                if (time.perf_counter() - t0) >= duration_s:
                    break
                t_start = time.perf_counter()
                laser.emission_on()
                time.sleep(on_seconds)
                laser.emission_off()
                t_end = time.perf_counter()
                laser_on_intervals.append((t_start - t0, t_end - t0))
                next_read_t = max(next_read_t, t_end - t0)
                time.sleep(off_seconds)
            if (time.perf_counter() - t0) >= duration_s:
                break

        while (time.perf_counter() - t0) < duration_s:
            elapsed = time.perf_counter() - t0
            if elapsed >= next_read_t:
                t_sec, i = system.measure_current_once()
                timestamps.append(t_sec - t0)
                currents.append(i)
                next_read_t += sample_interval_s
            time.sleep(max(0, min(sample_interval_s, t0 + duration_s - time.perf_counter())))
    finally:
        try:
            laser.emission_off()
        except Exception:
            pass
        system.source_output_off()

    voltages = [read_voltage] * len(timestamps)
    resistances = [v / i if i and abs(i) > 1e-18 else float("nan") for v, i in zip(voltages, currents)]
    return {
        "timestamps": timestamps,
        "voltages": voltages,
        "currents": currents,
        "resistances": resistances,
        "laser_on_intervals": laser_on_intervals,
        "laser_pattern": pattern,
    }


def run_binary_sweep(
    system,
    laser,
    params: dict,
    progress: ProgressCb = None,
    save_run_cb: Optional[Callable] = None,
    stop_flag=None,
) -> List[Dict[str, Any]]:
    num_bits = max(1, int(params.get("num_bits", 4)))
    num_runs = 2 ** num_bits
    delay_between_runs_s = float(params.get("delay_between_runs_s", 2.0))
    all_results: List[Dict[str, Any]] = []

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    for run_idx in range(num_runs):
        if stop_flag is not None and stop_flag.is_set():
            log("Binary sweep stopped by user")
            break
        pattern = format(run_idx, f"0{num_bits}b")
        log(f"Binary sweep run {run_idx + 1}/{num_runs}: pattern {pattern}")
        run_params = dict(params)
        run_params["laser_pattern"] = pattern
        run_params["pattern_repeats"] = 1
        result = _run_optical_pulse_train_pattern_read(system, laser, run_params)
        result["laser_pattern"] = pattern
        result["run_idx"] = run_idx
        all_results.append(result)
        if save_run_cb:
            try:
                save_run_cb(run_idx, pattern, result)
            except Exception as exc:
                log(f"  WARNING: could not save run {run_idx}: {exc}")
        if run_idx < num_runs - 1 and delay_between_runs_s > 0:
            log(f"  Waiting {delay_between_runs_s:.1f}s…")
            time.sleep(delay_between_runs_s)
    log(f"Binary sweep complete: {len(all_results)} runs")
    return all_results


def run_pattern_repeat(
    system,
    laser,
    params: dict,
    progress: ProgressCb = None,
    save_run_cb: Optional[Callable] = None,
    stop_flag=None,
) -> List[Dict[str, Any]]:
    n_repeats = max(1, int(params.get("n_repeats", 5)))
    delay_between_runs_s = float(params.get("delay_between_runs_s", 2.0))
    pattern = str(params.get("laser_pattern", "0101"))
    all_results: List[Dict[str, Any]] = []

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    for run_idx in range(n_repeats):
        if stop_flag is not None and stop_flag.is_set():
            log("Pattern repeat stopped by user")
            break
        log(f"Pattern repeat {run_idx + 1}/{n_repeats}: {pattern}")
        run_params = dict(params)
        run_params["pattern_repeats"] = 1
        result = _run_optical_pulse_train_pattern_read(system, laser, run_params)
        result["laser_pattern"] = pattern
        result["run_idx"] = run_idx
        all_results.append(result)
        if save_run_cb:
            try:
                save_run_cb(run_idx, pattern, result)
            except Exception as exc:
                log(f"  WARNING: could not save run {run_idx}: {exc}")
        if run_idx < n_repeats - 1 and delay_between_runs_s > 0:
            log(f"  Waiting {delay_between_runs_s:.1f}s…")
            time.sleep(delay_between_runs_s)
    log(f"Pattern repeat complete: {len(all_results)} runs")
    return all_results
