"""
Single Measurement Runner
=========================

Encapsulates the legacy single-measurement workflow that historically lived
inside `Measurement_GUI.start_measurement`.  The goal is to slowly peel logic
out of the GUI class so it focuses on wiring callbacks and delegating to
services.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import tkinter as tk
from tkinter import messagebox

from Measurments.measurement_services_smu import VoltageRangeMode


def find_largest_number_in_folder(folder: str | Path) -> Optional[int]:
    """
    Return the largest numeric prefix found in ``folder`` filenames.

    The historical GUI saved IV sweeps using the pattern
    ``{index}-{sweep_type}-...``, so we scan existing files to increment the
    prefix safely.
    """
    try:
        entries = os.listdir(folder)
    except FileNotFoundError:
        return None
    max_idx: Optional[int] = None
    for name in entries:
        try:
            prefix = name.split("-", 1)[0]
            value = int(prefix)
        except Exception:
            continue
        if max_idx is None or value > max_idx:
            max_idx = value
    return max_idx


class SingleMeasurementRunner:
    """
    Orchestrate the "standard" DC IV measurement path.

    The runner proxies attribute access back to the GUI instance so existing
    logic can be migrated with minimal churn while we continue to tease apart
    responsibilities.
    """

    __slots__ = ("_gui",)

    def __init__(self, gui: Any) -> None:
        object.__setattr__(self, "_gui", gui)

    # Proxy attribute access/assignment back to the GUI -----------------
    def __getattr__(self, item: str) -> Any:  # pragma: no cover - passthrough
        return getattr(self._gui, item)

    def __setattr__(self, key: str, value: Any) -> None:  # pragma: no cover
        setattr(self._gui, key, value)

    # Public API --------------------------------------------------------
    def run_standard_iv(self) -> None:
        """
        Execute the legacy DC IV sweep workflow (no special excitation mode).

        This block is a near lift-and-shift from the original GUI method; once
        we have all helper modules in place we can streamline and unit test it.
        """

        # Build sweep parameters from Tk variables ----------------------
        start_v = self._safe_get_float(self.start_voltage, "Start Voltage")
        if start_v is None:
            self.measuring = False
            return
        stop_v = self._safe_get_float(self.voltage_high, "Stop Voltage")
        if stop_v is None:
            self.measuring = False
            return

        neg_stop_v: Optional[float] = None
        try:
            raw_neg = (
                self.voltage_low_str.get().strip()
                if hasattr(self, "voltage_low_str")
                else ""
            )
            if raw_neg != "":
                neg_stop_v = float(raw_neg)
        except Exception:
            neg_stop_v = None

        sweeps_val = self._safe_get_float(self.sweeps, "Sweeps", default=1)
        if sweeps_val is None:
            self.measuring = False
            return
        sweeps = int(sweeps_val)

        step_v = self._safe_get_float(self.step_size, "Step Size", default=0.1)
        if step_v is None:
            self.measuring = False
            return

        step_delay = self._safe_get_float(self.step_delay, "Step Delay", default=0.05)
        if step_delay is None:
            self.measuring = False
            return

        icc = self._safe_get_float(self.icc, "Compliance (Icc)", default=1e-3)
        if icc is None:
            self.measuring = False
            return

        pause = self._safe_get_float(self.pause, "Pause", default=0.0)
        if pause is None:
            self.measuring = False
            return

        led = self.led.get()
        led_power = self._safe_get_float(self.led_power, "LED Power", default=1.0)
        if led_power is None:
            self.measuring = False
            return

        sequence = self.sequence.get().strip()
        mode = (
            self.sweep_mode_var.get()
            if hasattr(self, "sweep_mode_var")
            else VoltageRangeMode.FIXED_STEP
        )
        sweep_rate = (
            float(self.var_sweep_rate.get())
            if mode == VoltageRangeMode.FIXED_SWEEP_RATE
            else None
        )
        total_time = (
            float(self.var_total_time.get())
            if mode == VoltageRangeMode.FIXED_VOLTAGE_TIME
            else None
        )
        nsteps = (
            int(self.var_num_steps.get())
            if mode
            in (VoltageRangeMode.FIXED_SWEEP_RATE, VoltageRangeMode.FIXED_VOLTAGE_TIME)
            else None
        )
        try:
            sweep_type = self.sweep_type_var.get().strip().upper() or "FS"
        except Exception:
            sweep_type = "FS"

        self.stop_measurement_flag = False  # Reset stop flag
        self.bring_to_top()

        if not (self.use_custom_save_var.get() and self.custom_save_location):
            self.check_for_sample_name()

        if self.current_device in self.device_list:
            start_index = self.device_list.index(self.current_device)
        else:
            start_index = 0
        device_count = 1 if self.single_device_flag else len(self.device_list)

        # Helper to resolve per-device save directories -----------------
        def _ensure_save_dir() -> str:
            save_dir = self._get_save_directory(
                self.sample_name_var.get(),
                self.final_device_letter,
                self.final_device_number,
            )
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            return save_dir

        # Execute measurement over each device --------------------------
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                print("Measurement interrupted!")
                break

            self.keithley.set_voltage(0, self.icc.get())
            self.keithley.enable_output(True)

            print("working on device - ", device)
            self.set_status_message(f"Measuring {device}...")
            self.master.update()
            time.sleep(1)

            icc_val = float(self.icc.get())
            smu_type_str = getattr(self, "SMU_type", "Keithley 2401")

            num_points_estimate = (
                int(abs(stop_v - start_v) / step_v) + 1 if step_v else 100
            )
            using_hardware_sweep = (
                smu_type_str == "Keithley 4200A"
                and num_points_estimate > 20
                and step_delay < 0.05
            )

            if using_hardware_sweep:
                self.set_status_message("Hardware sweep in progress (fast mode)...")
                self.master.update()

                from Measurments.sweep_config import SweepConfig
                from Measurments.source_modes import SourceMode

                source_mode_var = getattr(self, "source_mode_var", None)
                if source_mode_var:
                    source_mode = (
                        SourceMode.CURRENT
                        if source_mode_var.get() == "current"
                        else SourceMode.VOLTAGE
                    )
                else:
                    source_mode = SourceMode.VOLTAGE

                config = SweepConfig(
                    start_v=start_v,
                    stop_v=stop_v,
                    step_v=step_v,
                    neg_stop_v=neg_stop_v,
                    step_delay=step_delay,
                    sweep_type=sweep_type,
                    sweeps=sweeps,
                    pause_s=pause,
                    icc=icc_val,
                    led=bool(led),
                    power=led_power,
                    sequence=sequence,
                    source_mode=source_mode,
                )

                v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep_v2(
                    keithley=self.keithley,
                    config=config,
                    smu_type=smu_type_str,
                    psu=getattr(self, "psu", None),
                    optical=getattr(self, "optical", None),
                    should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                    on_point=None,
                )

                if timestamps:
                    self.set_status_message(
                        f"Sweep complete: {len(v_arr)} points in {timestamps[-1]:.2f}s"
                    )
            else:
                def _on_point(v, i, t_s):
                    self.v_arr_disp.append(v)
                    self.c_arr_disp.append(i)
                    self.t_arr_disp.append(t_s)

                from Measurments.source_modes import SourceMode

                source_mode_var = getattr(self, "source_mode_var", None)
                if source_mode_var:
                    source_mode = (
                        SourceMode.CURRENT
                        if source_mode_var.get() == "current"
                        else SourceMode.VOLTAGE
                    )
                else:
                    source_mode = SourceMode.VOLTAGE

                v_arr, c_arr, timestamps = self.measurement_service.run_iv_sweep(
                    keithley=self.keithley,
                    icc=icc_val,
                    sweeps=sweeps,
                    step_delay=step_delay,
                    start_v=start_v,
                    stop_v=stop_v,
                    neg_stop_v=neg_stop_v,
                    step_v=step_v,
                    sweep_type=sweep_type,
                    mode=mode,
                    sweep_rate_v_per_s=sweep_rate,
                    total_time_s=total_time,
                    num_steps=nsteps,
                    psu=getattr(self, "psu", None),
                    led=bool(led),
                    power=led_power,
                    optical=getattr(self, "optical", None),
                    sequence=sequence,
                    pause_s=pause,
                    smu_type=smu_type_str,
                    should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                    on_point=_on_point,
                    source_mode=source_mode,
                )

            if hasattr(self, "endurance_ratios") and self.endurance_ratios:
                self.ax_endurance.clear()
                self.ax_endurance.set_title("Endurance (ON/OFF)")
                self.ax_endurance.set_xlabel("Cycle")
                self.ax_endurance.set_ylabel("ON/OFF Ratio")
                self.ax_endurance.plot(
                    range(1, len(self.endurance_ratios) + 1),
                    self.endurance_ratios,
                    marker="o",
                )
                self.canvas_endurance.draw()

            if (
                hasattr(self, "retention_times")
                and self.retention_times
                and hasattr(self, "retention_currents")
            ):
                self.ax_retention.clear()
                self.ax_retention.set_title("Retention")
                self.ax_retention.set_xlabel("Time (s)")
                self.ax_retention.set_ylabel("Current (A)")
                self.ax_retention.set_xscale("log")
                self.ax_retention.set_yscale("log")
                self.ax_retention.plot(
                    self.retention_times, self.retention_currents, marker="x"
                )
                self.canvas_retention.draw()

            data = np.column_stack((v_arr, c_arr, timestamps))
            save_dir = _ensure_save_dir()

            additional = f"-{sequence}" if sequence else ""
            try:
                extra_info_src = getattr(self, "additional_info_var", "")
                if hasattr(extra_info_src, "get"):
                    extra_value = extra_info_src.get().strip()
                else:
                    extra_value = str(extra_info_src).strip()
                extra_info = f"-{extra_value}" if extra_value else ""
            except Exception:
                extra_info = ""

            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            opt_suffix = ""
            try:
                if hasattr(self, "optical") and self.optical is not None:
                    caps = getattr(self.optical, "capabilities", {})
                    if str(caps.get("type", "")).lower() == "laser" and bool(led):
                        unit = str(caps.get("units", "mW"))
                        lvl = float(led_power)
                        opt_suffix = f"-LASER{lvl}{unit}"
            except Exception:
                opt_suffix = ""

            name = (
                f"{save_key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-"
                f"Py-{sweeps}{additional}{opt_suffix}{extra_info}"
            )
            file_path = f"{save_dir}\\{name}.txt"

            try:
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.3E\t%0.3E\t%0.3E",
                    header="Voltage Current Time",
                    comments="",
                )
                abs_path = os.path.abspath(file_path)
                print(f"[SAVE] File saved to: {abs_path}")
                self.log_terminal(f"File saved: {abs_path}")
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save file: {exc}")

            self.graphs_show(v_arr, c_arr, "1", stop_v)
            self.keithley.enable_output(False)

            if self.single_device_flag:
                print("measuring one device only")
                break

            self.sample_gui.next_device()

        # Finalise run ---------------------------------------------------
        self._finalize_output()
        self.measuring = False
        self.set_status_message("Measurement Complete")

        save_dir = self._get_save_directory(
            self.sample_name_var.get(),
            self.final_device_letter,
            self.final_device_number,
        )
        try:
            self._save_summary_artifacts(save_dir)
        except Exception as exc:
            print(f"[SAVE ERROR] Failed to save summary plots: {exc}")

        telegram_enabled = bool(self.telegram and self.telegram.is_enabled())
        if not telegram_enabled:
            messagebox.showinfo("Complete", "Measurements finished.")
            return

        try:
            combined = getattr(self, "_last_combined_summary_path", None)
            if self.telegram:
                self.telegram.start_post_measurement_worker(save_dir, combined)
        except Exception as exc:
            print(f"[SAVE ERROR] Post-measurement save failed: {exc}")


