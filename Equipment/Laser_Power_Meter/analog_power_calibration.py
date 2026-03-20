"""
Analog laser power calibration using:
 - Siglent SDG1032X function generator (DC output on CH1)
 - Thorlabs PM100D power meter

The script sweeps:
 - Software power limits (set manually in the existing laser-control software)
 - Analog control voltage from 0.0 V to 5.0 V in configurable steps

At each (power_limit, voltage) point it measures power and logs results to CSV.
Safety: if measured power exceeds a configurable safe maximum (default 50 mW),
the generator output is turned off and the run is stopped.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

# Ensure project root on sys.path for absolute imports when run as a script
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.Function_Generator.Siglent_SDG1032X import SiglentSDG1032X  # type: ignore
from Equipment.Laser_Power_Meter.pm100d import PM100D, find_pm100d_resource  # type: ignore
from Equipment.Laser_Controller.oxxius import OxxiusLaser  # type: ignore


# Lab-default VISA resource for the Siglent generator so the script can be
# run without command-line arguments. Change this if your unit uses a
# different resource string.
DEFAULT_FG_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"

# Default serial settings for the Oxxius laser.
DEFAULT_LASER_PORT = "COM4"
DEFAULT_LASER_BAUD = 19200

# Directory for analog-control calibration outputs (CSVs, plots).
ANALOG_OUTPUT_DIR = Path(__file__).resolve().parent / "analog_control"

DEFAULT_POWER_LIMITS_MW: Sequence[float] = (5, 10, 15, 20, 25, 30, 40, 50, 60, 70,80, 90,100,150,200,300,330)
DEFAULT_VOLTAGE_START: float = 0.0
DEFAULT_VOLTAGE_STOP: float = 3.0
DEFAULT_VOLTAGE_STEP: float = 0.05
DEFAULT_SETTLE_S: float = 0.75
DEFAULT_SAMPLES_PER_POINT: int = 5
DEFAULT_MAX_SAFE_MW: float = 50.0


@dataclass
class CalibrationPoint:
    power_limit_mw: float
    voltage_v: float
    measured_mw: float
    reading_index: int
    timestamp_iso: str
    status: str


def frange(start: float, stop: float, step: float) -> Iterable[float]:
    """Simple inclusive range for floats (ensures stop is included within tolerance)."""
    if step <= 0:
        raise ValueError("step must be > 0")
    # Add small epsilon to make sure stop is included
    value = start
    while value <= stop + 1e-9:
        yield round(value, 6)
        value += step


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sweep analog control voltage using a Siglent SDG1032X and "
            "measure laser output power with a Thorlabs PM100D."
        )
    )
    parser.add_argument(
        "--fg-resource",
        default=DEFAULT_FG_RESOURCE,
        help=(
            "VISA resource string for Siglent SDG1032X "
            f"(default: {DEFAULT_FG_RESOURCE})."
        ),
    )
    parser.add_argument(
        "--pm-resource",
        default=None,
        help=(
            "Optional VISA resource string for PM100D. "
            "If omitted, uses find_pm100d_resource() / default serial."
        ),
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=1,
        help="Function generator channel for analog control (default: 1).",
    )
    parser.add_argument(
        "--laser-port",
        type=str,
        default=DEFAULT_LASER_PORT,
        help=f"Serial port for Oxxius laser (default: {DEFAULT_LASER_PORT}).",
    )
    parser.add_argument(
        "--laser-baud",
        type=int,
        default=DEFAULT_LASER_BAUD,
        help=f"Baud rate for Oxxius laser (default: {DEFAULT_LASER_BAUD}).",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=str(ANALOG_OUTPUT_DIR / "analog_power_calibration.csv"),
        help="Path to CSV file for results "
        f"(default: {ANALOG_OUTPUT_DIR / 'analog_power_calibration.csv'}).",
    )
    parser.add_argument(
        "--v-start",
        type=float,
        default=DEFAULT_VOLTAGE_START,
        help=f"Start voltage in V (default: {DEFAULT_VOLTAGE_START}).",
    )
    parser.add_argument(
        "--v-stop",
        type=float,
        default=DEFAULT_VOLTAGE_STOP,
        help=f"Stop voltage in V (default: {DEFAULT_VOLTAGE_STOP}).",
    )
    parser.add_argument(
        "--v-step",
        type=float,
        default=DEFAULT_VOLTAGE_STEP,
        help=f"Voltage step in V (default: {DEFAULT_VOLTAGE_STEP}).",
    )
    parser.add_argument(
        "--settle-s",
        type=float,
        default=DEFAULT_SETTLE_S,
        help=f"Settling time after voltage change in seconds (default: {DEFAULT_SETTLE_S}).",
    )
    parser.add_argument(
        "--samples-per-point",
        type=int,
        default=DEFAULT_SAMPLES_PER_POINT,
        help=f"Number of PM100D readings to average at each point (default: {DEFAULT_SAMPLES_PER_POINT}).",
    )
    parser.add_argument(
        "--max-safe-mw",
        type=float,
        default=DEFAULT_MAX_SAFE_MW,
        help=f"Maximum safe measured power in mW before aborting (default: {DEFAULT_MAX_SAFE_MW}).",
    )
    parser.add_argument(
        "--power-limits-mw",
        type=float,
        nargs="*",
        default=list(DEFAULT_POWER_LIMITS_MW),
        help=(
            "Power limits in mW to iterate over. "
            "Defaults to 5 10 15 20 25 30 40 50."
        ),
    )
    return parser.parse_args(argv)


def connect_instruments(
    fg_resource: str,
    pm_resource: Optional[str],
    laser_port: str,
    laser_baud: int,
) -> tuple[SiglentSDG1032X, PM100D, OxxiusLaser]:
    gen = SiglentSDG1032X(resource=fg_resource)
    if not gen.connect():
        raise RuntimeError(f"Failed to connect to function generator at {fg_resource}")

    if pm_resource:
        pm = PM100D(resource=pm_resource)
        pm.connect()
    else:
        resource = find_pm100d_resource()
        if not resource:
            raise RuntimeError("No PM100D found on USB and no --pm-resource provided.")
        pm = PM100D(resource=resource)
        pm.connect()

    laser = OxxiusLaser(port=laser_port, baud=laser_baud)

    return gen, pm, laser


def measure_point(
    pm: PM100D,
    samples: int,
    max_safe_mw: float,
) -> tuple[float, str]:
    """
    Take N measurements from PM100D and return (average_mw, status).
    Status is 'OK' or 'ABORT_SAFETY' if any reading exceeds max_safe_mw.
    """
    readings: List[float] = []
    status = "OK"
    for _ in range(max(1, samples)):
        val = pm.measure_power_mw()
        readings.append(val)
        if val >= max_safe_mw:
            status = "ABORT_SAFETY"
            break
        # Small delay between samples to avoid hammering the instrument
        time.sleep(0.05)
    avg = sum(readings) / len(readings) if readings else 0.0
    return avg, status


def run_calibration(
    gen: SiglentSDG1032X,
    pm: PM100D,
    laser: OxxiusLaser,
    channel: int,
    power_limits_mw: Sequence[float],
    v_start: float,
    v_stop: float,
    v_step: float,
    settle_s: float,
    samples_per_point: int,
    max_safe_mw: float,
) -> List[CalibrationPoint]:
    results: List[CalibrationPoint] = []

    # Basic DC configuration and ensure output is initially OFF
    gen.set_output_load(channel, "50OHM")
    gen.set_dc_level(channel, "0V")
    gen.output(channel, False)

    for pl in power_limits_mw:
        print(f"\n=== Sweeping power limit {pl:.1f} mW (programmed via Oxxius) ===")

        # Program the laser's power limit in APC + analog modulation mode.
        try:
            laser.set_to_analog_modulation_mode(power_mw=pl)
            laser.emission_on()
        except Exception as e:
            print(f"Warning: failed to configure laser to {pl:.1f} mW: {e}")

        # Ensure we start from 0 V and turn output on
        gen.set_dc_level(channel, "0V")
        gen.output(channel, True)

        abort_this_limit = False
        try:
            for v in frange(v_start, v_stop, v_step):
                gen.set_dc_level(channel, f"{v}V")
                time.sleep(max(0.0, settle_s))

                ts = datetime.now(timezone.utc).isoformat()
                avg_mw, status = measure_point(
                    pm=pm,
                    samples=samples_per_point,
                    max_safe_mw=max_safe_mw,
                )

                point = CalibrationPoint(
                    power_limit_mw=pl,
                    voltage_v=v,
                    measured_mw=avg_mw,
                    reading_index=len(results),
                    timestamp_iso=ts,
                    status=status,
                )
                results.append(point)

                print(
                    f"Limit {pl:6.1f} mW | V={v:4.2f} -> {avg_mw:7.3f} mW [{status}]"
                )

                if status == "ABORT_SAFETY":
                    print(
                        f"Measured power {avg_mw:.3f} mW >= max safe "
                        f"{max_safe_mw:.3f} mW. Turning output OFF and stopping this limit."
                    )
                    try:
                        gen.output(channel, False)
                    except Exception:
                        pass
                    try:
                        laser.emission_off()
                    except Exception:
                        pass
                    abort_this_limit = True
                    break
        finally:
            # Always try to return to 0 V and output OFF for this limit
            try:
                gen.set_dc_level(channel, "0V")
            except Exception:
                pass
            try:
                gen.output(channel, False)
            except Exception:
                pass

    return results


def write_csv(path: Path, points: Sequence[CalibrationPoint]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "power_limit_mw",
                "voltage_v",
                "measured_mw",
                "reading_index",
                "timestamp_iso",
                "status",
            ]
        )
        for p in points:
            writer.writerow(
                [
                    f"{p.power_limit_mw:.3f}",
                    f"{p.voltage_v:.4f}",
                    f"{p.measured_mw:.4f}",
                    p.reading_index,
                    p.timestamp_iso,
                    p.status,
                ]
            )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        gen, pm, laser = connect_instruments(
            fg_resource=args.fg_resource,
            pm_resource=args.pm_resource,
            laser_port=args.laser_port,
            laser_baud=args.laser_baud,
        )
    except Exception as e:
        print(f"Error connecting to instruments: {e}")
        return 1

    try:
        print("Connected to function generator, power meter, and laser.")
        print("Starting calibration sweep...")

        points = run_calibration(
            gen=gen,
            pm=pm,
            laser=laser,
            channel=args.channel,
            power_limits_mw=args.power_limits_mw,
            v_start=args.v_start,
            v_stop=args.v_stop,
            v_step=args.v_step,
            settle_s=args.settle_s,
            samples_per_point=args.samples_per_point,
            max_safe_mw=args.max_safe_mw,
        )

        out_path = Path(args.output_file)
        write_csv(out_path, points)
        print(f"\nWrote {len(points)} calibration points to {out_path}")
        return 0
    except KeyboardInterrupt:
        print("\nCalibration aborted by user.")
        return 1
    except Exception as e:
        print(f"\nCalibration failed: {e}")
        return 1
    finally:
        try:
            pm.close()
        except Exception:
            pass
        try:
            gen.disconnect()
        except Exception:
            pass
        try:
            # Restore laser to its standard manual/analog control state.
            laser.close(restore_to_manual_control=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

