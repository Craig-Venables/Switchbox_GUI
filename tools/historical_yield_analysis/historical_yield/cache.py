"""SQLite cache for indexed classification workbooks and device rows."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence

from . import SCHEMA_VERSION
from .models import DeviceClassification, SampleMeta, WorkbookImportResult


class YieldCache:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workbooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id TEXT NOT NULL,
                    sample_number INTEGER NOT NULL,
                    sample_name TEXT NOT NULL,
                    source_path TEXT NOT NULL UNIQUE,
                    root_name TEXT NOT NULL,
                    root_priority INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    accepted INTEGER NOT NULL DEFAULT 1,
                    duplicate_of TEXT,
                    schema_header TEXT,
                    classifier_id TEXT NOT NULL,
                    classifier_version TEXT NOT NULL,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    concentration_raw TEXT,
                    concentration_mgml REAL,
                    is_stock INTEGER NOT NULL DEFAULT 0,
                    bottom_electrode TEXT,
                    polymer TEXT,
                    polymer_percent REAL,
                    top_electrode TEXT,
                    solution_tag TEXT,
                    material_hint TEXT,
                    imported_at TEXT NOT NULL,
                    schema_version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workbook_id INTEGER NOT NULL REFERENCES workbooks(id) ON DELETE CASCADE,
                    sample_id TEXT NOT NULL,
                    section TEXT NOT NULL,
                    device_number INTEGER NOT NULL,
                    raw_classification TEXT,
                    normalized_classification TEXT NOT NULL,
                    is_classified INTEGER NOT NULL,
                    is_yield_success INTEGER NOT NULL,
                    memristor_strength TEXT,
                    current_range TEXT,
                    resistance_value TEXT,
                    n_sweeps TEXT,
                    retention TEXT,
                    endurance TEXT,
                    volatile_flag TEXT,
                    current_state TEXT,
                    date_measured TEXT,
                    notes TEXT,
                    extra_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_workbooks_sample ON workbooks(sample_id);
                CREATE INDEX IF NOT EXISTS idx_workbooks_accepted ON workbooks(accepted);
                CREATE INDEX IF NOT EXISTS idx_devices_sample ON devices(sample_id);
                CREATE INDEX IF NOT EXISTS idx_devices_norm ON devices(normalized_classification);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

    def clear(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM devices")
            conn.execute("DELETE FROM workbooks")
            conn.execute("DELETE FROM audit_log")

    def get_fingerprint(self, source_path: str) -> Optional[str]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT fingerprint FROM workbooks WHERE source_path = ?",
                (str(source_path),),
            ).fetchone()
            return row["fingerprint"] if row else None

    def get_workbook_by_path(self, source_path: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM workbooks WHERE source_path = ?",
                (str(source_path),),
            ).fetchone()

    def accepted_sample_paths(self) -> Dict[str, str]:
        """sample_id -> source_path for currently accepted workbooks."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT sample_id, source_path FROM workbooks WHERE accepted = 1"
            ).fetchall()
            return {r["sample_id"]: r["source_path"] for r in rows}

    def delete_workbook(self, source_path: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM workbooks WHERE source_path = ?", (str(source_path),))

    def upsert_workbook(self, result: WorkbookImportResult) -> int:
        now = datetime.now(timezone.utc).isoformat()
        sample = result.sample
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM workbooks WHERE source_path = ?",
                (result.source_path,),
            ).fetchone()
            payload = (
                sample.sample_id,
                sample.sample_number,
                sample.sample_name,
                result.source_path,
                result.root_name,
                result.root_priority,
                result.fingerprint,
                result.file_size,
                result.mtime_ns,
                result.status,
                1 if result.accepted else 0,
                result.duplicate_of,
                result.schema_header,
                result.classifier_id,
                result.classifier_version,
                json.dumps(result.warnings),
                sample.concentration_raw,
                sample.concentration_mgml,
                1 if sample.is_stock else 0,
                sample.bottom_electrode,
                sample.polymer,
                sample.polymer_percent,
                sample.top_electrode,
                sample.solution_tag,
                sample.material_hint,
                now,
                SCHEMA_VERSION,
            )
            if existing:
                wb_id = int(existing["id"])
                conn.execute("DELETE FROM devices WHERE workbook_id = ?", (wb_id,))
                conn.execute(
                    """
                    UPDATE workbooks SET
                        sample_id=?, sample_number=?, sample_name=?, source_path=?,
                        root_name=?, root_priority=?, fingerprint=?, file_size=?, mtime_ns=?,
                        status=?, accepted=?, duplicate_of=?, schema_header=?,
                        classifier_id=?, classifier_version=?, warnings_json=?,
                        concentration_raw=?, concentration_mgml=?, is_stock=?,
                        bottom_electrode=?, polymer=?, polymer_percent=?,
                        top_electrode=?, solution_tag=?, material_hint=?,
                        imported_at=?, schema_version=?
                    WHERE id=?
                    """,
                    payload + (wb_id,),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO workbooks (
                        sample_id, sample_number, sample_name, source_path,
                        root_name, root_priority, fingerprint, file_size, mtime_ns,
                        status, accepted, duplicate_of, schema_header,
                        classifier_id, classifier_version, warnings_json,
                        concentration_raw, concentration_mgml, is_stock,
                        bottom_electrode, polymer, polymer_percent,
                        top_electrode, solution_tag, material_hint,
                        imported_at, schema_version
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    payload,
                )
                wb_id = int(cur.lastrowid)

            for d in result.devices:
                conn.execute(
                    """
                    INSERT INTO devices (
                        workbook_id, sample_id, section, device_number,
                        raw_classification, normalized_classification,
                        is_classified, is_yield_success,
                        memristor_strength, current_range, resistance_value,
                        n_sweeps, retention, endurance, volatile_flag,
                        current_state, date_measured, notes, extra_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        wb_id,
                        sample.sample_id,
                        d.section,
                        d.device_number,
                        d.raw_classification,
                        d.normalized_classification,
                        1 if d.is_classified else 0,
                        1 if d.is_yield_success else 0,
                        d.memristor_strength,
                        d.current_range,
                        d.resistance_value,
                        d.n_sweeps,
                        d.retention,
                        d.endurance,
                        d.volatile,
                        d.current_state,
                        d.date_measured,
                        d.notes,
                        json.dumps(d.extra or {}),
                    ),
                )
            return wb_id

    def log_event(self, event: str, payload: Dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit_log(created_at, event, payload_json) VALUES (?,?,?)",
                (datetime.now(timezone.utc).isoformat(), event, json.dumps(payload)),
            )

    def list_accepted_workbooks(self) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT * FROM workbooks
                    WHERE accepted = 1 AND status = 'ok'
                    ORDER BY sample_number ASC, sample_id ASC
                    """
                )
            )

    def list_all_workbooks(self) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    "SELECT * FROM workbooks ORDER BY sample_number ASC, root_priority ASC"
                )
            )

    def list_devices_for_accepted(self) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT d.*, w.sample_name, w.sample_number, w.source_path, w.root_name,
                           w.concentration_mgml, w.is_stock, w.polymer,
                           w.bottom_electrode, w.top_electrode, w.material_hint
                    FROM devices d
                    JOIN workbooks w ON w.id = d.workbook_id
                    WHERE w.accepted = 1 AND w.status = 'ok'
                    ORDER BY w.sample_number, d.section, d.device_number
                    """
                )
            )

    def stats(self) -> Dict[str, int]:
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM workbooks").fetchone()["n"]
            accepted = conn.execute(
                "SELECT COUNT(*) AS n FROM workbooks WHERE accepted = 1 AND status = 'ok'"
            ).fetchone()["n"]
            devices = conn.execute(
                """
                SELECT COUNT(*) AS n FROM devices d
                JOIN workbooks w ON w.id = d.workbook_id
                WHERE w.accepted = 1 AND w.status = 'ok'
                """
            ).fetchone()["n"]
            classified = conn.execute(
                """
                SELECT COUNT(*) AS n FROM devices d
                JOIN workbooks w ON w.id = d.workbook_id
                WHERE w.accepted = 1 AND w.status = 'ok' AND d.is_classified = 1
                """
            ).fetchone()["n"]
            duplicates = conn.execute(
                "SELECT COUNT(*) AS n FROM workbooks WHERE status = 'duplicate_rejected'"
            ).fetchone()["n"]
            malformed = conn.execute(
                "SELECT COUNT(*) AS n FROM workbooks WHERE status IN ('malformed','parse_error')"
            ).fetchone()["n"]
            return {
                "workbooks_total": int(total),
                "workbooks_accepted": int(accepted),
                "devices": int(devices),
                "classified_devices": int(classified),
                "duplicates": int(duplicates),
                "malformed": int(malformed),
            }
