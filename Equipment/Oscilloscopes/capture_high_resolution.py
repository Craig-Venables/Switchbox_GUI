"""
High-Resolution Oscilloscope Capture Script

This script discovers a connected oscilloscope (via `OscilloscopeManager`),
captures full-record waveform data at the highest resolution supported by the
driver, and stores the results as CSV files alongside a JSON metadata summary.

Usage:
    python -m Equipment.Oscilloscopes.capture_high_resolution --output-dir ./captures

Author: Generated for Switchbox_GUI project
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from Equipment.managers.oscilloscope import OscilloscopeManager


def _default_data_format(scope) -> str:
    """
    Choose a sensible binary data format for the connected oscilloscope.

    Tektronix scopes expect 'RIBINARY', whereas the GW Instek driver uses 'BINARY'.
    """
    if scope is None:
        return "ASCII"

    scope_name = scope.__class__.__name__.lower()
    if "gwinstek" in scope_name:
        return "BINARY"
    if "tektronix" in scope_name:
        return "RIBINARY"
    return "ASCII"


def _write_csv(path: Path, time_array: np.ndarray, voltage_array: np.ndarray) -> None:
    """Persist waveform data as a two-column CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if time_array.size == 0 or voltage_array.size == 0:
        # Still emit a header so downstream tooling can detect empty captures.
        path.write_text("time_s,voltage_v\n")
        return

    stacked = np.column_stack((time_array, voltage_array))
    np.savetxt(path, stacked, delimiter=",", header="time_s,voltage_v", comments="")


def capture_waveforms(manager: OscilloscopeManager,
                      channels: Sequence[int],
                      output_dir: Path,
                      data_format: Optional[str] = None,
                      num_points: Optional[int] = None,
                      autoscale: bool = False) -> Dict[str, object]:
    """
    Capture high-resolution waveform data for the requested channels.

    Args:
        manager: An initialised `OscilloscopeManager`.
        channels: Iterable of channel numbers to capture.
        output_dir: Directory where artefacts will be written.
        data_format: Optional override for the data format (driver-specific).
        num_points: Optional cap on number of points. Defaults to full record.
        autoscale: If True, run oscilloscope autoscale before captures.

    Returns:
        dict containing capture metadata for downstream use.
    """
    if not manager.is_connected():
        raise RuntimeError("OscilloscopeManager is not connected to any device.")

    scope = manager.scope
    if scope is None:
        raise RuntimeError("OscilloscopeManager has no active scope instance.")

    scope_format = data_format or _default_data_format(scope)

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    timestamp_label = timestamp.strftime("%Y%m%d_%H%M%S")

    if autoscale:
        manager.autoscale()

    captures: List[Dict[str, object]] = []

    for channel in channels:
        time_array, voltage_array = scope.acquire_waveform(
            channel=channel,
            format=scope_format,
            num_points=num_points,
        )

        csv_path = output_dir / f"osc_capture_ch{channel}_{timestamp_label}.csv"
        _write_csv(csv_path, time_array, voltage_array)

        stats = manager.compute_waveform_statistics(voltage_array)
        frequency = manager.compute_frequency(time_array, voltage_array)
        stats["frequency_hz"] = frequency

        captures.append(
            {
                "channel": channel,
                "points": int(voltage_array.size),
                "csv_path": str(csv_path),
                "stats": stats,
            }
        )

    metadata = {
        "generated_at_utc": timestamp.isoformat(),
        "channels": list(channels),
        "data_format": scope_format,
        "num_points_request": num_points,
        "captures": captures,
        "scope_info": manager.get_scope_info(),
    }

    metadata_path = output_dir / f"osc_capture_metadata_{timestamp_label}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True))

    return {
        "metadata_path": str(metadata_path),
        "captures": captures,
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture high-resolution oscilloscope waveform data."
    )
    parser.add_argument(
        "--channels",
        type=int,
        nargs="+",
        default=[1],
        help="Channel numbers to capture (default: 1).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd() / "oscilloscope_captures",
        help="Directory to save CSV and metadata files (default: ./oscilloscope_captures).",
    )
    parser.add_argument(
        "--format",
        dest="data_format",
        help="Optional data format override (e.g., RIBINARY, BINARY, ASCII).",
    )
    parser.add_argument(
        "--num-points",
        type=int,
        help="Optional limit on the number of points per capture. "
             "Defaults to the full record length reported by the oscilloscope.",
    )
    parser.add_argument(
        "--no-autoscale",
        action="store_true",
        help="Skip automatic scaling before captures.",
    )
    parser.add_argument(
        "--scope-type",
        help="Manual scope type (matches oscilloscope_manager configuration).",
    )
    parser.add_argument(
        "--address",
        help="Manual VISA resource address for the oscilloscope.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    auto_detect = not args.scope_type and not args.address
    manager = OscilloscopeManager(
        auto_detect=auto_detect,
        scope_type=args.scope_type,
        address=args.address,
    )

    if not manager.is_connected():
        print("No oscilloscope detected. Please check connections and try again.", file=sys.stderr)
        return 1

    try:
        capture_waveforms(
            manager=manager,
            channels=args.channels,
            output_dir=args.output_dir,
            data_format=args.data_format,
            num_points=args.num_points,
            autoscale=not args.no_autoscale,
        )
    finally:
        manager.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())









