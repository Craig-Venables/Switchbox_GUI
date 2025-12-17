"""
Tuning Panel - Adjust scoring weights and thresholds.
"""

import tkinter as tk
from tkinter import ttk, messagebox


class TuningPanel:
    """Panel for adjusting scoring weights and thresholds."""
    
    def __init__(self, parent, validator, on_parameters_updated_callback=None):
        """
        Initialize tuning panel.
        
        Args:
            parent: Parent widget (notebook)
            validator: ClassificationValidator instance
            on_parameters_updated_callback: Callback when parameters are updated
        """
        self.validator = validator
        self.on_parameters_updated_callback = on_parameters_updated_callback
        
        self.frame = ttk.Frame(parent)
        self.weight_vars = {}
        self.threshold_vars = {}
        self._build_ui()
        self._load_current_parameters()
    
    def _build_ui(self):
        """Build the UI."""
        # Title
        title = tk.Label(
            self.frame,
            text="Tune Scoring Weights & Thresholds",
            font=('Arial', 14, 'bold')
        )
        title.pack(pady=10)
        
        # Main container with scroll
        canvas = tk.Canvas(self.frame)
        scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Weights section
        weights_frame = ttk.LabelFrame(scrollable_frame, text="Scoring Weights")
        weights_frame.pack(fill=tk.X, padx=20, pady=10)
        
        weights_info = tk.Label(
            weights_frame,
            text="Adjust the contribution of each feature to the memristivity score (0-50 range recommended)",
            font=('Arial', 9),
            fg='#666666',
            wraplength=600
        )
        weights_info.pack(pady=5)
        
        # Weight controls
        weight_names = {
            'pinched_hysteresis': 'Pinched Hysteresis',
            'hysteresis_quality': 'Hysteresis Quality',
            'switching_behavior': 'Switching Behavior',
            'memory_window': 'Memory Window Quality',
            'nonlinearity': 'Nonlinearity',
            'polarity_dependence': 'Polarity Dependence'
        }
        
        for key, label in weight_names.items():
            row = ttk.Frame(weights_frame)
            row.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(row, text=label, width=25, anchor=tk.W).pack(side=tk.LEFT)
            
            var = tk.DoubleVar(value=30.0)
            self.weight_vars[key] = var
            
            scale = ttk.Scale(
                row,
                from_=0,
                to=50,
                variable=var,
                orient=tk.HORIZONTAL,
                length=300
            )
            scale.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
            
            value_label = tk.Label(row, text="30.0", width=8)
            value_label.pack(side=tk.LEFT, padx=5)
            
            # Update label when scale changes
            def update_label(v=var, lbl=value_label):
                lbl.config(text=f"{v.get():.1f}")
            var.trace('w', lambda *args: update_label())
        
        # Thresholds section
        thresholds_frame = ttk.LabelFrame(scrollable_frame, text="Classification Thresholds")
        thresholds_frame.pack(fill=tk.X, padx=20, pady=10)
        
        threshold_names = {
            'memristive_min_score': 'Memristive Minimum Score',
            'high_confidence_min': 'High Confidence Minimum'
        }
        
        for key, label in threshold_names.items():
            row = ttk.Frame(thresholds_frame)
            row.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(row, text=label, width=25, anchor=tk.W).pack(side=tk.LEFT)
            
            var = tk.DoubleVar(value=60.0)
            self.threshold_vars[key] = var
            
            entry = ttk.Entry(row, textvariable=var, width=10)
            entry.pack(side=tk.LEFT, padx=10)
            
            # Validate entry
            def validate_entry(v=var):
                try:
                    val = float(v.get())
                    if val < 0 or val > 100:
                        messagebox.showerror("Invalid Value", "Threshold must be between 0 and 100")
                        return False
                except ValueError:
                    messagebox.showerror("Invalid Value", "Threshold must be a number")
                    return False
                return True
            
            entry.bind('<FocusOut>', lambda e: validate_entry())
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(
            button_frame,
            text="Apply Changes",
            command=self._apply_changes
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Reset to Defaults",
            command=self._reset_defaults
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Save Configuration",
            command=self._save_config
        ).pack(side=tk.LEFT, padx=5)
        
        # Status
        self.status_var = tk.StringVar(value="")
        status_label = tk.Label(
            scrollable_frame,
            textvariable=self.status_var,
            font=('Arial', 9),
            fg='#666666'
        )
        status_label.pack(pady=5)
    
    def _load_current_parameters(self):
        """Load current parameters from validator."""
        weights = self.validator.parameter_tuner.get_weights()
        thresholds = self.validator.parameter_tuner.get_thresholds()
        
        for key, var in self.weight_vars.items():
            if key in weights:
                var.set(weights[key])
        
        for key, var in self.threshold_vars.items():
            if key in thresholds:
                var.set(thresholds[key])
    
    def _apply_changes(self):
        """Apply parameter changes."""
        # Get values from UI
        weights = {key: var.get() for key, var in self.weight_vars.items()}
        thresholds = {key: var.get() for key, var in self.threshold_vars.items()}
        
        # Update validator
        try:
            self.validator.update_parameters(weights=weights, thresholds=thresholds)
            self.status_var.set("Parameters applied! Recalculating predictions...")
            
            # Callback
            if self.on_parameters_updated_callback:
                self.on_parameters_updated_callback()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply parameters: {e}")
    
    def _reset_defaults(self):
        """Reset to default parameters."""
        if messagebox.askyesno("Reset", "Reset all parameters to defaults?"):
            self.validator.parameter_tuner.reset_to_defaults()
            self._load_current_parameters()
            self.status_var.set("Reset to defaults. Click 'Apply Changes' to use them.")
    
    def _save_config(self):
        """Save current configuration."""
        weights = {key: var.get() for key, var in self.weight_vars.items()}
        thresholds = {key: var.get() for key, var in self.threshold_vars.items()}
        
        self.validator.parameter_tuner.set_weights(weights)
        self.validator.parameter_tuner.set_thresholds(thresholds)
        self.validator.parameter_tuner.save()
        
        messagebox.showinfo("Saved", "Configuration saved to file")
        self.status_var.set("Configuration saved")
