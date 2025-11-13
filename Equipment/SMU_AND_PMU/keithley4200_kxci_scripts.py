"""KXCI-based testing scripts for Keithley 4200A-SCS.

Purpose:
--------
This module provides a unified interface for running memristor device tests on the
Keithley 4200A-SCS using KXCI (Keithley eXternal Control Interface). It wraps
existing C modules (pmu_retention_dual_channel, readtrain_dual_channel) into
test methods that match the interface of keithley2450_tsp_scripts.py.

The module enables:
- Direct script wrappers: Tests that map to single C module calls
- Multi-script composition: Tests that call C modules multiple times with different parameters
- Data format normalization: Output matches 2450 format for GUI compatibility

Usage:
------
    from keithley4200_kxci_scripts import Keithley4200_KXCI_Scripts
    
    scripts = Keithley4200_KXCI_Scripts(gpib_address="GPIB0::17::INSTR")
    results = scripts.pulse_read_repeat(
        pulse_voltage=1.5,
        pulse_width=1e-3,  # 1ms in seconds
        read_voltage=0.2,
        delay_between=10e-3,  # 10ms in seconds
        num_cycles=10,
        clim=100e-6
    )
    
    # Results format matches 2450:
    # {
    #     'timestamps': List[float],
    #     'voltages': List[float],
    #     'currents': List[float],
    #     'resistances': List[float]
    # }

See Also:
---------
- keithley2450_tsp_scripts.py: Similar interface for Keithley 2450
- run_pmu_retention.py: Original retention measurement script
- run_readtrain_dual_channel.py: Original readtrain script
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ============================================================================
# KXCI Client and Helper Functions
# ============================================================================

class KXCIClient:
    """Minimal KXCI helper for sending EX/GP commands over GPIB."""

    def __init__(self, gpib_address: str, timeout: float) -> None:
        self.gpib_address = gpib_address
        self.timeout_ms = int(timeout * 1000)
        self.rm = None
        self.inst = None
        self._ul_mode_active = False

    def connect(self) -> bool:
        try:
            import pyvisa
        except ImportError as exc:  # noqa: F401
            raise RuntimeError("pyvisa is required to communicate with the instrument") from exc

        try:
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(self.gpib_address)
            self.inst.timeout = self.timeout_ms
            self.inst.write_termination = "\n"
            self.inst.read_termination = "\n"
            idn = self.inst.query("*IDN?").strip()
            print(f"✓ Connected to: {idn}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Connection failed: {exc}")
            return False

    def disconnect(self) -> None:
        try:
            if self._ul_mode_active:
                self._exit_ul_mode()
            if self.inst is not None:
                self.inst.close()
            if self.rm is not None:
                self.rm.close()
        finally:
            self.inst = None
            self.rm = None
            self._ul_mode_active = False

    def _enter_ul_mode(self) -> bool:
        if self.inst is None:
            return False
        self.inst.write("UL")
        time.sleep(0.03)
        self._ul_mode_active = True
        return True

    def _exit_ul_mode(self) -> bool:
        if self.inst is None or not self._ul_mode_active:
            self._ul_mode_active = False
            return True
        self.inst.write("DE")
        time.sleep(0.03)
        self._ul_mode_active = False
        return True

    def _execute_ex_command(self, command: str) -> tuple[Optional[int], Optional[str]]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")

        try:
            self.inst.write(command)
            time.sleep(0.03)
            time.sleep(2.0)

            response = self._safe_read()
            return self._parse_return_value(response), None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def _safe_read(self) -> str:
        if self.inst is None:
            return ""
        try:
            return self.inst.read()
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _parse_return_value(response: str) -> Optional[int]:
        if not response:
            return None
        match = re.search(r"RETURN VALUE\s*=\s*(-?\d+)", response, re.IGNORECASE)
        if match:
            return int(match.group(1))
        try:
            return int(response.strip())
        except ValueError:
            return None

    def _query_gp(self, param_position: int, num_values: int) -> List[float]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")

        command = f"GP {param_position} {num_values}"
        self.inst.write(command)
        time.sleep(0.03)
        raw = self._safe_read()
        return self._parse_gp_response(raw)

    @staticmethod
    def _parse_gp_response(response: str) -> List[float]:
        response = response.strip()
        if "=" in response and "PARAM VALUE" in response.upper():
            response = response.split("=", 1)[1].strip()

        separator = None
        for cand in (";", ","):
            if cand in response:
                separator = cand
                break

        values: List[float] = []
        if separator is None:
            if response:
                try:
                    values.append(float(response))
                except ValueError:
                    pass
            return values

        for part in response.split(separator):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(float(part))
            except ValueError:
                pass
        return values


def format_param(value: float | int | str) -> str:
    """Format a parameter exactly as expected by KXCI EX commands."""
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


# ============================================================================
# Retention Configuration
# ============================================================================

@dataclass
class RetentionConfig:
    """Configuration for PMU retention measurements."""
    rise_time: float = 1e-7
    reset_v: float = 1.0
    reset_width: float = 1e-6
    reset_delay: float = 5e-7
    meas_v: float = 0.3
    meas_width: float = 1e-6
    meas_delay: float = 2e-6
    set_width: float = 1e-6
    set_fall_time: float = 1e-7
    set_delay: float = 1e-6
    set_start_v: float = 0.3
    set_stop_v: float = 0.3
    steps: int = 0
    i_range: float = 1e-4
    max_points: int = 10000
    iteration: int = 2
    out1_name: str = "VF"
    out2_name: str = "T"
    out2_size: int = 200
    num_pulses: int = 50  # retention measurement pulses
    num_initial_meas_pulses: int = 2
    num_pulses_seq: int = 5  # number of pulses in sequence
    pulse_width: float = 1e-6
    pulse_v: float = 4.0
    pulse_rise_time: float = 1e-7
    pulse_fall_time: float = 1e-7
    pulse_delay: float = 1e-6
    clarius_debug: int = 1

    def total_probe_count(self) -> int:
        return self.num_initial_meas_pulses + self.num_pulses

    def validate(self) -> None:
        limits: Dict[str, tuple[float, float]] = {
            "rise_time": (2e-8, 1.0),
            "reset_v": (-20.0, 20.0),
            "reset_width": (2e-8, 1.0),
            "reset_delay": (2e-8, 1.0),
            "meas_v": (-20.0, 20.0),
            "meas_width": (2e-8, 1.0),
            "meas_delay": (2e-8, 1.0),
            "set_width": (2e-8, 1.0),
            "set_fall_time": (2e-8, 1.0),
            "set_delay": (2e-8, 1.0),
            "set_start_v": (-20.0, 20.0),
            "set_stop_v": (-20.0, 20.0),
            "i_range": (100e-9, 0.8),
            "max_points": (12, 30000),
        }

        for field_name, (lo, hi) in limits.items():
            value = getattr(self, field_name)
            if value < lo or value > hi:
                raise ValueError(f"{field_name}={value} outside [{lo}, {hi}]")

        if not (8 <= self.num_pulses <= 1000):
            raise ValueError("num_pulses must be within [8, 1000]")
        if not (1 <= self.num_initial_meas_pulses <= 100):
            raise ValueError("num_initial_meas_pulses must be within [1, 100]")
        if not (1 <= self.num_pulses_seq <= 100):
            raise ValueError("num_pulses_seq must be within [1, 100]")
        if not (2e-8 <= self.pulse_width <= 1.0):
            raise ValueError("pulse_width must be within [2e-8, 1.0]")
        if not (-20.0 <= self.pulse_v <= 20.0):
            raise ValueError("pulse_v must be within [-20.0, 20.0]")
        if not (2e-8 <= self.pulse_rise_time <= 1.0):
            raise ValueError("pulse_rise_time must be within [2e-8, 1.0]")
        if not (2e-8 <= self.pulse_fall_time <= 1.0):
            raise ValueError("pulse_fall_time must be within [2e-8, 1.0]")
        if not (2e-8 <= self.pulse_delay <= 1.0):
            raise ValueError("pulse_delay must be within [2e-8, 1.0]")
        if self.clarius_debug not in (0, 1):
            raise ValueError("clarius_debug must be 0 or 1")
        if self.out2_size < 1:
            raise ValueError("out2_size must be positive")
        if self.steps < 0:
            raise ValueError("steps must be >= 0")


def build_retention_ex_command(cfg: RetentionConfig) -> str:
    """Build EX command for pmu_retention_dual_channel."""
    total_probes = cfg.total_probe_count()
    common_size = total_probes

    params = [
        format_param(cfg.rise_time),
        format_param(cfg.reset_v),
        format_param(cfg.reset_width),
        format_param(cfg.reset_delay),
        format_param(cfg.meas_v),
        format_param(cfg.meas_width),
        format_param(cfg.meas_delay),
        format_param(cfg.set_width),
        format_param(cfg.set_fall_time),
        format_param(cfg.set_delay),
        format_param(cfg.set_start_v),
        format_param(cfg.set_stop_v),
        format_param(cfg.steps),
        format_param(cfg.i_range),
        format_param(cfg.max_points),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        format_param(cfg.iteration),
        "",
        format_param(common_size),
        cfg.out1_name,
        "",
        format_param(cfg.out2_size),
        cfg.out2_name,
        "",
        format_param(common_size),
        format_param(cfg.num_pulses),
        format_param(cfg.num_initial_meas_pulses),
        format_param(cfg.num_pulses_seq),
        format_param(cfg.pulse_width),
        format_param(cfg.pulse_v),
        format_param(cfg.pulse_rise_time),
        format_param(cfg.pulse_fall_time),
        format_param(cfg.pulse_delay),
        format_param(cfg.clarius_debug),
    ]

    return f"EX A_Retention pmu_retention_dual_channel({','.join(params)})"


def build_readtrain_ex_command(
    rise_time: float, reset_v: float, reset_width: float, reset_delay: float,
    meas_v: float, meas_width: float, meas_delay: float,
    set_width: float, set_fall_time: float, set_delay: float,
    set_start_v: float, set_stop_v: float, steps: int,
    i_range: float, max_points: int,
    set_r_size: int, reset_r_size: int, set_v_size: int, set_i_size: int,
    iteration: int, out1_size: int, out1_name: str,
    out2_size: int, out2_name: str,
    pulse_times_size: int, numb_meas_pulses: int, clarius_debug: int
) -> str:
    """Build EX command for readtrain_dual_channel."""
    params = [
        format_param(rise_time),
        format_param(reset_v),
        format_param(reset_width),
        format_param(reset_delay),
        format_param(meas_v),
        format_param(meas_width),
        format_param(meas_delay),
        format_param(set_width),
        format_param(set_fall_time),
        format_param(set_delay),
        format_param(set_start_v),
        format_param(set_stop_v),
        format_param(steps),
        format_param(i_range),
        format_param(max_points),
        "",
        format_param(set_r_size),
        "",
        format_param(reset_r_size),
        "",
        format_param(set_v_size),
        "",
        format_param(set_i_size),
        format_param(iteration),
        "",
        format_param(out1_size),
        out1_name,
        "",
        format_param(out2_size),
        out2_name,
        "",
        format_param(pulse_times_size),
        format_param(numb_meas_pulses),
        format_param(clarius_debug),
    ]

    return f"EX A_Read_Train readtrain_dual_channel({','.join(params)})"


def _compute_probe_times(cfg: RetentionConfig) -> List[float]:
    """Recreate the probe timing centres used in the C implementation."""
    ratio = 0.4
    ttime = 0.0
    centres: List[float] = []

    def add_measurement(start_time: float) -> None:
        centres.append(start_time + cfg.meas_width * (ratio + 0.9) / 2.0)

    # Initial delay and rise time
    ttime += cfg.reset_delay
    ttime += cfg.rise_time

    # Initial measurement pulses
    for _ in range(cfg.num_initial_meas_pulses):
        add_measurement(ttime)
        ttime += cfg.meas_width
        ttime += cfg.rise_time
        ttime += cfg.meas_delay
        ttime += cfg.rise_time

    # Small delay before pulse sequence
    ttime += cfg.rise_time

    # Pulse sequence: Multiple pulses in a row
    for _ in range(cfg.num_pulses_seq):
        ttime += cfg.pulse_rise_time
        ttime += cfg.pulse_width
        ttime += cfg.pulse_fall_time
        ttime += cfg.pulse_delay

    # Retention measurement pulses
    for _ in range(cfg.num_pulses):
        ttime += cfg.rise_time
        add_measurement(ttime)
        ttime += cfg.meas_width
        ttime += cfg.set_fall_time
        ttime += cfg.meas_delay

    return centres


# ============================================================================
# Main Scripts Class
# ============================================================================

class Keithley4200_KXCI_Scripts:
    """KXCI-based testing scripts for Keithley 4200A-SCS.
    
    This class provides a unified interface for running memristor device tests
    on the Keithley 4200A-SCS, matching the interface of keithley2450_tsp_scripts.py.
    """
    
    def __init__(self, gpib_address: str, timeout: float = 30.0):
        """
        Initialize with GPIB address.
        
        Args:
            gpib_address: VISA resource string (e.g., "GPIB0::17::INSTR")
            timeout: Communication timeout in seconds (default: 30.0)
        """
        self.gpib_address = gpib_address
        self.timeout = timeout
        self.start_time = time.time()
        self._controller: Optional[KXCIClient] = None
    
    def _get_timestamp(self) -> float:
        """Get timestamp relative to tester initialization."""
        return time.time() - self.start_time
    
    def _get_controller(self) -> KXCIClient:
        """Get or create KXCI controller."""
        if self._controller is None:
            self._controller = KXCIClient(self.gpib_address, self.timeout)
        return self._controller
    
    def _convert_ms_to_seconds(self, value_ms: float) -> float:
        """Convert milliseconds to seconds."""
        return value_ms / 1000.0
    
    def _convert_clim_to_i_range(self, clim: float) -> float:
        """Convert current limit to appropriate i_range for 4200.
        
        The 4200 uses i_range parameter. We'll use clim with some headroom.
        """
        # Use 1.2x headroom, but clamp to valid range [100e-9, 0.8]
        i_range = clim * 1.2
        return max(100e-9, min(0.8, i_range))
    
    def _ensure_minimum_delays(self, meas_delay: float, num_retention_pulses: int) -> float:
        """Ensure meas_delay is sufficient for C module rate calculation.
        
        The C module requires a minimum sampling rate of 200000 samples/second.
        For short total times, we need to ensure meas_delay is large enough
        to allow valid rate calculation. The error "100050 is too small <<200000"
        indicates the calculated rate is below the minimum.
        
        Args:
            meas_delay: Requested measurement delay (seconds)
            num_retention_pulses: Number of retention measurement pulses
        
        Returns:
            Adjusted meas_delay that ensures valid rate calculation
        """
        # The C module needs sufficient total time to calculate a valid rate
        # With 8 retention pulses, each pulse has: riseTime + measWidth + setFallTime + riseTime + measDelay
        # Minimum total time needed: ~50 microseconds per pulse minimum
        # For 8 pulses: ~400 microseconds minimum total time for retention section
        # To be safe, use at least 2 microseconds per pulse spacing
        min_delay_per_pulse = 2e-6  # 2 microseconds minimum per pulse
        
        # Calculate minimum delay needed
        min_delay = max(meas_delay, min_delay_per_pulse)
        
        # If we have many pulses, ensure total time is sufficient
        # The total time for retention pulses section needs to be long enough
        # for the rate calculation (minimum rate is 200000 samples/sec)
        if num_retention_pulses >= 8:
            # Ensure we have at least 2 microseconds spacing between pulses
            min_delay = max(min_delay, min_delay_per_pulse)
        
        return min_delay
    
    def _format_results(self, timestamps: List[float], voltages: List[float], 
                       currents: List[float], resistances: List[float],
                       **extras) -> Dict:
        """Format results into standardized dict with optional extra keys."""
        result = {
            'timestamps': timestamps,
            'voltages': voltages,
            'currents': currents,
            'resistances': resistances
        }
        result.update(extras)
        return result
    
    def _query_gp_data(self, controller: KXCIClient, param: int, count: int, 
                      name: str = "") -> List[float]:
        """Query GP parameter with retry logic."""
        for attempt in range(3):
            try:
                data = controller._query_gp(param, count)
                if data:
                    return data
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.5)
                else:
                    print(f"⚠️ Failed to query GP {param} ({name}): {e}")
        return []
    
    def _execute_retention(self, cfg: RetentionConfig) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Execute retention measurement and return normalized data.
        
        Returns:
            Tuple of (timestamps, voltages, currents, resistances)
        """
        command = build_retention_ex_command(cfg)
        total_probes = cfg.total_probe_count()
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            return_value, error = controller._execute_ex_command(command)
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            
            if return_value is not None and return_value < 0:
                raise RuntimeError(f"EX command returned error code: {return_value}")
            
            time.sleep(0.2)  # Allow data to be ready
            
            # Query data from GP parameters
            set_v = self._query_gp_data(controller, 20, total_probes, "setV")
            set_i = self._query_gp_data(controller, 22, total_probes, "setI")
            pulse_times = self._query_gp_data(controller, 30, total_probes, "PulseTimes")
            
            if not pulse_times:
                pulse_times = _compute_probe_times(cfg)
            
            if len(pulse_times) != total_probes:
                pulse_times = [float(i) for i in range(total_probes)]
            
            # Calculate resistances
            resistances: List[float] = []
            for voltage, current in zip(set_v, set_i):
                if abs(current) < 1e-12:
                    resistances.append(float("inf"))
                else:
                    resistances.append(voltage / current)
            
            # Ensure all lists are same length
            min_len = min(len(set_v), len(set_i), len(pulse_times), len(resistances))
            set_v = set_v[:min_len]
            set_i = set_i[:min_len]
            pulse_times = pulse_times[:min_len]
            resistances = resistances[:min_len]
            
            return pulse_times, set_v, set_i, resistances
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    def _execute_readtrain(self, numb_meas_pulses: int, meas_v: float, meas_width: float,
                          meas_delay: float, i_range: float, 
                          rise_time: float = 3e-8) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Execute readtrain measurement and return normalized data.
        
        Returns:
            Tuple of (timestamps, voltages, currents, resistances)
        """
        # Auto-calculate array sizes
        array_size = numb_meas_pulses + 2
        
        command = build_readtrain_ex_command(
            rise_time=rise_time,
            reset_v=0.0,
            reset_width=1e-6,
            reset_delay=1e-6,
            meas_v=meas_v,
            meas_width=meas_width,
            meas_delay=meas_delay,
            set_width=1e-6,
            set_fall_time=rise_time,
            set_delay=1e-6,
            set_start_v=0.0,
            set_stop_v=0.0,
            steps=1,
            i_range=i_range,
            max_points=10000,
            set_r_size=array_size,
            reset_r_size=array_size,
            set_v_size=array_size,
            set_i_size=array_size,
            iteration=1,
            out1_size=200,
            out1_name="VF",
            out2_size=200,
            out2_name="T",
            pulse_times_size=array_size,
            numb_meas_pulses=numb_meas_pulses,
            clarius_debug=1
        )
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            return_value, error = controller._execute_ex_command(command)
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            
            if return_value is not None and return_value < 0:
                raise RuntimeError(f"EX command returned error code: {return_value}")
            
            time.sleep(0.2)
            
            # Query data from GP parameters
            set_v = self._query_gp_data(controller, 20, array_size, "setV")
            set_i = self._query_gp_data(controller, 22, array_size, "setI")
            pulse_times = self._query_gp_data(controller, 31, array_size, "PulseTimes")
            
            if not pulse_times:
                # Generate approximate times
                pulse_times = [i * (meas_width + meas_delay) for i in range(len(set_v))]
            
            # Calculate resistances
            resistances: List[float] = []
            for voltage, current in zip(set_v, set_i):
                if abs(current) > 1e-12:
                    resistances.append(voltage / current)
                else:
                    resistances.append(float('inf') if voltage > 0 else float('-inf'))
            
            # Ensure all lists are same length
            min_len = min(len(set_v), len(set_i), len(pulse_times), len(resistances))
            set_v = set_v[:min_len]
            set_i = set_i[:min_len]
            pulse_times = pulse_times[:min_len]
            resistances = resistances[:min_len]
            
            return pulse_times, set_v, set_i, resistances
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    # ============================================================================
    # Phase 1: Direct Script Wrappers
    # ============================================================================
    
    def pulse_read_repeat(self, pulse_voltage: float = 1.0, 
                         pulse_width: float = 100e-6,
                         read_voltage: float = 0.2,
                         delay_between: float = 10e-3,
                         num_cycles: int = 10,
                         clim: float = 100e-3) -> Dict:
        """(Pulse → Read → Delay) × N cycles.
        
        Pattern: Initial Read → (Pulse → Read → Delay) × N
        Basic pulse response with immediate read after each pulse.
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (ms) - will be converted to seconds
            read_voltage: Read voltage (V)
            delay_between: Delay between cycles (ms) - will be converted to seconds
            num_cycles: Number of cycles
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        # Convert ms to seconds
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        
        for cycle in range(num_cycles):
            # Ensure minimum delays for C module rate calculation
            num_retention_pulses = 8  # Minimum required by C module
            min_meas_delay = self._ensure_minimum_delays(delay_between_s, num_retention_pulses)
            min_pulse_delay = max(delay_between_s, 1e-6)
            
            cfg = RetentionConfig(
                num_initial_meas_pulses=1 if cycle == 0 else 0,
                num_pulses_seq=1,
                num_pulses=num_retention_pulses,
                pulse_v=pulse_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=min_pulse_delay,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=min_meas_delay,
                i_range=i_range,
            )
            cfg.validate()
            
            timestamps, voltages, currents, resistances = self._execute_retention(cfg)
            
            # For pulse_read_repeat, we only want the first measurement after the pulse
            # The retention module gives us: initial_read (if cycle==0) + pulse + retention_reads
            # We want: initial_read (if cycle==0) + pulse + first_read
            if cycle == 0:
                # First cycle: initial_read + pulse + first_read
                all_timestamps.extend(timestamps[:2])  # Initial read + first retention read
                all_voltages.extend(voltages[:2])
                all_currents.extend(currents[:2])
                all_resistances.extend(resistances[:2])
            else:
                # Subsequent cycles: pulse + first_read (skip initial read)
                # Actually, if num_initial_meas_pulses=0, we get: pulse + retention_reads
                # So we want just the first retention read
                all_timestamps.extend(timestamps[:1])
                all_voltages.extend(voltages[:1])
                all_currents.extend(currents[:1])
                all_resistances.extend(resistances[:1])
        
        return self._format_results(all_timestamps, all_voltages, all_currents, all_resistances)
    
    def multi_pulse_then_read(self, pulse_voltage: float = 1.0,
                             num_pulses_per_read: int = 10,
                             pulse_width: float = 100e-6,
                             delay_between_pulses: float = 1e-3,
                             read_voltage: float = 0.2,
                             num_reads: int = 1,
                             delay_between_reads: float = 10e-3,
                             num_cycles: int = 20,
                             delay_between_cycles: float = 10e-3,
                             clim: float = 100e-3) -> Dict:
        """Multiple pulses then multiple reads per cycle.
        
        Pattern: Initial Read → (Pulse×N → Read×M) × Cycles
        
        Args:
            pulse_voltage: Pulse voltage (V)
            num_pulses_per_read: Number of pulses per cycle
            pulse_width: Pulse width (ms)
            delay_between_pulses: Delay between pulses (ms)
            read_voltage: Read voltage (V)
            num_reads: Number of reads per cycle
            delay_between_reads: Delay between reads (ms)
            num_cycles: Number of cycles
            delay_between_cycles: Delay between cycles (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_pulses_s = self._convert_ms_to_seconds(delay_between_pulses)
        delay_between_reads_s = self._convert_ms_to_seconds(delay_between_reads)
        delay_between_cycles_s = self._convert_ms_to_seconds(delay_between_cycles)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        cycle_numbers: List[int] = []
        
        for cycle in range(num_cycles):
            # num_pulses must be >= 8
            retention_reads = max(num_reads, 8)
            
            cfg = RetentionConfig(
                num_initial_meas_pulses=1 if cycle == 0 else 0,
                num_pulses_seq=num_pulses_per_read,
                num_pulses=retention_reads,
                pulse_v=pulse_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_pulses_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_reads_s,
                i_range=i_range,
            )
            cfg.validate()
            
            timestamps, voltages, currents, resistances = self._execute_retention(cfg)
            
            # Only take the number of reads we actually want
            if num_reads < retention_reads:
                timestamps = timestamps[:len(timestamps) - (retention_reads - num_reads)]
                voltages = voltages[:len(voltages) - (retention_reads - num_reads)]
                currents = currents[:len(currents) - (retention_reads - num_reads)]
                resistances = resistances[:len(resistances) - (retention_reads - num_reads)]
            
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            cycle_numbers.extend([cycle] * len(timestamps))
            
            if cycle < num_cycles - 1:
                time.sleep(delay_between_cycles_s)
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            cycle_numbers=cycle_numbers
        )
    
    def potentiation_only(self, set_voltage: float = 2.0,
                         pulse_width: float = 100e-6,
                         read_voltage: float = 0.2,
                         num_pulses: int = 30,
                         delay_between: float = 10e-3,
                         num_post_reads: int = 0,
                         post_read_interval: float = 1e-3,
                         clim: float = 100e-3) -> Dict:
        """Repeated SET pulses with reads.
        
        Pattern: Initial Read → Repeated SET pulses with reads
        
        Args:
            set_voltage: SET voltage (V, positive)
            pulse_width: Pulse width (ms)
            read_voltage: Read voltage (V)
            num_pulses: Number of pulses
            delay_between: Delay between pulses (ms)
            num_post_reads: Post-pulse reads (0=disabled)
            post_read_interval: Post-read interval (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        post_read_interval_s = self._convert_ms_to_seconds(post_read_interval)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        # num_pulses must be >= 8, so use max of num_post_reads and 8
        retention_reads = max(num_post_reads, 8) if num_post_reads > 0 else 8
        
        cfg = RetentionConfig(
            num_initial_meas_pulses=1,
            num_pulses_seq=num_pulses,
            num_pulses=retention_reads,
            pulse_v=abs(set_voltage),  # Ensure positive
            pulse_width=pulse_width_s,
            pulse_rise_time=1e-7,
            pulse_fall_time=1e-7,
            pulse_delay=delay_between_s,
            meas_v=read_voltage,
            meas_width=2e-6,
            meas_delay=post_read_interval_s if num_post_reads > 0 else delay_between_s,
            i_range=i_range,
        )
        cfg.validate()
        
        timestamps, voltages, currents, resistances = self._execute_retention(cfg)
        
        # If num_post_reads=0, we only want initial read + pulses (no retention reads)
        # But retention module always gives retention reads, so we'll take:
        # - Initial read (timestamps[0])
        # - First retention read as "final state" (timestamps[1] if num_post_reads=0, or all if num_post_reads>0)
        if num_post_reads == 0:
            # Just take initial read and first retention read as final state
            timestamps = timestamps[:2]
            voltages = voltages[:2]
            currents = currents[:2]
            resistances = resistances[:2]
        # Otherwise, use all results (initial + retention reads)
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def depression_only(self, reset_voltage: float = -2.0,
                       pulse_width: float = 100e-6,
                       read_voltage: float = 0.2,
                       num_pulses: int = 30,
                       delay_between: float = 10e-3,
                       num_post_reads: int = 0,
                       post_read_interval: float = 1e-3,
                       clim: float = 100e-3) -> Dict:
        """Repeated RESET pulses with reads.
        
        Pattern: Initial Read → Repeated RESET pulses with reads
        
        Args:
            reset_voltage: RESET voltage (V, negative)
            pulse_width: Pulse width (ms)
            read_voltage: Read voltage (V)
            num_pulses: Number of pulses
            delay_between: Delay between pulses (ms)
            num_post_reads: Post-pulse reads (0=disabled)
            post_read_interval: Post-read interval (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        post_read_interval_s = self._convert_ms_to_seconds(post_read_interval)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        # num_pulses must be >= 8, so use max of num_post_reads and 8
        retention_reads = max(num_post_reads, 8) if num_post_reads > 0 else 8
        
        cfg = RetentionConfig(
            num_initial_meas_pulses=1,
            num_pulses_seq=num_pulses,
            num_pulses=retention_reads,
            pulse_v=reset_voltage,  # Negative for RESET
            pulse_width=pulse_width_s,
            pulse_rise_time=1e-7,
            pulse_fall_time=1e-7,
            pulse_delay=delay_between_s,
            meas_v=read_voltage,
            meas_width=2e-6,
            meas_delay=post_read_interval_s if num_post_reads > 0 else delay_between_s,
            i_range=i_range,
        )
        cfg.validate()
        
        timestamps, voltages, currents, resistances = self._execute_retention(cfg)
        
        # If num_post_reads=0, we only want initial read + pulses (no retention reads)
        if num_post_reads == 0:
            # Just take initial read and first retention read as final state
            timestamps = timestamps[:2]
            voltages = voltages[:2]
            currents = currents[:2]
            resistances = resistances[:2]
        # Otherwise, use all results (initial + retention reads)
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def pulse_multi_read(self, pulse_voltage: float = 1.0,
                        pulse_width: float = 100e-6,
                        num_pulses: int = 1,
                        delay_between_pulses: float = 1e-3,
                        read_voltage: float = 0.2,
                        num_reads: int = 50,
                        delay_between_reads: float = 100e-3,
                        clim: float = 100e-3) -> Dict:
        """Pulse then multiple reads to monitor relaxation.
        
        Pattern: Initial Read → (Pulse × M) → Read × N
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (ms)
            num_pulses: Number of pulses
            delay_between_pulses: Delay between pulses (ms)
            read_voltage: Read voltage (V)
            num_reads: Number of reads
            delay_between_reads: Delay between reads (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_pulses_s = self._convert_ms_to_seconds(delay_between_pulses)
        delay_between_reads_s = self._convert_ms_to_seconds(delay_between_reads)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        # num_pulses must be >= 8
        retention_reads = max(num_reads, 8)
        
        cfg = RetentionConfig(
            num_initial_meas_pulses=1,
            num_pulses_seq=num_pulses,
            num_pulses=retention_reads,
            pulse_v=pulse_voltage,
            pulse_width=pulse_width_s,
            pulse_rise_time=1e-7,
            pulse_fall_time=1e-7,
            pulse_delay=delay_between_pulses_s,
            meas_v=read_voltage,
            meas_width=2e-6,
            meas_delay=delay_between_reads_s,
            i_range=i_range,
        )
        cfg.validate()
        
        timestamps, voltages, currents, resistances = self._execute_retention(cfg)
        
        # Only take the number of reads we actually want
        if num_reads < retention_reads:
            # Remove excess retention reads from the end
            timestamps = timestamps[:len(timestamps) - (retention_reads - num_reads)]
            voltages = voltages[:len(voltages) - (retention_reads - num_reads)]
            currents = currents[:len(currents) - (retention_reads - num_reads)]
            resistances = resistances[:len(resistances) - (retention_reads - num_reads)]
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def multi_read_only(self, read_voltage: float = 0.2,
                       num_reads: int = 100,
                       delay_between: float = 100e-3,
                       clim: float = 100e-3) -> Dict:
        """Just reads, no pulses.
        
        Pattern: Just reads, no pulses
        Baseline noise, read disturb characterization.
        
        Args:
            read_voltage: Read voltage (V)
            num_reads: Number of reads
            delay_between: Delay between reads (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        meas_width = 2e-6
        meas_delay = self._convert_ms_to_seconds(delay_between)
        i_range = self._convert_clim_to_i_range(clim)
        
        timestamps, voltages, currents, resistances = self._execute_readtrain(
            numb_meas_pulses=num_reads,
            meas_v=read_voltage,
            meas_width=meas_width,
            meas_delay=meas_delay,
            i_range=i_range
        )
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def relaxation_after_multi_pulse(self, pulse_voltage: float = 1.5,
                                    num_pulses: int = 10,
                                    pulse_width: float = 100e-6,
                                    delay_between_pulses: float = 1e-3,
                                    read_voltage: float = 0.2,
                                    num_reads: int = 10,
                                    delay_between_reads: float = 100e-6,
                                    clim: float = 100e-3) -> Dict:
        """Monitor relaxation after cumulative pulsing.
        
        Pattern: 1×Read → N×Pulse → N×Read
        
        Args:
            pulse_voltage: Pulse voltage (V)
            num_pulses: Number of pulses
            pulse_width: Pulse width (ms)
            delay_between_pulses: Delay between pulses (ms)
            read_voltage: Read voltage (V)
            num_reads: Number of reads
            delay_between_reads: Delay between reads (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_pulses_s = self._convert_ms_to_seconds(delay_between_pulses)
        delay_between_reads_s = self._convert_ms_to_seconds(delay_between_reads)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        # num_pulses must be >= 8
        retention_reads = max(num_reads, 8)
        
        cfg = RetentionConfig(
            num_initial_meas_pulses=1,
            num_pulses_seq=num_pulses,
            num_pulses=retention_reads,
            pulse_v=pulse_voltage,
            pulse_width=pulse_width_s,
            pulse_rise_time=1e-7,
            pulse_fall_time=1e-7,
            pulse_delay=delay_between_pulses_s,
            meas_v=read_voltage,
            meas_width=2e-6,
            meas_delay=delay_between_reads_s,
            i_range=i_range,
        )
        cfg.validate()
        
        timestamps, voltages, currents, resistances = self._execute_retention(cfg)
        
        # Only take the number of reads we actually want
        if num_reads < retention_reads:
            # Remove excess retention reads from the end
            timestamps = timestamps[:len(timestamps) - (retention_reads - num_reads)]
            voltages = voltages[:len(voltages) - (retention_reads - num_reads)]
            currents = currents[:len(currents) - (retention_reads - num_reads)]
            resistances = resistances[:len(resistances) - (retention_reads - num_reads)]
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    # ============================================================================
    # Phase 2: Multi-Script Composition Tests
    # ============================================================================
    
    def width_sweep_with_reads(self, pulse_voltage: float = 1.5,
                              pulse_widths: List[float] = None,
                              read_voltage: float = 0.2,
                              num_pulses_per_width: int = 5,
                              reset_voltage: float = -1.0,
                              reset_width: float = 1e-3,
                              delay_between_widths: float = 5.0,
                              clim: float = 100e-3) -> Dict:
        """Width sweep: For each width, pulse then read.
        
        Pattern: For each width: Initial Read → (Pulse→Read)×N → Reset
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_widths: List of pulse widths (ms) - will be converted to seconds
            read_voltage: Read voltage (V)
            num_pulses_per_width: Pulses per width
            reset_voltage: Reset voltage (V)
            reset_width: Reset width (ms)
            delay_between_widths: Delay between widths (s)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, widths
        """
        if pulse_widths is None:
            pulse_widths = [10e-6, 50e-6, 100e-6, 500e-6, 1e-3]
        
        # Convert ms to seconds
        pulse_widths_s = [self._convert_ms_to_seconds(w) for w in pulse_widths]
        reset_width_s = self._convert_ms_to_seconds(reset_width)
        delay_between_widths_s = delay_between_widths  # Already in seconds
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        widths: List[float] = []
        
        for width_idx, width_s in enumerate(pulse_widths_s):
            # Pulse sequence with this width
            # num_pulses must be >= 8, so use max of num_pulses_per_width and 8
            retention_reads = max(num_pulses_per_width, 8)
            
            cfg = RetentionConfig(
                num_initial_meas_pulses=1 if width_idx == 0 else 0,
                num_pulses_seq=num_pulses_per_width,
                num_pulses=retention_reads,  # Read after each pulse (minimum 8)
                pulse_v=pulse_voltage,
                pulse_width=width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=1e-6,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=1e-6,
                i_range=i_range,
            )
            cfg.validate()
            
            timestamps, voltages, currents, resistances = self._execute_retention(cfg)
            
            # Only take the number of reads we actually want
            if num_pulses_per_width < retention_reads:
                # Remove excess retention reads from the end
                timestamps = timestamps[:len(timestamps) - (retention_reads - num_pulses_per_width)]
                voltages = voltages[:len(voltages) - (retention_reads - num_pulses_per_width)]
                currents = currents[:len(currents) - (retention_reads - num_pulses_per_width)]
                resistances = resistances[:len(resistances) - (retention_reads - num_pulses_per_width)]
            
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            widths.extend([pulse_widths[width_idx]] * len(timestamps))
            
            # Reset between widths (except last)
            if width_idx < len(pulse_widths_s) - 1:
                reset_cfg = RetentionConfig(
                    num_initial_meas_pulses=0,
                    num_pulses_seq=1,
                    num_pulses=8,  # Minimum required, but we'll ignore results
                    pulse_v=reset_voltage,
                    pulse_width=reset_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=0,
                    meas_v=read_voltage,
                    meas_width=2e-6,
                    meas_delay=0,
                    i_range=i_range,
                )
                reset_cfg.validate()
                self._execute_retention(reset_cfg)  # Just reset, don't collect data
                
                if delay_between_widths_s > 0:
                    time.sleep(delay_between_widths_s)
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            widths=widths
        )
    
    def voltage_amplitude_sweep(self, pulse_voltage_start: float = 0.5,
                               pulse_voltage_stop: float = 2.5,
                               pulse_voltage_step: float = 0.1,
                               pulse_width: float = 100e-6,
                               read_voltage: float = 0.2,
                               num_pulses_per_voltage: int = 5,
                               delay_between: float = 10e-3,
                               reset_voltage: float = -1.0,
                               reset_width: float = 1e-3,
                               delay_between_voltages: float = 1.0,
                               clim: float = 100e-3) -> Dict:
        """Voltage amplitude sweep: Test different pulse voltages.
        
        Pattern: For each voltage: Initial Read → (Pulse → Read) × N → Reset
        
        Args:
            pulse_voltage_start: Start voltage (V)
            pulse_voltage_stop: Stop voltage (V)
            pulse_voltage_step: Voltage step (V)
            pulse_width: Pulse width (ms)
            read_voltage: Read voltage (V)
            num_pulses_per_voltage: Pulses per voltage
            delay_between: Delay between pulses (ms)
            reset_voltage: Reset voltage (V)
            reset_width: Reset width (ms)
            delay_between_voltages: Delay between voltages (s)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, voltages_applied
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        reset_width_s = self._convert_ms_to_seconds(reset_width)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        # Generate voltage list
        voltage_list: List[float] = []
        v = pulse_voltage_start
        while v <= pulse_voltage_stop:
            voltage_list.append(v)
            v += pulse_voltage_step
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        voltages_applied: List[float] = []
        
        for volt_idx, pulse_v in enumerate(voltage_list):
            # num_pulses must be >= 8
            retention_reads = max(num_pulses_per_voltage, 8)
            
            cfg = RetentionConfig(
                num_initial_meas_pulses=1 if volt_idx == 0 else 0,
                num_pulses_seq=num_pulses_per_voltage,
                num_pulses=retention_reads,
                pulse_v=pulse_v,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            cfg.validate()
            
            timestamps, voltages, currents, resistances = self._execute_retention(cfg)
            
            # Only take the number of reads we actually want
            if num_pulses_per_voltage < retention_reads:
                # Remove excess retention reads from the end
                timestamps = timestamps[:len(timestamps) - (retention_reads - num_pulses_per_voltage)]
                voltages = voltages[:len(voltages) - (retention_reads - num_pulses_per_voltage)]
                currents = currents[:len(currents) - (retention_reads - num_pulses_per_voltage)]
                resistances = resistances[:len(resistances) - (retention_reads - num_pulses_per_voltage)]
            
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            voltages_applied.extend([pulse_v] * len(timestamps))
            
            # Reset between voltages (except last)
            if volt_idx < len(voltage_list) - 1:
                reset_cfg = RetentionConfig(
                    num_initial_meas_pulses=0,
                    num_pulses_seq=1,
                    num_pulses=0,
                    pulse_v=reset_voltage,
                    pulse_width=reset_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=0,
                    meas_v=read_voltage,
                    meas_width=2e-6,
                    meas_delay=0,
                    i_range=i_range,
                )
                reset_cfg.validate()
                self._execute_retention(reset_cfg)
                
                if delay_between_voltages > 0:
                    time.sleep(delay_between_voltages)
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            voltages_applied=voltages_applied
        )
    
    def potentiation_depression_cycle(self, set_voltage: float = 2.0,
                                     reset_voltage: float = -2.0,
                                     pulse_width: float = 100e-6,
                                     read_voltage: float = 0.2,
                                     steps: int = 20,
                                     num_cycles: int = 1,
                                     delay_between: float = 10e-3,
                                     clim: float = 100e-3) -> Dict:
        """Potentiation-depression cycle: Gradual SET then RESET.
        
        Pattern: Initial Read → (Gradual SET → Gradual RESET) × N cycles
        
        Args:
            set_voltage: SET voltage (V)
            reset_voltage: RESET voltage (V)
            pulse_width: Pulse width (ms)
            read_voltage: Read voltage (V)
            steps: Steps in each direction
            num_cycles: Number of cycles
            delay_between: Delay between pulses (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, cycle_numbers
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        cycle_numbers: List[int] = []
        
        for cycle in range(num_cycles):
            # Potentiation (SET) - gradual increase
            for step in range(steps):
                cfg = RetentionConfig(
                    num_initial_meas_pulses=1 if cycle == 0 and step == 0 else 0,
                    num_pulses_seq=1,
                    num_pulses=1,
                    pulse_v=set_voltage,
                    pulse_width=pulse_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=delay_between_s,
                    meas_v=read_voltage,
                    meas_width=2e-6,
                    meas_delay=delay_between_s,
                    i_range=i_range,
                )
                cfg.validate()
                
                timestamps, voltages, currents, resistances = self._execute_retention(cfg)
                
                all_timestamps.extend(timestamps)
                all_voltages.extend(voltages)
                all_currents.extend(currents)
                all_resistances.extend(resistances)
                cycle_numbers.extend([cycle] * len(timestamps))
            
            # Depression (RESET) - gradual decrease
            for step in range(steps):
                cfg = RetentionConfig(
                    num_initial_meas_pulses=0,
                    num_pulses_seq=1,
                    num_pulses=1,
                    pulse_v=reset_voltage,
                    pulse_width=pulse_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=delay_between_s,
                    meas_v=read_voltage,
                    meas_width=2e-6,
                    meas_delay=delay_between_s,
                    i_range=i_range,
                )
                cfg.validate()
                
                timestamps, voltages, currents, resistances = self._execute_retention(cfg)
                
                all_timestamps.extend(timestamps)
                all_voltages.extend(voltages)
                all_currents.extend(currents)
                all_resistances.extend(resistances)
                cycle_numbers.extend([cycle] * len(timestamps))
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            cycle_numbers=cycle_numbers
        )
    
    def endurance_test(self, set_voltage: float = 2.0,
                      reset_voltage: float = -2.0,
                      pulse_width: float = 100e-6,
                      read_voltage: float = 0.2,
                      num_cycles: int = 1000,
                      delay_between: float = 10e-3,
                      clim: float = 100e-3) -> Dict:
        """Endurance test: SET/RESET cycles for lifetime testing.
        
        Pattern: Initial Read → (SET → Read → RESET → Read) × N
        
        Args:
            set_voltage: SET voltage (V)
            reset_voltage: RESET voltage (V)
            pulse_width: Pulse width (ms)
            read_voltage: Read voltage (V)
            num_cycles: Number of cycles
            delay_between: Delay between operations (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, cycle_numbers
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        cycle_numbers: List[int] = []
        
        for cycle in range(num_cycles):
            # SET
            set_cfg = RetentionConfig(
                num_initial_meas_pulses=1 if cycle == 0 else 0,
                num_pulses_seq=1,
                num_pulses=1,
                pulse_v=set_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            set_cfg.validate()
            
            timestamps, voltages, currents, resistances = self._execute_retention(set_cfg)
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            cycle_numbers.extend([cycle] * len(timestamps))
            
            # RESET
            reset_cfg = RetentionConfig(
                num_initial_meas_pulses=0,
                num_pulses_seq=1,
                num_pulses=1,
                pulse_v=reset_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            reset_cfg.validate()
            
            timestamps, voltages, currents, resistances = self._execute_retention(reset_cfg)
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            cycle_numbers.extend([cycle] * len(timestamps))
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            cycle_numbers=cycle_numbers
        )
    
    def ispp_test(self, start_voltage: float = 0.5,
                  voltage_step: float = 0.05,
                  max_voltage: float = 3.0,
                  pulse_width: float = 100e-6,
                  read_voltage: float = 0.2,
                  target_resistance: float = None,
                  resistance_threshold_factor: float = 0.5,
                  max_pulses: int = 100,
                  delay_between: float = 10e-3,
                  clim: float = 100e-3) -> Dict:
        """ISPP: Incremental step pulse programming.
        
        Pattern: Start at low voltage, increase by step each pulse until switching
        
        Args:
            start_voltage: Start voltage (V)
            voltage_step: Voltage step (V)
            max_voltage: Maximum voltage (V)
            pulse_width: Pulse width (ms)
            read_voltage: Read voltage (V)
            target_resistance: Target resistance (Ohm, None = auto-detect)
            resistance_threshold_factor: Resistance change factor for switching detection
            max_pulses: Maximum pulses
            delay_between: Delay between pulses (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, voltages_applied
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        voltages_applied: List[float] = []
        
        current_voltage = start_voltage
        initial_resistance = None
        pulse_count = 0
        
        while current_voltage <= max_voltage and pulse_count < max_pulses:
            cfg = RetentionConfig(
                num_initial_meas_pulses=1 if pulse_count == 0 else 0,
                num_pulses_seq=1,
                num_pulses=1,
                pulse_v=current_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            cfg.validate()
            
            timestamps, voltages, currents, resistances = self._execute_retention(cfg)
            
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            voltages_applied.extend([current_voltage] * len(timestamps))
            
            if initial_resistance is None and resistances:
                initial_resistance = resistances[0] if abs(resistances[0]) < 1e10 else None
            
            # Check for switching
            if resistances and initial_resistance and abs(initial_resistance) < 1e10:
                current_resistance = resistances[-1] if abs(resistances[-1]) < 1e10 else initial_resistance
                resistance_change = abs(current_resistance - initial_resistance) / abs(initial_resistance)
                
                if target_resistance:
                    if abs(current_resistance - target_resistance) / target_resistance < 0.1:
                        break  # Reached target
                elif resistance_change > resistance_threshold_factor:
                    break  # Significant switching detected
            
            current_voltage += voltage_step
            pulse_count += 1
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            voltages_applied=voltages_applied
        )
    
    def switching_threshold_test(self, direction: str = "set",
                                start_voltage: float = 0.5,
                                voltage_step: float = 0.05,
                                max_voltage: float = 3.0,
                                pulse_width: float = 100e-6,
                                read_voltage: float = 0.2,
                                resistance_threshold_factor: float = 0.5,
                                num_pulses_per_voltage: int = 3,
                                delay_between: float = 10e-3,
                                clim: float = 100e-3) -> Dict:
        """Switching threshold finder: Find minimum SET or RESET voltage.
        
        Pattern: Try increasing voltages, find minimum that causes switching
        
        Args:
            direction: "set" or "reset"
            start_voltage: Start voltage (V)
            voltage_step: Voltage step (V)
            max_voltage: Maximum voltage (V)
            pulse_width: Pulse width (ms)
            read_voltage: Read voltage (V)
            resistance_threshold_factor: Resistance change factor for switching
            num_pulses_per_voltage: Pulses per voltage
            delay_between: Delay between pulses (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, voltages_applied
        """
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        # Determine voltage sign based on direction
        voltage_sign = 1.0 if direction.lower() == "set" else -1.0
        start_v = abs(start_voltage) * voltage_sign
        max_v = abs(max_voltage) * voltage_sign
        step_v = abs(voltage_step) * voltage_sign
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        voltages_applied: List[float] = []
        
        current_voltage = start_v
        initial_resistance = None
        
        while abs(current_voltage) <= abs(max_v):
            cfg = RetentionConfig(
                num_initial_meas_pulses=1 if initial_resistance is None else 0,
                num_pulses_seq=num_pulses_per_voltage,
                num_pulses=1,
                pulse_v=current_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            cfg.validate()
            
            timestamps, voltages, currents, resistances = self._execute_retention(cfg)
            
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            voltages_applied.extend([current_voltage] * len(timestamps))
            
            if initial_resistance is None and resistances:
                initial_resistance = resistances[0] if abs(resistances[0]) < 1e10 else None
            
            # Check for switching
            if resistances and initial_resistance and abs(initial_resistance) < 1e10:
                current_resistance = resistances[-1] if abs(resistances[-1]) < 1e10 else initial_resistance
                resistance_change = abs(current_resistance - initial_resistance) / abs(initial_resistance)
                
                if resistance_change > resistance_threshold_factor:
                    break  # Switching detected
            
            current_voltage += step_v
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            voltages_applied=voltages_applied
        )
    
    def multilevel_programming(self, target_levels: list = None,
                              pulse_voltage: float = 1.5,
                              pulse_width: float = 100e-6,
                              read_voltage: float = 0.2,
                              num_pulses_per_level: int = 5,
                              delay_between: float = 10e-3,
                              reset_voltage: float = -1.0,
                              reset_width: float = 1e-3,
                              delay_between_levels: float = 1.0,
                              clim: float = 100e-3) -> Dict:
        """Multilevel programming: Program to specific resistance levels.
        
        Pattern: For each level: Reset → Program with pulses → Read
        
        Args:
            target_levels: List of target levels (arbitrary units, used for labeling)
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (ms)
            read_voltage: Read voltage (V)
            num_pulses_per_level: Pulses per level
            delay_between: Delay between pulses (ms)
            reset_voltage: Reset voltage (V)
            reset_width: Reset width (ms)
            delay_between_levels: Delay between levels (s)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, levels
        """
        if target_levels is None:
            target_levels = [1, 2, 3, 4, 5]
        
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        reset_width_s = self._convert_ms_to_seconds(reset_width)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        levels: List[int] = []
        
        for level_idx, level in enumerate(target_levels):
            # Reset
            reset_cfg = RetentionConfig(
                num_initial_meas_pulses=0,
                num_pulses_seq=1,
                num_pulses=8,  # Minimum required, but we'll ignore results
                pulse_v=reset_voltage,
                pulse_width=reset_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=0,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=0,
                i_range=i_range,
            )
            reset_cfg.validate()
            self._execute_retention(reset_cfg)
            
            # Program to level
            prog_cfg = RetentionConfig(
                num_initial_meas_pulses=1 if level_idx == 0 else 0,
                num_pulses_seq=num_pulses_per_level,
                num_pulses=1,  # Final read
                pulse_v=pulse_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            prog_cfg.validate()
            
            timestamps, voltages, currents, resistances = self._execute_retention(prog_cfg)
            
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            levels.extend([level] * len(timestamps))
            
            if level_idx < len(target_levels) - 1 and delay_between_levels > 0:
                time.sleep(delay_between_levels)
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            levels=levels
        )
    
    def pulse_train_varying_amplitudes(self, pulse_voltages: list = None,
                                      pulse_width: float = 100e-6,
                                      read_voltage: float = 0.2,
                                      num_repeats: int = 1,
                                      delay_between: float = 10e-3,
                                      clim: float = 100e-3) -> Dict:
        """Pulse train with varying amplitudes.
        
        Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N
        
        Args:
            pulse_voltages: List of pulse voltages (V)
            pulse_width: Pulse width (ms)
            read_voltage: Read voltage (V)
            num_repeats: Number of repeats
            delay_between: Delay between pulses (ms)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, voltages_applied
        """
        if pulse_voltages is None:
            pulse_voltages = [1.0, 1.5, 2.0, -1.0, -1.5, -2.0]
        
        pulse_width_s = self._convert_ms_to_seconds(pulse_width)
        delay_between_s = self._convert_ms_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        voltages_applied: List[float] = []
        
        for repeat in range(num_repeats):
            for volt_idx, pulse_v in enumerate(pulse_voltages):
                cfg = RetentionConfig(
                    num_initial_meas_pulses=1 if repeat == 0 and volt_idx == 0 else 0,
                    num_pulses_seq=1,
                    num_pulses=1,
                    pulse_v=pulse_v,
                    pulse_width=pulse_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=delay_between_s,
                    meas_v=read_voltage,
                    meas_width=2e-6,
                    meas_delay=delay_between_s,
                    i_range=i_range,
                )
                cfg.validate()
                
                timestamps, voltages, currents, resistances = self._execute_retention(cfg)
                
                all_timestamps.extend(timestamps)
                all_voltages.extend(voltages)
                all_currents.extend(currents)
                all_resistances.extend(resistances)
                voltages_applied.extend([pulse_v] * len(timestamps))
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            voltages_applied=voltages_applied
        )
    
    # ============================================================================
    # Placeholders for Tests Requiring New C Modules
    # ============================================================================
    
    def current_range_finder(self, test_voltage: float = 0.2,
                            num_reads_per_range: int = 10,
                            delay_between_reads: float = 10e-3,
                            current_ranges: List[float] = None) -> Dict:
        """Find optimal current measurement range.
        
        NOTE: This test requires a new C module that can test multiple current
        ranges and recommend the optimal range. Currently not implemented.
        
        Raises:
            NotImplementedError: This test requires a new C module
        """
        raise NotImplementedError(
            "current_range_finder requires a new C module (current_range_finder_dual_channel.c) "
            "that can test multiple current ranges and recommend the optimal range based on "
            "signal-to-noise ratio. This module has not been developed yet."
        )
    
    def width_sweep_with_all_measurements(self, pulse_voltage: float = 1.5,
                                         pulse_widths: List[float] = None,
                                         read_voltage: float = 0.2,
                                         num_pulses_per_width: int = 5,
                                         reset_voltage: float = -1.0,
                                         reset_width: float = 1e-3,
                                         delay_between_widths: float = 5.0,
                                         clim: float = 100e-3) -> Dict:
        """Width sweep with pulse current measurement.
        
        NOTE: This test requires a C module that can measure current during the
        programming pulse itself, not just after. Currently not implemented.
        
        Raises:
            NotImplementedError: This test requires a new C module
        """
        raise NotImplementedError(
            "width_sweep_with_all_measurements requires a new C module that can measure "
            "current during the programming pulse itself (not just after). The existing "
            "retention module only measures during read pulses. A new module "
            "(pulse_with_measurement_dual_channel.c) would be needed."
        )
    
    def relaxation_after_multi_pulse_with_pulse_measurement(self, pulse_voltage: float = 1.5,
                                         num_pulses: int = 10,
                                         pulse_width: float = 100e-6,
                                         delay_between_pulses: float = 1e-3,
                                         read_voltage: float = 0.2,
                                         num_reads: int = 10,
                                         delay_between_reads: float = 100e-6,
                                         clim: float = 100e-3) -> Dict:
        """Relaxation with pulse current measurement.
        
        NOTE: This test requires a C module that can measure current during the
        programming pulse itself, not just after. Currently not implemented.
        
        Raises:
            NotImplementedError: This test requires a new C module
        """
        raise NotImplementedError(
            "relaxation_after_multi_pulse_with_pulse_measurement requires a new C module "
            "that can measure current during the programming pulse itself (not just after). "
            "The existing retention module only measures during read pulses. A new module "
            "(pulse_with_measurement_dual_channel.c) would be needed."
        )


# ============================================================================
# Testing and Examples
# ============================================================================

if __name__ == "__main__":
    """Standalone testing examples for keithley4200_kxci_scripts."""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test Keithley 4200A KXCI Scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test multi_read_only (simplest test)
  python keithley4200_kxci_scripts.py --test multi_read_only --gpib GPIB0::17::INSTR --num-reads 10
  
  # Test pulse_read_repeat
  python keithley4200_kxci_scripts.py --test pulse_read_repeat --gpib GPIB0::17::INSTR --num-cycles 5
  
  # Test potentiation_only
  python keithley4200_kxci_scripts.py --test potentiation_only --gpib GPIB0::17::INSTR --num-pulses 10
        """
    )
    
    parser.add_argument("--test", type=str, default="multi_read_only",
                       choices=["pulse_read_repeat", "multi_pulse_then_read", "potentiation_only",
                               "depression_only", "pulse_multi_read", "multi_read_only",
                               "relaxation_after_multi_pulse", "width_sweep_with_reads",
                               "voltage_amplitude_sweep", "potentiation_depression_cycle",
                               "endurance_test", "ispp_test", "switching_threshold_test",
                               "multilevel_programming", "pulse_train_varying_amplitudes"],
                       help="Test to run")
    parser.add_argument("--gpib", type=str, default="GPIB0::17::INSTR",
                       help="GPIB address")
    parser.add_argument("--timeout", type=float, default=30.0,
                       help="Timeout in seconds")
    
    # Common parameters
    parser.add_argument("--pulse-voltage", type=float, default=1.5, help="Pulse voltage (V)")
    parser.add_argument("--pulse-width", type=float, default=1.0, help="Pulse width (ms)")
    parser.add_argument("--read-voltage", type=float, default=0.2, help="Read voltage (V)")
    parser.add_argument("--delay-between", type=float, default=10.0, help="Delay between (ms)")
    parser.add_argument("--num-cycles", type=int, default=5, help="Number of cycles")
    parser.add_argument("--num-pulses", type=int, default=10, help="Number of pulses")
    parser.add_argument("--num-reads", type=int, default=10, help="Number of reads")
    parser.add_argument("--clim", type=float, default=100e-6, help="Current limit (A)")
    
    args = parser.parse_args()
    
    print("="*80)
    print("Keithley 4200A KXCI Scripts - Test Runner")
    print("="*80)
    print(f"Test: {args.test}")
    print(f"GPIB Address: {args.gpib}")
    print("="*80)
    
    scripts = Keithley4200_KXCI_Scripts(gpib_address=args.gpib, timeout=args.timeout)
    
    try:
        if args.test == "pulse_read_repeat":
            results = scripts.pulse_read_repeat(
                pulse_voltage=args.pulse_voltage,
                pulse_width=args.pulse_width,
                read_voltage=args.read_voltage,
                delay_between=args.delay_between,
                num_cycles=args.num_cycles,
                clim=args.clim
            )
        elif args.test == "multi_read_only":
            results = scripts.multi_read_only(
                read_voltage=args.read_voltage,
                num_reads=args.num_reads,
                delay_between=args.delay_between,
                clim=args.clim
            )
        elif args.test == "potentiation_only":
            results = scripts.potentiation_only(
                set_voltage=args.pulse_voltage,
                pulse_width=args.pulse_width,
                read_voltage=args.read_voltage,
                num_pulses=args.num_pulses,
                delay_between=args.delay_between,
                clim=args.clim
            )
        elif args.test == "depression_only":
            results = scripts.depression_only(
                reset_voltage=-args.pulse_voltage,
                pulse_width=args.pulse_width,
                read_voltage=args.read_voltage,
                num_pulses=args.num_pulses,
                delay_between=args.delay_between,
                clim=args.clim
            )
        elif args.test == "pulse_multi_read":
            results = scripts.pulse_multi_read(
                pulse_voltage=args.pulse_voltage,
                pulse_width=args.pulse_width,
                num_pulses=1,
                delay_between_pulses=args.delay_between,
                read_voltage=args.read_voltage,
                num_reads=args.num_reads,
                delay_between_reads=args.delay_between,
                clim=args.clim
            )
        elif args.test == "relaxation_after_multi_pulse":
            results = scripts.relaxation_after_multi_pulse(
                pulse_voltage=args.pulse_voltage,
                num_pulses=args.num_pulses,
                pulse_width=args.pulse_width,
                delay_between_pulses=args.delay_between,
                read_voltage=args.read_voltage,
                num_reads=args.num_reads,
                delay_between_reads=args.delay_between,
                clim=args.clim
            )
        else:
            print(f"Test '{args.test}' not yet implemented in test runner")
            print("Available tests: pulse_read_repeat, multi_read_only, potentiation_only, "
                  "depression_only, pulse_multi_read, relaxation_after_multi_pulse")
            exit(1)
        
        print("\n" + "="*80)
        print("Test Results:")
        print("="*80)
        print(f"Total measurements: {len(results['timestamps'])}")
        print(f"Timestamps range: {min(results['timestamps']):.6e} to {max(results['timestamps']):.6e} s")
        
        valid_resistances = [r for r in results['resistances'] if abs(r) < 1e10 and abs(r) > 0]
        if valid_resistances:
            import statistics
            print(f"Resistance range: {min(valid_resistances)/1e3:.2f} to {max(valid_resistances)/1e3:.2f} kOhm")
            print(f"Resistance mean: {statistics.mean(valid_resistances)/1e3:.2f} kOhm")
            print(f"Resistance std dev: {statistics.stdev(valid_resistances)/1e3:.2f} kOhm")
        
        print("\nFirst 10 measurements:")
        for i in range(min(10, len(results['timestamps']))):
            r_str = f"{results['resistances'][i]/1e3:.2f}" if abs(results['resistances'][i]) < 1e10 else "inf"
            print(f"  {i:2d}: t={results['timestamps'][i]:.6e}s, "
                  f"V={results['voltages'][i]:.6f}V, "
                  f"I={results['currents'][i]:.6e}A, "
                  f"R={r_str}kOhm")
        
        print("\n✓ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        # Cleanup connection
        if scripts._controller:
            scripts._controller.disconnect()

