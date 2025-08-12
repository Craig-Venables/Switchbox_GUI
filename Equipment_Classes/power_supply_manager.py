from __future__ import annotations

from typing import Dict, Any

from Equipment_Classes.PowerSupplies.Keithley2220 import Keithley2220_Powersupply


class PowerSupplyManager:
    """Simple manager to unify power supply drivers behind a common API.

    Add more supplies by extending SUPPORTED and ensuring each driver exposes:
      - set_voltage(channel, voltage)
      - set_current(channel, current)
      - enable_channel(channel)
      - disable_channel(channel)
      - get_output_voltage(channel)
      - get_output_current(channel)
      - close()
    """

    SUPPORTED: Dict[str, Any] = {
        'Keithley 2220': {
            'class': Keithley2220_Powersupply,
            'address_key': 'psu_address',
        },
    }

    def __init__(self, psu_type: str, address: str) -> None:
        self.psu_type = psu_type
        self.address = address
        self.instrument = self._init_instrument()

    @classmethod
    def from_config(cls, config: Dict[str, Any], default_type: str = 'Keithley 2220') -> 'PowerSupplyManager':
        psu_type = config.get('psu_type', default_type)
        address = config.get('psu_address')
        return cls(psu_type, address)

    def _init_instrument(self):
        meta = self.SUPPORTED.get(self.psu_type)
        if not meta:
            raise ValueError(f"Unsupported PSU Type: {self.psu_type}")
        controller_class = meta['class']
        return controller_class(self.address)

    # Unified pass-throughs
    def set_voltage(self, channel: int, voltage: float):
        return self.instrument.set_voltage(channel, voltage)

    def set_current(self, channel: int, current: float):
        return self.instrument.set_current(channel, current)

    def enable(self, channel: int):
        return self.instrument.enable_channel(channel)

    def disable(self, channel: int):
        return self.instrument.disable_channel(channel)

    def get_output_voltage(self, channel: int) -> float:
        return self.instrument.get_output_voltage(channel)

    def get_output_current(self, channel: int) -> float:
        return self.instrument.get_output_current(channel)

    def close(self):
        if hasattr(self.instrument, 'close'):
            self.instrument.close()


