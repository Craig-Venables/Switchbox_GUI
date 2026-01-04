"""

Review Panel - Review predictions and label devices.

"""



import tkinter as tk

from tkinter import ttk, messagebox

from pathlib import Path

import matplotlib

matplotlib.use('TkAgg')  # Set backend before importing pyplot

import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import numpy as np





class ReviewPanel:

    """Panel for reviewing predictions and labeling devices."""

    

    def __init__(self, parent, validator, on_labels_updated_callback=None):

        """

        Initialize review panel.

        

        Args:

            parent: Parent widget (notebook)

            validator: ClassificationValidator instance

            on_labels_updated_callback: Callback when labels are updated

        """

        self.validator = validator

        self.on_labels_updated_callback = on_labels_updated_callback

        

        self.frame = ttk.Frame(parent)

        self.current_device_idx = 0

        self.predictions = []

        self.filtered_predictions = []

        self._build_ui()

    

    def _build_ui(self):

        """Build the UI."""

        # Title

        title = tk.Label(

            self.frame,

            text="Review Predictions & Label Devices",

            font=('Arial', 14, 'bold')

        )

        title.pack(pady=10)

        

        # Main container

        main_container = ttk.Frame(self.frame)

        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        

        # Left panel - Device list

        left_panel = ttk.Frame(main_container)

        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5)

        

        # Filter

        filter_frame = ttk.Frame(left_panel)

        filter_frame.pack(fill=tk.X, pady=5)

        tk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)

        self.filter_var = tk.StringVar(value="all")

        filter_combo = ttk.Combobox(

            filter_frame,

            textvariable=self.filter_var,

            values=["all", "unlabeled", "labeled", "memristive", "ohmic", "capacitive", "conductive"],

            state="readonly",

            width=15

        )

        filter_combo.pack(side=tk.LEFT, padx=5)

        filter_combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_device_list())

        

        # Device list

        list_frame = ttk.LabelFrame(left_panel, text="Devices")

        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        

        scrollbar_list = ttk.Scrollbar(list_frame)

        scrollbar_list.pack(side=tk.RIGHT, fill=tk.Y)

        

        self.device_listbox = tk.Listbox(

            list_frame,

            yscrollcommand=scrollbar_list.set,

            width=30

        )

        self.device_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_list.config(command=self.device_listbox.yview)

        self.device_listbox.bind('<<ListboxSelect>>', self._on_device_selected)

        

        # Right panel - Device details

        right_panel = ttk.Frame(main_container)

        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        

        # Device info

        info_frame = ttk.LabelFrame(right_panel, text="Device Information")

        info_frame.pack(fill=tk.X, pady=5)

        

        self.info_text = tk.Text(info_frame, height=8, wrap=tk.WORD)

        self.info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        

        # IV Plot

        plot_frame = ttk.LabelFrame(right_panel, text="IV Curve")

        plot_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        

        self.fig, self.ax = plt.subplots(figsize=(6, 4))

        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)

        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        

        # Labeling

        label_frame = ttk.LabelFrame(right_panel, text="Set Ground Truth Label")

        label_frame.pack(fill=tk.X, pady=5)

        

        label_inner = ttk.Frame(label_frame)

        label_inner.pack(pady=10)

        

        tk.Label(label_inner, text="Label:").pack(side=tk.LEFT, padx=5)

        self.label_var = tk.StringVar(value="")

        label_combo = ttk.Combobox(

            label_inner,

            textvariable=self.label_var,

            values=["", "memristive", "ohmic", "capacitive", "conductive"],

            state="readonly",

            width=15

        )

        label_combo.pack(side=tk.LEFT, padx=5)

        

        save_label_btn = ttk.Button(

            label_inner,

            text="Save Label",

            command=self._save_label

        )

        save_label_btn.pack(side=tk.LEFT, padx=5)

        

        # Navigation

        nav_frame = ttk.Frame(right_panel)

        nav_frame.pack(fill=tk.X, pady=5)

        

        ttk.Button(nav_frame, text="Γùä Previous", command=self._previous_device).pack(side=tk.LEFT, padx=5)

        ttk.Button(nav_frame, text="Next Γû║", command=self._next_device).pack(side=tk.LEFT, padx=5)

        ttk.Button(nav_frame, text="Refresh", command=self.refresh).pack(side=tk.LEFT, padx=5)

    

    def refresh(self):

        """Refresh the device list and display."""

        self.predictions = self.validator.get_predictions()

        self.filtered_predictions = []

        self._refresh_device_list()

        if self.filtered_predictions:

            self._select_first_device()

        else:

            # Clear display

            self.info_text.delete('1.0', tk.END)

            self.info_text.insert('1.0', "No devices available. Load data in the 'Load Data' tab first.")

            self.ax.clear()

            self.canvas.draw()

    

    def _refresh_device_list(self):

        """Refresh the device list based on filter."""

        self.device_listbox.delete(0, tk.END)

        

        filter_value = self.filter_var.get()

        labels = self.validator.label_manager.get_all_labels()

        

        filtered = []

        for pred in self.predictions:

            if not pred.get('analysis'):

                continue

            

            device_id = pred.get('device_id', '')

            has_label = device_id in labels

            

            # Apply filter

            if filter_value == "unlabeled" and has_label:

                continue

            if filter_value == "labeled" and not has_label:

                continue

            

            classification = pred['analysis'].get('classification', {})

            predicted_type = classification.get('device_type', 'unknown')

            

            if filter_value in ['memristive', 'ohmic', 'capacitive', 'conductive']:

                if predicted_type != filter_value:

                    continue

            

            filtered.append(pred)

        

        # Sort by device_id

        filtered.sort(key=lambda x: x.get('device_id', ''))

        

        for pred in filtered:

            device_id = pred.get('device_id', 'unknown')

            classification = pred['analysis'].get('classification', {}) if pred.get('analysis') else {}

            predicted_type = classification.get('device_type', 'unknown')

            score = classification.get('memristivity_score', 0)

            

            # Handle None score

            if score is None:

                score = 0

            

            label = labels.get(device_id, '')

            label_marker = "Γ£ô" if label else ""

            

            display_text = f"{label_marker} {device_id} | {predicted_type} ({score:.0f})"

            self.device_listbox.insert(tk.END, display_text)

        

        self.filtered_predictions = filtered

    

    def _select_first_device(self):

        """Select first device in list."""

        if self.device_listbox.size() > 0:

            self.device_listbox.selection_set(0)

            self._on_device_selected()

    

    def _on_device_selected(self, event=None):

        """Handle device selection."""

        selection = self.device_listbox.curselection()

        if not selection:

            return

        

        idx = selection[0]

        if idx >= len(self.filtered_predictions):

            return

        

        pred = self.filtered_predictions[idx]

        self._display_device(pred)

    

    def _display_device(self, pred):

        """Display device details."""

        device_id = pred.get('device_id', 'unknown')

        analysis = pred.get('analysis')

        error = pred.get('error')

        

        # Update info text

        self.info_text.delete('1.0', tk.END)

        

        if error:

            self.info_text.insert('1.0', f"Error: {error}\n")

            self.ax.clear()

            self.canvas.draw()

            return

        

        if not analysis:

            self.info_text.insert('1.0', "No analysis data available\n")

            return

        

        classification = analysis.get('classification', {})

        resistance = analysis.get('resistance_metrics', {})

        

        # Build info text

        memristivity_score = classification.get('memristivity_score', 0)

        if memristivity_score is None:

            memristivity_score = 0

        

        confidence = classification.get('confidence', 0)

        if confidence is None:

            confidence = 0

        

        info_lines = [

            f"Device ID: {device_id}",

            f"File: {Path(pred.get('file_path', '')).name}",

            "",

            "PREDICTION:",

            f"  Type: {classification.get('device_type', 'unknown')}",

            f"  Memristivity Score: {memristivity_score:.1f}/100",

            f"  Confidence: {confidence*100:.1f}%",

            "",

            "SCORE BREAKDOWN:"

        ]

        

        breakdown = classification.get('memristivity_breakdown', {})

        for feature, score in breakdown.items():

            score_val = score if score is not None else 0

            info_lines.append(f"  {feature}: {score_val:.1f}")

        

        info_lines.extend([

            "",

            "RESISTANCE:",

            f"  Ron: {resistance.get('ron_mean', 0):.2e} ╬⌐",

            f"  Roff: {resistance.get('roff_mean', 0):.2e} ╬⌐",

            f"  Switching Ratio: {resistance.get('switching_ratio_mean', 0):.1f}",

        ])

        

        # Check for label

        label = self.validator.label_manager.get_label(device_id)

        if label:

            info_lines.extend([

                "",

                f"GROUND TRUTH: {label.upper()}",

                f"  {'Γ£ô Correct' if classification.get('device_type') == label else 'Γ£ù Incorrect'}"

            ])

        

        self.info_text.insert('1.0', '\n'.join(info_lines))

        

        # Update plot

        self._plot_iv_curve(pred)

        

        # Update label combo

        if label:

            self.label_var.set(label)

        else:

            self.label_var.set("")

    

    def _plot_iv_curve(self, pred):

        """Plot IV curve for device."""

        self.ax.clear()

        

        # Try to get voltage/current from file

        filepath = pred.get('file_path')

        if filepath and Path(filepath).exists():

            try:

                from Helpers.Analysis.core.sweep_analyzer import read_data_file

                result = read_data_file(filepath)

                if len(result) >= 2:

                    voltage, current = result[0], result[1]

                    # Convert to numpy arrays if needed

                    if not isinstance(voltage, np.ndarray):

                        voltage = np.array(voltage)

                    if not isinstance(current, np.ndarray):

                        current = np.array(current)

                    

                    self.ax.plot(voltage, current, 'b-', linewidth=1.5, alpha=0.7)

                    self.ax.set_xlabel('Voltage (V)', fontsize=10)

                    self.ax.set_ylabel('Current (A)', fontsize=10)

                    self.ax.set_title(f"IV Curve: {pred.get('device_id', 'unknown')}", fontsize=11)

                    self.ax.grid(True, alpha=0.3)

                    self.ax.ticklabel_format(style='scientific', axis='y', scilimits=(0,0))

            except Exception as e:

                self.ax.text(0.5, 0.5, f"Could not load IV data:\n{str(e)[:50]}...", 

                           ha='center', va='center', transform=self.ax.transAxes,

                           fontsize=9, wrap=True)

        else:

            self.ax.text(0.5, 0.5, "IV data not available", 

                       ha='center', va='center', transform=self.ax.transAxes)

        

        self.canvas.draw()

    

    def _save_label(self):

        """Save label for current device."""

        selection = self.device_listbox.curselection()

        if not selection:

            messagebox.showwarning("No Selection", "Please select a device first")

            return

        

        idx = selection[0]

        if idx >= len(self.filtered_predictions):

            return

        

        pred = self.filtered_predictions[idx]

        device_id = pred.get('device_id')

        label = self.label_var.get()

        

        if not label:

            # Remove label

            self.validator.label_manager.remove_label(device_id)

            messagebox.showinfo("Label Removed", f"Label removed for {device_id}")

        else:

            try:

                self.validator.label_manager.set_label(device_id, label)

                self.validator.label_manager.save()

                messagebox.showinfo("Label Saved", f"Label '{label}' saved for {device_id}")

            except ValueError as e:

                messagebox.showerror("Error", str(e))

                return

        

        # Refresh

        self._refresh_device_list()

        self._display_device(pred)

        

        # Callback

        if self.on_labels_updated_callback:

            self.on_labels_updated_callback()

    

    def _previous_device(self):

        """Navigate to previous device."""

        selection = self.device_listbox.curselection()

        if selection:

            idx = selection[0]

            if idx > 0:

                self.device_listbox.selection_clear(0, tk.END)

                self.device_listbox.selection_set(idx - 1)

                self.device_listbox.see(idx - 1)

                self._on_device_selected()

    

    def _next_device(self):

        """Navigate to next device."""

        selection = self.device_listbox.curselection()

        if selection:

            idx = selection[0]

            if idx < self.device_listbox.size() - 1:

                self.device_listbox.selection_clear(0, tk.END)

                self.device_listbox.selection_set(idx + 1)

                self.device_listbox.see(idx + 1)

                self._on_device_selected()

