import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.gridspec as gridspec
import numpy as np

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
        self._build_scope_frame(left_panel)
        self._build_pulse_frame(left_panel)
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
                                values=self.context.get('known_systems', ["keithley4200a", "keithley2450", "keithley2400"]), 
                                width=15, state="readonly")
        sys_combo.pack(side="left", padx=5)
        sys_combo.bind("<<ComboboxSelected>>", lambda e: self.callbacks.get('on_system_change', lambda: None)())
        
        # Simulation Mode (moved to top bar)
        self.vars['simulation_mode'] = tk.BooleanVar(value=self.config.get("simulation_mode", False))
        sim_check = ttk.Checkbutton(bar_frame, text="🔧 Simulation Mode", 
                                    variable=self.vars['simulation_mode'])
        sim_check.pack(side="left", padx=(10, 0))
        ToolTip(sim_check, "Test without oscilloscope - generates simulated data")
        
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
        self.widgets['smu_address'] = smu_combo  # Store reference for updates
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
        self._add_param(frame, "Bias Voltage (V):", "bias_voltage", "0.2",
                       ToolTipText="Bias level applied before and after the pulse")
        self._add_param(frame, "Pre-Bias Time (s):", "pre_bias_time", "0.1",
                       ToolTipText="Time at bias voltage before the pulse")
        self._add_param(frame, "Post-Bias Time (s):", "post_bias_time", "1.0",
                       ToolTipText="Time at bias voltage after the pulse")

    def _build_scope_frame(self, parent):
        """Build oscilloscope settings frame - simplified for manual setup"""
        frame = ttk.Labelframe(parent, text="1️⃣ Oscilloscope Setup (Manual)", padding=10)
        frame.pack(fill="x", pady=5)
        
        # Instructions
        instructions = (
            "Set up your oscilloscope MANUALLY:\n"
            "• Timebase: to capture full pulse (e.g., 500 ms/div for 1s pulse)\n"
            "• V/div: appropriate for signal level (e.g., 200 mV/div)\n"
            "• Trigger: set to capture pulse start\n"
            "• Channel: use CH1 (or set below)"
        )
        instr_label = tk.Label(frame, text=instructions, justify="left", bg="#fff3cd", 
                              font=("Segoe UI", 8), fg="#856404", relief=tk.SOLID, bd=1, padx=5, pady=5)
        instr_label.pack(fill="x", pady=(0, 10))
        
        # Just the essentials for reading
        self._add_param(frame, "Scope Channel:", "scope_channel", "CH1", 
                       options=["CH1", "CH2", "CH3", "CH4"],
                       ToolTipText="Which channel to read from")

    def _build_measurement_frame(self, parent):
        """Build measurement settings frame"""
        frame = ttk.Labelframe(parent, text="Analysis Parameters (Critical!)", padding=10)
        frame.pack(fill="x", pady=5)
        
        tk.Label(frame, text="⚠️ R_shunt must match your actual resistor for correct current calculation!", 
                bg="#f0f0f0", fg="#d32f2f", font=("Segoe UI", 8, "bold")).pack(fill="x", pady=(0, 5))
        
        self._add_param(frame, "R_shunt (Ω):", "r_shunt", "100000",
                       ToolTipText="Actual value of your shunt resistor - measure with DMM if unsure!")
    
    def _build_calculator_frame(self, parent):
        """Build shunt resistor calculator frame"""
        frame = ttk.Labelframe(parent, text="📐 Shunt Resistor Calculator", padding=10)
        frame.pack(fill="x", pady=5)
        
        # Input row
        input_row = ttk.Frame(frame)
        input_row.pack(fill="x", pady=2)
        
        ttk.Label(input_row, text="Test Voltage (V):").pack(side="left")
        self.vars['calc_voltage'] = tk.StringVar(value="2.0")
        calc_v_entry = ttk.Entry(input_row, textvariable=self.vars['calc_voltage'], width=8)
        calc_v_entry.pack(side="left", padx=5)
        
        ttk.Label(input_row, text="Expected Current (A):").pack(side="left", padx=(10, 0))
        self.vars['calc_current'] = tk.StringVar(value="0.000001")
        calc_i_entry = ttk.Entry(input_row, textvariable=self.vars['calc_current'], width=12)
        calc_i_entry.pack(side="left", padx=5)
        
        # Rule selection (1% or 10%)
        ttk.Label(input_row, text="Rule:").pack(side="left", padx=(10, 0))
        self.vars['calc_rule'] = tk.StringVar(value="10")
        rule_combo = ttk.Combobox(input_row, textvariable=self.vars['calc_rule'], 
                                 values=["1", "10"], width=5, state="readonly")
        rule_combo.pack(side="left", padx=5)
        ttk.Label(input_row, text="%").pack(side="left")
        
        tk.Button(input_row, text="Calculate", command=self._calculate_shunt,
                 bg="#4caf50", fg="white", font=("Segoe UI", 8, "bold"), 
                 relief=tk.FLAT, padx=10, pady=2).pack(side="left", padx=5)
        
        # Auto-calculate on Enter key
        calc_v_entry.bind("<Return>", lambda e: self._calculate_shunt())
        calc_i_entry.bind("<Return>", lambda e: self._calculate_shunt())
        
        # Results display
        results_frame = ttk.Frame(frame)
        results_frame.pack(fill="x", pady=(5, 0))
        
        self.vars['calc_result'] = tk.StringVar(value="Enter values and click Calculate")
        result_label = tk.Label(results_frame, textvariable=self.vars['calc_result'], 
                               bg="#f0f0f0", fg="#1b5e20", font=("Consolas", 8), 
                               justify="left", anchor="w", wraplength=400, relief=tk.SUNKEN, bd=1, padx=5, pady=5)
        result_label.pack(fill="x")
        
        # Quick Test Section (Expandable)
        self._build_quick_test_section(frame)
    
    def _build_quick_test_section(self, parent):
        """Build expandable quick test section"""
        # Container frame
        test_container = ttk.Frame(parent)
        test_container.pack(fill="x", pady=(10, 0))
        
        # Header with expand/collapse button
        header_frame = ttk.Frame(test_container)
        header_frame.pack(fill="x")
        
        self.vars['quick_test_expanded'] = tk.BooleanVar(value=False)
        expand_btn = ttk.Button(header_frame, text="▶ Quick Test", 
                               command=lambda: self._toggle_quick_test(test_container, expand_btn),
                               style="Small.TButton")
        expand_btn.pack(side="left")
        self.widgets['quick_test_expand_btn'] = expand_btn
        
        # Expandable content frame (initially hidden)
        self.widgets['quick_test_content'] = ttk.Frame(test_container)
        
        # Quick test parameters (stored but not shown until expanded)
        self.vars['quick_test_voltage'] = tk.StringVar(value="2.0")
        self.vars['quick_test_duration'] = tk.StringVar(value="0.1")
        self.vars['quick_test_compliance'] = tk.StringVar(value="0.001")
    
    def _toggle_quick_test(self, container, button):
        """Toggle quick test section expand/collapse"""
        content_frame = self.widgets['quick_test_content']
        expanded = self.vars['quick_test_expanded'].get()
        
        if expanded:
            # Collapse
            content_frame.pack_forget()
            button.config(text="▶ Quick Test")
            self.vars['quick_test_expanded'].set(False)
        else:
            # Expand - build content if not already built
            if not hasattr(self, '_quick_test_built'):
                self._build_quick_test_content(content_frame)
                self._quick_test_built = True
            
            content_frame.pack(fill="x", pady=(5, 0))
            button.config(text="▼ Quick Test")
            self.vars['quick_test_expanded'].set(True)
    
    def _build_quick_test_content(self, parent):
        """Build quick test content (called when expanded)"""
        # Quick test parameters
        params_frame = ttk.LabelFrame(parent, text="Quick Test Parameters", padding=5)
        params_frame.pack(fill="x", pady=2)
        
        # Voltage
        v_frame = ttk.Frame(params_frame)
        v_frame.pack(fill="x", pady=2)
        ttk.Label(v_frame, text="Voltage (V):").pack(side="left")
        v_entry = ttk.Entry(v_frame, textvariable=self.vars['quick_test_voltage'], width=10)
        v_entry.pack(side="right")
        
        # Duration
        d_frame = ttk.Frame(params_frame)
        d_frame.pack(fill="x", pady=2)
        ttk.Label(d_frame, text="Duration (s):").pack(side="left")
        d_entry = ttk.Entry(d_frame, textvariable=self.vars['quick_test_duration'], width=10)
        d_entry.pack(side="right")
        
        # Compliance
        c_frame = ttk.Frame(params_frame)
        c_frame.pack(fill="x", pady=2)
        ttk.Label(c_frame, text="Compliance (A):").pack(side="left")
        c_entry = ttk.Entry(c_frame, textvariable=self.vars['quick_test_compliance'], width=10)
        c_entry.pack(side="right")
        
        # Test button
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", pady=5)
        quick_test_btn = tk.Button(btn_frame, text="⚡ Run Quick Test", 
                                   command=self._run_quick_test,
                                   bg="#ff9800", fg="white", font=("Segoe UI", 9, "bold"),
                                   relief=tk.FLAT, padx=15, pady=5)
        quick_test_btn.pack(side="left")
        ToolTip(quick_test_btn, "Pulse device with specified parameters and measure current")
    
    def _run_quick_test(self):
        """Run quick test with specified parameters"""
        try:
            voltage = float(self.vars['quick_test_voltage'].get())
            duration = float(self.vars['quick_test_duration'].get())
            compliance = float(self.vars['quick_test_compliance'].get())
            
            # Update calculator voltage field
            self.vars['calc_voltage'].set(str(voltage))
            
            # Check if we have a callback for quick test
            if 'quick_test' in self.callbacks:
                self.vars['calc_result'].set(f"⚡ Testing device at {voltage}V for {duration}s...")
                self.parent.update()  # Force GUI update
                
                # Call the quick test callback with custom parameters
                # We need to modify the callback to accept duration and compliance
                current = self.callbacks['quick_test'](voltage, duration, compliance)
                
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
            self.vars['calc_result'].set("⚠️ Error: Please enter valid numbers")
        except Exception as e:
            self.vars['calc_result'].set(f"⚠️ Error: {str(e)}")


    def _build_save_options_frame(self, parent):
        """Build save options frame"""
        frame = ttk.Labelframe(parent, text="Save Options", padding=10)
        frame.pack(fill="x", pady=5)
        
        # Auto-save checkbox
        self.vars['auto_save'] = tk.BooleanVar(value=self.config.get("auto_save", True))
        auto_save_check = ttk.Checkbutton(
            frame, 
            text="Auto-save after measurement",
            variable=self.vars['auto_save']
        )
        auto_save_check.pack(side="left", padx=5)
        ToolTip(auto_save_check, "Automatically save measurement data after completion")
    
    def _build_action_buttons(self, parent):
        """Build action buttons frame - simplified workflow"""
        frame = ttk.LabelFrame(parent, text="📋 Measurement Workflow", padding=10)
        frame.pack(fill="x", pady=5)
        
        # Workflow instructions
        instructions = (
            "1️⃣ Manually set up your oscilloscope (timebase, V/div, trigger)\n"
            "2️⃣ Click 'Send Pulse' to fire the SMU pulse\n"
            "3️⃣ Verify pulse captured on scope screen\n"
            "4️⃣ Click 'Read & Analyze' to get the data and calculate I/V/R"
        )
        instr_label = tk.Label(frame, text=instructions, justify="left", bg="#f0f0f0", 
                              font=("Segoe UI", 9), fg="#1565c0")
        instr_label.pack(fill="x", pady=(0, 10))
        
        # Main workflow buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=2)
        
        self.widgets['pulse_only_btn'] = ttk.Button(btn_frame, text="2️⃣ Send Pulse", 
                                                     command=self.callbacks.get('pulse_only', lambda: None),
                                                     style="Action.TButton")
        self.widgets['pulse_only_btn'].pack(side="left", padx=2, fill="x", expand=True)
        
        self.widgets['grab_scope_btn'] = ttk.Button(btn_frame, text="4️⃣ Read & Analyze", 
                                                     command=self.callbacks.get('grab_scope', lambda: None),
                                                     style="Action.TButton")
        self.widgets['grab_scope_btn'].pack(side="left", padx=2, fill="x", expand=True)
        
        # Secondary actions
        btn_frame2 = ttk.Frame(frame)
        btn_frame2.pack(fill="x", pady=(5, 0))
        
        save_btn = ttk.Button(btn_frame2, text="💾 Save Data", 
                             command=self.callbacks.get('save', lambda: None))
        save_btn.pack(side="left", padx=2, fill="x", expand=True)
        
        self.widgets['stop_btn'] = ttk.Button(btn_frame2, text="⏹ Stop", 
                                             command=self.callbacks.get('stop', lambda: None),
                                             style="Stop.TButton", state="disabled")
        self.widgets['stop_btn'].pack(side="left", padx=2, fill="x", expand=True)

    def _build_status_bar(self, parent):
        """Build status bar"""
        frame = ttk.Frame(parent, padding=5)
        frame.pack(fill="x", pady=5)
        
        self.vars['status'] = tk.StringVar(value="Ready")
        status_label = ttk.Label(frame, textvariable=self.vars['status'], style="Status.TLabel")
        status_label.pack(side="left")

    def _build_plots(self, parent):
        """Build matplotlib plots - simplified to show only voltage overlay"""
        # Store plot data for line visibility toggles
        self.plot_data = {}
        self.plot_lines = {}
        
        # Create main voltage overlay plot (no tabs, just one big plot)
        plot_frame = ttk.Frame(parent)
        plot_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create figure with single plot
        fig = plt.Figure(figsize=(12, 6), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_ylabel("Voltage (V)", fontweight='bold', fontsize=12)
        ax.set_title("Voltage Overlay: V_SMU (Programmed) vs V_shunt (Measured) vs V_DUT (Calculated)", 
                    fontsize=12, fontweight='bold', pad=10)
        ax.set_xlabel("Time (s)", fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # Create canvas
        canvas = FigureCanvasTkAgg(fig, plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Create toolbar
        toolbar = NavigationToolbar2Tk(canvas, plot_frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")
        
        # Store references
        self.plot_lines['Main'] = {
            'fig': fig,
            'ax': ax,
            'canvas': canvas,
            'toolbar': toolbar,
            'lines': {}
        }
        
        # For compatibility with old code
        self.ax_voltage_breakdown = ax
    
    def _create_overview_tab(self):
        """Create overview tab with all plots in 2x2 grid"""
        # Create frame for tab
        tab_frame = ttk.Frame(self.plot_notebook)
        self.plot_notebook.add(tab_frame, text="Overview")
        
        # Create figure with 2x2 grid
        fig = plt.Figure(figsize=(12, 10), dpi=100)
        gs = gridspec.GridSpec(2, 2, height_ratios=[1, 1], width_ratios=[1, 1], hspace=0.4, wspace=0.3)
        
        # Create all 4 subplots
        ax_voltage = fig.add_subplot(gs[0, 0])
        ax_voltage.set_ylabel("Voltage (V)")
        ax_voltage.set_title("Voltage Distribution: SMU, Shunt, and Memristor", fontsize=11, fontweight='bold')
        ax_voltage.grid(True, alpha=0.3)
        ax_voltage.set_xlabel("Time (s)")
        
        ax_current = fig.add_subplot(gs[0, 1])
        ax_current.set_ylabel("Current (A)")
        ax_current.set_title("Current Through Circuit (I = V_shunt / R_shunt)", fontsize=11, fontweight='bold')
        ax_current.grid(True, alpha=0.3)
        ax_current.set_xlabel("Time (s)")
        
        ax_resistance = fig.add_subplot(gs[1, 0])
        ax_resistance.set_ylabel("Resistance (Ω)")
        ax_resistance.set_title("Memristor Resistance: R = (V_SMU - V_shunt) / I", fontsize=11, fontweight='bold')
        ax_resistance.grid(True, alpha=0.3)
        ax_resistance.set_xlabel("Time (s)")
        
        ax_power = fig.add_subplot(gs[1, 1])
        ax_power.set_ylabel("Power (W)")
        ax_power.set_title("Power Dissipation in Memristor: P = V_memristor × I", fontsize=11, fontweight='bold')
        ax_power.grid(True, alpha=0.3)
        ax_power.set_xlabel("Time (s)")
        
        # Create canvas
        canvas = FigureCanvasTkAgg(fig, tab_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create toolbar
        toolbar = NavigationToolbar2Tk(canvas, tab_frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")
        
        # Store references
        self.plot_lines['Overview'] = {
            'fig': fig,
            'axes': {
                'voltage': ax_voltage,
                'current': ax_current,
                'resistance': ax_resistance,
                'power': ax_power
            },
            'canvas': canvas,
            'toolbar': toolbar,
            'lines': {}
        }
    
    def _create_plot_tab(self, tab_name, title):
        """Create a tab with a single plot and controls"""
        # Create frame for tab
        tab_frame = ttk.Frame(self.plot_notebook)
        self.plot_notebook.add(tab_frame, text=tab_name)
        
        # Control frame for line visibility toggles
        control_frame = ttk.Frame(tab_frame)
        control_frame.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(control_frame, text="Show:", font=("Segoe UI", 9)).pack(side="left", padx=5)
        
        # Create figure and axis
        fig = plt.Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("Time (s)")
        
        # Create canvas
        canvas = FigureCanvasTkAgg(fig, tab_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create toolbar
        toolbar = NavigationToolbar2Tk(canvas, tab_frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")
        
        # Store references
        if not hasattr(self, 'plot_lines'):
            self.plot_lines = {}
        self.plot_lines[tab_name] = {
            'fig': fig,
            'ax': ax,
            'canvas': canvas,
            'toolbar': toolbar,
            'control_frame': control_frame,
            'checkboxes': {},
            'lines': {}  # Store line objects for visibility toggling
        }
    
    def _create_alignment_tab(self):
        """Create alignment tab with individual timing controls, auto-fit, and cleaner UI"""
        import numpy as np
        
        # Create frame for tab
        tab_frame = ttk.Frame(self.plot_notebook)
        self.plot_notebook.add(tab_frame, text="Alignment")
        
        # === CONTROL PANEL ===
        control_panel = ttk.LabelFrame(tab_frame, text="Timing & Alignment Controls", padding=8)
        control_panel.pack(fill="x", padx=8, pady=5)
        
        # Add help text
        help_text = ("Alignment Tool: Use this to sync the programmed V_SMU pulse with the measured V_shunt waveform.\n"
                    "• V_SMU (green dashed) = What you programmed the SMU to output (reconstructed from parameters)\n"
                    "• V_shunt (red solid) = What the oscilloscope actually measured\n"
                    "• Use 'Auto-Fit' to automatically detect and align the pulse, or manually adjust timing/offsets.")
        help_label = tk.Label(control_panel, text=help_text, bg="#f0f0f0", fg="#555", 
                             font=("Segoe UI", 8), justify="left", wraplength=700)
        help_label.pack(fill="x", pady=(0, 10))
        
        # Store offsets
        self.alignment_offset = 0.0
        self.zero_offset = 0.0
        
        # Initialize alignment timing vars if not exists
        if 'align_pre_bias_time' not in self.vars:
            self.vars['align_pre_bias_time'] = tk.DoubleVar(value=0.1)
        if 'align_pulse_duration' not in self.vars:
            self.vars['align_pulse_duration'] = tk.DoubleVar(value=0.001)
        if 'align_post_bias_time' not in self.vars:
            self.vars['align_post_bias_time'] = tk.DoubleVar(value=1.0)
        if 'pulse_alignment' not in self.vars:
            self.vars['pulse_alignment'] = tk.DoubleVar(value=0.0)
        if 'zero_offset' not in self.vars:
            self.vars['zero_offset'] = tk.DoubleVar(value=0.0)
        
        # === TIMING CONTROLS SECTION ===
        timing_frame = ttk.LabelFrame(control_panel, text="3️⃣ Fine-Tune: Individual Timing Controls", padding=10)
        timing_frame.pack(fill="x", pady=(0, 10))
        
        tk.Label(timing_frame, text="Adjust these to match the actual pulse timing if auto-fit doesn't work perfectly", 
                bg="#f0f0f0", fg="#555", font=("Segoe UI", 7, "italic")).pack(fill="x", pady=(0, 5))
        
        timing_grid = ttk.Frame(timing_frame)
        timing_grid.pack(fill="x")
        
        # Helper function to create timing control with slider
        def create_timing_control(parent, label, var_key, default, min_val, max_val):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=1)
            
            ttk.Label(row, text=label + ":", width=16, anchor="w", font=("Segoe UI", 8)).pack(side="left", padx=(0, 3))
            
            # Slider
            slider = ttk.Scale(
                row,
                from_=min_val,
                to=max_val,
                variable=self.vars[var_key],
                orient="horizontal",
                length=150
            )
            slider.pack(side="left", padx=3, fill="x", expand=True)
            
            # Entry box
            entry_var = tk.StringVar(value=f"{default:.3f}")
            entry_frame = ttk.Frame(row)
            entry_frame.pack(side="left", padx=3)
            
            entry = ttk.Entry(entry_frame, textvariable=entry_var, width=8, font=("Segoe UI", 8))
            entry.pack(side="left")
            ttk.Label(entry_frame, text="s", font=("Segoe UI", 8)).pack(side="left", padx=(1, 0))
            
            # Sync entry and var
            def update_var(*args):
                try:
                    val = float(entry_var.get())
                    val = max(min_val, min(max_val, val))
                    self.vars[var_key].set(val)
                    entry_var.set(f"{val:.3f}")
                    self._update_alignment_preview()
                except ValueError:
                    entry_var.set(f"{self.vars[var_key].get():.3f}")
            
            def update_entry(*args):
                val = self.vars[var_key].get()
                entry_var.set(f"{val:.3f}")
                self._update_alignment_preview()
            
            def update_slider(v):
                # Slider callback - update entry
                val = float(v)
                entry_var.set(f"{val:.3f}")
                self._update_alignment_preview()
            
            entry_var.trace_add('write', update_var)
            self.vars[var_key].trace_add('write', update_entry)
            slider.configure(command=update_slider)
        
        # Create timing controls
        create_timing_control(timing_grid, "Pre-Bias Time", "align_pre_bias_time", 0.1, 0.0, 10.0)
        create_timing_control(timing_grid, "Pulse Duration", "align_pulse_duration", 0.001, 0.0001, 10.0)
        create_timing_control(timing_grid, "Post-Bias Time", "align_post_bias_time", 1.0, 0.0, 100.0)
        
        # === ALIGNMENT OFFSETS SECTION ===
        offset_frame = ttk.LabelFrame(control_panel, text="3️⃣ Fine-Tune: Alignment Offsets", padding=8)
        offset_frame.pack(fill="x", pady=(0, 8))
        
        tk.Label(offset_frame, text="Shift the V_SMU reference waveform to align with measured data", 
                bg="#f0f0f0", fg="#555", font=("Segoe UI", 7, "italic")).pack(fill="x", pady=(0, 5))
        
        # Horizontal offset with slider
        h_row = ttk.Frame(offset_frame)
        h_row.pack(fill="x", pady=1)
        ttk.Label(h_row, text="Time Shift:", width=16, anchor="w", font=("Segoe UI", 8)).pack(side="left", padx=(0, 3))
        
        h_slider = ttk.Scale(
            h_row,
            from_=-10.0,
            to=10.0,
            variable=self.vars['pulse_alignment'],
            orient="horizontal",
            length=150
        )
        h_slider.pack(side="left", padx=3, fill="x", expand=True)
        
        h_entry_var = tk.StringVar(value="0.000")
        h_entry_frame = ttk.Frame(h_row)
        h_entry_frame.pack(side="left", padx=3)
        
        h_entry = ttk.Entry(h_entry_frame, textvariable=h_entry_var, width=8, font=("Segoe UI", 8))
        h_entry.pack(side="left")
        ttk.Label(h_entry_frame, text="s", font=("Segoe UI", 8)).pack(side="left", padx=(1, 0))
        
        def on_h_offset_change(*args):
            try:
                val = float(h_entry_var.get())
                val = max(-10.0, min(10.0, val))
                self.vars['pulse_alignment'].set(val)
                self.alignment_offset = val
                h_entry_var.set(f"{val:.3f}")
                self._update_alignment_preview()
            except ValueError:
                h_entry_var.set(f"{self.vars['pulse_alignment'].get():.3f}")
        
        def on_h_offset_var_change(*args):
            val = self.vars['pulse_alignment'].get()
            self.alignment_offset = val
            h_entry_var.set(f"{val:.3f}")
            self._update_alignment_preview()
        
        def on_h_slider_change(v):
            val = float(v)
            h_entry_var.set(f"{val:.3f}")
            self._update_alignment_preview()
        
        h_entry_var.trace_add('write', on_h_offset_change)
        self.vars['pulse_alignment'].trace_add('write', on_h_offset_var_change)
        h_slider.configure(command=on_h_slider_change)
        
        # Vertical offset with slider
        v_row = ttk.Frame(offset_frame)
        v_row.pack(fill="x", pady=1)
        ttk.Label(v_row, text="Voltage Shift:", width=16, anchor="w", font=("Segoe UI", 8)).pack(side="left", padx=(0, 3))
        
        v_slider = ttk.Scale(
            v_row,
            from_=-5.0,
            to=5.0,
            variable=self.vars['zero_offset'],
            orient="horizontal",
            length=150
        )
        v_slider.pack(side="left", padx=3, fill="x", expand=True)
        
        v_entry_var = tk.StringVar(value="0.000")
        v_entry_frame = ttk.Frame(v_row)
        v_entry_frame.pack(side="left", padx=3)
        
        v_entry = ttk.Entry(v_entry_frame, textvariable=v_entry_var, width=8, font=("Segoe UI", 8))
        v_entry.pack(side="left")
        ttk.Label(v_entry_frame, text="V", font=("Segoe UI", 8)).pack(side="left", padx=(1, 0))
        
        def on_v_offset_change(*args):
            try:
                val = float(v_entry_var.get())
                val = max(-5.0, min(5.0, val))
                self.vars['zero_offset'].set(val)
                self.zero_offset = val
                v_entry_var.set(f"{val:.3f}")
                self._update_alignment_preview()
            except ValueError:
                v_entry_var.set(f"{self.vars['zero_offset'].get():.3f}")
        
        def on_v_offset_var_change(*args):
            val = self.vars['zero_offset'].get()
            self.zero_offset = val
            v_entry_var.set(f"{val:.3f}")
            self._update_alignment_preview()
        
        def on_v_slider_change(v):
            val = float(v)
            v_entry_var.set(f"{val:.3f}")
            self._update_alignment_preview()
        
        v_entry_var.trace_add('write', on_v_offset_change)
        self.vars['zero_offset'].trace_add('write', on_v_offset_var_change)
        v_slider.configure(command=on_v_slider_change)
        
        # === BUTTONS SECTION ===
        button_frame = ttk.LabelFrame(control_panel, text="Alignment Workflow", padding=5)
        button_frame.pack(fill="x", pady=(4, 0))
        
        # Workflow instructions
        workflow_text = "Step 1: Load Params → Step 2: Auto-Fit → Step 3: Fine-tune manually → Step 4: Apply"
        tk.Label(button_frame, text=workflow_text, bg="#f0f0f0", fg="#1565c0", 
                font=("Segoe UI", 8, "bold"), justify="center").pack(fill="x", pady=(0, 5))
        
        # Row 1: Primary buttons with tooltips
        btn_row1 = ttk.Frame(button_frame)
        btn_row1.pack(fill="x", pady=1)
        
        load_params_btn = ttk.Button(
            btn_row1,
            text="1️⃣ Load Params",
            command=self._load_timings_from_params
        )
        load_params_btn.pack(side="left", padx=2, fill="x", expand=True)
        ToolTip(load_params_btn, "Load timing parameters from the Pulse Parameters tab")
        
        auto_fit_btn = ttk.Button(
            btn_row1,
            text="2️⃣ Auto-Fit",
            command=self._auto_fit_pulse
        )
        auto_fit_btn.pack(side="left", padx=2, fill="x", expand=True)
        ToolTip(auto_fit_btn, "Automatically detect pulse and align V_SMU to measured data")
        
        # Row 2: Secondary buttons
        btn_row2 = ttk.Frame(button_frame)
        btn_row2.pack(fill="x", pady=1)
        
        apply_btn = ttk.Button(
            btn_row2,
            text="4️⃣ Apply Changes",
            command=self._apply_alignment
        )
        apply_btn.pack(side="left", padx=2, fill="x", expand=True)
        ToolTip(apply_btn, "Apply alignment changes and recalculate all plots")
        
        reset_btn = ttk.Button(
            btn_row2,
            text="↻ Reset All",
            command=self._reset_alignment
        )
        reset_btn.pack(side="left", padx=2, fill="x", expand=True)
        ToolTip(reset_btn, "Reset all alignment settings to defaults")
        
        # === PLOT AREA ===
        fig = plt.Figure(figsize=(12, 5), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_title("Pulse Alignment: V_SMU vs V_shunt", fontsize=10, fontweight='bold', pad=10)
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("Time (s)", fontsize=9)
        ax.set_ylabel("Voltage (V)", fontsize=9)
        
        canvas = FigureCanvasTkAgg(fig, tab_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
        
        toolbar = NavigationToolbar2Tk(canvas, tab_frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")
        
        # Store references
        if not hasattr(self, 'plot_lines'):
            self.plot_lines = {}
        self.plot_lines['Alignment'] = {
            'fig': fig,
            'ax': ax,
            'canvas': canvas,
            'toolbar': toolbar,
            'control_frame': control_panel,
            'lines': {}
        }
    
    def _load_timings_from_params(self):
        """Load timing parameters from the Parameters tab"""
        try:
            if 'pre_bias_time' in self.vars:
                val = float(self.vars['pre_bias_time'].get())
                self.vars['align_pre_bias_time'].set(val)
            if 'pulse_duration' in self.vars:
                val = float(self.vars['pulse_duration'].get())
                self.vars['align_pulse_duration'].set(val)
            if 'post_bias_time' in self.vars:
                val = float(self.vars['post_bias_time'].get())
                self.vars['align_post_bias_time'].set(val)
            self._update_alignment_preview()
        except Exception as e:
            print(f"Error loading parameters: {e}")
    
    def _reset_alignment(self):
        """Reset all alignment settings"""
        self.vars['pulse_alignment'].set(0.0)
        self.vars['zero_offset'].set(0.0)
        self._load_timings_from_params()
        self._apply_alignment()
    
    def _auto_fit_pulse(self):
        """Automatically fit the pulse to the measured signal using improved detection"""
        if not hasattr(self, 'plot_data') or 't' not in self.plot_data:
            return
        
        import numpy as np
        t = self.plot_data['t']
        v_shunt_raw = self.plot_data.get('v_shunt', self.plot_data.get('v', []))
        
        if len(t) == 0 or len(v_shunt_raw) == 0:
            return
        
        try:
            bias_voltage = float(self.vars['bias_voltage'].get())
            pulse_voltage = float(self.vars['pulse_voltage'].get())
        except:
            metadata = self.plot_data.get('metadata', {})
            bias_voltage = float(metadata.get('bias_voltage', 0.2))
            pulse_voltage = float(metadata.get('pulse_voltage', 1.0))
        
        # Apply current zero offset
        zero_offset = self.vars['zero_offset'].get()
        v_shunt = v_shunt_raw - zero_offset
        
        # First, auto-detect baseline offset (DC level adjustment)
        baseline_len = max(10, len(v_shunt) // 10)
        baseline = np.median(v_shunt[:baseline_len])
        
        # Auto-adjust zero offset to center baseline
        v_offset = -baseline
        self.vars['zero_offset'].set(v_offset)
        v_shunt = v_shunt_raw - v_offset  # Apply corrected offset
        
        # Use improved pulse detection
        detected_start = self._detect_pulse_start_improved(t, v_shunt, bias_voltage, pulse_voltage)
        
        if detected_start is None:
            print("Auto-fit: Could not detect pulse start")
            return
        
        # Detect pulse end (find where signal returns below/above threshold)
        pulse_amplitude = pulse_voltage - bias_voltage
        threshold = baseline + (pulse_amplitude * 0.5)
        
        # Find pulse end
        start_idx = np.where(t >= detected_start)[0]
        if len(start_idx) == 0:
            return
        start_idx = start_idx[0]
        
        if pulse_amplitude > 0:
            # Look for falling edge after start
            end_candidates = np.where((t > detected_start) & (v_shunt < threshold))[0]
        else:
            # Look for rising edge after start
            end_candidates = np.where((t > detected_start) & (v_shunt > threshold))[0]
        
        if len(end_candidates) > 0:
            end_idx = end_candidates[0]
            detected_duration = t[end_idx] - detected_start
        else:
            # Use GUI parameter as fallback
            try:
                detected_duration = float(self.vars['pulse_duration'].get())
            except:
                detected_duration = 0.001
        
        # Update alignment parameters
        self.vars['align_pulse_duration'].set(detected_duration)
        
        # Calculate time offset needed
        pre_bias_time = self.vars['align_pre_bias_time'].get()
        expected_start = pre_bias_time
        offset = detected_start - expected_start
        self.vars['pulse_alignment'].set(offset)
        
        print(f"Auto-fit complete: pulse starts at {detected_start:.6f}s, duration {detected_duration:.6f}s, offset {offset:.6f}s")
        
        self._update_alignment_preview()
    
    def _update_alignment_preview(self):
        """Update alignment plot preview dynamically as controls change"""
        if 'Alignment' not in self.plot_lines:
            return
        if not hasattr(self, 'plot_data') or 't' not in self.plot_data:
            return
        
        import numpy as np
        t = self.plot_data['t']
        v_shunt_raw = self.plot_data.get('v_shunt', self.plot_data.get('v', []))
        metadata = self.plot_data.get('metadata', {})
        
        if len(t) == 0 or len(v_shunt_raw) == 0:
            return
        
        preview_v_offset = self.vars['zero_offset'].get()
        v_shunt_preview = v_shunt_raw - preview_v_offset
        
        try:
            pulse_voltage = float(self.vars['pulse_voltage'].get())
            pulse_duration = self.vars['align_pulse_duration'].get()
            bias_voltage = float(self.vars['bias_voltage'].get())
        except:
            pulse_voltage = float(metadata.get('pulse_voltage', 1.0))
            pulse_duration = float(metadata.get('pulse_duration', 0.001))
            bias_voltage = float(metadata.get('bias_voltage', 0.2))
        
        original_pulse_start = metadata.get('pulse_start_time', 0.0)
        if original_pulse_start is None:
            original_pulse_start = 0.0
        
        preview_h_offset = self.vars['pulse_alignment'].get()
        pulse_start = original_pulse_start + preview_h_offset
        pulse_end = pulse_start + pulse_duration
        
        # Build V_SMU preview as 0 V outside, bias_voltage (e.g. 0.2V) before/after, and pulse_voltage during pulse
        v_smu_preview = self._create_v_smu_waveform(
            t, pulse_start, pulse_end, bias_voltage, pulse_voltage,
            pre_bias_time, post_bias_time
        )
        
        plot_info = self.plot_lines['Alignment']
        ax = plot_info['ax']
        ax.clear()
        
        if len(v_smu_preview) > 0 and len(v_shunt_preview) > 0:
            v_min = min(np.min(v_smu_preview), np.min(v_shunt_preview))
            v_max = max(np.max(v_smu_preview), np.max(v_shunt_preview))
            v_margin = (v_max - v_min) * 0.1 if (v_max - v_min) > 0 else 0.1
            ax.set_ylim(v_min - v_margin, v_max + v_margin)
        
        ax.plot(t, v_smu_preview, 'b-', linewidth=2.5, label='V_SMU (Applied)', alpha=0.85)
        ax.plot(t, v_shunt_preview, 'r-', linewidth=2, label='V_shunt (Measured)', alpha=0.75)
        
        ax.axvspan(pulse_start, pulse_end, alpha=0.1, color='green', label='Pulse Window')
        ax.axvline(x=pulse_start, color='green', linestyle='--', linewidth=1.5, alpha=0.6)
        ax.axvline(x=pulse_end, color='orange', linestyle='--', linewidth=1.5, alpha=0.6)
        ax.axhline(y=0, color='gray', linestyle=':', linewidth=1, alpha=0.5)
        
        ax.set_title("Pulse Alignment: V_SMU vs V_shunt (Preview)", fontsize=13, fontweight='bold', pad=15)
        ax.set_xlabel("Time (s)", fontsize=11)
        ax.set_ylabel("Voltage (V)", fontsize=11)
        ax.grid(True, alpha=0.25, linestyle='--')
        ax.legend(loc='best', fontsize=10, framealpha=0.9)
        
        if len(t) > 0:
            t_margin = (t[-1] - t[0]) * 0.05 if (t[-1] - t[0]) > 0 else 0.1
            ax.set_xlim(max(0, t[0] - t_margin), t[-1] + t_margin)
        
        plot_info['fig'].tight_layout()
        plot_info['canvas'].draw()
    
    def _create_v_smu_waveform(self, t, pulse_start, pulse_end, bias_voltage, pulse_voltage,
                               pre_bias_time, post_bias_time):
        """
        Create V_SMU waveform from pulse parameters.
        
        V_SMU represents the PROGRAMMED voltage from the SMU (idealized reference).
        This is NOT measured data - it's reconstructed from pulse parameters to show
        what the SMU was commanded to output.
        
        Shape:
            bias_voltage              for pre_bias_time before pulse_start
            pulse_voltage (ABSOLUTE)  between pulse_start and pulse_end
            bias_voltage              for post_bias_time after pulse_end
            0 V                       outside these windows
        
        Args:
            t: Time array
            pulse_start: Start time of pulse
            pulse_end: End time of pulse
            bias_voltage: Bias level (e.g., 0.2V)
            pulse_voltage: Pulse level ABSOLUTE (e.g., 2.0V, not +1.8V relative)
            pre_bias_time: Duration of pre-bias
            post_bias_time: Duration of post-bias
        """
        import numpy as np
        v_smu = np.zeros_like(t)
        
        # Define windows
        pre_start = max(0.0, pulse_start - pre_bias_time)
        pre_end = pulse_start
        post_start = pulse_end
        post_end = pulse_end + post_bias_time
        
        # Pre-bias window: bias_voltage
        pre_mask = (t >= pre_start) & (t < pre_end)
        v_smu[pre_mask] = bias_voltage
        
        # Pulse window: pulse_voltage (absolute level, not relative)
        pulse_mask = (t >= pulse_start) & (t <= pulse_end)
        v_smu[pulse_mask] = pulse_voltage
        
        # Post-bias window: bias_voltage again
        post_mask = (t > post_start) & (t <= post_end)
        v_smu[post_mask] = bias_voltage
        
        # Outside these windows v_smu remains 0.0
        return v_smu
    
    def _apply_alignment(self):
        """Apply alignment changes and recalculate plots"""
        self.alignment_offset = self.vars['pulse_alignment'].get()
        self.zero_offset = self.vars['zero_offset'].get()
        
        if hasattr(self, 'plot_data') and 't' in self.plot_data:
            self._recalculate_with_alignment()
    
    def _recalculate_with_alignment(self):
        """Recalculate all plots with new alignment and zero offsets"""
        if not hasattr(self, 'plot_data') or 't' not in self.plot_data:
            return
        
        import numpy as np
        t = self.plot_data['t']
        v_shunt_raw = self.plot_data.get('v_shunt', self.plot_data.get('v', []))
        metadata = self.plot_data.get('metadata', {})
        
        if len(t) == 0 or len(v_shunt_raw) == 0:
            return
        
        v_shunt = v_shunt_raw - self.zero_offset
        
        try:
            pulse_voltage = float(self.vars['pulse_voltage'].get())
            pulse_duration = self.vars['align_pulse_duration'].get()
            bias_voltage = float(self.vars['bias_voltage'].get())
            pre_bias_time = self.vars['align_pre_bias_time'].get()
            # For 4200A we use the same hold on both sides; mirror pre-bias time
            post_bias_time = pre_bias_time
        except:
            pulse_voltage = float(metadata.get('pulse_voltage', 1.0))
            pulse_duration = float(metadata.get('pulse_duration', 0.001))
            bias_voltage = float(metadata.get('bias_voltage', 0.2))
            pre_bias_time = float(metadata.get('pre_bias_time', 0.1))
            post_bias_time = pre_bias_time
        
        original_pulse_start = metadata.get('pulse_start_time', 0.0)
        if original_pulse_start is None:
            original_pulse_start = 0.0
        
        pulse_start = original_pulse_start + self.alignment_offset
        pulse_end = pulse_start + pulse_duration
        
        # Build V_SMU as 0 V outside, bias_voltage before/after, and pulse_voltage during pulse
        v_smu = self._create_v_smu_waveform(
            t, pulse_start, pulse_end, bias_voltage, pulse_voltage,
            pre_bias_time, post_bias_time
        )
        
        v_memristor_raw = v_smu - v_shunt
        noise_threshold = 0.01
        v_memristor = np.where(np.abs(v_memristor_raw) > noise_threshold, v_memristor_raw, 0.0)
        
        shunt_r = metadata.get('shunt_resistance', 50.0)
        current = v_shunt / shunt_r
        
        resistance = np.zeros_like(current)
        nonzero_current = np.abs(current) > 1e-10
        resistance[nonzero_current] = v_memristor[nonzero_current] / current[nonzero_current]
        
        power = v_memristor * current
        
        self.plot_data['v_smu'] = v_smu
        self.plot_data['v_memristor'] = v_memristor
        self.plot_data['v_shunt'] = v_shunt
        self.plot_data['current'] = current
        self.plot_data['resistance'] = resistance
        self.plot_data['power'] = power
        
        metadata['pulse_start_time'] = pulse_start
        
        self.update_plots(t, v_shunt, current, metadata)
    
    def _detect_pulse_start_improved(self, t, v_shunt, bias_voltage, pulse_voltage):
        """
        Improved pulse start detection using multiple methods.
        
        Args:
            t: Time array
            v_shunt: Measured voltage array (from oscilloscope)
            bias_voltage: Expected bias voltage level
            pulse_voltage: Expected pulse voltage level
        
        Returns:
            Detected pulse start time, or None if detection fails
        """
        if len(t) < 10 or len(v_shunt) < 10:
            return None
        
        import numpy as np
        
        # Calculate baseline from first 10% of data
        baseline_len = max(10, len(v_shunt) // 10)
        baseline = np.median(v_shunt[:baseline_len])
        
        # Calculate transition threshold (50% of expected pulse amplitude)
        # Handle both positive and negative pulses
        pulse_amplitude = pulse_voltage - bias_voltage
        threshold = baseline + (pulse_amplitude * 0.5)
        
        # Method 1: Threshold crossing
        if pulse_amplitude > 0:
            # Positive pulse - look for rising edge
            crossings = np.where(v_shunt > threshold)[0]
        else:
            # Negative pulse - look for falling edge
            crossings = np.where(v_shunt < threshold)[0]
        
        if len(crossings) > 0:
            pulse_start_idx = crossings[0]
            return t[pulse_start_idx]
        
        # Method 2: Maximum derivative (rapid change)
        dv = np.diff(v_shunt)
        if pulse_amplitude > 0:
            # Look for maximum positive derivative
            rapid_change_idx = np.argmax(dv)
        else:
            # Look for maximum negative derivative
            rapid_change_idx = np.argmin(dv)
        
        if rapid_change_idx > 0 and rapid_change_idx < len(t) - 1:
            # Verify this is a significant change (not noise)
            if abs(dv[rapid_change_idx]) > abs(pulse_amplitude) * 0.1:
                return t[rapid_change_idx]
        
        # Detection failed
        return None
    
    def _calculate_shunt(self):
        """Calculate recommended shunt resistor values based on device parameters"""
        try:
            # Get inputs
            voltage = float(self.vars['calc_voltage'].get())
            current = float(self.vars['calc_current'].get())
            rule_pct = float(self.vars['calc_rule'].get())  # 1 or 10
            
            if current == 0:
                self.vars['calc_result'].set("⚠️ Error: Current cannot be zero")
                return
            
            # Calculate device resistance
            r_device = voltage / current
            
            # Calculate recommended shunt value based on selected rule
            r_shunt_target = r_device * (rule_pct / 100.0)
            
            # Calculate voltage drop
            v_drop = current * r_shunt_target
            
            # Find nearest standard resistor values
            # Standard E12 series: 1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2
            # Multiplied by powers of 10
            e12_base = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]
            
            # Find appropriate decade
            if r_shunt_target < 1e-3:
                decade = 1e-6  # µΩ range (unlikely)
                r_range = [r * 1e-6 for r in e12_base[:3]]  # Only smallest values
            elif r_shunt_target < 1:
                decade = 1e-3  # mΩ range
                r_range = [r * 1e-3 for r in e12_base]
            elif r_shunt_target < 1e3:
                decade = 1  # Ω range
                r_range = [r for r in e12_base]
            elif r_shunt_target < 1e6:
                decade = 1e3  # kΩ range
                r_range = [r * 1e3 for r in e12_base]
            else:
                decade = 1e6  # MΩ range
                r_range = [r * 1e6 for r in e12_base[:6]]  # Only smaller values
            
            # Find closest standard values (above and below target)
            r_range_sorted = sorted(r_range)
            r_below = None
            r_above = None
            
            for r in r_range_sorted:
                if r <= r_shunt_target:
                    r_below = r
                elif r > r_shunt_target and r_above is None:
                    r_above = r
                    break
            
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
            def format_resistance(r):
                if r >= 1e6:
                    return f"{r/1e6:.2f} MΩ"
                elif r >= 1e3:
                    return f"{r/1e3:.2f} kΩ"
                elif r >= 1:
                    return f"{r:.2f} Ω"
                elif r >= 1e-3:
                    return f"{r*1e3:.2f} mΩ"
                else:
                    return f"{r:.2e} Ω"
            
            r_device_str = format_resistance(r_device)
            r_target_str = format_resistance(r_shunt_target)
            
            # Build result string
            result = (
                f"Device: {r_device_str} @ {voltage}V ({i_str})\n"
                f"\n"
                f"{rule_pct:.0f}% Rule: R_shunt = {r_target_str}  →  {v_drop*1e3:.2f} mV signal\n"
                f"\n"
            )
            
            # Add standard resistor recommendations
            if r_below or r_above:
                result += "Standard Resistor Options:\n"
                if r_below:
                    v_below = current * r_below
                    result += f"  • {format_resistance(r_below)} → {v_below*1e3:.2f} mV\n"
                if r_above:
                    v_above = current * r_above
                    result += f"  • {format_resistance(r_above)} → {v_above*1e3:.2f} mV\n"
                result += "\n"
                
                # Auto-select closest standard value
                if r_below and r_above:
                    if abs(r_shunt_target - r_below) < abs(r_shunt_target - r_above):
                        selected_r = r_below
                    else:
                        selected_r = r_above
                elif r_below:
                    selected_r = r_below
                else:
                    selected_r = r_above
                
                result += f"✅ Recommended: {format_resistance(selected_r)}"
                # Auto-fill r_shunt field
                self.vars['r_shunt'].set(f"{selected_r:.2f}")
            else:
                result += f"✅ Use: {r_target_str}"
                self.vars['r_shunt'].set(f"{r_shunt_target:.2f}")
            
            # Check if signal is too small
            if v_drop < 0.001:  # Less than 1 mV
                result += "\n⚠️ Signal < 1mV - consider using TIA instead"
            
            self.vars['calc_result'].set(result)
            
        except ValueError:
            self.vars['calc_result'].set("⚠️ Error: Please enter valid numbers")
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
        """Reset plot to empty state"""
        if not hasattr(self, 'plot_lines') or 'Main' not in self.plot_lines:
            return
        
        plot_info = self.plot_lines['Main']
        ax = plot_info['ax']
        ax.clear()
        ax.set_xlabel("Time (s)", fontsize=11)
        ax.set_ylabel("Voltage (V)", fontweight='bold', fontsize=12)
        ax.set_title("Voltage Overlay: V_SMU (Programmed) vs V_shunt (Measured) vs V_DUT (Calculated)", 
                    fontsize=12, fontweight='bold', pad=10)
        ax.grid(True, alpha=0.3)
        plot_info['canvas'].draw()
        
    def update_plots(self, t, v, i, metadata=None):
        """Update plots with new data - works with tabbed interface
        
        MEASUREMENT MODEL EXPLANATION:
        ===============================
        In this setup, we measure V_shunt across a series shunt resistor using the oscilloscope.
        The SMU applies a programmed pulse V_SMU, which gets divided between the device and shunt.
        
        Circuit: [SMU+] → [Device] → [Shunt R] → [SMU-]
                                         ↓
                                    [Scope CH1]
        
        What we MEASURE:
            • V_shunt = Voltage across shunt resistor (measured by oscilloscope)
        
        What we CALCULATE:
            • I = V_shunt / R_shunt (current through circuit - Ohm's law)
            • V_DUT = V_SMU - V_shunt (voltage across device - Kirchhoff's voltage law)
            • R_DUT = V_DUT / I (device resistance - Ohm's law)
            • P_DUT = V_DUT × I (power dissipated in device)
        
        What is V_SMU?
            • V_SMU is the PROGRAMMED voltage from the SMU (what we commanded it to output)
            • It is RECONSTRUCTED from pulse parameters (pulse_voltage, bias_voltage, timing)
            • It is NOT directly measured - we only have one scope channel measuring V_shunt
            • It represents an IDEALIZED reference waveform for comparison
            • In reality, the SMU output may have rise times, overshoot, etc.
        
        Alignment:
            • The pulse start time is auto-detected from the measured V_shunt waveform
            • V_SMU is then drawn starting at this detected time for alignment
            • Use the Alignment tab to manually adjust if auto-detection fails
        
        Args:
            t: Time array (from oscilloscope)
            v: Voltage array (V_shunt from oscilloscope)
            i: Current array (pre-calculated as V_shunt / R_shunt)
            metadata: Dictionary containing pulse parameters and measurement info
        """
        if not hasattr(self, 'plot_lines'):
            return
        
        # Get metadata
        if metadata is None:
            metadata = {}

        # Normalize time to start at 0s
        if t is not None and len(t) > 0:
            t = t - t[0]
        
        # ---- Extract pulse parameters from metadata ----
        pulse_voltage = metadata.get('pulse_voltage', 1.0)
        pulse_duration = metadata.get('pulse_duration', 0.001)
        bias_voltage = float(metadata.get('bias_voltage', 0.2))
        pre_bias_time = float(metadata.get('pre_bias_time', 0.1))
        post_bias_time = float(metadata.get('post_bias_time', 0.1))
        
        # If original params dict is present, prefer those (they come directly from the GUI)
        if 'params' in metadata:
            params = metadata['params']
            try:
                pulse_voltage = float(params.get('pulse_voltage', pulse_voltage))
            except (TypeError, ValueError):
                pass
            try:
                pulse_duration = float(params.get('pulse_duration', pulse_duration))
            except (TypeError, ValueError):
                pass
            try:
                bias_voltage = float(params.get('bias_voltage', bias_voltage))
            except (TypeError, ValueError):
                pass
            try:
                pre_bias_time = float(params.get('pre_bias_time', pre_bias_time))
            except (TypeError, ValueError):
                pass
            try:
                post_bias_time = float(params.get('post_bias_time', post_bias_time))
            except (TypeError, ValueError):
                pass
        
        # ---- Detect pulse start from measured waveform ----
        # This is where we detect the ACTUAL pulse start in the measured data
        detected_start = self._detect_pulse_start_improved(t, v, bias_voltage, pulse_voltage)
        if detected_start is None:
            # Fallback: use pre_bias_time as expected start
            detected_start = pre_bias_time
        
        # Store detected start for alignment tools
        metadata['pulse_start_time'] = detected_start
        
        pulse_start = detected_start
        pulse_end = pulse_start + pulse_duration
        
        v_shunt = v
        v_smu = self._create_v_smu_waveform(
            t, pulse_start, pulse_end, bias_voltage, pulse_voltage,
            pre_bias_time, post_bias_time
        ) if len(v_shunt) > 0 else np.array([])
        
        # V_memristor = V_SMU - V_shunt (Kirchhoff's voltage law)
        # Note: Can be negative for negative pulses - this is correct!
        v_memristor = v_smu - v_shunt
        
        # R_memristor = V_memristor / I (Ohm's law)
        # Note: Resistance magnitude should be positive, but sign indicates current direction
        with np.errstate(divide='ignore', invalid='ignore'):
            r_memristor = np.divide(v_memristor, i, out=np.full_like(v_memristor, np.nan), where=i!=0)
            r_memristor = np.where(np.isfinite(r_memristor) & (r_memristor < 1e12), r_memristor, np.nan)
        
        # P_memristor = V_memristor × I 
        # For resistive devices: power dissipation is positive when V and I have same sign
        # Negative power would indicate measurement/calculation issue
        p_memristor = v_memristor * i
        
        # Store data for line visibility toggles and calculations
        self.plot_data = {
            't': t, 'v_smu': v_smu, 'v_shunt': v_shunt, 'v_memristor': v_memristor,
            'i': i, 'r_memristor': r_memristor, 'p_memristor': p_memristor,
            'metadata': metadata
        }
        
        # Update main voltage overlay plot
        self._update_main_plot()
    
    def _update_main_plot(self):
        """Update main voltage overlay plot with clear annotations"""
        if 'Main' not in self.plot_lines:
            return
        
        plot_info = self.plot_lines['Main']
        ax = plot_info['ax']
        
        t = self.plot_data['t']
        v_smu = self.plot_data['v_smu']
        v_shunt = self.plot_data['v_shunt']
        v_memristor = self.plot_data['v_memristor']
        
        # Clear plot
        ax.clear()
        
        # Plot all three traces
        line1 = ax.plot(t, v_smu, 'g--', label='V_SMU (Programmed)', linewidth=2.5, alpha=0.7)[0]
        line2 = ax.plot(t, v_shunt, 'b-', label='V_shunt (Measured from Scope)', linewidth=2, alpha=0.9)[0]
        line3 = ax.plot(t, v_memristor, 'r-', label='V_DUT (Across Device)', linewidth=2, alpha=0.8)[0]
        
        # Store line references
        plot_info['lines'] = {
            'V_SMU': line1,
            'V_shunt': line2,
            'V_DUT': line3
        }
        
        # Styling
        ax.set_ylabel("Voltage (V)", fontweight='bold', fontsize=12)
        ax.set_title("Voltage Overlay: Compare Programmed vs Measured vs Calculated", 
                    fontsize=12, fontweight='bold', pad=10)
        ax.set_xlabel("Time (s)", fontsize=11)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='best', fontsize=10, framealpha=0.9)
        
        # Add helpful annotation
        if len(t) > 0 and len(v_smu) > 0:
            max_v = max(np.max(v_smu) if len(v_smu) > 0 else 0,
                       np.max(v_shunt) if len(v_shunt) > 0 else 0)
            if max_v > 0:
                ax.text(0.5, 0.98, 
                       'V_SMU (green dashed) = Programmed reference | V_shunt (blue) = Raw scope data | V_DUT (red) = V_SMU - V_shunt', 
                       transform=ax.transAxes,
                       fontsize=8, style='italic', ha='center', va='top',
                       bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.3))
        
        # Calculate and display key metrics
        shunt_r = self.plot_data.get('metadata', {}).get('shunt_resistance', 100000.0)
        i = self.plot_data['i']
        
        if len(i) > 0:
            peak_current = np.nanmax(np.abs(i))
            mean_current = np.nanmean(np.abs(i[i != 0])) if np.any(i != 0) else 0.0
            
            metrics_text = f"Peak I: {peak_current*1e6:.2f} µA | Mean I: {mean_current*1e6:.2f} µA | R_shunt: {shunt_r/1e3:.1f} kΩ"
            ax.text(0.02, 0.02, metrics_text,
                   transform=ax.transAxes,
                   fontsize=9, ha='left', va='bottom',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
        
        plot_info['fig'].tight_layout()
        plot_info['canvas'].draw()
    
    def _update_overview_tab(self):
        """Update overview tab with all plots"""
        if 'Overview' not in self.plot_lines:
            return
        
        plot_info = self.plot_lines['Overview']
        axes = plot_info['axes']
        
        t = self.plot_data['t']
        v_smu = self.plot_data['v_smu']
        v_shunt = self.plot_data['v_shunt']
        v_memristor = self.plot_data['v_memristor']
        i = self.plot_data['i']
        r_memristor = self.plot_data['r_memristor']
        p_memristor = self.plot_data['p_memristor']
        
        # Clear all axes
        for ax in axes.values():
            ax.clear()
        
        # Plot 1: Voltage Breakdown with clear annotations
        axes['voltage'].plot(t, v_smu, 'g--', label='V_SMU (Programmed Reference)', linewidth=2.5, alpha=0.7)
        axes['voltage'].plot(t, v_shunt, 'b-', label='V_shunt (Measured from Scope)', linewidth=2, alpha=0.9)
        axes['voltage'].plot(t, v_memristor, 'r-', label='V_DUT (Across Device)', linewidth=2, alpha=0.8)
        axes['voltage'].set_ylabel("Voltage (V)", fontweight='bold')
        axes['voltage'].set_title("Voltage Distribution\nV_SMU (dashed) = Programmed | V_shunt (blue) = Measured | V_DUT (red) = Calculated", 
                                  fontsize=10, fontweight='bold')
        axes['voltage'].set_xlabel("Time (s)")
        axes['voltage'].grid(True, alpha=0.3)
        axes['voltage'].legend(loc='best', fontsize=8)
        
        # Add annotation explaining V_SMU
        if len(t) > 0:
            # Find a good spot for annotation (middle of plot)
            mid_t = t[len(t) // 2]
            max_v = max(np.max(v_smu) if len(v_smu) > 0 else 0, 
                       np.max(v_shunt) if len(v_shunt) > 0 else 0)
            if max_v > 0:
                axes['voltage'].text(mid_t, max_v * 0.95, 
                                    'Note: V_SMU is reconstructed from parameters (not measured)', 
                                    fontsize=7, style='italic', ha='center',
                                    bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.3))
        
        # Plot 2: Current
        axes['current'].plot(t, i, 'r-', linewidth=2, label='Current')
        axes['current'].set_ylabel("Current (A)")
        axes['current'].set_title("Current Through Circuit (I = V_shunt / R_shunt)", fontsize=11, fontweight='bold')
        axes['current'].set_xlabel("Time (s)")
        axes['current'].grid(True, alpha=0.3)
        axes['current'].legend(loc='best', fontsize=8)
        
        # Plot 3: Resistance
        valid_mask = ~np.isnan(r_memristor) & np.isfinite(r_memristor)
        if np.any(valid_mask):
            r_plot = r_memristor[valid_mask]
            t_plot = t[valid_mask]
            
            # Convert to appropriate units
            if np.max(r_plot) >= 1e6:
                r_plot_display = r_plot / 1e6
                unit = "MΩ"
            elif np.max(r_plot) >= 1e3:
                r_plot_display = r_plot / 1e3
                unit = "kΩ"
            else:
                r_plot_display = r_plot
                unit = "Ω"
            
            axes['resistance'].plot(t_plot, r_plot_display, 'purple', linewidth=2, label=f'R_memristor ({unit})')
            
            # Add annotations
            if len(r_plot) > 0:
                initial_r = r_plot[0]
                final_r = r_plot[-1]
                
                def format_r(r_val):
                    if r_val >= 1e6:
                        return f"{r_val/1e6:.2f} MΩ"
                    elif r_val >= 1e3:
                        return f"{r_val/1e3:.2f} kΩ"
                    else:
                        return f"{r_val:.2f} Ω"
                
                axes['resistance'].annotate(f'Initial: {format_r(initial_r)}', 
                                           xy=(t_plot[0], r_plot_display[0]), 
                                           xytext=(10, 10), textcoords='offset points',
                                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                                           arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'),
                                           fontsize=7)
                
                if abs(final_r - initial_r) / max(abs(initial_r), 1e-12) > 0.01:
                    axes['resistance'].annotate(f'Final: {format_r(final_r)}', 
                                               xy=(t_plot[-1], r_plot_display[-1]), 
                                               xytext=(10, -20), textcoords='offset points',
                                               bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7),
                                               arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'),
                                               fontsize=7)
            
            axes['resistance'].set_ylabel(f"Resistance ({unit})")
        else:
            axes['resistance'].set_ylabel("Resistance (Ω)")
        
        axes['resistance'].set_title("Memristor Resistance: R = (V_SMU - V_shunt) / I", fontsize=11, fontweight='bold')
        axes['resistance'].set_xlabel("Time (s)")
        axes['resistance'].grid(True, alpha=0.3)
        axes['resistance'].legend(loc='best', fontsize=8)
        
        # Plot 4: Power
        axes['power'].plot(t, p_memristor, 'orange', linewidth=2, label='Power')
        
        # Add peak power annotation
        if len(p_memristor) > 0:
            peak_power_idx = np.nanargmax(p_memristor)
            peak_power = p_memristor[peak_power_idx]
            if peak_power > 0:
                axes['power'].annotate(f'Peak: {peak_power*1e3:.2f} mW', 
                                      xy=(t[peak_power_idx], peak_power), 
                                      xytext=(10, 10), textcoords='offset points',
                                      bbox=dict(boxstyle='round,pad=0.3', facecolor='orange', alpha=0.7),
                                      arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'),
                                      fontsize=7)
        
        axes['power'].set_ylabel("Power (W)")
        axes['power'].set_title("Power Dissipation in Memristor: P = V_memristor × I", fontsize=11, fontweight='bold')
        axes['power'].set_xlabel("Time (s)")
        axes['power'].grid(True, alpha=0.3)
        axes['power'].legend(loc='best', fontsize=8)
        
        plot_info['canvas'].draw()
    
    def _update_voltage_tab(self):
        """Update voltage breakdown tab"""
        if 'Voltage Breakdown' not in self.plot_lines:
            return
        
        plot_info = self.plot_lines['Voltage Breakdown']
        ax = plot_info['ax']
        ax.clear()
        
        t = self.plot_data['t']
        v_smu = self.plot_data['v_smu']
        v_shunt = self.plot_data['v_shunt']
        v_memristor = self.plot_data['v_memristor']
        
        # Plot lines and store references
        line1 = ax.plot(t, v_smu, 'g--', label='V_SMU (Programmed Reference)', linewidth=2.5, alpha=0.7)[0]
        line2 = ax.plot(t, v_shunt, 'b-', label='V_shunt (Measured from Scope)', linewidth=2, alpha=0.9)[0]
        line3 = ax.plot(t, v_memristor, 'r-', label='V_DUT (Across Device)', linewidth=2, alpha=0.8)[0]
        
        plot_info['lines'] = {
            'V_SMU': line1,
            'V_shunt': line2,
            'V_DUT': line3
        }
        
        ax.set_ylabel("Voltage (V)", fontweight='bold')
        ax.set_title("Voltage Distribution\nV_SMU (dashed green) = Programmed Pulse | V_shunt (blue) = Measured Scope | V_DUT (red) = Across Device", 
                    fontsize=11, fontweight='bold')
        ax.set_xlabel("Time (s)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)
        
        # Add explanatory note
        if len(t) > 0 and len(v_smu) > 0:
            max_v = max(np.max(v_smu), np.max(v_shunt) if len(v_shunt) > 0 else 0)
            if max_v > 0:
                ax.text(t[len(t)//2], max_v * 0.95, 
                       'V_SMU is reconstructed from pulse parameters (idealized reference)', 
                       fontsize=8, style='italic', ha='center',
                       bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.3))
        
        # Add checkboxes for line visibility
        self._add_line_visibility_controls('Voltage Breakdown', ['V_SMU', 'V_shunt', 'V_DUT'])
        
        plot_info['canvas'].draw()
    
    def _update_current_tab(self):
        """Update current tab"""
        if 'Current' not in self.plot_lines:
            return
        
        plot_info = self.plot_lines['Current']
        ax = plot_info['ax']
        ax.clear()
        
        t = self.plot_data['t']
        i = self.plot_data['i']
        
        line = ax.plot(t, i, 'r-', label='Current', linewidth=2)[0]
        plot_info['lines'] = {'Current': line}
        
        ax.set_ylabel("Current (A)")
        ax.set_title("Current Through Circuit (I = V_shunt / R_shunt)", fontsize=12, fontweight='bold')
        ax.set_xlabel("Time (s)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)
        
        self._add_line_visibility_controls('Current', ['Current'])
        plot_info['canvas'].draw()
    
    def _update_resistance_tab(self):
        """Update resistance tab"""
        if 'Resistance' not in self.plot_lines:
            return
        
        plot_info = self.plot_lines['Resistance']
        ax = plot_info['ax']
        ax.clear()
        
        t = self.plot_data['t']
        r_memristor = self.plot_data['r_memristor']
        
        valid_mask = ~np.isnan(r_memristor) & np.isfinite(r_memristor)
        if np.any(valid_mask):
            r_plot = r_memristor[valid_mask]
            t_plot = t[valid_mask]
            
            # Convert to appropriate units
            if np.max(r_plot) >= 1e6:
                r_plot_display = r_plot / 1e6
                unit = "MΩ"
            elif np.max(r_plot) >= 1e3:
                r_plot_display = r_plot / 1e3
                unit = "kΩ"
            else:
                r_plot_display = r_plot
                unit = "Ω"
            
            line = ax.plot(t_plot, r_plot_display, 'purple', linewidth=2, label=f'R_memristor ({unit})')[0]
            plot_info['lines'] = {'R_memristor': line}
            
            # Add annotations
            if len(r_plot) > 0:
                initial_r = r_plot[0]
                final_r = r_plot[-1]
                
                def format_r(r_val):
                    if r_val >= 1e6:
                        return f"{r_val/1e6:.2f} MΩ"
                    elif r_val >= 1e3:
                        return f"{r_val/1e3:.2f} kΩ"
                    else:
                        return f"{r_val:.2f} Ω"
                
                ax.annotate(f'Initial: {format_r(initial_r)}', 
                           xy=(t_plot[0], r_plot_display[0]), 
                           xytext=(10, 10), textcoords='offset points',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                           arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'),
                           fontsize=8)
                
                if abs(final_r - initial_r) / max(abs(initial_r), 1e-12) > 0.01:
                    ax.annotate(f'Final: {format_r(final_r)}', 
                               xy=(t_plot[-1], r_plot_display[-1]), 
                               xytext=(10, -20), textcoords='offset points',
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7),
                               arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'),
                               fontsize=8)
            
            ax.set_ylabel(f"Resistance ({unit})")
        else:
            plot_info['lines'] = {}
            ax.set_ylabel("Resistance (Ω)")
        
        ax.set_title("Memristor Resistance: R = (V_SMU - V_shunt) / I", fontsize=12, fontweight='bold')
        ax.set_xlabel("Time (s)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)
        
        self._add_line_visibility_controls('Resistance', ['R_memristor'])
        plot_info['canvas'].draw()
    
    def _update_power_tab(self):
        """Update power tab"""
        if 'Power' not in self.plot_lines:
            return
        
        plot_info = self.plot_lines['Power']
        ax = plot_info['ax']
        ax.clear()
        
        t = self.plot_data['t']
        p_memristor = self.plot_data['p_memristor']
        
        line = ax.plot(t, p_memristor, 'orange', linewidth=2, label='Power')[0]
        plot_info['lines'] = {'Power': line}
        
        # Add peak power annotation
        if len(p_memristor) > 0:
            peak_power_idx = np.nanargmax(p_memristor)
            peak_power = p_memristor[peak_power_idx]
            if peak_power > 0:
                ax.annotate(f'Peak: {peak_power*1e3:.2f} mW', 
                           xy=(t[peak_power_idx], peak_power), 
                           xytext=(10, 10), textcoords='offset points',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='orange', alpha=0.7),
                           arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'),
                           fontsize=8)
        
        ax.set_ylabel("Power (W)")
        ax.set_title("Power Dissipation in Memristor: P = V_memristor × I", fontsize=12, fontweight='bold')
        ax.set_xlabel("Time (s)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)
        
        self._add_line_visibility_controls('Power', ['Power'])
        plot_info['canvas'].draw()
    
    def _add_line_visibility_controls(self, tab_name, line_names):
        """Add checkboxes to toggle line visibility"""
        if tab_name not in self.plot_lines:
            return
        
        plot_info = self.plot_lines[tab_name]
        control_frame = plot_info['control_frame']
        
        # Clear existing checkboxes
        for widget in control_frame.winfo_children():
            widget.destroy()
        
        ttk.Label(control_frame, text="Show:", font=("Segoe UI", 9)).pack(side="left", padx=5)
        
        # Create checkboxes for each line
        for line_name in line_names:
            if line_name in plot_info['lines']:
                var = tk.BooleanVar(value=True)
                cb = ttk.Checkbutton(control_frame, text=line_name, variable=var,
                                    command=lambda ln=line_name, v=var: self._toggle_line_visibility(tab_name, ln, v))
                cb.pack(side="left", padx=5)
                plot_info['checkboxes'][line_name] = var
    
    def _toggle_line_visibility(self, tab_name, line_name, var):
        """Toggle visibility of a plot line"""
        if tab_name not in self.plot_lines:
            return
        if line_name not in self.plot_lines[tab_name]['lines']:
            return
        
        line = self.plot_lines[tab_name]['lines'][line_name]
        line.set_visible(var.get())
        self.plot_lines[tab_name]['canvas'].draw()

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
