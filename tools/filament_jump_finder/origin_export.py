"""
Origin-ready tab-delimited exports and session JSON for filament jump review.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .core import (
    get_first_and_all,
    histogram_bins,
    compute_yield_summary,
    origin_export_root,
)

ORIGIN_DIR_NAME = "origin data"
REVIEW_JSON_NAME = "filament_jumps_review.json"
SESSION_VERSION = 2

JUMP_COLUMNS = (
    "SourceFolder",
    "Section",
    "Device",
    "Filename",
    "Voltage_V",
    "AbsVoltage_V",
    "Ratio",
    "I_before_A",
    "I_after_A",
)

HIST_COLUMNS = ("BinCenter_V", "Count")

DEVICE_YIELD_COLUMNS = (
    "SourceFolder",
    "Section",
    "Device",
    "HasJump",
    "Classification",
    "IsMemristive",
    "WorkedMemristive",
    "NDR_index_max",
    "MemristiveSweepCount",
)

YIELD_COUNT_COLUMNS = ("SourceFolder", "Category", "Count")

NDR_COMPARE_COLUMNS = (
    "Scope",
    "SourceFolder",
    "Group",
    "N_devices",
    "N_with_NDR",
    "Mean_NDR",
    "Median_NDR",
    "Max_NDR",
    "N_soft_NDR",
    "N_strong_NDR",
)

BEST_PAIR_COLUMNS = (
    "SourceFolder",
    "JumpGroup",
    "Section",
    "Device",
    "Classification",
    "NDR_index_max",
    "MemristiveSweepCount",
    "BestSweepFile",
)


def sanitize_export_name(name: str) -> str:
    """Make a filesystem-safe export / session name."""
    name = (name or "").strip()
    if not name:
        return ""
    # Replace path separators and illegal Windows chars
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:120]


def origin_data_dir(root_path: Path, export_name: Optional[str] = None) -> Path:
    """
    Return ``<root>/origin data`` or ``<root>/origin data/<export_name>``.
    """
    out = Path(root_path) / ORIGIN_DIR_NAME
    clean = sanitize_export_name(export_name or "")
    if clean:
        out = out / clean
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_tsv(path: Path, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(headers)]
    for row in rows:
        lines.append("\t".join("" if v is None else str(v) for v in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _jump_row(j: Dict[str, Any]) -> Tuple[Any, ...]:
    v = j.get("voltage", j.get("voltage_mid"))
    try:
        v_f = float(v) if v is not None else None
    except (TypeError, ValueError):
        v_f = None
    return (
        j.get("source_folder", ""),
        j.get("section", ""),
        j.get("device_num", ""),
        j.get("filename", ""),
        f"{v_f:.6g}" if v_f is not None else "",
        f"{abs(v_f):.6g}" if v_f is not None else "",
        f"{float(j.get('ratio', 0)):.6g}",
        f"{float(j.get('i_before', 0)):.6e}",
        f"{float(j.get('i_after', 0)):.6e}",
    )


def export_origin_files(
    out_root: Path,
    filtered_jumps: List[Dict[str, Any]],
    decisions: Dict[str, bool],
    filter_state: Optional[Dict[str, Any]] = None,
    excluded_files_from_first: Optional[set] = None,
    bin_width: float = 0.2,
    folder_paths: Optional[Sequence[Path]] = None,
    device_registry: Optional[List[Dict[str, Any]]] = None,
    export_name: Optional[str] = None,
) -> Dict[str, Path]:
    """
    Write Origin TXT files and a review JSON into ``<out_root>/origin data[/name]/``.

    Also writes yield tables when device_registry is provided.
    """
    out_dir = origin_data_dir(out_root, export_name=export_name)
    first_list, all_list = get_first_and_all(
        filtered_jumps,
        excluded_files_from_first=excluded_files_from_first,
        accepted_only=True,
    )

    paths: Dict[str, Path] = {}
    paths["all"] = _write_tsv(
        out_dir / "filament_jumps_all.txt",
        JUMP_COLUMNS,
        [_jump_row(j) for j in all_list],
    )
    paths["first"] = _write_tsv(
        out_dir / "filament_jumps_first.txt",
        JUMP_COLUMNS,
        [_jump_row(j) for j in first_list],
    )

    voltages = []
    for j in all_list:
        v = j.get("voltage", j.get("voltage_mid"))
        if v is not None:
            voltages.append(float(v))

    centers_s, counts_s = histogram_bins(voltages, bin_width=bin_width, absolute=False)
    paths["hist_signed"] = _write_tsv(
        out_dir / "filament_jump_histogram_signed.txt",
        HIST_COLUMNS,
        [(f"{c:.6g}", int(n)) for c, n in zip(centers_s, counts_s)],
    )
    centers_a, counts_a = histogram_bins(voltages, bin_width=bin_width, absolute=True)
    paths["hist_absolute"] = _write_tsv(
        out_dir / "filament_jump_histogram_absolute.txt",
        HIST_COLUMNS,
        [(f"{c:.6g}", int(n)) for c, n in zip(centers_a, counts_a)],
    )

    if device_registry is not None:
        yield_paths = export_yield_files(out_dir, device_registry, filtered_jumps)
        paths.update(yield_paths)

    review = {
        "version": SESSION_VERSION,
        "export_name": sanitize_export_name(export_name or "") or None,
        "folder_paths": [str(Path(p).resolve()) for p in (folder_paths or [out_root])],
        "sample_path": str(Path(out_root).resolve()),
        "decisions": {k: bool(v) for k, v in decisions.items()},
        "filter_state": filter_state or {},
        "excluded_files_from_first": [
            list(item) for item in (excluded_files_from_first or set())
        ],
    }
    review_path = out_dir / REVIEW_JSON_NAME
    review_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
    paths["review"] = review_path
    return paths


def export_yield_files(
    out_dir: Path,
    device_registry: List[Dict[str, Any]],
    filtered_jumps: List[Dict[str, Any]],
) -> Dict[str, Path]:
    """Write yield, NDR comparison, and best-memristive-pair Origin TXT files."""
    summary = compute_yield_summary(device_registry, filtered_jumps)
    paths: Dict[str, Path] = {}

    device_rows = []
    for r in summary["device_rows"]:
        ndr = r.get("ndr_index_max")
        device_rows.append((
            r["source_folder"],
            r["section"],
            r["device_num"],
            1 if r["has_jump"] else 0,
            r["classification"],
            1 if r["is_memristive"] else 0,
            1 if r.get("worked_memristive", r["is_memristive"]) else 0,
            f"{ndr:.6g}" if ndr is not None else "",
            r.get("memristive_sweep_count", ""),
        ))
    paths["device_yield"] = _write_tsv(
        Path(out_dir) / "filament_device_yield.txt",
        DEVICE_YIELD_COLUMNS,
        device_rows,
    )

    count_rows = []
    for folder, counts in sorted(summary["counts_by_folder"].items()):
        for cat in ("WithJump", "NoJump", "MemWithJump", "MemNoJump"):
            count_rows.append((folder, cat, counts.get(cat, 0)))
    combined = summary["combined"]
    for cat in ("WithJump", "NoJump", "MemWithJump", "MemNoJump"):
        count_rows.append(("Combined", cat, combined.get(cat, 0)))
    paths["yield_counts"] = _write_tsv(
        Path(out_dir) / "filament_yield_counts.txt",
        YIELD_COUNT_COLUMNS,
        count_rows,
    )

    # NDR comparison table
    ndr_rows = []
    ndr_stats = summary.get("ndr_stats") or {}

    def _ndr_row(scope: str, folder: str, group_name: str, g: Dict[str, Any]):
        mean = g.get("mean_ndr")
        med = g.get("median_ndr")
        mx = g.get("max_ndr")
        return (
            scope,
            folder,
            group_name,
            g.get("n", 0),
            g.get("n_with_ndr", 0),
            f"{mean:.6g}" if mean is not None else "",
            f"{med:.6g}" if med is not None else "",
            f"{mx:.6g}" if mx is not None else "",
            g.get("n_soft_ndr", 0),
            g.get("n_strong_ndr", 0),
        )

    for scope_key, scope_label in (("all", "All"), ("memristive", "Memristive")):
        block = ndr_stats.get(scope_key) or {}
        ndr_rows.append(_ndr_row(scope_label, "Combined", "WithJump", block.get("with_jump") or {}))
        ndr_rows.append(_ndr_row(scope_label, "Combined", "NoJump", block.get("no_jump") or {}))
    for folder, block in sorted((ndr_stats.get("by_folder") or {}).items()):
        for scope_key, scope_label in (("all", "All"), ("memristive", "Memristive")):
            g = block.get(scope_key) or {}
            ndr_rows.append(_ndr_row(scope_label, folder, "WithJump", g.get("with_jump") or {}))
            ndr_rows.append(_ndr_row(scope_label, folder, "NoJump", g.get("no_jump") or {}))
    paths["ndr_compare"] = _write_tsv(
        Path(out_dir) / "filament_ndr_compare.txt",
        NDR_COMPARE_COLUMNS,
        ndr_rows,
    )

    # Best memristive pairs used for IV overlay
    pair_rows = []
    for folder, pair in sorted((summary.get("best_memristive_pairs") or {}).items()):
        for group_name, key in (("WithJump", "with_jump"), ("NoJump", "no_jump")):
            r = pair.get(key)
            if not r:
                continue
            sweep = r.get("best_sweep") or {}
            fname = sweep.get("filename", "") if isinstance(sweep, dict) else ""
            ndr = r.get("ndr_index_max")
            pair_rows.append((
                folder,
                group_name,
                r.get("section", ""),
                r.get("device_num", ""),
                r.get("classification", ""),
                f"{ndr:.6g}" if ndr is not None else "",
                r.get("memristive_sweep_count", ""),
                fname,
            ))
    paths["best_pairs"] = _write_tsv(
        Path(out_dir) / "filament_best_memristive_pairs.txt",
        BEST_PAIR_COLUMNS,
        pair_rows,
    )
    return paths


def save_session(
    path: Path,
    folder_paths: Sequence[Path],
    decisions: Dict[str, bool],
    filter_state: Dict[str, Any],
    excluded_files_from_first: Optional[set] = None,
    session_name: Optional[str] = None,
) -> Path:
    """Write a named session JSON the user can reload later."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = sanitize_export_name(session_name or path.stem)
    payload = {
        "version": SESSION_VERSION,
        "session_name": clean or None,
        "folder_paths": [str(Path(p).resolve()) for p in folder_paths],
        "decisions": {k: bool(v) for k, v in decisions.items()},
        "filter_state": filter_state or {},
        "excluded_files_from_first": [
            list(item) for item in (excluded_files_from_first or set())
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_session(path: Path) -> Optional[Dict[str, Any]]:
    """Load a session JSON. Returns None on failure."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data


def load_review_json(sample_path: Path) -> Optional[Dict[str, Any]]:
    """Load previous review decisions if present under origin data."""
    path = Path(sample_path) / ORIGIN_DIR_NAME / REVIEW_JSON_NAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data


def apply_review_to_decisions(review: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    """Extract decision map from a loaded review/session JSON."""
    if not review:
        return {}
    raw = review.get("decisions") or {}
    return {str(k): bool(v) for k, v in raw.items()}


def apply_review_excluded_files(review: Optional[Dict[str, Any]]) -> set:
    """Extract excluded-from-first file keys from review/session JSON."""
    if not review:
        return set()
    out = set()
    for item in review.get("excluded_files_from_first") or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            if len(item) >= 4:
                sf, section, device_num, filename = item[0], item[1], item[2], item[3]
                try:
                    device_num = int(device_num)
                except (TypeError, ValueError):
                    pass
                out.add((sf, section, device_num, filename))
            else:
                section, device_num, filename = item[0], item[1], item[2]
                try:
                    device_num = int(device_num)
                except (TypeError, ValueError):
                    pass
                out.add((section, device_num, filename))
    return out


def session_folder_paths(session: Optional[Dict[str, Any]]) -> List[Path]:
    """Folder paths from a session/review dict."""
    if not session:
        return []
    paths = session.get("folder_paths") or []
    if not paths and session.get("sample_path"):
        paths = [session["sample_path"]]
    return [Path(p) for p in paths]


# Re-export
__all__ = [
    "ORIGIN_DIR_NAME",
    "REVIEW_JSON_NAME",
    "SESSION_VERSION",
    "sanitize_export_name",
    "origin_data_dir",
    "export_origin_files",
    "export_yield_files",
    "save_session",
    "load_session",
    "load_review_json",
    "apply_review_to_decisions",
    "apply_review_excluded_files",
    "session_folder_paths",
    "origin_export_root",
]
