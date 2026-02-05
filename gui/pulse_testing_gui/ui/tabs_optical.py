"""
Optical tab – Oxxius laser connection and ms-scale light pulsing.
Used from Pulse Testing GUI under the "Optical" tab (formerly FG Measurements).
"""

import tkinter as tk
from tkinter import ttk
import threading

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
    gui.laser_status_var = tk.StringVar(value="Disconnected")
    tk.Label(btn_row, textvariable=gui.laser_status_var, fg="gray", font=("TkDefaultFont", 9)).pack(side=tk.LEFT, padx=10)

    # --- Pulse parameters ---
    pulse_frame = tk.LabelFrame(tab, text="Pulse (ms-scale, serial)", padx=5, pady=5)
    pulse_frame.pack(fill=tk.X, padx=5, pady=5)

    row2 = tk.Frame(pulse_frame)
    row2.pack(fill=tk.X, pady=2)
    tk.Label(row2, text="On (ms):", width=10, anchor="w").pack(side=tk.LEFT)
    gui.laser_on_ms_var = tk.StringVar(value="100")
    tk.Entry(row2, textvariable=gui.laser_on_ms_var, width=8).pack(side=tk.LEFT, padx=2)
    tk.Label(row2, text="Off (ms):", width=10, anchor="w").pack(side=tk.LEFT, padx=(10, 0))
    gui.laser_off_ms_var = tk.StringVar(value="200")
    tk.Entry(row2, textvariable=gui.laser_off_ms_var, width=8).pack(side=tk.LEFT, padx=2)
    tk.Label(row2, text="Pulses:", width=8, anchor="w").pack(side=tk.LEFT, padx=(10, 0))
    gui.laser_n_pulses_var = tk.StringVar(value="5")
    tk.Entry(row2, textvariable=gui.laser_n_pulses_var, width=6).pack(side=tk.LEFT, padx=2)
    tk.Label(row2, text="Power (mW):", width=10, anchor="w").pack(side=tk.LEFT, padx=(10, 0))
    gui.laser_power_var = tk.StringVar(value="")
    tk.Entry(row2, textvariable=gui.laser_power_var, width=6).pack(side=tk.LEFT, padx=2)
    tk.Label(row2, text="(blank = leave as is)", font=("TkDefaultFont", 8), fg="gray").pack(side=tk.LEFT, padx=2)

    btn_pulse = tk.Frame(pulse_frame)
    btn_pulse.pack(fill=tk.X, pady=5)
    gui.laser_single_pulse_btn = tk.Button(btn_pulse, text="Single pulse", command=lambda: _run_single_pulse(gui), state=tk.DISABLED)
    gui.laser_single_pulse_btn.pack(side=tk.LEFT, padx=2)
    gui.laser_train_btn = tk.Button(btn_pulse, text="Pulse train", command=lambda: _run_pulse_train(gui), state=tk.DISABLED)
    gui.laser_train_btn.pack(side=tk.LEFT, padx=2)

    # Info
    tk.Label(tab, text="Pulsing uses serial (DL 1/0). For faster modulation use TTL input later.",
             font=("TkDefaultFont", 8), fg="gray").pack(anchor="w", padx=5, pady=2)


def _connect_laser(gui):
    port = gui.laser_port_var.get().strip()
    try:
        baud = int(gui.laser_baud_var.get().strip())
    except ValueError:
        gui.log("Optical: Invalid baud rate.")
        return
    try:
        gui.laser = OxxiusLaser(port=port, baud=baud)
        idn = gui.laser.idn()
        gui.laser_status_var.set("Connected")
        gui.laser_conn_btn.config(state=tk.DISABLED)
        gui.laser_disc_btn.config(state=tk.NORMAL)
        gui.laser_single_pulse_btn.config(state=tk.NORMAL)
        gui.laser_train_btn.config(state=tk.NORMAL)
        gui.log(f"Optical: Laser connected ({idn})")
    except Exception as e:
        gui.log(f"Optical: Connect failed: {e}")
        gui.laser = None


def _disconnect_laser(gui):
    if gui.laser is None:
        return
    try:
        gui.laser.close(restore_to_manual_control=True)
    except Exception:
        pass
    gui.laser = None
    gui.laser_status_var.set("Disconnected")
    gui.laser_conn_btn.config(state=tk.NORMAL)
    gui.laser_disc_btn.config(state=tk.DISABLED)
    gui.laser_single_pulse_btn.config(state=tk.DISABLED)
    gui.laser_train_btn.config(state=tk.DISABLED)
    gui.log("Optical: Laser disconnected.")


def _run_single_pulse(gui):
    if gui.laser is None:
        gui.log("Optical: Connect laser first.")
        return
    try:
        on_ms = float(gui.laser_on_ms_var.get().strip())
    except ValueError:
        gui.log("Optical: Invalid On (ms).")
        return
    if on_ms <= 0 or on_ms > 60000:
        gui.log("Optical: On (ms) must be in (0, 60000].")
        return

    def do():
        gui.laser.pulse_on_ms(on_ms)
        gui.log("Optical: Single pulse done.")

    threading.Thread(target=do, daemon=True).start()
    gui.log("Optical: Single pulse started.")


def _run_pulse_train(gui):
    if gui.laser is None:
        gui.log("Optical: Connect laser first.")
        return
    if getattr(gui, "_optical_pulse_running", False):
        gui.log("Optical: Pulse train already running.")
        return
    try:
        on_ms = float(gui.laser_on_ms_var.get().strip())
        off_ms = float(gui.laser_off_ms_var.get().strip())
        n_pulses = int(gui.laser_n_pulses_var.get().strip())
        power_str = gui.laser_power_var.get().strip()
        power_mw = int(power_str) if power_str else None
    except ValueError as e:
        gui.log(f"Optical: Invalid pulse params: {e}")
        return
    if n_pulses < 1 or on_ms <= 0 or off_ms < 0:
        gui.log("Optical: Pulses >= 1, On > 0, Off >= 0.")
        return

    def do():
        gui._optical_pulse_running = True
        gui.laser_train_btn.config(state=tk.DISABLED)
        gui.laser_single_pulse_btn.config(state=tk.DISABLED)
        try:
            gui.laser.pulse_train(n_pulses, on_ms, off_ms, power_mw=power_mw)
            gui.log(f"Optical: Pulse train done ({n_pulses} pulses).")
        except Exception as e:
            gui.log(f"Optical: Pulse train error: {e}")
        finally:
            gui._optical_pulse_running = False
            if gui.laser is not None:
                gui.laser_train_btn.config(state=tk.NORMAL)
                gui.laser_single_pulse_btn.config(state=tk.NORMAL)

    threading.Thread(target=do, daemon=True).start()
    gui.log("Optical: Pulse train started.")
