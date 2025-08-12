from __future__ import annotations

import json
from pathlib import Path

from tests.config import Thresholds
from tests.driver import MeasurementDriver
from tests.runner import TestRunner

# Example: wire to Keithley2400 if available
try:
    from Equipment_Classes.SMU.Keithley2400 import Keithley2400Controller
except Exception:
    Keithley2400Controller = None
from Other.testing import FakeMemristorInstrument


def main():
    # If real instrument not available, use simulator
    if Keithley2400Controller is None:
        print("Using simulated instrument (FakeMemristorInstrument, memristive mode)")
        inst = FakeMemristorInstrument(mode='memristive')
    else:
        inst = Keithley2400Controller()
    driver = MeasurementDriver(inst)
    runner = TestRunner(driver, Thresholds())

    # Example single-device run; integrate with GUI to iterate selected devices
    outcome = runner.run_device("A1")
    print(outcome)

    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    with (out_dir / f"{outcome.device_id}_summary.json").open("w", encoding="utf-8") as f:
        json.dump(outcome.__dict__, f, indent=2)


if __name__ == "__main__":
    main()


