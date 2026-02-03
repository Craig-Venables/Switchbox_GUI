"""
Device-level combined sweep plots. Used by analysis.aggregators.comprehensive_analyzer.
Plots combined IV (or endurance/retention) sweeps per device from config sweep_combinations.
Style: use plotting.style for dpi and figsize.
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Callable

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from . import style

_dpi = style.get_dpi()


def plot_device_combined_sweeps(
    device_path: Path,
    section: str,
    device_num: str,
    code_name: str,
    sample_name: str,
    test_configs: Dict,
    find_min_sweep: Callable[[Path, str], Optional[int]],
    has_header: Callable[[Path], bool],
    parse_filename: Callable[[str], Optional[Dict]],
) -> None:
    """
    Plot combined sweeps for a single device using sweep_combinations from config.
    Finds the minimum sweep number for the code_name and plots each combination.
    Special handling: endurance (resistance vs cycle), retention (resistance vs time), IV (voltage vs current).
    """
    if not device_path.exists():
        return
    images_dir = device_path / 'images'
    images_dir.mkdir(exist_ok=True)
    min_sweep = find_min_sweep(device_path, code_name)
    if min_sweep is None:
        return
    if code_name not in test_configs:
        return
    config = test_configs[code_name]
    combinations = config.get('sweep_combinations', [])
    if not combinations:
        return
    is_endurance = 'end' in code_name.lower()
    is_retention = 'ret' in code_name.lower()
    for combo in combinations:
        sweeps = combo.get('sweeps', [])
        title = combo.get('title', f"Combination {sweeps}")
        if not sweeps:
            continue
        if is_endurance or is_retention:
            fig = Figure(figsize=style.get_figsize("double"))
            FigureCanvasAgg(fig)
            ax1 = fig.add_subplot(111)
        else:
            fig = Figure(figsize=(16, 6))
            FigureCanvasAgg(fig)
            ax1 = fig.add_subplot(121)
            ax2 = fig.add_subplot(122)
        for relative_sweep in sweeps:
            actual_sweep_num = min_sweep + (relative_sweep - 1)
            sweep_files = list(device_path.glob(f'{actual_sweep_num}-*.txt'))
            sweep_files = [f for f in sweep_files if f.name != 'log.txt']
            matching_files = []
            for f in sweep_files:
                try:
                    parts = f.name.replace('.txt', '').split('-')
                    if len(parts) > 6 and parts[6] == code_name:
                        matching_files.append(f)
                except (ValueError, IndexError):
                    continue
            if matching_files:
                try:
                    data = np.loadtxt(matching_files[0], skiprows=1 if has_header(matching_files[0]) else 0)
                    if data.ndim == 1:
                        data = data.reshape(1, -1)
                    if data.shape[1] < 2:
                        continue
                    file_info = parse_filename(matching_files[0].name)
                    if is_endurance:
                        label = f"Endurance {relative_sweep}"
                        if file_info:
                            label += f" (Sweep {actual_sweep_num})"
                    elif is_retention:
                        label = f"Retention {relative_sweep}"
                        if file_info:
                            label += f" (Sweep {actual_sweep_num})"
                    else:
                        label = f"Sweep {actual_sweep_num}"
                        if file_info and len(sweeps) >= 3:
                            label += f" (V={file_info.get('voltage', '?')}, SD={file_info.get('step_delay', '?')})"
                    if is_endurance:
                        if data.shape[1] >= 4:
                            x_data = data[:, 0]
                            y_data = data[:, 3]
                        else:
                            x_data = np.arange(len(data))
                            y_data = data[:, 1]
                            if np.max(np.abs(y_data)) > 1e-3:
                                voltage = data[:, 0]
                                current = data[:, 1]
                                y_data = np.abs(voltage / (current + 1e-12))
                        ax1.plot(x_data, y_data, label=label, linewidth=1.5, marker='o', markersize=3)
                    elif is_retention:
                        if data.shape[1] >= 4:
                            x_data = data[:, 0]
                            y_data = data[:, 3]
                        else:
                            x_data = data[:, 0]
                            if data.shape[1] >= 3:
                                voltage = data[:, 1]
                                current = data[:, 2]
                                y_data = np.abs(voltage / (current + 1e-12))
                            else:
                                y_data = data[:, 1]
                        ax1.plot(x_data, y_data, label=label, linewidth=1.5, marker='o', markersize=3)
                    else:
                        voltage = data[:, 0]
                        current = data[:, 1]
                        ax1.plot(voltage, current, label=label, linewidth=1.5)
                        ax2.semilogy(voltage, np.abs(current), label=label, linewidth=1.5)
                except Exception as e:
                    print(f"[COMPREHENSIVE] Error reading {matching_files[0]}: {e}")
                    continue
        if is_endurance:
            ax1.set_xlabel('Cycle/Iteration', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Resistance (Ω)', fontsize=12, fontweight='bold')
            ax1.set_title(f"{sample_name} {section}{device_num} {code_name} - {title}", fontsize=13, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            ax1.set_yscale('log')
        elif is_retention:
            ax1.set_xlabel('Time (s)', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Resistance (Ω)', fontsize=12, fontweight='bold')
            ax1.set_title(f"{sample_name} {section}{device_num} {code_name} - {title}", fontsize=13, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            ax1.set_yscale('log')
        else:
            ax1.set_xlabel('Voltage (V)', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Current (A)', fontsize=12, fontweight='bold')
            ax1.set_title(f"{sample_name} {section}{device_num} {code_name} - {title}", fontsize=13, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            ax2.set_xlabel('Voltage (V)', fontsize=12, fontweight='bold')
            ax2.set_ylabel('|Current| (A)', fontsize=12, fontweight='bold')
            ax2.set_title(f"{sample_name} {section}{device_num} {code_name} - {title} (Log)", fontsize=13, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
        fig.tight_layout()
        safe_title = title.replace(" ", "_").replace("/", "-")
        output_file = images_dir / f'{code_name}_{sweeps}_{safe_title}.png'
        try:
            fig.savefig(output_file, dpi=_dpi, bbox_inches='tight')
        except Exception:
            pass
        print(f"[COMPREHENSIVE] Saved: {output_file}")
