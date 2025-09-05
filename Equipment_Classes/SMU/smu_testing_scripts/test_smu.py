from pathlib import Path
import time
import argparse

from Equipment_Classes.SMU.Keithley4200A import Keithley4200AController
from measurement_service import MeasurementService


def main():
    parser = argparse.ArgumentParser(description="Simple SMU test script for Keithley 4200A")
    parser.add_argument("address", nargs="?", default="192.168.0.10:8888|SMU1",
                        help="LPT address for the 4200A (e.g. 192.168.0.10:8888|SMU1)")
    parser.add_argument("--icc", type=float, default=1e-3, help="compliance current (A)")
    args = parser.parse_args()

    print(f"Connecting to SMU at {args.address} ...")
    keithley = Keithley4200AController(args.address)
    service = MeasurementService()

    try:
        print("Running IV sweep - simple test")
        v_arr, i_arr, t_arr = service.run_iv_sweep(
            keithley=keithley,
            icc=args.icc,
            sweeps=1,
            step_delay=0.05,
            start_v=-1.0,
            stop_v=1.0,
            step_v=0.5,
            sweep_type="FS",
        )
        print(f"IV sweep returned {len(v_arr)} points; sample: {list(zip(v_arr, i_arr, t_arr))[:5]}")

        print("Running pulse measurement - simple test")
        v_p, i_p, t_p = service.run_pulse_measurement(
            keithley=keithley,
            pulse_voltage=1.0,
            pulse_width_ms=1.0,
            num_pulses=5,
            read_voltage=0.1,
            inter_pulse_delay_s=0.01,
            icc=args.icc,
            smu_type="Keithley 4200A",
        )
        print(f"Pulse measurement returned {len(v_p)} points; sample: {list(zip(v_p, i_p, t_p))[:5]}")

    except Exception as exc:
        print(f"Error during tests: {exc}")
    finally:
        try:
            keithley.set_voltage(0, args.icc)
            keithley.enable_output(False)
        except Exception:
            pass
        try:
            keithley.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()


