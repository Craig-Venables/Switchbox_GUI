"""SMU Full Voltage-Current Sweep runner (KXCI compatible).

This script wraps the `EX Labview_Controlled_Programs_Kemp SMU_FullIVsweep(...)` command,
executes it on a Keithley 4200A-SCS SMU via KXCI, and retrieves the voltage
and current data from the full bidirectional IV sweep.

Purpose:
--------
This script performs a complete bidirectional voltage-current (IV) sweep using the SMU (Source
Measurement Unit) of the Keithley 4200A-SCS. It:
1. Sweeps in pattern: 0V → Vhigh → 0V → Vlow → 0V
2. Uses PointsPerSegment evenly distributed points per segment
3. At each step, forces voltage and measures current
4. Returns voltage and current arrays for plotting IV curves

Pattern: 0V → Vhigh → 0V → Vlow → 0V (triangular sweep)
Total points = 4 × PointsPerSegment + 1

Key Features:
-------------
- Full bidirectional sweep: 0V → Vhigh → 0V → Vlow → 0V
- Configurable number of points per segment
- Even voltage steps using same method as SMU_VIsweep
- Returns both forced voltage and measured current arrays
- Error handling for invalid parameters

Parameters:
-----------
- Vhigh: Positive voltage limit (V), range: 0 to 200 V (default: 5.0)
- Vlow: Negative voltage limit (V), range: -200 to 0 V (default: -5.0)
- PointsPerSegment: Number of points per segment (default: 10, range: 2-1000)
                    Total points = 4 × PointsPerSegment + 1

Usage examples:

    # Basic sweep: 0V → 5V → 0V → -5V → 0V (41 points with 10 points/segment)
    python run_smu_visweep.py --vhigh 5 --vlow -5 --points-per-segment 10

    # High-resolution sweep: 0V → 3V → 0V → -2V → 0V (201 points with 50 points/segment)
    python run_smu_visweep.py --vhigh 3 --vlow -2 --points-per-segment 50

    # Asymmetric sweep: 0V → 2V → 0V → -1V → 0V (21 points with 5 points/segment)
    python run_smu_visweep.py --vhigh 2 --vlow -1 --points-per-segment 5

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
            # Wait for measurement to complete
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
    # Handle integers explicitly
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
    points_per_segment: int,
    num_points: int,
) -> str:
    """Build EX command for SMU_FullIVsweep.
    
    Function signature:
    int SMU_FullIVsweep(double Vhigh, double Vlow, int PointsPerSegment, double *Imeas, int NumIPoints,
                        double *Vforce, int NumVPoints)
    
    Parameters (7 total):
    1. Vhigh (double, Input) - Positive voltage limit (V), range: 0 to 200
    2. Vlow (double, Input) - Negative voltage limit (V), range: -200 to 0
    3. PointsPerSegment (int, Input) - Points per segment, range: 2-1000
    4. Imeas (D_ARRAY_T, Output) - GP parameter 4 (empty string in EX command)
    5. NumIPoints (int, Input) - array size for Imeas (must equal 4 × PointsPerSegment + 1)
    6. Vforce (D_ARRAY_T, Output) - GP parameter 6 (empty string in EX command)
    7. NumVPoints (int, Input) - array size for Vforce (must equal NumIPoints)
    
    Pattern: 0V → Vhigh → 0V → Vlow → 0V (triangular sweep)
    Total points = 4 × PointsPerSegment + 1
    
    Note: Output arrays are passed as empty strings ("") in the EX command.
    They are retrieved via GP commands after execution (GP 4 for Imeas, GP 6 for Vforce).
    """
    
    params = [
        format_param(vhigh),              # 1: Vhigh
        format_param(vlow),               # 2: Vlow
        format_param(points_per_segment), # 3: PointsPerSegment
        "",                               # 4: Imeas output array (empty string)
        format_param(num_points),         # 5: NumIPoints (array size, must equal 4 × PointsPerSegment + 1)
        "",                               # 6: Vforce output array (empty string)
        format_param(num_points),         # 7: NumVPoints (array size, must equal NumIPoints)
    ]
    
    command = f"EX A_Iv_Sweep SMU_FullIVsweep({','.join(params)})"
    return command


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SMU Full Voltage-Current Sweep for Keithley 4200A-SCS",
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
        "--points-per-segment",
        type=int,
        default=10,
        help="Number of points per segment (default: 10, range: 2-1000). Total points = 4 × points-per-segment + 1"
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
    if not (2 <= args.points_per_segment <= 1000):
        parser.error(f"points-per-segment={args.points_per_segment} must be in range [2, 1000]")
    
    # Calculate total points: 4 segments × PointsPerSegment + 1 starting point
    num_points = 4 * args.points_per_segment + 1
    
    # Build command
    command = build_ex_command(
        vhigh=args.vhigh,
        vlow=args.vlow,
        points_per_segment=args.points_per_segment,
        num_points=num_points,
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
        print(f"[KXCI] Pattern: (0V → {args.vhigh}V → 0V → {args.vlow}V → 0V)")
        print(f"[KXCI] Vhigh: {args.vhigh} V")
        print(f"[KXCI] Vlow: {args.vlow} V")
        print(f"[KXCI] PointsPerSegment: {args.points_per_segment}")
        print(f"[KXCI] Total points: {num_points} (4 × {args.points_per_segment} + 1)")
        
        return_value, error = controller._execute_ex_command(command)
        
        if error:
            raise RuntimeError(f"EX command failed: {error}")
        if return_value is not None:
            print(f"Return value: {return_value}")
            if return_value < 0:
                error_messages = {
                    -1: "Vhigh < 0 or Vlow > 0 (invalid voltage limits)",
                    -2: "NumIPoints != NumVPoints (array size mismatch)",
                    -3: "NumIPoints != (4 × PointsPerSegment + 1) (array size mismatch)",
                    -4: "PointsPerSegment < 2 or PointsPerSegment > 1000 (invalid points per segment)",
                    -5: "forcev() failed (check SMU connection)",
                    -6: "measi() failed (check SMU connection)",
                }
                msg = error_messages.get(return_value, f"Unknown error code: {return_value}")
                raise RuntimeError(f"EX command returned error code: {return_value} - {msg}")
            elif return_value == 0:
                print("[OK] Return value is 0 (success)")
        
        print("\n[KXCI] Retrieving data...")
        time.sleep(0.2)
        
        # Query data from GP parameters
        # Based on function signature: 
        # 1=Vhigh, 2=Vlow, 3=PointsPerSegment, 4=Imeas (output), 5=NumIPoints, 6=Vforce (output), 7=NumVPoints
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
        # GP parameter 4 = Imeas (4th parameter in function signature, after PointsPerSegment)
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

