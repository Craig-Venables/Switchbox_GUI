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
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from analysis import quick_analyze

_TRACKING_SUBDIRS = (
    os.path.join("sample_analysis", "analysis", "device_tracking"),
    os.path.join("sample_analysis", "device_tracking"),
    "device_tracking",
)

_EXCLUDE_TXT = frozenset({"classification_log.txt", "classification_summary.txt", "log.txt"})


@dataclass
class ReclassifyStats:
    total_files: int = 0
    reclassified_count: int = 0
    type_changes: int = 0
    errors: List[str] = field(default_factory=list)

    def merge(self, other: "ReclassifyStats") -> None:
        self.total_files += other.total_files
        self.reclassified_count += other.reclassified_count
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
        p.suffix.lower() == ".txt" and p.name not in _EXCLUDE_TXT
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
                if p.name not in _EXCLUDE_TXT
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


def reclassify_sample(
    sample_dir: str | Path,
    sample_name: Optional[str] = None,
    *,
    log_fn: Callable[[str], None] = print,
    progress_fn: Optional[Callable[[int, int, str], None]] = None,
    include_research: bool = True,
) -> ReclassifyStats:
    """
    Re-run classification for all measurement files in a sample folder.

    Parameters
    ----------
    sample_dir:
        Root folder for the sample (e.g. Data_folder/D104).
    sample_name:
        Device id prefix used in tracking filenames. Defaults to folder basename.
    log_fn:
        Status logging callback.
    progress_fn:
        Optional callback(processed, total, message) for UI progress bars.
    include_research:
        When True, re-run research-level analysis for memristive sweeps.
    """
    stats = ReclassifyStats()
    sample_path = Path(sample_dir)
    if not sample_path.is_dir():
        stats.errors.append(f"Sample directory not found: {sample_path}")
        return stats

    sample_name = sample_name or sample_path.name
    tracking_dir = _tracking_dir_for_sample(sample_path)
    legacy_dirs = [str(sample_path / rel) for rel in _TRACKING_SUBDIRS[1:]]
    os.makedirs(tracking_dir, exist_ok=True)

    txt_jobs = enumerate_measurement_files(sample_path, sample_name)
    stats.total_files = len(txt_jobs)
    if stats.total_files == 0:
        log_fn(f"No measurement files found in {sample_path}")
        return stats

    log_fn(f"Reclassifying {stats.total_files} file(s) in {sample_name}…")

    for index, (txt_file, device_id, number_dir) in enumerate(txt_jobs, start=1):
        if progress_fn:
            progress_fn(index - 1, stats.total_files, f"{device_id} / {txt_file.name}")

        history_file = None
        history: Optional[Dict[str, Any]] = None
        for tracking_path in [tracking_dir, *legacy_dirs]:
            potential = os.path.join(tracking_path, f"{device_id}_history.json")
            if os.path.isfile(potential):
                history_file = potential
                try:
                    with open(potential, "r", encoding="utf-8") as f:
                        history = json.load(f)
                    break
                except Exception as exc:
                    stats.errors.append(f"Error loading {device_id} history: {exc}")
                    history = None

        if history is None:
            history_file = os.path.join(tracking_dir, f"{device_id}_history.json")
            history = {
                "device_id": device_id,
                "created": datetime.now().isoformat(),
                "measurements": [],
            }

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
                "file_name": txt_file.stem,
                "reclassification": True,
            }

            analysis_data = quick_analyze(
                voltage=voltage,
                current=current,
                time=timestamps,
                metadata=metadata,
                analysis_level="classification",
                device_id=device_id,
                cycle_number=None,
                save_directory=str(sample_path),
            )

            classification = analysis_data.get("classification", {}) or {}
            new_device_type = classification.get("device_type", "unknown")
            new_memristivity_score = classification.get("memristivity_score", 0)
            new_confidence = classification.get("confidence", 0.0)
            new_conduction_mechanism = classification.get("conduction_mechanism", "N/A")

            file_stem = txt_file.stem
            measurement_found = False
            old_device_type = None

            for measurement in history.get("measurements", []):
                if measurement.get("file_name") == file_stem:
                    old_classification = measurement.get("classification", {}) or {}
                    old_device_type = old_classification.get("device_type", "unknown")
                    measurement["classification"] = {
                        "device_type": new_device_type,
                        "confidence": float(new_confidence),
                        "memristivity_score": float(new_memristivity_score) if new_memristivity_score else None,
                        "conduction_mechanism": new_conduction_mechanism,
                    }
                    measurement["reclassified"] = True
                    measurement["reclassified_timestamp"] = datetime.now().isoformat()
                    if old_device_type != new_device_type:
                        stats.type_changes += 1
                    measurement_found = True
                    break

            if not measurement_found:
                measurements = history.get("measurements", [])
                measurement_to_update = None
                if len(measurements) == 1:
                    measurement_to_update = measurements[0]
                elif measurements:
                    measurement_to_update = sorted(
                        measurements,
                        key=lambda m: m.get("timestamp", ""),
                    )[-1]

                if measurement_to_update is not None:
                    old_classification = measurement_to_update.get("classification", {}) or {}
                    old_device_type = old_classification.get("device_type", "unknown")
                    measurement_to_update["classification"] = {
                        "device_type": new_device_type,
                        "confidence": float(new_confidence),
                        "memristivity_score": float(new_memristivity_score) if new_memristivity_score else None,
                        "conduction_mechanism": new_conduction_mechanism,
                    }
                    measurement_to_update["file_name"] = file_stem
                    measurement_to_update["reclassified"] = True
                    measurement_to_update["reclassified_timestamp"] = datetime.now().isoformat()
                    if old_device_type != new_device_type:
                        stats.type_changes += 1
                    measurement_found = True

            if not measurement_found:
                history.setdefault("measurements", []).append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "cycle_number": None,
                        "classification": {
                            "device_type": new_device_type,
                            "confidence": float(new_confidence),
                            "memristivity_score": float(new_memristivity_score) if new_memristivity_score else None,
                            "conduction_mechanism": new_conduction_mechanism,
                        },
                        "file_name": file_stem,
                        "reclassified": True,
                        "reclassified_timestamp": datetime.now().isoformat(),
                    }
                )

            history["last_updated"] = datetime.now().isoformat()
            history["total_measurements"] = len(history.get("measurements", []))
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(_convert_for_json(history), f, indent=2)

            is_memristive = new_device_type in ("memristive", "memcapacitive") or (
                new_memristivity_score and float(new_memristivity_score) > 60
            )
            if include_research and is_memristive:
                try:
                    research_data = quick_analyze(
                        voltage=voltage,
                        current=current,
                        time=timestamps,
                        metadata=metadata,
                        analysis_level="research",
                        device_id=device_id,
                        cycle_number=None,
                        save_directory=str(sample_path),
                    )
                    _save_research_analysis(research_data, number_dir, file_stem)
                except Exception as exc:
                    stats.errors.append(f"Research failed {device_id}/{txt_file.name}: {exc}")

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
        f"Done {sample_name}: {stats.reclassified_count}/{stats.total_files} files, "
        f"{stats.type_changes} type change(s)"
    )
    return stats
