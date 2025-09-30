"""
Ammeter Controller Manager

This module provides a unified interface for managing different ammeter types,
specifically designed to work with the Agilent 34401A Digital Multimeter.
Similar to the temperature_controller_manager.py and iv_controller_manager.py patterns.

Author: Generated for Switchbox_GUI project
"""

import time
import pyvisa
from typing import Optional, Dict, Any, Union, List, Tuple

# Import the Agilent34401A class
try:
    from Equipment.Ammeter.Aligent_A import Agilent34401A
except ModuleNotFoundError:
    # Allow running this file directly by adding project root to sys.path
    import os
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from Equipment.Ammeter.Aligent_A import Agilent34401A


class AmmeterControllerManager:
    """
    Manager class that automatically detects and manages ammeters.
    Currently supports Agilent 34401A Digital Multimeter via GPIB.
    
    Provides a unified interface for different ammeter types with:
    - Auto-detection of connected devices
    - Manual initialization with specific addresses
    - Caching for improved performance
    - Unified API for measurement operations
    """

    # Controller configurations
    CONTROLLER_CONFIGS = [
        {
            'class': Agilent34401A,
            'type': 'GPIB',
            'addresses': [22, 21, 23],  # Common GPIB addresses, with 22 as primary
            'name': 'Agilent 34401A',
            'test_method': 'read_measurement',
            'address_format': 'GPIB0::{address}::INSTR'
        }
    ]

    def __init__(self, auto_detect: bool = True, controller_type: Optional[str] = None,
                 address: Optional[Union[str, int]] = None):
        """
        Initialize the ammeter controller manager.

        Args:
            auto_detect: If True, automatically detect connected ammeter
            controller_type: Manual controller type ('Agilent34401A')
            address: Manual address (GPIB number or full VISA address)
        """
        self.controller = None
        self.controller_type = None
        self.controller_config = None
        self.address = None

        # Measurement caching
        self.last_measurements = {
            'dc_voltage': 0.0,
            'ac_voltage': 0.0,
            'dc_current': 0.0,
            'ac_current': 0.0,
            'resistance': 0.0,
            'frequency': 0.0
        }
        self.last_read_time = 0
        self.cache_duration = 0.5  # Cache for 0.5 seconds to reduce communication

        if auto_detect:
            self.auto_detect_controller()
        elif controller_type and address:
            self.manual_init_controller(controller_type, address)

    def auto_detect_controller(self) -> bool:
        """
        Automatically detect which ammeter is connected.

        Returns:
            bool: True if ammeter found, False otherwise
        """
        print("Scanning for ammeters...")

        # Try each controller type
        for config in self.CONTROLLER_CONFIGS:
            controller_class = config['class']

            for address in config['addresses']:
                print(f"Trying {config['name']} at GPIB {address}...", end=' ')

                try:
                    # Format address based on type
                    if config['type'] == 'GPIB':
                        visa_address = config['address_format'].format(address=address)
                    else:
                        visa_address = str(address)

                    # Initialize controller
                    controller = controller_class(visa_address=visa_address)

                    # Test the connection
                    if controller.connected:
                        # Try to read a measurement to verify functionality
                        test_reading = controller.read_measurement()
                        
                        if test_reading is not None:
                            self.controller = controller
                            self.controller_type = config['name']
                            self.controller_config = config
                            self.address = visa_address

                            print(f"✓ Success!")
                            print(f"Connected to {config['name']} at {visa_address}")
                            print(f"Test reading: {test_reading:.6f}")
                            return True
                        else:
                            controller.disconnect()
                            print("✗ (No valid reading)")
                    else:
                        print("✗ (Connection failed)")

                except Exception as e:
                    print(f"✗ ({str(e)[:30]}...)")
                    continue

        print("No ammeter detected. Using default values.")
        return False

    def manual_init_controller(self, controller_type: str, address: Union[str, int]) -> bool:
        """
        Manually initialize a specific ammeter controller.

        Args:
            controller_type: 'Agilent34401A' or similar
            address: GPIB address (e.g., 22) or full VISA address

        Returns:
            bool: True if successful, False otherwise
        """
        # Find matching config
        config = None
        for cfg in self.CONTROLLER_CONFIGS:
            if controller_type in cfg['name'] or controller_type.replace(' ', '') in cfg['name'].replace(' ', ''):
                config = cfg
                break

        if not config:
            print(f"Unknown controller type: {controller_type}")
            return False

        try:
            controller_class = config['class']

            # Format address if needed
            if config['type'] == 'GPIB' and isinstance(address, int):
                visa_address = config['address_format'].format(address=address)
            else:
                visa_address = str(address)

            self.controller = controller_class(visa_address=visa_address)

            # Test connection
            if self.controller.connected:
                test_reading = self.controller.read_measurement()
                if test_reading is not None:
                    self.controller_type = config['name']
                    self.controller_config = config
                    self.address = visa_address
                    print(f"Connected to {config['name']} at {visa_address}")
                    return True
                else:
                    self.controller.disconnect()
                    self.controller = None
                    return False
            else:
                self.controller = None
                return False

        except Exception as e:
            print(f"Failed to connect to {controller_type}: {e}")
            return False

    def _use_cached_value(self, measurement_type: str) -> Optional[float]:
        """Check if we can use a cached value for the measurement type."""
        current_time = time.time()
        if (current_time - self.last_read_time) < self.cache_duration:
            return self.last_measurements.get(measurement_type)
        return None

    def _update_cache(self, measurement_type: str, value: float):
        """Update the measurement cache."""
        self.last_measurements[measurement_type] = value
        self.last_read_time = time.time()

    # Unified API Methods

    def measure_dc_voltage(self, range_val: Optional[float] = None, use_cache: bool = True) -> float:
        """
        Measure DC voltage.

        Args:
            range_val: Voltage range (0.1, 1, 10, 100, 1000). None for auto range.
            use_cache: If True, use cached value if recent

        Returns:
            float: DC voltage in Volts
        """
        # Check cache first
        if use_cache:
            cached_value = self._use_cached_value('dc_voltage')
            if cached_value is not None:
                return cached_value

        if self.controller:
            try:
                self.controller.configure_dc_voltage(range_val=range_val)
                voltage = self.controller.read_and_wait()
                self._update_cache('dc_voltage', voltage)
                return voltage
            except Exception as e:
                print(f"Error reading DC voltage: {e}")
                return self.last_measurements['dc_voltage']
        
        return 0.0  # Default value when no controller

    def measure_ac_voltage(self, range_val: Optional[float] = None, use_cache: bool = True) -> float:
        """Measure AC voltage."""
        if use_cache:
            cached_value = self._use_cached_value('ac_voltage')
            if cached_value is not None:
                return cached_value

        if self.controller:
            try:
                self.controller.configure_ac_voltage(range_val=range_val)
                voltage = self.controller.read_and_wait()
                self._update_cache('ac_voltage', voltage)
                return voltage
            except Exception as e:
                print(f"Error reading AC voltage: {e}")
                return self.last_measurements['ac_voltage']
        
        return 0.0

    def measure_dc_current(self, range_val: Optional[float] = None, use_cache: bool = True) -> float:
        """
        Measure DC current.

        Args:
            range_val: Current range (0.1e-3, 1e-3, 10e-3, 100e-3, 1, 3). None for auto range.
            use_cache: If True, use cached value if recent

        Returns:
            float: DC current in Amperes
        """
        if use_cache:
            cached_value = self._use_cached_value('dc_current')
            if cached_value is not None:
                return cached_value

        if self.controller:
            try:
                self.controller.configure_dc_current(range_val=range_val)
                current = self.controller.read_and_wait()
                self._update_cache('dc_current', current)
                return current
            except Exception as e:
                print(f"Error reading DC current: {e}")
                return self.last_measurements['dc_current']
        
        return 0.0

    def measure_ac_current(self, range_val: Optional[float] = None, use_cache: bool = True) -> float:
        """Measure AC current."""
        if use_cache:
            cached_value = self._use_cached_value('ac_current')
            if cached_value is not None:
                return cached_value

        if self.controller:
            try:
                self.controller.configure_ac_current(range_val=range_val)
                current = self.controller.read_and_wait()
                self._update_cache('ac_current', current)
                return current
            except Exception as e:
                print(f"Error reading AC current: {e}")
                return self.last_measurements['ac_current']
        
        return 0.0

    def measure_resistance(self, range_val: Optional[float] = None, use_cache: bool = True) -> float:
        """
        Measure resistance.

        Args:
            range_val: Resistance range (100, 1000, 10000, 100000, 1000000, 10000000, 100000000). None for auto range.
            use_cache: If True, use cached value if recent

        Returns:
            float: Resistance in Ohms
        """
        if use_cache:
            cached_value = self._use_cached_value('resistance')
            if cached_value is not None:
                return cached_value

        if self.controller:
            try:
                self.controller.configure_resistance(range_val=range_val)
                resistance = self.controller.read_and_wait()
                self._update_cache('resistance', resistance)
                return resistance
            except Exception as e:
                print(f"Error reading resistance: {e}")
                return self.last_measurements['resistance']
        
        return 1000.0  # Default 1kΩ

    def measure_frequency(self, voltage_range: Optional[float] = None, use_cache: bool = True) -> float:
        """Measure frequency."""
        if use_cache:
            cached_value = self._use_cached_value('frequency')
            if cached_value is not None:
                return cached_value

        if self.controller:
            try:
                self.controller.configure_frequency(voltage_range=voltage_range)
                frequency = self.controller.read_and_wait()
                self._update_cache('frequency', frequency)
                return frequency
            except Exception as e:
                print(f"Error reading frequency: {e}")
                return self.last_measurements['frequency']
        
        return 1000.0  # Default 1kHz

    def measure_all(self, use_cache: bool = False) -> Dict[str, float]:
        """
        Measure all available parameters.

        Args:
            use_cache: If True, use cached values where available

        Returns:
            Dict[str, float]: Dictionary of all measurements
        """
        measurements = {}
        
        if self.controller:
            try:
                # Configure and measure each type
                self.controller.configure_dc_voltage()
                measurements['dc_voltage'] = self.controller.read_and_wait()
                
                self.controller.configure_ac_voltage()
                measurements['ac_voltage'] = self.controller.read_and_wait()
                
                self.controller.configure_dc_current()
                measurements['dc_current'] = self.controller.read_and_wait()
                
                self.controller.configure_ac_current()
                measurements['ac_current'] = self.controller.read_and_wait()
                
                self.controller.configure_resistance()
                measurements['resistance'] = self.controller.read_and_wait()
                
                self.controller.configure_frequency()
                measurements['frequency'] = self.controller.read_and_wait()
                
                # Update cache
                for key, value in measurements.items():
                    self.last_measurements[key] = value
                self.last_read_time = time.time()
                
            except Exception as e:
                print(f"Error in measure_all: {e}")
                measurements = self.last_measurements.copy()
        else:
            measurements = self.last_measurements.copy()
        
        return measurements

    # Configuration Methods

    def set_range(self, range_val: float):
        """Set measurement range."""
        if self.controller:
            self.controller.set_range(range_val)

    def set_auto_range(self, auto: bool = True):
        """Enable or disable auto range."""
        if self.controller:
            self.controller.set_auto_range(auto)

    def set_resolution(self, resolution: int):
        """Set measurement resolution in digits (4-6)."""
        if self.controller:
            self.controller.set_resolution(resolution)

    def set_trigger_source(self, source: str = 'IMM'):
        """Set trigger source."""
        if self.controller:
            self.controller.set_trigger_source(source)

    # Status and Information Methods

    def get_controller_info(self) -> Dict[str, Any]:
        """Get information about the connected controller."""
        if self.controller:
            try:
                status = self.controller.get_status()
                return {
                    'connected': True,
                    'type': self.controller_type,
                    'address': self.address,
                    'identity': status.get('identity', 'Unknown'),
                    'range': status.get('range', 0),
                    'resolution': status.get('resolution', 4),
                    'auto_range': status.get('auto_range', True),
                    'trigger_source': status.get('trigger_source', 'IMM'),
                    'last_measurements': self.last_measurements.copy()
                }
            except Exception as e:
                return {
                    'connected': True,
                    'type': self.controller_type,
                    'address': self.address,
                    'identity': 'Error reading status',
                    'error': str(e),
                    'last_measurements': self.last_measurements.copy()
                }
        else:
            return {
                'connected': False,
                'type': None,
                'address': None,
                'identity': None,
                'last_measurements': self.last_measurements.copy()
            }

    def is_connected(self) -> bool:
        """Check if an ammeter is connected."""
        return self.controller is not None and self.controller.connected

    def get_last_measurements(self) -> Dict[str, float]:
        """Get the last cached measurements."""
        return self.last_measurements.copy()

    def clear_cache(self):
        """Clear the measurement cache."""
        self.last_read_time = 0
        for key in self.last_measurements:
            self.last_measurements[key] = 0.0

    def close(self):
        """Close connection to the ammeter."""
        if self.controller:
            try:
                self.controller.disconnect()
                print(f"Closed connection to {self.controller_type}")
            except:
                pass
            self.controller = None
            self.controller_type = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Example usage
if __name__ == "__main__":
    print("Ammeter Controller Manager Test")
    print("=" * 40)

    # Auto-detect ammeter
    ammeter_mgr = AmmeterControllerManager(auto_detect=True)

    # Test measurements if connected
    if ammeter_mgr.is_connected():
        print("\nTaking measurements...")
        
        # Individual measurements
        dc_voltage = ammeter_mgr.measure_dc_voltage()
        print(f"DC Voltage: {dc_voltage:.6f} V")
        
        dc_current = ammeter_mgr.measure_dc_current()
        print(f"DC Current: {dc_current:.9f} A")
        
        resistance = ammeter_mgr.measure_resistance()
        print(f"Resistance: {resistance:.3f} Ω")
        
        # All measurements at once
        print("\nAll measurements:")
        all_measurements = ammeter_mgr.measure_all()
        for measurement_type, value in all_measurements.items():
            print(f"{measurement_type}: {value:.6f}")
        
        # Controller info
        print(f"\nController info:")
        info = ammeter_mgr.get_controller_info()
        for key, value in info.items():
            if key != 'last_measurements':
                print(f"{key}: {value}")
    
    else:
        print("No ammeter detected. Using default values.")
        
        # Test with default values
        dc_voltage = ammeter_mgr.measure_dc_voltage()
        print(f"DC Voltage (default): {dc_voltage:.6f} V")

    # Manual initialization example
    print(f"\nManual initialization example:")
    # ammeter_mgr_manual = AmmeterControllerManager(
    #     auto_detect=False,
    #     controller_type='Agilent34401A',
    #     address=22  # GPIB address 22
    # )

    ammeter_mgr.close()

