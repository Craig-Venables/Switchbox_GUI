"""2450 SMU sim + Oxxius sim through the real optical runner. No hardware."""

from __future__ import annotations

from Equipment.Laser_Controller.sim_link import get_laser_link
from Equipment.Laser_Controller.simulation_oxxius import SimulatedOxxius
from gui.pulse_testing_gui.optical_runner import (
    _run_optical_pulse_train_read,
    _run_optical_read_pulsed_light,
)
from Pulse_Testing.system_wrapper import (
    SystemWrapper,
    detect_system_from_address,
    get_default_address_for_system,
)
from Pulse_Testing.systems.keithley2450 import Keithley2450SimSystem


def _laser_off() -> None:
    link = get_laser_link()
    link.set_emitting(False)
    link.set_power_mw(0)


def _on_off_means(result: dict) -> tuple[float, float]:
    timestamps = result["timestamps"]
    currents = result["currents"]
    intervals = result["laser_on_intervals"]
    assert timestamps
    assert len(currents) == len(timestamps)
    assert len(result["voltages"]) == len(timestamps)
    assert len(result["resistances"]) == len(timestamps)
    assert len(intervals) >= 1

    def _inside(t: float) -> bool:
        return any(start <= t <= end for start, end in intervals)

    on_abs = [abs(i) for t, i in zip(timestamps, currents) if _inside(t)]
    off_abs = [abs(i) for t, i in zip(timestamps, currents) if not _inside(t)]
    assert on_abs, f"no sample inside {intervals} timestamps={timestamps}"
    assert off_abs, f"no sample outside {intervals} timestamps={timestamps}"
    on_mean = sum(on_abs) / len(on_abs)
    off_mean = sum(off_abs) / len(off_abs)
    assert off_mean > 0.0
    assert on_mean >= off_mean * 1.10, f"on/off ratio {on_mean / off_mean:.4f}"
    return on_mean, off_mean


def test_detect_2450_sim_address_without_pyvisa():
    assert detect_system_from_address("SIM::KEITHLEY2450") == "keithley2450_sim"
    assert get_default_address_for_system("keithley2450_sim") == "SIM::KEITHLEY2450"
    wrapper = SystemWrapper()
    try:
        assert wrapper.connect("SIM::KEITHLEY2450", terminals="rear") == "keithley2450_sim"
        assert wrapper.current_system.tsp_controller.terminals == "rear"
    finally:
        wrapper.disconnect()


def test_sim_current_rises_while_laser_emits():
    _laser_off()
    system = Keithley2450SimSystem()
    try:
        assert system.connect("SIM::KEITHLEY2450")
        system.tsp_controller.params.noise_current = 0.0
        system.source_voltage_for_optical(0.5, 1e-3)
        _off_t, off_i = system.measure_current_once()
        get_laser_link().set_emitting(True, power_mw=1.0)
        _on_t, on_i = system.measure_current_once()
        assert abs(off_i) > 0.0
        assert abs(on_i) >= abs(off_i) * 1.10
    finally:
        try:
            system.source_output_off()
        except Exception:
            pass
        _laser_off()


def test_optical_pulse_train_read_samples_during_laser():
    _laser_off()
    system = Keithley2450SimSystem()
    laser = SimulatedOxxius(live_hiccups=False)
    try:
        assert system.connect("SIM::KEITHLEY2450")
        # Default noise (~2e-7 A) hides the 25% laser gain on a short run.
        system.tsp_controller.params.noise_current = 0.0
        laser.set_to_digital_power_control(1.0)
        result = _run_optical_pulse_train_read(
            system,
            laser,
            {
                "duration_s": 0.30,
                "sample_interval_s": 0.05,
                "optical_on_ms": 100,
                "optical_off_ms": 40,
                "n_optical_pulses": 1,
                "laser_delay_s": 0.08,
                "read_voltage": 0.5,
                "clim": 1e-3,
            },
        )
        _on_off_means(result)
    finally:
        try:
            laser.close()
        except Exception:
            pass
        _laser_off()


def test_optical_read_pulsed_light_samples_during_laser():
    _laser_off()
    system = Keithley2450SimSystem()
    laser = SimulatedOxxius(live_hiccups=False)
    try:
        assert system.connect("SIM::KEITHLEY2450")
        system.tsp_controller.params.noise_current = 0.0
        laser.set_to_digital_power_control(1.0)
        result = _run_optical_read_pulsed_light(
            system,
            laser,
            {
                "total_time_s": 0.30,
                "sample_interval_s": 0.05,
                "optical_pulse_duration_s": 0.10,
                "optical_pulse_period_s": 0.25,
                "laser_delay_s": 0.05,
                "read_voltage": 0.5,
                "clim": 1e-3,
            },
        )
        _on_off_means(result)
    finally:
        try:
            laser.close()
        except Exception:
            pass
        _laser_off()
