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
                        # Step 1: Enable and configure channel FIRST (before trigger)
                        # Enable channel display
                        self.scope_manager.enable_channel(scope_ch, enable=True)
                        print(f"    Channel CH{scope_ch}: Enabled")
                        
                        # Set channel coupling to DC (required for shunt resistor measurements)
                        self.scope_manager.configure_channel(scope_ch, coupling='DC')
                        print(f"    Channel CH{scope_ch}: DC coupling")
                        
                        # Set voltage scale
                        v_scale_val = params.get('voltage_scale') or params.get('scope_vscale')
                        if v_scale_val:
                            v_scale = float(v_scale_val)
                        else:
                            # Auto-calculate: use pulse voltage / 3 to show pulse with some headroom
                            v_scale = pulse_voltage / 3.0
                            # Ensure reasonable minimum (at least 10mV/div for small signals)
                            v_scale = max(v_scale, 0.01)
                        
                        self.scope_manager.configure_channel(scope_ch, volts_per_div=v_scale)
                        print(f"    Voltage scale: {v_scale:.3f} V/div")
                        
                        # Step 2: Configure timebase
                        t_scale = params.get('timebase_scale') or params.get('scope_timebase')
                        if t_scale:
                            timebase = float(t_scale)
                            self.scope_manager.configure_timebase(time_per_div=timebase)
                            print(f"    Timebase: {timebase*1e3:.3f} ms/div")
                            
                            # Validate that timebase is large enough for total measurement time
                            total_measurement_time = pre_delay + duration + post_delay
                            time_window = timebase * 10.0  # 10 divisions on screen
                            if time_window < total_measurement_time:
                                print(f"    ⚠️ WARNING: Timebase too small!")
                                print(f"       Time window: {time_window:.3f}s, Required: {total_measurement_time:.3f}s")
                                print(f"       Recommended timebase: {(total_measurement_time * 1.2) / 10.0:.3f} s/div")
                        else:
                            # Auto-calculate based on TOTAL measurement time (not just pulse duration)
                            # Total time = pre_delay + duration + post_delay
                            total_measurement_time = pre_delay + duration + post_delay
                            # Add 20% margin for safety and ensure we capture the full window
                            # Timebase = (total_time + margin) / 10 divisions
                            timebase = (total_measurement_time * 1.2) / 10.0
                            
                            # Ensure minimum timebase for very short pulses (at least 1ms/div)
                            min_timebase = 1e-3 / 10.0  # 1ms/div minimum
                            timebase = max(timebase, min_timebase)
                            
                            self.scope_manager.configure_timebase(time_per_div=timebase)
                            time_window = timebase * 10.0
                            print(f"    Timebase: {timebase*1e3:.3f} ms/div (auto-calculated)")
                            print(f"    Time window: {time_window:.3f}s (covers {total_measurement_time:.3f}s measurement)")
                        
                        # Step 3: Set horizontal position (trigger position)
                        # Position trigger at ~40% from left (4 divisions) to capture pre-pulse
                        try:
                            if self.scope_manager.scope:
                                trigger_offset = 4.0 * timebase
                                if hasattr(self.scope_manager.scope, 'set_timebase_position'):
                                    self.scope_manager.scope.set_timebase_position(trigger_offset)
                                    print(f"    Horizontal Pos: {trigger_offset:.3f}s (Trigger at ~40% from left)")
                        except Exception as ex:
                            print(f"    Failed to set horiz pos: {ex}")
                        
                        # Step 4: Configure trigger (AFTER channel and timebase are set)
                        trigger_level = pulse_voltage * 0.5  # Trigger at 50% of pulse voltage
                        trigger_slope = params.get('trigger_slope', 'RISING')
                        self.scope_manager.configure_trigger(
                            source=f'CH{scope_ch}', 
                            level=trigger_level, 
                            slope=trigger_slope, 
                            mode='NORMAL'  # NORMAL mode waits for trigger
                        )
                        print(f"    Trigger: CH{scope_ch} @ {trigger_level:.3f}V ({trigger_slope})")
                            
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
                # Generate realistic memristor switching simulation
                total_time = pre_delay + duration + post_delay
                num_points = 5000  # Higher resolution for smooth switching
                t = np.linspace(0, total_time, num_points)
                
                # Memristor parameters
                r_initial = 10000.0  # Initial resistance: 10 kΩ (high resistance state)
                r_final = 1000.0     # Final resistance: 1 kΩ (low resistance state)
                switching_time = duration * 0.3  # Switch over 30% of pulse duration
                switching_start = pre_delay + duration * 0.1  # Start switching 10% into pulse
                
                # Calculate memristor resistance over time
                r_memristor_t = np.full_like(t, r_initial)
                pulse_mask = (t >= pre_delay) & (t <= (pre_delay + duration))
                
                # During pulse, memristor switches from high to low resistance
                for i, time_val in enumerate(t):
                    if pulse_mask[i]:
                        if time_val >= switching_start and time_val <= (switching_start + switching_time):
                            # Exponential switching transition
                            progress = (time_val - switching_start) / switching_time
                            # Smooth exponential decay
                            r_memristor_t[i] = r_initial * np.exp(-progress * np.log(r_initial / r_final))
                        elif time_val > (switching_start + switching_time):
                            # After switching, maintain low resistance
                            r_memristor_t[i] = r_final
                
                # Calculate circuit behavior
                # Total resistance: R_total = R_memristor + R_shunt
                r_total = r_memristor_t + shunt_r
                
                # Current through circuit: I = V_SMU / R_total (during pulse)
                current = np.zeros_like(t)
                current[pulse_mask] = pulse_voltage / r_total[pulse_mask]
                
                # Voltage across shunt: V_shunt = I × R_shunt
                v_scope = current * shunt_r
                
                # Add realistic noise (0.1% of signal)
                noise_level = np.max(v_scope) * 0.001
                noise = np.random.normal(0, noise_level, len(t))
                v_scope += noise
                
                # Add rise/fall time to pulse edges (RC-like behavior)
                rise_time = duration * 0.01  # 1% of pulse duration
                fall_time = duration * 0.01
                
                # Smooth rise at pulse start
                pulse_start = pre_delay
                pulse_end = pre_delay + duration
                rise_mask = (t >= pulse_start) & (t < (pulse_start + rise_time))
                fall_mask = (t >= (pulse_end - fall_time)) & (t <= pulse_end)
                
                if np.any(rise_mask):
                    rise_progress = (t[rise_mask] - pulse_start) / rise_time
                    v_scope[rise_mask] *= (1 - np.exp(-5 * rise_progress))  # Exponential rise
                
                if np.any(fall_mask):
                    fall_progress = (t[fall_mask] - (pulse_end - fall_time)) / fall_time
                    v_scope[fall_mask] *= np.exp(-5 * fall_progress)  # Exponential fall
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
                
                # Calculate Current (always using shunt method)
                # I = V_shunt / R_shunt
                # Note: If measuring across shunt to ground, V_scope = V_shunt. 
                # If high-side shunt, this is more complex (requires differential probe or math).
                # Assuming Low-Side Shunt for standard setup (Device -> Shunt -> GND).
                current = v_scope / shunt_r

            # --- 4. FINISH ---
            metadata = {
                'timestamp': time.time(),
                'params': params,
                'shunt_resistance': shunt_r,
                'pulse_voltage': pulse_voltage  # Include for voltage breakdown calculation
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
