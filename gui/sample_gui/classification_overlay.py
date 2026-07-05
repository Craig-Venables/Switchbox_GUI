"""
IV classification overlay for SampleGUI device map.

Shows pale fill colors and optional score labels from device_tracking history.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

import tkinter as tk

from gui.sample_gui.config import resolve_default_save_root
from gui.measurement_gui.yield_concentration.yield_source import (
    find_tracking_dir,
    summarize_device_from_history,
    summarize_sample_devices,
)

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI

OVERLAY_TAG = "classification_overlay"
SCORE_TAG = "classification_score"

# Base colors by display status (Material 200–300 — visible but not neon)
STATUS_COLORS: Dict[str, str] = {
    "pending": "#BDBDBD",
    "non_conductive": "#EF9A9A",
    "ohmic": "#90CAF9",
    "rectifying": "#FFCC80",
    "uncertain": "#CE93D8",
    "capacitive": "#FFF176",
    "conductive": "#BCAAA4",
}

# Memristive green gradient: score 60 → 100
MEM_FLOOR_RGB = (0xA5, 0xD6, 0xA7)  # green 200
MEM_CEIL_RGB = (0x66, 0xBB, 0x6A)   # green 400

# Subtle cell outline (darkened fill) for map readability
OUTLINE_DARKEN = 0.72


@dataclass
class DeviceDisplayInfo:
    display_status: str
    sweep_count: int = 0
    best_mem_score: Optional[float] = None
    latest_type: str = "unknown"
    promising: bool = False
    measured: bool = False
    fill_color: str = ""
    stipple: str = ""
    score_label: str = ""


def resolve_sample_folder(gui: "SampleGUI") -> Tuple[str, str]:
    """Return (sample_dir path, sample_name) for tracking lookup."""
    if getattr(gui, "current_device_name", None):
        sample_name = gui.current_device_name
    else:
        sample_name = gui.sample_type_var.get() if hasattr(gui, "sample_type_var") else ""
    if not sample_name:
        return "", ""
    sample_dir = str(resolve_default_save_root() / sample_name)
    return sample_dir, sample_name


def device_key_to_tracking_id(
    sample_name: str,
    device_key: str,
    section_number_by_key: Dict[str, Tuple[str, Optional[int]]],
) -> str:
    section, number = section_number_by_key.get(device_key, ("", None))
    if section and number is not None:
        return f"{sample_name}_{section}_{number}"
    return ""


def memristive_fill_color(best_score: float) -> str:
    """Interpolate green fill by memristivity score (60–100)."""
    t = max(0.0, min(1.0, (float(best_score) - 60.0) / 40.0))
    r = int(MEM_FLOOR_RGB[0] + (MEM_CEIL_RGB[0] - MEM_FLOOR_RGB[0]) * t)
    g = int(MEM_FLOOR_RGB[1] + (MEM_CEIL_RGB[1] - MEM_FLOOR_RGB[1]) * t)
    b = int(MEM_FLOOR_RGB[2] + (MEM_CEIL_RGB[2] - MEM_FLOOR_RGB[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def darken_hex(color: str, factor: float = OUTLINE_DARKEN) -> str:
    """Return a darker shade of a #RRGGBB color for outlines."""
    if not color or not color.startswith("#") or len(color) != 7:
        return "#757575"
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def build_device_display_info(summary: dict) -> DeviceDisplayInfo:
    status = summary.get("display_status", "unmeasured")
    best = summary.get("best_mem_score")
    sweep_count = int(summary.get("sweep_count") or 0)

    if status == "memristive" and best is not None:
        fill = memristive_fill_color(best)
        score_label = str(int(round(best)))
    elif status == "pending":
        fill = STATUS_COLORS["pending"]
        if best is not None:
            score_label = f"{int(round(best))}?"
        else:
            score_label = "1"
    elif status == "unmeasured":
        fill = ""
        score_label = ""
    else:
        fill = STATUS_COLORS.get(status, STATUS_COLORS.get("uncertain", "#CE93D8"))
        score_label = ""

    return DeviceDisplayInfo(
        display_status=status,
        sweep_count=sweep_count,
        best_mem_score=best,
        latest_type=str(summary.get("latest_type", "unknown")),
        promising=bool(summary.get("promising")),
        measured=bool(summary.get("measured")),
        fill_color=fill,
        stipple="",
        score_label=score_label,
    )


def load_device_summaries(
    sample_dir: str,
    sample_name: str,
    device_keys: list[str],
    section_number_by_key: Dict[str, Tuple[str, Optional[int]]],
) -> Dict[str, DeviceDisplayInfo]:
    """Load tracking history and build display info keyed by device_key."""
    result: Dict[str, DeviceDisplayInfo] = {}
    tracking_dir = find_tracking_dir(sample_dir) if sample_dir and os.path.isdir(sample_dir) else None

    for device_key in device_keys:
        tracking_id = device_key_to_tracking_id(sample_name, device_key, section_number_by_key)
        history = None
        if tracking_dir and tracking_id:
            path = os.path.join(tracking_dir, f"{tracking_id}_history.json")
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        history = json.load(f)
                except (json.JSONDecodeError, OSError):
                    history = None
        summary = summarize_device_from_history(history)
        result[device_key] = build_device_display_info(summary)
    return result


class ClassificationOverlayController:
    """Draw IV classification overlay on the sample device map."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui
        self.device_info: Dict[str, DeviceDisplayInfo] = {}
        self.classification_summary: dict = {}
        self._refresh_lock = threading.Lock()
        self._refresh_pending = False

    def refresh(self) -> None:
        """Reload tracking data in background and redraw overlay."""
        with self._refresh_lock:
            if self._refresh_pending:
                return
            self._refresh_pending = True

        def worker() -> None:
            try:
                info, summary = self._load_all()
            except Exception as exc:
                print(f"[CLASS OVERLAY] Refresh failed: {exc}")
                info, summary = {}, {}
            root = getattr(self.gui, "root", None)
            if root is not None:
                root.after(0, lambda: self._apply_refresh(info, summary))
            else:
                self._apply_refresh(info, summary)

        threading.Thread(target=worker, daemon=True, name="ClassOverlayRefresh").start()

    def _load_all(self) -> Tuple[Dict[str, DeviceDisplayInfo], dict]:
        gui = self.gui
        sample_dir, sample_name = resolve_sample_folder(gui)
        device_keys = list(getattr(gui, "device_list", []) or [])
        if not sample_dir or not device_keys:
            summaries_raw = {}
            info = {k: build_device_display_info({}) for k in device_keys}
        else:
            info = load_device_summaries(
                sample_dir,
                sample_name,
                device_keys,
                gui.device_section_number_by_key,
            )
            summaries_raw = {
                k: {
                    "measured": v.measured,
                    "display_status": v.display_status,
                    "promising": v.promising,
                }
                for k, v in info.items()
            }
        summary = summarize_sample_devices(summaries_raw, len(device_keys))
        return info, summary

    def _apply_refresh(self, info: Dict[str, DeviceDisplayInfo], summary: dict) -> None:
        with self._refresh_lock:
            self._refresh_pending = False
        self.device_info = info
        self.classification_summary = summary
        self.gui.classification_summary = summary
        self.draw()
        self._update_summary_label()
        self._update_checkbox_tints()

    def draw(self) -> None:
        """Draw overlay on main device canvas."""
        canvas = getattr(self.gui, "canvas", None)
        if canvas is None:
            return
        self._draw_on_canvas(canvas, OVERLAY_TAG, SCORE_TAG)

    def _draw_on_canvas(
        self,
        target_canvas: Optional[tk.Canvas],
        fill_tag: str,
        score_tag: str,
    ) -> None:
        if target_canvas is None:
            return
        target_canvas.delete(fill_tag)
        target_canvas.delete(score_tag)

        show_overlay = getattr(self.gui, "show_classification_overlay", None)
        if show_overlay is not None and not show_overlay.get():
            return

        if not getattr(self.gui, "original_image", None):
            return

        show_scores = getattr(self.gui, "show_classification_scores", None)
        scores_on = show_scores is None or show_scores.get()

        orig_width, orig_height = self.gui.original_image.size
        scale_x = orig_width / 600
        scale_y = orig_height / 500

        for device, bounds in self.gui.device_mapping.items():
            info = self.device_info.get(device)
            if not info or not info.fill_color:
                continue

            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y

            target_canvas.create_rectangle(
                x_min, y_min, x_max, y_max,
                fill=info.fill_color,
                outline=darken_hex(info.fill_color),
                width=1,
                tags=fill_tag,
            )

            if scores_on and info.score_label:
                cx = (x_min + x_max) / 2
                cy = (y_min + y_max) / 2
                target_canvas.create_text(
                    cx, cy,
                    text=info.score_label,
                    fill="#212121",
                    font=("Segoe UI", 9, "bold"),
                    tags=score_tag,
                )

    def _update_summary_label(self) -> None:
        label = getattr(self.gui, "classification_summary_label", None)
        if label is None:
            return
        s = self.classification_summary
        total = s.get("total_devices", 0)
        measured = s.get("measured_count", 0)
        mem = s.get("memristive_count", 0)
        pending = s.get("pending_count", 0)
        promising = s.get("promising_count", 0)
        text = (
            f"Measured {measured}/{total} · Memristive {mem} · "
            f"Promising {promising} · Pending {pending}"
        )
        label.config(text=text)

    def _update_checkbox_tints(self) -> None:
        row_frames = getattr(self.gui, "device_row_frames", None)
        if not row_frames:
            return
        for device_key, frame in row_frames.items():
            info = self.device_info.get(device_key)
            bg = info.fill_color if info and info.fill_color else self.gui.root.cget("bg")
            try:
                frame.config(bg=bg)
                for child in frame.winfo_children():
                    try:
                        child.config(bg=bg)
                    except tk.TclError:
                        pass
            except tk.TclError:
                pass
