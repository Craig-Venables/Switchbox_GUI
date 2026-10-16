"""Load thesis_llm sample fact packs for auto ≥N-loop yield overlays.

historical_yield's default timeline is Excel strict memristive yield.
Auto loop yield (memristive_loop_count ≥ N) is read from either:

- thesis_llm ``output/facts/{sample}/sample.json``
- the OneDrive device-summaries mirror ``reports/{sample}_sample_report.json``
  (same numbers nested under ``facts``)

Both expose ``worked_by_loop_threshold``.

memristive_loop_count = cumulative memristive triangular cycles across IV files
(not memristive_sweep_count = number of memristive IV files).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

_SAMPLE_NUM = re.compile(r"D(\d+)", re.IGNORECASE)
_SAMPLE_REPORT = re.compile(r"^(D\d+)_sample_report\.json$", re.IGNORECASE)


def parse_gates(raw: str, *, default: Sequence[int] = (4, 10, 20, 50, 100)) -> List[int]:
    parts = re.split(r"[,;\s]+", (raw or "").strip())
    vals: List[int] = []
    for p in parts:
        if not p:
            continue
        try:
            vals.append(int(p))
        except ValueError:
            continue
    out = sorted({v for v in vals if v > 0})
    return out or sorted({int(v) for v in default if int(v) > 0}) or [4]


def sample_number(sample_id: str) -> Optional[int]:
    m = _SAMPLE_NUM.search(str(sample_id))
    return int(m.group(1)) if m else None


def _fraction_at_loop_gate(pack: Dict[str, Any], gate: int) -> Optional[float]:
    wbl = pack.get("worked_by_loop_threshold") or {}
    row = wbl.get(str(gate))
    if isinstance(row, dict) and row.get("worked_fraction") is not None:
        try:
            return float(row["worked_fraction"])
        except (TypeError, ValueError):
            return None
    if int(gate) == int(pack.get("worked_memristive_min_loops") or 4):
        wf = pack.get("worked_loops_fraction")
        if wf is not None:
            try:
                return float(wf)
            except (TypeError, ValueError):
                return None
    return None


def _unwrap_fact_pack(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sample reports nest the fact pack under ``facts``; raw fact files do not."""
    facts = payload.get("facts")
    if isinstance(facts, dict) and (
        "worked_by_loop_threshold" in facts or "sample_id" in facts
    ):
        return facts
    return payload


def _fact_sources(facts_dir: Path) -> List[tuple]:
    """(sample_id, path) from a facts tree or a device-summaries folder."""
    search_dirs = [facts_dir]
    reports = facts_dir / "reports"
    if reports.is_dir():
        search_dirs.append(reports)

    found: List[tuple] = []
    seen = set()
    for directory in search_dirs:
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for path in children:
            if path.is_dir():
                sample_path = path / "sample.json"
                if not sample_path.is_file():
                    continue
                sid = path.name.upper() if path.name.upper().startswith("D") else path.name
                source = sample_path
            else:
                match = _SAMPLE_REPORT.match(path.name)
                if not match:
                    continue
                sid = match.group(1).upper()
                source = path
            key = sid.upper()
            if key in seen:
                continue
            seen.add(key)
            found.append((sid, source))
    return found


def load_auto_yield_dataframe(
    facts_dir: Optional[Path],
    *,
    gates: Sequence[int],
) -> pd.DataFrame:
    """Return one row per sample with worked_pct_at_{gate} from loop thresholds."""
    cols = ["sample_id", "sample_number", "n_devices"] + [
        f"worked_pct_at_{g}" for g in gates
    ] + [f"n_worked_at_{g}" for g in gates]
    if facts_dir is None:
        return pd.DataFrame(columns=cols)
    facts_dir = Path(facts_dir)
    if not facts_dir.is_dir():
        return pd.DataFrame(columns=cols)

    rows: List[Dict[str, Any]] = []
    for sid, sample_path in _fact_sources(facts_dir):
        try:
            payload = json.loads(sample_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        pack = _unwrap_fact_pack(payload)
        sid = str(pack.get("sample_id") or sid)
        row: Dict[str, Any] = {
            "sample_id": sid,
            "sample_number": sample_number(sid),
            "n_devices": pack.get("n_devices_with_facts"),
        }
        for g in gates:
            frac = _fraction_at_loop_gate(pack, int(g))
            row[f"worked_pct_at_{g}"] = (100.0 * frac) if frac is not None else None
            gate_row = (pack.get("worked_by_loop_threshold") or {}).get(str(g)) or {}
            row[f"n_worked_at_{g}"] = gate_row.get("n_worked_memristive_loops")
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame.from_records(rows).sort_values(
        by=["sample_number", "sample_id"], na_position="last"
    ).reset_index(drop=True)
