"""
Measure Oxxius laser power with Thorlabs PM100D, focused on low power (< 5 mW).

Uses Equipment/Laser_Power_Meter (PM100D) and Equipment/Laser_Controller (Oxxius).
Saves CSV and JSON to this folder for use in code: apparent (set) vs actual (measured)
power so you can configure power on the sample from calibration data.

Usage:
  python measure_laser_power.py [LASER_PORT] [LASER_BAUD] [PM_SERIAL]
  python measure_laser_power.py --setpoints 0.25 0.5 1 2 5

Output (in Equipment/Laser_Power_Meter/):
  laser_power_calibration_YYYYMMDD_HHMMSS.csv
  laser_power_calibration_YYYYMMDD_HHMMSS.json

Use laser_power_calibration.load_calibration() and .get_setpoint_for_actual_mw() etc.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Allow importing from repo root
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from Equipment.Laser_Power_Meter import PM100D, find_pm100d_resource
from Equipment.Laser_Controller.oxxius import OxxiusLaser


# One-time calibration: granular where curve changes most (from typical results).
# Sparse 0.1–1 mW (measured ≈ 0), dense 1–3 mW (steep rise), moderate 3–5 mW, sparse 5–20 mW.
# 0.1 mW steps from 0.1 to 10.0, then sparse 10–50 mW
DEFAULT_SETPOINTS_MW = (
    [round(x * 0.1, 2) for x in range(1, 101)]  # 0.1, 0.2, ..., 10.0
    + [10.5,11.0,12.0,13.0,14.0,15.0,16.0,17.0,18.0,19.0, 20.0,22.5, 25.0,27.5]
    + [30.0,32.5,35.0,37.5,40.0, 45.0, 50.0,60.0,70.0,80.0]  # high end: sparse
)
STABILITY_WAIT_S = 1.5
NUM_SAMPLES = 10
SAMPLE_INTERVAL_S = 0.2
OUTPUT_DIR = Path(__file__).resolve().parent
FILENAME_PREFIX = "laser_power_calibration"


def measure_power_stable(pm: PM100D, n: int = NUM_SAMPLES, interval_s: float = SAMPLE_INTERVAL_S) -> float:
    """Take n power readings (mW) and return mean."""
    readings = []
    for _ in range(n):
        readings.append(pm.measure_power_mw())
        time.sleep(interval_s)
    return sum(readings) / len(readings)


def save_calibration(
    results: list[tuple[float, float, float, float]],
    *,
    wavelength_nm: float | None = None,
    laser_port: str = "",
    laser_idn: str = "",
    pm_idn: str = "",
) -> tuple[Path, Path]:
    """Write CSV and JSON to OUTPUT_DIR. Returns (csv_path, json_path)."""
    timestamp = datetime.now()
    ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
    ts_iso = timestamp.isoformat()

    # Build calibration list: apparent (set) vs actual (measured) for use in code
    calibration = [
        {"set_mw": set_mw, "measured_mw": measured_mw}
        for set_mw, measured_mw, _err_mw, _err_pct in results
    ]
    meta: dict[str, Any] = {
        "timestamp_iso": ts_iso,
        "timestamp_filename": ts_str,
        "wavelength_nm": wavelength_nm,
        "laser_port": laser_port,
        "laser_idn": laser_idn,
        "pm_idn": pm_idn,
        "description": (
            "Apparent (set_mw) = laser setpoint. measured_mw = actual power at sensor/sample. "
            "Use load_calibration() and get_setpoint_for_actual_mw() / get_actual_mw() in code."
        ),
        "calibration": calibration,
    }

    csv_path = OUTPUT_DIR / f"{FILENAME_PREFIX}_{ts_str}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["set_mw", "measured_mw", "error_mw", "error_pct", "wavelength_nm", "timestamp"])
        for (set_mw, measured_mw, err_mw, err_pct) in results:
            w.writerow([set_mw, measured_mw, err_mw, err_pct, wavelength_nm or "", ts_iso])

    json_path = OUTPUT_DIR / f"{FILENAME_PREFIX}_{ts_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return csv_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure Oxxius laser power with PM100D (low power < 5 mW). Saves CSV + JSON."
    )
    parser.add_argument(
        "laser_port",
        nargs="?",
        default="COM4",
        help="Laser serial port (default: COM4)",
    )
    parser.add_argument(
        "laser_baud",
        nargs="?",
        type=int,
        default=19200,
        help="Laser baud rate (default: 19200)",
    )
    parser.add_argument(
        "pm_serial",
        nargs="?",
        default=None,
        help="PM100D serial (e.g. P0031757); default: first PM100D found",
    )
    parser.add_argument(
        "--setpoints",
        type=float,
        nargs="+",
        default=None,
        metavar="MW",
        help=f"Laser setpoints in mW (default: detailed <5 mW: {DEFAULT_SETPOINTS_MW})",
    )
    parser.add_argument(
        "--no-zero",
        action="store_true",
        help="Skip power meter zero (use if already zeroed)",
    )
    parser.add_argument(
        "--wavelength",
        type=float,
        default=None,
        metavar="NM",
        help="Set PM100D wavelength for correction (nm)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not write CSV/JSON",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Do not show applied vs actual mW plot after saving",
    )
    args = parser.parse_args()

    setpoints = args.setpoints if args.setpoints is not None else DEFAULT_SETPOINTS_MW
    setpoints = sorted([p for p in setpoints if 0 < p <= 50])
    if not setpoints:
        print("No setpoints in (0, 50] mW. Use --setpoints e.g. 0.25 0.5 1 2 5")
        sys.exit(1)

    print("=" * 64)
    print("Laser power measurement (Oxxius + PM100D, low power < 5 mW)")
    print("=" * 64)
    print(f"Laser: {args.laser_port} @ {args.laser_baud}")
    print(f"Setpoints (mW): {setpoints}")
    print(f"Save to: {OUTPUT_DIR}")
    print()

    # Connect power meter
    pm_resource = find_pm100d_resource(serial=args.pm_serial)
    if pm_resource is None:
        print("ERROR: PM100D not found. Check USB and serial.")
        sys.exit(1)
    print(f"PM100D: {pm_resource}")

    pm = PM100D(resource=pm_resource)
    pm_idn = ""
    try:
        pm.connect()
        pm_idn = pm.idn()
        print(f"  IDN: {pm_idn}")
        if args.wavelength is not None:
            pm.set_wavelength_nm(args.wavelength)
            print(f"  Wavelength: {args.wavelength} nm")
        pm.configure_power()
        if not args.no_zero:
            print("  Zeroing power meter (laser must be OFF)...")
            pm.zero()
            time.sleep(0.5)
        print()
    except Exception as e:
        print(f"ERROR: Power meter: {e}")
        sys.exit(1)

    # Connect laser
    laser_idn = ""
    try:
        laser = OxxiusLaser(port=args.laser_port, baud=args.laser_baud)
        laser_idn = laser.idn()
        print(f"Laser: {laser_idn}")
        print()
    except Exception as e:
        print(f"ERROR: Laser: {e}")
        pm.close()
        sys.exit(1)

    results = []
    try:
        print(f"{'Set (mW)':>10} {'Measured (mW)':>14} {'Error (mW)':>12} {'Error %':>8}")
        print("-" * 48)
        for set_mw in setpoints:
            laser.set_to_digital_power_control(set_mw)
            time.sleep(0.2)
            laser.emission_on()
            time.sleep(STABILITY_WAIT_S)
            measured_mw = measure_power_stable(pm)
            laser.emission_off()
            time.sleep(0.3)
            err_mw = measured_mw - set_mw
            err_pct = (err_mw / set_mw * 100) if set_mw else 0
            results.append((set_mw, measured_mw, err_mw, err_pct))
            print(f"{set_mw:>10.3f} {measured_mw:>14.4f} {err_mw:>+12.4f} {err_pct:>+7.1f}%")
        print("-" * 48)
    finally:
        # Turn laser off, then close without restoring to manual (keeps emission off)
        try:
            laser.emission_off()
            time.sleep(0.2)
        except Exception:
            pass
        laser.close(restore_to_manual_control=False)
        pm.close()

    print("Laser turned off and connection closed.")

    if not args.no_save and results:
        csv_path, json_path = save_calibration(
            results,
            wavelength_nm=args.wavelength,
            laser_port=args.laser_port,
            laser_idn=laser_idn,
            pm_idn=pm_idn,
        )
        print()
        print("Saved:")
        print(f"  CSV:  {csv_path}")
        print(f"  JSON: {json_path}")
        print("  Use: from Equipment.Laser_Power_Meter.laser_power_calibration import load_calibration, get_setpoint_for_actual_mw")
        if not args.no_plot:
            from Equipment.Laser_Power_Meter.plot_laser_calibration import plot_calibration_csv
            plot_calibration_csv(csv_path)

    print("=" * 64)


if __name__ == "__main__":
    main()
