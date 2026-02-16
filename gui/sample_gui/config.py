"""
Sample GUI Configuration
========================

Sample types, multiplexer options, device mappings, and default save paths.
Extracted from main.py for maintainability.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# When frozen (PyInstaller), use bundle root so resources/Json_Files paths resolve
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _PROJECT_ROOT = Path(sys._MEIPASS)
else:
    _PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = _PROJECT_ROOT

sample_config: Dict[str, Any] = {
    "Cross_bar": {
        "sections": {
            "A": True, "B": True, "C": False, "D": True, "E": True, "F": False,
            "G": True, "H": True, "I": True, "J": False, "K": True, "L": True,
        },
        "devices": [str(i) for i in range(1, 11)],
    },
    "Device_Array_10": {
        "sections": {"A": True},
        "devices": [str(i) for i in range(1, 11)],
    },
    "15x15mm": {
        "sections": {"A": True, "B": True, "C": True, "D": True},
        "devices": [str(i) for i in range(1, 10)],
    },
}

multiplexer_types: Dict[str, Dict] = {"Pyswitchbox": {}, "Electronic_Mpx": {}, "Manual": {}}


def load_device_mapping(filename: Optional[str] = None) -> Dict[str, Any]:
    """Load device/pin mapping from JSON file."""
    try:
        mapping_path = (BASE_DIR / "Json_Files" / "pin_mapping.json") if filename is None else Path(filename)
        with mapping_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {mapping_path}.")
        return {}
    except json.JSONDecodeError:
        print("Error: JSON file is not formatted correctly.")
        return {}


pin_mapping: Dict[str, Any] = load_device_mapping()

with (BASE_DIR / "Json_Files" / "mapping.json").open("r", encoding="utf-8") as f:
    device_maps: Dict[str, Any] = json.load(f)


def resolve_default_save_root() -> Path:
    """
    Determine the default base directory for measurement data.

    Preference order:
    1. OneDrive commercial root (environment-provided) → Documents → Data_folder
    2. Explicit %USERPROFILE%/OneDrive - The University of Nottingham/Documents/Data_folder
    3. Local %USERPROFILE%/Documents/Data_folder

    The folder is created on demand.
    """
    home = Path.home()
    candidates: List[Path] = []

    for env_key in ("OneDriveCommercial", "OneDrive"):
        env_path = os.environ.get(env_key)
        if env_path:
            root = Path(env_path)
            candidates.append(root / "Documents")

    candidates.append(home / "OneDrive - The University of Nottingham" / "Documents")
    candidates.append(home / "Documents")

    for documents_path in candidates:
        try:
            root_exists = documents_path.parent.exists()
            if not root_exists:
                continue
            documents_path.mkdir(parents=True, exist_ok=True)
            target = documents_path / "Data_folder"
            target.mkdir(parents=True, exist_ok=True)
            return target
        except Exception:
            continue

    fallback = home / "Documents" / "Data_folder"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback
