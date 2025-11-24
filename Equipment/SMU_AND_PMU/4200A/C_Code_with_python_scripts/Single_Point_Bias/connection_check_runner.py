"""
Shared helpers for the smu_check_connection UL module.

This module exposes utility functions so both the CLI streamer and the GUI/IV
controller can execute the same EX → GP workflow without duplicating code.
"""

from __future__ import annotations

from typing import Dict, Optional
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
A_IV_SWEEP_DIR = SCRIPT_DIR.parent / "A_Iv_Sweep"
if str(A_IV_SWEEP_DIR) not in sys.path:
    sys.path.insert(0, str(A_IV_SWEEP_DIR))

try:
    from run_smu_vi_sweep import format_param  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "Unable to import run_smu_vi_sweep helpers for connection_check_runner. "
        "Ensure Equipment/SMU_AND_PMU/4200A/C_Code_with_python_scripts/A_Iv_Sweep is present."
    ) from exc


def build_check_connection_command(
    bias_voltage: float,
    sample_interval: float,
    settle_time: float,
    ilimit: float,
    integration_time: float,
    buffer_size: int,
    max_samples: int,
    clarius_debug: int,
) -> str:
    """Return the EX command string for smu_check_connection."""

    params = [
        format_param(bias_voltage),  # 1 BiasVoltage
        format_param(sample_interval),  # 2 SampleInterval
        format_param(settle_time),  # 3 SettleTime
        format_param(ilimit),  # 4 Ilimit
        format_param(integration_time),  # 5 IntegrationTime
        "",  # 6 Ibuffer (D_ARRAY_T)
        format_param(buffer_size),  # 7 NumISamples
        "",  # 8 Vbuffer (D_ARRAY_T)
        format_param(buffer_size),  # 9 NumVSamples
        format_param(max_samples),  # 10 MaxSamples
        format_param(clarius_debug),  # 11 ClariusDebug
    ]
    return f"EX A_Check_Connection smu_check_connection({','.join(params)})"


def _latest_non_zero(voltage, current) -> Optional[int]:
    """Return the newest index that contains a non-zero sample."""

    limit = min(len(voltage), len(current))
    for idx in range(limit - 1, -1, -1):
        if voltage[idx] != 0.0 or current[idx] != 0.0:
            return idx
    return None


def execute_single_sample(
    kxci_controller,
    bias_voltage: float = 0.2,
    sample_interval: float = 0.1,
    settle_time: float = 0.01,
    ilimit: float = 0.01,
    integration_time: float = 0.01,
    buffer_size: int = 8,
    clarius_debug: int = 0,
) -> Dict[str, float]:
    """
    Execute the smu_check_connection UL module and return the latest sample.

    Args:
        kxci_controller: Connected `KXCIClient` instance (Keithley4200A_KXCI).

    Returns:
        {"voltage": <float>, "current": <float>}

    Raises:
        RuntimeError if the command fails or no sample is returned.
    """

    command = build_check_connection_command(
        bias_voltage=bias_voltage,
        sample_interval=sample_interval,
        settle_time=settle_time,
        ilimit=ilimit,
        integration_time=integration_time,
        buffer_size=buffer_size,
        max_samples=1,
        clarius_debug=clarius_debug,
    )

    wait_seconds = max(0.05, sample_interval + settle_time + integration_time)
    return_value, error = kxci_controller._execute_ex_command(  # pylint: disable=protected-access
        command,
        wait_seconds=wait_seconds,
    )
    if error:
        raise RuntimeError(f"EX command failed: {error}")
    if return_value not in (0, None):
        raise RuntimeError(f"EX command returned error code {return_value}")

    voltage = kxci_controller._query_gp(8, buffer_size)  # pylint: disable=protected-access
    current = kxci_controller._query_gp(6, buffer_size)  # pylint: disable=protected-access

    if not voltage or not current:
        raise RuntimeError("No data returned from smu_check_connection buffers")

    latest_index = _latest_non_zero(voltage, current)
    if latest_index is None:
        raise RuntimeError("Buffers contained only zeros; no valid sample found")

    return {
        "voltage": float(voltage[latest_index]),
        "current": float(current[latest_index]),
    }


