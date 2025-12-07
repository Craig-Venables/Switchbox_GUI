"""
Measurement Context
===================

Encapsulates common parameters used across all measurement types for consistent
handling of optical control, stopping conditions, callbacks, and source modes.

Author: Unified Measurement Strategy Refactor
"""

from dataclasses import dataclass
from typing import Optional, Callable, Iterable
from Measurments.source_modes import SourceMode


@dataclass
class MeasurementContext:
    """
    Context object for measurement operations.
    
    Groups common parameters used across all measurement types:
    - Optical/LED control
    - Stopping conditions and callbacks
    - Source mode (voltage/current)
    - Error handling preferences
    
    Examples:
        >>> # Simple IV sweep context
        >>> ctx = MeasurementContext(
        ...     led=True,
        ...     power=1.5,
        ...     on_point=lambda v, i, t: print(f"V={v}, I={i}")
        ... )
        >>> 
        >>> # Context with sequence
        >>> ctx = MeasurementContext(
        ...     led=True,
        ...     sequence=['1', '0', '1', '0'],
        ...     source_mode=SourceMode.VOLTAGE
        ... )
    """
    
    # Optical/LED control
    led: bool = False
    power: float = 1.0
    sequence: Optional[Iterable[str]] = None
    
    # Source mode
    source_mode: SourceMode = SourceMode.VOLTAGE
    
    # Callbacks
    should_stop: Optional[Callable[[], bool]] = None
    on_point: Optional[Callable[[float, float, float], None]] = None
    
    def get_led_state_for_sweep(self, sweep_idx: int) -> str:
        """
        Get LED state for a specific sweep index.
        
        Args:
            sweep_idx: Zero-based sweep index
            
        Returns:
            '1' if LED should be on, '0' if off
        """
        if not self.led:
            return '0'
        
        if self.sequence is None:
            return '1'
        
        try:
            seq_list = list(self.sequence)
            if sweep_idx < len(seq_list):
                return str(seq_list[sweep_idx])
        except Exception:
            pass
        
        return '1' if self.led else '0'
    
    def check_stop(self) -> bool:
        """Check if measurement should stop."""
        if self.should_stop is None:
            return False
        try:
            return self.should_stop()
        except Exception:
            return False
    
    def call_on_point(self, v: float, i: float, t: float) -> None:
        """Call on_point callback if provided."""
        if self.on_point is not None:
            try:
                self.on_point(v, i, t)
            except Exception:
                pass



