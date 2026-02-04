"""
Motor Control GUI - Canvas and Camera Section
=============================================
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

try:
    import cv2  # noqa: F401
    import numpy as np  # noqa: F401
    from PIL import Image, ImageTk  # noqa: F401
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False

from gui.motor_control_gui import config


def create_canvas_and_camera(gui: Any) -> None:
    """Build canvas and camera feed area."""
    c = config.COLORS
    right_container = tk.Frame(gui.root, bg=c["bg_dark"])
    right_container.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
    right_container.rowconfigure(0, weight=1)
    right_container.rowconfigure(1, weight=1)
    right_container.columnconfigure(0, weight=1)

    _build_canvas(gui, right_container)
    _build_camera_placeholder(gui, right_container)


def _build_canvas(gui: Any, parent: tk.Frame) -> None:
    """Build interactive canvas with grid and position marker."""
    c = config.COLORS
    canvas_frame = tk.LabelFrame(
        parent,
        text="🎯 Position Map (Click to Move)",
        bg=c["bg_medium"],
        fg=c["fg_primary"],
        font=("Arial", 11, "bold"),
        relief=tk.FLAT,
        borderwidth=2,
    )
    canvas_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    gui.canvas = tk.Canvas(
        canvas_frame,
        width=gui.canvas_size,
        height=gui.canvas_size,
        background="#ffffff",
        highlightthickness=0,
    )
    gui.canvas.pack(padx=10, pady=10)
    gui.canvas.bind("<Button-1>", gui._on_canvas_click)
    gui.canvas.bind("<Motion>", gui._on_canvas_hover)

    gui.canvas_coord_text = gui.canvas.create_text(
        10,
        10,
        text="",
        anchor="nw",
        fill=c["accent_blue"],
        font=("Consolas", 9),
    )


def _build_camera_placeholder(gui: Any, parent: tk.Frame) -> None:
    """Build camera feed display with controls."""
    c = config.COLORS
    camera_frame = tk.LabelFrame(
        parent,
        text="📷 Camera Feed",
        bg=c["bg_medium"],
        fg=c["fg_primary"],
        font=("Arial", 11, "bold"),
        relief=tk.FLAT,
        borderwidth=2,
    )
    camera_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    camera_frame.columnconfigure(0, weight=1)
    camera_frame.rowconfigure(0, weight=1)
    camera_frame.rowconfigure(1, weight=0)

    display_frame = tk.Frame(camera_frame, bg="#ffffff")
    display_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    display_frame.columnconfigure(0, weight=1)
    display_frame.rowconfigure(0, weight=1)

    if CAMERA_AVAILABLE:
        gui.camera_label = tk.Label(
            display_frame,
            text="Camera not started",
            bg="#000000",
            fg=c["fg_secondary"],
            font=("Arial", 12),
            anchor="center",
        )
        gui.camera_label.grid(row=0, column=0, sticky="nsew")
        gui._camera_photo_list = []
        gui._camera_photo = None
    else:
        tk.Label(
            display_frame,
            text="📹\nCamera support not available\n(Install opencv-python and pillow)",
            bg="#ffffff",
            fg=c["fg_secondary"],
            font=("Arial", 12),
        ).grid(row=0, column=0, sticky="nsew")

    controls_frame = tk.Frame(camera_frame, bg=c["bg_medium"])
    controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

    if CAMERA_AVAILABLE:
        mode_frame = tk.Frame(controls_frame, bg=c["bg_medium"])
        mode_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        tk.Label(
            mode_frame,
            text="Mode:",
            bg=c["bg_medium"],
            fg=c["fg_primary"],
            font=("Arial", 9),
        ).pack(side=tk.LEFT, padx=5)

        gui.camera_mode_var = tk.StringVar(value="IP Stream")
        mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=gui.camera_mode_var,
            values=["IP Stream", "USB Camera"],
            width=12,
            state="readonly",
        )
        mode_combo.pack(side=tk.LEFT, padx=5)
        mode_combo.bind("<<ComboboxSelected>>", lambda e: gui._update_camera_mode_ui())

        gui.ip_frame = tk.Frame(controls_frame, bg=c["bg_medium"])
        gui.ip_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        tk.Label(
            gui.ip_frame,
            text="Stream IP:",
            bg=c["bg_medium"],
            fg=c["fg_primary"],
            font=("Arial", 9),
        ).pack(side=tk.LEFT, padx=5)

        gui.camera_ip_var = tk.StringVar(value="localhost")
        tk.Entry(
            gui.ip_frame,
            textvariable=gui.camera_ip_var,
            width=15,
            font=("Arial", 9),
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(
            gui.ip_frame,
            text="Port:",
            bg=c["bg_medium"],
            fg=c["fg_primary"],
            font=("Arial", 9),
        ).pack(side=tk.LEFT, padx=5)

        gui.camera_port_var = tk.StringVar(value="8080")
        tk.Entry(
            gui.ip_frame,
            textvariable=gui.camera_port_var,
            width=6,
            font=("Arial", 9),
        ).pack(side=tk.LEFT, padx=5)

        gui.usb_frame = tk.Frame(controls_frame, bg=c["bg_medium"])

        tk.Label(
            gui.usb_frame,
            text="Camera Index:",
            bg=c["bg_medium"],
            fg=c["fg_primary"],
            font=("Arial", 9),
        ).pack(side=tk.LEFT, padx=5)

        gui.camera_index_var = tk.StringVar(value="0")
        tk.Entry(
            gui.usb_frame,
            textvariable=gui.camera_index_var,
            width=5,
            font=("Arial", 9),
        ).pack(side=tk.LEFT, padx=5)

        button_frame = tk.Frame(controls_frame, bg=c["bg_medium"])
        button_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        gui.camera_start_button = tk.Button(
            button_frame,
            text="▶ Start Camera",
            command=gui._start_camera_feed,
            bg=c["accent_green"],
            fg="white",
            font=("Arial", 9, "bold"),
            padx=10,
            pady=5,
            relief=tk.FLAT,
        )
        gui.camera_start_button.pack(side=tk.LEFT, padx=5)

        gui.camera_stop_button = tk.Button(
            button_frame,
            text="⏹ Stop Camera",
            command=gui._stop_camera_feed,
            bg=c["accent_red"],
            fg="white",
            font=("Arial", 9, "bold"),
            padx=10,
            pady=5,
            relief=tk.FLAT,
            state=tk.DISABLED,
        )
        gui.camera_stop_button.pack(side=tk.LEFT, padx=5)

        gui._update_camera_mode_ui()
