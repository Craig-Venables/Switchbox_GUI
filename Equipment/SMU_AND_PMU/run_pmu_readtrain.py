"""Read-train PMU waveform generator and runner.

This script builds the `EX ACraig2 ACraig1_PMU_readtrain(...)` command,
optionally executes it on a Keithley 4200A via KXCI, and prints the averaged
voltage/current returned for each read probe.  The script mirrors the helper in
`ACraig1_PMU_readtrain.c` and provides defaults plus CLI overrides.
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
    trigger_pulse: int = 1
    i_range: float = 1e-4
    max_points: int = 10000
    out1_name: str = "VF"
    iteration: int = 1
    clarius_debug: int = 0

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

        if not (1 <= self.num_pulses <= 200):
            raise ValueError("num_pulses must be within [1, 200]")
        if not (1 <= self.trigger_pulse <= self.num_pulses):
            raise ValueError("trigger_pulse must be within [1, num_pulses]")
        if self.clarius_debug not in (0, 1):
            raise ValueError("clarius_debug must be 0 or 1")


def build_ex_command(cfg: ReadTrainConfig) -> str:
    params = [
        format_param(cfg.rise_time),
        format_param(cfg.meas_v),
        format_param(cfg.meas_width),
        format_param(cfg.meas_delay),
        format_param(cfg.num_pulses),
        format_param(cfg.trigger_pulse),
        format_param(cfg.i_range),
        format_param(cfg.max_points),
        "",  # readV output
        format_param(cfg.num_pulses),
        "",  # readI output
        format_param(cfg.num_pulses),
        "",  # PulseTimes output
        format_param(cfg.num_pulses),
        "",  # out1 output
        format_param(cfg.num_pulses),
        cfg.out1_name,
        format_param(cfg.iteration),
        format_param(cfg.clarius_debug),
    ]

    return f"EX ACraig2 ACraig1_PMU_readtrain({','.join(params)})"


def _compute_probe_times(cfg: ReadTrainConfig) -> List[float]:
    ttime = cfg.meas_delay
    centres: List[float] = []
    window_low = 0.5
    window_high = 0.7

    for _ in range(cfg.num_pulses):
        ttime += cfg.rise_time
        centres.append(ttime + cfg.meas_width * (window_low + window_high) / 2.0)
        ttime += cfg.meas_width
        ttime += cfg.rise_time
        ttime += cfg.meas_delay

    return centres


def run_measurement(cfg: ReadTrainConfig, address: str, timeout: float, enable_plot: bool) -> None:
    command = build_ex_command(cfg)
    total_pulses = cfg.num_pulses

    controller = KXCIClient(gpib_address=address, timeout=timeout)

    try:
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")

        print("\n[KXCI] Generated EX command:")
        print(command)

        if not controller._enter_ul_mode():  # pylint: disable=protected-access
            raise RuntimeError("Failed to enter UL mode")

        return_value, error = controller._execute_ex_command(command)  # pylint: disable=protected-access
        if error:
            raise RuntimeError(error)
        if return_value is not None:
            print(f"Return value: {return_value}")

        print("\n[KXCI] Retrieving data...")

        def safe_query(param: int) -> List[float]:
            return controller._query_gp(param, total_pulses)  # pylint: disable=protected-access

        read_v = safe_query(9)
        read_i = safe_query(11)
        pulse_times = safe_query(13)
        out1 = safe_query(15)

        if not pulse_times:
            pulse_times = _compute_probe_times(cfg)

        if len(pulse_times) != total_pulses:
            pulse_times = [float(i) for i in range(total_pulses)]

        resistance: List[float] = []
        for v, i_cur in zip(read_v, read_i):
            if abs(i_cur) < 1e-12:
                resistance.append(float("inf"))
            else:
                resistance.append(v / i_cur)

        try:
            import pandas as pd  # type: ignore

            df = pd.DataFrame(
                {
                    "pulse": range(1, total_pulses + 1),
                    "time_s": pulse_times,
                    "voltage_V": read_v,
                    "current_A": read_i,
                    "resistance_ohm": resistance,
                    cfg.out1_name: out1,
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
                ("pulse", list(range(1, total_pulses + 1))),
                ("time_s", pulse_times),
                ("voltage_V", read_v),
                ("current_A", read_i),
                ("resistance_ohm", resistance),
                (cfg.out1_name, out1),
            ):
                print(f"\n{label}:")
                for idx, val in enumerate(values):
                    print(f"  {idx + 1:02d}: {val}")

    finally:
        try:
            controller._exit_ul_mode()  # pylint: disable=protected-access
        except Exception:  # noqa: BLE001
            pass
        controller.disconnect()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate/run ACraig1_PMU_readtrain")

    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR", help="VISA resource string")
    parser.add_argument("--timeout", type=float, default=30.0, help="Visa timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only print the EX command")
    parser.add_argument("--no-plot", action="store_true", help="Disable plotting even if matplotlib is present")

    parser.add_argument("--rise-time", type=float, default=1e-7)
    parser.add_argument("--meas-v", type=float, default=0.3)
    parser.add_argument("--meas-width", type=float, default=1e-6)
    parser.add_argument("--meas-delay", type=float, default=2e-6)
    parser.add_argument("--num-pulses", type=int, default=50)
    parser.add_argument("--trigger-pulse", type=int, default=1)
    parser.add_argument("--i-range", type=float, default=1e-4)
    parser.add_argument("--max-points", type=int, default=10000)
    parser.add_argument("--out1-name", default="VF")
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--clarius-debug", type=int, choices=[0, 1], default=0)

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
        iteration=args.iteration,
        clarius_debug=args.clarius_debug,
    )

    cfg.validate()

    command = build_ex_command(cfg)
    print("Generated EX command:\n" + command)

    if args.dry_run:
        return

    run_measurement(cfg, address=args.gpib_address, timeout=args.timeout, enable_plot=not args.no_plot)


if __name__ == "__main__":
    main()


