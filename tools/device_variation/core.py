"""
Pre/post IV comparison built on filament jump finder sessions.

Accepted jumps come from a saved review (decisions + filter settings).
Curves are normalised per sweep, then reduced to one current value per
voltage bin so devices in a sample can be overlaid and scored.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from tools.filament_jump_finder.core import (
    _natural_sort_key_for_name,
    device_key,
    filter_jumps,
    jump_decision_key,
    load_folders,
)
from tools.filament_jump_finder.origin_export import (
    apply_review_to_decisions,
    load_session,
    session_folder_paths,
)

NORM_RAW = "raw"
NORM_LOG = "log_abs"
NORM_MAX = "max_abs"
NORM_READ = "read_v"

NORM_LABELS = {
    NORM_MAX: "Divide by max |I|",
    NORM_RAW: "Raw current",
    NORM_LOG: "log10(|I|)",
    NORM_READ: "Divide by |I| at read voltage",
}

GRID_POINTS = 101
_CURRENT_FLOOR = 1e-15
VIEW_STATE_VERSION = 1

DeviceKey = Tuple[str, str, int]


def path_key(path: Any) -> str:
    """Stable absolute path string for matching session keys to loaded files."""
    try:
        return str(Path(path).resolve())
    except (OSError, ValueError, TypeError):
        return str(path)


def y_axis_label(mode: str) -> str:
    if mode == NORM_LOG:
        return "log10(|I|)"
    if mode == NORM_MAX:
        return "I / max|I|"
    if mode == NORM_READ:
        return "I / |I(Vread)|"
    return "Current (A)"


def filter_kwargs_from_state(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Map a jump-finder filter_state dict onto filter_jumps arguments."""
    state = state or {}
    min_current = state.get("min_current")
    if min_current is not None and str(min_current).strip() != "":
        try:
            min_current = float(min_current)
        except (TypeError, ValueError):
            min_current = None
    else:
        min_current = None
    v_min = state.get("v_min")
    v_max = state.get("v_max")
    if "voltage_window" in state and not state.get("voltage_window"):
        v_min = None
        v_max = None
    try:
        min_ratio = float(state.get("min_ratio", 10.0))
    except (TypeError, ValueError):
        min_ratio = 10.0
    return {
        "min_ratio": min_ratio,
        "v_min": v_min,
        "v_max": v_max,
        "use_abs_v": bool(state.get("use_abs_v", False)),
        "min_current": min_current,
        "upward_only": bool(state.get("upward_only", False)),
    }


def align_decisions(
    jumps: Sequence[Dict[str, Any]],
    decisions: Optional[Dict[str, bool]],
) -> Dict[str, bool]:
    """
    Re-key saved Jump / Rejected flags onto the paths just loaded.

    Session keys are ``absolute path::step index``. Resolving both sides
    keeps a review usable when the folder string differs only by
    normalisation (OneDrive, slash style, relative vs absolute).
    """
    indexed: Dict[Tuple[str, str], bool] = {}
    for key, val in (decisions or {}).items():
        path, sep, idx = str(key).rpartition("::")
        if not sep:
            continue
        indexed[(path_key(path), str(idx))] = bool(val)
    aligned: Dict[str, bool] = {}
    for jump in jumps:
        current = jump_decision_key(jump)
        path, sep, idx = current.rpartition("::")
        if not sep:
            continue
        hit = indexed.get((path_key(path), str(idx)))
        if hit is not None:
            aligned[current] = hit
    return aligned


def normalize_current(
    voltage: np.ndarray,
    current: np.ndarray,
    mode: str,
    read_voltage: float = 0.5,
) -> np.ndarray:
    """Return a per-curve current array in the requested normalisation."""
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    if mode == NORM_LOG:
        return np.log10(np.maximum(np.abs(current), _CURRENT_FLOOR))
    if mode == NORM_MAX:
        scale = np.nanmax(np.abs(current)) if current.size else np.nan
        if not np.isfinite(scale) or scale <= 0:
            return np.full(current.shape, np.nan)
        return current / scale
    if mode == NORM_READ:
        if voltage.size == 0 or current.size == 0 or not np.any(np.isfinite(voltage)):
            return np.full(current.shape, np.nan)
        idx = int(np.nanargmin(np.abs(voltage - float(read_voltage))))
        scale = abs(float(current[idx]))
        if not np.isfinite(scale) or scale < _CURRENT_FLOOR:
            return np.full(current.shape, np.nan)
        return current / scale
    return current.copy()


def read_current(voltage: np.ndarray, current: np.ndarray, read_voltage: float) -> Optional[float]:
    """Absolute current at the sample nearest ``read_voltage``. None if that point is missing."""
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n == 0:
        return None
    voltage = voltage[:n]
    current = current[:n]
    if not np.any(np.isfinite(voltage)):
        return None
    idx = int(np.nanargmin(np.abs(voltage - float(read_voltage))))
    value = abs(float(current[idx]))
    if not np.isfinite(value):
        return None
    return value


def voltage_side(voltage: np.ndarray, current: np.ndarray, *, negative: bool = False) -> List[Tuple[np.ndarray, np.ndarray]]:
    """One polarity of a loop, in measurement order, scaled by max |I| on that side.

    The other half is left out, and a gap is not joined up, so the line follows
    the sweep instead of collapsing the loop.
    """
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n < 2:
        return []
    voltage = voltage[:n]
    current = current[:n]
    if negative:
        selected = np.isfinite(voltage) & np.isfinite(current) & (voltage <= 0)
    else:
        selected = np.isfinite(voltage) & np.isfinite(current) & (voltage >= 0)
    if not np.any(selected):
        return []
    scale = float(np.nanmax(np.abs(current[selected])))
    if not np.isfinite(scale) or scale <= 0:
        return []
    scaled = current / scale
    segments: List[Tuple[np.ndarray, np.ndarray]] = []
    start = None
    for i in range(n + 1):
        on = i < n and bool(selected[i])
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= 2:
                segments.append((voltage[start:i].copy(), scaled[start:i].copy()))
            start = None
    return segments


def positive_side(voltage: np.ndarray, current: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Positive-voltage runs of one loop, scaled by max |I| on that side."""
    return voltage_side(voltage, current, negative=False)


def negative_side(voltage: np.ndarray, current: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Negative-voltage runs of one loop, scaled by max |I| on that side."""
    return voltage_side(voltage, current, negative=True)


def polarity_trace(voltage: np.ndarray, current: np.ndarray, *, negative: bool) -> Tuple[np.ndarray, np.ndarray]:
    """Raw points on one voltage side, in measurement order."""
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n < 2:
        return np.array([]), np.array([])
    voltage = voltage[:n]
    current = current[:n]
    if negative:
        selected = np.isfinite(voltage) & np.isfinite(current) & (voltage <= 0)
    else:
        selected = np.isfinite(voltage) & np.isfinite(current) & (voltage >= 0)
    parts_v = []
    parts_i = []
    start = None
    for i in range(n + 1):
        on = i < n and bool(selected[i])
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= 2:
                parts_v.append(voltage[start:i])
                parts_i.append(current[start:i])
            start = None
    if not parts_v:
        return np.array([]), np.array([])
    return np.concatenate(parts_v), np.concatenate(parts_i)


def split_loops(voltage: np.ndarray, current: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Split one measurement file into repeated IV loops.

    A loop is one trip out to the positive peak and back. Files such as
    ``Py-50`` repeat that triangle; a single sweep file stays one loop.
    """
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(voltage.size, current.size)
    if n < 4:
        return []
    voltage = voltage[:n]
    current = current[:n]
    finite = np.isfinite(voltage)
    if not np.any(finite):
        return []
    vmax = float(np.nanmax(voltage[finite]))
    if not np.isfinite(vmax) or vmax <= 0:
        return [(voltage.copy(), current.copy())]
    threshold = 0.7 * vmax
    peaks: List[int] = []
    k = 1
    while k < n - 1:
        if voltage[k] >= threshold and voltage[k] >= voltage[k - 1]:
            j = k
            while j + 1 < n and voltage[j + 1] >= threshold and voltage[j + 1] >= voltage[j] - 1e-12:
                j += 1
            if j + 1 >= n or voltage[j + 1] < voltage[j]:
                peaks.append(k)
            k = j + 1
        else:
            k += 1
    if len(peaks) <= 1:
        return [(voltage.copy(), current.copy())]
    period = int(round(float(np.median(np.diff(peaks)))))
    if period < 4:
        return [(voltage.copy(), current.copy())]
    first = int(peaks[0] - (peaks[0] % period))
    if first < 0:
        first = 0
    loops: List[Tuple[np.ndarray, np.ndarray]] = []
    for start in range(first, n, period):
        stop = min(start + period, n)
        if stop - start >= 4:
            loops.append((voltage[start:stop].copy(), current[start:stop].copy()))
    return loops or [(voltage.copy(), current.copy())]


# Twelve Origin files. Each is voltage against one Y column, sweep numbers from 1.
_ORIGIN_LOOP_FILES = (
    ("voltage, abs current", "full", "abs", False, "Absolute Current", "(A)"),
    ("voltage, current", "full", "signed", False, "Current", "(A)"),
    ("voltage, abs current (normalised)", "full", "abs", True, "Absolute Current", "(normalised)"),
    ("voltage, current (normalised)", "full", "signed", True, "Current", "(normalised)"),
    ("voltage, abs current (ps only)", "positive", "abs", False, "Absolute Current", "(A)"),
    ("voltage, current (ps only)", "positive", "signed", False, "Current", "(A)"),
    ("voltage, abs current (normalised) (ps only)", "positive", "abs", True, "Absolute Current", "(normalised)"),
    ("voltage, current (normalised) (ps only)", "positive", "signed", True, "Current", "(normalised)"),
    ("voltage, abs current (ng only)", "negative", "abs", False, "Absolute Current", "(A)"),
    ("voltage, current (ng only)", "negative", "signed", False, "Current", "(A)"),
    ("voltage, abs current (normalised) (ng only)", "negative", "abs", True, "Absolute Current", "(normalised)"),
    ("voltage, current (normalised) (ng only)", "negative", "signed", True, "Current", "(normalised)"),
)


def _loop_trace(loop_v: np.ndarray, loop_i: np.ndarray, scope: str):
    """Whole loop, or only the positive or negative voltage side."""
    if scope == "positive":
        return polarity_trace(loop_v, loop_i, negative=False)
    if scope == "negative":
        return polarity_trace(loop_v, loop_i, negative=True)
    return np.asarray(loop_v, dtype=float), np.asarray(loop_i, dtype=float)


def export_measurement_loops(
    out_dir: Path,
    stem: str,
    voltage: np.ndarray,
    current: np.ndarray,
    side: str = "positive",
):
    """Write twelve Origin-ready tables for one measurement.

    Each file pairs voltage with one current column. Sweep numbers start at 1.
    Normalised current is divided by the maximum absolute current of that sweep
    on the rows included in the file. The side argument is accepted and ignored.
    """
    del side
    loops = split_loops(voltage, current)
    dest = Path(out_dir) / _origin_stem(stem)
    dest.mkdir(parents=True, exist_ok=True)
    for title, scope, kind, normalised, y_name, y_unit in _ORIGIN_LOOP_FILES:
        headers = []
        columns = []
        for index, (loop_v, loop_i) in enumerate(loops, start=1):
            side_v, side_i = _loop_trace(loop_v, loop_i, scope)
            if normalised:
                scale = float(np.nanmax(np.abs(side_i))) if side_i.size else float("nan")
                if not np.isfinite(scale) or scale <= 0:
                    values = np.full(side_i.shape, np.nan)
                else:
                    values = side_i / scale
            else:
                values = np.asarray(side_i, dtype=float)
            if kind == "abs":
                values = np.abs(values)
            headers.extend([
                f"Voltage Sweep {index} (V)",
                f"{y_name} Sweep {index} {y_unit}",
            ])
            columns.extend([side_v, values])
        _write_tsv(dest / f"{title}.txt", headers, _columns_to_rows(columns))
    return dest, len(loops)


def common_voltage_grid(
    voltage_arrays: Iterable[np.ndarray],
    n_points: int = GRID_POINTS,
) -> np.ndarray:
    """One voltage axis covering every finite sample in the given curves."""
    chunks = []
    for voltage in voltage_arrays:
        arr = np.asarray(voltage, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size:
            chunks.append(arr)
    if not chunks:
        return np.linspace(-1.0, 1.0, n_points)
    all_v = np.concatenate(chunks)
    lo = float(np.min(all_v))
    hi = float(np.max(all_v))
    if hi <= lo:
        hi = lo + 1.0
    return np.linspace(lo, hi, n_points)


def voltage_profile(
    voltage: np.ndarray,
    values: np.ndarray,
    grid: np.ndarray,
) -> np.ndarray:
    """
    Median ``values`` in each voltage bin.

    A full IV loop visits the same voltage more than once. Binning keeps
    one number per voltage so devices can share an x-axis. The device tab
    still plots the raw loop.
    """
    voltage = np.asarray(voltage, dtype=float)
    values = np.asarray(values, dtype=float)
    out = np.full(len(grid), np.nan)
    if len(grid) < 2 or voltage.size == 0 or values.size == 0:
        return out
    n_pts = min(len(voltage), len(values))
    voltage = voltage[:n_pts]
    values = values[:n_pts]
    step = (float(grid[-1]) - float(grid[0])) / (len(grid) - 1)
    if step == 0:
        return out
    idx = np.rint((voltage - float(grid[0])) / step).astype(int)
    valid = (idx >= 0) & (idx < len(grid)) & np.isfinite(values) & np.isfinite(voltage)
    if not np.any(valid):
        return out
    idx = idx[valid]
    vals = values[valid]
    order = np.argsort(idx, kind="mergesort")
    idx = idx[order]
    vals = vals[order]
    cuts = np.flatnonzero(np.diff(idx)) + 1
    starts = np.concatenate([[0], cuts])
    ends = np.concatenate([cuts, [len(idx)]])
    for start, end in zip(starts, ends):
        out[int(idx[start])] = float(np.median(vals[start:end]))
    return out


def band_from_profiles(
    profiles: Sequence[np.ndarray],
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Median and interquartile range across profile rows. None if empty."""
    usable = [np.asarray(p, dtype=float) for p in profiles if p is not None]
    if not usable:
        return None
    stack = np.vstack(usable)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        median = np.nanmedian(stack, axis=0)
        q25 = np.nanpercentile(stack, 25, axis=0)
        q75 = np.nanpercentile(stack, 75, axis=0)
    return median, q25, q75


def rms_distance(profile: Optional[np.ndarray], median: Optional[np.ndarray]) -> Optional[float]:
    """Root-mean-square gap between one device profile and the sample median."""
    if profile is None or median is None:
        return None
    delta = np.asarray(profile, dtype=float) - np.asarray(median, dtype=float)
    ok = np.isfinite(delta)
    if not np.any(ok):
        return None
    return float(np.sqrt(np.mean(delta[ok] ** 2)))


def _median_profile(profiles: Sequence[np.ndarray]) -> Optional[np.ndarray]:
    usable = [np.asarray(p, dtype=float) for p in profiles if p is not None]
    if not usable:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmedian(np.vstack(usable), axis=0)


def classify_device_sweeps(
    sweeps: Sequence[Dict[str, Any]],
    accepted_path_keys: Iterable[str],
    excluded_keys: Iterable[str],
    split_before_name: Optional[str],
    use_jumps: bool,
) -> Dict[str, Any]:
    """
    Label each sweep pre, post, unformed, all, or excluded.

    ``split_before_name`` forces the forming file. Otherwise the forming
    file is the earliest included sweep that contains an accepted jump.
    """
    accepted = set(accepted_path_keys)
    excluded = set(excluded_keys)
    ordered: List[Dict[str, Any]] = []
    for sweep in sorted(sweeps, key=lambda s: _natural_sort_key_for_name(s["filename"])):
        row = dict(sweep)
        key = path_key(row["file_path"])
        row["path_key"] = key
        row["excluded"] = key in excluded
        row["phase"] = "excluded" if row["excluded"] else ""
        ordered.append(row)
    included = [row for row in ordered if not row["excluded"]]

    def _finish(status: str, forming_file: Optional[str]) -> Dict[str, Any]:
        return {
            "status": status,
            "forming_file": forming_file,
            "sweeps": ordered,
            "included": included,
        }

    if split_before_name:
        names = [row["filename"] for row in ordered]
        if split_before_name in names:
            start = names.index(split_before_name)
            post_names = set(names[start:])
            for row in included:
                row["phase"] = "post" if row["filename"] in post_names else "pre"
            forming = next((row["filename"] for row in included if row["phase"] == "post"), None)
            pre_exists = any(row["phase"] == "pre" for row in included)
            if forming or pre_exists:
                return _finish("formed", forming or split_before_name)
            return _finish("unformed", None)

    if not use_jumps:
        for row in included:
            row["phase"] = "all"
        return _finish("no_session", None)

    forming_name = None
    for row in included:
        if row["path_key"] in accepted:
            forming_name = row["filename"]
            break
    if forming_name is None:
        for row in included:
            row["phase"] = "unformed"
        return _finish("unformed", None)

    seen = False
    for row in included:
        if row["filename"] == forming_name:
            seen = True
        row["phase"] = "post" if seen else "pre"
    return _finish("formed", forming_name)


def _sweeps_by_device(curve_cache: Dict[Any, Dict[str, Any]]) -> Dict[DeviceKey, List[Dict[str, Any]]]:
    groups: Dict[DeviceKey, List[Dict[str, Any]]] = {}
    for path, rec in curve_cache.items():
        key: DeviceKey = (
            str(rec.get("source_folder", "")),
            str(rec.get("section", "")),
            int(rec.get("device_num") or 0),
        )
        groups.setdefault(key, []).append({
            "file_path": Path(path),
            "filename": rec.get("filename") or Path(path).name,
            "voltage": np.asarray(rec["voltage"], dtype=float),
            "current": np.asarray(rec["current"], dtype=float),
            "source_folder": key[0],
            "section": key[1],
            "device_num": key[2],
            "device_id": rec.get("device_id") or f"{key[1]}_{key[2]}",
        })
    return groups


def _empty_model_fields() -> Dict[str, Any]:
    return {
        "folders": [],
        "device_registry": [],
        "curve_cache": {},
        "accepted_path_keys": set(),
        "n_accepted": 0,
        "n_rejected": 0,
        "n_candidates": 0,
        "session_name": None,
        "session_path": None,
        "has_session": False,
        "filter_state": {},
        "session_folder_keys": set(),
    }


def _folder_record(path: Path, in_session: bool) -> Dict[str, Any]:
    return {
        "path": Path(path),
        "path_key": path_key(path),
        "source_folder": Path(path).name,
        "in_session": in_session,
    }


def _ingest_loaded(
    model: Dict[str, Any],
    loaded: Dict[str, Any],
    folder_paths: Sequence[Path],
    in_session: bool,
) -> None:
    known = {row["path_key"] for row in model["folders"]}
    for path in folder_paths:
        rec = _folder_record(path, in_session)
        if rec["path_key"] in known:
            continue
        model["folders"].append(rec)
        known.add(rec["path_key"])
    session_keys = {row["path_key"] for row in model["folders"] if row["in_session"]}
    model["session_folder_keys"] = session_keys
    for rec in loaded.get("device_registry") or []:
        enriched = dict(rec)
        enriched["in_session"] = path_key(rec.get("source_path")) in session_keys if in_session else False
        # Match by identity so a second load of the same folder does not duplicate.
        key = device_key(enriched)
        if any(device_key(existing) == key and path_key(existing.get("source_path")) == path_key(enriched.get("source_path"))
               for existing in model["device_registry"]):
            continue
        if not in_session:
            enriched["in_session"] = False
        model["device_registry"].append(enriched)
    model["curve_cache"].update(loaded.get("curve_cache") or {})


def _apply_jump_review(model: Dict[str, Any], jumps: Sequence[Dict[str, Any]], session: Dict[str, Any]) -> None:
    decisions = align_decisions(jumps, apply_review_to_decisions(session))
    filtered = filter_jumps(list(jumps), decisions=decisions, **filter_kwargs_from_state(session.get("filter_state")))
    accepted = {path_key(j["file_path"]) for j in filtered if j.get("included", True)}
    # Only jumps from session folders count. Extra folders stay unsplit.
    session_names = {row["source_folder"] for row in model["folders"] if row["in_session"]}
    if session_names:
        accepted_scoped = set()
        for jump in filtered:
            if not jump.get("included", True):
                continue
            if str(jump.get("source_folder", "")) in session_names:
                accepted_scoped.add(path_key(jump["file_path"]))
        accepted = accepted_scoped
    model["accepted_path_keys"] = accepted
    model["n_accepted"] = sum(1 for j in filtered if j.get("included", True) and str(j.get("source_folder", "")) in session_names)
    model["n_rejected"] = sum(1 for j in filtered if not j.get("included", True))
    model["n_candidates"] = len(filtered)
    model["filter_state"] = dict(session.get("filter_state") or {})
    model["has_session"] = True


def load_jump_session(session_path: Path) -> Dict[str, Any]:
    """Load curves for the folders in a jump-finder session and apply its review."""
    session_path = Path(session_path)
    session = load_session(session_path)
    if not session:
        raise ValueError(f"Could not read session: {session_path}")
    folders = session_folder_paths(session)
    missing = [p for p in folders if not p.exists()]
    present = [p for p in folders if p.exists()]
    if not present:
        raise ValueError("Session has no folders that still exist.")
    loaded = load_folders(present)
    model = _empty_model_fields()
    model["session_name"] = session.get("session_name") or session_path.stem
    model["session_path"] = session_path
    model["missing_folders"] = missing
    _ingest_loaded(model, loaded, present, in_session=True)
    for rec in model["device_registry"]:
        rec["in_session"] = True
    _apply_jump_review(model, loaded.get("jumps") or [], session)
    return model


def load_folder_paths(folder_paths: Sequence[Path]) -> Dict[str, Any]:
    """Load curves with no jump review. Nothing is labelled pre or post."""
    present = [Path(p) for p in folder_paths if Path(p).exists()]
    missing = [Path(p) for p in folder_paths if not Path(p).exists()]
    if not present:
        raise ValueError("No folders exist at those paths.")
    loaded = load_folders(present)
    model = _empty_model_fields()
    model["missing_folders"] = missing
    _ingest_loaded(model, loaded, present, in_session=False)
    return model


def add_folders_to_model(model: Dict[str, Any], folder_paths: Sequence[Path]) -> List[Path]:
    """
    Append folders that are not already loaded.

    New folders do not inherit implicit jump acceptance. Only an explicit
    review marks pre and post.
    """
    known = {row["path_key"] for row in model["folders"]}
    fresh = []
    for path in folder_paths:
        path = Path(path)
        if not path.exists():
            continue
        if path_key(path) in known:
            continue
        fresh.append(path)
    if not fresh:
        return []
    loaded = load_folders(fresh)
    _ingest_loaded(model, loaded, fresh, in_session=False)
    return fresh


def remove_folders_from_model(model: Dict[str, Any], folder_paths: Sequence[Path]) -> None:
    """Drop folders and their curves from an in-memory model."""
    drop = {path_key(p) for p in folder_paths}
    removed_names = {row["source_folder"] for row in model["folders"] if row["path_key"] in drop}
    # Same basename in two places is rare; only drop a name when every
    # remaining folder with that name is leaving.
    kept_names = {row["source_folder"] for row in model["folders"] if row["path_key"] not in drop}
    names_to_drop = removed_names - kept_names
    model["folders"] = [row for row in model["folders"] if row["path_key"] not in drop]
    model["session_folder_keys"] = {row["path_key"] for row in model["folders"] if row["in_session"]}
    model["device_registry"] = [
        rec for rec in model["device_registry"]
        if str(rec.get("source_folder", "")) not in names_to_drop
    ]
    model["curve_cache"] = {
        path: rec for path, rec in model["curve_cache"].items()
        if str(rec.get("source_folder", "")) not in names_to_drop
    }
    if not any(row["in_session"] for row in model["folders"]):
        model["has_session"] = False
        model["accepted_path_keys"] = set()
        model["n_accepted"] = 0
        model["n_rejected"] = 0


def iter_devices(model: Dict[str, Any], source_folder: Optional[str] = None) -> List[Dict[str, Any]]:
    """Registry rows with their sweeps attached, optionally for one sample."""
    groups = _sweeps_by_device(model.get("curve_cache") or {})
    rows = []
    for rec in model.get("device_registry") or []:
        if source_folder is not None and rec.get("source_folder") != source_folder:
            continue
        key = device_key(rec)
        row = dict(rec)
        row["key"] = key
        row["label"] = rec.get("device_id") or f"{key[1]}_{key[2]}"
        row["sweeps"] = groups.get(key, [])
        rows.append(row)
    rows.sort(key=lambda r: (str(r.get("source_folder", "")), _natural_sort_key_for_name(str(r["label"]))))
    return rows


def _split_key(source_folder: str, section: str, device_num: int) -> str:
    return f"{source_folder}\n{section}\n{int(device_num)}"


def split_lookup_key(source_folder: str, section: str, device_num: int) -> str:
    return _split_key(source_folder, section, device_num)


def classify_device(
    device: Dict[str, Any],
    model: Dict[str, Any],
    excluded_keys: Iterable[str],
    split_before: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    """Classify one device's sweeps using the loaded review and local overrides."""
    overrides = split_before or {}
    key = device.get("key") or device_key(device)
    override_name = overrides.get(_split_key(key[0], key[1], key[2]))
    use_jumps = bool(device.get("in_session")) and bool(model.get("has_session"))
    classified = classify_device_sweeps(
        device.get("sweeps") or [],
        model.get("accepted_path_keys") or (),
        excluded_keys,
        override_name,
        use_jumps,
    )
    classified["key"] = key
    classified["label"] = device.get("label") or f"{key[1]}_{key[2]}"
    classified["source_folder"] = key[0]
    classified["section"] = key[1]
    classified["device_num"] = key[2]
    return classified


def _profiles_for_phase(
    included: Sequence[Dict[str, Any]],
    phase: str,
    mode: str,
    read_voltage: float,
    grid: np.ndarray,
) -> Optional[np.ndarray]:
    profiles = []
    for sweep in included:
        if sweep.get("phase") != phase:
            continue
        values = normalize_current(sweep["voltage"], sweep["current"], mode, read_voltage)
        profile = voltage_profile(sweep["voltage"], values, grid)
        if np.any(np.isfinite(profile)):
            profiles.append(profile)
    return _median_profile(profiles)


def _voltages_for_folder(
    model: Dict[str, Any],
    source_folder: str,
    excluded_keys: Iterable[str],
    split_before: Optional[Dict[str, str]],
    include_keys: Optional[set] = None,
) -> List[np.ndarray]:
    excluded = set(excluded_keys)
    voltages = []
    for device in iter_devices(model, source_folder):
        if include_keys is not None and device["key"] not in include_keys:
            continue
        classified = classify_device(device, model, excluded, split_before)
        for sweep in classified["included"]:
            voltages.append(sweep["voltage"])
    return voltages


def summarize_sample(
    model: Dict[str, Any],
    source_folder: str,
    excluded_keys: Iterable[str],
    split_before: Optional[Dict[str, str]],
    mode: str,
    read_voltage: float = 0.5,
    grid: Optional[np.ndarray] = None,
    include_keys: Optional[set] = None,
) -> Dict[str, Any]:
    """
    One profile per device per phase, plus the sample median and IQR.

    Distance is the RMS gap between that device profile and the median.
    """
    devices = iter_devices(model, source_folder)
    if include_keys is not None:
        devices = [device for device in devices if device["key"] in include_keys]
    if grid is None:
        grid = common_voltage_grid(
            _voltages_for_folder(
                model, source_folder, excluded_keys, split_before, include_keys=include_keys,
            )
        )
    prepared = []
    for device in devices:
        classified = classify_device(device, model, excluded_keys, split_before)
        prepared.append({
            "key": classified["key"],
            "label": classified["label"],
            "status": classified["status"],
            "forming_file": classified["forming_file"],
            "n_pre": sum(1 for s in classified["included"] if s["phase"] == "pre"),
            "n_post": sum(1 for s in classified["included"] if s["phase"] == "post"),
            "n_unformed": sum(1 for s in classified["included"] if s["phase"] == "unformed"),
            "n_all": sum(1 for s in classified["included"] if s["phase"] == "all"),
            "pre": _profiles_for_phase(classified["included"], "pre", mode, read_voltage, grid),
            "post": _profiles_for_phase(classified["included"], "post", mode, read_voltage, grid),
            "unformed": _profiles_for_phase(classified["included"], "unformed", mode, read_voltage, grid),
            "all": _profiles_for_phase(classified["included"], "all", mode, read_voltage, grid),
        })
    pre_band = band_from_profiles([row["pre"] for row in prepared if row["pre"] is not None])
    post_band = band_from_profiles([row["post"] for row in prepared if row["post"] is not None])
    unformed_band = band_from_profiles([row["unformed"] for row in prepared if row["unformed"] is not None])
    all_band = band_from_profiles([row["all"] for row in prepared if row["all"] is not None])
    pre_median = pre_band[0] if pre_band else None
    post_median = post_band[0] if post_band else None
    for row in prepared:
        row["pre_rms"] = rms_distance(row["pre"], pre_median)
        row["post_rms"] = rms_distance(row["post"], post_median)
        row["unformed_rms"] = rms_distance(row["unformed"], unformed_band[0] if unformed_band else None)
        row["all_rms"] = rms_distance(row["all"], all_band[0] if all_band else None)
    return {
        "source_folder": source_folder,
        "grid": grid,
        "devices": prepared,
        "pre_band": pre_band,
        "post_band": post_band,
        "unformed_band": unformed_band,
        "all_band": all_band,
        "n_formed": sum(1 for row in prepared if row["status"] == "formed"),
        "n_unformed": sum(1 for row in prepared if row["status"] == "unformed"),
        "n_no_session": sum(1 for row in prepared if row["status"] == "no_session"),
        "mode": mode,
    }


def summarize_compare(
    model: Dict[str, Any],
    source_folders: Sequence[str],
    labels: Optional[Dict[str, str]],
    excluded_keys: Iterable[str],
    split_before: Optional[Dict[str, str]],
    mode: str,
    read_voltage: float = 0.5,
    include_keys: Optional[set] = None,
) -> Dict[str, Any]:
    """Median and IQR for each sample on one shared voltage grid."""
    labels = labels or {}
    voltages: List[np.ndarray] = []
    for folder in source_folders:
        voltages.extend(
            _voltages_for_folder(model, folder, excluded_keys, split_before, include_keys=include_keys)
        )
    grid = common_voltage_grid(voltages)
    samples = []
    for folder in source_folders:
        summary = summarize_sample(
            model, folder, excluded_keys, split_before, mode, read_voltage,
            grid=grid, include_keys=include_keys,
        )
        samples.append({
            "source_folder": folder,
            "label": labels.get(folder) or folder,
            "summary": summary,
        })
    return {"grid": grid, "samples": samples, "mode": mode}


def save_view_state(
    path: Path,
    excluded_keys: Iterable[str],
    split_before: Dict[str, str],
    sample_labels: Dict[str, str],
    session_meta: Optional[Dict[str, Any]] = None,
) -> Path:
    """Persist excludes, labels, and enough UI state to reopen the same view."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": VIEW_STATE_VERSION,
        "excluded_files": sorted(set(excluded_keys)),
        "split_before": _split_before_rows(split_before),
        "sample_labels": dict(sample_labels),
    }
    if session_meta:
        payload.update(session_meta)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _parse_split_key(key: str) -> Tuple[str, str, str]:
    folder, section, num = key.split("\n", 2)
    return folder, section, num


def _split_before_rows(split_before: Dict[str, str]) -> List[Dict[str, Any]]:
    rows = []
    for key, filename in sorted(split_before.items()):
        if not filename:
            continue
        folder, section, num = _parse_split_key(key)
        rows.append({
            "source_folder": folder,
            "section": section,
            "device_num": int(num),
            "filename": filename,
        })
    return rows


def load_view_state(path: Path) -> Dict[str, Any]:
    """Read a view-state JSON. Raises ValueError if the file is unusable."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read view state: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("View state is not a JSON object.")
    excluded = set()
    for item in data.get("excluded_files") or []:
        excluded.add(path_key(item))
    split_before: Dict[str, str] = {}
    for row in data.get("split_before") or []:
        if not isinstance(row, dict):
            continue
        filename = str(row.get("filename") or "")
        if not filename:
            continue
        try:
            device_num = int(row.get("device_num"))
        except (TypeError, ValueError):
            continue
        split_before[_split_key(str(row.get("source_folder") or ""), str(row.get("section") or ""), device_num)] = filename
    labels = data.get("sample_labels") or {}
    if not isinstance(labels, dict):
        labels = {}
    compare_devices = data.get("compare_devices") or []
    if not isinstance(compare_devices, list):
        compare_devices = []
    return {
        "excluded_keys": excluded,
        "split_before": split_before,
        "sample_labels": {str(k): str(v) for k, v in labels.items()},
        "jump_session_path": data.get("jump_session_path"),
        "folder_paths": [str(p) for p in (data.get("folder_paths") or [])],
        "compare_devices": compare_devices,
        "normalization": data.get("normalization"),
        "read_voltage": data.get("read_voltage"),
        "memristive_only": data.get("memristive_only"),
        "log_y": data.get("log_y"),
        "device_view": data.get("device_view"),
        "sample_pre_rule": data.get("sample_pre_rule"),
        "sample_post_rule": data.get("sample_post_rule"),
        "sample_show_raw": data.get("sample_show_raw"),
        "compare_figure": data.get("compare_figure"),
        "sample_plot": data.get("sample_plot"),
        "min_sweeps": data.get("min_sweeps"),
        "hidden_devices": data.get("hidden_devices") or [],
    }


def _write_tsv(path: Path, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(headers)]
    for row in rows:
        lines.append("\t".join("" if value is None else str(value) for value in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _origin_stem(text: str) -> str:
    stem = re.sub(r'[<>:"/\\|?*\s]+', "_", str(text)).strip("._")
    return (stem or "curve")[:60]


def _xy_columns(sweeps: Sequence[Dict[str, Any]], mode: str, read_voltage: float):
    headers: List[str] = []
    columns: List[np.ndarray] = []
    index_rows: List[Tuple[Any, ...]] = []
    for index, sweep in enumerate(sweeps):
        voltage = np.asarray(sweep["voltage"], dtype=float)
        y_values = normalize_current(voltage, sweep["current"], mode, read_voltage)
        stem = _origin_stem(sweep.get("filename") or f"sweep_{index}")
        headers.extend([f"V_{index}_{stem}", f"Y_{index}_{stem}"])
        columns.append(voltage)
        columns.append(np.asarray(y_values, dtype=float))
        index_rows.append((
            index,
            sweep.get("filename") or "",
            sweep.get("phase") or "",
            int(len(voltage)),
            mode,
        ))
    return headers, columns, index_rows


def _columns_to_rows(columns: Sequence[np.ndarray]) -> List[List[str]]:
    if not columns:
        return []
    length = max(len(column) for column in columns)
    rows: List[List[str]] = []
    for row_index in range(length):
        row = []
        for column in columns:
            if row_index < len(column):
                value = column[row_index]
                row.append(f"{float(value):.8g}" if np.isfinite(value) else "")
            else:
                row.append("")
        rows.append(row)
    return rows


def _export_lifetime_file(
    out_dir: Path,
    stem: str,
    sweeps: Sequence[Dict[str, Any]],
    mode: str,
    read_voltage: float,
) -> None:
    included = [sweep for sweep in sweeps if sweep.get("phase") != "excluded"]
    headers, columns, index_rows = _xy_columns(included, mode, read_voltage)
    if not headers:
        return
    _write_tsv(out_dir / f"{stem}.txt", headers, _columns_to_rows(columns))
    _write_tsv(
        out_dir / f"{stem}_index.txt",
        ("SweepIndex", "Filename", "Phase", "N_points", "Normalization"),
        index_rows,
    )


def _export_sample_band(out_dir: Path, folder: str, summary: Dict[str, Any]) -> None:
    grid = np.asarray(summary.get("grid"), dtype=float)
    headers = ["Voltage_V"]
    columns: List[np.ndarray] = [grid]
    for name, band in (
        ("Pre", summary.get("pre_band")),
        ("Post", summary.get("post_band")),
        ("Unformed", summary.get("unformed_band")),
        ("All", summary.get("all_band")),
    ):
        if not band:
            continue
        median, q25, q75 = band
        headers.extend([f"{name}_Median", f"{name}_Q25", f"{name}_Q75"])
        columns.extend([
            np.asarray(median, dtype=float),
            np.asarray(q25, dtype=float),
            np.asarray(q75, dtype=float),
        ])
    _write_tsv(
        out_dir / f"sample_{_origin_stem(folder)}_band.txt",
        headers,
        _columns_to_rows(columns),
    )


def export_origin_bundle(
    model: Dict[str, Any],
    export_name: str,
    excluded_keys: Iterable[str],
    split_before: Optional[Dict[str, str]],
    sample_labels: Optional[Dict[str, str]],
    mode: str,
    read_voltage: float = 0.5,
    include_keys: Optional[set] = None,
    compare_device_keys: Optional[Dict[str, Any]] = None,
    current_device: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Write tab-separated tables Origin can plot directly.

    Each lifetime file is paired XY columns (voltage, normalised current),
    one pair per included sweep, in sweep order. Empty cells pad shorter sweeps.
    Sample band files hold the median and interquartile curves.
    """
    from tools.filament_jump_finder.core import origin_export_root
    from tools.filament_jump_finder.origin_export import origin_data_dir, sanitize_export_name

    clean = sanitize_export_name(export_name)
    if not clean:
        raise ValueError("Enter a name for this Origin export.")
    folder_paths = [Path(row["path"]) for row in model.get("folders") or []]
    if not folder_paths:
        raise ValueError("No sample folders are loaded.")
    out_dir = origin_data_dir(origin_export_root(folder_paths), clean)

    devices: List[Dict[str, Any]] = []
    seen = set()

    def _add(device: Optional[Dict[str, Any]]):
        if not device:
            return
        key = device.get("key") or (
            device.get("source_folder"), device.get("section"), device.get("device_num"),
        )
        if key in seen:
            return
        seen.add(key)
        devices.append(device)

    _add(current_device)
    for folder, key in (compare_device_keys or {}).items():
        for device in iter_devices(model, folder):
            if device.get("key") == tuple(key) or (
                isinstance(key, (list, tuple)) and len(key) == 3 and device.get("key") == (str(key[0]), str(key[1]), int(key[2]))
            ):
                _add(device)
                break

    for device in devices:
        classified = classify_device(device, model, excluded_keys, split_before)
        label = device.get("label") or f"{device.get('section')}_{device.get('device_num')}"
        stem = f"lifetime_{_origin_stem(device.get('source_folder'))}_{_origin_stem(label)}"
        _export_lifetime_file(out_dir, stem, classified["sweeps"], mode, read_voltage)

    for row in model.get("folders") or []:
        folder = row["source_folder"]
        summary = summarize_sample(
            model, folder, excluded_keys, split_before, mode, read_voltage,
            include_keys=include_keys,
        )
        _export_sample_band(out_dir, sample_labels.get(folder) if sample_labels else folder, summary)
    return out_dir
