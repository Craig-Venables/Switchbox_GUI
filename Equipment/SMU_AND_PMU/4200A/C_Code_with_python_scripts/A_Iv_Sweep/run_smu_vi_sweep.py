"""SMU Voltage-Current Sweep runner (KXCI compatible).

This script wraps the `EX A_Iv_Sweep smu_ivsweep(...)` command,
executes it on a Keithley 4200A-SCS SMU via KXCI, and retrieves the voltage
and current data from the cyclical IV sweep.

Purpose:
--------
This script performs a cyclical voltage-current (IV) sweep using the SMU (Source
Measurement Unit) of the Keithley 4200A-SCS. It:
1. Sweeps in pattern: 0V → +Vpos → Vneg → 0V
2. Repeats this pattern NumCycles times
3. At each voltage point, waits for settling time
4. Measures current
5. Returns voltage and current arrays for plotting IV curves

Pattern: (0V → +Vpos → Vneg → 0V) × NumCycles
Total points = 4 × NumCycles

Key Features:
-------------
- Cyclical pattern: 0V → +Vpos → Vneg → 0V, repeated n times
- Symmetric or asymmetric sweeps (Vneg=0 uses -Vpos automatically)
- Settling time at each voltage point (allows device to stabilize before measurement)
- Current compliance limit protection
- Error handling for invalid parameters
- Returns both forced voltage and measured current arrays

Parameters:
-----------
- Vpos: Positive voltage (V), range: 0 to 200 V (default: 5.0)
- Vneg: Negative voltage (V), range: -200 to 0 V (default: 0.0)
         If Vneg=0, automatically uses -Vpos (symmetric sweep)
- NumCycles: Number of cycles to repeat (default: 1, range: 1-1000)
             Total points = 4 × NumCycles
- SettleTime: Settling time at each voltage point (seconds, default: 0.001 s = 1 ms)
- Ilimit: Current compliance limit (A, default: 0.1 A)

Usage examples:

    # Basic symmetric sweep: 0V → +5V → -5V → 0V (1 cycle = 4 points)
    python run_smu_vi_sweep.py --vpos 5

    # Asymmetric sweep: 0V → +5V → -2V → 0V (1 cycle = 4 points)
    python run_smu_vi_sweep.py --vpos 5 --vneg -2

    # Multiple cycles: (0V → +5V → -5V → 0V) × 3 (12 points total)
    python run_smu_vi_sweep.py --vpos 5 --num-cycles 3

    # Fast sweep with minimal settling time
    python run_smu_vi_sweep.py --vpos 3 --settle-time 0.0001

    # Custom current limit for high-resistance devices
    python run_smu_vi_sweep.py --vpos 5 --ilimit 1e-6

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
            # (4 × num_cycles) × (settle_time + integration_time × 0.01) × safety_factor
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
    vpos: float,
    vneg: float,
    num_cycles: int,
    num_points: int,
    settle_time: float,
    ilimit: float,
    integration_time: float,
    clarius_debug: int,
) -> str:
    """Build EX command for smu_ivsweep.
    
    Function signature:
    int smu_ivsweep(double Vpos, double Vneg, int NumCycles, double *Imeas, int NumIPoints,
                    double *Vforce, int NumVPoints, double SettleTime, double Ilimit,
                    double IntegrationTime, int ClariusDebug)
    
    Parameters (10 total):
    1. Vpos (double, Input) - Positive voltage (V), must be >= 0
    2. Vneg (double, Input) - Negative voltage (V), must be <= 0. If 0, uses -Vpos (symmetric)
    3. NumCycles (int, Input) - Number of cycles to repeat (1-1000)
    4. Imeas (D_ARRAY_T, Output) - GP parameter 4 (empty string in EX command)
    5. NumIPoints (int, Input) - array size for Imeas (must equal 4 × NumCycles)
    6. Vforce (D_ARRAY_T, Output) - GP parameter 6 (empty string in EX command)
    7. NumVPoints (int, Input) - array size for Vforce (must equal 4 × NumCycles)
    8. SettleTime (double, Input)
    9. Ilimit (double, Input)
    10. IntegrationTime (double, Input) - PLC (Power Line Cycles)
    11. ClariusDebug (int, Input) - 0=off, 1=on
    
    Pattern: (0V → +Vpos → Vneg → 0V) × NumCycles
    Total points = 4 × NumCycles
    
    Note: Output arrays are passed as empty strings ("") in the EX command.
    They are retrieved via GP commands after execution (GP 4 for Imeas, GP 6 for Vforce).
    """
    
    # Ensure clarius_debug is an integer (0 or 1)
    clarius_debug = int(bool(clarius_debug))  # Convert to 0 or 1
    
    params = [
        format_param(vpos),            # 1: Vpos
        format_param(vneg),            # 2: Vneg (0 for auto-symmetric with -Vpos)
        format_param(num_cycles),      # 3: NumCycles
        "",                             # 4: Imeas output array (empty string)
        format_param(num_points),       # 5: NumIPoints (array size, must be 4 × NumCycles)
        "",                             # 6: Vforce output array (empty string)
        format_param(num_points),       # 7: NumVPoints (array size, must equal NumIPoints)
        format_param(settle_time),      # 8: SettleTime
        format_param(ilimit),           # 9: Ilimit
        format_param(integration_time), # 10: IntegrationTime
        format_param(clarius_debug),    # 11: ClariusDebug
    ]
    
    # Debug: verify the debug flag is correctly formatted
    debug_param = params[10]  # 11th parameter (0-indexed: 10)
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
        "--vpos",
        type=float,
        default=2.0,
        help="Positive voltage (V), range: 0 to 200 (default: 5.0). Pattern: 0V → +Vpos → Vneg → 0V"
    )
    parser.add_argument(
        "--vneg",
        type=float,
        default=0.0,
        help="Negative voltage (V), range: -200 to 0 (default: 0.0). If 0, automatically uses -Vpos for symmetric sweep. Pattern: 0V → +Vpos → Vneg → 0V"
    )
    parser.add_argument(
        "--num-cycles",
        type=int,
        default=1,
        help="Number of cycles to repeat (default: 1, range: 1-1000). Each cycle: 0V → +Vpos → Vneg → 0V. Total points = 4 × num-cycles"
    )
    
    # Measurement parameters
    parser.add_argument(
        "--settle-time",
        type=float,
        default=0.001,
        help="Settling time at each voltage point (seconds, default: 0.001 = 1 ms, range: 0.0001 to 10.0)"
    )
    parser.add_argument(
        "--ilimit",
        type=float,
        default=0.1,
        help="Current compliance limit (A, default: 0.1, range: 1e-9 to 1.0)"
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
        help="Enable debug output from C module (ClariusDebug=1)"
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
    if args.vpos < 0:
        parser.error(f"vpos={args.vpos} must be >= 0")
    if args.vneg > 0:
        parser.error(f"vneg={args.vneg} must be <= 0 (use 0 for auto-symmetric with -vpos)")
    if not (1 <= args.num_cycles <= 1000):
        parser.error(f"num-cycles={args.num_cycles} must be in range [1, 1000]")
    
    # Calculate total points (4 points per cycle)
    num_points = 4 * args.num_cycles
    if not (0.0001 <= args.settle_time <= 10.0):
        parser.error(f"settle-time={args.settle_time} must be in range [0.0001, 10.0]")
    if not (1e-9 <= args.ilimit <= 1.0):
        parser.error(f"ilimit={args.ilimit} must be in range [1e-9, 1.0]")
    
    # Validate integration time
    if not (0.0001 <= args.integration_time <= 1.0):
        parser.error(f"integration-time={args.integration_time} must be in range [0.0001, 1.0]")
    
    # Build command
    clarius_debug = 1 if args.debug else 0
    command = build_ex_command(
        vpos=args.vpos,
        vneg=args.vneg,
        num_cycles=args.num_cycles,
        num_points=num_points,
        settle_time=args.settle_time,
        ilimit=args.ilimit,
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
        vneg_display = args.vneg if args.vneg != 0 else -args.vpos
        print(f"[KXCI] Pattern: (0V → +{args.vpos}V → {vneg_display}V → 0V) × {args.num_cycles} cycles")
        print(f"[KXCI] Vpos: {args.vpos} V")
        print(f"[KXCI] Vneg: {args.vneg} V" + (f" (auto → {vneg_display} V)" if args.vneg == 0 else ""))
        print(f"[KXCI] NumCycles: {args.num_cycles}")
        print(f"[KXCI] Total points: {num_points} (4 × {args.num_cycles})")
        print(f"[KXCI] Settle time: {args.settle_time*1000:.1f} ms per point")
        print(f"[KXCI] Current limit: {args.ilimit:.2e} A")
        print(f"[KXCI] Integration time: {args.integration_time:.6f} PLC")
        print(f"[KXCI] Debug output: {'ON' if args.debug else 'OFF'}")
        
        return_value, error = controller._execute_ex_command(command)
        
        if error:
            raise RuntimeError(f"EX command failed: {error}")
        if return_value is not None:
            print(f"Return value: {return_value}")
            if return_value < 0:
                error_messages = {
                    -1: "Invalid Vpos (must be >= 0) or Vneg (must be <= 0)",
                    -2: "NumIPoints != NumVPoints (array size mismatch)",
                    -3: "NumIPoints != 4 × NumCycles (array size must equal 4 × number of cycles)",
                    -4: "Invalid array sizes (NumIPoints or NumVPoints < 4)",
                    -5: "Invalid NumCycles (must be >= 1 and <= 1000)",
                    -6: "forcev() failed (check SMU connection and voltage range)",
                    -7: "measi() failed (check SMU connection)",
                    -8: "limiti() failed (check current limit value)",
                    -9: "setmode() failed (check SMU connection)",
                }
                msg = error_messages.get(return_value, f"Unknown error code: {return_value}")
                raise RuntimeError(f"EX command returned error code: {return_value} - {msg}")
            elif return_value == 0:
                print("[OK] Return value is 0 (success)")
        
        print("\n[KXCI] Retrieving data...")
        time.sleep(0.2)
        
        # Query data from GP parameters
        # Based on function signature: 
        # 1=Vpos, 2=Vneg, 3=NumCycles, 4=Imeas (output), 5=NumIPoints, 6=Vforce (output), 7=NumVPoints, 8=SettleTime, 9=Ilimit, 10=IntegrationTime, 11=ClariusDebug
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
        # GP parameter 6 = Vforce (6th parameter in function signature, after NumIPoints)
        # GP parameter 4 = Imeas (4th parameter in function signature, after NumCycles)
        voltage = safe_query(6, num_points, "Vforce")
        current = safe_query(4, num_points, "Imeas")
        
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
        print(f"{'Idx':>4} {'Voltage (V)':>14} {'Current (A)':>14} {'Resistance (Ω)':>16}")
        print("-" * 50)
        
        for idx in range(min(min_len, 20)):  # Show first 20 points
            v = voltage[idx]
            i = current[idx]
            r = resistances[idx]
            r_str = f"{r:.2e}" if abs(r) < 1e10 else "inf"
            print(f"{idx:>4} {v:>14.6f} {i:>14.6e} {r_str:>16}")
        
        if min_len > 20:
            print(f"... ({min_len - 20} more points)")
        
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

