"""
Keithley 2450 Measurement System Adapter
=========================================

Wraps Keithley2450_TSP_Scripts to provide standardized interface
for the Pulse Testing architecture.
"""

from typing import Dict, List, Any, Optional
from .base_system import BaseMeasurementSystem

# Import the actual implementation - use backward-compatible imports
from Equipment.SMU_AND_PMU import (
    Keithley2450_TSP,
    Keithley2450_TSP_Sim,
    keithley2450_tsp_scripts,
    keithley2450_tsp_sim_scripts,
)

# Extract the script classes and constants
try:
    Keithley2450_TSP_Scripts = keithley2450_tsp_scripts.Keithley2450_TSP_Scripts
    # Extract constants from the module
    MIN_PULSE_WIDTH = keithley2450_tsp_scripts.MIN_PULSE_WIDTH
    MAX_PULSE_WIDTH = keithley2450_tsp_scripts.MAX_PULSE_WIDTH
    MAX_VOLTAGE = keithley2450_tsp_scripts.MAX_VOLTAGE
    MIN_CURRENT_LIMIT = keithley2450_tsp_scripts.MIN_CURRENT_LIMIT
    MAX_CURRENT_LIMIT = keithley2450_tsp_scripts.MAX_CURRENT_LIMIT
except AttributeError:
    # Fallback if constants not available
    Keithley2450_TSP_Scripts = None
    MIN_PULSE_WIDTH = 1e-3
    MAX_PULSE_WIDTH = 10.0
    MAX_VOLTAGE = 5.0
    MIN_CURRENT_LIMIT = 1e-6
    MAX_CURRENT_LIMIT = 1.0

try:
    Keithley2450_TSP_Sim_Scripts = keithley2450_tsp_sim_scripts.Keithley2450_TSP_Sim_Scripts
except AttributeError:
    Keithley2450_TSP_Sim_Scripts = None


class Keithley2450System(BaseMeasurementSystem):
    """Adapter for Keithley 2450 TSP measurement system."""
    
    # Default device address for this system
    DEFAULT_ADDRESS = "USB0::0x05E6::0x2450::04496615::INSTR"
    
    def __init__(self):
        """Initialize the 2450 system (connection happens later)."""
        self.tsp_controller: Optional[Keithley2450_TSP] = None
        self.test_scripts: Optional[Keithley2450_TSP_Scripts] = None
        self._connected = False
    
    @classmethod
    def get_default_address(cls) -> str:
        """Get default device address for this system."""
        return cls.DEFAULT_ADDRESS
    
    def get_system_name(self) -> str:
        """Return system identifier."""
        return 'keithley2450'
    
    def get_hardware_limits(self) -> Dict[str, Any]:
        """Return hardware capability limits."""
        return {
            'min_pulse_width': MIN_PULSE_WIDTH,
            'max_pulse_width': MAX_PULSE_WIDTH,
            'min_voltage': 0.0,
            'max_voltage': MAX_VOLTAGE,
            'min_current_limit': MIN_CURRENT_LIMIT,
            'max_current_limit': MAX_CURRENT_LIMIT,
        }
    
    def connect(self, address: str, terminals: str = 'front', timeout: int = 10000, **kwargs) -> bool:
        """Connect to Keithley 2450 TSP.
        
        Args:
            address: Device address (USB/GPIB/LAN)
            terminals: 'front' or 'rear' terminal selection
            timeout: Communication timeout in milliseconds
            **kwargs: Additional connection parameters (ignored for 2450)
        
        Returns:
            True if connection successful
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            self.tsp_controller = Keithley2450_TSP(address, timeout=timeout, terminals=terminals)
            self.test_scripts = Keithley2450_TSP_Scripts(self.tsp_controller)
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to Keithley 2450: {e}") from e
    
    def disconnect(self) -> None:
        """Disconnect from Keithley 2450."""
        if self.tsp_controller:
            try:
                self.tsp_controller.close()
            except:
                pass
            self.tsp_controller = None
            self.test_scripts = None
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if system is connected."""
        return self._connected and self.tsp_controller is not None and self.test_scripts is not None
    
    def get_idn(self) -> str:
        """Get instrument identification."""
        if self.tsp_controller:
            return self.tsp_controller.get_idn()
        return "Not Connected"
    
    # Delegate all test methods to the underlying test_scripts object
    # All methods must return standardized format (already done by TSP scripts)
    
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
        return self.test_scripts.retention_test(**params)
    
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
    
    # Optional additional tests (also available in 2450)
    
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


class Keithley2450SimSystem(Keithley2450System):
    """Adapter that routes tests to the in-memory Keithley 2450 simulator."""

    DEFAULT_ADDRESS = "SIM::KEITHLEY2450"

    def get_system_name(self) -> str:
        return 'keithley2450_sim'

    def connect(self, address: str, terminals: str = 'front', timeout: int = 10000, **kwargs) -> bool:
        try:
            self.tsp_controller = Keithley2450_TSP_Sim(address, timeout=timeout, terminals=terminals)
            self.test_scripts = Keithley2450_TSP_Sim_Scripts(self.tsp_controller)
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to initialize Keithley 2450 simulation: {e}") from e

