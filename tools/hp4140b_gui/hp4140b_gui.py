"""
HP4140B Simple Control GUI

A simple, user-friendly interface for controlling the HP4140B pA Meter/DC Voltage Source.
Designed for straightforward operation with automatic connection on startup.

Features:
- Automatic connection on startup
- Voltage sweep control (voltage, step, current limit, dV/dt)
- Full/half sweep options (direction based on step sign)
- Real-time plotting (linear and log I vs V)
- Automatic data saving with incrementing sample numbers
- Remembers last save location

This is a standalone version that can be run independently from the folder.

Author: Generated for Switchbox_GUI project
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

# Import the controller from the same folder
try:
    from hp4140b_controller import HP4140BController
except ImportError:
    # Fallback: try to import from parent project structure
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from Equipment.SMU_AND_PMU.HP4140B import HP4140BController


class HP4140BGUI:
    """Simple GUI for HP4140B control with automatic connection and data saving."""
    
    def __init__(self, root: tk.Tk):
        """Initialize the GUI and attempt automatic connection."""
        self.root = root
        self.root.title("HP4140B Control Panel")
        self.root.geometry("1400x900")
        
        # Get script directory for relative paths
        self.script_dir = Path(__file__).parent.absolute()
        
        # Instrument connection
        self.instrument: Optional[HP4140BController] = None
        self.connected = False
        self.gpib_address = "GPIB0::17::INSTR"
        
        # Measurement data storage
        self.voltage_data: List[float] = []
        self.current_data: List[float] = []
        
        # Measurement control flags
        self.measuring = False
        self.stop_flag = False
        self._auto_connect_attempted = False
        
        # Save location management (relative to script directory)
        self.config_file = self.script_dir / "hp4140b_config.json"
        self.default_save_dir = Path.home() / "Documents" / "data"
        self.current_save_dir = self.default_save_dir
        self.sample_number = 1
        self._load_config()
        
        # Build GUI
        self._build_gui()
        
        # Attempt automatic connection (silent, won't show error on startup)
        self.root.after(500, self._auto_connect)
    
    def _build_gui(self):
        """Build the GUI interface."""
        # Top frame for save location
        top_frame = tk.Frame(self.root, padx=10, pady=5, bg='#f0f0f0')
        top_frame.pack(fill=tk.X)
        
        tk.Label(top_frame, text="Save Location:", font=('Arial', 10, 'bold'), bg='#f0f0f0').pack(side=tk.LEFT, padx=5)
        self.save_dir_var = tk.StringVar(value=str(self.current_save_dir))
        self.save_dir_entry = tk.Entry(top_frame, textvariable=self.save_dir_var, width=50)
        self.save_dir_entry.pack(side=tk.LEFT, padx=5)
        
        browse_btn = tk.Button(top_frame, text="Browse", command=self._browse_save_location, bg='#4CAF50', fg='white')
        browse_btn.pack(side=tk.LEFT, padx=5)
        
        # Connection status
        self.status_label = tk.Label(top_frame, text="Disconnected", fg='red', font=('Arial', 10, 'bold'), bg='#f0f0f0')
        self.status_label.pack(side=tk.RIGHT, padx=10)
        
        # Control frame (left side)
        control_frame = tk.LabelFrame(self.root, text="Measurement Controls", padx=15, pady=15, font=('Arial', 11, 'bold'))
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # GPIB Address
        tk.Label(control_frame, text="GPIB Address:", font=('Arial', 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.address_var = tk.StringVar(value=self.gpib_address)
        address_entry = tk.Entry(control_frame, textvariable=self.address_var, width=20)
        address_entry.grid(row=0, column=1, pady=5, padx=5)
        
        connect_btn = tk.Button(control_frame, text="Connect", command=self._connect, bg='#2196F3', fg='white', width=10)
        connect_btn.grid(row=0, column=2, pady=5, padx=5)
        
        # Voltage control
        tk.Label(control_frame, text="Voltage (V):", font=('Arial', 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.voltage_var = tk.DoubleVar(value=0.5)
        voltage_entry = tk.Entry(control_frame, textvariable=self.voltage_var, width=15)
        voltage_entry.grid(row=1, column=1, pady=5, padx=5)
        
        # Step control
        tk.Label(control_frame, text="Step (V):", font=('Arial', 10)).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.step_var = tk.DoubleVar(value=0.001)
        step_entry = tk.Entry(control_frame, textvariable=self.step_var, width=15)
        step_entry.grid(row=2, column=1, pady=5, padx=5)
        
        # Current limit
        tk.Label(control_frame, text="Current Limit (A):", font=('Arial', 10)).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.current_limit_var = tk.DoubleVar(value=1e-3)
        current_entry = tk.Entry(control_frame, textvariable=self.current_limit_var, width=15)
        current_entry.grid(row=3, column=1, pady=5, padx=5)
        
        # dV/dt control
        tk.Label(control_frame, text="dV/dt (V/s):", font=('Arial', 10)).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.dvdt_var = tk.DoubleVar(value=0.1)
        dvdt_entry = tk.Entry(control_frame, textvariable=self.dvdt_var, width=15)
        dvdt_entry.grid(row=4, column=1, pady=5, padx=5)
        
        # Sweep type selection
        tk.Label(control_frame, text="Sweep Type:", font=('Arial', 10)).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.sweep_type_var = tk.StringVar(value="Full")
        sweep_frame = tk.Frame(control_frame)
        sweep_frame.grid(row=5, column=1, pady=5, padx=5, sticky=tk.W)
        
        tk.Radiobutton(sweep_frame, text="Full", variable=self.sweep_type_var, value="Full", font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Radiobutton(sweep_frame, text="Half", variable=self.sweep_type_var, value="Half", font=('Arial', 9)).pack(side=tk.LEFT, padx=10)
        
        # Info label about direction
        info_label = tk.Label(control_frame, text="Note: Direction depends on step sign\n(+ = up, - = down)", 
                             font=('Arial', 8), fg='gray', justify=tk.LEFT)
        info_label.grid(row=6, column=0, columnspan=3, pady=5, sticky=tk.W)
        
        # Measure button (big and prominent)
        measure_btn = tk.Button(control_frame, text="START MEASUREMENT", 
                               command=self._start_measurement, 
                               bg='#FF5722', fg='white', 
                               font=('Arial', 14, 'bold'),
                               width=20, height=2)
        measure_btn.grid(row=7, column=0, columnspan=3, pady=20)
        
        # Stop button
        stop_btn = tk.Button(control_frame, text="STOP", 
                            command=self._stop_measurement,
                            bg='#F44336', fg='white',
                            font=('Arial', 12, 'bold'),
                            width=15)
        stop_btn.grid(row=8, column=0, columnspan=3, pady=5)
        
        # Clear plots button
        clear_btn = tk.Button(control_frame, text="Clear Plots", 
                             command=self._clear_plots,
                             bg='#9E9E9E', fg='white',
                             font=('Arial', 10),
                             width=15)
        clear_btn.grid(row=9, column=0, columnspan=3, pady=5)
        
        # Plot frame (right side)
        plot_frame = tk.Frame(self.root)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create matplotlib figure with two subplots side by side
        self.fig = Figure(figsize=(12, 6), dpi=100)
        
        # Linear plot (left)
        self.ax_linear = self.fig.add_subplot(121)
        self.ax_linear.set_xlabel('Voltage (V)', fontsize=11)
        self.ax_linear.set_ylabel('Current (A)', fontsize=11)
        self.ax_linear.set_title('Current vs Voltage', fontsize=12, fontweight='bold')
        self.ax_linear.grid(True, alpha=0.3)
        self.line_linear, = self.ax_linear.plot([], [], 'b-', linewidth=1.5, marker='o', markersize=3)
        
        # Log plot (right)
        self.ax_log = self.fig.add_subplot(122)
        self.ax_log.set_xlabel('Voltage (V)', fontsize=11)
        self.ax_log.set_ylabel('Current (A)', fontsize=11)
        self.ax_log.set_title('Log Current vs Voltage', fontsize=12, fontweight='bold')
        self.ax_log.set_yscale('log')
        self.ax_log.grid(True, alpha=0.3, which='both')
        self.line_log, = self.ax_log.plot([], [], 'r-', linewidth=1.5, marker='o', markersize=3)
        
        self.fig.tight_layout(pad=3.0)
        
        # Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Progress label
        self.progress_label = tk.Label(self.root, text="Ready", font=('Arial', 10), fg='blue')
        self.progress_label.pack(side=tk.BOTTOM, pady=5)
    
    def _load_config(self):
        """Load configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.current_save_dir = Path(config.get('save_dir', str(self.default_save_dir)))
                    self.sample_number = config.get('sample_number', 1)
                    self.gpib_address = config.get('gpib_address', "GPIB0::17::INSTR")
        except Exception as e:
            print(f"Could not load config: {e}")
            self.current_save_dir = self.default_save_dir
            self.sample_number = 1
    
    def _save_config(self):
        """Save configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            config = {
                'save_dir': str(self.current_save_dir),
                'sample_number': self.sample_number,
                'gpib_address': self.gpib_address
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Could not save config: {e}")
    
    def _browse_save_location(self):
        """Browse for save location."""
        folder = filedialog.askdirectory(
            title="Choose Save Location",
            initialdir=str(self.current_save_dir)
        )
        if folder:
            self.current_save_dir = Path(folder)
            self.save_dir_var.set(str(self.current_save_dir))
            self._save_config()
    
    def _auto_connect(self):
        """Attempt automatic connection on startup (silent, no error popup)."""
        self._auto_connect_attempted = True
        self._connect(silent=True)
    
    def _connect(self, silent: bool = False):
        """
        Connect to the HP4140B instrument.
        
        Args:
            silent: If True, don't show error message on failure (for auto-connect)
        """
        self.gpib_address = self.address_var.get()
        
        try:
            # Close existing connection if any
            if self.instrument:
                try:
                    self.instrument.close()
                except:
                    pass
            
            # Connect
            self.instrument = HP4140BController(gpib_address=self.gpib_address)
            self.connected = True
            self.status_label.config(text="Connected", fg='green')
            self.progress_label.config(text=f"Connected to {self.gpib_address}", fg='green')
            
            # Save address
            self._save_config()
            
            if not silent:
                messagebox.showinfo("Connection", "Successfully connected to HP4140B!")
            
        except Exception as e:
            self.connected = False
            self.status_label.config(text="Disconnected", fg='red')
            self.progress_label.config(text=f"Connection failed: {str(e)}", fg='red')
            # Only show error message if not silent (manual connect)
            if not silent:
                messagebox.showerror("Connection Error", 
                                    f"Could not connect to HP4140B:\n{str(e)}\n\nPlease check:\n- GPIB address is correct\n- Instrument is powered on\n- GPIB cable is connected")
            else:
                # Silent failure - just log to console
                print(f"Auto-connect failed: {str(e)}")
                print("You can manually connect using the Connect button.")
    
    def _start_measurement(self):
        """Start the measurement sweep."""
        if not self.connected or not self.instrument:
            messagebox.showerror("Error", "Not connected to instrument!")
            return
        
        if self.measuring:
            messagebox.showwarning("Warning", "Measurement already in progress!")
            return
        
        # Start measurement in separate thread
        import threading
        self.measuring = True
        self.stop_flag = False
        thread = threading.Thread(target=self._run_sweep, daemon=True)
        thread.start()
    
    def _stop_measurement(self):
        """Stop the current measurement."""
        self.stop_flag = True
        self.progress_label.config(text="Stopping measurement...", fg='orange')
    
    def _clear_plots(self):
        """Clear the plot data."""
        self.voltage_data.clear()
        self.current_data.clear()
        self._update_plots()
        self.progress_label.config(text="Plots cleared", fg='blue')
    
    def _run_sweep(self):
        """Run the voltage sweep measurement."""
        try:
            # Get parameters
            voltage = float(self.voltage_var.get())
            step = float(self.step_var.get())
            current_limit = float(self.current_limit_var.get())
            dvdt = float(self.dvdt_var.get())
            sweep_type = self.sweep_type_var.get()
            
            # Clear previous data
            self.voltage_data.clear()
            self.current_data.clear()
            
            # Determine sweep direction and range based on step sign
            if step == 0:
                self.root.after(0, lambda: messagebox.showerror("Error", "Step size cannot be zero!"))
                return
            
            # Determine sweep direction from step sign
            # Voltage parameter represents the magnitude (always positive in GUI)
            # Step sign determines direction:
            #   Positive step (+): 0 → +voltage (upward)
            #   Negative step (-): 0 → -voltage (downward)
            voltage_magnitude = abs(voltage)  # Use absolute value of voltage parameter
            
            if sweep_type == "Full":
                # Full sweep: start at 0, go to target, then back to 0
                if step > 0:
                    # Positive step: 0 → +voltage → 0 (triangle up)
                    # Up sweep: 0 to voltage
                    voltages_up = list(np.arange(0, voltage_magnitude + step/2, step))
                    # Down sweep: voltage back to 0 (reverse, skip first 0 and last voltage to avoid duplicates)
                    if len(voltages_up) > 2:
                        # Skip first (0) and last (voltage) from up sweep, then reverse and add 0 at end
                        voltages_down = list(reversed(voltages_up[1:-1])) + [0.0]
                    elif len(voltages_up) > 1:
                        # Only two points: just add 0 at end
                        voltages_down = [0.0]
                    else:
                        voltages_down = []
                    voltages = voltages_up + voltages_down
                else:
                    # Negative step: 0 → -voltage → 0 (triangle down)
                    step_abs = abs(step)
                    # Down sweep: 0 to -voltage
                    voltages_down = list(np.arange(0, -voltage_magnitude - step_abs/2, step))
                    # Up sweep: -voltage back to 0 (reverse, skip first 0 and last -voltage to avoid duplicates)
                    if len(voltages_down) > 2:
                        # Skip first (0) and last (-voltage) from down sweep, then reverse and add 0 at end
                        voltages_up = list(reversed(voltages_down[1:-1])) + [0.0]
                    elif len(voltages_down) > 1:
                        # Only two points: just add 0 at end
                        voltages_up = [0.0]
                    else:
                        voltages_up = []
                    voltages = voltages_down + voltages_up
            else:
                # Half sweep: start at 0, go to target (direction based on step sign)
                if step > 0:
                    # Positive step = upward sweep (0 to +voltage)
                    voltages = list(np.arange(0, voltage_magnitude + step/2, step))
                else:
                    # Negative step = downward sweep (0 to -voltage)
                    step_abs = abs(step)
                    voltages = list(np.arange(0, -voltage_magnitude - step_abs/2, step))
            
            # Remove duplicates while preserving order
            seen = set()
            voltages_unique = []
            for v in voltages:
                v_rounded = round(v, 6)  # Round to avoid floating point issues
                if v_rounded not in seen:
                    seen.add(v_rounded)
                    voltages_unique.append(v)
            voltages = voltages_unique
            
            self.root.after(0, lambda: self.progress_label.config(
                text=f"Starting sweep: {len(voltages)} points", fg='blue'
            ))
            
            # Enable output
            self.instrument.enable_output(enable=True, channel=1)
            time.sleep(0.1)
            
            # Perform sweep
            for i, v_target in enumerate(voltages):
                if self.stop_flag:
                    break
                
                # Update progress
                self.root.after(0, lambda v=v_target, idx=i, total=len(voltages): 
                               self.progress_label.config(
                                   text=f"Measuring: {v:.4f} V ({idx+1}/{total})", 
                                   fg='blue'
                               ))
                
                # Ramp to target voltage (using dV/dt)
                if dvdt > 0 and i > 0:
                    try:
                        v_current = self.instrument.measure_voltage(channel=1)
                        if not np.isfinite(v_current):
                            v_current = voltages[i-1] if i > 0 else 0.0
                    except Exception:
                        v_current = voltages[i-1] if i > 0 else 0.0
                    
                    dv = abs(v_target - v_current)
                    if dv > 0.001:  # Only ramp if significant change
                        ramp_time = dv / dvdt
                        steps = max(2, int(ramp_time * 10))  # 10 steps per second minimum
                        self.instrument.voltage_ramp(
                            target_voltage_v=v_target,
                            steps=steps,
                            pause_s=0.1,
                            compliance_a=current_limit,
                            channel=1
                        )
                else:
                    # Direct set for first point or if dV/dt is 0
                    self.instrument.set_voltage(
                        voltage=v_target,
                        Icc=current_limit,
                        channel=1
                    )
                    time.sleep(0.2)  # Settling time
                
                # Measure voltage and current
                try:
                    v_measured = self.instrument.measure_voltage(channel=1)
                    time.sleep(0.05)
                    i_measured = self.instrument.measure_current(channel=1)
                    
                    if np.isfinite(v_measured) and np.isfinite(i_measured):
                        self.voltage_data.append(v_measured)
                        self.current_data.append(i_measured)
                        
                        # Update plots in real-time
                        self.root.after(0, self._update_plots)
                        
                except Exception as e:
                    print(f"Measurement error at {v_target}V: {e}")
                    continue
                
                # Small delay between points
                time.sleep(0.05)
            
            # Ramp to zero
            if not self.stop_flag:
                self.root.after(0, lambda: self.progress_label.config(
                    text="Ramping to zero...", fg='blue'
                ))
                try:
                    self.instrument.voltage_ramp(0.0, steps=20, pause_s=0.05, compliance_a=current_limit, channel=1)
                except Exception as e:
                    print(f"Error ramping to zero: {e}")
            
            # Disable output
            try:
                self.instrument.disable_output(channel=1)
            except Exception as e:
                print(f"Error disabling output: {e}")
            
            # Save data automatically
            if self.voltage_data and not self.stop_flag:
                self.root.after(0, self._save_data)
                self.root.after(0, lambda: self.progress_label.config(
                    text=f"Measurement complete! Saved as sample {self.sample_number-1}", 
                    fg='green'
                ))
            else:
                self.root.after(0, lambda: self.progress_label.config(
                    text="Measurement stopped", fg='orange'
                ))
                
        except Exception as e:
            import traceback
            error_msg = f"Error during measurement:\n{str(e)}\n\n{traceback.format_exc()}"
            self.root.after(0, lambda: messagebox.showerror("Measurement Error", error_msg))
            self.root.after(0, lambda: self.progress_label.config(
                text=f"Error: {str(e)}", fg='red'
            ))
        finally:
            self.measuring = False
            if self.instrument:
                try:
                    self.instrument.disable_output(channel=1)
                except:
                    pass
    
    def _update_plots(self):
        """Update the plot displays."""
        if not self.voltage_data or not self.current_data:
            # Clear plots if no data
            self.line_linear.set_data([], [])
            self.line_log.set_data([], [])
            self.canvas.draw()
            return
        
        # Update linear plot
        self.line_linear.set_data(self.voltage_data, self.current_data)
        self.ax_linear.relim()
        self.ax_linear.autoscale_view()
        
        # Update log plot (filter out zero/negative currents for log scale)
        v_log = []
        i_log = []
        for v, i in zip(self.voltage_data, self.current_data):
            if i > 0:
                v_log.append(v)
                i_log.append(i)
        
        if v_log and i_log:
            self.line_log.set_data(v_log, i_log)
            self.ax_log.relim()
            self.ax_log.autoscale_view()
        else:
            # If no positive currents, clear log plot
            self.line_log.set_data([], [])
        
        self.canvas.draw()
    
    def _save_data(self):
        """Save measurement data to file."""
        if not self.voltage_data or not self.current_data:
            return
        
        try:
            # Ensure save directory exists
            self.current_save_dir.mkdir(parents=True, exist_ok=True)
            
            # Create filename with sample number
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sample_{self.sample_number:04d}_{timestamp}.txt"
            filepath = self.current_save_dir / filename
            
            # Save data
            data = np.column_stack((self.voltage_data, self.current_data))
            header = f"HP4140B Measurement - Sample {self.sample_number}\nVoltage (V)\tCurrent (A)"
            np.savetxt(filepath, data, fmt="%.6e\t%.6e", header=header, comments='')
            
            # Increment sample number
            self.sample_number += 1
            self._save_config()
            
            messagebox.showinfo("Data Saved", f"Data saved to:\n{filepath}\n\nNext sample number: {self.sample_number}")
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save data:\n{str(e)}")


def main():
    """Main entry point for the HP4140B GUI."""
    root = tk.Tk()
    app = HP4140BGUI(root)
    
    def on_closing():
        """Handle window closing."""
        if app.measuring:
            if not messagebox.askokcancel("Quit", "Measurement in progress. Stop and quit?"):
                return
            app.stop_flag = True
            time.sleep(0.5)  # Wait for measurement to stop
        
        if app.instrument:
            try:
                app.instrument.disable_output(channel=1)
                app.instrument.close()
            except:
                pass
        
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()

