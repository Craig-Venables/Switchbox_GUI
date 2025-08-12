from __future__ import annotations

import time
from typing import Optional, Dict, Any

from Equipment_Classes.SMU.Keithley2400 import Keithley2400Controller
from Equipment_Classes.SMU.HP4140B import HP4140BController
from Equipment_Classes.SMU.Keithley4200A_KXCI import Keithley4200A_KXCI


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
    SMU Type can be 'Keithley 2400' or 'Hp4140b'.
    """

    SUPPORTED: Dict[str, Any] = {
        'Keithley 2400': {
            'class': Keithley2400Controller,
            'address_key': 'SMU_address',
        },
        'Hp4140b': {
            'class': HP4140BController,
            'address_key': 'SMU_address',
        },
        'Keithley 4200A': {
            'class': Keithley4200A_KXCI,
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
        # Normalize to a tuple where index [1] is current, to match existing GUI usage
        if isinstance(value, (list, tuple)):
            # Try to use last element as current if length >= 1
            try:
                return (None, float(value[-1]))
            except Exception:
                pass
        try:
            return (None, float(value))
        except Exception:
            return (None, float('nan'))

    def enable_output(self, enable: bool = True):
        return self.instrument.enable_output(enable)

    def shutdown(self):
        if hasattr(self.instrument, 'shutdown'):
            return self.instrument.shutdown()

    def close(self):
        if hasattr(self.instrument, 'close'):
            self.instrument.close()

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


