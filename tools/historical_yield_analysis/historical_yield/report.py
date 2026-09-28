"""Build timestamped report bundles from the cache."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from .analysis import device_dataframe, filter_samples, quality_report, sample_dataframe
from .cache import YieldCache
from .config import AppConfig
from .fabrication import get_fabrication_index
from .missing_excel import find_missing_excel, missing_excel_dataframe
from .origin_export import export_origin_txt
from .plots import generate_all_plots


LogFn = Callable[[str], None]


@dataclass
class ReportResult:
    output_dir: Path
    sample_csv: Path
    device_csv: Path
    quality_csv: Path
    plot_paths: List[Path]
    config_snapshot: Path
    manifest: Path
    origin_paths: List[Path] = field(default_factory=list)
    missing_excel_csv: Optional[Path] = None


def make_report_dir(output_root: Path, stamp: Optional[str] = None) -> Path:
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_root / f"report_{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_report(
    config: AppConfig,
    *,
    sample_ids: Optional[Sequence[str]] = None,
    polymers: Optional[Sequence[str]] = None,
    bottom_electrodes: Optional[Sequence[str]] = None,
    top_electrodes: Optional[Sequence[str]] = None,
    polymer_percents: Optional[Sequence[float]] = None,
    np_types: Optional[Sequence[str]] = None,
    min_sample_number: Optional[int] = None,
    max_sample_number: Optional[int] = None,
    formats: Sequence[str] = ("png", "svg", "pdf"),
    log_fn: LogFn = print,
) -> ReportResult:
    cache = YieldCache(config.sqlite_path)
    out = make_report_dir(config.output_dir)
    plots_dir = out / "plots"
    plots_dir.mkdir(exist_ok=True)
    origin_dir = out / "origin"
    origin_dir.mkdir(exist_ok=True)

    log_fn(f"[report] writing to {out}")
    fab_index = get_fabrication_index(
        config.fabrication_workbook, config.fabrication_sheet
    )
    devices = device_dataframe(cache)
    samples = sample_dataframe(cache, fab_index=fab_index)
    samples = filter_samples(
        samples,
        sample_ids=sample_ids,
        polymers=polymers,
        bottom_electrodes=bottom_electrodes,
        top_electrodes=top_electrodes,
        polymer_percents=polymer_percents,
        np_types=np_types,
        min_sample_number=min_sample_number,
        max_sample_number=max_sample_number,
    )
    keep = set(samples["sample_id"].tolist()) if not samples.empty else set()
    if sample_ids is not None or polymers is not None or keep:
        if not devices.empty and keep:
            devices = devices[devices["sample_id"].isin(keep)].reset_index(drop=True)

    sample_csv = out / "sample_summary.csv"
    device_csv = out / "device_detail.csv"
    quality_csv = out / "quality_report.csv"
    samples.to_csv(sample_csv, index=False)
    devices.to_csv(device_csv, index=False)
    quality = quality_report(cache)
    quality.to_csv(quality_csv, index=False)

    missing = find_missing_excel(config, fab_index=fab_index)
    missing_df = missing_excel_dataframe(missing)
    missing_csv = out / "missing_classification_excel.csv"
    missing_df.to_csv(missing_csv, index=False)

    config_snapshot = out / "config_snapshot.json"
    config_snapshot.write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")

    plot_paths = generate_all_plots(samples, plots_dir, formats=formats, log_fn=log_fn)
    origin_paths = export_origin_txt(samples, origin_dir)
    log_fn(f"[report] Origin TXT: {len(origin_paths)} files")

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sqlite": str(config.sqlite_path),
        "n_samples": int(len(samples)),
        "n_devices": int(len(devices)),
        "n_missing_excel": int(len(missing_df)),
        "fab_rows_loaded": int(fab_index.n_rows),
        "cache_stats": cache.stats(),
        "filters": {
            "sample_ids": list(sample_ids) if sample_ids is not None else None,
            "polymers": list(polymers) if polymers is not None else None,
            "bottom_electrodes": list(bottom_electrodes) if bottom_electrodes else None,
            "top_electrodes": list(top_electrodes) if top_electrodes else None,
            "polymer_percents": list(polymer_percents) if polymer_percents else None,
            "np_types": list(np_types) if np_types else None,
            "min_sample_number": min_sample_number,
            "max_sample_number": max_sample_number,
        },
        "yield_definition": (
            "strict_yield = count(normalized==memristive) / count(is_classified); "
            "blank/unclassified rows excluded from denominator"
        ),
        "files": {
            "sample_csv": sample_csv.name,
            "device_csv": device_csv.name,
            "quality_csv": quality_csv.name,
            "missing_excel_csv": missing_csv.name,
            "plots": [str(p.relative_to(out)) for p in plot_paths],
            "origin": [str(p.relative_to(out)) for p in origin_paths],
        },
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    latest = config.output_dir / "latest_sample_summary.csv"
    try:
        shutil.copy2(sample_csv, latest)
    except OSError:
        pass

    log_fn(f"[report] complete — {len(samples)} samples, {len(plot_paths)} plot files")
    return ReportResult(
        output_dir=out,
        sample_csv=sample_csv,
        device_csv=device_csv,
        quality_csv=quality_csv,
        plot_paths=plot_paths,
        config_snapshot=config_snapshot,
        manifest=manifest_path,
        origin_paths=origin_paths,
        missing_excel_csv=missing_csv,
    )
