"""
Connection section – device/system selection, address, connect/disconnect, simple save toggle.
Builds the Connection LabelFrame and sets connection-related attributes on the GUI instance.
"""

import tkinter as tk
from tkinter import ttk

from Pulse_Testing.system_wrapper import detect_system_from_address, get_default_address_for_system


def toggle_connection_section(gui):
    """Toggle collapse/expand of connection section."""
    if gui.conn_collapsed.get():
        gui.conn_inner_frame.pack(fill=tk.X)
        gui.conn_collapse_btn.config(text="▼")
        gui.conn_collapsed.set(False)
    else:
        gui.conn_inner_frame.pack_forget()
        gui.conn_collapse_btn.config(text="▶")
        gui.conn_collapsed.set(True)


def build_connection_section(parent, gui):
    """Build Connection controls (system, device, terminals, connect, simple save). Sets gui.conn_*, gui.system_var, gui.addr_var, etc."""
    frame = tk.LabelFrame(parent, text="Connection", padx=5, pady=5)
    frame.pack(fill=tk.X, padx=5, pady=5)

    gui.conn_inner_frame = tk.Frame(frame)
    gui.conn_inner_frame.pack(fill=tk.X)
    gui.conn_collapsed = tk.BooleanVar(value=False)

    header_frame = tk.Frame(frame)
    header_frame.pack(fill=tk.X, pady=(0, 5))
    gui.conn_collapse_btn = tk.Button(header_frame, text="▼", width=3,
                                      command=lambda: toggle_connection_section(gui),
                                      font=("TkDefaultFont", 8), relief=tk.FLAT)
    gui.conn_collapse_btn.pack(side=tk.LEFT, padx=(0, 5))

    gui.context_var = tk.StringVar(value=f"Sample: {gui.sample_name}  |  Device: {gui.device_label}")
    tk.Label(header_frame, textvariable=gui.context_var, font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT, anchor="w")
    gui.conn_status_var = tk.StringVar(value="Disconnected")
    tk.Label(header_frame, textvariable=gui.conn_status_var, fg="red", font=("TkDefaultFont", 8)).pack(side=tk.RIGHT, padx=(5, 0))

    detected_system = detect_system_from_address(gui.device_address)
    gui.system_var = tk.StringVar()
    gui.system_var.set(detected_system if detected_system else "keithley4200a")

    system_frame = tk.Frame(gui.conn_inner_frame)
    system_frame.pack(fill=tk.X, pady=2)
    tk.Label(system_frame, text="System:").pack(side=tk.LEFT)
    system_combo = ttk.Combobox(system_frame, textvariable=gui.system_var,
                                values=["keithley2450", "keithley2450_sim", "keithley4200a", "keithley2400"],
                                state="readonly", width=20)
    system_combo.pack(side=tk.LEFT, padx=5)
    tk.Button(system_frame, text="🔍 Auto", command=gui._auto_detect_system, width=6, font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=2)
    gui.system_var.trace_add("write", lambda *args: gui._on_system_changed())

    addr_frame = tk.Frame(gui.conn_inner_frame)
    addr_frame.pack(fill=tk.X, pady=(5, 2))
    tk.Label(addr_frame, text="Device:").pack(side=tk.LEFT)
    gui.addr_var = tk.StringVar()
    if detected_system:
        default_addr = get_default_address_for_system(detected_system)
        gui.addr_var.set(default_addr or gui.device_address)
    else:
        gui.addr_var.set(gui.device_address)
    available_devices = gui._get_available_devices()
    current_addr = gui.addr_var.get()
    if current_addr not in available_devices and available_devices:
        available_devices.insert(0, current_addr)
    gui.addr_combo = ttk.Combobox(addr_frame, textvariable=gui.addr_var, values=available_devices, width=37, state="readonly")
    gui.addr_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    tk.Button(addr_frame, text="🔄", command=gui._refresh_devices, width=3, font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=2)
    gui.addr_var.trace_add("write", lambda *args: gui._update_system_detection())

    term_frame = tk.Frame(gui.conn_inner_frame)
    term_frame.pack(fill=tk.X, pady=(5, 2))
    tk.Label(term_frame, text="Terminals:").pack(side=tk.LEFT)
    gui.terminals_var = tk.StringVar()
    default_terminals = gui.load_default_terminals()
    gui.terminals_var.set(default_terminals)
    tk.Radiobutton(term_frame, text="Front", variable=gui.terminals_var, value="front", command=gui.save_terminal_default).pack(side=tk.LEFT, padx=5)
    tk.Radiobutton(term_frame, text="Rear", variable=gui.terminals_var, value="rear", command=gui.save_terminal_default).pack(side=tk.LEFT, padx=5)

    btn_frame = tk.Frame(gui.conn_inner_frame)
    btn_frame.pack(fill=tk.X, pady=5)
    tk.Button(btn_frame, text="Connect", command=gui.connect_device, bg="green", fg="white").pack(side=tk.LEFT, padx=2)
    tk.Button(btn_frame, text="Disconnect", command=gui.disconnect_device).pack(side=tk.LEFT, padx=2)

    save_frame = tk.Frame(gui.conn_inner_frame)
    save_frame.pack(fill=tk.X, pady=(8, 0))
    tk.Checkbutton(save_frame, text="Simple Save:", variable=gui.use_simple_save_var,
                   command=gui._on_simple_save_toggle, font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
    gui.simple_save_entry = tk.Entry(save_frame, textvariable=gui.simple_save_path_var, width=25, state="disabled", font=("TkDefaultFont", 8))
    gui.simple_save_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
    tk.Button(save_frame, text="📁", command=gui._browse_simple_save, state="disabled", width=2, font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=1)
