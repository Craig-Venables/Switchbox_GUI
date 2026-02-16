"""
Core jump detection and sample analysis for the Filament Jump Finder.

Finds large current jumps (configurable ratio threshold) in IV data,
with optional min current floor and upward-only filtering.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

# Import from device_visualizer when run from project root (e.g. python -m tools.filament_jump_finder)
try:
    from tools.device_visualizer.data.data_discovery import DataDiscovery
    from tools.device_visualizer.data.data_loader import DataLoader
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.device_visualizer.data.data_discovery import DataDiscovery
    from tools.device_visualizer.data.data_loader import DataLoader


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


def find_jumps_in_curve(
    voltage: np.ndarray,
    current: np.ndarray,
    min_ratio: float = 10.0,
    min_current: Optional[float] = None,
    upward_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Detect current jumps between consecutive points in an IV curve.

    A jump is when max(|I[i]|,|I[i+1]|) / max(min(|I[i]|,|I[i+1]|), 1e-15) >= min_ratio.
    Optionally filter by min current (both points above floor) and upward-only.

    Args:
        voltage: Voltage array (V).
        current: Current array (A).
        min_ratio: Minimum ratio for a step to count as a jump (default 10 = 1 order of magnitude).
        min_current: If set, only count jumps where min(|I[i]|,|I[i+1]|) > this value (A).
        upward_only: If True, only count steps where current increases (I[i+1] > I[i] in signed sense).

    Returns:
        List of dicts: voltage_mid, index, ratio, v_before, v_after, i_before, i_after.
    """
    if len(voltage) < 2 or len(current) < 2:
        return []
    voltage = np.asarray(voltage, dtype=float)
    current = np.asarray(current, dtype=float)
    n = min(len(voltage), len(current)) - 1
    results = []
    eps = 1e-15
    for i in range(n):
        v0, v1 = voltage[i], voltage[i + 1]
        i0, i1 = current[i], current[i + 1]
        abs_i0 = abs(i0) + eps
        abs_i1 = abs(i1) + eps
        lo = min(abs_i0, abs_i1)
        hi = max(abs_i0, abs_i1)
        ratio = hi / max(lo, eps)
        if ratio < min_ratio:
            continue
        if min_current is not None and lo < min_current:
            continue
        if upward_only and i1 <= i0:
            continue
        v_mid = 0.5 * (v0 + v1)
        results.append({
            'voltage_mid': float(v_mid),
            'index': i,
            'ratio': float(ratio),
            'v_before': float(v0),
            'v_after': float(v1),
            'i_before': float(i0),
            'i_after': float(i1),
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


def analyse_sample(
    sample_path: Path,
    min_ratio: float = 10.0,
    min_current: Optional[float] = None,
    upward_only: bool = False,
) -> Dict[str, Any]:
    """
    Scan sample folder: discover devices and raw files, detect jumps in each file.

    Returns a structure with:
      - devices: list of device_id (str)
      - jumps: list of jump records, each with section, device_num, filename, file_path,
               and a list of jump dicts (voltage_mid, index, ratio, ...), each with 'included' (bool).
      - section_device_nums: dict section -> list of device_num for ordering
    So we can derive first/all from jumps by filtering on included and by device.
    """

    sample_path = Path(sample_path)
    if not sample_path.exists():
        return {'devices': [], 'jumps': [], 'section_device_nums': {}}

    device_folders = DataDiscovery.find_device_folders(sample_path)
    section_device_nums = {}
    jumps = []

    for device_id, device_path in device_folders:
        section, device_num = _parse_device_id(device_id)
        section_device_nums.setdefault(section, []).append(device_num)
        raw_files = DataDiscovery.find_raw_data_files(device_path)
        raw_files.sort(key=_natural_sort_key)

        for txt_path in raw_files:
            voltage, current, _ = DataLoader.load_raw_measurement(txt_path)
            if len(voltage) < 2 or len(current) < 2:
                continue
            file_jumps = find_jumps_in_curve(
                voltage, current,
                min_ratio=min_ratio,
                min_current=min_current,
                upward_only=upward_only,
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
                jumps.append(j)

    for section in section_device_nums:
        section_device_nums[section] = sorted(set(section_device_nums[section]))

    return {
        'devices': [did for did, _ in device_folders],
        'jumps': jumps,
        'section_device_nums': section_device_nums,
        'voltage_cache': {},  # optional: path -> (V, I) for inspect dialog
    }


def get_first_and_all(
    jumps: List[Dict],
    excluded_files_from_first: Optional[set] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    From flat list of jump dicts (each with section, device_num, filename, voltage, included),
    build first-occurrence and all-occurrence lists using only included jumps.

    If excluded_files_from_first is provided, jumps from those (section, device_num, filename)
    are excluded from first_list (but still appear in all_list).
    """
    excluded = excluded_files_from_first or set()
    included = [j for j in jumps if j.get('included', True)]
    by_device = {}
    for j in included:
        key = (j['section'], j['device_num'])
        if key not in by_device:
            by_device[key] = []
        by_device[key].append(j)
    first_list = []
    all_list = []
    for key in sorted(by_device.keys(), key=lambda x: (x[0], x[1])):
        device_jumps = by_device[key]
        device_jumps.sort(key=lambda x: (_natural_sort_key_for_name(x.get('filename', '')), x.get('index', 0)))
        # For first: skip jumps from excluded files, take first remaining
        for j in device_jumps:
            file_key = (j['section'], j['device_num'], j.get('filename', ''))
            if file_key not in excluded:
                first_list.append(j)
                break
        all_list.extend(device_jumps)
    return first_list, all_list
