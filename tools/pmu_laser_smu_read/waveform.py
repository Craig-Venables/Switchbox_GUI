"""TTL waveform builders for PMU CH1 laser gate (preview + duration estimates).

Times are in seconds. Levels are binary (vlow / vhigh).

Cool-down UX: pulse 0 of a cool-down train is IDENTICAL to a single/train
shot — full **Width**, the on-time already confirmed to reach the laser.
From there, EVERY subsequent pulse's on-time (Width) AND off-time (period)
decay/expand together, start → end, over the **Cool-down over** span,
following the chosen decay shape — i.e. progressively smaller, more widely
spaced pulses, which is what "turn the laser on and off to gradually cool
the device" actually means.

Crucially, the decay's starting point is pinned to width_s itself (NOT a
fixed ns-scale constant): an earlier version capped the very first
cool-down pulse at a hardcoded ~200 ns regardless of the user's Width, so
pulse widths (and therefore pulse count/spacing) barely changed no matter
what Width was set to. Anchoring the taper to width_s means a big Width
gets a slow, big-to-small taper and a small Width barely tapers at all —
exactly the "cool-down pulses should be tied to the sweep Width" behavior
that's expected. If the requested cool-down span can't even fit two
full-Width pulses, the taper's starting width shrinks automatically so a
meaningful multi-pulse ramp still fits (see plan_cooldown's shrink-to-fit
step) instead of forcing one giant pulse into too little time.

The last pulse decays down toward MIN_WIDTH_S, the PMU's true hardware
minimum pulse width — a real instrument limit, not a policy choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple

ModeName = Literal["single", "train", "cooldown"]
DecayName = Literal["linear", "exponential", "quadratic"]

MAX_TTL_VHIGH = 5.0
MIN_SEG_S = 20e-9
MIN_WIDTH_S = 40e-9
# PMU Segment ARB hardware allows up to 40 s per segment. Older Clarius
# USRLIB headers capped width/period at ~1 s, which silently rejected longer
# exposure pulses (e.g. 5 s typed as 5000000 µs). Match the hardware limit.
MAX_WIDTH_S = 40.0
MAX_PERIOD_S = 40.0
MIN_RISE_FALL_S = 20e-9
# seg_arb limit 2048; waveform uses ~4 segments/pulse + overhead
MAX_PULSES = 500
MAX_SEGMENTS = 2048

# EX / C mode ints: 0=single, 1=train, 2=cooldown linear, 3=exp, 4=quadratic
_COOLDOWN_MODE_INT = {"linear": 2, "exponential": 3, "quadratic": 4}


@dataclass(frozen=True)
class Segment:
    t0: float
    t1: float
    v: float


@dataclass
class WaveformPreview:
    mode: ModeName
    segments: List[Segment]
    laser_on_intervals: List[Tuple[float, float]]
    total_duration_s: float
    num_pulses: int


def _clamp_vhigh(vhigh: float) -> float:
    if vhigh < 0:
        raise ValueError("vhigh must be >= 0")
    if vhigh > MAX_TTL_VHIGH:
        raise ValueError(f"vhigh ({vhigh} V) exceeds TTL safety limit ({MAX_TTL_VHIGH} V)")
    return float(vhigh)


def validate_timing(
    *,
    width_s: float,
    rise_s: float,
    fall_s: float,
    period_s: float | None = None,
) -> None:
    if width_s < MIN_WIDTH_S:
        raise ValueError(f"width must be >= {MIN_WIDTH_S * 1e6:.3g} µs")
    if width_s > MAX_WIDTH_S:
        raise ValueError(
            f"width ({width_s:g} s) exceeds PMU Segment ARB max ({MAX_WIDTH_S:g} s). "
            f"Use e.g. '5 s' or '5e6 µs' for a 5-second pulse (max {MAX_WIDTH_S:g} s)."
        )
    if rise_s < MIN_RISE_FALL_S or fall_s < MIN_RISE_FALL_S:
        raise ValueError(f"rise/fall must be >= {MIN_RISE_FALL_S * 1e9:.0f} ns")
    if period_s is not None:
        # Soft check only — callers should prefer ensure_period_s() which
        # auto-bumps too-short periods instead of aborting a measurement.
        min_p = min_period_s(width_s=width_s, rise_s=rise_s, fall_s=fall_s)
        if period_s < min_p:
            raise ValueError(
                f"period ({period_s * 1e6:.4g} µs) must exceed rise+width+fall "
                f"({(rise_s + width_s + fall_s) * 1e6:.4g} µs)"
            )
        if period_s > MAX_PERIOD_S:
            raise ValueError(
                f"period ({period_s:g} s) exceeds PMU Segment ARB max ({MAX_PERIOD_S:g} s)"
            )


def min_period_s(*, width_s: float, rise_s: float, fall_s: float) -> float:
    """Shortest legal period for a fixed width/rise/fall pulse."""
    return rise_s + width_s + fall_s + MIN_SEG_S


def ensure_period_s(
    period_s: float,
    *,
    width_s: float,
    rise_s: float,
    fall_s: float,
) -> float:
    """Bump period up to the legal minimum if needed (never raises for period).

    Adds a tiny margin above the exact minimum so the value still passes the
    C module's ``period >= rise+width+fall+MIN_SEG`` check after KXCI float
    formatting / round-trip (exact equality is not reliable in double).
    """
    min_p = min_period_s(width_s=width_s, rise_s=rise_s, fall_s=fall_s)
    # 0.1% above the floor, or at least 1 ns — enough to survive format/
    # float round-trip without changing the waveform in any meaningful way.
    floor = min_p * 1.001 + 1e-9
    return max(float(period_s), floor)


def mode_to_int(mode: ModeName, decay: DecayName = "linear") -> int:
    """Map GUI mode (+ cool-down decay) to the C USRLIB mode int."""
    if mode == "single":
        return 0
    if mode == "train":
        return 1
    if mode == "cooldown":
        return _COOLDOWN_MODE_INT[decay]
    raise ValueError(f"unknown mode: {mode}")


def cooldown_value_at(
    i: int,
    n: int,
    start: float,
    end: float,
    decay: DecayName,
) -> float:
    """Interpolate start→end over n points with the given decay shape."""
    if n <= 1:
        return float(start)
    f = i / (n - 1)
    if decay == "linear":
        return start + (end - start) * f
    if decay == "exponential":
        if start <= 0:
            return float(end)
        # Guard ratio when end is tiny but positive.
        if end <= 0:
            return float(start)
        return start * ((end / start) ** f)
    if decay == "quadratic":
        return start + (end - start) * (f * f)
    raise ValueError(f"unknown decay: {decay}")


def cooldown_period_at(
    i: int,
    n: int,
    start_period_s: float,
    end_period_s: float,
    decay: DecayName,
) -> float:
    """Period of pulse i in a cool-down train (matches C USRLIB formulas)."""
    return cooldown_value_at(i, n, start_period_s, end_period_s, decay)


def cooldown_periods(
    n: int,
    start_period_s: float,
    end_period_s: float,
    decay: DecayName = "linear",
) -> List[float]:
    return [
        cooldown_period_at(i, n, start_period_s, end_period_s, decay)
        for i in range(n)
    ]


def format_width_s(w: float) -> str:
    """Human-readable width for GUI info (ns below 1 µs, else µs)."""
    if w < 1e-6:
        return f"{w * 1e9:.3g} ns"
    return f"{w * 1e6:.3g} µs"


def resolve_cooldown_width_bounds(
    width_s: float,
    cd_start_width_s: float | None = None,
    cd_end_width_s: float | None = None,
) -> Tuple[float, float]:
    """Resolve the cool-down pulse-WIDTH decay bounds.

    Defaults tie BOTH ends to the main pulse Width, instead of a fixed
    ns-scale constant that ignored it:
      - start = width_s  -> pulse 0 is exactly the confirmed-working, full
        on-time pulse (identical to a single/train shot); the taper then
        shrinks from there.
      - end   = MIN_WIDTH_S -> the last pulse shrinks down to the PMU's
        true hardware-minimum pulse width (a real instrument limit, not a
        policy choice).
    Explicit >0 overrides (kept for the EX API / back-compat) win.
    """
    cd_start = (
        float(cd_start_width_s)
        if cd_start_width_s is not None and cd_start_width_s > 0
        else float(width_s)
    )
    cd_end = (
        float(cd_end_width_s)
        if cd_end_width_s is not None and cd_end_width_s > 0
        else MIN_WIDTH_S
    )
    cd_start = max(MIN_WIDTH_S, cd_start)
    cd_end = max(MIN_WIDTH_S, cd_end)
    if cd_end > cd_start:
        cd_end = cd_start
    return cd_start, cd_end


def cooldown_widths(
    n: int,
    *,
    cd_start_width_s: float,
    cd_end_width_s: float,
    decay: DecayName = "linear",
) -> List[float]:
    """Per-pulse WIDTH for an n-pulse cool-down train, decaying
    cd_start_width_s -> cd_end_width_s (pulse 0 == cd_start_width_s exactly,
    i.e. the same on-time as a single/train shot when using the defaults
    from resolve_cooldown_width_bounds)."""
    if n <= 0:
        return []
    return [
        max(MIN_WIDTH_S, cooldown_value_at(i, n, cd_start_width_s, cd_end_width_s, decay))
        for i in range(n)
    ]


def plan_cooldown(
    *,
    width_s: float,
    rise_s: float,
    fall_s: float,
    span_s: float,
    decay: DecayName = "linear",
    cd_start_width_s: float | None = None,
    cd_end_width_s: float | None = None,
) -> Tuple[int, float, float, List[float], float, float]:
    """Plan a cool-down train: N pulses whose WIDTH decays
    ``cd_start_width_s`` → ``cd_end_width_s`` (pulse 0 == the full,
    confirmed-working on-time == ``width_s`` by default) while the PERIOD
    (off-time) simultaneously expands ``start_period_s`` → ``end_period_s``,
    over ``span_s``, following ``decay``.

    Both bounds default to being anchored to ``width_s`` (see
    resolve_cooldown_width_bounds): a big Width gets a slow, big-to-small
    taper; a small Width barely tapers at all — pulse count, spacing, AND
    per-pulse on-time all scale with whatever Width the user actually set,
    instead of a fixed ns-scale constant that used to make the taper nearly
    independent of Width.

    Shrink-to-fit: if span_s can't even fit two full-Width pulses, the
    STARTING width is shrunk (not the whole train forced to one giant
    pulse) so a meaningful multi-pulse taper still fits in the time given —
    i.e. "use smaller pulses" when the cool-down span is small relative to
    the main Width.

    Returns (num_pulses, start_period_s, end_period_s, periods,
             cd_start_width_s, cd_end_width_s) — the last two are the
    RESOLVED (possibly shrunk-to-fit) bounds actually used. Callers MUST
    pass these on to build_preview()/the EX command builders so the widths
    reported in the preview match what the C module will actually generate.
    """
    validate_timing(width_s=width_s, rise_s=rise_s, fall_s=fall_s)
    if span_s <= 0:
        raise ValueError("cool-down span must be > 0")

    cd_start, cd_end = resolve_cooldown_width_bounds(
        width_s, cd_start_width_s, cd_end_width_s
    )

    def _min_p(w: float) -> float:
        return min_period_s(width_s=w, rise_s=rise_s, fall_s=fall_s)

    # Shrink-to-fit: if the span can't even fit ~2 pulses at the starting
    # (full) width, drop the starting width until 2 pulses fit.
    if span_s < 2.0 * _min_p(cd_start) and cd_start > MIN_WIDTH_S:
        w_fit = span_s / 2.0 - rise_s - fall_s - MIN_SEG_S
        if w_fit >= MIN_WIDTH_S:
            cd_start = min(cd_start, w_fit)
            if cd_end > cd_start:
                cd_end = cd_start
        else:
            cd_start = MIN_WIDTH_S
            cd_end = MIN_WIDTH_S

    start_p = _min_p(cd_start)
    # Bump above the exact floor so EX formatting / float round-trip can't
    # push startPeriod just under the C module's minimum check (that was
    # returning -1 and never firing cool-down).
    start_p = ensure_period_s(start_p, width_s=cd_start, rise_s=rise_s, fall_s=fall_s)
    if span_s <= start_p:
        # Span too short even for a single pulse at the (possibly shrunk)
        # starting width — just the one pulse.
        return 1, start_p, start_p, [start_p], cd_start, cd_end

    end_min_p = ensure_period_s(
        _min_p(cd_end), width_s=cd_end, rise_s=rise_s, fall_s=fall_s
    )
    # Aim for a handful-to-dozens of pulses depending on span vs. pulse
    # width; the tail period grows well past the tightest packing so the
    # last gaps are meaningfully longer than the first.
    end_guess = max(end_min_p, start_p * 1.5, span_s * 0.2)
    n_guess = max(2, int(round(2.0 * span_s / (start_p + end_guess))))
    n_guess = min(n_guess, MAX_PULSES)

    def _widths(n_total: int) -> List[float]:
        return cooldown_widths(
            n_total, cd_start_width_s=cd_start, cd_end_width_s=cd_end, decay=decay
        )

    def _periods(n_total: int, end_period: float, widths: List[float]) -> List[float]:
        raw = cooldown_periods(n_total, start_p, end_period, decay)
        return [
            ensure_period_s(p, width_s=w, rise_s=rise_s, fall_s=fall_s)
            for p, w in zip(raw, widths)
        ]

    def _fit_end(n_total: int, widths: List[float]) -> float:
        """Binary-search end_p so sum(periods) ≈ span_s."""
        lo = start_p * 1.001
        hi = max(lo * 1.5, span_s)
        best = lo
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            total = sum(_periods(n_total, mid, widths))
            best = mid
            if abs(total - span_s) / max(span_s, 1e-15) < 0.01:
                break
            if total > span_s:
                hi = mid
            else:
                lo = mid
        return best

    n = 2
    widths = _widths(2)
    end_p = max(start_p * 1.5, span_s)
    for trial_n in range(n_guess, 1, -1):
        trial_widths = _widths(trial_n)
        fit = _fit_end(trial_n, trial_widths)
        total = sum(_periods(trial_n, fit, trial_widths))
        if total <= span_s * 1.05:
            n = trial_n
            end_p = fit
            widths = trial_widths
            break

    end_p = max(end_p, start_p)
    periods = _periods(n, end_p, widths)
    return n, start_p, end_p, periods, cd_start, cd_end


def estimate_cooldown_num_pulses(
    *,
    width_s: float,
    rise_s: float,
    fall_s: float,
    start_period_s: float | None = None,
    end_period_s: float | None = None,
    duration_s: float,
    decay: DecayName = "linear",
) -> int:
    """Estimate pulse count for a cool-down of duration_s (legacy + new callers)."""
    if start_period_s is None or end_period_s is None:
        n, _, _, _, _, _ = plan_cooldown(
            width_s=width_s,
            rise_s=rise_s,
            fall_s=fall_s,
            span_s=duration_s,
            decay=decay,
        )
        return n
    validate_timing(width_s=width_s, rise_s=rise_s, fall_s=fall_s)
    start_period_s = ensure_period_s(
        start_period_s, width_s=width_s, rise_s=rise_s, fall_s=fall_s
    )
    end_period_s = ensure_period_s(
        end_period_s, width_s=width_s, rise_s=rise_s, fall_s=fall_s
    )
    avg = 0.5 * (start_period_s + end_period_s)
    if avg <= 0:
        raise ValueError("invalid cool-down periods")
    n = max(1, int(round(duration_s / avg)))
    return min(n, MAX_PULSES)


def build_preview(
    mode: ModeName,
    *,
    vhigh: float = 5.0,
    vlow: float = 0.0,
    width_s: float = 10e-6,
    rise_s: float = 100e-9,
    fall_s: float = 100e-9,
    period_s: float = 100e-6,
    start_period_s: float = 100e-6,
    end_period_s: float = 1e-3,
    num_pulses: int = 1,
    delay_before_s: float = 0.0,
    decay: DecayName = "linear",
    cooldown_span_s: float | None = None,
    cd_start_width_s: float | None = None,
    cd_end_width_s: float | None = None,
) -> WaveformPreview:
    """Build a timeline preview of HIGH/LOW segments and laser-on intervals."""
    vhigh = _clamp_vhigh(vhigh)
    validate_timing(width_s=width_s, rise_s=rise_s, fall_s=fall_s)

    widths: List[float]
    if mode == "single":
        n = 1
        periods = [rise_s + width_s + fall_s + MIN_SEG_S]
        widths = [width_s]
    elif mode == "train":
        n = max(1, int(num_pulses))
        if n > MAX_PULSES:
            raise ValueError(f"num_pulses ({n}) exceeds max {MAX_PULSES} (seg_arb limit)")
        validate_timing(width_s=width_s, rise_s=rise_s, fall_s=fall_s)
        period_s = ensure_period_s(period_s, width_s=width_s, rise_s=rise_s, fall_s=fall_s)
        periods = [period_s] * n
        widths = [width_s] * n
    elif mode == "cooldown":
        if cooldown_span_s is not None and cooldown_span_s > 0:
            n, start_period_s, end_period_s, periods, cd_start, cd_end = plan_cooldown(
                width_s=width_s,
                rise_s=rise_s,
                fall_s=fall_s,
                span_s=cooldown_span_s,
                decay=decay,
                cd_start_width_s=cd_start_width_s,
                cd_end_width_s=cd_end_width_s,
            )
            widths = cooldown_widths(
                n, cd_start_width_s=cd_start, cd_end_width_s=cd_end, decay=decay
            )
        else:
            n = max(1, int(num_pulses))
            if n > MAX_PULSES:
                raise ValueError(f"num_pulses ({n}) exceeds max {MAX_PULSES} (seg_arb limit)")
            validate_timing(width_s=width_s, rise_s=rise_s, fall_s=fall_s)
            cd_start, cd_end = resolve_cooldown_width_bounds(
                width_s, cd_start_width_s, cd_end_width_s
            )
            widths = cooldown_widths(
                n, cd_start_width_s=cd_start, cd_end_width_s=cd_end, decay=decay
            )
            start_period_s = ensure_period_s(
                start_period_s, width_s=widths[0], rise_s=rise_s, fall_s=fall_s
            )
            end_period_s = ensure_period_s(
                end_period_s, width_s=widths[-1], rise_s=rise_s, fall_s=fall_s
            )
            if end_period_s < start_period_s:
                end_period_s = start_period_s
            periods = [
                ensure_period_s(p, width_s=w, rise_s=rise_s, fall_s=fall_s)
                for p, w in zip(
                    cooldown_periods(n, start_period_s, end_period_s, decay), widths
                )
            ]
    else:
        raise ValueError(f"unknown mode: {mode}")

    segments: List[Segment] = []
    on_intervals: List[Tuple[float, float]] = []
    t = max(0.0, float(delay_before_s))
    if t > 0:
        segments.append(Segment(0.0, t, vlow))

    for p, w in zip(periods, widths):
        t_rise0 = t
        t += rise_s
        segments.append(Segment(t_rise0, t, vhigh))
        t_on0 = t
        t += w
        segments.append(Segment(t_on0, t, vhigh))
        t_on1 = t
        on_intervals.append((t_on0, t_on1))
        t_fall0 = t
        t += fall_s
        segments.append(Segment(t_fall0, t, vlow))
        off = p - (rise_s + w + fall_s)
        if off < MIN_SEG_S:
            off = MIN_SEG_S
        t_off0 = t
        t += off
        segments.append(Segment(t_off0, t, vlow))

    return WaveformPreview(
        mode=mode,
        segments=segments,
        laser_on_intervals=on_intervals,
        total_duration_s=t,
        num_pulses=n,
    )


def preview_polyline(preview: WaveformPreview) -> Tuple[List[float], List[float]]:
    """Return (times, voltages) suitable for a step plot."""
    times: List[float] = []
    volts: List[float] = []
    for seg in preview.segments:
        if not times:
            times.append(seg.t0)
            volts.append(seg.v)
        times.append(seg.t1)
        volts.append(seg.v)
    return times, volts


def format_param(value: float | int | str) -> str:
    """Format a value for a KXCI EX command.

    Uses .6E (not .2E): cool-down pins startPeriod to rise+width+fall+MIN_SEG
    exactly, and .2E was truncating that just *below* the C module's minimum
    check (e.g. 5.022e-5 → "5.02E-5"), so every cool-down returned -1 and
    never fired. .6E keeps enough digits that legal periods survive the
    round-trip. Voltage/current values are unaffected in practice.
    """
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        formatted = f"{value:.6E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


# Single Clarius USRLIB for this tool (PMU TTL + SMU Start/Collect)
DEFAULT_USR_LIBRARY = "A_pmu_laser_smu_read"


def build_smu_start_ex_command(
    vforce: float,
    ilimit: float,
    library: str = DEFAULT_USR_LIBRARY,
) -> str:
    return (
        f"EX {library} pmu_laser_smu_start("
        f"{format_param(vforce)},{format_param(ilimit)})"
    )


def build_smu_collect_ex_command(
    duration_s: float,
    sample_interval_s: float,
    num_points: int,
    library: str = DEFAULT_USR_LIBRARY,
) -> str:
    params = [
        format_param(duration_s),
        format_param(sample_interval_s),
        "",  # Imeas output
        format_param(num_points),
        "",  # Timestamps output
        format_param(num_points),
    ]
    return f"EX {library} pmu_laser_smu_collect({','.join(params)})"



def build_pmu_ex_command(
    mode: ModeName,
    *,
    vhigh: float = 5.0,
    vlow: float = 0.0,
    rise_s: float = 100e-9,
    fall_s: float = 100e-9,
    width_s: float = 10e-6,
    period_s: float = 100e-6,
    start_period_s: float = 100e-6,
    end_period_s: float = 1e-3,
    num_pulses: int = 1,
    delay_before_s: float = 0.0,
    vrange: float = 10.0,
    pmu_id: str = "PMU1",
    clarius_debug: int = 0,
    decay: DecayName = "linear",
    cd_start_width_s: float = 0.0,
    cd_end_width_s: float = 0.0,
    library: str = DEFAULT_USR_LIBRARY,
) -> str:
    """Build EX command for pmu_ttl_laser_ch1.

    cd_start_width_s / cd_end_width_s set the cool-down pulse-WIDTH decay
    bounds (pulse 0 = cd_start_width_s, last pulse = cd_end_width_s,
    decaying per ``decay``) — ignored for mode in {single, train}. Leave at
    0.0 to let the C module default to width_s / MIN_WIDTH respectively
    (matching resolve_cooldown_width_bounds on the Python side); pass the
    RESOLVED values from plan_cooldown() when using an auto span so the
    fired pulses match the preview exactly (plan_cooldown may shrink the
    starting width to fit a short span).
    """
    vhigh = _clamp_vhigh(vhigh)
    mode_i = mode_to_int(mode, decay)
    n = 1 if mode == "single" else max(1, int(num_pulses))
    params: Sequence[str] = [
        format_param(mode_i),
        format_param(vhigh),
        format_param(vlow),
        format_param(rise_s),
        format_param(fall_s),
        format_param(width_s),
        format_param(period_s),
        format_param(start_period_s),
        format_param(end_period_s),
        format_param(n),
        format_param(delay_before_s),
        format_param(vrange),
        pmu_id,  # unquoted: matches the working ACraig10_PMU_Waveform_SegArb
        # EX convention in kxci_scripts.py (quoting the char* param made
        # LPTIsInCurrentConfiguration("\"PMU1\"") fail -> return -2).
        format_param(int(clarius_debug)),
        format_param(cd_start_width_s),
        format_param(cd_end_width_s),
    ]
    return f"EX {library} pmu_ttl_laser_ch1({','.join(params)})"


# Parameter positions (1-indexed) of the Imeas/Timestamps D_ARRAY_T outputs in
# pmu_laser_smu_run's argument list, for GP queries after the EX call.
# cdStartWidth + cdEndWidth + Irange are inserted before the output arrays.
RUN_GP_PARAM_IMEAS = 23
RUN_GP_PARAM_TIMESTAMPS = 25


def build_pmu_laser_smu_run_ex_command(
    mode: ModeName,
    *,
    vforce: float,
    ilimit: float,
    vhigh: float = 5.0,
    vlow: float = 0.0,
    rise_s: float = 100e-9,
    fall_s: float = 100e-9,
    width_s: float = 10e-6,
    period_s: float = 100e-6,
    start_period_s: float = 100e-6,
    end_period_s: float = 1e-3,
    num_pulses: int = 1,
    delay_before_s: float = 0.0,
    vrange: float = 10.0,
    pmu_id: str = "PMU1",
    clarius_debug: int = 0,
    capture_time_s: float,
    sample_interval_s: float,
    num_pre_points: int = 0,
    num_points: int,
    decay: DecayName = "linear",
    cd_start_width_s: float = 0.0,
    cd_end_width_s: float = 0.0,
    irange: float = 0.0,
    library: str = DEFAULT_USR_LIBRARY,
) -> str:
    """Build EX command for pmu_laser_smu_run (SMU bias + PMU TTL + SMU read,
    all in ONE EX call so the SMU source stays "operational" throughout —
    see pmu_laser_smu_run.c for why the split-EX-call approach failed with
    LPT status -160).

    num_points is the TOTAL sample count (pre + post); num_pre_points of
    those are taken BEFORE the laser fires (baseline), the rest after.

    cd_start_width_s / cd_end_width_s set the cool-down pulse-WIDTH decay
    bounds — see build_pmu_ex_command's docstring for details.

    irange is SMU1's current MEASUREMENT range (separate from ilimit, the
    compliance limit): 0.0 = autorange (default), > 0.0 = fixed range for
    lower-noise/faster reads once you know roughly what current to expect.
    """
    vhigh = _clamp_vhigh(vhigh)
    mode_i = mode_to_int(mode, decay)
    n = 1 if mode == "single" else max(1, int(num_pulses))
    params: Sequence[str] = [
        format_param(vforce),
        format_param(ilimit),
        format_param(mode_i),
        format_param(vhigh),
        format_param(vlow),
        format_param(rise_s),
        format_param(fall_s),
        format_param(width_s),
        format_param(period_s),
        format_param(start_period_s),
        format_param(end_period_s),
        format_param(n),
        format_param(delay_before_s),
        format_param(vrange),
        pmu_id,
        format_param(int(clarius_debug)),
        format_param(capture_time_s),
        format_param(sample_interval_s),
        format_param(int(num_pre_points)),
        format_param(cd_start_width_s),
        format_param(cd_end_width_s),
        format_param(irange),
        "",  # Imeas output array
        format_param(num_points),
        "",  # Timestamps output array
        format_param(num_points),
    ]
    return f"EX {library} pmu_laser_smu_run({','.join(params)})"


# Parameter positions (1-indexed) of the Imeas/Timestamps D_ARRAY_T outputs in
# pmu_laser_smu_stream's argument list, for GP queries after each chunk EX call.
# cdStartWidth + cdEndWidth + Irange are inserted before the output arrays.
STREAM_GP_PARAM_IMEAS = 23
STREAM_GP_PARAM_TIMESTAMPS = 25


def build_pmu_laser_smu_stream_ex_command(
    mode: ModeName,
    *,
    vforce: float,
    ilimit: float,
    vhigh: float = 5.0,
    vlow: float = 0.0,
    rise_s: float = 100e-9,
    fall_s: float = 100e-9,
    width_s: float = 10e-6,
    period_s: float = 100e-6,
    start_period_s: float = 100e-6,
    end_period_s: float = 1e-3,
    num_pulses: int = 1,
    delay_before_s: float = 0.0,
    vrange: float = 10.0,
    pmu_id: str = "PMU1",
    clarius_debug: int = 0,
    sample_interval_s: float,
    fire_now: bool = False,
    stop_now: bool = False,
    num_points: int,
    decay: DecayName = "linear",
    cd_start_width_s: float = 0.0,
    cd_end_width_s: float = 0.0,
    irange: float = 0.0,
    library: str = DEFAULT_USR_LIBRARY,
) -> str:
    """Build EX command for ONE CHUNK of pmu_laser_smu_stream (live/manual-fire
    continuous SMU read, with an optional PMU TTL laser fire at the start of
    this chunk). Call this repeatedly, in a loop, over a single persistent
    KXCI session — see pmu_laser_smu_stream.c for why chunking is necessary
    (KXCI/GPIB has no mid-call interrupt/abort).

    num_points is this chunk's sample count (NOT a running total).

    cd_start_width_s / cd_end_width_s set the cool-down pulse-WIDTH decay
    bounds — see build_pmu_ex_command's docstring for details.

    irange is SMU1's current MEASUREMENT range (separate from ilimit, the
    compliance limit): 0.0 = autorange (default), > 0.0 = fixed range for
    lower-noise/faster reads once you know roughly what current to expect.
    """
    vhigh = _clamp_vhigh(vhigh)
    mode_i = mode_to_int(mode, decay)
    n = 1 if mode == "single" else max(1, int(num_pulses))
    params: Sequence[str] = [
        format_param(vforce),
        format_param(ilimit),
        format_param(mode_i),
        format_param(vhigh),
        format_param(vlow),
        format_param(rise_s),
        format_param(fall_s),
        format_param(width_s),
        format_param(period_s),
        format_param(start_period_s),
        format_param(end_period_s),
        format_param(n),
        format_param(delay_before_s),
        format_param(vrange),
        pmu_id,
        format_param(int(clarius_debug)),
        format_param(sample_interval_s),
        format_param(1 if fire_now else 0),
        format_param(1 if stop_now else 0),
        format_param(cd_start_width_s),
        format_param(cd_end_width_s),
        format_param(irange),
        "",  # Imeas output array
        format_param(num_points),
        "",  # Timestamps output array
        format_param(num_points),
    ]
    return f"EX {library} pmu_laser_smu_stream({','.join(params)})"
