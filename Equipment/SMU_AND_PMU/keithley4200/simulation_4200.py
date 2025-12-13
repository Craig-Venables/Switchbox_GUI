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
* Simulated C module behavior – mimics EX command execution and GP data retrieval.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any


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
    ) -> None:
        self.gpib_address = gpib_address
        self.timeout = timeout
        self.params = params or MemristorParameters()
        
        if seed is not None:
            random.seed(seed)

        self._output_enabled: bool = False
        self._source_mode: str = "voltage"  # 'voltage' or 'current'
        self._source_level: float = 0.0
        self._current_limit: float = 1e-3     # Amps
        self._voltage_limit: float = 10.0     # Volts for current-source mode
        self._last_update: float = time.time()
        self._ul_mode_active: bool = False
        
        # Simulated data storage for GP commands
        self._gp_data: Dict[int, List[float]] = {}  # GP parameter -> data array

        self._state_w: float = 0.2           # Start slightly conductive
        
        # KXCI compatibility - simulate VISA resource
        # Must be set before wrapper accesses it
        self.inst = self  # Self-reference for compatibility checks
        self.rm = None  # Resource manager (not used in simulation)
        
        # Auto-connect simulation (always succeeds)
        self.connect()

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

    def _execute_ex_command(self, command: str, wait_seconds: float = 1.0) -> Tuple[Optional[int], Optional[str]]:
        """
        Simulate EX command execution.
        
        For smu_ivsweep: Executes full sweep pattern (0 → +Vpos → Vneg → 0) × NumCycles
        and stores ALL data in GP parameters, matching real 4200A behavior.
        
        Returns (return_value, error_message) tuple.
        """
        # Simulate processing delay (longer for sweeps)
        time.sleep(min(wait_seconds, 0.1))
        
        # Parse command to extract parameters
        if "smu_ivsweep" in command:
            print(f"[SIM 4200] Received smu_ivsweep EX command")
            print(f"[SIM 4200] Command: {command}")
            
            # Parse EX command: EX A_Iv_Sweep smu_ivsweep(vpos,vneg,num_cycles,"",num_points,"",num_points,settle,ilimit,integ,debug)
            try:
                # Extract parameters from command string
                cmd_start = command.find('(')
                cmd_end = command.rfind(')')
                if cmd_start < 0 or cmd_end <= cmd_start:
                    return (-1, "Invalid command format")
                
                params_str = command[cmd_start+1:cmd_end]
                parts = [p.strip() for p in params_str.split(',')]
                
                if len(parts) < 11:
                    return (-1, "Not enough parameters")
                
                # Parse parameters according to function signature:
                # 1. Vpos (double)
                # 2. Vneg (double)
                # 3. NumCycles (int)
                # 4. Imeas (empty string "")
                # 5. NumIPoints (int)
                # 6. Vforce (empty string "")
                # 7. NumVPoints (int)
                # 8. SettleTime (double)
                # 9. Ilimit (double)
                # 10. IntegrationTime (double)
                # 11. ClariusDebug (int)
                
                vpos = float(parts[0])
                # Handle vneg - could be 0.0, negative value, or empty string
                vneg_str = parts[1].strip() if len(parts) > 1 else "0.0"
                if vneg_str in ('""', "''", '', '0', '0.0'):
                    vneg_val = 0.0
                else:
                    vneg_val = float(vneg_str)
                
                num_cycles = int(float(parts[2])) if len(parts) > 2 else 1
                # parts[3] is empty string for Imeas array
                num_points = int(float(parts[4])) if len(parts) > 4 else 4
                # parts[5] is empty string for Vforce array
                # parts[6] is NumVPoints (should match NumIPoints)
                settle_time = float(parts[7]) if len(parts) > 7 else 0.001
                ilimit = float(parts[8]) if len(parts) > 8 else 0.1
                integration_time = float(parts[9]) if len(parts) > 9 else 0.01
                clarius_debug = int(float(parts[10])) if len(parts) > 10 else 0
                
                print(f"[SIM 4200] Parsed parameters:")
                print(f"  - vpos: {vpos}V")
                print(f"  - vneg_val: {vneg_val}V")
                print(f"  - num_cycles: {num_cycles}")
                print(f"  - num_points: {num_points}")
                print(f"  - settle_time: {settle_time}s")
                print(f"  - ilimit: {ilimit}A")
                
                # Validate parameters
                if vpos < 0 or vpos > 200:
                    return (-1, "Invalid Vpos (must be >= 0 and <= 200)")
                if vneg_val > 0:
                    return (-1, "Invalid Vneg (must be <= 0)")
                if num_cycles < 1 or num_cycles > 1000:
                    return (-5, "Invalid NumCycles (must be 1-1000)")
                if num_points != 4 * num_cycles:
                    return (-3, "NumIPoints must equal 4 × NumCycles")
                if num_points < 4:
                    return (-4, "Invalid array sizes (must be >= 4)")
                
                # Determine actual negative voltage
                if vneg_val == 0.0:
                    vneg = -vpos  # Auto-symmetric
                else:
                    vneg = vneg_val
                
                # Update current limit from command
                self._current_limit = abs(ilimit)
                
                # Execute full sweep pattern: (0 → +vpos → vneg → 0) × num_cycles
                # This simulates the C module executing the entire sweep at once
                print(f"[SIM 4200] Executing full sweep: {num_cycles} cycles, {num_points} total points")
                voltages = []
                currents = []
                
                for cycle in range(num_cycles):
                    if cycle == 0 or (cycle + 1) % 10 == 0:
                        print(f"[SIM 4200] Processing cycle {cycle + 1}/{num_cycles}...")
                    # Pattern per cycle: 0 → +vpos → vneg → 0
                    cycle_voltages = [0.0, vpos, vneg, 0.0]
                    
                    for v in cycle_voltages:
                        # Simulate applying voltage and measuring
                        old_level = self._source_level
                        self._source_level = v
                        
                        # Simulate settle time
                        if settle_time > 0:
                            self._simulate_time(settle_time)
                        
                        # Update memristor state based on voltage
                        self._update_state()
                        
                        # Measure current based on resistance
                        resistance = self._resistance()
                        if abs(resistance) > 1e-6:
                            current = v / resistance
                        else:
                            current = 0.0
                        
                        # Add noise
                        current += random.gauss(0.0, self.params.noise_current)
                        
                        # Compliance limiting
                        if abs(current) > self._current_limit:
                            current = math.copysign(self._current_limit, current)
                        
                        voltages.append(v)
                        currents.append(current)
                        
                        self._source_level = old_level
                
                # Store ALL data in GP parameters (matching real 4200A behavior)
                # Data is available all at once after EX command completes
                self._gp_data[6] = voltages  # GP 6 = Vforce
                self._gp_data[4] = currents  # GP 4 = Imeas
                
                print(f"[SIM 4200] ✓ Sweep complete!")
                print(f"[SIM 4200] Stored {len(voltages)} voltage points in GP 6")
                print(f"[SIM 4200] Stored {len(currents)} current points in GP 4")
                print(f"[SIM 4200] First 3 points: V=[{voltages[0]:.3f}, {voltages[1]:.3f}, {voltages[2]:.3f}], I=[{currents[0]:.6e}, {currents[1]:.6e}, {currents[2]:.6e}]")
                
                return (0, None)  # Success (0 = success for smu_ivsweep)
            except ValueError as e:
                return (-1, f"Invalid parameter value: {e}")
            except Exception as e:
                return (-1, f"Failed to execute sweep: {e}")
        
        elif "SMU_pulse_measure" in command:
            # Simulate pulse measurement
            # Parse: SMU_pulse_measure(initialize, logMessages, widthTime, Amplitude, Irange, Icomp, measResistance)
            try:
                cmd_start = command.find('(')
                cmd_end = command.rfind(')')
                if cmd_start >= 0 and cmd_end > cmd_start:
                    params_str = command[cmd_start+1:cmd_end]
                    parts = [p.strip() for p in params_str.split(',')]
                    
                    if len(parts) >= 4:
                        initialize = int(float(parts[0])) if parts[0] else 0
                        width_time = float(parts[2]) if len(parts) > 2 and parts[2] else 0.001
                        amplitude = float(parts[3]) if len(parts) > 3 and parts[3] else 0.0
                        
                        # Update source level
                        self._source_level = amplitude
                        self._output_enabled = True
                        
                        # Simulate pulse duration
                        if width_time > 0:
                            self._simulate_time(width_time)
                        
                        # Measure after pulse
                        self._update_state()
                        current = self.measure_current()
                        
                        # Store as single point
                        self._gp_data[4] = [current]  # GP 4 = Imeas
                        self._gp_data[6] = [amplitude]  # GP 6 = Vforce
                        
                        return (0, None)  # Success
            except Exception as e:
                return (-1, f"Failed to parse pulse command: {e}")
        
        # Unknown command - return success but no data
        return (0, None)
    
    def _simulate_time(self, duration: float) -> None:
        """
        Simulate time passage for settle times, pulse widths, etc.
        
        Args:
            duration: Time in seconds to simulate
        """
        # Advance the simulation state by the duration
        steps = max(1, int(math.ceil(duration / 0.001)))  # 1ms steps
        step_dt = duration / steps if steps > 0 else duration
        
        for _ in range(steps):
            self._last_update -= step_dt  # Simulate time passing
            self._update_state()
            time.sleep(0.0)  # Yield to other threads

    def _query_gp(self, param: int, num_points: int) -> List[float]:
        """
        Simulate GP (Get Parameter) command.
        
        Returns data array for the specified parameter.
        """
        print(f"[SIM 4200] GP Query: param={param}, requesting {num_points} points")
        
        if param in self._gp_data:
            data = self._gp_data[param]
            print(f"[SIM 4200] GP {param} has {len(data)} stored points")
            
            # Return requested number of points (truncate or pad)
            if len(data) >= num_points:
                result = data[:num_points]
                print(f"[SIM 4200] Returning {len(result)} points (truncated from {len(data)})")
                return result
            else:
                # Pad with last value
                result = data + [data[-1] if data else 0.0] * (num_points - len(data))
                print(f"[SIM 4200] Returning {len(result)} points (padded from {len(data)})")
                return result
        
        # Return zeros if parameter not found
        print(f"[SIM 4200] ⚠️ GP {param} not found, returning {num_points} zeros")
        return [0.0] * num_points

    def connect(self) -> bool:
        """Connect to simulated instrument."""
        # Simulate connection - always succeeds
        if not self.inst:
            self.inst = self
        return True

    def disconnect(self) -> None:
        """Disconnect from simulated instrument."""
        self._output_enabled = False
        self._ul_mode_active = False
        # Keep self.inst = self for compatibility
    
    def set_debug(self, enabled: bool) -> None:
        """Enable or disable debug logging (no-op for simulation)."""
        pass
    
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
            # Unknown command - return empty or default response
            return "0"


__all__ = [
    "Simulation4200",
    "MemristorParameters",
]

