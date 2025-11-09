import time
import tkinter as tk
from types import SimpleNamespace

import pytest

from gui.plot_panels import MeasurementPlotPanels
from gui.plot_updaters import PlotUpdaters


def _build_plot_panels(temp_enabled: bool = True):
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()
    frame = tk.Frame(root)
    frame.pack()

    panels = MeasurementPlotPanels()
    panels.create_all_plots(frame, temp_enabled=temp_enabled)

    return SimpleNamespace(root=root, frame=frame, panels=panels)


def test_plot_updaters_populate_live_plots():
    widgets = _build_plot_panels(temp_enabled=True)
    panels = widgets.panels

    dummy_gui = SimpleNamespace(
        measuring=True,
        v_arr_disp=[0.1, 0.5, 1.0],
        c_arr_disp=[0.05, 0.1, 0.2],
        c_arr_disp_abs=[0.05, 0.1, 0.2],
        t_arr_disp=[0.1, 0.5, 1.0],
        r_arr_disp=[10.0, 11.0, 12.0],
        temp_time_disp=[25.0, 26.0, 27.0],
    )

    updaters = PlotUpdaters(gui=dummy_gui, plot_panels=panels, interval_s=0.01)
    updaters.start_all_threads()
    updaters.start_temperature_thread(True)

    try:
        time.sleep(0.2)
    finally:
        updaters.stop_all_threads()
        widgets.root.destroy()

    x_iv, y_iv = panels.lines["rt_iv"].get_data()
    assert list(x_iv) == dummy_gui.v_arr_disp
    assert list(y_iv) == dummy_gui.c_arr_disp

    x_logiv, y_logiv = panels.lines["rt_logiv"].get_data()
    assert list(x_logiv) == dummy_gui.v_arr_disp
    assert all(val > 0 for val in y_logiv)

    x_loglog, y_loglog = panels.lines["rt_logilogv"].get_data()
    assert all(val > 0 for val in x_loglog)
    assert list(y_loglog) == list(y_logiv)

    x_ct, y_ct = panels.lines["ct_rt"].get_data()
    assert list(x_ct) == dummy_gui.t_arr_disp
    assert list(y_ct) == dummy_gui.c_arr_disp

    x_tt, y_tt = panels.lines["tt_rt"].get_data()
    assert list(x_tt) == dummy_gui.t_arr_disp
    assert list(y_tt) == dummy_gui.temp_time_disp


def test_plot_updaters_reuse_existing_threads():
    widgets = _build_plot_panels(temp_enabled=False)
    panels = widgets.panels

    dummy_gui = SimpleNamespace(
        measuring=True,
        v_arr_disp=[0.1, 0.2],
        c_arr_disp=[0.05, 0.1],
        c_arr_disp_abs=[0.05, 0.1],
        t_arr_disp=[0.1, 0.2],
        r_arr_disp=[10.0, 10.5],
        temp_time_disp=[25.0, 25.5],
    )

    updaters = PlotUpdaters(gui=dummy_gui, plot_panels=panels, interval_s=0.01)
    updaters.start_all_threads()
    original_ids = {name: id(thread) for name, thread in updaters.threads.items()}

    try:
        time.sleep(0.05)
        updaters.start_all_threads()
        time.sleep(0.05)
        after_ids = {name: id(thread) for name, thread in updaters.threads.items()}
    finally:
        updaters.stop_all_threads()
        widgets.root.destroy()

    assert original_ids == after_ids


def test_plot_updaters_stop_all_threads_cleans_up():
    widgets = _build_plot_panels(temp_enabled=False)
    panels = widgets.panels

    dummy_gui = SimpleNamespace(
        measuring=True,
        v_arr_disp=[0.1],
        c_arr_disp=[0.05],
        c_arr_disp_abs=[0.05],
        t_arr_disp=[0.1],
        r_arr_disp=[10.0],
        temp_time_disp=[25.0],
    )

    updaters = PlotUpdaters(gui=dummy_gui, plot_panels=panels, interval_s=0.01)
    updaters.start_all_threads()

    try:
        time.sleep(0.05)
    finally:
        updaters.stop_all_threads()
        widgets.root.destroy()

    assert updaters.threads == {}
    assert all(
        not getattr(thread, "is_alive", lambda: False)()
        for thread in updaters.threads.values()
    )

