from __future__ import annotations

from typing import List, Optional

from .limits import VoltageRangeMode


def frange(start: float, stop: float, step: float) -> List[float]:
    """Simple float range with rounding to 3 decimals."""
    values: List[float] = []
    if step == 0:
        return values
    increasing = step > 0
    v = start
    if increasing:
        while v <= stop:
            values.append(round(v, 3))
            v += step
    else:
        while v >= stop:
            values.append(round(v, 3))
            v += step
    return values


def compute_voltage_range(
    *,
    start_v: float,
    stop_v: float,
    step_v: float,
    sweep_type: str,
    mode: str = VoltageRangeMode.FIXED_STEP,
    neg_stop_v: Optional[float] = None,
    sweep_rate_v_per_s: Optional[float] = None,
    voltage_time_s: Optional[float] = None,
    step_delay_s: Optional[float] = None,
    num_steps: Optional[int] = None,
) -> List[float]:
    """Build a voltage list for a sweep."""

    def travel_distance(v_start: float, v_stop_pos: float, kind: str, v_stop_neg_abs: Optional[float]) -> float:
        if kind == "PS":
            return abs(v_stop_pos - v_start) + abs(v_start - v_stop_pos)
        if kind == "NS":
            neg_target = -abs(v_stop_neg_abs if v_stop_neg_abs is not None else v_stop_pos)
            return abs(neg_target - v_start) + abs(v_start - neg_target)
        # FS
        neg_target = -abs(v_stop_neg_abs if v_stop_neg_abs is not None else v_stop_pos)
        return (
            abs(v_stop_pos - v_start)
            + abs(neg_target - v_stop_pos)
            + abs(v_start - neg_target)
        )

    # Determine effective step size for non-fixed-step modes
    effective_step_v = step_v
    if mode == VoltageRangeMode.FIXED_SWEEP_RATE:
        # Need sweep rate and step delay to determine step size
        if sweep_rate_v_per_s is None or (step_delay_s is None or step_delay_s <= 0):
            # Fallback to provided step_v if insufficient info
            effective_step_v = step_v
        else:
            effective_step_v = max(1e-9, abs(sweep_rate_v_per_s) * float(step_delay_s))
    elif mode == VoltageRangeMode.FIXED_VOLTAGE_TIME:
        # Use total time and step delay to compute number of steps, then step size from path length
        if voltage_time_s is not None and step_delay_s is not None and step_delay_s > 0:
            steps_float = max(1.0, float(voltage_time_s) / float(step_delay_s))
            # If explicit num_steps provided, prefer it
            steps_float = float(num_steps) if num_steps and num_steps > 0 else steps_float
            dist = travel_distance(start_v, stop_v, sweep_type, abs(neg_stop_v) if neg_stop_v is not None else None)
            effective_step_v = max(1e-9, dist / steps_float)
        else:
            effective_step_v = step_v

    step = effective_step_v if effective_step_v is not None else step_v

    if sweep_type == "NS":
        neg_target = -abs(neg_stop_v if neg_stop_v is not None else stop_v)
        return frange(start_v, neg_target, -abs(step)) + frange(neg_target, start_v, abs(step))
    if sweep_type == "PS":
        return frange(start_v, stop_v, abs(step)) + frange(stop_v, start_v, -abs(step))
    if sweep_type == "HS":
        # Half sweep: start to midpoint between start and stop
        midpoint = (start_v + stop_v) / 2.0
        return frange(start_v, midpoint, abs(step))
    # Default: Full sweep (FS) - triangle pattern (0 → +V → 0 → -V → 0)
    # If neg_stop_v not provided, default to symmetric negative (-stop_v)
    if neg_stop_v is None:
        neg_target = -abs(stop_v)  # Default symmetric negative
    else:
        neg_target = -abs(neg_stop_v)

    return (
        frange(start_v, stop_v, abs(step))
        + frange(stop_v, neg_target, -abs(step))
        + frange(neg_target, start_v, abs(step))
    )


__all__ = ["compute_voltage_range", "frange"]
