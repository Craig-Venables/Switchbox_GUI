"""ACraig8 single-channel waveform with auxiliary pulse.

Channel 1 sources a simple pulse train and captures the resulting voltage/current
waveform. Channel 2 optionally sources an auxiliary pulse (no measurement) that can
be used to drive an external trigger (e.g., a laser). The script configures the KXCI
UL client, runs the ACraig8 module, and retrieves the recorded waveform.
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
        except ImportError as exc:  # noqa: F401
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
        except Exception as exc:  # noqa: BLE001
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
class WaveConfig:
    width: float = 1e-6
    rise: float = 3e-8
    fall: float = 3e-8
    delay: float = 0.0
    period: float = 5e-6
    base_v: float = 0.0
    pulse_v: float = 1.5
    num_pulses: int = 50
    v_range: float = 10.0
    i_range: float = 1e-3
    dut_res: float = 1e6
    sample_rate: float = 5e7
    pre_pct: float = 0.1
    post_pct: float = 0.1
    aux_base: float = 0.0
    aux_pulse: float = 1.5
    aux_delay: float = 0.0
    aux_width: float = 1e-6
    aux_rise: float = 3e-8
    aux_fall: float = 3e-8
    max_points: int = 5000
    clarius_debug: int = 1

    def validate(self) -> None:
        limits = {
            "width": (2e-8, 1.0),
            "rise": (2e-8, 1.0),
            "fall": (2e-8, 1.0),
            "delay": (0.0, 1.0),
            "period": (1e-6, 5.0),
            "v_range": (5.0, 40.0),
            "i_range": (100e-9, 0.8),
            "sample_rate": (1e5, 2e8),
            "pre_pct": (0.0, 1.0),
            "post_pct": (0.0, 1.0),
            "aux_width": (2e-8, 1.0),
            "aux_rise": (2e-8, 1.0),
            "aux_fall": (2e-8, 1.0),
        }
        for field, (lo, hi) in limits.items():
            value = getattr(self, field)
            if value < lo or value > hi:
                raise ValueError(f"{field}={value} outside [{lo}, {hi}]")
        if self.num_pulses < 1 or self.num_pulses > 1000:
            raise ValueError("num_pulses must be within [1, 1000]")
        if self.max_points < 100 or self.max_points > 30000:
            raise ValueError("max_points must be within [100, 30000]")
        if self.clarius_debug not in (0, 1):
            raise ValueError("clarius_debug must be 0 or 1")


def build_ex_command(cfg: WaveConfig) -> str:
    params = [
        format_param(cfg.width),
        format_param(cfg.rise),
        format_param(cfg.fall),
        format_param(cfg.delay),
        format_param(cfg.period),
        format_param(cfg.base_v),
        format_param(cfg.pulse_v),
        format_param(cfg.num_pulses),
        format_param(cfg.v_range),
        format_param(cfg.i_range),
        format_param(cfg.dut_res),
        format_param(cfg.sample_rate),
        format_param(cfg.pre_pct),
        format_param(cfg.post_pct),
        format_param(cfg.aux_base),
        format_param(cfg.aux_pulse),
        format_param(cfg.aux_delay),
        format_param(cfg.aux_width),
        format_param(cfg.aux_rise),
        format_param(cfg.aux_fall),
        "",
        format_param(cfg.max_points),
        "",
        format_param(cfg.max_points),
        "",
        format_param(cfg.max_points),
        format_param(cfg.clarius_debug),
    ]

    return f"EX ACraig8 ACraig8_single_channel_wave_aux({','.join(params)})"


def run_measurement(cfg: WaveConfig, address: str, timeout: float, enable_plot: bool) -> None:
    command = build_ex_command(cfg)
    controller = KXCIClient(gpib_address=address, timeout=timeout)

    try:
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")

        print("\n[KXCI] Generated EX command:")
        print(command)
        print(
            f"[KXCI] Primary pulse: base={cfg.base_v} V, pulse={cfg.pulse_v} V, width={cfg.width}s, "
            f"rise={cfg.rise}s, fall={cfg.fall}s, period={cfg.period}s"
        )
        if abs(cfg.aux_pulse - cfg.aux_base) > 1e-9:
            print(
                "[KXCI] Auxiliary pulse: "
                f"base={cfg.aux_base} V, pulse={cfg.aux_pulse} V, delay={cfg.aux_delay}s, "
                f"width={cfg.aux_width}s"
            )

        if not controller._enter_ul_mode():  # pylint: disable=protected-access
            raise RuntimeError("Failed to enter UL mode")

        return_value, error = controller._execute_ex_command(command)  # pylint: disable=protected-access
        if error:
            raise RuntimeError(error)
        if return_value is not None:
            print(f"Return value: {return_value}")

        print("\n[KXCI] Retrieving data...")

        def safe_query(param: int, count: int) -> List[float]:
            data = controller._query_gp(param, count)  # pylint: disable=protected-access
            print(f"GP {param}: {len(data)} values (first 5: {data[:5]})")
            return data

        read_v = safe_query(21, cfg.max_points)
        read_i = safe_query(23, cfg.max_points)
        time_axis = safe_query(25, cfg.max_points)

        usable = min(len(read_v), len(read_i), len(time_axis))
        read_v = read_v[:usable]
        read_i = read_i[:usable]
        time_axis = time_axis[:usable]

        print(f"\n[KXCI] Collected {usable} samples.")
        if not read_v:
            print("No data returned.")
            return

        try:
            import pandas as pd  # type: ignore

            df = pd.DataFrame(
                {
                    "sample": range(usable),
                    "time_s": time_axis,
                    "voltage_V": read_v,
                    "current_A": read_i,
                }
            )
            print("\nWaveform Samples:")
            print(df.head(15).to_string(index=False))

            if enable_plot:
                try:
                    import matplotlib.pyplot as plt  # type: ignore

                    fig, ax1 = plt.subplots(figsize=(8, 4))
                    ax1.plot(time_axis, read_v, label="Voltage (V)", color="tab:blue")
                    ax1.set_xlabel("Time (s)")
                    ax1.set_ylabel("Voltage (V)", color="tab:blue")
                    ax1.tick_params(axis="y", labelcolor="tab:blue")

                    ax2 = ax1.twinx()
                    ax2.plot(time_axis, read_i, label="Current (A)", color="tab:red")
                    ax2.set_ylabel("Current (A)", color="tab:red")
                    ax2.tick_params(axis="y", labelcolor="tab:red")

                    plt.title("ACraig8 Channel 1 Waveform")
                    plt.tight_layout()
                    plt.show()
                except Exception as exc:  # noqa: BLE001
                    print(f"\n[WARN] Unable to display plot: {exc}")
        except ImportError:
            print("\nPandas not available; showing first 10 samples:")
            for idx in range(min(10, usable)):
                print(
                    f"{idx:04d}  t={time_axis[idx]:.3e} s  V={read_v[idx]:.3f} V  I={read_i[idx]:.3e} A"
                )

    finally:
        try:
            controller._exit_ul_mode()  # pylint: disable=protected-access
        except Exception:  # noqa: BLE001
            pass
        controller.disconnect()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate/run ACraig8 single-channel waveform with auxiliary pulse")

    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR", help="VISA resource string")
    parser.add_argument("--timeout", type=float, default=30.0, help="Visa timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only print the EX command")
    parser.add_argument("--no-plot", action="store_true", help="Disable plotting even if matplotlib is present")

    parser.add_argument("--width", type=float, default=1e-6)
    parser.add_argument("--rise", type=float, default=3e-8)
    parser.add_argument("--fall", type=float, default=3e-8)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--period", type=float, default=5e-6)
    parser.add_argument("--base-v", type=float, default=0.0)
    parser.add_argument("--pulse-v", type=float, default=1.5)
    parser.add_argument("--num-pulses", type=int, default=50)
    parser.add_argument("--v-range", type=float, default=10.0)
    parser.add_argument("--i-range", type=float, default=1e-3)
    parser.add_argument("--dut-res", type=float, default=1e6)
    parser.add_argument("--sample-rate", type=float, default=5e7)
    parser.add_argument("--pre-pct", type=float, default=0.1)
    parser.add_argument("--post-pct", type=float, default=0.1)

    parser.add_argument("--aux-base", type=float, default=0.0)
    parser.add_argument("--aux-pulse", type=float, default=1.5)
    parser.add_argument("--aux-delay", type=float, default=0.0)
    parser.add_argument("--aux-width", type=float, default=1e-6)
    parser.add_argument("--aux-rise", type=float, default=3e-8)
    parser.add_argument("--aux-fall", type=float, default=3e-8)

    parser.add_argument("--max-points", type=int, default=5000)
    parser.add_argument("--clarius-debug", type=int, choices=[0, 1], default=1)

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    cfg = WaveConfig(
        width=args.width,
        rise=args.rise,
        fall=args.fall,
        delay=args.delay,
        period=args.period,
        base_v=args.base_v,
        pulse_v=args.pulse_v,
        num_pulses=args.num_pulses,
        v_range=args.v_range,
        i_range=args.i_range,
        dut_res=args.dut_res,
        sample_rate=args.sample_rate,
        pre_pct=args.pre_pct,
        post_pct=args.post_pct,
        aux_base=args.aux_base,
        aux_pulse=args.aux_pulse,
        aux_delay=args.aux_delay,
        aux_width=args.aux_width,
        aux_rise=args.aux_rise,
        aux_fall=args.aux_fall,
        max_points=args.max_points,
        clarius_debug=args.clarius_debug,
    )

    cfg.validate()
    command = build_ex_command(cfg)
    print("Generated EX command:\n" + command)

    if args.dry_run:
        return

    run_measurement(
        cfg,
        address=args.gpib_address,
        timeout=args.timeout,
        enable_plot=not args.no_plot,
    )


if __name__ == "__main__":
    main()


