#!/usr/bin/env python3
"""Exercise Pulse Testing GUI code path without launching Tk.

Runs the same Keithley4200PMUSystem wrappers and preset parameters the GUI uses
(µs timing → keithley4200_core conversion → KXCI scripts).

Usage (from repo root):
    # Endurance (preset: DUT 10cyc @ 1us):
    python Equipment/SMU_AND_PMU/4200A/scripts/pmu_gui_path_test.py --test endurance

    # Pulse-Read-Repeat (preset: DUT 1us write):
    python Equipment/SMU_AND_PMU/4200A/scripts/pmu_gui_path_test.py --test pulse-read

    # PMU retention (preset: DUT 20 reads @ 1us program):
    python Equipment/SMU_AND_PMU/4200A/scripts/pmu_gui_path_test.py --test retention

    # All three PMU GUI tests:
    python Equipment/SMU_AND_PMU/4200A/scripts/pmu_gui_path_test.py --test all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from Pulse_Testing.system_wrapper import SystemWrapper  # noqa: E402

_PRESETS_PATH = _REPO_ROOT / "Json_Files" / "tsp_test_presets.json"


def _load_preset(test_key: str, preset_name: str) -> dict:
    with _PRESETS_PATH.open(encoding="utf-8") as fh:
        presets = json.load(fh)
    block = presets.get(test_key)
    if not block:
        raise KeyError(f"No presets for {test_key!r}")
    if preset_name not in block:
        raise KeyError(f"Preset {preset_name!r} not in {test_key!r}")
    return dict(block[preset_name])


def _run_endurance(wrapper: SystemWrapper, gpib: str) -> int:
    params = _load_preset("Endurance", "DUT 10cyc @ 1us")
    print("=" * 72)
    print("GUI PATH: Endurance / DUT 10cyc @ 1us")
    print(f"Params (µs where applicable): {params}")
    print("=" * 72)
    t0 = time.time()
    results = wrapper.run_test("endurance_test", params)
    ops = results.get("operation") or []
    n = len(results.get("timestamps", []))
    n_set = sum(1 for o in ops if o == "SET")
    n_reset = sum(1 for o in ops if o == "RESET")
    print(f"Readback: {n} points  SET={n_set}  RESET={n_reset}  ({time.time() - t0:.2f} s)")
    expected = 2 * int(params.get("num_cycles", 10))
    if n >= expected and n_set == n_reset:
        print("PASS endurance")
        return 0
    print(f"WARN: expected {expected} reads with equal SET/RESET counts")
    return 2


def _run_pulse_read(wrapper: SystemWrapper, gpib: str) -> int:
    params = _load_preset("Read → Write → Read", "DUT 1us write")
    print("=" * 72)
    print("GUI PATH: Read → Write → Read / DUT 1us write")
    print(f"Params (µs where applicable): {params}")
    print("=" * 72)
    t0 = time.time()
    results = wrapper.run_test("pulse_read_repeat", params)
    ts = results.get("timestamps") or []
    print(f"Readback: {len(ts)} probe points  ({time.time() - t0:.2f} s)")
    if ts:
        gp_us = [t * 1e6 for t in ts if t and abs(t) > 1e-15]
        if gp_us:
            print(f"GP times (us): {', '.join(f'{u:.2f}' for u in gp_us)}")
    expected = 1 + int(params.get("num_cycles", 1))
    if len(ts) >= expected:
        print("PASS pulse-read-repeat")
        return 0
    print(f"WARN: expected >= {expected} probe points")
    return 2


def _run_retention(wrapper: SystemWrapper, gpib: str) -> int:
    params = _load_preset("Retention", "DUT 20 reads @ 1us program")
    print("=" * 72)
    print("GUI PATH: Retention / DUT 20 reads @ 1us program")
    print(f"Params (µs where applicable): {params}")
    print("=" * 72)
    t0 = time.time()
    results = wrapper.run_test("retention_test", params)
    phases = results.get("phase") or []
    n_base = sum(1 for p in phases if p == "baseline")
    n_ret = sum(1 for p in phases if p == "retention")
    n = len(results.get("timestamps", []))
    print(f"Readback: {n} points  baseline={n_base}  retention={n_ret}  ({time.time() - t0:.2f} s)")
    expected = int(params.get("num_initial_reads", 2)) + int(params.get("num_reads", 20))
    if n >= expected and n_ret >= int(params.get("num_reads", 20)):
        print("PASS retention")
        return 0
    print(f"WARN: expected >= {expected} reads (>=8 retention)")
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="PMU tests via GUI system wrapper (no Tk)")
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR")
    parser.add_argument(
        "--test",
        choices=("endurance", "pulse-read", "retention", "all"),
        default="all",
        help="endurance, pulse-read, retention, or all",
    )
    args = parser.parse_args()

    wrapper = SystemWrapper()
    try:
        wrapper.connect(address=args.gpib_address, system_name="keithley4200_pmu")
    except Exception as exc:
        print(f"FAIL: connect — {exc}")
        return 1

    rc = 0
    try:
        if args.test in ("endurance", "all"):
            rc = max(rc, _run_endurance(wrapper, args.gpib_address))
        if args.test in ("pulse-read", "all"):
            rc = max(rc, _run_pulse_read(wrapper, args.gpib_address))
        if args.test in ("retention", "all"):
            rc = max(rc, _run_retention(wrapper, args.gpib_address))
    except Exception as exc:
        print(f"FAIL: {exc}")
        rc = 1
    finally:
        wrapper.disconnect()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
