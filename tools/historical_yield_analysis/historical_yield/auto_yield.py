"""Load thesis_llm sample fact packs for auto ≥N-loop yield overlays.

historical_yield's default timeline is Excel strict memristive yield.
Auto loop yield (memristive_loop_count ≥ N) lives in thesis_llm
``output/facts/{sample}/sample.json`` under ``worked_by_loop_threshold``.

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
    for p in sorted(facts_dir.iterdir()):
        sample_path = p / "sample.json"
        if not p.is_dir() or not sample_path.is_file():
            continue
        sid = p.name.upper() if p.name.upper().startswith("D") else p.name
        try:
            pack = json.loads(sample_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
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
