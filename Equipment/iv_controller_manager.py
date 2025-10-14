from __future__ import annotations

import time
from typing import Optional, Dict, Any

from Equipment.SMU_AND_PMU.Keithley2400 import Keithley2400Controller
from Equipment.SMU_AND_PMU.HP4140B import HP4140BController
from Equipment.SMU_AND_PMU.Keithley4200A import Keithley4200AController


class IVControllerManager:
    """Manager to initialize and unify different IV controllers behind a common API.

    Exposes a minimal, consistent interface used by the GUI/test code:
      - set_voltage(voltage: float, Icc: float = ...)
      - set_current(current: float, Vcc: float = ...)
      - measure_voltage() -> float or (float, ...)
      - measure_current() -> float or (float, ...)
      - enable_output(enable: bool)
      - close()

    Also supports manual selection using system_configs entries, where
    SMU_AND_PMU Type can be 'Keithley 2400' or 'Hp4140b'.
    """

    SUPPORTED: Dict[str, Any] = {
        'Keithley 2401': {
            'class': Keithley2400Controller,
            'address_key': 'SMU_address',
        },
        'Hp4140b': {
            'class': HP4140BController,
            'address_key': 'SMU_address',
        },
        'Keithley 4200A': {
            'class': Keithley4200AController,
            'address_key': 'SMU_address',  # Use IP:port string here
        },
    }

    def __init__(self, smu_type: str, address: str) -> None:
        self.instrument = None
        self.smu_type = smu_type
        self.address = address
        self._init_instrument()

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'IVControllerManager':
        smu_type = config.get('SMU Type', 'Keithley 2400')
        address = config.get('SMU_address')
        return cls(smu_type, address)

    def _init_instrument(self) -> None:
        meta = self.SUPPORTED.get(self.smu_type)
        if not meta:
            raise ValueError(f"Unsupported SMU Type: {self.smu_type}")
        controller_class = meta['class']
        # Both controllers accept a single address argument string
        self.instrument = controller_class(self.address)

    # Unified API pass-throughs
    def set_voltage(self, voltage: float, Icc: float = 1e-3):
        return self.instrument.set_voltage(voltage, Icc)

    def set_current(self, current: float, Vcc: float = 10.0):
        return self.instrument.set_current(current, Vcc)

    def measure_voltage(self):
        return self.instrument.measure_voltage()

    def measure_current(self):
        value = self.instrument.measure_current()
        # Only normalize for 4200A so GUI can use current[1]
        if self.smu_type == 'Keithley 4200A':
            try:
                if isinstance(value, (list, tuple)):
                    return (None, float(value[-1]))
                return (None, float(value))
            except Exception:
                return (None, float('nan'))
        return value

    def enable_output(self, enable: bool = True):
        return self.instrument.enable_output(enable)

    def shutdown(self):
        if hasattr(self.instrument, 'shutdown'):
            return self.instrument.shutdown()

    def close(self):
        if hasattr(self.instrument, 'close'):
            self.instrument.close()

    # Connection status helper used by GUI code
    def is_connected(self) -> bool:
        inst = getattr(self, 'instrument', None)
        if inst is None:
            return False
        # Common attributes for our supported controllers
        if hasattr(inst, 'device'):
            return getattr(inst, 'device') is not None
        if hasattr(inst, 'inst'):
            return getattr(inst, 'inst') is not None
        if hasattr(inst, 'sock'):
            return getattr(inst, 'sock') is not None
        # Fallback: assume connected if no known handle is exposed
        return True
    # Optional pass-throughs
    def beep(self, frequency: float = 1000, duration: float = 0.2):
        if hasattr(self.instrument, 'beep'):
            try:
                return self.instrument.beep(frequency, duration)
            except Exception:
                return None

    def get_idn(self) -> str:
        if hasattr(self.instrument, 'get_idn'):
            try:
                return self.instrument.get_idn()
            except Exception:
                return self.smu_type
        return self.smu_type

    # Pulse preparation helpers (only effective on instruments that support them)
    def prepare_for_pulses(self, Icc: float = 1e-3, v_range: float = 20.0, ovp: float = 21.0,
                           use_remote_sense: bool = False, autozero_off: bool = True) -> None:
        inst = getattr(self, 'instrument', None)
        if inst is not None and hasattr(inst, 'prepare_for_pulses'):
            try:
                inst.prepare_for_pulses(Icc=Icc, v_range=v_range, ovp=ovp,
                                        use_remote_sense=use_remote_sense, autozero_off=autozero_off)
            except Exception:
                pass

    def finish_pulses(self, Icc: float = 1e-3, restore_autozero: bool = True) -> None:
        inst = getattr(self, 'instrument', None)
        if inst is not None and hasattr(inst, 'finish_pulses'):
            try:
                inst.finish_pulses(Icc=Icc, restore_autozero=restore_autozero)
            except Exception:
                pass
    
    def get_capabilities(self):
        """
        Return instrument capabilities for sweep optimization.
        
        Returns:
            InstrumentCapabilities: Capabilities object describing instrument features
        
        Example:
            >>> caps = keithley.get_capabilities()
            >>> if caps.supports_hardware_sweep:
            ...     # Use fast hardware sweep
        """
        from Measurments.sweep_config import InstrumentCapabilities
        
        if self.smu_type == 'Keithley 4200A':
            return InstrumentCapabilities(
                supports_hardware_sweep=True,
                supports_arbitrary_sweep=True,
                supports_pulses=True,
                supports_current_source=True,
                min_step_delay_ms=1.0,
                max_points_per_sweep=10000,
                voltage_range=(-200.0, 200.0),
                current_range=(-1.0, 1.0)
            )
        elif self.smu_type in ['Keithley 2401', 'Keithley 2400']:
            return InstrumentCapabilities(
                supports_hardware_sweep=False,
                supports_arbitrary_sweep=False,
                supports_pulses=True,
                supports_current_source=True,
                min_step_delay_ms=50.0,
                max_points_per_sweep=2500,
                voltage_range=(-20.0, 20.0),
                current_range=(-1.0, 1.0)
            )
        elif self.smu_type == 'Hp4140b':
            return InstrumentCapabilities(
                supports_hardware_sweep=False,
                supports_arbitrary_sweep=False,
                supports_pulses=False,
                supports_current_source=True,
                min_step_delay_ms=100.0,
                max_points_per_sweep=1000,
                voltage_range=(-100.0, 100.0),
                current_range=(1e-14, 1e-2)
            )
        else:
            # Default conservative capabilities
            return InstrumentCapabilities()


