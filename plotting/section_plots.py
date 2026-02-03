"""
Section-level analysis plots. Used by analysis.aggregators.section_analyzer.SectionAnalyzer.
Style: use plotting.style for dpi and figsize.
"""

import numpy as np
from pathlib import Path
from typing import Callable, Optional, Dict, List, Tuple, Any

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from . import style

_dpi = style.get_dpi()


def plot_customization(test_type: str, ax1, ax2) -> None:
    """Apply test-type-specific axis titles and limits."""
    if test_type == 'St_v1':
        ax1.set_title('Standard V1 Test')
        ax2.set_title('Standard V1 Test (Log Scale)')
    elif test_type == 'Dy_v1':
        ax1.set_title('Dynamic V1 Test')
        ax2.set_title('Dynamic V1 Test (Log Scale)')
        ax1.set_ylim(-1e-3, 1e-3)


def create_subplot(title: str):
    """Create a figure with two subplots (linear and log)."""
    w, h = style.get_figsize("double")
    fig = Figure(figsize=(max(w, 15), max(h, 6)))
    FigureCanvasAgg(fig)
    ax1 = fig.add_subplot(121)
    ax2 = fig.add_subplot(122)
    fig.suptitle(title)
    ax2.set_yscale('log')
    return fig, ax1, ax2


def plot_data(voltage: Optional[np.ndarray], current: Optional[np.ndarray], label: str, ax1, ax2) -> None:
    """Plot voltage vs current on both axes (linear and log)."""
    if voltage is not None and current is not None and len(voltage) > 0:
        ax1.plot(voltage, current, 'o-', label=label, markersize=2, linewidth=1, alpha=0.7)
        ax2.plot(voltage, np.abs(current), 'o-', label=label, markersize=2, linewidth=1, alpha=0.7)
        ax1.set_xlabel('Voltage (V)')
        ax1.set_ylabel('Current (A)')
        ax2.set_xlabel('Voltage (V)')
        ax2.set_ylabel('|Current| (A)')


def plot_sweeps_by_type(
    sweeps_by_type: Dict[str, Dict[int, List[Tuple[str, Path]]]],
    section: str,
    sample_name: str,
    plots_dir: Path,
    read_data_file: Callable[[Path], Tuple[Optional[np.ndarray], Optional[np.ndarray], Any]],
    customizer: Callable[[str, Any, Any], None],
) -> None:
    """Generate stacked sweep plots grouped by test type."""
    for test_type, sweeps in sweeps_by_type.items():
        test_type_dir = plots_dir / test_type
        test_type_dir.mkdir(exist_ok=True)
        for sweep_num in sweeps.keys():
            fig, ax1, ax2 = create_subplot(
                f"{sample_name} section {section} {test_type} sweep {sweep_num} combined"
            )
            customizer(test_type, ax1, ax2)
            for device_name, sweep_file in sweeps[sweep_num]:
                voltage, current, _ = read_data_file(sweep_file)
                if voltage is not None:
                    label = f"{section}{device_name} (Sweep {sweep_num})"
                    plot_data(voltage, current, label, ax1, ax2)
            if len(ax1.get_lines()) > 0:
                ax1.legend(fontsize='x-small')
            if len(ax2.get_lines()) > 0:
                ax2.legend(fontsize='x-small')
            try:
                fig.savefig(test_type_dir / f'sweep_{sweep_num}_combined.png', dpi=_dpi)
            except Exception:
                pass


def plot_sweeps_by_voltage(
    sweeps_by_voltage: Dict[str, List[Tuple[str, Path, str]]],
    section: str,
    sample_name: str,
    plots_dir: Path,
    read_data_file: Callable[[Path], Tuple[Optional[np.ndarray], Optional[np.ndarray], Any]],
    customizer: Callable[[str, Any, Any], None],
) -> None:
    """Generate stacked sweep plots grouped by voltage."""
    voltage_dir = plots_dir / 'voltage_groups'
    voltage_dir.mkdir(exist_ok=True)
    for voltage_value, sweeps in sweeps_by_voltage.items():
        fig, ax1, ax2 = create_subplot(
            f"{sample_name} section {section} {voltage_value}V combined"
        )
        sweeps_by_test: Dict[str, List[Tuple[str, Path]]] = {}
        for device_name, sweep_file, test_type in sweeps:
            if test_type not in sweeps_by_test:
                sweeps_by_test[test_type] = []
            sweeps_by_test[test_type].append((device_name, sweep_file))
        for test_type, test_sweeps in sweeps_by_test.items():
            customizer(test_type, ax1, ax2)
            for device_name, sweep_file in test_sweeps:
                voltage, current, _ = read_data_file(sweep_file)
                if voltage is not None:
                    try:
                        sweep_num = int(sweep_file.name.split('-')[0])
                        label = f"{section}{device_name} {test_type} (Sweep {sweep_num})"
                        plot_data(voltage, current, label, ax1, ax2)
                    except Exception:
                        pass
        if len(ax1.get_lines()) > 0:
            ax1.legend(fontsize='x-small')
        if len(ax2.get_lines()) > 0:
            ax2.legend(fontsize='x-small')
        try:
            fig.savefig(voltage_dir / f'voltage_{voltage_value}V_combined.png', dpi=_dpi)
        except Exception:
            pass


def plot_statistical_comparisons(
    device_stats: Dict[int, Dict],
    main_sweep_data: Dict[int, Dict],
    stats_dir: Path,
    section: str,
) -> None:
    """Generate main-sweep overlay and metric bar comparison plots."""
    try:
        if main_sweep_data:
            w, h = style.get_figsize("single")
            fig = Figure(figsize=(max(w, 12), max(h, 12)))
            FigureCanvasAgg(fig)
            ax1 = fig.add_subplot(211)
            ax2 = fig.add_subplot(212)
            fig.suptitle(f'Main Sweep Comparison - Section {section}')
            for device_num, data in main_sweep_data.items():
                label = f"Device {device_num} ({data['test_type']})"
                ax1.plot(data['voltage'], data['current'], label=label)
                ax2.semilogy(data['voltage'], np.abs(data['current']), label=label)
            ax1.set_ylabel('Current (A)')
            ax2.set_ylabel('|Current| (A)')
            ax1.grid(True)
            ax2.grid(True)
            if len(ax1.get_lines()) > 0:
                ax1.legend(fontsize='x-small')
            if len(ax2.get_lines()) > 0:
                ax2.legend(fontsize='x-small')
            fig.tight_layout()
            fig.savefig(stats_dir / 'main_sweeps_comparison.png', dpi=_dpi)
        metrics = [
            ('mean_ron', 'Mean Ron'),
            ('mean_roff', 'Mean Roff'),
            ('mean_on_off_ratio', 'Mean On/Off Ratio'),
            ('avg_normalized_area', 'Average Normalized Area'),
            ('mean_r_02V', 'Mean R at 0.2V'),
            ('mean_r_05V', 'Mean R at 0.5V'),
            ('total_area', 'Total Area'),
            ('max_current', 'Maximum Current'),
            ('max_voltage', 'Maximum Voltage'),
            ('num_loops', 'Number of Loops'),
        ]
        for key, label in metrics:
            devices = []
            values = []
            for d_num, stats in device_stats.items():
                if key in stats and stats[key] is not None:
                    devices.append(d_num)
                    values.append(stats[key])
            if devices:
                fig = Figure(figsize=style.get_figsize("bar"))
                FigureCanvasAgg(fig)
                ax = fig.add_subplot(111)
                ax.bar(devices, values)
                ax.set_title(f'{label} Comparison - Section {section}')
                ax.set_xlabel('Device Number')
                ax.set_ylabel(label)
                if any(v > 0 for v in values) and ('ratio' in key.lower() or 'mean_r' in key.lower()):
                    ax.set_yscale('log')
                fig.tight_layout()
                fig.savefig(stats_dir / f'{key}_comparison.png', dpi=_dpi)
    except Exception as e:
        print(f"Error plotting stats: {e}")
