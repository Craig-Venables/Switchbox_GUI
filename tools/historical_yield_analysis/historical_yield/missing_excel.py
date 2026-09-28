"""Discover Dxx sample folders missing a classification Excel workbook."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import AppConfig, DataRoot
from .fabrication import FabricationIndex
from .parse_sample import extract_sample_id


# Folder must START with D + digits (e.g. D95-0.1mgml-...)
_DXX_FOLDER_RE = re.compile(r"(?i)^D(\d+)")


@dataclass
class MissingExcelEntry:
    sample_id: str
    sample_number: int
    folder_name: str
    folder_path: str
    root_name: str
    root_priority: int
    has_fab_row: bool
    preferred: bool = True  # surviving after duplicate resolution

    def to_dict(self) -> dict:
        return asdict(self)


def is_dxx_sample_folder(name: str) -> bool:
    return bool(_DXX_FOLDER_RE.match(name.strip()))


def folder_has_classification_excel(folder: Path, sample_id: str) -> bool:
    """True if folder contains a classification .xlsx for this sample ID."""
    exact = folder / f"{folder.name}.xlsx"
    if exact.exists() and not exact.name.startswith("~$"):
        return True
    for path in folder.glob("*.xlsx"):
        if path.name.startswith("~$"):
            continue
        lower = path.name.lower()
        if lower.startswith("device_status"):
            continue
        sid = extract_sample_id(path.stem)
        if sid and sid[0] == sample_id:
            return True
    return False


def discover_dxx_sample_folders(root: DataRoot) -> List[tuple[Path, str, int]]:
    """Return sample folders without walking their large raw-data subtrees."""
    if not root.path.exists():
        return []
    found: List[tuple[Path, str, int]] = []
    seen: set[str] = set()
    # topdown=True lets us prune a Dxx sample as soon as it is found. The
    # previous Path.rglob implementation descended into ~98k raw files and
    # blocked GUI startup.
    for current, dirnames, _filenames in os.walk(root.path, topdown=True):
        sample_dirnames: List[str] = []
        for dirname in dirnames:
            if is_dxx_sample_folder(dirname):
                sample_dirnames.append(dirname)

        for dirname in sample_dirnames:
            path = Path(current) / dirname
            match = _DXX_FOLDER_RE.match(dirname)
            if not match:
                continue
            sample_number = int(match.group(1))
            sample_id = f"D{sample_number}"
            key = os.path.normcase(os.path.abspath(path))
            if key in seen:
                continue
            seen.add(key)
            found.append((path, sample_id, sample_number))

        # Never descend into sample folders: only their top-level workbook is
        # relevant to this checklist.
        dirnames[:] = [d for d in dirnames if d not in sample_dirnames]
    return found


def find_missing_excel(
    config: AppConfig,
    fab_index: Optional[FabricationIndex] = None,
) -> List[MissingExcelEntry]:
    """
    Find Dxx sample folders that lack a matching classification workbook.

    Deduplicates by sample_id using root priority (lower wins); only the
    preferred folder per sample_id is marked preferred=True. All missing
    folders are returned; duplicates are listed with preferred=False.
    """
    raw: List[MissingExcelEntry] = []
    for root in config.enabled_roots():
        for folder, sample_id, sample_number in discover_dxx_sample_folders(root):
            if folder_has_classification_excel(folder, sample_id):
                continue
            has_fab = False
            if fab_index is not None:
                has_fab = fab_index.has_sample(sample_id)
            raw.append(
                MissingExcelEntry(
                    sample_id=sample_id,
                    sample_number=sample_number,
                    folder_name=folder.name,
                    folder_path=str(folder.resolve()),
                    root_name=root.name,
                    root_priority=root.priority,
                    has_fab_row=has_fab,
                    preferred=True,
                )
            )

    by_sample: Dict[str, List[MissingExcelEntry]] = {}
    for entry in raw:
        by_sample.setdefault(entry.sample_id, []).append(entry)

    resolved: List[MissingExcelEntry] = []
    for sample_id, group in by_sample.items():
        group.sort(key=lambda e: (e.root_priority, e.folder_path))
        group[0].preferred = True
        for loser in group[1:]:
            loser.preferred = False
        resolved.extend(group)

    resolved.sort(key=lambda e: (e.sample_number, e.root_priority, e.folder_path))
    return resolved


def missing_excel_dataframe(entries: Iterable[MissingExcelEntry]):
    import pandas as pd

    rows = [e.to_dict() for e in entries]
    if not rows:
        return pd.DataFrame(
            columns=[
                "sample_id",
                "sample_number",
                "folder_name",
                "folder_path",
                "root_name",
                "root_priority",
                "has_fab_row",
                "preferred",
            ]
        )
    return pd.DataFrame.from_records(rows)
