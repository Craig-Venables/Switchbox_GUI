"""
Pulse Testing GUI configuration
==============================

Paths, config file names, and window constants. Keeps main and UI code free of magic strings.
"""

from pathlib import Path

# Project root (go up from gui/pulse_testing_gui/ to project root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
JSON_DIR = PROJECT_ROOT / "Json_Files"

# Config files
SAVE_LOCATION_CONFIG_FILE = JSON_DIR / "save_location_config.json"
TSP_GUI_CONFIG_FILE = JSON_DIR / "tsp_gui_config.json"
TSP_GUI_SAVE_CONFIG_FILE = JSON_DIR / "tsp_gui_save_config.json"
TSP_TEST_PRESETS_FILE = JSON_DIR / "tsp_test_presets.json"

# Window geometry
WINDOW_GEOMETRY = "1400x900"
HELP_WINDOW_GEOMETRY = "800x700"
RANGE_FINDER_POPUP_GEOMETRY = "700x600"
