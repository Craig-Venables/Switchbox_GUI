"""
Pulse Testing GUI configuration
==============================

Paths, config file names, and window constants. Keeps main and UI code free of magic strings.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Literal, Optional


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _ensure_json_configs() -> None:
    """Seed editable Json_Files next to the executable from the PyInstaller bundle."""
    if not getattr(sys, "frozen", False):
        return
    bundle_json = _bundle_root() / "Json_Files"
    if not bundle_json.is_dir():
        return
    json_dir = _app_root() / "Json_Files"
    json_dir.mkdir(parents=True, exist_ok=True)
    for src in bundle_json.iterdir():
        if src.is_file():
            dest = json_dir / src.name
            if not dest.exists():
                shutil.copy2(src, dest)


# Writable project root (next to exe when frozen; repo root in dev)
PROJECT_ROOT = _app_root()
JSON_DIR = PROJECT_ROOT / "Json_Files"

_ensure_json_configs()

# Config files
SAVE_LOCATION_CONFIG_FILE = JSON_DIR / "save_location_config.json"
TSP_GUI_CONFIG_FILE = JSON_DIR / "tsp_gui_config.json"
TSP_GUI_SAVE_CONFIG_FILE = JSON_DIR / "tsp_gui_save_config.json"
TSP_TEST_PRESETS_FILE = JSON_DIR / "tsp_test_presets.json"

# Window geometry
WINDOW_GEOMETRY = "1400x900"
HELP_WINDOW_GEOMETRY = "820x780"
RANGE_FINDER_POPUP_GEOMETRY = "700x600"

# UI layout modes: "classic" (default) or "compact"
LayoutMode = Literal["classic", "compact"]
DEFAULT_LAYOUT: LayoutMode = "classic"
VALID_LAYOUTS = frozenset({"classic", "compact"})


def load_layout_preference() -> LayoutMode:
    """Read layout mode from tsp_gui_config.json (default classic)."""
    try:
        if TSP_GUI_CONFIG_FILE.is_file():
            with open(TSP_GUI_CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            layout = str(data.get("layout", DEFAULT_LAYOUT)).strip().lower()
            if layout in VALID_LAYOUTS:
                return layout  # type: ignore[return-value]
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return DEFAULT_LAYOUT


def resolve_layout(
    explicit: Optional[str] = None,
    cli: Optional[str] = None,
) -> LayoutMode:
    """Priority: explicit kwarg → CLI → config file → default."""
    for candidate in (explicit, cli):
        if candidate is not None:
            value = str(candidate).strip().lower()
            if value in VALID_LAYOUTS:
                return value  # type: ignore[return-value]
    return load_layout_preference()


def resolve_pulse_testing_save_base(sample_name: Optional[str] = None) -> Path:
    """
    Default save root for standalone Pulse Testing (matches other GUIs' Data_folder).

    Structure: Documents/Data_folder/Pulse_Testing/{sample_name}/…
    Device subfolders (e.g. A/1/Pulse_measurements) are added by FileNamer on save.
    """
    from gui.sample_gui.config import resolve_default_save_root

    name = (sample_name or "").strip() or "UnknownSample"
    base = resolve_default_save_root() / "Pulse_Testing" / name
    base.mkdir(parents=True, exist_ok=True)
    return base
