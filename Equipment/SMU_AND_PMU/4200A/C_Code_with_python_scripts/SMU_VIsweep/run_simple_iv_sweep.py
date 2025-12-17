"""Simple IV Sweep for Keithley 4200A-SCS using SMU_VIsweep.

This is a minimal, straightforward script that performs a simple linear IV sweep
from Vstart to Vstop using SMU_VIsweep. No complex timing, no multiple segments,
just a simple sweep that works.

Usage:
    python run_simple_iv_sweep.py --vstart 0 --vstop 5 --num-points 11
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
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simple IV Sweep for Keithley 4200A-SCS",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--gpib-address", type=str, default="GPIB0::17::INSTR",
                       help="GPIB address (default: GPIB0::17::INSTR)")
    parser.add_argument("--vstart", type=float, default=0.0,
                       help="Starting voltage (V, default: 0.0)")
    parser.add_argument("--vstop", type=float, default=5.0,
                       help="Stopping voltage (V, default: 5.0)")
    parser.add_argument("--num-points", type=int, default=11,
                       help="Number of points (default: 11)")
    parser.add_argument("--no-plot", action="store_true",
                       help="Skip plotting")
    
    args = parser.parse_args()
    
    # Validate
    if args.vstart == args.vstop:
        parser.error("vstart and vstop cannot be equal")
    if args.num_points < 2:
        parser.error("num-points must be >= 2")
    
    print(f"\n{'='*60}")
    print("Simple IV Sweep")
    print(f"{'='*60}")
    print(f"Vstart: {args.vstart} V")
    print(f"Vstop: {args.vstop} V")
    print(f"Points: {args.num_points}")
    print(f"{'='*60}\n")
    
    # Connect
    try:
        rm = pyvisa.ResourceManager()
        inst = rm.open_resource(args.gpib_address)
        inst.timeout = 30000  # 30 seconds
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
        params = [
            format_param(args.vstart),
            format_param(args.vstop),
            "",  # Imeas output array
            format_param(args.num_points),
            "",  # Vforce output array
            format_param(args.num_points),
        ]
        command = f"EX A_Iv_Sweep SMU_VIsweep({','.join(params)})"
        
        print(f"\n[KXCI] Executing: {args.vstart}V → {args.vstop}V ({args.num_points} points)")
        print(f"[KXCI] Command: {command}")
        
        # Execute command
        inst.write(command)
        time.sleep(0.05)  # Short wait for command to process
        
        # Wait for completion - estimate based on points
        # SMU_VIsweep is fast: ~0.01s per point
        wait_time = max(0.1, args.num_points * 0.01 + 0.1)
        print(f"[KXCI] Waiting {wait_time:.2f}s for measurement...")
        time.sleep(wait_time)
        
        # Read return value
        try:
            response = inst.read()
            print(f"[KXCI] Response: {response.strip()}")
            match = re.search(r"RETURN VALUE\s*=\s*(-?\d+)", response, re.IGNORECASE)
            if match:
                return_value = int(match.group(1))
                if return_value < 0:
                    print(f"[ERROR] Return value: {return_value}")
                    if return_value == -1:
                        print("  Vstart == Vstop (sweep range is zero)")
                    elif return_value == -2:
                        print("  Array size mismatch")
                    return
                print(f"[OK] Return value: {return_value} (success)")
        except Exception as e:
            print(f"[WARNING] Could not read return value: {e}")
        
        # Get data
        time.sleep(0.05)
        print("\n[KXCI] Retrieving data...")
        
        # GP 5 = Vforce, GP 3 = Imeas
        def get_gp(param: int, count: int, name: str) -> List[float]:
            """Get GP parameter."""
            try:
                inst.write(f"GP {param} {count}")
                time.sleep(0.02)
                response = inst.read().strip()
                
                # Parse response
                if "=" in response:
                    response = response.split("=", 1)[1].strip()
                
                # Find separator
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
        
        voltage = get_gp(5, args.num_points, "Vforce")
        current = get_gp(3, args.num_points, "Imeas")
        
        # Ensure same length
        min_len = min(len(voltage), len(current))
        voltage = voltage[:min_len]
        current = current[:min_len]
        
        if min_len == 0:
            print("\n[ERROR] No data retrieved!")
            return
        
        print(f"\n[RESULTS] Retrieved {min_len} points")
        print(f"{'Idx':>4} {'Voltage (V)':>14} {'Current (A)':>14}")
        print("-" * 35)
        
        for i in range(min(min_len, 20)):
            print(f"{i:>4} {voltage[i]:>14.6f} {current[i]:>14.6e}")
        
        if min_len > 20:
            print(f"... ({min_len - 20} more points)")
        
        # Plot
        if not args.no_plot:
            try:
                import matplotlib.pyplot as plt
                plt.figure(figsize=(10, 6))
                plt.plot(voltage, current, 'b-o', markersize=4)
                plt.xlabel('Voltage (V)')
                plt.ylabel('Current (A)')
                plt.title(f'IV Characteristic ({args.vstart}V → {args.vstop}V)')
                plt.grid(True, alpha=0.3)
                plt.yscale('log')
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

