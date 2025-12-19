"""SMU Full Voltage-Current Sweep runner using SMU_VIsweep (KXCI compatible).

This script performs a complete bidirectional IV sweep by calling SMU_VIsweep
multiple times (once for each segment) to create a full triangular sweep pattern:
0V → Vhigh → 0V → Vlow → 0V

Purpose:
--------
This script performs a complete bidirectional voltage-current (IV) sweep using the SMU (Source
Measurement Unit) of the Keithley 4200A-SCS by calling SMU_VIsweep 4 times:
1. Segment 1: 0V → Vhigh (PointsPerSegment + 1 points)
2. Segment 2: Vhigh → 0V (PointsPerSegment points, excluding duplicate Vhigh)
3. Segment 3: 0V → Vlow (PointsPerSegment points, excluding duplicate 0V)
4. Segment 4: Vlow → 0V (PointsPerSegment points, excluding duplicate Vlow)

Pattern: 0V → Vhigh → 0V → Vlow → 0V (triangular sweep)
Total points = 4 × PointsPerSegment + 1

Key Features:
-------------
- Full bidirectional sweep: 0V → Vhigh → 0V → Vlow → 0V
- Uses SMU_VIsweep for each segment (ensures even steps)
- Combines results from all segments into final arrays
- Configurable number of points per segment
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
    python run_smu_full_visweep.py --vhigh 5 --vlow -5 --points-per-segment 10

    # High-resolution sweep: 0V → 3V → 0V → -2V → 0V (201 points with 50 points/segment)
    python run_smu_full_visweep.py --vhigh 3 --vlow -2 --points-per-segment 50

    # Asymmetric sweep: 0V → 2V → 0V → -1V → 0V (21 points with 5 points/segment)
    python run_smu_full_visweep.py --vhigh 2 --vlow -1 --points-per-segment 5

Pass `--dry-run` to print the generated EX commands without contacting the instrument.
"""

from __future__ import annotations

import argparse
import re
import time
from typing import List, Optional, Tuple


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

    def _execute_ex_command(self, command: str, wait_seconds: float = 0.1) -> tuple[Optional[int], Optional[str]]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")

        try:
            self.inst.write(command)
            time.sleep(0.03)
            # Wait for measurement to complete - SMU_VIsweep executes quickly, minimal wait needed
            # LabVIEW typically doesn't wait long for simple sweeps
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            # Try to read response immediately (non-blocking)
            response = self._safe_read()
            # If no response yet, wait a bit more and try again
            if not response:
                time.sleep(0.05)
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
                # Minimal wait - LabVIEW doesn't wait long between GP commands
                time.sleep(0.02 if attempt == 0 else 0.05)  # Very short wait, slightly longer on retry
                raw = self._safe_read()
                if raw and not raw.strip().startswith("ERROR"):
                    return self._parse_gp_response(raw)
                if attempt < 2:
                    time.sleep(0.05)  # Short wait before retry
                    continue
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.05)
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
    vstart: float,
    vstop: float,
    num_points: int,
) -> str:
    """Build EX command for SMU_VIsweep.
    
    Function signature:
    int SMU_VIsweep(double Vstart, double Vstop, double *Imeas, int NumIPoints,
                    double *Vforce, int NumVPoints)
    
    Parameters (6 total):
    1. Vstart (double, Input) - Starting voltage (V), range: -200 to 200
    2. Vstop (double, Input) - Stopping voltage (V), range: -200 to 200
    3. Imeas (D_ARRAY_T, Output) - GP parameter 3 (empty string in EX command)
    4. NumIPoints (int, Input) - array size for Imeas
    5. Vforce (D_ARRAY_T, Output) - GP parameter 5 (empty string in EX command)
    6. NumVPoints (int, Input) - array size for Vforce (must equal NumIPoints)
    
    Pattern: Linear sweep from Vstart to Vstop
    Total points = NumPoints
    
    Note: Output arrays are passed as empty strings ("") in the EX command.
    They are retrieved via GP commands after execution (GP 3 for Imeas, GP 5 for Vforce).
    """
    
    params = [
        format_param(vstart),      # 1: Vstart
        format_param(vstop),        # 2: Vstop
        "",                         # 3: Imeas output array (empty string)
        format_param(num_points),   # 4: NumIPoints (array size)
        "",                         # 5: Vforce output array (empty string)
        format_param(num_points),   # 6: NumVPoints (array size, must equal NumIPoints)
    ]
    
    command = f"EX A_Iv_Sweep SMU_VIsweep({','.join(params)})"
    return command


def execute_segment(
    controller: KXCIClient,
    segment_num: int,
    vstart: float,
    vstop: float,
    num_points: int,
    skip_first: bool = False,
) -> Tuple[List[float], List[float]]:
    """Execute a single segment using SMU_VIsweep and retrieve data.
    
    Args:
        controller: KXCI client instance
        segment_num: Segment number (1-4) for logging
        vstart: Starting voltage
        vstop: Stopping voltage
        num_points: Number of points for this segment
        skip_first: If True, skip the first point (already measured in previous segment)
    
    Returns:
        Tuple of (voltage_list, current_list)
    """
    command = build_ex_command(vstart, vstop, num_points)
    
    print(f"\n[Segment {segment_num}] Executing: {vstart}V → {vstop}V ({num_points} points)")
    
    # Calculate wait time based on number of points
    # SMU_VIsweep executes quickly: ~0.01s per point (forcev + measi with default integration time)
    # Add small safety margin
    estimated_wait = max(0.05, num_points * 0.01 + 0.05)  # Minimum 50ms, ~10ms per point + 50ms safety
    
    return_value, error = controller._execute_ex_command(command, wait_seconds=estimated_wait)
    
    if error:
        raise RuntimeError(f"Segment {segment_num} EX command failed: {error}")
    if return_value is not None:
        if return_value < 0:
            error_messages = {
                -1: "Vstart == Vstop (sweep range is zero)",
                -2: "NumIPoints != NumVPoints (array size mismatch)",
            }
            msg = error_messages.get(return_value, f"Unknown error code: {return_value}")
            raise RuntimeError(f"Segment {segment_num} returned error code: {return_value} - {msg}")
        elif return_value == 0:
            print(f"[Segment {segment_num}] Return value is 0 (success)")
    
    # Minimal delay before querying GP - SMU_VIsweep completes quickly
    time.sleep(0.05)
    
    # Query data from GP parameters
    # GP parameter 5 = Vforce (5th parameter in function signature, after NumIPoints)
    # GP parameter 3 = Imeas (3rd parameter in function signature, after Vstop)
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
                    time.sleep(0.05)  # Short wait before retry
                else:
                    print(f"✗ failed ({e})")
                    return []
        return []
    
    voltage = safe_query(5, num_points, "Vforce")
    current = safe_query(3, num_points, "Imeas")
    
    # Skip first point if requested (to avoid duplicates between segments)
    if skip_first and len(voltage) > 0 and len(current) > 0:
        voltage = voltage[1:]
        current = current[1:]
        print(f"  Skipped first point (duplicate from previous segment)")
    
    return voltage, current


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SMU Full Voltage-Current Sweep using SMU_VIsweep for Keithley 4200A-SCS",
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
        default=5.0,
        help="Positive voltage limit (V), range: 0 to 200 (default: 5.0). Pattern: 0V → Vhigh → 0V → Vlow → 0V"
    )
    parser.add_argument(
        "--vlow",
        type=float,
        default=-5.0,
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
        help="Print EX commands without executing"
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
    
    # Calculate points per segment
    # Segment 1: PointsPerSegment + 1 points (includes starting 0V)
    # Segments 2-4: PointsPerSegment points each (excluding duplicate start points)
    seg1_points = args.points_per_segment + 1
    seg2_points = args.points_per_segment
    seg3_points = args.points_per_segment
    seg4_points = args.points_per_segment
    total_points = seg1_points + seg2_points + seg3_points + seg4_points
    
    print("\n" + "=" * 80)
    print("SMU Full IV Sweep using SMU_VIsweep")
    print("=" * 80)
    print(f"Pattern: (0V → {args.vhigh}V → 0V → {args.vlow}V → 0V)")
    print(f"Vhigh: {args.vhigh} V")
    print(f"Vlow: {args.vlow} V")
    print(f"PointsPerSegment: {args.points_per_segment}")
    print(f"\nSegment breakdown:")
    print(f"  Segment 1: 0V → {args.vhigh}V ({seg1_points} points)")
    print(f"  Segment 2: {args.vhigh}V → 0V ({seg2_points} points, skip duplicate {args.vhigh}V)")
    print(f"  Segment 3: 0V → {args.vlow}V ({seg3_points} points, skip duplicate 0V)")
    print(f"  Segment 4: {args.vlow}V → 0V ({seg4_points} points, skip duplicate {args.vlow}V)")
    print(f"  Total: {total_points} points")
    print("=" * 80)
    
    if args.dry_run:
        print("\n[DRY RUN] Generated EX commands:")
        print(f"  Segment 1: {build_ex_command(0.0, args.vhigh, seg1_points)}")
        print(f"  Segment 2: {build_ex_command(args.vhigh, 0.0, seg2_points)}")
        print(f"  Segment 3: {build_ex_command(0.0, args.vlow, seg3_points)}")
        print(f"  Segment 4: {build_ex_command(args.vlow, 0.0, seg4_points)}")
        return
    
    # Connect and execute
    controller = KXCIClient(gpib_address=args.gpib_address, timeout=args.timeout)
    
    if not controller.connect():
        print("[ERROR] Failed to connect to instrument")
        return
    
    try:
        if not controller._enter_ul_mode():
            raise RuntimeError("Failed to enter UL mode")
        
        # Execute all segments
        all_voltage: List[float] = []
        all_current: List[float] = []
        
        # Segment 1: 0V → Vhigh (include all points)
        v1, i1 = execute_segment(controller, 1, 0.0, args.vhigh, seg1_points, skip_first=False)
        all_voltage.extend(v1)
        all_current.extend(i1)
        
        # Segment 2: Vhigh → 0V (skip first point to avoid duplicate Vhigh)
        v2, i2 = execute_segment(controller, 2, args.vhigh, 0.0, seg2_points, skip_first=True)
        all_voltage.extend(v2)
        all_current.extend(i2)
        
        # Segment 3: 0V → Vlow (skip first point to avoid duplicate 0V)
        v3, i3 = execute_segment(controller, 3, 0.0, args.vlow, seg3_points, skip_first=True)
        all_voltage.extend(v3)
        all_current.extend(i3)
        
        # Segment 4: Vlow → 0V (skip first point to avoid duplicate Vlow)
        v4, i4 = execute_segment(controller, 4, args.vlow, 0.0, seg4_points, skip_first=True)
        all_voltage.extend(v4)
        all_current.extend(i4)
        
        print(f"\n[KXCI] Combined results: {len(all_voltage)} voltage, {len(all_current)} current samples")
        
        # Ensure arrays are same length
        min_len = min(len(all_voltage), len(all_current))
        all_voltage = all_voltage[:min_len]
        all_current = all_current[:min_len]
        
        if min_len == 0:
            print("\n[ERROR] No data returned!")
            return
        
        # Calculate resistance
        resistances: List[float] = []
        for v, i in zip(all_voltage, all_current):
            if abs(i) < 1e-12:
                resistances.append(float("inf"))
            else:
                resistances.append(v / i)
        
        # Display results
        print("\n[RESULTS] Full IV Sweep Data:")
        print(f"Total points measured: {min_len}")
        print(f"{'Idx':>4} {'Voltage (V)':>14} {'Current (A)':>14} {'Resistance (Ω)':>16}")
        print("-" * 50)
        
        # Show all points, or first 50 if there are many
        display_limit = min(min_len, 50)
        for idx in range(display_limit):
            v = all_voltage[idx]
            i = all_current[idx]
            r = resistances[idx]
            r_str = f"{r:.2e}" if abs(r) < 1e10 else "inf"
            print(f"{idx:>4} {v:>14.6f} {i:>14.6e} {r_str:>16}")
        
        if min_len > display_limit:
            print(f"... ({min_len - display_limit} more points)")
        
        # Statistics
        import numpy as np
        valid_currents = [i for i in all_current if abs(i) > 1e-12]
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
                ax1.plot(all_voltage, all_current, 'b-o', markersize=4)
                ax1.set_xlabel('Voltage (V)')
                ax1.set_ylabel('Current (A)')
                ax1.set_title('Full IV Characteristic (0V → Vhigh → 0V → Vlow → 0V)')
                ax1.grid(True, alpha=0.3)
                ax1.set_yscale('log')
                
                # Resistance vs Voltage
                valid_r = [r for r in resistances if abs(r) < 1e10]
                valid_v = [v for v, r in zip(all_voltage, resistances) if abs(r) < 1e10]
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

