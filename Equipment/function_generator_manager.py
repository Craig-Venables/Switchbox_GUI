from __future__ import annotations

from typing import Dict, Any, Optional

try:
    from Equipment.Function_Generator.Siglent_SDG1032X import SiglentSDG1032X
except ModuleNotFoundError:
    # Allow running this file directly by adding project root to sys.path
    import os
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from Equipment.Function_Generator.Siglent_SDG1032X import SiglentSDG1032X


class FunctionGeneratorManager:
    """Manager to initialize and unify different function generators behind a common API.

    Primary goals:
      - Provide a stable, minimal surface area for GUIs/tests
      - Make it easy to add new generators (extend SUPPORTED and implement same API)

    Minimal unified interface:
      - connect() / close()
      - is_connected() -> bool
      - get_idn() -> str
      - output(channel: int, enable: bool)
      - set_basic_waveform(channel, wvtype, frequency, amplitude, offset, ...)
      - set_dc_level(channel, level)
      - set_pulse_shape(...)
      - enable_burst(...), disable_burst(...), trigger_now(channel)
      - upload_csv_waveform(...), upload_arb_data(...), set_arb_waveform(...), list_arb_waveforms(...)

    Configuration keys (for from_config):
      - fg_type: human-readable generator type (default: 'Siglent SDG1032X')
      - fg_address: VISA resource string (e.g., 'USB0::...::INSTR' or 'TCPIP0::...::INSTR')
    """

    SUPPORTED: Dict[str, Any] = {
        'Siglent SDG1032X': {
            'class': SiglentSDG1032X,
            'config_address_key': 'fg_address',
            'default_address': 'USB0::0xF4EC::0x1103::INSTR',  # fallback if none provided
        },
    }

    # Cache last working addresses during runtime (per type)
    LAST_KNOWN_ADDRESSES: Dict[str, Optional[str]] = {}

    def __init__(self, fg_type: str, address: Optional[str] = None, auto_connect: bool = True) -> None:
        # Normalize provided type/aliases
        self.fg_type = self._normalize_type(fg_type)
        # Resolve address using provided value, last-known, default, or auto-detect
        self.address = self._resolve_address(self.fg_type, address)
        self.instrument: Optional[SiglentSDG1032X] = None
        self._init_instrument()
        if auto_connect:
            try:
                self.connect()
            except Exception:
                pass

    @classmethod
    def from_config(cls, config: Dict[str, Any], default_type: str = 'Siglent SDG1032X', auto_connect: bool = True) -> 'FunctionGeneratorManager':
        fg_type = config.get('fg_type', default_type)
        # Prefer explicit config address if present
        address = config.get('fg_address')
        return cls(fg_type=fg_type, address=address, auto_connect=auto_connect)

    def _init_instrument(self) -> None:
        meta = self.SUPPORTED.get(self.fg_type)
        if not meta:
            raise ValueError(f"Unsupported Function Generator Type: {self.fg_type}")
        controller_class = meta['class']
        # Siglent driver accepts the VISA resource string as 'resource' in constructor
        self.instrument = controller_class(resource=self.address)

    # ----- Connection management -----
    def connect(self) -> bool:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        ok = bool(self.instrument.connect(self.address))
        if ok:
            # Remember working address for this type
            self.LAST_KNOWN_ADDRESSES[self.fg_type] = self.address
        return ok

    def close(self) -> None:
        if self.instrument and hasattr(self.instrument, 'disconnect'):
            try:
                self.instrument.disconnect()
            except Exception:
                pass

    # ----- Status helpers -----
    def is_connected(self) -> bool:
        inst = getattr(self, 'instrument', None)
        if inst is None:
            return False
        if hasattr(inst, 'is_connected'):
            try:
                return bool(inst.is_connected())
            except Exception:
                return False
        # Fallback: assume connected if we cannot query
        return True

    def get_idn(self) -> str:
        if self.instrument and hasattr(self.instrument, 'idn'):
            try:
                return str(self.instrument.idn())
            except Exception:
                return self.fg_type
        return self.fg_type

    # ----- Pass-throughs to instrument (unified naming) -----
    def output(self, channel: int, enable: bool = True) -> None:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        self.instrument.output(channel, enable)

    def get_output_status(self, channel: int) -> bool:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        # Delegate to driver; returns boolean
        return bool(self.instrument.get_output_status(channel))

    def set_basic_waveform(
        self,
        channel: int,
        wvtype: str = "SINE",
        frequency: Any = "1KHZ",
        amplitude: Any = "1VPP",
        offset: Any = "0V",
        phase_deg: Any = 0,
        duty_cycle: Optional[Any] = None,
    ) -> None:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        self.instrument.set_basic_waveform(
            channel=channel,
            wvtype=wvtype,
            frequency=frequency,
            amplitude=amplitude,
            offset=offset,
            phase_deg=phase_deg,
            duty_cycle=duty_cycle,
        )

    def set_dc_level(self, channel: int, level: Any = "0V") -> None:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        self.instrument.set_dc_level(channel, level)

    def set_pulse_shape(
        self,
        channel: int,
        frequency_hz: Any,
        high_level_v: Any,
        low_level_v: Any,
        pulse_width_s: Optional[Any] = None,
        duty_pct: Optional[Any] = None,
        rise_s: Optional[Any] = None,
        fall_s: Optional[Any] = None,
        delay_s: Optional[Any] = None,
    ) -> None:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        self.instrument.set_pulse_shape(
            channel=channel,
            frequency_hz=frequency_hz,
            high_level_v=high_level_v,
            low_level_v=low_level_v,
            pulse_width_s=pulse_width_s,
            duty_pct=duty_pct,
            rise_s=rise_s,
            fall_s=fall_s,
            delay_s=delay_s,
        )

    def enable_burst(
        self,
        channel: int,
        mode: str = "NCYC",
        cycles: int = 1,
        trigger_source: str = "BUS",
        internal_period: Optional[Any] = None,
        burst_delay_s: Optional[Any] = None,
    ) -> None:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        self.instrument.enable_burst(
            channel=channel,
            mode=mode,
            cycles=cycles,
            trigger_source=trigger_source,
            internal_period=internal_period,
            burst_delay_s=burst_delay_s,
        )

    def disable_burst(self, channel: int) -> None:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        self.instrument.disable_burst(channel)

    def trigger_now(self, channel: int) -> None:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        self.instrument.trigger_now(channel)

    # ----- ARB helpers -----
    def upload_csv_waveform(self, channel: int, csv_filename: str, waveform_name: str = "USER") -> bool:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        return bool(self.instrument.upload_csv_waveform(channel, csv_filename, waveform_name))

    def set_arb_waveform(self, channel: int, waveform_name: str = "USER", index: int = 0) -> None:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        self.instrument.set_arb_waveform(channel, waveform_name=waveform_name, index=index)

    def upload_arb_data(self, channel: int, data: list, waveform_name: str = "USER") -> bool:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        return bool(self.instrument.upload_arb_data(channel, data=data, waveform_name=waveform_name))

    def list_arb_waveforms(self, channel: int) -> Optional[str]:
        if not self.instrument:
            raise RuntimeError("Instrument not initialized")
        try:
            return str(self.instrument.list_arb_waveforms(channel))
        except Exception:
            return None

    # ----- Utility / misc -----
    def reset(self) -> None:
        if self.instrument and hasattr(self.instrument, 'reset'):
            self.instrument.reset()

    def clear_status(self) -> None:
        if self.instrument and hasattr(self.instrument, 'clear_status'):
            self.instrument.clear_status()

    def error_query(self) -> Optional[str]:
        if self.instrument and hasattr(self.instrument, 'error_query'):
            try:
                return str(self.instrument.error_query())
            except Exception:
                return None
        return None

    # ----- Address helpers -----
    @classmethod
    def _normalize_type(cls, fg_type: str) -> str:
        key = (fg_type or '').strip().lower().replace(' ', '')
        # Simple aliasing so 'SiglentSDG1032X' maps to canonical key
        aliases = {
            'siglentsdg1032x': 'Siglent SDG1032X',
        }
        return aliases.get(key, fg_type)

    @classmethod
    def _resolve_address(cls, fg_type: str, provided: Optional[str]) -> Optional[str]:
        if provided:
            return provided
        # Last known address in this process
        last = cls.LAST_KNOWN_ADDRESSES.get(fg_type)
        if last:
            return last
        # Per-type default
        meta = cls.SUPPORTED.get(fg_type) or {}
        default_addr = meta.get('default_address')
        if default_addr:
            return default_addr
        # Try auto-detect via VISA as a final fallback
        autodetected = cls._auto_detect_address(fg_type)
        return autodetected

    @classmethod
    def _auto_detect_address(cls, fg_type: str) -> Optional[str]:
        try:
            import pyvisa  # lazy import
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
        except Exception:
            return None

        # Basic heuristics per type
        if fg_type == 'Siglent SDG1032X':
            # Prefer USB resources with Siglent vendor ID 0xF4EC if available
            usb_siglent = [r for r in resources if ('USB' in r and ('0xF4EC' in r.upper() or 'SIGLENT' in r.upper()))]
            if usb_siglent:
                return usb_siglent[0]
            # Otherwise, any USB or TCPIP instrument
            for r in resources:
                if r.startswith('USB') or r.startswith('TCPIP'):
                    return r
        # Unknown type: best-effort first VISA resource
        return resources[0] if resources else None

    # ----- Convenience constructors -----
    @classmethod
    def from_name(cls, name: str, auto_connect: bool = True) -> 'FunctionGeneratorManager':
        """Create manager by type name only; address is resolved from cache/default/detection."""
        return cls(fg_type=name, address=None, auto_connect=auto_connect)



if __name__ == "__main__":
    # Simple connectivity test
    VISA_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"
    mgr = FunctionGeneratorManager(fg_type="Siglent SDG1032X", address=VISA_RESOURCE, auto_connect=False)
    connected = mgr.connect()
    print(f"Connected: {connected}")
    if connected:
        try:
            print(f"IDN: {mgr.get_idn()}")
            mgr.clear_status()
            err = mgr.error_query()
            if err is not None:
                print(f"Instrument error: {err}")
        except Exception as e:
            print(f"Runtime error during test: {e}")
        finally:
            mgr.close()