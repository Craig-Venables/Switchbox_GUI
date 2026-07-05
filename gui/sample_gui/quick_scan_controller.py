"""
Quick-scan workflow for SampleGUI: measurement, overlays, and persistence.
"""

from __future__ import annotations

import csv
import json
import math
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
from tkinter import messagebox

from gui.sample_gui.config import resolve_default_save_root

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI

try:
    from Equipment.SMU_AND_PMU import Keithley2400Controller
except Exception:
    Keithley2400Controller = None  # type: ignore[misc, assignment]


class QuickScanController:
    """Quick scan execution, visualization, and file I/O."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui

    # ------------------------------------------------------------------
    # Color / overlay helpers
    # ------------------------------------------------------------------
    def update_background(self, image: Image.Image) -> None:
        gui = self.gui
        if not hasattr(gui, "quick_scan_canvas") or gui.quick_scan_canvas is None:
            return
        gui.quick_scan_canvas.delete("all")
        quick_scan_img = image.resize((600, 500))
        gui.quick_scan_base_image = quick_scan_img.copy()
        gui.quick_scan_canvas_image = ImageTk.PhotoImage(gui.quick_scan_base_image)
        gui.quick_scan_canvas.create_image(0, 0, anchor="nw", image=gui.quick_scan_canvas_image)
        self.redraw_overlay()

    def current_to_color(self, current_a: float) -> str:
        gui = self.gui
        min_i = max(gui.quick_scan_min_current, 1e-20)
        max_i = max(gui.quick_scan_max_current, min_i * 10)
        log_min = math.log10(min_i)
        log_max = math.log10(max_i)
        denom = log_max - log_min if log_max != log_min else 1e-9
        if current_a <= 0:
            ratio = 0.0
        else:
            ratio = (math.log10(max(current_a, min_i)) - log_min) / denom
        ratio = max(0.0, min(1.0, ratio))
        if ratio <= 0.5:
            local = ratio / 0.5
            start = (255, 0, 0)
            end = (255, 140, 0)
        else:
            local = (ratio - 0.5) / 0.5
            start = (255, 140, 0)
            end = (0, 255, 0)
        r = int(start[0] + (end[0] - start[0]) * local)
        g = int(start[1] + (end[1] - start[1]) * local)
        b = int(start[2] + (end[2] - start[2]) * local)
        return f"#{r:02x}{g:02x}{b:02x}"

    def redraw_overlay(self) -> None:
        gui = self.gui
        self._draw_quick_scan_overlay_on(
            gui.quick_scan_canvas if hasattr(gui, "quick_scan_canvas") else None,
            "overlay",
        )
        self._draw_quick_scan_overlay_on(
            gui.canvas if hasattr(gui, "canvas") else None,
            "quick_scan_overlay",
        )
        self._draw_status_overlay_on(
            gui.canvas if hasattr(gui, "canvas") else None,
            "status_overlay",
        )
        if hasattr(gui, "classification_overlay"):
            gui.classification_overlay.draw()

    def _draw_quick_scan_overlay_on(
        self, target_canvas: Optional[tk.Canvas], tag: str,
    ) -> None:
        gui = self.gui
        if target_canvas is None:
            return
        target_canvas.delete(tag)
        if not gui.show_quick_scan_overlay.get():
            return
        if not getattr(gui, "original_image", None):
            return

        orig_width, orig_height = gui.original_image.size
        scale_x = orig_width / 600
        scale_y = orig_height / 500

        for device, bounds in gui.device_mapping.items():
            current = gui.quick_scan_results.get(device)
            if current is None or (isinstance(current, float) and math.isnan(current)):
                continue
            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y
            color = self.current_to_color(current)
            target_canvas.create_rectangle(
                x_min, y_min, x_max, y_max,
                fill=color, outline="", stipple="gray50", tags=tag,
            )

    def _draw_status_overlay_on(
        self, target_canvas: Optional[tk.Canvas], tag: str,
    ) -> None:
        gui = self.gui
        if target_canvas is None:
            return
        target_canvas.delete(tag)
        if not gui.show_status_overlay.get():
            return
        if not getattr(gui, "original_image", None):
            return

        orig_width, orig_height = gui.original_image.size
        scale_x = orig_width / 600
        scale_y = orig_height / 500

        for device, bounds in gui.device_mapping.items():
            manual_status = gui.device_status.get(device, {}).get("manual_status", "undefined")
            if manual_status == "undefined":
                continue
            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y
            if manual_status == "working":
                color = "#4CAF50"
            elif manual_status == "broken":
                color = "#F44336"
            else:
                continue
            target_canvas.create_rectangle(
                x_min, y_min, x_max, y_max,
                fill=color, outline="", stipple="gray75", tags=tag,
            )

    # ------------------------------------------------------------------
    # Scan execution
    # ------------------------------------------------------------------
    def start(self) -> None:
        gui = self.gui
        if gui.quick_scan_running:
            return
        if gui.mpx_manager is None:
            messagebox.showwarning("Multiplexer", "Multiplexer manager not initialized.")
            return
        if not getattr(gui, "device_list", None):
            messagebox.showwarning("Devices", "No devices available to scan.")
            return
        try:
            voltage = float(gui.quick_scan_voltage_var.get())
        except (tk.TclError, ValueError, TypeError):
            messagebox.showerror("Quick Scan", "Voltage value is invalid.")
            return
        try:
            settle_time = max(0.0, float(gui.quick_scan_settle_var.get()))
        except (tk.TclError, ValueError, TypeError):
            messagebox.showerror("Quick Scan", "Settle time value is invalid.")
            return

        gui.quick_scan_abort.clear()
        gui.quick_scan_running = True
        gui.quick_scan_results.clear()
        self.redraw_overlay()
        self._set_buttons(running=True)
        self._set_status("Running")
        self._log("Starting quick scan...")

        gui.quick_scan_thread = threading.Thread(
            target=self._worker,
            args=(voltage, settle_time),
            daemon=True,
        )
        gui.quick_scan_thread.start()

    def stop(self) -> None:
        if self.gui.quick_scan_running:
            self.gui.quick_scan_abort.set()
            self._log("Stop requested. Finishing current device...")

    def _worker(self, voltage: float, settle_time: float) -> None:
        gui = self.gui
        controller = None
        instrument_ready = False
        if Keithley2400Controller is not None:
            try:
                controller = Keithley2400Controller()
                if getattr(controller, "device", None):
                    instrument_ready = True
                    gui._run_on_ui(lambda: self._log("Keithley 2400 connected for quick scan."))
                else:
                    controller = None
            except Exception as exc:
                controller = None
                gui._run_on_ui(lambda: self._log(f"Instrument unavailable, using simulation. ({exc})"))
        else:
            gui._run_on_ui(lambda: self._log("Instrument driver not available, using simulation."))

        if not instrument_ready:
            controller = None
        if controller:
            try:
                controller.set_voltage(0.0)
            except Exception:
                pass

        for idx, device in enumerate(gui.device_list):
            if gui.quick_scan_abort.is_set():
                break
            gui._run_on_ui(lambda d=device, i=idx: self._highlight_device(d, i))
            try:
                routed = gui.mpx_manager.route_to_device(device, idx)
            except Exception as exc:
                gui._run_on_ui(
                    lambda msg=f"Routing failed for {gui.get_device_label(device)}: {exc}": self._log(msg),
                )
                continue
            if not routed:
                gui._run_on_ui(
                    lambda msg=f"Routing failed for {gui.get_device_label(device)}.": self._log(msg),
                )
                continue
            time.sleep(settle_time)
            if gui.quick_scan_abort.is_set():
                break
            if controller:
                current = self._measure_device_current(controller, voltage)
            else:
                current = self._simulate_current(device, voltage)
            gui._run_on_ui(lambda d=device, value=current: self._store_result(d, value))
            label = gui.get_device_label(device)
            gui._run_on_ui(
                lambda l=label, value=current: self._log(f"{l}: {self._format_current(value)}"),
            )

        aborted = gui.quick_scan_abort.is_set()
        if controller:
            try:
                controller.set_voltage(0.0)
                time.sleep(0.05)
                controller.enable_output(False)
            except Exception:
                pass
        gui._run_on_ui(lambda: self._finalize(aborted))

    def _measure_device_current(self, controller: Any, voltage: float) -> Optional[float]:
        try:
            controller.set_voltage(voltage)
            time.sleep(0.1)
            current = controller.measure_current()
            controller.set_voltage(0.0)
            return float(current) if current is not None else None
        except Exception as exc:
            self.gui._run_on_ui(lambda msg=f"Measurement error: {exc}": self._log(msg))
            return None

    def _simulate_current(self, device: str, voltage: float) -> float:
        gui = self.gui
        rng = random.Random()
        rng.seed(f"{device}:{round(voltage, 3)}")
        failure_floor = min(gui.quick_scan_min_current * 0.1, 1e-11)
        if rng.random() < 0.25:
            return rng.uniform(failure_floor, gui.quick_scan_min_current * 0.25)
        log_min = math.log10(max(gui.quick_scan_min_current, 1e-12))
        log_max = math.log10(max(gui.quick_scan_max_current, log_min + 1e-6))
        span = log_max - log_min
        return 10 ** (log_min + span * (rng.random() ** 0.5))

    def _highlight_device(self, device: str, idx: int) -> None:
        gui = self.gui
        label = gui.get_device_label(device)
        gui.current_index = idx
        gui.device_var.set(label)
        gui.info_box.config(text=f"Current Device: {label}")
        try:
            gui.update_highlight(device)
        except Exception:
            pass
        self._set_status(f"Scanning {label}")

    def _store_result(self, device: str, current: Optional[float]) -> None:
        self.gui.quick_scan_results[device] = current
        self.redraw_overlay()

    def _finalize(self, aborted: bool) -> None:
        gui = self.gui
        gui.quick_scan_running = False
        status = "Aborted" if aborted else "Complete"
        self._set_status(status)
        self._set_buttons(running=False)
        if gui.quick_scan_results:
            gui.quick_scan_save_button.config(state=tk.NORMAL)
            voltage = gui.quick_scan_voltage_var.get()
            updated_count = 0
            for device, current in gui.quick_scan_results.items():
                if current is None or (isinstance(current, float) and math.isnan(current)):
                    continue
                if device not in gui.device_status:
                    gui.device_status[device] = gui.status_store.default_device_status_entry()
                auto_class = "working" if current >= gui.quick_scan_threshold else "not-working"
                gui.device_status[device]["auto_classification"] = auto_class
                gui.device_status[device]["last_current_a"] = current
                gui.device_status[device]["test_voltage_v"] = voltage
                gui.device_status[device]["last_tested"] = datetime.now().isoformat(timespec="seconds")
                history_entry = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "current_a": current,
                    "voltage_v": voltage,
                }
                gui.device_status[device].setdefault("quick_scan_history", []).append(history_entry)
                updated_count += 1
            if updated_count > 0:
                gui.status_store.save_device_status()
                self._log(f"Updated status for {updated_count} device(s)")
        self._log(f"Quick scan {status.lower()}.")
        if not aborted:
            gui._send_telegram_notification(aborted)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_results(self) -> None:
        gui = self.gui
        if gui.quick_scan_running:
            messagebox.showinfo("Quick Scan", "Please wait for the scan to finish before saving.")
            return
        if not gui.quick_scan_results:
            messagebox.showwarning("Quick Scan", "No quick scan data to save.")
            return
        sample = gui.sample_type_var.get()
        if not sample:
            messagebox.showwarning("Quick Scan", "Select a sample before saving.")
            return

        storage_dir = gui.status_store.get_quick_scan_storage_dir(sample)
        storage_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat(timespec="seconds")
        voltage = float(gui.quick_scan_voltage_var.get())
        payload = {
            "sample": sample,
            "voltage_v": voltage,
            "timestamp": timestamp,
            "device_count": len(gui.quick_scan_results),
            "results": [],
        }
        for device_key in gui.device_list:
            current = gui.quick_scan_results.get(device_key)
            if current is not None and isinstance(current, float) and math.isnan(current):
                current = None
            payload["results"].append({
                "device_key": device_key,
                "device_label": gui.get_device_label(device_key),
                "current_a": current,
            })

        json_path = storage_dir / "quick_scan.json"
        csv_path = storage_dir / "quick_scan.csv"
        try:
            with json_path.open("w", encoding="utf-8") as fp:
                json.dump(payload, fp, indent=2)
        except Exception as exc:
            messagebox.showerror("Quick Scan", f"Failed to save JSON: {exc}")
            return
        try:
            with csv_path.open("w", newline="", encoding="utf-8") as fp:
                writer = csv.writer(fp)
                writer.writerow(["device_key", "device_label", "current_a", "voltage_v", "timestamp"])
                for entry in payload["results"]:
                    writer.writerow([
                        entry["device_key"],
                        entry["device_label"],
                        "" if entry["current_a"] is None else f"{entry['current_a']:.6e}",
                        f"{voltage:.6f}",
                        timestamp,
                    ])
        except Exception as exc:
            messagebox.showerror("Quick Scan", f"Failed to save CSV: {exc}")
            return

        gui.quick_scan_metadata = {
            "sample": sample,
            "voltage_v": voltage,
            "timestamp": timestamp,
            "paths": {"json": str(json_path), "csv": str(csv_path)},
        }
        self._log(f"Saved quick scan to {json_path.name} and {csv_path.name}.")
        self._set_status("Saved")

    def load_results(self) -> None:
        sample = self.gui.sample_type_var.get()
        if not sample:
            messagebox.showwarning("Quick Scan", "Select a sample before loading data.")
            return
        if not self.load_for_sample(sample, silent=False):
            messagebox.showinfo("Quick Scan", f"No saved quick scan data for sample '{sample}'.")

    def load_for_sample(self, sample: str, silent: bool = True) -> bool:
        gui = self.gui
        storage_dir = gui.status_store.get_quick_scan_storage_dir(sample)
        json_path = storage_dir / "quick_scan.json"
        if not json_path.exists():
            if not silent:
                self._log("No saved quick scan data found.")
            return False
        try:
            with json_path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
        except Exception as exc:
            if not silent:
                messagebox.showerror("Quick Scan", f"Failed to load quick scan JSON: {exc}")
            return False

        results = {}
        for entry in payload.get("results", []):
            key = entry.get("device_key")
            if key is not None:
                results[key] = entry.get("current_a")

        gui.quick_scan_results = results
        gui.quick_scan_metadata = {
            "sample": payload.get("sample", sample),
            "voltage_v": payload.get("voltage_v"),
            "timestamp": payload.get("timestamp"),
            "paths": {"json": str(json_path)},
        }
        if payload.get("voltage_v") is not None:
            try:
                gui.quick_scan_voltage_var.set(float(payload["voltage_v"]))
            except Exception:
                pass
        self.redraw_overlay()
        self._set_buttons(running=False)
        if results:
            gui.quick_scan_save_button.config(state=tk.NORMAL)
        if not silent:
            self._log(f"Loaded quick scan data from {json_path.name}.")
        return True

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _set_buttons(self, running: bool) -> None:
        gui = self.gui
        gui.quick_scan_run_button.config(state=tk.DISABLED if running else tk.NORMAL)
        gui.quick_scan_stop_button.config(state=tk.NORMAL if running else tk.DISABLED)
        if running:
            gui.quick_scan_save_button.config(state=tk.DISABLED)
        elif gui.quick_scan_results:
            gui.quick_scan_save_button.config(state=tk.NORMAL)
        else:
            gui.quick_scan_save_button.config(state=tk.DISABLED)

    def _set_status(self, text: str) -> None:
        self.gui.quick_scan_status.config(text=f"Status: {text}")

    def _log(self, message: str) -> None:
        gui = self.gui
        timestamp = datetime.now().strftime("%H:%M:%S")
        gui.quick_scan_log.config(state=tk.NORMAL)
        gui.quick_scan_log.insert(tk.END, f"[{timestamp}] {message}\n")
        gui.quick_scan_log.config(state=tk.DISABLED)
        gui.quick_scan_log.see(tk.END)

    @staticmethod
    def _format_current(current: Optional[float]) -> str:
        if current is None or (isinstance(current, float) and math.isnan(current)):
            return "n/a"
        return f"{current:.3e} A"
