"""Simple front-end for ACraig6_simple_pulse.

This script configures a single PMU channel for a basic two-level pulse train
and executes the ACraig6_simple_pulse module via KXCI. It mirrors the carved
down two-level flow: load, compliance, edge times, dwell/pulse width, voltage
low/high, optional burst count. After execution it fetches VF/IF samples and
prints them (with optional plotting). Designed for rapid long-duration read
trains without segmented arbitrary calls.
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
class SimplePulseConfig:
    instr: str = "PMU1"
    channel: int = 2
    load: float = 50.0
    current_limit: float = 1e-3
    rise_time: float = 20e-9
    fall_time: float = 20e-9
    delay: float = 0.0
    range_v: float = 5.0
    vlow: float = 0.0
    vhigh: float = 0.5
    period: float = 1e-6
    width: float = 5e-7
    burst_count: int = 1000
    vf_points: int = 2000

    def validate(self) -> None:
        limits: Dict[str, tuple[float, float]] = {
            "rise_time": (2e-9, 1.0),
            "fall_time": (2e-9, 1.0),
            "period": (1e-7, 1.0),
            "width": (5e-9, 1.0),
            "range_v": (0.2, 40.0),
            "vlow": (-20.0, 20.0),
            "vhigh": (-20.0, 20.0),
            "load": (0.1, 1e6),
            "current_limit": (0.0, 1.0),
        }
        for field, (lo, hi) in limits.items():
            value = getattr(self, field)
            if value < lo or value > hi:
                raise ValueError(f"{field}={value} outside [{lo}, {hi}]")
        if self.channel not in (1, 2):
            raise ValueError("channel must be 1 or 2")
        if self.burst_count < 1 or self.burst_count > 1000000:
            raise ValueError("burst_count must be >=1 and reasonable")
        if self.vf_points < 10 or self.vf_points > 30000:
            raise ValueError("vf_points must be within [10, 30000]")


def build_ex_command(cfg: SimplePulseConfig) -> str:
    params = [
        cfg.instr,
        format_param(cfg.channel),
        format_param(cfg.load),
        format_param(cfg.current_limit),
        format_param(cfg.rise_time),
        format_param(cfg.fall_time),
        format_param(cfg.delay),
        format_param(cfg.range_v),
        format_param(cfg.vlow),
        format_param(cfg.vhigh),
        format_param(cfg.period),
        format_param(cfg.width),
        format_param(cfg.burst_count),
        "",  # VF
        format_param(cfg.vf_points),
        "",  # IF
        format_param(cfg.vf_points),
        "",  # T
        format_param(cfg.vf_points),
        "",  # npts pointer replaced by fetch
    ]

    return f"EX ACraig6 ACraig6_simple_pulse({','.join(params)})"


def run_measurement(cfg: SimplePulseConfig, address: str, timeout: float, enable_plot: bool) -> None:
    command = build_ex_command(cfg)
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

        def safe_query(param: int, count: int) -> List[float]:
            return controller._query_gp(param, count)  # pylint: disable=protected-access

        read_v = safe_query(14, cfg.vf_points)
        read_i = safe_query(16, cfg.vf_points)
        pulse_times = safe_query(18, cfg.vf_points)

        trimmed_len = min(len(read_v), len(read_i), len(pulse_times))
        read_v = read_v[:trimmed_len]
        read_i = read_i[:trimmed_len]
        pulse_times = pulse_times[:trimmed_len]

        print(f"\n[KXCI] Collected {trimmed_len} samples.")

        def print_array(name: str, values: List[float]) -> None:
            print(f"\n{name}:")
            for idx, val in enumerate(values):
                print(f"  {idx + 1:04d}: {val}")

        print_array("time_s", pulse_times)
        print_array("voltage_V", read_v)
        print_array("current_A", read_i)

        resistance: List[float] = []
        for v, i in zip(read_v, read_i):
            if abs(i) < 1e-12:
                resistance.append(float("inf"))
            else:
                resistance.append(v / i)

        if enable_plot:
            try:
                import matplotlib.pyplot as plt  # type: ignore

                plt.figure(figsize=(8, 4))
                plt.plot(pulse_times, resistance, marker="o", linewidth=1)
                plt.xlabel("Time (s)")
                plt.ylabel("Resistance (Ohm)")
                plt.title("ACraig6 Simple Pulse Resistance vs Time")
                plt.grid(True)
                plt.tight_layout()
                plt.show()
            except Exception as exc:  # noqa: BLE001
                print(f"\n⚠️ Unable to display plot: {exc}")

    finally:
        try:
            controller._exit_ul_mode()  # pylint: disable=protected-access
        except Exception:  # noqa: BLE001
            pass
        controller.disconnect()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate/run ACraig6_simple_pulse")

    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR", help="VISA resource string")
    parser.add_argument("--timeout", type=float, default=30.0, help="Visa timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only print the EX command")
    parser.add_argument("--no-plot", action="store_true", help="Disable plotting even if matplotlib is present")

    parser.add_argument("--instr", default="PMU1")
    parser.add_argument("--channel", type=int, default=2)
    parser.add_argument("--load", type=float, default=50.0)
    parser.add_argument("--current-limit", type=float, dest="current_limit", default=1e-3)
    parser.add_argument("--rise-time", type=float, default=20e-9)
    parser.add_argument("--fall-time", type=float, default=20e-9)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--range", type=float, dest="range_v", default=5.0)
    parser.add_argument("--vlow", type=float, default=0.0)
    parser.add_argument("--vhigh", type=float, default=0.5)
    parser.add_argument("--period", type=float, default=1e-6)
    parser.add_argument("--width", type=float, default=5e-7)
    parser.add_argument("--burst-count", type=int, dest="burst_count", default=1000)
    parser.add_argument("--vf-points", type=int, dest="vf_points", default=2000)

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    cfg = SimplePulseConfig(
        instr=args.instr,
        channel=args.channel,
        load=args.load,
        current_limit=args.current_limit,
        rise_time=args.rise_time,
        fall_time=args.fall_time,
        delay=args.delay,
        range_v=args.range_v,
        vlow=args.vlow,
        vhigh=args.vhigh,
        period=args.period,
        width=args.width,
        burst_count=args.burst_count,
        vf_points=args.vf_points,
    )

    cfg.validate()

    command = build_ex_command(cfg)
    print("Generated EX command:\n" + command)

    if args.dry_run:
        return

    run_measurement(cfg, address=args.gpib_address, timeout=args.timeout, enable_plot=not args.no_plot)


if __name__ == "__main__":
    main()



