"""
PMU Pulse-Read Interleaved with Baseline Bias (0.5 V -> 1.5 V -> 0.5 V)
========================================================================

This variant keeps a constant baseline (meas_v) before/after the pulse rather than
returning to 0 V. Use when you want to hold the device at a read/bias level (e.g., 0.5 V),
apply a higher pulse (e.g., 1.5 V), then return to the same bias.

IMPORTANT: The underlying C UL program (pmu_pulse_read_interleaved.c) currently
hard-codes returns to 0 V. To truly hold at meas_v before/after pulses, that C code
must be modified to use meas_v as the baseline in its volts[] assignments.
This Python wrapper only builds and sends the EX command; it cannot change the
instrument waveform shape by itself.

Usage (programmatic):
    from pmu_pulse_read_interleaved_bias import PulseReadInterleavedConfigBias, run_measurement_bias
    cfg = PulseReadInterleavedConfigBias(
        meas_v=0.5,
        pulse_v=1.5,
        num_cycles=1,
        num_reads=1,
        num_pulses_per_group=1,
    )
    cfg.validate()
    run_measurement_bias(cfg, address="GPIB0::17::INSTR", timeout=30.0, enable_plot=True)

Command-line example:
    python pmu_pulse_read_interleaved_bias.py --gpib-address GPIB0::17::INSTR \
        --meas-v 0.5 --pulse-v 1.5 --num-cycles 1 --num-reads 1 --num-pulses-per-group 1
"""

from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


class KXCIClient:
    """Minimal KXCI helper for sending EX/GP commands over GPIB."""

    def __init__(self, gpib_address: str, timeout: float) -> None:
        self.gpib_address = gpib_address
        self.timeout_ms = int(timeout * 1000)
        self.rm = None
        self.inst = None
        self._ul_mode_active = False

    def connect(self) -> bool:
        try:
            import pyvisa
        except ImportError as exc:  # noqa: F401
            raise RuntimeError("pyvisa is required to communicate with the instrument") from exc

        try:
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(self.gpib_address)
            self.inst.timeout = self.timeout_ms
            self.inst.write_termination = "\n"
            self.inst.read_termination = "\n"
            idn = self.inst.query("*IDN?").strip()
            print(f"✓ Connected to: {idn}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Connection failed: {exc}")
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
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def _safe_read(self) -> str:
        if self.inst is None:
            return ""
        try:
            return self.inst.read()
        except Exception:  # noqa: BLE001
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
    """Format a parameter exactly as expected by KXCI EX commands."""
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


@dataclass
class PulseReadInterleavedConfigBias:
    rise_time: float = 1e-7
    reset_v: float = 0.5
    reset_width: float = 1e-6
    reset_delay: float = 1.0   # max allowed by C validation (seconds)
    meas_v: float = 0.2        # baseline bias
    meas_width: float = 1e-6
    meas_delay: float = 1.0    # max allowed by C validation (seconds)
    set_width: float = 1e-6
    set_fall_time: float = 1e-7
    set_delay: float = 1e-6
    set_start_v: float = 0.5
    set_stop_v: float = 0.5
    steps: int = 0
    i_range: float = 1e-4
    max_points: int = 10000
    iteration: int = 2
    out1_name: str = "VF"
    out2_name: str = "T"
    out2_size: int = 200
    num_cycles: int = 1               # single cycle
    num_reads: int = 1                # single read
    num_pulses_per_group: int = 1     # single pulse
    pulse_width: float = 1.0          # max allowed (C limits to 1s)
    pulse_v: float = 2.0              # pulse top
    pulse_rise_time: float = 1e-7
    pulse_fall_time: float = 1e-7
    pulse_delay: float = 1.0          # hold baseline after pulse (max allowed)
    clarius_debug: int = 1

    def total_probe_count(self) -> int:
        return 1 + self.num_cycles * self.num_reads

    def validate(self) -> None:
        limits: Dict[str, tuple[float, float]] = {
            "rise_time": (2e-8, 1.0),
            "reset_v": (-20.0, 20.0),
            "reset_width": (2e-8, 1.0),
            "reset_delay": (2e-8, 1.0),
            "meas_v": (-20.0, 20.0),
            "meas_width": (2e-8, 1.0),
            "meas_delay": (2e-8, 1.0),
            "set_width": (2e-8, 1.0),
            "set_fall_time": (2e-8, 1.0),
            "set_delay": (2e-8, 1.0),
            "set_start_v": (-20.0, 20.0),
            "set_stop_v": (-20.0, 20.0),
            "i_range": (100e-9, 0.8),
            "max_points": (12, 1_000_000),
        }
        for field_name, (lo, hi) in limits.items():
            value = getattr(self, field_name)
            if value < lo or value > hi:
                raise ValueError(f"{field_name}={value} outside [{lo}, {hi}]")
        if not (1 <= self.num_cycles <= 100):
            raise ValueError("num_cycles must be within [1, 100]")
        if not (1 <= self.num_reads <= 100):
            raise ValueError("num_reads must be within [1, 100]")
        if not (1 <= self.num_pulses_per_group <= 100):
            raise ValueError("num_pulses_per_group must be within [1, 100]")
        if not (2e-8 <= self.pulse_width <= 1.0):
            raise ValueError("pulse_width must be within [2e-8, 1.0]")
        if not (-20.0 <= self.pulse_v <= 20.0):
            raise ValueError("pulse_v must be within [-20.0, 20.0]")
        if not (2e-8 <= self.pulse_rise_time <= 1.0):
            raise ValueError("pulse_rise_time must be within [2e-8, 1.0]")
        if not (2e-8 <= self.pulse_fall_time <= 1.0):
            raise ValueError("pulse_fall_time must be within [2e-8, 1.0]")
        if not (2e-8 <= self.pulse_delay <= 1.0):
            raise ValueError("pulse_delay must be within [2e-8, 1.0]")
        if self.clarius_debug not in (0, 1):
            raise ValueError("clarius_debug must be 0 or 1")
        if self.out2_size < 1:
            raise ValueError("out2_size must be positive")
        if self.steps < 0:
            raise ValueError("steps must be >= 0")


def build_ex_command_bias(cfg: PulseReadInterleavedConfigBias) -> str:
    """
    Build EX command for the bias-hold variant. This still calls the same C UL program name,
    but we reinterpret parameters to keep baseline at meas_v. If the C module itself forces
    0 V, this wrapper won't override it without changing the C code. This wrapper is intended
    for a C variant that uses meas_v as baseline (0.5 V → 1.5 V → 0.5 V).
    """
    total_probes = cfg.total_probe_count()
    common_size = total_probes

    params = [
        format_param(cfg.rise_time),
        format_param(cfg.reset_v),
        format_param(cfg.reset_width),
        format_param(cfg.reset_delay),
        format_param(cfg.meas_v),
        format_param(cfg.meas_width),
        format_param(cfg.meas_delay),
        format_param(cfg.set_width),
        format_param(cfg.set_fall_time),
        format_param(cfg.set_delay),
        format_param(cfg.set_start_v),
        format_param(cfg.set_stop_v),
        format_param(cfg.steps),
        format_param(cfg.i_range),
        format_param(cfg.max_points),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        format_param(cfg.iteration),
        "",
        format_param(common_size),
        cfg.out1_name,
        "",
        format_param(cfg.out2_size),
        cfg.out2_name,
        "",
        format_param(common_size),
        format_param(cfg.num_pulses_per_group),
        format_param(cfg.num_cycles),
        format_param(cfg.num_reads),
        format_param(cfg.pulse_width),
        format_param(cfg.pulse_v),
        format_param(cfg.pulse_rise_time),
        format_param(cfg.pulse_fall_time),
        format_param(cfg.pulse_delay),
        format_param(cfg.clarius_debug),
    ]

    # NOTE: This still calls the same C entry point. For true baseline-at-meas_v behavior,
    # the C UL program must honor meas_v as baseline instead of 0 V.
    return f"EX a_bias_pulse pmu_pulse_read_interleaved_bias({','.join(params)})"


def _compute_probe_times(cfg: PulseReadInterleavedConfigBias) -> List[float]:
    ratio = 0.4
    ttime = 0.0
    centres: List[float] = []

    def add_measurement(start_time: float) -> None:
        centres.append(start_time + cfg.meas_width * (ratio + 0.9) / 2.0)

    ttime += cfg.reset_delay
    ttime += cfg.rise_time

    ttime += cfg.rise_time
    add_measurement(ttime)
    ttime += cfg.meas_width
    ttime += cfg.set_fall_time
    ttime += cfg.rise_time
    ttime += cfg.meas_delay

    for _ in range(cfg.num_cycles):
        for _ in range(cfg.num_pulses_per_group):
            ttime += cfg.pulse_rise_time
            ttime += cfg.pulse_width
            ttime += cfg.pulse_fall_time
            ttime += cfg.pulse_delay
        for _ in range(cfg.num_reads):
            ttime += cfg.rise_time
            add_measurement(ttime)
            ttime += cfg.meas_width
            ttime += cfg.set_fall_time
            ttime += cfg.rise_time
            ttime += cfg.meas_delay

    return centres


def run_measurement_bias(cfg: PulseReadInterleavedConfigBias, address: str, timeout: float, enable_plot: bool) -> None:
    command = build_ex_command_bias(cfg)
    total_probes = cfg.total_probe_count()

    controller = KXCIClient(gpib_address=address, timeout=timeout)

    try:
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")

        print("\n[KXCI] Generated EX command (bias variant):")
        print(command)

        if not controller._enter_ul_mode():  # pylint: disable=protected-access
            raise RuntimeError("Failed to enter UL mode")

        return_value, error = controller._execute_ex_command(command)  # pylint: disable=protected-access
        if error:
            raise RuntimeError(error)
        if return_value is not None:
            print(f"Return value: {return_value}")

        print("\n[KXCI] Retrieving data...")

        def safe_query(param: int, count: int) -> List[float]:
            return controller._query_gp(param, count)  # pylint: disable=protected-access

        param18 = safe_query(18, 1)
        if param18:
            print(f"Param 18 value: {param18[0]}")

        set_v = safe_query(20, total_probes)
        set_i = safe_query(22, total_probes)
        out1 = safe_query(25, total_probes)
        pulse_times = safe_query(31, total_probes)

        if not pulse_times:
            pulse_times = _compute_probe_times(cfg)
        if len(pulse_times) != total_probes:
            pulse_times = [float(index) for index in range(total_probes)]

        resistance: List[float] = []
        for voltage, current in zip(set_v, set_i):
            if abs(current) < 1e-12:
                resistance.append(float("inf"))
            else:
                resistance.append(voltage / current)

        try:
            import pandas as pd  # type: ignore
            print("\nMeasurement Results:")
            df = pd.DataFrame(
                {
                    "probe": range(total_probes),
                    "time_s": pulse_times,
                    "voltage_V": set_v,
                    "current_A": set_i,
                    "resistance_ohm": resistance,
                    cfg.out1_name: out1,
                }
            )
            print(df.to_string(index=False))

            if enable_plot:
                try:
                    import matplotlib.pyplot as plt  # type: ignore
                    plt.figure(figsize=(8, 4))
                    plt.plot(df["time_s"], df["resistance_ohm"], marker="o")
                    plt.xlabel("Time (s)")
                    plt.ylabel("Resistance (Ohm)")
                    plt.title(
                        f"PMU Pulse-Read Interleaved (Bias): "
                        f"{cfg.num_cycles} cycles, {cfg.num_reads} reads/cycle, {cfg.num_pulses_per_group} pulses/cycle"
                    )
                    plt.grid(True)
                    plt.tight_layout()
                    plt.show()
                except Exception as exc:  # noqa: BLE001
                    print(f"\n⚠️ Unable to display plot: {exc}")
        except ImportError:
            print("\nPandas not available; printing raw arrays.")
            for label, values in (
                ("probe", list(range(total_probes))),
                ("time_s", pulse_times),
                ("voltage_V", set_v),
                ("current_A", set_i),
                ("resistance_ohm", resistance),
                (cfg.out1_name, out1),
            ):
                print(f"\n{label}:")
                for idx, val in enumerate(values):
                    print(f"  {idx:02d}: {val}")

    finally:
        try:
            controller._exit_ul_mode()  # pylint: disable=protected-access
        except Exception:  # noqa: BLE001
            pass
        controller.disconnect()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and optionally run PMU pulse-read interleaved (bias) command")
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR", help="VISA resource string")
    parser.add_argument("--timeout", type=float, default=30.0, help="Visa timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only print the command")
    parser.add_argument("--no-plot", action="store_true", help="Disable resistance plot even if matplotlib is available")

    # Read/baseline parameters
    parser.add_argument("--rise-time", type=float, default=3e-8, help="Rise/fall time for read pulses (seconds)")
    parser.add_argument("--meas-v", type=float, default=0.2, help="Baseline/read voltage (volts)")
    parser.add_argument("--meas-width", type=float, default=0.5e-6, help="Read pulse width (seconds)")
    parser.add_argument("--meas-delay", type=float, default=1.0, help="Delay after read (seconds, max 1.0)")
    parser.add_argument("--set-fall-time", type=float, default=1e-7, help="Settling time at meas-v before fall (seconds)")

    # Pulse parameters
    parser.add_argument("--pulse-v", type=float, default=2.0, help="Pulse voltage amplitude (volts)")
    parser.add_argument("--pulse-width", type=float, default=1.0, help="Pulse width (seconds, max 1.0)")
    parser.add_argument("--pulse-rise-time", type=float, default=3e-8, help="Pulse rise time (seconds)")
    parser.add_argument("--pulse-fall-time", type=float, default=3e-8, help="Pulse fall time (seconds)")
    parser.add_argument("--pulse-delay", type=float, default=1.0, help="Delay after each pulse (seconds, max 1.0)")

    # Pattern
    parser.add_argument("--num-cycles", type=int, default=1, help="Number of cycles (M)")
    parser.add_argument("--num-reads", type=int, default=1, help="Number of reads per cycle (N)")
    parser.add_argument("--num-pulses-per-group", type=int, default=1, help="Number of pulses per cycle")

    # Instrument/config
    parser.add_argument("--i-range", type=float, default=0.01, help="Current range (amps)")
    parser.add_argument("--max-points", type=int, default=10000, help="Maximum data points per channel")
    parser.add_argument("--iteration", type=int, default=1, help="Iteration number")

    # Outputs
    parser.add_argument("--out1-name", default="VF", help="Output 1 name (VF, IF, VM, IM, or T)")
    parser.add_argument("--out2-name", default="T", help="Output 2 name (VF, IF, VM, IM, or T)")
    parser.add_argument("--out2-size", type=int, default=200, help="Output 2 array size")

    # Debug
    parser.add_argument("--clarius-debug", type=int, choices=[0, 1], default=1, help="Enable debug output")

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    cfg = PulseReadInterleavedConfigBias(
        rise_time=args.rise_time,
        reset_v=args.meas_v,
        reset_width=1e-6,
        reset_delay=5e-7,
        meas_v=args.meas_v,
        meas_width=args.meas_width,
        meas_delay=args.meas_delay,
        set_width=1e-6,
        set_fall_time=args.set_fall_time,
        set_delay=1e-6,
        set_start_v=args.meas_v,
        set_stop_v=args.meas_v,
        steps=0,
        i_range=args.i_range,
        max_points=args.max_points,
        iteration=args.iteration,
        out1_name=args.out1_name,
        out2_name=args.out2_name,
        out2_size=args.out2_size,
        num_cycles=args.num_cycles,
        num_reads=args.num_reads,
        num_pulses_per_group=args.num_pulses_per_group,
        pulse_width=args.pulse_width,
        pulse_v=args.pulse_v,
        pulse_rise_time=args.pulse_rise_time,
        pulse_fall_time=args.pulse_fall_time,
        pulse_delay=args.pulse_delay,
        clarius_debug=args.clarius_debug,
    )

    cfg.validate()
    command = build_ex_command_bias(cfg)
    print("Generated EX command (bias variant):\n" + command)

    if args.dry_run:
        return

    run_measurement_bias(cfg, address=args.gpib_address, timeout=args.timeout, enable_plot=not args.no_plot)


if __name__ == "__main__":
    main()


