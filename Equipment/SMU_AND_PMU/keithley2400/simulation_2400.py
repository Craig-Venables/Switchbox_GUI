"""
Keithley 2400 Simulation
=========================

This module provides a pure-Python simulation of the Keithley 2400 SourceMeter
that mirrors the public API of `Keithley2400Controller`. It is intended for GUI
and measurement-pipeline testing when real hardware is unavailable.

The simulator focuses on:
* API compatibility – the same methods as the hardware-backed driver are
  available, with similar signatures and return formats.
* Memristor-style behaviour – internal state evolves with applied pulses,
  producing hysteresis-like current/voltage responses.
* Lightweight diagnostics – error handling stubbed so higher layers
  keep working without needing to special-case the simulator.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp `value` inside the inclusive range [low, high]."""
    return max(low, min(high, value))


@dataclass
class MemristorParameters:
    """Group tunable parameters that shape the simulated device response."""

    ron: float = 150.0                 # Low-resistance limit (Ohms)
    roff: float = 1.5e6               # High-resistance limit (Ohms)
    set_threshold: float = 0.9        # |V| above which SET dynamics start (Volts)
    reset_threshold: float = 0.9      # |V| above which RESET dynamics start (Volts)
    set_rate: float = 2.0             # State change per (Volt-second) in SET direction
    reset_rate: float = 2.5           # State change per (Volt-second) in RESET direction
    relax_rate: float = 0.02          # Slow relaxation towards mid state when unbiased
    noise_current: float = 2e-7       # White noise sigma (Amps)
    noise_voltage: float = 2e-4       # Voltage noise sigma (Volts) in current-source mode


class Simulation2400:
    """
    Drop-in simulation of the hardware-backed `Keithley2400Controller`.

    The simulator keeps track of an internal memristor state `w` in [0, 1].  A
    `w` close to 0 represents a high-resistance state (HRS) while a value near 1
    represents a low-resistance state (LRS).  Applying sufficiently large SET
    pulses pushes `w` towards 1; RESET pulses move it towards 0.  During idle
    periods the state relaxes slowly towards an intermediate value.

    Methods intentionally mirror the public surface of the production driver so
    the GUI and measurement services can be exercised without modification.
    """

    def __init__(
        self,
        gpib_address: str = "SIM::GPIB0::24::INSTR",
        timeout: int = 5,
        *,
        params: Optional[MemristorParameters] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.gpib_address = gpib_address
        self.timeout = timeout
        self.params = params or MemristorParameters()
        
        # PyMeasure compatibility - simulate device object
        self.device = self
        
        # Ensure device is not None for connection checks
        if self.device is None:
            self.device = self
        
        if seed is not None:
            random.seed(seed)

        self._output_enabled: bool = False
        self._source_mode: str = "voltage"  # 'voltage' or 'current'
        self._source_level: float = 0.0
        self._current_limit: float = 0.1     # Amps
        self._voltage_limit: float = 40.0    # Volts for current-source mode
        self._last_update: float = time.time()
        
        # Range configuration
        self._configured = False
        self._cached_icc: Optional[float] = None
        self._cached_vrange: Optional[float] = None
        self._range_lock: Optional[float] = None

        self._state_w: float = 0.2           # Start slightly conductive

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _resistance(self) -> float:
        """Return instantaneous resistance based on the memristor state."""
        w = _clamp(self._state_w, 0.0, 1.0)
        ron = self.params.ron
        roff = self.params.roff
        return w * ron + (1.0 - w) * roff

    def _conductance(self) -> float:
        """Convenience wrapper returning 1 / resistance."""
        resist = self._resistance()
        if resist <= 0.0:
            return 1e6
        return 1.0 / resist

    def _update_state(self) -> None:
        """Evolve memristor state based on elapsed time and applied stimulus."""
        now = time.time()
        dt = max(0.0, now - self._last_update)
        self._last_update = now

        if dt == 0.0:
            return

        # Relaxation towards a mid-state when no strong bias is present.
        def relax(target: float) -> None:
            delta = (target - self._state_w) * self.params.relax_rate * dt
            self._state_w = _clamp(self._state_w + delta, 0.0, 1.0)

        if not self._output_enabled:
            relax(0.3)
            return

        if self._source_mode == "voltage":
            voltage = self._source_level
        else:
            # Approximate equivalent voltage from current source.
            voltage = self._source_level * self._resistance()

        abs_v = abs(voltage)
        if voltage >= self.params.set_threshold:
            delta = self.params.set_rate * (voltage - self.params.set_threshold) * dt
            self._state_w = _clamp(self._state_w + delta, 0.0, 1.0)
        elif voltage <= -self.params.reset_threshold:
            delta = self.params.reset_rate * (abs_v - self.params.reset_threshold) * dt
            self._state_w = _clamp(self._state_w - delta, 0.0, 1.0)
        else:
            relax(0.3)

    # ------------------------------------------------------------------ #
    # Public API mirroring the real driver
    # ------------------------------------------------------------------ #
    def get_idn(self) -> str:
        """Return a simulated identification string."""
        return "KEITHLEY INSTRUMENTS INC.,MODEL 2400-SIM,000001,1.0.0"

    @property
    def id(self) -> str:
        """PyMeasure compatibility - device.id property."""
        return self.get_idn()

    def check_errors(self) -> str:
        """Check instrument error status."""
        return '0,"No error"'

    def _configure_voltage_source(self, icc: float, v_range: float = 20.0) -> None:
        """Configure source range and compliance once or when changed."""
        if (not self._configured) or (self._cached_icc != icc) or (self._cached_vrange != v_range):
            self._current_limit = float(abs(icc))
            self._cached_vrange = float(v_range)
            self._configured = True
            self._cached_icc = float(icc)

    def set_voltage(self, voltage: float, Icc: float = 0.1) -> None:
        """Set source level without reconfiguring range/compliance each time."""
        self._update_state()
        self._source_mode = "voltage"
        self._source_level = float(voltage)
        
        # Select discrete range based on requested level
        if self._range_lock is not None:
            v_rng = float(self._range_lock)
        else:
            v_abs = abs(float(voltage))
            if v_abs <= 0.2:
                v_rng = 0.2
            elif v_abs <= 2.0:
                v_rng = 2.0
            elif v_abs <= 20.0:
                v_rng = 20.0
            else:
                v_rng = 200.0
        
        self._configure_voltage_source(float(Icc), v_rng)
        
        # Auto-enable output
        if not self._output_enabled:
            self._output_enabled = True

    def set_current(self, current: float, Vcc: float = 10.0) -> None:
        """Set current source level."""
        self._update_state()
        self._source_mode = "current"
        self._source_level = float(current)
        self._voltage_limit = float(abs(Vcc))
        if not self._output_enabled:
            self._output_enabled = True

    def measure_voltage(self) -> float:
        """Measure voltage."""
        self._update_state()
        if self._source_mode == "voltage":
            voltage = self._source_level
        else:
            voltage = self._source_level * self._resistance()
            voltage += random.gauss(0.0, self.params.noise_voltage)
            voltage = _clamp(voltage, -self._voltage_limit, self._voltage_limit)
        return float(voltage)

    def measure_current(self) -> float:
        """Measure current."""
        self._update_state()
        if self._source_mode == "current":
            current = self._source_level
        else:
            conductance = self._conductance()
            current = self._source_level * conductance

        # Compliance limiting
        if abs(current) > self._current_limit:
            current = math.copysign(self._current_limit, current)

        current += random.gauss(0.0, self.params.noise_current)
        return float(current)

    def enable_source(self) -> None:
        """Enable source output (PyMeasure compatibility)."""
        self._output_enabled = True

    def enable_output(self, enable: bool = True) -> None:
        """Enable/disable output (common API compatibility)."""
        self._output_enabled = bool(enable)
        if not enable:
            self._source_level = 0.0

    def disable_source(self) -> None:
        """Disable source output (PyMeasure compatibility)."""
        self._output_enabled = False
        self._source_level = 0.0

    @property
    def source_voltage(self) -> float:
        """PyMeasure compatibility - source_voltage property."""
        return self._source_level

    @source_voltage.setter
    def source_voltage(self, value: float) -> None:
        """PyMeasure compatibility - set source_voltage."""
        self.set_voltage(value, self._current_limit)

    def apply_voltage(self, voltage_range: float = 20.0, compliance_current: float = 0.1) -> None:
        """Configure voltage source (PyMeasure compatibility)."""
        self._configure_voltage_source(compliance_current, voltage_range)

    def write(self, command: str) -> None:
        """Simulate SCPI write command."""
        # Parse common commands
        cmd = command.strip().upper()
        
        if cmd.startswith("SOUR:FUNC VOLT"):
            self._source_mode = "voltage"
        elif cmd.startswith("SOUR:FUNC CURR"):
            self._source_mode = "current"
        elif cmd.startswith("SOUR:VOLT:RANG"):
            # Extract range value
            try:
                value = float(cmd.split()[-1])
                self._range_lock = value
                self._cached_vrange = value
            except (ValueError, IndexError):
                pass
        elif cmd.startswith("OUTP:STAT ON") or cmd == "OUTP ON":
            self._output_enabled = True
        elif cmd.startswith("OUTP:STAT OFF") or cmd == "OUTP OFF":
            self._output_enabled = False

    def ask(self, command: str) -> str:
        """Simulate SCPI ask command."""
        cmd = command.strip().upper()
        
        if cmd.startswith("SYST:ERR"):
            return '0,"No error"'
        elif cmd.startswith("*IDN"):
            return self.get_idn()
        elif cmd.startswith("SOUR:VOLT?"):
            return str(self._source_level)
        elif cmd.startswith("MEAS:VOLT?"):
            return str(self.measure_voltage())
        elif cmd.startswith("MEAS:CURR?"):
            return str(self.measure_current())
        else:
            return "0"

    def prepare_for_pulses(
        self,
        Icc: float = 1e-3,
        v_range: float = 20.0,
        ovp: float = 21.0,
        use_remote_sense: bool = False,
        autozero_off: bool = True,
    ) -> None:
        """One-shot prep for pulsed operation."""
        self._configure_voltage_source(float(Icc), float(v_range))
        self._range_lock = float(v_range)
        self._current_limit = float(abs(Icc))
        self.set_voltage(0.0, Icc)
        self._output_enabled = True

    def finish_pulses(self, Icc: float = 1e-3, restore_autozero: bool = True) -> None:
        """Finish pulse session."""
        self.set_voltage(0.0, Icc)
        self._output_enabled = False

    def reset(self) -> None:
        """Reset instrument state."""
        self._output_enabled = False
        self._source_level = 0.0
        self._state_w = 0.2
        self._configured = False
        self._range_lock = None

    def shutdown(self) -> None:
        """Shutdown and cleanup."""
        self.set_voltage(0.0, self._current_limit or 0.1)
        self._output_enabled = False

    def close(self) -> None:
        """Close connection."""
        self.shutdown()


__all__ = [
    "Simulation2400",
    "MemristorParameters",
]

