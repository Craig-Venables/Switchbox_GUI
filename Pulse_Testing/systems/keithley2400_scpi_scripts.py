"""
Keithley 2400 SCPI-based Pulse Testing Scripts
===============================================

SCPI command-based implementation of pulse testing patterns for Keithley 2400.
Uses direct SCPI commands for voltage-based pulsing (0V → pulse → 0V) without
toggling output on/off to avoid current spikes.

All results returned as: {'timestamps': [...], 'voltages': [...], 'currents': [...], 'resistances': [...]}
"""

import time
from typing import Dict, List, Any, Optional
from Equipment.SMU_AND_PMU.keithley2400.controller import Keithley2400Controller


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
    
    def _read(self, voltage: float, icc: float = 0.1) -> tuple[float, float, float]:
        """Perform a read measurement.
        
        Args:
            voltage: Read voltage (V)
            icc: Current limit (A)
        
        Returns:
            Tuple of (voltage, current, resistance)
        """
        self.controller.set_voltage(voltage, Icc=icc)
        time.sleep(0.01)  # Settle time for measurement
        
        v = self.controller.measure_voltage()
        i = self.controller.measure_current()
        
        if v is None or i is None:
            raise RuntimeError("Failed to read measurement")
        
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
                         clim: float = 100e-3) -> Dict[str, Any]:
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
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def pulse_then_read(self, pulse_voltage: float = 1.0,
                       pulse_width: float = 0.01,
                       delay_after_pulse: float = 0.01,
                       read_voltage: float = 0.2,
                       num_cycles: int = 10,
                       clim: float = 100e-3) -> Dict[str, Any]:
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
                             num_cycles: int = 10,
                             delay_between_cycles: float = 0.01,
                             clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: (Pulse×N → Read) × Cycles
        
        Args:
            pulse_voltage: Pulse voltage (V)
            num_pulses_per_read: Number of pulses before each read
            pulse_width: Pulse width (seconds)
            delay_between_pulses: Delay between pulses (seconds)
            read_voltage: Read voltage (V)
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
            
            # Read
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            
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
                            clim: float = 100e-3) -> Dict[str, Any]:
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
                              clim: float = 100e-3) -> Dict[str, Any]:
        """Width sweep: For each width: (Read→Pulse→Read)×N, Reset
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_widths: List of pulse widths to test (seconds)
            num_pulses_per_width: Number of pulses per width
            reset_voltage: Reset voltage (V), if None, uses -pulse_voltage
            read_voltage: Read voltage (V)
            clim: Current limit (A)
        
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
                self._pulse(reset_voltage, 0.01, icc=clim)
                time.sleep(0.01)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances,
                                   pulse_widths=pulse_widths_list)
    
    def width_sweep_with_all_measurements(self, pulse_voltage: float = 1.0,
                                         pulse_widths: Optional[List[float]] = None,
                                         num_pulses_per_width: int = 5,
                                         reset_voltage: Optional[float] = None,
                                         read_voltage: float = 0.2,
                                         clim: float = 100e-3) -> Dict[str, Any]:
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
                
                # Measure during pulse
                v_pulse = self.controller.measure_voltage()
                i_pulse = self.controller.measure_current()
                if v_pulse is None or i_pulse is None:
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
                self._pulse(reset_voltage, 0.01, icc=clim)
                time.sleep(0.01)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances,
                                   pulse_widths=pulse_widths_list)
    
    def potentiation_depression_cycle(self, set_voltage: float = 1.5,
                                     reset_voltage: float = -1.5,
                                     read_voltage: float = 0.2,
                                     num_steps: int = 10,
                                     pulse_width: float = 0.01,
                                     clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: Initial Read → Gradual SET → Gradual RESET
        
        Args:
            set_voltage: SET pulse voltage (V)
            reset_voltage: RESET pulse voltage (V)
            read_voltage: Read voltage (V)
            num_steps: Number of steps in each direction
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary with phase field
        """
        print(f"Starting potentiation_depression_cycle: {num_steps} steps each direction")
        
        v_range = max(abs(set_voltage), abs(reset_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        timestamps = []
        voltages = []
        currents = []
        resistances = []
        phases = []
        
        start_time = time.time()
        
        # Initial read
        v, i, r = self._read(read_voltage, icc=clim)
        timestamps.append(0.0)
        voltages.append(v)
        currents.append(i)
        resistances.append(r)
        phases.append("INITIAL")
        
        # Potentiation (SET) - gradual increase
        for step in range(1, num_steps + 1):
            pulse_v = set_voltage * (step / num_steps)
            self._pulse(pulse_v, pulse_width, icc=clim)
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            phases.append("POTENTIATION")
        
        # Depression (RESET) - gradual decrease
        for step in range(num_steps, 0, -1):
            pulse_v = reset_voltage * (step / num_steps)
            self._pulse(pulse_v, pulse_width, icc=clim)
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
            phases.append("DEPRESSION")
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances,
                                   phase=phases)
    
    def potentiation_only(self, set_voltage: float = 1.5,
                         pulse_width: float = 0.01,
                         read_voltage: float = 0.2,
                         num_pulses: int = 10,
                         clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated SET pulses with reads
        
        Args:
            set_voltage: SET pulse voltage (V)
            pulse_width: Pulse width (seconds)
            read_voltage: Read voltage (V)
            num_pulses: Number of pulses
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting potentiation_only: {num_pulses} pulses")
        
        v_range = max(abs(set_voltage), abs(read_voltage)) * 1.2
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
        
        # Repeated SET pulses
        for _ in range(num_pulses):
            self._pulse(set_voltage, pulse_width, icc=clim)
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def depression_only(self, reset_voltage: float = -1.5,
                       pulse_width: float = 0.01,
                       read_voltage: float = 0.2,
                       num_pulses: int = 10,
                       clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: Initial Read → Repeated RESET pulses with reads
        
        Args:
            reset_voltage: RESET pulse voltage (V)
            pulse_width: Pulse width (seconds)
            read_voltage: Read voltage (V)
            num_pulses: Number of pulses
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        print(f"Starting depression_only: {num_pulses} pulses")
        
        v_range = max(abs(reset_voltage), abs(read_voltage)) * 1.2
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
        
        # Repeated RESET pulses
        for _ in range(num_pulses):
            self._pulse(reset_voltage, pulse_width, icc=clim)
            v, i, r = self._read(read_voltage, icc=clim)
            t = time.time() - start_time
            timestamps.append(t)
            voltages.append(v)
            currents.append(i)
            resistances.append(r)
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)
    
    def endurance_test(self, set_voltage: float = 1.5,
                     reset_voltage: float = -1.5,
                     read_voltage: float = 0.2,
                     num_cycles: int = 100,
                     pulse_width: float = 0.01,
                     clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: (SET → Read → RESET → Read) × N cycles
        
        Args:
            set_voltage: SET pulse voltage (V)
            reset_voltage: RESET pulse voltage (V)
            read_voltage: Read voltage (V)
            num_cycles: Number of cycles
            pulse_width: Pulse width (seconds)
            clim: Current limit (A)
        
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
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances,
                                   cycle_number=cycle_numbers, operation=operations)
    
    def retention_test(self, pulse_voltage: float = 1.5,
                      read_voltage: float = 0.2,
                      read_intervals: Optional[List[float]] = None,
                      total_time: Optional[float] = None,
                      pulse_width: float = 0.01,
                      clim: float = 100e-3) -> Dict[str, Any]:
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
                        num_reads: int = 10,
                        delay_between_reads: float = 0.01,
                        clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: N pulses then many reads
        
        Args:
            pulse_voltage: Pulse voltage (V)
            pulse_width: Pulse width (seconds)
            read_voltage: Read voltage (V)
            num_pulses: Number of pulses before reads
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
        for _ in range(num_pulses):
            self._pulse(pulse_voltage, pulse_width, icc=clim)
        
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
                       clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: Just reads, no pulses
        
        Args:
            read_voltage: Read voltage (V)
            num_reads: Number of reads
            delay_between_reads: Delay between reads (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
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
    
    def current_range_finder(self, read_voltage: float = 0.2,
                            test_voltage: float = 1.0,
                            test_pulse_width: float = 0.01,
                            clim: float = 100e-3) -> Dict[str, Any]:
        """Find optimal current measurement range
        
        Args:
            read_voltage: Read voltage (V)
            test_voltage: Test pulse voltage (V)
            test_pulse_width: Test pulse width (seconds)
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary with range_values, range_stats, recommended_range
        """
        print("Starting current_range_finder")
        
        v_range = max(abs(test_voltage), abs(read_voltage)) * 1.2
        v_range = max(min(v_range, 200.0), 0.2)
        self.controller.prepare_for_pulses(Icc=clim, v_range=v_range)
        
        # Test with a pulse and read
        self._pulse(test_voltage, test_pulse_width, icc=clim)
        v, i, r = self._read(read_voltage, icc=clim)
        
        # Determine recommended range based on measured current
        abs_i = abs(i)
        if abs_i < 1e-9:
            recommended = 1e-9
        elif abs_i < 1e-6:
            recommended = 1e-6
        elif abs_i < 1e-3:
            recommended = 1e-3
        else:
            recommended = 1.0
        
        self.controller.set_voltage(0.0, Icc=clim)
        
        return self._format_results(
            timestamps=[0.0],
            voltages=[v],
            currents=[i],
            resistances=[r],
            range_values=[recommended],
            range_stats=[{"measured_current": i, "recommended_range": recommended}],
            recommended_range=recommended
        )
    
    def relaxation_after_multi_pulse(self, pulse_voltage: float = 1.5,
                                     num_pulses: int = 10,
                                     read_voltage: float = 0.2,
                                     num_reads: int = 20,
                                     delay_between_reads: float = 0.01,
                                     pulse_width: float = 0.01,
                                     clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: 1×Read → N×Pulse → N×Read (measure reads only)
        
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
        for _ in range(num_pulses):
            self._pulse(pulse_voltage, pulse_width, icc=clim)
        
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
            
            # Measure during pulse
            v_pulse = self.controller.measure_voltage()
            i_pulse = self.controller.measure_current()
            if v_pulse is None or i_pulse is None:
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
                               clim: float = 100e-3) -> Dict[str, Any]:
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
                               clim: float = 100e-3) -> Dict[str, Any]:
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
                                       num_cycles: int = 5,
                                       clim: float = 100e-3) -> Dict[str, Any]:
        """Pattern: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N
        
        Args:
            pulse_voltages: List of pulse voltages in sequence (V)
            read_voltage: Read voltage (V)
            pulse_width: Pulse width (seconds)
            num_cycles: Number of cycles
            clim: Current limit (A)
        
        Returns:
            Standardized data dictionary
        """
        if pulse_voltages is None:
            pulse_voltages = [0.5, 1.0, 1.5, 2.0]
        
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
        
        self.controller.set_voltage(0.0, Icc=clim)
        return self._format_results(timestamps, voltages, currents, resistances)












