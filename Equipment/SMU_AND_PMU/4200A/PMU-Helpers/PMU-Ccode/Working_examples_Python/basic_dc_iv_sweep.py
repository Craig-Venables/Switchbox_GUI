"""
TEST #11: DC IV SWEEP
=====================
# Do notuse skew rate issue and isnt speedy enough

DC (continuous) IV characteristic measurement.

Purpose:
--------
- Measure quasi-static IV curve
- Find DC switching thresholds
- Compare DC vs pulse behavior
- Identify hysteresis loops

Method:
-------
1. Apply slow voltage ramp (DC-like)
2. Measure current at each voltage point
3. Plot IV curve
4. Detect switching events
5. Optional: Bidirectional sweep for hysteresis

Output:
-------
- IV curve (I vs V)
- DC resistance curve (R vs V)
- Switching voltage detection
- Hysteresis analysis
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


class DCIVSweepTest:
    """DC IV sweep test."""
    
    def __init__(self, ip="192.168.0.10", pmu_id="PMU1", channel=1, data_dir="Memristor_Tests/data"):
        """Initialize PMU."""
        self.ip = ip
        self.pmu_id = pmu_id
        self.channel = channel
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        print("="*70)
        print("MEMRISTOR TESTER - DC IV Sweep")
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
    
    def test_dc_iv_sweep(self,
                        # Sweep parameters
                        start_voltage=-2.0,
                        stop_voltage=2.0,
                        points=50,
                        
                        # Quasi-DC parameters
                        step_width=10e-3,  # 10ms per point (slow = DC-like)
                        
                        # Sweep direction
                        bidirectional=False,  # If True: 0→+V→-V→0
                        
                        # Ranges
                        v_range=10.0,
                        i_range=0.01,
                        
                        # Options
                        verbose=True,
                        plot=True,
                        test_mode=False):
        """
        Test DC IV sweep.
        
        Args:
            start_voltage: Starting voltage (V)
            stop_voltage: Ending voltage (V)
            points: Number of voltage points
            step_width: Time at each voltage (s) - longer = more DC-like
            bidirectional: If True, sweep both directions
            v_range: Voltage range (V)
            i_range: Current range (A)
            verbose: Print progress
            plot: Show/save plot
            test_mode: Non-interactive mode
            
        Returns:
            Dictionary with test results
        """
        
        if verbose:
            print("="*70)
            print("TEST #11: DC IV SWEEP")
            print("="*70)
            print(f"Voltage range: {start_voltage}V to {stop_voltage}V")
            print(f"Points:        {points}")
            print(f"Step time:     {step_width*1e3:.1f}ms (quasi-DC)")
            print(f"Bidirectional: {bidirectional}")
            print("="*70)
            print()
        
        # Initialize
        self.lpt.pg2_init(self.card_id, self.param.PULSE_MODE_PULSE)
        self.lpt.pulse_ranges(self.card_id, self.channel,
                             v_range, self.param.PULSE_MEAS_FIXED, v_range,
                             self.param.PULSE_MEAS_FIXED, i_range)
        
        # Generate voltage sweep
        if bidirectional:
            # 0 → +V → -V → 0
            v_forward = np.linspace(0, stop_voltage, points//2)
            v_reverse = np.linspace(stop_voltage, start_voltage, points//2)
            v_return = np.linspace(start_voltage, 0, points//4)
            voltages = np.concatenate([v_forward, v_reverse, v_return])
        else:
            # Simple sweep
            voltages = np.linspace(start_voltage, stop_voltage, points)
        
        currents = []
        resistances = []
        
        if verbose:
            print("Starting DC IV sweep...")
            print()
        
        # Sweep
        for i, voltage in enumerate(voltages):
            if verbose and (i % max(1, len(voltages)//20) == 0 or i < 3):
                print(f"[{i+1}/{len(voltages)}] V = {voltage:+.3f}V", end=" ")
            
            # Apply voltage and measure current
            current = self._apply_and_measure(voltage, step_width, v_range, i_range)
            currents.append(current)
            
            # Calculate resistance
            if abs(current) > 1e-12:
                r = abs(voltage / current)
                resistances.append(r)
            else:
                resistances.append(np.nan)
            
            if verbose and (i % max(1, len(voltages)//20) == 0 or i < 3):
                print(f"-> I = {current*1e6:.3f}µA, R = {resistances[-1]/1e3:.2f}kΩ")
        
        if verbose:
            print()
            print("="*70)
            print("Sweep complete!")
            print("="*70)
            print()
        
        # Analysis
        v_arr = np.array(voltages)
        i_arr = np.array(currents)
        r_arr = np.array(resistances)
        
        # Find max/min current
        i_max = np.nanmax(np.abs(i_arr))
        i_min = np.nanmin(np.abs(i_arr[i_arr != 0]))
        
        if verbose:
            print("ANALYSIS:")
            print(f"  Max |I|:  {i_max*1e6:.3f} µA")
            print(f"  Min |I|:  {i_min*1e6:.3f} µA")
            print(f"  Mean R:   {np.nanmean(r_arr)/1e3:.2f} kΩ")
            print("="*70)
            print()
        
        # Prepare results
        results = {
            'voltage': voltages,
            'current_a': currents,
            'current_ua': i_arr * 1e6,
            'current_ma': i_arr * 1e3,
            'resistance_ohm': resistances,
            'resistance_kohm': r_arr / 1e3,
            'bidirectional': bidirectional,
            'i_max': i_max,
            'i_min': i_min
        }
        
        # Save data
        save_dir = self.data_dir / "dc_iv_sweep"
        save_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = save_dir / f"dc_iv_sweep_{timestamp}.csv"
        
        df = pd.DataFrame({
            'Voltage_V': results['voltage'],
            'Current_A': results['current_a'],
            'Current_uA': results['current_ua'],
            'Resistance_Ohm': results['resistance_ohm'],
            'Resistance_kOhm': results['resistance_kohm']
        })
        df.to_csv(filename, index=False)
        print(f"[OK] Data saved: {filename}")
        
        # Plot
        if plot:
            self._plot_results(results, filename, test_mode=test_mode)
        
        return results
    
    def _apply_and_measure(self, voltage, width, v_range, i_range):
        """Apply voltage and measure current (DC-like)."""
        voltage = float(voltage)
        width = float(width)
        
        # Use long pulse for quasi-DC
        rise_time = min(1e-6, width / 100)  # Slow rise for DC-like (use min())
        fall_time = rise_time
        delay = 1e-7
        period = max(width * 2, 10e-6)  # Period = 2x width, min 10µs
        
        self.lpt.pulse_source_timing(self.card_id, self.channel,
                                    period, delay, width, rise_time, fall_time)
        self.lpt.pulse_limits(self.card_id, self.channel,
                             v_range, i_range, v_range * i_range)
        self.lpt.pulse_sweep_linear(self.card_id, self.channel,
                                   self.param.PULSE_AMPLITUDE_SP,
                                   voltage, voltage, 0.0)
        
        # Measure during pulse
        self.lpt.pulse_meas_sm(self.card_id, self.channel, 0, 0, 0, 1, 0, 1, 0)
        self.lpt.pulse_meas_timing(self.card_id, self.channel, 0.5, 0.9, 1)  # Measure at end
        
        self.lpt.pulse_output(self.card_id, self.channel, 1)
        self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)
        
        # Wait for completion
        timeout = time.time() + 60
        while time.time() < timeout:
            try:
                status, elapsed = self.lpt.pulse_exec_status()
                if status != self.param.PMU_TEST_STATUS_RUNNING:
                    break
            except:
                pass
            time.sleep(0.01)
        
        # Get current measurement
        buf_size = self.lpt.pulse_chan_status(self.card_id, self.channel)
        if buf_size > 0:
            v, i, ts, st = self.lpt.pulse_fetch(self.card_id, self.channel, 0, max(0, buf_size - 1))
            if len(i) > 0:
                current = i[0]
            else:
                current = 0.0
        else:
            current = 0.0
        
        self.lpt.pulse_output(self.card_id, self.channel, 0)
        
        return current
    
    def _plot_results(self, results, filename, test_mode=False):
        """Plot DC IV results."""
        if test_mode:
            plt.ioff()
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        v = results['voltage']
        i = results['current_ua']
        r = results['resistance_kohm']
        
        # Plot 1: IV curve
        if results['bidirectional']:
            # Show direction with arrows
            ax1.plot(v, i, 'b-', linewidth=2, alpha=0.7)
            ax1.scatter(v[::len(v)//10], i[::len(v)//10], c=range(0, len(v), len(v)//10),
                       cmap='viridis', s=50, zorder=5)
        else:
            ax1.plot(v, i, 'bo-', linewidth=2, markersize=4)
        
        ax1.axhline(y=0, color='k', linestyle='--', linewidth=1, alpha=0.5)
        ax1.axvline(x=0, color='k', linestyle='--', linewidth=1, alpha=0.5)
        ax1.set_xlabel('Voltage (V)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Current (µA)', fontsize=12, fontweight='bold')
        ax1.set_title('DC IV Characteristic', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Resistance vs voltage
        ax2.plot(v, r, 'ro-', linewidth=2, markersize=4)
        ax2.set_xlabel('Voltage (V)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Resistance (kΩ)', fontsize=12, fontweight='bold')
        ax2.set_title('DC Resistance vs Voltage', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # Add stats
        stats_text = f"Max |I|: {results['i_max']*1e6:.2f} µA\n"
        stats_text += f"Min |I|: {results['i_min']*1e6:.2f} µA"
        ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes,
                fontsize=10, verticalalignment='top',
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
    print("MEMRISTOR TEST #11: DC IV SWEEP")
    print("="*70)
    print()
    
    tester = DCIVSweepTest(ip="192.168.0.10", pmu_id="PMU1", channel=1)
    
    try:
        results = tester.test_dc_iv_sweep(
            start_voltage=-2.0,
            stop_voltage=2.0,
            points=30,  # Reduced for testing
            step_width=10e-3,  # 10ms per point
            bidirectional=False,
            verbose=True,
            plot=True,
            test_mode=True
        )
        
        print("\n" + "="*70)
        print("SUCCESS! DC IV sweep complete.")
        print("="*70)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()

