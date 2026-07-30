"""
Yield Source Resolver
=====================

Determines per-device yield with the following priority:

  1. Per-sample manual Excel  ({sample_name}.xlsx)
     Sheets named by section letter (A, B, …). Columns: "Device #", "Classification".
     Yield = 1 when Classification == "Memristive" (case-insensitive), else 0.
     When found this source is always used — JSON manifest is ignored.

  2. Cached JSON manifest  (sample_analysis/yield_analysis/yield_manifest.json)
     Written by a previous auto-run. Re-used when the manual Excel is absent.

  3. Auto-classify from device_tracking history JSONs
     yield = 1 if ANY measurement ever had device_type == "memristive", else 0.
     yield_promising = 1 if ever memristive (includes rectifying-character sub-type).
     Saves a new JSON manifest so future runs use priority 2.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd


_TRACKING_SUBDIRS = [
    os.path.join("sample_analysis", "analysis", "device_tracking"),
    os.path.join("sample_analysis", "device_tracking"),
    "device_tracking",
]

_MANIFEST_REL = os.path.join("sample_analysis", "yield_analysis", "yield_manifest.json")

_EXCLUDE_TXT = {"classification_log.txt", "classification_summary.txt", "log.txt"}

PROMISING_DEVICE_TYPES = frozenset({"memristive"})
FORMED_DEVICE_TYPES = frozenset({"memristive"})


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def resolve_yield(
    sample_dir: str,
    sample_name: str,
    device_ids: list[str],
    log_fn: Callable[[str], None] = print,
    manual_excel_dir: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Return per-device yield dict.

    Result format::

        {
            "Sample_A_01": {"yield": 1, "source": "manual_excel", "classification_type": "Memristive"},
            "Sample_A_02": {"yield": 0, "source": "device_tracking", "classification_type": "ohmic"},
            ...
        }

    Parameters
    ----------
    sample_dir:
        Root directory of the sample (contains section letter subdirs).
    sample_name:
        Name used for the manual Excel filename lookup ({sample_name}.xlsx).
    device_ids:
        List of device_id strings to resolve (e.g. ["MySample_A_01", …]).
    log_fn:
        Logging callback.
    manual_excel_dir:
        Extra directory to search for {sample_name}.xlsx (in addition to
        sample_dir and its parent).
    """
    # Priority 1 — manual Excel
    result, excel_path = _try_manual_excel(sample_dir, sample_name, device_ids, log_fn, manual_excel_dir)
    if result is not None:
        log_fn(f"[YIELD] Using manual Excel: {excel_path}")
        return result

    # Priority 2 — cached manifest
    manifest_path = os.path.join(sample_dir, _MANIFEST_REL)
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            devices = manifest.get("devices", {})
            if devices:
                log_fn(f"[YIELD] Using cached manifest: {manifest_path}")
                return devices
        except Exception as exc:
            log_fn(f"[YIELD] Could not load manifest ({exc}) — falling back to auto-classify")

    # Priority 3 — auto from device_tracking
    log_fn("[YIELD] Auto-classifying yield from device_tracking history…")
    result = _auto_classify(sample_dir, device_ids, log_fn)
    _save_manifest(sample_dir, sample_name, result)
    return result


def compute_sample_yield(per_device: Dict[str, Dict[str, Any]]) -> float:
    """Fraction of devices with yield == 1 (0.0 – 1.0). Strict: formed memristive only."""
    if not per_device:
        return 0.0
    total = len(per_device)
    positive = sum(1 for v in per_device.values() if v.get("yield", 0) == 1)
    return positive / total


def compute_sample_promising_yield(per_device: Dict[str, Dict[str, Any]]) -> float:
    """Fraction of devices with yield_promising == 1 (memristive, including rectifying sub-type)."""
    if not per_device:
        return 0.0
    total = len(per_device)
    positive = sum(1 for v in per_device.values() if v.get("yield_promising", v.get("yield", 0)) == 1)
    return positive / total


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _try_manual_excel(
    sample_dir: str,
    sample_name: str,
    device_ids: list[str],
    log_fn: Callable,
    extra_dir: Optional[str],
) -> Tuple[Optional[Dict], Optional[str]]:
    """Search for {sample_name}.xlsx; return (result_dict, path) or (None, None)."""
    search_dirs = [sample_dir, str(Path(sample_dir).parent)]
    if extra_dir:
        search_dirs.insert(0, extra_dir)

    for directory in search_dirs:
        candidate = os.path.join(directory, f"{sample_name}.xlsx")
        if os.path.exists(candidate):
            try:
                result = _read_manual_excel(candidate, device_ids, log_fn)
                return result, candidate
            except Exception as exc:
                log_fn(f"[YIELD] Manual Excel found but failed to read ({exc})")
    return None, None


def _read_manual_excel(
    excel_path: str,
    device_ids: list[str],
    log_fn: Callable,
) -> Dict[str, Dict[str, Any]]:
    """Read per-section sheets and return per-device yield dict."""
    xl = pd.ExcelFile(excel_path, engine="openpyxl")
    sheets: Dict[str, pd.DataFrame] = {}
    for sheet_name in xl.sheet_names:
        key = sheet_name.strip().upper()
        if len(key) == 1 and key.isalpha():
            df = xl.parse(sheet_name)
            df.columns = [str(c).strip() for c in df.columns]
            sheets[key] = df

    result: Dict[str, Dict[str, Any]] = {}
    for device_id in device_ids:
        section, dev_num = _parse_device_id(device_id)
        if section is None:
            result[device_id] = {"yield": 0, "source": "manual_excel", "classification_type": "unknown"}
            continue

        df = sheets.get(section)
        if df is None or "Device #" not in df.columns or "Classification" not in df.columns:
            log_fn(f"[YIELD] No sheet '{section}' in manual Excel — device {device_id} yield=0")
            result[device_id] = {"yield": 0, "source": "manual_excel", "classification_type": "not_found"}
            continue

        try:
            dev_int = int(dev_num[:2])
        except (ValueError, TypeError):
            dev_int = -1

        row = df[df["Device #"] == dev_int]
        if row.empty:
            result[device_id] = {"yield": 0, "source": "manual_excel", "classification_type": "not_found"}
        else:
            classification = str(row.iloc[0]["Classification"]).strip()
            cls_lower = classification.lower()
            yield_val = 1 if cls_lower == "memristive" else 0
            yield_promising = 1 if cls_lower in PROMISING_DEVICE_TYPES else yield_val
            result[device_id] = {
                "yield": yield_val,
                "yield_promising": yield_promising,
                "yield_tier": "formed" if yield_val else ("forming" if yield_promising else "none"),
                "source": "manual_excel",
                "classification_type": classification,
            }
    return result


def _auto_classify(
    sample_dir: str,
    device_ids: list[str],
    log_fn: Callable,
) -> Dict[str, Dict[str, Any]]:
    """Derive yield from device_tracking history JSONs."""
    tracking_dir = _find_tracking_dir(sample_dir)
    result: Dict[str, Dict[str, Any]] = {}

    for device_id in device_ids:
        if tracking_dir:
            history_file = os.path.join(tracking_dir, f"{device_id}_history.json")
        else:
            history_file = None

        if history_file and os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                all_measurements = history.get("all_measurements", [])
                if not all_measurements:
                    all_measurements = history.get("measurements", [])
                classification_type = "unknown"
                ever_memristive = False
                ever_promising = False
                ever_formed_rectifying = False
                yield_tier = "none"
                for m in all_measurements:
                    clf = m.get("classification", {})
                    dt = clf.get("device_type", "")
                    stage = clf.get("forming_stage", "")
                    if isinstance(dt, str):
                        dt_lower = dt.lower()
                        if dt_lower in FORMED_DEVICE_TYPES:
                            ever_memristive = True
                            classification_type = dt
                        if dt_lower in PROMISING_DEVICE_TYPES:
                            ever_promising = True
                            if classification_type == "unknown":
                                classification_type = dt
                        if stage == "formed_rectifying" or (
                            clf.get("features", {}).get("rectifying_character")
                            and clf.get("features", {}).get("rectifying_tier") == "formed"
                        ):
                            ever_formed_rectifying = True
                    if dt and classification_type == "unknown":
                        classification_type = dt
                if ever_memristive:
                    yield_tier = "formed"
                elif ever_formed_rectifying:
                    yield_tier = "formed_rectifying"
                elif ever_promising:
                    yield_tier = "forming"
                result[device_id] = {
                    "yield": 1 if (ever_memristive or ever_formed_rectifying) else 0,
                    "yield_promising": 1 if ever_promising else 0,
                    "yield_tier": yield_tier,
                    "source": "device_tracking",
                    "classification_type": classification_type,
                }
            except Exception as exc:
                log_fn(f"[YIELD] Could not read history for {device_id}: {exc}")
                result[device_id] = {"yield": 0, "source": "device_tracking", "classification_type": "error"}
        else:
            result[device_id] = {"yield": 0, "source": "no_tracking", "classification_type": "unknown"}

    return result


def _save_manifest(sample_dir: str, sample_name: str, devices: Dict[str, Dict[str, Any]]) -> None:
    """Persist auto-classified yield as a JSON manifest."""
    try:
        manifest_path = os.path.join(sample_dir, _MANIFEST_REL)
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        sample_yield = compute_sample_yield(devices)
        sample_promising_yield = compute_sample_promising_yield(devices)
        manifest = {
            "sample_name": sample_name,
            "generated": datetime.now(timezone.utc).isoformat(),
            "yield_source": "device_tracking",
            "sample_yield": sample_yield,
            "sample_promising_yield": sample_promising_yield,
            "devices": devices,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as exc:
        print(f"[YIELD] Could not save manifest: {exc}")


def find_tracking_dir(sample_dir: str) -> Optional[str]:
    """Return first existing device_tracking directory under a sample folder."""
    for subdir in _TRACKING_SUBDIRS:
        path = os.path.join(sample_dir, subdir)
        if os.path.isdir(path):
            return path
    return None


# Backward-compatible alias
_find_tracking_dir = find_tracking_dir


def summarize_device_from_history(
    history: Optional[dict],
    *,
    min_sweeps_for_confident: int = 2,
    mem_score_threshold: float = 60.0,
) -> dict:
    """Summarize one device for Sample GUI overlay (best score, min sweeps rule).

    Returns dict with: measured, sweep_count, display_status, best_mem_score,
    latest_type, promising.
    """
    empty = {
        "measured": False,
        "sweep_count": 0,
        "display_status": "unmeasured",
        "best_mem_score": None,
        "latest_type": "unknown",
        "promising": False,
    }
    if not history:
        return empty

    measurements = history.get("all_measurements") or history.get("measurements") or []
    sweep_count = len(measurements)
    if sweep_count == 0:
        return empty

    scores: list[float] = []
    latest_type = "unknown"
    for m in measurements:
        clf = m.get("classification") or {}
        dt = clf.get("device_type")
        if isinstance(dt, str) and dt.strip():
            latest_type = dt.strip().lower()
        score = clf.get("memristivity_score")
        if score is not None:
            try:
                scores.append(float(score))
            except (TypeError, ValueError):
                pass

    best_mem_score = max(scores) if scores else None

    if sweep_count == 1:
        display_status = "pending"
    elif (
        sweep_count >= min_sweeps_for_confident
        and best_mem_score is not None
        and best_mem_score >= mem_score_threshold
    ):
        display_status = "memristive"
    else:
        display_status = _normalize_display_type(latest_type)

    promising = False
    if display_status != "memristive":
        if latest_type in ("rectifying", "memcapacitive"):
            promising = True
        elif best_mem_score is not None and 40 <= best_mem_score < mem_score_threshold:
            promising = True

    return {
        "measured": True,
        "sweep_count": sweep_count,
        "display_status": display_status,
        "best_mem_score": best_mem_score,
        "latest_type": latest_type,
        "promising": promising,
    }


def summarize_sample_devices(device_summaries: Dict[str, dict], total_devices: int) -> dict:
    """Aggregate per-device summaries for the map legend strip."""
    measured = sum(1 for d in device_summaries.values() if d.get("measured"))
    memristive = sum(1 for d in device_summaries.values() if d.get("display_status") == "memristive")
    pending = sum(1 for d in device_summaries.values() if d.get("display_status") == "pending")
    promising = sum(1 for d in device_summaries.values() if d.get("promising"))
    return {
        "total_devices": total_devices,
        "measured_count": measured,
        "memristive_count": memristive,
        "pending_count": pending,
        "promising_count": promising,
    }


def _normalize_display_type(device_type: str) -> str:
    dt = (device_type or "unknown").lower().strip()
    if dt in ("memristive", "memcapacitive"):
        return "memristive"
    if dt in ("non_conductive", "non-conductive", "nonconductive"):
        return "non_conductive"
    if dt in ("ohmic", "rectifying", "uncertain", "capacitive", "conductive"):
        return dt
    return "uncertain"


def _parse_device_id(device_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract (section_letter, device_number) from a device_id string.

    Handles IDs like:
      "MySample_A_01"          -> ("A", "01")
      "My-Long-Sample_B_03"    -> ("B", "03")
    """
    parts = device_id.rsplit("_", 2)
    if len(parts) >= 2:
        section = parts[-2].strip().upper()
        dev_num = parts[-1].strip()
        if len(section) >= 1 and section[0].isalpha():
            return section[0], dev_num
    return None, None
