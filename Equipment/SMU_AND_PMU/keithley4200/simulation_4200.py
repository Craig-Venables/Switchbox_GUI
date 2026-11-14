"""
Keithley 4200A Simulation
==========================

This module provides a pure-Python simulation of the Keithley 4200A-SCS
that mirrors the public API of `_Keithley4200A_KXCI_Wrapper`. It is intended
for GUI and measurement-pipeline testing when real hardware is unavailable.

The simulator focuses on:
    * API compatibility – the same methods as the hardware-backed driver are
      available, with similar signatures and return formats.
    * Memristor-style behaviour – internal state evolves with applied pulses,
      producing hysteresis-like current/voltage responses.
    * Simulated C module behavior – mimics EX command execution and GP data retrieval
      for ``smu_ivsweep`` (matching A_Iv_Sweep / run_smu_vi_sweep parameter order
      and GP slots 5=Imeas, 7=Vforce).
    * Opt-in fault injection – timeout/halt, pauses, truncated/dropped GP, EX
      error codes, and mid-sweep disconnect (off by default).
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp `value` inside the inclusive range [low, high]."""
    return max(low, min(high, value))


@dataclass
class MemristorParameters:
    """Group tunable parameters that shape the simulated device response."""

    ron: float = 150.0  # Low-resistance limit (Ohms)
    roff: float = 1.5e6  # High-resistance limit (Ohms)
    set_threshold: float = 0.9  # |V| above which SET dynamics start (Volts)
    reset_threshold: float = 0.9  # |V| above which RESET dynamics start (Volts)
    set_rate: float = 2.0  # State change per (Volt-second) in SET direction
    reset_rate: float = 2.5  # State change per (Volt-second) in RESET direction
    relax_rate: float = 0.02  # Slow relaxation towards mid state when unbiased
    noise_current: float = 2e-7  # White noise sigma (Amps)
    noise_voltage: float = 2e-4  # Voltage noise sigma (Volts) in current-source mode


@dataclass
class Simulation4200Faults:
    """Opt-in fault scenarios for IV / KXCI path testing. All defaults are off."""

    halt: bool = False
    """If True, EX never completes — raises TimeoutError (simulates GPIB timeout)."""

    pause_s: float = 0.0
    """Wall-clock delay injected before EX work (and optionally before GP)."""

    drop_gp: bool = False
    """If True, GP queries raise as if the parameter were inaccessible."""

    truncate_gp_points: Optional[int] = None
    """If set, GP returns at most this many points (truncated readback)."""

    ex_error_code: Optional[int] = None
    """If set, EX returns this code immediately without generating sweep data."""

    mid_sweep_disconnect: bool = False
    """If True, disconnect mid-sweep and fail EX with a connection error."""

    force_stale_sample: bool = False
    """If True, ``bias_timed_read`` copies the previous current after the first sample."""

    glitch_index: Optional[int] = None
    """If set, that ``bias_timed_read`` sample is forced to ``glitch_current_a``."""

    glitch_current_a: float = 0.0
    """Exact current used when ``glitch_index`` matches the sample index."""


# GP parameter positions for smu_ivsweep (1-based, matching C module signature order)
GP_IMEAS = 5
GP_VFORCE = 7


def build_iv_sweep_voltages(vhigh: float, vlow: float, num_steps: int) -> List[float]:
    """
    Build forced-voltage list matching ``smu_ivsweep.c``.

    Pattern per cycle: 0 → Vhigh → 0 → Vlow → 0 with NumSteps distributed across
    four segments. Point count is ``NumSteps + 1``.
    """
    steps_per_segment = num_steps // 4
    remainder = num_steps % 4
    voltages: List[float] = []

    # Segment 1: 0V → Vhigh (measure start at 0, then seg_steps increments)
    seg_steps = steps_per_segment + (1 if remainder > 0 else 0)
    if remainder > 0:
        remainder -= 1
    voltages.append(0.0)
    if seg_steps > 0:
        vstep = (vhigh - 0.0) / float(seg_steps)
        v = 0.0
        for _ in range(seg_steps):
            v = v + vstep
            if vhigh >= 0.0 and v > vhigh:
                v = vhigh
            voltages.append(v)
        voltages[-1] = vhigh

    # Segment 2: Vhigh → 0V
    seg_steps = steps_per_segment + (1 if remainder > 0 else 0)
    if remainder > 0:
        remainder -= 1
    if seg_steps > 0:
        vstep = (0.0 - vhigh) / float(seg_steps)
        v = vhigh
        for _ in range(seg_steps):
            v = v + vstep
            if v < 0.0:
                v = 0.0
            voltages.append(v)
        voltages[-1] = 0.0

    # Segment 3: 0V → Vlow (no duplicate 0V sample)
    seg_steps = steps_per_segment + (1 if remainder > 0 else 0)
    if remainder > 0:
        remainder -= 1
    if seg_steps > 0:
        vstep = (vlow - 0.0) / float(seg_steps)
        v = 0.0
        for _ in range(seg_steps):
            v = v + vstep
            if vlow <= 0.0 and v < vlow:
                v = vlow
            voltages.append(v)
        voltages[-1] = vlow

    # Segment 4: Vlow → 0V
    seg_steps = steps_per_segment + (1 if remainder > 0 else 0)
    if remainder > 0:
        remainder -= 1
    if seg_steps > 0:
        vstep = (0.0 - vlow) / float(seg_steps)
        v = vlow
        for _ in range(seg_steps):
            v = v + vstep
            if v > 0.0:
                v = 0.0
            voltages.append(v)
        voltages[-1] = 0.0

    return voltages


class Simulation4200:
    """
    Drop-in simulation of the hardware-backed `_Keithley4200A_KXCI_Wrapper`.

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
        gpib_address: str = "SIM::GPIB0::17::INSTR",
        timeout: float = 60.0,
        *,
        params: Optional[MemristorParameters] = None,
        seed: Optional[int] = None,
        faults: Optional[Simulation4200Faults] = None,
        debug: bool = False,
        live_hiccups: bool = False,
        wall_sleep: bool = False,
    ) -> None:
        self.gpib_address = gpib_address
        self.timeout = timeout
        self.params = params or MemristorParameters()
        self.faults = faults or Simulation4200Faults()
        self.debug = bool(debug)
        self.live_hiccups = bool(live_hiccups)
        self.wall_sleep = bool(wall_sleep)

        if seed is not None:
            random.seed(seed)
        # Separate generator so hiccups do not change the existing noise stream.
        self._hiccup_rng = random.Random(seed)

        self._output_enabled: bool = False
        self._source_mode: str = "voltage"  # 'voltage' or 'current'
        self._source_level: float = 0.0
        self._current_limit: float = 1e-3  # Amps
        self._voltage_limit: float = 10.0  # Volts for current-source mode
        self._last_update: float = time.time()
        self._ul_mode_active: bool = False
        self._connected: bool = False

        # Simulated data storage for GP commands
        self._gp_data: Dict[int, List[float]] = {}  # GP parameter -> data array

        self._state_w: float = 0.2  # Start slightly conductive

        # KXCI compatibility - simulate VISA resource
        # Must be set before wrapper accesses it
        self.inst = self  # Self-reference for compatibility checks
        self.rm = None  # Resource manager (not used in simulation)

        # Auto-connect simulation (always succeeds)
        self.connect()

    def _log(self, msg: str) -> None:
        if self.debug:
            print(f"[SIM 4200] {msg}")

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

    def _ensure_connected(self) -> None:
        if not self._connected or self.inst is None:
            raise RuntimeError("Not connected")

    # ------------------------------------------------------------------ #
    # KXCI Wrapper API (mirrors _Keithley4200A_KXCI_Wrapper)
    # ------------------------------------------------------------------ #
    def get_idn(self) -> str:
        """Return a simulated identification string."""
        return "KEITHLEY INSTRUMENTS INC.,MODEL 4200A-SIM,000001,1.0.0"

    def set_voltage(self, voltage: float, Icc: float = 1e-3) -> None:
        """Set source voltage."""
        self._update_state()
        self._source_mode = "voltage"
        self._source_level = float(voltage)
        self._current_limit = float(abs(Icc))
        if not self._output_enabled:
            self._output_enabled = True

    def set_current(self, current: float, Vcc: float = 10.0) -> None:
        """Set source current."""
        self._update_state()
        self._source_mode = "current"
        self._source_level = float(current)
        self._voltage_limit = float(abs(Vcc))
        if not self._output_enabled:
            self._output_enabled = True

    def set_current_measurement_range(self, current_range_a: float = 0.0) -> None:
        """Simulated API parity with real controllers; 0 means auto range."""
        try:
            self._measurement_current_range = float(current_range_a)
        except Exception:
            self._measurement_current_range = 0.0

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
            # Optical tests share a process-wide laser flag. Emission raises
            # photocurrent only while this SMU is forcing voltage.
            if self._output_enabled:
                from Equipment.Laser_Controller.sim_link import get_laser_link

                emitting, power_mw = get_laser_link().snapshot()
                if emitting and power_mw > 0.0:
                    current *= 1.0 + 0.25 * min(float(power_mw), 5.0)

        # Compliance limiting
        if abs(current) > self._current_limit:
            current = math.copysign(self._current_limit, current)

        current += random.gauss(0.0, self.params.noise_current)
        return float(current)

    def _maybe_hiccup(self) -> None:
        """Occasional short stall so a live GUI run does not look perfectly smooth."""
        if not self.live_hiccups:
            return
        if self._hiccup_rng.random() < 0.08:
            time.sleep(self._hiccup_rng.uniform(0.05, 0.30))

    @staticmethod
    def _ohms_from_vi(voltage: float, current: float) -> float:
        """Positive finite resistance. Tiny current (or zero force) → 1e12 ohm."""
        if abs(current) < 1e-15 or abs(voltage) < 1e-18:
            return 1e12
        resistance = abs(float(voltage) / float(current))
        if not math.isfinite(resistance) or resistance <= 0.0:
            return 1e12
        return float(resistance)

    def enable_output(self, enable: bool = True) -> None:
        """Enable/disable output."""
        self._output_enabled = bool(enable)
        if not enable:
            self._source_level = 0.0

    def prepare_for_pulses(
        self,
        Icc: float = 1e-3,
        v_range: float = 20.0,
        ovp: float = 21.0,
        use_remote_sense: bool = False,
        autozero_off: bool = True,
    ) -> None:
        """Prepare for pulse measurements."""
        self._current_limit = float(abs(Icc))
        self.set_voltage(0.0, Icc)
        self._output_enabled = True

    def finish_pulses(self, Icc: float = 1e-3, restore_autozero: bool = True) -> None:
        """Finish pulse session."""
        self.set_voltage(0.0, Icc)
        self._output_enabled = False

    def shutdown(self) -> None:
        """Shutdown and cleanup."""
        self.set_voltage(0.0, self._current_limit or 1e-3)
        self._output_enabled = False

    def close(self) -> None:
        """Close connection."""
        self.shutdown()

    # ------------------------------------------------------------------ #
    # KXCI API (for C module execution simulation)
    # ------------------------------------------------------------------ #
    def _enter_ul_mode(self) -> bool:
        """Enter user library (UL) mode."""
        self._ul_mode_active = True
        return True

    def _exit_ul_mode(self) -> None:
        """Exit user library (UL) mode."""
        self._ul_mode_active = False

    def _parse_smu_ivsweep_params(self, command: str) -> Tuple[float, float, int, int, int, int, float, float, float, float, int]:
        """
        Parse EX smu_ivsweep(...) parameters.

        Signature (13 args), matching run_smu_vi_sweep.build_ex_command:
          Vhigh, Vlow, NumSteps, NumCycles, Imeas(""), NumIPoints,
          Vforce(""), NumVPoints, StepDelay, Ilimit, IRange, IntegrationTime, ClariusDebug
        """
        cmd_start = command.find("(")
        cmd_end = command.rfind(")")
        if cmd_start < 0 or cmd_end <= cmd_start:
            raise ValueError("Invalid command format")

        params_str = command[cmd_start + 1 : cmd_end]
        parts = [p.strip() for p in params_str.split(",")]

        def _is_empty(s: str) -> bool:
            return s in ("", '""', "''")

        # Empty array placeholders may collapse consecutive commas; tolerate 11–13 parts
        if len(parts) < 11:
            raise ValueError(f"Not enough parameters ({len(parts)})")

        vhigh = float(parts[0])
        vlow = float(parts[1]) if not _is_empty(parts[1]) else 0.0
        num_steps = int(float(parts[2]))
        num_cycles = int(float(parts[3]))

        # parts[4] is Imeas placeholder (empty)
        idx = 4
        if idx < len(parts) and _is_empty(parts[idx]):
            idx += 1
        num_i_points = int(float(parts[idx]))
        idx += 1

        if idx < len(parts) and _is_empty(parts[idx]):
            idx += 1
        num_v_points = int(float(parts[idx]))
        idx += 1

        step_delay = float(parts[idx]) if idx < len(parts) else 0.001
        idx += 1
        ilimit = float(parts[idx]) if idx < len(parts) else 0.1
        idx += 1
        irange = float(parts[idx]) if idx < len(parts) else 0.0
        idx += 1
        integration_time = float(parts[idx]) if idx < len(parts) else 0.01
        idx += 1
        clarius_debug = int(float(parts[idx])) if idx < len(parts) else 0

        return (
            vhigh,
            vlow,
            num_steps,
            num_cycles,
            num_i_points,
            num_v_points,
            step_delay,
            ilimit,
            irange,
            integration_time,
            clarius_debug,
        )

    def _validate_smu_ivsweep(
        self,
        vhigh: float,
        vlow: float,
        num_steps: int,
        num_cycles: int,
        num_i_points: int,
        num_v_points: int,
    ) -> Optional[int]:
        """Return C-module style error code, or None if valid."""
        if vhigh < 0.0:
            return -1
        if vlow > 0.0:
            return -1
        if num_steps < 4 or num_steps > 10000:
            return -5
        if num_cycles < 1 or num_cycles > 1000:
            return -5
        if num_i_points != num_v_points:
            return -2
        expected = (num_steps + 1) * num_cycles
        if num_i_points != expected or num_v_points != expected:
            return -3
        points_per_cycle = num_steps + 1
        if num_i_points < points_per_cycle or num_v_points < points_per_cycle:
            return -4
        return None

    def _measure_at_voltage(self, voltage: float, step_delay: float, ilimit: float) -> float:
        """Apply voltage, advance memristor state, return compliance-clipped current."""
        self._output_enabled = True
        self._source_mode = "voltage"
        self._source_level = float(voltage)
        self._current_limit = abs(ilimit)

        # Advance state using step delay as simulated dwell (no wall sleep)
        dwell = max(step_delay, 1e-4)
        self._simulate_time(dwell)

        resistance = self._resistance()
        if abs(resistance) > 1e-12:
            current = voltage / resistance
        else:
            current = 0.0

        if self.params.noise_current > 0.0:
            current += random.gauss(0.0, self.params.noise_current)

        if abs(current) > self._current_limit:
            current = math.copysign(self._current_limit, current)

        return float(current)

    def _run_smu_ivsweep(
        self,
        vhigh: float,
        vlow: float,
        num_steps: int,
        num_cycles: int,
        step_delay: float,
        ilimit: float,
    ) -> Tuple[List[float], List[float]]:
        """Execute full (0→Vhigh→0→Vlow→0)×NumCycles sweep; return Vforce, Imeas."""
        if step_delay < 0.001:
            step_delay = 0.001
        if ilimit < 1e-9:
            ilimit = 1e-9

        self._current_limit = abs(ilimit)
        voltages: List[float] = []
        currents: List[float] = []

        cycle_voltages = build_iv_sweep_voltages(vhigh, vlow, num_steps)
        total_points = len(cycle_voltages) * num_cycles
        disconnect_at = total_points // 2 if self.faults.mid_sweep_disconnect else None

        for _cycle in range(num_cycles):
            for v in cycle_voltages:
                if disconnect_at is not None and len(voltages) >= disconnect_at:
                    self.disconnect()
                    raise RuntimeError("Simulated mid-sweep disconnect")

                current = self._measure_at_voltage(v, step_delay, ilimit)
                voltages.append(v)
                currents.append(current)

        self._source_level = 0.0
        return voltages, currents

    def _store_iv_gp(self, voltages: List[float], currents: List[float]) -> None:
        """Store IV arrays in GP slots matching smu_ivsweep (5=Imeas, 7=Vforce)."""
        self._gp_data[GP_IMEAS] = list(currents)
        self._gp_data[GP_VFORCE] = list(voltages)
        # Legacy aliases used by older single-point wrapper path (GP 4 / GP 6)
        self._gp_data[4] = list(currents)
        self._gp_data[6] = list(voltages)

    def _execute_ex_command(self, command: str, wait_seconds: float = 1.0) -> Tuple[Optional[int], Optional[str]]:
        """
        Simulate EX command execution.

        For smu_ivsweep: Executes (0 → Vhigh → 0 → Vlow → 0) × NumCycles with
        NumSteps distributed across segments, stores data in GP 5/7.

        Returns (return_value, error_message) tuple.
        """
        try:
            self._ensure_connected()
        except RuntimeError as e:
            return (None, f"EX command failed: {e}")

        if self.faults.pause_s > 0.0:
            time.sleep(self.faults.pause_s)

        if self.faults.halt:
            raise TimeoutError("Simulated EX halt/timeout: smu_ivsweep did not return")

        if "smu_ivsweep" in command:
            self._log(f"Received smu_ivsweep EX command: {command}")

            if self.faults.ex_error_code is not None:
                code = int(self.faults.ex_error_code)
                self._log(f"Injected EX error code {code}")
                return (code, None)

            try:
                (
                    vhigh,
                    vlow,
                    num_steps,
                    num_cycles,
                    num_i_points,
                    num_v_points,
                    step_delay,
                    ilimit,
                    _irange,
                    _integration_time,
                    _clarius_debug,
                ) = self._parse_smu_ivsweep_params(command)

                self._log(
                    f"Parsed Vhigh={vhigh}, Vlow={vlow}, NumSteps={num_steps}, "
                    f"NumCycles={num_cycles}, points={num_i_points}, ilimit={ilimit}"
                )

                err = self._validate_smu_ivsweep(
                    vhigh, vlow, num_steps, num_cycles, num_i_points, num_v_points
                )
                if err is not None:
                    return (err, None)

                voltages, currents = self._run_smu_ivsweep(
                    vhigh=vhigh,
                    vlow=vlow,
                    num_steps=num_steps,
                    num_cycles=num_cycles,
                    step_delay=step_delay,
                    ilimit=ilimit,
                )
                self._store_iv_gp(voltages, currents)
                self._log(f"Sweep complete: {len(voltages)} points stored in GP {GP_VFORCE}/{GP_IMEAS}")
                return (0, None)
            except RuntimeError as e:
                if "disconnect" in str(e).lower():
                    return (None, f"EX command failed: {e}")
                return (-1, f"Failed to execute sweep: {e}")
            except ValueError as e:
                return (-1, f"Invalid parameter value: {e}")
            except Exception as e:
                return (-1, f"Failed to execute sweep: {e}")

        elif "SMU_pulse_measure" in command or "SMU_pulse_only" in command:
            return self._execute_pulse_ex(command)

        # Unknown command - return success but no data
        _ = wait_seconds  # real hardware waits; sim skips wall sleep for speed
        return (0, None)

    def _parse_smu_pulse_params(self, command: str) -> Tuple[float, float, float]:
        """Parse SMU_pulse_measure / SMU_pulse_only: (width_s, amplitude_v, icomp_a)."""
        cmd_start = command.find("(")
        cmd_end = command.rfind(")")
        if cmd_start < 0 or cmd_end <= cmd_start:
            raise ValueError("Invalid pulse command format")
        parts = [p.strip() for p in command[cmd_start + 1 : cmd_end].split(",")]
        if len(parts) < 4:
            raise ValueError(f"Not enough pulse parameters ({len(parts)})")
        width = float(parts[2]) if parts[2] else 0.0
        amplitude = float(parts[3]) if parts[3] else 0.0
        icomp = float(parts[5]) if len(parts) > 5 and parts[5] else 0.0
        return width, amplitude, icomp

    def _apply_voltage_pulse(self, amplitude: float, width_s: float, icomp: float) -> float:
        """Force ``amplitude`` for ``width_s`` and return the compliance-limited current."""
        self._source_mode = "voltage"
        self._source_level = float(amplitude)
        self._output_enabled = True
        if abs(float(icomp)) > 0.0:
            self._current_limit = abs(float(icomp))
        width = max(0.0, float(width_s))
        # Drop any time spent in a hiccup so only the pulse width moves the state.
        self._last_update = time.time()
        if width > 0.0 and self.wall_sleep:
            time.sleep(width)
            self._update_state()
        elif width > 0.0:
            self._simulate_time(width)
        else:
            self._update_state()
        return self.measure_current()

    def _execute_pulse_ex(self, command: str) -> Tuple[Optional[float], Optional[str]]:
        """Run SMU_pulse_measure (return ohms) or SMU_pulse_only (return 0)."""
        self._maybe_hiccup()

        if self.faults.ex_error_code is not None:
            return (int(self.faults.ex_error_code), None)

        if self.faults.mid_sweep_disconnect:
            self.disconnect()
            return (None, "EX command failed: Simulated connection error (mid-sweep disconnect)")

        measure = "SMU_pulse_measure" in command
        try:
            width, amplitude, icomp = self._parse_smu_pulse_params(command)
            current = self._apply_voltage_pulse(amplitude, width, icomp)
            if not measure:
                return (0, None)
            resistance = self._ohms_from_vi(amplitude, current)
            self._gp_data[4] = [current]
            self._gp_data[6] = [amplitude]
            self._gp_data[GP_IMEAS] = [current]
            self._gp_data[GP_VFORCE] = [amplitude]
            return (resistance, None)
        except RuntimeError as e:
            if "disconnect" in str(e).lower() or "connection" in str(e).lower():
                return (None, f"EX command failed: {e}")
            return (-1, f"Failed to execute pulse: {e}")
        except Exception as e:
            return (-1, f"Failed to parse pulse command: {e}")

    def bias_timed_read(
        self,
        vforce: float,
        duration_s: float,
        sample_interval_s: float,
        ilimit: float,
        num_points: Optional[int] = None,
        current_range_a: float = 0.0,
    ) -> Dict[str, List[float]]:
        """Hold ``vforce`` and sample current. Timestamps start at 0.

        Point count is ``num_points`` when given, otherwise ``duration_s / sample_interval_s``.
        """
        if num_points is None:
            if sample_interval_s <= 0.0:
                n = 1
            else:
                n = max(1, int(float(duration_s) / float(sample_interval_s)))
        else:
            n = max(0, int(num_points))

        self.set_current_measurement_range(current_range_a)
        if abs(float(ilimit)) > 0.0:
            self._current_limit = abs(float(ilimit))
        self.set_voltage(float(vforce), Icc=self._current_limit)
        self.enable_output(True)
        self._last_update = time.time()

        timestamps: List[float] = []
        voltages: List[float] = []
        currents: List[float] = []
        resistances: List[float] = []
        prev_current: Optional[float] = None
        interval = float(sample_interval_s)

        for i in range(n):
            if i > 0:
                if self.wall_sleep:
                    time.sleep(max(0.0, interval))
                else:
                    self._simulate_time(max(0.0, interval))
            self._maybe_hiccup()
            current = self.measure_current()
            # Forced stale is exact. The 3% live hiccup stays a separate dice roll.
            if self.faults.force_stale_sample and prev_current is not None:
                current = prev_current
            elif (
                self.live_hiccups
                and prev_current is not None
                and self._hiccup_rng.random() < 0.03
            ):
                current = prev_current
            if self.faults.glitch_index is not None and i == int(self.faults.glitch_index):
                current = float(self.faults.glitch_current_a)
            prev_current = current
            timestamps.append(i * interval)
            voltages.append(float(vforce))
            currents.append(float(current))
            resistances.append(self._ohms_from_vi(float(vforce), float(current)))

        return {
            "timestamps": timestamps,
            "voltages": voltages,
            "currents": currents,
            "resistances": resistances,
        }

    def _simulate_time(self, duration: float) -> None:
        """
        Simulate time passage for settle times, pulse widths, etc. without wall sleep.

        Args:
            duration: Time in seconds to simulate
        """
        steps = max(1, int(math.ceil(duration / 0.001)))  # 1ms steps
        step_dt = duration / steps if steps > 0 else duration

        for _ in range(steps):
            self._last_update -= step_dt  # Simulate time passing
            self._update_state()

    def _query_gp(self, param: int, num_points: int) -> List[float]:
        """
        Simulate GP (Get Parameter) command.

        Returns data array for the specified parameter (list of floats), matching
        what ``Keithley4200A_KXCI._parse_gp_response`` would produce from a
        semicolon-separated instrument reply.
        """
        if self.faults.pause_s > 0.0:
            time.sleep(min(self.faults.pause_s, 0.05))

        try:
            self._ensure_connected()
        except RuntimeError:
            self._log(f"GP {param} failed: not connected")
            return []

        if self.faults.drop_gp:
            raise RuntimeError(
                "GP command returned error -980: Parameter not accessible or invalid parameter number"
            )

        self._log(f"GP Query: param={param}, requesting {num_points} points")

        if param in self._gp_data:
            data = list(self._gp_data[param])
            if self.faults.truncate_gp_points is not None:
                # Return short array as-is so callers see truncated hardware readback
                return data[: max(0, int(self.faults.truncate_gp_points))]

            if len(data) >= num_points:
                return data[:num_points]
            if not data:
                return [0.0] * num_points
            # Benign path: pad with last value when instrument has fewer points than requested
            return data + [data[-1]] * (num_points - len(data))

        self._log(f"GP {param} not found, returning {num_points} zeros")
        return [0.0] * num_points

    def connect(self) -> bool:
        """Connect to simulated instrument."""
        self._connected = True
        if not self.inst:
            self.inst = self
        return True

    def disconnect(self) -> None:
        """Disconnect from simulated instrument."""
        self._output_enabled = False
        self._ul_mode_active = False
        self._connected = False
        self.inst = None

    def set_debug(self, enabled: bool) -> None:
        """Enable or disable debug logging."""
        self.debug = bool(enabled)

    def query(self, command: str) -> str:
        """
        Simulate SCPI query command.

        Args:
            command: SCPI command string

        Returns:
            Simulated response string
        """
        cmd = command.strip().upper()

        if cmd == "*IDN?":
            return self.get_idn()
        elif cmd.startswith("SYST:ERR"):
            return '0,"No error"'
        else:
            return "0"


__all__ = [
    "Simulation4200",
    "MemristorParameters",
    "Simulation4200Faults",
    "build_iv_sweep_voltages",
    "GP_IMEAS",
    "GP_VFORCE",
]
