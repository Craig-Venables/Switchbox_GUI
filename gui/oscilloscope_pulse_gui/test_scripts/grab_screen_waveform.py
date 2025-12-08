#!/usr/bin/env python3
"""
Grab whatever is currently displayed on CH1 of the Tektronix TBS1000C
without reconfiguring the scope. Saves to:
  - grabbed_waveform.txt (tab-separated, Origin-friendly)
  - grabbed_waveform.npz

Usage:
  python gui/oscilloscope_pulse_gui/test_scripts/grab_screen_waveform.py <VISA_RESOURCE> [output_basename]
Example:
  python gui/oscilloscope_pulse_gui/test_scripts/grab_screen_waveform.py USB0::0x0699::0x03C4::C023684::INSTR
"""

import sys
from pathlib import Path
import numpy as np

# Ensure project root on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]  # Switchbox_GUI
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C


def save_waveform(t, v, out_base: Path):
    out_txt = out_base.with_suffix(".txt")
    out_npz = out_base.with_suffix(".npz")
    with out_txt.open("w", encoding="utf-8") as f:
        f.write("Time(s)\tV_raw(V)\n")
        for ti, vi in zip(t, v):
            f.write(f"{ti:.9e}\t{vi:.9e}\n")
    np.savez(out_npz, time=t, voltage=v)
    print(f"Saved {out_txt}")
    print(f"Saved {out_npz}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python grab_screen_waveform.py <VISA_RESOURCE> [output_basename]")
        sys.exit(1)

    resource = sys.argv[1]
    out_base = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("grabbed_waveform")

    scope = TektronixTBS1000C(resource=resource, timeout_ms=20000)
    if not scope.connect():
        print("Failed to connect to scope.")
        sys.exit(1)

    try:
        # Do not change any acquisition or record length settings; just read what's on screen
        scope.write("DAT:SOU CH1")
        scope.write("DAT:ENC ASCII")
        scope.write("DAT:WID 1")

        preamble = scope.get_waveform_preamble(1)
        record_len = scope._extract_record_length(preamble)
        # Prefer HOR:RECO? if available (sometimes preamble NR_PT is smaller)
        try:
            rec_query = scope.query("HOR:RECO?").strip()
            record_len = max(record_len, int(rec_query))
        except Exception:
            pass
        x_incr = preamble.get("XINCR", None)
        x_zero = preamble.get("XZERO", 0.0)
        y_mult = preamble.get("YMULT", None)
        print(f"Preamble: record_len={record_len}, XINCR={x_incr}, XZERO={x_zero}, YMULT={y_mult}")

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
        y_values = scope._scale_waveform_values(y_values, preamble)
        num_points = len(y_values)

        if num_points > 1:
            if x_incr is None:
                # Fallback: use HOR:SCA? * 10 as total window
                try:
                    tb_scale = float(scope.query("HOR:SCA?"))
                except Exception:
                    tb_scale = 0.2
                window = tb_scale * 10.0
                time_values = np.linspace(0.0, window, num_points)
            else:
                time_values = scope._build_time_array(num_points, preamble, fallback_scale=None)
                window = time_values[-1] - time_values[0]
                if window <= 0:
                    # Safety fallback
                    try:
                        tb_scale = float(scope.query("HOR:SCA?"))
                    except Exception:
                        tb_scale = 0.2
                    window = tb_scale * 10.0
                    time_values = np.linspace(0.0, window, num_points)
            window = time_values[-1] - time_values[0]
            dt = window / (num_points - 1) if num_points > 1 else 0
            print(f"Captured {num_points} points, window {window:.6f} s, dt {dt:.6e} s")
            print(f"Voltage range: {np.min(y_values):.6e} to {np.max(y_values):.6e} V")
        else:
            time_values = np.array([], dtype=np.float64)
            print(f"Captured {num_points} points (empty?)")

        save_waveform(time_values, y_values, out_base)

    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()

