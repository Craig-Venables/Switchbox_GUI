"""First-sweep curves and forming metrics for every device in a sample folder."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from tools.device_visualizer.data.data_discovery import DataDiscovery
from tools.device_visualizer.data.data_loader import DataLoader
from tools.filament_jump_finder.core import _natural_sort_key, find_jumps_in_curve

_SKIP_NAME = ("endurance", "retention", "pulse", "optical", "classification", "files_analysed")
_SKIP_DIR = {"origin data", "__pycache__", ".git"}
_V_FLOOR = 0.05
_MIN_REGION = 8
_SLOPE_GAP = 0.5
# Ignore steps whose smaller current is below this. A sweep through 0 A
# would otherwise look like a huge ratio jump.
_MIN_JUMP_CURRENT = 1e-13

METRIC_FIELDS = (
    ("pre_current_A", "Pre-forming current (A)"),
    ("pre_resistance_ohm", "Pre-forming resistance (ohm)"),
    ("first_jump_voltage_V", "First jump voltage (V)"),
    ("forming_voltage_V", "Forming voltage (V)"),
    ("forming_polarity", "Forming polarity"),
    ("current_before_forming_A", "Current before forming (A)"),
    ("current_after_forming_A", "Current after forming (A)"),
    ("first_loglog_slope", "First log-log slope"),
    ("loglog_slopes", "Log-log slopes"),
    ("conduction_regions", "Conduction regions"),
    ("switching_voltage_V", "Switching voltage (V)"),
    ("r_on_ohm", "R_on (ohm)"),
    ("r_off_ohm", "R_off (ohm)"),
    ("on_off_ratio", "ON/OFF ratio"),
    ("permanently_ohmic", "Permanently ohmic"),
)


def _parse_device_id(device_id: str) -> Tuple[str, int]:
    parts = str(device_id).split("_")
    if len(parts) >= 2:
        try:
            return "_".join(parts[:-1]), int(parts[-1])
        except ValueError:
            pass
    match = re.search(r"(\d+)", str(device_id))
    number = int(match.group(1)) if match else 0
    return str(device_id), number


def _skipped_path(path: Path) -> bool:
    if any(part.lower() in _SKIP_DIR for part in path.parts):
        return True
    name = path.name.lower()
    return any(token in name for token in _SKIP_NAME)


def measurement_files(device_path: Path) -> List[Path]:
    """Measurement files in one device folder, in sweep order."""
    kept: List[Path] = []
    for path in DataDiscovery.find_raw_data_files(Path(device_path)):
        if _skipped_path(path):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < 200 or size > 8_000_000:
            continue
        kept.append(path)
    kept.sort(key=_natural_sort_key)
    return kept


def discover_sample(sample_path: Path) -> List[Dict[str, Any]]:
    """Devices under one sample. Each record lists files but does not load them."""
    sample_path = Path(sample_path)
    nested = DataDiscovery.find_device_folders(sample_path)
    found: List[Tuple[str, Path, str, int]] = []
    if nested:
        for device_id, device_path in nested:
            if any(part.lower() in _SKIP_DIR for part in Path(device_path).parts):
                continue
            section, device_num = _parse_device_id(device_id)
            found.append((str(device_id), Path(device_path), section, device_num))
    else:
        section, device_num = _parse_device_id(sample_path.name)
        found.append((sample_path.name, sample_path, section, device_num))

    devices: List[Dict[str, Any]] = []
    for device_id, device_path, section, device_num in found:
        files = measurement_files(device_path)
        if not files:
            continue
        devices.append({
            "sample_path": str(sample_path.resolve()),
            "sample_folder": sample_path.name,
            "device_id": device_id,
            "device_path": str(device_path),
            "section": section,
            "device_num": int(device_num),
            "files": files,
            "sweeps": None,
            "full": False,
            "metrics": None,
        })
    devices.sort(key=lambda row: (row["section"].lower(), row["device_num"], row["device_id"].lower()))
    return devices


def path_key(path: Any) -> str:
    """Stable absolute path string for matching a measurement file."""
    try:
        return str(Path(path).resolve())
    except (OSError, ValueError, TypeError):
        return str(path)


def load_iv(path: Path) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Voltage and current, or None when the file is not an IV table."""
    try:
        voltage, current, _time = DataLoader.load_raw_measurement(Path(path))
    except Exception:
        return None
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n < 2:
        return None
    return voltage[:n], current[:n]


def _sweep_record(path: Path, voltage: np.ndarray, current: np.ndarray) -> Dict[str, Any]:
    return {
        "path": Path(path),
        "filename": Path(path).name,
        "voltage": voltage,
        "current": current,
    }


def ensure_sweeps(
    device: Dict[str, Any],
    full: bool = False,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Load measurement files, cached on the device.

    ``full`` reads every file. ``limit`` reads that many from the start.
    With neither, only the first file is read. A later call with a higher
    limit, or with ``full``, reads files that are not already cached.
    The returned list is the requested subset, in file order. The cache
    keeps every file loaded so far.
    """
    files = [Path(path) for path in (device.get("files") or [])]
    if full:
        target = files
    elif limit is None:
        target = files[:1]
    else:
        target = files[: max(0, int(limit))]

    by_path = {path_key(sweep["path"]): sweep for sweep in (device.get("sweeps") or [])}
    attempted = set(device.get("_attempted") or [])
    changed = False
    for path in target:
        key = path_key(path)
        if key in attempted:
            continue
        attempted.add(key)
        changed = True
        loaded = load_iv(path)
        if loaded is None:
            continue
        voltage, current = loaded
        by_path[key] = _sweep_record(path, voltage, current)
    if changed:
        ordered = []
        for path in files:
            sweep = by_path.get(path_key(path))
            if sweep is not None:
                ordered.append(sweep)
        device["sweeps"] = ordered
        device["_attempted"] = [path_key(path) for path in files if path_key(path) in attempted]
        device["full"] = all(path_key(path) in attempted for path in files)
        device["metrics"] = None

    wanted = {path_key(path) for path in target}
    return [sweep for sweep in (device.get("sweeps") or []) if path_key(sweep["path"]) in wanted]


def limited_sweeps(device: Dict[str, Any], limit: int) -> List[Tuple[int, Dict[str, Any]]]:
    """Loaded sweeps among the first ``limit`` files, numbered from 1 in file order."""
    ensure_sweeps(device, limit=limit)
    by_path = {path_key(sweep["path"]): sweep for sweep in (device.get("sweeps") or [])}
    rows: List[Tuple[int, Dict[str, Any]]] = []
    for index, path in enumerate(list(device.get("files") or [])[: max(0, int(limit))], start=1):
        sweep = by_path.get(path_key(path))
        if sweep is not None:
            rows.append((index, sweep))
    return rows


def opening_segment(
    voltage: np.ndarray,
    current: np.ndarray,
    cutoff: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Points from the start until voltage first reaches the cutoff.

    A sweep that starts at 0 and rises keeps the rise up to +cutoff.
    On that rise, a negative current is instrument noise, so those points
    are left out. The line between the points that remain stays at or above zero.
    Returns empty arrays when the first point is already past the cutoff.
    """
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n < 2:
        return np.array([]), np.array([])
    voltage = voltage[:n]
    current = current[:n]
    finite = np.where(np.isfinite(voltage))[0]
    if finite.size == 0:
        return np.array([]), np.array([])
    start = int(finite[0])
    target = abs(float(cutoff))
    if target <= 0:
        return np.array([]), np.array([])
    direction = 0.0
    for index in range(start, n - 1):
        if np.isfinite(voltage[index]) and np.isfinite(voltage[index + 1]):
            delta = float(voltage[index + 1] - voltage[index])
            if abs(delta) > 1e-6:
                direction = delta
                break
    if direction == 0.0:
        return np.array([]), np.array([])
    sign = 1.0 if direction > 0 else -1.0
    limit = sign * target
    first = float(voltage[start])
    if (sign > 0 and first >= limit) or (sign < 0 and first <= limit):
        return np.array([]), np.array([])
    last = start
    for index in range(start, n):
        if not np.isfinite(voltage[index]):
            continue
        last = index
        value = float(voltage[index])
        if (sign > 0 and value >= limit) or (sign < 0 and value <= limit):
            break
    voltage = voltage[start:last + 1].copy()
    current = current[start:last + 1].copy()
    if sign > 0:
        keep = np.isfinite(current) & (current >= 0)
        voltage = voltage[keep]
        current = current[keep]
    return voltage, current


def _jumps(voltage: np.ndarray, current: np.ndarray, min_ratio: float):
    return find_jumps_in_curve(
        voltage,
        current,
        min_ratio=min_ratio,
        min_current=_MIN_JUMP_CURRENT,
    )


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2 or y.size < 2:
        return float("nan")
    fit = np.polyfit(np.asarray(x, dtype=float), np.asarray(y, dtype=float), 1)
    return float(fit[0])


def first_positive_branch(
    voltage: np.ndarray,
    current: np.ndarray,
    v_floor: float = _V_FLOOR,
) -> Tuple[np.ndarray, np.ndarray]:
    """The first run of points with voltage above ``v_floor``."""
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    start = None
    end = 0
    for index in range(n):
        value = voltage[index]
        if not np.isfinite(value):
            continue
        if value > v_floor:
            if start is None:
                start = index
            end = index + 1
        elif start is not None:
            break
    if start is None:
        return np.array([]), np.array([])
    return voltage[start:end].copy(), current[start:end].copy()


def loglog_slopes(
    voltage: np.ndarray,
    current: np.ndarray,
    v_floor: float = _V_FLOOR,
    min_points: int = _MIN_REGION,
    slope_gap: float = _SLOPE_GAP,
) -> List[float]:
    """Slopes of log|I| versus log|V| on the first positive branch.

    The branch is split into blocks of ``min_points``. A new piece starts when
    the next block's slope differs by more than ``slope_gap``. A single block
    sitting between two slopes is joined to the closer side.
    """
    branch_v, branch_i = first_positive_branch(voltage, current, v_floor=v_floor)
    if branch_v.size < min_points:
        return []
    mask = np.isfinite(branch_v) & np.isfinite(branch_i) & (branch_v > v_floor) & (np.abs(branch_i) > 0)
    x = np.log10(branch_v[mask])
    y = np.log10(np.abs(branch_i[mask]))
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    n = int(x.size)
    if n < min_points:
        return []
    blocks = []
    for start in range(0, n - min_points + 1, min_points):
        end = start + min_points
        blocks.append([start, end, _slope(x[start:end], y[start:end])])
    if not blocks:
        return []
    if blocks[-1][1] < n:
        blocks[-1][1] = n
        blocks[-1][2] = _slope(x[blocks[-1][0]:n], y[blocks[-1][0]:n])
    groups = [blocks[0]]
    for start, end, slope in blocks[1:]:
        previous = groups[-1][2]
        if np.isfinite(previous) and np.isfinite(slope) and abs(slope - previous) <= slope_gap:
            groups[-1][1] = end
            groups[-1][2] = _slope(x[groups[-1][0]:end], y[groups[-1][0]:end])
        else:
            groups.append([start, end, slope])
    changed = True
    while changed and len(groups) >= 3:
        changed = False
        for index in range(1, len(groups) - 1):
            if groups[index][1] - groups[index][0] > min_points:
                continue
            left = groups[index - 1][2]
            right = groups[index + 1][2]
            mid = groups[index][2]
            if not (min(left, right) <= mid <= max(left, right)):
                continue
            if abs(mid - left) <= abs(mid - right):
                groups[index - 1][1] = groups[index][1]
                dest = groups[index - 1]
                del groups[index]
            else:
                groups[index + 1][0] = groups[index][0]
                dest = groups[index + 1]
                del groups[index]
            dest[2] = _slope(x[dest[0]:dest[1]], y[dest[0]:dest[1]])
            changed = True
            break
    return [float(group[2]) for group in groups if np.isfinite(group[2])]


def on_off_at_cutoff(
    voltage: np.ndarray,
    current: np.ndarray,
    cutoff: float,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """R_on, R_off, and R_off/R_on where the sweep passes the cutoff twice."""
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n < 4:
        return None, None, None
    voltage = voltage[:n]
    current = current[:n]
    target = abs(float(cutoff))
    if target <= 0 or not np.any(np.isfinite(voltage)):
        return None, None, None
    peak = int(np.nanargmax(voltage))
    if peak <= 0 or peak >= n - 1:
        return None, None, None
    if not np.any(voltage[:peak + 1] >= target):
        return None, None, None
    if not np.any(voltage[peak:] <= target):
        return None, None, None
    forward = int(np.where(voltage[:peak + 1] >= target)[0][0])
    after = np.arange(peak, n)
    returning = int(after[np.nanargmin(np.abs(voltage[after] - target))])
    i_forward = float(current[forward])
    i_return = float(current[returning])
    v_forward = float(voltage[forward])
    v_return = float(voltage[returning])
    if not all(np.isfinite(value) for value in (i_forward, i_return, v_forward, v_return)):
        return None, None, None
    if i_forward == 0 or i_return == 0:
        return None, None, None
    r_forward = abs(v_forward / i_forward)
    r_return = abs(v_return / i_return)
    r_on = min(r_forward, r_return)
    r_off = max(r_forward, r_return)
    if not np.isfinite(r_on) or r_on <= 0:
        return None, None, None
    return float(r_on), float(r_off), float(r_off / r_on)


def value_at_cutoff(
    voltage: np.ndarray,
    current: np.ndarray,
    cutoff: float,
) -> Tuple[Optional[float], Optional[float]]:
    """Absolute current and resistance at the forward point nearest the cutoff."""
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n < 2:
        return None, None
    voltage = voltage[:n]
    current = current[:n]
    target = abs(float(cutoff))
    usable = np.where(np.isfinite(voltage), voltage, -np.inf)
    peak = int(np.argmax(usable))
    if not np.isfinite(voltage[peak]):
        return None, None
    window_v = voltage[:peak + 1]
    window_i = current[:peak + 1]
    ok = np.isfinite(window_v) & np.isfinite(window_i) & (window_v >= 0)
    if not np.any(ok):
        return None, None
    indexes = np.where(ok)[0]
    chosen = int(indexes[np.argmin(np.abs(window_v[indexes] - target))])
    amps = abs(float(window_i[chosen]))
    if window_i[chosen] == 0 or not np.isfinite(window_i[chosen]):
        return (amps if np.isfinite(amps) else None), None
    return amps, abs(float(window_v[chosen] / window_i[chosen]))


def _blank_metrics() -> Dict[str, Any]:
    return {key: None for key, _title in METRIC_FIELDS}


def _preforming(
    voltage: np.ndarray,
    current: np.ndarray,
    cutoff: float,
    min_ratio: float,
) -> Tuple[Optional[float], Optional[float]]:
    """|I| nearest the cutoff, and median |V/I|, on 0 V up to the cutoff before the first jump."""
    jumps = _jumps(voltage, current, min_ratio=min_ratio)
    n = min(len(voltage), len(current))
    end = n
    if jumps:
        end = min(n, int(jumps[0]["index"]) + 1)
    volts = np.asarray(voltage[:end], dtype=float)
    amps = np.asarray(current[:end], dtype=float)
    target = abs(float(cutoff))
    mask = np.isfinite(volts) & np.isfinite(amps) & (volts >= 0) & (volts <= target)
    if not np.any(mask):
        return None, None
    kept_v = volts[mask]
    kept_i = amps[mask]
    nearest = int(np.argmin(np.abs(kept_v - target)))
    current_at = abs(float(kept_i[nearest]))
    ratios = [
        abs(float(v_value) / float(i_value))
        for v_value, i_value in zip(kept_v, kept_i)
        if i_value != 0 and np.isfinite(i_value) and abs(float(v_value)) > 0
    ]
    resistance = float(np.median(ratios)) if ratios else None
    if not np.isfinite(current_at):
        current_at = None
    return current_at, resistance


def _sweep_is_ohmic(
    voltage: np.ndarray,
    current: np.ndarray,
    cutoff: float,
    min_ratio: float,
) -> bool:
    if _jumps(voltage, current, min_ratio=min_ratio):
        return False
    _r_on, _r_off, ratio = on_off_at_cutoff(voltage, current, cutoff)
    if ratio is None or ratio >= 2:
        return False
    slopes = loglog_slopes(voltage, current)
    return len(slopes) == 1 and 0.7 <= slopes[0] <= 1.3


def compute_metrics(
    sweeps: Sequence[Dict[str, Any]],
    cutoff: float,
    min_ratio: float,
    full: bool,
) -> Dict[str, Any]:
    """Metrics from the loaded sweeps. Later-sweep fields stay blank when ``full`` is false."""
    metrics = _blank_metrics()
    if not sweeps:
        return metrics
    first = sweeps[0]
    voltage = first["voltage"]
    current = first["current"]
    pre_i, pre_r = _preforming(voltage, current, cutoff, min_ratio)
    metrics["pre_current_A"] = pre_i
    metrics["pre_resistance_ohm"] = pre_r
    first_jump = _jumps(voltage, current, min_ratio=min_ratio)
    if first_jump:
        metrics["first_jump_voltage_V"] = float(first_jump[0]["voltage_mid"])
    slopes = loglog_slopes(voltage, current)
    if slopes:
        metrics["first_loglog_slope"] = float(slopes[0])
        metrics["loglog_slopes"] = "; ".join(f"{value:.4g}" for value in slopes)
        metrics["conduction_regions"] = len(slopes)
    if not full:
        return metrics

    forming = None
    forming_index = None
    for index, sweep in enumerate(sweeps):
        jumps = _jumps(sweep["voltage"], sweep["current"], min_ratio=min_ratio)
        if jumps:
            forming = jumps[0]
            forming_index = index
            break
    if forming is None:
        return metrics
    forming_voltage = float(forming["voltage_mid"])
    metrics["forming_voltage_V"] = forming_voltage
    if forming_voltage > 0:
        metrics["forming_polarity"] = "positive"
    elif forming_voltage < 0:
        metrics["forming_polarity"] = "negative"
    metrics["current_before_forming_A"] = float(forming["i_before"])
    metrics["current_after_forming_A"] = float(forming["i_after"])

    later = list(sweeps)[forming_index + 1:]
    if not later:
        return metrics
    post = later[0]
    post_jumps = _jumps(post["voltage"], post["current"], min_ratio=min_ratio)
    if post_jumps:
        largest = max(post_jumps, key=lambda jump: jump["ratio"])
        metrics["switching_voltage_V"] = float(largest["voltage_mid"])
    r_on, r_off, ratio = on_off_at_cutoff(post["voltage"], post["current"], cutoff)
    metrics["r_on_ohm"] = r_on
    metrics["r_off_ohm"] = r_off
    metrics["on_off_ratio"] = ratio
    ohmic = all(
        _sweep_is_ohmic(sweep["voltage"], sweep["current"], cutoff, min_ratio)
        for sweep in later
    )
    metrics["permanently_ohmic"] = "yes" if ohmic else "no"
    return metrics


def metrics_for(device: Dict[str, Any], cutoff: float, min_ratio: float, full: bool) -> Dict[str, Any]:
    """Cached metrics. ``full`` reads every sweep and fills forming fields."""
    ensure_sweeps(device, full=full)
    cached = device.get("metrics")
    if (
        cached is not None
        and device.get("_metric_cutoff") == float(cutoff)
        and device.get("_metric_ratio") == float(min_ratio)
        and (not full or device.get("_metric_full"))
    ):
        return cached
    result = compute_metrics(device.get("sweeps") or [], cutoff, min_ratio, full=full or bool(device.get("full")))
    device["metrics"] = result
    device["_metric_cutoff"] = float(cutoff)
    device["_metric_ratio"] = float(min_ratio)
    device["_metric_full"] = bool(full or device.get("full"))
    return result


def evolution_rows(device: Dict[str, Any], cutoff: float) -> List[Tuple[int, Optional[float], Optional[float]]]:
    """Sweep number, |I| at the cutoff, and resistance at the cutoff."""
    sweeps = ensure_sweeps(device, full=True)
    rows = []
    for index, sweep in enumerate(sweeps, start=1):
        amps, resistance = value_at_cutoff(sweep["voltage"], sweep["current"], cutoff)
        rows.append((index, amps, resistance))
    return rows


def device_column_name(sample_label: str, device: Dict[str, Any]) -> str:
    text = f"{sample_label} {device['section']} {device['device_num']}"
    return " ".join(text.split())


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "yes" if value else "no"
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, str):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return ""
    return f"{number:.8g}"


def _write_tsv(path: Path, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(headers)]
    for row in rows:
        lines.append("\t".join(_cell(value) for value in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _columns_to_rows(columns: Sequence[np.ndarray]) -> List[List[str]]:
    if not columns:
        return []
    length = max(len(column) for column in columns)
    rows: List[List[str]] = []
    for row_index in range(length):
        row = []
        for column in columns:
            if row_index < len(column) and np.isfinite(column[row_index]):
                row.append(f"{float(column[row_index]):.8g}")
            else:
                row.append("")
        rows.append(row)
    return rows


def _curve_table(
    path: Path,
    series: Sequence[Tuple[str, np.ndarray, np.ndarray]],
    y_name: str,
    y_unit: str,
    absolute: bool,
    normalised: bool,
) -> None:
    headers: List[str] = []
    columns: List[np.ndarray] = []
    for label, voltage, current in series:
        values = np.abs(current) if absolute else np.asarray(current, dtype=float)
        if normalised:
            scale = float(np.nanmax(np.abs(current))) if current.size else float("nan")
            values = values / scale if np.isfinite(scale) and scale > 0 else np.full(values.shape, np.nan)
        headers.extend([f"Voltage {label} (V)", f"{y_name} {label} {y_unit}"])
        columns.extend([np.asarray(voltage, dtype=float), np.asarray(values, dtype=float)])
    _write_tsv(path, headers, _columns_to_rows(columns))


def series_label(sample_label: str, device: Dict[str, Any], filename: str, file_number: int) -> str:
    """Column name for one opening: sample, device, and measurement file."""
    text = f"{device_column_name(sample_label, device)} {file_number} {filename}"
    return " ".join(text.replace("\t", " ").split())


def export_origin(
    out_dir: Path,
    devices: Sequence[Dict[str, Any]],
    labels: Dict[str, str],
    cutoff: float,
    min_ratio: float,
    file_limit: int = 3,
    hidden_files: Optional[Iterable[str]] = None,
) -> Path:
    """Write opening-curve tables, an index, one metrics table, and sweep evolution.

    Curve tables contain only checked files, and only the points from the start
    of each file until the voltage first reaches ``cutoff``.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    hidden = {path_key(path) for path in (hidden_files or [])}
    window_series = []
    index_rows = []
    metric_rows = []
    evolution: List[Tuple[str, List[Tuple[int, Optional[float], Optional[float]]]]] = []
    cutoff_text = f"{float(cutoff):g}"
    used_names: Dict[str, int] = {}
    for device in devices:
        label = labels.get(device["sample_path"]) or device["sample_folder"]
        column = device_column_name(label, device)
        metrics = metrics_for(device, cutoff, min_ratio, full=True)
        metric_rows.append([
            label,
            device["section"],
            device["device_num"],
            *[metrics.get(key) for key, _title in METRIC_FIELDS],
        ])
        evolution.append((column, evolution_rows(device, cutoff)))
        for file_number, sweep in limited_sweeps(device, file_limit):
            key = path_key(sweep["path"])
            if key in hidden:
                continue
            name = series_label(label, device, sweep["filename"], file_number)
            used_names[name] = used_names.get(name, 0) + 1
            if used_names[name] > 1:
                name = f"{name} {used_names[name]}"
            win_v, win_i = opening_segment(sweep["voltage"], sweep["current"], cutoff)
            window_series.append((name, win_v, win_i))
            index_rows.append([name, key, file_number])

    curve_files = (
        ("voltage, current.txt", "Current", "(A)", False, False),
        ("voltage, abs current.txt", "Absolute Current", "(A)", True, False),
        ("voltage, current (normalised).txt", "Current", "(normalised)", False, True),
        ("voltage, abs current (normalised).txt", "Absolute Current", "(normalised)", True, True),
    )
    for filename, y_name, y_unit, absolute, normalised in curve_files:
        window_name = filename.replace(".txt", f" (first {cutoff_text} V).txt")
        _curve_table(out_dir / window_name, window_series, y_name, y_unit, absolute, normalised)
    _write_tsv(out_dir / "index.txt", ["Column", "Path", "File number"], index_rows)

    metric_headers = ["Sample", "Section", "Device", *[title for _key, title in METRIC_FIELDS]]
    _write_tsv(out_dir / "device metrics.txt", metric_headers, metric_rows)

    max_sweeps = max((len(rows) for _column, rows in evolution), default=0)
    evo_headers = ["Sweep number"]
    evo_columns: List[List[Any]] = [list(range(1, max_sweeps + 1))]
    for column, rows in evolution:
        by_number = {number: (amps, resistance) for number, amps, resistance in rows}
        evo_headers.extend([
            f"Current {column} (A)",
            f"Resistance {column} (ohm)",
        ])
        evo_columns.append([by_number.get(number, (None, None))[0] for number in range(1, max_sweeps + 1)])
        evo_columns.append([by_number.get(number, (None, None))[1] for number in range(1, max_sweeps + 1)])
    evo_rows = []
    for index in range(max_sweeps):
        evo_rows.append([column[index] if index < len(column) else None for column in evo_columns])
    _write_tsv(out_dir / "sweep evolution.txt", evo_headers, evo_rows)
    return out_dir


def save_session(path: Path, payload: Dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_session(path: Path) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Session file is not a JSON object.")
    return data
