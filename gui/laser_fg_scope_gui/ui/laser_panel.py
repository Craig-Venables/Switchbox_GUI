"""
Laser FG Scope GUI — Laser Control Panel
=========================================
Controls for the Oxxius LBX-405 in DM1 (TTL-gate) mode.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict


class LaserPanel(ttk.LabelFrame):
    """
    Laser settings: power entry, Arm / Disarm buttons, status.

    Expected callbacks:
      arm_laser(power_mw)   → (ok, msg)
      disarm_laser()        → (ok, msg)
    """

    def __init__(self, parent: tk.Widget, callbacks: Dict[str, Callable], cfg: Dict[str, Any], **kw) -> None:
        super().__init__(parent, text="  Laser Settings (Oxxius LBX-405 — DM1 mode)", padding=6, **kw)
        self._cb  = callbacks
        self._cfg = cfg
        self._vars: Dict[str, tk.Variable] = {}
        self._armed = False
        self._build()

    def _build(self) -> None:
        bg = "#f8f8f8"

        # ── Power row ────────────────────────────────────────────────────────
        pwr_row = tk.Frame(self, bg=bg)
        pwr_row.pack(fill="x", padx=2, pady=(4, 2))

        tk.Label(pwr_row, text="Set power:", bg=bg).pack(side="left")

        self._vars["power_mw"] = tk.DoubleVar(value=float(self._cfg.get("laser_power_mw", 10.0)))
        spin = ttk.Spinbox(
            pwr_row,
            textvariable=self._vars["power_mw"],
            from_=0.5, to=300.0, increment=0.5,
            width=8, format="%.1f",
        )
        spin.pack(side="left", padx=(4, 2))
        tk.Label(pwr_row, text="mW", bg=bg).pack(side="left")

        # Safety note
        tk.Label(
            pwr_row,
            text="  ⚠ Class 3B — wear goggles",
            fg="#c62828", bg=bg, font=("Segoe UI", 8),
        ).pack(side="left", padx=(10, 0))

        # ── Arm / Disarm buttons ─────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=bg)
        btn_row.pack(fill="x", padx=2, pady=(2, 4))

        self._arm_btn = ttk.Button(btn_row, text="Arm DM1  (enable TTL gate)",
                                   command=self._on_arm)
        self._arm_btn.pack(side="left", padx=(0, 6))

        self._disarm_btn = ttk.Button(btn_row, text="Disarm  (emission off)",
                                      command=self._on_disarm, state="disabled")
        self._disarm_btn.pack(side="left")

        # ── Status row ───────────────────────────────────────────────────────
        status_row = tk.Frame(self, bg=bg)
        status_row.pack(fill="x", padx=2, pady=(0, 2))

        self._dot = tk.Label(status_row, text="●", font=("Segoe UI", 12),
                             fg="grey", bg=bg)
        self._dot.pack(side="left")

        self._status_var = tk.StringVar(value="Not armed")
        tk.Label(status_row, textvariable=self._status_var,
                 anchor="w", bg=bg, font=("Segoe UI", 8), fg="#555").pack(
            side="left", padx=(4, 0))

        # ── Explanation label ─────────────────────────────────────────────────
        info_text = (
            "Arm: sets power over serial, enables DM1 mode. Laser emission is then gated "
            "by TTL from function generator CH1. Fire with Run below."
        )
        tk.Label(
            self, text=info_text, wraplength=290,
            justify="left", fg="#555", bg=bg, font=("Segoe UI", 8),
        ).pack(fill="x", padx=4, pady=(0, 2))

    def _on_arm(self) -> None:
        fn = self._cb.get("arm_laser")
        if fn is None:
            self._set_status("No arm handler registered", "red")
            return
        power = self._vars["power_mw"].get()
        self._set_status("Arming…", "orange")
        self.after(50, lambda: self._do_arm(fn, power))

    def _do_arm(self, fn: Callable, power: float) -> None:
        try:
            ok, msg = fn(power)
            color = "green" if ok else "red"
            self._armed = ok
            self._arm_btn.configure(state="disabled" if ok else "normal")
            self._disarm_btn.configure(state="normal" if ok else "disabled")
            self._set_status(msg, color)
        except Exception as exc:
            self._set_status(str(exc), "red")

    def _on_disarm(self) -> None:
        fn = self._cb.get("disarm_laser")
        if fn is None:
            return
        try:
            ok, msg = fn()
            self._armed = False
            self._arm_btn.configure(state="normal")
            self._disarm_btn.configure(state="disabled")
            self._set_status(msg, "grey")
        except Exception as exc:
            self._set_status(str(exc), "red")

    def _set_status(self, msg: str, color: str) -> None:
        self._dot.configure(fg=color)
        self._status_var.set(msg[:90])

    def get_values(self) -> Dict[str, Any]:
        return {"laser_power_mw": self._vars["power_mw"].get()}

    def is_armed(self) -> bool:
        return self._armed
