"""Multi-point calibration workflow for the FC-2901V.

Usage examples
--------------
# Manual entry (no hardware required, you read the MFC display yourself):
  python calibrate_mfc.py --mode manual --gas Ar

# Auto-setpoint via NI-DAQ (PC commands setpoints; you read reference meter):
  python calibrate_mfc.py --mode auto --driver nidaq --device Dev1

# Auto-setpoint via Arduino:
  python calibrate_mfc.py --mode auto --driver arduino --port COM3

Output: calibration.json (loaded automatically by main.py dashboard)
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from .calibration import build_calibration_record, fit_model, save_calibration
    from .driver import AbstractMFCDriver, ArduinoDriver, DriverError, NIDAQDriver
except ImportError:
    from calibration import build_calibration_record, fit_model, save_calibration
    from driver import AbstractMFCDriver, ArduinoDriver, DriverError, NIDAQDriver


def _parse_setpoints(raw: str) -> List[float]:
    values = [float(t.strip()) for t in raw.split(",") if t.strip()]
    if not values:
        raise ValueError("No setpoints provided.")
    return values


def _prompt_float(prompt: str) -> float:
    while True:
        try:
            return float(input(prompt).strip())
        except ValueError:
            print("  Invalid number, try again.")


def _build_driver(args: argparse.Namespace) -> Optional[AbstractMFCDriver]:
    if args.mode == "manual":
        return None
    if args.driver == "nidaq":
        return NIDAQDriver(
            device_name=args.device,
            ao_channel=args.ao_channel,
            ai_channel=args.ai_channel,
            do_valve_off_channel=args.do_channel,
            full_scale_sccm=args.full_scale,
        )
    return ArduinoDriver(
        port=args.port,
        baudrate=args.baud,
        full_scale_sccm=args.full_scale,
    )


def run_calibration(args: argparse.Namespace) -> None:
    print("=" * 60)
    print("  FC-2901V Calibration Workflow")
    print(f"  Gas: {args.gas}   Full scale: {args.full_scale} sccm")
    print(f"  Mode: {args.mode}   Fit order: {args.order}")
    print("=" * 60)
    print()

    driver = _build_driver(args)
    if driver is not None:
        print(f"Connecting via {args.driver} ...")
        try:
            driver.connect()
            print("  Connected.")
        except DriverError as exc:
            print(f"  ERROR: {exc}")
            print("  Falling back to manual entry.")
            driver = None

    points: List[Tuple[float, float]] = []

    for sp in args.setpoints:
        print(f"--- Setpoint target: {sp:.2f} sccm ---")

        if driver is not None:
            try:
                driver.set_setpoint_sccm(sp)
                print(f"  MFC setpoint commanded to {sp:.2f} sccm.")
                print(f"  Waiting {args.settle}s for flow to settle ...")
                time.sleep(args.settle)
            except DriverError as exc:
                print(f"  WARNING: could not command setpoint: {exc}")

        device_val = _prompt_float("  Enter MFC-reported flow (sccm, from display or readout): ")
        reference_val = _prompt_float("  Enter reference meter reading (sccm): ")
        points.append((device_val, reference_val))
        print()

    if driver is not None:
        try:
            driver.set_setpoint_sccm(0.0)
            driver.close()
        except Exception:
            pass

    device_readings = [p[0] for p in points]
    reference_readings = [p[1] for p in points]

    fit = fit_model(device_readings, reference_readings, args.order)
    record = build_calibration_record(
        gas=args.gas,
        full_scale_sccm=args.full_scale,
        points=points,
        fit=fit,
        notes=args.notes,
    )
    save_calibration(args.output, record)

    print("Calibration saved.")
    print(f"  File     : {args.output}")
    print(f"  Fit order: {fit['order']}")
    print(f"  Coeff    : {fit['coefficients']}")
    print(f"  RMSE     : {fit['rmse_sccm']:.4f} sccm")
    print(f"  Max err  : {fit['max_abs_error_sccm']:.4f} sccm")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Calibrate FC-2901V flow readings against a reference meter."
    )
    p.add_argument(
        "--setpoints", type=_parse_setpoints,
        default=[0, 25, 50, 75, 100, 125, 150, 175, 200],
        help="Comma-separated setpoints in sccm (default: 0,25,…,200).",
    )
    p.add_argument(
        "--mode", choices=["manual", "auto"], default="manual",
        help="manual = enter values yourself; auto = PC commands setpoints.",
    )
    p.add_argument("--driver", choices=["nidaq", "arduino"], default="nidaq",
                   help="Hardware backend for auto mode.")
    p.add_argument("--device", default="Dev1", help="NI-DAQ device name.")
    p.add_argument("--ao-channel", default="ao0", dest="ao_channel")
    p.add_argument("--ai-channel", default="ai0", dest="ai_channel")
    p.add_argument("--do-channel", default="port0/line0", dest="do_channel")
    p.add_argument("--port", default="COM3", help="Arduino COM port.")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--settle", type=float, default=10.0,
                   help="Seconds to wait after each setpoint command (auto mode).")
    p.add_argument("--order", type=int, choices=[1, 2], default=1,
                   help="Fit order: 1=linear, 2=quadratic.")
    p.add_argument("--gas", default="Ar", help="Calibration gas label.")
    p.add_argument("--full-scale", type=float, default=200.0, dest="full_scale")
    p.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parent / "calibration.json",
    )
    p.add_argument("--notes", default="")
    return p


def main() -> None:
    args = build_parser().parse_args()
    run_calibration(args)


if __name__ == "__main__":
    main()
