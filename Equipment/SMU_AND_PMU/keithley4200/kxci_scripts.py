"""KXCI-based testing scripts for Keithley 4200A-SCS.

Purpose:
--------
This module provides a unified interface for running memristor device tests on the
Keithley 4200A-SCS using KXCI (Keithley eXternal Control Interface). It wraps
existing C modules (pmu_retention_dual_channel, readtrain_dual_channel) into
test methods that match the interface of keithley2450_tsp_scripts.py.

The module enables:
- Direct script wrappers: Tests that map to single C module calls
- Multi-script composition: Tests that call C modules multiple times with different parameters
- Data format normalization: Output matches 2450 format for GUI compatibility

Usage:
------
    from keithley4200_kxci_scripts import Keithley4200_KXCI_Scripts
    
    scripts = Keithley4200_KXCI_Scripts(gpib_address="GPIB0::17::INSTR")
    results = scripts.pulse_read_repeat(
        pulse_voltage=1.5,
        pulse_width=1e-3,  # 1ms in seconds
        read_voltage=0.2,
        delay_between=10e-3,  # 10ms in seconds
        num_cycles=10,
        clim=100e-6
    )
    
    # Results format matches 2450:
    # {
    #     'timestamps': List[float],
    #     'voltages': List[float],
    #     'currents': List[float],
    #     'resistances': List[float]
    # }

See Also:
---------
- keithley2450_tsp_scripts.py: Similar interface for Keithley 2450
- run_pmu_retention.py: Original retention measurement script
- run_readtrain_dual_channel.py: Original readtrain script

IMPORTANT LIMITATIONS - C Module Constraints:
-----------------------------------------------
The underlying C modules (pmu_retention_dual_channel, pmu_pulse_read_interleaved,
pmu_potentiation_depression) have been updated with enhanced capabilities:

1. Maximum Points: 1,000,000 points per channel (updated from 30,000)
   - The C modules now support up to 1,000,000 points per channel
   - Python validation allows up to 1,000,000 points
   - This enables much longer measurements and higher sampling rates

2. Minimum Sampling Rate: 200,000 samples/second (200 kHz)
   - The C modules require rate >= 200000 samples/sec (hardware minimum)
   - This is calculated as: min_rate = 200000000 / 1000

3. Maximum Measurement Time: ~5,000 seconds (at minimum rate)
   - Calculated from: max_time = 1,000,000 points / 200,000 samples/sec = 5 seconds
   - For longer measurements, the sample rate is automatically reduced
   - The system dynamically selects optimal rate based on total time and max_points

4. Dynamic Rate Selection:
   - The C modules now use enhanced rate selection (ret_getRateWithMinSeg)
   - Automatically adapts to short segments (high rates up to 200 MHz)
   - Automatically adapts to long waveforms (lower rates to fit max_points)
   - Ensures at least 5 samples per segment for accuracy

5. Sample Rate Calculation:
   - The system automatically selects optimal sample rate based on:
     * Total waveform time (determines minimum rate needed)
     * Maximum allowed points (max_points limits total data)
     * Shortest segment time (constrains maximum rate)
   - Algorithm: Starts at 200 MHz, reduces if needed to fit within max_points
   - For very short segments (e.g., 100ns): rate is constrained to ensure
     at least 5 samples per segment: max_rate = 5 / min_segment_time

6. How max_points Works:
   - The max_points parameter controls maximum data samples collected per channel
   - Required points = total_time × sample_rate + 2
   - If required_points > max_points, rate is lowered until fit
   - Higher max_points: allows longer waveforms or higher rates (more memory)
   - Lower max_points: faster transfer, less memory (may force lower rates)

These enhancements are implemented in:
- pmu_pulse_read_interleaved.c: Enhanced rate selection with minimum segment time
- pmu_potentiation_depression.c: Enhanced rate selection with minimum segment time
- retention_pulse_ilimit_dual_channel.c: Updated max_pts to 1,000,000
"""

from __future__ import annotations

import re
import time
import math
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple, Callable


# ═══════════════════════════════════════════════════════════════════════════════
# AVAILABLE TEST FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
#
# NOTE: All functions above use PMU (Pulse Measure Unit) unless otherwise noted.
# For very slow pulses (milliseconds to seconds), see SMU functions at the bottom.
#
# 📋 BASIC PULSE-READ PATTERNS
# ────────────────────────────────────────────────────────────────────────────────
# 1. pulse_read_repeat()
#    Pattern: (Pulse → Read → Delay) × N
#    Use: Basic pulse response, immediate read after each pulse
#    Params: pulse_voltage, pulse_width, read_voltage, delay_between, num_cycles, clim
#
# 2. multi_pulse_then_read()
#    Pattern: (Pulse×N → Read×M) × Cycles
#    Use: Multiple pulses then multiple reads per cycle
#    Params: pulse_voltage, num_pulses_per_read, pulse_width, delay_between_pulses,
#            read_voltage, num_reads, delay_between_reads, num_cycles, delay_between_cycles, clim
#
# 🧠 MEMRISTOR / RRAM TESTS
# ────────────────────────────────────────────────────────────────────────────────
# 3. potentiation_only()
#    Pattern: Initial Read → Repeated SET pulses with reads
#    Use: Gradual conductance increase, weight potentiation
#    Params: set_voltage, pulse_width, read_voltage, num_pulses, delay_between,
#            num_post_reads, post_read_interval, num_cycles, delay_between_cycles, clim
#
# 4. depression_only()
#    Pattern: Initial Read → Repeated RESET pulses with reads
#    Use: Gradual conductance decrease, weight depression
#    Params: reset_voltage, pulse_width, read_voltage, num_pulses, delay_between,
#            num_post_reads, post_read_interval, num_cycles, delay_between_cycles, clim
#
# 5. potentiation_depression_cycle()
#    Pattern: Initial Read → (Gradual SET → Gradual RESET) × N cycles
#    Use: Synaptic weight update, neuromorphic applications
#    Params: set_voltage, reset_voltage, pulse_width, read_voltage, steps, num_cycles,
#            delay_between, clim
#
# 6. potentiation_depression_alternating()
#    Pattern: Initial Read → (SET → RESET) × N cycles with reads
#    Use: Alternating SET/RESET pattern for endurance testing
#    Params: set_voltage, reset_voltage, pulse_width, read_voltage, num_pulses_per_cycle,
#            delay_between, num_post_reads, post_read_interval, num_cycles, delay_between_cycles, clim
#
# ⏱️ RELIABILITY / STABILITY TESTS
# ────────────────────────────────────────────────────────────────────────────────
# 7. endurance_test()
#    Pattern: Initial Read → (SET → Read → RESET → Read) × N cycles
#    Use: Device lifetime, cycling endurance, degradation monitoring
#    Params: set_voltage, reset_voltage, pulse_width, read_voltage, num_cycles,
#            delay_between, clim
#
# 🔬 RELAXATION & DYNAMICS TESTS
# ────────────────────────────────────────────────────────────────────────────────
# 8. relaxation_after_multi_pulse()
#    Pattern: 1×Read → N×Pulse → N×Read (measure reads only)
#    Use: Find how device relaxes after cumulative pulsing
#    Params: pulse_voltage, num_pulses, pulse_width, delay_between_pulses,
#            read_voltage, num_reads, delay_between_reads, clim
#
# 9. relaxation_after_multi_pulse_with_pulse_measurement()
#    Pattern: 1×Read → N×Pulse(measured) → N×Read
#    Use: Full relaxation characterization including pulse peak currents
#    Params: pulse_voltage, num_pulses, pulse_width, delay_between_pulses,
#            read_voltage, num_reads, delay_between_reads, clim
#
# 🔄 PULSE WIDTH CHARACTERIZATION
# ────────────────────────────────────────────────────────────────────────────────
# 10. width_sweep_with_reads()
#     Pattern: For each width: Initial Read, (Pulse→Read)×N, Reset (per width)
#     Use: Measure pulse width dependence (reads only)
#     Params: pulse_voltage, pulse_widths (list), read_voltage, num_pulses_per_width,
#             reset_voltage, reset_width, delay_between_widths, clim
#
# 11. width_sweep_with_all_measurements()
#     Pattern: For each width: Initial Read, (Pulse(measured)→Read)×N, Reset (per width)
#     Use: Full width characterization including pulse peak currents
#     Params: pulse_voltage, pulse_widths (list), read_voltage, num_pulses_per_width,
#             reset_voltage, reset_width, delay_between_widths, clim
#
# 📊 VOLTAGE CHARACTERIZATION
# ────────────────────────────────────────────────────────────────────────────────
# 12. voltage_amplitude_sweep()
#     Pattern: For each voltage: Initial Read → (Pulse → Read) × N → Reset
#     Use: Test different pulse voltages at fixed width
#     Params: pulse_voltage_start, pulse_voltage_stop, pulse_voltage_step, pulse_width,
#             read_voltage, num_pulses_per_voltage, delay_between, reset_voltage,
#             reset_width, delay_between_voltages, clim
#
# 13. ispp_test() - Incremental Step Pulse Programming
#     Pattern: Start at low voltage, increase by step each pulse
#     Use: Gradually increase voltage until switching occurs
#     Params: start_voltage, voltage_step, max_voltage, pulse_width, read_voltage,
#             target_resistance, resistance_threshold_factor, max_pulses, delay_between, clim
#
# 14. switching_threshold_test()
#     Pattern: Try increasing voltages, find minimum that causes switching
#     Use: Find minimum SET or RESET voltage
#     Params: direction (set/reset), start_voltage, voltage_step, max_voltage, pulse_width,
#             read_voltage, resistance_threshold_factor, num_pulses_per_voltage,
#             delay_between, clim
#
# 🎯 MULTILEVEL & PATTERN TESTS
# ────────────────────────────────────────────────────────────────────────────────
# 15. multilevel_programming()
#     Pattern: For each level: Reset → Program with pulses → Read
#     Use: Target specific resistance states for multilevel memory
#     Params: target_levels (list), pulse_voltage, pulse_width, read_voltage,
#             num_pulses_per_level, delay_between, reset_voltage, reset_width,
#             delay_between_levels, clim
#
# 16. pulse_train_varying_amplitudes()
#     Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N
#     Use: Alternating or varying amplitude pulses
#     Params: pulse_voltages (list), pulse_width, read_voltage, num_repeats,
#             delay_between, clim
#
# 🔍 DIAGNOSTIC TESTS
# ────────────────────────────────────────────────────────────────────────────────
# 17. current_range_finder()
#     Pattern: Test multiple current ranges and recommend best for device
#     Use: Find optimal current measurement range
#     Params: test_voltage, num_reads_per_range, delay_between_reads, current_ranges (list)
#
# ⚠️  SMU-BASED SLOW PULSE MEASUREMENTS (Much Slower Than PMU)
# ────────────────────────────────────────────────────────────────────────────────
# ⚠️  IMPORTANT: These functions use SMU (Source Measure Unit) instead of PMU.
#     SMU is much slower but supports much longer pulse widths (up to 480 seconds).
#     Use only for very slow pulses (milliseconds to seconds). For fast pulses,
#     use PMU functions above.
#
# 18. smu_slow_pulse_measure()
#     Pattern: Single pulse → Measure resistance during pulse
#     Use: Very slow pulses (milliseconds to seconds), relaxation studies
#     Limits: Pulse width 40ns to 480s (vs microseconds for PMU)
#     Params: pulse_voltage, pulse_width (seconds), i_range, i_compliance,
#             initialize, log_messages, enable_debug_output
#     ⚠️  NOTE: Uses SMU1 hardware path, not PMU channels
#
# 19. smu_retention()
#     Pattern: (SET pulse → Read → RESET pulse → Read) × N cycles
#     Use: Retention studies with slow alternating SET/RESET pulses
#     Limits: Pulse widths 40ns to 480s (vs microseconds for PMU)
#     Params: set_voltage, reset_voltage, set_duration, reset_duration,
#             num_cycles, repeat_delay, probe_voltage, probe_duration,
#             i_range, i_compliance, initialize, log_messages, enable_debug_output
#     ⚠️  NOTE: Uses SMU1 hardware path, not PMU channels
#
# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE LIMITS - Keithley 4200A-SCS with KXCI C Module Constraints
# ═══════════════════════════════════════════════════════════════════════════════
#
# ENHANCED C MODULE CAPABILITIES:
# ────────────────────────────────────────────────────────────────────────────────
# The underlying C modules (pmu_retention_dual_channel, pmu_pulse_read_interleaved,
# pmu_potentiation_depression) have been updated with enhanced capabilities:
#
# 1. Maximum Points: 1,000,000 points per channel (updated from 30,000)
#    - The C modules now support up to 1,000,000 points per channel
#    - Python validation allows up to 1,000,000 points
#    - This enables much longer measurements and higher sampling rates
#
# 2. Minimum Sampling Rate: 200,000 samples/second (200 kHz)
#    - The C modules require rate >= 200000 samples/sec (hardware minimum)
#    - Calculated as: min_rate = 200000000 / 1000
#    - Lower rates cause "rate is too small" errors
#
# 3. Maximum Measurement Time: ~5,000 seconds (at minimum rate)
#    - Calculated from: max_time = 1,000,000 points / 200,000 samples/sec = 5 seconds
#    - For longer measurements, the sample rate is automatically reduced
#    - The system dynamically selects optimal rate based on total time and max_points
#
# 4. Dynamic Rate Selection:
#    - The C modules now use enhanced rate selection (ret_getRateWithMinSeg)
#    - Automatically adapts to short segments (high rates up to 200 MHz)
#    - Automatically adapts to long waveforms (lower rates to fit max_points)
#    - Ensures at least 5 samples per segment for accuracy
#
# 5. Sample Rate Calculation:
#    - The system automatically selects optimal sample rate based on:
#      * Total waveform time (determines minimum rate needed)
#      * Maximum allowed points (max_points limits total data)
#      * Shortest segment time (constrains maximum rate)
#    - Algorithm: Starts at 200 MHz, reduces if needed to fit within max_points
#    - For very short segments (e.g., 100ns): rate is constrained to ensure
#      at least 5 samples per segment: max_rate = 5 / min_segment_time
#
# 6. How max_points Works:
#    - The max_points parameter controls maximum data samples collected per channel
#    - Required points = total_time × sample_rate + 2
#    - If required_points > max_points, rate is lowered until fit
#    - Higher max_points: allows longer waveforms or higher rates (more memory)
#    - Lower max_points: faster transfer, less memory (may force lower rates)
#
# PARAMETER LIMITS (from RetentionConfig validation):
# ────────────────────────────────────────────────────────────────────────────────
# All parameters are validated and clamped to these limits with warnings.
# ═══════════════════════════════════════════════════════════════════════════════

# Pulse width limits (seconds)
MIN_PULSE_WIDTH = 2e-8          # 20ns - minimum pulse width (C module limit)
MAX_PULSE_WIDTH = 1.0           # 1s - maximum pulse width
DEFAULT_PULSE_WIDTH = 100e-6    # 100µs default (converted from ms in GUI)

# Voltage limits (volts)
MIN_VOLTAGE = -20.0              # -20V minimum voltage
MAX_VOLTAGE = 20.0               # +20V maximum voltage
DEFAULT_READ_VOLTAGE = 0.3       # 0.3V default (NOTE: C module uses 0.3V, not user's read_voltage)

# Current range limits (amps) - for i_range parameter
MIN_CURRENT_RANGE = 100e-9       # 100nA minimum current range
MAX_CURRENT_RANGE = 0.8          # 0.8A maximum current range
DEFAULT_CURRENT_RANGE = 1e-4      # 0.1mA default (NOTE: C module uses 1e-4, not converted clim)

# Timing limits (seconds)
MIN_RISE_TIME = 2e-8             # 20ns minimum rise/fall time
MAX_RISE_TIME = 1.0              # 1s maximum rise/fall time
MIN_DELAY = 2e-8                 # 20ns minimum delay between operations
MAX_DELAY = 1.0                  # 1s maximum delay

# Measurement limits
MIN_MAX_POINTS = 12              # Minimum points required by C module
MAX_MAX_POINTS = 1_000_000       # Maximum points (C module limit, updated from 30,000)
DEFAULT_MAX_POINTS = 10000       # Default max points

# Pulse count limits
MIN_NUM_PULSES = 8               # Minimum pulses per sequence
MAX_NUM_PULSES = 1000            # Maximum pulses per sequence
MIN_NUM_INITIAL_MEAS_PULSES = 1  # Minimum initial measurement pulses
MAX_NUM_INITIAL_MEAS_PULSES = 100 # Maximum initial measurement pulses
MIN_NUM_PULSES_SEQ = 1           # Minimum pulses in sequence
MAX_NUM_PULSES_SEQ = 100         # Maximum pulses in sequence

# Safety flags
ENABLE_PULSE_WIDTH_CHECK = True  # Set False to disable min pulse width enforcement
ENABLE_VOLTAGE_CHECK = True      # Set False to disable voltage limit checks
ENABLE_CURRENT_CHECK = True       # Set False to disable current range checks
ENABLE_MAX_POINTS_CHECK = True   # Set False to disable max points check
#
# FIXED PARAMETERS (Must Use Defaults - Do Not Change):
# ────────────────────────────────────────────────────────────────────────────────
# The C module is very sensitive to certain parameters. These MUST use the working
# example defaults (not user inputs) to avoid errors:
#
# - meas_v: Fixed to 0.3V (NOT user's read_voltage parameter)
# - meas_width: Fixed to 1e-6 (1µs) - measurement pulse width
# - meas_delay: Fixed to 2e-6 (2µs) - delay between measurement pulses
# - pulse_delay: Fixed to 1e-6 (1µs) - delay between pulses in sequence
# - i_range: Fixed to 1e-4 (0.1mA) - current measurement range
# - reset_width: Fixed to 1e-7 (0.1µs) - reset pulse width
# - iteration: Fixed to 1 - affects measurement processing
#
# Using user-provided values for these causes:
# - "rate is too small" errors (sampling rate < 200000 samples/sec)
# - "segment time too short" errors (segment validation failures)
# - Inconsistent behavior between different parameter combinations
#
# ═══════════════════════════════════════════════════════════════════════════════


# ============================================================================
# KXCI Client and Helper Functions
# ============================================================================

class KXCIClient:
    """Minimal KXCI helper for sending EX/GP commands over GPIB."""

    def __init__(self, gpib_address: str, timeout: float) -> None:
        self.gpib_address = gpib_address
        self.timeout_ms = int(timeout * 1000)
        self.rm = None
        self.inst = None
        self._ul_mode_active = False

    def connect(self) -> bool:
        try:
            import pyvisa
        except ImportError as exc:  # noqa: F401
            raise RuntimeError("pyvisa is required to communicate with the instrument") from exc

        try:
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(self.gpib_address)
            self.inst.timeout = self.timeout_ms
            self.inst.write_termination = "\n"
            self.inst.read_termination = "\n"
            idn = self.inst.query("*IDN?").strip()
            print(f"✓ Connected to: {idn}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Connection failed: {exc}")
            return False

    def disconnect(self) -> None:
        try:
            if self._ul_mode_active:
                self._exit_ul_mode()
            if self.inst is not None:
                self.inst.close()
            if self.rm is not None:
                self.rm.close()
        finally:
            self.inst = None
            self.rm = None
            self._ul_mode_active = False

    def _enter_ul_mode(self) -> bool:
        if self.inst is None:
            return False
        self.inst.write("UL")
        time.sleep(0.03)
        self._ul_mode_active = True
        return True

    def _exit_ul_mode(self) -> bool:
        if self.inst is None or not self._ul_mode_active:
            self._ul_mode_active = False
            return True
        self.inst.write("DE")
        time.sleep(0.03)
        self._ul_mode_active = False
        return True

    def _execute_ex_command(self, command: str) -> tuple[Optional[float], Optional[str]]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")

        try:
            self.inst.write(command)
            time.sleep(0.01)  # Small delay to ensure command is sent
            
            # Determine wait time based on command type
            # pulse_only commands are fast (no measurement), pulse_measure needs more time
            if "SMU_pulse_only" in command:
                # pulse_only is fast - minimal wait needed
                wait_time = 0.01  # 10ms should be enough for pulse_only
            elif "SMU_pulse_measure" in command:
                # pulse_measure may need slightly more time for measurement
                wait_time = 0.05  # 50ms for pulse_measure
            else:
                # Other commands - use minimal wait, reading loop will handle it
                wait_time = 0.02  # 20ms default
            
            # Small wait for command to start processing
            time.sleep(wait_time)
            
            # Read all available output (including printf statements from C code)
            # The reading loop will handle waiting for the response with appropriate timeouts
            all_output = []
            return_value = None
            max_attempts = 20  # Read up to 20 times to get all output
            attempt = 0
            
            while attempt < max_attempts:
                try:
                    # Read with a short timeout to check for more data
                    self.inst.timeout = 500  # 500ms timeout
                    response = self.inst.read()
                    if response:
                        all_output.append(response)
                        # Print printf output from C code immediately
                        print(response, end='', flush=True)
                        # Check if this contains the return value
                        parsed_value = self._parse_return_value(response)
                        if parsed_value is not None:
                            return_value = parsed_value
                            break
                    else:
                        # No more data, try one more time with a short delay
                        time.sleep(0.1)
                        attempt += 1
                except Exception:
                    # Timeout or no more data
                    attempt += 1
                    if attempt >= max_attempts:
                        break
                    time.sleep(0.1)
            
            # Try one final read to get the return value if we haven't found it
            if return_value is None:
                try:
                    self.inst.timeout = 2000  # 2 second timeout for slow SMU measurements
                    response = self.inst.read()
                    if response:
                        all_output.append(response)
                        print(response, end='', flush=True)
                        parsed = self._parse_return_value(response)
                        if parsed is not None:
                            return_value = parsed
                except Exception:
                    pass
            
            # If still None, try reading all accumulated output for return value
            if return_value is None and all_output:
                combined_output = ' '.join(all_output)
                return_value = self._parse_return_value(combined_output)
            
            return return_value, None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def _safe_read(self) -> str:
        if self.inst is None:
            return ""
        try:
            return self.inst.read()
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _parse_return_value(response: str) -> Optional[float]:
        """Parse return value from KXCI response.
        
        Handles both integer and float return values.
        Looks for patterns like "Return Value = 123.456" or just a number.
        """
        if not response:
            return None
        
        # Try to match "Return Value = <number>" pattern (handles both int and float)
        # Pattern matches: "Return Value = 123.456" or "RETURN VALUE = 123" etc.
        match = re.search(r'Return Value\s*=\s*(-?\d+\.?\d*(?:[eE][+-]?\d+)?)', response, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        
        # Try to parse the entire response as a number (for cases where it's just the number)
        try:
            # Remove any whitespace and try to parse
            cleaned = response.strip()
            # Remove any trailing text after the number
            cleaned = re.sub(r'[^\d\.\-\+eE].*$', '', cleaned)
            if cleaned:
                return float(cleaned)
        except ValueError:
            pass
        
        return None

    def _query_gp(self, param_position: int, num_values: int) -> List[float]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")

        command = f"GP {param_position} {num_values}"
        self.inst.write(command)
        time.sleep(0.03)
        raw = self._safe_read()
        return self._parse_gp_response(raw)

    @staticmethod
    def _parse_gp_response(response: str) -> List[float]:
        response = response.strip()
        if "=" in response and "PARAM VALUE" in response.upper():
            response = response.split("=", 1)[1].strip()

        separator = None
        for cand in (";", ","):
            if cand in response:
                separator = cand
                break

        values: List[float] = []
        if separator is None:
            if response:
                try:
                    values.append(float(response))
                except ValueError:
                    pass
            return values

        for part in response.split(separator):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(float(part))
            except ValueError:
                pass
        return values


def format_param(value: float | int | str) -> str:
    """Format a parameter exactly as expected by KXCI EX commands."""
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


# ============================================================================
# Retention Configuration
# ============================================================================

@dataclass
class RetentionConfig:
    """Configuration for PMU retention measurements."""
    rise_time: float = 1e-7
    reset_v: float = 1.0
    reset_width: float = 1e-6
    reset_delay: float = 5e-7
    meas_v: float = 0.3
    meas_width: float = 1e-6
    meas_delay: float = 2e-6
    set_width: float = 1e-6
    set_fall_time: float = 1e-7
    set_delay: float = 1e-6
    set_start_v: float = 0.3
    set_stop_v: float = 0.3
    steps: int = 0
    i_range: float = 1e-4
    max_points: int = 10000
    iteration: int = 2
    out1_name: str = "VF"
    out2_name: str = "T"
    out2_size: int = 200
    num_pulses: int = 50  # retention measurement pulses
    num_initial_meas_pulses: int = 2
    num_pulses_seq: int = 5  # number of pulses in sequence
    pulse_width: float = 1e-6
    pulse_v: float = 4.0
    pulse_rise_time: float = 1e-7
    pulse_fall_time: float = 1e-7
    pulse_delay: float = 1e-6
    clarius_debug: int = 1

    def total_probe_count(self) -> int:
        return self.num_initial_meas_pulses + self.num_pulses

    def validate(self) -> None:
        limits: Dict[str, tuple[float, float]] = {
            "rise_time": (2e-8, 1.0),
            "reset_v": (-20.0, 20.0),
            "reset_width": (2e-8, 1.0),
            "reset_delay": (2e-8, 1.0),
            "meas_v": (-20.0, 20.0),
            "meas_width": (2e-8, 1.0),
            "meas_delay": (2e-8, 1.0),
            "set_width": (2e-8, 1.0),
            "set_fall_time": (2e-8, 1.0),
            "set_delay": (2e-8, 1.0),
            "set_start_v": (-20.0, 20.0),
            "set_stop_v": (-20.0, 20.0),
            "i_range": (100e-9, 0.8),
            "max_points": (12, 1_000_000),
        }

        for field_name, (lo, hi) in limits.items():
            value = getattr(self, field_name)
            if value < lo or value > hi:
                raise ValueError(f"{field_name}={value} outside [{lo}, {hi}]")

        if not (8 <= self.num_pulses <= 1000):
            raise ValueError("num_pulses must be within [8, 1000]")
        if not (1 <= self.num_initial_meas_pulses <= 100):
            raise ValueError("num_initial_meas_pulses must be within [1, 100]")
        if not (1 <= self.num_pulses_seq <= 100):
            raise ValueError("num_pulses_seq must be within [1, 100]")
        if not (2e-8 <= self.pulse_width <= 1.0):
            raise ValueError("pulse_width must be within [2e-8, 1.0]")
        if not (-20.0 <= self.pulse_v <= 20.0):
            raise ValueError("pulse_v must be within [-20.0, 20.0]")
        if not (2e-8 <= self.pulse_rise_time <= 1.0):
            raise ValueError("pulse_rise_time must be within [2e-8, 1.0]")
        if not (2e-8 <= self.pulse_fall_time <= 1.0):
            raise ValueError("pulse_fall_time must be within [2e-8, 1.0]")
        if not (2e-8 <= self.pulse_delay <= 1.0):
            raise ValueError("pulse_delay must be within [2e-8, 1.0]")
        if self.clarius_debug not in (0, 1):
            raise ValueError("clarius_debug must be 0 or 1")
        if self.out2_size < 1:
            raise ValueError("out2_size must be positive")
        if self.steps < 0:
            raise ValueError("steps must be >= 0")


def build_retention_ex_command(cfg: RetentionConfig) -> str:
    """Build EX command for pmu_retention_dual_channel."""
    total_probes = cfg.total_probe_count()
    common_size = total_probes

    params = [
        format_param(cfg.rise_time),
        format_param(cfg.reset_v),
        format_param(cfg.reset_width),
        format_param(cfg.reset_delay),
        format_param(cfg.meas_v),
        format_param(cfg.meas_width),
        format_param(cfg.meas_delay),
        format_param(cfg.set_width),
        format_param(cfg.set_fall_time),
        format_param(cfg.set_delay),
        format_param(cfg.set_start_v),
        format_param(cfg.set_stop_v),
        format_param(cfg.steps),
        format_param(cfg.i_range),
        format_param(cfg.max_points),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        format_param(cfg.iteration),
        "",
        format_param(common_size),
        cfg.out1_name,
        "",
        format_param(cfg.out2_size),
        cfg.out2_name,
        "",
        format_param(common_size),
        format_param(cfg.num_pulses),
        format_param(cfg.num_initial_meas_pulses),
        format_param(cfg.num_pulses_seq),
        format_param(cfg.pulse_width),
        format_param(cfg.pulse_v),
        format_param(cfg.pulse_rise_time),
        format_param(cfg.pulse_fall_time),
        format_param(cfg.pulse_delay),
        format_param(cfg.clarius_debug),
    ]
    print(cfg.max_points)
    return f"EX A_Retention pmu_retention_dual_channel({','.join(params)})"


# ============================================================================
# Pulse Read Interleaved Configuration
# ============================================================================

@dataclass
class PulseReadInterleavedConfig:
    """Configuration for PMU pulse-read interleaved measurements."""
    rise_time: float = 1e-7
    reset_v: float = 1.5
    reset_width: float = 1e-6
    reset_delay: float = 5e-7
    meas_v: float = 0.3
    meas_width: float = 1e-6
    meas_delay: float = 2e-6
    set_width: float = 1e-6
    set_fall_time: float = 1e-7
    set_delay: float = 0.1e-6
    set_start_v: float = 0.3
    set_stop_v: float = 0.3
    steps: int = 0
    i_range: float = 1e-4
    max_points: int = 10000
    iteration: int = 2
    out1_name: str = "VF"
    out2_name: str = "T"
    out2_size: int = 200
    num_cycles: int = 3  # M - number of cycles
    num_reads: int = 2  # N - number of reads per cycle
    num_pulses_per_group: int = 2  # N - number of pulses per cycle
    pulse_width: float = 1e-6
    pulse_v: float = 4.0
    pulse_rise_time: float = 1e-7
    pulse_fall_time: float = 1e-7
    pulse_delay: float = 1e-6
    clarius_debug: int = 1

    def total_probe_count(self) -> int:
        """Total measurements = 1 (initial) + NumCycles * NumReads"""
        return 1 + self.num_cycles * self.num_reads

    def validate(self) -> None:
        limits: Dict[str, tuple[float, float]] = {
            "rise_time": (2e-8, 1.0),
            "reset_v": (-20.0, 20.0),
            "reset_width": (2e-8, 1.0),
            "reset_delay": (2e-8, 1.0),
            "meas_v": (-20.0, 20.0),
            "meas_width": (2e-8, 1.0),
            "meas_delay": (2e-8, 1.0),
            "set_width": (2e-8, 1.0),
            "set_fall_time": (2e-8, 1.0),
            "set_delay": (2e-8, 1.0),
            "set_start_v": (-20.0, 20.0),
            "set_stop_v": (-20.0, 20.0),
            "i_range": (100e-9, 0.8),
            "max_points": (12, 1_000_000),
        }

        for field_name, (lo, hi) in limits.items():
            value = getattr(self, field_name)
            if value < lo or value > hi:
                raise ValueError(f"{field_name}={value} outside [{lo}, {hi}]")

        if not (1 <= self.num_cycles <= 100):
            raise ValueError("num_cycles must be within [1, 100]")
        if not (1 <= self.num_reads <= 100):
            raise ValueError("num_reads must be within [1, 100]")
        if not (1 <= self.num_pulses_per_group <= 100):
            raise ValueError("num_pulses_per_group must be within [1, 100]")
        if not (2e-8 <= self.pulse_width <= 1.0):
            raise ValueError("pulse_width must be within [2e-8, 1.0]")
        if not (-20.0 <= self.pulse_v <= 20.0):
            raise ValueError("pulse_v must be within [-20.0, 20.0]")
        if not (2e-8 <= self.pulse_rise_time <= 1.0):
            raise ValueError("pulse_rise_time must be within [2e-8, 1.0]")
        if not (2e-8 <= self.pulse_fall_time <= 1.0):
            raise ValueError("pulse_fall_time must be within [2e-8, 1.0]")
        if not (2e-8 <= self.pulse_delay <= 1.0):
            raise ValueError("pulse_delay must be within [2e-8, 1.0]")
        if self.clarius_debug not in (0, 1):
            raise ValueError("clarius_debug must be 0 or 1")
        if self.out2_size < 1:
            raise ValueError("out2_size must be positive")
        if self.steps < 0:
            raise ValueError("steps must be >= 0")


def build_interleaved_ex_command(cfg: PulseReadInterleavedConfig) -> str:
    """Build EX command for pmu_pulse_read_interleaved."""
    total_probes = cfg.total_probe_count()
    common_size = total_probes

    params = [
        format_param(cfg.rise_time),
        format_param(cfg.reset_v),
        format_param(cfg.reset_width),
        format_param(cfg.reset_delay),
        format_param(cfg.meas_v),
        format_param(cfg.meas_width),
        format_param(cfg.meas_delay),
        format_param(cfg.set_width),
        format_param(cfg.set_fall_time),
        format_param(cfg.set_delay),
        format_param(cfg.set_start_v),
        format_param(cfg.set_stop_v),
        format_param(cfg.steps),
        format_param(cfg.i_range),
        format_param(cfg.max_points),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        format_param(cfg.iteration),
        "",
        format_param(common_size),
        cfg.out1_name,
        "",
        format_param(cfg.out2_size),
        cfg.out2_name,
        "",
        format_param(common_size),
        format_param(cfg.num_pulses_per_group),  # NumbMeasPulses → NumPulsesPerGroup
        format_param(cfg.num_cycles),  # NumInitialMeasPulses → NumCycles
        format_param(cfg.num_reads),  # NumPulses → NumReads
        format_param(cfg.pulse_width),
        format_param(cfg.pulse_v),
        format_param(cfg.pulse_rise_time),
        format_param(cfg.pulse_fall_time),
        format_param(cfg.pulse_delay),
        format_param(cfg.clarius_debug),
    ]
    return f"EX A_pulse_read_grouped_multi pmu_pulse_read_interleaved({','.join(params)})"


def build_potentiation_depression_ex_command(cfg: PulseReadInterleavedConfig) -> str:
    """Build EX command for pmu_potentiation_depression."""
    total_probes = cfg.total_probe_count()
    common_size = total_probes

    params = [
        format_param(cfg.rise_time),
        format_param(cfg.reset_v),
        format_param(cfg.reset_width),
        format_param(cfg.reset_delay),
        format_param(cfg.meas_v),
        format_param(cfg.meas_width),
        format_param(cfg.meas_delay),
        format_param(cfg.set_width),
        format_param(cfg.set_fall_time),
        format_param(cfg.set_delay),
        format_param(cfg.set_start_v),
        format_param(cfg.set_stop_v),
        format_param(cfg.steps),
        format_param(cfg.i_range),
        format_param(cfg.max_points),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        "",
        format_param(common_size),
        format_param(cfg.iteration),
        "",
        format_param(common_size),
        cfg.out1_name,
        "",
        format_param(cfg.out2_size),
        cfg.out2_name,
        "",
        format_param(common_size),
        format_param(cfg.num_pulses_per_group),  # NumbMeasPulses → NumPulsesPerGroup
        format_param(cfg.num_cycles),  # NumInitialMeasPulses → NumCycles
        format_param(cfg.num_reads),  # NumPulses → NumReads
        format_param(cfg.pulse_width),
        format_param(cfg.pulse_v),
        format_param(cfg.pulse_rise_time),
        format_param(cfg.pulse_fall_time),
        format_param(cfg.pulse_delay),
        format_param(cfg.clarius_debug),
    ]

    return f"EX A_Poteniation_Depression pmu_potentiation_depression({','.join(params)})"


def build_readtrain_ex_command(
    rise_time: float, reset_v: float, reset_width: float, reset_delay: float,
    meas_v: float, meas_width: float, meas_delay: float,
    set_width: float, set_fall_time: float, set_delay: float,
    set_start_v: float, set_stop_v: float, steps: int,
    i_range: float, max_points: int,
    set_r_size: int, reset_r_size: int, set_v_size: int, set_i_size: int,
    iteration: int, out1_size: int, out1_name: str,
    out2_size: int, out2_name: str,
    pulse_times_size: int, numb_meas_pulses: int, clarius_debug: int
) -> str:
    """Build EX command for readtrain_dual_channel."""
    params = [
        format_param(rise_time),
        format_param(reset_v),
        format_param(reset_width),
        format_param(reset_delay),
        format_param(meas_v),
        format_param(meas_width),
        format_param(meas_delay),
        format_param(set_width),
        format_param(set_fall_time),
        format_param(set_delay),
        format_param(set_start_v),
        format_param(set_stop_v),
        format_param(steps),
        format_param(i_range),
        format_param(max_points),
        "",
        format_param(set_r_size),
        "",
        format_param(reset_r_size),
        "",
        format_param(set_v_size),
        "",
        format_param(set_i_size),
        format_param(iteration),
        "",
        format_param(out1_size),
        out1_name,
        "",
        format_param(out2_size),
        out2_name,
        "",
        format_param(pulse_times_size),
        format_param(numb_meas_pulses),
        format_param(clarius_debug),
    ]

    return f"EX A_Read_Train readtrain_dual_channel({','.join(params)})"


def _compute_probe_times(cfg: RetentionConfig) -> List[float]:
    """Recreate the probe timing centres used in the C implementation."""
    ratio = 0.4
    ttime = 0.0
    centres: List[float] = []

    def add_measurement(start_time: float) -> None:
        centres.append(start_time + cfg.meas_width * (ratio + 0.9) / 2.0)

    # Initial delay and rise time
    ttime += cfg.reset_delay
    ttime += cfg.rise_time

    # Initial measurement pulses
    for _ in range(cfg.num_initial_meas_pulses):
        add_measurement(ttime)
        ttime += cfg.meas_width
        ttime += cfg.rise_time
        ttime += cfg.meas_delay
        ttime += cfg.rise_time

    # Small delay before pulse sequence
    ttime += cfg.rise_time

    # Pulse sequence: Multiple pulses in a row
    for _ in range(cfg.num_pulses_seq):
        ttime += cfg.pulse_rise_time
        ttime += cfg.pulse_width
        ttime += cfg.pulse_fall_time
        ttime += cfg.pulse_delay

    # Retention measurement pulses
    for _ in range(cfg.num_pulses):
        ttime += cfg.rise_time
        add_measurement(ttime)
        ttime += cfg.meas_width
        ttime += cfg.set_fall_time
        ttime += cfg.meas_delay

    return centres


# ============================================================================
# Main Scripts Class
# ============================================================================

class Keithley4200_KXCI_Scripts:
    """KXCI-based testing scripts for Keithley 4200A-SCS.
    
    This class provides a unified interface for running memristor device tests
    on the Keithley 4200A-SCS, matching the interface of keithley2450_tsp_scripts.py.
    
    CRITICAL PARAMETER FIXES - Why We Use Fixed Defaults Instead of User Parameters:
    ---------------------------------------------------------------------------------
    After extensive testing and comparison with working examples, we discovered that
    the C module (pmu_retention_dual_channel) is very sensitive to certain parameters.
    Using user-provided values (like read_voltage, delay_between, clim) instead of
    the C module's tested defaults causes errors like:
    - "rate is too small" (sampling rate < 200000 samples/sec)
    - "segment time too short" (segment validation failures)
    - Inconsistent behavior between different parameter combinations
    
    The following parameters MUST use the working example defaults (not user inputs):
    
    1. pulse_delay: Fixed to 1e-6 (1µs) instead of delay_between_pulses
       - The C module expects a consistent pulse delay for proper waveform generation
       - User-provided delays (e.g., 100µs) cause segment time validation issues
       - The working example uses 1e-6, which works reliably
    
    2. meas_v: Fixed to 0.3V instead of read_voltage parameter
       - The C module's internal measurement logic expects 0.3V
       - Using user's read_voltage (e.g., 0.2V) causes measurement inconsistencies
       - The working example consistently uses 0.3V
    
    3. meas_width: Fixed to 1e-6 (1µs) instead of 2e-6 or user values
       - Measurement pulse width must match the C module's expectations
       - The working example uses 1e-6, which provides reliable measurements
    
    4. meas_delay: Fixed to 2e-6 (2µs) instead of delay_between_reads
       - Delay between measurement pulses must be consistent
       - User-provided delays (e.g., 100µs) cause the waveform to exceed time limits
       - The working example uses 2e-6
    
    5. i_range: Fixed to 1e-4 (0.1mA) instead of converted clim
       - Current range must match the C module's tested configuration
       - User's clim (e.g., 100mA) converted to i_range causes measurement issues
       - The working example uses 1e-4
    
    6. reset_width: Fixed to 1e-7 (0.1µs) instead of default 1e-6
       - Reset pulse width must be very short for proper waveform generation
       - The working example uses 1e-7, which is smaller than the RetentionConfig default
    
    7. iteration: Fixed to 1 instead of default 2
       - The iteration parameter affects how the C module processes measurements
       - The working example uses 1, which provides correct behavior
    
    Why This Works:
    --------------
    The C module was designed and tested with specific parameter combinations. When
    we pass user-provided values that differ from these tested defaults, the internal
    waveform generation and rate calculation logic fails. By using the exact defaults
    from the working example, we ensure:
    - Consistent waveform generation
    - Valid sampling rate calculations (>= 200000 samples/sec)
    - Proper segment time validation
    - Reliable measurement collection
    
    Note: User parameters (pulse_voltage, pulse_width, num_pulses, etc.) are still
    used where they don't conflict with the C module's internal requirements. Only
    the timing and measurement parameters that affect waveform generation are fixed.
    """
    
    # Edge timing guidance (per 4225-PMU datasheet: ≤20 ns on fast ranges)
    _MIN_EDGE_TIME = 2e-8  # 20 ns KXCI minimum
    _DEFAULT_EDGE_TIME = 1e-7  # 100 ns legacy default
    _FAST_EDGE_THRESHOLD = 5e-7  # ≤500 ns pulses/read windows → use fast edge

    def __init__(self, gpib_address: str, timeout: float = 30.0):
        """
        Initialize with GPIB address.
        
        Args:
            gpib_address: VISA resource string (e.g., "GPIB0::17::INSTR")
            timeout: Communication timeout in seconds (default: 30.0)
        """
        self.gpib_address = gpib_address
        self.timeout = timeout
        self.start_time = time.time()
        self._controller: Optional[KXCIClient] = None
    
    def _select_edge_time(self, segment_width_s: float, user_edge_s: Optional[float] = None) -> float:
        """Choose the fastest safe rise/fall time for a waveform segment."""
        if user_edge_s is not None:
            edge_time = user_edge_s
        elif segment_width_s <= self._FAST_EDGE_THRESHOLD:
            edge_time = self._MIN_EDGE_TIME
        else:
            edge_time = self._DEFAULT_EDGE_TIME
        max_edge = max(self._MIN_EDGE_TIME, min(segment_width_s * 0.45, 1.0))
        return max(self._MIN_EDGE_TIME, min(edge_time, max_edge))
    
    def _run_interleaved_with_fallback(self, cfg: PulseReadInterleavedConfig) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Execute interleaved command, retrying with safe edge times if fast edges fail."""
        try:
            return self._execute_interleaved(cfg)
        except RuntimeError as exc:
            msg = str(exc)
            fast_edges_used = (
                cfg.pulse_rise_time <= self._MIN_EDGE_TIME * 1.01
                or cfg.pulse_fall_time <= self._MIN_EDGE_TIME * 1.01
                or cfg.rise_time <= self._MIN_EDGE_TIME * 1.01
            )
            if "error code: -90" in msg and fast_edges_used:
                print("[KXCI] Edge timing retry: -90 error with fast edges. Retrying with default 100 ns edges.")
                safe_cfg = replace(
                    cfg,
                    pulse_rise_time=self._DEFAULT_EDGE_TIME,
                    pulse_fall_time=self._DEFAULT_EDGE_TIME,
                    rise_time=max(cfg.rise_time, self._DEFAULT_EDGE_TIME),
                )
                return self._execute_interleaved(safe_cfg)
            raise
    
    def _get_timestamp(self) -> float:
        """Get timestamp relative to tester initialization."""
        return time.time() - self.start_time
    
    def _get_controller(self) -> KXCIClient:
        """Get or create KXCI controller."""
        if self._controller is None:
            self._controller = KXCIClient(self.gpib_address, self.timeout)
        return self._controller
    
    def _convert_us_to_seconds(self, value_ms: float) -> float:
        """Convert milliseconds to seconds."""
        return value_ms / 1000.0
    
    def _convert_us_to_seconds(self, value_us: float) -> float:
        """Convert microseconds to seconds."""
        return value_us / 1_000_000.0
    
    def _convert_clim_to_i_range(self, clim: float) -> float:
        """Convert current limit to appropriate i_range for 4200.
        
        The 4200 uses i_range parameter. We'll use clim with some headroom.
        """
        # Use 1.2x headroom, but clamp to valid range [100e-9, 0.8]
        i_range = clim * 1.2
        return max(100e-9, min(0.8, i_range))
    
    def _estimate_interleaved_total_time(self, cfg: PulseReadInterleavedConfig) -> float:
        """Estimate total waveform time for interleaved module.
        
        Pattern: Initial Read → (Pulses×N → Reads×M) × Cycles
        
        Args:
            cfg: PulseReadInterleavedConfig
            
        Returns:
            Estimated total time in seconds
        """
        ttime = 0.0
        
        # Initial Read
        ttime += cfg.reset_delay
        ttime += cfg.rise_time  # Rise to measV
        ttime += cfg.meas_width  # Measurement width
        ttime += cfg.set_fall_time  # Fall delay at measV
        ttime += cfg.rise_time  # Fall to 0V
        ttime += cfg.meas_delay  # Delay after read
        
        # For each cycle
        for _ in range(cfg.num_cycles):
            # Pulses per cycle
            for _ in range(cfg.num_pulses_per_group):
                ttime += cfg.pulse_rise_time  # Rise to pulse
                ttime += cfg.pulse_width  # Pulse width
                ttime += cfg.pulse_fall_time  # Fall from pulse
                ttime += cfg.pulse_delay  # Delay after pulse
            
            # Reads per cycle
            for _ in range(cfg.num_reads):
                ttime += cfg.rise_time  # Rise to measV
                ttime += cfg.meas_width  # Measurement width
                ttime += cfg.set_fall_time  # Fall delay at measV
                ttime += cfg.rise_time  # Fall to 0V
                ttime += cfg.meas_delay  # Delay after read
        
        return ttime
    
    def _calculate_interleaved_min_max_points(self, estimated_time: float, min_segment_time: float) -> int:
        """Calculate minimum max_points needed for interleaved module.
        
        The C module requires:
        - Minimum sampling rate: 200,000 samples/second
        - Maximum rate constraint: 5 / min_segment_time (for at least 5 samples per segment)
        - Required points = total_time × sample_rate + 2
        
        For long measurements, we need enough max_points to allow the rate to be
        lowered while still maintaining the minimum rate. The key insight is:
        - If max_points is too small for a long measurement, the C module calculates
          a very high rate (to fit within max_points), which makes short segments invalid
        - We need to increase max_points so the rate can be lower
        
        Args:
            estimated_time: Estimated total waveform time (seconds)
            min_segment_time: Minimum segment time in waveform (seconds)
            
        Returns:
            Minimum max_points needed
        """
        # Minimum sampling rate (200 kHz) - C module requirement
        min_rate = 200000
        
        # Maximum rate based on minimum segment time (need at least 5 samples per segment)
        # This ensures short segments are valid
        max_rate_from_segment = 5.0 / min_segment_time if min_segment_time > 0 else 200000000
        
        # The C module will select a rate between min_rate and max_rate_from_segment
        # that fits within max_points: required_points = estimated_time × rate + 2 <= max_points
        
        # For short measurements (< 100ms), use 10000 (reliable default)
        if estimated_time < 0.1:
            return 10000
        
        # For long measurements, we need to ensure max_points is large enough that:
        # 1. The rate can be at least min_rate (200 kHz) without exceeding max_points
        # 2. The rate doesn't exceed max_rate_from_segment (to keep short segments valid)
        
        # Calculate minimum points needed at minimum rate
        min_points_at_min_rate = int(estimated_time * min_rate + 2)
        
        # Calculate points needed at max allowed rate (if we want to use high rate)
        max_points_at_max_rate = int(estimated_time * max_rate_from_segment + 2)
        
        # We need enough points to allow the rate to be selected between min_rate and max_rate
        # The C module will pick the highest rate that fits, so we need at least:
        # max_points >= estimated_time × max_rate_from_segment + 2
        # But we also want to allow lower rates, so we use the maximum of both
        
        # Use the larger of the two, with 20% headroom for rate calculation
        calculated_min = max(min_points_at_min_rate, max_points_at_max_rate)
        calculated_min = int(calculated_min * 1.2)
        
        # Cap at 1,000,000 (C module maximum)
        return min(calculated_min, 1_000_000)
    
    def _ensure_valid_interleaved_max_points(self, cfg: PulseReadInterleavedConfig) -> None:
        """Ensure max_points is sufficient for interleaved module rate calculation.
        
        This calculates the minimum max_points needed based on estimated total time
        and updates the config if needed.
        
        Args:
            cfg: PulseReadInterleavedConfig to update
        """
        estimated_time = self._estimate_interleaved_total_time(cfg)
        
        # Find minimum segment time
        min_segment_time = min(
            cfg.pulse_width,
            cfg.pulse_delay,
            cfg.meas_width,
            cfg.meas_delay,
            cfg.pulse_rise_time,
            cfg.pulse_fall_time,
            cfg.rise_time,
            cfg.set_fall_time,
            cfg.reset_delay,
        )
        
        min_max_points = self._calculate_interleaved_min_max_points(estimated_time, min_segment_time)
        
        # Ensure max_points is at least the calculated minimum
        cfg.max_points = max(cfg.max_points, min_max_points)
        
        # Cap at validation limit
        cfg.max_points = min(cfg.max_points, 1_000_000)
    
    def _estimate_total_time(self, cfg: RetentionConfig) -> float:
        """Estimate total waveform time based on configuration.
        
        This estimates the total time that will be accumulated in the C module
        to calculate the minimum max_points needed for rate calculation.
        
        Args:
            cfg: RetentionConfig with all timing parameters
        
        Returns:
            Estimated total time in seconds
        """
        ttime = 0.0
        
        # Initial delay and rise time
        ttime += cfg.reset_delay
        ttime += cfg.rise_time
        
        # Initial measurement pulses: Each has measWidth + riseTime + measDelay + riseTime
        for _ in range(cfg.num_initial_meas_pulses):
            ttime += cfg.meas_width
            ttime += cfg.rise_time
            ttime += cfg.meas_delay
            ttime += cfg.rise_time
        
        # Small delay before pulse sequence
        ttime += cfg.rise_time
        
        # Pulse sequence: Each pulse has riseTime + width + fallTime + delay
        for _ in range(cfg.num_pulses_seq):
            ttime += cfg.pulse_rise_time
            ttime += cfg.pulse_width
            ttime += cfg.pulse_fall_time
            ttime += cfg.pulse_delay
        
        # Retention measurement pulses: Each has riseTime + measWidth + setFallTime + riseTime + measDelay
        for _ in range(cfg.num_pulses):
            ttime += cfg.rise_time  # Delay before measurement
            ttime += cfg.rise_time  # Rise to measurement voltage
            ttime += cfg.meas_width  # Measurement pulse width
            ttime += cfg.set_fall_time  # Fall delay at measV
            ttime += cfg.rise_time  # Fall to 0V
            ttime += cfg.meas_delay  # Delay at 0V before next measurement
        
        return ttime
    
    def _calculate_min_max_points(self, estimated_time: float) -> int:
        """Calculate minimum max_points needed for valid rate calculation.
        
        The C module requires a minimum sampling rate of 200000 samples/second (200 kHz).
        To ensure a valid rate, we need: max_points >= estimated_time * 200000
        
        Note: The C modules now support up to 1,000,000 points per channel, enabling
        much longer measurements. The rate selection algorithm will automatically
        reduce the sample rate if needed to fit within max_points while maintaining
        the minimum rate requirement.
        
        Args:
            estimated_time: Estimated total waveform time (seconds)
        
        Returns:
            Minimum max_points needed (with safety margin)
        """
        min_rate = 200000  # Minimum rate from C module (200000000 / 1000 = 200 kHz)
        min_points = int(estimated_time * min_rate)
        # Add 20% safety margin and round up to nearest 1000
        safety_margin = int(min_points * 0.2)
        min_points_with_margin = min_points + safety_margin
        # Round up to nearest 1000
        return ((min_points_with_margin + 999) // 1000) * 1000
    
    def _ensure_valid_max_points(self, cfg: RetentionConfig) -> None:
        """Ensure max_points is sufficient for C module rate calculation.
        
        This calculates the minimum max_points needed based on estimated total time
        and updates the config if needed. For long measurements, we may need to exceed
        10000 to maintain the minimum sampling rate (200000 samples/sec).
        
        The C modules now support up to 1,000,000 points per channel, enabling much
        longer measurements. The rate selection algorithm (ret_getRateWithMinSeg) will
        automatically select an optimal rate based on:
        - Total waveform time
        - Maximum allowed points (max_points)
        - Shortest segment time in the waveform
        
        Args:
            cfg: RetentionConfig to update
        """
        estimated_time = self._estimate_total_time(cfg)
        min_max_points = self._calculate_min_max_points(estimated_time)
        
        # Ensure max_points is at least the calculated minimum (required for rate calculation)
        cfg.max_points = max(cfg.max_points, min_max_points)
        
        # For short measurements, use 10000 (matches working example)
        # For long measurements, allow up to 1,000,000 (max allowed by RetentionConfig validation)
        # This ensures we can handle long measurements while avoiding segment time issues
        if min_max_points <= 10000:
            # Short measurement: use reliable 10000
            cfg.max_points = 10000
        else:
            # Long measurement: use calculated minimum, but cap at validation limit
            max_allowed_points = 1_000_000  # Max allowed by RetentionConfig.validate()
            cfg.max_points = min(cfg.max_points, max_allowed_points)
    
    def _estimate_readtrain_total_time(self, numb_meas_pulses: int, meas_width: float,
                                       meas_delay: float, rise_time: float = 3e-8) -> float:
        """Estimate total waveform time for readtrain measurements.
        
        Args:
            numb_meas_pulses: Number of measurement pulses
            meas_width: Measurement pulse width (seconds)
            meas_delay: Delay between measurements (seconds)
            rise_time: Rise/fall time (seconds)
        
        Returns:
            Estimated total time in seconds
        """
        ttime = 0.0
        
        # Initial delay (rise_time)
        ttime += rise_time
        
        # Each measurement pulse has: rise + width + fall + delay
        for _ in range(numb_meas_pulses):
            ttime += rise_time  # Rise to measurement voltage
            ttime += meas_width  # Measurement pulse width
            ttime += rise_time  # Fall delay
            ttime += rise_time  # Fall to 0V
            ttime += meas_delay  # Delay before next measurement
        
        return ttime
    
    def _calculate_readtrain_max_points(self, numb_meas_pulses: int, meas_width: float,
                                        meas_delay: float, rise_time: float = 3e-8) -> int:
        """Calculate minimum max_points for readtrain measurements.
        
        Args:
            numb_meas_pulses: Number of measurement pulses
            meas_width: Measurement pulse width (seconds)
            meas_delay: Delay between measurements (seconds)
            rise_time: Rise/fall time (seconds)
        
        Returns:
            Minimum max_points needed (with safety margin)
        """
        estimated_time = self._estimate_readtrain_total_time(numb_meas_pulses, meas_width, meas_delay, rise_time)
        return self._calculate_min_max_points(estimated_time)
    
    
    def _format_results(self, timestamps: List[float], voltages: List[float], 
                       currents: List[float], resistances: List[float],
                       **extras) -> Dict:
        """Format results into standardized dict with optional extra keys."""
        result = {
            'timestamps': timestamps,
            'voltages': voltages,
            'currents': currents,
            'resistances': resistances
        }
        result.update(extras)
        return result

    def _print_results_table(self, timestamps: List[float], voltages: List[float],
                              currents: List[float], resistances: List[float],
                              max_rows: int = 20) -> None:
        """Print measurement data in a readable table."""
        if not timestamps:
            print("\n[DATA] No measurement data returned.")
            return

        total = len(timestamps)
        rows_to_show = min(total, max_rows)

        print("\n[DATA] Measurement Results:")
        header = f"{'Idx':>4} {'Time (µs)':>12} {'Voltage (V)':>14} {'Current (A)':>14} {'Resistance (Ω)':>16}"
        print(header)
        print("-" * len(header))

        for idx in range(rows_to_show):
            time_us = timestamps[idx] * 1e6
            voltage = voltages[idx] if idx < len(voltages) else float('nan')
            current = currents[idx] if idx < len(currents) else float('nan')
            resistance = resistances[idx] if idx < len(resistances) else float('nan')
            print(f"{idx:>4} {time_us:>12.3f} {voltage:>14.6f} {current:>14.6e} {resistance:>16.3e}")

        if total > rows_to_show:
            print(f"... ({total - rows_to_show} more rows)")
    
    def _query_gp_data(self, controller: KXCIClient, param: int, count: int, 
                      name: str = "") -> List[float]:
        """Query GP parameter with retry logic."""
        for attempt in range(3):
            try:
                data = controller._query_gp(param, count)
                if data:
                    return data
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.5)
                else:
                    print(f"⚠️ Failed to query GP {param} ({name}): {e}")
        return []
    
    def _execute_retention(self, cfg: RetentionConfig) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Execute retention measurement and return normalized data.
        
        Returns:
            Tuple of (timestamps, voltages, currents, resistances)
        """
        # Debug: Print all parameters being sent
        print("\n" + "="*80)
        print("[DEBUG] Retention Parameters:")
        print("="*80)
        print(f"  rise_time:              {cfg.rise_time:.2E} s ({cfg.rise_time*1e9:.2f} ns)")
        print(f"  reset_v:                {cfg.reset_v:.6f} V")
        print(f"  reset_width:            {cfg.reset_width:.2E} s ({cfg.reset_width*1e6:.2f} µs)")
        print(f"  reset_delay:             {cfg.reset_delay:.2E} s ({cfg.reset_delay*1e6:.2f} µs)")
        print(f"  meas_v:                 {cfg.meas_v:.6f} V")
        print(f"  meas_width:             {cfg.meas_width:.2E} s ({cfg.meas_width*1e6:.2f} µs)")
        print(f"  meas_delay:             {cfg.meas_delay:.2E} s ({cfg.meas_delay*1e3:.2f} ms)")
        print(f"  set_width:              {cfg.set_width:.2E} s ({cfg.set_width*1e6:.2f} µs)")
        print(f"  set_fall_time:          {cfg.set_fall_time:.2E} s ({cfg.set_fall_time*1e9:.2f} ns)")
        print(f"  set_delay:               {cfg.set_delay:.2E} s ({cfg.set_delay*1e6:.2f} µs)")
        print(f"  set_start_v:            {cfg.set_start_v:.6f} V")
        print(f"  set_stop_v:             {cfg.set_stop_v:.6f} V")
        print(f"  steps:                  {cfg.steps}")
        print(f"  i_range:                {cfg.i_range:.2E} A ({cfg.i_range*1e3:.2f} mA)")
        print(f"  max_points:             {cfg.max_points}")
        print(f"  iteration:              {cfg.iteration}")
        print(f"  out1_name:              {cfg.out1_name}")
        print(f"  out2_name:              {cfg.out2_name}")
        print(f"  out2_size:              {cfg.out2_size}")
        print(f"  num_pulses:             {cfg.num_pulses}")
        print(f"  num_initial_meas_pulses: {cfg.num_initial_meas_pulses}")
        print(f"  num_pulses_seq:         {cfg.num_pulses_seq}")
        print(f"  pulse_width:            {cfg.pulse_width:.2E} s ({cfg.pulse_width*1e6:.2f} µs)")
        print(f"  pulse_v:                {cfg.pulse_v:.6f} V")
        print(f"  pulse_rise_time:        {cfg.pulse_rise_time:.2E} s ({cfg.pulse_rise_time*1e9:.2f} ns)")
        print(f"  pulse_fall_time:        {cfg.pulse_fall_time:.2E} s ({cfg.pulse_fall_time*1e9:.2f} ns)")
        print(f"  pulse_delay:            {cfg.pulse_delay:.2E} s ({cfg.pulse_delay*1e3:.2f} ms)")
        print(f"  clarius_debug:          {cfg.clarius_debug}")
        print("="*80)
        
        
        command = build_retention_ex_command(cfg)
        print(f"\n[DEBUG] Generated EX command:")
        print(command)
        print("="*80 + "\n")
        
        
        total_probes = cfg.total_probe_count()
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            return_value, error = controller._execute_ex_command(command)
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            
            if return_value is not None and return_value < 0:
                raise RuntimeError(f"EX command returned error code: {return_value}")
            
            time.sleep(0.2)  # Allow data to be ready
            
            # Query data from GP parameters
            set_v = self._query_gp_data(controller, 20, total_probes, "setV")
            set_i = self._query_gp_data(controller, 22, total_probes, "setI")
            pulse_times = self._query_gp_data(controller, 30, total_probes, "PulseTimes")
            
            if not pulse_times:
                pulse_times = _compute_probe_times(cfg)
            
            if len(pulse_times) != total_probes:
                pulse_times = [float(i) for i in range(total_probes)]
            
            # Calculate resistances
            resistances: List[float] = []
            for voltage, current in zip(set_v, set_i):
                if abs(current) < 1e-12:
                    resistances.append(float("inf"))
                else:
                    resistances.append(voltage / current)
            
            # Ensure all lists are same length
            min_len = min(len(set_v), len(set_i), len(pulse_times), len(resistances))
            set_v = set_v[:min_len]
            set_i = set_i[:min_len]
            pulse_times = pulse_times[:min_len]
            resistances = resistances[:min_len]
            
            return pulse_times, set_v, set_i, resistances
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    def _execute_interleaved(self, cfg: PulseReadInterleavedConfig) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Execute interleaved pulse-read measurement and return normalized data.
        
        Returns:
            Tuple of (timestamps, voltages, currents, resistances)
        """
        total_probes = cfg.total_probe_count()
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            command = build_interleaved_ex_command(cfg)
            print(f"\n[KXCI] Generated EX command for pulse-read-repeat:")
            print(command)
            print(f"\n[KXCI] Parameter Values Sent to C Module (in SECONDS as expected by C code):")
            print(f"  Configuration: num_cycles={cfg.num_cycles}, num_pulses_per_group={cfg.num_pulses_per_group}, num_reads={cfg.num_reads}")
            print(f"  Expected total measurements: {total_probes}")
            print(f"  Timing parameters (seconds):")
            print(f"    pulse_width={cfg.pulse_width:.2e} s ({cfg.pulse_width*1e6:.2f} µs)")
            print(f"    pulse_delay={cfg.pulse_delay:.2e} s ({cfg.pulse_delay*1e6:.2f} µs)")
            print(f"    pulse_rise_time={cfg.pulse_rise_time:.2e} s ({cfg.pulse_rise_time*1e6:.2f} µs)")
            print(f"    pulse_fall_time={cfg.pulse_fall_time:.2e} s ({cfg.pulse_fall_time*1e6:.2f} µs)")
            print(f"    meas_width={cfg.meas_width:.2e} s ({cfg.meas_width*1e6:.2f} µs)")
            print(f"    meas_delay={cfg.meas_delay:.2e} s ({cfg.meas_delay*1e6:.2f} µs)")
            print(f"    rise_time={cfg.rise_time:.2e} s ({cfg.rise_time*1e6:.2f} µs)")
            print(f"  Voltage parameters:")
            print(f"    pulse_v={cfg.pulse_v:.2f} V")
            print(f"    meas_v={cfg.meas_v:.2f} V")
            print(f"  Other parameters:")
            print(f"    i_range={cfg.i_range:.2e} A")
            print(f"    max_points={cfg.max_points}")
            return_value, error = controller._execute_ex_command(command)
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            
            if return_value is not None and return_value < 0:
                # Error code -207 typically means "minimum segment time" violation
                # Error code -90 typically means invalid parameter or rate calculation failure
                error_msg = f"EX command returned error code: {return_value}"
                if return_value == -207:
                    error_msg += "\nThis usually indicates a minimum segment time violation."
                    error_msg += "\nAll timing parameters (pulse_width, pulse_delay, meas_width, meas_delay) must be >= 20 ns (2e-8 seconds)."
                    error_msg += f"\nCurrent values: pulse_width={cfg.pulse_width:.2e}s, pulse_delay={cfg.pulse_delay:.2e}s, meas_width={cfg.meas_width:.2e}s, meas_delay={cfg.meas_delay:.2e}s"
                elif return_value == -90:
                    error_msg += "\nThis usually indicates an invalid parameter or rate calculation failure."
                    error_msg += "\nCommon causes:"
                    error_msg += "\n  - Measurement window (read_width) too large or invalid"
                    error_msg += "\n  - Sampling rate too low (< 200000 Hz)"
                    error_msg += "\n  - Invalid timing parameters"
                    error_msg += f"\nCurrent values: pulse_width={cfg.pulse_width:.2e}s ({cfg.pulse_width*1e6:.2f}µs), pulse_delay={cfg.pulse_delay:.2e}s ({cfg.pulse_delay*1e6:.2f}µs)"
                    error_msg += f"\n  meas_width={cfg.meas_width:.2e}s ({cfg.meas_width*1e6:.2f}µs), meas_delay={cfg.meas_delay:.2e}s ({cfg.meas_delay*1e6:.2f}µs)"
                    error_msg += f"\n  num_cycles={cfg.num_cycles}, num_pulses_per_group={cfg.num_pulses_per_group}, num_reads={cfg.num_reads}"
                raise RuntimeError(error_msg)
            
            time.sleep(0.2)  # Allow data to be ready
            
            # Query data from GP parameters (interleaved module uses different param positions)
            set_v = self._query_gp_data(controller, 20, total_probes, "setV")
            set_i = self._query_gp_data(controller, 22, total_probes, "setI")
            pulse_times = self._query_gp_data(controller, 31, total_probes, "PulseTimes")
            
            if not pulse_times:
                # Generate approximate times based on waveform structure
                pulse_times = []
                ttime = cfg.reset_delay + cfg.rise_time
                # Initial read
                ttime += cfg.rise_time + cfg.meas_width * 0.65 + cfg.set_fall_time + cfg.rise_time + cfg.meas_delay
                pulse_times.append(ttime)
                # Cycles
                for _ in range(cfg.num_cycles):
                    # Pulses
                    for _ in range(cfg.num_pulses_per_group):
                        ttime += cfg.pulse_rise_time + cfg.pulse_width + cfg.pulse_fall_time + cfg.pulse_delay
                    # Reads
                    for _ in range(cfg.num_reads):
                        ttime += cfg.rise_time + cfg.meas_width * 0.65 + cfg.set_fall_time + cfg.rise_time + cfg.meas_delay
                        pulse_times.append(ttime)
            
            if len(pulse_times) != total_probes:
                pulse_times = [float(i) for i in range(total_probes)]
            
            # Calculate resistances
            resistances: List[float] = []
            for voltage, current in zip(set_v, set_i):
                if abs(current) < 1e-12:
                    resistances.append(float("inf"))
                else:
                    resistances.append(abs(voltage / current))
            
            # Ensure all lists are same length
            min_len = min(len(set_v), len(set_i), len(pulse_times), len(resistances))
            set_v = set_v[:min_len]
            set_i = set_i[:min_len]
            pulse_times = pulse_times[:min_len]
            resistances = resistances[:min_len]
            
            # Filter out trailing zeros (from C module not filling all allocated slots)
            # The C module allocates arrays for total_probes but may only fill validProbeCount
            # Valid data ends when we encounter timestamp=0 AND voltage=0 AND current=0
            # after valid data has started (skip if all data is at the start)
            valid_len = min_len
            if min_len > 0:
                # Check backwards from the end to find where valid data ends
                for i in range(min_len - 1, -1, -1):
                    # If timestamp is 0 and voltage/current are also 0, this is likely trailing zeros
                    if (abs(pulse_times[i]) < 1e-12 and 
                        abs(set_v[i]) < 1e-12 and 
                        abs(set_i[i]) < 1e-12):
                        valid_len = i
                    else:
                        # Found valid data, stop looking
                        break
                
                # Trim to valid data length
                if valid_len < min_len:
                    set_v = set_v[:valid_len]
                    set_i = set_i[:valid_len]
                    pulse_times = pulse_times[:valid_len]
                    resistances = resistances[:valid_len]
            
            return pulse_times, set_v, set_i, resistances
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    def _execute_readtrain(self, numb_meas_pulses: int, meas_v: float, meas_width: float,
                          meas_delay: float, i_range: float, 
                          rise_time: float = 3e-8) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Execute readtrain measurement and return normalized data.
        
        Returns:
            Tuple of (timestamps, voltages, currents, resistances)
        """
        # Auto-calculate array sizes
        array_size = numb_meas_pulses + 2
        
        # Calculate minimum max_points based on estimated total time
        #max_points = self._calculate_readtrain_max_points(numb_meas_pulses, meas_width, meas_delay, rise_time)
        
        # Use defaults matching run_readtrain_dual_channel.py working example
        # Working example: reset_v=4, set_stop_v=4, meas_delay=1e-6
        # But for read-only measurements, we use reset_v=0, set_stop_v=0
        reset_v = 0.0
        reset_width = 0.5e-6  # Match working example: 5.00E-7
        reset_delay = 1e-6  # Match working example: 1.00E-6
        set_width = 0.5e-6  # Match working example: 5.00E-7
        set_fall_time = rise_time  # Match working example: 3.00E-8
        set_delay = 1e-6  # Match working example: 1.00E-6
        set_start_v = 0.0
        set_stop_v = 0.0
        steps = 1
        iteration = 1
        out1_size = 200
        out1_name = "VF"
        out2_size = 200
        out2_name = "T"
        clarius_debug = 1
        max_points = 10000
        
        # CRITICAL: meas_delay must be 1e-6 to match working example
        # The readtrain C module expects this fixed value
        if meas_delay != 1e-6:
            print(f"[WARN] meas_delay={meas_delay} differs from working example (1e-6). "
                  f"Overriding to 1e-6 to match working example.")
            meas_delay = 1e-6
        
        # Debug: Print all parameters being sent
        print("\n" + "="*80)
        print("[DEBUG] Readtrain Parameters:")
        print("="*80)
        print(f"  rise_time:        {rise_time:.2E} s ({rise_time*1e9:.2f} ns)")
        print(f"  reset_v:           {reset_v:.6f} V")
        print(f"  reset_width:       {reset_width:.2E} s ({reset_width*1e6:.2f} µs)")
        print(f"  reset_delay:       {reset_delay:.2E} s ({reset_delay*1e6:.2f} µs)")
        print(f"  meas_v:            {meas_v:.6f} V")
        print(f"  meas_width:        {meas_width:.2E} s ({meas_width*1e6:.2f} µs)")
        print(f"  meas_delay:        {meas_delay:.2E} s ({meas_delay*1e3:.2f} ms)")
        print(f"  set_width:         {set_width:.2E} s ({set_width*1e6:.2f} µs)")
        print(f"  set_fall_time:     {set_fall_time:.2E} s ({set_fall_time*1e9:.2f} ns)")
        print(f"  set_delay:         {set_delay:.2E} s ({set_delay*1e6:.2f} µs)")
        print(f"  set_start_v:       {set_start_v:.6f} V")
        print(f"  set_stop_v:        {set_stop_v:.6f} V")
        print(f"  steps:             {steps}")
        print(f"  i_range:           {i_range:.2E} A ({i_range*1e3:.2f} mA)")
        print(f"  max_points:        {max_points}")
        print(f"  set_r_size:        {array_size}")
        print(f"  reset_r_size:      {array_size}")
        print(f"  set_v_size:        {array_size}")
        print(f"  set_i_size:        {array_size}")
        print(f"  iteration:         {iteration}")
        print(f"  out1_size:         {out1_size}")
        print(f"  out1_name:         {out1_name}")
        print(f"  out2_size:         {out2_size}")
        print(f"  out2_name:         {out2_name}")
        print(f"  pulse_times_size:  {array_size}")
        print(f"  numb_meas_pulses:  {numb_meas_pulses}")
        print(f"  clarius_debug:     {clarius_debug}")
        print("="*80)
        
        command = build_readtrain_ex_command(
            rise_time=rise_time,
            reset_v=reset_v,
            reset_width=reset_width,
            reset_delay=reset_delay,
            meas_v=meas_v,
            meas_width=meas_width,
            meas_delay=meas_delay,
            set_width=set_width,
            set_fall_time=set_fall_time,
            set_delay=set_delay,
            set_start_v=set_start_v,
            set_stop_v=set_stop_v,
            steps=steps,
            i_range=i_range,
            max_points=max_points,
            set_r_size=array_size,
            reset_r_size=array_size,
            set_v_size=array_size,
            set_i_size=array_size,
            iteration=iteration,
            out1_size=out1_size,
            out1_name=out1_name,
            out2_size=out2_size,
            out2_name=out2_name,
            pulse_times_size=array_size,
            numb_meas_pulses=numb_meas_pulses,
            clarius_debug=clarius_debug
        )
        
        print(f"\n[DEBUG] Generated EX command:")
        print(command)
        print("="*80 + "\n")
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            return_value, error = controller._execute_ex_command(command)
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            
            if return_value is not None and return_value < 0:
                raise RuntimeError(f"EX command returned error code: {return_value}")
            
            time.sleep(0.2)
            
            # Query data from GP parameters
            set_v = self._query_gp_data(controller, 20, array_size, "setV")
            set_i = self._query_gp_data(controller, 22, array_size, "setI")
            pulse_times = self._query_gp_data(controller, 31, array_size, "PulseTimes")
            
            if not pulse_times:
                # Generate approximate times
                pulse_times = [i * (meas_width + meas_delay) for i in range(len(set_v))]
            
            # Calculate resistances
            resistances: List[float] = []
            for voltage, current in zip(set_v, set_i):
                if abs(current) > 1e-12:
                    resistances.append(voltage / current)
                else:
                    resistances.append(float('inf') if voltage > 0 else float('-inf'))
            
            # Ensure all lists are same length
            min_len = min(len(set_v), len(set_i), len(pulse_times), len(resistances))
            set_v = set_v[:min_len]
            set_i = set_i[:min_len]
            pulse_times = pulse_times[:min_len]
            resistances = resistances[:min_len]
            
            return pulse_times, set_v, set_i, resistances
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    # ============================================================================
    # Phase 1: Direct Script Wrappers
    # ============================================================================
    
    def pulse_read_repeat(self, pulse_voltage: float = 1.0, 
                         pulse_width: float = 1e-6,  # seconds (default 1 µs)
                         read_voltage: float = 0.2,
                         delay_between: float = 10e-6,  # seconds (default 10 µs)
                         num_cycles: int = 10,
                         clim: float = 100e-3,
                         read_width: float = 0.5e-6,  # seconds (default 0.5 µs)
                         read_delay: float = 1e-6,  # seconds (default 1 µs)
                         read_rise_time: float = 0.1e-6,  # seconds (default 0.1 µs)
                         enable_debug_output: bool = True) -> Dict:
        """(Pulse → Read → Delay) × N cycles.
        
        Pattern: Initial Read → (Pulse → Read → Delay) × N
        Basic pulse response with immediate read after each pulse.
        Uses pmu_pulse_read_interleaved module for better performance.
        Uses C code loops (not Python loops) for efficiency.
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (seconds) - C code expects seconds
            read_voltage: Read voltage (V)
            delay_between: Delay between cycles (seconds) - C code expects seconds
            num_cycles: Number of cycles (handled by C code, not Python loop)
            clim: Current limit (A)
            read_width: Read pulse width (seconds) - C code expects seconds [4200A only]
            read_delay: Read delay after measurement (seconds) - C code expects seconds [4200A only]
            read_rise_time: Read rise/fall time (seconds) - C code expects seconds [4200A only]
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        # Parameters are already in seconds from system wrapper (converted from µs)
        # No conversion needed - pass directly to C module
        pulse_width_s = pulse_width
        delay_between_s = delay_between
        read_width_s = read_width
        read_delay_s = read_delay
        read_rise_s = read_rise_time
        
        # Print values for verification (already in seconds)
        print(f"\n[KXCI] Parameter Values (in SECONDS as expected by C module):")
        print(f"  pulse_width: {pulse_width_s:.2e} s ({pulse_width_s*1e6:.2f} µs)")
        print(f"  delay_between: {delay_between_s:.2e} s ({delay_between_s*1e6:.2f} µs)")
        print(f"  read_width: {read_width_s:.2e} s ({read_width_s*1e6:.2f} µs)")
        print(f"  read_delay: {read_delay_s:.2e} s ({read_delay_s*1e6:.2f} µs)")
        print(f"  read_rise_time: {read_rise_s:.2e} s ({read_rise_s*1e6:.2f} µs)")
        
        # Enforce minimum segment time (2e-8 seconds = 20 ns) to prevent error -207
        MIN_SEGMENT_TIME = 2e-8
        MAX_SEGMENT_TIME = 1.0  # Maximum segment time (1 second)
        pulse_width_s = max(MIN_SEGMENT_TIME, min(pulse_width_s, MAX_SEGMENT_TIME))
        read_width_s = max(MIN_SEGMENT_TIME, min(read_width_s, MAX_SEGMENT_TIME))
        read_delay_s = max(MIN_SEGMENT_TIME, min(read_delay_s, MAX_SEGMENT_TIME))
        delay_between_s = max(MIN_SEGMENT_TIME, min(delay_between_s, MAX_SEGMENT_TIME))
        read_rise_s = max(MIN_SEGMENT_TIME, min(read_rise_s, MAX_SEGMENT_TIME))
        
        # Validate that read_width is reasonable (should be in µs range, not seconds)
        # If read_width_s is > 1e-3 (1 ms), it's likely a unit conversion error
        if read_width_s > 1e-3:
            raise ValueError(f"read_width appears to be in wrong units. Got {read_width_s*1e6:.2f} µs ({read_width_s:.2e} s). "
                           f"Expected value should be < 1000 µs. Check unit conversion.")
        
        # Use interleaved module: Pattern is Initial Read → (Pulse → Read) × N cycles
        # All cycles handled by C code (num_cycles parameter)
        # Pattern: Pulse immediately followed by Read, then delay before next cycle
        pulse_edge = self._select_edge_time(pulse_width_s)
        read_edge = self._select_edge_time(read_width_s, read_rise_s)
        cfg = PulseReadInterleavedConfig(
            num_cycles=num_cycles,  # Number of (pulse → read) cycles - C code handles loop
            num_pulses_per_group=1,  # One pulse per cycle
            num_reads=1,  # One read per cycle
            pulse_v=pulse_voltage,
            pulse_width=pulse_width_s,
            pulse_rise_time=pulse_edge,
            pulse_fall_time=pulse_edge,
            pulse_delay=2e-8,  # Minimal delay after pulse (minimum valid segment time, read happens immediately after pulse)
            # Enforce minimum segment time (2e-8 seconds = 20 ns) to prevent error -207
            # Round up values that are very close to minimum to avoid floating point precision issues
            meas_v=read_voltage,  # Use user's read voltage
            meas_width=read_width_s,  # Use user's read width
            meas_delay=delay_between_s,  # Delay after read (before next cycle) - this is the cycle-to-cycle delay
            rise_time=read_edge,  # Fast rise/fall for measurement window
            i_range=1e-4,  # Default current range
            max_points=10000,  # Default, will be adjusted if needed
            iteration=1,
            clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
        )
        cfg.validate()
        
        # Ensure max_points is sufficient for rate calculation (especially for long measurements)
        self._ensure_valid_interleaved_max_points(cfg)
        
        timestamps, voltages, currents, resistances = self._run_interleaved_with_fallback(cfg)
        self._print_results_table(timestamps, voltages, currents, resistances)
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def multi_pulse_then_read(self, pulse_voltage: float = 1.0,
                             num_pulses_per_read: int = 10,
                             pulse_width: float = 100.0,
                             delay_between_pulses: float = 1000.0,
                             read_voltage: float = 0.2,
                             num_reads: int = 1,
                             delay_between_reads: float = 10000.0,
                             num_cycles: int = 20,
                             delay_between_cycles: float = 10000.0,
                             clim: float = 100e-3,
                             enable_debug_output: bool = True) -> Dict:
        """Multiple pulses then multiple reads per cycle.
        
        Pattern: Initial Read → (Pulse×N → Read×M) × Cycles
        Uses pmu_pulse_read_interleaved module for better performance.
        Uses C code loops (not Python loops) for efficiency.
        
        Args:
            pulse_voltage: Pulse voltage (V)
            num_pulses_per_read: Number of pulses per cycle
            pulse_width: Pulse width (seconds) - already converted in system wrapper
            delay_between_pulses: Delay between pulses (seconds) - already converted
            read_voltage: Read voltage (V)
            num_reads: Number of reads per cycle
            delay_between_reads: Delay between reads (seconds) - already converted
            num_cycles: Number of cycles (handled by C code, not Python loop)
            delay_between_cycles: Delay between cycles (seconds) - not used (C code handles cycles)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        pulse_width_s = pulse_width
        delay_between_pulses_s = delay_between_pulses
        delay_between_reads_s = delay_between_reads
        
        # Print values for verification (already in seconds)
        print(f"\n[KXCI] Parameter Values (in SECONDS as expected by C module):")
        print(f"  pulse_width: {pulse_width_s:.2e} s ({pulse_width_s*1e6:.2f} µs)")
        print(f"  delay_between_pulses: {delay_between_pulses_s:.2e} s ({delay_between_pulses_s*1e6:.2f} µs)")
        print(f"  delay_between_reads: {delay_between_reads_s:.2e} s ({delay_between_reads_s*1e6:.2f} µs)")
        
        # Enforce minimum segment time (20 ns)
        MIN_SEGMENT_TIME = 2e-8
        pulse_width_s = max(pulse_width_s, MIN_SEGMENT_TIME)
        delay_between_pulses_s = max(delay_between_pulses_s, MIN_SEGMENT_TIME)
        delay_between_reads_s = max(delay_between_reads_s, MIN_SEGMENT_TIME)
        
        pulse_edge = self._select_edge_time(pulse_width_s)
        # Use interleaved module: Pattern is Initial Read → (Pulses×N → Reads×M) × Cycles
        # All cycles handled by C code (num_cycles parameter)
        cfg = PulseReadInterleavedConfig(
            num_cycles=num_cycles,  # C code handles all cycles in one call
            num_pulses_per_group=num_pulses_per_read,  # N pulses per cycle
            num_reads=num_reads,  # M reads per cycle
            pulse_v=pulse_voltage,
            pulse_width=pulse_width_s,
            pulse_rise_time=pulse_edge,
            pulse_fall_time=pulse_edge,
            pulse_delay=delay_between_pulses_s,  # Delay between pulses
            meas_v=read_voltage,
            meas_width=0.5e-6,  # Measurement window
            meas_delay=delay_between_reads_s,  # Delay between reads
            i_range=1e-4,
            max_points=10000,  # Will be updated by _ensure_valid_interleaved_max_points
            iteration=1,
            clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
        )
        cfg.validate()
        
        # Ensure max_points is sufficient for rate calculation (especially for long measurements)
        self._ensure_valid_interleaved_max_points(cfg)
        
        print(f"[KXCI] Calculated max_points: {cfg.max_points} for estimated time: {self._estimate_interleaved_total_time(cfg):.6f} s")
        
        timestamps, voltages, currents, resistances = self._run_interleaved_with_fallback(cfg)
        self._print_results_table(timestamps, voltages, currents, resistances)
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def potentiation_only(self, set_voltage: float = 2.0,
                         pulse_width: float = 100.0,
                         read_voltage: float = 0.2,
                         num_pulses: int = 30,
                         delay_between: float = 10000.0,
                         delay_between_pulses: Optional[float] = None,
                         delay_before_read: float = 10.0,
                         read_width: float = 0.5,
                         num_post_reads: int = 0,
                         post_read_interval: float = 1000.0,
                         num_cycles: int = 1,
                         delay_between_cycles: float = 0.0,
                         clim: float = 100e-3,
                         enable_debug_output: bool = True) -> Dict:
        """Repeated SET pulses with reads. Can be repeated multiple cycles.
        
        Pattern: (Initial Read → Repeated SET pulses with reads) × N cycles
        Uses pmu_pulse_read_interleaved module for better performance.
        Uses C code loops (not Python loops) for efficiency.
        
        Args:
            set_voltage: SET voltage (V, positive)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            num_pulses: Number of pulses per cycle
            delay_between: Delay between pulses (µs)
            delay_between_pulses: Override delay between pulses (µs)
            delay_before_read: Delay from pulse end to read (µs)
            read_width: Read window width (µs)
            num_post_reads: Post-pulse reads (0=disabled, uses 1 read per pulse)
            post_read_interval: Post-read interval (µs)
            num_cycles: Number of cycles to repeat (handled by C code if num_cycles > 1)
            delay_between_cycles: Delay between cycles (seconds, default: 0) - only used if Python loop needed
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, cycle_numbers
        """
        pulse_width_s = self._convert_us_to_seconds(pulse_width)
        if delay_between_pulses is None:
            delay_between_pulses = delay_between
        pulse_delay_s = self._convert_us_to_seconds(delay_between_pulses)
        meas_delay_s = self._convert_us_to_seconds(delay_before_read)
        post_read_interval_s = self._convert_us_to_seconds(post_read_interval)
        meas_width_s = self._convert_us_to_seconds(read_width)
        
        # Enforce minimum segment time (2e-8 seconds = 20 ns) to prevent error -207
        MIN_SEGMENT_TIME = 2e-8
        pulse_width_s = max(pulse_width_s, MIN_SEGMENT_TIME)
        pulse_delay_s = max(pulse_delay_s, MIN_SEGMENT_TIME)
        meas_delay_s = max(meas_delay_s, MIN_SEGMENT_TIME)
        meas_width_s = max(meas_width_s, MIN_SEGMENT_TIME)
        post_read_interval_s = max(post_read_interval_s, MIN_SEGMENT_TIME)
        
        # Pattern: Initial Read → (Pulse → Read) × N pulses
        # Each pulse is followed by a read, so num_cycles = num_pulses
        num_reads_per_pulse = max(num_post_reads, 1)  # At least 1 read per pulse
        
        # Use C code loop: num_cycles in C module handles all pulses
        # If num_cycles > 1, we need to handle that at a higher level (multiple cycles of pulses)
        # For now, if num_cycles > 1, we'll use Python loop but should ideally refactor C module
        # to support: Initial Read → (Pulse×N → Read×M) × Cycles
        if num_cycles == 1:
            # Single cycle: use C code loop for all pulses
            cfg = PulseReadInterleavedConfig(
                num_cycles=num_pulses,  # C code handles all pulses in one call
                num_pulses_per_group=1,  # One pulse per cycle
                num_reads=num_reads_per_pulse,  # Reads after each pulse
                pulse_v=abs(set_voltage),  # Ensure positive
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=pulse_delay_s,  # Delay between pulse and read
                meas_v=read_voltage,
                meas_width=meas_width_s,  # Measurement window
                meas_delay=post_read_interval_s if num_post_reads > 0 else meas_delay_s,  # Delay after read
                i_range=1e-4,
                max_points=10000,
                iteration=1,
                clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
            )
            cfg.validate()
            
            # Ensure max_points is sufficient for rate calculation (especially for long measurements)
            self._ensure_valid_interleaved_max_points(cfg)
            
            timestamps, voltages, currents, resistances = self._run_interleaved_with_fallback(cfg)
            
            return self._format_results(timestamps, voltages, currents, resistances)
        else:
            # Multiple cycles: use Python loop (TODO: refactor C module to support this natively)
            all_timestamps: List[float] = []
            all_voltages: List[float] = []
            all_currents: List[float] = []
            all_resistances: List[float] = []
            cycle_numbers: List[int] = []
            
            for cycle in range(num_cycles):
                cfg = PulseReadInterleavedConfig(
                    num_cycles=num_pulses,  # C code handles all pulses in one call
                    num_pulses_per_group=1,
                    num_reads=num_reads_per_pulse,
                    pulse_v=abs(set_voltage),
                    pulse_width=pulse_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=pulse_delay_s,
                    meas_v=read_voltage,
                    meas_width=meas_width_s,
                    meas_delay=post_read_interval_s if num_post_reads > 0 else meas_delay_s,
                    i_range=1e-4,
                    max_points=10000,
                    iteration=1,
                    clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
                )
                cfg.validate()
                
                timestamps, voltages, currents, resistances = self._run_interleaved_with_fallback(cfg)
                
                all_timestamps.extend(timestamps)
                all_voltages.extend(voltages)
                all_currents.extend(currents)
                all_resistances.extend(resistances)
                cycle_numbers.extend([cycle] * len(timestamps))
                
                if cycle < num_cycles - 1 and delay_between_cycles > 0:
                    time.sleep(delay_between_cycles)
            
            return self._format_results(
                all_timestamps, all_voltages, all_currents, all_resistances,
                cycle_numbers=cycle_numbers
            )
    
    def depression_only(self, reset_voltage: float = -2.0,
                       pulse_width: float = 100.0,
                       read_voltage: float = 0.2,
                       num_pulses: int = 30,
                       delay_between: float = 10000.0,
                       delay_between_pulses: Optional[float] = None,
                       delay_before_read: float = 10.0,
                       read_width: float = 0.5,
                       num_post_reads: int = 0,
                       post_read_interval: float = 1000.0,
                       num_cycles: int = 1,
                       delay_between_cycles: float = 0.0,
                       clim: float = 100e-3,
                       enable_debug_output: bool = True) -> Dict:
        """Repeated RESET pulses with reads. Can be repeated multiple cycles.
        
        Pattern: (Initial Read → Repeated RESET pulses with reads) × N cycles
        Uses pmu_pulse_read_interleaved module for better performance.
        Uses C code loops (not Python loops) for efficiency.
        
        Args:
            reset_voltage: RESET voltage (V, negative)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            num_pulses: Number of pulses per cycle
            delay_between: Delay between pulses (µs)
            delay_between_pulses: Override delay between pulses (µs)
            delay_before_read: Delay from pulse end to read (µs)
            read_width: Read window width (µs)
            num_post_reads: Post-pulse reads (0=disabled, uses 1 read per pulse)
            post_read_interval: Post-read interval (µs)
            num_cycles: Number of cycles to repeat (handled by C code if num_cycles > 1)
            delay_between_cycles: Delay between cycles (seconds, default: 0) - only used if Python loop needed
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, cycle_numbers
        """
        pulse_width_s = self._convert_us_to_seconds(pulse_width)
        if delay_between_pulses is None:
            delay_between_pulses = delay_between
        pulse_delay_s = self._convert_us_to_seconds(delay_between_pulses)
        meas_delay_s = self._convert_us_to_seconds(delay_before_read)
        post_read_interval_s = self._convert_us_to_seconds(post_read_interval)
        meas_width_s = self._convert_us_to_seconds(read_width)
        
        # Enforce minimum segment time (2e-8 seconds = 20 ns) to prevent error -207
        MIN_SEGMENT_TIME = 2e-8
        pulse_width_s = max(pulse_width_s, MIN_SEGMENT_TIME)
        pulse_delay_s = max(pulse_delay_s, MIN_SEGMENT_TIME)
        meas_delay_s = max(meas_delay_s, MIN_SEGMENT_TIME)
        meas_width_s = max(meas_width_s, MIN_SEGMENT_TIME)
        post_read_interval_s = max(post_read_interval_s, MIN_SEGMENT_TIME)
        
        # Pattern: Initial Read → (Pulse → Read) × N pulses
        num_reads_per_pulse = max(num_post_reads, 1)  # At least 1 read per pulse
        
        if num_cycles == 1:
            # Single cycle: use C code loop for all pulses
            cfg = PulseReadInterleavedConfig(
                num_cycles=num_pulses,  # C code handles all pulses in one call
                num_pulses_per_group=1,  # One pulse per cycle
                num_reads=num_reads_per_pulse,  # Reads after each pulse
                pulse_v=reset_voltage,  # Negative for RESET
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=pulse_delay_s,  # Delay between pulse and read
                meas_v=read_voltage,
                meas_width=meas_width_s,  # Measurement window
                meas_delay=post_read_interval_s if num_post_reads > 0 else meas_delay_s,  # Delay after read
                i_range=1e-4,
                max_points=10000,
                iteration=1,
                clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
            )
            cfg.validate()
            
            # Ensure max_points is sufficient for rate calculation (especially for long measurements)
            self._ensure_valid_interleaved_max_points(cfg)
            
            timestamps, voltages, currents, resistances = self._run_interleaved_with_fallback(cfg)
            
            return self._format_results(timestamps, voltages, currents, resistances)
        else:
            # Multiple cycles: use Python loop (TODO: refactor C module to support this natively)
            all_timestamps: List[float] = []
            all_voltages: List[float] = []
            all_currents: List[float] = []
            all_resistances: List[float] = []
            cycle_numbers: List[int] = []
            
            for cycle in range(num_cycles):
                cfg = PulseReadInterleavedConfig(
                    num_cycles=num_pulses,  # C code handles all pulses in one call
                    num_pulses_per_group=1,
                    num_reads=num_reads_per_pulse,
                    pulse_v=reset_voltage,
                    pulse_width=pulse_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=pulse_delay_s,
                    meas_v=read_voltage,
                    meas_width=meas_width_s,
                    meas_delay=post_read_interval_s if num_post_reads > 0 else meas_delay_s,
                    i_range=1e-4,
                    max_points=10000,
                    iteration=1,
                    clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
                )
                cfg.validate()
                
                timestamps, voltages, currents, resistances = self._run_interleaved_with_fallback(cfg)
                
                all_timestamps.extend(timestamps)
                all_voltages.extend(voltages)
                all_currents.extend(currents)
                all_resistances.extend(resistances)
                cycle_numbers.extend([cycle] * len(timestamps))
                
                if cycle < num_cycles - 1 and delay_between_cycles > 0:
                    time.sleep(delay_between_cycles)
            
            return self._format_results(
                all_timestamps, all_voltages, all_currents, all_resistances,
                cycle_numbers=cycle_numbers
            )
    
    def potentiation_depression_alternating(self, set_voltage: float = 2.0,
                                          reset_voltage: float = -2.0,
                                          pulse_width: float = 100.0,
                                          read_voltage: float = 0.2,
                                          num_pulses_per_cycle: int = 10,
                                          delay_between: float = 10000.0,
                                          num_post_reads: int = 0,
                                          post_read_interval: float = 1000.0,
                                          num_cycles: int = 5,
                                          delay_between_cycles: float = 0.0,
                                          clim: float = 100e-3) -> Dict:
        """Alternating potentiation and depression cycles.
        
        Pattern: (Potentiation → Depression) × N cycles
        This allows you to see the device behavior as it switches between
        high and low resistance states repeatedly.
        
        Args:
            set_voltage: SET voltage (V, positive)
            reset_voltage: RESET voltage (V, negative)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            num_pulses_per_cycle: Number of pulses per potentiation/depression cycle
            delay_between: Delay between pulses (µs) - NOTE: Not used, fixed to 1e-6 internally
            num_post_reads: Post-pulse reads (0=disabled)
            post_read_interval: Post-read interval (µs) - NOTE: Not used, fixed to 2e-6 internally
            num_cycles: Number of (potentiation + depression) cycles (default: 5)
            delay_between_cycles: Delay between cycles (seconds, default: 0)
            clim: Current limit (A) - NOTE: Not used, fixed to 1e-4 internally
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, cycle_numbers
            cycle_numbers: 0=first potentiation, 1=first depression, 2=second potentiation, etc.
        """
        delay_between_cycles_s = delay_between_cycles  # Already in seconds
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        cycle_numbers: List[int] = []
        
        for cycle in range(num_cycles):
            # Potentiation (SET) cycle
            pot_results = self.potentiation_only(
                set_voltage=set_voltage,
                pulse_width=pulse_width,
                read_voltage=read_voltage,
                num_pulses=num_pulses_per_cycle,
                delay_between=delay_between,
                num_post_reads=num_post_reads,
                post_read_interval=post_read_interval,
                num_cycles=1,  # Single cycle
                delay_between_cycles=0.0,
                clim=clim
            )
            
            all_timestamps.extend(pot_results['timestamps'])
            all_voltages.extend(pot_results['voltages'])
            all_currents.extend(pot_results['currents'])
            all_resistances.extend(pot_results['resistances'])
            # Even cycles (0, 2, 4, ...) are potentiation
            cycle_numbers.extend([cycle * 2] * len(pot_results['timestamps']))
            
            # Small delay between potentiation and depression
            if delay_between_cycles_s > 0:
                time.sleep(delay_between_cycles_s)
            
            # Depression (RESET) cycle
            dep_results = self.depression_only(
                reset_voltage=reset_voltage,
                pulse_width=pulse_width,
                read_voltage=read_voltage,
                num_pulses=num_pulses_per_cycle,
                delay_between=delay_between,
                num_post_reads=num_post_reads,
                post_read_interval=post_read_interval,
                num_cycles=1,  # Single cycle
                delay_between_cycles=0.0,
                clim=clim
            )
            
            all_timestamps.extend(dep_results['timestamps'])
            all_voltages.extend(dep_results['voltages'])
            all_currents.extend(dep_results['currents'])
            all_resistances.extend(dep_results['resistances'])
            # Odd cycles (1, 3, 5, ...) are depression
            cycle_numbers.extend([cycle * 2 + 1] * len(dep_results['timestamps']))
            
            # Delay between full cycles (except after last cycle)
            if cycle < num_cycles - 1 and delay_between_cycles_s > 0:
                time.sleep(delay_between_cycles_s)
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            cycle_numbers=cycle_numbers
        )
    
    def pulse_multi_read(self, pulse_voltage: float = 1.0,
                        pulse_width: float = 100.0,
                        num_pulses: int = 1,
                        delay_between_pulses: float = 1000.0,
                        read_voltage: float = 0.2,
                        num_reads: int = 50,
                        delay_between_reads: float = 100e-6,
                        read_width: float = 0.5e-6,
                        clim: float = 100e-3,
                        enable_debug_output: bool = True) -> Dict:
        """Pulse then multiple reads to monitor relaxation.
        
        Pattern: Initial Read → (Pulse × M) → Read × N
        Uses pmu_pulse_read_interleaved module for better performance.
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (seconds) - already converted from µs by system wrapper
            num_pulses: Number of pulses
            delay_between_pulses: Delay between pulses (seconds) - already converted from µs
            read_voltage: Read voltage (V)
            num_reads: Number of reads
            delay_between_reads: Delay between reads (seconds) - already converted from µs
            read_width: Read window width (seconds) - already converted from µs
            clim: Current limit (A)
            enable_debug_output: Enable debug output from C module (default: True)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        # Parameters are already in seconds from system wrapper (converted from µs)
        # No conversion needed - pass directly to C module
        pulse_width_s = pulse_width
        delay_between_pulses_s = delay_between_pulses
        delay_between_reads_s = delay_between_reads
        read_width_s = read_width
        
        # Print values for verification (already in seconds)
        print(f"\n[KXCI] Parameter Values Sent to C Module (in SECONDS as expected by C code):")
        print(f"  Configuration: num_pulses={num_pulses}, num_reads={num_reads}")
        print(f"  Expected total measurements: {1 + num_reads}")
        print(f"  Timing parameters (seconds):")
        print(f"    pulse_width={pulse_width_s:.2e} s ({pulse_width_s*1e6:.2f} µs)")
        print(f"    delay_between_pulses={delay_between_pulses_s:.2e} s ({delay_between_pulses_s*1e6:.2f} µs)")
        print(f"    delay_between_reads={delay_between_reads_s:.2e} s ({delay_between_reads_s*1e6:.2f} µs)")
        print(f"    read_width={read_width_s:.2e} s ({read_width_s*1e6:.2f} µs)")
        print(f"  Voltage parameters:")
        print(f"    pulse_v={pulse_voltage} V")
        print(f"    meas_v={read_voltage} V")
        print(f"  Other parameters:")
        print(f"    i_range=1.00e-04 A")
        
        # Enforce minimum segment time (2e-8 seconds = 20 ns) to prevent error -207
        MIN_SEGMENT_TIME = 2e-8
        MAX_SEGMENT_TIME = 1.0
        pulse_width_s = max(MIN_SEGMENT_TIME, min(pulse_width_s, MAX_SEGMENT_TIME))
        delay_between_pulses_s = max(MIN_SEGMENT_TIME, min(delay_between_pulses_s, MAX_SEGMENT_TIME))
        delay_between_reads_s = max(MIN_SEGMENT_TIME, min(delay_between_reads_s, MAX_SEGMENT_TIME))
        read_width_s = max(MIN_SEGMENT_TIME, min(read_width_s, MAX_SEGMENT_TIME))
        
        pulse_edge = self._select_edge_time(pulse_width_s)
        read_edge = self._select_edge_time(read_width_s)
        
        # Pattern: Initial Read → (Pulses×M) → Reads×N
        cfg = PulseReadInterleavedConfig(
            num_cycles=1,  # One cycle: pulses then reads
            num_pulses_per_group=num_pulses,  # M pulses
            num_reads=num_reads,  # N reads
            pulse_v=pulse_voltage,
            pulse_width=pulse_width_s,
            pulse_rise_time=pulse_edge,
            pulse_fall_time=pulse_edge,
            pulse_delay=delay_between_pulses_s,  # Delay between pulses
            meas_v=read_voltage,
            meas_width=read_width_s,  # Measurement window
            meas_delay=delay_between_reads_s,  # Delay between reads
            rise_time=read_edge,
            i_range=1e-4,
            max_points=10000,  # Will be updated by _ensure_valid_interleaved_max_points
            iteration=1,
            clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
        )
        cfg.validate()
        
        # Ensure max_points is sufficient for rate calculation (especially for long measurements)
        self._ensure_valid_interleaved_max_points(cfg)
        
        print(f"[KXCI] Calculated max_points: {cfg.max_points} for estimated time: {self._estimate_interleaved_total_time(cfg):.6f} s")
        print(f"⏳ Waiting for measurement to complete...")
        
        timestamps, voltages, currents, resistances = self._run_interleaved_with_fallback(cfg)
        
        self._print_results_table(timestamps, voltages, currents, resistances)
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def multi_read_only(self, read_voltage: float = 0.2,
                       num_reads: int = 100,
                       delay_between: float = 100000.0,
                       clim: float = 100e-3) -> Dict:
        """Just reads, no pulses.
        
        Pattern: Just reads, no pulses
        Baseline noise, read disturb characterization.
        
        Args:
            read_voltage: Read voltage (V)
            num_reads: Number of reads
            delay_between: Delay between reads (µs) - NOTE: readtrain uses fixed 1e-6 delay internally
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        # NOTE: The readtrain C module uses a fixed meas_delay of 1e-6 internally
        # The delay_between parameter is ignored for readtrain - it always uses 1e-6
        # This matches the working example: meas_delay = 1.00E-6
        meas_width = 2e-6
        meas_delay = 1e-6  # Fixed to match working example - readtrain doesn't support variable delays
        i_range = self._convert_clim_to_i_range(clim)
        
        print(f"[WARN] multi_read_only: delay_between={delay_between}ms is ignored. "
              f"readtrain uses fixed meas_delay=1e-6 (1µs)")
        
        timestamps, voltages, currents, resistances = self._execute_readtrain(
            numb_meas_pulses=num_reads,
            meas_v=read_voltage,  # readtrain allows user-specified meas_v
            meas_width=meas_width,
            meas_delay=meas_delay,  # Fixed to 1e-6 for readtrain (C module requirement)
            i_range=i_range
        )
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def relaxation_after_multi_pulse(self, pulse_voltage: float = 1.5,
                                    num_pulses: int = 10,
                                    pulse_width: float = 100.0,
                                    delay_between_pulses: float = 10.0,
                                    read_voltage: float = 0.2,
                                    num_reads: int = 20,
                                    delay_between_reads: float = 100.0,
                                    read_width: float = 0.5e-6,
                                    clim: float = 100e-3,
                                    enable_debug_output: bool = True) -> Dict:
        """Monitor relaxation after cumulative pulsing.
        
        Pattern: 1×Read → N×Pulse → N×Read
        Uses pmu_pulse_read_interleaved module for better performance.
        
        Args:
            pulse_voltage: Pulse voltage (V)
            num_pulses: Number of pulses
            pulse_width: Pulse width (µs)
            delay_between_pulses: Delay between pulses (µs)
            read_voltage: Read voltage (V)
            num_reads: Number of reads
            delay_between_reads: Delay between reads (µs)
            read_width: Read window width (seconds) - already converted from µs
            clim: Current limit (A)
            enable_debug_output: Enable debug output from C module (default: True)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        """
        pulse_width_s = pulse_width
        delay_between_pulses_s = delay_between_pulses
        delay_between_reads_s = delay_between_reads
        read_width_s = read_width
        
        print(f"\n[KXCI] relaxation_after_multi_pulse parameter values (in SECONDS):")
        print(f"  pulse_width: {pulse_width_s:.2e} s ({pulse_width_s*1e6:.2f} µs)")
        print(f"  delay_between_pulses: {delay_between_pulses_s:.2e} s ({delay_between_pulses_s*1e6:.2f} µs)")
        print(f"  delay_between_reads: {delay_between_reads_s:.2e} s ({delay_between_reads_s*1e6:.2f} µs)")
        print(f"  read_width: {read_width_s:.2e} s ({read_width_s*1e6:.2f} µs)")
        
        MIN_SEGMENT_TIME = 2e-8
        MAX_SEGMENT_TIME = 1.0
        pulse_width_s = max(MIN_SEGMENT_TIME, min(pulse_width_s, MAX_SEGMENT_TIME))
        delay_between_pulses_s = max(MIN_SEGMENT_TIME, min(delay_between_pulses_s, MAX_SEGMENT_TIME))
        delay_between_reads_s = max(MIN_SEGMENT_TIME, min(delay_between_reads_s, MAX_SEGMENT_TIME))
        read_width_s = max(MIN_SEGMENT_TIME, min(read_width_s, MAX_SEGMENT_TIME))
        
        pulse_edge = self._select_edge_time(pulse_width_s)
        read_edge = self._select_edge_time(read_width_s)
        
        # Pattern: Initial Read → (Pulses×N) → Reads×N
        cfg = PulseReadInterleavedConfig(
            num_cycles=1,  # One cycle: pulses then reads
            num_pulses_per_group=num_pulses,  # N pulses
            num_reads=num_reads,  # N reads
            pulse_v=pulse_voltage,
            pulse_width=pulse_width_s,
            pulse_rise_time=pulse_edge,
            pulse_fall_time=pulse_edge,
            pulse_delay=delay_between_pulses_s,  # Delay between pulses
            meas_v=read_voltage,
            meas_width=read_width_s,  # Measurement window
            meas_delay=delay_between_reads_s,  # Delay between reads
            rise_time=read_edge,
            i_range=1e-4,
            max_points=10000,  # Will be updated by _ensure_valid_interleaved_max_points
            iteration=1,
            clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
        )
        cfg.validate()
        
        # Ensure max_points is sufficient for rate calculation (especially for long measurements)
        self._ensure_valid_interleaved_max_points(cfg)
        
        timestamps, voltages, currents, resistances = self._run_interleaved_with_fallback(cfg)
        
        return self._format_results(timestamps, voltages, currents, resistances)
    
    # ============================================================================
    # Phase 2: Multi-Script Composition Tests
    # ============================================================================
    
    def width_sweep_with_reads(self, pulse_voltage: float = 1.5,
                              pulse_widths: List[float] = None,
                              read_voltage: float = 0.2,
                              num_pulses_per_width: int = 5,
                              reset_voltage: float = -1.0,
                              reset_width: float = 1000.0,
                              delay_between_widths: float = 5.0,
                              clim: float = 100e-3,
                              enable_debug_output: bool = True) -> Dict:
        """Width sweep: For each width, pulse then read.
        
        Pattern: For each width: Initial Read → (Pulse→Read)×N → Reset
        Uses pmu_pulse_read_interleaved module for better performance.
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_widths: List of pulse widths (µs) - will be converted to seconds
            read_voltage: Read voltage (V)
            num_pulses_per_width: Pulses per width
            reset_voltage: Reset voltage (V)
            reset_width: Reset width (µs)
            delay_between_widths: Delay between widths (s)
            clim: Current limit (A)
            enable_debug_output: Enable debug output from C module (default: True)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, widths
        """
        if pulse_widths is None:
            pulse_widths = [10.0, 50.0, 100.0, 500.0, 1000.0]  # Default in µs
        
        # Convert µs to seconds
        pulse_widths_s = [self._convert_us_to_seconds(w) for w in pulse_widths]
        reset_width_s = self._convert_us_to_seconds(reset_width)
        delay_between_widths_s = delay_between_widths  # Already in seconds
        
        print("\n[KXCI] Width Sweep Parameters:")
        print(f"  Pulse widths (s): {[f'{w:.2e}' for w in pulse_widths_s]}")
        print(f"  Reset width: {reset_width_s:.2e} s ({reset_width_s*1e6:.2f} µs)")
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        widths: List[float] = []
        
        for width_idx, width_s in enumerate(pulse_widths_s):
            # Pattern: Initial Read → (Pulse → Read) × N
            # Use interleaved module for each width
            cfg = PulseReadInterleavedConfig(
                num_cycles=num_pulses_per_width,  # N cycles of (pulse → read)
                num_pulses_per_group=1,  # One pulse per cycle
                num_reads=1,  # One read per cycle
                pulse_v=pulse_voltage,
                pulse_width=width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=1e-6,  # Delay between pulse and read
                meas_v=read_voltage,
                meas_width=0.5e-6,  # Measurement window
                meas_delay=1e-6,  # Delay after read
                i_range=1e-4,
                max_points=10000,  # Will be updated by _ensure_valid_interleaved_max_points
                iteration=1,
                clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
            )
            cfg.validate()
            
            # Ensure max_points is sufficient for rate calculation (especially for long measurements)
            self._ensure_valid_interleaved_max_points(cfg)
            
            timestamps, voltages, currents, resistances = self._run_interleaved_with_fallback(cfg)
            
            # Return all data - no filtering
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            widths.extend([pulse_widths[width_idx]] * len(timestamps))
            
            # Reset between widths (except last) - use interleaved module for reset
            if width_idx < len(pulse_widths_s) - 1:
                reset_cfg = PulseReadInterleavedConfig(
                    num_cycles=1,  # Single reset pulse
                    num_pulses_per_group=1,  # One reset pulse
                    num_reads=1,  # One read after reset
                    pulse_v=reset_voltage,
                    pulse_width=reset_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=1e-6,
                    meas_v=read_voltage,
                    meas_width=0.5e-6,
                    meas_delay=1e-6,
                    i_range=1e-4,
                    max_points=10000,  # Will be updated by _ensure_valid_interleaved_max_points
                    iteration=1,
                    clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
                )
                reset_cfg.validate()
                self._ensure_valid_interleaved_max_points(reset_cfg)
                self._execute_interleaved(reset_cfg)  # Just reset, don't collect data
                
                if delay_between_widths_s > 0:
                    time.sleep(delay_between_widths_s)
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            widths=widths
        )
    
    def voltage_amplitude_sweep(self, pulse_voltage_start: float = 0.5,
                               pulse_voltage_stop: float = 2.5,
                               pulse_voltage_step: float = 0.1,
                               pulse_width: float = 100.0,
                               read_voltage: float = 0.2,
                               num_pulses_per_voltage: int = 5,
                               delay_between: float = 10000.0,
                               reset_voltage: float = -1.0,
                               reset_width: float = 1000.0,
                               delay_between_voltages: float = 1.0,
                               clim: float = 100e-3) -> Dict:
        """Voltage amplitude sweep: Test different pulse voltages.
        
        Pattern: For each voltage: Initial Read → (Pulse → Read) × N → Reset
        
        Args:
            pulse_voltage_start: Start voltage (V)
            pulse_voltage_stop: Stop voltage (V)
            pulse_voltage_step: Voltage step (V)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            num_pulses_per_voltage: Pulses per voltage
            delay_between: Delay between pulses (µs)
            reset_voltage: Reset voltage (V)
            reset_width: Reset width (µs)
            delay_between_voltages: Delay between voltages (s)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, voltages_applied
        """
        pulse_width_s = self._convert_us_to_seconds(pulse_width)
        delay_between_s = self._convert_us_to_seconds(delay_between)
        reset_width_s = self._convert_us_to_seconds(reset_width)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        # Generate voltage list
        voltage_list: List[float] = []
        v = pulse_voltage_start
        while v <= pulse_voltage_stop:
            voltage_list.append(v)
            v += pulse_voltage_step
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        voltages_applied: List[float] = []
        
        for volt_idx, pulse_v in enumerate(voltage_list):
            # num_pulses must be >= 8
            retention_reads = max(num_pulses_per_voltage, 8)
            
            cfg = RetentionConfig(
                num_initial_meas_pulses=1 if volt_idx == 0 else 0,
                num_pulses_seq=num_pulses_per_voltage,
                num_pulses=retention_reads,
                pulse_v=pulse_v,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            cfg.validate()
            
            # Ensure max_points is sufficient for rate calculation
            self._ensure_valid_max_points(cfg)
            
            timestamps, voltages, currents, resistances = self._execute_retention(cfg)
            
            # Return all data - no filtering
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            voltages_applied.extend([pulse_v] * len(timestamps))
            
            # Reset between voltages (except last)
            if volt_idx < len(voltage_list) - 1:
                reset_cfg = RetentionConfig(
                    num_initial_meas_pulses=1,  # Always include initial read to get all data
                    num_pulses_seq=1,
                    num_pulses=8,  # Minimum required (was 0, which is invalid)
                    pulse_v=reset_voltage,
                    pulse_width=reset_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=1e-6,  # Use valid delay (matches working example default)
                    meas_v=read_voltage,
                    meas_width=2e-6,
                    meas_delay=2e-6,  # Use valid delay (matches working example default: 2e-6)
                    i_range=i_range,
                )
                reset_cfg.validate()
                self._ensure_valid_max_points(reset_cfg)
                self._execute_retention(reset_cfg)
                
                if delay_between_voltages > 0:
                    time.sleep(delay_between_voltages)
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            voltages_applied=voltages_applied
        )
    
    def potentiation_depression_cycle(self, set_voltage: float = 2.0,
                                     reset_voltage: float = -2.0,
                                     pulse_width: float = 1e-6,  # seconds (default 1 µs)
                                     read_voltage: float = 0.2,
                                     steps: int = 20,
                                     num_cycles: int = 1,
                                     delay_between: float = 10e-6,  # seconds (default 10 µs)
                                     delay_between_pulses: Optional[float] = None,
                                     delay_before_read: float = 0.02e-6,  # seconds (default 0.02 µs = 20 ns)
                                     read_width: float = 0.5e-6,  # seconds (default 0.5 µs)
                                     clim: float = 100e-3,
                                     enable_debug_output: bool = True) -> Dict:
        """Potentiation-depression cycle using pmu_potentiation_depression module.
        
        Pattern: Initial Read → (Potentiation Cycle → Depression Cycle) × N cycles
        Each cycle: Read → Pulses×N → Reads×M (for potentiation), then same for depression (negative pulses)
        
        Uses pmu_potentiation_depression module for proper potentiation-depression pattern.
        
        Args:
            set_voltage: SET voltage (V, positive for potentiation)
            reset_voltage: RESET voltage (V, negative for depression)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            steps: Number of pulses per cycle (repurposed, but pattern uses num_pulses_per_group)
            num_cycles: Number of cycle pairs (M cycles, each with potentiation then depression)
            delay_between: Delay between pulses/reads (µs)
            delay_between_pulses: Override delay between pulses (µs)
            delay_before_read: Delay between pulse and read (µs)
            read_width: Measurement window width (µs)
            clim: Current limit (A)
            enable_debug_output: Enable debug output from C module
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, cycle_numbers
        """
        # Parameters are already in seconds from system wrapper (converted from µs)
        # No conversion needed - pass directly to C module
        pulse_width_s = pulse_width
        if delay_between_pulses is None:
            delay_between_pulses = delay_between
        pulse_delay_s = delay_between_pulses
        meas_delay_s = delay_before_read
        meas_width_s = read_width
        
        # Print values for verification (already in seconds)
        print(f"\n[KXCI] Parameter Values (in SECONDS as expected by C module):")
        print(f"  pulse_width: {pulse_width_s:.2e} s ({pulse_width_s*1e6:.2f} µs)")
        print(f"  delay_between_pulses: {pulse_delay_s:.2e} s ({pulse_delay_s*1e6:.2f} µs)")
        print(f"  delay_before_read: {meas_delay_s:.2e} s ({meas_delay_s*1e6:.2f} µs)")
        print(f"  read_width: {meas_width_s:.2e} s ({meas_width_s*1e6:.2f} µs)")
        
        # Enforce minimum segment time (2e-8 seconds = 20 ns) to prevent error -207
        # Round up values that are very close to minimum to avoid floating point precision issues
        MIN_SEGMENT_TIME = 2e-8
        MAX_SEGMENT_TIME = 1.0  # Maximum segment time (1 second)
        pulse_width_s = max(MIN_SEGMENT_TIME, min(pulse_width_s, MAX_SEGMENT_TIME))
        pulse_delay_s = max(MIN_SEGMENT_TIME, min(pulse_delay_s, MAX_SEGMENT_TIME))
        meas_delay_s = max(MIN_SEGMENT_TIME, min(meas_delay_s, MAX_SEGMENT_TIME))
        meas_width_s = max(MIN_SEGMENT_TIME, min(meas_width_s, MAX_SEGMENT_TIME))
        
        # Validate that read_width is reasonable (should be in µs range, not seconds)
        # If meas_width_s is > 1e-3 (1 ms), it's likely a unit conversion error
        if meas_width_s > 1e-3:
            raise ValueError(f"read_width appears to be in wrong units. Got {meas_width_s*1e6:.2f} µs ({meas_width_s:.2e} s). "
                           f"Expected value should be < 1000 µs. Check unit conversion.")
        
        i_range = self._convert_clim_to_i_range(clim)
        
        # Use potentiation-depression module: Pattern is Initial Read → (Potentiation Cycle → Depression Cycle) × N cycles
        # Each cycle pair: Potentiation (Read → Pulses×N → Reads×M) then Depression (Read → Pulses×N → Reads×M)
        # For potentiation-depression, each step is a pulse followed by a read
        # So num_pulses_per_group = steps (number of pulses in each direction)
        # And num_reads = steps (number of reads after pulses in each direction)
        num_pulses_per_group = steps
        num_reads = steps  # Number of reads after pulses (one per step)
        
        # Create config with potentiation-depression probe count formula
        # Total = 2*NumCycles + 2*NumCycles*NumReads = 2*NumCycles*(1 + NumReads)
        class PotentiationDepressionConfig(PulseReadInterleavedConfig):
            def total_probe_count(self) -> int:
                """Total measurements = 2*NumCycles + 2*NumCycles*NumReads = 2*NumCycles*(1 + NumReads)"""
                return 2 * self.num_cycles * (1 + self.num_reads)
        
        cfg = PotentiationDepressionConfig(
            num_cycles=num_cycles,  # Number of cycle pairs (potentiation + depression)
            num_pulses_per_group=num_pulses_per_group,  # Pulses per cycle
            num_reads=num_reads,  # Reads per cycle
            pulse_v=abs(set_voltage),  # Use absolute value (depression uses negative internally)
            pulse_width=pulse_width_s,
            pulse_rise_time=1e-7,
            pulse_fall_time=1e-7,
            pulse_delay=pulse_delay_s,  # Delay between pulses
            meas_v=read_voltage,
            meas_width=meas_width_s,  # Measurement window
            meas_delay=meas_delay_s,  # Delay between reads
            rise_time=1e-7,  # Rise time for reads
            i_range=i_range,
            max_points=10000,
            iteration=1,
            clarius_debug=1 if enable_debug_output else 0,  # Enable/disable debug output
        )
        cfg.validate()
        
        # Use potentiation-depression execution (special command format)
        timestamps, voltages, currents, resistances, phases = self._execute_potentiation_depression(cfg)
        
        return self._format_results(timestamps, voltages, currents, resistances, phase=phases)
    
    def _execute_potentiation_depression(self, cfg: PulseReadInterleavedConfig) -> Tuple[List[float], List[float], List[float], List[float], List[str]]:
        """Execute potentiation-depression measurement using pmu_potentiation_depression module.
        
        Returns:
            Tuple of (timestamps, voltages, currents, resistances, phases)
        """
        total_probes = cfg.total_probe_count()
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            # Build command using potentiation-depression format (function is in this file)
            command = build_potentiation_depression_ex_command(cfg)
            print(f"\n[KXCI] Generated EX command for potentiation-depression:")
            print(command)
            print(f"\n[KXCI] Parameter Values Sent to C Module (in SECONDS as expected by C code):")
            print(f"  Configuration: num_cycles={cfg.num_cycles}, num_pulses_per_group={cfg.num_pulses_per_group}, num_reads={cfg.num_reads}")
            print(f"  Expected total measurements: {total_probes}")
            print(f"  Timing parameters (seconds):")
            print(f"    pulse_width={cfg.pulse_width:.2e} s ({cfg.pulse_width*1e6:.2f} µs)")
            print(f"    pulse_delay={cfg.pulse_delay:.2e} s ({cfg.pulse_delay*1e6:.2f} µs)")
            print(f"    pulse_rise_time={cfg.pulse_rise_time:.2e} s ({cfg.pulse_rise_time*1e6:.2f} µs)")
            print(f"    pulse_fall_time={cfg.pulse_fall_time:.2e} s ({cfg.pulse_fall_time*1e6:.2f} µs)")
            print(f"    meas_width={cfg.meas_width:.2e} s ({cfg.meas_width*1e6:.2f} µs)")
            print(f"    meas_delay={cfg.meas_delay:.2e} s ({cfg.meas_delay*1e6:.2f} µs)")
            print(f"    rise_time={cfg.rise_time:.2e} s ({cfg.rise_time*1e6:.2f} µs)")
            print(f"  Voltage parameters:")
            print(f"    pulse_v={cfg.pulse_v:.2f} V")
            print(f"    meas_v={cfg.meas_v:.2f} V")
            print(f"  Other parameters:")
            print(f"    i_range={cfg.i_range:.2e} A")
            print(f"    max_points={cfg.max_points}")
            return_value, error = controller._execute_ex_command(command)
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            
            if return_value is not None and return_value < 0:
                # Error code -207 typically means "minimum segment time" violation
                # Error code -90 typically means invalid parameter or rate calculation failure
                error_msg = f"EX command returned error code: {return_value}"
                if return_value == -207:
                    error_msg += "\nThis usually indicates a minimum segment time violation."
                    error_msg += "\nAll timing parameters (pulse_width, pulse_delay, meas_width, meas_delay) must be >= 20 ns (2e-8 seconds)."
                    error_msg += f"\nCurrent values: pulse_width={cfg.pulse_width:.2e}s, pulse_delay={cfg.pulse_delay:.2e}s, meas_width={cfg.meas_width:.2e}s, meas_delay={cfg.meas_delay:.2e}s"
                elif return_value == -90:
                    error_msg += "\nThis usually indicates an invalid parameter or rate calculation failure."
                    error_msg += "\nCommon causes:"
                    error_msg += "\n  - Measurement window (read_width) too large or invalid"
                    error_msg += "\n  - Sampling rate too low (< 200000 Hz)"
                    error_msg += "\n  - Invalid timing parameters"
                    error_msg += f"\nCurrent values: pulse_width={cfg.pulse_width:.2e}s ({cfg.pulse_width*1e6:.2f}µs), pulse_delay={cfg.pulse_delay:.2e}s ({cfg.pulse_delay*1e6:.2f}µs)"
                    error_msg += f"\n  meas_width={cfg.meas_width:.2e}s ({cfg.meas_width*1e6:.2f}µs), meas_delay={cfg.meas_delay:.2e}s ({cfg.meas_delay*1e6:.2f}µs)"
                    error_msg += f"\n  num_cycles={cfg.num_cycles}, num_pulses_per_group={cfg.num_pulses_per_group}, num_reads={cfg.num_reads}"
                raise RuntimeError(error_msg)
            
            time.sleep(0.2)  # Allow data to be ready
            
            # Query return value (param 18) like the example
            param18 = self._query_gp_data(controller, 18, 1, "return_value")
            if param18:
                print(f"Param 18 (return value): {param18[0]}")
            
            # Query data from GP parameters (same as example)
            set_v = self._query_gp_data(controller, 20, total_probes, "setV")
            set_i = self._query_gp_data(controller, 22, total_probes, "setI")
            out1 = self._query_gp_data(controller, 25, total_probes, "out1")  # Output signal (VF, IF, VM, IM, or T)
            pulse_times = self._query_gp_data(controller, 31, total_probes, "PulseTimes")
            
            # Use proper timing calculation from example if pulse_times is empty
            if not pulse_times:
                pulse_times = self._compute_probe_times_pot_dep(cfg)
            
            # Fallback if still empty or wrong length
            if not pulse_times or len(pulse_times) != total_probes:
                print(f"⚠️ Warning: Expected {total_probes} timestamps, got {len(pulse_times) if pulse_times else 0}")
                pulse_times = [float(i) for i in range(total_probes)]

            # Normalize timestamps so the initial read starts at t = 0
            if pulse_times:
                start_time = pulse_times[0]
                pulse_times = [t - start_time for t in pulse_times]
            
            # Calculate resistances (same as example)
            resistances: List[float] = []
            for voltage, current in zip(set_v, set_i):
                if abs(current) < 1e-12:
                    resistances.append(float("inf"))
                else:
                    resistances.append(voltage / current)  # Don't use abs() - preserve sign
            
            # Ensure all lists are same length
            min_len = min(len(set_v), len(set_i), len(pulse_times), len(resistances))
            if min_len < total_probes:
                print(f"⚠️ Warning: Data length mismatch. Expected {total_probes}, got {min_len}")
            set_v = set_v[:min_len]
            set_i = set_i[:min_len]
            pulse_times = pulse_times[:min_len]
            resistances = resistances[:min_len]
            
            # Generate phase information for plotting
            phases = self._generate_phases_pot_dep(cfg, min_len)
            
            return pulse_times, set_v, set_i, resistances, phases
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    def _compute_probe_times_pot_dep(self, cfg: PulseReadInterleavedConfig) -> List[float]:
        """Recreate the probe timing centres used in the C implementation (from example).
        
        This matches the _compute_probe_times function from pmu_potentiation_depression.py
        """
        ratio = 0.4
        ttime = 0.0
        centres: List[float] = []
        
        def add_measurement(start_time: float) -> None:
            centres.append(start_time + cfg.meas_width * (ratio + 0.9) / 2.0)
        
        # Initial delay and rise time
        ttime += cfg.reset_delay
        ttime += cfg.rise_time
        
        # Cycle pairs: ((Read, (Pulse)xn, (Read)xn), -(Read, (Pulse)xn, (Read)xn)) × NumCycles
        for cycle_pair_idx in range(cfg.num_cycles):
            # Potentiation cycle: Read → (Pulse)xn → (Read)xn
            # Potentiation: Initial read
            ttime += cfg.rise_time  # Rise to measV
            add_measurement(ttime)  # Measurement during measWidth
            ttime += cfg.meas_width  # Measurement width
            ttime += cfg.set_fall_time  # Fall delay at measV
            ttime += cfg.rise_time  # Fall to 0V
            ttime += cfg.meas_delay  # Delay after read
            
            # Potentiation: NumPulsesPerGroup pulses in sequence (positive)
            for _ in range(cfg.num_pulses_per_group):
                ttime += cfg.pulse_rise_time  # Rise to pulse
                ttime += cfg.pulse_width  # Pulse width (flat top)
                ttime += cfg.pulse_fall_time  # Fall from pulse
                ttime += cfg.pulse_delay  # Delay after pulse
            
            # Potentiation: NumReads reads in sequence
            for _ in range(cfg.num_reads):
                ttime += cfg.rise_time  # Rise to measV
                add_measurement(ttime)  # Measurement during measWidth
                ttime += cfg.meas_width  # Measurement width
                ttime += cfg.set_fall_time  # Fall delay at measV
                ttime += cfg.rise_time  # Fall to 0V
                ttime += cfg.meas_delay  # Delay after read
            
            # Depression cycle: Read → (Pulse)xn → (Read)xn (negative pulses)
            # Depression: Initial read
            ttime += cfg.rise_time  # Rise to measV
            add_measurement(ttime)  # Measurement during measWidth
            ttime += cfg.meas_width  # Measurement width
            ttime += cfg.set_fall_time  # Fall delay at measV
            ttime += cfg.rise_time  # Fall to 0V
            ttime += cfg.meas_delay  # Delay after read
            
            # Depression: NumPulsesPerGroup pulses in sequence (negative)
            for _ in range(cfg.num_pulses_per_group):
                ttime += cfg.pulse_rise_time  # Rise to pulse
                ttime += cfg.pulse_width  # Pulse width (flat top)
                ttime += cfg.pulse_fall_time  # Fall from pulse
                ttime += cfg.pulse_delay  # Delay after pulse
            
            # Depression: NumReads reads in sequence
            for _ in range(cfg.num_reads):
                ttime += cfg.rise_time  # Rise to measV
                add_measurement(ttime)  # Measurement during measWidth
                ttime += cfg.meas_width  # Measurement width
                ttime += cfg.set_fall_time  # Fall delay at measV
                ttime += cfg.rise_time  # Fall to 0V
                ttime += cfg.meas_delay  # Delay after read
        
        return centres
    
    def _generate_phases_pot_dep(self, cfg: PulseReadInterleavedConfig, num_points: int) -> List[str]:
        """Generate phase labels for potentiation-depression cycle data.
        
        Pattern matches _compute_probe_times_pot_dep:
        For each cycle:
        - Potentiation: 1 initial read + num_reads reads after pulses
        - Depression: 1 initial read + num_reads reads after pulses
        
        Total per cycle: 2 + 2*num_reads = 2*(1 + num_reads)
        """
        phases: List[str] = []
        points_per_cycle = 2 * (1 + cfg.num_reads)  # 2 initial reads + 2*num_reads after-pulse reads
        
        for i in range(num_points):
            point_in_cycle = i % points_per_cycle
            
            if point_in_cycle == 0:
                phases.append('potentiation')  # Potentiation initial read
            elif point_in_cycle < (1 + cfg.num_reads):
                phases.append('potentiation')  # Potentiation reads after pulses
            elif point_in_cycle == (1 + cfg.num_reads):
                phases.append('depression')  # Depression initial read
            else:
                phases.append('depression')  # Depression reads after pulses
        
        return phases
    
    def endurance_test(self, set_voltage: float = 2.0,
                      reset_voltage: float = -2.0,
                      pulse_width: float = 100.0,
                      read_voltage: float = 0.2,
                      num_cycles: int = 1000,
                      delay_between: float = 10000.0,
                      clim: float = 100e-3) -> Dict:
        """Endurance test: SET/RESET cycles for lifetime testing.
        
        Pattern: Initial Read → (SET → Read → RESET → Read) × N
        
        Args:
            set_voltage: SET voltage (V)
            reset_voltage: RESET voltage (V)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            num_cycles: Number of cycles
            delay_between: Delay between operations (µs)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, cycle_numbers
        """
        pulse_width_s = self._convert_us_to_seconds(pulse_width)
        delay_between_s = self._convert_us_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        cycle_numbers: List[int] = []
        
        for cycle in range(num_cycles):
            # SET
            # num_pulses must be >= 8, so use 8 and take only first result
            set_cfg = RetentionConfig(
                num_initial_meas_pulses=1 if cycle == 0 else 0,
                num_pulses_seq=1,
                num_pulses=8,  # Minimum required (was 1, which is invalid)
                pulse_v=set_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            set_cfg.validate()
            self._ensure_valid_max_points(set_cfg)
            
            timestamps, voltages, currents, resistances = self._execute_retention(set_cfg)
            
            # Return all data - no filtering
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            cycle_numbers.extend([cycle] * len(timestamps))
            
            # RESET
            # num_pulses must be >= 8, so use 8 and take only first result
            reset_cfg = RetentionConfig(
                num_initial_meas_pulses=0,
                num_pulses_seq=1,
                num_pulses=8,  # Minimum required (was 1, which is invalid)
                pulse_v=reset_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            reset_cfg.validate()
            self._ensure_valid_max_points(reset_cfg)
            
            timestamps, voltages, currents, resistances = self._execute_retention(reset_cfg)
            
            # Return all data - no filtering
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            cycle_numbers.extend([cycle] * len(timestamps))
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            cycle_numbers=cycle_numbers
        )
    
    def ispp_test(self, start_voltage: float = 0.5,
                  voltage_step: float = 0.05,
                  max_voltage: float = 3.0,
                  pulse_width: float = 100.0,
                  read_voltage: float = 0.2,
                  target_resistance: float = None,
                  resistance_threshold_factor: float = 0.5,
                  max_pulses: int = 100,
                  delay_between: float = 10000.0,
                  clim: float = 100e-3) -> Dict:
        """ISPP: Incremental step pulse programming.
        
        Pattern: Start at low voltage, increase by step each pulse until switching
        
        Args:
            start_voltage: Start voltage (V)
            voltage_step: Voltage step (V)
            max_voltage: Maximum voltage (V)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            target_resistance: Target resistance (Ohm, None = auto-detect)
            resistance_threshold_factor: Resistance change factor for switching detection
            max_pulses: Maximum pulses
            delay_between: Delay between pulses (µs)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, voltages_applied
        """
        pulse_width_s = self._convert_us_to_seconds(pulse_width)
        delay_between_s = self._convert_us_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        voltages_applied: List[float] = []
        
        current_voltage = start_voltage
        initial_resistance = None
        pulse_count = 0
        
        while current_voltage <= max_voltage and pulse_count < max_pulses:
            # num_pulses must be >= 8, so use 8 and take only first result
            cfg = RetentionConfig(
                num_initial_meas_pulses=1 if pulse_count == 0 else 0,
                num_pulses_seq=1,
                num_pulses=8,  # Minimum required (was 1, which is invalid)
                pulse_v=current_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            cfg.validate()
            
            # Ensure max_points is sufficient for rate calculation
            self._ensure_valid_max_points(cfg)
            
            timestamps, voltages, currents, resistances = self._execute_retention(cfg)
            
            # Return all data - no filtering
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            voltages_applied.extend([current_voltage] * len(timestamps))
            
            if initial_resistance is None and resistances:
                initial_resistance = resistances[0] if abs(resistances[0]) < 1e10 else None
            
            # Check for switching
            if resistances and initial_resistance and abs(initial_resistance) < 1e10:
                current_resistance = resistances[-1] if abs(resistances[-1]) < 1e10 else initial_resistance
                resistance_change = abs(current_resistance - initial_resistance) / abs(initial_resistance)
                
                if target_resistance:
                    if abs(current_resistance - target_resistance) / target_resistance < 0.1:
                        break  # Reached target
                elif resistance_change > resistance_threshold_factor:
                    break  # Significant switching detected
            
            current_voltage += voltage_step
            pulse_count += 1
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            voltages_applied=voltages_applied
        )
    
    def switching_threshold_test(self, direction: str = "set",
                                start_voltage: float = 0.5,
                                voltage_step: float = 0.05,
                                max_voltage: float = 3.0,
                                pulse_width: float = 100.0,
                                read_voltage: float = 0.2,
                                resistance_threshold_factor: float = 0.5,
                                num_pulses_per_voltage: int = 3,
                                delay_between: float = 10000.0,
                                clim: float = 100e-3) -> Dict:
        """Switching threshold finder: Find minimum SET or RESET voltage.
        
        Pattern: Try increasing voltages, find minimum that causes switching
        
        Args:
            direction: "set" or "reset"
            start_voltage: Start voltage (V)
            voltage_step: Voltage step (V)
            max_voltage: Maximum voltage (V)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            resistance_threshold_factor: Resistance change factor for switching
            num_pulses_per_voltage: Pulses per voltage
            delay_between: Delay between pulses (µs)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, voltages_applied
        """
        pulse_width_s = self._convert_us_to_seconds(pulse_width)
        delay_between_s = self._convert_us_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        # Determine voltage sign based on direction
        voltage_sign = 1.0 if direction.lower() == "set" else -1.0
        start_v = abs(start_voltage) * voltage_sign
        max_v = abs(max_voltage) * voltage_sign
        step_v = abs(voltage_step) * voltage_sign
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        voltages_applied: List[float] = []
        
        current_voltage = start_v
        initial_resistance = None
        
        while abs(current_voltage) <= abs(max_v):
            # num_pulses must be >= 8, so use 8 and take only first result
            cfg = RetentionConfig(
                num_initial_meas_pulses=1 if initial_resistance is None else 0,
                num_pulses_seq=num_pulses_per_voltage,
                num_pulses=8,  # Minimum required (was 1, which is invalid)
                pulse_v=current_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            cfg.validate()
            
            # Ensure max_points is sufficient for rate calculation
            self._ensure_valid_max_points(cfg)
            
            timestamps, voltages, currents, resistances = self._execute_retention(cfg)
            
            # Return all data - no filtering
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            voltages_applied.extend([current_voltage] * len(timestamps))
            
            if initial_resistance is None and resistances:
                initial_resistance = resistances[0] if abs(resistances[0]) < 1e10 else None
            
            # Check for switching
            if resistances and initial_resistance and abs(initial_resistance) < 1e10:
                current_resistance = resistances[-1] if abs(resistances[-1]) < 1e10 else initial_resistance
                resistance_change = abs(current_resistance - initial_resistance) / abs(initial_resistance)
                
                if resistance_change > resistance_threshold_factor:
                    break  # Switching detected
            
            current_voltage += step_v
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            voltages_applied=voltages_applied
        )
    
    def multilevel_programming(self, target_levels: list = None,
                              pulse_voltage: float = 1.5,
                              pulse_width: float = 100.0,
                              read_voltage: float = 0.2,
                              num_pulses_per_level: int = 5,
                              delay_between: float = 10000.0,
                              reset_voltage: float = -1.0,
                              reset_width: float = 1000.0,
                              delay_between_levels: float = 1.0,
                              clim: float = 100e-3) -> Dict:
        """Multilevel programming: Program to specific resistance levels.
        
        Pattern: For each level: Reset → Program with pulses → Read
        
        Args:
            target_levels: List of target levels (arbitrary units, used for labeling)
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            num_pulses_per_level: Pulses per level
            delay_between: Delay between pulses (µs)
            reset_voltage: Reset voltage (V)
            reset_width: Reset width (µs)
            delay_between_levels: Delay between levels (s)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, levels
        """
        if target_levels is None:
            target_levels = [1, 2, 3, 4, 5]
        
        pulse_width_s = self._convert_us_to_seconds(pulse_width)
        delay_between_s = self._convert_us_to_seconds(delay_between)
        reset_width_s = self._convert_us_to_seconds(reset_width)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        levels: List[int] = []
        
        for level_idx, level in enumerate(target_levels):
            # Reset
            reset_cfg = RetentionConfig(
                num_initial_meas_pulses=0,
                num_pulses_seq=1,
                num_pulses=8,  # Minimum required, but we'll ignore results
                pulse_v=reset_voltage,
                pulse_width=reset_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=1e-6,  # Use valid delay (matches working example default)
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=2e-6,  # Use valid delay (matches working example default: 2e-6)
                i_range=i_range,
            )
            reset_cfg.validate()
            self._ensure_valid_max_points(reset_cfg)
            self._execute_retention(reset_cfg)
            
            # Program to level
            # num_pulses must be >= 8, so use max of 1 and 8
            retention_reads = max(1, 8)
            prog_cfg = RetentionConfig(
                num_initial_meas_pulses=1 if level_idx == 0 else 0,
                num_pulses_seq=num_pulses_per_level,
                num_pulses=retention_reads,  # Minimum required (was 1, which is invalid)
                pulse_v=pulse_voltage,
                pulse_width=pulse_width_s,
                pulse_rise_time=1e-7,
                pulse_fall_time=1e-7,
                pulse_delay=delay_between_s,
                meas_v=read_voltage,
                meas_width=2e-6,
                meas_delay=delay_between_s,
                i_range=i_range,
            )
            prog_cfg.validate()
            self._ensure_valid_max_points(prog_cfg)
            
            timestamps, voltages, currents, resistances = self._execute_retention(prog_cfg)
            
            # Return all data - no filtering
            all_timestamps.extend(timestamps)
            all_voltages.extend(voltages)
            all_currents.extend(currents)
            all_resistances.extend(resistances)
            levels.extend([level] * len(timestamps))
            
            if level_idx < len(target_levels) - 1 and delay_between_levels > 0:
                time.sleep(delay_between_levels)
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            levels=levels
        )
    
    def pulse_train_varying_amplitudes(self, pulse_voltages: list = None,
                                      pulse_width: float = 100.0,
                                      read_voltage: float = 0.2,
                                      num_repeats: int = 1,
                                      delay_between: float = 10000.0,
                                      clim: float = 100e-3) -> Dict:
        """Pulse train with varying amplitudes.
        
        Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N
        
        Args:
            pulse_voltages: List of pulse voltages (V)
            pulse_width: Pulse width (µs)
            read_voltage: Read voltage (V)
            num_repeats: Number of repeats
            delay_between: Delay between pulses (µs)
            clim: Current limit (A)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, voltages_applied
        """
        if pulse_voltages is None:
            pulse_voltages = [1.0, 1.5, 2.0, -1.0, -1.5, -2.0]
        
        pulse_width_s = self._convert_us_to_seconds(pulse_width)
        delay_between_s = self._convert_us_to_seconds(delay_between)
        
        i_range = self._convert_clim_to_i_range(clim)
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        voltages_applied: List[float] = []
        
        for repeat in range(num_repeats):
            for volt_idx, pulse_v in enumerate(pulse_voltages):
                # num_pulses must be >= 8, so use 8 and take only first result
                cfg = RetentionConfig(
                    num_initial_meas_pulses=1,  # Always include initial read to get all data
                    num_pulses_seq=1,
                    num_pulses=8,  # Minimum required (was 1, which is invalid)
                    pulse_v=pulse_v,
                    pulse_width=pulse_width_s,
                    pulse_rise_time=1e-7,
                    pulse_fall_time=1e-7,
                    pulse_delay=delay_between_s,
                    meas_v=read_voltage,
                    meas_width=2e-6,
                    meas_delay=delay_between_s,
                    i_range=i_range,
                )
                cfg.validate()
                self._ensure_valid_max_points(cfg)
                
                timestamps, voltages, currents, resistances = self._execute_retention(cfg)
                
                # Return all data - no filtering
                all_timestamps.extend(timestamps)
                all_voltages.extend(voltages)
                all_currents.extend(currents)
                all_resistances.extend(resistances)
                voltages_applied.extend([pulse_v] * len(timestamps))
        
        return self._format_results(
            all_timestamps, all_voltages, all_currents, all_resistances,
            voltages_applied=voltages_applied
        )
    
    def laser_and_read(self,
                      read_voltage: float = 0.3,
                      read_width: float = 0.5,  # µs, will convert to seconds
                      read_period: float = 2.0,  # µs, will convert to seconds
                      num_reads: int = 500,
                      # Laser (CH2) parameters
                      laser_voltage_high: float = 1.5,  # Laser pulse voltage (V) - MUST BE LIMITED
                      laser_voltage_low: float = 0.0,  # Laser baseline voltage (V)
                      laser_width: float = 10.0,  # µs, will convert to seconds
                      laser_delay: float = 5.0,  # µs delay before laser pulse starts, will convert to seconds
                      laser_rise_time: float = 0.1,  # µs, will convert to seconds
                      laser_fall_time: float = 0.1,  # µs, will convert to seconds
                      # Instrument parameters
                      volts_source_rng: float = 10.0,  # CH1 voltage range (V)
                      current_measure_rng: float = 0.00001,  # CH1 current range (A)
                      sample_rate: float = 200e6,  # Sample rate (Sa/s)
                      clim: float = 100e-3) -> Dict:
        """Laser-assisted read measurements.
        
        ⚠️ IMPORTANT SAFETY WARNINGS:
        - You MUST reconfigure coax cables before running this test
        - CH2 laser voltage MUST NOT exceed safe limits (typically 2.0V max) to prevent laser damage
        - This test uses CH1 for measurement and CH2 for laser pulse (independent timing)
        
        Pattern: CH1 continuous reads at specified period, CH2 independent laser pulse
        
        Args:
            read_voltage: CH1 read voltage (V)
            read_width: CH1 pulse width (µs) - will be converted to seconds
            read_period: CH1 pulse period (µs) - will be converted to seconds
            num_reads: Number of CH1 read pulses (burst_count)
            laser_voltage_high: CH2 laser pulse voltage (V) - MUST BE LIMITED (max 2.0V recommended)
            laser_voltage_low: CH2 baseline voltage (V)
            laser_width: CH2 laser pulse width (µs) - will be converted to seconds
            laser_delay: CH2 delay before laser pulse starts (µs) - will be converted to seconds
            laser_rise_time: CH2 rise time (µs) - will be converted to seconds
            laser_fall_time: CH2 fall time (µs) - will be converted to seconds
            volts_source_rng: CH1 voltage range (V)
            current_measure_rng: CH1 current measurement range (A)
            sample_rate: Sample rate (Sa/s)
            clim: Current limit (A) - not directly used, kept for compatibility
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
        
        Raises:
            ValueError: If laser_voltage_high exceeds safety limit (2.0V)
        """
        # Safety check: Limit laser voltage to prevent damage
        MAX_LASER_VOLTAGE = 2.0  # Maximum safe voltage for laser (V)
        if abs(laser_voltage_high) > MAX_LASER_VOLTAGE:
            raise ValueError(
                f"⚠️ SAFETY ERROR: laser_voltage_high ({laser_voltage_high}V) exceeds maximum safe limit ({MAX_LASER_VOLTAGE}V). "
                f"This could damage the laser. Please reduce the voltage."
            )
        
        # Convert µs to seconds
        read_width_s = self._convert_us_to_seconds(read_width)
        read_period_s = self._convert_us_to_seconds(read_period)
        laser_width_s = self._convert_us_to_seconds(laser_width)
        laser_delay_s = self._convert_us_to_seconds(laser_delay)
        laser_rise_time_s = self._convert_us_to_seconds(laser_rise_time)
        laser_fall_time_s = self._convert_us_to_seconds(laser_fall_time)
        
        # Auto-calculate array size (one value per pulse in average mode)
        array_size = num_reads
        
        # Build EX command for ACraig10_PMU_Waveform_SegArb
        # CH1: Continuous waveform reads
        # CH2: Laser pulse with independent timing
        command = self._build_laser_read_ex_command(
            # CH1 parameters
            width=read_width_s,
            rise=100e-9,  # Default rise time (100ns)
            fall=100e-9,  # Default fall time (100ns)
            delay=0.0,  # No pre-pulse delay
            period=read_period_s,
            volts_source_rng=volts_source_rng,
            current_measure_rng=current_measure_rng,
            dut_res=1e6,  # Default DUT resistance
            start_v=read_voltage,
            stop_v=read_voltage,
            step_v=0.0,  # No voltage sweep
            base_v=0.0,  # Base voltage
            acq_type=1,  # Average mode (one value per pulse)
            lle_comp=0,  # Load line effect compensation off
            pre_data_pct=0.1,  # Default pre-pulse data capture
            post_data_pct=0.1,  # Default post-pulse data capture
            pulse_avg_cnt=1,  # No pulse averaging
            burst_count=num_reads,
            sample_rate=sample_rate,
            pmu_mode=0,  # Simple mode
            chan=1,  # CH1 for measurement
            pmu_id="PMU1",
            array_size=array_size,
            # CH2 parameters (laser pulse)
            ch2_enable=1,  # Enable CH2
            ch2_vrange=10.0,  # CH2 voltage range (V)
            ch2_vlow=laser_voltage_low,
            ch2_vhigh=laser_voltage_high,
            ch2_width=laser_width_s,
            ch2_rise=laser_rise_time_s,
            ch2_fall=laser_fall_time_s,
            ch2_period=laser_delay_s,  # Delay before laser pulse starts
            ch2_loop_count=1.0,  # Single laser pulse
            clarius_debug=1  # Enable debug output
        )
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            return_value, error = controller._execute_ex_command(command)
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            
            if return_value is not None and return_value < 0:
                raise RuntimeError(f"EX command returned error code: {return_value}")
            
            time.sleep(0.2)  # Allow data to be ready
            
            # Query data from GP parameters
            # Parameter positions: 23=V_Meas, 25=I_Meas, 27=T_Stamp
            voltage = self._query_gp_data(controller, 23, array_size, "voltage")
            current = self._query_gp_data(controller, 25, array_size, "current")
            time_axis = self._query_gp_data(controller, 27, array_size, "time")
            
            # Trim to valid data
            usable = min(len(voltage), len(current), len(time_axis))
            voltage = voltage[:usable]
            current = current[:usable]
            time_axis = time_axis[:usable]
            
            # Calculate resistances
            resistances: List[float] = []
            for v, i in zip(voltage, current):
                if abs(i) > 1e-12:
                    resistances.append(v / i)
                else:
                    resistances.append(float('inf') if v > 0 else float('-inf'))
            
            return self._format_results(time_axis, voltage, current, resistances)
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    def _build_laser_read_ex_command(
        self,
        # CH1 parameters
        width: float, rise: float, fall: float, delay: float, period: float,
        volts_source_rng: float, current_measure_rng: float, dut_res: float,
        start_v: float, stop_v: float, step_v: float, base_v: float,
        acq_type: int, lle_comp: int, pre_data_pct: float, post_data_pct: float,
        pulse_avg_cnt: int, burst_count: int, sample_rate: float, pmu_mode: int,
        chan: int, pmu_id: str, array_size: int,
        # CH2 parameters (laser pulse)
        ch2_enable: int, ch2_vrange: float,
        ch2_vlow: float, ch2_vhigh: float, ch2_width: float,
        ch2_rise: float, ch2_fall: float, ch2_period: float, ch2_loop_count: float,
        clarius_debug: int = 1
    ) -> str:
        """Build EX command for ACraig10_PMU_Waveform_SegArb (laser read)."""
        ch2_num_segments = 0  # 0 = auto-build mode
        
        params = [
            # CH1 parameters
            format_param(width),
            format_param(rise),
            format_param(fall),
            format_param(delay),
            format_param(period),
            format_param(volts_source_rng),
            format_param(current_measure_rng),
            format_param(dut_res),
            format_param(start_v),
            format_param(stop_v),
            format_param(step_v),
            format_param(base_v),
            format_param(acq_type),
            format_param(lle_comp),
            format_param(pre_data_pct),
            format_param(post_data_pct),
            format_param(pulse_avg_cnt),
            format_param(burst_count),
            format_param(sample_rate),
            format_param(pmu_mode),
            format_param(chan),
            pmu_id,
            "",  # V_Meas output array
            format_param(array_size),
            "",  # I_Meas output array
            format_param(array_size),
            "",  # T_Stamp output array
            format_param(array_size),
            # CH2 parameters - ORDER MATCHES METADATA
            format_param(ch2_enable),           # 29: Ch2Enable
            format_param(ch2_vrange),          # 30: Ch2VRange
            format_param(ch2_vlow),            # 31: Ch2Vlow
            format_param(ch2_vhigh),           # 32: Ch2Vhigh
            format_param(ch2_width),           # 33: Ch2Width
            format_param(ch2_rise),            # 34: Ch2Rise
            format_param(ch2_fall),            # 35: Ch2Fall
            format_param(ch2_period),          # 36: Ch2Period
            format_param(ch2_num_segments),    # 37: Ch2NumSegments (0 = auto-build)
            "",                                 # 38: Ch2StartV (empty array for auto-build)
            format_param(10),                  # 39: Ch2StartV_size
            "",                                 # 40: Ch2StopV (empty array)
            format_param(10),                  # 41: Ch2StopV_size
            "",                                 # 42: Ch2SegTime (empty array)
            format_param(10),                  # 43: Ch2SegTime_size
            "",                                 # 44: Ch2SSRCtrl (empty array)
            format_param(10),                  # 45: Ch2SSRCtrl_size
            "",                                 # 46: Ch2SegTrigOut (empty array)
            format_param(10),                  # 47: Ch2SegTrigOut_size
            "",                                 # 48: Ch2MeasType (empty array)
            format_param(10),                  # 49: Ch2MeasType_size
            "",                                 # 50: Ch2MeasStart (empty array)
            format_param(10),                  # 51: Ch2MeasStart_size
            "",                                 # 52: Ch2MeasStop (empty array)
            format_param(10),                  # 53: Ch2MeasStop_size
            format_param(ch2_loop_count),      # 54: Ch2LoopCount
            format_param(clarius_debug),       # 55: ClariusDebug
        ]
        
        return f"EX A_Ch1Read_Ch2Laser_Pulse ACraig10_PMU_Waveform_SegArb({','.join(params)})"
    
    # ============================================================================
    # Placeholders for Tests Requiring New C Modules
    # ============================================================================
    
    def current_range_finder(self, test_voltage: float = 0.2,
                            num_reads_per_range: int = 10,
                            delay_between_reads: float = 10000.0,
                            current_ranges: List[float] = None) -> Dict:
        """Find optimal current measurement range.
        
        NOTE: This test requires a new C module that can test multiple current
        ranges and recommend the optimal range. Currently not implemented.
        
        Raises:
            NotImplementedError: This test requires a new C module
        """
        raise NotImplementedError(
            "current_range_finder requires a new C module (current_range_finder_dual_channel.c) "
            "that can test multiple current ranges and recommend the optimal range based on "
            "signal-to-noise ratio. This module has not been developed yet."
        )
    
    def width_sweep_with_all_measurements(self, pulse_voltage: float = 1.5,
                                         pulse_widths: List[float] = None,
                                         read_voltage: float = 0.2,
                                         num_pulses_per_width: int = 5,
                                         reset_voltage: float = -1.0,
                                         reset_width: float = 1000.0,
                                         delay_between_widths: float = 5.0,
                                         clim: float = 100e-3) -> Dict:
        """Width sweep with pulse current measurement.
        
        NOTE: This test requires a C module that can measure current during the
        programming pulse itself, not just after. Currently not implemented.
        
        Raises:
            NotImplementedError: This test requires a new C module
        """
        raise NotImplementedError(
            "width_sweep_with_all_measurements requires a new C module that can measure "
            "current during the programming pulse itself (not just after). The existing "
            "retention module only measures during read pulses. A new module "
            "(pulse_with_measurement_dual_channel.c) would be needed."
        )
    
    def relaxation_after_multi_pulse_with_pulse_measurement(self, pulse_voltage: float = 1.5,
                                         num_pulses: int = 10,
                                         pulse_width: float = 100.0,
                                         delay_between_pulses: float = 1000.0,
                                         read_voltage: float = 0.2,
                                         num_reads: int = 10,
                                         delay_between_reads: float = 10.0,
                                         clim: float = 100e-3) -> Dict:
        """Relaxation with pulse current measurement.
        
        NOTE: This test requires a C module that can measure current during the
        programming pulse itself, not just after. Currently not implemented.
        
        Raises:
            NotImplementedError: This test requires a new C module
        """
        raise NotImplementedError(
            "relaxation_after_multi_pulse_with_pulse_measurement requires a new C module "
            "that can measure current during the programming pulse itself (not just after). "
            "The existing retention module only measures during read pulses. A new module "
            "(pulse_with_measurement_dual_channel.c) would be needed."
        )

    # ============================================================================
    # SMU-Based Slow Pulse Measurements (Much Slower Than PMU)
    # ============================================================================
    
    def smu_slow_pulse_measure(self, pulse_voltage: float = 1.0,
                               pulse_width: float = 0.1,  # seconds (default 100ms)
                               i_range: float = 10e-3,  # A (default 10mA)
                               i_compliance: float = 0.0,  # A (0 = disabled)
                               initialize: bool = True,
                               log_messages: bool = True,
                               enable_debug_output: bool = True) -> Dict:
        """Single slow pulse measurement using SMU (not PMU).
        
        ⚠️ IMPORTANT: This function uses the SMU (Source Measure Unit) instead of PMU
        (Pulse Measure Unit). The SMU is much slower but supports much longer pulse widths
        (up to 480 seconds vs microseconds for PMU).
        
        **Key Differences from PMU Functions:**
        - Uses SMU1 instead of PMU channels
        - Much slower pulse widths: 40ns to 480 seconds (vs microseconds for PMU)
        - Single measurement per call (not multiple pulses/reads)
        - Different hardware path (SMU vs PMU)
        - Lower maximum current range (1A vs higher for PMU)
        
        **Limits:**
        - Pulse width: 40ns (4e-8s) to 480 seconds
        - Pulse voltage: -20V to +20V
        - Current range: 0 to 1A
        - Current compliance: -10mA to +10mA (0 = disabled)
        
        **When to Use:**
        - For very slow pulses (milliseconds to seconds)
        - When PMU timing constraints are too restrictive
        - For relaxation studies requiring long pulse durations
        - When you need pulse widths > 1ms
        
        **When NOT to Use:**
        - For fast pulses (< 1ms) - use PMU functions instead
        - For multiple pulses in sequence - use PMU functions
        - For high-speed measurements - PMU is much faster
        
        Pattern: Single pulse → Measure resistance during pulse
        
        Args:
            pulse_voltage: Pulse voltage (V), range: -20 to +20
            pulse_width: Pulse width (seconds), range: 40ns to 480s
            i_range: Current range (A), range: 0 to 1A (default: 10mA)
            i_compliance: Current compliance limit (A), range: -10mA to +10mA (0 = disabled)
            initialize: Initialize SMU configuration (default: True)
            log_messages: Enable C module log messages (default: True)
            enable_debug_output: Enable debug output (default: True)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
            Note: Single measurement point (1 timestamp, 1 voltage, 1 current, 1 resistance)
        """
        # Validate parameters
        if pulse_width < 40e-9:
            raise ValueError(f"pulse_width must be >= 40ns (4e-8s), got {pulse_width:.2e}s")
        if pulse_width > 480.0:
            raise ValueError(f"pulse_width must be <= 480s, got {pulse_width:.2e}s")
        if abs(pulse_voltage) > 20.0:
            raise ValueError(f"pulse_voltage must be between -20V and +20V, got {pulse_voltage:.2f}V")
        if i_range < 0.0 or i_range > 1.0:
            raise ValueError(f"i_range must be between 0 and 1A, got {i_range:.2e}A")
        if abs(i_compliance) > 10e-3:
            raise ValueError(f"i_compliance must be between -10mA and +10mA, got {i_compliance:.2e}A")
        
        # Build EX command
        # Format: EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(initialize, logMessages, widthTime, Amplitude, Irange, Icomp, measResistance)
        # Note: measResistance is an output parameter, so we use a placeholder
        initialize_int = 1 if initialize else 0
        log_messages_int = 1 if log_messages else 0
        
        # Format parameters for EX command
        init_str = format_param(initialize_int)
        log_str = format_param(log_messages_int)
        width_str = format_param(pulse_width)
        amp_str = format_param(pulse_voltage)
        irange_str = format_param(i_range)
        icomp_str = format_param(i_compliance)
        
        # measResistance is output, so we use empty string (C module will populate it)
        command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure({init_str},{log_str},{width_str},{amp_str},{irange_str},{icomp_str},)"
        
        if enable_debug_output:
            print("\n" + "="*80)
            print("[KXCI] SMU Slow Pulse Measurement Parameters:")
            print("="*80)
            print(f"  ⚠️  Using SMU (not PMU) - Much slower but supports longer pulses")
            print(f"  Pulse voltage:        {pulse_voltage:.6f} V")
            print(f"  Pulse width:          {pulse_width:.6e} s ({pulse_width*1e3:.3f} ms)")
            print(f"  Current range:        {i_range:.2e} A ({i_range*1e3:.2f} mA)")
            print(f"  Current compliance:    {i_compliance:.2e} A ({i_compliance*1e3:.2f} mA)" if i_compliance != 0.0 else "  Current compliance:    Disabled")
            print(f"  Initialize:           {initialize}")
            print(f"  Log messages:         {log_messages}")
            print("="*80)
            print(f"\n[KXCI] Generated EX command:")
            print(command)
            print("="*80 + "\n")
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            return_value, error = controller._execute_ex_command(command)
            if error:
                raise RuntimeError(f"EX command failed: {error}")
            
            if return_value is not None and return_value < 0:
                raise RuntimeError(f"EX command returned error code: {return_value}")
            
            # The C module returns the resistance directly as a double
            # The return_value should be a float (resistance in ohms)
            if return_value is None:
                raise RuntimeError("EX command did not return a value. Check instrument connection and command format.")
            
            # Convert to float (it should already be a float from _parse_return_value)
            resistance = float(return_value)
            
            # Validate resistance is reasonable (not zero or invalid)
            if resistance <= 0 or not math.isfinite(resistance):
                if enable_debug_output:
                    print(f"[WARNING] Resistance value may be invalid: {resistance} Ω")
            
            # Calculate current from resistance and voltage
            # R = V/I, so I = V/R
            if abs(resistance) < 1e-12 or abs(resistance) > 1e12:
                current = 0.0
            else:
                current = pulse_voltage / resistance
            
            # Create single measurement point
            timestamp = self._get_timestamp()
            timestamps = [timestamp]
            voltages = [pulse_voltage]
            currents = [current]
            resistances = [resistance]
            
            if enable_debug_output:
                print(f"\n[KXCI] Measurement Result:")
                print(f"  Resistance: {resistance:.6e} Ω ({resistance/1e3:.3f} kΩ)")
                print(f"  Voltage:   {pulse_voltage:.6f} V")
                print(f"  Current:   {current:.6e} A ({current*1e6:.3f} µA)")
                print(f"  Timestamp: {timestamp:.6f} s")
            
            return self._format_results(timestamps, voltages, currents, resistances)
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    def smu_endurance(self, set_voltage: float = 2.0,
                     reset_voltage: float = -2.0,
                     set_duration: float = 0.1,  # seconds
                     reset_duration: float = 0.1,  # seconds
                     num_cycles: int = 10,
                     repeat_delay: float = 1.0,  # seconds between cycles
                     probe_voltage: float = 0.2,  # V (read voltage)
                     probe_duration: float = 0.01,  # seconds (read pulse width)
                     i_range: float = 10e-3,  # A
                     i_compliance: float = 0.0,  # A (0 = disabled)
                     initialize: bool = True,
                     log_messages: bool = True,
                     enable_debug_output: bool = True,
                     progress_callback: Optional[Callable] = None) -> Dict:
        """SMU-based endurance test with alternating SET/RESET pulses.
        
        ⚠️ IMPORTANT: This function uses the SMU (Source Measure Unit) instead of PMU.
        The SMU is much slower but supports much longer pulse widths (up to 480 seconds).
        
        Pattern: (SET pulse → Read → RESET pulse → Read) × N cycles
        
        **Implementation Details:**
        - SET/RESET pulses use `SMU_pulse_only` (no measurement during pulse)
        - Reads use `SMU_pulse_measure` (measures resistance during read pulse)
        - Only read measurements are stored in the output data
        
        **Key Differences from PMU Functions:**
        - Uses SMU1 instead of PMU channels
        - Much slower pulse widths: 40ns to 480 seconds (vs microseconds for PMU)
        - Single measurement per pulse (not multiple measurements per pulse)
        - Different hardware path (SMU vs PMU)
        - Lower maximum current range (1A vs higher for PMU)
        
        **Limits:**
        - Pulse widths: 40ns (4e-8s) to 480 seconds
        - Voltages: -20V to +20V
        - Current range: 0 to 1A
        - Current compliance: -10mA to +10mA (0 = disabled)
        
        **When to Use:**
        - For very slow pulses (milliseconds to seconds)
        - When PMU timing constraints are too restrictive
        - For retention studies requiring long pulse durations
        - When you need pulse widths > 1ms
        
        **When NOT to Use:**
        - For fast pulses (< 1ms) - use PMU functions instead
        - For high-speed measurements - PMU is much faster
        
        Args:
            set_voltage: SET pulse voltage (V, positive), range: 0 to +20
            reset_voltage: RESET pulse voltage (V, negative), range: -20 to 0
            set_duration: SET pulse width (seconds), range: 40ns to 480s
            reset_duration: RESET pulse width (seconds), range: 40ns to 480s
            num_cycles: Number of (SET → Read → RESET → Read) cycles
            repeat_delay: Delay between cycles (seconds)
            probe_voltage: Read/probe voltage (V), range: -20 to +20
            probe_duration: Read pulse width (seconds), range: 40ns to 480s
            i_range: Current range (A), range: 0 to 1A (default: 10mA)
            i_compliance: Current compliance limit (A), range: -10mA to +10mA (0 = disabled)
            initialize: Initialize SMU configuration (default: True)
            log_messages: Enable C module log messages (default: True)
            enable_debug_output: Enable debug output (default: True)
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, cycle_numbers
            cycle_numbers: 0=first SET, 1=first RESET, 2=second SET, etc.
        """
        # Validate parameters
        if set_duration < 40e-9 or set_duration > 480.0:
            raise ValueError(f"set_duration must be between 40ns and 480s, got {set_duration:.2e}s")
        if reset_duration < 40e-9 or reset_duration > 480.0:
            raise ValueError(f"reset_duration must be between 40ns and 480s, got {reset_duration:.2e}s")
        if probe_duration < 40e-9 or probe_duration > 480.0:
            raise ValueError(f"probe_duration must be between 40ns and 480s, got {probe_duration:.2e}s")
        if abs(set_voltage) > 20.0:
            raise ValueError(f"set_voltage must be between -20V and +20V, got {set_voltage:.2f}V")
        if abs(reset_voltage) > 20.0:
            raise ValueError(f"reset_voltage must be between -20V and +20V, got {reset_voltage:.2f}V")
        if abs(probe_voltage) > 20.0:
            raise ValueError(f"probe_voltage must be between -20V and +20V, got {probe_voltage:.2f}V")
        if i_range < 0.0 or i_range > 1.0:
            raise ValueError(f"i_range must be between 0 and 1A, got {i_range:.2e}A")
        if abs(i_compliance) > 10e-3:
            raise ValueError(f"i_compliance must be between -10mA and +10mA, got {i_compliance:.2e}A")
        
        if enable_debug_output:
            print("\n" + "="*80)
            print("[KXCI] SMU Endurance Test Parameters:")
            print("="*80)
            print(f"  ⚠️  Using SMU (not PMU) - Much slower but supports longer pulses")
            print(f"  Pattern: (SET → Read → RESET → Read) × {num_cycles} cycles")
            print(f"  SET pulse:   {set_voltage:.6f} V, {set_duration:.6e} s ({set_duration*1e3:.3f} ms)")
            print(f"  RESET pulse: {reset_voltage:.6f} V, {reset_duration:.6e} s ({reset_duration*1e3:.3f} ms)")
            print(f"  Read/probe:  {probe_voltage:.6f} V, {probe_duration:.6e} s ({probe_duration*1e3:.3f} ms)")
            print(f"  Repeat delay: {repeat_delay:.6e} s ({repeat_delay*1e3:.3f} ms)")
            print(f"  Current range:        {i_range:.2e} A ({i_range*1e3:.2f} mA)")
            print(f"  Current compliance:    {i_compliance:.2e} A ({i_compliance*1e3:.2f} mA)" if i_compliance != 0.0 else "  Current compliance:    Disabled")
            print(f"  Initialize:           {initialize}")
            print(f"  Log messages:         {log_messages}")
            print("="*80 + "\n")
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        cycle_numbers: List[int] = []
        pulse_types: List[str] = []  # "SET", "READ_AFTER_SET", "RESET", "READ_AFTER_RESET"
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            # Initialize once at the start
            if initialize:
                init_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(1,0,1.00E-4,0,{format_param(i_range)},{format_param(i_compliance)},)"
                controller._execute_ex_command(init_command)
            
            for cycle in range(num_cycles):
                if enable_debug_output:
                    print(f"\n[Cycle {cycle + 1}/{num_cycles}]")
                
                # 1. SET pulse (no measurement - just apply pulse)
                set_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_only(0,{1 if log_messages else 0},{format_param(set_duration)},{format_param(set_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
                return_value, error = controller._execute_ex_command(set_command)
                if error:
                    raise RuntimeError(f"SET pulse failed: {error}")
                if return_value is not None and return_value != 0:
                    raise RuntimeError(f"SET pulse returned error code: {return_value} (0=success, non-zero=error)")
                
                if enable_debug_output:
                    print(f"  SET pulse applied: {set_voltage:.6f} V, {set_duration:.6e} s")
                
                # 2. Read after SET (measure resistance)
                read_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(0,{1 if log_messages else 0},{format_param(probe_duration)},{format_param(probe_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
                return_value, error = controller._execute_ex_command(read_command)
                if error:
                    raise RuntimeError(f"Read after SET failed: {error}")
                
                # Store whatever value we get - no validation, just plot it
                if return_value is not None:
                    resistance = float(return_value)
                    # Calculate current (handle division by zero or very large values)
                    if abs(resistance) > 1e-12 and abs(resistance) < 1e12:
                        current = probe_voltage / resistance
                    else:
                        current = 0.0
                    
                    timestamp = self._get_timestamp()
                    all_timestamps.append(timestamp)
                    all_voltages.append(probe_voltage)
                    all_currents.append(current)
                    all_resistances.append(resistance)
                    cycle_numbers.append(cycle)
                    pulse_types.append("READ_AFTER_SET")
                    
                    if enable_debug_output:
                        print(f"  Read after SET: R={resistance:.6e} Ω ({resistance/1e3:.3f} kΩ), I={current:.6e} A ({current*1e6:.3f} µA)")
                    
                    # Call progress callback for real-time plotting
                    if progress_callback:
                        try:
                            progress_callback({
                                'timestamps': all_timestamps.copy(),
                                'voltages': all_voltages.copy(),
                                'currents': all_currents.copy(),
                                'resistances': all_resistances.copy(),
                                'cycle_numbers': cycle_numbers.copy(),
                                'pulse_types': pulse_types.copy(),
                                'test_name': '⚠️ SMU Endurance'
                            })
                        except Exception as e:
                            if enable_debug_output:
                                print(f"  ⚠️  Progress callback error: {e}")
                
                # 3. RESET pulse (no measurement - just apply pulse)
                reset_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_only(0,{1 if log_messages else 0},{format_param(reset_duration)},{format_param(reset_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
                return_value, error = controller._execute_ex_command(reset_command)
                if error:
                    raise RuntimeError(f"RESET pulse failed: {error}")
                if return_value is not None and return_value != 0:
                    raise RuntimeError(f"RESET pulse returned error code: {return_value} (0=success, non-zero=error)")
                
                if enable_debug_output:
                    print(f"  RESET pulse applied: {reset_voltage:.6f} V, {reset_duration:.6e} s")
                
                # 4. Read after RESET (measure resistance)
                read_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(0,{1 if log_messages else 0},{format_param(probe_duration)},{format_param(probe_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
                return_value, error = controller._execute_ex_command(read_command)
                if error:
                    raise RuntimeError(f"Read after RESET failed: {error}")
                
                # Store whatever value we get - no validation, just plot it
                if return_value is not None:
                    resistance = float(return_value)
                    # Calculate current (handle division by zero or very large values)
                    if abs(resistance) > 1e-12 and abs(resistance) < 1e12:
                        current = probe_voltage / resistance
                    else:
                        current = 0.0
                    
                    timestamp = self._get_timestamp()
                    all_timestamps.append(timestamp)
                    all_voltages.append(probe_voltage)
                    all_currents.append(current)
                    all_resistances.append(resistance)
                    cycle_numbers.append(cycle)
                    pulse_types.append("READ_AFTER_RESET")
                    
                    if enable_debug_output:
                        print(f"  Read after RESET: R={resistance:.6e} Ω ({resistance/1e3:.3f} kΩ), I={current:.6e} A ({current*1e6:.3f} µA)")
                    
                    # Call progress callback for real-time plotting
                    if progress_callback:
                        try:
                            progress_callback({
                                'timestamps': all_timestamps.copy(),
                                'voltages': all_voltages.copy(),
                                'currents': all_currents.copy(),
                                'resistances': all_resistances.copy(),
                                'cycle_numbers': cycle_numbers.copy(),
                                'pulse_types': pulse_types.copy(),
                                'test_name': '⚠️ SMU Endurance'
                            })
                        except Exception as e:
                            if enable_debug_output:
                                print(f"  ⚠️  Progress callback error: {e}")
                
                # Delay between cycles (except after last cycle)
                if cycle < num_cycles - 1 and repeat_delay > 0:
                    time.sleep(repeat_delay)
            
            if enable_debug_output:
                print(f"\n[KXCI] Endurance Test Complete:")
                print(f"  Total measurements: {len(all_timestamps)}")
                print(f"  Cycles completed: {num_cycles}")
            
            return self._format_results(
                all_timestamps, all_voltages, all_currents, all_resistances,
                cycle_numbers=cycle_numbers if num_cycles > 1 else None,
                pulse_types=pulse_types
            )
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    def smu_retention(self, pulse_voltage: float = 2.0,
                     pulse_duration: float = 0.1,  # seconds
                     read_voltage: float = 0.2,  # V (read voltage)
                     read_duration: float = 0.01,  # seconds (read pulse width)
                     num_reads: int = 10,
                     delay_between_reads: float = 1.0,  # seconds between reads
                     i_range: float = 10e-3,  # A
                     i_compliance: float = 0.0,  # A (0 = disabled)
                     initialize: bool = True,
                     log_messages: bool = True,
                     enable_debug_output: bool = True,
                     progress_callback: Optional[Callable] = None) -> Dict:
        """SMU-based retention test: Initial read, then pulse, then multiple reads over time.
        
        ⚠️ IMPORTANT: This function uses the SMU (Source Measure Unit) instead of PMU.
        The SMU is much slower but supports much longer pulse widths (up to 480 seconds).
        
        Pattern: Initial Read → Pulse → Read @ t1 → Read @ t2 → Read @ t3... (measures retention over time)
        
        **Implementation Details:**
        - Single pulse using `SMU_pulse_only` (no measurement during pulse)
        - Multiple reads using `SMU_pulse_measure` (measures resistance at each read)
        - Time between reads is user-configurable
        - Plots resistance over time to show retention characteristics
        
        **Key Differences from PMU Functions:**
        - Uses SMU1 instead of PMU channels
        - Much slower pulse widths: 40ns to 480 seconds (vs microseconds for PMU)
        - Single measurement per read (not multiple measurements per pulse)
        - Different hardware path (SMU vs PMU)
        - Lower maximum current range (1A vs higher for PMU)
        
        **Limits:**
        - Pulse widths: 40ns (4e-8s) to 480 seconds
        - Voltages: -20V to +20V
        - Current range: 0 to 1A
        - Current compliance: -10mA to +10mA (0 = disabled)
        
        **When to Use:**
        - For retention studies (measuring how resistance changes over time after a pulse)
        - For very slow pulses (milliseconds to seconds)
        - When PMU timing constraints are too restrictive
        - When you need pulse widths > 1ms
        
        **When NOT to Use:**
        - For fast pulses (< 1ms) - use PMU functions instead
        - For high-speed measurements - PMU is much faster
        - For endurance cycling - use smu_endurance instead
        
        Args:
            pulse_voltage: Pulse voltage (V), range: -20 to +20
            pulse_duration: Pulse width (seconds), range: 40ns to 480s
            read_voltage: Read/probe voltage (V), range: -20 to +20
            read_duration: Read pulse width (seconds), range: 40ns to 480s
            num_reads: Number of reads after the pulse
            delay_between_reads: Delay between reads (seconds)
            i_range: Current range (A), range: 0 to 1A (default: 10mA)
            i_compliance: Current compliance limit (A), range: -10mA to +10mA (0 = disabled)
            initialize: Initialize SMU configuration (default: True)
            log_messages: Enable C module log messages (default: True)
            enable_debug_output: Enable debug output (default: True)
            progress_callback: Optional callback for real-time plotting
        
        Returns:
            Dict with timestamps, voltages, currents, resistances
            Timestamps are relative to the start (initial read at t=0, pulse and subsequent reads at positive times)
        """
        # Validate parameters
        if pulse_duration < 40e-9 or pulse_duration > 480.0:
            raise ValueError(f"pulse_duration must be between 40ns and 480s, got {pulse_duration:.2e}s")
        if read_duration < 40e-9 or read_duration > 480.0:
            raise ValueError(f"read_duration must be between 40ns and 480s, got {read_duration:.2e}s")
        if abs(pulse_voltage) > 20.0:
            raise ValueError(f"pulse_voltage must be between -20V and +20V, got {pulse_voltage:.2f}V")
        if abs(read_voltage) > 20.0:
            raise ValueError(f"read_voltage must be between -20V and +20V, got {read_voltage:.2f}V")
        if i_range < 0.0 or i_range > 1.0:
            raise ValueError(f"i_range must be between 0 and 1A, got {i_range:.2e}A")
        if abs(i_compliance) > 10e-3:
            raise ValueError(f"i_compliance must be between -10mA and +10mA, got {i_compliance:.2e}A")
        if num_reads < 1:
            raise ValueError(f"num_reads must be >= 1, got {num_reads}")
        
        if enable_debug_output:
            print("\n" + "="*80)
            print("[KXCI] SMU Retention Test Parameters:")
            print("="*80)
            print(f"  ⚠️  Using SMU (not PMU) - Much slower but supports longer pulses")
            print(f"  Pattern: Initial Read → Pulse → {num_reads} reads (retention over time)")
            print(f"  Pulse:    {pulse_voltage:.6f} V, {pulse_duration:.6e} s ({pulse_duration*1e3:.3f} ms)")
            print(f"  Read:     {read_voltage:.6f} V, {read_duration:.6e} s ({read_duration*1e3:.3f} ms)")
            print(f"  Delay between reads: {delay_between_reads:.6e} s ({delay_between_reads*1e3:.3f} ms)")
            print(f"  Current range:        {i_range:.2e} A ({i_range*1e3:.2f} mA)")
            print(f"  Current compliance:    {i_compliance:.2e} A ({i_compliance*1e3:.2f} mA)" if i_compliance != 0.0 else "  Current compliance:    Disabled")
            print(f"  Initialize:           {initialize}")
            print(f"  Log messages:         {log_messages}")
            print("="*80 + "\n")
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            # Initialize once at the start
            if initialize:
                init_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(1,0,1.00E-4,0,{format_param(i_range)},{format_param(i_compliance)},)"
                controller._execute_ex_command(init_command)
            
            # Record start time (for relative timestamps)
            start_timestamp = self._get_timestamp()
            
            # Initial read before pulse
            if enable_debug_output:
                print(f"\n[Initial Read] Measuring initial state before pulse")
            
            initial_read_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(0,{1 if log_messages else 0},{format_param(read_duration)},{format_param(read_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
            return_value, error = controller._execute_ex_command(initial_read_command)
            if error:
                raise RuntimeError(f"Initial read failed: {error}")
            
            # Store initial read measurement
            if return_value is not None:
                resistance = float(return_value)
                # Calculate current (handle division by zero or very large values)
                if abs(resistance) > 1e-12 and abs(resistance) < 1e12:
                    current = read_voltage / resistance
                else:
                    current = 0.0
                
                # Calculate time relative to start (initial read at t=0)
                current_timestamp = self._get_timestamp()
                time_since_start = current_timestamp - start_timestamp
                
                all_timestamps.append(time_since_start)
                all_voltages.append(read_voltage)
                all_currents.append(current)
                all_resistances.append(resistance)
                
                if enable_debug_output:
                    print(f"  Initial resistance: R={resistance:.6e} Ω ({resistance/1e3:.3f} kΩ), I={current:.6e} A ({current*1e6:.3f} µA)")
            
            # Apply the pulse (no measurement)
            if enable_debug_output:
                print(f"\n[Pulse] Applying pulse: {pulse_voltage:.6f} V, {pulse_duration:.6e} s")
            
            pulse_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_only(0,{1 if log_messages else 0},{format_param(pulse_duration)},{format_param(pulse_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
            return_value, error = controller._execute_ex_command(pulse_command)
            if error:
                raise RuntimeError(f"Pulse failed: {error}")
            if return_value is not None and return_value != 0:
                raise RuntimeError(f"Pulse returned error code: {return_value} (0=success, non-zero=error)")
            
            # Record pulse time (for reference, but timestamps are relative to start)
            pulse_timestamp = self._get_timestamp()
            
            # Perform multiple reads over time
            for read_idx in range(num_reads):
                if enable_debug_output:
                    print(f"\n[Read {read_idx + 1}/{num_reads}]")
                
                # Wait for the delay (except before first read)
                if read_idx > 0 and delay_between_reads > 0:
                    time.sleep(delay_between_reads)
                
                # Read (measure resistance)
                read_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(0,{1 if log_messages else 0},{format_param(read_duration)},{format_param(read_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
                return_value, error = controller._execute_ex_command(read_command)
                if error:
                    raise RuntimeError(f"Read {read_idx + 1} failed: {error}")
                
                # Store measurement
                if return_value is not None:
                    resistance = float(return_value)
                    # Calculate current (handle division by zero or very large values)
                    if abs(resistance) > 1e-12 and abs(resistance) < 1e12:
                        current = read_voltage / resistance
                    else:
                        current = 0.0
                    
                    # Calculate time since start (all timestamps relative to initial read at t=0)
                    current_timestamp = self._get_timestamp()
                    time_since_start = current_timestamp - start_timestamp
                    
                    all_timestamps.append(time_since_start)
                    all_voltages.append(read_voltage)
                    all_currents.append(current)
                    all_resistances.append(resistance)
                    
                    if enable_debug_output:
                        time_since_pulse = current_timestamp - pulse_timestamp
                        print(f"  Time since start: {time_since_start:.6f} s (since pulse: {time_since_pulse:.6f} s)")
                        print(f"  Resistance: R={resistance:.6e} Ω ({resistance/1e3:.3f} kΩ), I={current:.6e} A ({current*1e6:.3f} µA)")
                    
                    # Call progress callback for real-time plotting
                    if progress_callback:
                        try:
                            progress_callback({
                                'timestamps': all_timestamps.copy(),
                                'voltages': all_voltages.copy(),
                                'currents': all_currents.copy(),
                                'resistances': all_resistances.copy(),
                                'test_name': '⚠️ SMU Retention'
                            })
                        except Exception as e:
                            if enable_debug_output:
                                print(f"  ⚠️  Progress callback error: {e}")
            
            if enable_debug_output:
                print(f"\n[KXCI] Retention Test Complete:")
                print(f"  Total measurements: {len(all_timestamps)}")
                print(f"  Time span: {all_timestamps[-1] if all_timestamps else 0:.6f} s")
            
            return self._format_results(
                all_timestamps, all_voltages, all_currents, all_resistances
            )
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass
    
    def smu_retention_with_pulse_measurement(self, set_voltage: float = 2.0,
                     reset_voltage: float = -2.0,
                     set_duration: float = 0.1,  # seconds
                     reset_duration: float = 0.1,  # seconds
                     num_cycles: int = 10,
                     repeat_delay: float = 1.0,  # seconds between cycles
                     probe_voltage: float = 0.2,  # V (read voltage)
                     probe_duration: float = 0.01,  # seconds (read pulse width)
                     i_range: float = 10e-3,  # A
                     i_compliance: float = 0.0,  # A (0 = disabled)
                     initialize: bool = True,
                     log_messages: bool = True,
                     enable_debug_output: bool = True,
                     progress_callback: Optional[Callable] = None) -> Dict:
        """SMU-based retention test with measurements during SET/RESET pulses.
        
        ⚠️ IMPORTANT: This function uses the SMU (Source Measure Unit) instead of PMU.
        The SMU is much slower but supports much longer pulse widths (up to 480 seconds).
        
        Pattern: (SET pulse with measurement → Read → RESET pulse with measurement → Read) × N cycles
        
        **Key Differences from smu_retention():**
        - Measures resistance DURING the SET pulse (not just after)
        - Measures resistance DURING the RESET pulse (not just after)
        - Uses SMU_pulse_measure for both pulses and reads
        - Provides more data points per cycle (4 measurements: SET pulse, read after SET, RESET pulse, read after RESET)
        
        **Implementation Details:**
        - SET pulse uses `SMU_pulse_measure` (measures resistance during pulse)
        - Reads use `SMU_pulse_measure` (measures resistance during read pulse)
        - RESET pulse uses `SMU_pulse_measure` (measures resistance during pulse)
        - All measurements are stored and plotted
        
        **Limits:**
        - Pulse widths: 40ns (4e-8s) to 480 seconds
        - Voltages: -20V to +20V
        - Current range: 0 to 1A
        - Current compliance: -10mA to +10mA (0 = disabled)
        
        Args:
            set_voltage: SET pulse voltage (V, positive), range: 0 to +20
            reset_voltage: RESET pulse voltage (V, negative), range: -20 to 0
            set_duration: SET pulse width (seconds), range: 40ns to 480s
            reset_duration: RESET pulse width (seconds), range: 40ns to 480s
            num_cycles: Number of (SET → Read → RESET → Read) cycles
            repeat_delay: Delay between cycles (seconds)
            probe_voltage: Read/probe voltage (V), range: -20 to +20
            probe_duration: Read pulse width (seconds), range: 40ns to 480s
            i_range: Current range (A), range: 0 to 1A (default: 10mA)
            i_compliance: Current compliance limit (A), range: -10mA to +10mA (0 = disabled)
            initialize: Initialize SMU configuration (default: True)
            log_messages: Enable C module log messages (default: True)
            enable_debug_output: Enable debug output (default: True)
            progress_callback: Optional callback for real-time plotting
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, cycle_numbers, pulse_types
            pulse_types: "SET_PULSE", "READ_AFTER_SET", "RESET_PULSE", "READ_AFTER_RESET"
        """
        # Validate parameters
        if set_duration < 40e-9 or set_duration > 480.0:
            raise ValueError(f"set_duration must be between 40ns and 480s, got {set_duration:.2e}s")
        if reset_duration < 40e-9 or reset_duration > 480.0:
            raise ValueError(f"reset_duration must be between 40ns and 480s, got {reset_duration:.2e}s")
        if probe_duration < 40e-9 or probe_duration > 480.0:
            raise ValueError(f"probe_duration must be between 40ns and 480s, got {probe_duration:.2e}s")
        if abs(set_voltage) > 20.0:
            raise ValueError(f"set_voltage must be between -20V and +20V, got {set_voltage:.2f}V")
        if abs(reset_voltage) > 20.0:
            raise ValueError(f"reset_voltage must be between -20V and +20V, got {reset_voltage:.2f}V")
        if abs(probe_voltage) > 20.0:
            raise ValueError(f"probe_voltage must be between -20V and +20V, got {probe_voltage:.2f}V")
        if i_range < 0.0 or i_range > 1.0:
            raise ValueError(f"i_range must be between 0 and 1A, got {i_range:.2e}A")
        if abs(i_compliance) > 10e-3:
            raise ValueError(f"i_compliance must be between -10mA and +10mA, got {i_compliance:.2e}A")
        
        if enable_debug_output:
            print("\n" + "="*80)
            print("[KXCI] SMU Retention with Pulse Measurement Parameters:")
            print("="*80)
            print(f"  ⚠️  Using SMU (not PMU) - Much slower but supports longer pulses")
            print(f"  Pattern: (SET pulse+measure → Read → RESET pulse+measure → Read) × {num_cycles} cycles")
            print(f"  SET pulse:   {set_voltage:.6f} V, {set_duration:.6e} s ({set_duration*1e3:.3f} ms) [WITH MEASUREMENT]")
            print(f"  RESET pulse: {reset_voltage:.6f} V, {reset_duration:.6e} s ({reset_duration*1e3:.3f} ms) [WITH MEASUREMENT]")
            print(f"  Read/probe:  {probe_voltage:.6f} V, {probe_duration:.6e} s ({probe_duration*1e3:.3f} ms)")
            print(f"  Repeat delay: {repeat_delay:.6e} s ({repeat_delay*1e3:.3f} ms)")
            print(f"  Current range:        {i_range:.2e} A ({i_range*1e3:.2f} mA)")
            print(f"  Current compliance:    {i_compliance:.2e} A ({i_compliance*1e3:.2f} mA)" if i_compliance != 0.0 else "  Current compliance:    Disabled")
            print(f"  Initialize:           {initialize}")
            print(f"  Log messages:         {log_messages}")
            print("="*80 + "\n")
        
        all_timestamps: List[float] = []
        all_voltages: List[float] = []
        all_currents: List[float] = []
        all_resistances: List[float] = []
        cycle_numbers: List[int] = []
        pulse_types: List[str] = []  # "SET_PULSE", "READ_AFTER_SET", "RESET_PULSE", "READ_AFTER_RESET"
        
        controller = self._get_controller()
        
        if not controller.connect():
            raise RuntimeError("Unable to connect to instrument")
        
        try:
            if not controller._enter_ul_mode():
                raise RuntimeError("Failed to enter UL mode")
            
            # Initialize once at the start
            if initialize:
                init_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(1,0,1.00E-4,0,{format_param(i_range)},{format_param(i_compliance)},)"
                controller._execute_ex_command(init_command)
            
            for cycle in range(num_cycles):
                if enable_debug_output:
                    print(f"\n[Cycle {cycle + 1}/{num_cycles}]")
                
                # 1. SET pulse WITH measurement (measures resistance during pulse)
                set_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(0,{1 if log_messages else 0},{format_param(set_duration)},{format_param(set_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
                return_value, error = controller._execute_ex_command(set_command)
                if error:
                    raise RuntimeError(f"SET pulse failed: {error}")
                
                # Store whatever value we get - no validation, just plot it
                if return_value is not None:
                    resistance = float(return_value)
                    # Calculate current (handle division by zero or very large values)
                    if abs(resistance) > 1e-12 and abs(resistance) < 1e12:
                        current = set_voltage / resistance
                    else:
                        current = 0.0
                    
                    timestamp = self._get_timestamp()
                    all_timestamps.append(timestamp)
                    all_voltages.append(set_voltage)
                    all_currents.append(current)
                    all_resistances.append(resistance)
                    cycle_numbers.append(cycle)
                    pulse_types.append("SET_PULSE")
                    
                    if enable_debug_output:
                        print(f"  SET pulse (measured): R={resistance:.6e} Ω ({resistance/1e3:.3f} kΩ), I={current:.6e} A ({current*1e6:.3f} µA)")
                    
                    # Call progress callback for real-time plotting
                    if progress_callback:
                        try:
                            progress_callback({
                                'timestamps': all_timestamps.copy(),
                                'voltages': all_voltages.copy(),
                                'currents': all_currents.copy(),
                                'resistances': all_resistances.copy(),
                                'cycle_numbers': cycle_numbers.copy(),
                                'pulse_types': pulse_types.copy(),
                                'test_name': '⚠️ SMU Retention (Pulse Measured)'
                            })
                        except Exception as e:
                            if enable_debug_output:
                                print(f"  ⚠️  Progress callback error: {e}")
                
                # 2. Read after SET (measure resistance)
                read_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(0,{1 if log_messages else 0},{format_param(probe_duration)},{format_param(probe_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
                return_value, error = controller._execute_ex_command(read_command)
                if error:
                    raise RuntimeError(f"Read after SET failed: {error}")
                
                # Store whatever value we get - no validation, just plot it
                if return_value is not None:
                    resistance = float(return_value)
                    # Calculate current (handle division by zero or very large values)
                    if abs(resistance) > 1e-12 and abs(resistance) < 1e12:
                        current = probe_voltage / resistance
                    else:
                        current = 0.0
                    
                    timestamp = self._get_timestamp()
                    all_timestamps.append(timestamp)
                    all_voltages.append(probe_voltage)
                    all_currents.append(current)
                    all_resistances.append(resistance)
                    cycle_numbers.append(cycle)
                    pulse_types.append("READ_AFTER_SET")
                    
                    if enable_debug_output:
                        print(f"  Read after SET: R={resistance:.6e} Ω ({resistance/1e3:.3f} kΩ), I={current:.6e} A ({current*1e6:.3f} µA)")
                    
                    # Call progress callback for real-time plotting
                    if progress_callback:
                        try:
                            progress_callback({
                                'timestamps': all_timestamps.copy(),
                                'voltages': all_voltages.copy(),
                                'currents': all_currents.copy(),
                                'resistances': all_resistances.copy(),
                                'cycle_numbers': cycle_numbers.copy(),
                                'pulse_types': pulse_types.copy(),
                                'test_name': '⚠️ SMU Retention (Pulse Measured)'
                            })
                        except Exception as e:
                            if enable_debug_output:
                                print(f"  ⚠️  Progress callback error: {e}")
                
                # 3. RESET pulse WITH measurement (measures resistance during pulse)
                reset_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(0,{1 if log_messages else 0},{format_param(reset_duration)},{format_param(reset_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
                return_value, error = controller._execute_ex_command(reset_command)
                if error:
                    raise RuntimeError(f"RESET pulse failed: {error}")
                
                # Store whatever value we get - no validation, just plot it
                if return_value is not None:
                    resistance = float(return_value)
                    # Calculate current (handle division by zero or very large values)
                    if abs(resistance) > 1e-12 and abs(resistance) < 1e12:
                        current = reset_voltage / resistance
                    else:
                        current = 0.0
                    
                    timestamp = self._get_timestamp()
                    all_timestamps.append(timestamp)
                    all_voltages.append(reset_voltage)
                    all_currents.append(current)
                    all_resistances.append(resistance)
                    cycle_numbers.append(cycle)
                    pulse_types.append("RESET_PULSE")
                    
                    if enable_debug_output:
                        print(f"  RESET pulse (measured): R={resistance:.6e} Ω ({resistance/1e3:.3f} kΩ), I={current:.6e} A ({current*1e6:.3f} µA)")
                    
                    # Call progress callback for real-time plotting
                    if progress_callback:
                        try:
                            progress_callback({
                                'timestamps': all_timestamps.copy(),
                                'voltages': all_voltages.copy(),
                                'currents': all_currents.copy(),
                                'resistances': all_resistances.copy(),
                                'cycle_numbers': cycle_numbers.copy(),
                                'pulse_types': pulse_types.copy(),
                                'test_name': '⚠️ SMU Retention (Pulse Measured)'
                            })
                        except Exception as e:
                            if enable_debug_output:
                                print(f"  ⚠️  Progress callback error: {e}")
                
                # 4. Read after RESET (measure resistance)
                read_command = f"EX Labview_Controlled_Programs_Kemp SMU_pulse_measure(0,{1 if log_messages else 0},{format_param(probe_duration)},{format_param(probe_voltage)},{format_param(i_range)},{format_param(i_compliance)},)"
                return_value, error = controller._execute_ex_command(read_command)
                if error:
                    raise RuntimeError(f"Read after RESET failed: {error}")
                
                # Store whatever value we get - no validation, just plot it
                if return_value is not None:
                    resistance = float(return_value)
                    # Calculate current (handle division by zero or very large values)
                    if abs(resistance) > 1e-12 and abs(resistance) < 1e12:
                        current = probe_voltage / resistance
                    else:
                        current = 0.0
                    
                    timestamp = self._get_timestamp()
                    all_timestamps.append(timestamp)
                    all_voltages.append(probe_voltage)
                    all_currents.append(current)
                    all_resistances.append(resistance)
                    cycle_numbers.append(cycle)
                    pulse_types.append("READ_AFTER_RESET")
                    
                    if enable_debug_output:
                        print(f"  Read after RESET: R={resistance:.6e} Ω ({resistance/1e3:.3f} kΩ), I={current:.6e} A ({current*1e6:.3f} µA)")
                    
                    # Call progress callback for real-time plotting
                    if progress_callback:
                        try:
                            progress_callback({
                                'timestamps': all_timestamps.copy(),
                                'voltages': all_voltages.copy(),
                                'currents': all_currents.copy(),
                                'resistances': all_resistances.copy(),
                                'cycle_numbers': cycle_numbers.copy(),
                                'pulse_types': pulse_types.copy(),
                                'test_name': '⚠️ SMU Retention (Pulse Measured)'
                            })
                        except Exception as e:
                            if enable_debug_output:
                                print(f"  ⚠️  Progress callback error: {e}")
                
                # Delay between cycles (except after last cycle)
                if cycle < num_cycles - 1 and repeat_delay > 0:
                    time.sleep(repeat_delay)
            
            if enable_debug_output:
                print(f"\n[KXCI] Retention Test Complete:")
                print(f"  Total measurements: {len(all_timestamps)}")
                print(f"  Cycles completed: {num_cycles}")
            
            return self._format_results(
                all_timestamps, all_voltages, all_currents, all_resistances,
                cycle_numbers=cycle_numbers if num_cycles > 1 else None,
                pulse_types=pulse_types
            )
            
        finally:
            try:
                controller._exit_ul_mode()
            except Exception:
                pass


# ============================================================================
# Testing and Examples
# ============================================================================

if __name__ == "__main__":
    """Standalone testing examples for keithley4200_kxci_scripts.
    
    Simply uncomment and modify the function call you want to run.
    All parameters have defaults, so you only need to specify what you want to change.
    """
    
    # ============================================================================
    # CONFIGURATION - Set your GPIB address and timeout here
    # ============================================================================
    GPIB_ADDRESS = "GPIB0::17::INSTR"
    TIMEOUT = 30.0
    
    # ============================================================================
    # TEST SELECTION - Uncomment the test you want to run and modify parameters
    # ============================================================================
    
    # Initialize the scripts object
    scripts = Keithley4200_KXCI_Scripts(gpib_address=GPIB_ADDRESS, timeout=TIMEOUT)
    
    try:
        # Example 1: Simple pulse-read-repeat test
        # Uncomment to run:
        # results = scripts.pulse_read_repeat(
        #     pulse_voltage=1.5,      # Pulse voltage (V)
        #     pulse_width=1.0,        # Pulse width (µs) - default is 1µs
        #     read_voltage=0.2,       # Read voltage (V)
        #     delay_between=10000.0,  # Delay between cycles (µs)
        #     num_cycles=5,           # Number of cycles
        #     clim=100e-3             # Current limit (A)
        # )
        
        # Example 2: Multi-read only (simplest test)
        # Uncomment to run:
        # results = scripts.multi_read_only(
        #     read_voltage=0.2,       # Read voltage (V)
        #     num_reads=10,           # Number of reads
        #     delay_between=10000.0,  # Delay between reads (µs)
        #     clim=100e-3             # Current limit (A)
        # )
        
        # Example 3: Potentiation only
        # Uncomment to run:
        # results = scripts.potentiation_only(
        #     set_voltage=1.5,        # Set voltage (V)
        #     pulse_width=100.0,      # Pulse width (µs)
        #     read_voltage=0.2,       # Read voltage (V)
        #     num_pulses=10,          # Number of pulses
        #     delay_between=10000.0,  # Delay between pulses (µs)
        #     clim=100e-3             # Current limit (A)
        # )
        
        # Example 4: Depression only
        # Uncomment to run:
        results = scripts.depression_only(
            reset_voltage=-1.5,     # Reset voltage (V, negative)
            pulse_width=10.0,      # Pulse width (µs)
            read_voltage=0.2,       # Read voltage (V)
            num_pulses=10,          # Number of pulses
            delay_between=100.0,  # Delay between pulses (µs)
            clim=100e-3,             # Current limit (A)
            num_cycles = 1,
        )
        
        # Example 5: Pulse then multiple reads
        # Uncomment to run:
        # results = scripts.pulse_multi_read(
        #     pulse_voltage=1.0,      # Pulse voltage (V)
        #     pulse_width=10.0,      # Pulse width (µs)
        #     num_pulses=1,           # Number of pulses
        #     delay_between_pulses=100.0,  # Delay between pulses (µs)
        #     read_voltage=0.2,       # Read voltage (V)
        #     num_reads=10,           # Number of reads
        #     delay_between_reads=100.0,   # Delay between reads (µs)
        #     clim=100e-3             # Current limit (A)
        # )
        
        # Example 6: Relaxation after multi-pulse
        # Uncomment to run:
        # results = scripts.relaxation_after_multi_pulse(
        #     pulse_voltage=1.5,      # Pulse voltage (V)
        #     num_pulses=5,           # Number of pulses
        #     pulse_width=10.0,      # Pulse width (µs)
        #     delay_between_pulses=100.0,  # Delay between pulses (µs)
        #     read_voltage=0.2,       # Read voltage (V)
        #     num_reads=20,           # Number of reads
        #     delay_between_reads=100.0,   # Delay between reads (µs)
        #     clim=100e-3             # Current limit (A)
        # )
        
        # ============================================================================
        # DEFAULT TEST - Uncomment one of the above or modify this default:
        # ============================================================================
        # results = scripts.pulse_read_repeat(
        #     pulse_voltage=1.5,
        #     pulse_width=1.0,        # 1µs
        #     read_voltage=0.2,
        #     delay_between=10000.0,  # 10ms (10000µs)
        #     num_cycles=1,
        #     clim=100e-3
        # )
        
        # ============================================================================
        # DISPLAY RESULTS
        # ============================================================================
        print("\n" + "="*80)
        print("Test Results:")
        print("="*80)
        print(f"Total measurements: {len(results['timestamps'])}")
        print(f"Timestamps range: {min(results['timestamps']):.6e} to {max(results['timestamps']):.6e} s")
        
        valid_resistances = [r for r in results['resistances'] if abs(r) < 1e10 and abs(r) > 0]
        if valid_resistances:
            import statistics
            print(f"Resistance range: {min(valid_resistances)/1e3:.2f} to {max(valid_resistances)/1e3:.2f} kOhm")
            print(f"Resistance mean: {statistics.mean(valid_resistances)/1e3:.2f} kOhm")
            print(f"Resistance std dev: {statistics.stdev(valid_resistances)/1e3:.2f} kOhm")
        
        print("\nFirst 10 measurements:")
        for i in range(min(10, len(results['timestamps']))):
            r_str = f"{results['resistances'][i]/1e3:.2f}" if abs(results['resistances'][i]) < 1e10 else "inf"
            print(f"  {i:2d}: t={results['timestamps'][i]:.6e}s, "
                  f"V={results['voltages'][i]:.6f}V, "
                  f"I={results['currents'][i]:.6e}A, "
                  f"R={r_str}kOhm")
        
        print("\n✓ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        # Cleanup connection
        if scripts._controller:
            scripts._controller.disconnect()

