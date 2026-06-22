#!/usr/bin/env python3
"""PMU retention smoke test — requires pmu_retention_dual_channel in A_Retention USRLIB."""

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
build_retention_ex_command = _mod.build_retention_ex_command


def main() -> int:
    parser = argparse.ArgumentParser(description="PMU retention dual-channel smoke test")
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR")
    parser.add_argument("--baseline-reads", type=int, default=2)
    parser.add_argument("--program-pulses", type=int, default=5)
    parser.add_argument("--retention-reads", type=int, default=8)
    parser.add_argument("--pulse-voltage", type=float, default=2.0)
    parser.add_argument("--read-voltage", type=float, default=0.3)
    parser.add_argument("--pulse-width-us", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    scripts = Keithley4200_KXCI_Scripts(gpib_address=args.gpib_address)
    cfg = scripts.build_pmu_retention_burst_cfg(
        pulse_voltage=args.pulse_voltage,
        pulse_width_s=args.pulse_width_us * 1e-6,
        num_program_pulses=args.program_pulses,
        num_initial_reads=args.baseline_reads,
        num_reads=args.retention_reads,
        read_voltage=args.read_voltage,
        read_width_s=2e-6,
        read_rise_s=100e-9,
    )
    cfg.validate()
    expected = cfg.total_probe_count()
    cmd = build_retention_ex_command(cfg)
    print("=" * 72)
    print("PMU RETENTION SMOKE TEST (A_Retention library)")
    print(f"Expected probes: {expected}  Program pulses: {args.program_pulses}")
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
        results = scripts.retention_test(
            pulse_voltage=args.pulse_voltage,
            pulse_width=args.pulse_width_us * 1e-6,
            num_program_pulses=args.program_pulses,
            num_initial_reads=args.baseline_reads,
            num_reads=args.retention_reads,
            read_voltage=args.read_voltage,
            read_width=2e-6,
            read_rise_time=100e-9,
        )
        phases = results.get("phase") or []
        n = len(results.get("timestamps", []))
        n_ret = sum(1 for p in phases if p == "retention")
        print(f"\nReadback points: {n}  retention reads: {n_ret}")
        print(f"Elapsed: {time.time() - t0:.2f} s")
        if n >= expected and n_ret >= 8:
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
