from __future__ import annotations

import importlib
import importlib.util
import time
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING, Tuple, List, Callable, Iterable

# Import SourceMode for type hints
try:
    from Measurments.source_modes import SourceMode
except ImportError:
    SourceMode = None  # Will be imported when needed

# Lazy imports to avoid failing if dependencies are missing
# Each controller is imported only when needed
if TYPE_CHECKING:
    from Equipment.SMU_AND_PMU import (
        Keithley2400Controller,
        Keithley2450_TSP,
        Keithley2450_TSP_Sim,
        HP4140BController,
        Keithley4200A_KXCI,
    )

_connection_check_sample_helper = None
try:
    _runner_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "SMU_AND_PMU"
        / "4200A"
        / "C_Code_with_python_scripts"
        / "Single_Point_Bias"
        / "connection_check_runner.py"
    )
    if _runner_path.exists():
        spec = importlib.util.spec_from_file_location("connection_check_runner", _runner_path)
        if spec and spec.loader:
            _connection_check_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_connection_check_module)  # type: ignore[attr-defined]
            _connection_check_sample_helper = getattr(_connection_check_module, "execute_single_sample", None)
            if _connection_check_sample_helper is None:
                print("[connection_check] execute_single_sample not found in helper module")
        else:
            print("[connection_check] Unable to build module spec for connection_check_runner")
    else:
        print(f"[connection_check] Runner file missing: {_runner_path}")
except Exception as exc:  # pragma: no cover
    print(f"[connection_check] Failed to load helper: {exc}")
    _connection_check_sample_helper = None


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
        import threading
        self._kxci = kxci_controller
        self._output_enabled = False
        self._last_source_mode = "voltage"  # or "current"
        self._current_limit = 1e-3  # Default current compliance
        self._voltage_limit = 10.0  # Default voltage compliance
        self._last_voltage = 0.0  # Track last set voltage
        self._last_current = 0.0  # Track last set current
        self._ex_command_lock = threading.Lock()  # Lock to prevent concurrent EX commands
        
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
        
        self._connection_check_helper = _connection_check_sample_helper
        self._ensure_connection()
    
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
    
    def connection_check_sample(
        self,
        bias_voltage: float = 0.2,
        sample_interval: float = 0.1,
        settle_time: float = 0.01,
        ilimit: Optional[float] = None,
        integration_time: float = 0.01,
        buffer_size: int = 8,
    ) -> Dict[str, float]:
        """
        Take a single connection-check sample using smu_check_connection.
        
        Returns a dict with ``voltage`` and ``current`` fields. Intended for the
        Connection Check GUI so it can stream readings without reimplementing the
        EX/GP logic.
        """
        self._ensure_connection()

        if self._connection_check_helper is None:
            raise RuntimeError("Connection check helper is not available on this build.")
        
        ilimit_val = float(ilimit) if ilimit is not None else self._current_limit
        was_in_ul = self._kxci._ul_mode_active
        if not was_in_ul:
            entered = self._kxci._enter_ul_mode()
            if not entered:
                raise RuntimeError("Failed to enter UL mode for connection check sample")
        try:
            return self._connection_check_helper(
                self._kxci,
                bias_voltage=bias_voltage,
                sample_interval=sample_interval,
                settle_time=settle_time,
                ilimit=ilimit_val,
                integration_time=integration_time,
                buffer_size=buffer_size,
            )
        finally:
            if not was_in_ul and self._kxci._ul_mode_active:
                self._kxci._exit_ul_mode()
    
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
        self._ensure_connection()
        
        # Handle negative voltages by converting to positive sweep
        # The C module pattern is 0 → +V → -V → 0
        # If voltage is negative, we want to measure at -voltage, so use positive sweep with vneg
        if voltage < 0:
            # For negative voltage, create sweep that goes to the negative value
            # Use abs(voltage) as vpos, and voltage (negative) as vneg
            vpos = abs(voltage)
            vneg = voltage  # Already negative
        else:
            # For positive voltage, standard sweep
            vpos = voltage
            vneg = -voltage  # Negative of voltage
        
        # Build EX command for single-cycle sweep (0 → +V → -V → 0)
        num_cycles = 1
        num_points = 4  # 0, +V, -V, 0
        
        command = self._build_ex_command(
            vhigh=vpos,
            vlow=vneg,  # Explicitly set negative voltage
            num_steps=1,  # Minimal steps for single point
            num_cycles=num_cycles,
            num_points=num_points,
            step_delay=0.01,  # 10ms step delay (was settle_time)
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
            
            # Extract the measurement at the target voltage
            # Pattern is: 0 → +vpos → vneg → 0 (indices 0, 1, 2, 3)
            if len(vforce) >= 4 and len(imeas) >= 4:
                # Find the point closest to the requested voltage
                target_voltage = voltage
                best_idx = 0
                min_diff = abs(vforce[0] - target_voltage)
                
                for i in range(len(vforce)):
                    diff = abs(vforce[i] - target_voltage)
                    if diff < min_diff:
                        min_diff = diff
                        best_idx = i
                
                measured_v = vforce[best_idx]
                measured_i = imeas[best_idx] if best_idx < len(imeas) else 0.0
                
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

    @property
    def kxci(self):
        """Property to access the underlying KXCI controller (for compatibility)."""
        return self._kxci
    
    def _ensure_connection(self) -> None:
        """Ensure the underlying KXCI controller is connected before issuing commands."""
        if not self._kxci:
            raise RuntimeError("KXCI controller not available")
        # Check if already connected (inst exists and is truthy)
        if hasattr(self._kxci, 'inst') and self._kxci.inst:
            return
        # For simulations, inst might be self-reference, so check if connect() exists
        if hasattr(self._kxci, 'connect'):
            if not self._kxci.connect():
                raise RuntimeError("Failed to connect to Keithley 4200A via KXCI")
        # If no connect method, assume already connected (simulation case)
    
    def get_idn(self) -> str:
        """
        Get instrument identification using *IDN? query.
        
        Follows the same pattern as TSP GUI: directly queries *IDN? from the
        instrument. Uses standard SCPI *IDN? command (not TSP) to verify
        connection and get instrument identification.
        
        If not connected, will attempt to connect first (lazy connection).
        """
        # Connect if not already connected (lazy connection)
        # For simulations, inst might be self-reference, so check differently
        if not hasattr(self._kxci, 'inst') or not self._kxci.inst:
            if hasattr(self._kxci, 'connect'):
                if not self._kxci.connect():
                    return "Keithley 4200A (Not Connected)"
            else:
                # No connect method - assume simulation that's always connected
                pass
        
        try:
            # For simulations, use get_idn() method if available
            if hasattr(self._kxci, 'get_idn'):
                return self._kxci.get_idn()
            
            # *IDN? is a standard SCPI command (not TSP) - works in normal mode
            # If we're in UL mode, exit it first to send *IDN? (4200A specific)
            if hasattr(self._kxci, '_ul_mode_active') and self._kxci._ul_mode_active:
                self._kxci._exit_ul_mode()
                time.sleep(0.05)
            
            # Send *IDN? query directly (same pattern as TSP GUI)
            if hasattr(self._kxci, 'inst') and self._kxci.inst:
                idn = self._kxci.inst.query("*IDN?").strip()
            else:
                # Fallback for simulations
                return "KEITHLEY INSTRUMENTS INC.,MODEL 4200A-SIM,000001,1.0.0"
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
        
        # Import KXCI controller for GPIB connections (preferred method)
        try:
            from Equipment.SMU_AND_PMU import Keithley4200A_KXCI
        except ImportError:
            Keithley4200A_KXCI = None
        
        # Import simulation classes
        try:
            from Equipment.SMU_AND_PMU import Simulation2400
        except ImportError:
            Simulation2400 = None
        
        try:
            from Equipment.SMU_AND_PMU import Simulation4200
        except ImportError:
            Simulation4200 = None
        
        supported: Dict[str, Any] = {}
        
        if Keithley2400Controller is not None:
            supported['Keithley 2401'] = {
                'class': Keithley2400Controller,
                'address_key': 'SMU_address',
            }
        
        if Simulation2400 is not None:
            supported['simulation_2400'] = {
                'class': Simulation2400,
                'address_key': 'SMU_address',
            }
        
        if Keithley2450_TSP is not None:
            supported['Keithley 2450'] = {
                'class': Keithley2450_TSP,  # Now using TSP for all 2450 operations
                'address_key': 'SMU_address',
            }
        
        if Keithley2450_TSP_Sim is not None:
            supported['simulation_2450'] = {
                'class': Keithley2450_TSP_Sim,
                'address_key': 'SMU_address',
            }
        
        if HP4140BController is not None:
            supported['Hp4140b'] = {
                'class': HP4140BController,
                'address_key': 'SMU_address',
            }
        
        if Keithley4200A_KXCI is not None:
            supported['Keithley 4200A'] = {
                'class': Keithley4200A_KXCI,
                'address_key': 'SMU_address',
            }
        
        if Simulation4200 is not None:
            supported['simulation_4200'] = {
                'class': Simulation4200,
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
        
        # Special handling for 4200A (real and simulation): always use the KXCI wrapper
        if self.smu_type in ['Keithley 4200A', 'simulation_4200']:
            controller_class = meta.get('class')
            if controller_class is None:
                raise RuntimeError(
                    f"Controller for {self.smu_type} is not available. "
                    f"Required dependencies may be missing. Check installation."
                )
            # For real 4200A, require GPIB address
            if self.smu_type == 'Keithley 4200A':
                if not self.address or not self.address.upper().startswith('GPIB'):
                    raise ValueError(
                        f"Keithley 4200A now requires a GPIB address (got '{self.address}'). "
                        "Update system_configs.json to point to the GPIB resource."
                    )
                kxci_inst = controller_class(gpib_address=self.address, timeout=30.0)
            else:
                # Simulation - address can be anything (default provided)
                address = self.address or "SIM::GPIB0::17::INSTR"
                kxci_inst = controller_class(gpib_address=address, timeout=30.0)
            
            if hasattr(kxci_inst, "set_debug"):
                kxci_inst.set_debug(False)
            # For simulations, ensure connection is established
            if self.smu_type == 'simulation_4200':
                # Auto-connect simulation
                if hasattr(kxci_inst, 'connect'):
                    connected = kxci_inst.connect()
                    print(f"[IVController] Simulation 4200 connect() returned: {connected}")
                # Ensure inst attribute is set for connection checks
                if not hasattr(kxci_inst, 'inst') or kxci_inst.inst is None:
                    kxci_inst.inst = kxci_inst  # Self-reference for simulations
                print(f"[IVController] Simulation 4200 initialized and marked as connected")
                # Update smu_type to match what the wrapper expects
                self.smu_type = 'Keithley 4200A'  # Wrapper treats it as 4200A
            self.instrument = _Keithley4200A_KXCI_Wrapper(kxci_inst)
            print(f"[IVController] Created {self.smu_type} controller at {self.address}")
            print(f"[IVController] is_connected() = {self.is_connected()}")
        else:
            # Standard controllers (2400, 2450, simulation_2400, simulation_2450, etc.)
            controller_class = meta['class']
            if controller_class is None:
                raise RuntimeError(
                    f"Controller class for {self.smu_type} is not available. "
                    f"Required dependencies may be missing. Check installation."
                )
            # For simulations, provide default address if not given
            address = self.address
            if self.smu_type.startswith('simulation_') and not address:
                if self.smu_type == 'simulation_2400':
                    address = "SIM::GPIB0::24::INSTR"
                elif self.smu_type == 'simulation_2450':
                    address = "SIM::KEITHLEY2450"
            
            self.instrument = controller_class(address)
            
            # Auto-connect simulations
            if self.smu_type == 'simulation_2400':
                # Simulation 2400 is always "connected" (no real hardware)
                # Ensure device attribute is set for connection checks
                if not hasattr(self.instrument, 'device') or self.instrument.device is None:
                    self.instrument.device = self.instrument
                # Call connect if method exists
                if hasattr(self.instrument, 'connect'):
                    try:
                        connected = self.instrument.connect()
                        print(f"[IVController] Simulation 2400 connect() returned: {connected}")
                    except Exception as e:
                        print(f"[IVController] Simulation 2400 connect() raised: {e}")
                        pass  # Simulations may not have connect method
                print(f"[IVController] Simulation 2400 initialized and marked as connected")
                self.smu_type = 'Keithley 2401'  # Use same type as real 2400
            elif self.smu_type == 'simulation_2450':
                # Simulation 2450 - ensure it's marked as connected
                if hasattr(self.instrument, 'connect'):
                    try:
                        connected = self.instrument.connect()
                        print(f"[IVController] Simulation 2450 connect() returned: {connected}")
                    except Exception as e:
                        print(f"[IVController] Simulation 2450 connect() raised: {e}")
                        pass
                print(f"[IVController] Simulation 2450 initialized and marked as connected")
                self.smu_type = 'Keithley 2450'  # Use same type as real 2450

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

    def connection_check_sample(
        self,
        bias_voltage: float = 0.2,
        sample_interval: float = 0.1,
        settle_time: float = 0.01,
        ilimit: Optional[float] = None,
        integration_time: float = 0.01,
        buffer_size: int = 8,
    ):
        """Proxy connection-check helper if underlying instrument implements it."""
        inst = getattr(self.instrument, "connection_check_sample", None)
        if callable(inst):
            return inst(
                bias_voltage=bias_voltage,
                sample_interval=sample_interval,
                settle_time=settle_time,
                ilimit=ilimit,
                integration_time=integration_time,
                buffer_size=buffer_size,
            )
        raise AttributeError("connection_check_sample is not available for this instrument")

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
        
        # Handle KXCI wrapper (GPIB connection) - mark as connected if wrapper exists
        # For 4200A via GPIB/KXCI, connection is lazy (happens on first use)
        # So we consider it "connected" if the wrapper was successfully created
        # The actual connection will be established when needed (get_idn(), measurements, etc.)
        if isinstance(inst, _Keithley4200A_KXCI_Wrapper):
            # Wrapper exists = considered connected (lazy connection will happen when needed)
            # For simulations, also check if the underlying KXCI is properly initialized
            if hasattr(inst, '_kxci') and inst._kxci:
                # Check if simulation has proper attributes
                if hasattr(inst._kxci, 'inst') and inst._kxci.inst is not None:
                    return True
                # Simulations might have inst as self-reference
                if hasattr(inst._kxci, 'inst') or hasattr(inst._kxci, 'get_idn'):
                    return True
            return True  # Wrapper exists, assume connected
        
        # For simulations, check class name to auto-mark as connected
        inst_class_name = type(inst).__name__
        if 'Simulation' in inst_class_name or 'Sim' in inst_class_name:
            # Simulations are always "connected" (no real hardware)
            return True
        
        # Common attributes for our supported controllers
        if hasattr(inst, 'device'):
            device = getattr(inst, 'device')
            if device is not None:
                return True
        
        if hasattr(inst, 'inst'):
            inst_obj = getattr(inst, 'inst')
            if inst_obj is not None:
                return True
        
        # Check for socket connection (some controllers)
        if hasattr(inst, 'sock'):
            return getattr(inst, 'sock') is not None
        
        # Fallback: if instrument exists, assume connected
        # (Some controllers don't have device/inst attributes)
        return True
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
    
    # ========================================================================
    # Unified Measurement API - Routes to instrument-specific implementations
    # ========================================================================
    
    def do_iv_sweep(
        self,
        config: 'SweepConfig',
        psu=None,
        optical=None,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Execute IV sweep using instrument-specific optimized method.
        
        Routes based on self.smu_type to instrument-specific implementation.
        Each implementation respects instrument limits and provides live plotting.
        
        Args:
            config: SweepConfig with all sweep parameters
            psu: Optional power supply for LED control
            optical: Optional optical excitation system
            should_stop: Optional callback to check if measurement should stop
            on_point: Optional callback for live plotting (v, i, timestamp)
            
        Returns:
            Tuple of (voltages, currents, timestamps) arrays
            
        Raises:
            RuntimeError: If instrument-specific method is unavailable
            ValueError: If configuration violates instrument limits
        """
        from Measurments.measurement_context import MeasurementContext
        from Measurments.source_modes import SourceMode
        
        context = MeasurementContext(
            led=config.led if hasattr(config, 'led') else False,
            power=config.power if hasattr(config, 'power') else 1.0,
            sequence=config.sequence if hasattr(config, 'sequence') else None,
            source_mode=config.source_mode if hasattr(config, 'source_mode') else SourceMode.VOLTAGE,
            should_stop=should_stop,
            on_point=on_point
        )
        
        # Route to instrument-specific implementation
        if self.smu_type == 'Keithley 4200A':
            print("using 4200a")
            return self._do_iv_sweep_4200a(config, context, psu, optical)
        elif self.smu_type == 'Keithley 2450':
            return self._do_iv_sweep_2450(config, context, psu, optical)
        elif self.smu_type in ['Keithley 2401', 'Keithley 2400']:
            return self._do_iv_sweep_2400(config, context, psu, optical)
        else:
            print("using geneic")
            return self._do_iv_sweep_generic(config, context, psu, optical)
    
    def do_pulse_measurement(
        self,
        pulse_voltage: float,
        pulse_width_ms: float,
        num_pulses: int,
        read_voltage: float = 0.1,
        inter_pulse_delay_s: float = 0.01,
        icc: float = 1e-4,
        psu=None,
        optical=None,
        sequence: Optional[Iterable[str]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        validate_timing: bool = True,
        start_at_zero: bool = True,
        return_to_zero_at_end: bool = True,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Execute pulse measurement using instrument-specific optimized method.
        
        Routes based on self.smu_type to instrument-specific implementation.
        
        Args:
            pulse_voltage: Voltage for pulse (V)
            pulse_width_ms: Pulse width (ms)
            num_pulses: Number of pulses
            read_voltage: Read voltage between pulses (V)
            inter_pulse_delay_s: Delay between pulses (s)
            icc: Current compliance (A)
            psu: Optional power supply for LED control
            optical: Optional optical excitation system
            sequence: Optional LED sequence (list of '0'/'1')
            should_stop: Optional stop callback
            on_point: Optional callback for live plotting
            validate_timing: Validate timing constraints
            start_at_zero: Start at 0V
            return_to_zero_at_end: Return to 0V at end
            
        Returns:
            Tuple of (voltages, currents, timestamps) arrays
        """
        from Measurments.measurement_context import MeasurementContext
        from Measurments.source_modes import SourceMode
        
        # Check if LED is enabled (if sequence provided or implicit)
        led_enabled = sequence is not None or False
        
        context = MeasurementContext(
            led=led_enabled,
            power=1.0,
            sequence=list(sequence) if sequence else None,
            source_mode=SourceMode.VOLTAGE,
            should_stop=should_stop,
            on_point=on_point
        )
        
        # Route to instrument-specific implementation
        if self.smu_type == 'Keithley 4200A':
            return self._do_pulse_measurement_4200a(
                pulse_voltage, pulse_width_ms, num_pulses, read_voltage,
                inter_pulse_delay_s, icc, context, psu, optical,
                validate_timing, start_at_zero, return_to_zero_at_end
            )
        elif self.smu_type == 'Keithley 2450':
            return self._do_pulse_measurement_2450(
                pulse_voltage, pulse_width_ms, num_pulses, read_voltage,
                inter_pulse_delay_s, icc, context, psu, optical,
                validate_timing, start_at_zero, return_to_zero_at_end
            )
        elif self.smu_type in ['Keithley 2401', 'Keithley 2400']:
            return self._do_pulse_measurement_2400(
                pulse_voltage, pulse_width_ms, num_pulses, read_voltage,
                inter_pulse_delay_s, icc, context, psu, optical,
                validate_timing, start_at_zero, return_to_zero_at_end
            )
        else:
            return self._do_pulse_measurement_generic(
                pulse_voltage, pulse_width_ms, num_pulses, read_voltage,
                inter_pulse_delay_s, icc, context, psu, optical,
                validate_timing, start_at_zero, return_to_zero_at_end
            )
    
    def do_retention_measurement(
        self,
        set_voltage: float,
        set_time_s: float,
        read_voltage: float,
        repeat_delay_s: float,
        number: int,
        icc: float = 1e-4,
        psu=None,
        optical=None,
        led: bool = False,
        led_time_s: Optional[float] = None,
        sequence: Optional[Iterable[str]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Execute retention measurement using instrument-specific optimized method.
        
        Routes based on self.smu_type to instrument-specific implementation.
        
        Args:
            set_voltage: Voltage for set pulse (V)
            set_time_s: Duration of set pulse (s)
            read_voltage: Read voltage for sampling (V)
            repeat_delay_s: Delay between reads (s)
            number: Number of read samples
            icc: Current compliance (A)
            psu: Optional power supply for LED control
            optical: Optional optical excitation system
            led: Enable LED
            led_time_s: Optional LED duration (not used in all implementations)
            sequence: Optional LED sequence
            should_stop: Optional stop callback
            on_point: Optional callback for live plotting
            
        Returns:
            Tuple of (voltages, currents, timestamps) arrays
        """
        from Measurments.measurement_context import MeasurementContext
        from Measurments.source_modes import SourceMode
        
        context = MeasurementContext(
            led=led,
            power=1.0,
            sequence=list(sequence) if sequence else None,
            source_mode=SourceMode.VOLTAGE,
            should_stop=should_stop,
            on_point=on_point
        )
        
        # Route to instrument-specific implementation
        if self.smu_type == 'Keithley 4200A':
            return self._do_retention_measurement_4200a(
                set_voltage, set_time_s, read_voltage, repeat_delay_s,
                number, icc, context, psu, optical, led_time_s
            )
        elif self.smu_type == 'Keithley 2450':
            return self._do_retention_measurement_2450(
                set_voltage, set_time_s, read_voltage, repeat_delay_s,
                number, icc, context, psu, optical, led_time_s
            )
        elif self.smu_type in ['Keithley 2401', 'Keithley 2400']:
            return self._do_retention_measurement_2400(
                set_voltage, set_time_s, read_voltage, repeat_delay_s,
                number, icc, context, psu, optical, led_time_s
            )
        else:
            return self._do_retention_measurement_generic(
                set_voltage, set_time_s, read_voltage, repeat_delay_s,
                number, icc, context, psu, optical, led_time_s
            )
    
    def do_endurance_measurement(
        self,
        set_voltage: float,
        reset_voltage: float,
        pulse_width_s: float,
        num_cycles: int,
        read_voltage: float = 0.1,
        inter_cycle_delay_s: float = 0.0,
        icc: float = 1e-4,
        psu=None,
        optical=None,
        led: bool = False,
        power: float = 1.0,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Execute endurance measurement using instrument-specific optimized method.
        
        Routes based on self.smu_type to instrument-specific implementation.
        
        Args:
            set_voltage: Voltage for SET pulse (V)
            reset_voltage: Voltage for RESET pulse (V)
            pulse_width_s: Pulse width (s)
            num_cycles: Number of SET/RESET cycles
            read_voltage: Read voltage after each pulse (V)
            inter_cycle_delay_s: Delay between cycles (s)
            icc: Current compliance (A)
            psu: Optional power supply for LED control
            optical: Optional optical excitation system
            led: Enable LED
            power: LED power level
            should_stop: Optional stop callback
            on_point: Optional callback for live plotting
            
        Returns:
            Tuple of (voltages, currents, timestamps) arrays
        """
        from Measurments.measurement_context import MeasurementContext
        from Measurments.source_modes import SourceMode
        
        context = MeasurementContext(
            led=led,
            power=power,
            sequence=None,
            source_mode=SourceMode.VOLTAGE,
            should_stop=should_stop,
            on_point=on_point
        )
        
        # Route to instrument-specific implementation
        if self.smu_type == 'Keithley 4200A':
            return self._do_endurance_measurement_4200a(
                set_voltage, reset_voltage, pulse_width_s, num_cycles,
                read_voltage, inter_cycle_delay_s, icc, context, psu, optical
            )
        elif self.smu_type == 'Keithley 2450':
            return self._do_endurance_measurement_2450(
                set_voltage, reset_voltage, pulse_width_s, num_cycles,
                read_voltage, inter_cycle_delay_s, icc, context, psu, optical
            )
        elif self.smu_type in ['Keithley 2401', 'Keithley 2400']:
            return self._do_endurance_measurement_2400(
                set_voltage, reset_voltage, pulse_width_s, num_cycles,
                read_voltage, inter_cycle_delay_s, icc, context, psu, optical
            )
        else:
            return self._do_endurance_measurement_generic(
                set_voltage, reset_voltage, pulse_width_s, num_cycles,
                read_voltage, inter_cycle_delay_s, icc, context, psu, optical
            )
    
    def do_pulsed_iv_sweep(
        self,
        config: 'SweepConfig',
        pulse_width_ms: float,
        read_delay_ms: float,
        psu=None,
        optical=None,
        should_stop: Optional[Callable[[], bool]] = None,
        on_point: Optional[Callable[[float, float, float], None]] = None,
        validate_timing: bool = True,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Execute pulsed IV sweep using instrument-specific optimized method.
        
        Routes based on self.smu_type to instrument-specific implementation.
        
        Args:
            config: SweepConfig with sweep parameters
            pulse_width_ms: Pulse width (ms)
            read_delay_ms: Read delay after pulse (ms)
            psu: Optional power supply for LED control
            optical: Optional optical excitation system
            should_stop: Optional stop callback
            on_point: Optional callback for live plotting
            validate_timing: Validate timing constraints
            
        Returns:
            Tuple of (voltages, currents, timestamps) arrays
        """
        from Measurments.measurement_context import MeasurementContext
        from Measurments.source_modes import SourceMode
        
        context = MeasurementContext(
            led=config.led if hasattr(config, 'led') else False,
            power=config.power if hasattr(config, 'power') else 1.0,
            sequence=config.sequence if hasattr(config, 'sequence') else None,
            source_mode=config.source_mode if hasattr(config, 'source_mode') else SourceMode.VOLTAGE,
            should_stop=should_stop,
            on_point=on_point
        )
        
        # Route to instrument-specific implementation
        if self.smu_type == 'Keithley 4200A':
            return self._do_pulsed_iv_sweep_4200a(
                config, pulse_width_ms, read_delay_ms, context, psu, optical, validate_timing
            )
        elif self.smu_type == 'Keithley 2450':
            return self._do_pulsed_iv_sweep_2450(
                config, pulse_width_ms, read_delay_ms, context, psu, optical, validate_timing
            )
        elif self.smu_type in ['Keithley 2401', 'Keithley 2400']:
            return self._do_pulsed_iv_sweep_2400(
                config, pulse_width_ms, read_delay_ms, context, psu, optical, validate_timing
            )
        else:
            return self._do_pulsed_iv_sweep_generic(
                config, pulse_width_ms, read_delay_ms, context, psu, optical, validate_timing
            )
    
    # ========================================================================
    # Instrument-Specific Implementations
    # ========================================================================
    
    # 2400 implementations - Point-by-point (wraps existing patterns)
    
    def _do_iv_sweep_2400(
        self,
        config: 'SweepConfig',
        context: 'MeasurementContext',
        psu,
        optical
    ) -> Tuple[List[float], List[float], List[float]]:
        """Point-by-point IV sweep for Keithley 2400."""
        from Measurments.measurement_services_smu import MeasurementService
        from Measurments.sweep_patterns import build_sweep_values
        from Measurments.data_utils import normalize_measurement
        from Measurments.source_modes import SourceMode, apply_source, measure_result
        from Measurments.optical_controller import OpticalController
        
        # Build voltage list if not provided
        if config.voltage_list is None:
            voltage_range = build_sweep_values(
                start=config.start_v,
                stop=config.stop_v,
                step=config.step_v,
                sweep_type=config.sweep_type,
                neg_stop=config.neg_stop_v
            )
        else:
            voltage_range = config.voltage_list
        
        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []
        
        v_list = list(voltage_range) * config.sweeps
        if not v_list:
            return v_arr, c_arr, t_arr
        
        v_max = max(v_list)
        v_min = min(v_list)
        prev_v = None
        
        start_time = time.perf_counter()
        
        # Precondition instrument
        try:
            apply_source(self, context.source_mode, 0.0, config.icc)
            self.enable_output(True)
        except Exception:
            pass
        
        # Initialize optical controller
        optical_ctrl = OpticalController(optical=optical, psu=psu)
        
        sweep_idx = 0
        points_per_sweep = len(v_list) // config.sweeps if config.sweeps > 0 else len(v_list)
        
        for i, v in enumerate(v_list):
            if context.check_stop():
                break
            
            # Check if we're starting a new sweep
            if i > 0 and i % points_per_sweep == 0:
                sweep_idx += 1
            
            # Apply LED state for this sweep
            led_state = context.get_led_state_for_sweep(sweep_idx)
            try:
                optical_ctrl.set_state(led_state == '1', power=context.power)
            except Exception:
                pass
            
            # Apply source value
            try:
                apply_source(self, context.source_mode, v, config.icc)
            except Exception:
                pass
            
            time.sleep(0.1)  # Brief settle
            
            # Measure
            try:
                measurement = measure_result(self, context.source_mode)
                measurement = normalize_measurement(measurement)
            except Exception:
                measurement = float('nan')
            
            t_now = time.perf_counter() - start_time
            
            # Store based on mode
            if context.source_mode == SourceMode.VOLTAGE:
                v_arr.append(v)
                c_arr.append(measurement)
            elif context.source_mode == SourceMode.CURRENT:
                v_arr.append(measurement)
                c_arr.append(v)
            
            t_arr.append(t_now)
            
            # Call on_point callback
            if context.source_mode == SourceMode.VOLTAGE:
                context.call_on_point(v, measurement, t_now)
            else:
                context.call_on_point(measurement, v, t_now)
            
            time.sleep(max(0.0, float(config.step_delay)))
            
            # Pause at extrema
            if config.pause_s > 0:
                if (v == v_max or v == v_min) and v != prev_v:
                    try:
                        apply_source(self, context.source_mode, 0.0, config.icc)
                    except Exception:
                        pass
                    time.sleep(config.pause_s)
            prev_v = v
        
        # Cleanup
        optical_ctrl.disable()
        try:
            apply_source(self, context.source_mode, 0.0, config.icc)
            self.enable_output(False)
        except Exception:
            pass
        
        return v_arr, c_arr, t_arr
    
    def _do_pulse_measurement_2400(
        self,
        pulse_voltage: float,
        pulse_width_ms: float,
        num_pulses: int,
        read_voltage: float,
        inter_pulse_delay_s: float,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical,
        validate_timing: bool,
        start_at_zero: bool,
        return_to_zero_at_end: bool
    ) -> Tuple[List[float], List[float], List[float]]:
        """Point-by-point pulse measurement for Keithley 2400."""
        from Measurments.data_utils import safe_measure_current
        from Measurments.optical_controller import OpticalController
        
        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []
        
        # Validate timing
        if validate_timing:
            caps = self.get_capabilities()
            min_pulse_width = caps.min_step_delay_ms
            if pulse_width_ms < min_pulse_width:
                raise ValueError(
                    f"Pulse width {pulse_width_ms} ms is below minimum "
                    f"for {self.smu_type} ({min_pulse_width} ms)"
                )
        
        start_time = time.perf_counter()
        
        # Initialize optical controller
        optical_ctrl = OpticalController(optical=optical, psu=psu)
        if context.led:
            optical_ctrl.enable(context.power)
        
        try:
            if start_at_zero:
                self.set_voltage(0, icc)
            
            for pulse_idx in range(int(num_pulses)):
                if context.check_stop():
                    break
                
                # Apply LED state from sequence if provided
                led_state = context.get_led_state_for_sweep(pulse_idx) if context.sequence else None
                if led_state is not None:
                    try:
                        optical_ctrl.set_state(led_state == '1', power=context.power)
                    except Exception:
                        pass
                
                # Apply pulse
                try:
                    self.set_voltage(pulse_voltage, icc)
                except Exception:
                    pass
                
                pulse_start = time.perf_counter()
                pulse_width_s = pulse_width_ms / 1000.0
                while (time.perf_counter() - pulse_start) < pulse_width_s:
                    if context.check_stop():
                        break
                    time.sleep(0.00001)
                
                if context.check_stop():
                    break
                
                # Return to read voltage
                try:
                    self.set_voltage(read_voltage, icc)
                except Exception:
                    pass
                
                # Measure
                try:
                    current = safe_measure_current(self)
                except Exception:
                    current = float('nan')
                
                t_now = time.perf_counter() - start_time
                v_arr.append(read_voltage)
                c_arr.append(current)
                t_arr.append(t_now)
                
                context.call_on_point(read_voltage, current, t_now)
                
                # Inter-pulse delay with sampling
                if inter_pulse_delay_s > 0:
                    post_start = time.perf_counter()
                    while (time.perf_counter() - post_start) < float(inter_pulse_delay_s):
                        if context.check_stop():
                            break
                        try:
                            current_tuple = self.measure_current()
                            current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
                        except Exception:
                            current = float('nan')
                        t_now = time.perf_counter() - start_time
                        v_arr.append(read_voltage)
                        c_arr.append(current)
                        t_arr.append(t_now)
                        context.call_on_point(read_voltage, current, t_now)
        
        finally:
            optical_ctrl.disable()
            if return_to_zero_at_end:
                try:
                    self.set_voltage(0, icc)
                    self.enable_output(False)
                except Exception:
                    pass
        
        return v_arr, c_arr, t_arr
    
    def _do_retention_measurement_2400(
        self,
        set_voltage: float,
        set_time_s: float,
        read_voltage: float,
        repeat_delay_s: float,
        number: int,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical,
        led_time_s: Optional[float]
    ) -> Tuple[List[float], List[float], List[float]]:
        """Point-by-point retention measurement for Keithley 2400."""
        from Measurments.data_utils import safe_measure_current
        from Measurments.optical_controller import OpticalController
        
        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []
        
        start_t = time.perf_counter()
        
        # Initialize optical controller
        optical_ctrl = OpticalController(optical=optical, psu=psu)
        if context.led:
            optical_ctrl.enable(context.power)
        
        try:
            # Apply set pulse
            try:
                self.set_voltage(set_voltage, icc)
            except Exception:
                pass
            time.sleep(max(0.0, float(set_time_s)))
            
            # Switch to read voltage
            try:
                self.set_voltage(read_voltage, icc)
            except Exception:
                pass
            
            for i in range(int(number)):
                if context.check_stop():
                    break
                try:
                    current = safe_measure_current(self)
                except Exception:
                    current = float('nan')
                t_now = time.perf_counter() - start_t
                v_arr.append(read_voltage)
                c_arr.append(current)
                t_arr.append(t_now)
                context.call_on_point(read_voltage, current, t_now)
                time.sleep(max(0.0, float(repeat_delay_s)))
        finally:
            optical_ctrl.disable()
            try:
                self.finish_pulses(Icc=float(icc), restore_autozero=True)
            except Exception:
                pass
        
        return v_arr, c_arr, t_arr
    
    def _do_endurance_measurement_2400(
        self,
        set_voltage: float,
        reset_voltage: float,
        pulse_width_s: float,
        num_cycles: int,
        read_voltage: float,
        inter_cycle_delay_s: float,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical
    ) -> Tuple[List[float], List[float], List[float]]:
        """Point-by-point endurance measurement for Keithley 2400."""
        from Measurments.data_utils import safe_measure_current
        from Measurments.optical_controller import OpticalController
        
        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []
        start_t = time.perf_counter()
        
        try:
            self.prepare_for_pulses(Icc=float(icc), v_range=20.0, ovp=21.0,
                                    use_remote_sense=False, autozero_off=True)
        except Exception:
            pass
        
        # Optical handling
        optical_ctrl = OpticalController(optical=optical, psu=psu)
        if context.led:
            optical_ctrl.enable(context.power)
        
        try:
            for k in range(int(num_cycles)):
                if context.check_stop():
                    break
                
                # SET pulse
                try:
                    self.set_voltage(set_voltage, icc)
                except Exception:
                    pass
                time.sleep(max(0.0, float(pulse_width_s)))
                
                # Read after SET
                try:
                    self.set_voltage(read_voltage, icc)
                    time.sleep(0.002)
                    i_set_val = safe_measure_current(self)
                except Exception:
                    i_set_val = float('nan')
                t_now = time.perf_counter() - start_t
                v_arr.append(read_voltage)
                c_arr.append(i_set_val)
                t_arr.append(t_now)
                context.call_on_point(read_voltage, i_set_val, t_now)
                
                if context.check_stop():
                    break
                
                # RESET pulse
                try:
                    self.set_voltage(reset_voltage, icc)
                except Exception:
                    pass
                time.sleep(max(0.0, float(pulse_width_s)))
                
                # Read after RESET
                try:
                    self.set_voltage(read_voltage, icc)
                    time.sleep(0.002)
                    i_reset_val = safe_measure_current(self)
                except Exception:
                    i_reset_val = float('nan')
                t_now = time.perf_counter() - start_t
                v_arr.append(read_voltage)
                c_arr.append(i_reset_val)
                t_arr.append(t_now)
                context.call_on_point(read_voltage, i_reset_val, t_now)
                
                if inter_cycle_delay_s:
                    post_start = time.perf_counter()
                    while (time.perf_counter() - post_start) < float(inter_cycle_delay_s):
                        if context.check_stop():
                            break
                        try:
                            it = self.measure_current()
                            iv = it[1] if isinstance(it, (list, tuple)) and len(it) > 1 else float(it)
                        except Exception:
                            iv = float('nan')
                        t_now = time.perf_counter() - start_t
                        v_arr.append(read_voltage)
                        c_arr.append(iv)
                        t_arr.append(t_now)
                        context.call_on_point(read_voltage, iv, t_now)
        finally:
            optical_ctrl.disable()
            try:
                self.set_voltage(0, icc)
                self.enable_output(False)
            except Exception:
                pass
        
        return v_arr, c_arr, t_arr
    
    def _do_pulsed_iv_sweep_2400(
        self,
        config: 'SweepConfig',
        pulse_width_ms: float,
        read_delay_ms: float,
        context: 'MeasurementContext',
        psu,
        optical,
        validate_timing: bool
    ) -> Tuple[List[float], List[float], List[float]]:
        """Point-by-point pulsed IV sweep for Keithley 2400."""
        # Use the pulse measurement for each voltage point
        from Measurments.sweep_patterns import build_sweep_values
        
        # Build amplitude list
        if config.voltage_list is None:
            amps = build_sweep_values(
                start=config.start_v,
                stop=config.stop_v,
                step=config.step_v,
                sweep_type=config.sweep_type,
                neg_stop=config.neg_stop_v
            )
        else:
            amps = config.voltage_list
        
        v_out: List[float] = []
        i_out: List[float] = []
        t_out: List[float] = []
        t0 = time.perf_counter()
        
        # Call pulse measurement for each amplitude
        for amp in amps:
            if context.check_stop():
                break
            
            _, _i, _t = self._do_pulse_measurement_2400(
                pulse_voltage=float(amp),
                pulse_width_ms=float(pulse_width_ms),
                num_pulses=1,
                read_voltage=0.2,  # Default read voltage
                inter_pulse_delay_s=0.0,
                icc=config.icc,
                context=context,
                psu=psu,
                optical=optical,
                validate_timing=validate_timing,
                start_at_zero=True,
                return_to_zero_at_end=False
            )
            
            try:
                i_val = float(_i[-1]) if _i else float('nan')
            except Exception:
                i_val = float('nan')
            v_out.append(float(amp))
            i_out.append(i_val)
            t_out.append(time.perf_counter() - t0)
            context.call_on_point(float(amp), i_val, t_out[-1])
        
        return v_out, i_out, t_out
    
    # Generic fallback implementations (reuse 2400 point-by-point)
    
    def _do_iv_sweep_generic(
        self,
        config: 'SweepConfig',
        context: 'MeasurementContext',
        psu,
        optical
    ) -> Tuple[List[float], List[float], List[float]]:
        """Generic point-by-point IV sweep (fallback for HP4140B, etc.)."""
        return self._do_iv_sweep_2400(config, context, psu, optical)
    
    def _do_pulse_measurement_generic(
        self,
        pulse_voltage: float,
        pulse_width_ms: float,
        num_pulses: int,
        read_voltage: float,
        inter_pulse_delay_s: float,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical,
        validate_timing: bool,
        start_at_zero: bool,
        return_to_zero_at_end: bool
    ) -> Tuple[List[float], List[float], List[float]]:
        """Generic point-by-point pulse measurement."""
        return self._do_pulse_measurement_2400(
            pulse_voltage, pulse_width_ms, num_pulses, read_voltage,
            inter_pulse_delay_s, icc, context, psu, optical,
            validate_timing, start_at_zero, return_to_zero_at_end
        )
    
    def _do_retention_measurement_generic(
        self,
        set_voltage: float,
        set_time_s: float,
        read_voltage: float,
        repeat_delay_s: float,
        number: int,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical,
        led_time_s: Optional[float]
    ) -> Tuple[List[float], List[float], List[float]]:
        """Generic point-by-point retention measurement."""
        return self._do_retention_measurement_2400(
            set_voltage, set_time_s, read_voltage, repeat_delay_s,
            number, icc, context, psu, optical, led_time_s
        )
    
    def _do_endurance_measurement_generic(
        self,
        set_voltage: float,
        reset_voltage: float,
        pulse_width_s: float,
        num_cycles: int,
        read_voltage: float,
        inter_cycle_delay_s: float,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical
    ) -> Tuple[List[float], List[float], List[float]]:
        """Generic point-by-point endurance measurement."""
        return self._do_endurance_measurement_2400(
            set_voltage, reset_voltage, pulse_width_s, num_cycles,
            read_voltage, inter_cycle_delay_s, icc, context, psu, optical
        )
    
    def _do_pulsed_iv_sweep_generic(
        self,
        config: 'SweepConfig',
        pulse_width_ms: float,
        read_delay_ms: float,
        context: 'MeasurementContext',
        psu,
        optical,
        validate_timing: bool
    ) -> Tuple[List[float], List[float], List[float]]:
        """Generic point-by-point pulsed IV sweep."""
        return self._do_pulsed_iv_sweep_2400(
            config, pulse_width_ms, read_delay_ms, context, psu, optical, validate_timing
        )
    
    # 4200A implementations - C module based (TO BE IMPLEMENTED)
    
    def _do_iv_sweep_4200a(
        self,
        config: 'SweepConfig',
        context: 'MeasurementContext',
        psu,
        optical
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        C module hardware sweep for Keithley 4200A.
        
        Uses EX commands via kxci wrapper. Breaks into sub-sweeps for LED/pausing,
        retrieves data via GP commands, and calls on_point callbacks for live plotting.
        """
        from Measurments.sweep_patterns import build_sweep_values
        from Measurments.source_modes import SourceMode, apply_source
        from Measurments.optical_controller import OpticalController
        from Measurments.data_utils import normalize_measurement
        
        # Check if we have the wrapper
        if not isinstance(self.instrument, _Keithley4200A_KXCI_Wrapper):
            raise RuntimeError(
                f"4200A requires KXCI wrapper, but got {type(self.instrument)}. "
                "This should not happen - check IVControllerManager initialization."
            )
        
        kxci_wrapper = self.instrument
        kxci = kxci_wrapper.kxci
        
        # Build voltage list
        if config.voltage_list is None:
            voltage_range = build_sweep_values(
                start=config.start_v,
                stop=config.stop_v,
                step=config.step_v,
                sweep_type=config.sweep_type,
                neg_stop=config.neg_stop_v
            )
        else:
            voltage_range = config.voltage_list
        
        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []
        
        v_list = list(voltage_range)
        if not v_list:
            return v_arr, c_arr, t_arr
        
        # Check if we need fine-grained control
        # For LED/pausing, fall back to point-by-point
        num_sweep_points = len(v_list)
        
        needs_fine_control = (
            (context.sequence is not None and len(context.sequence) > 0) or  # LED sequence
            config.pause_s > 0  # Pausing needed
            # Note: Multiple sweeps (config.sweeps > 1) is supported by C module via NumCycles
            # Only need fine control if LED sequence or pausing is required
        )
        
        # Debug: Check which mode we're using
        # Check if we should use EX command batch mode
        print(f"  - Num sweep points: {num_sweep_points}")
        print(f"  - Has LED sequence: {context.sequence is not None and len(context.sequence) > 0}")
        print(f"  - Pause duration: {config.pause_s}s")
        print(f"  - Num sweeps: {config.sweeps}")
        print(f"  - Needs fine control: {needs_fine_control}")
        
        # Fall back to point-by-point for fine-grained control
        # TODO: Implement sub-sweep breaking for LED/pausing with C modules
        if needs_fine_control:
            # Fall back to point-by-point mode
            return self._do_iv_sweep_2400(config, context, psu, optical)
        
        # Acquire lock to prevent concurrent EX commands (only one EX command at a time)
        # Do this AFTER checking if we need fine control, so we don't hold the lock unnecessarily
        if not kxci_wrapper._ex_command_lock.acquire(blocking=False):
            raise RuntimeError(
                "4200A EX command already in progress. Please wait for the current measurement to complete."
            )
        
        # Initialize optical controller early so it's always available in finally block
        optical_ctrl = OpticalController(optical=optical, psu=psu)
        
        try:
            
            # Using EX command batch mode (4200A C module)
            
            # Check instrument limits
            caps = self.get_capabilities()
            if config.step_delay * 1000 < caps.min_step_delay_ms:
                raise ValueError(
                    f"Step delay {config.step_delay*1000} ms is below minimum "
                    f"for {self.smu_type} ({caps.min_step_delay_ms} ms)"
                )
            
            # Determine sweep parameters for C module
            # The C module does (0 → Vhigh → 0 → Vlow → 0) pattern per cycle
            # Steps are distributed across the full sweep path
            
            if config.sweep_type in ["FS", "FULL"]:
                # Full sweep: 0 → stop_v → 0 → neg_stop_v → 0
                vhigh = abs(config.stop_v)
                vlow = -abs(config.neg_stop_v if config.neg_stop_v is not None else config.stop_v)
                num_cycles = config.sweeps
            elif config.sweep_type == "PS":
                # Positive sweep: 0 → stop_v → 0 (vlow=0 means only positive)
                vhigh = abs(config.stop_v)
                vlow = 0.0  # Only sweep positive
                num_cycles = config.sweeps
            elif config.sweep_type == "NS":
                # Negative sweep: 0 → -stop_v → 0
                vhigh = 0.0  # Start at 0
                vlow = -abs(config.stop_v)
                num_cycles = config.sweeps
            elif config.sweep_type == "Triangle":
                # Triangle: 0 → stop_v → 0 → neg_stop_v → 0
                vhigh = abs(config.stop_v)
                vlow = -abs(config.neg_stop_v if config.neg_stop_v is not None else config.stop_v)
                num_cycles = config.sweeps
            else:
                # Default to full sweep
                vhigh = abs(config.stop_v)
                vlow = -abs(config.neg_stop_v if config.neg_stop_v is not None else config.stop_v)
                num_cycles = config.sweeps
            
            # Calculate number of steps from step_v
            # The C module distributes steps across the full path (0→Vhigh→0→Vlow→0)
            # We need to calculate how many steps fit in the voltage range
            if config.step_v > 0:
                # Calculate steps based on step size
                # Full path length = |Vhigh| + |Vhigh| + |Vlow| + |Vlow| = 2*(|Vhigh| + |Vlow|)
                total_path_length = 2 * (abs(vhigh) + abs(vlow))
                if total_path_length > 0:
                    num_steps = max(4, int(total_path_length / config.step_v))
                else:
                    num_steps = 4  # Minimum steps
            else:
                # If no step_v specified, use a reasonable default
                num_steps = 20
            
            # Ensure num_steps is within valid range
            num_steps = max(4, min(num_steps, 10000))
            
            # Calculate total points: (NumSteps + 1) × NumCycles
            points_per_cycle = num_steps + 1
            num_points = points_per_cycle * num_cycles
            
            # Ensure we don't exceed max points
            if num_points > caps.max_points_per_sweep:
                max_points_per_cycle = caps.max_points_per_sweep // num_cycles
                max_steps = max_points_per_cycle - 1
                raise ValueError(
                    f"Requested {num_steps} steps × {num_cycles} cycles ({num_points} points) exceeds maximum "
                    f"for {self.smu_type} ({caps.max_points_per_sweep} points). "
                    f"Maximum steps per cycle: {max_steps}"
                )
            
            # Get build_ex_command function from wrapper (already imported)
            build_ex_command = kxci_wrapper._build_ex_command
            
            # Enable optical controller if needed (works for both LED and Laser)
            # The OpticalController automatically handles both LED (via PSU) and Laser (via optical)
            if context.led:
                optical_ctrl.enable(context.power)
            
            start_time = time.perf_counter()
            
            try:
                # Ensure connected
                kxci_wrapper._ensure_connection()
                
                # Enter UL mode
                was_in_ul = kxci._ul_mode_active
                if not was_in_ul:
                    if not kxci._enter_ul_mode():
                        raise RuntimeError("Failed to enter UL mode for 4200A sweep")
                
                try:
                    # Build EX command
                    step_delay = config.step_delay  # Use step_delay
                    integration_time = 0.01  # 0.01 PLC (default)
                    
                    command = build_ex_command(
                        vhigh=vhigh,
                        vlow=vlow,
                        num_steps=num_steps,
                        num_cycles=num_cycles,
                        num_points=num_points,
                        step_delay=step_delay,
                        ilimit=config.icc,
                        integration_time=integration_time,
                        clarius_debug=0
                    )
                    
                    # Calculate wait time based on sweep parameters
                    time_per_point = step_delay + (integration_time * 0.01)  # Rough: 1 PLC ≈ 0.01s
                    estimated_time = num_points * time_per_point
                    wait_time = max(2.0, estimated_time * 1.5)  # Minimum 2s, add 50% safety margin
                    
                    # Execute EX command with calculated wait time
                    # IMPORTANT: Ensure we're in UL mode before executing
                    if not kxci._ul_mode_active:
                        kxci._enter_ul_mode()
                        time.sleep(0.1)
                    
                    return_value, error_msg = kxci._execute_ex_command(command, wait_seconds=wait_time)
                    if error_msg:
                        raise RuntimeError(f"4200A EX command failed: {error_msg}")
                    
                    # Check return value (0 = success for smu_ivsweep)
                    if return_value is not None and return_value != 0:
                        if return_value < 0:
                            error_messages = {
                                -1: "Invalid Vhigh (must be >= 0) or Vlow (must be <= 0)",
                                -2: "NumIPoints != NumVPoints (array size mismatch)",
                                -3: "NumIPoints != (NumSteps + 1) × NumCycles (array size mismatch)",
                                -4: "Invalid array sizes (NumIPoints or NumVPoints < NumSteps + 1)",
                                -5: "Invalid NumSteps (must be >= 4 and <= 10000) or NumCycles (must be >= 1 and <= 1000)",
                                -6: "limiti() failed (check current limit value)",
                                -7: "measi() failed (check SMU connection)",
                            }
                            msg = error_messages.get(return_value, f"Unknown error code: {return_value}")
                            raise RuntimeError(f"4200A EX command returned error code: {return_value} - {msg}")
                        else:
                            raise RuntimeError(f"4200A EX command returned unexpected value: {return_value} (expected 0)")
                    
                    # Additional wait to ensure EX command is fully complete and data arrays are written
                    time.sleep(0.5)  # Give C module time to write data to output arrays
                    
                    # Ensure we're still in UL mode for GP commands (smu_ivsweep requires UL mode for GP)
                    if not kxci._ul_mode_active:
                        kxci._enter_ul_mode()
                        time.sleep(0.1)
                    
                    # Retrieve data via GP commands
                    # GP parameter positions: 1=Vhigh, 2=Vlow, 3=NumSteps, 4=NumCycles, 5=Imeas, 6=NumIPoints, 7=Vforce, ...
                    def try_query_gp(param: int, name: str, try_ul_mode: bool = True) -> List[float]:
                        """Try querying GP parameter, first in current mode, then try switching modes if needed."""
                        # First try in current mode
                        try:
                            data = kxci._query_gp(param, num_points)
                            if len(data) > 0:
                                return data
                        except Exception as e:
                            pass  # Silently try alternative mode
                        
                        # If that failed, try switching modes
                        if try_ul_mode and not kxci._ul_mode_active:
                            try:
                                kxci._enter_ul_mode()
                                time.sleep(0.1)
                                data = kxci._query_gp(param, num_points)
                                if len(data) > 0:
                                    return data
                            except Exception:
                                pass
                        elif not try_ul_mode and kxci._ul_mode_active:
                            try:
                                kxci._exit_ul_mode()
                                time.sleep(0.2)
                                data = kxci._query_gp(param, num_points)
                                if len(data) > 0:
                                    return data
                            except Exception:
                                pass
                        
                        return []
                    
                    # Query voltage and current
                    vforce = try_query_gp(7, "Vforce", try_ul_mode=True)
                    if len(vforce) == 0:
                        vforce = try_query_gp(7, "Vforce", try_ul_mode=False)
                    
                    imeas = try_query_gp(5, "Imeas", try_ul_mode=True)
                    if len(imeas) == 0:
                        imeas = try_query_gp(5, "Imeas", try_ul_mode=False)
                    
                    if len(vforce) == 0 or len(imeas) == 0:
                        raise RuntimeError(
                            f"Failed to retrieve data: vforce={len(vforce)} points, imeas={len(imeas)} points"
                        )
                    
                    if len(vforce) != len(imeas):
                        # Trim to minimum length
                        min_len = min(len(vforce), len(imeas))
                        vforce = vforce[:min_len]
                        imeas = imeas[:min_len]
                    
                    # Data retrieved successfully (no verbose output)
                    
                    # Process data and call on_point callbacks for live plotting
                    measurement_duration = time.perf_counter() - start_time
                    
                    for i, (v, i_meas) in enumerate(zip(vforce, imeas)):
                        if context.check_stop():
                            break
                        
                        # Normalize current measurement
                        try:
                            i_val = normalize_measurement(i_meas)
                        except Exception:
                            i_val = float('nan')
                        
                        # Estimate timestamp (uniform distribution over measurement duration)
                        t_est = measurement_duration * i / max(1, len(vforce) - 1)
                        
                        v_arr.append(float(v))
                        c_arr.append(float(i_val))
                        t_arr.append(t_est)
                        
                        # Call on_point callback for live plotting
                        context.call_on_point(float(v), float(i_val), t_est)
                    
                except Exception as e:
                    # Re-raise exceptions from EX command execution
                    raise
                finally:
                    # Ensure we're out of UL mode
                    if not was_in_ul and kxci._ul_mode_active:
                        kxci._exit_ul_mode()
            
            except Exception as e:
                # Re-raise exceptions from inner try
                raise
        finally:
            # Cleanup optical
            optical_ctrl.disable()
            
            # Return to 0V
            try:
                apply_source(self, context.source_mode, 0.0, config.icc)
                self.enable_output(False)
            except Exception:
                pass
            
            # Release lock to allow next EX command
            kxci_wrapper._ex_command_lock.release()
        
        return v_arr, c_arr, t_arr
    
    def _do_pulse_measurement_4200a(
        self,
        pulse_voltage: float,
        pulse_width_ms: float,
        num_pulses: int,
        read_voltage: float,
        inter_pulse_delay_s: float,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical,
        validate_timing: bool,
        start_at_zero: bool,
        return_to_zero_at_end: bool
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        C module pulse measurement for Keithley 4200A.
        
        Uses SMU_pulse_measure C module. For multiple pulses with LED sequences,
        loops through pulses with LED control between pulses.
        """
        from Measurments.data_utils import safe_measure_current, normalize_measurement
        from Measurments.optical_controller import OpticalController
        
        # Check if we have the wrapper
        if not isinstance(self.instrument, _Keithley4200A_KXCI_Wrapper):
            raise RuntimeError(
                f"4200A requires KXCI wrapper, but got {type(self.instrument)}."
            )
        
        kxci_wrapper = self.instrument
        kxci = kxci_wrapper.kxci
        
        # Acquire lock to prevent concurrent EX commands (only one EX command at a time)
        if not kxci_wrapper._ex_command_lock.acquire(blocking=False):
            raise RuntimeError(
                "4200A EX command already in progress. Please wait for the current measurement to complete."
            )
        
        try:
            # Validate timing
            if validate_timing:
                caps = self.get_capabilities()
                min_pulse_width = caps.min_step_delay_ms
                if pulse_width_ms < min_pulse_width:
                    raise ValueError(
                        f"Pulse width {pulse_width_ms} ms is below minimum "
                        f"for {self.smu_type} ({min_pulse_width} ms)"
                    )
            
            v_arr: List[float] = []
            c_arr: List[float] = []
            t_arr: List[float] = []
            
            start_time = time.perf_counter()
            
            # Initialize optical controller
            optical_ctrl = OpticalController(optical=optical, psu=psu)
            
            # Helper function to format parameters for EX command
            def format_param(value: float) -> str:
                """Format parameter for EX command (scientific notation)."""
                if abs(value) < 1e-3 or abs(value) > 1e3:
                    return f"{value:.6E}"
                return f"{value:.6f}"
            
            try:
                # Ensure connected
                kxci_wrapper._ensure_connection()
                
                # Initialize pulse measurement module (once at start)
                was_in_ul = kxci._ul_mode_active
                if not was_in_ul:
                    if not kxci._enter_ul_mode():
                        raise RuntimeError("Failed to enter UL mode for 4200A pulse measurement")
                
                try:
                    # Initialize SMU_pulse_measure module
                    init_command = (
                        f"EX Labview_Controlled_Programs_Kemp "
                        f"SMU_pulse_measure(1,0,{format_param(1e-4)},{format_param(0.0)},"
                        f"{format_param(icc)},{format_param(icc)},)"
                    )
                    return_value, error = kxci._execute_ex_command(init_command, wait_seconds=0.5)
                    if error:
                        raise RuntimeError(f"4200A pulse initialization failed: {error}")
                    
                    # Execute pulses
                    pulse_width_s = pulse_width_ms / 1000.0
                    
                    for pulse_idx in range(int(num_pulses)):
                        if context.check_stop():
                            break
                        
                        # Apply LED state from sequence if provided
                        led_state = context.get_led_state_for_sweep(pulse_idx) if context.sequence else None
                        if led_state is not None:
                            try:
                                optical_ctrl.set_state(led_state == '1', power=context.power)
                            except Exception:
                                pass
                        
                        # Execute pulse measurement
                        # SMU_pulse_measure(initialize=0, logMessages, widthTime, Amplitude, Irange, Icomp, measResistance)
                        pulse_command = (
                            f"EX Labview_Controlled_Programs_Kemp "
                            f"SMU_pulse_measure(0,0,{format_param(pulse_width_s)},"
                            f"{format_param(pulse_voltage)},{format_param(icc)},{format_param(icc)},)"
                        )
                        
                        return_value, error = kxci._execute_ex_command(pulse_command, wait_seconds=pulse_width_s + 0.1)
                        if error:
                            raise RuntimeError(f"4200A pulse execution failed: {error}")
                        if return_value is not None and return_value != 0:
                            raise RuntimeError(f"4200A pulse returned error code: {return_value} (expected 0)")
                        
                        # For now, use read_voltage for measurement after pulse
                        # TODO: Retrieve actual measured data from C module if available
                        # For now, fall back to setting read voltage and measuring
                        kxci._exit_ul_mode()
                        time.sleep(0.03)
                        
                        try:
                            # Set to read voltage and measure
                            self.set_voltage(read_voltage, icc)
                            time.sleep(0.01)  # Brief settle
                            current = safe_measure_current(self)
                            current = normalize_measurement(current)
                        except Exception:
                            current = float('nan')
                        
                        t_now = time.perf_counter() - start_time
                        v_arr.append(read_voltage)
                        c_arr.append(current)
                        t_arr.append(t_now)
                        context.call_on_point(read_voltage, current, t_now)
                        
                        # Re-enter UL mode for next pulse
                        if pulse_idx < num_pulses - 1:  # Don't re-enter after last pulse
                            if not kxci._enter_ul_mode():
                                raise RuntimeError("Failed to re-enter UL mode for next pulse")
                        
                        # Inter-pulse delay (sample at read voltage)
                        if inter_pulse_delay_s > 0 and pulse_idx < num_pulses - 1:
                            post_start = time.perf_counter()
                            while (time.perf_counter() - post_start) < float(inter_pulse_delay_s):
                                if context.check_stop():
                                    break
                                try:
                                    current_tuple = self.measure_current()
                                    current = current_tuple[1] if isinstance(current_tuple, (list, tuple)) and len(current_tuple) > 1 else float(current_tuple)
                                    current = normalize_measurement(current)
                                except Exception:
                                    current = float('nan')
                                t_now = time.perf_counter() - start_time
                                v_arr.append(read_voltage)
                                c_arr.append(current)
                                t_arr.append(t_now)
                                context.call_on_point(read_voltage, current, t_now)
                
                except Exception as e:
                    # Re-raise exceptions from pulse measurement
                    raise
                finally:
                    # Exit UL mode
                    if not was_in_ul and kxci._ul_mode_active:
                        kxci._exit_ul_mode()
            
            except Exception as e:
                # Re-raise exceptions from outer try
                raise
        finally:
            optical_ctrl.disable()
            if return_to_zero_at_end:
                try:
                    self.set_voltage(0, icc)
                    self.enable_output(False)
                except Exception:
                    pass
            
            # Release lock to allow next EX command
            kxci_wrapper._ex_command_lock.release()
        
        return v_arr, c_arr, t_arr
    
    def _do_retention_measurement_4200a(
        self,
        set_voltage: float,
        set_time_s: float,
        read_voltage: float,
        repeat_delay_s: float,
        number: int,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical,
        led_time_s: Optional[float]
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Retention measurement for Keithley 4200A.
        
        For now, uses point-by-point implementation. Can be optimized with
        C modules in the future if a suitable retention C module exists.
        """
        # Fall back to point-by-point for now
        # TODO: Implement using C modules if available
        return self._do_retention_measurement_2400(
            set_voltage, set_time_s, read_voltage, repeat_delay_s,
            number, icc, context, psu, optical, led_time_s
        )
    
    def _do_endurance_measurement_4200a(
        self,
        set_voltage: float,
        reset_voltage: float,
        pulse_width_s: float,
        num_cycles: int,
        read_voltage: float,
        inter_cycle_delay_s: float,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Endurance measurement for Keithley 4200A.
        
        Uses point-by-point implementation with pulse measurements.
        Can be optimized with C modules in the future.
        """
        # Fall back to point-by-point for now
        # TODO: Implement using C modules if available (smu_endurance or similar)
        return self._do_endurance_measurement_2400(
            set_voltage, reset_voltage, pulse_width_s, num_cycles,
            read_voltage, inter_cycle_delay_s, icc, context, psu, optical
        )
    
    def _do_pulsed_iv_sweep_4200a(
        self,
        config: 'SweepConfig',
        pulse_width_ms: float,
        read_delay_ms: float,
        context: 'MeasurementContext',
        psu,
        optical,
        validate_timing: bool
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Pulsed IV sweep for Keithley 4200A.
        
        Uses pulse measurement for each voltage point in the sweep.
        """
        from Measurments.sweep_patterns import build_sweep_values
        
        # Build amplitude list
        if config.voltage_list is None:
            amps = build_sweep_values(
                start=config.start_v,
                stop=config.stop_v,
                step=config.step_v,
                sweep_type=config.sweep_type,
                neg_stop=config.neg_stop_v
            )
        else:
            amps = config.voltage_list
        
        v_out: List[float] = []
        i_out: List[float] = []
        t_out: List[float] = []
        t0 = time.perf_counter()
        
        # Call pulse measurement for each amplitude
        for amp in amps:
            if context.check_stop():
                break
            
            _, _i, _t = self._do_pulse_measurement_4200a(
                pulse_voltage=float(amp),
                pulse_width_ms=float(pulse_width_ms),
                num_pulses=1,
                read_voltage=0.2,  # Default read voltage (could use config if available)
                inter_pulse_delay_s=0.0,
                icc=config.icc,
                context=context,
                psu=psu,
                optical=optical,
                validate_timing=validate_timing,
                start_at_zero=True,
                return_to_zero_at_end=False
            )
            
            try:
                i_val = float(_i[-1]) if _i else float('nan')
            except Exception:
                i_val = float('nan')
            v_out.append(float(amp))
            i_out.append(i_val)
            t_out.append(time.perf_counter() - t0)
            context.call_on_point(float(amp), i_val, t_out[-1])
        
        return v_out, i_out, t_out
    
    # 2450 implementations - TSP based (TO BE IMPLEMENTED)
    
    def _do_iv_sweep_2450(
        self,
        config: 'SweepConfig',
        context: 'MeasurementContext',
        psu,
        optical
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        TSP script sweep for Keithley 2450.
        
        Uses TSP scripts when beneficial, streams output for live plotting.
        Falls back to point-by-point when LED/pausing needed.
        """
        from Measurments.sweep_patterns import build_sweep_values
        from Measurments.source_modes import SourceMode, apply_source
        from Measurments.optical_controller import OpticalController
        from Measurments.data_utils import normalize_measurement
        import pyvisa
        
        # Check if LED sequence or pausing needed - fall back to point-by-point
        needs_fine_control = (
            (context.sequence is not None and len(context.sequence) > 0) or
            config.pause_s > 0 or
            config.sweeps > 1  # Multiple sweeps with different LED states
        )
        
        if needs_fine_control:
            # Fall back to point-by-point for fine control
            return self._do_iv_sweep_2400(config, context, psu, optical)
        
        # Check if controller supports TSP
        if not hasattr(self.instrument, 'device') or self.instrument.device is None:
            raise RuntimeError("2450 device not available")
        
        # Build voltage list
        if config.voltage_list is None:
            voltage_range = build_sweep_values(
                start=config.start_v,
                stop=config.stop_v,
                step=config.step_v,
                sweep_type=config.sweep_type,
                neg_stop=config.neg_stop_v
            )
        else:
            voltage_range = config.voltage_list
        
        v_list = list(voltage_range)
        if not v_list:
            return [], [], []
        
        # Check instrument limits
        caps = self.get_capabilities()
        if config.step_delay * 1000 < caps.min_step_delay_ms:
            raise ValueError(
                f"Step delay {config.step_delay*1000} ms is below minimum "
                f"for {self.smu_type} ({caps.min_step_delay_ms} ms)"
            )
        
        v_arr: List[float] = []
        c_arr: List[float] = []
        t_arr: List[float] = []
        
        start_time = time.perf_counter()
        
        # Initialize optical controller
        optical_ctrl = OpticalController(optical=optical, psu=psu)
        if context.led:
            optical_ctrl.enable(context.power)
        
        try:
            # Build TSP script for sweep
            # Determine source mode
            if context.source_mode == SourceMode.VOLTAGE:
                source_func = "smu.FUNC_DC_VOLTAGE"
                measure_func = "smu.FUNC_DC_CURRENT"
            else:
                source_func = "smu.FUNC_DC_CURRENT"
                measure_func = "smu.FUNC_DC_VOLTAGE"
            
            # Build voltage list as TSP array
            v_list_str = "{" + ",".join([f"{v:.9g}" for v in v_list]) + "}"
            delay_ms = int(config.step_delay * 1000)  # Convert to milliseconds
            
            # Build TSP script
            if context.source_mode == SourceMode.VOLTAGE:
                # Voltage source mode
                tsp_script = f"""
smu.source.func = smu.FUNC_DC_VOLTAGE
smu.source.autorangev = smu.AUTORANGE_ON
smu.source.autorangei = smu.AUTORANGE_ON
smu.source.limiti = {config.icc}
smu.measure.func = smu.FUNC_DC_CURRENT
smu.source.output = smu.ON

local vlist = {v_list_str}
local delayval = {delay_ms}

for i = 1, #vlist do
    smu.source.levelv = vlist[i]
    delayN(delayval)
    local measV = smu.measure.read(smu.FUNC_DC_VOLTAGE)
    local measI = smu.measure.read(smu.FUNC_DC_CURRENT)
    print(string.format('DATA:%0.9g,%0.12g', measV, measI))
end

smu.source.output = smu.OFF
print('SWEEP_DONE')
"""
            else:
                # Current source mode
                tsp_script = f"""
smu.source.func = smu.FUNC_DC_CURRENT
smu.source.autorangev = smu.AUTORANGE_ON
smu.source.autorangei = smu.AUTORANGE_ON
smu.source.vlimit.level = {config.icc}
smu.measure.func = smu.FUNC_DC_VOLTAGE
smu.source.output = smu.ON

local ilist = {v_list_str}
local delayval = {delay_ms}

for i = 1, #ilist do
    smu.source.leveli = ilist[i]
    delayN(delayval)
    local measV = smu.measure.read(smu.FUNC_DC_VOLTAGE)
    local measI = smu.measure.read(smu.FUNC_DC_CURRENT)
    print(string.format('DATA:%0.9g,%0.12g', measV, measI))
end

smu.source.output = smu.OFF
print('SWEEP_DONE')
"""
            
            # Execute TSP script with streaming output
            device = self.instrument.device
            original_timeout = device.timeout
            
            try:
                # Set timeout for sweep
                estimated_time = len(v_list) * config.step_delay + 5.0
                device.timeout = int(estimated_time * 1000)
                
                # Clear buffer
                device.write('*CLS')
                
                # Send TSP script line by line
                script_lines = [line.strip() for line in tsp_script.strip().split('\n') 
                               if line.strip() and not line.strip().startswith('--')]
                
                for line in script_lines:
                    device.write(line)
                
                # Small delay to let script start
                time.sleep(0.05)
                
                # Read output and parse DATA lines for live plotting
                max_reads = len(v_list) * 2  # Allow some margin
                for read_idx in range(max_reads):
                    try:
                        line = device.read().strip()
                        
                        if 'DATA:' in line:
                            # Parse data line: DATA:v,i
                            payload = line.split('DATA:')[1].strip()
                            parts = payload.split(',')
                            if len(parts) >= 2:
                                v_meas = float(parts[0])
                                i_meas = float(parts[1])
                                
                                # Normalize measurement
                                try:
                                    i_val = normalize_measurement(i_meas)
                                except Exception:
                                    i_val = float('nan')
                                
                                t_now = time.perf_counter() - start_time
                                
                                # Store based on source mode
                                # TSP script returns: measV, measI
                                # For voltage source: measV is source voltage, measI is measured current
                                # For current source: measV is measured voltage, measI is source current
                                if context.source_mode == SourceMode.VOLTAGE:
                                    # Sourcing voltage, measuring current
                                    v_arr.append(v_meas)  # Use measured voltage (should match source)
                                    c_arr.append(i_val)
                                    context.call_on_point(v_meas, i_val, t_now)
                                else:
                                    # Sourcing current, measuring voltage
                                    v_arr.append(v_meas)  # Measured voltage
                                    c_arr.append(i_meas)  # Source current
                                    context.call_on_point(v_meas, i_meas, t_now)
                                
                                t_arr.append(t_now)
                                
                                if context.check_stop():
                                    break
                        
                        elif 'SWEEP_DONE' in line or 'DONE' in line:
                            break
                    
                    except (pyvisa.errors.VisaIOError, pyvisa.errors.VI_ERROR_TMO):
                        # Timeout - may have finished
                        break
            
            finally:
                device.timeout = original_timeout
        
        finally:
            optical_ctrl.disable()
            try:
                apply_source(self, context.source_mode, 0.0, config.icc)
                self.enable_output(False)
            except Exception:
                pass
        
        return v_arr, c_arr, t_arr
    
    def _do_pulse_measurement_2450(
        self,
        pulse_voltage: float,
        pulse_width_ms: float,
        num_pulses: int,
        read_voltage: float,
        inter_pulse_delay_s: float,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical,
        validate_timing: bool,
        start_at_zero: bool,
        return_to_zero_at_end: bool
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Pulse measurement for Keithley 2450.
        
        Uses point-by-point implementation. Can be optimized with TSP scripts
        in the future for faster pulse sequences.
        """
        # Use point-by-point for now
        # TODO: Implement using TSP scripts for faster pulse sequences if beneficial
        return self._do_pulse_measurement_2400(
            pulse_voltage, pulse_width_ms, num_pulses, read_voltage,
            inter_pulse_delay_s, icc, context, psu, optical,
            validate_timing, start_at_zero, return_to_zero_at_end
        )
    
    def _do_retention_measurement_2450(
        self,
        set_voltage: float,
        set_time_s: float,
        read_voltage: float,
        repeat_delay_s: float,
        number: int,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical,
        led_time_s: Optional[float]
    ) -> Tuple[List[float], List[float], List[float]]:
        """Point-by-point retention measurement for Keithley 2450."""
        # 2450 retention can use point-by-point
        return self._do_retention_measurement_2400(
            set_voltage, set_time_s, read_voltage, repeat_delay_s,
            number, icc, context, psu, optical, led_time_s
        )
    
    def _do_endurance_measurement_2450(
        self,
        set_voltage: float,
        reset_voltage: float,
        pulse_width_s: float,
        num_cycles: int,
        read_voltage: float,
        inter_cycle_delay_s: float,
        icc: float,
        context: 'MeasurementContext',
        psu,
        optical
    ) -> Tuple[List[float], List[float], List[float]]:
        """Point-by-point endurance measurement for Keithley 2450."""
        # 2450 endurance can use point-by-point
        return self._do_endurance_measurement_2400(
            set_voltage, reset_voltage, pulse_width_s, num_cycles,
            read_voltage, inter_cycle_delay_s, icc, context, psu, optical
        )
    
    def _do_pulsed_iv_sweep_2450(
        self,
        config: 'SweepConfig',
        pulse_width_ms: float,
        read_delay_ms: float,
        context: 'MeasurementContext',
        psu,
        optical,
        validate_timing: bool
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Pulsed IV sweep for Keithley 2450.
        
        Uses pulse measurement for each voltage point.
        """
        # Use point-by-point pulsed sweep implementation
        return self._do_pulsed_iv_sweep_2400(
            config, pulse_width_ms, read_delay_ms, context, psu, optical, validate_timing
        )