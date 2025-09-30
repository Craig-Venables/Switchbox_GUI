"""
Agilent 34401A Digital Multimeter Control Script

This script provides a comprehensive interface for controlling the Agilent 34401A
Digital Multimeter through SCPI commands over VISA interface.

Author: Generated for Switchbox_GUI project
"""

import pyvisa
import time
import numpy as np
from typing import Optional, Union, List, Tuple


class Agilent34401A:
    """
    A class to control the Agilent 34401A Digital Multimeter.
    
    This class provides methods for configuring and reading measurements
    from the Agilent 34401A DMM via VISA communication.
    """
    
    def __init__(self, visa_address: str = None, timeout: int = 10000):
        """
        Initialize the Agilent 34401A connection.
        
        Args:
            visa_address (str): VISA address of the device (e.g., 'USB0::0x0957::0x2007::MY12345678::INSTR')
            timeout (int): Communication timeout in milliseconds
        """
        self.rm = pyvisa.ResourceManager()
        self.device = None
        self.visa_address = visa_address
        self.timeout = timeout
        self.connected = False
        
        if visa_address:
            self.connect(visa_address)
    
    def connect(self, visa_address: str = None) -> bool:
        """
        Connect to the Agilent 34401A device.
        
        Args:
            visa_address (str): VISA address of the device
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if visa_address:
                self.visa_address = visa_address
            
            if not self.visa_address:
                raise ValueError("No VISA address provided")
            
            self.device = self.rm.open_resource(self.visa_address)
            self.device.timeout = self.timeout
            
            # Test connection by querying device identity
            idn = self.device.query('*IDN?').strip()
            if '34401A' in idn or '34401' in idn:
                self.connected = True
                print(f"Connected to: {idn}")
                return True
            else:
                print(f"Warning: Connected device may not be a 34401A. ID: {idn}")
                self.connected = True
                return True
                
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from the device."""
        if self.device:
            self.device.close()
            self.connected = False
            print("Disconnected from Agilent 34401A")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def reset(self):
        """Reset the device to default settings."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        self.device.write('*RST')
        time.sleep(1)  # Allow time for reset
    
    def get_identity(self) -> str:
        """Get device identification string."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return self.device.query('*IDN?').strip()
    
    def self_test(self) -> bool:
        """Perform device self-test."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        result = self.device.query('*TST?').strip()
        return result == '0'  # 0 indicates pass
    
    def clear_status(self):
        """Clear device status registers."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        self.device.write('*CLS')
    
    # Measurement Configuration Methods
    
    def configure_dc_voltage(self, range_val: Optional[float] = None, resolution: Optional[int] = None):
        """
        Configure for DC voltage measurement.
        
        Args:
            range_val (float): Voltage range (0.1, 1, 10, 100, 1000). None for auto range.
            resolution (int): Resolution in digits (4-6). None for default.
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        if range_val:
            self.device.write(f'CONF:VOLT:DC {range_val}')
        else:
            self.device.write('CONF:VOLT:DC')
        
        if resolution:
            self.device.write(f'VOLT:DC:RES {resolution}')
    
    def configure_ac_voltage(self, range_val: Optional[float] = None, resolution: Optional[int] = None):
        """
        Configure for AC voltage measurement.
        
        Args:
            range_val (float): Voltage range (0.1, 1, 10, 100, 1000). None for auto range.
            resolution (int): Resolution in digits (4-6). None for default.
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        if range_val:
            self.device.write(f'CONF:VOLT:AC {range_val}')
        else:
            self.device.write('CONF:VOLT:AC')
        
        if resolution:
            self.device.write(f'VOLT:AC:RES {resolution}')
    
    def configure_dc_current(self, range_val: Optional[float] = None, resolution: Optional[int] = None):
        """
        Configure for DC current measurement.
        
        Args:
            range_val (float): Current range (0.1e-3, 1e-3, 10e-3, 100e-3, 1, 3). None for auto range.
            resolution (int): Resolution in digits (4-6). None for default.
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        if range_val:
            self.device.write(f'CONF:CURR:DC {range_val}')
        else:
            self.device.write('CONF:CURR:DC')
        
        if resolution:
            self.device.write(f'CURR:DC:RES {resolution}')
    
    def configure_ac_current(self, range_val: Optional[float] = None, resolution: Optional[int] = None):
        """
        Configure for AC current measurement.
        
        Args:
            range_val (float): Current range (0.1e-3, 1e-3, 10e-3, 100e-3, 1, 3). None for auto range.
            resolution (int): Resolution in digits (4-6). None for default.
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        if range_val:
            self.device.write(f'CONF:CURR:AC {range_val}')
        else:
            self.device.write('CONF:CURR:AC')
        
        if resolution:
            self.device.write(f'CURR:AC:RES {resolution}')
    
    def configure_resistance(self, range_val: Optional[float] = None, resolution: Optional[int] = None):
        """
        Configure for resistance measurement.
        
        Args:
            range_val (float): Resistance range (100, 1000, 10000, 100000, 1000000, 10000000, 100000000). None for auto range.
            resolution (int): Resolution in digits (4-6). None for default.
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        if range_val:
            self.device.write(f'CONF:RES {range_val}')
        else:
            self.device.write('CONF:RES')
        
        if resolution:
            self.device.write(f'RES:RES {resolution}')
    
    def configure_frequency(self, voltage_range: Optional[float] = None):
        """
        Configure for frequency measurement.
        
        Args:
            voltage_range (float): Voltage range for frequency measurement. None for auto range.
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        if voltage_range:
            self.device.write(f'CONF:FREQ {voltage_range}')
        else:
            self.device.write('CONF:FREQ')
    
    # Reading Methods
    
    def read_voltage_dc(self) -> float:
        """Read DC voltage measurement."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return float(self.device.query('READ?').strip())
    
    def read_voltage_ac(self) -> float:
        """Read AC voltage measurement."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return float(self.device.query('READ?').strip())
    
    def read_current_dc(self) -> float:
        """Read DC current measurement."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return float(self.device.query('READ?').strip())
    
    def read_current_ac(self) -> float:
        """Read AC current measurement."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return float(self.device.query('READ?').strip())
    
    def read_resistance(self) -> float:
        """Read resistance measurement."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return float(self.device.query('READ?').strip())
    
    def read_frequency(self) -> float:
        """Read frequency measurement."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return float(self.device.query('READ?').strip())
    
    def read_measurement(self) -> float:
        """Read the currently configured measurement."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return float(self.device.query('READ?').strip())
    
    # Trigger and Sampling Methods
    
    def set_trigger_source(self, source: str = 'IMM'):
        """
        Set trigger source.
        
        Args:
            source (str): 'IMM' for immediate, 'EXT' for external, 'BUS' for bus trigger
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        valid_sources = ['IMM', 'EXT', 'BUS']
        if source not in valid_sources:
            raise ValueError(f"Invalid trigger source. Must be one of: {valid_sources}")
        
        self.device.write(f'TRIG:SOUR {source}')
    
    def trigger_measurement(self):
        """Trigger a single measurement."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        self.device.write('INIT')
    
    def wait_for_completion(self, timeout: float = 10.0) -> bool:
        """
        Wait for measurement completion.
        
        Args:
            timeout (float): Timeout in seconds
            
        Returns:
            bool: True if completed, False if timeout
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.device.query('*OPC?').strip() == '1':
                return True
            time.sleep(0.1)
        return False
    
    def read_and_wait(self, timeout: float = 10.0) -> float:
        """
        Trigger measurement, wait for completion, and read result.
        
        Args:
            timeout (float): Timeout in seconds
            
        Returns:
            float: Measurement result
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        self.trigger_measurement()
        if self.wait_for_completion(timeout):
            return self.read_measurement()
        else:
            raise TimeoutError("Measurement timed out")
    
    # Range and Resolution Methods
    
    def set_range(self, range_val: float):
        """Set measurement range."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        self.device.write(f'RANG {range_val}')
    
    def set_auto_range(self, auto: bool = True):
        """Enable or disable auto range."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        self.device.write(f'RANG:AUTO {"ON" if auto else "OFF"}')
    
    def set_resolution(self, resolution: int):
        """Set measurement resolution in digits (4-6)."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        if not 4 <= resolution <= 6:
            raise ValueError("Resolution must be between 4 and 6 digits")
        
        self.device.write(f'RES {resolution}')
    
    def get_range(self) -> float:
        """Get current measurement range."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return float(self.device.query('RANG?').strip())
    
    def get_resolution(self) -> int:
        """Get current measurement resolution."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        return int(self.device.query('RES?').strip())
    
    # Utility Methods
    
    def get_status(self) -> dict:
        """Get device status information."""
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        status = {}
        try:
            status['identity'] = self.get_identity()
            status['range'] = self.get_range()
            status['resolution'] = self.get_resolution()
            status['auto_range'] = self.device.query('RANG:AUTO?').strip() == '1'
            status['trigger_source'] = self.device.query('TRIG:SOUR?').strip()
        except Exception as e:
            status['error'] = str(e)
        
        return status
    
    def scan_multiple_measurements(self, measurements: List[str], count: int = 1, delay: float = 0.1) -> List[List[float]]:
        """
        Perform multiple different measurements in sequence.
        
        Args:
            measurements (List[str]): List of measurement types ['DC_VOLT', 'AC_VOLT', 'DC_CURR', 'AC_CURR', 'RES', 'FREQ']
            count (int): Number of readings per measurement type
            delay (float): Delay between measurements in seconds
            
        Returns:
            List[List[float]]: List of measurement results for each type
        """
        if not self.connected:
            raise RuntimeError("Device not connected")
        
        results = []
        measurement_configs = {
            'DC_VOLT': lambda: self.configure_dc_voltage(),
            'AC_VOLT': lambda: self.configure_ac_voltage(),
            'DC_CURR': lambda: self.configure_dc_current(),
            'AC_CURR': lambda: self.configure_ac_current(),
            'RES': lambda: self.configure_resistance(),
            'FREQ': lambda: self.configure_frequency()
        }
        
        for measurement in measurements:
            if measurement not in measurement_configs:
                raise ValueError(f"Invalid measurement type: {measurement}")
            
            measurement_configs[measurement]()
            measurement_results = []
            
            for _ in range(count):
                result = self.read_and_wait()
                measurement_results.append(result)
                if delay > 0:
                    time.sleep(delay)
            
            results.append(measurement_results)
        
        return results


# Example usage and testing functions

def example_basic_usage():
    """Example of basic usage of the Agilent34401A class."""
    print("=== Agilent 34401A Basic Usage Example ===")
    
    # Replace with your actual VISA address
    visa_address = "USB0::0x0957::0x2007::MY12345678::INSTR"
    
    try:
        # Using context manager for automatic cleanup
        with Agilent34401A(visa_address) as dmm:
            # Get device information
            print(f"Connected to: {dmm.get_identity()}")
            
            # Perform self-test
            if dmm.self_test():
                print("Self-test: PASSED")
            else:
                print("Self-test: FAILED")
            
            # Configure for DC voltage measurement
            dmm.configure_dc_voltage(range_val=10.0, resolution=6)
            print(f"Configured for DC voltage measurement")
            print(f"Current range: {dmm.get_range()} V")
            print(f"Current resolution: {dmm.get_resolution()} digits")
            
            # Take a measurement
            voltage = dmm.read_and_wait()
            print(f"DC Voltage reading: {voltage:.6f} V")
            
            # Switch to resistance measurement
            dmm.configure_resistance()
            resistance = dmm.read_and_wait()
            print(f"Resistance reading: {resistance:.3f} Ω")
            
            # Get device status
            status = dmm.get_status()
            print(f"Device status: {status}")
    
    except Exception as e:
        print(f"Error: {e}")


def example_multiple_measurements():
    """Example of performing multiple measurement types."""
    print("\n=== Multiple Measurements Example ===")
    
    visa_address = "USB0::0x0957::0x2007::MY12345678::INSTR"
    
    try:
        with Agilent34401A(visa_address) as dmm:
            # Perform multiple measurement types
            measurement_types = ['DC_VOLT', 'RES', 'DC_CURR']
            results = dmm.scan_multiple_measurements(measurement_types, count=3, delay=0.5)
            
            for i, (measurement_type, measurement_results) in enumerate(zip(measurement_types, results)):
                avg_result = np.mean(measurement_results)
                std_result = np.std(measurement_results)
                print(f"{measurement_type}: {measurement_results} (Avg: {avg_result:.6f}, Std: {std_result:.6f})")
    
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Run examples
    print("Agilent 34401A Digital Multimeter Control Script")
    print("=" * 50)
    
    # Note: Uncomment and modify the VISA address to test with actual hardware
    # example_basic_usage()
    # example_multiple_measurements()
    
    print("\nTo use this script with actual hardware:")
    print("1. Install required packages: pip install pyvisa numpy")
    print("2. Connect your Agilent 34401A via USB or GPIB")
    print("3. Find the VISA address using: python -m visa info")
    print("4. Update the visa_address variable in the examples")
    print("5. Uncomment the example function calls above")

