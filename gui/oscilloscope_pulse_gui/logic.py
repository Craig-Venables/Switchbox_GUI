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

def timing_log(message: str):
    """Log message with timestamp for timing/alignment debugging."""
    if DEBUG_ENABLED:
        timestamp = time.perf_counter()
        print(f"[{timestamp:.6f}s] ⏱️ {message}")
# =======================================================

# Constants
HORIZONTAL_DIVISIONS = 15.0  # TBS1000C has 15 horizontal divisions
VERTICAL_DIVISIONS = 10.0    # TBS1000C has 10 vertical divisions

# Wait time after SMU command completes before reading scope (hardcoded)
SMU_POST_COMMAND_WAIT_S = 3  # Wait 0.5s after SMU command completes before reading scope

# Wait time for scope to trigger before sending pulse (to ensure scope is ready)
# In AUTO mode, scope will trigger periodically. This ensures it has triggered at least once
# before we send the pulse, so the next trigger will capture our pulse.
SCOPE_PRE_TRIGGER_WAIT_S = 0  # Wait 2.0s for scope to trigger before sending pulse

# Try to import equipment managers, but handle failure for simulation/offline dev
try:
    from Equipment.managers.oscilloscope import OscilloscopeManager
except ImportError:
    OscilloscopeManager = None

# Try to import SystemWrapper for auto-connection
try:
    from Pulse_Testing.system_wrapper import SystemWrapper, detect_system_from_address
except ImportError:
    SystemWrapper = None
    detect_system_from_address = None

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
        timing_log(f"Scope: Setting data source to CH{scope_ch} (DAT:SOU CH{scope_ch})")
        scope.write(f"DAT:SOU CH{scope_ch}")
        timing_log("Scope: Setting data encoding to ASCII (DAT:ENC ASCII)")
        scope.write("DAT:ENC ASCII")
        timing_log("Scope: Setting data width to 1 byte (DAT:WID 1)")
        scope.write("DAT:WID 1")

        # Get preamble (contains essential scaling info)
        timing_log("Scope: Querying waveform preamble (WFMO?)")
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

        timing_log(f"Scope: Setting data range (DAT:STAR 1, DAT:STOP {record_len})")
        scope.write("DAT:STAR 1")
        scope.write(f"DAT:STOP {record_len}")

        # Read data
        timing_log(f"Scope: Querying waveform data (CURV?) - expecting {record_len} points")
        data_str = scope.query("CURV?")
        timing_log(f"Scope: Received {len(data_str)} characters of waveform data")
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

    # ==================== Helper Functions ====================

    def _parse_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate measurement parameters."""
        scope_ch_raw = params.get('scope_channel', 1)
        if isinstance(scope_ch_raw, str):
            scope_ch = int(''.join(filter(str.isdigit, scope_ch_raw)) or '1')
        else:
            scope_ch = int(scope_ch_raw)
        
        return {
            'pulse_voltage': float(params.get('pulse_voltage', 1.0)),
            'duration': float(params.get('pulse_duration', 0.001)),
            'compliance': float(params.get('current_compliance', 0.001)),
            'bias_voltage': float(params.get('bias_voltage', 0.2)),
            'pre_bias_time': float(params.get('pre_bias_time', 0.1)),
            'post_bias_time': float(params.get('post_bias_time', 1.0)),
            'shunt_r': float(params.get('r_shunt', 50.0)),
            'scope_ch': scope_ch,
            'simulation_mode': params.get('simulation_mode', False),
        }

    def _get_smu_system_name(self) -> str:
        """Get SMU system name (cached to avoid repeated VISA calls)."""
        if not self.smu:
            return 'unknown'
        try:
            return getattr(self.smu, 'get_system_name', lambda: 'unknown')()
        except Exception as e:
            debug_print(f"Warning: Could not get SMU system name: {e}")
            return 'unknown'

    def _ensure_scope_connected(self, params: Dict[str, Any]) -> None:
        """Ensure oscilloscope is connected."""
        if not self.scope_manager:
            raise RuntimeError("Oscilloscope Manager not available (import failed).")
        
        if self.scope_manager.is_connected():
            return
        
        addr = params.get('scope_address')
        if addr and addr.strip():
            scope_type = params.get('scope_type', 'Tektronix TBS1000C')
            if scope_type == 'Auto-Detect':
                scope_type = 'Unknown'
            if not self.scope_manager.manual_init_scope(scope_type, addr):
                raise RuntimeError(f"Could not connect to oscilloscope at {addr}.")
        else:
            if not self.scope_manager.auto_detect_scope():
                raise RuntimeError("No oscilloscope detected. Please provide an address.")

    # ==================== Scope Configuration ====================

    def _configure_scope_auto(self, params: Dict[str, Any], meas_params: Dict[str, Any]) -> float:
        """Auto-configure oscilloscope for pulse measurement. Returns vertical_offset."""
        timing_log("=== SCOPE CONFIGURATION START ===")
        
        scope_inst = self.scope_manager.scope
        scope_ch = meas_params['scope_ch']
        
        # Reset to defaults
        timing_log("Scope: Sending *RST (reset to factory defaults)")
        scope_inst.reset()
        time.sleep(1.0)
        
        # Set timeout
        total_time = meas_params['pre_bias_time'] + meas_params['duration'] + meas_params['post_bias_time']
        timeout_ms = max(int((total_time * 2.0 + 30.0) * 1000), 30000)
        if hasattr(scope_inst, 'inst') and scope_inst.inst:
            scope_inst.inst.timeout = timeout_ms
        timing_log(f"Scope: Set VISA timeout to {timeout_ms/1000:.1f}s")
        
        # Acquisition mode
        if hasattr(scope_inst, 'configure_acquisition'):
            scope_inst.configure_acquisition(mode='SAMPLE', stop_after='SEQUENCE')
        timing_log("Scope: Set acquisition mode to SAMPLE")
        
        # Channel setup
        self.scope_manager.enable_channel(scope_ch, enable=True)
        self.scope_manager.configure_channel(scope_ch, coupling='DC')
        timing_log(f"Scope: Enabled CH{scope_ch} with DC coupling")
        
        # Record length
        target_points = 20000
        self.scope_manager.configure_record_length(target_points)
        timing_log(f"Scope: Set record length to {target_points} points")
        
        # Calculate and set timebase
        timebase = self._calculate_timebase(total_time)
        timing_log(f"Scope: Setting timebase to {timebase:.6f} s/div")
        self.scope_manager.configure_timebase(time_per_div=timebase)
        
        # Voltage scale
        v_scale = 0.2
        self.scope_manager.configure_channel(scope_ch, volts_per_div=v_scale)
        timing_log(f"Scope: Set voltage scale to {v_scale} V/div")
        
        # Trigger position
        trigger_pos = (-HORIZONTAL_DIVISIONS / 2.0 + 1.5) * timebase
        try:
            if hasattr(scope_inst, 'set_timebase_position'):
                scope_inst.set_timebase_position(trigger_pos)
                timing_log(f"Scope: Set horizontal position to {trigger_pos:.6f}s")
        except Exception as ex:
            debug_print(f"  ⚠️ Could not set horizontal position: {ex}")
        
        # Trigger configuration
        trigger_level, trigger_slope = self._calculate_trigger_settings(meas_params, params)
        holdoff_s = total_time * 1.5
        self.scope_manager.configure_trigger(
            source=f'CH{scope_ch}',
            level=trigger_level,
            slope=trigger_slope,
            mode='AUTO',
            holdoff=holdoff_s
        )
        timing_log(f"Scope: Set trigger CH{scope_ch} @ {trigger_level*1e3:.1f}mV, {trigger_slope} edge, AUTO mode")
        
        # Vertical offset
        vertical_offset = 0.0
        try:
            if hasattr(scope_inst, 'set_channel_offset'):
                scope_inst.set_channel_offset(scope_ch, vertical_offset)
        except Exception:
            pass
        
        timing_log("=== SCOPE CONFIGURATION COMPLETE ===")
        return vertical_offset

    def _calculate_timebase(self, total_time: float) -> float:
        """Calculate optimal timebase for measurement window.
        Extended by 1.2x (from 1.4x to 1.68x) to ensure full waveform capture."""
        timebase = (total_time * 1.68) / HORIZONTAL_DIVISIONS  # 1.4 * 1.2 = 1.68
        
        # Round to reasonable scope values
        if timebase < 0.1:
            return 0.1
        elif timebase < 0.2:
            return 0.2
        elif timebase < 0.5:
            return 0.5
        elif timebase < 1.0:
            return 1.0
        elif timebase < 2.0:
            return 2.0
        else:
            return round(timebase, 1)

    def _calculate_trigger_settings(self, meas_params: Dict[str, Any], params: Dict[str, Any]) -> Tuple[float, str]:
        """Calculate trigger level and slope from measurement parameters."""
        pulse_voltage = meas_params['pulse_voltage']
        bias_voltage = meas_params['bias_voltage']
        
        if pulse_voltage > 0:
            trigger_level = max(bias_voltage + 0.025, bias_voltage + (pulse_voltage - bias_voltage) * 0.25)
            trigger_slope = 'RISING'
        else:
            trigger_level = min(bias_voltage - 0.025, bias_voltage + (pulse_voltage - bias_voltage) * 0.25)
            trigger_slope = 'FALLING'
        
        # Ensure reasonable trigger level
        if abs(trigger_level) < 0.01:
            trigger_level = 0.025 if pulse_voltage > 0 else -0.025
        
        # Override with user setting if provided
        trigger_slope_param = params.get('trigger_slope')
        if trigger_slope_param and str(trigger_slope_param).strip():
            trigger_slope = str(trigger_slope_param).upper()
        
        return trigger_level, trigger_slope

    def _start_scope_acquisition(self) -> None:
        """Start oscilloscope acquisition in AUTO mode."""
        timing_log("Scope: Sending ACQ:STATE RUN (start acquisition)")
        scope_inst = self.scope_manager.scope
        if scope_inst:
            try:
                scope_inst.write("ACQ:STATE RUN")
                timing_log("Scope: Acquisition started (AUTO mode - will roll if untriggered)")
            except Exception as ex:
                debug_print(f"  ⚠️ Could not start acquisition: {ex}")

    def _disconnect_scope(self) -> None:
        """Disconnect scope to prevent VISA conflicts during SMU pulse."""
        timing_log("Scope: Disconnecting (AUTO mode will continue rolling)")
        scope_inst = self.scope_manager.scope
        if scope_inst:
            try:
                scope_inst.disconnect()
                timing_log("Scope: Disconnected - ready for SMU pulse")
            except Exception as ex:
                debug_print(f"  ⚠️ Warning: Could not disconnect scope cleanly: {ex}")

    # ==================== SMU Pulse Execution ====================

    def _auto_connect_smu(self, params: Dict[str, Any]) -> None:
        """Attempt to automatically connect SMU using params."""
        if SystemWrapper is None:
            timing_log("SMU: SystemWrapper not available - cannot auto-connect")
            return
        
        try:
            address = params.get('smu_address')
            if not address:
                timing_log("SMU: No address in params - cannot auto-connect")
                return
            
            # Determine system type
            system_type = params.get('system')
            if not system_type and detect_system_from_address:
                system_type = detect_system_from_address(address)
            
            if not system_type:
                timing_log("SMU: Cannot determine system type - cannot auto-connect")
                return
            
            timing_log(f"SMU: Auto-connecting to {address} (system: {system_type})")
            system_wrapper = SystemWrapper()
            connected_system = system_wrapper.connect(address=address, system_name=system_type)
            self.smu = system_wrapper.current_system
            timing_log(f"SMU: Auto-connected successfully ({connected_system})")
        except Exception as ex:
            timing_log(f"SMU: Auto-connection failed: {ex}")
            self.smu = None
    
    def _configure_smu_pre_pulse(self, meas_params: Dict[str, Any], system_name: str) -> None:
        """Configure SMU before pulse execution."""
        if system_name == 'keithley4200a':
            timing_log("SMU: 4200A - no pre-configuration needed")
            return
        
        timing_log(f"SMU: Setting initial bias voltage {meas_params['bias_voltage']:.3f}V")
        self.smu.set_voltage(meas_params['bias_voltage'], Icc=meas_params['compliance'])
        self.smu.enable_output(True)
        timing_log("SMU: Output enabled")

    def _execute_smu_pulse_4200a(self, meas_params: Dict[str, Any]) -> None:
        """Execute pulse using Keithley 4200A C function."""
        timing_log("=== SMU PULSE EXECUTION START (4200A) ===")
        timing_log(f"SMU: Connecting to 4200A for pulse execution")
        
        from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import KXCIClient, format_param
        
        gpib_address = getattr(self.smu, '_address', 'GPIB0::17::INSTR')
        kxci = KXCIClient(gpib_address=gpib_address, timeout=30.0)
        
        if not kxci.connect():
            raise RuntimeError("Failed to connect to 4200A for pulse")
        
        try:
            timing_log("SMU: Entering UL mode")
            kxci._enter_ul_mode()
            
            # Build command
            # NOTE: The C function SMU_pulse_only_craig uses a single biasHold parameter
            # for BOTH pre-bias and post-bias hold times. We use pre_bias_time here.
            # The post_bias_time is handled separately via hardcoded wait after command completes.
            params_list = [
                "1",  # initialize
                "1",  # logMessages
                format_param(meas_params['duration']),
                format_param(meas_params['pulse_voltage']),
                format_param(meas_params['compliance']),
                format_param(meas_params['compliance']),
                format_param(meas_params['bias_voltage']),
                format_param(meas_params['pre_bias_time']),  # biasHold: used for both pre and post in C function
                "0"  # pulse_success (output)
            ]
            command = f"EX a_SMU_Pulse SMU_pulse_only_craig({','.join(params_list)})"
            
            timing_log(f"SMU: Executing C function SMU_pulse_only_craig")
            timing_log(f"SMU: Parameters - duration={meas_params['duration']:.6f}s, "
                      f"pulse_voltage={meas_params['pulse_voltage']:.3f}V, "
                      f"bias_voltage={meas_params['bias_voltage']:.3f}V, "
                      f"biasHold={meas_params['pre_bias_time']:.6f}s (C function uses this for both pre and post bias)")
            timing_log(f"SMU: Command: {command}")
            
            return_value, error = kxci._execute_ex_command(command)
            
            if error:
                raise RuntimeError(f"SMU_pulse_only failed: {error}")
            
            timing_log("SMU: C function execution complete")
            
        finally:
            timing_log("SMU: Exiting UL mode and disconnecting")
            kxci._exit_ul_mode()
            kxci.disconnect()
        
        timing_log("=== SMU PULSE EXECUTION END (4200A) ===")

    def _execute_smu_pulse_standard(self, meas_params: Dict[str, Any]) -> None:
        """Execute pulse using standard SMU commands (2450/2400)."""
        timing_log("=== SMU PULSE EXECUTION START (Standard) ===")
        
        # Apply pulse voltage
        pulse_v = meas_params['bias_voltage'] + meas_params['pulse_voltage']
        timing_log(f"SMU: Setting pulse voltage {pulse_v:.3f}V (bias + pulse)")
        self.smu.set_voltage(pulse_v, Icc=meas_params['compliance'])
        
        # Wait for pulse duration
        timing_log(f"SMU: Holding pulse for {meas_params['duration']:.6f}s")
        start_time = time.perf_counter()
        while (time.perf_counter() - start_time) < meas_params['duration']:
            pass  # Busy wait for precision
        
        # Return to bias voltage
        timing_log(f"SMU: Returning to bias voltage {meas_params['bias_voltage']:.3f}V")
        self.smu.set_voltage(meas_params['bias_voltage'], Icc=meas_params['compliance'])
        
        timing_log("=== SMU PULSE EXECUTION END (Standard) ===")

    def _execute_full_pulse_sequence(self, meas_params: Dict[str, Any], 
                                     system_name: str, on_progress: Callable) -> None:
        """
        Execute full pulse sequence.
        
        For 4200A:
        - The C function SMU_pulse_only_craig uses pre_bias_time as the biasHold parameter.
        - The biasHold parameter controls BOTH pre-bias and post-bias hold times in the C function.
        - After the C function completes, we wait a hardcoded time (SMU_POST_COMMAND_WAIT_S) before reading scope.
        
        For standard SMU (2450/2400):
        - Pre-bias, pulse, and post-bias are handled manually in Python.
        """
        # Pulse execution
        timing_log(f"=== PULSE EXECUTION START ===")
        on_progress("Pulsing...")
        
        if system_name == 'keithley4200a':
            # C function handles pre-bias, pulse, and post-bias internally
            # biasHold parameter controls both pre and post bias hold times
            self._execute_smu_pulse_4200a(meas_params)
        else:
            # For standard SMU, handle pre-bias, pulse, post-bias manually
            # Pre-bias period
            timing_log(f"=== PRE-BIAS PERIOD START ({meas_params['pre_bias_time']:.6f}s) ===")
            on_progress(f"Pre-bias ({meas_params['bias_voltage']:.3f}V) for {meas_params['pre_bias_time']:.3f}s...")
            time.sleep(meas_params['pre_bias_time'])
            timing_log("=== PRE-BIAS PERIOD END ===")
            
            if self._stop_event.is_set():
                return
            
            self._execute_smu_pulse_standard(meas_params)
            
            # Post-bias period
            timing_log(f"=== POST-BIAS PERIOD START ({meas_params['post_bias_time']:.6f}s) ===")
            on_progress(f"Post-bias ({meas_params['bias_voltage']:.3f}V) for {meas_params['post_bias_time']:.3f}s...")
            self.smu.set_voltage(meas_params['bias_voltage'], Icc=meas_params['compliance'])
            time.sleep(meas_params['post_bias_time'])
            timing_log("=== POST-BIAS PERIOD END ===")
        
        timing_log("=== PULSE EXECUTION END ===")
        
        # Hardcoded wait time after SMU command completes before reading scope
        timing_log(f"=== WAITING {SMU_POST_COMMAND_WAIT_S:.3f}s BEFORE READING SCOPE ===")
        time.sleep(SMU_POST_COMMAND_WAIT_S)
        timing_log("=== WAIT COMPLETE ===")

    # ==================== Waveform Processing ====================

    def _process_waveform_data(self, t: np.ndarray, v_scope: np.ndarray, 
                               vertical_offset: float, meas_params: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, float]:
        """Process acquired waveform data: apply offset, smooth, calculate current, detect pulse."""
        # Apply vertical offset correction
        if abs(vertical_offset) > 1e-6:
            v_scope = v_scope - vertical_offset
        
        # Apply light smoothing
        if len(v_scope) > 10:
            window_size = 3
            if len(v_scope) >= window_size:
                kernel = np.ones(window_size) / window_size
                v_scope = np.convolve(v_scope, kernel, mode='same')
        
        # Calculate current
        current = v_scope / meas_params['shunt_r']
        
        # Detect pulse start
        pulse_start_time = self._detect_pulse_start(t, v_scope, meas_params)
        
        return v_scope, current, pulse_start_time

    def _detect_pulse_start(self, t: np.ndarray, v_scope: np.ndarray, 
                           meas_params: Dict[str, Any]) -> float:
        """Detect pulse start time in waveform data."""
        if len(v_scope) < 10 or len(t) != len(v_scope):
            return meas_params['pre_bias_time']
        
        # Estimate baseline
        baseline_samples = min(100, len(v_scope) // 10)
        baseline_voltage = np.median(v_scope[:baseline_samples]) if baseline_samples > 0 else 0.0
        
        # Calculate transition threshold
        pulse_voltage = meas_params['pulse_voltage']
        transition_threshold = baseline_voltage + (pulse_voltage * 0.5) if pulse_voltage > 0 else baseline_voltage + (pulse_voltage * 0.5)
        
        # Find transition
        if pulse_voltage > 0:
            rising_edge = np.where(v_scope > transition_threshold)[0]
            if len(rising_edge) == 0:
                dv = np.diff(v_scope)
                rapid_rise = np.where(dv > abs(pulse_voltage) * 0.1)[0]
                if len(rapid_rise) > 0:
                    rising_edge = rapid_rise
        else:
            falling_edge = np.where(v_scope < transition_threshold)[0]
            if len(falling_edge) == 0:
                dv = np.diff(v_scope)
                rapid_fall = np.where(dv < pulse_voltage * 0.1)[0]
                if len(rapid_fall) > 0:
                    falling_edge = rapid_fall
            rising_edge = falling_edge
        
        if len(rising_edge) > 0:
            pulse_start_time = t[rising_edge[0]]
            debug_print(f"  Detected pulse start at t={pulse_start_time:.6f}s")
            return pulse_start_time
        
        debug_print(f"  Could not detect pulse start, using pre_bias_time={meas_params['pre_bias_time']:.4f}s")
        return meas_params['pre_bias_time']

    def _acquire_waveform(self, params: Dict[str, Any], meas_params: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
        """Acquire waveform from oscilloscope without resetting it."""
        timing_log("=== WAVEFORM ACQUISITION START ===")
        
        # Try to reuse existing connection (should still be connected from setup)
        scope = self.scope_manager.scope
        
        # Check if existing connection is valid
        if scope is None or not hasattr(scope, 'inst') or scope.inst is None:
            # Only reconnect if absolutely necessary
            addr = params.get('scope_address')
            if not addr:
                raise RuntimeError("No existing scope connection and no address provided")
            
            scope_type = params.get('scope_type', 'Tektronix TBS1000C')
            if scope_type == 'Auto-Detect':
                scope_type = 'Unknown'
            
            timing_log(f"Scope: Reconnecting to {addr} (connection was lost)")
            if not self.scope_manager.manual_init_scope(scope_type, addr):
                raise RuntimeError(f"Failed to reconnect to oscilloscope at {addr}")
            scope = self.scope_manager.scope
        else:
            # Test if connection is still valid without resetting
            try:
                scope.inst.query("*IDN?", timeout=2000)  # Quick IDN query to test connection
                timing_log("Scope: Connection is valid - reusing it (no reset, no reconnect)")
            except Exception as ex:
                # Connection lost, need to reconnect
                timing_log(f"Scope: Connection lost ({ex}), will reconnect")
                addr = params.get('scope_address')
                if not addr:
                    raise RuntimeError("Scope connection lost and no address provided")
                
                scope_type = params.get('scope_type', 'Tektronix TBS1000C')
                if scope_type == 'Auto-Detect':
                    scope_type = 'Unknown'
                
                timing_log(f"Scope: Reconnecting to {addr}")
                if not self.scope_manager.manual_init_scope(scope_type, addr):
                    raise RuntimeError(f"Failed to reconnect to oscilloscope at {addr}")
                scope = self.scope_manager.scope
        
        # Read waveform (this should NOT reset the scope - just read what's on screen)
        timing_log("Scope: Reading waveform from screen")
        t, v_scope = self._read_screen_buffer(scope, meas_params['scope_ch'])
        
        if len(t) == 0:
            raise RuntimeError("Failed to acquire waveform from oscilloscope.")
        
        timing_log("=== WAVEFORM ACQUISITION END ===")
        return t, v_scope

    def _generate_simulation_data(self, meas_params: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
        """Generate simulated memristor switching data."""
        total_time = meas_params['pre_bias_time'] + meas_params['duration'] + meas_params['post_bias_time']
        num_points = 5000
        t = np.linspace(0, total_time, num_points)
        
        # Memristor parameters
        r_initial = 10000.0
        r_final = 1000.0
        switching_time = meas_params['duration'] * 0.3
        switching_start = meas_params['pre_bias_time'] + meas_params['duration'] * 0.1
        
        # Calculate resistance over time
        r_memristor_t = np.full_like(t, r_initial)
        pulse_mask = (t >= meas_params['pre_bias_time']) & (t <= (meas_params['pre_bias_time'] + meas_params['duration']))
        
        for i, time_val in enumerate(t):
            if pulse_mask[i]:
                if switching_start <= time_val <= (switching_start + switching_time):
                    progress = (time_val - switching_start) / switching_time
                    r_memristor_t[i] = r_initial * np.exp(-progress * np.log(r_initial / r_final))
                elif time_val > (switching_start + switching_time):
                    r_memristor_t[i] = r_final
        
        # Calculate circuit behavior
        r_total = r_memristor_t + meas_params['shunt_r']
        current = np.zeros_like(t)
        current[pulse_mask] = meas_params['pulse_voltage'] / r_total[pulse_mask]
        v_scope = current * meas_params['shunt_r']
        
        # Add noise
        noise_level = np.max(v_scope) * 0.001
        noise = np.random.normal(0, noise_level, len(t))
        v_scope += noise
        
        return t, v_scope

    # ==================== Main Worker Functions ====================

    def _measurement_worker(self, params: Dict[str, Any], 
                            on_progress: Callable, on_data: Callable, 
                            on_error: Callable, on_finished: Callable):
        """Main measurement worker thread."""
        timing_log("=== MEASUREMENT WORKER START ===")
        try:
            # Parse parameters
            meas_params = self._parse_parameters(params)
            system_name = self._get_smu_system_name() if not meas_params['simulation_mode'] and self.smu else 'unknown'
            
            if self._stop_event.is_set():
                return
            
            # 1. Setup: Configure scope
            on_progress("Configuring hardware...")
            vertical_offset = 0.0
            
            if not meas_params['simulation_mode']:
                self._ensure_scope_connected(params)
                
                if params.get('auto_configure_scope', True):
                    vertical_offset = self._configure_scope_auto(params, meas_params)
                    self._start_scope_acquisition()
                    # DO NOT disconnect - keep scope connected to avoid reset
                    # The scope will continue acquiring in AUTO mode
                    timing_log("Scope: Keeping connection open (AUTO mode will continue)")
                # For manual scope setup, connection should already exist
            
            # 2. Configure SMU (auto-connect if needed)
            if not meas_params['simulation_mode']:
                if self.smu is None:
                    # Try to auto-connect SMU using params
                    timing_log("SMU: Not connected, attempting auto-connection...")
                    self._auto_connect_smu(params)
                    if self.smu is None:
                        raise RuntimeError("SMU not connected and auto-connection failed. Please click 'Connect SMU' button first.")
                self._configure_smu_pre_pulse(meas_params, system_name)
            
            if self._stop_event.is_set():
                return
            
            # 2.5. Wait for scope to trigger before sending pulse (if auto-configured)
            # This ensures the scope has triggered at least once and is ready for our pulse
            if not meas_params['simulation_mode'] and params.get('auto_configure_scope', True):
                timing_log(f"=== WAITING {SCOPE_PRE_TRIGGER_WAIT_S:.1f}s FOR SCOPE TO TRIGGER (AUTO mode) ===")
                on_progress(f"Waiting for scope to trigger ({SCOPE_PRE_TRIGGER_WAIT_S:.1f}s)...")
                time.sleep(SCOPE_PRE_TRIGGER_WAIT_S)
                timing_log("=== SCOPE PRE-TRIGGER WAIT COMPLETE ===")
            
            # 3. Execute pulse sequence
            self._execute_full_pulse_sequence(meas_params, system_name, on_progress)
            
            # 4. Disable SMU output (if not 4200A)
            if not meas_params['simulation_mode'] and system_name != 'keithley4200a':
                self.smu.enable_output(False)
            
            # 5. Acquire waveform
            on_progress("Acquiring data...")
            
            if meas_params['simulation_mode']:
                t, v_scope = self._generate_simulation_data(meas_params)
            else:
                # Wait if manual scope setup
                if not params.get('auto_configure_scope', True):
                    wait_time = 3.0
                    debug_print(f"Waiting {wait_time:.1f}s before reading waveform (manual scope setup)...")
                    time.sleep(wait_time)
                
                t, v_scope = self._acquire_waveform(params, meas_params)
            
            # 6. Process data
            v_scope, current, pulse_start_time = self._process_waveform_data(
                t, v_scope, vertical_offset, meas_params)
            
            # 7. Build metadata
            metadata = {
                'timestamp': time.time(),
                'params': params,
                'shunt_resistance': meas_params['shunt_r'],
                'pulse_voltage': meas_params['pulse_voltage'],
                'bias_voltage': meas_params['bias_voltage'],
                'pre_bias_time': meas_params['pre_bias_time'],
                'post_bias_time': meas_params['post_bias_time'],
                'pulse_start_time': pulse_start_time,
                'pulse_duration': meas_params['duration'],
                'vertical_offset': vertical_offset,
                'v_raw': v_scope.copy()
            }
            
            timing_log("=== MEASUREMENT WORKER END (SUCCESS) ===")
            on_data(t, v_scope, current, metadata)
            on_progress("Done.")
            
        except Exception as e:
            timing_log(f"=== MEASUREMENT WORKER END (ERROR) ===")
            traceback.print_exc()
            on_error(str(e))
        finally:
            # Safety cleanup
            if not meas_params.get('simulation_mode', False) and self.smu:
                try:
                    if system_name != 'keithley4200a':
                        self.smu.enable_output(False)
                except:
                    pass
            self.is_running = False
            on_finished()

    def _pulse_only_worker(self, params: Dict[str, Any],
                           on_progress: Callable, on_error: Callable, on_finished: Callable):
        """Pulse-only worker thread (no scope interaction)."""
        timing_log("=== PULSE-ONLY WORKER START ===")
        try:
            meas_params = self._parse_parameters(params)
            system_name = self._get_smu_system_name() if not meas_params['simulation_mode'] and self.smu else 'unknown'
            
            if self._stop_event.is_set():
                return
            
            # Configure SMU
            if not meas_params['simulation_mode']:
                if self.smu is None:
                    raise RuntimeError("SMU not connected. Please click 'Connect SMU' button first.")
                self._configure_smu_pre_pulse(meas_params, system_name)
            
            if self._stop_event.is_set():
                return
            
            # Execute pulse sequence
            self._execute_full_pulse_sequence(meas_params, system_name, on_progress)
            
            # Disable output
            if not meas_params['simulation_mode'] and system_name != 'keithley4200a':
                self.smu.enable_output(False)
            
            timing_log("=== PULSE-ONLY WORKER END ===")
            on_progress("Pulse complete.")
            
        except Exception as e:
            timing_log(f"=== PULSE-ONLY WORKER END (ERROR) ===")
            traceback.print_exc()
            on_error(str(e))
        finally:
            if not meas_params.get('simulation_mode', False) and self.smu:
                try:
                    if system_name != 'keithley4200a':
                        self.smu.enable_output(False)
                except:
                    pass
            self.is_running = False
            on_finished()

    def _scope_only_worker(self, params: Dict[str, Any],
                           on_progress: Callable, on_data: Callable,
                           on_error: Callable, on_finished: Callable):
        """Scope-only worker thread (no pulse, just read screen).
        
        This function does NOT reset the scope - it only reads what's currently on screen.
        Similar to grab_screen_waveform.py behavior.
        """
        timing_log("=== SCOPE-ONLY WORKER START ===")
        try:
            meas_params = self._parse_parameters(params)
            
            if meas_params['simulation_mode']:
                raise RuntimeError("Scope-only grab not available in simulation mode")
            
            if not self.scope_manager:
                raise RuntimeError("Oscilloscope Manager not available (import failed).")
            
            # Try to reuse existing connection first (don't reset scope)
            scope = self.scope_manager.scope
            need_reconnect = False
            
            # Check if existing connection is valid
            if scope is None or not hasattr(scope, 'inst') or scope.inst is None:
                need_reconnect = True
            else:
                # Test if connection is still valid without resetting
                try:
                    scope.inst.query("*IDN?", timeout=2000)  # Quick IDN query to test connection
                    timing_log("Scope: Existing connection is valid - reusing it (no reset)")
                except Exception as ex:
                    timing_log(f"Scope: Existing connection invalid ({ex}), will reconnect")
                    need_reconnect = True
            
            # Only reconnect if absolutely necessary
            if need_reconnect:
                addr = params.get('scope_address')
                if not addr or not addr.strip():
                    raise RuntimeError("No oscilloscope address provided. Please set scope address.")
                
                scope_type = params.get('scope_type', 'Tektronix TBS1000C')
                if scope_type == 'Auto-Detect':
                    scope_type = 'Unknown'
                
                timing_log(f"Scope: Connecting to {addr} (no reset - just reading screen)")
                on_progress("Connecting to oscilloscope...")
                if not self.scope_manager.manual_init_scope(scope_type, addr):
                    raise RuntimeError(f"Could not connect to oscilloscope at {addr}.")
                scope = self.scope_manager.scope
            
            if not scope or not hasattr(scope, 'inst') or scope.inst is None:
                raise RuntimeError("Scope not properly initialized.")
            
            # Read waveform (this does NOT reset the scope - just reads what's on screen)
            on_progress("Reading scope screen...")
            t, v_scope = self._read_screen_buffer(scope, meas_params['scope_ch'])
            
            if len(t) == 0:
                raise RuntimeError("No data returned from scope.")
            
            # Process data
            v_scope, current, pulse_start_time = self._process_waveform_data(
                t, v_scope, 0.0, meas_params)
            
            # Build metadata
            metadata = {
                'timestamp': time.time(),
                'params': params,
                'shunt_resistance': meas_params['shunt_r'],
                'pulse_voltage': params.get('pulse_voltage'),
                'bias_voltage': params.get('bias_voltage'),
                'pulse_start_time': pulse_start_time,
                'pulse_duration': params.get('pulse_duration'),
                'scope_only': True,
                'v_raw': v_scope.copy()
            }
            
            timing_log("=== SCOPE-ONLY WORKER END ===")
            on_data(t, v_scope, current, metadata)
            on_progress("Done.")
            
        except Exception as e:
            timing_log(f"=== SCOPE-ONLY WORKER END (ERROR) ===")
            traceback.print_exc()
            on_error(str(e))
        finally:
            self.is_running = False
            on_finished()
