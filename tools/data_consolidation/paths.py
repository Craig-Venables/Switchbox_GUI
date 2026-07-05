"""OneDrive paths for consolidated IV datasets (synced across PCs)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

TOOL_DIR = Path(__file__).resolve().parent

ONEDRIVE_PHD_DATA = Path(
    r"C:\Users\Craig-Desktop\OneDrive - The University of Nottingham\Documents\Phd\2) Data"
)
ALL_DATA_COLLATED = ONEDRIVE_PHD_DATA / "All_data_collated"

LEGACY_LOCAL_DATA = TOOL_DIR / "data"

DATA_FOLDER_SOURCE = Path(
    r"C:\Users\Craig-Desktop\OneDrive - The University of Nottingham\Documents\Data_folder"
)
QUANTUM_DOTS_SOURCE = ONEDRIVE_PHD_DATA / "1) Devices" / "1) Memristors" / "Quantum Dots"
STOCK_SOURCE = ONEDRIVE_PHD_DATA / "1) Devices" / "1) Memristors" / "Stock"
DANS_DATA_SOURCE = ALL_DATA_COLLATED / "Daniel Whitt (staff)'s files - Data_folder"

SOURCE_DATASETS: List[str] = ["data 1", "Quantum Dots", "Stock", "dans data"]
COMBINED_DATASET = "All combined"

# Filename prefix in merged folder (data1-D108-..., qd-WS2-D15-..., stock-...)
MERGE_TAGS: Dict[str, str] = {
    "data 1": "data1",
    "Quantum Dots": "qd",
    "Stock": "stock",
    "dans data": "dan",
}

DATASETS: Dict[str, Dict[str, object]] = {
    "data 1": {
        "output_name": "data 1",
        "source": DATA_FOLDER_SOURCE,
        "mode": "dxx_top_level",
        "prefix_material": False,
    },
    "Quantum Dots": {
        "output_name": "Quantum Dots",
        "source": QUANTUM_DOTS_SOURCE,
        "mode": "dxx_nested",
        "prefix_material": True,
    },
    "Stock": {
        "output_name": "Stock",
        "source": STOCK_SOURCE,
        "mode": "dxx_nested",
        "prefix_material": True,
    },
    "dans data": {
        "output_name": "dans data",
        "source": DANS_DATA_SOURCE,
        "mode": "named_sample",
        "prefix_material": False,
    },
    COMBINED_DATASET: {
        "output_name": COMBINED_DATASET,
        "mode": "merge",
        "merge_from": list(SOURCE_DATASETS),
    },
}

DEFAULT_DATASET = "data 1"


def dataset_dir(name: str = DEFAULT_DATASET) -> Path:
    if name not in DATASETS:
        raise KeyError(f"Unknown dataset {name!r}. Choose from: {list(DATASETS)}")
    return ALL_DATA_COLLATED / str(DATASETS[name]["output_name"])


def dataset_paths(name: str = DEFAULT_DATASET) -> Dict[str, Path]:
    """Paths for a dataset's flat data + manifests + classification outputs."""
    base = dataset_dir(name)
    return {
        "data_dir": base,
        "manifest": base / "manifest.csv",
        "results_json": base / "classification_results.json",
        "results_csv": base / "classification_results.csv",
        "summary_txt": base / "classification_summary.txt",
        "labels_json": base / "review_labels.json",  # legacy; migrated to corrections_json
        "corrections_json": base / "review_corrections.json",
        "corrections_csv": base / "review_corrections.csv",
        "device_yield_json": base / "device_yield_summary.json",
    }


def is_merge_dataset(name: str) -> bool:
    return str(DATASETS.get(name, {}).get("mode")) == "merge"
