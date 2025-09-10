import time
from typing import Callable, Iterable, List, Optional, Tuple


class VoltageRangeMode:
    FIXED_STEP = "fixed_step"          # Default: use explicit step size
    FIXED_SWEEP_RATE = "fixed_sweep_rate"  # Placeholder for future
    FIXED_VOLTAGE_TIME = "fixed_voltage_time"  # Placeholder for future


class SMULimits:
    """Configuration for different SMU types and their timing limits."""

    def __init__(self):
        self.limits = {
            "Keithley 2400": {
                "min_timing_us": 200,
                "max_update_rate": 2000,
                "rise_fall_time_us": 50,
                "min_pulse_width_ms": 1.0,
                "voltage_range_V": (-200, 200),
                "current_range_A": (-1, 1),
                "compliance_resolution": 1e-6,
                "defaults": {
                    "read_v": 0.2,
                    "vbase": 0.2,
                    "pulse_ms": 1.0,
                    "triangle": {"vmin": 0.0, "vmax": 1.0, "step": 0.05, "delay_s": 0.05}
                }
            },
            "Keithley 2401": {
                "min_timing_us": 250,
                "max_update_rate": 2000,
                "rise_fall_time_us": 30,
                "min_pulse_width_ms": 1.0,
                "voltage_range_V": (-20, 20),
                "current_range_A": (-1, 1),
                "compliance_resolution": 1e-6,
                "defaults": {
                    "read_v": 0.2,
                    "vbase": 0.2,
                    "pulse_ms": 1.0,
                    "triangle": {"vmin": 0.0, "vmax": 1.0, "step": 0.05, "delay_s": 0.05}
                }
            },
            "Keithley 4200A_smu": {
                "min_timing_us": 100,
                "max_update_rate": 5000,
                "rise_fall_time_us": 20,
                "min_pulse_width_ms": 0.5,
                "voltage_range_V": (-210, 210),
                "current_range_A": (-1, 1),
                "compliance_resolution": 1e-9,
                "defaults": {
                    "read_v": 0.2,
                    "vbase": 0.2,
                    "pulse_ms": 0.5,
                    "triangle": {"vmin": 0.0, "vmax": 1.0, "step": 0.05, "delay_s": 0.02}
                }
            },
            "Keithley 4200A_pmu": {
                "min_timing_us": 10,
                "max_update_rate": 10000,
                "rise_fall_time_us": 0.01,
                "min_pulse_width_ms": 0.00005,  # 50 µs
                "voltage_range_V": (-10, 10),
                "current_range_A": (-0.1, 0.1),  # ±100 mA
                "compliance_resolution": 1e-6,
                "bandwidth_MHz": 5
            },
            "HP4140B": {
                "min_timing_ms": 5,
                "max_update_rate": 20,
                "voltage_range_V": (-100, 100),
                "current_range_A": (1e-14, 1e-2),
                "pulse_capability": None,
                "integration_modes": ["short", "medium", "long"]
            }
        }
    

    def get_limits(self, smu_type: str) -> dict:
        """Get timing limits for the specified SMU type."""
        return self.limits.get(smu_type, self.limits["Keithley 2401"])

    def update_limits(self, smu_type: str, **kwargs):
        """Update timing limits for a specific SMU type."""
        if smu_type not in self.limits:
            self.limits[smu_type] = {}
        self.limits[smu_type].update(kwargs)

    def get_defaults(self, smu_type: str) -> dict:
        """Return sensible per-model defaults (read_v, vbase, pulse_ms, triangle)."""
        lim = self.get_limits(smu_type)
        return lim.get("defaults", self.limits["Keithley 2401"].get("defaults", {}))


class MeasurementService:
    """
    Centralized measurement engine for IV, retention, pulse, and endurance flows.

    Responsibilities
    - Compute voltage ranges for different sweep types
    - Run IV sweeps with LED control, pause-at-extrema, and stop hooks
    - Run retention measurements
    - Run pulse measurements with timing validation
    - Return data in the unified format: (v_arr, c_arr, timestamps)

    This class is UI-agnostic. The caller can provide optional callbacks to
    receive per-point updates for plotting without coupling this class to the GUI.
    """

    def __init__(self):
        self.smu_limits = SMULimits()

    # --------------------------
    # Pulse session helpers
    # --------------------------
    def begin_pulse_session(self, keithley, icc: float, *, v_range: float = 20.0, ovp: float = 21.0,
                            use_remote_sense: bool = False, autozero_off: bool = True) -> None:
        """Prepare SMU once for a batch of pulses; caller should later call end_pulse_session."""
        try:
            keithley.prepare_for_pulses(Icc=float(icc), v_range=float(v_range), ovp=float(ovp),
                                        use_remote_sense=bool(use_remote_sense), autozero_off=bool(autozero_off))
        except Exception:
            pass

    def end_pulse_session(self, keithley, icc: float, *, restore_autozero: bool = True) -> None:
        """Finish a pulse batch: return to 0 V, optionally restore autozero, disable output."""
        try:
            keithley.finish_pulses(Icc=float(icc), restore_autozero=bool(restore_autozero))
        except Exception:
            pass

    # --------------------------
    # Voltage range helpers
    # --------------------------
    def _frange(self, start: float, stop: float, step: float) -> List[float]:
        values: List[float] = []
        if step == 0:
            return values
        increasing = step > 0
        v = start
        if increasing:
            while v <= stop:
                values.append(round(v, 3))
                v += step
        else:
            while v >= stop:
                values.append(round(v, 3))
                v += step
        return values

    def compute_voltage_range(
        self,
        start_v: float,
        stop_v: float,
        step_v: float,
        sweep_type: str,
        mode: str = VoltageRangeMode.FIXED_STEP,
        neg_stop_v: Optional[float] = None,
        sweep_rate_v_per_s: Optional[float] = None,
        voltage_time_s: Optional[float] = None,
        step_delay_s: Optional[float] = None,
        num_steps: Optional[int] = None,
    ) -> List[float]:
        """
        Build the voltage array for the requested sweep type.

        sweep_type: "FS" (full), "PS" (positive), "NS" (negative)
        mode: controls how the effective step size or point count is derived
        """
        def travel_distance(v_start: float, v_stop_pos: float, kind: str, v_stop_neg_abs: Optional[float]) -> float:
            if kind == "PS":
                return abs(v_stop_pos - v_start) + abs(v_start - v_stop_pos)
            if kind == "NS":
                neg_target = -abs(v_stop_neg_abs if v_stop_neg_abs is not None else v_stop_pos)
                return abs(neg_target - v_start) + abs(v_start - neg_target)
            # FS
            neg_target = -abs(v_stop_neg_abs if v_stop_neg_abs is not None else v_stop_pos)
            return (
                abs(v_stop_pos - v_start)
                + abs(neg_target - v_stop_pos)
                + abs(v_start - neg_target)
            )

        # Determine effective step size for non-fixed-step modes
        effective_step_v = step_v
        if mode == VoltageRangeMode.FIXED_SWEEP_RATE:
            # Need sweep rate and step delay to determine step size
            if sweep_rate_v_per_s is None or (step_delay_s is None or step_delay_s <= 0):
                # Fallback to provided step_v if insufficient info
                effective_step_v = step_v
            else:
                effective_step_v = max(1e-9, abs(sweep_rate_v_per_s) * float(step_delay_s))
        elif mode == VoltageRangeMode.FIXED_VOLTAGE_TIME:
            # Use total time and step delay to compute number of steps, then step size from path length
            if voltage_time_s is not None and step_delay_s is not None and step_delay_s > 0:
                steps_float = max(1.0, float(voltage_time_s) / float(step_delay_s))
                # If explicit num_steps provided, prefer it
                steps_float = float(num_steps) if num_steps and num_steps > 0 else steps_float
                dist = travel_distance(start_v, stop_v, sweep_type, abs(neg_stop_v) if neg_stop_v is not None else None)
                effective_step_v = max(1e-9, dist / steps_float)
            else:
                effective_step_v = step_v

        step = effective_step_v if effective_step_v is not None else step_v

        if sweep_type == "NS":
            neg_target = -abs(neg_stop_v if neg_stop_v is not None else stop_v)
            return (
                self._frange(start_v, neg_target, -abs(step))
                + self._frange(neg_target, start_v, abs(step))
            )
        if sweep_type == "PS":
            return (
                self._frange(start_v, stop_v, abs(step))
                + self._frange(stop_v, start_v, -abs(step))
            )
        # Default: Full sweep (FS)
        neg_target = -abs(neg_stop_v if neg_stop_v is not None else stop_v)
        return (
            self._frange(start_v, stop_v, abs(step))
            + self._frange(stop_v, neg_target, -abs(step))
            + self._frange(neg_target, start_v, abs(step))
        )

    # --------------------------
    # Core measurement routines
    # --------------------------
    def run_iv_sweep(
        self,
        *,
        keithley,
        icc: float,
        sweeps: int = 1,
        step_delay: float = 0.05,
        start_v: Optional[float] = None,
        stop_v: Optional[float] = None,
        neg_stop_v: Optional[float] = None,
        step_v: Optional[float] = None,
        sweep_type: str = "FS",
        mode: str = VoltageRangeMode.FIXED_STEP,
        voltage_range: Optional[Iterable[float]] = None,
        sweep_rate_v_per_s: Optional[float] = None,
        total_time_s: Optional[float] = None,
        num_steps: Optional[int] = None,
        smu_type: str = "Keithley 2400",
        psu=None,
        led: bool = False,
        power: float = 1.0,
        sequence: Optional[Iterable[str]] = None,
        pause_s: float = 0.0,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Execute IV sweeps and return arrays (v_arr, c_arr, timestamps).
        - If voltage_range is None, it will be computed from (start_v, stop_v, neg_stop_v, step_v, sweep_type, mode).
        - LED control: if led==True, turn on via psu.led_on_380(power) for sweeps where sequence toggles '1'.
        - Pause behavior: dwell at v_max/v_min after first arrival by pause_s seconds.
        - Stop hook: if should_stop() is True, aborts early and returns accumulated arrays.
        - on_point: callback called as on_point(v, current_A, t_s) for live plotting.
        """
        if voltage_range is None:
            if start_v is None or stop_v is None:
                raise ValueError("Must provide voltage_range or (start_v, stop_v)")
            # For fixed step, require step_v; for others, compute from rate/time
            step_val = 0.0 if step_v is None else float(step_v)
            voltage_range = self.compute_voltage_range(
                float(start_v), float(stop_v), step_val, sweep_type, mode,
                neg_stop_v=neg_stop_v,
                sweep_rate_v_per_s=sweep_rate_v_per_s,
                voltage_time_s=total_time_s,
                step_delay_s=float(step_delay) if step_delay is not None else None,
                num_steps=num_steps,
            )

        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []

        # Derive extrema for pause behavior
        v_list = list(voltage_range)
        if not v_list:
            return v_arr, c_arr, t_arr
        v_max = max(v_list)
        v_min = min(v_list)
        prev_v = None

        start_time = time.perf_counter()

        # Precondition instrument (smu_type is reserved for future device-specific differences)
        try:
            keithley.set_voltage(0, icc)
            keithley.enable_output(True)
        except Exception:
            pass

        for sweep_idx in range(int(sweeps)):
            # Determine LED state for this sweep
            led_state = '1' if led else '0'
            if sequence is not None:
                try:
                    seq_list = list(sequence)
                    if sweep_idx < len(seq_list):
                        led_state = str(seq_list[sweep_idx])
                except Exception:
                    pass

            # Apply LED per-sweep
            try:
                if psu is not None:
                    if led_state == '1':
                        psu.led_on_380(power)
                    else:
                        # only turn off if LED feature is in use
                        if led:
                            psu.led_off_380()
            except Exception:
                pass

            for v in v_list:
                if should_stop and should_stop():
                    break
                try:
                    keithley.set_voltage(v, icc)
                except Exception:
                    # attempt to continue but capture what we can
                    pass
                time.sleep(0.1)
                try:
                    current_tuple = keithley.measure_current()
                    current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
                except Exception:
                    current = float('nan')

                t_now = time.time() - start_time

                v_arr.append(v)
                c_arr.append(current)
                t_arr.append(t_now)

                if on_point:
                    try:
                        on_point(v, current, t_now)
                    except Exception:
                        pass

                time.sleep(max(0.0, float(step_delay)))

                # Pause at extrema only once per arrival
                if pause_s:
                    if (v == v_max or v == v_min) and v != prev_v:
                        try:
                            keithley.set_voltage(0, icc)
                        except Exception:
                            pass
                        time.sleep(pause_s)
                prev_v = v

            if should_stop and should_stop():
                break

        # Always attempt to turn LED off at the end
        try:
            if psu is not None:
                psu.led_off_380()
        except Exception:
            pass

        try:
            keithley.set_voltage(0, icc)
            keithley.enable_output(False)
        except Exception:
            pass

        return v_arr, c_arr, t_arr

    def run_retention(
        self,
        *,
        keithley,
        set_voltage: float,
        set_time_s: float,
        read_voltage: float,
        repeat_delay_s: float,
        number: int,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2400",
        psu=None,
        led: bool = False,
        led_time_s: Optional[float] = None,
        sequence: Optional[Iterable[str]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Run a retention measurement. Returns (v_arr, c_arr, timestamps) where v_arr is the read voltage repeated.
        """
        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []

        start_t = time.perf_counter()

        # Session assumed prepared by caller

        # Optional LED handling (basic): turn on if requested
        try:
            if psu is not None and led:
                psu.led_on_380(1.0)
        except Exception:
            pass

        # Apply set pulse
        try:
            keithley.set_voltage(set_voltage, icc)
        except Exception:
            pass
        time.sleep(max(0.0, float(set_time_s)))

        # Switch to read voltage for sampling
        try:
            keithley.set_voltage(read_voltage, icc)
        except Exception:
            pass

        for i in range(int(number)):
            if should_stop and should_stop():
                break
            try:
                current_tuple = keithley.measure_current()
                current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
            except Exception:
                current = float('nan')
            t_now = time.time() - start_t
            v_arr.append(read_voltage)
            c_arr.append(current)
            t_arr.append(t_now)
            if on_point:
                try:
                    on_point(read_voltage, current, t_now)
                except Exception:
                    pass
            time.sleep(max(0.0, float(repeat_delay_s)))

        # Optional LED off
        try:
            if psu is not None and led:
                psu.led_off_380()
        except Exception:
            pass

        try:
            keithley.finish_pulses(Icc=float(icc), restore_autozero=True)
        except Exception:
            pass

        return v_arr, c_arr, t_arr

    # --------------------------
    # Endurance (basic pulse-based)
    # --------------------------
    def run_endurance(
        self,
        *,
        keithley,
        set_voltage: float,
        reset_voltage: float,
        pulse_width_s: float,
        num_cycles: int,
        read_voltage: float = 0.1,
        inter_cycle_delay_s: float = 0.0,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2400",
        psu=None,
        led: bool = False,
        power: float = 1.0,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Minimal endurance loop: alternate set/reset pulses and sample read current after each pulse.
        Returns arrays of (V_read, I_read, t_s) for each read sample in sequence.
        """
        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []
        start_t = time.time()

        try:
            keithley.prepare_for_pulses(Icc=float(icc), v_range=20.0, ovp=21.0,
                                        use_remote_sense=False, autozero_off=True)
        except Exception:
            pass

        # LED handling (optional)
        try:
            if psu is not None and led:
                psu.led_on_380(power)
        except Exception:
            pass

        for k in range(int(num_cycles)):
            if should_stop and should_stop():
                break

            # SET pulse
            try:
                keithley.set_voltage(set_voltage, icc)
            except Exception:
                pass
            time.sleep(max(0.0, float(pulse_width_s)))

            # Read after SET
            try:
                keithley.set_voltage(read_voltage, icc)
                time.sleep(0.002)
                i_set = keithley.measure_current()
                i_set_val = i_set[1] if isinstance(i_set, (list, tuple)) and len(i_set) > 1 else float(i_set)
            except Exception:
                i_set_val = float('nan')
            t_now = time.perf_counter() - start_t
            v_arr.append(read_voltage); c_arr.append(i_set_val); t_arr.append(t_now)
            if on_point:
                try: on_point(read_voltage, i_set_val, t_now)
                except Exception: pass

            if should_stop and should_stop():
                break

            # RESET pulse
            try:
                keithley.set_voltage(reset_voltage, icc)
            except Exception:
                pass
            time.sleep(max(0.0, float(pulse_width_s)))

            # Read after RESET
            try:
                keithley.set_voltage(read_voltage, icc)
                time.sleep(0.002)
                i_reset = keithley.measure_current()
                i_reset_val = i_reset[1] if isinstance(i_reset, (list, tuple)) and len(i_reset) > 1 else float(i_reset)
            except Exception:
                i_reset_val = float('nan')
            t_now = time.perf_counter() - start_t
            v_arr.append(read_voltage); c_arr.append(i_reset_val); t_arr.append(t_now)
            if on_point:
                try: on_point(read_voltage, i_reset_val, t_now)
                except Exception: pass

            if inter_cycle_delay_s:
                post_start = time.perf_counter()
                buf_i: List[float] = []
                buf_t: List[float] = []
                while (time.perf_counter() - post_start) < float(inter_cycle_delay_s):
                    if should_stop and should_stop():
                        break
                    try:
                        it = keithley.measure_current()
                        iv = it[1] if isinstance(it, (list, tuple)) and len(it) > 1 else float(it)
                    except Exception:
                        iv = float('nan')
                    buf_i.append(iv)
                    buf_t.append(time.perf_counter() - start_t)
                if buf_t:
                    c_arr.extend(buf_i)
                    t_arr.extend(buf_t)
                    try:
                        v_arr.extend([read_voltage] * len(buf_t))
                    except Exception:
                        for _ in buf_t:
                            v_arr.append(read_voltage)

        # Cleanup
        try:
            if psu is not None and led:
                psu.led_off_380()
        except Exception:
            pass
        try:
            keithley.set_voltage(0, icc)
            keithley.enable_output(False)
        except Exception:
            pass

        return v_arr, c_arr, t_arr

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
        sequence: Optional[Iterable[str]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        validate_timing: bool = True,
        start_at_zero: bool = True,
        return_to_zero_at_end: bool = True,
        reset_should_stop: Optional[Callable[[], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Run pulse measurements with timing validation and LED control.

        Parameters:
        - pulse_voltage: Voltage level for the pulse (V)
        - pulse_width_ms: Duration of each pulse in milliseconds
        - num_pulses: Number of pulses to apply
        - read_voltage: Voltage to use for reading current after each pulse (V)
        - inter_pulse_delay_s: Delay between pulses in seconds
        - smu_type: SMU type for timing validation ("Keithley 4200A", "Keithley 4200A_pmu", "Keithley 2401", etc.)
        - validate_timing: Whether to validate pulse width against SMU limits
        - Other parameters: same as other measurement methods (LED control, callbacks, etc.)

        Supported SMU Types:
        - "Keithley 4200A": Standard SMU mode (min pulse width: 0.5 ms)
        - "Keithley 4200A_pmu": Pulse Measurement Unit mode (min pulse width: 0.05 ms)
        - "Keithley 2401": 2401 series (min pulse width: 1.0 ms)
        - "Keithley 2400": 2400 series (min pulse width: 1.0 ms)

        Returns:
        Tuple of (v_arr, c_arr, timestamps) where:
        - v_arr: Applied voltage for each measurement point
        - c_arr: Measured current values
        - timestamps: Time stamps for each measurement
        """
        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []

        # Validate timing constraints
        if validate_timing:
            limits = self.smu_limits.get_limits(smu_type)
            min_pulse_width = limits["min_pulse_width_ms"]
            if pulse_width_ms < min_pulse_width:
                raise ValueError(
                    f"Pulse width {pulse_width_ms} ms is below minimum "
                    f"for {smu_type} ({min_pulse_width} ms)"
                )

        start_time = time.perf_counter()
        # Optional: reset external stop flag provided by GUI
        if reset_should_stop:
            try:
                reset_should_stop()
            except Exception:
                pass

        # Assumes caller/session manager already prepared; only set initial level if needed
        try:
            if not start_at_zero:
                keithley.set_voltage(read_voltage, icc)
        except Exception:
            pass

        # LED setup if requested
        try:
            if psu is not None and led:
                psu.led_on_380(power)
        except Exception:
            pass

        for pulse_idx in range(int(num_pulses)):
            if should_stop and should_stop():
                break

            # Determine LED state for this pulse
            led_state = '1' if led else '0'
            if sequence is not None:
                try:
                    seq_list = list(sequence)
                    if pulse_idx < len(seq_list):
                        led_state = str(seq_list[pulse_idx])
                except Exception:
                    pass

            # Apply LED state if using sequence
            if sequence is not None:
                try:
                    if psu is not None:
                        if led_state == '1':
                            psu.led_on_380(power)
                        elif led:
                            psu.led_off_380()
                except Exception:
                    pass

            # Apply pulse (no sampling during the pulse window)
            try:
                keithley.set_voltage(pulse_voltage, icc)
            except Exception:
                pass

            pulse_start = time.perf_counter()
            pulse_width_s = pulse_width_ms / 1000.0
            while (time.perf_counter() - pulse_start) < pulse_width_s:
                if should_stop and should_stop():
                    break
                # Very small sleep to avoid 100% CPU busy-wait
                time.sleep(0.00001)

            if should_stop and should_stop():
                break

            # Return to read voltage
            try:
                keithley.set_voltage(read_voltage, icc)
            except Exception:
                pass

            # Forced immediate single read after returning to read voltage
            try:
                #time.sleep(0.0001)  # brief settle
                current_tuple = keithley.measure_current()
                current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
            except Exception:
                current = float('nan')
            t_now = time.perf_counter() - start_time
            v_arr.append(read_voltage)
            c_arr.append(current)
            t_arr.append(t_now)
            if on_point:
                try:
                    on_point(read_voltage, current, t_now)
                except Exception:
                    pass

            # Continue sampling until inter-pulse delay elapses
            if inter_pulse_delay_s > 0:
                post_start = time.perf_counter()
                buf_t: List[float] = []
                buf_i: List[float] = []
                while (time.perf_counter() - post_start) < float(inter_pulse_delay_s):
                    if should_stop and should_stop():
                        break
                    try:
                        current_tuple = keithley.measure_current()
                        current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
                    except Exception:
                        current = float('nan')
                    t_now = time.perf_counter() - start_time
                    buf_t.append(t_now)
                    buf_i.append(current)
                # Bulk-extend once at the end to reduce overhead
                if buf_t:
                    t_arr.extend(buf_t)
                    c_arr.extend(buf_i)
                    try:
                        v_arr.extend([read_voltage] * len(buf_t))
                    except Exception:
                        for _ in buf_t:
                            v_arr.append(read_voltage)

        # Cleanup
        try:
            if psu is not None and led:
                psu.led_off_380()
        except Exception:
            pass

        # Do not finish session here; caller/high-level manages session

        return v_arr, c_arr, t_arr

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
        """Fire one pulse and capture measured V/I during pulse and after returning to read voltage.

        Returns a dict with keys:
        - pulse_v_cmd, pulse_v_meas, pulse_i_meas
        - read_v_meas, read_i_meas
        - pulse_width_ms
        """
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
                    return float(v[-1] if len(v) > 0 else float('nan'))
                return float(v)
            except Exception:
                return float('nan')

        def _mi():
            try:
                it = keithley.measure_current()
                return float(it[1]) if isinstance(it, (list, tuple)) and len(it) > 1 else float(it)
            except Exception:
                return float('nan')

        out = {
            "pulse_v_cmd": float(pulse_voltage),
            "pulse_v_meas": float('nan'),
            "pulse_i_meas": float('nan'),
            "read_v_meas": float('nan'),
            "read_i_meas": float('nan'),
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
    ) -> Tuple[List[float], List[float], List[float]]:
        """Amplitude-sweep pulsed IV using a standard SMU.

        Supports single-slope or full-sweep shapes via sweep_type:
        - PS: start_v → stop_v → start_v
        - NS: start_v → −|neg_stop_v or stop_v| → start_v
        - FS (default): start_v → stop_v → −|neg_stop_v or stop_v| → start_v

        For each amplitude point, applies one pulse (pulse_width_ms), returns to vbase,
        and samples current. The returned arrays are (amplitudes, read_currents, timestamps).
        """
        # Optional: reset external stop flag prior to run
        if reset_should_stop:
            try:
                reset_should_stop()
            except Exception:
                pass
        # Build amplitude list according to sweep_type
        amps: List[float] = []
        sv = float(start_v); ev = float(stop_v)
        # helper to build linear range including endpoint
        def _linrange(v0: float, v1: float, step_opt: Optional[float], nsteps_opt: Optional[int]) -> List[float]:
            out: List[float] = []
            if step_opt is not None and float(step_opt) != 0.0:
                s = float(step_opt) if v1 >= v0 else -abs(float(step_opt))
                v = v0
                if s > 0:
                    while v <= v1 + 1e-12:
                        out.append(round(v, 6)); v += s
                else:
                    while v >= v1 - 1e-12:
                        out.append(round(v, 6)); v += s
            elif nsteps_opt is not None and int(nsteps_opt) > 1:
                n = int(nsteps_opt)
                step = (v1 - v0) / float(n - 1)
                out = [round(v0 + i * step, 6) for i in range(n)]
            else:
                out = [round(v0, 6)] if abs(v1 - v0) < 1e-15 else [round(v0, 6), round(v1, 6)]
            return out

        if sweep_type == "PS":
            amps = _linrange(sv, ev, step_v, num_steps) + _linrange(ev, sv, step_v, num_steps)
        elif sweep_type == "NS":
            nv = -abs(neg_stop_v if neg_stop_v is not None else ev)
            amps = _linrange(sv, nv, step_v, num_steps) + _linrange(nv, sv, step_v, num_steps)
        else:  # FS
            nv = -abs(neg_stop_v if neg_stop_v is not None else ev)
            amps = (
                _linrange(sv, ev, step_v, num_steps)
                + _linrange(ev, nv, step_v, num_steps)
                + _linrange(nv, sv, step_v, num_steps)
            )

        # Default pulse width from SMU limits if not provided
        if pulse_width_ms is None:
            try:
                pulse_width_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
            except Exception:
                pulse_width_ms = 1.0

        v_out: List[float] = []
        i_out: List[float] = []
        t_out: List[float] = []
        t0 = time.perf_counter()

        if manage_session:
            self.begin_pulse_session(keithley, icc, v_range=20.0, ovp=21.0, use_remote_sense=False, autozero_off=True)
        try:
            for amp in amps:
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
                    psu=None,
                    led=False,
                    power=1.0,
                    sequence=None,
                    should_stop=should_stop,
                    on_point=None,
                    validate_timing=validate_timing,
                )
                try:
                    i_val = float(_i[-1]) if _i else float('nan')
                except Exception:
                    i_val = float('nan')
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
        finally:
            if manage_session:
                self.end_pulse_session(keithley, icc, restore_autozero=True)
        return v_out, i_out, t_out

    def run_pulsed_iv_sweep_debug(
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
        """Like run_pulsed_iv_sweep but also records measured V/I during pulse and at read.

        Returns (V_amp_list, I_read_list, t_list, debug_records).
        Each debug record is a dict from run_pulse_measurement_debug.
        """
        # Build amplitude list
        amps: List[float] = []
        sv = float(start_v); ev = float(stop_v)
        def _linrange(v0: float, v1: float, step_opt: Optional[float], nsteps_opt: Optional[int]) -> List[float]:
            out: List[float] = []
            if step_opt is not None and float(step_opt) != 0.0:
                s = float(step_opt) if v1 >= v0 else -abs(float(step_opt))
                v = v0
                if s > 0:
                    while v <= v1 + 1e-12:
                        out.append(round(v, 6)); v += s
                else:
                    while v >= v1 - 1e-12:
                        out.append(round(v, 6)); v += s
            elif nsteps_opt is not None and int(nsteps_opt) > 1:
                n = int(nsteps_opt)
                step = (v1 - v0) / float(n - 1)
                out = [round(v0 + i * step, 6) for i in range(n)]
            else:
                out = [round(v0, 6)] if abs(v1 - v0) < 1e-15 else [round(v0, 6), round(v1, 6)]
            return out
        if sweep_type == "PS":
            amps = _linrange(sv, ev, step_v, num_steps) + _linrange(ev, sv, step_v, num_steps)
        elif sweep_type == "NS":
            nv = -abs(neg_stop_v if neg_stop_v is not None else ev)
            amps = _linrange(sv, nv, step_v, num_steps) + _linrange(nv, sv, step_v, num_steps)
        else:
            nv = -abs(neg_stop_v if neg_stop_v is not None else ev)
            amps = (
                _linrange(sv, ev, step_v, num_steps)
                + _linrange(ev, nv, step_v, num_steps)
                + _linrange(nv, sv, step_v, num_steps)
            )

        # Default pulse width
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

        # Pre-enable output at base
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
            # Read-back current at read (immediate measurement)
            i_val = float(rec.get("read_i_meas", float('nan')))
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

        # Leave output at 0 V for safety
        try:
            keithley.set_voltage(0.0, float(icc))
        except Exception:
            pass
        try:
            keithley.enable_output(False)
        except Exception:
            pass

        return v_out, i_out, t_out, dbg

    def run_ispp(
        self,
        *,
        keithley,
        start_v: float,
        stop_v: float,
        step_v: float,
        vbase: float = 0.2,
        pulse_width_ms: Optional[float] = None,
        target_current_a: float = 1e-5,
        inter_step_delay_s: float = 0.0,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        validate_timing: bool = True,
    ) -> Tuple[List[float], List[float], List[float]]:
        """SMU Incremental Step Pulse Programming until reaching target current magnitude.

        Increments amplitude from start_v to stop_v by step_v (sign-sensitive) and
        stops when |I_read| >= |target_current_a| or the range is exhausted.
        Returns (amp_list, i_list, t_list).
        """
        if pulse_width_ms is None:
            try:
                pulse_width_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
            except Exception:
                pulse_width_ms = 1.0

        amps: List[float] = []
        i_list: List[float] = []
        t_list: List[float] = []
        t0 = time.time()

        sv = float(start_v); ev = float(stop_v)
        s = float(step_v) if (ev >= sv) else -abs(float(step_v))
        if s == 0.0:
            s = 0.1 if ev >= sv else -0.1
        v = sv
        while (s > 0 and v <= ev + 1e-12) or (s < 0 and v >= ev - 1e-12):
            if should_stop and should_stop():
                break
            _v, _i, _t = self.run_pulse_measurement(
                keithley=keithley,
                pulse_voltage=float(v),
                pulse_width_ms=float(pulse_width_ms),
                num_pulses=1,
                read_voltage=float(vbase),
                inter_pulse_delay_s=0.0,
                icc=float(icc),
                smu_type=smu_type,
                psu=None,
                led=False,
                power=1.0,
                sequence=None,
                should_stop=should_stop,
                on_point=None,
                validate_timing=validate_timing,
            )
            try:
                i_val = float(_i[-1]) if _i else float('nan')
            except Exception:
                i_val = float('nan')
            amps.append(float(v)); i_list.append(i_val); t_list.append(time.time() - t0)
            if on_point:
                try: on_point(float(v), i_val, t_list[-1])
                except Exception: pass
            try:
                if abs(i_val) >= abs(float(target_current_a)):
                    break
            except Exception:
                pass
            if inter_step_delay_s and inter_step_delay_s > 0:
                time.sleep(max(0.0, float(inter_step_delay_s)))
            v += s

        return amps, i_list, t_list

    def run_pulse_width_sweep(
        self,
        *,
        keithley,
        amplitude_v: float,
        widths_ms: Iterable[float],
        vbase: float = 0.2,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        inter_step_delay_s: float = 0.0,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        validate_timing: bool = True,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Sweep pulse width at fixed amplitude using a standard SMU.

        For each width (ms), apply one pulse and read at vbase. Returns (width_ms_list, i_list, t_list).
        """
        out_w: List[float] = []
        out_i: List[float] = []
        out_t: List[float] = []
        t0 = time.time()
        # Get min pulse
        try:
            min_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
        except Exception:
            min_ms = 1.0
        # Baseline: hold at vbase and take a few readings before any pulses
        try:
            keithley.enable_output(True)
            keithley.set_voltage(float(vbase), float(icc))
        except Exception:
            pass
        baseline_start = time.perf_counter()
        baseline_duration_s = 0.002
        while (time.perf_counter() - baseline_start) < baseline_duration_s:
            if should_stop and should_stop():
                break
            try:
                current_tuple = keithley.measure_current()
                current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
            except Exception:
                current = float('nan')
            out_w.append(0.0)
            out_i.append(current)
            out_t.append(time.time() - t0)
        # Sweep widths
        for w in widths_ms:
            if should_stop and should_stop():
                break
            w_ms = max(min_ms, float(w))
            _v, _i, _t = self.run_pulse_measurement(
                keithley=keithley,
                pulse_voltage=float(amplitude_v),
                pulse_width_ms=w_ms,
                num_pulses=1,
                read_voltage=float(vbase),
                inter_pulse_delay_s=float(inter_step_delay_s),
                icc=float(icc),
                smu_type=smu_type,
                psu=None,
                led=False,
                power=1.0,
                sequence=None,
                should_stop=should_stop,
                on_point=None,
                validate_timing=validate_timing,
                start_at_zero=False,
                return_to_zero_at_end=False,
            )
            try:
                i_val = float(_i[-1]) if _i else float('nan')
            except Exception:
                i_val = float('nan')
            out_w.append(w_ms); out_i.append(i_val); out_t.append(time.perf_counter() - t0)
            if on_point:
                try: on_point(w_ms, i_val, out_t[-1])
                except Exception: pass
            # After pulse, keep holding at vbase and sample during the inter-step window
            if inter_step_delay_s and inter_step_delay_s > 0:
                post_start = time.perf_counter()
                while (time.perf_counter() - post_start) < float(inter_step_delay_s):
                    if should_stop and should_stop():
                        break
                    try:
                        current_tuple = keithley.measure_current()
                        current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
                    except Exception:
                        current = float('nan')
                    out_w.append(w_ms)
                    out_i.append(current)
                    out_t.append(time.perf_counter() - t0)

        keithley.set_voltage(0)
        keithley.enable_output(True)
        return out_w, out_i, out_t

    def run_threshold_search(
        self,
        *,
        keithley,
        v_low: float,
        v_high: float,
        vbase: float = 0.2,
        pulse_width_ms: Optional[float] = None,
        target_current_a: float = 1e-5,
        max_iters: int = 12,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        validate_timing: bool = True,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Binary search for minimal |V| in [v_low, v_high] that yields |I| >= target_current_a.

        Returns (tried_voltages, measured_currents, timestamps). Assumes monotonic response in range.
        """
        if pulse_width_ms is None:
            try:
                pulse_width_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
            except Exception:
                pulse_width_ms = 1.0
        v_lo = float(min(v_low, v_high))
        v_hi = float(max(v_low, v_high))
        tried_v: List[float] = []
        tried_i: List[float] = []
        tried_t: List[float] = []
        t0 = time.time()
        for _ in range(max(1, int(max_iters))):
            if should_stop and should_stop():
                break
            v_mid = 0.5 * (v_lo + v_hi)
            _v, _i, _t = self.run_pulse_measurement(
                keithley=keithley,
                pulse_voltage=v_mid,
                pulse_width_ms=float(pulse_width_ms),
                num_pulses=1,
                read_voltage=float(vbase),
                inter_pulse_delay_s=0.0,
                icc=float(icc),
                smu_type=smu_type,
                psu=None,
                led=False,
                power=1.0,
                sequence=None,
                should_stop=should_stop,
                on_point=None,
                validate_timing=validate_timing,
            )
            try:
                i_val = float(_i[-1]) if _i else float('nan')
            except Exception:
                i_val = float('nan')
            tried_v.append(v_mid); tried_i.append(i_val); tried_t.append(time.time() - t0)
            if on_point:
                try: on_point(v_mid, i_val, tried_t[-1])
                except Exception: pass
            if abs(i_val) >= abs(float(target_current_a)):
                # shrink upper bound
                v_hi = v_mid
            else:
                v_lo = v_mid
            if abs(v_hi - v_lo) < 1e-6:
                break
        return tried_v, tried_i, tried_t
    def run_dc_capture(
        self,
        *,
        keithley,
        voltage_v: float,
        capture_time_s: float,
        sample_dt_s: float = 0.01,
        icc: float = 1e-4,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Hold a DC bias and sample current vs time using a standard SMU.

        Returns (v_arr, i_arr, t_arr) where v_arr is constant at voltage_v.
        """
        v_arr: List[float] = []
        i_arr: List[float] = []
        t_arr: List[float] = []

        try:
            keithley.enable_output(True)
            keithley.set_voltage(float(voltage_v), float(icc))
        except Exception:
            pass

        t0 = time.perf_counter()
        while (time.perf_counter() - t0) < float(capture_time_s):
            if should_stop and should_stop():
                break
            try:
                current_tuple = keithley.measure_current()
                current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
            except Exception:
                current = float('nan')
            t_now = time.perf_counter() - t0
            v_arr.append(float(voltage_v))
            i_arr.append(current)
            t_arr.append(t_now)
            if on_point:
                try:
                    on_point(float(voltage_v), current, t_now)
                except Exception:
                    pass
            if sample_dt_s and sample_dt_s > 0:
                time.sleep(max(0.0, float(sample_dt_s)))

        try:
            keithley.set_voltage(0.0, float(icc))
            keithley.enable_output(False)
        except Exception:
            pass

        return v_arr, i_arr, t_arr

    def run_transient_decay(
        self,
        *,
        keithley,
        pulse_voltage: float,
        pulse_width_ms: float,
        read_voltage: float = 0.2,
        capture_time_s: float = 1.0,
        sample_dt_s: float = 0.001,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Apply a single pulse, then hold at read_voltage and sample I(t).

        Returns (t_arr, i_arr, v_arr_read) where v_arr_read is constant at read_voltage.
        """
        # Enforce minimum pulse width from limits
        try:
            min_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
        except Exception:
            min_ms = 1.0
        w_ms = max(min_ms, float(pulse_width_ms))

        # Fire the set pulse (session assumed prepared by caller)
        try:
            keithley.set_voltage(float(pulse_voltage), float(icc))
        except Exception:
            pass
        t0 = time.perf_counter()
        while (time.perf_counter() - t0) < (w_ms / 1000.0):
            if should_stop and should_stop():
                break
            time.sleep(0.001)

        # Switch to read voltage and sample decay
        try:
            keithley.set_voltage(float(read_voltage), float(icc))
        except Exception:
            pass

        t_arr: List[float] = []
        i_arr: List[float] = []
        v_arr: List[float] = []
        t1 = time.perf_counter()
        while (time.perf_counter() - t1) < float(capture_time_s):
            if should_stop and should_stop():
                break
            try:
                current_tuple = keithley.measure_current()
                current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
            except Exception:
                current = float('nan')
            now = time.perf_counter() - t1
            t_arr.append(now)
            i_arr.append(current)
            v_arr.append(float(read_voltage))
            if on_point:
                try:
                    on_point(float(read_voltage), current, now)
                except Exception:
                    pass
            if sample_dt_s and sample_dt_s > 0:
                time.sleep(max(0.0, float(sample_dt_s)))

        # Leave session open for caller to finish

        return t_arr, i_arr, v_arr

    def run_ppf(
        self,
        *,
        keithley,
        pulse_voltage: float,
        pulse_width_ms: float,
        dt_list_s: Iterable[float],
        read_voltage: float = 0.2,
        read_settle_s: float = 0.002,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        timeseries_out: Optional[Tuple[List[float], List[float], List[float]]] = None,
    ) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Paired-pulse facilitation: two pulses separated by Δt; measure I1 and I2 at Vread.

        Returns (dt_list, I1_list, I2_list, ppf_index_list) where ppf_index=(I2 - I1)/max(|I1|,eps).
        """
        # Enforce min pulse width
        try:
            min_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
        except Exception:
            min_ms = 1.0
        w_ms = max(min_ms, float(pulse_width_ms))

        out_dt: List[float] = []
        out_i1: List[float] = []
        out_i2: List[float] = []
        out_ppf: List[float] = []
        eps = 1e-15
        try:
            keithley.prepare_for_pulses(Icc=float(icc), v_range=20.0, ovp=21.0,
                                        use_remote_sense=False, autozero_off=True)
        except Exception:
            pass
        t_ref = time.perf_counter()
        for dt_s in list(dt_list_s or []):
            if should_stop and should_stop():
                break
            # Pulse 1
            try:
                keithley.set_voltage(float(pulse_voltage), float(icc))
            except Exception:
                pass
            t0 = time.time()
            while (time.time() - t0) < (w_ms / 1000.0):
                if should_stop and should_stop():
                    break
                time.sleep(0.001)
            # Switch to read and sample I1
            try:
                keithley.set_voltage(float(read_voltage), float(icc))
            except Exception:
                pass
            if read_settle_s and read_settle_s > 0:
                time.sleep(max(0.0, float(read_settle_s)))
            try:
                i1_t = keithley.measure_current()
                i1 = i1_t[1] if isinstance(i1_t, (list, tuple)) and len(i1_t) > 1 else float(i1_t)
            except Exception:
                i1 = float('nan')

            # Wait Δt before pulse 2
            if dt_s and dt_s > 0:
                t_wait = float(dt_s)
                t1 = time.perf_counter()
                while (time.perf_counter() - t1) < t_wait:
                    if should_stop and should_stop():
                        break
                    # sample continuously during the wait at read voltage
                    try:
                        itmp = keithley.measure_current()
                        ival = itmp[1] if isinstance(itmp, (list, tuple)) and len(itmp) > 1 else float(itmp)
                    except Exception:
                        ival = float('nan')
                    if timeseries_out is not None:
                        v_ts, i_ts, t_ts = timeseries_out
                        v_ts.append(float(read_voltage))
                        i_ts.append(ival)
                        t_ts.append(time.perf_counter() - t_ref)
                    time.sleep(0.0001)

            # Pulse 2
            try:
                keithley.set_voltage(float(pulse_voltage), float(icc))
            except Exception:
                pass
            t2 = time.perf_counter()
            while (time.perf_counter() - t2) < (w_ms / 1000.0):
                if should_stop and should_stop():
                    break
                time.sleep(0.001)

            # Switch to read and sample I2
            try:
                keithley.set_voltage(float(read_voltage), float(icc))
            except Exception:
                pass
            if read_settle_s and read_settle_s > 0:
                time.sleep(max(0.0, float(read_settle_s)))
            try:
                i2_t = keithley.measure_current()
                i2 = i2_t[1] if isinstance(i2_t, (list, tuple)) and len(i2_t) > 1 else float(i2_t)
            except Exception:
                i2 = float('nan')

            out_dt.append(float(dt_s)); out_i1.append(i1); out_i2.append(i2)
            denom = max(abs(i1), eps)
            out_ppf.append((i2 - i1) / denom)
            if on_point:
                try:
                    on_point(float(read_voltage), i2, float(dt_s))
                except Exception:
                    pass
        # Leave session open for caller to finish
        return out_dt, out_i1, out_i2, out_ppf

    def run_stdp(
        self,
        *,
        keithley,
        pre_voltage: float,
        post_voltage: float,
        pulse_width_ms: float,
        delta_t_list_s: Iterable[float],
        read_voltage: float = 0.2,
        read_settle_s: float = 0.002,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        timeseries_out: Optional[Tuple[List[float], List[float], List[float]]] = None,
    ) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Spike-timing dependent plasticity: pre/post pulses separated by Δt (±).

        For each Δt: if Δt>0, pre then wait Δt then post; else post then wait |Δt| then pre.
        Baseline I0 is measured at Vread before the pair; I_after measured after the pair.
        Returns (dt_list, I0_list, I_after_list, delta_w_list) where Δw=(I_after−I0)/max(|I0|,eps).
        """
        # Enforce min width
        try:
            min_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
        except Exception:
            min_ms = 1.0
        w_ms = max(min_ms, float(pulse_width_ms))
        out_dt: List[float] = []; I0_list: List[float] = []; I_after_list: List[float] = []; dW: List[float] = []
        eps = 1e-15
        # Session assumed prepared by caller
        t_ref = time.perf_counter()
        for dt in list(delta_t_list_s or []):
            if should_stop and should_stop(): break
            # Baseline
            try:
                keithley.set_voltage(float(read_voltage), float(icc))
                time.sleep(max(0.0, float(read_settle_s)))
                i0_t = keithley.measure_current()
                i0 = i0_t[1] if isinstance(i0_t, (list, tuple)) and len(i0_t) > 1 else float(i0_t)
            except Exception:
                i0 = float('nan')
            # Pulse order by sign of dt
            def pulse(level_v: float):
                try: keithley.set_voltage(float(level_v), float(icc))
                except Exception: pass
                t0 = time.perf_counter()
                while (time.perf_counter() - t0) < (w_ms / 1000.0):
                    if should_stop and should_stop(): break
                    time.sleep(0.001)
            if float(dt) >= 0:
                pulse(pre_voltage)
                # wait Δt
                t_wait = float(dt)
                t1 = time.perf_counter()
                while (time.perf_counter() - t1) < t_wait:
                    if should_stop and should_stop(): break
                    # sample during wait at read voltage
                    try:
                        _it = keithley.measure_current(); _iv = _it[1] if isinstance(_it, (list, tuple)) and len(_it) > 1 else float(_it)
                    except Exception:
                        _iv = float('nan')
                    if timeseries_out is not None:
                        v_ts, i_ts, t_ts = timeseries_out
                        v_ts.append(float(read_voltage)); i_ts.append(_iv); t_ts.append(time.perf_counter() - t_ref)
                    time.sleep(0.0001)
                pulse(post_voltage)
            else:
                pulse(post_voltage)
                t_wait = abs(float(dt))
                t1 = time.perf_counter()
                while (time.perf_counter() - t1) < t_wait:
                    if should_stop and should_stop(): break
                    try:
                        _it = keithley.measure_current(); _iv = _it[1] if isinstance(_it, (list, tuple)) and len(_it) > 1 else float(_it)
                    except Exception:
                        _iv = float('nan')
                    if timeseries_out is not None:
                        v_ts, i_ts, t_ts = timeseries_out
                        v_ts.append(float(read_voltage)); i_ts.append(_iv); t_ts.append(time.perf_counter() - t_ref)
                    time.sleep(0.0001)
                pulse(pre_voltage)
            # Measure after
            try:
                keithley.set_voltage(float(read_voltage), float(icc))
                time.sleep(max(0.0, float(read_settle_s)))
                ia_t = keithley.measure_current()
                ia = ia_t[1] if isinstance(ia_t, (list, tuple)) and len(ia_t) > 1 else float(ia_t)
            except Exception:
                ia = float('nan')
            out_dt.append(float(dt)); I0_list.append(i0); I_after_list.append(ia)
            denom = max(abs(i0), eps)
            dW.append((ia - i0) / denom)
        try:
            keithley.finish_pulses(Icc=float(icc), restore_autozero=True)
        except Exception:
            pass
        return out_dt, I0_list, I_after_list, dW

    def run_srdp(
        self,
        *,
        keithley,
        pulse_voltage: float,
        pulse_width_ms: float,
        freq_list_hz: Iterable[float],
        pulses_per_train: int = 20,
        read_voltage: float = 0.2,
        read_settle_s: float = 0.002,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        timeseries_out: Optional[Tuple[List[float], List[float], List[float]]] = None,
    ) -> Tuple[List[float], List[float]]:
        """Spike-rate dependent plasticity: trains at different frequencies; measure steady-state after each train.

        Returns (freq_list_hz, I_ss_list).
        """
        try:
            min_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
        except Exception:
            min_ms = 1.0
        w_s = max(min_ms, float(pulse_width_ms)) / 1000.0
        freqs: List[float] = []
        I_ss: List[float] = []
        # Session assumed prepared by caller
        t_ref = time.perf_counter()
        for f in list(freq_list_hz or []):
            if should_stop and should_stop(): break
            f = max(0.1, float(f))
            period = max(w_s * 1.1, 1.0 / f)
            # Train
            for _ in range(max(1, int(pulses_per_train))):
                try: keithley.set_voltage(float(pulse_voltage), float(icc))
                except Exception: pass
                t0 = time.perf_counter()
                while (time.perf_counter() - t0) < w_s:
                    if should_stop and should_stop(): break
                    time.sleep(0.001)
                try: keithley.set_voltage(float(read_voltage), float(icc))
                except Exception: pass
                t_gap = max(0.0, period - w_s)
                t1 = time.perf_counter()
                while (time.perf_counter() - t1) < t_gap:
                    if should_stop and should_stop(): break
                    try:
                        itgap = keithley.measure_current()
                        ivgap = itgap[1] if isinstance(itgap, (list, tuple)) and len(itgap) > 1 else float(itgap)
                    except Exception:
                        ivgap = float('nan')
                    if timeseries_out is not None:
                        v_ts, i_ts, t_ts = timeseries_out
                        v_ts.append(float(read_voltage)); i_ts.append(ivgap); t_ts.append(time.perf_counter() - t_ref)
                    time.sleep(0.0001)
            # Measure steady state
            try:
                time.sleep(max(0.0, float(read_settle_s)))
                i_t = keithley.measure_current()
                i_val = i_t[1] if isinstance(i_t, (list, tuple)) and len(i_t) > 1 else float(i_t)
            except Exception:
                i_val = float('nan')
            freqs.append(f); I_ss.append(i_val)
        try:
            keithley.set_voltage(0.0, float(icc)); keithley.enable_output(False)
        except Exception:
            pass
        return freqs, I_ss

    def run_pot_dep(
        self,
        *,
        keithley,
        set_voltage: float,
        reset_voltage: float,
        pulse_width_ms: float,
        cycles: int,
        read_voltage: float = 0.2,
        relax_s: float = 0.1,
        pulses_per_phase: int = 10,
        inter_pulse_gap_s: float = 0.0,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        timeseries_out: Optional[Tuple[List[float], List[float], List[float]]] = None,
        return_raw: bool = False,
    ) -> Tuple[List[int], List[float], List[float], List[float]]:
        """Potentiation/Depression: alternate +/− pulses; measure immediate and post-relax; compute volatility ratio.

        Returns (cycle_idx, I_immediate, I_post, ratio_list).
        """
        try: min_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
        except Exception: min_ms = 1.0
        w_s = max(min_ms, float(pulse_width_ms)) / 1000.0
        idx: List[int] = []; I_im: List[float] = []; I_post: List[float] = []; ratio: List[float] = []
        # Raw outputs (optional)
        f_t: List[float] = []; f_i: List[float] = []; f_v: List[float] = []; f_phase: List[int] = []  # phase: +1=set, -1=reset
        try: keithley.enable_output(True)
        except Exception: pass
        t_ref = time.perf_counter()
        for c in range(int(max(1, cycles))):
            if should_stop and should_stop(): break
            # Potentiation phase: apply pulses_per_phase pulses at set_voltage
            for _ in range(max(1, int(pulses_per_phase))):
                try: keithley.set_voltage(float(set_voltage), float(icc))
                except Exception: pass
                t0 = time.perf_counter()
                while (time.perf_counter() - t0) < w_s:
                    if should_stop and should_stop(): break
                    time.sleep(0.001)
                try: keithley.set_voltage(float(read_voltage), float(icc))
                except Exception: pass
                # optional brief settle
                time.sleep(0.0002)
                # Immediate read-back at Vread
                try:
                    itp = keithley.measure_current(); ivp = itp[1] if isinstance(itp, (list, tuple)) and len(itp) > 1 else float(itp)
                except Exception:
                    ivp = float('nan')
                if timeseries_out is not None:
                    v_ts, i_ts, t_ts = timeseries_out
                    v_ts.append(float(read_voltage)); i_ts.append(ivp); t_ts.append(time.perf_counter() - t_ref)
                if return_raw:
                    f_v.append(float(read_voltage)); f_i.append(ivp); f_t.append(time.perf_counter() - t_ref); f_phase.append(+1)
                # Sample as fast as possible during inter-pulse gap (if any)
                if inter_pulse_gap_s and inter_pulse_gap_s > 0:
                    t_gap = time.perf_counter()
                    while (time.perf_counter() - t_gap) < float(inter_pulse_gap_s):
                        if should_stop and should_stop(): break
                        try:
                            itgp = keithley.measure_current(); ivgp = itgp[1] if isinstance(itgp, (list, tuple)) and len(itgp) > 1 else float(itgp)
                        except Exception:
                            ivgp = float('nan')
                        if timeseries_out is not None:
                            v_ts, i_ts, t_ts = timeseries_out
                            v_ts.append(float(read_voltage)); i_ts.append(ivgp); t_ts.append(time.perf_counter() - t_ref)
                        if return_raw:
                            f_v.append(float(read_voltage)); f_i.append(ivgp); f_t.append(time.perf_counter() - t_ref); f_phase.append(+1)
                        time.sleep(0.0001)
            # Read immediate and relaxed after potentiation burst
            try:
                i1_t = keithley.measure_current(); i1 = i1_t[1] if isinstance(i1_t, (list, tuple)) and len(i1_t) > 1 else float(i1_t)
            except Exception:
                i1 = float('nan')
            if relax_s and relax_s > 0:
                t_rel = time.perf_counter()
                while (time.perf_counter() - t_rel) < float(relax_s):
                    if should_stop and should_stop(): break
                    try: it_rel = keithley.measure_current(); iv_rel = it_rel[1] if isinstance(it_rel, (list, tuple)) and len(it_rel) > 1 else float(it_rel)
                    except Exception: iv_rel = float('nan')
                    if timeseries_out is not None:
                        v_ts, i_ts, t_ts = timeseries_out
                        v_ts.append(float(read_voltage)); i_ts.append(iv_rel); t_ts.append(time.perf_counter() - t_ref)
                    time.sleep(0.0001)
            try:
                i2_t = keithley.measure_current(); i2 = i2_t[1] if isinstance(i2_t, (list, tuple)) and len(i2_t) > 1 else float(i2_t)
            except Exception:
                i2 = float('nan')
            idx.append(c + 1); I_im.append(i1); I_post.append(i2)
            denom = max(abs(i1), 1e-15); ratio.append((i1 - i2) / denom)
            # Depression phase: apply pulses_per_phase pulses at reset_voltage
            for _ in range(max(1, int(pulses_per_phase))):
                try: keithley.set_voltage(float(reset_voltage), float(icc))
                except Exception: pass
                t1 = time.perf_counter()
                while (time.perf_counter() - t1) < w_s:
                    if should_stop and should_stop(): break
                    time.sleep(0.001)
                try: keithley.set_voltage(float(read_voltage), float(icc))
                except Exception: pass
                time.sleep(0.0002)
                # Immediate read-back at Vread
                try:
                    itd = keithley.measure_current(); ivd = itd[1] if isinstance(itd, (list, tuple)) and len(itd) > 1 else float(itd)
                except Exception:
                    ivd = float('nan')
                if timeseries_out is not None:
                    v_ts, i_ts, t_ts = timeseries_out
                    v_ts.append(float(read_voltage)); i_ts.append(ivd); t_ts.append(time.perf_counter() - t_ref)
                if return_raw:
                    f_v.append(float(read_voltage)); f_i.append(ivd); f_t.append(time.perf_counter() - t_ref); f_phase.append(-1)
                # Gap sampling
                if inter_pulse_gap_s and inter_pulse_gap_s > 0:
                    t_gap2 = time.perf_counter()
                    while (time.perf_counter() - t_gap2) < float(inter_pulse_gap_s):
                        if should_stop and should_stop(): break
                        try:
                            itgd = keithley.measure_current(); ivgd = itgd[1] if isinstance(itgd, (list, tuple)) and len(itgd) > 1 else float(itgd)
                        except Exception:
                            ivgd = float('nan')
                        if timeseries_out is not None:
                            v_ts, i_ts, t_ts = timeseries_out
                            v_ts.append(float(read_voltage)); i_ts.append(ivgd); t_ts.append(time.perf_counter() - t_ref)
                        if return_raw:
                            f_v.append(float(read_voltage)); f_i.append(ivgd); f_t.append(time.perf_counter() - t_ref); f_phase.append(-1)
                        time.sleep(0.0001)
        try:
            keithley.set_voltage(0.0, float(icc)); keithley.enable_output(False)
        except Exception:
            pass
        if return_raw:
            # Overload return with raw stream: phase encoded in f_phase (+1 set, -1 reset)
            return f_phase, f_i, f_t, f_v  # type: ignore
        return idx, I_im, I_post, ratio

    def run_frequency_response(
        self,
        *,
        keithley,
        pulse_voltage: float,
        pulse_width_ms: float,
        freq_list_hz: Iterable[float],
        pulses_per_freq: int = 10,
        vbase: float = 0.2,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
        timeseries_out: Optional[Tuple[List[float], List[float], List[float]]] = None,
        return_raw: bool = True,
    ) -> Tuple[List[float], List[float]]:
        """Frequency response via pulse train.

        When return_raw is False (default): returns (freq_list_hz, I_avg_list) like before.
        When return_raw is True: returns (freq_per_sample, current_per_sample, elapsed_time_s, v_per_sample).
        """
        # Enforce minimum pulse width
        try: min_ms = float(self.smu_limits.get_limits(smu_type).get("min_pulse_width_ms", 1.0))
        except Exception: min_ms = 1.0
        w_s = max(min_ms, float(pulse_width_ms)) / 1000.0
        # Raw collectors (used when return_raw=True)
        f_out: List[float] = []
        i_out: List[float] = []
        t_out: List[float] = []
        v_out: List[float] = []
        # Averaged per-frequency outputs (compat mode)
        freqs: List[float] = []
        I_avg: List[float] = []
        try: keithley.enable_output(True)
        except Exception: pass
        # Reference time for optional timeseries capture
        t_ref = time.perf_counter()
        for f in list(freq_list_hz or []):
            if should_stop and should_stop(): break
            f = max(0.1, float(f)); period = max(w_s * 1.1, 1.0 / f)
            reads: List[float] = []
            for _ in range(max(1, int(pulses_per_freq))):
                try: keithley.set_voltage(float(pulse_voltage), float(icc))
                except Exception: pass
                # Hold the pulse for w_s (no sampling during pulse)
                t0 = time.perf_counter()
                while (time.perf_counter() - t0) < w_s:
                    if should_stop and should_stop(): break
                    time.sleep(0.001)
                try: keithley.set_voltage(float(vbase), float(icc))
                except Exception: pass
                # Brief settle and take an immediate read
                time.sleep(0.002)
                try:
                    it = keithley.measure_current(); iv = it[1] if isinstance(it, (list, tuple)) and len(it) > 1 else float(it)
                except Exception:
                    iv = float('nan')
                # record immediate read for both raw and average
                if return_raw:
                    i_out.append(iv); f_out.append(f); t_out.append(time.perf_counter() - t_ref); v_out.append(float(vbase))
                reads.append(iv)
                # Sample as fast as possible during remaining gap; do not extend timing
                t_gap = max(0.0, period - w_s)
                t1 = time.perf_counter()
                while (time.perf_counter() - t1) < t_gap:
                    if should_stop and should_stop(): break
                    try:
                        itgap = keithley.measure_current(); ivgap = itgap[1] if isinstance(itgap, (list, tuple)) and len(itgap) > 1 else float(itgap)
                    except Exception:
                        ivgap = float('nan')
                    # Always append raw sample when requested
                    if return_raw:
                        i_out.append(ivgap); f_out.append(f); t_out.append(time.perf_counter() - t_ref); v_out.append(float(vbase))
                    time.sleep(0.0001)
            # Per-frequency average (compat)
            try:
                avg = float(sum(reads) / max(1, len(reads)))
            except Exception:
                avg = float('nan')
            freqs.append(f); I_avg.append(avg)
        try: keithley.set_voltage(0.0, float(icc)); keithley.enable_output(False)
        except Exception: pass
        if return_raw:
            return f_out, i_out, t_out, v_out
        return freqs, I_avg

    def run_bias_dependent_decay(
        self,
        *,
        keithley,
        pulse_voltage: float,
        pulse_width_ms: float,
        read_voltage_list: Iterable[float],
        capture_time_s: float = 1.0,
        sample_dt_s: float = 0.001,
        icc: float = 1e-4,
        smu_type: str = "Keithley 2401",
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Repeat transient decay for each read voltage; concatenate results.

        Returns concatenated (t_all, i_all, vread_all) where vread encodes the read voltage per point.
        """
        t_all: List[float] = []; i_all: List[float] = []; v_all: List[float] = []
        for rv in list(read_voltage_list or []):
            if should_stop and should_stop(): break
            t_arr, i_arr, v_arr = self.run_transient_decay(
                keithley=keithley,
                pulse_voltage=pulse_voltage,
                pulse_width_ms=pulse_width_ms,
                read_voltage=float(rv),
                capture_time_s=capture_time_s,
                sample_dt_s=sample_dt_s,
                icc=icc,
                smu_type=smu_type,
                should_stop=should_stop,
                on_point=None,
            )
            # shift time to be contiguous
            t_offset = (t_all[-1] if t_all else 0.0)
            for k in range(len(t_arr)):
                t_all.append(t_offset + float(t_arr[k]))
                i_all.append(float(i_arr[k]))
                v_all.append(float(rv))
            # add small gap
            if t_all:
                t_all[-1] = t_all[-1] + 0.01
        return t_all, i_all, v_all

    def run_noise_capture(
        self,
        *,
        keithley,
        read_voltage: float = 0.1,
        capture_time_s: float = 5.0,
        sample_dt_s: float = 0.001,
        icc: float = 1e-4,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Alias for DC capture at low bias to observe RTN/noise; returns (t, i, v)."""
        return self.run_dc_capture(
            keithley=keithley,
            voltage_v=float(read_voltage),
            capture_time_s=float(capture_time_s),
            sample_dt_s=float(sample_dt_s),
            icc=float(icc),
            on_point=on_point,
            should_stop=should_stop,
        )

    def update_smu_limits(self, smu_type: str, **kwargs):
        """
        Update timing limits for a specific SMU type.

        Examples:
        service.update_smu_limits("Keithley 2401", min_pulse_width_ms=0.5)
        service.update_smu_limits("Keithley 4200A_pmu", min_pulse_width_ms=0.01, rise_fall_time_us=0.5)
        """
        self.smu_limits.update_limits(smu_type, **kwargs)

    def get_smu_limits(self, smu_type: str) -> dict:
        """
        Get timing limits for a specific SMU type.
        """
        return self.smu_limits.get_limits(smu_type)

    def get_smu_defaults(self, smu_type: str) -> dict:
        """Get per-model sensible defaults (used for GUI seeding)."""
        return self.smu_limits.get_defaults(smu_type)

    # --------------------------
    # PMU-dedicated routines
    # --------------------------
    def _validate_pmu_connected(self, pmu) -> None:
        """Ensure a PMU controller is present and connected."""
        try:
            is_ok = pmu is not None and getattr(pmu, "is_connected", lambda: False)()
        except Exception:
            is_ok = False
        if not is_ok:
            raise RuntimeError("PMU is not connected. Connect a 4200A PMU before running PMU tests.")

    def _validate_pmu_timing(self,
                              *,
                              smu_type: str,
                              width_s: float,
                              period_s: float,
                              rise_s: float,
                              fall_s: float,
                              amplitude_v: float,
                              v_range: Optional[Tuple[float, float]] = None) -> None:
        """Check timing and amplitude against configured SMU limits for 4200A PMU."""
        limits = self.smu_limits.get_limits(smu_type)
        min_width_ms = limits.get("min_pulse_width_ms", 0.00005)
        min_rise_us = limits.get("rise_fall_time_us", 1)
        vmin, vmax = limits.get("voltage_range_V", (-10, 10))
        if v_range is not None and len(v_range) == 2:
            vmin, vmax = v_range

        if (width_s * 1000.0) < float(min_width_ms):
            raise ValueError(f"Pulse width {width_s*1e3:.3f} ms below minimum for {smu_type} ({min_width_ms} ms)")
        if amplitude_v < float(vmin) or amplitude_v > float(vmax):
            raise ValueError(f"Pulse amplitude {amplitude_v} V exceeds range {vmin}..{vmax} V for {smu_type}")
        # Earlier working behavior: period must exceed width only
        if period_s <= width_s:
            raise ValueError("Period must be greater than pulse width")
        
        if (rise_s * 1e6) < float(min_rise_us) or (fall_s * 1e6) < float(min_rise_us):
            print((rise_s * 1e6), min_rise_us)
            raise ValueError(f"Rise/Fall times must be >= {min_rise_us} us for {smu_type}")
        

    def run_pmu_pulse_train(
        self,
        *,
        pmu,
        amplitude_v: float,
        base_v: float,
        width_s: float,
        period_s: float,
        num_pulses: int,
        smu_type: str = "Keithley 4200A_pmu",
        psu=None,
        led: bool = False,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Run a fixed-amplitude pulse train on the PMU and return (V, I, t)."""
        self._validate_pmu_connected(pmu)
        self._validate_pmu_timing(smu_type=smu_type, width_s=width_s, period_s=period_s,
                                  rise_s=1e-7, fall_s=1e-7, amplitude_v=amplitude_v, v_range=None)

        try:
            if psu is not None and led:
                psu.led_on_380(1.0)
        except Exception:
            pass

        v_arr: List[float] = []
        i_arr: List[float] = []
        t_arr: List[float] = []
        
        try:
            result = pmu.run_fixed_amplitude_pulses(amplitude_v, base_v, int(num_pulses),
                                                    width_s, period_s, as_dataframe=False)
            v_arr, i_arr, t_arr = list(result[0]), list(result[1]), list(result[2])
            if on_point:
                for idx in range(len(v_arr)):
                    if should_stop and should_stop():
                        break
                    try:
                        on_point(float(v_arr[idx]), float(i_arr[idx]), float(t_arr[idx]))
                    except Exception:
                        pass
        finally:
            try:
                if psu is not None and led:
                    psu.led_off_380()
            except Exception:
                pass

        return v_arr, i_arr, t_arr

    def run_pmu_pulse_pattern(
        self,
        *,
        pmu,
        pattern: str,
        amplitude_v: float,
        base_v: float,
        width_s: float,
        period_s: float,
        smu_type: str = "Keithley 4200A_pmu",
        psu=None,
        led_power: float = 1.0,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Run a bitstring pattern like '1011' and return concatenated (V, I, t)."""
        self._validate_pmu_connected(pmu)
        self._validate_pmu_timing(smu_type=smu_type, width_s=width_s, period_s=period_s,
                                  rise_s=1e-7, fall_s=1e-7, amplitude_v=amplitude_v, v_range=None)

        v_all: List[float] = []
        i_all: List[float] = []
        t_all: List[float] = []
        base_time_offset = 0.0

        for bit in str(pattern):
            if should_stop and should_stop():
                break
            try:
                if psu is not None:
                    if bit == '1':
                        psu.led_on_380(led_power)
                    else:
                        psu.led_off_380()
            except Exception:
                pass

            result = pmu.run_fixed_amplitude_pulses(
                amplitude_v if bit == '1' else base_v,
                base_v,
                1,
                width_s,
                period_s,
                as_dataframe=False,
            )
            v, i, t = result[0], result[1], result[2]
            if t:
                t0 = t[0]
                t_shifted = [base_time_offset + (tv - t0) for tv in t]
                base_time_offset = t_shifted[-1] + period_s
            else:
                t_shifted = []
            v_all.extend(v); i_all.extend(i); t_all.extend(t_shifted)
            if on_point:
                for k in range(len(v)):
                    try:
                        on_point(float(v[k]), float(i[k]), float(t_shifted[k]))
                    except Exception:
                        pass
        try:
            if psu is not None:
                psu.led_off_380()
        except Exception:
            pass
        return v_all, i_all, t_all

    def run_pmu_transient_switching(
        self,
        *,
        pmu,
        amplitude_v: float,
        base_v: float,
        width_s: float,
        period_s: float,
        smu_type: str = "Keithley 4200A_pmu",
    ) -> Tuple[List[float], List[float], List[float]]:
        """Acquire a single transient (one pulse) waveform."""
        self._validate_pmu_connected(pmu)
        self._validate_pmu_timing(smu_type=smu_type, width_s=width_s, period_s=period_s,
                                  rise_s=1e-7, fall_s=1e-7, amplitude_v=amplitude_v, v_range=None)
        result = pmu.run_fixed_amplitude_pulses(amplitude_v, base_v, 1, width_s, period_s,
                                                as_dataframe=False)
        return list(result[0]), list(result[1]), list(result[2])

    def run_pmu_dc_measure(
        self,
        *,
        pmu,
        voltage_v: float,
        capture_time_s: float,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Hold a constant voltage using a single long pulse and capture I(t).

        Implemented by issuing a single pulse with width=capture_time_s and period slightly larger.
        Returns (V, I, t) arrays from the PMU.
        """
        self._validate_pmu_connected(pmu)
        width_s = float(capture_time_s)
        period_s = float(capture_time_s) * 1.2 if float(capture_time_s) > 0 else 2e-4
        # Timing guard using existing PMU limits
        self._validate_pmu_timing(smu_type="Keithley 4200A_pmu", width_s=width_s, period_s=period_s,
                                  rise_s=1e-7, fall_s=1e-7, amplitude_v=voltage_v, v_range=None)
        result = pmu.run_fixed_amplitude_pulses(voltage_v, 0.0, 1, width_s, period_s, as_dataframe=False)
        return list(result[0]), list(result[1]), list(result[2])

    def run_pmu_endurance(
        self,
        *,
        pmu,
        set_voltage: float,
        reset_voltage: float,
        pulse_width_s: float,
        num_cycles: int,
        period_s: float,
        smu_type: str = "Keithley 4200A_pmu",
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Alternate set/reset PMU pulses; report the readback current near pulse center."""
        self._validate_pmu_connected(pmu)
        v_out: List[float] = []
        i_out: List[float] = []
        t_out: List[float] = []
        for _ in range(int(num_cycles)):
            for level in (set_voltage, reset_voltage):
                self._validate_pmu_timing(smu_type=smu_type, width_s=pulse_width_s, period_s=period_s,
                                          rise_s=1e-7, fall_s=1e-7, amplitude_v=level, v_range=None)
                result = pmu.run_fixed_amplitude_pulses(level, 0.0, 1, pulse_width_s, period_s,
                                                        as_dataframe=False)
                v, i, t = result[0], result[1], result[2]
                if t:
                    mid_idx = max(0, min(len(t) - 1, len(t) // 2))
                    v_mid = float(v[mid_idx]); i_mid = float(i[mid_idx]); t_mid = float(t[mid_idx] if not t_out else t_out[-1] + period_s)
                    v_out.append(v_mid); i_out.append(i_mid); t_out.append(t_mid)
                    if on_point:
                        try:
                            on_point(v_mid, i_mid, t_mid)
                        except Exception:
                            pass
        return v_out, i_out, t_out

    def run_pmu_retention(
        self,
        *,
        pmu,
        keithley,
        set_voltage: float,
        set_width_s: float,
        read_voltage: float,
        repeat_delay_s: float,
        number: int,
        smu_type: str = "Keithley 4200A_pmu",
        icc: float = 1e-4,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """PMU-based set pulse then standard SMU-based retention sampling."""
        self._validate_pmu_connected(pmu)
        self._validate_pmu_timing(smu_type=smu_type, width_s=set_width_s, period_s=max(2*set_width_s, 1e-5),
                                  rise_s=1e-7, fall_s=1e-7, amplitude_v=set_voltage, v_range=None)
        pmu.run_fixed_amplitude_pulses(set_voltage, 0.0, 1, set_width_s, max(2*set_width_s, 1e-5), as_dataframe=False)
        return self.run_retention(
            keithley=keithley,
            set_voltage=0.0,
            set_time_s=0.0,
            read_voltage=read_voltage,
            repeat_delay_s=repeat_delay_s,
            number=number,
            icc=icc,
            smu_type="Keithley 2400",
            on_point=on_point,
        )

    def run_pmu_ispp(
        self,
        *,
        pmu,
        start_v: float,
        stop_v: float,
        step_v: float,
        base_v: float,
        width_s: float,
        period_s: float,
        target_current_a: float,
        smu_type: str = "Keithley 4200A_pmu",
    ) -> Tuple[List[float], List[float], List[float]]:
        """Incremental Step Pulse Programming until reaching target current."""
        self._validate_pmu_connected(pmu)
        direction = 1.0 if stop_v >= start_v else -1.0
        v_all: List[float] = []
        i_all: List[float] = []
        t_all: List[float] = []
        current_amp = start_v
        while (direction > 0 and current_amp <= stop_v) or (direction < 0 and current_amp >= stop_v):
            self._validate_pmu_timing(smu_type=smu_type, width_s=width_s, period_s=period_s,
                                      rise_s=1e-7, fall_s=1e-7, amplitude_v=current_amp, v_range=None)
            result = pmu.run_fixed_amplitude_pulses(current_amp, base_v, 1, width_s, period_s,
                                                    as_dataframe=False)
            v, i, t = result[0], result[1], result[2]
            v_all.extend(v); i_all.extend(i); t_all.extend(t)
            try:
                mean_i = sum(i) / max(1, len(i))
            except Exception:
                mean_i = 0.0
            if abs(mean_i) >= abs(target_current_a):
                break
            current_amp += step_v * direction
        return v_all, i_all, t_all
    
    def run_pmu_amplitude_sweep(
        self,
        *,
        pmu,
        start_v: float,
        stop_v: float,
        step_v: float,
        base_v: float,
        width_s: float,
        period_s: float,
        smu_type: str = "Keithley 4200A_pmu",
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Run a linear amplitude sweep on the PMU and return concatenated data."""
        self._validate_pmu_connected(pmu)
        for amp in (start_v, stop_v):
            self._validate_pmu_timing(smu_type=smu_type, width_s=width_s, period_s=period_s,
                                      rise_s=1e-7, fall_s=1e-7, amplitude_v=amp, v_range=None)
        result = pmu.run_amplitude_sweep(start_v, stop_v, step_v, base_v, width_s, period_s,
                                         as_dataframe=False)
        v, i, t = result[0], result[1], result[2]
        if on_point:
            for k in range(len(v)):
                if should_stop and should_stop():
                    break
                try:
                    on_point(float(v[k]), float(i[k]), float(t[k]))
                except Exception:
                    pass
        return list(v), list(i), list(t)

    def run_pmu_width_sweep(
        self,
        *,
        pmu,
        amplitude_v: float,
        base_v: float,
        widths_s: Iterable[float],
        period_s: float,
        smu_type: str = "Keithley 4200A_pmu",
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Sweep pulse width, concatenating the returned traces."""
        self._validate_pmu_connected(pmu)
        v_all: List[float] = []
        i_all: List[float] = []
        t_all: List[float] = []
        t_offset = 0.0
        for w in widths_s:
            if should_stop and should_stop():
                break
            self._validate_pmu_timing(smu_type=smu_type, width_s=float(w), period_s=period_s,
                                      rise_s=1e-7, fall_s=1e-7, amplitude_v=amplitude_v, v_range=None)
            result = pmu.run_fixed_amplitude_pulses(amplitude_v, base_v, 1, float(w), period_s,
                                                    as_dataframe=False)
            v, i, t = result[0], result[1], result[2]
            if t:
                t0 = t[0]
                t = [t_offset + (tv - t0) for tv in t]
                t_offset = t[-1] + period_s
            v_all.extend(v); i_all.extend(i); t_all.extend(t)
            if on_point:
                for k in range(len(v)):
                    try:
                        on_point(float(v[k]), float(i[k]), float(t[k]))
                    except Exception:
                        pass
        return v_all, i_all, t_all

    # --------------------------
    # Combined PMU + Generator routines
    # --------------------------
    def run_laser_decay(
        self,
        *,
        keithley,
        gen,
        bias_v: float = 0.2,
        capture_time_s: float = 0.02,
        sample_dt_s: float = 0.001,
        prep_delay_s: float = 0.01,
        trig_mode: str = "BUS",
    ) -> Tuple[List[float], List[float]]:
        """Apply a generator pulse and measure fast decay current at a DC bias using the SMU/PMU.

        - keithley: device with set_voltage/enable_output/measure_current
        - gen: Siglent generator instance (already configured); will be triggered via software when trig_mode='BUS'
        - bias_v: DC bias voltage to hold during measurement
        - capture_time_s: total time to sample after trigger
        - sample_dt_s: sampling interval for SMU current reads
        - prep_delay_s: delay after bias set before triggering
        - trig_mode: 'BUS' (software trigger) or 'EXT' (external cabling required; no software trigger)
        """
        v_target = float(bias_v)
        try:
            keithley.enable_output(True)
            keithley.set_voltage(v_target, 1e-3)
        except Exception:
            pass

        if prep_delay_s and prep_delay_s > 0:
            time.sleep(prep_delay_s)

        try:
            if gen is not None and hasattr(gen, 'is_connected') and gen.is_connected():
                if str(trig_mode).upper() == 'BUS':
                    gen.trigger_now(1)
        except Exception:
            pass

        t0 = time.time()
        t_arr: List[float] = []
        i_arr: List[float] = []
        while (time.time() - t0) < float(capture_time_s):
            try:
                i_val = keithley.measure_current()
                i_val = i_val[1] if isinstance(i_val, (list, tuple)) and len(i_val) > 1 else float(i_val)
            except Exception:
                i_val = float('nan')
            t_arr.append(time.time() - t0)
            i_arr.append(i_val)
            if sample_dt_s and sample_dt_s > 0:
                time.sleep(max(0.0, float(sample_dt_s)))

        try:
            keithley.set_voltage(0.0, 1e-3)
            keithley.enable_output(False)
        except Exception:
            pass

        return t_arr, i_arr

    def run_moku_decay(
        self,
        *,
        keithley,
        laser,  # LaserFunctionGenerator
        bias_v: float = 0.2,
        capture_time_s: float = 0.02,
        sample_dt_s: float = 0.001,
        prep_delay_s: float = 0.01,
        high_v: float = 1.0,
        width_s: float = 100e-9,
        period_s: float = 200e-9,
        edge_s: float = 16e-9,
        pulses: int = 1,
        continuous_duration_s: float = 0.0,
    ) -> Tuple[List[float], List[float]]:
        """
        Apply a Moku laser pulse (single/burst/continuous) while sampling current at a DC bias.
        Returns (t_arr, i_arr).
        """
        t_arr: List[float] = []
        i_arr: List[float] = []

        # Bias and settle
        try:
            keithley.enable_output(True)
            keithley.set_voltage(float(bias_v), 1e-3)
        except Exception:
            pass

        if prep_delay_s and prep_delay_s > 0:
            time.sleep(prep_delay_s)

        # Fire laser according to mode in background to avoid blocking sampling
        import threading
        def _fire():
            try:
                if pulses and pulses > 1:
                    laser.run_burst(high_v, width_s, period_s, edge_s, count=int(pulses))
                elif continuous_duration_s and continuous_duration_s > 0:
                    laser.start_continuous(high_v, width_s, period_s, edge_s)
                    time.sleep(float(continuous_duration_s))
                    laser.stop_output()
                else:
                    laser.send_single_pulse(high_v, width_s, edge_s, period_s)
            except Exception:
                pass

        th = threading.Thread(target=_fire, daemon=True)
        th.start()

        t0 = time.time()
        while (time.time() - t0) < float(capture_time_s):
            try:
                i_val = keithley.measure_current()
                i_val = i_val[1] if isinstance(i_val, (list, tuple)) and len(i_val) > 1 else float(i_val)
            except Exception:
                i_val = float('nan')
            t_arr.append(time.time() - t0)
            i_arr.append(i_val)
            if sample_dt_s and sample_dt_s > 0:
                time.sleep(max(0.0, float(sample_dt_s)))

        try:
            keithley.set_voltage(0.0, 1e-3)
            keithley.enable_output(False)
        except Exception:
            pass

        return t_arr, i_arr

    def run_laser_4bit_sequences(
        self,
        *,
        keithley,
        gen,
        bit_period_s: float,
        relax_between_bits_s: float,
        relax_between_patterns_s: float,
        repeats: int = 1,
        trig_mode: str = "BUS",
        bias_v: float = 0.2,
        sample_dt_s: float = 0.001,
    ) -> Tuple[List[float], List[float], List[str]]:
        """Run through all 4-bit combinations (0000..1111) with relax times, capture current continuously.

        - For each pattern: for each bit, we either trigger (bit '1') or wait (bit '0') for one bit period.
        - relax_between_bits_s: extra delay after each bit window
        - relax_between_patterns_s: extra delay between patterns
        - returns (t_arr, i_arr, pattern_log) where pattern_log records the active pattern segments
        """
        patterns = [f"{n:04b}" for n in range(16)]
        t_arr: List[float] = []
        i_arr: List[float] = []
        log: List[str] = []

        try:
            keithley.enable_output(True)
            keithley.set_voltage(float(bias_v), 1e-3)
        except Exception:
            pass

        t0 = time.time()
        def sample_once():
            try:
                i_val = keithley.measure_current()
                return i_val[1] if isinstance(i_val, (list, tuple)) and len(i_val) > 1 else float(i_val)
            except Exception:
                return float('nan')

        for _ in range(max(1, int(repeats))):
            for pat in patterns:
                for b in pat:
                    if b == '1' and gen is not None and hasattr(gen, 'is_connected') and gen.is_connected():
                        if str(trig_mode).upper() == 'BUS':
                            try: gen.trigger_now(1)
                            except Exception: pass
                    t_bit_start = time.time()
                    while (time.time() - t_bit_start) < float(bit_period_s):
                        t_arr.append(time.time() - t0)
                        i_arr.append(sample_once())
                        if sample_dt_s and sample_dt_s > 0:
                            time.sleep(max(0.0, float(sample_dt_s)))
                    if relax_between_bits_s and relax_between_bits_s > 0:
                        t_relax_start = time.time()
                        while (time.time() - t_relax_start) < float(relax_between_bits_s):
                            t_arr.append(time.time() - t0)
                            i_arr.append(sample_once())
                            if sample_dt_s and sample_dt_s > 0:
                                time.sleep(max(0.0, float(sample_dt_s)))
                log.append(pat)
                if relax_between_patterns_s and relax_between_patterns_s > 0:
                    t_relax2 = time.time()
                    while (time.time() - t_relax2) < float(relax_between_patterns_s):
                        t_arr.append(time.time() - t0)
                        i_arr.append(sample_once())
                        if sample_dt_s and sample_dt_s > 0:
                            time.sleep(max(0.0, float(sample_dt_s)))

        try:
            keithley.set_voltage(0.0, 1e-3)
            keithley.enable_output(False)
        except Exception:
            pass

        return t_arr, i_arr, log


