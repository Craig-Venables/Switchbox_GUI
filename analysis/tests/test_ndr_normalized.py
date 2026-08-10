"""Unit tests for NDR normalized-slope research diagnostics."""

from __future__ import annotations

import numpy as np

from analysis.core.sweep_analyzer import SweepAnalyzer


def test_ndr_normalized_slope_on_synthetic_ndr():
    # Ramp V 0→2→0 with an artificial NDR region around V=1.0–1.4 on the up-sweep
    v_up = np.linspace(0.0, 2.0, 81)
    i_up = 0.5 * v_up
    # Inject NDR: current falls while V rises
    mask = (v_up >= 1.0) & (v_up <= 1.4)
    i_up = i_up.copy()
    i_up[mask] = 0.5 - 1.2 * (v_up[mask] - 1.0)

    v_down = np.linspace(2.0, 0.0, 81)
    i_down = 0.4 * v_down
    v = np.concatenate([v_up, v_down[1:]])
    i = np.concatenate([i_up, i_down[1:]])

    sa = SweepAnalyzer(v, i, analysis_level="research")
    assert sa.ndr_index is not None and sa.ndr_index > 0.05
    assert sa.ndr_segment_count is not None and sa.ndr_segment_count >= 1
    assert sa.ndr_norm_slope is not None
    # Primary NDR segment should have negative slope in I_norm vs V
    assert sa.ndr_norm_slope < 0
    assert sa.ndr_depth is not None and sa.ndr_depth > 0
    assert sa.ndr_v_start is not None and sa.ndr_v_end is not None


def test_feature_registry_missing():
    from analysis.feature_registry import missing_features, merge_stamp

    assert "research_ndr" in missing_features({}, ["research_ndr", "classification"])
    stamped = merge_stamp({}, ["classification", "research_ndr"])
    assert stamped["classification"] == 1
    assert missing_features(stamped, ["classification", "research_ndr"]) == []
