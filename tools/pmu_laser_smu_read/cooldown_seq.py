"""Explicit cool-down pulse/delay sequence parsing and planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from tools.pmu_laser_smu_read.routine import parse_time_value

MIN_SEG_S = 20e-9
MIN_WIDTH_S = 40e-9
MAX_WIDTH_S = 40.0
MAX_PULSES = 500

# Each line is delay-before-pulse, then pulse width. The first delay is the
# OFF gap immediately after the main write pulse.
DEFAULT_COOLDOWN_SEQUENCE_TEXT = (
    "1 us, 1 us\n"
    "2 us, 500 ns\n"
    "5 us, 100 ns"
)


def parse_cooldown_sequence(text: str) -> List[Tuple[float, float]]:
    """Parse multiline cool-down text into ``(delay_before_s, width_s)`` pairs.

    Each non-empty, non-``#`` line is ``delay, pulse`` using the same unit
    rules as Width (bare number = µs). Delay is the LOW time *before* that
    pulse (after the previous pulse — or after the write for the first line).
    """
    pairs: List[Tuple[float, float]] = []
    raw = text if text is not None else ""
    for lineno, line in enumerate(raw.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "," in s:
            left, right = s.split(",", 1)
        else:
            parts = s.split()
            if len(parts) != 2:
                raise ValueError(
                    f"cool-down line {lineno}: expected 'delay, pulse' got {line!r}"
                )
            left, right = parts[0], parts[1]
        try:
            d = parse_time_value(left)
            w = parse_time_value(right)
        except ValueError as exc:
            raise ValueError(f"cool-down line {lineno}: {exc}") from exc
        if w < MIN_WIDTH_S:
            raise ValueError(
                f"cool-down line {lineno}: pulse width must be >= {MIN_WIDTH_S * 1e9:.0f} ns"
            )
        if w > MAX_WIDTH_S:
            raise ValueError(
                f"cool-down line {lineno}: pulse width exceeds {MAX_WIDTH_S:g} s"
            )
        if d <= 0:
            raise ValueError(f"cool-down line {lineno}: delay must be > 0")
        pairs.append((d, w))
    if len(pairs) > MAX_PULSES - 1:
        raise ValueError(
            f"cool-down sequence has {len(pairs)} pulses; max is {MAX_PULSES - 1} (SegArb)"
        )
    return pairs


def _fp(x: float) -> str:
    """Plain decimal for EX char* (avoid ``E-`` so Clarius never splits the string)."""
    if x == 0.0:
        return "0"
    s = f"{float(x):.12g}"
    if "e" in s.lower():
        # Very small/large: fixed decimals (still no comma, no exponent).
        s = f"{float(x):.12f}".rstrip("0").rstrip(".")
    return s or "0"


def format_cooldown_sequence_wire(sequence: Sequence[Tuple[float, float]]) -> str:
    """Encode for KXCI EX ``cdSequence`` without commas (commas split EX args).

    Format: ``delay:width;delay:width;...`` (delay before each cool-down pulse).
    """
    return ";".join(f"{_fp(float(d))}:{_fp(float(w))}" for d, w in sequence)


@dataclass(frozen=True)
class CooldownPlan:
    """Write + explicit cool-down tail ready for preview / EX."""

    num_pulses: int
    widths: List[float]
    offs: List[float]
    sequence: List[Tuple[float, float]]
    wire: str
    total_cd_s: float


def plan_cooldown_sequence(
    *,
    width_s: float,
    rise_s: float,
    fall_s: float,
    sequence: Sequence[Tuple[float, float]],
) -> CooldownPlan:
    """Build write + cool-down widths/offs from ``(delay_before, width)`` pairs.

    ``offs[0]`` is the gap after the write (= first line's delay). Each
    cool-down pulse then uses the *next* line's delay as its trailing OFF
    (last pulse gets ``MIN_SEG_S``).
    """
    if width_s < MIN_WIDTH_S:
        raise ValueError(f"width must be >= {MIN_WIDTH_S * 1e9:.0f} ns")
    seq = [(max(MIN_SEG_S, float(d)), float(w)) for d, w in sequence]
    if len(seq) + 1 > MAX_PULSES:
        raise ValueError(f"too many cool-down pulses (max {MAX_PULSES - 1})")

    widths = [float(width_s)] + [w for _, w in seq]
    if not seq:
        offs = [MIN_SEG_S]
    else:
        offs = [seq[0][0]]  # after write
        for i in range(len(seq)):
            if i + 1 < len(seq):
                offs.append(seq[i + 1][0])
            else:
                offs.append(MIN_SEG_S)

    total_cd = 0.0
    if seq:
        # First delay (after write) + each rise/width/fall + trailing offs for CD pulses
        total_cd += seq[0][0]
        for i, (_, w) in enumerate(seq):
            total_cd += rise_s + w + fall_s
            total_cd += offs[i + 1]

    return CooldownPlan(
        num_pulses=1 + len(seq),
        widths=widths,
        offs=offs,
        sequence=list(seq),
        wire=format_cooldown_sequence_wire(seq),
        total_cd_s=total_cd,
    )


def avg_power_polyline(
    *,
    width_s: float,
    rise_s: float,
    fall_s: float,
    sequence: Sequence[Tuple[float, float]],
    vhigh: float,
    delay_before_s: float = 0.0,
) -> Tuple[List[float], List[float]]:
    """Step polyline of local average power (duty * vhigh) for plotting."""
    times: List[float] = []
    volts: List[float] = []
    t = max(0.0, float(delay_before_s))
    plan = plan_cooldown_sequence(
        width_s=width_s, rise_s=rise_s, fall_s=fall_s, sequence=sequence
    )

    def _step(t0: float, t1: float, v: float) -> None:
        times.extend([t0, t1])
        volts.extend([v, v])

    for i, (w, off) in enumerate(zip(plan.widths, plan.offs)):
        slot = rise_s + w + fall_s + off
        if slot <= 0:
            continue
        if i == 0:
            duty_v = float(vhigh)
        else:
            duty_v = (float(w) / slot) * float(vhigh)
        _step(t, t + slot, duty_v)
        t += slot
    return times, volts
