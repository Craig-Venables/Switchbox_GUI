"""
PMU Segment ARB Example - Python version of PMU_SegArb_Example.c

Segment ARB mode allows creating complex multi-segment waveforms with:
- Different voltage levels per segment
- Individual timing for each segment
- Waveform measurement (V, I vs time)

Based on Keithley's C example.
"""

import sys
import time
from pathlib import Path
import numpy as np

# Add parent directory to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.SMU_AND_PMU.ProxyClass import Proxy


class PMU_SegArb:
    """Segment ARB waveform generator for dual-channel PMU."""
    
    def __init__(self, ip="192.168.0.10", port=8888, card="PMU1"):
        self.ip = ip
        self.port = port
        self.card = card
        
        # Connect
        self.lpt = Proxy(ip, port, "lpt")
        self.param = Proxy(ip, port, "param")
        
        self.lpt.initialize()
        self.lpt.tstsel(1)
        self.lpt.devint()
        
        self.card_id = self.lpt.getinstid(card)
        
        # Set to return actual values on compliance
        self.lpt.setmode(self.card_id, self.param.KI_LIM_MODE, self.param.KI_VALUE)
        
        print(f"Connected to {card}")
    
    def run_segarb_sweep(self,
                         # Channel 1 settings
                         v_range_ch1=10.0,
                         i_range_ch1=0.2,
                         dut_res_ch1=1e6,
                         start_v_ch1=None,
                         stop_v_ch1=None,
                         ssr_ctrl_ch1=None,
                         # Channel 2 settings
                         v_range_ch2=10.0,
                         i_range_ch2=0.2,
                         dut_res_ch2=1e6,
                         start_v_ch2=None,
                         stop_v_ch2=None,
                         ssr_ctrl_ch2=None,
                         # Timing (common to both channels)
                         seg_time=None,
                         # Trigger
                         seg_trig_out=None,
                         # Measurement
                         max_sheet_points=5000):
        """
        Run Segment ARB waveform on both channels.
        
        Args:
            v_range_ch1, v_range_ch2: Voltage ranges (10 or 40V)
            i_range_ch1, i_range_ch2: Current ranges (0.01, 0.2, etc.)
            dut_res_ch1, dut_res_ch2: DUT resistance (1 to 1e6 ohms)
            start_v_ch1, stop_v_ch1: Arrays of start/stop voltages for Ch1
            start_v_ch2, stop_v_ch2: Arrays of start/stop voltages for Ch2
            seg_time: Array of segment times (seconds)
            ssr_ctrl_ch1, ssr_ctrl_ch2: SSR control (1=closed, 0=open)
            seg_trig_out: Trigger output array (1 or 0)
            max_sheet_points: Max samples to return
            
        Returns:
            dict with 'v_ch1', 'i_ch1', 'v_ch2', 'i_ch2', 'time' arrays
        """
        
        # Validate inputs
        num_segments = len(seg_time) if seg_time else 0
        if num_segments < 3:
            raise ValueError("Need at least 3 segments")
        
        # Default arrays if not provided
        if start_v_ch1 is None or stop_v_ch1 is None:
            raise ValueError("Must provide start_v_ch1 and stop_v_ch1")
        if start_v_ch2 is None or stop_v_ch2 is None:
            raise ValueError("Must provide start_v_ch2 and stop_v_ch2")
        if ssr_ctrl_ch1 is None:
            ssr_ctrl_ch1 = [1] * num_segments
        if ssr_ctrl_ch2 is None:
            ssr_ctrl_ch2 = [1] * num_segments  
        if seg_trig_out is None:
            seg_trig_out = [1] + [0] * (num_segments - 1)
        
        # Convert to arrays
        start_v_ch1 = np.array(start_v_ch1, dtype=float)
        stop_v_ch1 = np.array(stop_v_ch1, dtype=float)
        start_v_ch2 = np.array(start_v_ch2, dtype=float)
        stop_v_ch2 = np.array(stop_v_ch2, dtype=float)
        seg_time = np.array(seg_time, dtype=float)
        ssr_ctrl_ch1 = np.array(ssr_ctrl_ch1, dtype=int)
        ssr_ctrl_ch2 = np.array(ssr_ctrl_ch2, dtype=int)
        seg_trig_out = np.array(seg_trig_out, dtype=int)
        
        # Ensure first trigger is 1
        seg_trig_out[0] = 1
        
        print(f"Segment ARB: {num_segments} segments")
        
        # Configure RPMs if present
        try:
            self.lpt.rpm_config(self.card_id, 1, self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
            self.lpt.rpm_config(self.card_id, 2, self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
        except:
            pass
        
        # Set to Segment ARB mode
        PULSE_MODE_SARB = 2
        try:
            self.lpt.pg2_init(self.card_id, PULSE_MODE_SARB)
            print("Set to Segment ARB mode")
        except Exception as e:
            raise RuntimeError(f"pg2_init failed: {e}")
        
        # Set load resistance
        self.lpt.pulse_load(self.card_id, 1, float(dut_res_ch1))
        self.lpt.pulse_load(self.card_id, 2, float(dut_res_ch2))
        
        # Set ranges (fixed ranges for SegArb)
        PULSE_MEAS_FIXED = 1
        self.lpt.pulse_ranges(self.card_id, 1,
                             float(v_range_ch1), PULSE_MEAS_FIXED, float(v_range_ch1),
                             PULSE_MEAS_FIXED, float(i_range_ch1))
        self.lpt.pulse_ranges(self.card_id, 2,
                             float(v_range_ch2), PULSE_MEAS_FIXED, float(v_range_ch2),
                             PULSE_MEAS_FIXED, float(i_range_ch2))
        
        # Calculate sample rate
        total_seg_time = np.sum(seg_time)
        sample_rate = 200e6  # Start at max
        num_total_samples = total_seg_time * sample_rate
        
        # Reduce sample rate if too many samples
        MaxSamplesPerAtoD = 65536
        if num_total_samples > MaxSamplesPerAtoD:
            rate_factor = int(num_total_samples / MaxSamplesPerAtoD) + 1
            sample_rate = sample_rate / rate_factor
            print(f"Reduced sample rate by {rate_factor}x to {sample_rate/1e6:.1f} MSa/s")
        
        if num_total_samples > max_sheet_points:
            rate_factor = int(num_total_samples / max_sheet_points) + 1
            sample_rate = sample_rate / rate_factor
            print(f"Sample rate set to {sample_rate/1e6:.1f} MSa/s")
        
        self.lpt.pulse_sample_rate(self.card_id, int(sample_rate))
        
        # Set burst count (number of waveforms)
        self.lpt.pulse_burst_count(self.card_id, 1, 1)
        self.lpt.pulse_burst_count(self.card_id, 2, 1)
        
        # Prepare measurement arrays
        PULSE_MEAS_WFM_PER = 3  # Waveform per segment
        meas_type = [PULSE_MEAS_WFM_PER] * num_segments
        meas_start = [0.0] * num_segments
        meas_stop = seg_time.tolist()
        
        # Program Segment ARB sequences
        print("Programming Channel 1 sequence...")
        self.lpt.seg_arb_sequence(
            self.card_id, 1, 1, num_segments,
            start_v_ch1.tolist(),
            stop_v_ch1.tolist(),
            seg_time.tolist(),
            seg_trig_out.tolist(),
            ssr_ctrl_ch1.tolist(),
            meas_type,
            meas_start,
            meas_stop
        )
        
        print("Programming Channel 2 sequence...")
        self.lpt.seg_arb_sequence(
            self.card_id, 2, 1, num_segments,
            start_v_ch2.tolist(),
            stop_v_ch2.tolist(),
            seg_time.tolist(),
            seg_trig_out.tolist(),
            ssr_ctrl_ch2.tolist(),
            meas_type,
            meas_start,
            meas_stop
        )
        
        # Program waveforms
        seq_list = [1]
        loop_count = [1.0]
        
        self.lpt.seg_arb_waveform(self.card_id, 1, 1, seq_list, loop_count)
        self.lpt.seg_arb_waveform(self.card_id, 2, 1, seq_list, loop_count)
        
        # Turn on outputs
        self.lpt.pulse_output(self.card_id, 1, 1)
        self.lpt.pulse_output(self.card_id, 2, 1)
        
        # Execute test
        print("Executing waveform...")
        PULSE_MODE_SIMPLE = 0
        self.lpt.pulse_exec(PULSE_MODE_SIMPLE)
        
        # Wait for completion
        while True:
            status, elapsed = self.lpt.pulse_exec_status()
            if status != 1:  # Not running
                break
            time.sleep(0.1)
        
        print("Waveform complete, fetching data...")
        
        # Fetch data
        buf_size_ch1 = self.lpt.pulse_chan_status(self.card_id, 1)
        buf_size_ch2 = self.lpt.pulse_chan_status(self.card_id, 2)
        
        v_ch1, i_ch1, t_ch1, st_ch1 = self.lpt.pulse_fetch(self.card_id, 1, 0, max(0, buf_size_ch1-1))
        v_ch2, i_ch2, t_ch2, st_ch2 = self.lpt.pulse_fetch(self.card_id, 2, 0, max(0, buf_size_ch2-1))
        
        print(f"Fetched {len(v_ch1)} samples from Ch1, {len(v_ch2)} samples from Ch2")
        
        return {
            'v_ch1': np.array(v_ch1),
            'i_ch1': np.array(i_ch1),
            'time_ch1': np.array(t_ch1),
            'v_ch2': np.array(v_ch2),
            'i_ch2': np.array(i_ch2),
            'time_ch2': np.array(t_ch2),
        }
    
    def cleanup(self):
        """Clean shutdown."""
        try:
            self.lpt.pulse_output(self.card_id, 1, 0)
            self.lpt.pulse_output(self.card_id, 2, 0)
        except:
            pass
        try:
            self.lpt.tstdsl()
            self.lpt.devint()
        except:
            pass


def example_5point_voltage_sweep():
    """
    Example from C code: 5-point voltage sweep
    
    Ch1 sweeps UP: 0.5V, 1V, 1.5V, 2V, 2.5V  
    Ch2 sweeps DOWN: 2.5V, 2V, 1.5V, 1V, 0.5V
    
    Each pulse is 10us with 100ns transitions
    """
    
    # 21 segments total (see C example)
    seg_time = [
        100e-9, 100e-9, 10e-6, 100e-9, 50e-6,  # 0V -> 0.5V pulse
        100e-9, 10e-6, 100e-9, 50e-6,          # 0V -> 1.0V pulse
        100e-9, 10e-6, 100e-9, 50e-6,          # 0V -> 1.5V pulse
        100e-9, 10e-6, 100e-9, 50e-6,          # 0V -> 2.0V pulse  
        100e-9, 10e-6, 100e-9, 100e-9          # 0V -> 2.5V pulse
    ]
    
    # Ch1 voltages (sweep UP)
    start_v_ch1 = [
        0.0, 0.0, 0.5, 0.5, 0.0,
        0.0, 1.0, 1.0, 0.0,
        0.0, 1.5, 1.5, 0.0,
        0.0, 2.0, 2.0, 0.0,
        0.0, 2.5, 2.5, 0.0
    ]
    stop_v_ch1 = [
        0.0, 0.5, 0.5, 0.0, 0.0,
        1.0, 1.0, 0.0, 0.0,
        1.5, 1.5, 0.0, 0.0,
        2.0, 2.0, 0.0, 0.0,
        2.5, 2.5, 0.0, 0.0
    ]
    
    # Ch2 voltages (sweep DOWN)
    start_v_ch2 = [
        0.0, 0.0, 2.5, 2.5, 0.0,
        0.0, 2.0, 2.0, 0.0,
        0.0, 1.5, 1.5, 0.0,
        0.0, 1.0, 1.0, 0.0,
        0.0, 0.5, 0.5, 0.0
    ]
    stop_v_ch2 = [
        0.0, 2.5, 2.5, 0.0, 0.0,
        2.0, 2.0, 0.0, 0.0,
        1.5, 1.5, 0.0, 0.0,
        1.0, 1.0, 0.0, 0.0,
        0.5, 0.5, 0.0, 0.0
    ]
    
    # Trigger outputs (trigger on each new pulse level)
    seg_trig_out = [
        1, 0, 1, 0, 0,
        0, 1, 0, 0,
        0, 1, 0, 0,
        0, 1, 0, 0,
        0, 1, 0, 0
    ]
    
    pmu = PMU_SegArb(ip="192.168.0.10", port=8888, card="PMU1")
    
    try:
        results = pmu.run_segarb_sweep(
            v_range_ch1=10.0,
            i_range_ch1=0.2,
            dut_res_ch1=1e6,
            start_v_ch1=start_v_ch1,
            stop_v_ch1=stop_v_ch1,
            v_range_ch2=10.0,
            i_range_ch2=0.2,
            dut_res_ch2=1e6,
            start_v_ch2=start_v_ch2,
            stop_v_ch2=stop_v_ch2,
            seg_time=seg_time,
            seg_trig_out=seg_trig_out,
            max_sheet_points=5000
        )
        
        print("\nResults:")
        print(f"  Channel 1: {len(results['v_ch1'])} samples")
        print(f"  Channel 2: {len(results['v_ch2'])} samples")
        print(f"  Time range: {results['time_ch1'][0]:.2e} to {results['time_ch1'][-1]:.2e} s")
        
        return results
        
    finally:
        pmu.cleanup()


if __name__ == "__main__":
    print("Running 5-point voltage sweep example...")
    print("Ch1 sweeps UP: 0.5V -> 1V -> 1.5V -> 2V -> 2.5V")
    print("Ch2 sweeps DOWN: 2.5V -> 2V -> 1.5V -> 1V -> 0.5V")
    print()
    
    results = example_5point_voltage_sweep()
    
    # Optional: save data
    try:
        np.savez('segarb_results.npz', **results)
        print("\nSaved results to segarb_results.npz")
    except:
        pass

