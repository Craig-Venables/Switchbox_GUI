from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from .config import Thresholds


def load_thresholds(config_path: Path | None = None) -> Thresholds:
    base = Thresholds()
    if config_path is None:
        # default path at project root
        config_path = Path(__file__).resolve().parents[1] / "tests_settings.json"
    if not config_path.exists():
        return base
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return base

    # Only allow keys that exist in Thresholds
    valid_keys = set(asdict(base).keys())
    filtered: dict[str, Any] = {k: v for k, v in data.items() if k in valid_keys}

    # Convert lists to tuples for tuple fields
    for key in ("forming_voltages_v", "hyst_profiles", "retention_times_s"):
        if key in filtered and isinstance(filtered[key], list):
            filtered[key] = tuple(filtered[key])

    try:
        return replace(base, **filtered)
    except Exception:
        return base


def save_thresholds(thresholds: Thresholds, config_path: Path | None = None) -> None:
    if config_path is None:
        config_path = Path(__file__).resolve().parents[1] / "tests_settings.json"
    data = asdict(thresholds)
    # Convert tuples to lists for JSON
    for key in ("forming_voltages_v", "hyst_profiles", "retention_times_s"):
        if key in data and isinstance(data[key], tuple):
            data[key] = list(data[key])
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


