"""Origin-ready tab-delimited text exports."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

import pandas as pd

# Columns appended after the plotted x/y pair so Origin worksheets carry the
# identifying/grouping information needed for legends and further filtering.
PLOT_METADATA_COLUMNS = (
    "sample_id",
    "sample_name",
    "sample_number",
    "concentration_mgml",
    "is_stock",
    "strict_yield_pct",
    "n_classified",
    "n_memristive",
    "polymer",
    "polymer_percent",
    "bottom_electrode",
    "top_electrode",
    "np_type",
    "source_root",
)


def _write_tsv(df: pd.DataFrame, path: Path, columns: Sequence[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [c for c in columns if c in df.columns]
    out = df.loc[:, cols].copy() if not df.empty else pd.DataFrame(columns=list(columns))
    # ensure requested columns exist even if empty
    for c in columns:
        if c not in out.columns:
            out[c] = pd.Series(dtype=object)
    out = out.loc[:, list(columns)]
    out.to_csv(path, sep="\t", index=False, encoding="utf-8", lineterminator="\n")
    return path


def export_plotted_txt(
    plotted_df: pd.DataFrame,
    output_dir: Path | str,
    stem: str,
    x_column: Optional[str] = None,
    y_column: Optional[str] = None,
) -> Path:
    """
    Write the rows currently drawn on a plot to ``<stem>.txt``.

    The plotted x/y columns are placed first (as ``X_<col>`` / ``Y_<col>``) so an
    Origin import picks up the right axes, followed by sample names and
    fabrication metadata for legends and grouping.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stem}.txt"

    df = plotted_df.copy() if plotted_df is not None else pd.DataFrame()
    out = pd.DataFrame(index=df.index)
    if x_column and x_column in df.columns:
        out[f"X_{x_column}"] = df[x_column]
    if y_column and y_column in df.columns:
        out[f"Y_{y_column}"] = df[y_column]
    for col in PLOT_METADATA_COLUMNS:
        if col in df.columns and col not in (x_column, y_column):
            out[col] = df[col]
    if out.empty and out.columns.empty:
        out = df

    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, sep="\t", index=False, encoding="utf-8", lineterminator="\n")
    return path


def export_origin_txt(
    sample_df: pd.DataFrame,
    output_dir: Path | str,
) -> List[Path]:
    """
    Write Origin-importable TSV files for the current sample selection.

    Files:
      origin_yield_vs_sample.txt
      origin_concentration_vs_yield.txt
      origin_composition_vs_sample.txt
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []

    yield_cols = [
        "sample_id",
        "sample_number",
        "sample_name",
        "strict_yield",
        "strict_yield_pct",
        "n_classified",
        "n_memristive",
        "polymer",
        "polymer_percent",
        "bottom_electrode",
        "top_electrode",
        "np_type",
        "concentration_mgml",
        "is_stock",
    ]
    paths.append(
        _write_tsv(sample_df, output_dir / "origin_yield_vs_sample.txt", yield_cols)
    )

    conc = (
        sample_df.dropna(subset=["concentration_mgml"])
        if not sample_df.empty and "concentration_mgml" in sample_df.columns
        else sample_df
    )
    conc_cols = [
        "sample_id",
        "sample_number",
        "concentration_mgml",
        "strict_yield_pct",
        "polymer",
        "polymer_percent",
        "bottom_electrode",
        "top_electrode",
        "np_type",
        "is_stock",
    ]
    paths.append(
        _write_tsv(conc, output_dir / "origin_concentration_vs_yield.txt", conc_cols)
    )

    final_comp = [
        "sample_id",
        "sample_number",
        "n_classified",
        "strict_yield_pct",
        "n_memristive",
        "pct_memristive",
        "n_ohmic",
        "pct_ohmic",
        "n_capacitive",
        "pct_capacitive",
        "n_conductive",
        "pct_conductive",
        "n_non_conductive",
        "pct_non_conductive",
        "n_mem_capacitive",
        "pct_mem_capacitive",
        "n_intermittent",
        "pct_intermittent",
        "n_other",
        "pct_other",
    ]
    paths.append(
        _write_tsv(
            sample_df,
            output_dir / "origin_composition_vs_sample.txt",
            final_comp,
        )
    )
    return paths
