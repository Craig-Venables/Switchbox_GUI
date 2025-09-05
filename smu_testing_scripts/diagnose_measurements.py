"""Diagnostic script to read raw measurement returns from the 4200A (SMU/PMU)

Usage examples:
  python smu_testing_scripts/diagnose_measurements.py --smu 192.168.0.10:8888|SMU1
  python smu_testing_scripts/diagnose_measurements.py --pmu 192.168.0.10:8888|PMU1-CH1
"""
from pathlib import Path
import argparse
import time

from Equipment_Classes.SMU.Keithley4200A import Keithley4200AController, Keithley4200A_PMUController


def diagnose_smu(address: str, icc: float = 1e-3):
    print(f"Connecting to SMU at {address}")
    k = Keithley4200AController(address)
    try:
        print("Setting 0V and measuring baseline")
        k.set_voltage(0, icc)
        time.sleep(0.05)
        raw = k.lpt.intgi(k._instr_id)
        print("Raw intgi result:", raw, type(raw))
        val = k.measure_current()
        print("measure_current() returned:", val, type(val))
        print("Interpreted float current (A):", float(val))

        print("Now sourcing 0.5V and reading current")
        k.set_voltage(0.5, icc)
        time.sleep(0.05)
        raw2 = k.lpt.intgi(k._instr_id)
        print("Raw intgi result (0.5V):", raw2)
        print("measure_current() (0.5V):", k.measure_current())

    finally:
        try: k.set_voltage(0, icc); k.enable_output(False)
        except Exception: pass
        try: k.close()
        except Exception: pass


def diagnose_pmu(address: str):
    print(f"Connecting to PMU at {address}")
    pmu = Keithley4200A_PMUController(address)
    try:
        # Basic config: conservative defaults
        pmu._ensure_configured_with_defaults()
        # small pulse to fill buffer
        pmu.arm_single_pulse(0.5, 0.0)
        pmu.lpt.pulse_exec(pmu.param.PULSE_MODE_SIMPLE)
        t0 = time.time()
        timeout = 2.0
        while True:
            status, _ = pmu.lpt.pulse_exec_status()
            print("pulse_exec_status:", status)
            if status != pmu.param.PMU_TEST_STATUS_RUNNING:
                break
            if time.time() - t0 > timeout:
                print("Timeout waiting for pulse_exec_status")
                pmu.lpt.dev_abort()
                break
            time.sleep(0.05)

        buf_size = pmu.lpt.pulse_chan_status(pmu.card_id, pmu.channel)
        print("pulse_chan_status buffer size:", buf_size)
        if buf_size <= 0:
            print("No data in PMU buffer")
            return

        v, i, ts, statuses = pmu.lpt.pulse_fetch(pmu.card_id, pmu.channel, 0, buf_size-1)
        print("First 10 I samples:", i[:10])
        print("First 10 statuses:", statuses[:10])
        try:
            decoded = pmu.lpt.decode_pulse_status(statuses[0])
            print("Decoded status[0]:", decoded)
        except Exception as exc:
            print("Failed to decode status[0]:", exc)

    finally:
        try: pmu.close()
        except Exception: pass


def main():
    parser = argparse.ArgumentParser(description="Diagnose Keithley 4200A measurement returns")
    parser.add_argument("--smu", help="SMU address, e.g. 192.168.0.10:8888|SMU1")
    parser.add_argument("--pmu", help="PMU address, e.g. 192.168.0.10:8888|PMU1-CH1")
    parser.add_argument("--icc", type=float, default=1e-3, help="compliance current for SMU (A)")
    args = parser.parse_args()

    if not args.smu and not args.pmu:
        print("Specify --smu or --pmu")
        return

    if args.smu:
        diagnose_smu(args.smu, args.icc)
    if args.pmu:
        diagnose_pmu(args.pmu)


if __name__ == "__main__":
    main()


