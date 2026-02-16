"""
Plot and Analysis Handlers
==========================

Orchestration for plotting, stats display, and sample folder selection.
Extracted from main.py for maintainability.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional

import numpy as np

DEBUG_ENABLED = False


def _debug_print(*args: Any, **kwargs: Any) -> None:
    if DEBUG_ENABLED:
        print(*args, **kwargs)


def clear_sample_folder_selection(gui: Any) -> None:
    """Clear the selected sample folder (use current sample instead)."""
    if hasattr(gui, "analysis_folder_var"):
        gui.analysis_folder_var.set("(Use current sample)")
        print("[ANALYSIS] Cleared folder selection - will use current sample")


def clear_stats_plots(gui: Any) -> None:
    """Clear stats plots."""
    try:
        if hasattr(gui, "stats_plot_figure") and hasattr(gui, "stats_plot_canvas"):
            fig = gui.stats_plot_figure
            fig.clear()
            ax = fig.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                "No device selected\n\nSelect a device to view trends",
                ha="center",
                va="center",
                fontsize=14,
                color="gray",
            )
            ax.axis("off")
            gui.stats_plot_canvas.draw()
    except Exception as e:
        print(f"[STATS] Error clearing plots: {e}")


def browse_sample_folder_for_analysis(gui: Any) -> None:
    """Browse for a sample folder to analyze retroactively."""
    try:
        initial_dir = None
        if hasattr(gui, "sample_name_var") and gui.sample_name_var.get():
            try:
                initial_dir = gui._get_sample_save_directory(gui.sample_name_var.get())
                initial_dir = os.path.dirname(initial_dir) if os.path.exists(initial_dir) else None
            except Exception:
                pass

        if not initial_dir and hasattr(gui, "data_saver") and hasattr(gui.data_saver, "base_directory"):
            try:
                initial_dir = gui.data_saver.base_directory
            except Exception:
                pass

        folder = filedialog.askdirectory(
            title="Select Sample Folder to Analyze",
            initialdir=initial_dir,
        )

        if folder:
            has_tracking = (
                os.path.exists(os.path.join(folder, "sample_analysis", "analysis", "device_tracking"))
                or os.path.exists(os.path.join(folder, "sample_analysis", "device_tracking"))
                or os.path.exists(os.path.join(folder, "sample_analysis", "device_research"))
                or os.path.exists(os.path.join(folder, "device_tracking"))
                or os.path.exists(os.path.join(folder, "device_research"))
            )

            has_device_folders = False
            try:
                for item in os.listdir(folder):
                    item_path = os.path.join(folder, item)
                    if os.path.isdir(item_path):
                        for subitem in os.listdir(item_path):
                            subitem_path = os.path.join(item_path, subitem)
                            if os.path.isdir(subitem_path):
                                txt_files = [f for f in os.listdir(subitem_path) if f.endswith(".txt")]
                                if txt_files:
                                    has_device_folders = True
                                    break
                        if has_device_folders:
                            break
            except Exception:
                pass

            if has_tracking or has_device_folders:
                if hasattr(gui, "analysis_folder_var"):
                    gui.analysis_folder_var.set(folder)
                    print(f"[ANALYSIS] Selected folder: {folder}")
                    if has_device_folders and not has_tracking:
                        print(
                            "[ANALYSIS] Note: Folder contains raw data - will run retroactive analysis first"
                        )
            else:
                messagebox.showwarning(
                    "Invalid Folder",
                    "Selected folder doesn't appear to be a sample folder.\n\n"
                    "Expected either:\n"
                    "- 'sample_analysis/analysis/device_tracking' or 'sample_analysis/device_research' subfolders, OR\n"
                    "- Device subfolders (letter/number) containing .txt measurement files",
                )
    except Exception as e:
        print(f"[ANALYSIS] Error browsing folder: {e}")
        import traceback

        traceback.print_exc()


def browse_impedance_folder(gui: Any) -> None:
    """Browse for a folder containing SMaRT impedance CSV or .dat files."""
    try:
        initial_dir = None
        if hasattr(gui, "impedance_folder_var") and gui.impedance_folder_var.get():
            p = Path(gui.impedance_folder_var.get())
            if p.exists() and p.is_dir():
                initial_dir = str(p)
        if not initial_dir and hasattr(gui, "data_saver") and hasattr(gui.data_saver, "base_directory"):
            try:
                initial_dir = gui.data_saver.base_directory
            except Exception:
                pass
        folder = filedialog.askdirectory(
            title="Select folder with impedance CSV or .dat files",
            initialdir=initial_dir,
        )
        if folder and hasattr(gui, "impedance_folder_var"):
            gui.impedance_folder_var.set(folder)
            print(f"[IMPEDANCE] Selected folder: {folder}")
    except Exception as e:
        print(f"[IMPEDANCE] Error browsing folder: {e}")
        import traceback
        traceback.print_exc()


def run_impedance_visualisation(gui: Any) -> None:
    """Run the Impedance Analyzer visualisation (CSV) on the selected folder."""
    folder = getattr(gui, "impedance_folder_var", None) and gui.impedance_folder_var.get()
    if not folder or not Path(folder).exists():
        messagebox.showwarning(
            "No folder selected",
            "Please select a folder containing impedance CSV (or .dat) files using Browse.",
        )
        return
    try:
        tools_dir = Path(__file__).resolve().parents[2] / "tools" / "Impedence Analyzer"
        script = tools_dir / "visualise_csv.py"
        if not script.exists():
            script = tools_dir / "visualise_dat.py"
        if not script.exists():
            messagebox.showerror(
                "Impedance tool not found",
                f"Expected visualise_csv.py or visualise_dat.py in:\n{tools_dir}",
            )
            return
        subprocess.Popen(
            [sys.executable, str(script), folder],
            cwd=str(tools_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
        print(f"[IMPEDANCE] Launched visualisation for: {folder}")
    except Exception as e:
        messagebox.showerror("Impedance visualisation", str(e))
        import traceback
        traceback.print_exc()


def update_classification_display(gui: Any, classification_data: Dict[str, Any]) -> None:
    """Update top bar with classification and score."""
    try:
        device_type = classification_data.get("device_type", "")
        score = classification_data.get("memristivity_score")

        if not score:
            return

        if score >= 80:
            color = "#4CAF50"
        elif score >= 60:
            color = "#FFA500"
        elif score >= 40:
            color = "#FF9800"
        else:
            color = "#F44336"

        if hasattr(gui, "classification_label"):
            text = f"| {device_type.title()} ({score:.1f}/100)"
            gui.classification_label.config(text=text, fg=color)
    except Exception as e:
        print(f"[CLASSIFICATION DISPLAY] Error updating: {e}")


def plot_measurement_in_background(
    gui: Any,
    voltage: Any,
    current: Any,
    timestamps: Any,
    save_dir: str,
    device_name: str,
    sweep_number: int,
    is_memristive: Optional[bool] = None,
    filename: Optional[str] = None,
    measurement_type: str = "IV",
    measurement_params: Optional[dict] = None,
) -> None:
    """Plot measurement graphs in background thread using UnifiedPlotter."""
    def run_plotting() -> None:
        try:
            import sys
            import matplotlib
            matplotlib.use("Agg")
            try:
                from plotting import UnifiedPlotter
            except ImportError:
                plotting_path = Path(__file__).resolve().parents[2] / "plotting"
                if str(plotting_path.parent) not in sys.path:
                    sys.path.insert(0, str(plotting_path.parent))
                from plotting import UnifiedPlotter  # type: ignore

            import matplotlib.pyplot as plt
            plt.rcParams["text.usetex"] = False
            plt.rcParams["mathtext.default"] = "regular"
            plt.rcParams["axes.formatter.use_mathtext"] = False
            plt.rcParams["axes.formatter.min_exponent"] = 0
            plt.rcParams["axes.unicode_minus"] = False

            graphs_dir = os.path.join(save_dir, "Graphs")
            os.makedirs(graphs_dir, exist_ok=True)

            plot_filename = filename
            if plot_filename is None:
                try:
                    txt_files = [f for f in os.listdir(save_dir) if f.endswith(".txt")]
                    if txt_files:
                        txt_files_with_time = [
                            (f, os.path.getmtime(os.path.join(save_dir, f))) for f in txt_files
                        ]
                        txt_files_with_time.sort(key=lambda x: x[1], reverse=True)
                        plot_filename = os.path.splitext(txt_files_with_time[0][0])[0]
                    else:
                        plot_filename = f"{device_name}_sweep_{sweep_number}"
                except Exception:
                    plot_filename = f"{device_name}_sweep_{sweep_number}"

            conduction_dir = os.path.join(graphs_dir, "conduction")
            sclc_dir = os.path.join(graphs_dir, "sclc_fit")
            if is_memristive:
                os.makedirs(conduction_dir, exist_ok=True)
                os.makedirs(sclc_dir, exist_ok=True)

            is_memristive_flag = is_memristive
            if is_memristive is None:
                try:
                    memristivity_score = 0
                    if hasattr(gui, "_last_analysis_result"):
                        analysis = gui._last_analysis_result
                        if isinstance(analysis, dict):
                            classification = analysis.get("classification", {})
                            memristivity_score = classification.get("memristivity_score", 0)
                    is_memristive_flag = memristivity_score > 60
                except Exception:
                    is_memristive_flag = False

            sample_name = gui.sample_name_var.get() if hasattr(gui, "sample_name_var") else ""
            title_prefix = f"{sample_name} {device_name}" if sample_name else device_name
            meas_type = measurement_type
            meas_params = measurement_params if measurement_params else {}

            if meas_type == "Endurance":
                plotter_end = UnifiedPlotter(save_dir=graphs_dir, auto_close=True)
                read_voltage = meas_params.get("read_v", meas_params.get("read_voltage", 0.2))
                plotter_end.plot_endurance_analysis(
                    voltage=voltage,
                    current=current,
                    timestamps=timestamps,
                    device_name=plot_filename,
                    title_prefix=title_prefix,
                    read_voltage=read_voltage,
                    save_name_cycle_resistance=f"{plot_filename}_endurance_cycle_resistance.png",
                    save_name_onoff_ratio=f"{plot_filename}_endurance_onoff_ratio.png",
                )
                _debug_print(f"[PLOT] Generated endurance plots for {plot_filename}")
            elif meas_type == "Retention":
                plotter_ret = UnifiedPlotter(save_dir=graphs_dir, auto_close=True)
                read_voltage = meas_params.get("read_v", meas_params.get("read_voltage", 0.2))
                plotter_ret.plot_retention_analysis(
                    voltage=voltage,
                    current=current,
                    timestamps=timestamps,
                    device_name=plot_filename,
                    title_prefix=title_prefix,
                    read_voltage=read_voltage,
                    save_name_loglog=f"{plot_filename}_retention_loglog.png",
                    save_name_linear=f"{plot_filename}_retention_linear.png",
                    save_name_resistance=f"{plot_filename}_retention_resistance.png",
                )
                _debug_print(f"[PLOT] Generated retention plots for {plot_filename}")
            elif meas_type in ("Forming", "Pulse"):
                plotter_form = UnifiedPlotter(save_dir=graphs_dir, auto_close=True)
                read_voltage = meas_params.get("read_voltage", meas_params.get("read_v", 0.1))
                forming_metadata = meas_params.get("forming_metadata", {})
                plotter_form.plot_pulse_forming_analysis(
                    voltage=voltage,
                    current=current,
                    timestamps=timestamps,
                    device_name=plot_filename,
                    title_prefix=title_prefix,
                    forming_metadata=forming_metadata,
                    read_voltage=read_voltage,
                    save_name_time_current=f"{plot_filename}_forming_time_current.png",
                    save_name_pulse_current=f"{plot_filename}_forming_pulse_current.png",
                    save_name_voltage_current=f"{plot_filename}_forming_voltage_current.png",
                )
                _debug_print(f"[PLOT] Generated forming plots for {plot_filename}")
            else:
                plotter_graph = UnifiedPlotter(save_dir=graphs_dir, auto_close=True)
                section_letter, dev_num = "", ""
                if device_name:
                    for idx, char in enumerate(device_name):
                        if char.isdigit():
                            section_letter = device_name[:idx]
                            dev_num = device_name[idx:]
                            break
                    if not section_letter:
                        section_letter = device_name
                plotter_graph.plot_iv_dashboard(
                    voltage=voltage,
                    current=current,
                    time=timestamps,
                    device_name=plot_filename,
                    title=f"{title_prefix} {plot_filename} - IV Dashboard",
                    save_name=f"{plot_filename}_iv_dashboard.png",
                    sample_name=sample_name,
                    section=section_letter,
                    device_num=dev_num,
                )
                try:
                    os.makedirs(conduction_dir, exist_ok=True)
                    os.makedirs(sclc_dir, exist_ok=True)
                    plotter_cond = UnifiedPlotter(save_dir=conduction_dir, auto_close=True)
                    plotter_cond.plot_conduction_analysis(
                        voltage=voltage,
                        current=current,
                        device_name=plot_filename,
                        title=f"{title_prefix} {plot_filename} - Conduction Analysis",
                        save_name=f"{plot_filename}_conduction.png",
                    )
                    plotter_sclc = UnifiedPlotter(save_dir=sclc_dir, auto_close=True)
                    plotter_sclc.plot_sclc_fit(
                        voltage=voltage,
                        current=current,
                        device_name=plot_filename,
                        title=f"{title_prefix} {plot_filename} - SCLC Fit",
                        save_name=f"{plot_filename}_sclc_fit.png",
                    )
                except Exception as e:
                    _debug_print(f"[PLOT] Error plotting conduction/SCLC for {plot_filename}: {e}")
                _debug_print(f"[PLOT] Generated plots for {plot_filename} (memristive={is_memristive_flag})")
        except ImportError as e:
            _debug_print(f"[PLOT ERROR] Failed to import UnifiedPlotter: {e}")
        except Exception as e:
            _debug_print(f"[PLOT ERROR] Background plotting failed: {e}")
            import traceback
            traceback.print_exc()

    plot_thread = threading.Thread(target=run_plotting, daemon=True)
    plot_thread.start()
    _debug_print(f"[PLOT] Background plotting queued for {device_name} sweep {sweep_number}")


def generate_sequence_summary(
    gui: Any,
    device_id: str,
    sequence_name: str,
    sequence_results: List[Dict[str, Any]],
    save_dir: str,
    total_sweeps: int,
) -> None:
    """Generate comprehensive summary report for custom measurement sequence."""
    try:
        sample_name = gui.sample_name_var.get() if hasattr(gui, "sample_name_var") else None
        if not sample_name:
            _debug_print("[SUMMARY ERROR] No sample name available")
            return
        sample_save_dir = gui._get_sample_save_directory(sample_name)
        summary_dir = os.path.join(sample_save_dir, "sample_analysis", "device_summaries")
        os.makedirs(summary_dir, exist_ok=True)

        scores, voltages = [], []
        best_sweep, worst_sweep = None, None
        for result in sequence_results:
            classification = result["analysis"].get("classification", {})
            score = classification.get("memristivity_score", 0)
            scores.append(score)
            voltages.append(result["voltage"])
            if best_sweep is None or score > best_sweep["score"]:
                best_sweep = {"sweep": result["sweep_number"], "score": score, "voltage": result["voltage"]}
            if worst_sweep is None or score < worst_sweep["score"]:
                worst_sweep = {"sweep": result["sweep_number"], "score": score, "voltage": result["voltage"]}

        weights = np.linspace(0.5, 1.0, len(scores)) if len(scores) > 0 else np.array([1.0])
        overall_score = float(np.average(scores, weights=weights)) if scores else 0
        final_classification = sequence_results[-1]["analysis"].get("classification", {}) if sequence_results else {}
        final_device_type = final_classification.get("device_type", "unknown")
        score_improvement = scores[-1] - scores[0] if len(scores) > 1 else 0
        is_forming = score_improvement > 15

        lines = [
            "=" * 80,
            "CUSTOM MEASUREMENT SEQUENCE SUMMARY",
            "=" * 80,
            f"Device: {device_id}",
            f"Sequence: {sequence_name}",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Sweeps: {total_sweeps}",
            f"Analyzed Sweeps: {len(scores)} (memristive sweeps only)",
            "",
            "OVERALL ASSESSMENT",
            "-" * 80,
            f"Overall Device Score: {overall_score:.1f}/100",
            f"Final Classification: {(final_device_type or 'UNKNOWN').upper() if isinstance(final_device_type, str) else 'UNKNOWN'}",
        ]
        if overall_score >= 80:
            lines.append("Rating: EXCELLENT - Ready for advanced testing")
        elif overall_score >= 60:
            lines.append("Rating: GOOD - Suitable for basic memristive applications")
        elif overall_score >= 40:
            lines.append("Rating: FAIR - May need additional forming")
        else:
            lines.append("Rating: POOR - Not suitable for memristive applications")
        if is_forming:
            lines.append(f"Forming Detected: YES (improved {score_improvement:.1f} points)")
        lines.extend(["", "KEY SWEEPS", "-" * 80])
        if best_sweep:
            lines.append(f"Best Sweep: #{best_sweep['sweep']} @ {best_sweep['voltage']:.1f}V (Score: {best_sweep['score']:.1f})")
        if worst_sweep and worst_sweep["sweep"] != best_sweep["sweep"]:
            lines.append(f"Worst Sweep: #{worst_sweep['sweep']} @ {worst_sweep['voltage']:.1f}V (Score: {worst_sweep['score']:.1f})")
        lines.extend(["", "SWEEP-BY-SWEEP PROGRESSION", "-" * 80])
        for result in sequence_results:
            classification = result["analysis"].get("classification", {})
            score = classification.get("memristivity_score", 0)
            device_type = classification.get("device_type", "unknown")
            lines.append(f"Sweep #{result['sweep_number']:2d} @ {result['voltage']:4.1f}V: {device_type:12s} Score: {score:5.1f}/100")
        lines.extend(["", "DETAILED METRICS (Final Sweep)", "-" * 80])
        if sequence_results:
            final_analysis = sequence_results[-1]["analysis"]
            resistance = final_analysis.get("resistance_metrics", {})
            lines.extend([
                f"Ron (mean):  {resistance.get('ron_mean', 0):.2e} Ω",
                f"Roff (mean): {resistance.get('roff_mean', 0):.2e} Ω",
                f"Switching Ratio: {resistance.get('switching_ratio_mean', 0):.1f}",
                "",
            ])
            hysteresis = final_analysis.get("hysteresis_metrics", {})
            lines.extend([
                f"Hysteresis: {'Yes' if hysteresis.get('has_hysteresis') else 'No'}",
                f"Pinched: {'Yes' if hysteresis.get('pinched_hysteresis') else 'No'}",
                "",
            ])
            if "memory_window_quality" in final_classification:
                quality = final_classification["memory_window_quality"]
                lines.append(f"Memory Window Quality: {quality.get('overall_quality_score', 0):.1f}/100")
        lines.extend([
            "", "=" * 80,
            "NOTES FOR BATCH PROCESSING:",
            f"- Data Location: {save_dir}",
            f"- Device Tracking: {sample_save_dir}/sample_analysis/analysis/device_tracking/{device_id}_history.json",
            f"- Classification Summary: {save_dir}/classification_summary.txt (quick reference)",
            f"- Classification Log: {save_dir}/classification_log.txt (detailed)",
            "", "=" * 80,
        ])
        text_file = os.path.join(summary_dir, f"{device_id}_{sequence_name}_summary.txt")
        with open(text_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        def convert_types(obj: Any) -> Any:
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            if isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {key: convert_types(value) for key, value in obj.items()}
            if isinstance(obj, list):
                return [convert_types(item) for item in obj]
            return obj

        json_summary = {
            "device_id": device_id,
            "sequence_name": sequence_name,
            "timestamp": datetime.now().isoformat(),
            "total_sweeps": total_sweeps,
            "analyzed_sweeps": len(scores),
            "overall_score": float(overall_score),
            "final_device_type": final_device_type,
            "forming_detected": is_forming,
            "score_improvement": float(score_improvement) if score_improvement else 0,
            "best_sweep": best_sweep,
            "worst_sweep": worst_sweep,
            "sweep_progression": [
                {
                    "sweep_number": r["sweep_number"],
                    "voltage": r["voltage"],
                    "score": r["analysis"].get("classification", {}).get("memristivity_score", 0),
                    "device_type": r["analysis"].get("classification", {}).get("device_type", "unknown"),
                }
                for r in sequence_results
            ],
            "final_metrics": {
                "resistance": sequence_results[-1]["analysis"].get("resistance_metrics", {}) if sequence_results else {},
                "hysteresis": sequence_results[-1]["analysis"].get("hysteresis_metrics", {}) if sequence_results else {},
                "classification": final_classification,
            },
            "data_locations": {
                "raw_data": save_dir,
                "tracking": f"{sample_save_dir}/sample_analysis/analysis/device_tracking/{device_id}_history.json",
                "research": f"{save_dir}/sweep_analysis/" if overall_score > 60 else None,
                "classification_summary": f"{save_dir}/classification_summary.txt",
                "classification_log": f"{save_dir}/classification_log.txt",
            },
        }
        json_file = os.path.join(summary_dir, f"{device_id}_{sequence_name}_summary.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(convert_types(json_summary), f, indent=2, ensure_ascii=False)
        _debug_print(f"[SUMMARY] Sequence summary saved: {text_file}, {json_file}")
    except Exception as e:
        _debug_print(f"[SUMMARY ERROR] Failed to generate sequence summary: {e}")
        import traceback
        traceback.print_exc()


def refresh_stats_list(gui: Any) -> None:
    """Refresh list of tracked devices."""
    try:
        import tkinter as tk
        sample_name = gui.sample_name_var.get() if hasattr(gui, "sample_name_var") else ""
        if not sample_name:
            if hasattr(gui, "stats_text_widget"):
                gui.stats_text_widget.config(state=tk.NORMAL)
                gui.stats_text_widget.delete("1.0", tk.END)
                gui.stats_text_widget.insert(
                    "1.0",
                    "No sample selected.\n\nPlease select a sample in the Sample GUI first,\n"
                    "then run some measurements to track devices.\n\n"
                    "Device tracking data will appear here after\n"
                    "you complete measurements.",
                )
                gui.stats_text_widget.config(state=tk.DISABLED)
            print("[STATS] No sample name set - cannot load device tracking")
            return
        save_root = gui._get_sample_save_directory(sample_name)
        tracking_dir = os.path.join(save_root, "sample_analysis", "analysis", "device_tracking")
        legacy_tracking_dir = os.path.join(save_root, "sample_analysis", "device_tracking")
        old_legacy_tracking_dir = os.path.join(save_root, "device_tracking")
        devices = []
        for check_dir in [tracking_dir, legacy_tracking_dir, old_legacy_tracking_dir]:
            if os.path.exists(check_dir):
                for file in os.listdir(check_dir):
                    if file.endswith("_history.json"):
                        device_id = file.replace("_history.json", "")
                        if device_id not in devices:
                            devices.append(device_id)
                if devices:
                    break
        if hasattr(gui, "stats_device_combo"):
            gui.stats_device_combo["values"] = sorted(devices)
            if devices:
                if not gui.stats_device_var.get():
                    gui.stats_device_var.set(devices[0])
                update_stats_display(gui)
                print(f"[STATS] Found {len(devices)} tracked device(s)")
            else:
                gui.stats_device_var.set("")
                if hasattr(gui, "stats_text_widget"):
                    gui.stats_text_widget.config(state=tk.NORMAL)
                    gui.stats_text_widget.delete("1.0", tk.END)
                    gui.stats_text_widget.insert(
                        "1.0",
                        f"No device tracking data found for sample: {sample_name}\n\n"
                        "Run some measurements to start tracking devices.\n\n"
                        "After each measurement with analysis enabled,\n"
                        "device statistics will be saved to:\n"
                        f"{tracking_dir}\n\n"
                        "Then refresh this tab to see tracked devices.",
                    )
                    gui.stats_text_widget.config(state=tk.DISABLED)
                clear_stats_plots(gui)
                print(f"[STATS] No tracked devices found in {tracking_dir}")
    except Exception as e:
        print(f"[STATS] Error refreshing device list: {e}")
        import traceback
        traceback.print_exc()


def update_stats_display(gui: Any) -> None:
    """Display device tracking stats."""
    try:
        import tkinter as tk
        device_id = gui.stats_device_var.get()
        if not device_id:
            return
        sample_name = gui.sample_name_var.get() if hasattr(gui, "sample_name_var") else ""
        save_root = gui._get_sample_save_directory(sample_name)
        history_file = os.path.join(
            save_root, "sample_analysis", "analysis", "device_tracking", f"{device_id}_history.json"
        )
        if not os.path.exists(history_file):
            if hasattr(gui, "stats_text_widget"):
                gui.stats_text_widget.config(state=tk.NORMAL)
                gui.stats_text_widget.delete("1.0", tk.END)
                gui.stats_text_widget.insert("1.0", f"Device tracking file not found:\n{history_file}")
                gui.stats_text_widget.config(state=tk.DISABLED)
            return
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        lines = [f"{'='*80}", f"DEVICE STATISTICS: {device_id}", f"{'='*80}", ""]
        lines.append(f"Total Measurements: {history.get('total_measurements', 0)}")
        measurements = history.get("all_measurements", [])
        if len(measurements) >= 3:
            mem_scores, sw_ratios, rs_on, rs_off, vs = [], [], [], [], []
            for m in measurements:
                c = m.get("classification", {})
                if c.get("memristivity_score"):
                    mem_scores.append(c["memristivity_score"])
                r = m.get("resistance", {})
                if r.get("ron_mean"):
                    rs_on.append(r["ron_mean"])
                if r.get("roff_mean"):
                    rs_off.append(r["roff_mean"])
                if r.get("switching_ratio"):
                    sw_ratios.append(r["switching_ratio"])
                v = m.get("voltage", {})
                if v.get("max_voltage"):
                    vs.append(abs(v["max_voltage"]))
            forming_info = gui._analyze_forming_process(mem_scores, sw_ratios, rs_on, rs_off, vs)
            status = forming_info["status"]
            confidence = forming_info["confidence"]
            status_display = {
                "forming": "🔧 FORMING",
                "formed": "✓ FORMED",
                "degrading": "⚠ DEGRADING",
                "unstable": "⚠ UNSTABLE",
                "stable": "→ STABLE",
            }
            status_text = status_display.get(status, status.upper()) if status and isinstance(status, str) else "UNKNOWN"
            lines.append(f"Device Status: {status_text} ({confidence*100:.0f}% confidence)")
            if status == "forming":
                lines.append(f"Forming Progress: {forming_info['progress']}% complete")
            if forming_info["indicators"]:
                lines.append("Evidence:")
                for indicator in forming_info["indicators"]:
                    lines.append(f"  • {indicator}")
            lines.append("")
        created = history.get("created", "N/A")
        if created != "N/A":
            try:
                dt = datetime.fromisoformat(created)
                created = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        lines.append(f"First Measurement: {created}")
        last_updated = history.get("last_updated", "N/A")
        if last_updated != "N/A":
            try:
                dt = datetime.fromisoformat(last_updated)
                last_updated = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        lines.extend([f"Last Updated: {last_updated}", ""])
        measurements = history.get("measurements", [])
        if measurements:
            latest = measurements[-1]
            lines.extend(["LATEST MEASUREMENT", "-" * 80])
            timestamp = latest.get("timestamp", "N/A")
            if timestamp != "N/A":
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            lines.extend([f"Timestamp: {timestamp}", f"Cycle: {latest.get('cycle_number', 'N/A')}", ""])
            classification = latest.get("classification", {})
            lines.extend(["CLASSIFICATION", "-" * 40])
            device_type = classification.get("device_type") or "N/A"
            device_type_str = device_type.upper() if isinstance(device_type, str) else "N/A"
            lines.append(f"  Device Type: {device_type_str}")
            conf = classification.get("confidence")
            lines.append(f"  Confidence: {conf*100:.1f}%" if conf is not None else "  Confidence: N/A")
            score = classification.get("memristivity_score")
            if score is not None:
                score_str = f"{score:.1f}/100"
                if score >= 80:
                    score_str += " (Excellent)"
                elif score >= 60:
                    score_str += " (Good)"
                elif score >= 40:
                    score_str += " (Fair)"
                else:
                    score_str += " (Poor)"
            else:
                score_str = "N/A"
            lines.extend([
                f"  Memristivity Score: {score_str}",
                f"  Conduction: {classification.get('conduction_mechanism', 'N/A')}",
                "",
            ])
            resistance = latest.get("resistance", {})
            lines.extend(["RESISTANCE METRICS", "-" * 40])
            ron, roff = resistance.get("ron_mean"), resistance.get("roff_mean")
            if ron is not None:
                lines.append(f"  Ron (mean): {ron:.2e} Ω")
            if roff is not None:
                lines.append(f"  Roff (mean): {roff:.2e} Ω")
            if resistance.get("switching_ratio"):
                lines.append(f"  Switching Ratio: {resistance.get('switching_ratio', 0):.2f}")
            if resistance.get("on_off_ratio"):
                lines.append(f"  ON/OFF Ratio: {resistance.get('on_off_ratio', 0):.2f}")
            lines.append("")
            hysteresis = latest.get("hysteresis", {})
            if hysteresis:
                lines.extend([
                    "HYSTERESIS", "-" * 40,
                    f"  Has Hysteresis: {'Yes' if hysteresis.get('has_hysteresis') else 'No'}",
                    f"  Pinched: {'Yes' if hysteresis.get('pinched') else 'No'}",
                ])
                if hysteresis.get("normalized_area"):
                    lines.append(f"  Normalized Area: {hysteresis.get('normalized_area'):.3f}")
                lines.append("")
            quality = latest.get("quality", {})
            if quality and quality.get("memory_window_quality"):
                lines.extend([
                    "QUALITY METRICS", "-" * 40,
                    f"  Memory Window: {quality.get('memory_window_quality'):.1f}/100",
                ])
                if quality.get("stability"):
                    lines.append(f"  Stability: {quality.get('stability'):.1f}/100")
                lines.append("")
            if len(measurements) > 1:
                lines.extend(["TRENDS OVER TIME", "-" * 40, f"  Measurements: {len(measurements)}"])
                scores_list = [
                    m["classification"].get("memristivity_score")
                    for m in measurements
                    if m.get("classification", {}).get("memristivity_score") is not None
                ]
                if len(scores_list) > 1:
                    trend = "↓ declining" if scores_list[-1] < scores_list[0] * 0.9 else "→ stable"
                    if scores_list[-1] > scores_list[0] * 1.1:
                        trend = "↑ improving"
                    lines.append(f"  Memristivity: {scores_list[0]:.1f} → {scores_list[-1]:.1f} ({trend})")
                rons_list = [
                    m["resistance"].get("ron_mean")
                    for m in measurements
                    if m.get("resistance", {}).get("ron_mean") is not None
                ]
                if len(rons_list) > 1:
                    drift_pct = (rons_list[-1] - rons_list[0]) / (rons_list[0] + 1e-20) * 100
                    drift_str = f"{drift_pct:+.1f}%"
                    if abs(drift_pct) > 20:
                        drift_str += " (significant)"
                    lines.append(f"  Ron Drift: {drift_str}")
                types_list = [
                    m["classification"].get("device_type")
                    for m in measurements
                    if m.get("classification", {}).get("device_type")
                ]
                if len(set(types_list)) > 1:
                    lines.append(f"  ⚠ Classification changed: {types_list[0]} → {types_list[-1]}")
                lines.append("")
            warnings_list = latest.get("warnings", [])
            if warnings_list:
                lines.extend(["⚠ WARNINGS", "-" * 40])
                for i, warning in enumerate(warnings_list[:5], 1):
                    lines.append(f"  {i}. {warning}")
                if len(warnings_list) > 5:
                    lines.append(f"  ... and {len(warnings_list)-5} more")
                lines.append("")
            lines.extend(["DATA LOCATION", "-" * 40, f"  Tracking: {history_file}"])
            device_letter, device_num = device_id.rsplit("_", 1)
            research_dir = os.path.join(save_root, device_letter, device_num, "sweep_analysis")
            if os.path.exists(research_dir):
                research_files = [f for f in os.listdir(research_dir) if f.endswith("_research.json")]
                lines.append(f"  Research: {len(research_files)} file(s) in {research_dir}")
            classification_log = os.path.join(save_root, device_letter, device_num, "classification_log.txt")
            if os.path.exists(classification_log):
                lines.append(f"  Classification Log: {classification_log}")
        else:
            lines.append("No measurements recorded yet.")
        if hasattr(gui, "stats_text_widget"):
            gui.stats_text_widget.config(state=tk.NORMAL)
            gui.stats_text_widget.delete("1.0", tk.END)
            gui.stats_text_widget.insert("1.0", "\n".join(lines))
            gui.stats_text_widget.config(state=tk.DISABLED)
        update_stats_plots(gui, history, device_id)
    except Exception as e:
        print(f"[STATS] Error updating display: {e}")
        import traceback
        traceback.print_exc()
        if hasattr(gui, "stats_text_widget"):
            import tkinter as tk
            gui.stats_text_widget.config(state=tk.NORMAL)
            gui.stats_text_widget.delete("1.0", tk.END)
            gui.stats_text_widget.insert("1.0", f"Error loading device stats:\n\n{str(e)}\n\nCheck console for details.")
            gui.stats_text_widget.config(state=tk.DISABLED)


def update_stats_plots(gui: Any, history: Dict[str, Any], device_id: str) -> None:
    """Update trend plots for device tracking."""
    try:
        if not hasattr(gui, "stats_plot_figure") or not hasattr(gui, "stats_plot_canvas"):
            return
        measurements = history.get("measurements", [])
        if len(measurements) < 2:
            fig = gui.stats_plot_figure
            fig.clear()
            ax = fig.add_subplot(111)
            ax.text(
                0.5, 0.5,
                "Not enough data\nfor trend analysis\n\n(Need 2+ measurements)",
                ha="center", va="center", fontsize=14, color="gray",
            )
            ax.axis("off")
            gui.stats_plot_canvas.draw()
            return
        timestamps, memristivity_scores, rons, roffs = [], [], [], []
        switching_ratios, confidences, device_types, voltages = [], [], [], []
        for i, m in enumerate(measurements):
            timestamps.append(i + 1)
            classification = m.get("classification", {})
            score = classification.get("memristivity_score")
            if score is not None:
                memristivity_scores.append(score)
            conf = classification.get("confidence")
            if conf is not None:
                confidences.append(conf * 100)
            device_types.append(classification.get("device_type", "unknown"))
            resistance = m.get("resistance", {})
            ron = resistance.get("ron_mean")
            if ron is not None:
                rons.append(ron)
            roff = resistance.get("roff_mean")
            if roff is not None:
                roffs.append(roff)
            ratio = resistance.get("switching_ratio")
            if ratio is not None:
                switching_ratios.append(ratio)
            voltage_data = m.get("voltage", {})
            max_v = voltage_data.get("max_voltage", 0)
            voltages.append(abs(max_v) if max_v else 0)
        forming_status = gui._analyze_forming_process(
            memristivity_scores, switching_ratios, rons, roffs, voltages
        )
        fig = gui.stats_plot_figure
        fig.clear()
        status = forming_status["status"]
        status_colors = {
            "forming": "#2196F3", "formed": "#4CAF50", "degrading": "#F44336",
            "unstable": "#FF9800", "stable": "#9E9E9E",
            "insufficient_data": "#9E9E9E", "unknown": "#9E9E9E",
        }
        status_color = status_colors.get(status, "#000000")
        title_text = f"Device Evolution: {device_id}"
        if status not in ("insufficient_data", None) and status:
            confidence_pct = int(forming_status.get("confidence", 0) * 100)
            status_str = status.upper() if isinstance(status, str) else "UNKNOWN"
            title_text += f"  |  Status: {status_str} ({confidence_pct}%)"
        fig.suptitle(title_text, fontsize=11, fontweight="bold", color=status_color)
        gs = fig.add_gridspec(4, 1, hspace=0.4, left=0.15, right=0.95, top=0.93, bottom=0.05)
        if memristivity_scores:
            ax1 = fig.add_subplot(gs[0])
            ax1.plot(timestamps[: len(memristivity_scores)], memristivity_scores, "o-", color="#2196F3", linewidth=2, markersize=6)
            ax1.axhline(y=80, color="green", linestyle="--", alpha=0.3, label="Excellent")
            ax1.axhline(y=60, color="orange", linestyle="--", alpha=0.3, label="Good")
            ax1.axhline(y=40, color="red", linestyle="--", alpha=0.3, label="Poor")
            ax1.set_ylabel("Memristivity\nScore", fontsize=9)
            ax1.set_ylim(0, 105)
            ax1.grid(True, alpha=0.3)
            ax1.legend(loc="upper right", fontsize=7)
            ax1.tick_params(labelsize=8)
            if len(memristivity_scores) > 1:
                trend = memristivity_scores[-1] - memristivity_scores[0]
                if abs(trend) > 5:
                    if status == "forming" and trend > 0:
                        progress = forming_status["progress"]
                        ax1.text(0.02, 0.98, f"🔧 Forming: {progress}%", transform=ax1.transAxes, fontsize=9, color="blue", va="top", fontweight="bold")
                    elif status == "degrading" and trend < 0:
                        ax1.text(0.02, 0.98, f"⚠ ↓ {abs(trend):.1f}", transform=ax1.transAxes, fontsize=10, color="red", va="top", fontweight="bold")
                    else:
                        arrow = "↑" if trend > 0 else "↓"
                        color = "green" if trend > 0 else "orange"
                        ax1.text(0.02, 0.98, f"{arrow} {abs(trend):.1f}", transform=ax1.transAxes, fontsize=10, color=color, va="top", fontweight="bold")
        if rons and roffs:
            ax2 = fig.add_subplot(gs[1])
            x_ron, x_roff = timestamps[: len(rons)], timestamps[: len(roffs)]
            ax2.semilogy(x_ron, rons, "o-", color="#4CAF50", linewidth=2, markersize=6, label="Ron (ON)")
            ax2.semilogy(x_roff, roffs, "s-", color="#F44336", linewidth=2, markersize=6, label="Roff (OFF)")
            ax2.set_ylabel("Resistance\n(Ω)", fontsize=9)
            ax2.grid(True, alpha=0.3, which="both")
            ax2.legend(loc="upper right", fontsize=7)
            ax2.tick_params(labelsize=8)
            if len(rons) > 1:
                ron_drift = (rons[-1] - rons[0]) / (rons[0] + 1e-20) * 100
                if abs(ron_drift) > 10 and status != "forming":
                    arrow = "↑" if ron_drift > 0 else "↓"
                    color = "red" if abs(ron_drift) > 20 else "orange"
                    warning = "⚠ " if abs(ron_drift) > 20 else ""
                    ax2.text(0.02, 0.98, f"{warning}Ron {arrow} {abs(ron_drift):.0f}%", transform=ax2.transAxes, fontsize=9, color=color, va="top", fontweight="bold")
                elif status == "forming":
                    ax2.text(0.02, 0.98, "🔧 Forming", transform=ax2.transAxes, fontsize=9, color="blue", va="top", fontweight="bold")
        if switching_ratios:
            ax3 = fig.add_subplot(gs[2])
            ax3.plot(timestamps[: len(switching_ratios)], switching_ratios, "o-", color="#9C27B0", linewidth=2, markersize=6)
            ax3.set_ylabel("Switching\nRatio", fontsize=9)
            ax3.grid(True, alpha=0.3)
            ax3.tick_params(labelsize=8)
            mean_ratio = np.mean(switching_ratios)
            ax3.axhline(y=mean_ratio, color="gray", linestyle="--", alpha=0.5, label=f"Mean: {mean_ratio:.1f}")
            ax3.legend(loc="upper right", fontsize=7)
            if len(switching_ratios) > 1:
                ratio_change = (switching_ratios[-1] - switching_ratios[0]) / (switching_ratios[0] + 1e-20) * 100
                if status == "forming" and ratio_change > 10:
                    ax3.text(0.02, 0.98, f"🔧 Improving (+{ratio_change:.0f}%)", transform=ax3.transAxes, fontsize=9, color="blue", va="top", fontweight="bold")
                elif status == "degrading" and ratio_change < -20:
                    ax3.text(0.02, 0.98, f"⚠ Degrading ({ratio_change:.0f}%)", transform=ax3.transAxes, fontsize=9, color="red", va="top", fontweight="bold")
                elif ratio_change < -20 and status != "forming":
                    ax3.text(0.02, 0.98, f"⚠ Declining ({ratio_change:.0f}%)", transform=ax3.transAxes, fontsize=9, color="orange", va="top", fontweight="bold")
        if confidences:
            ax4 = fig.add_subplot(gs[3])
            ax4.plot(timestamps[: len(confidences)], confidences, "o-", color="#FF9800", linewidth=2, markersize=6)
            ax4.set_ylabel("Confidence\n(%)", fontsize=9)
            ax4.set_xlabel("Measurement #", fontsize=9)
            ax4.set_ylim(0, 105)
            ax4.grid(True, alpha=0.3)
            ax4.tick_params(labelsize=8)
            for i in range(1, len(device_types)):
                if device_types[i] != device_types[i - 1]:
                    ax4.axvline(x=timestamps[i], color="red", linestyle=":", alpha=0.5)
                    ax4.text(timestamps[i], 5, "Type\nChanged", rotation=90, fontsize=7, color="red", va="bottom")
        gui.stats_plot_canvas.draw()
    except Exception as e:
        print(f"[STATS] Error updating plots: {e}")
        import traceback
        traceback.print_exc()


def plot_all_device_graphs(gui: Any) -> None:
    """Plot all graphs for all measurement files in the currently selected device."""
    try:
        if not hasattr(gui, "sample_name_var") or not gui.sample_name_var.get():
            messagebox.showwarning("No Sample Selected", "Please select a sample name first.")
            return
        if not hasattr(gui, "final_device_letter") or not hasattr(gui, "final_device_number"):
            messagebox.showwarning("No Device Selected", "Please select a device (letter and number) first.")
            return
        sample_name = gui.sample_name_var.get()
        device_letter = gui.final_device_letter
        device_number = gui.final_device_number
        device_name = f"{device_letter}{device_number}"
        device_dir = gui._get_save_directory(sample_name, device_letter, device_number)
        if not os.path.exists(device_dir):
            messagebox.showerror("Directory Not Found", f"Device directory not found:\n{device_dir}")
            return
        # Exclude known non-measurement .txt files (logs, classification outputs)
        EXCLUDE_TXT = frozenset(
            {"log.txt", "classification_log.txt", "classification_summary.txt"}
        )
        txt_files = sorted(
            [
                f
                for f in os.listdir(device_dir)
                if f.endswith(".txt") and f not in EXCLUDE_TXT
            ]
        )
        if not txt_files:
            messagebox.showinfo("No Files Found", f"No measurement files (.txt) found in:\n{device_dir}")
            return
        response = messagebox.askyesno(
            "Plot All Device Graphs",
            f"Found {len(txt_files)} measurement file(s) for device {device_name}.\n\n"
            "This will:\n• Load each measurement file\n• Run analysis to determine if memristive\n"
            "• Plot dashboard graphs (all files)\n• Plot endurance graphs (endurance files)\n"
            "• Plot retention graphs (retention files)\n• Plot DC endurance graphs (if ≥10 sweeps detected)\n"
            "• Plot conduction & SCLC graphs (memristive files only)\n\nContinue?",
        )
        if not response:
            return
        if hasattr(gui, "analysis_status_label"):
            gui.analysis_status_label.config(text=f"Plotting graphs for {len(txt_files)} file(s)...", fg="#2196F3")
            gui.master.update()

        def run_plotting() -> None:
            try:
                from analysis import quick_analyze
                from plotting import UnifiedPlotter
                from analysis.aggregators.dc_endurance_analyzer import DCEnduranceAnalyzer
                from plotting import UnifiedPlotter as UP

                import matplotlib
                matplotlib.use("Agg")
                success_count, error_count = 0, 0
                all_voltage_data, all_current_data = [], []
                dc_endurance_filename = None
                for idx, txt_file in enumerate(txt_files, 1):
                    try:
                        file_path = os.path.join(device_dir, txt_file)
                        filename = os.path.splitext(txt_file)[0]
                        print(f"[DEVICE PLOT] Processing {idx}/{len(txt_files)}: {txt_file}")
                        if hasattr(gui, "analysis_status_label"):
                            gui.master.after(
                                0,
                                lambda t=f"Plotting {idx}/{len(txt_files)}: {txt_file[:40]}...": gui.analysis_status_label.config(text=t, fg="#2196F3"),
                            )
                        try:
                            data = np.loadtxt(file_path, skiprows=1, ndmin=2)
                            if data.ndim < 2 or data.shape[1] < 2:
                                error_count += 1
                                continue
                            voltage = data[:, 0]
                            current = data[:, 1]
                            timestamps = data[:, 2] if data.shape[1] > 2 else None
                        except (ValueError, IndexError, OSError) as e:
                            print(f"[DEVICE PLOT] Skip (not measurement data): {txt_file} — {e}")
                            error_count += 1
                            continue
                        except Exception as e:
                            print(f"[DEVICE PLOT] Error loading {txt_file}: {e}")
                            error_count += 1
                            continue
                        try:
                            analysis_data = quick_analyze(
                                voltage=list(voltage),
                                current=list(current),
                                time=list(timestamps) if timestamps is not None else None,
                                analysis_level="full",
                            )
                            classification = analysis_data.get("classification", {})
                            device_type = classification.get("device_type", "")
                            raw_score = classification.get("memristivity_score")
                            memristivity_score = float(raw_score) if raw_score is not None else 0.0
                            is_memristive = (
                                device_type in ["memristive", "memcapacitive"]
                                or memristivity_score > 60
                            )
                        except Exception as e:
                            print(f"[DEVICE PLOT] Analysis error for {txt_file}: {e}")
                            is_memristive = False
                        measurement_type = "IV"
                        measurement_params = {}
                        filename_upper = txt_file.upper()
                        if "ENDURANCE" in filename_upper:
                            measurement_type = "Endurance"
                            measurement_params = {"read_v": 0.2, "read_voltage": 0.2}
                        elif "RETENTION" in filename_upper:
                            measurement_type = "Retention"
                            measurement_params = {"read_v": 0.2, "read_voltage": 0.2}
                        if measurement_type != "Endurance":
                            sweeps_in_file = UP._detect_sweeps_by_zero_crossings(voltage, current)
                            if len(sweeps_in_file) >= 10:
                                try:
                                    split_v_data = [voltage[s:e] for s, e in sweeps_in_file]
                                    split_c_data = [current[s:e] for s, e in sweeps_in_file]
                                    analyzer = DCEnduranceAnalyzer(
                                        split_voltage_data=split_v_data,
                                        split_current_data=split_c_data,
                                        file_name=filename,
                                        device_path=device_dir,
                                    )
                                    analyzer.analyze_and_plot()
                                except Exception as e:
                                    print(f"[DEVICE PLOT] DC endurance error for {txt_file}: {e}")
                                    import traceback
                                    traceback.print_exc()
                            else:
                                all_voltage_data.append(voltage)
                                all_current_data.append(current)
                                if dc_endurance_filename is None:
                                    dc_endurance_filename = filename
                        # Progress: explain what we're plotting so user knows why it may pause
                        plot_desc = measurement_type
                        if measurement_type == "IV":
                            plot_desc = "IV dashboard" + (
                                " + conduction + SCLC (memristive)"
                                if is_memristive
                                else ""
                            )
                        print(
                            f"[DEVICE PLOT] Plotting {plot_desc} for {txt_file} — may take a moment for multi-sweep files."
                        )
                        if hasattr(gui, "analysis_status_label"):
                            gui.master.after(
                                0,
                                lambda t=f"Plotting {idx}/{len(txt_files)}: {plot_desc}...": gui.analysis_status_label.config(text=t, fg="#2196F3"),
                            )
                        try:
                            plot_measurement_in_background(
                                gui, voltage, current, timestamps,
                                save_dir=device_dir, device_name=device_name,
                                sweep_number=idx, is_memristive=is_memristive,
                                filename=filename, measurement_type=measurement_type,
                                measurement_params=measurement_params,
                            )
                            success_count += 1
                        except Exception as e:
                            print(f"[DEVICE PLOT] Plotting error for {txt_file}: {e}")
                            error_count += 1
                    except Exception as e:
                        print(f"[DEVICE PLOT] Unexpected error processing {txt_file}: {e}")
                        error_count += 1
                if len(all_voltage_data) >= 10 and len(all_voltage_data) == len(all_current_data):
                    try:
                        endurance_filename = dc_endurance_filename or device_name
                        analyzer = DCEnduranceAnalyzer(
                            split_voltage_data=all_voltage_data,
                            split_current_data=all_current_data,
                            file_name=endurance_filename,
                            device_path=device_dir,
                        )
                        analyzer.analyze_and_plot()
                    except Exception as e:
                        print(f"[DEVICE PLOT] DC endurance analysis error: {e}")
                        import traceback
                        traceback.print_exc()
                elif len(all_voltage_data) > 0:
                    try:
                        combined_voltage = np.concatenate(all_voltage_data)
                        combined_current = np.concatenate(all_current_data)
                        sweeps = UP._detect_sweeps_by_zero_crossings(combined_voltage, combined_current)
                        if len(sweeps) >= 10:
                            split_v_data = [combined_voltage[s:e] for s, e in sweeps]
                            split_c_data = [combined_current[s:e] for s, e in sweeps]
                            endurance_filename = dc_endurance_filename or device_name
                            analyzer = DCEnduranceAnalyzer(
                                split_voltage_data=split_v_data,
                                split_current_data=split_c_data,
                                file_name=endurance_filename,
                                device_path=device_dir,
                            )
                            analyzer.analyze_and_plot()
                    except Exception as e:
                        print(f"[DEVICE PLOT] DC endurance detection error: {e}")
                if hasattr(gui, "analysis_status_label"):
                    status_text = f"Completed: {success_count} plotted, {error_count} errors"
                    gui.analysis_status_label.config(
                        text=status_text,
                        fg="#4CAF50" if error_count == 0 else "#FF9800",
                    )
                messagebox.showinfo(
                    "Plotting Complete",
                    f"Finished plotting graphs for device {device_name}.\n\n"
                    f"Success: {success_count} file(s)\nErrors: {error_count} file(s)\n\n"
                    f"Graphs saved to:\n{os.path.join(device_dir, 'Graphs')}",
                )
            except Exception as e:
                print(f"[DEVICE PLOT] Fatal error: {e}")
                import traceback
                traceback.print_exc()
                if hasattr(gui, "analysis_status_label"):
                    gui.analysis_status_label.config(text=f"Error: {str(e)}", fg="#F44336")
                messagebox.showerror("Plotting Error", f"Error during plotting:\n{str(e)}")

        threading.Thread(target=run_plotting, daemon=True).start()
    except Exception as e:
        print(f"[DEVICE PLOT] Error: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error", f"Failed to start plotting:\n{str(e)}")


_EXCLUDE_TXT = {"log.txt", "classification_log.txt", "classification_summary.txt"}

# Top-level dirs under base path that are not sample folders
_NON_SAMPLE_DIRS = frozenset({"Multiplexer_Avg_Measure"})


def get_discovered_sample_names(gui: Any) -> List[str]:
    """
    Discover sample folder names under the GUI's data save base path.
    Returns sorted list of names; only includes dirs that look like samples
    (optional: have at least one section/device subtree).
    """
    base = getattr(gui, "_get_base_save_path", None)
    if not base or not callable(base):
        return []
    base_path = Path(base())
    if not base_path.is_dir():
        return []
    names = []
    for item in base_path.iterdir():
        if not item.is_dir() or item.name in _NON_SAMPLE_DIRS:
            continue
        # Optional: only include if it has at least one section/device (letter/digit)
        has_devices = False
        for sub in item.iterdir():
            if sub.is_dir() and len(sub.name) == 1 and sub.name.isalpha():
                for subsub in sub.iterdir():
                    if subsub.is_dir() and subsub.name.isdigit():
                        has_devices = True
                        break
            if has_devices:
                break
        if has_devices:
            names.append(item.name)
    return sorted(names)


def _run_plot_all_sample_graphs_for_dir(
    gui: Any,
    sample_dir: str,
    sample_name: str,
    status_callback: Optional[Callable[[str, str], None]] = None,
) -> tuple[int, int]:
    """
    Run plot-all-sample-graphs logic for one sample directory.
    Returns (processed_devices, total_success). Call from background thread.
    """
    from analysis import quick_analyze
    from plotting import UnifiedPlotter
    from analysis.aggregators.dc_endurance_analyzer import DCEnduranceAnalyzer
    from plotting import UnifiedPlotter as UP
    import matplotlib
    matplotlib.use("Agg")

    def _status(msg: str, fg: str = "#2196F3") -> None:
        if status_callback:
            status_callback(msg, fg)
        elif hasattr(gui, "analysis_status_label"):
            gui.master.after(0, lambda m=msg, c=fg: gui.analysis_status_label.config(text=m, fg=c))

    device_dirs: List[tuple] = []
    for item in os.listdir(sample_dir):
        section_path = os.path.join(sample_dir, item)
        if os.path.isdir(section_path) and len(item) == 1 and item.isalpha():
            for subitem in os.listdir(section_path):
                device_path = os.path.join(section_path, subitem)
                if os.path.isdir(device_path) and subitem.isdigit():
                    device_dirs.append((item, subitem, device_path))

    if not device_dirs:
        return 0, 0

    processed_devices, total_success = 0, 0
    for section, device_num, device_dir in device_dirs:
        processed_devices += 1
        _status(f"Processing {section}{device_num} ({processed_devices}/{len(device_dirs)})...")
        device_voltage_data, device_current_data = [], []
        dc_endurance_filename = None
        txt_files = [
            f for f in os.listdir(device_dir)
            if f.endswith(".txt") and f not in _EXCLUDE_TXT
        ]
        for txt_file in txt_files:
            try:
                file_path = os.path.join(device_dir, txt_file)
                try:
                    data = np.loadtxt(file_path, skiprows=1, ndmin=2)
                    if data.ndim < 2 or data.shape[1] < 2:
                        continue
                    voltage, current = data[:, 0], data[:, 1]
                    timestamps = data[:, 2] if data.shape[1] > 2 else None
                except (ValueError, IndexError, OSError):
                    continue
                analysis_data = quick_analyze(
                    voltage=list(voltage),
                    current=list(current),
                    time=list(timestamps) if timestamps is not None else None,
                    analysis_level="full",
                )
                classification = analysis_data.get("classification", {})
                device_type = classification.get("device_type", "")
                raw_score = classification.get("memristivity_score")
                memristivity_score = float(raw_score) if raw_score is not None else 0.0
                is_memristive = (
                    device_type in ["memristive", "memcapacitive"]
                    or memristivity_score > 60
                )
                measurement_type = "IV"
                measurement_params = {}
                if "ENDURANCE" in txt_file.upper():
                    measurement_type = "Endurance"
                    measurement_params = {"read_v": 0.2, "read_voltage": 0.2}
                elif "RETENTION" in txt_file.upper():
                    measurement_type = "Retention"
                    measurement_params = {"read_v": 0.2, "read_voltage": 0.2}
                graphs_dir = os.path.join(device_dir, "Graphs")
                os.makedirs(graphs_dir, exist_ok=True)
                filename_base = os.path.splitext(txt_file)[0]
                sample_name_str = sample_name or ""
                title_prefix = f"{sample_name_str} {section}{device_num}".strip()
                plotter = UnifiedPlotter(save_dir=graphs_dir, auto_close=True)
                if measurement_type != "Endurance":
                    sweeps_in_file = UP._detect_sweeps_by_zero_crossings(voltage, current)
                    if len(sweeps_in_file) >= 10:
                        try:
                            split_v_data = [voltage[s:e] for s, e in sweeps_in_file]
                            split_c_data = [current[s:e] for s, e in sweeps_in_file]
                            analyzer = DCEnduranceAnalyzer(
                                split_voltage_data=split_v_data,
                                split_current_data=split_c_data,
                                file_name=filename_base,
                                device_path=device_dir,
                            )
                            analyzer.analyze_and_plot()
                        except Exception as e:
                            print(f"[SAMPLE PLOT] DC endurance error for {txt_file}: {e}")
                    else:
                        device_voltage_data.append(voltage)
                        device_current_data.append(current)
                        if dc_endurance_filename is None:
                            dc_endurance_filename = filename_base
                if measurement_type == "Endurance":
                    plotter.plot_endurance_analysis(
                        voltage=voltage, current=current, timestamps=timestamps,
                        device_name=filename_base, title_prefix=title_prefix,
                        read_voltage=measurement_params.get("read_v", 0.2),
                        save_name_cycle_resistance=f"{filename_base}_endurance_cycle_resistance.png",
                        save_name_onoff_ratio=f"{filename_base}_endurance_onoff_ratio.png",
                    )
                elif measurement_type == "Retention":
                    plotter.plot_retention_analysis(
                        voltage=voltage, current=current, timestamps=timestamps,
                        device_name=filename_base, title_prefix=title_prefix,
                        read_voltage=measurement_params.get("read_v", 0.2),
                        save_name_loglog=f"{filename_base}_retention_loglog.png",
                        save_name_linear=f"{filename_base}_retention_linear.png",
                        save_name_resistance=f"{filename_base}_retention_resistance.png",
                    )
                else:
                    plot_title = f"{title_prefix} {filename_base} - IV Dashboard".strip()
                    plotter.plot_iv_dashboard(
                        voltage=voltage, current=current, time=timestamps,
                        device_name=filename_base, title=plot_title,
                        save_name=f"{filename_base}_iv_dashboard.png",
                        sample_name=sample_name_str,
                        section=section or "",
                        device_num=device_num or "",
                    )
                    try:
                        conduction_dir = os.path.join(graphs_dir, "conduction")
                        sclc_dir = os.path.join(graphs_dir, "sclc_fit")
                        os.makedirs(conduction_dir, exist_ok=True)
                        os.makedirs(sclc_dir, exist_ok=True)
                        plotter_cond = UnifiedPlotter(save_dir=conduction_dir, auto_close=True)
                        plotter_cond.plot_conduction_analysis(
                            voltage=voltage, current=current,
                            device_name=filename_base,
                            title=f"{title_prefix} {filename_base} - Conduction Analysis",
                            save_name=f"{filename_base}_conduction.png",
                        )
                        plotter_sclc = UnifiedPlotter(save_dir=sclc_dir, auto_close=True)
                        plotter_sclc.plot_sclc_fit(
                            voltage=voltage, current=current,
                            device_name=filename_base,
                            title=f"{title_prefix} {filename_base} - SCLC Fit",
                            save_name=f"{filename_base}_sclc_fit.png",
                        )
                    except Exception as e:
                        print(f"[SAMPLE PLOT] Error plotting conduction/SCLC for {txt_file}: {e}")
                total_success += 1
            except Exception as e:
                print(f"Error processing {txt_file}: {e}")
        if len(device_voltage_data) >= 10 and len(device_voltage_data) == len(device_current_data):
            try:
                endurance_filename = dc_endurance_filename or f"{section}{device_num}"
                analyzer = DCEnduranceAnalyzer(
                    split_voltage_data=device_voltage_data,
                    split_current_data=device_current_data,
                    file_name=endurance_filename,
                    device_path=device_dir,
                )
                analyzer.analyze_and_plot()
            except Exception as e:
                print(f"[SAMPLE PLOT] DC endurance analysis error for {section}{device_num}: {e}")
        elif len(device_voltage_data) > 0:
            try:
                combined_voltage = np.concatenate(device_voltage_data)
                combined_current = np.concatenate(device_current_data)
                sweeps = UP._detect_sweeps_by_zero_crossings(combined_voltage, combined_current)
                if len(sweeps) >= 10:
                    split_v_data = [combined_voltage[s:e] for s, e in sweeps]
                    split_c_data = [combined_current[s:e] for s, e in sweeps]
                    endurance_filename = dc_endurance_filename or f"{section}{device_num}"
                    analyzer = DCEnduranceAnalyzer(
                        split_voltage_data=split_v_data,
                        split_current_data=split_c_data,
                        file_name=endurance_filename,
                        device_path=device_dir,
                    )
                    analyzer.analyze_and_plot()
            except Exception as e:
                print(f"[SAMPLE PLOT] DC endurance detection error for {section}{device_num}: {e}")
    return processed_devices, total_success


def plot_all_sample_graphs(gui: Any) -> None:
    """Plot all graphs for ALL devices in the selected sample directory."""
    try:
        sample_dir, sample_name = None, None
        if hasattr(gui, "analysis_folder_var"):
            selected_folder = gui.analysis_folder_var.get()
            if selected_folder and selected_folder != "(Use current sample)":
                if os.path.exists(selected_folder):
                    sample_dir = selected_folder
                    sample_name = os.path.basename(selected_folder)
                else:
                    messagebox.showerror("Error", f"Selected folder not found: {selected_folder}")
                    return
        if not sample_dir:
            sample_name = gui.sample_name_var.get() if hasattr(gui, "sample_name_var") else None
            if not sample_name:
                messagebox.showwarning("No Sample", "Please select a sample first.")
                return
            sample_dir = gui._get_sample_save_directory(sample_name)
        if not os.path.exists(sample_dir):
            messagebox.showerror("Error", f"Sample directory not found: {sample_dir}")
            return
        device_dirs = []
        for item in os.listdir(sample_dir):
            section_path = os.path.join(sample_dir, item)
            if os.path.isdir(section_path) and len(item) == 1 and item.isalpha():
                for subitem in os.listdir(section_path):
                    device_path = os.path.join(section_path, subitem)
                    if os.path.isdir(device_path) and subitem.isdigit():
                        device_dirs.append((item, subitem, device_path))
        if not device_dirs:
            messagebox.showinfo("No Devices", f"No device folders found in {sample_dir}")
            return
        total_files = sum(
            len([f for f in os.listdir(d[2]) if f.endswith(".txt") and f not in _EXCLUDE_TXT])
            for d in device_dirs
        )
        response = messagebox.askyesno(
            "Plot All Sample Graphs",
            f"Found {len(device_dirs)} devices with ~{total_files} measurement files.\n\n"
            f"This will generate dashboard plots for EVERY device in sample '{sample_name}'.\n"
            "This process may take some time.\n\nContinue?",
        )
        if not response:
            return
        if hasattr(gui, "analysis_status_label"):
            gui.analysis_status_label.config(text="Starting sample-wide plotting...", fg="#2196F3")
            gui.master.update()

        def run_sample_plotting() -> None:
            try:
                _devices, _success = _run_plot_all_sample_graphs_for_dir(
                    gui, sample_dir, sample_name or ""
                )
                msg = f"Completed! Generated plots for {_devices} devices ({_success} files)."
                gui.master.after(0, lambda: messagebox.showinfo("Done", msg))
                gui.master.after(0, lambda: gui.analysis_status_label.config(text=msg, fg="#4CAF50"))
            except Exception as e:
                gui.master.after(0, lambda: gui.analysis_status_label.config(text=f"Error: {e}", fg="#F44336"))

        threading.Thread(target=run_sample_plotting, daemon=True).start()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start plotting: {e}")


def plot_all_sample_graphs_batch(
    gui: Any,
    sample_names: List[str],
    base_path: str,
) -> None:
    """Run plot-all-sample-graphs for each selected sample in a single background thread."""
    def run_batch() -> None:
        total_devices, total_files = 0, 0
        n = len(sample_names)

        def status_cb(msg: str, fg: str = "#2196F3") -> None:
            if hasattr(gui, "analysis_status_label"):
                gui.master.after(0, lambda m=msg, c=fg: gui.analysis_status_label.config(text=m, fg=c))

        try:
            for idx, name in enumerate(sample_names, 1):
                sample_dir = os.path.join(base_path, name)
                if not os.path.isdir(sample_dir):
                    status_cb(f"Skipping {name} (not a directory)", fg="#FF9800")
                    continue
                status_cb(f"Sample {idx}/{n}: {name}...", fg="#2196F3")
                devs, success = _run_plot_all_sample_graphs_for_dir(
                    gui, sample_dir, name, status_callback=status_cb
                )
                total_devices += devs
                total_files += success
            msg = f"Completed! {n} sample(s), {total_devices} devices, {total_files} files plotted."
            gui.master.after(0, lambda: messagebox.showinfo("Batch plotting complete", msg))
            gui.master.after(0, lambda: gui.analysis_status_label.config(text=msg, fg="#4CAF50"))
        except Exception as e:
            gui.master.after(0, lambda: gui.analysis_status_label.config(text=f"Error: {e}", fg="#F44336"))
            gui.master.after(0, lambda: messagebox.showerror("Batch plotting error", str(e)))

    threading.Thread(target=run_batch, daemon=True).start()


def run_full_sample_analysis(gui: Any) -> None:
    """Run comprehensive sample analysis with all plots and data exports."""
    try:
        import subprocess
        sample_dir, sample_name = None, None
        if hasattr(gui, "analysis_folder_var"):
            selected_folder = gui.analysis_folder_var.get()
            if selected_folder and selected_folder != "(Use current sample)":
                if os.path.exists(selected_folder):
                    sample_dir = selected_folder
                    sample_name = os.path.basename(selected_folder)
                else:
                    messagebox.showerror("Error", f"Selected folder not found: {selected_folder}")
                    return
        if not sample_dir:
            sample_name = gui.sample_name_var.get() if hasattr(gui, "sample_name_var") else None
            if not sample_name:
                messagebox.showwarning(
                    "No Sample",
                    "Please either:\n1. Select a sample in the GUI, OR\n2. Click 'Browse...' to select a sample folder",
                )
                return
            sample_dir = gui._get_sample_save_directory(sample_name)
        if not os.path.exists(sample_dir):
            messagebox.showerror("Error", f"Sample directory not found: {sample_dir}")
            return
        if hasattr(gui, "analysis_status_label"):
            gui.analysis_status_label.config(text="Checking for existing analysis data...")
            gui.master.update_idletasks()

        def log_to_terminal(message: str) -> None:
            if hasattr(gui, "plot_panels") and gui.plot_panels:
                gui.plot_panels.log_graph_activity(message)
            if hasattr(gui, "analysis_status_label"):
                gui.analysis_status_label.config(text=message)
                gui.master.update_idletasks()

        print(f"[SAMPLE ANALYSIS] Starting analysis for: {sample_name or os.path.basename(sample_dir)}")
        log_to_terminal(f"Starting analysis for: {sample_name or os.path.basename(sample_dir)}")
        tracking_dir = os.path.join(sample_dir, "sample_analysis", "analysis", "device_tracking")
        legacy_tracking_dir = os.path.join(sample_dir, "sample_analysis", "device_tracking")
        old_legacy_tracking_dir = os.path.join(sample_dir, "device_tracking")
        has_tracking = (
            (os.path.exists(tracking_dir) and os.listdir(tracking_dir))
            or (os.path.exists(legacy_tracking_dir) and os.listdir(legacy_tracking_dir))
            or (os.path.exists(old_legacy_tracking_dir) and os.listdir(old_legacy_tracking_dir))
        )
        if not has_tracking:
            if hasattr(gui, "analysis_status_label"):
                gui.analysis_status_label.config(text="Running retroactive analysis on raw data...")
                gui.master.update_idletasks()
            log_to_terminal("No tracking data found - analyzing raw measurement files...")
            analyzed_count = gui._run_retroactive_analysis(
                sample_dir, sample_name or os.path.basename(sample_dir), log_callback=log_to_terminal
            )
            if analyzed_count == 0:
                messagebox.showwarning(
                    "No Data",
                    "No measurement files found to analyze.\n\n"
                    "Expected device subfolders (letter/number) containing .txt files.",
                )
                if hasattr(gui, "analysis_status_label"):
                    gui.analysis_status_label.config(text="✗ No data found")
                return
            print(f"[RETROACTIVE] Analyzed {analyzed_count} measurement files")
        if hasattr(gui, "analysis_status_label"):
            gui.analysis_status_label.config(text="Loading device data...")
            gui.master.update_idletasks()
        from analysis import ComprehensiveAnalyzer
        if hasattr(gui, "analysis_status_label"):
            gui.analysis_status_label.config(text="Running comprehensive analysis (all code_names)...")
            gui.master.update_idletasks()
        comprehensive = ComprehensiveAnalyzer(sample_dir)
        comprehensive.set_log_callback(log_to_terminal)
        comprehensive.run_comprehensive_analysis()
        device_count = 0
        if os.path.exists(tracking_dir):
            device_count = len([f for f in os.listdir(tracking_dir) if f.endswith("_history.json")])
        elif os.path.exists(legacy_tracking_dir):
            device_count = len([f for f in os.listdir(legacy_tracking_dir) if f.endswith("_history.json")])
        elif os.path.exists(old_legacy_tracking_dir):
            device_count = len([f for f in os.listdir(old_legacy_tracking_dir) if f.endswith("_history.json")])
        output_dir = os.path.join(sample_dir, "sample_analysis")
        messagebox.showinfo(
            "Comprehensive Analysis Complete",
            f"Comprehensive analysis complete!\n\nDevices analyzed: {device_count}\n"
            f"Code names processed: {len(comprehensive.discovered_code_names)}\n"
            f"Output: {output_dir}\n\nGenerated:\n• Device-level combined sweep plots\n"
            "• Sample-level analysis for each code_name\n• Overall sample analysis\n"
            "• Origin-ready data exports\n\nCheck the output folders for all results.",
        )
        if hasattr(gui, "analysis_status_label"):
            gui.analysis_status_label.config(
                text=f"✓ Complete - {device_count} devices, {len(comprehensive.discovered_code_names)} code_names"
            )
        print(f"[COMPREHENSIVE ANALYSIS] Complete! Output: {output_dir}")
        try:
            subprocess.Popen(f'explorer "{output_dir}"')
        except Exception:
            pass
    except Exception as e:
        error_msg = f"Sample analysis failed: {e}"
        print(f"[SAMPLE ANALYSIS ERROR] {error_msg}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Analysis Error", error_msg)
        if hasattr(gui, "analysis_status_label"):
            gui.analysis_status_label.config(text=f"✗ Error: {e}")
