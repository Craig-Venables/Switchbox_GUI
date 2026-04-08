"""
Laser FG Scope GUI — 4200 SMU Bias Panel
=========================================
DC bias voltage entry, compliance, apply/off buttons.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict


class BiasPanel(ttk.LabelFrame):
    """
    Controls the Keithley 4200 SMU as a passive DC bias source.

    Expected callbacks:
      apply_bias(voltage, compliance)  → (ok, msg)
      bias_off()
    """

    def __init__(self, parent: tk.Widget, callbacks: Dict[str, Callable], cfg: Dict[str, Any], **kw) -> None:
        super().__init__(parent, text="  4200 SMU Bias", padding=6, **kw)
        self._cb  = callbacks
        self._cfg = cfg
        self._vars: Dict[str, tk.Variable] = {}
        self._build()

    def _build(self) -> None:
        bg = "#f8f8f8"

        params = [
            ("Bias voltage (V):",    "bias_v",          self._cfg.get("bias_v", 0.0),
             -200.0, 200.0, 0.1, "%.4f",
             "DC voltage applied to the DUT. Common range: ±0.5 V to ±5 V."),
            ("Compliance (A):",      "bias_compliance", self._cfg.get("bias_compliance", 1e-3),
             0.0, 1.0, 1e-4, "%.2e",
             "Maximum current the SMU will source. Protects the device."),
        ]

        for row_i, (label, key, default, from_, to, inc, fmt, tip) in enumerate(params):
            tk.Label(self, text=label, anchor="w", bg=bg).grid(
                row=row_i, column=0, sticky="w", padx=(0, 6), pady=2)
            var = tk.DoubleVar(value=float(default))
            self._vars[key] = var
            spin = ttk.Spinbox(self, textvariable=var, from_=from_, to=to,
                               increment=inc, width=12, format=fmt)
            spin.grid(row=row_i, column=1, sticky="w", pady=2)
            tip_lbl = tk.Label(self, text=tip, fg="#777", bg=bg,
                               font=("Segoe UI", 7), anchor="w", wraplength=160)
            tip_lbl.grid(row=row_i, column=2, sticky="w", padx=(6, 0))

        # ── Channel ───────────────────────────────────────────────────────────
        tk.Label(self, text="SMU channel:", anchor="w", bg=bg).grid(
            row=len(params), column=0, sticky="w", pady=2)
        self._vars["smu_channel"] = tk.IntVar(value=int(self._cfg.get("smu_channel", 1)))
        ch_cb = ttk.Combobox(self, textvariable=self._vars["smu_channel"],
                             values=["1", "2", "3", "4"], width=4, state="readonly")
        ch_cb.grid(row=len(params), column=1, sticky="w", pady=2)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=bg)
        btn_row.grid(row=len(params) + 1, column=0, columnspan=3, sticky="w", pady=(4, 2))

        self._apply_btn = ttk.Button(btn_row, text="Apply Bias", command=self._on_apply)
        self._apply_btn.pack(side="left", padx=(0, 6))

        self._off_btn = ttk.Button(btn_row, text="Output OFF", command=self._on_off)
        self._off_btn.pack(side="left")

        # Status
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var, fg="#555", bg=bg,
                 font=("Segoe UI", 8)).grid(
            row=len(params) + 2, column=0, columnspan=3, sticky="w", pady=(0, 2))

    def _on_apply(self) -> None:
        fn = self._cb.get("apply_bias")
        if fn is None:
            self._status_var.set("No handler registered.")
            return
        bias_v    = self._vars["bias_v"].get()
        bias_comp = self._vars["bias_compliance"].get()
        try:
            ok, msg = fn(bias_v, bias_comp)
            self._status_var.set(msg)
        except Exception as exc:
            self._status_var.set(str(exc))

    def _on_off(self) -> None:
        fn = self._cb.get("bias_off")
        if fn:
            try:
                fn()
                self._status_var.set("Output OFF")
            except Exception as exc:
                self._status_var.set(str(exc))

    def get_values(self) -> Dict[str, Any]:
        return {k: v.get() for k, v in self._vars.items()}
