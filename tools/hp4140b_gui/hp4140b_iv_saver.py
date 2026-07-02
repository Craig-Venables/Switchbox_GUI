"""
Standalone IV data and plot saver for HP4140B GUI.

Duplicated from Measurements/data_saver.py summary plot logic so this tool
can be packaged as its own executable without depending on the main project.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

IMAGES_SUBDIR = "images"


@dataclass
class SummaryPlotData:
    """Line data for summary IV / log plots."""

    all_iv: Iterable[Tuple[Sequence[float], Sequence[float]]]
    all_log: Iterable[Tuple[Sequence[float], Sequence[float]]]
    final_iv: Tuple[Sequence[float], Sequence[float]]


def save_measurement_txt(
    filepath: Path,
    voltages: Sequence[float],
    currents: Sequence[float],
    *,
    sample_number: int,
    loop_indices: Optional[Sequence[int]] = None,
    metadata: Optional[dict] = None,
) -> Path:
    """Save V/I data to a tab-separated text file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    v = np.asarray(voltages, dtype=float)
    i = np.asarray(currents, dtype=float)

    header_lines = [
        f"HP4140B Measurement - Sample {sample_number}",
        f"Saved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if metadata:
        for key, value in metadata.items():
            header_lines.append(f"{key}: {value}")

    if loop_indices is not None and len(loop_indices) == len(v):
        header_lines.append("Loop\tVoltage (V)\tCurrent (A)")
        data = np.column_stack((loop_indices, v, i))
        fmt = "%d\t%.6e\t%.6e"
    else:
        header_lines.append("Voltage (V)\tCurrent (A)")
        data = np.column_stack((v, i))
        fmt = "%.6e\t%.6e"

    np.savetxt(filepath, data, fmt=fmt, header="\n".join(header_lines), comments="")
    return filepath


def save_loop_txt(
    folder: Path,
    sample_number: int,
    timestamp: str,
    loop_index: int,
    voltages: Sequence[float],
    currents: Sequence[float],
    metadata: Optional[dict] = None,
) -> Path:
    """Save a single loop to its own file."""
    filename = f"sample_{sample_number:04d}_{timestamp}_loop_{loop_index:02d}.txt"
    return save_measurement_txt(
        folder / filename,
        voltages,
        currents,
        sample_number=sample_number,
        metadata={**(metadata or {}), "Loop": loop_index},
    )


def save_summary_plots(
    save_dir: Path | str,
    plot_data: SummaryPlotData,
    artifact_label: Optional[str] = None,
    dpi: int = 300,
) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
    """
    Save Final_graph_IV, Final_graph_LOG, and Combined_summary PNGs.

    Mirrors Measurements/data_saver.py::save_summary_plots for standalone use.
    """
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
        from matplotlib.figure import Figure
    except Exception:
        return (None, None, None)

    save_folder = Path(save_dir)
    save_folder.mkdir(parents=True, exist_ok=True)
    pfx = f"{artifact_label}_" if artifact_label else ""

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
            ax_iv.grid(True, alpha=0.3)
            final_iv_path = save_folder / f"{pfx}Final_graph_IV.png"
            fig_iv.savefig(final_iv_path, dpi=dpi, bbox_inches="tight")

            fig_log = Figure(figsize=(4, 3))
            FigureCanvas(fig_log)
            ax_log = fig_log.add_subplot(111)
            ax_log.set_title("Final Sweep (|I|)")
            ax_log.set_xlabel("Voltage (V)")
            ax_log.set_ylabel("|Current| (A)")
            pos_i = [abs(x) if abs(x) > 0 else 1e-15 for x in final_i]
            ax_log.semilogy(final_v, pos_i, marker="o", markersize=2, color="k")
            ax_log.grid(True, alpha=0.3, which="both")
            final_log_path = save_folder / f"{pfx}Final_graph_LOG.png"
            fig_log.savefig(final_log_path, dpi=dpi, bbox_inches="tight")
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
        ax_all_iv.grid(True, alpha=0.3)

        for x, y in plot_data.all_log:
            pos_y = [abs(v) if abs(v) > 0 else 1e-15 for v in y]
            ax_all_log.semilogy(x, pos_y, marker="o", markersize=2, alpha=0.8)
        ax_all_log.set_title("All sweeps (|I|)")
        ax_all_log.set_xlabel("V (V)")
        ax_all_log.set_ylabel("|I| (A)")
        ax_all_log.grid(True, alpha=0.3, which="both")

        if final_v and final_i:
            ax_final_iv.plot(final_v, final_i, marker="o", markersize=2, color="k")
            pos_final = [abs(x) if abs(x) > 0 else 1e-15 for x in final_i]
            ax_final_log.semilogy(final_v, pos_final, marker="o", markersize=2, color="k")

        ax_final_iv.set_title("Final Sweep (IV)")
        ax_final_iv.set_xlabel("Voltage (V)")
        ax_final_iv.set_ylabel("Current (A)")
        ax_final_iv.grid(True, alpha=0.3)
        ax_final_log.set_title("Final Sweep (|I|)")
        ax_final_log.set_xlabel("Voltage (V)")
        ax_final_log.set_ylabel("|Current| (A)")
        ax_final_log.grid(True, alpha=0.3, which="both")

        combined_path = save_folder / f"{pfx}Combined_summary.png"
        fig.tight_layout()
        fig.savefig(combined_path, dpi=dpi, bbox_inches="tight")
    except Exception:
        combined_path = None

    return (final_iv_path, final_log_path, combined_path)


def save_all_graphs(
    save_dir: Path | str,
    plot_data: SummaryPlotData,
    artifact_label: Optional[str] = None,
    dpi: int = 400,
) -> Tuple[Optional[Path], Optional[Path]]:
    """Save All_graphs_IV and All_graphs_LOG PNGs (mirrors measurement GUI)."""
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
        from matplotlib.figure import Figure
    except Exception:
        return (None, None)

    save_folder = Path(save_dir)
    save_folder.mkdir(parents=True, exist_ok=True)
    pfx = f"{artifact_label}_" if artifact_label else ""

    iv_path: Optional[Path] = None
    log_path: Optional[Path] = None

    try:
        fig_iv = Figure(figsize=(6, 4))
        FigureCanvas(fig_iv)
        ax = fig_iv.add_subplot(111)
        ax.set_title("All Sweeps (IV)")
        ax.set_xlabel("Voltage (V)")
        ax.set_ylabel("Current (A)")
        for x, y in plot_data.all_iv:
            ax.plot(x, y, marker="o", markersize=2, alpha=0.8)
        ax.grid(True, alpha=0.3)
        iv_path = save_folder / f"{pfx}All_graphs_IV.png"
        fig_iv.savefig(iv_path, dpi=dpi, bbox_inches="tight")

        fig_log = Figure(figsize=(6, 4))
        FigureCanvas(fig_log)
        ax_log = fig_log.add_subplot(111)
        ax_log.set_title("All Sweeps (|I|)")
        ax_log.set_xlabel("Voltage (V)")
        ax_log.set_ylabel("|Current| (A)")
        for x, y in plot_data.all_log:
            pos_y = [abs(v) if abs(v) > 0 else 1e-15 for v in y]
            ax_log.semilogy(x, pos_y, marker="o", markersize=2, alpha=0.8)
        ax_log.grid(True, alpha=0.3, which="both")
        log_path = save_folder / f"{pfx}All_graphs_LOG.png"
        fig_log.savefig(log_path, dpi=dpi, bbox_inches="tight")
    except Exception:
        iv_path = None
        log_path = None

    return (iv_path, log_path)


def save_measurement_artifacts(
    save_dir: Path | str,
    sample_number: int,
    loop_data: List[Tuple[List[float], List[float]]],
    *,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Save combined data file, per-loop files (if multiple loops), and all IV plots.

    Returns dict of saved file paths for UI feedback.
    """
    save_folder = Path(save_dir)
    save_folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_label = f"sample_{sample_number:04d}"

    all_v: List[float] = []
    all_i: List[float] = []
    loop_indices: List[int] = []
    for loop_idx, (v_list, i_list) in enumerate(loop_data, start=1):
        all_v.extend(v_list)
        all_i.extend(i_list)
        loop_indices.extend([loop_idx] * len(v_list))

    meta = metadata or {}
    saved: dict = {}

    combined_name = f"{artifact_label}_{timestamp}.txt"
    saved["data"] = save_measurement_txt(
        save_folder / combined_name,
        all_v,
        all_i,
        sample_number=sample_number,
        loop_indices=loop_indices if len(loop_data) > 1 else None,
        metadata=meta,
    )

    if len(loop_data) > 1:
        saved["loop_files"] = []
        for loop_idx, (v_list, i_list) in enumerate(loop_data, start=1):
            path = save_loop_txt(
                save_folder, sample_number, timestamp, loop_idx, v_list, i_list, metadata=meta
            )
            saved["loop_files"].append(path)

    plot_data = SummaryPlotData(
        all_iv=[(v, i) for v, i in loop_data],
        all_log=[(v, i) for v, i in loop_data],
        final_iv=loop_data[-1] if loop_data else ([], []),
    )

    images_folder = save_folder / IMAGES_SUBDIR
    images_folder.mkdir(parents=True, exist_ok=True)

    iv_path, log_path = save_all_graphs(images_folder, plot_data, artifact_label=artifact_label)
    final_iv, final_log, combined = save_summary_plots(
        images_folder, plot_data, artifact_label=artifact_label
    )

    saved["plots"] = {
        "folder": images_folder,
        "all_iv": iv_path,
        "all_log": log_path,
        "final_iv": final_iv,
        "final_log": final_log,
        "combined": combined,
    }
    return saved
