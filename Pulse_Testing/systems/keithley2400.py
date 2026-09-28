"""
Keithley 2400 Measurement System Adapter
=========================================

Script location: Equipment/SMU_AND_PMU/keithley2400/scpi_scripts.py.
Controller: Equipment/SMU_AND_PMU/keithley2400/controller.py.
This file: Pulse_Testing/systems/keithley2400.py (adapter only; delegates to Equipment).

Wraps Keithley2400_SCPI_Scripts to provide standardized BaseMeasurementSystem
interface for the Pulse Testing architecture.
"""

import time
from typing import Dict, List, Any, Optional, Tuple
from .base_system import BaseMeasurementSystem
from Equipment.SMU_AND_PMU.keithley2400.scpi_scripts import Keithley2400_SCPI_Scripts
from Equipment.SMU_AND_PMU.keithley2400.controller import Keithley2400Controller


# Hardware limits for Keithley 2400
MIN_PULSE_WIDTH = 0.01  # 10ms minimum due to GPIB speed limitations
MAX_PULSE_WIDTH = 10.0  # seconds
MIN_VOLTAGE = -200.0    # volts (2400 spec)
MAX_VOLTAGE = 200.0      # volts (2400 spec)
MIN_CURRENT_LIMIT = 1e-9  # amps
MAX_CURRENT_LIMIT = 1.0   # amps


class Keithley2400System(BaseMeasurementSystem):
    """Adapter for Keithley 2400 SCPI measurement system."""
    
    # Default device address for this system (GPIB format)
    DEFAULT_ADDRESS = "GPIB0::24::INSTR"
    
    def __init__(self):
        """Initialize the 2400 system (connection happens later)."""
        self.controller: Optional[Keithley2400Controller] = None
        self.test_scripts: Optional[Keithley2400_SCPI_Scripts] = None
        self._connected = False
        self._address: Optional[str] = None
        self._timeout: float = 5.0
    
    @classmethod
    def get_default_address(cls) -> str:
        """Get default device address for this system."""
        return cls.DEFAULT_ADDRESS
    
    def get_system_name(self) -> str:
        """Return system identifier."""
        return 'keithley2400'
    
    def get_hardware_limits(self) -> Dict[str, Any]:
        """Return hardware capability limits."""
        return {
            'min_pulse_width': MIN_PULSE_WIDTH,
            'max_pulse_width': MAX_PULSE_WIDTH,
            'min_voltage': MIN_VOLTAGE,
            'max_voltage': MAX_VOLTAGE,
            'min_current_limit': MIN_CURRENT_LIMIT,
            'max_current_limit': MAX_CURRENT_LIMIT,
        }
    
    def connect(self, address: str, timeout: float = 5.0, **kwargs) -> bool:
        """Connect to Keithley 2400 via GPIB.
        
        Args:
            address: Device address (GPIB format, e.g., "GPIB0::24::INSTR")
            timeout: Communication timeout in seconds
            **kwargs: Additional connection parameters (ignored for 2400)
        
        Returns:
            True if connection successful
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            self._address = address
            self._timeout = timeout
            self.controller = Keithley2400Controller(gpib_address=address, timeout=timeout)
            
            if not self.controller.device:
                raise ConnectionError("Failed to initialize Keithley 2400 controller")
            
            # Create test scripts instance
            self.test_scripts = Keithley2400_SCPI_Scripts(self.controller)
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            self.controller = None
            self.test_scripts = None
            raise ConnectionError(f"Failed to connect to Keithley 2400: {e}") from e
    
    def disconnect(self) -> None:
        """Disconnect from Keithley 2400."""
        if self.controller:
            try:
                self.controller.close()
            except:
                pass
            self.controller = None
        self.test_scripts = None
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if system is connected."""
        return self._connected and self.controller is not None and self.test_scripts is not None
    
    def get_idn(self) -> str:
        """Get instrument identification."""
        if self.controller:
            return self.controller.get_idn()
        return "Not Connected"
    
    # Delegate all test methods to the underlying test_scripts object
    # All methods must return standardized format (already done by SCPI scripts)
    
    def pulse_read_repeat(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → (Pulse → Read → Delay) × N"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.pulse_read_repeat(**params)
    
    def pulse_then_read(self, **params) -> Dict[str, Any]:
        """Pattern: (Pulse → Delay → Read) × N"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.pulse_then_read(**params)
    
    def multi_pulse_then_read(self, **params) -> Dict[str, Any]:
        """Pattern: (Pulse×N → Read×M) × Cycles"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.multi_pulse_then_read(**params)
    
    def varying_width_pulses(self, **params) -> Dict[str, Any]:
        """Test multiple pulse widths"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.varying_width_pulses(**params)
    
    def width_sweep_with_reads(self, **params) -> Dict[str, Any]:
        """Width sweep: For each width: (Read→Pulse→Read)×N, Reset"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.width_sweep_with_reads(**params)
    
    def width_sweep_with_all_measurements(self, **params) -> Dict[str, Any]:
        """Width sweep with pulse peak measurements"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.width_sweep_with_all_measurements(**params)
    
    def potentiation_depression_cycle(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Gradual SET → Gradual RESET"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.potentiation_depression_cycle(**params)
    
    def potentiation_only(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated SET pulses with reads"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.potentiation_only(**params)
    
    def depression_only(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated RESET pulses with reads"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.depression_only(**params)
    
    def endurance_test(self, **params) -> Dict[str, Any]:
        """Pattern: (SET → Read → RESET → Read) × N cycles"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.endurance_test(**params)
    
    def retention_test(self, **params) -> Dict[str, Any]:
        """Pattern: Pulse → Read @ t1 → Read @ t2 → Read @ t3..."""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        from .retention_intervals import normalize_timed_retention_params
        params = normalize_timed_retention_params(params)
        return self.test_scripts.retention_test(**params)

    def log_retention_test(self, **params) -> Dict[str, Any]:
        """Log-spaced retention (PC-timed on 2400)."""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        from .retention_intervals import (
            fit_log_retention_decay,
            normalize_log_retention_params,
        )
        params = normalize_log_retention_params(params)
        result = self.test_scripts.retention_test(**params)
        ops = result.get("operation") or []
        post_idx = [i for i, op in enumerate(ops) if op == "post_pulse"]
        t_pulse = result["timestamps"][post_idx[0]] if post_idx else None
        fit = fit_log_retention_decay(
            result["timestamps"], result["resistances"], ops, t_pulse_end=t_pulse
        )
        if fit:
            result["retention_fit"] = fit
        result["read_intervals_used"] = params.get("read_intervals", [])
        return result

    def volatile_screening_test(self, **params) -> Dict[str, Any]:
        """Volatile screening via PC-timed reads (GPIB — not ms-resolution)."""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        from .retention_intervals import (
            classify_volatile_screening,
            normalize_volatile_screening_params,
        )
        params = normalize_volatile_screening_params(params)
        burst = params.get("burst_intervals") or []
        tail = params.get("slow_tail_intervals") or []
        all_intervals = list(burst)
        for t in tail:
            if not all_intervals or t > all_intervals[-1]:
                all_intervals.append(t)
        run_params = {
            k: v
            for k, v in params.items()
            if k
            not in (
                "burst_intervals",
                "burst_wait_deltas",
                "slow_tail_intervals",
                "schedule_mode",
                "t_min_s",
                "burst_t_max_s",
                "num_reads",
                "include_slow_tail",
                "slow_tail_start_s",
                "slow_tail_num_reads",
                "include_early_burst",
            )
        }
        run_params["read_intervals"] = all_intervals
        result = self.test_scripts.retention_test(**run_params)
        ops = result.get("operation") or []
        for i, op in enumerate(ops):
            if op == "retention" and i > 0:
                post_t = None
                post_idx = [j for j, o in enumerate(ops) if o == "post_pulse"]
                if post_idx:
                    post_t = result["timestamps"][post_idx[0]]
                if post_t is not None and result["timestamps"][i] > (
                    burst[-1] if burst else 0
                ):
                    ops[i] = "slow_tail"
        result["operation"] = ops
        post_idx = [i for i, op in enumerate(ops) if op == "post_pulse"]
        t_pulse = result["timestamps"][post_idx[0]] if post_idx else None
        result["volatile_screening"] = classify_volatile_screening(
            result["timestamps"],
            result["resistances"],
            ops,
            retention_threshold=float(params.get("retention_threshold", 0.85)),
            min_switch_ratio=float(params.get("min_switch_ratio", 0.05)),
            t_pulse_end=t_pulse,
        )
        result["read_intervals_used"] = burst
        if tail:
            result["slow_tail_intervals_used"] = tail
        return result
    
    def pulse_multi_read(self, **params) -> Dict[str, Any]:
        """Pattern: N pulses then many reads"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.pulse_multi_read(**params)
    
    def multi_read_only(self, **params) -> Dict[str, Any]:
        """Pattern: Just reads, no pulses"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.multi_read_only(**params)
    
    def current_range_finder(self, **params) -> Dict[str, Any]:
        """Find optimal current measurement range"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.current_range_finder(**params)
    
    def relaxation_after_multi_pulse(self, **params) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse → N×Read (measure reads only)"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.relaxation_after_multi_pulse(**params)
    
    def relaxation_after_multi_pulse_with_pulse_measurement(self, **params) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse(measured) → N×Read"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.relaxation_after_multi_pulse_with_pulse_measurement(**params)
    
    # Optional additional tests (also available in 2400)
    
    def voltage_amplitude_sweep(self, **params) -> Dict[str, Any]:
        """Pattern: For each voltage: Initial Read → (Pulse → Read) × N → Reset"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.voltage_amplitude_sweep(**params)
    
    def ispp_test(self, **params) -> Dict[str, Any]:
        """Pattern: Start at low voltage, increase by step each pulse"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.ispp_test(**params)
    
    def switching_threshold_test(self, **params) -> Dict[str, Any]:
        """Pattern: Try increasing voltages, find minimum that causes switching"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.switching_threshold_test(**params)
    
    def multilevel_programming(self, **params) -> Dict[str, Any]:
        """Pattern: For each level: Reset → Program with pulses → Read"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.multilevel_programming(**params)
    
    def pulse_train_varying_amplitudes(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N"""
        if not self.test_scripts:
            raise RuntimeError("Not connected to device")
        return self.test_scripts.pulse_train_varying_amplitudes(**params)

    # ----- Optical-test API: source V + measure I in a loop (for laser+SMU hybrid tests) -----

    def source_voltage_for_optical(self, voltage: float, current_limit: float) -> None:
        """Configure DC voltage source and turn output on for optical+read tests."""
        if not self.controller:
            raise RuntimeError("Not connected to device")
        self.controller.set_voltage(voltage, current_limit)

    def measure_current_once(self) -> Tuple[float, float]:
        """Take one current reading. Returns (timestamp_sec, current_A)."""
        if not self.controller:
            raise RuntimeError("Not connected to device")
        t = time.perf_counter()
        i = self.controller.measure_current()
        return (t, i if i is not None else 0.0)

    def source_output_off(self) -> None:
        """Turn SMU output off (e.g. after optical test)."""
        if self.controller:
            try:
                self.controller.enable_output(False)
            except Exception:
                pass










