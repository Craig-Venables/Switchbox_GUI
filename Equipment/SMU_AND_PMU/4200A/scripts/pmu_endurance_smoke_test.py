#!/usr/bin/env python3
"""PMU endurance smoke test — requires pmu_endurance_interleaved in USRLIB."""

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
build_endurance_ex_command = _mod.build_endurance_ex_command


def main() -> int:
    parser = argparse.ArgumentParser(description="PMU endurance interleaved smoke test")
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR")
    parser.add_argument("--cycles", type=int, default=2)
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
    expected = endurance_total_probe_count(args.cycles)
    cmd = build_endurance_ex_command(cfg, args.cycles)
    print("=" * 72)
    print("PMU ENDURANCE SMOKE TEST")
    print(f"Cycles: {args.cycles}  Expected probes: {expected}")
    print(f"SET={args.set_voltage} V  RESET={args.reset_voltage} V")
    print("=" * 72)
    print(cmd)

    if args.dry_run:
        return 0

    controller = scripts._get_controller()
    if not controller.connect():
        print("FAIL: GPIB connect")
        return 1
    try:
        t0 = time.time()
        results = scripts.endurance_test(
            set_voltage=args.set_voltage,
            reset_voltage=args.reset_voltage,
            pulse_width=args.pulse_width_us * 1e-6,
            read_voltage=args.read_voltage,
            num_cycles=args.cycles,
            delay_between=20e-9,
            read_width=args.read_width_us * 1e-6,
            read_rise_time=100e-9,
        )
        n = len(results.get("timestamps", []))
        expected = 2 * args.cycles
        print(f"\nReadback points (excl. initial): {n}  (expected {expected})")
        ops = results.get("operation") or []
        if ops:
            print(f"SET reads: {sum(1 for o in ops if o == 'SET')}  RESET reads: {sum(1 for o in ops if o == 'RESET')}")
        print(f"Elapsed: {time.time() - t0:.2f} s")
        if n >= expected:
            print("PASS")
            return 0
        print("WARN: fewer points than expected")
        return 2
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    finally:
        controller.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
