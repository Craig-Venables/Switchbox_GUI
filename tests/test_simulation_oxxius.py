"""Simulated Oxxius: no serial port, shared laser-link emission state."""

from __future__ import annotations

import time

import pytest

from Equipment.Laser_Controller.sim_link import get_laser_link
from Equipment.Laser_Controller.simulation_oxxius import (
    SimulatedOxxius,
    is_simulation_port,
)


@pytest.fixture(autouse=True)
def _reset_laser_link():
    link = get_laser_link()
    link.set_emitting(False, power_mw=0.0)
    yield
    link.set_emitting(False, power_mw=0.0)


def test_construct_does_not_need_a_com_port(monkeypatch):
    try:
        import serial
    except ImportError:
        serial = None
    if serial is not None:

        def _boom(*_args, **_kwargs):
            raise AssertionError("serial.Serial must not be constructed")

        monkeypatch.setattr(serial, "Serial", _boom)

    laser = SimulatedOxxius(port="SIM", live_hiccups=False)
    assert laser.live_hiccups is False
    text = laser.idn()
    assert "Oxxius" in text
    assert "SIM" in text
    laser.close()


def test_emission_updates_shared_link():
    laser = SimulatedOxxius(safe_power_mw=10, live_hiccups=False)
    laser.emission_on()
    emitting, power = get_laser_link().snapshot()
    assert emitting is True
    assert power == pytest.approx(10.0)

    laser.emission_off()
    emitting, power = get_laser_link().snapshot()
    assert emitting is False
    assert power == pytest.approx(10.0)
    laser.close()


def test_digital_power_control_stores_setpoint_and_stays_off():
    laser = SimulatedOxxius(safe_power_mw=10, live_hiccups=False)
    laser.emission_on()
    result = laser.set_to_digital_power_control(2.5)
    assert "power" in result
    emitting, power = get_laser_link().snapshot()
    assert emitting is False
    assert power == pytest.approx(2.5)
    assert laser.power_mw == pytest.approx(2.5)
    laser.close()


def test_pulse_on_ms_is_on_during_pulse_and_off_after():
    laser = SimulatedOxxius(safe_power_mw=4.0, live_hiccups=False)
    assert laser.live_hiccups is False
    seen: list[bool] = []
    original = laser.emission_on

    def _emission_on() -> str:
        reply = original()
        seen.append(get_laser_link().snapshot()[0])
        return reply

    laser.emission_on = _emission_on  # type: ignore[method-assign]
    t0 = time.perf_counter()
    laser.pulse_on_ms(30)
    elapsed = time.perf_counter() - t0

    assert seen == [True]
    assert elapsed >= 0.025
    emitting, power = get_laser_link().snapshot()
    assert emitting is False
    assert power == pytest.approx(4.0)
    laser.close()


def test_close_then_emission_on_raises():
    laser = SimulatedOxxius(live_hiccups=False)
    laser.close()
    with pytest.raises(RuntimeError):
        laser.emission_on()


@pytest.mark.parametrize(
    "port",
    ["SIM", "sim", " SIMULATION ", "sim::laser", "Sim::Laser"],
)
def test_simulation_port_names(port):
    assert is_simulation_port(port)


@pytest.mark.parametrize("port", ["COM3", "SIM::GPIB0::17::INSTR", "", "SIMULATION2"])
def test_other_ports_are_not_the_laser_simulator(port):
    assert not is_simulation_port(port)
