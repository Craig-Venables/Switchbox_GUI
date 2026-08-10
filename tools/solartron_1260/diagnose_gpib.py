"""
Solartron SI 1260 GPIB diagnostics.

Run from repo root:
  python tools/solartron_1260/diagnose_gpib.py

Walks through open / write / read combinations and prints PASS/FAIL so we can
see which terminator + command sequence actually talks to the instrument.

Based on the 1260 manual example (7.6.2):
  CV0 / CZ0  -> coordinates
  OP2,1      -> send readings to GPIB
  SI         -> single measurement
  then INPUT the result line
  DO         -> re-output last result

Note: SW is "sweep enable", NOT a measure-and-return query.
"""

from __future__ import annotations

import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

import pyvisa

ADDRESS_CANDIDATES = ("GPIB0::8::INSTR", "GPIB0::9::INSTR")
TIMEOUT_MS = 8000
MEASURE_TIMEOUT_MS = 15000

# (name, write_term, read_term)
TERMINATORS: List[Tuple[str, str, str]] = [
    ("eoi_empty", "", ""),
    ("lf", "\n", "\n"),
    ("cr", "\r", "\r"),
    ("crlf", "\r\n", "\r\n"),
    ("semicolon", ";", ";"),
]


@dataclass
class TrialResult:
    name: str
    ok: bool
    detail: str


def banner(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def try_call(label: str, fn: Callable[[], str]) -> TrialResult:
    try:
        detail = fn()
        print(f"  [PASS] {label}: {detail}")
        return TrialResult(label, True, detail)
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        print(f"  [FAIL] {label}: {msg}")
        return TrialResult(label, False, msg)


def list_resources() -> Tuple[str, ...]:
    rm = pyvisa.ResourceManager()
    try:
        res = tuple(rm.list_resources())
    finally:
        rm.close()
    print("VISA resources:")
    for r in res:
        print(f"  {r}")
    return res


def open_instr(
    address: str,
    write_term: str,
    read_term: str,
    timeout_ms: int = TIMEOUT_MS,
):
    rm = pyvisa.ResourceManager()
    instr = rm.open_resource(address)
    instr.timeout = timeout_ms
    try:
        instr.send_end = True
    except Exception:
        pass
    try:
        instr.query_delay = 0.05
    except Exception:
        pass
    instr.write_termination = write_term
    instr.read_termination = read_term
    try:
        instr.clear()
    except Exception:
        pass
    time.sleep(0.15)
    return rm, instr


def safe_close(rm, instr) -> None:
    try:
        if instr is not None:
            instr.close()
    except Exception:
        pass
    try:
        if rm is not None:
            rm.close()
    except Exception:
        pass


def read_any(instr, label: str = "read") -> str:
    """Try normal read, then raw bytes if needed."""
    try:
        return str(instr.read()).strip()
    except Exception as first:
        # Fallback: grab up to 512 bytes
        try:
            raw = instr.read_bytes(512)
            text = raw.decode("ascii", errors="replace").strip()
            if text:
                return f"{text}  (via read_bytes; prior={first})"
        except Exception as second:
            raise TimeoutError(f"{label} failed: {first} | bytes: {second}") from second
        raise


def phase_open_only(address: str) -> List[TrialResult]:
    banner(f"Phase A — open only @ {address}")
    out: List[TrialResult] = []
    for name, wt, rt in TERMINATORS:
        def _open(n=name, w=wt, r=rt):
            rm, instr = open_instr(address, w, r)
            safe_close(rm, instr)
            return f"opened with terminator={n}"

        out.append(try_call(f"open/{name}", _open))
    return out


def phase_writes(address: str) -> List[TrialResult]:
    """Writes should succeed even when reads fail — proves listen path."""
    banner(f"Phase B — write-only commands @ {address}")
    out: List[TrialResult] = []
    # Prefer EOI-empty first (SMaRT), then CRLF (manual example)
    for name, wt, rt in (("eoi_empty", "", ""), ("crlf", "\r\n", "\r\n"), ("lf", "\n", "\n")):
        rm = instr = None
        try:
            rm, instr = open_instr(address, wt, rt)

            def _writes(i=instr, n=name):
                cmds = [
                    "OT1",  # GPIB term: CR LF + EOI (software selectable)
                    "OS0",  # separator = comma
                    "OP2,1",  # all readings -> GPIB
                    "CZ0",  # impedance coords R,X
                    "FR 1000",  # 1 kHz
                    "VA 0.1",  # 100 mV
                ]
                for c in cmds:
                    i.write(c)
                    time.sleep(0.05)
                return f"wrote {cmds} with terminator={n}"

            out.append(try_call(f"writes/{name}", _writes))
        except Exception as exc:
            out.append(TrialResult(f"writes/{name}", False, str(exc)))
            print(f"  [FAIL] writes/{name}: {exc}")
        finally:
            safe_close(rm, instr)
    return out


def phase_idn_style(address: str) -> List[TrialResult]:
    banner(f"Phase C — identity / version queries @ {address}")
    out: List[TrialResult] = []
    queries = ("*IDN?", "VN?", "ER?", "*STB?")
    for name, wt, rt in (("eoi_empty", "", ""), ("crlf", "\r\n", "\r\n"), ("lf", "\n", "\n")):
        for q in queries:
            rm = instr = None
            try:
                rm, instr = open_instr(address, wt, rt, timeout_ms=5000)

                def _q(i=instr, cmd=q, n=name):
                    i.write(cmd)
                    time.sleep(0.1)
                    return f"terminator={n} -> {read_any(i)!r}"

                out.append(try_call(f"{q}/{name}", _q))
            except Exception as exc:
                out.append(TrialResult(f"{q}/{name}", False, str(exc)))
                print(f"  [FAIL] {q}/{name}: {type(exc).__name__}: {exc}")
            finally:
                safe_close(rm, instr)
    return out


def phase_manual_sequence(address: str, stop_on_success: bool = True) -> List[TrialResult]:
    """
    Official manual 7.6.2 style:
      OP2,1 ; CZ0 ; FR ; VA ; SI ; read
    Also try DO after SI.
    """
    banner(f"Phase D — manual SI measurement sequence @ {address}")
    out: List[TrialResult] = []
    setups = (
        ("crlf", "\r\n", "\r\n"),  # manual example assumes crlf
        ("eoi_empty", "", ""),
        ("lf", "\n", "\n"),
        ("cr", "\r", "\r"),
    )
    for name, wt, rt in setups:
        for variant in ("SI_then_read", "SI_then_DO_then_read", "SW_then_read"):
            rm = instr = None
            label = f"{variant}/{name}"
            try:
                rm, instr = open_instr(address, wt, rt, timeout_ms=MEASURE_TIMEOUT_MS)

                def _meas(i=instr, v=variant, n=name):
                    for c in ("OT1", "OS0", "OP2,1", "CZ0", "FR 1000", "VA 0.1"):
                        i.write(c)
                        time.sleep(0.08)
                    time.sleep(0.3)
                    if v == "SI_then_read":
                        i.write("SI")
                        time.sleep(1.0)
                        return f"terminator={n} SI-> {read_any(i)!r}"
                    if v == "SI_then_DO_then_read":
                        i.write("SI")
                        time.sleep(1.5)
                        i.write("DO")
                        time.sleep(0.2)
                        return f"terminator={n} SI+DO-> {read_any(i)!r}"
                    i.write("SW")
                    time.sleep(1.0)
                    return f"terminator={n} SW-> {read_any(i)!r}"

                result = try_call(label, _meas)
                out.append(result)
                if stop_on_success and result.ok and variant.startswith("SI"):
                    print("  >> Stopping early — found a working SI read path.")
                    return out
            except Exception as exc:
                out.append(TrialResult(label, False, str(exc)))
                print(f"  [FAIL] {label}: {type(exc).__name__}: {exc}")
            finally:
                safe_close(rm, instr)
    return out


def phase_spoll(address: str) -> List[TrialResult]:
    banner(f"Phase E — serial poll / status @ {address}")
    out: List[TrialResult] = []
    rm = instr = None
    try:
        rm, instr = open_instr(address, "", "", timeout_ms=5000)

        def _spoll(i=instr):
            stb = i.read_stb()
            return f"status byte={stb} (0b{stb:08b})"

        out.append(try_call("read_stb", _spoll))
    except Exception as exc:
        out.append(TrialResult("read_stb", False, str(exc)))
        print(f"  [FAIL] read_stb: {exc}")
    finally:
        safe_close(rm, instr)
    return out


def summarize(results: Sequence[TrialResult]) -> None:
    banner("Summary")
    passed = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    print(f"PASS: {len(passed)}   FAIL: {len(failed)}")
    if passed:
        print("\nWorking combinations:")
        for r in passed:
            print(f"  + {r.name}: {r.detail}")
    else:
        print("\nNo successful read/query yet.")
        print("Next checks on the instrument:")
        print("  1) Front panel: press LOCAL, clear BREAK if shown.")
        print("  2) Confirm GPIB primary address is EVEN (8). Address 9 is binary twin.")
        print("  3) Rear F1/F2 terminator switches — power-cycle after changes.")
        print("  4) Watch front panel when SI is sent — generator should leave BREAK.")


def main() -> int:
    banner("Solartron 1260 GPIB diagnose")
    print(f"Timeout per IO: {TIMEOUT_MS} ms")
    resources = list_resources()
    addresses = [a for a in ADDRESS_CANDIDATES if a in resources]
    if not addresses:
        # still try 8 even if list is stale
        addresses = ["GPIB0::8::INSTR"]
        print("WARNING: GPIB0::8 not in list_resources(); still trying it.")

    all_results: List[TrialResult] = []
    # Address 8 first (ASCII). Skip 9 unless 8 finds nothing useful.
    primary = addresses[0]
    print(f"\n>>> Testing address {primary}")
    all_results.extend(phase_open_only(primary))
    all_results.extend(phase_writes(primary))
    all_results.extend(phase_spoll(primary))
    all_results.extend(phase_manual_sequence(primary))
    # Only probe IDN-style if SI path failed (saves time)
    if not any(r.ok and "SI" in r.name for r in all_results):
        all_results.extend(phase_idn_style(primary))
        if len(addresses) > 1:
            print(f"\n>>> Also testing address {addresses[1]}")
            all_results.extend(phase_writes(addresses[1]))
            all_results.extend(phase_manual_sequence(addresses[1]))

    summarize(all_results)
    return 0 if any(r.ok and ("SI" in r.name or "VN" in r.name or "*IDN" in r.name) for r in all_results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
