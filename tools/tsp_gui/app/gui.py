"""Tkinter shell for the standalone 2450 TSP pulse + optical GUI."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Optional

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from . import config
from .connection import SMUConnection, list_usb_resources
from .laser import LaserConnection, list_com_ports
from .optical_runner import run_optical_test
from .plot import plot_results
from .runner import run_electrical_test, save_results
from .tests import (
    OPTICAL_FUNCTIONS,
    get_2450_test_definitions,
    split_electrical_optical,
)


class TSP2450App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(config.WINDOW_GEOMETRY)

        config.ensure_dirs()
        self.settings = config.load_settings()

        self.smu = SMUConnection()
        self.laser_conn = LaserConnection()
        self.definitions = get_2450_test_definitions()
        self.electrical_defs, self.optical_defs = split_electrical_optical(self.definitions)

        self.param_vars: Dict[str, Dict[str, Any]] = {}
        self.optical_param_vars: Dict[str, Dict[str, Any]] = {}
        self._busy = False
        self._stop_flag = threading.Event()
        self.last_results: Any = None
        self.last_func: Optional[str] = None
        self.last_plot_type = "time_series"

        self._build_ui()
        self._restore_settings()
        self.refresh_usb()
        self.refresh_com()
        self.log("2450 TSP GUI ready. Set instrument Command Set = TSP before connecting.")

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill=tk.X)

        # SMU USB
        smu_fr = ttk.LabelFrame(top, text="Keithley 2450 (USB / TSP)", padding=6)
        smu_fr.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        row = ttk.Frame(smu_fr)
        row.pack(fill=tk.X)
        ttk.Label(row, text="VISA:").pack(side=tk.LEFT)
        self.usb_var = tk.StringVar()
        self.usb_combo = ttk.Combobox(row, textvariable=self.usb_var, width=48)
        self.usb_combo.pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="Refresh", command=self.refresh_usb).pack(side=tk.LEFT)

        row2 = ttk.Frame(smu_fr)
        row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="Terminals:").pack(side=tk.LEFT)
        self.term_var = tk.StringVar(value=config.DEFAULT_TERMINALS)
        ttk.Radiobutton(row2, text="Front", variable=self.term_var, value="front").pack(side=tk.LEFT)
        ttk.Radiobutton(row2, text="Rear", variable=self.term_var, value="rear").pack(side=tk.LEFT, padx=(0, 8))
        self.smu_conn_btn = ttk.Button(row2, text="Connect", command=self.connect_smu)
        self.smu_conn_btn.pack(side=tk.LEFT)
        self.smu_disc_btn = ttk.Button(row2, text="Disconnect", command=self.disconnect_smu, state=tk.DISABLED)
        self.smu_disc_btn.pack(side=tk.LEFT, padx=4)
        self.smu_status = tk.StringVar(value="Disconnected")
        ttk.Label(row2, textvariable=self.smu_status).pack(side=tk.LEFT, padx=8)

        # Laser
        laser_fr = ttk.LabelFrame(top, text="Oxxius laser (COM)", padding=6)
        laser_fr.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lrow = ttk.Frame(laser_fr)
        lrow.pack(fill=tk.X)
        ttk.Label(lrow, text="Port:").pack(side=tk.LEFT)
        self.com_var = tk.StringVar(value=config.DEFAULT_LASER_PORT)
        self.com_combo = ttk.Combobox(lrow, textvariable=self.com_var, width=10)
        self.com_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(lrow, text="Baud:").pack(side=tk.LEFT)
        self.baud_var = tk.StringVar(value=str(config.DEFAULT_LASER_BAUD))
        ttk.Entry(lrow, textvariable=self.baud_var, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(lrow, text="Refresh", command=self.refresh_com).pack(side=tk.LEFT)

        lrow2 = ttk.Frame(laser_fr)
        lrow2.pack(fill=tk.X, pady=4)
        self.laser_conn_btn = ttk.Button(lrow2, text="Connect", command=self.connect_laser)
        self.laser_conn_btn.pack(side=tk.LEFT)
        self.laser_disc_btn = ttk.Button(lrow2, text="Disconnect", command=self.disconnect_laser, state=tk.DISABLED)
        self.laser_disc_btn.pack(side=tk.LEFT, padx=4)
        self.laser_status = tk.StringVar(value="Disconnected")
        ttk.Label(lrow2, textvariable=self.laser_status).pack(side=tk.LEFT, padx=8)

        lrow3 = ttk.Frame(laser_fr)
        lrow3.pack(fill=tk.X)
        ttk.Label(lrow3, text="Power mW:").pack(side=tk.LEFT)
        self.laser_power_var = tk.StringVar(value="1.0")
        ttk.Entry(lrow3, textvariable=self.laser_power_var, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(lrow3, text="Set", command=self.laser_set_power).pack(side=tk.LEFT)
        ttk.Button(lrow3, text="On", command=self.laser_on).pack(side=tk.LEFT, padx=2)
        ttk.Button(lrow3, text="Off", command=self.laser_off).pack(side=tk.LEFT)
        ttk.Label(lrow3, text="Pulse ms:").pack(side=tk.LEFT, padx=(8, 0))
        self.laser_pulse_ms = tk.StringVar(value="100")
        ttk.Entry(lrow3, textvariable=self.laser_pulse_ms, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(lrow3, text="Pulse", command=self.laser_pulse).pack(side=tk.LEFT)
        ttk.Label(lrow3, text="N:").pack(side=tk.LEFT, padx=(6, 0))
        self.laser_n = tk.StringVar(value="5")
        ttk.Entry(lrow3, textvariable=self.laser_n, width=4).pack(side=tk.LEFT)
        ttk.Label(lrow3, text="Off ms:").pack(side=tk.LEFT)
        self.laser_off_ms = tk.StringVar(value="100")
        ttk.Entry(lrow3, textvariable=self.laser_off_ms, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(lrow3, text="Train", command=self.laser_train).pack(side=tk.LEFT)

        # Notebook
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.manual_tab = ttk.Frame(nb)
        self.optical_tab = ttk.Frame(nb)
        nb.add(self.manual_tab, text="Pulse tests")
        nb.add(self.optical_tab, text="Optical tests")

        self._build_test_tab(self.manual_tab, electrical=True)
        self._build_test_tab(self.optical_tab, electrical=False)

        # Plot + log
        bottom = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        bottom.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        plot_fr = ttk.Frame(bottom)
        log_fr = ttk.Frame(bottom)
        bottom.add(plot_fr, weight=3)
        bottom.add(log_fr, weight=1)

        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Results")
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_fr)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = NavigationToolbar2Tk(self.canvas, plot_fr)
        toolbar.update()

        ttk.Label(log_fr, text="Log").pack(anchor=tk.W)
        self.log_text = tk.Text(log_fr, height=16, width=40, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        btn_row = ttk.Frame(log_fr)
        btn_row.pack(fill=tk.X, pady=4)
        ttk.Button(btn_row, text="Clear log", command=lambda: self.log_text.delete("1.0", tk.END)).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Save folder…", command=self.choose_save_folder).pack(side=tk.LEFT, padx=4)
        self.save_dir_var = tk.StringVar(value=str(config.DATA_DIR))
        ttk.Label(btn_row, textvariable=self.save_dir_var).pack(side=tk.LEFT)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_test_tab(self, parent: ttk.Frame, electrical: bool) -> None:
        left = ttk.Frame(parent, padding=6)
        left.pack(side=tk.LEFT, fill=tk.Y)
        right = ttk.Frame(parent, padding=6)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        defs = self.electrical_defs if electrical else self.optical_defs
        names = list(defs.keys()) or ["(none)"]

        ttk.Label(left, text="Test").pack(anchor=tk.W)
        var = tk.StringVar(value=names[0])
        combo = ttk.Combobox(left, textvariable=var, values=names, width=36, state="readonly")
        combo.pack(anchor=tk.W, pady=2)

        desc = tk.Text(left, height=6, width=40, wrap=tk.WORD)
        desc.pack(fill=tk.X, pady=4)

        params_fr = ttk.LabelFrame(right, text=f"Parameters (time unit: {config.TIME_UNIT})" if electrical else "Parameters", padding=6)
        params_fr.pack(fill=tk.BOTH, expand=True)

        run_row = ttk.Frame(left)
        run_row.pack(fill=tk.X, pady=8)
        run_btn = ttk.Button(run_row, text="Run")
        run_btn.pack(side=tk.LEFT)
        stop_btn = ttk.Button(run_row, text="Stop", command=self.request_stop)
        stop_btn.pack(side=tk.LEFT, padx=4)

        if electrical:
            self.elec_test_var = var
            self.elec_desc = desc
            self.elec_params_fr = params_fr
            self.elec_run_btn = run_btn
            combo.bind("<<ComboboxSelected>>", lambda _e: self._on_test_selected(True))
            run_btn.configure(command=lambda: self.start_test(True))
            self._on_test_selected(True)
        else:
            self.opt_test_var = var
            self.opt_desc = desc
            self.opt_params_fr = params_fr
            self.opt_run_btn = run_btn
            combo.bind("<<ComboboxSelected>>", lambda _e: self._on_test_selected(False))
            run_btn.configure(command=lambda: self.start_test(False))
            self._on_test_selected(False)

    def _on_test_selected(self, electrical: bool) -> None:
        if electrical:
            name = self.elec_test_var.get()
            defs = self.electrical_defs
            desc_w = self.elec_desc
            frame = self.elec_params_fr
            store = self.param_vars
        else:
            name = self.opt_test_var.get()
            defs = self.optical_defs
            desc_w = self.opt_desc
            frame = self.opt_params_fr
            store = self.optical_param_vars

        defn = defs.get(name, {})
        desc_w.delete("1.0", tk.END)
        desc_w.insert(tk.END, defn.get("description", ""))

        for child in frame.winfo_children():
            child.destroy()
        store.clear()

        row = 0
        for key, meta in (defn.get("params") or {}).items():
            label = meta.get("label", key)
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            default = meta.get("default", "")
            typ = meta.get("type", "float")
            if typ == "bool":
                var = tk.BooleanVar(value=bool(default))
                ttk.Checkbutton(frame, variable=var).grid(row=row, column=1, sticky=tk.W)
            elif typ == "choice":
                var = tk.StringVar(value=str(default))
                ttk.Combobox(
                    frame,
                    textvariable=var,
                    values=meta.get("choices", []),
                    width=18,
                    state="readonly",
                ).grid(row=row, column=1, sticky=tk.W)
            else:
                var = tk.StringVar(value=str(default))
                ttk.Entry(frame, textvariable=var, width=22).grid(row=row, column=1, sticky=tk.W)
            store[key] = {"var": var, "type": typ}
            row += 1
        if row == 0:
            ttk.Label(frame, text="(no parameters)").grid(row=0, column=0)

    # ----------------------------------------------------------- connection
    def refresh_usb(self) -> None:
        devices = list_usb_resources(include_sim=True)
        self.usb_combo["values"] = devices
        if not self.usb_var.get() and devices:
            preferred = self.settings.get("last_usb") or devices[0]
            self.usb_var.set(preferred if preferred in devices else devices[0])

    def refresh_com(self) -> None:
        ports = list_com_ports()
        self.com_combo["values"] = ports
        last = self.settings.get("last_com")
        if last:
            self.com_var.set(last)
        elif not self.com_var.get() and ports:
            self.com_var.set(ports[0])

    def connect_smu(self) -> None:
        ok, msg = self.smu.connect(self.usb_var.get(), terminals=self.term_var.get())
        self.log(msg)
        if ok:
            self.smu_status.set("Connected")
            self.smu_conn_btn.configure(state=tk.DISABLED)
            self.smu_disc_btn.configure(state=tk.NORMAL)
            config.save_settings({"last_usb": self.usb_var.get(), "terminals": self.term_var.get()})
        else:
            self.smu_status.set("Error")
            messagebox.showerror("SMU", msg)

    def disconnect_smu(self) -> None:
        self.smu.disconnect()
        self.smu_status.set("Disconnected")
        self.smu_conn_btn.configure(state=tk.NORMAL)
        self.smu_disc_btn.configure(state=tk.DISABLED)
        self.log("SMU disconnected")

    def connect_laser(self) -> None:
        try:
            baud = int(self.baud_var.get())
        except ValueError:
            baud = config.DEFAULT_LASER_BAUD
        ok, msg = self.laser_conn.connect(self.com_var.get(), baud=baud)
        self.log(msg)
        if ok:
            self.laser_status.set("Connected")
            self.laser_conn_btn.configure(state=tk.DISABLED)
            self.laser_disc_btn.configure(state=tk.NORMAL)
            config.save_settings({"last_com": self.com_var.get(), "baud": baud})
        else:
            self.laser_status.set("Error")
            messagebox.showerror("Laser", msg)

    def disconnect_laser(self) -> None:
        self.laser_conn.disconnect()
        self.laser_status.set("Disconnected")
        self.laser_conn_btn.configure(state=tk.NORMAL)
        self.laser_disc_btn.configure(state=tk.DISABLED)
        self.log("Laser disconnected")

    def laser_on(self) -> None:
        ok, msg = self.laser_conn.emission_on()
        self.log(msg)
        if not ok:
            messagebox.showerror("Laser", msg)

    def laser_off(self) -> None:
        ok, msg = self.laser_conn.emission_off()
        self.log(msg)

    def laser_set_power(self) -> None:
        try:
            p = float(self.laser_power_var.get())
        except ValueError:
            messagebox.showerror("Laser", "Invalid power")
            return
        ok, msg = self.laser_conn.set_power_mw(p)
        self.log(msg)

    def laser_pulse(self) -> None:
        try:
            ms = float(self.laser_pulse_ms.get())
        except ValueError:
            messagebox.showerror("Laser", "Invalid pulse ms")
            return

        def work():
            ok, msg = self.laser_conn.pulse_on_ms(ms)
            self.root.after(0, lambda: self.log(msg))

        threading.Thread(target=work, daemon=True).start()

    def laser_train(self) -> None:
        try:
            n = int(self.laser_n.get())
            on_ms = float(self.laser_pulse_ms.get())
            off_ms = float(self.laser_off_ms.get())
            power = float(self.laser_power_var.get())
        except ValueError:
            messagebox.showerror("Laser", "Invalid train parameters")
            return

        def work():
            ok, msg = self.laser_conn.pulse_train(n, on_ms, off_ms, power_mw=power)
            self.root.after(0, lambda: self.log(msg))

        threading.Thread(target=work, daemon=True).start()

    # --------------------------------------------------------------- tests
    def _collect_params(self, store: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key, info in store.items():
            typ = info["type"]
            var = info["var"]
            try:
                if typ == "bool":
                    params[key] = bool(var.get())
                elif typ == "int":
                    params[key] = int(float(str(var.get()).strip()))
                elif typ == "float":
                    params[key] = float(str(var.get()).strip())
                elif typ == "list":
                    params[key] = [float(x.strip()) for x in str(var.get()).split(",") if x.strip()]
                else:
                    params[key] = str(var.get())
            except Exception:
                params[key] = var.get()
        return params

    def start_test(self, electrical: bool) -> None:
        if self._busy:
            messagebox.showinfo("Busy", "A test is already running")
            return
        if not self.smu.connected:
            messagebox.showerror("SMU", "Connect the 2450 (USB, TSP mode) first")
            return

        if electrical:
            name = self.elec_test_var.get()
            defn = self.electrical_defs.get(name, {})
            params = self._collect_params(self.param_vars)
        else:
            if not self.laser_conn.connected:
                messagebox.showerror("Laser", "Connect the Oxxius laser first")
                return
            name = self.opt_test_var.get()
            defn = self.optical_defs.get(name, {})
            params = self._collect_params(self.optical_param_vars)
            # Prefer panel power if optical param missing
            if "optical_laser_power_mw" not in params:
                try:
                    params["optical_laser_power_mw"] = float(self.laser_power_var.get())
                except ValueError:
                    pass

        func_name = defn.get("function")
        if not func_name:
            messagebox.showerror("Test", "No test selected")
            return

        self._busy = True
        self._stop_flag.clear()
        self.elec_run_btn.configure(state=tk.DISABLED)
        self.opt_run_btn.configure(state=tk.DISABLED)
        self.log(f"Start: {name} ({func_name})")

        def work():
            if func_name in OPTICAL_FUNCTIONS:
                results, err = run_optical_test(
                    self.smu.system,
                    self.laser_conn.laser,
                    func_name,
                    params,
                    progress=lambda m: self.root.after(0, lambda msg=m: self.log(msg)),
                    save_run_cb=self._save_optical_run,
                    stop_flag=self._stop_flag,
                )
            else:
                results, err = run_electrical_test(
                    self.smu.system,
                    func_name,
                    params,
                    progress=lambda m: self.root.after(0, lambda msg=m: self.log(msg)),
                )
            self.root.after(0, lambda: self._on_test_done(results, err, func_name, defn.get("plot_type", "time_series"), params))

        threading.Thread(target=work, daemon=True).start()

    def _save_optical_run(self, run_idx: int, pattern: str, result: dict) -> None:
        folder = Path(self.save_dir_var.get()) / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        # For multi-run, save each into data dir with pattern in name
        path = save_results(result, f"optical_run{run_idx}_{pattern}", {"laser_pattern": pattern}, folder=Path(self.save_dir_var.get()))
        self.root.after(0, lambda: self.log(f"  Saved {path.name}"))

    def _on_test_done(self, results, err, func_name, plot_type, params) -> None:
        self._busy = False
        self.elec_run_btn.configure(state=tk.NORMAL)
        self.opt_run_btn.configure(state=tk.NORMAL)
        if err is not None:
            self.log(f"ERROR: {err}")
            messagebox.showerror("Test failed", str(err))
            return
        self.last_results = results
        self.last_func = func_name
        self.last_plot_type = plot_type
        plot_results(self.ax, results, plot_type=plot_type, title=func_name)
        self.canvas.draw_idle()
        try:
            path = save_results(results if isinstance(results, dict) else {"runs": results}, func_name, params, folder=Path(self.save_dir_var.get()))
            self.log(f"Saved {path}")
        except Exception as e:
            self.log(f"Save warning: {e}")
        self.log("Done")

    def request_stop(self) -> None:
        self._stop_flag.set()
        self.log("Stop requested…")
        try:
            if self.laser_conn.connected:
                self.laser_conn.emission_off()
        except Exception:
            pass
        try:
            if self.smu.connected and self.smu.system:
                self.smu.system.source_output_off()
        except Exception:
            pass

    def choose_save_folder(self) -> None:
        path = filedialog.askdirectory(initialdir=self.save_dir_var.get())
        if path:
            self.save_dir_var.set(path)
            config.save_settings({"save_dir": path})

    def _restore_settings(self) -> None:
        if self.settings.get("last_usb"):
            self.usb_var.set(self.settings["last_usb"])
        if self.settings.get("terminals"):
            self.term_var.set(self.settings["terminals"])
        if self.settings.get("last_com"):
            self.com_var.set(self.settings["last_com"])
        if self.settings.get("baud"):
            self.baud_var.set(str(self.settings["baud"]))
        if self.settings.get("save_dir"):
            self.save_dir_var.set(self.settings["save_dir"])

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{stamp}] {message}\n")
        self.log_text.see(tk.END)

    def on_close(self) -> None:
        try:
            self.request_stop()
        except Exception:
            pass
        self.disconnect_laser()
        self.disconnect_smu()
        self.root.destroy()
