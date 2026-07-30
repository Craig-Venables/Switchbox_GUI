"""Parse fabrication metadata from sample folder / workbook names."""

from __future__ import annotations

import re
from typing import Optional, Tuple

from .models import SampleMeta

# D95-0.1mgml-ITO-PMMA(2%)-Gold-s3
# D104-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s5
# D107-Stock-Gold-PMMA 2.0(2%)-Gold-s2
_SAMPLE_ID_RE = re.compile(r"(?i)(?:^|[^A-Za-z0-9])(D)(\d+)\b")
_CONC_RE = re.compile(r"(?i)^(?:(\d+(?:\.\d+)?)\s*mg\s*/?\s*ml|stock)$")
_POLYMER_RE = re.compile(
    r"(?i)^(PMMA|PS|PVA|PVP|PEO|PVK)(?:\s*[\d.]*)?\s*(?:\((\d+(?:\.\d+)?)\s*%\))?$"
)
_SOLUTION_RE = re.compile(r"(?i)^s(\d+)$")


def extract_sample_id(name: str) -> Optional[Tuple[str, int]]:
    """Return (D95, 95) from a sample name or path fragment."""
    m = _SAMPLE_ID_RE.search(name)
    if not m:
        return None
    num = int(m.group(2))
    return f"D{num}", num


def parse_concentration(token: str) -> Tuple[Optional[str], Optional[float], bool]:
    """Return (raw, mgml_float, is_stock). Stock -> 0.0 for numeric plots."""
    t = token.strip()
    if not t:
        return None, None, False
    m = _CONC_RE.match(t.replace(" ", ""))
    if not m:
        # try looser: 0.1mgml already stripped spaces above; also allow 0.1mg/ml
        loose = re.match(r"(?i)^(\d+(?:\.\d+)?)mgml$", t.replace(" ", "").replace("/", ""))
        if loose:
            val = float(loose.group(1))
            return f"{val}mgml", val, False
        if t.lower() == "stock":
            return "Stock", 0.0, True
        return t, None, False
    if t.lower().replace(" ", "") == "stock" or (m.group(0).lower() == "stock"):
        return "Stock", 0.0, True
    # matched numeric via first branch after strip — rebuild
    num_m = re.match(r"(?i)^(\d+(?:\.\d+)?)", t.replace(" ", ""))
    if num_m:
        val = float(num_m.group(1))
        return f"{val}mgml", val, False
    return t, None, False


def parse_polymer(token: str) -> Tuple[Optional[str], Optional[float]]:
    t = token.strip()
    m = _POLYMER_RE.match(t)
    if not m:
        # Allow embedded percent only
        m2 = re.match(r"(?i)^([A-Za-z]+)(?:.*?\((\d+(?:\.\d+)?)\s*%\))?$", t)
        if not m2:
            return (t or None), None
        pct = float(m2.group(2)) if m2.group(2) else None
        return m2.group(1), pct
    pct = float(m.group(2)) if m.group(2) else None
    return m.group(1), pct


def parse_sample_name(name: str, material_hint: Optional[str] = None) -> SampleMeta:
    """
    Parse a sample stem such as:
      D95-0.1mgml-ITO-PMMA(2%)-Gold-s3
      D104-0.1mgml-ITO-PMMA 2.0(2%)-Gold-s5
    """
    stem = name.strip()
    # drop extension if present
    if stem.lower().endswith((".xlsx", ".xls", ".xlsm")):
        stem = stem.rsplit(".", 1)[0]

    sid = extract_sample_id(stem)
    if sid is None:
        raise ValueError(f"Cannot extract sample ID from name: {name!r}")
    sample_id, sample_number = sid

    parts = [p for p in stem.split("-") if p != ""]
    # First part is Dxx (maybe alone)
    # Remaining tokens in typical order:
    # concentration, bottom electrode, polymer(+%), top electrode, solution
    tokens = parts[1:] if parts and re.match(r"(?i)^D\d+$", parts[0]) else parts

    concentration_raw = None
    concentration_mgml = None
    is_stock = False
    bottom_electrode = None
    polymer = None
    polymer_percent = None
    top_electrode = None
    solution_tag = None

    idx = 0
    if idx < len(tokens):
        concentration_raw, concentration_mgml, is_stock = parse_concentration(tokens[idx])
        # If it didn't look like concentration, leave fields and still consume if Stock/mgml pattern-ish
        if concentration_raw is not None or is_stock or re.search(r"(?i)mg|stock", tokens[idx]):
            idx += 1
        else:
            concentration_raw = concentration_mgml = None
            is_stock = False

    if idx < len(tokens):
        bottom_electrode = tokens[idx].strip() or None
        idx += 1

    if idx < len(tokens):
        polymer, polymer_percent = parse_polymer(tokens[idx])
        idx += 1

    if idx < len(tokens):
        # solution tag may be last; if current looks like sN, skip electrode
        if _SOLUTION_RE.match(tokens[idx]):
            solution_tag = tokens[idx]
            idx += 1
        else:
            top_electrode = tokens[idx].strip() or None
            idx += 1

    if idx < len(tokens) and solution_tag is None:
        if _SOLUTION_RE.match(tokens[idx]):
            solution_tag = tokens[idx]
        elif top_electrode is None:
            top_electrode = tokens[idx].strip() or None

    return SampleMeta(
        sample_id=sample_id,
        sample_number=sample_number,
        sample_name=stem,
        concentration_raw=concentration_raw,
        concentration_mgml=concentration_mgml,
        is_stock=is_stock,
        bottom_electrode=bottom_electrode,
        polymer=polymer,
        polymer_percent=polymer_percent,
        top_electrode=top_electrode,
        solution_tag=solution_tag,
        material_hint=material_hint,
    )


def material_hint_from_path(path_str: str) -> Optional[str]:
    """Best-effort material / QD type from parent folders."""
    parts = [p for p in path_str.replace("\\", "/").split("/") if p]
    # Look for Quantum Dots child folders e.g. Zn-Cu-In-S(Zns), WS2
    for i, part in enumerate(parts):
        if part.lower() in {"quantum dots", "quantum_dots"} and i + 1 < len(parts):
            return parts[i + 1]
    return None
