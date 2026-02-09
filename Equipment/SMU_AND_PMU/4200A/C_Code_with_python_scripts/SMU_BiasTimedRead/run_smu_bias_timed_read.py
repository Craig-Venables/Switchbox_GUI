"""SMU Bias Timed Read runner (KXCI compatible).

Calls the SMU_BiasTimedRead C module: applies a constant voltage for a set
duration, samples current at a fixed interval, returns data via GP.

Synced mode (for laser/optical): use run_bias_timed_read_synced() with a
threading.Event. The 4200 runs Start (bias on) and returns; that return
signals "ready". The host waits for the event, sets t0, starts the laser,
while the instrument runs Collect (sample loop). Clocks are aligned to
"ready".

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
import threading
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
    return f"EX A_SMU_BiasTimedRead SMU_BiasTimedRead({','.join(params)})"


def build_ex_command_start(vforce: float, ilimit: float) -> str:
    """Build EX command for SMU_BiasTimedRead_Start (Phase 1: apply bias, return for sync)."""
    return f"EX A_SMU_BiasTimedRead_Start SMU_BiasTimedRead_Start({format_param(vforce)},{format_param(ilimit)})"


def build_ex_command_collect(
    duration_s: float,
    sample_interval_s: float,
    num_points: int,
) -> str:
    """Build EX command for SMU_BiasTimedRead_Collect (Phase 2: sample loop, then ramp down).
    Imeas is output param 3 (empty string in EX).
    """
    params = [
        format_param(duration_s),
        format_param(sample_interval_s),
        "",  # 3: Imeas output
        format_param(num_points),
    ]
    return f"EX A_SMU_BiasTimedRead_Start SMU_BiasTimedRead_Collect({','.join(params)})"


# Imeas in Collect: 3rd param of Collect. If Start+Collect share one module, 4200 may use
# combined numbering (Start 1,2 + Collect 3,4,5,6) so Imeas is param 5.
GP_PARAM_IMEAS_COLLECT = 3
GP_PARAM_IMEAS_COLLECT_ALT = 5  # fallback when both functions in same module


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


# Imeas is the 5th parameter (1-based) in SMU_BiasTimedRead(...)
GP_PARAM_IMEAS = 5


def run_bias_timed_read_synced(
    gpib_address: str,
    timeout: float,
    vforce: float,
    duration_s: float,
    sample_interval_s: float,
    ilimit: float,
    sync_ready_event: threading.Event,
    num_points: Optional[int] = None,
) -> Tuple[threading.Thread, List[Optional[Dict[str, Any]]], List[Optional[Exception]]]:
    """Run two-phase SMU bias timed read so the host can sync to "4200 ready".

    Starts a background thread that:
      1. Connects, enters UL, runs SMU_BiasTimedRead_Start (bias on).
      2. Sets sync_ready_event so the host knows "4200 is ready and starting".
      3. Runs SMU_BiasTimedRead_Collect (sample loop, then ramp down).
      4. Retrieves data via GP and stores in result_holder.

    Caller should: wait for sync_ready_event (with timeout), set t0 = time.perf_counter(),
    run the laser (or other sync'd equipment), then thread.join() and read result_holder[0].

    Returns:
        (thread, result_holder, exc_holder). result_holder[0] is set when thread finishes
        (dict with timestamps, voltages, currents, resistances); exc_holder[0] on error.
    """
    if num_points is None:
        num_points = max(1, int(duration_s / sample_interval_s))
    result_holder: List[Optional[Dict[str, Any]]] = [None]
    exc_holder: List[Optional[Exception]] = [None]

    def _measurement_thread() -> None:
        currents: List[float] = []
        client = KXCIClient(gpib_address=gpib_address, timeout=timeout)
        try:
            if not client.connect():
                exc_holder[0] = RuntimeError("Failed to connect to instrument")
                return
            if not client._enter_ul_mode():
                exc_holder[0] = RuntimeError("Failed to enter UL mode")
                return
            # Phase 1: apply bias; when this returns, 4200 is "ready"
            cmd_start = build_ex_command_start(vforce, ilimit)
            rv, err = client._execute_ex_command(cmd_start, wait_seconds=0.5)
            if err:
                exc_holder[0] = RuntimeError(f"SMU_BiasTimedRead_Start failed: {err}")
                return
            if rv is not None and rv < 0:
                exc_holder[0] = RuntimeError(
                    f"SMU_BiasTimedRead_Start returned {rv} (forcev/limiti failed)"
                )
                return
            # Signal host: 4200 ready, host can start laser and we start sampling
            sync_ready_event.set()
            # Phase 2: sample loop
            cmd_collect = build_ex_command_collect(duration_s, sample_interval_s, num_points)
            wait_collect = duration_s + 2.0
            rv, err = client._execute_ex_command(cmd_collect, wait_seconds=wait_collect)
            if err:
                exc_holder[0] = RuntimeError(f"SMU_BiasTimedRead_Collect failed: {err}")
                return
            if rv is not None and rv < 0:
                err_meaning = {-1: "invalid params", -5: "forcev failed", -6: "measi failed"}
                meaning = err_meaning.get(rv, f"code {rv}")
                exc_holder[0] = RuntimeError(
                    f"SMU_BiasTimedRead_Collect returned {rv} ({meaning})"
                )
                return
            time.sleep(0.05)
            currents = client._query_gp(GP_PARAM_IMEAS_COLLECT, num_points)
            if (not currents or len(currents) != num_points) and num_points > 0:
                try:
                    alt = client._query_gp(GP_PARAM_IMEAS_COLLECT_ALT, num_points)
                    if alt and len(alt) == num_points:
                        currents = alt
                except Exception:
                    pass
        except Exception as e:
            exc_holder[0] = e
        finally:
            try:
                client._exit_ul_mode()
            except Exception:
                pass
            client.disconnect()

        if exc_holder[0] is None and currents:
            n_actual = len(currents)
            timestamps = [i * sample_interval_s for i in range(n_actual)]
            voltages = [vforce] * n_actual
            resistances = [
                (vforce / i if i and abs(i) > 1e-18 else float("nan"))
                for i in currents
            ]
            result_holder[0] = {
                "timestamps": timestamps,
                "voltages": voltages,
                "currents": currents,
                "resistances": resistances,
            }

    thread = threading.Thread(target=_measurement_thread, daemon=False)
    thread.start()
    return (thread, result_holder, exc_holder)


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
    parser.add_argument("--sample-interval", type=float, default=0.01, help="Sample interval (s)")
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

    print(result)
if __name__ == "__main__":
    main()
