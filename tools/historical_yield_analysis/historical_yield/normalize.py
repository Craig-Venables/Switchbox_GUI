"""Normalize raw Excel classification labels to canonical categories."""

from __future__ import annotations

import re
from typing import Iterable, Optional, Set, Tuple

from .models import CANONICAL_CATEGORIES


# Map cleaned lowercase aliases -> canonical key
_ALIAS_MAP = {
    "memristive": "memristive",
    "memristor": "memristive",
    "ohmic": "ohmic",
    "ohm": "ohmic",
    "capacitive": "capacitive",
    "capacative": "capacitive",  # common typo in lab sheets
    "capacitance": "capacitive",
    "conductive": "conductive",
    "non-conductive": "non_conductive",
    "non conductive": "non_conductive",
    "nonconductive": "non_conductive",
    "non_conductive": "non_conductive",
    "mem-capacitance": "mem_capacitive",
    "mem capacitance": "mem_capacitive",
    "mem-capacitive": "mem_capacitive",
    "memcapacitive": "mem_capacitive",
    "mem-capacative": "mem_capacitive",
    "mem capacative": "mem_capacitive",
    "intermittent": "intermittent",
    "intermittant": "intermittent",  # typo
}

# Header / instruction rows often paste the column description as a fake label
_INSTRUCTION_FRAGMENTS = (
    "memristive , ohmic or non conductive",
    "memristive, ohmic or non conductive",
    "poor, good,excellent",
)


def _clean(raw: Optional[str]) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_instruction_label(raw: Optional[str]) -> bool:
    cleaned = _clean(raw).lower()
    if not cleaned:
        return False
    return any(frag in cleaned for frag in _INSTRUCTION_FRAGMENTS)


def normalize_classification(
    raw: Optional[str],
    *,
    success_categories: Optional[Iterable[str]] = None,
) -> Tuple[str, bool, bool]:
    """
    Return (canonical, is_classified, is_yield_success).

    Blank / NaN / instruction-row text => unknown, not classified.
    Unrecognized nonblank labels => other, classified (counts in denominator).
    """
    success: Set[str] = {str(x).lower() for x in (success_categories or ("memristive",))}
    cleaned = _clean(raw)
    if not cleaned or cleaned.lower() in {"none", "nan", "null", "-"}:
        return "unknown", False, False
    if is_instruction_label(cleaned):
        return "unknown", False, False

    key = cleaned.lower().replace("_", " ").replace("–", "-").replace("—", "-")
    key = key.strip()
    # normalize hyphen spacing
    key = re.sub(r"\s*-\s*", "-", key)

    canonical = _ALIAS_MAP.get(key)
    if canonical is None:
        # try without spaces around hyphens already done; try collapsing spaces
        compact = key.replace(" ", "")
        for alias, canon in _ALIAS_MAP.items():
            if alias.replace(" ", "").replace("-", "") == compact.replace("-", ""):
                canonical = canon
                break

    if canonical is None:
        canonical = "other"

    if canonical not in CANONICAL_CATEGORIES:
        canonical = "other"

    is_classified = True
    is_success = canonical in success
    return canonical, is_classified, is_success
