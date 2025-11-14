"""
Keithley 4200A Measurement System Implementation
==================================================

Implementation for Keithley 4200A measurement system using KXCI scripts.
Integrates with keithley4200_kxci_scripts.py for all test functions.
"""

from typing import Dict, List, Any, Optional
from .base_system import BaseMeasurementSystem
from Equipment.SMU_AND_PMU.keithley4200_kxci_scripts import (
    Keithley4200_KXCI_Scripts,
    MIN_PULSE_WIDTH,
    MAX_PULSE_WIDTH,
    MIN_VOLTAGE,
    MAX_VOLTAGE,
    MIN_CURRENT_RANGE,
    MAX_CURRENT_RANGE,
    MAX_MAX_POINTS,
)


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
            'max_points': MAX_MAX_POINTS,        # 30,000 (C module hard limit)
            'min_sampling_rate': 200000,         # samples/second (C module requirement)
            'max_measurement_time': 0.15,        # ~150ms (calculated from max_points/min_rate)
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
        # Convert ms to µs for 4200A scripts (they expect µs)
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0  # ms → µs
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0  # ms → µs
        return self._scripts.pulse_read_repeat(**params)
    
    def pulse_then_read(self, **params) -> Dict[str, Any]:
        """Pattern: (Pulse → Delay → Read) × N"""
        # Not implemented in 4200A scripts - use pulse_read_repeat instead
        raise NotImplementedError("pulse_then_read not available for 4200A - use pulse_read_repeat")
    
    def multi_pulse_then_read(self, **params) -> Dict[str, Any]:
        """Pattern: (Pulse×N → Read×M) × Cycles"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] * 1000.0
        if 'delay_between_reads' in params:
            params['delay_between_reads'] = params['delay_between_reads'] * 1000.0
        if 'delay_between_cycles' in params:
            params['delay_between_cycles'] = params['delay_between_cycles'] * 1000.0
        return self._scripts.multi_pulse_then_read(**params)
    
    def varying_width_pulses(self, **params) -> Dict[str, Any]:
        """Test multiple pulse widths"""
        # Not directly available - use width_sweep_with_reads instead
        raise NotImplementedError("varying_width_pulses not available for 4200A - use width_sweep_with_reads")
    
    def width_sweep_with_reads(self, **params) -> Dict[str, Any]:
        """Width sweep: For each width: (Read→Pulse→Read)×N, Reset"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert pulse_widths from seconds (GUI) to µs (4200A scripts)
        if 'pulse_widths' in params:
            if isinstance(params['pulse_widths'], str):
                # Comma-separated string
                widths = [float(x.strip()) for x in params['pulse_widths'].split(",")]
            else:
                widths = params['pulse_widths']
            # Convert from seconds to µs
            params['pulse_widths'] = [w * 1e6 for w in widths]
        if 'reset_width' in params:
            params['reset_width'] = params['reset_width'] * 1e6  # s → µs
        if 'delay_between_widths' in params:
            # Already in seconds, keep as-is
            pass
        return self._scripts.width_sweep_with_reads(**params)
    
    def width_sweep_with_all_measurements(self, **params) -> Dict[str, Any]:
        """Width sweep with pulse peak measurements"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert pulse_widths from seconds to µs
        if 'pulse_widths' in params:
            if isinstance(params['pulse_widths'], str):
                widths = [float(x.strip()) for x in params['pulse_widths'].split(",")]
            else:
                widths = params['pulse_widths']
            params['pulse_widths'] = [w * 1e6 for w in widths]
        if 'reset_width' in params:
            params['reset_width'] = params['reset_width'] * 1e6
        return self._scripts.width_sweep_with_all_measurements(**params)
    
    def potentiation_depression_cycle(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Gradual SET → Gradual RESET"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        return self._scripts.potentiation_depression_cycle(**params)
    
    def potentiation_only(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated SET pulses with reads"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        if 'post_read_interval' in params:
            params['post_read_interval'] = params['post_read_interval'] * 1000.0
        if 'delay_between_cycles' in params:
            # Already in seconds, keep as-is
            pass
        return self._scripts.potentiation_only(**params)
    
    def depression_only(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated RESET pulses with reads"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        if 'post_read_interval' in params:
            params['post_read_interval'] = params['post_read_interval'] * 1000.0
        if 'delay_between_cycles' in params:
            # Already in seconds, keep as-is
            pass
        return self._scripts.depression_only(**params)
    
    def endurance_test(self, **params) -> Dict[str, Any]:
        """Pattern: (SET → Read → RESET → Read) × N cycles"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        return self._scripts.endurance_test(**params)
    
    def retention_test(self, **params) -> Dict[str, Any]:
        """Pattern: Pulse → Read @ t1 → Read @ t2 → Read @ t3..."""
        # Not implemented in 4200A scripts yet
        raise NotImplementedError("retention_test not yet implemented for 4200A")
    
    def pulse_multi_read(self, **params) -> Dict[str, Any]:
        """Pattern: N pulses then many reads"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] * 1000.0
        if 'delay_between_reads' in params:
            params['delay_between_reads'] = params['delay_between_reads'] * 1000.0
        return self._scripts.pulse_multi_read(**params)
    
    def multi_read_only(self, **params) -> Dict[str, Any]:
        """Pattern: Just reads, no pulses"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        return self._scripts.multi_read_only(**params)
    
    def current_range_finder(self, **params) -> Dict[str, Any]:
        """Find optimal current measurement range"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'delay_between_reads' in params:
            params['delay_between_reads'] = params['delay_between_reads'] * 1000.0
        # Handle current_ranges if it's a string
        if 'current_ranges' in params and isinstance(params['current_ranges'], str):
            params['current_ranges'] = [float(x.strip()) for x in params['current_ranges'].split(",")]
        return self._scripts.current_range_finder(**params)
    
    def relaxation_after_multi_pulse(self, **params) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse → N×Read (measure reads only)"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] * 1000.0
        if 'delay_between_reads' in params:
            params['delay_between_reads'] = params['delay_between_reads'] * 1000.0
        return self._scripts.relaxation_after_multi_pulse(**params)
    
    def relaxation_after_multi_pulse_with_pulse_measurement(self, **params) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse(measured) → N×Read"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between_pulses' in params:
            params['delay_between_pulses'] = params['delay_between_pulses'] * 1000.0
        if 'delay_between_reads' in params:
            params['delay_between_reads'] = params['delay_between_reads'] * 1000.0
        return self._scripts.relaxation_after_multi_pulse_with_pulse_measurement(**params)
    
    # Additional tests available in 4200A but not in base_system
    # These can be called directly but won't be in the standard interface
    
    def voltage_amplitude_sweep(self, **params) -> Dict[str, Any]:
        """Pattern: For each voltage: Initial Read → (Pulse → Read) × N → Reset"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        if 'reset_width' in params:
            params['reset_width'] = params['reset_width'] * 1000.0
        if 'delay_between_voltages' in params:
            # Already in seconds, keep as-is
            pass
        return self._scripts.voltage_amplitude_sweep(**params)
    
    def ispp_test(self, **params) -> Dict[str, Any]:
        """Pattern: Start at low voltage, increase by step each pulse"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        return self._scripts.ispp_test(**params)
    
    def switching_threshold_test(self, **params) -> Dict[str, Any]:
        """Pattern: Try increasing voltages, find minimum that causes switching"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        return self._scripts.switching_threshold_test(**params)
    
    def multilevel_programming(self, **params) -> Dict[str, Any]:
        """Pattern: For each level: Reset → Program with pulses → Read"""
        if not self._scripts:
            raise RuntimeError("Not connected")
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        if 'reset_width' in params:
            params['reset_width'] = params['reset_width'] * 1000.0
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
        # Convert ms to µs
        if 'pulse_width' in params:
            params['pulse_width'] = params['pulse_width'] * 1000.0
        if 'delay_between' in params:
            params['delay_between'] = params['delay_between'] * 1000.0
        # Handle pulse_voltages if it's a string
        if 'pulse_voltages' in params and isinstance(params['pulse_voltages'], str):
            params['pulse_voltages'] = [float(x.strip()) for x in params['pulse_voltages'].split(",")]
        return self._scripts.pulse_train_varying_amplitudes(**params)
