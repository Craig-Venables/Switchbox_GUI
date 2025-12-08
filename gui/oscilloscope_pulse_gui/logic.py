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
            
            # CRITICAL: Cache system name ONCE at start to avoid VISA calls during scope acquisition
            # Calling get_system_name() later opens GPIB connection which can invalidate USB scope session!
            system_name_cached = 'unknown'
            if not simulation_mode and self.smu:
                try:
                    system_name_cached = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                    print(f"SMU System: {system_name_cached}")
                except Exception as e:
                    print(f"Warning: Could not get SMU system name: {e}")
                    system_name_cached = 'unknown'
            
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
                    print("  Auto-configuring oscilloscope (reset to defaults + full setup)...")
                    try:
                        scope_inst = self.scope_manager.scope
                        
                        # Step 0: RESET to factory defaults and increase timeout
                        print("    Resetting scope to factory defaults...")
                        scope_inst.reset()  # Sends *RST
                        time.sleep(2.0)  # Wait for reset to complete
                        
                        # Increase VISA timeout to prevent session expiration during long pulses
                        total_measurement_time = pre_delay + duration + post_delay
                        # Set timeout to 2x the total measurement time + 30s buffer for acquisition
                        timeout_ms = int((total_measurement_time * 2.0 + 30.0) * 1000)
                        timeout_ms = max(timeout_ms, 30000)  # Minimum 30 seconds
                        if hasattr(scope_inst, 'inst') and scope_inst.inst:
                            scope_inst.inst.timeout = timeout_ms
                            print(f"    VISA timeout: {timeout_ms/1000:.1f}s (prevents session expiration)")
                        
                        # Step 1: Set acquisition mode for best resolution
                        if hasattr(scope_inst, 'configure_acquisition'):
                            scope_inst.configure_acquisition(mode='SAMPLE', stop_after='SEQUENCE')
                            print(f"    Acquisition mode: SAMPLE (single-shot)")
                        
                        # Step 2: Enable and configure channel
                        self.scope_manager.enable_channel(scope_ch, enable=True)
                        self.scope_manager.configure_channel(scope_ch, coupling='DC')
                        print(f"    Channel CH{scope_ch}: Enabled, DC coupling")
                        
                        # Step 3: Set probe attenuation to 1x AFTER channel config (critical for correct readings!)
                        # Reset sets it to 10x by default, so we must explicitly set to 1x
                        try:
                            scope_inst.write(f"CH{scope_ch}:PROBE 1")
                            # Verify it was set correctly
                            probe_setting = scope_inst.query(f"CH{scope_ch}:PROBE?").strip()
                            print(f"    Channel CH{scope_ch}: Probe attenuation set to 1x (verified: {probe_setting})")
                        except Exception as ex:
                            print(f"    ⚠️ Could not set/verify probe attenuation: {ex}")
                        
                        # Step 4: Apply known-good settings from scope_settings.json
                        # Force record length to 20k (scope will clamp if needed)
                        target_points = 20000
                        
                        applied_points = self.scope_manager.configure_record_length(target_points)
                        
                        # Read back actual record length (scope may limit it at slow timebases)
                        try:
                            actual_record = scope_inst.query("HOR:RECO?").strip()
                            actual_points = int(actual_record)
                            print(f"    Record length: {actual_points} points (requested {target_points}, scope set {actual_points})")
                            if actual_points < target_points:
                                print(f"    ⚠️ Scope limited record length to {actual_points} at this timebase")
                                print(f"       To get {target_points} points, use faster timebase (<100 ms/div)")
                            applied_points = actual_points
                        except:
                            if applied_points:
                                print(f"    Record length: {applied_points} points (max resolution)")
                            else:
                                print(f"    Record length: {target_points} points requested")
                        
                        # Step 5: Force timebase to known-good value (0.2 s/div)
                        timebase = 0.2
                        desired_window = timebase * 10.0
                        
                        # Validate against config values (warn if they're way off)
                        t_scale_config = params.get('timebase_scale') or params.get('scope_timebase')
                        if t_scale_config:
                            config_timebase = float(t_scale_config)
                            config_window = config_timebase * 10.0
                            if abs(config_window - (timebase * 10.0)) > total_measurement_time * 0.5:
                                print(f"    ⚠️ Config timebase ({config_timebase:.4f} s/div) ignored - auto-calculating instead")
                                print(f"       Config would give {config_window:.4f}s window, need ~{total_measurement_time:.4f}s")
                        
                        # Apply the calculated timebase
                        self.scope_manager.configure_timebase(time_per_div=timebase)
                        time_window = timebase * 10.0
                        
                        # Calculate expected resolution metrics
                        points_for_calc = applied_points if applied_points else target_points
                        sample_interval = time_window / points_for_calc if points_for_calc > 0 else 0
                        sample_rate = 1.0 / sample_interval if sample_interval > 0 else 0
                        
                        print(f"    Timebase: {timebase:.6f} s/div ({timebase*1e3:.3f} ms/div) [FORCED]")
                        print(f"    Total window: {time_window:.6f} s (target: {desired_window:.4f}s)")
                        print(f"    Expected sample interval: {sample_interval:.6e} s")
                        print(f"    Expected sample rate: {sample_rate:.3f} Sa/s")
                        print(f"    Target points: {points_for_calc} (scope may return less at slow timebases)")
                        
                        # Step 6: Set voltage scale to known-good value (0.2 V/div)
                        v_scale = 0.2
                        self.scope_manager.configure_channel(scope_ch, volts_per_div=v_scale)
                        print(f"    Voltage scale: {v_scale:.4f} V/div [FORCED]")
                        
                        # Step 7: Position trigger to capture pre-pulse baseline
                        # Set trigger at ~20% from left edge (2 divisions) to capture pre-pulse
                        try:
                            if scope_inst and hasattr(scope_inst, 'set_timebase_position'):
                                # Trigger position: want trigger at -3 divisions from center (20% from left)
                                trigger_pos = -3.0 * timebase
                                scope_inst.set_timebase_position(trigger_pos)
                                print(f"    Horizontal position: {trigger_pos:.6f}s (trigger at 20% from left)")
                        except Exception as ex:
                            print(f"    ⚠️ Could not set horizontal position: {ex}")
                        
                        # Step 8: Configure trigger (NORMAL mode, noise-safe threshold)
                        # Force trigger level to 50 mV as per working settings
                        trigger_level = 0.05
                        
                        # Auto-select trigger slope based on pulse polarity
                        trigger_slope_param = params.get('trigger_slope')
                        if trigger_slope_param and str(trigger_slope_param).strip():
                            trigger_slope = str(trigger_slope_param).upper()
                        else:
                            # Auto: positive pulse -> RISING, negative -> FALLING
                            trigger_slope = 'FALLING' if pulse_voltage < 0 else 'RISING'
                        
                        # Set holdoff to prevent re-triggering during measurement
                        holdoff_s = total_measurement_time * 1.5  # 50% extra margin
                        
                        self.scope_manager.configure_trigger(
                            source=f'CH{scope_ch}', 
                            level=trigger_level,  # Trigger level based on expected signal
                            slope=trigger_slope, 
                            mode='NORMAL',  # NORMAL mode waits for valid trigger
                            holdoff=holdoff_s
                        )
                        print(f"    Trigger: CH{scope_ch} @ {trigger_level*1e3:.1f}mV")
                        print(f"    Trigger slope: {trigger_slope} [AUTO for {'+' if pulse_voltage >= 0 else '-'}{abs(pulse_voltage):.2f}V pulse]")
                        print(f"    Trigger holdoff: {holdoff_s:.4f}s (prevents re-trigger)")
                            
                        print("  ✓ Scope configured for high-resolution capture")
                        print("  Waiting for scope to settle...")
                        time.sleep(0.5)  # Brief settling time
                        
                    except Exception as e:
                        print(f"  ⚠️ Warning: Scope configuration error: {e}")
                        traceback.print_exc()
                else:
                    print("  Using manual oscilloscope settings (auto-configure disabled)")
                
                # Arm scope (Single Shot)
                print("  Arming scope for Single Shot capture...")
                scope_inst = self.scope_manager.scope
                if scope_inst and hasattr(scope_inst, 'set_single_shot'):
                     scope_inst.set_single_shot()
                     print("  ✓ Scope armed (SEQUENCE mode - will auto-stop after trigger)")
                else:
                     # Fallback
                     self.scope_manager.configure_trigger(source=f'CH{scope_ch}', level=pulse_voltage*0.5, slope=params.get('trigger_slope', 'RISING'), mode='NORMAL')
                     print("  ✓ Scope configured for normal trigger mode")
                
                # Give scope a moment to fully arm before disconnecting
                time.sleep(1.0)
                
                # CRITICAL: Close scope connection to prevent VISA conflicts with SMU
                # The scope will hold the triggered waveform in SEQUENCE mode even when disconnected
                print("  Closing scope connection (waveform will be held in memory)...")
                if scope_inst:
                    try:
                        scope_inst.disconnect()
                        print("  ✓ Scope disconnected - ready for SMU pulse")
                    except Exception as ex:
                        print(f"  ⚠️ Warning: Could not disconnect scope cleanly: {ex}") 
                
                # Wait for scope to fully settle after arming/disconnecting (critical for reliable triggering)
                # On subsequent runs, the scope needs more time to be ready
                print("  Waiting for scope to settle before SMU pulse (5 seconds)...")
                time.sleep(5.0)
            
            # Configure SMU - System-specific
            if not simulation_mode:
                 # Check if SMU exists (might be None if not connected yet)
                 if self.smu is None:
                      raise RuntimeError("SMU not connected. Please click 'Connect SMU' button first.")
                 
                 # Use cached system name (already retrieved above)
                 if system_name_cached == 'keithley4200a':
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
                    if system_name_cached != 'keithley4200a':
                        self.smu.enable_output(False)
                return

            # --- 2. EXECUTION ---
            on_progress("Waiting pre-pulse...")
            time.sleep(pre_delay)
            
            if self._stop_event.is_set(): return

            on_progress("Pulsing...")
            
            # Execute pulse - System-specific
            if not simulation_mode:
                # Use cached system name to avoid VISA calls during scope acquisition
                if system_name_cached == 'keithley4200a':
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
            
            # Simple time-based wait - scope is disconnected so we can't poll it
            # The scope will trigger, capture, and hold the waveform in SEQUENCE mode
            time.sleep(post_delay)
            # Extra guard time before reconnecting to read the screen
            time.sleep(1.0)
            
            if not simulation_mode:
                # Use cached system name
                if system_name_cached != 'keithley4200a':
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
                # Reconnect to scope to read the waveform (it's been disconnected to avoid VISA conflicts)
                # Give the scope a brief moment to finalize capture before reconnecting
                time.sleep(5)
                print("Reconnecting to oscilloscope to read waveform...")
                addr = params.get('scope_address')
                scope_type = params.get('scope_type', 'Tektronix TBS1000C')
                
                if not addr:
                    raise RuntimeError("No oscilloscope address provided for reconnection")
                
                # Reconnect to scope (waveform should still be in memory from SEQUENCE trigger)
                if not self.scope_manager.manual_init_scope(scope_type, addr):
                    raise RuntimeError(f"Failed to reconnect to oscilloscope at {addr}")
                
                scope = self.scope_manager.scope
                if scope is None:
                    raise RuntimeError("Reconnection succeeded but scope instance is None")
                
                # CRITICAL: Check if scope actually triggered and stopped
                print("✓ Reconnected - checking if scope triggered...")
                try:
                    acq_state = scope.query("ACQ:STATE?").strip()
                    trigger_state = scope.query("TRIG:STATE?").strip() if hasattr(scope, 'query') else "UNKNOWN"
                    
                    print(f"  Acquisition state: {acq_state} (0=STOP, 1=RUN)")
                    print(f"  Trigger state: {trigger_state}")
                    
                    if acq_state == "1" or acq_state.upper() == "RUN":
                        print("  ❌ Scope did not trigger (still RUN). Not reading data.")
                        raise RuntimeError("Scope did not trigger. Please lower trigger level or check signal on CH1.")
                    elif acq_state == "0" or acq_state.upper() == "STOP":
                        print("  ✓ Scope STOPPED - acquisition completed (triggered successfully)")
                    
                except Exception as e:
                    print(f"  ⚠️ Could not check acquisition state: {e}")
                    print("  Proceeding to read waveform anyway...")
                
                print("Reading captured waveform...")
                
                def _read_screen_buffer(active_scope):
                    # Read whatever is currently on screen without reconfiguring
                    active_scope.write(f"DAT:SOU CH{scope_ch}")
                    active_scope.write("DAT:ENC ASCII")
                    active_scope.write("DAT:WID 1")

                    preamble = active_scope.get_waveform_preamble(scope_ch)
                    record_len = self.scope_manager.scope._extract_record_length(preamble)
                    try:
                        rec_query = active_scope.query("HOR:RECO?").strip()
                        record_len = max(record_len, int(rec_query))
                    except Exception:
                        pass

                    x_incr = preamble.get("XINCR", None)
                    x_zero = preamble.get("XZERO", 0.0)
                    y_mult = preamble.get("YMULT", None)
                    print(f"  Preamble: record_len={record_len}, XINCR={x_incr}, XZERO={x_zero}, YMULT={y_mult}")

                    active_scope.write("DAT:STAR 1")
                    active_scope.write(f"DAT:STOP {record_len}")

                    data_str = active_scope.query("CURV?")
                    data_points = []
                    for value in data_str.split(','):
                        try:
                            data_points.append(float(value.strip()))
                        except ValueError:
                            continue
                    y_values = np.array(data_points, dtype=np.float64)
                    y_values = active_scope._scale_waveform_values(y_values, preamble)
                    num_points = len(y_values)

                    if num_points > 1:
                        if x_incr is None:
                            try:
                                tb_scale = float(active_scope.query("HOR:SCA?"))
                            except Exception:
                                tb_scale = timebase
                            window = tb_scale * 10.0
                            time_values = np.linspace(0.0, window, num_points)
                        else:
                            time_values = active_scope._build_time_array(num_points, preamble, fallback_scale=None)
                            window = time_values[-1] - time_values[0]
                            if window <= 0:
                                try:
                                    tb_scale = float(active_scope.query("HOR:SCA?"))
                                except Exception:
                                    tb_scale = timebase
                                window = tb_scale * 10.0
                                time_values = np.linspace(0.0, window, num_points)
                        time_window = time_values[-1] - time_values[0]
                        sample_rate = len(time_values) / time_window if time_window > 0 else 0
                        print(f"  ✓ Captured {len(time_values)} points from screen")
                        print(f"  Time window: {time_window:.6f} s, dt ≈ {time_window/(len(time_values)-1):.6e} s, Fs ≈ {sample_rate:.3f} Sa/s")
                    else:
                        time_values = np.array([], dtype=np.float64)
                        print(f"  Captured {num_points} points (empty)")
                    return time_values, y_values
                
                # Acquire waveform (should be in memory from SEQUENCE trigger)
                try:
                    t, v_scope = _read_screen_buffer(scope)
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to acquire waveform from oscilloscope.\n"
                        f"Possible causes:\n"
                        f"1. Scope didn't trigger (check trigger level and source)\n"
                        f"2. Wrong channel selected (using CH{scope_ch})\n"
                        f"3. Waveform overwritten or empty screen\n"
                        f"Original error: {e}"
                    ) from e
                
                if len(t) == 0:
                    raise RuntimeError("Failed to acquire waveform from oscilloscope.")
                
                # Calculate Current (always using shunt method)
                # I = V_shunt / R_shunt
                # Note: If measuring across shunt to ground, V_scope = V_shunt. 
                # If high-side shunt, this is more complex (requires differential probe or math).
                # Assuming Low-Side Shunt for standard setup (Device -> Shunt -> GND).
                current = v_scope / shunt_r

            # --- 4. FINISH ---
            # Detect actual pulse start in scope data by finding where signal rises above threshold
            pulse_start_time = pre_delay  # Default fallback
            if len(v_scope) > 10 and len(t) == len(v_scope):
                # Find where signal rises significantly (pulse detection)
                v_max = np.max(np.abs(v_scope))
                threshold = max(v_max * 0.1, 0.01)  # 10% of max or 10mV minimum
                
                # For positive pulses, find first significant rise
                if pulse_voltage > 0:
                    rising_edge = np.where(v_scope > threshold)[0]
                else:
                    rising_edge = np.where(v_scope < -threshold)[0]
                
                if len(rising_edge) > 0:
                    pulse_start_idx = rising_edge[0]
                    pulse_start_time = t[pulse_start_idx]
                    print(f"  Detected pulse start at t={pulse_start_time:.6f}s (index {pulse_start_idx})")
                else:
                    print(f"  Could not detect pulse start, using pre_delay={pre_delay:.4f}s")
            
            metadata = {
                'timestamp': time.time(),
                'params': params,
                'shunt_resistance': shunt_r,
                'pulse_voltage': pulse_voltage,
                'pulse_start_time': pulse_start_time,  # Detected or fallback to pre_delay
                'pulse_duration': duration  # Pulse duration for V_SMU calculation
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
                    # Use cached system name if available, otherwise get it (fallback)
                    smu_sys_name = system_name_cached if 'system_name_cached' in locals() else 'unknown'
                    if smu_sys_name == 'unknown':
                        smu_sys_name = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                    if smu_sys_name != 'keithley4200a':
                        self.smu.enable_output(False)
                except:
                    pass
            self.is_running = False
            on_finished()
