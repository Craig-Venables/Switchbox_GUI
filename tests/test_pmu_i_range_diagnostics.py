"""Unit tests for PMU IRange / read-timing diagnostics."""

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

analyze_pmu_i_range_usage = _mod.analyze_pmu_i_range_usage
analyze_pmu_read_flat_top = _mod.analyze_pmu_read_flat_top


def test_user_like_endurance_currents_suggest_10u_range():
    """Terminal-like spread: ~150 nA HRS to ~5 uA LRS at 0.2 V read."""
    currents = [
        1.503e-7, 5.128e-6, 7.587e-7, 3.986e-7, 3.699e-7,
        2.225e-7, 2.738e-7, 3.269e-7,
    ]
    r = analyze_pmu_i_range_usage(1e-4, currents, read_voltage=0.2)
    assert r["suggested_i_range"] == 10e-6
    assert any("wide" in line.lower() or "5" in line for line in r["lines"])


def test_stuck_currents_warn_on_coarse_range():
    currents = [1.153e-7] * 10
    r = analyze_pmu_i_range_usage(1e-4, currents, read_voltage=0.3)
    assert not r["ok"]
    assert any("identical" in line.lower() or "quantized" in line.lower() for line in r["lines"])


def test_short_read_width_warns_flat_top():
    r = analyze_pmu_read_flat_top(100e-9, 20e-9)
    assert not r["ok"]
    assert any("WARNING" in line for line in r["lines"])


def test_2us_read_default_ok():
    r = analyze_pmu_read_flat_top(2e-6, 100e-9)
    assert r["ok"]


if __name__ == "__main__":
    test_user_like_endurance_currents_suggest_10u_range()
    test_stuck_currents_warn_on_coarse_range()
    test_short_read_width_warns_flat_top()
    test_2us_read_default_ok()
    print("all ok")
