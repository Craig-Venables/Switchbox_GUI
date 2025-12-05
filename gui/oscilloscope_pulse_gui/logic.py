import time
import threading
import numpy as np
from typing import Optional, Callable, Dict, Any, Tuple
import traceback

# Try to import equipment managers, but handle failure for simulation/offline dev
try:
    from Equipment.managers.oscilloscope import OscilloscopeManager
except ImportError:
    OscilloscopeManager = None

class PulseMeasurementLogic:
    """
    Handles the execution of pulse measurements, including:
    - Threading (to keep UI responsive)
    - Hardware control (SMU pulse + Oscilloscope capture)
    - Data processing (Voltage -> Current conversion)
    - Simulation mode (for testing without hardware)
    """

    def __init__(self, smu_instance=None):
        self.smu = smu_instance
        self.scope_manager = None
        if OscilloscopeManager:
            self.scope_manager = OscilloscopeManager(auto_detect=False)
        
        self.is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def set_smu(self, smu_instance):
        """Update the SMU instance (e.g. if connection changes in main GUI)."""
        self.smu = smu_instance

    def start_measurement(self, params: Dict[str, Any], 
                          on_progress: Callable[[str], None],
                          on_data: Callable[[np.ndarray, np.ndarray, np.ndarray, Dict], None],
                          on_error: Callable[[str], None],
                          on_finished: Callable[[], None]):
        """
        Start the measurement sequence in a background thread.
        
        Args:
            params: Dictionary of measurement parameters
            on_progress: Callback for status updates (msg)
            on_data: Callback for successful data (time, voltage, current, metadata)
            on_error: Callback for errors (error_msg)
            on_finished: Callback when thread ends (success or fail)
        """
        if self.is_running:
            return

        self.is_running = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._measurement_worker,
            args=(params, on_progress, on_data, on_error, on_finished),
            daemon=True
        )
        self._thread.start()

    def stop_measurement(self):
        """Signal the measurement thread to stop."""
        self._stop_event.set()

    def _measurement_worker(self, params: Dict[str, Any], 
                            on_progress: Callable, on_data: Callable, 
                            on_error: Callable, on_finished: Callable):
        """Background worker thread for the measurement sequence."""
        try:
            simulation_mode = params.get('simulation_mode', False)
            
            # --- 1. SETUP ---
            on_progress("Configuring hardware...")
            
            pulse_voltage = float(params.get('pulse_voltage', 1.0))
            duration = float(params.get('pulse_duration', 0.001))
            compliance = float(params.get('current_compliance', 0.001))
            pre_delay = float(params.get('pre_pulse_delay', 0.1))
            post_delay = float(params.get('post_pulse_hold', 0.1))
            
            shunt_r = float(params.get('r_shunt', 50.0))
            # Parse scope channel - handle both 'CH1' and '1' formats
            scope_ch_raw = params.get('scope_channel', 1)
            if isinstance(scope_ch_raw, str):
                # Extract number from 'CH1', 'CH2', etc.
                scope_ch = int(''.join(filter(str.isdigit, scope_ch_raw)) or '1')
            else:
                scope_ch = int(scope_ch_raw)
            
            if self._stop_event.is_set(): return

            # Connect/Configure Scope
            if not simulation_mode:
                if not self.scope_manager:
                     raise RuntimeError("Oscilloscope Manager not available (import failed).")
                
                # Ensure connected
                if not self.scope_manager.is_connected():
                    # Try manual connect if address provided, else auto
                    addr = params.get('scope_address')
                    if addr and addr.strip():
                        scope_type = params.get('scope_type', 'Tektronix TBS1000C')
                        # If "Auto-Detect" is selected, try all known types
                        if scope_type == 'Auto-Detect':
                            scope_type = 'Unknown'  # Will trigger trying all types
                        if not self.scope_manager.manual_init_scope(scope_type, addr):
                             raise RuntimeError(f"Could not connect to oscilloscope at {addr}. Please check:\n"
                                              f"1. Address is correct: {addr}\n"
                                              f"2. Scope is powered on and connected\n"
                                              f"3. VISA drivers are installed\n"
                                              f"4. Try 'Auto-Detect' scope type")
                    else:
                        if not self.scope_manager.auto_detect_scope():
                            raise RuntimeError("No oscilloscope detected. Please provide an address.")

                # Configure Scope
                auto_configure = params.get('auto_configure_scope', True)
                
                if auto_configure:
                    print("  Auto-configuring oscilloscope settings...")
                    try:
                        # Set trigger
                        trigger_level = pulse_voltage * 0.5  # Trigger at 50% of pulse voltage
                        trigger_slope = params.get('trigger_slope', 'RISING')
                        self.scope_manager.configure_trigger(
                            source=f'CH{scope_ch}', 
                            level=trigger_level, 
                            slope=trigger_slope, 
                            mode='NORMAL'
                        )
                        print(f"    Trigger: CH{scope_ch} @ {trigger_level:.3f}V ({trigger_slope})")
                        
                        # Set timebase if provided
                        t_scale = params.get('timebase_scale') or params.get('scope_timebase')
                        if t_scale:
                            timebase = float(t_scale)
                            self.scope_manager.configure_timebase(time_per_div=timebase)
                            print(f"    Timebase: {timebase*1e3:.3f} ms/div")
                        else:
                            # Auto-calculate
                            timebase = duration / 2.0 
                            self.scope_manager.configure_timebase(time_per_div=timebase)
                            print(f"    Timebase: {timebase*1e6:.1f} µs/div (auto)")
                        
                        # Set horizontal position (10% left)
                        try:
                            if self.scope_manager.scope:
                                trigger_offset = 4.0 * timebase
                                if hasattr(self.scope_manager.scope, 'set_timebase_position'):
                                    self.scope_manager.scope.set_timebase_position(trigger_offset)
                                    print(f"    Horizontal Pos: {trigger_offset}s (Trigger at left)")
                        except Exception as ex:
                            print(f"    Failed to set horiz pos: {ex}")
                            
                        # Set voltage scale
                        v_scale_val = params.get('voltage_scale') or params.get('scope_vscale')
                        if v_scale_val:
                            v_scale = float(v_scale_val)
                            self.scope_manager.configure_channel(scope_ch, volts_per_div=v_scale)
                            print(f"    Voltage scale: {v_scale:.3f} V/div")
                        else:
                            v_scale = pulse_voltage / 3.0
                            self.scope_manager.configure_channel(scope_ch, volts_per_div=v_scale)
                            print(f"    Voltage scale: {v_scale:.3f} V/div (auto)")
                            
                        print("  Scope configuration sent. Waiting for settling...")
                        time.sleep(1.0) 
                        
                    except Exception as e:
                        print(f"  Warning: Failed to configure scope settings: {e}")
                else:
                    print("  Using manual oscilloscope settings (auto-configure disabled)")
                
                # Arm scope (Single Shot)
                print("  Arming scope for Single Shot capture...")
                if self.scope_manager.scope and hasattr(self.scope_manager.scope, 'set_single_shot'):
                     self.scope_manager.scope.set_single_shot()
                else:
                     # Fallback if specific method missing (shouldn't happen with our edits)
                     self.scope_manager.configure_trigger(source=f'CH{scope_ch}', level=pulse_voltage*0.5, slope=params.get('trigger_slope', 'RISING'), mode='NORMAL')
                
                pass 
            
            # Configure SMU - System-specific
            if not simulation_mode:
                 # Check if SMU exists (might be None if not connected yet)
                 if self.smu is None:
                      raise RuntimeError("SMU not connected. Please click 'Connect SMU' button first.")
                 
                 # Check system type
                 system_name = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                 
                 if system_name == 'keithley4200a':
                     # For 4200A, no pre-configuration needed
                     # Pulse will be executed via KXCI command
                     pass
                 else:
                     # For 2450/2400, check connection and set to 0V
                     if not self.smu.is_connected():
                         raise RuntimeError("SMU not connected.")
                     # Ensure 0V start
                     self.smu.set_voltage(0.0, Icc=compliance)
                     self.smu.enable_output(True)
            
            if self._stop_event.is_set(): 
                if not simulation_mode and self.smu:
                    system_name = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                    if system_name != 'keithley4200a':
                        self.smu.enable_output(False)
                return

            # --- 2. EXECUTION ---
            on_progress("Waiting pre-pulse...")
            time.sleep(pre_delay)
            
            if self._stop_event.is_set(): return

            on_progress("Pulsing...")
            
            # Execute pulse - System-specific
            if not simulation_mode:
                system_name = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                
                if system_name == 'keithley4200a':
                    # Use KXCI SMU_pulse_measure for 4200A
                    try:
                        from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import KXCIClient, format_param
                        
                        # Get GPIB address from SMU
                        gpib_address = getattr(self.smu, '_address', 'GPIB0::17::INSTR')
                        
                        # Create KXCI client
                        kxci = KXCIClient(gpib_address=gpib_address, timeout=30.0)
                        if not kxci.connect():
                            raise RuntimeError("Failed to connect to 4200A for pulse")
                        
                        try:
                            # Enter UL mode
                            kxci._enter_ul_mode()
                            
                            # Build SMU_pulse_measure command
                            # EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(initialize, logMessages, widthTime, Amplitude, Irange, Icomp, measResistance)
                            # Parameters: initialize(0/1), logMessages(0/1), widthTime(s), Amplitude(V), Irange(A), Icomp(A), measResistance(unused)
                            params_list = [
                                "1",  # initialize = 1 (DO initialize - required for measurement to work!)
                                "1",  # logMessages = 1 (enable debug output to see what's happening)
                                format_param(duration),  # widthTime in seconds
                                format_param(pulse_voltage),  # Amplitude in volts
                                format_param(compliance),  # Irange
                                format_param(compliance),  # Icomp
                                ""  # measResistance (empty/unused)
                            ]
                            command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure({','.join(params_list)})"
                            
                            # Execute command
                            return_value, error = kxci._execute_ex_command(command)
                            
                            if error:
                                raise RuntimeError(f"SMU_pulse_measure failed: {error}")
                            
                        finally:
                            kxci._exit_ul_mode()
                            kxci.disconnect()
                            
                    except Exception as e:
                        raise RuntimeError(f"4200A pulse execution failed: {e}")
                else:
                    # For 2450/2400, use standard set_voltage method
                    # Start Pulse
                    self.smu.set_voltage(pulse_voltage, Icc=compliance)
                    
                    # Wait Pulse Duration
                    # Critical timing section
                    start_time = time.perf_counter()
                    while (time.perf_counter() - start_time) < duration:
                        pass # Busy wait for precision on short pulses, or use sleep for long
                    
                    # End Pulse
                    self.smu.set_voltage(0.0, Icc=compliance)
                
            on_progress("Hold time...")
            time.sleep(post_delay)
            
            if not simulation_mode:
                system_name = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                if system_name != 'keithley4200a':
                    self.smu.enable_output(False)

            # --- 3. ACQUISITION ---
            on_progress("Acquiring data...")
            
            if simulation_mode:
                # Generate fake data
                total_time = pre_delay + duration + post_delay
                t = np.linspace(0, total_time, 1000)
                v_scope = np.zeros_like(t)
                
                # Create a pulse in the middle
                start_idx = int(1000 * (pre_delay / total_time))
                end_idx = int(1000 * ((pre_delay + duration) / total_time))
                
                # Add some rise/fall time and noise
                v_scope[start_idx:end_idx] = pulse_voltage * (shunt_r / (shunt_r + 1000)) # voltage divider effect
                noise = np.random.normal(0, 0.01, len(t))
                v_scope += noise
                
                # Current (I = V / R)
                current = v_scope / shunt_r
            else:
                # Real acquisition
                # The oscilloscope was connected earlier, but the VISA session may have
                # timed out during the pulse delays. Always reconnect before acquisition.
                
                addr = params.get('scope_address')
                scope_type = params.get('scope_type', 'Tektronix TBS1000C')
                
                if not addr:
                    raise RuntimeError("No oscilloscope address provided")
                
                # Close any existing connection
                if self.scope_manager.scope:
                    try:
                        self.scope_manager.scope.disconnect()
                    except:
                        pass
                
                # Reconnect fresh
                print(f"Reconnecting to oscilloscope at {addr} for waveform acquisition...")
                if not self.scope_manager.manual_init_scope(scope_type, addr):
                    raise RuntimeError(f"Failed to connect to oscilloscope at {addr}")
                
                scope = self.scope_manager.scope
                if scope is None:
                    raise RuntimeError("Oscilloscope manager has no active scope instance")
                
                print("✓ Oscilloscope reconnected successfully")
                
                # Reconfigure trigger and timebase (only if auto-configure is enabled)
                # ERROR FIX: Configuring AFTER the pulse clears the acquisition!
                # Configuration logic moved to Setup phase (before pulse).
                # Here we strictly READ the data.
                pass
                
                # auto_configure = params.get('auto_configure_scope', True)
                # if auto_configure: ... (REMOVED)
                
                # Now acquire waveform with fresh connection
                try:
                    # Get Requested Record Length (e.g. 20k -> 20000)
                    rec_len_k = float(params.get('record_length', 20))
                    num_points = int(rec_len_k * 1000)
                    
                    print(f"  Acquiring waveform ({num_points} points target)...")
                    t, v_scope = scope.acquire_waveform(channel=scope_ch, format='ASCII', num_points=num_points)
                    print(f"  Captured {len(t)} points.")
                except Exception as e:
                    raise RuntimeError(f"Failed to acquire waveform: {e}")
                
                if len(t) == 0:
                    raise RuntimeError("Failed to acquire waveform from oscilloscope.")
                
                # Calculate Current
                if params.get('measurement_method') == 'shunt':
                    # I = V_shunt / R_shunt
                    # Note: If measuring across shunt to ground, V_scope = V_shunt. 
                    # If high-side shunt, this is more complex (requires differential probe or math).
                    # Assuming Low-Side Shunt for standard setup (Device -> Shunt -> GND).
                    current = v_scope / shunt_r
                else:
                    # SMU Current method fallback (not really synchronous with scope trace)
                    # For this scope-centric tool, we might just return flat line or cached SMU reading?
                    # Let's just return zeros if not using shunt, or user relies on V_scope only.
                    current = np.zeros_like(v_scope)

            # --- 4. FINISH ---
            metadata = {
                'timestamp': time.time(),
                'params': params,
                'shunt_resistance': shunt_r
            }
            
            on_data(t, v_scope, current, metadata)
            on_progress("Done.")
            
        except Exception as e:
            traceback.print_exc()
            on_error(str(e))
        finally:
            # Ensure safety
            if not simulation_mode and self.smu:
                try:
                    system_name = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                    if system_name != 'keithley4200a':
                        self.smu.enable_output(False)
                except:
                    pass
            self.is_running = False
            on_finished()
