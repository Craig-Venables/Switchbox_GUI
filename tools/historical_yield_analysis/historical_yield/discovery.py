"""Discover classification Excel workbooks under configured data roots."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Set

from .config import AppConfig, DataRoot
from .parse_sample import extract_sample_id, material_hint_from_path, parse_sample_name


EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}


@dataclass
class DiscoveredWorkbook:
    path: Path
    root: DataRoot
    sample_id: str
    sample_number: int
    sample_name: str
    fingerprint: str
    file_size: int
    mtime_ns: int
    material_hint: Optional[str] = None


def file_fingerprint(path: Path) -> tuple[str, int, int]:
    """Return (fingerprint, size, mtime_ns) based on size + mtime (fast, no content hash)."""
    st = path.stat()
    size = int(st.st_size)
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    raw = f"{path.resolve()}|{size}|{mtime_ns}".encode("utf-8", errors="replace")
    return hashlib.sha1(raw).hexdigest(), size, mtime_ns


def should_skip_workbook(path: Path, exclude_names: Iterable[str]) -> bool:
    name = path.name.lower()
    if name.startswith("~$"):
        return True
    exclude = {n.lower() for n in exclude_names}
    if name in exclude:
        return True
    # skip bare device_status without sample id
    if name.startswith("device_status"):
        return True
    return False


def discover_workbooks(config: AppConfig) -> List[DiscoveredWorkbook]:
    found: List[DiscoveredWorkbook] = []
    for root in config.enabled_roots():
        found.extend(discover_in_root(root, config.exclude_workbook_names))
    return found


def discover_in_root(root: DataRoot, exclude_names: Iterable[str]) -> List[DiscoveredWorkbook]:
    if not root.path.exists():
        return []
    results: List[DiscoveredWorkbook] = []
    seen: Set[str] = set()
    for path in _iter_excel(root.path):
        if should_skip_workbook(path, exclude_names):
            continue
        # Require the workbook filename itself to contain D# — skip templates
        # / side-car sheets that merely live inside a sample folder.
        sid = extract_sample_id(path.stem)
        if sid is None:
            continue
        sample_id, sample_number = sid
        # Prefer full sample folder name when it matches the same D#
        sample_name = path.stem
        parent_sid = extract_sample_id(path.parent.name)
        if parent_sid and parent_sid[0] == sample_id and path.parent.name.lower().startswith("d"):
            sample_name = path.parent.name
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            fp, size, mtime_ns = file_fingerprint(path)
        except OSError:
            continue
        results.append(
            DiscoveredWorkbook(
                path=path,
                root=root,
                sample_id=sample_id,
                sample_number=sample_number,
                sample_name=sample_name,
                fingerprint=fp,
                file_size=size,
                mtime_ns=mtime_ns,
                material_hint=material_hint_from_path(str(path)),
            )
        )
    return results


def _iter_excel(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in EXCEL_SUFFIXES:
            yield path


def parse_discovered_sample(disc: DiscoveredWorkbook):
    return parse_sample_name(disc.sample_name, material_hint=disc.material_hint)
