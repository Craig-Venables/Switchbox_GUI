"""
Core jump detection and sample analysis for the Filament Jump Finder.

Loads curves once (one or more folders), detects candidate steps at a low floor
ratio, then filters live by ratio / voltage window / min current / upward-only.
Builds a device registry with classification for yield comparisons.
"""

import csv
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Sequence, Iterable

import numpy as np

try:
    from tools.device_visualizer.data.data_discovery import DataDiscovery
    from tools.device_visualizer.data.data_loader import DataLoader
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.device_visualizer.data.data_discovery import DataDiscovery
    from tools.device_visualizer.data.data_loader import DataLoader

# Floor ratio used when scanning on load; live UI filters upward from this.
DETECTION_FLOOR_RATIO = 1.5

# Thesis LLM classification exports (written by thesis_llm.classification_export)
THESIS_LLM_EXPORT_SUBDIR = Path("sample_analysis") / "thesis_llm_exports"


def _natural_sort_key(path: Path) -> List:
    """Sort key for paths with numeric parts (1, 2, 10 not 1, 10, 2)."""
    def atoi(text):
        return int(text) if text.isdigit() else text.lower()
    return [atoi(c) for c in re.split(r'(\d+)', path.name)]


def _natural_sort_key_for_name(name: str) -> List:
    """Sort key for filename strings (7-FS before 21-FS, not lexicographic)."""
    def atoi(text):
        return int(text) if text.isdigit() else text.lower()
    return [atoi(c) for c in re.split(r'(\d+)', str(name))]


def jump_decision_key(jump: Dict[str, Any]) -> str:
    """Stable key for manual Jump / Not a jump decisions across threshold changes."""
    path = jump.get('file_path')
    path_str = str(path) if path is not None else jump.get('filename', '')
    return f"{path_str}::{jump.get('index', -1)}"


def is_memristive_type(device_type: str) -> bool:
    """True if classification type looks memristive."""
    return 'mem' in (device_type or '').lower()


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ('1', 'true', 'yes', 'y', 't')


def find_thesis_llm_exports_dir(sample_folder: Path) -> Optional[Path]:
    """
    Locate ``sample_analysis/thesis_llm_exports`` under a sample folder,
    or a few parents up if a nested device path was given.
    """
    p = Path(sample_folder)
    try:
        p = p.resolve()
    except OSError:
        pass
    candidates = [p]
    cur = p
    for _ in range(4):
        if cur.parent == cur:
            break
        cur = cur.parent
        candidates.append(cur)
    for candidate in candidates:
        exports = candidate / THESIS_LLM_EXPORT_SUBDIR
        if exports.is_dir():
            return exports
    return None


def find_device_summary_csv(sample_folder: Path) -> Optional[Path]:
    """Prefer ``{sid}_device_summary.csv`` inside thesis_llm_exports."""
    exports = find_thesis_llm_exports_dir(sample_folder)
    if exports is None:
        return None
    matches = sorted(exports.glob("*_device_summary.csv"))
    if matches:
        # Prefer file whose stem starts with a short sample id if several exist
        return matches[0]
    # Fallback: any device_summary in devices/ subfolder is wrong schema (per-device);
    # sample-level only.
    return None


def _parse_optional_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ('nan', 'none', ''):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_thesis_device_classifications(sample_folder: Path) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """
    Load per-device classification from thesis_llm_exports ``*_device_summary.csv``.

    Keyed by (section, device_number). Uses:
      - endpoint_type (display classification; fallback majority_type)
      - worked_memristive (primary memristive flag)
      - memristive_sweep_count, ndr_index_max, first_jump_voltage_V, R_at_0p5V_fold_change
    """
    csv_path = find_device_summary_csv(sample_folder)
    out: Dict[Tuple[str, int], Dict[str, Any]] = {}
    if csv_path is None or not csv_path.exists():
        return out
    try:
        with csv_path.open(newline='', encoding='utf-8-sig') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                section = str(row.get('section', '') or '').strip()
                try:
                    device_num = int(float(str(row.get('device_number', '')).strip()))
                except (TypeError, ValueError):
                    continue
                endpoint = str(row.get('endpoint_type') or row.get('majority_type') or 'Unknown').strip()
                worked = _parse_bool(row.get('worked_memristive', False))
                is_mem = worked
                try:
                    score = float(row.get('memristive_sweep_count') or 0)
                except (TypeError, ValueError):
                    score = 0.0
                out[(section, device_num)] = {
                    'classification': endpoint or 'Unknown',
                    'is_memristive': bool(is_mem),
                    'worked_memristive': worked,
                    'majority_type': str(row.get('majority_type') or ''),
                    'endpoint_type': str(row.get('endpoint_type') or ''),
                    'score': score,
                    'memristive_sweep_count': score,
                    'ndr_index_max': _parse_optional_float(row.get('ndr_index_max')),
                    'first_jump_voltage_V': _parse_optional_float(row.get('first_jump_voltage_V')),
                    'R_at_0p5V_fold_change': _parse_optional_float(row.get('R_at_0p5V_fold_change')),
                    'has_classification': True,
                    'device_key': str(row.get('device_key') or ''),
                    'source_csv': str(csv_path),
                }
    except OSError:
        return {}
    return out


def find_iv_classifications_csv(sample_folder: Path) -> Optional[Path]:
    """Locate ``*_iv_classifications.csv`` under thesis_llm_exports."""
    exports = find_thesis_llm_exports_dir(sample_folder)
    if exports is None:
        return None
    matches = sorted(exports.glob("*_iv_classifications.csv"))
    return matches[0] if matches else None


def load_best_sweep_paths(
    sample_folder: Path,
) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """
    For each device, pick the best IV sweep from ``*_iv_classifications.csv``
    (highest memristivity_score; prefer predicted_type containing 'mem').
    Returns (section, device_num) -> {filename, file_path, memristivity_score, predicted_type}.
    """
    csv_path = find_iv_classifications_csv(sample_folder)
    best: Dict[Tuple[str, int], Dict[str, Any]] = {}
    if csv_path is None or not csv_path.exists():
        return best
    try:
        with csv_path.open(newline='', encoding='utf-8-sig') as fh:
            for row in csv.DictReader(fh):
                section = str(row.get('section', '') or '').strip()
                try:
                    device_num = int(float(str(row.get('device_number', '')).strip()))
                except (TypeError, ValueError):
                    continue
                score = _parse_optional_float(row.get('memristivity_score')) or 0.0
                pred = str(row.get('predicted_type') or '')
                mem_bonus = 1000.0 if is_memristive_type(pred) else 0.0
                rank = mem_bonus + score
                key = (section, device_num)
                prev = best.get(key)
                prev_rank = (prev or {}).get('_rank', -1)
                if rank >= prev_rank:
                    fpath = row.get('file_path') or ''
                    fname = str(row.get('filename') or '').strip()
                    best[key] = {
                        'filename': fname,
                        'file_path': fpath,
                        'memristivity_score': score,
                        'predicted_type': pred,
                        '_rank': rank,
                    }
    except OSError:
        return {}
    for v in best.values():
        v.pop('_rank', None)
    return best


def read_device_classification(
    device_path: Path,
    section: str = '',
    device_num: int = 0,
    class_lookup: Optional[Dict[Tuple[str, int], Dict[str, Any]]] = None,
    sample_folder: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Classification for a device from thesis_llm_exports device_summary CSV.

    Falls back to Unknown if the export is missing (no longer uses classification_log.txt).
    """
    unknown = {
        'classification': 'Unknown',
        'is_memristive': False,
        'worked_memristive': False,
        'score': 0.0,
        'has_classification': False,
    }
    lookup = class_lookup
    if lookup is None and sample_folder is not None:
        lookup = load_thesis_device_classifications(sample_folder)
    if lookup is None and device_path is not None:
        lookup = load_thesis_device_classifications(Path(device_path))
    if not lookup:
        return unknown
    key = (str(section), int(device_num))
    if key in lookup:
        return dict(lookup[key])
    # Case-insensitive section match
    for (sec, num), info in lookup.items():
        if num == int(device_num) and sec.lower() == str(section).lower():
            return dict(info)
    return unknown


def find_jumps_in_curve(
    voltage: np.ndarray,
    current: np.ndarray,
    min_ratio: float = 10.0,
    min_current: Optional[float] = None,
    upward_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Detect current jumps between consecutive points in an IV curve (vectorized).

    A jump is when max(|I[i]|,|I[i+1]|) / max(min(|I[i]|,|I[i+1]|), 1e-15) >= min_ratio.
    """
    if len(voltage) < 2 or len(current) < 2:
        return []
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(len(voltage), len(current)) - 1
    if n < 1:
        return []

    v0 = voltage[:n]
    v1 = voltage[1:n + 1]
    i0 = current[:n]
    i1 = current[1:n + 1]
    eps = 1e-15
    abs_i0 = np.abs(i0) + eps
    abs_i1 = np.abs(i1) + eps
    lo = np.minimum(abs_i0, abs_i1)
    hi = np.maximum(abs_i0, abs_i1)
    ratio = hi / np.maximum(lo, eps)

    mask = ratio >= min_ratio
    if min_current is not None:
        mask &= lo >= min_current
    if upward_only:
        mask &= i1 > i0

    indices = np.nonzero(mask)[0]
    results = []
    for i in indices:
        ii = int(i)
        results.append({
            'voltage_mid': float(0.5 * (v0[ii] + v1[ii])),
            'index': ii,
            'ratio': float(ratio[ii]),
            'v_before': float(v0[ii]),
            'v_after': float(v1[ii]),
            'i_before': float(i0[ii]),
            'i_after': float(i1[ii]),
        })
    return results


def _parse_device_id(device_id: str) -> Tuple[str, int]:
    """Return (section, device_num) from device_id e.g. 'G_1' -> ('G', 1)."""
    parts = device_id.split('_')
    if len(parts) >= 2:
        try:
            device_num = int(parts[-1])
            section = '_'.join(parts[:-1])
            return section, device_num
        except ValueError:
            pass
    return device_id, 0


def _scan_device(
    device_path: Path,
    device_id: str,
    section: str,
    device_num: int,
    source_folder: str,
    source_path: Path,
    detection_floor: float,
    class_lookup: Optional[Dict[Tuple[str, int], Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[Path, Dict[str, Any]]]:
    """Scan one device folder: classification (thesis exports), curves, jumps."""
    class_info = read_device_classification(
        device_path,
        section=section,
        device_num=device_num,
        class_lookup=class_lookup,
        sample_folder=source_path,
    )
    device_rec = {
        'source_folder': source_folder,
        'source_path': Path(source_path),
        'section': section,
        'device_num': device_num,
        'device_id': device_id,
        'device_path': Path(device_path),
        'classification': class_info['classification'],
        'is_memristive': class_info['is_memristive'],
        'worked_memristive': class_info.get('worked_memristive', False),
        'score': class_info['score'],
        'memristive_sweep_count': class_info.get('memristive_sweep_count', class_info.get('score', 0)),
        'ndr_index_max': class_info.get('ndr_index_max'),
        'first_jump_voltage_V': class_info.get('first_jump_voltage_V'),
        'R_at_0p5V_fold_change': class_info.get('R_at_0p5V_fold_change'),
        'has_classification': class_info['has_classification'],
        'device_key': class_info.get('device_key', ''),
        'classification_csv': class_info.get('source_csv', ''),
        'best_sweep': None,  # filled by load_folder
    }
    jumps: List[Dict[str, Any]] = []
    curve_cache: Dict[Path, Dict[str, Any]] = {}
    raw_files = DataDiscovery.find_raw_data_files(device_path)
    raw_files.sort(key=_natural_sort_key)
    for txt_path in raw_files:
        voltage, current, time_arr = DataLoader.load_raw_measurement(txt_path)
        voltage = np.asarray(voltage, dtype=float)
        current = np.asarray(current, dtype=float)
        if len(voltage) < 2 or len(current) < 2:
            continue
        curve_cache[txt_path] = {
            'voltage': voltage,
            'current': current,
            'time': time_arr,
            'section': section,
            'device_num': device_num,
            'device_id': device_id,
            'filename': txt_path.name,
            'source_folder': source_folder,
        }
        file_jumps = find_jumps_in_curve(
            voltage, current,
            min_ratio=detection_floor,
            min_current=None,
            upward_only=False,
        )
        for j in file_jumps:
            j = dict(j)
            j['included'] = True
            j['section'] = section
            j['device_num'] = device_num
            j['device_id'] = device_id
            j['filename'] = txt_path.name
            j['file_path'] = txt_path
            j['voltage'] = j['voltage_mid']
            j['source_folder'] = source_folder
            j['source_path'] = Path(source_path)
            jumps.append(j)
    return device_rec, jumps, curve_cache


def load_folder(
    folder_path: Path,
    detection_floor: float = DETECTION_FLOOR_RATIO,
) -> Dict[str, Any]:
    """
    Load one folder as either a sample (nested section/digit devices) or a
    single device folder with raw measurement files.

    Classification comes from ``sample_analysis/thesis_llm_exports/*_device_summary.csv``.
    """
    folder_path = Path(folder_path)
    source_folder = folder_path.name
    empty = {
        'source_path': folder_path,
        'source_folder': source_folder,
        'devices': [],
        'device_registry': [],
        'jumps': [],
        'section_device_nums': {},
        'curve_cache': {},
        'classification_csv': None,
    }
    if not folder_path.exists():
        return empty

    class_lookup = load_thesis_device_classifications(folder_path)
    class_csv = find_device_summary_csv(folder_path)
    best_sweeps = load_best_sweep_paths(folder_path)

    nested = DataDiscovery.find_device_folders(folder_path)
    device_list: List[Tuple[str, Path, str, int]] = []
    if nested:
        for device_id, device_path in nested:
            section, device_num = _parse_device_id(device_id)
            device_list.append((device_id, device_path, section, device_num))
    else:
        raw = DataDiscovery.find_raw_data_files(folder_path)
        if raw:
            # Single device folder (e.g. D110 with measurement txts)
            device_id = source_folder
            section = source_folder
            device_num = 0
            m = re.search(r'(\d+)', source_folder)
            if m:
                try:
                    device_num = int(m.group(1))
                except ValueError:
                    pass
            device_list.append((device_id, folder_path, section, device_num))

    section_device_nums: Dict[str, List[int]] = {}
    jumps: List[Dict[str, Any]] = []
    curve_cache: Dict[Path, Dict[str, Any]] = {}
    device_registry: List[Dict[str, Any]] = []
    device_ids: List[str] = []

    for device_id, device_path, section, device_num in device_list:
        section_device_nums.setdefault(section, []).append(device_num)
        device_ids.append(device_id)
        rec, dj, cc = _scan_device(
            device_path, device_id, section, device_num,
            source_folder, folder_path, detection_floor,
            class_lookup=class_lookup,
        )
        sweep = best_sweeps.get((section, device_num))
        if sweep is None:
            # case-insensitive section
            for (sec, num), info in best_sweeps.items():
                if num == device_num and sec.lower() == section.lower():
                    sweep = info
                    break
        rec['best_sweep'] = sweep
        device_registry.append(rec)
        jumps.extend(dj)
        curve_cache.update(cc)

    for section in section_device_nums:
        section_device_nums[section] = sorted(set(section_device_nums[section]))

    return {
        'source_path': folder_path,
        'source_folder': source_folder,
        'devices': device_ids,
        'device_registry': device_registry,
        'jumps': jumps,
        'section_device_nums': section_device_nums,
        'curve_cache': curve_cache,
        'classification_csv': str(class_csv) if class_csv else None,
        'n_classified': sum(1 for d in device_registry if d.get('has_classification')),
    }


def load_folders(
    folder_paths: Sequence[Path],
    detection_floor: float = DETECTION_FLOOR_RATIO,
) -> Dict[str, Any]:
    """Load and merge multiple folders into one session pool."""
    folder_paths = [Path(p) for p in folder_paths]
    all_jumps: List[Dict[str, Any]] = []
    device_registry: List[Dict[str, Any]] = []
    curve_cache: Dict[Path, Dict[str, Any]] = {}
    devices: List[str] = []
    section_device_nums: Dict[str, List[int]] = {}
    loaded_folders: List[Dict[str, Any]] = []

    for path in folder_paths:
        loaded = load_folder(path, detection_floor=detection_floor)
        loaded_folders.append({
            'path': str(Path(path).resolve()),
            'source_folder': loaded['source_folder'],
            'n_devices': len(loaded['device_registry']),
            'n_jumps': len(loaded['jumps']),
        })
        all_jumps.extend(loaded['jumps'])
        device_registry.extend(loaded['device_registry'])
        curve_cache.update(loaded['curve_cache'])
        devices.extend(loaded['devices'])
        for section, nums in loaded['section_device_nums'].items():
            section_device_nums.setdefault(section, []).extend(nums)

    for section in section_device_nums:
        section_device_nums[section] = sorted(set(section_device_nums[section]))

    return {
        'folder_paths': [Path(p) for p in folder_paths],
        'loaded_folders': loaded_folders,
        'devices': devices,
        'device_registry': device_registry,
        'jumps': all_jumps,
        'section_device_nums': section_device_nums,
        'curve_cache': curve_cache,
        # Back-compat: first folder as sample_path
        'sample_path': folder_paths[0] if folder_paths else None,
    }


def load_sample(
    sample_path: Path,
    detection_floor: float = DETECTION_FLOOR_RATIO,
) -> Dict[str, Any]:
    """Back-compat: load a single folder (sample or device)."""
    return load_folders([sample_path], detection_floor=detection_floor)


def filter_jumps(
    jumps: List[Dict[str, Any]],
    min_ratio: float = 10.0,
    v_min: Optional[float] = None,
    v_max: Optional[float] = None,
    use_abs_v: bool = False,
    min_current: Optional[float] = None,
    upward_only: bool = False,
    decisions: Optional[Dict[str, bool]] = None,
) -> List[Dict[str, Any]]:
    """Filter the cached jump list by live controls."""
    decisions = decisions or {}
    out: List[Dict[str, Any]] = []
    for j in jumps:
        if j.get('ratio', 0) < min_ratio:
            continue
        v = j.get('voltage_mid', j.get('voltage'))
        if v is None:
            continue
        v_cmp = abs(float(v)) if use_abs_v else float(v)
        if v_min is not None and v_cmp < v_min:
            continue
        if v_max is not None and v_cmp > v_max:
            continue
        if min_current is not None:
            lo = min(abs(j.get('i_before', 0)), abs(j.get('i_after', 0)))
            if lo < min_current:
                continue
        if upward_only and j.get('i_after', 0) <= j.get('i_before', 0):
            continue
        row = dict(j)
        key = jump_decision_key(j)
        if key in decisions:
            row['included'] = bool(decisions[key])
        else:
            row['included'] = bool(j.get('included', True))
        out.append(row)
    return out


def device_key(rec_or_jump: Dict[str, Any]) -> Tuple[str, str, int]:
    """Unique device identity across multi-folder sessions."""
    return (
        str(rec_or_jump.get('source_folder', '')),
        str(rec_or_jump.get('section', '')),
        int(rec_or_jump.get('device_num', 0) or 0),
    )


def devices_with_accepted_jumps(
    filtered_jumps: List[Dict[str, Any]],
    excluded_files_from_first: Optional[set] = None,
) -> set:
    """Set of device_key for devices that have at least one accepted jump."""
    excluded = excluded_files_from_first or set()
    keys = set()
    for j in filtered_jumps:
        if not j.get('included', True):
            continue
        sf = j.get('source_folder', '')
        file_key_4 = (sf, j.get('section'), j.get('device_num'), j.get('filename', ''))
        file_key_3 = (j.get('section'), j.get('device_num'), j.get('filename', ''))
        if file_key_4 in excluded or file_key_3 in excluded:
            # still counts as having a jump for yield if other files have jumps;
            # yield uses any accepted jump, not first-occurrence exclusion
            pass
        keys.add(device_key(j))
    return keys


# Soft / strong NDR thresholds (same as thesis sample_summary blurbs)
NDR_SOFT_THRESHOLD = 0.05
NDR_STRONG_THRESHOLD = 0.15


def compute_yield_summary(
    device_registry: List[Dict[str, Any]],
    filtered_jumps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Per-device has_jump flags and count tables for Compare tab / Origin export.
    Also attaches NDR comparison stats and best memristive IV pairs.
    """
    with_jump = devices_with_accepted_jumps(filtered_jumps)
    device_rows = []
    counts_by_folder: Dict[str, Dict[str, int]] = {}

    def _ensure(folder: str):
        if folder not in counts_by_folder:
            counts_by_folder[folder] = {
                'WithJump': 0, 'NoJump': 0,
                'MemWithJump': 0, 'MemNoJump': 0,
                'UnknownClass': 0,
            }

    for rec in device_registry:
        sf = rec.get('source_folder', '')
        _ensure(sf)
        key = device_key(rec)
        has_jump = key in with_jump
        is_mem = bool(rec.get('is_memristive'))
        has_class = bool(rec.get('has_classification'))
        ndr = rec.get('ndr_index_max')
        try:
            ndr_f = float(ndr) if ndr is not None and str(ndr).strip() != '' else None
        except (TypeError, ValueError):
            ndr_f = None
        row = {
            'source_folder': sf,
            'section': rec.get('section', ''),
            'device_num': rec.get('device_num', ''),
            'device_id': rec.get('device_id', ''),
            'has_jump': has_jump,
            'classification': rec.get('classification', 'Unknown'),
            'is_memristive': is_mem,
            'worked_memristive': bool(rec.get('worked_memristive', is_mem)),
            'has_classification': has_class,
            'ndr_index_max': ndr_f,
            'memristive_sweep_count': rec.get('memristive_sweep_count', rec.get('score', 0)),
            'R_at_0p5V_fold_change': rec.get('R_at_0p5V_fold_change'),
            'first_jump_voltage_V': rec.get('first_jump_voltage_V'),
            'device_path': rec.get('device_path'),
            'best_sweep': rec.get('best_sweep'),
            'source_path': rec.get('source_path'),
        }
        device_rows.append(row)
        if has_jump:
            counts_by_folder[sf]['WithJump'] += 1
        else:
            counts_by_folder[sf]['NoJump'] += 1
        if not has_class:
            counts_by_folder[sf]['UnknownClass'] += 1
        elif is_mem:
            if has_jump:
                counts_by_folder[sf]['MemWithJump'] += 1
            else:
                counts_by_folder[sf]['MemNoJump'] += 1

    combined = {
        'WithJump': 0, 'NoJump': 0,
        'MemWithJump': 0, 'MemNoJump': 0,
        'UnknownClass': 0,
    }
    for c in counts_by_folder.values():
        for k in combined:
            combined[k] += c[k]

    return {
        'device_rows': device_rows,
        'counts_by_folder': counts_by_folder,
        'combined': combined,
        'ndr_stats': compute_ndr_comparison(device_rows),
        'best_memristive_pairs': pick_best_memristive_pairs(device_rows),
        'with_jump_keys': with_jump,
    }


def _mean(vals: List[float]) -> Optional[float]:
    return float(np.mean(vals)) if vals else None


def _ndr_group_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ndrs = [r['ndr_index_max'] for r in rows if r.get('ndr_index_max') is not None]
    soft = sum(1 for v in ndrs if v >= NDR_SOFT_THRESHOLD)
    strong = sum(1 for v in ndrs if v >= NDR_STRONG_THRESHOLD)
    return {
        'n': len(rows),
        'n_with_ndr': len(ndrs),
        'mean_ndr': _mean(ndrs),
        'median_ndr': float(np.median(ndrs)) if ndrs else None,
        'max_ndr': max(ndrs) if ndrs else None,
        'n_soft_ndr': soft,
        'n_strong_ndr': strong,
        'frac_soft': (soft / len(ndrs)) if ndrs else None,
        'frac_strong': (strong / len(ndrs)) if ndrs else None,
        'ndr_values': ndrs,
    }


def compute_ndr_comparison(device_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """NDR (ndr_index_max) for With-jump vs No-jump, overall and memristive-only."""
    def split(rows):
        w = [r for r in rows if r.get('has_jump')]
        n = [r for r in rows if not r.get('has_jump')]
        return {'with_jump': _ndr_group_stats(w), 'no_jump': _ndr_group_stats(n)}

    all_rows = list(device_rows)
    mem_rows = [r for r in device_rows if r.get('is_memristive')]
    by_folder: Dict[str, Any] = {}
    folders = sorted({r.get('source_folder', '') for r in device_rows})
    for sf in folders:
        fr = [r for r in device_rows if r.get('source_folder') == sf]
        by_folder[sf] = {
            'all': split(fr),
            'memristive': split([r for r in fr if r.get('is_memristive')]),
        }
    return {
        'all': split(all_rows),
        'memristive': split(mem_rows),
        'by_folder': by_folder,
    }


def _device_quality_key(row: Dict[str, Any]) -> Tuple[float, float, float]:
    """Higher is better for picking a showcase memristive device."""
    sweeps = float(row.get('memristive_sweep_count') or 0)
    ndr = float(row.get('ndr_index_max') or 0)
    rfold = row.get('R_at_0p5V_fold_change')
    try:
        rf = abs(np.log10(max(float(rfold), 1e-30))) if rfold is not None else 0.0
    except (TypeError, ValueError):
        rf = 0.0
    return (sweeps, ndr, rf)


def pick_best_memristive_pairs(
    device_rows: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Optional[Dict[str, Any]]]]:
    """Per folder: best worked-memristive with jump vs without (for IV overlay)."""
    folders = sorted({r.get('source_folder', '') for r in device_rows})
    out: Dict[str, Dict[str, Optional[Dict[str, Any]]]] = {}
    for sf in folders:
        with_j, no_j = memristive_devices_by_jump(device_rows, source_folder=sf)
        out[sf] = {
            'with_jump': max(with_j, key=_device_quality_key) if with_j else None,
            'no_jump': max(no_j, key=_device_quality_key) if no_j else None,
        }
    return out


def memristive_devices_by_jump(
    device_rows: List[Dict[str, Any]],
    source_folder: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split worked-memristive devices into (with_jump, no_jump) lists.

    If ``source_folder`` is set, only that folder is included; otherwise all folders.
    """
    rows = [
        r for r in device_rows
        if r.get('is_memristive')
        and (source_folder is None or r.get('source_folder') == source_folder)
    ]
    with_j = [r for r in rows if r.get('has_jump')]
    no_j = [r for r in rows if not r.get('has_jump')]
    return with_j, no_j


def resolve_device_iv_curve(
    device_row: Dict[str, Any],
    curve_cache: Optional[Dict[Path, Dict[str, Any]]] = None,
) -> Optional[Tuple[np.ndarray, np.ndarray, str]]:
    """Load V/I for a device's best sweep (or last raw file). Returns (V, I, label)."""
    curve_cache = curve_cache or {}
    device_path = device_row.get('device_path')
    if device_path is not None:
        device_path = Path(device_path)

    candidates: List[Path] = []
    sweep = device_row.get('best_sweep') or {}
    fpath = sweep.get('file_path') if isinstance(sweep, dict) else None
    fname = sweep.get('filename') if isinstance(sweep, dict) else None
    if fpath:
        candidates.append(Path(fpath))
    if device_path and fname:
        candidates.append(device_path / fname)
        if not str(fname).lower().endswith('.txt'):
            candidates.append(device_path / f"{fname}.txt")
    if device_path and device_path.is_dir():
        raws = DataDiscovery.find_raw_data_files(device_path)
        raws.sort(key=_natural_sort_key)
        if raws:
            candidates.append(raws[-1])

    seen = set()
    for path in candidates:
        try:
            path = Path(path)
        except TypeError:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        cached = curve_cache.get(path)
        if cached is None:
            for cp, data in curve_cache.items():
                if Path(cp).name == path.name or (
                    fname and Path(cp).stem == Path(str(fname)).stem
                ):
                    cached = data
                    path = Path(cp)
                    break
        if cached is not None:
            v = np.asarray(cached['voltage'], dtype=float)
            i = np.asarray(cached['current'], dtype=float)
            label = f"{device_row.get('section')}_{device_row.get('device_num')} / {path.name}"
            return v, i, label
        if path.exists():
            try:
                voltage, current, _ = DataLoader.load_raw_measurement(path)
                v = np.asarray(voltage, dtype=float)
                i = np.asarray(current, dtype=float)
                if len(v) < 2:
                    continue
                label = f"{device_row.get('section')}_{device_row.get('device_num')} / {path.name}"
                return v, i, label
            except Exception:
                continue
    return None


def common_parent(paths: Iterable[Path]) -> Optional[Path]:
    """Return common parent of paths, or None if empty / no shared parent."""
    paths = [Path(p).resolve() for p in paths]
    if not paths:
        return None
    try:
        import os
        return Path(os.path.commonpath([str(p) for p in paths]))
    except ValueError:
        return paths[0].parent


def origin_export_root(folder_paths: Sequence[Path]) -> Path:
    """
    Prefer common parent of loaded folders for origin data/;
    if folders do not share a useful parent, use parent of the first folder.
    """
    paths = [Path(p).resolve() for p in folder_paths]
    if not paths:
        return Path.cwd()
    if len(paths) == 1:
        return paths[0]
    parent = common_parent(paths)
    if parent is None:
        return paths[0].parent
    # If commonpath is one of the folders themselves, use its parent
    resolved = {p.resolve() for p in paths}
    if parent.resolve() in resolved:
        return parent.parent
    return parent


def analyse_sample(
    sample_path: Path,
    min_ratio: float = 10.0,
    min_current: Optional[float] = None,
    upward_only: bool = False,
) -> Dict[str, Any]:
    """Back-compat wrapper: load then filter at the given threshold."""
    loaded = load_sample(sample_path, detection_floor=DETECTION_FLOOR_RATIO)
    filtered = filter_jumps(
        loaded['jumps'],
        min_ratio=min_ratio,
        min_current=min_current,
        upward_only=upward_only,
    )
    jumps = [j for j in filtered if j.get('included', True)]
    return {
        'devices': loaded['devices'],
        'jumps': jumps,
        'section_device_nums': loaded['section_device_nums'],
        'curve_cache': loaded['curve_cache'],
        'sample_path': loaded.get('sample_path'),
        'device_registry': loaded.get('device_registry', []),
    }


def get_first_and_all(
    jumps: List[Dict],
    excluded_files_from_first: Optional[set] = None,
    accepted_only: bool = True,
) -> Tuple[List[Dict], List[Dict]]:
    """
    From flat list of jump dicts, build first-occurrence and all-occurrence lists.
    Device identity includes source_folder for multi-folder sessions.
    """
    excluded = excluded_files_from_first or set()
    pool = [j for j in jumps if j.get('included', True)] if accepted_only else list(jumps)
    by_device: Dict[Tuple[str, str, int], List[Dict]] = {}
    for j in pool:
        key = device_key(j)
        by_device.setdefault(key, []).append(j)
    first_list: List[Dict] = []
    all_list: List[Dict] = []
    for key in sorted(by_device.keys(), key=lambda x: (x[0], x[1], x[2])):
        device_jumps = by_device[key]
        device_jumps.sort(
            key=lambda x: (_natural_sort_key_for_name(x.get('filename', '')), x.get('index', 0))
        )
        for j in device_jumps:
            sf = j.get('source_folder', '')
            file_key_4 = (sf, j['section'], j['device_num'], j.get('filename', ''))
            file_key_3 = (j['section'], j['device_num'], j.get('filename', ''))
            if file_key_4 not in excluded and file_key_3 not in excluded:
                first_list.append(j)
                break
        all_list.extend(device_jumps)
    return first_list, all_list


def histogram_bins(
    voltages: List[float],
    bin_width: float = 0.2,
    absolute: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return (bin_centers, counts) for Origin histogram export."""
    if not voltages:
        return np.array([]), np.array([])
    vals = [abs(v) for v in voltages] if absolute else list(voltages)
    v_min, v_max = min(vals), max(vals)
    if absolute:
        start = 0.0
        stop = np.ceil(v_max / bin_width) * bin_width + bin_width * 0.01
    else:
        start = np.floor(v_min / bin_width) * bin_width
        stop = np.ceil(v_max / bin_width) * bin_width + bin_width * 0.01
    edges = np.arange(start, stop, bin_width)
    if len(edges) < 2:
        edges = np.array([start, start + bin_width])
    counts, edges = np.histogram(vals, bins=edges)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return centers, counts.astype(int)
