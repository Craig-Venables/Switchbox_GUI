"""Laser-port binding and short 4200 SMU + Oxxius optical runs. Simulator only."""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

from Equipment.Laser_Controller.sim_link import get_laser_link
from Equipment.Laser_Controller.simulation_oxxius import SimulatedOxxius
from gui.pulse_testing_gui.optical_runner import (
    _run_optical_4200,
    run_binary_sweep_test,
    run_pattern_repeat_test,
)
from gui.pulse_testing_gui.ui import laser_section
from gui.pulse_testing_gui.ui.tabs_optical import build_optical_tab
from Pulse_Testing.system_wrapper import SystemWrapper
from Pulse_Testing.systems.keithley4200_smu import Keithley4200SMUSimSystem

_DURATION_S = 0.25
_SAMPLE_S = 0.05


def _laser_off() -> None:
    link = get_laser_link()
    link.set_emitting(False)
    link.set_power_mw(0)


def _port_entry(frame: tk.Widget) -> tk.Entry:
    """First Entry after the Port label inside Laser Control."""
    for child in frame.winfo_children():
        if isinstance(child, tk.Label) and child.cget("text") == "Port:":
            kids = child.master.winfo_children()
            for widget in kids[kids.index(child) + 1 :]:
                if isinstance(widget, tk.Entry):
                    return widget
        found = _port_entry(child)
        if found is not None:
            return found
    return None


def _optical_params() -> dict:
    return {
        "duration_s": _DURATION_S,
        "total_time_s": _DURATION_S,
        "sample_interval_s": _SAMPLE_S,
        "measurement_init_time_s": 0.0,
        # Fire at t=0 so the 0.00/0.05 s samples sit inside the pulse and
        # 0.15/0.20 s stay dark, with margin for sleep() jitter.
        "laser_delay_s": 0.0,
        "read_voltage": 0.5,
        "clim": 1e-3,
        "optical_laser_power_mw": 1.0,
        "optical_on_ms": 120,
        "optical_off_ms": 50,
        "optical_pulse_duration_s": 0.12,
        "optical_pulse_period_s": 1.0,
        "n_optical_pulses": 1,
        "laser_pattern": "1010",
        "pattern_repeats": 1,
        "time_between_patterns_s": 0.0,
        "num_bits": 1,
        "n_repeats": 2,
        "delay_between_runs_s": 0.0,
    }


def _assert_optical(result: dict, *, label: str, expect_laser: bool) -> None:
    timestamps = result["timestamps"]
    currents = result["currents"]
    resistances = result["resistances"]
    intervals = result.get("laser_on_intervals") or []
    assert timestamps, f"{label}: empty timestamps"
    assert len(currents) == len(timestamps), label
    assert len(resistances) == len(timestamps), label
    if not expect_laser:
        return
    assert len(intervals) >= 1, f"{label}: expected a laser-on interval, got {intervals}"

    def _inside(t: float) -> bool:
        return any(start <= t <= end for start, end in intervals)

    on_abs = [abs(i) for t, i in zip(timestamps, currents) if _inside(t)]
    off_abs = [abs(i) for t, i in zip(timestamps, currents) if not _inside(t)]
    assert on_abs, f"{label}: no sample inside {intervals} timestamps={timestamps}"
    assert off_abs, f"{label}: no sample outside {intervals} timestamps={timestamps}"
    on_mean = sum(on_abs) / len(on_abs)
    off_mean = sum(off_abs) / len(off_abs)
    assert off_mean > 0.0, label
    assert on_mean >= off_mean * 1.10, (
        f"{label}: on {on_mean} vs off {off_mean} intervals={intervals} t={timestamps}"
    )


class _Gui:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, message) -> None:
        self.messages.append(str(message))


def test_laser_control_port_survives_optical_tab():
    """Optical tab must not replace the StringVar the Laser Control Port entry uses."""
    root = tk.Tk()
    root.withdraw()
    gui = _Gui()
    try:
        parent = tk.Frame(root)
        laser_section.build_laser_section(parent, gui)
        port_var = gui.laser_port_var
        baud_var = gui.laser_baud_var
        port_entry = _port_entry(gui.laser_section_frame)
        assert port_entry is not None
        optical = tk.Frame(root)
        build_optical_tab(optical, gui)

        assert gui.laser_port_var is port_var
        assert gui.laser_baud_var is baud_var
        assert port_entry.cget("textvariable") == str(gui.laser_port_var)

        port_entry.delete(0, tk.END)
        port_entry.insert(0, "SIM")
        calls = {"n": 0}

        def _refuse_serial(*_args, **_kwargs):
            calls["n"] += 1
            raise AssertionError("serial.Serial must not be constructed")

        with patch("serial.Serial", side_effect=_refuse_serial):
            laser_section._connect_laser(gui)

        assert calls["n"] == 0
        assert isinstance(gui.laser, SimulatedOxxius)
    finally:
        root.destroy()
        _laser_off()


def test_optical_sim_stress_and_save(tmp_path):
    """Short real optical runners, then the pulse-GUI save path into tmp_path."""
    _laser_off()
    system = Keithley4200SMUSimSystem()
    laser = SimulatedOxxius(live_hiccups=False)
    try:
        assert system.connect("SIM::4200", live_hiccups=False, wall_sleep=True)
        system._scripts._get_controller().simulation.params.noise_current = 0.0
        laser.set_to_digital_power_control(1.0)
        params = _optical_params()

        for func_name in (
            "optical_read_pulsed_light",
            "optical_pulse_train_read",
            "optical_pulse_train_pattern_read",
        ):
            result = _run_optical_4200(system, laser, func_name, dict(params))
            _assert_optical(result, label=func_name, expect_laser=True)
            if func_name == "optical_pulse_train_pattern_read":
                saved_result = result

        wrapper = SystemWrapper()
        wrapper.current_system = system
        wrapper.system_name = "keithley4200_smu_sim"
        gui = SimpleNamespace(laser=laser, system_wrapper=wrapper)

        binary = run_binary_sweep_test(
            gui, dict(params), lambda _msg: None, lambda *_a: None
        )
        assert len(binary) == 2
        for run in binary:
            pattern = run.get("laser_pattern", "")
            _assert_optical(
                run,
                label=f"binary {pattern}",
                expect_laser=("1" in pattern),
            )

        repeats = run_pattern_repeat_test(
            gui, dict(params), lambda _msg: None, lambda *_a: None
        )
        assert len(repeats) == 2
        for run in repeats:
            _assert_optical(run, label=f"repeat {run.get('run_index')}", expect_laser=True)

        _save_and_reload(saved_result, params, tmp_path)
    finally:
        try:
            laser.close()
        except Exception:
            pass
        try:
            system.disconnect()
        except Exception:
            pass
        _laser_off()


class _Get:
    def __init__(self, value):
        self._value = value

    def get(self, *_args, **_kwargs):
        return self._value


def _save_and_reload(result: dict, params: dict, tmp_path) -> None:
    """Call TSPTestingGUI.save_data in simple-save mode and read the txt back."""
    from gui.pulse_testing_gui.main import TSPTestingGUI

    payload = dict(result)
    payload["test_name"] = "Optical Pattern Read"
    payload["params"] = dict(params)
    payload["plot_type"] = "optical"
    gui = SimpleNamespace(
        last_results=payload,
        provider=None,
        use_simple_save_var=_Get(True),
        simple_save_path=tmp_path,
        device_label="A1",
        sample_name="OpticalSim",
        filename_suffix_var=_Get(""),
        notes_text=_Get(""),
        system_wrapper=SimpleNamespace(is_connected=lambda: False),
        current_system_name="keithley4200_smu_sim",
        addr_var=_Get("SIM::4200"),
        custom_base_path=tmp_path,
        log=lambda *_a, **_k: None,
    )
    gui._generate_test_details = lambda p: TSPTestingGUI._generate_test_details(gui, p)
    assert TSPTestingGUI.save_data(gui, show_dialog=False) is True

    files = [p for p in tmp_path.glob("*.txt") if p.name != "tsp_test_log.txt"]
    assert len(files) == 1, files
    text = files[0].read_text(encoding="utf-8")
    assert "Current(A)" in text
    assert "Laser On Intervals" in text

    header = None
    currents = []
    timestamps = []
    resistances = []
    for line in text.splitlines():
        if line.startswith("#") and "Current(A)" in line and "Timestamp(s)" in line:
            header = [part.strip() for part in line[1:].split("\t")]
            continue
        if line.startswith("#") or not line.strip() or header is None:
            continue
        cols = line.split("\t")
        row = dict(zip(header, cols))
        timestamps.append(float(row["Timestamp(s)"]))
        currents.append(float(row["Current(A)"]))
        resistances.append(float(row["Resistance(Ohm)"]))

    assert len(currents) == len(result["currents"])
    for got, exp in zip(timestamps, result["timestamps"]):
        assert abs(got - exp) <= 1e-5
    for got, exp in zip(currents, result["currents"]):
        assert abs(got - exp) <= max(1e-12, abs(exp) * 1e-5)
    for got, exp in zip(resistances, result["resistances"]):
        assert abs(got - exp) <= max(1e-6, abs(exp) * 1e-5)

    loaded_intervals = []
    in_intervals = False
    for line in text.splitlines():
        if line.startswith("# Laser On Intervals"):
            in_intervals = True
            continue
        if in_intervals:
            if not line.startswith("#"):
                break
            body = line[1:].strip()
            if not body:
                break
            start_s, end_s = body.split()
            loaded_intervals.append((float(start_s), float(end_s)))
    expected = [(float(a), float(b)) for a, b in result["laser_on_intervals"]]
    assert len(loaded_intervals) == len(expected)
    for got, exp in zip(loaded_intervals, expected):
        assert abs(got[0] - exp[0]) <= 1e-5
        assert abs(got[1] - exp[1]) <= 1e-5
