"""Golden-file / synthetic tests for branch-aware Ron/Roff."""

from __future__ import annotations

import numpy as np
import pytest

from analysis.core.sweep_analyzer import SweepAnalyzer, _positive_finite
from analysis.reclassify_sample import _is_excluded_measurement_file
from pathlib import Path


def _ideal_pinched_loop(
    *,
    hrs: float = 1e5,
    lrs: float = 1e3,
    vmax: float = 1.0,
    n_per_leg: int = 80,
):
    """
    Synthetic bipolar pinched hysteresis with known HRS/LRS.

    Path: 0→+V→0→-V→0
    - Rising +V (forward): HRS until SET near +0.7 V, then LRS
    - Falling +V (reverse): LRS
    - Rising -V magnitude / falling back: LRS then RESET to HRS

    For the positive-V read window the two branches give HRS (forward pre-SET
    region near V_read if V_read is low) and LRS (reverse). We place SET high
    enough that V_read=0.2 V samples HRS on the rising leg and LRS on the
    falling leg.
    """
    v_up = np.linspace(0.0, vmax, n_per_leg)
    # HRS below SET, LRS above
    set_v = 0.7
    i_up = np.where(v_up < set_v, v_up / hrs, v_up / lrs)

    v_down = np.linspace(vmax, 0.0, n_per_leg)
    i_down = v_down / lrs  # stays LRS on return

    v_neg = np.linspace(0.0, -vmax, n_per_leg)
    reset_v = -0.7
    i_neg = np.where(v_neg > reset_v, v_neg / lrs, v_neg / hrs)

    v_ret = np.linspace(-vmax, 0.0, n_per_leg)
    i_ret = v_ret / hrs

    v = np.concatenate([v_up, v_down[1:], v_neg[1:], v_ret[1:]])
    i = np.concatenate([i_up, i_down[1:], i_neg[1:], i_ret[1:]])
    return v, i


def test_ideal_pinched_loop_recovers_hrs_lrs():
    hrs, lrs = 1e5, 1e3
    v, i = _ideal_pinched_loop(hrs=hrs, lrs=lrs)
    sa = SweepAnalyzer(v, i, analysis_level="full")
    ron = sa.ron[0] if sa.ron else None
    roff = sa.roff[0] if sa.roff else None
    assert ron is not None and roff is not None
    # Within 30% of ground truth (median near V_read=0.2)
    assert abs(ron - lrs) / lrs < 0.3, f"Ron={ron}, expected ~{lrs}"
    assert abs(roff - hrs) / hrs < 0.3, f"Roff={roff}, expected ~{hrs}"
    ratio = roff / ron
    assert 50 < ratio < 200
    assert not sa.metrics_quarantined


def test_loop_sampled_at_v0_does_not_invent_tiny_ron():
    """Points exactly at V=0 must not produce sub-mΩ Ron via |V/I| singularity."""
    # Dense sampling through origin with finite current
    v = np.concatenate([
        np.linspace(0.0, 1.0, 50),
        np.linspace(1.0, 0.0, 50),
        np.linspace(0.0, -1.0, 50),
        np.linspace(-1.0, 0.0, 50),
    ])
    # Force several exact zeros
    v[0] = 0.0
    v[49] = 0.0
    v[99] = 0.0
    v[-1] = 0.0
    i = v / 1e4 + 1e-9  # ~10 kΩ ohmic + tiny offset
    sa = SweepAnalyzer(v, i, analysis_level="full")
    for r in _positive_finite(sa.ron) + _positive_finite(sa.roff):
        assert r >= 1e-2, f"Implausible Ron/Roff survived: {r}"


def test_ohmic_line_ratio_near_one():
    v = np.concatenate([
        np.linspace(0.0, 1.0, 40),
        np.linspace(1.0, 0.0, 40),
        np.linspace(0.0, -1.0, 40),
        np.linspace(-1.0, 0.0, 40),
    ])
    i = v / 5e3
    sa = SweepAnalyzer(v, i, analysis_level="full")
    ron = sa.ron[0] if sa.ron else None
    roff = sa.roff[0] if sa.roff else None
    assert ron is not None and roff is not None
    ratio = roff / ron
    assert 0.8 <= ratio <= 1.25


def test_all_zero_current_returns_none_not_zero():
    v = np.linspace(-1.0, 1.0, 100)
    i = np.zeros_like(v)
    sa = SweepAnalyzer.__new__(SweepAnalyzer)
    # Call method unbound via a minimal stub
    from analysis.core.sweep_analyzer import SweepAnalyzer as SA
    stub = object.__new__(SA)
    stub._last_ron_roff_meta = {}
    ron, roff, von, voff = SA.on_off_values(stub, v, i)
    assert ron is None
    assert roff is None


def test_on_off_values_direct_ideal():
    hrs, lrs = 2e4, 2e3
    v, i = _ideal_pinched_loop(hrs=hrs, lrs=lrs, vmax=1.0)
    stub = object.__new__(SweepAnalyzer)
    stub._last_ron_roff_meta = {}
    ron, roff, _, _ = SweepAnalyzer.on_off_values(stub, v, i)
    assert ron is not None and roff is not None
    assert abs(ron - lrs) / lrs < 0.3
    assert abs(roff - hrs) / hrs < 0.3
    meta = stub._last_ron_roff_meta
    assert meta.get("method") == "branch_median_at_vread"
    assert meta.get("n_forward", 0) > 0
    assert meta.get("n_reverse", 0) > 0


def test_exclude_non_iv_filenames():
    assert _is_excluded_measurement_file(Path("14-ENDURANCE-1.0v--1.0v-1000.txt"))
    assert _is_excluded_measurement_file(Path("freqresp_scan.txt"))
    assert _is_excluded_measurement_file(Path("Pulse_measurements_dump.txt"))
    assert _is_excluded_measurement_file(Path("13-RETENTION-2.0v-0.2v-Py.txt"))
    assert _is_excluded_measurement_file(Path("log.txt"))
    assert not _is_excluded_measurement_file(Path("12-FS-1.2v-0.05sv-0.05sd-Py-.txt"))
    assert not _is_excluded_measurement_file(Path("0-FS-0.5v-0.1sv-0.05sd-Py-1.txt"))


def test_sentinel_fallbacks_are_none():
    """Failed Ron must not invent switching_ratio=1.0 or on_off=0."""
    v = np.linspace(-0.01, 0.01, 20)  # all below |V| floor
    i = np.ones_like(v) * 1e-15       # below i_floor
    sa = SweepAnalyzer(v, i, analysis_level="full")
    # Either empty or None entries — never 0/1.0 sentinels for failed metrics
    for r in sa.on_off:
        assert r is None or (isinstance(r, float) and r > 0)
    for r in sa.switching_ratio:
        assert r is None or (isinstance(r, float) and r > 0)
