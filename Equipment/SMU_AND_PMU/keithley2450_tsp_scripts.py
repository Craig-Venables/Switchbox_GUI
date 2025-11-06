"""note : below is an example of a script using propper pulsing methods  """

def varying_width_pulses(self, pulse_voltage=1.0,
                         pulse_widths=None,
                         pulses_per_width=5,
                         read_voltage=0.2,
                         delay_between=10e-3,
                         clim=100e-3):
    if pulse_widths is None:
        pulse_widths = [50e-6, 100e-6, 500e-6, 1e-3]

    self.tsp.device.write('if varyingWidthPulses ~= nil then script.delete("varyingWidthPulses") end')
    time.sleep(0.01)
    self.tsp.device.write('loadscript varyingWidthPulses')

    self.tsp.device.write('smu.reset()')
    self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
    self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
    self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
    self.tsp.device.write('smu.measure.nplc = 0.01')
    self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
    self.tsp.device.write('defbuffer1.clear()')

    # prepare for timing and digital trigger line
    self.tsp.device.write('digio.line[1].mode = digio.MODE_TRIGGER_OUT')
    self.tsp.device.write('trigger.digout[1].logic = trigger.LOGIC_POSITIVE')

    # main loop
    self.tsp.device.write('local widths = {' + ','.join(str(w) for w in pulse_widths) + '}')
    self.tsp.device.write(f'local readV = {read_voltage}')
    self.tsp.device.write(f'local pulseV = {pulse_voltage}')
    self.tsp.device.write(f'local pulses_per_width = {pulses_per_width}')
    self.tsp.device.write(f'local delay_between = {delay_between}')

    self.tsp.device.write('smu.source.output = smu.ON')
    self.tsp.device.write('for _, width in ipairs(widths) do')
    self.tsp.device.write('  for n = 1, pulses_per_width do')
    self.tsp.device.write('    smu.source.level = pulseV')
    self.tsp.device.write('    trigger.digout[1].pulsewidth = width')
    self.tsp.device.write('    trigger.digout[1].assert()  -- 10 µs–range accuracy pulse marker')
    self.tsp.device.write('    trigger.timer[1].delay = width')
    self.tsp.device.write('    trigger.timer[1].start.generate()')
    self.tsp.device.write('    trigger.timer[1].wait()')
    self.tsp.device.write('    smu.source.level = 0')
    self.tsp.device.write('    smu.source.level = readV')
    self.tsp.device.write('    smu.measure.read(defbuffer1)')
    self.tsp.device.write('    smu.source.level = 0')
    self.tsp.device.write('    delay(delay_between)')
    self.tsp.device.write('  end')
    self.tsp.device.write('end')
    self.tsp.device.write('smu.source.output = smu.OFF')
    self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.readings)')
    self.tsp.device.write('endscript')

    # execute and collect data
    self.tsp.device.write('varyingWidthPulses()')
    self.tsp.device.write('waitcomplete()')
    result = self.tsp.device.read().strip()
    return result

"""
Keithley 2450 TSP Testing Scripts

Specialized pulse and measurement sequences for device characterization.
All results returned as: {'timestamps': [...], 'voltages': [...], 'currents': [...], 'resistances': [...]}

═══════════════════════════════════════════════════════════════════════════════
AVAILABLE TEST FUNCTIONS
═══════════════════════════════════════════════════════════════════════════════

📋 BASIC PULSE-READ PATTERNS
────────────────────────────────────────────────────────────────────────────────
1. pulse_read_repeat()
   Pattern: (Pulse → Read → Delay) × N
   Use: Basic pulse response, immediate read after each pulse
   Params: pulse_voltage, pulse_width, read_voltage, delay_between, num_cycles

2. pulse_then_read()
   Pattern: (Pulse → Delay → Read) × N
   Use: Delayed read after pulse, test relaxation/settling
   Params: pulse_voltage, pulse_width, delay_after_pulse, read_voltage, num_cycles

3. multi_pulse_then_read()
   Pattern: (Pulse×N → Read) × Cycles
   Use: Cumulative effect of multiple pulses before reading
   Params: pulse_voltage, num_pulses_per_read, pulse_width, delay_between_pulses, 
           read_voltage, num_cycles, delay_between_cycles

📊 ADVANCED CHARACTERIZATION
────────────────────────────────────────────────────────────────────────────────
4. varying_width_pulses()
   Pattern: Sweep of different pulse widths with read before/after each
   Use: Find optimal pulse timing, measure speed dependence
   Params: pulse_voltage, pulse_widths (list), read_voltage, num_pulses_per_width

5. pulse_multi_read()
   Pattern: Pulse → Read → Read → Read... (multiple consecutive reads)
   Use: Monitor state relaxation/drift immediately after pulse
   Params: pulse_voltage, pulse_width, read_voltage, num_reads, delay_between_reads

6. multi_read_only()
   Pattern: Just reads, no pulses
   Use: Baseline noise, read disturb, initial state characterization
   Params: read_voltage, num_reads, delay_between_reads

🧠 MEMRISTOR / RRAM TESTS
────────────────────────────────────────────────────────────────────────────────
7. potentiation_depression_cycle()
   Pattern: Gradual SET (LRS) → Gradual RESET (HRS) → Gradual SET
   Use: Synaptic weight update, analog programming, neuromorphic applications
   Params: set_voltage, reset_voltage, read_voltage, num_steps (each direction)

8. potentiation_only()
   Pattern: Repeated SET pulses with reads (LRS programming)
   Use: Gradual conductance increase, weight potentiation
   Params: set_voltage, pulse_width, read_voltage, num_pulses

9. depression_only()
   Pattern: Repeated RESET pulses with reads (HRS programming)
   Use: Gradual conductance decrease, weight depression
   Params: reset_voltage, pulse_width, read_voltage, num_pulses

⏱️ RELIABILITY / STABILITY TESTS
────────────────────────────────────────────────────────────────────────────────
10. endurance_test()
    Pattern: (SET → Read → RESET → Read) × N cycles
    Use: Device lifetime, cycling endurance, degradation monitoring
    Params: set_voltage, reset_voltage, read_voltage, num_cycles

11. retention_test()
    Pattern: Pulse → Read @ t1 → Read @ t2 → Read @ t3...
    Use: Non-volatile state retention, data stability over time
    Params: pulse_voltage, read_voltage, read_intervals (list), total_time

🔬 RELAXATION & DYNAMICS TESTS
────────────────────────────────────────────────────────────────────────────────
12. relaxation_after_multi_pulse()
    Pattern: 1×Read → N×Pulse → N×Read (measure reads only)
    Use: Find how device relaxes after cumulative pulsing
    Params: pulse_voltage, num_pulses, read_voltage, num_reads, delays

13. relaxation_with_pulse_measurement()
    Pattern: 1×Read → N×Pulse → N×Read (measure EVERYTHING)
    Use: Full relaxation characterization including pulse peaks
    Params: pulse_voltage, num_pulses, read_voltage, num_reads, delays

🔄 PULSE WIDTH CHARACTERIZATION
────────────────────────────────────────────────────────────────────────────────
14. width_sweep_with_reads()
    Pattern: For each width: (Read→Pulse→Read)×N, Reset, next width
    Use: Measure pulse width dependence (reads only)
    Params: pulse_voltage, pulse_widths (list), num_pulses_per_width, reset

15. width_sweep_with_all_measurements()
    Pattern: For each width: (Read→Pulse→Read)×N, Reset (measure ALL)
    Use: Full width characterization including pulse peak currents
    Params: pulse_voltage, pulse_widths (list), num_pulses_per_width, reset

🚧 PLACEHOLDERS (Not Yet Implemented)
────────────────────────────────────────────────────────────────────────────────
16. switching_threshold_test()
    Use: Find minimum voltage for state switching (V_set, V_reset)

17. multilevel_switching_test()
    Use: Characterize intermediate resistance states for MLC

═══════════════════════════════════════════════════════════════════════════════
WHAT'S MISSING?
═══════════════════════════════════════════════════════════════════════════════

Potential additions:
  - IV sweep (continuous voltage ramp)
  - Forming operation (initial electroforming)
  - Pulse amplitude sweep (vary voltage, fixed width)  PRIORITY
  - Switching threshold test (find V_set/V_reset min)
  - Multi-level switching (intermediate resistance states)
  - Read disturb immunity test (how many reads before state corruption)
  - Temperature-dependent characterization
  - AC impedance / frequency response
  - Compliance-limited forming
  - State verification with multiple read voltages
  - Incremental step pulse programming (ISPP)
  - Pattern-dependent testing (alternating SET/RESET sequences)

═══════════════════════════════════════════════════════════════════════════════
"""

import time
from typing import List, Dict, Optional
from .Keithley2450_TSP import Keithley2450_TSP


# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE LIMITS - MODIFY THESE FOR YOUR DEVICE SAFETY REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════════════════
# Min pulse width is currently 1e-3 seconds, cant get it any faster when not measuring 
# when measuring 2-3e-3 seems resonable. 
# Example: To allow 100µs pulses, change MIN_PULSE_WIDTH to 100e-6
#          To disable checking, set ENABLE_PULSE_WIDTH_CHECK = False
#
# All parameters are validated and clamped to these limits with warnings.
# ═══════════════════════════════════════════════════════════════════════════════

# Pulse width limits (seconds)
MIN_PULSE_WIDTH = 1e-3      # 1ms - minimum safe pulse width
MAX_PULSE_WIDTH = 10.0      # 10s - maximum pulse width
DEFAULT_PULSE_WIDTH = 100e-6  # 100µs default (will be clamped to MIN if too small)

# Voltage limits (volts)
MIN_VOLTAGE = 0.0           # Minimum voltage magnitude
MAX_VOLTAGE = 5.0           # Maximum voltage magnitude (positive or negative)
DEFAULT_READ_VOLTAGE = 0.2  # Default read voltage

# Current limits (amps)
MIN_CURRENT_LIMIT = 1e-6    # 1µA minimum compliance
MAX_CURRENT_LIMIT = 1.0     # 1A maximum compliance
DEFAULT_CURRENT_LIMIT = 100e-3  # 100mA default

# Delay/timing limits (seconds)
MIN_DELAY = 10e-6           # 10µs minimum delay between operations
MAX_DELAY = 3600.0          # 1 hour maximum delay

# Buffer limits
MIN_BUFFER_CAPACITY = 10    # Keithley requirement
MAX_BUFFER_CAPACITY = 5311488  # Keithley max

# Safety flags
ENABLE_PULSE_WIDTH_CHECK = True   # Set False to disable min pulse width enforcement
ENABLE_VOLTAGE_CHECK = True       # Set False to disable voltage limit checks
ENABLE_CURRENT_CHECK = True       # Set False to disable current limit checks

# ═══════════════════════════════════════════════════════════════════════════════


class Keithley2450_TSP_Scripts:
    """TSP-based testing scripts for Keithley 2450."""
    
    def __init__(self, tsp_controller: Keithley2450_TSP):
        """
        Initialize with TSP controller instance.
        
        Args:
            tsp_controller: Connected Keithley2450_TSP instance
        """
        self.tsp = tsp_controller
        self.start_time = time.time()
        
    def _get_timestamp(self) -> float:
        """Get timestamp relative to tester initialization."""
        return time.time() - self.start_time
    
    def _validate_and_clamp(self, param_name: str, value: float, 
                           min_val: float, max_val: float, 
                           check_enabled: bool = True) -> float:
        """Validate and clamp parameter to safe limits with warnings."""
        if not check_enabled:
            return value
        
        original_value = value
        value = max(min_val, min(max_val, value))
        
        if abs(original_value - value) > 1e-12:
            print(f"⚠️  WARNING: {param_name} = {original_value} clamped to {value}")
            print(f"    Valid range: [{min_val}, {max_val}]")
        
        return value
    
    def _validate_pulse_width(self, width: float) -> float:
        """Validate pulse width against configured limits."""
        return self._validate_and_clamp(
            "pulse_width", width, 
            MIN_PULSE_WIDTH, MAX_PULSE_WIDTH,
            ENABLE_PULSE_WIDTH_CHECK
        )
    
    def _validate_voltage(self, voltage: float) -> float:
        """Validate voltage against configured limits."""
        return self._validate_and_clamp(
            "voltage", abs(voltage), 
            MIN_VOLTAGE, MAX_VOLTAGE,
            ENABLE_VOLTAGE_CHECK
        ) * (1 if voltage >= 0 else -1)
    
    def _validate_current_limit(self, clim: float) -> float:
        """Validate current limit against configured limits."""
        return self._validate_and_clamp(
            "current_limit", clim, 
            MIN_CURRENT_LIMIT, MAX_CURRENT_LIMIT,
            ENABLE_CURRENT_CHECK
        )
    
    def _validate_pulse_widths(self, widths: List[float]) -> List[float]:
        """Validate list of pulse widths."""
        return [self._validate_pulse_width(w) for w in widths]
    
    def _get_autodelay(self, current_range: float, use_high_capacitance: bool = False, 
                      source_mode: str = 'voltage') -> float:
        """
        Get autodelay time in seconds based on current range.
        
        Based on Keithley 2450 manual specifications:
        - Voltage source autodelay (default): Standard delays
        - Current source autodelay: Same delays for most ranges
        
        Args:
            current_range: Current measurement range (A)
            use_high_capacitance: If True, use high capacitance delays (default: False)
            source_mode: 'voltage' or 'current' (default: 'voltage')
        
        Returns:
            Autodelay time in seconds
        """
        # Autodelay lookup table (in milliseconds)
        # Format: (range_limit, voltage_source_std, voltage_source_high_cap, 
        #          current_source_std, current_source_high_cap)
        autodelay_table = [
            (10e-9,  150, 300, 150, 300),  # 10 nA
            (100e-9, 100, 200, 100, 200),  # 100 nA
            (1e-6,   3,   20,  3,   20),   # 1 μA
            (10e-6,  2,   10,  2,   10),   # 10 μA
            (100e-6, 1,   10,  1,   10),   # 100 μA
            (1e-3,   1,   10,  1,   10),   # 1 mA
            (10e-3,  1,   5,   1,   5),    # 10 mA
            (100e-3, 1,   5,   1,   5),    # 100 mA
            (1.0,    1,   5,   2,   5),    # 1 A
        ]
        
        # Find matching range (use range_limit that is >= current_range)
        delay_ms = 1.0  # Default fallback
        
        # Find the appropriate entry
        for range_limit, v_std, v_high, i_std, i_high in autodelay_table:
            if current_range <= range_limit:
                if source_mode == 'voltage':
                    delay_ms = v_high if use_high_capacitance else v_std
                else:  # current source
                    delay_ms = i_high if use_high_capacitance else i_std
                break
        
        # Convert milliseconds to seconds
        return delay_ms / 1000.0
    
    def _fast_read(self, read_voltage: float, clim: float) -> tuple:
        """Fast single-point measurement using direct TSP commands."""
        timestamp = self._get_timestamp()
        
        self.tsp.device.write(f"smu.source.level = {read_voltage}")
        self.tsp.device.write(f"i = smu.measure.read()")
        self.tsp.device.write(f"v = smu.source.level")
        self.tsp.device.write(f"smu.source.level = 0")
        self.tsp.device.write(f"print(string.format('%.6e,%.6e', v, i))")
        
        response = self.tsp.device.read().strip()
        
        try:
            parts = response.split(',')
            v = float(parts[0])
            i = float(parts[1])
            r = v / i if abs(i) > 1e-12 else 1e12
            return timestamp, v, i, r
        except:
            return timestamp, read_voltage, 0.0, 1e12
    
    def _fast_pulse(self, pulse_voltage: float, pulse_width: float) -> None:
        """Fast pulse using direct TSP commands (no script loading)."""
        self.tsp.device.write(f"smu.source.level = {pulse_voltage}")
        self.tsp.device.write(f"delay({pulse_width})")
        self.tsp.device.write(f"smu.source.level = 0")
    
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

    def _flush_output_buffer(self):
        """Clear any leftover data in the instrument's output buffer.
        
        This prevents reading stale data from previous test runs.
        """
        try:
            # Try to read and discard any leftover data (non-blocking with short timeout)
            old_timeout = self.tsp.device.timeout
            self.tsp.device.timeout = 100  # Very short timeout for flushing
            try:
                # Read until buffer is empty (will raise exception when empty)
                while True:
                    self.tsp.device.read()
            except:
                pass  # Expected when buffer is empty
            self.tsp.device.timeout = old_timeout
        except:
            pass  # If flushing fails, continue anyway
    
    def _parse_timestamped_buffer(self, response: str) -> Optional[Dict]:
        """Parse buffer output containing (timestamp, source, reading) triplets.

        Returns dict with timestamps, voltages, currents, resistances if parse succeeds,
        otherwise returns None to allow caller to fallback.
        """
        try:
            values = [float(x.strip()) for x in response.split(',') if x.strip()]
        except Exception:
            return None
        if not values or len(values) % 3 != 0:
            return None
        timestamps: List[float] = []
        voltages: List[float] = []
        currents: List[float] = []
        resistances: List[float] = []
        for i in range(0, len(values), 3):
            ts = values[i]
            v = values[i + 1]
            i_val = values[i + 2]
            r = v / i_val if abs(i_val) > 1e-12 else 1e12
            timestamps.append(ts)
            voltages.append(v)
            currents.append(i_val)
            resistances.append(r)
        return {
            'timestamps': timestamps,
            'voltages': voltages,
            'currents': currents,
            'resistances': resistances,
        }
    
    def pulse_read_repeat(self, pulse_voltage: float = 1.0, 
                         pulse_width: float = 100e-6,
                         read_voltage: float = 0.2,
                         delay_between: float = 10e-3,
                         num_cycles: int = 10,
                         clim: float = 100e-3) -> Dict:
        """(Pulse → Read → Delay) × N cycles. FAST buffer-based implementation.
        Current limit of 2ms pulse , read 2.45ms, 0 delay = 1ms gap
        There is always a delay of 1ms for anything """
        # Validate parameters
        pulse_width = self._validate_pulse_width(pulse_width)
        pulse_voltage = self._validate_voltage(pulse_voltage)
        read_voltage = self._validate_voltage(read_voltage)
        clim = self._validate_current_limit(clim)
        
        print(f"Starting FAST pulse_read_repeat: {num_cycles} cycles, {pulse_voltage}V pulse, {read_voltage}V read")
        
        start_time = time.time()
        
        # Delete existing script
        self.tsp.device.write('if pulseReadRepeat ~= nil then script.delete("pulseReadRepeat") end')
        time.sleep(0.01)
        
        # Calculate fixed ranges for speed (20% headroom)
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)  # Minimum 200mV range
        i_range = clim * 1.2
        
        # Upload complete TSP script with buffer-based measurement
        self.tsp.device.write('loadscript pulseReadRepeat')
        # Setup buffer (minimum 10 readings required) - add 1 for initial read
        buffer_capacity = max(num_cycles + 1, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        # Configure measure first (per manual), then source and limit
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        # Initial read before any pulses
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        # Fast pulse loop - no print() overhead!
        self.tsp.device.write(f'for cycle = 1, {num_cycles} do')
        self.tsp.device.write(f'  smu.source.level = {pulse_voltage}')
        self.tsp.device.write(f'  delay({pulse_width})')
        self.tsp.device.write('  smu.source.level = 0')
        #self.tsp.device.write('  delay(0.000010)')  # 10µs settle
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')  # Read directly into buffer!
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  if cycle < {num_cycles} then')
        self.tsp.device.write(f'    delay({delay_between})')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        # Restore settings and output all buffer data at once
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration for proper timeout
        # Pattern: Initial read + num_cycles × (pulse_width + read_time + delay_between)
        time_per_cycle = pulse_width + 0.001 + delay_between  # Pulse + read + delay
        expected_duration = 0.001 + num_cycles * time_per_cycle + 0.5  # Initial read + cycles + safety margin
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        # Set longer timeout for long tests
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))  # 1.5x expected, min 30s
        
        # Execute script (runs entirely on instrument)
        print(f"  Executing {num_cycles} cycles on instrument...")
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('pulseReadRepeat()')
        
        # Wait for script to complete - waitcomplete() is non-blocking in this context
        print(f"  Waiting {expected_duration:.1f}s for instrument to complete...")
        time.sleep(expected_duration + 0.5)  # Wait full duration + safety margin
        
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)  # Small additional wait after waitcomplete
        
        # Collect all results at once from buffer
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        print("  Collecting buffer data...")
        try:
            # Increase timeout for large buffer reads (100 readings can be ~2KB)
            original_timeout = self.tsp.device.timeout
            self.tsp.device.timeout = 10000  # 10 second timeout
            
            # Read entire buffer output (all values in one line, comma-separated)
            response = self.tsp.device.read().strip()
            
            # Restore original timeout
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements from buffer")
                return self._format_results(parsed['timestamps'], parsed['voltages'], parsed['currents'], parsed['resistances'])
            
            current_readings = [float(x.strip()) for x in response.split(',') if x.strip()]
            print(f"  Retrieved {len(current_readings)} measurements from buffer (no timestamps)")
            
            for idx, i in enumerate(current_readings):
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                # First measurement is initial read (t=0), rest are cycles
                if idx == 0:
                    ts = 0.0
                else:
                    # Cycle number is idx - 1 (since idx 0 is initial read)
                    cycle = idx - 1
                    ts = 0.001 + cycle * (pulse_width + 0.001 + delay_between)  # 0.001 for initial read duration
                timestamps.append(ts)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                    
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
            import traceback
            traceback.print_exc()
        
        elapsed = time.time() - start_time
        print(f"✓ pulse_read_repeat complete in {elapsed:.2f}s")
        print(f"  Average: {elapsed/num_cycles*1000:.2f}ms per cycle")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def pulse_then_read(self, pulse_voltage: float = 1.0,
                       pulse_width: float = 100e-6,
                       read_voltage: float = 0.2,
                       delay_after_pulse: float = 1e-3,
                       num_cycles: int = 10,
                       clim: float = 100e-3) -> Dict:
        """(Pulse → Delay → Read) × N cycles. Runs entirely on-instrument."""
        print(f"Starting pulse_then_read: {num_cycles} cycles, {delay_after_pulse*1e3:.2f}ms delay")
        
        start_time = time.time()
        
        self.tsp.device.write('if pulseThenRead ~= nil then script.delete("pulseThenRead") end')
        time.sleep(0.01)
        
        self.tsp.device.write('loadscript pulseThenRead')
        # Set measure function FIRST (per manual), then source settings
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.source.output = smu.ON')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        # Initial read before any pulses
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('local i_init = smu.measure.read()')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write(f'print(string.format("%.6e,%.6e", {read_voltage}, i_init))')
        self.tsp.device.write(f'for cycle = 1, {num_cycles} do')
        self.tsp.device.write(f'  smu.source.level = {pulse_voltage}')
        self.tsp.device.write(f'  delay({pulse_width})')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  delay({delay_after_pulse})')
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  local i = smu.measure.read()')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  print(string.format("%.6e,%.6e", {read_voltage}, i))')
        self.tsp.device.write('end')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('endscript')
        
        self.tsp.device.write('pulseThenRead()')
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.05)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        # Calculate estimated timestamps
        # Pattern: Initial read + (pulse→read→delay) × N
        # First read initial value
        try:
            response = self.tsp.device.read().strip()
            parts = response.split(',')
            v = float(parts[0])
            i = float(parts[1])
            r = v / i if abs(i) > 1e-12 else 1e12
            timestamps.append(0.0)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            print(f"  Initial read: R = {r:.2e} Ω")
        except:
            pass
        
        for cycle in range(num_cycles):
            try:
                response = self.tsp.device.read().strip()
                parts = response.split(',')
                v = float(parts[0])
                i = float(parts[1])
                r = v / i if abs(i) > 1e-12 else 1e12
                
                # Estimate time: cycle * (pulse_width + delay + read)
                ts = cycle * (pulse_width + delay_after_pulse + 0.001)
                timestamps.append(ts)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                
                if (cycle + 1) % 5 == 0 or cycle == num_cycles - 1:
                    print(f"  Cycle {cycle+1}/{num_cycles}: R = {r:.2e} Ω")
            except:
                pass
        
        print("✓ pulse_then_read complete")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def varying_width_pulses(self, pulse_voltage: float = 1.0,
                            pulse_widths: List[float] = None,
                            pulses_per_width: int = 5,
                            read_voltage: float = 0.2,
                            delay_between: float = 10e-3,
                            clim: float = 100e-3) -> Dict:
        """Test multiple pulse widths. FAST buffer-based."""
        if pulse_widths is None:
            pulse_widths = [50e-6, 100e-6, 500e-6, 1e-3]
        
        print(f"Starting FAST varying_width_pulses: {len(pulse_widths)} widths, {pulses_per_width} pulses each")
        
        start_time = time.time()
        total_measurements = 1 + len(pulse_widths) * pulses_per_width
        
        self.tsp.device.write('if varyingWidthPulses ~= nil then script.delete("varyingWidthPulses") end')
        time.sleep(0.01)
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript varyingWidthPulses')
        # Setup buffer (minimum 10 readings required)
        buffer_capacity = max(total_measurements, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        # Set measure function and range FIRST (per manual), then source settings
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        # Initial read to buffer
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        # Test each width
        for width in pulse_widths:
            self.tsp.device.write(f'for pulse_num = 1, {pulses_per_width} do')
            self.tsp.device.write(f'  smu.source.level = {pulse_voltage}')
            self.tsp.device.write(f'  delay({width})')
            self.tsp.device.write('  smu.source.level = 0')
            self.tsp.device.write('  delay(0.000010)')
            self.tsp.device.write(f'  smu.source.level = {read_voltage}')
            self.tsp.device.write('  smu.measure.read(defbuffer1)')
            self.tsp.device.write('  smu.source.level = 0')
            self.tsp.device.write(f'  if pulse_num < {pulses_per_width} then delay({delay_between}) end')
            self.tsp.device.write('end')
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        print(f"  Executing {total_measurements} measurements...")
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('varyingWidthPulses()')
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        width_labels = []
        
        print("  Collecting buffer data...")
        try:
            original_timeout = self.tsp.device.timeout
            self.tsp.device.timeout = 10000
            
            response = self.tsp.device.read().strip()
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                # Attach width labels matching each measurement count
                count = len(parsed['timestamps'])
                # Heuristic: first is initial read, remaining split equally by widths
                if count >= 1:
                    width_labels.append(0.0)
                    per_width = (count - 1) // max(1, len(pulse_widths))
                    for width in pulse_widths:
                        width_labels.extend([width] * per_width)
                    width_labels = width_labels[:count]
                return self._format_results(parsed['timestamps'], parsed['voltages'], parsed['currents'], parsed['resistances'],
                                           pulse_widths=width_labels)
            
            current_readings = [float(x.strip()) for x in response.split(',') if x.strip()]
            print(f"  Retrieved {len(current_readings)} measurements (no timestamps)")
            
            if current_readings:
                i = current_readings[0]
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                timestamps.append(time.time() - start_time)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                width_labels.append(0.0)
                print(f"  Initial: R = {r:.2e} Ω")
            
            idx = 1
            for width in pulse_widths:
                for pulse_num in range(pulses_per_width):
                    if idx < len(current_readings):
                        i = current_readings[idx]
                        v = read_voltage
                        r = v / i if abs(i) > 1e-12 else 1e12
                        timestamps.append(time.time() - start_time)
                        voltages.append(v)
                        currents.append(i)
                        resistances.append(r)
                        width_labels.append(width)
                        idx += 1
                            
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ varying_width_pulses complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances,
                                   pulse_widths=width_labels)
    
    def potentiation_depression_cycle(self, set_voltage: float = 2.0,
                                     reset_voltage: float = -2.0,
                                     pulse_width: float = 100e-6,
                                     read_voltage: float = 0.2,
                                     steps: int = 20,
                                     num_cycles: int = 1,
                                     delay_between: float = 10e-3,
                                     clim: float = 100e-3) -> Dict:
        """Full potentiation then depression cycle, repeated N times. FAST buffer-based.
        
        Pattern: Initial Read → (Potentiation → Depression) × num_cycles
        """
        print(f"Starting FAST potentiation-depression cycle: {num_cycles} cycle(s), {steps} steps each phase")
        
        start_time = time.time()
        total_measurements = 1 + (steps * 2 * num_cycles)  # Initial read + (pot + dep) × cycles
        
        self.tsp.device.write('if potDepCycle ~= nil then script.delete("potDepCycle") end')
        time.sleep(0.01)
        
        v_range = max(abs(set_voltage), abs(reset_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript potDepCycle')
        # Setup buffer (minimum 10 readings required) - add 1 for initial read
        buffer_capacity = max(total_measurements + 1, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        # Initial read before any pulses
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        # Main cycle loop: (Potentiation → Depression) × num_cycles
        self.tsp.device.write(f'for cycle = 1, {num_cycles} do')
        # Potentiation phase
        self.tsp.device.write(f'  for step = 1, {steps} do')
        self.tsp.device.write(f'    smu.source.level = {set_voltage}')
        self.tsp.device.write(f'    delay({pulse_width})')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    delay(0.000010)')
        self.tsp.device.write(f'    smu.source.level = {read_voltage}')
        self.tsp.device.write('    smu.measure.read(defbuffer1)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write(f'    if step < {steps} then delay({delay_between}) end')
        self.tsp.device.write('  end')
        # Depression phase
        self.tsp.device.write(f'  for step = 1, {steps} do')
        self.tsp.device.write(f'    smu.source.level = {reset_voltage}')
        self.tsp.device.write(f'    delay({pulse_width})')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    delay(0.000010)')
        self.tsp.device.write(f'    smu.source.level = {read_voltage}')
        self.tsp.device.write('    smu.measure.read(defbuffer1)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write(f'    if step < {steps} then delay({delay_between}) end')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration for proper timeout
        # Pattern: Initial read + num_cycles × (potentiation + depression)
        # Each step: pulse_width + 0.00001 settle + read_time (~0.001) + delay_between
        time_per_step = pulse_width + 0.00001 + 0.001 + delay_between
        time_per_cycle = steps * 2 * time_per_step  # Potentiation + Depression
        expected_duration = 0.001 + num_cycles * time_per_cycle + 0.5  # Initial read + cycles + safety margin
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        # Set longer timeout for long tests
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))  # 1.5x expected, min 30s
        
        print("  Running potentiation-depression cycle on instrument...")
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('potDepCycle()')
        
        # Wait for script to complete - waitcomplete() is non-blocking in this context
        # We need to wait the full expected duration
        print(f"  Waiting {expected_duration:.1f}s for instrument to complete...")
        time.sleep(expected_duration + 0.5)  # Wait full duration + safety margin
        
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)  # Small additional wait after waitcomplete
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        phases = []
        
        print("  Collecting buffer data...")
        try:
            # Timeout already set above for script execution, keep it for reading
            response = self.tsp.device.read().strip()
            
            # Restore original timeout after reading
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                # Assign phases based on count - first is initial, rest alternate potentiation/depression per cycle
                count = len(parsed['timestamps'])
                phases.append('initial')  # First measurement is initial read
                for idx in range(1, count):  # Start from 1 (skip initial read)
                    step_idx = idx - 1  # Step number (idx 0 is initial read)
                    # Calculate which cycle and phase we're in
                    steps_per_cycle = steps * 2  # Potentiation + Depression
                    cycle_num = step_idx // steps_per_cycle
                    step_in_cycle = step_idx % steps_per_cycle
                    # Determine phase: first half of cycle is potentiation, second half is depression
                    phase = 'potentiation' if step_in_cycle < steps else 'depression'
                    phases.append(phase)
                return self._format_results(parsed['timestamps'], parsed['voltages'], parsed['currents'], parsed['resistances'],
                                           phase=phases)
            
            current_readings = [float(x.strip()) for x in response.split(',') if x.strip()]
            print(f"  Retrieved {len(current_readings)} measurements (no timestamps)")
            
            for idx, i in enumerate(current_readings):
                # First measurement is initial read, rest are steps
                if idx == 0:
                    phase = 'initial'
                    ts = 0.0
                else:
                    step_idx = idx - 1  # Step number (idx 0 is initial read)
                    # Calculate which cycle and phase we're in
                    steps_per_cycle = steps * 2  # Potentiation + Depression
                    step_in_cycle = step_idx % steps_per_cycle
                    phase = 'potentiation' if step_in_cycle < steps else 'depression'
                    ts = 0.001 + step_idx * (pulse_width + 0.001 + delay_between)
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                timestamps.append(ts)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                phases.append(phase)
                    
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ Full cycle complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances,
                                   phase=phases)
    
    def potentiation_only(self, set_voltage: float = 2.0,
                         pulse_width: float = 100e-6,
                         read_voltage: float = 0.2,
                         num_pulses: int = 20,
                         delay_between: float = 10e-3,
                         num_post_reads: int = 0,
                         post_read_interval: float = 1e-3,
                         clim: float = 100e-3) -> Dict:
        """Potentiation only. FAST buffer-based.
        
        Optional post-pulse reads to observe relaxation after all pulses.
        """
        post_reads_enabled = num_post_reads > 0
        total_measurements = 1 + num_pulses + (num_post_reads if post_reads_enabled else 0)
        
        print(f"Starting FAST potentiation: {num_pulses} pulses at {set_voltage}V")
        if post_reads_enabled:
            print(f"  + {num_post_reads} post-pulse reads at {post_read_interval*1000:.1f}ms intervals")
        
        start_time = time.time()
        
        self.tsp.device.write('if potentiationOnly ~= nil then script.delete("potentiationOnly") end')
        time.sleep(0.01)
        
        v_range = max(abs(set_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript potentiationOnly')
        buffer_capacity = max(total_measurements, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        # Initial read before any pulses
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        # Main pulse loop
        self.tsp.device.write(f'for pulse = 1, {num_pulses} do')
        self.tsp.device.write(f'  smu.source.level = {set_voltage}')
        self.tsp.device.write(f'  delay({pulse_width})')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('  delay(0.000010)')
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  if pulse < {num_pulses} then delay({delay_between}) end')
        self.tsp.device.write('end')
        # Post-pulse reads (optional)
        if post_reads_enabled:
            self.tsp.device.write('delay(0.000010)')  # Small delay after last pulse
            self.tsp.device.write(f'for post_read = 1, {num_post_reads} do')
            self.tsp.device.write(f'  delay({post_read_interval})')
            self.tsp.device.write(f'  smu.source.level = {read_voltage}')
            self.tsp.device.write('  delay(0.001)')  # Hold read voltage for 1ms
            self.tsp.device.write('  smu.measure.read(defbuffer1)')
            self.tsp.device.write('  smu.source.level = 0')
            self.tsp.device.write('end')
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration for proper timeout
        # Pattern: Initial read + num_pulses × (pulse_width + settle + read_time + delay_between) + post_reads
        time_per_pulse = pulse_width + 0.00001 + 0.001 + delay_between  # Pulse + settle + read + delay
        pulse_phase_time = num_pulses * time_per_pulse
        post_read_time = num_post_reads * (post_read_interval + 0.001) if post_reads_enabled else 0
        expected_duration = 0.001 + pulse_phase_time + post_read_time + 0.5  # Initial read + pulses + post_reads + safety margin
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        # Set longer timeout for long tests
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))  # 1.5x expected, min 30s
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('potentiationOnly()')
        
        # Wait for script to complete - waitcomplete() is non-blocking in this context
        print(f"  Waiting {expected_duration:.1f}s for instrument to complete...")
        time.sleep(expected_duration + 0.5)  # Wait full duration + safety margin
        
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)  # Small additional wait after waitcomplete
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        print("  Collecting buffer data...")
        try:
            # Timeout already set above for script execution, keep it for reading
            response = self.tsp.device.read().strip()
            
            # Restore original timeout after reading
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                return self._format_results(parsed['timestamps'], parsed['voltages'], parsed['currents'], parsed['resistances'])
            
            current_readings = [float(x.strip()) for x in response.split(',') if x.strip()]
            print(f"  Retrieved {len(current_readings)} measurements (no timestamps)")
            
            for idx, i in enumerate(current_readings):
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                # First measurement is initial read (t=0), rest are pulses
                if idx == 0:
                    ts = 0.0
                    print(f"  Initial read: R = {r:.2e} Ω")
                else:
                    pulse = idx - 1  # Pulse number (idx 0 is initial read)
                    ts = 0.001 + pulse * (pulse_width + 0.001 + delay_between)
                    if (pulse + 1) % 5 == 0 or pulse == num_pulses - 1:
                        print(f"  Pulse {pulse+1}/{num_pulses}: R = {r:.2e} Ω")
                timestamps.append(ts)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ Potentiation complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def depression_only(self, reset_voltage: float = -2.0,
                       pulse_width: float = 100e-6,
                       read_voltage: float = 0.2,
                       num_pulses: int = 20,
                       delay_between: float = 10e-3,
                       num_post_reads: int = 0,
                       post_read_interval: float = 1e-3,
                       clim: float = 100e-3) -> Dict:
        """Depression only. FAST buffer-based.
        
        Optional post-pulse reads to observe relaxation after all pulses.
        """
        post_reads_enabled = num_post_reads > 0
        total_measurements = 1 + num_pulses + (num_post_reads if post_reads_enabled else 0)
        
        print(f"Starting FAST depression: {num_pulses} pulses at {reset_voltage}V")
        if post_reads_enabled:
            print(f"  + {num_post_reads} post-pulse reads at {post_read_interval*1000:.1f}ms intervals")
        
        start_time = time.time()
        
        self.tsp.device.write('if depressionOnly ~= nil then script.delete("depressionOnly") end')
        time.sleep(0.01)
        
        v_range = max(abs(reset_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript depressionOnly')
        buffer_capacity = max(total_measurements, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        # Initial read before any pulses
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        # Main pulse loop
        self.tsp.device.write(f'for pulse = 1, {num_pulses} do')
        self.tsp.device.write(f'  smu.source.level = {reset_voltage}')
        self.tsp.device.write(f'  delay({pulse_width})')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('  delay(0.000010)')
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  if pulse < {num_pulses} then delay({delay_between}) end')
        self.tsp.device.write('end')
        # Post-pulse reads (optional)
        if post_reads_enabled:
            self.tsp.device.write('delay(0.000010)')  # Small delay after last pulse
            self.tsp.device.write(f'for post_read = 1, {num_post_reads} do')
            self.tsp.device.write(f'  delay({post_read_interval})')
            self.tsp.device.write(f'  smu.source.level = {read_voltage}')
            self.tsp.device.write('  delay(0.001)')  # Hold read voltage for 1ms
            self.tsp.device.write('  smu.measure.read(defbuffer1)')
            self.tsp.device.write('  smu.source.level = 0')
            self.tsp.device.write('end')
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration for proper timeout
        # Pattern: Initial read + num_pulses × (pulse_width + settle + read_time + delay_between) + post_reads
        time_per_pulse = pulse_width + 0.00001 + 0.001 + delay_between  # Pulse + settle + read + delay
        pulse_phase_time = num_pulses * time_per_pulse
        post_read_time = num_post_reads * (post_read_interval + 0.001) if post_reads_enabled else 0
        expected_duration = 0.001 + pulse_phase_time + post_read_time + 0.5  # Initial read + pulses + post_reads + safety margin
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        # Set longer timeout for long tests
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))  # 1.5x expected, min 30s
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('depressionOnly()')
        
        # Wait for script to complete - waitcomplete() is non-blocking in this context
        print(f"  Waiting {expected_duration:.1f}s for instrument to complete...")
        time.sleep(expected_duration + 0.5)  # Wait full duration + safety margin
        
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)  # Small additional wait after waitcomplete
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        print("  Collecting buffer data...")
        try:
            # Timeout already set above for script execution, keep it for reading
            response = self.tsp.device.read().strip()
            
            # Restore original timeout after reading
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                return self._format_results(parsed['timestamps'], parsed['voltages'], parsed['currents'], parsed['resistances'])
            
            current_readings = [float(x.strip()) for x in response.split(',') if x.strip()]
            print(f"  Retrieved {len(current_readings)} measurements (no timestamps)")
            
            for idx, i in enumerate(current_readings):
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                # First measurement is initial read (t=0), rest are pulses
                if idx == 0:
                    ts = 0.0
                    print(f"  Initial read: R = {r:.2e} Ω")
                else:
                    pulse = idx - 1  # Pulse number (idx 0 is initial read)
                    ts = 0.001 + pulse * (pulse_width + 0.001 + delay_between)
                    if (pulse + 1) % 5 == 0 or pulse == num_pulses - 1:
                        print(f"  Pulse {pulse+1}/{num_pulses}: R = {r:.2e} Ω")
                timestamps.append(ts)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ Depression complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def pulse_multi_read(self, pulse_voltage: float = 1.0,
                        pulse_width: float = 100e-6,
                        num_pulses: int = 1,
                        delay_between_pulses: float = 1e-3,
                        read_voltage: float = 0.2,
                        num_reads: int = 50,
                        delay_between_reads: float = 100e-3,
                        clim: float = 100e-3) -> Dict:
        """N pulses then many reads. FAST buffer-based."""
        print(f"Starting FAST pulse_multi_read: {num_pulses} pulse(s), {num_reads} reads")
        
        start_time = time.time()
        
        self.tsp.device.write('if pulseMultiRead ~= nil then script.delete("pulseMultiRead") end')
        time.sleep(0.01)
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript pulseMultiRead')
        buffer_capacity = max(num_reads + 1, 10)  # Add 1 for initial read
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        # Initial read before any pulses
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        # N pulses
        self.tsp.device.write(f'for pulse_num = 1, {num_pulses} do')
        self.tsp.device.write(f'  smu.source.level = {pulse_voltage}')
        self.tsp.device.write(f'  delay({pulse_width})')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  delay({delay_between_pulses})')
        self.tsp.device.write('end')
        # Multiple reads to buffer
        self.tsp.device.write(f'for read_num = 1, {num_reads} do')
        self.tsp.device.write(f'  delay({delay_between_reads})')
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('end')
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        print(f"  {num_pulses} pulse(s): {pulse_voltage}V, {pulse_width*1e6:.1f}µs, then {num_reads} reads...")
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('pulseMultiRead()')
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        print("  Collecting buffer data...")
        try:
            original_timeout = self.tsp.device.timeout
            self.tsp.device.timeout = 10000
            
            response = self.tsp.device.read().strip()
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                return self._format_results(parsed['timestamps'], parsed['voltages'], parsed['currents'], parsed['resistances'])
            
            current_readings = [float(x.strip()) for x in response.split(',') if x.strip()]
            print(f"  Retrieved {len(current_readings)} measurements (no timestamps)")
            
            # First measurement is initial read (before pulses)
            if current_readings:
                i = current_readings[0]
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                timestamps.append(0.0)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                print(f"  Initial read: R = {r:.2e} Ω")
            
            # Remaining measurements are after pulses
            pulse_phase_time = 0.001 + num_pulses * (pulse_width + delay_between_pulses)  # Include initial read time
            for read_num, i in enumerate(current_readings[1:], start=1):  # Skip first (initial read)
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                ts = pulse_phase_time + (read_num - 1) * (delay_between_reads + 0.001)
                timestamps.append(ts)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                
                if (read_num + 1) % 10 == 0 or read_num == num_reads - 1:
                    print(f"  Read {read_num+1}/{num_reads}: R = {r:.2e} Ω")
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ pulse_multi_read complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def multi_read_only(self, read_voltage: float = 0.2,
                       num_reads: int = 100,
                       delay_between: float = 100e-3,
                       clim: float = 100e-3) -> Dict:
        """Continuous reading without pulses. FAST buffer-based."""
        print(f"Starting FAST multi_read_only: {num_reads} reads, no pulses")
        
        start_time = time.time()
        
        self.tsp.device.write('if multiReadOnly ~= nil then script.delete("multiReadOnly") end')
        time.sleep(0.01)
        
        v_range = abs(read_voltage) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript multiReadOnly')
        buffer_capacity = max(num_reads, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        self.tsp.device.write(f'for read_num = 1, {num_reads} do')
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  if read_num < {num_reads} then')
        self.tsp.device.write(f'    delay({delay_between})')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration for proper timeout
        # Each read: set voltage + measurement (~0.001s) + delay + set to 0
        time_per_read = 0.001 + delay_between + 0.00001  # ~1ms for measurement + delay + settle
        expected_duration = num_reads * time_per_read + 0.5  # Add 0.5s buffer
        
        # Set longer timeout for long tests and large buffer reads
        original_timeout = self.tsp.device.timeout
        # For large buffers: with timestamps + source values + readings, each point is ~30 bytes
        # At 115200 baud (typical USB), that's ~0.3ms per point, but add overhead
        # For 1000 reads: ~30KB = ~0.3s at max speed, but allow 10x for safety = 3s minimum
        # Scale with num_reads, but cap reasonable max
        buffer_read_time_seconds = max(3.0, num_reads * 0.003)  # At least 3s, ~3ms per read
        script_timeout = max(30000, int(expected_duration * 1000 * 1.5))  # 1.5x expected, min 30s
        read_timeout = max(30000, int(buffer_read_time_seconds * 1000))  # At least 30s for reading large buffers
        
        self.tsp.device.timeout = script_timeout
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('multiReadOnly()')
        self.tsp.device.write('waitcomplete()')
        # Wait for full execution - dynamic sleep based on expected duration
        time.sleep(expected_duration + 0.5)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        print("  Collecting buffer data...")
        try:
            # Set timeout for reading large buffers
            self.tsp.device.timeout = read_timeout
            
            response = self.tsp.device.read().strip()
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                return self._format_results(parsed['timestamps'], parsed['voltages'], parsed['currents'], parsed['resistances'])
            
            current_readings = [float(x.strip()) for x in response.split(',') if x.strip()]
            print(f"  Retrieved {len(current_readings)} measurements (no timestamps)")
            
            for read_num, i in enumerate(current_readings):
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                ts = read_num * (delay_between + 0.001)
                timestamps.append(ts)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                
                if (read_num + 1) % 20 == 0 or read_num == num_reads - 1:
                    print(f"  Read {read_num+1}/{num_reads}: R = {r:.2e} Ω")
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ multi_read_only complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def current_range_finder(self, test_voltage: float = 0.2,
                            num_reads_per_range: int = 10,
                            delay_between_reads: float = 10e-3,
                            current_ranges: List[float] = None) -> Dict:
        """
        Test different current measurement ranges to find the optimal one.
        
        Measures current at multiple ranges and returns statistics to help choose
        the best range for accurate measurements.
        
        Pattern: For each range: read × N times
        Useful for: Finding optimal current limit/range before running full tests
        
        Args:
            test_voltage: Voltage to apply for testing (V)
            num_reads_per_range: Number of measurements per range
            delay_between_reads: Delay between measurements (s)
            current_ranges: List of current limits to test (A)
                          Default: [1mA, 100µA, 10µA, 1µA]
        
        Returns:
            Dict with timestamps, voltages, currents, resistances, and range info
        """
        if current_ranges is None:
            # Default ranges: 1mA, 100µA, 10µA, 1µA
            current_ranges = [1e-3, 100e-6, 10e-6, 1e-6]
        
        print(f"Starting current_range_finder: testing {len(current_ranges)} ranges at {test_voltage}V")
        print(f"  Ranges to test: {[f'{r*1e6:.1f}µA' if r < 1e-3 else f'{r*1e3:.1f}mA' for r in current_ranges]}")
        
        start_time = time.time()
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        range_values = []  # Track which range was used
        range_stats = []   # Statistics per range
        
        v_range = abs(test_voltage) 
        v_range = max(v_range, 0.2)
        
        for range_idx, clim in enumerate(current_ranges):
            print(f"\n  [{range_idx+1}/{len(current_ranges)}] Testing range: {clim*1e6:.1f}µA limit")
            
            i_range = clim
            
            # Delete old script
            self.tsp.device.write(f'if rangeFinder{range_idx} ~= nil then script.delete("rangeFinder{range_idx}") end')
            time.sleep(0.01)
            
            # Create measurement script for this range
            # Follow Keithley manual order: measure function/range FIRST, then source settings
            # Use autorange for source limit to avoid 5076/5077 errors
            self.tsp.device.write(f'loadscript rangeFinder{range_idx}')
            buffer_capacity = max(num_reads_per_range, 10)
            self.tsp.device.write('defbuffer1.clear()')
            self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
            
            # Step 1: Set measure function and range FIRST (per manual)
            self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
            self.tsp.device.write(f'smu.measure.range = {i_range}')
            
            # Step 2: Set source function
            self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
            self.tsp.device.write(f'smu.source.range = {v_range}')
            
            # Step 3: Set source limit - use autorange for small ranges to avoid errors
            # For ranges >= 100µA, set explicit limit; for smaller, use autorange
            if i_range >= 100e-6:
                # Large enough range - set explicit limit
                self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
            else:
                # Very small range - use autorange to avoid 5076/5077 errors
                self.tsp.device.write('smu.source.ilimit.autorange = smu.ON')
            
            self.tsp.device.write('smu.measure.nplc = 0.01')
            self.tsp.device.write('smu.measure.autozero.enable = smu.ON')  # Enable for accuracy
            self.tsp.device.write('smu.source.output = smu.ON')
            
            # Take multiple readings
            self.tsp.device.write(f'for read_num = 1, {num_reads_per_range} do')
            self.tsp.device.write(f'  smu.source.level = {test_voltage}')
            self.tsp.device.write('  smu.measure.read(defbuffer1)')
            self.tsp.device.write('  smu.source.level = 0')
            self.tsp.device.write(f'  if read_num < {num_reads_per_range} then')
            self.tsp.device.write(f'    delay({delay_between_reads})')
            self.tsp.device.write('  end')
            self.tsp.device.write('end')
            
            self.tsp.device.write('smu.source.output = smu.OFF')
            self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
            self.tsp.device.write('endscript')
            
            # Execute
            self.tsp.device.write(f'rangeFinder{range_idx}()')
            self.tsp.device.write('waitcomplete()')
            time.sleep(0.1)
            
            # Collect data
            try:
                original_timeout = self.tsp.device.timeout
                self.tsp.device.timeout = 5000
                
                response = self.tsp.device.read().strip()
                self.tsp.device.timeout = original_timeout
                
                # Parse triplets: timestamp, source voltage, current
                parsed = self._parse_timestamped_buffer(response)
                if parsed:
                    current_readings = parsed['currents']
                else:
                    # Fallback to parsing just currents (shouldn't happen with triplet format)
                    current_readings = [float(x.strip()) for x in response.split(',') if x.strip()]
                
                # Calculate statistics for this range
                import numpy as np
                currents_array = np.array(current_readings)
                mean_i = np.mean(currents_array)
                std_i = np.std(currents_array)
                min_i = np.min(currents_array)
                max_i = np.max(currents_array)
                has_negative = np.any(currents_array < 0)
                
                mean_r = test_voltage / mean_i if abs(mean_i) > 1e-12 else 1e12
                
                stats = {
                    'range_limit': clim,
                    'mean_current': mean_i,
                    'std_current': std_i,
                    'min_current': min_i,
                    'max_current': max_i,
                    'mean_resistance': mean_r,
                    'has_negative': has_negative,
                    'cv_percent': (std_i / abs(mean_i) * 100) if abs(mean_i) > 1e-12 else 999
                }
                range_stats.append(stats)
                
                print(f"    Mean: {mean_i*1e6:.3f}µA, Std: {std_i*1e6:.3f}µA, CV: {stats['cv_percent']:.2f}%")
                print(f"    Range: [{min_i*1e6:.3f}, {max_i*1e6:.3f}]µA, Negative: {has_negative}")
                print(f"    → Resistance: {mean_r:.2e}Ω")
                
                # Store individual readings
                range_start_time = time.time() - start_time
                for idx, i in enumerate(current_readings):
                    v = test_voltage
                    r = v / i if abs(i) > 1e-12 else 1e12
                    ts = range_start_time + idx * (delay_between_reads + 0.001)
                    
                    timestamps.append(ts)
                    voltages.append(v)
                    currents.append(i)
                    resistances.append(r)
                    range_values.append(clim)
                    
            except Exception as e:
                print(f"    ❌ Error reading range {clim}: {e}")
        
        # Print recommendation
        print("\n" + "="*70)
        print("RANGE FINDER RESULTS:")
        print("="*70)
        
        # Find best range (lowest CV%, no negatives, reasonable current)
        best_range = None
        best_cv = 999
        
        for stats in range_stats:
            if not stats['has_negative'] and abs(stats['mean_current']) > 1e-9:
                if stats['cv_percent'] < best_cv:
                    best_cv = stats['cv_percent']
                    best_range = stats
        
        if best_range:
            print(f"\n✓ RECOMMENDED RANGE: {best_range['range_limit']*1e6:.1f}µA")
            print(f"  • Mean current: {best_range['mean_current']*1e6:.3f}µA")
            print(f"  • Stability (CV): {best_range['cv_percent']:.2f}%")
            print(f"  • Mean resistance: {best_range['mean_resistance']:.2e}Ω")
            print(f"  • No negative readings")
        else:
            print("\n⚠ No ideal range found - check your device/connections")
        
        print("\nAll ranges tested:")
        for idx, stats in enumerate(range_stats):
            status = "✓" if not stats['has_negative'] else "✗"
            print(f"  {status} {stats['range_limit']*1e6:6.1f}µA: "
                  f"Mean={stats['mean_current']*1e6:7.3f}µA, "
                  f"CV={stats['cv_percent']:6.2f}%, "
                  f"R={stats['mean_resistance']:.2e}Ω")
        
        print("="*70)
        
        elapsed = time.time() - start_time
        print(f"\n✓ current_range_finder complete in {elapsed:.2f}s")
        
        # Return results with extra info
        results = self._format_results(timestamps, voltages, currents, resistances)
        results['range_values'] = range_values
        results['range_stats'] = range_stats
        results['recommended_range'] = best_range['range_limit'] if best_range else None
        
        return results
    
    def endurance_test(self, set_voltage: float = 2.0,
                      reset_voltage: float = -2.0,
                      pulse_width: float = 100e-6,
                      read_voltage: float = 0.2,
                      num_cycles: int = 1000,
                      delay_between: float = 10e-3,
                      clim: float = 100e-3) -> Dict:
        """Endurance cycling: (SET → Read → RESET → Read) × N. Runs entirely on-instrument!"""
        print(f"Starting endurance test: {num_cycles} SET/RESET cycles")
        print("  Running on instrument (no PC communication during test)...")
        
        start_time = time.time()
        
        # Delete existing script
        self.tsp.device.write('if enduranceTest ~= nil then script.delete("enduranceTest") end')
        time.sleep(0.01)
        
        # Upload complete TSP script with full endurance loop
        self.tsp.device.write('loadscript enduranceTest')
        # Set measure function FIRST (per manual), then source settings
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.source.output = smu.ON')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        # Initial read before any cycles
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('local i_init = smu.measure.read()')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write(f'print(string.format("0,INIT,%.6e", i_init))')
        self.tsp.device.write(f'for cycle = 1, {num_cycles} do')
        # SET pulse + read
        self.tsp.device.write(f'  smu.source.level = {set_voltage}')
        self.tsp.device.write(f'  delay({pulse_width})')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  delay(0.001)')
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  local i_set = smu.measure.read()')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  delay({delay_between})')
        # RESET pulse + read
        self.tsp.device.write(f'  smu.source.level = {reset_voltage}')
        self.tsp.device.write(f'  delay({pulse_width})')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  delay(0.001)')
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  local i_reset = smu.measure.read()')
        self.tsp.device.write('  smu.source.level = 0')
        # Print both results
        self.tsp.device.write(f'  print(string.format("%d,SET,%.6e", cycle, i_set))')
        self.tsp.device.write(f'  print(string.format("%d,RESET,%.6e", cycle, i_reset))')
        self.tsp.device.write('end')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('endscript')
        
        # Execute script (this will take a while but runs on instrument!)
        test_start = time.time()
        self.tsp.device.write('enduranceTest()')
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)
        
        # Collect all results
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        cycle_numbers = []
        operations = []
        
        print("  Collecting results...")
        # Pattern: Initial read + (SET pulse + read + RESET pulse + read) × N cycles
        # First collect initial read
        try:
            response = self.tsp.device.read().strip()
            parts = response.split(',')
            cycle_num = int(parts[0])
            operation = parts[1]
            i = float(parts[2])
            v = read_voltage
            r = v / i if abs(i) > 1e-12 else 1e12
            timestamps.append(0.0)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            cycle_numbers.append(0)
            operations.append('INIT')
            print(f"  Initial read: R = {r:.2e} Ω")
        except:
            pass
        
        # Then collect cycle data: (SET pulse + read + RESET pulse + read) × N cycles
        for idx in range(num_cycles * 2):  # SET + RESET per cycle
            try:
                response = self.tsp.device.read().strip()
                parts = response.split(',')
                cycle_num = int(parts[0])
                operation = parts[1]
                i = float(parts[2])
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                
                # Estimate time based on pattern
                cycle_idx = (cycle_num - 1)
                is_set = (operation == 'SET')
                if is_set:
                    # SET: cycle * (full_cycle_time)
                    ts = cycle_idx * (2 * (pulse_width + 0.001 + delay_between))
                else:
                    # RESET: cycle * (full_cycle_time) + SET time
                    ts = cycle_idx * (2 * (pulse_width + 0.001 + delay_between)) + (pulse_width + 0.001 + delay_between)
                
                timestamps.append(ts)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                cycle_numbers.append(cycle_num - 1)  # 0-indexed
                operations.append(operation)
                
                if idx % 200 == 0 and idx > 0:
                    print(f"  Collected {idx}/{num_cycles*2} measurements...")
            except:
                pass
        
        elapsed = time.time() - test_start
        print(f"✓ Endurance test complete in {elapsed:.1f}s")
        print(f"  Average: {elapsed/num_cycles*1000:.1f}ms per cycle")
        return self._format_results(timestamps, voltages, currents, resistances,
                                   cycle_number=cycle_numbers, operation=operations)
    
    def retention_test(self, pulse_voltage: float = 2.0,
                      pulse_width: float = 100e-6,
                      read_voltage: float = 0.2,
                      read_intervals: List[float] = None,
                      clim: float = 100e-3) -> Dict:
        """Retention test. Initial pulse on-instrument, reads at PC-controlled intervals."""
        if read_intervals is None:
            read_intervals = [1, 10, 100, 1000, 10000]
        
        print(f"Starting retention test: {len(read_intervals)} reads over {read_intervals[-1]}s")
        
        start_time = time.time()
        
        # Upload simple read script (reused for each read)
        self.tsp.device.write('if retentionRead ~= nil then script.delete("retentionRead") end')
        time.sleep(0.01)
        
        self.tsp.device.write('loadscript retentionRead')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.source.output = smu.ON')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        # Initial pulse
        self.tsp.device.write(f'smu.source.level = {pulse_voltage}')
        self.tsp.device.write(f'delay({pulse_width})')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.001)')
        # Initial read
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('local i = smu.measure.read()')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write(f'print(string.format("%.6e,%.6e", {read_voltage}, i))')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('endscript')
        
        # Execute initial pulse and read
        print(f"  Setting initial state: {pulse_voltage}V pulse")
        self.tsp.device.write('retentionRead()')
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.05)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        # Get initial read
        response = self.tsp.device.read().strip()
        parts = response.split(',')
        v = float(parts[0])
        i = float(parts[1])
        r = v / i if abs(i) > 1e-12 else 1e12
        
        # Initial read at t=0
        ts = 0.0
        timestamps.append(ts)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        print(f"  t=0s: R = {r:.2e} Ω")
        
        # Create simple read-only script for subsequent reads
        self.tsp.device.write('if retentionReadOnly ~= nil then script.delete("retentionReadOnly") end')
        time.sleep(0.01)
        
        self.tsp.device.write('loadscript retentionReadOnly')
        self.tsp.device.write('smu.source.output = smu.ON')
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('local i = smu.measure.read()')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write(f'print(string.format("%.6e,%.6e", {read_voltage}, i))')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('endscript')
        
        # PC-controlled interval reads
        last_time = time.time()
        for interval in read_intervals:
            wait_time = interval - (time.time() - last_time)
            if wait_time > 0:
                print(f"  Waiting {wait_time:.1f}s until next read...")
                time.sleep(wait_time)
            
            self.tsp.device.write('retentionReadOnly()')
            self.tsp.device.write('waitcomplete()')
            time.sleep(0.02)
            
            response = self.tsp.device.read().strip()
            parts = response.split(',')
            v = float(parts[0])
            i = float(parts[1])
            r = v / i if abs(i) > 1e-12 else 1e12
            
            # Use actual interval time (defined by user)
            ts = interval
            timestamps.append(ts)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            print(f"  t={interval}s: R = {r:.2e} Ω")
            
            last_time = time.time()
        
        print("✓ Retention test complete")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def multi_pulse_then_read(self, pulse_voltage: float = 1.0,
                             num_pulses_per_read: int = 10,
                             pulse_width: float = 100e-6,
                             delay_between_pulses: float = 1e-3,
                             read_voltage: float = 0.2,
                             num_reads: int = 1,
                             delay_between_reads: float = 10e-3,
                             num_cycles: int = 20,
                             delay_between_cycles: float = 10e-3,
                             clim: float = 100e-3) -> Dict:
        """Send N pulses, then M reads. Repeat. FAST buffer-based.
        
        Pattern: (Pulse×N → Read×M) × num_cycles
        Useful for cumulative effects where multiple pulses change device state.
        """
        print(f"Starting FAST multi_pulse_then_read:")
        print(f"  {num_pulses_per_read} pulses → {num_reads} read(s), repeated {num_cycles} times")
        
        start_time = time.time()
        
        self.tsp.device.write('if multiPulseThenRead ~= nil then script.delete("multiPulseThenRead") end')
        time.sleep(0.01)
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript multiPulseThenRead')
        # Setup buffer for multiple reads per cycle (minimum 10) - add 1 for initial read
        buffer_capacity = max(num_cycles * num_reads + 1, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        # Set measure function and range FIRST (per manual), then source settings
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        
        # Initial read before any pulses
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        
        # Main cycle loop
        self.tsp.device.write(f'for cycle = 1, {num_cycles} do')
        # Send multiple pulses
        self.tsp.device.write(f'  for pulse = 1, {num_pulses_per_read} do')
        self.tsp.device.write(f'    smu.source.level = {pulse_voltage}')
        self.tsp.device.write(f'    delay({pulse_width})')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write(f'    if pulse < {num_pulses_per_read} then')
        self.tsp.device.write(f'      delay({delay_between_pulses})')
        self.tsp.device.write('    end')
        self.tsp.device.write('  end')
        # Multiple reads after all pulses
        self.tsp.device.write('  delay(0.000010)')
        self.tsp.device.write(f'  for read_num = 1, {num_reads} do')
        self.tsp.device.write(f'    smu.source.level = {read_voltage}')
        self.tsp.device.write('    smu.measure.read(defbuffer1)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write(f'    if read_num < {num_reads} then')
        self.tsp.device.write(f'      delay({delay_between_reads})')
        self.tsp.device.write('    end')
        self.tsp.device.write('  end')
        # Delay before next cycle
        self.tsp.device.write(f'  if cycle < {num_cycles} then')
        self.tsp.device.write(f'    delay({delay_between_cycles})')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        print(f"  Executing {num_cycles} cycles on instrument...")
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('multiPulseThenRead()')
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        print("  Collecting buffer data...")
        try:
            original_timeout = self.tsp.device.timeout
            self.tsp.device.timeout = 10000
            
            response = self.tsp.device.read().strip()
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                return self._format_results(parsed['timestamps'], parsed['voltages'], parsed['currents'], parsed['resistances'])
            
            current_readings = [float(x.strip()) for x in response.split(',') if x.strip()]
            print(f"  Retrieved {len(current_readings)} measurements (no timestamps)")
            
            # First measurement is initial read
            if current_readings:
                i = current_readings[0]
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                timestamps.append(0.0)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                print(f"  Initial read: R = {r:.2e} Ω")
            
            # Remaining measurements are cycle reads
            time_per_pulse_phase = num_pulses_per_read * (pulse_width + delay_between_pulses)
            time_per_read_phase = num_reads * (0.001 + delay_between_reads) if num_reads > 1 else 0.001
            time_per_cycle = time_per_pulse_phase + time_per_read_phase + delay_between_cycles
            
            for idx, i in enumerate(current_readings[1:], start=1):  # Skip first (initial read)
                v = read_voltage
                r = v / i if abs(i) > 1e-12 else 1e12
                # Adjust for initial read
                adjusted_idx = idx - 1  # Subtract 1 for initial read
                cycle_num = adjusted_idx // max(1, num_reads)
                read_num = adjusted_idx % max(1, num_reads)
                ts = 0.001 + cycle_num * time_per_cycle + time_per_pulse_phase + read_num * (0.001 + delay_between_reads)
                timestamps.append(ts)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                
                if (idx + 1) % 10 == 0 or idx == len(current_readings) - 1:
                    print(f"  Reading {idx+1}/{len(current_readings)}: R = {r:.2e} Ω")
                    
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ multi_pulse_then_read complete in {elapsed:.2f}s")
        print(f"  Total pulses sent: {num_pulses_per_read * num_cycles}")
        print(f"  Total reads collected: {len(current_readings)}")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def relaxation_after_multi_pulse(self, pulse_voltage: float = 1.5,
                                    num_pulses: int = 10,
                                    pulse_width: float = 100e-6,
                                    delay_between_pulses: float = 1e-3,
                                    read_voltage: float = 0.2,
                                    num_reads: int = 10,
                                    delay_between_reads: float = 100e-6,
                                    clim: float = 100e-3) -> Dict:
        """Relaxation test: 1×Read → N×Pulse → N×Read (measure reads only).
        
        Pattern: Initial read → Apply N pulses → Read N times to see relaxation
        Useful for: Finding how device state relaxes after multiple pulses
        """
        # Validate parameters
        pulse_width = self._validate_pulse_width(pulse_width)
        pulse_voltage = self._validate_voltage(pulse_voltage)
        read_voltage = self._validate_voltage(read_voltage)
        clim = self._validate_current_limit(clim)
        
        print(f"Starting relaxation_after_multi_pulse:")
        print(f"  1 read → {num_pulses} pulses → {num_reads} reads")
        
        start_time = time.time()
        
        self.tsp.device.write('if relaxAfterMulti ~= nil then script.delete("relaxAfterMulti") end')
        time.sleep(0.01)
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        total_measurements = 1 + num_reads  # Initial read + N reads after pulses
        
        self.tsp.device.write('loadscript relaxAfterMulti')
        buffer_capacity = max(total_measurements, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        # Set measure function and range FIRST (per manual), then source settings
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        
        # Initial read
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        
        # Apply N pulses (no measurement)
        self.tsp.device.write(f'for i = 1, {num_pulses} do')
        self.tsp.device.write(f'  smu.source.level = {pulse_voltage}')
        self.tsp.device.write(f'  delay({pulse_width})')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  if i < {num_pulses} then')
        self.tsp.device.write(f'    delay({delay_between_pulses})')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        self.tsp.device.write('delay(0.000010)')
        
        # Read N times to observe relaxation
        self.tsp.device.write(f'for i = 1, {num_reads} do')
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  if i < {num_reads} then')
        self.tsp.device.write(f'    delay({delay_between_reads})')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        print(f"  Executing on instrument...")
        
        # Calculate expected duration for proper timeout
        expected_duration = (
            0.001 +  # Initial read
            num_pulses * (pulse_width + delay_between_pulses) +  # All pulses
            num_reads * (delay_between_reads + 0.001) +  # All reads
            0.5  # Safety margin
        )
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        # Set longer timeout for long tests
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))  # 1.5x expected, min 30s
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('relaxAfterMulti()')
        
        # Wait for script to complete - waitcomplete() is non-blocking in this context
        # We need to wait the full expected duration
        print(f"  Waiting {expected_duration:.1f}s for instrument to complete...")
        time.sleep(expected_duration + 0.5)  # Wait full duration + safety margin
        
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)  # Small additional wait after waitcomplete
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        print("  Collecting buffer data...")
        try:
            # Timeout already set above for script execution, keep it for reading
            response = self.tsp.device.read().strip()
            
            # Parse triplets: timestamp, source voltage, current
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                n_measurements = len(parsed['timestamps'])
                print(f"  Retrieved {n_measurements} measurements")
                timestamps = parsed['timestamps']
                voltages = parsed['voltages']
                currents = parsed['currents']
                resistances = parsed['resistances']
            else:
                print(f"  ❌ Error parsing buffer data")
                
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        finally:
            # Restore original timeout
            self.tsp.device.timeout = original_timeout
        
        elapsed = time.time() - start_time
        print(f"✓ relaxation_after_multi_pulse complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def relaxation_after_multi_pulse_with_pulse_measurement(self, pulse_voltage: float = 1.5,
                                         num_pulses: int = 10,
                                         pulse_width: float = 100e-6,
                                         delay_between_pulses: float = 1e-3,
                                         read_voltage: float = 0.2,
                                         num_reads: int = 10,
                                         delay_between_reads: float = 100e-6,
                                         clim: float = 100e-3) -> Dict:
        """Relaxation test: 1×Read → N×Pulse → N×Read (measure EVERYTHING).
        
        Pattern: Initial read → Apply N pulses (measure at peak) → Read N times
        Useful for: Full characterization including pulse peak current
        """
        print(f"Starting relaxation_after_multi_pulse_with_pulse_measurement:")
        print(f"  1 read → {num_pulses} pulses (measured) → {num_reads} reads")
        
        start_time = time.time()
        
        self.tsp.device.write('if relaxWithPulseMeas ~= nil then script.delete("relaxWithPulseMeas") end')
        time.sleep(0.01)
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        total_measurements = 1 + num_pulses + num_reads  # Initial read + N pulse peaks + N reads
        
        self.tsp.device.write('loadscript relaxWithPulseMeas')
        buffer_capacity = max(total_measurements, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        
        # Initial read
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        
        # Apply N pulses WITH measurement at peak
        self.tsp.device.write(f'for i = 1, {num_pulses} do')
        self.tsp.device.write(f'  smu.source.level = {pulse_voltage}')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write(f'  delay({pulse_width})')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  if i < {num_pulses} then')
        self.tsp.device.write(f'    delay({delay_between_pulses})')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        self.tsp.device.write('delay(0.000010)')
        
        # Read N times to observe relaxation
        self.tsp.device.write(f'for i = 1, {num_reads} do')
        self.tsp.device.write(f'  smu.source.level = {read_voltage}')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write(f'  if i < {num_reads} then')
        self.tsp.device.write(f'    delay({delay_between_reads})')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        print(f"  Executing on instrument...")
        
        # Calculate expected duration for proper timeout
        expected_duration = (
            0.001 +  # Initial read
            num_pulses * (pulse_width + delay_between_pulses) +  # All pulses
            num_reads * (delay_between_reads + 0.001) +  # All reads
            0.5  # Safety margin
        )
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        # Set longer timeout for long tests
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))  # 1.5x expected, min 30s
        
        # Clear any leftover data in the instrument's output buffer before starting
        self._flush_output_buffer()
        
        self.tsp.device.write('relaxWithPulseMeas()')
        
        # Wait for script to complete - waitcomplete() is non-blocking in this context
        # We need to wait the full expected duration
        print(f"  Waiting {expected_duration:.1f}s for instrument to complete...")
        time.sleep(expected_duration + 0.5)  # Wait full duration + safety margin
        
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)  # Small additional wait after waitcomplete
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        print("  Collecting buffer data...")
        try:
            # Timeout already set above for script execution, keep it for reading
            response = self.tsp.device.read().strip()
            
            # Parse triplets: timestamp, source voltage, current
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                n_measurements = len(parsed['timestamps'])
                print(f"  Retrieved {n_measurements} measurements")
                timestamps = parsed['timestamps']
                voltages = parsed['voltages']
                currents = parsed['currents']
                resistances = parsed['resistances']
            else:
                print(f"  ❌ Error parsing buffer data")
                
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        finally:
            # Restore original timeout
            self.tsp.device.timeout = original_timeout
        
        elapsed = time.time() - start_time
        print(f"✓ relaxation_after_multi_pulse_with_pulse_measurement complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def width_sweep_with_reads(self, pulse_voltage: float = 1.5,
                              pulse_widths: List[float] = [10e-6, 50e-6, 100e-6, 500e-6, 1e-3],
                              read_voltage: float = 0.2,
                              num_pulses_per_width: int = 5,
                              reset_voltage: float = -1.0,
                              reset_width: float = 1e-3,
                              delay_between_widths: float = 5.0,
                              clim: float = 100e-3) -> Dict:
        """Width sweep: For each width: Initial Read, (Pulse→Read)×N, Reset, next width.
        
        Pattern: Initial read, then pulse-read pairs (no double reads between pulses)
        Useful for: Finding optimal pulse timing, speed-dependent characterization
        Measures: Initial read + read after each pulse
        """
        # Validate parameters
        pulse_widths = self._validate_pulse_widths(pulse_widths)
        pulse_voltage = self._validate_voltage(pulse_voltage)
        read_voltage = self._validate_voltage(read_voltage)
        reset_voltage = self._validate_voltage(reset_voltage)
        reset_width = self._validate_pulse_width(reset_width)
        clim = self._validate_current_limit(clim)
        
        print(f"Starting width_sweep_with_reads:")
        print(f"  Testing {len(pulse_widths)} widths, {num_pulses_per_width} pulses each")
        print(f"  Widths: {[f'{w*1e6:.1f}µs' for w in pulse_widths]}")
        
        start_time = time.time()
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        pulse_widths_log = []
        
        v_range = max(abs(pulse_voltage), abs(read_voltage), abs(reset_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        for width_idx, width in enumerate(pulse_widths):
            print(f"\n  [{width_idx+1}/{len(pulse_widths)}] Testing width {width*1e6:.1f}µs")
            
            self.tsp.device.write(f'if widthSweep{width_idx} ~= nil then script.delete("widthSweep{width_idx}") end')
            time.sleep(0.01)
            
            measurements_per_width = num_pulses_per_width + 1  # Initial read + read after each pulse
            
            self.tsp.device.write(f'loadscript widthSweep{width_idx}')
            buffer_capacity = max(measurements_per_width, 10)
            self.tsp.device.write('defbuffer1.clear()')
            self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
            # Set measure function and range FIRST (per manual), then source settings
            self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
            self.tsp.device.write(f'smu.measure.range = {i_range}')
            self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
            self.tsp.device.write(f'smu.source.range = {v_range}')
            self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
            self.tsp.device.write('smu.measure.nplc = 0.01')
            self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
            self.tsp.device.write('smu.source.output = smu.ON')
            
            # Initial read before any pulses
            self.tsp.device.write(f'smu.source.level = {read_voltage}')
            self.tsp.device.write('smu.measure.read(defbuffer1)')
            self.tsp.device.write('smu.source.level = 0')
            self.tsp.device.write('delay(0.000010)')
            
            # Loop: Pulse → Read
            self.tsp.device.write(f'for i = 1, {num_pulses_per_width} do')
            # Main pulse (no measurement)
            self.tsp.device.write(f'  smu.source.level = {pulse_voltage}')
            self.tsp.device.write(f'  delay({width})')
            self.tsp.device.write('  smu.source.level = 0')
            self.tsp.device.write('  delay(0.000010)')
            # Read after pulse
            self.tsp.device.write(f'  smu.source.level = {read_voltage}')
            self.tsp.device.write('  smu.measure.read(defbuffer1)')
            self.tsp.device.write('  smu.source.level = 0')
            self.tsp.device.write(f'  if i < {num_pulses_per_width} then')
            self.tsp.device.write('    delay(0.001)')
            self.tsp.device.write('  end')
            self.tsp.device.write('end')
            
            self.tsp.device.write('smu.source.autorange = smu.ON')
            self.tsp.device.write('smu.measure.autorange = smu.ON')
            self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
            self.tsp.device.write('smu.source.output = smu.OFF')
            self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
            self.tsp.device.write('endscript')
            
            # Clear any leftover data in the instrument's output buffer before starting
            self._flush_output_buffer()
            
            self.tsp.device.write(f'widthSweep{width_idx}()')
            self.tsp.device.write('waitcomplete()')
            time.sleep(0.1)
            
            try:
                original_timeout = self.tsp.device.timeout
                self.tsp.device.timeout = 10000
                
                response = self.tsp.device.read().strip()
                self.tsp.device.timeout = original_timeout
                
                # Parse triplets: timestamp, source voltage, current
                parsed = self._parse_timestamped_buffer(response)
                if parsed:
                    print(f"    Retrieved {len(parsed['timestamps'])} measurements")
                    # Use actual timestamps and voltages from instrument
                    for idx in range(len(parsed['timestamps'])):
                        timestamps.append(parsed['timestamps'][idx])
                        voltages.append(parsed['voltages'][idx])
                        currents.append(parsed['currents'][idx])
                        resistances.append(parsed['resistances'][idx])
                        pulse_widths_log.append(width)
                else:
                    print(f"    ❌ Error parsing buffer data")
                    
            except Exception as e:
                print(f"    ❌ Error reading buffer: {e}")
            
            # Apply reset pulse between widths
            if width_idx < len(pulse_widths) - 1:
                print(f"    Applying reset pulse...")
                self.tsp.device.write('smu.source.output = smu.ON')
                self.tsp.device.write(f'smu.source.level = {reset_voltage}')
                self.tsp.device.write(f'delay({reset_width})')
                self.tsp.device.write('smu.source.level = 0')
                self.tsp.device.write('smu.source.output = smu.OFF')
                self.tsp.device.write('waitcomplete()')
                # Pause between width measurements to allow device relaxation
                print(f"    Waiting {delay_between_widths:.2f}s for device relaxation before next width block...")
                time.sleep(delay_between_widths)
        
        elapsed = time.time() - start_time
        print(f"\n✓ width_sweep_with_reads complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances, 
                                    pulse_widths=pulse_widths_log)
    
    def width_sweep_with_all_measurements(self, pulse_voltage: float = 1.5,
                                         pulse_widths: List[float] = [10e-6, 50e-6, 100e-6, 500e-6, 1e-3],
                                         read_voltage: float = 0.2,
                                         num_pulses_per_width: int = 5,
                                         reset_voltage: float = -1.0,
                                         reset_width: float = 1e-3,
                                         delay_between_widths: float = 1.0,
                                         clim: float = 100e-3) -> Dict:
        """Width sweep: For each width: Initial Read, (Pulse(measured)→Read)×N, Reset.
        
        Pattern: Initial read, then pulse-read pairs with pulse peak measurements
        Useful for: Full characterization including pulse peak current vs width
        Measures: Initial read + pulse peak + read after (for each pulse)
        """
        # Validate parameters
        pulse_widths = self._validate_pulse_widths(pulse_widths)
        pulse_voltage = self._validate_voltage(pulse_voltage)
        read_voltage = self._validate_voltage(read_voltage)
        reset_voltage = self._validate_voltage(reset_voltage)
        reset_width = self._validate_pulse_width(reset_width)
        clim = self._validate_current_limit(clim)
        
        print(f"Starting width_sweep_with_all_measurements:")
        print(f"  Testing {len(pulse_widths)} widths, {num_pulses_per_width} pulses each")
        print(f"  Widths: {[f'{w*1e6:.1f}µs' for w in pulse_widths]}")
        
        start_time = time.time()
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        pulse_widths_log = []
        
        v_range = max(abs(pulse_voltage), abs(read_voltage), abs(reset_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        for width_idx, width in enumerate(pulse_widths):
            print(f"\n  [{width_idx+1}/{len(pulse_widths)}] Testing width {width*1e6:.1f}µs")
            
            self.tsp.device.write(f'if widthSweepAll{width_idx} ~= nil then script.delete("widthSweepAll{width_idx}") end')
            time.sleep(0.01)
            
            measurements_per_width = 1 + (2 * num_pulses_per_width)  # Initial read + (pulse peak + read after) each pulse
            
            self.tsp.device.write(f'loadscript widthSweepAll{width_idx}')
            buffer_capacity = max(measurements_per_width, 10)
            self.tsp.device.write('defbuffer1.clear()')
            self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
            # Set measure function and range FIRST (per manual), then source settings
            self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
            self.tsp.device.write(f'smu.measure.range = {i_range}')
            self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
            self.tsp.device.write(f'smu.source.range = {v_range}')
            self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
            self.tsp.device.write('smu.measure.nplc = 0.01')
            self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
            self.tsp.device.write('smu.source.output = smu.ON')
            
            # Initial read before any pulses
            self.tsp.device.write(f'smu.source.level = {read_voltage}')
            self.tsp.device.write('smu.measure.read(defbuffer1)')
            self.tsp.device.write('smu.source.level = 0')
            self.tsp.device.write('delay(0.000010)')
            
            # Loop: Pulse (measured) → Read
            self.tsp.device.write(f'for i = 1, {num_pulses_per_width} do')
            # Main pulse WITH measurement at peak
            self.tsp.device.write(f'  smu.source.level = {pulse_voltage}')
            self.tsp.device.write('  smu.measure.read(defbuffer1)')
            self.tsp.device.write('  smu.source.level = 0')
            self.tsp.device.write('  delay(0.000010)')
            # Read after pulse
            self.tsp.device.write(f'  smu.source.level = {read_voltage}')
            self.tsp.device.write('  smu.measure.read(defbuffer1)')
            self.tsp.device.write('  smu.source.level = 0')
            self.tsp.device.write(f'  if i < {num_pulses_per_width} then')
            self.tsp.device.write('    delay(0.001)')
            self.tsp.device.write('  end')
            self.tsp.device.write('end')
            
            self.tsp.device.write('smu.source.autorange = smu.ON')
            self.tsp.device.write('smu.measure.autorange = smu.ON')
            self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
            self.tsp.device.write('smu.source.output = smu.OFF')
            self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
            self.tsp.device.write('endscript')
            
            # Clear any leftover data in the instrument's output buffer before starting
            self._flush_output_buffer()
            
            self.tsp.device.write(f'widthSweepAll{width_idx}()')
            self.tsp.device.write('waitcomplete()')
            time.sleep(0.1)
            
            try:
                original_timeout = self.tsp.device.timeout
                self.tsp.device.timeout = 10000
                
                response = self.tsp.device.read().strip()
                self.tsp.device.timeout = original_timeout
                
                # Parse triplets: timestamp, source voltage, current
                parsed = self._parse_timestamped_buffer(response)
                if parsed:
                    print(f"    Retrieved {len(parsed['timestamps'])} measurements")
                    # Use actual timestamps and voltages from instrument
                    for idx in range(len(parsed['timestamps'])):
                        timestamps.append(parsed['timestamps'][idx])
                        voltages.append(parsed['voltages'][idx])
                        currents.append(parsed['currents'][idx])
                        resistances.append(parsed['resistances'][idx])
                        pulse_widths_log.append(width)
                else:
                    print(f"    ❌ Error parsing buffer data")
                    
            except Exception as e:
                print(f"    ❌ Error reading buffer: {e}")
            
            # Apply reset pulse between widths
            if width_idx < len(pulse_widths) - 1:
                print(f"    Applying reset pulse...")
                self.tsp.device.write('smu.source.output = smu.ON')
                self.tsp.device.write(f'smu.source.level = {reset_voltage}')
                self.tsp.device.write(f'delay({reset_width})')
                self.tsp.device.write('smu.source.level = 0')
                self.tsp.device.write('smu.source.output = smu.OFF')
                self.tsp.device.write('waitcomplete()')
                # Pause between width measurements to allow device relaxation
                print(f"    Waiting {delay_between_widths:.2f}s for device relaxation before next width block...")
                time.sleep(delay_between_widths)
        
        elapsed = time.time() - start_time
        print(f"\n✓ width_sweep_with_all_measurements complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages, currents, resistances, 
                                    pulse_widths=pulse_widths_log)
    
    def voltage_amplitude_sweep(self, pulse_voltage_start: float = 0.5,
                               pulse_voltage_stop: float = 2.5,
                               pulse_voltage_step: float = 0.1,
                               pulse_width: float = 100e-6,
                               read_voltage: float = 0.2,
                               num_pulses_per_voltage: int = 5,
                               delay_between: float = 10e-3,
                               reset_voltage: float = -1.0,
                               reset_width: float = 1e-3,
                               delay_between_voltages: float = 1.0,
                               clim: float = 100e-3) -> Dict:
        """Voltage amplitude sweep: test different pulse voltages at fixed width. FAST buffer-based.
        
        Pattern: For each voltage: Initial Read → (Pulse → Read) × num_pulses → Reset
        """
        # Generate voltage list
        num_voltages = int((pulse_voltage_stop - pulse_voltage_start) / pulse_voltage_step) + 1
        pulse_voltages = [pulse_voltage_start + i * pulse_voltage_step for i in range(num_voltages)]
        pulse_voltages = [min(v, pulse_voltage_stop) for v in pulse_voltages]  # Ensure we don't exceed stop
        
        print(f"Starting FAST voltage amplitude sweep: {num_voltages} voltages from {pulse_voltage_start}V to {pulse_voltage_stop}V")
        print(f"  {num_pulses_per_voltage} pulses per voltage, {pulse_width*1000:.1f}ms width")
        
        start_time = time.time()
        total_measurements = num_voltages * (1 + num_pulses_per_voltage)  # Initial read + pulses per voltage
        
        self.tsp.device.write('if voltageAmplitudeSweep ~= nil then script.delete("voltageAmplitudeSweep") end')
        time.sleep(0.01)
        
        v_range = max(max(abs(v) for v in pulse_voltages), abs(reset_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript voltageAmplitudeSweep')
        buffer_capacity = max(total_measurements + 10, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        
        # Voltage list
        voltages_str = '{' + ','.join(str(v) for v in pulse_voltages) + '}'
        self.tsp.device.write(f'local voltages = {voltages_str}')
        self.tsp.device.write(f'local readV = {read_voltage}')
        self.tsp.device.write(f'local resetV = {reset_voltage}')
        self.tsp.device.write(f'local resetW = {reset_width}')
        self.tsp.device.write(f'local pulseW = {pulse_width}')
        self.tsp.device.write(f'local pulses_per_volt = {num_pulses_per_voltage}')
        self.tsp.device.write(f'local delay_between = {delay_between}')
        
        # Main loop: for each voltage
        self.tsp.device.write('for _, pulseV in ipairs(voltages) do')
        # Initial read before pulses at this voltage
        self.tsp.device.write('  smu.source.level = readV')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('  delay(0.000010)')
        # Pulses at this voltage
        self.tsp.device.write('  for pulse = 1, pulses_per_volt do')
        self.tsp.device.write('    smu.source.level = pulseV')
        self.tsp.device.write('    delay(pulseW)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    delay(0.000010)')
        self.tsp.device.write('    smu.source.level = readV')
        self.tsp.device.write('    smu.measure.read(defbuffer1)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    if pulse < pulses_per_volt then delay(delay_between) end')
        self.tsp.device.write('  end')
        # Reset between voltages (except last)
        self.tsp.device.write('  delay(0.000010)')
        self.tsp.device.write('  smu.source.level = resetV')
        self.tsp.device.write('  delay(resetW)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('  delay(0.000010)')
        self.tsp.device.write('end')
        
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration
        time_per_pulse = pulse_width + 0.00001 + 0.001 + delay_between
        time_per_voltage = 0.001 + (num_pulses_per_voltage * time_per_pulse) + reset_width + 0.00002
        expected_duration = num_voltages * time_per_voltage + delay_between_voltages * (num_voltages - 1) + 0.5
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))
        
        self._flush_output_buffer()
        
        self.tsp.device.write('voltageAmplitudeSweep()')
        time.sleep(expected_duration + delay_between_voltages * (num_voltages - 1) + 0.5)
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)
        
        timestamps = []
        voltages_list = []
        currents = []
        resistances = []
        pulse_voltages_log = []  # Track which pulse voltage was used
        
        print("  Collecting buffer data...")
        try:
            response = self.tsp.device.read().strip()
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                # Assign pulse voltages to each measurement
                measurements_per_voltage = 1 + num_pulses_per_voltage  # Initial read + pulses
                for idx in range(len(parsed['timestamps'])):
                    voltage_idx = idx // measurements_per_voltage
                    if voltage_idx < len(pulse_voltages):
                        pulse_voltages_log.append(pulse_voltages[voltage_idx])
                    else:
                        pulse_voltages_log.append(pulse_voltages[-1])  # Fallback
                return self._format_results(parsed['timestamps'], parsed['voltages'], 
                                          parsed['currents'], parsed['resistances'],
                                          pulse_voltages=pulse_voltages_log)
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ Voltage amplitude sweep complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages_list, currents, resistances,
                                   pulse_voltages=pulse_voltages_log)
    
    def ispp_test(self, start_voltage: float = 0.5,
                  voltage_step: float = 0.05,
                  max_voltage: float = 3.0,
                  pulse_width: float = 100e-6,
                  read_voltage: float = 0.2,
                  target_resistance: float = None,
                  resistance_threshold_factor: float = 0.5,
                  max_pulses: int = 100,
                  delay_between: float = 10e-3,
                  clim: float = 100e-3) -> Dict:
        """ISPP (Incremental Step Pulse Programming): Gradually increase voltage until switching. FAST buffer-based.
        
        Pattern: Start at low voltage, increase by step each pulse until target resistance reached or max voltage.
        """
        print(f"Starting FAST ISPP test: {start_voltage}V start, {voltage_step}V step, {max_voltage}V max")
        print(f"  Target: {target_resistance:.2e}Ω" if target_resistance else "  Target: No target (will run to max voltage)")
        
        start_time = time.time()
        total_measurements = max_pulses + 1  # Initial read + pulses
        
        self.tsp.device.write('if isppTest ~= nil then script.delete("isppTest") end')
        time.sleep(0.01)
        
        v_range = max(max_voltage, abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript isppTest')
        buffer_capacity = max(total_measurements + 10, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        
        # Initial read
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        
        # ISPP loop: increment voltage each pulse
        self.tsp.device.write(f'local startV = {start_voltage}')
        self.tsp.device.write(f'local stepV = {voltage_step}')
        self.tsp.device.write(f'local maxV = {max_voltage}')
        self.tsp.device.write(f'local readV = {read_voltage}')
        self.tsp.device.write(f'local pulseW = {pulse_width}')
        self.tsp.device.write(f'local delay_between = {delay_between}')
        self.tsp.device.write(f'local max_pulses = {max_pulses}')
        
        self.tsp.device.write('local currentV = startV')
        self.tsp.device.write('for pulse = 1, max_pulses do')
        self.tsp.device.write('  if currentV > maxV then break end')
        self.tsp.device.write('  smu.source.level = currentV')
        self.tsp.device.write('  delay(pulseW)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('  delay(0.000010)')
        self.tsp.device.write('  smu.source.level = readV')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('  currentV = currentV + stepV')
        self.tsp.device.write('  if pulse < max_pulses then delay(delay_between) end')
        self.tsp.device.write('end')
        
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration
        time_per_pulse = pulse_width + 0.00001 + 0.001 + delay_between
        expected_duration = 0.001 + max_pulses * time_per_pulse + 0.5
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))
        
        self._flush_output_buffer()
        
        self.tsp.device.write('isppTest()')
        time.sleep(expected_duration + 0.5)
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)
        
        timestamps = []
        voltages_list = []
        currents = []
        resistances = []
        pulse_voltages_log = []  # Track pulse voltage used
        
        print("  Collecting buffer data...")
        try:
            response = self.tsp.device.read().strip()
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                # Calculate pulse voltages used (incremental)
                for idx in range(len(parsed['timestamps'])):
                    if idx == 0:
                        pulse_voltages_log.append(0.0)  # Initial read
                    else:
                        pulse_num = idx - 1
                        pulse_volt = start_voltage + pulse_num * voltage_step
                        pulse_volt = min(pulse_volt, max_voltage)
                        pulse_voltages_log.append(pulse_volt)
                return self._format_results(parsed['timestamps'], parsed['voltages'],
                                          parsed['currents'], parsed['resistances'],
                                          pulse_voltages=pulse_voltages_log)
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ ISPP test complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages_list, currents, resistances,
                                   pulse_voltages=pulse_voltages_log)
    
    def switching_threshold_test(self, direction: str = "set",
                                start_voltage: float = 0.5,
                                voltage_step: float = 0.05,
                                max_voltage: float = 3.0,
                                pulse_width: float = 100e-6,
                                read_voltage: float = 0.2,
                                resistance_threshold_factor: float = 0.5,
                                num_pulses_per_voltage: int = 3,
                                delay_between: float = 10e-3,
                                clim: float = 100e-3) -> Dict:
        """Find minimum voltage to switch state (SET or RESET). FAST buffer-based.
        
        Pattern: Try increasing voltages, find the minimum that causes significant resistance change.
        """
        print(f"Starting FAST switching threshold test ({direction.upper()}): {start_voltage}V start, {voltage_step}V step, {max_voltage}V max")
        print(f"  {num_pulses_per_voltage} pulses per voltage to verify switching")
        
        start_time = time.time()
        num_voltages = int((max_voltage - start_voltage) / voltage_step) + 1
        total_measurements = num_voltages * (1 + num_pulses_per_voltage)  # Initial read + pulses per voltage
        
        self.tsp.device.write('if switchingThreshold ~= nil then script.delete("switchingThreshold") end')
        time.sleep(0.01)
        
        v_range = max(max_voltage, abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript switchingThreshold')
        buffer_capacity = max(total_measurements + 10, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        
        # Generate voltage list
        pulse_voltages = [start_voltage + i * voltage_step for i in range(num_voltages)]
        pulse_voltages = [min(v, max_voltage) for v in pulse_voltages]
        if direction.lower() == "reset":
            pulse_voltages = [-v for v in pulse_voltages]  # Negative for RESET
        
        voltages_str = '{' + ','.join(str(v) for v in pulse_voltages) + '}'
        self.tsp.device.write(f'local voltages = {voltages_str}')
        self.tsp.device.write(f'local readV = {read_voltage}')
        self.tsp.device.write(f'local pulseW = {pulse_width}')
        self.tsp.device.write(f'local pulses_per_volt = {num_pulses_per_voltage}')
        self.tsp.device.write(f'local delay_between = {delay_between}')
        
        # Main loop: for each voltage
        self.tsp.device.write('for _, pulseV in ipairs(voltages) do')
        # Initial read before pulses at this voltage
        self.tsp.device.write('  smu.source.level = readV')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('  delay(0.000010)')
        # Pulses at this voltage
        self.tsp.device.write('  for pulse = 1, pulses_per_volt do')
        self.tsp.device.write('    smu.source.level = pulseV')
        self.tsp.device.write('    delay(pulseW)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    delay(0.000010)')
        self.tsp.device.write('    smu.source.level = readV')
        self.tsp.device.write('    smu.measure.read(defbuffer1)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    if pulse < pulses_per_volt then delay(delay_between) end')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration
        time_per_pulse = pulse_width + 0.00001 + 0.001 + delay_between
        time_per_voltage = 0.001 + (num_pulses_per_voltage * time_per_pulse)
        expected_duration = num_voltages * time_per_voltage + 0.5
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))
        
        self._flush_output_buffer()
        
        self.tsp.device.write('switchingThreshold()')
        time.sleep(expected_duration + 0.5)
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)
        
        timestamps = []
        voltages_list = []
        currents = []
        resistances = []
        pulse_voltages_log = []
        
        print("  Collecting buffer data...")
        try:
            response = self.tsp.device.read().strip()
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                # Assign pulse voltages
                measurements_per_voltage = 1 + num_pulses_per_voltage
                for idx in range(len(parsed['timestamps'])):
                    voltage_idx = idx // measurements_per_voltage
                    if voltage_idx < len(pulse_voltages):
                        pulse_voltages_log.append(pulse_voltages[voltage_idx])
                    else:
                        pulse_voltages_log.append(pulse_voltages[-1])
                return self._format_results(parsed['timestamps'], parsed['voltages'],
                                          parsed['currents'], parsed['resistances'],
                                          pulse_voltages=pulse_voltages_log,
                                          direction=direction)
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ Switching threshold test complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages_list, currents, resistances,
                                   pulse_voltages=pulse_voltages_log,
                                   direction=direction)
    
    def multilevel_programming(self, target_levels: list = None,
                              pulse_voltage: float = 1.5,
                              pulse_width: float = 100e-6,
                              read_voltage: float = 0.2,
                              num_pulses_per_level: int = 5,
                              delay_between: float = 10e-3,
                              reset_voltage: float = -1.0,
                              reset_width: float = 1e-3,
                              delay_between_levels: float = 1.0,
                              clim: float = 100e-3) -> Dict:
        """Multilevel programming: Target specific resistance states. FAST buffer-based.
        
        Pattern: For each target level: Reset → Program with pulses until target reached → Read
        """
        if target_levels is None:
            target_levels = [1, 2, 3, 4, 5]  # Default: 5 levels
        
        print(f"Starting FAST multilevel programming: {len(target_levels)} target levels")
        print(f"  {num_pulses_per_level} pulses per level, {pulse_voltage}V pulse")
        
        start_time = time.time()
        total_measurements = len(target_levels) * (1 + num_pulses_per_level)  # Initial read + pulses per level
        
        self.tsp.device.write('if multilevelProgramming ~= nil then script.delete("multilevelProgramming") end')
        time.sleep(0.01)
        
        v_range = max(abs(pulse_voltage), abs(reset_voltage), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript multilevelProgramming')
        buffer_capacity = max(total_measurements + 10, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        
        # Target levels list
        levels_str = '{' + ','.join(str(l) for l in target_levels) + '}'
        self.tsp.device.write(f'local levels = {levels_str}')
        self.tsp.device.write(f'local readV = {read_voltage}')
        self.tsp.device.write(f'local resetV = {reset_voltage}')
        self.tsp.device.write(f'local resetW = {reset_width}')
        self.tsp.device.write(f'local pulseV = {pulse_voltage}')
        self.tsp.device.write(f'local pulseW = {pulse_width}')
        self.tsp.device.write(f'local pulses_per_level = {num_pulses_per_level}')
        self.tsp.device.write(f'local delay_between = {delay_between}')
        
        # Main loop: for each target level
        self.tsp.device.write('for _, level in ipairs(levels) do')
        # Reset before programming each level
        self.tsp.device.write('  smu.source.level = resetV')
        self.tsp.device.write('  delay(resetW)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('  delay(0.000010)')
        # Initial read after reset
        self.tsp.device.write('  smu.source.level = readV')
        self.tsp.device.write('  smu.measure.read(defbuffer1)')
        self.tsp.device.write('  smu.source.level = 0')
        self.tsp.device.write('  delay(0.000010)')
        # Program with pulses
        self.tsp.device.write('  for pulse = 1, pulses_per_level do')
        self.tsp.device.write('    smu.source.level = pulseV')
        self.tsp.device.write('    delay(pulseW)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    delay(0.000010)')
        self.tsp.device.write('    smu.source.level = readV')
        self.tsp.device.write('    smu.measure.read(defbuffer1)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    if pulse < pulses_per_level then delay(delay_between) end')
        self.tsp.device.write('  end')
        self.tsp.device.write('  delay(0.000010)')
        self.tsp.device.write('end')
        
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration
        time_per_pulse = pulse_width + 0.00001 + 0.001 + delay_between
        time_per_level = reset_width + 0.00002 + 0.001 + (num_pulses_per_level * time_per_pulse)
        expected_duration = len(target_levels) * time_per_level + delay_between_levels * (len(target_levels) - 1) + 0.5
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))
        
        self._flush_output_buffer()
        
        self.tsp.device.write('multilevelProgramming()')
        time.sleep(expected_duration + delay_between_levels * (len(target_levels) - 1) + 0.5)
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)
        
        timestamps = []
        voltages_list = []
        currents = []
        resistances = []
        target_levels_log = []
        
        print("  Collecting buffer data...")
        try:
            response = self.tsp.device.read().strip()
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                # Assign target levels
                measurements_per_level = 1 + num_pulses_per_level
                for idx in range(len(parsed['timestamps'])):
                    level_idx = idx // measurements_per_level
                    if level_idx < len(target_levels):
                        target_levels_log.append(target_levels[level_idx])
                    else:
                        target_levels_log.append(target_levels[-1])
                return self._format_results(parsed['timestamps'], parsed['voltages'],
                                          parsed['currents'], parsed['resistances'],
                                          target_levels=target_levels_log)
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ Multilevel programming complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages_list, currents, resistances,
                                   target_levels=target_levels_log)
    
    def pulse_train_varying_amplitudes(self, pulse_voltages: list = None,
                                      pulse_width: float = 100e-6,
                                      read_voltage: float = 0.2,
                                      num_repeats: int = 1,
                                      delay_between: float = 10e-3,
                                      clim: float = 100e-3) -> Dict:
        """Pulse train with varying amplitudes: Alternating or varying amplitude pulses. FAST buffer-based.
        
        Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × num_repeats
        """
        if pulse_voltages is None:
            pulse_voltages = [1.0, 1.5, 2.0, -1.0, -1.5, -2.0]  # Default: alternating pattern
        
        print(f"Starting FAST pulse train with varying amplitudes: {len(pulse_voltages)} different voltages × {num_repeats} repeats")
        
        start_time = time.time()
        total_measurements = 1 + (len(pulse_voltages) * num_repeats)  # Initial read + pulses
        
        self.tsp.device.write('if pulseTrainVarying ~= nil then script.delete("pulseTrainVarying") end')
        time.sleep(0.01)
        
        v_range = max(max(abs(v) for v in pulse_voltages), abs(read_voltage)) * 1.2
        v_range = max(v_range, 0.2)
        i_range = clim * 1.2
        
        self.tsp.device.write('loadscript pulseTrainVarying')
        buffer_capacity = max(total_measurements + 10, 10)
        self.tsp.device.write('defbuffer1.clear()')
        self.tsp.device.write(f'defbuffer1.capacity = {buffer_capacity}')
        self.tsp.device.write('smu.source.func = smu.FUNC_DC_VOLTAGE')
        self.tsp.device.write(f'smu.source.range = {v_range}')
        self.tsp.device.write(f'smu.source.ilimit.level = {clim}')
        self.tsp.device.write('smu.measure.func = smu.FUNC_DC_CURRENT')
        self.tsp.device.write(f'smu.measure.range = {i_range}')
        self.tsp.device.write('smu.measure.nplc = 0.01')
        self.tsp.device.write('smu.measure.autozero.enable = smu.OFF')
        self.tsp.device.write('smu.source.output = smu.ON')
        
        # Initial read
        self.tsp.device.write(f'smu.source.level = {read_voltage}')
        self.tsp.device.write('smu.measure.read(defbuffer1)')
        self.tsp.device.write('smu.source.level = 0')
        self.tsp.device.write('delay(0.000010)')
        
        # Pulse voltages list
        voltages_str = '{' + ','.join(str(v) for v in pulse_voltages) + '}'
        self.tsp.device.write(f'local voltages = {voltages_str}')
        self.tsp.device.write(f'local readV = {read_voltage}')
        self.tsp.device.write(f'local pulseW = {pulse_width}')
        self.tsp.device.write(f'local num_repeats = {num_repeats}')
        self.tsp.device.write(f'local delay_between = {delay_between}')
        
        # Main loop: repeat the voltage pattern
        self.tsp.device.write('for repeat = 1, num_repeats do')
        self.tsp.device.write('  for _, pulseV in ipairs(voltages) do')
        self.tsp.device.write('    smu.source.level = pulseV')
        self.tsp.device.write('    delay(pulseW)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    delay(0.000010)')
        self.tsp.device.write('    smu.source.level = readV')
        self.tsp.device.write('    smu.measure.read(defbuffer1)')
        self.tsp.device.write('    smu.source.level = 0')
        self.tsp.device.write('    delay(delay_between)')
        self.tsp.device.write('  end')
        self.tsp.device.write('end')
        
        self.tsp.device.write('smu.source.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autorange = smu.ON')
        self.tsp.device.write('smu.measure.autozero.enable = smu.ON')
        self.tsp.device.write('smu.source.output = smu.OFF')
        self.tsp.device.write('printbuffer(1, defbuffer1.n, defbuffer1.relativetimestamps, defbuffer1.sourcevalues, defbuffer1.readings)')
        self.tsp.device.write('endscript')
        
        # Calculate expected duration
        time_per_pulse = pulse_width + 0.00001 + 0.001 + delay_between
        expected_duration = 0.001 + num_repeats * len(pulse_voltages) * time_per_pulse + 0.5
        print(f"  Expected duration: {expected_duration:.2f}s")
        
        original_timeout = self.tsp.device.timeout
        self.tsp.device.timeout = max(30000, int(expected_duration * 1000 * 1.5))
        
        self._flush_output_buffer()
        
        self.tsp.device.write('pulseTrainVarying()')
        time.sleep(expected_duration + 0.5)
        self.tsp.device.write('waitcomplete()')
        time.sleep(0.1)
        
        timestamps = []
        voltages_list = []
        currents = []
        resistances = []
        pulse_voltages_log = []
        
        print("  Collecting buffer data...")
        try:
            response = self.tsp.device.read().strip()
            self.tsp.device.timeout = original_timeout
            
            parsed = self._parse_timestamped_buffer(response)
            if parsed:
                print(f"  Retrieved {len(parsed['timestamps'])} measurements")
                # Assign pulse voltages (repeated pattern)
                for idx in range(len(parsed['timestamps'])):
                    if idx == 0:
                        pulse_voltages_log.append(0.0)  # Initial read
                    else:
                        pulse_idx = (idx - 1) % len(pulse_voltages)
                        pulse_voltages_log.append(pulse_voltages[pulse_idx])
                return self._format_results(parsed['timestamps'], parsed['voltages'],
                                          parsed['currents'], parsed['resistances'],
                                          pulse_voltages=pulse_voltages_log)
        except Exception as e:
            print(f"  ❌ Error reading buffer: {e}")
        
        elapsed = time.time() - start_time
        print(f"✓ Pulse train with varying amplitudes complete in {elapsed:.2f}s")
        return self._format_results(timestamps, voltages_list, currents, resistances,
                                   pulse_voltages=pulse_voltages_log)


if __name__ == "__main__":
    
    DEVICE_ADDRESS = 'USB0::0x05E6::0x2450::04496615::INSTR'
    
    print("=" * 70)
    print("Keithley 2450 TSP Testing Scripts - Examples")
    print("=" * 70)
    
    try:
        print("\nConnecting to Keithley 2450...")
        tsp = Keithley2450_TSP(DEVICE_ADDRESS)
        print(f"Connected to: {tsp.get_idn()}")
        
        test = Keithley2450_TSP_Scripts(tsp)
        
        print("\n" + "=" * 70)
        print("Example 1: Pulse-Read-Repeat Test")
        print("=" * 70)
        
        results1 = test.pulse_read_repeat(
            pulse_voltage=1.5,
            pulse_width=100e-6,
            read_voltage=0.2,
            delay_between=0,
            num_cycles=100,
            clim=100e-3
        )
        
        print(f"\n{len(results1['timestamps'])} measurements")
        print(f"Initial R: {results1['resistances'][0]:.2e} Ω")
        print(f"Final R:   {results1['resistances'][-1]:.2e} Ω")
        
        time.sleep(2)

        print("\n" + "=" * 70)
        print("Example 2: Varying Width Pulses")
        print("=" * 70)
        
        results2 = test.varying_width_pulses(
            pulse_voltage=1.0,
            pulse_widths=[50e-6, 100e-6, 500e-6, 1e-3],
            pulses_per_width=3,
            read_voltage=0.2,
            clim=100e-3
        )
        
        print(f"\n{len(results2['timestamps'])} measurements")
        time.sleep(2)
        
        print("\n" + "=" * 70)
        print("Example 3: Potentiation-Depression Cycle")
        print("=" * 70)
        
        results3 = test.potentiation_depression_cycle(
            set_voltage=2.0,
            reset_voltage=-2.0,
            pulse_width=100e-6,
            read_voltage=0.2,
            steps=10,
            clim=100e-3
        )
        
        print(f"\n{len(results3['timestamps'])} measurements")
        print(f"Potentiation steps: {results3['phase'].count('potentiation')}")
        print(f"Depression steps:   {results3['phase'].count('depression')}")
        
        try:
            import matplotlib.pyplot as plt
            
            print("\n" + "=" * 70)
            print("Plotting Results")
            print("=" * 70)
            
            fig, axes = plt.subplots(3, 1, figsize=(10, 10))
            
            axes[0].plot(results1['timestamps'], results1['resistances'], 'o-')
            axes[0].set_xlabel('Time (s)')
            axes[0].set_ylabel('Resistance (Ω)')
            axes[0].set_title('Pulse-Read-Repeat')
            axes[0].grid(True)
            
            axes[1].scatter(results2['pulse_widths'], results2['resistances'], c=results2['timestamps'])
            axes[1].set_xlabel('Pulse Width (s)')
            axes[1].set_ylabel('Resistance (Ω)')
            axes[1].set_title('Varying Width Pulses')
            axes[1].set_xscale('log')
            axes[1].grid(True)
            
            pot_idx = [i for i, p in enumerate(results3['phase']) if p == 'potentiation']
            dep_idx = [i for i, p in enumerate(results3['phase']) if p == 'depression']
            
            axes[2].plot([results3['timestamps'][i] for i in pot_idx],
                        [results3['resistances'][i] for i in pot_idx],
                        'o-', label='Potentiation', color='green')
            axes[2].plot([results3['timestamps'][i] for i in dep_idx],
                        [results3['resistances'][i] for i in dep_idx],
                        'o-', label='Depression', color='red')
            axes[2].set_xlabel('Time (s)')
            axes[2].set_ylabel('Resistance (Ω)')
            axes[2].set_title('Potentiation-Depression')
            axes[2].legend()
            axes[2].grid(True)
            
            plt.tight_layout()
            plt.savefig('test_results.png', dpi=150)
            print("✓ Plots saved: test_results.png")
            
        except ImportError:
            print("\nmatplotlib not available, skipping plots")
        
        time.sleep(2)
        
        print("\n" + "=" * 70)
        print("Example 4: Relaxation After Multi-Pulse (reads only)")
        print("=" * 70)
        
        results4 = test.relaxation_after_multi_pulse(
            pulse_voltage=1.5,
            num_pulses=5,
            pulse_width=100e-6,
            delay_between_pulses=500e-6,
            read_voltage=0.2,
            num_reads=10,
            delay_between_reads=100e-6,
            clim=100e-3
        )
        
        print(f"\n{len(results4['timestamps'])} measurements")
        print(f"Data: 1 initial read + 5 pulses (not measured) + 10 relaxation reads")
        
        time.sleep(2)
        
        print("\n" + "=" * 70)
        print("Example 5: Relaxation With Pulse Measurement (all)")
        print("=" * 70)
        
        results5 = test.relaxation_with_pulse_measurement(
            pulse_voltage=1.5,
            num_pulses=5,
            pulse_width=100e-6,
            delay_between_pulses=500e-6,
            read_voltage=0.2,
            num_reads=10,
            delay_between_reads=100e-6,
            clim=100e-3
        )
        
        print(f"\n{len(results5['timestamps'])} measurements")
        print(f"Data: 1 initial read + 5 pulses (measured) + 10 relaxation reads")
        
        time.sleep(2)
        
        print("\n" + "=" * 70)
        print("Example 6: Width Sweep With Reads")
        print("=" * 70)
        
        results6 = test.width_sweep_with_reads(
            pulse_voltage=1.5,
            pulse_widths=[1e-3, 10e-3, 100e-3],
            read_voltage=0.2,
            num_pulses_per_width=5,
            reset_voltage=-1.0,
            reset_width=1e-3,
            clim=100e-3
        )
        
        print(f"\n{len(results6['timestamps'])} measurements")
        print(f"Data: 3 widths × 3 pulses × 2 reads (before+after) = 18 measurements")
        
        time.sleep(2)
        
        print("\n" + "=" * 70)
        print("Example 7: Width Sweep With All Measurements")
        print("=" * 70)
        
        results7 = test.width_sweep_with_all_measurements(
            pulse_voltage=1.5,
            pulse_widths=[10e-6, 50e-6, 100e-6],
            read_voltage=0.2,
            num_pulses_per_width=3,
            reset_voltage=-1.0,
            reset_width=1e-3,
            clim=100e-3
        )
        
        print(f"\n{len(results7['timestamps'])} measurements")
        print(f"Data: 3 widths × 3 pulses × 3 measurements (read+pulse+read) = 27 measurements")
        
        print("\n" + "=" * 70)
        print("Diagnostics & Cleanup")
        print("=" * 70)
        
        tsp.print_diagnostics()
        tsp.close()
        print("✓ Connection closed")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Complete")
    print("=" * 70)

