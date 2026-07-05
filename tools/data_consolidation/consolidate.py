"""
Consolidate IV sweep .txt files into flat OneDrive dataset folders.

Datasets (under All_data_collated/):
  data 1       — Data_folder (top-level Dxx sample folders)
  Quantum Dots — recursive scan under PhD Devices/Memristors/Quantum Dots
  Stock        — recursive scan under PhD Devices/Memristors/Stock

Output naming: D94-A-1-1-FS-0.5v-....txt
  Nested sources may prefix material: WS2-D15-G-1-1-Fs_....txt

Usage:
    python tools/data_consolidation/consolidate.py --all
    python tools/data_consolidation/consolidate.py --dataset "data 1"
    python tools/data_consolidation/consolidate.py --dataset "Quantum Dots" --dry-run
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from paths import ALL_DATA_COLLATED, COMBINED_DATASET, DATASETS, MERGE_TAGS, SOURCE_DATASETS, dataset_dir

D_SAMPLE_FOLDER_RE = re.compile(r"^(D\d+)", re.IGNORECASE)

EXCLUDE_FILENAMES = frozenset({
    "log.txt",
    "classification_log.txt",
    "classification_summary.txt",
    "stats_dict.txt",
})

EXCLUDE_NAME_SUBSTRINGS = (
    "freqresp",
    "endurance",
    "pulse_measurements",
    "fast_pulses",
)

# Duplicate extracts / plots — IV originals live in section/device folders
EXCLUDE_PATH_PARTS = frozenset({
    "python_images",
    "plots_combined",
    "extracted sweeps",
    "sample_analysis",
    "sweep_analysis",
})

MANIFEST_FIELDS = (
    "output_name",
    "source_path",
    "sample_id",
    "section",
    "device_number",
    "original_filename",
    "source_folder",
    "material_prefix",
    "dataset",
    "origin_dataset",
    "collision_suffix",
)


@dataclass
class ParsedPath:
    sample_id: str
    section: str
    device_number: str
    filename_part: str
    material_prefix: str = ""


def extract_sample_id(folder_name: str) -> Optional[str]:
    """Return Dxx from folder name (e.g. D94 from D94-0.1mgml-ITO-...)."""
    match = D_SAMPLE_FOLDER_RE.match(folder_name.strip())
    if not match:
        return None
    return match.group(1).upper()


def iter_d_sample_roots(source: Path) -> Iterator[tuple[str, Path]]:
    """Yield (sample_id, folder_path) for each top-level Dxx folder."""
    if not source.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source}")

    for entry in sorted(source.iterdir()):
        if not entry.is_dir():
            continue
        sample_id = extract_sample_id(entry.name)
        if sample_id is None:
            continue
        yield sample_id, entry


def find_dxx_ancestor(path: Path, stop_at: Path) -> Optional[tuple[str, Path]]:
    """Walk parents from path until a Dxx-named folder is found (up to stop_at)."""
    current = path.parent
    stop_resolved = stop_at.resolve()
    while True:
        sample_id = extract_sample_id(current.name)
        if sample_id:
            return sample_id, current
        if current.resolve() == stop_resolved:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def material_slug(source_root: Path, dxx_root: Path) -> str:
    """First path component between source root and Dxx folder (e.g. WS2, F8PFB)."""
    try:
        parts = dxx_root.relative_to(source_root).parts
        if parts:
            return sanitize_filename(parts[0])
    except ValueError:
        pass
    return ""


def should_include_txt(path: Path) -> bool:
    name = path.name
    if name in EXCLUDE_FILENAMES:
        return False
    if name.endswith("_analysis.txt"):
        return False
    name_lower = name.lower()
    if "tsp_test_log" in name_lower:
        return False
    if any(token in name_lower for token in EXCLUDE_NAME_SUBSTRINGS):
        return False
    parts_lower = {p.lower() for p in path.parts}
    if parts_lower & EXCLUDE_PATH_PARTS:
        return False
    return True


def parse_relative_path(sample_id: str, relative: Path) -> ParsedPath:
    """
    Build output name parts from path relative to sample root.

    Expected layout: Section/Device/file.txt or Section/Device/subdir/file.txt
    """
    rel_str = relative.as_posix()
    m = re.match(r"^([A-Za-z])/(\d+)(?:/(.*))?$", rel_str)
    if m:
        section = m.group(1).upper()
        device = m.group(2)
        rest = m.group(3) or relative.name
        if "/" in rest:
            rest = rest.replace("/", "-")
        return ParsedPath(
            sample_id=sample_id,
            section=section,
            device_number=device,
            filename_part=rest,
        )

    flat = "-".join(relative.parts)
    return ParsedPath(
        sample_id=sample_id,
        section="X",
        device_number="0",
        filename_part=flat,
    )


def build_output_name(parsed: ParsedPath) -> str:
    if parsed.material_prefix:
        return (
            f"{parsed.material_prefix}-{parsed.sample_id}-"
            f"{parsed.section}-{parsed.device_number}-{parsed.filename_part}"
        )
    return f"{parsed.sample_id}-{parsed.section}-{parsed.device_number}-{parsed.filename_part}"


def sanitize_filename(name: str) -> str:
    """Remove characters invalid or problematic on Windows."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"-{2,}", "-", name)
    name = name.strip(".-_")
    return name or "file.txt"


def unique_output_path(output_dir: Path, base_name: str, reserved: set[str]) -> tuple[Path, str]:
    """Return a unique path in output_dir; append -2, -3, ... on collision."""
    base_name = sanitize_filename(base_name)
    if not base_name.lower().endswith(".txt"):
        base_name = f"{base_name}.txt"

    if base_name not in reserved:
        reserved.add(base_name)
        return output_dir / base_name, ""

    stem = Path(base_name).stem
    suffix = Path(base_name).suffix
    n = 2
    while True:
        collision_name = f"{stem}-{n}{suffix}"
        if collision_name not in reserved:
            reserved.add(collision_name)
            return output_dir / collision_name, f"-{n}"
        n += 1


def _process_txt(
    txt_path: Path,
    *,
    sample_id: str,
    sample_root: Path,
    source_root: Path,
    prefix_material: bool,
    output: Path,
    dataset_name: str,
    dry_run: bool,
    used_names: set[str],
    manifest_rows: list[dict[str, str]],
    stats: dict[str, int],
) -> None:
    if not should_include_txt(txt_path):
        stats["files_skipped"] += 1
        return

    stats["files_found"] += 1
    try:
        relative = txt_path.relative_to(sample_root)
        parsed = parse_relative_path(sample_id, relative)
        if prefix_material:
            parsed.material_prefix = material_slug(source_root, sample_root)
        output_name = build_output_name(parsed)
        dest_path, collision_suffix = unique_output_path(output, output_name, used_names)
        if collision_suffix:
            stats["collisions"] += 1

        manifest_rows.append({
            "output_name": dest_path.name,
            "source_path": str(txt_path),
            "sample_id": parsed.sample_id,
            "section": parsed.section,
            "device_number": parsed.device_number,
            "original_filename": txt_path.name,
            "source_folder": sample_root.name,
            "material_prefix": parsed.material_prefix,
            "dataset": dataset_name,
            "origin_dataset": dataset_name,
            "collision_suffix": collision_suffix,
        })

        if dry_run:
            msg = f"[dry-run] {txt_path.name} -> {dest_path.name}"
            print(msg.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8", errors="replace"
            ))
        elif dest_path.exists():
            stats["files_skipped"] += 1
        else:
            shutil.copy2(txt_path, dest_path)
            stats["files_copied"] += 1
        if dry_run:
            stats["files_copied"] += 1
    except Exception as exc:
        stats["errors"] += 1
        print(f"[ERROR] {txt_path}: {exc}", file=sys.stderr)


def consolidate_combined(
    dataset_name: str = COMBINED_DATASET,
    *,
    dry_run: bool = False,
    manifest_path: Optional[Path] = None,
) -> dict[str, int]:
    """Merge flat files from source datasets into one folder with origin prefix tags."""
    cfg = DATASETS[dataset_name]
    merge_from = list(cfg.get("merge_from", SOURCE_DATASETS))
    output = dataset_dir(dataset_name)
    output.mkdir(parents=True, exist_ok=True)
    ALL_DATA_COLLATED.mkdir(parents=True, exist_ok=True)
    if manifest_path is None:
        manifest_path = output / "manifest.csv"

    import csv as csv_mod

    stats = {
        "dataset": dataset_name,
        "folders_scanned": len(merge_from),
        "files_found": 0,
        "files_copied": 0,
        "files_skipped": 0,
        "collisions": 0,
        "errors": 0,
    }
    used_names: set[str] = set()
    manifest_rows: list[dict[str, str]] = []

    for src_dataset in merge_from:
        src_dir = dataset_dir(src_dataset)
        tag = MERGE_TAGS.get(src_dataset, src_dataset.replace(" ", "")[:6])
        src_manifest = src_dir / "manifest.csv"

        entries: list[tuple[str, dict[str, str]]] = []
        if src_manifest.exists():
            with src_manifest.open(newline="", encoding="utf-8") as f:
                for row in csv_mod.DictReader(f):
                    entries.append((row["output_name"], row))
        else:
            for txt in sorted(src_dir.glob("*.txt")):
                entries.append((txt.name, {"output_name": txt.name, "source_path": str(txt)}))

        for output_name, src_row in entries:
            src_file = src_dir / output_name
            if not src_file.is_file():
                stats["files_skipped"] += 1
                continue

            stats["files_found"] += 1
            combined_name = f"{tag}-{output_name}"
            try:
                dest_path, collision_suffix = unique_output_path(output, combined_name, used_names)
                if collision_suffix:
                    stats["collisions"] += 1

                manifest_rows.append({
                    "output_name": dest_path.name,
                    "source_path": str(src_file),
                    "sample_id": src_row.get("sample_id", ""),
                    "section": src_row.get("section", ""),
                    "device_number": src_row.get("device_number", ""),
                    "original_filename": src_row.get("original_filename", src_file.name),
                    "source_folder": src_row.get("source_folder", ""),
                    "material_prefix": src_row.get("material_prefix", ""),
                    "dataset": dataset_name,
                    "origin_dataset": src_dataset,
                    "collision_suffix": collision_suffix,
                })

                if dry_run:
                    print(f"[dry-run] {src_dataset}/{output_name} -> {dest_path.name}")
                    stats["files_copied"] += 1
                elif dest_path.exists():
                    stats["files_skipped"] += 1
                else:
                    shutil.copy2(src_file, dest_path)
                    stats["files_copied"] += 1
            except Exception as exc:
                stats["errors"] += 1
                print(f"[ERROR] {src_file}: {exc}", file=sys.stderr)

    if not dry_run and manifest_rows:
        with manifest_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv_mod.DictWriter(f, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(manifest_rows)
        print(f"[MANIFEST] {dataset_name}: {len(manifest_rows)} rows -> {manifest_path}")

    return stats


def consolidate_dataset(
    dataset_name: str,
    *,
    dry_run: bool = False,
    manifest_path: Optional[Path] = None,
) -> dict[str, int]:
    if dataset_name not in DATASETS:
        raise KeyError(f"Unknown dataset: {dataset_name}")

    if str(DATASETS[dataset_name].get("mode")) == "merge":
        return consolidate_combined(dataset_name, dry_run=dry_run, manifest_path=manifest_path)

    cfg = DATASETS[dataset_name]
    source = Path(str(cfg["source"])).resolve()
    output = dataset_dir(dataset_name)
    ALL_DATA_COLLATED.mkdir(parents=True, exist_ok=True)

    return consolidate(
        source,
        output,
        dry_run=dry_run,
        manifest_path=manifest_path or output / "manifest.csv",
        prefix_material=bool(cfg.get("prefix_material", False)),
        mode=str(cfg["mode"]),
        dataset_name=dataset_name,
    )


def consolidate(
    source: Path,
    output: Path,
    dry_run: bool = False,
    manifest_path: Optional[Path] = None,
    *,
    prefix_material: bool = False,
    mode: str = "dxx_top_level",
    dataset_name: str = "data 1",
) -> dict[str, int]:
    """Single-source consolidate into a specific output directory."""
    output.mkdir(parents=True, exist_ok=True)
    if manifest_path is None:
        manifest_path = output / "manifest.csv"

    stats = {
        "dataset": dataset_name,
        "folders_scanned": 0,
        "files_found": 0,
        "files_copied": 0,
        "files_skipped": 0,
        "collisions": 0,
        "errors": 0,
    }
    used_names: set[str] = set()
    manifest_rows: list[dict[str, str]] = []

    if mode == "dxx_top_level":
        for sample_id, sample_root in iter_d_sample_roots(source):
            stats["folders_scanned"] += 1
            for txt_path in sorted(sample_root.rglob("*.txt")):
                _process_txt(
                    txt_path,
                    sample_id=sample_id,
                    sample_root=sample_root,
                    source_root=source,
                    prefix_material=prefix_material,
                    output=output,
                    dataset_name=dataset_name,
                    dry_run=dry_run,
                    used_names=used_names,
                    manifest_rows=manifest_rows,
                    stats=stats,
                )
    elif mode == "dxx_nested":
        seen_roots: set[Path] = set()
        for txt_path in sorted(source.rglob("*.txt")):
            found = find_dxx_ancestor(txt_path, source)
            if not found:
                stats["files_skipped"] += 1
                continue
            sample_id, sample_root = found
            sample_root = sample_root.resolve()
            if sample_root not in seen_roots:
                seen_roots.add(sample_root)
                stats["folders_scanned"] += 1
            _process_txt(
                txt_path,
                sample_id=sample_id,
                sample_root=sample_root,
                source_root=source,
                prefix_material=prefix_material,
                output=output,
                dataset_name=dataset_name,
                dry_run=dry_run,
                used_names=used_names,
                manifest_rows=manifest_rows,
                stats=stats,
            )
    elif mode == "named_sample":
        # Each top-level subdirectory IS the sample (no Dxx prefix needed).
        # Structure: source/{SampleName}/{Section}/{Device}/{sweep}.txt
        for sample_dir in sorted(source.iterdir()):
            if not sample_dir.is_dir():
                continue
            sample_id = sanitize_filename(sample_dir.name)
            if not sample_id:
                continue
            stats["folders_scanned"] += 1
            for txt_path in sorted(sample_dir.rglob("*.txt")):
                _process_txt(
                    txt_path,
                    sample_id=sample_id,
                    sample_root=sample_dir,
                    source_root=source,
                    prefix_material=prefix_material,
                    output=output,
                    dataset_name=dataset_name,
                    dry_run=dry_run,
                    used_names=used_names,
                    manifest_rows=manifest_rows,
                    stats=stats,
                )

    if not dry_run and manifest_rows:
        with manifest_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(manifest_rows)
        print(f"[MANIFEST] {dataset_name}: {len(manifest_rows)} rows -> {manifest_path}")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate IV .txt files into OneDrive All_data_collated datasets.",
    )
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()),
        default=None,
        help=f"Dataset to build (default: {list(DATASETS.keys())[0]} if not using --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Consolidate source datasets then merge into All combined",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Override source path (single run only; ignores dataset source)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output directory (single run only)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="CSV manifest path (default: <dataset_dir>/manifest.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned copies without writing files",
    )
    args = parser.parse_args()

    if args.all:
        datasets = list(SOURCE_DATASETS) + [COMBINED_DATASET]
    elif args.dataset:
        datasets = [args.dataset]
    else:
        datasets = ["data 1"]

    if (args.source or args.output) and len(datasets) > 1:
        print("Error: --source/--output only valid with a single dataset.", file=sys.stderr)
        return 1

    exit_code = 0
    for name in datasets:
        print(f"\n{'=' * 60}\nDataset: {name}\n{'=' * 60}")
        cfg = DATASETS[name]
        if str(cfg.get("mode")) == "merge":
            print(f"Merge from: {', '.join(cfg.get('merge_from', []))}")
        else:
            print(f"Source:  {args.source or cfg['source']}")
        print(f"Output:  {args.output or dataset_dir(name)}")
        if args.dry_run:
            print("Mode:    dry-run")

        try:
            if args.source or args.output:
                if str(cfg.get("mode")) == "merge":
                    print("Error: --source/--output not valid for merge dataset.", file=sys.stderr)
                    exit_code = 1
                    continue
                cfg = DATASETS[name]
                stats = consolidate(
                    source=(args.source or Path(str(cfg["source"]))).resolve(),
                    output=(args.output or dataset_dir(name)).resolve(),
                    dry_run=args.dry_run,
                    manifest_path=args.manifest.resolve() if args.manifest else None,
                    prefix_material=bool(cfg.get("prefix_material", False)),
                    mode=str(cfg["mode"]),
                    dataset_name=name,
                )
            else:
                stats = consolidate_dataset(
                    name,
                    dry_run=args.dry_run,
                    manifest_path=args.manifest.resolve() if args.manifest else None,
                )
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        print("\nSummary:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        if stats.get("errors", 0):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
