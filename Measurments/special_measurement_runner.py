"""
Special Measurement Runner
==========================

Handles ISPP, pulse-width sweep, threshold search, and transient decay flows.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import numpy as np
from tkinter import messagebox

from Measurments.single_measurement_runner import find_largest_number_in_folder


class SpecialMeasurementRunner:
    """Coordinate ISPP / pulse-width / threshold / transient routines."""

    __slots__ = ("_gui",)

    def __init__(self, gui: Any) -> None:
        object.__setattr__(self, "_gui", gui)

    def __getattr__(self, item: str) -> Any:  # pragma: no cover - passthrough
        return getattr(self._gui, item)

    def __setattr__(self, key: str, value: Any) -> None:  # pragma: no cover
        setattr(self._gui, key, value)

    def run(self, excitation: str, device_count: int, start_index: int) -> bool:
        handlers = {
            "ISPP": self._run_ispp,
            "Pulse Width Sweep": self._run_pulse_width_sweep,
            "Threshold Search": self._run_threshold_search,
            "Transient Decay": self._run_transient_decay,
            "Endurance": self._run_endurance,
            "Retention": self._run_retention,
        }
        handler = handlers.get(excitation)
        if not handler:
            return False
        handler(device_count, start_index)
        return True

    # Shared helper ---------------------------------------------------------
    def _ensure_save_dir(self) -> str:
        save_dir = self._gui._get_save_directory(
            self.sample_name_var.get(),
            self.final_device_letter,
            self.final_device_number,
        )
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        return save_dir

    def _finalize(self) -> None:
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

        if not self.telegram.is_enabled():
            messagebox.showinfo("Complete", "Measurements finished.")
            return

        try:
            combined = getattr(self, "_last_combined_summary_path", None)
            self.telegram.start_post_measurement_worker(save_dir, combined)
        except Exception as exc:
            print(f"[SAVE ERROR] Post-measurement save failed: {exc}")

    # Individual mode handlers ----------------------------------------------
    def _run_ispp(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (ISPP)...")
            self.master.update()

            start_v = float(getattr(self, "_ispp_start", self._wrap(0.0)).get())
            stop_v = float(getattr(self, "_ispp_stop", self._wrap(1.0)).get())
            step_v = float(getattr(self, "_ispp_step", self._wrap(0.1)).get())
            pulse_ms = float(getattr(self, "_ispp_pulse_ms", self._wrap(1.0)).get())
            vbase = float(getattr(self, "_ispp_vbase", self._wrap(0.2)).get())
            target = float(getattr(self, "_ispp_target", self._wrap(1e-5)).get())
            inter = float(getattr(self, "_ispp_inter", self._wrap(0.0)).get())
            icc_val = float(self.icc.get())

            v_arr, c_arr, t_arr = self.measurement_service.run_ispp(
                keithley=self.keithley,
                start_v=start_v,
                stop_v=stop_v,
                step_v=step_v,
                vbase=vbase,
                pulse_width_ms=pulse_ms,
                target_current_a=target,
                inter_step_delay_s=inter,
                icc=icc_val,
                smu_type=getattr(self, "SMU_type", "Keithley 2401"),
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=None,
                validate_timing=True,
            )

            try:
                self.graphs_show(v_arr, c_arr, "ISPP", stop_v)
            except Exception:
                pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-ISPP-{stop_v}v-{pulse_ms}ms-Py"
            file_path = Path(save_dir) / f"{name}.txt"
            try:
                data = np.column_stack((v_arr, c_arr, t_arr))
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.3E\t%0.3E\t%0.3E",
                    header="Amplitude(V) Current(A) Time(s)",
                    comments="",
                )
                self.log_terminal(f"File saved: {file_path.resolve()}")
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save file: {exc}")
            
            # Run IV analysis if enabled
            try:
                metadata = {}
                # Call analysis helper
                self._run_analysis_if_enabled(
                    voltage=v_arr,
                    current=c_arr,
                    timestamps=t_arr,
                    save_dir=save_dir,
                    file_name=name,
                    metadata=metadata
                )
            except Exception as exc:
                # Don't interrupt measurement flow if analysis fails
                print(f"[ANALYSIS] Failed to run analysis: {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize()

    def _run_endurance(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (Endurance)...")
            self.master.update()

            set_v = float(self.end_set_v.get())
            reset_v = float(self.end_reset_v.get())
            pulse_ms = float(self.end_pulse_ms.get())
            cycles = int(self.end_cycles.get())
            read_v = float(self.end_read_v.get())
            icc_val = float(self.icc.get())

            def _on_point(v: float, i_val: float, t_s: float) -> None:
                self.v_arr_disp.append(v)
                self.c_arr_disp.append(i_val)
                self.t_arr_disp.append(t_s)

            v_arr, c_arr, t_arr = self.measurement_service.run_endurance(
                keithley=self.keithley,
                set_voltage=set_v,
                reset_voltage=reset_v,
                pulse_width_s=pulse_ms / 1000.0,
                num_cycles=cycles,
                read_voltage=read_v,
                icc=icc_val,
                psu=getattr(self, "psu", None),
                led=False,
                power=1.0,
                optical=getattr(self, "optical", None),
                smu_type=getattr(self, "SMU_type", "Keithley 2401"),
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=_on_point,
            )

            try:
                self.graphs_show(v_arr, c_arr, "ENDURANCE", set_v)
            except Exception:
                pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-ENDURANCE-{set_v}v-{reset_v}v-{pulse_ms}ms-Py"
            file_path = Path(save_dir) / f"{name}.txt"
            try:
                data = np.column_stack((v_arr, c_arr, t_arr))
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.3E\t%0.3E\t%0.3E",
                    header="Voltage(V) Current(A) Time(s)",
                    comments="",
                )
                self.log_terminal(f"File saved: {file_path.resolve()}")
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save endurance file: {exc}")
            
            # Run IV analysis if enabled
            try:
                metadata = {}
                # Call analysis helper
                self._run_analysis_if_enabled(
                    voltage=v_arr,
                    current=c_arr,
                    timestamps=t_arr,
                    save_dir=save_dir,
                    file_name=name,
                    metadata=metadata
                )
            except Exception as exc:
                # Don't interrupt measurement flow if analysis fails
                print(f"[ANALYSIS] Failed to run analysis: {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize()

    def _run_retention(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (Retention)...")
            self.master.update()

            set_v = float(self.ret_set_v.get())
            set_ms = float(self.ret_set_ms.get())
            read_v = float(self.ret_read_v.get())
            try:
                delay_s = float(self.ret_measure_delay.get())
            except Exception:
                delay_s = 10.0
            times_s = [delay_s]
            icc_val = float(self.icc.get())

            def _on_point(v: float, i_val: float, t_s: float) -> None:
                self.v_arr_disp.append(v)
                self.c_arr_disp.append(i_val)
                self.t_arr_disp.append(t_s)

            v_arr, c_arr, t_arr = self.measurement_service.run_retention(
                keithley=self.keithley,
                set_voltage=set_v,
                set_time_s=set_ms / 1000.0,
                read_voltage=read_v,
                repeat_delay_s=0.1,
                number=len(times_s),
                icc=icc_val,
                psu=getattr(self, "psu", None),
                led=False,
                optical=getattr(self, "optical", None),
                smu_type=getattr(self, "SMU_type", "Keithley 2401"),
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=_on_point,
            )

            try:
                self.graphs_show(v_arr, c_arr, "RETENTION", read_v)
            except Exception:
                pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-RETENTION-{set_v}v-{read_v}v-Py"
            file_path = Path(save_dir) / f"{name}.txt"
            try:
                data = np.column_stack((t_arr, c_arr, v_arr))
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.3E\t%0.3E\t%0.3E",
                    header="Time(s) Current(A) Voltage(V)",
                    comments="",
                )
                self.log_terminal(f"File saved: {file_path.resolve()}")
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save retention file: {exc}")
            
            # Run IV analysis if enabled
            try:
                metadata = {}
                # Call analysis helper
                self._run_analysis_if_enabled(
                    voltage=v_arr,
                    current=c_arr,
                    timestamps=t_arr,
                    save_dir=save_dir,
                    file_name=name,
                    metadata=metadata
                )
            except Exception as exc:
                # Don't interrupt measurement flow if analysis fails
                print(f"[ANALYSIS] Failed to run analysis: {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize()

    def _run_pulse_width_sweep(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (Pulse Width Sweep)...")
            self.master.update()

            amp = float(getattr(self, "_pws_amp", self._wrap(0.5)).get())
            widths_csv = str(
                getattr(self, "_pws_widths", self._wrap("1,2,5,10", tk_type="str")).get()
            )
            try:
                widths_ms = [float(x.strip()) for x in widths_csv.split(",") if x.strip()]
            except Exception:
                widths_ms = [1.0, 2.0, 5.0, 10.0]
            vbase = float(getattr(self, "_pws_vbase", self._wrap(0.2)).get())
            inter = float(getattr(self, "_pws_inter", self._wrap(0.0)).get())
            icc_val = float(self.icc.get())

            w_arr, i_arr, t_arr = self.measurement_service.run_pulse_width_sweep(
                keithley=self.keithley,
                amplitude_v=amp,
                widths_ms=widths_ms,
                vbase=vbase,
                icc=icc_val,
                smu_type=getattr(self, "SMU_type", "Keithley 2401"),
                inter_step_delay_s=inter,
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=None,
                validate_timing=True,
            )

            try:
                self.graphs_show(w_arr, i_arr, "PWidth", amp)
            except Exception:
                pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-PWIDTH-{amp}v-Py"
            file_path = Path(save_dir) / f"{name}.txt"
            try:
                data = np.column_stack((w_arr, i_arr, t_arr))
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.3E\t%0.3E\t%0.3E",
                    header="Width(ms) Current(A) Time(s)",
                    comments="",
                )
                self.log_terminal(f"File saved: {file_path.resolve()}")
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save file: {exc}")
            
            # Note: Pulse width sweep uses width arrays, not voltage arrays
            # Analysis may not be directly applicable, but we'll try with width as "voltage"
            try:
                metadata = {}
                # Use width array as voltage for analysis (may not be ideal, but allows analysis)
                self._run_analysis_if_enabled(
                    voltage=w_arr,  # Using width as voltage proxy
                    current=i_arr,
                    timestamps=t_arr,
                    save_dir=save_dir,
                    file_name=name,
                    metadata=metadata
                )
            except Exception as exc:
                # Don't interrupt measurement flow if analysis fails
                print(f"[ANALYSIS] Failed to run analysis (pulse width sweep may not be suitable): {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize()

    def _run_threshold_search(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (Threshold Search)...")
            self.master.update()

            v_lo = float(getattr(self, "_th_lo", self._wrap(0.0)).get())
            v_hi = float(getattr(self, "_th_hi", self._wrap(1.0)).get())
            pulse_ms = float(getattr(self, "_th_pulse_ms", self._wrap(1.0)).get())
            vbase = float(getattr(self, "_th_vbase", self._wrap(0.2)).get())
            target = float(getattr(self, "_th_target", self._wrap(1e-5)).get())
            iters = int(getattr(self, "_th_iters", self._wrap(12, tk_type="int")).get())
            icc_val = float(self.icc.get())

            v_arr, c_arr, t_arr = self.measurement_service.run_threshold_search(
                keithley=self.keithley,
                v_low=v_lo,
                v_high=v_hi,
                vbase=vbase,
                pulse_width_ms=pulse_ms,
                target_current_a=target,
                max_iters=iters,
                icc=icc_val,
                smu_type=getattr(self, "SMU_type", "Keithley 2401"),
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=None,
                validate_timing=True,
            )

            try:
                self.graphs_show(v_arr, c_arr, "THRESH", v_hi)
            except Exception:
                pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-THRESH-{v_lo}-{v_hi}v-{pulse_ms}ms-Py"
            file_path = Path(save_dir) / f"{name}.txt"
            try:
                data = np.column_stack((v_arr, c_arr, t_arr))
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.3E\t%0.3E\t%0.3E",
                    header="TestV(V) Current(A) Time(s)",
                    comments="",
                )
                self.log_terminal(f"File saved: {file_path.resolve()}")
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save file: {exc}")
            
            # Run IV analysis if enabled
            try:
                metadata = {}
                # Call analysis helper
                self._run_analysis_if_enabled(
                    voltage=v_arr,
                    current=c_arr,
                    timestamps=t_arr,
                    save_dir=save_dir,
                    file_name=name,
                    metadata=metadata
                )
            except Exception as exc:
                # Don't interrupt measurement flow if analysis fails
                print(f"[ANALYSIS] Failed to run analysis: {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize()

    def _run_transient_decay(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (Transient Decay)...")
            self.master.update()

            p_v = float(getattr(self, "_tr_pulse_v", self._wrap(0.8)).get())
            p_ms = float(getattr(self, "_tr_pulse_ms", self._wrap(1.0)).get())
            r_v = float(getattr(self, "_tr_read_v", self._wrap(0.2)).get())
            cap_s = float(getattr(self, "_tr_cap_s", self._wrap(1.0)).get())
            dt_s = float(getattr(self, "_tr_dt_s", self._wrap(0.001)).get())
            icc_val = float(self.icc.get())

            t_arr, i_arr, v_arr = self.measurement_service.run_transient_decay(
                keithley=self.keithley,
                pulse_voltage=p_v,
                pulse_width_ms=p_ms,
                read_voltage=r_v,
                capture_time_s=cap_s,
                sample_dt_s=dt_s,
                icc=icc_val,
                smu_type=getattr(self, "SMU_type", "Keithley 2401"),
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=None,
            )

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-TRANSIENT-{p_v}v-{p_ms}ms-Read{r_v}v-{cap_s}s@{dt_s}s-Py"
            file_path = Path(save_dir) / f"{name}.txt"
            try:
                data = np.column_stack((v_arr, i_arr, t_arr))
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.6E\t%0.6E\t%0.6E",
                    header="Voltage(V) Current(A) Time(s)",
                    comments="",
                )
                self.log_terminal(f"File saved: {file_path.resolve()}")
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save file: {exc}")
            
            # Run IV analysis if enabled
            try:
                metadata = {}
                # Call analysis helper
                self._run_analysis_if_enabled(
                    voltage=v_arr,
                    current=i_arr,
                    timestamps=t_arr,
                    save_dir=save_dir,
                    file_name=name,
                    metadata=metadata
                )
            except Exception as exc:
                # Don't interrupt measurement flow if analysis fails
                print(f"[ANALYSIS] Failed to run analysis: {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize()

    # Utility ---------------------------------------------------------------
    def _wrap(self, value: Any, tk_type: str = "double"):
        """Create Tkinter variable type clones when original attributes missing."""
        import tkinter as tk  # local import to avoid circular issues

        if tk_type == "double":
            return tk.DoubleVar(value=value)
        if tk_type == "int":
            return tk.IntVar(value=value)
        if tk_type == "str":
            return tk.StringVar(value=value)
        return tk.DoubleVar(value=value)


