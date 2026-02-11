"""
Optical test runner – laser + SMU, simplified flow.

Flow (4200A):
  1. Send Keithley command to start measurement (bias + timed read).
  2. Wait MEASUREMENT_INIT_TIME_S for GPIB/Keithley to initialise → this is t0.
  3. Wait laser_fire_delay_s (0 = fire at t0, 1 = fire at 1 s after t0), then fire laser per pattern (on/off times).
  4. Collect data (measurement runs in background; timestamps start at 0 = first sample).

Timeline: Data timestamps from Keithley are 0, dt, 2*dt, ... (t=0 = first measurement).
          t0 in wall clock = MEASUREMENT_INIT_TIME_S after we sent start. Laser intervals
          are stored in the same timeline (add MEASUREMENT_INIT_TIME_S to schedule times).
"""

import logging
import threading
import time
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger(__name__)


OPTICAL_TEST_FUNCTIONS = ('optical_read_pulsed_light', 'optical_pulse_train_read', 'optical_pulse_train_pattern_read')

# Time (s) we wait after sending "start measurement" before we consider measurement started (t0).
# Allows GPIB commands to send and Keithley to initialise; then we wait laser_fire_delay_s and fire.
MEASUREMENT_INIT_TIME_S = 1.0


def _optical_on_to_seconds(val: float) -> float:
    """Convert optical on/off param to seconds. Values in (0, 2] treated as seconds (e.g. 0.5, 1.0), else as ms."""
    if 0 < val <= 2:
        return val
    return val / 1000.0


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
    # Laser power: use test param optical_laser_power_mw if set, else GUI "Set (mW)" value
    power_mw = None
    try:
        p = params.get('optical_laser_power_mw')
        if p is not None:
            power_mw = float(p)
    except (TypeError, ValueError):
        pass
    if power_mw is None:
        use_software_power = getattr(gui, 'laser_power_use_software_var', None)
        if use_software_power is not None and use_software_power.get():
            try:
                pvar = getattr(gui, 'laser_power_var', None)
                power_mw = float(pvar.get().strip()) if pvar is not None else 1.0
            except (ValueError, AttributeError):
                power_mw = 1.0
    if power_mw is not None:
        try:
            laser.set_to_digital_power_control(power_mw)
        except Exception:
            pass
        # Store calibrated true power in params for save file / metadata
        try:
            from Equipment.Laser_Power_Meter.laser_power_calibration import load_calibration, get_actual_mw
            cal = load_calibration()
            params["optical_laser_power_true_mw"] = get_actual_mw(cal, power_mw)
        except (FileNotFoundError, Exception):
            params["optical_laser_power_true_mw"] = None

    if not getattr(gui, 'system_wrapper', None) or not gui.system_wrapper.is_connected():
        return (None, RuntimeError("SMU not connected. Connect the instrument in the Connection tab first."))

    system = getattr(gui.system_wrapper, 'current_system', None)
    if system is None:
        return (None, RuntimeError("No measurement system. Connect the instrument in the Connection tab first."))

    system_name = getattr(system, 'get_system_name', lambda: getattr(gui.system_wrapper, 'system_name', 'unknown'))()
    logger.info(f"Optical test: system_name = '{system_name}'")
    
    if system_name == 'keithley4200a':
        if not hasattr(system, 'run_bias_timed_read'):
            return (None, RuntimeError("4200A optical path requires run_bias_timed_read."))
        try:
            logger.info(f"Calling _run_optical_4200() for {func_name}")
            return (_run_optical_4200(system, laser, func_name, params), None)
        except Exception as e:
            logger.error(f"_run_optical_4200() failed: {type(e).__name__}: {e}")
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


def _run_laser_schedule(
    laser, func_name: str, params: dict, t0: float, duration_s: float
) -> List[Tuple[float, float]]:
    """Execute laser firing: wait laser_fire_delay_s from t0, then fire per pattern. Returns intervals relative to t0."""
    # Seconds after t0 when first pulse fires (0 = at t0, 1 = 1 s after t0)
    laser_delay_s = float(params.get('laser_delay_s') or params.get('laser_start_delay_s', 0.0))
    laser_fire_delay_s = laser_delay_s
    logger.info(f"Laser fire delay (s): {laser_fire_delay_s}")

    laser_on_intervals: List[Tuple[float, float]] = []

    if func_name == 'optical_read_pulsed_light':
        optical_pulse_duration_s = float(params.get('optical_pulse_duration_s', 0.2))
        optical_pulse_period_s = float(params.get('optical_pulse_period_s', 1.0))
        next_pulse_t = laser_fire_delay_s
        logger.info(f"Optical pulse duration (s): {optical_pulse_duration_s} -> {optical_pulse_duration_s*1000:.1f}ms")
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
        optical_on_ms = float(params.get('optical_on_ms', 500.0))
        optical_off_ms = float(params.get('optical_off_ms', 500.0))
        on_seconds = _optical_on_to_seconds(optical_on_ms)
        off_seconds = _optical_on_to_seconds(optical_off_ms)
        logger.info(f"Optical on: {optical_on_ms} -> {on_seconds*1000:.1f}ms, off: {optical_off_ms} -> {off_seconds*1000:.1f}ms")
        if laser_fire_delay_s > 0:
            time.sleep(laser_fire_delay_s)
        if func_name == 'optical_pulse_train_pattern_read':
            pattern_raw = str(params.get('laser_pattern', '1011')).strip()
            pattern = ''.join(c for c in pattern_raw if c in '01')
            if not pattern:
                raise ValueError("Laser pattern is empty. Use 1s and 0s (e.g., 1011)")
            pattern_repeats = max(1, int(params.get('pattern_repeats', 1)))
            time_between_patterns_s = float(params.get('time_between_patterns_s', 0.0))
            # One pattern = fire at slot indices where pattern has '1'. Repeat pattern N times with optional delay between repeats.
            pulse_schedule_single = [i for i, c in enumerate(pattern) if c == '1']
            pulse_period_s = on_seconds + off_seconds
            pattern_duration_s = len(pattern) * pulse_period_s
            # If time_between_patterns_s is 0, use one period as default; otherwise use specified time
            wait_between_repeats_s = time_between_patterns_s if time_between_patterns_s > 0 else pulse_period_s
            # Build full schedule: for each repeat, fire at repeat_start + slot * period
            t_laser_start = time.perf_counter()
            for repeat in range(pattern_repeats):
                repeat_start = repeat * (pattern_duration_s + wait_between_repeats_s)
                for slot_idx in pulse_schedule_single:
                    target_time = repeat_start + slot_idx * pulse_period_s
                    current_elapsed = time.perf_counter() - t_laser_start
                    if target_time > current_elapsed:
                        time.sleep(target_time - current_elapsed)
                    if (time.perf_counter() - t0) >= duration_s:
                        break
                    t_start = time.perf_counter()
                    laser.emission_on()
                    time.sleep(on_seconds)
                    laser.emission_off()
                    t_end = time.perf_counter()
                    laser_on_intervals.append((t_start - t0, t_end - t0))
                if (time.perf_counter() - t0) >= duration_s:
                    break
        else:
            n_optical_pulses = int(params.get('n_optical_pulses', 5))
            pulse_schedule = list(range(n_optical_pulses))
            pulse_period_s = on_seconds + off_seconds
            t_laser_start = time.perf_counter()
            for slot_idx in pulse_schedule:
                target_time = slot_idx * pulse_period_s
                current_elapsed = time.perf_counter() - t_laser_start
                if target_time > current_elapsed:
                    time.sleep(target_time - current_elapsed)
                if (time.perf_counter() - t0) >= duration_s:
                    break
                t_start = time.perf_counter()
                laser.emission_on()
                time.sleep(on_seconds)
                laser.emission_off()
                t_end = time.perf_counter()
                laser_on_intervals.append((t_start - t0, t_end - t0))

    logger.info(f"_run_laser_schedule() completed: fired {len(laser_on_intervals)} pulses")
    return laser_on_intervals


def suggest_laser_sync_offset_s(
    timestamps: List[float],
    resistances: List[float],
    desired_first_pulse_s: float,
    baseline_fraction: float = 0.1,
    min_samples_baseline: int = 10,
) -> Optional[float]:
    """Suggest laser_sync_offset_s so the first pulse appears at desired_first_pulse_s on the plot.

    Uses the first significant resistance drop (e.g. photodiode response) to estimate
    when the laser actually fired; suggests offset = desired_first_pulse_s - observed_time.
    Run one optical test with laser_delay_s=0 and sync_offset_s=0, then call this with
    the result timestamps and resistances and desired time (e.g. 1.0). Set the suggested
    value as "Laser sync offset (s)" for the next run.

    Args:
        timestamps: Measurement timestamps (s).
        resistances: Resistance values (Ohms); drop indicates laser on.
        desired_first_pulse_s: Desired time (s) for first pulse on the plot.
        baseline_fraction: Fraction of baseline to detect drop (default 0.1 = 10%).
        min_samples_baseline: Number of initial samples for baseline (default 10).

    Returns:
        Suggested sync offset (s) to add, or None if no drop detected.
    """
    if not timestamps or not resistances or len(timestamps) != len(resistances):
        return None
    if len(resistances) < min_samples_baseline:
        return None

    valid_baseline = [r for r in resistances[:min_samples_baseline] if r and abs(r) < 1e15]
    if not valid_baseline:
        return None

    baseline = sorted(valid_baseline)[len(valid_baseline) // 2]
    threshold = baseline * baseline_fraction

    for t, r in zip(timestamps, resistances):
        if not r or abs(r) >= 1e15:
            continue
        if abs(r - baseline) > threshold:
            observed_first_pulse_s = t
            suggested = desired_first_pulse_s - observed_first_pulse_s
            logger.info(
                f"Calibration: first pulse observed at {observed_first_pulse_s:.3f}s, "
                f"desired {desired_first_pulse_s:.3f}s -> suggest laser_sync_offset_s = {suggested:.3f}s"
            )
            return suggested

    return None


def _validate_timing_alignment(
    laser_on_intervals: List[Tuple[float, float]],
    timestamps: List[float],
    resistances: List[float],
    sample_interval_s: float
) -> None:
    """Validate timing alignment between laser firing and photodiode response.
    
    Compares recorded laser pulse times with resistance changes in measurements.
    Logs warnings if timing error exceeds acceptable thresholds.
    
    Args:
        laser_on_intervals: List of (start, end) times for laser pulses
        timestamps: Measurement timestamps
        resistances: Resistance measurements
        sample_interval_s: Sample interval for measurements
    """
    if not laser_on_intervals or len(resistances) < 10:
        return
    
    try:
        # Calculate baseline resistance (median of first 10 samples)
        baseline_samples = resistances[:min(10, len(resistances))]
        # Filter out NaN and inf values
        valid_baseline = [r for r in baseline_samples if r and abs(r) < 1e15]
        if not valid_baseline:
            return
        
        baseline = sorted(valid_baseline)[len(valid_baseline) // 2]  # median
        threshold = baseline * 0.1  # 10% change threshold
        
        # Check alignment for each laser pulse
        for pulse_idx, (pulse_start, pulse_end) in enumerate(laser_on_intervals):
            # Find when resistance changes near this pulse time
            pulse_detected = False
            for i, (t, r) in enumerate(zip(timestamps, resistances)):
                if not r or abs(r) >= 1e15:
                    continue
                    
                # Look for resistance change within window around pulse
                time_diff = abs(t - pulse_start)
                if time_diff < (pulse_end - pulse_start + sample_interval_s * 3):
                    if abs(r - baseline) > threshold:
                        # Found resistance change near expected pulse time
                        timing_error = t - pulse_start
                        if abs(timing_error) > sample_interval_s * 2:
                            logger.warning(
                                f"Pulse {pulse_idx}: timing error {timing_error*1000:.1f}ms "
                                f"(pulse at {pulse_start:.3f}s, detected at {t:.3f}s)"
                            )
                        else:
                            logger.debug(
                                f"Pulse {pulse_idx}: good alignment, error {timing_error*1000:.1f}ms"
                            )
                        pulse_detected = True
                        break
            
            if not pulse_detected:
                logger.warning(f"Pulse {pulse_idx} at {pulse_start:.3f}s: no photodiode response detected")
                
    except Exception as e:
        logger.debug(f"Timing validation error: {e}")


def _run_optical_4200_fallback(
    system, laser, func_name: str, params: dict
) -> Dict[str, Any]:
    """
    Simplified 4200A flow:
      1. Start measurement (thread sends EX to Keithley; data timestamps 0, dt, 2*dt, ... from then).
      2. Wait MEASUREMENT_INIT_TIME_S → that moment is t0.
      3. Run laser schedule (waits laser_fire_delay_s from t0, then fires per pattern).
      4. Join thread; return data. Laser intervals are converted to data timeline (add init time).
    """
    logger.info(f"_run_optical_4200_fallback() for {func_name}")
    read_voltage = float(params.get('read_voltage', 0.5))
    sample_interval_s = float(params.get('sample_interval_s', 0.02))
    clim = float(params.get('clim', 1e-3))
    if func_name == 'optical_read_pulsed_light':
        duration_s = float(params.get('total_time_s', 10.0))
    else:
        duration_s = float(params.get('duration_s', 5.0))
    num_points = max(1, int(duration_s / sample_interval_s))
    result_holder: List[Optional[Dict[str, Any]]] = [None]
    exc_holder: List[Optional[Exception]] = [None]

    current_range_a = float(params.get('current_range_a', 0.0))
    def run_measurement() -> None:
        try:
            result_holder[0] = system.run_bias_timed_read(
                vforce=read_voltage,
                duration_s=duration_s,
                sample_interval_s=sample_interval_s,
                ilimit=clim,
                num_points=num_points,
                current_range_a=current_range_a,
            )
        except Exception as e:
            exc_holder[0] = e

    init_time_s = float(params.get('measurement_init_time_s', MEASUREMENT_INIT_TIME_S))
    init_time_s = max(0.0, min(5.0, init_time_s))
    # 1. Start measurement (data t=0 is first sample from Keithley, which happens ~init_time_s after thread starts)
    thread = threading.Thread(target=run_measurement, daemon=False)
    thread.start()
    # 2. Wait for GPIB/Keithley to initialise → t0 (accounts for ~1s delay before measurement actually starts)
    time.sleep(init_time_s)
    t0 = time.perf_counter()
    # 3. Run laser: wait laser_fire_delay_s from t0, then fire per pattern
    #    Laser intervals are returned relative to t0
    laser_on_intervals = _run_laser_schedule(laser, func_name, params, t0, duration_s)
    thread.join()
    if exc_holder[0] is not None:
        raise exc_holder[0]
    result = result_holder[0]
    if result is None:
        raise RuntimeError("4200A bias timed read returned no data.")
    
    # 4. Align laser intervals with measurement timestamps
    #    Measurement timestamps start at t=0 (when C code actually started measuring, ~init_time_s after thread start)
    #    t0 is set after init_time_s delay to account for Keithley initialization
    #    Laser intervals are relative to t0, which corresponds to t≈0 in the data timeline
    #    So we should store laser intervals directly (they're already aligned with data timeline)
    #    We do NOT add init_time_s because measurement timestamps already account for when measurement started
    result['laser_on_intervals'] = laser_on_intervals
    logger.info(f"Optical 4200: timestamps start at 0; {len(laser_on_intervals)} laser intervals stored directly (relative to t0, which aligns with data t=0)")
    return result


def _run_optical_4200(
    system, laser, func_name: str, params: dict
) -> Dict[str, Any]:
    """4200A path: synchronized measurement using Start+Collect two-phase mode.
    
    Uses run_bias_timed_read_synced() to properly align measurement and laser timelines.
    Falls back to single-phase mode with timestamp correction if synced mode unavailable.
    """
    logger.info(f"_run_optical_4200() called for {func_name}")
    logger.info(f"System object: {type(system).__name__}")
    logger.info(f"Has run_bias_timed_read_synced: {hasattr(system, 'run_bias_timed_read_synced')}")
    logger.info(f"Has run_bias_timed_read: {hasattr(system, 'run_bias_timed_read')}")
    
    read_voltage = float(params.get('read_voltage', 0.2))
    sample_interval_s = float(params.get('sample_interval_s', 0.02))
    clim = float(params.get('clim', 1e-3))

    if func_name == 'optical_read_pulsed_light':
        total_time_s = float(params.get('total_time_s', 10.0))
        duration_s = total_time_s
    else:
        duration_s = float(params.get('duration_s', 5.0))

    num_points = max(1, int(duration_s / sample_interval_s))
    
    logger.info(f"Test parameters: V={read_voltage}V, duration={duration_s}s, interval={sample_interval_s}s, points={num_points}")
    
    # TEMPORARY: Disable synced mode due to -6 errors on Collect
    # TODO: Debug why measi() fails in Collect phase
    use_synced_mode = False  # Set to False to disable
    
    # Try synced mode first for accurate timing
    if use_synced_mode and hasattr(system, 'run_bias_timed_read_synced'):
        try:
            logger.info("Using synced mode (Start+Collect) for precise timing alignment")
            
            # Create sync event for coordination
            sync_ready_event = threading.Event()
            
            # Start measurement thread (returns tuple: thread, result_holder, exc_holder)
            thread, result_holder, exc_holder = system.run_bias_timed_read_synced(
                vforce=read_voltage,
                duration_s=duration_s,
                sample_interval_s=sample_interval_s,
                ilimit=clim,
                sync_ready_event=sync_ready_event,
                num_points=num_points,
            )
            
            # Wait for 4200A to apply bias and signal ready
            if not sync_ready_event.wait(timeout=5.0):
                raise RuntimeError("4200A did not signal ready within 5s")
            
            # NOW set t0 - measurement hasn't started sampling yet
            # This is the key fix: both measurement and laser use the same t0 reference
            t0 = time.perf_counter()
            collect_start_time = t0  # Record when Collect phase should begin
            
            logger.debug(f"Sync ready event received, t0 set, starting laser schedule")
            
            # Run laser schedule (synchronized with measurement timeline)
            laser_on_intervals = _run_laser_schedule(laser, func_name, params, t0, duration_s)
            
            # Wait for measurement to complete
            thread.join()
            
            if exc_holder[0] is not None:
                raise exc_holder[0]
            result = result_holder[0]
            if result is None:
                raise RuntimeError("4200A bias timed read (synced) returned no data.")
            
            logger.info(f"Synced: Received result with keys: {list(result.keys())}")
            logger.info(f"Synced: Data points - timestamps: {len(result.get('timestamps', []))}, currents: {len(result.get('currents', []))}")
            
            # Measurement timestamps are already aligned with t0 (Collect started after sync event)
            result['laser_on_intervals'] = laser_on_intervals
            
            logger.info(f"Synced mode: Added {len(laser_on_intervals)} laser intervals to result")
            
            # Timing validation diagnostics
            if laser_on_intervals and 'resistances' in result and 'timestamps' in result:
                _validate_timing_alignment(
                    laser_on_intervals, 
                    result['timestamps'], 
                    result['resistances'], 
                    sample_interval_s
                )
            
            logger.info("Synced mode completed successfully")
            return result
            
        except (RuntimeError, AttributeError, Exception) as e:
            # Synced mode failed - log and fall back
            logger.warning(f"Synced mode failed ({type(e).__name__}: {e}), falling back to single-phase with correction")
    else:
        if not use_synced_mode:
            logger.info("Synced mode disabled, using fallback with timestamp correction")
        else:
            logger.info("Synced mode not available (run_bias_timed_read_synced not found), using fallback")
    
    # Fallback: single-phase mode with timestamp correction
    return _run_optical_4200_fallback(system, laser, func_name, params)


def _run_optical_read_pulsed_light(system, laser, params: dict) -> Dict[str, Any]:
    """Read at V for total_time_s; optical pulse duration_s every period_s, starting after laser_delay_s."""
    read_voltage = float(params.get('read_voltage', 0.2))
    total_time_s = float(params.get('total_time_s', 10.0))
    optical_pulse_duration_s = float(params.get('optical_pulse_duration_s', 0.2))
    optical_pulse_period_s = float(params.get('optical_pulse_period_s', 1.0))
    sample_interval_s = float(params.get('sample_interval_s', 0.02))
    clim = float(params.get('clim', 1e-3))
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
    optical_off_ms = float(params.get('optical_off_ms', 100.0))
    on_seconds = _optical_on_to_seconds(optical_on_ms)
    off_seconds = _optical_on_to_seconds(optical_off_ms)
    n_optical_pulses = int(params.get('n_optical_pulses', 5))
    duration_s = float(params.get('duration_s', 5.0))
    sample_interval_s = float(params.get('sample_interval_s', 0.02))
    clim = float(params.get('clim', 1e-3))
    laser_delay_s = float(params.get('laser_delay_s', 0.0))

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
            time.sleep(on_seconds)
            laser.emission_off()
            t_end = time.perf_counter()
            laser_on_intervals.append((t_start - t0, t_end - t0))
            next_read_t = max(next_read_t, t_end - t0)
            time.sleep(off_seconds)

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
    optical_off_ms = float(params.get('optical_off_ms', 100.0))
    on_seconds = _optical_on_to_seconds(optical_on_ms)
    off_seconds = _optical_on_to_seconds(optical_off_ms)
    pattern_raw = str(params.get('laser_pattern', '1011')).strip()
    duration_s = float(params.get('duration_s', 5.0))
    sample_interval_s = float(params.get('sample_interval_s', 0.02))
    clim = float(params.get('clim', 1e-3))
    laser_delay_s = float(params.get('laser_delay_s', 0.0))
    pattern_repeats = max(1, int(params.get('pattern_repeats', 1)))
    time_between_patterns_s = float(params.get('time_between_patterns_s', 0.0))

    # Build pattern and validate
    pattern = ''.join(c for c in pattern_raw if c in '01')
    if not pattern:
        raise ValueError("Laser pattern is empty. Use binary pattern with 1s and 0s (e.g., 1011 or 10101).")
    
    # Build pulse schedule: indices where pattern is '1' (per repeat)
    pulse_schedule = [i for i, c in enumerate(pattern) if c == '1']
    pulse_period_s = on_seconds + off_seconds
    pattern_duration_s = len(pattern) * pulse_period_s
    # If time_between_patterns_s is 0, use one period as default; otherwise use specified time
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
                time.sleep(on_seconds)
                laser.emission_off()
                t_end = time.perf_counter()
                laser_on_intervals.append((t_start - t0, t_end - t0))
                next_read_t = max(next_read_t, t_end - t0)
                time.sleep(off_seconds)
            if (time.perf_counter() - t0) >= duration_s:
                break

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
