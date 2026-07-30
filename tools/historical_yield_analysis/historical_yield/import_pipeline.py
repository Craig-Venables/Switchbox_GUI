"""Import / scan pipeline: discover workbooks, classify, write SQLite cache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .cache import YieldCache
from .classifiers import get_classifier
from .config import AppConfig
from .discovery import DiscoveredWorkbook, discover_workbooks, parse_discovered_sample
from .models import SampleMeta, WorkbookImportResult


ProgressFn = Callable[[str, float], None]


@dataclass
class ScanSummary:
    discovered: int = 0
    unchanged: int = 0
    imported: int = 0
    malformed: int = 0
    duplicates_rejected: int = 0
    parse_errors: int = 0
    accepted: int = 0
    warnings: List[str] = field(default_factory=list)
    results: List[WorkbookImportResult] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "discovered": self.discovered,
            "unchanged": self.unchanged,
            "imported": self.imported,
            "malformed": self.malformed,
            "duplicates_rejected": self.duplicates_rejected,
            "parse_errors": self.parse_errors,
            "accepted": self.accepted,
            "warnings": list(self.warnings),
        }


def _empty_sample(disc: DiscoveredWorkbook) -> SampleMeta:
    return SampleMeta(
        sample_id=disc.sample_id,
        sample_number=disc.sample_number,
        sample_name=disc.sample_name,
        material_hint=disc.material_hint,
    )


def import_workbook(
    disc: DiscoveredWorkbook,
    config: AppConfig,
    *,
    force: bool = False,
    cache: Optional[YieldCache] = None,
) -> WorkbookImportResult:
    """Classify one discovered workbook into a WorkbookImportResult (not yet deduped)."""
    try:
        sample = parse_discovered_sample(disc)
    except Exception as exc:
        sample = _empty_sample(disc)
        return WorkbookImportResult(
            source_path=str(disc.path.resolve()),
            root_name=disc.root.name,
            root_priority=disc.root.priority,
            sample=sample,
            fingerprint=disc.fingerprint,
            file_size=disc.file_size,
            mtime_ns=disc.mtime_ns,
            status="parse_error",
            warnings=[f"sample name parse failed: {exc}"],
            accepted=False,
        )

    if cache is not None and not force:
        existing_fp = cache.get_fingerprint(str(disc.path.resolve()))
        if existing_fp == disc.fingerprint:
            # Return a lightweight unchanged marker; caller may skip upsert
            return WorkbookImportResult(
                source_path=str(disc.path.resolve()),
                root_name=disc.root.name,
                root_priority=disc.root.priority,
                sample=sample,
                fingerprint=disc.fingerprint,
                file_size=disc.file_size,
                mtime_ns=disc.mtime_ns,
                status="unchanged",
                accepted=True,
            )

    classifier = get_classifier(config.classifier)
    try:
        clf = classifier.classify(
            str(disc.path),
            sample,
            success_categories=config.yield_success_categories,
        )
        status = "ok"
        if not clf.devices:
            # still ok but warn
            clf.warnings.append("workbook produced zero device rows")
        return WorkbookImportResult(
            source_path=str(disc.path.resolve()),
            root_name=disc.root.name,
            root_priority=disc.root.priority,
            sample=clf.sample,
            fingerprint=disc.fingerprint,
            file_size=disc.file_size,
            mtime_ns=disc.mtime_ns,
            status=status,
            devices=clf.devices,
            warnings=list(clf.warnings),
            schema_header=clf.schema_header,
            classifier_id=clf.classifier_id,
            classifier_version=clf.classifier_version,
            accepted=True,
        )
    except Exception as exc:
        return WorkbookImportResult(
            source_path=str(disc.path.resolve()),
            root_name=disc.root.name,
            root_priority=disc.root.priority,
            sample=sample,
            fingerprint=disc.fingerprint,
            file_size=disc.file_size,
            mtime_ns=disc.mtime_ns,
            status="malformed",
            warnings=[str(exc)],
            accepted=False,
            classifier_id=classifier.classifier_id,
            classifier_version=classifier.classifier_version,
        )


def resolve_duplicates(results: List[WorkbookImportResult]) -> List[WorkbookImportResult]:
    """
    Prefer lower root_priority for the same sample_id.
    On ties, prefer lexicographically greater source_path mtime already encoded
    by keeping the first after sorting by (sample_number, priority, -mtime).
    """
    by_sample: Dict[str, List[WorkbookImportResult]] = {}
    for r in results:
        if r.status == "unchanged":
            by_sample.setdefault(r.sample.sample_id, []).append(r)
            continue
        by_sample.setdefault(r.sample.sample_id, []).append(r)

    resolved: List[WorkbookImportResult] = []
    for sample_id, group in by_sample.items():
        # Only consider candidates that aren't parse-fatal for winning,
        # but still record all.
        candidates = [g for g in group if g.status in {"ok", "unchanged"}]
        others = [g for g in group if g.status not in {"ok", "unchanged"}]
        if not candidates:
            for g in others:
                g.accepted = False
                resolved.append(g)
            continue
        candidates.sort(key=lambda r: (r.root_priority, -r.mtime_ns, r.source_path))
        winner = candidates[0]
        winner.accepted = True
        if winner.status != "unchanged":
            # keep status
            pass
        resolved.append(winner)
        for loser in candidates[1:]:
            loser.accepted = False
            loser.status = "duplicate_rejected"
            loser.duplicate_of = winner.source_path
            loser.warnings = list(loser.warnings) + [
                f"duplicate of preferred workbook for {sample_id}: {winner.source_path}"
            ]
            resolved.append(loser)
        for g in others:
            g.accepted = False
            resolved.append(g)
    return resolved


def scan_and_update_cache(
    config: AppConfig,
    *,
    rebuild: bool = False,
    progress: Optional[ProgressFn] = None,
) -> ScanSummary:
    """Discover workbooks and update the SQLite cache.

    rebuild=True clears the cache first and re-imports everything.
    Otherwise only new/changed fingerprints are re-parsed.
    """
    cache = YieldCache(config.sqlite_path)
    if rebuild:
        cache.clear()
        cache.log_event("rebuild_started", {"sqlite": str(config.sqlite_path)})

    if progress:
        progress("Discovering workbooks…", 0.0)

    discovered = discover_workbooks(config)
    summary = ScanSummary(discovered=len(discovered))

    raw_results: List[WorkbookImportResult] = []
    total = max(len(discovered), 1)
    for i, disc in enumerate(discovered):
        if progress:
            progress(f"Importing {disc.path.name}", (i + 0.5) / total)
        result = import_workbook(disc, config, force=rebuild, cache=cache)
        raw_results.append(result)

    # Separate unchanged vs needing write
    to_resolve = [r for r in raw_results if r.status != "unchanged"]
    unchanged = [r for r in raw_results if r.status == "unchanged"]
    summary.unchanged = len(unchanged)

    resolved = resolve_duplicates(to_resolve)

    # For unchanged files, still need duplicate policy if a better root appeared.
    # Re-evaluate acceptance among all accepted paths including unchanged.
    # Strategy: load current accepted map, merge with new resolved winners.
    if not rebuild and unchanged:
        # Ensure unchanged rows remain unless a better-priority import of same sample arrived
        winners_by_sample = {
            r.sample.sample_id: r
            for r in resolved
            if r.accepted and r.status == "ok"
        }
        for u in unchanged:
            better = winners_by_sample.get(u.sample.sample_id)
            if better is not None and (
                better.root_priority < u.root_priority
                or (
                    better.root_priority == u.root_priority
                    and better.mtime_ns > u.mtime_ns
                )
            ):
                # demote unchanged duplicate in DB
                cache.delete_workbook(u.source_path)
                u.accepted = False
                u.status = "duplicate_rejected"
                u.duplicate_of = better.source_path
                resolved.append(u)
            else:
                # keep existing cache row; if a worse new duplicate arrived it is already rejected
                summary.accepted += 1

    for r in resolved:
        if r.status == "unchanged":
            continue
        cache.upsert_workbook(r)
        if r.status == "ok" and r.accepted:
            summary.imported += 1
            summary.accepted += 1
        elif r.status == "duplicate_rejected":
            summary.duplicates_rejected += 1
        elif r.status == "malformed":
            summary.malformed += 1
        elif r.status == "parse_error":
            summary.parse_errors += 1
        summary.results.append(r)
        for w in r.warnings:
            if w not in summary.warnings:
                summary.warnings.append(w)

    # After incremental import, re-assert single accepted workbook per sample_id
    _enforce_single_winner(cache)

    stats = cache.stats()
    summary.accepted = stats["workbooks_accepted"]
    cache.log_event(
        "scan_completed",
        {"rebuild": rebuild, "summary": summary.as_dict(), "stats": stats},
    )
    if progress:
        progress("Scan complete", 1.0)
    return summary


def _enforce_single_winner(cache: YieldCache) -> None:
    """Ensure only the best-priority workbook per sample_id is accepted."""
    rows = cache.list_all_workbooks()
    by_sample: Dict[str, list] = {}
    for row in rows:
        if row["status"] not in {"ok", "unchanged"} and not row["accepted"]:
            # still group ok ones
            pass
        by_sample.setdefault(row["sample_id"], []).append(row)

    for sample_id, group in by_sample.items():
        okish = [g for g in group if g["status"] == "ok" or g["accepted"]]
        if len(okish) <= 1:
            continue
        okish.sort(key=lambda r: (r["root_priority"], -r["mtime_ns"], r["source_path"]))
        winner = okish[0]
        for loser in okish[1:]:
            with cache.connect() as conn:
                conn.execute(
                    """
                    UPDATE workbooks
                    SET accepted = 0, status = 'duplicate_rejected', duplicate_of = ?
                    WHERE id = ?
                    """,
                    (winner["source_path"], loser["id"]),
                )
        with cache.connect() as conn:
            conn.execute(
                "UPDATE workbooks SET accepted = 1, status = 'ok', duplicate_of = NULL WHERE id = ?",
                (winner["id"],),
            )
