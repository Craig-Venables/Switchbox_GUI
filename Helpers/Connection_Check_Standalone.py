"""
Standalone Connection Check GUI for Keithley 2400

This is a standalone application for checking electrical connections using a Keithley 2400 SMU.
It applies a small DC bias (0.2V) and plots measured current vs time in real-time.
The application will beep when the absolute current crosses a threshold (default 1e-9 A).

Usage:
    Run this file directly to launch the GUI. You will be prompted for the GPIB address.
    The default GPIB address is 'GPIB0::24::INSTR'.

Dependencies:
    - tkinter (usually included with Python)
    - matplotlib
    - PyMeasure
    - PyVISA and PyVISA-py (for instrument communication)

To create an executable:
    1. Install dependencies: pip install -r requirements.txt
    2. Install PyInstaller: pip install pyinstaller
    3. Run: pyinstaller --onefile --windowed Connection_Check_Standalone.py
    4. The executable will be in the 'dist' folder
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time
import threading
from typing import Any, List, Optional
import sys

# PyMeasure imports
try:
    from pymeasure.instruments.keithley import Keithley2400
except ImportError:
    print("ERROR: PyMeasure not installed. Please install it with: pip install PyMeasure")
    sys.exit(1)


class Keithley2400Controller:
    """
    Controller class for Keithley 2400 Source Measure Unit (SMU).
    
    This class provides a high-level interface to the Keithley 2400 instrument,
    handling voltage sourcing, current measurement, and output control.
    
    Attributes:
        device: The underlying PyMeasure Keithley2400 device object
        _configured: Flag indicating if source is configured
        _cached_icc: Cached compliance current value
        _cached_vrange: Cached voltage range value
        _range_lock: Optional fixed range lock
        _output_enabled: Local tracking of output state
    """
    
    def __init__(self, gpib_address='GPIB0::24::INSTR', timeout=5):
        """
        Initialize connection to Keithley 2400 via PyMeasure.
        
        Args:
            gpib_address: GPIB address string (e.g., 'GPIB0::24::INSTR')
            timeout: Connection timeout in seconds
        """
        try:
            self.device = Keithley2400(gpib_address)
            self.device.adapter.connection.timeout = timeout * 1000  # Convert to milliseconds
            self.device.reset()  # Reset the instrument
            print(f"Connected to: {self.get_idn()}")

            # Cache for source configuration to avoid reapplying each set
            self._configured = False
            self._cached_icc: Optional[float] = None
            self._cached_vrange: Optional[float] = None
            # Optional range lock (when set, set_voltage will not change the source range)
            self._range_lock: Optional[float] = None
            # Track output state locally to avoid querying
            self._output_enabled: bool = False
        except Exception as e:
            print(f"Error initializing Keithley 2400: {e}")
            raise

    def get_idn(self):
        """Query and return the device identity string."""
        return self.device.id if self.device else "No Device Connected"

    def check_errors(self):
        """Check instrument error status."""
        return self.device.ask('SYST:ERR?') if self.device else "No Device Connected"

    def _configure_voltage_source(self, icc: float, v_range: float = 20.0) -> None:
        """Configure source range and compliance once or when changed."""
        if not self.device:
            return
        # Only reconfigure if first time or values changed
        if (not self._configured) or (self._cached_icc != icc) or (self._cached_vrange != v_range):
            # Apply voltage sourcing with desired range and compliance
            self.device.apply_voltage(voltage_range=v_range, compliance_current=icc)
            # Force fixed range when supported (use discrete ranges only: 0.2/2/20/200)
            try:
                if v_range in (0.2, 2.0, 20.0, 200.0):
                    self.device.write(f"SOUR:VOLT:RANG {v_range}")
            except Exception:
                pass
            self._configured = True
            self._cached_icc = icc
            self._cached_vrange = v_range

    def set_voltage(self, voltage, Icc=0.1):
        """Set source level without reconfiguring range/compliance each time."""
        if self.device:
            # Select discrete range based on requested level
            if self._range_lock is not None:
                v_rng = float(self._range_lock)
            else:
                v_abs = abs(float(voltage))
                if v_abs <= 0.2:
                    v_rng = 0.2
                elif v_abs <= 2.0:
                    v_rng = 2.0
                elif v_abs <= 20.0:
                    v_rng = 20.0
                else:
                    v_rng = 200.0
            self._configure_voltage_source(float(Icc), v_rng)
            # Safe auto-enable: if output is OFF, bias 0 V, enable, then set target
            if not self._output_enabled:
                try:
                    self.device.source_voltage = 0.0
                except Exception:
                    pass
                try:
                    self.device.enable_source()
                    self._output_enabled = True
                except Exception:
                    pass
            self.device.source_voltage = voltage

    def measure_voltage(self):
        """Measure and return voltage."""
        return self.device.voltage if self.device else None

    def measure_current(self):
        """Measure and return current."""
        return self.device.current if self.device else None

    def enable_output(self, enable=True):
        """Enable or disable output."""
        if self.device:
            if enable:
                self.device.enable_source()
                self._output_enabled = True
            else:
                self.device.disable_source()
                self._output_enabled = False

    def beep(self, frequency=1000, duration=0.5):
        """Make the instrument beep."""
        if self.device:
            self.device.write(f'SYST:BEEP {frequency}, {duration}')

    def shutdown(self):
        """Ramp current to 0 mA and disable output."""
        if self.device:
            try:
                self.device.source_voltage = 0
                self.device.disable_source()
                self._output_enabled = False
            except Exception:
                pass

    def close(self):
        """Close connection to the instrument."""
        if self.device:
            try:
                self.device.shutdown()
                print("Connection closed.")
            except Exception:
                pass


class CheckConnection:
    """
    Popup window that applies a bias and plots current in real-time.
    
    This GUI provides a real-time monitoring interface for checking electrical connections.
    It applies a small DC bias (0.2V) and continuously measures current, plotting the results
    and optionally alerting when current exceeds a threshold.
    """
    
    def __init__(self, master: tk.Misc, keithley: Any):
        """
        Initialize the connection check GUI.
        
        Args:
            master: Parent Tkinter window
            keithley: Keithley2400Controller instance
        """
        self.master = master
        self.top = tk.Toplevel(master)
        self.top.title("Connection Check - Pin Lowering Assistant")
        self.top.geometry("800x750")
        self.keithley = keithley
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
        # Apply a small bias and enable output
        try:
            self.keithley.set_voltage(0.2, 0.1)
            self.keithley.enable_output(True)
        except Exception as e:
            print(f"Error setting up measurement: {e}")
            self.top.after(0, lambda: messagebox.showerror(
                "Measurement Error",
                f"Failed to set up measurement:\n{e}"
            ))
            return
        
        time.sleep(0.5)
        self.previous_current = None
        while self.check_connection_window:
            try:
                current_value = self.keithley.measure_current()
                elapsed_time = time.time() - start_time
                
                # Handle both tuple (Keithley 4200A) and float (Keithley 2400/2450 TSP) returns
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
                time.sleep(0.2)
                
            except Exception as e:
                print(f"Error in measurement loop: {e}")
                time.sleep(0.5)  # Wait before retrying

        try:
            self.keithley.shutdown()
        except Exception:
            pass

    def on_spike_detected(self, continuous: bool = False) -> None:
        """Emit a beep via the instrument and mark spike as handled."""
        try:
            self.keithley.beep(400, 0.1 if continuous else 0.5)
            if continuous:
                print(f"Continuous beep: I = {abs(self.current_data[-1]):.2e} A")
            else:
                print(f"⚠️ Connection detected! I = {abs(self.current_data[-1]):.2e} A")
                self.noise_already = True
                # Update status on main thread
                self.top.after(0, lambda: self.status_text.config(
                    text=f"✓ Connection detected at {abs(self.current_data[-1]):.2e} A", 
                    fg="#4CAF50"
                ))
        except Exception as e:
            print(f"Error making beep: {e}")

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
        """Close the window and clean up resources."""
        self.check_connection_window = False
        try:
            self.keithley.enable_output(False)
        except Exception:
            pass
        self.top.destroy()


def get_gpib_address() -> str:
    """
    Prompt user for GPIB address with a dialog.
    
    Returns:
        GPIB address string, or None if user cancels
    """
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    address = simpledialog.askstring(
        "GPIB Address",
        "Enter GPIB address for Keithley 2400:\n\n(Default: GPIB0::24::INSTR)",
        initialvalue="GPIB0::24::INSTR",
        parent=root
    )
    
    root.destroy()
    return address


def main():
    """Main entry point for the standalone application."""
    # Get GPIB address from user
    gpib_address = get_gpib_address()
    
    if not gpib_address:
        print("No GPIB address provided. Exiting.")
        return
    
    # Create main window
    root = tk.Tk()
    root.withdraw()  # Hide the main window, we only show the CheckConnection window
    
    # Try to connect to Keithley 2400
    try:
        print(f"Attempting to connect to {gpib_address}...")
        keithley = Keithley2400Controller(gpib_address=gpib_address, timeout=10)
        print(f"Successfully connected to: {keithley.get_idn()}")
    except Exception as e:
        error_msg = f"Failed to connect to Keithley 2400 at {gpib_address}:\n\n{e}\n\nPlease check:\n1. Instrument is powered on\n2. GPIB/USB connection is correct\n3. GPIB address is correct\n4. PyVISA drivers are installed"
        print(error_msg)
        messagebox.showerror("Connection Error", error_msg)
        root.destroy()
        return
    
    # Create and show the connection check GUI
    try:
        app = CheckConnection(root, keithley)
        root.mainloop()
    except KeyboardInterrupt:
        print("Application interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
        messagebox.showerror("Application Error", f"An error occurred:\n\n{e}")
    finally:
        # Cleanup
        try:
            keithley.shutdown()
            keithley.close()
        except Exception:
            pass
        root.destroy()


if __name__ == "__main__":
    main()

