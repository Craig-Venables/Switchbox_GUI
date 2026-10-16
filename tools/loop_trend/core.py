"""Scan folders for IV files that repeat a loop many times, and score how much they drift."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np

from plotting.device.conduction import _DEFAULT_AREA_M2, _DEFAULT_LENGTH_M, _compute_e_j
from tools.device_variation.core import (
    export_measurement_loops,
    polarity_trace,
    split_loops,
    voltage_profile,
)
from tools.device_visualizer.data.data_loader import DataLoader

# Same axes as plotting.device.conduction: SCLC is log J vs log E,
# Schottky is J vs sqrt(E), Poole-Frenkel is J/E vs sqrt(E).
MECHANISM_KINDS = ("sclc", "schottky", "pf")
_FIT_POINTS = 8

# Pulse, endurance, and retention files are not repeated IV triangles.
_SKIP_NAME = ("endurance", "retention", "pulse", "optical", "classification", "files_analysed")
_SKIP_DIR = {"origin data", "__pycache__", ".git"}


def measurement_files(folders: Iterable[Path]):
    """Yield measurement txt files under the chosen folders."""
    for folder in folders:
        root = Path(folder)
        if not root.exists():
            continue
        for path in root.rglob("*.txt"):
            if any(part.lower() in _SKIP_DIR for part in path.parts):
                continue
            name = path.name.lower()
            if any(token in name for token in _SKIP_NAME):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size < 200 or size > 8_000_000:
                continue
            yield path


def load_iv(path: Path):
    """Voltage and current from one measurement file, or None if it is not an IV table."""
    try:
        voltage, current, _time = DataLoader.load_raw_measurement(Path(path))
    except Exception:
        return None
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n < 8:
        return None
    return voltage[:n], current[:n]


def _side_rms(loops, negative: bool) -> float:
    """Distance between the first and last normalised side. Larger means more drift."""
    traces = []
    for voltage, current in loops:
        side_v, side_i = polarity_trace(voltage, current, negative=negative)
        if side_v.size < 2:
            continue
        scale = float(np.nanmax(np.abs(side_i)))
        if not np.isfinite(scale) or scale <= 0:
            continue
        traces.append((side_v, side_i / scale))
    if len(traces) < 2:
        return 0.0
    values = np.concatenate([pair[0] for pair in traces])
    values = values[np.isfinite(values)]
    if values.size < 2:
        return 0.0
    grid = np.linspace(float(np.min(values)), float(np.max(values)), 80)
    first = voltage_profile(traces[0][0], traces[0][1], grid)
    last = voltage_profile(traces[-1][0], traces[-1][1], grid)
    delta = first - last
    ok = np.isfinite(delta)
    if not np.any(ok):
        return 0.0
    return float(np.sqrt(np.mean(delta[ok] ** 2)))


def change_score(loops) -> float:
    """How far the last loop sits from the first, on either voltage side."""
    return max(_side_rms(loops, False), _side_rms(loops, True))


def scan_folders(
    folders: Iterable[Path],
    min_loops: int = 20,
    on_progress: Optional[Callable[[str], None]] = None,
) -> List[Dict]:
    """Measurements whose file contains at least ``min_loops`` repeated IV loops.

    Results are sorted with the largest first-to-last change first.
    """
    hits: List[Dict] = []
    for path in measurement_files(folders):
        if on_progress:
            on_progress(path.name)
        loaded = load_iv(path)
        if loaded is None:
            continue
        voltage, current = loaded
        loops = split_loops(voltage, current)
        if len(loops) < int(min_loops):
            continue
        hits.append({
            "path": Path(path),
            "n_loops": len(loops),
            "change": change_score(loops),
        })
    hits.sort(key=lambda row: (-row["change"], -row["n_loops"], row["path"].name.lower()))
    return hits


def polarity_segments(voltage, current, *, negative: bool, v_floor: float = 0.1):
    """Contiguous runs on one voltage side, with raw current.

    Points closer to zero than ``v_floor`` are left out so the log and
    square-root plots are not dominated by the origin.
    """
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n < 2:
        return []
    voltage = voltage[:n]
    current = current[:n]
    if negative:
        selected = np.isfinite(voltage) & np.isfinite(current) & (voltage <= -float(v_floor))
    else:
        selected = np.isfinite(voltage) & np.isfinite(current) & (voltage >= float(v_floor))
    segments = []
    start = None
    for i in range(n + 1):
        on = i < n and bool(selected[i])
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= 2:
                segments.append((voltage[start:i].copy(), current[start:i].copy()))
            start = None
    return segments


def mechanism_xy(voltage, current, kind: str):
    """Transform one sweep into the coordinates used by the conduction plots.

    Invalid points are NaN so a line breaks instead of jumping across a gap.
    """
    if kind not in MECHANISM_KINDS:
        raise ValueError(f"unknown mechanism {kind!r}")
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    e_arr, j_arr = _compute_e_j(voltage, current, _DEFAULT_LENGTH_M, _DEFAULT_AREA_M2)
    with np.errstate(divide="ignore", invalid="ignore"):
        if kind == "sclc":
            x = e_arr
            y = j_arr
        elif kind == "schottky":
            x = np.sqrt(e_arr)
            y = j_arr
        else:
            x = np.sqrt(e_arr)
            y = j_arr / e_arr
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    bad = ~(np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0))
    x[bad] = np.nan
    y[bad] = np.nan
    return x, y


def outward_fit_xy(voltage, current, kind: str, min_points: int = _FIT_POINTS):
    """Straight-line fit on the high-field half of the outward leg.

    The outward leg runs from the start of the segment up to the voltage peak,
    matching the forward sweep in the conduction plotter. Returns the fit
    curve, or None when there are not enough points.
    """
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    if voltage.size < 2:
        return None
    peak = int(np.argmax(np.abs(voltage)))
    if peak < 1:
        return None
    x, y = mechanism_xy(voltage[: peak + 1], current[: peak + 1], kind)
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]
    if x.size < int(min_points):
        return None
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    mid = x.size // 2
    x_fit_src = x[mid:]
    y_fit_src = y[mid:]
    if x_fit_src.size < int(min_points):
        x_fit_src, y_fit_src = x, y
    log_x = kind == "sclc"
    lx = np.log10(x_fit_src) if log_x else x_fit_src
    ly = np.log10(y_fit_src) if log_x else np.log(y_fit_src)
    if lx.size < int(min_points) or np.ptp(lx) <= 0 or not np.all(np.isfinite(ly)):
        return None
    slope, intercept = np.polyfit(lx, ly, 1)
    if not np.isfinite(slope) or not np.isfinite(intercept):
        return None
    if log_x:
        x_line = np.logspace(np.log10(x_fit_src.min()), np.log10(x_fit_src.max()), 40)
        y_line = 10 ** (slope * np.log10(x_line) + intercept)
    else:
        x_line = np.linspace(float(x_fit_src.min()), float(x_fit_src.max()), 40)
        y_line = np.exp(slope * x_line + intercept)
    return x_line, y_line


def save_all_loops(hits: Iterable[Dict], out_dir: Path) -> int:
    """Write the twelve Origin tables for every hit. Returns how many measurements were written."""
    written = 0
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for hit in hits:
        loaded = load_iv(hit["path"])
        if loaded is None:
            continue
        voltage, current = loaded
        stem = hit["path"].stem
        export_measurement_loops(out_dir, stem, voltage, current)
        written += 1
    return written
