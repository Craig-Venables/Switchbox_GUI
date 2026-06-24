#!/usr/bin/env python3
"""Smoke test for pmu_endurance_burst_test (instrument-side burst batching)."""

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
endurance_total_probe_count = _mod.endurance_total_probe_count
plan_endurance_burst_sizes = _mod.plan_endurance_burst_sizes
build_endurance_burst_test_ex_command = _mod.build_endurance_burst_test_ex_command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PMU endurance burst test (C-internal batching, experimental)"
    )
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR")
    parser.add_argument("--cycles", type=int, default=100)
    parser.add_argument("--set-voltage", type=float, default=2.0)
    parser.add_argument("--reset-voltage", type=float, default=-2.0)
    parser.add_argument("--read-voltage", type=float, default=0.3)
    parser.add_argument("--pulse-width-us", type=float, default=1.0)
    parser.add_argument("--read-width-us", type=float, default=2.0)
    parser.add_argument("--dry-run", action="store_true", help="Print EX only")
    args = parser.parse_args()

    scripts = Keithley4200_KXCI_Scripts(gpib_address=args.gpib_address)
    cfg = scripts.build_pmu_endurance_burst_cfg(
        set_voltage=args.set_voltage,
        reset_voltage=args.reset_voltage,
        pulse_width_s=args.pulse_width_us * 1e-6,
        read_voltage=args.read_voltage,
        read_width_s=args.read_width_us * 1e-6,
        read_rise_s=100e-9,
        delay_between_s=20e-9,
    )
    cfg.validate()
    expected_probes = endurance_total_probe_count(args.cycles)
    burst_plan = plan_endurance_burst_sizes(args.cycles)
    cmd = build_endurance_burst_test_ex_command(cfg, args.cycles)

    print("=" * 72)
    print("PMU ENDURANCE BURST TEST (experimental C-internal batching)")
    print(f"Total cycles: {args.cycles}  Internal bursts: {burst_plan}")
    print(f"Expected probes: {expected_probes}")
    print(f"SET={args.set_voltage} V  RESET={args.reset_voltage} V")
    print("=" * 72)
    print(cmd)

    if args.dry_run:
        print()
        print("DRY-RUN: not connecting to GPIB / 4200. Remove --dry-run to run on hardware.")
        return 0

    print()
    print(f"Connecting to {args.gpib_address} ...")
    print("Running on 4200 (one EX, internal batching - may take several seconds) ...")

    controller = scripts._get_controller()
    if not controller.connect():
        print("FAIL: GPIB connect")
        return 1
    try:
        t0 = time.time()
        results = scripts.endurance_burst_test(
            set_voltage=args.set_voltage,
            reset_voltage=args.reset_voltage,
            pulse_width=args.pulse_width_us * 1e-6,
            read_voltage=args.read_voltage,
            num_cycles=args.cycles,
            delay_between=20e-9,
            read_width=args.read_width_us * 1e-6,
            read_rise_time=100e-9,
        )
        elapsed = time.time() - t0
        n = len(results.get("timestamps", []))
        ops = results.get("operation") or []
        n_set = sum(1 for o in ops if o == "SET")
        n_reset = sum(1 for o in ops if o == "RESET")
        print(f"\nProbes: {n} (expected {expected_probes})")
        print(f"SET reads: {n_set}  RESET reads: {n_reset}  (expect {args.cycles} each)")
        print(f"Elapsed: {elapsed:.2f} s")
        print(f"Burst plan used: {results.get('burst_plan', burst_plan)}")

        if n >= expected_probes and n_set >= args.cycles and n_reset >= args.cycles:
            currents = results.get("currents") or []
            times = results.get("timestamps") or []
            has_time = any(abs(t) > 1e-15 for t in times[: min(20, len(times))])
            has_i = any(abs(c) > 1e-15 for c in currents[: min(20, len(currents))])
            if not has_time:
                print("FAIL: probe PulseTimes are all zero — C module did not write readback")
                return 3
            if not has_i:
                print(
                    "WARN: probe count OK but all read currents are zero "
                    "(open DUT, wrong IRange, or measure path issue)"
                )
            print("PASS")
            return 0
        print("WARN: probe/cycle counts below expected")
        return 2
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    finally:
        controller.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
