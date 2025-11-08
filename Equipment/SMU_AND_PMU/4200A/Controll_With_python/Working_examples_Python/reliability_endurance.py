"""
TEST #4: ENDURANCE TEST
========================

Cycle device many times to test lifetime and detect degradation.

Purpose:
--------
- Test device endurance (lifetime cycles)
- Detect degradation over many cycles
- Verify switching reliability
- Find failure point (window closure)

Method:
-------
Similar to SET/RESET cycling but with MORE cycles and degradation tracking:
1. Cycle device N times (100s to 1000s)
2. Track R_HRS and R_LRS each cycle
3. Calculate window ratio: R_HRS / R_LRS
4. Detect degradation trends
5. Identify failure (when window ratio < threshold)

Output:
-------
- Long-term resistance tracking
- Window ratio vs cycles
- Degradation rate analysis
- Failure detection
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


class EnduranceTest:
    """Endurance test - many cycles."""
    
    def __init__(self, ip="192.168.0.10", pmu_id="PMU1", channel=1, data_dir="Memristor_Tests/data"):
        """Initialize PMU."""
        self.ip = ip
        self.pmu_id = pmu_id
        self.channel = channel
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        print("="*70)
        print("MEMRISTOR TESTER - Endurance Test")
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
    
    def test_endurance(self,
                      cycles=100,
                      
                      # SET/RESET parameters
                      set_voltage=2.5,
                      set_width=100e-6,
                      reset_voltage=-2.0,
                      reset_width=1e-3,
                      
                      # Read parameters
                      read_voltage=0.5,
                      read_width=10e-6,
                      read_count=1,  # Less averaging for speed
                      
                      # Timing
                      settling_time=1e-3,  # Shorter for speed
                      
                      # Failure detection
                      window_threshold=1.5,  # Stop if window < this
                      
                      # Options
                      save_interval=10,  # Save every N cycles
                      verbose=True,
                      plot=True,
                      test_mode=False):
        """
        Test endurance over many cycles.
        
        Args:
            cycles: Number of cycles to run
            set_voltage, set_width: SET pulse parameters
            reset_voltage, reset_width: RESET pulse parameters
            read_voltage, read_width, read_count: Read parameters
            settling_time: Wait after pulses (s)
            window_threshold: Stop if window ratio < this
            save_interval: Save intermediate data every N cycles
            verbose: Print progress
            plot: Show/save plot
            test_mode: Non-interactive mode
            
        Returns:
            Dictionary with test results
        """
        
        if verbose:
            print("="*70)
            print("TEST #4: ENDURANCE TEST")
            print("="*70)
            print(f"Total cycles:     {cycles}")
            print(f"SET:              {set_voltage}V, {set_width*1e6:.1f}us")
            print(f"RESET:            {reset_voltage}V, {reset_width*1e3:.1f}ms")
            print(f"Window threshold: {window_threshold}")
            print("="*70)
            print()
        
        r_lrs = []
        r_hrs = []
        window_ratio = []
        cycle_times = []
        
        # Initialize ONCE
        v_range = 10.0
        i_range = 0.01
        self.lpt.pg2_init(self.card_id, self.param.PULSE_MODE_PULSE)
        self.lpt.pulse_ranges(self.card_id, self.channel,
                             v_range, self.param.PULSE_MEAS_FIXED, v_range,
                             self.param.PULSE_MEAS_FIXED, i_range)
        
        test_start = time.time()
        failed = False
        
        for i in range(cycles):
            cycle_start = time.time()
            
            if verbose and (i % max(1, cycles//20) == 0 or i < 5):
                print(f"[Cycle {i+1}/{cycles}]", end=" ")
            
            # SET
            self._apply_pulse(set_voltage, set_width, v_range, i_range)
            time.sleep(settling_time)
            
            # Measure LRS
            r_lrs_val, _ = self._measure_resistance(
                read_voltage, read_width, read_count, v_range, i_range, False)
            r_lrs.append(r_lrs_val)
            
            time.sleep(settling_time)
            
            # RESET
            self._apply_pulse(reset_voltage, reset_width, v_range, i_range)
            time.sleep(settling_time)
            
            # Measure HRS
            r_hrs_val, _ = self._measure_resistance(
                read_voltage, read_width, read_count, v_range, i_range, False)
            r_hrs.append(r_hrs_val)
            
            # Calculate window
            if r_lrs_val > 0 and not np.isnan(r_lrs_val) and not np.isnan(r_hrs_val):
                window = r_hrs_val / r_lrs_val
                window_ratio.append(window)
                
                if verbose and (i % max(1, cycles//20) == 0 or i < 5):
                    print(f"LRS={r_lrs_val/1e3:.1f}k, HRS={r_hrs_val/1e3:.1f}k, Window={window:.2f}")
                
                # Check for failure
                if window < window_threshold:
                    if verbose:
                        print(f"\n[FAILURE] Window ratio {window:.2f} < {window_threshold} at cycle {i+1}")
                    failed = True
                    break
            else:
                window_ratio.append(np.nan)
                if verbose and (i % max(1, cycles//20) == 0 or i < 5):
                    print("Measurement failed")
            
            cycle_times.append(time.time() - cycle_start)
            
            # Intermediate save
            if save_interval > 0 and (i+1) % save_interval == 0:
                self._save_intermediate(i+1, r_lrs, r_hrs, window_ratio)
        
        elapsed = time.time() - test_start
        avg_cycle_time = np.mean(cycle_times) if cycle_times else 0
        
        if verbose:
            print("\n" + "="*70)
            print(f"Test complete! Total time: {elapsed:.1f}s")
            print(f"Avg cycle time: {avg_cycle_time:.3f}s")
            if failed:
                print(f"FAILED at cycle {len(r_lrs)}/{cycles}")
            else:
                print(f"SUCCESS: Completed all {cycles} cycles")
            print("="*70)
            print()
        
        # Statistics
        r_lrs_arr = np.array(r_lrs)
        r_hrs_arr = np.array(r_hrs)
        window_arr = np.array(window_ratio)
        
        if verbose:
            print("STATISTICS:")
            print(f"  R_LRS:  {np.nanmean(r_lrs_arr)/1e3:.2f} +/- {np.nanstd(r_lrs_arr)/1e3:.2f} kOhm")
            print(f"  R_HRS:  {np.nanmean(r_hrs_arr)/1e3:.2f} +/- {np.nanstd(r_hrs_arr)/1e3:.2f} kOhm")
            print(f"  Window: {np.nanmean(window_arr):.2f} +/- {np.nanstd(window_arr):.2f}")
            print("="*70)
            print()
        
        # Prepare results
        results = {
            'cycle': np.arange(1, len(r_lrs)+1),
            'r_lrs_ohm': r_lrs,
            'r_lrs_kohm': r_lrs_arr / 1e3,
            'r_hrs_ohm': r_hrs,
            'r_hrs_kohm': r_hrs_arr / 1e3,
            'window_ratio': window_ratio,
            'failed': failed,
            'failure_cycle': len(r_lrs) if failed else None,
            'total_cycles_requested': cycles,
            'avg_cycle_time': avg_cycle_time
        }
        
        # Save final data
        save_dir = self.data_dir / "endurance"
        save_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = save_dir / f"endurance_{timestamp}.csv"
        
        df = pd.DataFrame({
            'Cycle': results['cycle'],
            'R_LRS_Ohm': results['r_lrs_ohm'],
            'R_LRS_kOhm': results['r_lrs_kohm'],
            'R_HRS_Ohm': results['r_hrs_ohm'],
            'R_HRS_kOhm': results['r_hrs_kohm'],
            'Window_Ratio': results['window_ratio']
        })
        df.to_csv(filename, index=False)
        print(f"[OK] Data saved: {filename}")
        
        # Plot
        if plot:
            self._plot_results(results, filename, test_mode=test_mode)
        
        return results
    
    def _save_intermediate(self, cycle, r_lrs, r_hrs, window):
        """Save intermediate results."""
        save_dir = self.data_dir / "endurance"
        save_dir.mkdir(exist_ok=True)
        filename = save_dir / f"endurance_intermediate_cycle{cycle}.csv"
        
        df = pd.DataFrame({
            'Cycle': np.arange(1, len(r_lrs)+1),
            'R_LRS_Ohm': r_lrs,
            'R_HRS_Ohm': r_hrs,
            'Window_Ratio': window
        })
        df.to_csv(filename, index=False)
    
    def _apply_pulse(self, amplitude, width, v_range, i_range):
        """Apply pulse (optimized for speed)."""
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
            time.sleep(0.005)
        
        self.lpt.pulse_output(self.card_id, self.channel, 0)
    
    def _measure_resistance(self, read_v, read_w, count, v_range, i_range, verbose=False):
        """Measure resistance (optimized for speed)."""
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
        """Plot endurance results."""
        if test_mode:
            plt.ioff()
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        cycles = results['cycle']
        r_lrs = results['r_lrs_kohm']
        r_hrs = results['r_hrs_kohm']
        window = results['window_ratio']
        
        # Plot 1: Resistance over cycles
        ax1.semilogy(cycles, r_hrs, 'r-', linewidth=1.5, alpha=0.7, label='R_HRS')
        ax1.semilogy(cycles, r_lrs, 'b-', linewidth=1.5, alpha=0.7, label='R_LRS')
        ax1.set_xlabel('Cycle Number', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Resistance (kOhm, log scale)', fontsize=12, fontweight='bold')
        ax1.set_title('Endurance Test - Resistance Tracking', fontsize=14, fontweight='bold')
        ax1.legend(fontsize=11)
        ax1.grid(True, alpha=0.3, which='both')
        
        # Plot 2: Window ratio
        ax2.plot(cycles, window, 'g-', linewidth=2, label='Window Ratio')
        ax2.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='No switching')
        ax2.set_xlabel('Cycle Number', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Window Ratio (R_HRS / R_LRS)', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=11)
        ax2.grid(True, alpha=0.3)
        
        # Mark failure point if failed
        if results['failed']:
            ax1.axvline(x=results['failure_cycle'], color='red', linestyle='--', linewidth=2, label='Failure')
            ax2.axvline(x=results['failure_cycle'], color='red', linestyle='--', linewidth=2)
        
        # Add stats text
        stats_text = f"Cycles: {len(cycles)}/{results['total_cycles_requested']}\n"
        stats_text += f"Avg cycle: {results['avg_cycle_time']:.3f}s\n"
        if results['failed']:
            stats_text += f"FAILED at cycle {results['failure_cycle']}"
        else:
            stats_text += "SUCCESS"
        ax1.text(0.02, 0.02, stats_text, transform=ax1.transAxes,
                fontsize=10, verticalalignment='bottom',
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
    print("MEMRISTOR TEST #4: ENDURANCE TEST")
    print("="*70)
    print()
    
    tester = EnduranceTest(ip="192.168.0.10", pmu_id="PMU1", channel=1)
    
    try:
        results = tester.test_endurance(
            cycles=5,  # Reduced for testing
            set_voltage=2.5,
            reset_voltage=-2.0,
            read_voltage=0.5,
            window_threshold=1.5,
            save_interval=5,
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

