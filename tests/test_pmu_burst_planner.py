"""Unit tests for PMU endurance burst planning (Python mirror of C pmu_burst_common.h)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_KXCI = _ROOT / "Equipment" / "SMU_AND_PMU" / "keithley4200" / "kxci_scripts.py"
_spec = importlib.util.spec_from_file_location("kxci_scripts", _KXCI)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["kxci_scripts"] = _mod
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

plan_endurance_burst_sizes = _mod.plan_endurance_burst_sizes
endurance_total_probe_count = _mod.endurance_total_probe_count


def test_plan_100_cycles_single_continuous_waveform():
    assert plan_endurance_burst_sizes(100) == [100]


def test_plan_10_cycles_single_burst():
    assert plan_endurance_burst_sizes(10) == [10]


def test_probe_count_100_cycles():
    assert endurance_total_probe_count(100) == 201
