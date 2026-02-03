"""
Pulsed Measurement Runner
=========================

Encapsulates the legacy SMU/PMU pulsed measurement flows that used to live
inside `Measurement_GUI.start_measurement`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from Measurements.single_measurement_runner import find_largest_number_in_folder
from tkinter import messagebox


class PulsedMeasurementRunner:
    """Coordinate pulsed IV / fast pulse / fast hold measurement flows."""

    __slots__ = ("_gui",)

    def __init__(self, gui: Any) -> None:
        object.__setattr__(self, "_gui", gui)

    # Proxy attribute access back to the GUI ---------------------------------
    def __getattr__(self, item: str) -> Any:  # pragma: no cover - passthrough
        return getattr(self._gui, item)

    def __setattr__(self, key: str, value: Any) -> None:  # pragma: no cover
        setattr(self._gui, key, value)

    # Public entrypoint ------------------------------------------------------
    def run(self, excitation: str, device_count: int, start_index: int) -> bool:
        """
        Dispatch pulsed measurement modes. Returns True if the excitation was
        handled, False to let the caller continue with other branches.
        """
        handlers = {
            "Pulsed IV <1.5V": self._run_pulsed_lt_1p5,
            "Pulsed IV >1.5V": self._run_pulsed_gt_1p5,
            "Pulsed IV (fixed 20V)": self._run_pulsed_fixed_20,
            "Fast Pulses": self._run_fast_pulses,
            "Fast Hold": self._run_fast_hold,
        }
        handler = handlers.get(excitation)
        if not handler:
            return False

        handler(device_count, start_index)
        return True

    # Internal helpers -------------------------------------------------------
    def _ensure_save_dir(self) -> str:
        save_dir = self._gui._get_save_directory(
            self.sample_name_var.get(),
            self.final_device_letter,
            self.final_device_number,
        )
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        return save_dir

    def _run_pulsed_lt_1p5(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break

            self.set_status_message(f"Measuring {device} (SMU_AND_PMU Pulsed IV <1.5v)...")
            self.master.update()

            start_v = float(self.ex_piv_start.get())
            stop_v = float(self.ex_piv_stop.get())
            step_v = float(self.ex_piv_step.get()) if self.ex_piv_step.get() != 0 else None
            nsteps = int(self.ex_piv_nsteps.get()) if int(self.ex_piv_nsteps.get() or 0) > 0 else None
            width_ms = float(self.ex_piv_width_ms.get())
            width_ms = max(self._min_pulse_width_ms(), width_ms)
            vbase = float(self.ex_piv_vbase.get())
            inter_step = float(self.ex_piv_inter_delay.get())
            icc_val = float(self.icc.get())
            smu_type = getattr(self, "SMU_type", "Keithley 2401")

            try:
                self.keithley.prepare_for_pulses(
                    Icc=icc_val,
                    v_range=20.0,
                    ovp=22.0,
                    use_remote_sense=False,
                    autozero_off=True,
                )
            except Exception:
                pass

            try:
                v_out, i_out, t_out = self.measurement_service.run_pulsed_iv_sweep(
                    keithley=self.keithley,
                    start_v=start_v,
                    stop_v=stop_v,
                    step_v=step_v,
                    num_steps=nsteps,
                    pulse_width_ms=width_ms,
                    vbase=vbase,
                    inter_step_delay_s=inter_step,
                    icc=icc_val,
                    smu_type=smu_type,
                    should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                    on_point=None,
                    validate_timing=True,
                    manage_session=False,
                )
            finally:
                try:
                    self.keithley.finish_pulses(Icc=icc_val, restore_autozero=True)
                except Exception:
                    pass

            # Note: graphs_show is only for custom measurements - normal sweeps don't add to "all sweeps" graph
            # try:
            #     self.graphs_show(v_out, i_out, "PULSED_IV", stop_v)
            # except Exception:
            #     pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-PULSED_IV_LT1p5-{stop_v}v-{width_ms}ms-Py"
            file_path = os.path.join(save_dir, f"{name}.txt")

            try:
                data = np.column_stack((v_out, i_out, t_out))
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.3E\t%0.3E\t%0.3E",
                    header="Amplitude(V) Current(A) Time(s)",
                    comments="",
                )
                self.log_terminal(f"File saved: {os.path.abspath(file_path)}")
                # Store filename for analysis
                self._last_pulsed_file_name = name
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save file: {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize_mode()

    def _run_pulsed_gt_1p5(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (SMU_AND_PMU Pulsed IV >1.5v)...")
            self.master.update()

            start_v = float(self.ex_piv_start.get())
            stop_v = float(self.ex_piv_stop.get())
            step_v = float(self.ex_piv_step.get()) if self.ex_piv_step.get() != 0 else None
            nsteps = int(self.ex_piv_nsteps.get()) if int(self.ex_piv_nsteps.get() or 0) > 0 else None
            width_ms = max(self._min_pulse_width_ms(), float(self.ex_piv_width_ms.get()))
            vbase = float(self.ex_piv_vbase.get())
            inter_step = float(self.ex_piv_inter_delay.get())
            icc_val = float(self.icc.get())
            smu_type = getattr(self, "SMU_type", "Keithley 2401")

            try:
                self.keithley.prepare_for_pulses(
                    Icc=icc_val,
                    v_range=20.0,
                    ovp=22.0,
                    use_remote_sense=False,
                    autozero_off=True,
                )
            except Exception:
                pass

            try:
                v_out, i_out, t_out = self.measurement_service.run_pulsed_iv_sweep(
                    keithley=self.keithley,
                    start_v=start_v,
                    stop_v=stop_v,
                    step_v=step_v,
                    num_steps=nsteps,
                    pulse_width_ms=width_ms,
                    vbase=vbase,
                    inter_step_delay_s=inter_step,
                    icc=icc_val,
                    smu_type=smu_type,
                    should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                    on_point=None,
                    validate_timing=True,
                    manage_session=False,
                )
            finally:
                try:
                    self.keithley.finish_pulses(Icc=icc_val, restore_autozero=True)
                except Exception:
                    pass

            # Note: graphs_show is only for custom measurements - normal sweeps don't add to "all sweeps" graph
            # try:
            #     self.graphs_show(v_out, i_out, "PULSED_IV_GT1p5", stop_v)
            # except Exception:
            #     pass

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize_mode()

    def _run_pulsed_fixed_20(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(
                f"Measuring {device} (SMU_AND_PMU Pulsed IV - fixed 20V)..."
            )
            self.master.update()

            start_v = float(self.ex_piv_start.get())
            stop_v = float(self.ex_piv_stop.get())
            step_v = float(self.ex_piv_step.get()) if self.ex_piv_step.get() != 0 else None
            nsteps = int(self.ex_piv_nsteps.get()) if int(self.ex_piv_nsteps.get() or 0) > 0 else None
            width_ms = max(self._min_pulse_width_ms(), float(self.ex_piv_width_ms.get()))
            vbase = float(self.ex_piv_vbase.get())
            inter_step = float(self.ex_piv_inter_delay.get())
            icc_val = float(self.icc.get())
            smu_type = getattr(self, "SMU_type", "Keithley 2401")

            try:
                self.keithley.prepare_for_pulses(
                    Icc=icc_val,
                    v_range=20.0,
                    ovp=21.0,
                    use_remote_sense=False,
                    autozero_off=True,
                )
            except Exception:
                pass

            v_out, i_out, t_out, dbg = self.measurement_service.run_pulsed_iv_sweep_debug(
                keithley=self.keithley,
                start_v=start_v,
                stop_v=stop_v,
                step_v=step_v,
                num_steps=nsteps,
                pulse_width_ms=width_ms,
                vbase=vbase,
                inter_step_delay_s=inter_step,
                icc=icc_val,
                smu_type=smu_type,
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=None,
                validate_timing=True,
            )

            try:
                self.keithley.finish_pulses(Icc=icc_val, restore_autozero=True)
            except Exception:
                pass

            # Note: graphs_show is only for custom measurements - normal sweeps don't add to "all sweeps" graph
            # try:
            #     self.graphs_show(v_out, i_out, "PULSED_IV_FIXED", stop_v)
            # except Exception:
            #     pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-PULSED_IV_FIXED20-{stop_v}v-{width_ms}ms-Py"
            file_path = Path(save_dir) / f"{name}.txt"
            dbg_path = Path(save_dir) / f"{name}_debug.json"

            try:
                data = np.column_stack((v_out, i_out, t_out))
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.3E\t%0.3E\t%0.3E",
                    header="Amplitude(V) Current(A) Time(s)",
                    comments="",
                )
                self.log_terminal(f"File saved: {file_path.resolve()}")
                # Store filename for analysis
                self._last_pulsed_file_name = name
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save file: {exc}")

            try:
                with dbg_path.open("w", encoding="utf-8") as handle:
                    json.dump(dbg, handle, indent=2)
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save debug file: {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize_mode()

    def _run_fast_pulses(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (SMU_AND_PMU Fast Pulses)...")
            self.master.update()

            pulse_v = float(self.ex_fp_voltage.get())
            width_ms = max(self._min_pulse_width_ms(), float(self.ex_fp_width_ms.get()))
            num = max(1, int(self.ex_fp_num.get()))
            inter = (
                0.0 if bool(self.ex_fp_max_speed.get()) else float(self.ex_fp_inter_delay.get())
            )
            vbase = float(self.ex_fp_vbase.get())
            icc_val = float(self.icc.get())
            smu_type = getattr(self, "SMU_type", "Keithley 2401")

            v_arr, c_arr, t_arr = self.measurement_service.run_pulse_measurement(
                keithley=self.keithley,
                pulse_voltage=pulse_v,
                pulse_width_ms=width_ms,
                num_pulses=num,
                read_voltage=vbase,
                inter_pulse_delay_s=inter,
                icc=icc_val,
                smu_type=smu_type,
                psu=getattr(self, "psu", None),
                led=False,
                power=1.0,
                sequence=None,
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=None,
                validate_timing=True,
            )

            try:
                self.v_arr_disp.extend(list(v_arr))
                self.c_arr_disp.extend(list(c_arr))
                self.t_arr_disp.extend(list(t_arr))
            except Exception:
                pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-FAST_PULSES-{pulse_v}v-{width_ms}ms-N{num}-Py"
            file_path = Path(save_dir) / f"{name}.txt"

            try:
                data = np.column_stack((t_arr, c_arr, v_arr))
                np.savetxt(
                    file_path,
                    data,
                    fmt="%0.9E\t%0.9E\t%0.6E",
                    header="Time(s) Current(A) Voltage(V)",
                    comments="",
                )
                self.log_terminal(f"File saved: {file_path.resolve()}")
                # Store filename for analysis
                self._last_pulsed_file_name = name
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save file: {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize_mode()

    def _run_fast_hold(self, device_count: int, start_index: int) -> None:
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (SMU_AND_PMU Fast Hold)...")
            self.master.update()

            hold_v = float(self.ex_fh_voltage.get())
            duration = float(self.ex_fh_duration.get())
            dt = float(self.ex_fh_sample_dt.get())
            icc_val = float(self.icc.get())

            v_arr, c_arr, t_arr = self.measurement_service.run_dc_capture(
                keithley=self.keithley,
                voltage_v=hold_v,
                capture_time_s=duration,
                sample_dt_s=dt,
                icc=icc_val,
                on_point=None,
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
            )

            try:
                self.v_arr_disp.extend(list(v_arr))
                self.c_arr_disp.extend(list(c_arr))
                self.t_arr_disp.extend(list(t_arr))
            except Exception:
                pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-FAST_HOLD-{hold_v}v-{duration}s-Py"
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
                # Store filename for analysis
                self._last_pulsed_file_name = name
            except Exception as exc:
                print(f"[SAVE ERROR] Failed to save file: {exc}")

            if not self.single_device_flag:
                self.sample_gui.next_device()
                time.sleep(0.1)
                self.sample_gui.change_relays()
                time.sleep(0.1)

        self._finalize_mode()

    # Misc helpers -----------------------------------------------------------
    def _min_pulse_width_ms(self) -> float:
        try:
            smu_type = getattr(self, "SMU_type", "Keithley 2401")
            limits = self.measurement_service.get_smu_limits(smu_type)
            return float(limits.get("min_pulse_width_ms", 1.0))
        except Exception:
            return 1.0

    def _finalize_mode(self) -> None:
        # Run analysis on collected data if available
        try:
            # Check if we have display arrays with data
            if hasattr(self, 'v_arr_disp') and hasattr(self, 'c_arr_disp'):
                v_arr = list(self.v_arr_disp) if self.v_arr_disp else []
                c_arr = list(self.c_arr_disp) if self.c_arr_disp else []
                
                if len(v_arr) > 0 and len(c_arr) > 0:
                    save_dir = self._get_save_directory(
                        self.sample_name_var.get(),
                        self.final_device_letter,
                        self.final_device_number,
                    )
                    
                    # Try to get the last saved filename from the most recent measurement
                    # Use a generic name if we can't determine it
                    file_name = "pulsed_measurement"
                    if hasattr(self, '_last_pulsed_file_name'):
                        file_name = self._last_pulsed_file_name
                    
                    # Build metadata
                    metadata = {}
                    if hasattr(self, 'optical') and self.optical is not None:
                        try:
                            caps = getattr(self.optical, 'capabilities', {})
                            if caps.get('type'):
                                metadata['led_type'] = str(caps.get('type', ''))
                        except Exception:
                            pass
                    
                    # Get timestamps if available
                    t_arr = None
                    if hasattr(self, 't_arr_disp') and self.t_arr_disp:
                        t_arr = list(self.t_arr_disp)
                    
                    # Call analysis helper
                    self._run_analysis_if_enabled(
                        voltage=v_arr,
                        current=c_arr,
                        timestamps=t_arr,
                        save_dir=save_dir,
                        file_name=file_name,
                        metadata=metadata
                    )
        except Exception as exc:
            # Don't interrupt measurement flow if analysis fails
            print(f"[ANALYSIS] Failed to run analysis in pulsed measurement: {exc}")
        
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

