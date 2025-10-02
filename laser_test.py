from Equipment.SMU_AND_PMU.Keithley4200A import Keithley4200A_PMUDualChannel
from Equipment.function_generator_manager import FunctionGeneratorManager
from Measurments.measurement_services_pmu import MeasurementServicesPMU
import os
import json
from datetime import datetime
VISA_RESOURCE = "USB0::0xF4EC::0x1103::SDG1XCAQ3R3184::INSTR"

pmu = Keithley4200A_PMUDualChannel("192.168.0.10:8888|PMU1")
gen = FunctionGeneratorManager(fg_type="Siglent SDG1032X", address=VISA_RESOURCE, auto_connect=True)
ms_pmu = MeasurementServicesPMU(pmu=pmu, function_generator=gen)




## Deprecated: software-only sequencing helper removed with orchestrator

pmu_params = {
    "amplitude_v": 0.5,
    "width_s": 5e-6, #increasing this will significantly increase the time to complete the measurement
    "period_s": 2e-5, #increasing this will significantly increase the time to complete the measurement
    "num_pulses": 100,
    "source_channel": 1,
    "force_fixed_ranges": True,
    "v_meas_range": 2.0,
    "i_meas_range": 200e-6,
    # optional PMU output delay:
    # "delay_s": 0.0002,
}
# pmu_params = {
#     "amplitude_v": 0.2,
#     "width_s": 500e-5,
#     "period_s": 100e-4,
#     "num_pulses": 1,
#     "source_channel": 1,
#     "force_fixed_ranges": True,
#     "v_meas_range": 2.0,
#     "i_meas_range": 200e-6,
#     # optional PMU output delay:
#     # "delay_s": 0.0002,
# }

fg_params = {
    "channel": 1,
    "high_level_v": 1,
    "low_level_v": 0.0,
    "period_s": 100,           # 1 Hz → 1 s period
    "pulse_width_s": 0.01,   # 20000 µs
    #"duty_pct": 0.02,
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
import time
a=time.time()
print("Starting measurement: be patient on the readings it can take a while >60s if you use wide pulses and high number of pulses")
df = ms_pmu.Single_Laser_Pulse_with_read(
    pmu_peramiter=pmu_params,
    fg_peramiter=fg_params,
    timeout_s=60,
)

# maybe add in a way to check range on that first pulse, pulse once, find current and range and set the range based on that.
#df = coord.Single_Laser_Pulse_with_read(timeout_s=15.0)
b=time.time()
print("Time taken: ", b-a)
print(df.head())

# Save DataFrame to a timestamped TXT with header including parameters
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = os.path.join(os.path.dirname(__file__), "Data_save_loc", "testing_again", "F", "2", "PMU measurments")
os.makedirs(out_dir, exist_ok=True)

# Build header with parameters and derived pulse information
derived_duty = None
try:
    period_s = fg_params.get("period_s")
    pulse_width_s = fg_params.get("pulse_width_s")
    if period_s and pulse_width_s:
        derived_duty = pulse_width_s / period_s
except Exception:
    derived_duty = None

header_lines = [
    f"# Measurement: Single_Laser_Pulse",
    f"# Timestamp: {datetime.now().isoformat(timespec='seconds')}",
    f"# PMU parameters: {json.dumps(pmu_params)}",
    f"# FG parameters: {json.dumps(fg_params)}",
]
if derived_duty is not None:
    header_lines.append(f"# Derived duty_cycle: {derived_duty:.6f} (fraction)")

file_base = f"0-Single_Laser_Pulse-{timestamp}"
data_path = os.path.join(out_dir, f"{file_base}.txt")

with open(data_path, "w", encoding="utf-8") as f:
    f.write("\n".join(header_lines) + "\n")

# Append the DataFrame as tab-separated values below the header
df.to_csv(data_path, sep="\t", index=False, mode="a")

print(f"Saved measurement to: {data_path}")