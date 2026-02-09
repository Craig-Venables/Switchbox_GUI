"""
Laser section – Oxxius laser connection and pulsing controls (collapsible).
Integrated into manual tab for seamless optical testing.
"""

import tkinter as tk
from tkinter import ttk
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
    gui.laser_status_var = tk.StringVar(value="Disconnected")
    tk.Label(header_frame, textvariable=gui.laser_status_var, fg="gray", font=("TkDefaultFont", 8)).pack(side=tk.RIGHT, padx=(5, 0))
    
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

    # --- Pulse parameters ---
    row2 = tk.Frame(gui.laser_inner_frame)
    row2.pack(fill=tk.X, pady=(3, 1))
    tk.Label(row2, text="On (ms):", width=8, anchor="w").pack(side=tk.LEFT)
    gui.laser_on_ms_var = tk.StringVar(value="100")
    tk.Entry(row2, textvariable=gui.laser_on_ms_var, width=6).pack(side=tk.LEFT, padx=2)
    tk.Label(row2, text="Off (ms):", width=8, anchor="w").pack(side=tk.LEFT, padx=(5, 0))
    gui.laser_off_ms_var = tk.StringVar(value="200")
    tk.Entry(row2, textvariable=gui.laser_off_ms_var, width=6).pack(side=tk.LEFT, padx=2)
    tk.Label(row2, text="Pulses:", width=6, anchor="w").pack(side=tk.LEFT, padx=(5, 0))
    gui.laser_n_pulses_var = tk.StringVar(value="5")
    tk.Entry(row2, textvariable=gui.laser_n_pulses_var, width=4).pack(side=tk.LEFT, padx=2)
    tk.Label(row2, text="Pwr (mW):", width=8, anchor="w").pack(side=tk.LEFT, padx=(5, 0))
    gui.laser_power_var = tk.StringVar(value="")
    tk.Entry(row2, textvariable=gui.laser_power_var, width=4).pack(side=tk.LEFT, padx=2)

    btn_pulse = tk.Frame(gui.laser_inner_frame)
    btn_pulse.pack(fill=tk.X, pady=2)
    gui.laser_single_pulse_btn = tk.Button(btn_pulse, text="Single pulse", command=lambda: _run_single_pulse(gui), state=tk.DISABLED, font=("TkDefaultFont", 8))
    gui.laser_single_pulse_btn.pack(side=tk.LEFT, padx=2)
    # Pulse train: fires N consecutive laser pulses (on for On ms, off for Off ms between them)
    gui.laser_train_btn = tk.Button(btn_pulse, text="Pulse train", command=lambda: _run_pulse_train(gui), state=tk.DISABLED, font=("TkDefaultFont", 8))
    gui.laser_train_btn.pack(side=tk.LEFT, padx=2)

    # Info
    tk.Label(gui.laser_inner_frame, text="Single pulse: one light pulse (On ms). Pulse train: N consecutive pulses (On/Off ms). Serial (DL 1/0); for faster use TTL.",
             font=("TkDefaultFont", 7), fg="gray").pack(anchor="w", padx=2, pady=1)


def _connect_laser(gui):
    port = gui.laser_port_var.get().strip()
    try:
        baud = int(gui.laser_baud_var.get().strip())
    except ValueError:
        gui.log("Laser: Invalid baud rate.")
        return
    try:
        gui.laser = OxxiusLaser(port=port, baud=baud)
        idn = gui.laser.idn()
        gui.laser_status_var.set("Connected")
        gui.laser_conn_btn.config(state=tk.DISABLED)
        gui.laser_disc_btn.config(state=tk.NORMAL)
        gui.laser_single_pulse_btn.config(state=tk.NORMAL)
        gui.laser_train_btn.config(state=tk.NORMAL)
        gui.log(f"Laser: Connected ({idn})")
    except Exception as e:
        gui.log(f"Laser: Connect failed: {e}")
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
    gui.log("Laser: Disconnected.")


def _run_single_pulse(gui):
    if gui.laser is None:
        gui.log("Laser: Connect laser first.")
        return
    try:
        on_ms = float(gui.laser_on_ms_var.get().strip())
    except ValueError:
        gui.log("Laser: Invalid On (ms).")
        return
    if on_ms <= 0 or on_ms > 60000:
        gui.log("Laser: On (ms) must be in (0, 60000].")
        return

    def do():
        gui.laser.pulse_on_ms(on_ms)
        gui.log("Laser: Single pulse done.")

    threading.Thread(target=do, daemon=True).start()
    gui.log("Laser: Single pulse started.")


def _run_pulse_train(gui):
    if gui.laser is None:
        gui.log("Laser: Connect laser first.")
        return
    if getattr(gui, "_optical_pulse_running", False):
        gui.log("Laser: Pulse train already running.")
        return
    try:
        on_ms = float(gui.laser_on_ms_var.get().strip())
        off_ms = float(gui.laser_off_ms_var.get().strip())
        n_pulses = int(gui.laser_n_pulses_var.get().strip())
        power_str = gui.laser_power_var.get().strip()
        power_mw = int(power_str) if power_str else None
    except ValueError as e:
        gui.log(f"Laser: Invalid pulse params: {e}")
        return
    if n_pulses < 1 or on_ms <= 0 or off_ms < 0:
        gui.log("Laser: Pulses >= 1, On > 0, Off >= 0.")
        return

    def do():
        gui._optical_pulse_running = True
        gui.laser_train_btn.config(state=tk.DISABLED)
        gui.laser_single_pulse_btn.config(state=tk.DISABLED)
        try:
            gui.laser.pulse_train(n_pulses, on_ms, off_ms, power_mw=power_mw)
            gui.log(f"Laser: Pulse train done ({n_pulses} pulses).")
        except Exception as e:
            gui.log(f"Laser: Pulse train error: {e}")
        finally:
            gui._optical_pulse_running = False
            if gui.laser is not None:
                gui.laser_train_btn.config(state=tk.NORMAL)
                gui.laser_single_pulse_btn.config(state=tk.NORMAL)

    threading.Thread(target=do, daemon=True).start()
    gui.log("Laser: Pulse train started.")
