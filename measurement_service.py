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
                "compliance_resolution": 1e-6
            },
            "Keithley 2401": {
                "min_timing_us": 250,
                "max_update_rate": 2000,
                "rise_fall_time_us": 30,
                "min_pulse_width_ms": 1.0,
                "voltage_range_V": (-20, 20),
                "current_range_A": (-1, 1),
                "compliance_resolution": 1e-6
            },
            "Keithley 4200A_smu": {
                "min_timing_us": 100,
                "max_update_rate": 5000,
                "rise_fall_time_us": 20,
                "min_pulse_width_ms": 0.5,
                "voltage_range_V": (-210, 210),
                "current_range_A": (-1, 1),
                "compliance_resolution": 1e-9
            },
            "Keithley 4200A_pmu": {
                "min_timing_us": 10,
                "max_update_rate": 10000,
                "rise_fall_time_us": 1,
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
        def travel_distance(v_start: float, v_stop: float, kind: str) -> float:
            if kind == "PS":
                return abs(v_stop - v_start) + abs(v_start - v_stop)
            if kind == "NS":
                return abs(-v_stop - v_start) + abs(v_start - (-v_stop))
            # FS
            return abs(v_stop - v_start) + abs((-v_stop) - v_stop) + abs(v_start - (-v_stop))

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
                dist = travel_distance(start_v, stop_v, sweep_type)
                effective_step_v = max(1e-9, dist / steps_float)
            else:
                effective_step_v = step_v

        step = effective_step_v if effective_step_v is not None else step_v

        if sweep_type == "NS":
            return (
                self._frange(start_v, -stop_v, -abs(step))
                + self._frange(-stop_v, start_v, abs(step))
            )
        if sweep_type == "PS":
            return (
                self._frange(start_v, stop_v, abs(step))
                + self._frange(stop_v, start_v, -abs(step))
            )
        # Default: Full sweep (FS)
        return (
            self._frange(start_v, stop_v, abs(step))
            + self._frange(stop_v, -stop_v, -abs(step))
            + self._frange(-stop_v, start_v, abs(step))
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
        - If voltage_range is None, it will be computed from (start_v, stop_v, step_v, sweep_type, mode).
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

        start_time = time.time()

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

        start_t = time.time()

        try:
            keithley.enable_output(True)
        except Exception:
            pass

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
            keithley.set_voltage(0, icc)
            keithley.enable_output(False)
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
            keithley.enable_output(True)
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
            t_now = time.time() - start_t
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
            t_now = time.time() - start_t
            v_arr.append(read_voltage); c_arr.append(i_reset_val); t_arr.append(t_now)
            if on_point:
                try: on_point(read_voltage, i_reset_val, t_now)
                except Exception: pass

            if inter_cycle_delay_s:
                time.sleep(max(0.0, float(inter_cycle_delay_s)))

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

        start_time = time.time()

        try:
            keithley.enable_output(True)
            keithley.set_voltage(0, icc)  # Start at 0V
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

            # Apply pulse
            try:
                keithley.set_voltage(pulse_voltage, icc)
            except Exception:
                pass

            pulse_start = time.time()
            pulse_width_s = pulse_width_ms / 1000.0

            # Wait for pulse duration
            while (time.time() - pulse_start) < pulse_width_s:
                if should_stop and should_stop():
                    break
                time.sleep(0.001)  # Small sleep to avoid busy waiting

            if should_stop and should_stop():
                break

            # Return to read voltage and measure
            try:
                keithley.set_voltage(read_voltage, icc)
                time.sleep(0.002)  # Brief settling time
                current_tuple = keithley.measure_current()
                current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
            except Exception:
                current = float('nan')

            t_now = time.time() - start_time

            # Record measurement
            v_arr.append(read_voltage)
            c_arr.append(current)
            t_arr.append(t_now)

            if on_point:
                try:
                    on_point(read_voltage, current, t_now)
                except Exception:
                    pass

            # Inter-pulse delay
            if inter_pulse_delay_s > 0:
                time.sleep(max(0.0, float(inter_pulse_delay_s)))

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


