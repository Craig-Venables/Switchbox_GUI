"""Exact simulator numbers: laser gain, compliance, and one forced fault at a time.

Noise is zero. Hard faults stay off unless a test sets that one flag.
No GPIB, VISA, or serial.
"""

from __future__ import annotations

import math
import time

import pytest

from Equipment.Laser_Controller.sim_link import get_laser_link
from Equipment.Laser_Controller.simulation_oxxius import SimulatedOxxius
from Equipment.SMU_AND_PMU.keithley2450.tsp_sim_controller import (
    Keithley2450_TSP_Sim,
    Simulation2450Faults,
)
from Equipment.SMU_AND_PMU.keithley2450.tsp_sim_controller import (
    MemristorParameters as MemristorParameters2450,
)
from Equipment.SMU_AND_PMU.keithley4200.simulation_4200 import (
    GP_IMEAS,
    GP_VFORCE,
    Simulation4200,
    Simulation4200Faults,
)
from Equipment.SMU_AND_PMU.keithley4200.simulation_4200 import (
    MemristorParameters as MemristorParameters4200,
)

_LASER_GAINS = ((1.0, 1.25), (2.0, 1.50), (10.0, 2.25))
_READ_V = 0.5


def _frozen(cls, **overrides):
    values = dict(
        noise_current=0.0,
        relax_rate=0.0,
        set_rate=0.0,
        reset_rate=0.0,
    )
    values.update(overrides)
    return cls(**values)


def _sim4200(**kwargs) -> Simulation4200:
    params = kwargs.pop("params", _frozen(MemristorParameters4200))
    return Simulation4200(
        params=params,
        seed=0,
        live_hiccups=False,
        wall_sleep=False,
        **kwargs,
    )


def _sim2450(**kwargs) -> Keithley2450_TSP_Sim:
    params = kwargs.pop("params", _frozen(MemristorParameters2450))
    return Keithley2450_TSP_Sim(params=params, seed=0, **kwargs)


def _bias_on(sim, voltage: float, icc: float) -> None:
    sim.set_voltage(voltage, icc)
    sim.enable_output(True)


def _ex_cmd(
    vhigh: float = 2.0,
    vlow: float = -2.0,
    num_steps: int = 8,
    num_cycles: int = 1,
    step_delay: float = 0.001,
    ilimit: float = 1e-3,
) -> str:
    num_points = (num_steps + 1) * num_cycles
    params = [
        f"{vhigh}",
        f"{vlow}",
        f"{num_steps}",
        f"{num_cycles}",
        "",
        f"{num_points}",
        "",
        f"{num_points}",
        f"{step_delay}",
        f"{ilimit}",
        "0.0",
        "0.01",
        "0",
    ]
    return f"EX A_Iv_Sweep smu_ivsweep({','.join(params)})"


def _measure_ex(voltage: float, width: float = 0.001) -> str:
    return (
        "EX Labview_Controlled_Programs_Kemp "
        f"SMU_pulse_measure(0,0,{width},{voltage},0.01,0.01,)"
    )


def _reset_laser() -> None:
    get_laser_link().set_emitting(False, power_mw=0.0)


@pytest.fixture(autouse=True)
def _laser_link_off():
    _reset_laser()
    yield
    _reset_laser()


def _assert_laser_gains(read_current) -> None:
    link = get_laser_link()
    link.set_emitting(False, power_mw=0.0)
    off = read_current()
    assert off != 0.0
    for power_mw, ratio in _LASER_GAINS:
        link.set_emitting(True, power_mw=power_mw)
        on = read_current()
        assert on / off == pytest.approx(ratio, rel=1e-6)


def test_4200_laser_gain_exact_ratios():
    sim = _sim4200()
    _bias_on(sim, _READ_V, 1e-2)
    try:
        _assert_laser_gains(sim.measure_current)
    finally:
        _reset_laser()


def test_2450_laser_gain_exact_ratios():
    sim = _sim2450()
    _bias_on(sim, _READ_V, 1e-2)
    try:
        _assert_laser_gains(sim.measure_current)
    finally:
        _reset_laser()


def test_4200_pulse_ohms_match_measure_current():
    voltage = 0.5
    sim = _sim4200()
    try:
        _reset_laser()
        ohms, err = sim._execute_ex_command(_measure_ex(voltage))
        measured = sim.measure_current()
    finally:
        _reset_laser()
    assert err is None
    assert math.isfinite(ohms) and ohms > 0
    assert ohms == pytest.approx(abs(voltage / measured), rel=1e-6)
    assert voltage / ohms == pytest.approx(measured, rel=1e-9)


def test_4200_compliance_equals_1e_3():
    params = _frozen(MemristorParameters4200, ron=10.0, roff=20.0)
    sim = _sim4200(params=params)
    sim._state_w = 1.0
    _bias_on(sim, 5.0, 1e-3)
    sim._state_w = 1.0
    assert abs(sim.measure_current()) == pytest.approx(1e-3, abs=1e-12)


def test_2450_compliance_equals_limit_the_device_exceeds():
    # Default w=0.2, R ≈ 1.20003e6 ohm. At 1 V that is ~8.33e-7 A, under 1e-4 A,
    # so the limit is set to 1e-7 A, which this device does exceed.
    voltage = 1.0
    limit = 1e-7
    sim = _sim2450()
    _bias_on(sim, voltage, limit)
    assert abs(voltage * sim._conductance()) > limit
    assert abs(sim.measure_current()) == pytest.approx(limit, abs=1e-12)


def test_4200_ex_error_code_is_not_a_resistance():
    sim = _sim4200(faults=Simulation4200Faults(ex_error_code=-7))
    rc, err = sim._execute_ex_command(_ex_cmd(), wait_seconds=0.0)
    assert rc == -7
    assert err is None
    assert not (isinstance(rc, (int, float)) and rc > 0)
    assert sim._query_gp(GP_VFORCE, 9) == [0.0] * 9


def test_4200_halt_raises_timeout():
    sim = _sim4200(faults=Simulation4200Faults(halt=True))
    with pytest.raises(TimeoutError):
        sim._execute_ex_command(_ex_cmd(), wait_seconds=0.0)


def test_4200_truncate_gp_returns_three_points():
    sim = _sim4200(faults=Simulation4200Faults(truncate_gp_points=3))
    rc, err = sim._execute_ex_command(_ex_cmd(num_steps=8), wait_seconds=0.0)
    assert rc == 0 and err is None
    assert len(sim._query_gp(GP_VFORCE, 9)) == 3
    assert len(sim._query_gp(GP_IMEAS, 9)) == 3


def test_4200_pause_takes_at_least_40ms():
    sim = _sim4200(faults=Simulation4200Faults(pause_s=0.05))
    t0 = time.perf_counter()
    rc, err = sim._execute_ex_command(_ex_cmd(num_steps=4), wait_seconds=0.0)
    elapsed = time.perf_counter() - t0
    assert rc == 0 and err is None
    assert elapsed >= 0.04


def test_4200_drop_gp_raises():
    sim = _sim4200(faults=Simulation4200Faults(drop_gp=True))
    rc, err = sim._execute_ex_command(_ex_cmd(num_steps=4), wait_seconds=0.0)
    assert rc == 0 and err is None
    with pytest.raises(RuntimeError):
        sim._query_gp(GP_IMEAS, 5)


def test_4200_mid_sweep_disconnect_returns_error_string():
    sim = _sim4200(faults=Simulation4200Faults(mid_sweep_disconnect=True))
    rc, err = sim._execute_ex_command(_ex_cmd(num_steps=8), wait_seconds=0.0)
    assert rc is None
    assert isinstance(err, str) and err
    assert sim._connected is False


def test_4200_bias_timed_read_stale_and_glitch_are_exact():
    sim = _sim4200(
        faults=Simulation4200Faults(
            force_stale_sample=True,
            glitch_index=0,
            glitch_current_a=1.5e-6,
        )
    )
    data = sim.bias_timed_read(
        vforce=0.2,
        duration_s=0.4,
        sample_interval_s=0.1,
        ilimit=1e-3,
        num_points=4,
    )
    currents = data["currents"]
    assert len(currents) == 4
    assert currents[0] == pytest.approx(1.5e-6, abs=1e-12)
    assert currents[1] == currents[2] == currents[3] == pytest.approx(1.5e-6, abs=1e-12)


def test_2450_halt_raises_timeout():
    sim = _sim2450(halt=True)
    with pytest.raises(TimeoutError):
        sim.measure_current()


def test_2450_pause_takes_at_least_40ms():
    sim = _sim2450(pause_s=0.05)
    t0 = time.perf_counter()
    sim.measure_current()
    assert time.perf_counter() - t0 >= 0.04


def test_2450_force_stale_sample_ignores_new_voltage():
    sim = _sim2450(faults=Simulation2450Faults(force_stale_sample=True))
    _bias_on(sim, 0.5, 0.1)
    first = sim.measure_current()
    sim.set_voltage(2.0, Icc=0.1)
    assert sim._source_level == pytest.approx(2.0)
    second = sim.measure_current()
    assert second == pytest.approx(first, rel=1e-6)
    assert abs(second) < abs(first) * 2


def test_laser_late_on_pulse_then_off():
    link = get_laser_link()
    laser = SimulatedOxxius(live_hiccups=False, late_on_s=0.02)
    try:
        t0 = time.perf_counter()
        laser.pulse_on_ms(30)
        elapsed = time.perf_counter() - t0
        assert elapsed >= 0.050
        assert link.snapshot()[0] is False
    finally:
        _reset_laser()
        laser.close()


def test_laser_fail_emission_stays_off():
    link = get_laser_link()
    laser = SimulatedOxxius(live_hiccups=False, fail_emission=True)
    try:
        with pytest.raises(RuntimeError):
            laser.emission_on()
        assert link.snapshot()[0] is False
        with pytest.raises(RuntimeError):
            laser.pulse_on_ms(30)
        assert link.snapshot()[0] is False
    finally:
        _reset_laser()
        laser.close()
