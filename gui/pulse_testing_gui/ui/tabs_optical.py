"""
Optical tab – Oxxius laser connection and ms-scale light pulsing.
Used from Pulse Testing GUI under the "Optical" tab (formerly FG Measurements).
Uses laser power calibration (JSON in Equipment/Laser_Power_Meter) to show true power.
"""

import subprocess
import sys
import tkinter as tk
from pathlib import Path
import threading
from tkinter import messagebox
from tkinter import simpledialog

from Equipment.Laser_Controller.oxxius import OxxiusLaser


def build_optical_tab(tab_frame, gui):
    """
    Build the Optical tab: laser connection (COM, baud), pulse params, single pulse / pulse train.
    Sets gui.laser, gui.laser_* vars. Runs pulse train in a thread so GUI stays responsive.
    """
    tab = tab_frame
    gui.laser = None
    gui._optical_pulse_running = False

    # --- Laser connection ---
    conn_frame = tk.LabelFrame(tab, text="Oxxius laser", padx=5, pady=5)
    conn_frame.pack(fill=tk.X, padx=5, pady=5)

    row1 = tk.Frame(conn_frame)
    row1.pack(fill=tk.X, pady=2)
    tk.Label(row1, text="Port:", width=8, anchor="w").pack(side=tk.LEFT)
    gui.laser_port_var = tk.StringVar(value="COM4")
    tk.Entry(row1, textvariable=gui.laser_port_var, width=12).pack(side=tk.LEFT, padx=2)
    tk.Label(row1, text="Baud:").pack(side=tk.LEFT, padx=(10, 2))
    gui.laser_baud_var = tk.StringVar(value="19200")
    tk.Entry(row1, textvariable=gui.laser_baud_var, width=8).pack(side=tk.LEFT, padx=2)

    btn_row = tk.Frame(conn_frame)
    btn_row.pack(fill=tk.X, pady=5)
    gui.laser_conn_btn = tk.Button(btn_row, text="Connect", command=lambda: _connect_laser(gui), bg="green", fg="white")
    gui.laser_conn_btn.pack(side=tk.LEFT, padx=2)
    gui.laser_disc_btn = tk.Button(btn_row, text="Disconnect", command=lambda: _disconnect_laser(gui), state=tk.DISABLED)
    gui.laser_disc_btn.pack(side=tk.LEFT, padx=2)
    if not hasattr(gui, "laser_status_var"):
        gui.laser_status_var = tk.StringVar(value="Disconnected")
    if not hasattr(gui, "laser_status_labels"):
        gui.laser_status_labels = []
    status_lbl = tk.Label(btn_row, textvariable=gui.laser_status_var, fg="gray", font=("TkDefaultFont", 9))
    status_lbl.pack(side=tk.LEFT, padx=10)
    gui.laser_status_labels.append(status_lbl)
    if not getattr(gui, "_laser_status_trace_added", False):
        gui._laser_status_trace_added = True
        def _update_status_color(*args):
            s = gui.laser_status_var.get()
            for lbl in getattr(gui, "laser_status_labels", []):
                lbl.config(fg="green" if s == "Connected" else "gray")
        gui.laser_status_var.trace_add("write", _update_status_color)
        _update_status_color()

    # --- Emission On/Off (shared with laser_section) ---
    if not hasattr(gui, "laser_emission_on_var"):
        gui.laser_emission_on_var = tk.BooleanVar(value=False)
    if not hasattr(gui, "laser_emission_off_buttons"):
        gui.laser_emission_off_buttons = []
    if not hasattr(gui, "laser_emission_on_buttons"):
        gui.laser_emission_on_buttons = []
    emission_row = tk.Frame(conn_frame)
    emission_row.pack(fill=tk.X, pady=(2, 0))
    tk.Label(emission_row, text="Emission:", width=8, anchor="w").pack(side=tk.LEFT)
    off_btn = tk.Button(emission_row, text="Off", command=lambda: _laser_emission_off(gui), width=4, state=tk.DISABLED)
    off_btn.pack(side=tk.LEFT, padx=2)
    on_btn = tk.Button(emission_row, text="On", command=lambda: _laser_emission_on(gui), width=4, state=tk.DISABLED)
    on_btn.pack(side=tk.LEFT, padx=2)
    gui.laser_emission_off_buttons.append(off_btn)
    gui.laser_emission_on_buttons.append(on_btn)
    _update_emission_buttons(gui)

    # --- Power: Manual vs Set (mW) (shared vars with laser_section) ---
    if not hasattr(gui, "laser_power_use_software_var"):
        gui.laser_power_use_software_var = tk.BooleanVar(value=False)
    if not hasattr(gui, "laser_power_var"):
        gui.laser_power_var = tk.StringVar(value="1")
    if not hasattr(gui, "laser_power_entries"):
        gui.laser_power_entries = []
    power_row = tk.Frame(conn_frame)
    power_row.pack(fill=tk.X, pady=(5, 2))
    tk.Label(power_row, text="Power:", width=8, anchor="w").pack(side=tk.LEFT)
    tk.Radiobutton(power_row, text="Manual (front panel)", variable=gui.laser_power_use_software_var,
                   value=False, command=lambda: _laser_power_mode_changed(gui)).pack(side=tk.LEFT, padx=(0, 8))
    tk.Radiobutton(power_row, text="Set (mW):", variable=gui.laser_power_use_software_var,
                   value=True, command=lambda: _laser_power_mode_changed(gui)).pack(side=tk.LEFT, padx=(0, 2))
    gui.laser_power_entry = tk.Entry(power_row, textvariable=gui.laser_power_var, width=6)
    gui.laser_power_entry.pack(side=tk.LEFT, padx=2)
    gui.laser_power_entries.append(gui.laser_power_entry)
    if not hasattr(gui, "laser_true_power_var"):
        gui.laser_true_power_var = tk.StringVar(value="")
    tk.Label(power_row, text="True:", fg="gray").pack(side=tk.LEFT, padx=(8, 2))
    tk.Label(power_row, textvariable=gui.laser_true_power_var, fg="gray", width=24, anchor="w").pack(side=tk.LEFT)
    if not getattr(gui, "_laser_true_power_trace_added_optical", False):
        gui._laser_true_power_trace_added_optical = True
        gui.laser_power_var.trace_add("write", lambda *a: _update_laser_true_power(gui))
    _update_laser_true_power(gui)
    if not getattr(gui, "_laser_power_trace_added", False):
        gui._laser_power_trace_added = True
        def _on_power_changed(*args):
            # Auto-apply new power when in Set (mW) mode
            if gui.laser is None:
                return
            use_software = getattr(gui, "laser_power_use_software_var", None)
            if not (use_software and use_software.get()):
                return
            try:
                power_mw = float(gui.laser_power_var.get().strip())
            except ValueError:
                return
            try:
                gui.laser.set_to_digital_power_control(power_mw)
                gui.log(f"Optical: Laser power updated to {power_mw} mW.")
            except Exception:
                pass
        gui.laser_power_var.trace_add("write", _on_power_changed)
    _laser_power_mode_changed(gui)

    # Calibration curve button + note
    cal_row = tk.Frame(conn_frame)
    cal_row.pack(fill=tk.X, pady=(0, 5))
    tk.Button(cal_row, text="Calibration curve", command=lambda: _show_calibration_curve(gui)).pack(side=tk.LEFT, padx=(0, 8))
    note_text = (
        "Below 10 mW the laser\u2019s front-panel display does not match actual output; "
        "the \u2018True\u2019 value here is from calibration. Use it for reporting."
    )
    tk.Label(cal_row, text=note_text, font=("TkDefaultFont", 8), fg="gray", wraplength=450, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Laser sync calibration: suggest sync offset from last optical run
    sync_row = tk.Frame(conn_frame)
    sync_row.pack(fill=tk.X, pady=(2, 5))
    tk.Button(sync_row, text="Suggest sync offset from last run", command=lambda: _suggest_laser_sync_offset(gui), font=("TkDefaultFont", 9)).pack(side=tk.LEFT, padx=(0, 8))
    tk.Label(sync_row, text="Run an optical test with delay=0, then click to get suggested \"Laser sync offset (s)\".", font=("TkDefaultFont", 8), fg="gray", wraplength=400, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)

    # (Pulse parameters UI removed – pulsing now controlled by optical tests only)


def _suggest_laser_sync_offset(gui):
    """Use last optical run to suggest Laser sync offset (s) so pulses appear at desired time."""
    results = getattr(gui, "last_results", None)
    if not results:
        messagebox.showinfo("Suggest sync offset", "No results from a previous run. Run an optical test first (e.g. with Laser Start Delay = 0).")
        return
    timestamps = results.get("timestamps")
    resistances = results.get("resistances")
    if not timestamps or not resistances or len(timestamps) != len(resistances):
        messagebox.showinfo("Suggest sync offset", "Last run has no timestamps/resistances. Run an optical test first.")
        return
    desired_s = simpledialog.askfloat("Desired first pulse time (s)", "At what time (s) should the first pulse appear on the plot?", initialvalue=1.0, minvalue=0.0, maxvalue=3600.0)
    if desired_s is None:
        return
    try:
        from gui.pulse_testing_gui.optical_runner import suggest_laser_sync_offset_s
        suggested = suggest_laser_sync_offset_s(timestamps, resistances, desired_s)
    except Exception as e:
        messagebox.showerror("Suggest sync offset", f"Error: {e}")
        return
    if suggested is None:
        messagebox.showinfo("Suggest sync offset", "Could not detect a resistance drop in the last run. Ensure the run was optical and the photodiode responded.")
        return
    messagebox.showinfo(
        "Suggest sync offset",
        f"Suggested \"Laser sync offset (s)\" = {suggested:.3f}\n\n"
        f"Set this in Test Parameters (Laser sync offset) and run again to align the first pulse with {desired_s} s on the plot."
    )


def _update_emission_buttons(gui):
    """Update emission On/Off button states and appearance from laser_emission_on_var and connection."""
    connected = gui.laser is not None
    on_var = getattr(gui, "laser_emission_on_var", None)
    off_btns = getattr(gui, "laser_emission_off_buttons", [])
    on_btns = getattr(gui, "laser_emission_on_buttons", [])
    if on_var is None:
        return
    for off_btn, on_btn in zip(off_btns, on_btns):
        if not connected:
            off_btn.config(state=tk.DISABLED)
            on_btn.config(state=tk.DISABLED)
        else:
            off_btn.config(state=tk.NORMAL)
            on_btn.config(state=tk.NORMAL)
            if on_var.get():
                off_btn.config(relief=tk.RAISED)
                on_btn.config(relief=tk.SUNKEN)
            else:
                off_btn.config(relief=tk.SUNKEN)
                on_btn.config(relief=tk.RAISED)


def _laser_emission_off(gui):
    if gui.laser is None:
        return
    try:
        gui.laser.emission_off()
        gui.laser_emission_on_var.set(False)
        _update_emission_buttons(gui)
        gui.log("Optical: Laser emission off.")
    except Exception as e:
        gui.log(f"Optical: Emission off failed: {e}")


def _laser_emission_on(gui):
    if gui.laser is None:
        return
    try:
        gui.laser.emission_on()
        gui.laser_emission_on_var.set(True)
        _update_emission_buttons(gui)
        gui.log("Optical: Laser emission on.")
    except Exception as e:
        gui.log(f"Optical: Emission on failed: {e}")


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
    # If connected and using software power: turn emission off first, then set power (avoids spike)
    if gui.laser is not None and use_software is not None and use_software.get():
        try:
            power_mw = float(gui.laser_power_var.get().strip())
            gui.laser.set_to_digital_power_control(power_mw)  # already does emission_off + set power
            gui.laser_emission_on_var.set(False)
            _update_emission_buttons(gui)
            gui.log(f"Optical: Laser power set to {power_mw} mW (emission off until you turn On).")
        except (ValueError, Exception):
            pass
    elif gui.laser is not None and use_software is not None and not use_software.get():
        try:
            gui.laser.set_to_analog_modulation_mode(power_mw=100)
            gui.log("Optical: Laser set to manual (front panel) control.")
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
    # Reuse laser from Measurement GUI if already connected there
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
                    gui.log(f"Optical: Using shared connection ({idn}), power {power_mw} mW.")
                except ValueError:
                    gui.log(f"Optical: Using shared connection ({idn}). Set power (mW) and use 'Set (mW)' to apply.")
            else:
                gui.log(f"Optical: Using shared connection ({idn}), manual power.")
            gui.laser_status_var.set("Connected")
            gui.laser_emission_on_var.set(False)
            _update_emission_buttons(gui)
            gui.laser_conn_btn.config(state=tk.DISABLED)
            gui.laser_disc_btn.config(state=tk.NORMAL)
            return

    port = gui.laser_port_var.get().strip()
    try:
        baud = int(gui.laser_baud_var.get().strip())
    except ValueError:
        gui.log("Optical: Invalid baud rate.")
        return
    gui._laser_from_provider = False
    try:
        gui.laser = OxxiusLaser(port=port, baud=baud)
        idn = gui.laser.idn()
        if getattr(gui, "laser_power_use_software_var", None) and gui.laser_power_use_software_var.get():
            try:
                power_mw = float(gui.laser_power_var.get().strip())
                gui.laser.set_to_digital_power_control(power_mw)
                gui.log(f"Optical: Laser connected ({idn}), power set to {power_mw} mW.")
            except ValueError:
                gui.log(f"Optical: Laser connected ({idn}). Set valid power (mW) and use 'Set (mW)' to apply.")
        else:
            gui.log(f"Optical: Laser connected ({idn}), manual power control.")
        gui.laser_status_var.set("Connected")
        gui.laser_emission_on_var.set(False)
        _update_emission_buttons(gui)
        gui.laser_conn_btn.config(state=tk.DISABLED)
        gui.laser_disc_btn.config(state=tk.NORMAL)
    except Exception as e:
        gui.log(f"Optical: Connect failed: {e}")
        gui.laser = None


def _disconnect_laser(gui):
    if gui.laser is None:
        return
    if getattr(gui, "_laser_from_provider", False):
        gui.laser = None
        gui.laser_status_var.set("Disconnected")
        gui.laser_emission_on_var.set(False)
        _update_emission_buttons(gui)
        gui.laser_conn_btn.config(state=tk.NORMAL)
        gui.laser_disc_btn.config(state=tk.DISABLED)
        gui.log("Optical: Released shared connection (still connected in Measurement GUI).")
        return
    try:
        gui.laser.close(restore_to_manual_control=True)
    except Exception:
        pass
    gui.laser = None
    gui.laser_status_var.set("Disconnected")
    gui.laser_emission_on_var.set(False)
    _update_emission_buttons(gui)
    gui.laser_conn_btn.config(state=tk.NORMAL)
    gui.laser_disc_btn.config(state=tk.DISABLED)
    gui.log("Optical: Laser disconnected.")
