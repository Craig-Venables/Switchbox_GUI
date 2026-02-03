"""
DC endurance plots: current vs cycle and summary.
Used by analysis.aggregators.dc_endurance_analyzer.
"""

import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
from typing import Dict

from . import style


def plot_current_vs_cycle(
    voltage: float,
    df: pd.DataFrame,
    save_path: Path,
    file_name: str,
    dpi: int = None,
) -> None:
    """Plot current vs cycle for a specific voltage (forward/reverse, positive/negative)."""
    if dpi is None:
        dpi = style.get_dpi()
    fig, ax = plt.subplots(2, 1, figsize=(10, 8))
    ax[0].plot(
        df.index,
        df[f'Current_Forward_(OFF)_{voltage}V'],
        marker='o',
        label=f'OFF Value {voltage}V'
    )
    ax[0].plot(
        df.index,
        df[f'Current_Reverse_(ON)_{voltage}V'],
        marker='o',
        label=f'ON Value {voltage}V'
    )
    ax[0].set_xlabel('Cycle')
    ax[0].set_ylabel('Current (A)')
    ax[0].set_title(f'Current vs Cycle for {voltage}V - {file_name}')
    ax[0].legend()
    ax[0].grid(True)
    ax[1].plot(
        df.index,
        df[f'Current_Forward_(ON)_{-voltage}V'],
        marker='o',
        label=f'ON Value {-voltage}V'
    )
    ax[1].plot(
        df.index,
        df[f'Current_Reverse_(OFF)_{-voltage}V'],
        marker='o',
        label=f'OFF Value {-voltage}V'
    )
    ax[1].set_xlabel('Cycle')
    ax[1].set_ylabel('Current (A)')
    ax[1].set_title(f'Current vs Cycle for {-voltage}V')
    ax[1].legend()
    ax[1].grid(True)
    fig.tight_layout()
    fig_file = Path(save_path) / f'{file_name}_endurance_{voltage}V.png'
    plt.savefig(fig_file, dpi=dpi, bbox_inches='tight')
    plt.close(fig)


def plot_endurance_summary(
    voltages: list,
    extracted_data: Dict[float, pd.DataFrame],
    save_path: Path,
    file_name: str,
    dpi: int = None,
) -> None:
    """Create summary figure with all voltages (current vs cycle per voltage)."""
    if dpi is None:
        dpi = style.get_dpi()
    if not extracted_data:
        return
    num_voltages = len(voltages)
    fig, axs = plt.subplots(num_voltages, 2, figsize=(12, 4 * num_voltages))
    if num_voltages == 1:
        axs = axs.reshape(1, -1)
    for i, v in enumerate(voltages):
        df = extracted_data[v]
        axs[i, 0].plot(df.index, df[f'Current_Forward_(OFF)_{v}V'], marker='o', label=f'OFF Value {v}V')
        axs[i, 0].plot(df.index, df[f'Current_Reverse_(ON)_{v}V'], marker='o', label=f'ON Value {v}V')
        axs[i, 0].set_xlabel('Cycle')
        axs[i, 0].set_ylabel('Current (A)')
        axs[i, 0].set_title(f'Current vs Cycle for {v}V')
        axs[i, 0].legend()
        axs[i, 0].grid(True)
        axs[i, 1].plot(df.index, df[f'Current_Forward_(ON)_{-v}V'], marker='o', label=f'ON Value {-v}V')
        axs[i, 1].plot(df.index, df[f'Current_Reverse_(OFF)_{-v}V'], marker='o', label=f'OFF Value {-v}V')
        axs[i, 1].set_xlabel('Cycle')
        axs[i, 1].set_ylabel('Current (A)')
        axs[i, 1].set_title(f'Current vs Cycle for {-v}V')
        axs[i, 1].legend()
        axs[i, 1].grid(True)
    short_name = file_name.replace('.txt', '') if isinstance(file_name, str) else file_name
    fig.suptitle(f'Current vs Cycle for Different Voltages ({short_name})', fontsize=16)
    fig.tight_layout()
    final_fig_file = Path(save_path) / f'{file_name}_endurance_summary.png'
    plt.savefig(final_fig_file, dpi=dpi, bbox_inches='tight')
    plt.close(fig)
