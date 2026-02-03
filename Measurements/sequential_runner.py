"""
Sequential Measurement Runner
=============================

Encapsulates the legacy sequential measurement workflow that previously lived
inside `Measurement_GUI`.  By lifting the implementation into this standalone
module we reduce the size of the GUI class while keeping behaviour identical.

The runner accepts the existing GUI instance and operates on its public
attributes/callbacks (status updates, logging, plot buffers, instrument
handles).  This keeps the refactor low risk while paving the way for a future
dependency-injected design.
"""

from __future__ import annotations

import os
import time
from typing import Any, Iterable

import numpy as np

from Measurements.measurement_services_smu import VoltageRangeMode


def run_sequential_measurement(gui: Any) -> None:
    """Entry point used by `MeasurementGUI.sequential_measure`."""
    _reset_for_run(gui)

    try:
        mode = _get_str(getattr(gui, "Sequential_measurement_var", None), "Iv Sweep")
        if mode == "Iv Sweep":
            _run_iv_sweep_mode(gui)
        elif mode == "Single Avg Measure":
            _run_single_avg_mode(gui)
        else:
            _log(gui, f"Unknown sequential measurement mode '{mode}'.")
    finally:
        gui.measuring = False
        _safe_disable_output(gui, set_zero=False)


def _reset_for_run(gui: Any) -> None:
    gui._reset_plots_for_new_run()
    gui.measuring = True
    gui.stop_measurement_flag = False
    try:
        gui.bring_to_top()
    except Exception:
        pass

    use_custom = _get_bool(getattr(gui, "use_custom_save_var", None), False)
    custom_location = getattr(gui, "custom_save_location", None)
    if not (use_custom and custom_location):
        try:
            gui.check_for_sample_name()
        except Exception:
            pass

    print("Running sequential measurement:")


def _run_iv_sweep_mode(gui: Any) -> None:
    passes = max(1, _get_int(getattr(gui, "sequential_number_of_sweeps", 1), 1))
    voltage_limit = _get_float(getattr(gui, "sq_voltage", 0.0), 0.0)
    delay_between_passes = max(
        0.0, _get_float(getattr(gui, "sq_time_delay", 0.0), 0.0)
    )
    icc_val = _get_float(getattr(gui, "icc", 0.1), 0.1)

    count_pass = 1
    interrupted = False

    for pass_index in range(passes):
        if getattr(gui, "stop_measurement_flag", False):
            interrupted = True
            break

        print(f"Starting pass #{pass_index + 1}")

        voltage_array = _build_voltage_range(gui, 0.0, voltage_limit, 0.05)

        current_device = getattr(gui, "current_device", None)
        device_list = list(getattr(gui, "device_list", []))
        if current_device in device_list:
            start_index = device_list.index(current_device)
        else:
            start_index = 0

        device_count = len(device_list) if device_list else 0
        if device_count == 0:
            _log(gui, "Sequential measurement aborted: no devices available.")
            interrupted = True
            break

        for offset in range(device_count):
            if getattr(gui, "stop_measurement_flag", False):
                interrupted = True
                break

            device = device_list[(start_index + offset) % device_count]

            _update_status(gui, f"Measuring {device}...")
            _safe_master_update(gui)

            try:
                gui.keithley.set_voltage(0, icc_val)
                gui.keithley.enable_output(True)
            except Exception:
                pass

            time.sleep(0.5)

            def _on_point(voltage: float, current: float, timestamp: float) -> None:
                gui.v_arr_disp.append(voltage)
                gui.c_arr_disp.append(current)
                gui.t_arr_disp.append(timestamp)

            try:
                # Use unified API directly from IVControllerManager
                if hasattr(gui.keithley, 'do_iv_sweep'):
                    from Measurements.sweep_config import SweepConfig
                    from Measurements.source_modes import SourceMode
                    
                    # Determine start/stop from voltage array
                    v_list = list(voltage_array)
                    if not v_list:
                        return
                    start_v = v_list[0]
                    stop_v = v_list[-1]
                    
                    config = SweepConfig(
                        start_v=start_v,
                        stop_v=stop_v,
                        step_v=0.05,  # Default, not used since voltage_list is provided
                        step_delay=0.05,
                        sweep_type="FS",
                        sweeps=1,
                        pause_s=0.0,
                        icc=icc_val,
                        led=False,
                        power=1.0,
                        sequence=None,
                        source_mode=SourceMode.VOLTAGE,
                        voltage_list=v_list,
                    )
                    
                    v_arr, c_arr, timestamps = gui.keithley.do_iv_sweep(
                        config=config,
                        psu=getattr(gui, "psu", None),
                        optical=None,
                        should_stop=lambda: getattr(gui, "stop_measurement_flag", False),
                        on_point=_on_point,
                    )
                else:
                    # Fallback to measurement service (backwards compatibility)
                    v_arr, c_arr, timestamps = gui.measurement_service.run_iv_sweep(
                        keithley=gui.keithley,
                        icc=icc_val,
                        sweeps=1,
                        step_delay=0.05,
                        voltage_range=voltage_array,
                        psu=getattr(gui, "psu", None),
                        led=False,
                        power=1.0,
                        sequence=None,
                        pause_s=0.0,
                        smu_type=getattr(gui, "SMU_type", "Keithley 2401"),
                        should_stop=lambda: getattr(gui, "stop_measurement_flag", False),
                        on_point=_on_point,
                    )
            except Exception as exc:
                _log(gui, f"Sequential measurement error: {exc}")
                interrupted = True
                break

            data = np.column_stack((v_arr, c_arr, timestamps))
            _persist_iv_sweep(gui, data, device, count_pass, voltage_limit, offset)

            if not getattr(gui, "single_device_flag", True):
                _advance_device(gui)

        count_pass += 1
        if getattr(gui, "stop_measurement_flag", False):
            interrupted = True
            break

        if pass_index < passes - 1 and delay_between_passes > 0:
            time.sleep(delay_between_passes)

    if interrupted:
        _update_status(gui, "Sequential measurement stopped.")
    else:
        _update_status(gui, "Sequential measurement complete.")
        
        # Run IV analysis on combined data if enabled
        try:
            if hasattr(gui, 'v_arr_disp') and hasattr(gui, 'c_arr_disp'):
                v_arr = list(gui.v_arr_disp) if gui.v_arr_disp else []
                c_arr = list(gui.c_arr_disp) if gui.c_arr_disp else []
                
                if len(v_arr) > 0 and len(c_arr) > 0:
                    save_dir = gui._get_save_directory(
                        gui.sample_name_var.get(),
                        gui.final_device_letter,
                        gui.final_device_number,
                    )
                    
                    # Get timestamps if available
                    t_arr = None
                    if hasattr(gui, 't_arr_disp') and gui.t_arr_disp:
                        t_arr = list(gui.t_arr_disp)
                    
                    # Build metadata
                    metadata = {}
                    
                    # Use a generic filename for sequential measurements
                    file_name = f"sequential_measurement_{passes}passes"
                    
                    # Call analysis helper
                    gui._run_analysis_if_enabled(
                        voltage=v_arr,
                        current=c_arr,
                        timestamps=t_arr,
                        save_dir=save_dir,
                        file_name=file_name,
                        metadata=metadata
                    )
        except Exception as exc:
            # Don't interrupt measurement flow if analysis fails
            print(f"[ANALYSIS] Failed to run analysis in sequential measurement: {exc}")

    _safe_disable_output(gui)


def _persist_iv_sweep(
    gui: Any,
    data: np.ndarray,
    device: str,
    count_pass: int,
    voltage_limit: float,
    device_index: int,
) -> None:
    sample_name = _get_str(getattr(gui, "sample_name_var", None), "Sample")
    base_dir = None
    try:
        base_dir = gui._get_base_save_path()
    except Exception:
        base_dir = None

    if base_dir:
        save_dir = os.path.join(
            str(base_dir), "Multiplexer_IV_sweep", sample_name, str(device_index + 1)
        )
    else:
        save_dir = os.path.join(
            "Data_save_loc",
            "Multiplexer_IV_sweep",
            sample_name,
            str(device_index + 1),
        )

    os.makedirs(save_dir, exist_ok=True)
    filename = f"{count_pass}-FS-{voltage_limit}v-0.05sv-0.05sd-Py-Sq-1.txt"
    file_path = os.path.join(save_dir, filename)

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
        _log(gui, f"File saved: {abs_path}")
    except Exception as exc:
        print(f"[SAVE ERROR] Failed to save file: {exc}")
        _log(gui, f"Error saving IV sweep: {exc}")


def _run_single_avg_mode(gui: Any) -> None:
    passes = max(1, _get_int(getattr(gui, "sequential_number_of_sweeps", 1), 1))
    measurement_duration = _get_float(
        getattr(gui, "measurement_duration_var", 1.0), 1.0
    )
    voltage = _get_float(getattr(gui, "sq_voltage", 0.0), 0.0)
    delay_between_passes = max(
        0.0, _get_float(getattr(gui, "sq_time_delay", 0.0), 0.0)
    )

    device_list = list(getattr(gui, "device_list", []))
    if not device_list:
        _log(gui, "Sequential measurement aborted: no devices available.")
        _update_status(gui, "Sequential measurement stopped.")
        return

    if getattr(gui, "current_device", None) in device_list:
        start_index = device_list.index(gui.current_device)
    else:
        start_index = 0

    device_count = 1 if getattr(gui, "single_device_flag", False) else len(device_list)

    device_data = {
        device_list[(start_index + j) % len(device_list)]: {
            "voltages": [],
            "currents": [],
            "std_errors": [],
            "timestamps": [],
            "temperatures": [],
        }
        for j in range(device_count)
    }

    start_time = time.time()
    interrupted = False

    for pass_index in range(passes):
        if getattr(gui, "stop_measurement_flag", False):
            interrupted = True
            break

        print(f"Starting pass #{pass_index + 1}")
        for offset in range(device_count):
            if getattr(gui, "stop_measurement_flag", False):
                interrupted = True
                break

            device_idx = (start_index + offset) % len(device_list)
            device = device_list[device_idx]
            pseudo_number = device_idx + 1

            _update_status(gui, f"Pass {pass_index + 1}: Measuring {device}...")
            _safe_master_update(gui)

            measurement_timestamp = (
                time.time() - start_time + (measurement_duration / 2.0)
            )
            avg_current, std_error, _temperature = gui.measure_average_current(
                voltage, measurement_duration
            )

            entry = device_data[device]
            entry["voltages"].append(voltage)
            entry["currents"].append(avg_current)
            entry["std_errors"].append(std_error)
            entry["timestamps"].append(measurement_timestamp)

            if _get_bool(getattr(gui, "record_temp_var", None), False):
                try:
                    temperature = gui.temp_controller.get_temperature_celsius()
                except Exception:
                    temperature = float("nan")
                entry["temperatures"].append(temperature)

            _log(
                gui,
                (
                    f"Pass {pass_index + 1}, Device {device}: "
                    f"V={voltage}V, I_avg={avg_current:.3E}A, σ={std_error:.3E}A, "
                    f"t={measurement_timestamp:.1f}s"
                ),
            )

            if getattr(gui, "stop_measurement_flag", False):
                interrupted = True
                break

            if not getattr(gui, "single_device_flag", False):
                _safe_set_voltage(gui, 0.0)
                time.sleep(0.1)
                _advance_device(gui)
                print("Switching Device")
                time.sleep(0.1)

        if getattr(gui, "stop_measurement_flag", False):
            interrupted = True
            break

        if (pass_index + 1) % 5 == 0:
            _log(gui, f"Auto-saving data after {pass_index + 1} cycles...")
            gui.save_averaged_data(
                device_data, gui.sample_name_var.get(), start_index, interrupted=False
            )

        if pass_index < passes - 1 and delay_between_passes > 0:
            time.sleep(delay_between_passes)

    gui.save_averaged_data(
        device_data,
        _get_str(getattr(gui, "sample_name_var", None), "Sample"),
        start_index,
        interrupted=interrupted,
    )

    if not interrupted:
        gui.save_all_measurements_file(
            device_data,
            _get_str(getattr(gui, "sample_name_var", None), "Sample"),
            start_index,
        )
        _update_status(gui, "Measurement Complete")
        
        # Run IV analysis on combined data if enabled (for single avg mode)
        try:
            if hasattr(gui, 'v_arr_disp') and hasattr(gui, 'c_arr_disp'):
                v_arr = list(gui.v_arr_disp) if gui.v_arr_disp else []
                c_arr = list(gui.c_arr_disp) if gui.c_arr_disp else []
                
                if len(v_arr) > 0 and len(c_arr) > 0:
                    save_dir = gui._get_save_directory(
                        gui.sample_name_var.get(),
                        gui.final_device_letter,
                        gui.final_device_number,
                    )
                    
                    # Get timestamps if available
                    t_arr = None
                    if hasattr(gui, 't_arr_disp') and gui.t_arr_disp:
                        t_arr = list(gui.t_arr_disp)
                    
                    # Build metadata
                    metadata = {}
                    
                    # Use a generic filename for sequential measurements
                    file_name = "sequential_single_avg"
                    
                    # Call analysis helper
                    gui._run_analysis_if_enabled(
                        voltage=v_arr,
                        current=c_arr,
                        timestamps=t_arr,
                        save_dir=save_dir,
                        file_name=file_name,
                        metadata=metadata
                    )
        except Exception as exc:
            # Don't interrupt measurement flow if analysis fails
            print(f"[ANALYSIS] Failed to run analysis in sequential measurement: {exc}")
    else:
        _update_status(gui, "Sequential measurement stopped.")

    _safe_set_voltage(gui, 0.0)
    time.sleep(0.1)
    _safe_disable_output(gui)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _build_voltage_range(
    gui: Any, start: float, stop: float, step: float
) -> Iterable[float]:
    try:
        return gui.measurement_service.compute_voltage_range(
            start_v=start,
            stop_v=stop,
            step_v=step,
            sweep_type="FS",
            mode=VoltageRangeMode.FIXED_STEP,
        )
    except Exception:
        from Measurements.sweep_patterns import build_sweep_values, SweepType

        return build_sweep_values(start, stop, step, SweepType.FULL)


def _advance_device(gui: Any) -> None:
    try:
        gui.sample_gui.next_device()
        time.sleep(0.1)
        gui.sample_gui.change_relays()
    except Exception:
        pass


def _safe_set_voltage(gui: Any, value: float) -> None:
    try:
        gui.keithley.set_voltage(value)
    except Exception:
        pass


def _safe_disable_output(gui: Any, set_zero: bool = True) -> None:
    try:
        if set_zero:
            gui.keithley.set_voltage(0)
            time.sleep(0.1)
        gui.keithley.enable_output(False)
    except Exception:
        pass


def _safe_master_update(gui: Any) -> None:
    try:
        gui.master.update()
    except Exception:
        pass


def _update_status(gui: Any, message: str) -> None:
    setter = getattr(gui, "set_status_message", None)
    if callable(setter):
        try:
            setter(message)
            return
        except Exception:
            pass
    try:
        gui.master.title(message)
    except Exception:
        pass


def _log(gui: Any, message: str) -> None:
    try:
        gui.log_terminal(message)
    except Exception:
        pass


def _get_int(value: Any, default: int) -> int:
    try:
        raw = value.get()
    except Exception:
        raw = value
    try:
        return int(raw)
    except Exception:
        return default


def _get_float(value: Any, default: float) -> float:
    try:
        raw = value.get()
    except Exception:
        raw = value
    try:
        return float(raw)
    except Exception:
        return default


def _get_bool(value: Any, default: bool) -> bool:
    try:
        raw = value.get()
    except Exception:
        raw = value
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        return raw.lower() in {"1", "true", "yes", "on"}
    return default


def _get_str(value: Any, default: str) -> str:
    try:
        raw = value.get()
    except Exception:
        raw = value
    if raw is None:
        return default
    return str(raw)


__all__ = ["run_sequential_measurement"]


