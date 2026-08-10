"""
Reclassify saved sample measurements using current classification weights.

Updates device_tracking history JSON files so Sample GUI overlays and yield
manifests reflect the latest scoring rules in classification_weights.json.
"""

from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

from analysis import quick_analyze
from analysis.feature_registry import (
    ALL_FEATURES,
    FULL_FEATURES,
    RESEARCH_FEATURES,
    merge_stamp,
    missing_features,
    needs_full_pass,
    needs_research_pass,
)

_TRACKING_SUBDIRS = (
    os.path.join("sample_analysis", "analysis", "device_tracking"),
    os.path.join("sample_analysis", "device_tracking"),
    "device_tracking",
)

_EXCLUDE_TXT = frozenset({"classification_log.txt", "classification_summary.txt", "log.txt"})

# Non-IV measurement files that must not be scored by the IV sweep classifier.
# Mirrors tools/data_consolidation/batch_classify.EXCLUDE_NAME_SUBSTRINGS.
_EXCLUDE_NAME_SUBSTRINGS = (
    "freqresp",
    "endurance",
    "pulse_measurements",
    "fast_pulses",
    "pot_dep",
    "pulse_multi_read",
    "pulse_train",
    "retention",
)


def _is_excluded_measurement_file(path: Path) -> bool:
    name = path.name
    if name in _EXCLUDE_TXT:
        return True
    lower = name.lower()
    return any(token in lower for token in _EXCLUDE_NAME_SUBSTRINGS)


@dataclass
class ReclassifyStats:
    total_files: int = 0
    reclassified_count: int = 0
    skipped_count: int = 0
    type_changes: int = 0
    errors: List[str] = field(default_factory=list)

    def merge(self, other: "ReclassifyStats") -> None:
        self.total_files += other.total_files
        self.reclassified_count += other.reclassified_count
        self.skipped_count += other.skipped_count
        self.type_changes += other.type_changes
        self.errors.extend(other.errors)


def get_weights_version() -> str:
    """Return version string from classification_weights.json."""
    try:
        root = Path(__file__).resolve().parents[1]
        path = root / "Json_Files" / "classification_weights.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("version", "unknown"))
    except Exception:
        return "unknown"


def discover_sample_dirs(save_root: Path) -> List[Tuple[str, Path]]:
    """Return (sample_name, path) pairs that contain measurement or tracking data."""
    if not save_root.is_dir():
        return []
    found: List[Tuple[str, Path]] = []
    for folder in sorted(save_root.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if _has_sample_data(folder):
            found.append((folder.name, folder))
    return found


def _has_sample_data(folder: Path) -> bool:
    for rel in _TRACKING_SUBDIRS:
        tracking = folder / rel
        if tracking.is_dir() and any(tracking.glob("*_history.json")):
            return True
    for letter_dir in folder.iterdir():
        if not letter_dir.is_dir() or not _looks_like_section_dir(letter_dir.name):
            continue
        for num_dir in letter_dir.iterdir():
            if num_dir.is_dir() and _has_measurement_txt(num_dir):
                return True
    return False


def _looks_like_section_dir(name: str) -> bool:
    return len(name) == 1 and name.isalpha()


def _has_measurement_txt(device_dir: Path) -> bool:
    return any(
        p.suffix.lower() == ".txt" and not _is_excluded_measurement_file(p)
        for p in device_dir.iterdir()
        if p.is_file()
    )


def enumerate_measurement_files(
    sample_dir: str | Path,
    sample_name: Optional[str] = None,
) -> List[Tuple[Path, str, str]]:
    """Return (txt_path, device_id, device_folder) jobs for a sample."""
    sample_path = Path(sample_dir)
    sample_name = sample_name or sample_path.name
    jobs: List[Tuple[Path, str, str]] = []
    if not sample_path.is_dir():
        return jobs
    for letter_dir in sorted(sample_path.iterdir()):
        if not letter_dir.is_dir() or letter_dir.name.startswith("."):
            continue
        if not _looks_like_section_dir(letter_dir.name):
            continue
        letter = letter_dir.name
        for number_dir in sorted(letter_dir.iterdir()):
            if not number_dir.is_dir():
                continue
            txt_files = [
                p for p in number_dir.glob("*.txt")
                if not _is_excluded_measurement_file(p)
            ]
            if not txt_files:
                continue
            device_id = f"{sample_name}_{letter}_{number_dir.name}"
            for txt_file in txt_files:
                jobs.append((txt_file, device_id, str(number_dir)))
    return jobs


def count_measurement_files(sample_dir: str | Path, sample_name: Optional[str] = None) -> int:
    return len(enumerate_measurement_files(sample_dir, sample_name))


def _tracking_dir_for_sample(sample_dir: Path) -> str:
    for rel in _TRACKING_SUBDIRS:
        path = sample_dir / rel
        if path.is_dir():
            return str(path)
    return str(sample_dir / _TRACKING_SUBDIRS[0])


def _convert_for_json(obj: Any) -> Any:
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {key: _convert_for_json(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_convert_for_json(item) for item in obj]
    return obj


def _load_txt_data(txt_file: Path) -> Optional[np.ndarray]:
    try:
        return np.loadtxt(txt_file, skiprows=1)
    except Exception:
        try:
            return np.loadtxt(txt_file)
        except Exception:
            lines = txt_file.read_text(encoding="utf-8", errors="replace").splitlines()
            if lines and ("Voltage" in lines[0] or "voltage" in lines[0].lower()):
                lines = lines[1:]
            data_lines: List[List[float]] = []
            for line in lines:
                if not line.strip() or line.strip().startswith("#"):
                    continue
                try:
                    values = [float(x) for x in line.strip().split()]
                    if len(values) >= 2:
                        data_lines.append(values)
                except ValueError:
                    continue
            if not data_lines:
                return None
            return np.array(data_lines)


def _save_research_analysis(
    research_data: Dict[str, Any],
    save_dir: str,
    file_name: str,
) -> None:
    research_dir = os.path.join(save_dir, "sweep_analysis")
    os.makedirs(research_dir, exist_ok=True)
    research_file = os.path.join(research_dir, f"{file_name}_research.json")
    serializable = _convert_for_json(research_data)
    serializable["saved_timestamp"] = datetime.now().isoformat()
    with open(research_file, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def _append_classification_log(
    save_dir: str,
    file_name: str,
    analysis_data: Dict[str, Any],
) -> None:
    log_file = os.path.join(save_dir, "classification_log.txt")
    classification = analysis_data.get("classification", {}) or {}
    device_type = classification.get("device_type") or "unknown"
    confidence = float(classification.get("confidence") or 0.0)
    memristivity_score = float(classification.get("memristivity_score") or 0.0)
    breakdown = classification.get("breakdown", {}) or {}
    reasoning = classification.get("reasoning", "") or ""
    warnings = classification.get("warnings", []) or []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 80
    file_exists = os.path.exists(log_file)
    with open(log_file, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write(separator + "\n")
            f.write("DEVICE CLASSIFICATION LOG (DETAILED)\n")
            f.write(f"Device: {os.path.basename(save_dir)}\n")
            f.write(f"Created: {timestamp}\n\n")
            f.write(separator + "\n\n")
        f.write(f"{separator}\n")
        f.write(f"Sweep: {file_name}\n")
        f.write(f"Timestamp: {timestamp}\n\n")
        f.write(f"CLASSIFICATION: {str(device_type).upper()}\n")
        f.write(f"Confidence: {confidence:.1%}\n")
        f.write(f"Memristivity Score: {memristivity_score:.1f}/100\n\n")
        if breakdown:
            f.write("Score Breakdown:\n")
            for dtype, score in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
                if score > 0:
                    f.write(f"  - {dtype:15s}: {float(score):6.1f}\n")
            f.write("\n")
        if reasoning:
            f.write("DETAILED EXPLANATION:\n")
            f.write("-" * 80 + "\n")
            for line in reasoning.split("\n"):
                f.write(f"{line}\n")
            f.write("\n")
        if warnings:
            f.write("WARNINGS:\n")
            for i, warning in enumerate(warnings, 1):
                wrapped = textwrap.fill(
                    str(warning),
                    width=75,
                    initial_indent=f"  {i}. ",
                    subsequent_indent="     ",
                )
                f.write(wrapped + "\n")
            f.write("\n")


def _invalidate_yield_manifest(sample_dir: Path) -> None:
    manifest = sample_dir / "sample_analysis" / "yield_analysis" / "yield_manifest.json"
    if manifest.is_file():
        try:
            manifest.unlink()
        except OSError:
            pass


def _compact_mwq(mwq: Any) -> Dict[str, Any]:
    if not isinstance(mwq, dict):
        return {}
    keys = (
        "set_voltage",
        "reset_voltage",
        "avg_switching_voltage",
        "separation_ratio",
        "overall_quality_score",
        "reproducibility",
        "ron_stability",
        "roff_stability",
    )
    out: Dict[str, Any] = {}
    for k in keys:
        if k in mwq and mwq[k] is not None:
            out[k] = mwq[k]
    return out


def _compact_hyst_shape(hs: Any) -> Dict[str, Any]:
    if not isinstance(hs, dict):
        return {}
    keys = (
        "figure_eight_quality",
        "lobe_asymmetry",
        "lobe_area_ratio",
        "num_kinks_detected",
        "avg_hysteresis_width",
    )
    return {k: hs[k] for k in keys if k in hs and hs[k] is not None}


def _compact_memristivity_breakdown(bd: Any) -> Dict[str, Any]:
    if not isinstance(bd, dict):
        return {}
    # Keep top drivers only (by abs value if numeric)
    items = []
    for k, v in bd.items():
        try:
            items.append((str(k), float(v)))
        except (TypeError, ValueError):
            continue
    items.sort(key=lambda x: abs(x[1]), reverse=True)
    return {k: v for k, v in items[:6]}


def _build_full_payloads(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    classification = analysis_data.get("classification", {}) or {}
    resistance = analysis_data.get("resistance_metrics") or {}
    hysteresis = analysis_data.get("hysteresis_metrics") or {}
    voltage = analysis_data.get("voltage_metrics") or {}
    performance = analysis_data.get("performance_metrics") or {}
    features = classification.get("features") or {}

    new_device_type = classification.get("device_type", "unknown")
    new_memristivity_score = classification.get("memristivity_score", 0)
    new_confidence = classification.get("confidence", 0.0)

    class_payload = {
        "device_type": new_device_type,
        "confidence": float(new_confidence),
        "memristivity_score": float(new_memristivity_score)
        if new_memristivity_score is not None
        else None,
        "conduction_mechanism": classification.get("conduction_mechanism", "N/A"),
        "model_r2": classification.get("model_r2"),
        "conduction_model_fits": classification.get("conduction_model_fits") or {},
        "forming_stage": classification.get("forming_stage"),
        "yield_bucket": classification.get("yield_bucket"),
        "warnings": (classification.get("warnings") or [])[:8],
        "memristivity_breakdown": _compact_memristivity_breakdown(
            classification.get("memristivity_breakdown")
        ),
        "switching_strength": features.get(
            "switching_strength", classification.get("switching_strength")
        ),
        "current_jump_detected": features.get("current_jump_detected"),
        "current_jump_ratio": features.get("current_jump_ratio"),
        "forming_voltage_onset": features.get("forming_voltage_onset"),
        "rectifying_tier": features.get("rectifying_tier"),
        "rectification_ratio": features.get("rectification_ratio"),
        "memory_window_quality": _compact_mwq(
            classification.get("memory_window_quality")
        ),
        "hysteresis_shape": _compact_hyst_shape(classification.get("hysteresis_shape")),
    }
    # Prefer performance rectification mean when feature ratio missing
    if class_payload.get("rectification_ratio") is None:
        class_payload["rectification_ratio"] = performance.get(
            "rectification_ratio_mean"
        )

    res_payload = {
        "ron_mean": resistance.get("ron_mean"),
        "roff_mean": resistance.get("roff_mean"),
        "switching_ratio_mean": resistance.get("switching_ratio_mean"),
        "window_margin_mean": resistance.get("window_margin_mean"),
        "on_off_ratio_mean": resistance.get("on_off_ratio_mean"),
        "ron_std": resistance.get("ron_std"),
        "roff_std": resistance.get("roff_std"),
        "ron_n": resistance.get("ron_n"),
        "roff_n": resistance.get("roff_n"),
        "switching_ratio_n": resistance.get("switching_ratio_n"),
        "on_off_ratio_n": resistance.get("on_off_ratio_n"),
        "window_margin_n": resistance.get("window_margin_n"),
        "ron_roff_meta": resistance.get("ron_roff_meta"),
    }
    hyst_payload = {
        "has_hysteresis": hysteresis.get("has_hysteresis"),
        "pinched_hysteresis": hysteresis.get(
            "pinched_hysteresis", hysteresis.get("pinched")
        ),
        # Extract uses normalized_area_mean; accept either key
        "normalized_area": hysteresis.get("normalized_area")
        if hysteresis.get("normalized_area") is not None
        else hysteresis.get("normalized_area_mean"),
    }
    voltage_payload = {
        "von_mean": voltage.get("von_mean"),
        "voff_mean": voltage.get("voff_mean"),
        "max_voltage": voltage.get("max_voltage"),
        "min_voltage": voltage.get("min_voltage"),
    }
    performance_payload = {
        "rectification_ratio_mean": performance.get("rectification_ratio_mean"),
        "nonlinearity_mean": performance.get("nonlinearity_mean"),
        "asymmetry_mean": performance.get("asymmetry_mean"),
        "compliance_current_uA": performance.get("compliance_current"),
        "retention_score": performance.get("retention_score"),
        "endurance_score": performance.get("endurance_score"),
    }
    return {
        "device_type": new_device_type,
        "memristivity_score": new_memristivity_score,
        "classification": class_payload,
        "resistance": res_payload,
        "hysteresis": hyst_payload,
        "voltage": voltage_payload,
        "performance": performance_payload,
        "metrics_quarantined": bool(
            classification.get("metrics_quarantined")
            or (classification.get("quarantine_reasons") or [])
        ),
        "quarantine_reasons": list(classification.get("quarantine_reasons") or []),
    }


def _research_diagnostics_from_extract(research_data: Dict[str, Any]) -> Dict[str, Any]:
    rd = research_data.get("research_diagnostics") or {}
    if not rd and isinstance(research_data.get("diagnostics"), dict):
        rd = research_data["diagnostics"]
    ses = rd.get("slope_exponent_stats") or {}
    return {
        "switching_polarity": rd.get("switching_polarity"),
        "ndr_index": rd.get("ndr_index"),
        "hysteresis_direction": rd.get("hysteresis_direction"),
        "kink_voltage": rd.get("kink_voltage"),
        "loop_similarity_score": rd.get("loop_similarity_score"),
        "pinch_offset": rd.get("pinch_offset"),
        "noise_floor": rd.get("noise_floor"),
        "slope_n_mean": ses.get("mean_n"),
        "slope_n_std": ses.get("std_n"),
        "slope_n_max": ses.get("max_n"),
        "ndr_norm_slope": rd.get("ndr_norm_slope"),
        "ndr_depth": rd.get("ndr_depth"),
        "ndr_v_start": rd.get("ndr_v_start"),
        "ndr_v_end": rd.get("ndr_v_end"),
        "ndr_peak_to_valley": rd.get("ndr_peak_to_valley"),
        "ndr_segment_count": rd.get("ndr_segment_count"),
    }


def reclassify_sample(
    sample_dir: str | Path,
    sample_name: Optional[str] = None,
    *,
    log_fn: Callable[[str], None] = print,
    progress_fn: Optional[Callable[[int, int, str], None]] = None,
    include_research: bool = True,
    rebuild_history: bool = False,
    required_features: Optional[Iterable[str]] = None,
) -> ReclassifyStats:
    """
    Re-run classification for all measurement files in a sample folder.

    Writes one history measurement per .txt (matched by file_name). Skips files
    whose ``analysis_features`` already cover ``required_features`` at current
    versions (unless ``rebuild_history``).
    """
    stats = ReclassifyStats()
    sample_path = Path(sample_dir)
    if not sample_path.is_dir():
        stats.errors.append(f"Sample directory not found: {sample_path}")
        return stats

    sample_name = sample_name or sample_path.name
    tracking_dir = _tracking_dir_for_sample(sample_path)
    os.makedirs(tracking_dir, exist_ok=True)

    req = set(required_features) if required_features is not None else set(ALL_FEATURES)
    if not include_research:
        req -= RESEARCH_FEATURES
    # Always keep full features when requesting anything
    if req & FULL_FEATURES:
        req |= FULL_FEATURES & set(ALL_FEATURES)

    txt_jobs = enumerate_measurement_files(sample_path, sample_name)
    stats.total_files = len(txt_jobs)
    if stats.total_files == 0:
        log_fn(f"No measurement files found in {sample_path}")
        return stats

    log_fn(
        f"Reclassifying {stats.total_files} file(s) in {sample_name} "
        f"(features={sorted(req)})…"
    )

    histories: Dict[str, Dict[str, Any]] = {}
    history_paths: Dict[str, str] = {}

    for index, (txt_file, device_id, number_dir) in enumerate(txt_jobs, start=1):
        if progress_fn:
            progress_fn(index - 1, stats.total_files, f"{device_id} / {txt_file.name}")

        if device_id not in histories:
            history_file = os.path.join(tracking_dir, f"{device_id}_history.json")
            history: Dict[str, Any]
            if rebuild_history or not os.path.isfile(history_file):
                history = {
                    "device_id": device_id,
                    "created": datetime.now().isoformat(),
                    "measurements": [],
                }
                if rebuild_history:
                    history["rebuilt"] = datetime.now().isoformat()
            else:
                try:
                    with open(history_file, "r", encoding="utf-8") as f:
                        history = json.load(f)
                except Exception as exc:
                    stats.errors.append(f"Error loading {device_id} history: {exc}")
                    history = {
                        "device_id": device_id,
                        "created": datetime.now().isoformat(),
                        "measurements": [],
                    }
            histories[device_id] = history
            history_paths[device_id] = history_file

        history = histories[device_id]
        history_file = history_paths[device_id]
        file_stem = txt_file.stem

        measurement: Optional[Dict[str, Any]] = None
        for m in history.get("measurements", []):
            if m.get("file_name") == file_stem:
                measurement = m
                break

        miss = (
            list(req)
            if rebuild_history or measurement is None
            else missing_features(measurement.get("analysis_features"), req)
        )
        if not miss:
            stats.skipped_count += 1
            if progress_fn:
                progress_fn(index, stats.total_files, f"{device_id} / {txt_file.name}")
            continue

        try:
            data = _load_txt_data(txt_file)
            if data is None or len(data.shape) < 2 or data.shape[1] < 2:
                stats.errors.append(f"{txt_file.name}: insufficient data")
                continue

            voltage = data[:, 0]
            current = data[:, 1]
            timestamps = data[:, 2] if data.shape[1] > 2 else None
            if len(voltage) == 0 or len(current) == 0:
                stats.errors.append(f"{txt_file.name}: empty data")
                continue

            metadata = {
                "device_name": device_id,
                "file_name": file_stem,
                "reclassification": True,
            }

            analysis_data: Optional[Dict[str, Any]] = None
            stamped_ids: List[str] = []

            if needs_full_pass(miss) or measurement is None:
                analysis_data = quick_analyze(
                    voltage=voltage,
                    current=current,
                    time=timestamps,
                    metadata=metadata,
                    analysis_level="full",
                    device_id=device_id,
                    cycle_number=None,
                    save_directory=None,
                )
                payloads = _build_full_payloads(analysis_data)
                new_device_type = payloads["device_type"]
                new_memristivity_score = payloads["memristivity_score"]

                if measurement is None:
                    measurement = {
                        "timestamp": datetime.now().isoformat(),
                        "cycle_number": None,
                        "file_name": file_stem,
                    }
                    history.setdefault("measurements", []).append(measurement)
                else:
                    old_type = (measurement.get("classification") or {}).get(
                        "device_type", "unknown"
                    )
                    if old_type != new_device_type:
                        stats.type_changes += 1

                measurement["classification"] = payloads["classification"]
                measurement["resistance"] = payloads["resistance"]
                measurement["hysteresis"] = payloads["hysteresis"]
                measurement["voltage"] = payloads["voltage"]
                measurement["performance"] = payloads["performance"]
                measurement["metrics_quarantined"] = bool(
                    payloads.get("metrics_quarantined")
                )
                measurement["quarantine_reasons"] = list(
                    payloads.get("quarantine_reasons") or []
                )
                stamped_ids.extend(sorted(FULL_FEATURES))
            else:
                # Research-only fill: infer memristive from existing classification
                cls = (measurement or {}).get("classification") or {}
                new_device_type = cls.get("device_type", "unknown")
                new_memristivity_score = cls.get("memristivity_score", 0)

            is_memristive = new_device_type in ("memristive", "memcapacitive") or (
                new_memristivity_score and float(new_memristivity_score) > 60
            )

            if include_research and needs_research_pass(miss):
                if is_memristive:
                    try:
                        research_data = quick_analyze(
                            voltage=voltage,
                            current=current,
                            time=timestamps,
                            metadata=metadata,
                            analysis_level="research",
                            device_id=device_id,
                            cycle_number=None,
                            save_directory=None,
                        )
                        _save_research_analysis(research_data, number_dir, file_stem)
                        assert measurement is not None
                        measurement["research_diagnostics"] = (
                            _research_diagnostics_from_extract(research_data)
                        )
                        stamped_ids.extend(sorted(RESEARCH_FEATURES))
                    except Exception as exc:
                        stats.errors.append(
                            f"Research failed {device_id}/{txt_file.name}: {exc}"
                        )
                else:
                    # Non-memristive: mark research features present as null block
                    assert measurement is not None
                    measurement["research_diagnostics"] = {
                        "ndr_index": None,
                        "note": "research_skipped_non_memristive",
                    }
                    stamped_ids.extend(sorted(RESEARCH_FEATURES))

            assert measurement is not None
            measurement["reclassified"] = True
            measurement["reclassified_timestamp"] = datetime.now().isoformat()
            if stamped_ids:
                measurement["analysis_features"] = merge_stamp(
                    measurement.get("analysis_features"), stamped_ids
                )

            history["last_updated"] = datetime.now().isoformat()
            history["total_measurements"] = len(history.get("measurements", []))
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(_convert_for_json(history), f, indent=2)

            if analysis_data is not None:
                try:
                    _append_classification_log(number_dir, file_stem, analysis_data)
                except Exception:
                    pass

            stats.reclassified_count += 1
            if progress_fn:
                progress_fn(index, stats.total_files, f"{device_id} / {txt_file.name}")

        except Exception as exc:
            stats.errors.append(f"{device_id}/{txt_file.name}: {exc}")

    _invalidate_yield_manifest(sample_path)
    log_fn(
        f"Done {sample_name}: updated={stats.reclassified_count} "
        f"skipped={stats.skipped_count}/{stats.total_files} files, "
        f"{stats.type_changes} type change(s)"
    )
    return stats
