"""
Optical test runner – hybrid laser + SMU tests.

Runs optical_read_pulsed_light and optical_pulse_train_read by coordinating
Oxxius laser (gui.laser) and SMU (gui.system_wrapper.system). Requires both
to be connected. Returns standard result dict for plotting/save.

4200A path: runs SMU_BiasTimedRead in a thread; main thread sleeps
optical_start_delay_s (default 1 s) then runs the laser schedule.
"""

import threading
import time
from typing import Dict, Any, Tuple, Optional, List


OPTICAL_TEST_FUNCTIONS = ('optical_read_pulsed_light', 'optical_pulse_train_read', 'optical_pulse_train_pattern_read')

# Delay (s) before starting laser after EX is sent on 4200A (measurement assumed started ~1 s later)
DEFAULT_OPTICAL_START_DELAY_S = 1.0


def run_optical_test(gui, func_name: str, params: dict) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
    """
    Run an optical+SMU test. Uses gui.laser and gui.system_wrapper.system.

    Args:
        gui: TSPTestingGUI instance (must have .laser, .system_wrapper).
        func_name: 'optical_read_pulsed_light' or 'optical_pulse_train_read'.
        params: Test parameters (read_voltage, total_time_s, etc.).

    Returns:
        (results_dict, None) on success; (None, exception) on error.
        results_dict has timestamps, currents, voltages, resistances, laser_on_intervals.
    """
    if func_name not in OPTICAL_TEST_FUNCTIONS:
        return (None, ValueError(f"Unknown optical test: {func_name}"))

    laser = getattr(gui, 'laser', None)
    if laser is None:
        return (None, RuntimeError("Laser not connected. Connect Oxxius laser in the Optical tab first."))

    if not getattr(gui, 'system_wrapper', None) or not gui.system_wrapper.is_connected():
        return (None, RuntimeError("SMU not connected. Connect the instrument in the Connection tab first."))

    system = getattr(gui.system_wrapper, 'current_system', None)
    if system is None:
        return (None, RuntimeError("No measurement system. Connect the instrument in the Connection tab first."))

    system_name = getattr(system, 'get_system_name', lambda: getattr(gui.system_wrapper, 'system_name', 'unknown'))()
    if system_name == 'keithley4200a':
        if not hasattr(system, 'run_bias_timed_read'):
            return (None, RuntimeError("4200A optical path requires run_bias_timed_read."))
        try:
            return (_run_optical_4200(system, laser, func_name, params), None)
        except Exception as e:
            return (None, e)

    if not hasattr(system, 'source_voltage_for_optical') or not hasattr(system, 'measure_current_once'):
        return (None, RuntimeError(
            f"Current system ({system_name}) does not support optical+read tests. Use Keithley 2450, 2400, or 4200A."
        ))

    try:
        if func_name == 'optical_read_pulsed_light':
            return (_run_optical_read_pulsed_light(system, laser, params), None)
        if func_name == 'optical_pulse_train_read':
            return (_run_optical_pulse_train_read(system, laser, params), None)
        if func_name == 'optical_pulse_train_pattern_read':
            return (_run_optical_pulse_train_pattern_read(system, laser, params), None)
    except Exception as e:
        return (None, e)

    return (None, ValueError(f"Unknown optical test: {func_name}"))


def _run_optical_4200(
    system, laser, func_name: str, params: dict
) -> Dict[str, Any]:
    """4200A path: run SMU_BiasTimedRead in a thread; main thread runs laser after delay."""
    read_voltage = float(params.get('read_voltage', 0.2))
    sample_interval_s = float(params.get('sample_interval_s', 0.02))
    clim = float(params.get('clim', 100e-6))
    # Use laser_delay_s from params if provided, else default to 1.0s
    optical_start_delay_s = float(params.get('laser_delay_s', DEFAULT_OPTICAL_START_DELAY_S))

    if func_name == 'optical_read_pulsed_light':
        total_time_s = float(params.get('total_time_s', 10.0))
        duration_s = total_time_s
    else:
        duration_s = float(params.get('duration_s', 5.0))

    num_points = max(1, int(duration_s / sample_interval_s))
    result_holder: List[Optional[Dict[str, Any]]] = [None]
    exc_holder: List[Optional[Exception]] = [None]

    def run_measurement() -> None:
        try:
            result_holder[0] = system.run_bias_timed_read(
                vforce=read_voltage,
                duration_s=duration_s,
                sample_interval_s=sample_interval_s,
                ilimit=clim,
                num_points=num_points,
            )
        except Exception as e:
            exc_holder[0] = e

    thread = threading.Thread(target=run_measurement, daemon=False)
    thread.start()
    time.sleep(optical_start_delay_s)

    laser_on_intervals: List[Tuple[float, float]] = []
    t0 = time.perf_counter()

    if func_name == 'optical_read_pulsed_light':
        optical_pulse_duration_s = float(params.get('optical_pulse_duration_s', 0.2))
        optical_pulse_period_s = float(params.get('optical_pulse_period_s', 1.0))
        laser_delay_s = float(params.get('laser_delay_s', 0.0))
        next_pulse_t = laser_delay_s  # Start first pulse after delay
        while (time.perf_counter() - t0) < duration_s:
            elapsed = time.perf_counter() - t0
            if next_pulse_t < duration_s and elapsed >= next_pulse_t:
                t_start = time.perf_counter()
                laser.pulse_on_ms(optical_pulse_duration_s * 1000.0)
                t_end = time.perf_counter()
                laser_on_intervals.append((t_start - t0, t_end - t0))
                next_pulse_t += optical_pulse_period_s
            time.sleep(max(0, min(0.05, optical_pulse_period_s * 0.25)))
    elif func_name in ('optical_pulse_train_read', 'optical_pulse_train_pattern_read'):
        optical_on_ms = float(params.get('optical_on_ms', 100.0))
        optical_off_ms = float(params.get('optical_off_ms', 200.0))
        laser_delay_s = float(params.get('laser_delay_s', 0.0))
        
        # Wait for laser delay before starting pulses
        if laser_delay_s > 0:
            time.sleep(laser_delay_s)
        
        # Build pulse schedule (which slots fire) from pattern if provided
        if func_name == 'optical_pulse_train_pattern_read':
            pattern_raw = str(params.get('laser_pattern', '11111')).strip()
            pattern = ''.join(c for c in pattern_raw if c in '01')
            if not pattern:
                raise ValueError("Laser pattern is empty. Use 1s and 0s (e.g., 11010)")
            num_laser_pulses = len(pattern)  # Calculate from pattern length
            pulse_schedule = [i for i, c in enumerate(pattern) if c == '1']  # Indices of pulses to fire
        else:
            n_optical_pulses = int(params.get('n_optical_pulses', 5))
            pulse_schedule = list(range(n_optical_pulses))  # All pulses fire
        
        # Fire pulses according to schedule
        pulse_period_s = (optical_on_ms + optical_off_ms) / 1000.0
        t_laser_start = time.perf_counter()
        for slot_idx in pulse_schedule:
            # Wait until this slot's time (relative to laser start)
            target_time = slot_idx * pulse_period_s
            current_elapsed = time.perf_counter() - t_laser_start
            if target_time > current_elapsed:
                time.sleep(target_time - current_elapsed)
            
            if (time.perf_counter() - t0) >= duration_s:
                break
            t_start = time.perf_counter()
            laser.emission_on()
            time.sleep(optical_on_ms / 1000.0)
            laser.emission_off()
            t_end = time.perf_counter()
            laser_on_intervals.append((t_start - t0, t_end - t0))

    thread.join()
    if exc_holder[0] is not None:
        raise exc_holder[0]
    result = result_holder[0]
    if result is None:
        raise RuntimeError("4200A bias timed read returned no data.")
    result['laser_on_intervals'] = laser_on_intervals
    return result


def _run_optical_read_pulsed_light(system, laser, params: dict) -> Dict[str, Any]:
    """Read at V for total_time_s; optical pulse duration_s every period_s, starting after laser_delay_s."""
    read_voltage = float(params.get('read_voltage', 0.2))
    total_time_s = float(params.get('total_time_s', 10.0))
    optical_pulse_duration_s = float(params.get('optical_pulse_duration_s', 0.2))
    optical_pulse_period_s = float(params.get('optical_pulse_period_s', 1.0))
    sample_interval_s = float(params.get('sample_interval_s', 0.02))
    clim = float(params.get('clim', 100e-6))
    laser_delay_s = float(params.get('laser_delay_s', 0.0))

    system.source_voltage_for_optical(read_voltage, clim)
    t0 = time.perf_counter()
    timestamps: List[float] = []
    currents: List[float] = []
    laser_on_intervals: List[Tuple[float, float]] = []
    next_pulse_t = laser_delay_s  # Start first pulse after delay
    next_read_t = 0.0

    try:
        while True:
            elapsed = time.perf_counter() - t0
            if elapsed >= total_time_s:
                break

            # Fire laser at each period (e.g. at t=delay, delay+period, delay+2*period, ... s)
            if next_pulse_t < total_time_s and elapsed >= next_pulse_t:
                t_start = time.perf_counter()
                laser.pulse_on_ms(optical_pulse_duration_s * 1000.0)
                t_end = time.perf_counter()
                laser_on_intervals.append((t_start - t0, t_end - t0))
                next_pulse_t += optical_pulse_period_s

            # Take one current reading at sample interval
            if elapsed >= next_read_t:
                t_sec, i = system.measure_current_once()
                timestamps.append(t_sec - t0)
                currents.append(i)
                next_read_t += sample_interval_s

            # Sleep until next action or end
            next_event = min(next_pulse_t, next_read_t, total_time_s)
            sleep_s = max(0, min(sample_interval_s * 0.25, next_event - (time.perf_counter() - t0)))
            if sleep_s > 0:
                time.sleep(sleep_s)
    finally:
        system.source_output_off()

    voltages = [read_voltage] * len(timestamps)
    resistances = [v / i if i and abs(i) > 1e-18 else float('nan') for v, i in zip(voltages, currents)]
    return {
        'timestamps': timestamps,
        'voltages': voltages,
        'currents': currents,
        'resistances': resistances,
        'laser_on_intervals': laser_on_intervals,
    }


def _run_optical_pulse_train_read(system, laser, params: dict) -> Dict[str, Any]:
    """Read at V for duration_s while running one optical pulse train (n pulses, on_ms, off_ms) after laser_delay_s."""
    read_voltage = float(params.get('read_voltage', 0.2))
    optical_on_ms = float(params.get('optical_on_ms', 100.0))
    optical_off_ms = float(params.get('optical_off_ms', 200.0))
    n_optical_pulses = int(params.get('n_optical_pulses', 5))
    duration_s = float(params.get('duration_s', 5.0))
    sample_interval_s = float(params.get('sample_interval_s', 0.02))
    clim = float(params.get('clim', 100e-6))
    laser_delay_s = float(params.get('laser_delay_s', 0.0))

    system.source_voltage_for_optical(read_voltage, clim)
    t0 = time.perf_counter()
    timestamps: List[float] = []
    currents: List[float] = []
    laser_on_intervals: List[Tuple[float, float]] = []
    next_read_t = 0.0
    pulse_period_s = (optical_on_ms + optical_off_ms) / 1000.0

    try:
        for pulse_idx in range(n_optical_pulses):
            pulse_start = laser_delay_s + pulse_idx * pulse_period_s
            # Take reads until just before this pulse starts
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
            # Laser on then off
            t_start = time.perf_counter()
            laser.emission_on()
            time.sleep(optical_on_ms / 1000.0)
            laser.emission_off()
            t_end = time.perf_counter()
            laser_on_intervals.append((t_start - t0, t_end - t0))
            next_read_t = max(next_read_t, t_end - t0)
            time.sleep(optical_off_ms / 1000.0)

        # Reads until duration_s
        while (time.perf_counter() - t0) < duration_s:
            elapsed = time.perf_counter() - t0
            if elapsed >= next_read_t:
                t_sec, i = system.measure_current_once()
                timestamps.append(t_sec - t0)
                currents.append(i)
                next_read_t += sample_interval_s
            time.sleep(max(0, min(sample_interval_s, t0 + duration_s - time.perf_counter())))
    finally:
        system.source_output_off()

    voltages = [read_voltage] * len(timestamps)
    resistances = [v / i if i and abs(i) > 1e-18 else float('nan') for v, i in zip(voltages, currents)]
    return {
        'timestamps': timestamps,
        'voltages': voltages,
        'currents': currents,
        'resistances': resistances,
        'laser_on_intervals': laser_on_intervals,
    }


def _run_optical_pulse_train_pattern_read(system, laser, params: dict) -> Dict[str, Any]:
    """Read at V for duration_s while firing laser pulses per binary pattern (1=on, 0=off) after laser_delay_s."""
    read_voltage = float(params.get('read_voltage', 0.2))
    optical_on_ms = float(params.get('optical_on_ms', 100.0))
    optical_off_ms = float(params.get('optical_off_ms', 200.0))
    pattern_raw = str(params.get('laser_pattern', '11111')).strip()
    duration_s = float(params.get('duration_s', 5.0))
    sample_interval_s = float(params.get('sample_interval_s', 0.02))
    clim = float(params.get('clim', 100e-6))
    laser_delay_s = float(params.get('laser_delay_s', 0.0))

    # Build pattern and validate
    pattern = ''.join(c for c in pattern_raw if c in '01')
    if not pattern:
        raise ValueError("Laser pattern is empty. Use binary pattern with 1s and 0s (e.g., 11111 or 10101).")
    
    # Number of laser pulses is determined by pattern length
    num_laser_pulses = len(pattern)
    
    # Build pulse schedule: indices where pattern is '1'
    pulse_schedule = [i for i, c in enumerate(pattern) if c == '1']

    system.source_voltage_for_optical(read_voltage, clim)
    t0 = time.perf_counter()
    timestamps: List[float] = []
    currents: List[float] = []
    laser_on_intervals: List[Tuple[float, float]] = []
    next_read_t = 0.0
    pulse_period_s = (optical_on_ms + optical_off_ms) / 1000.0

    try:
        for slot_idx in pulse_schedule:
            pulse_start = laser_delay_s + slot_idx * pulse_period_s
            # Take reads until just before this pulse starts
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
            # Laser on then off
            t_start = time.perf_counter()
            laser.emission_on()
            time.sleep(optical_on_ms / 1000.0)
            laser.emission_off()
            t_end = time.perf_counter()
            laser_on_intervals.append((t_start - t0, t_end - t0))
            next_read_t = max(next_read_t, t_end - t0)
            time.sleep(optical_off_ms / 1000.0)

        # Reads until duration_s
        while (time.perf_counter() - t0) < duration_s:
            elapsed = time.perf_counter() - t0
            if elapsed >= next_read_t:
                t_sec, i = system.measure_current_once()
                timestamps.append(t_sec - t0)
                currents.append(i)
                next_read_t += sample_interval_s
            time.sleep(max(0, min(sample_interval_s, t0 + duration_s - time.perf_counter())))
    finally:
        system.source_output_off()

    voltages = [read_voltage] * len(timestamps)
    resistances = [v / i if i and abs(i) > 1e-18 else float('nan') for v, i in zip(voltages, currents)]
    return {
        'timestamps': timestamps,
        'voltages': voltages,
        'currents': currents,
        'resistances': resistances,
        'laser_on_intervals': laser_on_intervals,
    }
