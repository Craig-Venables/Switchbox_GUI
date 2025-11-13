"""ACraig12 PMU+SMU Sweep runner (KXCI compatible).

This script wraps the `EX ACraig12 ACraig12_PMU_SMU_Sweep(...)` command,
executes it on a Keithley 4200A via KXCI, and retrieves the voltage/current
data from combined PMU pulse and SMU DC measurements.

This module supports three execution modes:
- Mode 0 (Pulse+SMU): Perform both PMU pulse test and SMU DC test
- Mode 1 (Pulse only): Perform only PMU pulse test
- Mode 2 (SMU only): Perform only SMU DC test

PMU Pulse Test:
- CH1: Fixed amplitude pulse train
- CH2: Swept amplitude pulse train
- Returns: Voltage/current at pulse top and base for both channels

SMU DC Test:
- CH1 SMU: Fixed DC bias
- CH2 SMU: Swept DC voltage
- Returns: DC voltage and current for both SMUs

Usage examples:

    # Pulse test only
    python run_acraig12_pmu_smu_sweep.py --exec-mode 1 --start-v-ch2 0.0 --stop-v-ch2 5.0 --step-v-ch2 0.1

    # SMU test only
    python run_acraig12_pmu_smu_sweep.py --exec-mode 2 --start-v-ch2 0.0 --stop-v-ch2 5.0 --step-v-ch2 0.1

    # Both tests
    python run_acraig12_pmu_smu_sweep.py --exec-mode 0 --start-v-ch2 0.0 --stop-v-ch2 5.0 --step-v-ch2 0.1

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
                    val = float(part)
                    # Filter out NaN values
                    if val == val:  # NaN check
                        values.append(val)
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
    # Pulse parameters
    pulse_width_ch1: float, rise_time_ch1: float, fall_time_ch1: float, delay_ch1: float,
    pulse_width_ch2: float, rise_time_ch2: float, fall_time_ch2: float, delay_ch2: float,
    period: float, pulse_average: int,
    load_line_ch1: int, load_line_ch2: int, res_ch1: float, res_ch2: float,
    ampl_v_ch1: float, base_v_ch1: float,
    start_v_ch2: float, stop_v_ch2: float, step_v_ch2: float, base_v_ch2: float,
    v_range_ch1: float, i_range_ch1: float, ltd_auto_curr_ch1: float,
    v_range_ch2: float, i_range_ch2: float, ltd_auto_curr_ch2: float,
    pmu_mode: int, smu_irange: float, smu_icomp: float,
    ch1_smu_id: str, ch2_smu_id: str, pmu_id: str, exec_mode: int,
    array_size: int, debug: int = 1
) -> str:
    """Build EX command for ACraig12_PMU_SMU_Sweep."""
    
    params = [
        # Pulse parameters (1-26)
        format_param(pulse_width_ch1),      # 1
        format_param(rise_time_ch1),        # 2
        format_param(fall_time_ch1),        # 3
        format_param(delay_ch1),            # 4
        format_param(pulse_width_ch2),      # 5
        format_param(rise_time_ch2),        # 6
        format_param(fall_time_ch2),        # 7
        format_param(delay_ch2),            # 8
        format_param(period),               # 9
        format_param(pulse_average),        # 10
        format_param(load_line_ch1),        # 11
        format_param(load_line_ch2),        # 12
        format_param(res_ch1),              # 13
        format_param(res_ch2),              # 14
        format_param(ampl_v_ch1),          # 15
        format_param(base_v_ch1),          # 16
        format_param(start_v_ch2),          # 17
        format_param(stop_v_ch2),           # 18
        format_param(step_v_ch2),           # 19
        format_param(base_v_ch2),          # 20
        format_param(v_range_ch1),          # 21
        format_param(i_range_ch1),          # 22
        format_param(ltd_auto_curr_ch1),    # 23
        format_param(v_range_ch2),          # 24
        format_param(i_range_ch2),          # 25
        format_param(ltd_auto_curr_ch2),    # 26
        format_param(pmu_mode),             # 27
        format_param(smu_irange),           # 28
        format_param(smu_icomp),            # 29
        ch1_smu_id,                         # 30
        ch2_smu_id,                         # 31
        pmu_id,                             # 32
        format_param(exec_mode),            # 33
        # Output arrays (34-69) - all empty strings, sizes follow
        "",                                 # 34: Ch1_V_Ampl
        format_param(array_size),           # 35: Ch1_V_Ampl_Size
        "",                                 # 36: Ch1_I_Ampl
        format_param(array_size),           # 37: Ch1_I_Ampl_Size
        "",                                 # 38: Ch1_V_Base
        format_param(array_size),           # 39: Ch1_V_Base_Size
        "",                                 # 40: Ch1_I_Base
        format_param(array_size),           # 41: Ch1_I_Base_Size
        "",                                 # 42: Ch2_V_Ampl
        format_param(array_size),           # 43: Ch2_V_Ampl_Size
        "",                                 # 44: Ch2_I_Ampl
        format_param(array_size),           # 45: Ch2_I_Ampl_Size
        "",                                 # 46: Ch2_V_Base
        format_param(array_size),           # 47: Ch2_V_Base_Size
        "",                                 # 48: Ch2_I_Base
        format_param(array_size),           # 49: Ch2_I_Base_Size
        "",                                 # 50: TimeStampAmpl_Ch1
        format_param(array_size),           # 51: TimeStampAmpl_Ch1_Size
        "",                                 # 52: TimeStampBase_Ch1
        format_param(array_size),           # 53: TimeStampBase_Ch1_Size
        "",                                 # 54: TimeStampAmpl_Ch2
        format_param(array_size),           # 55: TimeStampAmpl_Ch2_Size
        "",                                 # 56: TimeStampBase_Ch2
        format_param(array_size),           # 57: TimeStampBase_Ch2_Size
        "",                                 # 58: Status_Ch1
        format_param(array_size),           # 59: Status_Ch1_Size
        "",                                 # 60: Status_Ch2
        format_param(array_size),           # 61: Status_Ch2_Size
        "",                                 # 62: Ch2_SMU_Voltage
        format_param(array_size),           # 63: Ch2SMUVoltageSize
        "",                                 # 64: Ch2_SMU_Current
        format_param(array_size),           # 65: Ch2SMUCurrentSize
        "",                                 # 66: Ch1_SMU_Voltage
        format_param(array_size),           # 67: Ch1SMUVoltageSize
        "",                                 # 68: Ch1_SMU_Current
        format_param(array_size),           # 69: Ch1SMUCurrentSize
        format_param(debug),                # 70: ClariusDebug
    ]
    
    return f"EX ACraig12 ACraig12_PMU_SMU_Sweep({','.join(params)})"


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="ACraig12 PMU+SMU Sweep runner (KXCI compatible)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Pulse parameters CH1
    parser.add_argument("--pulse-width-ch1", type=float, default=1e-6,
                       help="CH1 pulse width in s (default: 1e-6)")
    parser.add_argument("--rise-time-ch1", type=float, default=40e-9,
                       help="CH1 rise time in s (default: 40e-9)")
    parser.add_argument("--fall-time-ch1", type=float, default=40e-9,
                       help="CH1 fall time in s (default: 40e-9)")
    parser.add_argument("--delay-ch1", type=float, default=0.0,
                       help="CH1 delay in s (default: 0.0)")
    
    # Pulse parameters CH2
    parser.add_argument("--pulse-width-ch2", type=float, default=1e-6,
                       help="CH2 pulse width in s (default: 1e-6)")
    parser.add_argument("--rise-time-ch2", type=float, default=100e-9,
                       help="CH2 rise time in s (default: 100e-9)")
    parser.add_argument("--fall-time-ch2", type=float, default=100e-9,
                       help="CH2 fall time in s (default: 100e-9)")
    parser.add_argument("--delay-ch2", type=float, default=0.0,
                       help="CH2 delay in s (default: 0.0)")
    
    # Common pulse parameters
    parser.add_argument("--period", type=float, default=2e-6,
                       help="Pulse period in s (default: 2e-6)")
    parser.add_argument("--pulse-average", type=int, default=1,
                       help="Number of pulses to average (default: 1)")
    
    # Load line and resistance
    parser.add_argument("--load-line-ch1", type=int, default=0, choices=[0, 1],
                       help="CH1 load line compensation (default: 0)")
    parser.add_argument("--load-line-ch2", type=int, default=0, choices=[0, 1],
                       help="CH2 load line compensation (default: 0)")
    parser.add_argument("--res-ch1", type=float, default=1e6,
                       help="CH1 expected resistance in Ohms (default: 1e6)")
    parser.add_argument("--res-ch2", type=float, default=1e6,
                       help="CH2 expected resistance in Ohms (default: 1e6)")
    
    # Voltage settings
    parser.add_argument("--ampl-v-ch1", type=float, default=2.0,
                       help="CH1 amplitude voltage in V (default: 2.0)")
    parser.add_argument("--base-v-ch1", type=float, default=0.0,
                       help="CH1 base voltage in V (default: 0.0)")
    parser.add_argument("--start-v-ch2", type=float, default=0.0,
                       help="CH2 start voltage in V (default: 0.0)")
    parser.add_argument("--stop-v-ch2", type=float, default=5.0,
                       help="CH2 stop voltage in V (default: 5.0)")
    parser.add_argument("--step-v-ch2", type=float, default=0.1,
                       help="CH2 step voltage in V (default: 0.1)")
    parser.add_argument("--base-v-ch2", type=float, default=0.0,
                       help="CH2 base voltage in V (default: 0.0)")
    
    # Ranges
    parser.add_argument("--v-range-ch1", type=float, default=10.0,
                       help="CH1 voltage range in V (default: 10.0)")
    parser.add_argument("--i-range-ch1", type=float, default=0.01,
                       help="CH1 current range in A (default: 0.01)")
    parser.add_argument("--ltd-auto-curr-ch1", type=float, default=0.0, choices=[0.0, 1.0],
                       help="CH1 limited auto current (default: 0.0)")
    parser.add_argument("--v-range-ch2", type=float, default=10.0,
                       help="CH2 voltage range in V (default: 10.0)")
    parser.add_argument("--i-range-ch2", type=float, default=0.2,
                       help="CH2 current range in A (default: 0.2)")
    parser.add_argument("--ltd-auto-curr-ch2", type=float, default=0.0, choices=[0.0, 1.0],
                       help="CH2 limited auto current (default: 0.0)")
    
    # PMU mode
    parser.add_argument("--pmu-mode", type=int, default=0, choices=[0, 1, 2],
                       help="PMU mode (0=Simple, 1=Advanced, default: 0)")
    
    # SMU settings
    parser.add_argument("--smu-irange", type=float, default=0.01,
                       help="SMU current range in A (default: 0.01)")
    parser.add_argument("--smu-icomp", type=float, default=0.01,
                       help="SMU current compliance in A (default: 0.01)")
    
    # Instrument IDs
    parser.add_argument("--ch1-smu-id", type=str, default="SMU1",
                       help="CH1 SMU ID (default: SMU1)")
    parser.add_argument("--ch2-smu-id", type=str, default="SMU2",
                       help="CH2 SMU ID (default: SMU2)")
    parser.add_argument("--pmu-id", type=str, default="PMU1",
                       help="PMU ID (default: PMU1)")
    
    # Execution mode
    parser.add_argument("--exec-mode", type=int, default=0, choices=[0, 1, 2],
                       help="Execution mode (0=Pulse+SMU, 1=Pulse only, 2=SMU only, default: 0)")
    
    # Array size
    parser.add_argument("--array-size", type=int, default=100,
                       help="Output array size (default: 100)")
    
    # Connection
    parser.add_argument("--gpib-address", type=str, default="GPIB0::22::INSTR",
                       help="GPIB address (default: GPIB0::22::INSTR)")
    parser.add_argument("--timeout", type=float, default=120.0,
                       help="Timeout in seconds (default: 120.0)")
    
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
    
    # Calculate number of sweep points
    num_sweep_pts = int(abs((args.stop_v_ch2 - args.start_v_ch2) / args.step_v_ch2) + 1)
    
    command = build_ex_command(
        pulse_width_ch1=args.pulse_width_ch1,
        rise_time_ch1=args.rise_time_ch1,
        fall_time_ch1=args.fall_time_ch1,
        delay_ch1=args.delay_ch1,
        pulse_width_ch2=args.pulse_width_ch2,
        rise_time_ch2=args.rise_time_ch2,
        fall_time_ch2=args.fall_time_ch2,
        delay_ch2=args.delay_ch2,
        period=args.period,
        pulse_average=args.pulse_average,
        load_line_ch1=args.load_line_ch1,
        load_line_ch2=args.load_line_ch2,
        res_ch1=args.res_ch1,
        res_ch2=args.res_ch2,
        ampl_v_ch1=args.ampl_v_ch1,
        base_v_ch1=args.base_v_ch1,
        start_v_ch2=args.start_v_ch2,
        stop_v_ch2=args.stop_v_ch2,
        step_v_ch2=args.step_v_ch2,
        base_v_ch2=args.base_v_ch2,
        v_range_ch1=args.v_range_ch1,
        i_range_ch1=args.i_range_ch1,
        ltd_auto_curr_ch1=args.ltd_auto_curr_ch1,
        v_range_ch2=args.v_range_ch2,
        i_range_ch2=args.i_range_ch2,
        ltd_auto_curr_ch2=args.ltd_auto_curr_ch2,
        pmu_mode=args.pmu_mode,
        smu_irange=args.smu_irange,
        smu_icomp=args.smu_icomp,
        ch1_smu_id=args.ch1_smu_id,
        ch2_smu_id=args.ch2_smu_id,
        pmu_id=args.pmu_id,
        exec_mode=args.exec_mode,
        array_size=args.array_size,
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
    print("ACraig12 PMU+SMU Sweep Runner - Starting")
    print("="*80)
    print(f"[Auto] Number of sweep points: {num_sweep_pts}")
    print(f"[Auto] array_size set to {args.array_size}")
    
    print("="*80)
    print("[DEBUG] Generated EX command:")
    print("="*80)
    print(command)
    print("="*80)
    
    controller = KXCIClient(gpib_address=args.gpib_address, timeout=args.timeout)
    
    try:
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        exec_mode_names = {0: "Pulse+SMU", 1: "Pulse only", 2: "SMU only"}
        print(f"\n[KXCI] Execution mode: {args.exec_mode} ({exec_mode_names[args.exec_mode]})")
        
        if args.exec_mode in [0, 1]:
            print(f"[KXCI] PMU Pulse Test:")
            print(f"  CH1: Fixed amplitude {args.ampl_v_ch1}V (base {args.base_v_ch1}V)")
            print(f"  CH2: Sweep {args.start_v_ch2}V to {args.stop_v_ch2}V (base {args.base_v_ch2}V)")
            print(f"  Period: {args.period*1e6:.2f}µs, Pulse average: {args.pulse_average}")
        
        if args.exec_mode in [0, 2]:
            print(f"[KXCI] SMU DC Test:")
            print(f"  CH1 SMU: Fixed bias {args.ampl_v_ch1}V")
            print(f"  CH2 SMU: Sweep {args.start_v_ch2}V to {args.stop_v_ch2}V")
        
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
        num_points = min(args.array_size, num_sweep_pts)
        print(f"[KXCI] Requesting {num_points} points")
        
        # Retrieve PMU data if pulse test was performed
        if args.exec_mode in [0, 1]:
            print("\n[KXCI] Retrieving PMU pulse data...")
            ch1_v_ampl = controller.safe_query(34, num_points, "Ch1_V_Ampl")
            ch1_i_ampl = controller.safe_query(36, num_points, "Ch1_I_Ampl")
            ch1_v_base = controller.safe_query(38, num_points, "Ch1_V_Base")
            ch1_i_base = controller.safe_query(40, num_points, "Ch1_I_Base")
            ch2_v_ampl = controller.safe_query(42, num_points, "Ch2_V_Ampl")
            ch2_i_ampl = controller.safe_query(44, num_points, "Ch2_I_Ampl")
            ch2_v_base = controller.safe_query(46, num_points, "Ch2_V_Base")
            ch2_i_base = controller.safe_query(48, num_points, "Ch2_I_Base")
            
            print(f"[KXCI] PMU data: CH1 ampl={len(ch1_v_ampl)} pts, CH2 ampl={len(ch2_v_ampl)} pts")
        
        # Retrieve SMU data if DC test was performed
        if args.exec_mode in [0, 2]:
            print("\n[KXCI] Retrieving SMU DC data...")
            ch2_smu_voltage = controller.safe_query(62, num_points, "Ch2_SMU_Voltage")
            ch2_smu_current = controller.safe_query(64, num_points, "Ch2_SMU_Current")
            ch1_smu_voltage = controller.safe_query(66, num_points, "Ch1_SMU_Voltage")
            ch1_smu_current = controller.safe_query(68, num_points, "Ch1_SMU_Current")
            
            print(f"[KXCI] SMU data: CH1={len(ch1_smu_voltage)} pts, CH2={len(ch2_smu_voltage)} pts")
        
        # Print summary
        print(f"\n[Summary]")
        if args.exec_mode in [0, 1]:
            if ch1_v_ampl:
                print(f"  CH1 Pulse Ampl: {len(ch1_v_ampl)} points, V range: {min(ch1_v_ampl):.6g} to {max(ch1_v_ampl):.6g} V")
            if ch2_v_ampl:
                print(f"  CH2 Pulse Ampl: {len(ch2_v_ampl)} points, V range: {min(ch2_v_ampl):.6g} to {max(ch2_v_ampl):.6g} V")
        if args.exec_mode in [0, 2]:
            if ch2_smu_voltage:
                print(f"  CH2 SMU: {len(ch2_smu_voltage)} points, V range: {min(ch2_smu_voltage):.6g} to {max(ch2_smu_voltage):.6g} V")
        
        # Plot if requested
        if enable_plot and PLOTTING_AVAILABLE:
            if args.exec_mode in [0, 1] and ch2_v_ampl and ch2_i_ampl:
                # Plot PMU IV curve
                fig1, ax1 = plt.subplots(1, 1, figsize=(8, 6))
                ax1.plot(ch2_v_ampl, ch2_i_ampl, 'b-', linewidth=1.5, label='CH2 Pulse Ampl')
                ax1.set_xlabel('Voltage (V)')
                ax1.set_ylabel('Current (A)')
                ax1.set_title('PMU Pulse IV Curve (CH2 Amplitude)')
                ax1.grid(True)
                ax1.legend()
                plt.tight_layout()
                plt.show()
            
            if args.exec_mode in [0, 2] and ch2_smu_voltage and ch2_smu_current:
                # Plot SMU IV curve
                fig2, ax2 = plt.subplots(1, 1, figsize=(8, 6))
                ax2.plot(ch2_smu_voltage, ch2_smu_current, 'r-', linewidth=1.5, label='CH2 SMU DC')
                ax2.set_xlabel('Voltage (V)')
                ax2.set_ylabel('Current (A)')
                ax2.set_title('SMU DC IV Curve (CH2)')
                ax2.grid(True)
                ax2.legend()
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



