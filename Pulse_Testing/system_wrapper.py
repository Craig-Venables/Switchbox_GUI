"""
System Wrapper - Test Routing and System Detection
==================================================

Main wrapper class that:
1. Detects measurement system from device address
2. Routes test function calls to appropriate system implementation
3. Normalizes return data to standard format
4. Handles errors gracefully
"""

from typing import Dict, Any, Optional, Type
from .systems.base_system import BaseMeasurementSystem
from .systems.keithley2450 import Keithley2450System
from .systems.keithley4200a import Keithley4200ASystem
from .test_capabilities import is_test_supported
from .utils.data_formatter import normalize_data, ensure_list_format


# Map of system names to their implementation classes
SYSTEM_CLASSES: Dict[str, Type[BaseMeasurementSystem]] = {
    'keithley2450': Keithley2450System,
    'keithley4200a': Keithley4200ASystem,
}


def get_default_address_for_system(system_name: str) -> Optional[str]:
    """Get default device address for a system.
    
    Args:
        system_name: System identifier
    
    Returns:
        Default address string or None if not available
    """
    if system_name not in SYSTEM_CLASSES:
        return None
    
    system_class = SYSTEM_CLASSES[system_name]
    if hasattr(system_class, 'get_default_address'):
        return system_class.get_default_address()
    
    return None


def detect_system_from_address(address: str) -> Optional[str]:
    """Detect measurement system type from device address.
    
    Args:
        address: Device address string
    
    Returns:
        System identifier ('keithley2450', 'keithley4200a', etc.) or None if unknown
    
    Detection logic:
    - USB/GPIB addresses containing "2450" → keithley2450
    - IP:port format (e.g., "192.168.0.10:8888") → keithley4200a
    - GPIB addresses → try keithley2450 as default
    """
    address_lower = address.lower().strip()
    
    # Check for 2450 indicators
    if '2450' in address_lower:
        return 'keithley2450'
    
    # Check for 4200A indicators (IP:port format)
    if ':' in address and not address_lower.startswith(('usb', 'gpib', 'tcpip')):
        # Simple IP:port pattern (e.g., "192.168.0.10:8888")
        # More sophisticated: check if it looks like IP address
        parts = address.split(':')
        if len(parts) == 2:
            try:
                # Try to parse as IP:port
                ip_part = parts[0].strip()
                port_part = parts[1].strip()
                # Check if IP part looks like IP address
                ip_parts = ip_part.split('.')
                if len(ip_parts) == 4 and all(p.isdigit() for p in ip_parts):
                    if port_part.isdigit():
                        return 'keithley4200a'
            except:
                pass
    
    # Check for explicit TCPIP format (could be either, default to 2450)
    if address_lower.startswith('tcpip'):
        # TCPIP could be either system, default to 2450 unless we detect otherwise
        if '4200' in address_lower:
            return 'keithley4200a'
        return 'keithley2450'
    
    # Default: assume 2450 for USB/GPIB addresses
    if address_lower.startswith(('usb', 'gpib')):
        return 'keithley2450'
    
    # Unknown format - return None (caller should handle)
    return None


class SystemWrapper:
    """Main wrapper for routing test calls to appropriate measurement systems."""
    
    def __init__(self):
        """Initialize the wrapper (no connection yet)."""
        self.current_system: Optional[BaseMeasurementSystem] = None
        self.system_name: Optional[str] = None
    
    def connect(self, address: str, system_name: Optional[str] = None, **kwargs) -> str:
        """Connect to a measurement system.
        
        Args:
            address: Device address
            system_name: Optional system identifier (if None, auto-detect)
            **kwargs: Additional connection parameters (terminals, timeout, etc.)
        
        Returns:
            Detected/used system name
        
        Raises:
            ValueError: If system cannot be determined or is unsupported
            ConnectionError: If connection fails
        """
        # Auto-detect system if not provided
        if system_name is None:
            detected = detect_system_from_address(address)
            if detected is None:
                raise ValueError(
                    f"Cannot determine measurement system from address: {address}\n"
                    f"Please specify system manually or use a recognized address format."
                )
            system_name = detected
        
        # Check if system is supported
        if system_name not in SYSTEM_CLASSES:
            raise ValueError(f"Unsupported measurement system: {system_name}")
        
        # Create and connect system instance
        system_class = SYSTEM_CLASSES[system_name]
        system_instance = system_class()
        
        # Handle system-specific connection parameters
        if system_name == 'keithley2450':
            # Extract terminals parameter if present
            terminals = kwargs.pop('terminals', 'front')
            system_instance.connect(address, terminals=terminals, **kwargs)
        else:
            # For other systems, pass all kwargs
            system_instance.connect(address, **kwargs)
        
        self.current_system = system_instance
        self.system_name = system_name
        
        return system_name
    
    def disconnect(self) -> None:
        """Disconnect from current system."""
        if self.current_system:
            try:
                self.current_system.disconnect()
            except:
                pass
            self.current_system = None
            self.system_name = None
    
    def is_connected(self) -> bool:
        """Check if a system is connected."""
        return self.current_system is not None and self.current_system.is_connected()
    
    def get_current_system_name(self) -> Optional[str]:
        """Get name of currently connected system."""
        return self.system_name
    
    def get_idn(self) -> str:
        """Get instrument identification."""
        if self.current_system:
            return self.current_system.get_idn()
        return "No system connected"
    
    def get_hardware_limits(self) -> Dict[str, Any]:
        """Get hardware limits for current system."""
        if self.current_system:
            return self.current_system.get_hardware_limits()
        return {}
    
    def run_test(self, test_function: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a test function on the current system.
        
        This is the main routing function - all test calls go through here.
        
        Args:
            test_function: Test function name (e.g., 'pulse_read_repeat')
            params: Test parameters dictionary
        
        Returns:
            Standardized data dictionary with timestamps, voltages, currents, resistances
        
        Raises:
            RuntimeError: If not connected or test not supported
            NotImplementedError: If test not implemented for current system
            Exception: Other errors from test execution
        """
        if not self.current_system:
            raise RuntimeError("No measurement system connected")
        
        if not self.is_connected():
            raise RuntimeError("Measurement system not connected")
        
        # Check if test is supported
        if not is_test_supported(self.system_name, test_function):
            raise RuntimeError(
                f"Test '{test_function}' is not supported by {self.system_name}. "
                f"Check test_capabilities.py to enable support."
            )
        
        # Get the test method from the system
        if not hasattr(self.current_system, test_function):
            raise RuntimeError(
                f"Test method '{test_function}' not found in {self.system_name} implementation"
            )
        
        test_method = getattr(self.current_system, test_function)
        
        # Execute test
        try:
            result = test_method(**params)
        except NotImplementedError as e:
            raise RuntimeError(
                f"Test '{test_function}' not yet implemented for {self.system_name}: {e}"
            ) from e
        
        # Normalize and validate data format
        try:
            normalized = normalize_data(result)
            # Convert numpy arrays to lists for GUI compatibility
            return ensure_list_format(normalized)
        except ValueError as e:
            raise RuntimeError(
                f"Invalid data format returned from {test_function}: {e}\n"
                f"Expected format: {{'timestamps': [...], 'voltages': [...], 'currents': [...], 'resistances': [...]}}"
            ) from e


# Global instance for easy access (can be instantiated per-GUI if needed)
_default_wrapper = SystemWrapper()


def get_default_wrapper() -> SystemWrapper:
    """Get the default global system wrapper instance."""
    return _default_wrapper

