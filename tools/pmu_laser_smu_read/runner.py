"""KXCI orchestration: SMU continuous read + PMU CH1 TTL laser pulse.

Uses a **single GPIB session** via Keithley4200A_KXCI (same stack as Pulse Testing).
Dual sessions cannot talk to one 4200 while Collect is running — that was why
commands appeared not to reach KXCI.

IMPORTANT — single combined EX call, not three:
This used to be three separate EX calls (pmu_laser_smu_start ->
pmu_ttl_laser_ch1 -> pmu_laser_smu_collect). On real hardware, that failed
with LPT status -160 ("Measurement cannot be performed because the source
is not operational") on the very first measi() in Collect: each top-level
EX/UL invocation from KXCI is its own execution context, and the SMU's
forcev() from Start did not stay "operational" once that EX call returned
and the next EX call began. Fixed by inlining bias -> pulse -> measure ->
ramp-down into ONE USRLIB module (pmu_laser_smu_run.c) called with ONE EX
command, so the SMU source is never torn down mid-sequence.

Sequence (one UL session):
  1. DE (clear stuck UL) → *IDN?
  2. UL
  3. pmu_laser_smu_run EX  (bias + PMU TTL fire + SMU sample loop + ramp down)
  4. GP → DE
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from waveform import (  # type: ignore
        DEFAULT_USR_LIBRARY,
        RUN_GP_PARAM_IMEAS,
        STREAM_GP_PARAM_IMEAS,
        DecayName,
        ModeName,
        WaveformPreview,
        build_pmu_laser_smu_run_ex_command,
        build_pmu_laser_smu_stream_ex_command,
        build_preview,
        plan_cooldown,
        ensure_period_s,
    )
except ImportError:
    from tools.pmu_laser_smu_read.waveform import (
        DEFAULT_USR_LIBRARY,
        RUN_GP_PARAM_IMEAS,
        STREAM_GP_PARAM_IMEAS,
        DecayName,
        ModeName,
        WaveformPreview,
        build_pmu_laser_smu_run_ex_command,
        build_pmu_laser_smu_stream_ex_command,
        build_preview,
        plan_cooldown,
        ensure_period_s,
    )

# Import KXCI controller directly (avoid Equipment.SMU_AND_PMU.__init__ pulling pymeasure)
import importlib.util

_KXCI_PATH = (
    _REPO_ROOT
    / "Equipment"
    / "SMU_AND_PMU"
    / "keithley4200"
    / "kxci_controller.py"
)
_spec = importlib.util.spec_from_file_location("keithley4200_kxci_controller", _KXCI_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load KXCI controller from {_KXCI_PATH}")
_kxci_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_kxci_mod)
Keithley4200A_KXCI = _kxci_mod.Keithley4200A_KXCI


def _log(msg: str) -> None:
    print(f"[pmu_laser_smu] {msg}", flush=True)


def _synthetic_laser_centered_timestamps(
    n: int, sample_interval_s: float, num_pre_points: int = 0
) -> List[float]:
    """Build the plot/CSV time axis from sample_interval_s (not instrument GP).

    Matches the C module convention: t=0 is the laser-fire instant; pre-pulse
    baseline samples are negative; post-pulse samples start at +dt. Instrument
    GP Timestamps are the same synthetic i*dt values, but we never trust them
    as the axis source — live mode used to accumulate those and lagged wall
    clock because each GPIB chunk takes longer than n*dt.
    """
    return [
        (i - num_pre_points + 1) * sample_interval_s
        if i >= num_pre_points
        else -(num_pre_points - i) * sample_interval_s
        for i in range(n)
    ]


def _package_smu_result(
    currents: List[float],
    vforce: float,
    sample_interval_s: float,
    num_pre_points: int = 0,
) -> Dict[str, Any]:
    n = len(currents)
    timestamps = _synthetic_laser_centered_timestamps(n, sample_interval_s, num_pre_points)
    voltages = [vforce] * n
    resistances = [
        (vforce / i if i and abs(i) > 1e-18 else float("nan")) for i in currents
    ]
    return {
        "timestamps": timestamps,
        "voltages": voltages,
        "currents": currents,
        "resistances": resistances,
    }


def _parse_return_value(response: str) -> Optional[int]:
    """Parse a KXCI EX return value.

    The 4200 often replies with a bare integer (e.g. "-2\\r"), not the
    "RETURN VALUE = -2" format that Keithley4200A_KXCI._execute_ex_command
    expects. Try that format first, then fall back to a bare int — otherwise
    real error codes (like -2 from pmu_ttl_laser_ch1) are silently treated
    as "unknown" and never raised.
    """
    if not response:
        return None
    text = response.strip()
    import re as _re

    match = _re.search(r"RETURN VALUE\s*=\s*(-?\d+)", text, _re.IGNORECASE)
    if match:
        return int(match.group(1))
    try:
        return int(text)
    except ValueError:
        return None


def _send_ex(kxci: Keithley4200A_KXCI, command: str, wait_seconds: float) -> Tuple[Optional[int], str]:
    """Send an EX command and reliably parse its return value.

    Bypasses Keithley4200A_KXCI._execute_ex_command's parser (which misses
    bare-integer replies) and reads directly off kxci.inst.
    """
    if kxci.inst is None:
        raise RuntimeError("Instrument not connected")
    kxci.inst.write(command)
    time.sleep(0.03)
    time.sleep(max(0.01, wait_seconds))
    raw = ""
    try:
        raw = kxci.inst.read()
    except Exception:
        time.sleep(0.1)
        try:
            raw = kxci.inst.read()
        except Exception:
            raw = ""
    rv = _parse_return_value(raw)
    return rv, raw


# Meaning tables for our own USRLIB return codes (see pmu_ttl_laser_ch1.c /
# pmu_laser_smu_start.c / pmu_laser_smu_collect.c)
# pmu_laser_smu_run.c return-code meanings. Nonzero codes not in this table
# are RAW LPT status codes bubbled up verbatim from limiti/forcev/measi/
# rpm_config/pg2_init/pulse_ranges/pulse_output/seg_arb_*/pulse_exec — look
# them up in the Keithley LPT Library reference (kiXXXX / error code table).
_RUN_ERROR_MEANINGS = {
    -1: "invalid parameters (SMU collect params OR PMU pulse params)",
    -2: (
        "PMU instrument ID not found in system configuration "
        "(LPTIsInCurrentConfiguration failed). Check the PMU card's name in "
        "KCON on the 4200 and match it to the 'PMU_ID' field (default 'PMU1')."
    ),
    -3: "getinstid() failed for PMU_ID",
    -4: "memory allocation failed on the 4200",
    -5: "too many Segment ARB segments (reduce num_pulses)",
    -160: "LPT error -160: source (SMU) is not operational — measurement attempted while SMU output is not active",
}


def _query_gp(kxci: Keithley4200A_KXCI, param: int, n: int) -> List[float]:
    """Prefer controller helper; fall back to raw GP."""
    if hasattr(kxci, "_query_gp"):
        try:
            vals = kxci._query_gp(param, n)  # type: ignore[attr-defined]
            if vals:
                return list(vals)
        except Exception as exc:
            _log(f"GP {param} via controller failed: {exc}")
    # Raw fallback matching SMU BiasTimedRead runner
    if kxci.inst is None:
        return []
    kxci.inst.write(f"GP {param} {n}")
    time.sleep(0.05)
    try:
        raw = kxci.inst.read()
    except Exception:
        return []
    if not raw:
        return []
    text = raw.strip()
    if "=" in text and "PARAM VALUE" in text.upper():
        text = text.split("=", 1)[1].strip()
    sep = ";" if ";" in text else ("," if "," in text else None)
    out: List[float] = []
    parts = text.split(sep) if sep else [text]
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError:
            pass
    return out


def _make_resource_manager():
    """Create a VISA ResourceManager, trying common backends."""
    import pyvisa

    errors: List[str] = []
    for backend in (None, "@ni", "@ivi", "@py"):
        try:
            rm = pyvisa.ResourceManager() if backend is None else pyvisa.ResourceManager(backend)
            return rm, backend or "default"
        except Exception as exc:
            errors.append(f"{backend or 'default'}: {exc}")
    raise RuntimeError("No VISA backend opened. Tried default/@ni/@ivi/@py. " + " | ".join(errors))


def _flush_read(inst, max_reads: int = 8, timeout_ms: int = 100) -> None:
    """Drain stale bytes so a later *IDN? is not blocked by a prior DE/UL reply."""
    old = getattr(inst, "timeout", 2000)
    try:
        inst.timeout = timeout_ms
        for _ in range(max_reads):
            try:
                inst.read()
            except Exception:
                break
    finally:
        try:
            inst.timeout = old
        except Exception:
            pass


def _safe_clear(inst) -> None:
    try:
        inst.clear()
    except Exception:
        pass


def list_visa_resources(timeout_s: float = 5.0) -> Tuple[List[str], str]:
    """Return (resources, status_message). Never raises."""
    try:
        import pyvisa  # noqa: F401
    except ImportError:
        return [], "FAIL: pyvisa not installed (pip install pyvisa)"
    try:
        rm, backend = _make_resource_manager()
    except Exception as exc:
        return [], f"FAIL ResourceManager: {exc}"
    try:
        # list_resources can be slow; keep it best-effort
        res = list(rm.list_resources())
        rm.close()
        return res, f"OK backend={backend}, {len(res)} resource(s)"
    except Exception as exc:
        try:
            rm.close()
        except Exception:
            pass
        return [], f"FAIL list_resources: {exc}"


def _connect_kxci(
    gpib_address: str, timeout: float, debug: bool = True
) -> Keithley4200A_KXCI:
    """Open GPIB with short, safe KXCI handshake (DE flush → *IDN?)."""
    address = (gpib_address or "").strip()
    if not address:
        raise ValueError("GPIB address is empty")

    kxci = Keithley4200A_KXCI(gpib_address=address, timeout=timeout, debug=debug)
    # Keithley4200A_KXCI stores timeout already in ms
    timeout_ms = int(max(1.0, timeout) * 1000)
    try:
        rm, backend = _make_resource_manager()
        kxci.rm = rm
        _log(f"VISA backend={backend}, opening {address!r} (timeout={timeout_ms} ms)")
        kxci.inst = kxci.rm.open_resource(address)
        kxci.inst.timeout = timeout_ms
        kxci.inst.write_termination = "\n"
        kxci.inst.read_termination = "\n"

        _safe_clear(kxci.inst)

        # Leave stuck UL if possible; ignore errors (not in UL is fine)
        try:
            kxci.inst.write("DE")
            time.sleep(0.05)
            _flush_read(kxci.inst)
        except Exception as exc:
            _log(f"DE (optional) note: {exc}")
        kxci._ul_mode_active = False

        _safe_clear(kxci.inst)
        idn = kxci.inst.query("*IDN?").strip()
        if not idn:
            raise RuntimeError("*IDN? returned empty — is KXCI enabled and address correct?")
        _log(f"Connected: {idn}")
        return kxci
    except Exception as exc:
        # Attach a short hint (avoid list_resources — it often hangs)
        hint = (
            "\nHints: check GPIB address, enable KXCI, close other sessions holding the bus."
        )
        try:
            kxci.disconnect()
        except Exception:
            pass
        raise RuntimeError(f"{exc}{hint}") from exc


def test_kxci_connection(gpib_address: str, timeout: float = 5.0) -> str:
    """Open GPIB, *IDN?, UL/DE. Short timeout — does not call list_resources first
    (that scan often hangs on Windows NI-VISA)."""
    address = (gpib_address or "").strip()
    lines = [f"Trying {address!r} (timeout={timeout}s)…"]

    try:
        kxci = _connect_kxci(address, timeout=timeout, debug=True)
    except Exception as exc:
        lines.append(f"FAIL connect: {exc}")
        # Best-effort resource list only after failure (may also hang — cap via timeout on open)
        try:
            resources, list_msg = list_visa_resources()
            lines.append(f"VISA scan: {list_msg}")
            if resources:
                lines.append("Resources: " + ", ".join(resources))
        except Exception as scan_exc:
            lines.append(f"VISA scan skipped/failed: {scan_exc}")
        lines.append(
            "Hints: enable KXCI on the 4200; close Clarius / other Python GPIB sessions; "
            "confirm address (often GPIB0::17::INSTR); install/repair NI-VISA."
        )
        return "\n".join(lines)

    try:
        if not kxci._enter_ul_mode():
            lines.append("Connected (*IDN? OK) but UL failed")
            return "\n".join(lines)
        time.sleep(0.05)
        if not kxci._exit_ul_mode():
            lines.append("UL entered but DE failed")
            return "\n".join(lines)
        try:
            _flush_read(kxci.inst)
            idn = kxci.inst.query("*IDN?").strip()  # type: ignore[union-attr]
        except Exception as exc:
            idn = f"(IDN after DE failed: {exc})"
        lines.append(f"OK: {idn}")
        lines.append("GPIB + UL/DE working")
        return "\n".join(lines)
    except Exception as exc:
        lines.append(f"FAIL: {exc}")
        return "\n".join(lines)
    finally:
        try:
            kxci.disconnect()
        except Exception:
            pass


def run_pmu_laser_smu_read(
    *,
    gpib_address: str = "GPIB0::17::INSTR",
    timeout: float = 120.0,
    mode: ModeName = "single",
    vread: float = 0.2,
    ilimit: float = 1e-4,
    capture_time_s: float = 2.0,
    pre_capture_s: float = 0.0,
    sample_interval_s: float = 0.01,
    vhigh: float = 5.0,
    vlow: float = 0.0,
    width_s: float = 10e-6,
    rise_s: float = 100e-9,
    fall_s: float = 100e-9,
    period_s: float = 100e-6,
    start_period_s: float = 100e-6,
    end_period_s: float = 1e-3,
    num_pulses: int = 10,
    delay_before_s: float = 0.05,
    laser_fire_delay_s: float = 0.1,
    vrange: float = 10.0,
    pmu_id: str = "PMU1",
    clarius_debug: int = 0,
    usr_library: str = DEFAULT_USR_LIBRARY,
    dry_run: bool = False,
    debug: bool = True,
    decay: DecayName = "linear",
    cooldown_span_s: Optional[float] = None,
    cd_start_width_s: Optional[float] = None,
    cd_end_width_s: Optional[float] = None,
) -> Dict[str, Any]:
    """Run SMU bias + PMU TTL + SMU collect on one KXCI GPIB session.

    cd_start_width_s / cd_end_width_s are OPTIONAL overrides for the
    cool-down pulse-WIDTH decay bounds (normally left None so
    plan_cooldown() derives them from width_s — see its docstring). The GUI
    passes back the values IT already resolved (from its own plan_cooldown
    call, used for the on-screen preview/info text) purely so this call's
    plan_cooldown() reproduces the identical, possibly shrunk-to-fit bounds
    rather than recomputing them a second time.
    """
    if sample_interval_s < 0.001:
        raise ValueError("sample_interval_s must be >= 1 ms (SMU_BiasTimedRead limit)")

    n_pulses = num_pulses
    start_p = start_period_s
    end_p = end_period_s
    period_use = period_s
    cd_start_w = 0.0
    cd_end_w = 0.0
    if mode == "train":
        period_use = ensure_period_s(
            period_s, width_s=width_s, rise_s=rise_s, fall_s=fall_s
        )
    if mode == "cooldown":
        span = cooldown_span_s
        if span is None or span <= 0:
            span = max(start_period_s, 1e-6)
        n_pulses, start_p, end_p, _, cd_start_w, cd_end_w = plan_cooldown(
            width_s=width_s,
            rise_s=rise_s,
            fall_s=fall_s,
            span_s=span,
            decay=decay,
            cd_start_width_s=cd_start_width_s,
            cd_end_width_s=cd_end_width_s,
        )
    if mode == "single":
        n_pulses = 1

    preview: WaveformPreview = build_preview(
        mode,
        vhigh=vhigh,
        vlow=vlow,
        width_s=width_s,
        rise_s=rise_s,
        fall_s=fall_s,
        period_s=period_use,
        start_period_s=start_p,
        end_period_s=end_p,
        num_pulses=n_pulses,
        delay_before_s=delay_before_s,
        decay=decay,
        cooldown_span_s=cooldown_span_s if mode == "cooldown" else None,
        cd_start_width_s=cd_start_w,
        cd_end_width_s=cd_end_w,
    )

    num_pre_points = max(0, int(round(pre_capture_s / sample_interval_s))) if pre_capture_s > 0 else 0
    num_post_points = max(1, int(round(capture_time_s / sample_interval_s)))
    num_points = num_pre_points + num_post_points
    run_cmd = build_pmu_laser_smu_run_ex_command(
        mode,
        vforce=vread,
        ilimit=ilimit,
        vhigh=vhigh,
        vlow=vlow,
        rise_s=rise_s,
        fall_s=fall_s,
        width_s=width_s,
        period_s=period_use,
        start_period_s=start_p,
        end_period_s=end_p,
        num_pulses=n_pulses,
        delay_before_s=delay_before_s,
        vrange=vrange,
        pmu_id=pmu_id,
        clarius_debug=clarius_debug,
        capture_time_s=capture_time_s,
        sample_interval_s=sample_interval_s,
        num_pre_points=num_pre_points,
        num_points=num_points,
        decay=decay,
        cd_start_width_s=cd_start_w,
        cd_end_width_s=cd_end_w,
        library=usr_library,
    )
    # Wait long enough for: pre-pulse baseline samples + PMU pulse train duration
    # + post-pulse SMU sample loop duration + margin
    run_wait = max(2.0, pre_capture_s + preview.total_duration_s + capture_time_s + 3.0)

    if dry_run:
        _log(f"DRY Run: {run_cmd}")
        return {
            "dry_run": True,
            "pmu_command": run_cmd,
            "preview": preview,
            "num_points": num_points,
            "num_pre_points": num_pre_points,
            "num_post_points": num_post_points,
            "laser_on_intervals": preview.laser_on_intervals,
            "timestamps": [],
            "currents": [],
            "voltages": [],
            "resistances": [],
            "overlap_mode": "dry_run",
            "mode": mode,
        }

    kxci = _connect_kxci(gpib_address, timeout, debug=debug)

    laser_intervals: List[Tuple[float, float]] = []
    try:
        if not kxci._enter_ul_mode():
            raise RuntimeError("Failed to enter UL mode")

        if laser_fire_delay_s > 0:
            # Kept for API compatibility; the delay is now applied inside the
            # combined module itself (delayBefore), not between separate EX calls.
            pass

        # Single combined EX call: SMU bias -> PMU TTL fire -> SMU sample loop
        # -> ramp down. All inside ONE execution context so the SMU source
        # never gets torn down mid-sequence (see module docstring for why the
        # 3-EX-call split failed with LPT -160).
        _log(f"Sending: {run_cmd}")
        t_ex0 = time.perf_counter()
        rv, raw = _send_ex(kxci, run_cmd, wait_seconds=run_wait)
        wall_ex_s = time.perf_counter() - t_ex0
        _log(f"Run return={rv} raw={raw!r} wall={wall_ex_s:.3f}s")
        if rv is None:
            raise RuntimeError(
                f"pmu_laser_smu_run: no parseable return value (raw={raw!r}). "
                f"Is library '{usr_library}' compiled/loaded in Clarius?"
            )
        if rv < 0:
            meaning = _RUN_ERROR_MEANINGS.get(rv, "unknown error / raw LPT status code")
            raise RuntimeError(f"pmu_laser_smu_run returned {rv} ({meaning})")

        time.sleep(0.05)
        currents = _query_gp(kxci, RUN_GP_PARAM_IMEAS, num_points)

        if not currents:
            raise RuntimeError("No SMU current data from GP")

        # Time axis: Python sample_interval grid with t=0 at laser fire (same
        # reference as preview.laser_on_intervals). Do not GP-query or trust
        # instrument Timestamps for the plot/CSV axis.
        laser_intervals = list(preview.laser_on_intervals)

        result = _package_smu_result(currents, vread, sample_interval_s, num_pre_points)
        result.update(
            {
                "laser_on_intervals": laser_intervals,
                "preview": preview,
                "mode": mode,
                "decay": decay if mode == "cooldown" else None,
                "overlap_mode": "single_ex_call",
                "pmu_command": run_cmd,
                "vread": vread,
                "num_pulses": n_pulses,
                "pmu_return": rv,
                "num_pre_points": num_pre_points,
                "num_post_points": num_post_points,
                "wall_ex_s": wall_ex_s,
                "time_base": "sample_interval_s_laser_centered",
            }
        )
        return result
    finally:
        try:
            kxci._exit_ul_mode()
        except Exception:
            pass
        kxci.disconnect()


class PmuLaserSmuStreamSession:
    """Persistent KXCI session for LIVE/MANUAL-FIRE continuous SMU read.

    KXCI/GPIB is one-command-at-a-time and synchronous — there is no way to
    interrupt an in-flight EX call to fire the laser "right now". Instead,
    this session reads the SMU in small repeated CHUNKS (one EX call each,
    via pmu_laser_smu_stream.c). Before each chunk you decide whether to set
    fire_now=True; if so, the laser fires at the very start of that chunk
    and the chunk's own samples immediately after capture the transient.
    "Fire Now" latency is therefore bounded by the CURRENT chunk's duration
    (chunk_points * sample_interval_s), not by the full continuous-read span.

    Typical usage (see gui.py's Live tab worker thread)::

        session = PmuLaserSmuStreamSession(gpib_address=..., pmu_id=...)
        session.connect()
        try:
            while streaming:
                chunk = session.read_chunk(vread=..., ilimit=...,
                                            sample_interval_s=0.05, num_points=10,
                                            fire_now=fire_pending, mode=..., vhigh=..., ...)
                # chunk['timestamps'] are ABSOLUTE session seconds from
                # time.perf_counter() (t=0 at first chunk). Samples in each
                # chunk are spaced evenly from the previous last sample to
                # wall-clock receipt, so GPIB/EX overhead widens spacing
                # instead of leaving a hole on the plot.
                # laser_on_intervals (if fired) use the same time base.
        finally:
            session.stop()  # ramps SMU to 0 V safely
    """

    def __init__(
        self,
        *,
        gpib_address: str,
        timeout: float = 30.0,
        pmu_id: str = "PMU1",
        clarius_debug: int = 0,
        usr_library: str = DEFAULT_USR_LIBRARY,
        debug: bool = True,
    ) -> None:
        self.gpib_address = gpib_address
        self.timeout = timeout
        self.pmu_id = pmu_id
        self.clarius_debug = clarius_debug
        self.usr_library = usr_library
        self.debug = debug
        self._kxci: Optional[Keithley4200A_KXCI] = None
        self._connected = False
        # Session time origin (perf_counter); set on first read_chunk.
        self._t0_perf: Optional[float] = None
        # Last assigned sample time (session seconds); continuous axis across chunks.
        self._last_t: float = 0.0

    def connect(self) -> None:
        kxci = _connect_kxci(self.gpib_address, self.timeout, debug=self.debug)
        if not kxci._enter_ul_mode():
            try:
                kxci.disconnect()
            except Exception:
                pass
            raise RuntimeError("Failed to enter UL mode")
        self._kxci = kxci
        self._connected = True
        self._t0_perf = None
        self._last_t = 0.0

    def read_chunk(
        self,
        *,
        vread: float,
        ilimit: float,
        sample_interval_s: float,
        num_points: int,
        fire_now: bool = False,
        mode: ModeName = "single",
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
        decay: DecayName = "linear",
        cooldown_span_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run one chunk: (optionally fire the laser, then) sample NumPoints
        SMU readings. Returns absolute session timestamps on a continuous
        wall-clock axis (perf_counter origin; even spacing within each chunk)."""
        if not self._connected or self._kxci is None:
            raise RuntimeError("Not connected — call connect() first")

        n_pulses = 1 if mode == "single" else max(1, int(num_pulses))
        start_p = start_period_s
        end_p = end_period_s
        period_use = ensure_period_s(
            period_s, width_s=width_s, rise_s=rise_s, fall_s=fall_s
        ) if mode == "train" else period_s
        cd_start_w = 0.0
        cd_end_w = 0.0
        if fire_now and mode == "cooldown":
            span = cooldown_span_s if cooldown_span_s and cooldown_span_s > 0 else None
            if span is None:
                span = max(start_period_s, 1e-6)
            n_pulses, start_p, end_p, _, cd_start_w, cd_end_w = plan_cooldown(
                width_s=width_s,
                rise_s=rise_s,
                fall_s=fall_s,
                span_s=span,
                decay=decay,
            )

        laser_on_intervals: List[Tuple[float, float]] = []
        pulse_dur = 0.0
        if fire_now:
            preview = build_preview(
                mode,
                vhigh=vhigh,
                vlow=vlow,
                width_s=width_s,
                rise_s=rise_s,
                fall_s=fall_s,
                period_s=period_use,
                start_period_s=start_p,
                end_period_s=end_p,
                num_pulses=n_pulses,
                delay_before_s=delay_before_s,
                decay=decay,
                cooldown_span_s=cooldown_span_s if mode == "cooldown" else None,
                cd_start_width_s=cd_start_w,
                cd_end_width_s=cd_end_w,
            )
            pulse_dur = preview.total_duration_s
            laser_on_intervals = list(preview.laser_on_intervals)

        cmd = build_pmu_laser_smu_stream_ex_command(
            mode,
            vforce=vread,
            ilimit=ilimit,
            vhigh=vhigh,
            vlow=vlow,
            rise_s=rise_s,
            fall_s=fall_s,
            width_s=width_s,
            period_s=period_use,
            start_period_s=start_p,
            end_period_s=end_p,
            num_pulses=n_pulses,
            delay_before_s=delay_before_s,
            vrange=vrange,
            pmu_id=self.pmu_id,
            clarius_debug=self.clarius_debug,
            sample_interval_s=sample_interval_s,
            fire_now=fire_now,
            stop_now=False,
            num_points=num_points,
            decay=decay,
            cd_start_width_s=cd_start_w,
            cd_end_width_s=cd_end_w,
            library=self.usr_library,
        )
        wait = max(0.5, pulse_dur + num_points * sample_interval_s + 0.5)
        if self._t0_perf is None:
            self._t0_perf = time.perf_counter()
        rv, raw = _send_ex(self._kxci, cmd, wait_seconds=wait)
        if rv is None:
            raise RuntimeError(
                f"pmu_laser_smu_stream: no parseable return value (raw={raw!r})"
            )
        if rv < 0:
            meaning = _RUN_ERROR_MEANINGS.get(rv, "unknown error / raw LPT status code")
            raise RuntimeError(f"pmu_laser_smu_stream returned {rv} ({meaning})")

        time.sleep(0.03)
        currents = _query_gp(self._kxci, STREAM_GP_PARAM_IMEAS, num_points)
        # Stamp after GP so the axis tracks when samples are in hand (wall clock).
        t_recv = time.perf_counter()
        n_actual = len(currents) if currents else 0
        if not currents:
            raise RuntimeError("No SMU current data from GP (chunk)")

        # Continuous wall-clock axis: distribute this chunk evenly from the
        # previous last sample to receipt time. GPIB/EX overhead widens the
        # within-chunk spacing instead of leaving a hole between chunks.
        # Fallback to fixed sample_interval_s only if wall time did not advance.
        assert self._t0_perf is not None
        t_end = t_recv - self._t0_perf
        t_start = self._last_t
        if t_end > t_start and n_actual > 0:
            step = (t_end - t_start) / n_actual
            timestamps = [t_start + (i + 1) * step for i in range(n_actual)]
        else:
            dt = sample_interval_s
            timestamps = [t_start + (i + 1) * dt for i in range(n_actual)]
        self._last_t = timestamps[-1]

        # Preview intervals are relative to local t=0 at fire. Map onto this
        # chunk's assigned time base (fire at first sample of a fire chunk).
        if fire_now and laser_on_intervals:
            t_fire = timestamps[0]
            laser_on_intervals = [(a + t_fire, b + t_fire) for a, b in laser_on_intervals]

        voltages = [vread] * n_actual
        resistances = [
            (vread / i if i and abs(i) > 1e-18 else float("nan")) for i in currents
        ]
        return {
            "timestamps": timestamps,  # absolute session seconds (perf_counter)
            "currents": currents,
            "voltages": voltages,
            "resistances": resistances,
            "fired": bool(fire_now),
            "laser_on_intervals": laser_on_intervals,  # absolute, only if fired
            "pmu_command": cmd,
            "pmu_return": rv,
            "time_base": "perf_counter_continuous",
        }

    def stop(self) -> None:
        """Ramp the SMU to 0 V (StopNow=1) and close the session. Safe to
        call even if a chunk previously errored."""
        if self._connected and self._kxci is not None:
            try:
                cmd = build_pmu_laser_smu_stream_ex_command(
                    "single",
                    vforce=0.0,
                    ilimit=1e-4,
                    pmu_id=self.pmu_id,
                    clarius_debug=self.clarius_debug,
                    sample_interval_s=0.01,
                    fire_now=False,
                    stop_now=True,
                    num_points=1,
                    library=self.usr_library,
                )
                _send_ex(self._kxci, cmd, wait_seconds=0.3)
            except Exception as exc:
                _log(f"stream stop EX warning: {exc}")
        self.disconnect()

    def disconnect(self) -> None:
        if self._kxci is not None:
            try:
                self._kxci._exit_ul_mode()
            except Exception:
                pass
            try:
                self._kxci.disconnect()
            except Exception:
                pass
        self._kxci = None
        self._connected = False
        self._t0_perf = None
        self._last_t = 0.0
