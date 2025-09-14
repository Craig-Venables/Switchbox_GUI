from __future__ import annotations

from typing import Any, Dict, Optional


class LaserManager:
    """Factory/manager for laser controllers.

    Usage:
      mgr = LaserManager.from_config({"driver": "Oxxius", "address": "COM3", "baud": 38400})
      laser = mgr.instrument  # expose vendor-specific API
    """

    SUPPORTED: Dict[str, Dict[str, Any]] = {
        "Oxxius": {
            "class_path": "Equipment.Laser_Controller.oxxius",
            "class_name": "OxxiusLaser",
            "ctor": lambda address, baud: _import_oxxius()(address, baud),
        },
    }

    def __init__(self, driver: str, instrument: Any) -> None:
        self.driver = driver
        self.instrument = instrument

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "LaserManager":
        driver = str(cfg.get("driver", "Oxxius"))
        meta = cls.SUPPORTED.get(driver)
        if not meta:
            raise ValueError(f"Unsupported laser driver: {driver}")
        address = cfg.get("address", "COM3")
        baud = int(cfg.get("baud", 38400))
        instrument = meta["ctor"](address, baud)
        return cls(driver, instrument)


def _import_oxxius():
    from Equipment.Laser_Controller.oxxius import OxxiusLaser  # type: ignore

    def ctor(address: str, baud: int) -> Any:
        return OxxiusLaser(port=address, baud=baud)

    return ctor


