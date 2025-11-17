"""ACraig10 PMU Waveform with SegArb runner (KXCI compatible).

This script wraps the `EX ACraig10 ACraig10_PMU_Waveform_SegArb(...)` command,
executes it on a Keithley 4200A via KXCI, and retrieves the voltage/current
waveform data.

CH1: Continuous waveform reads at specified period (simple pulse commands)
CH2: Laser pulse using seg_arb at independent period (no period constraint!)

KEY ADVANTAGE OVER ACraig9:
- CH2 period is INDEPENDENT of CH1 period (no period sharing constraint!)
- CH2 uses seg_arb, so you can pulse at any period you want
- Both channels execute together but operate independently

⚠️  SINGLE-CHANNEL MODE CURRENT MEASUREMENT LIMITATION:
═══════════════════════════════════════════════════════════════════════════════
This script uses CH1 for BOTH forcing and measuring (single-channel mode)
because CH2 is needed for the laser pulse. This differs from other scripts
(e.g., pmu_pulse_read_interleaved) which use dual-channel mode:
- Dual-channel: CH1 (force), CH2 (measure) → Accurate current measurement
- Single-channel: CH1 (force + measure) → May have range saturation issues

OBSERVED ISSUE: Current measurements appear to scale with range setting,
suggesting range saturation rather than actual DUT current:
- 100nA range → ~108nA current (108% of range, saturated)
- 1µA range → ~1.09µA current (109% of range, saturated)

This indicates current is being clamped at the range limit, not real measured
current. For accurate current measurement, consider:
1. Using dual-channel mode if CH2 can be freed up for measurement
2. Verifying physical connections (CH1 Force/Measure to DUT, CH1 Sense/Ground)
3. Using this script primarily for voltage monitoring rather than resistance

Current range limits:
- Minimum: 100nA (1e-7 A) - Below this returns error -122
- Maximum: 0.8 A
- Default: 100nA (1e-7 A)

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

    # CH1 reads at 2µs, CH2 pulses laser every 10µs
    python run_acraig10_waveform_segarb.py --burst-count 50 --period 2e-6 --ch2-period 10e-6 --ch2-width 1e-6

    # CH1 reads at 1µs, CH2 pulses every 5µs
    python run_acraig10_waveform_segarb.py --burst-count 100 --period 1e-6 --ch2-period 5e-6 --ch2-width 500e-9

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
    # CH1 parameters
    width: float, rise: float, fall: float, delay: float, period: float,
    volts_source_rng: float, current_measure_rng: float, dut_res: float,
    start_v: float, stop_v: float, step_v: float, base_v: float,
    acq_type: int, lle_comp: int, pre_data_pct: float, post_data_pct: float,
    pulse_avg_cnt: int, burst_count: int, sample_rate: float, pmu_mode: int,
    chan: int, pmu_id: str, array_size: int,
    # CH2 parameters (simple pulse mode - auto-build segments)
    ch2_enable: int, ch2_vrange: float,
    ch2_vlow: float, ch2_vhigh: float, ch2_width: float,
    ch2_rise: float, ch2_fall: float, ch2_period: float, ch2_loop_count: float,
    clarius_debug: int = 1
) -> str:
    """Build EX command for ACraig10_PMU_Waveform_SegArb."""
    
    # For auto-build mode (Ch2NumSegments=0), we need empty arrays for seg_arb parameters
    # The C code will auto-build segments from Ch2Vlow, Ch2Vhigh, Ch2Width, etc.
    ch2_num_segments = 0  # 0 = auto-build mode
    
    params = [
        # CH1 parameters
        format_param(width),
        format_param(rise),
        format_param(fall),
        format_param(delay),
        format_param(period),
        format_param(volts_source_rng),
        format_param(current_measure_rng),
        format_param(dut_res),
        format_param(start_v),
        format_param(stop_v),
        format_param(step_v),
        format_param(base_v),
        format_param(acq_type),
        format_param(lle_comp),
        format_param(pre_data_pct),
        format_param(post_data_pct),
        format_param(pulse_avg_cnt),
        format_param(burst_count),
        format_param(sample_rate),
        format_param(pmu_mode),
        format_param(chan),
        pmu_id,
        "",  # V_Meas output array
        format_param(array_size),
        "",  # I_Meas output array
        format_param(array_size),
        "",  # T_Stamp output array
        format_param(array_size),
        # CH2 parameters - ORDER MATCHES METADATA (KXCI uses metadata order, not function signature!)
        # Metadata order: Ch2Enable, Ch2VRange, Ch2Vlow-Ch2Period, Ch2NumSegments, arrays..., Ch2LoopCount, ClariusDebug
        format_param(ch2_enable),           # 29: Ch2Enable
        format_param(ch2_vrange),          # 30: Ch2VRange
        format_param(ch2_vlow),            # 31: Ch2Vlow (metadata order!)
        format_param(ch2_vhigh),           # 32: Ch2Vhigh
        format_param(ch2_width),           # 33: Ch2Width
        format_param(ch2_rise),            # 34: Ch2Rise
        format_param(ch2_fall),            # 35: Ch2Fall
        format_param(ch2_period),          # 36: Ch2Period
        format_param(ch2_num_segments),    # 37: Ch2NumSegments (0 = auto-build mode)
        "",                                 # 38: Ch2StartV (empty array for auto-build)
        format_param(10),                  # 39: Ch2StartV_size (min 3, but 10 is safe)
        "",                                 # 40: Ch2StopV (empty array)
        format_param(10),                  # 41: Ch2StopV_size
        "",                                 # 42: Ch2SegTime (empty array)
        format_param(10),                  # 43: Ch2SegTime_size (min 3, but 10 is safe)
        "",                                 # 44: Ch2SSRCtrl (empty array)
        format_param(10),                  # 45: Ch2SSRCtrl_size
        "",                                 # 46: Ch2SegTrigOut (empty array)
        format_param(10),                  # 47: Ch2SegTrigOut_size
        "",                                 # 48: Ch2MeasType (empty array) - THIS IS PARAMETER 48!
        format_param(10),                  # 49: Ch2MeasType_size (min 3, but 10 is safe)
        "",                                 # 50: Ch2MeasStart (empty array)
        format_param(10),                  # 51: Ch2MeasStart_size
        "",                                 # 52: Ch2MeasStop (empty array)
        format_param(10),                  # 53: Ch2MeasStop_size
        format_param(ch2_loop_count),      # 54: Ch2LoopCount (MUST be >= 1.0!)
        format_param(clarius_debug),       # 55: ClariusDebug
    ]

    return f"EX A_Ch1Read_Ch2Laser_Pulse ACraig10_PMU_Waveform_SegArb({','.join(params)})"


def run_measurement(args, enable_plot: bool) -> None:
    """Run the measurement and retrieve data."""
    
    # Auto-calculate array_size if needed
    array_size = args.array_size
    if array_size == 0:
        if args.acq_type == 1:
            array_size = args.burst_count
        else:
            array_size = min(int(args.period * args.sample_rate * args.burst_count) + 100, 10000)
        print(f"[Auto] array_size set to {array_size}")
    
    # Auto-calculate CH2 loop count if not specified
    ch2_loop_count = args.ch2_loop_count
    print(f"[DEBUG] Initial ch2_loop_count from args: {ch2_loop_count}")
    
    if ch2_loop_count <= 0:
        # For single pulse: CH2 cycle time = delay + pulse_time + post_delay
        # But since we want single pulse, loop_count should be 1.0
        ch2_loop_count = 1.0
        print(f"[Auto] CH2 loop count set to 1.0 (single pulse mode)")
    
    # Final validation - ensure it's always > 0
    if ch2_loop_count <= 0:
        print(f"[ERROR] CH2 loop count must be > 0, got {ch2_loop_count}")
        ch2_loop_count = 1.0
        print(f"[FIX] Setting CH2 loop count to {ch2_loop_count}")
    
    print(f"[DEBUG] Final ch2_loop_count being passed to C: {ch2_loop_count}")
    print(f"[DEBUG] ch2_loop_count type: {type(ch2_loop_count)}, value: {ch2_loop_count}")
    
    # Ensure ch2_loop_count is a float and >= 1.0
    ch2_loop_count = float(ch2_loop_count)
    if ch2_loop_count < 1.0:
        print(f"[ERROR] ch2_loop_count ({ch2_loop_count}) < 1.0, forcing to 1.0")
        ch2_loop_count = 1.0
    
    # Enable debug by default
    debug_enable = 1
    
    print(f"[DEBUG] Building command with ch2_loop_count={ch2_loop_count}")
    
    command = build_ex_command(
        args.width, args.rise, args.fall, args.delay, args.period,
        args.volts_source_rng, args.current_measure_rng, args.dut_res,
        args.start_v, args.stop_v, args.step_v, args.base_v,
        args.acq_type, args.lle_comp, args.pre_data_pct, args.post_data_pct,
        args.pulse_avg_cnt, args.burst_count, args.sample_rate, args.pmu_mode,
        args.chan, args.pmu_id, array_size,
        args.ch2_enable, args.ch2_vrange,
        args.ch2_vlow, args.ch2_vhigh, args.ch2_width,
        args.ch2_rise, args.ch2_fall, args.ch2_period, ch2_loop_count,
        debug_enable
    )
    
    print("\n" + "="*80)
    print("[DEBUG] Generated EX command:")
    print("="*80)
    print(command)
    print("="*80)
    
    # Extract and show parameter 48 (Ch2LoopCount) from the command
    try:
        params_str = command.split("(")[1].rstrip(")")
        # Filter out empty strings from split (empty arrays create empty strings)
        params_list = [p for p in params_str.split(",") if p.strip()]
        # Count non-empty parameters to find Ch2LoopCount
        # Ch2LoopCount should be near the end (parameter 54 in metadata, but empty strings shift indices)
        if len(params_list) >= 50:  # Should have at least 50 non-empty params
            # Ch2LoopCount is the second-to-last parameter (before ClariusDebug)
            ch2_loop_param = params_list[-2] if len(params_list) >= 2 else "N/A"
            print(f"\n[DEBUG] Ch2LoopCount (from command): '{ch2_loop_param}'")
            print(f"[DEBUG] Total non-empty parameters: {len(params_list)}")
    except Exception as e:
        print(f"[DEBUG] Could not parse parameters: {e}")
    
    controller = KXCIClient(gpib_address=args.gpib_address, timeout=args.timeout)

    try:
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")

        print("\n[KXCI] Sending command to instrument...")
        
        print(f"\n[KXCI] CH1: {args.burst_count} pulses @ {args.period*1e6:.2f}µs period")
        print(f"[KXCI] CH1 pulse: width={args.width*1e6:.2f}µs, rise={args.rise*1e6:.2f}µs, fall={args.fall*1e6:.2f}µs")
        
        if args.ch2_enable:
            print(f"[KXCI] CH2: Single laser pulse starting {args.ch2_period*1e6:.2f}µs into measurement")
            print(f"[KXCI]        {args.ch2_vlow}V → {args.ch2_vhigh}V, width={args.ch2_width*1e6:.2f}µs")
            print(f"[KXCI]        Loop count: {ch2_loop_count:.1f} (single pulse)")

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

        # Parameter positions: 23=V_Meas, 25=I_Meas, 27=T_Stamp
        num_points = args.burst_count if args.acq_type == 1 else array_size
        print(f"[KXCI] Requesting {num_points} points")
        
        voltage = safe_query(23, num_points, "voltage")
        current = safe_query(25, num_points, "current")
        time_axis = safe_query(27, num_points, "time")
        
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

        # Diagnostic output: Check raw current values
        import numpy as np
        print("\n[DIAGNOSTIC] Current measurement analysis:")
        print(f"  Total samples: {len(current)}")
        print(f"  Current range: [{np.min(current):.3e}, {np.max(current):.3e}] A")
        print(f"  Current mean: {np.mean(current):.3e} A")
        print(f"  Current std: {np.std(current):.3e} A")
        print(f"  Non-zero currents: {np.sum(np.abs(current) > 1e-12)} / {len(current)}")
        
        # Check if there's current when voltage is near zero (baseline/offset check)
        low_voltage_mask = np.abs(voltage) < 0.1
        if np.any(low_voltage_mask):
            baseline_current = np.mean(np.array(current)[low_voltage_mask])
            print(f"  Baseline current (when |V| < 0.1V): {baseline_current:.3e} A")
            print(f"  This suggests offset/leakage: {'YES' if abs(baseline_current) > 1e-9 else 'NO'}")
        
        # Check if current is actually changing
        unique_currents = len(np.unique(np.round(current, decimals=12)))
        print(f"  Unique current values (rounded to 1pA): {unique_currents}")
        if unique_currents < 5:
            print("  ⚠️  WARNING: Current values show very little variation!")
            print("     This suggests the measurement may not be sensitive to device changes.")

        # Calculate resistance
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
            
            # Print resistance statistics
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

                    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
                    
                    ax1.plot(time_axis, voltage, label="Voltage", color="tab:blue", linewidth=1)
                    ax1.set_ylabel("Voltage (V)", color="tab:blue")
                    ax1.tick_params(axis="y", labelcolor="tab:blue")
                    ax1.grid(True, alpha=0.3)
                    ax1.set_title("ACraig10 PMU Waveform with SegArb")

                    ax2.plot(time_axis, current, label="Current", color="tab:red", linewidth=1)
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
        description="ACraig10 PMU Waveform with SegArb - CH1 continuous reads, CH2 independent laser pulse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CH1 reads at 2µs, CH2 pulses laser every 10µs
  python run_acraig10_waveform_segarb.py --burst-count 50 --period 2e-6 --ch2-period 10e-6 --ch2-width 1e-6

  # CH1 reads at 1µs, CH2 pulses every 5µs  
  python run_acraig10_waveform_segarb.py --burst-count 100 --period 1e-6 --ch2-period 5e-6 --ch2-width 500e-9
        """
    )

    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR", help="VISA resource string")
    parser.add_argument("--timeout", type=float, default=30.0, help="Visa timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only print the EX command")
    parser.add_argument("--no-plot", action="store_true", help="Disable plotting")

    # CH1 timing parameters
    parser.add_argument("--width", type=float, default=0.5e-6, help="CH1 pulse width (s). Default 1µs")
    parser.add_argument("--rise", type=float, default=100e-9, help="CH1 rise time (s). Default 100ns")
    parser.add_argument("--fall", type=float, default=100e-9, help="CH1 fall time (s). Default 100ns")
    parser.add_argument("--delay", type=float, default=0, help="CH1 pre-pulse delay (s)")
    parser.add_argument("--period", type=float, default=0.5e-6, help="CH1 pulse period (s). Default 1µs")

    # CH1 voltage parameters
    parser.add_argument("--start-v", type=float, default=1.0, help="CH1 start voltage (V)")
    parser.add_argument("--stop-v", type=float, default=1.0, help="CH1 stop voltage (V)")
    parser.add_argument("--step-v", type=float, default=0.0, help="CH1 step voltage (V). 0 = single pulse")
    parser.add_argument("--base-v", type=float, default=0.0, help="CH1 base voltage (V)")

    # CH1 range and measurement parameters
    parser.add_argument("--volts-source-rng", type=float, default=10.0, help="CH1 voltage source range (V)")
    parser.add_argument("--current-measure-rng", type=float, default=0.0000001, help="CH1 current measure range (A, default 100nA). Minimum: 100nA (1e-7), Maximum: 0.8A. ⚠️ Single-channel mode may show range saturation - current may scale with range setting rather than actual DUT current")
    parser.add_argument("--dut-res", type=float, default=1e6, help="DUT resistance (Ohm)")
    parser.add_argument("--sample-rate", type=float, default=200e6, help="Sample rate (Sa/s)")
    parser.add_argument("--pulse-avg-cnt", type=int, default=1, help="Pulse averaging count")
    parser.add_argument("--burst-count", type=int, default=500, help="Number of CH1 pulse repetitions")
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

    # CH2 seg_arb parameters (simple pulse mode - auto-build)
    parser.add_argument("--ch2-enable", type=int, default=1, choices=[0, 1], 
                       help="Enable CH2 for laser pulse. Default 1 (enabled)")
    parser.add_argument("--ch2-vrange", type=float, default=10.0, help="CH2 voltage range (V)")
    parser.add_argument("--ch2-vlow", type=float, default=0.0, help="CH2 low voltage (V)")
    parser.add_argument("--ch2-vhigh", type=float, default=1.5, help="CH2 high voltage (V)")
    parser.add_argument("--ch2-width", type=float, default=10e-6, 
                       help="CH2 pulse width (s). Default 10µs")
    parser.add_argument("--ch2-rise", type=float, default=100e-9, help="CH2 rise time (s). Default 100ns")
    parser.add_argument("--ch2-fall", type=float, default=100e-9, help="CH2 fall time (s). Default 100ns")
    parser.add_argument("--ch2-period", type=float, default=5e-6, 
                       help="CH2 delay before pulse starts (s). Default 5µs (pulse fires 5µs into measurement)")
    parser.add_argument("--ch2-loop-count", type=float, default=1.0, 
                       help="CH2 loop count (0=auto-calculate to match CH1 duration)")

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    print("\n" + "="*80)
    print("ACraig10 PMU Waveform SegArb Runner - Starting")
    print("="*80)
    
    args = parse_arguments()
    
    print(f"[DEBUG] Parsed arguments:")
    print(f"  burst_count: {args.burst_count}")
    print(f"  period: {args.period}")
    print(f"  ch2_enable: {args.ch2_enable}")
    print(f"  ch2_period: {args.ch2_period}")
    print(f"  ch2_loop_count (from args): {args.ch2_loop_count}")

    # Build command
    array_size = args.array_size
    if array_size == 0:
        array_size = args.burst_count if args.acq_type == 1 else 10000
    
    ch2_loop_count = args.ch2_loop_count
    print(f"[DEBUG] Initial ch2_loop_count from args: {ch2_loop_count}")
    
    if ch2_loop_count <= 0:
        # CH2 cycle time = Ch2Period (one complete pulse cycle)
        ch2_cycle_time = args.ch2_period
        ch1_total_time = args.burst_count * args.period
        print(f"[DEBUG] CH2 cycle time: {ch2_cycle_time:.6e} s")
        print(f"[DEBUG] CH1 total time: {ch1_total_time:.6e} s ({args.burst_count} pulses × {args.period:.6e} s)")
        
        if ch2_cycle_time > 1e-12:  # Avoid division by very small numbers
            ch2_loop_count = ch1_total_time / ch2_cycle_time
            print(f"[DEBUG] Calculated ch2_loop_count: {ch2_loop_count:.6f}")
        else:
            print(f"[WARN] CH2 period too small ({ch2_cycle_time:.6e}), using default 1.0")
            ch2_loop_count = 1.0
        
        # Ensure at least 1.0 (C code requires > 0)
        ch2_loop_count = max(1.0, ch2_loop_count)
    
    # Final validation - ensure it's always > 0
    if ch2_loop_count <= 0:
        print(f"[ERROR] CH2 loop count must be > 0, got {ch2_loop_count}")
        ch2_loop_count = 1.0
        print(f"[FIX] Setting CH2 loop count to {ch2_loop_count}")
    
    print(f"[DEBUG] Final ch2_loop_count being passed to C: {ch2_loop_count}")
    print(f"[DEBUG] ch2_loop_count type: {type(ch2_loop_count)}, value: {ch2_loop_count}")
    
    # Ensure ch2_loop_count is a float and >= 1.0
    ch2_loop_count = float(ch2_loop_count)
    if ch2_loop_count < 1.0:
        print(f"[ERROR] ch2_loop_count ({ch2_loop_count}) < 1.0, forcing to 1.0")
        ch2_loop_count = 1.0
    
    # Enable debug by default
    debug_enable = 1
    
    print(f"[DEBUG] Building command with ch2_loop_count={ch2_loop_count}")

    command = build_ex_command(
        args.width, args.rise, args.fall, args.delay, args.period,
        args.volts_source_rng, args.current_measure_rng, args.dut_res,
        args.start_v, args.stop_v, args.step_v, args.base_v,
        args.acq_type, args.lle_comp, args.pre_data_pct, args.post_data_pct,
        args.pulse_avg_cnt, args.burst_count, args.sample_rate, args.pmu_mode,
        args.chan, args.pmu_id, array_size,
        args.ch2_enable, args.ch2_vrange,
        args.ch2_vlow, args.ch2_vhigh, args.ch2_width,
        args.ch2_rise, args.ch2_fall, args.ch2_period, ch2_loop_count,
        debug_enable
    )

    print("Generated EX command:\n" + command)

    if args.dry_run:
        return

    run_measurement(args, enable_plot=not args.no_plot)


if __name__ == "__main__":
    main()

