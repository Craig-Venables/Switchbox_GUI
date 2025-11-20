from __future__ import annotations

import time
from typing import Optional, Dict, Any, TYPE_CHECKING

# Lazy imports to avoid failing if dependencies are missing
# Each controller is imported only when needed
if TYPE_CHECKING:
    from Equipment.SMU_AND_PMU import (
        Keithley2400Controller,
        Keithley2450_TSP,
        Keithley2450_TSP_Sim,
        HP4140BController,
        Keithley4200AController,
        Keithley4200A_KXCI,
    )


class _Keithley4200A_KXCI_Wrapper:
    """
    Wrapper around Keithley4200A_KXCI to provide DC measurement API compatibility.
    
    This wrapper adds basic DC measurement methods (set_voltage, measure_current, etc.)
    by calling C modules via EX commands, since the 4200A via GPIB/KXCI can only execute
    C modules, not direct SCPI/TSP commands.
    
    The wrapped KXCI controller provides the GPIB connection and UL mode management,
    and this wrapper adds the unified API expected by IVControllerManager by calling
    appropriate C modules (e.g., smu_ivsweep for single-point measurements).
    
    Note: For C module execution (pulse trains, sweeps), use the underlying KXCI
    controller methods directly. This wrapper only provides basic DC measurements
    by wrapping C module calls.
    """
    
    def __init__(self, kxci_controller):
        """
        Initialize wrapper around KXCI controller.
        
        Args:
            kxci_controller: Keithley4200A_KXCI instance (must already be connected)
        """
        self._kxci = kxci_controller
        self._output_enabled = False
        self._last_source_mode = "voltage"  # or "current"
        self._current_limit = 1e-3  # Default current compliance
        self._voltage_limit = 10.0  # Default voltage compliance
        self._last_voltage = 0.0  # Track last set voltage
        self._last_current = 0.0  # Track last set current
        
        # Note: Don't force connection in __init__ - connection will be established
        # when needed. This allows the wrapper to be created without immediate connection.
        # Connection will be checked/established on first use.
        
        # Import C module helpers for single-point measurements
        try:
            import importlib
            _smu_iv_sweep_module = importlib.import_module(
                'Equipment.SMU_AND_PMU.4200A.C_Code_with_python_scripts.A_Iv_Sweep.run_smu_vi_sweep'
            )
            self._build_ex_command = _smu_iv_sweep_module.build_ex_command
        except (ImportError, AttributeError) as e:
            raise RuntimeError(
                f"Required C module helpers not available: {e}. "
                "Cannot perform DC measurements without smu_ivsweep module."
            ) from e
    
    # Unified API methods (matching Keithley4200AController interface)
    # Note: These methods call C modules via EX commands, not direct instrument commands
    
    def set_voltage(self, voltage: float, Icc: float = 1e-3):
        """
        Set voltage and current compliance.
        
        Note: This only stores the voltage - the actual measurement happens when
        measure_current() is called, which executes a C module to apply the voltage
        and measure current.
        """
        self._last_source_mode = "voltage"
        self._current_limit = float(Icc)
        self._last_voltage = float(voltage)
        self._output_enabled = True
        # Note: We don't actually apply voltage here - that happens during measurement
    
    def set_current(self, current: float, Vcc: float = 10.0):
        """
        Set current and voltage compliance.
        
        Note: Current sourcing is not supported via basic C modules.
        This only stores the values for reference.
        """
        self._last_source_mode = "current"
        self._voltage_limit = float(Vcc)
        self._last_current = float(current)
        self._output_enabled = True
        # Note: Current sourcing requires a specialized C module
    
    def measure_voltage(self) -> float:
        """
        Measure voltage.
        
        If output is enabled and voltage was set, this executes a single-point
        measurement C module to apply the voltage and return the measured voltage.
        """
        if not self._output_enabled or self._last_source_mode != "voltage":
            return float("nan")
        
        # Execute single-point measurement using smu_ivsweep C module
        try:
            result = self._execute_single_point_measurement(
                voltage=self._last_voltage,
                ilimit=self._current_limit
            )
            return result.get('voltage', float("nan"))
        except Exception as e:
            print(f"[KXCI Wrapper] Warning: Failed to measure voltage: {e}")
            return float("nan")
    
    def measure_current(self) -> float:
        """
        Measure current.
        
        If output is enabled and voltage was set, this executes a single-point
        measurement C module to apply the voltage and measure current.
        """
        if not self._output_enabled or self._last_source_mode != "voltage":
            return float("nan")
        
        # Execute single-point measurement using smu_ivsweep C module
        try:
            result = self._execute_single_point_measurement(
                voltage=self._last_voltage,
                ilimit=self._current_limit
            )
            return result.get('current', float("nan"))
        except Exception as e:
            print(f"[KXCI Wrapper] Warning: Failed to measure current: {e}")
            return float("nan")
    
    def _execute_single_point_measurement(self, voltage: float, ilimit: float) -> Dict[str, float]:
        """
        Execute a single-point measurement by calling smu_ivsweep C module.
        
        This performs a minimal sweep: 0 → +V → -V → 0 (one cycle) and extracts
        the measurement at +V. This is the only way to get DC measurements via
        GPIB/KXCI, as direct SCPI commands are not available.
        
        Args:
            voltage: Voltage to apply (V)
            ilimit: Current compliance limit (A)
            
        Returns:
            Dictionary with 'voltage' and 'current' keys
        """
        if voltage < 0:
            raise ValueError(f"Voltage must be >= 0 (got {voltage}V)")
        
        # Build EX command for single-cycle sweep (0 → +V → -V → 0)
        num_cycles = 1
        num_points = 4  # 0, +V, -V, 0
        
        command = self._build_ex_command(
            vpos=voltage,
            vneg=0.0,  # Auto-sets to -voltage internally
            num_cycles=num_cycles,
            num_points=num_points,
            settle_time=0.01,  # 10ms settle time
            ilimit=ilimit,
            integration_time=0.01,  # 0.01 PLC
            clarius_debug=0,
        )
        
        # Use the wrapped KXCI controller to execute
        # Ensure we're in UL mode
        was_in_ul = self._kxci._ul_mode_active
        if not was_in_ul:
            if not self._kxci._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode for measurement")
        
        try:
            # Execute EX command (returns tuple: (return_value, error_message))
            return_value, error_msg = self._kxci._execute_ex_command(command)
            if error_msg:
                raise RuntimeError(f"EX command failed: {error_msg}")
            # Return value of 1 means success, -1 means error, 0/None also OK
            if return_value not in (0, 1, None):
                # Check if it's an error code (negative or not 1)
                if isinstance(return_value, int) and return_value < 0:
                    raise RuntimeError(f"EX command returned error code: {return_value}")
                elif return_value != 1:
                    # Unexpected return value
                    raise RuntimeError(f"EX command returned unexpected value: {return_value} (expected 1)")
            
            # Retrieve data via GP commands (exit UL mode first)
            # GP commands must be sent AFTER exiting UL mode
            # Always exit UL mode before GP commands
            self._kxci._exit_ul_mode()
            time.sleep(0.03)
            
            # Query GP parameters: GP 6 = Vforce, GP 4 = Imeas
            # Note: GP commands must be sent AFTER exiting UL mode
            vforce = self._kxci._query_gp(6, num_points)
            imeas = self._kxci._query_gp(4, num_points)
            
            # Extract the +voltage point (should be at index 1: 0 → +V → -V → 0)
            if len(vforce) >= 2 and len(imeas) >= 2:
                # Find the point closest to +voltage
                target_idx = 1  # Index 1 should be the +voltage point
                if abs(vforce[target_idx] - voltage) < abs(vforce[target_idx] - (-voltage)):
                    # Index 1 is +voltage
                    measured_v = vforce[target_idx]
                    measured_i = imeas[target_idx]
                else:
                    # Index 1 is -voltage, try index 2
                    if len(vforce) >= 3:
                        measured_v = vforce[2]
                        measured_i = imeas[2] if len(imeas) >= 3 else 0.0
                    else:
                        measured_v = vforce[1]
                        measured_i = imeas[1]
                
                return {
                    'voltage': float(measured_v),
                    'current': float(measured_i),
                }
            else:
                raise RuntimeError(f"Unexpected data length: vforce={len(vforce)}, imeas={len(imeas)}")
                
        finally:
            # Ensure we're out of UL mode if we entered it
            # (we already exited after GP commands, but make sure)
            if not was_in_ul:
                # Make sure we're out of UL mode if we entered it
                if self._kxci._ul_mode_active:
                    self._kxci._exit_ul_mode()
    
    def enable_output(self, enable: bool = True):
        """
        Enable or disable output.
        
        Note: For 4200A via GPIB/KXCI, output is controlled through C modules,
        not direct commands. This method only updates the internal state flag.
        """
        # For 4200A via GPIB/KXCI, output is controlled through C module execution
        # We can't directly enable/disable output like other SMUs
        # This method only updates the internal state
        self._output_enabled = enable
        if not enable:
            # Reset voltage/current tracking when disabling output
            self._last_voltage = 0.0
            self._last_current = 0.0
    
    def close(self):
        """Close connection."""
        self.enable_output(False)
        if self._kxci:
            self._kxci.disconnect()
    
    def get_idn(self) -> str:
        """
        Get instrument identification using *IDN? query.
        
        Follows the same pattern as TSP GUI: directly queries *IDN? from the
        instrument. Uses standard SCPI *IDN? command (not TSP) to verify
        connection and get instrument identification.
        """
        # Check if controller exists and is connected
        if not self._kxci.inst:
            return "Keithley 4200A (Not Connected)"
        
        try:
            # *IDN? is a standard SCPI command (not TSP) - works in normal mode
            # If we're in UL mode, exit it first to send *IDN? (4200A specific)
            if self._kxci._ul_mode_active:
                self._kxci._exit_ul_mode()
                time.sleep(0.05)
            
            # Send *IDN? query directly (same pattern as TSP GUI)
            idn = self._kxci.inst.query("*IDN?").strip()
            return idn
        except Exception as e:
            print(f"[KXCI Wrapper] Warning: Failed to query *IDN?: {e}")
            return "Keithley 4200A (Not Connected)"
    
    def beep(self, frequency: float = 1000, duration: float = 0.2):
        """
        Beep (not supported on 4200A).
        
        The 4200A does not have a beeper, so this method does nothing.
        """
        # 4200A does not have a beeper
        return None
    
    # Expose underlying KXCI controller for advanced features
    @property
    def kxci(self):
        """Access underlying KXCI controller for EX command execution."""
        return self._kxci
    
    # Compatibility properties
    @property
    def inst(self):
        """Access underlying pyvisa instrument (for compatibility)."""
        return self._kxci.inst
    
    @property
    def device(self):
        """Alias for inst (for compatibility with other controllers)."""
        return self._kxci.inst


class IVControllerManager:
    """Manager to initialize and unify different IV controllers behind a common API.

    Exposes a minimal, consistent interface used by the GUI/test code:
      - set_voltage(voltage: float, Icc: float = ...)
      - set_current(current: float, Vcc: float = ...)
      - measure_voltage() -> float or (float, ...)
      - measure_current() -> float or (float, ...)
      - enable_output(enable: bool)
      - close()

    Also supports manual selection using system_configs entries, where
    SMU_AND_PMU Type can be 'Keithley 2400' or 'Hp4140b'.
    """

    @classmethod
    def _get_supported(cls) -> Dict[str, Any]:
        """Get supported controllers with lazy imports."""
        # Lazy imports to avoid failing if dependencies are missing
        try:
            from Equipment.SMU_AND_PMU import Keithley2400Controller
        except ImportError:
            Keithley2400Controller = None
        
        try:
            from Equipment.SMU_AND_PMU import Keithley2450_TSP
        except ImportError:
            Keithley2450_TSP = None
        
        try:
            from Equipment.SMU_AND_PMU import Keithley2450_TSP_Sim
        except ImportError:
            Keithley2450_TSP_Sim = None
        
        try:
            from Equipment.SMU_AND_PMU import HP4140BController
        except ImportError:
            HP4140BController = None
        
        try:
            from Equipment.SMU_AND_PMU import Keithley4200AController
        except ImportError:
            Keithley4200AController = None
        
        # Import KXCI controller for GPIB connections (NEW - preferred method)
        try:
            from Equipment.SMU_AND_PMU import Keithley4200A_KXCI
        except ImportError:
            Keithley4200A_KXCI = None
        
        supported: Dict[str, Any] = {}
        
        if Keithley2400Controller is not None:
            supported['Keithley 2401'] = {
                'class': Keithley2400Controller,
                'address_key': 'SMU_address',
            }
        
        if Keithley2450_TSP is not None:
            supported['Keithley 2450'] = {
                'class': Keithley2450_TSP,  # Now using TSP for all 2450 operations
                'address_key': 'SMU_address',
            }
        
        if Keithley2450_TSP_Sim is not None:
            supported['Keithley 2450 (Simulation)'] = {
                'class': Keithley2450_TSP_Sim,
                'address_key': 'SMU_address',
            }
        
        if HP4140BController is not None:
            supported['Hp4140b'] = {
                'class': HP4140BController,
                'address_key': 'SMU_address',
            }
        
        # For 4200A, we now support both GPIB (KXCI) and IP:port (LPT) connections
        # GPIB is preferred for C module support, IP:port kept for backward compatibility
        if Keithley4200A_KXCI is not None or Keithley4200AController is not None:
            # Will be handled dynamically based on address format
            supported['Keithley 4200A'] = {
                'class_kxci': Keithley4200A_KXCI,  # GPIB/KXCI controller (preferred)
                'class_lpt': Keithley4200AController,  # IP:port/LPT controller (legacy, kept for compatibility)
                'address_key': 'SMU_address',
            }
        
        return supported
    
    @property
    def SUPPORTED(self) -> Dict[str, Any]:
        """Get supported controllers (lazy-loaded)."""
        return self._get_supported()

    def __init__(self, smu_type: str, address: str) -> None:
        self.instrument = None
        self.smu_type = smu_type
        self.address = address
        self._init_instrument()

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'IVControllerManager':
        smu_type = config.get('SMU Type', 'Keithley 2400')
        address = config.get('SMU_address')
        return cls(smu_type, address)

    def _init_instrument(self) -> None:
        supported = self._get_supported()
        meta = supported.get(self.smu_type)
        if not meta:
            available = ', '.join(supported.keys()) if supported else 'none'
            raise ValueError(
                f"Unsupported SMU Type: {self.smu_type}. "
                f"Available types: {available}. "
                f"Check that required dependencies are installed."
            )
        
        # Special handling for 4200A: choose controller based on address format
        # GPIB addresses -> use KXCI controller (preferred, supports C modules)
        # IP:port addresses -> use LPT controller (legacy, kept for backward compatibility)
        if self.smu_type == 'Keithley 4200A':
            is_gpib = self.address and self.address.upper().startswith('GPIB')
            
            if is_gpib:
                # Use KXCI controller for GPIB addresses
                controller_class = meta.get('class_kxci')
                if controller_class is None:
                    raise RuntimeError(
                        f"KXCI controller for 4200A (GPIB) is not available. "
                        f"Required dependencies may be missing. Check installation."
                    )
                # Create KXCI controller with GPIB address
                kxci_inst = controller_class(gpib_address=self.address, timeout=30.0)
                # Wrap it with DC measurement API
                self.instrument = _Keithley4200A_KXCI_Wrapper(kxci_inst)
            else:
                # Use LPT controller for IP:port addresses (legacy support)
                controller_class = meta.get('class_lpt')
                if controller_class is None:
                    raise RuntimeError(
                        f"LPT controller for 4200A (IP:port) is not available. "
                        f"Required dependencies may be missing. Check installation."
                    )
                # Create LPT controller with IP:port address
                self.instrument = controller_class(self.address)
        else:
            # Standard controllers (2400, 2450, etc.)
            controller_class = meta['class']
            if controller_class is None:
                raise RuntimeError(
                    f"Controller class for {self.smu_type} is not available. "
                    f"Required dependencies may be missing. Check installation."
                )
            self.instrument = controller_class(self.address)

    # Unified API pass-throughs
    def set_voltage(self, voltage: float, Icc: float = 1e-3):
        return self.instrument.set_voltage(voltage, Icc)

    def set_current(self, current: float, Vcc: float = 10.0):
        return self.instrument.set_current(current, Vcc)

    def measure_voltage(self):
        return self.instrument.measure_voltage()

    def measure_current(self):
        value = self.instrument.measure_current()
        # Only normalize for 4200A so GUI can use current[1]
        if self.smu_type == 'Keithley 4200A':
            try:
                if isinstance(value, (list, tuple)):
                    return (None, float(value[-1]))
                return (None, float(value))
            except Exception:
                return (None, float('nan'))
        return value

    def enable_output(self, enable: bool = True):
        return self.instrument.enable_output(enable)

    def shutdown(self):
        if hasattr(self.instrument, 'shutdown'):
            return self.instrument.shutdown()

    def close(self):
        if hasattr(self.instrument, 'close'):
            self.instrument.close()

    # Connection status helper used by GUI code
    def is_connected(self) -> bool:
        inst = getattr(self, 'instrument', None)
        if inst is None:
            return False
        # Handle KXCI wrapper (GPIB connection) - verify with *IDN? query
        if isinstance(inst, _Keithley4200A_KXCI_Wrapper):
            try:
                # Use get_idn() which sends *IDN? to verify connection
                idn = inst.get_idn()
                # If IDN contains "Not Connected", connection failed
                return "Not Connected" not in idn
            except Exception:
                return False
        # Common attributes for our supported controllers
        if hasattr(inst, 'device'):
            return getattr(inst, 'device') is not None
        if hasattr(inst, 'inst'):
            return getattr(inst, 'inst') is not None
        if hasattr(inst, 'sock'):
            return getattr(inst, 'sock') is not None
        # Fallback: assume connected if no known handle is exposed
        return True
    # Optional pass-throughs
    def beep(self, frequency: float = 1000, duration: float = 0.2):
        if hasattr(self.instrument, 'beep'):
            try:
                return self.instrument.beep(frequency, duration)
            except Exception:
                return None

    def get_idn(self) -> str:
        if hasattr(self.instrument, 'get_idn'):
            try:
                return self.instrument.get_idn()
            except Exception:
                return self.smu_type
        return self.smu_type

    # Pulse preparation helpers (only effective on instruments that support them)
    def prepare_for_pulses(self, Icc: float = 1e-3, v_range: float = 20.0, ovp: float = 21.0,
                           use_remote_sense: bool = False, autozero_off: bool = True) -> None:
        inst = getattr(self, 'instrument', None)
        if inst is not None and hasattr(inst, 'prepare_for_pulses'):
            try:
                inst.prepare_for_pulses(Icc=Icc, v_range=v_range, ovp=ovp,
                                        use_remote_sense=use_remote_sense, autozero_off=autozero_off)
            except Exception:
                pass

    def finish_pulses(self, Icc: float = 1e-3, restore_autozero: bool = True) -> None:
        inst = getattr(self, 'instrument', None)
        if inst is not None and hasattr(inst, 'finish_pulses'):
            try:
                inst.finish_pulses(Icc=Icc, restore_autozero=restore_autozero)
            except Exception:
                pass
    
    def get_capabilities(self):
        """
        Return instrument capabilities for sweep optimization.
        
        Returns:
            InstrumentCapabilities: Capabilities object describing instrument features
        
        Example:
            >>> caps = keithley.get_capabilities()
            >>> if caps.supports_hardware_sweep:
            ...     # Use fast hardware sweep
        """
        from Measurments.sweep_config import InstrumentCapabilities
        
        if self.smu_type == 'Keithley 4200A':
            return InstrumentCapabilities(
                supports_hardware_sweep=True,
                supports_arbitrary_sweep=True,
                supports_pulses=True,
                supports_current_source=True,
                min_step_delay_ms=1.0,
                max_points_per_sweep=10000,
                voltage_range=(-200.0, 200.0),
                current_range=(-1.0, 1.0)
            )
        elif self.smu_type == 'Keithley 2450':
            return InstrumentCapabilities(
                supports_hardware_sweep=True,  # Via TSP scripting
                supports_arbitrary_sweep=True,
                supports_pulses=True,  # Fast TSP pulse capabilities
                supports_current_source=True,
                min_step_delay_ms=1.0,  # Fast with TSP
                max_points_per_sweep=10000,
                voltage_range=(-200.0, 200.0),
                current_range=(-1.05, 1.05)
            )
        elif self.smu_type in ['Keithley 2401', 'Keithley 2400']:
            return InstrumentCapabilities(
                supports_hardware_sweep=False,
                supports_arbitrary_sweep=False,
                supports_pulses=True,
                supports_current_source=True,
                min_step_delay_ms=50.0,
                max_points_per_sweep=2500,
                voltage_range=(-20.0, 20.0),
                current_range=(-1.0, 1.0)
            )
        elif self.smu_type == 'Hp4140b':
            return InstrumentCapabilities(
                supports_hardware_sweep=False,
                supports_arbitrary_sweep=False,
                supports_pulses=False,
                supports_current_source=True,
                min_step_delay_ms=100.0,
                max_points_per_sweep=1000,
                voltage_range=(-100.0, 100.0),
                current_range=(1e-14, 1e-2)
            )
        else:
            # Default conservative capabilities
            return InstrumentCapabilities()
