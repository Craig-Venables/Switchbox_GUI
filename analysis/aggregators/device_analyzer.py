"""
Device-level analyzer: aggregates classification results across all sweeps for one device.

Usage (standalone):
    from analysis.aggregators.device_analyzer import DeviceSweepAggregator
    agg = DeviceSweepAggregator(sweeps)   # list of sweep dicts from device_yield_summary
    summary = agg.summarize()

Or use the module-level helper:
    from analysis.aggregators.device_analyzer import analyse_device_sweeps
    summary = analyse_device_sweeps(sweeps)
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FORMING_STAGE_ORDER = [
    "unformed",
    "precursor_rectifying",
    "forming_memristive",
    "weak_memristive",
    "formed_rectifying",
    "formed_memristive",
]

FORMING_STAGE_RANK = {s: i for i, s in enumerate(FORMING_STAGE_ORDER)}


def _stage_rank(stage: str) -> int:
    return FORMING_STAGE_RANK.get(stage, -1)


# ---------------------------------------------------------------------------
# Trajectory helpers
# ---------------------------------------------------------------------------

def _detect_trajectory(sweeps: List[Dict[str, Any]]) -> str:
    """
    Classify the forming trajectory across an ordered list of sweeps.

    Possible values:
        formed          - reached formed_memristive at any point
        forming         - progressing toward formed (rank improving)
        formed_rectifying - best stage is formed_rectifying
        precursor       - only precursor / unformed states
        regression      - was formed/memristive, then degraded to non_conductive
        stable_unformed - never left unformed state
        unknown         - too few sweeps or all missing stage info
    """
    stages = [s.get("forming_stage", "") for s in sweeps if s.get("forming_stage")]
    if not stages:
        return "unknown"

    if "formed_memristive" in stages:
        # Check if device later degraded (formed → non_conductive with nothing after)
        last_types = [s.get("predicted_type", "") for s in sweeps[-3:]]
        if all(t in ("non_conductive", "uncertain") for t in last_types) and len(stages) > 2:
            return "regression"
        return "formed"

    if "formed_rectifying" in stages:
        return "formed_rectifying"

    ranks = [_stage_rank(st) for st in stages if _stage_rank(st) >= 0]
    if not ranks:
        return "unknown"

    if max(ranks) <= _stage_rank("unformed"):
        return "stable_unformed"

    # Look for a clear improving trend (last rank > first rank)
    if ranks[-1] > ranks[0]:
        return "forming"

    return "precursor"


def _memristivity_trend(sweeps: List[Dict[str, Any]]) -> str:
    """
    Assess whether memristivity_score is improving, stable, or declining across sweeps.
    Only meaningful for devices with 3+ scored sweeps.
    """
    scores = []
    for s in sweeps:
        ms = s.get("memristivity_score")
        try:
            v = float(ms)
            scores.append(v)
        except (TypeError, ValueError):
            pass

    if len(scores) < 3:
        return "insufficient_data"

    first_half = scores[: len(scores) // 2]
    second_half = scores[len(scores) // 2 :]
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    delta = avg_second - avg_first

    if delta > 10:
        return "improving"
    if delta < -10:
        return "declining"
    return "stable"


# ---------------------------------------------------------------------------
# Core aggregator
# ---------------------------------------------------------------------------

class DeviceSweepAggregator:
    """
    Aggregate multiple sweep classification results for a single device.

    Parameters
    ----------
    sweeps : list of dicts
        Each dict must have at minimum the fields produced by
        classification_store.build_device_yield_summaries (forming_stage,
        predicted_type, memristivity_score, sweep_index, filename).
    """

    def __init__(self, sweeps: List[Dict[str, Any]]) -> None:
        self.sweeps = sorted(
            sweeps,
            key=lambda s: (int(s.get("sweep_index") or 0), s.get("filename", "")),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summarize(self) -> Dict[str, Any]:
        """Return a device-level summary dict."""
        sweeps = self.sweeps
        if not sweeps:
            return {"trajectory": "unknown", "yield_tier": "none", "yield_promising": 0}

        type_counts = Counter(s.get("predicted_type", "unknown") for s in sweeps)
        stages = [s.get("forming_stage", "") for s in sweeps if s.get("forming_stage")]

        trajectory = _detect_trajectory(sweeps)
        mem_trend = _memristivity_trend(sweeps)

        # Yield tier: require 2+ memristive sweeps OR a single high-score sweep
        mem_sweeps = [s for s in sweeps if s.get("predicted_type") == "memristive"]
        mem_scores = []
        for s in mem_sweeps:
            try:
                mem_scores.append(float(s["memristivity_score"]))
            except (TypeError, ValueError, KeyError):
                pass

        formed_memristive = len(mem_sweeps) >= 2 or (
            len(mem_sweeps) == 1 and bool(mem_scores) and max(mem_scores) >= 60
        )
        has_formed_rect = "formed_rectifying" in stages
        has_precursor = "precursor_rectifying" in stages

        if formed_memristive:
            yield_tier = "formed"
        elif has_formed_rect:
            yield_tier = "formed_rectifying"
        elif has_precursor or "forming_memristive" in stages:
            yield_tier = "forming"
        else:
            yield_tier = "none"

        ever_promising = bool(type_counts.get("memristive", 0))

        peak_stage = max(stages, key=_stage_rank) if stages else ""
        best_mem_score = max(mem_scores) if mem_scores else None

        return {
            "trajectory": trajectory,
            "memristivity_trend": mem_trend,
            "yield_tier": yield_tier,
            "yield": 1 if yield_tier in ("formed", "formed_rectifying") else 0,
            "yield_promising": 1 if ever_promising else 0,
            "peak_forming_stage": peak_stage,
            "best_memristivity_score": best_mem_score,
            "memristive_sweep_count": len(mem_sweeps),
            "type_counts": dict(type_counts),
            "forming_stages_seen": list(dict.fromkeys(stages)),
        }

    def latest_type(self) -> str:
        return self.sweeps[-1].get("predicted_type", "") if self.sweeps else ""

    def latest_stage(self) -> str:
        stages = [s.get("forming_stage", "") for s in self.sweeps if s.get("forming_stage")]
        return stages[-1] if stages else ""


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

def analyse_device_sweeps(sweeps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience wrapper — analyse a list of sweep dicts and return a summary."""
    return DeviceSweepAggregator(sweeps).summarize()


# ---------------------------------------------------------------------------
# Legacy stub (kept for backward compatibility)
# ---------------------------------------------------------------------------

class DeviceAnalyzer:
    """
    Legacy placeholder class — kept so existing imports do not break.
    For batch yield aggregation use DeviceSweepAggregator or the
    build_device_yield_summaries function in classification_store.
    """

    def __init__(self, device_directory: str) -> None:
        self.device_directory = device_directory

    def analyze_device(self) -> dict:
        return {
            "status": "use DeviceSweepAggregator",
            "message": (
                "Pass a list of sweep classification dicts to DeviceSweepAggregator "
                "or use build_device_yield_summaries in classification_store."
            ),
        }
