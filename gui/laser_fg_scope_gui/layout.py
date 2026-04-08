"""
Laser FG Scope GUI — Layout Composition
=======================================
Three-tab notebook on the left (Controls | Connections | Help)
plus a waveform plot on the right.

Tab layout:
  Controls    — Laser, FG, Scope, Bias, Run  (scrollable)
  Connections — Instrument address + connect buttons
  Help        — Wiring diagram image + documentation text
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict

from .config import COLORS, FONT_FAMILY, FONT_SIZE, LEFT_PANEL_WIDTH
from .ui.connection  import ConnectionPanel
from .ui.laser_panel import LaserPanel
from .ui.fg_panel    import FGPanel
from .ui.scope_panel import ScopePanel
from .ui.bias_panel  import BiasPanel
from .ui.save_panel  import SavePanel
from .ui.help_panel  import HelpPanel
from .ui.plot_panel  import PlotPanel


class LayoutBuilder:
    """
    Builds the full UI and exposes panel references for main.py.

    Accessible after init:
      self.connection_panel
      self.laser_panel
      self.fg_panel
      self.scope_panel
      self.bias_panel
      self.plot_panel
    """

    def __init__(
        self,
        parent: tk.Widget,
        callbacks: Dict[str, Callable],
        cfg: Dict[str, Any],
    ) -> None:
        self._parent    = parent
        self._cb        = callbacks
        self._cfg       = cfg
        self._status_var = tk.StringVar(value="Ready")
        self._run_btn:  ttk.Button = None   # type: ignore
        self._stop_btn: ttk.Button = None   # type: ignore

        # Panel references (populated by _build)
        self.connection_panel: ConnectionPanel = None  # type: ignore
        self.laser_panel:      LaserPanel      = None  # type: ignore
        self.fg_panel:         FGPanel         = None  # type: ignore
        self.scope_panel:      ScopePanel      = None  # type: ignore
        self.bias_panel:       BiasPanel       = None  # type: ignore
        self.save_panel:       SavePanel       = None  # type: ignore
        self.plot_panel:       PlotPanel       = None  # type: ignore

        self._build()

    # ── Main build ────────────────────────────────────────────────────────────

    def _build(self) -> None:
        parent = self._parent
        bg = COLORS["bg"]

        # ── Outer pane: [left notebook] | [right plot] ────────────────────────
        paned = tk.PanedWindow(parent, orient="horizontal", bg=bg,
                               sashrelief="raised", sashwidth=5)
        paned.pack(fill="both", expand=True)

        # ── LEFT — three-tab notebook ─────────────────────────────────────────
        left_frame = tk.Frame(paned, width=LEFT_PANEL_WIDTH, bg=bg)
        left_frame.pack_propagate(False)
        paned.add(left_frame, minsize=300, stretch="never")

        self._notebook = ttk.Notebook(left_frame)
        self._notebook.pack(fill="both", expand=True)

        self._build_controls_tab()
        self._build_connections_tab()
        self._build_help_tab()

        # ── RIGHT — waveform plot ─────────────────────────────────────────────
        right_frame = tk.Frame(paned, bg=bg)
        paned.add(right_frame, minsize=500, stretch="always")

        self.plot_panel = PlotPanel(right_frame)
        self.plot_panel.pack(fill="both", expand=True)

        # ── Status bar ────────────────────────────────────────────────────────
        status_bar = tk.Frame(parent, bg="#e0e0e0", relief="sunken", height=22)
        status_bar.pack(side="bottom", fill="x")
        tk.Label(status_bar, textvariable=self._status_var,
                 anchor="w", bg="#e0e0e0",
                 font=(FONT_FAMILY, FONT_SIZE)).pack(side="left", padx=6)

    # ── Tab 1: Controls ───────────────────────────────────────────────────────

    def _build_controls_tab(self) -> None:
        """Scrollable frame with Laser, FG, Scope, Bias, Run controls."""
        outer = ttk.Frame(self._notebook)
        self._notebook.add(outer, text="  Controls  ")

        canvas    = tk.Canvas(outer, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORS["bg"])

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse-wheel scrolling
        def _on_mousewheel(event: Any) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._populate_controls(scroll_frame)

    def _populate_controls(self, parent: tk.Frame) -> None:
        bg  = COLORS["bg"]
        pad = {"fill": "x", "padx": 6, "pady": 4}

        # Header strip
        header = tk.Frame(parent, bg=COLORS["header"])
        header.pack(fill="x", pady=(0, 4))
        tk.Label(
            header,
            text="Laser  ·  Function Generator  ·  Oscilloscope",
            font=(FONT_FAMILY, 10, "bold"),
            fg=COLORS["header_fg"], bg=COLORS["header"],
            padx=8, pady=5,
        ).pack(side="left")

        # Laser
        self.laser_panel = LaserPanel(parent, self._cb, self._cfg)
        self.laser_panel.pack(**pad)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=6, pady=2)

        # Function generator
        self.fg_panel = FGPanel(parent, self._cfg)
        self.fg_panel.pack(**pad)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=6, pady=2)

        # Scope
        self.scope_panel = ScopePanel(parent, self._cfg)
        self.scope_panel.pack(**pad)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=6, pady=2)

        # SMU bias
        self.bias_panel = BiasPanel(parent, self._cb, self._cfg)
        self.bias_panel.pack(**pad)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=6, pady=2)

        # Save location
        self.save_panel = SavePanel(
            parent,
            on_save_now=self._cb.get("save_now", lambda: None),
            cfg=self._cfg,
        )
        self.save_panel.pack(**pad)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=6, pady=2)

        # Run controls
        run_lf = ttk.LabelFrame(parent, text="  Run", padding=6)
        run_lf.pack(**pad)

        btn_row = tk.Frame(run_lf, bg=bg)
        btn_row.pack(fill="x", pady=(2, 4))

        self._run_btn = ttk.Button(
            btn_row, text="▶  Run",
            command=self._cb.get("run", lambda: None),
            style="Accent.TButton",
        )
        self._run_btn.pack(side="left", padx=(0, 8), ipadx=8)

        self._stop_btn = ttk.Button(
            btn_row, text="■  Stop",
            command=self._cb.get("stop", lambda: None),
            state="disabled",
        )
        self._stop_btn.pack(side="left")

        tk.Label(run_lf, textvariable=self._status_var,
                 anchor="w", bg=bg, fg="#333",
                 font=(FONT_FAMILY, 8), wraplength=290).pack(fill="x", padx=2)

    # ── Tab 2: Connections ────────────────────────────────────────────────────

    def _build_connections_tab(self) -> None:
        outer = ttk.Frame(self._notebook, padding=8)
        self._notebook.add(outer, text="  Connections  ")

        self.connection_panel = ConnectionPanel(outer, self._cb, self._cfg)
        self.connection_panel.pack(fill="x")

        # Quick-reference note
        note = tk.Label(
            outer,
            text=(
                "Connect all four instruments before pressing Run.\n"
                "See the Help tab for the wiring diagram."
            ),
            justify="left", fg="#555",
            font=(FONT_FAMILY, 8), wraplength=320,
        )
        note.pack(anchor="w", pady=(10, 0))

    # ── Tab 3: Help ───────────────────────────────────────────────────────────

    def _build_help_tab(self) -> None:
        outer = ttk.Frame(self._notebook)
        self._notebook.add(outer, text="  Help  ")

        self.help_panel = HelpPanel(outer)
        self.help_panel.pack(fill="both", expand=True)

    # ── Helpers called by main.py ─────────────────────────────────────────────

    def set_status(self, msg: str) -> None:
        self._status_var.set(msg)

    def set_running(self, running: bool) -> None:
        if self._run_btn:
            self._run_btn.configure(state="disabled" if running else "normal")
        if self._stop_btn:
            self._stop_btn.configure(state="normal" if running else "disabled")

    def collect_params(self) -> dict:
        params: dict = {}
        for panel in (self.connection_panel, self.laser_panel,
                      self.fg_panel, self.scope_panel, self.bias_panel,
                      self.save_panel):
            try:
                params.update(panel.get_values())
            except Exception:
                pass
        return params
