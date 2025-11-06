"""
TEST #1: VARYING PULSE WIDTH
=============================

Sweep pulse width from short to long and measure resistance response.

Purpose:
--------
- Find optimal pulse width for SET/RESET operations
- Understand speed/energy trade-offs
- Measure switching time constants
- Determine minimum width for reliable switching

Pulse Sequence (per width point):
----------------------------------
                    
       RESET   read      TEST         SETTLING      READ x3
     -2V, 1ms  read  +Vtest, Xµs   10ms wait     +0.5V, 10µs
      │        read    │            │             │ │ │
      │        read    │            │             │ │ │
      └─► HRS  read    └─► SET?     └─► Stable   └─┴─┴─► R_final
    
    ◄─ Baseline  ◄100ms─►    ◄──────10ms──────────────►
                  wait                 wait
    
    Measure: ΔR = R_final - R₀

Method:
-------
1. Measure initial resistance (baseline)
2. RESET device to HRS (high resistance state)
3. Apply test pulse with specific width
4. Wait for settling
5. Measure final resistance with read pulses
6. Repeat for all widths (logarithmic spacing)

Based on: Working_Examples/Single Channel/Width_Sweep_Pulse_read_After/Varying_Pulse_Width_FIXED.py
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import time
from datetime import datetime

# Add root directory to path (2 levels up)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ProxyClass import Proxy

# Note: Base class moved to Automation folder and has issues
# This script is standalone


class VaryingWidthTest:
    """Varying width test implementation - standalone."""
    
    def __init__(self, ip="192.168.0.10", pmu_id="PMU1", channel=1, data_dir="Memristor_Tests/data"):
        """Initialize PMU."""
        self.ip = ip
        self.pmu_id = pmu_id
        self.channel = channel
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        print("="*70)
        print("MEMRISTOR TESTER - Varying Width Test")
        print("="*70)
        print(f"IP:      {ip}")
        print(f"PMU:     {pmu_id}")
        print(f"Channel: {channel}")
        print()
        
        # Connect to PMU
        print("Connecting to PMU...")
        self.lpt = Proxy(ip, 8888, "lpt")
        self.param = Proxy(ip, 8888, "param")
        
        self.lpt.initialize()
        self.lpt.tstsel(1)
        self.lpt.devint()
        self.card_id = self.lpt.getinstid(pmu_id)
        self.lpt.setmode(self.card_id, self.param.KI_LIM_MODE, self.param.KI_VALUE)
        
        print(f"[OK] Connected to {pmu_id}\n")
        
        # Configure RPM
        try:
            self.lpt.rpm_config(self.card_id, channel,
                               self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
            print(f"[OK] RPM configured\n")
        except Exception as e:
            print(f"[WARNING] RPM: {e}\n")
    
    def test_varying_width(self,
                          # Sweep parameters
                          start_width=1e-6,      # 1µs
                          stop_width=100e-6,     # 100µs
                          points=20,
                          
                          # Test pulse parameters
                          test_amplitude=1.0,    # SET voltage
                          
                          # Reset pulse parameters
                          reset_amplitude=-2.0,  # RESET voltage
                          reset_width=1e-3,      # 1ms
                          
                          # Read parameters
                          read_voltage=-0.2,
                          read_width=10e-6,
                          read_count=1,
                          
                          # Timing
                          settling_time= 0, # 10e-3,   # 10ms
                          
                          i_range = 0.0001,
                          # Options
                          measure_test_current=False,  # Measure current at test pulse peak (can affect measurements)
                          verbose=True,
                          plot=True,
                          test_mode=False):
        """
        Test varying pulse width.
        
        Args:
            start_width: Starting pulse width (s)
            stop_width: Ending pulse width (s)
            points: Number of points in sweep
            test_amplitude: Test pulse voltage (V)
            reset_amplitude: Reset pulse voltage (V)
            reset_width: Reset pulse width (s)
            read_voltage: Read pulse voltage (V)
            read_width: Read pulse width (s)
            read_count: Number of read pulses to average
            settling_time: Wait time after test pulse (s)
            i_range: Current range (A)
            measure_test_current: If True, measure V/I at test pulse peak (may affect device state)
            verbose: Print progress
            plot: Show plot at end
            test_mode: If True, save plot without showing (non-interactive)
            
        Returns:
            Dictionary with test results
        """
        
        if verbose:
            print("="*70)
            print("TEST #1: VARYING PULSE WIDTH")
            print("="*70)
            print(f"Width range:    {start_width*1e6:.2f} to {stop_width*1e6:.2f} µs")
            print(f"Points:         {points}")
            print(f"Test voltage:   {test_amplitude} V")
            print(f"Reset voltage:  {reset_amplitude} V")
            print(f"Read voltage:   {read_voltage} V")
            print(f"Settling time:  {settling_time*1e3:.1f} ms")
            
            # Warn about pulse width limitations
            MIN_WIDTH_NS = 220  # 220ns hardware minimum
            MAX_WIDTH_MS = 833  # 833ms maximum (period <= 1s constraint)
            
            if start_width < MIN_WIDTH_NS * 1e-9:
                print(f"\n[WARNING] PMU minimum pulse width: {MIN_WIDTH_NS}ns")
                print(f"          Pulses < {MIN_WIDTH_NS}ns will be clamped to {MIN_WIDTH_NS}ns")
                print(f"          (Limited by rise/fall time: 100ns + 100ns + 20ns)")
                print(f"\n[NOTE]    For pulses < {MIN_WIDTH_NS}ns without data capture,")
                print(f"          use the 10ns pulse mode (no current measurement)")
            
            if stop_width > MAX_WIDTH_MS * 1e-3:
                print(f"\n[WARNING] PMU maximum pulse width: ~{MAX_WIDTH_MS}ms")
                print(f"          Pulses > {MAX_WIDTH_MS}ms may fail (period > 1s limit)")
                print(f"          Consider capping stop_width at {MAX_WIDTH_MS}ms")
            
            print("="*70)
            print()
        
        # Generate logarithmic width sweep
        widths = np.logspace(np.log10(start_width), np.log10(stop_width), points)
        
        resistances_initial = []    # Initial (baseline) resistance
        resistances_initial_std = []
        resistances_final = []      # Final resistance after test pulse
        resistances_final_std = []
        all_measurements_initial = []
        all_measurements_final = []
        currents_initial = []
        currents_initial_std = []
        currents_final = []
        currents_final_std = []
        all_currents_initial = []
        all_currents_final = []
        test_pulse_currents = []    # Current at peak of test pulse
        test_pulse_voltages = []    # Voltage at peak of test pulse
        
        # Initialize pulse mode ONCE
        v_range = 10.0
        #i_range = 0.00001
        self.lpt.pg2_init(self.card_id, self.param.PULSE_MODE_PULSE)
        self.lpt.pulse_ranges(self.card_id, self.channel,
                             v_range, self.param.PULSE_MEAS_FIXED, v_range,
                             self.param.PULSE_MEAS_FIXED, i_range)
        
        start_time = time.time()
        
        for i, width in enumerate(widths):
            if verbose:
                print(f"[{i+1}/{points}] Width: {width*1e6:.2f} µs")

            # 1. RESET pulse - put device in HRS
            if verbose:
                print("  RESET...")
            self._apply_pulse(reset_amplitude, reset_width, v_range, i_range)
            time.sleep(0.1)  # Wait after reset

            
            # 2. INITIAL READ - measure baseline resistance
            if verbose:
                print("  Initial read (baseline)...")
            r_init, r_init_std, r_init_indiv, i_init, i_init_std, i_init_indiv, v_init, v_init_indiv = self._measure_resistance(
                read_voltage, read_width, read_count, v_range, i_range, verbose=False
            )
            resistances_initial.append(r_init)
            resistances_initial_std.append(r_init_std)
            all_measurements_initial.append(r_init_indiv)
            currents_initial.append(i_init)
            currents_initial_std.append(i_init_std)
            all_currents_initial.append(i_init_indiv)
            if verbose:
                print(f"    R0 = {r_init/1e3:.2f} +/- {r_init_std/1e3:.2f} kOhm, I = {i_init*1e6:.3f} uA")
            
            
            
            # 3. Apply test pulse with this width and optionally measure current at peak
            if verbose:
                print(f"  TEST pulse ({width*1e6:.2f}µs)...")
            v_test, i_test = self._apply_pulse(test_amplitude, width, v_range, i_range, measure_current=measure_test_current)
            test_pulse_voltages.append(v_test if v_test is not None else np.nan)
            test_pulse_currents.append(i_test if i_test is not None else np.nan)
            if verbose and i_test is not None and measure_test_current:
                print(f"    Peak: V={v_test:.3f}V, I={i_test*1e3:.3f}mA")
            
            # 4. Settling time
            if verbose:
                print(f"  Settling...")
            time.sleep(settling_time)
            
            # 5. Measure final resistance
            if verbose:
                print("  Final read...")
            r_final, r_final_std, r_final_indiv, i_final, i_final_std, i_final_indiv, v_final, v_final_indiv = self._measure_resistance(
                read_voltage, read_width, read_count, v_range, i_range, verbose=False
            )
            resistances_final.append(r_final)
            resistances_final_std.append(r_final_std)
            all_measurements_final.append(r_final_indiv)
            currents_final.append(i_final)
            currents_final_std.append(i_final_std)
            all_currents_final.append(i_final_indiv)
            
            # Calculate change
            delta_r = r_final - r_init
            if verbose:
                print(f"    R_final = {r_final/1e3:.2f} +/- {r_final_std/1e3:.2f} kOhm")
                print(f"    Delta_R = {delta_r/1e3:+.2f} kOhm")
            
            if verbose:
                print()
            # sleep 1s to "cool down" the device
            time.sleep(1)
        
        elapsed = time.time() - start_time
        
        if verbose:
            print("="*70)
            print(f"Test complete! Elapsed time: {elapsed:.1f}s")
            print("="*70)
            print()
        
        # Prepare results
        delta_r = np.array(resistances_final) - np.array(resistances_initial)
        
        results = {
            'width_us': widths * 1e6,
            'width_s': widths,
            'resistance_initial_ohm': resistances_initial,
            'resistance_initial_kohm': np.array(resistances_initial) / 1e3,
            'resistance_initial_std_ohm': resistances_initial_std,
            'resistance_initial_std_kohm': np.array(resistances_initial_std) / 1e3,
            'resistance_final_ohm': resistances_final,
            'resistance_final_kohm': np.array(resistances_final) / 1e3,
            'resistance_final_std_ohm': resistances_final_std,
            'resistance_final_std_kohm': np.array(resistances_final_std) / 1e3,
            'delta_r_ohm': delta_r,
            'delta_r_kohm': delta_r / 1e3,
            'test_amplitude': test_amplitude,
            'reset_amplitude': reset_amplitude,
            'read_voltage': read_voltage,
            'settling_time': settling_time,
            'v_range': v_range,
            'i_range': i_range,
            'current_initial_mA': np.array(currents_initial) * 1e3,
            'current_final_mA': np.array(currents_final) * 1e3,
            'current_initial_std_mA': np.array(currents_initial_std) * 1e3,
            'current_final_std_mA': np.array(currents_final_std) * 1e3,
            'test_pulse_voltage_V': np.array(test_pulse_voltages),
            'test_pulse_current_mA': np.array(test_pulse_currents) * 1e3,
            'all_measurements_initial': all_measurements_initial,
            'all_measurements_final': all_measurements_final,
            'all_currents_initial': all_currents_initial,
            'all_currents_final': all_currents_final
        }
        
        # Save data with descriptive filename
        save_dir = self.data_dir / "varying_width"
        save_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create descriptive filename with key parameters
        w_start_str = f"{start_width*1e6:.0f}us" if start_width >= 1e-6 else f"{start_width*1e9:.0f}ns"
        w_stop_str = f"{stop_width*1e6:.0f}us" if stop_width >= 1e-6 else f"{stop_width*1e9:.0f}ns"
        if stop_width >= 1e-3:
            w_stop_str = f"{stop_width*1e3:.0f}ms"
        v_test_str = f"{abs(test_amplitude):.1f}V".replace('.', 'p')
        v_sign = "neg" if test_amplitude < 0 else "pos"
        
        filename = save_dir / f"width_{w_start_str}_to_{w_stop_str}_{v_sign}{v_test_str}_{points}pts_{timestamp}.csv"
        log_filename = save_dir / f"width_{w_start_str}_to_{w_stop_str}_{v_sign}{v_test_str}_{points}pts_{timestamp}.log"
        
        # Prepare CSV columns - cleaner output with test pulse current
        csv_data = {
                'Width_us': results['width_us'],
                'Width_s': results['width_s'],
            'Test_Pulse_V': results['test_pulse_voltage_V'],
            'Test_Pulse_mA': results['test_pulse_current_mA'],
            'R_Initial_kOhm': results['resistance_initial_kohm'],
            'R_Initial_Std_kOhm': results['resistance_initial_std_kohm'],
            'R_Final_kOhm': results['resistance_final_kohm'],
            'R_Final_Std_kOhm': results['resistance_final_std_kohm'],
            'Delta_R_kOhm': results['delta_r_kohm'],
            'Read_Current_Initial_mA': results['current_initial_mA'],
            'Read_Current_Final_mA': results['current_final_mA']
        }
        
        
        # Save parameter log file
        with open(log_filename, 'w') as f:
            f.write("="*70 + "\n")
            f.write("VARYING WIDTH TEST - PARAMETER LOG\n")
            f.write("="*70 + "\n\n")
            f.write(f"Test Date/Time: {timestamp}\n\n")
            
            f.write("SWEEP PARAMETERS:\n")
            f.write("-"*70 + "\n")
            f.write(f"  Start Width:         {start_width*1e6:.3f} us ({start_width*1e9:.1f} ns)\n")
            f.write(f"  Stop Width:          {stop_width*1e6:.3f} us ({stop_width*1e9:.1f} ns)\n")
            f.write(f"  Number of Points:    {points}\n")
            f.write(f"  Sweep Type:          Logarithmic\n\n")
            
            f.write("TEST PULSE PARAMETERS:\n")
            f.write("-"*70 + "\n")
            f.write(f"  Test Amplitude:      {test_amplitude:+.3f} V\n")
            f.write(f"  Settling Time:       {settling_time*1e3:.1f} ms\n\n")
            
            f.write("RESET PARAMETERS:\n")
            f.write("-"*70 + "\n")
            f.write(f"  Reset Amplitude:     {reset_amplitude:+.3f} V\n")
            f.write(f"  Reset Width:         {reset_width*1e3:.1f} ms\n")
            f.write(f"  Wait After Reset:    100 ms\n\n")
            
            f.write("READ PARAMETERS:\n")
            f.write("-"*70 + "\n")
            f.write(f"  Read Voltage:        {read_voltage:.3f} V\n")
            f.write(f"  Read Width:          {read_width*1e6:.1f} us\n")
            f.write(f"  Read Count:          {read_count}\n\n")
            
            f.write("HARDWARE SETTINGS:\n")
            f.write("-"*70 + "\n")
            f.write(f"  Voltage Range:       {v_range:.1f} V\n")
            f.write(f"  Current Range:       {i_range:.4f} A\n")
            f.write(f"  Channel:             {self.channel}\n\n")
            
            f.write("TEST RESULTS:\n")
            f.write("-"*70 + "\n")
            f.write(f"  Total Points:        {len(results['width_us'])}\n")
            f.write(f"  Elapsed Time:        {elapsed:.1f} s\n")
            f.write(f"  Avg Time/Point:      {elapsed/len(results['width_us']):.2f} s\n\n")
            
            f.write("FILES:\n")
            f.write("-"*70 + "\n")
            f.write(f"  Data CSV:  {filename}\n")
            f.write(f"  Plot PNG:  {str(filename).replace('.csv', '.png')}\n")
            f.write(f"  This Log:  {log_filename}\n\n")
            
            f.write("="*70 + "\n")
        
        print(f"[OK] Parameter log saved: {log_filename}")
        
        # Save CSV with header
        df = pd.DataFrame(csv_data)
        with open(filename, 'w') as f:
            f.write(f"# Varying Width Test Data\n")
            f.write(f"# Date: {timestamp}\n")
            f.write(f"# Width: {start_width*1e6:.2f}us to {stop_width*1e6:.2f}us ({points} points, log scale)\n")
            f.write(f"# Test Voltage: {test_amplitude:+.2f}V, Reset: {reset_amplitude:+.2f}V\n")
            f.write(f"# Read: {read_voltage}V, Settling: {settling_time*1e3:.1f}ms, Read Count: {read_count}\n")
            f.write(f"#\n")
            df.to_csv(f, index=False)
        
        print(f"[OK] Data saved: {filename}")
        print(f"[INFO] Columns: Width, Test Pulse V/I, R_Initial, R_Final, Delta_R, Read Currents")
        
        # Plot
        if plot:
            self._plot_results(results, filename, test_mode=test_mode)
        
        return results
    
    def _plot_results(self, results, data_filename, test_mode=False):
        """Plot width sweep results - 3-plot layout with test pulse current."""
        if test_mode:
            plt.ioff()
        
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14))
        
        widths = results['width_us']
        r_init = results['resistance_initial_kohm']
        r_init_std = results['resistance_initial_std_kohm']
        r_final = results['resistance_final_kohm']
        r_final_std = results['resistance_final_std_kohm']
        delta_r = results['delta_r_kohm']
        test_current = results['test_pulse_current_mA']
        
        # Plot 1: Initial vs Final Resistance
        ax1.errorbar(widths, r_init, yerr=r_init_std, fmt='o-', linewidth=2, 
                    markersize=8, capsize=5, capthick=2, color='blue',
                    label='Initial (R0)', alpha=0.7)
        ax1.errorbar(widths, r_final, yerr=r_final_std, fmt='s-', linewidth=2,
                    markersize=8, capsize=5, capthick=2, color='red',
                    label='Final (after pulse)', alpha=0.7)
        
        ax1.set_xlabel('Pulse Width (us)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Resistance (kOhm)', fontsize=12, fontweight='bold')
        ax1.set_title('Memristor Resistance vs Pulse Width', fontsize=14, fontweight='bold')
        ax1.set_xscale('log')
        ax1.grid(True, alpha=0.3, which='both')
        ax1.legend(fontsize=11)
        
        # Add parameter text
        param_text = f"Test: {results['test_amplitude']}V\n"
        param_text += f"Reset: {results['reset_amplitude']}V\n"
        param_text += f"Read: {results['read_voltage']}V\n"
        param_text += f"Settling: {results['settling_time']*1e3:.1f}ms"
        ax1.text(0.02, 0.98, param_text, transform=ax1.transAxes,
               fontsize=10, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Plot 2: Delta R (change in resistance)
        ax2.plot(widths, delta_r, 'go-', linewidth=2, markersize=8, label='Delta_R = R_final - R0')
        ax2.axhline(y=0, color='k', linestyle='--', linewidth=1, alpha=0.5)
        
        ax2.set_ylabel('Delta_R (kOhm)', fontsize=12, fontweight='bold')
        ax2.set_title('Resistance Change vs Pulse Width', fontsize=14, fontweight='bold')
        ax2.set_xscale('log')
        ax2.grid(True, alpha=0.3, which='both')
        ax2.legend(fontsize=11)
        
        # Plot 3: Test Pulse Current (at peak of pulse)
        # Only plot non-NaN values
        valid_mask = ~np.isnan(test_current)
        if np.any(valid_mask):
            ax3.plot(widths[valid_mask], test_current[valid_mask], 'mo-', 
                    linewidth=2, markersize=8, label='Peak Current (Test Pulse)')
            ax3.set_xlabel('Pulse Width (us)', fontsize=12, fontweight='bold')
            ax3.set_ylabel('Current (mA)', fontsize=12, fontweight='bold')
            ax3.set_title('Test Pulse Peak Current vs Width', fontsize=14, fontweight='bold')
            ax3.set_xscale('log')
            ax3.grid(True, alpha=0.3, which='both')
            ax3.legend(fontsize=11)
            
            # Add note if some measurements are missing
            num_missing = np.sum(~valid_mask)
            if num_missing > 0:
                ax3.text(0.98, 0.02, f'Note: {num_missing} measurements unavailable',
                       transform=ax3.transAxes, fontsize=9,
                       verticalalignment='bottom', horizontalalignment='right',
                       bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.3))
        else:
            # If no current data available, show message
            ax3.text(0.5, 0.5, 'Test pulse current not measured\n(set measure_test_current=True)',
                   transform=ax3.transAxes, fontsize=12, ha='center', va='center',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            ax3.set_xlabel('Pulse Width (us)', fontsize=12, fontweight='bold')
            ax3.set_ylabel('Current (mA)', fontsize=12, fontweight='bold')
            ax3.set_title('Test Pulse Peak Current vs Width', fontsize=14, fontweight='bold')
            ax3.set_xscale('log')
        
        plt.tight_layout()
        
        # Save plot
        plot_filename = str(data_filename).replace('.csv', '.png')
        plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
        print(f"[OK] Plot saved: {plot_filename}")
        
        if not test_mode:
            plt.show()
        else:
            plt.close(fig)
    
    def _apply_pulse(self, amplitude, width, v_range, i_range, measure_current=False):
        """Apply pulse and optionally measure current at peak.
        
        Returns:
            If measure_current=True: (v_peak, i_peak)
            If measure_current=False: (None, None)
        """
        amplitude = float(amplitude)
        width = float(width)
        
        # PMU hardware constraints for pulse timing
        # Minimum pulse width depends on rise/fall times:
        # min_width = rise_time + fall_time + 20ns
        
        if width < 1e-6:  # For pulses < 1µs, use optimized fast timing
            rise_time = 100e-9  # 100ns is practical minimum for PMU
            fall_time = 100e-9
            # Minimum achievable width: 100ns + 100ns + 20ns = 220ns
            min_width = 220e-9
            
            if width < min_width:
                # Cannot achieve requested width - clamp to minimum
                width = min_width
        else:
            # For pulses >= 1µs, use adaptive rise/fall time
            # Cap at 1µs for long pulses (no need for 50ms rise on 500ms pulse!)
            rise_time = min(1e-6, width / 10)
            fall_time = rise_time
        
        delay = 1e-7
        
        # Period calculation with maximum limit
        # PMU hardware limit: period must be <= 1 second
        if width > 100e-3:  # For pulses > 100ms
            # Use minimal overhead, max 1 second
            period = min(width * 1.2, 1.0)
        else:
            # Standard: 3x width for settling, min 1µs
            period = max(width * 3, 1e-6)
        
        self.lpt.pulse_source_timing(self.card_id, self.channel,
                                    period, delay, width, rise_time, fall_time)
        
        self.lpt.pulse_limits(self.card_id, self.channel,
                             v_range, i_range, v_range * i_range)
        
        self.lpt.pulse_sweep_linear(self.card_id, self.channel,
                                   self.param.PULSE_AMPLITUDE_SP,
                                   amplitude, amplitude, 0.0)
        
        if measure_current:
            # Enable spot mean measurement at pulse peak
            self.lpt.pulse_meas_sm(self.card_id, self.channel, 0, 1, 0, 1, 0, 1, 0)
            self.lpt.pulse_meas_timing(self.card_id, self.channel, 0.4, 0.6, 1)  # Measure at pulse center
        else:
            # No measurement
            self.lpt.pulse_meas_sm(self.card_id, self.channel, 0, 0, 0, 0, 0, 0, 0)
        
        self.lpt.pulse_output(self.card_id, self.channel, 1)
        self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
        
        # Wait for completion
        timeout = time.time() + 120
        while time.time() < timeout:
            try:
                status, elapsed = self.lpt.pulse_exec_status()
                if status != self.param.PMU_TEST_STATUS_RUNNING:
                    break
            except:
                pass
            time.sleep(0.01)
        
        v_peak = None
        i_peak = None
        
        if measure_current:
            # Fetch measurement
            buf_size = self.lpt.pulse_chan_status(self.card_id, self.channel)
            if buf_size > 0:
                v, i, ts, st = self.lpt.pulse_fetch(self.card_id, self.channel, 0, max(0, buf_size - 1))
                if len(v) > 0 and len(i) > 0:
                    v_peak = abs(v[0])
                    i_peak = abs(i[0])
        
        self.lpt.pulse_output(self.card_id, self.channel, 0)
        
        return v_peak, i_peak
    
    def _measure_resistance(self, read_v, read_w, count, v_range, i_range, verbose=False):
        """Measure resistance with read pulses - returns voltage, current, and resistance."""
        resistances = []
        currents = []
        voltages = []
        
        for _ in range(count):
            rise_time = min(1e-6, read_w / 10)  # Use min() for short pulses
            fall_time = rise_time
            delay = 1e-7
            period = max(read_w * 3, 10e-6)  # Period = 3x width, min 10µs
            
            self.lpt.pulse_source_timing(self.card_id, self.channel,
                                        period, delay, read_w, rise_time, fall_time)
            
            self.lpt.pulse_limits(self.card_id, self.channel,
                                 v_range, i_range, v_range * i_range)
            
            self.lpt.pulse_sweep_linear(self.card_id, self.channel,
                                       self.param.PULSE_AMPLITUDE_SP,
                                       read_v, read_v, 0.0)
            
            # Enable measurement
            self.lpt.pulse_meas_sm(self.card_id, self.channel, 0, 1, 0, 1, 0, 1, 0)
            self.lpt.pulse_meas_timing(self.card_id, self.channel, 0.1, 0.9, 1)
            
            self.lpt.pulse_output(self.card_id, self.channel, 1)
            self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
            
            # Wait for completion
            timeout = time.time() + 120
            while time.time() < timeout:
                try:
                    status, elapsed = self.lpt.pulse_exec_status()
                    if status != self.param.PMU_TEST_STATUS_RUNNING:
                        break
                except:
                    pass
                time.sleep(0.01)
            
            # Fetch measurement using pulse_fetch
            buf_size = self.lpt.pulse_chan_status(self.card_id, self.channel)
            if buf_size > 0:
                v, i, ts, st = self.lpt.pulse_fetch(self.card_id, self.channel, 0, max(0, buf_size - 1))
                if len(v) > 0 and len(i) > 0:
                    v_meas = v[0]
                    i_meas = i[0]
                    if abs(i_meas) > 1e-12:
                        r = abs(v_meas / i_meas)
                        resistances.append(r)
                        currents.append(abs(i_meas))
                        voltages.append(abs(v_meas))
            
            self.lpt.pulse_output(self.card_id, self.channel, 0)
        
        if len(resistances) > 0:
            r_mean = np.mean(resistances)
            r_std = np.std(resistances) if len(resistances) > 1 else 0.0
            i_mean = np.mean(currents)
            i_std = np.std(currents) if len(currents) > 1 else 0.0
            v_mean = np.mean(voltages)
            if verbose:
                print(f"  R = {r_mean/1e3:.2f} +/- {r_std/1e3:.2f} kOhm, I = {i_mean*1e6:.3f} uA")
            return r_mean, r_std, resistances, i_mean, i_std, currents, v_mean, voltages
        else:
            return np.nan, np.nan, [], np.nan, np.nan, [], np.nan, []
    
    def cleanup(self):
        """Cleanup."""
        try:
            self.lpt.pulse_output(self.card_id, 1, 0)
            self.lpt.dev_abort()
            print("\n[OK] PMU shutdown complete")
        except:
            pass


def main():
    """Standalone execution."""
    print("="*70)
    print("MEMRISTOR TEST #1: VARYING PULSE WIDTH")
    print("="*70)
    print()
    
    # Create tester
    tester = VaryingWidthTest(ip="192.168.0.10", pmu_id="PMU1", channel=1)
    
    try:
        # Run test in test_mode (non-interactive)
        results = tester.test_varying_width(
            start_width=1e-6,  
            #start_width=100e-9,      # 100ns (will be clamped to 220ns minimum)
            stop_width=500e-3,       # 500ms (safe maximum, well below 833ms limit)
            points=30,               # 30 points across range

            # test pulse parameters
            test_amplitude=-2.5,
            reset_amplitude=2.5,

            # read parameters
            read_voltage=-0.5,
            read_width=10e-6,
            read_count=1,

            # timing
            settling_time= 0, # 10e-3,   # 10ms

            # current range
            i_range=0.0001, # 0.1 mA
            
            # options
            measure_test_current=True,  # Set True to measure V/I at test pulse peak (may affect device)
            verbose=True,
            plot=True,
            test_mode=False         # Non-interactive mode
        )
        
        print("\n" + "="*70)
        print("SUCCESS! Test completed.")
        print("="*70)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()

