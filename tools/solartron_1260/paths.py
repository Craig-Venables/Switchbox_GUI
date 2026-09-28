"""
Save-path helpers matching the main Sample GUI / PMU laser tool layout.

Layout:
  <Data_folder>/<Sample>/<Section>/<Device #>/Solartron_1260/<N>-<kind>_<timestamp>/
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

_TOOL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TOOL_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from gui.sample_gui.config import resolve_default_save_root
except Exception:  # pragma: no cover - standalone fallback

    def resolve_default_save_root() -> Path:
        return (
            Path.home()
            / "OneDrive - The University of Nottingham"
            / "Documents"
            / "Data_folder"
        )


DEFAULT_DATA_ROOT = resolve_default_save_root()
TEST_TYPE_FOLDER_NAME = "Solartron_1260"
SECTION_LETTERS = list("ABCDEFGHIJKL")
DEVICE_NUMBERS = [str(i) for i in range(1, 11)]
_OLD_DEFAULT_SAVE = Path.home() / "Documents" / "solartron_1260_data"


def sanitize_sample_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in (name or "").strip())
    cleaned = "_".join(cleaned.split())
    return cleaned or "untitled"


def sanitize_notes(notes: str) -> str:
    """Filesystem-safe run note, e.g. 'hrs after 55' -> 'hrs_after_55'."""
    cleaned = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in (notes or "").strip())
    cleaned = "_".join(cleaned.split())
    return cleaned


def discover_samples(save_root: Path) -> List[str]:
    """Existing sample folders under Data_folder, most-recent first."""
    root = Path(save_root)
    try:
        if not root.exists():
            return []
        dirs = [p for p in root.iterdir() if p.is_dir()]
        dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [p.name for p in dirs]
    except Exception:
        return []


def next_run_index(folder: Path) -> int:
    """Next N for folders named like '3-device_20260807_120000'."""
    best = 0
    if folder.exists():
        for p in folder.iterdir():
            if not p.is_dir():
                continue
            head = p.name.split("-", 1)[0]
            try:
                best = max(best, int(head))
            except ValueError:
                continue
    return best + 1


def device_leaf(
    save_root: Path,
    sample: str,
    section: str,
    device: str,
) -> Path:
    """<root>/<sample>/<section>/<device>/Solartron_1260"""
    return (
        Path(save_root)
        / sanitize_sample_name(sample)
        / (section.strip() or "A")
        / (device.strip() or "1")
        / TEST_TYPE_FOLDER_NAME
    )


def allocate_run_directory(
    save_root: Path,
    sample: str,
    section: str,
    device: str,
    *,
    kind: str = "device",
) -> Tuple[Path, int, str]:
    """
    Create the next run folder under the per-device Solartron leaf.

    Returns (run_dir, run_index, sample_sanitized).
    """
    leaf = device_leaf(save_root, sample, section, device)
    leaf.mkdir(parents=True, exist_ok=True)
    n = next_run_index(leaf)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kind = "".join(c if c.isalnum() or c in "-_" else "_" for c in kind) or "run"
    run_dir = leaf / f"{n}-{safe_kind}_{stamp}"
    (run_dir / "origin_data").mkdir(parents=True, exist_ok=True)
    (run_dir / "graphs").mkdir(parents=True, exist_ok=True)
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    return run_dir, n, sanitize_sample_name(sample)


def migrate_save_root(path: Optional[Path]) -> Path:
    """Prefer shared Data_folder; migrate away from old local default."""
    if path is None:
        return DEFAULT_DATA_ROOT
    try:
        if path.resolve() == _OLD_DEFAULT_SAVE.resolve():
            return DEFAULT_DATA_ROOT
    except Exception:
        pass
    return Path(path)
