"""
TEST #6: READ DISTURB TEST
===========================

Apply many read pulses and verify they don't change the device state.

Purpose:
--------
- Verify read pulses are non-destructive
- Ensure read operations don't switch device
- Find maximum safe read voltage
- Test read reliability

Method:
-------
1. Write device to known state (SET or RESET)
2. Apply many read pulses (100s to 1000s)
3. Measure resistance after each read
4. Verify resistance stays constant
5. Calculate variation/drift

Output:
-------
- Resistance vs read count
- Statistical analysis of variation
- Maximum deviation from initial state
- Pass/fail based on threshold
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


class ReadDisturbTest:
    """Read disturb test - verify read pulses are non-destructive."""
    
    def __init__(self, ip="192.168.0.10", pmu_id="PMU1", channel=1, data_dir="Memristor_Tests/data"):
        """Initialize PMU."""
        self.ip = ip
        self.pmu_id = pmu_id
        self.channel = channel
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        print("="*70)
        print("MEMRISTOR TESTER - Read Disturb Test")
        print("="*70)
        print(f"IP:      {ip}")
        print(f"PMU:     {pmu_id}")
        print(f"Channel: {channel}")
        print()
        
        print("Connecting to PMU...")
        self.lpt = Proxy(ip, 8888, "lpt")
        self.param = Proxy(ip, 8888, "param")
        
        self.lpt.initialize()
        self.lpt.tstsel(1)
        self.lpt.devint()
        self.card_id = self.lpt.getinstid(pmu_id)
        self.lpt.setmode(self.card_id, self.param.KI_LIM_MODE, self.param.KI_VALUE)
        
        print(f"[OK] Connected to {pmu_id}\n")
        
        try:
            self.lpt.rpm_config(self.card_id, channel,
                               self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
            print(f"[OK] RPM configured\n")
        except Exception as e:
            print(f"[WARNING] RPM: {e}\n")
    
    def test_read_disturb(self,
                         # Test parameters
                         read_count=100,
                         test_state='LRS',
                         
                         # Write pulse (to set state)
                         write_voltage=2.5,
                         write_width=100e-6,
                         
                         # Read pulse
                         read_voltage=0.5,
                         read_width=10e-6,
                         
                         # Pass/fail criteria
                         max_deviation_percent=5.0,
                         
                         # Options
                         verbose=True,
                         plot=True,
                         test_mode=False):
        """
        Test read disturb - verify reads don't change state.
        
        Args:
            read_count: Number of read pulses to apply
            test_state: State to test ('LRS' or 'HRS')
            write_voltage: Voltage to write state (V)
            write_width: Write pulse width (s)
            read_voltage: Read pulse voltage (V)
            read_width: Read pulse width (s)
            max_deviation_percent: Max allowed deviation (%)
            verbose: Print progress
            plot: Show/save plot
            test_mode: Non-interactive mode
            
        Returns:
            Dictionary with test results
        """
        
        if verbose:
            print("="*70)
            print("TEST #6: READ DISTURB TEST")
            print("="*70)
            print(f"Test state:    {test_state}")
            print(f"Read count:    {read_count}")
            print(f"Write:         {write_voltage}V, {write_width*1e6:.1f}us")
            print(f"Read:          {read_voltage}V, {read_width*1e6:.1f}us")
            print(f"Max deviation: {max_deviation_percent}%")
            print("="*70)
            print()
        
        resistances = []
        read_numbers = []
        
        # Initialize ONCE
        v_range = 10.0
        i_range = 0.01
        self.lpt.pg2_init(self.card_id, self.param.PULSE_MODE_PULSE)
        self.lpt.pulse_ranges(self.card_id, self.channel,
                             v_range, self.param.PULSE_MEAS_FIXED, v_range,
                             self.param.PULSE_MEAS_FIXED, i_range)
        
        # 1. Write initial state
        if verbose:
            print(f"Writing {test_state} state ({write_voltage}V)...")
        self._apply_pulse(write_voltage, write_width, v_range, i_range)
        time.sleep(0.01)
        
        # 2. Initial read
        if verbose:
            print("Measuring initial resistance...")
        r_initial, _ = self._measure_resistance(read_voltage, read_width, 1, v_range, i_range, False)
        
        if verbose:
            print(f"Initial R: {r_initial/1e3:.2f} kOhm")
            print()
            print("Starting read disturb test...")
            print()
        
        # 3. Apply many read pulses
        start_time = time.time()
        
        for i in range(read_count):
            if verbose and (i % max(1, read_count//20) == 0 or i < 5):
                print(f"[Read {i+1}/{read_count}]", end=" ")
            
            # Read and measure
            r_meas, _ = self._measure_resistance(read_voltage, read_width, 1, v_range, i_range, False)
            resistances.append(r_meas)
            read_numbers.append(i + 1)
            
            if verbose and (i % max(1, read_count//20) == 0 or i < 5):
                deviation = abs(r_meas - r_initial) / r_initial * 100 if r_initial > 0 else 0
                print(f"R={r_meas/1e3:.2f}k, Dev={deviation:.2f}%")
        
        elapsed = time.time() - start_time
        
        if verbose:
            print()
            print("="*70)
            print(f"Test complete! Elapsed: {elapsed:.1f}s")
            print("="*70)
            print()
        
        # Analysis
        r_arr = np.array(resistances)
        r_mean = np.nanmean(r_arr)
        r_std = np.nanstd(r_arr)
        r_min = np.nanmin(r_arr)
        r_max = np.nanmax(r_arr)
        
        # Calculate deviations
        max_deviation = max(abs(r_max - r_initial), abs(r_min - r_initial)) / r_initial * 100 if r_initial > 0 else 0
        variation_percent = (r_std / r_mean * 100) if r_mean > 0 else 0
        
        # Pass/fail
        passed = max_deviation <= max_deviation_percent
        
        if verbose:
            print("ANALYSIS:")
            print(f"  Initial R:     {r_initial/1e3:.2f} kOhm")
            print(f"  Mean R:        {r_mean/1e3:.2f} kOhm")
            print(f"  Std dev:       {r_std/1e3:.2f} kOhm ({variation_percent:.2f}%)")
            print(f"  Min R:         {r_min/1e3:.2f} kOhm")
            print(f"  Max R:         {r_max/1e3:.2f} kOhm")
            print(f"  Max deviation: {max_deviation:.2f}%")
            print()
            print(f"  Status: {'PASS' if passed else 'FAIL'}")
            print("="*70)
            print()
        
        # Prepare results
        results = {
            'read_number': read_numbers,
            'resistance_ohm': resistances,
            'resistance_kohm': r_arr / 1e3,
            'r_initial': r_initial,
            'r_mean': r_mean,
            'r_std': r_std,
            'r_min': r_min,
            'r_max': r_max,
            'max_deviation_percent': max_deviation,
            'variation_percent': variation_percent,
            'passed': passed,
            'test_state': test_state,
            'read_voltage': read_voltage,
            'read_count': read_count
        }
        
        # Save data
        save_dir = self.data_dir / "read_disturb"
        save_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = save_dir / f"read_disturb_{test_state}_{timestamp}.csv"
        
        df = pd.DataFrame({
            'Read_Number': results['read_number'],
            'Resistance_Ohm': results['resistance_ohm'],
            'Resistance_kOhm': results['resistance_kohm']
        })
        df.to_csv(filename, index=False)
        print(f"[OK] Data saved: {filename}")
        
        # Plot
        if plot:
            self._plot_results(results, filename, test_mode=test_mode)
        
        return results
    
    def _apply_pulse(self, amplitude, width, v_range, i_range):
        """Apply pulse."""
        amplitude = float(amplitude)
        width = float(width)
        
        rise_time = max(1e-6, width / 10)
        fall_time = rise_time
        delay = 1e-7
        min_period = delay + rise_time + width + fall_time + 1e-7
        period = max(width * 3, min_period, 10e-6)
        
        self.lpt.pulse_source_timing(self.card_id, self.channel,
                                    period, delay, width, rise_time, fall_time)
        self.lpt.pulse_limits(self.card_id, self.channel,
                             v_range, i_range, v_range * i_range)
        self.lpt.pulse_sweep_linear(self.card_id, self.channel,
                                   self.param.PULSE_AMPLITUDE_SP,
                                   amplitude, amplitude, 0.0)
        self.lpt.pulse_meas_sm(self.card_id, self.channel, 0, 0, 0, 0, 0, 0, 0)
        
        self.lpt.pulse_output(self.card_id, self.channel, 1)
        self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
        
        timeout = time.time() + 60
        while time.time() < timeout:
            try:
                status, elapsed = self.lpt.pulse_exec_status()
                if status != self.param.PMU_TEST_STATUS_RUNNING:
                    break
            except:
                pass
            time.sleep(0.01)
        
        self.lpt.pulse_output(self.card_id, self.channel, 0)
    
    def _measure_resistance(self, read_v, read_w, count, v_range, i_range, verbose=False):
        """Measure resistance."""
        resistances = []
        
        for _ in range(count):
            rise_time = max(1e-6, read_w / 10)
            fall_time = rise_time
            delay = 1e-7
            min_period = delay + rise_time + read_w + fall_time + 1e-7
            period = max(read_w * 3, min_period, 10e-6)
            
            self.lpt.pulse_source_timing(self.card_id, self.channel,
                                        period, delay, read_w, rise_time, fall_time)
            self.lpt.pulse_limits(self.card_id, self.channel,
                                 v_range, i_range, v_range * i_range)
            self.lpt.pulse_sweep_linear(self.card_id, self.channel,
                                       self.param.PULSE_AMPLITUDE_SP,
                                       read_v, read_v, 0.0)
            self.lpt.pulse_meas_sm(self.card_id, self.channel, 0, 1, 0, 1, 0, 1, 0)
            self.lpt.pulse_meas_timing(self.card_id, self.channel, 0.1, 0.9, 1)
            
            self.lpt.pulse_output(self.card_id, self.channel, 1)
            self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
            
        timeout = time.time() + 60
        while time.time() < timeout:
            try:
                status, elapsed = self.lpt.pulse_exec_status()
                if status != self.param.PMU_TEST_STATUS_RUNNING:
                    break
            except:
                pass
            time.sleep(0.005)
            
            buf_size = self.lpt.pulse_chan_status(self.card_id, self.channel)
            if buf_size > 0:
                v, i, ts, st = self.lpt.pulse_fetch(self.card_id, self.channel, 0, max(0, buf_size - 1))
                if len(v) > 0 and len(i) > 0:
                    if abs(i[0]) > 1e-12:
                        resistances.append(abs(v[0] / i[0]))
            
            self.lpt.pulse_output(self.card_id, self.channel, 0)
        
        if resistances:
            return np.mean(resistances), np.std(resistances) if len(resistances) > 1 else 0.0
        else:
            return np.nan, np.nan
    
    def _plot_results(self, results, filename, test_mode=False):
        """Plot read disturb results."""
        if test_mode:
            plt.ioff()
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        reads = np.array(results['read_number'])
        r = results['resistance_kohm']
        r_initial = results['r_initial'] / 1e3
        r_mean = results['r_mean'] / 1e3
        
        # Plot 1: Resistance vs read number
        ax1.plot(reads, r, 'b-', linewidth=1, alpha=0.7, label='Measured R')
        ax1.axhline(y=r_initial, color='r', linestyle='--', linewidth=2, label=f'Initial R ({r_initial:.2f} kOhm)')
        ax1.axhline(y=r_mean, color='g', linestyle='--', linewidth=2, label=f'Mean R ({r_mean:.2f} kOhm)')
        
        # Shade acceptable deviation zone
        max_dev = results['max_deviation_percent'] if 'max_deviation_percent' in results else 5.0
        upper = r_initial * (1 + max_dev/100)
        lower = r_initial * (1 - max_dev/100)
        ax1.fill_between(reads, lower, upper, alpha=0.2, color='green', label=f'+/- {max_dev}% zone')
        
        ax1.set_xlabel('Read Number', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Resistance (kOhm)', fontsize=12, fontweight='bold')
        ax1.set_title(f"Read Disturb Test - {results['test_state']} State", fontsize=14, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Deviation from initial
        deviation = (r - r_initial) / r_initial * 100
        ax2.plot(reads, deviation, 'g-', linewidth=1.5)
        ax2.axhline(y=0, color='r', linestyle='--', linewidth=2)
        ax2.set_xlabel('Read Number', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Deviation from Initial (%)', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # Add stats text
        stats_text = f"Reads: {results['read_count']}\n"
        stats_text += f"Read V: {results['read_voltage']}V\n"
        stats_text += f"Variation: {results['variation_percent']:.2f}%\n"
        stats_text += f"Max dev: {results['max_deviation_percent']:.2f}%\n"
        stats_text += f"Status: {'PASS' if results['passed'] else 'FAIL'}"
        ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', 
                         facecolor='lightgreen' if results['passed'] else 'lightcoral', 
                         alpha=0.5))
        
        plt.tight_layout()
        
        plot_filename = str(filename).replace('.csv', '.png')
        plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
        print(f"[OK] Plot saved: {plot_filename}")
        
        if not test_mode:
            plt.show()
        else:
            plt.close(fig)
    
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
    print("MEMRISTOR TEST #6: READ DISTURB TEST")
    print("="*70)
    print()
    
    tester = ReadDisturbTest(ip="192.168.0.10", pmu_id="PMU1", channel=1)
    
    try:
        results = tester.test_read_disturb(
            read_count=50,  # Reduced for testing
            test_state='LRS',
            write_voltage=2.5,
            read_voltage=0.5,
            max_deviation_percent=5.0,
            verbose=True,
            plot=True,
            test_mode=True
        )
        
        print("\n" + "="*70)
        print(f"SUCCESS! Test {'PASSED' if results['passed'] else 'FAILED'}.")
        print("="*70)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()

