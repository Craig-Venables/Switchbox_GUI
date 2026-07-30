"""Custom measurement plan runner (extracted from MeasurementGUI)."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from typing import Any

import numpy as np
from tkinter import messagebox

from Measurements.measurement_services_smu import VoltageRangeMode


def __debug_print(*args: Any, **kwargs: Any) -> None:
    """No-op debug logger (matches MeasurementGUI debug_print when disabled)."""
    return None


def run_custom_measurement(gui: Any) -> None:
        """Execute a custom measurement plan from the loaded JSON file.

        The JSON (loaded into `gui.custom_sweeps`) contains an ordered set of
        named sweeps. For each sweep the method configures instrument options
        (LED, PSU, pulse parameters, etc.) and delegates the actual work to
        `MeasurementService`. Per-sweep overrides made at runtime via the
        sweep editor popup are applied on-the-fly.

        The GUI's `stop_measurement_flag` is checked frequently to allow
        cooperative abort. Results are saved per-sweep in the default `Data_folder`
        basic summary plots are produced.
        """


        if not gui.connected:
            messagebox.showwarning("Warning", "Not connected to Keithley!")
            return

        # Reset graphs/buffers between runs
        gui._reset_plots_for_new_run(gui)

        if gui.single_device_flag:
            response = messagebox.askquestion(
                "Did you choose the correct device?",
                "Please make sure the correct device is selected.\nClick 'Yes' if you are sure.\nIf not you will be "
                "saving over old data")
            if response != 'yes':
                return
        gui.measuring = True
        gui._set_measurement_feedback(True, "Acquiring data from instrument")

        gui.stop_measurement_flag = False

        # make sure it is on the top
        gui.bring_to_top()

        # checks for sample name if not prompts user
        # Skip sample name check if custom save location is enabled (custom path takes priority)
        if not (gui.use_custom_save_var.get() and gui.custom_save_location):
            gui.check_for_sample_name()

        selected_measurement = gui.custom_measurement_var.get()
        # Reset any prior sweep edits from the popup for a fresh run
        try:
            gui.sweep_runtime_overrides = {}
        except Exception:
            pass
        print(f"Running custom measurement: {selected_measurement}")

        if gui.telegram.is_enabled():
            var = gui.custom_measurement_var.get()
            sample_name = gui.sample_name_var.get()
            section = gui.device_section_and_number
            text = f"Starting Measurements on {sample_name} device {section} ({var})"
            gui.telegram.send_message(text)

        if selected_measurement in gui.custom_sweeps:
            if gui.current_device in gui.device_list:
                start_index = gui.device_list.index(gui.current_device)
            else:
                start_index = 0  # Default to the first device if current one is not found

            device_count = len(gui.device_list)

            # looping through each device.
            for i in range(device_count):  # Ensure we process each device exactly once
                device = gui.device_list[(start_index + i) % device_count]  # Wrap around when reaching the end

                gui.master.update()
                time.sleep(1)

                # Ensure Kiethley set correctly
                gui.keithley.set_voltage(0, gui.icc.get())  # Start at 0V
                gui.keithley.enable_output(True)  # Enable output

                start = time.time()
                start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                sweeps = gui.custom_sweeps[selected_measurement]["sweeps"]
                # Store total count before loop (sweeps dict may be shadowed inside loop)
                total_sweeps_count = len(sweeps)
                # Initial merge disabled; we now apply live edits per-sweep inside the loop
                code_name = gui.custom_sweeps[selected_measurement].get("code_name", "unknown")
            
                # === CUSTOM MEASUREMENT ANALYSIS TRACKING ===
                # Track device memristive status across sweeps
                device_is_memristive = None  # Unknown until first sweep analyzed
                sequence_analysis_results = []  # Collect all analysis results
                sweep_classifications = {}  # Track score per sweep

                # checks psu connection only if any sweep explicitly requires LED
                def _is_truthy(val) -> bool:
                    try:
                        # numeric truthiness: non-zero => True
                        if isinstance(val, (int, float)):
                            return float(val) != 0.0
                    except Exception:
                        pass
                    if isinstance(val, str):
                        return val.strip().lower() in {"1", "true", "on", "yes", "y"}
                    return bool(val)

                any_led_required = any(_is_truthy(params.get("LED_ON", 0)) for _k, params in sweeps.items())
                if any_led_required and not gui.psu_connected:
                    print("LED required by at least one sweep; connecting PSU")
                    messagebox.showwarning("Warning", "Not connected to PSU! Connecting now for LED use...")
                    time.sleep(1)
                    gui.connect_keithley_psu()

                # Initialize save_key once before the loop to ensure sequential numbering
                # This ensures each sweep gets a unique number and graphs are saved properly
                save_dir = gui._get_save_directory(gui.sample_name_var.get(), 
                                                   gui.final_device_letter, 
                                                   gui.final_device_number)
                # make directory if doesn't exist
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
            
                # Find the largest existing file number to continue from the most recent
                from Measurements.single_measurement_runner import find_largest_number_in_folder
                key_num = find_largest_number_in_folder(save_dir)
                save_key = 0 if key_num is None else key_num + 1
            
                # Track if this is the first sweep in the sequence
                first_sweep_in_sequence = True

                for key, params in sweeps.items():
                    # Apply live edits for this sweep (skip/stop_v) so mid-run changes take effect
                    try:
                        live_edits = getattr(gui, 'sweep_runtime_overrides', {}) or {}
                        per = live_edits.get(str(key), {})
                        if per.get('skip'):
                            continue
                        if 'stop_v' in per:
                            try:
                                params['stop_v'] = float(per['stop_v'])
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if gui.stop_measurement_flag:  # Check if stop was pressed
                        print("Measurement interrupted!")
                        break  # Exit measurement loop immediately

                    gui.measurment_number = key
                    print("Working on device -", device, ": Measurement -", key)

                    # Runtime: pause between sweeps if requested
                    while getattr(gui, 'pause_requested', False) and not gui.stop_measurement_flag:
                        time.sleep(0.1)

                    # Runtime: skip forward to a specific sweep number, if set
                    skip_to = getattr(gui, 'skip_to_sweep_target', None)
                    if skip_to is not None:
                        try:
                            current_idx = int(str(key))
                            if current_idx < int(skip_to):
                                continue
                            else:
                                # Clear the target once reached
                                gui.skip_to_sweep_target = None
                        except Exception:
                            pass

                    # default values
                    start_v = params.get("start_v", 0)
                    stop_v = params.get("stop_v", 1)
                    # Runtime: override stop_v for a configured sweep range
                    override = getattr(gui, 'override_range', None)
                    if override is not None:
                        try:
                            cur_idx = int(str(key))
                            if override["start"] <= cur_idx <= override["end"]:
                                stop_v = float(override["stop_v"])
                        except Exception:
                            pass
                    num_sweeps_in_measurement = params.get("sweeps", 1)  # Renamed to avoid shadowing outer 'sweeps' dict
                    step_v = params.get("step_v", 0.1)
                    step_delay = params.get("step_delay", 0.05)
                    sweep_type = params.get("Sweep_type", "FS")
                    pause = params.get('pause', 0)

                    # LED control
                    led = _is_truthy(params.get("LED_ON", 0))
                    power = params.get("power", 1)  # Power Refers to voltage
                    sequence = params.get("sequence", 0)


                    # retention
                    set_voltage = params.get("set_voltage", 10)
                    reset_voltage = params.get("reset_voltage", 10)
                    repeat_delay = params.get("repeat_delay", 500) #ms
                    number = params.get("number", 100)
                    set_time = params.get("set_time",100)
                    read_voltage = params.get("read_voltage",0.15)
                    #led = params.get("LED_ON", 0)
                    # sequence
                    led_time = params.get("led_time", "100") # in seconds


                    if sequence == 0:
                        sequence = None

                    if led:
                        if not gui.psu_connected:
                            messagebox.showwarning("Warning", "Not connected to PSU!")
                            gui.connect_keithley_psu()
                        gui.psu_needed = True
                    else:
                        gui.psu_needed = False

                    # add checker step where it checks if the devices current state and if ts ohmic or capacaive it stops

                    # Read measurement_type (new unified field)
                    measurement_type = str(params.get("measurement_type", "IV"))
                
                    # Backward compatibility: check old "mode" and "excitation" fields
                    if "mode" in params:
                        measurement_type = params["mode"]  # Endurance, Retention
                    elif "excitation" in params:
                        # Map old excitation names to measurement_type
                        excitation_map = {
                            "DC Triangle IV": "IV",
                            "SMU Pulsed IV": "PulsedIV",
                            "SMU Fast Pulses": "FastPulses",
                            "SMU Fast Hold": "Hold"
                        }
                        measurement_type = excitation_map.get(params["excitation"], "IV")
                
                    # Read source mode (NEW)
                    source_mode_str = params.get("source_mode", "voltage")
                    from Measurements.source_modes import SourceMode
                    source_mode = SourceMode.CURRENT if source_mode_str == "current" else SourceMode.VOLTAGE
                
                    # Read compliance per sweep (NEW - optional, defaults to GUI value)
                    icc_val = params.get("icc", None)
                    if icc_val is None:
                        icc_val = float(gui.icc.get())  # Use GUI value
                    else:
                        icc_val = float(icc_val)  # Use JSON value
                    gui._apply_smu_current_range()
                
                    # Read metadata/notes (NEW - optional)
                    sweep_notes = params.get("notes", None)
                    if sweep_notes:
                        print(f"Sweep {key} notes: {sweep_notes}")
                
                    # Read temperature (NEW - OPTIONAL, defaults to OFF)
                    # Temperature control is ONLY activated if temperature_C is explicitly set in JSON
                    if "temperature_C" in params:
                        target_temp = params["temperature_C"]
                        if hasattr(gui, 'temp_controller') and gui.temp_controller is not None:
                            try:
                                print(f"Setting temperature to {target_temp}°C")
                                gui.temp_controller.set_temperature(float(target_temp))
                            
                                # Optional: wait for stabilization (only if specified)
                                stabilization_time = params.get("temp_stabilization_s", 0)
                                if stabilization_time > 0:
                                    print(f"Waiting {stabilization_time}s for temperature stabilization...")
                                    time.sleep(float(stabilization_time))
                            except Exception as e:
                                print(f"Temperature setting failed: {e}")
                                # Continue with measurement even if temp control fails
                        else:
                            print("Warning: temperature_C specified but no temp controller connected")
                    # If "temperature_C" not in params, temperature control is completely skipped

                    # Helpers for SMU_AND_PMU timing defaults
                    def _min_pw_ms() -> float:
                        try:
                            smu_type_loc = getattr(gui, 'SMU_type', 'Keithley 2401')
                            return float(gui.measurement_service.get_smu_limits(smu_type_loc).get("min_pulse_width_ms", 1.0))
                        except Exception:
                            return 1.0

                    # Route to appropriate measurement based on measurement_type
                    if measurement_type == "IV":
                        # Check if this is a cyclical sweep (4200A only)
                        if sweep_type == "CYCLICAL":
                            if KXCIClient is None or build_ex_command is None:
                                print("ERROR: Cyclical sweep requires KXCI client, but module is not available")
                                messagebox.showerror("Module Not Available", 
                                                    "Cyclical sweep requires the KXCI module.\n"
                                                    "Please ensure the 4200A C module is properly installed.")
                                continue
                        
                            smu_type = getattr(gui, 'SMU_type', 'Keithley 2401')
                            if smu_type != 'Keithley 4200A':
                                print(f"ERROR: Cyclical sweep (CYCLICAL) is only available for Keithley 4200A, not {smu_type}")
                                messagebox.showerror("Invalid SMU Type", 
                                                    f"Cyclical sweep is only available for Keithley 4200A.\n"
                                                    f"Current SMU: {smu_type}\n"
                                                    f"Please change SMU type or select a different sweep type.")
                                continue
                        
                            # Get cyclical parameters from GUI variables or params
                            if hasattr(gui, 'cyclical_vpos'):
                                vpos = gui.cyclical_vpos.get()
                                vneg = gui.cyclical_vneg.get()
                                num_cycles = gui.cyclical_num_cycles.get()
                                settle_time = gui.cyclical_settle_time.get()
                                ilimit = gui.cyclical_ilimit.get()
                                integration_time = gui.cyclical_integration_time.get()
                                debug = 1 if gui.cyclical_debug.get() else 0
                            else:
                                # Fallback to params if GUI vars don't exist
                                vpos = float(params.get("vpos", stop_v if stop_v > 0 else 2.0))
                                vneg = float(params.get("vneg", 0.0))
                                num_cycles = int(params.get("num_cycles", 1))
                                settle_time = float(params.get("settle_time", step_delay if step_delay > 0 else 0.001))
                                ilimit = float(params.get("ilimit", icc_val if icc_val > 0 else 0.1))
                                integration_time = float(params.get("integration_time", 0.01))
                                debug = 1 if _is_truthy(params.get("debug", True)) else 0
                        
                            # Flag to track if graphs have been cleared for this measurement
                            _graphs_cleared_for_this_measurement = False
                        
                            def _on_point(v, i, t_s):
                                nonlocal _graphs_cleared_for_this_measurement
                                # Clear graphs on first data point (right before plotting new data)
                                if not _graphs_cleared_for_this_measurement:
                                    _graphs_cleared_for_this_measurement = True
                                    if hasattr(gui, 'master') and hasattr(gui, '_reset_plots_for_new_sweep'):
                                        # Ensure reset completes before first point append to avoid
                                        # async reset wiping newly appended data.
                                        try:
                                            _reset_done = threading.Event()
                                            def _do_reset():
                                                try:
                                                    gui._reset_plots_for_new_sweep(gui)
                                                finally:
                                                    _reset_done.set()
                                            gui.master.after(0, _do_reset)
                                            _reset_done.wait(timeout=1.0)
                                        except Exception:
                                            gui.master.after(0, lambda: gui._reset_plots_for_new_sweep(gui))
                            
                                gui.v_arr_disp.append(v)
                                gui.c_arr_disp.append(i)
                                gui.t_arr_disp.append(t_s)
                        
                            # Execute cyclical sweep via 4200A system wrapper (manager pattern)
                            v_arr, c_arr, timestamps = gui._run_cyclical_iv_sweep_via_manager(
                                vpos=vpos,
                                vneg=vneg,
                                num_cycles=num_cycles,
                                settle_time=settle_time,
                                ilimit=ilimit,
                                integration_time=integration_time,
                                debug=debug,
                                on_point=_on_point
                            )
                        else:
                            # Standard triangle IV sweep (FS/PS/NS)
                            # Optional per-sweep negative stop voltage: params override UI field
                            neg_stop_v_param = None
                            try:
                                if 'neg_stop_v' in params:
                                    neg_stop_v_param = float(params.get('neg_stop_v'))
                                elif 'Vneg' in params:
                                    neg_stop_v_param = float(params.get('Vneg'))
                                else:
                                    raw_neg = gui.voltage_low_str.get().strip() if hasattr(gui, 'voltage_low_str') else ""
                                    if raw_neg != "":
                                        neg_stop_v_param = float(raw_neg)
                            except Exception:
                                neg_stop_v_param = None
                            voltage_range = gui.measurement_service.compute_voltage_range(
                                start_v=start_v,
                                stop_v=stop_v,
                                step_v=step_v,
                                sweep_type=sweep_type,
                                mode=VoltageRangeMode.FIXED_STEP,
                                neg_stop_v=neg_stop_v_param,
                            )
                        
                            # Flag to track if graphs have been cleared for this measurement
                            _graphs_cleared_for_this_measurement = False
                        
                            def _on_point(v, i, t_s):
                                nonlocal _graphs_cleared_for_this_measurement
                                # Clear graphs on first data point (right before plotting new data)
                                if not _graphs_cleared_for_this_measurement:
                                    _graphs_cleared_for_this_measurement = True
                                    if hasattr(gui, 'master') and hasattr(gui, '_reset_plots_for_new_sweep'):
                                        # Ensure reset completes before first point append to avoid
                                        # async reset wiping newly appended data.
                                        try:
                                            _reset_done = threading.Event()
                                            def _do_reset():
                                                try:
                                                    gui._reset_plots_for_new_sweep(gui)
                                                finally:
                                                    _reset_done.set()
                                            gui.master.after(0, _do_reset)
                                            _reset_done.wait(timeout=1.0)
                                        except Exception:
                                            gui.master.after(0, lambda: gui._reset_plots_for_new_sweep(gui))
                            
                                gui.v_arr_disp.append(v)
                                gui.c_arr_disp.append(i)
                                gui.t_arr_disp.append(t_s)
                        
                            v_arr, c_arr, timestamps = gui.measurement_service.run_iv_sweep(
                                keithley=gui.keithley,
                                start_v=start_v,
                                stop_v=stop_v,
                                step_v=step_v,
                                sweeps=num_sweeps_in_measurement,
                                step_delay=step_delay,
                                sweep_type=sweep_type,
                                icc=icc_val,
                                psu=getattr(gui, 'psu', None),
                                led=led,
                                power=power,
                                optical=getattr(gui, 'optical', None),
                                sequence=sequence,
                                pause_s=pause,
                                smu_type=getattr(gui, 'SMU_type', 'Keithley 2401'),
                                source_mode=source_mode,
                                should_stop=lambda: getattr(gui, 'stop_measurement_flag', False),
                                on_point=_on_point
                            )

                    elif measurement_type == "Endurance":
                        # Read from JSON params first, fallback to GUI variables
                        set_v = float(params.get("set_v", gui.end_set_v.get()))
                        reset_v = float(params.get("reset_v", gui.end_reset_v.get()))
                        pulse_ms = float(params.get("pulse_ms", gui.end_pulse_ms.get()))
                        cycles = int(params.get("cycles", gui.end_cycles.get()))
                        read_v = float(params.get("read_v", gui.end_read_v.get()))
                        # Get read pulse width and inter cycle delay - properly read from GUI
                        read_pulse_ms = params.get("read_pulse_ms", None)
                        if read_pulse_ms is None:
                            ret_read_pulse = getattr(gui, 'end_read_pulse_ms', None)
                            if ret_read_pulse is not None and hasattr(ret_read_pulse, 'get'):
                                read_pulse_ms = ret_read_pulse.get()
                            else:
                                read_pulse_ms = 100.0
                        read_pulse_ms = float(read_pulse_ms)
                    
                        inter_cycle_delay_s = params.get("inter_cycle_delay_s", None)
                        print(f"DEBUG: inter_cycle_delay_s from params: {inter_cycle_delay_s}")
                        if inter_cycle_delay_s is None:
                            # Try to get from GUI variable
                            ret_delay = getattr(gui, 'end_inter_cycle_delay_s', None)
                            print(f"DEBUG: ret_delay from GUI: {ret_delay}, type: {type(ret_delay)}")
                            if ret_delay is not None and hasattr(ret_delay, 'get'):
                                try:
                                    inter_cycle_delay_s = ret_delay.get()
                                    print(f"DEBUG: Got value from GUI variable: {inter_cycle_delay_s}")
                                except Exception as e:
                                    print(f"DEBUG: Error reading GUI variable: {e}")
                                    inter_cycle_delay_s = 0.0
                            else:
                                inter_cycle_delay_s = 0.0
                                print(f"DEBUG: GUI variable not found, using default 0.0")
                        else:
                            print(f"DEBUG: Using value from params: {inter_cycle_delay_s}")
                        inter_cycle_delay_s = float(inter_cycle_delay_s)
                    
                        print(f"Endurance params FINAL: inter_cycle_delay_s={inter_cycle_delay_s}, read_pulse_ms={read_pulse_ms}")
                    
                        def _on_point(v, i, t_s):
                            gui.v_arr_disp.append(v)
                            gui.c_arr_disp.append(i)
                            gui.t_arr_disp.append(t_s)
                    
                        v_arr, c_arr, timestamps = gui.measurement_service.run_endurance(
                            keithley=gui.keithley,
                            set_voltage=set_v,
                            reset_voltage=reset_v,
                            pulse_width_s=pulse_ms/1000,
                            num_cycles=cycles,
                            read_voltage=read_v,
                            read_pulse_width_s=read_pulse_ms/1000,
                            inter_cycle_delay_s=inter_cycle_delay_s,
                            icc=icc_val,
                            psu=getattr(gui, 'psu', None),
                            led=led,
                            power=power,
                            optical=getattr(gui, 'optical', None),
                            smu_type=getattr(gui, 'SMU_type', 'Keithley 2401'),
                            should_stop=lambda: getattr(gui, 'stop_measurement_flag', False),
                            on_point=_on_point
                        )
                        print("endurance")

                    elif measurement_type == "Retention":
                        # Read from JSON params first, fallback to GUI variables
                        set_v = float(params.get("set_v", gui.ret_set_v.get()))
                        set_ms = float(params.get("set_ms", gui.ret_set_ms.get()))
                        read_v = float(params.get("read_v", gui.ret_read_v.get()))
                    
                        def _on_point(v, i, t_s):
                            gui.v_arr_disp.append(v)
                            gui.c_arr_disp.append(i)
                            gui.t_arr_disp.append(t_s)
                    
                        # Get read pulse width and number of reads - prioritize new parameters
                        read_pulse_ms = float(params.get("read_pulse_ms", 
                            getattr(gui, 'ret_read_pulse_ms', None)))
                        if read_pulse_ms is None or (hasattr(read_pulse_ms, 'get') and read_pulse_ms.get() is None):
                            read_pulse_ms = 100.0
                        elif hasattr(read_pulse_ms, 'get'):
                            read_pulse_ms = read_pulse_ms.get()
                    
                        number_reads = params.get("number_reads", None)
                        if number_reads is None:
                            ret_num = getattr(gui, 'ret_number_reads', None)
                            if ret_num is not None and hasattr(ret_num, 'get'):
                                number_reads = ret_num.get()
                            else:
                                number_reads = 30
                        number_reads = int(number_reads)
                    
                        repeat_delay = params.get("repeat_delay_s", None)
                        if repeat_delay is None:
                            ret_delay = getattr(gui, 'ret_measure_delay', None)
                            if ret_delay is not None and hasattr(ret_delay, 'get'):
                                repeat_delay = ret_delay.get()
                            else:
                                repeat_delay = 10.0
                        repeat_delay = float(repeat_delay)
                    
                        print(f"Retention params: number_reads={number_reads}, read_pulse_ms={read_pulse_ms}, repeat_delay={repeat_delay}")
                    
                        v_arr, c_arr, timestamps = gui.measurement_service.run_retention(
                            keithley=gui.keithley,
                            set_voltage=set_v,
                            set_time_s=set_ms/1000,
                            read_voltage=read_v,
                            read_pulse_width_s=read_pulse_ms/1000,
                            repeat_delay_s=repeat_delay,
                            number=number_reads,
                            icc=icc_val,
                            psu=getattr(gui, 'psu', None),
                            led=led,
                            optical=getattr(gui, 'optical', None),
                            smu_type=getattr(gui, 'SMU_type', 'Keithley 2401'),
                            should_stop=lambda: getattr(gui, 'stop_measurement_flag', False),
                            on_point=_on_point
                        )
                        print("retention")

                    elif measurement_type == "PulsedIV":
                        # Parameters
                        start_amp = float(params.get("start_v", 0.0))
                        stop_amp = float(params.get("stop_v", 0.2))
                        step_amp = float(params.get("step_v", 0.0)) if params.get("step_v") is not None else None
                        num_steps = int(params.get("num_steps", 0)) or None
                        pulse_ms = float(params.get("pulse_ms", _min_pw_ms()))
                        vbase = float(params.get("vbase", 0.2))
                        inter_step = float(params.get("inter_delay", 0.0))

                        v_arr, c_arr, timestamps, _ = gui.measurement_service.run_pulsed_iv_sweep(
                            keithley=gui.keithley,
                            start_v=start_amp,
                            stop_v=stop_amp,
                            step_v=step_amp,
                            num_steps=num_steps,
                            pulse_width_ms=max(_min_pw_ms(), pulse_ms),
                            vbase=vbase,
                            inter_step_delay_s=inter_step,
                            icc=icc_val,
                            smu_type=getattr(gui, 'SMU_type', 'Keithley 2401'),
                            should_stop=lambda: getattr(gui, 'stop_measurement_flag', False),
                            on_point=None,
                            validate_timing=True,
                        )
                    
                    elif measurement_type == "FastPulses":
                        pulse_v = float(params.get("pulse_v", 0.2))
                        pulse_ms = float(params.get("pulse_ms", _min_pw_ms()))
                        num_pulses = int(params.get("num", 10))
                        inter_delay = float(params.get("inter_delay", 0.0))
                        vbase = float(params.get("vbase", 0.2))
                    
                        v_arr, c_arr, timestamps = gui.measurement_service.run_pulse_measurement(
                            keithley=gui.keithley,
                            pulse_voltage=pulse_v,
                            pulse_width_ms=max(_min_pw_ms(), pulse_ms),
                            num_pulses=max(1, num_pulses),
                            read_voltage=vbase,
                            inter_pulse_delay_s=max(0.0, inter_delay),
                            icc=icc_val,
                            smu_type=getattr(gui, 'SMU_type', 'Keithley 2401'),
                            psu=getattr(gui, 'psu', None),
                            led=False,
                            power=1.0,
                            optical=getattr(gui, 'optical', None),
                            sequence=None,
                            should_stop=lambda: getattr(gui, 'stop_measurement_flag', False),
                            on_point=None,
                            validate_timing=True,
                        )
                    
                    elif measurement_type == "Hold":
                        hold_v = float(params.get("hold_v", 0.2))
                        duration = float(params.get("duration_s", 5.0))
                        sample_dt = float(params.get("sample_dt_s", 0.01))
                    
                        v_arr, c_arr, timestamps = gui.measurement_service.run_dc_capture(
                            keithley=gui.keithley,
                            voltage_v=hold_v,
                            capture_time_s=duration,
                            sample_dt_s=sample_dt,
                            icc=icc_val,
                            on_point=None,
                            should_stop=lambda: getattr(gui, 'stop_measurement_flag', False),
                        )
                    
                    else:
                        print(f"Unknown measurement_type: {measurement_type}")
                        continue

                    # this isnt being used yet i dont think
                    if device not in gui.measurement_data:
                        gui.measurement_data[device] = {}

                    gui.measurement_data[device][key] = (v_arr, c_arr, timestamps)

                    # todo wrap this into a function for use on other method!!!

                    #gui.keithley.beep(600, 1)

                    # data arry to save
                    data = np.column_stack((v_arr, c_arr, timestamps))

                    # save_dir and save_key are now initialized before the loop
                    # Increment save_key for this sweep to ensure unique filenames
                    current_save_key = save_key
                    save_key += 1  # Increment for next sweep

                    if gui.additional_info_var != "":
                        #extra_info = "-" + str(gui.additional_info_entry.get())
                        # or
                        extra_info = "-" + gui.additional_info_entry.get().strip()
                    else:
                        extra_info = ""

                    name = f"{current_save_key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-Py-{code_name}{extra_info}"
                    file_path = f"{save_dir}\\{name}.txt"

                    try:
                        np.savetxt(file_path, data, fmt="%0.3E\t%0.3E\t%0.3E", header="Voltage Current Time", comments="")
                        abs_path = os.path.abspath(file_path)
                        print(f"[SAVE] File saved to: {abs_path}")
                        gui.log_terminal(f"File saved: {abs_path}")
                    except Exception as e:
                        print(f"[SAVE ERROR] Failed to save file: {e}")

                    # show graphs on main display (must run on main thread for reliable redraw)
                    v_list = list(v_arr)
                    c_list = list(c_arr)
                    gui.master.after(0, lambda: gui.graphs_show(v_list, c_list, key, stop_v))
                
                    # === PER-SWEEP ANALYSIS FOR CUSTOM SEQUENCES ===
                    try:
                        # Build metadata for this sweep
                        sweep_metadata = {}
                        if hasattr(gui, 'optical') and gui.optical is not None:
                            try:
                                caps = getattr(gui.optical, 'capabilities', {})
                                if caps.get('type'):
                                    sweep_metadata['led_type'] = str(caps.get('type', ''))
                            except Exception:
                                pass
                    
                        # Use sweep-specific filename (should match the actual saved file: current_save_key-based)
                        sweep_file_name = name  # Use the actual filename that was saved
                    
                        # Run analysis with conditional logic
                        analysis_result = gui._run_analysis_if_enabled(
                            voltage=list(v_arr),
                            current=list(c_arr),
                            timestamps=list(timestamps) if timestamps is not None else None,
                            save_dir=save_dir,
                            file_name=sweep_file_name,
                            metadata=sweep_metadata,
                            is_custom_sequence=True,
                            sweep_number=int(str(current_save_key)),  # Use current_save_key for consistency
                            device_memristive_flag=device_is_memristive
                        )
                    
                        # Update memristive flag after first sweep
                        # Since analysis now runs in background, check for pending results
                        if first_sweep_in_sequence:  # First sweep in the sequence
                            # Wait a bit for analysis to complete (with timeout)
                            max_wait = 10.0  # 10 seconds max
                            wait_start = time.time()
                            while time.time() - wait_start < max_wait:
                                if hasattr(gui, '_pending_analysis_results'):
                                    result_key = f"{sweep_file_name}_sweep_{current_save_key}"
                                    if result_key in gui._pending_analysis_results:
                                        result = gui._pending_analysis_results[result_key]
                                        device_is_memristive = result.get('is_memristive', False)
                                        analysis_result = result
                                        print(f"[CUSTOM ANALYSIS] First sweep complete: memristive={device_is_memristive}")
                                        break
                                time.sleep(0.1)
                            else:
                                print(f"[CUSTOM ANALYSIS] Timeout waiting for first sweep analysis result")
                                analysis_result = None
                        
                            # Mark that we've processed the first sweep
                            first_sweep_in_sequence = False

                        # === PLOTTING (IV dashboard always; conduction/SCLC only via Extended elsewhere) ===
                        try:
                            is_memristive_for_plot = False
                            if analysis_result and hasattr(analysis_result, 'get'):
                                analysis_data = analysis_result.get('analysis_data') or analysis_result
                                if analysis_data:
                                    classification = analysis_data.get('classification', {})
                                    is_memristive_for_plot = classification.get('memristivity_score', 0) > 60
                            else:
                                is_memristive_for_plot = (
                                    device_is_memristive if device_is_memristive is not None else False
                                )

                            gui._plot_measurement_in_background(
                                voltage=v_arr,
                                current=c_arr,
                                timestamps=timestamps,
                                save_dir=save_dir,
                                device_name=f"{gui.final_device_letter}{gui.final_device_number}",
                                sweep_number=current_save_key,
                                is_memristive=is_memristive_for_plot,
                                filename=name,
                                measurement_type=measurement_type,
                                measurement_params=params,
                                include_conduction=False,
                            )
                            _debug_print(
                                f"[PLOT] Queued plots for sweep {current_save_key}: {name} "
                                f"(memristive={is_memristive_for_plot})"
                            )
                        except Exception as plot_exc:
                            print(f"[PLOT ERROR] Failed to queue background plotting: {plot_exc}")
                    
                        # Collect analysis data (if available)
                        if analysis_result and hasattr(analysis_result, 'get'):
                            try:
                                analysis_data = analysis_result.get('analysis_data') or analysis_result
                                sequence_analysis_results.append({
                                    'sweep_number': current_save_key,  # Use current_save_key for consistency
                                    'voltage': stop_v,
                                    'analysis': analysis_data
                                })
                            
                                # Update live display (separate try-except to not block data collection)
                                try:
                                    classification = analysis_data.get('classification', {})
                                    gui._update_live_classification_display(
                                        sweep_num=current_save_key,  # Use current_save_key for consistency
                                        total_sweeps=total_sweeps_count,
                                        classification_data=classification
                                    )
                                except Exception as display_exc:
                                    print(f"[LIVE DISPLAY ERROR] Failed to update display: {display_exc}")
                            
                                # Store classification for summary
                                try:
                                    sweep_classifications[int(str(key))] = {
                                        'score': classification.get('memristivity_score', 0),
                                        'device_type': classification.get('device_type', 'unknown')
                                    }
                                except Exception as class_exc:
                                    print(f"[CLASSIFICATION ERROR] Failed to store classification: {class_exc}")
                            except Exception as data_exc:
                                print(f"[DATA COLLECTION ERROR] Failed to collect analysis data: {data_exc}")
                    except Exception as exc:
                        # Don't interrupt measurement flow if analysis fails
                        print(f"[CUSTOM ANALYSIS] Failed to run per-sweep analysis: {exc}")

                    # Handle inter-sweep delay (NEW - optional)
                    delay_after_sweep = params.get("delay_after_sweep_s", None)
                    if delay_after_sweep is not None:
                        try:
                            delay_time = float(delay_after_sweep)
                            if delay_time > 0:
                                print(f"Waiting {delay_time}s after sweep {key}...")
                                time.sleep(delay_time)
                        except (ValueError, TypeError):
                            print(f"Invalid delay_after_sweep_s value: {delay_after_sweep}")
                
                    # Default sleep between measurements (if no specific delay set)
                    if delay_after_sweep is None:
                        time.sleep(2)
                try:
                    if hasattr(gui, 'optical') and gui.optical is not None and bool(led):
                        gui.optical.set_enabled(False)
                    elif getattr(gui, 'psu_needed', False) and hasattr(gui, 'psu'):
                        gui.psu.led_off_380()
                except Exception:
                    # Do not skip the rest of the per-device finalization
                    pass
                try:
                    custom_label = f"custom_{selected_measurement}"
                    safe_label = sanitize_summary_artifact_label(custom_label)
                    unique_label = resolve_unique_summary_artifact_label(save_dir, safe_label)
                    gui._save_summary_artifacts(save_dir, artifact_label=unique_label)
                except Exception as exc:
                    print(f"[SAVE ERROR] Failed to save summary plots: {exc}")
                    gui._last_combined_summary_path = None
            
                # Run IV analysis on combined data from all sweeps if enabled
                try:
                    if hasattr(gui, 'v_arr_disp') and hasattr(gui, 'c_arr_disp'):
                        v_arr = list(gui.v_arr_disp) if gui.v_arr_disp else []
                        c_arr = list(gui.c_arr_disp) if gui.c_arr_disp else []
                    
                        if len(v_arr) > 0 and len(c_arr) > 0:
                            # Get timestamps if available
                            t_arr = None
                            if hasattr(gui, 't_arr_disp') and gui.t_arr_disp:
                                t_arr = list(gui.t_arr_disp)
                        
                            # Build metadata
                            metadata = {}
                            if hasattr(gui, 'optical') and gui.optical is not None:
                                try:
                                    caps = getattr(gui.optical, 'capabilities', {})
                                    if caps.get('type'):
                                        metadata['led_type'] = str(caps.get('type', ''))
                                except Exception:
                                    pass
                        
                            # Use measurement name as filename
                            file_name = f"custom_{selected_measurement}"
                        
                            # Call analysis helper
                            # NOTE: Pass is_custom_sequence=True to suppress automatic plotting
                            # (Individual sweeps already have plots, this is just for combined stats)
                            gui._run_analysis_if_enabled(
                                voltage=v_arr,
                                current=c_arr,
                                timestamps=t_arr,
                                save_dir=save_dir,
                                file_name=file_name,
                                metadata=metadata,
                                is_custom_sequence=True,  # Suppress automatic plotting
                                sweep_number=9999,  # Dummy value (will be ignored for combined analysis)
                                device_memristive_flag=True  # Allow analysis to run (combined data)
                            )
                except Exception as exc:
                    # Don't interrupt measurement flow if analysis fails
                    print(f"[ANALYSIS] Failed to run analysis in custom measurement: {exc}")
            
                gui.ax_all_iv.clear()
                gui.ax_all_logiv.clear()
                gui.keithley.enable_output(False)

                end = time.time()
                print("total time for ", selected_measurement, "=", end - start, " - ")

                gui.data_saver.log_measurement_event(
                    save_dir,
                    filename=f"custom_{selected_measurement}",
                    file_path=save_dir,
                    measurement_type=selected_measurement,
                    status="saved",
                    sample_name=gui.sample_name_var.get(),
                    section=gui.final_device_letter,
                    device_number=gui.final_device_number,
                )
            
                # === GENERATE SEQUENCE SUMMARY ===
                # Wrap in try-except to ensure measurement flow is never interrupted
                try:
                    if sequence_analysis_results:
                        device_id = f"{gui.sample_name_var.get()}_{gui.final_device_letter}_{gui.final_device_number}"
                        gui._generate_sequence_summary(
                            device_id=device_id,
                            sequence_name=selected_measurement,
                            sequence_results=sequence_analysis_results,
                            save_dir=save_dir,
                            total_sweeps=total_sweeps_count
                        )
                except Exception as exc:
                    # Don't interrupt measurement flow if summary generation fails
                    _debug_print(f"[SUMMARY ERROR] Failed to generate sequence summary: {exc}")
                    import traceback
                    traceback.print_exc()
            
                # === AUTOMATIC COMPREHENSIVE ANALYSIS AFTER CUSTOM MEASUREMENT ===
                # DISABLED: Auto analysis should only run after the very last sample is measured
                # This will be a later feature - for now, only dashboard/general graphs are plotted
                # (Dashboard graphs are handled by the plotting system automatically)
                pass

                _debug_print(gui.single_device_flag,device_count)
            
                if gui.single_device_flag:
                    _debug_print("Measuring one device only")
                    # Stop iterating further devices by exiting the device loop
                
                    break
                if not gui.single_device_flag:
                    # Check if in manual mode - skip automatic advancement
                    if hasattr(gui.sample_gui, 'multiplexer_type') and gui.sample_gui.multiplexer_type == "Manual":
                        _debug_print("Manual mode: Skipping automatic device advancement - user must manually advance")
                        gui.log_terminal("Manual mode: Measurement complete. Please manually advance to next device using GUI buttons.")
                    else:
                        gui.sample_gui.next_device()
                        time.sleep(0.1)
                        gui.sample_gui.change_relays()
                        print("Switching Device")


            # Always mark measurement complete in GUI
            if hasattr(gui, "_finish_measurement_ui"):
                gui._finish_measurement_ui()
            else:
                gui.measuring = False
                gui._set_measurement_feedback(False)
            if gui.telegram.is_enabled():
                combined = getattr(gui, '_last_combined_summary_path', None)
                gui.telegram.start_post_measurement_worker(save_dir, combined)
            else:
                # Only show blocking popup when bot is disabled
                messagebox.showinfo("Complete", "Measurements finished.")
        else:
            print("Selected measurement not found in JSON file.")
