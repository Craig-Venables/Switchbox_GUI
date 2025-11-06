"""
GW Instek GDS-2062 Series Oscilloscope Control

This module provides a comprehensive interface for controlling and reading from
GW Instek GDS-2062 series oscilloscopes via USB using PyVISA and SCPI commands.

The class supports:
- Connection management via USB using VISA
- Channel configuration and control
- Waveform acquisition in various formats ✓
- Timebase and vertical scale settings
- Trigger configuration
- Automatic measurements (SCPI support)
- Waveform data export ✓

Note: Based on standard SCPI commands. Some commands may vary slightly by model.

Author: Generated for Switchbox_GUI project
"""

import pyvisa
import time
import struct
import numpy as np
from typing import Optional, Dict, Any, Tuple, List, Union


class GWInstekGDS2062:
    """
    Controller for GW Instek GDS-2062 series oscilloscopes.
    
    Provides methods for configuring channels, acquiring waveforms, and
    making measurements via SCPI commands over USB using USBTMC protocol.
    """
    
    def __init__(self, resource: Optional[str] = None, timeout_ms: int = 30000):
        """
        Initialize the GW Instek GDS-2062 controller.
        
        Args:
            resource: VISA resource string (e.g., 'USB0::......')
            timeout_ms: VISA IO timeout in milliseconds (default: 30000)
        """
        self.rm: Optional[pyvisa.ResourceManager] = None
        self.inst: Optional[pyvisa.resources.MessageBasedResource] = None
        self.resource = resource
        self.timeout_ms = timeout_ms
        self.wfmo_cache: Dict[str, Any] = {}  # Cache waveform preamble
        
    # ==================== Connection Management ====================
    
    def connect(self, resource: Optional[str] = None) -> bool:
        """
        Connect to the oscilloscope.
        
        Args:
            resource: Optional VISA resource string. If not provided, uses instance resource.
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if resource:
                self.resource = resource
            if not self.resource:
                raise ValueError("No VISA resource specified.")
            
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(self.resource)
            self.inst.timeout = self.timeout_ms
            
            # Configure communication settings
            self.inst.write_termination = '\n'
            self.inst.read_termination = '\n'
            
            # Verify connection by checking IDN
            _ = self.idn()
            return True
        except Exception as e:
            print(f"Error connecting to oscilloscope: {e}")
            self.inst = None
            if self.rm:
                try:
                    self.rm.close()
                except Exception:
                    pass
                self.rm = None
            return False
    
    def disconnect(self):
        """Disconnect from the oscilloscope and clean up resources."""
        if self.inst is not None:
            try:
                self.inst.close()
            except Exception:
                pass
        if self.rm is not None:
            try:
                self.rm.close()
            except Exception:
                pass
        self.inst = None
        self.rm = None
        self.wfmo_cache.clear()
    
    def is_connected(self) -> bool:
        """Check if oscilloscope is connected."""
        return self.inst is not None
    
    # ==================== Basic SCPI Commands ====================
    
    def write(self, cmd: str):
        """
        Send a command to the oscilloscope.
        
        Args:
            cmd: SCPI command string
        """
        if not self.inst:
            raise RuntimeError("Oscilloscope not connected.")
        self.inst.write(cmd)
    
    def query(self, cmd: str) -> str:
        """
        Send a query to the oscilloscope and return response.
        
        Args:
            cmd: SCPI query string
            
        Returns:
            str: Response from oscilloscope
        """
        if not self.inst:
            raise RuntimeError("Oscilloscope not connected.")
        resp = self.inst.query(cmd)
        return resp.strip()
    
    def idn(self) -> str:
        """
        Get oscilloscope identification string.
        
        Returns:
            str: IDN string containing manufacturer, model, serial, and firmware
        """
        try:
            return self.query("*IDN?")
        except Exception as e:
            return f"IDN error: {e}"
    
    def reset(self):
        """Reset oscilloscope to default settings."""
        self.write("*RST")
        time.sleep(2)  # Wait for reset to complete
        self.wfmo_cache.clear()
    
    def clear_status(self):
        """Clear status registers and error queue."""
        self.write("*CLS")
    
    def error_query(self) -> str:
        """
        Query error queue.
        
        Returns:
            str: Error message or "0,'No error'"
        """
        try:
            return self.query("SYST:ERR?")
        except Exception as e:
            return f"Error query failed: {e}"
    
    def wait_for_operation(self, timeout_s: float = 30.0) -> bool:
        """
        Wait for operation to complete.
        
        Args:
            timeout_s: Maximum time to wait in seconds
            
        Returns:
            bool: True if operation completed, False if timeout
        """
        t0 = time.time()
        while True:
            try:
                resp = self.query("*OPC?")
                if resp.strip() == "1":
                    return True
            except Exception:
                pass
            if (time.time() - t0) > timeout_s:
                return False
            time.sleep(0.1)
    
    # ==================== Channel Control ====================
    
    def channel_enable(self, channel: int, enable: bool = True):
        """
        Enable or disable a channel display.
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
            enable: True to enable, False to disable
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        self.write(f"SELECT:CH{channel} {'ON' if enable else 'OFF'}")
    
    def channel_display(self, channel: int, enable: bool = True):
        """
        Display or hide a channel.
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
            enable: True to display, False to hide
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        self.write(f"SELECT:CH{channel} {'ON' if enable else 'OFF'}")
    
    def set_channel_scale(self, channel: int, volts_per_div: float):
        """
        Set vertical scale for a channel.
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
            volts_per_div: Voltage per division in volts (e.g., 1.0 for 1V/div)
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        self.write(f"CH{channel}:SCAL {volts_per_div}")
    
    def get_channel_scale(self, channel: int) -> float:
        """
        Get current vertical scale for a channel.
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
            
        Returns:
            float: Voltage per division in volts
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        try:
            return float(self.query(f"CH{channel}:SCAL?"))
        except Exception:
            return 1.0
    
    def set_channel_offset(self, channel: int, offset: float):
        """
        Set vertical offset for a channel.
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
            offset: Vertical offset in volts
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        self.write(f"CH{channel}:OFFS {offset}")
    
    def get_channel_offset(self, channel: int) -> float:
        """
        Get current vertical offset for a channel.
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
            
        Returns:
            float: Vertical offset in volts
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        try:
            return float(self.query(f"CH{channel}:OFFS?"))
        except Exception:
            return 0.0
    
    def set_channel_coupling(self, channel: int, coupling: str):
        """
        Set input coupling for a channel.
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
            coupling: 'DC', 'AC', or 'GND'
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        if coupling.upper() not in ('DC', 'AC', 'GND'):
            raise ValueError("Coupling must be DC, AC, or GND")
        self.write(f"CH{channel}:COUP {coupling.upper()}")
    
    # ==================== Timebase Control ====================
    
    def set_timebase_scale(self, scale: float):
        """
        Set horizontal time per division.
        
        Args:
            scale: Time per division in seconds (e.g., 1e-3 for 1 ms/div)
        """
        self.write(f"HOR:SCAL {scale}")
    
    def get_timebase_scale(self) -> float:
        """
        Get current horizontal time per division.
        
        Returns:
            float: Time per division in seconds
        """
        try:
            return float(self.query("HOR:SCAL?"))
        except Exception:
            return 1e-3
    
    def set_timebase_position(self, position: float):
        """
        Set horizontal position (trigger position).
        
        Args:
            position: Horizontal position in seconds
        """
        self.write(f"HOR:POS {position}")
    
    def get_timebase_position(self) -> float:
        """
        Get current horizontal position.
        
        Returns:
            float: Horizontal position in seconds
        """
        try:
            return float(self.query("HOR:POS?"))
        except Exception:
            return 0.0
    
    # ==================== Trigger Control ====================
    
    def set_trigger_mode(self, mode: str):
        """
        Set trigger mode.
        
        Args:
            mode: 'AUTO', 'NORMAL', or 'SINGLE'
        """
        valid_modes = ['AUTO', 'NORMAL', 'SINGLE']
        if mode.upper() not in valid_modes:
            raise ValueError(f"Mode must be one of: {valid_modes}")
        self.write(f"TRIG:MODE {mode.upper()}")
    
    def get_trigger_mode(self) -> str:
        """
        Get current trigger mode.
        
        Returns:
            str: Trigger mode
        """
        try:
            return self.query("TRIG:MODE?").strip().upper()
        except Exception:
            return "AUTO"
    
    def set_trigger_source(self, source: str):
        """
        Set trigger source.
        
        Args:
            source: 'CH1', 'CH2', 'CH3', 'CH4', 'EXT', or 'LINE'
        """
        valid_sources = ['CH1', 'CH2', 'CH3', 'CH4', 'EXT', 'LINE']
        if source.upper() not in valid_sources:
            raise ValueError(f"Source must be one of: {valid_sources}")
        self.write(f"TRIG:SOUR {source.upper()}")
    
    def set_trigger_level(self, level: float):
        """
        Set trigger level.
        
        Args:
            level: Trigger level in volts
        """
        self.write(f"TRIG:LEV {level}")
    
    def get_trigger_level(self) -> float:
        """
        Get current trigger level.
        
        Returns:
            float: Trigger level in volts
        """
        try:
            return float(self.query("TRIG:LEV?"))
        except Exception:
            return 0.0
    
    def set_trigger_slope(self, slope: str):
        """
        Set trigger slope.
        
        Args:
            slope: 'RISING' or 'FALLING'
        """
        valid_slopes = ['RISING', 'FALLING']
        if slope.upper() not in valid_slopes:
            raise ValueError(f"Slope must be one of: {valid_slopes}")
        self.write(f"TRIG:SLOP {slope.upper()[0]}E")
    
    def force_trigger(self):
        """Force a trigger event."""
        self.write("TRIG FORC")
    
    # ==================== Waveform Acquisition ====================
    
    def get_waveform_preamble(self, channel: int) -> Dict[str, Any]:
        """
        Get waveform preamble information for a channel.
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
            
        Returns:
            dict: Waveform preamble containing format, type, points, etc.
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        
        # Check cache first
        cache_key = f"CH{channel}"
        if cache_key in self.wfmo_cache:
            return self.wfmo_cache[cache_key]
        
        # Select channel and get preamble
        self.write(f"DATA:SOURCE CH{channel}")
        wfmo_str = self.query("WFMO?")
        
        # Parse preamble
        preamble = self._parse_waveform_preamble(wfmo_str)
        self.wfmo_cache[cache_key] = preamble
        return preamble
    
    def _parse_waveform_preamble(self, wfmo_str: str) -> Dict[str, Any]:
        """
        Parse waveform preamble string.
        
        Args:
            wfmo_str: Waveform preamble string from WFMO? query
            
        Returns:
            dict: Parsed preamble dictionary
        """
        preamble = {}
        for item in wfmo_str.split(';'):
            if ':' in item:
                key, value = item.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Convert numeric values
                try:
                    if '.' in value or 'e' in value.lower() or 'E' in value:
                        preamble[key] = float(value)
                    else:
                        preamble[key] = int(value)
                except ValueError:
                    preamble[key] = value
            else:
                preamble[item.strip()] = True
        
        return preamble
    
    def acquire_waveform(self, channel: int, format: str = "ASCII", num_points: int = 10000) -> Tuple[np.ndarray, np.ndarray]:
        """
        Acquire waveform data from a channel.
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
            format: Data format - 'ASCII' or 'BINARY' (default: 'ASCII')
            num_points: Number of points to acquire (default: 10000)
            
        Returns:
            tuple: (time_array, voltage_array) both as numpy arrays
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        
        # Select channel and set data format
        self.write(f"DATA:SOURCE CH{channel}")
        self.write(f"DATA:ENC {format}")
        self.write(f"DATA:WID 1")  # 1 byte per data point
        
        # Get preamble for scaling
        preamble = self.get_waveform_preamble(channel)
        
        # Read waveform data
        if format == "ASCII":
            self.write(f"DATA:START 1")
            self.write(f"DATA:STOP {num_points}")
            data_str = self.query("CURV?")
            
            # Parse ASCII data
            data_points = []
            for value in data_str.split(','):
                try:
                    data_points.append(int(float(value.strip())))
                except ValueError:
                    continue
        else:
            # Binary format
            self.write(f"DATA:START 1")
            self.write(f"DATA:STOP {num_points}")
            
            # Configure for binary read
            self.inst.chunk_size = 1024000  # Increase chunk size for binary
            data_binary = self.inst.query_binary_values("CURV?", datatype='B', container=np.array)
            data_points = data_binary.tolist()
        
        # Convert to numpy array
        y_values = np.array(data_points, dtype=np.float64)
        
        # Apply vertical scaling
        if 'YMULT' in preamble and 'YOFF' in preamble and 'YZERO' in preamble:
            y_values = (y_values * preamble['YMULT']) + preamble['YOFF'] - preamble['YZERO']
        
        # Generate time array
        num_points = len(y_values)
        if 'XINCR' in preamble and 'XZERO' in preamble:
            time_values = np.arange(num_points) * preamble['XINCR'] + preamble['XZERO']
        else:
            # Fallback: use timebase scale
            time_scale = self.get_timebase_scale()
            time_values = np.linspace(-4 * time_scale, 4 * time_scale, num_points)
        
        return time_values, y_values
    
    def save_screen(self, filename: str):
        """
        Save oscilloscope screen to file.
        
        Args:
            filename: Output filename (supports .bmp, .png, .jpg)
        """
        self.write(f"HARDCOPY:IMAG " + filename)
    
    # ==================== Automatic Measurements ====================
    
    def configure_measurement(self, measurement_type: str, channel: int = 1, 
                             measurement_number: int = 1):
        """
        Configure an automatic measurement.
        
        Args:
            measurement_type: Measurement type (e.g., 'VPP', 'VAMP', 'FREQ', 'PERI')
            channel: Channel number (1, 2, 3, or 4)
            measurement_number: Measurement slot number (1-4)
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Channel must be 1, 2, 3, or 4")
        if measurement_number not in (1, 2, 3, 4):
            raise ValueError("Measurement number must be 1-4")
        
        self.write(f"MEAS:MEAS{measurement_number}:TYP {measurement_type}")
        self.write(f"MEAS:MEAS{measurement_number}:SOUR CH{channel}")
    
    def read_measurement(self, measurement_number: int = 1, debug: bool = False) -> float:
        """
        Read measurement value.
        
        Args:
            measurement_number: Measurement slot number (1-4)
            debug: If True, print debug information
            
        Returns:
            float: Measurement value
        """
        if measurement_number not in (1, 2, 3, 4):
            raise ValueError("Measurement number must be 1-4")
        
        try:
            result = self.query(f"MEAS:MEAS{measurement_number}:VAL?")
            if debug:
                print(f"Raw measurement result: '{result}'")
            
            # Handle responses that may contain units or status
            result = result.strip()
            
            # Try to parse as float, but handle edge cases
            # Invalid measurements typically return 9.9E37 or similar
            if '9.9E37' in result or '99.0E36' in result or result.startswith('****') or 'E+36' in result.upper():
                # Invalid measurement
                if debug:
                    print(f"Invalid measurement detected (no valid measurement available): {result}")
                raise ValueError(f"No valid measurement: scope returned {result}")
            
            # Remove any non-numeric trailing characters
            numeric_result = result.split()[0] if ' ' in result else result
            return float(numeric_result)
        except (ValueError, Exception) as e:
            if debug:
                print(f"Warning: Could not parse measurement value: {result if 'result' in locals() else 'unknown'}")
                print(f"Exception: {e}")
            return 0.0
    
    # ==================== Utility Methods ====================
    
    def autoscale(self):
        """Automatically scale all displayed channels."""
        self.write("AUTOSET EXEC")
        time.sleep(2)  # Wait for autoscale to complete
        self.wfmo_cache.clear()
    
    def stop_acquisition(self):
        """Stop waveform acquisition."""
        self.write("ACQ:STOP")
    
    def start_acquisition(self):
        """Start waveform acquisition."""
        self.write("ACQ:STAR")
    
    def compute_waveform_statistics(self, voltage_array: np.ndarray) -> Dict[str, float]:
        """
        Compute basic statistics from acquired waveform data.
        
        Useful for oscilloscopes which may not support automatic measurements via SCPI.
        
        Args:
            voltage_array: Array of voltage values from acquire_waveform()
            
        Returns:
            dict: Dictionary containing peak-to-peak, mean, std, etc.
        """
        if len(voltage_array) == 0:
            return {'vpp': 0.0, 'mean': 0.0, 'std': 0.0, 'vmax': 0.0, 'vmin': 0.0}
        
        return {
            'vpp': float(voltage_array.max() - voltage_array.min()),
            'mean': float(voltage_array.mean()),
            'std': float(voltage_array.std()),
            'vmax': float(voltage_array.max()),
            'vmin': float(voltage_array.min()),
            'vpk': float(abs(voltage_array).max())
        }
    
    def compute_frequency(self, time_array: np.ndarray, voltage_array: np.ndarray) -> float:
        """
        Estimate signal frequency from waveform data using zero-crossing detection.
        
        Args:
            time_array: Array of time values from acquire_waveform()
            voltage_array: Array of voltage values from acquire_waveform()
            
        Returns:
            float: Estimated frequency in Hz, or 0.0 if calculation fails
        """
        if len(voltage_array) < 10:
            return 0.0
        
        # Simple zero-crossing detection
        mean = voltage_array.mean()
        zero_crossings = 0
        
        # Count rising zero crossings
        for i in range(1, len(voltage_array)):
            if voltage_array[i-1] < mean <= voltage_array[i]:
                zero_crossings += 1
        
        # Calculate frequency: crossings per period * periods per second
        dt = time_array[1] - time_array[0] if len(time_array) > 1 else 1.0
        total_time = time_array[-1] - time_array[0] if len(time_array) > 1 else 1.0
        
        if total_time > 0 and zero_crossings > 0:
            frequency = zero_crossings / total_time
            return frequency
        
        return 0.0
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get oscilloscope status information.
        
        Returns:
            dict: Status dictionary containing connection, model, etc.
        """
        status = {
            'connected': self.is_connected(),
        }
        
        if self.is_connected():
            try:
                status['idn'] = self.idn()
                status['error'] = self.error_query()
                status['ch1_scale'] = self.get_channel_scale(1)
                status['ch2_scale'] = self.get_channel_scale(2)
                status['timebase_scale'] = self.get_timebase_scale()
                status['trigger_mode'] = self.get_trigger_mode()
            except Exception as e:
                status['error'] = str(e)
        
        return status
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


# Example usage
if __name__ == "__main__":
    """
    Example usage of the GW Instek GDS-2062 oscilloscope controller.
    """
    # Update with your VISA resource string
    VISA_RESOURCE = "USB0::......INSTR"
    
    print("GW Instek GDS-2062 Oscilloscope Test")
    print("=" * 50)
    
    # Initialize and connect
    scope = GWInstekGDS2062(resource=VISA_RESOURCE)
    
    if not scope.connect():
        print("Failed to connect to oscilloscope")
        exit(1)
    
    try:
        # Get identification
        print(f"Connected to: {scope.idn()}")
        
        # Autoscale
        print("\nRunning autoscale...")
        scope.autoscale()
        
        # Configure channels
        print("Configuring channels...")
        scope.channel_display(1, True)
        scope.channel_display(2, False)
        scope.set_channel_coupling(1, 'DC')
        
        # Configure trigger
        print("Configuring trigger...")
        scope.set_trigger_mode('AUTO')
        scope.set_trigger_source('CH1')
        scope.set_trigger_level(0.0)
        
        # Wait for acquisition
        time.sleep(2)
        
        # Acquire waveform from CH1
        print("\nAcquiring waveform from CH1...")
        time_array, voltage_array = scope.acquire_waveform(1, format='ASCII')
        print(f"Acquired {len(voltage_array)} data points")
        if len(voltage_array) > 0:
            print(f"Voltage range: {voltage_array.min():.3f} V to {voltage_array.max():.3f} V")
        
        # Compute statistics from waveform data
        print("\nComputing statistics from waveform data...")
        stats = scope.compute_waveform_statistics(voltage_array)
        print(f"Peak-to-Peak: {stats['vpp']:.3f} V")
        print(f"Mean: {stats['mean']:.3f} V")
        print(f"Max: {stats['vmax']:.3f} V")
        print(f"Min: {stats['vmin']:.3f} V")
        
        freq = scope.compute_frequency(time_array, voltage_array)
        if freq > 0:
            print(f"Estimated frequency: {freq:.2f} Hz")
        
        # Attempt automatic measurements
        print("\nAttempting SCPI automatic measurements...")
        try:
            scope.configure_measurement('VPP', channel=1, measurement_number=1)
            scope.configure_measurement('FREQ', channel=1, measurement_number=2)
            time.sleep(1)
            vpp = scope.read_measurement(1, debug=True)
            frequency = scope.read_measurement(2, debug=True)
            print(f"✓ SCPI VPP: {vpp:.3f} V")
            print(f"✓ SCPI Frequency: {frequency:.3f} Hz")
        except ValueError as e:
            print(f"✗ Automatic measurements not supported")
            print(f"  ({str(e)[:100]})")
            print("\nUsing computed statistics from waveform data instead:")
            print(f"  Calculated Vpp: {stats['vpp']:.3f} V")
            if freq > 0:
                print(f"  Calculated Freq: {freq:.2f} Hz")
        except Exception as e:
            print(f"✗ Measurement error: {e}")
        
        # Check for errors
        try:
            err = scope.error_query()
            if err.startswith("0"):
                print("\nNo errors reported")
            else:
                print(f"Note: {err}")
        except Exception as e:
            print(f"Could not query errors: {e}")
        
    except Exception as e:
        print(f"Error during operation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scope.disconnect()
        print("\nDisconnected from oscilloscope")





