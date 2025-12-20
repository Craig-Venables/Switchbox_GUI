"""

Review Panel - Review predictions and label devices.

NOW WITH INTERACTIVE WEIGHT ADJUSTMENT!

"""



import tkinter as tk

from tkinter import ttk, messagebox

from pathlib import Path

import matplotlib

matplotlib.use('TkAgg')  # Set backend before importing pyplot

import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import numpy as np





class ReviewPanel:

    """Panel for reviewing device predictions and providing feedback for weight adjustment."""

    

    def __init__(self, parent_frame, validator, on_labels_updated_callback=None):

        """

        Initialize review panel.

        

        Args:

            parent_frame: Parent tkinter frame

            validator: ClassificationValidator instance

            on_labels_updated_callback: Callback when labels are updated

        """

        self.frame = ttk.Frame(parent_frame)

        self.validator = validator

        self.on_labels_updated_callback = on_labels_updated_callback

        

        self.filtered_predictions = []

        self.current_device_id = None

        

        self._setup_ui()

    

    def _setup_ui(self):

        """Setup the review panel UI."""

        # Main layout: Left (device list) + Right (device details + plot)

        left_frame = ttk.Frame(self.frame)

        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=5)

        

        right_frame = ttk.Frame(self.frame)

        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        

        # === LEFT: DEVICE LIST ===

        list_header = ttk.Frame(left_frame)

        list_header.pack(fill=tk.X, pady=(0, 5))

        

        list_label = ttk.Label(list_header, text="Devices", font=("Arial", 11, "bold"))

        list_label.pack(side=tk.LEFT)

        

        # Help button for weight explanation

        help_btn = ttk.Button(list_header, text="ℹ️ Help", command=self._show_weight_help, width=8)

        help_btn.pack(side=tk.RIGHT)

        

        # Device listbox with scrollbar

        list_scroll_frame = ttk.Frame(left_frame)

        list_scroll_frame.pack(fill=tk.BOTH, expand=True)

        

        scrollbar = ttk.Scrollbar(list_scroll_frame)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        

        self.device_listbox = tk.Listbox(list_scroll_frame, width=40, height=20,

                                         yscrollcommand=scrollbar.set)

        self.device_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.device_listbox.yview)

        

        self.device_listbox.bind('<<ListboxSelect>>', lambda e: self._on_device_selected())

        

        # Navigation buttons

        nav_frame = ttk.Frame(left_frame)

        nav_frame.pack(pady=5)

        

        ttk.Button(nav_frame, text="◀ Previous", command=self._previous_device).pack(side=tk.LEFT, padx=2)

        ttk.Button(nav_frame, text="Next ▶", command=self._next_device).pack(side=tk.LEFT, padx=2)

        

        # === RIGHT: DEVICE DETAILS ===

        # Classification scores display (NEW!)

        scores_frame = ttk.LabelFrame(right_frame, text="Classification Scores", padding=10)

        scores_frame.pack(fill=tk.X, pady=(0, 10))

        

        self.score_labels = {}

        score_row = ttk.Frame(scores_frame)

        score_row.pack(fill=tk.X)

        

        for i, device_type in enumerate(['memristive', 'memcapacitive', 'capacitive', 'conductive', 'ohmic']):

            col_frame = ttk.Frame(score_row)

            col_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

            

            ttk.Label(col_frame, text=device_type.capitalize(), 

                     font=("Arial", 9, "bold")).pack()

            score_label = ttk.Label(col_frame, text="--", font=("Arial", 12))

            score_label.pack()

            self.score_labels[device_type] = score_label

        

        # Predicted classification

        pred_frame = ttk.Frame(right_frame)

        pred_frame.pack(fill=tk.X, pady=(0, 10))

        

        ttk.Label(pred_frame, text="Predicted:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        self.predicted_label = ttk.Label(pred_frame, text="--", 

                                         font=("Arial", 12, "bold"), foreground="blue")

        self.predicted_label.pack(side=tk.LEFT, padx=5)

        

        ttk.Label(pred_frame, text="Confidence:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(20, 5))

        self.confidence_label = ttk.Label(pred_frame, text="--", font=("Arial", 12))

        self.confidence_label.pack(side=tk.LEFT)

        

        # === INTERACTIVE FEEDBACK SECTION (NEW!) ===

        feedback_frame = ttk.LabelFrame(right_frame, text="Interactive Feedback", padding=10)

        feedback_frame.pack(fill=tk.X, pady=(0, 10))

        

        ttk.Label(feedback_frame, text="Is this classification correct?", 

                 font=("Arial", 10)).pack(pady=(0, 5))

        

        button_frame = ttk.Frame(feedback_frame)

        button_frame.pack(pady=5)

        

        # Correct button (green)

        correct_btn = tk.Button(button_frame, text="✓ Correct", 

                               bg="#4CAF50", fg="white", font=("Arial", 11, "bold"),

                               command=self._mark_correct, width=12, height=2)

        correct_btn.pack(side=tk.LEFT, padx=5)

        

        # Incorrect button (red) with dropdown

        incorrect_frame = ttk.Frame(button_frame)

        incorrect_frame.pack(side=tk.LEFT, padx=5)

        

        incorrect_btn = tk.Button(incorrect_frame, text="✗ Incorrect", 

                                 bg="#f44336", fg="white", font=("Arial", 11, "bold"),

                                 command=self._mark_incorrect, width=12, height=2)

        incorrect_btn.pack()

        

        # Actual classification dropdown

        actual_frame = ttk.Frame(feedback_frame)

        actual_frame.pack(pady=5)

        

        ttk.Label(actual_frame, text="If incorrect, select actual type:").pack(side=tk.LEFT, padx=5)

        self.actual_class_var = tk.StringVar()

        self.actual_class_combo = ttk.Combobox(actual_frame, textvariable=self.actual_class_var,

                                               values=['memristive', 'memcapacitive', 'capacitive', 'conductive', 'ohmic'],

                                               state='readonly', width=15)

        self.actual_class_combo.pack(side=tk.LEFT)

        

        # Reanalyze all checkbox

        self.reanalyze_all_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(feedback_frame, text="Re-analyze all devices after adjustment",

                       variable=self.reanalyze_all_var).pack(pady=5)

        

        # Feedback message

        self.feedback_msg_label = ttk.Label(feedback_frame, text="", 

                                           font=("Arial", 9), foreground="green")

        self.feedback_msg_label.pack(pady=5)

        

        # === Device Info ===

        info_frame = ttk.LabelFrame(right_frame, text="Device Info", padding=10)

        info_frame.pack(fill=tk.X, pady=(0, 10))

        

        self.info_text = tk.Text(info_frame, height=8, width=60, font=("Consolas", 9))

        self.info_text.pack(fill=tk.BOTH, expand=True)

        

        # === Plot ===

        plot_frame = ttk.LabelFrame(right_frame, text="I-V Curve", padding=5)

        plot_frame.pack(fill=tk.BOTH, expand=True)

        

        self.fig, self.ax = plt.subplots(figsize=(6, 4))

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)

        self.canvas.draw()
        
        # Add Toolbar for Zoom/Pan
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    

    def refresh(self):

        """Refresh the device list."""

        predictions = self.validator.get_predictions()

        self.filtered_predictions = [p for p in predictions if p.get('analysis')]

        

        self.device_listbox.delete(0, tk.END)

        

        if not self.filtered_predictions:

            self.device_listbox.insert(tk.END, "(No devices available)")

            return

        

        for pred in self.filtered_predictions:

            device_id = pred.get('device_id', 'Unknown')

            analysis = pred.get('analysis', {})

            classification = analysis.get('classification', {})

            device_type = classification.get('device_type', '?')

            confidence = classification.get('confidence', 0) * 100

            

            display_text = f"{device_id} → {device_type} ({confidence:.0f}%)"

            self.device_listbox.insert(tk.END, display_text)

        

        # Select first device

        if self.filtered_predictions:

            self.device_listbox.selection_set(0)

            self._on_device_selected()

    

    def _on_device_selected(self):

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

        """Display detailed information for a device."""

        self.current_device_id = pred.get('device_id')

        device_id = pred.get('device_id', 'Unknown')

        analysis = pred.get('analysis', {})

        

        # === UPDATE SCORES (NEW!) ===

        classification = analysis.get('classification', {})

        breakdown = classification.get('breakdown', {})

        

        # Display scores for all device types

        for device_type_key, score_label in self.score_labels.items():

            score = breakdown.get(device_type_key, 0)

            score_label.config(text=f"{score:.1f}")

            

            # Highlight the predicted class

            if device_type_key == classification.get('device_type'):

                score_label.config(foreground="blue", font=("Arial", 13, "bold"))

            else:

                score_label.config(foreground="black", font=("Arial", 12))

        

        # Prediction (handle None safely)

        device_type = classification.get('device_type') or 'unknown'

        confidence = classification.get('confidence', 0) or 0

        

        self.predicted_label.config(text=device_type.capitalize())

        self.confidence_label.config(text=f"{confidence*100:.1f}%")

        

        # Clear feedback message

        self.feedback_msg_label.config(text="")

        

        # Device info

        self.info_text.delete('1.0', tk.END)

        

        info_lines = [

            f"Device: {device_id}",

            f"File: {Path(pred.get('file_path', '')).name}",

            f"",

            f"Predicted: {device_type.capitalize()} ({confidence*100:.1f}%)",

            f"",

            f"Scores:",

            f"  Memristive: {breakdown.get('memristive', 0):.1f}",
            f"  Memcapacitive: {breakdown.get('memcapacitive', 0):.1f}", 
            f"  Capacitive: {breakdown.get('capacitive', 0):.1f}",
            f"  Conductive: {breakdown.get('conductive', 0):.1f}",
            f"  Ohmic: {breakdown.get('ohmic', 0):.1f}",

        ]

        # Add Features Breakdown
        features = classification.get('features', {})
        if features:
            info_lines.extend([
                f"",
                f"Features:",
                f"  Hysteresis: {'YES' if features.get('has_hysteresis') else 'no'}",
                f"  Pinched Loop: {'YES' if features.get('pinched_hysteresis') else 'no'}",
                f"  Switching: {'YES' if features.get('switching_behavior') else 'no'}",
                f"  Nonlinear I-V: {'YES' if features.get('nonlinear_iv') else 'no'}",
            ])
            # Only show phase if relevant
            if features.get('phase_shift'):
                 info_lines.append(f"  Phase Shift: {features.get('phase_shift', 0):.1f}")

            if features.get('is_noisy'):
                 info_lines.append(f"")
                 info_lines.append(f"⚠️ NOISE DETECTED: {features.get('noise_reason')}")
            elif device_type.lower() == 'unknown':
                 max_score = max(breakdown.values()) if breakdown else 0
                 info_lines.append(f"")
                 info_lines.append(f"Reason: Scores low (Max: {max_score:.1f})")


        

        resistance = analysis.get('resistance', {})

        if resistance:

            info_lines.extend([

                f"",

                f"Resistance:",

                f"  Ron: {resistance.get('ron_mean', 0):.2e} Ω",

                f"  Roff: {resistance.get('roff_mean', 0):.2e} Ω",

                f"  ON/OFF: {resistance.get('on_off_mean', 0):.2f}",

            ])

        

        self.info_text.insert('1.0', '\n'.join(info_lines))

        

        # Plot I-V curve

        self.ax.clear()

        

        try:

            file_path = pred.get('file_path')

            if file_path and Path(file_path).exists():

                # Read voltage/current from file

                from ...IV_Analysis.single_file_metrics import read_data_file

                result = read_data_file(file_path)

                

                if len(result) >= 2:

                    voltage = np.array(result[0])

                    current = np.array(result[1])

                    

                    self.ax.plot(voltage, current, 'b-', linewidth=1.5, label='I-V Curve')

                    self.ax.axhline(0, color='gray', linestyle='--', alpha=0.5)

                    self.ax.axvline(0, color='gray', linestyle='--', alpha=0.5)

                    self.ax.set_xlabel('Voltage (V)')

                    self.ax.set_ylabel('Current (A)')

                    self.ax.set_title(f"{device_id} - {device_type.capitalize()}")

                    self.ax.grid(True, alpha=0.3)

                    self.ax.legend()

        except Exception as e:

            self.ax.text(0.5, 0.5, f'Error loading plot:\n{str(e)}',

                        ha='center', va='center', transform=self.ax.transAxes)

        

        self.fig.tight_layout()

        self.canvas.draw()

    

    def _mark_correct(self):

        """User marks current classification as CORRECT."""

        if not self.current_device_id:

            messagebox.showwarning("No Selection", "Please select a device first.")

            return

        

        # Provide feedback to validator

        result = self.validator.provide_feedback(

            device_id=self.current_device_id,

            is_correct=True,

            reanalyze_all=self.reanalyze_all_var.get()

        )

        

        if result['success']:

            self.feedback_msg_label.config(text=f"✓ {result['message']}", foreground="green")

            

            # Refresh display with updated classification

            self._refresh_current_device()

            

            if self.reanalyze_all_var.get():

                self.refresh()  # Refresh entire list

        else:

            messagebox.showerror("Error", result['message'])

    

    def _mark_incorrect(self):

        """User marks current classification as INCORRECT."""

        if not self.current_device_id:

            messagebox.showwarning("No Selection", "Please select a device first.")

            return

        

        actual_class = self.actual_class_var.get()

        if not actual_class:

            messagebox.showwarning("Missing Info", "Please select the actual device type.")

            return

        

        # Provide feedback to validator

        result = self.validator.provide_feedback(

            device_id=self.current_device_id,

            is_correct=False,

            actual_class=actual_class,

            reanalyze_all=self.reanalyze_all_var.get()

        )

        

        if result['success']:

            self.feedback_msg_label.config(text=f"✓ {result['message']}", foreground="orange")

            

            # Refresh display with updated classification

            self._refresh_current_device()

            

            if self.reanalyze_all_var.get():

                self.refresh()  # Refresh entire list

        else:

            messagebox.showerror("Error", result['message'])

    

    def _refresh_current_device(self):

        """Refresh the currently displayed device after weight adjustment."""

        selection = self.device_listbox.curselection()

        if not selection:

            return

        

        idx = selection[0]

        

        # Get updated predictions

        predictions = self.validator.get_predictions()

        self.filtered_predictions = [p for p in predictions if p.get('analysis')]

        

        if idx < len(self.filtered_predictions):

            pred = self.filtered_predictions[idx]

            self._display_device(pred)

            

            # Update list item text

            device_id = pred.get('device_id', 'Unknown')

            analysis = pred.get('analysis', {})

            classification = analysis.get('classification', {})

            device_type = classification.get('device_type', '?')

            confidence = classification.get('confidence', 0) * 100

            

            display_text = f"{device_id} → {device_type} ({confidence:.0f}%)"

            self.device_listbox.delete(idx)

            self.device_listbox.insert(idx, display_text)

            self.device_listbox.selection_set(idx)

    

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

    

    def _show_weight_help(self):

        """Show help dialog explaining how weights work."""

        help_window = tk.Toplevel(self.frame)

        help_window.title("Classification Weights - Quick Reference")

        help_window.geometry("700x600")

        

        # Create scrollable text widget

        text_frame = ttk.Frame(help_window, padding=10)

        text_frame.pack(fill=tk.BOTH, expand=True)

        

        scrollbar = ttk.Scrollbar(text_frame)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        

        help_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set,

                           font=("Consolas", 10), padx=10, pady=10)

        help_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=help_text.yview)

        

        # Help content

        content = """

╔═══════════════════════════════════════════════════════════════╗

║          CLASSIFICATION WEIGHTS - HOW IT WORKS                ║

╚═══════════════════════════════════════════════════════════════╝



OVERVIEW

────────

Each device gets scored for 4 types: Memristive, Capacitive, Conductive, 

and Ohmic. The type with the highest score wins. You can see all 4 scores 

in the "Classification Scores" panel.





═══════════════════════════════════════════════════════════════

MEMRISTIVE CLASSIFICATION (Target: Memory Devices)

═══════════════════════════════════════════════════════════════



Positive Features (+points):

  ✓ Has Hysteresis (+25)

    - I-V curve forms a loop (different path up vs down)

  

  ✓ Pinched Hysteresis (+30) ★ STRONGEST INDICATOR

    - Loop passes through origin (0,0)

    - Classic memristor signature

  

  ✓ Switching Behavior (+25)

    - Clear resistance state changes

    - HRS ↔ LRS transitions

  

  ✓ Nonlinear I-V (+10)

    - Current doesn't scale linearly with voltage

  

  ✓ Polarity Dependent (+10)

    - Different behavior for +V vs -V



Penalties (prevents false positives):

  ✗ Linear I-V (-20)

    - If perfectly linear, probably not memristive

  

  ✗ Ohmic Behavior (-30)

    - If just a resistor, definitely not memristive





═══════════════════════════════════════════════════════════════

CAPACITIVE CLASSIFICATION (Charge Storage)

═══════════════════════════════════════════════════════════════



  ✓ Hysteresis but NOT Pinched (+40)

    - Has loop but doesn't cross origin

    - Typical of capacitors

  

  ✓ Phase Shift > 45° (+40)

    - Current leads voltage (capacitive response)

  

  ✓ Elliptical Hysteresis (+20)

    - Smooth elliptical loop shape





═══════════════════════════════════════════════════════════════

MEMCAPACITIVE CLASSIFICATION (Memory + Capacitance)

═══════════════════════════════════════════════════════════════



  ✓ Unpinched Hysteresis (+40)

    - Open loop that does NOT cross zero ideally

    - Classic capacitive signature but with memory traits

  

  ✓ Switching Behavior (+30)

    - Shows resistance change like a memristor

  

  ✓ Nonlinear I-V (+20)

    - Not a simple capacitor ellipse, has structure

  

  ✓ Phase Shift (+20)

    - Current leads voltage

  

  ✗ Penalty: Pinched Hysteresis (-20)

    - If it's pinched at zero, it's likely a Memristor instead



═══════════════════════════════════════════════════════════════

CONDUCTIVE CLASSIFICATION (Non-Ohmic Transport)

═══════════════════════════════════════════════════════════════



  ✓ No Hysteresis (+30)

    - Single-valued I-V curve

  

  ✓ Nonlinear, No Switching (+40)

    - Interesting transport but no memory

  

  ✓ Advanced Conduction Mechanism (+30)

    - Space Charge Limited Current (SCLC)

    - Poole-Frenkel emission

    - Schottky emission

    - Fowler-Nordheim tunneling





═══════════════════════════════════════════════════════════════

OHMIC CLASSIFICATION (Simple Resistor)

═══════════════════════════════════════════════════════════════



  ✓ Linear + Clean (+60)

    - Linear I-V

    - No hysteresis

    - No switching

    - Small memory window

    - No compliance effects

  

  ✓ Ohmic Model Fit (+20)

    - Excellent fit (R² > 0.98) to V = IR





═══════════════════════════════════════════════════════════════

INTERACTIVE FEEDBACK - WHAT HAPPENS?

═══════════════════════════════════════════════════════════════



When you click "✓ Correct":

  → Active weights are gently increased (+2.5 by default)

  → Reinforces the correct classification pattern

  → Small adjustment to avoid overfitting



When you click "✗ Incorrect":

  → MULTI-WEIGHT ADJUSTMENT:

    1. Decrease weights for wrong class (-5.0)

    2. Increase weights for correct class (+5.0)

  → Example: Predicted "memristive" but actually "capacitive"

     • memristive_has_hysteresis: -5.0

     • capacitive_hysteresis_unpinched: +5.0

  → Device is immediately re-analyzed with new weights



Learning Rate: 5.0 (default)

  - Higher = faster learning, may overshoot

  - Lower = slower learning, more stable





═══════════════════════════════════════════════════════════════

TIPS FOR BEST RESULTS

═══════════════════════════════════════════════════════════════



1. Start with Known Devices

   Review devices you're confident about first



2. Watch the Scores

   Pay attention to how close second-place is

   If memristive=75, capacitive=70 → borderline case



3. Iterate Multiple Times

   Classification improves with each feedback

   Review 10-15 devices for noticeable improvement



4. Use "Re-analyze all" Sparingly

   For single corrections, just current device is fine

   Use "all" when you want to see global impact



5. Weights Persist

   Your adjustments save to: data/config.json

   Start where you left off next time





═══════════════════════════════════════════════════════════════

CURRENT WEIGHTS

═══════════════════════════════════════════════════════════════

"""

        

        # Add current weights from validator

        try:

            current_weights = self.validator.parameter_tuner.get_weights()

            content += "\nMemristive:\n"

            for key, val in current_weights.items():

                if key.startswith('memristive'):

                    content += f"  {key.replace('memristive_', '')}: {val:.1f}\n"

            

            content += "\nCapacitive:\n"

            for key, val in current_weights.items():

                if key.startswith('capacitive'):

                    content += f"  {key.replace('capacitive_', '')}: {val:.1f}\n"

            

            content += "\nConductive:\n"

            for key, val in current_weights.items():

                if key.startswith('conductive'):

                    content += f"  {key.replace('conductive_', '')}: {val:.1f}\n"

            

            content += "\nOhmic:\n"

            for key, val in current_weights.items():

                if key.startswith('ohmic'):

                    content += f"  {key.replace('ohmic_', '')}: {val:.1f}\n"

            

            lr = current_weights.get('adjustment_learning_rate', 5.0)

            content += f"\nLearning Rate: {lr:.1f}\n"

        except:

            content += "\n(Could not load current weights)\n"

        

        content += "\n\n" + "═"*63 + "\n"

        content += "Press any key or click outside to close this window\n"

        

        help_text.insert('1.0', content)

        help_text.config(state='disabled')  # Make read-only

        

        # Close button

        close_btn = ttk.Button(help_window, text="Close", command=help_window.destroy)

        close_btn.pack(pady=10)

        

        # Make window modal

        help_window.transient(self.frame)

        help_window.grab_set()

