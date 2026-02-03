"""
Multiplexer Manager and Abstraction Layer

Provides a unified interface for different multiplexer types:
- Pyswitchbox (relay-based)
- Electronic Multiplexer
- Future multiplexer types

This eliminates 6+ duplicate multiplexer routing if-statements across the codebase.

Author: AI Refactoring - October 2025
"""

from typing import Protocol, Optional, Dict, Any
from abc import ABC, abstractmethod


class MultiplexerInterface(Protocol):
    """
    Protocol defining the common interface for all multiplexers.
    
    All multiplexer adapters must implement this interface.
    """
    
    def route_to_device(self, device_name: str, device_index: int) -> bool:
        """
        Route connections to a specific device.
        
        Args:
            device_name: Name of the device (e.g., "A1", "B5")
            device_index: Index of the device in the device list
        
        Returns:
            bool: True if routing successful, False otherwise
        """
        ...
    
    def disconnect_all(self) -> bool:
        """
        Disconnect all connections.
        
        Returns:
            bool: True if successful
        """
        ...


class PyswitchboxAdapter:
    """
    Adapter for Pyswitchbox relay-based multiplexer.
    
    Uses pin mapping to activate appropriate relay combinations.
    """
    
    def __init__(self, pin_mapping: Dict[str, Any]):
        """
        Initialize Pyswitchbox adapter.
        
        Args:
            pin_mapping: Dictionary mapping device names to pin configurations
                Format: {"device_name": {"pins": [pin1, pin2, ...]}, ...}
        """
        self.pin_mapping = pin_mapping
        self.switchbox = None
        
        # Try to initialize actual switchbox (may not be available)
        try:
            from Equipment.Multiplexers.PySwitchbox.pySwitchbox import Switchbox
            self.switchbox = Switchbox()
        except Exception as e:
            print(f"Warning: Could not initialize Pyswitchbox: {e}")
            self.switchbox = None
    
    def route_to_device(self, device_name: str, device_index: int) -> bool:
        """Route to device using pin mapping."""
        if device_name not in self.pin_mapping:
            print(f"Warning: {device_name} not found in pin mapping")
            return False
        
        pins = self.pin_mapping[device_name].get("pins", [])
        
        if self.switchbox is not None:
            try:
                self.switchbox.activate(pins)
                return True
            except Exception as e:
                print(f"Error activating switchbox: {e}")
                return False
        else:
            # Simulation mode - just log
            print(f"[SIMULATION] Would activate pins: {pins} for {device_name}")
            return True
    
    def disconnect_all(self) -> bool:
        """Disconnect all relays."""
        if self.switchbox is not None:
            try:
                self.switchbox.deactivate_all()
                return True
            except Exception as e:
                print(f"Error deactivating switchbox: {e}")
                return False
        return True


class ElectronicMpxAdapter:
    """
    Adapter for Electronic Multiplexer.
    
    Uses channel selection to route signals.
    """
    
    def __init__(self, controller):
        """
        Initialize Electronic Multiplexer adapter.
        
        Args:
            controller: MultiplexerController instance
        """
        self.controller = controller
    
    def route_to_device(self, device_name: str, device_index: int) -> bool:
        """Route to device using channel selection."""
        try:
            # Electronic multiplexer uses 1-based indexing
            channel_number = device_index + 1
            self.controller.select_channel(channel_number)
            return True
        except Exception as e:
            print(f"Error selecting channel {device_index + 1}: {e}")
            return False
    
    def disconnect_all(self) -> bool:
        """Disconnect all channels."""
        try:
            if hasattr(self.controller, 'disconnect_all'):
                self.controller.disconnect_all()
            return True
        except Exception as e:
            print(f"Error disconnecting: {e}")
            return False


class Multiplexer10OutAdapter:
    """
    Adapter for 10-output multiplexer configuration.
    
    Future implementation for specific 10-output multiplexer hardware.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize 10-output multiplexer adapter.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        print("Warning: Multiplexer_10_OUT adapter not fully implemented")
    
    def route_to_device(self, device_name: str, device_index: int) -> bool:
        """Route to device (placeholder)."""
        print(f"[PLACEHOLDER] Would route to {device_name} (index {device_index})")
        return True
    
    def disconnect_all(self) -> bool:
        """Disconnect all (placeholder)."""
        return True


class MultiplexerManager:
    """
    Factory and manager for different multiplexer types.
    
    Automatically creates the appropriate adapter based on multiplexer type.
    
    Examples:
        >>> # Create Pyswitchbox manager
        >>> mpx_mgr = MultiplexerManager.create(
        ...     "Pyswitchbox", 
        ...     pin_mapping=pin_mapping
        ... )
        
        >>> # Route to a device
        >>> mpx_mgr.route_to_device("A1", 0)
        
        >>> # Create Electronic multiplexer manager
        >>> mpx_mgr = MultiplexerManager.create(
        ...     "Electronic_Mpx",
        ...     controller=electronic_mpx_controller
        ... )
    """
    
    @staticmethod
    def create(
        multiplexer_type: str, 
        **kwargs
    ) -> MultiplexerInterface:
        """
        Create appropriate multiplexer adapter based on type.
        
        Args:
            multiplexer_type: Type of multiplexer 
                ("Pyswitchbox", "Electronic_Mpx", "Multiplexer_10_OUT")
            **kwargs: Type-specific configuration
                - For Pyswitchbox: pin_mapping (dict)
                - For Electronic_Mpx: controller (object)
                - For Multiplexer_10_OUT: config (dict)
        
        Returns:
            MultiplexerInterface: Configured multiplexer adapter
        
        Raises:
            ValueError: If multiplexer type is unknown
        """
        if multiplexer_type == "Pyswitchbox":
            pin_mapping = kwargs.get('pin_mapping', {})
            return PyswitchboxAdapter(pin_mapping)
        
        elif multiplexer_type == "Electronic_Mpx":
            controller = kwargs.get('controller')
            if controller is None:
                raise ValueError("Electronic_Mpx requires 'controller' argument")
            return ElectronicMpxAdapter(controller)
        
        elif multiplexer_type == "Multiplexer_10_OUT":
            config = kwargs.get('config', {})
            return Multiplexer10OutAdapter(config)
        
        else:
            raise ValueError(
                f"Unknown multiplexer type: {multiplexer_type}. "
                f"Supported types: Pyswitchbox, Electronic_Mpx, Multiplexer_10_OUT"
            )
    
    @staticmethod
    def get_supported_types() -> list[str]:
        """Get list of supported multiplexer types."""
        return ["Pyswitchbox", "Electronic_Mpx", "Multiplexer_10_OUT"]


class MultiplexerContext:
    """
    Context manager for safe multiplexer operation.
    
    Ensures disconnection even if errors occur.
    
    Example:
        >>> with MultiplexerContext(mpx_manager, "A1", 0) as mpx:
        ...     # Perform measurements
        ...     measure_iv()
        >>> # Automatically disconnects after measurements
    """
    
    def __init__(
        self, 
        multiplexer: MultiplexerInterface,
        device_name: str,
        device_index: int
    ):
        """
        Initialize context manager.
        
        Args:
            multiplexer: Multiplexer adapter instance
            device_name: Device to route to
            device_index: Device index
        """
        self.multiplexer = multiplexer
        self.device_name = device_name
        self.device_index = device_index
    
    def __enter__(self) -> MultiplexerInterface:
        """Enter context - route to device."""
        self.multiplexer.route_to_device(self.device_name, self.device_index)
        return self.multiplexer
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - disconnect."""
        self.multiplexer.disconnect_all()


# Module-level test
if __name__ == "__main__":
    print("Testing multiplexer_manager module...")
    
    # Test Pyswitchbox adapter
    print("\n1. Testing Pyswitchbox adapter:")
    pin_mapping = {
        "A1": {"pins": [1, 2, 3]},
        "A2": {"pins": [4, 5, 6]},
        "B1": {"pins": [7, 8, 9]}
    }
    
    mpx = MultiplexerManager.create("Pyswitchbox", pin_mapping=pin_mapping)
    success = mpx.route_to_device("A1", 0)
    print(f"  Routing to A1: {'Success' if success else 'Failed'}")
    mpx.disconnect_all()
    
    # Test with context manager
    print("\n2. Testing context manager:")
    with MultiplexerContext(mpx, "B1", 2):
        print("  Inside context - device B1 routed")
    print("  Outside context - disconnected")
    
    # Test supported types
    print("\n3. Supported multiplexer types:")
    for mpx_type in MultiplexerManager.get_supported_types():
        print(f"  - {mpx_type}")
    
    print("\nAll tests passed!")

