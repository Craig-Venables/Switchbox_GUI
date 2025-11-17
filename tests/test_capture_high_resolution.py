"""
Tests for the high-resolution oscilloscope capture script.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

from Equipment.Oscilloscopes.capture_high_resolution import capture_waveforms


class DummyScope:
    def __init__(self):
        self.calls: List[Dict[str, object]] = []

    def acquire_waveform(self, channel: int, format: str = "ASCII", num_points=None):
        self.calls.append(
            {"channel": channel, "format": format, "num_points": num_points}
        )
        # Provide deterministic data for assertions.
        time_array = np.linspace(0, 1, 5)
        voltage_array = np.linspace(0, 1, 5) + channel
        return time_array, voltage_array


class DummyManager:
    def __init__(self, connected: bool = True):
        self._connected = connected
        self.scope = DummyScope() if connected else None
        self.autoscale_called = False

    def is_connected(self) -> bool:
        return self._connected

    def autoscale(self) -> None:
        self.autoscale_called = True

    def compute_waveform_statistics(self, voltage_array):
        if voltage_array.size == 0:
            return {'vpp': 0.0, 'mean': 0.0, 'std': 0.0, 'vmax': 0.0, 'vmin': 0.0}
        return {
            'vpp': float(np.max(voltage_array) - np.min(voltage_array)),
            'mean': float(np.mean(voltage_array)),
            'std': float(np.std(voltage_array)),
            'vmax': float(np.max(voltage_array)),
            'vmin': float(np.min(voltage_array)),
        }

    def compute_frequency(self, time_array, voltage_array):
        return 123.45 if voltage_array.size > 0 else 0.0

    def get_scope_info(self):
        return {'connected': self._connected, 'idn': 'DUMMY,SCOPE,1234,1.0'}


def test_capture_waveforms_writes_csv_and_metadata(tmp_path: Path):
    manager = DummyManager(connected=True)
    result = capture_waveforms(
        manager=manager,
        channels=[1, 2],
        output_dir=tmp_path,
        data_format="ASCII",
        num_points=8,
        autoscale=True,
    )

    # Autoscale should run once when requested.
    assert manager.autoscale_called

    # Two CSV files (one per channel) plus metadata JSON should exist.
    csv_files = sorted(tmp_path.glob("osc_capture_ch*.csv"))
    assert len(csv_files) == 2

    metadata_path = Path(result["metadata_path"])
    assert metadata_path.exists()

    metadata = json.loads(metadata_path.read_text())
    assert metadata["channels"] == [1, 2]
    assert metadata["data_format"] == "ASCII"
    assert metadata["num_points_request"] == 8
    assert len(metadata["captures"]) == 2
    for entry in metadata["captures"]:
        assert Path(entry["csv_path"]).exists()
        assert entry["points"] == 5  # From DummyScope data
        assert "frequency_hz" in entry["stats"]

    # Ensure waveform acquisition honoured the num_points argument.
    assert all(call["num_points"] == 8 for call in manager.scope.calls)


def test_capture_waveforms_requires_connection(tmp_path: Path):
    manager = DummyManager(connected=False)
    with pytest.raises(RuntimeError):
        capture_waveforms(manager, channels=[1], output_dir=tmp_path)









