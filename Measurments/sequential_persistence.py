"""Utility helpers for saving sequential measurement artifacts.

The Tk-based and Qt-based measurement GUIs both capture sequential runs (IV
passes and averaged measurements). Historically, the persistence logic lived
inside `Measurement_GUI.py`, which made the code hard to reuse as we expand the
Qt port. This module collects the shared saving behaviour behind a small helper
class so front-ends can call consistent methods without duplicating file-system
logic.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np

try:  # Optional heavy deps used for summary CSV/graphs
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pd = None

try:  # Matplotlib is optional for environments without plotting back-end
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.cm as cm  # type: ignore
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    matplotlib = None
    plt = None
    cm = None

Logger = Optional[Callable[[str], None]]


@dataclass
class SequentialDataSaver:
    """Persist sequential measurement data and graphs."""

    iv_root: Path = Path("Data_save_loc") / "Multiplexer_IV_sweep"
    avg_root: Path = Path("Data_save_loc") / "Multiplexer_Avg_Measure"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def save_iv_pass(
        self,
        *,
        sample_name: str,
        device_identifier: str,
        device_index: int,
        pass_index: int,
        target_voltage: float,
        step_voltage: float,
        step_delay: float,
        voltage_arr: Iterable[float],
        current_arr: Iterable[float],
        timestamps: Iterable[float],
        custom_base: Optional[Path] = None,
        logger: Logger = None,
    ) -> Path:
        """Persist raw IV sweep data for a sequential pass."""
        base_dir = self._resolve_iv_dir(sample_name, device_index, custom_base)
        data = np.column_stack((voltage_arr, current_arr, timestamps))
        fname = (
            f"{pass_index + 1}-FS-{target_voltage}v-"
            f"{step_voltage}sv-{step_delay}sd-Py-Sq-1"
        )
        file_path = base_dir / f"{fname}.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        np.savetxt(
            file_path,
            data,
            fmt="%0.3E\t%0.3E\t%0.3E",
            header="Voltage Current Time",
            comments="",
        )
        self._log(logger, f"[SAVE] Sequential IV saved: {file_path.resolve()}")
        return file_path

    def save_averaged_data(
        self,
        *,
        device_data: Dict[str, Dict[str, List[float]]],
        sample_name: str,
        measurement_duration: float,
        record_temperature: bool,
        status: str,
        custom_base: Optional[Path] = None,
        logger: Logger = None,
    ) -> List[Path]:
        """Persist averaged current measurements for each device."""
        base_dir = self._resolve_avg_dir(sample_name, custom_base)
        saved_paths: List[Path] = []
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")

        for device, values in device_data.items():
            currents = np.asarray(values.get("currents", []), dtype=float)
            if currents.size == 0:
                continue

            timestamps = np.asarray(values.get("timestamps", []), dtype=float)
            voltages = np.asarray(values.get("voltages", []), dtype=float)
            std_errors = np.asarray(values.get("std_errors", []), dtype=float)
            temperatures = np.asarray(
                values.get("temperatures", []), dtype=float
            )

            # Derive device index from name (fallback to enumeration order)
            device_number = _extract_device_number(device)
            device_dir = base_dir / str(device_number)
            device_dir.mkdir(parents=True, exist_ok=True)

            resistance = np.divide(
                voltages,
                currents,
                where=np.abs(currents) > 1e-12,
                out=np.full_like(voltages, np.nan, dtype=float),
            )
            conductance = np.divide(
                currents,
                voltages,
                where=np.abs(voltages) > 1e-12,
                out=np.full_like(currents, np.nan, dtype=float),
            )
            if conductance.size:
                conductance_normalized = conductance / np.nanmax(
                    np.abs(conductance)
                )
            else:
                conductance_normalized = conductance

            if record_temperature and temperatures.size == timestamps.size:
                temp_column = temperatures
            else:
                temp_column = np.full_like(timestamps, np.nan, dtype=float)

            output = np.column_stack(
                (
                    timestamps,
                    temp_column,
                    voltages,
                    currents,
                    std_errors,
                    resistance,
                    conductance,
                    conductance_normalized,
                )
            )

            voltage_setpoint = float(voltages[0]) if voltages.size else 0.0
            filename = (
                f"Device_{device_number}_{device}_{voltage_setpoint}V_"
                f"{measurement_duration}s_{currents.size}measurements_"
                f"{status}_{timestamp_str}.txt"
            )
            file_path = device_dir / filename
            header = (
                "Time(s)\tTemperature(C)\tVoltage(V)\tCurrent(A)\tStd_Error(A)\t"
                "Resistance(Ohm)\tConductance(S)\tConductance_Normalized"
            )
            np.savetxt(
                file_path,
                output,
                fmt="%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E\t%0.3E",
                header=header,
                comments="# ",
            )
            saved_paths.append(file_path)
            self._log(logger, f"[SAVE] Averaged data saved: {file_path.resolve()}")

        return saved_paths

    def save_all_measurements_file(
        self,
        *,
        device_data: Dict[str, Dict[str, List[float]]],
        sample_name: str,
        record_temperature: bool,
        custom_base: Optional[Path] = None,
        logger: Logger = None,
    ) -> Optional[Path]:
        """Create consolidated CSV/graphs for averaged sequential data."""
        if pd is None:  # pragma: no cover - optional dependency path
            self._log(
                logger,
                "[WARN] pandas not available; skipping combined sequential export.",
            )
            return None

        base_dir = self._resolve_avg_dir(sample_name, custom_base)
        base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = base_dir / f"{sample_name}_{timestamp}_all.csv"

        all_columns: Dict[str, np.ndarray] = {}
        graph_data: Dict[str, Dict[str, np.ndarray]] = {}

        for device, values in device_data.items():
            device_number = _extract_device_number(device)
            display = f"D{device_number}_{device}"

            timestamps = np.asarray(values.get("timestamps", []), dtype=float)
            voltages = np.asarray(values.get("voltages", []), dtype=float)
            currents = np.asarray(values.get("currents", []), dtype=float)
            std_errors = np.asarray(values.get("std_errors", []), dtype=float)
            temperatures = np.asarray(
                values.get("temperatures", []), dtype=float
            )

            resistance = np.divide(
                voltages,
                currents,
                where=np.abs(currents) > 1e-12,
                out=np.full_like(voltages, np.nan),
            )
            conductance = np.divide(
                currents,
                voltages,
                where=np.abs(voltages) > 1e-12,
                out=np.full_like(currents, np.nan),
            )
            if conductance.size:
                conductance_norm = conductance / np.nanmax(np.abs(conductance))
            else:
                conductance_norm = conductance

            if not record_temperature or temperatures.size != timestamps.size:
                temperatures = np.full_like(timestamps, np.nan)

            all_columns[f"Time({display})"] = timestamps
            all_columns[f"Temperature({display})"] = temperatures
            all_columns[f"Voltage({display})"] = voltages
            all_columns[f"Current({display})"] = currents
            all_columns[f"StdError({display})"] = std_errors
            all_columns[f"Resistance({display})"] = resistance
            all_columns[f"Conductance({display})"] = conductance
            all_columns[f"Conductance_Normalized({display})"] = conductance_norm

            graph_data[device] = {
                "device_number": device_number,
                "device_name": device,
                "timestamps": timestamps,
                "temperatures": temperatures,
                "currents": currents,
                "conductance": conductance,
                "conductance_normalized": conductance_norm,
            }

        df = pd.DataFrame({k: pd.Series(v) for k, v in all_columns.items()})
        df.to_csv(filename, index=False)
        self._log(logger, f"[SAVE] CSV file saved: {filename.resolve()}")

        if matplotlib and plt:
            graphs_dir = base_dir / "graphs"
            graphs_dir.mkdir(parents=True, exist_ok=True)
            self._create_individual_graphs(graph_data, graphs_dir, sample_name, timestamp, logger)
            self._create_comparison_graph(graph_data, graphs_dir, sample_name, timestamp, logger)
        else:  # pragma: no cover - optional dependency
            self._log(
                logger,
                "[WARN] matplotlib not available; skipping sequential graphs.",
            )

        return filename

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_iv_dir(
        self, sample_name: str, device_index: int, custom_base: Optional[Path]
    ) -> Path:
        base = Path(custom_base) if custom_base else self.iv_root
        return base / sample_name / str(device_index)

    def _resolve_avg_dir(
        self, sample_name: str, custom_base: Optional[Path]
    ) -> Path:
        base = Path(custom_base) if custom_base else self.avg_root
        return base / sample_name

    @staticmethod
    def _log(logger: Logger, message: str) -> None:
        if callable(logger):
            logger(message)

    # ------------------------------------------------------------------
    # Graph generation
    # ------------------------------------------------------------------
    def _create_individual_graphs(
        self,
        graph_data: Dict[str, Dict[str, np.ndarray]],
        graphs_dir: Path,
        sample_name: str,
        timestamp: str,
        logger: Logger,
    ) -> None:
        if plt is None or cm is None:  # pragma: no cover - optional dependency
            return

        for device, data in graph_data.items():
            if np.all(np.isnan(data["temperatures"])):
                continue

            device_number = data["device_number"]
            device_name = data["device_name"]

            fig, axes = plt.subplots(2, 3, figsize=(18, 12))
            fig.suptitle(
                f"Device {device_number} ({device_name}) - {sample_name}",
                fontsize=16,
            )

            axes[0, 0].plot(data["timestamps"], data["currents"], "b.-")
            axes[0, 0].set_xlabel("Time (s)")
            axes[0, 0].set_ylabel("Current (A)")
            axes[0, 0].set_title("Time vs Current")
            axes[0, 0].grid(True)

            axes[0, 1].plot(data["temperatures"], data["currents"], "r.-")
            axes[0, 1].set_xlabel("Temperature (°C)")
            axes[0, 1].set_ylabel("Current (A)")
            axes[0, 1].set_title("Temperature vs Current")
            axes[0, 1].grid(True)

            axes[0, 2].plot(data["temperatures"], data["conductance"], "g.-")
            axes[0, 2].set_xlabel("Temperature (°C)")
            axes[0, 2].set_ylabel("Conductance (S)")
            axes[0, 2].set_title("Temperature vs Conductance")
            axes[0, 2].grid(True)

            axes[1, 0].plot(
                data["temperatures"], data["conductance_normalized"], "m.-"
            )
            axes[1, 0].set_xlabel("Temperature (°C)")
            axes[1, 0].set_ylabel("Normalized Conductance")
            axes[1, 0].set_title("Temperature vs Normalized Conductance")
            axes[1, 0].grid(True)

            axes[1, 1].plot(
                data["timestamps"],
                data["conductance"],
                color=cm.Blues(0.7),
            )
            axes[1, 1].set_xlabel("Time (s)")
            axes[1, 1].set_ylabel("Conductance (S)")
            axes[1, 1].set_title("Time vs Conductance")
            axes[1, 1].grid(True)

            axes[1, 2].plot(
                data["timestamps"],
                data["conductance_normalized"],
                color=cm.Oranges(0.6),
            )
            axes[1, 2].set_xlabel("Time (s)")
            axes[1, 2].set_ylabel("Normalized Conductance")
            axes[1, 2].set_title("Time vs Normalized Conductance")
            axes[1, 2].grid(True)

            fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            out_path = graphs_dir / f"{sample_name}_{timestamp}_{device}.png"
            fig.savefig(out_path, dpi=200)
            plt.close(fig)
            self._log(logger, f"[GRAPH] Saved {out_path.resolve()}")

    def _create_comparison_graph(
        self,
        graph_data: Dict[str, Dict[str, np.ndarray]],
        graphs_dir: Path,
        sample_name: str,
        timestamp: str,
        logger: Logger,
    ) -> None:
        if plt is None or cm is None:  # pragma: no cover - optional dependency
            return

        fig, ax = plt.subplots(figsize=(10, 6))
        for idx, (device, data) in enumerate(graph_data.items()):
            ax.plot(
                data["timestamps"],
                data["currents"],
                label=device,
                color=cm.viridis(idx / max(len(graph_data) - 1, 1)),
            )

        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Current (A)")
        ax.set_title(f"{sample_name} - Sequential Average Comparison")
        ax.legend(loc="best", fontsize=8)
        ax.grid(True)

        out_path = graphs_dir / f"{sample_name}_{timestamp}_comparison.png"
        fig.tight_layout()
        fig.savefig(out_path, dpi=250)
        plt.close(fig)
        self._log(logger, f"[GRAPH] Saved {out_path.resolve()}")


def _extract_device_number(device_name: str) -> int:
    """Helper that extracts numeric suffix from device identifiers."""
    if "_" in device_name:
        try:
            return int(device_name.split("_")[1])
        except (ValueError, IndexError):
            return 1
    return 1

