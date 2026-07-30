"""Unit tests for historical yield analysis (no live OneDrive dependency)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from historical_yield.analysis import sample_dataframe, summarize_sample_devices
from historical_yield.cache import YieldCache
from historical_yield.config import AppConfig, DataRoot, load_config
from historical_yield.discovery import should_skip_workbook
from historical_yield.import_pipeline import import_workbook, resolve_duplicates, scan_and_update_cache
from historical_yield.models import DeviceClassification, SampleMeta, WorkbookImportResult
from historical_yield.normalize import normalize_classification
from historical_yield.parse_sample import parse_sample_name
from historical_yield.workbook import parse_workbook_rows


def _write_xlsx(path: Path, rows):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r_i, row in enumerate(rows, start=1):
        for c_i, val in enumerate(row, start=1):
            ws.cell(r_i, c_i, val)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


HEADER = [
    "Section",
    "Device #",
    "Classification",
    "Memristor Strength",
    "Current Range",
    "Resistance Value",
    "# Sweeps",
    "Retention",
    "Endurance",
    "Volatile",
    "Current State",
    "Date Measured",
    "Notes",
]
INSTR = [
    "Device section",
    "Device Number",
    "Memristive , ohmic or non conductive",
    "poor, good,excellent",
    "Max current seen,",
    "If ohmic whats the resistance value",
    "Number of sweeps completed",
    "Give values for the Retention here",
    "Give Values for Endurance here",
    "Volatile or non Volatile?",
    "What Is the devices current state",
    "Date Measured",
    "Notes for when doing the measurement.",
]


def test_parse_sample_name_standard():
    meta = parse_sample_name("D95-0.1mgml-ITO-PMMA(2%)-Gold-s3")
    assert meta.sample_id == "D95"
    assert meta.sample_number == 95
    assert meta.concentration_mgml == pytest.approx(0.1)
    assert meta.bottom_electrode == "ITO"
    assert meta.polymer == "PMMA"
    assert meta.polymer_percent == pytest.approx(2.0)
    assert meta.top_electrode == "Gold"
    assert meta.solution_tag.lower() == "s3"


def test_parse_sample_name_stock_and_spaced_polymer():
    meta = parse_sample_name("D107-Stock-Gold-PMMA 2.0(2%)-Gold-s2")
    assert meta.is_stock
    assert meta.concentration_mgml == 0.0
    assert meta.polymer == "PMMA"
    assert meta.polymer_percent == pytest.approx(2.0)


def test_normalize_aliases_and_blanks():
    assert normalize_classification("Capacative") == ("capacitive", True, False)
    assert normalize_classification("Non Conductive") == ("non_conductive", True, False)
    assert normalize_classification("Mem-capacative") == ("mem_capacitive", True, False)
    assert normalize_classification("Intermittant") == ("intermittent", True, False)
    assert normalize_classification("Memristive") == ("memristive", True, True)
    assert normalize_classification(None) == ("unknown", False, False)
    assert normalize_classification("") == ("unknown", False, False)
    assert normalize_classification("Memristive , ohmic or non conductive") == (
        "unknown",
        False,
        False,
    )


def test_workbook_instruction_row_and_blanks_excluded_from_yield():
    rows = [
        HEADER,
        INSTR,
        ("A", 1, "Memristive", "Good", None, None, None, None, None, None, None, None, None),
        ("A", 2, "Ohmic", None, None, None, None, None, None, None, None, None, None),
        ("A", 3, None, None, None, None, None, None, None, None, None, None, None),
        ("A", 4, "Capacative", None, None, None, None, None, None, None, None, None, None),
    ]
    devices, warnings, schema = parse_workbook_rows(rows)
    assert schema is not None
    assert len(devices) == 4
    classified = [d for d in devices if d.is_classified]
    assert len(classified) == 3
    assert sum(1 for d in classified if d.is_yield_success) == 1
    # blank excluded
    assert devices[2].is_classified is False


def test_schema_variant_how_strong():
    header = [
        "Section",
        "Device #",
        "Classification",
        "How strong",
        "Current Range",
        "Resistance Value",
        "# Sweeps",
        "Retention",
        "Endurance",
        "Volatile",
        "Current State",
        "Date Measured",
        "Notes",
    ]
    rows = [
        header,
        ("B", 1, "conductive", "weak", None, None, None, None, None, None, None, None, None),
    ]
    devices, _, _ = parse_workbook_rows(rows)
    assert devices[0].normalized_classification == "conductive"
    assert devices[0].memristor_strength == "weak"


def test_should_skip_device_status():
    assert should_skip_workbook(Path("device_status.xlsx"), ["device_status.xlsx"])
    assert should_skip_workbook(Path("~$D95.xlsx"), [])
    assert not should_skip_workbook(Path("D95-0.1mgml.xlsx"), ["device_status.xlsx"])


def test_duplicate_priority_prefers_lower_priority_number():
    s = SampleMeta(sample_id="D104", sample_number=104, sample_name="D104-x")
    a = WorkbookImportResult(
        source_path=r"C:\new\D104.xlsx",
        root_name="Data_folder",
        root_priority=1,
        sample=s,
        fingerprint="a",
        file_size=1,
        mtime_ns=10,
        status="ok",
        devices=[],
    )
    b = WorkbookImportResult(
        source_path=r"C:\old\D104.xlsx",
        root_name="Memristors_legacy",
        root_priority=2,
        sample=s,
        fingerprint="b",
        file_size=1,
        mtime_ns=99,
        status="ok",
        devices=[],
    )
    resolved = resolve_duplicates([b, a])
    winners = [r for r in resolved if r.accepted]
    losers = [r for r in resolved if r.status == "duplicate_rejected"]
    assert len(winners) == 1
    assert winners[0].root_name == "Data_folder"
    assert len(losers) == 1
    assert losers[0].duplicate_of == a.source_path


def test_cache_incremental_fingerprint(tmp_path: Path):
    root_a = tmp_path / "data_a"
    sample_dir = root_a / "D10-0.1mgml-ITO-PMMA(2%)-Gold-s1"
    xlsx = sample_dir / "D10-0.1mgml-ITO-PMMA(2%)-Gold-s1.xlsx"
    _write_xlsx(
        xlsx,
        [
            HEADER,
            INSTR,
            ("A", 1, "Memristive", None, None, None, None, None, None, None, None, None, None),
            ("A", 2, "Ohmic", None, None, None, None, None, None, None, None, None, None),
        ],
    )
    cache_dir = tmp_path / "cache"
    out_dir = tmp_path / "output"
    config = AppConfig(
        data_roots=[DataRoot(name="data_a", path=root_a, priority=1)],
        cache_dir=cache_dir,
        output_dir=out_dir,
    )
    s1 = scan_and_update_cache(config, rebuild=True)
    assert s1.imported >= 1
    s2 = scan_and_update_cache(config, rebuild=False)
    assert s2.unchanged >= 1
    assert s2.imported == 0

    # modify workbook -> reimport
    _write_xlsx(
        xlsx,
        [
            HEADER,
            INSTR,
            ("A", 1, "Memristive", None, None, None, None, None, None, None, None, None, None),
            ("A", 2, "Memristive", None, None, None, None, None, None, None, None, None, None),
            ("A", 3, "Capacative", None, None, None, None, None, None, None, None, None, None),
        ],
    )
    s3 = scan_and_update_cache(config, rebuild=False)
    assert s3.imported >= 1

    cache = YieldCache(config.sqlite_path)
    sdf = sample_dataframe(cache)
    assert len(sdf) == 1
    assert sdf.iloc[0]["n_classified"] == 3
    assert sdf.iloc[0]["n_memristive"] == 2
    assert sdf.iloc[0]["strict_yield"] == pytest.approx(2 / 3)


def test_summarize_yield_denominator():
    import pandas as pd

    devices = pd.DataFrame(
        [
            {
                "sample_id": "D1",
                "sample_number": 1,
                "sample_name": "D1-x",
                "normalized_classification": "memristive",
                "is_classified": True,
                "is_yield_success": True,
                "concentration_mgml": 0.1,
                "is_stock": False,
                "polymer": "PMMA",
                "bottom_electrode": "ITO",
                "top_electrode": "Gold",
                "source_path": "x",
                "root_name": "r",
            },
            {
                "sample_id": "D1",
                "sample_number": 1,
                "sample_name": "D1-x",
                "normalized_classification": "unknown",
                "is_classified": False,
                "is_yield_success": False,
                "concentration_mgml": 0.1,
                "is_stock": False,
                "polymer": "PMMA",
                "bottom_electrode": "ITO",
                "top_electrode": "Gold",
                "source_path": "x",
                "root_name": "r",
            },
            {
                "sample_id": "D1",
                "sample_number": 1,
                "sample_name": "D1-x",
                "normalized_classification": "ohmic",
                "is_classified": True,
                "is_yield_success": False,
                "concentration_mgml": 0.1,
                "is_stock": False,
                "polymer": "PMMA",
                "bottom_electrode": "ITO",
                "top_electrode": "Gold",
                "source_path": "x",
                "root_name": "r",
            },
        ]
    )
    summary = summarize_sample_devices("D1", devices)
    assert summary.n_classified == 2
    assert summary.n_blank == 1
    assert summary.strict_yield == pytest.approx(0.5)


def test_report_generation(tmp_path: Path):
    from historical_yield.report import generate_report

    root_a = tmp_path / "data_a"
    sample_dir = root_a / "D20-0.2mgml-Gold-PS(2%)-Gold-s3"
    xlsx = sample_dir / "D20-0.2mgml-Gold-PS(2%)-Gold-s3.xlsx"
    _write_xlsx(
        xlsx,
        [
            HEADER,
            INSTR,
            ("A", 1, "Memristive", None, None, None, None, None, None, None, None, None, None),
            ("A", 2, "Ohmic", None, None, None, None, None, None, None, None, None, None),
            ("B", 1, "Non-Conductive", None, None, None, None, None, None, None, None, None, None),
        ],
    )
    config = AppConfig(
        data_roots=[DataRoot(name="data_a", path=root_a, priority=1)],
        cache_dir=tmp_path / "cache",
        output_dir=tmp_path / "output",
    )
    scan_and_update_cache(config, rebuild=True)
    result = generate_report(config, formats=("png",))
    assert result.sample_csv.exists()
    assert result.device_csv.exists()
    assert result.manifest.exists()
    assert any(p.suffix == ".png" for p in result.plot_paths)


def test_load_config_creates_from_example(tmp_path: Path, monkeypatch):
    # Use tool's ensure by pointing at a temp copy of example
    example = ROOT / "config.example.json"
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    # override paths to tmp so we don't touch real data
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    data["data_roots"] = []
    data["cache_dir"] = str(tmp_path / "cache")
    data["output_dir"] = str(tmp_path / "output")
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.cache_dir.exists()
    assert cfg.classifier == "manual_excel"


def test_load_config_accepts_utf8_bom(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    raw = {
        "data_roots": [],
        "cache_dir": str(tmp_path / "cache"),
        "output_dir": str(tmp_path / "output"),
        "classifier": "manual_excel",
    }
    cfg_path.write_text(json.dumps(raw), encoding="utf-8-sig")

    cfg = load_config(cfg_path)

    assert cfg.classifier == "manual_excel"
    assert cfg.cache_dir.exists()
