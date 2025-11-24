"""
Check Connection GUI - Connection Verification Tool
====================================================

Purpose:
--------
Small popup tool to quickly verify electrical connections by applying a small
DC bias and monitoring current in real-time. Useful for checking if probes
are making good contact before running measurements.

Key Features:
-------------
- Real-time current vs time plotting
- Audio alerts when current exceeds threshold
- Adjustable current threshold (default: 1e-9 A)
- Continuous or one-time alert modes
- Data recording for analysis
- Simple, focused interface

Entry Points:
-------------
Launched from MeasurementGUI:
  ```python
  # In MeasurementGUI
  check_connection = CheckConnection(master=self.master, keithley=self.keithley)
  ```

Dependencies:
-------------
- Requires: Keithley instrument instance (passed from MeasurementGUI)
- matplotlib: For real-time plotting
- tkinter: GUI framework

Relationships:
-------------
CheckConnection (this file)
    └─> Launched from: MeasurementGUI
    └─> Uses: Keithley instrument from MeasurementGUI

Usage:
------
1. User clicks "Check Connection" in MeasurementGUI
2. Window opens with real-time current plot
3. User observes current to verify connection
4. Audio alert triggers if current exceeds threshold
5. User closes window when done

File Structure:
---------------
- ~382 lines
- Main class: CheckConnection
- Focused, single-purpose tool
- Good example of a well-scoped GUI component
"""

import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time
import threading
from typing import Any, List

try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None


class CheckConnection:
    """Popup window that applies a bias and plots current in real-time."""
    def __init__(self, master: tk.Misc, keithley: Any):
        self.master = master
        self.top = tk.Toplevel(master)
        self.top.title("Connection Check - Pin Lowering Assistant")
        self.top.geometry("800x750")
        self.keithley = keithley
        smu_type = str(getattr(self.keithley, "smu_type", "")).lower()
        self._is_4200a = "4200a" in smu_type
        self.check_connection_window: bool = True
        self.noise_already: bool = False
        # Beep when absolute current reaches or exceeds this threshold (A)
        self.current_threshold_a: float = 1e-9
        
        # Store measurement data for saving
        self.time_data: List[float] = []
        self.current_data: List[float] = []

        self.create_ui()
        # Ensure we also handle window manager close (X button)
        try:
            self.top.protocol("WM_DELETE_WINDOW", self.close_window)
        except Exception:
            pass
        self.start_measurement_loop()

    def create_ui(self) -> None:
        """Create the main UI with plot and controls."""
        # Configure grid weights for responsive layout
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=0)
        
        # ========== PLOT FRAME ==========
        plot_frame = tk.LabelFrame(self.top, text="Real-Time Current Monitor", 
                                   padx=10, pady=10, relief=tk.GROOVE, borderwidth=2)
        plot_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)

        self.figure, self.ax = plt.subplots(figsize=(7, 5))
        self.ax.set_title("Connection Current vs Time", fontsize=12, fontweight='bold')
        self.ax.set_xlabel("Time (s)", fontsize=10)
        self.ax.set_ylabel("Current (A)", fontsize=10)
        self.ax.grid(True, alpha=0.3, linestyle='--')

        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # ========== CONTROLS FRAME ==========
        controls_frame = tk.LabelFrame(self.top, text="Settings & Controls", 
                                       padx=10, pady=10, relief=tk.GROOVE, borderwidth=2)
        controls_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        # Row 0: Sound Settings
        sound_label = tk.Label(controls_frame, text="🔊 Sound Alert:", font=("Arial", 10, "bold"))
        sound_label.grid(row=0, column=0, sticky="w", pady=5)
        
        self.make_sound_var = tk.IntVar(value=1)
        self.make_sound_switch = ttk.Checkbutton(
            controls_frame, 
            text="Enable Alert", 
            variable=self.make_sound_var,
            command=self.on_sound_toggle
        )
        self.make_sound_switch.grid(row=0, column=1, sticky="w", padx=10)
        
        self.continuous_sound_var = tk.IntVar(value=0)
        self.continuous_sound_switch = ttk.Checkbutton(
            controls_frame,
            text="Continuous (beep on every reading)",
            variable=self.continuous_sound_var
        )
        self.continuous_sound_switch.grid(row=0, column=2, sticky="w", padx=10)
        
        # Reset beep button
        self.reset_beep_btn = tk.Button(
            controls_frame,
            text="🔄 Reset Alert",
            command=self.reset_beep,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.RAISED,
            cursor="hand2"
        )
        self.reset_beep_btn.grid(row=0, column=3, padx=10)
        
        # Row 1: Threshold Settings
        threshold_label = tk.Label(controls_frame, text="⚡ Threshold:", font=("Arial", 10, "bold"))
        threshold_label.grid(row=1, column=0, sticky="w", pady=5)
        
        tk.Label(controls_frame, text="Alert when |I| ≥").grid(row=1, column=1, sticky="e")
        
        self.threshold_var = tk.StringVar(value="1e-9")
        self.threshold_entry = ttk.Entry(
            controls_frame,
            textvariable=self.threshold_var,
            width=15,
            font=("Arial", 9)
        )
        self.threshold_entry.grid(row=1, column=2, sticky="w", padx=5)
        
        tk.Label(controls_frame, text="A").grid(row=1, column=2, sticky="e", padx=(0, 5))
        
        self.update_threshold_btn = tk.Button(
            controls_frame,
            text="✓ Update",
            command=self.update_threshold,
            bg="#2196F3",
            fg="white",
            font=("Arial", 9, "bold"),
            cursor="hand2"
        )
        self.update_threshold_btn.grid(row=1, column=3, padx=10)
        
        # Row 2: Status and Actions
        status_label = tk.Label(controls_frame, text="📊 Actions:", font=("Arial", 10, "bold"))
        status_label.grid(row=2, column=0, sticky="w", pady=5)
        
        self.status_text = tk.Label(
            controls_frame,
            text="Monitoring... Waiting for connection",
            fg="#555",
            font=("Arial", 9, "italic")
        )
        self.status_text.grid(row=2, column=1, columnspan=2, sticky="w", padx=10)
        
        # Save and Close buttons
        button_frame = tk.Frame(controls_frame)
        button_frame.grid(row=2, column=3, padx=5)
        
        self.save_btn = tk.Button(
            button_frame,
            text="💾 Save Graph",
            command=self.save_graph,
            bg="#FF9800",
            fg="white",
            font=("Arial", 9, "bold"),
            width=12,
            cursor="hand2"
        )
        self.save_btn.pack(side=tk.LEFT, padx=2)
        
        self.close_button = tk.Button(
            button_frame,
            text="❌ Close",
            command=self.close_window,
            bg="#f44336",
            fg="white",
            font=("Arial", 9, "bold"),
            width=10,
            cursor="hand2"
        )
        self.close_button.pack(side=tk.LEFT, padx=2)

    def on_sound_toggle(self) -> None:
        """Handle sound toggle."""
        if self.make_sound_var.get():
            self.status_text.config(text="🔊 Sound alerts enabled", fg="#4CAF50")
        else:
            self.status_text.config(text="🔇 Sound alerts disabled", fg="#999")
    
    def reset_beep(self) -> None:
        """Reset the beep flag so it can beep again."""
        self.noise_already = False
        self.status_text.config(text="🔄 Alert reset - will beep on next threshold crossing", fg="#2196F3")
        print("Alert reset - ready to beep again")
    
    def update_threshold(self) -> None:
        """Update the current threshold from the entry field."""
        try:
            new_threshold = float(self.threshold_var.get())
            if new_threshold <= 0:
                raise ValueError("Threshold must be positive")
            self.current_threshold_a = new_threshold
            self.status_text.config(
                text=f"✓ Threshold updated: {new_threshold:.2e} A", 
                fg="#4CAF50"
            )
            print(f"Threshold updated to: {new_threshold:.2e} A")
            # Reset beep flag when threshold changes
            self.noise_already = False
        except ValueError as e:
            self.status_text.config(
                text=f"❌ Invalid threshold value", 
                fg="#f44336"
            )
            print(f"Error updating threshold: {e}")
    
    def save_graph(self) -> None:
        """Save the current graph to a file."""
        from tkinter import filedialog
        from datetime import datetime
        
        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"connection_check_{timestamp}.png"
        
        filepath = filedialog.asksaveasfilename(
            parent=self.top,
            title="Save Connection Check Graph",
            defaultextension=".png",
            initialfile=default_filename,
            filetypes=[
                ("PNG Image", "*.png"),
                ("PDF Document", "*.pdf"),
                ("JPEG Image", "*.jpg"),
                ("All Files", "*.*")
            ]
        )
        
        if filepath:
            try:
                self.figure.savefig(filepath, dpi=300, bbox_inches='tight')
                self.status_text.config(text=f"✓ Saved: {filepath.split('/')[-1]}", fg="#4CAF50")
                print(f"Graph saved to: {filepath}")
            except Exception as e:
                self.status_text.config(text=f"❌ Save failed: {str(e)}", fg="#f44336")
                print(f"Error saving graph: {e}")

    def start_measurement_loop(self) -> None:
        """Start background thread to measure current and update the plot."""
        self.measurement_thread = threading.Thread(target=self.measurement_loop)
        self.measurement_thread.daemon = True
        self.measurement_thread.start()

    def measurement_loop(self) -> None:
        """Worker thread: bias the device and stream current to the plot."""
        start_time = time.time()
        helper = getattr(self.keithley, "connection_check_sample", None)
        if not callable(helper) and hasattr(self.keithley, "instrument"):
            inner = getattr(self.keithley.instrument, "connection_check_sample", None)
            if callable(inner):
                helper = inner
        use_connection_helper = callable(helper)
        print(
            "[ConnectionCheck] keithley type:",
            type(self.keithley),
            "has connection helper:",
            bool(use_connection_helper),
        )
        self._connection_helper_active = use_connection_helper
        fallback_initialized = False

        if use_connection_helper:
            print("[ConnectionCheck] Using connection_check_sample helper (4200A path).")
        else:
            print("[ConnectionCheck] Using legacy set_voltage/measure_current path.")
            try:
                self.keithley.set_voltage(0.2, 0.1)
                self.keithley.enable_output(True)
                fallback_initialized = True
            except Exception as exc:
                print(f"Error setting up measurement: {exc}")
                return
        
        time.sleep(0.5)
        self.previous_current = None
        while self.check_connection_window:
            try:
                if use_connection_helper and callable(helper):
                    sample = helper()
                    current = float(sample.get("current", 0.0))
                    elapsed_time = time.time() - start_time
                else:
                    if not fallback_initialized:
                        try:
                            self.keithley.set_voltage(0.2, 0.1)
                            self.keithley.enable_output(True)
                            fallback_initialized = True
                            print("[ConnectionCheck] Fallback path initialized.")
                        except Exception as exc:
                            print(f"Error initializing fallback path: {exc}")
                            time.sleep(1.0)
                            continue
                    current_value = self.keithley.measure_current()
                    elapsed_time = time.time() - start_time
                    if isinstance(current_value, (tuple, list)):
                        current = float(current_value[1])
                    else:
                        current = float(current_value) if current_value is not None else 0.0
                
                # Store data for plotting and saving
                self.time_data.append(elapsed_time)
                self.current_data.append(current)

                # Handle sound alerts
                if self.make_sound_var.get():
                    threshold_exceeded = abs(current) >= self.current_threshold_a
                    
                    if self.continuous_sound_var.get():
                        # Continuous mode: beep on every reading that exceeds threshold
                        if threshold_exceeded:
                            self.on_spike_detected(continuous=True)
                    else:
                        # Single beep mode: beep once when threshold is first crossed
                        if not self.noise_already and threshold_exceeded:
                            self.on_spike_detected(continuous=False)

                self.previous_current = current
                self.update_plot(self.time_data, self.current_data, current)
                time.sleep(0.05)
                
            except Exception as e:
                print(f"[ConnectionCheck] Error in measurement loop: {e}")
                if use_connection_helper:
                    print("[ConnectionCheck] Disabling helper and falling back to legacy path.")
                    use_connection_helper = False
                    self._connection_helper_active = False
                    helper = None
                    fallback_initialized = False
                    try:
                        self.keithley.set_voltage(0.2, 0.1)
                        self.keithley.enable_output(True)
                        fallback_initialized = True
                        print("[ConnectionCheck] Legacy fallback initialized.")
                    except Exception as sub_exc:
                        print(f"[ConnectionCheck] Fallback init failed: {sub_exc}")
                        time.sleep(1.0)
                    continue
                time.sleep(0.5)  # Wait before retrying

        if not use_connection_helper:
            try:
                self.keithley.shutdown()
            except Exception:
                pass

    def on_spike_detected(self, continuous: bool = False) -> None:
        """Emit a beep via the instrument and mark spike as handled."""
        played_hw_beep = False
        try:
            self.keithley.beep(400, 0.1 if continuous else 0.5)
            played_hw_beep = True
            if continuous:
                print(f"Continuous beep: I = {abs(self.current_data[-1]):.2e} A")
            else:
                print(f"⚠️ Connection detected! I = {abs(self.current_data[-1]):.2e} A")
                self.noise_already = True
                self.top.after(0, lambda: self.status_text.config(
                    text=f"✓ Connection detected at {abs(self.current_data[-1]):.2e} A", 
                    fg="#4CAF50"
                ))
        except Exception as e:
            print(f"Error making instrument beep: {e}")
        finally:
            if self._is_4200a or not played_hw_beep:
                self._play_system_beep(continuous)

    def _play_system_beep(self, continuous: bool) -> None:
        """Fallback beep using the host system (4200A has no hardware beep)."""
        duration_ms = 100 if continuous else 300
        frequency_hz = 1200 if continuous else 800
        try:
            if winsound is not None:
                winsound.Beep(frequency_hz, duration_ms)
            else:
                print("\a", end="")
        except Exception:
            print("\a", end="")

    def update_plot(self, time_data: List[float], current_data: List[float], current: float) -> None:
        """Update the real-time plot with new data."""
        self.ax.clear()
        
        # Plot the data
        self.ax.plot(time_data, [abs(c) for c in current_data], 
                    color='#2196F3', linewidth=2, label='|Current|')
        
        # Add threshold line
        self.ax.axhline(y=self.current_threshold_a, color='r', 
                       linestyle='--', linewidth=2, alpha=0.7, 
                       label=f'Threshold: {self.current_threshold_a:.2e} A')
        
        # Highlight if currently above threshold
        if abs(current) >= self.current_threshold_a:
            self.ax.plot(time_data[-1], abs(current), 
                        'go', markersize=12, markeredgewidth=2, 
                        markerfacecolor='lime', label='Connection!')
        
        # Styling
        self.ax.set_title("Connection Current vs Time", fontsize=12, fontweight='bold')
        self.ax.set_xlabel("Time (s)", fontsize=10)
        self.ax.set_ylabel("Current (A)", fontsize=10)
        self.ax.set_yscale("log")
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.legend(loc='upper right', fontsize=9)
        
        # Add current value text
        self.ax.text(0.02, 0.98, f'Current: {abs(current):.2e} A', 
                    transform=self.ax.transAxes,
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        self.canvas.draw()

    def close_window(self) -> None:
        self.check_connection_window = False
        if not getattr(self, "_connection_helper_active", False):
            try:
                self.keithley.enable_output(False)
            except Exception:
                pass
        self.top.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    # Note: CheckConnection requires a keithley parameter
    # This is just for testing the import
    # For standalone use, use the wrapper or pass a mock keithley object
    from unittest.mock import MagicMock
    mock_keithley = MagicMock()
    app = CheckConnection(root, mock_keithley)
    root.mainloop()
