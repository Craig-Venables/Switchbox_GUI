#!/usr/bin/env python3
"""
Tektronix TBS1000C – Arm single-shot, then disconnect
-----------------------------------------------------
Sets up CH1, timebase, record length, trigger, arms SEQUENCE,
then disconnects so you can fire the pulse. After firing the pulse,
run grab_screen_waveform.py to read the captured data.

Defaults (adjust in code as needed):
  - Timebase: 0.2 s/div (2 s window)
  - Record length: 20000 (scope may clamp at slow timebases)
  - CH1: 1x probe, DC, 0.2 V/div, 0 offset
  - Trigger: NORMAL, CH1, RISING, 50 mV level, holdoff 3 s

Usage:
  python arm_then_disconnect.py <VISA_RESOURCE>
Example:
  python arm_then_disconnect.py USB0::0x0699::0x03C4::C023684::INSTR
Then fire your pulse, and run grab_screen_waveform.py to read it.
"""

import sys
import time
from pathlib import Path


def find_project_root(start: Path) -> Path:
    p = start
    for _ in range(6):
        if p.name.lower() == "switchbox_gui":
            return p
        if p.parent == p:
            break
        p = p.parent
    return start


# Ensure project root on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = find_project_root(SCRIPT_DIR)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C


def main():
    if len(sys.argv) < 2:
        print("Usage: python arm_then_disconnect.py <VISA_RESOURCE>")
        sys.exit(1)

    resource = sys.argv[1]

    scope = TektronixTBS1000C(resource=resource, timeout_ms=40000)
    if not scope.connect():
        print("Failed to connect to scope.")
        sys.exit(1)

    try:
        print("Resetting scope...")
        scope.reset()
        time.sleep(2.0)
        scope.inst.timeout = 40000

        # Known-good defaults
        record_length = 20000   # scope may clamp at slow timebases
        timebase_s_div = 0.2    # 2 s window
        volts_per_div = 0.2     # 0.2 V/div
        trigger_level_v = 0.05  # 50 mV
        trigger_slope = "RISE"
        trigger_source = "CH1"
        holdoff_s = 3.0

        # Channel setup
        scope.write("CH1:PROBE 1")
        scope.channel_enable(1, True)
        scope.set_channel_coupling(1, "DC")
        scope.set_channel_scale(1, volts_per_div)
        scope.set_channel_offset(1, 0.0)

        # Record length
        scope.set_record_length(record_length)

        # Timebase
        scope.set_timebase_scale(timebase_s_div)

        # Trigger
        scope.set_trigger_mode("NORMAL")
        scope.set_trigger_source(trigger_source)
        slope_norm = str(trigger_slope).strip().upper()
        if slope_norm.startswith("R"):
            slope_norm = "RISING"
        elif slope_norm.startswith("F"):
            slope_norm = "FALLING"
        else:
            slope_norm = "RISING"
        scope.set_trigger_slope(slope_norm)
        scope.set_trigger_level(trigger_level_v)
        try:
            scope.set_trigger_holdoff(holdoff_s)
        except Exception:
            pass

        # Acquisition: single sequence
        scope.configure_acquisition(mode="SAMPLE", stop_after="SEQUENCE")
        scope.start_acquisition()
        print("Scope armed (SEQUENCE). You can now fire the pulse.")

        # Disconnect so you can run the pulse and later grab the screen
        scope.disconnect()
        print("Scope disconnected. Fire the pulse, then run grab_screen_waveform.py to read the capture.")

    finally:
        # Ensure closed if not already
        try:
            scope.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()

