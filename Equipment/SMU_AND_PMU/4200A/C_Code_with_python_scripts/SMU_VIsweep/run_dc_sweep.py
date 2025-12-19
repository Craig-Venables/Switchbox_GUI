"""DC Sweep runner for Keithley 4200A-SCS using dcSweep module from nvm(KXCI compatible).

This script wraps the `EX` command for dcSweep, which uses hardware sweepv()
function for smooth voltage sweeps. This module uses synchronous measurement
functions and may provide better timing than manual loops.

Note: dcSweep requires:
- Two SMUs (SMU_low and SMU_high)
- NVM library support
- RPM switching capability

Usage:
    python run_dc_sweep.py --vamp 5 --vamp-pts 300 --step-time 0.001
"""

from __future__ import annotations

import argparse
import re
import time
from typing import List, Optional

try:
    import pyvisa
except ImportError:
    print("ERROR: pyvisa is required. Install with: pip install pyvisa")
    exit(1)


def format_param(value: float | int | str) -> str:
    """Format parameter for EX command."""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        if value >= 1.0 and value < 1e6:
            if value == int(value):
                return str(int(value))
            return f"{value:.10g}".rstrip('0').rstrip('.')
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    if isinstance(value, str):
        return f'"{value}"'  # String parameters need quotes
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DC Sweep for Keithley 4200A-SCS using dcSweep module",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--gpib-address", type=str, default="GPIB0::17::INSTR",
                       help="GPIB address (default: GPIB0::17::INSTR)")
    parser.add_argument("--smu-low", type=str, default="SMU1",
                       help="Low side SMU (default: SMU1)")
    parser.add_argument("--smu-high", type=str, default="SMU2",
                       help="High side SMU (default: SMU2)")
    parser.add_argument("--comp-ch", type=int, default=1, choices=[1, 2],
                       help="Compliance channel (1 or 2, default: 1)")
    parser.add_argument("--meas-ch", type=int, default=2, choices=[1, 2],
                       help="Measurement channel (1 or 2, default: 2)")
    parser.add_argument("--irange", type=float, default=0.0,
                       help="Current range (A, 0.0 for AUTO, default: 0.0)")
    parser.add_argument("--ilimit", type=float, default=0.1,
                       help="Current limit (A, default: 0.1)")
    parser.add_argument("--step-time", type=float, default=0.001,
                       help="Time per step (s, default: 0.001)")
    parser.add_argument("--width-time", type=float, default=0.001,
                       help="Hold time at peak voltage (s, default: 0.001)")
    parser.add_argument("--vamp", type=float, default=1.0,
                       help="Peak voltage (V, can be positive or negative, default: 1.0)")
    parser.add_argument("--vamp-pts", type=int, default=300,
                       help="Number of points (10-1000, default: 300)")
    parser.add_argument("--no-plot", action="store_true",
                       help="Skip plotting")
    
    args = parser.parse_args()
    
    # Validate
    if not (10 <= args.vamp_pts <= 1000):
        parser.error("vamp-pts must be in range [10, 1000]")
    if abs(args.vamp) > 10:
        parser.error("vamp must be in range [-10, 10]")
    if abs(args.ilimit) > 0.1:
        parser.error("ilimit must be in range [-0.1, 0.1]")
    
    print(f"\n{'='*60}")
    print("DC Sweep using dcSweep module")
    print(f"{'='*60}")
    print(f"SMU_low: {args.smu_low}")
    print(f"SMU_high: {args.smu_high}")
    print(f"Peak voltage: {args.vamp} V")
    print(f"Points: {args.vamp_pts}")
    print(f"Step time: {args.step_time} s")
    print(f"Width time: {args.width_time} s")
    print(f"Current limit: {args.ilimit} A")
    print(f"{'='*60}\n")
    
    # Connect
    try:
        rm = pyvisa.ResourceManager()
        inst = rm.open_resource(args.gpib_address)
        inst.timeout = 60000  # 60 seconds (dcSweep can take longer)
        inst.write_termination = "\n"
        inst.read_termination = "\n"
        print(f"[OK] Connected to: {inst.query('*IDN?').strip()}")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return
    
    try:
        # Enter UL mode
        inst.write("UL")
        time.sleep(0.03)
        print("[OK] Entered UL mode")
        
        # Build EX command
        # Function signature: dcSweep(SMU_low, SMU_high, compCH, measCH, irange, ilimit, 
        #                             stepTime, widthTime, vamp, vamp_pts, vforce, vforce_pts,
        #                             imeasd, imeasd_pts, timed, timed_pts)
        params = [
            format_param(args.smu_low),      # 1: SMU_low (string)
            format_param(args.smu_high),     # 2: SMU_high (string)
            format_param(args.comp_ch),      # 3: compCH (int)
            format_param(args.meas_ch),      # 4: measCH (int)
            format_param(args.irange),      # 5: irange (double)
            format_param(args.ilimit),       # 6: ilimit (double)
            format_param(args.step_time),    # 7: stepTime (double)
            format_param(args.width_time),   # 8: widthTime (double)
            format_param(args.vamp),         # 9: vamp (double)
            format_param(args.vamp_pts),     # 10: vamp_pts (int)
            "",                              # 11: vforce output array
            format_param(args.vamp_pts),     # 12: vforce_pts (int)
            "",                              # 13: imeasd output array
            format_param(args.vamp_pts),     # 14: imeasd_pts (int)
            "",                              # 15: timed output array
            format_param(args.vamp_pts),     # 16: timed_pts (int)
        ]
        
        command = f"EX Labview_Controlled_Programs_Kemp dcSweep({','.join(params)})"
        
        print(f"[KXCI] Executing dcSweep: 0V → {args.vamp}V → 0V")
        print(f"[KXCI] Command: {command}")
        
        # Execute command
        inst.write(command)
        time.sleep(0.05)
        
        # Wait for completion - dcSweep uses sweepv which is hardware-timed
        # Estimate: stepTime * points + widthTime
        estimated_time = args.step_time * args.vamp_pts + args.width_time + 1.0  # Add 1s safety
        print(f"[KXCI] Waiting {estimated_time:.2f}s for measurement...")
        time.sleep(estimated_time)
        
        # Read return value
        try:
            response = inst.read()
            print(f"[KXCI] Response: {response.strip()}")
            match = re.search(r"RETURN VALUE\s*=\s*(-?\d+)", response, re.IGNORECASE)
            if match:
                return_value = int(match.group(1))
                if return_value < 0:
                    print(f"[ERROR] Return value: {return_value}")
                    error_msgs = {
                        -1: "SMU_high not in current configuration",
                        -2: "SMU_low not in current configuration",
                        -3: "ilimit > 0.1 or array size mismatch",
                    }
                    print(f"  {error_msgs.get(return_value, 'Unknown error')}")
                    return
                print(f"[OK] Return value: {return_value} (success)")
        except Exception as e:
            print(f"[WARNING] Could not read return value: {e}")
        
        # Get data
        time.sleep(0.1)
        print("\n[KXCI] Retrieving data...")
        
        def get_gp(param: int, count: int, name: str) -> List[float]:
            """Get GP parameter."""
            try:
                inst.write(f"GP {param} {count}")
                time.sleep(0.05)
                response = inst.read().strip()
                
                if "=" in response:
                    response = response.split("=", 1)[1].strip()
                
                separator = None
                for sep in (";", ","):
                    if sep in response:
                        separator = sep
                        break
                
                values = []
                if separator:
                    for part in response.split(separator):
                        part = part.strip()
                        if part:
                            try:
                                values.append(float(part))
                            except ValueError:
                                pass
                else:
                    if response:
                        try:
                            values.append(float(response))
                        except ValueError:
                            pass
                
                print(f"  GP {param} ({name}): {len(values)} values")
                return values
            except Exception as e:
                print(f"  GP {param} ({name}): ERROR - {e}")
                return []
        
        # GP parameters based on function signature:
        # 11=vforce, 13=imeasd, 15=timed
        voltage = get_gp(11, args.vamp_pts, "vforce")
        current = get_gp(13, args.vamp_pts, "imeasd")
        timestamps = get_gp(15, args.vamp_pts, "timed")
        
        # Ensure same length
        min_len = min(len(voltage), len(current), len(timestamps))
        voltage = voltage[:min_len]
        current = current[:min_len]
        timestamps = timestamps[:min_len] if timestamps else []
        
        if min_len == 0:
            print("\n[ERROR] No data retrieved!")
            return
        
        print(f"\n[RESULTS] Retrieved {min_len} points")
        print(f"{'Idx':>4} {'Time (s)':>12} {'Voltage (V)':>14} {'Current (A)':>14}")
        print("-" * 45)
        
        for i in range(min(min_len, 20)):
            t = timestamps[i] if timestamps and i < len(timestamps) else 0.0
            print(f"{i:>4} {t:>12.6f} {voltage[i]:>14.6f} {current[i]:>14.6e}")
        
        if min_len > 20:
            print(f"... ({min_len - 20} more points)")
        
        # Plot
        if not args.no_plot:
            try:
                import matplotlib.pyplot as plt
                
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
                
                # IV curve
                ax1.plot(voltage, current, 'b-o', markersize=3)
                ax1.set_xlabel('Voltage (V)')
                ax1.set_ylabel('Current (A)')
                ax1.set_title(f'IV Characteristic (0V → {args.vamp}V → 0V)')
                ax1.grid(True, alpha=0.3)
                ax1.set_yscale('log')
                
                # Voltage vs Time
                if timestamps:
                    ax2.plot(timestamps[:min_len], voltage, 'g-o', markersize=3)
                    ax2.set_xlabel('Time (s)')
                    ax2.set_ylabel('Voltage (V)')
                    ax2.set_title('Voltage vs Time')
                    ax2.grid(True, alpha=0.3)
                
                plt.tight_layout()
                plt.show()
            except ImportError:
                print("\n[INFO] matplotlib not available, skipping plot")
        
    finally:
        try:
            inst.write("DE")
            time.sleep(0.03)
        except:
            pass
        inst.close()
        rm.close()
        print("\n[OK] Disconnected")


if __name__ == "__main__":
    main()

