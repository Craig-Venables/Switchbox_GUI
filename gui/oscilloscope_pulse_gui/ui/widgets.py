"""
Shared widgets for Oscilloscope Pulse GUI.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import config as gui_config


def _var_name_from_title(title: str) -> str:
    """Generate expansion var name from collapsible section title."""
    s = title.lower().replace(" ", "_")
    for emoji in ("1️⃣", "📐", "💾"):
        s = s.replace(emoji, "")
    return s.strip() + "_expanded"


def create_collapsible_frame(gui, parent, title: str, build_content_func, default_expanded: bool = True):
    """
    Create a collapsible frame with expand/collapse button.
    gui must have: .vars, .widgets, ._toggle_collapsible_frame(container, button, var_name, build_content_func).
    """
    container = ttk.Frame(parent)
    container.pack(fill="x", pady=2)

    var_name = _var_name_from_title(title)
    gui.vars[var_name] = tk.BooleanVar(value=default_expanded)

    header_frame = ttk.Frame(container)
    header_frame.pack(fill="x")

    container._title = title

    expand_btn = ttk.Button(
        header_frame,
        text=f"▼ {title}" if default_expanded else f"▶ {title}",
        command=lambda: gui._toggle_collapsible_frame(container, expand_btn, var_name, build_content_func),
        style="Small.TButton",
    )
    expand_btn.pack(side="left")
    container._expand_btn = expand_btn

    content_frame = ttk.Labelframe(container, text=title, padding=5)
    content_key = _var_name_from_title(title).replace("_expanded", "_content")
    gui.widgets[content_key] = content_frame
    container._content_frame = content_frame

    if default_expanded:
        content_frame.pack(fill="x", pady=(2, 0))
        build_content_func(content_frame)
        content_frame._content_built = True
    else:
        content_frame._build_func = build_content_func

    return container


class ToolTip:
    """Tooltip for a given widget."""

    def __init__(self, widget, text: str = "widget info"):
        self.waittime = 500
        self.wraplength = 180
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id_val = self.id
        self.id = None
        if id_val:
            self.widget.after_cancel(id_val)

    def showtip(self, event=None):
        x = y = 0
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except Exception:
            return
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(
            self.tw,
            text=self.text,
            justify="left",
            background=gui_config.COLORS.get("tooltip_bg", "#ffffe0"),
            relief="solid",
            borderwidth=1,
            wraplength=self.wraplength,
        )
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            try:
                tw.destroy()
            except tk.TclError:
                pass
