"""
Laser FG Scope GUI — Oscilloscope Settings Panel
================================================
Timebase, trigger level/channel, V/div, auto-configure option.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict


class ScopePanel(ttk.LabelFrame):
    """
    Oscilloscope configuration panel.

    All settings feed into params for logic._configure_scope().
    """

    _TIMEBASE_PRESETS = [
        ("10 ns/div",  0.010),
        ("20 ns/div",  0.020),
        ("50 ns/div",  0.050),
        ("100 ns/div", 0.100),
        ("200 ns/div", 0.200),
        ("500 ns/div", 0.500),
        ("1 µs/div",   1.000),
        ("2 µs/div",   2.000),
        ("5 µs/div",   5.000),
        ("10 µs/div",  10.00),
        ("50 µs/div",  50.00),
        ("100 µs/div", 100.0),
        ("1 ms/div",   1000.0),
    ]

    def __init__(self, parent: tk.Widget, cfg: Dict[str, Any], **kw) -> None:
        super().__init__(parent, text="  Oscilloscope Settings (TBS1000C)", padding=6, **kw)
        self._cfg = cfg
        self._vars: Dict[str, tk.Variable] = {}
        self._build()

    def _build(self) -> None:
        bg = "#f8f8f8"

        # ── Auto-configure checkbox ───────────────────────────────────────────
        self._vars["auto_configure_scope"] = tk.BooleanVar(
            value=bool(self._cfg.get("auto_configure_scope", True)))
        ttk.Checkbutton(
            self,
            text="Auto-configure scope before each Run  (applies timebase and trigger settings)",
            variable=self._vars["auto_configure_scope"],
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))

        # ── Auto-timebase checkbox ────────────────────────────────────────────
        self._vars["auto_timebase"] = tk.BooleanVar(
            value=bool(self._cfg.get("auto_timebase", True)))
        ttk.Checkbutton(
            self,
            text="Auto-timebase from burst duration  (overrides Timebase setting below)",
            variable=self._vars["auto_timebase"],
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 4))

        rows = [
            ("Channel:",      "scope_channel",  "int",   self._cfg.get("scope_channel", 1),
             [1, 2, 3, 4], "Oscilloscope channel connected to the DUT. EXT TRIG is always used."),
            ("Timebase:",     "timebase_us",    "combo", self._cfg.get("timebase_us", 0.5),
             [v for _, v in self._TIMEBASE_PRESETS],
             "Horizontal scale in µs/division. Set ~3–5× the expected pulse width."),
            ("Trigger lvl:", "trig_level_v",   "float", self._cfg.get("trig_level_v", 0.1),
             None, "EXT TRIG level in volts. Set to ~50% of FG SYNC OUT amplitude (≈1.5 V)."),
            ("V/div:",        "volts_per_div",  "float", self._cfg.get("volts_per_div", 0.5),
             None, "Vertical scale in V/division. Set to show the expected signal swing."),
            ("Capture wait:", "capture_wait_s", "float", self._cfg.get("capture_wait_s", 0.2),
             None, "Seconds to wait after FG trigger before reading waveform."),
        ]

        for row_i, (label, key, kind, default, choices, tip) in enumerate(rows, start=2):
            tk.Label(self, text=label, anchor="w", bg=bg).grid(
                row=row_i, column=0, sticky="w", padx=(0, 6), pady=2)

            if kind == "int" and choices:
                var = tk.IntVar(value=int(default))
                self._vars[key] = var
                widget = ttk.Combobox(self, textvariable=var,
                                      values=[str(c) for c in choices],
                                      width=8, state="readonly")
            elif kind == "combo" and choices:
                # Timebase: show human-readable but store µs float
                combo_labels  = [lbl for lbl, _ in self._TIMEBASE_PRESETS]
                combo_values  = [v for _, v in self._TIMEBASE_PRESETS]
                closest_idx   = min(range(len(combo_values)),
                                    key=lambda i: abs(combo_values[i] - float(default)))
                self._vars[key] = tk.DoubleVar(value=combo_values[closest_idx])
                display_var      = tk.StringVar(value=combo_labels[closest_idx])

                def _on_change(event: Any, cvals=combo_values, clbls=combo_labels,
                               dv=display_var, sv=self._vars[key]) -> None:
                    txt = dv.get()
                    if txt in clbls:
                        sv.set(cvals[clbls.index(txt)])

                widget = ttk.Combobox(self, textvariable=display_var,
                                      values=combo_labels, width=12, state="readonly")
                widget.bind("<<ComboboxSelected>>", _on_change)
            else:
                var = tk.DoubleVar(value=float(default))
                self._vars[key] = var
                widget = ttk.Spinbox(self, textvariable=var,
                                     from_=-100.0, to=100.0, increment=0.05,
                                     width=10, format="%.4f")

            widget.grid(row=row_i, column=1, sticky="w", padx=(0, 4), pady=2)

            tip_lbl = tk.Label(self, text=tip, fg="#777", bg=bg,
                               font=("Segoe UI", 7), anchor="w", wraplength=180)
            tip_lbl.grid(row=row_i, column=2, sticky="w")

        # ── Trigger source note ───────────────────────────────────────────────
        tk.Label(
            self,
            text=(
                "Trigger source: EXT  (hardware — SDG1032X SYNC OUT BNC → scope EXT TRIG BNC)\n"
                "Single acquisition mode; scope arms before each Run."
            ),
            fg="#555", bg=bg, font=("Segoe UI", 8), justify="left",
        ).grid(row=len(rows) + 2, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def get_values(self) -> Dict[str, Any]:
        return {k: v.get() for k, v in self._vars.items()}
