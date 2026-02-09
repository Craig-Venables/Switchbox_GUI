"""
Pulse diagram – preview of pulse pattern for selected test.
PulseDiagramHelper draws the pattern on a matplotlib axes. Main builds params and calls draw().
"""

import numpy as np
from Pulse_Testing.pulse_pattern_visualizer import PulsePatternVisualizer


class PulseDiagramHelper:
    def __init__(self, diagram_ax, diagram_fig):
        self.ax = diagram_ax
        self.fig = diagram_fig
        self._system_name = None

    def draw(self, test_name, params, system_name=None):
        self._system_name = system_name
        self.ax.clear()
        for ax in self.fig.get_axes():
            if ax != self.ax:
                try:
                    self.fig.delaxes(ax)
                except Exception:
                    pass
        if "Pulse-Read-Repeat" in test_name:
            self._draw_pulse_read_repeat(params)
        elif "Multi-Pulse-Then-Read" in test_name:
            self._draw_multi_pulse_then_read(params)
        elif "Width Sweep" in test_name:
            self._draw_width_sweep(params, "Full" in test_name)
        elif "Potentiation-Depression" in test_name:
            self._draw_pot_dep_cycle(params)
        elif "Potentiation Only" in test_name:
            self._draw_potentiation_only(params)
        elif "Depression Only" in test_name:
            self._draw_depression_only(params)
        elif "Endurance" in test_name:
            self._draw_endurance(params)
        elif test_name == "⚠️ SMU Retention":
            self._draw_smu_retention(params)
        elif "Pulse-Multi-Read" in test_name:
            self._draw_pulse_multi_read(params)
        elif "Multi-Read Only" in test_name:
            self._draw_multi_read_only(params)
        elif "Relaxation" in test_name:
            self._draw_relaxation(params, "Pulse Measurement" in test_name)
        elif "Voltage Amplitude Sweep" in test_name:
            self._draw_voltage_sweep(params)
        elif "ISPP" in test_name:
            self._draw_ispp(params)
        elif "Switching Threshold" in test_name:
            self._draw_threshold(params)
        elif "Multilevel Programming" in test_name:
            self._draw_multilevel(params)
        elif "Optical Read (Pulsed Light)" in test_name:
            self._draw_optical_read_pulsed_light(params)
        elif "Optical: Laser Pattern + Continuous Read" in test_name:
            self._draw_optical_laser_pattern_read(params)
        elif "Optical Pulse Train + Read" in test_name:
            self._draw_optical_pulse_train_read(params)
        elif "Electrical Pulse Train" in test_name or "Pulse Train" in test_name:
            self._draw_pulse_train(params)
        elif "Laser and Read" in test_name:
            self._draw_laser_and_read(params)
        else:
            self._draw_generic_pattern()
        self._add_limit_warnings(params)

    
    def _draw_pulse_read_repeat(self, params):
        """Draw: Initial Read → (Pulse → Read → Delay) × N"""
        t = 0
        times, voltages = [], []
        read_times = []  # Track read measurement times
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        cycles = min(params.get('num_cycles', 100), 5)  # Show max 5 cycles
        
        # Use proper read width - params are already in seconds from update_pulse_diagram
        is_4200a = self._system_name in ('keithley4200a',)
        if is_4200a:
            # For 4200A, use read_width parameter if provided (already converted to seconds)
            read_width = params.get('read_width', 0.5e-6)  # Default 0.5 µs = 0.5e-6s
            read_rise = params.get('read_rise_time', 0.1e-6)  # Default 0.1 µs = 0.1e-6s
            read_delay_after = params.get('read_delay', 1.0e-6)  # Default 1.0 µs = 1.0e-6s
        else:
            # For 2450, use ms-based defaults (already in seconds)
            read_width = params.get('read_width', 1e-3)  # Default 1ms = 1e-3s
            read_rise = params.get('read_rise_time', 0.1e-3)  # Default 0.1ms = 0.1e-3s
            read_delay_after = params.get('read_delay', 0.1e-3)  # Default 0.1ms = 0.1e-3s
        
        # Initial read before any pulses
        read_start = t + read_rise  # Rise time to read voltage
        read_end = read_start + read_width
        read_center = (read_start + read_end) / 2
        read_times.append(read_center)
        # Draw read pulse: 0 → rise → read_width → fall → 0
        times.extend([t, t, read_start, read_start, read_end, read_end, read_end + read_rise, read_end + read_rise])
        voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, 0])
        t = read_end + read_rise + read_delay_after  # After read completes
        
        for i in range(cycles):
            # Pulse
            pulse_start = t
            pulse_end = pulse_start + p_w
            times.extend([pulse_start, pulse_start, pulse_end, pulse_end])
            voltages.extend([0, p_v, p_v, 0])
            t = pulse_end + delay * 0.1  # Small gap after pulse
            
            # Read after pulse
            read_start = t + read_rise  # Rise time to read voltage
            read_end = read_start + read_width
            read_center = (read_start + read_end) / 2
            read_times.append(read_center)
            # Draw read pulse: 0 → rise → read_width → fall → 0
            times.extend([t, t, read_start, read_start, read_end, read_end, read_end + read_rise, read_end + read_rise])
            voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, 0])
            t = read_end + read_rise + delay  # Delay before next cycle
        
        # Convert to ms for display
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'b-', linewidth=2, label='Voltage')
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='blue')
        
        # Mark read points with visible markers
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'ro', markersize=8, markeredgewidth=2, 
                               markerfacecolor='red', markeredgecolor='darkred', 
                               label='Read' if rt == read_times[0] else '')
        
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'Pattern: Initial Read → (Pulse→Read)×{cycles}', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [r_v, p_v, 0])
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0, not -0.1
    
    def _draw_multi_pulse_then_read(self, params):
        """Draw: Initial Read → (Pulse×N → Read×M) × Cycles"""
        t = 0
        times, voltages = [], []
        read_times = []
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        n_pulses = min(params.get('num_pulses_per_read', 10), 5)
        n_reads = min(params.get('num_reads', 1), 5)
        cycles = min(params.get('num_cycles', 20), 2)
        
        # Check if 4200A (use realistic timing) or 2450 (use ms-based timing)
        is_4200a = self._system_name in ('keithley4200a',)
        if is_4200a:
            # For 4200A: use realistic timing matching C code
            # Initial read: riseTime + measWidth + setFallTime + riseTime + measDelay
            # Get parameters (already in seconds for 4200A from get_test_parameters)
            read_rise = params.get('read_rise_time', 0.1e-6)  # Default 0.1µs = 0.1e-6s
            read_width = params.get('read_width', 0.5e-6)  # Default 0.5µs = 0.5e-6s
            set_fall_time = 1e-7  # Default fall delay
            # Use a small delay after initial read (not delay_between_reads, which is for between reads in a cycle)
            delay_after_initial_read = 1e-6  # 1µs delay after initial read before cycles start
            
            # Initial read pulse
            read_start = t + read_rise
            read_end = read_start + read_width
            read_center = (read_start + read_end) / 2
            read_times.append(read_center)
            # Draw: 0 → rise → width → fall_delay → fall → delay
            times.extend([t, t, read_start, read_start, read_end, read_end, read_end + set_fall_time, 
                         read_end + set_fall_time, read_end + set_fall_time + read_rise, 
                         read_end + set_fall_time + read_rise, read_end + set_fall_time + read_rise + delay_after_initial_read,
                         read_end + set_fall_time + read_rise + delay_after_initial_read])
            voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, r_v, r_v, 0, 0, 0])
            t = read_end + set_fall_time + read_rise + delay_after_initial_read
        else:
            # For 2450: use ms-based timing (simplified)
            read_t = t + p_w*0.15
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.3 + 0.0001
        
        for cycle in range(cycles):
            # Multiple pulses
            for i in range(n_pulses):
                times.extend([t, t, t+p_w, t+p_w])
                voltages.extend([0, p_v, p_v, 0])
                t += p_w + params.get('delay_between_pulses', 1e-3)
            # Multiple reads
            for i in range(n_reads):
                read_t = t + p_w*0.25
                read_times.append(read_t)
                times.extend([t, t, t+p_w*0.5, t+p_w*0.5])
                voltages.extend([0, r_v, r_v, 0])
                t += p_w*0.5 + (params.get('delay_between_reads', 10e-3) if i < n_reads-1 else params.get('delay_between_cycles', 10e-3))
        
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'purple', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='purple')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'Pattern: Initial Read → {n_pulses}×Pulse→{n_reads}×Read ×{cycles}', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [r_v, p_v, 0])
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0
    
    def _draw_width_sweep(self, params, with_pulse_measurement=False):
        """Draw width sweep pattern"""
        t = 0
        times, voltages = [], []
        read_times = []
        pulse_read_times = []  # Read at pulse peak
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        widths = params.get('pulse_widths', [1e-3, 5e-3, 10e-3])[:3]
        
        for width in widths:
            # Read before
            read_t = t + width*0.15
            read_times.append(read_t)
            times.extend([t, t, t+width*0.3, t+width*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += width*0.3 + 0.0001
            # Pulse at this width
            pulse_start_t = t
            times.extend([t, t, t+width, t+width])
            voltages.extend([0, p_v, p_v, 0])
            if with_pulse_measurement:
                pulse_read_times.append(pulse_start_t + width*0.5)  # Peak read
            t += width + 0.0001
            # Read after
            read_t = t + width*0.15
            read_times.append(read_t)
            times.extend([t, t, t+width*0.3, t+width*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += width*0.3 + width*2
        
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'orange', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='orange')
        # Regular reads
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        # Pulse-peak reads (if Full version)
        for pt in pulse_read_times:
            self.ax.plot(pt*1e3, p_v, 'rx', markersize=10, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        title = f'Width Sweep (Full): {len(widths)} widths' if with_pulse_measurement else f'Width Sweep: {len(widths)} widths'
        self.ax.set_title(title, fontsize=10)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [r_v, p_v, 0])
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0
    
    def _draw_pot_dep_cycle(self, params):
        """Draw potentiation-depression cycle with initial read, repeated for multiple cycles"""
        t = 0
        times, voltages, colors = [], [], []
        read_times = []
        set_v = params.get('set_voltage', 2.0)
        reset_v = params.get('reset_voltage', -2.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        steps = params.get('steps', 20)  # Show all steps, not limited to 5
        num_cycles = min(params.get('num_cycles', 1), 3)  # Show max 3 cycles in diagram
        
        # Get timing parameters (already in seconds from update_pulse_diagram)
        is_4200a = self._system_name in ('keithley4200a',)
        if is_4200a:
            read_width = params.get('read_width', 0.5e-6)  # Already in seconds
            read_rise = params.get('read_rise_time', 0.1e-6) if 'read_rise_time' in params else 0.1e-6
        else:
            read_width = params.get('read_width', 1e-3) if 'read_width' in params else 1e-3
            read_rise = 0.1e-3
        delay_before_read = params.get('delay_before_read', 10e-6)  # Already in seconds
        delay_between_pulses = params.get('delay_between_pulses', 10e-3)
        delay_between_cycles = params.get('delay_between_cycles', 10e-3)
        
        # Initial read before any pulses
        read_start = t + delay_before_read + read_rise
        read_end = read_start + read_width
        read_center = (read_start + read_end) / 2
        read_times.append(read_center)
        times.extend([t, t, read_start, read_start, read_end, read_end, read_end + read_rise, read_end + read_rise])
        voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, 0])
        t = read_end + read_rise
        
        # Loop through cycles
        for cycle in range(num_cycles):
            # Potentiation (SET)
            for i in range(steps):
                # Pulse
                times.extend([t, t, t+p_w, t+p_w])
                voltages.extend([0, set_v, set_v, 0])
                t += p_w
                
                # Delay before read
                t += delay_before_read
                
                # Read after pulse
                read_start = t + read_rise
                read_end = read_start + read_width
                read_center = (read_start + read_end) / 2
                read_times.append(read_center)
                times.extend([t, t, read_start, read_start, read_end, read_end, read_end + read_rise, read_end + read_rise])
                voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, 0])
                t = read_end + read_rise
                
                # Wait before next pulse (if not last in this direction)
                if i < steps - 1:
                    t += delay_between_pulses
            
            # Depression (RESET)
            for i in range(steps):
                # Pulse
                times.extend([t, t, t+p_w, t+p_w])
                voltages.extend([0, reset_v, reset_v, 0])
                t += p_w
                
                # Delay before read
                t += delay_before_read
                
                # Read after pulse
                read_start = t + read_rise
                read_end = read_start + read_width
                read_center = (read_start + read_end) / 2
                read_times.append(read_center)
                times.extend([t, t, read_start, read_start, read_end, read_end, read_end + read_rise, read_end + read_rise])
                voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, 0])
                t = read_end + read_rise
                
                # Wait before next pulse (if not last in this direction)
                if i < steps - 1:
                    t += delay_between_pulses
            
            # Delay between cycles (between potentiation and depression, or between cycle pairs)
            if cycle < num_cycles - 1:
                t += delay_between_cycles
        
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'red', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, 
                                     where=np.array(voltages)>=0, color='green', label='SET')
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3,
                                     where=np.array(voltages)<0, color='red', label='RESET')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        title = f'Pot-Dep Cycle: Initial Read → {num_cycles}×({steps} SET → {steps} RESET)'
        self.ax.set_title(title, fontsize=9)
        self.ax.legend(fontsize=8)
        self.ax.grid(True, alpha=0.3)
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0
    
    def _draw_potentiation_only(self, params):
        """Draw potentiation only with initial read"""
        t = 0
        times, voltages = [], []
        read_times = []
        set_v = params.get('set_voltage', 2.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        n = params.get('num_pulses', 30)  # Show all pulses, not limited to 5
        
        # Get timing parameters (already in seconds from update_pulse_diagram)
        is_4200a = self._system_name in ('keithley4200a',)
        if is_4200a:
            read_width = params.get('read_width', 0.5e-6)  # Already in seconds
            read_rise = params.get('read_rise_time', 0.1e-6) if 'read_rise_time' in params else 0.1e-6
        else:
            read_width = params.get('read_width', 1e-3) if 'read_width' in params else 1e-3
            read_rise = 0.1e-3
        delay_before_read = params.get('delay_before_read', 10e-6)  # Already in seconds
        delay_between_pulses = params.get('delay_between_pulses', 10e-3)
        delay_between_cycles = params.get('delay_between_cycles', 10e-3)
        
        # Initial read before any pulses
        read_start = t + delay_before_read + read_rise
        read_end = read_start + read_width
        read_center = (read_start + read_end) / 2
        read_times.append(read_center)
        times.extend([t, t, read_start, read_start, read_end, read_end, read_end + read_rise, read_end + read_rise])
        voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, 0])
        t = read_end + read_rise
        
        for i in range(n):
            # Pulse
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, set_v, set_v, 0])
            t += p_w
            
            # Delay before read
            t += delay_before_read
            
            # Read after pulse
            read_start = t + read_rise
            read_end = read_start + read_width
            read_center = (read_start + read_end) / 2
            read_times.append(read_center)
            times.extend([t, t, read_start, read_start, read_end, read_end, read_end + read_rise, read_end + read_rise])
            voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, 0])
            t = read_end + read_rise
            
            # Wait before next pulse (if not last)
            if i < n - 1:
                t += delay_between_pulses
        
        # Post-pulse reads (if enabled)
        num_post_reads = params.get('num_post_reads', 0)
        post_interval = params.get('post_read_interval', 1e-3)
        if num_post_reads > 0:
            t += 0.0001  # Small delay after last pulse
            post_n = min(num_post_reads, 3)  # Show max 3 for diagram
            for i in range(post_n):
                t += post_interval
                read_t = t + 0.001*0.5  # Read at middle of 1ms pulse
                read_times.append(read_t)
                times.extend([t, t, t+0.001, t+0.001])
                voltages.extend([0, r_v, r_v, 0])
                t += 0.001
        
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'green', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='green')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        title = f'Potentiation: Initial Read → {n} SET pulses'
        if num_post_reads > 0:
            title += f' → {num_post_reads} post-reads'
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(title, fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [set_v, r_v, 0])
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0
    
    def _draw_depression_only(self, params):
        """Draw depression only with initial read"""
        t = 0
        times, voltages = [], []
        read_times = []
        reset_v = params.get('reset_voltage', -2.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        n = params.get('num_pulses', 30)  # Show all pulses, not limited to 5
        
        # Get timing parameters (already in seconds from update_pulse_diagram)
        is_4200a = self._system_name in ('keithley4200a',)
        if is_4200a:
            read_width = params.get('read_width', 0.5e-6)  # Already in seconds
            read_rise = params.get('read_rise_time', 0.1e-6) if 'read_rise_time' in params else 0.1e-6
        else:
            read_width = params.get('read_width', 1e-3) if 'read_width' in params else 1e-3
            read_rise = 0.1e-3
        delay_before_read = params.get('delay_before_read', 10e-6)  # Already in seconds
        delay_between_pulses = params.get('delay_between_pulses', 10e-3)
        delay_between_cycles = params.get('delay_between_cycles', 10e-3)
        
        # Initial read before any pulses
        read_start = t + delay_before_read + read_rise
        read_end = read_start + read_width
        read_center = (read_start + read_end) / 2
        read_times.append(read_center)
        times.extend([t, t, read_start, read_start, read_end, read_end, read_end + read_rise, read_end + read_rise])
        voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, 0])
        t = read_end + read_rise
        
        for i in range(n):
            # Pulse
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, reset_v, reset_v, 0])
            t += p_w
            
            # Delay before read
            t += delay_before_read
            
            # Read after pulse
            read_start = t + read_rise
            read_end = read_start + read_width
            read_center = (read_start + read_end) / 2
            read_times.append(read_center)
            times.extend([t, t, read_start, read_start, read_end, read_end, read_end + read_rise, read_end + read_rise])
            voltages.extend([0, 0, 0, r_v, r_v, r_v, r_v, 0])
            t = read_end + read_rise
            
            # Wait before next pulse (if not last)
            if i < n - 1:
                t += delay_between_pulses
        
        # Post-pulse reads (if enabled)
        num_post_reads = params.get('num_post_reads', 0)
        post_interval = params.get('post_read_interval', 1e-3)
        if num_post_reads > 0:
            t += 0.0001  # Small delay after last pulse
            post_n = min(num_post_reads, 3)  # Show max 3 for diagram
            for i in range(post_n):
                t += post_interval
                read_t = t + 0.001*0.5  # Read at middle of 1ms pulse
                read_times.append(read_t)
                times.extend([t, t, t+0.001, t+0.001])
                voltages.extend([0, r_v, r_v, 0])
                t += 0.001
        
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'red', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='red')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        title = f'Depression: Initial Read → {n} RESET pulses'
        if num_post_reads > 0:
            title += f' → {num_post_reads} post-reads'
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(title, fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [reset_v, r_v, 0])
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0
    
    def _set_preview_ylim(self, values):
        """Set Y limits for preview plots, handling negative voltages."""
        if not values:
            self.ax.set_ylim(-1, 1)
            return
        min_v = min(values)
        max_v = max(values)
        if min_v == max_v:
            pad = max(0.1, abs(max_v) * 0.1 + 0.1)
        else:
            pad = max(0.1, (max_v - min_v) * 0.1)
        self.ax.set_ylim(min_v - pad, max_v + pad)
    
    def _draw_endurance(self, params):
        """Draw endurance test with initial read"""
        t = 0
        times, voltages = [], []
        read_times = []
        set_v = params.get('set_voltage', 2.0)
        reset_v = params.get('reset_voltage', -2.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        cycles = min(params.get('num_cycles', 100), 3)
        
        # Initial read before any cycles
        read_t = t + p_w*0.15
        read_times.append(read_t)
        times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
        voltages.extend([0, r_v, r_v, 0])
        t += p_w*0.3 + 0.0001
        
        for i in range(cycles):
            # SET + read
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, set_v, set_v, 0])
            t += p_w + 0.0001
            read_t = t + p_w*0.15
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.3 + params.get('delay_between', 10e-3)
            # RESET + read
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, reset_v, reset_v, 0])
            t += p_w + 0.0001
            read_t = t + p_w*0.15
            read_times.append(read_t)
            times.extend([t, t, t+p_w*0.3, t+p_w*0.3])
            voltages.extend([0, r_v, r_v, 0])
            t += p_w*0.3 + params.get('delay_between', 10e-3)
        
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'brown', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='brown')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'Endurance: Initial Read → {cycles} SET/RESET cycles', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0
    
    def _draw_smu_retention(self, params):
        """Draw SMU retention test: Initial Read → Pulse → Read @ t1 → Read @ t2 → Read @ t3..."""
        t = 0
        times, voltages = [], []
        read_times = []
        pulse_v = params.get('pulse_voltage', 2.0)
        read_v = params.get('read_voltage', 0.2)
        pulse_duration = params.get('pulse_duration', 0.1)  # seconds
        read_duration = params.get('read_duration', 0.01)  # seconds
        num_reads = min(params.get('num_reads', 10), 10)  # Limit to 10 for visualization
        delay_between_reads = params.get('delay_between_reads', 1.0)  # seconds
        
        # Draw initial read before pulse
        initial_read_start = t
        initial_read_end = t + read_duration
        initial_read_center = (initial_read_start + initial_read_end) / 2
        read_times.append(initial_read_center)
        times.extend([initial_read_start, initial_read_start, initial_read_end, initial_read_end])
        voltages.extend([0, read_v, read_v, 0])
        t = initial_read_end + 0.001  # Small gap after initial read
        
        # Draw the pulse
        times.extend([t, t, t + pulse_duration, t + pulse_duration])
        voltages.extend([0, pulse_v, pulse_v, 0])
        t += pulse_duration + 0.001  # Small gap after pulse
        
        # Draw multiple reads over time
        for i in range(num_reads):
            if i > 0:
                t += delay_between_reads
            
            # Read pulse
            read_start = t
            read_end = t + read_duration
            read_center = (read_start + read_end) / 2
            read_times.append(read_center)
            
            times.extend([read_start, read_start, read_end, read_end])
            voltages.extend([0, read_v, read_v, 0])
            t = read_end + 0.001  # Small gap after read
        
        # Convert to milliseconds for display
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'brown', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='brown')
        
        # Mark read points (initial read in different color/style)
        for i, rt in enumerate(read_times):
            if i == 0:
                # Initial read - use different marker
                self.ax.plot(rt*1e3, read_v, 'go', markersize=10, markeredgewidth=2, label='Initial Read')
            else:
                # Subsequent reads
                self.ax.plot(rt*1e3, read_v, 'rx', markersize=10, markeredgewidth=2)
        
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'SMU Retention: Initial Read → Pulse → {num_reads} Reads Over Time', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)
    
    def _draw_pulse_multi_read(self, params):
        """Draw initial read → pulse followed by multiple reads"""
        t = 0
        times, voltages = [], []
        read_times = []
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-6)  # Default in seconds for 4200A
        n_pulses = params.get('num_pulses', 1)
        n_reads = params.get('num_reads', 50)
        pulses_to_draw = min(n_pulses, 12)
        reads_to_draw = min(n_reads, 12)
        
        # Get actual delay parameters (already in seconds)
        delay_between_pulses = params.get('delay_between_pulses', 1e-6)  # Default 1µs
        delay_between_reads = params.get('delay_between_reads', 100e-6)  # Default 100µs
        read_width = max(params.get('read_width', 0.5e-6 if self._system_name in ('keithley4200a',) else 1e-3), 1e-9)
        
        # Check if 4200A - use realistic timing
        is_4200a = self._system_name in ('keithley4200a',)
        if is_4200a:
            read_rise = params.get('read_rise_time', 0.1e-6)  # 0.1µs in seconds
            
            # Initial read before pulses
            read_start = t + read_rise
            read_end = read_start + read_width
            read_center = (read_start + read_end) / 2
            read_times.append(read_center)
            times.extend([t, t, read_start, read_start, read_end, read_end])
            voltages.extend([0, 0, 0, r_v, r_v, 0])
            t = read_end + max(1e-6, delay_between_pulses, delay_between_reads, read_width * 0.2)
        else:
            # For 2450: simplified timing
            read_t = t + read_width / 2
            read_times.append(read_t)
            times.extend([t, t, t+read_width, t+read_width])
            voltages.extend([0, r_v, r_v, 0])
            t += read_width + max(delay_between_reads, read_width * 0.2)
        
        # N pulses
        for i in range(pulses_to_draw):
            times.extend([t, t, t+p_w, t+p_w])
            voltages.extend([0, p_v, p_v, 0])
            t += p_w + delay_between_pulses
        
        # Many reads after pulses (use actual delay_between_reads)
        if is_4200a:
            read_rise = params.get('read_rise_time', 0.1e-6)
            for i in range(reads_to_draw):
                read_start = t + read_rise
                read_end = read_start + read_width
                read_center = (read_start + read_end) / 2
                read_times.append(read_center)
                times.extend([t, t, read_start, read_start, read_end, read_end])
                voltages.extend([0, 0, 0, r_v, r_v, 0])
                t = read_end + delay_between_reads
        else:
            for i in range(reads_to_draw):
                read_t = t + read_width / 2
                read_times.append(read_t)
                times.extend([t, t, t+read_width, t+read_width])
                voltages.extend([0, r_v, r_v, 0])
                t += read_width
                if i < reads_to_draw - 1:
                    t += delay_between_reads
        
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'cyan', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='cyan')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'Initial Read → {n_pulses}×Pulse → {n_reads} Reads', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [r_v, p_v, 0])
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0
        
        if n_pulses > pulses_to_draw or n_reads > reads_to_draw:
            self.ax.text(0.98, 0.9,
                                 "preview truncated",
                                 transform=self.ax.transAxes,
                                 ha='right', va='top', fontsize=8, color='gray')
    
    def _draw_multi_read_only(self, params):
        """Draw multiple reads only"""
        t = 0
        times, voltages = [], []
        read_times = []
        r_v = params.get('read_voltage', 0.2)
        n_reads = min(params.get('num_reads', 100), 8)
        
        for i in range(n_reads):
            read_t = t + 0.0005
            read_times.append(read_t)
            times.extend([t, t, t+0.001, t+0.001])
            voltages.extend([0, r_v, r_v, 0])
            t += 0.001 + params.get('delay_between', 100e-3)
        
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'gray', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='gray')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'Only Reads: {n_reads} measurements', fontsize=10)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [r_v, 0])
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0
    
    def _draw_relaxation(self, params, with_pulse_measurement=False):
        """Draw relaxation pattern"""
        t = 0.0
        times, voltages = [], []
        read_times = []
        pulse_read_times = []  # Read at pulse peak
        p_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        is_4200a = self._system_name in ('keithley4200a',)
        
        pulse_width = max(params.get('pulse_width', 1e-6 if is_4200a else 1e-3), 1e-9)
        delay_between_pulses = max(params.get('delay_between_pulses', 1e-6 if is_4200a else 1e-3), 0.0)
        read_width = max(params.get('read_width', 0.5e-6 if is_4200a else 1e-3), 1e-9)
        delay_between_reads = max(params.get('delay_between_reads', 100e-6 if is_4200a else 1e-3), 0.0)
        
        n_pulses = params.get('num_pulses', 10)
        n_reads = params.get('num_reads', 10)
        pulses_to_draw = min(n_pulses, 12)
        reads_to_draw = min(n_reads, 12)
        
        # Initial read
        if is_4200a:
            read_rise = params.get('read_rise_time', 0.1e-6)
            read_start = t + read_rise
            read_end = read_start + read_width
            read_times.append((read_start + read_end) / 2)
            times.extend([t, t, read_start, read_start, read_end, read_end])
            voltages.extend([0, 0, 0, r_v, r_v, 0])
            t = read_end + max(1e-6, delay_between_pulses, read_width * 0.2)
        else:
            read_times.append(t + read_width / 2)
            times.extend([t, t, t + read_width, t + read_width])
            voltages.extend([0, r_v, r_v, 0])
            t += read_width + max(delay_between_reads, read_width * 0.2)
        
        # Multiple pulses
        for i in range(pulses_to_draw):
            pulse_start_t = t
            times.extend([t, t, t + pulse_width, t + pulse_width])
            voltages.extend([0, p_v, p_v, 0])
            if with_pulse_measurement:
                pulse_read_times.append(pulse_start_t + pulse_width * 0.5)  # Peak read marker
            t += pulse_width
            if i < pulses_to_draw - 1:
                t += delay_between_pulses
        
        # Pause before reads
        t += max(delay_between_reads, pulse_width * 0.1)
        
        # Multiple reads (relaxation)
        if is_4200a:
            read_rise = params.get('read_rise_time', 0.1e-6)
            for i in range(reads_to_draw):
                read_start = t + read_rise
                read_end = read_start + read_width
                read_times.append((read_start + read_end) / 2)
                times.extend([t, t, read_start, read_start, read_end, read_end])
                voltages.extend([0, 0, 0, r_v, r_v, 0])
                t = read_end
                if i < reads_to_draw - 1:
                    t += delay_between_reads
        else:
            for i in range(reads_to_draw):
                read_times.append(t + read_width / 2)
                times.extend([t, t, t + read_width, t + read_width])
                voltages.extend([0, r_v, r_v, 0])
                t += read_width
                if i < reads_to_draw - 1:
                    t += delay_between_reads
        
        times_ms = np.array(times) * 1e3
        self.ax.plot(times_ms, voltages, 'magenta', linewidth=2)
        self.ax.fill_between(times_ms, 0, voltages, alpha=0.3, color='magenta')
        # Regular reads
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=10, markeredgewidth=2)
        # Pulse-peak reads (if with pulse measurement)
        for pt in pulse_read_times:
            self.ax.plot(pt*1e3, p_v, 'rx', markersize=10, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        title = f'Relaxation (Pulse Meas): 1Read→{n_pulses}Pulse→{n_reads}Read' if with_pulse_measurement else f'Relaxation: 1Read→{n_pulses}Pulse→{n_reads}Read'
        self.ax.set_title(title, fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [r_v, p_v, 0])
        if times_ms.size > 0:
            self.ax.set_xlim(0, times_ms[-1]*1.1)  # Start at 0
        if n_pulses > pulses_to_draw or n_reads > reads_to_draw:
            self.ax.text(0.98, 0.9, "preview truncated",
                                 transform=self.ax.transAxes,
                                 ha='right', va='top', fontsize=8, color='gray')
    
    def _draw_voltage_sweep(self, params):
        """Draw: For each voltage: Initial Read → (Pulse → Read) × N → Reset"""
        t = 0
        times, voltages = [], []
        read_times = []
        start_v = params.get('pulse_voltage_start', 0.5)
        stop_v = params.get('pulse_voltage_stop', 2.5)
        step_v = params.get('pulse_voltage_step', 0.1)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        reset_v = params.get('reset_voltage', -1.0)
        reset_w = params.get('reset_width', 1e-3)
        pulses_per_v = min(params.get('num_pulses_per_voltage', 5), 3)  # Show max 3
        
        # Show 2-3 voltage levels for diagram
        num_voltages = min(int((stop_v - start_v) / step_v) + 1, 3)
        pulse_voltages = [start_v + i * step_v for i in range(num_voltages)]
        
        for v_idx, pulse_v in enumerate(pulse_voltages):
            # Initial read before pulses at this voltage
            read_times.append(t)
            t += 0.001
            
            # Pulses at this voltage
            for p in range(pulses_per_v):
                times.append(t)
                voltages.append(pulse_v)
                t += p_w
                times.append(t)
                voltages.append(0)
                t += 0.00001
                read_times.append(t)
                t += 0.001
                if p < pulses_per_v - 1:
                    t += delay
            
            # Reset between voltages (except last)
            if v_idx < len(pulse_voltages) - 1:
                times.append(t)
                voltages.append(reset_v)
                t += reset_w
                times.append(t)
                voltages.append(0)
                t += 0.00001
        
        self.ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='blue')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'Voltage Sweep: {start_v}V to {stop_v}V, {pulses_per_v} pulses/voltage', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [reset_v, start_v, stop_v, r_v, 0])
    
    def _draw_ispp(self, params):
        """Draw: Initial Read → (Pulse with increasing voltage → Read) × N"""
        t = 0
        times, voltages = [], []
        read_times = []
        start_v = params.get('start_voltage', 0.5)
        step_v = params.get('voltage_step', 0.05)
        max_v = params.get('max_voltage', 3.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        max_pulses = min(params.get('max_pulses', 100), 10)  # Show max 10
        
        # Initial read
        read_times.append(t)
        t += 0.001
        
        # ISPP pulses with increasing voltage
        current_v = start_v
        for p in range(max_pulses):
            if current_v > max_v:
                break
            times.append(t)
            voltages.append(current_v)
            t += p_w
            times.append(t)
            voltages.append(0)
            t += 0.00001
            read_times.append(t)
            t += 0.001
            current_v += step_v
            if p < max_pulses - 1:
                t += delay
        
        self.ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='green')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'ISPP: {start_v}V → {max_v}V, step {step_v}V', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [r_v, start_v, max_v, 0])
    
    def _draw_threshold(self, params):
        """Draw: For each voltage: Initial Read → (Pulse → Read) × N"""
        t = 0
        times, voltages = [], []
        read_times = []
        start_v = params.get('start_voltage', 0.5)
        step_v = params.get('voltage_step', 0.05)
        max_v = params.get('max_voltage', 3.0)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        pulses_per_v = min(params.get('num_pulses_per_voltage', 3), 2)  # Show max 2
        direction = params.get('direction', 'set')
        
        # Show 3 voltage levels for diagram
        num_voltages = min(int((max_v - start_v) / step_v) + 1, 3)
        pulse_voltages = [start_v + i * step_v for i in range(num_voltages)]
        if direction.lower() == 'reset':
            pulse_voltages = [-v for v in pulse_voltages]
        
        for pulse_v in pulse_voltages:
            # Initial read before pulses at this voltage
            read_times.append(t)
            t += 0.001
            
            # Pulses at this voltage
            for p in range(pulses_per_v):
                times.append(t)
                voltages.append(pulse_v)
                t += p_w
                times.append(t)
                voltages.append(0)
                t += 0.00001
                read_times.append(t)
                t += 0.001
                if p < pulses_per_v - 1:
                    t += delay
        
        self.ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='orange')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'Threshold Test ({direction.upper()}): {start_v}V → {max_v}V', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [r_v, -max_v, max_v, 0])
    
    def _draw_multilevel(self, params):
        """Draw: For each level: Reset → Program with pulses → Read"""
        t = 0
        times, voltages = [], []
        read_times = []
        pulse_v = params.get('pulse_voltage', 1.5)
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        reset_v = params.get('reset_voltage', -1.0)
        reset_w = params.get('reset_width', 1e-3)
        pulses_per_level = min(params.get('num_pulses_per_level', 5), 3)  # Show max 3
        target_levels = params.get('target_levels', [1, 2, 3])
        if isinstance(target_levels, str):
            target_levels = [float(x.strip()) for x in target_levels.split(",")]
        levels_to_show = min(len(target_levels), 3)  # Show max 3 levels
        
        for level_idx in range(levels_to_show):
            # Reset before programming each level
            times.append(t)
            voltages.append(reset_v)
            t += reset_w
            times.append(t)
            voltages.append(0)
            t += 0.00001
            
            # Initial read after reset
            read_times.append(t)
            t += 0.001
            
            # Program with pulses
            for p in range(pulses_per_level):
                times.append(t)
                voltages.append(pulse_v)
                t += p_w
                times.append(t)
                voltages.append(0)
                t += 0.00001
                read_times.append(t)
                t += 0.001
                if p < pulses_per_level - 1:
                    t += delay
        
        self.ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='purple')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'Multilevel: {levels_to_show} levels, {pulses_per_level} pulses/level', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self._set_preview_ylim(voltages + [reset_v, pulse_v, r_v, 0])
    
    def _draw_pulse_train(self, params):
        """Draw: Initial Read → (Pulse1 → Read → Pulse2 → Read → ...) × N. Supports binary pattern (1=on, 0=off)."""
        t = 0
        times, voltages = [], []
        read_times = []
        # Support pulse_pattern (1=on, 0=off) or legacy pulse_voltages list
        pulse_pattern = params.get('pulse_pattern')
        if pulse_pattern is not None:
            pattern = ''.join(c for c in str(pulse_pattern).strip() if c in '01')
            p_v = params.get('pulse_voltage', 1.5)
            pulse_voltages = [p_v if c == '1' else 0.0 for c in pattern] if pattern else [p_v]
        else:
            pulse_voltages = params.get('pulse_voltages', [1.0, 1.5, 2.0, -1.0, -1.5, -2.0])
            if isinstance(pulse_voltages, str):
                pulse_voltages = [float(x.strip()) for x in pulse_voltages.split(",")]
        r_v = params.get('read_voltage', 0.2)
        p_w = params.get('pulse_width', 1e-3)
        delay = params.get('delay_between', 10e-3)
        num_repeats = min(params.get('num_repeats', 1), 2)  # Show max 2 repeats
        
        # Initial read
        read_times.append(t)
        t += 0.001
        
        # Pulse train pattern
        for repeat in range(num_repeats):
            for pulse_v in pulse_voltages:
                # Vertical rising edge: t → pulse_v (duplicate time for vertical line)
                times.extend([t, t])
                voltages.extend([0, pulse_v])
                t += p_w
                # Vertical falling edge: t+width → 0 (duplicate time for vertical line)
                times.extend([t, t])
                voltages.extend([pulse_v, 0])
                t += 0.00001
                read_times.append(t)
                t += 0.001
                t += delay
        
        self.ax.fill_between(np.array(times)*1e3, 0, voltages, alpha=0.3, color='cyan')
        for rt in read_times:
            self.ax.plot(rt*1e3, r_v, 'rx', markersize=8, markeredgewidth=2)
        self.ax.set_xlabel('Time (ms)')
        self.ax.set_ylabel('Voltage (V)')
        self.ax.set_title(f'Pulse Train: {len(pulse_voltages)} voltages × {num_repeats} repeats', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        extra = pulse_voltages if isinstance(pulse_voltages, list) else []
        self._set_preview_ylim(voltages + extra + [r_v, 0])
    
    def _draw_laser_and_read(self, params):
        """Draw laser and read pattern using visualizer"""
        try:
            # Check if current system is 4200A (values are in µs)
            is_4200a = self._system_name in ('keithley4200a',)
            
            # Extract parameters (already converted to seconds in update_pulse_diagram)
            read_voltage = params.get('read_voltage', 0.3)
            read_width_s = params.get('read_width', 0.5e-6)  # Already in seconds
            read_period_s = params.get('read_period', 2.0e-6)  # Already in seconds
            num_reads_total = params.get('num_reads', 500)  # Total number of reads for generation
            laser_voltage_high = params.get('laser_voltage_high', 1.5)
            laser_voltage_low = params.get('laser_voltage_low', 0.0)
            laser_width_s = params.get('laser_width', 10.0e-6)  # Already in seconds
            laser_delay_s = params.get('laser_delay', 5.0e-6)  # Already in seconds
            laser_rise_time_s = params.get('laser_rise_time', 0.1e-6)  # Already in seconds
            laser_fall_time_s = params.get('laser_fall_time', 0.1e-6)  # Already in seconds
            
            # Calculate how many reads to show - ensure at least 20 reads are visible
            min_reads_to_show = 20
            # Calculate laser end time (in seconds)
            laser_end_time_s = laser_delay_s + laser_width_s + laser_fall_time_s
            # Calculate time needed for 20 reads (in seconds)
            time_for_20_reads_s = min_reads_to_show * read_period_s
            
            # Use whichever is longer: 20 reads or full laser pulse (with some margin)
            # Convert margin to seconds (5 µs = 5e-6 s)
            margin_s = 5e-6
            num_reads_to_generate = max(
                min_reads_to_show,
                int((laser_end_time_s + margin_s) / read_period_s) + 5  # Show laser plus margin
            )
            # But don't generate more than the total requested reads
            num_reads_to_generate = min(num_reads_to_generate, num_reads_total)
            
            # Create visualizer and generate timeline
            visualizer = PulsePatternVisualizer(time_resolution=0.1e-6)  # 100ns resolution
            timeline = visualizer.generate_laser_and_read_pattern(
                read_voltage=read_voltage,
                read_width=read_width_s,
                read_period=read_period_s,
                num_reads=num_reads_to_generate,
                laser_voltage_high=laser_voltage_high,
                laser_voltage_low=laser_voltage_low,
                laser_width=laser_width_s,
                laser_delay=laser_delay_s,
                laser_rise_time=laser_rise_time_s,
                laser_fall_time=laser_fall_time_s
            )
            
            # Clear axis completely - remove any existing twin axes
            self.ax.clear()
            # Remove any existing secondary axes (twinx axes)
            # Get all axes in the figure and remove any that aren't the main one
            for ax in self.fig.get_axes():
                if ax != self.ax:
                    try:
                        self.fig.delaxes(ax)
                    except:
                        pass
            
            # Convert time to microseconds for display
            time_us = timeline.time_points * 1e6
            
            # Create two y-axes for voltage and laser (create fresh twin axis)
            ax_voltage = self.ax
            ax_laser = ax_voltage.twinx()
            
            # Plot voltage signal (read pulses) on left axis
            ax_voltage.plot(time_us, timeline.voltage_signal, 'b-', linewidth=1.5, label='CH1 Read', alpha=0.8)
            ax_voltage.fill_between(time_us, 0, timeline.voltage_signal, alpha=0.3, color='blue')
            ax_voltage.set_ylabel('Read Voltage (V)', color='blue', fontsize=9, fontweight='bold')
            ax_voltage.tick_params(axis='y', labelcolor='blue')
            
            # Plot laser signal on right axis
            ax_laser.plot(time_us, timeline.laser_signal, 'r-', linewidth=2, label='CH2 Laser', alpha=0.8)
            ax_laser.fill_between(time_us, laser_voltage_low, timeline.laser_signal, 
                                 where=(timeline.laser_signal > laser_voltage_low * 1.1),
                                 alpha=0.3, color='red')
            ax_laser.set_ylabel('Laser Voltage (V)', color='red', fontsize=9, fontweight='bold')
            ax_laser.tick_params(axis='y', labelcolor='red')
            
            # Mark laser pulse (only one should exist, but handle first one only)
            laser_end_time_display_us = 0
            if timeline.laser_pulses and len(timeline.laser_pulses) > 0:
                # Only process the first laser pulse (should only be one)
                laser_start, laser_end = timeline.laser_pulses[0]
                laser_start_us = laser_start * 1e6
                laser_end_us = laser_end * 1e6
                laser_end_time_display_us = laser_end_us
                
                # Draw laser pulse region
                ax_laser.axvspan(laser_start_us, laser_end_us, alpha=0.2, color='orange')
                ax_laser.axvline(laser_start_us, color='red', linestyle='--', alpha=0.7, linewidth=1.5)
                ax_laser.axvline(laser_end_us, color='red', linestyle='--', alpha=0.7, linewidth=1.5)
                
                # Add single annotation at the center of the laser pulse
                mid_time = (laser_start_us + laser_end_us) / 2
                duration = laser_end_us - laser_start_us
                ax_laser.annotate(f'ON\n{duration:.2f} µs', 
                               xy=(mid_time, laser_voltage_high * 0.5),
                               ha='center', va='center', fontsize=8, fontweight='bold',
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
            
            # Mark read windows (show up to 20 or until laser end)
            reads_to_mark = min(len(timeline.read_windows), min_reads_to_show)
            for i, (read_start, read_end) in enumerate(timeline.read_windows[:reads_to_mark]):
                read_start_us = read_start * 1e6
                read_end_us = read_end * 1e6
                ax_voltage.axvspan(read_start_us, read_end_us, alpha=0.15, color='cyan')
                if i == 0:
                    ax_voltage.axvline(read_start_us, color='cyan', linestyle='--', alpha=0.5, linewidth=0.8)
            
            # Set labels and title
            ax_voltage.set_xlabel('Time (µs)', fontsize=9, fontweight='bold')
            ax_voltage.set_title('Laser and Read Pattern: CH1 Reads & CH2 Laser', fontsize=10, fontweight='bold')
            ax_voltage.grid(True, alpha=0.3)
            
            # Calculate x limits: show at least 20 reads OR full laser pulse (whichever is longer)
            time_for_20_reads_s = min_reads_to_show * read_period_s
            time_for_20_reads_us = time_for_20_reads_s * 1e6  # Convert to µs for display
            if laser_end_time_display_us > 0:
                # Show whichever is longer: 20 reads or laser pulse + margin
                max_time = max(time_for_20_reads_us, laser_end_time_display_us + 2)  # +2 µs margin after laser
            else:
                # No laser pulse, show at least 20 reads
                max_time = time_for_20_reads_us
            
            # Don't exceed the actual data range
            max_time = min(max_time, time_us[-1])
            ax_voltage.set_xlim(0, max_time)
            
            # Add legend
            lines1, labels1 = ax_voltage.get_legend_handles_labels()
            lines2, labels2 = ax_laser.get_legend_handles_labels()
            ax_voltage.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=8)
            
        except Exception as e:
            self.ax.clear()
            self.ax.text(0.5, 0.5, f"Error drawing pattern:\n{str(e)}", 
                               ha='center', va='center', fontsize=9)
            self.ax.set_xlim(0, 1)
            self.ax.set_ylim(0, 1)

    def _draw_optical_read_pulsed_light(self, params):
        """Draw: Read voltage constant; optical pulse rectangles every period (twin axes, time in s).
        Draw each laser pulse as a rectangular axvspan so they render as clear rectangles, not triangles.
        """
        read_voltage = params.get('read_voltage', 0.2)
        total_time_s = max(params.get('total_time_s', 10.0), 0.1)
        optical_pulse_duration_s = params.get('optical_pulse_duration_s', 0.2)
        optical_pulse_period_s = max(params.get('optical_pulse_period_s', 1.0), 1e-6)
        # Build rectangular spans: one (t_start, t_end) per pulse
        pulse_spans = []
        t = 0.0
        while t < total_time_s:
            pulse_spans.append((t, t + optical_pulse_duration_s))
            t += optical_pulse_period_s
        volt_t = np.array([0, total_time_s])
        volt_v = np.array([read_voltage, read_voltage])
        self.ax.clear()
        for ax in self.fig.get_axes():
            if ax != self.ax:
                try:
                    self.fig.delaxes(ax)
                except Exception:
                    pass
        ax_voltage = self.ax
        ax_optical = ax_voltage.twinx()
        ax_voltage.plot(volt_t, volt_v, 'b-', linewidth=2, label='Read voltage (V)')
        ax_voltage.fill_between(volt_t, 0, volt_v, alpha=0.3, color='blue')
        ax_voltage.set_ylabel('Read Voltage (V)', color='blue', fontsize=9)
        ax_voltage.tick_params(axis='y', labelcolor='blue')
        # Draw each optical pulse as a rectangle (axvspan) so they look like blocks, not triangles
        for t_start, t_end in pulse_spans:
            ax_optical.axvspan(t_start, t_end, ymin=0, ymax=1, alpha=0.3, color='red')
        ax_optical.set_ylabel('Laser (on/off)', color='red', fontsize=9)
        ax_optical.tick_params(axis='y', labelcolor='red')
        ax_optical.set_ylim(-0.1, 1.2)
        ax_optical.set_xlim(0, total_time_s)
        ax_voltage.set_xlabel('Time (s)', fontsize=9)
        ax_voltage.set_title('Optical Read (Pulsed Light): Read V + optical pulses', fontsize=10)
        ax_voltage.set_xlim(0, total_time_s)
        ax_voltage.grid(True, alpha=0.3)
        self._set_preview_ylim([read_voltage, 0])

    def _draw_optical_pulse_train_read(self, params):
        """Draw: Read voltage constant; one optical pulse train (N pulses, on_ms, off_ms). Time in s.
        Draw each laser pulse as a rectangular axvspan so they render as clear rectangles, not triangles.
        """
        read_voltage = params.get('read_voltage', 0.2)
        duration_s = max(params.get('duration_s', 5.0), 0.1)
        optical_on_ms = params.get('optical_on_ms', 100.0)
        optical_off_ms = params.get('optical_off_ms', 100.0)
        n_optical_pulses = min(int(params.get('n_optical_pulses', 5)), 50)
        on_s = optical_on_ms / 1000.0
        off_s = optical_off_ms / 1000.0
        period_s = on_s + off_s
        # Build rectangular spans: one (t_start, t_end) per pulse
        pulse_spans = []
        t = 0.0
        for _ in range(n_optical_pulses):
            pulse_spans.append((t, t + on_s))
            t += period_s
        volt_t = np.array([0, duration_s])
        volt_v = np.array([read_voltage, read_voltage])
        self.ax.clear()
        for ax in self.fig.get_axes():
            if ax != self.ax:
                try:
                    self.fig.delaxes(ax)
                except Exception:
                    pass
        ax_voltage = self.ax
        ax_optical = ax_voltage.twinx()
        ax_voltage.plot(volt_t, volt_v, 'b-', linewidth=2, label='Read voltage (V)')
        ax_voltage.fill_between(volt_t, 0, volt_v, alpha=0.3, color='blue')
        ax_voltage.set_ylabel('Read Voltage (V)', color='blue', fontsize=9)
        ax_voltage.tick_params(axis='y', labelcolor='blue')
        # Draw each optical pulse as a rectangle (axvspan) so they look like blocks, not triangles
        for t_start, t_end in pulse_spans:
            ax_optical.axvspan(t_start, t_end, ymin=0, ymax=1, alpha=0.3, color='red')
        ax_optical.set_ylabel('Laser (on/off)', color='red', fontsize=9)
        ax_optical.tick_params(axis='y', labelcolor='red')
        ax_optical.set_ylim(-0.1, 1.2)
        ax_optical.set_xlim(0, duration_s)
        ax_voltage.set_xlabel('Time (s)', fontsize=9)
        ax_voltage.set_title(f'Optical Pulse Train + Read: {n_optical_pulses} pulses (on {optical_on_ms}ms / off {optical_off_ms}ms)', fontsize=9)
        ax_voltage.set_xlim(0, duration_s)
        ax_voltage.grid(True, alpha=0.3)
        self._set_preview_ylim([read_voltage, 0])
    
    def _draw_optical_laser_pattern_read(self, params):
        """Draw: SMU reads continuously at constant voltage while laser fires per binary pattern (1=on, 0=off).
        Shows continuous SMU read voltage + laser pulses firing only for '1' slots.
        """
        read_voltage = params.get('read_voltage', 0.2)
        duration_s = max(params.get('duration_s', 5.0), 0.1)
        optical_on_ms = params.get('optical_on_ms', 100.0)
        optical_off_ms = params.get('optical_off_ms', 100.0)
        pattern_raw = str(params.get('laser_pattern', '11111')).strip()
        laser_delay_s = params.get('laser_delay_s', 0.0)
        
        # Parse pattern - number of slots is determined by pattern length
        pattern = ''.join(c for c in pattern_raw if c in '01')
        if not pattern:
            pattern = '11111'  # Default if empty
        # Limit display to first 15 slots for clarity
        pattern_display = pattern[:min(len(pattern), 15)]
        
        on_s = optical_on_ms / 1000.0
        off_s = optical_off_ms / 1000.0
        period_s = on_s + off_s
        
        # Build rectangular spans: only for '1' bits in pattern
        pulse_spans = []
        t = laser_delay_s
        for bit in pattern_display:
            if bit == '1':
                pulse_spans.append((t, t + on_s))
            t += period_s
        
        # SMU voltage (constant read throughout entire duration)
        volt_t = np.array([0, duration_s])
        volt_v = np.array([read_voltage, read_voltage])
        
        # Clear existing axes
        self.ax.clear()
        for ax in self.fig.get_axes():
            if ax != self.ax:
                try:
                    self.fig.delaxes(ax)
                except Exception:
                    pass
        
        # Create two y-axes
        ax_voltage = self.ax
        ax_optical = ax_voltage.twinx()
        
        # Plot SMU continuous read (blue line)
        ax_voltage.plot(volt_t, volt_v, 'b-', linewidth=2.5, label='SMU Read (continuous)')
        ax_voltage.fill_between(volt_t, 0, volt_v, alpha=0.3, color='blue')
        ax_voltage.set_ylabel('SMU Read Voltage (V)', color='blue', fontsize=9, fontweight='bold')
        ax_voltage.tick_params(axis='y', labelcolor='blue')
        
        # Draw laser pulses as rectangles (only where pattern has '1')
        for t_start, t_end in pulse_spans:
            ax_optical.axvspan(t_start, t_end, ymin=0, ymax=1, alpha=0.35, color='red')
        
        # Draw faint vertical lines at each slot boundary to show skipped slots
        t_slot = laser_delay_s
        for idx, bit in enumerate(pattern_display):
            if bit == '0':
                # Draw thin dashed line for skipped slot
                ax_optical.axvline(t_slot + on_s/2, color='gray', linestyle=':', alpha=0.4, linewidth=1)
            t_slot += period_s
        
        ax_optical.set_ylabel('Laser (ON/OFF)', color='red', fontsize=9, fontweight='bold')
        ax_optical.tick_params(axis='y', labelcolor='red')
        ax_optical.set_ylim(-0.1, 1.2)
        ax_optical.set_xlim(0, duration_s)
        
        # Format pattern for title
        pattern_str = pattern_display if len(pattern) <= 15 else f"{pattern_display}..."
        ones_count = pattern_display.count('1')
        zeros_count = pattern_display.count('0')
        delay_str = f", delay {laser_delay_s:.1f}s" if laser_delay_s > 0 else ""
        
        ax_voltage.set_xlabel('Time (s)', fontsize=9, fontweight='bold')
        ax_voltage.set_title(
            f'🔬 Optical Pattern: "{pattern_str}" ({ones_count} fire, {zeros_count} skip{delay_str})',
            fontsize=9, fontweight='bold'
        )
        ax_voltage.set_xlim(0, duration_s)
        ax_voltage.grid(True, alpha=0.3)
        self._set_preview_ylim([read_voltage, 0])
    
    def _draw_generic_pattern(self):
        """Generic pattern for unknown tests"""
        self.ax.text(0.5, 0.5, "Pulse Pattern\n(Generic)", ha='center', va='center', fontsize=12)
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
    
    def _add_limit_warnings(self, params):
        """Add visual warnings for parameters near hardware limits"""
        warnings = []
        
        # Skip warnings for 4200A (no 1ms minimum limit)
        is_4200a = self._system_name in ('keithley4200a',)
        
        if not is_4200a:
            # Check pulse width (min 1ms = 0.001s) - only for 2450
            if 'pulse_width' in params:
                pw = params['pulse_width']
                if pw < 1e-3:
                    warnings.append(f"⚠ Pulse width {pw*1e3:.2f}ms < 1ms min")
            
            # Check delay between pulses (min 1ms) - only for 2450
            if 'delay_between' in params:
                delay = params['delay_between']
                if delay < 1e-3:
                    warnings.append(f"⚠ Delay {delay*1e3:.2f}ms < 1ms min")
            
            if 'delay_between_pulses' in params:
                delay = params['delay_between_pulses']
                if delay < 1e-3:
                    warnings.append(f"⚠ Pulse delay {delay*1e3:.2f}ms < 1ms min")
            
            # Check pulse widths list - only for 2450
            if 'pulse_widths' in params:
                widths = params['pulse_widths']
                if isinstance(widths, list):
                    for w in widths:
                        if w < 1e-3:
                            warnings.append(f"⚠ Width {w*1e3:.2f}ms < 1ms min")
                            break
        
        # Display warnings on diagram (only if there are any)
        if warnings:
            warning_text = "\n".join(warnings)
            self.ax.text(0.02, 0.98, warning_text,
                         transform=self.ax.transAxes,
                         fontsize=8, color='red', weight='bold',
                         va='top', ha='left',
                         bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))
