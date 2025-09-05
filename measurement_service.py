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


