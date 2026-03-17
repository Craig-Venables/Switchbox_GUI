"""
Quick helper script to test Oxxius APC + analog modulation using the
Siglent SDG1032X function generator as the 0–5 V analog control input,
while reading the actual optical power with a Thorlabs PM100D.

Experiment:
  1. Put laser into power-control (APC) mode with analog modulation enabled.
  2. Set laser power setpoint to 5 mW, apply 5 V DC from the function
     generator into the analog control input, measure output.
  3. Change laser power setpoint to 20 mW (still APC + analog), keep 5 V
     applied, measure output again.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

# Ensure project root on sys.path for absolute imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.Laser_Controller.oxxius import OxxiusLaser  # type: ignore
from Equipment.Function_Generator.Siglent_SDG1032X import SiglentSDG1032X  # type: ignore
from Equipment.Laser_Power_Meter.pm100d import PM100D, find_pm100d_resource  # type: ignore


# Lab-default VISA resource for the Siglent generator so this test script can
# be run without command-line arguments. Change this if your unit uses a
# different resource string.
DEFAULT_FG_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test Oxxius APC + analog modulation vs 5 V analog input using "
            "Siglent SDG1032X (and optionally PM100D)."
        )
    )
    parser.add_argument(
        "--laser-port",
        default="COM4",
        help="Serial port for Oxxius laser (default: COM4).",
    )
    parser.add_argument(
        "--laser-baud",
        type=int,
        default=19200,
        help="Baud rate for Oxxius laser (default: 19200).",
    )
    parser.add_argument(
        "--fg-resource",
        default=DEFAULT_FG_RESOURCE,
        help=(
            "VISA resource for Siglent SDG1032X "
            f"(default: {DEFAULT_FG_RESOURCE})."
        ),
    )
    parser.add_argument(
        "--fg-channel",
        type=int,
        default=1,
        help="Function generator channel wired to the analog control input (default: 1).",
    )
    parser.add_argument(
        "--pm-resource",
        default=None,
        help="Optional VISA resource for PM100D. If omitted, uses find_pm100d_resource().",
    )
    parser.add_argument(
        "--v-test",
        type=float,
        default=5.0,
        help="DC voltage to apply from the function generator (default: 5.0 V).",
    )
    parser.add_argument(
        "--wait-s",
        type=float,
        default=2.0,
        help="Wait time after changing conditions before measuring (default: 2.0 s).",
    )
    return parser.parse_args()


def connect_pm(pm_resource: Optional[str]) -> Optional[PM100D]:
    if pm_resource:
        pm = PM100D(resource=pm_resource)
        pm.connect()
        return pm
    resource = find_pm100d_resource()
    if not resource:
        print("WARNING: No PM100D found on USB and no --pm-resource provided; continuing without meter.")
        return None
    pm = PM100D(resource=resource)
    pm.connect()
    return pm


def main() -> int:
    args = parse_args()

    print("=" * 60)
    print("Oxxius APC + analog modulation test with Siglent SDG1032X")
    print("=" * 60)
    print(f"Laser port: {args.laser_port}, baud: {args.laser_baud}")
    print(f"Function generator: {args.fg_resource}, channel: {args.fg_channel}")
    print(f"Analog test voltage: {args.v_test:.2f} V")
    print("=" * 60)

    laser = OxxiusLaser(port=args.laser_port, baud=args.laser_baud)
    gen = SiglentSDG1032X(resource=args.fg_resource)
    pm: Optional[PM100D] = None

    try:
        # Connect instruments
        print("\nConnecting to function generator...")
        if not gen.connect():
            print("ERROR: Failed to connect to function generator.")
            return 1
        print(f"  FG IDN: {gen.idn()}")

        print("Connecting to PM100D...")
        pm = connect_pm(args.pm_resource)
        if pm is not None:
            print(f"  PM100D IDN: {pm.idn()}")

        print("\nLaser identity/status:")
        print(f"  ID: {laser.idn()}")
        print(f"  Status: {laser.get_status()}")
        print(f"  Errors: {laser.get_error()}")

        # Configure function generator channel for DC output, initially 0 V
        ch = args.fg_channel
        gen.set_output_load(ch, "50OHM")
        gen.set_dc_level(ch, "0V")
        gen.output(ch, True)
        print("\nFunction generator configured for DC output (0 V, output ON).")

        # Step 1: 5 mW, APC + analog modulation, then apply Vtest
        print("\nStep 1: Set APC + analog modulation, power setpoint 5 mW.")
        # Use helper to go to analog modulation mode with given power
        res1 = laser.set_to_analog_modulation_mode(power_mw=5)
        print(f"  Commands: {res1}")

        # Ensure emission is ON
        print("  Turning laser emission ON (DL 1)...")
        print(f"  Reply: {laser.emission_on()}")

        print(f"\nApplying {args.v_test:.2f} V DC from function generator...")
        gen.set_dc_level(ch, f"{args.v_test}V")
        time.sleep(args.wait_s)

        if pm is not None:
            power1 = pm.measure_power_mw()
            print(f"  Measured power at 5 mW setpoint, {args.v_test:.2f} V: {power1:.3f} mW")
        else:
            print("  (No PM100D measurement; observe power meter manually.)")

        # Step 2: 20 mW, same APC + analog, same 5 V applied
        print("\nStep 2: Increase power setpoint to 20 mW (still APC + analog modulation).")
        print(f"  Setting power to 20 mW via PM command...")
        print(f"  Reply: {laser.set_power(20)}")
        time.sleep(0.5)
        print(f"  Current power setpoint reply: {laser.get_power()}")

        print(f"\nKeeping {args.v_test:.2f} V DC applied, waiting {args.wait_s:.1f} s...")
        time.sleep(args.wait_s)

        if pm is not None:
            power2 = pm.measure_power_mw()
            print(f"  Measured power at 20 mW setpoint, {args.v_test:.2f} V: {power2:.3f} mW")
        else:
            print("  (No PM100D measurement; observe power meter manually.)")

        print("\nTest complete. You should now have seen how the output changes when")
        print("the power setpoint is changed from 5 mW to 20 mW with the same analog")
        print("control voltage applied.")
        return 0

    except KeyboardInterrupt:
        print("\nAborted by user.")
        return 1
    finally:
        print("\nCleaning up...")
        try:
            # Set function generator back to 0 V and output OFF
            gen.set_dc_level(args.fg_channel, "0V")
        except Exception:
            pass
        try:
            gen.output(args.fg_channel, False)
        except Exception:
            pass
        try:
            gen.disconnect()
        except Exception:
            pass

        try:
            if pm is not None:
                pm.close()
        except Exception:
            pass

        # Use default close behaviour so the laser is left in standard
        # manual/analog modulation state as per documentation.
        try:
            laser.close(restore_to_manual_control=True)
        except Exception:
            pass

        print("Cleanup done.")


if __name__ == "__main__":
    raise SystemExit(main())

