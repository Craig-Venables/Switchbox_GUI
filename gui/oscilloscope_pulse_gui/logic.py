import time
import threading
import numpy as np
from typing import Optional, Callable, Dict, Any, Tuple
import traceback

# ==================== DEBUG CONTROL ====================
# Set to False to disable all debug print statements
DEBUG_ENABLED = True

def debug_print(*args, **kwargs):
    """Print debug messages only if DEBUG_ENABLED is True."""
    if DEBUG_ENABLED:
        print(*args, **kwargs)
# =======================================================

# Timing knobs (adjust as needed)
SCOPE_ARM_SETTLE_S = 1.0      # Wait after arming before disconnecting scope
SCOPE_POST_DISCONNECT_S = 5.0 # Wait after disconnecting scope before SMU pulse
SCOPE_POST_HOLD_EXTRA_S = 1.0 # Extra wait after post-delay before reconnect/read

# NOTE: Scope probe remains at 10x (cannot force 1x on this unit). We compensate in
# software by dividing captured voltages by 10 to get correct 1x-equivalent values.

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

    def send_pulse_only(self, params: Dict[str, Any],
                        on_progress: Callable[[str], None],
                        on_error: Callable[[str], None],
                        on_finished: Callable[[], None]):
        """
        Send SMU pulse only, without any oscilloscope interaction.
        Useful for manual scope setup/triggering.
        """
        if self.is_running:
            return
        
        self.is_running = True
        self._stop_event.clear()
        
        self._thread = threading.Thread(
            target=self._pulse_only_worker,
            args=(params, on_progress, on_error, on_finished),
            daemon=True
        )
        self._thread.start()

    def start_scope_capture(self, params: Dict[str, Any],
                            on_progress: Callable[[str], None],
                            on_data: Callable[[np.ndarray, np.ndarray, np.ndarray, Dict], None],
                            on_error: Callable[[str], None],
                            on_finished: Callable[[], None]):
        """Grab current waveform from scope without pulsing/configuring."""
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._scope_only_worker,
            args=(params, on_progress, on_data, on_error, on_finished),
            daemon=True
        )
        self._thread.start()

    def _read_screen_buffer(self, scope, scope_ch):
        """Read current screen buffer and return time, voltage arrays.
        Simplified version - minimal queries for speed."""
        if not hasattr(scope, 'inst') or scope.inst is None:
            raise RuntimeError("Scope instrument not connected")
        
        # Minimal setup - just read what's on screen
        scope.write(f"DAT:SOU CH{scope_ch}")
        scope.write("DAT:ENC ASCII")
        scope.write("DAT:WID 1")

        # Get preamble (contains essential scaling info)
        preamble = scope.get_waveform_preamble(scope_ch)
        record_len = scope._extract_record_length(preamble)
        # Prefer HOR:RECO? if available (sometimes preamble NR_PT is smaller)
        try:
            rec_query = scope.query("HOR:RECO?").strip()
            record_len = max(record_len, int(rec_query))
        except Exception:
            pass

        x_incr = preamble.get("XINCR", None)
        y_mult = preamble.get("YMULT", None)
        y_off = preamble.get("YOFF", None)
        y_zero = preamble.get("YZERO", 0.0)

        scope.write("DAT:STAR 1")
        scope.write(f"DAT:STOP {record_len}")

        # Read data
        data_str = scope.query("CURV?")
        data_points = []
        for value in data_str.split(','):
            try:
                data_points.append(float(value.strip()))
            except ValueError:
                continue
        raw_adc_codes = np.array(data_points, dtype=np.float64)
        
        # Scale using preamble (essential - handles probe attenuation automatically)
        y_values = scope._scale_waveform_values(raw_adc_codes, preamble)
        num_points = len(y_values)

        if num_points > 1:
            # Build time array - use preamble XINCR if available, otherwise query timebase once
            HORIZONTAL_DIVISIONS = 15.0  # TBS1000C has 15 horizontal divisions
            if x_incr is None:
                try:
                    tb_scale = float(scope.query("HOR:SCA?"))
                except Exception:
                    tb_scale = 0.2
                window = tb_scale * HORIZONTAL_DIVISIONS
                time_values = np.linspace(0.0, window, num_points)
            else:
                time_values = scope._build_time_array(num_points, preamble, fallback_scale=None)
                window = time_values[-1] - time_values[0] if len(time_values) > 1 else 0
                if window <= 0:
                    # Safety fallback - query timebase only if needed
                    try:
                        tb_scale = float(scope.query("HOR:SCA?"))
                    except Exception:
                        tb_scale = 0.2
                    window = tb_scale * HORIZONTAL_DIVISIONS
                    time_values = np.linspace(0.0, window, num_points)
            
            return time_values, y_values
        else:
            return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

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
            compliance = float(params.get('current_compliance', 0.001))  # Default if not provided
            bias_voltage = float(params.get('bias_voltage', 0.2))
            pre_bias_time = float(params.get('pre_bias_time', 0.1))
            post_bias_time = float(params.get('post_bias_time', 1.0))
            
            shunt_r = float(params.get('r_shunt', 50.0))
            # Parse scope channel - handle both 'CH1' and '1' formats
            scope_ch_raw = params.get('scope_channel', 1)
            if isinstance(scope_ch_raw, str):
                # Extract number from 'CH1', 'CH2', etc.
                scope_ch = int(''.join(filter(str.isdigit, scope_ch_raw)) or '1')
            else:
                scope_ch = int(scope_ch_raw)
            
            # Initialize vertical offset (will be set during auto-config if enabled)
            vertical_offset = 0.0
            
            # CRITICAL: Cache system name ONCE at start to avoid VISA calls during scope acquisition
            # Calling get_system_name() later opens GPIB connection which can invalidate USB scope session!
            system_name_cached = 'unknown'
            if not simulation_mode and self.smu:
                try:
                    system_name_cached = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                    debug_print(f"SMU System: {system_name_cached}")
                except Exception as e:
                    debug_print(f"Warning: Could not get SMU system name: {e}")
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
                    debug_print("  Auto-configuring oscilloscope (reset to defaults + full setup)...")
                    try:
                        scope_inst = self.scope_manager.scope
                        
                        # Step 0: RESET to factory defaults and increase timeout
                        debug_print("    Resetting scope to factory defaults...")
                        scope_inst.reset()  # Sends *RST
                        time.sleep(1.0)  # Wait for reset to complete
                        
                        # Increase VISA timeout to prevent session expiration during long pulses
                        # Include bias hold times on both sides of the pulse
                        total_measurement_time = pre_bias_time + duration + post_bias_time
                        # Set timeout to 2x the total measurement time + 30s buffer for acquisition
                        timeout_ms = int((total_measurement_time * 2.0 + 30.0) * 1000)
                        timeout_ms = max(timeout_ms, 30000)  # Minimum 30 seconds
                        if hasattr(scope_inst, 'inst') and scope_inst.inst:
                            scope_inst.inst.timeout = timeout_ms
                            debug_print(f"    VISA timeout: {timeout_ms/1000:.1f}s (prevents session expiration)")
                        
                        # Step 1: Set acquisition mode for best resolution
                        if hasattr(scope_inst, 'configure_acquisition'):
                            scope_inst.configure_acquisition(mode='SAMPLE', stop_after='SEQUENCE')
                            debug_print(f"    Acquisition mode: SAMPLE (single-shot)")
                        
                        # Step 2: Enable and configure channel
                        self.scope_manager.enable_channel(scope_ch, enable=True)
                        self.scope_manager.configure_channel(scope_ch, coupling='DC')
                        debug_print(f"    Channel CH{scope_ch}: Enabled, DC coupling")
                        
                        # Step 3: Probe attenuation: leave at scope setting (10x). Just log what scope reports.
                        # try:
                        #     probe_setting = scope_inst.query(f"CH{scope_ch}:PROBEFACTOR?").strip()
                        #     print(f"    Channel CH{scope_ch}: Probe factor reported: {probe_setting} (leaving as-is)")
                        # except Exception:
                        #     try:
                        #         probe_setting = scope_inst.query(f"CH{scope_ch}:PROBE?").strip()
                        #         print(f"    Channel CH{scope_ch}: Probe reported: {probe_setting} (leaving as-is)")
                        #     except Exception as ex2:
                        #         print(f"    ⚠️ Could not read probe attenuation: {ex2}")
                        
                        # Step 4: Apply known-good settings from scope_settings.json
                        # Force record length to 20k (scope will clamp if needed)
                        target_points = 20000
                        
                        applied_points = self.scope_manager.configure_record_length(target_points)
                        
                        # Read back actual record length (scope may limit it at slow timebases)
                        try:
                            actual_record = scope_inst.query("HOR:RECO?").strip()
                            actual_points = int(actual_record)
                            debug_print(f"    Record length: {actual_points} points (requested {target_points}, scope set {actual_points})")
                            if actual_points < target_points:
                                debug_print(f"    ⚠️ Scope limited record length to {actual_points} at this timebase")
                                debug_print(f"       To get {target_points} points, use faster timebase (<100 ms/div)")
                            applied_points = actual_points
                        except:
                            if applied_points:
                                debug_print(f"    Record length: {applied_points} points (max resolution)")
                            else:
                                debug_print(f"    Record length: {target_points} points requested")
                        
                        # Step 5: Calculate timebase to capture full waveform including bias holds
                        # Full waveform: pre_bias_time + pulse + post_bias_time
                        # Tektronix TBS1000C has 15 horizontal divisions and 10 vertical divisions
                        # Add 40% margin and divide by 15 divisions (increased from 20% for better capture)
                        HORIZONTAL_DIVISIONS = 15.0  # TBS1000C has 15 divisions horizontally
                        VERTICAL_DIVISIONS = 10.0    # TBS1000C has 10 divisions vertically
                        debug_print(f"    ========== TIMEBASE CALCULATION DEBUG ==========")
                        debug_print(f"    Pre-bias time: {pre_bias_time:.6f} s")
                        debug_print(f"    Pulse duration: {duration:.6f} s")
                        debug_print(f"    Post-bias time: {post_bias_time:.6f} s")
                        debug_print(f"    Total measurement time: {total_measurement_time:.6f} s")
                        debug_print(f"    Horizontal divisions: {HORIZONTAL_DIVISIONS:.0f} (TBS1000C)")
                        debug_print(f"    Vertical divisions: {VERTICAL_DIVISIONS:.0f} (TBS1000C)")
                        
                        timebase = (total_measurement_time * 1.4) / HORIZONTAL_DIVISIONS
                        debug_print(f"    Calculated timebase (before rounding): {timebase:.6f} s/div")
                        
                        # Round to reasonable scope values (avoid too fine steps)
                        # Scope typically supports steps like 0.1, 0.2, 0.5, 1.0, 2.0, 5.0 s/div
                        original_timebase = timebase
                        if timebase < 0.1:
                            timebase = 0.1
                        elif timebase < 0.2:
                            timebase = 0.2
                        elif timebase < 0.5:
                            timebase = 0.5
                        elif timebase < 1.0:
                            timebase = 1.0
                        elif timebase < 2.0:
                            timebase = 2.0
                        else:
                            timebase = round(timebase, 1)
                        
                        if timebase != original_timebase:
                            debug_print(f"    Rounded timebase from {original_timebase:.6f} to {timebase:.6f} s/div")
                        
                        desired_window = timebase * HORIZONTAL_DIVISIONS
                        
                        # Validate against config values (warn if they're way off)
                        t_scale_config = params.get('timebase_scale') or params.get('scope_timebase')
                        if t_scale_config:
                            config_timebase = float(t_scale_config)
                            config_window = config_timebase * HORIZONTAL_DIVISIONS
                            if abs(config_window - (timebase * HORIZONTAL_DIVISIONS)) > total_measurement_time * 0.5:
                                debug_print(f"    ⚠️ Config timebase ({config_timebase:.4f} s/div) ignored - auto-calculating instead")
                                debug_print(f"       Config would give {config_window:.4f}s window, need ~{total_measurement_time:.4f}s")
                        
                        # Apply the calculated timebase
                        debug_print(f"    Applying timebase: {timebase:.6f} s/div to scope...")
                        self.scope_manager.configure_timebase(time_per_div=timebase)
                        time_window = timebase * HORIZONTAL_DIVISIONS
                        
                        # Verify the timebase was actually set
                        try:
                            actual_tb_scale = float(scope_inst.query("HOR:SCA?"))
                            actual_window = actual_tb_scale * HORIZONTAL_DIVISIONS
                            debug_print(f"    Actual scope timebase: {actual_tb_scale:.6f} s/div (window: {actual_window:.6f} s)")
                            if abs(actual_tb_scale - timebase) > 0.01:
                                debug_print(f"    ⚠️ WARNING: Requested timebase ({timebase:.6f}) != actual ({actual_tb_scale:.6f})")
                        except Exception as e:
                            debug_print(f"    ⚠️ Could not verify timebase setting: {e}")
                        
                        # Calculate expected resolution metrics
                        points_for_calc = applied_points if applied_points else target_points
                        sample_interval = time_window / points_for_calc if points_for_calc > 0 else 0
                        sample_rate = 1.0 / sample_interval if sample_interval > 0 else 0
                        
                        debug_print(f"    ========== FINAL TIMEBASE SETTINGS ==========")
                        debug_print(f"    Timebase: {timebase:.6f} s/div ({timebase*1e3:.3f} ms/div) [AUTO-CALCULATED]")
                        debug_print(f"    Total window: {time_window:.6f} s")
                        debug_print(f"    Window breakdown:")
                        debug_print(f"      - Full waveform: {pre_bias_time:.3f}s pre-bias + {duration:.3f}s pulse + {post_bias_time:.3f}s post-bias = {total_measurement_time:.3f}s")
                        debug_print(f"      - Margin: {time_window - total_measurement_time:.3f}s ({(time_window/total_measurement_time - 1.0)*100:.1f}% extra)")
                        debug_print(f"    Expected sample interval: {sample_interval:.6e} s")
                        debug_print(f"    Expected sample rate: {sample_rate:.3f} Sa/s")
                        debug_print(f"    Target points: {points_for_calc} (scope may return less at slow timebases)")
                        debug_print(f"    ============================================")
                        
                        # Step 6: Set voltage scale to known-good value (0.2 V/div)
                        # Full vertical range = v_scale * VERTICAL_DIVISIONS (10 divisions)
                        # For 0.2 V/div: full range = 0.2 * 10 = 2.0 V
                        v_scale = 0.2
                        self.scope_manager.configure_channel(scope_ch, volts_per_div=v_scale)
                        full_vertical_range = v_scale * VERTICAL_DIVISIONS
                        debug_print(f"    Voltage scale: {v_scale:.4f} V/div [FORCED]")
                        debug_print(f"    Full vertical range: {full_vertical_range:.4f} V ({VERTICAL_DIVISIONS:.0f} divisions × {v_scale:.4f} V/div)")
                        
                        # Step 7: Position trigger to capture pre-bias and pre-pulse baseline
                        # Set trigger at ~10% from left edge (1.5 divisions for 15-division screen) to capture full pre-bias period
                        try:
                            if scope_inst and hasattr(scope_inst, 'set_timebase_position'):
                                # Trigger position: want trigger at ~1.5 divisions from left (10% of 15 divisions)
                                # Center is at 7.5 divisions from left, so 1.5 divisions from left = -6.0 divisions from center
                                # HOR:POS is time offset from center, negative = left of center
                                # This ensures we capture the full pre-bias hold period before the pulse
                                trigger_pos = (-HORIZONTAL_DIVISIONS / 2.0 + 1.5) * timebase  # 1.5 divs from left = -6.0 divs from center
                                scope_inst.set_timebase_position(trigger_pos)
                                debug_print(f"    Horizontal position: {trigger_pos:.6f}s (trigger at 1.5 divs from left = -6.0 divs from center, captures pre-bias)")
                        except Exception as ex:
                            debug_print(f"    ⚠️ Could not set horizontal position: {ex}")
                        
                        # Step 8: Configure trigger (NORMAL mode, noise-safe threshold)
                        # Calculate trigger level relative to expected signal
                        # For positive pulses: trigger on rising edge from bias to pulse
                        # Set trigger level at 25% between bias and pulse (lowered by 50% from previous 50%)
                        if pulse_voltage > 0:
                            # Trigger on rising edge from bias to pulse
                            # Set level at 25% between bias and pulse (or minimum 25mV above bias)
                            trigger_level = max(bias_voltage + 0.025, bias_voltage + (pulse_voltage - bias_voltage) * 0.25)
                        else:
                            # For negative pulses: trigger on falling edge
                            trigger_level = min(bias_voltage - 0.025, bias_voltage + (pulse_voltage - bias_voltage) * 0.25)
                        
                        # Ensure trigger level is reasonable (not too close to noise floor)
                        if abs(trigger_level) < 0.01:
                            trigger_level = 0.025 if pulse_voltage > 0 else -0.025
                        
                        # Auto-select trigger slope based on pulse polarity
                        trigger_slope_param = params.get('trigger_slope')
                        if trigger_slope_param and str(trigger_slope_param).strip():
                            trigger_slope = str(trigger_slope_param).upper()
                        else:
                            # Auto: positive pulse -> RISING, negative -> FALLING
                            trigger_slope = 'FALLING' if pulse_voltage < 0 else 'RISING'
                        
                        # Set holdoff to prevent re-triggering during measurement
                        holdoff_s = total_measurement_time * 1.5  # 50% extra margin
                        
                        # Use AUTO mode with untriggered roll (captures even if no trigger)
                        self.scope_manager.configure_trigger(
                            source=f'CH{scope_ch}', 
                            level=trigger_level,  # Trigger level based on expected signal
                            slope=trigger_slope, 
                            mode='AUTO',  # AUTO mode: triggers if signal present, otherwise rolls untriggered
                            holdoff=holdoff_s
                        )
                        debug_print(f"    Trigger: CH{scope_ch} @ {trigger_level*1e3:.1f}mV")
                        debug_print(f"    Trigger slope: {trigger_slope} [AUTO for {'+' if pulse_voltage >= 0 else '-'}{abs(pulse_voltage):.2f}V pulse]")
                        debug_print(f"    Trigger mode: AUTO (untriggered roll enabled)")
                        debug_print(f"    Trigger holdoff: {holdoff_s:.4f}s (prevents re-trigger)")
                        
                        # Set vertical offset to 0 (no offset - user requested)
                        try:
                            if scope_inst and hasattr(scope_inst, 'set_channel_offset'):
                                vertical_offset = 0.0  # No offset - set to zero
                                scope_inst.set_channel_offset(scope_ch, vertical_offset)
                                debug_print(f"    Vertical offset: {vertical_offset:.4f}V (set to zero)")
                        except Exception as ex:
                            debug_print(f"    ⚠️ Could not set vertical offset: {ex}")
                            
                        debug_print("  ✓ Scope configured for high-resolution capture")
                        
                    except Exception as e:
                        debug_print(f"  ⚠️ Warning: Scope configuration error: {e}")
                        traceback.print_exc()
                else:
                    debug_print("  Using manual oscilloscope settings (auto-configure disabled)")
                
                # Start acquisition in AUTO mode (will roll untriggered if no trigger)
                debug_print("  Starting scope acquisition in AUTO mode...")
                scope_inst = self.scope_manager.scope
                if scope_inst:
                    # Ensure acquisition is running
                    try:
                        scope_inst.write("ACQ:STATE RUN")
                        debug_print("  ✓ Scope acquisition started (AUTO mode - will roll if untriggered)")
                    except Exception as ex:
                        debug_print(f"  ⚠️ Could not start acquisition: {ex}")
                
                # No wait - disconnect immediately to avoid missing the pulse
                debug_print("  Disconnecting immediately to avoid missing pulse...")
                
                # CRITICAL: Close scope connection to prevent VISA conflicts with SMU
                # The scope will roll untriggered in AUTO mode and capture waveform on screen
                debug_print("  Closing scope connection (AUTO mode will continue rolling)...")
                if scope_inst:
                    try:
                        scope_inst.disconnect()
                        debug_print("  ✓ Scope disconnected - ready for SMU pulse")
                    except Exception as ex:
                        debug_print(f"  ⚠️ Warning: Could not disconnect scope cleanly: {ex}") 
                
                # No wait - send pulse immediately to avoid missing capture window
            
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
                     # For 2450/2400, check connection and set to bias voltage
                     if not self.smu.is_connected():
                         raise RuntimeError("SMU not connected.")
                     # Start at bias voltage for pre-bias period
                     self.smu.set_voltage(bias_voltage, Icc=compliance)
                     self.smu.enable_output(True)
            
            if self._stop_event.is_set(): 
                if not simulation_mode and self.smu:
                    if system_name_cached != 'keithley4200a':
                        self.smu.enable_output(False)
                return

            # --- 2. EXECUTION ---
            # Pre-bias time (already at bias voltage from setup)
            on_progress(f"Pre-bias ({bias_voltage}V) for {pre_bias_time}s...")
            time.sleep(pre_bias_time)
            
            if self._stop_event.is_set(): return

            on_progress("Pulsing...")
            
            # Execute pulse - System-specific
            if not simulation_mode:
                # Use cached system name to avoid VISA calls during scope acquisition
                if system_name_cached == 'keithley4200a':
                    # Use KXCI SMU_pulse_only_craig for 4200A (faster - no measurement overhead)
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
                            
                            # Build SMU_pulse_only_craig command (faster - no measurement overhead)
                            # EX a_SMU_Pulse SMU_pulse_only_craig(initialize, logMessages, widthTime, Amplitude, Irange, Icomp, biasV, biasHold, pulse_success)
                            # Parameters: initialize(0/1), logMessages(0/1), widthTime(s), Amplitude(V), Irange(A), Icomp(A), biasV(V), biasHold(s), pulse_success(output)
                            params_list = [
                                "1",  # initialize = 1 (DO initialize - required for pulse to work!)
                                "1",  # logMessages = 1 (enable debug output to see what's happening)
                                format_param(duration),  # widthTime in seconds
                                format_param(pulse_voltage),  # Amplitude in volts
                                format_param(compliance),  # Irange
                                format_param(compliance),  # Icomp
                                format_param(bias_voltage),  # biasV
                                format_param(pre_bias_time), # biasHold - pre-bias time
                                "0"  # pulse_success (output parameter, dummy value)
                            ]
                            command = f"EX a_SMU_Pulse SMU_pulse_only_craig({','.join(params_list)})"
                            
                            # Execute command
                            return_value, error = kxci._execute_ex_command(command)
                            
                            if error:
                                raise RuntimeError(f"SMU_pulse_only failed: {error}")
                            
                        finally:
                            kxci._exit_ul_mode()
                            kxci.disconnect()
                            
                    except Exception as e:
                        raise RuntimeError(f"4200A pulse execution failed: {e}")
                else:
                    # For 2450/2400, use standard set_voltage method
                    # Apply pulse voltage (bias + pulse amplitude)
                    self.smu.set_voltage(bias_voltage + pulse_voltage, Icc=compliance)
                    
                    # Wait Pulse Duration
                    # Critical timing section
                    start_time = time.perf_counter()
                    while (time.perf_counter() - start_time) < duration:
                        pass # Busy wait for precision on short pulses, or use sleep for long
                    
                    # End Pulse - return to bias voltage
                    self.smu.set_voltage(bias_voltage, Icc=compliance)
                
            # Apply post-bias voltage
            on_progress(f"Applying post-bias ({bias_voltage}V) for {post_bias_time}s...")
            if not simulation_mode:
                if system_name_cached != 'keithley4200a':
                    # Return to bias voltage after pulse
                    self.smu.set_voltage(bias_voltage, Icc=compliance)
            
            # Simple time-based wait - scope is disconnected so we can't poll it
            # The scope will roll in AUTO mode and capture waveform on screen
            time.sleep(post_bias_time)
            # No extra wait - reconnect immediately to read screen
            
            if not simulation_mode:
                # Use cached system name
                if system_name_cached != 'keithley4200a':
                    self.smu.enable_output(False)

            # --- 3. ACQUISITION ---
            on_progress("Acquiring data...")
            
            if simulation_mode:
                # Generate realistic memristor switching simulation
                total_time = pre_bias_time + duration + post_bias_time
                num_points = 5000  # Higher resolution for smooth switching
                t = np.linspace(0, total_time, num_points)
                
                # Memristor parameters
                r_initial = 10000.0  # Initial resistance: 10 kΩ (high resistance state)
                r_final = 1000.0     # Final resistance: 1 kΩ (low resistance state)
                switching_time = duration * 0.3  # Switch over 30% of pulse duration
                switching_start = pre_bias_time + duration * 0.1  # Start switching 10% into pulse
                
                # Calculate memristor resistance over time
                r_memristor_t = np.full_like(t, r_initial)
                pulse_mask = (t >= pre_bias_time) & (t <= (pre_bias_time + duration))
                
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
                pulse_start = pre_bias_time
                pulse_end = pre_bias_time + duration
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
                # Check if auto-configure was disabled (manual scope setup)
                auto_configure = params.get('auto_configure_scope', True)
                if not auto_configure:
                    # For manual setup, wait a few seconds longer to ensure waveform is fully captured
                    wait_time = 3.0  # Additional 3 seconds for manual setup
                    debug_print(f"Waiting {wait_time:.1f}s before reading waveform (manual scope setup)...")
                    time.sleep(wait_time)
                
                # Simply reuse existing connection - don't reconnect (preserves scope state/screen)
                scope = self.scope_manager.scope
                if scope is None or not hasattr(scope, 'inst') or scope.inst is None:
                    # Only reconnect if connection is missing
                    addr = params.get('scope_address')
                    if not addr:
                        raise RuntimeError("No existing scope connection and no address provided")
                    scope_type = params.get('scope_type', 'Tektronix TBS1000C')
                    if scope_type == 'Auto-Detect':
                        scope_type = 'Unknown'
                    debug_print("  Reconnecting to scope (connection missing)...")
                    if not self.scope_manager.manual_init_scope(scope_type, addr):
                        raise RuntimeError(f"Failed to reconnect to oscilloscope at {addr}")
                    scope = self.scope_manager.scope
                    if scope is None:
                        raise RuntimeError("Reconnection succeeded but scope instance is None")
                
                debug_print("Reading captured waveform from screen...")
                
                # Acquire waveform from screen (waveform should already be visible)
                try:
                    t, v_scope = self._read_screen_buffer(scope, scope_ch)
                    if len(t) > 0:
                        time_window = t[-1] - t[0] if len(t) > 1 else 0
                        debug_print(f"  Captured {len(t)} points, window: {time_window:.3f} s")
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to acquire waveform from oscilloscope.\n"
                        f"Possible causes:\n"
                        f"1. Scope not in AUTO mode or waveform not on screen\n"
                        f"2. Wrong channel selected (using CH{scope_ch})\n"
                        f"3. Waveform not visible or empty screen\n"
                        f"Original error: {e}"
                    ) from e
                
                if len(t) == 0:
                    raise RuntimeError("Failed to acquire waveform from oscilloscope.")
                
                # Apply vertical offset correction if needed (offset from auto-config)
                if abs(vertical_offset) > 1e-6:
                    v_scope = v_scope - vertical_offset
                
                # Apply light smoothing to reduce noise
                if len(v_scope) > 10:
                    window_size = 3
                    if len(v_scope) >= window_size:
                        kernel = np.ones(window_size) / window_size
                        v_scope = np.convolve(v_scope, kernel, mode='same')
                
                # Calculate Current (always using shunt method)
                # I = V_shunt / R_shunt
                # Note: If measuring across shunt to ground, V_scope = V_shunt. 
                # If high-side shunt, this is more complex (requires differential probe or math).
                # Assuming Low-Side Shunt for standard setup (Device -> Shunt -> GND).
                current = v_scope / shunt_r

            # --- 4. FINISH ---
            # Detect actual pulse start in scope data by finding transition from bias to pulse
            pulse_start_time = pre_bias_time  # Default fallback
            if len(v_scope) > 10 and len(t) == len(v_scope):
                # Better pulse detection: find transition from bias voltage to pulse voltage
                # First, estimate baseline (bias voltage) from early samples
                baseline_samples = min(100, len(v_scope) // 10)
                baseline_voltage = np.median(v_scope[:baseline_samples]) if baseline_samples > 0 else 0.0
                
                # Expected pulse voltage (bias + pulse amplitude)
                expected_pulse_level = baseline_voltage + pulse_voltage if pulse_voltage > 0 else baseline_voltage + pulse_voltage
                
                # Find where signal transitions from baseline to pulse level
                # Look for significant change (at least 50% of expected pulse amplitude)
                transition_threshold = baseline_voltage + (pulse_voltage * 0.5) if pulse_voltage > 0 else baseline_voltage + (pulse_voltage * 0.5)
                
                # For positive pulses, find first significant rise above baseline
                if pulse_voltage > 0:
                    # Find where signal rises significantly above baseline
                    rising_edge = np.where(v_scope > transition_threshold)[0]
                    # Also check for rapid change (derivative) to catch fast transitions
                    if len(rising_edge) == 0:
                        dv = np.diff(v_scope)
                        # Find where derivative exceeds threshold (rapid rise)
                        rapid_rise = np.where(dv > abs(pulse_voltage) * 0.1)[0]
                        if len(rapid_rise) > 0:
                            rising_edge = rapid_rise
                else:
                    # For negative pulses, find first significant fall below baseline
                    falling_edge = np.where(v_scope < transition_threshold)[0]
                    if len(falling_edge) == 0:
                        dv = np.diff(v_scope)
                        rapid_fall = np.where(dv < pulse_voltage * 0.1)[0]
                        if len(rapid_fall) > 0:
                            falling_edge = rapid_fall
                    rising_edge = falling_edge
                
                if len(rising_edge) > 0:
                    pulse_start_idx = rising_edge[0]
                    pulse_start_time = t[pulse_start_idx]
                    debug_print(f"  Detected pulse start at t={pulse_start_time:.6f}s (index {pulse_start_idx})")
                    debug_print(f"    Baseline (bias): {baseline_voltage:.4f}V, Transition threshold: {transition_threshold:.4f}V")
                else:
                    debug_print(f"  Could not detect pulse start, using pre_bias_time={pre_bias_time:.4f}s")
                    debug_print(f"    Baseline (bias): {baseline_voltage:.4f}V, Expected pulse level: {expected_pulse_level:.4f}V")
            
            metadata = {
                'timestamp': time.time(),
                'params': params,
                'shunt_resistance': shunt_r,
                'pulse_voltage': pulse_voltage,
                'bias_voltage': bias_voltage,
                'pre_bias_time': pre_bias_time,
                'post_bias_time': post_bias_time,
                'pulse_start_time': pulse_start_time,  # Detected or fallback to pre_bias_time
                'pulse_duration': duration,  # Pulse duration for V_SMU calculation
                'vertical_offset': vertical_offset,  # Vertical offset applied (for re-zeroing)
                'v_raw': v_scope.copy()  # Store raw for rescaling
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

    def _pulse_only_worker(self, params: Dict[str, Any],
                           on_progress: Callable, on_error: Callable, on_finished: Callable):
        """Send SMU pulse only, no scope interaction."""
        try:
            simulation_mode = params.get('simulation_mode', False)
            
            pulse_voltage = float(params.get('pulse_voltage', 1.0))
            duration = float(params.get('pulse_duration', 0.001))
            compliance = float(params.get('current_compliance', 0.001))  # Default if not provided
            bias_voltage = float(params.get('bias_voltage', 0.2))
            pre_bias_time = float(params.get('pre_bias_time', 0.1))
            post_bias_time = float(params.get('post_bias_time', 1.0))
            
            # Get system name
            system_name_cached = 'unknown'
            if not simulation_mode and self.smu:
                try:
                    system_name_cached = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                    debug_print(f"SMU System: {system_name_cached}")
                except Exception as e:
                    debug_print(f"Warning: Could not get SMU system name: {e}")
                    system_name_cached = 'unknown'
            
            if self._stop_event.is_set():
                return
            
            # Configure SMU
            if not simulation_mode:
                if self.smu is None:
                    raise RuntimeError("SMU not connected. Please click 'Connect SMU' button first.")
                
                if system_name_cached == 'keithley4200a':
                    pass  # No pre-config needed for 4200A
                else:
                    if not self.smu.is_connected():
                        raise RuntimeError("SMU not connected.")
                    # Start at bias voltage for pre-bias period
                    self.smu.set_voltage(bias_voltage, Icc=compliance)
                    self.smu.enable_output(True)
            
            if self._stop_event.is_set():
                if not simulation_mode and self.smu:
                    if system_name_cached != 'keithley4200a':
                        self.smu.enable_output(False)
                return
            
            # Pre-bias time
            on_progress(f"Pre-bias ({bias_voltage}V) for {pre_bias_time}s...")
            time.sleep(pre_bias_time)
            
            if self._stop_event.is_set():
                return
            
            # Execute pulse
            on_progress("Pulsing...")
            
            if not simulation_mode:
                if system_name_cached == 'keithley4200a':
                    # Use KXCI SMU_pulse_only_craig for 4200A (faster - no measurement overhead)
                    try:
                        from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import KXCIClient, format_param
                        
                        gpib_address = getattr(self.smu, '_address', 'GPIB0::17::INSTR')
                        kxci = KXCIClient(gpib_address=gpib_address, timeout=30.0)
                        if not kxci.connect():
                            raise RuntimeError("Failed to connect to 4200A for pulse")
                        
                        try:
                            kxci._enter_ul_mode()
                            
                            # Build SMU_pulse_only_craig command (faster - no measurement overhead)
                            # EX a_SMU_Pulse SMU_pulse_only_craig(initialize, logMessages, widthTime, Amplitude, Irange, Icomp, biasV, biasHold, pulse_success)
                            params_list = [
                                "1",  # initialize
                                "1",  # logMessages
                                format_param(duration),  # widthTime in seconds
                                format_param(pulse_voltage),  # Amplitude in volts
                                format_param(compliance),  # Irange
                                format_param(compliance),  # Icomp
                                format_param(bias_voltage),  # biasV
                                format_param(pre_bias_time), # biasHold - pre-bias time
                                "0"  # pulse_success (output parameter, dummy value)
                            ]
                            command = f"EX a_SMU_Pulse SMU_pulse_only_craig({','.join(params_list)})"
                            
                            return_value, error = kxci._execute_ex_command(command)
                            if error:
                                raise RuntimeError(f"SMU_pulse_only failed: {error}")
                            
                        finally:
                            kxci._exit_ul_mode()
                            kxci.disconnect()
                            
                    except Exception as e:
                        raise RuntimeError(f"4200A pulse execution failed: {e}")
                else:
                    # For 2450/2400
                    # Apply pulse voltage (bias + pulse amplitude)
                    self.smu.set_voltage(bias_voltage + pulse_voltage, Icc=compliance)
                    start_time = time.perf_counter()
                    while (time.perf_counter() - start_time) < duration:
                        pass
                    # Return to bias voltage
                    self.smu.set_voltage(bias_voltage, Icc=compliance)
            
            # Post-bias time (already at bias voltage)
            on_progress(f"Post-bias ({bias_voltage}V) for {post_bias_time}s...")
            time.sleep(post_bias_time)
            
            if not simulation_mode:
                if system_name_cached != 'keithley4200a':
                    self.smu.enable_output(False)
            
            on_progress("Pulse complete.")
            
        except Exception as e:
            traceback.print_exc()
            on_error(str(e))
        finally:
            if not simulation_mode and self.smu:
                try:
                    smu_sys_name = system_name_cached if 'system_name_cached' in locals() else 'unknown'
                    if smu_sys_name == 'unknown':
                        smu_sys_name = getattr(self.smu, 'get_system_name', lambda: 'unknown')()
                    if smu_sys_name != 'keithley4200a':
                        self.smu.enable_output(False)
                except:
                    pass
            self.is_running = False
            on_finished()

    def _scope_only_worker(self, params: Dict[str, Any],
                           on_progress: Callable, on_data: Callable,
                           on_error: Callable, on_finished: Callable):
        """Grab existing scope screen data without pulsing or configuring.
        Simplified version following grab_screen_waveform.py pattern."""
        try:
            simulation_mode = params.get('simulation_mode', False)
            shunt_r = float(params.get('r_shunt', 50.0))
            scope_ch_raw = params.get('scope_channel', 1)
            scope_ch = int(''.join(filter(str.isdigit, scope_ch_raw)) or '1') if isinstance(scope_ch_raw, str) else int(scope_ch_raw)

            if simulation_mode:
                raise RuntimeError("Scope-only grab not available in simulation mode")

            if not self.scope_manager:
                raise RuntimeError("Oscilloscope Manager not available (import failed).")

            # Simple connection - just connect and use it
            addr = params.get('scope_address')
            if not addr or not addr.strip():
                raise RuntimeError("No oscilloscope address provided. Please set scope address.")
            
            scope_type = params.get('scope_type', 'Tektronix TBS1000C')
            if scope_type == 'Auto-Detect':
                scope_type = 'Unknown'
            
            on_progress("Connecting to oscilloscope...")
            if not self.scope_manager.manual_init_scope(scope_type, addr):
                raise RuntimeError(f"Could not connect to oscilloscope at {addr}.")

            scope = self.scope_manager.scope
            if not scope or not hasattr(scope, 'inst') or scope.inst is None:
                raise RuntimeError("Scope not properly initialized.")

            on_progress("Reading scope screen...")
            t, v_scope = self._read_screen_buffer(scope, scope_ch)
            if len(t) == 0:
                raise RuntimeError("No data returned from scope.")

            debug_print(f"  Scope samples (first 5): {v_scope[:5].tolist()}")
            
            # Apply light smoothing to reduce noise
            if len(v_scope) > 10:
                window_size = 3
                if len(v_scope) >= window_size:
                    kernel = np.ones(window_size) / window_size
                    v_scope = np.convolve(v_scope, kernel, mode='same')
            
            debug_print(f"  Smoothed samples (first 5): {v_scope[:5].tolist()}")

            current = v_scope / shunt_r

            pulse_start_time = 0.0
            if len(v_scope) > 10 and len(t) == len(v_scope):
                v_max = np.max(np.abs(v_scope))
                threshold = max(v_max * 0.1, 0.01)
                rising_edge = np.where(v_scope > threshold)[0]
                if len(rising_edge) > 0:
                    pulse_start_time = t[rising_edge[0]]
                    debug_print(f"  Detected pulse start at t={pulse_start_time:.6f}s (index {rising_edge[0]})")

            metadata = {
                'timestamp': time.time(),
                'params': params,
                'shunt_resistance': shunt_r,
                'pulse_voltage': params.get('pulse_voltage'),
                'bias_voltage': params.get('bias_voltage'),
                'bias_hold': params.get('bias_hold'),
                'pulse_start_time': pulse_start_time,
                'pulse_duration': params.get('pulse_duration'),
                'scope_only': True,
                'v_raw': v_scope.copy()  # Store raw for rescaling
            }

            on_data(t, v_scope, current, metadata)
            on_progress("Done.")

        except Exception as e:
            traceback.print_exc()
            on_error(str(e))
        finally:
            self.is_running = False
            on_finished()
