"""
Motor Control GUI - Reusable Widgets
====================================

CollapsibleFrame and other shared UI components.
"""

from __future__ import annotations

import tkinter as tk


class CollapsibleFrame(tk.Frame):
    """A frame that can be collapsed and expanded with a toggle button."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        bg_color: str = "#e8e8e8",
        fg_color: str = "#000000",
        start_expanded: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=bg_color, **kwargs)
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.is_expanded = start_expanded

        self.header = tk.Frame(self, bg=bg_color)
        self.header.pack(fill=tk.X, padx=2, pady=2)

        self.toggle_btn = tk.Button(
            self.header,
            text="▼" if start_expanded else "▶",
            command=self.toggle,
            bg=bg_color,
            fg=fg_color,
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            width=2,
            cursor="hand2",
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=(2, 5))

        self.title_label = tk.Label(
            self.header,
            text=title,
            bg=bg_color,
            fg=fg_color,
            font=("Arial", 10, "bold"),
            anchor="w",
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.header.bind("<Button-1>", lambda e: self.toggle())
        self.title_label.bind("<Button-1>", lambda e: self.toggle())

        self.content_frame = tk.Frame(self, bg="#d0d0d0", relief=tk.FLAT, borderwidth=1)
        self.inner_frame = tk.Frame(self.content_frame, bg="#f0f0f0")
        self.inner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        if start_expanded:
            self.content_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
        # else: content_frame not packed, so section starts collapsed

    def toggle(self) -> None:
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.toggle_btn.config(text="▶")
            self.is_expanded = False
        else:
            self.content_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
            self.toggle_btn.config(text="▼")
            self.is_expanded = True

    def collapse(self) -> None:
        if self.is_expanded:
            self.toggle()

    def expand(self) -> None:
        if not self.is_expanded:
            self.toggle()

    def get_content_frame(self) -> tk.Frame:
        return self.inner_frame
