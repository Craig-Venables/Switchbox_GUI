#!/usr/bin/env python3
"""PMU hardware smoke test — run before GUI changes.

Validates KXCI + pmu_pulse_read_interleaved on a scope-only bench setup
(CH1 + CH2 into splitter -> oscilloscope, no memristor DUT).

Pattern sent: Initial Read -> Write pulse -> Read  (num_cycles=1)

Usage (from repo root):
    # Scope-visible defaults (1 us write, 2 us read) -- start here:
    python Equipment/SMU_AND_PMU/4200A/scripts/pmu_scope_smoke_test.py --scope-visible

    # Nanosecond attempt (needs fast scope; 100 ns flat-top):
    python Equipment/SMU_AND_PMU/4200A/scripts/pmu_scope_smoke_test.py --pulse-width-ns 100

    # Repeat while tuning scope:
    python Equipment/SMU_AND_PMU/4200A/scripts/pmu_scope_smoke_test.py --scope-visible --repeat 10 --interval 2
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_KXCI_SCRIPTS_PATH = _SCRIPT_DIR.parent.parent / "keithley4200" / "kxci_scripts.py"
_spec = importlib.util.spec_from_file_location("kxci_scripts", _KXCI_SCRIPTS_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["kxci_scripts"] = _mod
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
Keithley4200_KXCI_Scripts = _mod.Keithley4200_KXCI_Scripts
print_interleaved_timeline = _mod.print_interleaved_timeline


def _run_once(scripts, args) -> tuple[int, dict]:
    """Single pulse burst. Returns (exit_code, results dict)."""
    pulse_width_s = args.pulse_width_ns * 1e-9
    read_width_s = args.read_width_ns * 1e-9
    rise_s = args.rise_ns * 1e-9

    cfg = scripts.build_pmu_pulse_read_burst_cfg(
        pulse_voltage=args.pulse_voltage,
        pulse_width_s=pulse_width_s,
        read_voltage=args.read_voltage,
        read_width_s=read_width_s,
        read_rise_s=rise_s,
        delay_between_s=20e-9,
        num_cycles=args.num_cycles,
        pulse_rise_s=rise_s,
        pulse_fall_s=rise_s,
        clarius_debug=1 if args.debug else 0,
    )
    cfg.validate()
    scripts._ensure_valid_interleaved_max_points(cfg)
    print_interleaved_timeline(cfg)

    try:
        timestamps, voltages, currents, resistances = scripts._run_interleaved_with_fallback(cfg)
        scripts._print_results_table(timestamps, voltages, currents, resistances)
        results = scripts._format_results(timestamps, voltages, currents, resistances)
    except Exception as exc:
        print(f"\nFAIL: pulse burst raised: {exc}")
        return 1, {}

    ts = results.get("timestamps", [])
    volts = results.get("voltages", [])

    print(f"\n--- Instrument readback (GP 20/22/31) ---")
    print(f"  probe points: {len(ts)}")
    for i, (t, v) in enumerate(zip(ts, volts)):
        print(f"  [{i}] t={t:.3e} s ({t*1e6:.3f} us)  V={v:.4f} V")

    expected_probes = 1 + args.num_cycles
    if len(ts) < expected_probes:
        print(f"WARN: expected ~{expected_probes} read points, got {len(ts)}")

    if len(volts) >= 2 and any(abs(v) > 0.05 for v in volts):
        print("PASS: EX completed and voltage readbacks returned.")
        return 0, results
    print("WARN: EX ran but voltage data looks empty.")
    return 2, results


def main() -> int:
    parser = argparse.ArgumentParser(description="PMU scope smoke test (Read -> Write -> Read)")
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR")
    parser.add_argument("--dry-run", action="store_true", help="Connect only; skip EX")
    parser.add_argument(
        "--scope-visible",
        action="store_true",
        help="Use 1 us write / 2 us read / 100 ns edges (easy to see on scope)",
    )
    parser.add_argument("--pulse-width-ns", type=float, default=None, help="Write flat-top (ns)")
    parser.add_argument("--read-width-ns", type=float, default=None, help="Read window (ns)")
    parser.add_argument("--rise-ns", type=float, default=None, help="Rise/fall time (ns)")
    parser.add_argument("--read-voltage", type=float, default=0.3, help="Read level (V)")
    parser.add_argument("--pulse-voltage", type=float, default=None, help="Write level (V)")
    parser.add_argument("--num-cycles", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=1, help="Number of pulse bursts")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between repeats")
    parser.add_argument("--debug", action="store_true", help="Print C-module debug from instrument")
    args = parser.parse_args()

    if args.scope_visible:
        args.pulse_width_ns = args.pulse_width_ns if args.pulse_width_ns is not None else 1000.0
        args.read_width_ns = args.read_width_ns if args.read_width_ns is not None else 2000.0
        args.rise_ns = args.rise_ns if args.rise_ns is not None else 100.0
        args.pulse_voltage = args.pulse_voltage if args.pulse_voltage is not None else 2.0
    else:
        args.pulse_width_ns = args.pulse_width_ns if args.pulse_width_ns is not None else 100.0
        args.read_width_ns = args.read_width_ns if args.read_width_ns is not None else 200.0
        args.rise_ns = args.rise_ns if args.rise_ns is not None else 100.0
        args.pulse_voltage = args.pulse_voltage if args.pulse_voltage is not None else 1.0

    print("=" * 72)
    print("PMU SCOPE SMOKE TEST")
    print("=" * 72)
    print("Bench: CH1 force waveform on scope (CH2 at 0 V in dual-channel mode).")
    print("Scope: ~250 mV trigger = full Read->Write->Read; >600 mV = write only (see TEK CSV analysis).")
    print("If scope times do NOT match printed timeline below, check trigger/timebase.")
    print(f"GPIB: {args.gpib_address}")
    print(f"Timing: write={args.pulse_width_ns} ns flat, read={args.read_width_ns} ns, rise={args.rise_ns} ns")
    print(f"Levels: read={args.read_voltage} V, write={args.pulse_voltage} V, cycles={args.num_cycles}")
    print(f"Repeat: {args.repeat}x every {args.interval}s")
    print("=" * 72)

    scripts = Keithley4200_KXCI_Scripts(gpib_address=args.gpib_address, timeout=30.0)
    controller = scripts._get_controller()

    if not controller.connect():
        print("FAIL: Could not open GPIB session.")
        return 1

    if args.dry_run:
        print("Dry run -- skipping pulse.")
        controller.disconnect()
        return 0

    last_code = 0
    try:
        for shot in range(1, args.repeat + 1):
            if args.repeat > 1:
                print(f"\n{'=' * 72}\nShot {shot}/{args.repeat}\n{'=' * 72}")
            t0 = time.time()
            last_code, _ = _run_once(scripts, args)
            print(f"Elapsed: {time.time() - t0:.2f} s")
            if shot < args.repeat:
                print(f"Waiting {args.interval}s (adjust scope)...")
                time.sleep(args.interval)
    finally:
        controller.disconnect()

    print("\nDone.")
    return last_code


if __name__ == "__main__":
    raise SystemExit(main())
