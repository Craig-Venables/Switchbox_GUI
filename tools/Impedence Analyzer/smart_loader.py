"""
Load SMaRT impedance analyzer CSV exports.

The .dat files are binary SMaRT_Data format; use the CSV exports from the same
folder (e.g. 1_onstate_10pt_decade.csv) for analysis.
"""

from pathlib import Path
from typing import Dict, Optional, Union

import pandas as pd


# SMaRT CSV has 3 header lines: title, "Experiment start time : ...", then column names
SMART_CSV_HEADER_LINES = 3

# Required for plotting; CSV may have trailing comma (15 data fields, 14 named in header)
REQUIRED_PLOT_COLUMNS = [
    "Frequency (Hz)",
    "Impedance Magnitude (Ohms)",
    "Impedance Phase Degrees (')",
    "Capacitance Magnitude (F)",
]


def load_smart_csv(
    path: Union[str, Path],
    frequency_col: str = "Frequency (Hz)",
    numeric_columns: Optional[list] = None,
) -> pd.DataFrame:
    """
    Load a single SMaRT impedance CSV export.

    Parameters
    ----------
    path : path to the .csv file
    frequency_col : column name for frequency (used for sorting)
    numeric_columns : if given, only these columns are forced to numeric; otherwise all applicable

    Returns
    -------
    DataFrame with numeric data, sorted by frequency.
    """
    path = Path(path)
    if not path.suffix.lower() == ".csv":
        raise ValueError(f"Expected a .csv file, got {path.suffix}")

    # SMaRT CSV often has trailing comma: header has 14 names, data rows have 15 fields.
    # Read header line to get exact names and support 15 columns so Capacitance is kept.
    with open(path, encoding="utf-8", errors="replace") as f:
        for _ in range(SMART_CSV_HEADER_LINES):
            f.readline()
        header_line = f.readline()
    names = [s.strip() for s in header_line.split(",")]
    # Trailing comma: header has 14 names but data has 15 fields; 15th is empty
    if len(names) == 14:
        names.append("_trailing")
    elif names and not names[-1]:
        names[-1] = "_trailing"

    # skiprows: 3 intro lines + 1 header line (we supply names)
    df = pd.read_csv(path, skiprows=SMART_CSV_HEADER_LINES + 1, names=names, header=None)
    # Drop trailing column (from trailing comma in CSV) and any fully empty columns
    df = df.drop(columns=["_trailing"], errors="ignore")
    df = df.dropna(axis=1, how="all")
    # Normalize: strip whitespace from column names
    df.columns = [str(c).strip() for c in df.columns]

    # Coerce numeric columns (skip Time and integer index columns)
    if numeric_columns is not None:
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    else:
        for col in df.columns:
            if col == "Time" or "Number" in col:
                continue
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            except (TypeError, ValueError):
                pass

    if frequency_col in df.columns:
        df = df.sort_values(frequency_col).reset_index(drop=True)

    return df


def load_impedance_folder(
    folder: Union[str, Path],
    pattern: str = "*.csv",
    name_from_file: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    Load all SMaRT CSV files from a folder.

    Parameters
    ----------
    folder : path to folder containing .csv exports
    pattern : glob for files (default *.csv)
    name_from_file : if True, keys are file stems (e.g. "1_onstate_10pt_decade"); else "file_0", "file_1", ...

    Returns
    -------
    Dict mapping name -> DataFrame.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(str(folder))

    result: Dict[str, pd.DataFrame] = {}
    for i, p in enumerate(sorted(folder.glob(pattern))):
        if not p.suffix.lower() == ".csv":
            continue
        try:
            df = load_smart_csv(p)
            key = p.stem if name_from_file else f"file_{i}"
            result[key] = df
        except Exception as e:
            result[p.stem] = pd.DataFrame()  # placeholder so user sees which file failed
            raise RuntimeError(f"Failed to load {p.name}: {e}") from e
    return result
