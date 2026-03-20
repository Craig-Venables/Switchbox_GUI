"""
First-Sweep Resistance Calculator
===================================

Finds the first measurement file (alphabetically) for a device and computes
the average resistance over the window 0 V <= V <= voltage_val.

No sweep files are saved to any subfolder — this module is compute-only.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, Optional

import numpy as np


_EXCLUDE_FILES = {
    "classification_log.txt",
    "classification_summary.txt",
    "log.txt",
}


def get_first_sweep_resistance(
    device_dir: str,
    voltage_val: float = 0.1,
    log_fn: Callable[[str], None] = print,
) -> Dict:
    """Load the first .txt measurement file alphabetically and return average resistance.

    Parameters
    ----------
    device_dir:
        Path to the device folder (e.g. .../MySample/A/01/).
    voltage_val:
        Upper bound of the voltage window used to compute resistance.
    log_fn:
        Logging callback.

    Returns
    -------
    dict with keys:
        - ``resistance``: float or None
        - ``file``: filename used (str)
        - ``n_points``: number of points in the window (int)
        - ``error``: error message if failed (str or None)
    """
    txt_files = _list_measurement_files(device_dir)
    if not txt_files:
        return {"resistance": None, "file": None, "n_points": 0, "error": "No measurement files found"}

    first_file = txt_files[0]
    file_path = os.path.join(device_dir, first_file)

    try:
        data = np.loadtxt(file_path, skiprows=1, ndmin=2)
    except Exception as exc:
        return {"resistance": None, "file": first_file, "n_points": 0, "error": str(exc)}

    if data.ndim < 2 or data.shape[1] < 2:
        return {"resistance": None, "file": first_file, "n_points": 0, "error": "Not enough columns"}

    voltage = data[:, 0]
    current = data[:, 1]

    # Window: 0 <= V <= voltage_val
    mask = (voltage >= 0) & (voltage <= voltage_val)
    v_win = voltage[mask]
    i_win = current[mask]

    if len(v_win) == 0:
        return {"resistance": None, "file": first_file, "n_points": 0, "error": f"No data in 0–{voltage_val} V window"}

    # R = V / I, skip zero-current rows to avoid division by zero
    nonzero = i_win != 0
    if not np.any(nonzero):
        return {"resistance": None, "file": first_file, "n_points": 0, "error": "All current values are zero in window"}

    r_vals = v_win[nonzero] / i_win[nonzero]
    mean_r = float(np.mean(r_vals))
    n_pts = int(np.sum(nonzero))

    return {"resistance": mean_r, "file": first_file, "n_points": n_pts, "error": None}


def get_resistance_for_all_devices(
    sample_dir: str,
    device_ids: list[str],
    voltage_val: float = 0.1,
    log_fn: Callable[[str], None] = print,
) -> Dict[str, Dict]:
    """Return first-sweep resistance results for each device_id.

    Expects devices to live at {sample_dir}/{section}/{device_number}/.

    Returns
    -------
    dict mapping device_id -> result dict from :func:`get_first_sweep_resistance`.
    """
    results: Dict[str, Dict] = {}
    for device_id in device_ids:
        device_dir = _device_dir_from_id(sample_dir, device_id)
        if device_dir is None or not os.path.isdir(device_dir):
            results[device_id] = {
                "resistance": None, "file": None, "n_points": 0,
                "error": f"Device directory not found: {device_dir}"
            }
            continue
        results[device_id] = get_first_sweep_resistance(device_dir, voltage_val, log_fn)

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _list_measurement_files(device_dir: str) -> list[str]:
    """Return sorted list of eligible .txt files in *device_dir*."""
    if not os.path.isdir(device_dir):
        return []
    files = [
        f for f in os.listdir(device_dir)
        if f.endswith(".txt") and f not in _EXCLUDE_FILES
    ]
    files.sort()
    return files


def _device_dir_from_id(sample_dir: str, device_id: str) -> Optional[str]:
    """Reconstruct device directory path from device_id.

    device_id format: "{sample_name}_{section}_{number}"
    e.g. "D17-Stock-Gold-PMMA-Gold-s1_A_01" → {sample_dir}/A/01/
    """
    parts = device_id.rsplit("_", 2)
    if len(parts) < 3:
        return None
    section = parts[-2].strip()
    dev_num = parts[-1].strip()
    return os.path.join(sample_dir, section, dev_num)
