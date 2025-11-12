"""Readtrain Dual Channel runner (KXCI compatible).

This script wraps the `EX A_Read_Train readtrain_dual_channel(...)` command,
executes it on a Keithley 4200A via KXCI, and retrieves the resistance, voltage,
and current data from multiple measurement pulses.

The module performs a sequence of measurement pulses to monitor resistance
over time (readtrain). It uses dual-channel PMU configuration with ForceCh=1
and MeasureCh=2.

Usage examples:

    # Basic readtrain with 8 measurement pulses
    python run_readtrain_dual_channel.py --numb-meas-pulses 8

    # Custom timing and voltage parameters
    python run_readtrain_dual_channel.py --meas-v 0.5 --meas-width 2e-6 --numb-meas-pulses 10

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

    def _execute_ex_command(self, command: str) -> tuple[Optional[int], Optional[str]]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")

        try:
            self.inst.write(command)
            time.sleep(0.03)
            time.sleep(2.0)
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
        self.inst.write(command)
        time.sleep(0.03)
        raw = self._safe_read()
        return self._parse_gp_response(raw)

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
    # Timing parameters (1-10)
    rise_time: float, reset_v: float, reset_width: float, reset_delay: float,
    meas_v: float, meas_width: float, meas_delay: float,
    set_width: float, set_fall_time: float, set_delay: float,
    # Sweep parameters (11-15)
    set_start_v: float, set_stop_v: float, steps: int,
    i_range: float, max_points: int,
    # Output array sizes (16-23)
    set_r_size: int, reset_r_size: int, set_v_size: int, set_i_size: int,
    # Debug parameters (24-30)
    iteration: int, out1_size: int, out1_name: str,
    out2_size: int, out2_name: str,
    # Pulse parameters (31-34)
    pulse_times_size: int, numb_meas_pulses: int, clarius_debug: int
) -> str:
    """Build EX command for readtrain_dual_channel."""
    
    params = [
        # Input parameters (1-15)
        format_param(rise_time),          # 1: riseTime
        format_param(reset_v),            # 2: resetV
        format_param(reset_width),        # 3: resetWidth
        format_param(reset_delay),        # 4: resetDelay
        format_param(meas_v),             # 5: measV
        format_param(meas_width),         # 6: measWidth
        format_param(meas_delay),         # 7: measDelay
        format_param(set_width),          # 8: setWidth
        format_param(set_fall_time),      # 9: setFallTime
        format_param(set_delay),          # 10: setDelay
        format_param(set_start_v),        # 11: setStartV
        format_param(set_stop_v),         # 12: setStopV
        format_param(steps),              # 13: steps
        format_param(i_range),            # 14: IRange
        format_param(max_points),         # 15: max_points
        # Output arrays (16-23) - empty strings for arrays, sizes follow
        "",                               # 16: setR (output array)
        format_param(set_r_size),         # 17: setR_size
        "",                               # 18: resetR (output array)
        format_param(reset_r_size),       # 19: resetR_size
        "",                               # 20: setV (output array)
        format_param(set_v_size),         # 21: setV_size
        "",                               # 22: setI (output array)
        format_param(set_i_size),         # 23: setI_size
        # Debug parameters (24-30)
        format_param(iteration),          # 24: iteration
        "",                               # 25: out1 (output array)
        format_param(out1_size),          # 26: out1_size
        out1_name,                        # 27: out1_name
        "",                               # 28: out2 (output array)
        format_param(out2_size),          # 29: out2_size
        out2_name,                        # 30: out2_name
        # Pulse parameters (31-34)
        "",                               # 31: PulseTimes (output array)
        format_param(pulse_times_size),   # 32: PulseTimesSize
        format_param(numb_meas_pulses),   # 33: NumbMeasPulses
        format_param(clarius_debug),      # 34: ClariusDebug
    ]

    return f"EX A_Read_Train readtrain_dual_channel({','.join(params)})"


def run_measurement(args, enable_plot: bool) -> None:
    """Run the measurement and retrieve data."""
    
    # Auto-calculate array sizes if needed
    set_r_size = args.set_r_size if args.set_r_size > 0 else args.numb_meas_pulses + 2
    reset_r_size = args.reset_r_size if args.reset_r_size > 0 else args.numb_meas_pulses + 2
    set_v_size = args.set_v_size if args.set_v_size > 0 else args.numb_meas_pulses + 2
    set_i_size = args.set_i_size if args.set_i_size > 0 else args.numb_meas_pulses + 2
    pulse_times_size = args.pulse_times_size if args.pulse_times_size > 0 else args.numb_meas_pulses + 2
    
    print(f"[Auto] Array sizes: setR={set_r_size}, resetR={reset_r_size}, setV={set_v_size}, setI={set_i_size}, PulseTimes={pulse_times_size}")
    
    command = build_ex_command(
        args.rise_time, args.reset_v, args.reset_width, args.reset_delay,
        args.meas_v, args.meas_width, args.meas_delay,
        args.set_width, args.set_fall_time, args.set_delay,
        args.set_start_v, args.set_stop_v, args.steps,
        args.i_range, args.max_points,
        set_r_size, reset_r_size, set_v_size, set_i_size,
        args.iteration, args.out1_size, args.out1_name,
        args.out2_size, args.out2_name,
        pulse_times_size, args.numb_meas_pulses, args.clarius_debug
    )
    
    print("\n" + "="*80)
    print("[DEBUG] Generated EX command:")
    print("="*80)
    print(command)
    print("="*80)
    
    controller = KXCIClient(gpib_address=args.gpib_address, timeout=args.timeout)

    try:
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")

        print("\n[KXCI] Sending command to instrument...")
        print(f"[KXCI] Measurement pulses: {args.numb_meas_pulses}")
        print(f"[KXCI] Measurement voltage: {args.meas_v}V, width: {args.meas_width*1e6:.2f}µs")

        if not controller._enter_ul_mode():
            raise RuntimeError("Failed to enter UL mode")

        return_value, error = controller._execute_ex_command(command)
        
        if error:
            raise RuntimeError(error)
        if return_value is not None:
            print(f"Return value: {return_value}")
            if return_value < 0:
                print(f"[WARN] Negative return value indicates an error (code: {return_value})")
            elif return_value == 0:
                print(f"[OK] Return value is 0 (success)")

        print("\n[KXCI] Retrieving data...")
        time.sleep(0.2)

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

        # Parameter positions: 20=setV, 22=setI, 31=PulseTimes
        # Note: setR (16) and resetR (18) are legacy outputs from old code with programming pulses
        # For readtrain (all reads), the actual data is in setV and setI
        expected_points = args.numb_meas_pulses + 2  # Baseline + second read + measurement pulses
        print(f"[KXCI] Requesting {expected_points} points per array")
        
        set_v = safe_query(20, set_v_size, "setV")
        set_i = safe_query(22, set_i_size, "setI")
        pulse_times = safe_query(31, pulse_times_size, "PulseTimes")
        
        print(f"[KXCI] Received: {len(set_v)} setV, {len(set_i)} setI, {len(pulse_times)} PulseTimes")

        # Use all received data - the C code should populate arrays correctly
        # Expected number of points: NumbMeasPulses + 2 (baseline + second read + measurement pulses)
        expected_points = args.numb_meas_pulses + 2
        usable = min(len(set_v), len(set_i), len(pulse_times), expected_points)
        
        # Trim to usable length (use all data we received, up to expected points)
        set_v = set_v[:usable]
        set_i = set_i[:usable]
        pulse_times = pulse_times[:usable]
        
        # Debug: print first few values to see what we got
        print(f"\n[DEBUG] Expected points: {expected_points}, Using: {usable}")
        if usable > 0:
            print(f"[DEBUG] First 5 PulseTimes: {pulse_times[:min(5, usable)]}")
            print(f"[DEBUG] First 5 setV: {set_v[:min(5, usable)]}")
            print(f"[DEBUG] First 5 setI: {set_i[:min(5, usable)]}")
        print(f"\n[KXCI] Collected {usable} valid samples")

        if usable == 0:
            print("\n[ERROR] No data returned!")
            return

        # Calculate resistance from voltage and current
        resistance = []
        for v, i in zip(set_v, set_i):
            if abs(i) > 1e-12:
                r = v / i
                resistance.append(r)
            else:
                resistance.append(float('inf') if v > 0 else float('-inf'))

        # Display data
        try:
            import pandas as pd
            import numpy as np

            df = pd.DataFrame({
                "pulse": range(usable),
                "time_s": pulse_times,
                "voltage_V": set_v,
                "current_A": set_i,
                "resistance_kOhm": [r/1000.0 if abs(r) < 1e10 else np.nan for r in resistance],
            })
            
            print("\nReadtrain Data:")
            print(df.to_string(index=False))
            
            # Print statistics
            valid_resistance = [r for r in resistance if abs(r) < 1e10 and abs(r) > 0]
            if valid_resistance:
                print(f"\nResistance Statistics:")
                print(f"  Mean: {np.mean(valid_resistance)/1e3:.2f} kOhm")
                print(f"  Std Dev: {np.std(valid_resistance)/1e3:.2f} kOhm")
                print(f"  Min: {np.min(valid_resistance)/1e3:.2f} kOhm")
                print(f"  Max: {np.max(valid_resistance)/1e3:.2f} kOhm")

            if enable_plot:
                try:
                    import matplotlib.pyplot as plt

                    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))
                    
                    # Voltage vs time
                    ax1.plot(pulse_times, set_v, 'o-', label="Voltage", color="tab:blue", markersize=4)
                    ax1.set_ylabel("Voltage (V)", color="tab:blue")
                    ax1.tick_params(axis="y", labelcolor="tab:blue")
                    ax1.grid(True, alpha=0.3)
                    ax1.set_title("Voltage vs Time")
                    ax1.set_xlabel("Time (s)")

                    # Current vs time
                    ax2.plot(pulse_times, set_i, 'o-', label="Current", color="tab:red", markersize=4)
                    ax2.set_ylabel("Current (A)", color="tab:red")
                    ax2.tick_params(axis="y", labelcolor="tab:red")
                    ax2.grid(True, alpha=0.3)
                    ax2.set_title("Current vs Time")
                    ax2.set_xlabel("Time (s)")

                    # Resistance vs time
                    valid_res_ohm = [r/1e3 if abs(r) < 1e10 else np.nan for r in resistance]
                    ax3.plot(pulse_times, valid_res_ohm, 'o-', label="Resistance", color="tab:green", markersize=4)
                    ax3.set_ylabel("Resistance (kOhm)", color="tab:green")
                    ax3.tick_params(axis="y", labelcolor="tab:green")
                    ax3.grid(True, alpha=0.3)
                    ax3.set_title("Resistance vs Time")
                    ax3.set_xlabel("Time (s)")

                    # Resistance vs pulse number (linear scale for easier viewing)
                    pulse_numbers = range(usable)
                    ax4.plot(pulse_numbers, valid_res_ohm, 'o-', label="Resistance", color="tab:green", markersize=4)
                    ax4.set_ylabel("Resistance (kOhm)", color="tab:green")
                    ax4.tick_params(axis="y", labelcolor="tab:green")
                    ax4.grid(True, alpha=0.3)
                    ax4.set_title("Resistance vs Pulse Number")
                    ax4.set_xlabel("Pulse Number")
                    ax4.set_xticks(pulse_numbers)

                    plt.tight_layout()
                    plt.show()
                except Exception as exc:
                    print(f"\n[WARN] Unable to display plot: {exc}")
        except ImportError:
            print("\nPandas not available; showing first 15 samples:")
            for idx in range(min(15, usable)):
                r_str = f"{resistance[idx]/1e3:.2f}" if abs(resistance[idx]) < 1e10 else "inf"
                print(f"{idx:04d}  t={pulse_times[idx]:.6e} s  V={set_v[idx]:.6f} V  I={set_i[idx]:.6e} A  R={r_str} kOhm")

    finally:
        try:
            controller._exit_ul_mode()
        except Exception:
            pass
        controller.disconnect()


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Readtrain Dual Channel - Multiple measurement pulses to monitor resistance over time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic readtrain with 8 measurement pulses
  python run_readtrain_dual_channel.py --numb-meas-pulses 8

  # Custom timing and voltage parameters
  python run_readtrain_dual_channel.py --meas-v 0.5 --meas-width 2e-6 --numb-meas-pulses 10
        """
    )

    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR", help="VISA resource string")
    parser.add_argument("--timeout", type=float, default=30.0, help="Visa timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only print the EX command")
    parser.add_argument("--no-plot", action="store_true", help="Disable plotting")

    # Timing parameters
    parser.add_argument("--rise-time", type=float, default=3e-8, help="Rise/fall time (s). Default 30ns")
    parser.add_argument("--reset-v", type=float, default=4.0, help="Reset voltage (V). Default 4V")
    parser.add_argument("--reset-width", type=float, default=1e-6, help="Reset pulse width (s). Default 1µs")
    parser.add_argument("--reset-delay", type=float, default=1e-6, help="Reset delay (s). Default 1µs")
    parser.add_argument("--meas-v", type=float, default=1.5, help="Measurement voltage (V). Default 0.5V")
    parser.add_argument("--meas-width", type=float, default=2e-6, help="Measurement pulse width (s). Default 2µs")
    parser.add_argument("--meas-delay", type=float, default=1e-6, help="Measurement delay (s). Default 1µs")
    parser.add_argument("--set-width", type=float, default=1e-6, help="Set pulse width (s). Default 1µs")
    parser.add_argument("--set-fall-time", type=float, default=3e-8, help="Set fall time (s). Default 30ns")
    parser.add_argument("--set-delay", type=float, default=1e-6, help="Set delay (s). Default 1µs")

    # Sweep parameters
    parser.add_argument("--set-start-v", type=float, default=0.0, help="Set start voltage (V). Default 0V")
    parser.add_argument("--set-stop-v", type=float, default=4.0, help="Set stop voltage (V). Default 4V")
    parser.add_argument("--steps", type=int, default=1, help="Number of sweep steps. Default 1")
    parser.add_argument("--i-range", type=float, default=0.01, help="Current range (A). Default 10mA")
    parser.add_argument("--max-points", type=int, default=10000, help="Maximum points. Default 10000")

    # Output array sizes
    parser.add_argument("--set-r-size", type=int, default=0, help="setR array size (0=auto)")
    parser.add_argument("--reset-r-size", type=int, default=0, help="resetR array size (0=auto)")
    parser.add_argument("--set-v-size", type=int, default=0, help="setV array size (0=auto)")
    parser.add_argument("--set-i-size", type=int, default=0, help="setI array size (0=auto)")

    # Debug parameters
    parser.add_argument("--iteration", type=int, default=1, help="Iteration for debug output. Default 1")
    parser.add_argument("--out1-size", type=int, default=200, help="out1 array size. Default 200")
    parser.add_argument("--out1-name", type=str, default="VF", choices=["VF", "VM", "IF", "IM", "T"],
                       help="out1 debug parameter. Default VF")
    parser.add_argument("--out2-size", type=int, default=200, help="out2 array size. Default 200")
    parser.add_argument("--out2-name", type=str, default="T", choices=["VF", "VM", "IF", "IM", "T"],
                       help="out2 debug parameter. Default T")

    # Pulse parameters
    parser.add_argument("--pulse-times-size", type=int, default=0, help="PulseTimes array size (0=auto)")
    parser.add_argument("--numb-meas-pulses", type=int, default=8, help="Number of measurement pulses. Default 8")
    parser.add_argument("--clarius-debug", type=int, default=1, choices=[0, 1], help="Enable debug output. Default 1")

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    print("\n" + "="*80)
    print("Readtrain Dual Channel Runner - Starting")
    print("="*80)
    
    args = parse_arguments()
    
    print(f"[DEBUG] Parsed arguments:")
    print(f"  numb_meas_pulses: {args.numb_meas_pulses}")
    print(f"  meas_v: {args.meas_v}V")
    print(f"  meas_width: {args.meas_width*1e6:.2f}µs")

    command = build_ex_command(
        args.rise_time, args.reset_v, args.reset_width, args.reset_delay,
        args.meas_v, args.meas_width, args.meas_delay,
        args.set_width, args.set_fall_time, args.set_delay,
        args.set_start_v, args.set_stop_v, args.steps,
        args.i_range, args.max_points,
        args.set_r_size, args.reset_r_size, args.set_v_size, args.set_i_size,
        args.iteration, args.out1_size, args.out1_name,
        args.out2_size, args.out2_name,
        args.pulse_times_size, args.numb_meas_pulses, args.clarius_debug
    )

    print("Generated EX command:\n" + command)

    if args.dry_run:
        return

    run_measurement(args, enable_plot=not args.no_plot)


if __name__ == "__main__":
    main()

