"""
Pulse Testing GUI configuration
==============================

Paths, config file names, and window constants. Keeps main and UI code free of magic strings.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


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
HELP_WINDOW_GEOMETRY = "800x700"
RANGE_FINDER_POPUP_GEOMETRY = "700x600"
