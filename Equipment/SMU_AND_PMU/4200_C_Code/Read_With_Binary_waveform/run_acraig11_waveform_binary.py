"""ACraig11 PMU Waveform with Binary Pattern runner (KXCI compatible).

This script wraps the `EX ACraig11 ACraig11_PMU_Waveform_Binary(...)` command,
executes it on a Keithley 4200A via KXCI, and retrieves the voltage/current
waveform data.

CH1: Continuous waveform reads at specified period (simple pulse commands)
CH2: Binary pulse train using seg_arb (sequence of 1s and 0s)

KEY FEATURE:
- CH2 generates binary pulse trains from a pattern array (e.g., "10110100")
- Each bit in the pattern becomes one segment in the seg_arb waveform
- Pattern can be repeated multiple times via loop count

MEASUREMENT WINDOW (40-80% of Pulse Width):
===========================================
When --acq-type=1 (average mode, default), the C module extracts one averaged
measurement per pulse from a specific time window: 40-80% of the pulse width.

Why 40-80%?
- Avoids transition regions: The first 40% excludes the rise time transition
  and any settling/ringing at the start of the pulse
- Avoids fall transition: The last 20% (80-100%) excludes the fall time transition
  and any pre-fall settling effects
- Stable region: The 40-80% window captures the most stable, flat portion of
  the pulse where voltage and current have fully settled

Example with 1µs pulse width:
- Pulse starts at t=0 (after delay + rise)
- Measurement window: 0.4µs to 0.8µs (40-80% of 1µs)
- All samples within this window are averaged to produce one value per pulse
- This gives accurate resistance measurements by avoiding transient effects

The measurement window is hardcoded in the C code and cannot be changed via
command-line parameters. To modify it, edit the C source file:
  measurementStartFrac = 0.4  (40% of pulse width)
  measurementEndFrac = 0.8    (80% of pulse width)

Usage examples:

    # CH1 reads at 1µs, CH2 sends pattern "10110100" (8 bits, 1µs each)
    python run_acraig11_waveform_binary.py --burst-count 50 --period 1e-6 --ch2-pattern "10110100" --ch2-width 1e-6 --ch2-spacing 500e-9

    # CH1 reads at 2µs, CH2 sends pattern "1100" repeated 10 times
    python run_acraig11_waveform_binary.py --burst-count 100 --period 2e-6 --ch2-pattern "1100" --ch2-width 500e-9 --ch2-spacing 500e-9 --ch2-loop-count 10

Pass `--dry-run` to print the generated EX command without contacting the instrument.
"""

from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass
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
        # For values >= 1.0, use standard notation if reasonable, otherwise scientific
        if value >= 1.0 and value < 1e6:
            # Use standard notation for reasonable values (e.g., 1.0, 10.5, 100.0)
            if value == int(value):
                return str(int(value))
            return f"{value:.10g}".rstrip('0').rstrip('.')
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


# format_array_param removed - arrays are expanded directly into params list


def build_ex_command(
    # CH1 parameters
    width: float, rise: float, fall: float, delay: float, period: float,
    volts_source_rng: float, current_measure_rng: float, dut_res: float,
    start_v: float, stop_v: float, step_v: float, base_v: float,
    acq_type: int, lle_comp: int, pre_data_pct: float, post_data_pct: float,
    pulse_avg_cnt: int, burst_count: int, sample_rate: float, pmu_mode: int,
    chan: int, pmu_id: str, array_size: int,
    # CH2 parameters (binary pattern)
    ch2_enable: int, ch2_vrange: float,
    ch2_pattern: List[int], ch2_pattern_size: int,
    ch2_delay: float, ch2_width: float, ch2_rise: float, ch2_fall: float, ch2_spacing: float, ch2_vlow: float, ch2_vhigh: float, ch2_loop_count: float,
    clarius_debug: int = 1
) -> str:
    """Build EX command for ACraig11_PMU_Waveform_Binary."""
    
    params = [
        # CH1 parameters (1-21)
        format_param(width),                    # 1
        format_param(rise),                     # 2
        format_param(fall),                     # 3
        format_param(delay),                    # 4
        format_param(period),                   # 5
        format_param(volts_source_rng),         # 6
        format_param(current_measure_rng),      # 7
        format_param(dut_res),                  # 8
        format_param(start_v),                  # 9
        format_param(stop_v),                   # 10
        format_param(step_v),                   # 11
        format_param(base_v),                   # 12
        format_param(acq_type),                 # 13
        format_param(lle_comp),                 # 14
        format_param(pre_data_pct),             # 15
        format_param(post_data_pct),            # 16
        format_param(pulse_avg_cnt),            # 17
        format_param(burst_count),              # 18
        format_param(sample_rate),              # 19
        format_param(pmu_mode),                 # 20
        format_param(chan),                    # 21
        pmu_id,                                 # 22: PMU_ID
        "",                                     # 23: V_Meas output array
        format_param(array_size),               # 24: size_V_Meas
        "",                                     # 25: I_Meas output array
        format_param(array_size),               # 26: size_I_Meas
        "",                                     # 27: T_Stamp output array
        format_param(array_size),               # 28: size_T_Stamp
        # CH2 parameters (29-37) - ORDER MATCHES METADATA
        # Note: Ch2PatternSize comes BEFORE Ch2Pattern so KXCI knows how many array values to read
        format_param(ch2_enable),               # 29: Ch2Enable
        format_param(ch2_vrange),               # 30: Ch2VRange
        format_param(ch2_pattern_size),         # 31: Ch2PatternSize (size comes first!)
        # Ch2Pattern: pass as single string without commas (e.g., "10110100")
        # C code will parse the string character by character
        ''.join(str(bit) for bit in ch2_pattern),  # 32: Ch2Pattern (single string parameter)
        format_param(ch2_delay),                 # 33: Ch2Delay
        format_param(ch2_width),                 # 34: Ch2Width
        format_param(ch2_rise),                  # 35: Ch2Rise
        format_param(ch2_fall),                  # 36: Ch2Fall
        format_param(ch2_spacing),               # 37: Ch2Spacing
        format_param(ch2_vlow),                 # 38: Ch2Vlow
        format_param(ch2_vhigh),                 # 39: Ch2Vhigh
        format_param(ch2_loop_count),           # 40: Ch2LoopCount
        format_param(clarius_debug),            # 41: ClariusDebug
    ]
    
    # Total: 41 parameters (arrays passed as single string, no expansion)
    # 1-21: CH1 (21), 22: PMU_ID (1), 23-28: Output arrays + sizes (6), 29-41: CH2 (13) = 41

    return f"EX A_Ch1Read_Ch2Binary_out ACraig11_PMU_Waveform_Binary({','.join(params)})"


def parse_pattern(pattern_str: str) -> List[int]:
    """Parse pattern string into list of integers (0s and 1s).
    
    Accepts:
    - String of digits: "10110100"
    - Comma-separated: "1,0,1,1,0,1,0,0"
    - Space-separated: "1 0 1 1 0 1 0 0"
    """
    # Remove whitespace
    pattern_str = pattern_str.strip()
    
    # Try comma-separated first
    if "," in pattern_str:
        parts = pattern_str.split(",")
    # Try space-separated
    elif " " in pattern_str:
        parts = pattern_str.split()
    # Otherwise, treat as continuous string of digits
    else:
        parts = list(pattern_str)
    
    pattern = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            bit = int(part)
            if bit not in (0, 1):
                raise ValueError(f"Pattern bit must be 0 or 1, got {bit}")
            pattern.append(bit)
        except ValueError as e:
            raise ValueError(f"Invalid pattern bit '{part}': {e}")
    
    if not pattern:
        raise ValueError("Pattern cannot be empty")
    
    return pattern


def run_measurement(args, enable_plot: bool) -> None:
    """Run the measurement and retrieve data."""
    
    # Parse pattern
    try:
        ch2_pattern = parse_pattern(args.ch2_pattern)
        ch2_pattern_size = len(ch2_pattern)
    except ValueError as e:
        print(f"[ERROR] Invalid pattern: {e}")
        return
    
    # Auto-calculate array_size if needed
    array_size = args.array_size
    if array_size == 0:
        if args.acq_type == 1:
            array_size = args.burst_count
        else:
            array_size = min(int(args.period * args.sample_rate * args.burst_count) + 100, 10000)
        print(f"[Auto] array_size set to {array_size}")
    
    # Validate CH2 loop count
    ch2_loop_count = args.ch2_loop_count
    try:
        ch2_loop_count = float(ch2_loop_count)
        if ch2_loop_count <= 0 or ch2_loop_count < 1.0:
            print(f"[Auto] CH2 loop count ({ch2_loop_count}) invalid, setting to 1.0")
            ch2_loop_count = 1.0
        if ch2_loop_count > 100000.0:
            print(f"[WARN] CH2 loop count ({ch2_loop_count}) is very large, capping at 100000.0")
            ch2_loop_count = 100000.0
        if not (ch2_loop_count == ch2_loop_count):  # NaN check
            print(f"[ERROR] CH2 loop count is NaN, setting to 1.0")
            ch2_loop_count = 1.0
    except (ValueError, TypeError):
        print(f"[ERROR] CH2 loop count ({args.ch2_loop_count}) is not a valid number, setting to 1.0")
        ch2_loop_count = 1.0
    
    print(f"[DEBUG] CH2 loop count: {ch2_loop_count} (type: {type(ch2_loop_count).__name__})")
    
    # Enable debug by default
    debug_enable = 1
    
    command = build_ex_command(
        args.width, args.rise, args.fall, args.delay, args.period,
        args.volts_source_rng, args.current_measure_rng, args.dut_res,
        args.start_v, args.stop_v, args.step_v, args.base_v,
        args.acq_type, args.lle_comp, args.pre_data_pct, args.post_data_pct,
        args.pulse_avg_cnt, args.burst_count, args.sample_rate, args.pmu_mode,
        args.chan, args.pmu_id, array_size,
        args.ch2_enable, args.ch2_vrange,
        ch2_pattern, ch2_pattern_size,
        args.ch2_delay, args.ch2_width, args.ch2_rise, args.ch2_fall, args.ch2_spacing, args.ch2_vlow, args.ch2_vhigh, ch2_loop_count,
        debug_enable
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
        
        print(f"\n[KXCI] CH1: {args.burst_count} pulses @ {args.period*1e6:.2f}µs period")
        print(f"[KXCI] CH1 pulse: width={args.width*1e6:.2f}µs, rise={args.rise*1e6:.2f}µs, fall={args.fall*1e6:.2f}µs")
        
        if args.ch2_enable:
            pattern_str = "".join(str(b) for b in ch2_pattern)
            print(f"[KXCI] CH2: Binary pattern '{pattern_str}' ({ch2_pattern_size} bits)")
            if args.ch2_delay > 0:
                print(f"[KXCI]        Delay: {args.ch2_delay*1e6:.2f}µs before pattern starts")
            print(f"[KXCI]        Pulse width: {args.ch2_width*1e6:.2f}µs, Rise: {args.ch2_rise*1e6:.2f}µs, Fall: {args.ch2_fall*1e6:.2f}µs, Spacing: {args.ch2_spacing*1e6:.2f}µs")
            print(f"[KXCI]        {args.ch2_vlow:.1f}V (0) / {args.ch2_vhigh:.1f}V (1)")
            print(f"[KXCI]        Loop count: {ch2_loop_count:.1f}")
        
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
        
        voltage = controller.safe_query(23, num_points, "voltage")
        current = controller.safe_query(25, num_points, "current")
        time_axis = controller.safe_query(27, num_points, "time")
        
        print(f"[KXCI] Received: {len(voltage)} voltage, {len(current)} current, {len(time_axis)} time samples")

        usable = min(len(voltage), len(current), len(time_axis))
        voltage = voltage[:usable]
        current = current[:usable]
        time_axis = time_axis[:usable]

        # Trim trailing zeros (but be less aggressive - only remove if ALL are zero)
        last_valid = usable
        for idx in range(usable - 1, -1, -1):
            # Keep if any value is non-zero (more lenient check)
            if (abs(time_axis[idx]) > 1e-15 or 
                abs(voltage[idx]) > 1e-15 or 
                abs(current[idx]) > 1e-15):
                last_valid = idx + 1
                break
        
        voltage = voltage[:last_valid]
        current = current[:last_valid]
        time_axis = time_axis[:last_valid]

        print(f"\n[KXCI] Collected {last_valid} valid samples (after trimming trailing zeros)")
        
        # Show first few values for debugging
        if last_valid > 0:
            print(f"[DEBUG] First sample: V={voltage[0]:.6e} V, I={current[0]:.6e} A, T={time_axis[0]:.6e} s")
            if last_valid > 1:
                print(f"[DEBUG] Last sample: V={voltage[last_valid-1]:.6e} V, I={current[last_valid-1]:.6e} A, T={time_axis[last_valid-1]:.6e} s")

        if len(voltage) == 0 or last_valid == 0:
            print("\n[ERROR] No data returned!")
            print(f"[DEBUG] voltage length: {len(voltage)}, last_valid: {last_valid}")
            if len(voltage) > 0:
                print(f"[DEBUG] First few voltage values: {voltage[:min(5, len(voltage))]}")
            return

        # Calculate resistance
        import numpy as np
        resistance = []
        for v, i in zip(voltage, current):
            if abs(i) > 1e-12:
                r = v / i
                resistance.append(r)
            else:
                resistance.append(float('inf') if v > 0 else float('-inf'))

        # Display data
        try:
            import pandas as pd

            df = pd.DataFrame({
                "sample": range(last_valid),
                "time_s": time_axis,
                "voltage_V": voltage,
                "current_A": current,
                "resistance_kOhm": [r/1000.0 if abs(r) < 1e10 else np.nan for r in resistance],
            })
            
            print("\nWaveform Samples (first 20):")
            print(df[["sample", "time_s", "voltage_V", "current_A", "resistance_kOhm"]].head(20).to_string(index=False))
            
            if last_valid > 20:
                print(f"\n... ({last_valid - 20} more samples)")
            
            # Statistics
            valid_res = [r for r in resistance if abs(r) < 1e10]
            if valid_res:
                print("\nResistance Statistics:")
                print(f"  Mean: {np.mean(valid_res)/1e3:.2f} kOhm")
                print(f"  Std Dev: {np.std(valid_res)/1e3:.2f} kOhm")
                print(f"  Min: {np.min(valid_res)/1e3:.2f} kOhm")
                print(f"  Max: {np.max(valid_res)/1e3:.2f} kOhm")
            
            # Plotting
            if enable_plot:
                try:
                    import matplotlib.pyplot as plt
                    
                    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8))
                    
                    ax1.plot(time_axis, voltage, label="Voltage", color="tab:blue", linewidth=1)
                    ax1.set_xlabel("Time (s)")
                    ax1.set_ylabel("Voltage (V)", color="tab:blue")
                    ax1.tick_params(axis="y", labelcolor="tab:blue")
                    ax1.grid(True, alpha=0.3)
                    
                    ax2.plot(time_axis, current, label="Current", color="tab:red", linewidth=1)
                    ax2.set_xlabel("Time (s)")
                    ax2.set_ylabel("Current (A)", color="tab:red")
                    ax2.tick_params(axis="y", labelcolor="tab:red")
                    ax2.grid(True, alpha=0.3)
                    
                    valid_res_ohm = [r/1e3 if abs(r) < 1e10 else np.nan for r in resistance]
                    ax3.plot(time_axis, valid_res_ohm, label="Resistance", color="tab:green", linewidth=1)
                    ax3.set_xlabel("Time (s)")
                    ax3.set_ylabel("Resistance (kOhm)", color="tab:green")
                    ax3.tick_params(axis="y", labelcolor="tab:green")
                    ax3.grid(True, alpha=0.3)
                    
                    plt.tight_layout()
                    plt.show()
                except Exception as exc:
                    print(f"\n[WARN] Unable to display plot: {exc}")
        except ImportError:
            print("\nPandas not available; showing first 15 samples:")
            for idx in range(min(15, last_valid)):
                r_str = f"{resistance[idx]/1e3:.2f}" if abs(resistance[idx]) < 1e10 else "inf"
                print(f"{idx:04d}  t={time_axis[idx]:.6e} s  V={voltage[idx]:.6f} V  I={current[idx]:.6e} A  R={r_str} kOhm")

    finally:
        try:
            controller._exit_ul_mode()
        except Exception:
            pass
        controller.disconnect()


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="ACraig11 PMU Waveform with Binary Pattern - CH1 continuous reads, CH2 binary pulse train",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CH1 reads at 1µs, CH2 sends pattern "10110100" (8 bits, 1µs each)
  python run_acraig11_waveform_binary.py --burst-count 50 --period 1e-6 --ch2-pattern "10110100" --ch2-width 1e-6 --ch2-spacing 500e-9

  # CH1 reads at 2µs, CH2 sends pattern "1100" repeated 10 times
  python run_acraig11_waveform_binary.py --burst-count 100 --period 2e-6 --ch2-pattern "1100" --ch2-width 500e-9 --ch2-spacing 500e-9 --ch2-loop-count 10
        """
    )

    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR", help="VISA resource string")
    parser.add_argument("--timeout", type=float, default=30.0, help="Visa timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only print the EX command")
    parser.add_argument("--no-plot", action="store_true", help="Disable plotting")

    # CH1 timing parameters
    parser.add_argument("--width", type=float, default=0.5e-6, help="CH1 pulse width (s). Default 0.5µs")
    parser.add_argument("--rise", type=float, default=100e-9, help="CH1 rise time (s). Default 100ns")
    parser.add_argument("--fall", type=float, default=100e-9, help="CH1 fall time (s). Default 100ns")
    parser.add_argument("--delay", type=float, default=0, help="CH1 pre-pulse delay (s)")
    parser.add_argument("--period", type=float, default=0.5e-6, help="CH1 pulse period (s). Default 0.5µs")

    # CH1 voltage parameters
    parser.add_argument("--start-v", type=float, default=1.5, help="CH1 start voltage (V)")
    parser.add_argument("--stop-v", type=float, default=1.5, help="CH1 stop voltage (V)")
    parser.add_argument("--step-v", type=float, default=0.0, help="CH1 step voltage (V). 0 = single pulse")
    parser.add_argument("--base-v", type=float, default=0.0, help="CH1 base voltage (V)")

    # CH1 range and measurement parameters
    parser.add_argument("--volts-source-rng", type=float, default=10.0, help="CH1 voltage source range (V)")
    parser.add_argument("--current-measure-rng", type=float, default=0.00001, help="CH1 current measure range (A, default 10µA)")
    parser.add_argument("--dut-res", type=float, default=1e6, help="DUT resistance (Ohm)")
    parser.add_argument("--sample-rate", type=float, default=200e6, help="Sample rate (Sa/s)")
    parser.add_argument("--pulse-avg-cnt", type=int, default=1, help="Pulse averaging count")
    parser.add_argument("--burst-count", type=int, default=100, help="Number of CH1 pulse repetitions")
    parser.add_argument("--acq-type", type=int, default=1, choices=[0, 1], 
                       help="0=discrete (full waveform), 1=average (one value per pulse)")
    parser.add_argument("--pmu-mode", type=int, default=0, choices=[0, 1], help="PMU mode: 0=simple, 1=advanced")
    parser.add_argument("--pre-data-pct", type=float, default=0.1, help="Pre-pulse data capture percentage")
    parser.add_argument("--post-data-pct", type=float, default=0.1, help="Post-pulse data capture percentage")
    parser.add_argument("--lle-comp", type=int, default=0, choices=[0, 1], help="Load line effect compensation")

    # Instrument parameters
    parser.add_argument("--chan", type=int, default=1, choices=[1, 2], help="PMU channel for DUT measurement")
    parser.add_argument("--pmu-id", type=str, default="PMU1", help="PMU instrument ID")
    parser.add_argument("--array-size", type=int, default=0, help="Output array size (0=auto)")

    # CH2 binary pattern parameters
    parser.add_argument("--ch2-enable", type=int, default=1, choices=[0, 1], 
                       help="Enable CH2 for binary pattern. Default 1 (enabled)")
    parser.add_argument("--ch2-vrange", type=float, default=10.0, help="CH2 voltage range (V)")
    parser.add_argument("--ch2-pattern", type=str, default="10110100", 
                       help="CH2 binary pattern (string of 0s and 1s, e.g., '10110100' or '1,0,1,1,0,1,0,0')")
    parser.add_argument("--ch2-delay", type=float, default=0.0, 
                       help="CH2 delay (s). Default 0s (time delay before pattern starts, holds at 0V)")
    parser.add_argument("--ch2-width", type=float, default=500e-9, 
                       help="CH2 pulse width (s). Default 500ns (duration of flat high for '1' bits)")
    parser.add_argument("--ch2-rise", type=float, default=100e-9, 
                       help="CH2 rise time (s). Default 100ns (transition time from low to high)")
    parser.add_argument("--ch2-fall", type=float, default=100e-9, 
                       help="CH2 fall time (s). Default 100ns (transition time from high to low)")
    parser.add_argument("--ch2-spacing", type=float, default=500e-9, 
                       help="CH2 spacing (s). Default 500ns (low time between pulses)")
    parser.add_argument("--ch2-vlow", type=float, default=0.0, help="CH2 voltage for '0' bits (V)")
    parser.add_argument("--ch2-vhigh", type=float, default=1.5, help="CH2 voltage for '1' bits (V)")
    parser.add_argument("--ch2-loop-count", type=float, default=1.0, 
                       help="CH2 loop count (how many times to repeat the pattern)")

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    print("\n" + "="*80)
    print("ACraig11 PMU Waveform Binary Pattern Runner - Starting")
    print("="*80)
    
    args = parse_arguments()
    
    if args.dry_run:
        # Parse pattern for dry run
        try:
            ch2_pattern = parse_pattern(args.ch2_pattern)
            ch2_pattern_size = len(ch2_pattern)
        except ValueError as e:
            print(f"[ERROR] Invalid pattern: {e}")
            return
        
        array_size = args.array_size
        if array_size == 0:
            array_size = args.burst_count if args.acq_type == 1 else 10000
        
        ch2_loop_count = max(1.0, float(args.ch2_loop_count))
        debug_enable = 1
        
        command = build_ex_command(
            args.width, args.rise, args.fall, args.delay, args.period,
            args.volts_source_rng, args.current_measure_rng, args.dut_res,
            args.start_v, args.stop_v, args.step_v, args.base_v,
            args.acq_type, args.lle_comp, args.pre_data_pct, args.post_data_pct,
            args.pulse_avg_cnt, args.burst_count, args.sample_rate, args.pmu_mode,
            args.chan, args.pmu_id, array_size,
            args.ch2_enable, args.ch2_vrange,
            ch2_pattern, ch2_pattern_size,
            args.ch2_width, args.ch2_spacing, args.ch2_vlow, args.ch2_vhigh, ch2_loop_count,
            debug_enable
        )
        
        print("\n" + "="*80)
        print("[DRY RUN] Generated EX command:")
        print("="*80)
        print(command)
        print("="*80)
        return
    
    run_measurement(args, enable_plot=not args.no_plot)


if __name__ == "__main__":
    main()

