import sys
import os
import tkinter as tk
from tkinter import messagebox, filedialog
import numpy as np
import json
from pathlib import Path

# Get project root (go up from gui/oscilloscope_pulse_gui/ to project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # gui/oscilloscope_pulse_gui/main.py -> gui -> root

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
        # Start maximized for full-screen view (Windows-friendly)
        try:
            self.state("zoomed")
        except Exception:
            pass
        
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

        # 3. Layout container with scrollbars
        container = tk.Frame(self)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        v_scroll = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        h_scroll = tk.Scrollbar(container, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        content_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=content_frame, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        content_frame.bind("<Configure>", _on_frame_configure)

        # 4. Layout (View)
        self.layout = OscilloscopePulseLayout(
            parent=content_frame, 
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

    def _load_systems_from_json(self):
        """Load system configurations from JSON file (same method as measurement GUI)
        
        Returns:
            List of system config names (e.g., ['Lab_Laser-4200A_C', 'Lab Small-2401', ...])
            Same format as measurement GUI - uses named configs, not just system types
        """
        config_file = _PROJECT_ROOT / "Json_Files" / "system_configs.json"
        
        try:
            with open(config_file, 'r') as f:
                system_configs = json.load(f)
            
            # Store configs for later use
            self.system_configs = system_configs
            
            # Return list of config names (same as measurement GUI)
            systems_list = list(system_configs.keys())
            
            # Fallback if no systems found
            if not systems_list:
                systems_list = ["No systems available"]
            
            return systems_list
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load systems from JSON: {e}")
            # Fallback
            self.system_configs = {}
            return ["No systems available"]
    
    def _populate_context_defaults(self):
        """Ensure context has necessary keys, auto-discovering if standalone."""
        if 'device_label' not in self.context: self.context['device_label'] = "Stand-alone"
        if 'sample_name' not in self.context: self.context['sample_name'] = "Test"
        if 'save_directory' not in self.context: 
            self.context['save_directory'] = str(Path.home() / "Documents" / "PulseData")
            os.makedirs(self.context['save_directory'], exist_ok=True)
            
        # Load systems from JSON file (same method as measurement GUI)
        if 'known_systems' not in self.context:
            self.context['known_systems'] = self._load_systems_from_json()

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
            # Update plots with metadata for calculations
            self.layout.update_plots(t, v, i, metadata)
                
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
                
            # Auto-save if enabled
            auto_save_var = self.layout.vars.get('auto_save')
            if auto_save_var:
                auto_save_enabled = auto_save_var.get()
            else:
                auto_save_enabled = True  # Default to enabled if not set
            
            if auto_save_enabled:
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
            import numpy as np
            
            # Calculate all derived quantities for saving
            pulse_voltage = meta.get('pulse_voltage', 1.0)
            if 'params' in meta:
                params = meta['params']
                pulse_voltage = float(params.get('pulse_voltage', pulse_voltage))
                pre_delay = float(params.get('pre_pulse_delay', 0.1))
                pulse_duration = float(params.get('pulse_duration', 0.001))
            else:
                pre_delay = 0.1
                pulse_duration = 0.001
            
            shunt_r = meta.get('shunt_resistance', 50.0)
            
            # V_shunt is what we measured (v)
            v_shunt = v
            
            # V_SMU is the applied pulse voltage
            pulse_start = pre_delay
            pulse_end = pre_delay + pulse_duration
            v_smu = np.where((t >= pulse_start) & (t <= pulse_end), pulse_voltage, 0.0)
            
            # V_memristor = V_SMU - V_shunt (Kirchhoff's voltage law)
            v_memristor = np.maximum(v_smu - v_shunt, 0.0)
            
            # R_memristor = V_memristor / I (Ohm's law)
            with np.errstate(divide='ignore', invalid='ignore'):
                r_memristor = np.divide(v_memristor, i, out=np.full_like(v_memristor, np.nan), where=i!=0)
                r_memristor = np.where(np.isfinite(r_memristor) & (r_memristor < 1e12), r_memristor, np.nan)
            
            # P_memristor = V_memristor × I
            p_memristor = np.maximum(v_memristor * i, 0.0)
            
            if filename.endswith('.txt'):
                with open(filename, 'w', encoding='utf-8') as f:
                    import datetime
                    # Write Header
                    f.write(f"Timestamp: {datetime.datetime.now()}\n")
                    f.write(f"Device: {self.context.get('device_label', 'Unknown')}\n")
                    f.write(f"Sample: {self.context.get('sample_name', 'Unknown')}\n")
                    f.write("=" * 60 + "\n")
                    f.write("MEASUREMENT PARAMETERS\n")
                    f.write("=" * 60 + "\n")
                    # Handle nested meta params
                    params = meta.get('params', meta)
                    for k, val in params.items():
                        if isinstance(val, (str, int, float, bool)):
                           f.write(f"{k}: {val}\n")
                    f.write("\n")
                    f.write("=" * 60 + "\n")
                    f.write("CALCULATED VALUES SUMMARY\n")
                    f.write("=" * 60 + "\n")
                    
                    # Calculate statistics
                    valid_r_mask = ~np.isnan(r_memristor) & np.isfinite(r_memristor)
                    if np.any(valid_r_mask):
                        r_valid = r_memristor[valid_r_mask]
                        initial_r = r_valid[0] if len(r_valid) > 0 else np.nan
                        final_r = r_valid[-1] if len(r_valid) > 0 else np.nan
                        min_r = np.nanmin(r_valid) if len(r_valid) > 0 else np.nan
                        max_r = np.nanmax(r_valid) if len(r_valid) > 0 else np.nan
                        mean_r = np.nanmean(r_valid) if len(r_valid) > 0 else np.nan
                        
                        def format_resistance(r_val):
                            if np.isnan(r_val):
                                return "N/A"
                            if r_val >= 1e6:
                                return f"{r_val/1e6:.3f} MΩ"
                            elif r_val >= 1e3:
                                return f"{r_val/1e3:.3f} kΩ"
                            else:
                                return f"{r_val:.3f} Ω"
                        
                        f.write(f"Initial Memristor Resistance: {format_resistance(initial_r)}\n")
                        f.write(f"Final Memristor Resistance: {format_resistance(final_r)}\n")
                        f.write(f"Minimum Memristor Resistance: {format_resistance(min_r)}\n")
                        f.write(f"Maximum Memristor Resistance: {format_resistance(max_r)}\n")
                        f.write(f"Mean Memristor Resistance: {format_resistance(mean_r)}\n")
                        if not np.isnan(initial_r) and not np.isnan(final_r) and initial_r > 0:
                            resistance_ratio = final_r / initial_r
                            f.write(f"Resistance Ratio (Final/Initial): {resistance_ratio:.4f}\n")
                    
                    # Power statistics
                    if len(p_memristor) > 0:
                        peak_power = np.nanmax(p_memristor)
                        mean_power = np.nanmean(p_memristor[p_memristor > 0]) if np.any(p_memristor > 0) else 0.0
                        total_energy = np.trapz(p_memristor, t)  # Integrate power over time
                        f.write(f"\nPeak Power: {peak_power*1e3:.3f} mW\n")
                        f.write(f"Mean Power: {mean_power*1e3:.3f} mW\n")
                        f.write(f"Total Energy: {total_energy*1e3:.3f} mJ\n")
                    
                    # Current statistics
                    if len(i) > 0:
                        peak_current = np.nanmax(np.abs(i))
                        mean_current = np.nanmean(np.abs(i[i != 0])) if np.any(i != 0) else 0.0
                        f.write(f"\nPeak Current: {peak_current*1e3:.3f} mA\n")
                        f.write(f"Mean Current: {mean_current*1e3:.3f} mA\n")
                    
                    f.write("\n")
                    f.write("=" * 60 + "\n")
                    f.write("TIME SERIES DATA\n")
                    f.write("=" * 60 + "\n")
                    f.write("Time(s)\tV_SMU(V)\tV_shunt(V)\tV_memristor(V)\tCurrent(A)\tR_memristor(Ω)\tPower(W)\n")
                    
                    # Write Data
                    for j in range(len(t)):
                        r_str = f"{r_memristor[j]:.9e}" if not np.isnan(r_memristor[j]) else "NaN"
                        f.write(f"{t[j]:.9e}\t{v_smu[j]:.9e}\t{v_shunt[j]:.9e}\t{v_memristor[j]:.9e}\t{i[j]:.9e}\t{r_str}\t{p_memristor[j]:.9e}\n")
                        
            elif filename.endswith('.json'):
                data = meta.copy()
                data['time'] = t.tolist()
                data['voltage_shunt'] = v.tolist()
                data['voltage_smu'] = v_smu.tolist()
                data['voltage_memristor'] = v_memristor.tolist()
                data['current'] = i.tolist()
                # Convert NaN to None for JSON compatibility
                r_memristor_list = [float(x) if not np.isnan(x) else None for x in r_memristor]
                data['resistance_memristor'] = r_memristor_list
                data['power_memristor'] = p_memristor.tolist()
                # Add statistics
                valid_r_mask = ~np.isnan(r_memristor) & np.isfinite(r_memristor)
                if np.any(valid_r_mask):
                    r_valid = r_memristor[valid_r_mask]
                    data['statistics'] = {
                        'initial_resistance': float(r_valid[0]) if len(r_valid) > 0 else None,
                        'final_resistance': float(r_valid[-1]) if len(r_valid) > 0 else None,
                        'min_resistance': float(np.nanmin(r_valid)) if len(r_valid) > 0 else None,
                        'max_resistance': float(np.nanmax(r_valid)) if len(r_valid) > 0 else None,
                        'mean_resistance': float(np.nanmean(r_valid)) if len(r_valid) > 0 else None,
                        'peak_power': float(np.nanmax(p_memristor)) if len(p_memristor) > 0 else None,
                        'total_energy': float(np.trapz(p_memristor, t)) if len(p_memristor) > 0 else None,
                        'peak_current': float(np.nanmax(np.abs(i))) if len(i) > 0 else None
                    }
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif filename.endswith('.csv'):
                import pandas as pd
                df = pd.DataFrame({
                    'time': t,
                    'voltage_smu': v_smu,
                    'voltage_shunt': v_shunt,
                    'voltage_memristor': v_memristor,
                    'current': i,
                    'resistance_memristor': r_memristor,
                    'power_memristor': p_memristor
                })
                df.to_csv(filename, index=False, encoding='utf-8')
            elif filename.endswith('.npz'):
                np.savez(filename, 
                        time=t, 
                        voltage_shunt=v_shunt, 
                        voltage_smu=v_smu,
                        voltage_memristor=v_memristor,
                        current=i, 
                        resistance_memristor=r_memristor,
                        power_memristor=p_memristor,
                        metadata=meta)
            
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
            system_config_name = self.layout.vars['system'].get()
            
            # Determine system type from config name (same as measurement GUI)
            system_type = None
            if hasattr(self, 'system_configs') and system_config_name in self.system_configs:
                config = self.system_configs[system_config_name]
                smu_type = config.get("SMU Type", "").lower()
                
                # Map SMU Type to system identifier
                if "4200" in smu_type or "4200a" in smu_type:
                    system_type = "keithley4200a"
                elif "2450" in smu_type:
                    system_type = "keithley2450"
                elif "2400" in smu_type or "2401" in smu_type:
                    system_type = "keithley2400"
            
            # Fallback: auto-detect system from address if config lookup failed
            if not system_type and detect_system_from_address:
                system_type = detect_system_from_address(address)
            
            if not system_type:
                messagebox.showerror("Error", "Could not determine system type. Please check system configuration.")
                return
            
            # Connect using system wrapper
            self.layout.vars['smu_status'].set("Connecting...")
            self.layout.widgets['smu_status_label'].config(foreground="orange")
            self.update()
            
            connected_system = self.system_wrapper.connect(
                address=address,
                system_name=system_type  # Use system type, not config name
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
        """Callback when system dropdown changes - auto-populates SMU address from JSON config
        Same method as measurement GUI - uses named config selection
        """
        system_config_name = self.layout.vars.get('system', tk.StringVar()).get()
        if not system_config_name or system_config_name == "No systems available":
            return
        
        # Update config
        self.config['system'] = system_config_name
        
        # Load system configs if not already loaded
        if not hasattr(self, 'system_configs') or not self.system_configs:
            try:
                config_file = _PROJECT_ROOT / "Json_Files" / "system_configs.json"
                with open(config_file, 'r') as f:
                    self.system_configs = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                self.layout.set_status("⚠️ Could not load system configs from JSON")
                return
        
        # Get the selected config (same as measurement GUI)
        if system_config_name not in self.system_configs:
            self.layout.set_status(f"⚠️ System config '{system_config_name}' not found")
            return
        
        config = self.system_configs[system_config_name]
        smu_address = config.get("SMU_address", "")
        smu_type = config.get("SMU Type", "")
        
        if not smu_address:
            self.layout.set_status(f"⚠️ No SMU address found for '{system_config_name}'")
            return
        
        # For 2450, try to find a USB device with "2450" in it (auto-detect if USB)
        if "2450" in smu_type and smu_address.startswith("USB"):
            try:
                import pyvisa
                rm = pyvisa.ResourceManager()
                resources = list(rm.list_resources())
                
                # Look for USB devices containing "2450"
                for res in resources:
                    if res.startswith('USB') and '2450' in res.upper():
                        smu_address = res
                        break
            except:
                pass  # Use config address if scanning fails
        
        # Update the SMU address field
        if 'smu_address' in self.layout.vars:
            self.layout.vars['smu_address'].set(smu_address)
            self.config['smu_address'] = smu_address
            
            # Update the combobox values if it exists
            if 'smu_address' in self.layout.widgets:
                combo = self.layout.widgets['smu_address']
                current_values = list(combo['values']) if combo['values'] else []
                if smu_address not in current_values:
                    combo['values'] = list(current_values) + [smu_address]
            
            self.layout.set_status(f"System: {system_config_name} ({smu_type}), address: {smu_address}")
    
    def _quick_test_device(self, voltage, duration=0.1, compliance=None):
        """Perform a quick pulse to measure device current at specified voltage
        
        Args:
            voltage: Pulse voltage in volts
            duration: Pulse duration in seconds (default: 0.1)
            compliance: Current compliance in amps (default: from GUI or 0.001)
        """
        try:
            # Check if SMU is connected via SystemWrapper
            if not self.system_wrapper or not self.system_wrapper.is_connected():
                return None
            
            smu = self.system_wrapper.current_system
            
            # Get compliance from parameter or GUI
            if compliance is None:
                compliance = float(self.layout.vars.get('current_compliance', tk.StringVar(value="0.001")).get())
            
            # For 4200A, we need to use specific methods
            # For 2450, we use standard set_voltage/enable_output
            if self.current_system_name == 'keithley4200a':
                # Use smu_slow_pulse_measure for 4200A
                try:
                    result = smu.smu_slow_pulse_measure(
                        pulse_voltage=voltage,
                        pulse_width=duration,
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
                time.sleep(min(0.05, duration * 0.1))  # Wait proportional to duration
                
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
