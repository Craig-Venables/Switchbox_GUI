"""Pure-logic helpers for the Automated Routine tab (no tkinter deps).

Builds a "sweep pulse width at each of a series of laser current-% levels"
plan: for each current level (low -> high), fire every width in the widths
list, then move to the next (higher) current %. Kept separate from
``gui.py`` so the parsing/generation logic is easy to read and reason
about on its own — mirrors the style of ``waveform.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Literal, Optional

# Recognised time-unit suffixes, longest-first so "us"/"ms" don't get
# swallowed by a shorter alternative.
_UNIT_SECONDS = {
    "ns": 1e-9,
    "us": 1e-6,
    "\u00b5s": 1e-6,  # µs
    "ms": 1e-3,
    "s": 1.0,
}

_TOKEN_RE = re.compile(
    r"^\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*([a-zA-Z\u00b5]*)\s*$"
)


def parse_time_value(token: str) -> float:
    """Parse a single width/time token (e.g. ``"100ns"``, ``"1.5 us"``,
    ``"2ms"``) into seconds.

    A bare number with no unit suffix is assumed to be in **microseconds**,
    matching the convention of the existing "Width (\u00b5s)" field elsewhere
    in this tool.
    """
    text = (token or "").strip()
    if not text:
        raise ValueError("empty value")
    match = _TOKEN_RE.match(text)
    if not match:
        raise ValueError(f"could not parse time value {token!r}")
    number_s, unit = match.group(1), match.group(2).lower()
    try:
        number = float(number_s)
    except ValueError as exc:
        raise ValueError(f"could not parse number in {token!r}") from exc
    if not unit:
        scale = 1e-6  # bare number -> microseconds
    elif unit in _UNIT_SECONDS:
        scale = _UNIT_SECONDS[unit]
    else:
        raise ValueError(
            f"unrecognised unit {unit!r} in {token!r} (use ns / us / \u00b5s / ms / s)"
        )
    seconds = number * scale
    if seconds <= 0:
        raise ValueError(f"time value must be > 0: {token!r}")
    return seconds


def format_time_compact(seconds: float) -> str:
    """Human-readable ns/\u00b5s/ms/s display for a duration."""
    if seconds <= 0:
        return "0 s"
    if seconds < 1e-6:
        return f"{seconds * 1e9:.3g} ns"
    if seconds < 1e-3:
        return f"{seconds * 1e6:.3g} \u00b5s"
    if seconds < 1.0:
        return f"{seconds * 1e3:.3g} ms"
    return f"{seconds:.3g} s"


def parse_width_list(text: str) -> List[float]:
    """Parse a comma/whitespace/newline-separated list of width tokens into
    seconds. Raises ``ValueError`` (with the offending token) on bad input."""
    if not (text or "").strip():
        raise ValueError("widths list is empty")
    raw_tokens = [t for t in re.split(r"[,\n]", text) if t.strip()]
    if not raw_tokens:
        raise ValueError("widths list is empty")
    widths: List[float] = []
    for raw in raw_tokens:
        try:
            widths.append(parse_time_value(raw))
        except ValueError as exc:
            raise ValueError(f"bad width {raw.strip()!r}: {exc}") from exc
    return widths


def format_width_list(widths_s: List[float]) -> str:
    """Render a list of widths (seconds) back into the editable comma list
    format used by the Generate button / widths Entry."""
    return ", ".join(format_time_compact(w) for w in widths_s)


def generate_decade_widths(
    start_s: float, multiplier: float, num_steps: int
) -> List[float]:
    """``start, start*multiplier, start*multiplier**2, ...`` for
    ``num_steps`` entries (multiplier defaults to 10 for true decade steps
    in the GUI, but is customizable — e.g. 2x steps)."""
    if start_s <= 0:
        raise ValueError("start width must be > 0")
    if multiplier <= 0:
        raise ValueError("step multiplier must be > 0")
    num_steps = max(1, int(num_steps))
    return [start_s * (multiplier**i) for i in range(num_steps)]


def generate_power_levels(start_mw: float, step_mw: float, max_mw: float) -> List[float]:
    """Additive level ramp from ``start`` to ``max`` in ``step`` increments
    (same boundary logic as the existing Live-tab width sweep).

    In the Automated Routine UI these values are **diode current percent**
    (0–100), not mW; the parameter names are kept for call-site compatibility.
    A ``step`` of 0 with ``start <= max`` yields a single level.
    """
    if start_mw <= 0:
        raise ValueError("start current % must be > 0")
    if max_mw < start_mw:
        raise ValueError("max current % must be >= start")

    levels = [start_mw]
    if step_mw <= 0:
        return levels
    level = start_mw
    while True:
        nxt = level + step_mw
        if nxt > max_mw + 1e-9:
            break
        levels.append(nxt)
        level = nxt
    return levels


@dataclass
class RoutineStep:
    """One step of the routine plan.

    ``kind == "set_power"``: set diode current percent and turn emission ON
    (connect leaves emission off; the run path arms it).

    ``kind == "fire"``: fire one PMU pulse at the current width (and the
    most recently set current %, recorded for the CSV).
    """

    kind: Literal["set_power", "fire"]
    power_mw: Optional[float] = None  # diode current % (field name kept for CSV/meta)
    width_s: Optional[float] = None
    label: str = ""


def build_routine_plan(widths_s: List[float], powers_mw: List[float]) -> List[RoutineStep]:
    """For each current-% level (low -> high): one ``set_power`` step, then one
    ``fire`` step per width (low -> high). Encodes "low-current pulse at
    various widths, then increase current %, repeat until something is seen."
    """
    if not widths_s:
        raise ValueError("no widths configured")
    if not powers_mw:
        raise ValueError("no current % levels configured")

    plan: List[RoutineStep] = []
    for current_pct in powers_mw:
        plan.append(
            RoutineStep(
                kind="set_power",
                power_mw=current_pct,
                label=f"Set laser current \u2192 {current_pct:.3g} %",
            )
        )
        for width_s in widths_s:
            plan.append(
                RoutineStep(
                    kind="fire",
                    power_mw=current_pct,
                    width_s=width_s,
                    label=f"Fire {format_time_compact(width_s)} @ {current_pct:.3g} %",
                )
            )
    return plan


def estimate_duration_s(plan: List[RoutineStep], settle_s: float, interval_s: float) -> float:
    """Sum of the wait-after time for each step (settle after a current
    change, fire-interval after a pulse) — matches how ``_routine_tick``
    schedules the next step in the GUI."""
    total = 0.0
    for step in plan:
        total += settle_s if step.kind == "set_power" else interval_s
    return total


def describe_plan(plan: List[RoutineStep], settle_s: float, interval_s: float) -> str:
    """Multi-line human-readable summary of a plan, for the Preview dialog."""
    n_fires = sum(1 for s in plan if s.kind == "fire")
    n_powers = sum(1 for s in plan if s.kind == "set_power")
    total_s = estimate_duration_s(plan, settle_s, interval_s)
    lines = [
        f"{n_powers} current % level(s), {n_fires} fire(s) total, "
        f"~{total_s:.1f}s estimated duration.",
        "",
    ]
    for i, step in enumerate(plan, start=1):
        lines.append(f"{i:>3}. {step.label}")
    return "\n".join(lines)
