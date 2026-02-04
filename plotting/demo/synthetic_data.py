"""
Deterministic synthetic data for the plotting demo. Same data every run (fixed seed).
"""
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Any

_SEED = 42


def _reset_seed() -> None:
    np.random.seed(_SEED)


# ---------------------------------------------------------------------------
# IV / device: bipolar sweep (0 -> +V -> 0 -> -V -> 0)
# ---------------------------------------------------------------------------

def get_iv_arrays() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (voltage, current, time) for a single bipolar sweep. Deterministic."""
    _reset_seed()
    n = 200
    t = np.linspace(0, 1, n)
    # Bipolar: 0 -> +1 -> 0 -> -1 -> 0
    v = np.sin(np.pi * t) * (1.0 + 0.05 * np.random.randn(n))
    # Memristive-like current: hysteresis, higher at +V
    i = 1e-6 * (np.abs(v) ** 1.5 + 0.1 * np.random.randn(n))
    i = np.clip(i, 1e-9, None)
    time = np.arange(n, dtype=float) * 0.01
    return v, i, time


# ---------------------------------------------------------------------------
# Sample: devices_data for SamplePlots
# ---------------------------------------------------------------------------

def get_devices_data() -> List[Dict[str, Any]]:
    """Minimal devices_data for heatmap, conduction_mechanisms, classification_scatter. Deterministic."""
    _reset_seed()
    devices = []
    for row in ["a", "b"]:
        for col in [1, 2, 3]:
            device_id = f"Demo_{row}_{col}"
            score = 20 + (hash(device_id) % 80)  # 20-99 deterministic
            devices.append({
                "device_id": device_id,
                "classification": {
                    "memristivity_score": score,
                    "device_type": "memristive" if score > 50 else "ohmic",
                    "conduction_mechanism": "SCLC" if score > 60 else "Ohmic",
                },
                "resistance": {
                    "ron_mean": 1e3 * (1 + 0.3 * (hash(device_id) % 10) / 10),
                    "roff_mean": 1e5 * (1 + 0.5 * (hash(device_id + "x") % 10) / 10),
                    "switching_ratio": 50 + (hash(device_id) % 100),
                },
                "hysteresis": {"pinched": True},
            })
    return devices


# ---------------------------------------------------------------------------
# Section: sweeps_by_type and read_data_file
# ---------------------------------------------------------------------------

# One canonical (V, I) for all section demo "files"
_SECTION_V, _SECTION_I = None, None


def _get_section_iv() -> Tuple[np.ndarray, np.ndarray]:
    global _SECTION_V, _SECTION_I
    if _SECTION_V is None:
        _reset_seed()
        n = 150
        v = np.linspace(-1, 1, n) + 0.02 * np.random.randn(n)
        i = 1e-6 * np.abs(v) ** 2 + 1e-8 * np.random.randn(n)
        i = np.clip(i, 1e-10, None)
        _SECTION_V, _SECTION_I = v, i
    return _SECTION_V.copy(), _SECTION_I.copy()


def make_section_sweeps_by_type(plots_dir: Path) -> Dict[str, Dict[int, List[Tuple[str, Path]]]]:
    """
    Build sweeps_by_type for plot_sweeps_by_type. Uses dummy files keyed by path name;
    read_data_file should use get_section_read_data_file() which returns synthetic (V,I) for any path.
    """
    # We don't write real files; we use Path objects as keys and read_data_file returns synthetic data
    dummy_path = plots_dir / "dummy_sweep_1.txt"
    sweeps_by_type = {
        "St_v1": {
            1: [("1", dummy_path), ("2", dummy_path)],
        },
    }
    return sweeps_by_type


def get_section_read_data_file():
    """Return a read_data_file(Path) -> (voltage, current, extra) that returns deterministic data."""
    def read_data_file(path: Path) -> Tuple[np.ndarray, np.ndarray, Any]:
        v, i = _get_section_iv()
        return v, i, None
    return read_data_file


def get_main_sweep_data() -> Dict[int, Dict]:
    """Minimal main_sweep_data for plot_statistical_comparisons. Deterministic."""
    _reset_seed()
    v, i = _get_section_iv()
    return {
        1: {"voltage": v, "current": i, "test_type": "St_v1"},
        2: {"voltage": v * 0.9, "current": i * 1.1, "test_type": "St_v1"},
    }


def get_device_stats() -> Dict[int, Dict]:
    """Minimal device_stats for plot_statistical_comparisons. Deterministic."""
    _reset_seed()
    return {
        1: {"mean_ron": 1e3, "mean_roff": 1e5, "mean_on_off_ratio": 100, "avg_normalized_area": 0.5},
        2: {"mean_ron": 1.2e3, "mean_roff": 1.2e5, "mean_on_off_ratio": 95, "avg_normalized_area": 0.48},
    }


# ---------------------------------------------------------------------------
# Endurance: DataFrame with required column names
# ---------------------------------------------------------------------------

def get_endurance_data() -> Tuple[List[float], Dict[float, pd.DataFrame]]:
    """Return (voltages, extracted_data) for plot_current_vs_cycle and plot_endurance_summary. Deterministic."""
    _reset_seed()
    voltages = [1.0]  # one voltage for simplicity
    n_cycles = 10
    extracted_data = {}
    for v in voltages:
        # Columns: Current_Forward_(OFF)_{v}V, Current_Reverse_(ON)_{v}V, Current_Forward_(ON)_{-v}V, Current_Reverse_(OFF)_{-v}V
        df = pd.DataFrame(
            index=range(1, n_cycles + 1),
            data={
                f"Current_Forward_(OFF)_{v}V": 1e-6 * (1 + 0.1 * np.random.randn(n_cycles)),
                f"Current_Reverse_(ON)_{v}V": 1e-5 * (1 + 0.1 * np.random.randn(n_cycles)),
                f"Current_Forward_(ON)_{-v}V": 1e-5 * (1 + 0.1 * np.random.randn(n_cycles)),
                f"Current_Reverse_(OFF)_{-v}V": 1e-6 * (1 + 0.1 * np.random.randn(n_cycles)),
            },
        )
        df = df.clip(lower=1e-10)
        extracted_data[v] = df
    return voltages, extracted_data


# ---------------------------------------------------------------------------
# HDF5-style: concentration / yield for HDF5StylePlotter
# ---------------------------------------------------------------------------

def get_concentration_yield_arrays() -> Tuple[List[float], List[float]]:
    """Return (x, y) for concentration vs yield. Deterministic."""
    _reset_seed()
    x = [0.01, 0.05, 0.1, 0.2, 0.4]
    y = [0.3 + 0.1 * np.random.rand() for _ in x]
    return x, y
