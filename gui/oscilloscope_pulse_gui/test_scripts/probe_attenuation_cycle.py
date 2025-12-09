#!/usr/bin/env python3
"""
Cycle through multiple probe-attenuation set attempts for TBS1000C CH1.
After each attempt, show readbacks and wait for Enter before trying next.

Order of attempts:
  1) SCPI: CH1:PROBEFACTOR 1 / read CH1:PROBEFACTOR?
  2) SCPI: CH1:PROBE 1 / read CH1:PROBE?
  3) FPANEL: CH1, RMENU3, GPKNOB -3, press (aim for 1x)
  4) FPANEL: CH1, RMENU3, GPKNOB -4, press (alternate)
  5) FPANEL: CH1, RMENU3, GPKNOB -2, press (alternate)

Defaults:
  VISA resource: USB0::0x0699::0x03C4::C023684::INSTR
  No reset is performed automatically.

Usage:
  python gui/oscilloscope_pulse_gui/test_scripts/probe_attenuation_cycle.py [VISA_RESOURCE]
Press Enter between attempts to proceed to the next method.
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


def press(scope, control: str, wait: float = 0.25):
    scope.write(f"FPANEL:PRESS {control}")
    time.sleep(wait)


def turn(scope, knob: str, detents: int, wait: float = 0.25):
    scope.write(f"FPANEL:TURN {knob},{detents}")
    time.sleep(wait)


def readback(scope):
    """Return probefactor, probe, and last system error."""
    pf = None
    pb = None
    err = None
    try:
        pf = scope.query("CH1:PROBEFACTOR?").strip()
    except Exception:
        pf = "ERR"
    try:
        pb = scope.query("CH1:PROBE?").strip()
    except Exception:
        pb = "ERR"
    try:
        err = scope.query("SYST:ERR?").strip()
    except Exception:
        err = "ERR"
    return pf, pb, err


def attempt_probe_factor(scope):
    scope.write("CH1:PROBEFACTOR 1")
    time.sleep(0.2)


def attempt_probe(scope):
    scope.write("CH1:PROBE 1")
    time.sleep(0.2)


def attempt_panel(scope, detents: int):
    press(scope, "CH1", wait=0.15)
    press(scope, "RMENU3", wait=0.15)
    turn(scope, "GPKNOB", detents, wait=0.2)
    press(scope, "GPKNOB", wait=0.25)
    time.sleep(0.2)


ATTEMPTS = [
    ("SCPI PROBEFACTOR 1", attempt_probe_factor),
    ("SCPI PROBE 1", attempt_probe),
    ("FPANEL detents -3", lambda s: attempt_panel(s, -3)),
    ("FPANEL detents -4", lambda s: attempt_panel(s, -4)),
    ("FPANEL detents -2", lambda s: attempt_panel(s, -2)),
]


def main():
    resource = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RESOURCE
    if len(sys.argv) < 2:
        print(f"No VISA resource provided; defaulting to {DEFAULT_RESOURCE}")
        print("Usage (optional): python probe_attenuation_cycle.py [VISA_RESOURCE]")

    scope = TektronixTBS1000C(resource=resource, timeout_ms=10000)
    if not scope.connect():
        print("Failed to connect to scope.")
        sys.exit(1)

    try:
        print("No reset is performed automatically. Ensure the scope is ready.")
        for name, fn in ATTEMPTS:
            input(f"\nPress Enter to try: {name} ...")
            try:
                fn(scope)
            except Exception as e:
                print(f"{name} raised exception: {e}")
            pf, pb, err = readback(scope)
            print(f"{name} -> PROBEFACTOR?={pf}, PROBE?={pb}, SYST:ERR?={err}")
        print("\nDone cycling attempts.")
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()


