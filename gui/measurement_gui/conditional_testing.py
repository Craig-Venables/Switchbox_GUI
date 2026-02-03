"""
Conditional Testing Runner
==========================

Run conditional memristive testing workflow.
Extracted from main.py for maintainability.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import tkinter as tk
from tkinter import messagebox


def run_quick_test(
    gui: Any,
    custom_sweep_name: str,
    device: str,
) -> Tuple[List[float], List[float], List[float]]:
    """
    Run quick screening test using a custom sweep.
    Returns (voltage_array, current_array, timestamps_array).
    """
    if not custom_sweep_name or custom_sweep_name not in gui.custom_sweeps:
        raise ValueError(f"Quick test '{custom_sweep_name}' not found in custom sweeps")

    print(f"[Conditional Testing] Running quick test '{custom_sweep_name}' on device {device}")

    original_selection = getattr(gui, "custom_measurement_var", None)
    original_value = original_selection.get() if original_selection else None

    if hasattr(gui, "custom_measurement_var"):
        gui.custom_measurement_var.set(custom_sweep_name)

    sweeps = gui.custom_sweeps[custom_sweep_name]["sweeps"]
    if not sweeps:
        raise ValueError(f"Quick test '{custom_sweep_name}' has no sweeps defined")

    first_sweep_key = sorted(sweeps.keys(), key=lambda x: int(x) if x.isdigit() else 0)[0]
    params = sweeps[first_sweep_key]

    try:
        v_arr, c_arr, t_arr = execute_single_sweep_for_conditional_test(gui, params, device)
        return v_arr, c_arr, t_arr
    finally:
        if original_selection and original_value:
            original_selection.set(original_value)


def execute_single_sweep_for_conditional_test(
    gui: Any,
    params: Dict[str, Any],
    device: str,
) -> Tuple[List[float], List[float], List[float]]:
    """Execute a single sweep for conditional testing."""
    from Measurements.source_modes import SourceMode

    measurement_type = str(params.get("measurement_type", "IV"))
    if "mode" in params:
        measurement_type = params["mode"]
    elif "excitation" in params:
        excitation_map = {
            "DC Triangle IV": "IV",
            "SMU Pulsed IV": "PulsedIV",
            "SMU Fast Pulses": "FastPulses",
            "SMU Fast Hold": "Hold",
        }
        measurement_type = excitation_map.get(params["excitation"], "IV")

    start_v = params.get("start_v", 0)
    stop_v = params.get("stop_v", 1)
    step_v = params.get("step_v", 0.1)
    num_sweeps = params.get("sweeps", 1)
    step_delay = params.get("step_delay", 0.05)
    sweep_type = params.get("Sweep_type", "FS")
    icc_val = params.get("icc", float(gui.icc.get()) if hasattr(gui, "icc") else 1e-3)

    led = bool(params.get("LED_ON", 0))
    power = params.get("power", 1)
    sequence = params.get("sequence", None)
    if sequence == 0:
        sequence = None

    if measurement_type == "IV":

        def _on_point(v, i, t_s):
            pass

        v_arr, c_arr, timestamps = gui.measurement_service.run_iv_sweep(
            keithley=gui.keithley,
            start_v=start_v,
            stop_v=stop_v,
            step_v=step_v,
            sweeps=num_sweeps,
            step_delay=step_delay,
            sweep_type=sweep_type,
            icc=icc_val,
            psu=getattr(gui, "psu", None),
            led=led,
            power=power,
            optical=getattr(gui, "optical", None),
            sequence=sequence,
            pause_s=0,
            smu_type=getattr(gui, "SMU_type", "Keithley 2401"),
            source_mode=SourceMode.VOLTAGE,
            should_stop=lambda: getattr(gui, "stop_measurement_flag", False),
            on_point=_on_point,
        )
        return v_arr, c_arr, timestamps
    else:
        raise ValueError(
            f"Quick test measurement type '{measurement_type}' not supported for conditional testing"
        )


def run_tiered_test(
    gui: Any,
    test_config: Dict[str, Any],
    device: str,
) -> Optional[Tuple[List[float], List[float], List[float]]]:
    """
    Run a tiered test (basic or high-quality) using a custom sweep.
    Returns (v_arr, c_arr, t_arr) of the last sweep for re-evaluation, or None.
    """
    custom_sweep_name = test_config.get("custom_sweep_name", "")
    if not custom_sweep_name or custom_sweep_name not in gui.custom_sweeps:
        print(f"[Conditional Testing] Warning: Test '{custom_sweep_name}' not found, skipping")
        return None

    print(f"[Conditional Testing] Running tiered test '{custom_sweep_name}' on device {device}")

    original_selection = getattr(gui, "custom_measurement_var", None)
    original_value = original_selection.get() if original_selection else None

    last_v_arr, last_c_arr, last_t_arr = None, None, None

    try:
        if hasattr(gui, "custom_measurement_var"):
            gui.custom_measurement_var.set(custom_sweep_name)

        sweeps = gui.custom_sweeps[custom_sweep_name]["sweeps"]

        for key, params in sweeps.items():
            if gui.stop_measurement_flag:
                break

            v_arr, c_arr, t_arr = execute_single_sweep_for_conditional_test(gui, params, device)
            last_v_arr, last_c_arr, last_t_arr = v_arr, c_arr, t_arr

            save_dir = gui._get_save_directory(
                gui.sample_name_var.get(),
                gui.final_device_letter,
                gui.final_device_number,
            )
            os.makedirs(save_dir, exist_ok=True)

            from Measurements.single_measurement_runner import find_largest_number_in_folder

            key_num = find_largest_number_in_folder(save_dir)
            save_key = 0 if key_num is None else key_num + 1

            stop_v = params.get("stop_v", 1)
            step_v = params.get("step_v", 0.1)
            step_delay = params.get("step_delay", 0.05)
            sweep_type = params.get("Sweep_type", "FS")
            code_name = gui.custom_sweeps[custom_sweep_name].get("code_name", custom_sweep_name)

            name = f"{save_key}-{sweep_type}-{stop_v}v-{step_v}sv-{step_delay}sd-Py-{code_name}"
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
                print(f"[Conditional Testing] Saved: {file_path}")
            except Exception as exc:
                print(f"[Conditional Testing] Failed to save {file_path}: {exc}")
    finally:
        if original_selection and original_value:
            original_selection.set(original_value)

    if last_v_arr is not None:
        return (last_v_arr, last_c_arr, last_t_arr)
    return None


def run_conditional_testing(gui: Any) -> None:
    """
    Main entry point for conditional memristive testing.
    Runs quick test on all devices, analyzes, and conditionally runs additional tests.
    """
    if not gui.connected:
        messagebox.showwarning("Warning", "Not connected to Keithley!")
        return

    config = gui._load_conditional_test_config()

    quick_test_name = config.get("quick_test", {}).get("custom_sweep_name", "")
    if not quick_test_name:
        messagebox.showerror("Error", "Quick test not configured. Please select a quick test.")
        return

    basic_threshold = config.get("thresholds", {}).get("basic_memristive", 60)
    high_quality_threshold = config.get("thresholds", {}).get("high_quality", 80)
    re_evaluate_enabled = config.get("re_evaluate_during_test", {}).get("enabled", True)
    include_memcapacitive = config.get("include_memcapacitive", True)

    basic_test_name = config.get("tests", {}).get("basic_memristive", {}).get("custom_sweep_name", "")
    high_quality_test_name = (
        config.get("tests", {}).get("high_quality", {}).get("custom_sweep_name", "")
    )

    if not basic_test_name:
        messagebox.showerror("Error", "Basic memristive test not configured.")
        return

    gui.stop_measurement_flag = False
    device_scores: Dict[str, float] = {}

    device_count = len(gui.device_list)
    start_index = 0
    if gui.current_device in gui.device_list:
        start_index = gui.device_list.index(gui.current_device)

    for i in range(device_count):
        device = gui.device_list[(start_index + i) % device_count]

        if gui.stop_measurement_flag:
            print("[Conditional Testing] Measurement interrupted!")
            break

        print(f"[Conditional Testing] Processing device {device}")
        gui.set_status_message(f"Conditional Testing: Device {device}")
        gui.master.update()

        try:
            v_arr, c_arr, t_arr = run_quick_test(gui, quick_test_name, device)

            save_dir = gui._get_save_directory(
                gui.sample_name_var.get(),
                gui.final_device_letter,
                gui.final_device_number,
            )
            analysis = gui._run_analysis_sync(v_arr, c_arr, t_arr, device, save_dir)

            if not analysis:
                print(f"[Conditional Testing] Analysis failed for device {device}, skipping")
                continue

            score = analysis.get("classification", {}).get("memristivity_score", 0)
            device_type = analysis.get("classification", {}).get("device_type", "")
            device_scores[device] = score

            is_qualified = False
            if include_memcapacitive:
                is_qualified = device_type in ["memristive", "memcapacitive"] or score >= basic_threshold
            else:
                is_qualified = device_type == "memristive" or score >= basic_threshold

            print(
                f"[Conditional Testing] Device {device}: Score={score:.1f}, Type={device_type}, "
                f"Qualified={is_qualified} (include_memcapacitive={include_memcapacitive})"
            )

            if is_qualified:
                basic_test_data = None
                if basic_test_name:
                    basic_test_data = run_tiered_test(
                        gui,
                        {"custom_sweep_name": basic_test_name},
                        device,
                    )

                if score >= high_quality_threshold:
                    if high_quality_test_name:
                        run_tiered_test(
                            gui,
                            {"custom_sweep_name": high_quality_test_name},
                            device,
                        )

                elif re_evaluate_enabled and basic_test_name and basic_test_data:
                    basic_v, basic_c, basic_t = basic_test_data
                    basic_test_analysis = gui._run_analysis_sync(
                        basic_v, basic_c, basic_t, device, save_dir
                    )
                    if basic_test_analysis:
                        new_score = basic_test_analysis.get("classification", {}).get(
                            "memristivity_score", 0
                        )
                        new_device_type = basic_test_analysis.get("classification", {}).get(
                            "device_type", ""
                        )

                        qualifies_high_quality = False
                        if include_memcapacitive:
                            qualifies_high_quality = (
                                new_device_type in ["memristive", "memcapacitive"]
                                or new_score >= high_quality_threshold
                            )
                        else:
                            qualifies_high_quality = (
                                new_device_type == "memristive"
                                or new_score >= high_quality_threshold
                            )

                        print(
                            f"[Conditional Testing] Device {device}: Re-evaluation score={new_score:.1f}, "
                            f"type={new_device_type}, qualifies={qualifies_high_quality}"
                        )
                        if qualifies_high_quality and high_quality_test_name:
                            print(
                                f"[Conditional Testing] Device {device}: Score improved to {new_score:.1f}, "
                                "running high-quality test"
                            )
                            run_tiered_test(
                                gui,
                                {"custom_sweep_name": high_quality_test_name},
                                device,
                            )
            else:
                print(
                    f"[Conditional Testing] Device {device}: Score {score:.1f} below threshold "
                    f"{basic_threshold}, skipping additional tests"
                )

        except Exception as exc:
            print(f"[Conditional Testing] Error processing device {device}: {exc}")
            import traceback

            traceback.print_exc()
            continue

    final_test_config = config.get("final_test", {})
    if final_test_config.get("enabled", False) and hasattr(gui, "_run_final_test"):
        gui._run_final_test(final_test_config, device_scores)

    gui.set_status_message("Conditional Testing Complete")
    messagebox.showinfo("Complete", "Conditional testing finished for all devices.")


def update_conditional_testing_button_state(gui: Any) -> None:
    """Update the conditional testing run button state based on connection status."""
    if hasattr(gui, "conditional_testing_run_button"):
        gui.conditional_testing_run_button.config(
            state=tk.NORMAL if gui.connected else tk.DISABLED
        )
    if hasattr(gui, "run_conditional_button_main"):
        gui.run_conditional_button_main.config(
            state=tk.NORMAL if gui.connected else tk.DISABLED
        )
