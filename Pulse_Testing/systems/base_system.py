"""
Base Measurement System Interface
=================================

Abstract base class for all measurement systems. Implementations (adapters) live in
Pulse_Testing/systems/ (keithley2400.py, keithley2450.py, keithley4200_*.py); each
delegates to script modules in Equipment/SMU_AND_PMU/<instrument>/.
See Pulse_Testing/README.md and Equipment/SMU_AND_PMU/README.md for unified layout.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class BaseMeasurementSystem(ABC):
    """Abstract base class for measurement system implementations.
    
    All measurement systems must inherit from this class and implement
    all abstract methods. This ensures consistent interface across systems.
    
    Standard Return Format:
    -----------------------
    All test methods must return a dictionary with:
        {
            'timestamps': List[float],      # Time in seconds
            'voltages': List[float],        # Voltage in volts
            'currents': List[float],        # Current in amps
            'resistances': List[float],     # Resistance in ohms
            # Optional extra fields (test-specific):
            'phase': List[str],             # For pot/dep cycles
            'pulse_widths': List[float],    # For width sweeps
            'cycle_number': List[int],       # For endurance tests
            'operation': List[str],          # For endurance tests
            'range_values': List[float],     # For range finder
            'range_stats': List[dict],      # For range finder
            'recommended_range': float,      # For range finder
            # ... etc
        }
    """
    
    @abstractmethod
    def get_system_name(self) -> str:
        """Return the system identifier name (e.g., 'keithley2450', 'keithley4200_pmu')."""
        pass
    
    @abstractmethod
    def get_hardware_limits(self) -> Dict[str, Any]:
        """Return hardware capability limits.
        
        Returns:
            Dict with keys like:
            - 'min_pulse_width': float (seconds)
            - 'max_pulse_width': float (seconds)
            - 'max_voltage': float (volts)
            - 'max_current_limit': float (amps)
            - 'min_current_limit': float (amps)
            - etc.
        """
        pass
    
    @abstractmethod
    def connect(self, address: str, **kwargs) -> bool:
        """Connect to the measurement system.
        
        Args:
            address: System-specific address string
            **kwargs: Additional connection parameters (terminals, timeout, etc.)
        
        Returns:
            True if connection successful, False otherwise
        
        Raises:
            ConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the measurement system."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if system is currently connected.
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    def get_idn(self) -> str:
        """Get instrument identification string."""
        pass
    
    # Test methods - all must return standardized format
    @abstractmethod
    def pulse_read_repeat(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → (Pulse → Read → Delay) × N"""
        pass
    
    @abstractmethod
    def pulse_then_read(self, **params) -> Dict[str, Any]:
        """Pattern: (Pulse → Delay → Read) × N"""
        pass
    
    @abstractmethod
    def multi_pulse_then_read(self, **params) -> Dict[str, Any]:
        """Pattern: (Pulse×N → Read×M) × Cycles"""
        pass
    
    @abstractmethod
    def varying_width_pulses(self, **params) -> Dict[str, Any]:
        """Test multiple pulse widths"""
        pass
    
    @abstractmethod
    def width_sweep_with_reads(self, **params) -> Dict[str, Any]:
        """Width sweep: For each width: (Read→Pulse→Read)×N, Reset"""
        pass
    
    @abstractmethod
    def width_sweep_with_all_measurements(self, **params) -> Dict[str, Any]:
        """Width sweep with pulse peak measurements"""
        pass
    
    @abstractmethod
    def potentiation_depression_cycle(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Gradual SET → Gradual RESET"""
        pass
    
    @abstractmethod
    def potentiation_only(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated SET pulses with reads"""
        pass
    
    @abstractmethod
    def depression_only(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated RESET pulses with reads"""
        pass
    
    @abstractmethod
    def endurance_test(self, **params) -> Dict[str, Any]:
        """Pattern: (SET → Read → RESET → Read) × N cycles"""
        pass
    
    @abstractmethod
    def retention_test(self, **params) -> Dict[str, Any]:
        """Pattern: Pulse → Read @ t1 → Read @ t2 → Read @ t3..."""
        pass
    
    @abstractmethod
    def pulse_multi_read(self, **params) -> Dict[str, Any]:
        """Pattern: N pulses then many reads"""
        pass
    
    @abstractmethod
    def multi_read_only(self, **params) -> Dict[str, Any]:
        """Pattern: Just reads, no pulses"""
        pass
    
    @abstractmethod
    def current_range_finder(self, **params) -> Dict[str, Any]:
        """Find optimal current measurement range"""
        pass
    
    @abstractmethod
    def relaxation_after_multi_pulse(self, **params) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse → N×Read (measure reads only)"""
        pass
    
    @abstractmethod
    def relaxation_after_multi_pulse_with_pulse_measurement(self, **params) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse(measured) → N×Read"""
        pass
    
    # Optional additional tests (not all systems support these)
    # These are not abstract - systems can implement them if supported
    
    def voltage_amplitude_sweep(self, **params) -> Dict[str, Any]:
        """Pattern: For each voltage: Initial Read → (Pulse → Read) × N → Reset
        
        Optional test - not all systems support this.
        """
        raise NotImplementedError("voltage_amplitude_sweep not implemented for this system")
    
    def ispp_test(self, **params) -> Dict[str, Any]:
        """Pattern: Start at low voltage, increase by step each pulse
        
        Optional test - not all systems support this.
        """
        raise NotImplementedError("ispp_test not implemented for this system")
    
    def switching_threshold_test(self, **params) -> Dict[str, Any]:
        """Pattern: Try increasing voltages, find minimum that causes switching
        
        Optional test - not all systems support this.
        """
        raise NotImplementedError("switching_threshold_test not implemented for this system")
    
    def multilevel_programming(self, **params) -> Dict[str, Any]:
        """Pattern: For each level: Reset → Program with pulses → Read
        
        Optional test - not all systems support this.
        """
        raise NotImplementedError("multilevel_programming not implemented for this system")
    
    def pulse_train_varying_amplitudes(self, **params) -> Dict[str, Any]:
        """Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N
        
        Optional test - not all systems support this.
        """
        raise NotImplementedError("pulse_train_varying_amplitudes not implemented for this system")
    
    @staticmethod
    def _pattern_to_pulse_voltages(params: Dict[str, Any]) -> Dict[str, Any]:
        """Turn the GUI's Electrical Pulse Train fields into the scripts' ``pulse_voltages`` list.

        ``pulse_pattern`` "11010" with ``pulse_voltage`` 1.5 → [1.5, 1.5, 0.0, 1.5, 0.0];
        the pattern repeats to fill ``num_pulses`` slots. An explicit ``pulse_voltages`` wins.
        """
        out = dict(params)
        pattern = str(out.pop("pulse_pattern", "") or "")
        num_pulses = out.pop("num_pulses", None)
        amplitude = out.pop("pulse_voltage", None)
        if isinstance(out.get("pulse_voltages"), str):
            out["pulse_voltages"] = [float(x) for x in out["pulse_voltages"].split(",") if x.strip()]
        if out.get("pulse_voltages") or amplitude is None:
            return out
        bits = [c for c in pattern if c in "01"] or ["1"]
        slots = int(num_pulses) if num_pulses else len(bits)
        out["pulse_voltages"] = [
            float(amplitude) if bits[k % len(bits)] == "1" else 0.0 for k in range(slots)
        ]
        return out

    def _format_results(self, timestamps: List[float], voltages: List[float], 
                       currents: List[float], resistances: List[float],
                       **extras) -> Dict[str, Any]:
        """Helper method to format results into standardized dict.
        
        Subclasses can use this to ensure consistent format.
        """
        result = {
            'timestamps': timestamps,
            'voltages': voltages,
            'currents': currents,
            'resistances': resistances
        }
        result.update(extras)
        return result

