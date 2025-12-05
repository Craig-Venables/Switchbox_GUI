import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.gridspec as gridspec

class OscilloscopePulseLayout:
    """
    Handles the creation and layout of GUI elements for the Oscilloscope Pulse Capture tool.
    Separates view construction from controller logic.
    """
    
    def __init__(self, parent, callbacks, config, context=None):
        self.parent = parent
        self.callbacks = callbacks
        self.config = config
        self.context = context or {} # {device_label, sample_name, is_standalone, known_systems}
        
        self.vars = {} # Store Tk vars here
        self.widgets = {} # Store widget references
        
        self._setup_styles()
        self._build_layout()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Colors
        bg_color = "#f0f0f0"
        accent_color = "#e6f3ff" # Light blue hint
        header_color = "#1565c0"
        
        # Frame Styles
        style.configure("TFrame", background=bg_color)
        style.configure("TLabelframe", background=bg_color)
        style.configure("TLabelframe.Label", background=bg_color, font=("Segoe UI", 10, "bold"), foreground=header_color)
        
        # Label Styles
        style.configure("TLabel", background=bg_color, font=("Segoe UI", 9))
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"), foreground=header_color, background=accent_color)
        style.configure("Info.TLabel", font=("Segoe UI", 9), foreground="#555", background=accent_color)
        style.configure("Status.TLabel", font=("Segoe UI", 9), foreground="#333333", background=bg_color)
        
        # Button Styles
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Stop.TButton", font=("Segoe UI", 10, "bold"), foreground="red")
        style.configure("Small.TButton", font=("Segoe UI", 8))
        
        # Checkbutton
        style.configure("TCheckbutton", background=bg_color, font=("Segoe UI", 9))
        
        self.parent.configure(bg=bg_color)

    def _build_layout(self):
        # Top Control Bar (New)
        self._build_top_bar(self.parent)
        
        # Main Content Grid
        content_frame = ttk.Frame(self.parent)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # --- LEFT PANEL (Controls) ---
        left_panel = ttk.Frame(content_frame, padding=5)
        left_panel.grid(row=0, column=0, sticky="nsew")
        
        self._build_connection_frame(left_panel)
        self._build_pulse_frame(left_panel)
        self._build_scope_frame(left_panel)
        self._build_measurement_frame(left_panel)
        self._build_action_buttons(left_panel)
        self._build_status_bar(left_panel)

        # --- RIGHT PANEL (Visualization) ---
        right_panel = ttk.Frame(content_frame)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=5)
        self._build_plots(right_panel)

    def _build_top_bar(self, parent):
        """Top banner with System selection, Save path, and Identity info."""
        bar_frame = tk.Frame(parent, bg="#e6f3ff", pady=8, padx=10, relief="raised", bd=1)
        bar_frame.pack(fill="x", side="top")
        
        # Left: Identity
        id_text = f"Device: {self.context.get('device_label', 'Unknown')} | Sample: {self.context.get('sample_name', 'Unknown')}"
        ttk.Label(bar_frame, text=id_text, style="Header.TLabel").pack(side="left", padx=(0, 20))
        
        # Middle: System Selector
        tk.Label(bar_frame, text="System:", bg="#e6f3ff").pack(side="left")
        self.vars['system'] = tk.StringVar(value=self.config.get("system", "keithley4200a"))
        sys_combo = ttk.Combobox(bar_frame, textvariable=self.vars['system'], 
                                values=self.context.get('known_systems', ["keithley4200a", "keithley2450"]), 
                                width=15, state="readonly")
        sys_combo.pack(side="left", padx=5)
        sys_combo.bind("<<ComboboxSelected>>", lambda e: self.callbacks.get('on_system_change', lambda: None)())
        
        # Right: Help & Save
        tk.Button(bar_frame, text="Help / Guide", command=self._show_help, bg="#1565c0", fg="white", font=("Segoe UI", 9, "bold")).pack(side="right", padx=10)
        
        tk.Button(bar_frame, text="Save Location...", command=self.callbacks['browse_save'], font=("Segoe UI", 8)).pack(side="right", padx=5)
        self.vars['save_dir'] = tk.StringVar(value=self.context.get('save_directory', "Default"))
        tk.Label(bar_frame, textvariable=self.vars['save_dir'], bg="#e6f3ff", fg="#555", width=30, anchor="e").pack(side="right")

    def _show_help(self):
        """Display a help window with setup instructions."""
        help_win = tk.Toplevel(self.parent)
        help_win.title("Setup Guide & Instructions")
        help_win.geometry("800x700")
        help_win.configure(bg="#f0f0f0")
        
        # Scrollable Content
        canvas = tk.Canvas(help_win, bg="#f0f0f0")
        scrollbar = ttk.Scrollbar(help_win, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # --- CONTENT ---
        pad = {'padx': 20, 'pady': 10, 'anchor': 'w'}  # Changed sticky to anchor for pack()
        
        # Title
        tk.Label(scrollable_frame, text="Oscilloscope Pulse Capture Guide", font=("Segoe UI", 16, "bold"), bg="#f0f0f0", fg="#1565c0").pack(**pad)
        
        # 1. Overview
        tk.Label(scrollable_frame, text="1. Overview", font=("Segoe UI", 12, "bold"), bg="#f0f0f0").pack(**pad)
        tk.Label(scrollable_frame, text="This tool generates a voltage pulse using the SMU and captures the transient current response using an Oscilloscope.\nIt is designed for capturing fast transients that standard SMUs cannot resolve.", justify="left", bg="#f0f0f0").pack(**pad)
        
        # 2. Measurement Methods
        tk.Label(scrollable_frame, text="2. Setup & Wiring Modes", font=("Segoe UI", 12, "bold"), bg="#f0f0f0").pack(**pad)
        
        # Method A: Shunt
        f_shunt = tk.LabelFrame(scrollable_frame, text="Method A: Shunt Resistor (Recommended for Fast Pulses)", bg="#f0f0f0", font=("Segoe UI", 10, "bold"))
        f_shunt.pack(fill="x", **pad)
        
        shunt_txt = (
            "• Best for: Fast switching (<1ms), high bandwidth.\n"
            "• How it works: Measures voltage drop across a known resistor.\n\n"
            "WIRING:\n"
            "   [SMU Hi] ----> [Shunt Resistor] ----+---- [DUT] ----> [SMU Lo]\n"
            "                                       |\n"
            "   [Scope CH1] ------------------------+\n"
            "   [Scope GND] ------------------------+ (at Shunt-DUT junction? No, across Shunt!)\n\n"
            "   CORRECT WIRING (Shunt on Low Side is safer for Scope GND):\n"
            "   [SMU Hi] -----------------> [DUT] ----+---- [Shunt] ----> [SMU Lo]\n"
            "                                        |\n"
            "   [Scope CH1] -------------------------+\n"
            "   [Scope GND] --------------------------------------------+ (SMU Lo)\n\n"
            "   * Ensure Scope Ground is shared with SMU Lo/Ground."
        )
        tk.Label(f_shunt, text=shunt_txt, justify="left", bg="#f0f0f0", font=("Consolas", 9)).pack(padx=10, pady=5)
        
        # Method B: SMU
        f_smu = tk.LabelFrame(scrollable_frame, text="Method B: SMU Current (Slower)", bg="#f0f0f0", font=("Segoe UI", 10, "bold"))
        f_smu.pack(fill="x", **pad)
        
        smu_txt = (
            "• Best for: Slow pulses (>10ms), DC accuracy.\n"
            "• How it works: Uses the SMU's internal measurement.\n"
            "• Wiring: Standard direct connection. Scope is NOT used for current, only Voltage monitoring if attached."
        )
        tk.Label(f_smu, text=smu_txt, justify="left", bg="#f0f0f0").pack(padx=10, pady=5)
        
        # 3. Parameters
        tk.Label(scrollable_frame, text="3. Parameters Explained", font=("Segoe UI", 12, "bold"), bg="#f0f0f0").pack(**pad)
        
        params_txt = (
            "• Pulse Voltage: Amplitude of the pulse.\n"
            "• Duration: Width of the pulse.\n"
            "• Compliance: Current limit for the SMU (safety).\n"
            "• Pre-Pulse Delay: Time to wait at 0V before pulsing (to arm scope).\n"
            "• R_shunt: Value of shunt resistor used in Method A. Crucial for accurate Current calc (I = V_scope / R)."
        )
        tk.Label(scrollable_frame, text=params_txt, justify="left", bg="#f0f0f0").pack(**pad)
        
        # 4. Low Current Measurements (nA/µA)
        tk.Label(scrollable_frame, text="4. Low Current Measurements (nA/µA Range)", font=("Segoe UI", 12, "bold"), bg="#f0f0f0", fg="#d32f2f").pack(**pad)
        
        f_lowcurrent = tk.LabelFrame(scrollable_frame, text="⚠️ IMPORTANT: Shunt Method NOT Suitable for nA/µA", bg="#fff3cd", font=("Segoe UI", 10, "bold"), fg="#d32f2f")
        f_lowcurrent.pack(fill="x", **pad)
        
        lowcurrent_txt = (
            "Problem: For 1 µA through 10Ω shunt → only 10 µV signal (too small for scope!)\n"
            "         For 1 nA through 1kΩ shunt → only 1 µV signal (impossible to measure)\n\n"
            "SOLUTION: Use a Transimpedance Amplifier (TIA)\n\n"
            "What is a TIA?\n"
            "• Converts tiny currents (nA/µA) into measurable voltages (mV/V)\n"
            "• Has high bandwidth (MHz range) - perfect for fast measurements\n"
            "• Gain = R_feedback (typically 10kΩ to 10MΩ)\n\n"
            "Example: 1 µA × 1MΩ TIA = 1V output (easily measured by scope!)"
        )
        tk.Label(f_lowcurrent, text=lowcurrent_txt, justify="left", bg="#fff3cd", font=("Segoe UI", 9)).pack(padx=10, pady=5)
        
        # TIA Options
        tk.Label(scrollable_frame, text="TIA Options for Low-Current Fast Measurements:", font=("Segoe UI", 11, "bold"), bg="#f0f0f0").pack(**pad)
        
        # Option 1: Commercial
        f_commercial = tk.LabelFrame(scrollable_frame, text="Option 1: Commercial TIA (Easiest)", bg="#f0f0f0", font=("Segoe UI", 10, "bold"))
        f_commercial.pack(fill="x", **pad)
        commercial_txt = (
            "• FEMTO DLPCA-200: 10 MHz bandwidth, 10³ to 10⁹ V/A gain\n"
            "• FEMTO HCA series: High-speed current amplifiers\n"
            "• Cost: $1000-$3000\n"
            "✅ Plug-and-play, calibrated, professional"
        )
        tk.Label(f_commercial, text=commercial_txt, justify="left", bg="#f0f0f0").pack(padx=10, pady=5)
        
        # Option 2: DIY
        f_diy = tk.LabelFrame(scrollable_frame, text="Option 2: DIY TIA (Budget)", bg="#f0f0f0", font=("Segoe UI", 10, "bold"))
        f_diy.pack(fill="x", **pad)
        diy_txt = (
            "• Build with op-amp (OPA657, AD8015)\n"
            "• Feedback resistor: 100kΩ to 10MΩ\n"
            "• Example: 1 µA × 1MΩ = 1V (easily measured!)\n"
            "• Cost: $20-50 in parts\n"
            "⚠️ Requires PCB design, careful layout for low noise\n\n"
            "Basic Circuit:\n"
            "   Device → [Op-Amp +Input]\n"
            "            [R_feedback between - and output]\n"
            "            [Output] → Scope\n"
            "   Ground → [Op-Amp -Input]"
        )
        tk.Label(f_diy, text=diy_txt, justify="left", bg="#f0f0f0", font=("Consolas", 8)).pack(padx=10, pady=5)
        
        # Option 3: PMU
        f_pmu = tk.LabelFrame(scrollable_frame, text="Option 3: Keithley 4200A PMU Module", bg="#f0f0f0", font=("Segoe UI", 10, "bold"))
        f_pmu.pack(fill="x", **pad)
        pmu_txt = (
            "• 4225-PMU module has built-in fast current measurement\n"
            "• Bandwidth: 200 MHz\n"
            "• Range: 100 pA to 1 A\n"
            "✅ Best of both worlds (fast + sensitive)\n"
            "❌ Expensive module (~$15k)"
        )
        tk.Label(f_pmu, text=pmu_txt, justify="left", bg="#f0f0f0").pack(padx=10, pady=5)
        
        # Recommended Resistor Values
        tk.Label(scrollable_frame, text="5. Choosing Shunt Resistor (for mA+ currents)", font=("Segoe UI", 12, "bold"), bg="#f0f0f0").pack(**pad)
        
        resistor_txt = (
            "For mA-range currents (where shunt method works):\n\n"
            "Current Range → Recommended R_shunt → Voltage Drop\n"
            "• 1 mA:  10Ω to 100Ω  → 10mV to 100mV\n"
            "• 10 mA: 1Ω to 10Ω    → 10mV to 100mV\n"
            "• 100 mA: 0.1Ω to 1Ω  → 10mV to 100mV\n\n"
            "Tips:\n"
            "• Use 1% tolerance or better (metal film)\n"
            "• Power rating: P = I² × R (use 0.5W or 1W for safety)\n"
            "• Measure actual resistance with multimeter for accuracy\n"
            "• General purpose: 10Ω, 1%, 0.5W is a good starting point"
        )
        tk.Label(scrollable_frame, text=resistor_txt, justify="left", bg="#f0f0f0", font=("Consolas", 9)).pack(**pad)


    def _build_connection_frame(self, parent):
        """Build connection settings frame"""
        frame = ttk.Labelframe(parent, text="Connections", padding=10)
        frame.pack(fill="x", pady=5)
        
        # SMU Address
        smu_frame = ttk.Frame(frame)
        smu_frame.pack(fill="x", pady=2)
        ttk.Label(smu_frame, text="SMU Address:").pack(side="left")
        self.vars['smu_address'] = tk.StringVar(value=self.config.get("smu_address", "GPIB0::17::INSTR"))
        smu_combo = ttk.Combobox(smu_frame, textvariable=self.vars['smu_address'], 
                                values=self.context.get('smu_ports', ["GPIB0::17::INSTR"]), 
                                width=20)
        smu_combo.pack(side="right")
        self.widgets['smu_combo'] = smu_combo
        
        # Scope Address
        scope_frame = ttk.Frame(frame)
        scope_frame.pack(fill="x", pady=2)
        ttk.Label(scope_frame, text="Scope Address:").pack(side="left")
        self.vars['scope_address'] = tk.StringVar(value=self.config.get("scope_address", ""))
        scope_combo = ttk.Combobox(scope_frame, textvariable=self.vars['scope_address'], 
                                   values=self.context.get('scope_ports', []), 
                                   width=20)
        scope_combo.pack(side="right")
        refresh_btn = ttk.Button(scope_frame, text="Refresh", 
                                command=self.callbacks.get('refresh_scopes', lambda: None),
                                style="Small.TButton")
        refresh_btn.pack(side="right", padx=5)
        self.widgets['scope_combo'] = scope_combo
        
        # Connection buttons and status
        conn_btn_frame = ttk.Frame(frame)
        conn_btn_frame.pack(fill="x", pady=(10, 0))
        
        self.widgets['connect_smu_btn'] = ttk.Button(conn_btn_frame, text="🔌 Connect SMU", 
                                                     command=self.callbacks.get('connect_smu', lambda: None),
                                                     style="Action.TButton")
        self.widgets['connect_smu_btn'].pack(side="left", padx=5)
        
        # SMU Connection status
        self.vars['smu_status'] = tk.StringVar(value="SMU: Not Connected")
        smu_status_label = ttk.Label(conn_btn_frame, textvariable=self.vars['smu_status'], 
                                     style="Status.TLabel", foreground="red")
        smu_status_label.pack(side="left", padx=10)
        self.widgets['smu_status_label'] = smu_status_label

    def _build_pulse_frame(self, parent):
        """Build pulse parameters frame"""
        frame = ttk.Labelframe(parent, text="Pulse Parameters", padding=10)
        frame.pack(fill="x", pady=5)
        
        self._add_param(frame, "Pulse Voltage (V):", "pulse_voltage", "1.0", 
                       ToolTipText="Amplitude of the pulse")
        self._add_param(frame, "Pulse Duration (s):", "pulse_duration", "0.001",
                       ToolTipText="Width of the pulse")
        self._add_param(frame, "Pre-Pulse Delay (s):", "pre_pulse_delay", "0.1",
                       ToolTipText="Time to wait at 0V before pulsing (to arm scope)")
        self._add_param(frame, "Current Compliance (A):", "current_compliance", "0.001",
                       ToolTipText="Current limit for the SMU (safety)")

    def _build_scope_frame(self, parent):
        """Build oscilloscope settings frame"""
        frame = ttk.Labelframe(parent, text="Oscilloscope Settings", padding=10)
        frame.pack(fill="x", pady=5)
        
        # Auto-configure checkbox
        auto_config_frame = ttk.Frame(frame)
        auto_config_frame.pack(fill="x", pady=(0, 5))
        self.vars['auto_configure_scope'] = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            auto_config_frame, 
            text="Auto-configure scope (trigger, timebase, voltage scale)",
            variable=self.vars['auto_configure_scope']
        ).pack(side="left")
        
        # Read scope settings button
        ttk.Button(
            auto_config_frame,
            text="📖 Read Current Scope Settings",
            command=self._read_scope_settings,
            width=25
        ).pack(side="right", padx=(5, 0))
        
        # Scope Type (for connection)
        scope_type_frame = ttk.Frame(frame)
        scope_type_frame.pack(fill="x", pady=2)
        ttk.Label(scope_type_frame, text="Scope Type:").pack(side="left")
        self.vars['scope_type'] = tk.StringVar(value=self.config.get("scope_type", "Tektronix TBS1000C"))
        scope_type_combo = ttk.Combobox(scope_type_frame, textvariable=self.vars['scope_type'], 
                                       values=["Tektronix TBS1000C", "GW Instek GDS-2062", "Auto-Detect"], 
                                       width=20, state="readonly")
        scope_type_combo.pack(side="right")
        self.widgets['scope_type_combo'] = scope_type_combo
        
        scope_type_combo.pack(side="right")
        self.widgets['scope_type_combo'] = scope_type_combo
        
        self._add_param(frame, "Channel:", "scope_channel", "CH1", 
                       options=["CH1", "CH2", "CH3", "CH4"],
                       ToolTipText="Oscilloscope channel to use")
        
        # Record Length / Points
        self._add_param(frame, "Points (k):", "record_length", "20",
                       options=["2.5", "20"],
                       ToolTipText="Record length (thousands of points). Select '20' for high resolution.")
                       
        self._add_param(frame, "Timebase (s/div):", "scope_timebase", "0.0001",
                       ToolTipText="Oscilloscope timebase setting")
        self._add_param(frame, "Voltage Scale (V/div):", "scope_vscale", "0.1",
                       ToolTipText="Oscilloscope voltage scale")

    def _build_measurement_frame(self, parent):
        """Build measurement method frame"""
        frame = ttk.Labelframe(parent, text="Measurement Method", padding=10)
        frame.pack(fill="x", pady=5)
        
        self.vars['measurement_method'] = tk.StringVar(value=self.config.get("measurement_method", "shunt"))
        method_frame = ttk.Frame(frame)
        method_frame.pack(fill="x", pady=2)
        ttk.Label(method_frame, text="Method:").pack(side="left")
        ttk.Radiobutton(method_frame, text="Shunt Resistor", variable=self.vars['measurement_method'], 
                       value="shunt").pack(side="left", padx=10)
        ttk.Radiobutton(method_frame, text="SMU Current", variable=self.vars['measurement_method'], 
                       value="smu").pack(side="left", padx=10)
        
        self._add_param(frame, "R_shunt (Ω):", "r_shunt", "1.0",
                       ToolTipText="Value of shunt resistor (for Method A)")
        
        # Simulation mode checkbox
        sim_frame = ttk.Frame(frame)
        sim_frame.pack(fill="x", pady=(10, 0))
        self.vars['simulation_mode'] = tk.BooleanVar(value=self.config.get("simulation_mode", False))
        sim_check = ttk.Checkbutton(sim_frame, text="🔧 Simulation Mode (no scope required)", 
                                    variable=self.vars['simulation_mode'])
        sim_check.pack(side="left")
        ToolTip(sim_check, "Test without oscilloscope - generates simulated data")

        
        # Shunt Calculator Section
        calc_frame = tk.LabelFrame(frame, text="📐 Shunt Resistor Calculator", bg="#e8f5e9", 
                                   font=("Segoe UI", 9, "bold"), fg="#2e7d32", padx=10, pady=8)
        calc_frame.pack(fill="x", pady=(10, 0))
        
        # Input row
        input_row = ttk.Frame(calc_frame)
        input_row.pack(fill="x", pady=2)
        
        ttk.Label(input_row, text="Test Voltage (V):", background="#e8f5e9").pack(side="left")
        self.vars['calc_voltage'] = tk.StringVar(value="2.0")
        calc_v_entry = ttk.Entry(input_row, textvariable=self.vars['calc_voltage'], width=8)
        calc_v_entry.pack(side="left", padx=5)
        
        ttk.Label(input_row, text="Expected Current (A):", background="#e8f5e9").pack(side="left", padx=(10, 0))
        self.vars['calc_current'] = tk.StringVar(value="0.000001")
        calc_i_entry = ttk.Entry(input_row, textvariable=self.vars['calc_current'], width=12)
        calc_i_entry.pack(side="left", padx=5)
        
        tk.Button(input_row, text="Calculate", command=self._calculate_shunt,
                 bg="#4caf50", fg="white", font=("Segoe UI", 8, "bold"), 
                 relief=tk.FLAT, padx=10, pady=2).pack(side="left", padx=5)
        
        # Quick Test button
        quick_test_btn = tk.Button(input_row, text="⚡ Quick Test", 
                                   command=self._quick_test_device,
                                   bg="#ff9800", fg="white", font=("Segoe UI", 8, "bold"),
                                   relief=tk.FLAT, padx=10, pady=2)
        quick_test_btn.pack(side="left", padx=5)
        ToolTip(quick_test_btn, "Pulse device at test voltage and measure current")
        
        # Results display with wrapping
        results_frame = ttk.Frame(calc_frame)
        results_frame.pack(fill="x", pady=(5, 0))
        
        self.vars['calc_result'] = tk.StringVar(value="Enter values and click Calculate (or Quick Test)")
        result_label = tk.Label(results_frame, textvariable=self.vars['calc_result'], 
                               bg="#e8f5e9", fg="#1b5e20", font=("Consolas", 8), 
                               justify="left", anchor="w", wraplength=400)
        result_label.pack(fill="x")
        
        # Auto-calculate on Enter key
        calc_v_entry.bind("<Return>", lambda e: self._calculate_shunt())
        calc_i_entry.bind("<Return>", lambda e: self._calculate_shunt())


    def _build_action_buttons(self, parent):
        """Build action buttons frame"""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill="x", pady=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x")
        
        self.widgets['run_btn'] = ttk.Button(btn_frame, text="▶ Start Measurement", 
                                             command=self.callbacks.get('start', lambda: None),
                                             style="Action.TButton")
        self.widgets['run_btn'].pack(side="left", padx=5, fill="x", expand=True)
        
        self.widgets['stop_btn'] = ttk.Button(btn_frame, text="⏹ Stop", 
                                             command=self.callbacks.get('stop', lambda: None),
                                             style="Stop.TButton", state="disabled")
        self.widgets['stop_btn'].pack(side="left", padx=5, fill="x", expand=True)
        
        save_btn = ttk.Button(btn_frame, text="💾 Save", 
                             command=self.callbacks.get('save', lambda: None),
                             style="Action.TButton")
        save_btn.pack(side="left", padx=5, fill="x", expand=True)

    def _build_status_bar(self, parent):
        """Build status bar"""
        frame = ttk.Frame(parent, padding=5)
        frame.pack(fill="x", pady=5)
        
        self.vars['status'] = tk.StringVar(value="Ready")
        status_label = ttk.Label(frame, textvariable=self.vars['status'], style="Status.TLabel")
        status_label.pack(side="left")

    def _build_plots(self, parent):
        """Build matplotlib plots"""
        # Create figure with subplots
        self.fig = plt.Figure(figsize=(10, 8), dpi=100)
        gs = gridspec.GridSpec(3, 1, height_ratios=[1, 1, 1], hspace=0.3)
        
        # Voltage plot
        self.ax_voltage = self.fig.add_subplot(gs[0])
        self.ax_voltage.set_ylabel("Voltage (V)")
        self.ax_voltage.set_title("Voltage Waveform", fontsize=10)
        self.ax_voltage.grid(True, alpha=0.3)
        
        # Current plot
        self.ax_current = self.fig.add_subplot(gs[1])
        self.ax_current.set_ylabel("Current (A)")
        self.ax_current.set_title("Current Waveform", fontsize=10)
        self.ax_current.grid(True, alpha=0.3)
        
        # Zoom plot (dual axis)
        self.ax_zoom = self.fig.add_subplot(gs[2])
        self.ax_zoom.set_xlabel("Time (s)")
        self.ax_zoom.set_title("Pulse Zoom View", fontsize=10)
        self.ax_zoom.set_ylabel("Voltage (V)", color='b')
        self.ax_zoom.tick_params(axis='y', labelcolor='b')
        self.ax_zoom.grid(True, alpha=0.3)
        
        # Dual y-axis for current in zoom
        self.ax_zoom_r = self.ax_zoom.twinx()
        self.ax_zoom_r.set_ylabel("Current (A)", color='r')
        self.ax_zoom_r.tick_params(axis='y', labelcolor='r')
        
        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Toolbar
        toolbar = NavigationToolbar2Tk(self.canvas, parent)
        toolbar.update()
    
    def _calculate_shunt(self):
        """Calculate recommended shunt resistor values based on device parameters"""
        try:
            # Get inputs
            voltage = float(self.vars['calc_voltage'].get())
            current = float(self.vars['calc_current'].get())
            
            if current == 0:
                self.vars['calc_result'].set("⚠️ Error: Current cannot be zero")
                return
            
            # Calculate device resistance
            r_device = voltage / current
            
            # Calculate recommended shunt values
            r_shunt_10pct = r_device * 0.10
            r_shunt_1pct = r_device * 0.01
            
            # Calculate voltage drops across shunts
            v_drop_10pct = current * r_shunt_10pct
            v_drop_1pct = current * r_shunt_1pct
            
            # Format current for display
            if abs(current) >= 1e-3:
                i_str = f"{current*1e3:.3f} mA"
            elif abs(current) >= 1e-6:
                i_str = f"{current*1e6:.3f} µA"
            elif abs(current) >= 1e-9:
                i_str = f"{current*1e9:.3f} nA"
            else:
                i_str = f"{current:.3e} A"
            
            # Format resistance for display
            if r_device >= 1e6:
                r_str = f"{r_device/1e6:.2f} MΩ"
            elif r_device >= 1e3:
                r_str = f"{r_device/1e3:.2f} kΩ"
            else:
                r_str = f"{r_device:.2f} Ω"
            
            # Build result string
            result = (
                f"Device: {r_str} @ {voltage}V ({i_str})\\n"
                f"\\n"
                f"10% Rule: R_shunt = {r_shunt_10pct:.2f} Ω  →  {v_drop_10pct*1e3:.2f} mV signal\\n"
                f" 1% Rule: R_shunt = {r_shunt_1pct:.2f} Ω  →  {v_drop_1pct*1e3:.2f} mV signal\\n"
                f"\\n"
            )
            
            # Add recommendation
            if v_drop_10pct >= 0.01:  # 10 mV or more
                result += f"✅ Recommended: Use 10% rule ({r_shunt_10pct:.2f} Ω)"
                # Auto-fill r_shunt field
                self.vars['r_shunt'].set(f"{r_shunt_10pct:.2f}")
            elif v_drop_1pct >= 0.001:  # 1 mV or more
                result += f"⚠️ Use 1% rule ({r_shunt_1pct:.2f} Ω) - signal is small"
                self.vars['r_shunt'].set(f"{r_shunt_1pct:.2f}")
            else:
                result += "❌ Signal too small! Consider using TIA instead"
            
            self.vars['calc_result'].set(result)
            
        except ValueError:
            self.vars['calc_result'].set("⚠️ Error: Please enter valid numbers")
        except Exception as e:
            self.vars['calc_result'].set(f"⚠️ Error: {str(e)}")
    
    def _quick_test_device(self):
        """Perform a quick pulse test to measure device current"""
        try:
            voltage = float(self.vars['calc_voltage'].get())
            
            # Check if we have a callback for quick test
            if 'quick_test' in self.callbacks:
                self.vars['calc_result'].set(f"⚡ Testing device at {voltage}V...")
                self.parent.update()  # Force GUI update
                
                # Call the quick test callback (will be handled by logic layer)
                current = self.callbacks['quick_test'](voltage)
                
                if current is not None and abs(current) > 1e-15:
                    # Success! Update current field
                    self.vars['calc_current'].set(f"{current:.9f}")
                    # Auto-calculate
                    self._calculate_shunt()
                    # Show success message
                    self.vars['calc_result'].set(f"✅ Quick test successful! Measured {abs(current)*1e6:.3f} µA\n" + 
                                                 self.vars['calc_result'].get())
                else:
                    self.vars['calc_result'].set("⚠️ Quick test returned zero or None - check connections")
            else:
                self.vars['calc_result'].set("⚠️ Quick test not available - connect SMU first")
                
        except ValueError:
            self.vars['calc_result'].set("⚠️ Error: Invalid voltage value")
        except Exception as e:
            self.vars['calc_result'].set(f"⚠️ Error: {str(e)}")
    
    def _read_scope_settings(self):
        """Read current oscilloscope settings and populate GUI fields"""
        try:
            # Check if we have a callback for reading scope settings
            if 'read_scope_settings' in self.callbacks:
                self.vars['calc_result'].set("📖 Reading oscilloscope settings...")
                self.parent.update()
                
                # Call the callback to read settings
                settings = self.callbacks['read_scope_settings']()
                
                if settings:
                    # Populate the GUI fields with current scope settings
                    if 'timebase' in settings:
                        self.vars['scope_timebase'].set(f"{settings['timebase']:.6f}")
                    if 'voltage_scale' in settings:
                        self.vars['scope_vscale'].set(f"{settings['voltage_scale']:.6f}")
                    if 'trigger_level' in settings:
                        # Could add a trigger level field if needed
                        pass
                    
                    # Build info message
                    info_msg = "✅ Scope settings read successfully:\n"
                    if 'timebase' in settings:
                        info_msg += f"  Timebase: {settings['timebase']*1e3:.3f} ms/div\n"
                    if 'voltage_scale' in settings:
                        info_msg += f"  Voltage scale: {settings['voltage_scale']:.3f} V/div\n"
                    if 'trigger_level' in settings:
                        info_msg += f"  Trigger level: {settings['trigger_level']:.3f} V\n"
                    if 'trigger_mode' in settings:
                        info_msg += f"  Trigger mode: {settings['trigger_mode']}\n"
                    
                    self.vars['calc_result'].set(info_msg)
                else:
                    self.vars['calc_result'].set("⚠️ Failed to read scope settings")
            else:
                self.vars['calc_result'].set("⚠️ Scope not connected - connect oscilloscope first")
                
        except Exception as e:
            self.vars['calc_result'].set(f"⚠️ Error reading scope: {str(e)}")


    def _add_param(self, parent, label, config_key, default, options=None, ToolTipText=None):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)
        lbl = ttk.Label(frame, text=label)
        lbl.pack(side="left")
        
        if ToolTipText:
            ToolTip(lbl, ToolTipText)
        
        var = tk.StringVar(value=str(self.config.get(config_key, default)))
        self.vars[config_key] = var
        
        if options:
            widget = ttk.Combobox(frame, textvariable=var, values=options, width=10)
            widget.pack(side="right")
        else:
            widget = ttk.Entry(frame, textvariable=var, width=15)
            widget.pack(side="right")
            
        if ToolTipText:
            ToolTip(widget, ToolTipText)
    
    def reset_plots(self):
        """Reset all plots to empty state"""
        if not hasattr(self, 'ax_voltage'):
            return
        for ax in [self.ax_voltage, self.ax_current, self.ax_zoom, self.ax_zoom_r]:
            ax.clear()
            
        self.ax_voltage.set_ylabel("Voltage (V)")
        self.ax_voltage.set_title("Voltage Waveform", fontsize=10)
        self.ax_voltage.grid(True, alpha=0.3)
        
        self.ax_current.set_ylabel("Current (A)")
        self.ax_current.set_title("Current Waveform", fontsize=10)
        self.ax_current.grid(True, alpha=0.3)
        
        self.ax_zoom.set_xlabel("Time (s)")
        self.ax_zoom.set_title("Pulse Zoom View", fontsize=10)
        self.ax_zoom.set_ylabel("Voltage (V)", color='b')
        self.ax_zoom_r.set_ylabel("Current (A)", color='r')
        self.ax_zoom.grid(True, alpha=0.3)
        
        self.canvas.draw()
        
    def update_plots(self, t, v, i):
        """Update plots with new data"""
        if not hasattr(self, 'ax_voltage'):
            return
        # 1. Full View
        self.ax_voltage.plot(t, v, 'b-', label='V')
        self.ax_current.plot(t, i, 'r-', label='I')
        
        # 2. Zoom View
        self.ax_zoom.plot(t, v, 'b-', alpha=0.7)
        self.ax_zoom_r.plot(t, i, 'r-', alpha=0.7)
        
        self.canvas.draw()

    def set_status(self, msg):
        """Set status message"""
        if 'status' in self.vars:
            self.vars['status'].set(msg)

    def set_running_state(self, is_running):
        """Update button states based on running status"""
        if 'run_btn' in self.widgets and 'stop_btn' in self.widgets:
            if is_running:
                self.widgets['run_btn'].config(state="disabled")
                self.widgets['stop_btn'].config(state="normal")
            else:
                self.widgets['run_btn'].config(state="normal")
                self.widgets['stop_btn'].config(state="disabled")

    def get_params(self):
        """Retrieve all parameter values from vars."""
        params = {}
        for key, var in self.vars.items():
            if key not in ['status', 'save_dir']: # Exclude status/display vars
                params[key] = var.get()
        return params
            
class ToolTip(object):
    """
    create a tooltip for a given widget
    """
    def __init__(self, widget, text='widget info'):
        self.waittime = 500     #miliseconds
        self.wraplength = 180   #pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       wraplength = self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()
