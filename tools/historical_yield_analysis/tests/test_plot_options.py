"""Tests for log-scale concentration plots, age gradient, and plotted-data export."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from historical_yield.origin_export import export_plotted_txt
from historical_yield.plots import plot_concentration_yield


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sample_id": "D1",
                "sample_name": "D1-Stock-ITO-PMMA(2%)-Gold",
                "sample_number": 1,
                "concentration_mgml": 0.0,
                "is_stock": True,
                "strict_yield_pct": 10.0,
                "polymer": "PMMA",
            },
            {
                "sample_id": "D2",
                "sample_name": "D2-0.07mgml-ITO-PMMA(2%)-Gold",
                "sample_number": 2,
                "concentration_mgml": 0.07,
                "is_stock": False,
                "strict_yield_pct": 40.0,
                "polymer": "PMMA",
            },
            {
                "sample_id": "D3",
                "sample_name": "D3-0.2mgml-ITO-PMMA(2%)-Gold",
                "sample_number": 3,
                "concentration_mgml": 0.2,
                "is_stock": False,
                "strict_yield_pct": 70.0,
                "polymer": "PS",
            },
        ]
    )


def test_log_concentration_plot_uses_separate_stem(tmp_path: Path):
    out = tmp_path / "plots"
    linear = plot_concentration_yield(_sample_df(), out, formats=("png",), log_fn=lambda _m: None)
    logged = plot_concentration_yield(
        _sample_df(), out, formats=("png",), log_x=True, log_fn=lambda _m: None
    )
    assert linear[0].name == "concentration_vs_yield.png"
    assert logged[0].name == "concentration_vs_yield_logx.png"
    assert logged[0].exists()


def test_log_plot_skipped_when_no_positive_concentrations(tmp_path: Path):
    df = _sample_df().head(1)  # stock only
    messages: list[str] = []
    paths = plot_concentration_yield(
        df, tmp_path, formats=("png",), log_x=True, log_fn=messages.append
    )
    assert paths == []
    assert any("no positive concentrations" in m for m in messages)


def test_age_gradient_plot_renders(tmp_path: Path):
    paths = plot_concentration_yield(
        _sample_df(), tmp_path, formats=("png",), color_by_age=True, log_fn=lambda _m: None
    )
    assert paths and paths[0].exists()


def test_export_plotted_txt_leads_with_axes_and_names(tmp_path: Path):
    path = export_plotted_txt(
        _sample_df(),
        tmp_path,
        "plot_concentration_vs_yield_logx",
        "concentration_mgml",
        "strict_yield_pct",
    )
    assert path.name == "plot_concentration_vs_yield_logx.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    assert header[0] == "X_concentration_mgml"
    assert header[1] == "Y_strict_yield_pct"
    assert "sample_id" in header
    assert "sample_name" in header
    assert "concentration_mgml" not in header  # not duplicated as metadata
    assert len(lines) == 4
    assert lines[1].split("\t")[0] == "0.0"
