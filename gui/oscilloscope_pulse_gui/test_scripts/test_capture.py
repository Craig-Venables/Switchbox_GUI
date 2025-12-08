#!/usr/bin/env python3
"""
Simple scope-only capture test for TBS1000C.
Configures known-good settings, arms single-shot, waits for trigger,
then reads the waveform and saves results to txt/npz.
Assumes: CH1, 1x probe, 1 V / 1 s pulse provided externally (e.g., SMU).
"""
import time
import sys
from pathlib import Path
import numpy as np

# Ensure project root on sys.path (Switchbox_GUI)
SCRIPT_DIR = Path(__file__).resolve().parent
# Path structure: Switchbox_GUI/gui/oscilloscope_pulse_gui/test_scripts/test_capture.py
PROJECT_ROOT = SCRIPT_DIR.parents[2]  # parents[2] = Switchbox_GUI
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C


def save_results(time_arr, volt_arr, out_base: Path):
    out_txt = out_base.with_suffix(".txt")
    out_npz = out_base.with_suffix(".npz")

    # Save txt (Origin-friendly: no comments, tab-separated)
    with out_txt.open("w", encoding="utf-8") as f:
        f.write("Time(s)\tV_shunt_raw(V)\n")
        for t, v in zip(time_arr, volt_arr):
            f.write(f"{t:.9e}\t{v:.9e}\n")

    # Save npz
    np.savez(out_npz, time=time_arr, voltage=volt_arr)
    print(f"Saved: {out_txt}")
    print(f"Saved: {out_npz}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_capture.py <VISA_RESOURCE> [output_basename]")
        print("Example: python test_capture.py USB0::0x0699::0x03C4::C023684::INSTR")
        sys.exit(1)

    resource = sys.argv[1]
    out_base = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("scope_test_capture")

    scope = TektronixTBS1000C(resource=resource, timeout_ms=40000)
    if not scope.connect():
        print("Failed to connect to scope.")
        sys.exit(1)

    try:
        # Known-good settings
        record_length = 20000   # scope may clamp down at slow timebases
        timebase_s_div = 0.2    # 0.2 s/div → 2 s window
        volts_per_div = 0.2     # 0.2 V/div
        trigger_level_v = 0.04  # 40 mV threshold to avoid noise
        trigger_slope = "RISING"
        trigger_source = "CH1"
        holdoff_s = 3.0

        print("Resetting scope...")
        scope.reset()
        time.sleep(2.0)
        scope.inst.timeout = 40000

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
        scope.set_trigger_slope(trigger_slope)
        scope.set_trigger_level(trigger_level_v)
        scope.set_trigger_holdoff(holdoff_s)

        # Acquisition: single shot
        scope.configure_acquisition(mode="SAMPLE", stop_after="SEQUENCE")
        scope.start_acquisition()  # arms

        print("Scope armed (SEQUENCE).")
        print("Provide a 1 V, 1 s pulse on CH1 now...")

        # Wait for trigger/acquisition to complete (up to ~6 s)
        t0 = time.time()
        while True:
            try:
                state = scope.query("ACQ:STATE?").strip()
            except Exception:
                state = "1"
            if state in ("0", "STOP"):
                break
            if (time.time() - t0) > 6.0:
                print("Timeout waiting for trigger/acquisition.")
                break
            time.sleep(0.05)

        # Read waveform (do not force num_points; let scope return what it has)
        print("Reading waveform...")
        t_arr, v_arr = scope.acquire_waveform(channel=1, format="ASCII", num_points=None)

        if len(t_arr) > 1:
            window = t_arr[-1] - t_arr[0]
            dt = window / (len(t_arr) - 1)
            print(f"Captured {len(t_arr)} points, window {window:.6f} s, dt {dt:.6e} s")
            print(f"Voltage range: {np.min(v_arr):.6e} to {np.max(v_arr):.6e} V")
        else:
            print(f"Captured {len(t_arr)} points (empty?)")

        save_results(t_arr, v_arr, out_base)

    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()

