"""
Simple runner for SMU single-pulse modules with pre/post bias, sent over GPIB (e.g., GPIB0::17::INSTR).

Calls:
  - SMU_pulse_measure_craig (measured pulse)
  - SMU_pulse_only_craig    (pulse only)

Defaults:
  biasV = 0.2 V, biasHold = 1.0 s (each side), pulse = 2.0 V for 2.0 s.
  i_range = 1e-2, i_comp = 0.0, logMessages = 1, initialize = 1.
"""

import argparse
import time
import pyvisa


def run_ul_over_gpib(resource: str, module_name: str, args: list[str]) -> str:
    """
    Send UL command over GPIB to the 4200A.
    Sequence: UL -> EX ... -> DE
    """
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(resource)
    inst.timeout = 30000  # ms
    # Enter UL mode
    inst.write("UL")
    time.sleep(0.05)
    cmd = f"EX {module_name}({','.join(args)})"
    inst.write(cmd)
    time.sleep(0.05)
    resp = inst.read().strip()
    # Exit UL
    inst.write("DE")
    time.sleep(0.05)
    return resp


def main():
    parser = argparse.ArgumentParser(description="Run SMU pulse modules with pre/post bias over GPIB")
    parser.add_argument("--biasV", type=float, default=0.2, help="Bias voltage (V) pre/post")
    parser.add_argument("--biasHold", type=float, default=1.0, help="Bias hold time (s) pre/post")
    parser.add_argument("--pulseV", type=float, default=2.0, help="Pulse amplitude (V)")
    parser.add_argument("--pulseWidth", type=float, default=2.0, help="Pulse width (s)")
    parser.add_argument("--iRange", type=float, default=1e-2, help="Current range (A)")
    parser.add_argument("--iComp", type=float, default=0.0, help="Compliance current (A)")
    parser.add_argument("--log", type=int, default=1, help="logMessages (0/1)")
    parser.add_argument("--init", type=int, default=1, help="initialize (0/1)")
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR", help="VISA resource string (e.g., GPIB0::17::INSTR)")
    parser.add_argument("--mode", choices=["measure", "pulse"], default="measure",
                        help="measure: SMU_pulse_measure_craig; pulse: SMU_pulse_only_craig")
    args = parser.parse_args()

    if args.mode == "measure":
        module = "SMU_pulse_measure_craig"
        # initialize, logMessages, widthTime, Amplitude, Irange, Icomp, biasV, biasHold, measResistance(out)
        ul_args = [
            str(args.init),
            str(args.log),
            f"{args.pulseWidth:.6e}",
            f"{args.pulseV:.6e}",
            f"{args.iRange:.6e}",
            f"{args.iComp:.6e}",
            f"{args.biasV:.6e}",
            f"{args.biasHold:.6e}",
            "0"  # dummy for measResistance output
        ]
    else:
        module = "SMU_pulse_only_craig"
        # initialize, logMessages, widthTime, Amplitude, Irange, Icomp, biasV, biasHold, pulse_success(out)
        ul_args = [
            str(args.init),
            str(args.log),
            f"{args.pulseWidth:.6e}",
            f"{args.pulseV:.6e}",
            f"{args.iRange:.6e}",
            f"{args.iComp:.6e}",
            f"{args.biasV:.6e}",
            f"{args.biasHold:.6e}",
            "0"  # dummy for pulse_success output
        ]

    resp = run_ul_over_gpib(args.gpib_address, module, ul_args)
    print(f"{module} response: {resp}")


if __name__ == "__main__":
    main()



