"""
Oscilloscope Manager

This module provides a unified interface for managing different oscilloscope types,
specifically designed to work with the Tektronix TBS1000C series.
Similar to the temperature_controller_manager.py, ammeter_manager.py patterns.

The manager provides:
- Auto-detection of connected oscilloscopes
- Manual initialization with specific addresses
- Unified API for waveform acquisition and measurements
- Configuration management
- Connection caching

Author: Generated for Switchbox_GUI project
"""

import time
import pyvisa
from typing import Optional, Dict, Any, Union, Tuple
import numpy as np

# Import oscilloscope classes
try:
    from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C
    from Equipment.Oscilloscopes.GWInstekGDS2062 import GWInstekGDS2062
except ModuleNotFoundError:
    # Allow running this file directly by adding project root to sys.path
    import os
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C
    from Equipment.Oscilloscopes.GWInstekGDS2062 import GWInstekGDS2062


class OscilloscopeManager:
    """
    Manager class that automatically detects and manages oscilloscopes.
    Currently supports Tektronix TBS1000C series and GW Instek GDS-2062 via USB.
    
    Provides a unified interface for different oscilloscope types with:
    - Auto-detection of connected devices
    - Manual initialization with specific addresses
    - Unified API for waveform acquisition and measurements
    """
    
    # Oscilloscope configurations
    OSCILLOSCOPE_CONFIGS = [
        {
            'class': TektronixTBS1000C,
            'type': 'USB',
            'addresses': [],  # Will be auto-detected
            'name': 'Tektronix TBS1000C',
            'test_method': 'idn',
            'address_format': 'USB0::{vid}::{pid}::{serial}::INSTR'
        },
        {
            'class': GWInstekGDS2062,
            'type': 'USB',
            'addresses': [],  # Will be auto-detected
            'name': 'GW Instek GDS-2062',
            'test_method': 'idn',
            'address_format': 'USB0::......::INSTR'
        }
    ]
    
    def __init__(self, auto_detect: bool = True, scope_type: Optional[str] = None,
                 address: Optional[Union[str, int]] = None):
        """
        Initialize the oscilloscope manager.
        
        Args:
            auto_detect: If True, automatically detect connected oscilloscope
            scope_type: Manual oscilloscope type ('Tektronix TBS1000C', 'GW Instek GDS-2062')
            address: Manual address (VISA resource string)
        """
        self.scope = None
        self.scope_type = None
        self.scope_config = None
        self.address = None
        
        # Waveform cache
        self.last_waveform = {
            'channel': None,
            'format': None,
            'time_array': None,
            'voltage_array': None,
            'timestamp': 0,
            'kwargs': {}
        }
        self.cache_duration = 1.0  # Cache for 1 second
        
        if auto_detect:
            self.auto_detect_scope()
        elif scope_type and address:
            self.manual_init_scope(scope_type, address)
    
    def auto_detect_scope(self) -> bool:
        """
        Automatically detect which oscilloscope is connected.
        
        Returns:
            bool: True if oscilloscope found, False otherwise
        """
        print("Scanning for oscilloscopes...")
        
        # First, try to find Tektronix devices via USB
        try:
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
            
            # Try each oscilloscope type
            for config in self.OSCILLOSCOPE_CONFIGS:
                scope_class = config['class']
                scope_name = config['name']
                
                # Try to find matching USB resources
                usb_resources = [r for r in resources if 'USB' in r]
                if not usb_resources:
                    continue
                
                # Try each found resource
                for resource in usb_resources:
                    print(f"Trying {scope_name} at {resource}...", end=' ')
                    try:
                        scope = scope_class(resource=resource)
                        if scope.connect():
                            # Verify it matches expected type
                            idn = scope.idn()
                            if (('TEKTRONIX' in idn.upper() or 'TBS' in idn.upper()) and 
                                'Tektronix' in scope_name) or \
                               (('GW' in idn.upper() or 'INSTEK' in idn.upper() or 'GDS' in idn.upper()) and
                                'GW Instek' in scope_name):
                                self.scope = scope
                                self.scope_type = scope_name
                                self.scope_config = config
                                self.address = resource
                                print(f"✓ Success!")
                                print(f"Connected to: {idn}")
                                return True
                            else:
                                scope.disconnect()
                                print("✗ (Wrong type)")
                        else:
                            print("✗ (Connection failed)")
                    except Exception as e:
                        print(f"✗ ({str(e)[:30]}...)")
                        continue
                    
                    # Only try first successful match
                    if self.scope:
                        break
                    
                # Break if we found a scope
                if self.scope:
                    break
        except Exception as e:
            print(f"Error during auto-detection: {e}")
        
        print("No oscilloscope detected.")
        return False
    
    def manual_init_scope(self, scope_type: str, address: str) -> bool:
        """
        Manually initialize a specific oscilloscope.
        
        Args:
            scope_type: 'Tektronix TBS1000C' or similar. If 'Unknown' or doesn't match,
                       will try all known scope types.
            address: VISA resource string
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Find matching config
        config = None
        if scope_type and scope_type != 'Unknown':
            for cfg in self.OSCILLOSCOPE_CONFIGS:
                if scope_type in cfg['name'] or scope_type.replace(' ', '') in cfg['name'].replace(' ', ''):
                    config = cfg
                    break
        
        # If no config found or scope_type is 'Unknown', try all known types
        configs_to_try = [config] if config else self.OSCILLOSCOPE_CONFIGS
        
        for cfg in configs_to_try:
            try:
                scope_class = cfg['class']
                self.scope = scope_class(resource=address)
                
                # Test connection
                if self.scope.connect():
                    idn = self.scope.idn()
                    self.scope_type = cfg['name']
                    self.scope_config = cfg
                    self.address = address
                    print(f"Connected to {cfg['name']} at {address}")
                    print(f"ID: {idn}")
                    return True
                else:
                    self.scope = None
            except Exception as e:
                # Try next config if this one fails
                if self.scope:
                    try:
                        self.scope.disconnect()
                    except:
                        pass
                self.scope = None
                continue
        
        # If we get here, all attempts failed
        print(f"Failed to connect to oscilloscope at {address}")
        if scope_type and scope_type != 'Unknown':
            print(f"  Tried type: {scope_type}")
        print(f"  Tried all known oscilloscope types")
        return False
    
    # ==================== Unified API Methods ====================
    
    def acquire_waveform(self, channel: int = 1, format: str = 'ASCII',
                         use_cache: bool = True, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """
        Acquire waveform data from a channel.
        
        Args:
            channel: Channel number (1 or 2)
            format: Data format - 'ASCII', 'RIBINARY', or 'WORD'
            use_cache: If True, use cached waveform if recent
            **kwargs: Additional keyword arguments forwarded to the underlying
                oscilloscope driver implementation (e.g., num_points).
            
        Returns:
            tuple: (time_array, voltage_array) both as numpy arrays
        """
        # Check cache (only when no additional kwargs are passed to avoid mismatched results)
        if use_cache and not kwargs:
            if (self.last_waveform['channel'] == channel and
                self.last_waveform['time_array'] is not None and
                self.last_waveform.get('format') == format and
                (time.time() - self.last_waveform['timestamp']) < self.cache_duration):
                return self.last_waveform['time_array'], self.last_waveform['voltage_array']
        
        if self.scope:
            try:
                time_array, voltage_array = self.scope.acquire_waveform(channel, format=format, **kwargs)
                # Update cache
                self.last_waveform = {
                    'channel': channel,
                    'format': format,
                    'time_array': time_array,
                    'voltage_array': voltage_array,
                    'timestamp': time.time(),
                    'kwargs': dict(kwargs)
                }
                return time_array, voltage_array
            except Exception as e:
                print(f"Error acquiring waveform: {e}")
                if self.last_waveform['time_array'] is not None:
                    return self.last_waveform['time_array'], self.last_waveform['voltage_array']
        
        # Return empty arrays if no scope
        return np.array([]), np.array([])
    
    def configure_channel(self, channel: int, volts_per_div: Optional[float] = None,
                         coupling: Optional[str] = None, offset: Optional[float] = None):
        """
        Configure oscilloscope channel.
        
        Args:
            channel: Channel number (1 or 2)
            volts_per_div: Vertical scale in V/div
            coupling: 'DC', 'AC', or 'GND'
            offset: Vertical offset in volts
        """
        if not self.scope:
            return
        
        try:
            if volts_per_div is not None:
                self.scope.set_channel_scale(channel, volts_per_div)
            if coupling is not None:
                self.scope.set_channel_coupling(channel, coupling)
            if offset is not None:
                self.scope.set_channel_offset(channel, offset)
        except Exception as e:
            print(f"Error configuring channel: {e}")
    
    def configure_record_length(self, points: Optional[int] = None) -> Optional[int]:
        """
        Configure acquisition record length (number of samples).
        
        Args:
            points: Desired number of points; driver may clamp to supported range.
        
        Returns:
            Optional[int]: The record length actually applied, if available.
        """
        if not self.scope or not hasattr(self.scope, 'set_record_length'):
            return None
        try:
            return self.scope.set_record_length(points if points is not None else 20000)
        except Exception as e:
            print(f"Error configuring record length: {e}")
            return None
    
    def configure_timebase(self, time_per_div: Optional[float] = None,
                          position: Optional[float] = None):
        """
        Configure horizontal timebase.
        
        Args:
            time_per_div: Time per division in seconds
            position: Horizontal position in seconds
        """
        if not self.scope:
            return
        
        try:
            if time_per_div is not None:
                self.scope.set_timebase_scale(time_per_div)
            if position is not None:
                self.scope.set_timebase_position(position)
        except Exception as e:
            print(f"Error configuring timebase: {e}")
    
    def configure_trigger(self, source: Optional[str] = None,
                         level: Optional[float] = None, 
                         mode: Optional[str] = None,
                         slope: Optional[str] = None,
                         holdoff: Optional[float] = None):
        """
        Configure trigger settings.
        
        Args:
            source: 'CH1', 'CH2', 'EXT', 'LINE', or 'AC'
            level: Trigger level in volts
            mode: 'AUTO', 'NORMAL', 'SINGLE', or 'STOP'
            slope: 'RISING', 'FALLING', or 'EITHER'
            holdoff: Trigger holdoff in seconds
        """
        if not self.scope:
            return
        
        try:
            if source is not None:
                self.scope.set_trigger_source(source)
            if level is not None:
                self.scope.set_trigger_level(level)
            if mode is not None:
                self.scope.set_trigger_mode(mode)
            if slope is not None:
                self.scope.set_trigger_slope(slope)
            if holdoff is not None and hasattr(self.scope, "set_trigger_holdoff"):
                self.scope.set_trigger_holdoff(holdoff)
        except Exception as e:
            print(f"Error configuring trigger: {e}")
    
    def autoscale(self):
        """Automatically scale all displayed channels."""
        if self.scope:
            try:
                self.scope.autoscale()
                # Clear cache after autoscale
                self.last_waveform = {
                    'channel': None,
                    'format': None,
                    'time_array': None,
                    'voltage_array': None,
                    'timestamp': 0,
                    'kwargs': {}
                }
            except Exception as e:
                print(f"Error during autoscale: {e}")
    
    def enable_channel(self, channel: int, enable: bool = True):
        """
        Enable or disable channel display.
        
        Args:
            channel: Channel number (1 or 2)
            enable: True to enable, False to disable
        """
        if self.scope:
            try:
                self.scope.channel_display(channel, enable)
            except Exception as e:
                print(f"Error enabling channel: {e}")
    
    def configure_measurement(self, measurement_type: str, channel: int = 1,
                             measurement_number: int = 1):
        """
        Configure an automatic measurement.
        
        Args:
            measurement_type: Type (e.g., 'AMPL', 'FREQ', 'RIS', 'FALL')
            channel: Channel number (1 or 2)
            measurement_number: Measurement slot (1-4)
        """
        if self.scope:
            try:
                self.scope.configure_measurement(measurement_type, channel, measurement_number)
            except Exception as e:
                print(f"Error configuring measurement: {e}")
    
    def read_measurement(self, measurement_number: int = 1) -> float:
        """
        Read measurement value.
        
        Args:
            measurement_number: Measurement slot number (1-4)
            
        Returns:
            float: Measurement value
        """
        if self.scope:
            try:
                return self.scope.read_measurement(measurement_number)
            except Exception as e:
                print(f"Error reading measurement: {e}")
                return 0.0
        return 0.0
    
    def save_screen(self, filename: str):
        """
        Save oscilloscope screen to file.
        
        Args:
            filename: Output filename
        """
        if self.scope:
            try:
                self.scope.save_screen(filename)
            except Exception as e:
                print(f"Error saving screen: {e}")
    
    def force_trigger(self):
        """Force a trigger event."""
        if self.scope:
            try:
                self.scope.force_trigger()
            except Exception as e:
                print(f"Error forcing trigger: {e}")
    
    def compute_waveform_statistics(self, voltage_array: np.ndarray) -> Dict[str, float]:
        """
        Compute basic statistics from acquired waveform data.
        
        Useful for TBS1000C which may not support automatic measurements via SCPI.
        
        Args:
            voltage_array: Array of voltage values from acquire_waveform()
            
        Returns:
            dict: Dictionary containing peak-to-peak, mean, std, etc.
        """
        if self.scope:
            try:
                return self.scope.compute_waveform_statistics(voltage_array)
            except Exception as e:
                print(f"Error computing statistics: {e}")
        return {'vpp': 0.0, 'mean': 0.0, 'std': 0.0, 'vmax': 0.0, 'vmin': 0.0}
    
    def compute_frequency(self, time_array: np.ndarray, voltage_array: np.ndarray) -> float:
        """
        Estimate signal frequency from waveform data using zero-crossing detection.
        
        Args:
            time_array: Array of time values from acquire_waveform()
            voltage_array: Array of voltage values from acquire_waveform()
            
        Returns:
            float: Estimated frequency in Hz, or 0.0 if calculation fails
        """
        if self.scope:
            try:
                return self.scope.compute_frequency(time_array, voltage_array)
            except Exception as e:
                print(f"Error computing frequency: {e}")
        return 0.0
    
    # ==================== Status and Information Methods ====================
    
    def get_scope_info(self) -> Dict[str, Any]:
        """
        Get information about the connected oscilloscope.
        
        Returns:
            dict: Info dictionary
        """
        if self.scope:
            try:
                status = self.scope.get_status()
                return {
                    'connected': True,
                    'type': self.scope_type,
                    'address': self.address,
                    **status
                }
            except Exception as e:
                return {
                    'connected': True,
                    'type': self.scope_type,
                    'address': self.address,
                    'error': str(e)
                }
        else:
            return {
                'connected': False,
                'type': None,
                'address': None
            }
    
    def is_connected(self) -> bool:
        """Check if oscilloscope is connected."""
        return self.scope is not None and self.scope.is_connected()
    
    def clear_cache(self):
        """Clear waveform cache."""
        self.last_waveform = {
            'channel': None,
            'format': None,
            'time_array': None,
            'voltage_array': None,
            'timestamp': 0,
            'kwargs': {}
        }
    
    def close(self):
        """Close connection to the oscilloscope."""
        if self.scope:
            try:
                self.scope.disconnect()
                print(f"Closed connection to {self.scope_type}")
            except Exception as e:
                print(f"Error closing connection: {e}")
            self.scope = None
            self.scope_type = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Example usage
if __name__ == "__main__":
    print("Oscilloscope Manager Test")
    print("=" * 40)
    
    # Auto-detect oscilloscope
    scope_mgr = OscilloscopeManager(auto_detect=True)
    
    # Test operations if connected
    if scope_mgr.is_connected():
        print("\nTaking measurements...")
        
        # Get info
        info = scope_mgr.get_scope_info()
        print(f"Connected to: {info.get('idn', 'Unknown')}")
        
        # Autoscale
        print("\nRunning autoscale...")
        scope_mgr.autoscale()
        
        # Configure channels
        print("Configuring channels...")
        scope_mgr.enable_channel(1, True)
        scope_mgr.enable_channel(2, False)
        scope_mgr.configure_channel(1, coupling='DC')
        
        # Wait for acquisition
        time.sleep(2)
        
        # Acquire waveform
        print("\nAcquiring waveform...")
        time_array, voltage_array = scope_mgr.acquire_waveform(channel=1)
        print(f"Acquired {len(voltage_array)} data points")
        if len(voltage_array) > 0:
            print(f"Voltage range: {voltage_array.min():.3f} V to {voltage_array.max():.3f} V")
        
        # Configure measurements
        print("\nConfiguring measurements...")
        scope_mgr.configure_measurement('AMPL', channel=1, measurement_number=1)
        scope_mgr.configure_measurement('FREQ', channel=1, measurement_number=2)
        
        time.sleep(1)
        
        # Read measurements
        amplitude = scope_mgr.read_measurement(1)
        frequency = scope_mgr.read_measurement(2)
        print(f"Amplitude: {amplitude:.3f} V")
        print(f"Frequency: {frequency:.3f} Hz")
    
    else:
        print("No oscilloscope detected.")
    
    # Manual initialization example
    print(f"\nManual initialization example:")
    # scope_mgr_manual = OscilloscopeManager(
    #     auto_detect=False,
    #     scope_type='Tektronix TBS1000C',
    #     address='USB0::0x0699::0x0409::C000000::INSTR'
    # )
    
    scope_mgr.close()

