"""
Load SMaRT impedance analyzer binary .dat files.

Format: "SMaRT_Data" (Solartron ModuLab SMaRT). Header is 82 bytes; then each
point is 7 little-endian doubles (56 bytes): Frequency, AC Level, DC Level,
3 reserved, Impedance Magnitude. Phase/Capacitance are not stored in the
binary (use CSV export for those).
"""

import struct
from pathlib import Path
from typing import Optional, Union

import pandas as pd


# Fixed layout from reverse-engineering sample files
SMART_DAT_HEADER_SIZE = 82
SMART_DAT_DOUBLES_PER_POINT = 7
SMART_DAT_BYTES_PER_POINT = SMART_DAT_DOUBLES_PER_POINT * 8  # 56

# Column order in .dat: Freq, AC, DC, (3 unused in file), |Z|
# Phase and C are not in .dat; we add them as NaN or leave out
DAT_COLUMNS = [
    "Frequency (Hz)",
    "AC Level (V)",
    "DC Level (V)",
    "Impedance Magnitude (Ohms)",
]
# Optional columns we could add as NaN
EXTRA_COLUMNS_CSV = ["Impedance Phase Degrees (')", "Admittance Magnitude (S)", "Capacitance Magnitude (F)"]


def load_smart_dat(
    path: Union[str, Path],
    n_points: Optional[int] = None,
    include_extra_columns: bool = False,
) -> pd.DataFrame:
    """
    Load a SMaRT binary .dat file into a DataFrame.

    The .dat stores per point: Frequency, AC Level, DC Level, 3 reserved values,
    and Impedance Magnitude. Phase and Capacitance are not in the binary; use
    the CSV export for full columns. Only blocks that pass a simple sanity
    check (valid frequency and |Z|) are kept; you may get fewer points than the
    CSV (e.g. 37 vs 77). Prefer CSV when both are available.

    Parameters
    ----------
    path : path to the .dat file
    n_points : number of frequency points (optional; inferred from file size if None)
    include_extra_columns : if True, add Phase/Admittance/Capacitance columns as NaN

    Returns
    -------
    DataFrame with at least Frequency, AC Level, DC Level, Impedance Magnitude.
    """
    path = Path(path)
    if path.suffix.lower() != ".dat":
        raise ValueError(f"Expected a .dat file, got {path.suffix}")

    raw = path.read_bytes()

    if not raw.startswith(b"SMaRT_Data"):
        raise ValueError("Not a SMaRT_Data file (missing magic)")

    data_start = SMART_DAT_HEADER_SIZE
    available = len(raw) - data_start
    max_points = available // SMART_DAT_BYTES_PER_POINT

    if n_points is None:
        n_points = max_points
    else:
        n_points = min(n_points, max_points)

    rows = []
    for i in range(n_points):
        offset = data_start + i * SMART_DAT_BYTES_PER_POINT
        if offset + SMART_DAT_BYTES_PER_POINT > len(raw):
            break
        block = raw[offset : offset + SMART_DAT_BYTES_PER_POINT]
        values = struct.unpack("<" + "d" * SMART_DAT_DOUBLES_PER_POINT, block)
        row = {
            DAT_COLUMNS[0]: values[0],
            DAT_COLUMNS[1]: values[1],
            DAT_COLUMNS[2]: values[2],
            DAT_COLUMNS[3]: values[6],  # 4th stored quantity is |Z|
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    # Keep only rows that look like real measurements (some .dat blocks are garbage)
    freq_ok = (df[DAT_COLUMNS[0]] > 0) & (df[DAT_COLUMNS[0]] < 1e10)
    z_ok = (df[DAT_COLUMNS[3]] > 1) & (df[DAT_COLUMNS[3]] < 1e8)
    mask = freq_ok & z_ok
    if not mask.all():
        df = df.loc[mask].copy()
    if include_extra_columns:
        for c in EXTRA_COLUMNS_CSV:
            df[c] = float("nan")
    df = df.sort_values(DAT_COLUMNS[0]).reset_index(drop=True)
    return df
