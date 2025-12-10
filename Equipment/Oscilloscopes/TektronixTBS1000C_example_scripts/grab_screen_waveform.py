#!/usr/bin/env python3
"""
Tektronix TBS1000C – Grab whatever is currently on screen (CH1)
----------------------------------------------------------------
This script DOES NOT change any scope settings. It simply:
  1) Connects to the scope
  2) Reads the screen buffer for CH1 (using the current record length)
  3) Builds a time axis from the scope preamble (falls back to HOR:SCA? if needed)
  4) Saves to:
        grabbed_waveform.txt   (tab-separated, Origin-friendly)
        grabbed_waveform.npz

Usage:
  python grab_screen_waveform.py <VISA_RESOURCE> [output_basename]
Example:
  python grab_screen_waveform.py USB0::0x0699::0x03C4::C023684::INSTR
"""

import sys
from pathlib import Path
import numpy as np

# ==================== DEBUG CONTROL ====================
# Set to False to disable all debug print statements
DEBUG_ENABLED = True

def debug_print(*args, **kwargs):
    """Print debug messages only if DEBUG_ENABLED is True."""
    if DEBUG_ENABLED:
        print(*args, **kwargs)
# =======================================================

# Tektronix TBS1000C has 15 horizontal divisions (not 10!)
HORIZONTAL_DIVISIONS = 15.0


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


def save_waveform(t, v, out_base: Path):
    """
    Save waveform data in Origin-compatible format.
    Origin prefers tab-separated values with headers.
    """
    out_txt = out_base.with_suffix(".txt")
    out_npz = out_base.with_suffix(".npz")
    
    with out_txt.open("w", encoding="utf-8") as f:
        # Origin-compatible header: column names with units
        # Use tab separator (Origin handles this well)
        f.write("Time (s)\tVoltage (V)\n")
        
        # Write data rows - use scientific notation for precision
        # Origin handles both scientific and decimal notation well
        for ti, vi in zip(t, v):
            f.write(f"{ti:.9e}\t{vi:.9e}\n")
    
    # Also save as NPZ for Python reloading
    np.savez(out_npz, time=t, voltage=v)
    print(f"Saved {out_txt} (Origin-compatible format)")
    print(f"Saved {out_npz}")


def save_raw(raw_codes, preamble, raw_str, out_base: Path):
    """
    Save the exact data returned by CURV? plus the parsed preamble.
    Formats as Origin-compatible columns: Index and Raw ADC Code.
    """
    out_raw_txt = out_base.with_name(out_base.name + "_raw.txt")
    out_raw_npz = out_base.with_name(out_base.name + "_raw.npz")

    # Text: preamble as comments, then column-formatted raw ADC codes
    with out_raw_txt.open("w", encoding="utf-8") as f:
        f.write("# Tektronix TBS1000C RAW CURV? capture\n")
        f.write("# Preamble (WFMO/WFMPRE):\n")
        for k, v in preamble.items():
            f.write(f"#   {k}: {v}\n")
        f.write("# Raw ADC codes (comma-separated values from CURV?):\n")
        f.write("# Origin-compatible column format:\n")
        
        # Write header with tab separator (Origin-compatible)
        f.write("Index\tRaw_ADC_Code\n")
        
        # Write each raw ADC code with its index
        for idx, code in enumerate(raw_codes, start=1):
            f.write(f"{idx}\t{code:.0f}\n")
    
    # NPZ: store raw integer codes and preamble for programmatic inspection
    np.savez(out_raw_npz, raw_codes=np.array(raw_codes, dtype=np.float64), preamble=np.array(list(preamble.items()), dtype=object))

    print(f"Saved {out_raw_txt} (Origin-compatible format)")
    print(f"Saved {out_raw_npz}")


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
        # Do not change acquisition settings; just read CH1
        scope.write("DAT:SOU CH1")
        
        # Data format options for Tektronix scopes:
        # DAT:ENC ASCII  - Returns ASCII comma-separated values (what we're using)
        #                  Raw values are integers (-128 to 127 for 8-bit, -32768 to 32767 for 16-bit)
        #                  These are ADC codes that MUST be scaled using YMULT, YOFF, YZERO
        # DAT:ENC RIBINARY - Returns binary data (RI = signed integer, MSB first, faster)
        #                    Same raw ADC codes, just in binary format
        # DAT:ENC RPBINARY - Returns binary data (RP = positive integer, offset by 128)
        # DAT:WID 1 - 1 byte per point (8-bit, range -128 to 127) - CURRENT SETTING
        # DAT:WID 2 - 2 bytes per point (16-bit, range -32768 to 32767, higher resolution)
        #
        # NOTE: Regardless of format, raw values are ALWAYS ADC codes, not voltages!
        #       They must be scaled: V = (code - YOFF) * YMULT + YZERO
        scope.write("DAT:ENC ASCII")
        scope.write("DAT:WID 1")
        
        debug_print("Data format: ASCII, 8-bit (1 byte per point)")
        debug_print("  Raw values are ADC codes (integers), not voltages")
        debug_print("  With 8-bit: valid range is -128 to 127")
        debug_print("  Alternative formats:")
        debug_print("    - DAT:ENC RIBINARY, DAT:WID 2 (16-bit binary, higher resolution)")
        debug_print("    - DAT:ENC RPBINARY (unsigned binary, values offset by 128)")

        preamble = scope.get_waveform_preamble(1)
        
        # DEBUG: Print raw WFMO? response to understand format
        # According to Tektronix TBS1000C Programmer Manual:
        # - WFMO? returns waveform output preamble (scaling factors)
        # - CURV? returns raw ADC codes (integers) that MUST be scaled
        # - There is NO command that returns pre-scaled voltage values
        # - All waveform data via SCPI requires scaling using preamble
        scope.write("DAT:SOU CH1")
        raw_wfmo = scope.query("WFMO?")
        debug_print(f"Raw WFMO? response: {repr(raw_wfmo)}")
        debug_print(f"WFMO? length: {len(raw_wfmo)} characters")
        debug_print(f"")
        debug_print(f"According to Tektronix TBS1000C Programmer Manual:")
        debug_print(f"  - CURV? always returns raw ADC codes (integers)")
        debug_print(f"  - WFMO? returns scaling factors (YMULT, YOFF, YZERO)")
        debug_print(f"  - There is NO SCPI command for pre-scaled voltage values")
        debug_print(f"  - USB CSV uses scope's internal save function (different from SCPI)")
        debug_print(f"  - Scaling formula: V = (code - YOFF) * YMULT + YZERO")
        
        record_len = scope._extract_record_length(preamble)
        try:
            rec_query = scope.query("HOR:RECO?").strip()
            record_len = max(record_len, int(rec_query))
        except Exception:
            pass

        x_incr = preamble.get("XINCR", None)
        x_zero = preamble.get("XZERO", 0.0)
        y_mult = preamble.get("YMULT", None)
        y_off = preamble.get("YOFF", None)
        y_zero = preamble.get("YZERO", 0.0)
        
        debug_print(f"Preamble: record_len={record_len}, XINCR={x_incr}, XZERO={x_zero}")
        debug_print(f"Voltage scaling: YMULT={y_mult}, YOFF={y_off}, YZERO={y_zero}")
        debug_print(f"Full preamble keys: {list(preamble.keys())}")

        scope.write("DAT:STAR 1")
        scope.write(f"DAT:STOP {record_len}")

        data_str = scope.query("CURV?")
        data_points = []
        for value in data_str.split(','):
            try:
                data_points.append(float(value.strip()))
            except ValueError:
                continue
        raw_codes = np.array(data_points, dtype=np.float64)

        # Save the raw (unscaled) data and preamble for debugging/verification
        save_raw(raw_codes, preamble, data_str, out_base)

        # Scale to volts using the preamble
        debug_print(f"Raw ADC codes (first 5): {raw_codes[:5]}")
        debug_print(f"Raw ADC code range: {np.min(raw_codes):.0f} to {np.max(raw_codes):.0f}")
        debug_print(f"  ✓ These values are CORRECT - they're raw ADC integer codes")
        debug_print(f"  Note: With DAT:WID 1 (8-bit), valid range is -128 to 127")
        debug_print(f"        These are INTEGER values from the scope's ADC, not voltages")
        debug_print(f"        They need to be scaled using YMULT, YOFF, YZERO to get volts")
        
        y_values = scope._scale_waveform_values(raw_codes, preamble)
        debug_print(f"Scaled voltages (first 5): {y_values[:5]}")
        debug_print(f"Scaled voltage range: {np.min(y_values):.6f} to {np.max(y_values):.6f} V")
        debug_print(f"")
        debug_print(f"========== COMPARISON WITH USB CSV ==========")
        debug_print(f"USB CSV format: Pre-scaled voltages (already in volts)")
        debug_print(f"SCPI CURV?: Raw ADC codes (integers) that need scaling")
        debug_print(f"  USB CSV shows: -1.024 V")
        debug_print(f"  SCPI scaled to: {y_values[0]:.6f} V")
        if abs(y_values[0] - (-1.024)) < 0.001:
            debug_print(f"  ✓ VALUES MATCH! Scaling is working correctly.")
        debug_print(f"=============================================")
        num_points = len(y_values)

        if num_points > 1:
            if x_incr is None:
                # Fallback: use HOR:SCA? * 15 as total window (TBS1000C has 15 horizontal divisions)
                try:
                    tb_scale = float(scope.query("HOR:SCA?"))
                except Exception:
                    tb_scale = 0.2
                window = tb_scale * HORIZONTAL_DIVISIONS
                debug_print(f"Using timebase scale: {tb_scale:.6f} s/div → {window:.6f} s window ({HORIZONTAL_DIVISIONS:.0f} divisions)")
                time_values = np.linspace(0.0, window, num_points)
            else:
                time_values = scope._build_time_array(num_points, preamble, fallback_scale=None)
                window = time_values[-1] - time_values[0]
                debug_print(f"Time array from preamble: window={window:.6f} s (from {time_values[0]:.6f} to {time_values[-1]:.6f} s)")
                if window <= 0:
                    try:
                        tb_scale = float(scope.query("HOR:SCA?"))
                    except Exception:
                        tb_scale = 0.2
                    window = tb_scale * HORIZONTAL_DIVISIONS
                    debug_print(f"Window was invalid, using timebase fallback: {tb_scale:.6f} s/div → {window:.6f} s ({HORIZONTAL_DIVISIONS:.0f} divisions)")
                    time_values = np.linspace(0.0, window, num_points)
            window = time_values[-1] - time_values[0]
            dt = window / (num_points - 1) if num_points > 1 else 0
            debug_print(f"Captured {num_points} points, window {window:.6f} s, dt {dt:.6e} s")
            debug_print(f"Time range: {time_values[0]:.6f} s to {time_values[-1]:.6f} s")
            debug_print(f"Voltage range: {np.min(y_values):.6e} to {np.max(y_values):.6e} V")
            
            # Compare with USB CSV format expectations
            if y_off is not None and y_mult is not None:
                # Calculate what voltage should be for first sample
                test_code = raw_codes[0] if len(raw_codes) > 0 else -128
                calculated_v = (test_code - y_off) * y_mult + y_zero
                debug_print(f"")
                debug_print(f"========== SCALING VERIFICATION ==========")
                debug_print(f"Raw ADC code: {test_code}")
                debug_print(f"YMULT: {y_mult} V/code")
                debug_print(f"YOFF: {y_off}")
                debug_print(f"YZERO: {y_zero} V")
                debug_print(f"Formula: V = (code - YOFF) * YMULT + YZERO")
                debug_print(f"Calculated: V = ({test_code} - {y_off}) * {y_mult} + {y_zero} = {calculated_v:.6f} V")
                debug_print(f"Actual scaled value: {y_values[0]:.6f} V")
                debug_print(f"USB CSV typically shows voltage already scaled to final value")
                debug_print(f"  (e.g., -1.024 V for a 10x probe with -128 ADC code)")
                debug_print(f"==========================================")
        else:
            time_values = np.array([], dtype=np.float64)
            debug_print(f"Captured {num_points} points (empty?)")

        save_waveform(time_values, y_values, out_base)

    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()

