"""Single-sample bias monitor for the Keithley 4200A.

This Python utility repeatedly launches the `smu_check_connection` UL module,
waits for a single measurement to be collected, grabs that sample from the
instrument via `GP 8` (voltage) and `GP 6` (current), and prints the result.

Implementation overview
=======================
1. The command is generated with ``build_check_connection_command`` and looks
   like ``EX A_Check_Connection smu_check_connection(...)``.
2. ``CheckConnectionStreamer.run_batch`` sends the EX command using
   ``KXCIClient._execute_ex_command``. When the UL module finishes, we query
   the output buffers (parameters 8 and 6) to retrieve the latest measurement.
3. By default the script loops forever, issuing EX → GP → print as quickly as
   allowed. This gives a near real-time feed while you probe or adjust a DUT.
   Press Ctrl+C to stop the stream. Use ``--once`` to capture a single sample.
4. The script depends on the shared ``KXCIClient`` from ``run_smu_vi_sweep``,
   so it inherits the same visa connection handling, UL entry/exit, etc.

Command-line usage
==================
``python run_check_connection_stream.py [options]``

Key options:
* ``--bias-voltage``: DC bias applied by the UL module (default 0.2V)
* ``--sample-interval``: Delay between successive samples inside the UL module
* ``--settle-time``: Initial settle delay after first forcing the bias
* ``--ilimit`` / ``--integration-time``: Compliance and measurement settings
* ``--once``: Take a single sample and exit (instead of continuous streaming)
* ``--pause``: Delay between repeated EX commands when streaming (default 50ms)
* ``--json``: Emit samples as JSON objects instead of human-readable text

Example
=======
```
python run_check_connection_stream.py --bias-voltage 0.2 --sample-interval 0.2
```
prints lines like ``[01] V= 0.200012 V | I= 1.99e-06 A`` until you press Ctrl+C.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List


SCRIPT_DIR = Path(__file__).resolve().parent
A_IV_SWEEP_DIR = SCRIPT_DIR.parent / "A_Iv_Sweep"
if str(A_IV_SWEEP_DIR) not in sys.path:
    sys.path.insert(0, str(A_IV_SWEEP_DIR))

try:
    from run_smu_vi_sweep import KXCIClient  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Unable to import run_smu_vi_sweep helpers. "
        "Ensure Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/A_Iv_Sweep "
        "is present."
    ) from exc

from connection_check_runner import build_check_connection_command, execute_single_sample


class CheckConnectionStreamer:
    def __init__(self, controller: KXCIClient, buffer_size: int) -> None:
        self.controller = controller
        self.buffer_size = buffer_size

    def run_batch(self, config: dict, emit_json: bool) -> bool:
        """Execute UL program once, then fetch/print the single latest sample.

        Returns True if a sample was printed, False if the EX/GP requests failed.
        """

        try:
            sample = execute_single_sample(
                self.controller,
                bias_voltage=config["bias"],
                sample_interval=config["sample_interval"],
                settle_time=config["settle_time"],
                ilimit=config["ilimit"],
                integration_time=config["integration_time"],
                buffer_size=config["buffer_size"],
                clarius_debug=config["debug"],
            )
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] Failed to retrieve sample: {exc}")
            return False

        if emit_json:
            print(json.dumps(sample))
        else:
            print(f"[01] V={sample['voltage']: .6f} V | I={sample['current']: .6e} A")

        return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Looped EX/GP helper for smu_check_connection",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--gpib-address", default="GPIB0::17::INSTR")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--bias-voltage", type=float, default=0.2)
    parser.add_argument("--sample-interval", type=float, default=0.1)
    parser.add_argument("--settle-time", type=float, default=0.01)
    parser.add_argument("--ilimit", type=float, default=0.01)
    parser.add_argument("--integration-time", type=float, default=0.01)
    parser.add_argument("--buffer-size", type=int, default=8, help="Circular buffer size in the UL module")
    parser.add_argument("--pause", type=float, default=0.05, help="Pause between batches when looping")
    parser.add_argument("--once", action="store_true", help="Take a single sample then exit")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON lines")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.buffer_size < 1:
        parser.error("buffer-size must be >= 1")
    if args.pause < 0:
        parser.error("pause must be >= 0")

    sample_config = {
        "bias": args.bias_voltage,
        "sample_interval": args.sample_interval,
        "settle_time": args.settle_time,
        "ilimit": args.ilimit,
        "integration_time": args.integration_time,
        "debug": 1 if args.debug else 0,
        "buffer_size": args.buffer_size,
    }
    preview = build_check_connection_command(
        bias_voltage=args.bias_voltage,
        sample_interval=args.sample_interval,
        settle_time=args.settle_time,
        ilimit=args.ilimit,
        integration_time=args.integration_time,
        buffer_size=args.buffer_size,
        max_samples=1,
        clarius_debug=sample_config["debug"],
    )

    if args.dry_run:
        print(preview)
        return

    controller = KXCIClient(gpib_address=args.gpib_address, timeout=args.timeout)
    if not controller.connect():
        raise SystemExit("[ERROR] Failed to connect to instrument")

    try:
        if not controller._enter_ul_mode():  # pylint: disable=protected-access
            raise RuntimeError("Failed to enter UL mode")

        streamer = CheckConnectionStreamer(controller=controller, buffer_size=args.buffer_size)

        try:
            if args.once:
                streamer.run_batch(sample_config, emit_json=args.json)
            else:
                print("[INFO] Streaming measurements (Ctrl+C to stop)")
                while True:
                    success = streamer.run_batch(sample_config, emit_json=args.json)
                    if args.pause > 0:
                        time.sleep(args.pause)
                    if not success:
                        # Small pause before retry to avoid hammering the bus on error
                        time.sleep(max(args.pause, 0.1))
        except KeyboardInterrupt:
            print("\n[INFO] Stopped by user")
    finally:
        try:
            controller._exit_ul_mode()  # pylint: disable=protected-access
        finally:
            controller.disconnect()


if __name__ == "__main__":
    main()


