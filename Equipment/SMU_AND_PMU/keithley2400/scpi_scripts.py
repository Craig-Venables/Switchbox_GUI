"""
Keithley 2400 SCPI-based Pulse Testing Scripts
===============================================

Script location: Equipment/SMU_AND_PMU/keithley2400/scpi_scripts.py (this file).
Controller: Equipment/SMU_AND_PMU/keithley2400/controller.py.
Pulse Testing adapter: Pulse_Testing/systems/keithley2400.py (imports this module).

SCPI command-based implementation of pulse testing patterns for Keithley 2400.
Uses direct SCPI commands for voltage-based pulsing (0V → pulse → 0V) without
toggling output on/off to avoid current spikes.

All results returned as: {'timestamps': [...], 'voltages': [...], 'currents': [...], 'resistances': [...]}
"""

import time
from typing import Dict, List, Any, Optional
from .controller import Keithley2400Controller


class Keithley2400_SCPI_Scripts:
    """SCPI-based testing scripts for Keithley 2400."""
    
    def __init__(self, controller: Keithley2400Controller):
        """Initialize with a Keithley2400Controller instance.
        
        Args:
            controller: Keithley2400Controller instance (already connected)
        """
        self.controller = controller
        if not controller or not controller.device:
            raise ValueError("Controller must be connected and have a device")
    
    def _check_error(self) -> Optional[str]:
        """Check for SCPI errors and return error message if any."""
        try:
            error = self.controller.check_errors()
            if error and "0," not in error:  # "0," means no error
                return error
        except Exception:
            pass
        return None
    
    def _pulse(self, voltage: float, width: float, icc: float = 0.1) -> None:
        """Execute a single pulse: 0V → voltage → 0V.
        
        Args:
            voltage: Pulse voltage (V)
            width: Pulse width (seconds)
            icc: Current limit (A)
        """
        # Set to 0V first (if not already)
        self.controller.set_voltage(0.0, Icc=icc)
        time.sleep(0.001)  # Small settle time
        
        # Set to pulse voltage
        self.controller.set_voltage(voltage, Icc=icc)
        time.sleep(width)  # Hold pulse width
        
        # Return to 0V
        self.controller.set_voltage(0.0, Icc=icc)
        time.sleep(0.001)  # Small settle time
    
    def _measure_v_i(self) -> tuple[float, float]:
        """Perform a voltage and current measurement using explicit SCPI commands.
        
        Returns:
            Tuple of (voltage, current)
        
        Raises:
            RuntimeError: If measurement fails
        """
        device = self.controller.device
        if not device:
            raise RuntimeError("Device not connected")
        
        try:
            # Ensure we're measuring current (when sourcing voltage)
            device.write(":SENS:FUNC 'CURR'")
            # Trigger a measurement and read both voltage and current
            # :READ? returns: voltage,current,resistance,time,status
            result = device.ask(":READ?")
            
            # Parse the result - format is typically: "voltage,current,resistance,time,status"
            parts = result.strip().split(',')
            if len(parts) >= 2:
                v = float(parts[0])
                i = float(parts[1])
                return (v, i)
            else:
                raise ValueError(f"Unexpected :READ? response format: {result}")
        except Exception as e:
            # Fallback to PyMeasure properties if SCPI fails
            v = self.controller.measure_voltage()
            i = self.controller.measure_current()
            if v is None or i is None:
                raise RuntimeError(f"Failed to read measurement: {e}")
            # Handle case where PyMeasure returns lists instead of single values
            if isinstance(v, (list, tuple)):
                v = float(v[0]) if len(v) > 0 else 0.0
            else:
                v = float(v)
            if isinstance(i, (list, tuple)):
                i = float(i[0]) if len(i) > 0 else 0.0
            else:
                i = float(i)
            return (v, i)
    
    def _read(self, voltage: float, icc: float = 0.1) -> tuple[float, float, float]:
        """Perform a read measurement.
        
        Args:
            voltage: Read voltage (V)
            icc: Current limit (A)
        
        Returns:
            Tuple of (voltage, current, resistance)
        """
        self.controller.set_voltage(voltage, Icc=icc)
        time.sleep(0.01)  # Settle time for measurement (10ms for GPIB)
        
        # Use explicit SCPI measurement
        v, i = self._measure_v_i()
        
        r = v / i if abs(i) > 1e-12 else 1e12
        return (v, i, r)
    
    def _format_results(self, timestamps: List[float], voltages: List[float],
                       currents: List[float], resistances: List[float],
                       **extras) -> Dict[str, Any]:
        """Format results into standardized dictionary."""
        result = {
            'timestamps': timestamps,
            'voltages': voltages,
            'currents': currents,
            'resistances': resistances
        }
        result.update(extras)
        return result
    
    # ============================================================================
    # Test Methods - All must return standardized format
    # ============================================================================
    
    def pulse_read_repeat(self, pulse_voltage: float = 1.0,
                         pulse_width: float = 0.01,  # 10ms minimum for GPIB
                         read_voltage: float = 0.2,
                         delay_between: float = 0.01,
                         num_cycles: int = 10,
                         clim: float = 100e-3,
                         **kwargs) -> Dict[str, Any]:
        """Pattern: Initial Read → (Pulse → Read → Delay) × N
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (seconds) - minimum ~10ms for GPIB
            read_voltage: Read voltage (V)
            delay_between: Delay between cycles (seconds)
            num_cycles: Number of cycles
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting pulse_read_repeat: {num_cycles} cycles, {pulse_voltage}V pulse, {read_voltage}V read")
        
        # Prepare for pulses
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)  # Clamp to valid ranges
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        # Initial read
        v, i, r = self._read(read_voltage, icc=clim)
        timestamps.append(0.0)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        
        # Pulse-read cycles
        for cycle in range(num_cycles):
            cycle_start = time.time()
            
            # Pulse
            self._pulse(pulse_voltage, pulse_width, icc=clim)
            
            # Read
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            
            # Delay between cycles (except after last)
            if cycle < num_cycles - 1:
                time.sleep(delay_between)
        
        # Return to 0V
        self.controller.set_voltage(0.0, Icc=clim)
        
        print(f"✓ pulse_read_repeat complete: {len(timestamps)} measurements")
        print(f"timestamps: {timestamps}")
        print(f"voltages: {voltages}")
        print(f"currents: {currents}")
        print(f"resistances: {resistances}")
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def pulse_then_read(self, pulse_voltage: float = 1.0,
                       pulse_width: float = 0.01,
                       delay_after_pulse: float = 0.01,
                       read_voltage: float = 0.2,
                       num_cycles: int = 10,
                       clim: float = 100e-3,
                       **kwargs) -> Dict[str, Any]:
        """Pattern: (Pulse → Delay → Read) × N
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (seconds)
            delay_after_pulse: Delay after pulse before read (seconds)
            read_voltage: Read voltage (V)
            num_cycles: Number of cycles
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting pulse_then_read: {num_cycles} cycles")
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        for cycle in range(num_cycles):
            # Pulse
            self._pulse(pulse_voltage, pulse_width, icc=clim)
            
            # Delay after pulse
            time.sleep(delay_after_pulse)
            
            # Read
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def multi_pulse_then_read(self, pulse_voltage: float = 1.0,
                             num_pulses_per_read: int = 5,
                             pulse_width: float = 0.01,
                             delay_between_pulses: float = 0.01,
                             read_voltage: float = 0.2,
                             num_reads: int = 1,
                             delay_between_reads: float = 0.01,
                             num_cycles: int = 10,
                             delay_between_cycles: float = 0.01,
                             clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: (Pulse×N → Read×M) × Cycles
        
        Args:
            pulse_voltage: Pulse voltage (V)
            num_pulses_per_read: Number of pulses before each read
            pulse_width: Pulse width (seconds)
            delay_between_pulses: Delay between pulses (seconds)
            read_voltage: Read voltage (V)
            num_reads: Reads after each pulse group
            delay_between_reads: Delay between those reads (seconds)
            num_cycles: Number of cycles
            delay_between_cycles: Delay between cycles (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting multi_pulse_then_read: {num_cycles} cycles, {num_pulses_per_read} pulses per read")
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        for cycle in range(num_cycles):
            # Multiple pulses
            for _ in range(num_pulses_per_read):
                self._pulse(pulse_voltage, pulse_width, icc=clim)
                if delay_between_pulses > 0:
                    time.sleep(delay_between_pulses)
            
            for read_idx in range(max(1, int(num_reads))):
                v, i, r = self._read(read_voltage, icc=clim)
                t = time.time() - start_time
                timestamps.append(t)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                if read_idx < num_reads - 1 and delay_between_reads > 0:
                    time.sleep(delay_between_reads)
            
            # Delay between cycles
            if cycle < num_cycles - 1:
                time.sleep(delay_between_cycles)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def varying_width_pulses(self, pulse_voltage: float = 1.0,
                            pulse_widths: Optional[List[float]] = None,
                            pulses_per_width: int = 5,
                            read_voltage: float = 0.2,
                            delay_between: float = 0.01,
                            clim: float = 100e-3,
                            **kwargs) -> Dict[str, Any]:
        """Test multiple pulse widths
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_widths: List of pulse widths to test (seconds)
            pulses_per_width: Number of pulses per width
            read_voltage: Read voltage (V)
            delay_between: Delay between operations (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary with pulse_widths field
        """
        if pulse_widths is None:
            pulse_widths = [0.01, 0.02, 0.05, 0.1, 0.2]
        
        print(f"Starting varying_width_pulses: {len(pulse_widths)} widths, {pulses_per_width} pulses each")
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        pulse_widths_list = []
        
        start_time = time.time()
        
        # Initial read
        v, i, r = self._read(read_voltage, icc=clim)
        timestamps.append(0.0)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        pulse_widths_list.append(0.0)
        
        for width in pulse_widths:
            for _ in range(pulses_per_width):
                # Pulse
                self._pulse(pulse_voltage, width, icc=clim)
                
                # Read
                v, i, r = self._read(read_voltage, icc=clim)
                t = time.time() - start_time
                timestamps.append(t)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                pulse_widths_list.append(width)
                
                if delay_between > 0:
                    time.sleep(delay_between)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances,
                                   pulse_widths=pulse_widths_list)
    
    def width_sweep_with_reads(self, pulse_voltage: float = 1.0,
                              pulse_widths: Optional[List[float]] = None,
                              num_pulses_per_width: int = 5,
                              reset_voltage: Optional[float] = None,
                              read_voltage: float = 0.2,
                              clim: float = 100e-3,
                              reset_width: float = 0.01,
                              delay_between_widths: float = 0.0) -> Dict[str, Any]:
        """Width sweep: For each width: (Read→Pulse→Read)×N, Reset
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_widths: List of pulse widths to test (seconds)
            num_pulses_per_width: Number of pulses per width
            reset_voltage: Reset voltage (V), if None, uses -pulse_voltage
            read_voltage: Read voltage (V)
            clim: Current limit (A)
            reset_width: Reset pulse width (seconds)
            delay_between_widths: Relaxation delay between width blocks (seconds)
        
        Returns:
            Standardized data dictionary with pulse_widths field
        """
        if pulse_widths is None:
            pulse_widths = [0.01, 0.02, 0.05, 0.1, 0.2]
        if reset_voltage is None:
            reset_voltage = -pulse_voltage
        
        print(f"Starting width_sweep_with_reads: {len(pulse_widths)} widths")
        
        v_range = max(abs(pulse_voltage), abs(read_voltage), abs(reset_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        pulse_widths_list = []
        
        start_time = time.time()
        
        for width in pulse_widths:
            for pulse_num in range(num_pulses_per_width):
                # Read before pulse
                v, i, r = self._read(read_voltage, icc=clim)
                t = time.time() - start_time
                timestamps.append(t)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                pulse_widths_list.append(width)
                
                # Pulse
                self._pulse(pulse_voltage, width, icc=clim)
                
                # Read after pulse
                v, i, r = self._read(read_voltage, icc=clim)
                t = time.time() - start_time
                timestamps.append(t)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                pulse_widths_list.append(width)
            
            # Reset after all pulses at this width
            if reset_voltage != 0:
                self._pulse(reset_voltage, reset_width, icc=clim)
                time.sleep(0.01)
            if width != pulse_widths[-1] and delay_between_widths > 0:
                time.sleep(delay_between_widths)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances,
                                   pulse_widths=pulse_widths_list)
    
    def width_sweep_with_all_measurements(self, pulse_voltage: float = 1.0,
                                         pulse_widths: Optional[List[float]] = None,
                                         num_pulses_per_width: int = 5,
                                         reset_voltage: Optional[float] = None,
                                         read_voltage: float = 0.2,
                                         clim: float = 100e-3,
                                         delay_between_widths: float = 0.01,
                                         reset_width: float = 0.01) -> Dict[str, Any]:
        """Width sweep with pulse peak measurements
        
        Similar to width_sweep_with_reads but also measures during pulses.
        For GPIB-limited 2400, we measure immediately after pulse starts.
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_widths: List of pulse widths to test (seconds)
            num_pulses_per_width: Number of pulses per width
            reset_voltage: Reset voltage (V), if None, uses -pulse_voltage
            read_voltage: Read voltage (V)
            clim: Current limit (A)
            delay_between_widths: Delay between different width tests (seconds)
            reset_width: Reset pulse width (seconds)
        
        Returns:
            Standardized data dictionary with pulse_widths field
        """
        if pulse_widths is None:
            pulse_widths = [0.01, 0.02, 0.05, 0.1, 0.2]
        if reset_voltage is None:
            reset_voltage = -pulse_voltage
        
        print(f"Starting width_sweep_with_all_measurements: {len(pulse_widths)} widths")
        
        v_range = max(abs(pulse_voltage), abs(read_voltage), abs(reset_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        pulse_widths_list = []
        
        start_time = time.time()
        
        for width in pulse_widths:
            for pulse_num in range(num_pulses_per_width):
                # Read before pulse
                v, i, r = self._read(read_voltage, icc=clim)
                t = time.time() - start_time
                timestamps.append(t)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                pulse_widths_list.append(width)
                
                # Pulse with measurement during pulse
                self.controller.set_voltage(0.0, Icc=clim)
                time.sleep(0.001)
                self.controller.set_voltage(pulse_voltage, Icc=clim)
                time.sleep(0.005)  # Small delay then measure
                
                # Measure during pulse using explicit SCPI measurement
                try:
                    v_pulse, i_pulse = self._measure_v_i()
                except Exception:
                    # Fallback if measurement fails
                    v_pulse, i_pulse = pulse_voltage, 0.0
                r_pulse = v_pulse / i_pulse if abs(i_pulse) > 1e-12 else 1e12
                t = time.time() - start_time
                timestamps.append(t)
                voltages.append(v_pulse)
                currents.append(i_pulse)
                resistances.append(r_pulse)
                pulse_widths_list.append(width)
                
                # Complete pulse width
                remaining_width = width - 0.005
                if remaining_width > 0:
                    time.sleep(remaining_width)
                
                self.controller.set_voltage(0.0, Icc=clim)
                time.sleep(0.001)
                
                # Read after pulse
                v, i, r = self._read(read_voltage, icc=clim)
                t = time.time() - start_time
                timestamps.append(t)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                pulse_widths_list.append(width)
            
            # Reset
            if reset_voltage != 0:
                self._pulse(reset_voltage, reset_width, icc=clim)
                time.sleep(0.01)
            
            # Delay between widths (except after last)
            if width != pulse_widths[-1] and delay_between_widths > 0:
                time.sleep(delay_between_widths)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances,
                                   pulse_widths=pulse_widths_list)
    
    def potentiation_depression_cycle(self, set_voltage: float = 1.5,
                                     reset_voltage: float = -1.5,
                                     read_voltage: float = 0.2,
                                     steps: int = 10,
                                     pulse_width: float = 0.01,
                                     clim: float = 100e-3,
                                     num_cycles: int = 1,
                                     delay_between_pulses: float = 0.01,
                                     delay_before_read: float = 0.0,
                                     delay_between_cycles: float = 0.0,
                                     num_steps: Optional[int] = None) -> Dict[str, Any]:
        """Pattern: Initial Read → (Gradual SET → Gradual RESET) × num_cycles
        
        Args:
            set_voltage: SET pulse voltage (V)
            reset_voltage: RESET pulse voltage (V)
            read_voltage: Read voltage (V)
            steps: Number of steps in each direction (``num_steps`` is the legacy name)
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
            num_cycles: Number of potentiation+depression cycles
            delay_between_pulses: Delay between pulses (seconds)
            delay_before_read: Delay after each pulse before its read (seconds)
            delay_between_cycles: Delay between cycles (seconds)
        
        Returns:
            Standardized data dictionary with phase field
        """
        if num_steps is not None:
            steps = num_steps
        steps = max(1, int(steps))
        print(f"Starting potentiation_depression_cycle: {num_cycles} cycle(s), {steps} steps each direction")
        
        v_range = max(abs(set_voltage), abs(reset_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        phases = []
        
        start_time = time.time()

        def _pulse_and_read(pulse_v: float, phase: str) -> None:
            self._pulse(pulse_v, pulse_width, icc=clim)
            if delay_before_read > 0:
                time.sleep(delay_before_read)
            v, i, r = self._read(read_voltage, icc=clim)
            timestamps.append(time.time() - start_time)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            phases.append(phase)
            if delay_between_pulses > 0:
                time.sleep(delay_between_pulses)
        
        # Initial read
        v, i, r = self._read(read_voltage, icc=clim)
        timestamps.append(0.0)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        phases.append("INITIAL")
        
        for cycle in range(max(1, int(num_cycles))):
            # Potentiation (SET) - gradual increase
            for step in range(1, steps + 1):
                _pulse_and_read(set_voltage * (step / steps), "POTENTIATION")
            # Depression (RESET) - gradual decrease
            for step in range(steps, 0, -1):
                _pulse_and_read(reset_voltage * (step / steps), "DEPRESSION")
            if cycle < num_cycles - 1 and delay_between_cycles > 0:
                time.sleep(delay_between_cycles)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances,
                                   phase=phases)
    
    def _repeated_pulse_reads(self, label: str, pulse_voltage: float, pulse_width: float,
                              read_voltage: float, num_pulses: int,
                              delay_between_pulses: float, delay_before_read: float,
                              num_post_reads: int, post_read_interval: float,
                              clim: float) -> Dict[str, Any]:
        """Initial Read → (Pulse → [delay] → Read) × N → optional post-pulse reads."""
        print(f"Starting {label}: {num_pulses} pulses, {num_post_reads} post-reads")

        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)

        timestamps: List[float] = []
        voltages: List[float] = []
        currents: List[float] = []
        resistances: List[float] = []
        phases: List[str] = []
        start_time = time.time()

        def _record(phase: str, t: Optional[float] = None) -> None:
            v, i, r = self._read(read_voltage, icc=clim)
            timestamps.append(time.time() - start_time if t is None else t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            phases.append(phase)

        _record("initial", 0.0)
        for n in range(num_pulses):
            self._pulse(pulse_voltage, pulse_width, icc=clim)
            if delay_before_read > 0:
                time.sleep(delay_before_read)
            _record("pulse")
            if n < num_pulses - 1 and delay_between_pulses > 0:
                time.sleep(delay_between_pulses)
        for _ in range(max(0, int(num_post_reads))):
            if post_read_interval > 0:
                time.sleep(post_read_interval)
            _record("post_read")

        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances, phase=phases)

    def potentiation_only(self, set_voltage: float = 1.5,
                         pulse_width: float = 0.01,
                         read_voltage: float = 0.2,
                         num_pulses: int = 10,
                         delay_between_pulses: float = 0.0,
                         delay_before_read: float = 0.0,
                         num_post_reads: int = 0,
                         post_read_interval: float = 0.001,
                         delay_between_cycles: float = 0.0,
                         clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated SET pulses with reads → optional post-pulse reads.

        All times in seconds. ``delay_between_cycles`` is accepted for GUI parity (single run).
        """
        return self._repeated_pulse_reads(
            "potentiation_only", set_voltage, pulse_width, read_voltage, num_pulses,
            delay_between_pulses, delay_before_read, num_post_reads, post_read_interval, clim,
        )

    def depression_only(self, reset_voltage: float = -1.5,
                       pulse_width: float = 0.01,
                       read_voltage: float = 0.2,
                       num_pulses: int = 10,
                       delay_between_pulses: float = 0.0,
                       delay_before_read: float = 0.0,
                       num_post_reads: int = 0,
                       post_read_interval: float = 0.001,
                       delay_between_cycles: float = 0.0,
                       clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated RESET pulses with reads → optional post-pulse reads.

        All times in seconds. ``delay_between_cycles`` is accepted for GUI parity (single run).
        """
        return self._repeated_pulse_reads(
            "depression_only", reset_voltage, pulse_width, read_voltage, num_pulses,
            delay_between_pulses, delay_before_read, num_post_reads, post_read_interval, clim,
        )
    
    def endurance_test(self, set_voltage: float = 1.5,
                     reset_voltage: float = -1.5,
                     read_voltage: float = 0.2,
                     num_cycles: int = 100,
                     pulse_width: float = 0.01,
                     clim: float = 100e-3,
                     delay_between: float = 0.0) -> Dict[str, Any]:
        """Pattern: (SET → Read → RESET → Read) × N cycles
        
        Args:
            set_voltage: SET pulse voltage (V)
            reset_voltage: RESET pulse voltage (V)
            read_voltage: Read voltage (V)
            num_cycles: Number of cycles
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
            delay_between: Delay between cycles (seconds)
        
        Returns:
            Standardized data dictionary with cycle_number and operation fields
        """
        print(f"Starting endurance_test: {num_cycles} cycles")
        
        v_range = max(abs(set_voltage), abs(reset_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        cycle_numbers = []
        operations = []
        
        start_time = time.time()
        
        for cycle in range(num_cycles):
            # SET
            self._pulse(set_voltage, pulse_width, icc=clim)
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            cycle_numbers.append(cycle + 1)
            operations.append("SET")
            
            # RESET
            self._pulse(reset_voltage, pulse_width, icc=clim)
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            cycle_numbers.append(cycle + 1)
            operations.append("RESET")
            if cycle < num_cycles - 1 and delay_between > 0:
                time.sleep(delay_between)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances,
                                   cycle_number=cycle_numbers, operation=operations)
    
    def retention_test(self, pulse_voltage: float = 1.5,
                      read_voltage: float = 0.2,
                      read_intervals: Optional[List[float]] = None,
                      total_time: Optional[float] = None,
                      pulse_width: float = 0.01,
                      clim: float = 100e-3,
                      **kwargs) -> Dict[str, Any]:
        """Pattern: Pulse → Read @ t1 → Read @ t2 → Read @ t3...
        
        Args:
            pulse_voltage: Pulse voltage (V)
            read_voltage: Read voltage (V)
            read_intervals: List of time intervals after pulse for reads (seconds)
            total_time: Total time for test (seconds), if read_intervals not provided
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        if read_intervals is None:
            if total_time is None:
                total_time = 60.0
            # Default: reads at 1s, 10s, 30s, 60s, etc.
            read_intervals = [1.0, 10.0, 30.0, 60.0]
            if total_time > 60:
                read_intervals.extend([120.0, 300.0, 600.0])
        
        print(f"Starting retention_test: {len(read_intervals)} read intervals")
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        pulse_time = time.time()
        
        # Initial pulse
        self._pulse(pulse_voltage, pulse_width, icc=clim)
        
        # Reads at specified intervals
        for interval in read_intervals:
            # Wait until interval
            elapsed = time.time() - pulse_time
            wait_time = interval - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
            
            # Read
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def pulse_multi_read(self, pulse_voltage: float = 1.5,
                        pulse_width: float = 0.01,
                        read_voltage: float = 0.2,
                        num_pulses: int = 5,
                        delay_between_pulses: float = 0.0,
                        num_reads: int = 10,
                        delay_between_reads: float = 0.01,
                        clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: N pulses then many reads
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (seconds)
            read_voltage: Read voltage (V)
            num_pulses: Number of pulses before reads
            delay_between_pulses: Delay between pulses (seconds)
            num_reads: Number of reads after pulses
            delay_between_reads: Delay between reads (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting pulse_multi_read: {num_pulses} pulses, {num_reads} reads")
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        # Multiple pulses
        for n in range(num_pulses):
            self._pulse(pulse_voltage, pulse_width, icc=clim)
            if n < num_pulses - 1 and delay_between_pulses > 0:
                time.sleep(delay_between_pulses)
        
        # Multiple reads
        for _ in range(num_reads):
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            if delay_between_reads > 0:
                time.sleep(delay_between_reads)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def multi_read_only(self, read_voltage: float = 0.2,
                       num_reads: int = 100,
                       delay_between_reads: float = 0.01,
                       clim: float = 100e-3,
                       delay_between: Optional[float] = None) -> Dict[str, Any]:
        """Pattern: Just reads, no pulses
        
        Args:
            read_voltage: Read voltage (V)
            num_reads: Number of reads
            delay_between_reads: Delay between reads (seconds)
            clim: Current limit (A)
            delay_between: GUI name for delay_between_reads (seconds); overrides it when given
        
        Returns:
            Standardized data dictionary
        """
        if delay_between is not None:
            delay_between_reads = delay_between
        print(f"Starting multi_read_only: {num_reads} reads")
        
        v_range = max(abs(read_voltage), 0.2) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        for _ in range(num_reads):
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            if delay_between_reads > 0:
                time.sleep(delay_between_reads)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def current_range_finder(self, test_voltage: float = 0.2,
                            num_reads_per_range: int = 10,
                            delay_between_reads: float = 10e-3,
                            current_ranges: Optional[List[float]] = None) -> Dict[str, Any]:
        """For each current range: read N times at test_voltage; recommend the most stable range.

        Same parameters and result keys as the 2450 version (range_values, range_stats,
        recommended_range). Each range is also used as the compliance limit.
        """
        if current_ranges is None:
            current_ranges = [1e-3, 100e-6, 10e-6, 1e-6]
        print(f"Starting current_range_finder: {len(current_ranges)} ranges at {test_voltage}V")

        timestamps: List[float] = []
        voltages: List[float] = []
        currents: List[float] = []
        resistances: List[float] = []
        range_values: List[float] = []
        range_stats: List[Dict[str, Any]] = []
        start_time = time.time()
        v_range = max(min(abs(test_voltage) * 1.2, 200.0), 0.2)

        for clim in current_ranges:
            clim = float(clim)
            self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
            self.controller.set_current_measurement_range(clim)
            readings: List[float] = []
            for n in range(max(1, int(num_reads_per_range))):
                v, i, r = self._read(test_voltage, icc=clim)
                timestamps.append(time.time() - start_time)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                range_values.append(clim)
                readings.append(i)
                if n < num_reads_per_range - 1 and delay_between_reads > 0:
                    time.sleep(delay_between_reads)
            self.controller.set_voltage(0.0, Icc=clim)

            mean_i = sum(readings) / len(readings)
            std_i = (sum((x - mean_i) ** 2 for x in readings) / len(readings)) ** 0.5
            range_stats.append({
                'range_limit': clim,
                'mean_current': mean_i,
                'std_current': std_i,
                'min_current': min(readings),
                'max_current': max(readings),
                'mean_resistance': test_voltage / mean_i if abs(mean_i) > 1e-12 else 1e12,
                'has_negative': any(x < 0 for x in readings),
                'cv_percent': (std_i / abs(mean_i) * 100) if abs(mean_i) > 1e-12 else 999,
            })

        self.controller.set_current_measurement_range(0.0)
        candidates = [s for s in range_stats if not s['has_negative'] and abs(s['mean_current']) > 1e-9]
        best = min(candidates, key=lambda s: s['cv_percent']) if candidates else None
        return self._format_results(
            timestamps, voltages, currents, resistances,
            range_values=range_values,
            range_stats=range_stats,
            recommended_range=best['range_limit'] if best else None,
        )
    
    def relaxation_after_multi_pulse(self, pulse_voltage: float = 1.5,
                                     num_pulses: int = 10,
                                     read_voltage: float = 0.2,
                                     num_reads: int = 20,
                                     delay_between_reads: float = 0.01,
                                     pulse_width: float = 0.01,
                                     clim: float = 100e-3,
                                     delay_between_pulses: float = 0.0) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse → N×Read (measure reads only)
        
        Args:
            pulse_voltage: Pulse voltage (V)
            num_pulses: Number of pulses
            read_voltage: Read voltage (V)
            num_reads: Number of reads after pulses
            delay_between_reads: Delay between reads (seconds)
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
            delay_between_pulses: Delay between pulses (seconds)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting relaxation_after_multi_pulse: {num_pulses} pulses, {num_reads} reads")
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        # Initial read
        v, i, r = self._read(read_voltage, icc=clim)
        timestamps.append(0.0)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        
        # Multiple pulses
        for n in range(num_pulses):
            self._pulse(pulse_voltage, pulse_width, icc=clim)
            if n < num_pulses - 1 and delay_between_pulses > 0:
                time.sleep(delay_between_pulses)
        
        # Multiple reads
        for _ in range(num_reads):
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            if delay_between_reads > 0:
                time.sleep(delay_between_reads)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def relaxation_after_multi_pulse_with_pulse_measurement(self, pulse_voltage: float = 1.5,
                                                            num_pulses: int = 10,
                                                            read_voltage: float = 0.2,
                                                            num_reads: int = 20,
                                                            delay_between_reads: float = 0.01,
                                                            pulse_width: float = 0.01,
                                                            delay_between_pulses: float = 0.0,
                                                            clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse(measured) → N×Read
        
        Args:
            pulse_voltage: Pulse voltage (V)
            num_pulses: Number of pulses
            read_voltage: Read voltage (V)
            num_reads: Number of reads after pulses
            delay_between_reads: Delay between reads (seconds)
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting relaxation_after_multi_pulse_with_pulse_measurement: {num_pulses} pulses, {num_reads} reads")
        
        v_range = max(abs(pulse_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        # Initial read
        v, i, r = self._read(read_voltage, icc=clim)
        timestamps.append(0.0)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        
        # Multiple pulses with measurement
        for _ in range(num_pulses):
            # Start pulse
            self.controller.set_voltage(0.0, Icc=clim)
            time.sleep(0.001)
            self.controller.set_voltage(pulse_voltage, Icc=clim)
            time.sleep(0.005)  # Small delay then measure
            
            # Measure during pulse using explicit SCPI measurement
            try:
                v_pulse, i_pulse = self._measure_v_i()
            except Exception:
                # Fallback if measurement fails
                v_pulse, i_pulse = pulse_voltage, 0.0
            r_pulse = v_pulse / i_pulse if abs(i_pulse) > 1e-12 else 1e12
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v_pulse)
            currents.append(i_pulse)
            resistances.append(r_pulse)
            
            # Complete pulse
            remaining_width = pulse_width - 0.005
            if remaining_width > 0:
                time.sleep(remaining_width)
            self.controller.set_voltage(0.0, Icc=clim)
            time.sleep(0.001)
            if delay_between_pulses > 0:
                time.sleep(delay_between_pulses)
        
        # Multiple reads
        for _ in range(num_reads):
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            if delay_between_reads > 0:
                time.sleep(delay_between_reads)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def voltage_amplitude_sweep(self, pulse_voltages: Optional[List[float]] = None,
                               read_voltage: float = 0.2,
                               num_pulses_per_voltage: int = 5,
                               reset_voltage: Optional[float] = None,
                               pulse_width: float = 0.01,
                               clim: float = 100e-3,
                               **kwargs) -> Dict[str, Any]:
        """Pattern: For each voltage: Initial Read → (Pulse → Read) × N → Reset
        
        Args:
            pulse_voltages: List of pulse voltages to test (V)
            read_voltage: Read voltage (V)
            num_pulses_per_voltage: Number of pulses per voltage
            reset_voltage: Reset voltage (V), if None, uses -max(pulse_voltages)
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        if pulse_voltages is None:
            pulse_voltages = [0.5, 1.0, 1.5, 2.0, 2.5]
        if reset_voltage is None:
            reset_voltage = -max(abs(v) for v in pulse_voltages)
        
        print(f"Starting voltage_amplitude_sweep: {len(pulse_voltages)} voltages")
        
        v_range = max(max(abs(v) for v in pulse_voltages), abs(read_voltage), abs(reset_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        for pulse_v in pulse_voltages:
            # Initial read
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            
            # Multiple pulses at this voltage
            for _ in range(num_pulses_per_voltage):
                self._pulse(pulse_v, pulse_width, icc=clim)
                v, i, r = self._read(read_voltage, icc=clim)
                t = time.time() - start_time
                timestamps.append(t)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
            
            # Reset
            if reset_voltage != 0:
                self._pulse(reset_voltage, 0.01, icc=clim)
                time.sleep(0.01)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def ispp_test(self, start_voltage: float = 0.5,
                 voltage_step: float = 0.1,
                 max_voltage: float = 2.5,
                 read_voltage: float = 0.2,
                 pulse_width: float = 0.01,
                 clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: Start at low voltage, increase by step each pulse
        
        Args:
            start_voltage: Starting pulse voltage (V)
            voltage_step: Voltage increment per pulse (V)
            max_voltage: Maximum pulse voltage (V)
            read_voltage: Read voltage (V)
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting ispp_test: {start_voltage}V to {max_voltage}V, step {voltage_step}V")
        
        v_range = max(abs(max_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        # Initial read
        v, i, r = self._read(read_voltage, icc=clim)
        timestamps.append(0.0)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        
        # Incremental step pulse programming
        current_voltage = start_voltage
        while current_voltage <= max_voltage:
            self._pulse(current_voltage, pulse_width, icc=clim)
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            current_voltage += voltage_step
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def switching_threshold_test(self, start_voltage: float = 0.5,
                               voltage_step: float = 0.1,
                               max_voltage: float = 3.0,
                               read_voltage: float = 0.2,
                               pulse_width: float = 0.01,
                               threshold_current: float = 1e-6,
                               clim: float = 100e-3,
                               **kwargs) -> Dict[str, Any]:
        """Pattern: Try increasing voltages, find minimum that causes switching
        
        Args:
            start_voltage: Starting pulse voltage (V)
            voltage_step: Voltage increment per pulse (V)
            max_voltage: Maximum pulse voltage (V)
            read_voltage: Read voltage (V)
            pulse_width: Pulse width (seconds)
            threshold_current: Current threshold to detect switching (A)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting switching_threshold_test: {start_voltage}V to {max_voltage}V")
        
        v_range = max(abs(max_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        # Initial read
        v, i, r = self._read(read_voltage, icc=clim)
        timestamps.append(0.0)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        
        # Try increasing voltages
        current_voltage = start_voltage
        switching_detected = False
        while current_voltage <= max_voltage and not switching_detected:
            self._pulse(current_voltage, pulse_width, icc=clim)
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            
            # Check if switching occurred (large current change)
            if abs(i) > threshold_current:
                switching_detected = True
                print(f"Switching detected at {current_voltage}V")
            
            current_voltage += voltage_step
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def multilevel_programming(self, levels: Optional[List[float]] = None,
                              reset_voltage: float = -1.5,
                              read_voltage: float = 0.2,
                              pulses_per_level: int = 5,
                              pulse_width: float = 0.01,
                              clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: For each level: Reset → Program with pulses → Read
        
        Args:
            levels: List of programming voltage levels (V)
            reset_voltage: Reset voltage (V)
            read_voltage: Read voltage (V)
            pulses_per_level: Number of pulses per level
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        if levels is None:
            levels = [0.5, 1.0, 1.5, 2.0]
        
        print(f"Starting multilevel_programming: {len(levels)} levels")
        
        v_range = max(max(abs(v) for v in levels), abs(reset_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        for level in levels:
            # Reset
            self._pulse(reset_voltage, 0.01, icc=clim)
            time.sleep(0.01)
            
            # Program with pulses
            for _ in range(pulses_per_level):
                self._pulse(level, pulse_width, icc=clim)
            
            # Read
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def pulse_train_varying_amplitudes(self, pulse_voltages: Optional[List[float]] = None,
                                       read_voltage: float = 0.2,
                                       pulse_width: float = 0.01,
                                       num_repeats: int = 5,
                                       delay_between: float = 0.0,
                                       clim: float = 100e-3,
                                       num_cycles: Optional[int] = None) -> Dict[str, Any]:
        """Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N
        
        Args:
            pulse_voltages: List of pulse voltages in sequence (V)
            read_voltage: Read voltage (V)
            pulse_width: Pulse width (seconds)
            num_repeats: Number of times the whole train repeats (``num_cycles`` is the legacy name)
            delay_between: Delay after each pulse+read slot (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        if pulse_voltages is None:
            pulse_voltages = [0.5, 1.0, 1.5, 2.0]
        num_cycles = int(num_cycles if num_cycles is not None else num_repeats)
        
        print(f"Starting pulse_train_varying_amplitudes: {len(pulse_voltages)} pulses per cycle, {num_cycles} cycles")
        
        v_range = max(max(abs(v) for v in pulse_voltages), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        
        start_time = time.time()
        
        # Initial read
        v, i, r = self._read(read_voltage, icc=clim)
        timestamps.append(0.0)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        
        # Cycles
        for cycle in range(num_cycles):
            for pulse_v in pulse_voltages:
                # Pulse
                self._pulse(pulse_v, pulse_width, icc=clim)
                
                # Read
                v, i, r = self._read(read_voltage, icc=clim)
                t = time.time() - start_time
                timestamps.append(t)
                voltages.append(v)
                currents.append(i)
                resistances.append(r)
                if delay_between > 0:
                    time.sleep(delay_between)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)













