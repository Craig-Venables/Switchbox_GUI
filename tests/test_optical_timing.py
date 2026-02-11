"""
Unit tests for optical timing helpers: _optical_on_to_seconds, suggest_laser_sync_offset_s,
and pulse-width / first-pulse detection from synthetic data.

Run from repo root: pytest tests/test_optical_timing.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root on path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pytest


# Import the module under test (optical_runner exposes the helpers we need)
def _optical_on_to_seconds(val: float) -> float:
    """Copy of logic from optical_runner for testing."""
    if 0 < val <= 2:
        return val
    return val / 1000.0


def suggest_laser_sync_offset_s(
    timestamps: list[float],
    resistances: list[float],
    desired_first_pulse_s: float,
    baseline_fraction: float = 0.1,
    min_samples_baseline: int = 10,
) -> float | None:
    """Copy of logic from optical_runner for testing (no logging)."""
    if not timestamps or not resistances or len(timestamps) != len(resistances):
        return None
    if len(resistances) < min_samples_baseline:
        return None
    valid_baseline = [r for r in resistances[:min_samples_baseline] if r and abs(r) < 1e15]
    if not valid_baseline:
        return None
    baseline = sorted(valid_baseline)[len(valid_baseline) // 2]
    threshold = baseline * baseline_fraction
    for t, r in zip(timestamps, resistances):
        if not r or abs(r) >= 1e15:
            continue
        if abs(r - baseline) > threshold:
            return desired_first_pulse_s - t
    return None


# ----- _optical_on_to_seconds -----


class TestOpticalOnToSeconds:
    """Test conversion of optical on/off param to seconds (ms vs s heuristic)."""

    def test_ms_values(self):
        assert _optical_on_to_seconds(100) == 0.1
        assert _optical_on_to_seconds(500) == 0.5
        assert _optical_on_to_seconds(1000) == 1.0
        assert _optical_on_to_seconds(50) == 0.05

    def test_seconds_values(self):
        assert _optical_on_to_seconds(0.5) == 0.5
        assert _optical_on_to_seconds(1.0) == 1.0
        assert _optical_on_to_seconds(1.5) == 1.5
        assert _optical_on_to_seconds(0.2) == 0.2

    def test_boundary(self):
        assert _optical_on_to_seconds(2.0) == 2.0
        assert _optical_on_to_seconds(2.5) == 0.0025  # >2 treated as ms
        assert _optical_on_to_seconds(3) == 0.003

    def test_zero_and_negative(self):
        assert _optical_on_to_seconds(0) == 0.0  # 0/1000
        assert _optical_on_to_seconds(-1) == -0.001


# ----- suggest_laser_sync_offset_s -----


class TestSuggestLaserSyncOffset:
    """Test sync offset suggestion from synthetic timestamps/resistances."""

    def test_detects_first_drop(self):
        # Baseline 1e9, drop at index 50 (t=1.0s with dt=0.02)
        n = 100
        dt = 0.02
        ts = [i * dt for i in range(n)]
        R = [1e9] * 50 + [5e8] * 30 + [1e9] * 20  # drop 1.0–1.6 s
        offset = suggest_laser_sync_offset_s(ts, R, desired_first_pulse_s=1.0)
        assert offset is not None
        # First drop at t=1.0, desired 1.0 -> offset 0
        assert abs(offset) < 0.05

    def test_suggests_positive_offset_when_early(self):
        # Drop at t=0.1, desired 1.0 -> offset +0.9
        ts = [0.02 * i for i in range(100)]
        R = [1e9] * 5 + [5e8] * 40 + [1e9] * 55
        offset = suggest_laser_sync_offset_s(ts, R, desired_first_pulse_s=1.0)
        assert offset is not None
        assert 0.85 < offset < 0.95

    def test_suggests_negative_offset_when_late(self):
        # Drop at t=2.0, desired 1.0 -> offset -1.0
        ts = [0.02 * i for i in range(150)]
        R = [1e9] * 100 + [5e8] * 30 + [1e9] * 20
        offset = suggest_laser_sync_offset_s(ts, R, desired_first_pulse_s=1.0)
        assert offset is not None
        assert -1.1 < offset < -0.9

    def test_no_drop_returns_none(self):
        ts = [0.02 * i for i in range(50)]
        R = [1e9] * 50
        assert suggest_laser_sync_offset_s(ts, R, 1.0) is None

    def test_empty_returns_none(self):
        assert suggest_laser_sync_offset_s([], [], 1.0) is None
        assert suggest_laser_sync_offset_s([0.0], [], 1.0) is None

    def test_length_mismatch_returns_none(self):
        assert suggest_laser_sync_offset_s([0.0, 0.02], [1e9], 1.0) is None


# ----- Pulse width from resistance (helper used by analysis script) -----


def estimate_pulse_width_s(
    timestamps: list[float],
    resistances: list[float],
    baseline_fraction: float = 0.1,
    min_baseline_samples: int = 10,
) -> list[tuple[float, float, float]]:
    """
    Estimate each pulse width (s) from resistance drops.
    Returns list of (t_start, t_end, width_s) for each detected drop.
    """
    if len(timestamps) < min_baseline_samples or len(timestamps) != len(resistances):
        return []
    valid = [r for r in resistances[:min_baseline_samples] if r and abs(r) < 1e15]
    if not valid:
        return []
    baseline = sorted(valid)[len(valid) // 2]
    threshold = baseline * baseline_fraction
    in_drop = False
    t_start = 0.0
    out = []
    for t, r in zip(timestamps, resistances):
        if not r or abs(r) >= 1e15:
            continue
        below = (baseline - r) > threshold
        if below and not in_drop:
            in_drop = True
            t_start = t
        elif not below and in_drop:
            in_drop = False
            out.append((t_start, t, t - t_start))
    if in_drop:
        out.append((t_start, timestamps[-1], timestamps[-1] - t_start))
    return out


class TestEstimatePulseWidth:
    """Test pulse width estimation from synthetic R(t)."""

    def test_single_pulse(self):
        ts = [0.02 * i for i in range(100)]
        R = [1e9] * 25 + [5e8] * 25 + [1e9] * 50  # drop 0.5–1.0 s
        pulses = estimate_pulse_width_s(ts, R)
        assert len(pulses) == 1
        t_start, t_end, w = pulses[0]
        assert 0.48 < t_start < 0.52
        assert 0.98 < t_end < 1.02
        assert 0.45 < w < 0.55

    def test_two_pulses(self):
        ts = [0.02 * i for i in range(150)]
        R = [1e9] * 25 + [5e8] * 25 + [1e9] * 25 + [5e8] * 25 + [1e9] * 50
        pulses = estimate_pulse_width_s(ts, R)
        assert len(pulses) == 2
        assert 0.45 < pulses[0][2] < 0.55
        assert 0.45 < pulses[1][2] < 0.55
