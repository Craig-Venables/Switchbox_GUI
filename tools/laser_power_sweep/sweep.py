"""Laser power sweep with Thorlabs PM100D — digital mW or TTL + current %."""

from __future__ import annotations

import csv
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List, Literal, Optional, Sequence

import matplotlib.pyplot as plt

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from Equipment.Laser_Controller.oxxius import OxxiusLaser, TTL_FULL_POWER_MW
from Equipment.Laser_Power_Meter.pm100d import PM100D

ControlMode = Literal["digital_mw", "ttl_current_pct"]
SweepStatus = Literal["OK", "ABORT_SAFETY", "SKIPPED", "STOPPED"]

DEFAULT_SETTLE_S = 1.5
DEFAULT_NUM_SAMPLES = 10
DEFAULT_SAMPLE_INTERVAL_S = 0.2
DEFAULT_ABORT_THRESHOLD_MW = 40.0
DEFAULT_MAX_SETPOINT_MW = 50.0
DEFAULT_MAX_CURRENT_PCT = 100.0
FILENAME_PREFIX = "laser_power_sweep"


@dataclass
class SweepPoint:
    setpoint: float
    setpoint_unit: str  # "mW" | "current_pct"
    measured_mw: float
    error_value: float
    error_pct: float
    status: SweepStatus
    timestamp_iso: str
    intensity_from_fwhm_mw_per_um2: Optional[float] = None
    intensity_from_e2_mw_per_um2: Optional[float] = None

    @property
    def intensity_mw_per_um2(self) -> Optional[float]:
        """Primary intensity: Gaussian peak from 1/e², else FWHM-disk average."""
        if self.intensity_from_e2_mw_per_um2 is not None:
            return self.intensity_from_e2_mw_per_um2
        return self.intensity_from_fwhm_mw_per_um2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    # Back-compat alias used by GUI logging
    @property
    def set_mw(self) -> float:
        return self.setpoint


@dataclass
class SweepResult:
    control_mode: ControlMode = "digital_mw"
    points: List[SweepPoint] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str = ""
    timestamp_iso: str = ""
    timestamp_filename: str = ""

    @property
    def completed_ok(self) -> bool:
        return bool(self.points) and not self.aborted


def generate_ramp(start: float, step: float, maximum: float) -> List[float]:
    """Build an additive ramp from start to maximum."""
    if start <= 0:
        raise ValueError("start must be > 0")
    if maximum < start:
        raise ValueError("max must be >= start")
    levels = [start]
    if step <= 0:
        return levels
    level = start
    while True:
        nxt = level + step
        if nxt > maximum + 1e-9:
            break
        levels.append(nxt)
        level = nxt
    return levels


generate_setpoints_mw = generate_ramp


def parse_setpoint_list(text: str) -> List[float]:
    """Parse comma/whitespace-separated numeric setpoints."""
    if not (text or "").strip():
        raise ValueError("setpoint list is empty")
    tokens = [t.strip() for t in text.replace("\n", ",").split(",") if t.strip()]
    if not tokens:
        raise ValueError("setpoint list is empty")
    values: List[float] = []
    for tok in tokens:
        try:
            val = float(tok)
        except ValueError as exc:
            raise ValueError(f"bad setpoint {tok!r}") from exc
        if val <= 0:
            raise ValueError(f"setpoint must be > 0: {val}")
        values.append(val)
    return sorted(values)


def filter_setpoints(
    setpoints: Sequence[float],
    *,
    maximum: float,
) -> tuple[List[float], List[float]]:
    """Return (accepted, rejected) setpoints."""
    accepted: List[float] = []
    rejected: List[float] = []
    for sp in sorted(setpoints):
        if sp <= maximum:
            accepted.append(sp)
        else:
            rejected.append(sp)
    return accepted, rejected


def spot_area_from_diameter_um(diameter_um: float) -> float:
    """Circular spot area from a diameter (FWHM or 1/e²)."""
    if diameter_um <= 0:
        return 0.0
    return math.pi * (diameter_um / 2.0) ** 2


def intensity_from_diameter(measured_mw: float, diameter_um: float) -> Optional[float]:
    """Top-hat average: P / (π (d/2)²). Not a Gaussian peak."""
    area = spot_area_from_diameter_um(diameter_um)
    if area <= 0:
        return None
    return measured_mw / area


def gaussian_peak_from_e2(measured_mw: float, e2_diameter_um: float) -> Optional[float]:
    """Peak intensity I0 = 2P / (π w²) with w = 1/e² radius (mW/µm²)."""
    area = spot_area_from_diameter_um(e2_diameter_um)
    if area <= 0:
        return None
    return 2.0 * measured_mw / area


def fwhm_disk_average(measured_mw: float, fwhm_um: float) -> Optional[float]:
    """Average intensity inside the FWHM disk for a Gaussian (half the power is inside)."""
    area = spot_area_from_diameter_um(fwhm_um)
    if area <= 0:
        return None
    return 0.5 * measured_mw / area


def compute_intensities(
    measured_mw: float,
    *,
    fwhm_um: Optional[float] = None,
    e2_um: Optional[float] = None,
) -> tuple[Optional[float], Optional[float]]:
    """Return (FWHM-disk average, Gaussian peak from 1/e²) in mW/µm²."""
    i_fwhm = fwhm_disk_average(measured_mw, fwhm_um) if fwhm_um and fwhm_um > 0 else None
    i_e2 = gaussian_peak_from_e2(measured_mw, e2_um) if e2_um and e2_um > 0 else None
    return i_fwhm, i_e2


def measure_with_abort(
    pm: PM100D,
    n: int,
    interval_s: float,
    abort_threshold_mw: float,
) -> tuple[float, SweepStatus]:
    readings: List[float] = []
    status: SweepStatus = "OK"
    for _ in range(max(1, n)):
        val = pm.measure_power_mw()
        readings.append(val)
        if val >= abort_threshold_mw:
            status = "ABORT_SAFETY"
            break
        time.sleep(max(0.0, interval_s))
    avg = sum(readings) / len(readings) if readings else 0.0
    return avg, status


ProgressCallback = Callable[[SweepPoint, int, int], None]
ShouldStopCallback = Callable[[], bool]


def _append_skipped(
    result: SweepResult,
    rejected: Sequence[float],
    unit: str,
) -> None:
    for sp in rejected:
        result.points.append(
            SweepPoint(
                setpoint=sp,
                setpoint_unit=unit,
                measured_mw=0.0,
                error_value=0.0,
                error_pct=0.0,
                status="SKIPPED",
                timestamp_iso=datetime.now(timezone.utc).isoformat(),
            )
        )


def _make_point(
    *,
    setpoint: float,
    unit: str,
    measured_mw: float,
    status: SweepStatus,
    fwhm_um: Optional[float],
    e2_um: Optional[float],
    compare_to_setpoint: bool,
) -> SweepPoint:
    if compare_to_setpoint and setpoint:
        error_value = measured_mw - setpoint
        error_pct = error_value / setpoint * 100.0
    else:
        error_value = 0.0
        error_pct = 0.0
    i_fwhm, i_e2 = compute_intensities(
        measured_mw,
        fwhm_um=float(fwhm_um) if fwhm_um else None,
        e2_um=float(e2_um) if e2_um else None,
    )
    return SweepPoint(
        setpoint=setpoint,
        setpoint_unit=unit,
        measured_mw=measured_mw,
        error_value=error_value,
        error_pct=error_pct,
        status=status,
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        intensity_from_fwhm_mw_per_um2=i_fwhm,
        intensity_from_e2_mw_per_um2=i_e2,
    )


def run_digital_mw_sweep(
    laser: OxxiusLaser,
    pm: PM100D,
    setpoints_mw: Sequence[float],
    *,
    abort_threshold_mw: float = DEFAULT_ABORT_THRESHOLD_MW,
    max_setpoint_mw: float = DEFAULT_MAX_SETPOINT_MW,
    settle_s: float = DEFAULT_SETTLE_S,
    num_samples: int = DEFAULT_NUM_SAMPLES,
    sample_interval_s: float = DEFAULT_SAMPLE_INTERVAL_S,
    fwhm_um: Optional[float] = None,
    e2_um: Optional[float] = None,
    on_progress: Optional[ProgressCallback] = None,
    should_stop: Optional[ShouldStopCallback] = None,
) -> SweepResult:
    accepted, rejected = filter_setpoints(setpoints_mw, maximum=max_setpoint_mw)
    now = datetime.now(timezone.utc)
    result = SweepResult(
        control_mode="digital_mw",
        timestamp_iso=now.isoformat(),
        timestamp_filename=now.strftime("%Y%m%d_%H%M%S"),
    )
    _append_skipped(result, rejected, "mW")

    total = len(accepted)
    for idx, set_mw in enumerate(accepted):
        if should_stop and should_stop():
            result.aborted = True
            result.abort_reason = "Stopped by user"
            break

        laser.set_to_digital_power_control(set_mw)
        time.sleep(0.2)
        laser.emission_on()
        time.sleep(max(0.0, settle_s))

        measured_mw, status = measure_with_abort(
            pm, num_samples, sample_interval_s, abort_threshold_mw
        )

        try:
            laser.emission_off()
        except Exception:
            pass
        time.sleep(0.3)

        pt = _make_point(
            setpoint=set_mw,
            unit="mW",
            measured_mw=measured_mw,
            status=status,
            fwhm_um=fwhm_um,
            e2_um=e2_um,
            compare_to_setpoint=True,
        )
        result.points.append(pt)
        if on_progress:
            on_progress(pt, idx + 1, total)

        if status == "ABORT_SAFETY":
            result.aborted = True
            result.abort_reason = (
                f"Measured {measured_mw:.3f} mW >= safety limit {abort_threshold_mw:.1f} mW"
            )
            break

    return result


def run_ttl_current_sweep(
    laser: OxxiusLaser,
    pm: PM100D,
    setpoints_pct: Sequence[float],
    *,
    abort_threshold_mw: float = DEFAULT_ABORT_THRESHOLD_MW,
    max_current_pct: float = DEFAULT_MAX_CURRENT_PCT,
    settle_s: float = DEFAULT_SETTLE_S,
    num_samples: int = DEFAULT_NUM_SAMPLES,
    sample_interval_s: float = DEFAULT_SAMPLE_INTERVAL_S,
    fwhm_um: Optional[float] = None,
    e2_um: Optional[float] = None,
    on_progress: Optional[ProgressCallback] = None,
    should_stop: Optional[ShouldStopCallback] = None,
) -> SweepResult:
    """Sweep diode current % with TTL HIGH applied manually (e.g. 5 V from FG)."""
    accepted, rejected = filter_setpoints(setpoints_pct, maximum=max_current_pct)
    now = datetime.now(timezone.utc)
    result = SweepResult(
        control_mode="ttl_current_pct",
        timestamp_iso=now.isoformat(),
        timestamp_filename=now.strftime("%Y%m%d_%H%M%S"),
    )
    _append_skipped(result, rejected, "current_pct")

    laser.ensure_ttl_modulation(full_power_mw=TTL_FULL_POWER_MW)

    total = len(accepted)
    for idx, pct in enumerate(accepted):
        if should_stop and should_stop():
            result.aborted = True
            result.abort_reason = "Stopped by user"
            break

        laser.set_current_percent_for_ttl(pct)
        time.sleep(0.2)
        # User holds TTL HIGH manually during settle + measurement.
        time.sleep(max(0.0, settle_s))

        measured_mw, status = measure_with_abort(
            pm, num_samples, sample_interval_s, abort_threshold_mw
        )

        time.sleep(0.3)

        pt = _make_point(
            setpoint=pct,
            unit="current_pct",
            measured_mw=measured_mw,
            status=status,
            fwhm_um=fwhm_um,
            e2_um=e2_um,
            compare_to_setpoint=False,
        )
        result.points.append(pt)
        if on_progress:
            on_progress(pt, idx + 1, total)

        if status == "ABORT_SAFETY":
            result.aborted = True
            result.abort_reason = (
                f"Measured {measured_mw:.3f} mW >= safety limit {abort_threshold_mw:.1f} mW"
            )
            break

    return result


def run_power_sweep(
    laser: OxxiusLaser,
    pm: PM100D,
    setpoints: Sequence[float],
    *,
    control_mode: ControlMode = "digital_mw",
    abort_threshold_mw: float = DEFAULT_ABORT_THRESHOLD_MW,
    max_setpoint_mw: float = DEFAULT_MAX_SETPOINT_MW,
    max_current_pct: float = DEFAULT_MAX_CURRENT_PCT,
    settle_s: float = DEFAULT_SETTLE_S,
    num_samples: int = DEFAULT_NUM_SAMPLES,
    sample_interval_s: float = DEFAULT_SAMPLE_INTERVAL_S,
    fwhm_um: Optional[float] = None,
    e2_um: Optional[float] = None,
    on_progress: Optional[ProgressCallback] = None,
    should_stop: Optional[ShouldStopCallback] = None,
) -> SweepResult:
    if control_mode == "digital_mw":
        return run_digital_mw_sweep(
            laser,
            pm,
            setpoints,
            abort_threshold_mw=abort_threshold_mw,
            max_setpoint_mw=max_setpoint_mw,
            settle_s=settle_s,
            num_samples=num_samples,
            sample_interval_s=sample_interval_s,
            fwhm_um=fwhm_um,
            e2_um=e2_um,
            on_progress=on_progress,
            should_stop=should_stop,
        )
    return run_ttl_current_sweep(
        laser,
        pm,
        setpoints,
        abort_threshold_mw=abort_threshold_mw,
        max_current_pct=max_current_pct,
        settle_s=settle_s,
        num_samples=num_samples,
        sample_interval_s=sample_interval_s,
        fwhm_um=fwhm_um,
        e2_um=e2_um,
        on_progress=on_progress,
        should_stop=should_stop,
    )


def save_sweep_results(
    result: SweepResult,
    out_dir: Path,
    *,
    laser_port: str = "",
    laser_idn: str = "",
    pm_idn: str = "",
    wavelength_nm: Optional[float] = None,
    abort_threshold_mw: float = DEFAULT_ABORT_THRESHOLD_MW,
    max_setpoint_mw: float = DEFAULT_MAX_SETPOINT_MW,
    max_current_pct: float = DEFAULT_MAX_CURRENT_PCT,
    fwhm_um: Optional[float] = None,
    e2_um: Optional[float] = None,
    focus_scan_dir: str = "",
    focus_scan_z_mm: Optional[float] = None,
    setpoints_requested: Optional[Sequence[float]] = None,
) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = result.timestamp_filename or datetime.now().strftime("%Y%m%d_%H%M%S")
    base = out_dir / f"{FILENAME_PREFIX}_{ts}"

    measured_rows = [p for p in result.points if p.status in ("OK", "ABORT_SAFETY")]
    use_intensity = any(
        p.intensity_from_fwhm_mw_per_um2 is not None or p.intensity_from_e2_mw_per_um2 is not None
        for p in measured_rows
    )
    has_fwhm = fwhm_um and fwhm_um > 0
    has_e2 = e2_um and e2_um > 0
    set_col = "set_mw" if result.control_mode == "digital_mw" else "set_current_pct"

    csv_path = base.with_suffix(".csv")
    fieldnames = [
        set_col,
        "measured_mw",
        "error_value",
        "error_pct",
        "status",
        "timestamp_iso",
    ]
    if use_intensity:
        if has_fwhm:
            fieldnames.append("intensity_from_fwhm_mw_per_um2")
        if has_e2:
            fieldnames.append("intensity_from_e2_mw_per_um2")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pt in result.points:
            row = {
                set_col: pt.setpoint,
                "measured_mw": pt.measured_mw if pt.status != "SKIPPED" else "",
                "error_value": pt.error_value if pt.status != "SKIPPED" else "",
                "error_pct": pt.error_pct if pt.status != "SKIPPED" else "",
                "status": pt.status,
                "timestamp_iso": pt.timestamp_iso,
            }
            if use_intensity:
                if has_fwhm:
                    row["intensity_from_fwhm_mw_per_um2"] = pt.intensity_from_fwhm_mw_per_um2 or ""
                if has_e2:
                    row["intensity_from_e2_mw_per_um2"] = pt.intensity_from_e2_mw_per_um2 or ""
            writer.writerow(row)

    meta: dict[str, Any] = {
        "control_mode": result.control_mode,
        "timestamp_iso": result.timestamp_iso,
        "timestamp_filename": ts,
        "aborted": result.aborted,
        "abort_reason": result.abort_reason,
        "laser_port": laser_port,
        "laser_idn": laser_idn,
        "pm_idn": pm_idn,
        "wavelength_nm": wavelength_nm,
        "abort_threshold_mw": abort_threshold_mw,
        "max_setpoint_mw": max_setpoint_mw,
        "max_current_pct": max_current_pct,
        "fwhm_um": fwhm_um,
        "e2_um": e2_um,
        "intensity_definition": {
            "intensity_from_e2_mw_per_um2": "Gaussian peak I0 = 2P / (pi w^2), w = e2_diameter/2",
            "intensity_from_fwhm_mw_per_um2": "Average in FWHM disk = 0.5 P / (pi (FWHM/2)^2)",
        },
        "focus_scan_dir": focus_scan_dir,
        "focus_scan_z_mm": focus_scan_z_mm,
        "setpoints_requested": list(setpoints_requested) if setpoints_requested else [],
        "points": [p.to_dict() for p in result.points],
    }
    json_path = base.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    png_path = base.with_suffix(".png")
    plot_sweep_result(result, png_path, use_intensity=use_intensity)
    return csv_path, json_path, png_path


def plot_sweep_result(
    result: SweepResult,
    png_path: Path,
    *,
    use_intensity: bool = False,
) -> None:
    ok_points = [p for p in result.points if p.status in ("OK", "ABORT_SAFETY")]
    if not ok_points:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "No measured points", ha="center", va="center")
        ax.axis("off")
        fig.savefig(png_path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        return

    if use_intensity and any(
        p.intensity_from_e2_mw_per_um2 is not None or p.intensity_from_fwhm_mw_per_um2 is not None
        for p in ok_points
    ):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    else:
        fig, ax1 = plt.subplots(figsize=(7, 5))
        ax2 = None

    sets = [p.setpoint for p in ok_points]
    measured = [p.measured_mw for p in ok_points]
    colors = ["#ef4444" if p.status == "ABORT_SAFETY" else "#2563eb" for p in ok_points]

    ax1.plot(sets, measured, "o-", color="#2563eb", markersize=5, label="Measured")
    for x, y, c in zip(sets, measured, colors):
        ax1.scatter([x], [y], c=[c], s=60, zorder=5, edgecolors="k", linewidths=0.4)

    if result.control_mode == "digital_mw":
        max_mw = max(max(sets), max(measured))
        ax1.plot([0, max_mw], [0, max_mw], "k--", alpha=0.5, label="Ideal (set = measured)")
        ax1.set_xlabel("Setpoint (mW)")
    else:
        ax1.set_xlabel("Current setpoint (%)")

    ax1.set_ylabel("Measured (mW)")
    title = "Laser power sweep"
    if result.control_mode == "ttl_current_pct":
        title += " (TTL + current %)"
    if result.aborted:
        title += " — ABORTED"
    ax1.set_title(title)
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    if ax2 is not None:
        e2_pts = [(p.setpoint, p.intensity_from_e2_mw_per_um2) for p in ok_points if p.intensity_from_e2_mw_per_um2]
        fwhm_pts = [(p.setpoint, p.intensity_from_fwhm_mw_per_um2) for p in ok_points if p.intensity_from_fwhm_mw_per_um2]
        if e2_pts:
            ax2.plot(
                [x for x, _ in e2_pts],
                [y for _, y in e2_pts],
                "s-",
                color="#0f766e",
                label="Peak I₀ (Gaussian 1/e²)",
            )
        if fwhm_pts:
            ax2.plot(
                [x for x, _ in fwhm_pts],
                [y for _, y in fwhm_pts],
                "o--",
                color="#7c3aed",
                label="Avg in FWHM disk",
            )
        xlabel = "Setpoint (mW)" if result.control_mode == "digital_mw" else "Current (%)"
        ax2.set_xlabel(xlabel)
        ax2.set_ylabel("Intensity (mW / µm²)")
        ax2.set_title("Power density  (1 mW/µm² = 100 kW/cm²)")
        ax2.legend(fontsize=7)
        ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(png_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
