"""
Laser FG Scope GUI — Instrument Connection Panel
================================================
Four instrument rows: FG, Laser, Scope, 4200 SMU.
Each row has an address/port entry, a Connect button, and a coloured status dot.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict


def _dot(parent: tk.Widget, color: str = "grey") -> tk.Label:
    """Small coloured circle indicator."""
    return tk.Label(parent, text="●", font=("Segoe UI", 12), fg=color, bg="#f8f8f8")


class ConnectionPanel(ttk.LabelFrame):
    """
    Collapsible instrument connection panel.

    Callbacks dict keys expected:
      connect_fg(address)   → (ok: bool, msg: str)
      connect_laser(port, baud) → (ok, msg)
      connect_scope(address)   → (ok, msg)
      connect_smu(address)     → (ok, msg)
    """

    def __init__(self, parent: tk.Widget, callbacks: Dict[str, Callable], cfg: Dict[str, Any], **kw) -> None:
        super().__init__(parent, text="  Instrument Connections", padding=6, **kw)
        self._cb  = callbacks
        self._cfg = cfg
        self._vars: Dict[str, tk.Variable] = {}
        self._dots: Dict[str, tk.Label] = {}
        self._status_labels: Dict[str, tk.Label] = {}
        self._build()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build(self) -> None:
        bg = "#f8f8f8"

        rows = [
            ("fg",    "Function Generator (VISA):",  self._cfg.get("fg_address",    ""),     None,
             self._connect_fg),
            ("scope", "Oscilloscope (VISA):",         self._cfg.get("scope_address", ""),     None,
             self._connect_scope),
            ("smu",   "Keithley 4200 (GPIB/VISA):",  self._cfg.get("smu_address",   ""),     None,
             self._connect_smu),
            ("laser", "Oxxius Laser (COM port):",     self._cfg.get("laser_port",    "COM4"), None,
             self._connect_laser),
        ]

        for col, text in enumerate(("  ", "Instrument", "Address / Port", "", "")):
            self.columnconfigure(col, weight=1 if col == 2 else 0)

        row_idx = 0
        for key, label_text, default_val, _, connect_fn in rows:
            dot = _dot(self, "grey")
            dot.grid(row=row_idx, column=0, sticky="e", padx=(2, 4), pady=3)
            self._dots[key] = dot

            tk.Label(self, text=label_text, anchor="w", bg=bg).grid(
                row=row_idx, column=1, sticky="w", padx=(0, 6))

            var = tk.StringVar(value=default_val)
            self._vars[key] = var
            entry = ttk.Entry(self, textvariable=var, width=32)
            entry.grid(row=row_idx, column=2, sticky="ew", padx=(0, 4))

            if key == "laser":
                # Baud selector alongside COM port
                baud_var = tk.StringVar(value=str(self._cfg.get("laser_baud", 19200)))
                self._vars["laser_baud"] = baud_var
                baud_menu = ttk.Combobox(self, textvariable=baud_var,
                                         values=["9600", "19200", "38400", "115200"],
                                         width=7, state="readonly")
                baud_menu.grid(row=row_idx, column=3, padx=(0, 4))

            btn = ttk.Button(self, text="Connect", width=9,
                             command=connect_fn)
            btn.grid(row=row_idx, column=4, padx=(0, 2))

            status_lbl = tk.Label(self, text="", anchor="w", bg=bg,
                                  font=("Segoe UI", 8), fg="#555")
            status_lbl.grid(row=row_idx + 1, column=1, columnspan=4,
                            sticky="w", padx=(4, 0), pady=(0, 4))
            self._status_labels[key] = status_lbl

            row_idx += 2

    # ── connect handlers ──────────────────────────────────────────────────────

    def _connect_fg(self) -> None:
        addr = self._vars["fg"].get().strip()
        self._set_status("fg", "Connecting…", "orange")
        self.after(50, lambda: self._do_connect("fg", self._cb.get("connect_fg"), addr))

    def _connect_scope(self) -> None:
        addr = self._vars["scope"].get().strip()
        self._set_status("scope", "Connecting…", "orange")
        self.after(50, lambda: self._do_connect("scope", self._cb.get("connect_scope"), addr))

    def _connect_smu(self) -> None:
        addr = self._vars["smu"].get().strip()
        self._set_status("smu", "Connecting…", "orange")
        self.after(50, lambda: self._do_connect("smu", self._cb.get("connect_smu"), addr))

    def _connect_laser(self) -> None:
        port = self._vars["laser"].get().strip()
        baud = int(self._vars.get("laser_baud", tk.StringVar(value="19200")).get())
        self._set_status("laser", "Connecting…", "orange")
        fn = self._cb.get("connect_laser")
        self.after(50, lambda: self._do_connect_laser(port, baud, fn))

    def _do_connect(self, key: str, fn: Callable | None, *args) -> None:
        if fn is None:
            self._set_status(key, "No handler", "red")
            return
        try:
            ok, msg = fn(*args)
            self._set_status(key, msg, "green" if ok else "red")
        except Exception as exc:
            self._set_status(key, str(exc), "red")

    def _do_connect_laser(self, port: str, baud: int, fn: Callable | None) -> None:
        if fn is None:
            self._set_status("laser", "No handler", "red")
            return
        try:
            ok, msg = fn(port, baud)
            self._set_status("laser", msg, "green" if ok else "red")
        except Exception as exc:
            self._set_status("laser", str(exc), "red")

    # ── status helper ─────────────────────────────────────────────────────────

    def _set_status(self, key: str, msg: str, color: str) -> None:
        if key in self._dots:
            self._dots[key].configure(fg=color)
        if key in self._status_labels:
            short = msg[:80] + ("…" if len(msg) > 80 else "")
            self._status_labels[key].configure(text=short)

    def set_connected(self, key: str, msg: str = "Connected") -> None:
        self._set_status(key, msg, "green")

    def set_disconnected(self, key: str, msg: str = "Disconnected") -> None:
        self._set_status(key, msg, "grey")

    def set_error(self, key: str, msg: str) -> None:
        self._set_status(key, msg, "red")

    # ── getters ───────────────────────────────────────────────────────────────

    def get_values(self) -> Dict[str, Any]:
        return {
            "fg_address":   self._vars["fg"].get().strip(),
            "scope_address": self._vars["scope"].get().strip(),
            "smu_address":  self._vars["smu"].get().strip(),
            "laser_port":   self._vars["laser"].get().strip(),
            "laser_baud":   int(self._vars.get("laser_baud", tk.StringVar(value="19200")).get()),
        }
