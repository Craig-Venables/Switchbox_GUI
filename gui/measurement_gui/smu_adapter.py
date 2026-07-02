"""Thin adapter wrapping IVControllerManager for child tools and testers."""

from __future__ import annotations

from typing import Any, Optional


class SMUAdapter:
    """Minimal SMU-like API over an IV controller manager instance."""

    def __init__(self, iv_manager: Any) -> None:
        self._iv = iv_manager
        self.device = None
        try:
            inst = getattr(self._iv, "instrument", None)
            if inst is not None and hasattr(inst, "device"):
                self.device = inst.device
        except Exception:
            self.device = None

    def safe_init(self) -> None:
        return None

    def set_voltage(self, voltage: float, Icc: Optional[float] = None) -> None:
        if Icc is None:
            Icc = 1e-3
        return self._iv.set_voltage(voltage, Icc)

    def set_current(self, current: float, Vcc: Optional[float] = None) -> None:
        if Vcc is None:
            Vcc = 10.0
        return self._iv.set_current(current, Vcc)

    def measure_voltage(self) -> float:
        val = self._iv.measure_voltage()
        try:
            if isinstance(val, (list, tuple)):
                return float(val[0] if len(val) > 0 else 0.0)
            return float(val)
        except Exception:
            return 0.0

    def measure_current(self) -> float:
        val = self._iv.measure_current()
        try:
            if isinstance(val, (list, tuple)):
                return float(val[-1])
            return float(val)
        except Exception:
            return 0.0

    def enable_output(self, enable: bool) -> None:
        return self._iv.enable_output(bool(enable))

    def close(self) -> None:
        try:
            return self._iv.close()
        except Exception:
            return None

    def run_tsp_sweep(
        self,
        start_v: float,
        stop_v: float,
        step_v: float,
        icc_start: float,
        icc_factor: float = 10.0,
        icc_max: Optional[float] = None,
        delay_s: float = 0.005,
        burn_abort_A: Optional[float] = None,
    ) -> Any:
        inst = getattr(self._iv, "instrument", None)
        if inst is not None and hasattr(inst, "run_tsp_sweep"):
            return inst.run_tsp_sweep(
                start_v=start_v,
                stop_v=stop_v,
                step_v=step_v,
                icc_start=icc_start,
                icc_factor=icc_factor,
                icc_max=icc_max,
                delay_s=delay_s,
                burn_abort_A=burn_abort_A,
            )
        raise NotImplementedError("Underlying instrument does not support run_tsp_sweep")
