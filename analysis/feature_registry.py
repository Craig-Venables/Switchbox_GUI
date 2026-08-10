"""
Per-file analysis feature versions.

History measurements stamp ``analysis_features: {feature_id: version}``.
Reclassify skips files that already have all requested features at the
current versions, and only fills missing ones on incremental runs.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional, Set

# Bump a feature's version when its compute semantics change.
FEATURE_VERSIONS: Dict[str, int] = {
    "classification": 1,
    "resistance": 1,
    "hysteresis": 1,
    "voltage_window": 1,
    "switching_features": 1,
    "memory_window_quality": 1,
    "performance_compact": 1,
    "research_ndr": 1,
    "ndr_normalized_slope": 1,
}

# Features produced by analysis_level="full" (no research pass required).
FULL_FEATURES: Set[str] = {
    "classification",
    "resistance",
    "hysteresis",
    "voltage_window",
    "switching_features",
    "memory_window_quality",
    "performance_compact",
}

# Features produced by analysis_level="research".
RESEARCH_FEATURES: Set[str] = {
    "research_ndr",
    "ndr_normalized_slope",
}

ALL_FEATURES: Set[str] = set(FEATURE_VERSIONS)


def current_stamp(feature_ids: Optional[Iterable[str]] = None) -> Dict[str, int]:
    ids = list(feature_ids) if feature_ids is not None else list(FEATURE_VERSIONS)
    return {fid: FEATURE_VERSIONS[fid] for fid in ids if fid in FEATURE_VERSIONS}


def missing_features(
    stamped: Optional[Mapping[str, object]],
    required: Optional[Iterable[str]] = None,
) -> List[str]:
    """Return feature ids that are absent or at a lower version than current."""
    req = list(required) if required is not None else list(FEATURE_VERSIONS)
    have = stamped or {}
    missing: List[str] = []
    for fid in req:
        if fid not in FEATURE_VERSIONS:
            continue
        want = FEATURE_VERSIONS[fid]
        got = have.get(fid)
        try:
            got_i = int(got) if got is not None else None
        except (TypeError, ValueError):
            got_i = None
        if got_i is None or got_i < want:
            missing.append(fid)
    return missing


def merge_stamp(
    stamped: Optional[Mapping[str, object]],
    feature_ids: Iterable[str],
) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if stamped:
        for k, v in stamped.items():
            try:
                out[str(k)] = int(v)
            except (TypeError, ValueError):
                continue
    out.update(current_stamp(feature_ids))
    return out


def needs_full_pass(missing: Iterable[str]) -> bool:
    miss = set(missing)
    return bool(miss & FULL_FEATURES)


def needs_research_pass(missing: Iterable[str]) -> bool:
    miss = set(missing)
    return bool(miss & RESEARCH_FEATURES)
