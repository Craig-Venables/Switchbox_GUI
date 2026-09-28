"""Unit tests for retention interval builders and volatile classification."""

import math
import unittest

from Pulse_Testing.systems.retention_intervals import (
    build_logarithmic_read_intervals,
    build_linear_read_intervals,
    build_schedule_intervals,
    classify_volatile_screening,
    intervals_to_wait_deltas,
    normalize_log_retention_params,
    normalize_volatile_screening_params,
)


class TestLogIntervals(unittest.TestCase):
    def test_log_spaced_endpoints(self):
        intervals = build_logarithmic_read_intervals(0.1, 1000.0, 5, include_early_burst=False)
        self.assertEqual(len(intervals), 5)
        self.assertAlmostEqual(intervals[0], 0.1, places=6)
        self.assertAlmostEqual(intervals[-1], 1000.0, places=3)
        self.assertEqual(intervals, sorted(intervals))

    def test_early_burst_prepended(self):
        intervals = build_logarithmic_read_intervals(0.05, 100.0, 10, include_early_burst=True)
        self.assertIn(0.05, intervals)
        self.assertIn(1.0, intervals)
        self.assertEqual(intervals, sorted(set(intervals)))

    def test_linear_uniform(self):
        intervals = build_linear_read_intervals(0.01, 1.0, 11)
        self.assertEqual(len(intervals), 11)
        self.assertAlmostEqual(intervals[0], 0.01)
        self.assertAlmostEqual(intervals[-1], 1.0)
        step = intervals[1] - intervals[0]
        for a, b in zip(intervals, intervals[1:]):
            self.assertAlmostEqual(b - a, step, places=9)

    def test_wait_deltas(self):
        self.assertEqual(intervals_to_wait_deltas([1.0, 3.0, 10.0]), [1.0, 2.0, 7.0])

    def test_normalize_log_params(self):
        out = normalize_log_retention_params(
            {
                "t_min_s": 0.1,
                "t_max_s": 100.0,
                "num_reads": 10,
                "include_early_burst": False,
                "pulse_voltage": 2.0,
            }
        )
        self.assertIn("read_intervals", out)
        self.assertEqual(len(out["read_intervals"]), 10)

    def test_normalize_volatile_burst(self):
        out = normalize_volatile_screening_params(
            {
                "schedule_mode": "log",
                "t_min_s": 0.001,
                "burst_t_max_s": 1.0,
                "num_reads": 20,
            }
        )
        self.assertEqual(len(out["burst_intervals"]), 20)
        self.assertEqual(len(out["burst_wait_deltas"]), 20)


class TestVolatileClassification(unittest.TestCase):
    def _series(self, fracs, times):
        ops = ["baseline", "post_pulse"] + ["retention"] * len(fracs)
        r_base = 1000.0
        delta = 500.0
        resistances = [r_base, r_base + delta]
        resistances.extend(r_base + delta * f for f in fracs)
        timestamps = [0.0, 0.01] + times
        return timestamps, resistances, ops

    def test_non_volatile(self):
        ts, rs, ops = self._series([0.95, 0.94, 0.93], [0.1, 1.0, 5.0])
        result = classify_volatile_screening(ts, rs, ops, t_pulse_end=0.01)
        self.assertEqual(result["verdict"], "NON-VOLATILE")

    def test_volatile(self):
        ts, rs, ops = self._series([0.4, 0.2, 0.1], [0.05, 0.1, 0.5])
        result = classify_volatile_screening(ts, rs, ops, t_pulse_end=0.01)
        self.assertEqual(result["verdict"], "VOLATILE")

    def test_inconclusive_no_switch(self):
        ts = [0.0, 0.01, 0.1]
        rs = [1000.0, 1005.0, 1004.0]
        ops = ["baseline", "post_pulse", "retention"]
        result = classify_volatile_screening(ts, rs, ops, t_pulse_end=0.01, min_switch_ratio=0.05)
        self.assertIn("INCONCLUSIVE", result["verdict"])


if __name__ == "__main__":
    unittest.main()
