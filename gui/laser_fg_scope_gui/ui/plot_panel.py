"""
Laser FG Scope GUI — Waveform Plot Panel
=========================================
Matplotlib canvas embedded in Tkinter.
Displays time (µs or ns) vs voltage (V or mV) from the last scope capture.
Includes save (CSV + PNG) and clear buttons.
"""

from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any, Dict, Optional

import numpy as np

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    _MPL_OK = True
except ImportError:
    _MPL_OK = False


class PlotPanel(tk.Frame):
    """
    Waveform display with Matplotlib, save and clear controls.
    """

    def __init__(self, parent: tk.Widget, **kw) -> None:
        super().__init__(parent, bg="#f0f0f0", **kw)
        self._time_arr:  Optional[np.ndarray] = None
        self._volt_arr:  Optional[np.ndarray] = None
        self._meta: Dict[str, Any] = {}
        self._save_mgr: Any = None   # SaveManager, set by main.py
        self._build()

    def set_save_manager(self, mgr: Any) -> None:
        """Wire in the SaveManager (called by main.py after build)."""
        self._save_mgr = mgr

    def _build(self) -> None:
        if not _MPL_OK:
            tk.Label(self, text="matplotlib not installed — no plot available.",
                     fg="red", bg="#f0f0f0").pack(expand=True)
            return

        # ── Matplotlib figure ─────────────────────────────────────────────────
        self._fig = Figure(figsize=(6, 4), dpi=100, tight_layout=True)
        self._fig.patch.set_facecolor("#ffffff")
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor("#ffffff")
        self._ax.tick_params(labelsize=8)
        self._ax.grid(True, color="#e0e0e0", linestyle="--", linewidth=0.5)
        self._ax.set_xlabel("Time", fontsize=9)
        self._ax.set_ylabel("Voltage (V)", fontsize=9)
        self._ax.set_title("Laser Pulse — Scope Capture", fontsize=10)
        self._line, = self._ax.plot([], [], color="#1565c0", linewidth=1.0)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        # Matplotlib toolbar (zoom, pan, etc.)
        toolbar_frame = tk.Frame(self, bg="#f0f0f0")
        toolbar_frame.pack(fill="x")
        self._toolbar = NavigationToolbar2Tk(self._canvas, toolbar_frame)
        self._toolbar.update()

        # ── Buttons row ───────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg="#f0f0f0")
        btn_row.pack(fill="x", padx=4, pady=(2, 4))

        ttk.Button(btn_row, text="Save CSV + PNG…", command=self._save_manual).pack(
            side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Clear", command=self.clear).pack(side="left")

        self._info_var = tk.StringVar(value="No data yet — press Run to capture.")
        tk.Label(btn_row, textvariable=self._info_var, fg="#555",
                 bg="#f0f0f0", font=("Segoe UI", 8)).pack(side="left", padx=(12, 0))

    def update_plot(
        self,
        time_arr: np.ndarray,
        volt_arr: np.ndarray,
        meta: Dict[str, Any],
    ) -> None:
        """Replace plot contents with new waveform data."""
        if not _MPL_OK:
            return
        self._time_arr = np.asarray(time_arr, dtype=np.float64)
        self._volt_arr = np.asarray(volt_arr, dtype=np.float64)
        self._meta = meta

        if len(self._time_arr) < 2:
            self._info_var.set("Empty waveform returned from scope.")
            return

        # Choose best time unit
        span = float(self._time_arr[-1] - self._time_arr[0])
        if span < 1e-6:
            t_scale, t_unit = 1e9, "ns"
        elif span < 1e-3:
            t_scale, t_unit = 1e6, "µs"
        else:
            t_scale, t_unit = 1e3, "ms"

        t_plot = self._time_arr * t_scale
        v_plot = self._volt_arr

        self._ax.cla()
        self._ax.set_facecolor("#ffffff")
        self._ax.grid(True, color="#e0e0e0", linestyle="--", linewidth=0.5)
        self._ax.plot(t_plot, v_plot, color="#1565c0", linewidth=1.0)
        self._ax.set_xlabel(f"Time ({t_unit})", fontsize=9)
        self._ax.set_ylabel("Voltage (V)", fontsize=9)

        pulse_w = meta.get("pulse_width_ns", 0)
        mode    = meta.get("fg_mode", "?").upper()
        bias_v  = meta.get("bias_v", 0.0)
        pwr_mw  = meta.get("laser_power_mw", 0.0)
        self._ax.set_title(
            f"{mode} mode  |  {pulse_w:.0f} ns  |  bias {bias_v:.2f} V  |  laser {pwr_mw:.1f} mW",
            fontsize=9,
        )
        self._fig.tight_layout()
        self._canvas.draw()

        ts = time.strftime("%H:%M:%S", time.localtime(meta.get("timestamp", time.time())))
        self._info_var.set(
            f"Captured {len(v_plot)} pts  |  {ts}  |  "
            f"Vpp {float(np.ptp(v_plot)):.3f} V"
        )

    def clear(self) -> None:
        if not _MPL_OK:
            return
        self._time_arr = None
        self._volt_arr = None
        self._ax.cla()
        self._ax.set_facecolor("#ffffff")
        self._ax.grid(True, color="#e0e0e0", linestyle="--", linewidth=0.5)
        self._ax.set_title("Laser Pulse — Scope Capture", fontsize=10)
        self._canvas.draw()
        self._info_var.set("No data yet — press Run to capture.")

    def save_to_manager(self) -> Optional[str]:
        """
        Save using the wired SaveManager.  Returns saved path or None.
        Called by main.py for auto-save and by save_panel's manual button.
        """
        if self._save_mgr is None or self._time_arr is None:
            return None
        fig = self._fig if _MPL_OK else None
        return self._save_mgr.save_capture(self._time_arr, self._volt_arr,
                                           self._meta, fig)

    def _save_manual(self) -> None:
        """Manual save — use SaveManager if configured, else fall back to dialog."""
        if self._time_arr is None or self._volt_arr is None:
            tk.messagebox.showinfo("Nothing to save", "Run a measurement first.")
            return

        # If a save manager with a valid directory is configured, use it
        if self._save_mgr is not None and self._save_mgr._resolve_dir() is not None:
            path = self.save_to_manager()
            if path:
                self._info_var.set(f"Saved: {os.path.basename(path)}")
            else:
                self._info_var.set("⚠ Save failed — check Save panel folder")
            return

        # Fallback: file dialog (no folder configured yet)
        stem = time.strftime("laser_scope_%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            initialfile=stem,
            title="Save waveform data",
        )
        if not path:
            return
        csv_path = path if path.endswith(".csv") else path + ".csv"
        png_path = os.path.splitext(csv_path)[0] + ".png"

        import csv as _csv
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            fh.write("# Laser FG Scope — Fast Optical Pulse Capture\n")
            fh.write(f"# Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            for k, v in self._meta.items():
                fh.write(f"# {k}: {v}\n")
            fh.write("#\n")
            fh.write("time_s,voltage_V\n")
            writer = _csv.writer(fh)
            for t, v in zip(self._time_arr, self._volt_arr):
                writer.writerow([f"{t:.12e}", f"{v:.8e}"])

        if _MPL_OK:
            self._fig.savefig(png_path, dpi=150, bbox_inches="tight")

        self._info_var.set(f"Saved: {os.path.basename(csv_path)}")

    def has_data(self) -> bool:
        return self._time_arr is not None and len(self._time_arr) > 1
