import sys
import os
import tkinter as tk
from tkinter import messagebox, filedialog
import numpy as np
import json
from pathlib import Path

# --- Standalone Execution Hack ---
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    try:
        from gui.oscilloscope_pulse_gui.logic import PulseMeasurementLogic
        from gui.oscilloscope_pulse_gui.config_manager import ConfigManager
        from gui.oscilloscope_pulse_gui.layout import OscilloscopePulseLayout
        from Pulse_Testing.system_wrapper import SystemWrapper, detect_system_from_address
    except ImportError:
        sys.path.append(os.path.dirname(current_dir)) 
        from logic import PulseMeasurementLogic
        from config_manager import ConfigManager
        from layout import OscilloscopePulseLayout
        try:
            from Pulse_Testing.system_wrapper import SystemWrapper, detect_system_from_address
        except ImportError:
            SystemWrapper = None
            detect_system_from_address = None
    
    # Try to import connection manager for dropdowns if available
    try:
        from Measurments.connection_manager import InstrumentConnectionManager
    except ImportError:
        InstrumentConnectionManager = None

else:
    from .logic import PulseMeasurementLogic
    from .config_manager import ConfigManager
    from .layout import OscilloscopePulseLayout
    try:
        from Pulse_Testing.system_wrapper import SystemWrapper, detect_system_from_address
    except ImportError:
        SystemWrapper = None
        detect_system_from_address = None
    # In integrated mode, manager usually passed or importable
    try:
        from Measurments.connection_manager import InstrumentConnectionManager
    except ImportError:
        InstrumentConnectionManager = None

class OscilloscopePulseGUI(tk.Toplevel):
    """
    Main Window for Oscilloscope Pulse Capture.
    Controller class that glues Logic and Layout together.
    """
    
    def __init__(self, master=None, smu_instance=None, context=None):
        """
        Args:
            master: Tk parent.
            smu_instance: Existing SMU adapter if any.
            context: Dict with keys:
                'device_label': str
                'sample_name': str
                'save_directory': str/Path
                'smu_ports': list[str]
                'scope_ports': list[str]
        """
        if __name__ == "__main__":
             if master is None: master = tk.Tk()
             super().__init__(master)
        else:
             super().__init__(master)
             
        self.title("Oscilloscope Pulse Capture")
        self.geometry("1400x900")
        
        # 1. State & Config
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        
        # Initialize SystemWrapper for SMU connection
        self.system_wrapper = SystemWrapper() if SystemWrapper else None
        self.current_system_name = None
        
        self.smu = smu_instance 
        self.logic = PulseMeasurementLogic(smu_instance)
        
        # 2. Prepare Context (Dropdowns, Info)
        self.context = context or {}
        self._populate_context_defaults()

        # 3. Layout (View)
        self.layout = OscilloscopePulseLayout(
            parent=self, 
            callbacks={
                'start': self._start_measurement,
                'stop': self._stop_measurement,
                'save': self._save_data_dialog,
                'browse_save': self._browse_save_path,
                'refresh_scopes': self._refresh_scope_list,
                'on_system_change': self._on_system_change,
                'quick_test': self._quick_test_device,
                'read_scope_settings': self._read_scope_settings,
                'connect_smu': self._connect_smu
            },
            config=self.config,
            context=self.context
        )
        
        # 4. Final Setup
        self.is_running = False
        self.last_data = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _populate_context_defaults(self):
        """Ensure context has necessary keys, auto-discovering if standalone."""
        if 'device_label' not in self.context: self.context['device_label'] = "Stand-alone"
        if 'sample_name' not in self.context: self.context['sample_name'] = "Test"
        if 'save_directory' not in self.context: 
            self.context['save_directory'] = str(Path.home() / "Documents" / "PulseData")
            os.makedirs(self.context['save_directory'], exist_ok=True)
            
        if 'known_systems' not in self.context:
            self.context['known_systems'] = ["keithley4200a", "keithley2450"]

        # Hardware Discovery (if standalone or not provided)
        if 'smu_ports' not in self.context or not self.context['smu_ports']:
            # Minimal hardcoded list or detection logic could go here
            self.context['smu_ports'] = ["GPIB0::17::INSTR", "GPIB0::18::INSTR", "USB0::..."]
            
        if 'scope_ports' not in self.context:
            self.context['scope_ports'] = [] # Populated on refresh

    def _refresh_scope_list(self):
        """Callback to refresh scope dropdown using Manager logic."""
        # This is a bit hacky: we access logic's manager if available
        # or we instantiate a temp one. Logic has scope_manager.
        mgr = self.logic.scope_manager
        if mgr:
             # This might block UI slightly, but usually fast. 
             # For smoother UI, run in thread.
             # For now, just return existing known + maybe "Auto"
             pass # logic.scope_manager.auto_detect returns bool, doesn't list all.
             # We might need to extend OscilloscopeManager to list resources.
             # For now, we'll just allow typing or config persistence.
             # If using PyVisa directly:
             try:
                 import pyvisa
                 rm = pyvisa.ResourceManager()
                 resources = list(rm.list_resources())
                 self.layout.widgets['scope_combo']['values'] = resources
             except:
                 pass

    def _start_measurement(self):
        try:
            params = self.layout.get_params()
            
            # Update Config
            self.config.update(params)
            self.config_manager.save_config(self.config)
            
        except Exception as e:
            messagebox.showerror("Configuration Error", str(e))
            return

        self.layout.set_running_state(True)
        self.layout.set_status("Starting...")
        self.layout.reset_plots()
        
        # Pass full context to logic params for metadata
        params.update({
            'device_label': self.context.get('device_label'),
            'sample_name': self.context.get('sample_name'),
            'system': self.layout.vars.get('system', tk.StringVar()).get()
        })

        self.logic.start_measurement(
            params,
            on_progress=self._update_status,
            on_data=self._on_data_received,
            on_error=self._on_error,
            on_finished=self._on_finished
        )

    def _stop_measurement(self):
        self.logic.stop_measurement()
        self.layout.set_status("Stopping...")

    def _update_status(self, msg):
        self.after(0, lambda: self.layout.set_status(msg))

    def _on_data_received(self, t, v, i, metadata):
        def update_plot():
            self.last_data = (t, v, i, metadata)
            # Update plots including zoom
            self.layout.update_plots(t, v, i)
            
            # Zoom logic: center closely around pulse
            # We know params['pre_pulse_delay'] and duration
            # But simpler: find where v > 0.1 * max(v) ?
            # Logic: Zoom to [start_of_pulse - margin, end_of_pulse + margin]
            # If simulated or we trust timing:
            try:
                # Metadata might carry exact timing from logic?
                # If not, use config
                pre = float(self.config.get('pre_pulse_delay', 0.1))
                dur = float(self.config.get('pulse_duration', 0.001))
                zoomed_start = max(0, pre - dur*0.5)
                zoomed_end = pre + dur*1.5 
                
                self.layout.ax_zoom.set_xlim(zoomed_start, zoomed_end)
                self.layout.canvas.draw()
            except:
                pass
                
        self.after(0, update_plot)

    def _on_error(self, error_msg):
        self.after(0, lambda: messagebox.showerror("Measurement Error", error_msg))

    def _on_finished(self):
        def reset_ui():
            self.layout.set_running_state(False)
            if "Stopping" in self.layout.vars['status'].get():
                self.layout.set_status("Stopped.")
            else:
                self.layout.set_status("Measurement Complete.")
                
            # Auto-save Check? Or "Simple Save" flow?
            # User requirement: "simple save will forced" if standalone
            # Actually standard practice: Just save to default dir with timestamp
            self._auto_save_if_needed()
            
        self.after(0, reset_ui)
        
    def _auto_save_if_needed(self):
        # Implementation of auto-save to context['save_directory']
        if not self.last_data: return
        t, v, i, meta = self.last_data
        
        # Simple filename: Pulse_{sample}_{device}_{timestamp}.txt
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"Pulse_{self.context.get('sample_name','Sample')}_{self.context.get('device_label','Device')}_{ts}.txt"
        
        # Ensure directory exists
        save_dir = Path(self.context.get('save_directory', '.'))
        try:
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / fname
            
            self._write_file(str(save_path), t, v, i, meta)
            self.layout.set_status(f"Auto-saved to {fname}")
        except Exception as e:
            print(f"Auto-save failed: {e}")

    def _save_data_dialog(self):
        if not hasattr(self, 'last_data') or self.last_data is None:
            messagebox.showinfo("Info", "No data to save.")
            return
            
        initial_dir = self.context.get('save_directory', "")
        filename = filedialog.asksaveasfilename(
            initialdir=initial_dir,
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("CSV Data", "*.csv"), ("JSON Data", "*.json")]
        )
        if not filename: return
        
        t, v, i, meta = self.last_data
        self._write_file(filename, t, v, i, meta)

    def _write_file(self, filename, t, v, i, meta):
        try:
            if filename.endswith('.txt'):
                with open(filename, 'w') as f:
                    import datetime
                    # Write Header
                    f.write(f"Timestamp: {datetime.datetime.now()}\n")
                    f.write(f"Device: {self.context.get('device_label', 'Unknown')}\n")
                    f.write(f"Sample: {self.context.get('sample_name', 'Unknown')}\n")
                    f.write("-" * 40 + "\n")
                    f.write("Parameters:\n")
                    # Handle nested meta params
                    params = meta.get('params', meta)
                    for k, val in params.items():
                        if isinstance(val, (str, int, float, bool)):
                           f.write(f"{k}: {val}\n")
                    f.write("-" * 40 + "\n")
                    f.write("Time(s)\tVoltage(V)\tCurrent(A)\n")
                    
                    # Write Data
                    for j in range(len(t)):
                        f.write(f"{t[j]:.9e}\t{v[j]:.9e}\t{i[j]:.9e}\n")
                        
            elif filename.endswith('.json'):
                data = meta.copy()
                data['time'] = t.tolist()
                data['voltage'] = v.tolist()
                data['current'] = i.tolist()
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
            elif filename.endswith('.csv'):
                import pandas as pd
                df = pd.DataFrame({'time': t, 'voltage': v, 'current': i})
                df.to_csv(filename, index=False)
            elif filename.endswith('.npz'):
                np.savez(filename, time=t, voltage=v, current=i, metadata=meta)
            
            messagebox.showinfo("Success", f"Saved to {os.path.basename(filename)}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _browse_save_path(self):
        path = filedialog.askdirectory()
        if path:
            self.context['save_directory'] = path
            self.layout.vars['save_dir'].set(path)
    
    def _connect_smu(self):
        """Connect to SMU using SystemWrapper"""
        try:
            if not self.system_wrapper:
                messagebox.showerror("Error", "SystemWrapper not available. Cannot connect to SMU.")
                return
            
            address = self.layout.vars['smu_address'].get()
            system_name = self.layout.vars['system'].get()
            
            # Auto-detect system if possible
            if detect_system_from_address:
                detected = detect_system_from_address(address)
                if detected and detected != system_name:
                    self.layout.vars['system'].set(detected)
                    system_name = detected
            
            # Connect using system wrapper
            self.layout.vars['smu_status'].set("Connecting...")
            self.layout.widgets['smu_status_label'].config(foreground="orange")
            self.update()
            
            connected_system = self.system_wrapper.connect(
                address=address,
                system_name=system_name
            )
            
            self.current_system_name = connected_system
            idn = self.system_wrapper.get_idn()
            
            # Update logic with connected system
            self.logic.set_smu(self.system_wrapper.current_system)
            
            # Update status
            self.layout.vars['smu_status'].set(f"SMU: Connected ({connected_system.upper()})")
            self.layout.widgets['smu_status_label'].config(foreground="green")
            
            messagebox.showinfo("Success", f"Connected to {idn}")
        except Exception as e:
            self.layout.vars['smu_status'].set("SMU: Connection Failed")
            self.layout.widgets['smu_status_label'].config(foreground="red")
            messagebox.showerror("Connection Error", f"Failed to connect to SMU: {str(e)}")

    def _on_system_change(self):
        """Callback when system dropdown changes"""
        system = self.layout.vars.get('system', tk.StringVar()).get()
        if system and self.system_wrapper:
            # Update any system-specific settings if needed
            self.config['system'] = system
            # self.logic.set_system(system) # If logic supports it
    
    def _quick_test_device(self, voltage):
        """Perform a quick pulse to measure device current at specified voltage"""
        try:
            # Check if SMU is connected via SystemWrapper
            if not self.system_wrapper or not self.system_wrapper.is_connected():
                return None
            
            smu = self.system_wrapper.current_system
            
            # Simple measurement: apply voltage and read current
            compliance = float(self.layout.vars.get('current_compliance', tk.StringVar(value="0.001")).get())
            
            # For 4200A, we need to use specific methods
            # For 2450, we use standard set_voltage/enable_output
            if self.current_system_name == 'keithley4200a':
                # Use smu_slow_pulse_measure for 4200A
                try:
                    result = smu.smu_slow_pulse_measure(
                        pulse_voltage=voltage,
                        pulse_width=0.1,  # 100ms pulse
                        i_compliance=compliance,
                        i_range=compliance  # Auto-range
                    )
                    # Extract current from result - returns 'currents' (plural)
                    if 'currents' in result and len(result['currents']) > 0:
                        # Get the current value
                        import numpy as np
                        current = np.mean(result['currents'])
                        return current
                except Exception as e:
                    print(f"4200A quick test error: {e}")
                    return None
            else:
                # For 2450, use standard methods
                smu.set_voltage(voltage, Icc=compliance)
                smu.enable_output(True)
                
                # Wait for settling
                import time
                time.sleep(0.05)
                
                # Measure current
                current = smu.measure_current()
                
                # Turn off
                smu.set_voltage(0.0, Icc=compliance)
                smu.enable_output(False)
                
                return current
            
        except Exception as e:
            print(f"Quick test error: {e}")
            return None

    def _read_scope_settings(self):
        """Read current settings from the oscilloscope via logic layer"""
        try:
            if not self.logic.scope_manager:
                print("Error: Scope manager not initialized")
                return None
            
            # Ensure connected
            if not self.logic.scope_manager.is_connected():
                # Try to connect using address from GUI
                addr = self.layout.vars['scope_address'].get()
                scope_type = self.layout.vars['scope_type'].get()
                
                if not addr:
                    print("Error: No scope address provided")
                    return None
                    
                print(f"Connecting to scope at {addr}...")
                # Map 'Auto-Detect' to 'Unknown' or handle it
                if scope_type == 'Auto-Detect':
                    if not self.logic.scope_manager.auto_detect_scope():
                        return None
                else:
                    if not self.logic.scope_manager.manual_init_scope(scope_type, addr):
                        return None
            
            # Get selected channel
            channel_str = self.layout.vars['scope_channel'].get()
            # Extract number
            channel = int(''.join(filter(str.isdigit, channel_str)) or '1')
            
            # Read settings
            settings = {}
            if self.logic.scope_manager.scope:
                try:
                    # Access the underlying scope driver directly
                    settings['timebase'] = self.logic.scope_manager.scope.get_timebase_scale()
                    settings['voltage_scale'] = self.logic.scope_manager.scope.get_channel_scale(channel)
                    settings['trigger_level'] = self.logic.scope_manager.scope.get_trigger_level()
                    settings['trigger_mode'] = self.logic.scope_manager.scope.get_trigger_mode()
                except AttributeError:
                    print(f"Warning: Scope driver does not support all getter methods")
                except Exception as e:
                    print(f"Warning: Error reading specific settings: {e}")
            else:
                 print("Error: Manager has no active scope instance")
                 return None
            
            print(f"Read scope settings: {settings}")
            return settings
            
        except Exception as e:
            print(f"Error reading scope settings: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _on_close(self):
        """Handle window close"""
        if self.is_running:
            if messagebox.askokcancel("Quit", "Measurement in progress. Stop and quit?"):
                self._stop_measurement()
                self.destroy()
        else:
            self.destroy()


# Standalone execution
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = OscilloscopePulseGUI(root)
    root.mainloop()
