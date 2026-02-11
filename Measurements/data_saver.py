"""
Measurement data saving helpers.
================================

This module centralises every file system action that used to live inside
`Measurement_GUI.py`.  By funnelling all persistence logic through the
`MeasurementDataSaver` class we keep GUI code focused on orchestration and
make it easier to migrate to other front-ends (Qt, CLI, batch scripts).

The saver is intentionally explicit about the inputs it needs.  Callers must
provide data arrays, sample metadata, and optional custom base directories,
which keeps hidden Tkinter state out of the persistence layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:  # pandas is optional but widely available in this project
    import pandas as pd
except ImportError:  # pragma: no cover - fallback for minimal installs
    pd = None  # type: ignore

from Measurements.data_formats import DataFormatter, FileNamer, save_measurement_data


@dataclass
class SummaryPlotData:
    """
    Container describing the lines used when producing summary plots.

    Attributes:
        all_iv:    Iterable of (voltage, current) sequences for the linear plot.
        all_log:   Iterable of (voltage, current) for the log-magnitude plot.
        final_iv:  Tuple with the latest sweep (voltage, current).
    """

    all_iv: Iterable[Tuple[Sequence[float], Sequence[float]]]
    all_log: Iterable[Tuple[Sequence[float], Sequence[float]]]
    final_iv: Tuple[Sequence[float], Sequence[float]]


class MeasurementDataSaver:
    """
    Persist measurement artefacts (raw data, aggregates, plots, logs).

    The saver keeps directory handling, filename conventions, and formatting
    in one place.  The default base directory mirrors the historical
    `Data_save_loc` tree, while callers can provide a custom base when users
    select a different storage path.
    """

    def __init__(self, default_base: Path | str = "Data_save_loc") -> None:
        self.default_base = Path(default_base)
        self.formatter = DataFormatter()

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------
    def _resolve_base(self, custom_base: Optional[Path | str]) -> Path:
        """Return a writable base directory (custom overrides default)."""
        if custom_base:
            base = Path(custom_base)
        else:
            base = self.default_base
        base.mkdir(parents=True, exist_ok=True)
        return base

    def get_device_folder(
        self,
        sample_name: str,
        device_label: str,
        base_override: Optional[Path | str] = None,
    ) -> Path:
        """
        Resolve the folder used for a particular device.

        Replicates the previous layout `{base}/{sample}/{letter}/{number}` so
        existing downstream scripts keep working.
        """
        base = self._resolve_base(base_override)
        letter = device_label[0] if device_label else "X"
        number = device_label[1:] if len(device_label) > 1 else "0"
        folder = base / sample_name / letter / number
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def get_multiplexer_folder(
        self, sample_name: str, base_override: Optional[Path | str] = None
    ) -> Path:
        """
        Folder used for multiplexer aggregate exports.

        Historical layout: `{base}/Multiplexer_Avg_Measure/{sample}`.
        """
        base = self._resolve_base(base_override)
        folder = base / "Multiplexer_Avg_Measure" / sample_name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    # ------------------------------------------------------------------
    # Saving helpers
    # ------------------------------------------------------------------
    def save_iv_sweep(
        self,
        voltages: Sequence[float],
        currents: Sequence[float],
        timestamps: Sequence[float],
        device_label: str,
        sample_name: str,
        sweep_type: str,
        stop_voltage: float,
        sweeps: int,
        step_voltage: float,
        delay_s: float,
        optical_suffix: str = "",
        metadata: Optional[Dict[str, str]] = None,
        base_override: Optional[Path | str] = None,
    ) -> Path:
        """
        Save a single IV sweep using the standard filename convention.

        Returns the absolute path of the saved file for logging/UI updates.
        """
        folder = self.get_device_folder(sample_name, device_label, base_override)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extra_parts = [
            sweep_type,
            f"{stop_voltage}v",
            f"{step_voltage}sv",
            f"{delay_s}sd",
            f"{sweeps}",
        ]
        if optical_suffix:
            extra_parts.append(optical_suffix)
        if metadata and metadata.get("additional_info"):
            extra_parts.append(metadata["additional_info"])
        filename = f"{timestamp}-{'-'.join(extra_parts)}.txt"
        target = folder / filename
        data, header, fmt = self.formatter.format_iv_data(
            timestamps=np.asarray(timestamps, dtype=float),
            voltages=np.asarray(voltages, dtype=float),
            currents=np.asarray(currents, dtype=float),
        )
        save_measurement_data(target, data, header, fmt)
        return target

    def save_averaged_data(
        self,
        device_data: Dict[str, Dict[str, Sequence[float]]],
        sample_name: str,
        measurement_duration_s: float,
        record_temperature: bool,
        interrupted: bool = False,
        base_override: Optional[Path | str] = None,
    ) -> List[Path]:
        """
        Persist averaged multiplexer measurements for every device.

        Args:
            device_data: mapping of device name -> arrays used during export.
            sample_name: folder name used when organising results.
            measurement_duration_s: duration string appended to filenames.
            record_temperature: whether temperature arrays contain real data.
            interrupted: flag indicating whether the measurement stopped early.
            base_override: optional root directory chosen by the user.

        Returns:
            List of saved file paths.
        """
        saved_files: List[Path] = []
        base_dir = self.get_multiplexer_folder(sample_name, base_override)

        for device, payload in device_data.items():
            currents = np.asarray(payload.get("currents", []), dtype=float)
            if currents.size == 0:
                continue

            timestamps = np.asarray(payload.get("timestamps", []), dtype=float)
            voltages = np.asarray(payload.get("voltages", []), dtype=float)
            std_errors = np.asarray(payload.get("std_errors", []), dtype=float)

            with np.errstate(divide="ignore", invalid="ignore"):
                resistance = np.divide(voltages, currents)
                conductance = np.divide(currents, voltages)
            resistance[~np.isfinite(resistance)] = np.nan
            conductance[~np.isfinite(conductance)] = np.nan

            if record_temperature and payload.get("temperatures"):
                temperatures = np.asarray(payload["temperatures"], dtype=float)
            else:
                temperatures = np.full_like(timestamps, np.nan, dtype=float)

            first_valid = np.nanmax(np.abs(conductance))
            if np.isnan(first_valid) or first_valid == 0:
                conductance_normalized = np.full_like(conductance, np.nan)
            else:
                conductance_normalized = conductance / first_valid

            data = np.column_stack(
                (
                    timestamps,
                    temperatures,
                    voltages,
                    currents,
                    std_errors,
                    resistance,
                    conductance,
                    conductance_normalized,
                )
            )

            header = (
                "Time(s)\tTemperature(C)\tVoltage(V)\tCurrent(A)\tStd_Error(A)"
                "\tResistance(Ohm)\tConductance(S)\tConductance_Normalized"
            )
            fmt = "\t".join(["%0.3E"] * data.shape[1])

            # Filename uses the historical convention.
            device_number = 0
            try:
                device_number = int(device.split("_")[1])
            except Exception:
                pass
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            voltage = voltages[0] if voltages.size else 0
            status = "interrupted" if interrupted else "complete"
            filename = (
                f"Device_{device_number}_{device}_{voltage}V_{measurement_duration_s}s_"
                f"{currents.size}measurements_{status}_{timestamp_str}.txt"
            )

            device_folder = base_dir / str(device_number)
            device_folder.mkdir(parents=True, exist_ok=True)
            target = device_folder / filename
            np.savetxt(target, data, fmt=fmt, header=header, comments="# ")
            saved_files.append(target)

        return saved_files

    def save_all_measurements_file(
        self,
        device_data: Dict[str, Dict[str, Sequence[float]]],
        sample_name: str,
        record_temperature: bool,
        base_override: Optional[Path | str] = None,
    ) -> Optional[Path]:
        """
        Save a consolidated CSV and companion graphs for all devices.

        Returns the CSV path, or ``None`` if pandas is not available.
        """
        if pd is None:
            return None

        base_dir = self.get_multiplexer_folder(sample_name, base_override)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = base_dir / f"{sample_name}_{timestamp}_all.csv"

        columns: Dict[str, Sequence[float]] = {}
        graph_data: Dict[str, Dict[str, np.ndarray]] = {}

        for device, payload in device_data.items():
            device_number = 0
            try:
                device_number = int(device.split("_")[1])
            except Exception:
                pass
            device_display = f"D{device_number}_{device}"

            timestamps = np.asarray(payload.get("timestamps", []), dtype=float)
            voltages = np.asarray(payload.get("voltages", []), dtype=float)
            currents = np.asarray(payload.get("currents", []), dtype=float)
            std_errors = np.asarray(payload.get("std_errors", []), dtype=float)

            with np.errstate(divide="ignore", invalid="ignore"):
                resistance = np.divide(voltages, currents)
                conductance = np.divide(currents, voltages)
            resistance[~np.isfinite(resistance)] = np.nan
            conductance[~np.isfinite(conductance)] = np.nan

            if record_temperature and payload.get("temperatures"):
                temperatures = np.asarray(payload["temperatures"], dtype=float)
            else:
                temperatures = np.full_like(timestamps, np.nan, dtype=float)

            max_cond = np.nanmax(np.abs(conductance))
            if np.isnan(max_cond) or max_cond == 0:
                conductance_normalized = np.full_like(conductance, np.nan)
            else:
                conductance_normalized = conductance / max_cond

            columns[f"Time({device_display})"] = timestamps
            columns[f"Temperature({device_display})"] = temperatures
            columns[f"Voltage({device_display})"] = voltages
            columns[f"Current({device_display})"] = currents
            columns[f"StdError({device_display})"] = std_errors
            columns[f"Resistance({device_display})"] = resistance
            columns[f"Conductance({device_display})"] = conductance
            columns[f"Conductance_Normalized({device_display})"] = conductance_normalized

            graph_data[device] = {
                "device_number": device_number,
                "device_name": device,
                "timestamps": timestamps,
                "temperatures": temperatures,
                "currents": currents,
                "conductance": conductance,
                "conductance_normalized": conductance_normalized,
            }

        df = pd.DataFrame(dict((k, pd.Series(v)) for k, v in columns.items()))
        df.to_csv(filename, index=False)

        graphs_dir = base_dir / "graphs"
        graphs_dir.mkdir(parents=True, exist_ok=True)
        self._create_individual_device_graphs(graph_data, graphs_dir, sample_name, timestamp)
        self._create_comparison_graph(graph_data, graphs_dir, sample_name, timestamp)
        return filename

    def save_temperature_log(
        self,
        entries: Sequence[Tuple[float, float]],
        sample_name: str,
        base_override: Optional[Path | str] = None,
    ) -> Optional[Path]:
        """Persist a temperature log gathered during measurement runs."""
        if not entries:
            return None
        base = self._resolve_base(base_override)
        folder = base / "Temperature_Logs"
        folder.mkdir(parents=True, exist_ok=True)
        start_time = entries[0][0]
        target = folder / f"Temperature_Log_{sample_name}_{datetime.now():%Y%m%d_%H%M%S}.txt"
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("Time(s)\tTemperature(C)\n")
            for timestamp, temp in entries:
                handle.write(f"{timestamp - start_time:.1f}\t{temp:.2f}\n")
        return target

    # ------------------------------------------------------------------
    # Measurement timeline log (single CSV line per measurement)
    # ------------------------------------------------------------------
    LOG_HEADER = "entry#,datetime,filename,location,measurement_type,status"

    def _parse_device_folder(self, device_folder: Path) -> Tuple[str, str, str]:
        """Get sample_name, section, device_number from device folder path (base/sample/letter/number)."""
        parts = Path(device_folder).parts
        if len(parts) >= 3:
            return (parts[-3], parts[-2], parts[-1])
        if len(parts) == 2:
            return ("", parts[-2], parts[-1])
        if len(parts) == 1 and parts[0]:
            return ("", "", parts[0])
        return ("", "", "")

    def _ensure_log_header(
        self,
        log_path: Path,
        sample_name: str,
        section: str,
        device_number: str,
    ) -> None:
        """Write sample/section/device header at top of log file if file is new or empty."""
        if log_path.exists() and log_path.stat().st_size > 0:
            with open(log_path, "r", encoding="utf-8") as f:
                first = f.readline()
            if first.strip().startswith("Sample:"):
                return
        folder = log_path.parent
        folder.mkdir(parents=True, exist_ok=True)
        header = f"Sample: {sample_name}, Section: {section}, Device: {device_number}\n"
        if log_path.exists():
            existing = log_path.read_text(encoding="utf-8")
            log_path.write_text(header + self.LOG_HEADER + "\n" + existing, encoding="utf-8")
        else:
            log_path.write_text(header + self.LOG_HEADER + "\n", encoding="utf-8")
        # Mirror to log.csv so it opens in Excel when double-clicked
        csv_path = folder / "log.csv"
        csv_path.write_text(log_path.read_text(encoding="utf-8"), encoding="utf-8")

    def _get_next_entry_number(self, log_path: Path) -> int:
        """Return next sequential entry number for this device log (1-based)."""
        if not log_path.exists():
            return 1
        max_num = 0
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("Sample:") or line == self.LOG_HEADER:
                    continue
                if "," in line:
                    try:
                        entry_num = int(line.split(",", 1)[0])
                        if entry_num > max_num:
                            max_num = entry_num
                    except ValueError:
                        pass
        return max_num + 1

    def _calculate_relative_path(self, log_dir: Path, measurement_path: Optional[Path]) -> str:
        """Return path of measurement file relative to log file directory, or 'unsaved'."""
        if measurement_path is None:
            return "unsaved"
        try:
            log_dir = log_dir.resolve()
            meas = Path(measurement_path).resolve()
            if not meas.is_absolute():
                return "unsaved"
            try:
                rel = meas.relative_to(log_dir)
                return str(rel).replace("\\", "/")
            except ValueError:
                return "unsaved"
        except Exception:
            return "unsaved"

    def log_measurement_event(
        self,
        device_folder: Path | str,
        filename: str,
        file_path: Optional[Path | str],
        measurement_type: str,
        status: str,
        sample_name: Optional[str] = None,
        section: Optional[str] = None,
        device_number: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Append one CSV line to log.txt in the device folder for measurement timeline tracking.
        Uses readable datetime format: 2026-01-09 19:19:28.
        Returns path to log file, or None on error.
        """
        folder = Path(device_folder)
        folder.mkdir(parents=True, exist_ok=True)
        log_path = folder / "log.txt"
        sn, sec, dev = (sample_name, section, device_number) if (sample_name is not None and section is not None and device_number is not None) else self._parse_device_folder(folder)
        self._ensure_log_header(log_path, sn or "?", sec or "?", dev or "?")
        entry_num = self._get_next_entry_number(log_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        location = self._calculate_relative_path(folder, Path(file_path) if file_path else None)
        row = [str(entry_num), now, filename, location, measurement_type, status]
        with open(log_path, "a", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(row)
        # Append same row to log.csv for Excel
        csv_path = folder / "log.csv"
        if csv_path.exists():
            with open(csv_path, "a", encoding="utf-8") as handle:
                csv.writer(handle, lineterminator="\n").writerow(row)
        else:
            # First data row: ensure header exists in csv (e.g. if log.txt was created before csv was added)
            header = f"Sample: {sn or '?'}, Section: {sec or '?'}, Device: {dev or '?'}\n"
            csv_path.write_text(header + self.LOG_HEADER + "\n", encoding="utf-8")
            with open(csv_path, "a", encoding="utf-8") as handle:
                csv.writer(handle, lineterminator="\n").writerow(row)
        return log_path

    def log_unsaved_measurement(
        self,
        device_folder: Path | str,
        measurement_type: str,
        params: Optional[Dict[str, Any]] = None,
        sample_name: Optional[str] = None,
        section: Optional[str] = None,
        device_number: Optional[str] = None,
    ) -> Optional[Path]:
        """Log an unsaved measurement with key parameters in filename field."""
        parts = [measurement_type]
        if params:
            for k in ("pulse_voltage", "voltage", "V", "v", "bias_voltage"):
                if k in params and params[k] is not None:
                    v = params[k]
                    parts.append(f"{v}v" if isinstance(v, (int, float)) else str(v))
                    break
            for k in ("pulse_duration", "duration", "duration_s", "width_ms"):
                if k in params and params[k] is not None:
                    v = params[k]
                    if isinstance(v, (int, float)):
                        parts.append(f"{v}s" if v >= 1 else f"{v*1000}ms")
                    else:
                        parts.append(str(v))
                    break
            for k in ("loops", "n_loops", "sweeps", "num_measurements"):
                if k in params and params[k] is not None:
                    parts.append(f"{params[k]}loops")
                    break
        filename = "unsaved(" + ",".join(parts) + ")"
        return self.log_measurement_event(
            device_folder,
            filename=filename,
            file_path=None,
            measurement_type=measurement_type,
            status="unsaved",
            sample_name=sample_name,
            section=section,
            device_number=device_number,
        )

    def create_log_file(
        self,
        save_dir: Path | str,
        start_time: str,
        measurement_type: str,
    ) -> Path:
        """
        Append an entry to `log.txt` inside ``save_dir`` documenting the run.
        Prefer log_measurement_event() for new timeline format.
        """
        folder = Path(save_dir)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "log.txt"
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"Measurement started at: {start_time}\n")
            handle.write(f"Measurement ended at: {end_time}\n")
            handle.write(f"Time Taken: {end_time}\n")
            handle.write(f"Measurement Type: {measurement_type}\n")
            handle.write("-" * 40 + "\n")
        return target

    def save_summary_plots(
        self,
        save_dir: Path | str,
        plot_data: SummaryPlotData,
    ) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """
        Persist the final sweep (IV + log) and combined summary plots.
        """
        try:
            from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
            from matplotlib.figure import Figure
        except Exception:  # pragma: no cover - matplotlib missing
            return (None, None, None)

        save_folder = Path(save_dir)
        save_folder.mkdir(parents=True, exist_ok=True)

        final_v, final_i = plot_data.final_iv
        final_iv_path: Optional[Path] = None
        final_log_path: Optional[Path] = None
        combined_path: Optional[Path] = None

        if final_v and final_i:
            try:
                fig_iv = Figure(figsize=(4, 3))
                FigureCanvas(fig_iv)
                ax_iv = fig_iv.add_subplot(111)
                ax_iv.set_title("Final Sweep (IV)")
                ax_iv.set_xlabel("Voltage (V)")
                ax_iv.set_ylabel("Current (A)")
                ax_iv.plot(final_v, final_i, marker="o", markersize=2, color="k")
                final_iv_path = save_folder / "Final_graph_IV.png"
                fig_iv.savefig(final_iv_path, dpi=300)

                fig_log = Figure(figsize=(4, 3))
                FigureCanvas(fig_log)
                ax_log = fig_log.add_subplot(111)
                ax_log.set_title("Final Sweep (|I|)")
                ax_log.set_xlabel("Voltage (V)")
                ax_log.set_ylabel("|Current| (A)")
                ax_log.semilogy(final_v, np.abs(final_i), marker="o", markersize=2, color="k")
                final_log_path = save_folder / "Final_graph_LOG.png"
                fig_log.savefig(final_log_path, dpi=300)
            except Exception:
                final_iv_path = None
                final_log_path = None

        try:
            fig = Figure(figsize=(8, 6))
            FigureCanvas(fig)
            ax_all_iv = fig.add_subplot(221)
            ax_all_log = fig.add_subplot(222)
            ax_final_iv = fig.add_subplot(223)
            ax_final_log = fig.add_subplot(224)

            for x, y in plot_data.all_iv:
                ax_all_iv.plot(x, y, marker="o", markersize=2, alpha=0.8)
            ax_all_iv.set_title("All sweeps (IV)")
            ax_all_iv.set_xlabel("V (V)")
            ax_all_iv.set_ylabel("I (A)")

            for x, y in plot_data.all_log:
                ax_all_log.semilogy(x, np.abs(y), marker="o", markersize=2, alpha=0.8)
            ax_all_log.set_title("All sweeps (|I|)")
            ax_all_log.set_xlabel("V (V)")
            ax_all_log.set_ylabel("|I| (A)")

            if final_v and final_i:
                ax_final_iv.plot(final_v, final_i, marker="o", markersize=2, color="k")
                ax_final_log.semilogy(final_v, np.abs(final_i), marker="o", markersize=2, color="k")

            ax_final_iv.set_title("Final Sweep (IV)")
            ax_final_iv.set_xlabel("Voltage (V)")
            ax_final_iv.set_ylabel("Current (A)")
            ax_final_log.set_title("Final Sweep (|I|)")
            ax_final_log.set_xlabel("Voltage (V)")
            ax_final_log.set_ylabel("|Current| (A)")

            combined_path = save_folder / "Combined_summary.png"
            fig.tight_layout()
            fig.savefig(combined_path, dpi=300)
        except Exception:
            combined_path = None

        return (final_iv_path, final_log_path, combined_path)

    # ------------------------------------------------------------------
    # Plot helpers (internal)
    # ------------------------------------------------------------------
    def _create_individual_device_graphs(
        self,
        graph_data: Dict[str, Dict[str, np.ndarray]],
        graphs_dir: Path,
        sample_name: str,
        timestamp: str,
    ) -> None:
        """Create individual multiplexer graphs (non-interactive backend)."""
        try:
            import matplotlib.cm as cm
            import matplotlib.pyplot as plt
            from matplotlib import use as mpl_use

            mpl_use("Agg", force=True)
        except Exception:  # pragma: no cover
            return

        for device, data in graph_data.items():
            temps = data["temperatures"]
            if temps.size == 0 or np.all(np.isnan(temps)):
                continue

            fig, axes = plt.subplots(2, 3, figsize=(18, 12), constrained_layout=True)
            fig.suptitle(f'Device {data["device_number"]} ({device}) - {sample_name}', fontsize=16)

            axes[0, 0].plot(data["timestamps"], data["currents"], "b.-")
            axes[0, 0].set_xlabel("Time (s)")
            axes[0, 0].set_ylabel("Current (A)")
            axes[0, 0].set_title("Time vs Current")
            axes[0, 0].grid(True)

            axes[0, 1].plot(temps, data["currents"], "r.-")
            axes[0, 1].set_xlabel("Temperature (°C)")
            axes[0, 1].set_ylabel("Current (A)")
            axes[0, 1].set_title("Temperature vs Current")
            axes[0, 1].grid(True)

            axes[0, 2].plot(temps, data["conductance"], "g.-")
            axes[0, 2].set_xlabel("Temperature (°C)")
            axes[0, 2].set_ylabel("Conductance (S)")
            axes[0, 2].set_title("Temperature vs Conductance")
            axes[0, 2].grid(True)

            axes[1, 0].plot(temps, data["conductance_normalized"], "m.-")
            axes[1, 0].set_xlabel("Temperature (°C)")
            axes[1, 0].set_ylabel("Normalized Conductance")
            axes[1, 0].set_title("Temperature vs Normalized Conductance")
            axes[1, 0].grid(True)

            temp_kelvin = temps + 273.15
            valid_mask = temp_kelvin > 0
            if np.any(valid_mask):
                temp_filtered = temp_kelvin[valid_mask]
                cond_norm_filtered = data["conductance_normalized"][valid_mask]
                axes[1, 1].loglog(temp_filtered ** (-0.25), cond_norm_filtered, "c.-", label="T^(-1/4)")
                axes[1, 1].loglog(temp_filtered ** (-1 / 3), cond_norm_filtered, "y.-", label="T^(-1/3)")
                axes[1, 1].loglog(temp_filtered ** (-0.5), cond_norm_filtered, "k.-", label="T^(-1/2)")
                axes[1, 1].set_xlabel("Temperature^(-n) (K^(-n))")
                axes[1, 1].set_ylabel("Normalized Conductance")
                axes[1, 1].set_title("Power Law: T^(-n) vs Normalized Conductance")
                axes[1, 1].legend()
                axes[1, 1].grid(True)

            # Remove spare subplot used in the Tk version.
            fig.delaxes(axes[1, 2])

            graph_filename = f"Device_{data['device_number']}_{device}_{sample_name}_{timestamp}.png"
            fig.savefig(graphs_dir / graph_filename, dpi=300)
            plt.close(fig)

    def _create_comparison_graph(
        self,
        graph_data: Dict[str, Dict[str, np.ndarray]],
        graphs_dir: Path,
        sample_name: str,
        timestamp: str,
    ) -> None:
        """Create a single comparison chart across all devices."""
        try:
            import matplotlib.cm as cm
            import matplotlib.pyplot as plt
            from matplotlib import use as mpl_use

            mpl_use("Agg", force=True)
        except Exception:  # pragma: no cover
            return

        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        colors = cm.tab10(np.linspace(0, 1, len(graph_data))) if graph_data else []

        for idx, (device, data) in enumerate(graph_data.items()):
            temps = data["temperatures"]
            if temps.size == 0 or np.all(np.isnan(temps)):
                continue
            ax.plot(
                temps,
                data["conductance_normalized"],
                ".-",
                color=colors[idx] if len(colors) > idx else None,
                label=f'Device {data["device_number"]}',
                linewidth=2,
                markersize=6,
            )

        ax.set_xlabel("Temperature (°C)", fontsize=12)
        ax.set_ylabel("Normalized Conductance", fontsize=12)
        ax.set_title(f"All Devices - Temperature vs Normalized Conductance\n{sample_name}", fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        fig.tight_layout()

        comparison_path = graphs_dir / f"All_Devices_Comparison_{sample_name}_{timestamp}.png"
        fig.savefig(comparison_path, dpi=300)
        plt.close(fig)


# ----------------------------------------------------------------------
# Lightweight diagnostics
# ----------------------------------------------------------------------
def _run_self_test() -> Dict[str, str]:
    """
    Minimal smoke test used by `python -m Measurements.data_saver`.

    Ensures that the saver can create folders, dump numeric data, and write
    summary plots without raising. The function returns a JSON-friendly dict
    describing the generated artefacts so it can be inspected quickly.
    """
    import tempfile

    saver = MeasurementDataSaver()
    report: Dict[str, str] = {}

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        device_payload = {
            "Device_1": {
                "timestamps": [0, 1, 2],
                "voltages": [0.0, 0.5, 1.0],
                "currents": [0.0, 1e-3, 2e-3],
                "std_errors": [0.0, 1e-5, 2e-5],
                "temperatures": [25.0, 26.0, 27.0],
            }
        }
        saved = saver.save_averaged_data(
            device_payload,
            sample_name="SelfTest",
            measurement_duration_s=1.5,
            record_temperature=True,
            base_override=base,
        )
        report["averaged_count"] = str(len(saved))

        csv_path = saver.save_all_measurements_file(
            device_payload,
            sample_name="SelfTest",
            record_temperature=True,
            base_override=base,
        )
        report["csv_exists"] = str(csv_path is not None and csv_path.exists())

        plot_info = SummaryPlotData(
            all_iv=[([0, 1], [0, 1e-3])],
            all_log=[([0, 1], [0, 1e-3])],
            final_iv=([0, 1], [0, 1e-3]),
        )
        _, _, combined = saver.save_summary_plots(base, plot_info)
        report["combined_plot"] = str(combined is not None and combined.exists())

    return report


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    result = _run_self_test()
    print(json.dumps(result, indent=2))

