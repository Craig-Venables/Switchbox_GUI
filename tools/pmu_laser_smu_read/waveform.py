"""TTL waveform builders for PMU CH1 laser gate (preview + duration estimates).

Times are in seconds. Levels are binary (vlow / vhigh).

Cool-down UX:
  Pulse 0 is a full **Width** write pulse. Pulses after that are an
  explicit user sequence of (delay-before, pulse width) pairs — typed in
  the GUI as one `delay, pulse` line per pulse. The first delay is the
  cool-down gap right after the write. Preview and hardware play that
  list exactly (no auto packing / % envelope).
"""



from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple

ModeName = Literal["single", "train", "cooldown"]
DecayName = Literal["linear", "exponential", "quadratic", "fixed"]
# Kept for API compatibility; cool-down always uses the linear duty envelope.
PackingName = Literal["sparse", "dense"]

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
# Default first cool-down pulse on-time as a fraction of the write Width.
CD_START_FRACTION = 0.1
# Legacy constant (unused by envelope packing); kept for importers.
CD_SPARSE_START_DUTY = 0.2

# EX / C mode ints: 0=single, 1=train, 2=cooldown linear, 3=exp, 4=quadratic
# "fixed" cool-down widths use linear mode int on the wire (C still gets
# cdStart==cdEnd so every cool-down pulse has the same on-time).
_COOLDOWN_MODE_INT = {"linear": 2, "exponential": 3, "quadratic": 4, "fixed": 2}


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
    if n <= 1 or decay == "fixed" or abs(start - end) < 1e-18:
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
    """Human-readable width for GUI info (ns / µs / ms / s)."""
    if w < 1e-6:
        return f"{w * 1e9:.3g} ns"
    if w < 1e-3:
        return f"{w * 1e6:.3g} µs"
    if w < 1.0:
        return f"{w * 1e3:.3g} ms"
    return f"{w:.3g} s"


# Re-export explicit cool-down sequence API (manual pulse/delay list).
from tools.pmu_laser_smu_read.cooldown_seq import (  # noqa: E402
    DEFAULT_COOLDOWN_SEQUENCE_TEXT,
    CooldownPlan,
    avg_power_polyline,
    format_cooldown_sequence_wire,
    parse_cooldown_sequence,
    plan_cooldown_sequence,
)


def resolve_cooldown_width_bounds(
    width_s: float,
    cd_start_width_s: float | None = None,
    cd_end_width_s: float | None = None,
) -> Tuple[float, float]:
    """Legacy helper; prefer explicit ``parse_cooldown_sequence``."""
    if cd_start_width_s is not None and cd_start_width_s > 0:
        cd_start = float(cd_start_width_s)
    else:
        cd_start = max(MIN_WIDTH_S, CD_START_FRACTION * float(width_s))
    cd_end = (
        float(cd_end_width_s)
        if cd_end_width_s is not None and cd_end_width_s > 0
        else MIN_WIDTH_S
    )
    cd_start = max(MIN_WIDTH_S, cd_start)
    cd_end = max(MIN_WIDTH_S, cd_end)
    if cd_start > width_s:
        cd_start = float(width_s)
    if cd_end > cd_start:
        cd_end = cd_start
    return cd_start, cd_end


def plan_cooldown(
    *,
    width_s: float,
    rise_s: float,
    fall_s: float,
    span_s: float = 0.0,
    decay: DecayName = "linear",
    packing: PackingName = "sparse",
    num_cd_pulses: int | None = None,
    cd_start_width_s: float | None = None,
    cd_end_width_s: float | None = None,
    sequence: Sequence[Tuple[float, float]] | None = None,
) -> Tuple[int, float, float, List[float], float, float]:
    """Compatibility wrapper — use ``plan_cooldown_sequence``."""
    del span_s, decay, packing, num_cd_pulses, cd_start_width_s, cd_end_width_s
    validate_timing(width_s=width_s, rise_s=rise_s, fall_s=fall_s)
    write_period = ensure_period_s(
        min_period_s(width_s=width_s, rise_s=rise_s, fall_s=fall_s),
        width_s=width_s,
        rise_s=rise_s,
        fall_s=fall_s,
    )
    if not sequence:
        return 1, write_period, write_period, [write_period], MIN_WIDTH_S, MIN_WIDTH_S
    plan = plan_cooldown_sequence(
        width_s=width_s, rise_s=rise_s, fall_s=fall_s, sequence=sequence
    )
    periods = [rise_s + w + fall_s + off for w, off in zip(plan.widths, plan.offs)]
    cd0 = plan.sequence[0][1] if plan.sequence else MIN_WIDTH_S
    cd1 = plan.sequence[-1][1] if plan.sequence else MIN_WIDTH_S
    p1 = periods[1] if len(periods) > 1 else write_period
    return plan.num_pulses, p1, periods[-1], periods, cd0, cd1


def estimate_cooldown_num_pulses(
    *,
    width_s: float,
    rise_s: float,
    fall_s: float,
    start_period_s: float | None = None,
    end_period_s: float | None = None,
    duration_s: float,
    decay: DecayName = "linear",
    sequence: Sequence[Tuple[float, float]] | None = None,
) -> int:
    """Pulse count for cool-down (1 write + len(sequence))."""
    del start_period_s, end_period_s, duration_s, decay
    if sequence is not None:
        return min(1 + len(sequence), MAX_PULSES)
    validate_timing(width_s=width_s, rise_s=rise_s, fall_s=fall_s)
    return 1


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
    packing: PackingName = "sparse",
    cooldown_span_s: float | None = None,
    num_cd_pulses: int | None = None,
    cd_start_width_s: float | None = None,
    cd_end_width_s: float | None = None,
    cooldown_sequence: Sequence[Tuple[float, float]] | None = None,
) -> WaveformPreview:
    """Build a timeline preview of HIGH/LOW segments and laser-on intervals."""
    del cooldown_span_s, num_cd_pulses, cd_start_width_s, cd_end_width_s
    vhigh = _clamp_vhigh(vhigh)
    validate_timing(width_s=width_s, rise_s=rise_s, fall_s=fall_s)

    widths: List[float]
    offs: List[float] | None = None
    if mode == "single":
        n = 1
        periods = [rise_s + width_s + fall_s + MIN_SEG_S]
        widths = [width_s]
    elif mode == "train":
        n = max(1, int(num_pulses))
        if n > MAX_PULSES:
            raise ValueError(f"num_pulses ({n}) exceeds max {MAX_PULSES} (seg_arb limit)")
        period_s = ensure_period_s(period_s, width_s=width_s, rise_s=rise_s, fall_s=fall_s)
        periods = [period_s] * n
        widths = [width_s] * n
    elif mode == "cooldown":
        seq = list(cooldown_sequence or [])
        plan = plan_cooldown_sequence(
            width_s=width_s, rise_s=rise_s, fall_s=fall_s, sequence=seq
        )
        n = plan.num_pulses
        widths = plan.widths
        offs = plan.offs
        periods = [rise_s + w + fall_s + off for w, off in zip(widths, offs)]
        if periods:
            start_period_s = periods[1] if len(periods) > 1 else periods[0]
            end_period_s = periods[-1]
        del packing, decay  # sequence is authoritative
    else:
        raise ValueError(f"unknown mode: {mode}")

    segments: List[Segment] = []
    on_intervals: List[Tuple[float, float]] = []
    t = max(0.0, float(delay_before_s))
    if t > 0:
        segments.append(Segment(0.0, t, vlow))

    for i, (p, w) in enumerate(zip(periods, widths)):
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
        if offs is not None:
            off = offs[i]
        else:
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
    cd_sequence: str = "",
    library: str = DEFAULT_USR_LIBRARY,
) -> str:
    """Build EX command for pmu_ttl_laser_ch1.

    Cool-down shape is driven by ``cd_sequence`` (``width:delay;...``).
    """
    vhigh = _clamp_vhigh(vhigh)
    mode_i = mode_to_int(mode, decay)
    n = 1 if mode == "single" else max(1, int(num_pulses))
    seq = (cd_sequence or "").strip() or "0"
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
        pmu_id,
        format_param(int(clarius_debug)),
        format_param(cd_start_width_s),
        format_param(cd_end_width_s),
        seq,
    ]
    return f"EX {library} pmu_ttl_laser_ch1({','.join(params)})"


# Parameter positions (1-indexed) of the Imeas/Timestamps D_ARRAY_T outputs in
# pmu_laser_smu_run's argument list, for GP queries after the EX call.
# cdStartWidth + cdEndWidth + cdSequence + Irange sit before the output arrays.
RUN_GP_PARAM_IMEAS = 24
RUN_GP_PARAM_TIMESTAMPS = 26


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
    cd_sequence: str = "",
    irange: float = 0.0,
    library: str = DEFAULT_USR_LIBRARY,
) -> str:
    """Build EX command for pmu_laser_smu_run (SMU bias + PMU TTL + SMU read).

    Cool-down shape is driven by ``cd_sequence`` (``width:delay;...`` wire
    string). ``cd_start_width_s`` / ``cd_end_width_s`` are unused legacy args.
    """
    vhigh = _clamp_vhigh(vhigh)
    mode_i = mode_to_int(mode, decay)
    n = 1 if mode == "single" else max(1, int(num_pulses))
    seq = (cd_sequence or "").strip() or "0"
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
        seq,  # cdSequence char* — unquoted; uses : and ; only (no commas)
        format_param(irange),
        "",  # Imeas output array
        format_param(num_points),
        "",  # Timestamps output array
        format_param(num_points),
    ]
    return f"EX {library} pmu_laser_smu_run({','.join(params)})"


# Parameter positions (1-indexed) of the Imeas/Timestamps D_ARRAY_T outputs in
# pmu_laser_smu_stream's argument list, for GP queries after each chunk EX call.
# cdStartWidth + cdEndWidth + cdSequence + Irange sit before the output arrays.
STREAM_GP_PARAM_IMEAS = 24
STREAM_GP_PARAM_TIMESTAMPS = 26


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
    cd_sequence: str = "",
    irange: float = 0.0,
    library: str = DEFAULT_USR_LIBRARY,
) -> str:
    """Build EX command for ONE CHUNK of pmu_laser_smu_stream.

    Cool-down shape is driven by ``cd_sequence`` (``width:delay;...``).
    """
    vhigh = _clamp_vhigh(vhigh)
    mode_i = mode_to_int(mode, decay)
    n = 1 if mode == "single" else max(1, int(num_pulses))
    seq = (cd_sequence or "").strip() or "0"
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
        seq,
        format_param(irange),
        "",  # Imeas output array
        format_param(num_points),
        "",  # Timestamps output array
        format_param(num_points),
    ]
    return f"EX {library} pmu_laser_smu_stream({','.join(params)})"
