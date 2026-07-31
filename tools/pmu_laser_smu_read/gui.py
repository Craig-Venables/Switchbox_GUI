"""Standalone tkinter GUI: PMU CH1 TTL laser + SMU continuous resistance read."""

from __future__ import annotations

import csv
import io
import json
import math
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

from matplotlib import cm
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from gui.sample_gui.config import resolve_default_save_root
except Exception:  # pragma: no cover - fall back if the main app package moves
    def resolve_default_save_root() -> Path:
        root = Path.home() / "OneDrive - The University of Nottingham" / "Documents" / "Data_folder"
        root.mkdir(parents=True, exist_ok=True)
        return root

# Shared lab data root (OneDrive Documents\Data_folder) — same root the main
# Sample/Measurement GUIs use, so samples created there show up here too.
# Data for this tool is nested per-device as <sample>/<section>/<device>/<TEST_TYPE_FOLDER_NAME>.
DEFAULT_DATA_ROOT = resolve_default_save_root()
TEST_TYPE_FOLDER_NAME = "PMU_Laser_SMU_Testing"
SECTION_LETTERS = list("ABCDEFGHIJKL")
DEVICE_NUMBERS = [str(i) for i in range(1, 11)]
_OLD_DEFAULT_SAVE = Path.home() / "Documents" / "data" / "pmu_laser_smu_read"
_OLD_TOOL_DATA_ROOT = DEFAULT_DATA_ROOT / "pmu_laser_smu_read"

try:
    from waveform import (
        MAX_TTL_VHIGH,
        DecayName,
        ModeName,
        build_preview,
        ensure_period_s,
        format_width_s,
        plan_cooldown,
        preview_polyline,
    )
    from runner import (
        PmuLaserSmuStreamSession,
        run_pmu_laser_smu_read,
        test_kxci_connection,
    )
    from routine import (
        RoutineStep,
        build_routine_plan,
        describe_plan,
        format_time_compact,
        format_width_list,
        generate_decade_widths,
        generate_power_levels,
        parse_width_list,
    )
except ImportError:
    from tools.pmu_laser_smu_read.waveform import (
        MAX_TTL_VHIGH,
        DecayName,
        ModeName,
        build_preview,
        ensure_period_s,
        format_width_s,
        plan_cooldown,
        preview_polyline,
    )
    from tools.pmu_laser_smu_read.runner import (
        PmuLaserSmuStreamSession,
        run_pmu_laser_smu_read,
        test_kxci_connection,
    )
    from tools.pmu_laser_smu_read.routine import (
        RoutineStep,
        build_routine_plan,
        describe_plan,
        format_time_compact,
        format_width_list,
        generate_decade_widths,
        generate_power_levels,
        parse_width_list,
    )

try:
    from Equipment.Laser_Controller.oxxius import OxxiusLaser
except Exception:  # pragma: no cover - optional dep (pyserial) may be missing
    OxxiusLaser = None  # type: ignore[assignment,misc]

import queue


class PmuLaserSmuReadGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PMU TTL Laser + SMU Read")
        self.root.geometry("1280x860")

        self.config_path = _SCRIPT_DIR / "pmu_laser_smu_config.json"
        self.save_dir = DEFAULT_DATA_ROOT
        self.sample_default = "untitled"
        self.last_result: Optional[Dict[str, Any]] = None
        self.last_params: Optional[Dict[str, Any]] = None
        self._running = False

        self._inset_ax = None

        # Laser (serial, Oxxius) — shared across the Automated Routine tab.
        self.laser: Optional[Any] = None

        self._load_config()
        self._build()
        self._on_mode_change()
        self._update_preview()
        self._update_points_estimate()

    def _load_config(self) -> None:
        self.gpib_default = "GPIB0::17::INSTR"
        self.pmu_id_default = "PMU1"
        self.routine_settle_default = "5.0"
        self.routine_interval_default = "5.0"
        self.routine_start_pct_default = "10"
        self.routine_step_pct_default = "10"
        self.routine_max_pct_default = "100"
        self.routine_widths_default = "100 ns, 1000 ns, 10000 ns, 100000 ns"
        self.section_default = "A"
        self.device_default = "1"
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.gpib_default = data.get("gpib_address", self.gpib_default)
                self.pmu_id_default = data.get("pmu_id", self.pmu_id_default)
                self.sample_default = data.get("sample_name", self.sample_default) or "untitled"
                self.section_default = data.get("section", self.section_default) or "A"
                self.device_default = str(data.get("device_number", self.device_default) or "1")
                self.routine_settle_default = str(
                    data.get("routine_settle_s", self.routine_settle_default)
                )
                self.routine_interval_default = str(
                    data.get("routine_interval_s", self.routine_interval_default)
                )
                self.routine_start_pct_default = str(
                    data.get("routine_start_pct", self.routine_start_pct_default)
                )
                self.routine_step_pct_default = str(
                    data.get("routine_step_pct", self.routine_step_pct_default)
                )
                self.routine_max_pct_default = str(
                    data.get("routine_max_pct", self.routine_max_pct_default)
                )
                if data.get("routine_widths"):
                    self.routine_widths_default = str(data["routine_widths"])
                save = data.get("save_dir")
                if save:
                    save_path = Path(save)
                    # Migrate away from old local/tool-specific save-root defaults —
                    # the shared Data_folder root is now the default, with
                    # sample/section/device appended per-save instead.
                    try:
                        resolved = save_path.resolve()
                        if resolved in (_OLD_DEFAULT_SAVE.resolve(), _OLD_TOOL_DATA_ROOT.resolve()):
                            save_path = DEFAULT_DATA_ROOT
                    except Exception:
                        pass
                    self.save_dir = save_path
            except Exception:
                pass

    def _save_config(self) -> None:
        payload = {
            "gpib_address": self.gpib_var.get().strip(),
            "pmu_id": self.pmu_id_var.get().strip(),
            "save_dir": str(self.save_dir),
            "sample_name": self.sample_var.get().strip() or "untitled",
            "section": self.section_var.get().strip() if hasattr(self, "section_var") else self.section_default,
            "device_number": self.device_var.get().strip() if hasattr(self, "device_var") else self.device_default,
        }
        # Routine timing / levels (may not exist until tab is built)
        if hasattr(self, "routine_settle_var"):
            payload["routine_settle_s"] = self.routine_settle_var.get().strip()
            payload["routine_interval_s"] = self.routine_interval_var.get().strip()
            payload["routine_start_pct"] = self.routine_start_power_var.get().strip()
            payload["routine_step_pct"] = self.routine_power_step_var.get().strip()
            payload["routine_max_pct"] = self.routine_power_max_var.get().strip()
            payload["routine_widths"] = self.routine_widths_var.get().strip()
        try:
            self.config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _make_scrollable(self, parent: tk.Misc) -> ttk.Frame:
        """Canvas + interior frame with vertical scrollbar (Windows MouseWheel).

        Returns the interior frame — pack widgets into it. The outer container
        fills ``parent``. Matches the left-panel scroll pattern used elsewhere
        in this repo (e.g. pulse_testing layout_classic).
        """
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        interior = ttk.Frame(canvas, padding=4)

        window_id = canvas.create_window((0, 0), window=interior, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event: tk.Event) -> None:
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass

        def _bind_tree(widget: tk.Misc) -> None:
            # Re-bind on Configure so newly packed children (mode blocks,
            # collapsible sections) also receive MouseWheel when hovered.
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                _bind_tree(child)

        def _on_interior_configure(_event: Optional[tk.Event] = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            _bind_tree(interior)

        def _on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=max(int(event.width), 1))

        interior.bind("<Configure>", _on_interior_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return interior

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="GPIB:").pack(side=tk.LEFT)
        self.gpib_var = tk.StringVar(value=self.gpib_default)
        ttk.Entry(top, textvariable=self.gpib_var, width=22).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Test GPIB", command=self._test_gpib).pack(side=tk.LEFT, padx=2)

        ttk.Label(top, text="Sample:").pack(side=tk.LEFT, padx=(10, 0))
        self.sample_var = tk.StringVar(value=self.sample_default)
        self.sample_combo = ttk.Combobox(
            top, textvariable=self.sample_var, width=16, values=self._discover_samples()
        )
        self.sample_combo.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="\u21bb", width=2, command=self._refresh_sample_list).pack(
            side=tk.LEFT
        )

        ttk.Label(top, text="Section:").pack(side=tk.LEFT, padx=(10, 0))
        self.section_var = tk.StringVar(value=self.section_default)
        ttk.Combobox(
            top,
            textvariable=self.section_var,
            width=3,
            values=SECTION_LETTERS,
            state="readonly",
        ).pack(side=tk.LEFT, padx=4)

        ttk.Label(top, text="Device #:").pack(side=tk.LEFT, padx=(6, 0))
        self.device_var = tk.StringVar(value=self.device_default)
        ttk.Combobox(
            top,
            textvariable=self.device_var,
            width=4,
            values=DEVICE_NUMBERS,
            state="readonly",
        ).pack(side=tk.LEFT, padx=4)

        ttk.Label(top, text="Save root:").pack(side=tk.LEFT, padx=(10, 0))
        self.save_var = tk.StringVar(value=str(self.save_dir))
        ttk.Entry(top, textvariable=self.save_var, width=36).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Browse", command=self._browse_save).pack(side=tk.LEFT)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        run_tab = ttk.Frame(self.notebook)
        live_tab = ttk.Frame(self.notebook)
        routine_tab = ttk.Frame(self.notebook)
        self.notebook.add(live_tab, text="Live / Manual Fire")
        self.notebook.add(routine_tab, text="Automated Routine")
        self.notebook.add(run_tab, text="Single-shot Run")

        body = ttk.Panedwindow(run_tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left_host = ttk.Frame(body)
        right = ttk.Frame(body, padding=4)
        body.add(left_host, weight=1)
        body.add(right, weight=2)
        left = self._make_scrollable(left_host)

        # Wiring
        wire = ttk.LabelFrame(left, text="Wiring", padding=6)
        wire.pack(fill=tk.X, pady=4)
        ttk.Label(
            wire,
            text=(
                "PMU → RPM → laser TTL (pulse only)\n"
                "SMU cables → device directly (no RPM)\n"
                "PMU CH2 → leave unconnected\n"
                "One GPIB owner only — close other tools"
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        ttk.Button(wire, text="Wiring diagram / RPM help…", command=self._show_wiring_help).pack(
            anchor=tk.W, pady=(6, 0)
        )
        self.pmu_id_var = tk.StringVar(value=self.pmu_id_default)
        pmu_id_row = ttk.Frame(wire)
        pmu_id_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(pmu_id_row, text="PMU_ID (KCON name)", width=22).pack(side=tk.LEFT)
        ttk.Entry(pmu_id_row, textvariable=self.pmu_id_var, width=14).pack(side=tk.LEFT)
        ttk.Label(
            wire,
            text=(
                "If a run fails with 'pmu_ttl_laser_ch1 returned -2', it means\n"
                "LPTIsInCurrentConfiguration(PMU_ID) failed. Most likely the PMU\n"
                "card's name in KCON (on the 4200) doesn't match this field —\n"
                "open KCON and use the exact PMU card name shown there\n"
                "(commonly 'PMU1'). See tools/pmu_laser_smu_read/README.md."
            ),
            justify=tk.LEFT,
            foreground="#8a4b00",
        ).pack(anchor=tk.W, pady=(4, 0))

        # SMU
        smu = ttk.LabelFrame(left, text="SMU continuous read", padding=6)
        smu.pack(fill=tk.X, pady=4)
        self.vread_var = tk.StringVar(value="0.2")
        self.ilimit_var = tk.StringVar(value="1e-4")
        self.irange_var = tk.StringVar(value="0")
        self.capture_var = tk.StringVar(value="2.0")
        self.pre_capture_var = tk.StringVar(value="0.5")
        self.dt_var = tk.StringVar(value="0.01")
        self._row(smu, "Vread (V)", self.vread_var)
        self._row(smu, "Ilimit (A)", self.ilimit_var)
        self._row(smu, "Current range (A)", self.irange_var)
        ttk.Label(
            smu,
            text="SMU1 current MEASUREMENT range (separate from Ilimit above).\n"
            "0 or blank = Autorange. Set a fixed value (e.g. 1e-6) for\n"
            "lower-noise/faster reads once you know roughly what current\n"
            "to expect.",
            foreground="#555555",
            font=("TkDefaultFont", 7),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=(22, 0))

        self._row(smu, "Pre-laser baseline (s)", self.pre_capture_var)
        ttk.Label(
            smu,
            text="How long to read the SMU BEFORE the laser fires (baseline). 0 = skip.",
            foreground="#555555",
            font=("TkDefaultFont", 7),
        ).pack(anchor=tk.W, padx=(22, 0))
        pre_preset_row = ttk.Frame(smu)
        pre_preset_row.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(pre_preset_row, text="", width=22).pack(side=tk.LEFT)
        for secs in (0, 0.1, 0.5, 1, 2, 5):
            ttk.Button(
                pre_preset_row,
                text=f"{secs}s",
                width=4,
                command=lambda s=secs: self._set_pre_capture(s),
            ).pack(side=tk.LEFT, padx=1)

        self._row(smu, "Post-laser capture (s)", self.capture_var)

        preset_row = ttk.Frame(smu)
        preset_row.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(preset_row, text="", width=22).pack(side=tk.LEFT)
        for secs in (2, 5, 10, 30, 60, 120, 300):
            ttk.Button(
                preset_row,
                text=f"{secs}s",
                width=4,
                command=lambda s=secs: self._set_capture(s),
            ).pack(side=tk.LEFT, padx=1)

        self._row(smu, "Sample dt (s)", self.dt_var)

        self.points_est_var = tk.StringVar(value="")
        ttk.Label(
            smu, textvariable=self.points_est_var, foreground="#555555"
        ).pack(anchor=tk.W, pady=(2, 0))
        for var in (self.capture_var, self.pre_capture_var, self.dt_var):
            var.trace_add("write", lambda *_: self._update_points_estimate())

        # PMU
        pmu = ttk.LabelFrame(left, text="PMU CH1 TTL", padding=6)
        pmu.pack(fill=tk.X, pady=4)
        self.vhigh_var = tk.StringVar(value="5.0")
        self.width_us_var = tk.StringVar(value="10")
        self.rise_ns_var = tk.StringVar(value="100")
        self.fall_ns_var = tk.StringVar(value="100")
        self.delay_ms_var = tk.StringVar(value="50")
        self.fire_delay_ms_var = tk.StringVar(value="100")
        self._row(pmu, "Vhigh (V)", self.vhigh_var)
        self._row(pmu, "Width (µs)", self.width_us_var)
        self._row(pmu, "Rise (ns)", self.rise_ns_var)
        self._row(pmu, "Fall (ns)", self.fall_ns_var)
        self._row(pmu, "PMU delay before (ms)", self.delay_ms_var)
        self._row(pmu, "Fire after Collect start (ms)", self.fire_delay_ms_var)

        # Mode
        mode_fr = ttk.LabelFrame(left, text="Pulse mode", padding=6)
        mode_fr.pack(fill=tk.X, pady=4)
        self.mode_var = tk.StringVar(value="single")
        self.decay_var = tk.StringVar(value="linear")
        self.cooldown_span_us_var = tk.StringVar(value="1000")
        self.cooldown_info_var = tk.StringVar(value="")
        for label, val in (
            ("Single", "single"),
            ("Train", "train"),
            ("Cool-down", "cooldown"),
        ):
            ttk.Radiobutton(
                mode_fr,
                text=label,
                value=val,
                variable=self.mode_var,
                command=self._on_mode_change,
            ).pack(anchor=tk.W)

        self.mode_params = ttk.Frame(mode_fr)
        self.mode_params.pack(fill=tk.X, pady=4)
        self.period_us_var = tk.StringVar(value="100")
        self.num_pulses_var = tk.StringVar(value="10")
        # Legacy vars kept for config compatibility; cool-down now plans these.
        self.start_period_us_var = tk.StringVar(value="100")
        self.end_period_us_var = tk.StringVar(value="1000")

        self.period_row = self._row(self.mode_params, "Period (µs)", self.period_us_var)
        self.npulses_row = self._row(self.mode_params, "Num pulses", self.num_pulses_var)

        self.cooldown_block = ttk.Frame(self.mode_params)
        self._row(self.cooldown_block, "Cool-down over (µs)", self.cooldown_span_us_var)
        decay_row = ttk.Frame(self.cooldown_block)
        decay_row.pack(fill=tk.X, pady=1)
        ttk.Label(decay_row, text="Decay type", width=22).pack(side=tk.LEFT)
        self.decay_combo = ttk.Combobox(
            decay_row,
            textvariable=self.decay_var,
            values=("linear", "exponential", "quadratic"),
            state="readonly",
            width=12,
        )
        self.decay_combo.pack(side=tk.LEFT)
        self.decay_combo.bind("<<ComboboxSelected>>", lambda *_: self._on_cooldown_change())
        ttk.Label(
            self.cooldown_block,
            textvariable=self.cooldown_info_var,
            foreground="#555555",
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(2, 2))
        self.cd_fig = Figure(figsize=(3.2, 1.35), dpi=100)
        self.cd_ax = self.cd_fig.add_subplot(111)
        self.cd_fig.subplots_adjust(left=0.14, right=0.98, top=0.88, bottom=0.28)
        self.cd_canvas = FigureCanvasTkAgg(self.cd_fig, master=self.cooldown_block)
        self.cd_canvas.get_tk_widget().pack(fill=tk.X, pady=(2, 0))

        btns = ttk.Frame(left)
        btns.pack(fill=tk.X, pady=8)
        self.run_btn = ttk.Button(btns, text="Run", command=self._run)
        self.run_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Preview", command=self._update_preview).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="Dry-run EX", command=self._dry_run).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="Save CSV", command=self._save_csv).pack(
            side=tk.LEFT, padx=2
        )

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(left, textvariable=self.status_var, wraplength=360).pack(
            fill=tk.X, pady=4
        )

        # Plots
        self.fig = Figure(figsize=(7.5, 7), dpi=100)
        self.ax_ttl = self.fig.add_subplot(211)
        self.ax_r = self.fig.add_subplot(212)
        self.fig.tight_layout(pad=2.0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        for var in (
            self.width_us_var,
            self.period_us_var,
            self.num_pulses_var,
            self.cooldown_span_us_var,
            self.vhigh_var,
            self.decay_var,
        ):
            var.trace_add("write", lambda *_: self.root.after(200, self._update_preview))

        self._build_live_tab(live_tab)
        self._build_routine_tab(routine_tab)
        self._on_mode_change()

    def _row(self, parent: tk.Misc, label: str, var: tk.StringVar) -> ttk.Frame:
        fr = ttk.Frame(parent)
        fr.pack(fill=tk.X, pady=1)
        ttk.Label(fr, text=label, width=22).pack(side=tk.LEFT)
        ttk.Entry(fr, textvariable=var, width=14).pack(side=tk.LEFT)
        return fr

    def _collapsible_section(
        self,
        parent: tk.Misc,
        title: str,
        *,
        expanded: bool = False,
    ) -> ttk.Frame:
        """Pack a header button that shows/hides a body frame. Returns the body."""
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.X, pady=4)

        state = {"expanded": bool(expanded)}
        body = ttk.Frame(outer, padding=(4, 2, 4, 4))

        def refresh() -> None:
            if state["expanded"]:
                toggle.configure(text=f"▼ {title}")
                body.pack(fill=tk.X)
            else:
                toggle.configure(text=f"▶ {title}")
                body.pack_forget()

        def on_toggle() -> None:
            state["expanded"] = not state["expanded"]
            refresh()

        toggle = ttk.Button(outer, command=on_toggle)
        toggle.pack(fill=tk.X)
        refresh()
        return body

    def _show_wiring_help(self) -> None:
        try:
            from wiring_help import WIRING_HELP_TEXT, draw_wiring_diagram
        except ImportError:
            from tools.pmu_laser_smu_read.wiring_help import (
                WIRING_HELP_TEXT,
                draw_wiring_diagram,
            )

        win = tk.Toplevel(self.root)
        win.title("Wiring / RPM help")
        win.geometry("900x720")

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tab_diag = ttk.Frame(nb)
        tab_text = ttk.Frame(nb)
        nb.add(tab_diag, text="Diagram")
        nb.add(tab_text, text="Checklist / RPM notes")

        fig = Figure(figsize=(8.5, 6.5), dpi=100)
        draw_wiring_diagram(fig)
        canvas = FigureCanvasTkAgg(fig, master=tab_diag)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

        txt = tk.Text(tab_text, wrap=tk.WORD, font=("Consolas", 10))
        txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        txt.insert("1.0", WIRING_HELP_TEXT)
        txt.configure(state=tk.DISABLED)

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=6)

    def _test_gpib(self) -> None:
        addr = self.gpib_var.get().strip()
        self.status_var.set(f"Testing {addr} (up to ~5s)…")
        self.root.update_idletasks()

        def worker() -> None:
            try:
                from runner import test_kxci_connection as _test
            except ImportError:
                from tools.pmu_laser_smu_read.runner import test_kxci_connection as _test
            try:
                msg = _test(addr, timeout=5.0)
            except Exception as exc:
                msg = f"FAIL (uncaught): {exc}"

            def done() -> None:
                self.status_var.set(msg.split("\n")[0][:120])
                if "OK:" in msg and "working" in msg:
                    messagebox.showinfo("GPIB / KXCI", msg)
                else:
                    messagebox.showerror("GPIB / KXCI", msg)

            self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _set_capture(self, seconds: float) -> None:
        self.capture_var.set(str(seconds))

    def _set_pre_capture(self, seconds: float) -> None:
        self.pre_capture_var.set(str(seconds))

    def _update_points_estimate(self) -> None:
        try:
            capture = self._f(self.capture_var)
            dt = self._f(self.dt_var)
            try:
                pre_capture = max(0.0, self._f(self.pre_capture_var))
            except Exception:
                pre_capture = 0.0
            if dt <= 0:
                raise ValueError
            n_post = max(1, int(round(capture / dt)))
            n_pre = int(round(pre_capture / dt)) if pre_capture > 0 else 0
            n = n_pre + n_post
            # Rough GPIB ASCII transfer estimate: ~0.3 ms/point is a
            # reasonable order-of-magnitude guess for a "GP" query reply.
            est_s = n * 3e-4
            warn = " (large — GP query may take a while)" if n > 5000 else ""
            pre_txt = f"{n_pre} pre + " if n_pre else ""
            self.points_est_var.set(
                f"≈ {pre_txt}{n_post} post = {n} points, ~{est_s:.1f}s to fetch{warn}"
            )
        except Exception:
            self.points_est_var.set("")

    def _browse_save(self) -> None:
        path = filedialog.askdirectory(initialdir=str(self.save_dir))
        if path:
            self.save_dir = Path(path)
            self.save_var.set(path)
            self._save_config()

    def _discover_samples(self) -> List[str]:
        """Existing sample folders under the shared Data_folder, most-recent first.

        Lets the user "look up" a sample already created elsewhere (e.g. via
        the main Sample GUI) and continue measuring on it here.
        """
        root = self.save_dir if hasattr(self, "save_dir") else DEFAULT_DATA_ROOT
        try:
            if not root.exists():
                return []
            dirs = [p for p in root.iterdir() if p.is_dir()]
            dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return [p.name for p in dirs]
        except Exception:
            return []

    def _refresh_sample_list(self) -> None:
        try:
            self.sample_combo.configure(values=self._discover_samples())
        except Exception:
            pass

    def _on_mode_change(self) -> None:
        mode = self.mode_var.get()

        def sync(period_row, npulses_row, cooldown_block) -> None:
            for row in (period_row, npulses_row, cooldown_block):
                row.pack_forget()
            if mode == "train":
                period_row.pack(fill=tk.X, pady=1)
                npulses_row.pack(fill=tk.X, pady=1)
            elif mode == "cooldown":
                cooldown_block.pack(fill=tk.X, pady=1)

        sync(self.period_row, self.npulses_row, self.cooldown_block)
        if hasattr(self, "live_period_row"):
            sync(self.live_period_row, self.live_npulses_row, self.live_cooldown_block)
        if hasattr(self, "routine_period_row"):
            sync(self.routine_period_row, self.routine_npulses_row, self.routine_cooldown_block)
        self._update_preview()
        self._update_cooldown_mini()

    def _on_cooldown_change(self) -> None:
        self._update_preview()
        self._update_cooldown_mini()
        if hasattr(self, "live_pulse_summary_var"):
            self._update_live_pulse_summary()
        if hasattr(self, "routine_pulse_summary_var"):
            self._update_routine_pulse_summary()

    def _f(self, var: tk.StringVar) -> float:
        return float(var.get().strip())

    def _irange(self) -> float:
        """SMU1 current MEASUREMENT range: blank or <= 0 means Autorange (0.0)."""
        raw = self.irange_var.get().strip()
        if not raw:
            return 0.0
        try:
            val = float(raw)
        except ValueError:
            return 0.0
        return val if val > 0 else 0.0

    def _params(self) -> Dict[str, Any]:
        mode: ModeName = self.mode_var.get()  # type: ignore[assignment]
        width_s = self._f(self.width_us_var) * 1e-6
        rise_s = self._f(self.rise_ns_var) * 1e-9
        fall_s = self._f(self.fall_ns_var) * 1e-9
        vhigh = self._f(self.vhigh_var)
        if vhigh > MAX_TTL_VHIGH:
            raise ValueError(f"Vhigh must be ≤ {MAX_TTL_VHIGH} V")

        num_pulses = max(1, int(float(self.num_pulses_var.get().strip())))
        period_s = self._f(self.period_us_var) * 1e-6
        decay: DecayName = self.decay_var.get()  # type: ignore[assignment]
        if decay not in ("linear", "exponential", "quadratic"):
            decay = "linear"

        start_period_s = self._f(self.start_period_us_var) * 1e-6
        end_period_s = self._f(self.end_period_us_var) * 1e-6
        cooldown_span_s = self._f(self.cooldown_span_us_var) * 1e-6

        # Auto-bump period so train/cool-down never abort over rise+width+fall
        # (those are fixed elsewhere; period is the adjustable timing).
        period_s = ensure_period_s(period_s, width_s=width_s, rise_s=rise_s, fall_s=fall_s)

        cd_start_width_s = 0.0
        cd_end_width_s = 0.0
        if mode == "cooldown":
            # Pulse 0 is IDENTICAL to a single/train shot (full Width — the
            # on-time already confirmed to reach the laser). From there
            # BOTH the on-time (Width) and off-time (period) taper together
            # start -> end over Cool-down span, per the chosen decay shape.
            # The taper is anchored to Width itself (not a fixed ns-scale
            # constant), so pulse count/width/spacing all scale with
            # whatever Width the user set. If the span is too short to fit
            # even 2 full-Width pulses, the starting width auto-shrinks so
            # the taper still fits (see plan_cooldown's shrink-to-fit step).
            (
                num_pulses,
                start_period_s,
                end_period_s,
                _,
                cd_start_width_s,
                cd_end_width_s,
            ) = plan_cooldown(
                width_s=width_s,
                rise_s=rise_s,
                fall_s=fall_s,
                span_s=cooldown_span_s,
                decay=decay,
            )
            w0 = format_width_s(cd_start_width_s)
            w1 = format_width_s(cd_end_width_s)
            shrunk = cd_start_width_s < width_s * 0.999
            shrink_note = " (span too short for full Width — shrunk)" if shrunk else ""
            info = (
                f"Auto: {num_pulses} pulses, width {w0}\u2192{w1}{shrink_note} "
                f"over {cooldown_span_s * 1e6:.3g} µs ({decay})"
            )
            self.cooldown_info_var.set(info)
            if hasattr(self, "live_cooldown_info_var"):
                self.live_cooldown_info_var.set(info)

        return {
            "gpib_address": self.gpib_var.get().strip(),
            "pmu_id": self.pmu_id_var.get().strip() or "PMU1",
            "mode": mode,
            "decay": decay,
            "cooldown_span_s": cooldown_span_s,
            "vread": self._f(self.vread_var),
            "ilimit": self._f(self.ilimit_var),
            "irange": self._irange(),
            "capture_time_s": self._f(self.capture_var),
            "pre_capture_s": max(0.0, self._f(self.pre_capture_var)),
            "sample_interval_s": self._f(self.dt_var),
            "vhigh": vhigh,
            "width_s": width_s,
            "rise_s": rise_s,
            "fall_s": fall_s,
            "period_s": period_s,
            "start_period_s": start_period_s,
            "end_period_s": end_period_s,
            "num_pulses": num_pulses,
            "cd_start_width_s": cd_start_width_s,
            "cd_end_width_s": cd_end_width_s,
            "delay_before_s": self._f(self.delay_ms_var) * 1e-3,
            "laser_fire_delay_s": self._f(self.fire_delay_ms_var) * 1e-3,
        }

    @staticmethod
    def _pick_time_unit(total_s: float) -> Tuple[float, str]:
        """Pick a readable time unit/scale so short pulses aren't squashed
        into unreadable 1e-5-style tick labels."""
        if total_s <= 0:
            return 1.0, "s"
        if total_s < 1e-6:
            return 1e9, "ns"
        if total_s < 1e-3:
            return 1e6, "µs"
        if total_s < 1.0:
            return 1e3, "ms"
        return 1.0, "s"

    def _update_preview(self) -> None:
        try:
            p = self._params()
            prev = build_preview(
                p["mode"],
                vhigh=p["vhigh"],
                width_s=p["width_s"],
                rise_s=p["rise_s"],
                fall_s=p["fall_s"],
                period_s=p["period_s"],
                start_period_s=p["start_period_s"],
                end_period_s=p["end_period_s"],
                num_pulses=p["num_pulses"],
                delay_before_s=p["delay_before_s"],
                decay=p.get("decay", "linear"),
                cooldown_span_s=p.get("cooldown_span_s") if p["mode"] == "cooldown" else None,
                cd_start_width_s=p.get("cd_start_width_s"),
                cd_end_width_s=p.get("cd_end_width_s"),
            )
            t, v = preview_polyline(prev)
            scale, unit = self._pick_time_unit(prev.total_duration_s)
            t_scaled = [x * scale for x in t]

            self.ax_ttl.clear()
            for idx, (a, b) in enumerate(prev.laser_on_intervals):
                self.ax_ttl.axvspan(
                    a * scale,
                    b * scale,
                    color="#4caf50",
                    alpha=0.30,
                    label="Laser ON" if idx == 0 else None,
                    zorder=0,
                )
            self.ax_ttl.step(
                t_scaled, v, where="post", color="#1f4e79", lw=1.6, zorder=2
            )
            self.ax_ttl.set_ylabel("TTL (V)")
            self.ax_ttl.set_xlabel(f"t ({unit})")
            self.ax_ttl.set_title(
                f"TTL preview — {prev.mode}, {prev.num_pulses} pulse(s), "
                f"{prev.total_duration_s * 1e3:.3g} ms total"
            )
            self.ax_ttl.grid(True, alpha=0.3)
            y_span = max(1.0, p["vhigh"]) * 0.15
            self.ax_ttl.set_ylim(-y_span, max(1.0, p["vhigh"]) + y_span)
            if prev.laser_on_intervals:
                self.ax_ttl.legend(loc="upper right", fontsize=8)
            self.canvas.draw_idle()
            self.status_var.set(
                f"Preview OK: {prev.num_pulses} pulses, "
                f"duration {prev.total_duration_s * 1e3:.4g} ms"
            )
            self._update_cooldown_mini()
        except Exception as exc:
            self.status_var.set(f"Preview error: {exc}")
            self._update_cooldown_mini()

    def _dry_run(self) -> None:
        try:
            p = self._params()
            result = run_pmu_laser_smu_read(**p, dry_run=True)
            cmd = result.get("pmu_command", "")
            messagebox.showinfo("Dry-run EX", cmd)
            self.status_var.set("Dry-run ready (see dialog)")
        except Exception as exc:
            messagebox.showerror("Dry-run failed", str(exc))

    def _run(self) -> None:
        if self._running:
            return
        try:
            params = self._params()
        except Exception as exc:
            messagebox.showerror("Invalid parameters", str(exc))
            return

        self._running = True
        self.last_params = dict(params)
        self.run_btn.configure(state=tk.DISABLED)
        self.status_var.set("Running…")
        self._save_config()

        def worker() -> None:
            err: Optional[Exception] = None
            result: Optional[Dict[str, Any]] = None
            try:
                result = run_pmu_laser_smu_read(**params)
            except Exception as exc:
                err = exc

            def done() -> None:
                self._running = False
                self.run_btn.configure(state=tk.NORMAL)
                if err is not None:
                    self.status_var.set(f"Error: {err}")
                    messagebox.showerror("Run failed", str(err))
                    return
                assert result is not None
                self.last_result = result
                self._plot_result(result)
                om = result.get("overlap_mode", "?")
                n = len(result.get("timestamps") or [])
                self.status_var.set(
                    f"Done — {n} samples, overlap={om}, mode={result.get('mode')}"
                )

            self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _plot_result(self, result: Dict[str, Any]) -> None:
        self._update_preview()

        # Remove any previous zoom inset (ax_r.clear() does not remove it,
        # since it's a separate Axes anchored to ax_r via a locator).
        if self._inset_ax is not None:
            try:
                self._inset_ax.remove()
            except Exception:
                pass
            self._inset_ax = None

        self.ax_r.clear()
        t = result.get("timestamps") or []
        r = result.get("resistances") or []
        intervals: List[Tuple[float, float]] = list(result.get("laser_on_intervals") or [])
        if t and r:
            self.ax_r.plot(t, r, color="#b35c00", lw=1.2, label="R(t)", zorder=2)
            self.ax_r.set_yscale("log")
            self.ax_r.set_xlabel("t (s)  [t=0 = laser fires; negative = pre-laser baseline]")
            self.ax_r.set_ylabel("R (Ohm)")
            self.ax_r.set_title("SMU resistance vs time")
            self.ax_r.grid(True, which="both", alpha=0.3)
            if t and t[0] < 0:
                self.ax_r.axvline(0.0, color="#888888", lw=0.8, linestyle=":", zorder=1)

            if intervals:
                # SMU is not sampling during the µs-scale PMU pulse, so do NOT
                # shade a "pulse length" band on R(t) — mark fire time only.
                a0 = intervals[0][0]
                color = self._pulse_color(result.get("mode"))
                label = self._mode_label(result)
                trans = self.ax_r.get_xaxis_transform()
                self.ax_r.axvline(
                    a0, color=color, lw=1.4, linestyle="--",
                    label=label, zorder=3,
                )
                self.ax_r.text(
                    a0, 1.02, label, transform=trans,
                    color=color, fontsize=9, fontweight="bold",
                    ha="center", va="bottom", clip_on=False,
                )
                self.ax_r.legend(loc="lower right", fontsize=8)
                self._add_laser_zoom_inset(t, r, intervals, mode=result.get("mode"))
        self.canvas.draw_idle()

    @staticmethod
    def _pulse_color(mode: Optional[str]) -> str:
        """Distinct marker colour per pulse type on R(t) plots."""
        return {
            "single": "#1565c0",      # blue
            "train": "#ef6c00",       # orange
            "cooldown": "#7b1fa2",    # purple
        }.get(mode or "", "#2e7d32")

    @staticmethod
    def _mode_label(info: Dict[str, Any]) -> str:
        """Human-readable pulse-type label for graph annotations, e.g.
        'Laser ON (train, 10x)' — includes num_pulses for train/cool-down."""
        mode = info.get("mode", "?")
        n = info.get("num_pulses")
        if mode == "single":
            return "Laser ON (single)"
        if mode == "cooldown":
            decay = info.get("decay") or (info.get("params") or {}).get("decay") or "linear"
            if n:
                return f"Laser ON (cooldown/{decay}, {n}x)"
            return f"Laser ON (cooldown/{decay})"
        if mode == "train" and n:
            return f"Laser ON (train, {n}x)"
        return f"Laser ON ({mode})"

    def _update_cooldown_mini(self) -> None:
        """Tiny cool-down waveform sketch in the cool-down param block(s)."""
        axes = []
        canvases = []
        if hasattr(self, "cd_ax"):
            axes.append(self.cd_ax)
            canvases.append(self.cd_canvas)
        if hasattr(self, "live_cd_ax"):
            axes.append(self.live_cd_ax)
            canvases.append(self.live_cd_canvas)
        if hasattr(self, "routine_cd_ax"):
            axes.append(self.routine_cd_ax)
            canvases.append(self.routine_cd_canvas)
        if not axes:
            return
        try:
            if self.mode_var.get() != "cooldown":
                for ax, canvas in zip(axes, canvases):
                    ax.clear()
                    ax.set_xticks([])
                    ax.set_yticks([])
                    ax.text(0.5, 0.5, "select Cool-down", ha="center", va="center",
                            transform=ax.transAxes, fontsize=8, color="#888888")
                    canvas.draw_idle()
                return
            p = self._params()
            prev = build_preview(
                "cooldown",
                vhigh=p["vhigh"],
                width_s=p["width_s"],
                rise_s=p["rise_s"],
                fall_s=p["fall_s"],
                start_period_s=p["start_period_s"],
                end_period_s=p["end_period_s"],
                num_pulses=p["num_pulses"],
                delay_before_s=0.0,
                decay=p.get("decay", "linear"),
                cooldown_span_s=p.get("cooldown_span_s"),
                cd_start_width_s=p.get("cd_start_width_s"),
                cd_end_width_s=p.get("cd_end_width_s"),
            )
            t, v = preview_polyline(prev)
            scale, unit = self._pick_time_unit(prev.total_duration_s)
            t_scaled = [x * scale for x in t]
            for ax, canvas in zip(axes, canvases):
                ax.clear()
                ax.step(t_scaled, v, where="post", color="#1f4e79", lw=1.1)
                for a, b in prev.laser_on_intervals:
                    ax.axvspan(a * scale, b * scale, color="#4caf50", alpha=0.25)
                ax.set_ylabel("V", fontsize=7)
                ax.set_xlabel(unit, fontsize=7)
                ax.tick_params(labelsize=6)
                ax.set_ylim(-0.2, max(1.0, p["vhigh"]) * 1.15)
                ax.set_title("Cool-down preview", fontsize=8)
                canvas.draw_idle()
        except Exception as exc:
            for ax, canvas in zip(axes, canvases):
                ax.clear()
                ax.text(0.5, 0.5, str(exc)[:40], ha="center", va="center",
                        transform=ax.transAxes, fontsize=7, color="#a00")
                canvas.draw_idle()

    def _add_laser_zoom_inset(
        self,
        t: List[float],
        r: List[float],
        intervals: List[Tuple[float, float]],
        mode: Optional[str] = None,
    ) -> None:
        """Zoom around the fire marker on R(t). SMU isn't sampling during the
        µs pulse, so we pad using the capture timescale — not the pulse width."""
        if not t or not intervals:
            return
        t_span = t[-1] - t[0]
        if t_span <= 0:
            return
        a_first = intervals[0][0]
        pad = max(t_span * 0.05, 1e-3)
        xlo = max(t[0], a_first - pad)
        xhi = min(t[-1], a_first + pad)
        if xhi <= xlo:
            return
        if (xhi - xlo) > 0.4 * t_span:
            return

        idxs = [i for i, tv in enumerate(t) if xlo <= tv <= xhi]
        if len(idxs) < 2:
            return

        axins = inset_axes(self.ax_r, width="42%", height="42%", loc="upper left", borderpad=1.6)
        self._inset_ax = axins
        t_zoom = [t[i] for i in idxs]
        r_zoom = [r[i] for i in idxs]
        axins.plot(t_zoom, r_zoom, color="#b35c00", lw=1.1)
        color = self._pulse_color(mode)
        axins.axvline(a_first, color=color, lw=1.0, linestyle="--")
        axins.set_yscale("log")
        axins.set_title("Zoom: around fire", fontsize=8)
        axins.tick_params(labelsize=6.5)
        axins.grid(True, which="both", alpha=0.3)

    def _display_rel_path(self, path: Path) -> str:
        """Path relative to the Save root, for compact status/dialog text."""
        try:
            return str(path.relative_to(self.save_dir))
        except Exception:
            return str(path)

    def _sanitize_sample_name(self, name: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in name.strip())
        cleaned = "_".join(cleaned.split())  # collapse whitespace
        return cleaned or "untitled"

    def _next_run_index(self, folder: Path) -> int:
        best = 0
        if folder.exists():
            for p in folder.iterdir():
                if not p.is_file():
                    continue
                head = p.stem.split("-", 1)[0]
                try:
                    best = max(best, int(head))
                except ValueError:
                    continue
        return best + 1

    def _allocate_save_paths(self, kind: str) -> Tuple[Path, Path, str, int]:
        """Return (csv_path, meta_path, sample_name, run_index).

        Layout (nested under the same per-device tree the main Sample GUI
        uses, so this tool's files sit alongside other measurements for the
        exact same sample/section/device):
          <Save root>/<sample_name>/<section>/<device>/PMU_Laser_SMU_Testing/<N>-<kind>_<timestamp>.csv
        """
        self.save_dir = Path(self.save_var.get().strip() or self.save_dir)
        sample = self._sanitize_sample_name(self.sample_var.get())
        section = (self.section_var.get().strip() or "A") if hasattr(self, "section_var") else "A"
        device = (self.device_var.get().strip() or "1") if hasattr(self, "device_var") else "1"
        folder = self.save_dir / sample / section / device / TEST_TYPE_FOLDER_NAME
        folder.mkdir(parents=True, exist_ok=True)
        n = self._next_run_index(folder)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"{n}-{kind}_{stamp}"
        return folder / f"{stem}.csv", folder / f"{stem}_meta.json", sample, n

    @staticmethod
    def _laser_fire_markers(
        timestamps: List[float],
        fire_times_s: List[float],
    ) -> List[int]:
        """Mark the nearest sample to each fire with 1, 2, 3… (else 0).

        SMU isn't sampling during the µs pulse, so we stamp the closest
        measured point rather than shading a duration.
        """
        marks = [0] * len(timestamps)
        if not timestamps or not fire_times_s:
            return marks
        used: set[int] = set()
        for fire_i, t_fire in enumerate(fire_times_s, start=1):
            best_i = None
            best_dt = float("inf")
            for i, tv in enumerate(timestamps):
                if i in used:
                    continue
                dt = abs(tv - t_fire)
                if dt < best_dt:
                    best_dt = dt
                    best_i = i
            if best_i is not None:
                marks[best_i] = fire_i
                used.add(best_i)
        return marks

    @staticmethod
    def _write_fires_and_data_csv(
        path: Path,
        *,
        sample_name: str,
        run_kind: str,
        fire_events: List[Dict[str, Any]],
        timestamps: List[float],
        currents: List[float],
        voltages: List[float],
        resistances: List[float],
        laser_fire: List[int],
        extra_header_lines: Optional[List[str]] = None,
    ) -> None:
        """One CSV with two logical tables:

        1) `#`-prefixed laser_fires table (index + pulse params)
        2) data table with a laser_fire column (0 / 1 / 2 / …)
        """
        with path.open("w", newline="", encoding="utf-8") as f:
            f.write(f"# sample_name: {sample_name}\n")
            f.write(f"# run_kind: {run_kind}\n")
            f.write(f"# num_fires: {len(fire_events)}\n")
            for line in extra_header_lines or []:
                f.write(f"# {line}\n")
            f.write("# --- laser_fires (table 1; pandas: comment='#') ---\n")
            f.write(
                "# fire_index,t_fire_s,mode,decay,width_s,vhigh_V,num_pulses,"
                "period_s,rise_s,fall_s,mode_label,params_json\n"
            )
            for ev in fire_events:
                params = ev.get("params") or {}
                row_buf = io.StringIO()
                csv.writer(row_buf).writerow(
                    [
                        ev.get("index", ""),
                        f"{float(ev.get('t_fire_s', ev.get('t_start_s', 0.0))):.8g}",
                        ev.get("mode", params.get("mode", "")),
                        ev.get("decay", params.get("decay", "")),
                        f"{float(params.get('width_s', 0.0) or 0.0):.8g}",
                        f"{float(params.get('vhigh', 0.0) or 0.0):.8g}",
                        params.get("num_pulses", ev.get("num_pulses", "")),
                        f"{float(params.get('period_s', 0.0) or 0.0):.8g}",
                        f"{float(params.get('rise_s', 0.0) or 0.0):.8g}",
                        f"{float(params.get('fall_s', 0.0) or 0.0):.8g}",
                        ev.get("mode_label", ""),
                        json.dumps(params, default=str),
                    ]
                )
                f.write("# " + row_buf.getvalue().rstrip("\r\n") + "\n")
            f.write("# --- data (table 2) ---\n")
            w = csv.writer(f)
            w.writerow(["t_s", "I_A", "V_V", "R_Ohm", "laser_fire"])
            for row in zip(timestamps, currents, voltages, resistances, laser_fire):
                w.writerow(row)

    def _save_csv(self) -> None:
        if not self.last_result:
            messagebox.showwarning("No data", "Run a measurement first.")
            return
        path, meta_path, sample, run_n = self._allocate_save_paths("single")

        t = list(self.last_result.get("timestamps") or [])
        i = list(self.last_result.get("currents") or [])
        v = list(self.last_result.get("voltages") or [])
        r = list(self.last_result.get("resistances") or [])
        intervals: List[Tuple[float, float]] = list(
            self.last_result.get("laser_on_intervals") or []
        )
        params = dict(self.last_params or {})
        # Single-shot: one fire at t=0 (or first laser_on interval start).
        t_fire = float(intervals[0][0]) if intervals else 0.0
        fire_events = [
            {
                "index": 1,
                "t_fire_s": t_fire,
                "t_start_s": t_fire,
                "t_end_s": float(intervals[0][1]) if intervals else t_fire,
                "mode": self.last_result.get("mode") or params.get("mode"),
                "decay": self.last_result.get("decay") or params.get("decay"),
                "num_pulses": self.last_result.get("num_pulses") or params.get("num_pulses"),
                "mode_label": self._mode_label(self.last_result),
                "params": params,
            }
        ]
        laser_fire = self._laser_fire_markers(t, [t_fire])

        self._write_fires_and_data_csv(
            path,
            sample_name=sample,
            run_kind="single_shot",
            fire_events=fire_events,
            timestamps=t,
            currents=i,
            voltages=v,
            resistances=r,
            laser_fire=laser_fire,
            extra_header_lines=[
                f"run_index: {run_n}",
                f"vread_V: {self.last_result.get('vread')}",
                f"irange_A: {self.last_result.get('irange')}",
            ],
        )

        meta = {
            "sample_name": sample,
            "run_index": run_n,
            "run_kind": "single_shot",
            "mode": self.last_result.get("mode"),
            "mode_label": self._mode_label(self.last_result),
            "decay": self.last_result.get("decay"),
            "overlap_mode": self.last_result.get("overlap_mode"),
            "vread": self.last_result.get("vread"),
            "irange": self.last_result.get("irange"),
            "num_pulses": self.last_result.get("num_pulses"),
            "num_pre_points": self.last_result.get("num_pre_points"),
            "num_post_points": self.last_result.get("num_post_points"),
            "laser_on_intervals": intervals,
            "fire_events": fire_events,
            "pmu_command": self.last_result.get("pmu_command"),
            "gpib": self.gpib_var.get().strip(),
            "pulse_parameters": params,
            "csv_format": {
                "table1": "laser_fires (#-commented rows)",
                "table2": "data columns t_s,I_A,V_V,R_Ohm,laser_fire",
                "laser_fire": "0=none; N=Nth fire marked on nearest sample (no SMU read during pulse)",
            },
        }
        meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        self._save_config()
        self.status_var.set(f"Saved {self._display_rel_path(path)}")
        messagebox.showinfo("Saved", f"Wrote:\n{path}\n{meta_path}")

    # ---------------------------------------------------------------
    # Live / Manual Fire tab
    # ---------------------------------------------------------------
    def _build_live_tab(self, parent: ttk.Frame) -> None:
        body = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left_host = ttk.Frame(body)
        right = ttk.Frame(body, padding=4)
        body.add(left_host, weight=1)
        body.add(right, weight=2)
        left = self._make_scrollable(left_host)

        info = self._collapsible_section(left, "How this works", expanded=False)
        ttk.Label(
            info,
            text=(
                "Continuously reads the SMU in short chunks over ONE GPIB\n"
                "session. Press 'Fire Pulse Now' anytime — the laser fires at\n"
                "the START of the next chunk (latency \u2248 one chunk's\n"
                "duration, since GPIB is one-command-at-a-time and can't be\n"
                "interrupted mid-call). Change pulse type/shape below anytime\n"
                "— even between fires — to alternate pulse types live\n"
                "(shared with the Single-shot tab's PMU/Pulse mode panels).\n"
                "Each fire is labelled with its pulse type on the graph, and\n"
                "'Save live CSV' records the exact parameters used per fire.\n"
                "Or use 'Preset experiment' below to auto-fire increasing\n"
                "pulse widths on a timer instead of clicking manually."
            ),
            justify=tk.LEFT,
            wraplength=340,
        ).pack(anchor=tk.W)

        bias = ttk.LabelFrame(left, text="SMU bias + chunking", padding=6)
        bias.pack(fill=tk.X, pady=4)
        self._row(bias, "Vread (V)", self.vread_var)
        self._row(bias, "Ilimit (A)", self.ilimit_var)
        self._row(bias, "Current range (A)", self.irange_var)
        ttk.Label(
            bias,
            text="0/blank = Autorange. Fixed value = lower-noise/faster reads.",
            foreground="#555555",
            font=("TkDefaultFont", 7),
        ).pack(anchor=tk.W, padx=(22, 0))
        self.live_dt_var = tk.StringVar(value="0.05")
        self.live_chunk_var = tk.StringVar(value="0.3")
        self._row(bias, "Sample dt (s)", self.live_dt_var)
        self._row(bias, "Chunk size (s)", self.live_chunk_var)
        self.live_chunk_info_var = tk.StringVar(value="")
        ttk.Label(
            bias, textvariable=self.live_chunk_info_var, foreground="#555555"
        ).pack(anchor=tk.W, pady=(2, 0))
        for var in (self.live_dt_var, self.live_chunk_var):
            var.trace_add("write", lambda *_: self._update_live_chunk_info())

        # PMU CH1 TTL shape — same StringVars as the Single-shot tab, so
        # editing here (or there) keeps both tabs in sync.
        live_pmu = ttk.LabelFrame(left, text="PMU CH1 TTL", padding=6)
        live_pmu.pack(fill=tk.X, pady=4)
        self._row(live_pmu, "Vhigh (V)", self.vhigh_var)
        self._row(live_pmu, "Width (µs)", self.width_us_var)
        self._row(live_pmu, "Rise (ns)", self.rise_ns_var)
        self._row(live_pmu, "Fall (ns)", self.fall_ns_var)
        self._row(live_pmu, "PMU delay before (ms)", self.delay_ms_var)

        # Pulse type selector — same self.mode_var as the Single-shot tab.
        live_mode_fr = ttk.LabelFrame(left, text="Pulse type (fires on 'Fire Pulse Now')", padding=6)
        live_mode_fr.pack(fill=tk.X, pady=4)
        for label, val in (
            ("Single", "single"),
            ("Train", "train"),
            ("Cool-down", "cooldown"),
        ):
            ttk.Radiobutton(
                live_mode_fr,
                text=label,
                value=val,
                variable=self.mode_var,
                command=self._on_mode_change,
            ).pack(anchor=tk.W)

        self.live_mode_params = ttk.Frame(live_mode_fr)
        self.live_mode_params.pack(fill=tk.X, pady=4)
        self.live_period_row = self._row(self.live_mode_params, "Period (µs)", self.period_us_var)
        self.live_npulses_row = self._row(self.live_mode_params, "Num pulses", self.num_pulses_var)

        self.live_cooldown_block = ttk.Frame(self.live_mode_params)
        self._row(self.live_cooldown_block, "Cool-down over (µs)", self.cooldown_span_us_var)
        live_decay_row = ttk.Frame(self.live_cooldown_block)
        live_decay_row.pack(fill=tk.X, pady=1)
        ttk.Label(live_decay_row, text="Decay type", width=22).pack(side=tk.LEFT)
        live_decay_combo = ttk.Combobox(
            live_decay_row,
            textvariable=self.decay_var,
            values=("linear", "exponential", "quadratic"),
            state="readonly",
            width=12,
        )
        live_decay_combo.pack(side=tk.LEFT)
        live_decay_combo.bind("<<ComboboxSelected>>", lambda *_: self._on_cooldown_change())
        self.live_cooldown_info_var = tk.StringVar(value="")
        ttk.Label(
            self.live_cooldown_block,
            textvariable=self.live_cooldown_info_var,
            foreground="#555555",
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(2, 2))
        self.live_cd_fig = Figure(figsize=(3.2, 1.35), dpi=100)
        self.live_cd_ax = self.live_cd_fig.add_subplot(111)
        self.live_cd_fig.subplots_adjust(left=0.14, right=0.98, top=0.88, bottom=0.28)
        self.live_cd_canvas = FigureCanvasTkAgg(self.live_cd_fig, master=self.live_cooldown_block)
        self.live_cd_canvas.get_tk_widget().pack(fill=tk.X, pady=(2, 0))

        pulse_summary = ttk.LabelFrame(left, text="Pulse that will fire", padding=6)
        pulse_summary.pack(fill=tk.X, pady=4)
        self.live_pulse_summary_var = tk.StringVar(value="")
        ttk.Label(
            pulse_summary,
            textvariable=self.live_pulse_summary_var,
            justify=tk.LEFT,
            wraplength=340,
        ).pack(anchor=tk.W)

        # Control sits above the optional width-sweep so Start/Stop/Fire stay
        # visible without scrolling past collapsed (or expanded) sections.
        ctrl = ttk.LabelFrame(left, text="Control", padding=6)
        ctrl.pack(fill=tk.X, pady=4)
        row1 = ttk.Frame(ctrl)
        row1.pack(fill=tk.X, pady=2)
        self.live_start_btn = ttk.Button(row1, text="Start streaming", command=self._start_streaming)
        self.live_start_btn.pack(side=tk.LEFT, padx=2)
        self.live_stop_btn = ttk.Button(
            row1, text="Stop streaming", command=self._stop_streaming, state=tk.DISABLED
        )
        self.live_stop_btn.pack(side=tk.LEFT, padx=2)
        self.live_pause_btn = ttk.Button(
            row1, text="\u23f8 Pause", command=self._toggle_pause, state=tk.DISABLED
        )
        self.live_pause_btn.pack(side=tk.LEFT, padx=2)

        self.live_fire_btn = ttk.Button(
            ctrl,
            text="\U0001f525 Fire Pulse Now",
            command=self._fire_now,
            state=tk.DISABLED,
        )
        self.live_fire_btn.pack(fill=tk.X, pady=(8, 2))

        self.live_status_var = tk.StringVar(value="Not streaming")
        ttk.Label(ctrl, textvariable=self.live_status_var, wraplength=340).pack(
            anchor=tk.W, pady=(4, 0)
        )

        # Preset experiment: automatic pulse-width sweep. Uses the current
        # streaming session (must be streaming already, or this starts it)
        # and auto-fires on a timer, incrementing Width each time — so you
        # get a live, on-screen view of R(t) vs. increasing pulse width
        # without manually clicking Fire Now every time.
        exp = self._collapsible_section(
            left, "Preset experiment: pulse-width sweep", expanded=False
        )
        self.exp_start_width_var = tk.StringVar(value="10")
        self.exp_step_width_var = tk.StringVar(value="10")
        self.exp_max_width_var = tk.StringVar(value="100")
        self.exp_interval_var = tk.StringVar(value="10")
        self._row(exp, "Start width (µs)", self.exp_start_width_var)
        self._row(exp, "Width step (µs)", self.exp_step_width_var)
        self._row(exp, "Max width (µs)", self.exp_max_width_var)
        self._row(exp, "Fire every (s)", self.exp_interval_var)

        exp_btns = ttk.Frame(exp)
        exp_btns.pack(fill=tk.X, pady=(4, 0))
        self.exp_start_btn = ttk.Button(
            exp_btns, text="Start width sweep", command=self._start_width_sweep
        )
        self.exp_start_btn.pack(side=tk.LEFT, padx=2)
        self.exp_stop_btn = ttk.Button(
            exp_btns, text="Stop sweep", command=self._stop_width_sweep, state=tk.DISABLED
        )
        self.exp_stop_btn.pack(side=tk.LEFT, padx=2)

        self.exp_status_var = tk.StringVar(value="")
        ttk.Label(exp, textvariable=self.exp_status_var, foreground="#555555", wraplength=340).pack(
            anchor=tk.W, pady=(4, 0)
        )

        ttk.Button(
            left, text="Save live CSV", command=lambda: self._save_stream_csv("live_manual_fire")
        ).pack(fill=tk.X, pady=(8, 2))

        self.live_fig = Figure(figsize=(7.5, 7), dpi=100)
        self.live_ax = self.live_fig.add_subplot(111)
        self.live_fig.tight_layout(pad=2.0)
        self.live_canvas = FigureCanvasTkAgg(self.live_fig, master=right)
        self.live_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Streaming state
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_stop_event = threading.Event()
        # Main thread puts a captured pulse-params dict here on "Fire Now";
        # the worker thread only reads plain Python objects from this queue
        # (never touches Tkinter Vars directly — Tkinter is not safe to
        # access from a background thread).
        self._stream_fire_queue: "queue.Queue" = queue.Queue()
        self._stream_queue: "queue.Queue" = queue.Queue()
        self._stream_t: List[float] = []
        self._stream_i: List[float] = []
        self._stream_v: List[float] = []
        self._stream_r: List[float] = []
        self._stream_intervals: List[Tuple[float, float]] = []
        self._stream_fire_events: List[Dict[str, Any]] = []
        self._stream_elapsed = 0.0
        self._stream_active = False

        # Pause-everything: freezes the streaming worker (no new SMU reads /
        # bias re-asserts) and any routine/sweep timers, without tearing the
        # session down — bias stays exactly as last set, so it's safe to
        # check the sample (e.g. under a scope) and Resume picks up right
        # where it left off.
        self._paused = False
        self._stream_pause_event = threading.Event()

        # Width-sweep preset experiment state
        self._exp_active = False
        self._exp_after_id: Optional[str] = None
        self._exp_next_width_us = 0.0
        self._exp_step_us = 0.0
        self._exp_max_width_us = 0.0
        self._exp_count = 0

        self._update_live_chunk_info()
        for var in (
            self.width_us_var,
            self.period_us_var,
            self.num_pulses_var,
            self.cooldown_span_us_var,
            self.decay_var,
            self.vhigh_var,
            self.mode_var,
        ):
            var.trace_add("write", lambda *_: self._update_live_pulse_summary())
        self._update_live_pulse_summary()
        self._on_mode_change()

    # ---------------------------------------------------------------
    # Automated Routine tab
    # ---------------------------------------------------------------
    def _build_routine_tab(self, parent: ttk.Frame) -> None:
        body = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left_host = ttk.Frame(body)
        right = ttk.Frame(body, padding=4)
        body.add(left_host, weight=1)
        body.add(right, weight=2)
        left = self._make_scrollable(left_host)

        info = self._collapsible_section(left, "How this works", expanded=False)
        ttk.Label(
            info,
            text=(
                "Automates \u2018low-current pulse at increasing widths, then\n"
                "raise current % and repeat\u2019: for each current level (low\u2192high)\n"
                "it fires every width in the list below, in order, on the\n"
                "SAME streaming session as Live / Manual Fire (only one GPIB\n"
                "session can exist at a time — streaming starts automatically\n"
                "if it isn't already running). Laser current % is set over serial\n"
                "(Equipment/Laser_Controller/oxxius.py) between blocks — you\n"
                "must Connect the laser below first. Connect arms TTL mod\n"
                "with emission ON (needed for TTL gating). Watch the live\n"
                "R(t) plot and click 'Stop routine' as soon as you see a\n"
                "response — the laser is automatically restored to normal\n"
                "manual (front panel wheel) control whenever the routine\n"
                "stops or finishes."
            ),
            justify=tk.LEFT,
            wraplength=340,
        ).pack(anchor=tk.W)

        # --- Laser (serial) ---
        laser_fr = ttk.LabelFrame(left, text="Laser (serial)", padding=6)
        laser_fr.pack(fill=tk.X, pady=4)
        conn_row = ttk.Frame(laser_fr)
        conn_row.pack(fill=tk.X, pady=1)
        ttk.Label(conn_row, text="Port", width=8).pack(side=tk.LEFT)
        self.laser_port_var = tk.StringVar(value="COM8")
        ttk.Entry(conn_row, textvariable=self.laser_port_var, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Label(conn_row, text="Baud").pack(side=tk.LEFT, padx=(8, 2))
        self.laser_baud_var = tk.StringVar(value="19200")
        ttk.Entry(conn_row, textvariable=self.laser_baud_var, width=8).pack(side=tk.LEFT, padx=2)

        btn_row = ttk.Frame(laser_fr)
        btn_row.pack(fill=tk.X, pady=2)
        self.laser_connect_btn = ttk.Button(btn_row, text="Connect", command=self._connect_laser)
        self.laser_connect_btn.pack(side=tk.LEFT, padx=2)
        self.laser_disconnect_btn = ttk.Button(
            btn_row, text="Disconnect", command=self._disconnect_laser, state=tk.DISABLED
        )
        self.laser_disconnect_btn.pack(side=tk.LEFT, padx=2)
        self.laser_status_var = tk.StringVar(value="Disconnected")
        ttk.Label(btn_row, textvariable=self.laser_status_var, foreground="#888888").pack(
            side=tk.LEFT, padx=(10, 0)
        )

        emission_row = ttk.Frame(laser_fr)
        emission_row.pack(fill=tk.X, pady=2)
        ttk.Label(emission_row, text="Emission", width=8).pack(side=tk.LEFT)
        self.laser_emission_on_btn = ttk.Button(
            emission_row, text="On", width=4, command=self._laser_emission_on, state=tk.DISABLED
        )
        self.laser_emission_on_btn.pack(side=tk.LEFT, padx=2)
        self.laser_emission_off_btn = ttk.Button(
            emission_row, text="Off", width=4, command=self._laser_emission_off, state=tk.DISABLED
        )
        self.laser_emission_off_btn.pack(side=tk.LEFT, padx=2)

        power_now_row = ttk.Frame(laser_fr)
        power_now_row.pack(fill=tk.X, pady=2)
        ttk.Label(power_now_row, text="Set current (%)", width=14).pack(side=tk.LEFT)
        self.laser_manual_power_var = tk.StringVar(value="10")
        ttk.Entry(power_now_row, textvariable=self.laser_manual_power_var, width=8).pack(
            side=tk.LEFT, padx=2
        )
        self.laser_set_power_btn = ttk.Button(
            power_now_row, text="Set now", command=self._laser_set_power_now, state=tk.DISABLED
        )
        self.laser_set_power_btn.pack(side=tk.LEFT, padx=2)

        align_row = ttk.Frame(laser_fr)
        align_row.pack(fill=tk.X, pady=2)
        ttk.Label(align_row, text="Align (%)", width=14).pack(side=tk.LEFT)
        self.laser_align_pct_var = tk.StringVar(value="5")
        ttk.Entry(align_row, textvariable=self.laser_align_pct_var, width=8).pack(
            side=tk.LEFT, padx=2
        )
        self.laser_align_on_btn = ttk.Button(
            align_row, text="Align ON", width=9, command=self._laser_align_on, state=tk.DISABLED
        )
        self.laser_align_on_btn.pack(side=tk.LEFT, padx=2)
        self.laser_align_off_btn = ttk.Button(
            align_row,
            text="Align OFF → TTL",
            width=14,
            command=self._laser_align_off,
            state=tk.DISABLED,
        )
        self.laser_align_off_btn.pack(side=tk.LEFT, padx=2)
        ttk.Label(
            laser_fr,
            text="Align ON: TTL mod off, CW beam at Align %. Align OFF re-arms TTL mod (emission ON).",
            foreground="#555555",
            font=("TkDefaultFont", 7),
            wraplength=340,
        ).pack(anchor=tk.W, pady=(0, 2))

        self.laser_restore_btn = ttk.Button(
            laser_fr,
            text="Restore manual control (front panel)",
            command=self._laser_restore_manual,
            state=tk.DISABLED,
        )
        self.laser_restore_btn.pack(fill=tk.X, pady=(4, 0))

        if OxxiusLaser is None:
            ttk.Label(
                laser_fr,
                text="pyserial is not available — laser control disabled.",
                foreground="#a00000",
            ).pack(anchor=tk.W, pady=(4, 0))
            self.laser_connect_btn.configure(state=tk.DISABLED)

        # --- SMU bias + chunking (shared with Live tab) ---
        bias = ttk.LabelFrame(left, text="SMU bias + chunking", padding=6)
        bias.pack(fill=tk.X, pady=4)
        self._row(bias, "Vread (V)", self.vread_var)
        self._row(bias, "Ilimit (A)", self.ilimit_var)
        self._row(bias, "Current range (A)", self.irange_var)
        ttk.Label(
            bias,
            text="0/blank = Autorange. Fixed value = lower-noise/faster reads.",
            foreground="#555555",
            font=("TkDefaultFont", 7),
        ).pack(anchor=tk.W, padx=(22, 0))
        self._row(bias, "Sample dt (s)", self.live_dt_var)
        self._row(bias, "Chunk size (s)", self.live_chunk_var)
        ttk.Label(bias, textvariable=self.live_chunk_info_var, foreground="#555555").pack(
            anchor=tk.W, pady=(2, 0)
        )

        # --- PMU CH1 TTL (shared; Width is routine-controlled) ---
        pmu = ttk.LabelFrame(left, text="PMU CH1 TTL", padding=6)
        pmu.pack(fill=tk.X, pady=4)
        self._row(pmu, "Vhigh (V)", self.vhigh_var)
        self._row(pmu, "Rise (ns)", self.rise_ns_var)
        self._row(pmu, "Fall (ns)", self.fall_ns_var)
        self._row(pmu, "PMU delay before (ms)", self.delay_ms_var)
        width_row = ttk.Frame(pmu)
        width_row.pack(fill=tk.X, pady=1)
        ttk.Label(width_row, text="Current width", width=22).pack(side=tk.LEFT)
        self.routine_current_width_var = tk.StringVar(
            value=format_width_s(self._f(self.width_us_var) * 1e-6)
        )
        ttk.Label(width_row, textvariable=self.routine_current_width_var, foreground="#555555").pack(
            side=tk.LEFT
        )
        ttk.Label(
            pmu,
            text="Width is set automatically by the routine below (not editable here).",
            foreground="#555555",
            font=("TkDefaultFont", 7),
        ).pack(anchor=tk.W, padx=(2, 0))

        # --- Pulse type (shared mode_var) ---
        mode_fr = ttk.LabelFrame(left, text="Pulse type (fires during the routine)", padding=6)
        mode_fr.pack(fill=tk.X, pady=4)
        for label, val in (
            ("Single", "single"),
            ("Train", "train"),
            ("Cool-down", "cooldown"),
        ):
            ttk.Radiobutton(
                mode_fr, text=label, value=val, variable=self.mode_var, command=self._on_mode_change
            ).pack(anchor=tk.W)

        self.routine_mode_params = ttk.Frame(mode_fr)
        self.routine_mode_params.pack(fill=tk.X, pady=4)
        self.routine_period_row = self._row(self.routine_mode_params, "Period (µs)", self.period_us_var)
        self.routine_npulses_row = self._row(
            self.routine_mode_params, "Num pulses", self.num_pulses_var
        )

        self.routine_cooldown_block = ttk.Frame(self.routine_mode_params)
        self._row(self.routine_cooldown_block, "Cool-down over (µs)", self.cooldown_span_us_var)
        rd_row = ttk.Frame(self.routine_cooldown_block)
        rd_row.pack(fill=tk.X, pady=1)
        ttk.Label(rd_row, text="Decay type", width=22).pack(side=tk.LEFT)
        rd_combo = ttk.Combobox(
            rd_row,
            textvariable=self.decay_var,
            values=("linear", "exponential", "quadratic"),
            state="readonly",
            width=12,
        )
        rd_combo.pack(side=tk.LEFT)
        rd_combo.bind("<<ComboboxSelected>>", lambda *_: self._on_cooldown_change())
        ttk.Label(
            self.routine_cooldown_block,
            textvariable=self.live_cooldown_info_var,
            foreground="#555555",
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(2, 2))
        self.routine_cd_fig = Figure(figsize=(3.2, 1.1), dpi=100)
        self.routine_cd_ax = self.routine_cd_fig.add_subplot(111)
        self.routine_cd_fig.subplots_adjust(left=0.14, right=0.98, top=0.88, bottom=0.28)
        self.routine_cd_canvas = FigureCanvasTkAgg(self.routine_cd_fig, master=self.routine_cooldown_block)
        self.routine_cd_canvas.get_tk_widget().pack(fill=tk.X, pady=(2, 0))

        pulse_summary = ttk.LabelFrame(left, text="Pulse that will fire", padding=6)
        pulse_summary.pack(fill=tk.X, pady=4)
        self.routine_pulse_summary_var = tk.StringVar(value="")
        ttk.Label(
            pulse_summary,
            textvariable=self.routine_pulse_summary_var,
            justify=tk.LEFT,
            wraplength=340,
        ).pack(anchor=tk.W)

        # --- Routine: width x current-% sweep ---
        routine_fr = ttk.LabelFrame(left, text="Routine: width \u00d7 current % sweep", padding=6)
        routine_fr.pack(fill=tk.X, pady=4)

        ttk.Label(routine_fr, text="Pulse widths", font=("TkDefaultFont", 8, "bold")).pack(anchor=tk.W)
        gen_row = ttk.Frame(routine_fr)
        gen_row.pack(fill=tk.X, pady=1)
        ttk.Label(gen_row, text="Start", width=6).pack(side=tk.LEFT)
        self.routine_start_width_var = tk.StringVar(value="100")
        ttk.Entry(gen_row, textvariable=self.routine_start_width_var, width=7).pack(
            side=tk.LEFT, padx=2
        )
        self.routine_width_unit_var = tk.StringVar(value="ns")
        ttk.Combobox(
            gen_row,
            textvariable=self.routine_width_unit_var,
            values=("ns", "us", "ms"),
            state="readonly",
            width=4,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Label(gen_row, text="x", width=2).pack(side=tk.LEFT)
        self.routine_width_multiplier_var = tk.StringVar(value="10")
        ttk.Entry(gen_row, textvariable=self.routine_width_multiplier_var, width=5).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Label(gen_row, text="for", width=4).pack(side=tk.LEFT)
        self.routine_width_steps_var = tk.StringVar(value="4")
        ttk.Entry(gen_row, textvariable=self.routine_width_steps_var, width=4).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Label(gen_row, text="steps").pack(side=tk.LEFT, padx=(2, 4))
        ttk.Button(gen_row, text="Generate", command=self._generate_routine_widths).pack(
            side=tk.LEFT, padx=2
        )

        self.routine_widths_var = tk.StringVar(value=self.routine_widths_default)
        ttk.Entry(routine_fr, textvariable=self.routine_widths_var).pack(fill=tk.X, pady=(2, 4))
        ttk.Label(
            routine_fr,
            text="Editable comma-separated list, e.g. '100ns, 1000ns, 10000ns'.",
            foreground="#555555",
            font=("TkDefaultFont", 7),
        ).pack(anchor=tk.W)

        ttk.Label(routine_fr, text="Laser current (%)", font=("TkDefaultFont", 8, "bold")).pack(
            anchor=tk.W, pady=(6, 0)
        )
        self.routine_start_power_var = tk.StringVar(value=self.routine_start_pct_default)
        self.routine_power_step_var = tk.StringVar(value=self.routine_step_pct_default)
        self.routine_power_max_var = tk.StringVar(value=self.routine_max_pct_default)
        self._row(routine_fr, "Start current (%)", self.routine_start_power_var)
        self._row(routine_fr, "Current step (%)", self.routine_power_step_var)
        self._row(routine_fr, "Max current (%)", self.routine_power_max_var)
        self.routine_power_preview_var = tk.StringVar(value="")
        ttk.Label(
            routine_fr,
            textvariable=self.routine_power_preview_var,
            foreground="#555555",
            wraplength=340,
        ).pack(anchor=tk.W, pady=(0, 4))
        for var in (
            self.routine_start_power_var,
            self.routine_power_step_var,
            self.routine_power_max_var,
        ):
            var.trace_add("write", lambda *_: self._update_routine_power_preview())

        ttk.Label(routine_fr, text="Timing", font=("TkDefaultFont", 8, "bold")).pack(
            anchor=tk.W, pady=(6, 0)
        )
        self.routine_settle_var = tk.StringVar(value=self.routine_settle_default)
        self.routine_interval_var = tk.StringVar(value=self.routine_interval_default)
        self._row(routine_fr, "Settle after current change (s)", self.routine_settle_var)
        self._row(routine_fr, "Fire every (s)", self.routine_interval_var)

        preview_btn_row = ttk.Frame(routine_fr)
        preview_btn_row.pack(fill=tk.X, pady=(4, 2))
        ttk.Button(
            preview_btn_row, text="Preview plan", command=self._preview_routine_plan
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(
            preview_btn_row, text="Visualize routine", command=self._show_routine_visual
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        ctrl_row = ttk.Frame(routine_fr)
        ctrl_row.pack(fill=tk.X, pady=2)
        self.routine_start_btn = ttk.Button(ctrl_row, text="Start routine", command=self._start_routine)
        self.routine_start_btn.pack(side=tk.LEFT, padx=2)
        self.routine_stop_btn = ttk.Button(
            ctrl_row, text="Stop routine", command=self._stop_routine, state=tk.DISABLED
        )
        self.routine_stop_btn.pack(side=tk.LEFT, padx=2)
        self.routine_stop_stream_btn = ttk.Button(
            ctrl_row,
            text="Stop streaming",
            command=self._stop_streaming,
            state=tk.DISABLED,
        )
        self.routine_stop_stream_btn.pack(side=tk.LEFT, padx=2)
        self.routine_pause_btn = ttk.Button(
            ctrl_row, text="\u23f8 Pause", command=self._toggle_pause, state=tk.DISABLED
        )
        self.routine_pause_btn.pack(side=tk.LEFT, padx=2)

        self.routine_status_var = tk.StringVar(value="Idle")
        ttk.Label(routine_fr, textvariable=self.routine_status_var, wraplength=340).pack(
            anchor=tk.W, pady=(4, 0)
        )

        self.routine_stream_status_var = tk.StringVar(value="Not streaming")
        ttk.Label(
            routine_fr,
            textvariable=self.routine_stream_status_var,
            foreground="#555555",
            wraplength=340,
        ).pack(anchor=tk.W, pady=(2, 0))

        ttk.Button(
            left, text="Save routine CSV", command=lambda: self._save_stream_csv("routine")
        ).pack(fill=tk.X, pady=(8, 2))

        self.routine_fig = Figure(figsize=(7.5, 7), dpi=100)
        self.routine_ax = self.routine_fig.add_subplot(111)
        self.routine_fig.tight_layout(pad=2.0)
        self.routine_canvas = FigureCanvasTkAgg(self.routine_fig, master=right)
        self.routine_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Routine execution state
        self._routine_active = False
        self._routine_plan: List[RoutineStep] = []
        self._routine_index = 0
        self._routine_after_id: Optional[str] = None
        self._routine_last_wait_ms: int = 200
        self._routine_current_power_mw: Optional[float] = None
        self._laser_align_active = False

        self._update_routine_power_preview()
        self._update_routine_pulse_summary()
        for var in (
            self.width_us_var,
            self.period_us_var,
            self.num_pulses_var,
            self.cooldown_span_us_var,
            self.decay_var,
            self.vhigh_var,
            self.mode_var,
        ):
            var.trace_add("write", lambda *_: self._update_routine_pulse_summary())
        self._on_mode_change()

    def _update_live_chunk_info(self) -> None:
        try:
            dt = self._f(self.live_dt_var)
            chunk_s = self._f(self.live_chunk_var)
            if dt <= 0 or chunk_s <= 0:
                raise ValueError
            n = max(1, int(round(chunk_s / dt)))
            text = f"\u2248 {n} pts/chunk — Fire Now latency \u2248 up to {n * dt:.2f}s"
            if n <= 15:
                # Each chunk re-asserts the SMU bias (required — see
                # pmu_laser_smu_stream.c). On some samples this shows up as a
                # small periodic sawtooth/"triangle" ripple in I(t)/R(t)
                # synced to the chunk boundary. A bigger chunk here reduces it.
                text += " — small chunks can show a periodic sawtooth ripple; bump this up if you see one"
            self.live_chunk_info_var.set(text)
        except Exception:
            self.live_chunk_info_var.set("")

    def _pulse_summary_text(self) -> str:
        """Human-readable one-liner describing whatever pulse would fire
        right now, shared by the Live tab and the Automated Routine tab."""
        p = self._params()
        mode = p["mode"]
        if mode == "single":
            return f"Single pulse, {p['width_s'] * 1e6:.3g} µs wide, Vhigh={p['vhigh']} V"
        if mode == "train":
            return (
                f"Train: {p['num_pulses']} pulses @ {p['period_s'] * 1e6:.3g} µs "
                f"period, {p['width_s'] * 1e6:.3g} µs wide, Vhigh={p['vhigh']} V"
            )
        return (
            f"Cool-down ({p.get('decay', 'linear')}): "
            f"{p['num_pulses']} pulses, width "
            f"{format_width_s(p.get('cd_start_width_s') or p['width_s'])}\u2192"
            f"{format_width_s(p.get('cd_end_width_s') or p['width_s'])}, "
            f"period {p['start_period_s'] * 1e6:.3g}\u2192"
            f"{p['end_period_s'] * 1e6:.3g} µs, over "
            f"{p.get('cooldown_span_s', 0) * 1e6:.3g} µs"
        )

    def _update_live_pulse_summary(self) -> None:
        try:
            self.live_pulse_summary_var.set(self._pulse_summary_text())
        except Exception as exc:
            self.live_pulse_summary_var.set(f"(fix Pulse mode / PMU CH1 TTL params: {exc})")

    def _update_routine_pulse_summary(self) -> None:
        if not hasattr(self, "routine_pulse_summary_var"):
            return
        if hasattr(self, "routine_current_width_var"):
            try:
                self.routine_current_width_var.set(format_width_s(self._f(self.width_us_var) * 1e-6))
            except Exception:
                pass
        try:
            self.routine_pulse_summary_var.set(self._pulse_summary_text())
        except Exception as exc:
            self.routine_pulse_summary_var.set(f"(fix Pulse mode / PMU CH1 TTL params: {exc})")

    def _start_streaming(self) -> None:
        if self._stream_active:
            return
        try:
            dt = self._f(self.live_dt_var)
            chunk_s = self._f(self.live_chunk_var)
            if dt <= 0 or chunk_s <= 0:
                raise ValueError("Sample dt and Chunk size must be > 0")
            chunk_points = max(1, int(round(chunk_s / dt)))
            vread = self._f(self.vread_var)
            ilimit = self._f(self.ilimit_var)
            irange = self._irange()
        except Exception as exc:
            messagebox.showerror("Invalid parameters", str(exc))
            return

        self._stream_t = []
        self._stream_i = []
        self._stream_v = []
        self._stream_r = []
        self._stream_intervals = []
        self._stream_fire_events = []
        self._stream_elapsed = 0.0
        self._stream_stop_event.clear()
        self._stream_pause_event.clear()
        self._paused = False
        self._stream_fire_queue = queue.Queue()
        self._stream_queue = queue.Queue()

        self.live_start_btn.configure(state=tk.DISABLED)
        self.live_stop_btn.configure(state=tk.NORMAL)
        self.live_fire_btn.configure(state=tk.DISABLED)
        self.live_pause_btn.configure(state=tk.NORMAL, text="\u23f8 Pause")
        if hasattr(self, "routine_stop_stream_btn"):
            self.routine_stop_stream_btn.configure(state=tk.NORMAL)
        if hasattr(self, "routine_pause_btn"):
            self.routine_pause_btn.configure(state=tk.NORMAL, text="\u23f8 Pause")
        self.live_status_var.set("Connecting…")
        if hasattr(self, "routine_stream_status_var"):
            self.routine_stream_status_var.set("Connecting…")
        self._save_config()

        gpib_address = self.gpib_var.get().strip()
        pmu_id = self.pmu_id_var.get().strip() or "PMU1"

        def worker() -> None:
            session = PmuLaserSmuStreamSession(gpib_address=gpib_address, pmu_id=pmu_id)
            try:
                session.connect()
            except Exception as exc:
                self._stream_queue.put(("error", exc))
                return
            self._stream_queue.put(("connected", None))

            while not self._stream_stop_event.is_set():
                if self._stream_pause_event.is_set():
                    # Paused: no new EX calls at all (no SMU reads, no bias
                    # re-assert, no fires) — bias stays exactly as last set.
                    # Still watch stop_event so "Stop streaming" works while
                    # paused.
                    time.sleep(0.1)
                    continue
                # Only reads plain Python objects off a queue here — never
                # touches Tkinter Vars from this background thread.
                fire_params: Optional[Dict[str, Any]] = None
                try:
                    fire_params = self._stream_fire_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    if fire_params is not None:
                        try:
                            chunk = session.read_chunk(
                                vread=vread,
                                ilimit=ilimit,
                                irange=irange,
                                sample_interval_s=dt,
                                num_points=chunk_points,
                                fire_now=True,
                                mode=fire_params["mode"],
                                vhigh=fire_params["vhigh"],
                                rise_s=fire_params["rise_s"],
                                fall_s=fire_params["fall_s"],
                                width_s=fire_params["width_s"],
                                period_s=fire_params["period_s"],
                                start_period_s=fire_params["start_period_s"],
                                end_period_s=fire_params["end_period_s"],
                                num_pulses=fire_params["num_pulses"],
                                delay_before_s=fire_params["delay_before_s"],
                                decay=fire_params.get("decay", "linear"),
                                cooldown_span_s=fire_params.get("cooldown_span_s"),
                            )
                            chunk["fire_params"] = fire_params
                        except Exception as fire_exc:
                            # Pulse failed — keep streaming SMU reads; don't
                            # tear down the whole session for a bad fire.
                            self._stream_queue.put(("fire_error", fire_exc))
                            chunk = session.read_chunk(
                                vread=vread,
                                ilimit=ilimit,
                                irange=irange,
                                sample_interval_s=dt,
                                num_points=chunk_points,
                                fire_now=False,
                            )
                    else:
                        chunk = session.read_chunk(
                            vread=vread,
                            ilimit=ilimit,
                            irange=irange,
                            sample_interval_s=dt,
                            num_points=chunk_points,
                            fire_now=False,
                        )
                except Exception as exc:
                    self._stream_queue.put(("error", exc))
                    break
                self._stream_queue.put(("chunk", chunk))

            try:
                session.stop()
            except Exception:
                pass
            self._stream_queue.put(("stopped", None))

        self._stream_active = True
        self._stream_thread = threading.Thread(target=worker, daemon=True)
        self._stream_thread.start()
        self.root.after(100, self._poll_stream_queue)

    def _stop_streaming(self) -> None:
        if self._exp_active:
            self._stop_width_sweep()
        if getattr(self, "_routine_active", False):
            self._stop_routine()
        self._paused = False
        self._stream_pause_event.clear()
        self._stream_stop_event.set()
        self.live_stop_btn.configure(state=tk.DISABLED)
        self.live_fire_btn.configure(state=tk.DISABLED)
        self.live_pause_btn.configure(state=tk.DISABLED, text="\u23f8 Pause")
        if hasattr(self, "routine_stop_stream_btn"):
            self.routine_stop_stream_btn.configure(state=tk.DISABLED)
        if hasattr(self, "routine_pause_btn"):
            self.routine_pause_btn.configure(state=tk.DISABLED, text="\u23f8 Pause")
        self.live_status_var.set("Stopping (ramping SMU to 0 V)…")
        if hasattr(self, "routine_stream_status_var"):
            self.routine_stream_status_var.set("Stopping (ramping SMU to 0 V)…")

    def _update_pause_buttons(self) -> None:
        text = "\u25b6 Resume" if self._paused else "\u23f8 Pause"
        state = tk.NORMAL if self._stream_active else tk.DISABLED
        if hasattr(self, "live_pause_btn"):
            self.live_pause_btn.configure(text=text, state=state)
        if hasattr(self, "routine_pause_btn"):
            self.routine_pause_btn.configure(text=text, state=state)

    def _toggle_pause(self) -> None:
        if self._paused:
            self._resume_all()
        else:
            self._pause_all()

    def _pause_all(self) -> None:
        """Freeze everything in place: no new SMU reads/bias re-asserts, no
        more automatic pulses — bias stays exactly as last set, so it's safe
        to check the sample (e.g. under a scope). Resume picks up right
        where it left off (routine/sweep timers restart their full wait,
        rather than firing immediately)."""
        if self._paused or not self._stream_active:
            return
        self._paused = True
        self._stream_pause_event.set()

        if self._routine_active and self._routine_after_id is not None:
            try:
                self.root.after_cancel(self._routine_after_id)
            except Exception:
                pass
            self._routine_after_id = None

        if self._exp_active and self._exp_after_id is not None:
            try:
                self.root.after_cancel(self._exp_after_id)
            except Exception:
                pass
            self._exp_after_id = None

        self.live_fire_btn.configure(state=tk.DISABLED)
        if hasattr(self, "routine_start_btn") and not self._routine_active:
            self.routine_start_btn.configure(state=tk.DISABLED)
        if hasattr(self, "exp_start_btn") and not self._exp_active:
            self.exp_start_btn.configure(state=tk.DISABLED)
        msg = "\u23f8 PAUSED — no new pulses/SMU reads; bias held steady. Click Resume to continue."
        self.live_status_var.set(msg)
        if hasattr(self, "routine_stream_status_var"):
            self.routine_stream_status_var.set(msg)
        if self._routine_active:
            n = len(self._routine_plan)
            self.routine_status_var.set(
                f"\u23f8 PAUSED at step {self._routine_index}/{n} — click Resume to continue"
            )
        if self._exp_active:
            self.exp_status_var.set("\u23f8 Paused — click Resume to continue")
        self._update_pause_buttons()
        print("[PAUSE] Everything paused — safe to check the sample.", flush=True)

    def _resume_all(self) -> None:
        if not self._paused:
            return
        self._paused = False
        self._stream_pause_event.clear()

        if self._routine_active:
            wait_ms = max(50, int(getattr(self, "_routine_last_wait_ms", 200)))
            self._routine_after_id = self.root.after(wait_ms, self._routine_tick)
            n = len(self._routine_plan)
            self.routine_status_var.set(f"Resumed — step {self._routine_index}/{n}")

        if self._exp_active:
            try:
                interval_s = max(0.05, self._f(self.exp_interval_var))
            except Exception:
                interval_s = 10.0
            self._exp_after_id = self.root.after(int(interval_s * 1000), self._experiment_tick)
            self.exp_status_var.set("Resumed — sweep continuing")

        if self._stream_active:
            self.live_fire_btn.configure(state=tk.NORMAL)
        if hasattr(self, "routine_start_btn") and not self._routine_active:
            self.routine_start_btn.configure(state=tk.NORMAL)
        if hasattr(self, "exp_start_btn") and not self._exp_active:
            self.exp_start_btn.configure(state=tk.NORMAL)
        self.live_status_var.set("Resumed — streaming")
        if hasattr(self, "routine_stream_status_var"):
            self.routine_stream_status_var.set("Resumed — streaming")
        self._update_pause_buttons()
        print("[PAUSE] Resumed.", flush=True)

    def _fire_now(self) -> None:
        if not self._stream_active or self._paused:
            return
        try:
            # Captured HERE on the main thread (safe Tkinter access); the
            # worker thread only ever sees this plain dict via the queue.
            p = self._params()
        except Exception as exc:
            # Don't kill streaming — just refuse this fire and say why.
            self.live_status_var.set(f"Fire skipped: {exc}")
            return
        self._stream_fire_queue.put(p)
        self.live_fire_btn.configure(state=tk.DISABLED)
        self.live_status_var.set("Fire pending — will fire at start of next chunk…")

    def _poll_stream_queue(self) -> None:
        try:
            while True:
                kind, payload = self._stream_queue.get_nowait()
                if kind == "connected":
                    self.live_status_var.set("Streaming…")
                    self.live_fire_btn.configure(state=tk.NORMAL)
                    if hasattr(self, "routine_stop_stream_btn"):
                        self.routine_stop_stream_btn.configure(state=tk.NORMAL)
                    if hasattr(self, "routine_stream_status_var"):
                        self.routine_stream_status_var.set("Streaming…")
                elif kind == "chunk":
                    self._on_stream_chunk(payload)
                elif kind == "fire_error":
                    # Pulse failed but streaming continues — surface it without
                    # a modal that blocks the live session.
                    self.live_fire_btn.configure(state=tk.NORMAL)
                    self.live_status_var.set(f"Fire failed (streaming continues): {payload}")
                elif kind == "error":
                    self._stream_active = False
                    self._paused = False
                    self._stream_pause_event.clear()
                    if self._exp_active:
                        self._stop_width_sweep()
                    if getattr(self, "_routine_active", False):
                        self._stop_routine()
                    self.live_start_btn.configure(state=tk.NORMAL)
                    self.live_stop_btn.configure(state=tk.DISABLED)
                    self.live_fire_btn.configure(state=tk.DISABLED)
                    self.live_pause_btn.configure(state=tk.DISABLED, text="\u23f8 Pause")
                    if hasattr(self, "routine_stop_stream_btn"):
                        self.routine_stop_stream_btn.configure(state=tk.DISABLED)
                    if hasattr(self, "routine_pause_btn"):
                        self.routine_pause_btn.configure(state=tk.DISABLED, text="\u23f8 Pause")
                    self.live_status_var.set(f"Error: {payload}")
                    if hasattr(self, "routine_stream_status_var"):
                        self.routine_stream_status_var.set(f"Error: {payload}")
                    messagebox.showerror("Streaming error", str(payload))
                elif kind == "stopped":
                    self._stream_active = False
                    self._paused = False
                    self._stream_pause_event.clear()
                    if self._exp_active:
                        self._stop_width_sweep()
                    if getattr(self, "_routine_active", False):
                        self._stop_routine()
                    self.live_start_btn.configure(state=tk.NORMAL)
                    self.live_stop_btn.configure(state=tk.DISABLED)
                    self.live_fire_btn.configure(state=tk.DISABLED)
                    self.live_pause_btn.configure(state=tk.DISABLED, text="\u23f8 Pause")
                    if hasattr(self, "routine_stop_stream_btn"):
                        self.routine_stop_stream_btn.configure(state=tk.DISABLED)
                    if hasattr(self, "routine_pause_btn"):
                        self.routine_pause_btn.configure(state=tk.DISABLED, text="\u23f8 Pause")
                    n = len(self._stream_t)
                    self.live_status_var.set(f"Stopped — {n} points collected")
                    if hasattr(self, "routine_stream_status_var"):
                        self.routine_stream_status_var.set(f"Stopped — {n} points collected")
        except queue.Empty:
            pass

        if self._stream_active:
            self.root.after(100, self._poll_stream_queue)

    def _on_stream_chunk(self, chunk: Dict[str, Any]) -> None:
        # Timestamps / laser intervals are already absolute session seconds
        # from PmuLaserSmuStreamSession.read_chunk (continuous wall-clock axis).
        local_t = chunk.get("timestamps") or []
        self._stream_t.extend(local_t)
        self._stream_i.extend(chunk.get("currents") or [])
        self._stream_v.extend(chunk.get("voltages") or [])
        self._stream_r.extend(chunk.get("resistances") or [])
        if chunk.get("fired"):
            fire_params = chunk.get("fire_params") or {}
            for a, b in chunk.get("laser_on_intervals") or []:
                interval = (float(a), float(b))
                self._stream_intervals.append(interval)
                self._stream_fire_events.append(
                    {
                        "index": len(self._stream_fire_events) + 1,
                        "t_start_s": interval[0],
                        "t_end_s": interval[1],
                        "mode": fire_params.get("mode"),
                        "mode_label": self._mode_label(fire_params),
                        "params": fire_params,
                    }
                )
            self.live_fire_btn.configure(state=tk.NORMAL)
        if local_t:
            self._stream_elapsed = float(local_t[-1])

        n = len(self._stream_t)
        n_fires = len(self._stream_intervals)
        status = f"Streaming… t={self._stream_elapsed:.2f}s, {n} points, {n_fires} fire(s)"
        self.live_status_var.set(status)
        if hasattr(self, "routine_stream_status_var"):
            self.routine_stream_status_var.set(status)
        self._redraw_all_stream_plots()

    def _redraw_all_stream_plots(self) -> None:
        """Redraw every canvas subscribed to the shared stream buffers —
        currently the Live tab and (if built) the Automated Routine tab,
        since both drive the same single GPIB session/data buffers."""
        self._redraw_stream_plot(
            self.live_ax, self.live_canvas, "Live SMU resistance — manual fire session"
        )
        if hasattr(self, "routine_ax"):
            self._redraw_stream_plot(
                self.routine_ax, self.routine_canvas, "Live SMU resistance — automated routine"
            )

    def _redraw_stream_plot(self, ax, canvas, title: str) -> None:
        ax.clear()
        t = self._stream_t
        r = self._stream_r
        if t and r:
            ax.plot(t, r, color="#b35c00", lw=1.0, label="R(t)", zorder=2)
            trans = ax.get_xaxis_transform()
            seen_labels = set()
            for idx, (a, _b) in enumerate(self._stream_intervals):
                mode = None
                mode_label = None
                if idx < len(self._stream_fire_events):
                    ev = self._stream_fire_events[idx]
                    mode_label = ev.get("mode_label")
                    mode = ev.get("mode") or (ev.get("params") or {}).get("mode")
                color = self._pulse_color(mode)
                legend_label = None
                if mode_label and mode_label not in seen_labels:
                    legend_label = mode_label
                    seen_labels.add(mode_label)
                elif not mode_label and idx == 0:
                    legend_label = "Laser fired"
                # Fire marker only — no green duration band (SMU isn't reading
                # during the µs-scale PMU pulse).
                ax.axvline(
                    a, color=color, lw=1.2, linestyle="--",
                    label=legend_label, zorder=3,
                )
                if mode_label:
                    ax.text(
                        a, 1.02, mode_label, transform=trans,
                        color=color, fontsize=7, rotation=45,
                        ha="left", va="bottom", clip_on=False,
                    )
            ax.set_yscale("log")
            ax.set_xlabel("t (s) — wall clock (continuous)")
            ax.set_ylabel("R (Ohm)")
            ax.set_title(title)
            ax.grid(True, which="both", alpha=0.3)
            if self._stream_intervals:
                ax.legend(loc="best", fontsize=8)
        canvas.draw_idle()

    def _save_stream_csv(self, run_kind: str = "live_manual_fire") -> None:
        if not self._stream_t:
            messagebox.showwarning("No data", "Stream some data first.")
            return
        path, meta_path, sample, run_n = self._allocate_save_paths(
            "routine" if run_kind == "routine" else "live"
        )

        fire_events: List[Dict[str, Any]] = []
        fire_times: List[float] = []
        for ev in self._stream_fire_events:
            params = dict(ev.get("params") or {})
            t_fire = float(ev.get("t_start_s", 0.0))
            fire_times.append(t_fire)
            fire_events.append(
                {
                    "index": ev.get("index"),
                    "t_fire_s": t_fire,
                    "t_start_s": t_fire,
                    "t_end_s": ev.get("t_end_s"),
                    "mode": ev.get("mode") or params.get("mode"),
                    "decay": params.get("decay"),
                    "num_pulses": params.get("num_pulses"),
                    "mode_label": ev.get("mode_label"),
                    "params": params,
                }
            )
        laser_fire = self._laser_fire_markers(list(self._stream_t), fire_times)

        self._write_fires_and_data_csv(
            path,
            sample_name=sample,
            run_kind=run_kind,
            fire_events=fire_events,
            timestamps=list(self._stream_t),
            currents=list(self._stream_i),
            voltages=list(self._stream_v),
            resistances=list(self._stream_r),
            laser_fire=laser_fire,
            extra_header_lines=[
                f"run_index: {run_n}",
                f"vread_V: {self.vread_var.get().strip()}",
                f"irange_A: {self.irange_var.get().strip() or 'auto'}",
            ],
        )

        image_path: Optional[Path] = None
        try:
            vis_events = [
                {"width_s": fe["params"].get("width_s"), "percent": fe["params"].get("laser_power_mw")}
                for fe in fire_events
                if fe.get("params", {}).get("width_s") is not None
            ]
            if vis_events:
                fig = self._render_pulse_train_figure(
                    vis_events,
                    f"{sample} — run {run_n} ({run_kind}) — {len(vis_events)} pulse(s) fired",
                )
                image_path = path.with_name(f"{path.stem}_pulses.png")
                fig.savefig(image_path, dpi=150, bbox_inches="tight")
        except Exception:
            image_path = None

        meta = {
            "sample_name": sample,
            "section": self.section_var.get().strip() if hasattr(self, "section_var") else None,
            "device_number": self.device_var.get().strip() if hasattr(self, "device_var") else None,
            "run_index": run_n,
            "run_kind": run_kind,
            "laser_on_intervals": list(self._stream_intervals),
            "num_fires": len(fire_events),
            "fire_events": fire_events,
            "gpib": self.gpib_var.get().strip(),
            "vread": self._f(self.vread_var) if self.vread_var.get().strip() else None,
            "irange": self._irange(),
            "pulse_image": str(image_path) if image_path else None,
            "csv_format": {
                "table1": "laser_fires (#-commented rows)",
                "table2": "data columns t_s,I_A,V_V,R_Ohm,laser_fire",
                "laser_fire": "0=none; N=Nth fire marked on nearest sample",
            },
        }
        meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        self._save_config()
        self._refresh_sample_list()
        if image_path:
            self.status_var.set(f"Saved {self._display_rel_path(path)} + pulse image")
            messagebox.showinfo("Saved", f"Wrote:\n{path}\n{meta_path}\n{image_path}")
        else:
            self.status_var.set(f"Saved {self._display_rel_path(path)}")
            messagebox.showinfo("Saved", f"Wrote:\n{path}\n{meta_path}")

    # ---------------------------------------------------------------
    # Preset experiment: automatic pulse-width sweep
    # ---------------------------------------------------------------
    def _start_width_sweep(self) -> None:
        if self._exp_active:
            return
        try:
            start_w = self._f(self.exp_start_width_var)
            step_w = self._f(self.exp_step_width_var)
            max_w = self._f(self.exp_max_width_var)
            interval_s = self._f(self.exp_interval_var)
            if interval_s <= 0:
                raise ValueError("'Fire every (s)' must be > 0")
            if step_w == 0:
                raise ValueError("'Width step' must be nonzero")
        except Exception as exc:
            messagebox.showerror("Invalid experiment parameters", str(exc))
            return

        self.width_us_var.set(self._fmt_num(start_w))

        if not self._stream_active:
            self._start_streaming()

        self._exp_active = True
        self._exp_next_width_us = start_w
        self._exp_step_us = step_w
        self._exp_max_width_us = max_w
        self._exp_count = 0
        self.exp_start_btn.configure(state=tk.DISABLED)
        self.exp_stop_btn.configure(state=tk.NORMAL)
        self.exp_status_var.set(f"Sweep armed — first fire at {start_w:.3g} µs")
        self._exp_after_id = self.root.after(int(interval_s * 1000), self._experiment_tick)

    def _experiment_tick(self) -> None:
        if not self._exp_active:
            return
        if not self._stream_active:
            self.exp_status_var.set("Sweep stopped — streaming is not active")
            self._stop_width_sweep()
            return

        width_us = self._exp_next_width_us
        self.width_us_var.set(self._fmt_num(width_us))
        try:
            p = self._params()
        except Exception as exc:
            self.exp_status_var.set(f"Sweep stopped — invalid params: {exc}")
            self._stop_width_sweep()
            return
        self._stream_fire_queue.put(p)
        self._exp_count += 1

        done = False
        if self._exp_step_us > 0 and width_us + self._exp_step_us > self._exp_max_width_us:
            done = True
        elif self._exp_step_us < 0 and width_us + self._exp_step_us < self._exp_max_width_us:
            done = True
        self._exp_next_width_us = width_us + self._exp_step_us

        if done:
            self.exp_status_var.set(
                f"Sweep complete — fired {self._exp_count} pulse(s), last width {width_us:.3g} µs"
            )
            self._stop_width_sweep()
            return

        try:
            interval_s = max(0.05, self._f(self.exp_interval_var))
        except Exception:
            interval_s = 10.0
        self.exp_status_var.set(
            f"Fired #{self._exp_count} @ {width_us:.3g} µs — next in {interval_s:.3g}s "
            f"(\u2192 {self._exp_next_width_us:.3g} µs)"
        )
        self._exp_after_id = self.root.after(int(interval_s * 1000), self._experiment_tick)

    def _stop_width_sweep(self) -> None:
        self._exp_active = False
        if self._exp_after_id is not None:
            try:
                self.root.after_cancel(self._exp_after_id)
            except Exception:
                pass
            self._exp_after_id = None
        self.exp_start_btn.configure(state=tk.NORMAL)
        self.exp_stop_btn.configure(state=tk.DISABLED)

    @staticmethod
    def _fmt_num(value: float) -> str:
        """Compact string for a StringVar, avoiding float repr noise."""
        return f"{value:.6g}"

    # ---------------------------------------------------------------
    # Laser (serial, Oxxius) — used by the Automated Routine tab
    # ---------------------------------------------------------------
    def _connect_laser(self) -> None:
        if OxxiusLaser is None:
            messagebox.showerror("Laser", "pyserial is not installed — cannot connect.")
            return
        if self.laser is not None:
            return
        port = self.laser_port_var.get().strip()
        try:
            baud = int(self.laser_baud_var.get().strip())
        except ValueError:
            messagebox.showerror("Laser", "Invalid baud rate.")
            return
        self.laser_status_var.set(f"Connecting to {port}…")
        self.root.update_idletasks()
        try:
            laser = OxxiusLaser(port=port, baud=baud)
            idn = laser.idn()
            laser.prepare_for_ttl_modulation()
        except Exception as exc:
            self.laser_status_var.set("Disconnected")
            try:
                if "laser" in locals() and laser is not None:
                    laser.close(restore_to_manual_control=False)
            except Exception:
                pass
            messagebox.showerror("Laser connect failed", str(exc))
            return
        self.laser = laser
        self._laser_align_active = False
        self.laser_status_var.set(f"Connected ({idn}) — TTL mod armed, emission ON")
        self.laser_connect_btn.configure(state=tk.DISABLED)
        self.laser_disconnect_btn.configure(state=tk.NORMAL)
        for btn in (
            self.laser_emission_on_btn,
            self.laser_emission_off_btn,
            self.laser_set_power_btn,
            self.laser_align_on_btn,
            self.laser_align_off_btn,
            self.laser_restore_btn,
        ):
            btn.configure(state=tk.NORMAL)

    def _disconnect_laser(self) -> None:
        if self.laser is None:
            return
        if self._routine_active:
            self._stop_routine()
        try:
            self.laser.close(restore_to_manual_control=True)
        except Exception:
            pass
        self.laser = None
        self._laser_align_active = False
        self.laser_status_var.set("Disconnected")
        self.laser_connect_btn.configure(state=tk.NORMAL)
        self.laser_disconnect_btn.configure(state=tk.DISABLED)
        for btn in (
            self.laser_emission_on_btn,
            self.laser_emission_off_btn,
            self.laser_set_power_btn,
            self.laser_align_on_btn,
            self.laser_align_off_btn,
            self.laser_restore_btn,
        ):
            btn.configure(state=tk.DISABLED)

    def _laser_emission_on(self) -> None:
        if self.laser is None:
            return
        try:
            self.laser.emission_on()
            self.laser_status_var.set("Connected — emission ON")
        except Exception as exc:
            messagebox.showerror("Laser", f"Emission on failed: {exc}")

    def _laser_emission_off(self) -> None:
        if self.laser is None:
            return
        try:
            self.laser.emission_off()
            self.laser_status_var.set("Connected — emission OFF")
        except Exception as exc:
            messagebox.showerror("Laser", f"Emission off failed: {exc}")

    def _laser_set_power_now(self) -> None:
        """Manual one-off current-% set for pre-routine testing.

        Leaves emission OFF (same idea as pulse-testing Set power): call
        Emission On, or start the routine, when you want light.
        """
        if self.laser is None:
            return
        try:
            current_pct = float(self.laser_manual_power_var.get().strip())
        except ValueError:
            messagebox.showerror("Laser", "Invalid current (%).")
            return
        try:
            self.laser.set_current_percent_for_ttl(current_pct)
            self.laser_status_var.set(
                f"Current set to {current_pct:.3g} % (emission OFF — click On or Start routine)"
            )
        except Exception as exc:
            messagebox.showerror("Laser", f"Set current failed: {exc}")

    def _laser_align_on(self) -> None:
        """CW low-power beam for alignment: TTL mod off, set Align %, emission ON."""
        if self.laser is None:
            return
        if self._routine_active:
            messagebox.showwarning("Laser", "Stop the routine before entering Align mode.")
            return
        try:
            pct = float(self.laser_align_pct_var.get().strip())
        except ValueError:
            messagebox.showerror("Laser", "Invalid Align current (%).")
            return
        if pct <= 0:
            messagebox.showerror("Laser", "Align current (%) must be > 0.")
            return
        try:
            self.laser.enter_alignment_mode(pct)
            self._laser_align_active = True
            self.laser_status_var.set(f"Align ON — CW @ {pct:.3g} % (TTL mod off)")
        except Exception as exc:
            messagebox.showerror("Laser", f"Align ON failed: {exc}")

    def _laser_align_off(self) -> None:
        """Leave align mode: re-arm TTL digital modulation with emission ON."""
        if self.laser is None:
            return
        try:
            self.laser.prepare_for_ttl_modulation()
            self._laser_align_active = False
            self.laser_status_var.set("Connected — TTL mod armed, emission ON (ready for pulses)")
        except Exception as exc:
            messagebox.showerror("Laser", f"Align OFF failed: {exc}")

    def _laser_restore_manual(self) -> None:
        """Return the laser to normal front-panel-wheel manual control.
        Called automatically whenever the routine stops or finishes."""
        if self.laser is None:
            return
        try:
            self.laser.set_to_analog_modulation_mode(power_mw=100)
            self._laser_align_active = False
            self.laser_status_var.set("Connected — manual (front panel) control restored")
        except Exception as exc:
            messagebox.showerror("Laser", f"Restore manual control failed: {exc}")

    # ---------------------------------------------------------------
    # Automated Routine tab: width x power sweep helpers
    # ---------------------------------------------------------------
    def _generate_routine_widths(self) -> None:
        try:
            start_val = float(self.routine_start_width_var.get().strip())
            unit = self.routine_width_unit_var.get().strip() or "ns"
            unit_scale = {"ns": 1e-9, "us": 1e-6, "\u00b5s": 1e-6, "ms": 1e-3}.get(unit, 1e-9)
            start_s = start_val * unit_scale
            multiplier = float(self.routine_width_multiplier_var.get().strip())
            steps = int(float(self.routine_width_steps_var.get().strip()))
            widths_s = generate_decade_widths(start_s, multiplier, steps)
            self.routine_widths_var.set(format_width_list(widths_s))
        except Exception as exc:
            messagebox.showerror("Invalid width generator parameters", str(exc))

    def _update_routine_power_preview(self) -> None:
        if not hasattr(self, "routine_power_preview_var"):
            return
        try:
            start_mw = self._f(self.routine_start_power_var)
            step_mw = self._f(self.routine_power_step_var)
            max_mw = self._f(self.routine_power_max_var)
            levels = generate_power_levels(start_mw, step_mw, max_mw)
            preview = ", ".join(f"{lvl:.3g}" for lvl in levels)
            self.routine_power_preview_var.set(f"{len(levels)} level(s): {preview} %")
        except Exception as exc:
            self.routine_power_preview_var.set(f"(fix current % fields: {exc})")

    def _routine_widths_and_powers(self) -> Tuple[List[float], List[float]]:
        widths_s = parse_width_list(self.routine_widths_var.get())
        start_mw = self._f(self.routine_start_power_var)
        step_mw = self._f(self.routine_power_step_var)
        max_mw = self._f(self.routine_power_max_var)
        powers_mw = generate_power_levels(start_mw, step_mw, max_mw)
        return widths_s, powers_mw

    def _preview_routine_plan(self) -> None:
        try:
            widths_s, powers_mw = self._routine_widths_and_powers()
            plan = build_routine_plan(widths_s, powers_mw)
            settle_s = self._f(self.routine_settle_var)
            interval_s = self._f(self.routine_interval_var)
            text = describe_plan(plan, settle_s, interval_s)
        except Exception as exc:
            messagebox.showerror("Invalid routine parameters", str(exc))
            return
        messagebox.showinfo("Routine plan preview", text)

    # ---------------------------------------------------------------
    # Pulse-train visualizer: width-representative, height = current %
    # ---------------------------------------------------------------
    @staticmethod
    def _render_pulse_train_figure(
        events: List[Dict[str, Any]], title: str
    ) -> Figure:
        """Quick, NOT-to-scale visual of a pulse sequence.

        Each pulse is drawn as a bar: height = diode current setpoint (%),
        bar width = log-scaled pulse width (so ns..ms pulses are all
        visible side-by-side) — a schematic, not a true timing diagram
        (the laser is actually TTL-gated 0/5V; height here stands in for
        the current % armed at fire time).
        """
        n = len(events)
        fig_w = max(6.0, min(22.0, 0.55 * n + 2.2))
        fig = Figure(figsize=(fig_w, 4.2), dpi=100)
        ax = fig.add_subplot(111)
        if not events:
            ax.text(0.5, 0.5, "No pulses to show", ha="center", va="center")
            ax.axis("off")
            return fig

        widths_s = [max(float(e.get("width_s") or 1e-9), 1e-12) for e in events]
        log_w = [math.log10(w) for w in widths_s]
        lo, hi = min(log_w), max(log_w)
        span = (hi - lo) if hi > lo else 1.0
        gap = 0.28
        x = 0.0
        for e, lw, w_s in zip(events, log_w, widths_s):
            vw = 0.35 + 0.75 * ((lw - lo) / span)
            pct = e.get("percent")
            pct_val = float(pct) if pct is not None else 0.0
            color = cm.plasma(min(1.0, max(0.0, pct_val / 100.0)))
            ax.add_patch(
                Rectangle(
                    (x, 0),
                    vw,
                    pct_val,
                    facecolor=color,
                    edgecolor="black",
                    linewidth=0.6,
                )
            )
            label_pct = f"{pct_val:.3g}%" if pct is not None else "n/a"
            ax.text(x + vw / 2, pct_val + 3, label_pct, ha="center", va="bottom", fontsize=7)
            ax.text(
                x + vw / 2,
                -6,
                format_time_compact(w_s),
                ha="right",
                va="top",
                fontsize=6.5,
                rotation=45,
            )
            x += vw + gap

        ax.set_xlim(-gap, x)
        ax.set_ylim(-18, 112)
        ax.set_ylabel("Diode current setpoint (%)")
        ax.set_xticks([])
        ax.set_title(title, fontsize=10)
        ax.text(
            0.5,
            -0.22,
            "Schematic only — bar width is log-scaled pulse width (not true timing); "
            "height = current % armed at fire time.",
            transform=ax.transAxes,
            ha="center",
            fontsize=7,
            color="#666666",
        )
        fig.tight_layout(rect=(0, 0.06, 1, 1))
        return fig

    def _open_figure_window(self, fig: Figure, title: str) -> None:
        win = tk.Toplevel(self.root)
        win.title(title)
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.pack(fill=tk.BOTH, expand=True)
        try:
            w_px = min(1400, int(fig.get_size_inches()[0] * fig.dpi) + 40)
            h_px = min(900, int(fig.get_size_inches()[1] * fig.dpi) + 40)
            win.geometry(f"{w_px}x{h_px}")
        except Exception:
            pass

    def _show_routine_visual(self) -> None:
        try:
            widths_s, powers_mw = self._routine_widths_and_powers()
            plan = build_routine_plan(widths_s, powers_mw)
        except Exception as exc:
            messagebox.showerror("Invalid routine parameters", str(exc))
            return
        events = [
            {"width_s": step.width_s, "percent": step.power_mw}
            for step in plan
            if step.kind == "fire"
        ]
        fig = self._render_pulse_train_figure(
            events,
            f"Routine preview — {len(events)} pulse(s), {len(powers_mw)} current level(s)",
        )
        self._open_figure_window(fig, "Routine preview (schematic)")

    def _start_routine(self) -> None:
        if self._routine_active:
            return
        if self.laser is None:
            messagebox.showerror(
                "Routine", "Connect the laser first (Laser (serial) panel above)."
            )
            return
        try:
            widths_s, powers_mw = self._routine_widths_and_powers()
            plan = build_routine_plan(widths_s, powers_mw)
            settle_s = self._f(self.routine_settle_var)
            interval_s = self._f(self.routine_interval_var)
            if settle_s <= 0 or interval_s <= 0:
                raise ValueError("Settle time and Fire-every time must both be > 0")
        except Exception as exc:
            messagebox.showerror("Invalid routine parameters", str(exc))
            return

        if not self._stream_active:
            self._start_streaming()

        if getattr(self, "_laser_align_active", False):
            try:
                self.laser.prepare_for_ttl_modulation()
                self._laser_align_active = False
                self.laser_status_var.set("Connected — TTL mod re-armed for routine (emission ON)")
            except Exception as exc:
                messagebox.showerror("Routine", f"Could not leave Align mode: {exc}")
                return

        self._save_config()
        self._routine_plan = plan
        self._routine_index = 0
        self._routine_current_power_mw = None
        self._routine_active = True
        self.routine_start_btn.configure(state=tk.DISABLED)
        self.routine_stop_btn.configure(state=tk.NORMAL)

        pct_list = ", ".join(f"{p:.3g}%" for p in powers_mw)
        print("\n" + "=" * 60, flush=True)
        print("[ROUTINE] START", flush=True)
        print(f"[ROUTINE] Current levels: {pct_list}", flush=True)
        print(
            f"[ROUTINE] Widths: {format_width_list(widths_s)}",
            flush=True,
        )
        print(
            f"[ROUTINE] {len(plan)} step(s) | settle={settle_s:g}s | fire every={interval_s:g}s",
            flush=True,
        )
        print("=" * 60, flush=True)

        self.routine_status_var.set(f"Routine armed — {len(plan)} step(s)")
        self._routine_last_wait_ms = 200
        self._routine_after_id = self.root.after(200, self._routine_tick)

    def _routine_tick(self) -> None:
        if not self._routine_active:
            return
        if not self._stream_active:
            print("[ROUTINE] STOP — streaming is not active", flush=True)
            self.routine_status_var.set("Routine stopped — streaming is not active")
            self._stop_routine()
            return
        if self.laser is None:
            print("[ROUTINE] STOP — laser disconnected", flush=True)
            self.routine_status_var.set("Routine stopped — laser disconnected")
            self._stop_routine()
            return
        if self._routine_index >= len(self._routine_plan):
            print("[ROUTINE] All steps done — finishing.", flush=True)
            self._stop_routine(complete=True)
            return

        step = self._routine_plan[self._routine_index]
        self._routine_index += 1
        n = len(self._routine_plan)
        i = self._routine_index

        try:
            settle_s = max(0.05, self._f(self.routine_settle_var))
        except Exception:
            settle_s = 5.0
        try:
            interval_s = max(0.05, self._f(self.routine_interval_var))
        except Exception:
            interval_s = 5.0

        if step.kind == "set_power":
            pct = float(step.power_mw) if step.power_mw is not None else float("nan")
            print(
                f"[ROUTINE] Step {i}/{n}: SET CURRENT → {pct:.3g}% "
                f"(then settle {settle_s:g}s)",
                flush=True,
            )
            try:
                # Already in ACC+TTL+emission from connect; only change CM.
                self.laser.set_current_percent_for_ttl(pct)
                # Keep emission ON for TTL gating (no-op if already on).
                self.laser.emission_on()
            except Exception as exc:
                print(f"[ROUTINE] STOP — current set failed: {exc}", flush=True)
                self.routine_status_var.set(f"Routine stopped — current set failed: {exc}")
                self._stop_routine()
                return
            self._routine_current_power_mw = pct
            self.routine_status_var.set(
                f"Step {i}/{n}: current {pct:.3g}% — settling {settle_s:.3g}s"
            )
            wait_ms = int(settle_s * 1000)
        else:
            width_us = step.width_s * 1e6
            pct = self._routine_current_power_mw
            self.width_us_var.set(self._fmt_num(width_us))
            print(
                f"[ROUTINE] Step {i}/{n}: FIRE width={format_time_compact(step.width_s)} "
                f"@ current={pct:.3g}% (next in {interval_s:g}s)",
                flush=True,
            )
            try:
                p = self._params()
            except Exception as exc:
                print(f"[ROUTINE] STOP — invalid pulse params: {exc}", flush=True)
                self.routine_status_var.set(f"Routine stopped — invalid pulse params: {exc}")
                self._stop_routine()
                return
            p["laser_power_mw"] = self._routine_current_power_mw
            self._stream_fire_queue.put(p)
            self.routine_status_var.set(
                f"Step {i}/{n}: fire {format_time_compact(step.width_s)} "
                f"@ {pct:.3g}% — next in {interval_s:.3g}s"
            )
            wait_ms = int(interval_s * 1000)

        self._routine_last_wait_ms = wait_ms
        self._routine_after_id = self.root.after(wait_ms, self._routine_tick)

    def _stop_routine(self, complete: bool = False) -> None:
        self._routine_active = False
        if self._routine_after_id is not None:
            try:
                self.root.after_cancel(self._routine_after_id)
            except Exception:
                pass
            self._routine_after_id = None
        self.routine_start_btn.configure(state=tk.NORMAL)
        self.routine_stop_btn.configure(state=tk.DISABLED)
        n = len(self._routine_plan)
        print("\n" + "=" * 60, flush=True)
        if complete:
            print(f"[ROUTINE] COMPLETE — {n} step(s) finished.", flush=True)
            print("[ROUTINE] Restoring laser to manual (front-panel) control…", flush=True)
            self.routine_status_var.set(
                f"Routine complete — {n} step(s) done. "
                "Streaming still running — click Stop streaming, then Save routine CSV."
            )
            if self._stream_active and hasattr(self, "routine_stop_stream_btn"):
                self.routine_stop_stream_btn.configure(state=tk.NORMAL)
            if self._stream_active and hasattr(self, "routine_stream_status_var"):
                self.routine_stream_status_var.set(
                    "Streaming (routine finished) — click Stop streaming to end & save"
                )
        else:
            print(f"[ROUTINE] STOPPED early — after {self._routine_index}/{n} step(s).", flush=True)
            print("[ROUTINE] Restoring laser to manual (front-panel) control…", flush=True)
            self.routine_status_var.set(
                "Routine stopped — laser restored. "
                "If still streaming, click Stop streaming then Save routine CSV."
            )
            if self._stream_active and hasattr(self, "routine_stop_stream_btn"):
                self.routine_stop_stream_btn.configure(state=tk.NORMAL)
        self._laser_restore_manual()
        print("[ROUTINE] Done.", flush=True)
        print("=" * 60 + "\n", flush=True)
        self._save_config()


def main() -> None:
    root = tk.Tk()
    PmuLaserSmuReadGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
