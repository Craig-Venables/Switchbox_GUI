"""
Keithley 2450 TSP Simulation
============================

This module provides a pure-Python simulation of the Keithley 2450 SourceMeter
that mirrors the public surface of `Keithley2450_TSP`.  It is intended for GUI
and measurement-pipeline testing when real hardware is unavailable.  The
simulator focuses on:

* API compatibility – the same methods as the hardware-backed driver are
  available, with similar signatures and return formats.
* Memristor-style behaviour – internal state evolves with applied pulses,
  producing hysteresis-like current/voltage responses.
* Lightweight diagnostics – event/error queues are stubbed so higher layers
  keep working without needing to special-case the simulator.

The simulator deliberately avoids wiring itself into any configuration code.
Consumers can instantiate `Keithley2450_TSP_Sim` manually (or via future
factory wiring) and exercise measurement flows exactly as they would with a
physical instrument.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp `value` inside the inclusive range [low, high]."""
    return max(low, min(high, value))


@dataclass
class _SimEvent:
    """Minimal event-record representation for diagnostics."""

    timestamp: float
    severity: int
    message: str


class _SimulatedTSPTransport:
    """
    Tiny helper that mimics the `.device` handle present on the real driver.

    The simulator does **not** implement the full TSP parser; it only recognises
    the handful of `print(...)` commands that the existing driver issues when
    querying ID and diagnostic information.  All other commands are logged and
    ignored.
    """

    def __init__(self) -> None:
        self._pending_read: str = ""
        self._history: List[str] = []

    @property
    def history(self) -> Tuple[str, ...]:
        """Return immutable view of the command log."""
        return tuple(self._history)

    def write(self, command: str) -> None:
        """Store the command and pre-compute canned responses where required."""
        cmd = command.strip()
        self._history.append(cmd)

        if "localnode.model" in cmd:
            self._pending_read = "2450-SIM,000001,1.0.0"
        elif "errorqueue.next" in cmd:
            self._pending_read = '0,"No error"'
        elif "errorqueue.count" in cmd:
            self._pending_read = "0"
        elif "eventlog.count" in cmd:
            self._pending_read = "0"
        elif "eventlog.next" in cmd:
            self._pending_read = "NONE"
        else:
            # Unknown commands simply clear pending output.
            self._pending_read = ""

    def read(self) -> str:
        """Return the previously staged response (if any)."""
        response = self._pending_read
        self._pending_read = ""
        return response


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


class Keithley2450_TSP_Sim:
    """
    Drop-in simulation of the hardware-backed `Keithley2450_TSP`.

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
        address: str = "SIM::KEITHLEY2450",
        timeout: int = 10000,
        terminals: str = "front",
        *,
        params: Optional[MemristorParameters] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.address = address
        self.timeout = timeout
        self.terminals = terminals.lower()
        self.params = params or MemristorParameters()
        self.device = _SimulatedTSPTransport()

        if seed is not None:
            random.seed(seed)

        self._output_on: bool = False
        self._source_mode: str = "voltage"  # 'voltage' or 'current'
        self._source_level: float = 0.0
        self._current_limit: float = 0.1     # Amps
        self._voltage_limit: float = 40.0    # Volts for current-source mode
        self._last_update: float = time.time()

        self._state_w: float = 0.2           # Start slightly conductive
        self._event_log: List[_SimEvent] = []
        self._error_queue: List[str] = []

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

        if not self._output_on:
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

    def _log_event(self, severity: int, message: str) -> None:
        """Append an event to the circular log (limited to 50 entries)."""
        self._event_log.append(_SimEvent(time.time(), severity, message))
        self._event_log = self._event_log[-50:]

    def _ensure_terminal(self) -> None:
        if self.terminals not in ("front", "rear"):
            self._log_event(1, f"Invalid terminals '{self.terminals}', defaulting to front")
            self.terminals = "front"

    def _reset_errors(self) -> None:
        self._error_queue.clear()

    # ------------------------------------------------------------------ #
    # Public API mirroring the real driver
    # ------------------------------------------------------------------ #
    def get_idn(self) -> str:
        """Return a simulated identification string."""
        return "KEITHLEY INSTRUMENTS,MODEL 2450-SIM,000001,1.0.0"

    def set_voltage(self, voltage: float, Icc: float = 0.1) -> None:
        self._ensure_terminal()
        self._update_state()
        self._source_mode = "voltage"
        self._source_level = float(voltage)
        self._current_limit = float(abs(Icc))
        self._log_event(0, f"Set voltage to {voltage:.3f} V (Icc={Icc:.3f} A)")

    def set_current(self, current: float, Vcc: float = 10.0) -> None:
        self._ensure_terminal()
        self._update_state()
        self._source_mode = "current"
        self._source_level = float(current)
        self._voltage_limit = float(abs(Vcc))
        self._log_event(0, f"Set current to {current:.3e} A (Vcc={Vcc:.3f} V)")

    def measure_voltage(self) -> float:
        self._update_state()
        if self._source_mode == "voltage":
            voltage = self._source_level
        else:
            voltage = self._source_level * self._resistance()
            voltage += random.gauss(0.0, self.params.noise_voltage)
            voltage = _clamp(voltage, -self._voltage_limit, self._voltage_limit)
        return float(voltage)

    def measure_current(self) -> float:
        self._update_state()
        if self._source_mode == "current":
            current = self._source_level
        else:
            conductance = self._conductance()
            current = self._source_level * conductance

        # Compliance limiting
        if abs(current) > self._current_limit:
            current = math.copysign(self._current_limit, current)
            self._log_event(1, "Current limited by compliance")

        current += random.gauss(0.0, self.params.noise_current)
        return float(current)

    def measure_both(self) -> Tuple[float, float]:
        """Return (voltage, current) pair."""
        return self.measure_voltage(), self.measure_current()

    def enable_output(self, enable: bool = True) -> None:
        self._update_state()
        self._output_on = bool(enable)
        state = "ON" if enable else "OFF"
        self._log_event(0, f"Source output {state}")

    def shutdown(self) -> None:
        self.set_voltage(0.0, self._current_limit or 0.1)
        self.enable_output(False)
        self._log_event(0, "Shutdown invoked")

    def close(self) -> None:
        self.shutdown()

    def beep(self, frequency: float = 1000, duration: float = 0.2) -> None:
        self._log_event(0, f"Beep requested at {frequency} Hz for {duration}s")

    # Diagnostics ------------------------------------------------------- #
    def check_errors(self) -> str:
        if not self._error_queue:
            return "No errors"
        return self._error_queue[-1]

    def get_all_errors(self) -> List[str]:
        errors = list(self._error_queue)
        self._reset_errors()
        return errors

    def get_error_count(self) -> int:
        return len(self._error_queue)

    def get_event_log(self, max_events: int = 50) -> List[Dict[str, float]]:
        events = self._event_log[-max_events:]
        return [
            {
                "timestamp_sec": int(ev.timestamp),
                "timestamp_nano": int((ev.timestamp - int(ev.timestamp)) * 1e9),
                "severity": ev.severity,
                "message": ev.message,
            }
            for ev in events
        ]

    def get_event_log_count(self) -> int:
        return len(self._event_log)

    def clear_event_log(self) -> None:
        self._event_log.clear()

    def get_full_diagnostics(self) -> Dict[str, object]:
        return {
            "error_count": self.get_error_count(),
            "errors": list(self._error_queue),
            "event_count": self.get_event_log_count(),
            "events": self.get_event_log(),
            "instrument_status": {
                "output": "ON" if self._output_on else "OFF",
                "source_function": self._source_mode.upper(),
            },
        }

    def print_diagnostics(self, diagnostics: Optional[Dict[str, object]] = None) -> None:
        diag = diagnostics or self.get_full_diagnostics()
        print("=" * 60)
        print("KEITHLEY 2450 SIMULATED DIAGNOSTICS")
        print("=" * 60)
        print(f"Errors: {diag['error_count']}")
        for idx, err in enumerate(diag["errors"], 1):
            print(f"  {idx}. {err}")
        print(f"Events: {diag['event_count']}")
        for idx, event in enumerate(diag["events"], 1):
            print(f"  {idx}. [{event['severity']}] {event['message']}")
        status = diag["instrument_status"]
        print(f"Output: {status.get('output', 'UNKNOWN')}")
        print(f"Source Function: {status.get('source_function', 'UNKNOWN')}")
        print("=" * 60)

    # Script helpers ---------------------------------------------------- #
    def clear_all_scripts(self) -> None:
        """No-op for compatibility."""
        self._log_event(0, "Cleared simulated scripts")

    def prepare_for_pulses(
        self,
        *,
        Icc: float = 0.1,
        v_range: float = 20.0,
        ovp: float = 21.0,
        use_remote_sense: bool = False,
        autozero_off: bool = True,
    ) -> None:
        """Record pulse-preparation meta-data (used by measurement services)."""
        self._current_limit = float(abs(Icc))
        self._voltage_limit = float(abs(v_range))
        self._log_event(
            0,
            f"Prepare pulses (Icc={Icc:.3f}A, range={v_range:.1f}V, OVP={ovp:.1f}V, remote={use_remote_sense})",
        )

    def finish_pulses(self, *, Icc: float = 0.1, restore_autozero: bool = True) -> None:
        self._log_event(0, "Finish pulses")
        self.enable_output(False)
        self.set_voltage(0.0, Icc)

    # Pulse / sweep primitives ----------------------------------------- #
    def voltage_pulse(self, voltage: float, width: float, clim: float = 100e-3, fast: bool = True) -> None:
        self.enable_output(True)
        self.set_voltage(voltage, clim)
        self._simulate_pulse(width)
        self.set_voltage(0.0, clim)
        self.enable_output(False)

    def current_pulse(self, current: float, width: float, vlim: float = 40.0) -> None:
        self.enable_output(True)
        self.set_current(current, vlim)
        self._simulate_pulse(width)
        self.set_current(0.0, vlim)
        self.enable_output(False)

    def pulse_with_measurement(self, voltage: float, width: float, clim: float = 100e-3) -> Tuple[float, float]:
        self.enable_output(True)
        self.set_voltage(voltage, clim)
        self._simulate_pulse(width)
        current = self.measure_current()
        voltage_eff = self.measure_voltage()
        self.set_voltage(0.0, clim)
        self.enable_output(False)
        return voltage_eff, current

    def pulse_train(
        self,
        voltage: float,
        width: float,
        count: int,
        delay_between: float,
        clim: float = 100e-3,
    ) -> None:
        self.enable_output(True)
        for _ in range(max(0, int(count))):
            self.set_voltage(voltage, clim)
            self._simulate_pulse(width)
            self.set_voltage(0.0, clim)
            self._simulate_pulse(delay_between, bias=False)
        self.enable_output(False)

    def run_tsp_sweep(
        self,
        start_v: float = 0.0,
        stop_v: float = 2.5,
        step_v: float = 0.05,
        icc_start: float = 1e-4,
        icc_factor: float = 10.0,
        icc_max: Optional[float] = None,
        delay_s: float = 0.005,
        burn_abort_A: Optional[float] = None,
    ) -> Dict[str, object]:
        """
        Simulate the embedded TSP sweep interface used by the hardware driver.

        Returns a dict mirroring the real instrument response:
            {
                "status": "FORMED" | "NO_FORM" | "DAMAGE",
                "voltages": [...],
                "currents": [...],
                "message": Optional[str],
            }
        """

        voltages: List[float] = []
        currents: List[float] = []
        compliance = abs(icc_start) if icc_start else 1e-5
        max_compliance = icc_max if icc_max is not None else compliance * 1e3
        abort_threshold = (
            burn_abort_A if burn_abort_A is not None else max(compliance * 10.0, compliance + 1e-6)
        )
        status = "NO_FORM"
        message: Optional[str] = None

        self.enable_output(True)

        def sweep_condition(v: float, stop: float, step: float) -> bool:
            return v <= stop if step >= 0 else v >= stop

        v = start_v
        if step_v == 0:
            message = "Step size of zero is invalid; aborting sweep"
            self._log_event(2, message)
            self.enable_output(False)
            return {
                "status": "ERROR",
                "voltages": voltages,
                "currents": currents,
                "message": message,
            }
        while sweep_condition(v, stop_v, step_v):
            self.set_voltage(v, compliance)
            if delay_s > 0:
                self._simulate_pulse(delay_s)
            voltage_measured = self.measure_voltage()
            current_measured = self.measure_current()
            voltages.append(voltage_measured)
            currents.append(current_measured)

            if abs(current_measured) >= abort_threshold:
                status = "DAMAGE"
                message = "Current exceeded abort threshold"
                self._log_event(2, message)
                break

            if abs(current_measured) > 0.9 * compliance:
                new_limit = min(compliance * icc_factor, max_compliance)
                if new_limit > compliance:
                    compliance = new_limit
                    self._log_event(1, f"Compliance raised to {compliance:.3e} A")

            v += step_v

        if status != "DAMAGE" and currents:
            if max(abs(i) for i in currents) > 5e-4:
                status = "FORMED"
            else:
                status = "NO_FORM"

        self.set_voltage(0.0, compliance)
        self.enable_output(False)

        return {
            "status": status,
            "voltages": voltages,
            "currents": currents,
            "message": message,
        }

    # ------------------------------------------------------------------ #
    # Simulation primitives
    # ------------------------------------------------------------------ #
    def _simulate_pulse(self, duration: float, *, bias: bool = True) -> None:
        """Advance the simulation by `duration` seconds under current bias."""
        steps = max(1, int(math.ceil(duration / 0.001)))
        step_dt = duration / steps if steps else duration

        if not bias:
            original_level = self._source_level
            original_mode = self._source_mode
            original_output = self._output_on
            self._output_on = False
            for _ in range(steps):
                self._last_update -= step_dt
                self._update_state()
                time.sleep(0.0)
            self._output_on = original_output
            self._source_mode = original_mode
            self._source_level = original_level
            return

        for _ in range(steps):
            # Pretend that `step_dt` seconds elapsed between updates.
            self._last_update -= step_dt
            self._update_state()
            time.sleep(0.0)

    def advance_time(self, duration: float, *, with_bias: bool = True) -> None:
        """
        Public helper for scripts/tests to advance the simulation clock.

        Args:
            duration: Seconds of simulated time to elapse.
            with_bias: If False the state relaxes as-if the output were disabled.
        """
        if duration <= 0:
            return
        self._simulate_pulse(duration, bias=with_bias)


__all__ = [
    "Keithley2450_TSP_Sim",
    "MemristorParameters",
]

