"""ACraig13 PMU Waveform with Flexible SegArb runner (KXCI compatible).

This script wraps the `EX ACraig13 ACraig13_PMU_Waveform_FlexSegArb(...)` command,
executes it on a Keithley 4200A via KXCI, and retrieves the voltage/current
waveform data.

CH1: Continuous waveform reads using seg_arb (auto-built from simple pulse parameters)
CH2: Flexible seg_arb waveform with segments designed in Python

KEY FEATURES:
- CH1: Simple pulse parameters converted to seg_arb automatically
- CH2: Complete flexibility - design segments in Python and pass as arrays
- Both channels use seg_arb, allowing independent timing

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

CH2 SEGMENT DESIGN:
===================
Design CH2 segments in Python by creating arrays:
- Ch2StartV: Start voltage for each segment
- Ch2StopV: Stop voltage for each segment
- Ch2SegTime: Duration of each segment (minimum 20ns)
- Ch2SSRCtrl: SSR control (1=closed, 0=open)
- Ch2SegTrigOut: Trigger output (1=trigger, 0=no trigger). First segment MUST be 1
- Ch2MeasType: Measurement type (0=no measure, 2=waveform)
- Ch2MeasStart: Measurement start time within segment
- Ch2MeasStop: Measurement stop time within segment

CRITICAL REQUIREMENTS:
- Segment voltages must be continuous: stopV[i] == startV[i+1]
- First segment MUST have Ch2SegTrigOut[0] = 1
- All segment times must be >= 20ns

Usage examples:

    # Simple CH2 pulse: 0V -> 1.5V -> 0V
    python run_acraig13_waveform_flex_segarb.py --burst-count 50 --period 2e-6

    # Custom CH2 waveform with multiple segments
    python run_acraig13_waveform_flex_segarb.py --burst-count 100 --period 1e-6

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
        if value >= 1.0 and value < 1e6:
            if value == int(value):
                return str(int(value))
            return f"{value:.10g}".rstrip('0').rstrip('.')
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


def build_ch2_segments_simple(
    vlow: float, vhigh: float, width: float, rise: float, fall: float, delay: float
) -> tuple[List[float], List[float], List[float], List[int], List[int], List[int], List[float], List[float]]:
    """Build simple CH2 segments: delay -> rise -> width -> fall -> 0V.
    
    Returns:
        (startV, stopV, segTime, ssrCtrl, segTrigOut, measType, measStart, measStop)
    """
    min_seg_time = 20e-9  # 20ns minimum
    
    # Ensure all times meet minimum
    delay = max(delay, min_seg_time) if delay > 0 else min_seg_time
    rise = max(rise, min_seg_time)
    width = max(width, min_seg_time)
    fall = max(fall, min_seg_time)
    
    startV = []
    stopV = []
    segTime = []
    ssrCtrl = []
    segTrigOut = []
    measType = []
    measStart = []
    measStop = []
    
    # Segment 0: Delay at vlow (with trigger)
    startV.append(vlow)
    stopV.append(vlow)
    segTime.append(delay)
    ssrCtrl.append(1)
    segTrigOut.append(1)  # First segment triggers
    measType.append(0)
    measStart.append(0.0)
    measStop.append(0.0)
    
    # Segment 1: Rise (vlow -> vhigh)
    startV.append(vlow)
    stopV.append(vhigh)
    segTime.append(rise)
    ssrCtrl.append(1)
    segTrigOut.append(0)
    measType.append(0)
    measStart.append(0.0)
    measStop.append(0.0)
    
    # Segment 2: Width (at vhigh)
    startV.append(vhigh)
    stopV.append(vhigh)
    segTime.append(width)
    ssrCtrl.append(1)
    segTrigOut.append(0)
    measType.append(0)
    measStart.append(0.0)
    measStop.append(0.0)
    
    # Segment 3: Fall (vhigh -> vlow)
    startV.append(vhigh)
    stopV.append(vlow)
    segTime.append(fall)
    ssrCtrl.append(1)
    segTrigOut.append(0)
    measType.append(0)
    measStart.append(0.0)
    measStop.append(0.0)
    
    # Segment 4: Final 0V segment
    startV.append(vlow)
    stopV.append(0.0)
    segTime.append(min_seg_time)
    ssrCtrl.append(1)
    segTrigOut.append(0)
    measType.append(0)
    measStart.append(0.0)
    measStop.append(0.0)
    
    return startV, stopV, segTime, ssrCtrl, segTrigOut, measType, measStart, measStop


def build_ex_command(
    # CH1 parameters
    width: float, rise: float, fall: float, delay: float, period: float,
    volts_source_rng: float, current_measure_rng: float, dut_res: float,
    start_v: float, stop_v: float, step_v: float, base_v: float,
    acq_type: int, lle_comp: int, pre_data_pct: float, post_data_pct: float,
    pulse_avg_cnt: int, burst_count: int, sample_rate: float, pmu_mode: int,
    chan: int, pmu_id: str, array_size: int,
    # CH2 parameters (flexible seg_arb)
    ch2_enable: int, ch2_vrange: float, ch2_num_segments: int,
    ch2_startv: List[float], ch2_stopv: List[float], ch2_segtime: List[float],
    ch2_ssrctrl: List[int], ch2_segtrigout: List[int], ch2_meastype: List[int],
    ch2_measstart: List[float], ch2_measstop: List[float], ch2_loop_count: float,
    clarius_debug: int = 1
) -> str:
    """Build EX command for ACraig13_PMU_Waveform_FlexSegArb."""
    
    params = [
        # CH1 parameters (1-27)
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
        # CH2 parameters (28-40)
        format_param(ch2_enable),           # 28: Ch2Enable
        format_param(ch2_vrange),          # 29: Ch2VRange
        format_param(ch2_num_segments),    # 30: Ch2NumSegments
        # CH2 segment arrays (passed as comma-separated strings)
        ",".join(format_param(v) for v in ch2_startv),      # 31: Ch2StartV
        ",".join(format_param(v) for v in ch2_stopv),       # 32: Ch2StopV
        ",".join(format_param(v) for v in ch2_segtime),     # 33: Ch2SegTime
        ",".join(format_param(v) for v in ch2_ssrctrl),     # 34: Ch2SSRCtrl
        ",".join(format_param(v) for v in ch2_segtrigout),  # 35: Ch2SegTrigOut
        ",".join(format_param(v) for v in ch2_meastype),    # 36: Ch2MeasType
        ",".join(format_param(v) for v in ch2_measstart),   # 37: Ch2MeasStart
        ",".join(format_param(v) for v in ch2_measstop),    # 38: Ch2MeasStop
        format_param(ch2_loop_count),       # 39: Ch2LoopCount
        format_param(clarius_debug),        # 40: ClariusDebug
    ]

    return f"EX ACraig13 ACraig13_PMU_Waveform_FlexSegArb({','.join(params)})"


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
    
    # Build CH2 segments
    if args.ch2_enable:
        ch2_startv, ch2_stopv, ch2_segtime, ch2_ssrctrl, ch2_segtrigout, ch2_meastype, ch2_measstart, ch2_measstop = build_ch2_segments_simple(
            args.ch2_vlow, args.ch2_vhigh, args.ch2_width, args.ch2_rise, args.ch2_fall, args.ch2_delay
        )
        ch2_num_segments = len(ch2_startv)
        print(f"[CH2] Built {ch2_num_segments} segments:")
        for i in range(ch2_num_segments):
            print(f"  Seg {i}: {ch2_startv[i]:.6g}V -> {ch2_stopv[i]:.6g}V, time={ch2_segtime[i]:.6g}s")
    else:
        ch2_num_segments = 0
        ch2_startv = ch2_stopv = ch2_segtime = []
        ch2_ssrctrl = ch2_segtrigout = ch2_meastype = []
        ch2_measstart = ch2_measstop = []
    
    # Validate CH2 loop count
    ch2_loop_count = args.ch2_loop_count
    if ch2_loop_count <= 0:
        ch2_loop_count = 1.0
    if ch2_loop_count < 1.0:
        ch2_loop_count = 1.0
    
    command = build_ex_command(
        args.width, args.rise, args.fall, args.delay, args.period,
        args.volts_source_rng, args.current_measure_rng, args.dut_res,
        args.start_v, args.stop_v, args.step_v, args.base_v,
        args.acq_type, args.lle_comp, args.pre_data_pct, args.post_data_pct,
        args.pulse_avg_cnt, args.burst_count, args.sample_rate, args.pmu_mode,
        args.chan, args.pmu_id, array_size,
        args.ch2_enable, args.ch2_vrange, ch2_num_segments,
        ch2_startv, ch2_stopv, ch2_segtime,
        ch2_ssrctrl, ch2_segtrigout, ch2_meastype,
        ch2_measstart, ch2_measstop, ch2_loop_count,
        1  # debug enabled
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
            print(f"[KXCI] CH2: {ch2_num_segments} segments, loop count={ch2_loop_count:.1f}")

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
                    ax1.set_title("ACraig13 PMU Waveform with Flexible SegArb")

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
        description="ACraig13 PMU Waveform with Flexible SegArb - CH1 auto-built, CH2 designed in Python",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple CH2 pulse
  python run_acraig13_waveform_flex_segarb.py --burst-count 50 --period 2e-6 --ch2-width 1e-6

  # Custom CH2 waveform
  python run_acraig13_waveform_flex_segarb.py --burst-count 100 --period 1e-6 --ch2-delay 5e-6
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
    parser.add_argument("--start-v", type=float, default=1.0, help="CH1 start voltage (V)")
    parser.add_argument("--stop-v", type=float, default=1.0, help="CH1 stop voltage (V)")
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

    # CH2 flexible seg_arb parameters
    parser.add_argument("--ch2-enable", type=int, default=1, choices=[0, 1], 
                       help="Enable CH2 for flexible seg_arb. Default 1 (enabled)")
    parser.add_argument("--ch2-vrange", type=float, default=10.0, help="CH2 voltage range (V)")
    parser.add_argument("--ch2-vlow", type=float, default=0.0, help="CH2 low voltage (V)")
    parser.add_argument("--ch2-vhigh", type=float, default=1.5, help="CH2 high voltage (V)")
    parser.add_argument("--ch2-width", type=float, default=10e-6, 
                       help="CH2 pulse width (s). Default 10µs")
    parser.add_argument("--ch2-rise", type=float, default=100e-9, help="CH2 rise time (s). Default 100ns")
    parser.add_argument("--ch2-fall", type=float, default=100e-9, help="CH2 fall time (s). Default 100ns")
    parser.add_argument("--ch2-delay", type=float, default=5e-6, 
                       help="CH2 delay before pulse starts (s). Default 5µs")
    parser.add_argument("--ch2-loop-count", type=float, default=1.0, 
                       help="CH2 loop count (must be >= 1.0)")

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    print("\n" + "="*80)
    print("ACraig13 PMU Waveform Flexible SegArb Runner - Starting")
    print("="*80)
    
    args = parse_arguments()
    
    # Build command
    array_size = args.array_size
    if array_size == 0:
        array_size = args.burst_count if args.acq_type == 1 else 10000

    if args.dry_run:
        # Build CH2 segments for dry-run display
        if args.ch2_enable:
            ch2_startv, ch2_stopv, ch2_segtime, ch2_ssrctrl, ch2_segtrigout, ch2_meastype, ch2_measstart, ch2_measstop = build_ch2_segments_simple(
                args.ch2_vlow, args.ch2_vhigh, args.ch2_width, args.ch2_rise, args.ch2_fall, args.ch2_delay
            )
            ch2_num_segments = len(ch2_startv)
        else:
            ch2_num_segments = 0
            ch2_startv = ch2_stopv = ch2_segtime = []
            ch2_ssrctrl = ch2_segtrigout = ch2_meastype = []
            ch2_measstart = ch2_measstop = []
        
        ch2_loop_count = args.ch2_loop_count if args.ch2_loop_count > 0 else 1.0
        
        command = build_ex_command(
            args.width, args.rise, args.fall, args.delay, args.period,
            args.volts_source_rng, args.current_measure_rng, args.dut_res,
            args.start_v, args.stop_v, args.step_v, args.base_v,
            args.acq_type, args.lle_comp, args.pre_data_pct, args.post_data_pct,
            args.pulse_avg_cnt, args.burst_count, args.sample_rate, args.pmu_mode,
            args.chan, args.pmu_id, array_size,
            args.ch2_enable, args.ch2_vrange, ch2_num_segments,
            ch2_startv, ch2_stopv, ch2_segtime,
            ch2_ssrctrl, ch2_segtrigout, ch2_meastype,
            ch2_measstart, ch2_measstop, ch2_loop_count,
            1
        )
        print("\nGenerated EX command:\n" + command)
        return

    run_measurement(args, enable_plot=not args.no_plot)


if __name__ == "__main__":
    main()

