"""
Custom Measurements Builder and Visualizer
==========================================

This module provides a comprehensive interface for building, editing, and visualizing
custom measurement configurations for the IV Measurement System GUI.

Purpose:
--------
The CustomMeasurementsBuilder class creates a user-friendly interface within the
Custom Measurements tab that allows users to:
- Create new custom measurement sequences
- Edit existing measurements
- Visualize measurement patterns (voltage sweeps, endurance cycles, retention tests)
- Save/load measurements from JSON configuration files

Key Features:
-------------
- Interactive builder UI with dynamic parameter fields based on measurement type
- Real-time visualization of voltage sweep patterns
- Support for multiple measurement types: IV, Endurance, Retention, PulsedIV, FastPulses, Hold
- Visual preview graphs showing expected measurement sequences
- Parameter summary display
- LED control integration
- JSON-based persistence

Usage:
------
The builder is automatically integrated into the Custom Measurements tab via
layout_builder.py. Users can access it by navigating to the "Custom Measurements"
tab in the main GUI.

File Structure:
--------------
- Left Panel: Measurement list and builder form
- Right Panel: Visualization graphs and summary text
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class CustomMeasurementsBuilder:
    """
    Builder interface for creating and editing custom measurement configurations.
    Includes visualization of sweep patterns and measurement sequences.
    """
    
    COLOR_PRIMARY = "#4CAF50"
    COLOR_SECONDARY = "#888888"
    COLOR_BG_INFO = "#f0f0f0"
    COLOR_SUCCESS = "#4CAF50"
    COLOR_ERROR = "#F44336"
    COLOR_WARNING = "#FFA500"
    COLOR_INFO = "#569CD6"
    
    FONT_MAIN = ("Segoe UI", 9)
    FONT_HEADING = ("Segoe UI", 10, "bold")
    FONT_LARGE = ("Segoe UI", 12, "bold")
    FONT_BUTTON = ("Segoe UI", 9, "bold")
    
    def __init__(self, parent: tk.Misc, gui_instance: object, json_path: str = "Json_Files/Custom_Sweeps.json"):
        """
        Initialize the custom measurements builder.
        
        Args:
            parent: Parent widget to attach the builder to
            gui_instance: Reference to the main GUI instance
            json_path: Path to the custom sweeps JSON file
        """
        self.parent = parent
        self.gui = gui_instance
        self.json_path = Path(json_path)
        self.custom_sweeps: Dict[str, Dict[str, Any]] = {}
        self.selected_measurement: Optional[str] = None
        
        # Load existing custom sweeps
        self.load_custom_sweeps()
        
        # Build the UI
        self._build_ui()
    
    def load_custom_sweeps(self) -> None:
        """Load custom sweeps from JSON file."""
        if not self.json_path.exists():
            print(f"[Custom Sweeps] Config not found at {self.json_path}, using empty dict.")
            self.custom_sweeps = {}
            return
        
        try:
            with self.json_path.open("r", encoding="utf-8") as f:
                self.custom_sweeps = json.load(f)
        except Exception as e:
            print(f"[Custom Sweeps] Failed to load {self.json_path}: {e}")
            self.custom_sweeps = {}
    
    def save_custom_sweeps(self) -> bool:
        """Save custom sweeps to JSON file."""
        try:
            # Ensure directory exists
            self.json_path.parent.mkdir(parents=True, exist_ok=True)
            
            with self.json_path.open("w", encoding="utf-8") as f:
                json.dump(self.custom_sweeps, f, indent=2, ensure_ascii=False)
            
            # Reload in GUI if it has the method
            if hasattr(self.gui, 'load_custom_sweeps'):
                self.gui.custom_sweeps = self.gui.load_custom_sweeps(str(self.json_path))
                self.gui.test_names = list(self.gui.custom_sweeps.keys())
                if hasattr(self.gui, 'custom_measurement_menu'):
                    self.gui.custom_measurement_menu['values'] = self.gui.test_names
            
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save custom sweeps:\n{e}")
            return False
    
    def _build_ui(self) -> None:
        """Build the main UI layout."""
        # Main container with two columns: left (list + builder), right (visualization)
        main_frame = tk.Frame(self.parent, bg='white')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left panel smaller (30%), right panel larger (70%)
        main_frame.columnconfigure(0, weight=3, minsize=400)
        main_frame.columnconfigure(1, weight=7, minsize=700)
        main_frame.rowconfigure(0, weight=1)
        
        # LEFT PANEL: List and Builder
        left_panel = self._build_left_panel(main_frame)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        # RIGHT PANEL: Visualization
        right_panel = self._build_right_panel(main_frame)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
    
    def _build_left_panel(self, parent: tk.Misc) -> tk.Frame:
        """Build the left panel with measurement list and builder."""
        panel = tk.Frame(parent, bg='white')
        
        # Top section: Measurement list (smaller)
        list_frame = tk.LabelFrame(
            panel,
            text="Custom Measurements",
            font=self.FONT_HEADING,
            bg='white',
            padx=10,
            pady=10
        )
        list_frame.pack(fill='both', expand=False, pady=(0, 10))
        list_frame.configure(height=150)  # Fixed smaller height
        
        # Listbox with scrollbar
        list_container = tk.Frame(list_frame, bg='white')
        list_container.pack(fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(list_container)
        scrollbar.pack(side='right', fill='y')
        
        self.measurement_listbox = tk.Listbox(
            list_container,
            font=self.FONT_MAIN,
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE
        )
        self.measurement_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.measurement_listbox.yview)
        
        self.measurement_listbox.bind('<<ListboxSelect>>', self._on_measurement_select)
        
        # Buttons for list management
        list_btn_frame = tk.Frame(list_frame, bg='white')
        list_btn_frame.pack(fill='x', pady=(10, 0))
        
        tk.Button(
            list_btn_frame,
            text="New",
            font=self.FONT_BUTTON,
            bg=self.COLOR_PRIMARY,
            fg='white',
            command=self._create_new_measurement,
            padx=15,
            pady=5
        ).pack(side='left', padx=(0, 5))
        
        tk.Button(
            list_btn_frame,
            text="Delete",
            font=self.FONT_BUTTON,
            bg=self.COLOR_ERROR,
            fg='white',
            command=self._delete_measurement,
            padx=15,
            pady=5
        ).pack(side='left', padx=5)
        
        tk.Button(
            list_btn_frame,
            text="Duplicate",
            font=self.FONT_BUTTON,
            bg=self.COLOR_INFO,
            fg='white',
            command=self._duplicate_measurement,
            padx=15,
            pady=5
        ).pack(side='left', padx=5)
        
        # Bottom section: Builder form (larger)
        builder_frame = tk.LabelFrame(
            panel,
            text="Measurement Builder",
            font=self.FONT_HEADING,
            bg='white',
            padx=10,
            pady=10
        )
        builder_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        self._build_measurement_form(builder_frame)
        
        # Save button
        save_btn = tk.Button(
            panel,
            text="💾 Save All Measurements",
            font=self.FONT_LARGE,
            bg=self.COLOR_SUCCESS,
            fg='white',
            command=self._save_all,
            padx=20,
            pady=10
        )
        save_btn.pack(fill='x', pady=(0, 5))
        
        # Refresh button
        refresh_btn = tk.Button(
            panel,
            text="🔄 Refresh List",
            font=self.FONT_BUTTON,
            bg=self.COLOR_INFO,
            fg='white',
            command=self._refresh_list,
            padx=15,
            pady=5
        )
        refresh_btn.pack(fill='x')
        
        self._refresh_list()
        
        return panel
    
    def _build_measurement_form(self, parent: tk.Frame) -> None:
        """Build the form for editing measurement parameters."""
        # Test name
        tk.Label(parent, text="Test Name:", font=self.FONT_MAIN, bg='white').grid(row=0, column=0, sticky='w', pady=5)
        self.test_name_var = tk.StringVar()
        test_name_entry = tk.Entry(parent, textvariable=self.test_name_var, font=self.FONT_MAIN, width=30)
        test_name_entry.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Code name
        tk.Label(parent, text="Code Name:", font=self.FONT_MAIN, bg='white').grid(row=1, column=0, sticky='w', pady=5)
        self.code_name_var = tk.StringVar()
        code_name_entry = tk.Entry(parent, textvariable=self.code_name_var, font=self.FONT_MAIN, width=30)
        code_name_entry.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        parent.columnconfigure(1, weight=1)
        
        # Sweeps section (will be populated dynamically)
        sweeps_label = tk.Label(parent, text="Sweeps:", font=self.FONT_HEADING, bg='white')
        sweeps_label.grid(row=2, column=0, columnspan=2, sticky='w', pady=(15, 5))
        
        # Scrollable sweeps list (larger)
        sweeps_container = tk.Frame(parent, bg='white', relief='solid', borderwidth=1)
        sweeps_container.grid(row=3, column=0, columnspan=2, sticky='nsew', pady=5)
        sweeps_container.columnconfigure(0, weight=1)
        sweeps_container.rowconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)  # Make sweeps section expandable
        
        sweeps_canvas = tk.Canvas(sweeps_container, bg='white', height=300, highlightthickness=0)
        sweeps_scrollbar = tk.Scrollbar(sweeps_container, orient="vertical", command=sweeps_canvas.yview)
        self.sweeps_scrollable = tk.Frame(sweeps_canvas, bg='white')
        
        self.sweeps_scrollable.bind(
            "<Configure>",
            lambda e: sweeps_canvas.configure(scrollregion=sweeps_canvas.bbox("all"))
        )
        
        sweeps_canvas.create_window((0, 0), window=self.sweeps_scrollable, anchor="nw")
        sweeps_canvas.configure(yscrollcommand=sweeps_scrollbar.set)
        
        sweeps_canvas.pack(side="left", fill="both", expand=True)
        sweeps_scrollbar.pack(side="right", fill="y")
        
        # Add sweep button
        add_sweep_btn = tk.Button(
            parent,
            text="+ Add Sweep",
            font=self.FONT_BUTTON,
            bg=self.COLOR_INFO,
            fg='white',
            command=self._add_sweep,
            padx=10,
            pady=5
        )
        add_sweep_btn.grid(row=4, column=0, columnspan=2, pady=(5, 0))
        
        self.sweeps_canvas = sweeps_canvas
        self.sweeps_widgets: List[Dict[str, tk.Widget]] = []
    
    def _build_right_panel(self, parent: tk.Misc) -> tk.Frame:
        """Build the right panel with visualizations."""
        panel = tk.Frame(parent, bg='white')
        
        # Title
        title = tk.Label(
            panel,
            text="Measurement Visualization",
            font=self.FONT_LARGE,
            bg='white',
            fg=self.COLOR_PRIMARY
        )
        title.pack(pady=(0, 10))
        
        # Visualization container
        viz_container = tk.Frame(panel, bg='white', relief='solid', borderwidth=2)
        viz_container.pack(fill='both', expand=True)
        
        # Create matplotlib figure for visualization
        self.viz_figure = Figure(figsize=(6, 5), facecolor='white')
        self.viz_canvas = FigureCanvasTkAgg(self.viz_figure, master=viz_container)
        self.viz_canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Summary text area
        summary_frame = tk.LabelFrame(
            panel,
            text="Measurement Summary",
            font=self.FONT_HEADING,
            bg='white',
            padx=10,
            pady=10
        )
        summary_frame.pack(fill='x', pady=(10, 0))
        
        self.summary_text = tk.Text(
            summary_frame,
            font=("Consolas", 9),
            bg='#f8f8f8',
            wrap=tk.WORD,
            height=8,
            state=tk.DISABLED
        )
        self.summary_text.pack(fill='both', expand=True)
        
        # Initial empty visualization
        self._show_empty_visualization()
        
        return panel
    
    def _refresh_list(self) -> None:
        """Refresh the measurement list."""
        self.measurement_listbox.delete(0, tk.END)
        for name in sorted(self.custom_sweeps.keys()):
            self.measurement_listbox.insert(tk.END, name)
    
    def _on_measurement_select(self, event: tk.Event) -> None:
        """Handle measurement selection."""
        selection = self.measurement_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        name = self.measurement_listbox.get(index)
        self.selected_measurement = name
        
        # Load measurement data into form
        if name in self.custom_sweeps:
            measurement = self.custom_sweeps[name]
            self.test_name_var.set(name)
            self.code_name_var.set(measurement.get("code_name", ""))
            
            # Load sweeps
            self._load_sweeps(measurement.get("sweeps", {}))
            
            # Update visualization
            self._visualize_measurement(name, measurement)
    
    def _load_sweeps(self, sweeps: Dict[str, Dict[str, Any]]) -> None:
        """Load sweeps into the form."""
        # Clear existing sweep widgets
        for widget_dict in self.sweeps_widgets:
            # Destroy the row_frame which will destroy all its child widgets
            if 'row_frame' in widget_dict:
                widget_dict['row_frame'].destroy()
        self.sweeps_widgets.clear()
        
        # Add sweeps
        for sweep_num, sweep_data in sorted(sweeps.items(), key=lambda x: int(x[0])):
            self._add_sweep_row(sweep_num, sweep_data)
    
    def _add_sweep(self) -> None:
        """Add a new sweep row."""
        # Find next available sweep number
        existing_nums = [int(w['num'].get()) for w in self.sweeps_widgets if w.get('num')]
        next_num = max(existing_nums) + 1 if existing_nums else 1
        
        self._add_sweep_row(str(next_num), {})
    
    def _add_sweep_row(self, sweep_num: str, sweep_data: Dict[str, Any]) -> None:
        """Add a sweep row to the form."""
        row_frame = tk.Frame(self.sweeps_scrollable, bg='white', relief='solid', borderwidth=1)
        row_frame.pack(fill='x', pady=2, padx=5)
        
        widgets = {'row_frame': row_frame}
        
        # Top row: Basic info
        top_row = tk.Frame(row_frame, bg='white')
        top_row.pack(fill='x', pady=2)
        
        # Sweep number
        tk.Label(top_row, text=f"Sweep {sweep_num}:", font=self.FONT_MAIN, bg='white', width=10).pack(side='left', padx=5)
        widgets['num'] = tk.StringVar(value=sweep_num)
        
        # Measurement type dropdown
        tk.Label(top_row, text="Type:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
        measurement_type = tk.StringVar(value=sweep_data.get("measurement_type", sweep_data.get("mode", "IV")))
        type_combo = ttk.Combobox(
            top_row,
            textvariable=measurement_type,
            values=["IV", "Endurance", "Retention", "PulsedIV", "FastPulses", "Hold"],
            state="readonly",
            width=12
        )
        type_combo.pack(side='left', padx=5)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._update_sweep_row_params(row_frame, widgets, measurement_type.get()))
        widgets['type'] = measurement_type
        
        # Delete button
        delete_btn = tk.Button(
            top_row,
            text="×",
            font=("Arial", 12, "bold"),
            bg=self.COLOR_ERROR,
            fg='white',
            command=lambda: self._remove_sweep_row(row_frame, widgets),
            width=3
        )
        delete_btn.pack(side='right', padx=5)
        widgets['delete_btn'] = delete_btn
        
        # Parameters row (will be updated based on type)
        params_row = tk.Frame(row_frame, bg='white')
        params_row.pack(fill='x', pady=2)
        widgets['params_row'] = params_row
        
        # Initialize parameters based on current type
        self._update_sweep_row_params(row_frame, widgets, measurement_type.get(), sweep_data)
        
        self.sweeps_widgets.append(widgets)
        self.sweeps_canvas.update_idletasks()
        self.sweeps_canvas.configure(scrollregion=self.sweeps_canvas.bbox("all"))
    
    def _update_sweep_row_params(self, row_frame: tk.Frame, widgets: Dict[str, tk.Widget], 
                                  measurement_type: str, sweep_data: Optional[Dict[str, Any]] = None) -> None:
        """Update parameter fields based on measurement type."""
        params_row = widgets.get('params_row')
        if not params_row:
            return
        
        # Clear existing parameter widgets
        for widget in params_row.winfo_children():
            widget.destroy()
        
        # Remove old parameter widgets from dict
        keys_to_remove = [k for k in widgets.keys() if k not in ['row_frame', 'num', 'type', 'delete_btn', 'params_row']]
        for k in keys_to_remove:
            del widgets[k]
        
        if sweep_data is None:
            sweep_data = {}
        
        if measurement_type == "IV":
            tk.Label(params_row, text="Start V:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            start_v = tk.StringVar(value=str(sweep_data.get("start_v", "0")))
            tk.Entry(params_row, textvariable=start_v, width=8).pack(side='left', padx=2)
            widgets['start_v'] = start_v
            
            tk.Label(params_row, text="Stop V:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            stop_v = tk.StringVar(value=str(sweep_data.get("stop_v", "1")))
            tk.Entry(params_row, textvariable=stop_v, width=8).pack(side='left', padx=2)
            widgets['stop_v'] = stop_v
            
            tk.Label(params_row, text="Step V:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            step_v = tk.StringVar(value=str(sweep_data.get("step_v", "0.1")))
            tk.Entry(params_row, textvariable=step_v, width=8).pack(side='left', padx=2)
            widgets['step_v'] = step_v
            
            tk.Label(params_row, text="Sweeps:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            sweeps = tk.StringVar(value=str(sweep_data.get("sweeps", "1")))
            tk.Entry(params_row, textvariable=sweeps, width=6).pack(side='left', padx=2)
            widgets['sweeps'] = sweeps
            
            tk.Label(params_row, text="Delay:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            step_delay = tk.StringVar(value=str(sweep_data.get("step_delay", "0.01")))
            tk.Entry(params_row, textvariable=step_delay, width=8).pack(side='left', padx=2)
            widgets['step_delay'] = step_delay
        
        elif measurement_type == "Endurance":
            tk.Label(params_row, text="Set V:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            set_v = tk.StringVar(value=str(sweep_data.get("set_v", "1.5")))
            tk.Entry(params_row, textvariable=set_v, width=8).pack(side='left', padx=2)
            widgets['set_v'] = set_v
            
            tk.Label(params_row, text="Reset V:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            reset_v = tk.StringVar(value=str(sweep_data.get("reset_v", "-1.5")))
            tk.Entry(params_row, textvariable=reset_v, width=8).pack(side='left', padx=2)
            widgets['reset_v'] = reset_v
            
            tk.Label(params_row, text="Pulse (ms):", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            pulse_ms = tk.StringVar(value=str(sweep_data.get("pulse_ms", "10")))
            tk.Entry(params_row, textvariable=pulse_ms, width=8).pack(side='left', padx=2)
            widgets['pulse_ms'] = pulse_ms
            
            tk.Label(params_row, text="Cycles:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            cycles = tk.StringVar(value=str(sweep_data.get("cycles", "100")))
            tk.Entry(params_row, textvariable=cycles, width=8).pack(side='left', padx=2)
            widgets['cycles'] = cycles
            
            tk.Label(params_row, text="Read V:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            read_v = tk.StringVar(value=str(sweep_data.get("read_v", "0.2")))
            tk.Entry(params_row, textvariable=read_v, width=8).pack(side='left', padx=2)
            widgets['read_v'] = read_v
        
        elif measurement_type == "Retention":
            tk.Label(params_row, text="Set V:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            set_v = tk.StringVar(value=str(sweep_data.get("set_v", "1.5")))
            tk.Entry(params_row, textvariable=set_v, width=8).pack(side='left', padx=2)
            widgets['set_v'] = set_v
            
            tk.Label(params_row, text="Set (ms):", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            set_ms = tk.StringVar(value=str(sweep_data.get("set_ms", "10")))
            tk.Entry(params_row, textvariable=set_ms, width=8).pack(side='left', padx=2)
            widgets['set_ms'] = set_ms
            
            tk.Label(params_row, text="Read V:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=5)
            read_v = tk.StringVar(value=str(sweep_data.get("read_v", "0.2")))
            tk.Entry(params_row, textvariable=read_v, width=8).pack(side='left', padx=2)
            widgets['read_v'] = read_v
        
        # LED controls (common to all types)
        led_frame = tk.Frame(params_row, bg='white')
        led_frame.pack(side='left', padx=10)
        
        tk.Label(led_frame, text="LED:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=2)
        led_on = tk.IntVar(value=int(sweep_data.get("LED_ON", 0)))
        
        def update_led_power():
            # Remove existing power widget if any
            widgets_to_remove = []
            for widget in led_frame.winfo_children():
                if isinstance(widget, tk.Entry):
                    widgets_to_remove.append(widget)
                elif isinstance(widget, tk.Label):
                    try:
                        if widget.cget("text") == "Power:":
                            widgets_to_remove.append(widget)
                    except:
                        pass
            
            for widget in widgets_to_remove:
                widget.destroy()
            
            # Remove power from widgets dict if it exists
            if 'power' in widgets:
                del widgets['power']
            
            if led_on.get():
                tk.Label(led_frame, text="Power:", font=self.FONT_MAIN, bg='white').pack(side='left', padx=2)
                power_val = sweep_data.get("power", "1.0") if 'power' not in widgets else widgets.get('power', tk.StringVar(value="1.0")).get()
                power = tk.StringVar(value=str(power_val))
                power_entry = tk.Entry(led_frame, textvariable=power, width=6)
                power_entry.pack(side='left', padx=2)
                widgets['power'] = power
        
        led_check = tk.Checkbutton(led_frame, variable=led_on, bg='white', command=update_led_power)
        led_check.pack(side='left', padx=2)
        widgets['LED_ON'] = led_on
        
        # Initialize LED power field if LED is on
        if led_on.get():
            update_led_power()
    
    def _remove_sweep_row(self, row_frame: tk.Frame, widgets: Dict[str, tk.Widget]) -> None:
        """Remove a sweep row."""
        row_frame.destroy()
        if widgets in self.sweeps_widgets:
            self.sweeps_widgets.remove(widgets)
    
    def _create_new_measurement(self) -> None:
        """Create a new measurement."""
        dialog = tk.Toplevel(self.parent)
        dialog.title("New Measurement")
        dialog.geometry("300x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        tk.Label(dialog, text="Measurement Name:", font=self.FONT_MAIN).pack(pady=10)
        name_var = tk.StringVar()
        tk.Entry(dialog, textvariable=name_var, font=self.FONT_MAIN, width=30).pack(pady=5)
        
        def create():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Please enter a measurement name.")
                return
            
            if name in self.custom_sweeps:
                messagebox.showerror("Error", f"Measurement '{name}' already exists.")
                return
            
            # Create new measurement
            self.custom_sweeps[name] = {
                "code_name": name.lower().replace(" ", "_"),
                "sweeps": {}
            }
            
            self._refresh_list()
            # Select the new measurement
            index = list(self.custom_sweeps.keys()).index(name)
            self.measurement_listbox.selection_set(index)
            self.measurement_listbox.see(index)
            self._on_measurement_select(None)
            
            dialog.destroy()
        
        tk.Button(dialog, text="Create", command=create, font=self.FONT_BUTTON, bg=self.COLOR_PRIMARY, fg='white').pack(pady=10)
    
    def _delete_measurement(self) -> None:
        """Delete selected measurement."""
        selection = self.measurement_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a measurement to delete.")
            return
        
        name = self.measurement_listbox.get(selection[0])
        
        if messagebox.askyesno("Confirm Delete", f"Delete measurement '{name}'?"):
            if name in self.custom_sweeps:
                del self.custom_sweeps[name]
                self._refresh_list()
                self._show_empty_visualization()
                self.test_name_var.set("")
                self.code_name_var.set("")
                self.sweeps_widgets.clear()
    
    def _duplicate_measurement(self) -> None:
        """Duplicate selected measurement."""
        selection = self.measurement_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a measurement to duplicate.")
            return
        
        name = self.measurement_listbox.get(selection[0])
        new_name = f"{name}_copy"
        
        if new_name in self.custom_sweeps:
            counter = 1
            while f"{name}_copy_{counter}" in self.custom_sweeps:
                counter += 1
            new_name = f"{name}_copy_{counter}"
        
        # Deep copy
        import copy
        self.custom_sweeps[new_name] = copy.deepcopy(self.custom_sweeps[name])
        self.custom_sweeps[new_name]["code_name"] = f"{self.custom_sweeps[new_name]['code_name']}_copy"
        
        self._refresh_list()
    
    def _save_all(self) -> None:
        """Save current measurement and all others."""
        # Save current measurement if one is selected
        if self.selected_measurement:
            self._save_current_measurement()
        
        # Save to file
        if self.save_custom_sweeps():
            messagebox.showinfo("Success", "Custom measurements saved successfully!")
    
    def _save_current_measurement(self) -> None:
        """Save the currently edited measurement."""
        if not self.selected_measurement:
            return
        
        name = self.test_name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Measurement name cannot be empty.")
            return
        
        code_name = self.code_name_var.get().strip()
        if not code_name:
            code_name = name.lower().replace(" ", "_")
        
        # If name changed, update the dictionary
        if name != self.selected_measurement:
            if name in self.custom_sweeps:
                messagebox.showerror("Error", f"Measurement '{name}' already exists.")
                return
            self.custom_sweeps[name] = self.custom_sweeps.pop(self.selected_measurement)
            self.selected_measurement = name
            self._refresh_list()
        
        # Collect sweeps
        sweeps = {}
        for widgets in self.sweeps_widgets:
            sweep_num = widgets['num'].get()
            sweep_type = widgets['type'].get()
            
            sweep_data = {"measurement_type": sweep_type}
            
            if sweep_type == "IV":
                if 'start_v' in widgets:
                    sweep_data.update({
                        "start_v": float(widgets['start_v'].get()),
                        "stop_v": float(widgets['stop_v'].get()),
                        "step_v": float(widgets['step_v'].get()),
                        "sweeps": int(widgets.get('sweeps', tk.StringVar(value="1")).get()),
                        "step_delay": float(widgets.get('step_delay', tk.StringVar(value="0.01")).get())
                    })
            
            elif sweep_type == "Endurance":
                sweep_data.update({
                    "set_v": float(widgets.get('set_v', tk.StringVar(value="1.5")).get()),
                    "reset_v": float(widgets.get('reset_v', tk.StringVar(value="-1.5")).get()),
                    "pulse_ms": float(widgets.get('pulse_ms', tk.StringVar(value="10")).get()),
                    "cycles": int(widgets.get('cycles', tk.StringVar(value="100")).get()),
                    "read_v": float(widgets.get('read_v', tk.StringVar(value="0.2")).get())
                })
            
            elif sweep_type == "Retention":
                sweep_data.update({
                    "set_v": float(widgets.get('set_v', tk.StringVar(value="1.5")).get()),
                    "set_ms": float(widgets.get('set_ms', tk.StringVar(value="10")).get()),
                    "read_v": float(widgets.get('read_v', tk.StringVar(value="0.2")).get()),
                    "times_s": [1, 3, 10, 30, 100, 300]  # Default retention times
                })
            
            # Add LED settings if present
            if 'LED_ON' in widgets:
                led_on = widgets['LED_ON'].get()
                sweep_data["LED_ON"] = led_on
                if led_on and 'power' in widgets:
                    sweep_data["power"] = float(widgets['power'].get())
            
            sweeps[sweep_num] = sweep_data
        
        self.custom_sweeps[name] = {
            "code_name": code_name,
            "sweeps": sweeps
        }
    
    def _visualize_measurement(self, name: str, measurement: Dict[str, Any]) -> None:
        """Visualize a measurement with graphs and summary."""
        self.viz_figure.clear()
        
        sweeps = measurement.get("sweeps", {})
        if not sweeps:
            self._show_empty_visualization()
            return
        
        # Create subplots
        ax1 = self.viz_figure.add_subplot(211)
        ax2 = self.viz_figure.add_subplot(212)
        
        # Plot 1: Voltage sweep pattern
        all_voltages = []
        all_times = []
        time_offset = 0
        
        # Track LED states for visualization
        led_states = []  # List of (time, led_on) tuples
        
        for sweep_num, sweep_data in sorted(sweeps.items(), key=lambda x: int(x[0])):
            measurement_type = sweep_data.get("measurement_type", sweep_data.get("mode", "IV"))
            led_on = bool(sweep_data.get("LED_ON", 0))
            
            if measurement_type == "IV" and "start_v" in sweep_data:
                start_v = sweep_data.get("start_v", 0)
                stop_v = sweep_data.get("stop_v", 1)
                step_v = sweep_data.get("step_v", 0.1)
                num_sweeps = sweep_data.get("sweeps", 1)
                step_delay = sweep_data.get("step_delay", 0.01)
                
                # Generate voltage sequence
                voltages = np.arange(start_v, stop_v + step_v/2, step_v)
                if stop_v < start_v:
                    voltages = np.arange(start_v, stop_v - step_v/2, -step_v)
                
                # Repeat for multiple sweeps
                for sweep_idx in range(num_sweeps):
                    sweep_voltages = voltages.copy()
                    sweep_times = time_offset + np.arange(len(sweep_voltages)) * step_delay
                    
                    all_voltages.extend(sweep_voltages)
                    all_times.extend(sweep_times)
                    
                    # Track LED state for this sweep
                    if len(sweep_times) > 0:
                        led_states.append((sweep_times[0], sweep_times[-1], led_on))
                    
                    if len(sweep_times) > 0:
                        time_offset = sweep_times[-1] + step_delay * 2  # Small gap between sweeps
            
            elif measurement_type == "Endurance":
                set_v = sweep_data.get("set_v", 1.5)
                reset_v = sweep_data.get("reset_v", -1.5)
                pulse_ms = sweep_data.get("pulse_ms", 10) / 1000  # Convert to seconds
                cycles = sweep_data.get("cycles", 100)
                
                # Create endurance pattern visualization
                for cycle in range(min(cycles, 10)):  # Limit to 10 cycles for visualization
                    # Set pulse
                    set_start = time_offset
                    all_voltages.extend([set_v, set_v])
                    all_times.extend([time_offset, time_offset + pulse_ms])
                    time_offset += pulse_ms
                    
                    # Reset pulse
                    reset_start = time_offset
                    all_voltages.extend([reset_v, reset_v])
                    all_times.extend([time_offset, time_offset + pulse_ms])
                    time_offset += pulse_ms
                    
                    # Track LED state for this cycle
                    led_states.append((set_start, time_offset, led_on))
            
            elif measurement_type == "Retention":
                set_v = sweep_data.get("set_v", 1.5)
                set_ms = sweep_data.get("set_ms", 10) / 1000
                read_v = sweep_data.get("read_v", 0.2)
                times_s = sweep_data.get("times_s", [1, 3, 10, 30, 100, 300])
                
                # Set pulse
                retention_start = time_offset
                all_voltages.extend([set_v, set_v])
                all_times.extend([time_offset, time_offset + set_ms])
                time_offset += set_ms
                
                # Read pulses at different times
                for t in times_s[:10]:  # Limit visualization
                    all_voltages.extend([read_v, read_v])
                    all_times.extend([time_offset, time_offset + t])
                    time_offset += t
                
                # Track LED state for retention test
                led_states.append((retention_start, time_offset, led_on))
        
        if all_voltages:
            # Plot voltage pattern
            ax1.plot(all_times, all_voltages, 'b-', linewidth=2, marker='o', markersize=3, label='Voltage')
            ax1.set_xlabel("Time (s)", fontsize=9)
            ax1.set_ylabel("Voltage (V)", fontsize=9)
            ax1.set_title("Voltage Sweep Pattern (Green shading = LED ON)", fontsize=10, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            
            # Add LED state visualization as background shading (only for LED ON)
            has_led_on = False
            if led_states:
                for start_time, end_time, led_on in led_states:
                    if led_on:  # Only show shading when LED is ON
                        ax1.axvspan(start_time, end_time, alpha=0.3, color='#90EE90')
                        has_led_on = True
            
            # Add legend if LED ON states exist
            if has_led_on:
                from matplotlib.patches import Patch
                legend_elements = [
                    Patch(facecolor='#90EE90', alpha=0.3, label='LED ON')
                ]
                ax1.legend(handles=legend_elements, loc='upper right', fontsize=8)
        
        # Plot 2: Sweep summary (bar chart of voltage ranges)
        sweep_nums = []
        start_voltages = []
        stop_voltages = []
        
        for sweep_num, sweep_data in sorted(sweeps.items(), key=lambda x: int(x[0])):
            if "start_v" in sweep_data:
                sweep_nums.append(int(sweep_num))
                start_voltages.append(sweep_data.get("start_v", 0))
                stop_voltages.append(sweep_data.get("stop_v", 0))
        
        if sweep_nums:
            x_pos = np.arange(len(sweep_nums))
            width = 0.35
            
            ax2.bar(x_pos - width/2, start_voltages, width, label='Start V', alpha=0.7)
            ax2.bar(x_pos + width/2, stop_voltages, width, label='Stop V', alpha=0.7)
            ax2.set_xlabel("Sweep Number", fontsize=9)
            ax2.set_ylabel("Voltage (V)", fontsize=9)
            ax2.set_title("Sweep Voltage Ranges", fontsize=10, fontweight='bold')
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels(sweep_nums)
            ax2.legend()
            ax2.grid(True, alpha=0.3, axis='y')
        
        self.viz_figure.tight_layout()
        self.viz_canvas.draw()
        
        # Update summary text
        self._update_summary(name, measurement)
    
    def _update_summary(self, name: str, measurement: Dict[str, Any]) -> None:
        """Update the summary text."""
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        
        sweeps = measurement.get("sweeps", {})
        summary = f"Measurement: {name}\n"
        summary += f"Code Name: {measurement.get('code_name', 'N/A')}\n"
        summary += f"Total Sweeps: {len(sweeps)}\n\n"
        
        for sweep_num, sweep_data in sorted(sweeps.items(), key=lambda x: int(x[0])):
            summary += f"Sweep {sweep_num}:\n"
            measurement_type = sweep_data.get("measurement_type", "IV")
            summary += f"  Type: {measurement_type}\n"
            
            if measurement_type == "IV":
                summary += f"  Voltage Range: {sweep_data.get('start_v', 0)}V to {sweep_data.get('stop_v', 0)}V\n"
                summary += f"  Step: {sweep_data.get('step_v', 0)}V\n"
                summary += f"  Repeats: {sweep_data.get('sweeps', 1)}\n"
            elif measurement_type == "Endurance":
                summary += f"  Set: {sweep_data.get('set_v', 0)}V, Reset: {sweep_data.get('reset_v', 0)}V\n"
                summary += f"  Cycles: {sweep_data.get('cycles', 0)}\n"
            elif measurement_type == "Retention":
                summary += f"  Set: {sweep_data.get('set_v', 0)}V\n"
                summary += f"  Read: {sweep_data.get('read_v', 0)}V\n"
            
            summary += "\n"
        
        self.summary_text.insert(1.0, summary)
        self.summary_text.config(state=tk.DISABLED)
    
    def _show_empty_visualization(self) -> None:
        """Show empty visualization."""
        self.viz_figure.clear()
        ax = self.viz_figure.add_subplot(111)
        ax.text(0.5, 0.5, "Select a measurement\nto visualize", 
                ha='center', va='center', fontsize=14, color='gray')
        ax.axis('off')
        self.viz_figure.tight_layout()
        self.viz_canvas.draw()
        
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(1.0, "No measurement selected.")
        self.summary_text.config(state=tk.DISABLED)

