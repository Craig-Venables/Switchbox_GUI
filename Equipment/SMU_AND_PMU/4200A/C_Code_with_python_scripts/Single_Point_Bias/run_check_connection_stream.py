"""Continuous connection-check helper for the Keithley 4200A.

This script launches the `smu_check_connection` C module via KXCI to apply
a fixed DC bias (default 0.2 V) and streams measurements back to the host
until the user issues Ctrl+C. It is designed to integrate with the
Connection Check GUI but can be run standalone for bench verification.

Usage example:

    python run_check_connection_stream.py --bias-voltage 0.2 --sample-interval 0.05

Key behaviors:
- Reuses the existing `KXCIClient` helper from `run_smu_vi_sweep.py`.
- Starts the UL program without blocking so we can poll buffers via GP.
- Stores streaming data inside instrument circular buffers (size configurable).
- Gracefully stops by setting Control[0] = 1 before exiting UL mode.

Each file in this repo must document itself and ship with some unit coverage;
see `tests/test_check_connection_stream.py` for ring-buffer helper tests.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
A_IV_SWEEP_DIR = SCRIPT_DIR.parent / "A_Iv_Sweep"
if str(A_IV_SWEEP_DIR) not in sys.path:
    sys.path.insert(0, str(A_IV_SWEEP_DIR))

try:
    from run_smu_vi_sweep import KXCIClient, format_param  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Unable to import run_smu_vi_sweep helpers. "
        "Ensure Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/A_Iv_Sweep "
        "is present."
    ) from exc


def build_check_connection_command(
    bias_voltage: float,
    sample_interval: float,
    settle_time: float,
    ilimit: float,
    integration_time: float,
    buffer_size: int,
    max_samples: int,
    clarius_debug: int,
) -> str:
    """Return the EX command string for smu_check_connection."""

    params = [
        format_param(bias_voltage),     # 1 BiasVoltage
        format_param(sample_interval),  # 2 SampleInterval
        format_param(settle_time),      # 3 SettleTime
        format_param(ilimit),           # 4 Ilimit
        format_param(integration_time), # 5 IntegrationTime
        "",                             # 6 Ibuffer (D_ARRAY_T)
        format_param(buffer_size),      # 7 NumISamples
        "",                             # 8 Vbuffer (D_ARRAY_T)
        format_param(buffer_size),      # 9 NumVSamples
        format_param(max_samples),      # 10 MaxSamples
        format_param(clarius_debug),    # 11 ClariusDebug
    ]
    return f"EX Single_Point_Bias smu_check_connection({','.join(params)})"


def format_sp_command(param_position: int, values: Sequence[int]) -> str:
    value_str = " ".join(str(int(v)) for v in values)
    return f"SP {param_position} {value_str}"


@dataclass
class BufferSnapshot:
    voltage: float
    current: float
    total_samples: int
    write_index: int


def latest_sample_from_buffers(
    voltage: Sequence[float],
    current: Sequence[float],
    write_index: int,
    total_samples: int,
) -> BufferSnapshot:
    """Return the most recent (V, I) pair from circular buffers."""

    if total_samples <= 0 or not voltage or not current:
        raise ValueError("No samples available")

    buffer_size = min(len(voltage), len(current))
    idx = (write_index - 1) % buffer_size
    return BufferSnapshot(
        voltage=voltage[idx],
        current=current[idx],
        total_samples=total_samples,
        write_index=write_index,
    )


class CheckConnectionStreamer:
    def __init__(
        self,
        controller: KXCIClient,
        buffer_size: int,
    ) -> None:
        self.controller = controller
        self.buffer_size = buffer_size

    def _write(self, command: str) -> None:
        if self.controller.inst is None:
            raise RuntimeError("Instrument not connected")
        self.controller.inst.write(command)

    def execute_and_read(self, command: str, emit_json: bool) -> None:
        """Execute the module and read results after completion."""
        self._write(command)
        # Wait for module to complete (approximate time: max_samples * sample_interval)
        time.sleep(0.1)  # Small delay to ensure command is processed
        
        # Read buffers after module completes
        voltage = self.controller._query_gp(8, self.buffer_size)  # pylint: disable=protected-access
        current = self.controller._query_gp(6, self.buffer_size)  # pylint: disable=protected-access
        
        # Find the last non-zero sample (circular buffer)
        last_idx = 0
        for i in range(self.buffer_size):
            if abs(current[i]) > 1e-15 or abs(voltage[i]) > 1e-6:
                last_idx = i
        
        if emit_json:
            print(
                json.dumps(
                    {
                        "voltage": voltage[last_idx],
                        "current": current[last_idx],
                        "sample_index": last_idx,
                    }
                )
            )
        else:
            print(
                f"V={voltage[last_idx]: .6f} V | "
                f"I={current[last_idx]: .6e} A | idx={last_idx}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream continuous bias measurements via smu_check_connection",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--bias-voltage", type=float, default=0.2)
    parser.add_argument("--sample-interval", type=float, default=0.1)
    parser.add_argument("--settle-time", type=float, default=0.01)
    parser.add_argument("--ilimit", type=float, default=0.01)
    parser.add_argument("--integration-time", type=float, default=0.01)
    parser.add_argument("--buffer-size", type=int, default=128)
    parser.add_argument("--max-samples", type=int, default=1000, help="Number of samples to collect per run")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON lines")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continuous", action="store_true", help="Run continuously (repeated calls)")

    args = parser.parse_args()

    if args.buffer_size < 4:
        parser.error("buffer-size must be >= 4")
    if args.max_samples < 1:
        parser.error("max-samples must be >= 1")

    command = build_check_connection_command(
        bias_voltage=args.bias_voltage,
        sample_interval=args.sample_interval,
        settle_time=args.settle_time,
        ilimit=args.ilimit,
        integration_time=args.integration_time,
        buffer_size=args.buffer_size,
        max_samples=args.max_samples,
        clarius_debug=1 if args.debug else 0,
    )

    if args.dry_run:
        print(command)
        return

    controller = KXCIClient(gpib_address=args.gpib_address, timeout=args.timeout)
    if not controller.connect():
        raise SystemExit("[ERROR] Failed to connect to instrument")

    try:
        if not controller._enter_ul_mode():  # pylint: disable=protected-access
            raise RuntimeError("Failed to enter UL mode")

        streamer = CheckConnectionStreamer(
            controller=controller,
            buffer_size=args.buffer_size,
        )

        if args.continuous:
            print("[INFO] Running continuously (Ctrl+C to stop)...")
            try:
                while True:
                    streamer.execute_and_read(command, emit_json=args.json)
                    time.sleep(0.1)  # Small delay between runs
            except KeyboardInterrupt:
                print("\n[INFO] Stopped by user")
        else:
            streamer.execute_and_read(command, emit_json=args.json)

        response = controller._safe_read()  # pylint: disable=protected-access
        if response:
            print(f"\n[INFO] Instrument response: {response.strip()}")
    finally:
        try:
            controller._exit_ul_mode()  # pylint: disable=protected-access
        finally:
            controller.disconnect()


if __name__ == "__main__":
    main()


