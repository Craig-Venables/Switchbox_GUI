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

from Measurements.single_measurement_runner import find_largest_number_in_folder


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

            # Note: graphs_show is only for custom measurements - normal sweeps don't add to "all sweeps" graph
            # try:
            #     self.graphs_show(v_arr, c_arr, "ISPP", stop_v)
            # except Exception:
            #     pass

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
        # Initialize endurance data tracking
        if hasattr(self, 'plot_panels'):
            self.plot_panels.endurance_ratios = []
            self.plot_panels.endurance_on_times = []
            self.plot_panels.endurance_on_currents = []
            self.plot_panels.endurance_off_times = []
            self.plot_panels.endurance_off_currents = []
        cycle_reads = []  # Track current measurements for ON/OFF ratio calculation
        endurance_start_time = None  # Track start time for relative timestamps
        
        # Start endurance plot updater thread
        if hasattr(self, 'plot_updaters'):
            self.plot_updaters.start_endurance_thread(True)
        
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
            
            # Get read pulse width and inter cycle delay from GUI
            read_pulse_ms = getattr(self, 'end_read_pulse_ms', None)
            if read_pulse_ms is not None and hasattr(read_pulse_ms, 'get'):
                read_pulse_width_s = max(0.1, read_pulse_ms.get() / 1000.0)
            else:
                read_pulse_width_s = 0.1  # Default 100ms fallback
            
            inter_cycle_delay_s_var = getattr(self, 'end_inter_cycle_delay_s', None)
            if inter_cycle_delay_s_var is not None and hasattr(inter_cycle_delay_s_var, 'get'):
                inter_cycle_delay_s = max(0.0, inter_cycle_delay_s_var.get())
            else:
                inter_cycle_delay_s = 0.0  # Default fallback
            
            print(f"Endurance (special_runner): inter_cycle_delay_s={inter_cycle_delay_s}, read_pulse_width_s={read_pulse_width_s}")

            def _on_point(v: float, i_val: float, t_s: float) -> None:
                nonlocal endurance_start_time
                self.v_arr_disp.append(v)
                self.c_arr_disp.append(i_val)
                self.t_arr_disp.append(t_s)
                
                # Initialize start time for relative timestamps
                if endurance_start_time is None:
                    endurance_start_time = t_s
                
                # Process endurance data: track reads and calculate ON/OFF ratios
                # Endurance pattern: SET_pulse -> SET_read -> RESET_pulse -> RESET_read
                # We track read measurements (at read_voltage) to calculate ratios
                if abs(v - read_v) < 0.01:  # This is a read measurement
                    current_abs = abs(i_val) if i_val != 0 else 1e-12
                    cycle_reads.append(current_abs)
                    relative_time = t_s - endurance_start_time
                    
                    # Track ON and OFF currents separately with timestamps
                    if hasattr(self, 'plot_panels'):
                        # Even indices (0, 2, 4, ...) are SET reads (ON current)
                        # Odd indices (1, 3, 5, ...) are RESET reads (OFF current)
                        if len(cycle_reads) % 2 == 1:  # Odd number means this is a SET read (ON)
                            self.plot_panels.endurance_on_times.append(relative_time)
                            self.plot_panels.endurance_on_currents.append(current_abs)
                        else:  # Even number means this is a RESET read (OFF)
                            self.plot_panels.endurance_off_times.append(relative_time)
                            self.plot_panels.endurance_off_currents.append(current_abs)
                    
                    # When we have a pair (SET_read and RESET_read), calculate ratio
                    # Pattern: every two consecutive reads form a cycle
                    if len(cycle_reads) >= 2 and len(cycle_reads) % 2 == 0:
                        i_on = cycle_reads[-2]  # SET_read (second to last)
                        i_off = cycle_reads[-1]  # RESET_read (last)
                        if i_off > 0:
                            ratio = i_on / i_off
                            if hasattr(self, 'plot_panels'):
                                self.plot_panels.endurance_ratios.append(ratio)

            v_arr, c_arr, t_arr = self.measurement_service.run_endurance(
                keithley=self.keithley,
                set_voltage=set_v,
                reset_voltage=reset_v,
                pulse_width_s=pulse_ms / 1000.0,
                num_cycles=cycles,
                read_voltage=read_v,
                read_pulse_width_s=read_pulse_width_s,
                inter_cycle_delay_s=inter_cycle_delay_s,
                icc=icc_val,
                psu=getattr(self, "psu", None),
                led=False,
                power=1.0,
                optical=getattr(self, "optical", None),
                smu_type=getattr(self, "SMU_type", "Keithley 2401"),
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=_on_point,
            )
            
            # Post-process endurance data to extract ON/OFF ratios and currents if not done in on_point
            # Endurance data typically has pattern: SET_pulse, SET_read, RESET_pulse, RESET_read (repeat)
            # Extract read measurements (at read_voltage) and pair them
            if hasattr(self, 'plot_panels'):
                # If ratios weren't calculated in on_point, calculate them now
                if len(self.plot_panels.endurance_ratios) == 0:
                    read_indices = [i for i, v in enumerate(v_arr) if abs(v - read_v) < 0.01]
                    if len(read_indices) >= 2:
                        start_time = t_arr[0] if t_arr else 0
                        # Pair consecutive reads: even indices are SET reads, odd are RESET reads
                        for idx in range(0, len(read_indices) - 1, 2):
                            if idx + 1 < len(read_indices):
                                i_on = abs(c_arr[read_indices[idx]])  # SET read
                                i_off = abs(c_arr[read_indices[idx + 1]])  # RESET read
                                if i_off > 0:
                                    ratio = i_on / i_off
                                    self.plot_panels.endurance_ratios.append(ratio)
                                    
                                    # Also track ON and OFF currents with timestamps
                                    if len(self.plot_panels.endurance_on_times) == 0:
                                        on_time = t_arr[read_indices[idx]] - start_time
                                        off_time = t_arr[read_indices[idx + 1]] - start_time
                                        self.plot_panels.endurance_on_times.append(on_time)
                                        self.plot_panels.endurance_on_currents.append(i_on)
                                        self.plot_panels.endurance_off_times.append(off_time)
                                        self.plot_panels.endurance_off_currents.append(i_off)
                
                # Final update of endurance plots
                if hasattr(self.plot_panels, 'update_endurance_plot'):
                    self.plot_panels.update_endurance_plot(self.plot_panels.endurance_ratios)
                if hasattr(self.plot_panels, 'update_endurance_current_plot'):
                    self.plot_panels.update_endurance_current_plot(
                        self.plot_panels.endurance_on_times,
                        self.plot_panels.endurance_on_currents,
                        self.plot_panels.endurance_off_times,
                        self.plot_panels.endurance_off_currents
                    )

            # Note: graphs_show is only for custom measurements - normal sweeps don't add to "all sweeps" graph
            # try:
            #     self.graphs_show(v_arr, c_arr, "ENDURANCE", set_v)
            # except Exception:
            #     pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-ENDURANCE-{set_v}v-{reset_v}v-{pulse_ms}ms-Py"
            file_path = Path(save_dir) / f"{name}.txt"
            try:
                # Process endurance data: extract SET and RESET currents per cycle
                # Pattern: SET_pulse -> SET_read -> RESET_pulse -> RESET_read (repeat)
                # Find all read measurements (at read_voltage)
                read_indices = [i for i, v in enumerate(v_arr) if abs(v - read_v) < 0.01]
                
                if len(read_indices) >= 2:
                    # Extract cycle data: pair consecutive reads (SET then RESET)
                    cycles = []
                    times = []
                    i_set_arr = []
                    i_reset_arr = []
                    ratios = []
                    
                    start_time = t_arr[0] if t_arr else 0
                    
                    # Pair reads: even indices are SET reads, odd are RESET reads
                    for cycle_idx in range(0, len(read_indices) - 1, 2):
                        if cycle_idx + 1 < len(read_indices):
                            set_idx = read_indices[cycle_idx]
                            reset_idx = read_indices[cycle_idx + 1]
                            
                            cycle_num = (cycle_idx // 2) + 1
                            time_val = t_arr[reset_idx] - start_time  # Time at end of cycle
                            i_set = abs(c_arr[set_idx]) if c_arr[set_idx] != 0 else 1e-12
                            i_reset = abs(c_arr[reset_idx]) if c_arr[reset_idx] != 0 else 1e-12
                            ratio = i_set / i_reset if i_reset > 0 else float('nan')
                            
                            cycles.append(cycle_num)
                            times.append(time_val)
                            i_set_arr.append(i_set)
                            i_reset_arr.append(i_reset)
                            ratios.append(ratio)
                    
                    # Save structured data
                    data = np.column_stack((cycles, times, i_set_arr, i_reset_arr, ratios))
                    np.savetxt(
                        file_path,
                        data,
                        fmt="%d\t%0.3E\t%0.3E\t%0.3E\t%0.3E",
                        header="Cycle\tTime(s)\tI_SET(A)\tI_RESET(A)\tRatio",
                        comments="",
                    )
                else:
                    # Fallback: save raw data if we can't extract cycles
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
        # Initialize retention data tracking
        if hasattr(self, 'plot_panels'):
            self.plot_panels.retention_times = []
            self.plot_panels.retention_currents = []
        
        # Start retention plot updater thread
        if hasattr(self, 'plot_updaters'):
            self.plot_updaters.start_retention_thread(True)
        
        for i in range(device_count):
            device = self.device_list[(start_index + i) % device_count]
            if self.stop_measurement_flag:
                break
            self.set_status_message(f"Measuring {device} (Retention)...")
            self.master.update()

            set_v = float(self.ret_set_v.get())
            set_ms = float(self.ret_set_ms.get())
            read_v = float(self.ret_read_v.get())
            
            # Get number of reads from GUI
            try:
                ret_num = getattr(self, 'ret_number_reads', None)
                if ret_num is not None and hasattr(ret_num, 'get'):
                    number_reads = int(ret_num.get())
                else:
                    number_reads = 30
            except Exception:
                number_reads = 30
            
            # Get repeat delay from GUI
            try:
                repeat_delay_s = float(self.ret_measure_delay.get())
            except Exception:
                repeat_delay_s = 10.0
            
            # Get read pulse width from GUI
            try:
                ret_read_pulse = getattr(self, 'ret_read_pulse_ms', None)
                if ret_read_pulse is not None and hasattr(ret_read_pulse, 'get'):
                    read_pulse_ms = float(ret_read_pulse.get())
                else:
                    read_pulse_ms = 100.0
            except Exception:
                read_pulse_ms = 100.0
            
            print(f"Retention (special_runner): number_reads={number_reads}, read_pulse_ms={read_pulse_ms}, repeat_delay_s={repeat_delay_s}")
            
            icc_val = float(self.icc.get())

            def _on_point(v: float, i_val: float, t_s: float) -> None:
                self.v_arr_disp.append(v)
                self.c_arr_disp.append(i_val)
                self.t_arr_disp.append(t_s)
                
                # Process retention data: track time vs current for retention plot
                # Retention measurements track current over time after SET pulse
                if hasattr(self, 'plot_panels'):
                    # Use relative time from start of retention measurement
                    if not hasattr(self, 'retention_start_time') or self.retention_start_time is None:
                        self.retention_start_time = t_s
                    relative_time = t_s - self.retention_start_time
                    if relative_time > 0:  # Only add positive times for log scale
                        self.plot_panels.retention_times.append(relative_time)
                        self.plot_panels.retention_currents.append(abs(i_val) if i_val != 0 else 1e-12)

            # Track start time for retention measurement
            if hasattr(self, 'plot_panels'):
                self.retention_start_time = None
            
            v_arr, c_arr, t_arr = self.measurement_service.run_retention(
                keithley=self.keithley,
                set_voltage=set_v,
                set_time_s=set_ms / 1000.0,
                read_voltage=read_v,
                read_pulse_width_s=read_pulse_ms / 1000.0,
                repeat_delay_s=repeat_delay_s,
                number=number_reads,
                icc=icc_val,
                psu=getattr(self, "psu", None),
                led=False,
                optical=getattr(self, "optical", None),
                smu_type=getattr(self, "SMU_type", "Keithley 2401"),
                should_stop=lambda: getattr(self, "stop_measurement_flag", False),
                on_point=_on_point,
            )
            
            # Post-process retention data if not fully processed in on_point
            # Retention data: time vs current (log-log plot)
            if hasattr(self, 'plot_panels'):
                if len(self.plot_panels.retention_times) == 0 and len(t_arr) > 0:
                    # Use all time vs current data for retention plot
                    start_time = t_arr[0] if t_arr else 0
                    for idx in range(len(t_arr)):
                        if idx < len(c_arr):
                            relative_time = t_arr[idx] - start_time
                            if relative_time > 0:  # Only positive times for log scale
                                self.plot_panels.retention_times.append(relative_time)
                                current = abs(c_arr[idx]) if c_arr[idx] != 0 else 1e-12
                                self.plot_panels.retention_currents.append(current)
                
                # Final update of retention plot
                if hasattr(self.plot_panels, 'update_retention_plot'):
                    self.plot_panels.update_retention_plot(
                        self.plot_panels.retention_times,
                        self.plot_panels.retention_currents
                    )

            # Note: graphs_show is only for custom measurements - normal sweeps don't add to "all sweeps" graph
            # try:
            #     self.graphs_show(v_arr, c_arr, "RETENTION", read_v)
            # except Exception:
            #     pass

            save_dir = self._ensure_save_dir()
            key = find_largest_number_in_folder(save_dir)
            save_key = 0 if key is None else key + 1
            name = f"{save_key}-RETENTION-{set_v}v-{read_v}v-Py"
            file_path = Path(save_dir) / f"{name}.txt"
            try:
                # Process retention data: extract initial read and subsequent reads
                # Pattern: Initial_read -> SET_pulse -> Read_1 -> Read_2 -> ... -> Read_N
                # Find all read measurements (at read_voltage)
                read_indices = [i for i, v in enumerate(v_arr) if abs(v - read_v) < 0.01]
                
                if len(read_indices) > 0:
                    # Extract read data
                    read_numbers = []
                    times = []
                    currents = []
                    voltages = []
                    
                    start_time = t_arr[0] if t_arr else 0
                    
                    # Find SET pulse index (voltage = set_v)
                    set_pulse_idx = None
                    for i, v in enumerate(v_arr):
                        if abs(v - set_v) < 0.01:
                            set_pulse_idx = i
                            break
                    
                    # Separate initial read (before SET) from subsequent reads (after SET)
                    for read_idx in read_indices:
                        if set_pulse_idx is not None and read_idx < set_pulse_idx:
                            # This is the initial read (before SET pulse)
                            read_num = 0
                        elif set_pulse_idx is not None:
                            # This is a subsequent read (after SET pulse)
                            # Count how many reads have occurred after SET pulse up to this point
                            reads_after_set = [idx for idx in read_indices if idx > set_pulse_idx and idx <= read_idx]
                            read_num = len(reads_after_set)
                        else:
                            # No SET pulse found, number sequentially starting from 0
                            reads_before_this = [idx for idx in read_indices if idx < read_idx]
                            read_num = len(reads_before_this)
                        
                        time_val = t_arr[read_idx] - start_time
                        current_val = c_arr[read_idx]
                        voltage_val = v_arr[read_idx]
                        
                        read_numbers.append(read_num)
                        times.append(time_val)
                        currents.append(current_val)
                        voltages.append(voltage_val)
                    
                    # Save structured data
                    data = np.column_stack((read_numbers, times, currents, voltages))
                    np.savetxt(
                        file_path,
                        data,
                        fmt="%d\t%0.3E\t%0.3E\t%0.3E",
                        header="Read_Number\tTime(s)\tCurrent(A)\tVoltage(V)",
                        comments="",
                    )
                else:
                    # Fallback: save raw data if we can't extract reads
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

            # Note: graphs_show is only for custom measurements - normal sweeps don't add to "all sweeps" graph
            # try:
            #     self.graphs_show(w_arr, i_arr, "PWidth", amp)
            # except Exception:
            #     pass

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

            # Note: graphs_show is only for custom measurements - normal sweeps don't add to "all sweeps" graph
            # try:
            #     self.graphs_show(v_arr, c_arr, "THRESH", v_hi)
            # except Exception:
            #     pass

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


