# -*- coding: utf-8 -*-
"""
AFM Holes & Protrusion — Standalone GUI
========================================
Launch this file directly:
    python tools/afm_3d_holes_protrusion/launch_gui.py

Tabs:
  • Single Preview — live threshold preview for one selected .ibw file
  • All Images     — grid view of every .ibw in the data folder with threshold overlay

Dependencies: tkinter (stdlib), matplotlib, numpy — plus the same deps as main.py

IMPORTANT: All .ibw files must be pre-levelled (plane-fitted) before use.
"""

from __future__ import annotations

import os
import sys
import math
import glob
import threading
import subprocess
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Resolve paths relative to this file so the GUI works from any cwd
# ---------------------------------------------------------------------------
_HERE        = Path(__file__).resolve().parent   # tools/afm_3d_holes_protrusion/
_DEFAULT_DATA   = _HERE / "Data"
_DEFAULT_OUTPUT = _HERE / "Output"

# ---------------------------------------------------------------------------
# Tkinter
# ---------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# ---------------------------------------------------------------------------
# Matplotlib
# ---------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import numpy as np
    _MPL_OK = True
    _MPL_ERR = ""
except ImportError as _e:
    _MPL_OK = False
    _MPL_ERR = str(_e)

# ---------------------------------------------------------------------------
# Lazy import of main.py helpers
# ---------------------------------------------------------------------------
_afm_main: Optional[object] = None


def _get_afm_main():
    global _afm_main
    if _afm_main is None:
        if str(_HERE) not in sys.path:
            sys.path.insert(0, str(_HERE))
        try:
            import main as _m
            _afm_main = _m
        except Exception:
            pass
    return _afm_main


# ===========================================================================
# Utility helpers
# ===========================================================================

def _measure_folder_size(folder: Path) -> tuple[float, int]:
    total = 0
    count = 0
    try:
        for dirpath, _, fnames in os.walk(folder):
            for fn in fnames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, fn))
                    count += 1
                except OSError:
                    pass
    except OSError:
        pass
    return total / (1024 * 1024), count


def _latest_run_folder(output_root: Path) -> Optional[Path]:
    runs = sorted(glob.glob(str(output_root / "Run_*")),
                  key=os.path.getmtime, reverse=True)
    return Path(runs[0]) if runs else None


def _scan_ibw_files(data_folder: Path) -> list[Path]:
    return sorted(data_folder.rglob("*.ibw"))


def _detect(z_nm, pixel_nm, hole_sd, prot_sd, use_robust):
    """Call main.detect_features with temporary SD overrides."""
    mod = _get_afm_main()
    if mod is None:
        raise RuntimeError("Could not import main.py")
    saved = {k: getattr(mod, k) for k in
             ("HOLE_THRESHOLD_SD", "PROT_THRESHOLD_SD", "USE_ROBUST_THRESHOLD")}
    mod.HOLE_THRESHOLD_SD  = hole_sd
    mod.PROT_THRESHOLD_SD  = prot_sd
    mod.USE_ROBUST_THRESHOLD = use_robust
    try:
        return mod.detect_features(z_nm, pixel_nm)
    finally:
        for k, v in saved.items():
            setattr(mod, k, v)


# ===========================================================================
# Shared threshold state (sliders live in the left panel but both tabs read them)
# ===========================================================================

class _ThresholdState:
    def __init__(self):
        self.hole_sd    = tk.DoubleVar(value=2.5)
        self.prot_sd    = tk.DoubleVar(value=1.5)
        self.use_robust = tk.BooleanVar(value=True)


# ===========================================================================
# Single-preview tab
# ===========================================================================

class SinglePreviewTab(ttk.Frame):
    def __init__(self, parent, thresh: _ThresholdState, status_cb):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._thresh    = thresh
        self._set_status = status_cb
        self._ibw_files: list[Path] = []
        self._z_nm: Optional[np.ndarray] = None
        self._pixel_nm  = 1.0
        self._debounce_id: Optional[str] = None
        self._fig       = None
        self._canvas    = None

        self._build()

    def _build(self):
        # File selector row
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
        ttk.Label(top, text="Preview file:").pack(side="left")
        self._file_var = tk.StringVar()
        self._combo = ttk.Combobox(top, textvariable=self._file_var,
                                   state="readonly", width=55)
        self._combo.pack(side="left", padx=4, fill="x", expand=True)
        self._combo.bind("<<ComboboxSelected>>", lambda e: self._load_file())

        if _MPL_OK:
            # Use constrained_layout so colorbars never shrink the axes
            self._fig = plt.figure(constrained_layout=True, figsize=(9, 4.5))
            self._fig.patch.set_facecolor("#f0f0f0")
            self._canvas = FigureCanvasTkAgg(self._fig, master=self)
            self._canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")
        else:
            ttk.Label(self, text=f"matplotlib unavailable: {_MPL_ERR}",
                      foreground="red").grid(row=1, column=0)

    # ── public API called by the main window ─────────────────────────────

    def set_files(self, ibw_files: list[Path], data_root: Path):
        self._ibw_files = ibw_files
        display = [str(p.relative_to(data_root)) for p in ibw_files]
        self._combo["values"] = display
        if display:
            self._file_var.set(display[0])
            self._load_file()

    def schedule_refresh(self):
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(220, self._redraw)

    # ── internals ────────────────────────────────────────────────────────

    def _load_file(self):
        if not _MPL_OK:
            return
        idx = self._combo.current()
        if idx < 0 or idx >= len(self._ibw_files):
            return
        fp = self._ibw_files[idx]
        mod = _get_afm_main()
        if mod is None:
            self._set_status("Could not import main.py for preview.")
            return
        self._set_status(f"Loading {fp.name}…")

        def _load():
            try:
                z, px, sx, sy = mod.load_ibw(str(fp))
                self._z_nm    = z
                self._pixel_nm = px
                self.after(0, self._redraw)
                self.after(0, self._set_status,
                           f"Preview: {fp.name}  |  {sx:.2f} × {sy:.2f} µm")
            except Exception as exc:
                self.after(0, self._set_status, f"Load error: {exc}")

        threading.Thread(target=_load, daemon=True).start()

    def _redraw(self):
        if not _MPL_OK or self._z_nm is None or self._fig is None:
            return

        z        = self._z_nm
        pixel_nm = self._pixel_nm
        hole_sd  = self._thresh.hole_sd.get()
        prot_sd  = self._thresh.prot_sd.get()
        robust   = self._thresh.use_robust.get()

        try:
            hole_mask, prot_mask, stats = _detect(z, pixel_nm, hole_sd, prot_sd, robust)
        except Exception as exc:
            self._set_status(f"Detection error: {exc}")
            return

        # Clear and rebuild — constrained_layout handles colorbars cleanly
        self._fig.clf()
        ax1, ax2 = self._fig.subplots(1, 2)

        ny, nx = z.shape
        extent = [0, nx * pixel_nm / 1000, 0, ny * pixel_nm / 1000]  # µm

        # Left: raw height map
        im1 = ax1.imshow(z, origin="lower", cmap="afmhot", aspect="equal",
                         extent=extent, interpolation="nearest")
        ax1.set_title("Height map", fontsize=9)
        ax1.set_xlabel("µm", fontsize=8)
        ax1.set_ylabel("µm", fontsize=8)
        cb = self._fig.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
        cb.set_label("nm", fontsize=7)
        cb.ax.tick_params(labelsize=7)

        # Right: threshold overlay on greyscale base
        ax2.imshow(z, origin="lower", cmap="gray", aspect="equal",
                   extent=extent, interpolation="nearest",
                   vmin=np.nanpercentile(z, 2), vmax=np.nanpercentile(z, 98))
        overlay = np.zeros((*z.shape, 4), dtype=float)
        overlay[hole_mask] = [0.18, 0.45, 0.85, 0.70]   # blue  — holes
        overlay[prot_mask] = [0.95, 0.25, 0.15, 0.70]   # red   — protrusions
        ax2.imshow(overlay, origin="lower", aspect="equal",
                   extent=extent, interpolation="nearest")

        n_h = int(np.sum(hole_mask))
        n_p = int(np.sum(prot_mask))
        ht  = stats.get("hole_thresh_nm", float("nan"))
        pt  = stats.get("prot_thresh_nm", float("nan"))
        ax2.set_title(
            f"Holes (blue): {n_h} px  |  Prots (red): {n_p} px\n"
            f"H thresh: {ht:.2f} nm    P thresh: {pt:.2f} nm",
            fontsize=8,
        )
        ax2.set_xlabel("µm", fontsize=8)

        self._canvas.draw_idle()


# ===========================================================================
# All-images tab
# ===========================================================================

class AllImagesTab(ttk.Frame):
    """Loads every .ibw in the data folder and shows a threshold-overlay grid."""

    _COLS = 3          # thumbnails per row
    _THUMB_INCH = 2.8  # inches per thumbnail

    def __init__(self, parent, thresh: _ThresholdState, status_cb):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._thresh      = thresh
        self._set_status  = status_cb
        self._ibw_files: list[Path] = []
        self._data_root: Optional[Path] = None
        self._loading     = False
        self._fig         = None
        self._canvas_widget = None

        self._build()

    def _build(self):
        # ── Warning banner ────────────────────────────────────────────────
        warn = tk.Frame(self, bg="#fff3cd", bd=1, relief="solid")
        warn.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        tk.Label(
            warn,
            text="⚠  All .ibw files must be pre-levelled (plane-fitted) before "
                 "analysis.\nUnlevelled scans will produce unreliable hole/protrusion "
                 "detection.",
            bg="#fff3cd", fg="#856404",
            font=("", 9, "bold"),
            justify="left",
            wraplength=900,
            padx=8, pady=6,
        ).pack(anchor="w")

        # ── Toolbar ───────────────────────────────────────────────────────
        bar = ttk.Frame(self)
        bar.grid(row=1, column=0, sticky="ew", padx=6, pady=(2, 4))
        self._load_btn = ttk.Button(bar, text="⟳  Load / Refresh All Images",
                                    command=self._start_load)
        self._load_btn.pack(side="left")
        self._prog_var = tk.StringVar(value="No images loaded.")
        ttk.Label(bar, textvariable=self._prog_var,
                  foreground="gray", font=("", 8)).pack(side="left", padx=10)

        # ── Scrollable canvas host ─────────────────────────────────────────
        host = ttk.Frame(self)
        host.grid(row=2, column=0, sticky="nsew")
        host.columnconfigure(0, weight=1)
        host.rowconfigure(0, weight=1)

        self._scroll_canvas = tk.Canvas(host, highlightthickness=0, bg="#e8e8e8")
        vsb = ttk.Scrollbar(host, orient="vertical",
                            command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        self._scroll_canvas.grid(row=0, column=0, sticky="nsew")

        self._inner = ttk.Frame(self._scroll_canvas)
        self._inner_id = self._scroll_canvas.create_window(
            (0, 0), window=self._inner, anchor="nw"
        )

        def _on_inner_config(e):
            self._scroll_canvas.configure(
                scrollregion=self._scroll_canvas.bbox("all")
            )

        def _on_scroll_config(e):
            self._scroll_canvas.itemconfig(self._inner_id, width=e.width)

        self._inner.bind("<Configure>", _on_inner_config)
        self._scroll_canvas.bind("<Configure>", _on_scroll_config)

        def _mwheel(e):
            self._scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self._scroll_canvas.bind_all("<MouseWheel>", _mwheel)

    # ── public API ────────────────────────────────────────────────────────

    def set_files(self, ibw_files: list[Path], data_root: Path):
        self._ibw_files  = ibw_files
        self._data_root  = data_root
        n = len(ibw_files)
        self._prog_var.set(
            f"{n} file{'s' if n != 1 else ''} found. Click 'Load / Refresh' to render grid."
        )

    # ── loading ───────────────────────────────────────────────────────────

    def _start_load(self):
        if self._loading:
            return
        if not _MPL_OK:
            messagebox.showerror("matplotlib missing",
                                 "Install matplotlib to use the image grid.")
            return
        if not self._ibw_files:
            messagebox.showinfo("No files", "No .ibw files found — browse to a Data folder first.")
            return
        self._loading = True
        self._load_btn.state(["disabled"])
        self._prog_var.set("Loading…")
        threading.Thread(target=self._load_all, daemon=True).start()

    def _load_all(self):
        mod = _get_afm_main()
        if mod is None:
            self.after(0, self._prog_var.set, "Could not import main.py")
            self.after(0, self._load_btn.state, ["!disabled"])
            self._loading = False
            return

        hole_sd  = self._thresh.hole_sd.get()
        prot_sd  = self._thresh.prot_sd.get()
        robust   = self._thresh.use_robust.get()

        results = []
        total   = len(self._ibw_files)
        for i, fp in enumerate(self._ibw_files):
            self.after(0, self._prog_var.set,
                       f"Loading {i + 1}/{total}: {fp.name}")
            try:
                z, px, sx, sy = mod.load_ibw(str(fp))
                hm, pm, stats = _detect(z, px, hole_sd, prot_sd, robust)
                results.append((fp, z, px, sx, sy, hm, pm, stats, None))
            except Exception as exc:
                results.append((fp, None, None, None, None, None, None, None, str(exc)))

        self.after(0, self._render_grid, results)

    def _render_grid(self, results):
        # Destroy previous matplotlib figure if any
        for widget in self._inner.winfo_children():
            widget.destroy()
        if self._fig is not None:
            plt.close(self._fig)
            self._fig = None

        n       = len(results)
        cols    = self._COLS
        rows    = math.ceil(n / cols)
        w_inch  = cols * self._THUMB_INCH
        h_inch  = max(rows * self._THUMB_INCH * 0.85, 2.0)

        fig = plt.figure(figsize=(w_inch, h_inch), constrained_layout=True)
        fig.patch.set_facecolor("#e8e8e8")
        self._fig = fig

        if rows == 0:
            ax = fig.add_subplot(1, 1, 1)
            ax.text(0.5, 0.5, "No results", ha="center", va="center")
        else:
            axes = fig.subplots(rows, cols, squeeze=False)
            for idx, (fp, z, px, sx, sy, hm, pm, stats, err) in enumerate(results):
                r, c = divmod(idx, cols)
                ax = axes[r][c]
                ax.set_xticks([])
                ax.set_yticks([])

                # Relative file name for title
                try:
                    label = str(fp.relative_to(self._data_root))
                except ValueError:
                    label = fp.name

                if err:
                    ax.set_facecolor("#fee")
                    ax.text(0.5, 0.5, f"Error:\n{err}", ha="center", va="center",
                            fontsize=6, color="red", wrap=True,
                            transform=ax.transAxes)
                    ax.set_title(label, fontsize=6, color="red")
                else:
                    ny, nx_px = z.shape
                    extent = [0, nx_px * px / 1000, 0, ny * px / 1000]
                    ax.imshow(z, origin="lower", cmap="gray", aspect="equal",
                              extent=extent, interpolation="nearest",
                              vmin=np.nanpercentile(z, 2),
                              vmax=np.nanpercentile(z, 98))
                    overlay = np.zeros((*z.shape, 4), dtype=float)
                    overlay[hm] = [0.18, 0.45, 0.85, 0.72]
                    overlay[pm] = [0.95, 0.25, 0.15, 0.72]
                    ax.imshow(overlay, origin="lower", aspect="equal",
                              extent=extent, interpolation="nearest")
                    nh = int(np.sum(hm))
                    np_ = int(np.sum(pm))
                    ax.set_title(
                        f"{label}\n{sx:.1f}×{sy:.1f}µm  H:{nh}px P:{np_}px",
                        fontsize=6,
                    )

            # Hide unused axes
            for idx in range(n, rows * cols):
                r, c = divmod(idx, cols)
                axes[r][c].set_visible(False)

        canvas = FigureCanvasTkAgg(fig, master=self._inner)
        self._canvas_widget = canvas.get_tk_widget()
        self._canvas_widget.pack(fill="both", expand=True)
        canvas.draw()

        self._prog_var.set(
            f"Showing {n} image{'s' if n != 1 else ''}  "
            f"(hole SD={self._thresh.hole_sd.get():.2f}, "
            f"prot SD={self._thresh.prot_sd.get():.2f})"
        )
        self._loading = False
        self._load_btn.state(["!disabled"])


# ===========================================================================
# Main application window
# ===========================================================================

class AFMGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AFM Holes & Protrusion Analyser")
        self.resizable(True, True)

        # Shared state
        self._thresh     = _ThresholdState()
        self._data_dir   = tk.StringVar(
            value=str(_DEFAULT_DATA) if _DEFAULT_DATA.exists() else "")
        self._output_dir = tk.StringVar(
            value=str(_DEFAULT_OUTPUT) if _DEFAULT_OUTPUT.exists() else "")
        self._ibw_files: list[Path] = []

        # Analysis checkboxes
        self._cb = {
            "PLOT_2D_MAP":               tk.BooleanVar(value=True),
            "PLOT_FEATURE_MAP":          tk.BooleanVar(value=True),
            "PLOT_3D_SURFACE":           tk.BooleanVar(value=False),
            "PLOT_HISTOGRAMS":           tk.BooleanVar(value=True),
            "PLOT_ROUGHNESS":            tk.BooleanVar(value=True),
            "PLOT_COMP_COUNTS":          tk.BooleanVar(value=True),
            "PLOT_COMP_DENSITY":         tk.BooleanVar(value=True),
            "PLOT_COMP_COVERAGE":        tk.BooleanVar(value=True),
            "PLOT_COMP_ROUGHNESS":       tk.BooleanVar(value=True),
            "PLOT_COMP_BOXPLOTS":        tk.BooleanVar(value=True),
            "PLOT_COMP_BUBBLE":          tk.BooleanVar(value=False),
            "PLOT_COMP_SPACING":         tk.BooleanVar(value=True),
            "PLOT_COMP_THRESHOLD_REVIEW":tk.BooleanVar(value=True),
            "PLOT_COMP_OVERVIEW":        tk.BooleanVar(value=False),
            "PLOT_COMP_RANKING":         tk.BooleanVar(value=False),
            "PLOT_COMP_FIXED_DEPTH":     tk.BooleanVar(value=False),
            "SUBSTRATE_COMPARISON":      tk.BooleanVar(value=True),
            "SAVE_PNGS":                 tk.BooleanVar(value=False),
        }

        self._running   = False
        self._run_proc: Optional[subprocess.Popen] = None

        self._build_ui()
        self._refresh_output_size()
        if Path(self._data_dir.get()).exists():
            self._on_data_folder_changed()

    # ------------------------------------------------------------------
    # Top-level layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.columnconfigure(0, weight=0, minsize=310)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Left panel ────────────────────────────────────────────────────
        left_outer = ttk.Frame(self, relief="groove", borderwidth=1)
        left_outer.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=6)
        left_outer.rowconfigure(0, weight=1)
        left_outer.columnconfigure(0, weight=1)

        scv = tk.Canvas(left_outer, width=290, highlightthickness=0)
        vsb = ttk.Scrollbar(left_outer, orient="vertical", command=scv.yview)
        scv.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        scv.grid(row=0, column=0, sticky="nsew")

        self._left = ttk.Frame(scv)
        _win = scv.create_window((0, 0), window=self._left, anchor="nw")

        self._left.bind("<Configure>",
                        lambda e: scv.configure(scrollregion=scv.bbox("all")))
        scv.bind("<Configure>",
                 lambda e: scv.itemconfig(_win, width=e.width))
        scv.bind_all("<MouseWheel>",
                     lambda e: scv.yview_scroll(int(-1 * e.delta / 120), "units"))

        self._build_left_panel(self._left)

        # ── Right panel (notebook) ─────────────────────────────────────────
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(3, 6), pady=6)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        nb = ttk.Notebook(right)
        nb.grid(row=0, column=0, sticky="nsew")

        self._single_tab = SinglePreviewTab(nb, self._thresh, self._set_status)
        nb.add(self._single_tab, text="  Single Preview  ")

        self._all_tab = AllImagesTab(nb, self._thresh, self._set_status)
        nb.add(self._all_tab, text="  All Images  ")

        # Log area below notebook
        right.rowconfigure(1, weight=0)
        right.rowconfigure(2, weight=1)
        ttk.Label(right, text="Run log:", font=("", 8, "bold")).grid(
            row=1, column=0, sticky="w", pady=(6, 0))
        self._log = ScrolledText(right, height=7, font=("Consolas", 8),
                                 state="disabled", bg="#1e1e1e", fg="#d4d4d4")
        self._log.grid(row=2, column=0, sticky="nsew")

    # ------------------------------------------------------------------
    # Left panel construction
    # ------------------------------------------------------------------

    def _section(self, parent, text: str) -> ttk.Frame:
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(8, 2))
        if text:
            ttk.Label(parent, text=text, font=("", 9, "bold")).pack(
                anchor="w", padx=4)
        f = ttk.Frame(parent)
        f.pack(fill="x", padx=8)
        return f

    def _build_left_panel(self, parent: ttk.Frame):
        # Title
        ttk.Label(parent, text="AFM Analyser", font=("", 12, "bold")).pack(
            anchor="w", padx=4, pady=(6, 0))
        ttk.Label(parent,
                  text="Configure analysis, preview thresholds,\nthen click Run.",
                  foreground="gray", font=("", 8)).pack(
            anchor="w", padx=4, pady=(0, 2))

        # Levelling warning
        warn = tk.Frame(parent, bg="#fff3cd", bd=1, relief="solid")
        warn.pack(fill="x", padx=4, pady=(2, 4))
        tk.Label(warn,
                 text="⚠  Pre-level all .ibw files before use.\n"
                      "Unlevelled scans give unreliable results.",
                 bg="#fff3cd", fg="#856404",
                 font=("", 8, "italic"),
                 justify="left", padx=6, pady=4,
                 wraplength=260).pack(anchor="w")

        # Folders
        f = self._section(parent, "Folders")
        self._add_folder_row(f, "Data:",   self._data_dir,   self._browse_data)
        self._add_folder_row(f, "Output:", self._output_dir, self._browse_output)

        # Threshold
        f = self._section(parent, "Detection Threshold")
        self._add_slider_row(f, "Hole SD", self._thresh.hole_sd,  0.1, 6.0)
        self._add_slider_row(f, "Prot SD", self._thresh.prot_sd, 0.1, 6.0)
        ttk.Checkbutton(f, text="Use robust stats (median/MAD)",
                        variable=self._thresh.use_robust,
                        command=self._on_thresh_change).pack(anchor="w", pady=2)

        # Per-sample plots
        f = self._section(parent, "Per-Sample Plots")
        for key, lbl in [
            ("PLOT_2D_MAP",      "2D Height Map"),
            ("PLOT_FEATURE_MAP", "Feature Map"),
            ("PLOT_3D_SURFACE",  "3D Surface"),
            ("PLOT_HISTOGRAMS",  "Histograms"),
            ("PLOT_ROUGHNESS",   "Roughness Analysis"),
        ]:
            ttk.Checkbutton(f, text=lbl, variable=self._cb[key]).pack(anchor="w")

        # Comparison plots
        f = self._section(parent, "Comparison Plots")
        for key, lbl in [
            ("PLOT_COMP_COUNTS",           "Counts & Density"),
            ("PLOT_COMP_COVERAGE",         "Surface Coverage"),
            ("PLOT_COMP_ROUGHNESS",        "Roughness"),
            ("PLOT_COMP_BOXPLOTS",         "Box Plots (depth/diam)"),
            ("PLOT_COMP_BUBBLE",           "Bubble Chart"),
            ("PLOT_COMP_SPACING",          "NN Spacing"),
            ("PLOT_COMP_THRESHOLD_REVIEW", "Threshold Review Grid"),
            ("PLOT_COMP_OVERVIEW",         "Stats Overview"),
            ("PLOT_COMP_RANKING",          "Ranking Table"),
            ("PLOT_COMP_FIXED_DEPTH",      "Fixed-Depth Sensitivity"),
        ]:
            ttk.Checkbutton(f, text=lbl, variable=self._cb[key]).pack(anchor="w")

        # Other
        f = self._section(parent, "Other")
        ttk.Checkbutton(f, text="Substrate comparison",
                        variable=self._cb["SUBSTRATE_COMPARISON"]).pack(anchor="w")
        ttk.Checkbutton(f, text="Save PNGs",
                        variable=self._cb["SAVE_PNGS"]).pack(anchor="w")

        # Buttons
        self._section(parent, "")
        bf = ttk.Frame(parent)
        bf.pack(fill="x", padx=8, pady=(4, 2))

        self._run_btn = ttk.Button(bf, text="▶  Run Analysis",
                                   command=self._run_analysis)
        self._run_btn.pack(fill="x", pady=2)
        ttk.Button(bf, text="📂  Open Output Folder",
                   command=self._open_output_folder).pack(fill="x", pady=2)

        # Output size
        self._size_var = tk.StringVar(value="Output size: —")
        ttk.Label(parent, textvariable=self._size_var,
                  foreground="gray", font=("", 8)).pack(
            anchor="w", padx=8, pady=(4, 2))

        # Status
        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(parent, textvariable=self._status_var,
                  wraplength=270, foreground="steelblue",
                  font=("", 8)).pack(anchor="w", padx=8, pady=(0, 6))

    def _add_folder_row(self, parent, label, var, command):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=label, width=7).pack(side="left")
        ttk.Entry(row, textvariable=var, font=("", 7)).pack(
            side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse", width=7,
                   command=command).pack(side="left", padx=(2, 0))

    def _add_slider_row(self, parent, label: str,
                        var: tk.DoubleVar, from_: float, to: float):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=9).pack(side="left")
        val_lbl = ttk.Label(row, text=f"{var.get():.2f}", width=5, anchor="e")
        val_lbl.pack(side="right")
        ttk.Scale(
            row, from_=from_, to=to, orient="horizontal", variable=var,
            command=lambda v, vl=val_lbl: (
                vl.config(text=f"{float(v):.2f}"),
                self._on_thresh_change(),
            ),
        ).pack(side="left", fill="x", expand=True)

    # ------------------------------------------------------------------
    # Threshold change — update single preview only (all-images needs manual refresh)
    # ------------------------------------------------------------------

    def _on_thresh_change(self):
        self._single_tab.schedule_refresh()

    # ------------------------------------------------------------------
    # Folder browse
    # ------------------------------------------------------------------

    def _browse_data(self):
        d = filedialog.askdirectory(title="Select Data Folder",
                                    initialdir=self._data_dir.get() or str(_HERE))
        if d:
            self._data_dir.set(d)
            self._on_data_folder_changed()

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select Output Folder",
                                    initialdir=self._output_dir.get() or str(_HERE))
        if d:
            self._output_dir.set(d)
            self._refresh_output_size()

    def _on_data_folder_changed(self):
        data_p = Path(self._data_dir.get())
        if not data_p.exists():
            self._ibw_files = []
            return
        self._ibw_files = _scan_ibw_files(data_p)
        self._single_tab.set_files(self._ibw_files, data_p)
        self._all_tab.set_files(self._ibw_files, data_p)

    # ------------------------------------------------------------------
    # Output size
    # ------------------------------------------------------------------

    def _refresh_output_size(self):
        out_root = Path(self._output_dir.get())
        if not out_root.exists():
            self._size_var.set("Output size: folder not found")
            return
        latest = _latest_run_folder(out_root)
        if latest is None:
            sz, cnt = _measure_folder_size(out_root)
            self._size_var.set(f"Output: {sz:.1f} MB, {cnt} files")
        else:
            sz, cnt = _measure_folder_size(latest)
            self._size_var.set(f"Last run: {latest.name}  —  {sz:.1f} MB, {cnt} files")

    # ------------------------------------------------------------------
    # Run analysis
    # ------------------------------------------------------------------

    def _build_env(self) -> dict:
        env = os.environ.copy()
        env["AFM_GUI_HOLE_THRESHOLD_SD"]  = str(self._thresh.hole_sd.get())
        env["AFM_GUI_PROT_THRESHOLD_SD"]  = str(self._thresh.prot_sd.get())
        env["AFM_GUI_USE_ROBUST_THRESHOLD"] = "1" if self._thresh.use_robust.get() else "0"
        for key, var in self._cb.items():
            if key == "SUBSTRATE_COMPARISON":
                continue
            env[f"AFM_GUI_{key}"] = "1" if var.get() else "0"
        return env

    def _run_analysis(self):
        if self._running:
            self._set_status("Analysis already running — please wait.")
            return
        main_script = str(_HERE / "main.py")
        if not Path(main_script).exists():
            messagebox.showerror("Not found",
                                 f"Cannot find main.py at:\n{main_script}")
            return
        data_dir = self._data_dir.get()
        if not data_dir or not Path(data_dir).exists():
            messagebox.showerror("No data folder",
                                 "Please select a valid Data folder first.")
            return

        self._running = True
        self._run_btn.state(["disabled"])
        self._set_status("Running analysis…")
        self._log_clear()
        self._log_append(f"► python {main_script}\n  Data: {data_dir}\n\n")

        env = self._build_env()

        def _stream():
            try:
                proc = subprocess.Popen(
                    [sys.executable, main_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    env=env, cwd=str(_HERE),
                )
                self._run_proc = proc
                for line in proc.stdout:
                    self.after(0, self._log_append, line)
                proc.wait()
                self.after(0, self._on_run_finished, proc.returncode)
            except Exception as exc:
                self.after(0, self._log_append, f"\nERROR: {exc}\n")
                self.after(0, self._on_run_finished, -1)

        threading.Thread(target=_stream, daemon=True).start()

    def _on_run_finished(self, rc: int):
        self._running   = False
        self._run_proc  = None
        self._run_btn.state(["!disabled"])
        if rc == 0:
            self._set_status("Analysis complete.")
            self._log_append("\n✓ Finished successfully.\n")
        else:
            self._set_status(f"Finished with errors (code {rc}).")
            self._log_append(f"\n✗ Return code {rc}.\n")
        self._refresh_output_size()

    # ------------------------------------------------------------------
    # Open output folder
    # ------------------------------------------------------------------

    def _open_output_folder(self):
        out_root = Path(self._output_dir.get())
        latest   = _latest_run_folder(out_root) if out_root.exists() else None
        target   = latest if latest else out_root
        if target.exists():
            os.startfile(str(target))
        else:
            messagebox.showinfo("Not found",
                                f"Output folder not found:\n{target}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str):
        self._status_var.set(msg)

    def _log_clear(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _log_append(self, text: str):
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    app = AFMGui()
    app.geometry("1340x860")
    app.minsize(950, 620)
    app.mainloop()


if __name__ == "__main__":
    main()
