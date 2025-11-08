"""
TEST #5: RETENTION TEST
========================

Write a state and monitor resistance drift over time.

Purpose:
--------
- Measure non-volatility (data retention)
- Detect resistance drift
- Verify state stability
- Extrapolate to long-term retention

Method:
-------
1. Write device to specific state (SET or RESET)
2. Read resistance periodically over time
3. Track resistance vs time (seconds to hours)
4. Analyze drift rate
5. Extrapolate to 10 year retention

Output:
-------
- Plot: Resistance vs time (log scale)
- Drift rate analysis
- Extrapolated retention time
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


class RetentionTest:
    """Retention test - resistance vs time."""
    
    def __init__(self, ip="192.168.0.10", pmu_id="PMU1", channel=1, data_dir="Memristor_Tests/data"):
        """Initialize PMU."""
        self.ip = ip
        self.pmu_id = pmu_id
        self.channel = channel
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        print("="*70)
        print("MEMRISTOR TESTER - Retention Test")
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
    
    def test_retention(self,
                      # Test parameters
                      duration=60,  # Total test duration (seconds)
                      read_interval=1.0,  # Time between reads (seconds)
                      
                      # State to test
                      test_state='LRS',  # 'LRS' or 'HRS'
                      
                      # Write pulse (to set state)
                      write_voltage=2.5,  # For LRS
                      write_width=100e-6,
                      
                      # Read parameters
                      read_voltage=0.5,
                      read_width=10e-6,
                      read_count=3,
                      
                      # Options
                      verbose=True,
                      plot=True,
                      test_mode=False):
        """
        Test retention over time.
        
        Args:
            duration: Total test duration (s)
            read_interval: Time between reads (s)
            test_state: State to test ('LRS' or 'HRS')
            write_voltage: Voltage to write state (V)
            write_width: Width of write pulse (s)
            read_voltage: Read pulse voltage (V)
            read_width: Read pulse width (s)
            read_count: Number of read pulses to average
            verbose: Print progress
            plot: Show/save plot
            test_mode: Non-interactive mode
            
        Returns:
            Dictionary with test results
        """
        
        if verbose:
            print("="*70)
            print("TEST #5: RETENTION TEST")
            print("="*70)
            print(f"Test state:    {test_state}")
            print(f"Duration:      {duration}s")
            print(f"Read interval: {read_interval}s")
            print(f"Write:         {write_voltage}V, {write_width*1e6:.1f}us")
            print(f"Read:          {read_voltage}V")
            print("="*70)
            print()
        
        resistances = []
        resistances_std = []
        times = []
        
        # Initialize ONCE
        v_range = 10.0
        i_range = 0.01
        self.lpt.pg2_init(self.card_id, self.param.PULSE_MODE_PULSE)
        self.lpt.pulse_ranges(self.card_id, self.channel,
                             v_range, self.param.PULSE_MEAS_FIXED, v_range,
                             self.param.PULSE_MEAS_FIXED, i_range)
        
        # 1. Write state
        if verbose:
            print(f"Writing {test_state} state ({write_voltage}V)...")
        self._apply_pulse(write_voltage, write_width, v_range, i_range)
        time.sleep(0.1)
        
        # 2. Initial read
        if verbose:
            print("Starting retention monitoring...")
            print()
        
        test_start = time.time()
        next_read_time = test_start
        
        while True:
            current_time = time.time()
            elapsed = current_time - test_start
            
            # Check if it's time for next read
            if current_time >= next_read_time:
                # Measure
                r_mean, r_std = self._measure_resistance(
                    read_voltage, read_width, read_count, v_range, i_range, False)
                
                resistances.append(r_mean)
                resistances_std.append(r_std)
                times.append(elapsed)
                
                if verbose:
                    print(f"t={elapsed:6.1f}s: R={r_mean/1e3:7.2f} +/- {r_std/1e3:5.2f} kOhm")
                
                # Schedule next read
                next_read_time += read_interval
            
            # Check if test is complete
            if elapsed >= duration:
                break
            
            # Small sleep to avoid busy waiting
            time.sleep(0.01)
        
        if verbose:
            print()
            print("="*70)
            print(f"Test complete! Duration: {elapsed:.1f}s")
            print("="*70)
            print()
        
        # Analyze drift
        r_arr = np.array(resistances)
        t_arr = np.array(times)
        
        # Calculate drift rate (linear fit)
        if len(times) > 2:
            # Fit: R(t) = R0 + drift_rate * t
            p = np.polyfit(t_arr, r_arr, 1)
            drift_rate = p[0]  # Ohm/s
            r_initial = p[1]  # Ohm
            
            # Calculate relative drift (%/decade)
            if r_initial > 0:
                drift_per_decade = (drift_rate * 3600 * 24 * 365 * 10) / r_initial * 100
            else:
                drift_per_decade = np.nan
        else:
            drift_rate = np.nan
            r_initial = resistances[0] if resistances else np.nan
            drift_per_decade = np.nan
        
        if verbose:
            print("RETENTION ANALYSIS:")
            print(f"  Initial R:     {r_initial/1e3:.2f} kOhm")
            print(f"  Final R:       {resistances[-1]/1e3:.2f} kOhm")
            print(f"  Drift rate:    {drift_rate:.3e} Ohm/s")
            print(f"  Drift/decade:  {drift_per_decade:.2f} %")
            print("="*70)
            print()
        
        # Prepare results
        results = {
            'time_s': times,
            'resistance_ohm': resistances,
            'resistance_kohm': r_arr / 1e3,
            'resistance_std_ohm': resistances_std,
            'test_state': test_state,
            'write_voltage': write_voltage,
            'drift_rate_ohm_per_s': drift_rate,
            'drift_per_decade_percent': drift_per_decade,
            'r_initial': r_initial,
            'r_final': resistances[-1] if resistances else np.nan
        }
        
        # Save data
        save_dir = self.data_dir / "retention"
        save_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = save_dir / f"retention_{test_state}_{timestamp}.csv"
        
        df = pd.DataFrame({
            'Time_s': results['time_s'],
            'Resistance_Ohm': results['resistance_ohm'],
            'Resistance_kOhm': results['resistance_kohm'],
            'Resistance_Std_Ohm': results['resistance_std_ohm']
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
                time.sleep(0.01)
            
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
        """Plot retention results."""
        if test_mode:
            plt.ioff()
        
        fig, ax = plt.subplots(figsize=(12, 7))
        
        times = np.array(results['time_s'])
        r = results['resistance_kohm']
        r_std = np.array(results['resistance_std_ohm']) / 1e3
        
        # Plot with error bars
        ax.errorbar(times, r, yerr=r_std, fmt='o-', linewidth=2,
                   markersize=6, capsize=5, capthick=2,
                   label=f"R_{results['test_state']}")
        
        # Plot linear fit if we have data
        if not np.isnan(results['drift_rate_ohm_per_s']):
            r_fit = (results['r_initial'] + results['drift_rate_ohm_per_s'] * times) / 1e3
            ax.plot(times, r_fit, 'r--', linewidth=2, alpha=0.7, label='Linear fit')
        
        ax.set_xlabel('Time (s)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Resistance (kOhm)', fontsize=12, fontweight='bold')
        ax.set_title(f"Retention Test - {results['test_state']} State", fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # Add analysis text
        analysis_text = f"State: {results['test_state']}\n"
        analysis_text += f"Write: {results['write_voltage']}V\n"
        analysis_text += f"R_initial: {results['r_initial']/1e3:.2f} kOhm\n"
        analysis_text += f"R_final: {results['r_final']/1e3:.2f} kOhm\n"
        if not np.isnan(results['drift_per_decade_percent']):
            analysis_text += f"Drift: {results['drift_per_decade_percent']:.2f} %/decade"
        ax.text(0.98, 0.02, analysis_text, transform=ax.transAxes,
               fontsize=10, verticalalignment='bottom', horizontalalignment='right',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
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
    print("MEMRISTOR TEST #5: RETENTION TEST")
    print("="*70)
    print()
    
    tester = RetentionTest(ip="192.168.0.10", pmu_id="PMU1", channel=1)
    
    try:
        results = tester.test_retention(
            duration=30,  # 30 seconds for testing
            read_interval=2.0,  # Read every 2 seconds
            test_state='LRS',
            write_voltage=2.5,
            read_voltage=0.5,
            verbose=True,
            plot=True,
            test_mode=True
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

