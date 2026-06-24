"""PMU probe readback validation (burst / endurance GP arrays)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_KXCI = _ROOT / "Equipment" / "SMU_AND_PMU" / "keithley4200" / "kxci_scripts.py"
_spec = importlib.util.spec_from_file_location("kxci_scripts", _KXCI)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
Scripts = _mod.Keithley4200_KXCI_Scripts


def test_timestamps_populated_when_nonzero():
    assert Scripts._pmu_probe_timestamps_populated([0.0, 1.5e-6, 3.0e-6], 3)


def test_timestamps_not_populated_when_all_zero():
    assert not Scripts._pmu_probe_timestamps_populated([0.0, 0.0, 0.0], 3)
    assert not Scripts._pmu_probe_timestamps_populated([], 0)


if __name__ == "__main__":
    test_timestamps_populated_when_nonzero()
    test_timestamps_not_populated_when_all_zero()
    print("ok")
