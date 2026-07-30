"""Load/save batch classification results and user review labels."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from paths import DEFAULT_DATASET, MERGE_TAGS, dataset_paths

TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = dataset_paths(DEFAULT_DATASET)["data_dir"]
DEFAULT_RESULTS_JSON = dataset_paths(DEFAULT_DATASET)["results_json"]
DEFAULT_RESULTS_CSV = dataset_paths(DEFAULT_DATASET)["results_csv"]
DEFAULT_SUMMARY_TXT = dataset_paths(DEFAULT_DATASET)["summary_txt"]
DEFAULT_LABELS_JSON = dataset_paths(DEFAULT_DATASET)["labels_json"]
DEFAULT_CORRECTIONS_JSON = dataset_paths(DEFAULT_DATASET)["corrections_json"]
DEFAULT_CORRECTIONS_CSV = dataset_paths(DEFAULT_DATASET)["corrections_csv"]
DEFAULT_DEVICE_YIELD_JSON = dataset_paths(DEFAULT_DATASET)["device_yield_json"]

CORRECTIONS_SCHEMA_VERSION = 1

FILENAME_RE = re.compile(r"^(D\d+)-([A-Za-z])-(\d+)-(.+)$", re.IGNORECASE)
# Optional material prefix from nested sources: WS2-D15-G-1-...
MATERIAL_STRIP_RE = re.compile(r"^.*?-(D\d+-)", re.IGNORECASE)  # kept for reference; use _canonical_stem

PROMISING_DEVICE_TYPES = frozenset({"memristive"})
FORMED_DEVICE_TYPES = frozenset({"memristive"})
FORMED_RECTIFYING_STAGES = frozenset({"formed_rectifying"})

VALID_USER_LABELS = (
    "memristive",
    "capacitive",
    "conductive",
    "ohmic",
    "non_conductive",
    "uncertain",
    "skip",
)


def infer_origin_dataset(name: str) -> str:
    """Infer source dataset from merge tag in combined filenames."""
    stem = Path(name).stem.lower()
    for dataset_name, tag in MERGE_TAGS.items():
        if stem.startswith(f"{tag.lower()}-"):
            return dataset_name
    return ""


def _canonical_stem(name: str) -> tuple[str, str]:
    """Return (Dxx-... stem, optional material prefix). Strips merge tags (data1-, qd-, stock-)."""
    full = Path(name).stem
    for tag in MERGE_TAGS.values():
        prefix = f"{tag}-"
        if full.lower().startswith(prefix):
            full = full[len(prefix) :]
            break
    m = re.search(r"(D\d+-)", full, re.IGNORECASE)
    if not m:
        return full, ""
    idx = m.start()
    material = full[:idx].rstrip("-") if idx > 0 else ""
    return full[idx:], material


def build_device_key(sample_id: str, section: str, device_number: str) -> str:
    return f"{sample_id}-{section}-{device_number}"


def build_device_group_key(
    sample_id: str,
    section: str,
    device_number: str,
    *,
    origin_dataset: str = "",
    material: str = "",
) -> str:
    """Stable grouping key that avoids collisions across materials/datasets."""
    base_key = build_device_key(sample_id, section, device_number)
    parts = []
    if origin_dataset:
        parts.append(origin_dataset)
    if material:
        parts.append(material)
    parts.append(base_key)
    return " | ".join(parts)


def device_group_key_from_filename(name: str) -> str:
    meta = parse_consolidated_filename(name)
    return build_device_group_key(
        meta["sample_id"],
        meta["section"],
        meta["device_number"],
        origin_dataset=infer_origin_dataset(name),
        material=meta.get("material", ""),
    )


def parse_consolidated_filename(name: str) -> Dict[str, str]:
    """Parse Dxx-Section-Device-rest.txt into components."""
    stem, material = _canonical_stem(name)
    m = FILENAME_RE.match(stem)
    if not m:
        return {
            "sample_id": "",
            "section": "",
            "device_number": "",
            "sweep_name": stem,
            "sweep_index": "0",
            "material": material,
        }
    return {
        "sample_id": m.group(1).upper(),
        "section": m.group(2).upper(),
        "device_number": m.group(2 + 1),
        "sweep_name": m.group(4),
        "sweep_index": str(parse_sweep_index(name)),
        "material": material,
    }


def parse_sweep_index(name: str) -> int:
    """
    Numeric sweep sequence from consolidated filename.

    D108-B-4-8-FS-2.2v-... -> 8
    WS2-D15-G-1-9-FS-... -> 9
    """
    stem = _canonical_stem(name)[0]
    m = FILENAME_RE.match(stem)
    if not m:
        return 0
    rest = m.group(4)
    token = rest.split("-", 1)[0]
    try:
        return int(token)
    except ValueError:
        return 0


# Patterns to extract sweep parameters from filenames
# e.g. "8-FS-2.2v-0.05sv-0.05sd-Py-St_v2-" → type=FS, voltage=2.2
_SWEEP_TYPE_RE = re.compile(r"-(FS|RS|Endurance|Retention|Pulse[^-]*)-", re.IGNORECASE)
_SWEEP_VOLTAGE_RE = re.compile(r"-(\d+(?:\.\d+)?)v-", re.IGNORECASE)


def parse_sweep_params(name: str) -> Dict[str, str]:
    """
    Extract sweep type and voltage from a consolidated filename.

    Returns a dict with keys 'sweep_type' and 'sweep_voltage_v'.
    Both default to '' if not parseable.

    Examples:
        D108-B-4-8-FS-2.2v-0.05sv-...  → {'sweep_type': 'FS', 'sweep_voltage_v': '2.2'}
        D94-A-1-3-RS-1.5v-...           → {'sweep_type': 'RS', 'sweep_voltage_v': '1.5'}
    """
    stem = Path(name).stem
    sweep_type = ""
    sweep_voltage = ""

    m = _SWEEP_TYPE_RE.search(stem)
    if m:
        sweep_type = m.group(1).upper()

    m = _SWEEP_VOLTAGE_RE.search(stem)
    if m:
        sweep_voltage = m.group(1)

    return {"sweep_type": sweep_type, "sweep_voltage_v": sweep_voltage}


def record_sweep_sort_key(rec: Dict[str, Any]) -> tuple:
    """Sort key: device, numeric sweep index, then filename."""
    row = rec.get("row", {}) or {}
    fn = rec.get("filename") or row.get("filename", "")
    group_key = row.get("device_group_key") or device_group_key_from_filename(fn)
    return (group_key, parse_sweep_index(fn), fn)


def sort_records_by_device_sweep(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(records, key=record_sweep_sort_key)


def extract_summary_row(file_path: Path, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten analysis dict to a CSV-friendly row."""
    meta = parse_consolidated_filename(file_path.name)
    sweep_params = parse_sweep_params(file_path.name)
    clf = analysis.get("classification", {}) or {}
    feats = clf.get("features", {}) or {}
    res = analysis.get("resistance_metrics", {}) or {}
    breakdown = clf.get("breakdown", {}) or {}

    device_type = clf.get("device_type") or "unknown"
    confidence = float(clf.get("confidence") or 0)
    mem_score = clf.get("memristivity_score")
    if mem_score is None:
        mem_score = feats.get("memristivity_score")
    compliance_limited = bool(feats.get("compliance_limited", False))
    warnings = clf.get("warnings") or []
    has_override = any("OVERRIDE" in str(w) for w in warnings)

    origin = infer_origin_dataset(file_path.name)
    base_device_key = build_device_key(meta["sample_id"], meta["section"], meta["device_number"])
    device_group_key = build_device_group_key(
        meta["sample_id"],
        meta["section"],
        meta["device_number"],
        origin_dataset=origin,
        material=meta.get("material", ""),
    )

    return {
        "filename": file_path.name,
        "file_path": str(file_path),
        "sample_id": meta["sample_id"],
        "section": meta["section"],
        "device_number": meta["device_number"],
        "device_key": base_device_key,
        "device_group_key": device_group_key,
        "material": meta.get("material", ""),
        "sweep_index": meta.get("sweep_index", "0"),
        "sweep_type": sweep_params["sweep_type"],
        "sweep_voltage_v": sweep_params["sweep_voltage_v"],
        "origin_dataset": origin,
        "predicted_type": device_type,
        "confidence": round(confidence, 4),
        "confidence_pct": round(confidence * 100, 1),
        "memristivity_score": mem_score if mem_score is not None else "",
        "forming_stage": clf.get("forming_stage") or feats.get("forming_stage") or "",
        "rectifying_tier": feats.get("rectifying_tier") or clf.get("explanation", {}).get("rectifying_tier", ""),
        "yield_bucket": clf.get("yield_bucket") or feats.get("yield_bucket") or "",
        "conduction_mechanism": clf.get("conduction_mechanism") or "",
        "has_hysteresis": bool(feats.get("has_hysteresis", False)),
        "pinched_hysteresis": bool(feats.get("pinched_hysteresis", False)),
        "double_zero_crossing": bool(feats.get("double_zero_crossing", False)),
        "switching_behavior": bool(feats.get("switching_behavior", False)),
        "is_noisy": bool(feats.get("is_noisy", False)),
        "compliance_limited": compliance_limited,
        "rectifying_character": bool(feats.get("rectifying_character", False)),
        "weak_rectifying": bool(feats.get("weak_rectifying", False)),
        "noise_reason": feats.get("noise_reason") or "",
        "ron_mean": res.get("ron_mean", ""),
        "roff_mean": res.get("roff_mean", ""),
        "switching_ratio": res.get("switching_ratio_mean", res.get("switching_ratio", "")),
        "score_memristive": breakdown.get("memristive", ""),
        "score_capacitive": breakdown.get("capacitive", ""),
        "score_conductive": breakdown.get("conductive", ""),
        "score_ohmic": breakdown.get("ohmic", ""),
        "review_priority": _review_priority(
            device_type,
            confidence,
            mem_score,
            bool(feats.get("is_noisy", False)),
            compliance_limited=compliance_limited,
            has_override=has_override,
        ),
    }


def _review_priority(
    device_type: str,
    confidence: float,
    mem_score: Optional[float],
    is_noisy: bool = False,
    compliance_limited: bool = False,
    has_override: bool = False,
) -> str:
    """
    Assign a manual-review priority for the sweep.

    high   → classifier is uncertain, contradicted itself, or compliance was hit
    medium → moderate confidence / borderline forming / rectifying needs verification
    low    → high-confidence, unambiguous classification
    """
    # Compliance-saturated sweeps: scoring was penalised, result uncertain
    if compliance_limited:
        return "high"
    # Any post-classification override was applied (contradiction resolved automatically)
    if has_override:
        return "high"
    if device_type == "non_conductive" or is_noisy:
        return "low"
    if device_type == "uncertain" or confidence < 0.4:
        return "high"
    if mem_score is not None and 40 <= mem_score <= 65:
        return "medium"
    if confidence < 0.55:
        return "medium"
    return "low"


def _json_safe(obj: Any) -> Any:
    """Convert numpy scalars and nested structures for JSON."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def save_results(
    rows: List[Dict[str, Any]],
    records: List[Dict[str, Any]],
    *,
    json_path: Path = DEFAULT_RESULTS_JSON,
    csv_path: Path = DEFAULT_RESULTS_CSV,
    summary_path: Path = DEFAULT_SUMMARY_TXT,
) -> None:
    payload = _json_safe({
        "generated_at": datetime.now().isoformat(),
        "count": len(records),
        "records": records,
    })
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    summary_path.write_text(build_summary_text(rows), encoding="utf-8")


def build_summary_text(rows: List[Dict[str, Any]]) -> str:
    from collections import Counter, defaultdict

    lines = ["CLASSIFICATION BATCH SUMMARY", "=" * 60, f"Total files: {len(rows)}", ""]

    type_counts = Counter(r["predicted_type"] for r in rows)
    lines.append("Predicted type distribution:")
    for dtype, count in type_counts.most_common():
        pct = 100 * count / len(rows) if rows else 0
        lines.append(f"  {dtype:16s} {count:5d}  ({pct:.1f}%)")
    lines.append("")

    priority_counts = Counter(r["review_priority"] for r in rows)
    lines.append("Review priority (for manual checking):")
    for pri in ("high", "medium", "low"):
        lines.append(f"  {pri:8s} {priority_counts.get(pri, 0):5d}")
    lines.append("")

    low_conf = [r for r in rows if r["confidence"] < 0.4]
    lines.append(f"Low confidence (<40%): {len(low_conf)}")
    uncertain = [r for r in rows if r["predicted_type"] == "uncertain"]
    lines.append(f"Uncertain type: {len(uncertain)}")
    compliance_lim = [r for r in rows if r.get("compliance_limited")]
    if compliance_lim:
        lines.append(f"Compliance-limited sweeps: {len(compliance_lim)} (review_priority=high)")
    lines.append("")

    lines.append("Average confidence by predicted type:")
    by_type: Dict[str, List[float]] = {}
    for r in rows:
        by_type.setdefault(r["predicted_type"], []).append(float(r["confidence"]))
    for dtype in sorted(by_type):
        vals = by_type[dtype]
        avg = sum(vals) / len(vals) if vals else 0
        lines.append(f"  {dtype:16s} avg confidence {avg*100:.1f}%  (n={len(vals)})")
    lines.append("")

    # --- Per origin-dataset breakdown ---
    origins = set(r.get("origin_dataset", "") for r in rows if r.get("origin_dataset"))
    if len(origins) > 1:
        lines.append("Per origin-dataset breakdown:")
        by_origin: Dict[str, Counter] = defaultdict(Counter)
        for r in rows:
            by_origin[r.get("origin_dataset", "unknown")][r["predicted_type"]] += 1
        for origin in sorted(by_origin):
            total_o = sum(by_origin[origin].values())
            mem_n = by_origin[origin].get("memristive", 0)
            lines.append(
                f"  {origin:<20} {total_o:5d} sweeps  "
                f"memristive={mem_n} ({100*mem_n/total_o:.0f}%)"
            )
        lines.append("")

    # --- Per sweep-type breakdown (FS / RS etc.) ---
    sweep_types = [r.get("sweep_type", "") for r in rows if r.get("sweep_type")]
    if sweep_types:
        st_counts = Counter(sweep_types)
        lines.append("Per sweep-type breakdown:")
        for st, n in st_counts.most_common():
            st_rows = [r for r in rows if r.get("sweep_type") == st]
            mem_n = sum(1 for r in st_rows if r["predicted_type"] == "memristive")
            unc_n = sum(1 for r in st_rows if r["predicted_type"] == "uncertain")
            lines.append(
                f"  {st:<8} {n:5d} sweeps  "
                f"memristive={mem_n} ({100*mem_n/n:.0f}%)  "
                f"uncertain={unc_n} ({100*unc_n/n:.0f}%)"
            )
        lines.append("")

    # --- Sweep voltage breakdown for uncertain/low-confidence ---
    unc_voltages = [
        r.get("sweep_voltage_v", "")
        for r in rows
        if r["predicted_type"] in ("uncertain",) and r.get("sweep_voltage_v")
    ]
    if unc_voltages:
        v_counts = Counter(unc_voltages)
        lines.append("Uncertain sweeps by sweep voltage (top 5):")
        for v, n in v_counts.most_common(5):
            lines.append(f"  {v}V: {n}")
        lines.append("  (Low voltages may need a lower noise threshold.)")
        lines.append("")

    lines.append("Likely strong areas (high confidence, clear type):")
    strong = [r for r in rows if r["confidence"] >= 0.7 and r["predicted_type"] not in ("uncertain",)]
    strong_by = Counter(r["predicted_type"] for r in strong)
    for dtype, count in strong_by.most_common():
        lines.append(f"  {dtype}: {count} sweeps at >=70% confidence")
    lines.append("")

    lines.append("Likely weak areas (start manual review here):")
    lines.append("  1. 'uncertain' sweeps (ambiguous physics, not just noise)")
    lines.append("  2. closed nonlinear curves vs true memristive loops")
    lines.append("  3. capacitive vs memristive")
    lines.append("  4. ohmic with artifact hysteresis")
    lines.append("  5. compliance-limited sweeps (hardware current ceiling hit)")
    lines.append("")
    nc = type_counts.get("non_conductive", 0)
    if nc:
        lines.append(f"Non-conductive (open/noise, auto-detected): {nc} — low review priority")
    lines.append("")
    lines.append("Device-level promising yield: see device_yield_summary.json")
    lines.append("Corrections analysis:  python tools/data_consolidation/analyze_corrections.py")
    lines.append("Open review GUI:       python tools/data_consolidation/launch_review.py")
    return "\n".join(lines)


def build_device_yield_summaries(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate per-device forming stage and yield buckets from batch records.

    Improvements over the original logic:
    - Uses DeviceSweepAggregator for trajectory analysis and smarter yield tiers
      (requires 2+ memristive sweeps OR a single high-score sweep for 'formed')
    - Adds trajectory, memristivity_trend, peak_forming_stage, best_memristivity_score fields
    - Adds per-material memristive sweep counts for cross-dataset comparison
    """
    from collections import Counter, defaultdict

    # Import here to avoid circular imports at module load time
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _root = _Path(__file__).resolve().parents[2]
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        from analysis.aggregators.device_analyzer import DeviceSweepAggregator
        _has_aggregator = True
    except ImportError:
        _has_aggregator = False

    devices: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "device_key": "",
            "sample_id": "",
            "sweep_count": 0,
            "sweeps": [],
            "type_counts": Counter(),
        }
    )

    for rec in records:
        row = rec.get("row", {})
        fn = rec.get("filename", row.get("filename", ""))
        key = row.get("device_group_key") or device_group_key_from_filename(fn)
        if not key:
            continue
        entry = devices[key]
        entry["device_key"] = row.get("device_key", "")
        entry["device_group_key"] = key
        entry["sample_id"] = row.get("sample_id", "")
        entry["material"] = row.get("material", "")
        entry["origin_dataset"] = row.get("origin_dataset", infer_origin_dataset(fn))
        entry["sweep_count"] += 1
        predicted = row.get("predicted_type", "unknown")
        entry["type_counts"][predicted] += 1
        entry["sweeps"].append(
            {
                "filename": rec.get("filename", row.get("filename", "")),
                "sweep_index": parse_sweep_index(rec.get("filename", row.get("filename", ""))),
                "predicted_type": predicted,
                "forming_stage": row.get("forming_stage", ""),
                "yield_bucket": row.get("yield_bucket", ""),
                "memristivity_score": row.get("memristivity_score", ""),
            }
        )

    summaries: Dict[str, Dict[str, Any]] = {}
    for key, entry in devices.items():
        entry["sweeps"].sort(key=lambda s: (s.get("sweep_index", 0), s.get("filename", "")))
        sweep_stages = [s["forming_stage"] for s in entry["sweeps"] if s.get("forming_stage")]

        if _has_aggregator:
            agg = DeviceSweepAggregator(entry["sweeps"])
            agg_summary = agg.summarize()
            yield_tier = agg_summary["yield_tier"]
            device_forming_stage = agg_summary.get("peak_forming_stage") or (
                "formed_memristive" if yield_tier == "formed"
                else "formed_rectifying" if yield_tier == "formed_rectifying"
                else "precursor_rectifying" if yield_tier == "forming"
                else "unformed"
            )
        else:
            # Fallback to original logic if aggregator import fails
            types = set(entry["type_counts"].keys())
            ever_memristive = bool(types & FORMED_DEVICE_TYPES)
            has_formed_rectifying = bool(set(sweep_stages) & FORMED_RECTIFYING_STAGES)
            has_precursor_rect = bool(set(sweep_stages) & {"precursor_rectifying"})
            agg_summary = {}
            if ever_memristive and not has_formed_rectifying:
                yield_tier, device_forming_stage = "formed", "formed_memristive"
            elif has_formed_rectifying:
                yield_tier, device_forming_stage = "formed_rectifying", "formed_rectifying"
            elif ever_memristive or has_precursor_rect:
                yield_tier, device_forming_stage = "forming", "precursor_rectifying"
            else:
                yield_tier, device_forming_stage = "none", "unformed"

        ever_promising = bool(entry["type_counts"].get("memristive", 0))

        summaries[key] = {
            "device_key": entry["device_key"],
            "device_group_key": key,
            "sample_id": entry["sample_id"],
            "material": entry.get("material", ""),
            "origin_dataset": entry.get("origin_dataset", ""),
            "sweep_count": entry["sweep_count"],
            "type_counts": dict(entry["type_counts"]),
            "yield_tier": yield_tier,
            "yield": 1 if yield_tier in ("formed", "formed_rectifying") else 0,
            "yield_promising": 1 if ever_promising else 0,
            "device_forming_stage": device_forming_stage,
            "trajectory": agg_summary.get("trajectory", ""),
            "memristivity_trend": agg_summary.get("memristivity_trend", ""),
            "peak_forming_stage": agg_summary.get("peak_forming_stage", device_forming_stage),
            "best_memristivity_score": agg_summary.get("best_memristivity_score"),
            "memristive_sweep_count": agg_summary.get("memristive_sweep_count", entry["type_counts"].get("memristive", 0)),
            "forming_stages_seen": list(dict.fromkeys(sweep_stages)),
            "latest_type": entry["sweeps"][-1]["predicted_type"] if entry["sweeps"] else "",
            "latest_forming_stage": sweep_stages[-1] if sweep_stages else device_forming_stage,
            "sweeps": entry["sweeps"],
        }

    return summaries


def save_device_yield_summary(
    records: List[Dict[str, Any]],
    path: Path = DEFAULT_DEVICE_YIELD_JSON,
) -> Dict[str, Dict[str, Any]]:
    summaries = build_device_yield_summaries(records)
    formed = sum(1 for s in summaries.values() if s["yield_tier"] == "formed")
    formed_rect = sum(1 for s in summaries.values() if s["yield_tier"] == "formed_rectifying")
    forming = sum(1 for s in summaries.values() if s["yield_tier"] == "forming")
    promising = sum(1 for s in summaries.values() if s["yield_promising"] == 1)
    # Trajectory distribution
    from collections import Counter as _Counter
    traj_counts = _Counter(s.get("trajectory", "") for s in summaries.values() if s.get("trajectory"))
    regression_count = traj_counts.get("regression", 0)
    payload = _json_safe(
        {
            "generated_at": datetime.now().isoformat(),
            "device_count": len(summaries),
            "yield_formed_memristive_count": formed,
            "yield_formed_rectifying_count": formed_rect,
            "yield_forming_count": forming,
            "yield_promising_count": promising,
            "trajectory_distribution": dict(traj_counts),
            "regression_count": regression_count,
            "devices": summaries,
        }
    )
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return summaries


def load_results(json_path: Path | None = None, *, dataset: str = DEFAULT_DATASET) -> List[Dict[str, Any]]:
    if json_path is None:
        json_path = dataset_paths(dataset)["results_json"]
    if not json_path.exists():
        return []
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return data.get("records", [])


class ReviewLabelStore:
    """
    Persistent user review corrections, keyed by consolidated filename.

    Saved to review_corrections.json per dataset. Survives batch_classify re-runs;
    only adding/removing/renaming consolidated files affects which keys still match.
    """

    def __init__(
        self,
        path: Path = DEFAULT_CORRECTIONS_JSON,
        *,
        dataset: str = DEFAULT_DATASET,
        legacy_path: Path | None = None,
    ) -> None:
        self.path = path
        self.dataset = dataset
        self.legacy_path = legacy_path or DEFAULT_LABELS_JSON
        self.labels: Dict[str, Dict[str, Any]] = {}
        self.created_at: Optional[str] = None
        self.updated_at: Optional[str] = None
        self.load()

    def load(self) -> None:
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "corrections" in raw:
                self.labels = raw.get("corrections") or {}
                self.created_at = raw.get("created_at")
                self.updated_at = raw.get("updated_at")
                if raw.get("dataset"):
                    self.dataset = raw["dataset"]
            elif isinstance(raw, dict):
                # Flat legacy file accidentally at corrections path
                self.labels = raw
            else:
                self.labels = {}
            return

        if self.legacy_path.exists() and self.legacy_path != self.path:
            raw = json.loads(self.legacy_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "corrections" in raw:
                self.labels = raw.get("corrections") or {}
            elif isinstance(raw, dict):
                self.labels = raw
            if self.labels:
                self.save()  # migrate legacy review_labels.json → review_corrections.json
            return

        self.labels = {}

    def save(self) -> None:
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now
        payload = _json_safe(
            {
                "schema_version": CORRECTIONS_SCHEMA_VERSION,
                "dataset": self.dataset,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "correction_count": len(self.labels),
                "note": (
                    "User review corrections. Persists across batch_classify re-runs. "
                    "Keyed by consolidated filename."
                ),
                "corrections": self.labels,
            }
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, filename: str) -> Optional[Dict[str, Any]]:
        return self.labels.get(filename)

    def count(self) -> int:
        return len(self.labels)

    def match_stats(self, filenames: List[str]) -> Dict[str, int]:
        """How many saved corrections match current classification results."""
        current = set(filenames)
        matched = sum(1 for fn in self.labels if fn in current)
        orphaned = len(self.labels) - matched
        return {
            "total": len(self.labels),
            "matched": matched,
            "orphaned": orphaned,
            "unreviewed": max(0, len(current) - matched),
        }

    def export_csv(self, csv_path: Path) -> int:
        """Backup corrections to CSV for spreadsheets / manual archive."""
        rows: List[Dict[str, Any]] = []
        for filename, lab in sorted(self.labels.items()):
            rows.append(
                {
                    "filename": filename,
                    "user_label": lab.get("user_label", ""),
                    "agrees_with_prediction": lab.get("agrees_with_prediction", ""),
                    "predicted_type_at_review": lab.get("predicted_type", ""),
                    "device_group_key": lab.get("device_group_key", ""),
                    "notes": lab.get("notes", ""),
                    "reviewed_at": lab.get("reviewed_at", ""),
                }
            )
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        if rows:
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        else:
            csv_path.write_text("filename,user_label,agrees_with_prediction,predicted_type_at_review,device_group_key,notes,reviewed_at\n", encoding="utf-8")
        return len(rows)

    def set_review(
        self,
        filename: str,
        *,
        user_label: str,
        agrees_with_prediction: bool,
        predicted_type: str,
        notes: str = "",
        device_group_key: str = "",
        review_mode: str = "",
        needs_manual_label: bool = False,
    ) -> None:
        if user_label.lower() not in VALID_USER_LABELS:
            raise ValueError(f"Invalid label: {user_label}")
        entry: Dict[str, Any] = {
            "user_label": user_label.lower(),
            "agrees_with_prediction": agrees_with_prediction,
            "predicted_type": predicted_type,
            "notes": notes,
            "reviewed_at": datetime.now().isoformat(),
        }
        if device_group_key:
            entry["device_group_key"] = device_group_key
        if review_mode:
            entry["review_mode"] = review_mode
        if needs_manual_label:
            entry["needs_manual_label"] = True
        self.labels[filename] = entry
        self.save()
        self.export_csv(self.path.parent / "review_corrections.csv")
