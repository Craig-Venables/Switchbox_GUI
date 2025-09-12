import time
import pyvisa
from typing import Optional, Dict, Any

# Import your controller classes

try:
    from Equipment_Classes.TempControllers.OxfordITC4 import OxfordITC4
    from Equipment_Classes.TempControllers.Lakeshore355 import Lakeshore335Controller
except ModuleNotFoundError:
    # Allow running this file directly by adding project root to sys.path
    import os
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from Equipment_Classes.TempControllers.OxfordITC4 import OxfordITC4
    from Equipment_Classes.TempControllers.Lakeshore355 import Lakeshore335Controller


class TemperatureControllerManager:
    """
    Manager class that automatically detects and manages temperature controllers.
    Supports both Lakeshore 335 (GPIB) and Oxford ITC4 (Serial).
    """

    # Controller configurations
    CONTROLLER_CONFIGS = [
        {
            'class': Lakeshore335Controller,
            'type': 'GPIB',
            'addresses': [17,12, 13],  # Common GPIB addresses
            'name': 'Lakeshore 335',
            'test_method': 'get_temperature_celsius'
        },
        {
            'class': OxfordITC4,
            'type': 'Serial',
            'addresses': ['ASRL12::INSTR', 'ASRL13::INSTR', 'COM12', 'COM13'],  # Common serial ports
            'name': 'Oxford ITC4',
            'test_method': 'get_temperature_celsius'
        }
    ]

    def __init__(self, auto_detect: bool = True, controller_type: Optional[str] = None,
                 address: Optional[str] = None):
        """
        Initialize the temperature controller manager.

        Args:
            auto_detect: If True, automatically detect connected controller
            controller_type: Manual controller type ('Lakeshore335' or 'OxfordITC4')
            address: Manual address (GPIB number or serial port)
        """
        self.controller = None
        self.controller_type = None
        self.controller_config = None
        self.address = None

        # Temperature caching
        self.last_temperature = 25.0
        self.last_read_time = 0
        self.cache_duration = 1.0  # Cache for 1 second to reduce communication

        if auto_detect:
            self.auto_detect_controller()
        elif controller_type and address:
            self.manual_init_controller(controller_type, address)

    def auto_detect_controller(self) -> bool:
        """
        Automatically detect which temperature controller is connected.

        Returns:
            bool: True if controller found, False otherwise
        """
        print("Scanning for temperature controllers...")

        # Try each controller type
        for config in self.CONTROLLER_CONFIGS:
            controller_class = config['class']

            for address in config['addresses']:
                print(f"Trying {config['name']} at {address}...", end=' ')

                try:
                    # Initialize controller based on type
                    if config['type'] == 'GPIB':
                        controller = controller_class(gpib_address=int(address))
                    elif config['type'] == 'Serial':
                        controller = controller_class(port=address)
                    else:
                        continue

                    # Test the connection
                    test_temp = controller.get_temperature_celsius()

                    if test_temp is not None and test_temp != 25.0:  # Valid reading
                        self.controller = controller
                        self.controller_type = config['name']
                        self.controller_config = config
                        self.address = address

                        print(f"✓ Success!")
                        print(f"Connected to {config['name']} at {address}")
                        print(f"Current temperature: {test_temp:.1f}°C")
                        return True
                    else:
                        controller.close()
                        print("✗")

                except Exception as e:
                    print(f"✗ ({str(e)[:30]}...)")
                    continue

        print("No temperature controller detected. Using default 25°C.")
        return False

    def manual_init_controller(self, controller_type: str, address: str) -> bool:
        """
        Manually initialize a specific controller.

        Args:
            controller_type: 'Lakeshore335' or 'OxfordITC4'
            address: GPIB address (e.g., '12') or serial port (e.g., 'ASRL12::INSTR')

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

            if config['type'] == 'GPIB':
                self.controller = controller_class(gpib_address=int(address))
            elif config['type'] == 'Serial':
                self.controller = controller_class(port=address)

            # Test connection
            test_temp = self.controller.get_temperature_celsius()
            if test_temp is not None:
                self.controller_type = config['name']
                self.controller_config = config
                self.address = address
                print(f"Connected to {config['name']} at {address}")
                return True
            else:
                self.controller.close()
                self.controller = None
                return False

        except Exception as e:
            print(f"Failed to connect to {controller_type}: {e}")
            return False

    def get_temperature_celsius(self, channel: str = 'B', use_cache: bool = True) -> float:
        """
        Get temperature in Celsius.

        Args:
            channel: Channel to read ('A', 'B', etc.)
            use_cache: If True, use cached value if recent

        Returns:
            float: Temperature in Celsius
        """
        current_time = time.time()

        # Use cached value if recent enough
        if use_cache and (current_time - self.last_read_time) < self.cache_duration:
            return self.last_temperature

        if self.controller:
            try:
                temp = self.controller.get_temperature_celsius(channel)
                if temp is not None:
                    self.last_temperature = temp
                    self.last_read_time = current_time
                    return temp
            except Exception as e:
                print(f"Error reading temperature: {e}")
                return self.last_temperature

        return 25.0  # Default room temperature

    def get_temperature_kelvin(self, channel: str = 'A') -> float:
        """Get temperature in Kelvin."""
        return self.get_temperature_celsius(channel) + 273.15

    def set_temperature_setpoint(self, temperature: float, in_celsius: bool = True) -> bool:
        """
        Set temperature setpoint if controller supports it.

        Args:
            temperature: Target temperature
            in_celsius: If True, temperature is in Celsius, otherwise Kelvin

        Returns:
            bool: True if successful
        """
        if not self.controller:
            return False

        try:
            if self.controller_type == 'Lakeshore 335':
                # Lakeshore expects Kelvin
                temp_k = temperature + 273.15 if in_celsius else temperature
                self.controller.set_setpoint(temp_k)
                return True
            elif self.controller_type == 'Oxford ITC4':
                # Oxford expects Celsius
                temp_c = temperature if in_celsius else temperature - 273.15
                self.controller.set_temperature(temp_c)
                return True
        except Exception as e:
            print(f"Error setting temperature: {e}")
            return False

    def get_controller_info(self) -> Dict[str, Any]:
        """Get information about the connected controller."""
        if self.controller:
            return {
                'connected': True,
                'type': self.controller_type,
                'address': self.address,
                'id': self.controller.get_idn() if hasattr(self.controller, 'get_idn') else 'N/A',
                'temperature': self.get_temperature_celsius()
            }
        else:
            return {
                'connected': False,
                'type': None,
                'address': None,
                'id': None,
                'temperature': 25.0
            }

    def is_connected(self) -> bool:
        """Check if a controller is connected."""
        return self.controller is not None

    def close(self):
        """Close connection to the controller."""
        if self.controller:
            try:
                self.controller.close()
                print(f"Closed connection to {self.controller_type}")
            except:
                pass
            self.controller = None
            self.controller_type = None


# Example usage
if __name__ == "__main__":
    # Auto-detect controller
    temp_mgr = TemperatureControllerManager(auto_detect=True)

    # Get temperature
    if temp_mgr.is_connected():
        temp = temp_mgr.get_temperature_celsius()
        print(f"Current temperature: {temp:.2f}°C")

        # Get controller info
        info = temp_mgr.get_controller_info()
        print(f"Controller info: {info}")

    # Manual initialization example
    # temp_mgr = TemperatureControllerManager(
    #     auto_detect=False,
    #     controller_type='Oxford ITC4',
    #     address='ASRL12::INSTR'
    # )

    temp_mgr.close()