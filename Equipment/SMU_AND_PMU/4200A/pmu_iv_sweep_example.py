"""
PMU IV Sweep Example - Python version of PMU_IV_sweep_Example.c

This module performs a voltage amplitude Pulse IV sweep using 2 channels of a 
single 4225-PMU card. One channel sweeps (Drain), while the other uses a fixed 
pulse amplitude (Gate).

This routine allows for independent pulse width, rise, fall and delay 
parameters to be set for the 2 channels. Note that the period is the same for 
both channels.

Based on Keithley's C example from KXCI/CLARIUS user library modules.

The measurement window is the same for both channels and is set by 
MeasStartGate and MeasStopGate (percentage of pulse top, 0.0 to 1.0).

Optional SMU available for voltage biasing of a device terminal that does 
not react to the pulse.

Features:
- Dual channel PMU pulse IV sweep
- Independent timing per channel
- Spot mean measurements (amplitude and base)
- Optional SMU bias
- Load line effect compensation
- Automatic sample rate adjustment
- Threshold checking (voltage, current, power)
"""

import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple

# Add parent directory to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Equipment.SMU_AND_PMU.ProxyClass import Proxy


class PMU_IV_Sweep:
    """PMU IV Sweep controller following Keithley C example."""
    
    # Error codes matching C example
    ERR_WRONG_CARD_ID = -17001
    ERR_CARD_ID_HANDLE = -17002
    ERR_MEAS_EARLY = -17100
    ERR_OUTPUT_ARRAY_TOO_SMALL = -17110
    
    MAX_SAMPLES_PER_ATOD = 1000000
    
    def __init__(self, ip: str = "192.168.0.10", port: int = 8888, pmu_id: str = "PMU1"):
        """Initialize PMU connection.
        
        Args:
            ip: IP address of 4200A-SCS
            port: LPT server port (default 8888)
            pmu_id: PMU card name (e.g. "PMU1")
        """
        self.ip = ip
        self.port = port
        self.pmu_id = pmu_id
        self.smu_id: Optional[str] = None
        
        # Connect to LPT server
        self.lpt = Proxy(ip, port, "lpt")
        self.param = Proxy(ip, port, "param")
        
        # Initialize connection
        self.lpt.initialize()
        self.lpt.tstsel(1)
        self.lpt.devint()
        
        # Get instrument ID
        self.card_id = self.lpt.getinstid(pmu_id)
        if self.card_id == -1:
            raise RuntimeError(f"Failed to get instrument ID for {pmu_id}")
        
        # Set return mode to actual values on overflow
        self.lpt.setmode(self.card_id, self.param.KI_LIM_MODE, self.param.KI_VALUE)
        
        print(f"Connected to {pmu_id} at {ip}:{port}")
    
    def iv_sweep(self,
                 # Gate timing parameters
                 pulse_width_gate: float = 200e-9,
                 rise_time_gate: float = 40e-9,
                 fall_time_gate: float = 40e-9,
                 delay_gate: float = 0.0,
                 
                 # Drain timing parameters
                 pulse_width_drain: float = 300e-9,
                 rise_time_drain: float = 100e-9,
                 fall_time_drain: float = 100e-9,
                 delay_drain: float = 0.0,
                 
                 # Common timing
                 period: float = 5e-6,
                 meas_start_gate: float = 0.65,
                 meas_stop_gate: float = 0.80,
                 pulse_average: int = 1,
                 
                 # Load line compensation
                 load_line_gate: bool = True,
                 load_line_drain: bool = True,
                 res_gate: float = 1e6,
                 res_drain: float = 1e6,
                 
                 # Voltages
                 ampl_v_gate: float = 2.0,
                 base_v_gate: float = 0.0,
                 start_v_drain: float = 0.0,
                 stop_v_drain: float = 5.0,
                 step_v_drain: float = 1.0,
                 base_v_drain: float = 0.0,
                 
                 # Ranges
                 v_range_gate: float = 10.0,
                 i_range_gate: float = 0.01,
                 ltd_auto_curr_gate: bool = False,
                 v_range_drain: float = 10.0,
                 i_range_drain: float = 0.2,
                 ltd_auto_curr_drain: bool = False,
                 
                 # Channels
                 gate_ch: int = 1,
                 drain_ch: int = 2,
                 
                 # Thresholds
                 threshold_curr_gate: float = 1.0,
                 threshold_volt_gate: float = 40.0,
                 threshold_pwr_gate: float = 8.0,
                 threshold_curr_drain: float = 1.0,
                 threshold_volt_drain: float = 40.0,
                 threshold_pwr_drain: float = 8.0,
                 
                 # Mode
                 pmu_mode: int = 0,  # 0=Simple, 1=Advanced
                 
                 # Optional SMU
                 smu_v: float = 0.0,
                 smu_irange: float = 0.01,
                 smu_icomp: float = 0.01,
                 smu_id: Optional[str] = None,
                 
                 # Output options
                 verbose: bool = False) -> pd.DataFrame:
        """
        Perform a dual-channel PMU IV sweep.
        
        Gate channel uses fixed amplitude, Drain channel sweeps amplitude.
        Measures spot mean at pulse amplitude and base for both channels.
        
        Args:
            pulse_width_gate: Gate pulse width (FWHM) in seconds
            rise_time_gate: Gate rise time (0 to 100%) in seconds
            fall_time_gate: Gate fall time (100 to 0%) in seconds
            delay_gate: Gate delay before pulse in seconds
            pulse_width_drain: Drain pulse width (FWHM) in seconds
            rise_time_drain: Drain rise time in seconds
            fall_time_drain: Drain fall time in seconds
            delay_drain: Drain delay in seconds
            period: Pulse period (both channels) in seconds
            meas_start_gate: Measurement window start (0.0 to 1.0, fraction of pulse top)
            meas_stop_gate: Measurement window stop (0.0 to 1.0, fraction of pulse top)
            pulse_average: Number of pulses to average
            load_line_gate: Enable load line compensation on gate
            load_line_drain: Enable load line compensation on drain
            res_gate: Gate load resistance (ohms)
            res_drain: Drain load resistance (ohms)
            ampl_v_gate: Gate pulse amplitude (volts)
            base_v_gate: Gate base voltage (volts)
            start_v_drain: Drain sweep start voltage (volts)
            stop_v_drain: Drain sweep stop voltage (volts)
            step_v_drain: Drain sweep step voltage (volts)
            base_v_drain: Drain base voltage (volts)
            v_range_gate: Gate voltage range (5, 10, or 40V)
            i_range_gate: Gate current range (amps)
            ltd_auto_curr_gate: Enable limited auto-range on gate current
            v_range_drain: Drain voltage range (5, 10, or 40V)
            i_range_drain: Drain current range (amps)
            ltd_auto_curr_drain: Enable limited auto-range on drain current
            gate_ch: Gate channel number (1 or 2)
            drain_ch: Drain channel number (1 or 2)
            threshold_curr_gate: Gate current threshold (amps)
            threshold_volt_gate: Gate voltage threshold (volts)
            threshold_pwr_gate: Gate power threshold (watts)
            threshold_curr_drain: Drain current threshold (amps)
            threshold_volt_drain: Drain voltage threshold (volts)
            threshold_pwr_drain: Drain power threshold (watts)
            pmu_mode: 0=Simple (faster), 1=Advanced (with thresholds/LLEC)
            smu_v: Optional SMU bias voltage
            smu_irange: SMU current range
            smu_icomp: SMU current compliance
            smu_id: SMU instrument name (e.g. "SMU1", or None for no SMU)
            verbose: Print debug messages
            
        Returns:
            pandas DataFrame with columns:
                - Drain_V_Ampl, Drain_I_Ampl: Drain amplitude measurements
                - Drain_V_Base, Drain_I_Base: Drain base measurements
                - Gate_V_Ampl, Gate_I_Ampl: Gate amplitude measurements
                - Gate_V_Base, Gate_I_Base: Gate base measurements
                - TimeStamp_Ampl_Gate, TimeStamp_Base_Gate: Gate timestamps
                - TimeStamp_Ampl_Drain, TimeStamp_Base_Drain: Drain timestamps
        """
        
        # Calculate number of sweep points
        num_sweep_pts = int((stop_v_drain - start_v_drain) / step_v_drain + 1)
        
        if verbose:
            print(f"PMU_IV_Sweep: Starting sweep with {num_sweep_pts} points")
        
        # Calculate timing parameters
        pulse_top_time_gate = pulse_width_gate - 0.5 * rise_time_gate - 0.5 * fall_time_gate
        pulse_top_meas_start_gate = delay_gate + rise_time_gate + (pulse_top_time_gate * meas_start_gate)
        pulse_top_meas_stop_gate = delay_gate + rise_time_gate + (pulse_top_time_gate * meas_stop_gate)
        
        pulse_top_time_drain = pulse_width_drain - 0.5 * rise_time_drain - 0.5 * fall_time_drain
        pulse_top_start_time_drain = delay_drain + rise_time_drain
        pulse_top_stop_time_drain = delay_drain + rise_time_drain + pulse_top_time_drain
        
        if verbose:
            print(f"Gate measurement window: {pulse_top_meas_start_gate:.2e} to {pulse_top_meas_stop_gate:.2e} s")
            print(f"Drain pulse top: {pulse_top_start_time_drain:.2e} to {pulse_top_stop_time_drain:.2e} s")
        
        # Check: gate measurement window must be within drain pulse top
        if (pulse_top_meas_start_gate < pulse_top_start_time_drain or 
            pulse_top_meas_start_gate > pulse_top_stop_time_drain or
            pulse_top_meas_stop_gate < pulse_top_start_time_drain or 
            pulse_top_meas_stop_gate > pulse_top_stop_time_drain):
            raise ValueError(
                f"Gate measurement window ({pulse_top_meas_start_gate:.2e} to {pulse_top_meas_stop_gate:.2e} s) "
                f"not within drain pulse top ({pulse_top_start_time_drain:.2e} to {pulse_top_stop_time_drain:.2e} s)"
            )
        
        # Calculate drain measurement percentages (synchronous with gate)
        meas_start_perc_drain = (pulse_top_meas_start_gate - delay_drain - rise_time_drain) / pulse_top_time_drain
        meas_stop_perc_drain = (pulse_top_meas_stop_gate - delay_drain - rise_time_drain) / pulse_top_time_drain
        
        if verbose:
            print(f"Drain measurement percentages: {meas_start_perc_drain:.2%} to {meas_stop_perc_drain:.2%}")
        
        # Calculate sample rate
        pulse_base_time_gate = period - pulse_width_gate - 0.5 * (rise_time_gate - fall_time_gate) - delay_gate
        pulse_top_meas_time_gate = (meas_stop_gate - meas_start_gate) * pulse_top_time_gate
        num_samples_top_gate = int(pulse_top_meas_time_gate / 5e-9 + 1e-7 + 1)
        pulse_base_meas_time_gate = (meas_stop_gate - meas_start_gate) * pulse_base_time_gate
        num_samples_base_gate = int(pulse_base_meas_time_gate / 5e-9 + 1e-7 + 1)
        num_samples_period_gate = num_samples_top_gate + num_samples_base_gate
        num_samples_sweep_gate = num_sweep_pts * num_samples_period_gate
        
        sample_rate = 200e6
        if num_samples_sweep_gate > self.MAX_SAMPLES_PER_ATOD:
            rate_factor = int(num_samples_sweep_gate / self.MAX_SAMPLES_PER_ATOD) + 1
            sample_rate = sample_rate / rate_factor
            if verbose:
                print(f"Reduced sample rate by {rate_factor}x to {sample_rate/1e6:.1f} MSa/s")
        
        # Setup SMU if specified
        smu_present = False
        smu_inst_id = None
        if smu_id and smu_id.upper() != "NONE":
            try:
                smu_inst_id = self.lpt.getinstid(smu_id)
                if smu_inst_id != -1:
                    self.lpt.rangei(smu_inst_id, smu_irange)
                    self.lpt.limiti(smu_inst_id, smu_icomp)
                    self.lpt.forcev(smu_inst_id, smu_v)
                    smu_present = True
                    if verbose:
                        print(f"SMU {smu_id} configured: {smu_v}V, {smu_irange}A range")
            except Exception as e:
                print(f"Warning: SMU setup failed: {e}")
        
        # Configure RPMs if present
        try:
            self.lpt.rpm_config(self.card_id, gate_ch, self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
            self.lpt.rpm_config(self.card_id, drain_ch, self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
        except Exception:
            pass
        
        # Initialize pulse mode
        self.lpt.pg2_init(self.card_id, self.param.PULSE_MODE_PULSE)
        
        # Set sample rate
        self.lpt.pulse_sample_rate(self.card_id, sample_rate)
        
        # Configure gate channel ranges
        if ltd_auto_curr_gate:
            self.lpt.pulse_ranges(self.card_id, gate_ch,
                                 v_range_gate, self.param.PULSE_MEAS_FIXED, v_range_gate,
                                 self.param.PULSE_MEAS_LTD_AUTO, i_range_gate)
        else:
            self.lpt.pulse_ranges(self.card_id, gate_ch,
                                 v_range_gate, self.param.PULSE_MEAS_FIXED, v_range_gate,
                                 self.param.PULSE_MEAS_FIXED, i_range_gate)
        
        # Configure drain channel ranges
        if ltd_auto_curr_drain:
            self.lpt.pulse_ranges(self.card_id, drain_ch,
                                 v_range_drain, self.param.PULSE_MEAS_FIXED, v_range_drain,
                                 self.param.PULSE_MEAS_LTD_AUTO, i_range_drain)
        else:
            self.lpt.pulse_ranges(self.card_id, drain_ch,
                                 v_range_drain, self.param.PULSE_MEAS_FIXED, v_range_drain,
                                 self.param.PULSE_MEAS_FIXED, i_range_drain)
        
        # Set load resistance (if load line compensation disabled or simple mode)
        if not load_line_gate or pmu_mode == 0:
            self.lpt.pulse_load(self.card_id, gate_ch, res_gate)
        
        if not load_line_drain or pmu_mode == 0:
            self.lpt.pulse_load(self.card_id, drain_ch, res_drain)
        
        # Set pulse timing for gate
        self.lpt.pulse_source_timing(self.card_id, gate_ch, 
                                     period, delay_gate, pulse_width_gate, 
                                     rise_time_gate, fall_time_gate)
        
        # Set pulse timing for drain
        self.lpt.pulse_source_timing(self.card_id, drain_ch,
                                     period, delay_drain, pulse_width_drain,
                                     rise_time_drain, fall_time_drain)
        
        # Set thresholds (test-ending conditions)
        self.lpt.pulse_limits(self.card_id, gate_ch, 
                             threshold_volt_gate, threshold_curr_gate, threshold_pwr_gate)
        self.lpt.pulse_limits(self.card_id, drain_ch,
                             threshold_volt_drain, threshold_curr_drain, threshold_pwr_drain)
        
        # Set measurement timing for gate
        self.lpt.pulse_meas_timing(self.card_id, gate_ch,
                                   meas_start_gate, meas_stop_gate, pulse_average)
        
        # Set measurement timing for drain
        self.lpt.pulse_meas_timing(self.card_id, drain_ch,
                                   meas_start_perc_drain, meas_stop_perc_drain, pulse_average)
        
        # Enable spot mean measurements on gate
        self.lpt.pulse_meas_sm(self.card_id, gate_ch,
                              self.param.PULSE_ACQ_PBURST,
                              acquire_meas_v_ampl=1, acquire_meas_v_base=1,
                              acquire_meas_i_ampl=1, acquire_meas_i_base=1,
                              acquire_time_stamp=1,
                              llecomp=1 if load_line_gate else 0)
        
        # Enable spot mean measurements on drain
        self.lpt.pulse_meas_sm(self.card_id, drain_ch,
                              self.param.PULSE_ACQ_PBURST,
                              acquire_meas_v_ampl=1, acquire_meas_v_base=1,
                              acquire_meas_i_ampl=1, acquire_meas_i_base=1,
                              acquire_time_stamp=1,
                              llecomp=1 if load_line_drain else 0)
        
        # Program drain base voltage (needed for amplitude sweep)
        self.lpt.pulse_vlow(self.card_id, drain_ch, base_v_drain)
        
        # Set gate to fixed pulse train
        self.lpt.pulse_train(self.card_id, gate_ch, base_v_gate, ampl_v_gate)
        
        # Set drain to sweep amplitude
        self.lpt.pulse_sweep_linear(self.card_id, drain_ch,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    start_v_drain, stop_v_drain, step_v_drain)
        
        # Enable outputs
        self.lpt.pulse_output(self.card_id, gate_ch, 1)
        self.lpt.pulse_output(self.card_id, drain_ch, 1)
        
        if verbose:
            print("Executing pulse sweep...")
        
        # Execute test
        test_mode = self.param.PULSE_MODE_SIMPLE if pmu_mode == 0 else self.param.PULSE_MODE_ADVANCED
        self.lpt.pulse_exec(test_mode)
        
        # Wait for completion
        while True:
            status, elapsed = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            time.sleep(0.1)
        
        if verbose:
            print(f"Sweep complete (elapsed: {elapsed:.3f}s), fetching data...")
        
        # Fetch measurements (returns both amplitude and base, interleaved)
        gate_v_all, gate_i_all, gate_t_all, gate_s_all = self.lpt.pulse_fetch(
            self.card_id, gate_ch, 0, num_sweep_pts * 2 - 1)
        
        drain_v_all, drain_i_all, drain_t_all, drain_s_all = self.lpt.pulse_fetch(
            self.card_id, drain_ch, 0, num_sweep_pts * 2 - 1)
        
        # Convert to numpy arrays
        gate_v_all = np.array(gate_v_all)
        gate_i_all = np.array(gate_i_all)
        gate_t_all = np.array(gate_t_all)
        drain_v_all = np.array(drain_v_all)
        drain_i_all = np.array(drain_i_all)
        drain_t_all = np.array(drain_t_all)
        
        # Separate amplitude (even indices) and base (odd indices)
        gate_v_high = gate_v_all[0::2]
        gate_i_high = gate_i_all[0::2]
        gate_t_high = gate_t_all[0::2]
        gate_v_low = gate_v_all[1::2]
        gate_i_low = gate_i_all[1::2]
        gate_t_low = gate_t_all[1::2]
        
        drain_v_high = drain_v_all[0::2]
        drain_i_high = drain_i_all[0::2]
        drain_t_high = drain_t_all[0::2]
        drain_v_low = drain_v_all[1::2]
        drain_i_low = drain_i_all[1::2]
        drain_t_low = drain_t_all[1::2]
        
        # Turn off SMU if present
        if smu_present and smu_inst_id is not None:
            try:
                self.lpt.forcev(smu_inst_id, 0.0)
            except Exception:
                pass
        
        # Build result DataFrame
        df = pd.DataFrame({
            'Drain_V_Ampl': drain_v_high[:num_sweep_pts],
            'Drain_I_Ampl': drain_i_high[:num_sweep_pts],
            'Drain_V_Base': drain_v_low[:num_sweep_pts],
            'Drain_I_Base': drain_i_low[:num_sweep_pts],
            'Gate_V_Ampl': gate_v_high[:num_sweep_pts],
            'Gate_I_Ampl': gate_i_high[:num_sweep_pts],
            'Gate_V_Base': gate_v_low[:num_sweep_pts],
            'Gate_I_Base': gate_i_low[:num_sweep_pts],
            'TimeStamp_Ampl_Gate': gate_t_high[:num_sweep_pts],
            'TimeStamp_Base_Gate': gate_t_low[:num_sweep_pts],
            'TimeStamp_Ampl_Drain': drain_t_high[:num_sweep_pts],
            'TimeStamp_Base_Drain': drain_t_low[:num_sweep_pts],
        })
        
        if verbose:
            print(f"Fetched {len(df)} sweep points")
        
        return df
    
    def cleanup(self):
        """Clean shutdown."""
        try:
            self.lpt.pulse_output(self.card_id, 1, 0)
            self.lpt.pulse_output(self.card_id, 2, 0)
        except Exception:
            pass
        try:
            self.lpt.dev_abort()
        except Exception:
            pass
        try:
            self.lpt.tstdsl()
            self.lpt.devint()
        except Exception:
            pass


def example_two_terminal_iv():
    """
    Example: Two-terminal device IV sweep (DEFAULT)
    
    Simple voltage sweep across a two-terminal device (memristor, resistor, diode, etc.)
    Channel 1 is swept, Channel 2 held at 0V (acts as ground return).
    
    This is the recommended starting point for most measurements.
    """
    pmu = PMU_IV_Sweep(ip="192.168.0.10", port=8888, pmu_id="PMU1")
    
    try:
        results = pmu.iv_sweep(
            # Channel 1 (ground return - held at 0V) - "gate" in the sweep terminology
            pulse_width_gate=1e-6,    # 1us pulse (conservative)
            rise_time_gate=50e-9,     # 50ns rise (safe for 10V range)
            fall_time_gate=50e-9,     # 50ns fall
            delay_gate=0.0,
            ampl_v_gate=0.0,          # Held at 0V (ground reference)
            base_v_gate=0.0,
            gate_ch=1,
            
            # Channel 2 (swept voltage - DUT terminal) - "drain" in the sweep terminology
            pulse_width_drain=1e-6,   # 1us pulse (matches ch1)
            rise_time_drain=50e-9,    # 50ns rise
            fall_time_drain=50e-9,    # 50ns fall
            delay_drain=0.0,
            start_v_drain=-1.0,       # Sweep from -1V to +1V
            stop_v_drain=1.0,
            step_v_drain=0.2,         # 0.2V steps = 11 points
            base_v_drain=0.0,
            drain_ch=2,
            
            # Timing (common)
            period=10e-6,             # 10us period (plenty of settling time)
            meas_start_gate=0.3,      # Measure at 30-70% of pulse (well settled)
            meas_stop_gate=0.7,
            pulse_average=1,
            
            # Ranges (adjust based on your device)
            v_range_gate=10.0,
            i_range_gate=0.01,        # 10mA range (channel 1)
            v_range_drain=10.0,
            i_range_drain=0.01,       # 10mA range (channel 2)
            
            # Load resistance (50 ohm for standard termination)
            res_gate=50.0,
            res_drain=50.0,
            
            # Disable load line compensation in simple mode
            load_line_gate=False,
            load_line_drain=False,
            
            # Mode
            pmu_mode=0,  # Simple mode for speed
            
            verbose=True
        )
        
        print("\n" + "="*60)
        print("TWO-TERMINAL IV SWEEP RESULTS")
        print("="*60)
        
        # Extract the useful columns for two-terminal device
        # Channel 1 (Drain) is the swept channel
        two_term_results = pd.DataFrame({
            'V (V)': results['Drain_V_Ampl'],
            'I (A)': results['Drain_I_Ampl'],
            'Time (s)': results['TimeStamp_Ampl_Drain']
        })
        
        # Calculate resistance
        two_term_results['R (Ohm)'] = two_term_results['V (V)'] / two_term_results['I (A)'].replace(0, np.nan)
        
        print("\nMeasurements:")
        print(two_term_results.to_string(index=False))
        
        print(f"\nAverage Resistance: {two_term_results['R (Ohm)'].mean():.2e} Ohm")
        
        return two_term_results
        
    finally:
        pmu.cleanup()


def example_transistor_iv():
    """
    Example: Transistor-style IV sweep (3-terminal device)
    
    Gate held at 2V, drain swept from 0 to 5V in 1V steps.
    Measures Id-Vd curves at fixed Vg.
    """
    pmu = PMU_IV_Sweep(ip="192.168.0.10", port=8888, pmu_id="PMU1")
    
    try:
        results = pmu.iv_sweep(
            # Gate (held constant)
            pulse_width_gate=200e-9,
            rise_time_gate=40e-9,
            fall_time_gate=40e-9,
            ampl_v_gate=2.0,
            base_v_gate=0.0,
            
            # Drain (swept)
            pulse_width_drain=300e-9,
            rise_time_drain=100e-9,
            fall_time_drain=100e-9,
            start_v_drain=0.0,
            stop_v_drain=5.0,
            step_v_drain=1.0,
            base_v_drain=0.0,
            
            # Timing
            period=5e-6,
            meas_start_gate=0.65,
            meas_stop_gate=0.80,
            pulse_average=1,
            
            # Ranges
            v_range_gate=10.0,
            i_range_gate=0.01,
            v_range_drain=10.0,
            i_range_drain=0.2,
            
            # Channels
            gate_ch=1,
            drain_ch=2,
            
            # Mode
            pmu_mode=0,  # Simple mode for speed
            
            verbose=True
        )
        
        print("\nResults:")
        print(results)
        
        # Calculate resistances
        results['R_Drain_Ampl'] = results['Drain_V_Ampl'] / results['Drain_I_Ampl'].replace(0, np.nan)
        
        print("\nDrain amplitude resistance:")
        print(results[['Drain_V_Ampl', 'Drain_I_Ampl', 'R_Drain_Ampl']])
        
        return results
        
    finally:
        pmu.cleanup()


if __name__ == "__main__":
    print("PMU IV Sweep Example")
    print("=" * 60)
    print()
    print("Running TWO-TERMINAL device IV sweep (DEFAULT)")
    print("  Channel 1 (DUT+): -1V to +1V in 0.2V steps")
    print("  Channel 2 (DUT-): Held at 0V (ground return)")
    print()
    print("Connect your device between PMU Channel 1 and Channel 2")
    print()
    
    # Run the two-terminal example (DEFAULT)
    results = example_two_terminal_iv()
    
    # Optional: save results
    try:
        results.to_csv('pmu_iv_sweep_results.csv', index=False)
        print("\nSaved results to pmu_iv_sweep_results.csv")
    except Exception as e:
        print(f"Could not save CSV: {e}")
    
    print("\n" + "="*60)
    print("To run the transistor (3-terminal) example instead,")
    print("call: example_transistor_iv()")
    print("="*60)


