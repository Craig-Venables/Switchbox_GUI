"""
Tkinter layout construction helpers.
===================================

`MeasurementGUILayoutBuilder` encapsulates the Tkinter widget construction that
used to live inside `Measurement_GUI.py`.  By injecting the GUI instance we can
populate the same attributes (Tk variables, widgets) without leaving the main
class cluttered with layout code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

import tkinter as tk
from tkinter import ttk


@dataclass
class MeasurementGUILayoutBuilder:
    gui: object
    callbacks: Dict[str, Callable]
    widgets: Dict[str, tk.Widget] = field(default_factory=dict)

    def build_all_panels(
        self,
        left_frame: tk.Misc,
        middle_frame: tk.Misc,
        top_frame: Optional[tk.Misc] = None,
    ) -> None:
        self._build_connection_section(left_frame)
        self._build_mode_selection(left_frame)
        self._build_signal_messaging(left_frame)
        # self._build_manual_endurance_retention(left_frame)
        self._build_custom_measurement_section(middle_frame)
        self.build_sequential_controls(middle_frame)
        if top_frame is not None:
            self._build_top_banner(top_frame)

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------
    def _build_connection_section(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Keithley Connection", padx=5, pady=5)
        frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="Choose System:").grid(row=0, column=0, sticky="w")
        gui.systems = gui.load_systems()
        gui.system_var = tk.StringVar()
        system_dropdown = tk.OptionMenu(
            frame,
            gui.system_var,
            *gui.systems,
            command=self.callbacks.get("on_system_change"),
        )
        system_dropdown.grid(row=0, column=1, columnspan=2, sticky="ew")
        gui.system_dropdown = system_dropdown

        # SMU
        gui.iv_label = tk.Label(frame, text="GPIB Address - IV:")
        gui.iv_label.grid(row=1, column=0, sticky="w")
        gui.keithley_address_var = tk.StringVar(value=getattr(gui, "keithley_address", ""))
        gui.iv_address_entry = tk.Entry(frame, textvariable=gui.keithley_address_var)
        gui.iv_address_entry.grid(row=1, column=1)
        gui.iv_connect_button = tk.Button(frame, text="Connect", command=self.callbacks.get("connect_keithley"))
        gui.iv_connect_button.grid(row=1, column=2)

        # PSU
        gui.psu_label = tk.Label(frame, text="GPIB Address - PSU:")
        gui.psu_label.grid(row=2, column=0, sticky="w")
        gui.psu_address_var = tk.StringVar(value=getattr(gui, "psu_visa_address", ""))
        gui.psu_address_entry = tk.Entry(frame, textvariable=gui.psu_address_var)
        gui.psu_address_entry.grid(row=2, column=1)
        gui.psu_connect_button = tk.Button(frame, text="Connect", command=self.callbacks.get("connect_psu"))
        gui.psu_connect_button.grid(row=2, column=2)

        # Temperature controller
        gui.temp_label = tk.Label(frame, text="GPIB Address - Temp:")
        gui.temp_label.grid(row=3, column=0, sticky="w")
        gui.temp_address_var = tk.StringVar(value=getattr(gui, "temp_controller_address", ""))
        gui.temp_address_entry = tk.Entry(frame, textvariable=gui.temp_address_var)
        gui.temp_address_entry.grid(row=3, column=1)
        gui.temp_connect_button = tk.Button(frame, text="Connect", command=self.callbacks.get("connect_temp"))
        gui.temp_connect_button.grid(row=3, column=2)

        self.widgets["connection_frame"] = frame

    def _build_mode_selection(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Mode Selection", padx=5, pady=5)
        frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        gui.measure_one_device_label = tk.Label(frame, text="Measure One Device?")
        gui.measure_one_device_label.grid(row=0, column=0, sticky="w")
        gui.adaptive_var = tk.IntVar(value=1)
        gui.adaptive_switch = ttk.Checkbutton(
            frame,
            variable=gui.adaptive_var,
            command=self.callbacks.get("measure_one_device"),
        )
        gui.adaptive_switch.grid(row=0, column=1)

        gui.current_device_label = tk.Label(frame, text="Current Device:")
        gui.current_device_label.grid(row=1, column=0, sticky="w")
        gui.device_var = tk.Label(
            frame,
            text=getattr(gui, "display_index_section_number", ""),
            relief=tk.SUNKEN,
            anchor="w",
            width=20,
        )
        gui.device_var.grid(row=1, column=1, sticky="ew")

        gui.sample_name_label = tk.Label(frame, text="Sample Name (for saving):")
        gui.sample_name_label.grid(row=2, column=0, sticky="w")
        gui.sample_name_var = tk.StringVar()
        gui.sample_name_entry = ttk.Entry(frame, textvariable=gui.sample_name_var)
        gui.sample_name_entry.grid(row=2, column=1, sticky="ew")

        gui.additional_info_label = tk.Label(frame, text="Additional Info:")
        gui.additional_info_label.grid(row=3, column=0, sticky="w")
        gui.additional_info_var = tk.StringVar()
        gui.additional_info_entry = ttk.Entry(frame, textvariable=gui.additional_info_var)
        gui.additional_info_entry.grid(row=3, column=1, sticky="ew")

        save_location_frame = tk.Frame(frame)
        save_location_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        frame.columnconfigure(1, weight=1)

        gui.use_custom_save_var = tk.BooleanVar(value=False)
        gui.custom_save_location_var = tk.StringVar(value="")
        gui.custom_save_location = None

        tk.Checkbutton(
            save_location_frame,
            text="Use custom save location",
            variable=gui.use_custom_save_var,
            command=self.callbacks.get("on_custom_save_toggle"),
        ).grid(row=0, column=0, sticky="w")

        save_path_frame = tk.Frame(save_location_frame)
        save_path_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        save_path_frame.columnconfigure(0, weight=1)

        gui.save_path_entry = tk.Entry(
            save_path_frame,
            textvariable=gui.custom_save_location_var,
            state="disabled",
            width=40,
        )
        gui.save_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        browse_btn = tk.Button(save_path_frame, text="Browse...", command=self.callbacks.get("browse_save"))
        browse_btn.configure(state="disabled")
        browse_btn.grid(row=0, column=1)
        gui.save_browse_button = browse_btn

        # Load saved preference
        gui._load_save_location_config()

        self.widgets["mode_frame"] = frame

    def _build_top_banner(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="", padx=10, pady=10)
        frame.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(10, 5))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        title_label = tk.Label(
            frame,
            text="CRAIG'S CRAZY FUN IV CONTROL PANEL",
            font=("Helvetica", 12, "bold"),
            fg="black",
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=5, sticky="w")

        info_frame = tk.Frame(frame)
        info_frame.grid(row=1, column=0, columnspan=4, sticky="ew")
        info_frame.columnconfigure([0, 1, 2, 3, 4], weight=1)

        gui.device_label = tk.Label(info_frame, text="Device: XYZ", font=("Helvetica", 12))
        gui.device_label.grid(row=1, column=0, padx=10, sticky="w")

        gui.voltage_label = tk.Label(info_frame, text="Voltage: 1.23 V", font=("Helvetica", 12))
        gui.voltage_label.grid(row=1, column=1, padx=10, sticky="w")

        gui.loop_label = tk.Label(info_frame, text="Loop: 5", font=("Helvetica", 12))
        gui.loop_label.grid(row=1, column=2, padx=10, sticky="w")

        open_motor_cb = self.callbacks.get("open_motor_control")
        gui.motor_control_button = tk.Button(
            info_frame,
            text="Motor Control",
            command=open_motor_cb,
            state=tk.NORMAL if open_motor_cb else tk.DISABLED,
        )
        gui.motor_control_button.grid(row=1, column=3, columnspan=1, pady=5)

        check_conn_cb = self.callbacks.get("check_connection")
        gui.check_connection_button = tk.Button(
            info_frame,
            text="check_connection",
            command=check_conn_cb,
            state=tk.NORMAL if check_conn_cb else tk.DISABLED,
        )
        gui.check_connection_button.grid(row=1, column=4, columnspan=1, pady=5)

        gui._status_updates_active = True
        gui.master.after(250, gui._status_update_tick)

        self.widgets["top_banner"] = frame

    def _build_signal_messaging(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Telegram Messaging", padx=5, pady=5)
        frame.grid(row=8, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="Enable Telegram Bot").grid(row=0, column=0, sticky="w")
        current_value = getattr(gui, "get_messaged_var", 0)
        if hasattr(current_value, "get"):
            get_value = int(current_value.get())
        else:
            get_value = int(bool(current_value))
        gui.get_messaged_var = tk.IntVar(value=get_value)
        gui.get_messaged_switch = ttk.Checkbutton(frame, variable=gui.get_messaged_var)
        gui.get_messaged_switch.grid(row=0, column=1, padx=5, sticky="w")

        tk.Label(frame, text="Operator").grid(row=1, column=0, sticky="w")
        names = list(getattr(gui, "names", []))
        default_name = "Choose name" if names else "No_Name"
        gui.selected_user = tk.StringVar(value=default_name)
        gui.messaging_user_menu = ttk.Combobox(
            frame,
            textvariable=gui.selected_user,
            values=names,
            state="readonly" if names else "disabled",
        )
        gui.messaging_user_menu.grid(row=1, column=1, padx=5, sticky="ew")

        update_cb = self.callbacks.get("update_messaging_info") or getattr(gui, "update_messaging_info", None)
        if update_cb:
            gui.messaging_user_menu.bind("<<ComboboxSelected>>", update_cb)
            gui.get_messaged_switch.configure(command=lambda: update_cb(None))
        else:
            gui.get_messaged_switch.configure(state=tk.DISABLED)

        try:
            frame.lift()
        except Exception:
            pass

        frame.columnconfigure(1, weight=1)
        self.widgets["signal_messaging"] = frame

    def _build_manual_endurance_retention(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Manual Endurance / Retention", padx=5, pady=5)
        frame.grid(row=6, column=0, padx=10, pady=5, sticky="ew")

        end_frame = tk.Frame(frame)
        end_frame.grid(row=0, column=0, sticky="nw", padx=(0, 10))
        ret_frame = tk.Frame(frame)
        ret_frame.grid(row=0, column=1, sticky="ne")

        tk.Label(end_frame, text="Endurance").grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(end_frame, text="SET V").grid(row=1, column=0, sticky="w")
        end_set_default = getattr(gui, "end_set_v", 1.5)
        if hasattr(end_set_default, "get"):
            end_set_default = end_set_default.get()
        gui.end_set_v = tk.DoubleVar(value=end_set_default or 1.5)
        tk.Entry(end_frame, textvariable=gui.end_set_v, width=8).grid(row=1, column=1, sticky="w")

        tk.Label(end_frame, text="RESET V").grid(row=2, column=0, sticky="w")
        end_reset_default = getattr(gui, "end_reset_v", -1.5)
        if hasattr(end_reset_default, "get"):
            end_reset_default = end_reset_default.get()
        gui.end_reset_v = tk.DoubleVar(value=end_reset_default or -1.5)
        tk.Entry(end_frame, textvariable=gui.end_reset_v, width=8).grid(row=2, column=1, sticky="w")

        tk.Label(end_frame, text="Pulse (ms)").grid(row=3, column=0, sticky="w")
        end_pulse_default = getattr(gui, "end_pulse_ms", 10)
        if hasattr(end_pulse_default, "get"):
            end_pulse_default = end_pulse_default.get()
        gui.end_pulse_ms = tk.DoubleVar(value=end_pulse_default or 10)
        tk.Entry(end_frame, textvariable=gui.end_pulse_ms, width=8).grid(row=3, column=1, sticky="w")

        tk.Label(end_frame, text="Cycles").grid(row=4, column=0, sticky="w")
        end_cycles_default = getattr(gui, "end_cycles", 100)
        if hasattr(end_cycles_default, "get"):
            end_cycles_default = end_cycles_default.get()
        gui.end_cycles = tk.IntVar(value=end_cycles_default or 100)
        tk.Entry(end_frame, textvariable=gui.end_cycles, width=8).grid(row=4, column=1, sticky="w")

        tk.Label(end_frame, text="Read V").grid(row=5, column=0, sticky="w")
        end_read_default = getattr(gui, "end_read_v", 0.2)
        if hasattr(end_read_default, "get"):
            end_read_default = end_read_default.get()
        gui.end_read_v = tk.DoubleVar(value=end_read_default or 0.2)
        tk.Entry(end_frame, textvariable=gui.end_read_v, width=8).grid(row=5, column=1, sticky="w")

        start_endurance_cb = self.callbacks.get("start_manual_endurance") or getattr(gui, "start_manual_endurance", None)
        tk.Button(
            end_frame,
            text="Start Endurance",
            command=start_endurance_cb,
            state=tk.NORMAL if start_endurance_cb else tk.DISABLED,
        ).grid(row=6, column=0, columnspan=2, pady=(4, 0), sticky="w")

        tk.Label(ret_frame, text="Retention").grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(ret_frame, text="SET V").grid(row=1, column=0, sticky="w")
        ret_set_default = getattr(gui, "ret_set_v", 1.5)
        if hasattr(ret_set_default, "get"):
            ret_set_default = ret_set_default.get()
        gui.ret_set_v = tk.DoubleVar(value=ret_set_default or 1.5)
        tk.Entry(ret_frame, textvariable=gui.ret_set_v, width=8).grid(row=1, column=1, sticky="w")

        tk.Label(ret_frame, text="SET Time (ms)").grid(row=2, column=0, sticky="w")
        ret_set_ms_default = getattr(gui, "ret_set_ms", 10)
        if hasattr(ret_set_ms_default, "get"):
            ret_set_ms_default = ret_set_ms_default.get()
        gui.ret_set_ms = tk.DoubleVar(value=ret_set_ms_default or 10)
        tk.Entry(ret_frame, textvariable=gui.ret_set_ms, width=8).grid(row=2, column=1, sticky="w")

        tk.Label(ret_frame, text="Read V").grid(row=3, column=0, sticky="w")
        ret_read_default = getattr(gui, "ret_read_v", 0.2)
        if hasattr(ret_read_default, "get"):
            ret_read_default = ret_read_default.get()
        gui.ret_read_v = tk.DoubleVar(value=ret_read_default or 0.2)
        tk.Entry(ret_frame, textvariable=gui.ret_read_v, width=8).grid(row=3, column=1, sticky="w")

        tk.Label(ret_frame, text="Every (s)").grid(row=4, column=0, sticky="w")
        ret_every_default = getattr(gui, "ret_every_s", 10.0)
        if hasattr(ret_every_default, "get"):
            ret_every_default = ret_every_default.get()
        gui.ret_every_s = tk.DoubleVar(value=ret_every_default or 10.0)
        tk.Entry(ret_frame, textvariable=gui.ret_every_s, width=8).grid(row=4, column=1, sticky="w")

        tk.Label(ret_frame, text="# Points").grid(row=5, column=0, sticky="w")
        ret_points_default = getattr(gui, "ret_points", 30)
        if hasattr(ret_points_default, "get"):
            ret_points_default = ret_points_default.get()
        gui.ret_points = tk.IntVar(value=ret_points_default or 30)
        tk.Entry(ret_frame, textvariable=gui.ret_points, width=8).grid(row=5, column=1, sticky="w")

        ret_estimate_default = getattr(gui, "ret_estimate_var", "Total: ~300 s")
        if hasattr(ret_estimate_default, "get"):
            ret_estimate_default = ret_estimate_default.get()
        gui.ret_estimate_var = tk.StringVar(value=ret_estimate_default or "Total: ~300 s")
        tk.Label(ret_frame, textvariable=gui.ret_estimate_var, fg="grey").grid(row=6, column=0, columnspan=2, sticky="w")

        start_retention_cb = self.callbacks.get("start_manual_retention") or getattr(gui, "start_manual_retention", None)
        tk.Button(
            ret_frame,
            text="Start Retention",
            command=start_retention_cb,
            state=tk.NORMAL if start_retention_cb else tk.DISABLED,
        ).grid(row=7, column=0, columnspan=2, pady=(4, 0), sticky="w")

        led_frame = tk.Frame(frame)
        led_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        tk.Label(led_frame, text="LED:").pack(side="left")

        manual_led_power_default = getattr(gui, "manual_led_power", 1.0)
        if hasattr(manual_led_power_default, "get"):
            manual_led_power_default = manual_led_power_default.get()
        gui.manual_led_power = tk.DoubleVar(value=manual_led_power_default or 1.0)
        tk.Entry(led_frame, textvariable=gui.manual_led_power, width=8).pack(side="left", padx=(4, 4))

        gui.manual_led_on = getattr(gui, "manual_led_on", False)
        toggle_led_cb = self.callbacks.get("toggle_manual_led") or getattr(gui, "toggle_manual_led", None)
        gui.manual_led_btn = tk.Button(
            led_frame,
            text="LED ON" if gui.manual_led_on else "LED OFF",
            command=toggle_led_cb,
            state=tk.NORMAL if toggle_led_cb else tk.DISABLED,
        )
        gui.manual_led_btn.pack(side="left")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        self.widgets["manual_endurance_retention"] = frame

    def build_sequential_controls(self, parent: tk.Misc) -> None:
        self._build_sequential_controls(parent)

    def _build_sequential_controls(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Sequential Measurements", padx=5, pady=5)
        frame.grid(row=5, column=0, padx=10, pady=5, sticky="ew")

        existing_mode = getattr(gui, "Sequential_measurement_var", "Iv Sweep")
        if hasattr(existing_mode, "get"):
            existing_mode = existing_mode.get()
        gui.Sequential_measurement_var = tk.StringVar(value=existing_mode or "Iv Sweep")
        mode_menu = ttk.Combobox(
            frame,
            textvariable=gui.Sequential_measurement_var,
            values=["Iv Sweep", "Single Avg Measure"],
            state="readonly",
        )
        mode_menu.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tk.Label(frame, text="Mode:").grid(row=0, column=0, sticky="w")

        existing_sweeps = getattr(gui, "sequential_number_of_sweeps", 100)
        if hasattr(existing_sweeps, "get"):
            try:
                existing_sweeps = existing_sweeps.get()
            except Exception:
                existing_sweeps = 100
        try:
            sweeps_value = int(existing_sweeps)
        except Exception:
            sweeps_value = 100
        gui.sequential_number_of_sweeps = tk.IntVar(value=max(1, sweeps_value))
        tk.Label(frame, text="# Passes:").grid(row=1, column=0, sticky="w")
        sweeps_entry = tk.Entry(frame, textvariable=gui.sequential_number_of_sweeps, width=10)
        sweeps_entry.grid(row=1, column=1, sticky="w")

        existing_voltage = getattr(gui, "sq_voltage", 1.0)
        if hasattr(existing_voltage, "get"):
            try:
                existing_voltage = existing_voltage.get()
            except Exception:
                existing_voltage = 1.0
        try:
            voltage_value = float(existing_voltage)
        except Exception:
            voltage_value = 1.0
        gui.sq_voltage = tk.DoubleVar(value=voltage_value)
        tk.Label(frame, text="Voltage Limit (V):").grid(row=2, column=0, sticky="w")
        tk.Entry(frame, textvariable=gui.sq_voltage, width=10).grid(row=2, column=1, sticky="w")

        existing_delay = getattr(gui, "sq_time_delay", 1.0)
        if hasattr(existing_delay, "get"):
            try:
                existing_delay = existing_delay.get()
            except Exception:
                existing_delay = 1.0
        try:
            delay_value = float(existing_delay)
        except Exception:
            delay_value = 1.0
        gui.sq_time_delay = tk.DoubleVar(value=max(0.0, delay_value))
        tk.Label(frame, text="Delay Between Passes (s):").grid(row=3, column=0, sticky="w")
        tk.Entry(frame, textvariable=gui.sq_time_delay, width=10).grid(row=3, column=1, sticky="w")

        existing_duration = getattr(gui, "measurement_duration_var", 1.0)
        if hasattr(existing_duration, "get"):
            try:
                existing_duration = existing_duration.get()
            except Exception:
                existing_duration = 1.0
        try:
            duration_value = float(existing_duration)
        except Exception:
            duration_value = 1.0
        gui.measurement_duration_var = tk.DoubleVar(value=max(0.0, duration_value))
        tk.Label(frame, text="Duration per Device (s):").grid(row=4, column=0, sticky="w")
        duration_entry = tk.Entry(frame, textvariable=gui.measurement_duration_var, width=10)
        duration_entry.grid(row=4, column=1, sticky="w")

        existing_live_plot = getattr(gui, "live_plot_enabled", None)
        if not isinstance(existing_live_plot, tk.BooleanVar):
            gui.live_plot_enabled = tk.BooleanVar(
                value=bool(existing_live_plot) if existing_live_plot is not None else True
            )
        else:
            gui.live_plot_enabled = existing_live_plot
        tk.Checkbutton(
            frame,
            text="Enable live plotting",
            variable=gui.live_plot_enabled,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

        start_cb = self.callbacks.get("start_sequential_measurement") or getattr(
            gui, "sequential_measure", None
        )
        stop_cb = self.callbacks.get("stop_sequential_measurement") or getattr(
            gui, "set_measurment_flag_true", None
        )

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(6, 0), sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        start_state = tk.NORMAL if callable(start_cb) else tk.DISABLED
        stop_state = tk.NORMAL if callable(stop_cb) else tk.DISABLED

        tk.Button(btn_frame, text="Start Sequential", command=start_cb, state=start_state).grid(
            row=0, column=0, padx=(0, 4), sticky="ew"
        )
        tk.Button(btn_frame, text="Stop", command=stop_cb, state=stop_state).grid(
            row=0, column=1, padx=(4, 0), sticky="ew"
        )

        def _update_duration_state(*_: object) -> None:
            mode = gui.Sequential_measurement_var.get()
            if mode == "Single Avg Measure":
                duration_entry.configure(state="normal")
            else:
                duration_entry.configure(state="disabled")

        mode_menu.bind("<<ComboboxSelected>>", _update_duration_state)
        _update_duration_state()

        frame.columnconfigure(1, weight=1)
        self.widgets["sequential_controls"] = frame

    def _build_custom_measurement_section(self, parent: tk.Misc) -> None:
        gui = self.gui
        frame = tk.LabelFrame(parent, text="Custom Measurements", padx=5, pady=5)
        frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(frame, text="Custom Measurement:").grid(row=0, column=0, sticky="w")
        test_names = getattr(gui, "test_names", [])
        default_test = test_names[0] if test_names else "Test"
        gui.custom_measurement_var = tk.StringVar(value=default_test)
        gui.custom_measurement_menu = ttk.Combobox(
            frame,
            textvariable=gui.custom_measurement_var,
            values=test_names,
            state="readonly" if test_names else "disabled",
        )
        gui.custom_measurement_menu.grid(row=0, column=1, padx=5)

        start_cb = self.callbacks.get("start_custom_measurement_thread") or getattr(gui, "start_custom_measurement", None)
        gui.run_custom_button = tk.Button(
            frame,
            text="Run Custom",
            command=start_cb,
            state=tk.NORMAL if start_cb else tk.DISABLED,
        )
        gui.run_custom_button.grid(row=1, column=0, columnspan=2, pady=5)

        def toggle_pause() -> None:
            toggle_cb = self.callbacks.get("toggle_custom_pause") or getattr(gui, "toggle_custom_pause", None)
            if not toggle_cb:
                return
            new_state = toggle_cb()
            try:
                gui.pause_button_custom.config(text="Resume" if new_state else "Pause")
            except Exception:
                pass

        gui.pause_button_custom = tk.Button(frame, text="Pause", width=10, command=toggle_pause)
        gui.pause_button_custom.grid(row=2, column=0, padx=5, pady=2, sticky="w")

        edit_cb = self.callbacks.get("open_sweep_editor") or getattr(gui, "open_sweep_editor_popup", None)
        tk.Button(
            frame,
            text="Edit Sweeps",
            command=edit_cb,
            state=tk.NORMAL if edit_cb else tk.DISABLED,
        ).grid(row=2, column=1, padx=5, pady=2, sticky="w")

        frame.columnconfigure(1, weight=1)
        self.widgets["custom_measurements"] = frame


def _self_test() -> None:
    """Basic smoke-test to ensure panels build without raising."""
    root = tk.Tk()
    root.withdraw()

    class _DummyGUI:
        def __init__(self, master: tk.Tk) -> None:
            self.master = master
            self.names = []

        def load_systems(self):
            return ["System 1"]

        def _load_save_location_config(self):
            return None

        def _status_update_tick(self):
            return None

    dummy = _DummyGUI(root)
    left = tk.Frame(root)
    middle = tk.Frame(root)
    top = tk.Frame(root)

    builder = MeasurementGUILayoutBuilder(
        gui=dummy,
        callbacks={
            "connect_keithley": lambda: None,
            "connect_psu": lambda: None,
            "connect_temp": lambda: None,
            "measure_one_device": lambda: None,
            "on_system_change": lambda _: None,
            "on_custom_save_toggle": lambda: None,
            "browse_save": lambda: None,
            "open_motor_control": lambda: None,
            "check_connection": lambda: None,
        },
    )
    builder.build_all_panels(left, middle, top)

    assert "top_banner" in builder.widgets

    root.destroy()


if __name__ == "__main__":  # pragma: no cover - developer smoke test
    _self_test()

