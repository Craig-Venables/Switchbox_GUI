"""Build absolute post-program read times for SMU/TSP timed retention."""

from __future__ import annotations

from typing import Any, Dict, List, MutableMapping


def build_regular_read_intervals(every_s: float, duration_s: float) -> List[float]:
    """Return times every ``every_s`` from the first step through ``duration_s`` (inclusive)."""
    every = float(every_s)
    duration = float(duration_s)
    if every <= 0:
        raise ValueError(f"read_every_s must be > 0, got {every}")
    if duration <= 0:
        raise ValueError(f"retention_duration_s must be > 0, got {duration}")
    intervals: List[float] = []
    t = every
    # Guard against accidental huge lists (e.g. every=0.001 over days)
    max_points = 100_000
    while t < duration - 1e-9:
        intervals.append(t)
        t += every
        if len(intervals) >= max_points:
            break
    if not intervals or intervals[-1] < duration - 1e-9:
        intervals.append(duration)
    return intervals


def format_timed_retention_eta(every_s: float, duration_s: float) -> str:
    """Human-readable wall-clock estimate for Timed Retention (hours + h/m breakdown)."""
    every = float(every_s)
    duration = float(duration_s)
    if every <= 0 or duration <= 0:
        return "Estimated time: enter positive Read Every and Retention Duration"
    intervals = build_regular_read_intervals(every, duration)
    n_interval = len(intervals)
    # Wall time is dominated by waiting until the last read time (plus a short t=0 read)
    hours = duration / 3600.0
    total_min = int(duration // 60)
    h_part = total_min // 60
    m_part = total_min % 60
    s_part = int(round(duration - total_min * 60))
    if h_part > 0:
        clock = f"{h_part} h {m_part} min"
        if s_part:
            clock += f" {s_part} s"
    elif m_part > 0:
        clock = f"{m_part} min"
        if s_part:
            clock += f" {s_part} s"
    else:
        clock = f"{duration:g} s"
    return (
        f"Estimated time to complete: ~ {hours:.2f} h ({clock}) | "
        f"{n_interval} interval reads + t=0"
    )


def normalize_timed_retention_params(params: MutableMapping[str, Any]) -> Dict[str, Any]:
    """
    Convert GUI Timed Retention fields into TSP ``read_intervals`` (seconds).

    Accepts optional ``read_intervals`` override; otherwise builds a regular grid from
    ``read_every_s`` + ``retention_duration_s`` (defaults: 60 s / 10000 s).
    Strips GUI-only keys before returning.
    """
    out = dict(params)
    every = out.pop("read_every_s", None)
    duration = out.pop("retention_duration_s", None)

    ri = out.get("read_intervals")
    if isinstance(ri, str):
        parsed = [float(x.strip()) for x in ri.split(",") if x.strip()]
    elif isinstance(ri, (list, tuple)):
        parsed = [float(x) for x in ri]
    else:
        parsed = []

    if parsed:
        out["read_intervals"] = parsed
        return out

    every_s = float(every) if every is not None else 60.0
    duration_s = float(duration) if duration is not None else 10000.0
    out["read_intervals"] = build_regular_read_intervals(every_s, duration_s)
    return out
