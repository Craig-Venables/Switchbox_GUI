"""
Laser FG Scope GUI — Function Generator Panel
=============================================
Two-tab notebook:
  Tab 1 — Simple Pulse   : rectangular burst via built-in PULSE waveform
  Tab 2 — ARB Pattern    : custom segment table compiled to binary WVDT upload
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional, Tuple


def _tooltip(widget: tk.Widget, text: str) -> None:
    """Attach a simple tooltip to a widget."""
    tip: Optional[tk.Toplevel] = None

    def show(_ev: Any) -> None:
        nonlocal tip
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + 20
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(tip, text=text, bg="#ffffe0", relief="solid", borderwidth=1,
                 font=("Segoe UI", 8), justify="left", wraplength=260).pack()

    def hide(_ev: Any) -> None:
        nonlocal tip
        if tip:
            tip.destroy()
            tip = None

    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)


class FGPanel(ttk.LabelFrame):
    """
    Function generator configuration — Simple Pulse and ARB Pattern tabs.
    """

    def __init__(self, parent: tk.Widget, cfg: Dict[str, Any], **kw) -> None:
        super().__init__(parent, text="  Function Generator (SDG1032X)", padding=6, **kw)
        self._cfg = cfg
        self._vars: Dict[str, tk.Variable] = {}
        self._arb_rows: List[Tuple[tk.StringVar, tk.DoubleVar]] = []
        self._preview_canvas: Optional[tk.Canvas] = None
        self._build()

    # ── outer notebook ────────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── Manual FG mode toggle (above tabs) ───────────────────────────────
        top = tk.Frame(self, bg="#f8f8f8")
        top.pack(fill="x", pady=(0, 4))
        self._vars["fg_manual_mode"] = tk.BooleanVar(
            value=bool(self._cfg.get("fg_manual_mode", False)))
        self._manual_cb = ttk.Checkbutton(
            top,
            text="Manual FG mode  —  skip configuration, just fire C1:TRIG on Run",
            variable=self._vars["fg_manual_mode"],
            command=self._on_manual_toggle,
        )
        self._manual_cb.pack(anchor="w")
        # Manual-mode warning note — must be a direct child of self so that
        # pack(before=self._nb) works correctly.
        self._manual_note = tk.Label(
            self,
            text=(
                "⚠  Manual mode: GUI will NOT program the FG.\n"
                "Set up the FG front-panel exactly as you want,\n"
                "then press Run to trigger the burst and capture."
            ),
            justify="left", fg="#856404", bg="#fff3cd",
            font=("Segoe UI", 7), wraplength=320, padx=4, pady=2,
        )

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)

        # Show/hide based on saved state (after _nb is packed so before= works)
        if self._vars["fg_manual_mode"].get():
            self._manual_note.pack(fill="x", before=self._nb)

        self._simple_tab = ttk.Frame(self._nb, padding=6)
        self._arb_tab    = ttk.Frame(self._nb, padding=6)

        self._nb.add(self._simple_tab, text=" Simple Pulse ")
        self._nb.add(self._arb_tab,    text=" ARB Pattern ")

        self._build_simple_tab()
        self._build_arb_tab()

        # Restore last active tab
        active_mode = self._cfg.get("fg_mode", "simple")
        if active_mode == "arb":
            self._nb.select(1)

    def _on_manual_toggle(self) -> None:
        manual = self._vars["fg_manual_mode"].get()
        if manual:
            self._manual_note.pack(fill="x", before=self._nb)
        else:
            self._manual_note.pack_forget()
        # ttk.Notebook doesn't accept state= on the widget itself;
        # disable/enable each tab individually instead.
        tab_state = "disabled" if manual else "normal"
        for i in range(self._nb.index("end")):
            self._nb.tab(i, state=tab_state)

    # ── Simple Pulse tab ──────────────────────────────────────────────────────

    def _build_simple_tab(self) -> None:
        bg = "#f8f8f8"
        frm = self._simple_tab

        params = [
            ("High voltage (V):",    "pulse_high_v",   self._cfg.get("pulse_high_v", 3.3),
             "TTL HIGH level. 3.3 V drives the Oxxius DM1 input reliably.", 0.0, 10.0, 0.1),
            ("Low voltage (V):",     "pulse_low_v",    self._cfg.get("pulse_low_v",  0.0),
             "TTL LOW level. 0 V = laser off. Keep ≥0 V.", -2.0, 2.0, 0.1),
            ("Pulse width (ns):",    "pulse_width_ns", self._cfg.get("pulse_width_ns", 100.0),
             "Pulse duration. SDG1032X minimum is 32.6 ns.", 32.6, 1e9, 1.0),
            ("Rep rate (Hz):",       "pulse_rate_hz",  self._cfg.get("pulse_rate_hz", 1000.0),
             "Repetition frequency within a burst. 1 kHz = 1 ms period.", 0.001, 30e6, 100.0),
            ("Burst count (shots):", "burst_count",    self._cfg.get("burst_count",  1),
             "Number of pulses per Run press. 1 = single shot.", 1, 9999, 1),
        ]

        for row_i, (label, key, default, tip, from_, to, inc) in enumerate(params):
            tk.Label(frm, text=label, anchor="w", bg=bg).grid(
                row=row_i, column=0, sticky="w", pady=2)
            var = tk.DoubleVar(value=float(default))
            self._vars[key] = var
            spin = ttk.Spinbox(frm, textvariable=var, from_=from_, to=to,
                               increment=inc, width=12,
                               format="%.3f" if inc < 1 else "%.1f")
            spin.grid(row=row_i, column=1, sticky="w", padx=(4, 0), pady=2)
            _tooltip(spin, tip)

        note = tk.Label(
            frm,
            text=(
                "Output on CH1.  SYNC OUT connector → oscilloscope EXT TRIG.\n"
                "The burst fires with a single software trigger on Run."
            ),
            wraplength=290, justify="left",
            fg="#555", bg=bg, font=("Segoe UI", 8),
        )
        note.grid(row=len(params), column=0, columnspan=2, sticky="w", pady=(6, 0))

    # ── ARB Pattern tab ───────────────────────────────────────────────────────

    def _build_arb_tab(self) -> None:
        bg = "#f8f8f8"
        frm = self._arb_tab

        # ── Info/warning banner ───────────────────────────────────────────────
        banner = tk.Frame(frm, bg="#e8f5e9", relief="flat", bd=1)
        banner.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        tk.Label(
            banner,
            text=(
                "ARB pattern mode: builds a custom multi-segment TTL waveform and uploads it\n"
                "to the SDG1032X using the binary WVDT command (fixed in this version).\n"
                "Each segment has a level (H / L) and a duration in nanoseconds.\n"
                "Min 33 ns per segment at 30 MSa/s, max total 16,384 points."
            ),
            justify="left", bg="#e8f5e9", fg="#1b5e20",
            font=("Segoe UI", 8), padx=6, pady=4,
        ).pack(fill="x")

        # ── Sample rate ───────────────────────────────────────────────────────
        sr_row = tk.Frame(frm, bg=bg)
        sr_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        tk.Label(sr_row, text="Sample rate:", bg=bg).pack(side="left")
        self._vars["arb_sample_rate_msps"] = tk.DoubleVar(
            value=float(self._cfg.get("arb_sample_rate_msps", 10.0)))
        sr_spin = ttk.Spinbox(sr_row,
                              textvariable=self._vars["arb_sample_rate_msps"],
                              from_=0.001, to=30.0, increment=1.0, width=8, format="%.3f")
        sr_spin.pack(side="left", padx=(4, 2))
        tk.Label(sr_row, text="MSa/s  (10 MSa/s → 100 ns/pt, 30 MSa/s → 33 ns/pt)",
                 bg=bg, fg="#555", font=("Segoe UI", 8)).pack(side="left")

        # ── Segment table header ──────────────────────────────────────────────
        for col_i, hdr in enumerate(("Level", "Duration (ns)", "")):
            tk.Label(frm, text=hdr, font=("Segoe UI", 8, "bold"), bg=bg).grid(
                row=2, column=col_i, sticky="w", padx=4)

        # ── Segment rows container ─────────────────────────────────────────────
        self._seg_frame = tk.Frame(frm, bg=bg)
        self._seg_frame.grid(row=3, column=0, columnspan=3, sticky="ew")

        # Pre-populate from config
        saved_segs = self._cfg.get("arb_segments", [["H", 100], ["L", 400]])
        for level, dur_ns in saved_segs:
            self._add_segment_row(level=str(level), dur_ns=float(dur_ns))

        # ── Add / preview buttons ─────────────────────────────────────────────
        btn_row = tk.Frame(frm, bg=bg)
        btn_row.grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 2))
        ttk.Button(btn_row, text="+ Add segment", command=self._add_segment_row).pack(
            side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Preview pattern", command=self._preview).pack(side="left")

        # ── Preview canvas ────────────────────────────────────────────────────
        canvas_frame = tk.LabelFrame(frm, text="Pattern preview", bg=bg, font=("Segoe UI", 8))
        canvas_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4, 0))

        self._preview_canvas = tk.Canvas(canvas_frame, height=60, bg="white",
                                         highlightthickness=0)
        self._preview_canvas.pack(fill="x", padx=4, pady=4)

        # ── Point count label ─────────────────────────────────────────────────
        self._pts_var = tk.StringVar(value="")
        tk.Label(frm, textvariable=self._pts_var, bg=bg,
                 font=("Segoe UI", 8), fg="#555").grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(2, 0))

    def _add_segment_row(self, level: str = "H", dur_ns: float = 100.0) -> None:
        """Add a segment row to the ARB table."""
        bg = "#f8f8f8"
        row_idx = len(self._arb_rows)

        level_var = tk.StringVar(value=level.upper())
        dur_var   = tk.DoubleVar(value=dur_ns)
        self._arb_rows.append((level_var, dur_var))

        level_cb = ttk.Combobox(self._seg_frame, textvariable=level_var,
                                values=["H", "L"], width=4, state="readonly")
        level_cb.grid(row=row_idx, column=0, padx=4, pady=1)

        dur_spin = ttk.Spinbox(self._seg_frame, textvariable=dur_var,
                               from_=33.0, to=1_000_000.0, increment=33.0,
                               width=10, format="%.1f")
        dur_spin.grid(row=row_idx, column=1, padx=4, pady=1)

        def _remove(idx: int = row_idx) -> None:
            self._remove_segment_row(idx)

        ttk.Button(self._seg_frame, text="✕", width=3, command=_remove).grid(
            row=row_idx, column=2, padx=4)

    def _remove_segment_row(self, idx: int) -> None:
        """Remove a segment row (by index in _arb_rows)."""
        if 0 <= idx < len(self._arb_rows):
            self._arb_rows[idx] = None  # mark as deleted
        # Rebuild the segment frame
        for child in self._seg_frame.winfo_children():
            child.destroy()
        live_rows = [r for r in self._arb_rows if r is not None]
        self._arb_rows.clear()
        for level_v, dur_v in live_rows:
            self._add_segment_row(level=level_v.get(), dur_ns=dur_v.get())

    def _preview(self) -> None:
        """Draw the segment pattern on the preview canvas and show point count."""
        canvas = self._preview_canvas
        if canvas is None:
            return
        canvas.delete("all")

        segments = self._get_arb_segments()
        sr_msps  = self._vars["arb_sample_rate_msps"].get()
        sr_hz    = sr_msps * 1e6

        if not segments:
            canvas.create_text(100, 30, text="No segments defined", fill="#888")
            return

        total_ns = sum(d for _, d in segments)
        if total_ns <= 0:
            return

        total_pts = sum(max(1, round(d * 1e-9 * sr_hz)) for _, d in segments)
        self._pts_var.set(
            f"{total_pts} points at {sr_msps:.1f} MSa/s  "
            f"(total {total_ns:.0f} ns).  "
            f"{'⚠ Exceeds 16,384 limit!' if total_pts > 16384 else 'OK'}"
        )

        w = canvas.winfo_width() or 300
        h = 60
        margin = 4
        draw_w = w - 2 * margin
        draw_h = h - 2 * margin

        x = margin
        for level, dur_ns in segments:
            seg_w = draw_w * dur_ns / total_ns
            y_top    = margin + 2
            y_bottom = h - margin - 2
            y_high   = margin + 4
            y_low    = h - margin - 4
            if str(level).upper() in ("H", "HIGH", "1"):
                rect_y = y_high
                rect_h = y_bottom - y_high
                fill = "#1565c0"
            else:
                rect_y = y_low
                rect_h = y_bottom - y_low
                fill = "#90caf9"
            canvas.create_rectangle(x, rect_y, x + seg_w, y_bottom, fill=fill, outline="")
            x += seg_w

        # Draw midline
        canvas.create_line(margin, h // 2, w - margin, h // 2, fill="#ccc", dash=(2, 2))

    # ── accessors ─────────────────────────────────────────────────────────────

    def _get_arb_segments(self) -> List[Tuple[str, float]]:
        return [(lv.get(), dv.get()) for lv, dv in self._arb_rows if lv is not None]

    def get_values(self) -> Dict[str, Any]:
        mode = "arb" if self._nb.index("current") == 1 else "simple"
        segs = self._get_arb_segments()
        sr_msps = self._vars["arb_sample_rate_msps"].get()

        # Build normalised ARB samples from segment table
        arb_samples: List[float] = []
        arb_total_dur_s = 0.0
        if segs:
            from Equipment.Function_Generator.Siglent_SDG1032X import SiglentSDG1032X
            arb_samples = SiglentSDG1032X.build_ttl_pulse_samples(
                segments=[(lv, d * 1e-9) for lv, d in segs],
                sample_rate_hz=sr_msps * 1e6,
            )
            arb_total_dur_s = sum(d * 1e-9 for _, d in segs)

        arb_freq_hz = 1.0 / arb_total_dur_s if arb_total_dur_s > 0 else 1.0
        high_v = float(self._vars.get("pulse_high_v", tk.DoubleVar(value=3.3)).get()
                       if "pulse_high_v" in self._vars else 3.3)

        return {
            "fg_manual_mode":       bool(self._vars["fg_manual_mode"].get()),
            "fg_mode":              mode,
            "pulse_high_v":         float(self._vars.get("pulse_high_v", tk.DoubleVar(value=3.3)).get()
                                          if "pulse_high_v" in self._vars else 3.3),
            "pulse_low_v":          float(self._vars.get("pulse_low_v",  tk.DoubleVar(value=0.0)).get()
                                          if "pulse_low_v" in self._vars else 0.0),
            "pulse_width_ns":       float(self._vars.get("pulse_width_ns", tk.DoubleVar(value=100)).get()
                                          if "pulse_width_ns" in self._vars else 100.0),
            "pulse_rate_hz":        float(self._vars.get("pulse_rate_hz",  tk.DoubleVar(value=1000)).get()
                                          if "pulse_rate_hz" in self._vars else 1000.0),
            "burst_count":          int(self._vars.get("burst_count", tk.DoubleVar(value=1)).get()
                                        if "burst_count" in self._vars else 1),
            "arb_sample_rate_msps": sr_msps,
            "arb_segments":         [[lv, dur] for lv, dur in segs],
            "arb_samples":          arb_samples,
            "arb_freq_hz":          arb_freq_hz,
            "arb_amplitude_v":      high_v,
            "arb_offset_v":         high_v / 2.0,
            "arb_name":             "LSRPULSE",
        }
