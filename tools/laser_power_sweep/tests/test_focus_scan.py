"""Tests for focus scan loader."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from focus_scan import load_focus_scan, point_at_z

ITO_SCAN = Path(r"C:\Users\ppxcv1\Desktop\laser_fit\on ito")


@unittest.skipUnless(ITO_SCAN.is_dir(), "ITO focus scan folder not present")
class TestFocusScanLoader(unittest.TestCase):
    def test_load_ito_scan(self) -> None:
        points = load_focus_scan(ITO_SCAN)
        self.assertGreaterEqual(len(points), 10)
        z_vals = [p.z_mm for p in points]
        self.assertIn(10.2, [round(z, 1) for z in z_vals])

    def test_best_focus_10_2(self) -> None:
        points = load_focus_scan(ITO_SCAN)
        pt = point_at_z(points, 10.2)
        assert pt is not None
        self.assertGreater(pt.mean_fwhm_um, 10)
        self.assertGreater(pt.e2_mean_um, pt.mean_fwhm_um)
        self.assertTrue(pt.ok)


if __name__ == "__main__":
    unittest.main()
