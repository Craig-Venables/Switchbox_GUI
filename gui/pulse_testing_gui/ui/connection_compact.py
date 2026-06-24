"""
Compact connection bar — always visible, friendly system labels, settings popover.
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from gui.pulse_testing_gui import config
from gui.pulse_testing_gui.ui.connection import (
    ensure_terminals_var,
    update_terminals_visibility,
)
from gui.pulse_testing_gui.ui.instrument_current_range import (
    register_current_range_row,
    update_instrument_current_range_ui,
)
from Pulse_Testing.system_wrapper import detect_system_from_address, get_default_address_for_system

SYSTEM_PROFILES: list[tuple[str, str]] = [
    ("4200 PMU (fast)", "keithley4200_pmu"),
    ("4200 SMU (slow)", "keithley4200_smu"),
    ("2450 TSP", "keithley2450"),
    ("2450 Sim", "keithley2450_sim"),
    ("2400 SCPI", "keithley2400"),
    ("4200A (legacy)", "keithley4200a"),
    ("4200 Custom", "keithley4200_custom"),
]

_DISPLAY_BY_INTERNAL = {internal: label for label, internal in SYSTEM_PROFILES}
_INTERNAL_BY_DISPLAY = {label: internal for label, internal in SYSTEM_PROFILES}


def _label_for_system(internal: str) -> str:
    return _DISPLAY_BY_INTERNAL.get(internal, internal)


def _update_pmu_hint(gui) -> None:
    if not hasattr(gui, "compact_pmu_hint_label"):
        return
    name = gui.system_var.get() if hasattr(gui, "system_var") else ""
    if name in KEITHLEY4200_PMU_TIMING_SYSTEMS:
        gui.compact_pmu_hint_label.config(
            text=(
                "PMU: CH1 force → DUT+, CH2 measure → DUT−. "
                "Endurance & Retention use 2-ch interleaved wiring."
            ),
            fg="#004080",
        )
    else:
        gui.compact_pmu_hint_label.config(text="", fg="gray")


def _update_addr_display(gui) -> None:
    if hasattr(gui, "compact_addr_label") and hasattr(gui, "addr_var"):
        gui.compact_addr_label.config(text=f"Address: {gui.addr_var.get()}")


def _on_system_display_changed(gui) -> None:
    display = gui.system_display_var.get()
    internal = _INTERNAL_BY_DISPLAY.get(display)
    if internal and internal != gui.system_var.get():
        gui.system_var.set(internal)
    gui._on_system_changed()
    _update_addr_display(gui)


def _sync_display_from_internal(gui) -> None:
    internal = gui.system_var.get()
    gui.system_display_var.set(_label_for_system(internal))


def _apply_compact_context(gui) -> None:
    """Apply sample/device/save fields from compact settings vars."""
    if hasattr(gui, "compact_sample_var"):
        name = gui.compact_sample_var.get().strip()
        if name:
            gui.sample_name = name
    if hasattr(gui, "compact_device_var"):
        device = gui.compact_device_var.get().strip()
        if device:
            gui.device_label = device
    if hasattr(gui, "compact_save_path_var"):
        path_str = gui.compact_save_path_var.get().strip()
        if path_str:
            gui.custom_base_path = Path(path_str)
            gui._custom_base_from_provider = False
        else:
            gui._refresh_save_base_for_sample()
            gui.compact_save_path_var.set(str(gui.custom_base_path))

    if hasattr(gui, "context_var"):
        gui.context_var.set(f"Sample: {gui.sample_name}  |  Device: {gui.device_label}")
    if hasattr(gui, "compact_save_hint_var") and gui.custom_base_path:
        gui.compact_save_hint_var.set(str(gui.custom_base_path))

    _save_compact_context_config(gui)
    gui.log(f"Context: sample={gui.sample_name}, device={gui.device_label}")
    if gui.custom_base_path:
        gui.log(f"Save folder: {gui.custom_base_path}")


def _save_compact_context_config(gui) -> None:
    """Persist sample/device/save path for standalone compact launches."""
    try:
        data = {}
        cfg = config.TSP_GUI_CONFIG_FILE
        if cfg.is_file():
            with open(cfg, encoding="utf-8") as f:
                data = json.load(f)
        data["compact_sample_name"] = gui.sample_name
        data["compact_device_label"] = gui.device_label
        if gui.custom_base_path:
            data["compact_save_path"] = str(gui.custom_base_path)
        cfg.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        if gui.custom_base_path:
            save_cfg = config.SAVE_LOCATION_CONFIG_FILE
            save_data = {}
            if save_cfg.is_file():
                with open(save_cfg, encoding="utf-8") as f:
                    save_data = json.load(f)
            save_data["use_custom_save"] = True
            save_data["custom_save_path"] = str(gui.custom_base_path)
            save_cfg.parent.mkdir(parents=True, exist_ok=True)
            with open(save_cfg, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)
    except (OSError, json.JSONDecodeError, TypeError) as e:
        gui.log(f"Could not save context: {e}")


def _load_compact_context_defaults(gui) -> None:
    """Load last sample/device/save from config when not launched from Measurement GUI."""
    if gui.provider is not None:
        return
    try:
        if config.TSP_GUI_CONFIG_FILE.is_file():
            with open(config.TSP_GUI_CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            sn = data.get("compact_sample_name", "").strip()
            dl = data.get("compact_device_label", "").strip()
            sp = data.get("compact_save_path", "").strip()
            if sn and gui.sample_name == "UnknownSample":
                gui.sample_name = sn
            if dl and gui.device_label == "UnknownDevice":
                gui.device_label = dl
            if sp and not gui._custom_base_from_provider:
                gui.custom_base_path = Path(sp)
            elif gui.provider is None and not gui._custom_base_from_provider:
                gui._refresh_save_base_for_sample()
    except (OSError, json.JSONDecodeError, TypeError):
        pass


def _browse_compact_save(gui) -> None:
    folder = filedialog.askdirectory(title="Choose save folder", mustexist=False)
    if folder and hasattr(gui, "compact_save_path_var"):
        gui.compact_save_path_var.set(folder)


def _open_settings_popover(gui, anchor_widget) -> None:
    if getattr(gui, "_connection_settings_win", None):
        try:
            if gui._connection_settings_win.winfo_exists():
                gui._connection_settings_win.lift()
                return
        except tk.TclError:
            pass

    win = tk.Toplevel(gui)
    win.title("Settings")
    win.transient(gui)
    win.resizable(False, False)
    gui._connection_settings_win = win

    body = tk.Frame(win, padx=12, pady=10)
    body.pack(fill=tk.BOTH, expand=True)

    tk.Label(body, text="Sample & save (standalone)", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 6))

    if not hasattr(gui, "compact_sample_var"):
        gui.compact_sample_var = tk.StringVar(value=gui.sample_name)
    else:
        gui.compact_sample_var.set(gui.sample_name)
    if not hasattr(gui, "compact_device_var"):
        gui.compact_device_var = tk.StringVar(value=gui.device_label)
    else:
        gui.compact_device_var.set(gui.device_label)
    if not hasattr(gui, "compact_save_path_var"):
        path = str(gui.custom_base_path) if gui.custom_base_path else str(
            config.resolve_pulse_testing_save_base(gui.sample_name)
        )
        gui.compact_save_path_var = tk.StringVar(value=path)
    else:
        gui.compact_save_path_var.set(
            str(gui.custom_base_path) if gui.custom_base_path else str(
                config.resolve_pulse_testing_save_base(gui.sample_name)
            )
        )

    row = tk.Frame(body)
    row.pack(fill=tk.X, pady=3)
    tk.Label(row, text="Sample name:", width=14, anchor="w").pack(side=tk.LEFT)
    tk.Entry(row, textvariable=gui.compact_sample_var, width=32).pack(side=tk.LEFT, padx=4)

    row2 = tk.Frame(body)
    row2.pack(fill=tk.X, pady=3)
    tk.Label(row2, text="Device:", width=14, anchor="w").pack(side=tk.LEFT)
    tk.Entry(row2, textvariable=gui.compact_device_var, width=32).pack(side=tk.LEFT, padx=4)

    row3 = tk.Frame(body)
    row3.pack(fill=tk.X, pady=3)
    tk.Label(row3, text="Save folder:", width=14, anchor="w").pack(side=tk.LEFT)
    tk.Entry(row3, textvariable=gui.compact_save_path_var, width=26).pack(side=tk.LEFT, padx=4)
    tk.Button(row3, text="📁", command=lambda: _browse_compact_save(gui), width=2).pack(side=tk.LEFT)

    tk.Label(body, text="Instrument", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(10, 6))

    cr_row = tk.Frame(body)
    cr_row.pack(fill=tk.X, pady=3)
    cr_label = tk.Label(cr_row, text="Current range (A):", width=14, anchor="w")
    cr_label.pack(side=tk.LEFT)
    cr_hint = tk.Label(cr_row, text="", font=("TkDefaultFont", 8), fg="gray")
    cr_hint.pack(side=tk.LEFT)
    if not hasattr(gui, "instrument_current_range_var") or gui.instrument_current_range_var is None:
        gui.instrument_current_range_var = tk.DoubleVar(value=1e-4)
        gui.smu_current_range_var = gui.instrument_current_range_var
    tk.Entry(cr_row, textvariable=gui.instrument_current_range_var, width=14).pack(side=tk.LEFT, padx=4)
    register_current_range_row(gui, cr_row, cr_label, cr_hint)
    update_instrument_current_range_ui(gui)

    save_row = tk.Frame(body)
    save_row.pack(fill=tk.X, pady=3)
    tk.Checkbutton(
        save_row,
        text="Simple save path:",
        variable=gui.use_simple_save_var,
        command=gui._on_simple_save_toggle,
    ).pack(side=tk.LEFT)
    gui.simple_save_entry = tk.Entry(save_row, textvariable=gui.simple_save_path_var, width=22, state="disabled")
    gui.simple_save_entry.pack(side=tk.LEFT, padx=4)
    browse_btn = tk.Button(save_row, text="📁", command=gui._browse_simple_save, state="disabled", width=2)
    browse_btn.pack(side=tk.LEFT)
    gui._compact_simple_save_browse_btn = browse_btn

    btn_row = tk.Frame(body)
    btn_row.pack(fill=tk.X, pady=(10, 0))
    tk.Button(btn_row, text="Apply", command=lambda: (_apply_compact_context(gui), win.destroy()), bg="#2e7d32", fg="white").pack(
        side=tk.RIGHT, padx=(4, 0)
    )
    tk.Button(btn_row, text="Cancel", command=win.destroy).pack(side=tk.RIGHT)

    win.update_idletasks()
    x = anchor_widget.winfo_rootx()
    y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
    win.geometry(f"+{x}+{y}")


def build_connection_bar(parent, gui) -> None:
    """Always-visible connection toolbar for compact layout."""
    _load_compact_context_defaults(gui)

    outer = tk.Frame(parent, bg="#eef4fb", relief=tk.GROOVE, bd=1)
    outer.pack(fill=tk.X, padx=5, pady=(5, 3))
    gui.connection_bar_frame = outer

    detected_system = detect_system_from_address(gui.device_address)
    gui.system_var = tk.StringVar()
    default_internal = detected_system if detected_system else "keithley4200_pmu"
    gui.system_var.set(default_internal)
    gui.system_display_var = tk.StringVar(value=_label_for_system(default_internal))

    gui.addr_var = tk.StringVar()
    default_addr = get_default_address_for_system(default_internal) or gui.device_address
    gui.addr_var.set(default_addr)

    # Row 1: system, terminals, status, settings
    row1 = tk.Frame(outer, bg="#eef4fb")
    row1.pack(fill=tk.X, padx=6, pady=(4, 2))

    tk.Label(row1, text="System:", bg="#eef4fb", font=("TkDefaultFont", 8, "bold")).pack(side=tk.LEFT)
    system_combo = ttk.Combobox(
        row1,
        textvariable=gui.system_display_var,
        values=[label for label, _ in SYSTEM_PROFILES],
        state="readonly",
        width=18,
    )
    system_combo.pack(side=tk.LEFT, padx=(4, 10))
    system_combo.bind("<<ComboboxSelected>>", lambda e: _on_system_display_changed(gui))

    term_frame = tk.Frame(row1, bg="#eef4fb")
    gui.terminals_frame = term_frame
    tk.Label(term_frame, text="Term:", bg="#eef4fb", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
    ensure_terminals_var(gui)
    tk.Radiobutton(
        term_frame, text="Front", variable=gui.terminals_var, value="front",
        command=gui.save_terminal_default, bg="#eef4fb", font=("TkDefaultFont", 8),
    ).pack(side=tk.LEFT)
    tk.Radiobutton(
        term_frame, text="Rear", variable=gui.terminals_var, value="rear",
        command=gui.save_terminal_default, bg="#eef4fb", font=("TkDefaultFont", 8),
    ).pack(side=tk.LEFT)
    gui._terminals_show = lambda: term_frame.pack(side=tk.LEFT, padx=(0, 8))
    gui._terminals_hide = lambda: term_frame.pack_forget()

    gui.conn_status_var = tk.StringVar(value="Disconnected")
    gui.conn_status_label = tk.Label(
        row1, textvariable=gui.conn_status_var, fg="red", bg="#eef4fb", font=("TkDefaultFont", 8, "bold")
    )
    gui.conn_status_label.pack(side=tk.LEFT, padx=(4, 8))

    settings_btn = tk.Button(row1, text="⚙ Settings", command=lambda: _open_settings_popover(gui, settings_btn), font=("TkDefaultFont", 8))
    settings_btn.pack(side=tk.RIGHT)

    # Row 2: connect / disconnect + auto address (no GPIB picker)
    row2 = tk.Frame(outer, bg="#eef4fb")
    row2.pack(fill=tk.X, padx=6, pady=(0, 4))

    tk.Button(
        row2, text="Connect", command=gui.connect_device, bg="green", fg="white", font=("TkDefaultFont", 9), padx=12,
    ).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(
        row2, text="Disconnect", command=gui.disconnect_device, font=("TkDefaultFont", 9), padx=8,
    ).pack(side=tk.LEFT, padx=(0, 12))

    gui.compact_addr_label = tk.Label(
        row2, text=f"Address: {default_addr}", bg="#eef4fb", font=("TkDefaultFont", 8), fg="#444",
    )
    gui.compact_addr_label.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="w")

    row3 = tk.Frame(outer, bg="#eef4fb")
    row3.pack(fill=tk.X, padx=6, pady=(0, 2))
    gui.compact_pmu_hint_label = tk.Label(
        row3, text="", font=("TkDefaultFont", 8), wraplength=480, justify=tk.LEFT, bg="#eef4fb"
    )
    gui.compact_pmu_hint_label.pack(anchor="w")

    gui.context_var = tk.StringVar(value=f"Sample: {gui.sample_name}  |  Device: {gui.device_label}")
    tk.Label(
        row3,
        textvariable=gui.context_var,
        font=("TkDefaultFont", 7),
        fg="#555",
        bg="#eef4fb",
    ).pack(anchor="w")
    if gui.provider is None and gui.custom_base_path:
        gui.compact_save_hint_var = tk.StringVar(value=str(gui.custom_base_path))
        tk.Label(
            row3,
            textvariable=gui.compact_save_hint_var,
            font=("TkDefaultFont", 7),
            fg="#777",
            bg="#eef4fb",
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor="w")

    def _on_internal_system_changed(*_args):
        _sync_display_from_internal(gui)
        _update_pmu_hint(gui)
        _update_addr_display(gui)
        update_terminals_visibility(gui)

    gui.system_var.trace_add("write", _on_internal_system_changed)
    _update_pmu_hint(gui)
    update_terminals_visibility(gui)
