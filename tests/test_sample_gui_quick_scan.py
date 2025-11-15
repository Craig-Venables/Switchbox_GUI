"""Tests covering SampleGUI quick scan helpers and persistence."""

import math
import tkinter as tk

import pytest

import gui.sample_gui as Sample_GUI
from gui.sample_gui import SampleGUI


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_current_to_color_gradient(tk_root):
    gui = SampleGUI(tk_root)

    low_color = gui._current_to_color(gui.quick_scan_min_current).lower()
    high_color = gui._current_to_color(gui.quick_scan_max_current).lower()
    mid_current = math.sqrt(gui.quick_scan_min_current * gui.quick_scan_max_current)
    mid_color = gui._current_to_color(mid_current).lower()

    assert low_color == "#ff0000"
    assert high_color == "#00ff00"
    assert mid_color not in {low_color, high_color}


def test_quick_scan_persistence(tmp_path, monkeypatch, tk_root):
    monkeypatch.setattr(Sample_GUI, "BASE_DIR", tmp_path)

    gui = SampleGUI(tk_root)
    gui.sample_type_var.set("TestSample")

    gui.device_mapping = {
        "dev1": {"x_min": 0, "x_max": 10, "y_min": 0, "y_max": 10, "section": "", "sample": "TestSample"},
        "dev2": {"x_min": 10, "x_max": 20, "y_min": 0, "y_max": 10, "section": "", "sample": "TestSample"},
    }
    gui.device_list = list(gui.device_mapping.keys())
    gui._build_device_name_mapping()

    gui.quick_scan_results = {"dev1": 1e-9, "dev2": 5e-7}
    gui.quick_scan_voltage_var.set(0.25)

    gui.save_quick_scan_results()

    storage_dir = tmp_path / "Data_maps" / "TestSample"
    json_path = storage_dir / "quick_scan.json"
    csv_path = storage_dir / "quick_scan.csv"

    assert json_path.exists()
    assert csv_path.exists()

    gui.quick_scan_results = {}
    loaded = gui._load_quick_scan_for_sample("TestSample", silent=False)

    assert loaded
    assert gui.quick_scan_results["dev1"] == pytest.approx(1e-9)
    assert gui.quick_scan_results["dev2"] == pytest.approx(5e-7)

