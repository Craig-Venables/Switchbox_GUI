"""Measurement GUI in-app help window."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def show_measurement_help(gui: Any) -> None:
    """Display the scrollable Measurement GUI guide."""
    help_win = tk.Toplevel(gui.master)
    help_win.title("Measurement GUI Guide")
    help_win.geometry("800x700")
    help_win.configure(bg="#f0f0f0")

    canvas = tk.Canvas(help_win, bg="#f0f0f0")
    scrollbar = ttk.Scrollbar(help_win, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    pad = {"padx": 20, "pady": 10, "anchor": "w"}

    tk.Label(
        scrollable_frame, text="Measurement GUI Guide",
        font=("Segoe UI", 16, "bold"), bg="#f0f0f0", fg="#1565c0",
    ).pack(**pad)

    sections = [
        ("1. Overview",
         "This is the main measurement interface for IV/PMU/SMU measurements on device arrays.\n"
         "It provides comprehensive control over instrument connections, measurement\n"
         "configuration, real-time plotting, and data saving."),
        ("2. Getting Started",
         "• Select your measurement system from the dropdown in the top bar\n"
         "• Configure instrument connections in the Setup tab\n"
         "• Set measurement parameters in the Measurements tab\n"
         "• Click 'Start Measurement' to begin\n"
         "• Monitor progress in real-time plots"),
        ("3. Key Features",
         "• IV Sweeps: Standard voltage sweeps with current measurement\n"
         "• Custom Measurements: Load pre-configured sweeps from JSON\n"
         "• Sequential Measurements: Test multiple devices automatically\n"
         "• Conditional Testing: Smart workflow for memristive devices\n"
         "• Pulse Testing: Fast pulse characterization (separate GUI)\n"
         "• Real-time Plotting: Live voltage, current, and resistance plots\n"
         "• Data Saving: Automatic file naming and organization"),
        ("4. Utility Buttons",
         "• Motor Control / Check Connection / Pulse Testing / Device Visualizer\n"
         "• Oscilloscope Pulse / Laser FG Scope\n"
         "• Hardware Tools: Display control and LED testing (Arduino tools)"),
        ("5. Conditional Memristive Testing",
         "Smart workflow that screens devices and runs tests only on memristive devices.\n"
         "Configure from Advanced Tests or Measurements tab. See Documents/guides/ for details."),
        ("6. Additional Resources",
         "• Documents/guides/GUI_HANDBOOK.md\n"
         "• Documents/guides/GUI_EXTENSION_GUIDE.md\n"
         "• Documents/guides/JSON_CONFIG_GUIDE.md\n"
         "• Documents/guides/QUICK_REFERENCE.md"),
    ]

    for title, body in sections:
        tk.Label(scrollable_frame, text=title, font=("Segoe UI", 12, "bold"), bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame, text=body, justify="left", bg="#f0f0f0").pack(**pad)

    tk.Label(
        scrollable_frame, text="7. Video Tutorials",
        font=("Segoe UI", 12, "bold"), bg="#f0f0f0", fg="#d32f2f",
    ).pack(**pad)

    video_frame = ttk.Frame(scrollable_frame)
    video_frame.pack(**pad, fill="x")

    def open_video(video_path_or_url: str) -> None:
        try:
            if video_path_or_url.startswith(("http://", "https://")):
                webbrowser.open(video_path_or_url)
                return
            video_path = Path(video_path_or_url)
            if not video_path.is_absolute():
                video_path = _PROJECT_ROOT / "Videos" / video_path_or_url
            if not video_path.exists():
                messagebox.showerror(
                    "Video Not Found",
                    f"Video file not found:\n{video_path}\n\nPlace files in the Videos/ folder.",
                )
                return
            if sys.platform == "win32":
                os.startfile(str(video_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(video_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(video_path)], check=False)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open video:\n{exc}")

    video_config_path = _PROJECT_ROOT / "Json_Files" / "help_videos.json"
    video_config: list = []
    try:
        if video_config_path.exists():
            with video_config_path.open("r", encoding="utf-8") as f:
                video_config = json.load(f).get("videos", [])
    except Exception as exc:
        print(f"Warning: Could not load video config: {exc}")

    if video_config:
        for video_item in video_config:
            video_title = video_item.get("title", "Untitled Video")
            video_path = video_item.get("path", "")
            video_desc = video_item.get("description", "")
            if not video_path:
                continue
            btn_frame = ttk.Frame(video_frame)
            btn_frame.pack(side="top", fill="x", pady=5)
            tk.Button(
                btn_frame, text=f"▶ {video_title}",
                font=("Segoe UI", 10, "bold"),
                bg="#4CAF50", fg="white",
                activebackground="#45a049", activeforeground="white",
                relief="raised", cursor="hand2", padx=15, pady=8,
                command=lambda v=video_path: open_video(v),
            ).pack(side="left", padx=(0, 10))
            if video_desc:
                tk.Label(
                    btn_frame, text=video_desc,
                    font=("Segoe UI", 9), bg="#f0f0f0", fg="#666", justify="left",
                ).pack(side="left", fill="x", expand=True)
    else:
        tk.Label(
            video_frame,
            text="No video tutorials configured.\nEdit Json_Files/help_videos.json to add videos.",
            justify="left", bg="#f0f0f0", fg="#666",
        ).pack(**pad)

    tk.Label(
        scrollable_frame,
        text="\nNote: Videos can be local files (Videos/ folder) or online URLs.",
        justify="left", bg="#f0f0f0", fg="#666", font=("Segoe UI", 9),
    ).pack(**pad)
