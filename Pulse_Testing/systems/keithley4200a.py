"""
Keithley 4200A Measurement System Implementation
==================================================

Implementation for Keithley 4200A measurement system using KXCI scripts.
Integrates with keithley4200_kxci_scripts.py for all test functions.
"""

from typing import Dict, List, Any, Optional
from .base_system import BaseMeasurementSystem
# Import from backward-compatible module
from Equipment.SMU_AND_PMU import keithley4200_kxci_scripts

# Extract script class and constants
try:
    Keithley4200_KXCI_Scripts = keithley4200_kxci_scripts.Keithley4200_KXCI_Scripts
    MIN_PULSE_WIDTH = getattr(keithley4200_kxci_scripts, 'MIN_PULSE_WIDTH', 50e-6)
    MAX_PULSE_WIDTH = getattr(keithley4200_kxci_scripts, 'MAX_PULSE_WIDTH', 1.0)
    MIN_VOLTAGE = getattr(keithley4200_kxci_scripts, 'MIN_VOLTAGE', -40.0)
    MAX_VOLTAGE = getattr(keithley4200_kxci_scripts, 'MAX_VOLTAGE', 40.0)
    MIN_CURRENT_RANGE = getattr(keithley4200_kxci_scripts, 'MIN_CURRENT_RANGE', 100e-9)
    MAX_CURRENT_RANGE = getattr(keithley4200_kxci_scripts, 'MAX_CURRENT_RANGE', 0.8)
    MAX_MAX_POINTS = getattr(keithley4200_kxci_scripts, 'MAX_MAX_POINTS', 1_000_000)
except AttributeError:
    # Fallback if not available - import directly
    from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import (
        Keithley4200_KXCI_Scripts,
    )
    MIN_PULSE_WIDTH = 50e-6
    MAX_PULSE_WIDTH = 1.0
    MIN_VOLTAGE = -40.0
    MAX_VOLTAGE = 40.0
    MIN_CURRENT_RANGE = 100e-9
    MAX_CURRENT_RANGE = 0.8
    MAX_MAX_POINTS = 1_000_000  # Updated to match kxci_scripts.py


class Keithley4200ASystem(BaseMeasurementSystem):
    """Keithley 4200A measurement system implementation.
    
    Uses keithley4200_kxci_scripts.py for all test functions.
    Supports GPIB addresses (e.g., "GPIB0::17::INSTR").
    """
    
    # Default device address for this system (GPIB format)
    DEFAULT_ADDRESS = "GPIB0::17::INSTR"  # Update with actual GPIB number when known
    
    def __init__(self):
        """Initialize the 4200A system (connection happens later)."""
        self._connected = False
        self._scripts: Optional[Keithley4200_KXCI_Scripts] = None
        self._address: Optional[str] = None
        self._timeout: float = 30.0
    
    @classmethod
    def get_default_address(cls) -> str:
        """Get default device address for this system."""
        return cls.DEFAULT_ADDRESS
    
    def get_system_name(self) -> str:
        """Return system identifier."""
        return 'keithley4200a'
    
    def get_hardware_limits(self) -> Dict[str, Any]:
        """Return hardware capability limits from keithley4200_kxci_scripts.py."""
        return {
            'min_pulse_width': MIN_PULSE_WIDTH,  # 20ns from C module limit
            'max_pulse_width': MAX_PULSE_WIDTH,   # 1s
            'min_voltage': MIN_VOLTAGE,           # -20V
            'max_voltage': MAX_VOLTAGE,           # +20V
            'min_current_limit': MIN_CURRENT_RANGE,  # 100nA
            'max_current_limit': MAX_CURRENT_RANGE,  # 0.8A
            'max_points': MAX_MAX_POINTS,        # 1,000,000 (C module hard limit, updated)
            'min_sampling_rate': 200000,         # samples/second (C module requirement)
            'max_measurement_time': 5000.0,      # ~5,000 seconds (calculated from max_points/min_rate, updated)
        }
    
    def connect(self, address: str, **kwargs) -> bool:
        """Connect to Keithley 4200A.
        
        Args:
            address: System address (GPIB format expected, e.g., "GPIB0::17::INSTR")
                     Also supports IP:port format (e.g., "192.168.0.10:8888") - will convert to GPIB
            **kwargs: Additional connection parameters (timeout, etc.)
        
        Returns:
            True if connection successful
        
        Raises:
            ConnectionError: If connection fails
        """
        self._address = address
        self._timeout = kwargs.get('timeout', 30.0)
        
        # Handle IP:port format - convert to GPIB if needed
        # For now, we'll use the address as-is (KXCI scripts expect GPIB format)
        # If address is IP:port, we might need to handle it differently
        # For now, assume GPIB format
        
        try:
            # Create KXCI scripts instance
            self._scripts = Keithley4200_KXCI_Scripts(
                gpib_address=address,
                timeout=self._timeout
            )
            
            # Test connection by getting controller
            controller = self._scripts._get_controller()
            if controller.connect():
                self._connected = True
                return True
            else:
                self._connected = False
                return False
                
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to 4200A at {address}: {e}") from e
    
    def disconnect(self) -> None:
        """Disconnect from Keithley 4200A."""
        if self._scripts and self._scripts._controller:
            try:
                self._scripts._controller.disconnect()
            except:
                pass
        self._connected = False
        self._scripts = None
        self._address = None
    
    def is_connected(self) -> bool:
        """Check if system is connected."""
        return self._connected and self._scripts is not None
    
    def get_idn(self) -> str:
        """Get instrument identification."""
        if self._connected and self._scripts:
            try:
                controller = self._scripts._get_controller()
                if controller.inst:
                    # Try to query IDN
                    try:
                        idn = controller.inst.query("*IDN?").strip()
                        return f"Keithley 4200A - {idn}"
                    except:
                        return f"Keithley 4200A - {self._address}"
            except:
                pass
        return "Not Connected"
    
    # Test methods - all delegate to KXCI scripts
    
    def pulse_read_repeat(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → (Pulse → Read → Delay) × N"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        print(f"\n[System Wrapper] Converting parameters from µs to seconds:")
        if 'pulse_width' in params:
            pulse_width_us = params['pulse_width']
            # Validate: pulse_width should be in µs range (typically 0.02 to 1000 µs)
            if pulse_width_us > 1_000_000:  # If > 1 second in µs, likely wrong unit
                raise ValueError(f"pulse_width appears to be in wrong units. Got {pulse_width_us:.2f} µs "
                               f"({pulse_width_us/1e6:.2e} s). Expected value should be < 1000 µs. "
                               f"Check that the unit selector is set correctly (should be µs for 4200A).")
            params['pulse_width'] = pulse_width_us / 1_000_000.0  # µs → s
            print(f"  pulse_width: {pulse_width_us:.2f} µs → {params['pulse_width']:.2e} s")
        if 'delay_between' in params:
            delay_us = params['delay_between']
            if delay_us > 1_000_000:  # If > 1 second in µs, likely wrong unit
                raise ValueError(f"delay_between appears to be in wrong units. Got {delay_us:.2f} µs "
                               f"({delay_us/1e6:.2e} s). Expected value should be < 1000 µs.")
            params['delay_between'] = delay_us / 1_000_000.0  # µs → s
            print(f"  delay_between: {delay_us:.2f} µs → {params['delay_between']:.2e} s")
        if 'read_width' in params:
            read_width_us = params['read_width']
            if read_width_us > 1_000_000:  # If > 1 second in µs, likely wrong unit
                raise ValueError(f"read_width appears to be in wrong units. Got {read_width_us:.2f} µs "
                               f"({read_width_us/1e6:.2e} s). Expected value should be < 1000 µs.")
            params['read_width'] = read_width_us / 1_000_000.0  # µs → s
            print(f"  read_width: {read_width_us:.2f} µs → {params['read_width']:.2e} s")
        if 'read_delay' in params:
            read_delay_us = params['read_delay']
            if read_delay_us > 1_000_000:  # If > 1 second in µs, likely wrong unit
                raise ValueError(f"read_delay appears to be in wrong units. Got {read_delay_us:.2f} µs "
                               f"({read_delay_us/1e6:.2e} s). Expected value should be < 1000 µs.")
            params['read_delay'] = read_delay_us / 1_000_000.0  # µs → s
            print(f"  read_delay: {read_delay_us:.2f} µs → {params['read_delay']:.2e} s")
        if 'read_rise_time' in params:
            read_rise_us = params['read_rise_time']
            if read_rise_us > 1_000_000:  # If > 1 second in µs, likely wrong unit
                raise ValueError(f"read_rise_time appears to be in wrong units. Got {read_rise_us:.2f} µs "
                               f"({read_rise_us/1e6:.2e} s). Expected value should be < 1000 µs.")
            params['read_rise_time'] = read_rise_us / 1_000_000.0  # µs → s
            print(f"  read_rise_time: {read_rise_us:.2f} µs → {params['read_rise_time']:.2e} s")
        return self._scripts.pulse_read_repeat(**params)
    
    def pulse_then_read(self, **params) -> Dict[str, Any]:
        """Pattern: (Pulse → Delay → Read) × N"""
        # Not implemented in 4200A scripts - use pulse_read_repeat instead
        raise NotImplementedError("pulse_then_read not available for 4200A - use pulse_read_repeat")
    
    def multi_pulse_then_read(self, **params) -> Dict[str, Any]:
        """Pattern: (Pulse×N → Read×M) × Cycles"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        print(f"\n[System Wrapper] Converting parameters from µs to seconds:")
        if 'pulse_width' in params:
            pulse_width_us = params['pulse_width']
            if pulse_width_us > 1_000_000:  # If > 1 second in µs, likely wrong unit
                raise ValueError(f"pulse_width appears to be in wrong units. Got {pulse_width_us:.2f} µs "
                               f"({pulse_width_us/1e6:.2e} s). Expected value should be < 1000 µs.")
            params['pulse_width'] = pulse_width_us / 1_000_000.0  # µs → s
            print(f"  pulse_width: {pulse_width_us:.2f} µs → {params['pulse_width']:.2e} s")
        if 'delay_between_pulses' in params:
            delay_us = params['delay_between_pulses']
            if delay_us > 1_000_000:
                raise ValueError(f"delay_between_pulses appears to be in wrong units. Got {delay_us:.2f} µs "
                               f"({delay_us/1e6:.2e} s). Expected value should be < 1000 µs.")
            params['delay_between_pulses'] = delay_us / 1_000_000.0  # µs → s
            print(f"  delay_between_pulses: {delay_us:.2f} µs → {params['delay_between_pulses']:.2e} s")
        if 'delay_between_reads' in params:
            delay_reads_us = params['delay_between_reads']
            if delay_reads_us > 1_000_000:
                raise ValueError(f"delay_between_reads appears to be in wrong units. Got {delay_reads_us:.2f} µs "
                               f"({delay_reads_us/1e6:.2e} s). Expected value should be < 1000 µs.")
            params['delay_between_reads'] = delay_reads_us / 1_000_000.0  # µs → s
            print(f"  delay_between_reads: {delay_reads_us:.2f} µs → {params['delay_between_reads']:.2e} s")
        if 'delay_between_cycles' in params:
            delay_cycles_us = params['delay_between_cycles']
            if delay_cycles_us > 1_000_000:
                raise ValueError(f"delay_between_cycles appears to be in wrong units. Got {delay_cycles_us:.2f} µs "
                               f"({delay_cycles_us/1e6:.2e} s). Expected value should be < 1000 µs.")
            params['delay_between_cycles'] = delay_cycles_us / 1_000_000.0  # µs → s
            print(f"  delay_between_cycles: {delay_cycles_us:.2f} µs → {params['delay_between_cycles']:.2e} s")
        return self._scripts.multi_pulse_then_read(**params)
    
    def varying_width_pulses(self, **params) -> Dict[str, Any]:
        """Test multiple pulse widths"""
        # Not directly available - use width_sweep_with_reads instead
        raise NotImplementedError("varying_width_pulses not available for 4200A - use width_sweep_with_reads")
    
    def width_sweep_with_reads(self, **params) -> Dict[str, Any]:
        """Width sweep: For each width: (Read→Pulse→Read)×N, Reset"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Note: For 4200A, the GUI already converts these to µs:
        # - reset_width → µs (via params_4200a_in_us)
        # pulse_widths is a list, so it needs special handling - convert from seconds to µs
        if 'pulse_widths' in params:
            if isinstance(params['pulse_widths'], str):
                # Comma-separated string
                widths = [float(x.strip()) for x in params['pulse_widths'].split(",")]
            else:
                widths = params['pulse_widths']
            # Convert from seconds to µs (pulse_widths list is not in params_4200a_in_us)
            params['pulse_widths'] = [w * 1e6 for w in widths]
        # reset_width is already in µs from GUI, no conversion needed
        if 'delay_between_widths' in params:
            # Already in seconds, keep as-is
            pass
        return self._scripts.width_sweep_with_reads(**params)
    
    def width_sweep_with_all_measurements(self, **params) -> Dict[str, Any]:
        """Width sweep with pulse peak measurements"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Note: For 4200A, the GUI already converts these to µs:
        # - reset_width → µs (via params_4200a_in_us)
        # pulse_widths is a list, so it needs special handling - convert from seconds to µs
        if 'pulse_widths' in params:
            if isinstance(params['pulse_widths'], str):
                widths = [float(x.strip()) for x in params['pulse_widths'].split(",")]
            else:
                widths = params['pulse_widths']
            # Convert from seconds to µs (pulse_widths list is not in params_4200a_in_us)
            params['pulse_widths'] = [w * 1e6 for w in widths]
        # reset_width is already in µs from GUI, no conversion needed
        return self._scripts.width_sweep_with_all_measurements(**params)
    
    def potentiation_depression_cycle(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Gradual SET → Gradual RESET"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        # Map delay_between_cycles to delay_between for backend compatibility
        if 'delay_between_cycles' in params:
            params['delay_between'] = params['delay_between_cycles'] / 1_000_000.0  # µs → s
            del params['delay_between_cycles']  # Remove the new parameter name
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] / 1_000_000.0  # µs → s
        if 'read_width' in params:
            params['read_width'] = params['read_width'] / 1_000_000.0  # µs → s
        if 'delay_before_read' in params:
            params['delay_before_read'] = params['delay_before_read'] / 1_000_000.0  # µs → s
        return self._scripts.potentiation_depression_cycle(**params)
    
    def potentiation_only(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated SET pulses with reads"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] / 1_000_000.0  # µs → s
        if 'read_width' in params:
            params['read_width'] = params['read_width'] / 1_000_000.0  # µs → s
        if 'delay_before_read' in params:
            params['delay_before_read'] = params['delay_before_read'] / 1_000_000.0  # µs → s
        # post_read_interval is already in seconds from GUI, no conversion needed
        return self._scripts.potentiation_only(**params)
    
    def depression_only(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated RESET pulses with reads"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] / 1_000_000.0  # µs → s
        if 'read_width' in params:
            params['read_width'] = params['read_width'] / 1_000_000.0  # µs → s
        if 'delay_before_read' in params:
            params['delay_before_read'] = params['delay_before_read'] / 1_000_000.0  # µs → s
        # post_read_interval is already in seconds from GUI, no conversion needed
        return self._scripts.depression_only(**params)
    
    def endurance_test(self, **params) -> Dict[str, Any]:
        """Pattern: (SET → Read → RESET → Read) × N cycles"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] / 1_000_000.0  # µs → s
        return self._scripts.endurance_test(**params)
    
    def retention_test(self, **params) -> Dict[str, Any]:
        """Pattern: Pulse → Read @ t1 → Read @ t2 → Read @ t3..."""
        # Not implemented in 4200A scripts yet
        raise NotImplementedError("retention_test not yet implemented for 4200A")
    
    def pulse_multi_read(self, **params) -> Dict[str, Any]:
        """Pattern: N pulses then many reads"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] / 1_000_000.0  # µs → s
        if 'delay_between_reads' in params:
            params['delay_between_reads'] = params['delay_between_reads'] / 1_000_000.0  # µs → s
        return self._scripts.pulse_multi_read(**params)
    
    def multi_read_only(self, **params) -> Dict[str, Any]:
        """Pattern: Just reads, no pulses"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] / 1_000_000.0  # µs → s
        return self._scripts.multi_read_only(**params)
    
    def current_range_finder(self, **params) -> Dict[str, Any]:
        """Find optimal current measurement range"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'delay_between_reads' in params:
            params['delay_between_reads'] = params['delay_between_reads'] / 1_000_000.0  # µs → s
        # Handle current_ranges if it's a string
        if 'current_ranges' in params and isinstance(params['current_ranges'], str):
            params['current_ranges'] = [float(x.strip()) for x in params['current_ranges'].split(",")]
        return self._scripts.current_range_finder(**params)
    
    def relaxation_after_multi_pulse(self, **params) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse → N×Read (measure reads only)"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] / 1_000_000.0  # µs → s
        if 'delay_between_reads' in params:
            params['delay_between_reads'] = params['delay_between_reads'] / 1_000_000.0  # µs → s
        return self._scripts.relaxation_after_multi_pulse(**params)
    
    def relaxation_after_multi_pulse_with_pulse_measurement(self, **params) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse(measured) → N×Read"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] / 1_000_000.0  # µs → s
        if 'delay_between_reads' in params:
            params['delay_between_reads'] = params['delay_between_reads'] / 1_000_000.0  # µs → s
        return self._scripts.relaxation_after_multi_pulse_with_pulse_measurement(**params)
    
    # Additional tests available in 4200A but not in base_system
    # These can be called directly but won't be in the standard interface
    
    def voltage_amplitude_sweep(self, **params) -> Dict[str, Any]:
        """Pattern: For each voltage: Initial Read → (Pulse → Read) × N → Reset"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] / 1_000_000.0  # µs → s
        if 'reset_width' in params:
            params['reset_width'] = params['reset_width'] / 1_000_000.0  # µs → s
        if 'delay_between_voltages' in params:
            # Already in seconds, keep as-is
            pass
        return self._scripts.voltage_amplitude_sweep(**params)
    
    def ispp_test(self, **params) -> Dict[str, Any]:
        """Pattern: Start at low voltage, increase by step each pulse"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] / 1_000_000.0  # µs → s
        return self._scripts.ispp_test(**params)
    
    def switching_threshold_test(self, **params) -> Dict[str, Any]:
        """Pattern: Try increasing voltages, find minimum that causes switching"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] / 1_000_000.0  # µs → s
        return self._scripts.switching_threshold_test(**params)
    
    def multilevel_programming(self, **params) -> Dict[str, Any]:
        """Pattern: For each level: Reset → Program with pulses → Read"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] / 1_000_000.0  # µs → s
        if 'reset_width' in params:
            params['reset_width'] = params['reset_width'] / 1_000_000.0  # µs → s
        if 'delay_between_levels' in params:
            # Already in seconds, keep as-is
            pass
        # Handle target_levels if it's a string
        if 'target_levels' in params and isinstance(params['target_levels'], str):
            params['target_levels'] = [float(x.strip()) for x in params['target_levels'].split(",")]
        return self._scripts.multilevel_programming(**params)
    
    def pulse_train_varying_amplitudes(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert µs to seconds (KXCI scripts expect seconds, not microseconds)
        # GUI sends these in µs, convert to seconds for KXCI scripts
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] / 1_000_000.0  # µs → s
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] / 1_000_000.0  # µs → s
        # Handle pulse_voltages if it's a string
        if 'pulse_voltages' in params and isinstance(params['pulse_voltages'], str):
            params['pulse_voltages'] = [float(x.strip()) for x in params['pulse_voltages'].split(",")]
        return self._scripts.pulse_train_varying_amplitudes(**params)
    
    def laser_and_read(self, **params) -> Dict[str, Any]:
        """Pattern: CH1 continuous reads, CH2 independent laser pulse
        
        ⚠️ IMPORTANT: You MUST reconfigure coax cables before running this test.
        CH2 laser voltage is limited to 2.0V maximum to prevent laser damage.
        """
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Note: For 4200A, the GUI already converts these to µs:
        # - read_width → µs (via read_pulse_params)
        # - read_period, laser_width, laser_delay, laser_rise_time, laser_fall_time → µs (via laser_params)
        # So NO conversion needed here - they're already in the correct units
        return self._scripts.laser_and_read(**params)
    
    def cyclical_iv_sweep(self, **params) -> Dict[str, Any]:
        """Cyclical IV sweep: (0V → +Vpos → Vneg → 0V) × N cycles
        
        Uses the smu_ivsweep C module via KXCI. This method uses SMU1 for measurements.
        
        Args:
            vpos: Positive voltage (V), must be >= 0
            vneg: Negative voltage (V), must be <= 0. If 0, automatically uses -Vpos for symmetric sweep
            num_cycles: Number of cycles (1-1000). Each cycle: 0V → +Vpos → Vneg → 0V
            settle_time: Settling time at each voltage point (seconds), default 0.001 (1 ms)
            ilimit: Current compliance limit (A), default 0.1
            integration_time: Measurement integration time (PLC - Power Line Cycles), default 0.01
            debug: Enable debug output (0 or 1), default 0
            
        Returns:
            Dict with keys:
                - 'voltage': List of measured voltages (V)
                - 'current': List of measured currents (A)
                - 'resistance': List of calculated resistances (Ω)
                - 'timestamp': List of timestamps (s)
                - 'vpos': Positive voltage used (V)
                - 'vneg': Negative voltage used (V)
                - 'num_cycles': Number of cycles executed
                - 'total_points': Total number of points (4 × num_cycles)
        
        Raises:
            RuntimeError: If not connected or execution fails
            ValueError: If parameters are invalid
        """
        if not self._scripts:
            raise RuntimeError("Not connected")
        
        # Import cyclical IV sweep functions (conditional import)
        # Using importlib to avoid issues with directory names starting with numbers
        try:
            import importlib
            _smu_iv_sweep_module = importlib.import_module('Equipment.SMU_AND_PMU.4200A.C_Code_with_python_scripts.A_Iv_Sweep.run_smu_vi_sweep')
            KXCIClient = _smu_iv_sweep_module.KXCIClient
            build_ex_command = _smu_iv_sweep_module.build_ex_command
            format_param = _smu_iv_sweep_module.format_param
        except (ImportError, AttributeError) as e:
            raise RuntimeError(
                f"Cyclical IV sweep module not available: {e}. "
                "Please ensure Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/A_Iv_Sweep/run_smu_vi_sweep.py exists."
            ) from e
        
        # Extract parameters with defaults
        vpos = float(params.get('vpos', 2.0))
        vneg = float(params.get('vneg', 0.0))
        num_cycles = int(params.get('num_cycles', 1))
        settle_time = float(params.get('settle_time', 0.001))
        ilimit = float(params.get('ilimit', 0.1))
        integration_time = float(params.get('integration_time', 0.01))
        debug = int(params.get('debug', 0))
        
        # Validate parameters
        if vpos < 0:
            raise ValueError(f"vpos={vpos} must be >= 0")
        if vneg > 0:
            raise ValueError(f"vneg={vneg} must be <= 0 (use 0 for auto-symmetric with -vpos)")
        if not (1 <= num_cycles <= 1000):
            raise ValueError(f"num_cycles={num_cycles} must be in range [1, 1000]")
        
        # Calculate total points (4 points per cycle)
        num_points = 4 * num_cycles
        
        # Build EX command
        clarius_debug = debug
        command = build_ex_command(
            vpos=vpos,
            vneg=vneg,
            num_cycles=num_cycles,
            num_points=num_points,
            settle_time=settle_time,
            ilimit=ilimit,
            integration_time=integration_time,
            clarius_debug=clarius_debug,
        )
        
        # Get GPIB address from scripts (should be available)
        gpib_address = self._address if self._address else "GPIB0::17::INSTR"
        
        # Create KXCI client and execute
        kxci_client = KXCIClient(gpib_address=gpib_address, timeout=self._timeout)
        
        if not kxci_client.connect():
            raise RuntimeError("Failed to connect to instrument for cyclical IV sweep")
        
        try:
            if not kxci_client._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode for cyclical IV sweep")
            
            # Execute EX command
            result = kxci_client._execute_ex_command(command)
            
            if result != 0:
                raise RuntimeError(f"EX command failed with error code: {result}")
            
            # Retrieve data from GP parameters
            # GP 4 = Imeas, GP 6 = Vforce (as per C module metadata)
            imeas = kxci_client._query_gp_data(4, num_points)
            vforce = kxci_client._query_gp_data(6, num_points)
            
            # Filter out trailing zeros (C module may allocate more space than used)
            valid_len = num_points
            for i in range(len(imeas) - 1, -1, -1):
                if imeas[i] == 0.0 and vforce[i] == 0.0:
                    valid_len = i
                else:
                    break
            
            imeas = imeas[:valid_len]
            vforce = vforce[:valid_len]
            
            # Generate timestamps (approximate, based on settle_time)
            timestamps = [i * settle_time * 2.0 for i in range(len(imeas))]  # Approximate: 2×settle_time per point
            
            # Calculate resistance
            resistance = []
            for i in range(len(imeas)):
                if abs(imeas[i]) > 1e-15:  # Avoid division by zero
                    r = vforce[i] / imeas[i]
                    resistance.append(r)
                else:
                    resistance.append(float('inf'))
            
            return {
                'voltage': vforce.tolist() if hasattr(vforce, 'tolist') else list(vforce),
                'current': imeas.tolist() if hasattr(imeas, 'tolist') else list(imeas),
                'resistance': resistance,
                'timestamp': timestamps,
                'vpos': vpos,
                'vneg': -vpos if vneg == 0.0 else vneg,
                'num_cycles': num_cycles,
                'total_points': len(imeas),
            }
            
        finally:
            try:
                kxci_client._exit_ul_mode()
                kxci_client.disconnect()
            except Exception:
                pass