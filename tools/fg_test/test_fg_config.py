# -*- coding: utf-8 -*-
"""
SDG1032X Function Generator Configuration Test
===============================================
Standalone script to verify that the Siglent SDG1032X accepts and applies
the settings sent by the Laser FG Scope GUI.

Run from the project root:
    python tools/fg_test/test_fg_config.py

The script will:
  1. Connect to the FG
  2. Run write-then-readback tests for each relevant parameter
  3. Print a clear PASS / FAIL / WARN table

Paste the full terminal output back to the developer to diagnose issues.
"""

from __future__ import annotations

import sys
import os
import time

# Allow running from any directory
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# =============================================================================
# *** EDIT THESE TO MATCH YOUR GUI SETTINGS ***
# =============================================================================
FG_ADDRESS     = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"

PULSE_HIGH_V   = 3.3        # V  - high level
PULSE_LOW_V    = 0.0        # V  - low level
PULSE_WIDTH_NS = 200_000    # ns (enter same value as in GUI "Pulse width (ns)" field)
PULSE_RATE_HZ  = 1_600      # Hz - rep rate
BURST_COUNT    = 2          # pulses per burst
# =============================================================================

FREQ_TOL_HZ  = 1.0    # Hz  - pass tolerance
VOLT_TOL_V   = 0.05   # V   - pass tolerance
TIME_TOL_PCT = 2.0    # %   - pulse-width pass tolerance (also min 10 ns absolute)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def banner(title):
    print()
    print("-" * 70)
    print("  " + title)
    print("-" * 70)


def result(label, expected, got, ok, warn=False):
    if ok:
        status = "PASS"
    elif warn:
        status = "WARN"
    else:
        status = "FAIL"
    print("  [%s]  %-30s  expected=%-18s  got=%s" % (status, label, str(expected), str(got)))


def parse_bswv(resp):
    """Parse 'C1:BSWV WVTP,PULSE,FRQ,...' -> {'WVTP': 'PULSE', 'FRQ': '1600HZ', ...}

    Note: the SDG1032X returns pulse width as 'WIDTH' (not 'PWID').
    This function also copies WIDTH -> PWID so callers can use either key.
    """
    if "BSWV" in resp:
        resp = resp.split("BSWV", 1)[-1].strip()
    parts = [p.strip() for p in resp.split(",")]
    d = {}
    it = iter(parts)
    for k in it:
        try:
            v = next(it)
        except StopIteration:
            break
        d[k.upper()] = v
    # The FG uses WIDTH in its response; mirror it as PWID for convenience
    if "WIDTH" in d and "PWID" not in d:
        d["PWID"] = d["WIDTH"] + "S"   # WIDTH is bare seconds, e.g. "0.0002"
    return d


def parse_btwv(resp):
    """Parse 'C1:BTWV STATE,ON,TRSR,...,CARR,WVTP,...' -> {'STATE': 'ON', 'TRSR': '...', ...}

    The BTWV response embeds a CARR (carrier) sub-block after GATE_NCYC.
    Parsing stops at CARR to avoid its nested key/value pairs corrupting the dict.
    """
    if "BTWV" in resp:
        resp = resp.split("BTWV", 1)[-1].strip()
    # Truncate at CARR sub-block (contains nested waveform params that break simple parsing)
    if ",CARR," in resp:
        resp = resp.split(",CARR,")[0]
    parts = [p.strip() for p in resp.split(",")]
    d = {}
    it = iter(parts)
    for k in it:
        try:
            v = next(it)
        except StopIteration:
            break
        d[k.upper()] = v
    return d


def to_seconds(s):
    """Convert '200US', '100NS', '1MS', '0.5S' -> float seconds."""
    s = s.strip().upper()
    for suffix, mult in (("MS", 1e-3), ("US", 1e-6), ("NS", 1e-9), ("PS", 1e-12), ("S", 1.0)):
        if s.endswith(suffix):
            return float(s[:-len(suffix)]) * mult
    return float(s)


def to_hz(s):
    """Convert '1600HZ', '1KHZ', '1.6KHZ' -> float Hz."""
    s = s.strip().upper()
    for suffix, mult in (("MHZ", 1e6), ("KHZ", 1e3), ("HZ", 1.0)):
        if s.endswith(suffix):
            return float(s[:-len(suffix)]) * mult
    return float(s)


def to_volts(s):
    """Convert '3.3V', '3.3', '3300MV' -> float volts."""
    s = s.strip().upper()
    if s.endswith("MV"):
        return float(s[:-2]) * 1e-3
    if s.endswith("V"):
        return float(s[:-1])
    return float(s)


def fmt_time(s_val):
    """Format seconds as human-readable time string."""
    if s_val >= 1.0:
        return "%.6g S" % s_val
    if s_val * 1e3 >= 1.0:
        return "%.6g mS" % (s_val * 1e3)
    if s_val * 1e6 >= 1.0:
        return "%.6g uS" % (s_val * 1e6)
    return "%.6g nS" % (s_val * 1e9)


def fmt_pwid(s_val):
    """Format the PWID parameter the same way the driver does."""
    if s_val >= 1.0:
        return "%.6gS" % s_val
    if s_val * 1e3 >= 1.0:
        return "%.6gMS" % (s_val * 1e3)
    if s_val * 1e6 >= 1.0:
        return "%.6gUS" % (s_val * 1e6)
    return "%.6gNS" % (s_val * 1e9)


# ---------------------------------------------------------------------------
# Main test sequence
# ---------------------------------------------------------------------------

def run_tests(inst):
    fails = 0

    def w(cmd):
        print("  >> %s" % cmd)
        inst.write(cmd)
        time.sleep(0.05)

    def q(cmd):
        r = inst.query(cmd).strip()
        print("  << %s" % r)
        return r

    pw_s   = PULSE_WIDTH_NS * 1e-9
    pw_str = fmt_pwid(pw_s)

    bswv_cmd = ("C1:BSWV WVTP,PULSE,"
                "FRQ,%.6g,"
                "HLEV,%.6g,"
                "LLEV,%.6g,"
                "PWID,%s") % (PULSE_RATE_HZ, PULSE_HIGH_V, PULSE_LOW_V, pw_str)

    # NOTE: combined BTWV command silently drops TRSR on this firmware.
    # The fixed driver now sends each parameter as a separate command.

    # ------------------------------------------------------------------
    # 0. Identity
    # ------------------------------------------------------------------
    banner("0. Identity")
    idn = q("*IDN?")
    print("  IDN: %s" % idn)

    # ------------------------------------------------------------------
    # 1. Reset
    # ------------------------------------------------------------------
    banner("1. Reset to factory state")
    w("*RST")
    time.sleep(1.5)
    print("  Reset complete (waited 1.5 s)")

    # ------------------------------------------------------------------
    # 2. Set BSWV (pulse shape) ONLY -- no burst yet
    # ------------------------------------------------------------------
    banner("2. Set BSWV (pulse shape) with no burst")
    print("  Command: %s" % bswv_cmd)
    w(bswv_cmd)
    time.sleep(0.1)

    resp = q("C1:BSWV?")
    d = parse_bswv(resp)
    print("  Parsed:  %s" % d)

    wvtp = d.get("WVTP", "")
    ok = wvtp.upper() == "PULSE"
    result("WVTP", "PULSE", wvtp, ok)
    if not ok:
        fails += 1

    frq_str = d.get("FRQ", "0HZ")
    try:
        frq_got = to_hz(frq_str)
        ok = abs(frq_got - PULSE_RATE_HZ) <= FREQ_TOL_HZ
        result("FRQ", "%.6g Hz" % PULSE_RATE_HZ, "%.6g Hz" % frq_got, ok)
        if not ok:
            fails += 1
    except Exception as e:
        result("FRQ", "%.6g Hz" % PULSE_RATE_HZ, "parse err: %s" % e, False)
        fails += 1

    hlev_str = d.get("HLEV", "ERR")
    try:
        hlev_got = to_volts(hlev_str)
        ok = abs(hlev_got - PULSE_HIGH_V) <= VOLT_TOL_V
        result("HLEV", "%.3g V" % PULSE_HIGH_V, "%.3g V" % hlev_got, ok)
        if not ok:
            fails += 1
    except Exception as e:
        result("HLEV", "%.3g V" % PULSE_HIGH_V, "parse err: %s" % e, False)
        fails += 1

    llev_str = d.get("LLEV", "ERR")
    try:
        llev_got = to_volts(llev_str)
        ok = abs(llev_got - PULSE_LOW_V) <= VOLT_TOL_V
        result("LLEV", "%.3g V" % PULSE_LOW_V, "%.3g V" % llev_got, ok)
        if not ok:
            fails += 1
    except Exception as e:
        result("LLEV", "%.3g V" % PULSE_LOW_V, "parse err: %s" % e, False)
        fails += 1

    pwid_str = d.get("PWID", "ERR")
    try:
        pwid_got = to_seconds(pwid_str)
        tol = max(pw_s * TIME_TOL_PCT / 100.0, 10e-9)
        ok = abs(pwid_got - pw_s) <= tol
        result("PWID", fmt_time(pw_s), "%s  (%s)" % (fmt_time(pwid_got), pwid_str), ok)
        if not ok:
            fails += 1
    except Exception as e:
        result("PWID", fmt_time(pw_s), "parse err: %s" % e, False)
        fails += 1

    # ------------------------------------------------------------------
    # 3. Enable burst -- corrected order + MAN trigger source
    #
    #    Findings from previous test run:
    #    - BUS is not valid on firmware 1.01.01.33; use MAN instead
    #    - STATE,ON must come FIRST; sending it last resets TIME to 1
    #    - PRD is read-only; writing it silently turns STATE=OFF
    # ------------------------------------------------------------------
    banner("3. Enable burst -- corrected order (STATE first, then params)")
    print("  Sending each BTWV parameter as its own command:")

    # 3a. Enable burst FIRST (prevents STATE,ON from resetting later params)
    w("C1:BTWV STATE,ON")
    # 3b. Burst mode
    w("C1:BTWV TRMD,NCYC")
    # 3c. Cycle count after STATE,ON
    w("C1:BTWV TIME,%d" % BURST_COUNT)
    # 3d. Trigger source: MAN = software trigger (C1:TRIG).
    #     BUS is not valid on this firmware and is silently ignored.
    w("C1:BTWV TRSR,MAN")
    time.sleep(0.1)
    print("  NOTE: NOT sending PRD -- it is read-only and disables burst when written")

    resp_btwv = q("C1:BTWV?")
    db = parse_btwv(resp_btwv)
    print("  Parsed (pre-CARR):  %s" % db)

    ok = db.get("STATE", "").upper() == "ON"
    result("BTWV STATE", "ON", db.get("STATE", "ERR"), ok)
    if not ok:
        fails += 1

    # GATE_NCYC shows the actual burst type; TRMD readback may say OFF
    gate_ncyc = db.get("GATE_NCYC", db.get("TRMD", ""))
    ok = gate_ncyc.upper() in ("NCYC", "")   # empty = check GATE_NCYC field below
    # Prefer GATE_NCYC field
    gate_val = db.get("GATE_NCYC", "missing")
    ok = gate_val.upper() == "NCYC"
    result("BTWV GATE_NCYC", "NCYC", gate_val, ok, warn=not ok)
    if not ok:
        print("  (WARN only -- TRMD,NCYC may show as GATE_NCYC in readback)")

    # THE KEY CHECK: TRSR must now be BUS after separate command
    trsr_val = db.get("TRSR", "missing")
    ok = trsr_val.upper() in ("BUS", "MAN")
    result("BTWV TRSR (separate cmd)", "BUS or MAN", trsr_val, ok)
    if not ok:
        fails += 1
        print("  !! TRSR is still %s -- FG will auto-fire at internal rate, "
              "not wait for C1:TRIG !!" % trsr_val)

    for key in ("TIME", "NCYC", "CNT"):
        if key in db:
            try:
                cnt = int(float(db[key]))
                ok = cnt == BURST_COUNT
                result("BTWV count (%s)" % key, str(BURST_COUNT), str(cnt), ok)
                if not ok:
                    fails += 1
            except Exception:
                pass
            break

    # PRD is read-only -- do NOT check or write it.
    # With TRSR=MAN the FG only fires on C1:TRIG; PRD is irrelevant.
    print("  (PRD is read-only on this firmware -- not checked or written)")

    # ------------------------------------------------------------------
    # 4. Read BSWV AFTER burst enable -- check for firmware reset
    # ------------------------------------------------------------------
    banner("4. BSWV readback AFTER burst enable (firmware reset check)")
    print("  If any BSWV param differs here, BTWV STATE,ON wiped it.")

    resp2 = q("C1:BSWV?")
    d2 = parse_bswv(resp2)
    print("  Parsed:  %s" % d2)

    wvtp2 = d2.get("WVTP", "")
    ok = wvtp2.upper() == "PULSE"
    result("WVTP still PULSE?", "PULSE", wvtp2, ok, warn=not ok)
    if not ok:
        print("  !! BSWV WVTP was reset by BTWV enable -- "
              "set_pulse_shape MUST run after enable_burst !!")

    pwid2_str = d2.get("PWID", "missing")
    try:
        pwid2 = to_seconds(pwid2_str)
        tol = max(pw_s * TIME_TOL_PCT / 100.0, 10e-9)
        ok = abs(pwid2 - pw_s) <= tol
        result("PWID still correct?", fmt_time(pw_s),
               "%s  (%s)" % (fmt_time(pwid2), pwid2_str), ok, warn=not ok)
        if not ok:
            print("  !! PWID was reset by BTWV enable -- confirmed BSWV wipe !!")
    except Exception as e:
        result("PWID still correct?", fmt_time(pw_s),
               "parse err: %s" % e, False, warn=True)

    # ------------------------------------------------------------------
    # 5. Re-apply BSWV AFTER burst (the correct order used by the GUI)
    # ------------------------------------------------------------------
    banner("5. Re-apply BSWV after burst enable (correct GUI order)")
    print("  Command: %s" % bswv_cmd)
    w(bswv_cmd)
    time.sleep(0.1)

    resp3 = q("C1:BSWV?")
    d3 = parse_bswv(resp3)
    print("  Parsed:  %s" % d3)

    pwid3_str = d3.get("PWID", "missing")
    try:
        pwid3 = to_seconds(pwid3_str)
        tol = max(pw_s * TIME_TOL_PCT / 100.0, 10e-9)
        ok = abs(pwid3 - pw_s) <= tol
        result("PWID after re-apply", fmt_time(pw_s),
               "%s  (%s)" % (fmt_time(pwid3), pwid3_str), ok)
        if not ok:
            fails += 1
    except Exception as e:
        result("PWID after re-apply", fmt_time(pw_s),
               "parse err: %s" % e, False)
        fails += 1

    hlev3_str = d3.get("HLEV", "ERR")
    try:
        hlev3 = to_volts(hlev3_str)
        ok = abs(hlev3 - PULSE_HIGH_V) <= VOLT_TOL_V
        result("HLEV after re-apply", "%.3g V" % PULSE_HIGH_V,
               "%.3g V  (%s)" % (hlev3, hlev3_str), ok)
        if not ok:
            fails += 1
    except Exception as e:
        result("HLEV after re-apply", "%.3g V" % PULSE_HIGH_V,
               "parse err: %s" % e, False)
        fails += 1

    # ------------------------------------------------------------------
    # 6. Output housekeeping (LOAD, AMPL limit, SYNC, burst period)
    # ------------------------------------------------------------------
    banner("6. Output housekeeping (LOAD,HZ / AMPL,OFF / SYNC)")
    print("  Tracking BTWV STATE after each OUTP command:")
    resp_pre = q("C1:BTWV?")
    db_pre = parse_btwv(resp_pre)
    print("  BTWV before housekeeping: %s" % db_pre)

    for outp_cmd in ("C1:OUTP LOAD,HZ", "C1:OUTP AMPL,OFF", "C1:OUTP SYNC,ON", "C1:OUTP PLRT,NOR"):
        w(outp_cmd)
        resp_step = q("C1:BTWV?")
        db_step = parse_btwv(resp_step)
        print("    after %-18s -> STATE=%s TRSR=%s TIME=%s" % (
            outp_cmd,
            db_step.get("STATE", "missing"),
            db_step.get("TRSR", "missing"),
            db_step.get("TIME", "missing"),
        ))
    # PRD is read-only on firmware 1.01.01.33 -- do NOT write it.
    # TRSR=MAN means the FG only fires on C1:TRIG, so no safety period needed.
    time.sleep(0.1)

    resp_outp = q("C1:OUTP?")
    print("  Full OUTP response: %s" % resp_outp)
    load_ok = "HZ" in resp_outp.upper() or "HIGHZ" in resp_outp.upper()
    result("OUTP LOAD=HZ", "HZ in response", resp_outp, load_ok, warn=not load_ok)

    resp_btwv2 = q("C1:BTWV?")
    db2 = parse_btwv(resp_btwv2)
    print("  BTWV after housekeeping: %s" % db2)

    ok = db2.get("STATE", "").upper() == "ON"
    result("BTWV still ON after housekeeping", "ON", db2.get("STATE", "ERR"), ok)
    if not ok:
        fails += 1
        print("  !! Burst was disabled by a housekeeping command !!")

    trsr2 = db2.get("TRSR", "missing")
    ok = trsr2.upper() in ("MAN", "BUS")
    result("TRSR still MAN after housekeeping", "MAN", trsr2, ok, warn=not ok)

    # ------------------------------------------------------------------
    # 7. Enable output, fire burst, then turn off
    # ------------------------------------------------------------------
    banner("7. Enable output + fire one burst + turn off")
    w("C1:OUTP ON")
    time.sleep(0.2)
    print("  Sending C1:TRIG ...")
    w("C1:TRIG")
    time.sleep(0.5)
    print("  Burst fired -- check oscilloscope or scope for %d pulse(s)" % BURST_COUNT)

    w("C1:OUTP OFF")
    time.sleep(0.1)

    outp_after = q("C1:OUTP?")
    off_ok = "OFF" in outp_after.upper() or "STATE,OFF" in outp_after.upper()
    result("Output OFF after burst", "OFF in response", outp_after, off_ok)

    bswv_after = q("C1:BSWV?")
    d_after = parse_bswv(bswv_after)
    wvtp_after = d_after.get("WVTP", "")
    ok = wvtp_after.upper() == "PULSE"
    result("WVTP still PULSE after off", "PULSE", wvtp_after, ok, warn=not ok)
    if not ok:
        print("  !! WVTP changed to %s after output off -- "
              "something is still sending DC commands !!" % wvtp_after)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    banner("SUMMARY")
    if fails == 0:
        print("  ALL HARD CHECKS PASSED")
    else:
        print("  %d HARD CHECK(S) FAILED -- review output above" % fails)
    print()
    return fails


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        import pyvisa
    except ImportError:
        print("ERROR: pyvisa not installed.  Run:  pip install pyvisa pyvisa-py")
        sys.exit(1)

    rm = pyvisa.ResourceManager()
    print("Available VISA resources:")
    for r in rm.list_resources():
        print("  " + r)

    print()
    print("Connecting to: %s" % FG_ADDRESS)
    try:
        inst = rm.open_resource(FG_ADDRESS)
        inst.timeout           = 10_000
        inst.write_termination = "\n"
        inst.read_termination  = "\n"
    except Exception as e:
        print("ERROR: Could not open resource: %s" % e)
        sys.exit(1)

    try:
        fails = run_tests(inst)
    except Exception as e:
        print("\nFATAL ERROR during tests: %s" % e)
        import traceback
        traceback.print_exc()
        fails = 99
    finally:
        try:
            inst.close()
        except Exception:
            pass
        try:
            rm.close()
        except Exception:
            pass

    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
