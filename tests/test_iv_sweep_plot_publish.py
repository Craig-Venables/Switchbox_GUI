"""Completed DC IV sweeps must land on the live and all-sweeps plots."""

from __future__ import annotations

from pathlib import Path

import pytest

from Measurements.single_measurement_runner import SingleMeasurementRunner

_RUNNER_PATH = Path(__file__).resolve().parents[1] / "Measurements" / "single_measurement_runner.py"


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Canvas:
    def __init__(self, log: list):
        self.log = log
        self.key = ""

    def draw(self):
        self.log.append(self.key)


class _Updaters:
    def __init__(self):
        self.lines: list[tuple[str, list, list]] = []

    def _update_line(self, key, x, y):
        self.lines.append((key, list(x), list(y)))


class _Panels:
    def __init__(self, canvas_log: list):
        self.shown: list[tuple] = []
        self.canvases = {}
        for key in ("rt_iv", "rt_logiv", "ct_rt"):
            canvas = _Canvas(canvas_log)
            canvas.key = key
            self.canvases[key] = canvas
        self.measuring_at_show = None

    def graphs_show(self, v_arr, c_arr, key, stop_v):
        gui = getattr(self, "gui", None)
        self.measuring_at_show = None if gui is None else gui.measuring
        self.shown.append((list(v_arr), list(c_arr), str(key), stop_v))


class _Keithley:
    def __init__(self):
        self.on_point = None
        self.saw_callback = False

    def set_voltage(self, *_args, **_kwargs):
        return None

    def enable_output(self, *_args, **_kwargs):
        return None

    def do_iv_sweep(self, config, psu, optical, should_stop, on_point):
        self.on_point = on_point
        self.saw_callback = on_point is not None
        # Incremental callback must not be the data that gets published.
        if on_point is not None:
            on_point(9.0, 9.0, 9.0)
        return [0.0, 0.5, 1.0], [0.0, 1e-6, 2e-6], [0.0, 0.01, 0.02]


def _gui(save_dir: Path):
    canvas_log: list[str] = []
    panels = _Panels(canvas_log)
    updaters = _Updaters()

    class Gui:
        def __init__(self):
            self.v_arr_disp: list = []
            self.c_arr_disp: list = []
            self.t_arr_disp: list = []
            self.measuring = True
            self.SMU_type = "Keithley 4200A"
            self.start_voltage = _Var(0.0)
            self.voltage_high = _Var(1.0)
            self.sweeps = _Var(1)
            self.step_size = _Var(0.02)
            self.step_delay = _Var(0.01)
            self.icc = _Var(1e-3)
            self.pause = _Var(0.0)
            self.led = _Var(False)
            self.led_power = _Var(1.0)
            self.sequence = _Var("")
            self.use_custom_save_var = _Var(True)
            self.custom_save_location = str(save_dir)
            self.current_device = "D1"
            self.device_list = ["D1"]
            self.single_device_flag = True
            self.sample_name_var = _Var("sample")
            self.final_device_letter = "A"
            self.final_device_number = "1"
            self.keithley = _Keithley()
            self.master = type("Master", (), {"update": staticmethod(lambda: None)})()
            self.telegram = None
            self.plot_updaters = updaters
            self.plot_panels = panels
            self.canvas_log = canvas_log
            self.summary_measuring: list = []
            self._save_dir = str(save_dir)

        def _safe_get_float(self, var, name, default=None):
            try:
                return float(var.get())
            except Exception:
                return default

        def bring_to_top(self):
            return None

        def set_status_message(self, _msg):
            return None

        def log_terminal(self, _msg):
            return None

        def _get_save_directory(self, _sample, _letter, _number):
            return self._save_dir

        def _run_analysis_if_enabled(self, **_kwargs):
            return None

        def _finalize_output(self):
            return None

        def _save_summary_artifacts(self, _save_dir):
            self.summary_measuring.append(self.measuring)

    gui = Gui()
    panels.gui = gui
    return gui


def test_publish_helper_updates_live_lines_and_all_sweeps():
    gui = _gui(Path("."))
    runner = SingleMeasurementRunner(gui)
    voltages = [0.0, 0.5, 1.0]
    currents = [0.0, 1e-6, 2e-6]
    times = [0.0, 0.01, 0.02]

    runner._publish_completed_iv_sweep(voltages, currents, times, "4", 1.0)

    keys = [key for key, _x, _y in gui.plot_updaters.lines]
    assert keys == ["rt_iv", "rt_logiv", "ct_rt"]
    by_key = {key: (x, y) for key, x, y in gui.plot_updaters.lines}
    assert by_key["rt_iv"] == (voltages, currents)
    assert by_key["rt_logiv"][0] == voltages
    assert by_key["rt_logiv"][1][0] == pytest.approx(1e-12)
    assert by_key["rt_logiv"][1][1:] == currents[1:]
    assert by_key["ct_rt"] == (times, currents)
    assert gui.canvas_log == ["rt_iv", "rt_logiv", "ct_rt"]
    assert gui.plot_panels.shown == [(voltages, currents, "4", 1.0)]
    assert gui.v_arr_disp == voltages
    assert gui.c_arr_disp == currents
    assert gui.t_arr_disp == times


def test_publish_helper_skips_missing_plots_and_keeps_data():
    class Gui:
        def __init__(self):
            self.v_arr_disp = [1.0]
            self.c_arr_disp = [1.0]
            self.t_arr_disp = [1.0]

    gui = Gui()
    runner = SingleMeasurementRunner(gui)
    runner._publish_completed_iv_sweep([0.2, 0.4], [3e-9, 4e-9], [0.0, 0.1], "1", 0.4)
    assert gui.v_arr_disp == [0.2, 0.4]
    assert gui.c_arr_disp == [3e-9, 4e-9]
    assert gui.t_arr_disp == [0.0, 0.1]


def test_publish_helper_swallows_graphs_show_errors():
    class Panels:
        canvases: dict = {}

        def graphs_show(self, *_args, **_kwargs):
            raise RuntimeError("plot failed")

    class Gui:
        def __init__(self):
            self.v_arr_disp = []
            self.c_arr_disp = []
            self.t_arr_disp = []
            self.plot_panels = Panels()

    gui = Gui()
    runner = SingleMeasurementRunner(gui)
    runner._publish_completed_iv_sweep([1.0], [2e-9], [0.0], "1", 1.0)
    assert gui.v_arr_disp == [1.0]
    assert gui.c_arr_disp == [2e-9]


def test_fast_4200_branch_publishes_returned_sweep(tmp_path, monkeypatch):
    import Measurements.single_measurement_runner as runner_mod

    monkeypatch.setattr(runner_mod.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(runner_mod.messagebox, "showinfo", lambda *_a, **_k: None)

    gui = _gui(tmp_path)
    runner = SingleMeasurementRunner(gui)
    runner.run_standard_iv()

    assert gui.keithley.saw_callback is True
    assert gui.keithley.on_point is not None
    voltages = [0.0, 0.5, 1.0]
    currents = [0.0, 1e-6, 2e-6]
    assert gui.v_arr_disp == voltages
    assert 9.0 not in gui.v_arr_disp
    assert gui.c_arr_disp == currents
    assert gui.t_arr_disp == [0.0, 0.01, 0.02]
    keys = [key for key, _x, _y in gui.plot_updaters.lines]
    assert keys == ["rt_iv", "rt_logiv", "ct_rt"]
    assert gui.plot_panels.shown[0][0] == voltages
    assert gui.plot_panels.shown[0][1] == currents
    assert gui.plot_panels.shown[0][2] == "0"
    assert gui.plot_panels.measuring_at_show is True
    assert gui.summary_measuring == [False]
    assert gui.canvas_log == ["rt_iv", "rt_logiv", "ct_rt"]


def test_fast_branch_source_does_not_drop_on_point():
    source = _RUNNER_PATH.read_text(encoding="utf-8")
    assert "on_point=None" not in source
    assert source.count("on_point=_on_point") >= 2
