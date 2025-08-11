from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple

import numpy as np

from .config import Thresholds
from .driver import MeasurementDriver, MeasurementResult
from .metrics import hysteresis_loop_area, on_off_ratio, photoresponse, retention_alpha
from .preferences import load_thresholds


@dataclass
class DeviceOutcome:
    device_id: str
    is_working: bool
    formed: bool
    probe_current_a: float
    hyst_area: float | None
    best_profile: Tuple[float, float, float, float] | None
    notes: str = ""
    # Placeholders for future summaries
    endurance_on_off: float | None = None
    retention_alpha: float | None = None


class TestRunner:
    def __init__(self, driver: MeasurementDriver, thresholds: Thresholds | None = None):
        self.driver = driver
        self.t = thresholds or load_thresholds()

    def run_probe(self) -> Tuple[float, MeasurementResult]:
        res = self.driver.dc_hold(
            voltage_v=self.t.probe_voltage_v,
            duration_s=self.t.probe_duration_s,
            sample_hz=self.t.probe_sample_hz,
            compliance_a=self.t.max_compliance_a,
        )
        i_mean = float(np.mean(res.current))
        return i_mean, res

    def try_forming(self) -> Tuple[bool, List[MeasurementResult]]:
        results: List[MeasurementResult] = []
        for vmax in self.t.forming_voltages_v:
            r = self.driver.triangle_sweep(
                v_min=0.0,
                v_max=vmax,
                step_v=self.t.forming_step_v,
                dwell_s=self.t.forming_dwell_s,
                cycles=1,
                compliance_a=self.t.forming_compliance_a,
            )
            results.append(r)
            if np.any(np.abs(r.current) >= self.t.forming_spike_current_a):
                return True, results
            if hysteresis_loop_area(r.voltage, r.current) >= self.t.forming_hysteresis_min:
                return True, results
            # cooldown between steps
            import time as _time
            _time.sleep(self.t.forming_cooldown_s)
        return False, results

    def optimize_hysteresis(self) -> Tuple[float, Tuple[float, float, float, float], MeasurementResult, list[tuple[tuple[float,float,float,float], float]]]:
        best_area = -1.0
        best_prof = None
        best_res = None
        evals: list[tuple[tuple[float,float,float,float], float]] = []
        budget = max(1, self.t.hyst_budget)
        profiles = list(self.t.hyst_profiles)[:budget]
        for v_max, step_v, dwell_s, i_comp in profiles:
            r = self.driver.triangle_sweep(
                v_min=-v_max,
                v_max=v_max,
                step_v=step_v,
                dwell_s=dwell_s,
                cycles=1,
                compliance_a=i_comp,
            )
            area = hysteresis_loop_area(r.voltage, r.current)
            evals.append(((v_max, step_v, dwell_s, i_comp), float(area)))
            if area > best_area:
                best_area, best_prof, best_res = area, (v_max, step_v, dwell_s, i_comp), r
        return float(best_area), best_prof, best_res, evals

    def run_device(self, device_id: str) -> Tuple[DeviceOutcome, Dict[str, Any]]:
        probe_i, _ = self.run_probe()
        is_working = probe_i > self.t.working_current_a
        formed = False
        notes = ""
        hyst_area = None
        best_profile = None
        best_res: MeasurementResult | None = None
        log_lines: list[str] = []
        log_lines.append(f"Probe at {self.t.probe_voltage_v}V for {self.t.probe_duration_s}s -> I={probe_i:.2e}A")

        if not is_working:
            formed, _forming_results = self.try_forming()
            if formed:
                probe_i, _ = self.run_probe()
                is_working = probe_i > self.t.working_current_a
                notes = "Formed successfully" if is_working else "Formed but still below threshold"
                log_lines.append("Forming succeeded; re-probed device")
            else:
                log_lines.append("Forming attempts exhausted; device remains below threshold")

        if is_working:
            hyst_area, best_profile, best_res, evals = self.optimize_hysteresis()
            log_lines.append("Hysteresis evaluations:")
            for prof, area in evals:
                v_max, step_v, dwell_s, i_comp = prof
                log_lines.append(f"  Vmax={v_max}, step={step_v}, dwell={dwell_s}, Icc={i_comp} -> area={area:.2e}")
            if best_profile is not None:
                log_lines.append(f"Best profile: {best_profile} with area={hyst_area:.2e}")

        # Optional endurance and retention quick runs
        endurance_summary = None
        retention_summary = None
        try:
            if is_working and best_profile is not None:
                # Endurance quick check: limit cycles for speed
                cycles = min(20, self.t.endurance_cycles)
                pairs = self.driver.endurance_pulses(
                    set_v=self.t.set_voltage_v,
                    reset_v=self.t.reset_voltage_v,
                    width_s=self.t.pulse_width_s,
                    read_v=self.t.read_voltage_v,
                    cycles=cycles,
                    compliance_a=self.t.max_compliance_a,
                )
                ratios: List[float] = []
                below = 0
                for on, off in pairs:
                    r = on_off_ratio(on, off)
                    ratios.append(r)
                    if r < self.t.endurance_abort_on_ratio_below:
                        below += 1
                        if below >= self.t.endurance_abort_consec:
                            break
                    else:
                        below = 0
                if ratios:
                    endurance_summary = float(np.median(ratios))

                # Retention: perform one SET then timed reads
                # Ensure ON state
                _ = self.driver.endurance_pulses(
                    set_v=self.t.set_voltage_v,
                    reset_v=self.t.reset_voltage_v,
                    width_s=self.t.pulse_width_s,
                    read_v=self.t.read_voltage_v,
                    cycles=1,
                    compliance_a=self.t.max_compliance_a,
                )
                times = list(self.t.retention_times_s)
                currents = self.driver.retention_reads(
                    read_v=self.t.retention_read_voltage_v,
                    times_s=times,
                    compliance_a=self.t.max_compliance_a,
                )
                if len(currents) == len(times):
                    retention_summary = retention_alpha(np.array(times), np.array(currents))
        except Exception:
            # Non-fatal; proceed
            pass

        outcome = DeviceOutcome(
            device_id=device_id,
            is_working=is_working,
            formed=formed,
            probe_current_a=probe_i,
            hyst_area=hyst_area,
            best_profile=best_profile,
            notes=notes,
            endurance_on_off=endurance_summary,
            retention_alpha=retention_summary,
        )

        artifacts: Dict[str, Any] = {}
        if best_res is not None:
            artifacts["best_iv"] = best_res
        artifacts["log_lines"] = log_lines

        return outcome, artifacts


