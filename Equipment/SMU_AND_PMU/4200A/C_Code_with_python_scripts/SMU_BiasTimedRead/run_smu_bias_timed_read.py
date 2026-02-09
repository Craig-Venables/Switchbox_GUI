"""SMU Bias Timed Read runner (KXCI compatible).

Calls the SMU_BiasTimedRead C module: applies a constant voltage for a set
duration, samples current at a fixed interval, returns data via GP.

Used by the Pulse Testing GUI optical+read tests (4200A). Run standalone for
testing:

  # Just run (short test: 2 s, 20 points, ~4 s total)
  python run_smu_bias_timed_read.py

  # Dry run (no instrument): print EX command only
  python run_smu_bias_timed_read.py --dry-run

  # Longer run: e.g. 10 s, 0.02 s interval
  python run_smu_bias_timed_read.py --duration 10 --sample-interval 0.02
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from typing import List, Optional, Tuple, Dict, Any


def format_param(value: float | int | str) -> str:
    """Format parameter for EX command."""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        if value >= 1.0 and value < 1e6:
            if value == int(value):
                return str(int(value))
            return f"{value:.10g}".rstrip('0').rstrip('.')
        formatted = f"{value:.2E}".upper()
        return formatted.replace("E-0", "E-").replace("E+0", "E+")
    return str(value)


def build_ex_command(
    vforce: float,
    duration_s: float,
    sample_interval_s: float,
    ilimit: float,
    num_points: int,
) -> str:
    """Build EX command for SMU_BiasTimedRead.

    Signature: int SMU_BiasTimedRead(double Vforce, double Duration_s,
        double SampleInterval_s, double Ilimit, double *Imeas, int NumPoints)
    Parameters 1-4: inputs, 5: Imeas (output, "" in EX), 6: NumPoints.
    Retrieve Imeas via GP 5 after execution.
    """
    params = [
        format_param(vforce),
        format_param(duration_s),
        format_param(sample_interval_s),
        format_param(ilimit),
        "",  # 5: Imeas output (empty string)
        format_param(num_points),
    ]
    return f"EX SMU_BiasTimedRead SMU_BiasTimedRead({','.join(params)})"


class KXCIClient:
    """Minimal KXCI helper for EX/GP commands."""

    def __init__(self, gpib_address: str, timeout: float) -> None:
        self.gpib_address = gpib_address
        self.timeout_ms = int(timeout * 1000)
        self.rm = None
        self.inst = None
        self._ul_mode_active = False

    def connect(self) -> bool:
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError("pyvisa is required") from exc
        try:
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(self.gpib_address)
            self.inst.timeout = self.timeout_ms
            self.inst.write_termination = "\n"
            self.inst.read_termination = "\n"
            idn = self.inst.query("*IDN?").strip()
            print(f"[OK] Connected: {idn}")
            return True
        except Exception as exc:
            print(f"[ERR] Connection failed: {exc}")
            return False

    def disconnect(self) -> None:
        try:
            if self._ul_mode_active:
                self._exit_ul_mode()
            if self.inst is not None:
                self.inst.close()
            if self.rm is not None:
                self.rm.close()
        finally:
            self.inst = None
            self.rm = None
            self._ul_mode_active = False

    def _enter_ul_mode(self) -> bool:
        if self.inst is None:
            return False
        self.inst.write("UL")
        time.sleep(0.03)
        self._ul_mode_active = True
        return True

    def _exit_ul_mode(self) -> bool:
        if self.inst is None or not self._ul_mode_active:
            self._ul_mode_active = False
            return True
        self.inst.write("DE")
        time.sleep(0.03)
        self._ul_mode_active = False
        return True

    def _execute_ex_command(self, command: str, wait_seconds: float = 0.1) -> Tuple[Optional[int], Optional[str]]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")
        try:
            self.inst.write(command)
            time.sleep(0.03)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            response = self._safe_read()
            if not response:
                time.sleep(0.05)
                response = self._safe_read()
            return self._parse_return_value(response), None
        except Exception as exc:
            return None, str(exc)

    def _safe_read(self) -> str:
        if self.inst is None:
            return ""
        try:
            return self.inst.read()
        except Exception:
            return ""

    @staticmethod
    def _parse_return_value(response: str) -> Optional[int]:
        if not response:
            return None
        match = re.search(r"RETURN VALUE\s*=\s*(-?\d+)", response, re.IGNORECASE)
        if match:
            return int(match.group(1))
        try:
            return int(response.strip())
        except ValueError:
            return None

    def _query_gp(self, param_position: int, num_values: int) -> List[float]:
        if self.inst is None:
            raise RuntimeError("Instrument not connected")
        command = f"GP {param_position} {num_values}"
        for attempt in range(3):
            try:
                self.inst.write(command)
                time.sleep(0.02 if attempt == 0 else 0.05)
                raw = self._safe_read()
                if raw and not raw.strip().startswith("ERROR"):
                    return self._parse_gp_response(raw)
                if attempt < 2:
                    time.sleep(0.05)
                    continue
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.05)
                    continue
                raise RuntimeError(f"GP command failed after {attempt + 1} attempts: {e}") from e
        raise RuntimeError("GP command failed: no valid response")

    @staticmethod
    def _parse_gp_response(response: str) -> List[float]:
        response = response.strip()
        if "=" in response and "PARAM VALUE" in response.upper():
            response = response.split("=", 1)[1].strip()
        separator = None
        for cand in (";", ","):
            if cand in response:
                separator = cand
                break
        values: List[float] = []
        if separator is None:
            if response:
                try:
                    values.append(float(response))
                except ValueError:
                    pass
            return values
        for part in response.split(separator):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(float(part))
            except ValueError:
                pass
        return values


# Imeas is the 5th parameter (1-based) in SMU_BiasTimedRead(Vforce, Duration_s, SampleInterval_s, Ilimit, Imeas, NumPoints)
GP_PARAM_IMEAS = 5


def run_bias_timed_read(
    gpib_address: str,
    timeout: float,
    vforce: float,
    duration_s: float,
    sample_interval_s: float,
    ilimit: float,
    num_points: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute SMU_BiasTimedRead and return timestamps, voltages, currents, resistances.

    If num_points is None, it is set to max(1, int(duration_s / sample_interval_s)).
    """
    if num_points is None:
        num_points = max(1, int(duration_s / sample_interval_s))
    command = build_ex_command(vforce, duration_s, sample_interval_s, ilimit, num_points)
    wait_seconds = duration_s + 2.0

    client = KXCIClient(gpib_address=gpib_address, timeout=timeout)
    if not client.connect():
        raise RuntimeError("Failed to connect to instrument")

    try:
        if not client._enter_ul_mode():
            raise RuntimeError("Failed to enter UL mode")
        return_value, error = client._execute_ex_command(command, wait_seconds=wait_seconds)
        if error:
            raise RuntimeError(f"EX command failed: {error}")
        if return_value is not None and return_value < 0:
            err_msgs = {
                -1: "Invalid parameters",
                -5: "forcev failed",
                -6: "measi failed",
                -7: "limiti failed",
            }
            msg = err_msgs.get(return_value, f"Error code {return_value}")
            raise RuntimeError(f"SMU_BiasTimedRead returned {return_value}: {msg}")
        time.sleep(0.05)
        currents = client._query_gp(GP_PARAM_IMEAS, num_points)
    finally:
        try:
            client._exit_ul_mode()
        except Exception:
            pass
        client.disconnect()

    # Build timestamps (relative to start of measurement); use len(currents) in case GP returned fewer points
    n_actual = len(currents)
    if n_actual < num_points and n_actual > 0:
        print(f"[WARN] GP returned {n_actual} points (requested {num_points})", file=sys.stderr)
    timestamps = [i * sample_interval_s for i in range(n_actual)]
    voltages = [vforce] * n_actual
    resistances = [
        (vforce / i if i and abs(i) > 1e-18 else float('nan'))
        for i in currents
    ]
    return {
        "timestamps": timestamps,
        "voltages": voltages,
        "currents": currents,
        "resistances": resistances,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SMU Bias Timed Read: apply voltage for duration, sample current, return data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--gpib-address", type=str, default="GPIB0::17::INSTR", help="GPIB address")
    parser.add_argument("--timeout", type=float, default=60.0, help="Timeout (s)")
    parser.add_argument("--vforce", type=float, default=0.2, help="Bias voltage (V)")
    parser.add_argument("--duration", type=float, default=2.0, help="Duration (s)")
    parser.add_argument("--sample-interval", type=float, default=0.1, help="Sample interval (s)")
    parser.add_argument("--ilimit", type=float, default=0.0001, help="Current limit (A)")
    parser.add_argument("--num-points", type=int, default=None, help="Number of samples (default: duration/sample_interval)")
    parser.add_argument("--dry-run", action="store_true", help="Print EX command only (no instrument)")
    args = parser.parse_args()

    num_points = args.num_points
    if num_points is None:
        num_points = max(1, int(args.duration / args.sample_interval))

    if args.dry_run:
        print(build_ex_command(args.vforce, args.duration, args.sample_interval, args.ilimit, num_points))
        return

    result = run_bias_timed_read(
        gpib_address=args.gpib_address,
        timeout=args.timeout,
        vforce=args.vforce,
        duration_s=args.duration,
        sample_interval_s=args.sample_interval,
        ilimit=args.ilimit,
        num_points=num_points,
    )
    n = len(result["timestamps"])
    print(f"[OK] Got {n} points")
    if n == 0:
        print("[WARN] No data returned from instrument (check GP 5 and module load).")
    else:
        print(f"  Timestamps: 0 to {result['timestamps'][-1]:.3f} s")
        print(f"  Current range: {min(result['currents']):.3e} to {max(result['currents']):.3e} A")


if __name__ == "__main__":
    main()
