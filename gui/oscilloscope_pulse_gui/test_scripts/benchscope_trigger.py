#!/usr/bin/env python3
"""
Bench scope trigger test using settings from scope_settings.json
and aligned with Tektronix BenchScopes examples
(see https://github.com/tektronix/Programmatic-Control-Examples/tree/master/Examples/Oscilloscopes/BenchScopes/src).

What it does:
- Loads scope_settings.json (idn, timebase, record length, CH1, trigger).
- Applies those settings to a TBS1000C.
- Arms single-sequence (single-shot), waits for trigger (up to 8 s).
- Reads the captured waveform (CH1) without forcing point count.
- Saves to benchscope_trigger.txt (tab) and benchscope_trigger.npz.

Usage:
  python gui/oscilloscope_pulse_gui/test_scripts/benchscope_trigger.py \
         USB0::0x0699::0x03C4::C023684::INSTR [output_basename]
"""
import sys
import time
import json
from pathlib import Path
import numpy as np

# Ensure project root on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]  # Switchbox_GUI
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C


def load_settings(settings_path: Path):
    with settings_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_waveform(t, v, out_base: Path):
    out_txt = out_base.with_suffix(".txt")
    out_npz = out_base.with_suffix(".npz")

    with out_txt.open("w", encoding="utf-8") as f:
        f.write("Time(s)\tV_shunt_raw(V)\n")
        for ti, vi in zip(t, v):
            f.write(f"{ti:.9e}\t{vi:.9e}\n")
    np.savez(out_npz, time=t, voltage=v)
    print(f"Saved {out_txt}")
    print(f"Saved {out_npz}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python benchscope_trigger.py <VISA_RESOURCE> [output_basename]")
        sys.exit(1)

    resource = sys.argv[1]
    out_base = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("benchscope_trigger")

    settings_path = PROJECT_ROOT / "scope_settings.json"
    if not settings_path.exists():
        print(f"scope_settings.json not found at {settings_path}")
        sys.exit(1)

    settings = load_settings(settings_path)
    scope = TektronixTBS1000C(resource=resource, timeout_ms=40000)

    if not scope.connect():
        print("Failed to connect to scope.")
        sys.exit(1)

    try:
        print("Resetting scope...")
        scope.reset()
        time.sleep(2.0)
        scope.inst.timeout = 40000

        # Apply settings
        tb = settings.get("timebase", {})
        ch1 = settings.get("channel1", {})
        trig = settings.get("trigger", {})

        # Channel setup (CH1)
        scope.write("CH1:PROBE 1")  # Force 1x
        scope.channel_enable(1, True)
        scope.set_channel_coupling(1, ch1.get("coupling", "DC"))
        scope.set_channel_scale(1, float(ch1.get("scale_v_div", 0.2)))
        scope.set_channel_offset(1, float(ch1.get("offset_v", 0.0)))

        # Record length
        scope.set_record_length(int(settings.get("record_length", "20000")))

        # Timebase
        scope.set_timebase_scale(float(tb.get("scale_s_div", 0.2)))
        # Position may be huge in file (50s), skip changing position to avoid offsetting view

        # Trigger
        scope.set_trigger_mode(trig.get("mode", "NORMAL"))
        scope.set_trigger_source(trig.get("source", "CH1"))
        slope = trig.get("slope", "RISING")
        # Normalize slope to valid values: RISE/RISE, FALL/FALL
        slope_norm = str(slope).strip().upper()
        if slope_norm.startswith("R"):
            slope_norm = "RISING"
        elif slope_norm.startswith("F"):
            slope_norm = "FALL"
        else:
            slope_norm = "RISE"
        scope.set_trigger_slope(slope_norm)
        scope.set_trigger_level(float(trig.get("level_v", 0.05)))  # 50 mV from json
        try:
            scope.set_trigger_holdoff(float(trig.get("holdoff_s", 20e-9)))
        except Exception:
            pass

        # Acquisition: single sequence
        scope.configure_acquisition(mode=settings.get("acquisition", {}).get("mode", "SAMPLE"),
                                    stop_after=settings.get("acquisition", {}).get("stop_after", "SEQUENCE"))

        # Arm, then disconnect to avoid VISA conflicts; user fires pulse; reconnect and read
        input("Ready to arm scope. Press Enter, then apply 1 V / 1 s pulse on CH1. "
              "After the pulse, press Enter again to reconnect and read.")
        scope.start_acquisition()
        print("Scope armed (SEQUENCE). Disconnecting now; fire the pulse, then press Enter to continue.")
        scope.disconnect()

        input("Press Enter AFTER the pulse is sent to reconnect and read waveform...")
        if not scope.connect():
            print("Failed to reconnect to scope.")
            sys.exit(1)

        # Verify acquisition state after reconnect
        try:
            state = scope.query("ACQ:STATE?").strip()
            trig_state = scope.query("TRIG:STATE?").strip()
            print(f"Acquisition state after reconnect: {state} (0=STOP,1=RUN), Trigger state: {trig_state}")
        except Exception as e:
            print(f"Warning: could not read acquisition/trigger state: {e}")

        # Read waveform directly (no record-length changes)
        print("Reading waveform...")
        try:
            # Select channel and prepare data format
            scope.write("DAT:SOU CH1")
            scope.write("DAT:ENC ASCII")
            scope.write("DAT:WID 1")

            # Get preamble to know record length and scaling
            preamble = scope.get_waveform_preamble(1)
            record_len = scope._extract_record_length(preamble)
            x_incr = preamble.get("XINCR", None)
            x_zero = preamble.get("XZERO", 0.0)
            y_mult = preamble.get("YMULT", None)
            print(f"Preamble: record_len={record_len}, XINCR={x_incr}, XZERO={x_zero}, YMULT={y_mult}")

            # Read full available screen memory
            scope.write("DAT:STAR 1")
            scope.write(f"DAT:STOP {record_len}")

            data_str = scope.query("CURV?")
            data_points = []
            for value in data_str.split(','):
                try:
                    data_points.append(float(value.strip()))
                except ValueError:
                    continue
            y_values = np.array(data_points, dtype=np.float64)

            # Scale using preamble
            y_values = scope._scale_waveform_values(y_values, preamble)
            num_points = len(y_values)

            # Build time axis with fallback if XINCR missing
            if x_incr is None:
                try:
                    tb_scale = float(scope.query("HOR:SCA?"))
                except Exception:
                    tb_scale = 0.2
                window = tb_scale * 10.0
                time_values = np.linspace(0.0, window, num_points)
            else:
                time_values = scope._build_time_array(num_points, preamble, fallback_scale=None)

        except Exception as e:
            print(f"Failed to read waveform: {e}")
            scope.disconnect()
            sys.exit(1)

        t_arr, v_arr = time_values, y_values
        if len(t_arr) > 1:
            window = t_arr[-1] - t_arr[0]
            dt = window / (len(t_arr) - 1)
            print(f"Captured {len(t_arr)} points, window {window:.6f} s, dt {dt:.6e} s")
            print(f"Voltage range: {np.min(v_arr):.6e} to {np.max(v_arr):.6e} V")
        else:
            print(f"Captured {len(t_arr)} points (empty?)")

        save_results = save_waveform
        save_results(t_arr, v_arr, out_base)

    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()

