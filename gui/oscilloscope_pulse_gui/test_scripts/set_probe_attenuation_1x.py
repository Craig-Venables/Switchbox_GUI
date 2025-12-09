#!/usr/bin/env python3
"""
Drive the Tektronix TBS1000C front panel to set CH1 probe attenuation to 1x
using the knob/menu sequence (no direct SCPI found in TBS1000C manual):

Order:
  1) FPANEL:PRESS CH1
  2) FPANEL:PRESS RMENU3
  3) FPANEL:TURN GPKNOB,-3   # anticlockwise 3 detents
  4) FPANEL:PRESS GPKNOB     # confirm

Usage:
  python gui/oscilloscope_pulse_gui/test_scripts/set_probe_attenuation_1x.py <VISA_RESOURCE>
Example:
  python gui/oscilloscope_pulse_gui/test_scripts/set_probe_attenuation_1x.py USB0::0x0699::0x03C4::C023684::INSTR
"""
import sys
import time
from pathlib import Path

# Ensure project root on sys.path (Switchbox_GUI)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]  # Switchbox_GUI
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C


def press(scope, control: str, wait: float = 0.25):
    scope.write(f"FPANEL:PRESS {control}")
    time.sleep(wait)


def turn(scope, knob: str, detents: int, wait: float = 0.25):
    scope.write(f"FPANEL:TURN {knob},{detents}")
    time.sleep(wait)


DEFAULT_RESOURCE = "USB0::0x0699::0x03C4::C023684::INSTR"


def set_probe_to_1x(scope):
    """
    Try SCPI first (PROBEFACTOR then PROBE). If those fail, fall back to FPANEL.
    Returns the final readback string if available.
    """
    # Attempt PROBEFACTOR (preferred on TBS1000C)
    try:
        scope.write("CH1:PROBEFACTOR 1")
        time.sleep(0.2)
        probe = scope.query("CH1:PROBEFACTOR?").strip()
        if probe in ("1", "1.0", "1.00", "1.000000"):
            return probe
    except Exception:
        pass

    # Attempt legacy PROBE command
    try:
        scope.write("CH1:PROBE 1")
        time.sleep(0.2)
        probe = scope.query("CH1:PROBE?").strip()
        if probe.startswith("1"):
            return probe
    except Exception:
        pass

    # Fall back to front-panel simulation
    print("SCPI probe-set failed; using front-panel sequence...")
    press(scope, "CH1")
    press(scope, "RMENU3")
    turn(scope, "GPKNOB", -3)  # move to 1x entry (anticlockwise)
    press(scope, "GPKNOB")
    time.sleep(0.3)
    try:
        probe = scope.query("CH1:PROBE?").strip()
        return probe
    except Exception:
        return None


def main():
    # Allow running without args by falling back to the known resource
    resource = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RESOURCE
    if len(sys.argv) < 2:
        print(f"No VISA resource provided; defaulting to {DEFAULT_RESOURCE}")
        print("Usage (optional): python set_probe_attenuation_1x.py <VISA_RESOURCE>")
    scope = TektronixTBS1000C(resource=resource, timeout_ms=10000)

    if not scope.connect():
        print("Failed to connect to scope.")
        sys.exit(1)

    try:
        # Start from defaults per request
        print("Resetting scope to defaults...")
        scope.reset()
        time.sleep(2.0)

        print("Setting CH1 probe attenuation to 1x...")
        probe = set_probe_to_1x(scope)

        # Readback
        if probe is None:
            try:
                probe = scope.query("CH1:PROBE?").strip()
            except Exception:
                probe = "UNKNOWN"

        print(f"Probe setting after attempt: {probe}")
        if not str(probe).startswith("1"):
            print("ERROR: Probe attenuation does not appear to be 1x.")
            sys.exit(2)

        print("Done.")
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()


