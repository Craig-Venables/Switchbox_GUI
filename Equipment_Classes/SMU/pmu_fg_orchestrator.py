from __future__ import annotations

import time
from typing import Any, Literal

from Equipment_Classes.SMU.keitheley4200a3_workingpulse import Keithley4200A_PMUDualChannel
from Equipment_Classes.function_generator_manager import FunctionGeneratorManager
import pandas as pd


class PMUFGSoftwareOrchestrator:
    """Compose PMU and FunctionGeneratorManager with software-only sequencing.

    - All LPT/PMU calls remain inside Keithley4200A_PMUDualChannel.
    - This class only coordinates call order and optional software delays.
    """

    def __init__(self, pmu: Keithley4200A_PMUDualChannel, gen: FunctionGeneratorManager) -> None:
        self.pmu = pmu
        self.gen = gen

    def get_gen_ready(
        self,
        channel: int = 1,
        high_level_v: Any = 3.0,
        low_level_v: Any = 0.0,
        pulse_width_s: Any = 50e-6,
        frequency_hz: Any = 1e3,
        burst_cycles: int = 1,
    ) -> None:
        """Prepare the function generator for a single pulse using BUS trigger.

        - Leaves output ON so a subsequent software trigger fires immediately.
        """
        self.gen.set_pulse_shape(
            channel=channel,
            frequency_hz=frequency_hz,
            high_level_v=high_level_v,
            low_level_v=low_level_v,
            pulse_width_s=pulse_width_s,
        )
        self.gen.enable_burst(
            channel=channel,
            mode="NCYC",
            cycles=int(max(1, burst_cycles)),
            trigger_source="BUS",
        )
        self.gen.output(channel, True)

    def start_gen(self, channel: int = 1) -> None:
        self.gen.trigger_now(channel)

    def measure_at_voltage_with_laser_NO_TRIGGER_SOFTWEAR_ONLY(
        self,
        pmu_peramiter: dict,
        fg_peramiter: dict,
        start_order: Literal["pmu_first", "fg_first"] = "pmu_first",
        skew_s: float = 0.0,
        timeout_s: float = 10.0,
    ) -> pd.DataFrame:
        """Prepare PMU and FG, start in software order, wait, and fetch PMU data.

        - pmu_peramiter: keys like amplitude_v, base_v, width_s, period_s,
          meas_start_pct, meas_stop_pct, source_channel, hold_other_at_zero,
          force_fixed_ranges, v_meas_range, i_meas_range, num_pulses (default 100).
        - fg_peramiter: keys like channel, high_level_v, low_level_v, frequency_hz.
          A single 500 ms pulse (burst_cycles=1, pulse_width_s=0.5) is enforced.
        - Function generator output is turned OFF at the end.
        """
        # Extract PMU params with defaults
        amplitude_v = float(pmu_peramiter.get("amplitude_v"))
        base_v = float(pmu_peramiter.get("base_v", 0.0))
        width_s = float(pmu_peramiter.get("width_s", 10e-6))
        period_s = float(pmu_peramiter.get("period_s", 20e-6))
        meas_start_pct = float(pmu_peramiter.get("meas_start_pct", 0.1))
        meas_stop_pct = float(pmu_peramiter.get("meas_stop_pct", 0.9))
        source_channel = int(pmu_peramiter.get("source_channel", 1))
        hold_other_at_zero = bool(pmu_peramiter.get("hold_other_at_zero", True))
        force_fixed_ranges = bool(pmu_peramiter.get("force_fixed_ranges", False))
        v_meas_range = float(pmu_peramiter.get("v_meas_range", 10.0))
        i_meas_range = float(pmu_peramiter.get("i_meas_range", 100e-6))
        num_pulses = int(pmu_peramiter.get("num_pulses", 100))

        # Extract FG params and enforce single 500 ms pulse
        fg_channel = int(fg_peramiter.get("channel", 1))
        fg_high_level_v = fg_peramiter.get("high_level_v", 3.0)
        fg_low_level_v = fg_peramiter.get("low_level_v", 0.0)
        fg_frequency_hz = fg_peramiter.get("frequency_hz", 1e3)
        fg_burst_cycles = 1
        fg_pulse_width_s = 0.5

        # Prepare PMU
        self.pmu.prepare_measure_at_voltage(
            amplitude_v=amplitude_v,
            base_v=base_v,
            width_s=width_s,
            period_s=period_s,
            meas_start_pct=meas_start_pct,
            meas_stop_pct=meas_stop_pct,
            source_channel=source_channel,
            hold_other_at_zero=hold_other_at_zero,
            force_fixed_ranges=force_fixed_ranges,
            v_meas_range=v_meas_range,
            i_meas_range=i_meas_range,
            num_pulses=num_pulses,
            outputs_on=True,
        )

        # Prepare FG
        self.get_gen_ready(
            channel=fg_channel,
            high_level_v=fg_high_level_v,
            low_level_v=fg_low_level_v,
            pulse_width_s=fg_pulse_width_s,
            frequency_hz=fg_frequency_hz,
            burst_cycles=fg_burst_cycles,
        )

        try:
            # Start in software order
            if start_order == "pmu_first":
                print("Starting PMU first")
                self.pmu.start()
                if float(skew_s) > 0:
                    time.sleep(float(skew_s))
                self.start_gen(channel=fg_channel)
            else:
                self.start_gen(channel=fg_channel)
                if float(skew_s) > 0:
                    time.sleep(float(skew_s))
                self.pmu.start()

            # Wait and fetch
            self.pmu.wait(timeout_s=float(timeout_s))
            return self.pmu.fetch(channel=int(source_channel))
        finally:
            # Ensure FG output is OFF when done
            try:
                self.gen.output(int(fg_channel), False)
            except Exception:
                pass

    def Measure_at_voltage_with_laser_Using_trigger_out_pmu( 
        self,
        pmu_peramiter: dict | None,
        fg_peramiter: dict | None,
        timeout_s: float = 10.0,):

        """requires pmu trigger out and pulse from fg to be very specific
        period = 
        width = > measure time
        """

        # Defaults from working examples (PMU) and provided FG snapshot
        pmu_defaults = {
            "amplitude_v": 0.25,
            "base_v": 0.0,
            "width_s": 50e-6,
            "period_s": 200e-6,
            "meas_start_pct": 0.1,
            "meas_stop_pct": 0.9,
            "source_channel": 1,
            "hold_other_at_zero": True,
            "force_fixed_ranges": True,
            "v_meas_range": 2.0,
            "i_meas_range": 200e-6,
            "num_pulses": 100,
            "delay_s": None,
        }
        fg_defaults = {
            "channel": 1,
            "high_level_v": 1.5,
            "low_level_v": 0.0,
            "period_s": 1.0,
            "pulse_width_s": 0.0002,
            "duty_pct": 0.02,
            "rise_s": 1.68e-08,
            "fall_s": 1.68e-08,
            #"delay_s": 0.01,
            "mode": "NCYC",
            "cycles": 1,
            "trigger_source": "EXT",
            "burst_delay_s": 3.41e-07,
        }

        pmu_cfg = {**pmu_defaults, **(pmu_peramiter or {})}
        fg_cfg = {**fg_defaults, **(fg_peramiter or {})}

        amplitude_v = float(pmu_cfg["amplitude_v"]) 
        base_v = float(pmu_cfg["base_v"]) 
        width_s = float(pmu_cfg["width_s"]) 
        period_s = float(pmu_cfg["period_s"]) 
        meas_start_pct = float(pmu_cfg["meas_start_pct"]) 
        meas_stop_pct = float(pmu_cfg["meas_stop_pct"]) 
        source_channel = int(pmu_cfg["source_channel"]) 
        hold_other_at_zero = bool(pmu_cfg["hold_other_at_zero"]) 
        force_fixed_ranges = bool(pmu_cfg["force_fixed_ranges"]) 
        v_meas_range = float(pmu_cfg["v_meas_range"]) 
        i_meas_range = float(pmu_cfg["i_meas_range"]) 
        num_pulses = int(pmu_cfg["num_pulses"]) 
        delay_s = pmu_cfg["delay_s"]

        # FG config from provided snapshot
        fg_channel = int(fg_cfg["channel"])
        fg_high_level_v = fg_cfg["high_level_v"]
        fg_low_level_v = fg_cfg["low_level_v"]
        # Convert period to frequency for driver API
        period_s_val = float(fg_cfg["period_s"]) if fg_cfg.get("period_s") is not None else 1.0
        fg_frequency_hz = (1.0 / period_s_val) if period_s_val else 1.0
        fg_pulse_width_s = fg_cfg["pulse_width_s"]
        fg_duty_pct = fg_cfg["duty_pct"]
        fg_rise_s = fg_cfg["rise_s"]
        fg_fall_s = fg_cfg["fall_s"]
        #fg_delay_s = fg_cfg["delay_s"]
        fg_mode = str(fg_cfg["mode"]).upper()
        fg_cycles = int(fg_cfg["cycles"])
        fg_trigger_source = str(fg_cfg["trigger_source"]).upper()
        
        
        # Prepare PMU
        self.pmu.prepare_measure_at_voltage(
            amplitude_v=amplitude_v,
            base_v=base_v,
            width_s=width_s,
            period_s=period_s,
            meas_start_pct=meas_start_pct,
            meas_stop_pct=meas_stop_pct,
            source_channel=source_channel,
            hold_other_at_zero=hold_other_at_zero,
            force_fixed_ranges=force_fixed_ranges,
            v_meas_range=v_meas_range,
            i_meas_range=i_meas_range,
            num_pulses=num_pulses,
            delay_s=delay_s,
            outputs_on=True,
        )

        # Prepare FG with full shape + EXT burst
        self.gen.set_pulse_shape(
            channel=fg_channel,
            frequency_hz=fg_frequency_hz,
            high_level_v=fg_high_level_v,
            low_level_v=fg_low_level_v,
            pulse_width_s=fg_pulse_width_s,
            duty_pct=fg_duty_pct,
            rise_s=fg_rise_s,
            fall_s=fg_fall_s,
            #delay_s=fg_delay_s,
        )
        self.gen.enable_burst(
            channel=fg_channel,
            mode=fg_mode,
            cycles=fg_cycles,
            trigger_source=fg_trigger_source,

        )
        #self.gen.output(fg_channel, True)

        # Enable PMU TRIG OUT so FG (TRSR=EXT) can be driven by PMU
        try:
            self.pmu.set_trigger_polarity(1)
        except Exception:
            pass
        try:
            self.pmu.set_trigger_output(True)
        except Exception:
            pass

        
        # Check if FG output is currently on
        fg_output_status = self.gen.get_output_status(fg_channel)
        
        laser = True

        if not fg_output_status:
            
            print("WARNING: Function generator output is currently OFF.")
            print("Please turn OFF the laser manually before proceeding.")
            input("Press Enter once you have turned OFF the laser...")
            laser_on = False
        
        # Turn on FG output to prevent transients
        self.gen.output(fg_channel, True)

        if not laser:
            print("Please turn the laser back on, Function generator is Armed")
            input("Press Enter once you have turned OFF the laser...")
        
        

        # give function generator time to settle
        print("sleeping for 2 seconds  ")
        time.sleep(2)

        self.pmu.start()
        self.pmu.wait(timeout_s=float(timeout_s))
        df = self.pmu.fetch(channel=int(source_channel)) 

        print("##################")
        print("dont forget delay is disabled youn need to manualy input!")
        print("##################")
        return df









# # settings for fg for pulse read with laser #

# fg_peramiter = {
#   "channel": 1,
#   "pulse_shape": {
#     "frequency_hz": 1.0,
#     "high_level_v": 1.5,
#     "low_level_v": 0.0,
#     "pulse_width_s": 0.0002,
#     "duty_pct": 0.02,
#     "rise_s": 1.68e-08,
#     "fall_s": 1.68e-08,
#     "delay_s": 0.0101,
#   },
#   "burst": {
#     "mode": "NCYC",
#     "cycles": 1,
#     "trigger_source": "EXT",
#     "burst_delay_s": 3.41e-07,
#   },
#   "output_on": True,
# }
# # Apply:
# #gen.set_pulse_shape(channel=fg_peramiter["channel"], **fg_peramiter["pulse_shape"])
# #gen.enable_burst(channel=fg_peramiter["channel"], **fg_peramiter["burst"])
# #gen.output(fg_peramiter["channel"], fg_peramiter["output_on"])


# {
#   "idn": "Siglent Technologies,SDG1032X,SDG1XCAQ3R3184,1.01.01.33R1B5",
#   "channel": 1,
#   "output": "C1:OUTP ON,LOAD,50,PLRT,NOR",
#   "bswv": {
#     "C1:BSWV WVTP": "PULSE",
#     "FRQ": "1HZ",
#     "PERI": "1S",
#     "AMP": "1.5V",
#     "AMPVRMS": "0.75Vrms",
#     "AMPDBM": "10.5115dBm",
#     "OFST": "0.75V",
#     "HLEV": "1.5V",
#     "LLEV": "0V",
#     "DUTY": "0.02",
#     "WIDTH": "0.0002",
#     "RISE": "1.68e-08S",
#     "FALL": "1.68e-08S",
#     "DLY": "0.0101"
#   },
#   "btwv": {
#     "C1:BTWV STATE": "ON",
#     "TRSR": "EXT",
#     "TIME": "1",
#     "DLAY": "3.41e-07S",
#     "EDGE": "RISE",
#     "GATE_NCYC": "NCYC",
#     "CARR": "WVTP",
#     "PULSE": "FRQ",
#     "1HZ": "AMP",
#     "1.5V": "AMPVRMS",
#     "0.75VRMS": "AMPDBM",
#     "10.5115DBM": "OFST",
#     "0.75V": "DUTY",
#     "0.02": "RISE",
#     "1.68E-08S": "DLY"
#   },
#   "arwv": "C1:ARWV INDEX,3,NAME,StairDn",
#   "error": "-113,Undefined header,C1:TRIG"
# }
