"""Yield and composition calculations from the SQLite cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import pandas as pd

from .cache import YieldCache
from .fabrication import FabricationIndex, enrich_sample_row, get_fabrication_index
from .models import CATEGORY_DISPLAY, CANONICAL_CATEGORIES, SampleYieldSummary


def device_dataframe(cache: YieldCache) -> pd.DataFrame:
    rows = cache.list_devices_for_accepted()
    if not rows:
        return pd.DataFrame(
            columns=[
                "sample_id",
                "sample_number",
                "sample_name",
                "section",
                "device_number",
                "raw_classification",
                "normalized_classification",
                "is_classified",
                "is_yield_success",
                "concentration_mgml",
                "is_stock",
                "polymer",
                "bottom_electrode",
                "top_electrode",
                "source_path",
                "root_name",
            ]
        )
    records = []
    for r in rows:
        records.append(
            {
                "sample_id": r["sample_id"],
                "sample_number": r["sample_number"],
                "sample_name": r["sample_name"],
                "section": r["section"],
                "device_number": r["device_number"],
                "raw_classification": r["raw_classification"],
                "normalized_classification": r["normalized_classification"],
                "is_classified": bool(r["is_classified"]),
                "is_yield_success": bool(r["is_yield_success"]),
                "memristor_strength": r["memristor_strength"],
                "concentration_mgml": r["concentration_mgml"],
                "is_stock": bool(r["is_stock"]),
                "polymer": r["polymer"],
                "bottom_electrode": r["bottom_electrode"],
                "top_electrode": r["top_electrode"],
                "material_hint": r["material_hint"],
                "source_path": r["source_path"],
                "root_name": r["root_name"],
                "display_classification": CATEGORY_DISPLAY.get(
                    r["normalized_classification"], r["normalized_classification"]
                ),
            }
        )
    return pd.DataFrame.from_records(records)


def summarize_sample_devices(
    sample_id: str,
    devices: pd.DataFrame,
    workbook_meta: Optional[Dict[str, Any]] = None,
) -> SampleYieldSummary:
    meta = workbook_meta or {}
    n_rows = len(devices)
    classified = devices[devices["is_classified"]] if n_rows else devices
    n_classified = int(classified.shape[0])
    n_blank = n_rows - n_classified

    def _count(cat: str) -> int:
        if n_classified == 0:
            return 0
        return int((classified["normalized_classification"] == cat).sum())

    counts = {cat: _count(cat) for cat in CANONICAL_CATEGORIES}
    n_memristive = counts["memristive"]
    strict_yield = (n_memristive / n_classified) if n_classified else 0.0
    composition = {
        cat: ((counts[cat] / n_classified) if n_classified else 0.0)
        for cat in CANONICAL_CATEGORIES
        if cat not in {"unknown"}
    }
    composition["unknown"] = (counts["unknown"] / n_classified) if n_classified else 0.0

    return SampleYieldSummary(
        sample_id=sample_id,
        sample_number=int(meta.get("sample_number") or devices["sample_number"].iloc[0]),
        sample_name=str(meta.get("sample_name") or devices["sample_name"].iloc[0]),
        n_device_rows=n_rows,
        n_classified=n_classified,
        n_blank=n_blank,
        n_memristive=counts["memristive"],
        n_ohmic=counts["ohmic"],
        n_capacitive=counts["capacitive"],
        n_conductive=counts["conductive"],
        n_non_conductive=counts["non_conductive"],
        n_mem_capacitive=counts["mem_capacitive"],
        n_intermittent=counts["intermittent"],
        n_other=counts["other"],
        strict_yield=float(strict_yield),
        composition=composition,
        concentration_mgml=meta.get(
            "concentration_mgml",
            devices["concentration_mgml"].iloc[0] if n_rows else None,
        ),
        is_stock=bool(meta.get("is_stock", devices["is_stock"].iloc[0] if n_rows else False)),
        polymer=meta.get("polymer", devices["polymer"].iloc[0] if n_rows else None),
        bottom_electrode=meta.get(
            "bottom_electrode", devices["bottom_electrode"].iloc[0] if n_rows else None
        ),
        top_electrode=meta.get(
            "top_electrode", devices["top_electrode"].iloc[0] if n_rows else None
        ),
        source_path=str(meta.get("source_path") or devices["source_path"].iloc[0]),
        root_name=str(meta.get("root_name") or devices["root_name"].iloc[0]),
    )


def sample_dataframe(
    cache: YieldCache,
    fab_index: Optional[FabricationIndex] = None,
    *,
    fabrication_workbook: Optional[Union[str, Path]] = None,
    fabrication_sheet: str = "Memristor Devices",
) -> pd.DataFrame:
    devices = device_dataframe(cache)
    workbooks = cache.list_accepted_workbooks()
    meta_by_id = {w["sample_id"]: dict(w) for w in workbooks}
    if devices.empty and not workbooks:
        return pd.DataFrame()

    if fab_index is None and fabrication_workbook:
        fab_index = get_fabrication_index(fabrication_workbook, fabrication_sheet)

    summaries: List[SampleYieldSummary] = []
    sample_ids = [w["sample_id"] for w in workbooks]
    for sid in sample_ids:
        subset = devices[devices["sample_id"] == sid] if not devices.empty else devices
        if subset.empty:
            w = meta_by_id[sid]
            summaries.append(
                SampleYieldSummary(
                    sample_id=sid,
                    sample_number=int(w["sample_number"]),
                    sample_name=str(w["sample_name"]),
                    n_device_rows=0,
                    n_classified=0,
                    n_blank=0,
                    n_memristive=0,
                    n_ohmic=0,
                    n_capacitive=0,
                    n_conductive=0,
                    n_non_conductive=0,
                    n_mem_capacitive=0,
                    n_intermittent=0,
                    n_other=0,
                    strict_yield=0.0,
                    composition={c: 0.0 for c in CANONICAL_CATEGORIES},
                    concentration_mgml=w["concentration_mgml"],
                    is_stock=bool(w["is_stock"]),
                    polymer=w["polymer"],
                    bottom_electrode=w["bottom_electrode"],
                    top_electrode=w["top_electrode"],
                    source_path=w["source_path"],
                    root_name=w["root_name"],
                    warnings=["no device rows"],
                )
            )
            continue
        summaries.append(summarize_sample_devices(sid, subset, meta_by_id.get(sid)))

    records = []
    for s in summaries:
        row = {
            "sample_id": s.sample_id,
            "sample_number": s.sample_number,
            "sample_name": s.sample_name,
            "n_device_rows": s.n_device_rows,
            "n_classified": s.n_classified,
            "n_blank": s.n_blank,
            "n_memristive": s.n_memristive,
            "n_ohmic": s.n_ohmic,
            "n_capacitive": s.n_capacitive,
            "n_conductive": s.n_conductive,
            "n_non_conductive": s.n_non_conductive,
            "n_mem_capacitive": s.n_mem_capacitive,
            "n_intermittent": s.n_intermittent,
            "n_other": s.n_other,
            "strict_yield": s.strict_yield,
            "strict_yield_pct": s.strict_yield * 100.0,
            "concentration_mgml": s.concentration_mgml,
            "is_stock": s.is_stock,
            "polymer": s.polymer,
            "bottom_electrode": s.bottom_electrode,
            "top_electrode": s.top_electrode,
            "source_path": s.source_path,
            "root_name": s.root_name,
            "polymer_percent": None,
            "np_type": None,
            "date_made": None,
            "has_fab_row": False,
        }
        for cat, frac in s.composition.items():
            row[f"frac_{cat}"] = frac
            row[f"pct_{cat}"] = frac * 100.0
        fab = None
        if fab_index is not None:
            fab = fab_index.lookup(
                sample_number=s.sample_number,
                sample_id=s.sample_id,
                device_full_name=s.sample_name,
            )
        row = enrich_sample_row(row, fab)
        records.append(row)

    df = pd.DataFrame.from_records(records)
    if not df.empty:
        df = df.sort_values("sample_number").reset_index(drop=True)
    return df


def filter_samples(
    sample_df: pd.DataFrame,
    *,
    sample_ids: Optional[Sequence[str]] = None,
    polymers: Optional[Sequence[str]] = None,
    bottom_electrodes: Optional[Sequence[str]] = None,
    top_electrodes: Optional[Sequence[str]] = None,
    polymer_percents: Optional[Sequence[float]] = None,
    np_types: Optional[Sequence[str]] = None,
    min_sample_number: Optional[int] = None,
    max_sample_number: Optional[int] = None,
) -> pd.DataFrame:
    df = sample_df.copy()
    if df.empty:
        return df
    if sample_ids is not None:
        df = df[df["sample_id"].isin(sample_ids)]
    if polymers is not None:
        df = df[df["polymer"].isin(polymers)]
    if bottom_electrodes is not None and "bottom_electrode" in df.columns:
        df = df[df["bottom_electrode"].isin(bottom_electrodes)]
    if top_electrodes is not None and "top_electrode" in df.columns:
        df = df[df["top_electrode"].isin(top_electrodes)]
    if polymer_percents is not None and "polymer_percent" in df.columns:
        allowed = {float(x) for x in polymer_percents}
        df = df[
            df["polymer_percent"].apply(
                lambda v: v is not None and not pd.isna(v) and float(v) in allowed
            )
        ]
    if np_types is not None and "np_type" in df.columns:
        df = df[df["np_type"].isin(np_types)]
    if min_sample_number is not None:
        df = df[df["sample_number"] >= min_sample_number]
    if max_sample_number is not None:
        df = df[df["sample_number"] <= max_sample_number]
    return df.reset_index(drop=True)


def quality_report(cache: YieldCache) -> pd.DataFrame:
    rows = cache.list_all_workbooks()
    records = []
    for r in rows:
        import json

        warnings = json.loads(r["warnings_json"] or "[]")
        records.append(
            {
                "sample_id": r["sample_id"],
                "sample_number": r["sample_number"],
                "sample_name": r["sample_name"],
                "status": r["status"],
                "accepted": bool(r["accepted"]),
                "root_name": r["root_name"],
                "root_priority": r["root_priority"],
                "duplicate_of": r["duplicate_of"],
                "source_path": r["source_path"],
                "warnings": "; ".join(warnings),
                "schema_header": r["schema_header"],
            }
        )
    return pd.DataFrame.from_records(records)
