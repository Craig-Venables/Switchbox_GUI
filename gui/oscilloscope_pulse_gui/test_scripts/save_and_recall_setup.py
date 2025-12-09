#!/usr/bin/env python3
"""
Save the current TBS1000C setup to an internal slot, reset, then recall it.

Defaults:
  VISA resource: USB0::0x0699::0x03C4::C023684::INSTR
  Setup slot: 1

Usage:
  python gui/oscilloscope_pulse_gui/test_scripts/save_and_recall_setup.py [VISA_RESOURCE] [SLOT]
"""
import sys
import time
from pathlib import Path

# Ensure project root on sys.path (Switchbox_GUI)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C

DEFAULT_RESOURCE = "USB0::0x0699::0x03C4::C023684::INSTR"
DEFAULT_SLOT = 1  # internal setup memory slot


def read_brief_state(scope):
    """Grab a couple of fields to confirm recall worked."""
    try:
        ch1_scale = scope.query("CH1:SCA?").strip()
        time_scale = scope.query("HOR:SCA?").strip()
        probe = scope.query("CH1:PROBE?").strip()
        trig_src = scope.query("TRIG:MAI:EDGE:SOU?").strip()
        trig_lev = scope.query("TRIG:MAI:LEV?").strip()
        return {
            "CH1:SCA": ch1_scale,
            "HOR:SCA": time_scale,
            "CH1:PROBE": probe,
            "TRIG:SOURCE": trig_src,
            "TRIG:LEVEL": trig_lev,
        }
    except Exception:
        return {}


def verify_probe(before, after):
    """Check that probe attenuation survived recall."""
    b = before.get("CH1:PROBE")
    a = after.get("CH1:PROBE")
    if b is None or a is None:
        print("Warning: could not read probe setting before/after.")
        return
    if a != b:
        print(f"ERROR: Probe attenuation mismatch after recall (before={b}, after={a})")
        sys.exit(2)
    print(f"Probe attenuation preserved: {a}")


def main():
    resource = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RESOURCE
    slot = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SLOT

    if len(sys.argv) < 2:
        print(f"No VISA resource provided; defaulting to {DEFAULT_RESOURCE}")
        print("Usage (optional): python save_and_recall_setup.py [VISA_RESOURCE] [SLOT]")

    scope = TektronixTBS1000C(resource=resource, timeout_ms=10000)
    if not scope.connect():
        print("Failed to connect to scope.")
        sys.exit(1)

    try:
        print(f"Reading brief state before save (slot {slot})...")
        before = read_brief_state(scope)
        if before:
            print("Before save:", before)

        print(f"Saving current setup to slot {slot}...")
        scope.write(f"SAV:SET {slot}")
        time.sleep(0.5)

        print("Resetting scope...")
        scope.reset()
        time.sleep(2.0)

        print(f"Recalling setup from slot {slot}...")
        scope.write(f"REC:SET {slot}")
        time.sleep(0.5)

        after = read_brief_state(scope)
        if after:
            print("After recall:", after)
            verify_probe(before, after)

        print("Done.")
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()


