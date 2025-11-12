"""Read-train PMU waveform generator and runner.

This script builds the `EX +24 ACraig5_PMU_retention(...)` command,
optionally executes it on a Keithley 4200A via KXCI, and prints the averaged
voltage/current returned for each read probe.  The call targets the updated
ACraig5 modules where the initial excitation pulse has been converted into an
additional read, yielding a continuous train of measurement windows.  When
requested, the flow arms the new wait gate so the measurement can pause until
the user explicitly sends a ready signal, preventing stray TTLs during setup.
"""

from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


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
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


@dataclass
class ReadTrainConfig:
    rise_time: float = 1e-7
    meas_v: float = 0.3
    meas_width: float = 1e-6
    meas_delay: float = 2e-6
    num_pulses: int = 50
    trigger_pulse: int = 1  # retained for CLI compatibility (unused by ACraig modules)
    i_range: float = 1e-4
    max_points: int = 10000
    out1_name: str = "VF"
    out2_name: str = "IM"
    iteration: int = 1
    clarius_debug: int = 0

    def probe_capacity(self) -> int:
        """Total number of probe windows returned by ACraig5 (baseline + extra read + pulses)."""

        return self.num_pulses + 2

    def validate(self) -> None:
        limits: Dict[str, tuple[float, float]] = {
            "rise_time": (2e-8, 1.0),
            "meas_v": (-20.0, 20.0),
            "meas_width": (2e-8, 1.0),
            "meas_delay": (2e-8, 1.0),
            "i_range": (100e-9, 0.8),
            "max_points": (12, 30000),
        }

        for field, (lo, hi) in limits.items():
            value = getattr(self, field)
            if value < lo or value > hi:
                raise ValueError(f"{field}={value} outside [{lo}, {hi}]")

        if self.num_pulses < 2 or self.num_pulses > 1000:
            raise ValueError("num_pulses must be within [2, 1000]")
        if self.clarius_debug not in (0, 1):
            raise ValueError("clarius_debug must be 0 or 1")


def build_ex_command(cfg: ReadTrainConfig, module_prefix: str) -> str:
    probe_capacity = cfg.probe_capacity()
    reset_v = cfg.meas_v
    reset_width = cfg.meas_width
    reset_delay = cfg.meas_delay
    set_width = cfg.meas_width
    set_fall_time = cfg.rise_time
    set_delay = cfg.meas_delay
    set_start_v = cfg.meas_v
    set_stop_v = cfg.meas_v
    steps = 1

    params = [
        format_param(cfg.rise_time),          # riseTime
        format_param(reset_v),                # resetV
        format_param(reset_width),            # resetWidth
        format_param(reset_delay),            # resetDelay
        format_param(cfg.meas_v),             # measV
        format_param(cfg.meas_width),         # measWidth
        format_param(cfg.meas_delay),         # measDelay
        format_param(set_width),              # setWidth
        format_param(set_fall_time),          # setFallTime
        format_param(set_delay),              # setDelay
        format_param(set_start_v),            # setStartV
        format_param(set_stop_v),             # setStopV
        format_param(steps),                  # steps
        format_param(cfg.i_range),            # IRange
        format_param(cfg.max_points),         # max_points
        "",                                   # setR
        format_param(probe_capacity),         # setR_size
        "",                                   # resetR
        format_param(probe_capacity),         # resetR_size
        "",                                   # setV
        format_param(probe_capacity),         # setV_size
        "",                                   # setI
        format_param(probe_capacity),         # setI_size
        format_param(cfg.iteration),          # iteration
        "",                                   # out1
        format_param(probe_capacity),         # out1_size
        cfg.out1_name,                        # out1_name
        "",                                   # out2
        format_param(probe_capacity),         # out2_size
        cfg.out2_name,                        # out2_name
        "",                                   # PulseTimes
        format_param(probe_capacity),         # PulseTimesSize
        format_param(cfg.num_pulses),         # NumbMeasPulses
        format_param(cfg.clarius_debug),      # ClariusDebug
    ]

    return f"EX {module_prefix} {module_prefix}_PMU_retention({','.join(params)})"


def _compute_probe_times(cfg: ReadTrainConfig) -> List[float]:
    ratio = 0.4
    ttime = 0.0
    centres: List[float] = []

    def add_probe(current_t: float) -> None:
        centres.append(current_t + cfg.meas_width * (ratio + 0.9) / 2.0)

    # Initial baseline measurement pulse
    ttime += cfg.meas_delay  # times[0]
    ttime += cfg.rise_time   # times[1]
    add_probe(ttime)
    ttime += cfg.meas_width  # times[2]
    ttime += cfg.rise_time   # times[3]
    ttime += cfg.meas_delay  # times[4]
    ttime += cfg.rise_time   # times[5]
    ttime += cfg.rise_time   # times[6]

    # Second measurement pulse (converted reset)
    ttime += cfg.rise_time   # times[7]
    add_probe(ttime)
    ttime += cfg.meas_width  # times[8]
    ttime += cfg.rise_time   # times[9]
    ttime += cfg.meas_delay  # times[10]
    ttime += cfg.rise_time   # times[11]

    # Third measurement pulse
    ttime += cfg.rise_time   # times[12]
    add_probe(ttime)
    ttime += cfg.meas_width  # times[13]
    ttime += cfg.rise_time   # times[14]
    ttime += cfg.meas_delay  # times[15]

    # Fourth measurement pulse
    ttime += cfg.rise_time   # times[16]
    add_probe(ttime)
    ttime += cfg.meas_width  # times[17]
    ttime += cfg.rise_time   # times[18]
    ttime += cfg.meas_delay  # times[19]

    # Remaining measurement pulses
    for _ in range(max(cfg.num_pulses - 2, 0)):
        ttime += cfg.rise_time
        add_probe(ttime)
        ttime += cfg.meas_width
        ttime += cfg.rise_time
        ttime += cfg.meas_delay

    return centres


def run_measurement(
    cfg: ReadTrainConfig,
    address: str,
    timeout: float,
    enable_plot: bool,
    module_prefix: str,
    wait_for_ready: bool,
) -> None:
    command = build_ex_command(cfg, module_prefix)
    probe_capacity = cfg.probe_capacity()

    controller = KXCIClient(gpib_address=address, timeout=timeout)

    try:
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")

        print("\n[KXCI] Generated EX command:")
        print(command)

        if not controller._enter_ul_mode():  # pylint: disable=protected-access
            raise RuntimeError("Failed to enter UL mode")

        wait_mode_command = f"EX {module_prefix} {module_prefix}_wait_mode({format_param(1)})"
        wait_disable_command = f"EX {module_prefix} {module_prefix}_wait_mode({format_param(0)})"
        wait_ready_command = f"EX {module_prefix} {module_prefix}_wait_signal({format_param(1)})"

        wait_mode_sent = False
        if wait_for_ready:
            return_value, error = controller._execute_ex_command(wait_mode_command)  # pylint: disable=protected-access
            wait_mode_sent = error is None
            if error:
                raise RuntimeError(f"Failed to arm wait gate: {error}")

            print("\n[ACraig5] Waveform armed. Type 'go' to start or 'abort' to cancel.")
            while True:
                user_input = input("  ready> ").strip().lower()
                if user_input in ("", "go", "g", "start"):
                    break
                if user_input in ("abort", "a", "cancel", "quit", "exit"):
                    if wait_mode_sent:
                        controller._execute_ex_command(wait_disable_command)  # pylint: disable=protected-access
                    print("\nMeasurement cancelled before execution.")
                    return
                print("  Please respond with 'go' (Enter) or 'abort'.")

            return_value, error = controller._execute_ex_command(wait_ready_command)  # pylint: disable=protected-access
            if error:
                raise RuntimeError(f"Failed to release wait gate: {error}")

        return_value, error = controller._execute_ex_command(command)  # pylint: disable=protected-access
        if error:
            raise RuntimeError(error)
        if return_value is not None:
            print(f"Return value: {return_value}")

        print("\n[KXCI] Retrieving data...")

        def safe_query(param: int, count: int) -> List[float]:
            return controller._query_gp(param, count)  # pylint: disable=protected-access

        read_v = safe_query(20, probe_capacity)
        read_i = safe_query(22, probe_capacity)
        pulse_times = safe_query(31, probe_capacity)

        if not pulse_times:
            pulse_times = _compute_probe_times(cfg)

        if len(pulse_times) < len(read_v):
            fallback = _compute_probe_times(cfg)
            if fallback:
                pulse_times = (pulse_times + fallback)[0:len(read_v)]

        def trim_records(times: List[float], voltages: List[float], currents: List[float]) -> tuple[List[float], List[float], List[float]]:
            usable = min(len(times), len(voltages), len(currents))
            last_valid = usable
            for idx in range(usable - 1, -1, -1):
                if times[idx] > 0.0 or abs(voltages[idx]) > 1e-15 or abs(currents[idx]) > 1e-15:
                    last_valid = idx + 1
                    break
            return times[:last_valid], voltages[:last_valid], currents[:last_valid]

        pulse_times, read_v, read_i = trim_records(pulse_times, read_v, read_i)

        if not pulse_times:
            pulse_times = _compute_probe_times(cfg)
            pulse_times, read_v, read_i = trim_records(pulse_times, read_v, read_i)

        resistance: List[float] = []
        for v, i_cur in zip(read_v, read_i):
            if abs(i_cur) < 1e-12:
                resistance.append(float("inf"))
            else:
                resistance.append(v / i_cur)

        valid_count = min(len(pulse_times), len(read_v), len(read_i), len(resistance))
        pulse_times = pulse_times[:valid_count]
        read_v = read_v[:valid_count]
        read_i = read_i[:valid_count]
        resistance = resistance[:valid_count]

        print(f"\n[KXCI] Collected {valid_count} probe windows.")

        try:
            import pandas as pd  # type: ignore

            df = pd.DataFrame(
                {
                    "pulse": range(1, len(pulse_times) + 1),
                    "time_s": pulse_times,
                    "voltage_V": read_v,
                    "current_A": read_i,
                    "resistance_ohm": resistance,
                }
            )

            print("\nMeasurement Results:")
            print(df.to_string(index=False))

            if enable_plot:
                try:
                    import matplotlib.pyplot as plt  # type: ignore

                    plt.figure(figsize=(8, 4))
                    plt.plot(df["time_s"], df["resistance_ohm"], marker="o")
                    plt.xlabel("Time (s)")
                    plt.ylabel("Resistance (Ohm)")
                    plt.title("PMU Read Train Resistance vs Time")
                    plt.grid(True)
                    plt.tight_layout()
                    plt.show()
                except Exception as exc:  # noqa: BLE001
                    print(f"\n⚠️ Unable to display plot: {exc}")
        except ImportError:
            print("\nPandas not available; printing raw arrays.")
            for label, values in (
                ("pulse", list(range(1, len(pulse_times) + 1))),
                ("time_s", pulse_times),
                ("voltage_V", read_v),
                ("current_A", read_i),
                ("resistance_ohm", resistance),
            ):
                print(f"\n{label}:")
                for idx, val in enumerate(values):
                    print(f"  {idx + 1:02d}: {val}")

    finally:
        try:
            if wait_for_ready:
                controller._execute_ex_command(wait_disable_command)  # pylint: disable=protected-access
            controller._exit_ul_mode()  # pylint: disable=protected-access
        except Exception:  # noqa: BLE001
            pass
        controller.disconnect()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate/run ACraig5_PMU_retention read-train")

    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR", help="VISA resource string")
    parser.add_argument("--timeout", type=float, default=30.0, help="Visa timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only print the EX command")
    parser.add_argument("--no-plot", action="store_true", help="Disable plotting even if matplotlib is present")
    parser.add_argument("--module-prefix", choices=["ACraig4", "ACraig5"], default="ACraig5", help="UL library prefix to target")
    parser.add_argument("--no-wait", action="store_true", help="Execute immediately without waiting for manual ready signal")

    parser.add_argument("--rise-time", type=float, default=1e-7)
    parser.add_argument("--meas-v", type=float, default=1.5)
    parser.add_argument("--meas-width", type=float, default=1e-6)
    parser.add_argument("--meas-delay", type=float, default=2e-6)
    parser.add_argument("--num-pulses", type=int, default=50)
    parser.add_argument("--trigger-pulse", type=int, default=1)
    parser.add_argument("--i-range", type=float, default=1e-4)
    parser.add_argument("--max-points", type=int, default=10000)
    parser.add_argument("--out1-name", default="VF")
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--clarius-debug", type=int, choices=[0, 1], default=1)

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    cfg = ReadTrainConfig(
        rise_time=args.rise_time,
        meas_v=args.meas_v,
        meas_width=args.meas_width,
        meas_delay=args.meas_delay,
        num_pulses=args.num_pulses,
        trigger_pulse=args.trigger_pulse,
        i_range=args.i_range,
        max_points=args.max_points,
        out1_name=args.out1_name,
        out2_name="IM",
        iteration=args.iteration,
        clarius_debug=args.clarius_debug,
    )

    cfg.validate()

    if args.trigger_pulse != 1:
        print(f"⚠️ trigger_pulse is ignored by {args.module_prefix}_PMU_retention; keeping value for compatibility.")

    command = build_ex_command(cfg, args.module_prefix)
    print("Generated EX command:\n" + command)

    if args.dry_run:
        return

    wait_for_ready = args.module_prefix == "ACraig5" and not args.no_wait
    if args.module_prefix == "ACraig4" and not args.no_wait:
        print("⚠️ Wait gate disabled because ACraig4 library does not expose the control modules.")
    run_measurement(
        cfg,
        address=args.gpib_address,
        timeout=args.timeout,
        enable_plot=not args.no_plot,
        module_prefix=args.module_prefix,
        wait_for_ready=wait_for_ready,
    )


if __name__ == "__main__":
    main()


