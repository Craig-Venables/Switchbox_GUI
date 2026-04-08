"""
Laser FG Scope GUI — Main Window
=================================
LaserFGScopeGUI is a tk.Toplevel that can be launched standalone or
embedded in a parent Tk application (like the main Switchbox GUI).

Run standalone:
    python Laser_FG_Scope_GUI.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional

from .config import COLORS, FONT_FAMILY, WINDOW_MIN_H, WINDOW_MIN_W
from .config_manager import ConfigManager
from .layout import LayoutBuilder
from .logic import LaserFGScopeLogic
from .save_manager import SaveManager


class LaserFGScopeGUI(tk.Toplevel):
    """
    Main window for the Laser + Function Generator + Oscilloscope experiment GUI.

    Instruments:
      • Keithley 4200 SMU  — passive DC bias
      • Oxxius LBX-405     — laser (DM1 TTL-gate mode)
      • Siglent SDG1032X   — timing master / laser TTL driver
      • Tektronix TBS1000C — waveform capture

    The window manages:
      - Instrument connection / disconnection
      - Collecting parameters from UI panels
      - Launching the measurement thread (via LaserFGScopeLogic)
      - Updating plot and status from thread callbacks (thread-safe via after())
      - Settings load/save (ConfigManager)
    """

    def __init__(self, parent: tk.Widget, provider: Any = None) -> None:
        super().__init__(parent)
        self.title("Laser FG Scope — Pulse Experiment")
        self.minsize(WINDOW_MIN_W, WINDOW_MIN_H)
        self.geometry(f"{WINDOW_MIN_W}x{WINDOW_MIN_H}")

        self._cfg_manager = ConfigManager()
        self._cfg = self._cfg_manager.load()

        self._logic = LaserFGScopeLogic()
        self._layout: Optional[LayoutBuilder] = None

        # SaveManager — provider is the Measurement GUI instance if launched from there,
        # or None when run standalone.
        self._save_mgr = SaveManager(provider=provider)
        self._save_mgr.set_simple_path(self._cfg.get("simple_save_path", ""))
        self._save_mgr.auto_save = bool(self._cfg.get("auto_save", False))

        self._setup_style()
        self._setup_menu()
        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Style ─────────────────────────────────────────────────────────────────

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=(FONT_FAMILY, 9))
        style.configure("TLabelframe.Label", font=(FONT_FAMILY, 9, "bold"),
                        foreground=COLORS["header"])
        style.configure("Accent.TButton", foreground="white",
                        background=COLORS["header"])
        style.map("Accent.TButton",
                  background=[("active", "#0d47a1"), ("disabled", "#90a4ae")])

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _setup_menu(self) -> None:
        menubar = tk.Menu(self)
        self.configure(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Save settings", command=self._save_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Close", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        instr_menu = tk.Menu(menubar, tearoff=False)
        instr_menu.add_command(label="Disconnect all", command=self._disconnect_all)
        menubar.add_cascade(label="Instruments", menu=instr_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="Open README…", command=self._open_readme)
        menubar.add_cascade(label="Help", menu=help_menu)

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        callbacks = {
            # Connection
            "connect_fg":    self._connect_fg,
            "connect_laser": self._connect_laser,
            "connect_scope": self._connect_scope,
            "connect_smu":   self._connect_smu,
            # Laser
            "arm_laser":   self._arm_laser,
            "disarm_laser": self._disarm_laser,
            # Bias
            "apply_bias":  self._apply_bias,
            "bias_off":    self._bias_off,
            # Save
            "save_now": self._on_save_now,
            # Run
            "run":  self._on_run,
            "stop": self._on_stop,
        }
        self._layout = LayoutBuilder(self, callbacks, self._cfg)

        # Wire SaveManager into the save panel and plot panel
        if self._layout.save_panel:
            self._layout.save_panel.set_save_manager(self._save_mgr)
        if self._layout.plot_panel:
            self._layout.plot_panel.set_save_manager(self._save_mgr)

    # ── Instrument connection handlers ────────────────────────────────────────

    def _connect_fg(self, address: str):
        ok, msg = self._logic.connect_fg(address)
        return ok, msg

    def _connect_laser(self, port: str, baud: int):
        ok, msg = self._logic.connect_laser(port, baud)
        return ok, msg

    def _connect_scope(self, address: str):
        ok, msg = self._logic.connect_scope(address)
        return ok, msg

    def _connect_smu(self, address: str):
        ok, msg = self._logic.connect_smu(address)
        return ok, msg

    def _disconnect_all(self) -> None:
        self._logic.disconnect_fg()
        self._logic.disconnect_laser()
        self._logic.disconnect_scope()
        self._logic.disconnect_smu()
        self._set_status("All instruments disconnected.")

    # ── Laser handlers ────────────────────────────────────────────────────────

    def _arm_laser(self, power_mw: float):
        return self._logic.arm_laser_dm1(power_mw)

    def _disarm_laser(self):
        return self._logic.disarm_laser()

    # ── Bias handlers ─────────────────────────────────────────────────────────

    def _apply_bias(self, voltage: float, compliance: float):
        return self._logic.apply_bias(voltage, compliance)

    def _bias_off(self) -> None:
        self._logic.bias_off()

    # ── Run / Stop ────────────────────────────────────────────────────────────

    def _on_run(self) -> None:
        if self._logic.is_running:
            return

        params = self._layout.collect_params()

        self._layout.set_running(True)
        self._set_status("Measurement running…")

        self._logic.run_measurement(
            params=params,
            on_progress=lambda msg: self.after(0, self._set_status, msg),
            on_data=lambda t, v, meta: self.after(0, self._on_data, t, v, meta),
            on_error=lambda err: self.after(0, self._on_error, err),
            on_finished=lambda: self.after(0, self._on_finished),
        )

    def _on_stop(self) -> None:
        self._logic.stop_measurement()
        self._set_status("Stopping…")

    def _on_save_now(self) -> None:
        """Manual save triggered by the Save panel button."""
        if self._layout and self._layout.plot_panel:
            path = self._layout.plot_panel.save_to_manager()
            if self._layout.save_panel:
                self._layout.save_panel.notify_saved(path)
            if path:
                self._set_status(f"Saved: {path}")
            else:
                self._set_status("Save failed — set a save folder in the Save panel.")

    def _on_data(self, time_arr, volt_arr, meta: Dict[str, Any]) -> None:
        if self._layout and self._layout.plot_panel:
            self._layout.plot_panel.update_plot(time_arr, volt_arr, meta)

        # Auto-save if enabled
        if self._save_mgr.auto_save:
            path = self._save_mgr.save_capture(
                time_arr, volt_arr, meta,
                self._layout.plot_panel._fig if (self._layout and self._layout.plot_panel) else None,
            )
            if self._layout and self._layout.save_panel:
                self._layout.save_panel.notify_saved(path)
            if path:
                self._set_status(f"Auto-saved: {path}")

    def _on_error(self, err: str) -> None:
        self._set_status(f"Error: {err.splitlines()[0]}")
        messagebox.showerror("Measurement Error", err, parent=self)

    def _on_finished(self) -> None:
        self._layout.set_running(False)
        self._set_status("Done.")

    # ── Settings persistence ──────────────────────────────────────────────────

    def _save_settings(self) -> None:
        if self._layout:
            params = self._layout.collect_params()
            self._cfg.update(params)
        self._cfg_manager.save(self._cfg)
        self._set_status("Settings saved.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str) -> None:
        if self._layout:
            self._layout.set_status(msg)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "Laser FG Scope GUI\n\n"
            "Coordinates: Oxxius LBX-405 laser (DM1 TTL mode),\n"
            "Siglent SDG1032X function generator (timing master),\n"
            "Tektronix TBS1000C oscilloscope (waveform capture),\n"
            "Keithley 4200 SMU (passive DC bias).\n\n"
            "See gui/laser_fg_scope_gui/README.md for wiring details.",
            parent=self,
        )

    def _open_readme(self) -> None:
        import os, subprocess
        readme = os.path.join(os.path.dirname(__file__), "README.md")
        if os.path.exists(readme):
            os.startfile(readme)
        else:
            messagebox.showinfo("Not found", f"README not found at:\n{readme}", parent=self)

    def _on_close(self) -> None:
        if self._logic.is_running:
            if not messagebox.askyesno(
                "Measurement running",
                "A measurement is in progress. Stop it and close?",
                parent=self,
            ):
                return
            self._logic.stop_measurement()

        self._save_settings()
        self._disconnect_all()
        self.destroy()
