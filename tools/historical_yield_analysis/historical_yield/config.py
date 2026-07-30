"""Configuration loading for historical yield analysis."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional


TOOL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_NAME = "config.json"
EXAMPLE_CONFIG_NAME = "config.example.json"


@dataclass
class DataRoot:
    name: str
    path: Path
    priority: int
    enabled: bool = True


@dataclass
class AppConfig:
    data_roots: List[DataRoot] = field(default_factory=list)
    cache_dir: Path = field(default_factory=lambda: TOOL_ROOT / "cache")
    output_dir: Path = field(default_factory=lambda: TOOL_ROOT / "output")
    classifier: str = "manual_excel"
    yield_success_categories: List[str] = field(default_factory=lambda: ["memristive"])
    exclude_workbook_names: List[str] = field(
        default_factory=lambda: ["device_status.xlsx", "device_status.xls"]
    )
    fabrication_workbook: Optional[Path] = None
    fabrication_sheet: str = "Memristor Devices"
    config_path: Optional[Path] = None

    @property
    def sqlite_path(self) -> Path:
        return self.cache_dir / "historical_yield.sqlite"

    def enabled_roots(self) -> List[DataRoot]:
        return sorted(
            [r for r in self.data_roots if r.enabled],
            key=lambda r: (r.priority, r.name),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_roots": [
                {
                    "name": r.name,
                    "path": str(r.path),
                    "priority": r.priority,
                    "enabled": r.enabled,
                }
                for r in self.data_roots
            ],
            "cache_dir": _rel_or_abs(self.cache_dir),
            "output_dir": _rel_or_abs(self.output_dir),
            "classifier": self.classifier,
            "yield_success_categories": list(self.yield_success_categories),
            "exclude_workbook_names": list(self.exclude_workbook_names),
            "fabrication_workbook": (
                str(self.fabrication_workbook) if self.fabrication_workbook else None
            ),
            "fabrication_sheet": self.fabrication_sheet,
        }


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.relative_to(TOOL_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _resolve_path(value: str | Path, base: Path = TOOL_ROOT) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = base / p
    return p.resolve()


def ensure_config_file(config_path: Optional[Path] = None) -> Path:
    """Copy example config to config.json if missing; return path used."""
    path = Path(config_path) if config_path else TOOL_ROOT / DEFAULT_CONFIG_NAME
    if not path.exists():
        example = TOOL_ROOT / EXAMPLE_CONFIG_NAME
        if example.exists():
            shutil.copy2(example, path)
        else:
            path.write_text(json.dumps(AppConfig().to_dict(), indent=2), encoding="utf-8")
    return path


def load_config(config_path: Optional[Path | str] = None) -> AppConfig:
    path = ensure_config_file(Path(config_path) if config_path else None)
    # ``utf-8-sig`` accepts normal UTF-8 and strips the optional BOM emitted
    # by Windows PowerShell's Set-Content.
    with open(path, "r", encoding="utf-8-sig") as fh:
        raw = json.load(fh)

    roots = [
        DataRoot(
            name=str(item.get("name", f"root_{i}")),
            path=_resolve_path(item["path"]),
            priority=int(item.get("priority", i + 1)),
            enabled=bool(item.get("enabled", True)),
        )
        for i, item in enumerate(raw.get("data_roots", []))
    ]

    cache_dir = _resolve_path(raw.get("cache_dir", "cache"))
    output_dir = _resolve_path(raw.get("output_dir", "output"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    fab_raw = raw.get("fabrication_workbook")
    fab_path = _resolve_path(fab_raw) if fab_raw else None

    return AppConfig(
        data_roots=roots,
        cache_dir=cache_dir,
        output_dir=output_dir,
        classifier=str(raw.get("classifier", "manual_excel")),
        yield_success_categories=[
            str(x).lower() for x in raw.get("yield_success_categories", ["memristive"])
        ],
        exclude_workbook_names=[
            str(x).lower() for x in raw.get("exclude_workbook_names", ["device_status.xlsx", "device_status.xls"])
        ],
        fabrication_workbook=fab_path,
        fabrication_sheet=str(raw.get("fabrication_sheet", "Memristor Devices")),
        config_path=path,
    )


def save_config(config: AppConfig, config_path: Optional[Path] = None) -> Path:
    path = Path(config_path) if config_path else (config.config_path or TOOL_ROOT / DEFAULT_CONFIG_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(config.to_dict(), fh, indent=2)
        fh.write("\n")
    config.config_path = path
    return path
