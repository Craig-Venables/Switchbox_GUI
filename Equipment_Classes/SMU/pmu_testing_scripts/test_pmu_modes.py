import json
import argparse
from pathlib import Path

from Equipment_Classes.SMU.Keithley4200A import Keithley4200A_PMUController
from measurement_service import MeasurementService


def load_modes(path: Path):
    with open(path, "r") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Run PMU modes from PMU_modes.json")
    parser.add_argument("address", nargs="?", default="192.168.0.10:8888|PMU1-CH1",
                        help="LPT address for the 4200A PMU (e.g. 192.168.0.10:8888|PMU1-CH1)")
    parser.add_argument("--modes", default="PMU_modes.json", help="path to PMU_modes.json")
    args = parser.parse_args()

    modes_path = Path(args.modes)
    if not modes_path.exists():
        print(f"Modes file {modes_path} not found")
        return

    modes = load_modes(modes_path)
    pmu = Keithley4200A_PMUController(args.address)
    service = MeasurementService()

    try:
        for name, cfg in modes.items():
            print(f"Running mode: {name}")
            if name == "Pulse Train":
                v, i, t = service.run_pmu_pulse_train(
                    pmu=pmu,
                    amplitude_v=cfg.get("amplitude_v", 0.5),
                    base_v=cfg.get("base_v", 0.0),
                    width_s=cfg.get("width_s", 1e-5),
                    period_s=cfg.get("period_s", 2e-5),
                    num_pulses=cfg.get("num_pulses", 10),
                )
                print(f"Pulse Train got {len(v)} samples")
            elif name == "Pulse Pattern":
                v, i, t = service.run_pmu_pulse_pattern(
                    pmu=pmu,
                    pattern=cfg.get("pattern", "1011"),
                    amplitude_v=cfg.get("amplitude_v", 0.5),
                    base_v=cfg.get("base_v", 0.0),
                    width_s=cfg.get("width_s", 1e-5),
                    period_s=cfg.get("period_s", 2e-5),
                )
                print(f"Pulse Pattern got {len(v)} samples")
            elif name == "Amplitude Sweep":
                v, i, t = service.run_pmu_amplitude_sweep(
                    pmu=pmu,
                    start_v=cfg.get("base_v", 0.0),
                    stop_v=cfg.get("stop_v", 1.0),
                    step_v=cfg.get("step_v", 0.1),
                    base_v=cfg.get("base_v", 0.0),
                    width_s=cfg.get("width_s", 1e-5),
                    period_s=cfg.get("period_s", 2e-5),
                )
                print(f"Amplitude Sweep got {len(v)} samples")
            elif name == "Width Sweep":
                widths = [cfg.get("width_s", 1e-5) * (n+1) for n in range(cfg.get("num_pulses", 5))]
                v, i, t = service.run_pmu_width_sweep(
                    pmu=pmu,
                    amplitude_v=cfg.get("amplitude_v", 0.5),
                    base_v=cfg.get("base_v", 0.0),
                    widths_s=widths,
                    period_s=cfg.get("period_s", 2e-5),
                )
                print(f"Width Sweep got {len(v)} samples")
            elif name == "Transient":
                v, i, t = service.run_pmu_transient_switching(
                    pmu=pmu,
                    amplitude_v=cfg.get("amplitude_v", 0.5),
                    base_v=cfg.get("base_v", 0.0),
                    width_s=cfg.get("width_s", 1e-5),
                    period_s=cfg.get("period_s", 2e-5),
                )
                print(f"Transient got {len(v)} samples")
            elif name == "Endurance":
                v, i, t = service.run_pmu_endurance(
                    pmu=pmu,
                    set_voltage=cfg.get("amplitude_v", 0.5),
                    reset_voltage=0.0,
                    pulse_width_s=cfg.get("width_s", 1e-5),
                    num_cycles=cfg.get("num_pulses", 100),
                    period_s=cfg.get("period_s", 2e-5),
                )
                print(f"Endurance got {len(v)} samples")
            else:
                print(f"Unknown mode {name}, skipping")

    finally:
        try:
            pmu.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()


