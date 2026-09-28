"""Auto ≥N loop yield helpers for historical_yield GUI."""

from __future__ import annotations

import json
from pathlib import Path

from historical_yield.auto_yield import load_auto_yield_dataframe, parse_gates


def test_parse_gates():
    assert parse_gates("4,10,100") == [4, 10, 100]
    assert parse_gates("") == [4, 10, 20, 50, 100]


def test_load_auto_yield_dataframe_uses_loops(tmp_path: Path):
    facts = tmp_path / "facts"
    sample = facts / "D114"
    sample.mkdir(parents=True)
    (sample / "sample.json").write_text(
        json.dumps(
            {
                "sample_id": "D114",
                "n_devices_with_facts": 18,
                "worked_loops_fraction": 0.86,
                "worked_memristive_min_loops": 4,
                "worked_by_loop_threshold": {
                    "4": {"worked_fraction": 0.86, "n_worked_memristive_loops": 19},
                    "10": {"worked_fraction": 0.55, "n_worked_memristive_loops": 12},
                    "50": {"worked_fraction": 0.23, "n_worked_memristive_loops": 5},
                },
                "worked_by_threshold": {
                    "4": {"worked_fraction": 0.99, "n_worked_memristive": 99}
                },
            }
        ),
        encoding="utf-8",
    )
    df = load_auto_yield_dataframe(facts, gates=[4, 10, 50])
    assert len(df) == 1
    assert df.iloc[0]["sample_id"] == "D114"
    assert abs(float(df.iloc[0]["worked_pct_at_4"]) - 86.0) < 1e-6
    assert abs(float(df.iloc[0]["worked_pct_at_10"]) - 55.0) < 1e-6
    assert int(df.iloc[0]["n_worked_at_4"]) == 19
