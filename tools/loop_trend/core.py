"""Scan folders for IV files that repeat a loop many times, and score how much they drift."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np

from tools.device_variation.core import (
    export_measurement_loops,
    polarity_trace,
    split_loops,
    voltage_profile,
)
from tools.device_visualizer.data.data_loader import DataLoader

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
