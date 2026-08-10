"""Pure-logic helpers for the Laser ↔ SMU interaction routines tab.

Four protocols sharing a single SMU amplitude |V| (polarity ±V):

1. Laser-effect polarity blocks — SMU / laser / wait pattern per polarity
2. Alternating ±V with laser between each SMU pulse
3. SMU width sweep — for each width, +V then −V
4. SMU endurance — N cycles of +V / −V at fixed width

No tkinter deps — mirrors ``routine.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

try:
    from routine import format_time_compact, parse_width_list
except ImportError:  # pragma: no cover
    from tools.pmu_laser_smu_read.routine import format_time_compact, parse_width_list

ProtocolName = Literal[
    "laser_effect",
    "alt_polarity_laser",
    "smu_width_sweep",
    "smu_endurance",
]

PROTOCOL_LABELS: dict[str, str] = {
    "laser_effect": "Laser-effect polarity blocks",
    "alt_polarity_laser": "Alternating ±V with laser",
    "smu_width_sweep": "SMU width sweep (± alternate)",
    "smu_endurance": "SMU endurance (± fixed)",
}


@dataclass
class InteractionStep:
    """One stimulus or wait in an interaction plan.

    ``kind == "smu_pulse"``: queue an SMU set/reset pulse at ``smu_v``.
    ``kind == "laser_fire"``: queue a PMU TTL laser pulse (shape from Live params).
    ``kind == "wait"``: no stimulus — GUI sleeps ``wait_s`` (or the shared interval).
    """

    kind: Literal["smu_pulse", "laser_fire", "wait"]
    smu_v: Optional[float] = None
    smu_width_s: Optional[float] = None
    wait_s: Optional[float] = None
    label: str = ""


def _require_amplitude(amplitude_v: float) -> float:
    amp = abs(float(amplitude_v))
    if amp <= 0:
        raise ValueError("SMU |V| must be > 0")
    if amp > 200:
        raise ValueError("SMU |V| must be ≤ 200 V")
    return amp


def _require_width(width_s: float) -> float:
    w = float(width_s)
    if w < 1e-6 or w > 40.0:
        raise ValueError("SMU pulse width must be between 1 µs and 40 s")
    return w


def _require_positive_int(n: int, name: str) -> int:
    ni = int(n)
    if ni < 1:
        raise ValueError(f"{name} must be ≥ 1")
    return ni


def _smu_step(v: float, width_s: float, label: str | None = None) -> InteractionStep:
    return InteractionStep(
        kind="smu_pulse",
        smu_v=v,
        smu_width_s=width_s,
        label=label or f"SMU {v:+.3g} V / {format_time_compact(width_s)}",
    )


def _laser_step(label: str = "Laser fire") -> InteractionStep:
    return InteractionStep(kind="laser_fire", label=label)


def _wait_step(wait_s: float, label: str | None = None) -> InteractionStep:
    return InteractionStep(
        kind="wait",
        wait_s=wait_s,
        label=label or f"Wait {wait_s:.3g} s",
    )


def build_laser_effect_plan(
    amplitude_v: float,
    smu_width_s: float,
    interval_s: float,
    repeats: int = 1,
) -> List[InteractionStep]:
    """For each polarity P in {+|V|, −|V|}:

    SMU P → Laser → wait → SMU P → wait → Laser → wait → SMU P → Laser → wait

    Then the opposite polarity. ``repeats`` repeats the whole ± pair.
    """
    amp = _require_amplitude(amplitude_v)
    width_s = _require_width(smu_width_s)
    interval = float(interval_s)
    if interval <= 0:
        raise ValueError("interval must be > 0")
    n_rep = _require_positive_int(repeats, "repeats")

    plan: List[InteractionStep] = []
    for rep in range(n_rep):
        rep_tag = f" (rep {rep + 1}/{n_rep})" if n_rep > 1 else ""
        for sign, name in ((+1.0, "+"), (-1.0, "−")):
            p = sign * amp
            plan.append(_smu_step(p, width_s, f"{name} block{rep_tag}: SMU {p:+.3g} V"))
            plan.append(_laser_step(f"{name} block{rep_tag}: Laser"))
            plan.append(_wait_step(interval))
            plan.append(_smu_step(p, width_s, f"{name} block{rep_tag}: SMU {p:+.3g} V"))
            plan.append(_wait_step(interval))
            plan.append(_laser_step(f"{name} block{rep_tag}: Laser"))
            plan.append(_wait_step(interval))
            plan.append(_smu_step(p, width_s, f"{name} block{rep_tag}: SMU {p:+.3g} V"))
            plan.append(_laser_step(f"{name} block{rep_tag}: Laser"))
            plan.append(_wait_step(interval, f"{name} block{rep_tag}: end wait"))
    return plan


def build_alt_polarity_laser_plan(
    amplitude_v: float,
    smu_width_s: float,
    interval_s: float,
    cycles: int = 20,
) -> List[InteractionStep]:
    """Repeat N cycles: +V → Laser → −V → Laser → … (wait after every stimulus)."""
    amp = _require_amplitude(amplitude_v)
    width_s = _require_width(smu_width_s)
    interval = float(interval_s)
    if interval <= 0:
        raise ValueError("interval must be > 0")
    n = _require_positive_int(cycles, "cycles")

    plan: List[InteractionStep] = []
    for i in range(n):
        tag = f"cycle {i + 1}/{n}"
        plan.append(_smu_step(+amp, width_s, f"{tag}: SMU {+amp:+.3g} V"))
        plan.append(_wait_step(interval))
        plan.append(_laser_step(f"{tag}: Laser"))
        plan.append(_wait_step(interval))
        plan.append(_smu_step(-amp, width_s, f"{tag}: SMU {-amp:+.3g} V"))
        plan.append(_wait_step(interval))
        plan.append(_laser_step(f"{tag}: Laser"))
        plan.append(_wait_step(interval))
    return plan


def build_smu_width_sweep_plan(
    amplitude_v: float,
    widths_s: Sequence[float],
    interval_s: float,
) -> List[InteractionStep]:
    """For each width (outer): +|V| → wait → −|V| → wait. No laser."""
    amp = _require_amplitude(amplitude_v)
    interval = float(interval_s)
    if interval <= 0:
        raise ValueError("interval must be > 0")
    widths = [ _require_width(w) for w in widths_s ]
    if not widths:
        raise ValueError("no SMU widths configured")

    plan: List[InteractionStep] = []
    for w in widths:
        wlab = format_time_compact(w)
        plan.append(_smu_step(+amp, w, f"width {wlab}: SMU {+amp:+.3g} V"))
        plan.append(_wait_step(interval))
        plan.append(_smu_step(-amp, w, f"width {wlab}: SMU {-amp:+.3g} V"))
        plan.append(_wait_step(interval))
    return plan


def build_smu_endurance_plan(
    amplitude_v: float,
    smu_width_s: float,
    interval_s: float,
    cycles: int = 20,
) -> List[InteractionStep]:
    """N cycles of +|V| → wait → −|V| → wait at fixed width. No laser."""
    amp = _require_amplitude(amplitude_v)
    width_s = _require_width(smu_width_s)
    interval = float(interval_s)
    if interval <= 0:
        raise ValueError("interval must be > 0")
    n = _require_positive_int(cycles, "cycles")

    plan: List[InteractionStep] = []
    for i in range(n):
        tag = f"cycle {i + 1}/{n}"
        plan.append(_smu_step(+amp, width_s, f"{tag}: SMU {+amp:+.3g} V"))
        plan.append(_wait_step(interval))
        plan.append(_smu_step(-amp, width_s, f"{tag}: SMU {-amp:+.3g} V"))
        plan.append(_wait_step(interval))
    return plan


def build_interaction_plan(
    protocol: ProtocolName | str,
    *,
    amplitude_v: float,
    smu_width_s: float,
    interval_s: float,
    repeats: int = 1,
    cycles: int = 20,
    widths_s: Optional[Sequence[float]] = None,
    widths_text: Optional[str] = None,
) -> List[InteractionStep]:
    """Dispatch to the named protocol builder."""
    key = str(protocol).strip()
    if key == "laser_effect":
        return build_laser_effect_plan(amplitude_v, smu_width_s, interval_s, repeats=repeats)
    if key == "alt_polarity_laser":
        return build_alt_polarity_laser_plan(
            amplitude_v, smu_width_s, interval_s, cycles=cycles
        )
    if key == "smu_width_sweep":
        if widths_s is None:
            widths_s = parse_width_list(widths_text or "")
        return build_smu_width_sweep_plan(amplitude_v, widths_s, interval_s)
    if key == "smu_endurance":
        return build_smu_endurance_plan(
            amplitude_v, smu_width_s, interval_s, cycles=cycles
        )
    raise ValueError(f"unknown protocol {protocol!r}")


def estimate_interaction_duration_s(plan: Sequence[InteractionStep], default_interval_s: float) -> float:
    """Sum wait times. Stimulus steps use ``default_interval_s`` only if the
    next step is not an explicit wait (plans always insert waits after
    stimuli, so stimulus steps contribute 0 here)."""
    total = 0.0
    for step in plan:
        if step.kind == "wait":
            total += float(step.wait_s if step.wait_s is not None else default_interval_s)
    return total


def describe_interaction_plan(
    plan: Sequence[InteractionStep],
    *,
    protocol: str,
    interval_s: float,
) -> str:
    """Multi-line human-readable summary for the Preview dialog."""
    n_smu = sum(1 for s in plan if s.kind == "smu_pulse")
    n_laser = sum(1 for s in plan if s.kind == "laser_fire")
    n_wait = sum(1 for s in plan if s.kind == "wait")
    total_s = estimate_interaction_duration_s(plan, interval_s)
    label = PROTOCOL_LABELS.get(protocol, protocol)
    lines = [
        f"{label}: {n_smu} SMU pulse(s), {n_laser} laser fire(s), "
        f"{n_wait} wait(s), ~{total_s:.1f}s estimated.",
        "",
    ]
    for i, step in enumerate(plan, start=1):
        lines.append(f"{i:>3}. {step.label}")
    return "\n".join(lines)


def protocol_needs_laser(protocol: ProtocolName | str) -> bool:
    return str(protocol).strip() in ("laser_effect", "alt_polarity_laser")
