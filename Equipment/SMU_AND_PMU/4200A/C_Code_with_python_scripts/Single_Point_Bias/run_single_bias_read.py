"""Keithley 4200A single-bias helper.

This module applies a single DC bias (default 0.2 V) via the existing
`smu_ivsweep` C routine and immediately reports the measured current back
to the host PC. It reuses the proven `run_smu_vi_sweep` helpers for KXCI
communication so behavior stays consistent with the full sweep runner.

Typical usage:
    python run_single_bias_read.py --bias-voltage 0.2

Every file in this repository should document its purpose and include a
testable component; `extract_point_measurement` is implemented with unit
coverage under `tests/test_single_bias_measurement.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
A_IV_SWEEP_DIR = SCRIPT_DIR.parent / "A_Iv_Sweep"
if str(A_IV_SWEEP_DIR) not in sys.path:
    sys.path.insert(0, str(A_IV_SWEEP_DIR))

try:
    from run_smu_vi_sweep import KXCIClient, build_ex_command  # type: ignore
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "Unable to import run_smu_vi_sweep helpers. "
        "Verify the A_Iv_Sweep directory is intact."
    ) from exc


def extract_point_measurement(
    voltage: List[float],
    current: List[float],
    target_voltage: float,
    tolerance: float = 1e-6,
) -> Tuple[float, float]:
    """Return the first (voltage, current) pair matching the requested bias.

    Args:
        voltage: Sequence of forced voltages reported by `smu_ivsweep`.
        current: Sequence of measured currents aligned with `voltage`.
        target_voltage: Desired voltage we applied (e.g., 0.2 V).
        tolerance: Acceptable absolute deviation when matching the point.

    Raises:
        ValueError: If no data point matches within the tolerance.
    """

    for forced, measured in zip(voltage, current):
        if abs(forced - target_voltage) <= tolerance:
            return forced, measured
    raise ValueError(
        f"No measurement matched {target_voltage} V "
        f"(tolerance {tolerance}, received {len(voltage)} samples)."
    )


def measure_bias_current(
    gpib_address: str,
    timeout: float,
    bias_voltage: float = 0.2,
    settle_time: float = 0.01,
    ilimit: float = 0.01,
    integration_time: float = 0.01,
    tolerance: float = 1e-3,
    debug: bool = False,
) -> dict:
    """Execute one 0 → +Vbias → -Vbias → 0 cycle and return the +Vbias data."""

    if bias_voltage <= 0:
        raise ValueError("bias_voltage must be positive.")
    if settle_time < 0.0001 or settle_time > 10:
        raise ValueError("settle_time must be within [0.0001, 10].")
    if not (1e-9 <= ilimit <= 1.0):
        raise ValueError("ilimit must be within [1e-9, 1.0].")
    if not (0.0001 <= integration_time <= 1.0):
        raise ValueError("integration_time must be within [0.0001, 1.0].")
    if tolerance <= 0:
        raise ValueError("tolerance must be positive.")

    num_cycles = 1
    num_points = 4  # 0, +V, -V, 0
    command = build_ex_command(
        vpos=bias_voltage,
        vneg=0.0,  # auto-sets to -bias internally
        num_cycles=num_cycles,
        num_points=num_points,
        settle_time=settle_time,
        ilimit=ilimit,
        integration_time=integration_time,
        clarius_debug=1 if debug else 0,
    )

    controller = KXCIClient(gpib_address=gpib_address, timeout=timeout)
    if not controller.connect():
        raise RuntimeError("Failed to connect to instrument.")

    try:
        if not controller._enter_ul_mode():  # pylint: disable=protected-access
            raise RuntimeError("Failed to enter UL mode.")

        return_value, error = controller._execute_ex_command(command)
        if error:
            raise RuntimeError(f"EX command failed: {error}")
        if return_value not in (0, None):
            raise RuntimeError(f"EX command returned error code: {return_value}")

        voltage = controller._query_gp(6, num_points)  # pylint: disable=protected-access
        current = controller._query_gp(4, num_points)  # pylint: disable=protected-access

        forced_v, measured_i = extract_point_measurement(
            voltage, current, target_voltage=bias_voltage, tolerance=tolerance
        )
        return {
            "forced_voltage": forced_v,
            "measured_current": measured_i,
            "num_samples": len(current),
            "bias_voltage": bias_voltage,
            "settle_time": settle_time,
            "ilimit": ilimit,
            "integration_time": integration_time,
        }
    finally:
        try:
            controller._exit_ul_mode()  # pylint: disable=protected-access
        finally:
            controller.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply a single DC bias via smu_ivsweep and report current.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout (s).")
    parser.add_argument(
        "--bias-voltage",
        type=float,
        default=0.2,
        help="Positive bias to apply; script uses symmetric -bias for return.",
    )
    parser.add_argument(
        "--settle-time",
        type=float,
        default=0.01,
        help="Seconds to wait at each point.",
    )
    parser.add_argument(
        "--ilimit",
        type=float,
        default=0.01,
        help="Compliance current (A).",
    )
    parser.add_argument(
        "--integration-time",
        type=float,
        default=0.01,
        help="Measurement integration time (PLC).",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-3,
        help="Allowed deviation when matching the +bias point.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose C-module debug output.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print command without contacting instrument.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    if args.dry_run:
        command = build_ex_command(
            vpos=args.bias_voltage,
            vneg=0.0,
            num_cycles=1,
            num_points=4,
            settle_time=args.settle_time,
            ilimit=args.ilimit,
            integration_time=args.integration_time,
            clarius_debug=1 if args.debug else 0,
        )
        print("[DRY RUN] EX command:")
        print(command)
        return

    result = measure_bias_current(
        gpib_address=args.gpib_address,
        timeout=args.timeout,
        bias_voltage=args.bias_voltage,
        settle_time=args.settle_time,
        ilimit=args.ilimit,
        integration_time=args.integration_time,
        tolerance=args.tolerance,
        debug=args.debug,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print("\n[RESULT]")
    print(f"  Forced voltage : {result['forced_voltage']:.6f} V")
    print(f"  Measured current: {result['measured_current']:.6e} A")
    print(f"  Samples stored  : {result['num_samples']}")


if __name__ == "__main__":
    main()


