"""
Plot handlers – dispatch by plot_type and draw test results on the GUI axes.
=============================================================================

All _plot_* functions take (gui) and use gui.ax, gui.last_results. Caller clears ax,
calls plot_by_type(gui, plot_type), then gui.canvas.draw().
"""

import math
from typing import Any

import numpy as np
import matplotlib.pyplot as plt


def plot_by_type(gui: Any, plot_type: str) -> None:
    """Plot last_results onto gui.ax by plot_type. Caller must clear ax and call canvas.draw()."""
    if not getattr(gui, "last_results", None):
        return
    plot_type = (plot_type or "time_series").strip() or "time_series"
    handlers = {
        "time_series": _plot_time_series,
        "range_finder": _plot_range_finder,
        "width_vs_resistance": _plot_width_sweep,
        "pot_dep_cycle": _plot_pot_dep_cycle,
        "endurance": _plot_endurance,
        "relaxation_reads": _plot_relaxation_reads,
        "relaxation_all": _plot_relaxation_all,
        "relaxation": _plot_relaxation,
        "voltage_sweep": _plot_voltage_sweep,
        "ispp": _plot_ispp,
        "threshold": _plot_threshold,
        "multilevel": _plot_multilevel,
        "pulse_train": _plot_pulse_train,
    }
    fn = handlers.get(plot_type, _plot_time_series)
    fn(gui)


def _plot_time_series(gui):
    """Plot resistance vs time - raw data, no filtering"""
    test_name = gui.last_results['test_name']
    params = gui.last_results.get('params', {})
    
    timestamps = gui.last_results.get('timestamps', [])
    resistances = gui.last_results.get('resistances', [])
    
    # Only filter out NaN/inf (keep zeros, negatives, and ALL other values including negative!)
    valid_data = []
    for t, r in zip(timestamps, resistances):
        if r is None:
            continue
        if math.isnan(r) or math.isinf(r):
            continue
        # Keep ALL other values including negative ones - NO FILTERING!
        valid_data.append((t, r))
    
    if not valid_data:
        gui.ax.text(0.5, 0.5, 'No valid data to plot\n(All values are NaN or Inf)', 
                    ha='center', va='center', transform=gui.ax.transAxes)
        gui.ax.set_xlabel('Time (s)')
        gui.ax.set_ylabel('Resistance (Ω)')
        gui.ax.set_title(f'{test_name}')
        gui.ax.grid(True, alpha=0.3)
        return
    
    valid_times, valid_resistances = zip(*valid_data)
    
    # Special handling for SMU Retention: plot resistance over time (no pulse_types)
    if test_name == "⚠️ SMU Retention":
        # Retention test: Initial Read → Pulse → Read @ t1 → Read @ t2 → Read @ t3...
        # Timestamps are relative to start (initial read at t=0), plot resistance over time
        if timestamps and resistances:
            # Plot resistance over time
            # Mark initial read (first point) with different style
            if len(timestamps) > 0:
                # Plot initial read with different marker
                gui.ax.plot(timestamps[0], resistances[0], 'go', markersize=10, 
                           markeredgewidth=2, label='Initial Read', alpha=0.8, zorder=3)
                # Plot subsequent reads
                if len(timestamps) > 1:
                    gui.ax.plot(timestamps[1:], resistances[1:], 'o-', color='blue', 
                               markersize=6, linewidth=2, label='After Pulse', alpha=0.8)
            else:
                # Fallback if no data
                gui.ax.plot(timestamps, resistances, 'o-', color='blue', markersize=6, 
                           linewidth=2, label='Resistance', alpha=0.8)
            
            gui.ax.set_xlabel('Time Since Start (s)')
            gui.ax.set_ylabel('Resistance (Ω)')
            gui.ax.set_title('SMU Retention: Resistance vs Time (Initial Read → Pulse → Reads)')
            gui.ax.grid(True, alpha=0.3)
            gui.ax.legend(loc='best')
            
            # Use appropriate scale
            min_r = min(resistances)
            max_r = max(resistances)
            if min_r < 0 or max_r < 0:
                gui.ax.set_yscale('linear')
            elif min_r > 0:
                gui.ax.set_yscale('log')
            else:
                gui.ax.set_yscale('symlog', linthresh=1e-6)
        return
    
    # Special handling for SMU Endurance: plot SET and RESET separately with different colors
    pulse_types = gui.last_results.get('pulse_types', [])
    if test_name in ["⚠️ SMU Endurance", "⚠️ SMU Retention (Pulse Measured)"] and pulse_types:
        # For smu_retention_with_pulse_measurement: plot all four types
        if test_name == "⚠️ SMU Retention (Pulse Measured)":
            # Plot all four types with different colors
            set_pulse_indices = [i for i, pt in enumerate(pulse_types) if pt == "SET_PULSE"]
            read_after_set_indices = [i for i, pt in enumerate(pulse_types) if pt == "READ_AFTER_SET"]
            reset_pulse_indices = [i for i, pt in enumerate(pulse_types) if pt == "RESET_PULSE"]
            read_after_reset_indices = [i for i, pt in enumerate(pulse_types) if pt == "READ_AFTER_RESET"]
            
            # Get all data - NO FILTERING, plot EVERYTHING including negative values
            set_pulse_data = []
            for i in set_pulse_indices:
                if i < len(timestamps) and i < len(resistances):
                    set_pulse_data.append((timestamps[i], resistances[i]))
            
            read_after_set_data = []
            for i in read_after_set_indices:
                if i < len(timestamps) and i < len(resistances):
                    read_after_set_data.append((timestamps[i], resistances[i]))
            
            reset_pulse_data = []
            for i in reset_pulse_indices:
                if i < len(timestamps) and i < len(resistances):
                    reset_pulse_data.append((timestamps[i], resistances[i]))
            
            read_after_reset_data = []
            for i in read_after_reset_indices:
                if i < len(timestamps) and i < len(resistances):
                    read_after_reset_data.append((timestamps[i], resistances[i]))
            
            # Plot each type with different colors and markers
            if set_pulse_data:
                set_pulse_times, set_pulse_res = zip(*set_pulse_data)
                gui.ax.plot(set_pulse_times, set_pulse_res, 'o-', color='blue', markersize=5, 
                           linewidth=2, label='SET Pulse (measured)', alpha=0.8)
            
            if read_after_set_data:
                read_set_times, read_set_res = zip(*read_after_set_data)
                gui.ax.plot(read_set_times, read_set_res, 's-', color='cyan', markersize=4, 
                           linewidth=1.5, label='Read after SET', alpha=0.7)
            
            if reset_pulse_data:
                reset_pulse_times, reset_pulse_res = zip(*reset_pulse_data)
                gui.ax.plot(reset_pulse_times, reset_pulse_res, '^-', color='red', markersize=5, 
                           linewidth=2, label='RESET Pulse (measured)', alpha=0.8)
            
            if read_after_reset_data:
                read_reset_times, read_reset_res = zip(*read_after_reset_data)
                gui.ax.plot(read_reset_times, read_reset_res, 'v-', color='orange', markersize=4, 
                           linewidth=1.5, label='Read after RESET', alpha=0.7)
            
            if set_pulse_data or read_after_set_data or reset_pulse_data or read_after_reset_data:
                gui.ax.legend(loc='best')
                # Set labels and title
                gui.ax.set_xlabel('Time (s)')
                gui.ax.set_ylabel('Resistance (Ω)')
                gui.ax.set_title(gui.last_results['test_name'])
                gui.ax.grid(True, alpha=0.3)
                
                # Use appropriate scale - if all positive use log, otherwise use linear
                all_res = ([r for _, r in set_pulse_data] + [r for _, r in read_after_set_data] +
                          [r for _, r in reset_pulse_data] + [r for _, r in read_after_reset_data])
                if all_res:
                    min_r = min(all_res)
                    max_r = max(all_res)
                    if min_r < 0 or max_r < 0:
                        gui.ax.set_yscale('linear')
                    elif min_r > 0:
                        gui.ax.set_yscale('log')
                    else:
                        gui.ax.set_yscale('symlog', linthresh=1e-6)
            return
        
        # For regular smu_endurance: only READ_AFTER_SET and READ_AFTER_RESET
        set_indices = [i for i, pt in enumerate(pulse_types) if pt == "READ_AFTER_SET"]
        reset_indices = [i for i, pt in enumerate(pulse_types) if pt == "READ_AFTER_RESET"]
        
        # Get all data for SET and RESET - NO FILTERING, plot EVERYTHING including negative values
        set_data = []
        for i in set_indices:
            if i < len(timestamps) and i < len(resistances):
                # Plot ALL values, including negative ones - no filtering!
                set_data.append((timestamps[i], resistances[i]))
        
        reset_data = []
        for i in reset_indices:
            if i < len(timestamps) and i < len(resistances):
                # Plot ALL values, including negative ones - no filtering!
                reset_data.append((timestamps[i], resistances[i]))
        
        if set_data:
            set_times, set_res = zip(*set_data)
            gui.ax.plot(set_times, set_res, 'o-', color='blue', markersize=5, 
                       linewidth=2, label='SET (after SET pulse)', alpha=0.8)
        
        if reset_data:
            reset_times, reset_res = zip(*reset_data)
            gui.ax.plot(reset_times, reset_res, 's-', color='red', markersize=5, 
                       linewidth=2, label='RESET (after RESET pulse)', alpha=0.8)
        
        if set_data or reset_data:
            gui.ax.legend(loc='best')
            # Set labels and title
            gui.ax.set_xlabel('Time (s)')
            gui.ax.set_ylabel('Resistance (Ω)')
            gui.ax.set_title(gui.last_results['test_name'])
            gui.ax.grid(True, alpha=0.3)
            
            # Use appropriate scale - if all positive use log, otherwise use linear or symlog
            all_res = [r for _, r in set_data] + [r for _, r in reset_data]
            if all_res:
                min_r = min(all_res)
                max_r = max(all_res)
                # If we have negative values, use linear or symlog
                if min_r < 0 or max_r < 0:
                    # Has negative values - use linear scale
                    gui.ax.set_yscale('linear')
                elif min_r > 0:
                    # All positive - use log scale
                    gui.ax.set_yscale('log')
                else:
                    # Mixed or zero - use symlog
                    gui.ax.set_yscale('symlog', linthresh=1e-6)
    else:
        # Default plotting for other tests
        gui.ax.plot(valid_times, valid_resistances, 'o-', markersize=3)
    
    # Add red dotted line for potentiation/depression tests with post-reads
    if test_name in ["Potentiation Only", "Depression Only"]:
        num_post_reads = params.get('num_post_reads', 0)
        if num_post_reads > 0:
            num_pulses = params.get('num_pulses', 30)
            # Pattern: initial read (idx 0) + num_pulses pulse+read pairs (idx 1 to num_pulses)
            # Post-reads start at idx num_pulses + 1
            # Find the timestamp where pulses end (right after the last pulse read)
            pulse_end_idx = num_pulses  # Index of last pulse read (idx 0 is initial, 1-N are pulse reads)
            if pulse_end_idx < len(timestamps):
                pulse_end_time = timestamps[pulse_end_idx]
                gui.ax.axvline(x=pulse_end_time, color='red', linestyle='--', 
                               linewidth=2, alpha=0.7, label='Pulses End → Post-reads Start')
                gui.ax.legend()
    
    gui.ax.set_xlabel('Time (s)')
    gui.ax.set_ylabel('Resistance (Ω)')
    gui.ax.set_title(gui.last_results['test_name'])
    gui.ax.grid(True, alpha=0.3)
    
    # Refresh canvas for real-time updates
    # gui.canvas.draw() - caller does it
    
    # Use log scale only if all values are positive, otherwise use symlog or linear
    if valid_resistances:
        min_r = min(valid_resistances)
        max_r = max(valid_resistances)
        if min_r > 0:
            # All positive - use log scale
            gui.ax.set_yscale('log')
        elif max_r < 0:
            # All negative - use symlog to handle negative values properly
            # symlog can handle negative values with a linear threshold near zero
            gui.ax.set_yscale('symlog', linthresh=abs(max_r) * 1e-3 if abs(max_r) > 0 else 1e-6)
        else:
            # Mixed positive/negative - use symlog (symmetrical log)
            gui.ax.set_yscale('symlog', linthresh=1e-6)
    
def _plot_range_finder(gui):
    """Plot resistance vs current range"""
    range_values = gui.last_results.get('range_values', [])
    resistances = gui.last_results['resistances']
    range_stats = gui.last_results.get('range_stats', [])
    recommended_range = gui.last_results.get('recommended_range', None)
    
    if not range_values or len(range_values) != len(resistances):
        # Fallback to time series if no range data
        _plot_time_series(gui)
        return
    
    # Group data by range
    unique_ranges = []
    for r in range_values:
        if r not in unique_ranges:
            unique_ranges.append(r)
    
    # Sort ranges for proper x-axis ordering
    unique_ranges = sorted(unique_ranges, reverse=True)  # Largest to smallest
    
    # Create color map
    colors = plt.cm.viridis(np.linspace(0, 1, len(unique_ranges)))
    
    # Plot each range group
    for idx, range_val in enumerate(unique_ranges):
        # Find all measurements for this range
        range_indices = [i for i, r in enumerate(range_values) if r == range_val]
        range_resistances = [resistances[i] for i in range_indices]
        
        # Use range index for x-axis position
        x_pos = len(unique_ranges) - idx  # Reverse order for display
        x_positions = [x_pos] * len(range_resistances)
        
        # Plot with some jitter for visibility
        x_jittered = [x + np.random.uniform(-0.1, 0.1) for x in x_positions]
        
        label = f"{range_val*1e6:.1f} µA"
        if range_val == recommended_range:
            label += " (★ Recommended)"
        
        gui.ax.scatter(x_jittered, range_resistances, 
                      color=colors[idx], alpha=0.6, s=30,
                      label=label)
    
    # Set x-axis with range labels
    gui.ax.set_xticks(range(1, len(unique_ranges) + 1))
    gui.ax.set_xticklabels([f"{r*1e6:.1f} µA" for r in unique_ranges], 
                            rotation=45, ha='right')
    gui.ax.set_xlabel('Current Measurement Range (µA)', fontsize=11)
    gui.ax.set_ylabel('Resistance (Ω)', fontsize=11)
    gui.ax.set_title(f"{gui.last_results['test_name']}\nResistance vs Measurement Range", 
                     fontsize=12, fontweight='bold')
    gui.ax.set_yscale('log')
    gui.ax.grid(True, alpha=0.3)
    gui.ax.legend(loc='best', fontsize=9)
    
    # Highlight recommended range
    if recommended_range:
        rec_idx = unique_ranges.index(recommended_range)
        rec_x = len(unique_ranges) - rec_idx
        gui.ax.axvline(x=rec_x, color='red', linestyle='--', 
                       alpha=0.5, linewidth=2, label='Recommended')
    
def _plot_width_sweep(gui):
    """Plot resistance vs pulse number for each width"""
    widths = gui.last_results.get('pulse_widths', [])
    resistances = gui.last_results['resistances']
    
    if not widths or len(widths) != len(resistances):
        # Fallback to basic plot if data structure is unexpected
        gui.ax.plot(resistances, 'o-', markersize=4)
        gui.ax.set_xlabel('Measurement Number')
        gui.ax.set_ylabel('Resistance (Ω)')
        gui.ax.set_title(gui.last_results['test_name'])
        gui.ax.set_yscale('log')
        gui.ax.grid(True, alpha=0.3)
        return
    
    # Group data by width
    unique_widths = []
    for w in widths:
        if w not in unique_widths:
            unique_widths.append(w)
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(unique_widths)))
    
    for idx, width in enumerate(unique_widths):
        # Find all measurements for this width
        width_indices = [i for i, w in enumerate(widths) if w == width]
        width_resistances = [resistances[i] for i in width_indices]
        pulse_numbers = list(range(1, len(width_resistances) + 1))
        
        # Plot this width
        gui.ax.plot(pulse_numbers, width_resistances, 
                    'o-', color=colors[idx], 
                    label=f'{width*1e6:.1f} µs',
                    markersize=6, linewidth=2, alpha=0.8)
    
    gui.ax.set_xlabel('Pulse Number', fontsize=11)
    gui.ax.set_ylabel('Resistance (Ω)', fontsize=11)
    gui.ax.set_title(f'{gui.last_results["test_name"]}\nResistance Evolution per Width', 
                     fontsize=12, fontweight='bold')
    gui.ax.set_yscale('log')
    gui.ax.legend(title='Pulse Width', loc='best', fontsize=9)
    gui.ax.grid(True, alpha=0.3, linestyle='--')
    
    # Add subtle background for initial read if visible
    if len(unique_widths) > 0:
        gui.ax.axvline(x=0.5, color='gray', linestyle=':', alpha=0.3, label='Initial Read')
    
def _plot_pot_dep_cycle(gui):
    """Plot potentiation-depression cycle showing all cycles separately"""
    phases = gui.last_results.get('phase', [])
    timestamps = gui.last_results.get('timestamps', [])
    resistances = gui.last_results.get('resistances', [])
    params = gui.last_results.get('params', {})
    num_cycles = params.get('num_cycles', 1)
    steps = params.get('steps', 20)
    
    if not phases or not timestamps or not resistances:
        gui.ax.text(0.5, 0.5, "No data to plot", ha='center', va='center')
        return
    
    # Calculate steps per cycle (potentiation + depression)
    steps_per_cycle = steps * 2
    
    # Plot each cycle separately with distinct colors
    colors = plt.cm.tab10(np.linspace(0, 1, max(num_cycles, 1)))
    
    # Skip initial read (idx 0)
    for cycle in range(num_cycles):
        cycle_start_idx = 1 + (cycle * steps_per_cycle)
        cycle_end_idx = 1 + ((cycle + 1) * steps_per_cycle)
        
        if cycle_start_idx >= len(phases):
            break
        
        # Get indices for this cycle
        cycle_indices = list(range(cycle_start_idx, min(cycle_end_idx, len(phases))))
        
        # Separate potentiation and depression for this cycle
        pot_indices_cycle = [i for i in cycle_indices if i < len(phases) and phases[i] == 'potentiation']
        dep_indices_cycle = [i for i in cycle_indices if i < len(phases) and phases[i] == 'depression']
        
        # Plot potentiation for this cycle
        if pot_indices_cycle:
            pot_times = [timestamps[i] for i in pot_indices_cycle]
            pot_res = [resistances[i] for i in pot_indices_cycle]
            label = f'Cycle {cycle+1}: Potentiation' if num_cycles > 1 else 'Potentiation (SET)'
            gui.ax.plot(pot_times, pot_res, 'o-', color=colors[cycle % len(colors)], 
                       markersize=4, linewidth=2, alpha=0.8, label=label)
        
        # Plot depression for this cycle
        if dep_indices_cycle:
            dep_times = [timestamps[i] for i in dep_indices_cycle]
            dep_res = [resistances[i] for i in dep_indices_cycle]
            label = f'Cycle {cycle+1}: Depression' if num_cycles > 1 else 'Depression (RESET)'
            # Use darker shade of same color for depression
            dep_color = plt.cm.Reds(0.6 + (cycle % len(colors)) * 0.3)
            gui.ax.plot(dep_times, dep_res, 's-', color=dep_color, 
                       markersize=4, linewidth=2, alpha=0.8, label=label)
    
    # Plot initial read if present
    if len(phases) > 0 and phases[0] == 'initial':
        gui.ax.plot(timestamps[0], resistances[0], 'o', color='blue', 
                    markersize=8, label='Initial Read', zorder=5)
    
    gui.ax.set_xlabel('Time (s)', fontsize=11)
    gui.ax.set_ylabel('Resistance (Ω)', fontsize=11)
    title = f'{gui.last_results["test_name"]}'
    if num_cycles > 1:
        title += f' - {num_cycles} Cycles'
    gui.ax.set_title(title, fontsize=12, fontweight='bold')
    gui.ax.legend(loc='best', fontsize=9, ncol=2 if num_cycles > 1 else 1)
    gui.ax.grid(True, alpha=0.3)
    gui.ax.set_yscale('log')
    
def _plot_endurance(gui):
    """Plot endurance test (SET/RESET cycles)"""
    operations = gui.last_results.get('operation', [])
    cycle_numbers = gui.last_results.get('cycle_number', list(range(len(gui.last_results['resistances']))))
    
    set_idx = [i for i, op in enumerate(operations) if op == 'SET']
    reset_idx = [i for i, op in enumerate(operations) if op == 'RESET']
    
    if set_idx:
        gui.ax.plot([cycle_numbers[i] for i in set_idx],
                    [gui.last_results['resistances'][i] for i in set_idx],
                    'o', label='SET (LRS)', color='green', markersize=3)
    if reset_idx:
        gui.ax.plot([cycle_numbers[i] for i in reset_idx],
                    [gui.last_results['resistances'][i] for i in reset_idx],
                    'o', label='RESET (HRS)', color='red', markersize=3)
    
    gui.ax.set_xlabel('Cycle Number')
    gui.ax.set_ylabel('Resistance (Ω)')
    gui.ax.set_title(f'{gui.last_results["test_name"]} - Endurance')
    gui.ax.legend()
    gui.ax.grid(True, alpha=0.3)
    gui.ax.set_yscale('log')
    
def _plot_relaxation(gui):
    """Plot relaxation measurements (old plot type for backward compatibility)"""
    gui.ax.plot(gui.last_results['timestamps'], 
                 gui.last_results['resistances'], 'o-', markersize=4)
    gui.ax.set_xlabel('Time (s)')
    gui.ax.set_ylabel('Resistance (Ω)')
    gui.ax.set_title(f'{gui.last_results["test_name"]} - Relaxation')
    gui.ax.grid(True, alpha=0.3)
    
    # Only set log scale if there are positive values
    resistances = gui.last_results.get('resistances', [])
    valid_resistances = [r for r in resistances if r > 0 and not (r == float('inf') or r != r)]
    if valid_resistances:
        gui.ax.set_yscale('log')
    
    # Mark initial read and pulse/read transitions if possible
    gui.ax.axvline(x=gui.last_results['timestamps'][0], color='blue', 
                    linestyle='--', alpha=0.3, label='Initial Read')
    
def _plot_relaxation_reads(gui):
    """Plot read number vs resistance for relaxation_after_multi_pulse - raw data"""
    resistances = gui.last_results['resistances']
    params = gui.last_results.get('params', {})
    num_pulses = params.get('num_pulses', 10)
    
    # First measurement is initial read (pulse 0), then num_reads after pulses
    pulse_numbers = list(range(len(resistances)))
    
    # Filter only NaN/inf, keep all other values including zeros and negatives
    valid_data = [(i, r) for i, r in zip(pulse_numbers, resistances) 
                 if r is not None and not (math.isnan(r) or math.isinf(r))]
    
    if valid_data:
        valid_indices, valid_resistances = zip(*valid_data)
        gui.ax.plot(valid_indices, valid_resistances, 'o-', markersize=6, linewidth=2)
    
    gui.ax.set_xlabel('Read Number (0 = before pulses)')
    gui.ax.set_ylabel('Resistance (Ω)')
    gui.ax.set_title(f'{gui.last_results["test_name"]}\nAfter {num_pulses} pulses')
    gui.ax.grid(True, alpha=0.3)
    
    # Use appropriate scale based on data
    if valid_data:
        min_r = min(valid_resistances)
        max_r = max(valid_resistances)
        if min_r > 0:
            gui.ax.set_yscale('log')
        elif max_r < 0:
            gui.ax.set_yscale('log')
        else:
            gui.ax.set_yscale('symlog', linthresh=1e-6)
    
    # Mark the transition from initial read to post-pulse reads
    gui.ax.axvline(x=0.5, color='red', linestyle='--', alpha=0.5, label=f'{num_pulses} pulses here')
    gui.ax.legend()
    
def _plot_relaxation_all(gui):
    """Plot measurement number vs resistance for relaxation_after_multi_pulse_with_pulse_measurement"""
    resistances = gui.last_results['resistances']
    voltages = gui.last_results['voltages']
    params = gui.last_results.get('params', {})
    num_pulses = params.get('num_pulses', 10)
    read_voltage = params.get('read_voltage', 0.2)
    pulse_voltage = params.get('pulse_voltage', 1.5)
    
    # Separate into reads vs pulse measurements
    # Pattern: measurement 0 = initial read, 1 to num_pulses = pulse peaks, rest = reads
    measurement_nums = []
    read_resistances = []
    pulse_resistances = []
    
    for i, (r, v) in enumerate(zip(resistances, voltages)):
        measurement_nums.append(i)
        
        # Use position-based logic (more robust than voltage comparison)
        if i == 0:
            # Initial read
            read_resistances.append(r)
            pulse_resistances.append(None)
        elif i <= num_pulses:
            # Pulse peak measurement
            read_resistances.append(None)
            pulse_resistances.append(r)
        else:
            # Post-pulse read
            read_resistances.append(r)
            pulse_resistances.append(None)
    
    # Separate data into separate lists for plotting (filter out None and NaN/Inf only)
    read_meas_nums = [i for i, r in zip(measurement_nums, read_resistances) 
                     if r is not None and not (isinstance(r, float) and (math.isnan(r) or math.isinf(r)))]
    read_vals = [r for r in read_resistances 
                if r is not None and not (isinstance(r, float) and (math.isnan(r) or math.isinf(r)))]
    
    pulse_meas_nums = [i for i, p in zip(measurement_nums, pulse_resistances) 
                      if p is not None and not (isinstance(p, float) and (math.isnan(p) or math.isinf(p)))]
    pulse_vals = [p for p in pulse_resistances 
                 if p is not None and not (isinstance(p, float) and (math.isnan(p) or math.isinf(p)))]
    
    # Debug output
    print(f"Plotting: {len(read_vals)} reads at indices {read_meas_nums[:5]}...")
    print(f"Plotting: {len(pulse_vals)} pulse peaks at indices {pulse_meas_nums[:5]}...")
    
    # Plot both with different styles (no lines, just markers for clarity)
    if read_vals:
        gui.ax.plot(read_meas_nums, read_vals, 'o', markersize=6, 
                    label=f'Reads ({len(read_vals)})', color='blue')
    if pulse_vals:
        gui.ax.plot(pulse_meas_nums, pulse_vals, 's', markersize=7, 
                    label=f'Pulse Peaks ({len(pulse_vals)})', color='red', alpha=0.8)
    
    gui.ax.set_xlabel('Measurement Number (0 = initial read)')
    gui.ax.set_ylabel('Resistance (Ω)')
    gui.ax.set_title(f'{gui.last_results["test_name"]}\n{num_pulses} pulses @ {pulse_voltage}V with peak measurements')
    gui.ax.grid(True, alpha=0.3)
    
    # Use appropriate scale based on data
    all_vals = read_vals + pulse_vals
    if all_vals:
        min_r = min(all_vals)
        max_r = max(all_vals)
        if min_r > 0:
            gui.ax.set_yscale('log')
        elif max_r < 0:
            gui.ax.set_yscale('log')
        else:
            gui.ax.set_yscale('symlog', linthresh=1e-6)
    
    gui.ax.legend()
    
    # Mark the transition points
    gui.ax.axvline(x=0.5, color='green', linestyle='--', alpha=0.3, label='Start')
    gui.ax.axvline(x=num_pulses + 0.5, color='orange', linestyle='--', alpha=0.3, label='Post-pulse reads')
    
def _plot_voltage_sweep(gui):
    """Plot resistance vs pulse number for each voltage"""
    pulse_voltages = gui.last_results.get('pulse_voltages', [])
    resistances = gui.last_results['resistances']
    
    if not pulse_voltages or len(pulse_voltages) != len(resistances):
        # Fallback to basic plot
        _plot_time_series(gui)
        return
    
    # Group data by pulse voltage
    unique_voltages = []
    for v in pulse_voltages:
        if v not in unique_voltages:
            unique_voltages.append(v)
    
    colors = plt.cm.plasma(np.linspace(0, 1, len(unique_voltages)))
    params = gui.last_results.get('params', {})
    num_pulses_per_voltage = params.get('num_pulses_per_voltage', 5)
    
    for idx, voltage in enumerate(unique_voltages):
        # Find all measurements for this voltage
        voltage_indices = [i for i, v in enumerate(pulse_voltages) if v == voltage]
        voltage_resistances = [resistances[i] for i in voltage_indices]
        pulse_numbers = list(range(1, len(voltage_resistances) + 1))
        
        # Plot this voltage
        gui.ax.plot(pulse_numbers, voltage_resistances, 
                    'o-', color=colors[idx], 
                    label=f'{voltage:.2f}V',
                    markersize=6, linewidth=2, alpha=0.8)
    
    gui.ax.set_xlabel('Pulse Number', fontsize=11)
    gui.ax.set_ylabel('Resistance (Ω)', fontsize=11)
    gui.ax.set_title(f'{gui.last_results["test_name"]}\nResistance Evolution per Voltage', 
                     fontsize=12, fontweight='bold')
    gui.ax.set_yscale('log')
    gui.ax.legend(title='Pulse Voltage', loc='best', fontsize=9)
    gui.ax.grid(True, alpha=0.3, linestyle='--')
    
def _plot_ispp(gui):
    """Plot ISPP: Resistance vs Pulse Number with voltage annotation"""
    pulse_voltages = gui.last_results.get('pulse_voltages', [])
    resistances = gui.last_results['resistances']
    timestamps = gui.last_results.get('timestamps', [])
    
    if not pulse_voltages or len(pulse_voltages) != len(resistances):
        # Fallback to basic plot
        _plot_time_series(gui)
        return
    
    # Plot resistance vs pulse number
    pulse_numbers = list(range(len(resistances)))
    
    # Color by voltage (gradual increase)
    if len(pulse_voltages) > 1:
        scatter = gui.ax.scatter(pulse_numbers, resistances, 
                                 c=pulse_voltages, cmap='viridis',
                                 s=50, alpha=0.7, edgecolors='black', linewidth=0.5)
        cbar = plt.colorbar(scatter, ax=gui.ax)
        cbar.set_label('Pulse Voltage (V)', fontsize=10)
    else:
        gui.ax.plot(pulse_numbers, resistances, 'o-', markersize=6, linewidth=2)
    
    gui.ax.set_xlabel('Pulse Number', fontsize=11)
    gui.ax.set_ylabel('Resistance (Ω)', fontsize=11)
    gui.ax.set_title(f'{gui.last_results["test_name"]}\nIncremental Step Pulse Programming', 
                     fontsize=12, fontweight='bold')
    gui.ax.set_yscale('log')
    gui.ax.grid(True, alpha=0.3, linestyle='--')
    
def _plot_threshold(gui):
    """Plot switching threshold: Resistance vs Pulse Voltage"""
    pulse_voltages = gui.last_results.get('pulse_voltages', [])
    resistances = gui.last_results['resistances']
    direction = gui.last_results.get('direction', 'set')
    
    if not pulse_voltages or len(pulse_voltages) != len(resistances):
        # Fallback to basic plot
        _plot_time_series(gui)
        return
    
    # Group by voltage and average resistance for each voltage
    voltage_groups = {}
    for v, r in zip(pulse_voltages, resistances):
        if v != 0.0:  # Skip initial read (voltage = 0)
            if v not in voltage_groups:
                voltage_groups[v] = []
            voltage_groups[v].append(r)
    
    # Calculate mean resistance for each voltage
    unique_voltages = sorted(voltage_groups.keys())
    mean_resistances = [np.mean(voltage_groups[v]) for v in unique_voltages]
    std_resistances = [np.std(voltage_groups[v]) for v in unique_voltages]
    
    # Plot with error bars
    gui.ax.errorbar(unique_voltages, mean_resistances, yerr=std_resistances,
                    fmt='o-', markersize=8, linewidth=2, capsize=5,
                    label=f'{direction.upper()} Threshold Test')
    
    gui.ax.set_xlabel('Pulse Voltage (V)', fontsize=11)
    gui.ax.set_ylabel('Resistance (Ω)', fontsize=11)
    gui.ax.set_title(f'{gui.last_results["test_name"]}\nSwitching Threshold ({direction.upper()})', 
                     fontsize=12, fontweight='bold')
    gui.ax.set_yscale('log')
    gui.ax.grid(True, alpha=0.3, linestyle='--')
    gui.ax.legend()
    
def _plot_multilevel(gui):
    """Plot multilevel programming: Resistance vs Pulse Number for each level"""
    target_levels = gui.last_results.get('target_levels', [])
    resistances = gui.last_results['resistances']
    
    if not target_levels or len(target_levels) != len(resistances):
        # Fallback to basic plot
        _plot_time_series(gui)
        return
    
    # Group data by target level
    unique_levels = []
    for l in target_levels:
        if l not in unique_levels:
            unique_levels.append(l)
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(unique_levels)))
    params = gui.last_results.get('params', {})
    num_pulses_per_level = params.get('num_pulses_per_level', 5)
    
    for idx, level in enumerate(unique_levels):
        # Find all measurements for this level
        level_indices = [i for i, l in enumerate(target_levels) if l == level]
        level_resistances = [resistances[i] for i in level_indices]
        pulse_numbers = list(range(1, len(level_resistances) + 1))
        
        # Plot this level
        gui.ax.plot(pulse_numbers, level_resistances, 
                    'o-', color=colors[idx], 
                    label=f'Level {level}',
                    markersize=6, linewidth=2, alpha=0.8)
    
    gui.ax.set_xlabel('Pulse Number', fontsize=11)
    gui.ax.set_ylabel('Resistance (Ω)', fontsize=11)
    gui.ax.set_title(f'{gui.last_results["test_name"]}\nMultilevel Programming', 
                     fontsize=12, fontweight='bold')
    gui.ax.set_yscale('log')
    gui.ax.legend(title='Target Level', loc='best', fontsize=9)
    gui.ax.grid(True, alpha=0.3, linestyle='--')
    
def _plot_pulse_train(gui):
    """Plot pulse train with varying amplitudes: Resistance vs Pulse Number"""
    pulse_voltages = gui.last_results.get('pulse_voltages', [])
    resistances = gui.last_results['resistances']
    timestamps = gui.last_results.get('timestamps', [])
    
    if not pulse_voltages or len(pulse_voltages) != len(resistances):
        # Fallback to basic plot
        _plot_time_series(gui)
        return
    
    # Plot resistance vs pulse number
    pulse_numbers = list(range(len(resistances)))
    
    # Color by voltage (showing the pattern)
    if len(pulse_voltages) > 1:
        # Use a diverging colormap for positive/negative voltages
        scatter = gui.ax.scatter(pulse_numbers, resistances, 
                                 c=pulse_voltages, cmap='RdBu_r',
                                 s=50, alpha=0.7, edgecolors='black', linewidth=0.5)
        cbar = plt.colorbar(scatter, ax=gui.ax)
        cbar.set_label('Pulse Voltage (V)', fontsize=10)
    else:
        gui.ax.plot(pulse_numbers, resistances, 'o-', markersize=6, linewidth=2)
    
    gui.ax.set_xlabel('Pulse Number', fontsize=11)
    gui.ax.set_ylabel('Resistance (Ω)', fontsize=11)
    gui.ax.set_title(f'{gui.last_results["test_name"]}\nPulse Train with Varying Amplitudes', 
                     fontsize=12, fontweight='bold')
    gui.ax.set_yscale('log')
    gui.ax.grid(True, alpha=0.3, linestyle='--')
