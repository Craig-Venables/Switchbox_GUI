"""
Analyze review corrections vs classifier predictions.

Usage:
    python tools/data_consolidation/analyze_corrections.py
    python tools/data_consolidation/analyze_corrections.py --dataset "All combined"
    python tools/data_consolidation/analyze_corrections.py --export-csv corrections_analysis.csv

Reads classification_results.json + review_corrections.json for the dataset and prints:
  - Agreement rate (% you agreed with the classifier)
  - Confusion matrix  (predicted → your correction)
  - Per-origin-dataset and per-material breakdown
  - Uncertain / low-confidence audit
  - Export labeled subset CSV for use with the classification_validation tool
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from classification_store import (
    DEFAULT_DATASET,
    ReviewLabelStore,
    load_results,
)
from paths import DATASETS, dataset_paths


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def _load_dataset(dataset: str) -> tuple[List[Dict[str, Any]], ReviewLabelStore]:
    records = load_results(dataset=dataset)
    paths = dataset_paths(dataset)
    store = ReviewLabelStore(paths["corrections_json"], dataset=dataset)
    return records, store


def _join(records: List[Dict[str, Any]], store: ReviewLabelStore):
    """Yield (row, correction | None) for every record."""
    for rec in records:
        fn = rec.get("filename", "")
        row = rec.get("row", {}) or {}
        yield row, store.get(fn)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _build_metrics(rows_corrections):
    """
    rows_corrections: iterable of (row_dict, correction_dict | None)

    Returns a dict with:
      total_classified, total_reviewed, agreed, disagreed,
      confusion Counter{(pred, user): n},
      by_origin Counter, by_material Counter,
      by_predicted Counter, low_conf_errors list, uncertain_errors list
    """
    total = 0
    reviewed = 0
    agreed = 0
    disagreed = 0
    confusion: Counter = Counter()
    by_origin_agree: Counter = Counter()
    by_origin_disagree: Counter = Counter()
    by_material_agree: Counter = Counter()
    by_material_disagree: Counter = Counter()
    by_predicted_agree: Counter = Counter()
    by_predicted_disagree: Counter = Counter()
    low_conf_errors: List[Dict] = []
    uncertain_errors: List[Dict] = []
    labeled_rows: List[Dict] = []

    for row, corr in rows_corrections:
        total += 1
        if corr is None or corr.get("user_label") == "skip":
            continue
        reviewed += 1
        pred = row.get("predicted_type", "unknown")
        user = corr.get("user_label", "unknown")
        agrees = corr.get("agrees_with_prediction", pred == user)
        origin = row.get("origin_dataset", "") or "unknown"
        material = row.get("material", "") or "unknown"
        conf = float(row.get("confidence") or 0)

        if agrees:
            agreed += 1
            by_origin_agree[origin] += 1
            by_material_agree[material] += 1
            by_predicted_agree[pred] += 1
        else:
            disagreed += 1
            confusion[(pred, user)] += 1
            by_origin_disagree[origin] += 1
            by_material_disagree[material] += 1
            by_predicted_disagree[pred] += 1
            if conf < 0.4:
                low_conf_errors.append({"filename": row.get("filename", ""), "predicted": pred,
                                         "user": user, "confidence": conf})
            if pred == "uncertain":
                uncertain_errors.append({"filename": row.get("filename", ""), "user": user, "confidence": conf})

        labeled_rows.append({
            "filename": row.get("filename", ""),
            "file_path": row.get("file_path", ""),
            "predicted_type": pred,
            "user_label": user,
            "agrees": agrees,
            "confidence": conf,
            "memristivity_score": row.get("memristivity_score", ""),
            "forming_stage": row.get("forming_stage", ""),
            "origin_dataset": origin,
            "material": material,
            "sample_id": row.get("sample_id", ""),
            "has_hysteresis": row.get("has_hysteresis", ""),
            "pinched_hysteresis": row.get("pinched_hysteresis", ""),
            "switching_behavior": row.get("switching_behavior", ""),
            "score_memristive": row.get("score_memristive", ""),
            "score_ohmic": row.get("score_ohmic", ""),
            "score_capacitive": row.get("score_capacitive", ""),
            "score_conductive": row.get("score_conductive", ""),
            "review_priority": row.get("review_priority", ""),
            "notes": corr.get("notes", ""),
        })

    return {
        "total": total,
        "reviewed": reviewed,
        "agreed": agreed,
        "disagreed": disagreed,
        "confusion": confusion,
        "by_origin_agree": by_origin_agree,
        "by_origin_disagree": by_origin_disagree,
        "by_material_agree": by_material_agree,
        "by_material_disagree": by_material_disagree,
        "by_predicted_agree": by_predicted_agree,
        "by_predicted_disagree": by_predicted_disagree,
        "low_conf_errors": low_conf_errors,
        "uncertain_errors": uncertain_errors,
        "labeled_rows": labeled_rows,
    }


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

SEP = "=" * 65


def _pct(n: int, d: int) -> str:
    return f"{100*n/d:.1f}%" if d else "n/a"


def _print_report(m: Dict, dataset: str) -> None:
    total = m["total"]
    reviewed = m["reviewed"]
    agreed = m["agreed"]
    disagreed = m["disagreed"]
    agree_rate = _pct(agreed, reviewed)

    print(f"\n{SEP}")
    print(f"  CLASSIFICATION CORRECTIONS ANALYSIS  —  {dataset}")
    print(SEP)
    print(f"  Total classified sweeps : {total}")
    print(f"  Reviewed (non-skip)     : {reviewed}  ({_pct(reviewed, total)} coverage)")
    if reviewed == 0:
        print("\n  No review labels yet.  Run the flash/full review GUI first.")
        print(f"    python tools/data_consolidation/launch_flash_review.py --dataset \"{dataset}\"")
        print(f"    python tools/data_consolidation/launch_review.py --dataset \"{dataset}\"")
        print(SEP)
        return
    print(f"  Agreed with classifier  : {agreed}  ({agree_rate})")
    print(f"  Disagreed               : {disagreed}  ({_pct(disagreed, reviewed)})")

    # --- Confusion matrix ---
    if m["confusion"]:
        print(f"\n  Top prediction → your correction (disagreements only):")
        print(f"  {'Predicted':<18} {'Your label':<18} {'Count':>6}")
        print(f"  {'-'*18} {'-'*18} {'-'*6}")
        for (pred, user), n in m["confusion"].most_common(15):
            print(f"  {pred:<18} {user:<18} {n:>6}")

    # --- Per-origin ---
    all_origins = set(m["by_origin_agree"]) | set(m["by_origin_disagree"])
    if len(all_origins) > 1:
        print(f"\n  Per origin-dataset:")
        print(f"  {'Dataset':<20} {'Agreed':>7} {'Wrong':>7} {'Accuracy':>10}")
        print(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*10}")
        for origin in sorted(all_origins):
            a = m["by_origin_agree"].get(origin, 0)
            d = m["by_origin_disagree"].get(origin, 0)
            print(f"  {origin:<20} {a:>7} {d:>7} {_pct(a, a+d):>10}")

    # --- Per-material ---
    all_mats = set(m["by_material_agree"]) | set(m["by_material_disagree"])
    if len(all_mats) > 1:
        print(f"\n  Per material:")
        print(f"  {'Material':<20} {'Agreed':>7} {'Wrong':>7} {'Accuracy':>10}")
        print(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*10}")
        for mat in sorted(all_mats):
            a = m["by_material_agree"].get(mat, 0)
            d = m["by_material_disagree"].get(mat, 0)
            print(f"  {mat:<20} {a:>7} {d:>7} {_pct(a, a+d):>10}")

    # --- Per predicted type ---
    all_types = set(m["by_predicted_agree"]) | set(m["by_predicted_disagree"])
    print(f"\n  Accuracy per predicted type:")
    print(f"  {'Type':<18} {'Agreed':>7} {'Wrong':>7} {'Accuracy':>10}")
    print(f"  {'-'*18} {'-'*7} {'-'*7} {'-'*10}")
    for t in sorted(all_types):
        a = m["by_predicted_agree"].get(t, 0)
        d = m["by_predicted_disagree"].get(t, 0)
        print(f"  {t:<18} {a:>7} {d:>7} {_pct(a, a+d):>10}")

    # --- Low-conf errors ---
    if m["low_conf_errors"]:
        print(f"\n  Low-confidence (<40%) disagreements: {len(m['low_conf_errors'])}")
        for e in m["low_conf_errors"][:5]:
            print(f"    {e['filename']}  pred={e['predicted']}  user={e['user']}  conf={e['confidence']:.0%}")
        if len(m["low_conf_errors"]) > 5:
            print(f"    ... and {len(m['low_conf_errors'])-5} more")

    # --- Uncertain audit ---
    if m["uncertain_errors"]:
        print(f"\n  'uncertain' predictions you labelled as something else: {len(m['uncertain_errors'])}")
        label_dist = Counter(e["user"] for e in m["uncertain_errors"])
        for lbl, n in label_dist.most_common():
            print(f"    → {lbl}: {n}")

    # --- Recommendations ---
    print(f"\n  Recommended tuning actions:")
    top_pair = m["confusion"].most_common(1)
    if top_pair:
        (pred, user), n = top_pair[0]
        print(f"    1. Top confusion: {pred} → {user} ({n}x)")
        if pred == "memristive" and user == "ohmic":
            print("       → Lower memristive_switching_behavior weight or raise ohmic_clear weight")
        elif pred == "ohmic" and user == "memristive":
            print("       → Raise memristive_penalty_no_switching or lower ohmic_clear weight")
        elif pred == "capacitive" and user == "memristive":
            print("       → Check capacitive_hysteresis_unpinched penalty (needs pinched check)")
        elif pred == "conductive" and user == "memristive":
            print("       → Consider raising memristive_nonlinear_iv weight")
        elif pred == "uncertain" and user in ("memristive", "ohmic", "conductive"):
            print(f"       → Lower UNCERTAIN_THRESHOLD (currently 40) — too many {user} falling through")
    if m["uncertain_errors"]:
        print(f"    2. {len(m['uncertain_errors'])} uncertain predictions had clear labels — lower UNCERTAIN_THRESHOLD")
    if m["disagreed"] > 0 and reviewed > 0 and (m["disagreed"] / reviewed) > 0.2:
        print(f"    3. Agreement rate {agree_rate} is below 80% — use classification_validation tool to tune weights")
        print(f"       python tools/classification_validation/launch_gui.py")

    print(SEP)


def _export_labeled_csv(labeled_rows: List[Dict], out_path: Path) -> None:
    if not labeled_rows:
        print(f"  No labeled rows to export.")
        return
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(labeled_rows[0].keys()))
        writer.writeheader()
        writer.writerows(labeled_rows)
    print(f"\n  Exported {len(labeled_rows)} labeled rows → {out_path}")
    print(f"  (Load into classification_validation tool: python tools/classification_validation/launch_gui.py)")


# ---------------------------------------------------------------------------
# Multi-dataset comparison
# ---------------------------------------------------------------------------

def _compare_datasets(datasets: List[str]) -> None:
    """Print a quick comparison table across all source datasets."""
    print(f"\n{SEP}")
    print("  CROSS-DATASET SUMMARY")
    print(SEP)
    print(f"  {'Dataset':<25} {'Reviewed':>9} {'Accuracy':>10} {'Top confusion':>30}")
    print(f"  {'-'*25} {'-'*9} {'-'*10} {'-'*30}")
    for ds in datasets:
        try:
            records, store = _load_dataset(ds)
            m = _build_metrics(_join(records, store))
            acc = _pct(m["agreed"], m["reviewed"])
            top = m["confusion"].most_common(1)
            top_str = f"{top[0][0][0]}→{top[0][0][1]}({top[0][1]})" if top else "-"
            print(f"  {ds:<25} {m['reviewed']:>9} {acc:>10} {top_str:>30}")
        except Exception as e:
            print(f"  {ds:<25} {'error':>9}  ({e})")
    print(SEP)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze review corrections vs auto-classification predictions."
    )
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()),
        default=DEFAULT_DATASET,
        help="Which dataset to analyse (default: %(default)s)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyse all datasets and print a comparison table",
    )
    parser.add_argument(
        "--export-csv",
        metavar="PATH",
        help="Export labeled subset to CSV for use with classification_validation tool",
    )
    args = parser.parse_args()

    if args.all:
        for ds in DATASETS:
            records, store = _load_dataset(ds)
            m = _build_metrics(_join(records, store))
            _print_report(m, ds)
        _compare_datasets(list(DATASETS.keys()))
        return

    records, store = _load_dataset(args.dataset)
    m = _build_metrics(_join(records, store))
    _print_report(m, args.dataset)

    if args.export_csv:
        _export_labeled_csv(m["labeled_rows"], Path(args.export_csv))


if __name__ == "__main__":
    main()
