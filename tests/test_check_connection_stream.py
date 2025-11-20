"""Unit tests for run_check_connection_stream helpers."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = PROJECT_ROOT / "Equipment" / "SMU_AND_PMU" / "4200A" / "C_Code_with_python_scripts" / "Single_Point_Bias"

if str(MODULE_DIR) not in sys.path:
    sys.path.append(str(MODULE_DIR))

from run_check_connection_stream import (  # type: ignore  # pylint: disable=import-error
    build_check_connection_command,
    latest_sample_from_buffers,
)


def test_build_check_connection_command_contains_module_name() -> None:
    command = build_check_connection_command(
        bias_voltage=0.2,
        sample_interval=0.1,
        settle_time=0.01,
        ilimit=0.01,
        integration_time=0.01,
        buffer_size=64,
        control_size=4,
        clarius_debug=0,
    )
    assert "smu_check_connection" in command
    assert "Single_Point_Bias" in command


def test_latest_sample_from_buffers_calculates_last_index() -> None:
    voltage = [0.2, 0.2, 0.2, 0.2]
    current = [0.0, 1e-9, 2e-9, 3e-9]
    snapshot = latest_sample_from_buffers(voltage, current, write_index=2, total_samples=6)

    assert snapshot.voltage == 0.2
    assert snapshot.current == 1e-9
    assert snapshot.total_samples == 6
    assert snapshot.write_index == 2


