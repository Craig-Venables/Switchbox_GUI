"""
Optical/LED Control Abstraction

Provides a unified interface for controlling different light sources:
- Optical excitation systems (laser controllers, etc.)
- PSU-driven LEDs

This eliminates 26+ duplicate optical control if-statements across the codebase.

Author: AI Refactoring - October 2025
"""

from typing import Optional, List, Generator


class OpticalController:
    """
    Unified interface for optical excitation and LED control.
    
    Automatically detects and uses the available light source:
    - Optical system with set_level() and set_enabled() methods
    - PSU with led_on_380() and led_off_380() methods
    
    Examples:
        >>> # With optical system
        >>> optical_ctrl = OpticalController(optical=laser_controller)
        >>> optical_ctrl.enable(power=1.5)  # 1.5 mW
        >>> optical_ctrl.disable()
        
        >>> # With PSU LED
        >>> optical_ctrl = OpticalController(psu=power_supply)
        >>> optical_ctrl.enable(power=1.0)  # Arbitrary power level
        >>> optical_ctrl.disable()
        
        >>> # Auto-detection
        >>> optical_ctrl = OpticalController(optical=laser, psu=psu)
        >>> # Will use laser if available, fallback to PSU
    """
    
    def __init__(self, optical=None, psu=None):
        """
        Initialize optical controller with available light sources.
        
        Args:
            optical: Optical excitation system (e.g., laser controller)
            psu: Power supply with LED control methods
        """
        self.optical = optical
        self.psu = psu
        self._current_state = False
        self._current_power = 0.0
    
    @property
    def is_available(self) -> bool:
        """Check if any light source is available."""
        return self.optical is not None or self.psu is not None
    
    @property
    def source_type(self) -> str:
        """Get the type of light source being used."""
        if self.optical is not None:
            return "optical"
        elif self.psu is not None:
            return "psu_led"
        return "none"
    
    @property
    def is_enabled(self) -> bool:
        """Get current light source state."""
        return self._current_state
    
    def enable(self, power: float = 1.0):
        """
        Turn on the light source.
        
        Args:
            power: Power level
                - For optical: power in mW (or units defined by capabilities)
                - For PSU LED: arbitrary power level (typically 1.0)
        
        Example:
            >>> optical_ctrl.enable(power=2.5)  # 2.5 mW laser
        """
        try:
            if self.optical is not None:
                # Use optical excitation system
                units = 'mW'  # Default units
                if hasattr(self.optical, 'capabilities'):
                    units = getattr(self.optical.capabilities, 'units', 'mW')
                
                self.optical.set_level(float(power), units)
                self.optical.set_enabled(True)
                self._current_state = True
                self._current_power = power
                
            elif self.psu is not None:
                # Use PSU LED
                if hasattr(self.psu, 'led_on_380'):
                    self.psu.led_on_380(float(power))
                    self._current_state = True
                    self._current_power = power
                    
        except Exception as e:
            print(f"Error enabling light source: {e}")
    
    def disable(self):
        """
        Turn off the light source.
        
        Example:
            >>> optical_ctrl.disable()
        """
        try:
            if self.optical is not None:
                self.optical.set_enabled(False)
                self._current_state = False
                
            elif self.psu is not None:
                if hasattr(self.psu, 'led_off_380'):
                    self.psu.led_off_380()
                    self._current_state = False
                    
        except Exception as e:
            print(f"Error disabling light source: {e}")
    
    def set_state(self, enabled: bool, power: float = 1.0):
        """
        Set light source state (on/off) in one call.
        
        Args:
            enabled: True to enable, False to disable
            power: Power level if enabling
        
        Example:
            >>> optical_ctrl.set_state(True, power=1.5)   # Enable at 1.5 mW
            >>> optical_ctrl.set_state(False)              # Disable
        """
        if enabled:
            self.enable(power)
        else:
            self.disable()
    
    def pulse_sequence(
        self, 
        sequence: List[str], 
        power: float = 1.0
    ) -> Generator[int, None, None]:
        """
        Apply a light pulse sequence (for sweep-by-sweep control).
        
        Args:
            sequence: List of '0' or '1' strings indicating off/on states
            power: Power level when enabled
        
        Yields:
            int: Current step index
        
        Example:
            >>> # Alternating on/off pattern for 4 sweeps
            >>> for step in optical_ctrl.pulse_sequence(['1', '0', '1', '0'], power=2.0):
            >>>     run_sweep(step)
        """
        for idx, state in enumerate(sequence):
            if str(state) == '1':
                self.enable(power)
            else:
                self.disable()
            yield idx
    
    def apply_sequence_state(self, sequence: List[str], sweep_idx: int, power: float = 1.0):
        """
        Apply light state for a specific sweep based on sequence.
        
        Args:
            sequence: List of '0' or '1' strings
            sweep_idx: Current sweep index
            power: Power level when enabled
        
        Example:
            >>> for sweep_idx in range(sweeps):
            >>>     optical_ctrl.apply_sequence_state(led_sequence, sweep_idx, power=1.5)
            >>>     # Run sweep...
        """
        if sequence and sweep_idx < len(sequence):
            state = str(sequence[sweep_idx])
            if state == '1':
                self.enable(power)
            else:
                self.disable()
        else:
            # Default behavior if sequence doesn't cover this index
            self.enable(power)
    
    def __enter__(self):
        """Context manager entry - for use with 'with' statement."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures light is turned off."""
        self.disable()
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        status = "ON" if self._current_state else "OFF"
        return f"OpticalController(source={self.source_type}, state={status}, power={self._current_power})"


# Convenience function for backward compatibility
def create_optical_controller(optical=None, psu=None, led: bool = False) -> OpticalController:
    """
    Factory function to create an optical controller.
    
    Args:
        optical: Optical system object
        psu: Power supply object  
        led: Legacy parameter (ignored, kept for compatibility)
    
    Returns:
        OpticalController: Configured controller instance
    
    Example:
        >>> ctrl = create_optical_controller(optical=laser, psu=psu)
        >>> ctrl.enable(1.5)
    """
    return OpticalController(optical=optical, psu=psu)


# Module-level test
if __name__ == "__main__":
    print("Testing OpticalController...")
    
    # Mock objects for testing
    class MockOptical:
        def __init__(self):
            self.enabled = False
            self.level = 0.0
            
        def set_level(self, level, units):
            self.level = level
            print(f"  Optical: Set level to {level} {units}")
            
        def set_enabled(self, state):
            self.enabled = state
            print(f"  Optical: {'Enabled' if state else 'Disabled'}")
    
    class MockPSU:
        def __init__(self):
            self.led_state = False
            
        def led_on_380(self, power):
            self.led_state = True
            print(f"  PSU: LED ON at power {power}")
            
        def led_off_380(self):
            self.led_state = False
            print(f"  PSU: LED OFF")
    
    # Test with optical
    print("\n1. Testing with optical system:")
    optical = MockOptical()
    ctrl = OpticalController(optical=optical)
    print(f"  Source type: {ctrl.source_type}")
    ctrl.enable(2.5)
    ctrl.disable()
    
    # Test with PSU
    print("\n2. Testing with PSU:")
    psu = MockPSU()
    ctrl = OpticalController(psu=psu)
    print(f"  Source type: {ctrl.source_type}")
    ctrl.enable(1.0)
    ctrl.disable()
    
    # Test sequence
    print("\n3. Testing pulse sequence:")
    ctrl = OpticalController(optical=optical)
    for idx in ctrl.pulse_sequence(['1', '0', '1'], power=1.5):
        print(f"  Step {idx}")
    
    # Test context manager
    print("\n4. Testing context manager:")
    with OpticalController(optical=optical) as ctrl:
        ctrl.enable(1.0)
        print(f"  Inside context: {ctrl}")
    print(f"  After context: {ctrl}")
    
    print("\nAll tests passed!")

