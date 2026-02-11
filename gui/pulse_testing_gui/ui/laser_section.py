"""
Laser section – Oxxius laser connection and pulsing controls (collapsible).
Integrated into manual tab for seamless optical testing.
Uses laser power calibration (JSON in Equipment/Laser_Power_Meter) to show true power.
"""

import subprocess
import sys
import tkinter as tk
from pathlib import Path
import threading

from Equipment.Laser_Controller.oxxius import OxxiusLaser


def toggle_laser_section(gui):
    """Toggle collapse/expand of laser section."""
    if gui.laser_collapsed.get():
        gui.laser_inner_frame.pack(fill=tk.X)
        gui.laser_collapse_btn.config(text="▼")
        gui.laser_collapsed.set(False)
    else:
        gui.laser_inner_frame.pack_forget()
        gui.laser_collapse_btn.config(text="▶")
        gui.laser_collapsed.set(True)


def build_laser_section(parent, gui):
    """
    Build collapsible Laser Control section for manual tab.
    Sets gui.laser, gui.laser_* vars. Runs pulse train in a thread.
    """
    frame = tk.LabelFrame(parent, text="Laser Control (Optical)", padx=3, pady=3)
    frame.pack(fill=tk.X, padx=5, pady=(3, 3))
    
    # Initialize laser attributes
    gui.laser = None
    gui._optical_pulse_running = False
    
    # Header with collapse button and status
    header_frame = tk.Frame(frame)
    header_frame.pack(fill=tk.X, pady=(0, 3))
    
    gui.laser_collapsed = tk.BooleanVar(value=True)  # Start collapsed by default
    gui.laser_collapse_btn = tk.Button(header_frame, text="▶", width=3,
                                       command=lambda: toggle_laser_section(gui),
                                       font=("TkDefaultFont", 8), relief=tk.FLAT)
    gui.laser_collapse_btn.pack(side=tk.LEFT, padx=(0, 5))
    
    tk.Label(header_frame, text="Oxxius Laser", font=("TkDefaultFont", 8, "bold")).pack(side=tk.LEFT, anchor="w")
    if not hasattr(gui, "laser_status_var"):
        gui.laser_status_var = tk.StringVar(value="Disconnected")
    if not hasattr(gui, "laser_status_labels"):
        gui.laser_status_labels = []
    status_lbl = tk.Label(header_frame, textvariable=gui.laser_status_var, fg="gray", font=("TkDefaultFont", 8))
    status_lbl.pack(side=tk.RIGHT, padx=(5, 0))
    gui.laser_status_labels.append(status_lbl)
    if not getattr(gui, "_laser_status_trace_added", False):
        gui._laser_status_trace_added = True
        def _update_status_color(*args):
            s = gui.laser_status_var.get()
            for lbl in getattr(gui, "laser_status_labels", []):
                lbl.config(fg="green" if s == "Connected" else "gray")
        gui.laser_status_var.trace_add("write", _update_status_color)
        _update_status_color()
    
    # Inner frame for collapsible content
    gui.laser_inner_frame = tk.Frame(frame)
    
    # --- Laser connection ---
    row1 = tk.Frame(gui.laser_inner_frame)
    row1.pack(fill=tk.X, pady=1)
    tk.Label(row1, text="Port:", width=8, anchor="w").pack(side=tk.LEFT)
    gui.laser_port_var = tk.StringVar(value="COM4")
    tk.Entry(row1, textvariable=gui.laser_port_var, width=12).pack(side=tk.LEFT, padx=2)
    tk.Label(row1, text="Baud:").pack(side=tk.LEFT, padx=(10, 2))
    gui.laser_baud_var = tk.StringVar(value="19200")
    tk.Entry(row1, textvariable=gui.laser_baud_var, width=8).pack(side=tk.LEFT, padx=2)

    btn_row = tk.Frame(gui.laser_inner_frame)
    btn_row.pack(fill=tk.X, pady=2)
    gui.laser_conn_btn = tk.Button(btn_row, text="Connect", command=lambda: _connect_laser(gui), bg="green", fg="white", font=("TkDefaultFont", 8))
    gui.laser_conn_btn.pack(side=tk.LEFT, padx=2)
    gui.laser_disc_btn = tk.Button(btn_row, text="Disconnect", command=lambda: _disconnect_laser(gui), state=tk.DISABLED, font=("TkDefaultFont", 8))
    gui.laser_disc_btn.pack(side=tk.LEFT, padx=2)

    # --- Emission On/Off (shared with Optical tab) ---
    if not hasattr(gui, "laser_emission_on_var"):
        gui.laser_emission_on_var = tk.BooleanVar(value=False)
    if not hasattr(gui, "laser_emission_off_buttons"):
        gui.laser_emission_off_buttons = []
    if not hasattr(gui, "laser_emission_on_buttons"):
        gui.laser_emission_on_buttons = []
    emission_row = tk.Frame(gui.laser_inner_frame)
    emission_row.pack(fill=tk.X, pady=(2, 0))
    tk.Label(emission_row, text="Emission:", width=8, anchor="w", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
    off_btn = tk.Button(emission_row, text="Off", command=lambda: _laser_emission_off(gui), width=3, state=tk.DISABLED, font=("TkDefaultFont", 8))
    off_btn.pack(side=tk.LEFT, padx=2)
    on_btn = tk.Button(emission_row, text="On", command=lambda: _laser_emission_on(gui), width=3, state=tk.DISABLED, font=("TkDefaultFont", 8))
    on_btn.pack(side=tk.LEFT, padx=2)
    gui.laser_emission_off_buttons.append(off_btn)
    gui.laser_emission_on_buttons.append(on_btn)
    from gui.pulse_testing_gui.ui import tabs_optical
    tabs_optical._update_emission_buttons(gui)

    # --- Power: Manual vs Set (mW) (shared vars with Optical tab) ---
    if not hasattr(gui, "laser_power_use_software_var"):
        gui.laser_power_use_software_var = tk.BooleanVar(value=False)
    if not hasattr(gui, "laser_power_var"):
        gui.laser_power_var = tk.StringVar(value="1")
    if not hasattr(gui, "laser_power_entries"):
        gui.laser_power_entries = []
    power_row = tk.Frame(gui.laser_inner_frame)
    power_row.pack(fill=tk.X, pady=(2, 1))
    tk.Label(power_row, text="Power:", width=8, anchor="w").pack(side=tk.LEFT)
    tk.Radiobutton(power_row, text="Manual", variable=gui.laser_power_use_software_var,
                   value=False, command=lambda: _laser_power_mode_changed(gui), font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 4))
    tk.Radiobutton(power_row, text="Set (mW):", variable=gui.laser_power_use_software_var,
                   value=True, command=lambda: _laser_power_mode_changed(gui), font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
    laser_power_entry = tk.Entry(power_row, textvariable=gui.laser_power_var, width=4, font=("TkDefaultFont", 8))
    laser_power_entry.pack(side=tk.LEFT, padx=2)
    gui.laser_power_entries.append(laser_power_entry)
    gui.laser_true_power_var = tk.StringVar(value="")
    tk.Label(power_row, text="True:", font=("TkDefaultFont", 8), fg="gray").pack(side=tk.LEFT, padx=(6, 2))
    tk.Label(power_row, textvariable=gui.laser_true_power_var, font=("TkDefaultFont", 8), fg="gray", width=24, anchor="w").pack(side=tk.LEFT)
    _laser_power_mode_changed(gui)
    _update_laser_true_power(gui)
    if not getattr(gui, "_laser_true_power_trace_added", False):
        gui._laser_true_power_trace_added = True
        gui.laser_power_var.trace_add("write", lambda *a: _update_laser_true_power(gui))

    # Calibration curve button + note
    cal_row = tk.Frame(gui.laser_inner_frame)
    cal_row.pack(fill=tk.X, pady=(0, 2))
    tk.Button(cal_row, text="Calibration curve", command=lambda: _show_calibration_curve(gui), font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 8))
    note_text = (
        "Below 10 mW the laser\u2019s front-panel display does not match actual output; "
        "the \u2018True\u2019 value here is from calibration. Use it for reporting."
    )
    tk.Label(cal_row, text=note_text, font=("TkDefaultFont", 7), fg="gray", wraplength=400, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)

    # (Pulse parameters UI removed – pulsing now controlled by optical tests only)


def _laser_emission_off(gui):
    if gui.laser is None:
        return
    try:
        gui.laser.emission_off()
        gui.laser_emission_on_var.set(False)
        from gui.pulse_testing_gui.ui import tabs_optical
        tabs_optical._update_emission_buttons(gui)
        gui.log("Laser: Emission off.")
    except Exception as e:
        gui.log(f"Laser: Emission off failed: {e}")


def _laser_emission_on(gui):
    if gui.laser is None:
        return
    try:
        gui.laser.emission_on()
        gui.laser_emission_on_var.set(True)
        from gui.pulse_testing_gui.ui import tabs_optical
        tabs_optical._update_emission_buttons(gui)
        gui.log("Laser: Emission on.")
    except Exception as e:
        gui.log(f"Laser: Emission on failed: {e}")


def _laser_power_mode_changed(gui):
    """Enable/disable power entries and apply mode if laser connected."""
    use_software = getattr(gui, "laser_power_use_software_var", None)
    entries = getattr(gui, "laser_power_entries", [])
    if use_software is not None:
        for entry in entries:
            if use_software.get():
                entry.config(state=tk.NORMAL)
            else:
                entry.config(state=tk.DISABLED)
    if gui.laser is not None and use_software is not None and use_software.get():
        try:
            power_mw = float(gui.laser_power_var.get().strip())
            gui.laser.set_to_digital_power_control(power_mw)
            gui.laser_emission_on_var.set(False)
            from gui.pulse_testing_gui.ui import tabs_optical
            tabs_optical._update_emission_buttons(gui)
            gui.log(f"Laser: Power set to {power_mw} mW (emission off until you turn On).")
        except (ValueError, Exception):
            pass
    elif gui.laser is not None and use_software is not None and not use_software.get():
        try:
            gui.laser.set_to_analog_modulation_mode(power_mw=100)
            gui.log("Laser: Manual (front panel) control.")
        except Exception:
            pass


def _update_laser_true_power(gui):
    """Update the true power label from calibration (mW and µW)."""
    var = getattr(gui, "laser_true_power_var", None)
    if var is None:
        return
    try:
        from Equipment.Laser_Power_Meter.laser_power_calibration import (
            load_calibration,
            get_actual_mw,
            format_true_power_display,
        )
        set_mw = float(gui.laser_power_var.get().strip())
        cal = load_calibration()
        true_mw = get_actual_mw(cal, set_mw)
        var.set(format_true_power_display(true_mw))
    except (FileNotFoundError, ValueError, Exception):
        var.set("—")


def _show_calibration_curve(gui):
    """Open calibration curve plot in a separate process."""
    try:
        from Equipment.Laser_Power_Meter import plot_laser_calibration
        script = Path(plot_laser_calibration.__file__).resolve()
        repo_root = script.parent.parent.parent
        subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(repo_root),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
    except Exception as e:
        if hasattr(gui, "log"):
            gui.log(f"Could not open calibration curve: {e}")
        try:
            from tkinter import messagebox
            messagebox.showerror("Calibration curve", f"Could not open plot.\n{e}")
        except Exception:
            pass


def _connect_laser(gui):
    # Reuse laser from Measurement GUI if already connected there (avoids "port in use")
    provider = getattr(gui, "provider", None)
    if provider is not None and hasattr(provider, "get_shared_laser"):
        shared = provider.get_shared_laser()
        if shared is not None:
            gui.laser = shared
            gui._laser_from_provider = True
            try:
                idn = gui.laser.idn()
            except Exception:
                idn = "?"
            if getattr(gui, "laser_power_use_software_var", None) and gui.laser_power_use_software_var.get():
                try:
                    power_mw = float(gui.laser_power_var.get().strip())
                    gui.laser.set_to_digital_power_control(power_mw)
                    gui.log(f"Laser: Using shared connection ({idn}), power {power_mw} mW.")
                except ValueError:
                    gui.log(f"Laser: Using shared connection ({idn}). Set power (mW) and use 'Set (mW)' to apply.")
            else:
                gui.log(f"Laser: Using shared connection ({idn}), manual power.")
            gui.laser_status_var.set("Connected")
            gui.laser_emission_on_var.set(False)
            from gui.pulse_testing_gui.ui import tabs_optical
            tabs_optical._update_emission_buttons(gui)
            gui.laser_conn_btn.config(state=tk.DISABLED)
            gui.laser_disc_btn.config(state=tk.NORMAL)
            return

    port = gui.laser_port_var.get().strip()
    try:
        baud = int(gui.laser_baud_var.get().strip())
    except ValueError:
        gui.log("Laser: Invalid baud rate.")
        return
    gui._laser_from_provider = False
    try:
        gui.laser = OxxiusLaser(port=port, baud=baud)
        idn = gui.laser.idn()
        if getattr(gui, "laser_power_use_software_var", None) and gui.laser_power_use_software_var.get():
            try:
                power_mw = float(gui.laser_power_var.get().strip())
                gui.laser.set_to_digital_power_control(power_mw)
                gui.log(f"Laser: Connected ({idn}), power {power_mw} mW.")
            except ValueError:
                gui.log(f"Laser: Connected ({idn}). Set power (mW) and use 'Set (mW)' to apply.")
        else:
            gui.log(f"Laser: Connected ({idn}), manual power.")
        gui.laser_status_var.set("Connected")
        gui.laser_emission_on_var.set(False)
        from gui.pulse_testing_gui.ui import tabs_optical
        tabs_optical._update_emission_buttons(gui)
        gui.laser_conn_btn.config(state=tk.DISABLED)
        gui.laser_disc_btn.config(state=tk.NORMAL)
    except Exception as e:
        gui.log(f"Laser: Connect failed: {e}")
        gui.laser = None


def _disconnect_laser(gui):
    if gui.laser is None:
        return
    # If laser was shared from Measurement GUI, release reference but do not close the port
    if getattr(gui, "_laser_from_provider", False):
        gui.laser = None
        gui.laser_status_var.set("Disconnected")
        gui.laser_emission_on_var.set(False)
        from gui.pulse_testing_gui.ui import tabs_optical
        tabs_optical._update_emission_buttons(gui)
        gui.laser_conn_btn.config(state=tk.NORMAL)
        gui.laser_disc_btn.config(state=tk.DISABLED)
        gui.log("Laser: Released shared connection (still connected in Measurement GUI).")
        return
    try:
        gui.laser.close(restore_to_manual_control=True)
    except Exception:
        pass
    gui.laser = None
    gui.laser_status_var.set("Disconnected")
    gui.laser_emission_on_var.set(False)
    from gui.pulse_testing_gui.ui import tabs_optical
    tabs_optical._update_emission_buttons(gui)
    gui.laser_conn_btn.config(state=tk.NORMAL)
    gui.laser_disc_btn.config(state=tk.DISABLED)
    gui.log("Laser: Disconnected.")
