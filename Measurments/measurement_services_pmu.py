from __future__ import annotations

"""
MeasurementServicesPMU

- Centralizes PMU-focused measurement logic in one place.
- Wraps `Keithley4200A_PMUDualChannel` for low-level PMU control.
- Optionally coordinates with a `FunctionGeneratorManager` for laser/triggered tests.

Note: Some methods are moved over from the work-in-progress `MemristorMeasurements`
class for continuity. They may rely on PMU helpers that are not yet finalized and
will be revised in future prompts.
"""

import time
from typing import Iterable, Optional, Callable, Tuple, List, Any

import numpy as np
import pandas as pd

from Equipment.SMU_AND_PMU.Keithley4200A import Keithley4200A_PMUDualChannel
from Equipment.function_generator_manager import FunctionGeneratorManager


class MeasurementServicesPMU:
    def __init__(
        self,
        *,
        pmu: Keithley4200A_PMUDualChannel,
        function_generator: Optional[FunctionGeneratorManager] = None,
    ) -> None:
        self.pmu = pmu
        self.function_generator = function_generator

    # ----------------------
    # Thin PMU wrapper utils
    # ----------------------
    def prepare_measure_at_voltage(
        self,
        *,
        amplitude_v: float,
        base_v: float = 0.0,
        width_s: float = 10e-6,
        period_s: float = 20e-6,
        meas_start_pct: float = 0.1,
        meas_stop_pct: float = 0.9,
        source_channel: int = 1,
        hold_other_at_zero: bool = True,
        force_fixed_ranges: bool = False,
        v_meas_range: float = 10.0,
        i_meas_range: float = 100e-6,
        num_pulses: int = 1,
        delay_s: float | None = None,
        outputs_on: bool = True,
    ) -> None:
        self.pmu.prepare_measure_at_voltage(
            amplitude_v=amplitude_v,
            base_v=base_v,
            width_s=width_s,
            period_s=period_s,
            meas_start_pct=meas_start_pct,
            meas_stop_pct=meas_stop_pct,
            source_channel=source_channel,
            hold_other_at_zero=hold_other_at_zero,
            force_fixed_ranges=force_fixed_ranges,
            v_meas_range=v_meas_range,
            i_meas_range=i_meas_range,
            num_pulses=num_pulses,
            delay_s=delay_s,
            outputs_on=outputs_on,
        )

    def start(self) -> None:
        self.pmu.start()

    def wait(self, *, timeout_s: float = 30.0, poll_s: float = 0.02) -> None:
        self.pmu.wait(timeout_s=timeout_s, poll_s=poll_s)

    def fetch(self, *, channel: int = 1) -> pd.DataFrame:
        return self.pmu.fetch(channel=channel)

    def set_trigger_output(self, *, state: bool) -> None:
        self.pmu.set_trigger_output(state)

    def set_trigger_polarity(self, *, polarity: int) -> None:
        self.pmu.set_trigger_polarity(polarity)

    def estimate_runtime_from_params(
        self,
        pmu_params: dict,
        fg_params: dict | None = None,
        *,
        include_pre_sleep: bool = False,
        default_pre_sleep_s: float = 2.0,
    ) -> dict:
        """Estimate total runtime for a PMU measurement from waveform params.

        Returns a dict with a breakdown and the total estimate in seconds.

        Assumptions:
        - PMU runtime ~= (delay_s or 0) + num_pulses * period_s
        - Measurement window (meas_start_pct/stop_pct) does not change total runtime
        - Optional pre-sleep (e.g., arming FG) can be included
        - FG burst delay is informational; it generally does not extend PMU runtime
        """
        # PMU parameters with defaults
        amplitude_v = float(pmu_params.get("amplitude_v", 0.0))
        base_v = float(pmu_params.get("base_v", 0.0))
        width_s = float(pmu_params.get("width_s", 10e-6))
        period_s = float(pmu_params.get("period_s", 20e-6))
        meas_start_pct = float(pmu_params.get("meas_start_pct", 0.1))
        meas_stop_pct = float(pmu_params.get("meas_stop_pct", 0.9))
        num_pulses = int(pmu_params.get("num_pulses", 1))
        delay_s = pmu_params.get("delay_s", None)
        delay_s_val = float(delay_s) if delay_s is not None else 0.0

        # Derived windows (informational)
        capture_window_s = max(0.0, (meas_stop_pct - meas_start_pct)) * width_s

        # PMU active time
        pmu_active_s = delay_s_val + max(0, num_pulses) * period_s

        # Optional pre-sleep/settling (e.g., laser arming sleep in Single_Laser_Pulse_with_read)
        pre_sleep_s = float(default_pre_sleep_s) if include_pre_sleep else 0.0

        # FG parameters (informational)
        fg_burst_delay_s = 0.0
        if fg_params is not None:
            try:
                fg_burst_delay_s = float(fg_params.get("burst_delay_s", 0.0))
            except Exception:
                fg_burst_delay_s = 0.0

        total_estimate_s = pre_sleep_s + pmu_active_s

        return {
            "amplitude_v": amplitude_v,
            "width_s": width_s,
            "period_s": period_s,
            "num_pulses": num_pulses,
            "delay_s": delay_s_val,
            "capture_window_s": capture_window_s,
            "pmu_active_s": pmu_active_s,
            "pre_sleep_s": pre_sleep_s,
            "fg_burst_delay_s": fg_burst_delay_s,
            "total_estimate_s": total_estimate_s,
        }

    # ------------------------------
    # Moved from MemristorMeasurements
    # ------------------------------
    def pulse_iv_sweep(
        self,
        levels: list[float],
        width_s: float,
        period_s: float,
        source_channel: int = 1,
        v_meas_range: float = 2.0,
        i_meas_range: float = 20e-6,
        meas_start_pct: float = 0.85,
        meas_stop_pct: float = 0.98,
    ) -> dict:
        rows = []
        raw_all = []
        for vset in list(levels or []):
            df = self.pmu.measure_at_voltage(
                amplitude_v=float(vset),
                base_v=0.0,
                width_s=float(width_s),
                period_s=float(period_s),
                meas_start_pct=float(meas_start_pct),
                meas_stop_pct=float(meas_stop_pct),
                source_channel=int(source_channel),
                hold_other_at_zero=True,
                force_fixed_ranges=True,
                v_meas_range=float(v_meas_range),
                i_meas_range=float(i_meas_range),
                num_pulses=1,
                timeout_s=30.0,
            )
            df["Level (V)"] = float(vset)
            raw_all.append(df)
            vmed = float(np.nanmedian(df["V (V)"])) if not df.empty else float("nan")
            imed = float(np.nanmedian(df["I (A)"])) if not df.empty else float("nan")
            rmed = float(vmed / imed) if abs(imed) > 1e-15 else float("nan")
            rows.append({"Level (V)": float(vset), "Vmed (V)": vmed, "Imed (A)": imed, "Rmed (Ohm)": rmed})
        return {
            "summary": pd.DataFrame(rows),
            "raw_ch1": pd.concat(raw_all, ignore_index=True) if raw_all else pd.DataFrame(),
        }

    def pulse_width_sweep(
        self,
        voltage_v: float,
        widths_s: list[float],
        period_factor: float = 3.0,
        source_channel: int = 1,
        v_meas_range: float = 2.0,
        i_meas_range: float = 20e-6,
        meas_start_pct: float = 0.85,
        meas_stop_pct: float = 0.98,
    ) -> dict:
        rows = []
        raw_all = []
        for w in list(widths_s or []):
            period = max(float(w) * float(period_factor), 20e-6)
            df = self.pmu.measure_at_voltage(
                amplitude_v=float(voltage_v),
                base_v=0.0,
                width_s=float(w),
                period_s=period,
                meas_start_pct=float(meas_start_pct),
                meas_stop_pct=float(meas_stop_pct),
                source_channel=int(source_channel),
                hold_other_at_zero=True,
                force_fixed_ranges=True,
                v_meas_range=float(v_meas_range),
                i_meas_range=float(i_meas_range),
                num_pulses=1,
                timeout_s=30.0,
            )
            df["Width (s)"] = float(w)
            raw_all.append(df)
            vmed = float(np.nanmedian(df["V (V)"])) if not df.empty else float("nan")
            imed = float(np.nanmedian(df["I (A)"])) if not df.empty else float("nan")
            rmed = float(vmed / imed) if abs(imed) > 1e-15 else float("nan")
            rows.append({"Width (s)": float(w), "Vmed (V)": vmed, "Imed (A)": imed, "Rmed (Ohm)": rmed})
        return {
            "summary": pd.DataFrame(rows),
            "raw_ch1": pd.concat(raw_all, ignore_index=True) if raw_all else pd.DataFrame(),
        }

    def fast_read(
        self,
        read_v: float = 0.2,
        duration_pulses: int = 50,
        width_s: float = 50e-6,
        period_s: float = 100e-6,
        source_channel: int = 1,
        v_meas_range: float = 2.0,
        i_meas_range: float = 200e-6,
    ) -> dict:
        df = self.pmu.measure_at_voltage(
            amplitude_v=float(read_v),
            base_v=0.0,
            width_s=float(width_s),
            period_s=float(period_s),
            meas_start_pct=0.0,
            meas_stop_pct=1.0,
            source_channel=int(source_channel),
            hold_other_at_zero=True,
            force_fixed_ranges=True,
            v_meas_range=float(v_meas_range),
            i_meas_range=float(i_meas_range),
            num_pulses=int(duration_pulses),
            timeout_s=30.0,
        )
        return {"summary": pd.DataFrame(), "raw_ch1": df}

    def perturb_measure(
        self,
        bias_v: float,
        pulse_v: float,
        width_s: float,
        period_s: float,
        delay_s: float = 5e-6,
        num_pulses: int = 3,
        v_meas_range: float = 2.0,
        i_meas_range: float = 200e-6,
        fetch_both: bool = True,
    ) -> dict:
        # This relies on a PMU helper not yet finalized in the PMU class
        res = self.pmu.memr_perturb_relax(
            bias_v=float(bias_v),
            pulse_v=float(pulse_v),
            width_s=float(width_s),
            period_s=float(period_s),
            delay_s=float(delay_s),
            num_pulses=int(num_pulses),
            bias_channel=1,
            aux_channel=2,
            v_meas_range=float(v_meas_range),
            i_meas_range=float(i_meas_range),
            capture_start_pct=0.0,
            capture_stop_pct=1.0,
            fetch_both=bool(fetch_both),
        )
        if fetch_both:
            bias_df, aux_df = res
            return {"summary": pd.DataFrame(), "raw_ch1": bias_df, "raw_ch2": aux_df}
        return {"summary": pd.DataFrame(), "raw_ch1": res}

    def run_modes_from_json(
        self,
        config_path: str,
        bias_v: float = 0.0,
        bias_channel: int = 1,
        aux_channel: int = 2,
    ) -> dict:
        import json
        with open(config_path, "r") as f:
            cfg = json.load(f)

        results: dict[str, dict] = {}

        def run_bias_pulse(ampl_v: float, width: float, period: float, num_p: int) -> dict:
            res = self.pmu.memr_perturb_relax(
                bias_v=float(bias_v),
                pulse_v=float(ampl_v),
                width_s=float(width),
                period_s=float(period),
                delay_s=min(5e-6, max(1e-7, 0.1 * width)),
                num_pulses=int(num_p),
                bias_channel=int(bias_channel),
                aux_channel=int(aux_channel),
                v_meas_range=2.0,
                i_meas_range=200e-6,
                capture_start_pct=0.0,
                capture_stop_pct=1.0,
                fetch_both=True,
            )
            ch1, ch2 = res
            return {"summary": pd.DataFrame(), "raw_ch1": ch1, "raw_ch2": ch2}

        if "Pulse Train" in cfg:
            c = cfg["Pulse Train"]
            results["Pulse Train"] = run_bias_pulse(
                c.get("amplitude_v", 0.5), c.get("width_s", 1e-5), c.get("period_s", 2e-5), c.get("num_pulses", 10)
            )

        if "Pulse Pattern" in cfg:
            c = cfg["Pulse Pattern"]
            amp = float(c.get("amplitude_v", 0.5))
            width = float(c.get("width_s", 1e-5))
            period = float(c.get("period_s", 2e-5))
            pattern = str(c.get("pattern", "1011"))
            raw1_list, raw2_list = [], []
            for bit in pattern:
                a = amp if bit == "1" else 0.0
                r = run_bias_pulse(a, width, period, 1)
                raw1_list.append(r["raw_ch1"])
                raw2_list.append(r["raw_ch2"])
            results["Pulse Pattern"] = {
                "summary": pd.DataFrame(),
                "raw_ch1": pd.concat(raw1_list, ignore_index=True) if raw1_list else pd.DataFrame(),
                "raw_ch2": pd.concat(raw2_list, ignore_index=True) if raw2_list else pd.DataFrame(),
            }

        if "Amplitude Sweep" in cfg:
            c = cfg["Amplitude Sweep"]
            start = float(c.get("base_v", 0.0))
            stop = float(c.get("stop_v", 1.0))
            step = float(c.get("step_v", 0.1))
            width = float(c.get("width_s", 1e-5))
            period = float(c.get("period_s", 2e-5))
            levels = list(np.arange(start, stop + step / 2.0, step))
            rows, raw1_list, raw2_list = [], [], []
            for vset in levels:
                r = run_bias_pulse(vset, width, period, 1)
                raw1_list.append(r["raw_ch1"])
                raw2_list.append(r["raw_ch2"])
                df = r["raw_ch1"]
                vmed = float(np.nanmedian(df["V (V)"])) if not df.empty else float("nan")
                imed = float(np.nanmedian(df["I (A)"])) if not df.empty else float("nan")
                rmed = float(vmed / imed) if abs(imed) > 1e-15 else float("nan")
                rows.append({"Level (V)": float(vset), "Vmed (V)": vmed, "Imed (A)": imed, "Rmed (Ohm)": rmed})
            results["Amplitude Sweep"] = {
                "summary": pd.DataFrame(rows),
                "raw_ch1": pd.concat(raw1_list, ignore_index=True) if raw1_list else pd.DataFrame(),
                "raw_ch2": pd.concat(raw2_list, ignore_index=True) if raw2_list else pd.DataFrame(),
            }

        if "Width Sweep" in cfg:
            c = cfg["Width Sweep"]
            amp = float(c.get("amplitude_v", 0.5))
            width = float(c.get("width_s", 1e-5))
            period = float(c.get("period_s", 2e-5))
            num_p = int(c.get("num_pulses", 5))
            results["Width Sweep"] = run_bias_pulse(amp, width, period, num_p)

        if "Transient" in cfg:
            c = cfg["Transient"]
            results["Transient"] = run_bias_pulse(c.get("amplitude_v", 0.5), c.get("width_s", 1e-5), c.get("period_s", 2e-5), 1)

        if "Endurance" in cfg:
            c = cfg["Endurance"]
            results["Endurance"] = run_bias_pulse(
                c.get("amplitude_v", 0.5), c.get("width_s", 1e-5), c.get("period_s", 2e-5), c.get("num_pulses", 100)
            )

        if "DC Measure" in cfg:
            c = cfg["DC Measure"]
            dv = float(c.get("dc_voltage", 0.2))
            capture_s = float(c.get("capture_s", 0.02))
            dt_s = float(c.get("dt_s", 1e-3))
            n = max(1, int(round(capture_s / max(dt_s, 1e-6))))
            fr = self.fast_read(
                read_v=dv, duration_pulses=n, width_s=dt_s, period_s=dt_s, source_channel=bias_channel, v_meas_range=2.0, i_meas_range=200e-6
            )
            results["DC Measure"] = fr

        return results

    # ------------------------------------------------------------
    # Specific experiment: Measure_at_voltage_with_laser_Using_trigger_out_pmu
    # (copied verbatim from orchestrator; do not change internals)
    # ------------------------------------------------------------
    def Single_Laser_Pulse_with_read(
        self,
        pmu_peramiter: dict | None,
        fg_peramiter: dict | None,
        timeout_s: float = 30.0,
    ):
        if self.function_generator is None:
            raise RuntimeError("Function generator not connected: MeasurementServicesPMU(function_generator=None)")

        # Keep a short alias to match the original code body exactly
        self.gen = self.function_generator

        """
        Only pulls data from the active channel.
        requires pmu trigger out and pulse from fg to be very specific
        period = 
        width = > measure time
        """

        # Defaults from working examples (PMU) and provided FG snapshot
        pmu_defaults = {
            "amplitude_v": 0.25,
            "base_v": 0.0,
            "width_s": 50e-6,
            "period_s": 100e-6,
            "meas_start_pct": 0.1,
            "meas_stop_pct": 0.9,
            "source_channel": 1,
            "hold_other_at_zero": True,
            "force_fixed_ranges": True,
            "v_meas_range": 2.0,
            "i_meas_range": 200e-6,
            "num_pulses": 100,
            "delay_s": None,
        }
        fg_defaults = {
            "channel": 1,
            "high_level_v": 1.5,
            "low_level_v": 0.0,
            "period_s": 1.0,
            "pulse_width_s": 0.0002,
            #"duty_pct": 0.02,
            "rise_s": 1.68e-08,
            "fall_s": 1.68e-08,
            #"delay_s": 0.01,
            "mode": "NCYC",
            "cycles": 1,
            "trigger_source": "EXT",
            "burst_delay_s": 3.41e-07,
        }

        est = self.estimate_runtime_from_params(pmu_peramiter, fg_peramiter, include_pre_sleep=True)
        print(est["total_estimate_s"], est)

        pmu_cfg = {**pmu_defaults, **(pmu_peramiter or {})}
        fg_cfg = {**fg_defaults, **(fg_peramiter or {})}

        # Sanity check: ensure FG pulse width covers total PMU measurement time
        # est_effective = self.estimate_runtime_from_params(pmu_cfg, fg_cfg, include_pre_sleep=False)
        # fg_pulse_width_s_effective = float(fg_cfg["pulse_width_s"])
        # if fg_pulse_width_s_effective < est_effective["pmu_active_s"]:
        #     raise ValueError(
        #         f"FG pulse_width_s ({fg_pulse_width_s_effective}s) shorter than PMU active time "
        #         f"({est_effective['pmu_active_s']}s). Increase pulse_width_s or reduce num_pulses/period_s."
        #     )

        amplitude_v = float(pmu_cfg["amplitude_v"]) 
        base_v = float(pmu_cfg["base_v"]) 
        width_s = float(pmu_cfg["width_s"]) 
        period_s = float(pmu_cfg["period_s"]) 
        meas_start_pct = float(pmu_cfg["meas_start_pct"]) 
        meas_stop_pct = float(pmu_cfg["meas_stop_pct"]) 
        source_channel = int(pmu_cfg["source_channel"]) 
        hold_other_at_zero = bool(pmu_cfg["hold_other_at_zero"]) 
        force_fixed_ranges = bool(pmu_cfg["force_fixed_ranges"]) 
        v_meas_range = float(pmu_cfg["v_meas_range"]) 
        i_meas_range = float(pmu_cfg["i_meas_range"]) 
        num_pulses = int(pmu_cfg["num_pulses"]) 
        delay_s = pmu_cfg["delay_s"]

        # FG config from provided snapshot
        fg_channel = int(fg_cfg["channel"])
        fg_high_level_v = fg_cfg["high_level_v"]
        fg_low_level_v = fg_cfg["low_level_v"]
        # Convert period to frequency for driver API
        period_s_val = float(fg_cfg["period_s"]) if fg_cfg.get("period_s") is not None else 1.0
        fg_frequency_hz = (1.0 / period_s_val) if period_s_val else 1.0
        fg_pulse_width_s = fg_cfg["pulse_width_s"]
        #fg_duty_pct = fg_cfg["duty_pct"]
        fg_rise_s = fg_cfg["rise_s"]
        fg_fall_s = fg_cfg["fall_s"]
        #fg_delay_s = fg_cfg["delay_s"]
        fg_mode = str(fg_cfg["mode"]).upper()
        fg_cycles = int(fg_cfg["cycles"])
        fg_trigger_source = str(fg_cfg["trigger_source"]).upper()

        print(fg_pulse_width_s)        
        
        # Prepare PMU
        self.pmu.prepare_measure_at_voltage(
            amplitude_v=amplitude_v,
            base_v=base_v,
            width_s=width_s,
            period_s=period_s,
            meas_start_pct=meas_start_pct,
            meas_stop_pct=meas_stop_pct,
            source_channel=source_channel,
            hold_other_at_zero=hold_other_at_zero,
            force_fixed_ranges=force_fixed_ranges,
            v_meas_range=v_meas_range,
            i_meas_range=i_meas_range,
            num_pulses=num_pulses,
            delay_s=delay_s,
            outputs_on=True,
        )

        # Prepare FG with full shape + EXT burst
        self.gen.set_pulse_shape(
            channel=fg_channel,
            frequency_hz=fg_frequency_hz,
            high_level_v=fg_high_level_v,
            low_level_v=fg_low_level_v,
            #pulse_width_s=fg_pulse_width_s,
            #duty_pct=fg_duty_pct,
            #rise_s=fg_rise_s,
            #fall_s=fg_fall_s,
            #delay_s=fg_delay_s,
        )
        self.gen.enable_burst(
            channel=fg_channel,
            mode=fg_mode,
            cycles=fg_cycles,
            trigger_source=fg_trigger_source,

        )
        #self.gen.output(fg_channel, True)

        # Enable PMU TRIG OUT so FG (TRSR=EXT) can be driven by PMU
        try:
            self.pmu.set_trigger_polarity(1)
        except Exception:
            pass
        try:
            self.pmu.set_trigger_output(True)
        except Exception:
            pass

        
        # Check if FG output is currently on
        fg_output_status = self.gen.get_output_status(fg_channel)

        # Helper: GUI yes/no with fallback to console input
        def _ask_yes_no(title: str, message: str, warning: bool = False) -> bool:
            try:
                # Lazy import to avoid hard dependency in non-GUI contexts
                from tkinter import messagebox as _mb
                opts = {"icon": "warning"} if warning else {}
                return bool(_mb.askyesno(title, message, **opts))
            except Exception:
                try:
                    resp = input(f"{title}: {message} [y/N] ").strip().lower()
                    return resp in ("y", "yes")
                except Exception:
                    return False

        if not fg_output_status:
            # Safety prompt: ensure laser is OFF before arming generator
            proceed = _ask_yes_no(
                title="Laser Safety",
                message=(
                    "Function generator output is currently OFF.\n\n"
                    "Please TURN OFF the laser manually before proceeding.\n\n"
                    "Click Yes once the laser is OFF (or No to cancel)."
                ),
                warning=True,
            )
            if not proceed:
                raise RuntimeError("Operation cancelled by user at laser OFF confirmation.")

        # Turn on FG output to prevent transients
        self.gen.output(fg_channel, True)

        # Confirm laser ON (armed) before running
        proceed_on = _ask_yes_no(
            title="Laser Arm",
            message=(
                "Please TURN THE LASER ON. Function generator is now armed.\n\n"
                "Click Yes once the laser is ON (or No to cancel)."
            ),
            warning=False,
        )
        if not proceed_on:
            raise RuntimeError("Operation cancelled by user at laser ON confirmation.")
        
        

        # give function generator time to settle
        print("sleeping for 2 seconds  ")
        time.sleep(2)

        self.pmu.start()
        self.pmu.wait(timeout_s=float(timeout_s))
        df = self.pmu.fetch(channel=int(source_channel)) 

        print("##################")
        print("dont forget delay is disabled youn need to manualy input!")
        print("##################")
        return df


