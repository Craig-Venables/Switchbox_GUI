"""Build absolute post-program read times for SMU/TSP timed retention."""

from __future__ import annotations

import math
from typing import Any, Dict, List, MutableMapping, Optional, Tuple

MAX_READ_POINTS = 100_000
EARLY_BURST_LINEAR = [0.05, 0.1, 0.2, 0.5, 1.0]


def _dedupe_sorted(intervals: List[float], tol: float = 1e-12) -> List[float]:
    if not intervals:
        return []
    out = [float(intervals[0])]
    for t in intervals[1:]:
        t = float(t)
        if t > out[-1] + tol:
            out.append(t)
    return out


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
    while t < duration - 1e-9:
        intervals.append(t)
        t += every
        if len(intervals) >= MAX_READ_POINTS:
            break
    if not intervals or intervals[-1] < duration - 1e-9:
        intervals.append(duration)
    return intervals


def build_linear_read_intervals(t_min_s: float, t_max_s: float, num_reads: int) -> List[float]:
    """Uniform spacing from t_min_s through t_max_s (inclusive endpoints)."""
    t_min = float(t_min_s)
    t_max = float(t_max_s)
    n = int(num_reads)
    if t_min <= 0:
        raise ValueError(f"t_min_s must be > 0, got {t_min}")
    if t_max <= t_min:
        raise ValueError(f"t_max_s must be > t_min_s, got {t_max} <= {t_min}")
    if n < 1:
        raise ValueError(f"num_reads must be >= 1, got {n}")
    if n == 1:
        return [t_max]
    if n > MAX_READ_POINTS:
        n = MAX_READ_POINTS
    step = (t_max - t_min) / (n - 1)
    return [t_min + i * step for i in range(n)]


def build_logarithmic_read_intervals(
    t_min_s: float,
    t_max_s: float,
    num_reads: int,
    *,
    include_early_burst: bool = False,
) -> List[float]:
    """
    Log-spaced read times after program pulse (absolute seconds since pulse end).

    When ``include_early_burst`` and ``t_min_s < 1``, prepends linear points
    0.05–1.0 s then log-spaced reads from max(1.0, t_min) → t_max.
    """
    t_min = float(t_min_s)
    t_max = float(t_max_s)
    n = int(num_reads)
    if t_min <= 0:
        raise ValueError(f"t_min_s must be > 0, got {t_min}")
    if t_max <= t_min:
        raise ValueError(f"t_max_s must be > t_min_s, got {t_max} <= {t_min}")
    if n < 1:
        raise ValueError(f"num_reads must be >= 1, got {n}")
    if n > MAX_READ_POINTS:
        n = MAX_READ_POINTS

    intervals: List[float] = []
    if include_early_burst and t_min < 1.0:
        intervals.extend(EARLY_BURST_LINEAR)
        log_min = max(1.0, t_min)
    else:
        log_min = t_min

    if log_min >= t_max - 1e-15:
        intervals.append(t_max)
        return _dedupe_sorted(intervals)[:MAX_READ_POINTS]

    log_points = max(2, n) if not intervals else max(2, n)
    log_span = [
        10 ** (math.log10(log_min) + i * (math.log10(t_max) - math.log10(log_min)) / (log_points - 1))
        for i in range(log_points)
    ]
    intervals.extend(log_span)
    return _dedupe_sorted(intervals)[:MAX_READ_POINTS]


def build_schedule_intervals(
    schedule_mode: str,
    t_min_s: float,
    t_max_s: float,
    num_reads: int,
    *,
    include_early_burst: bool = False,
    read_intervals: Optional[List[float]] = None,
) -> List[float]:
    """Build read interval list from schedule mode or explicit override."""
    if read_intervals:
        parsed = [float(x) for x in read_intervals if float(x) > 0]
        if not parsed:
            raise ValueError("read_intervals must contain positive values")
        return _dedupe_sorted(parsed)[:MAX_READ_POINTS]

    mode = (schedule_mode or "log").strip().lower()
    if mode == "linear":
        return build_linear_read_intervals(t_min_s, t_max_s, num_reads)
    if mode == "log":
        return build_logarithmic_read_intervals(
            t_min_s, t_max_s, num_reads, include_early_burst=include_early_burst
        )
    raise ValueError(f"Unknown schedule_mode: {schedule_mode!r}")


def intervals_to_wait_deltas(intervals: List[float]) -> List[float]:
    """Convert absolute post-pulse times to wait-before-read deltas (first wait = intervals[0])."""
    if not intervals:
        return []
    waits: List[float] = []
    prev = 0.0
    for t in intervals:
        waits.append(max(0.0, float(t) - prev))
        prev = float(t)
    return waits


def format_duration_clock(duration_s: float) -> str:
    duration = float(duration_s)
    if duration <= 0:
        return "0 s"
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
    return clock


def format_timed_retention_eta(every_s: float, duration_s: float) -> str:
    """Human-readable wall-clock estimate for Timed Retention (hours + h/m breakdown)."""
    every = float(every_s)
    duration = float(duration_s)
    if every <= 0 or duration <= 0:
        return "Estimated time: enter positive Read Every and Retention Duration"
    intervals = build_regular_read_intervals(every, duration)
    n_interval = len(intervals)
    hours = duration / 3600.0
    clock = format_duration_clock(duration)
    return (
        f"Estimated time to complete: ~ {hours:.2f} h ({clock}) | "
        f"{n_interval} interval reads + t=0"
    )


def format_log_retention_eta(t_max_s: float, num_reads: int = 0) -> str:
    """Wall-clock estimate for Log Retention (dominated by t_max_s)."""
    t_max = float(t_max_s)
    if t_max <= 0:
        return "Estimated time: enter positive t_max"
    hours = t_max / 3600.0
    clock = format_duration_clock(t_max)
    n_part = f" | {int(num_reads)} log reads" if num_reads else ""
    return f"Estimated time to complete: ~ {hours:.2f} h ({clock}){n_part}"


def format_log_retention_summary(intervals: List[float]) -> str:
    """Summary string for log retention schedule."""
    if not intervals:
        return "No read intervals"
    t_min, t_max = intervals[0], intervals[-1]
    decades = math.log10(t_max / t_min) if t_min > 0 and t_max > t_min else 0.0
    ppd = len(intervals) / decades if decades > 0 else len(intervals)
    return (
        f"{len(intervals)} reads | ~{ppd:.1f} pts/decade | "
        f"t = {t_min:g} s … {t_max:g} s"
    )


def format_volatile_screening_eta(
    burst_t_max_s: float,
    num_reads: int,
    *,
    include_slow_tail: bool = False,
    t_max_s: Optional[float] = None,
) -> str:
    """ETA for volatile screening (burst + optional slow tail)."""
    burst = float(burst_t_max_s)
    if burst <= 0:
        return "Estimated time: enter positive burst duration"
    if include_slow_tail and t_max_s is not None and float(t_max_s) > burst:
        tail = float(t_max_s)
        return (
            f"Estimated time: ~ {format_duration_clock(burst)} burst ({num_reads} reads) + "
            f"~ {format_duration_clock(tail)} slow tail"
        )
    return f"Estimated time: ~ {format_duration_clock(burst)} ({num_reads} on-instrument reads)"


def _parse_read_intervals_field(ri: Any) -> List[float]:
    if isinstance(ri, str):
        return [float(x.strip()) for x in ri.split(",") if x.strip()]
    if isinstance(ri, (list, tuple)):
        return [float(x) for x in ri]
    return []


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

    parsed = _parse_read_intervals_field(out.get("read_intervals"))
    if parsed:
        out["read_intervals"] = parsed
        return out

    every_s = float(every) if every is not None else 60.0
    duration_s = float(duration) if duration is not None else 10000.0
    out["read_intervals"] = build_regular_read_intervals(every_s, duration_s)
    return out


def normalize_log_retention_params(params: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Convert GUI Log Retention fields into ``read_intervals``."""
    out = dict(params)
    out.pop("read_every_s", None)
    out.pop("retention_duration_s", None)

    parsed = _parse_read_intervals_field(out.get("read_intervals"))
    if parsed:
        out["read_intervals"] = parsed
        return out

    t_min = float(out.pop("t_min_s", 0.1))
    t_max = float(out.pop("t_max_s", 86400.0))
    num_reads = int(out.pop("num_reads", 80))
    include_burst = bool(out.pop("include_early_burst", True))
    out["read_intervals"] = build_logarithmic_read_intervals(
        t_min, t_max, num_reads, include_early_burst=include_burst
    )
    return out


def normalize_volatile_screening_params(params: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Convert GUI Volatile Screening fields into burst/tail interval lists."""
    out = dict(params)

    parsed = _parse_read_intervals_field(out.get("read_intervals"))
    schedule_mode = str(out.get("schedule_mode", "log")).strip().lower()
    t_min = float(out.get("t_min_s", 0.001))
    burst_t_max = float(out.get("burst_t_max_s", out.get("t_max_s", 5.0)))
    num_reads = int(out.get("num_reads", 50))
    include_burst = bool(out.get("include_early_burst", False))

    if parsed:
        burst_intervals = _dedupe_sorted(parsed)
    else:
        burst_intervals = build_schedule_intervals(
            schedule_mode,
            t_min,
            burst_t_max,
            num_reads,
            include_early_burst=include_burst,
        )

    out["burst_intervals"] = burst_intervals
    out["burst_wait_deltas"] = intervals_to_wait_deltas(burst_intervals)

    include_slow_tail = bool(out.get("include_slow_tail", False))
    t_max = float(out.get("t_max_s", burst_t_max))
    slow_start = float(out.get("slow_tail_start_s", 10.0))
    tail_intervals: List[float] = []
    if include_slow_tail and t_max > slow_start + 1e-9:
        tail_num = int(out.get("slow_tail_num_reads", 30))
        tail_intervals = build_logarithmic_read_intervals(
            slow_start, t_max, tail_num, include_early_burst=False
        )
    out["slow_tail_intervals"] = tail_intervals
    return out


def classify_volatile_screening(
    timestamps: List[float],
    resistances: List[float],
    operations: List[str],
    *,
    retention_threshold: float = 0.85,
    min_switch_ratio: float = 0.05,
    t_pulse_end: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Classify volatile vs non-volatile from retention screening data.

    Uses baseline and post_pulse operations; retention points for f(t).
    Times are converted to seconds since pulse end when ``t_pulse_end`` is given.
    """
    base_idx = [i for i, op in enumerate(operations) if op == "baseline"]
    post_idx = [i for i, op in enumerate(operations) if op == "post_pulse"]
    ret_idx = [i for i, op in enumerate(operations) if op in ("retention", "slow_tail")]

    if not base_idx or not post_idx:
        return {
            "verdict": "INCONCLUSIVE — missing baseline or post-pulse read",
            "retention_fraction_final": None,
            "retention_fraction_early": None,
            "retention_fraction_100ms": None,
            "relaxation_time_50pct": None,
            "relaxation_time_90pct": None,
            "switch_ratio": None,
        }

    r_base = float(resistances[base_idx[0]])
    r_prog = float(resistances[post_idx[0]])
    delta = r_prog - r_base
    switch_ratio = abs(delta) / abs(r_base) if abs(r_base) > 1e-15 else 0.0

    if switch_ratio < min_switch_ratio:
        return {
            "verdict": "INCONCLUSIVE — insufficient switching",
            "retention_fraction_final": None,
            "retention_fraction_early": None,
            "retention_fraction_100ms": None,
            "relaxation_time_50pct": None,
            "relaxation_time_90pct": None,
            "switch_ratio": switch_ratio,
            "r_base": r_base,
            "r_prog": r_prog,
        }

    t0 = t_pulse_end if t_pulse_end is not None else timestamps[post_idx[0]]

    def _retention_fraction(r_val: float) -> float:
        return (r_val - r_base) / delta

    t_ret: List[float] = []
    f_ret: List[float] = []
    for i in ret_idx:
        t_since = max(0.0, float(timestamps[i]) - t0)
        t_ret.append(t_since)
        f_ret.append(_retention_fraction(float(resistances[i])))

    if not t_ret:
        f_post = _retention_fraction(r_prog)
        return {
            "verdict": "MARGINAL — no retention reads",
            "retention_fraction_final": f_post,
            "retention_fraction_early": f_post,
            "retention_fraction_100ms": f_post,
            "relaxation_time_50pct": None,
            "relaxation_time_90pct": None,
            "switch_ratio": switch_ratio,
            "r_base": r_base,
            "r_prog": r_prog,
        }

    t_max = max(t_ret)
    t_early_target = min(10.0, t_max * 0.1)

    def _f_at(target: float) -> float:
        if not t_ret:
            return _retention_fraction(r_prog)
        best = min(range(len(t_ret)), key=lambda j: abs(t_ret[j] - target))
        return f_ret[best]

    f_final = f_ret[-1]
    f_early = _f_at(t_early_target)
    f_100ms = _f_at(0.1)

    def _interp_crossing(threshold: float) -> Optional[float]:
        """Time when f drops to threshold (interpolated), searching from t=0."""
        points = [(0.0, _retention_fraction(r_prog))] + list(zip(t_ret, f_ret))
        points.sort(key=lambda x: x[0])
        for j in range(len(points) - 1):
            t_a, f_a = points[j]
            t_b, f_b = points[j + 1]
            if f_a >= threshold >= f_b or f_a <= threshold <= f_b:
                if abs(f_b - f_a) < 1e-15:
                    return t_b
                frac = (threshold - f_a) / (f_b - f_a)
                return t_a + frac * (t_b - t_a)
        return None

    relax_50 = _interp_crossing(0.5)
    relax_90 = _interp_crossing(0.1)

    if f_final >= retention_threshold and (f_early - f_final) < 0.15:
        verdict = "NON-VOLATILE"
    elif f_final < 0.50 or f_early < 0.60 or f_100ms < 0.70:
        verdict = "VOLATILE"
    else:
        verdict = "MARGINAL — partial retention"

    return {
        "verdict": verdict,
        "retention_fraction_final": f_final,
        "retention_fraction_early": f_early,
        "retention_fraction_100ms": f_100ms,
        "relaxation_time_50pct": relax_50,
        "relaxation_time_90pct": relax_90,
        "switch_ratio": switch_ratio,
        "r_base": r_base,
        "r_prog": r_prog,
    }


def fit_log_retention_decay(
    timestamps: List[float],
    resistances: List[float],
    operations: List[str],
    *,
    t_pulse_end: Optional[float] = None,
) -> Optional[Dict[str, float]]:
    """
    Fit R(t) = R0 * (1 + alpha * log(1 + t)) on post_pulse + retention points.

    Returns dict with r0, alpha, r_squared or None if fit fails.
    """
    try:
        import warnings

        import numpy as np
        from scipy import optimize
        from scipy.optimize import curve_fit
    except ImportError:
        return None

    post_idx = [i for i, op in enumerate(operations) if op == "post_pulse"]
    ret_idx = [i for i, op in enumerate(operations) if op in ("retention", "slow_tail")]
    use_idx = post_idx + ret_idx
    if len(use_idx) < 3:
        return None

    t0 = t_pulse_end if t_pulse_end is not None else (
        timestamps[post_idx[0]] if post_idx else timestamps[use_idx[0]]
    )
    t_arr = np.array([max(0.0, timestamps[i] - t0) for i in use_idx], dtype=float)
    r_arr = np.array([resistances[i] for i in use_idx], dtype=float)

    if np.any(~np.isfinite(t_arr)) or np.any(~np.isfinite(r_arr)) or np.any(r_arr <= 0):
        return None

    def retention_model(t, r0, alpha):
        return r0 * (1.0 + alpha * np.log1p(t))

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=optimize.OptimizeWarning)
            popt, _ = curve_fit(retention_model, t_arr, r_arr, maxfev=5000)
        r0, alpha = float(popt[0]), float(popt[1])
        pred = retention_model(t_arr, r0, alpha)
        ss_res = float(np.sum((r_arr - pred) ** 2))
        ss_tot = float(np.sum((r_arr - np.mean(r_arr)) ** 2))
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        return {"r0": r0, "alpha": alpha, "r_squared": r_squared}
    except Exception:
        return None
