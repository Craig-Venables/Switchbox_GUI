"""
Generate example graphs for each subsection (core, device, sample, section, endurance)
using deterministic synthetic data. Run from project root: py plotting/demo/run_all.py
"""
import sys
from pathlib import Path

# Ensure project root (parent of plotting) is on path
_demo_dir = Path(__file__).resolve().parent
_plotting_root = _demo_dir.parent
_project_root = _plotting_root.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_demo_dir) not in sys.path:
    sys.path.insert(0, str(_demo_dir))

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from plotting.core import style
from plotting.core.formatters import plain_log_formatter
from plotting.core.base import PlotManager
from plotting import UnifiedPlotter, SamplePlots
from plotting.device.hdf5_style import HDF5StylePlotter
from plotting.section.section_plots import (
    plot_sweeps_by_type,
    plot_statistical_comparisons,
    plot_customization,
)
from plotting.endurance.endurance_plots import plot_current_vs_cycle, plot_endurance_summary

from synthetic_data import (
    get_iv_arrays,
    get_devices_data,
    make_section_sweeps_by_type,
    get_section_read_data_file,
    get_main_sweep_data,
    get_device_stats,
    get_endurance_data,
    get_concentration_yield_arrays,
)


OUTPUT_DIR = _demo_dir / "output"


def _ensure_output_dirs() -> None:
    for sub in ("core", "device", "sample", "section", "endurance"):
        (OUTPUT_DIR / sub).mkdir(parents=True, exist_ok=True)


def run_core() -> None:
    """Minimal figure using style and formatters so style changes are visible."""
    out = OUTPUT_DIR / "core"
    fig, ax = plt.subplots(figsize=style.get_figsize("single"))
    v = np.logspace(-2, 1, 50)
    ax.semilogy(v, 1e-6 * v**2, "o-", markersize=4)
    ax.xaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
    ax.yaxis.set_major_formatter(FuncFormatter(plain_log_formatter))
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current (A)")
    ax.set_title("Demo: core style + formatters")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "core_demo.png", dpi=style.get_dpi(), bbox_inches="tight")
    plt.close(fig)
    print("[demo] core: core_demo.png")


def run_device() -> None:
    """IV dashboard, conduction, SCLC, optional HDF5-style plot."""
    out = OUTPUT_DIR / "device"
    voltage, current, time = get_iv_arrays()
    plotter = UnifiedPlotter(save_dir=out, auto_close=True)
    plotter.plot_iv_dashboard(
        voltage, current, time=time,
        device_name="DemoDevice",
        save_name="demo_iv_dashboard.png",
    )
    print("[demo] device: demo_iv_dashboard.png")
    plotter.plot_conduction_analysis(
        voltage, current,
        device_name="DemoDevice",
        save_name="demo_conduction.png",
    )
    print("[demo] device: demo_conduction.png")
    plotter.plot_sclc_fit(
        voltage, current,
        device_name="DemoDevice",
        save_name="demo_sclc_fit.png",
    )
    print("[demo] device: demo_sclc_fit.png")
    # HDF5-style
    x, y = get_concentration_yield_arrays()
    hdf5 = HDF5StylePlotter(save_dir=out, auto_close=True)
    fig = hdf5.plot_concentration_yield(x, y, title_suffix="(demo)")
    if fig is not None:
        hdf5.manager.save(fig, "demo_concentration_yield.png")
    print("[demo] device: demo_concentration_yield.png")


def run_sample() -> None:
    """Memristivity heatmap, conduction mechanisms, classification scatter."""
    out = OUTPUT_DIR / "sample"
    devices_data = get_devices_data()
    plotter = SamplePlots(
        devices_data=devices_data,
        plots_dir=str(out),
        sample_name="DemoSample",
    )
    plotter.plot_memristivity_heatmap()
    plotter.plot_conduction_mechanisms()
    plotter.plot_classification_scatter()
    print("[demo] sample: 01_memristivity_heatmap.png, 02_conduction_mechanisms.png, 05_classification_scatter.png")


def run_section() -> None:
    """Sweeps by type and statistical comparisons."""
    out = OUTPUT_DIR / "section"
    stats_dir = out / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    sweeps_by_type = make_section_sweeps_by_type(out)
    read_data_file = get_section_read_data_file()
    plot_sweeps_by_type(
        sweeps_by_type,
        section="a",
        sample_name="DemoSample",
        plots_dir=out,
        read_data_file=read_data_file,
        customizer=plot_customization,
    )
    print("[demo] section: St_v1/sweep_1_combined.png")
    main_sweep_data = get_main_sweep_data()
    device_stats = get_device_stats()
    plot_statistical_comparisons(device_stats, main_sweep_data, stats_dir, "a")
    print("[demo] section: stats/main_sweeps_comparison.png, stats/*_comparison.png")


def run_endurance() -> None:
    """Current vs cycle and summary."""
    out = OUTPUT_DIR / "endurance"
    voltages, extracted_data = get_endurance_data()
    file_name = "demo_endurance"
    for v in voltages:
        plot_current_vs_cycle(v, extracted_data[v], out, file_name)
    print("[demo] endurance: demo_endurance_endurance_1.0V.png")
    plot_endurance_summary(voltages, extracted_data, out, file_name)
    print("[demo] endurance: demo_endurance_endurance_summary.png")


def main() -> None:
    _ensure_output_dirs()
    print("Generating demo plots (deterministic data)...")
    run_core()
    run_device()
    run_sample()
    run_section()
    run_endurance()
    print(f"Done. Outputs in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
