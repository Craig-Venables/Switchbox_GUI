"""
Batch-classify all consolidated IV .txt files and write CSV + JSON + summary report.

Usage:
    python tools/data_consolidation/batch_classify.py
    python tools/data_consolidation/batch_classify.py --limit 100
    python tools/data_consolidation/batch_classify.py --data-dir tools/data_consolidation/data
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Project root on path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from analysis import quick_analyze
from analysis.core.sweep_analyzer import read_data_file

from classification_store import (
    DEFAULT_DATASET,
    ReviewLabelStore,
    extract_summary_row,
    save_device_yield_summary,
    save_results,
)
from paths import COMBINED_DATASET, DATASETS, DEFAULT_DATASET, SOURCE_DATASETS, dataset_paths

EXCLUDE_NAME_SUBSTRINGS = (
    "freqresp",
    "endurance",
    "pulse_measurements",
    "fast_pulses",
)


def classify_file(path: Path) -> dict:
    result = read_data_file(str(path))
    if result is None or len(result) < 2:
        raise ValueError("no IV data")
    voltage, current = result[0], result[1]
    time_arr = result[2] if len(result) > 2 else None

    analysis = quick_analyze(
        voltage=voltage,
        current=current,
        time=time_arr,
        analysis_level="classification",
        device_name=path.stem,
    )
    row = extract_summary_row(path, analysis)
    record = {
        "filename": path.name,
        "file_path": str(path),
        "row": row,
        "analysis": {
            "classification": analysis.get("classification", {}),
            "resistance_metrics": analysis.get("resistance_metrics", {}),
        },
    }
    return record


def run_batch(
    data_dir: Path,
    *,
    limit: int | None = None,
    json_path: Path | None = None,
    csv_path: Path | None = None,
    summary_path: Path | None = None,
    dataset: str = DEFAULT_DATASET,
) -> dict:
    paths = dataset_paths(dataset)
    json_path = json_path or paths["results_json"]
    csv_path = csv_path or paths["results_csv"]
    summary_path = summary_path or paths["summary_txt"]
    device_yield_path = paths["device_yield_json"]
    files = sorted(data_dir.glob("*.txt"))
    skip_names = {"log.txt", "classification_log.txt", "classification_summary.txt"}
    files = [
        f for f in files
        if f.name not in skip_names
        and not f.name.endswith("_analysis.txt")
        and "tsp_test_log" not in f.name.lower()
        and not any(token in f.name.lower() for token in EXCLUDE_NAME_SUBSTRINGS)
    ]
    if limit is not None:
        files = files[:limit]

    if not files:
        raise FileNotFoundError(f"No .txt files in {data_dir}")

    records: list[dict] = []
    rows: list[dict] = []
    errors: list[str] = []
    t0 = time.time()

    for i, path in enumerate(files, 1):
        try:
            record = classify_file(path)
            records.append(record)
            rows.append(record["row"])
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

        if i % 100 == 0 or i == len(files):
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  [{i}/{len(files)}] {rate:.1f} files/s", flush=True)

    save_results(rows, records, json_path=json_path, csv_path=csv_path, summary_path=summary_path)
    device_summary = save_device_yield_summary(records, path=device_yield_path)

    return {
        "total": len(files),
        "success": len(records),
        "errors": len(errors),
        "error_samples": errors[:10],
        "elapsed_s": round(time.time() - t0, 1),
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "summary_path": str(summary_path),
        "device_yield_count": len(device_summary),
        "yield_promising_count": sum(1 for s in device_summary.values() if s.get("yield_promising")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch classify consolidated IV data.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Classify the All combined merged dataset",
    )
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()),
        default=DEFAULT_DATASET,
        help="Dataset under All_data_collated (default: data 1)",
    )
    parser.add_argument("--data-dir", type=Path, default=None, help="Override flat data directory")
    parser.add_argument("--limit", type=int, default=None, help="Max files (for testing)")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    args = parser.parse_args()

    if args.all:
        datasets = [COMBINED_DATASET]
    else:
        datasets = [args.dataset]

    overall_ok = True
    for ds in datasets:
        paths = dataset_paths(ds)
        data_dir = paths["data_dir"].resolve()
        if not args.all and args.data_dir:
            data_dir = args.data_dir.resolve()
        print(f"\n{'=' * 60}\nDataset: {ds}\nClassifying: {data_dir}\n{'=' * 60}")
        if args.limit:
            print(f"Limit: {args.limit} files")

        try:
            stats = run_batch(
                data_dir,
                limit=args.limit,
                json_path=args.json.resolve() if args.json else None,
                csv_path=args.csv.resolve() if args.csv else None,
                summary_path=args.summary.resolve() if args.summary else None,
                dataset=ds,
            )
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            overall_ok = False
            continue

        print("\nDone:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        print(f"\nRead summary: {stats['summary_path']}")

        corrections_path = paths["corrections_json"]
        legacy_path = paths["labels_json"]
        store = ReviewLabelStore(
            path=corrections_path,
            dataset=ds,
            legacy_path=legacy_path,
        )
        filenames = [p.name for p in data_dir.glob("*.txt")]
        cstats = store.match_stats(filenames)
        print(
            f"\nReview corrections preserved: {cstats['matched']} matched current files "
            f"({cstats['total']} total in {corrections_path.name})"
        )
        if cstats["orphaned"]:
            print(
                f"  {cstats['orphaned']} saved correction(s) are for filenames no longer present "
                f"(kept in {corrections_path.name})"
            )
        if cstats["unreviewed"]:
            print(f"  {cstats['unreviewed']} file(s) not yet reviewed")

    print("\nOpen review GUI: python tools/data_consolidation/launch_review.py --dataset \"All combined\"")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
