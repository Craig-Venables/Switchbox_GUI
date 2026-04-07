"""SMU Voltage-Current Sweep runner (KXCI compatible).

This script wraps the `EX A_Iv_Sweep smu_ivsweep(...)` command,
executes it on a Keithley 4200A-SCS SMU via KXCI, and retrieves the voltage
and current data from the step-based IV sweep.

Purpose:
--------
This script performs a step-based voltage-current (IV) sweep using the SMU (Source
Measurement Unit) of the Keithley 4200A-SCS. It:
1. Sweeps in pattern: 0V → Vhigh → 0V → Vlow → 0V
2. Distributes NumSteps evenly across the full sweep path
3. Repeats this pattern NumCycles times
4. At each step, waits for step delay
5. Measures current
6. Returns voltage and current arrays for plotting IV curves

Pattern: (0V → Vhigh → 0V → Vlow → 0V) × NumCycles
Total points = (NumSteps + 1) × NumCycles

Key Features:
-------------
- Step-based pattern: 0V → Vhigh → 0V → Vlow → 0V, repeated n times
- Configurable number of steps distributed across 4 segments
- Step delay at each voltage point (allows device to stabilize before measurement)
- Current compliance limit protection
- Error handling for invalid parameters
- Returns both forced voltage and measured current arrays

Parameters:
-----------
- Vhigh: Positive voltage limit (V), range: 0 to 200 V (default: 5.0)
- Vlow: Negative voltage limit (V), range: -200 to 0 V (default: -5.0)
- NumSteps: Total steps across full sweep path (default: 20, range: 4-10000)
            Steps are distributed evenly across 4 segments
- NumCycles: Number of cycles to repeat (default: 1, range: 1-1000)
             Total points = (NumSteps + 1) × NumCycles
- StepDelay: Delay at each step before measurement (seconds, default: 0.001 s = 1 ms)
- Ilimit: Current compliance limit (A, default: 0.1 A)

Usage examples:

    # Basic sweep: 0V → 5V → 0V → -5V → 0V (20 steps = 21 points)
    python run_smu_vi_sweep.py --vhigh 5 --vlow -5 --num-steps 20

    # High-resolution sweep: 0V → 3V → 0V → -2V → 0V (100 steps = 101 points)
    python run_smu_vi_sweep.py --vhigh 3 --vlow -2 --num-steps 100

    # Multiple cycles: (0V → 5V → 0V → -5V → 0V) × 3 (63 points total)
    python run_smu_vi_sweep.py --vhigh 5 --vlow -5 --num-steps 20 --num-cycles 3

    # Fast sweep with minimal step delay
    python run_smu_vi_sweep.py --vhigh 3 --vlow -3 --num-steps 20 --step-delay 0.0001

    # Custom current limit for high-resistance devices
    python run_smu_vi_sweep.py --vhigh 5 --vlow -5 --num-steps 20 --ilimit 1e-6

Pass `--dry-run` to print the generated EX command without contacting the instrument.
"""

from __future__ import annotations

import argparse
import re
import time
from typing import List, Optional


class KXCIClient:
    """Minimal KXCI helper for sending EX/GP commands."""

    def __init__(self, gpib_address: str, timeout: float) -> None:
        self.gpib_address = gpib_address
        self.timeout_ms = int(timeout * 1000)
        self.rm = None
        self.inst = None
        self._ul_mode_active = False

    def connect(self) -> bool:
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError("pyvisa is required to communicate with the instrument") from exc

        try:
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(self.gpib_address)
            self.inst.timeout = self.timeout_ms
            self.inst.write_termination = "\n"
            self.inst.read_termination = "\n"
            idn = self.inst.query("*IDN?").strip()
            print(f"[OK] Connected to: {idn}")
            return True
        except Exception as exc:
            print(f"[ERR] Connection failed: {exc}")
            return False

    def disconnect(self) -> None:
        try:
            if self._ul_mode_active:
                self._exit_ul_mode()
            if self.inst is not None:
                self.inst.close()
            if self.rm is not None:
                self.rm.close()
        finally:
            self.inst = None
            self.rm = None
            self._ul_mode_active = False

    def _enter_ul_mode(self) -> bool:
        if self.inst is None:
            return False
        self.inst.write("UL")
        time.sleep(0.03)
        self._ul_mode_active = True
        return True

    def _exit_ul_mode(self) -> bool:
        if self.inst is None or not self._ul_mode_active:
            self._ul_mode_active = False
            return True
        self.inst.write("DE")
        time.sleep(0.03)
        self._ul_mode_active = False
        return True

    def _execute_ex_command(self, command: str, wait_seconds: float = 1.0) -> tuple[Optional[int], Optional[str]]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")

        try:
            self.inst.write(command)
            time.sleep(0.03)
            # Wait for measurement to complete (configurable wait time)
            # For IV sweeps, this should be calculated based on:
            # ((num_steps + 1) × num_cycles) × (step_delay + integration_time × 0.01) × safety_factor
            wait_seconds = max(0.5, wait_seconds)  # Minimum 0.5s
            time.sleep(wait_seconds)
            response = self._safe_read()
            return self._parse_return_value(response), None
        except Exception as exc:
            return None, str(exc)

    def _safe_read(self) -> str:
        if self.inst is None:
            return ""
        try:
            return self.inst.read()
        except Exception:
            return ""

    @staticmethod
    def _parse_return_value(response: str) -> Optional[int]:
        if not response:
            return None
        match = re.search(r"RETURN VALUE\s*=\s*(-?\d+)", response, re.IGNORECASE)
        if match:
            return int(match.group(1))
        try:
            return int(response.strip())
        except ValueError:
            return None

    def _query_gp(self, param_position: int, num_values: int) -> List[float]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")
        command = f"GP {param_position} {num_values}"
        
        # Retry logic for GP commands (sometimes they fail with -992 if sent too quickly)
        for attempt in range(3):
            try:
                self.inst.write(command)
                time.sleep(0.1 if attempt > 0 else 0.03)  # Longer wait on retry
                raw = self._safe_read()
                if raw and not raw.strip().startswith("ERROR"):
                    return self._parse_gp_response(raw)
                if attempt < 2:
                    time.sleep(0.2)  # Wait before retry
                    continue
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.2)
                    continue
                raise RuntimeError(f"GP command failed after {attempt + 1} attempts: {e}")
        
        # If we get here, all retries failed
        raise RuntimeError(f"GP command failed: {raw if 'raw' in locals() else 'no response'}")

    @staticmethod
    def _parse_gp_response(response: str) -> List[float]:
        response = response.strip()
        if "=" in response and "PARAM VALUE" in response.upper():
            response = response.split("=", 1)[1].strip()

        separator = None
        for cand in (";", ","):
            if cand in response:
                separator = cand
                break

        values: List[float] = []
        if separator is None:
            if response:
                try:
                    values.append(float(response))
                except ValueError:
                    pass
            return values

        for part in response.split(separator):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(float(part))
            except ValueError:
                pass
        return values


def format_param(value: float | int | str) -> str:
    """Format parameter for EX command."""
    # Handle integers explicitly (e.g., debug flags, cycle counts)
    if isinstance(value, int):
        return str(value)
    
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        # For values >= 1.0, use standard notation if reasonable, otherwise scientific
        if value >= 1.0 and value < 1e6:
            # Use standard notation for reasonable values (e.g., 1.0, 10.5, 100.0)
            if value == int(value):
                return str(int(value))
            return f"{value:.10g}".rstrip('0').rstrip('.')
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


def build_ex_command(
    vhigh: float,
    vlow: float,
    num_steps: int,
    num_cycles: int,
    num_points: int,
    step_delay: float,
    ilimit: float,
    irange: float,
    integration_time: float,
    clarius_debug: int,
) -> str:
    """Build EX command for smu_ivsweep.
    
    Function signature:
    int smu_ivsweep(double Vhigh, double Vlow, int NumSteps, int NumCycles, double *Imeas, int NumIPoints,
                    double *Vforce, int NumVPoints, double StepDelay, double Ilimit,
                    double IRange, double IntegrationTime, int ClariusDebug)
    
    Parameters (13 total):
    1. Vhigh (double, Input) - Positive voltage limit (V), must be >= 0
    2. Vlow (double, Input) - Negative voltage limit (V), must be <= 0
    3. NumSteps (int, Input) - Total steps across full sweep path (4-10000)
    4. NumCycles (int, Input) - Number of cycles to repeat (1-1000)
    5. Imeas (D_ARRAY_T, Output) - GP parameter 5 (empty string in EX command)
    6. NumIPoints (int, Input) - array size for Imeas (must equal (NumSteps + 1) × NumCycles)
    7. Vforce (D_ARRAY_T, Output) - GP parameter 7 (empty string in EX command)
    8. NumVPoints (int, Input) - array size for Vforce (must equal (NumSteps + 1) × NumCycles)
    9. StepDelay (double, Input) - Delay per step (seconds)
    10. Ilimit (double, Input) - Current compliance limit (A)
    11. IRange (double, Input) - Current measurement range (A), 0 = auto range
    12. IntegrationTime (double, Input) - PLC (Power Line Cycles)
    13. ClariusDebug (int, Input) - 0=off, 1=on
    
    Pattern: (0V → Vhigh → 0V → Vlow → 0V) × NumCycles
    Total points = (NumSteps + 1) × NumCycles
    
    Note: Output arrays are passed as empty strings ("") in the EX command.
    They are retrieved via GP commands after execution (GP 5 for Imeas, GP 7 for Vforce).
    """
    
    # Ensure clarius_debug is an integer (0 or 1)
    clarius_debug = int(bool(clarius_debug))  # Convert to 0 or 1
    
    params = [
        format_param(vhigh),            # 1: Vhigh
        format_param(vlow),             # 2: Vlow
        format_param(num_steps),        # 3: NumSteps
        format_param(num_cycles),       # 4: NumCycles
        "",                             # 5: Imeas output array (empty string)
        format_param(num_points),       # 6: NumIPoints (array size, must be (NumSteps + 1) × NumCycles)
        "",                             # 7: Vforce output array (empty string)
        format_param(num_points),       # 8: NumVPoints (array size, must equal NumIPoints)
        format_param(step_delay),       # 9: StepDelay
        format_param(ilimit),           # 10: Ilimit
        format_param(irange),           # 11: IRange
        format_param(integration_time), # 12: IntegrationTime
        format_param(clarius_debug),    # 13: ClariusDebug
    ]
    
    # Debug: verify the debug flag is correctly formatted
    debug_param = params[12]  # 13th parameter (0-indexed: 12)
    if clarius_debug == 1 and debug_param != "1":
        print(f"[WARNING] Debug flag mismatch: clarius_debug={clarius_debug}, formatted='{debug_param}'")
    
    command = f"EX A_Iv_Sweep smu_ivsweep({','.join(params)})"
    return command


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SMU Voltage-Current Sweep for Keithley 4200A-SCS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Connection parameters
    parser.add_argument(
        "--gpib-address",
        type=str,
        default="GPIB0::17::INSTR",
        help="GPIB address (default: GPIB0::17::INSTR)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout in seconds (default: 30.0)"
    )
    
    # Sweep parameters
    parser.add_argument(
        "--vhigh",
        type=float,
        default=2.0,
        help="Positive voltage limit (V), range: 0 to 200 (default: 5.0). Pattern: 0V → Vhigh → 0V → Vlow → 0V"
    )
    parser.add_argument(
        "--vlow",
        type=float,
        default=-2.0,
        help="Negative voltage limit (V), range: -200 to 0 (default: -5.0). Pattern: 0V → Vhigh → 0V → Vlow → 0V"
    )
    parser.add_argument(
        "--num-steps",
        type=int,
        default=40,
        help="Total number of steps across full sweep path (default: 20, range: 4-10000). Steps are distributed across 4 segments"
    )
    parser.add_argument(
        "--num-cycles",
        type=int,
        default=1,
        help="Number of cycles to repeat (default: 1, range: 1-1000). Each cycle: 0V → Vhigh → 0V → Vlow → 0V. Total points = (num-steps + 1) × num-cycles"
    )
    
    # Measurement parameters
    parser.add_argument(
        "--step-delay",
        type=float,
        default=0.01,
        help="Delay at each step before measurement (seconds, default: 0.01 = 10 ms, minimum: 0.001 = 1 ms, range: 0.001 to 10.0). Note: Windows Sleep() requires minimum 1 ms"
    )
    parser.add_argument(
        "--ilimit",
        type=float,
        default=0.1,
        help="Current compliance limit (A, default: 0.1, range: 1e-9 to 1.0)"
    )
    parser.add_argument(
        "--irange",
        type=float,
        default=0.0,
        help="Current measurement range (A). Use 0.0 for auto range (default: 0.0)."
    )
    parser.add_argument(
        "--integration-time",
        type=float,
        default=0.01,
        help="Measurement integration time (PLC - Power Line Cycles, default: 0.01, range: 0.0001 to 1.0). Lower=faster but noisier, Higher=slower but more accurate"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=True,  # Enable debug by default
        help="Enable debug output from C module (ClariusDebug=1) (default: enabled, use --no-debug to disable)"
    )
    parser.add_argument(
        "--no-debug",
        dest="debug",
        action="store_false",
        help="Disable debug output from C module"
    )
    
    # Output options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print EX command without executing"
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip plotting results"
    )
    
    args = parser.parse_args()
    
    # Validate parameters
    if args.vhigh < 0:
        parser.error(f"vhigh={args.vhigh} must be >= 0")
    if args.vlow > 0:
        parser.error(f"vlow={args.vlow} must be <= 0")
    if not (4 <= args.num_steps <= 10000):
        parser.error(f"num-steps={args.num_steps} must be in range [4, 10000]")
    if not (1 <= args.num_cycles <= 1000):
        parser.error(f"num-cycles={args.num_cycles} must be in range [1, 1000]")
    
    # Calculate total points ((num_steps + 1) points per cycle)
    num_points = (args.num_steps + 1) * args.num_cycles
    if not (0.001 <= args.step_delay <= 10.0):
        parser.error(f"step-delay={args.step_delay} must be in range [0.001, 10.0] (minimum 1 ms required)")
    if not (1e-9 <= args.ilimit <= 1.0):
        parser.error(f"ilimit={args.ilimit} must be in range [1e-9, 1.0]")
    if args.irange < 0.0:
        parser.error(f"irange={args.irange} must be >= 0.0 (0.0 means auto range)")
    
    # Validate integration time
    if not (0.0001 <= args.integration_time <= 1.0):
        parser.error(f"integration-time={args.integration_time} must be in range [0.0001, 1.0]")
    
    # Build command
    # Debug is enabled by default (True), can be disabled with --no-debug
    clarius_debug = 1 if args.debug else 0
    command = build_ex_command(
        vhigh=args.vhigh,
        vlow=args.vlow,
        num_steps=args.num_steps,
        num_cycles=args.num_cycles,
        num_points=num_points,
        step_delay=args.step_delay,
        ilimit=args.ilimit,
        irange=args.irange,
        integration_time=args.integration_time,
        clarius_debug=clarius_debug,
    )
    
    if args.dry_run:
        print("=" * 80)
        print("[DRY RUN] Generated EX command:")
        print("=" * 80)
        print(command)
        print("=" * 80)
        return
    
    # Connect and execute
    controller = KXCIClient(gpib_address=args.gpib_address, timeout=args.timeout)
    
    if not controller.connect():
        print("[ERROR] Failed to connect to instrument")
        return
    
    try:
        if not controller._enter_ul_mode():
            raise RuntimeError("Failed to enter UL mode")
        
        print("\n[KXCI] Sending command to instrument...")
        print(f"[KXCI] Pattern: (0V → {args.vhigh}V → 0V → {args.vlow}V → 0V) × {args.num_cycles} cycles")
        print(f"[KXCI] Vhigh: {args.vhigh} V")
        print(f"[KXCI] Vlow: {args.vlow} V")
        print(f"[KXCI] NumSteps: {args.num_steps} (distributed across 4 segments)")
        
        # Calculate and display step distribution (matching C code logic)
        steps_per_segment = args.num_steps // 4
        remainder_steps = args.num_steps % 4
        seg1_steps = steps_per_segment + (1 if remainder_steps > 0 else 0)
        remainder_steps = remainder_steps - (1 if remainder_steps > 0 else 0)
        seg2_steps = steps_per_segment + (1 if remainder_steps > 0 else 0)
        remainder_steps = remainder_steps - (1 if remainder_steps > 0 else 0)
        seg3_steps = steps_per_segment + (1 if remainder_steps > 0 else 0)
        remainder_steps = remainder_steps - (1 if remainder_steps > 0 else 0)
        seg4_steps = steps_per_segment + (1 if remainder_steps > 0 else 0)
        
        # Point counting: Segment 1 has starting point (seg_steps + 1), others just have seg_steps
        # Segment 3 no longer has duplicate 0V starting point (we removed it)
        seg1_points = seg1_steps + 1  # Starts at 0V, then seg_steps steps
        seg2_points = seg2_steps      # Just seg_steps steps (ends at 0V)
        seg3_points = seg3_steps      # Just seg_steps steps (no duplicate 0V start)
        seg4_points = seg4_steps      # Just seg_steps steps (ends at 0V)
        
        print(f"[KXCI] Step distribution:")
        print(f"  - Segment 1 (0V → Vhigh): {seg1_steps} steps → {seg1_points} points (includes starting 0V)")
        print(f"  - Segment 2 (Vhigh → 0V): {seg2_steps} steps → {seg2_points} points")
        print(f"  - Segment 3 (0V → Vlow): {seg3_steps} steps → {seg3_points} points")
        print(f"  - Segment 4 (Vlow → 0V): {seg4_steps} steps → {seg4_points} points")
        print(f"  - Total: {seg1_steps + seg2_steps + seg3_steps + seg4_steps} steps → {seg1_points + seg2_points + seg3_points + seg4_points} points (should be {args.num_steps + 1})")
        
        print(f"[KXCI] NumCycles: {args.num_cycles}")
        print(f"[KXCI] Points per cycle: {args.num_steps + 1} (NumSteps + 1 starting point)")
        print(f"[KXCI] Total points: {num_points} (({args.num_steps} + 1) × {args.num_cycles})")
        print(f"[KXCI] Step delay: {args.step_delay*1000:.1f} ms per step")
        print(f"[KXCI] Current limit: {args.ilimit:.2e} A")
        print(f"[KXCI] Current range: {args.irange:.2e} A ({'AUTO' if args.irange == 0.0 else 'FIXED'})")
        print(f"[KXCI] Integration time: {args.integration_time:.6f} PLC")
        print(f"[KXCI] Debug output: {'ON' if args.debug else 'OFF'}")
        
        return_value, error = controller._execute_ex_command(command)
        
        if error:
            raise RuntimeError(f"EX command failed: {error}")
        if return_value is not None:
            print(f"Return value: {return_value}")
            if return_value < 0:
                error_messages = {
                    -1: "Invalid Vhigh (must be >= 0) or Vlow (must be <= 0)",
                    -2: "NumIPoints != NumVPoints (array size mismatch)",
                    -3: "NumIPoints != (NumSteps + 1) × NumCycles (array size mismatch)",
                    -4: "Invalid array sizes (NumIPoints or NumVPoints < NumSteps + 1)",
                    -5: "Invalid NumSteps (must be >= 4 and <= 10000) or NumCycles (must be >= 1 and <= 1000)",
                    -6: "limiti() failed (check current limit value)",
                    -7: "measi() failed (check SMU connection)",
                }
                msg = error_messages.get(return_value, f"Unknown error code: {return_value}")
                raise RuntimeError(f"EX command returned error code: {return_value} - {msg}")
            elif return_value == 0:
                print("[OK] Return value is 0 (success)")
        
        print("\n[KXCI] Retrieving data...")
        time.sleep(0.2)
        
        # Query data from GP parameters
        # Based on function signature: 
        # 1=Vhigh, 2=Vlow, 3=NumSteps, 4=NumCycles, 5=Imeas (output), 6=NumIPoints,
        # 7=Vforce (output), 8=NumVPoints, 9=StepDelay, 10=Ilimit, 11=IRange,
        # 12=IntegrationTime, 13=ClariusDebug
        def safe_query(param: int, count: int, name: str = "") -> List[float]:
            """Query GP parameter with retry."""
            for attempt in range(3):
                try:
                    print(f"  Querying GP {param} ({name})... ", end="", flush=True)
                    data = controller._query_gp(param, count)
                    print(f"✓ {len(data)} values")
                    return data
                except Exception as e:
                    if attempt < 2:
                        print(f"⚠ retry ({e})")
                        time.sleep(0.5)
                    else:
                        print(f"✗ failed ({e})")
                        return []
            return []
        
        print(f"[KXCI] Requesting {num_points} points")
        # GP parameter 7 = Vforce (7th parameter in function signature, after NumIPoints)
        # GP parameter 5 = Imeas (5th parameter in function signature, after NumCycles)
        voltage = safe_query(7, num_points, "Vforce")
        current = safe_query(5, num_points, "Imeas")
        
        print(f"[KXCI] Received: {len(voltage)} voltage, {len(current)} current samples")
        
        # Ensure arrays are same length
        min_len = min(len(voltage), len(current))
        voltage = voltage[:min_len]
        current = current[:min_len]
        
        if min_len == 0:
            print("\n[ERROR] No data returned!")
            return
        
        # Calculate resistance
        resistances: List[float] = []
        for v, i in zip(voltage, current):
            if abs(i) < 1e-12:
                resistances.append(float("inf"))
            else:
                resistances.append(v / i)
        
        # Display results
        print("\n[RESULTS] IV Sweep Data:")
        print(f"Total points measured: {min_len}")
        print(f"{'Idx':>4} {'Voltage (V)':>14} {'Current (A)':>14} {'Resistance (Ω)':>16}")
        print("-" * 50)
        
        # Show all points, or first 50 if there are many
        display_limit = min(min_len, 50)
        for idx in range(display_limit):
            v = voltage[idx]
            i = current[idx]
            r = resistances[idx]
            r_str = f"{r:.2e}" if abs(r) < 1e10 else "inf"
            print(f"{idx:>4} {v:>14.6f} {i:>14.6e} {r_str:>16}")
        
        if min_len > display_limit:
            print(f"... ({min_len - display_limit} more points)")
        
        # Statistics
        import numpy as np
        valid_currents = [i for i in current if abs(i) > 1e-12]
        if valid_currents:
            print(f"\n[STATS] Current Statistics:")
            print(f"  Min: {np.min(valid_currents):.3e} A")
            print(f"  Max: {np.max(valid_currents):.3e} A")
            print(f"  Mean: {np.mean(valid_currents):.3e} A")
            print(f"  Std: {np.std(valid_currents):.3e} A")
        
        valid_resistances = [r for r in resistances if abs(r) < 1e10]
        if valid_resistances:
            print(f"\n[STATS] Resistance Statistics:")
            print(f"  Min: {np.min(valid_resistances):.3e} Ω")
            print(f"  Max: {np.max(valid_resistances):.3e} Ω")
            print(f"  Mean: {np.mean(valid_resistances):.3e} Ω")
        
        # Plot results
        if not args.no_plot:
            try:
                import matplotlib.pyplot as plt
                
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
                
                # IV curve
                ax1.plot(voltage, current, 'b-o', markersize=4)
                ax1.set_xlabel('Voltage (V)')
                ax1.set_ylabel('Current (A)')
                ax1.set_title('IV Characteristic')
                ax1.grid(True, alpha=0.3)
                ax1.set_yscale('log')
                
                # Resistance vs Voltage
                valid_r = [r for r in resistances if abs(r) < 1e10]
                valid_v = [v for v, r in zip(voltage, resistances) if abs(r) < 1e10]
                if valid_r:
                    ax2.plot(valid_v, valid_r, 'r-o', markersize=4)
                    ax2.set_xlabel('Voltage (V)')
                    ax2.set_ylabel('Resistance (Ω)')
                    ax2.set_title('Resistance vs Voltage')
                    ax2.grid(True, alpha=0.3)
                    ax2.set_yscale('log')
                
                plt.tight_layout()
                plt.show()
                
            except ImportError:
                print("\n[INFO] matplotlib not available, skipping plot")
            except Exception as e:
                print(f"\n[WARNING] Failed to plot: {e}")
        
    finally:
        try:
            controller._exit_ul_mode()
        except Exception:
            pass
        controller.disconnect()


if __name__ == "__main__":
    main()

