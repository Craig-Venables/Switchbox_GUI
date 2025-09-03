import threading
import time
import os
from pathlib import Path
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from measurement_service import MeasurementService
from Equipment_Classes.SMU.Keithley4200A import Keithley4200A_PMUController


from Equipment_Classes.Moku.laser_controller import MonkuGoController, LaserFunctionGenerator


class Tooltip:
    """Simple hover tooltip for Tk widgets."""
    def __init__(self, widget, text: str, delay_ms: int = 400):
        self.widget = widget
        self.text = text
        self.delay_ms = max(0, int(delay_ms))
        self.tipwindow = None
        self._after_id = None
        try:
            self.widget.bind("<Enter>", self._on_enter, add="+")
            self.widget.bind("<Leave>", self._on_leave, add="+")
            self.widget.bind("<Motion>", self._on_motion, add="+")
        except Exception:
            pass

    def _on_enter(self, _event=None):
        self._schedule()

    def _on_leave(self, _event=None):
        self._unschedule()
        self._hide()

    def _on_motion(self, _event=None):
        # restart delay on motion to reduce flicker
        self._unschedule()
        self._schedule()

    def _schedule(self):
        try:
            self._after_id = self.widget.after(self.delay_ms, self._show)
        except Exception:
            pass

    def _unschedule(self):
        try:
            if self._after_id is not None:
                self.widget.after_cancel(self._after_id)
                self._after_id = None
        except Exception:
            pass

    def _show(self):
        if self.tipwindow or not self.text:
            return
        try:
            x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, "bbox") else (0, 0, 0, 0)
        except Exception:
            x, y, cx, cy = 0, 0, 0, 0
        try:
            x = x + self.widget.winfo_rootx() + 20
            y = y + self.widget.winfo_rooty() + cy + 20
        except Exception:
            return
        try:
            self.tipwindow = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                             background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                             font=("TkDefaultFont", 8))
            label.pack(ipadx=4, ipy=2)
        except Exception:
            self.tipwindow = None

    def _hide(self):
        try:
            if self.tipwindow is not None:
                self.tipwindow.destroy()
                self.tipwindow = None
        except Exception:
            pass

class PMUTestingGUI(tk.Toplevel):
    """PMU and Laser generator testing window with granular controls and live previews."""

    def __init__(self, master, pmu_address: str = "192.168.0.10:8888", provider=None):
        super().__init__(master)
        self.title("PMU & Laser Pulse Testing")
        try:
            # Give us more room
            self.geometry("1400x1000")
        except Exception:
            pass
        try:
            self.resizable(True, True)
        except Exception:
            pass

        self.service = MeasurementService()
        self.pmu = None
        self.moku_ctrl = None  # Moku:Go controller
        self.laser = None      # LaserFunctionGenerator
        self._moku_run_thread = None
        self._moku_stop = None
        self._exp_thread = None
        self._exp_stop = None
        self.pulses_applied = 0
        self.provider = provider

        # Context (sample/device) pulled from provider when available
        self.sample_name: str = "UnknownSample"
        self.device_label: str = "UnknownDevice"

        # ---------------- Controls: PMU ----------------
        ctrl = tk.LabelFrame(self, text="PMU Controls", padx=5, pady=3)
        ctrl.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=5, pady=3)

        self.context_var = tk.StringVar(value="Sample: -  |  Device: -")
        tk.Label(ctrl, textvariable=self.context_var, font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,4))

        # Connection section
        conn_frame = tk.Frame(ctrl)
        conn_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0,5))
        conn_frame.columnconfigure(1, weight=1)

        tk.Label(conn_frame, text="PMU Addr:").grid(row=0, column=0, sticky="w")
        self.addr_var = tk.StringVar(value=pmu_address)
        tk.Entry(conn_frame, textvariable=self.addr_var, width=35).grid(row=0, column=1, sticky="ew", padx=(5,0))
        tk.Button(conn_frame, text="Connect PMU", command=self.connect_pmu).grid(row=0, column=2, padx=5)
        self.status_var = tk.StringVar(value="PMU: Disconnected")
        tk.Label(conn_frame, textvariable=self.status_var).grid(row=0, column=3, sticky="w", padx=(5,0))

        # Mode section
        mode_frame = tk.Frame(ctrl)
        mode_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0,5))
        mode_frame.columnconfigure(1, weight=1)

        tk.Label(mode_frame, text="Mode:").grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="Pulse Train")
        self.mode_combo = ttk.Combobox(mode_frame, textvariable=self.mode_var, values=[
            "Pulse Train", "Pulse Pattern", "Amplitude Sweep", "Width Sweep", "Transient", "Endurance"
        ], width=25, state="readonly")
        self.mode_combo.grid(row=0, column=1, columnspan=2, sticky="ew")
        self.mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_enabled_controls())

        # Basic parameters section
        basic_frame = tk.Frame(ctrl)
        basic_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0,5))
        basic_frame.columnconfigure([1,3], weight=1)

        def mk_spin(row, col, label, init, frm=basic_frame):
            tk.Label(frm, text=label).grid(row=row, column=col*2, sticky="w")
            var = tk.StringVar(value=str(init))
            tk.Entry(frm, textvariable=var, width=12).grid(row=row, column=col*2+1, sticky="ew", padx=(5,10))
            return var

        self.amp_v = mk_spin(0, 0, "Amplitude V:", 0.5)
        self.base_v = mk_spin(0, 1, "Base V:", 0.0)
        self.width_s = mk_spin(1, 0, "Width (s):", 10e-6)
        self.period_s = mk_spin(1, 1, "Period (s):", 20e-6)
        self.num_pulses = mk_spin(2, 0, "Num Pulses:", 10)
        self.pattern = mk_spin(2, 1, "Pattern:", "1011")

        # Sweep parameters section
        sweep_frame = tk.Frame(ctrl)
        sweep_frame.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(0,5))
        sweep_frame.columnconfigure([1,3], weight=1)

        self.step_v = mk_spin(0, 0, "Step V:", 0.1, sweep_frame)
        self.stop_v = mk_spin(0, 1, "Stop V:", 1.0, sweep_frame)

        # Timing parameters section
        timing_frame = tk.Frame(ctrl)
        timing_frame.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0,5))
        timing_frame.columnconfigure([1,3], weight=1)

        self.rise_s = mk_spin(0, 0, "Rise (s):", 1e-7, timing_frame)
        self.fall_s = mk_spin(0, 1, "Fall (s):", 1e-7, timing_frame)
        self.start_pct = mk_spin(1, 0, "Meas Start %:", 10, timing_frame)
        self.stop_pct = mk_spin(1, 1, "Meas Stop %:", 90, timing_frame)

        # Limits section
        limits_frame = tk.Frame(ctrl)
        limits_frame.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(0,5))
        limits_frame.columnconfigure([1,3], weight=1)

        self.v_limit = mk_spin(0, 0, "V limit (V):", 5.0, limits_frame)
        self.i_limit = mk_spin(0, 1, "I limit (A):", 0.1, limits_frame)

        # Buttons section
        btn_frame = tk.Frame(ctrl)
        btn_frame.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(5,0))
        btn_frame.columnconfigure([0,1,2], weight=1)

        tk.Button(btn_frame, text="Run", command=self.run_selected).grid(row=0, column=0, padx=5, pady=2)
        tk.Button(btn_frame, text="Preview PMU", command=self.preview_pmu_waveform).grid(row=0, column=1, padx=5, pady=2)
        tk.Button(btn_frame, text="Close", command=self.destroy).grid(row=0, column=2, padx=5, pady=2)
        # Auto-trigger checkbox for GEN when measurement starts
        self.auto_trigger_gen = tk.BooleanVar(value=False)
        tk.Checkbutton(btn_frame, text="Trigger function generator at start", variable=self.auto_trigger_gen).grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=(2,0))

        # ---------------- Controls: Laser Generator ----------------
        genf = tk.LabelFrame(self, text="Laser Pulse Generator", padx=5, pady=3)
        genf.grid(row=1, column=0, sticky="nsew", padx=5, pady=3)
        self.gen_frame = genf

        # Connection section
        conn_frame = tk.Frame(genf)
        conn_frame.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0,5))
        conn_frame.columnconfigure(1, weight=1)

        tk.Label(conn_frame, text="Moku IP:").grid(row=0, column=0, sticky="w")
        self.gen_addr_var = tk.StringVar(value="192.168.0.45")
        gen_addr_entry = tk.Entry(conn_frame, textvariable=self.gen_addr_var, width=35)
        gen_addr_entry.grid(row=0, column=1, sticky="ew", padx=(5,0))
        tk.Button(conn_frame, text="Connect Moku", command=self.connect_moku).grid(row=0, column=2, padx=5)
        self.moku_status = tk.StringVar(value="Moku: Disconnected")
        tk.Label(conn_frame, textvariable=self.moku_status).grid(row=0, column=3, sticky="w", padx=(5,0))
        Tooltip(gen_addr_entry, "Moku:Go IP address, e.g. 192.168.0.45")

        # Pulse definition
        pulsef = tk.LabelFrame(genf, text="Pulse Definition", padx=5, pady=3)
        pulsef.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(0,5))
        pulsef.columnconfigure([1,3,5], weight=1)

        def mk_field(row, col, label, init):
            tk.Label(pulsef, text=label).grid(row=row, column=col*2, sticky="w")
            var = tk.StringVar(value=str(init))
            tk.Entry(pulsef, textvariable=var, width=12).grid(row=row, column=col*2+1, sticky="ew", padx=(5,10))
            return var

        self.gen_channel_var = getattr(self, 'gen_channel_var', tk.IntVar(value=1))
        tk.Label(pulsef, text="Channel:").grid(row=0, column=0, sticky="w")
        self.simple_ch_combo = ttk.Combobox(pulsef, values=[1,2], textvariable=self.gen_channel_var, width=6, state="readonly")
        self.simple_ch_combo.grid(row=0, column=1, sticky="ew", padx=(5,10))

        self.simple_high_v   = mk_field(1, 0, "High (V):", 1.0)
        self.simple_width_s  = mk_field(1, 1, "Width (s):", 100e-9)
        self.simple_period_s = mk_field(1, 2, "Period (s):", 200e-9)
        self.simple_rise_s   = mk_field(2, 0, "Edge (s):", 16e-9)
        self.simple_cycles   = mk_field(2, 1, "Burst cycles:", 10)
        self.simple_duration = mk_field(2, 2, "Duration (s):", 1.0)

        # Mode & actions
        modef = tk.LabelFrame(genf, text="Mode & Actions", padx=5, pady=3)
        modef.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(0,5))
        modef.columnconfigure([1,3,5], weight=1)

        tk.Label(modef, text="Mode:").grid(row=0, column=0, sticky="w")
        self.moku_mode = tk.StringVar(value="manual")
        ttk.Combobox(modef, values=["manual","burst","continuous","external"], textvariable=self.moku_mode, width=12, state="readonly").grid(row=0, column=1, sticky="ew")
        tk.Button(modef, text="Preview", command=self.preview_pulse_waveform).grid(row=0, column=2, padx=5)
        tk.Button(modef, text="Start", command=self._moku_start).grid(row=0, column=3, padx=5)
        tk.Button(modef, text="Manual Fire", command=self.trigger_simple_now).grid(row=0, column=4, padx=5)
        tk.Button(modef, text="Stop", command=lambda: self._set_gen_output(False)).grid(row=0, column=5, padx=5)

        # Binary Pattern panel
        binf = tk.LabelFrame(genf, text="Binary Pattern (AWG)", padx=5, pady=3)
        binf.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(0,5))
        binf.columnconfigure([1,3,5], weight=1)
        tk.Label(binf, text="Pattern:").grid(row=0, column=0, sticky="w")
        self.binary_pattern = tk.StringVar(value="10110011")
        tk.Entry(binf, textvariable=self.binary_pattern, width=20).grid(row=0, column=1, sticky="ew", padx=(5,10))
        tk.Label(binf, text="Bit Period (s):").grid(row=0, column=2, sticky="w")
        self.binary_bitp = tk.StringVar(value=str(100e-9))
        tk.Entry(binf, textvariable=self.binary_bitp, width=14).grid(row=0, column=3, sticky="ew", padx=(5,10))
        tk.Label(binf, text="High (V):").grid(row=0, column=4, sticky="w")
        self.binary_high = tk.StringVar(value=str(1.0))
        tk.Entry(binf, textvariable=self.binary_high, width=10).grid(row=0, column=5, sticky="ew", padx=(5,10))
        tk.Label(binf, text="Samples/bit:").grid(row=1, column=0, sticky="w")
        self.binary_spb = tk.StringVar(value="10")
        tk.Entry(binf, textvariable=self.binary_spb, width=10).grid(row=1, column=1, sticky="ew", padx=(5,10))
        tk.Button(binf, text="Send Once", command=self._binary_send_once).grid(row=1, column=2, padx=5)
        tk.Button(binf, text="Continuous", command=self._binary_send_continuous).grid(row=1, column=3, padx=5)
        tk.Button(binf, text="Stop", command=self._binary_stop).grid(row=1, column=4, padx=5)

        # Experiments (simple preset loader)
        expf = tk.LabelFrame(genf, text="Experiments", padx=5, pady=3)
        expf.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(0,5))
        expf.columnconfigure(1, weight=1)
        tk.Label(expf, text="Preset:").grid(row=0, column=0, sticky="w")
        self.exp_preset = tk.StringVar(value="None")
        ttk.Combobox(expf, values=["None","Write (50ns/200ns, 1.5V)","Read (16ns/200ns, 0.5V)","Endurance (100ns/200ns, 1.0V)"], textvariable=self.exp_preset, state="readonly", width=28).grid(row=0, column=1, sticky="ew")
        tk.Button(expf, text="Load Preset", command=self._load_exp_preset).grid(row=0, column=2, padx=5)
        tk.Button(expf, text="Save Settings", command=self._save_moku_settings).grid(row=0, column=3, padx=5)
        tk.Button(expf, text="Load Settings", command=self._load_moku_settings).grid(row=0, column=4, padx=5)

        # Advanced sections (kept hidden)
        self.show_advanced = tk.BooleanVar(value=False)

        # Channel and waveform section
        ch_wave_frame = tk.Frame(genf)
        ch_wave_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0,5))
        ch_wave_frame.columnconfigure([1,3], weight=1)

        def mk_gen_spin(row, col, label, init, frm=ch_wave_frame):
            tk.Label(frm, text=label).grid(row=row, column=col*2, sticky="w")
            var = tk.StringVar(value=str(init))
            tk.Entry(frm, textvariable=var, width=12).grid(row=row, column=col*2+1, sticky="ew", padx=(5,10))
            return var

        self.gen_channel_var = getattr(self, 'gen_channel_var', tk.IntVar(value=1))
        ch_label = tk.Label(ch_wave_frame, text="Channel:")
        ch_label.grid(row=0, column=0, sticky="w")
        ch_combo = ttk.Combobox(ch_wave_frame, values=[1,2], textvariable=self.gen_channel_var, width=6, state="readonly")
        ch_combo.grid(row=0, column=1, sticky="ew", padx=(5,10))
        Tooltip(ch_label, "Select output channel (1 or 2)")

        self.gen_wave = tk.StringVar(value="PULSE")
        wv_label = tk.Label(ch_wave_frame, text="Waveform:")
        wv_label.grid(row=0, column=2, sticky="w")
        wv_combo = ttk.Combobox(ch_wave_frame, values=["PULSE","SQUARE","SINE","RAMP","DC"], textvariable=self.gen_wave, width=10, state="readonly")
        wv_combo.grid(row=0, column=3, sticky="ew")
        Tooltip(wv_label, "Choose waveform type. Fields below adapt to the selection.")

        # Basic waveform parameters section
        basic_wave_frame = tk.Frame(genf)
        basic_wave_frame.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(0,5))
        basic_wave_frame.columnconfigure([1,3], weight=1)

        self.gen_amp = mk_gen_spin(0, 0, "Amplitude (Vpp):", 1.0, basic_wave_frame)
        self.gen_offset = mk_gen_spin(0, 1, "Offset (V):", 0.0, basic_wave_frame)
        self.gen_freq = mk_gen_spin(1, 0, "Frequency (Hz):", 1e3, basic_wave_frame)
        self.gen_duty = mk_gen_spin(1, 1, "Duty (%):", 50, basic_wave_frame)
        self.gen_phase = mk_gen_spin(2, 0, "Phase (deg):", 0, basic_wave_frame)
        self.gen_load = mk_gen_spin(2, 1, "Load:", "50OHM", basic_wave_frame)
        # Tooltips explaining key concepts
        Tooltip(self._entry_for(self.gen_amp), "Amplitude in Vpp for SINE/SQUARE/RAMP/PULSE. For DC, use Offset.")
        Tooltip(self._entry_for(self.gen_offset), "Offset (V) shifts the waveform vertically. For DC, Offset sets the output level.")
        Tooltip(self._entry_for(self.gen_freq), "Frequency in Hz for periodic waveforms.")
        Tooltip(self._entry_for(self.gen_duty), "Duty cycle (%). Effective for SQUARE/PULSE and some RAMP modes.")
        Tooltip(self._entry_for(self.gen_phase), "Starting phase in degrees (SINE/SQUARE/RAMP)")
        Tooltip(self._entry_for(self.gen_load), "Output load: 50OHM, HIGHZ, or numeric impedance like 75")

        # Burst and timing controls section
        burst_frame = tk.Frame(genf)
        burst_frame.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0,5))
        burst_frame.columnconfigure([1,3], weight=1)

        self.gen_burst_mode = tk.StringVar(value="NCYC")
        bm_label = tk.Label(burst_frame, text="Burst Mode:")
        bm_label.grid(row=0, column=0, sticky="w")
        bm_combo = ttk.Combobox(burst_frame, values=["OFF","NCYC","GATE","INF"], textvariable=self.gen_burst_mode, width=8, state="readonly")
        bm_combo.grid(row=0, column=1, sticky="ew", padx=(5,10))
        Tooltip(bm_label, "OFF: no burst. NCYC: finite cycles per trigger. GATE: output while gate active. INF: continuous cycles after trigger.")

        self.gen_cycles = mk_gen_spin(0, 1, "Cycles:", 3, burst_frame)
        self.gen_trig_src = tk.StringVar(value="BUS")
        ts_label = tk.Label(burst_frame, text="Trig Src:")
        ts_label.grid(row=1, column=0, sticky="w")
        ts_combo = ttk.Combobox(burst_frame, values=["BUS","INT","EXT"], textvariable=self.gen_trig_src, width=8, state="readonly")
        ts_combo.grid(row=1, column=1, sticky="ew", padx=(5,10))
        Tooltip(ts_label, "BUS: software trigger (button). INT: internal rate. EXT: rear BNC trigger.")

        self.gen_int_period = mk_gen_spin(1, 1, "INT Period (s):", 0.01, burst_frame)
        self.gen_trig_delay = mk_gen_spin(2, 0, "Trig Delay (s):", 0.0, burst_frame)
        Tooltip(self._entry_for(self.gen_cycles), "Cycles for NCYC mode (number of waveform cycles per trigger)")
        Tooltip(self._entry_for(self.gen_int_period), "Internal trigger period when Trig Src = INT")
        Tooltip(self._entry_for(self.gen_trig_delay), "Trigger-to-output delay (if supported)")

        # Multi-shot control section
        multi_frame = tk.Frame(genf)
        multi_frame.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(0,5))
        multi_frame.columnconfigure([1,3], weight=1)

        self.gen_shots = mk_gen_spin(0, 0, "Shots:", 1, multi_frame)
        self.gen_inter_shot = mk_gen_spin(0, 1, "Inter-shot (s):", 0.1, multi_frame)

        # Buttons section
        btn_frame = tk.Frame(genf)
        btn_frame.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(5,0))
        btn_frame.columnconfigure([0,1,2], weight=1)

        tk.Button(btn_frame, text="Apply Settings", command=self.apply_generator_settings).grid(row=0, column=0, padx=5, pady=2)
        tk.Button(btn_frame, text="Preview Waveform", command=self.preview_generator_waveform).grid(row=0, column=1, padx=5, pady=2)
        tk.Button(btn_frame, text="Run Burst(s)", command=self.fire_laser_pulse).grid(row=0, column=2, padx=5, pady=2)
        # Separate output control buttons
        out_btns = tk.Frame(genf)
        out_btns.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(3,0))
        out_btns.columnconfigure([0,1], weight=1)
        tk.Button(out_btns, text="Output ON", command=lambda: self._set_gen_output(True)).grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        tk.Button(out_btns, text="Output OFF", command=lambda: self._set_gen_output(False)).grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        # Keep references to advanced frames for show/hide (remain hidden)
        self._adv_frames = [ch_wave_frame, basic_wave_frame, burst_frame, multi_frame, btn_frame, out_btns]

        # Update enabled generator fields when waveform/burst/trigger changes
        try:
            self.gen_wave_combo = wv_combo
            self.gen_wave_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_gen_controls())
            bm_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_gen_controls())
            ts_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_gen_controls())
        except Exception:
            pass
        # Live preview: update when pulse fields change
        try:
            for var in (self.simple_high_v, self.simple_width_s, self.simple_period_s, self.simple_rise_s, self.simple_cycles):
                def _bind(v=var):
                    try:
                        v.trace_add('write', lambda *_: self.preview_generator_waveform())
                    except Exception:
                        pass
                _bind()
        except Exception:
            pass
        # Initial state update
        try:
            self._update_gen_controls()
            # Hide advanced by default
            self._toggle_advanced(show=False)
        except Exception: pass

        # ---------------- Plots ----------------
        # PMU figure (top-right area)
        plotf_pmu = tk.LabelFrame(self, text="PMU Preview / Data", padx=5, pady=3)
        plotf_pmu.grid(row=0, column=1, sticky="nsew", padx=5, pady=3)
        self.fig_pmu = Figure(figsize=(7, 4), constrained_layout=True)
        # Two rows: PMU voltage on top, Generator preview on bottom
        from matplotlib.gridspec import GridSpec
        gs = GridSpec(2, 1, figure=self.fig_pmu, height_ratios=[1, 1])
        self.ax_pmu_v = self.fig_pmu.add_subplot(gs[0])
        self.ax_pmu_v.set_xlabel("t (s)"); self.ax_pmu_v.set_ylabel("PMU V (V)")
        # Generator preview on bottom
        self.ax_pmu_gen = self.fig_pmu.add_subplot(gs[1])
        self.ax_pmu_gen.set_xlabel("t (s)"); self.ax_pmu_gen.set_ylabel("GEN V (V)")
        self.canvas_pmu = FigureCanvasTkAgg(self.fig_pmu, master=plotf_pmu)
        self.canvas_pmu.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        # Counter + sync toggle
        row2 = tk.Frame(plotf_pmu)
        row2.grid(row=1, column=0, sticky="ew", pady=(2,0))
        self.counter_var = tk.StringVar(value="Pulses applied: 0")
        tk.Label(row2, textvariable=self.counter_var).pack(side="left")
        self.sync_time = tk.BooleanVar(value=False)
        tk.Checkbutton(row2, text="Sync time axes (PMU <> GEN)", variable=self.sync_time, command=self._sync_time_axes).pack(side="right")

        # Data Preview figure (right side, row 1)
        plotf_data = tk.LabelFrame(self, text="Latest Data Preview", padx=5, pady=3)
        plotf_data.grid(row=1, column=1, sticky="nsew", padx=5, pady=3)
        self.fig_data = Figure(figsize=(7, 4))
        self.ax_data_i = self.fig_data.add_subplot(121)
        self.ax_data_i.set_xlabel("t (s)"); self.ax_data_i.set_ylabel("I (A)")
        self.ax_data_v = self.fig_data.add_subplot(122)
        self.ax_data_v.set_xlabel("t (s)"); self.ax_data_v.set_ylabel("V (V)")
        self.canvas_data = FigureCanvasTkAgg(self.fig_data, master=plotf_data)
        self.canvas_data.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Combined tests controls (bottom row, spans both columns)
        combo = tk.LabelFrame(self, text="Experiments (PMU + Moku)", padx=5, pady=3)
        combo.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=3)
        # Experiment selection
        row0 = tk.Frame(combo)
        row0.grid(row=0, column=0, columnspan=10, sticky="ew", pady=(0,5))
        row0.columnconfigure([1,3,5,7,9], weight=1)
        tk.Label(row0, text="Experiment:").grid(row=0, column=0, sticky="w")
        self.exp_select = tk.StringVar(value="Photoelectric Decay")
        self.exp_combo = ttk.Combobox(row0, values=["Photoelectric Decay"], textvariable=self.exp_select, state="readonly", width=28)
        self.exp_combo.grid(row=0, column=1, sticky="ew")
        tk.Button(row0, text="Load Library", command=self._load_experiment_library).grid(row=0, column=4, padx=6)
        tk.Button(row0, text="Run", command=self._run_experiment).grid(row=0, column=2, padx=6)
        tk.Button(row0, text="Stop", command=self._stop_experiment).grid(row=0, column=3, padx=6)
        tk.Button(row0, text="Save Current", command=self._save_current_experiment_to_library).grid(row=0, column=5, padx=6)

        # Parameters row 1: PMU (separate boxed section)
        row1 = tk.LabelFrame(combo, text="PMU Parameters", padx=5, pady=3)
        row1.grid(row=1, column=0, columnspan=10, sticky="ew", pady=(0,5))
        row1.columnconfigure([1,3,5], weight=1)
        tk.Label(row1, text="Bias V:").grid(row=0, column=0, sticky="w")
        self.exp_bias = tk.StringVar(value="0.2")
        tk.Entry(row1, textvariable=self.exp_bias, width=10).grid(row=0, column=1, sticky="ew", padx=(5,10))
        tk.Label(row1, text="Capture (s):").grid(row=0, column=2, sticky="w")
        self.exp_cap = tk.StringVar(value="0.02")
        tk.Entry(row1, textvariable=self.exp_cap, width=10).grid(row=0, column=3, sticky="ew", padx=(5,10))
        tk.Label(row1, text="dt (s):").grid(row=0, column=4, sticky="w")
        self.exp_dt = tk.StringVar(value="0.001")
        tk.Entry(row1, textvariable=self.exp_dt, width=10).grid(row=0, column=5, sticky="ew", padx=(5,10))
        tk.Label(row1, text="Tip: Use smaller dt for finer decay capture.", fg="#666").grid(row=1, column=0, columnspan=6, sticky="w")

        # Parameters row 2: Laser (separate boxed section)
        row2 = tk.LabelFrame(combo, text="Laser Parameters", padx=5, pady=3)
        row2.grid(row=2, column=0, columnspan=10, sticky="ew", pady=(0,5))
        row2.columnconfigure([1,3,5,7], weight=1)
        tk.Label(row2, text="High (V):").grid(row=0, column=0, sticky="w")
        self.exp_high = tk.StringVar(value="1.0")
        tk.Entry(row2, textvariable=self.exp_high, width=10).grid(row=0, column=1, sticky="ew", padx=(5,10))
        tk.Label(row2, text="Width (s):").grid(row=0, column=2, sticky="w")
        self.exp_width = tk.StringVar(value="1e-7")
        tk.Entry(row2, textvariable=self.exp_width, width=10).grid(row=0, column=3, sticky="ew", padx=(5,10))
        tk.Label(row2, text="Period (s):").grid(row=0, column=4, sticky="w")
        self.exp_period = tk.StringVar(value="2e-7")
        tk.Entry(row2, textvariable=self.exp_period, width=10).grid(row=0, column=5, sticky="ew", padx=(5,10))
        tk.Label(row2, text="Edge (s):").grid(row=0, column=6, sticky="w")
        self.exp_edge = tk.StringVar(value="1.6e-8")
        tk.Entry(row2, textvariable=self.exp_edge, width=10).grid(row=0, column=7, sticky="ew", padx=(5,10))

        # Parameters row 3: Repeats & ramping (boxed with hints)
        row3 = tk.LabelFrame(combo, text="Repeats & Ramping", padx=5, pady=3)
        row3.grid(row=3, column=0, columnspan=10, sticky="ew", pady=(0,5))
        row3.columnconfigure([1,3,5,7,9], weight=1)
        tk.Label(row3, text="Repeats:").grid(row=0, column=0, sticky="w")
        self.exp_repeats = tk.StringVar(value="1")
        tk.Entry(row3, textvariable=self.exp_repeats, width=10).grid(row=0, column=1, sticky="ew", padx=(5,10))
        tk.Label(row3, text="Ramp ΔV:").grid(row=0, column=2, sticky="w")
        self.exp_ramp_step = tk.StringVar(value="0.0")
        tk.Entry(row3, textvariable=self.exp_ramp_step, width=10).grid(row=0, column=3, sticky="ew", padx=(5,10))
        tk.Label(row3, text="Every N:").grid(row=0, column=4, sticky="w")
        self.exp_ramp_every = tk.StringVar(value="1")
        tk.Entry(row3, textvariable=self.exp_ramp_every, width=10).grid(row=0, column=5, sticky="ew", padx=(5,10))
        tk.Label(row3, text="Max V:").grid(row=0, column=6, sticky="w")
        self.exp_ramp_max = tk.StringVar(value="3.3")
        tk.Entry(row3, textvariable=self.exp_ramp_max, width=10).grid(row=0, column=7, sticky="ew", padx=(5,10))
        tk.Label(row3, text="Cont. sec:").grid(row=0, column=8, sticky="w")
        self.exp_cont = tk.StringVar(value="0.0")
        tk.Entry(row3, textvariable=self.exp_cont, width=10).grid(row=0, column=9, sticky="ew", padx=(5,10))
        tk.Label(row3, text="Tip: Ramp increases High(V) by ΔV every N runs up to Max V.", fg="#666").grid(row=1, column=0, columnspan=10, sticky="w")
        # Help note
        tk.Label(combo, text="Photoelectric Decay: applies Moku pulse(s) at bias and samples current.", fg="#555").grid(row=4, column=0, columnspan=10, sticky="w", pady=(4,0))
        # Trigger role: PMU waits vs Moku triggers
        row4 = tk.Frame(combo)
        row4.grid(row=5, column=0, columnspan=10, sticky="ew", pady=(0,5))
        tk.Label(row4, text="Trigger role:").pack(side="left")
        self.trigger_role = tk.StringVar(value="moku_sends")
        ttk.Combobox(row4, values=["moku_sends","pmu_waits"], textvariable=self.trigger_role, state="readonly", width=14).pack(side="left", padx=6)
        tk.Button(row4, text="Send Trigger (CH2)", command=self._send_trigger_ch2).pack(side="left", padx=6)

        # Make frames flexible
        self.grid_columnconfigure(0, weight=1)  # Controls column
        self.grid_columnconfigure(1, weight=2)  # Plot area gets more space
        self.grid_rowconfigure(0, weight=1)  # PMU controls + PMU preview
        self.grid_rowconfigure(1, weight=1)  # Generator controls + Data preview
        self.grid_rowconfigure(2, weight=0)  # Combined tests (fixed height)

        # Configure individual frame internals
        # PMU controls frame
        ctrl.grid_columnconfigure(0, weight=1)
        ctrl.grid_columnconfigure(1, weight=1)
        ctrl.grid_columnconfigure(2, weight=1)
        ctrl.grid_columnconfigure(3, weight=1)
        for i in range(10):  # Allow flexible row expansion
            ctrl.grid_rowconfigure(i, weight=0)

        # Generator controls frame
        genf.grid_columnconfigure(0, weight=1)
        genf.grid_columnconfigure(1, weight=1)
        genf.grid_columnconfigure(2, weight=1)
        genf.grid_columnconfigure(3, weight=1)
        for i in range(10):
            genf.grid_rowconfigure(i, weight=0)

        # Combined tests frame
        combo.grid_columnconfigure(0, weight=1)
        combo.grid_columnconfigure(1, weight=1)
        combo.grid_columnconfigure(2, weight=1)
        combo.grid_columnconfigure(3, weight=1)
        combo.grid_columnconfigure(4, weight=1)
        combo.grid_columnconfigure(5, weight=1)
        combo.grid_columnconfigure(6, weight=1)
        combo.grid_columnconfigure(7, weight=1)
        combo.grid_columnconfigure(8, weight=1)
        for i in range(5):
            combo.grid_rowconfigure(i, weight=0)

        # Plot frames
        plotf_pmu.grid_columnconfigure(0, weight=1)
        plotf_pmu.grid_rowconfigure(0, weight=1)
        plotf_pmu.grid_rowconfigure(1, weight=0)

        plotf_data.grid_columnconfigure(0, weight=1)
        plotf_data.grid_rowconfigure(0, weight=1)

        # Init state
        self._update_enabled_controls()
        self.after(500, self._poll_context)

    # ---------------- PMU methods ----------------

    def connect_pmu(self):
        try:
            addr = self.addr_var.get().strip()
            self.pmu = Keithley4200A_PMUController(addr)
            if self.pmu.is_connected():
                self.status_var.set("PMU: Connected")
            else:
                self.status_var.set("PMU: Failed to connect")
        except Exception as exc:
            messagebox.showerror("PMU", f"Connection failed: {exc}")
            self.status_var.set("PMU: Failed to connect")

    def run_selected(self):
        if self.pmu is None or not self.pmu.is_connected():
            messagebox.showwarning("PMU", "Connect to PMU first.")
            return
        mode = self.mode_var.get()
        try:
            amp = float(self.amp_v.get()); base = float(self.base_v.get())
            wid = float(self.width_s.get()); per = float(self.period_s.get())
            n = int(float(self.num_pulses.get()))
            pat = self.pattern.get()
            step = float(self.step_v.get()); stopv = float(self.stop_v.get())
        except Exception:
            messagebox.showerror("PMU", "Invalid parameters.")
            return

        def do_run():
            try:
                # Optional: issue generator trigger at start
                self._maybe_trigger_gen_start()
                if mode == "Pulse Train":
                    v, i, t = self.service.run_pmu_pulse_train(pmu=self.pmu, amplitude_v=amp, base_v=base,
                                                               width_s=wid, period_s=per, num_pulses=n)
                elif mode == "Pulse Pattern":
                    v, i, t = self.service.run_pmu_pulse_pattern(pmu=self.pmu, pattern=pat, amplitude_v=amp,
                                                                 base_v=base, width_s=wid, period_s=per)
                elif mode == "Amplitude Sweep":
                    v, i, t = self.service.run_pmu_amplitude_sweep(pmu=self.pmu, start_v=base,
                                                                   stop_v=stopv, step_v=step, base_v=base,
                                                                   width_s=wid, period_s=per)
                elif mode == "Width Sweep":
                    widths = [wid + k*wid for k in range(max(1, n))]
                    v, i, t = self.service.run_pmu_width_sweep(pmu=self.pmu, amplitude_v=amp, base_v=base,
                                                               widths_s=widths, period_s=per)
                elif mode == "Transient":
                    v, i, t = self.service.run_pmu_transient_switching(pmu=self.pmu, amplitude_v=amp,
                                                                       base_v=base, width_s=wid, period_s=per)
                elif mode == "Endurance":
                    v, i, t = self.service.run_pmu_endurance(pmu=self.pmu, set_voltage=amp, reset_voltage=-amp,
                                                             pulse_width_s=wid, num_cycles=max(1, n), period_s=per)
                else:
                    v, i, t = [], [], []

                self.pulses_applied += max(1, len(t))
                self.counter_var.set(f"Pulses applied: {self.pulses_applied}")
                self.update_plot(t, i, v)
                self._save_pmu_trace(t, v, i, mode)
            except Exception as exc:
                messagebox.showerror("PMU", str(exc))

        threading.Thread(target=do_run, daemon=True).start()

    def update_plot(self, t, i, v_preview=None):
        try:
            self.ax_pmu_v.clear()
            self.ax_pmu_v.set_xlabel("t (s)"); self.ax_pmu_v.set_ylabel("PMU V (V)")
            if t and i:
                self.ax_data_i.clear(); self.ax_data_v.clear()
                # Update data preview with current measurements
                self.ax_data_i.plot(t, i, "-")
                self.ax_data_i.set_xlabel("t (s)"); self.ax_data_i.set_ylabel("I (A)")

            if v_preview is not None and len(v_preview) == len(t):
                self.ax_pmu_v.plot(t, v_preview, "r-", label="PMU Measured V")
                self.ax_pmu_v.legend()
                if t:
                    self.ax_data_v.plot(t, v_preview, "r-")
                    self.ax_data_v.set_xlabel("t (s)"); self.ax_data_v.set_ylabel("V (V)")
            else:
                # Draw preview from current params automatically if no measurement yet
                self.preview_pmu_waveform()
            # Adjust margins for PMU voltage plot
            try:
                lines = self.ax_pmu_v.get_lines()
                if lines:
                    ys = []
                    for ln in lines:
                        ys.extend(ln.get_ydata())
                    if ys:
                        y0, y1 = min(ys), max(ys)
                        pad = max(1e-12, (y1 - y0) * 0.1 or 0.1)
                        self.ax_pmu_v.set_ylim(y0 - pad, y1 + pad)
            except Exception:
                pass
            self.canvas_pmu.draw(); self.canvas_data.draw()
            self._sync_time_axes()
        except Exception:
            pass

    def preview_pmu_waveform(self):
        """Preview the pulse waveform based on PMU control parameters without running the PMU."""
        try:
            mode = self.mode_var.get()
            amp = float(self.amp_v.get())
            base = float(self.base_v.get())
            wid = float(self.width_s.get())
            per = float(self.period_s.get())
            n = int(float(self.num_pulses.get()))
            pat = self.pattern.get()
            step = float(self.step_v.get()); stopv = float(self.stop_v.get())

            t_prev, v_prev = [], []

            if mode == "Pulse Train":
                t0 = 0.0
                for _ in range(n):
                    t_prev.extend([t0, t0, t0 + wid, t0 + wid])
                    v_prev.extend([base, amp, amp, base])
                    t0 += per

            elif mode == "Pulse Pattern":
                t0 = 0.0
                for bit in pat:
                    level = amp if bit == "1" else base
                    t_prev.extend([t0, t0, t0 + wid, t0 + wid])
                    v_prev.extend([base, level, level, base])
                    t0 += per

            elif mode == "Amplitude Sweep":
                val = base
                t0 = 0.0
                while val <= stopv:
                    t_prev.extend([t0, t0, t0 + wid, t0 + wid])
                    v_prev.extend([base, val, val, base])
                    t0 += per
                    val += step

            elif mode == "Width Sweep":
                t0 = 0.0
                w = wid
                for k in range(n):
                    t_prev.extend([t0, t0, t0 + w, t0 + w])
                    v_prev.extend([base, amp, amp, base])
                    t0 += per
                    w += wid

            elif mode == "Transient":
                t_prev = [0, 0, wid, wid]
                v_prev = [base, amp, amp, base]

            elif mode == "Endurance":
                t0 = 0.0
                for k in range(n):
                    # Set
                    t_prev.extend([t0, t0, t0 + wid, t0 + wid])
                    v_prev.extend([base, amp, amp, base])
                    t0 += per
                    # Reset
                    t_prev.extend([t0, t0, t0 + wid, t0 + wid])
                    v_prev.extend([base, -amp, -amp, base])
                    t0 += per

            # Draw to plot (PMU voltage preview)
            self.ax_pmu_v.clear()
            self.ax_pmu_v.set_xlabel("t (s)")
            self.ax_pmu_v.set_ylabel("Preview V (PMU)")
            self.ax_pmu_v.plot(t_prev, v_prev, "b-")
            # Annotate key timings
            self._annotate_timing(self.ax_pmu_v, t_prev, v_prev,
                                  width=float(self.width_s.get()), period=float(self.period_s.get()),
                                  label_prefix="PMU")
            self.canvas_pmu.draw()
            self._sync_time_axes()

        except Exception as exc:
            messagebox.showerror("Preview PMU", f"Error generating preview: {exc}")
    # ---------------- Generator methods ----------------
    
    def connect_moku(self):
        try:
            ip = self.gen_addr_var.get().strip()
            ch = int(self.gen_channel_var.get()) if hasattr(self, 'gen_channel_var') else 1
            self.moku_ctrl = MonkuGoController(ip)
            # Touch WaveformGenerator to validate connection
            self.moku_ctrl.wavegen()
            self.laser = LaserFunctionGenerator(self.moku_ctrl, channel=ch)
            self.moku_status.set("Moku: Connected")
        except Exception as exc:
            messagebox.showerror("Moku", f"Connection failed: {exc}")
            self.moku_status.set("Moku: Failed")

    def apply_simple_generator_settings(self):
        # For Moku: no pre-apply needed; just ensure channel is reflected in LaserFunctionGenerator
        try:
            if not self.laser:
                messagebox.showwarning("Moku", "Connect Moku first.")
                return
            ch = int(self.gen_channel_var.get())
            # Recreate laser with new channel if changed
            if self.laser.channel != ch:
                self.laser = LaserFunctionGenerator(self.moku_ctrl, channel=ch)
            self.moku_status.set("Moku: Ready")
        except Exception as exc:
            messagebox.showerror("Moku", f"Apply error: {exc}")

    def trigger_simple_now(self):
        # Map to a single pulse on Moku
        try:
            if not self.laser:
                messagebox.showwarning("Moku", "Connect Moku first.")
                return
            high = float(self.simple_high_v.get())
            width = float(self.simple_width_s.get())
            period = float(self.simple_period_s.get())
            rise = float(self.simple_rise_s.get())
            # Use safe wrapper to handle session resets transparently
            self.laser.safe_send_single_pulse(voltage_high=high, pulse_width=width, edge_time=rise, period=period)
            self.moku_status.set("Moku: Single pulse sent")
        except Exception as exc:
            messagebox.showerror("Moku", f"Trigger error: {exc}")

    def apply_burst_settings_only(self):
        # Not applicable for Moku; kept as no-op to preserve UI flow
        try:
            self.moku_status.set("Moku: Burst ready")
        except Exception:
            pass

    def apply_generator_settings(self):
        # Legacy advanced apply retained but redirect to simple apply + burst
        self.apply_all_simple_settings()

    def preview_generator_waveform(self):
        try:
            period = float(self.simple_period_s.get())
            width = float(self.simple_width_s.get())
            high_v = float(self.simple_high_v.get())
            # Moku Pulse baseline is 0 V; keep preview consistent. If legacy field exists, use it.
            try:
                low_v = float(self.simple_low_v.get())
            except Exception:
                low_v = 0.0
            cycles = max(1, int(float(self.simple_cycles.get() or 1)))

            # Build repeated cycles
            t_prev = []
            v_prev = []
            t0 = 0.0
            for _ in range(cycles):
                t_prev.extend([t0, t0, t0 + width, t0 + width])
                v_prev.extend([low_v, high_v, high_v, low_v])
                t0 += period

            self.ax_pmu_gen.clear()
            self.ax_pmu_gen.set_xlabel("t (s)")
            self.ax_pmu_gen.set_ylabel("GEN V (V)")
            self.ax_pmu_gen.plot(t_prev, v_prev, "m-")
            self._annotate_timing(self.ax_pmu_gen, t_prev, v_prev, width=width, period=period, label_prefix="GEN",
                                  extra_delays=[("cycles", cycles)])
            self.canvas_pmu.draw()
            self._sync_time_axes()
        except Exception as exc:
            messagebox.showerror("Generator", str(exc))

    # --- Binary actions ---
    def _binary_send_once(self):
        try:
            if not self.laser:
                messagebox.showwarning("Moku", "Connect Moku first.")
                return
            pat = self.binary_pattern.get().strip()
            bitp = float(self.binary_bitp.get())
            high = float(self.binary_high.get())
            spb = int(float(self.binary_spb.get()))
            import threading
            threading.Thread(target=lambda: self.laser.send_binary_pattern(pat, bitp, high, samples_per_bit=spb, continuous=False), daemon=True).start()
        except Exception as exc:
            messagebox.showerror("Moku", f"Binary error: {exc}")

    def _binary_send_continuous(self):
        try:
            if not self.laser:
                messagebox.showwarning("Moku", "Connect Moku first.")
                return
            pat = self.binary_pattern.get().strip()
            bitp = float(self.binary_bitp.get())
            high = float(self.binary_high.get())
            spb = int(float(self.binary_spb.get()))
            import threading
            threading.Thread(target=lambda: self.laser.send_binary_pattern(pat, bitp, high, samples_per_bit=spb, continuous=True), daemon=True).start()
        except Exception as exc:
            messagebox.showerror("Moku", f"Binary error: {exc}")

    def _binary_stop(self):
        try:
            if self.laser:
                self.laser.stop_all()
        except Exception:
            pass

    def preview_pulse_waveform(self):
        # Alias for UI button: reuse generator preview using simple fields
        try:
            self.preview_generator_waveform()
        except Exception:
            pass

    def fire_laser_pulse(self):
        if not self.laser:
            messagebox.showwarning("Moku", "Connect Moku first.")
            return
        try:
            # Use current definition and burst cycles
            high = float(self.simple_high_v.get())
            width = float(self.simple_width_s.get())
            period = float(self.simple_period_s.get())
            rise = float(self.simple_rise_s.get())
            cycles = int(float(self.simple_cycles.get() or 1))

            import threading
            def _run():
                try:
                    self.laser.run_burst(high, width, period, rise, count=max(1, cycles))
                    self.moku_status.set("Moku: Burst complete")
                except Exception as exc:
                    messagebox.showerror("Moku", f"Burst error: {exc}")

            threading.Thread(target=_run, daemon=True).start()
        except Exception as exc:
            messagebox.showerror("Moku", f"Burst error: {exc}")
    def _moku_start(self):
        if not self.laser:
            messagebox.showwarning("Moku", "Connect Moku first.")
            return
        try:
            mode = self.moku_mode.get()
            high = float(self.simple_high_v.get())
            width = float(self.simple_width_s.get())
            period = float(self.simple_period_s.get())
            rise = float(self.simple_rise_s.get())
            cycles = int(float(self.simple_cycles.get()))
            duration = float(self.simple_duration.get())

            if mode == 'manual':
                self.trigger_simple_now()
                return
            if mode == 'burst':
                threading.Thread(target=lambda: self.laser.safe_run_burst(high, width, period, rise, count=max(1, cycles)), daemon=True).start()
                self.moku_status.set("Moku: Burst running")
            elif mode == 'continuous':
                self._set_gen_output(True)
            elif mode == 'external':
                messagebox.showinfo("Moku", "External trigger arming requires SDK trigger API; not yet implemented.")
            else:
                messagebox.showwarning("Moku", f"Unknown mode: {mode}")
        except Exception as exc:
            messagebox.showerror("Moku", f"Start error: {exc}")

    def _set_gen_output(self, enable: bool):
        try:
            if not self.laser:
                messagebox.showwarning("Moku", "Connect Moku first.")
                return
            if enable:
                period = float(self.simple_period_s.get())
                width = float(self.simple_width_s.get())
                high = float(self.simple_high_v.get())
                rise = float(self.simple_rise_s.get())
                try:
                    self.laser.safe_start_continuous(high, width, period, rise)
                    self.moku_status.set("Moku: Output ON")
                except Exception as exc:
                    messagebox.showerror("Moku", f"Output error: {exc}")
            else:
                try:
                    self.laser.stop_all()
                except Exception:
                    pass
                self.moku_status.set("Moku: Output OFF")
            # Reflect state on toggle button if present
            try:
                self.output_on = bool(enable)
                self._refresh_output_button()
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Moku", f"Output error: {exc}")

    # --- Settings save/load and presets ---
    def _save_moku_settings(self):
        try:
            from tkinter.filedialog import asksaveasfilename
            cfg = {
                'ip': self.gen_addr_var.get(),
                'channel': int(self.gen_channel_var.get()),
                'high_v': float(self.simple_high_v.get()),
                'width_s': float(self.simple_width_s.get()),
                'period_s': float(self.simple_period_s.get()),
                'edge_s': float(self.simple_rise_s.get()),
                'cycles': float(self.simple_cycles.get()),
                'duration_s': float(self.simple_duration.get()),
            }
            path = asksaveasfilename(defaultextension=".json", filetypes=[["JSON","*.json"]], initialfile="moku_pulse_settings.json")
            if not path:
                return
            import json
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
            self.moku_status.set(f"Saved settings: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Moku", f"Save failed: {exc}")

    def _load_moku_settings(self):
        try:
            from tkinter.filedialog import askopenfilename
            path = askopenfilename(filetypes=[["JSON","*.json"]])
            if not path:
                return
            import json
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            self.gen_addr_var.set(cfg.get('ip', self.gen_addr_var.get()))
            self.gen_channel_var.set(cfg.get('channel', int(self.gen_channel_var.get())))
            self.simple_high_v.set(str(cfg.get('high_v', self.simple_high_v.get())))
            self.simple_width_s.set(str(cfg.get('width_s', self.simple_width_s.get())))
            self.simple_period_s.set(str(cfg.get('period_s', self.simple_period_s.get())))
            self.simple_rise_s.set(str(cfg.get('edge_s', self.simple_rise_s.get())))
            self.simple_cycles.set(str(cfg.get('cycles', self.simple_cycles.get())))
            self.simple_duration.set(str(cfg.get('duration_s', self.simple_duration.get())))
            self.moku_status.set(f"Loaded settings: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Moku", f"Load failed: {exc}")

    def _load_exp_preset(self):
        try:
            p = self.exp_preset.get()
            if p == "Write (50ns/200ns, 1.5V)":
                self.simple_high_v.set(str(1.5)); self.simple_width_s.set(str(50e-9)); self.simple_period_s.set(str(200e-9)); self.simple_rise_s.set(str(16e-9))
            elif p == "Read (16ns/200ns, 0.5V)":
                self.simple_high_v.set(str(0.5)); self.simple_width_s.set(str(16e-9)); self.simple_period_s.set(str(200e-9)); self.simple_rise_s.set(str(16e-9))
            elif p == "Endurance (100ns/200ns, 1.0V)":
                self.simple_high_v.set(str(1.0)); self.simple_width_s.set(str(100e-9)); self.simple_period_s.set(str(200e-9)); self.simple_rise_s.set(str(16e-9))
            self.preview_pulse_waveform()
        except Exception:
            pass

    def _maybe_trigger_gen_start(self):
        try:
            if not getattr(self, 'auto_trigger_gen', tk.BooleanVar(value=False)).get():
                return
            if not self.laser:
                return
            # Start continuous output at measurement start
            try:
                self._set_gen_output(True)
            except Exception:
                pass
        except Exception:
            pass

    # --- Simple/apply/output helpers ---
    def apply_all_simple_settings(self):
        # Apply waveform first, then burst, per request
        self.apply_simple_generator_settings()
        self.apply_burst_settings_only()

        # Keep output state unchanged here

    def toggle_output(self):
        try:
            new_state = not getattr(self, 'output_on', False)
            self._set_gen_output(new_state)
        except Exception:
            pass

    def _refresh_output_button(self):
        if getattr(self, 'output_btn', None) is None:
            return
        on = bool(getattr(self, 'output_on', False))
        self.output_btn.config(text=("Output ON" if on else "Output OFF"),
                               bg=("#6cc644" if on else "SystemButtonFace"))

    def _apply_preset(self):
        name = self.preset_var.get()
        try:
            if name == "Short pulse (5us/20us, 1V)":
                self.simple_period_s.set(str(20e-6))
                self.simple_width_s.set(str(5e-6))
                self.simple_high_v.set(str(1.0))
                self.simple_low_v.set(str(0.0))
            elif name == "Mid pulse (50us/200us, 2V)":
                self.simple_period_s.set(str(200e-6))
                self.simple_width_s.set(str(50e-6))
                self.simple_high_v.set(str(2.0))
                self.simple_low_v.set(str(0.0))
            elif name == "Long pulse (1ms/5ms, 3V)":
                self.simple_period_s.set(str(5e-3))
                self.simple_width_s.set(str(1e-3))
                self.simple_high_v.set(str(3.0))
                self.simple_low_v.set(str(0.0))
            # Keep rise/fall/delay as selected; refresh preview
            self.preview_pulse_waveform()
        except Exception:
            pass

    # removed run_burst_once per user request

    # ------- helpers: context/saving/UI -------
    def _run_decay(self):
        if self.pmu is None:
            messagebox.showwarning("PMU", "Connect PMU/SMU first.")
            return
        try:
            bias = float(self.combo_bias.get())
            cap = float(self.combo_cap.get())
            dt = float(self.combo_dt.get())
            t, i = self.service.run_laser_decay(keithley=self.pmu._base, gen=self.gen,
                                                bias_v=bias, capture_time_s=cap, sample_dt_s=dt,
                                                prep_delay_s=0.005, trig_mode="BUS")
            # Plot on Latest Data Preview
            self.ax_data_i.clear(); self.ax_data_v.clear()
            self.ax_data_i.plot(t, i, "-")
            self.ax_data_i.set_xlabel("t (s)"); self.ax_data_i.set_ylabel("I (A)")
            self.canvas_data.draw()

            # Save with metadata (same foldering as PMU)
            meta = self._collect_common_meta()
            meta.update({
                "test_type": "decay",
                "bias_v": bias,
                "capture_time_s": cap,
                "sample_dt_s": dt,
            })
            v_arr = [bias] * len(t)
            self._save_combined_trace("decay", t, v_arr, i, meta)
        except Exception as exc:
            messagebox.showerror("Combined", f"Decay error: {exc}")

    def _run_4bit(self):
        if self.pmu is None:
            messagebox.showwarning("PMU", "Connect PMU/SMU first.")
            return
        try:
            bitp = float(self.combo_bit.get())
            rbit = float(self.combo_relax_bit.get())
            rpat = float(self.combo_relax_pat.get())
            rep = int(float(self.combo_repeats.get()))
            t, i, log = self.service.run_laser_4bit_sequences(keithley=self.pmu._base, gen=self.gen,
                                                              bit_period_s=bitp, relax_between_bits_s=rbit,
                                                              relax_between_patterns_s=rpat,
                                                              repeats=rep, trig_mode="BUS",
                                                              bias_v=0.2, sample_dt_s=0.0005)
            # Plot on Latest Data Preview
            self.ax_data_i.clear(); self.ax_data_v.clear()
            self.ax_data_i.plot(t, i, "-")
            self.ax_data_i.set_xlabel("t (s)"); self.ax_data_i.set_ylabel("I (A)")
            self.canvas_data.draw()

            # Save with metadata
            meta = self._collect_common_meta()
            meta.update({
                "test_type": "4bit_sweep",
                "bit_period_s": bitp,
                "relax_between_bits_s": rbit,
                "relax_between_patterns_s": rpat,
                "repeats": rep,
                "patterns": "0000..1111",
            })
            # Voltage is bias (assume 0.2 V unless customized later)
            v_arr = [float(self.combo_bias.get() or 0.2)] * len(t)
            self._save_combined_trace("4bit", t, v_arr, i, meta)
        except Exception as exc:
            messagebox.showerror("Combined", f"4-bit error: {exc}")

    # --- Experiments panel handlers ---
    def _run_experiment(self):
        try:
            if self.pmu is None:
                messagebox.showwarning("PMU", "Connect PMU/SMU first.")
                return
            if not self.laser:
                messagebox.showwarning("Moku", "Connect Moku first.")
                return
            # Collect params
            bias = float(self.exp_bias.get()); cap = float(self.exp_cap.get()); dt = float(self.exp_dt.get())
            high = float(self.exp_high.get()); width = float(self.exp_width.get()); period = float(self.exp_period.get()); edge = float(self.exp_edge.get())
            repeats = int(float(self.exp_repeats.get() or 1))
            ramp_step = float(self.exp_ramp_step.get() or 0.0)
            ramp_every = max(1, int(float(self.exp_ramp_every.get() or 1)))
            ramp_max = float(self.exp_ramp_max.get() or 3.3)
            cont_sec = float(self.exp_cont.get() or 0.0)

            import threading
            import threading as _th
            self._exp_stop = _th.Event()

            def _loop():
                v_high = high
                try:
                    for k in range(max(1, repeats)):
                        if self._exp_stop.is_set():
                            break
                        # Run one decay capture using current v_high
                        t_arr, i_arr = self.service.run_moku_decay(
                            keithley=self.pmu._base if hasattr(self.pmu, '_base') else self.pmu,
                            laser=self.laser,
                            bias_v=bias,
                            capture_time_s=cap,
                            sample_dt_s=dt,
                            prep_delay_s=0.01,
                            high_v=v_high,
                            width_s=width,
                            period_s=period,
                            edge_s=edge,
                            pulses=1 if float(self.exp_cont.get() or 0.0) == 0.0 else 0,
                            continuous_duration_s=cont_sec,
                        )
                        # Plot to Latest Data Preview
                        try:
                            self.ax_data_i.clear(); self.ax_data_v.clear()
                            self.ax_data_i.plot(t_arr, i_arr, "-")
                            self.ax_data_i.set_xlabel("t (s)"); self.ax_data_i.set_ylabel("I (A)")
                            self.canvas_data.draw()
                        except Exception:
                            pass

                        # Ramping rule
                        if ramp_step and ((k + 1) % ramp_every == 0):
                            v_high = min(ramp_max, v_high + ramp_step)
                except Exception as exc:
                    messagebox.showerror("Experiment", f"Run error: {exc}")

            self._exp_thread = threading.Thread(target=_loop, daemon=True)
            self._exp_thread.start()
        except Exception as exc:
            messagebox.showerror("Experiment", f"Start error: {exc}")

    def _stop_experiment(self):
        try:
            if self._exp_stop:
                self._exp_stop.set()
        except Exception:
            pass

    def _load_experiment_library(self):
        try:
            import json
            from tkinter.filedialog import askopenfilename
            path = askopenfilename(filetypes=[["JSON","*.json"]], initialdir="Equipment_Classes/Moku")
            if not path:
                return
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            names = [item.get('name','') for item in data if isinstance(item, dict)]
            names = [n for n in names if n]
            if not names:
                messagebox.showwarning("Experiments", "No experiment names found in JSON.")
                return
            self.exp_combo['values'] = names
            self.exp_select.set(names[0])
            # Populate fields from first experiment
            first = next((item for item in data if item.get('name') == names[0]), None)
            if first:
                pmu = first.get('pmu', {})
                laser = first.get('laser', {})
                self.exp_bias.set(str(pmu.get('bias_v', self.exp_bias.get())))
                self.exp_cap.set(str(pmu.get('capture_s', self.exp_cap.get())))
                self.exp_dt.set(str(pmu.get('dt_s', self.exp_dt.get())))
                self.exp_high.set(str(laser.get('high_v', self.exp_high.get())))
                self.exp_width.set(str(laser.get('width_s', self.exp_width.get())))
                self.exp_period.set(str(laser.get('period_s', self.exp_period.get())))
                self.exp_edge.set(str(laser.get('edge_s', self.exp_edge.get())))
                self.exp_repeats.set(str(first.get('repeats', self.exp_repeats.get())))
                ramp = first.get('ramp', {})
                self.exp_ramp_step.set(str(ramp.get('step_v', self.exp_ramp_step.get())))
                self.exp_ramp_every.set(str(ramp.get('every', self.exp_ramp_every.get())))
                self.exp_ramp_max.set(str(ramp.get('max_v', self.exp_ramp_max.get())))
                self.exp_cont.set(str(first.get('continuous_duration_s', self.exp_cont.get())))
            self.status_var.set("Loaded experiments library")
        except Exception as exc:
            messagebox.showerror("Experiments", f"Load failed: {exc}")

    def _save_current_experiment_to_library(self):
        try:
            import json
            from tkinter.filedialog import asksaveasfilename
            entry = {
                "name": self.exp_select.get() or "Custom Experiment",
                "type": "decay",
                "pmu_mode": "read_dc",
                "laser_mode": "pulse" if float(self.exp_cont.get() or 0.0) == 0.0 else "dc",
                "pmu": {
                    "bias_v": float(self.exp_bias.get()),
                    "capture_s": float(self.exp_cap.get()),
                    "dt_s": float(self.exp_dt.get())
                },
                "laser": {
                    "high_v": float(self.exp_high.get()),
                    "width_s": float(self.exp_width.get()),
                    "period_s": float(self.exp_period.get()),
                    "edge_s": float(self.exp_edge.get()),
                    "dc_v": float(self.exp_high.get())
                },
                "repeats": int(float(self.exp_repeats.get() or 1)),
                "ramp": {
                    "step_v": float(self.exp_ramp_step.get() or 0.0),
                    "every": int(float(self.exp_ramp_every.get() or 1)),
                    "max_v": float(self.exp_ramp_max.get() or 3.3)
                },
                "continuous_duration_s": float(self.exp_cont.get() or 0.0)
            }
            path = asksaveasfilename(defaultextension=".json", filetypes=[["JSON","*.json"]], initialfile="experiments_custom.json")
            if not path:
                return
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    data.append(entry)
                else:
                    data = [data, entry]
            except Exception:
                data = [entry]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self.status_var.set("Saved current experiment to library")
        except Exception as exc:
            messagebox.showerror("Experiments", f"Save failed: {exc}")

    def _send_trigger_ch2(self):
        try:
            if not self.laser:
                messagebox.showwarning("Moku", "Connect Moku first.")
                return
            # Use wrapper to send a single trigger pulse on CH2
            # Reuse current laser timing for consistency
            high = float(self.simple_high_v.get())
            width = float(self.simple_width_s.get())
            period = float(self.simple_period_s.get())
            edge = float(self.simple_rise_s.get())
            self.laser.safe_send_trigger_pulse_on_ch2(voltage_high=high, pulse_width=width, period=period, edge_time=edge)
            self.moku_status.set("Moku: Trigger sent on CH2")
        except Exception as exc:
            messagebox.showerror("Moku", f"Trigger CH2 error: {exc}")
    def _poll_context(self):
        try:
            if self.provider is not None:
                # Measurement_GUI has sample_name_var and final_device_letter/number
                sn = getattr(self.provider, 'sample_name_var', None)
                name = sn.get().strip() if sn is not None else None
                letter = getattr(self.provider, 'final_device_letter', None)
                number = getattr(self.provider, 'final_device_number', None)
                if name: self.sample_name = name
                if letter and number:
                    self.device_label = f"{letter}{number}"
            self.context_var.set(f"Sample: {self.sample_name}  |  Device: {self.device_label}")
        except Exception:
            pass
        self.after(500, self._poll_context)

    def _ensure_dir(self, path: Path):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _next_index(self, folder: Path) -> int:
        max_idx = -1
        try:
            for p in folder.glob("*.txt"):
                m = re.match(r"(\d+)-", p.name)
                if m:
                    max_idx = max(max_idx, int(m.group(1)))
        except Exception:
            return 0
        return 0 if max_idx < 0 else max_idx + 1

    def _save_pmu_trace(self, t, v, i, mode: str):
        try:
            # Base folder consistent with Measurement_GUI: Data_save_loc/<sample>/<letter>/<number>/PMU measurments
            base = Path("Data_save_loc") / self.sample_name
            dev = self.device_label if self.device_label != "UnknownDevice" else "Unknown"
            if len(dev) >= 2:
                letter, number = dev[0], dev[1:]
            else:
                letter, number = "X", "0"
            folder = base / letter / number / "PMU measurments"
            self._ensure_dir(folder)

            idx = self._next_index(folder)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            name = f"{idx}-{mode.replace(' ', '_')}-{ts}.txt"
            path = folder / name

            import numpy as np
            data = np.column_stack([v if v is not None else [0.0]*len(t), i if i is not None else [0.0]*len(t), t])
            # Keep same header order as many files in Measurement_GUI: Voltage Current Time
            np.savetxt(str(path), data, fmt="%0.6E\t%0.6E\t%0.6E", header="Voltage Current Time", comments="")
            self.status_var.set(f"Saved: {path}")
        except Exception as exc:
            self.status_var.set(f"Save failed: {exc}")

    def _device_save_folder(self) -> Path:
        base = Path("Data_save_loc") / self.sample_name
        dev = self.device_label if self.device_label != "UnknownDevice" else "Unknown"
        if len(dev) >= 2:
            letter, number = dev[0], dev[1:]
        else:
            letter, number = "X", "0"
        folder = base / letter / number / "PMU measurments"
        self._ensure_dir(folder)
        return folder

    def _collect_common_meta(self) -> dict:
        meta = {
            "timestamp": datetime.now().isoformat(),
            "sample": self.sample_name,
            "device": self.device_label,
            "pmu_address": self.addr_var.get(),
        }
        try:
            meta.update({
                "gen_resource": self.gen_addr_var.get(),
                "gen_wave": self.gen_wave.get(),
                "gen_amp_vpp": float(self.gen_amp.get()),
                "gen_offset_v": float(self.gen_offset.get()),
                "gen_freq_hz": float(self.gen_freq.get()),
                "gen_duty_pct": float(self.gen_duty.get()),
                "gen_cycles": float(self.gen_cycles.get()),
                "gen_trig_src": self.gen_trig_src.get(),
            })
        except Exception:
            pass
        return meta

    def _save_combined_trace(self, tag: str, t: list, v: list, i: list, meta: dict):
        try:
            folder = self._device_save_folder()
            idx = self._next_index(folder)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            base = f"{idx}-{tag}-{ts}"
            txt_path = folder / f"{base}.txt"
            json_path = folder / f"{base}.json"
            png_path = folder / f"{base}_plot.png"

            # Save data (Voltage Current Time)
            import numpy as np
            data = np.column_stack([v if v is not None else [0.0]*len(t), i if i is not None else [0.0]*len(t), t])
            np.savetxt(str(txt_path), data, fmt="%0.6E\t%0.6E\t%0.6E", header="Voltage Current Time", comments="")

            # Save metadata JSON
            try:
                import json
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, indent=2)
            except Exception:
                pass

            # Save plot image (latest data preview figure)
            try:
                self.fig_data.tight_layout()
                self.fig_data.savefig(str(png_path), dpi=200)
            except Exception:
                pass

            # Append to per-device log
            try:
                log_path = folder / "combined_log.txt"
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(f"{meta.get('timestamp','')}, {meta.get('test_type', tag)}, file={base}\n")
            except Exception:
                pass

            self.status_var.set(f"Saved: {txt_path}")
        except Exception as exc:
            self.status_var.set(f"Save failed: {exc}")

    def _update_enabled_controls(self):
        mode = self.mode_var.get()
        widgets = {
            'amp': self._entry_for(self.amp_v),
            'base': self._entry_for(self.base_v),
            'width': self._entry_for(self.width_s),
            'period': self._entry_for(self.period_s),
            'num': self._entry_for(self.num_pulses),
            'pattern': self._entry_for(self.pattern),
            'step': self._entry_for(self.step_v),
            'stop': self._entry_for(self.stop_v),
        }
        # default disable all then enable needed
        for w in widgets.values():
            try: w.config(state='disabled')
            except Exception: pass

        def ena(keys):
            for k in keys:
                try: widgets[k].config(state='normal')
                except Exception: pass

        if mode == 'Pulse Train':
            ena(['amp','base','width','period','num'])
        elif mode == 'Pulse Pattern':
            ena(['amp','base','width','period','pattern'])
        elif mode == 'Amplitude Sweep':
            ena(['base','width','period','step','stop'])
        elif mode == 'Width Sweep':
            ena(['amp','base','width','period','num'])  # width used as start; num as count
        elif mode == 'Transient':
            ena(['amp','base','width','period'])
        elif mode == 'Endurance':
            ena(['amp','width','period','num'])  # num = cycles

    def _entry_for(self, var: tk.StringVar):
        # Return the associated Entry widget created for this var
        # Assumes var has a single Entry in same parent
        for child in self.children.values():
            pass
        # Simpler: walk our control frame
        try:
            parent = self.children.get('!labelframe')  # first labelframe (Controls)
            if parent is not None:
                for w in parent.winfo_children():
                    if isinstance(w, tk.Entry) and str(var) in str(w.cget('textvariable')):
                        return w
        except Exception:
            pass
        return tk.Entry(self)

    def _fmt_time(self, seconds: float) -> str:
        s = float(seconds)
        if s >= 1.0:
            return f"{s:.3f} s"
        if s >= 1e-3:
            return f"{s*1e3:.3f} ms"
        if s >= 1e-6:
            return f"{s*1e6:.3f} µs"
        return f"{s*1e9:.3f} ns"

    def _annotate_timing(self, ax, t_arr, v_arr, *, width: float, period: float, label_prefix: str, extra_delays=None):
        try:
            if not t_arr:
                return
            t0 = t_arr[0]
            # Width label at middle of first pulse
            ax.axvline(t0, color="#888", linestyle=":", linewidth=0.8)
            ax.axvline(t0 + width, color="#888", linestyle=":", linewidth=0.8)
            ymin = min(v_arr) if v_arr else 0.0
            ymax = max(v_arr) if v_arr else 1.0
            pad = max(1e-12, (ymax - ymin) * 0.1 or 0.1)
            ax.set_ylim(ymin - pad, ymax + pad)
            ax.annotate(f"{label_prefix} width = {self._fmt_time(width)}",
                        xy=(t0 + width/2, ymax + pad*0.5),
                        xytext=(0, 0), textcoords='offset points', ha='center', va='bottom', color="#444")
            # Period label between pulses
            ax.axvline(t0 + period, color="#bbb", linestyle=":", linewidth=0.8)
            ax.annotate(f"period = {self._fmt_time(period)}",
                        xy=(t0 + period/2, ymin - pad*0.5),
                        xytext=(0, 0), textcoords='offset points', ha='center', va='top', color="#666")
            # Extra delays
            if extra_delays:
                x = t0 + period
                y = ymax + pad*0.8
                for name, val in extra_delays:
                    ax.annotate(f"{name} = {self._fmt_time(val)}", xy=(x, y), xytext=(0, 0),
                                textcoords='offset points', ha='center', va='bottom', color="#884488")
                    y += pad*0.3
        except Exception:
            pass

    def _sync_time_axes(self):
        try:
            if not self.sync_time.get():
                return
            # Get current xlims and apply union across PMU and GEN previews
            pmu_xlim = self.ax_pmu_v.get_xlim()
            gen_xlim = self.ax_pmu_gen.get_xlim()
            x0 = min(pmu_xlim[0], gen_xlim[0])
            x1 = max(pmu_xlim[1], gen_xlim[1])
            self.ax_pmu_v.set_xlim(x0, x1)
            self.ax_pmu_gen.set_xlim(x0, x1)
            self.canvas_pmu.draw()
        except Exception:
            pass

    def _update_gen_controls(self):
        """Enable/disable generator fields depending on waveform type."""
        try:
            wv = self.gen_wave.get().upper()
            # Collect widget entries for quick toggle
            widgets = {
                'amp': self._entry_for(self.gen_amp),
                'offset': self._entry_for(self.gen_offset),
                'freq': self._entry_for(self.gen_freq),
                'duty': self._entry_for(self.gen_duty),
                'phase': self._entry_for(self.gen_phase),
                'load': self._entry_for(self.gen_load),
            }
            # Default disable
            for w in widgets.values():
                try: w.config(state='disabled')
                except Exception: pass
            # Enable per-type
            if wv == 'DC':
                # DC: Offset sets level; frequency/amplitude/duty/phase not applicable
                for k in ('offset','load'):
                    try: widgets[k].config(state='normal')
                    except Exception: pass
            elif wv == 'SINE':
                # SINE: amplitude, offset, freq, phase, load
                for k in ('amp','offset','freq','phase','load'):
                    try: widgets[k].config(state='normal')
                    except Exception: pass
            elif wv in ('SQUARE','PULSE'):
                # SQUARE/PULSE: includes duty
                for k in ('amp','offset','freq','duty','phase','load'):
                    try: widgets[k].config(state='normal')
                    except Exception: pass
            elif wv == 'RAMP':
                # RAMP: some units support duty as symmetry; we leave it disabled to avoid confusion
                for k in ('amp','offset','freq','phase','load'):
                    try: widgets[k].config(state='normal')
                    except Exception: pass
            # Also toggle burst-related fields: cycles only matters in NCYC; INT period only when INT trigger
            try:
                cycles_entry = self._entry_for(self.gen_cycles)
                int_per_entry = self._entry_for(self.gen_int_period)
                trig_src = self.gen_trig_src.get().upper()
                mode = self.gen_burst_mode.get().upper()
                cycles_entry.config(state='normal' if mode == 'NCYC' else 'disabled')
                int_per_entry.config(state='normal' if trig_src == 'INT' else 'disabled')
            except Exception:
                pass
        except Exception:
            pass

    def _toggle_advanced(self, show: bool = None):
        try:
            if show is None:
                show = bool(self.show_advanced.get())
        except Exception:
            show = False
        try:
            for frm in getattr(self, '_adv_frames', []):
                try:
                    if show:
                        frm.grid()
                    else:
                        frm.grid_remove()
                except Exception:
                    pass
        except Exception:
            pass


