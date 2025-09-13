from Equipment_Classes.SMU.Keithley4200A import Keithley4200A_PMUDualChannel
from Equipment_Classes.function_generator_manager import FunctionGeneratorManager
from measurement_services_pmu import MeasurementServicesPMU
VISA_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"

pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")
gen = FunctionGeneratorManager(fg_type="Siglent SDG1032X", address=VISA_RESOURCE, auto_connect=True)
ms_pmu = MeasurementServicesPMU(pmu=pmu, function_generator=gen)




## Deprecated: software-only sequencing helper removed with orchestrator


pmu_params = {
    "amplitude_v": 0.4,
    "width_s": 50e-6,
    "period_s": 200e-6,
    "num_pulses": 100,
    "source_channel": 1,
    "force_fixed_ranges": True,
    "v_meas_range": 2.0,
    "i_meas_range": 200e-6,
    # optional PMU output delay:
    # "delay_s": 0.0002,
}

fg_params = {
    "channel": 1,
    "high_level_v": 1.5,
    "low_level_v": 0.0,
    "period_s": 1.0,           # 1 Hz → 1 s period
    "pulse_width_s": 0.0002,   # 200 µs
    "duty_pct": 0.02,
    "rise_s": 1.68e-08,
    "fall_s": 1.68e-08,
    #"delay_s": 0.0, # delay of anything causes an error defualts on the machine to 1s
    "mode": "NCYC",
    "cycles": 1,
    "trigger_source": "EXT",

}

"""Current issue of delay not working correctly the system wont accept delay of >0
    work around for now, set delay on the system instead? 
    we may be able to set a minus delay on the system instead? not sure!
"""

df = ms_pmu.Measure_at_voltage_with_laser_Using_trigger_out_pmu(
    pmu_peramiter=pmu_params,
    fg_peramiter=fg_params,
    timeout_s=15.0,
)
# maybe add in a way to check range on that first pulse, pulse once, find current and range and set the range based on that.
#df = coord.Measure_at_voltage_with_laser_Using_trigger_out_pmu(timeout_s=15.0)

print(df.head())