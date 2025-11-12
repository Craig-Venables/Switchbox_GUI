"""ACraig12 DC Sweep runner (KXCI compatible).

This script wraps the `EX ACraig12 ACraig12_DC_Sweep(...)` command,
executes it on a Keithley 4200A via KXCI, and retrieves the voltage/current
data from a DC sweep using SMUs.

This module performs a DC voltage sweep from 0V to a peak voltage and back,
measuring current and voltage at each point. The SMUs are connected to the
DUT through RPMs.

Usage examples:

    # Basic sweep: 0V -> 1V -> 0V, 300 points
    python run_acraig12_dc_sweep.py --vamp 1.0 --vamp-pts 300

    # Sweep with custom timing
    python run_acraig12_dc_sweep.py --vamp 5.0 --step-time 0.01 --width-time 0.1

    # With current limit and range
    python run_acraig12_dc_sweep.py --vamp 3.0 --ilimit 0.01 --irange 1e-3

Pass `--dry-run` to print the generated EX command without contacting the instrument.
"""

from __future__ import annotations

import argparse
import time
from typing import List, Optional

try:
    import matplotlib.pyplot as plt
    import numpy as np
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False


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

    def _execute_ex_command(self, command: str) -> tuple[Optional[int], Optional[str]]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")

        try:
            self.inst.write(command)
            time.sleep(0.03)
            response = self.inst.read().strip()
            try:
                return_value = int(response)
                return return_value, None
            except ValueError:
                return None, response
        except Exception as exc:
            return None, str(exc)

    def execute_ex(self, command: str) -> tuple[Optional[int], Optional[str]]:
        """Execute an EX command and return the result."""
        if not self._ul_mode_active:
            if not self._enter_ul_mode():
                return None, "Failed to enter UL mode"
        return self._execute_ex_command(command)

    def safe_query(self, gp_param: int, num_points: int, name: str) -> List[float]:
        """Safely query GP parameter and parse array values."""
        if not self._ul_mode_active:
            if not self._enter_ul_mode():
                return []

        try:
            query = f"GP {gp_param}"
            response = self.inst.query(query).strip()
            
            # Parse comma-separated values
            values = []
            separator = ","
            
            for part in response.split(separator):
                part = part.strip()
                if not part:
                    continue
                try:
                    values.append(float(part))
                except ValueError:
                    pass
            return values
        except Exception as exc:
            print(f"[WARN] Failed to query GP {gp_param} ({name}): {exc}")
            return []


def format_param(value: float | int | str) -> str:
    """Format parameter for EX command."""
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        if value >= 1.0 and value < 1e6:
            if value == int(value):
                return str(int(value))
            return f"{value:.10g}".rstrip('0').rstrip('.')
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


def build_ex_command(
    smu_low: str, smu_high: str, comp_ch: int, meas_ch: int,
    irange: float, ilimit: float, step_time: float, width_time: float,
    vamp: float, vamp_pts: int, array_size: int, debug: int = 1
) -> str:
    """Build EX command for ACraig12_DC_Sweep."""
    
    params = [
        smu_low,                        # 1: SMU_low
        smu_high,                       # 2: SMU_high
        format_param(comp_ch),          # 3: compCH
        format_param(meas_ch),          # 4: measCH
        format_param(irange),          # 5: irange
        format_param(ilimit),          # 6: ilimit
        format_param(step_time),       # 7: stepTime
        format_param(width_time),      # 8: widthTime
        format_param(vamp),            # 9: vamp
        format_param(vamp_pts),        # 10: vamp_pts
        "",                             # 11: vforce output array
        format_param(array_size),      # 12: vforce_pts
        "",                             # 13: imeasd output array
        format_param(array_size),      # 14: imeasd_pts
        "",                             # 15: timed output array
        format_param(array_size),      # 16: timed_pts
        format_param(debug),           # 17: ClariusDebug
    ]
    
    return f"EX ACraig12 ACraig12_DC_Sweep({','.join(params)})"


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="ACraig12 DC Sweep runner (KXCI compatible)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # SMU configuration
    parser.add_argument("--smu-low", type=str, default="SMU1",
                       help="SMU identifier for low side (default: SMU1)")
    parser.add_argument("--smu-high", type=str, default="SMU2",
                       help="SMU identifier for high side (default: SMU2)")
    parser.add_argument("--comp-ch", type=int, default=1, choices=[1, 2],
                       help="Channel to apply compliance (default: 1)")
    parser.add_argument("--meas-ch", type=int, default=2, choices=[1, 2],
                       help="Channel to measure current (default: 2)")
    
    # Current settings
    parser.add_argument("--irange", type=float, default=0.0,
                       help="Current range (0.0 for AUTO, default: 0.0)")
    parser.add_argument("--ilimit", type=float, default=0.0,
                       help="Current limit in A (default: 0.0)")
    
    # Timing
    parser.add_argument("--step-time", type=float, default=0.0,
                       help="Time for each sweep step in s (default: 0.0)")
    parser.add_argument("--width-time", type=float, default=0.001,
                       help="Time to hold voltage at peak in s (default: 0.001)")
    
    # Sweep parameters
    parser.add_argument("--vamp", type=float, default=1.0,
                       help="Peak voltage in V (default: 1.0)")
    parser.add_argument("--vamp-pts", type=int, default=300,
                       help="Number of points in sweep (default: 300)")
    
    # Array size
    parser.add_argument("--array-size", type=int, default=None,
                       help="Output array size (default: same as vamp-pts)")
    
    # Connection
    parser.add_argument("--gpib-address", type=str, default="GPIB0::22::INSTR",
                       help="GPIB address (default: GPIB0::22::INSTR)")
    parser.add_argument("--timeout", type=float, default=60.0,
                       help="Timeout in seconds (default: 60.0)")
    
    # Options
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug output")
    parser.add_argument("--dry-run", action="store_true",
                       help="Print EX command without executing")
    parser.add_argument("--no-plot", action="store_true",
                       help="Disable plotting")
    
    return parser.parse_args()


def run_measurement(args, enable_plot: bool) -> None:
    """Run the measurement and retrieve data."""
    
    # Set array size to match vamp_pts if not specified
    array_size = args.array_size if args.array_size is not None else args.vamp_pts
    
    command = build_ex_command(
        smu_low=args.smu_low,
        smu_high=args.smu_high,
        comp_ch=args.comp_ch,
        meas_ch=args.meas_ch,
        irange=args.irange,
        ilimit=args.ilimit,
        step_time=args.step_time,
        width_time=args.width_time,
        vamp=args.vamp,
        vamp_pts=args.vamp_pts,
        array_size=array_size,
        debug=1 if args.debug else 0
    )
    
    if args.dry_run:
        print("="*80)
        print("[DEBUG] Generated EX command:")
        print("="*80)
        print(command)
        print("="*80)
        return
    
    print("="*80)
    print("ACraig12 DC Sweep Runner - Starting")
    print("="*80)
    print(f"[Auto] array_size set to {array_size}")
    
    print("="*80)
    print("[DEBUG] Generated EX command:")
    print("="*80)
    print(command)
    print("="*80)
    
    controller = KXCIClient(gpib_address=args.gpib_address, timeout=args.timeout)
    
    try:
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        print("\n[KXCI] Sending command to instrument...")
        print(f"[KXCI] Sweep: 0V -> {args.vamp}V -> 0V ({args.vamp_pts} points)")
        print(f"[KXCI] Step time: {args.step_time}s, Width time: {args.width_time}s")
        print(f"[KXCI] Current limit: {args.ilimit}A, Range: {'AUTO' if args.irange == 0 else f'{args.irange}A'}")
        
        return_value, error_msg = controller.execute_ex(command)
        
        if error_msg:
            print(f"\n[ERROR] Command failed: {error_msg}")
            return
        
        print(f"Return value: {return_value}")
        
        if return_value != 0:
            print(f"[ERROR] Return value is {return_value} (expected 0)")
            return
        
        print("[OK] Return value is 0 (success)")
        
        print("\n[KXCI] Retrieving data...")
        num_points = array_size
        print(f"[KXCI] Requesting {num_points} points")
        
        voltage = controller.safe_query(11, num_points, "voltage")
        current = controller.safe_query(13, num_points, "current")
        time_axis = controller.safe_query(15, num_points, "time")
        
        print(f"[KXCI] Received: {len(voltage)} voltage, {len(current)} current, {len(time_axis)} time samples")
        
        usable = min(len(voltage), len(current), len(time_axis))
        voltage = voltage[:usable]
        current = current[:usable]
        time_axis = time_axis[:usable]
        
        # Trim trailing zeros
        last_valid = usable
        for idx in range(usable - 1, -1, -1):
            if (abs(time_axis[idx]) > 1e-12 or 
                abs(voltage[idx]) > 1e-12 or 
                abs(current[idx]) > 1e-12):
                last_valid = idx + 1
                break
        
        voltage = voltage[:last_valid]
        current = current[:last_valid]
        time_axis = time_axis[:last_valid]
        
        print(f"\n[KXCI] Collected {last_valid} valid samples")
        
        if not voltage or last_valid == 0:
            print("\n[ERROR] No data returned!")
            return
        
        # Print summary statistics
        print(f"\n[Summary]")
        print(f"  Voltage range: {min(voltage):.6g} V to {max(voltage):.6g} V")
        print(f"  Current range: {min(current):.6g} A to {max(current):.6g} A")
        print(f"  Time range: {min(time_axis):.6g} s to {max(time_axis):.6g} s")
        
        # Plot if requested
        if enable_plot and PLOTTING_AVAILABLE:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            
            ax1.plot(time_axis, voltage, 'b-', linewidth=1.5)
            ax1.set_xlabel('Time (s)')
            ax1.set_ylabel('Voltage (V)')
            ax1.set_title('DC Sweep: Voltage vs Time')
            ax1.grid(True)
            
            ax2.plot(time_axis, current, 'r-', linewidth=1.5)
            ax2.set_xlabel('Time (s)')
            ax2.set_ylabel('Current (A)')
            ax2.set_title('DC Sweep: Current vs Time')
            ax2.grid(True)
            
            plt.tight_layout()
            plt.show()
            
            # Also plot IV curve
            fig2, ax3 = plt.subplots(1, 1, figsize=(8, 6))
            ax3.plot(voltage, current, 'g-', linewidth=1.5)
            ax3.set_xlabel('Voltage (V)')
            ax3.set_ylabel('Current (A)')
            ax3.set_title('DC Sweep: IV Curve')
            ax3.grid(True)
            plt.tight_layout()
            plt.show()
        elif enable_plot and not PLOTTING_AVAILABLE:
            print("\n[WARN] Plotting requested but matplotlib not available")
        
    finally:
        controller.disconnect()


def main() -> None:
    """Main entry point."""
    args = parse_arguments()
    enable_plot = not args.no_plot and PLOTTING_AVAILABLE
    run_measurement(args, enable_plot)


if __name__ == "__main__":
    main()

