"""
Laser FG Scope GUI — Save Panel
================================
Controls for choosing where data is saved and toggling auto-save.

Layout (inside a LabelFrame):
  Row 1: [Folder:] [path entry, read-only] [Browse…]
  Row 2: [☑ Auto-save every capture]
  Row 3: [Save Last Capture]  [status label]

When a provider is set (launched from Measurement GUI) the folder row shows
the resolved path from the provider's sample/device tree instead of the
simple folder, and the Browse button is hidden.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any, Callable, Optional

BG = "#f8f8f8"


class SavePanel(ttk.LabelFrame):
    """UI for configuring save location and triggering manual saves."""

    def __init__(
        self,
        parent: tk.Widget,
        on_save_now: Callable[[], None],   # called when "Save Last Capture" pressed
        cfg: dict,
        **kw,
    ) -> None:
        super().__init__(parent, text="  Save", padding=6, **kw)
        self._on_save_now = on_save_now
        self._cfg = cfg
        self._save_mgr: Any = None

        self._folder_var    = tk.StringVar(value=cfg.get("simple_save_path", ""))
        self._auto_save_var = tk.BooleanVar(value=bool(cfg.get("auto_save", False)))
        self._status_var    = tk.StringVar(value="")

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)

        # Row 0 — folder chooser
        tk.Label(self, text="Folder:", bg=BG,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 4))

        self._folder_entry = tk.Entry(
            self, textvariable=self._folder_var,
            state="readonly", font=("Segoe UI", 8),
            readonlybackground="#ececec",
        )
        self._folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))

        self._browse_btn = ttk.Button(self, text="Browse…", width=9,
                                      command=self._browse)
        self._browse_btn.grid(row=0, column=2, sticky="e")

        # Row 1 — auto-save toggle
        self._auto_chk = ttk.Checkbutton(
            self,
            text="Auto-save every capture",
            variable=self._auto_save_var,
            command=self._on_auto_toggle,
        )
        self._auto_chk.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 2))

        # Row 2 — manual save button + status
        btn_row = tk.Frame(self, bg=BG)
        btn_row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(2, 0))

        self._save_btn = ttk.Button(btn_row, text="Save Last Capture",
                                    command=self._on_save_now)
        self._save_btn.pack(side="left", padx=(0, 8))

        tk.Label(btn_row, textvariable=self._status_var,
                 fg="#1b5e20", bg=BG,
                 font=("Segoe UI", 8), anchor="w").pack(side="left", fill="x", expand=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_save_manager(self, mgr: Any) -> None:
        """Attach the SaveManager and sync initial state."""
        self._save_mgr = mgr
        mgr.set_simple_path(self._folder_var.get())
        mgr.auto_save = self._auto_save_var.get()
        self._refresh_folder_display()

    def notify_saved(self, path: Optional[str]) -> None:
        """Update status label after a save (call from main.py after save_capture)."""
        if path:
            self._status_var.set(f"✓ {os.path.basename(path)}")
        else:
            self._status_var.set("⚠ Save failed — check folder")

    def get_values(self) -> dict:
        """Return current save settings for persistence in config."""
        return {
            "simple_save_path": self._folder_var.get(),
            "auto_save":        self._auto_save_var.get(),
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _browse(self) -> None:
        initial = self._folder_var.get() or os.path.expanduser("~")
        chosen = filedialog.askdirectory(
            title="Choose base save folder for Fast Optical Pulses",
            initialdir=initial,
        )
        if chosen:
            self._folder_var.set(chosen)
            if self._save_mgr:
                self._save_mgr.set_simple_path(chosen)
            self._refresh_folder_display()

    def _on_auto_toggle(self) -> None:
        if self._save_mgr:
            self._save_mgr.auto_save = self._auto_save_var.get()

    def _refresh_folder_display(self) -> None:
        """If provider is active show the resolved path (read-only); else show simple path."""
        if self._save_mgr and self._save_mgr._provider:
            resolved = self._save_mgr._resolve_dir()
            if resolved:
                # Show the resolved provider path (greyed out, not editable)
                self._folder_var.set(str(resolved))
                self._browse_btn.configure(state="disabled")
                return
        # Standalone mode — make entry and Browse button active
        self._browse_btn.configure(state="normal")
