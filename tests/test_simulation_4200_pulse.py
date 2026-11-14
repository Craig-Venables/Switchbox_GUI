"""4200 SMU simulator: pulse EX, bias-timed read, laser gain. No hardware."""

from __future__ import annotations

import inspect
import math

import pytest

from Equipment.Laser_Controller.sim_link import get_laser_link
from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import Keithley4200_KXCI_Scripts
from Equipment.SMU_AND_PMU.keithley4200.simulation_4200 import (
    MemristorParameters,
    Simulation4200,
    Simulation4200Faults,
)
from Pulse_Testing.system_wrapper import (
    detect_system_from_address,
    get_default_address_for_system,
)
from Pulse_Testing.systems.keithley4200_smu import Keithley4200SMUSimSystem

_QUIET = dict(live_hiccups=False, wall_sleep=False)
_FROZEN = MemristorParameters(
    noise_current=0.0,
    relax_rate=0.0,
    set_rate=0.0,
    reset_rate=0.0,
)


def _measure_ex(voltage: float, width: float = 0.001) -> str:
    return (
        "EX Labview_Controlled_Programs_Kemp "
        f"SMU_pulse_measure(0,0,{width},{voltage},0.01,0.01,)"
    )


def _only_ex(voltage: float, width: float) -> str:
    return (
        "EX Labview_Controlled_Programs_Kemp "
        f"SMU_pulse_only(0,0,{width},{voltage},0.01,0.01,)"
    )


def _sim(**kwargs) -> Simulation4200:
    params = kwargs.pop("params", _FROZEN)
    return Simulation4200(params=params, seed=1, **_QUIET, **kwargs)


def test_detect_sim_4200_before_pyvisa_import():
    src = inspect.getsource(detect_system_from_address)
    assert src.find("SIM::4200") < src.find("import pyvisa")
    assert detect_system_from_address("SIM::4200") == "keithley4200_smu_sim"
    assert detect_system_from_address("  sim::4200::extra") == "keithley4200_smu_sim"
    assert detect_system_from_address("simulation_4200") == "keithley4200_smu_sim"
    assert get_default_address_for_system("keithley4200_smu_sim") == "SIM::4200"


def test_pulse_measure_returns_positive_ohms_and_scales_with_voltage():
    sim = _sim()
    r_pos, err = sim._execute_ex_command(_measure_ex(1.0))
    r_neg, err_neg = sim._execute_ex_command(_measure_ex(-2.0))
    assert err is None and err_neg is None
    assert r_pos > 0 and math.isfinite(r_pos)
    assert r_neg > 0 and math.isfinite(r_neg)
    i_pos = 1.0 / r_pos
    i_neg = -2.0 / r_neg
    assert i_pos > 0
    assert i_neg < 0
    assert abs(i_neg) == pytest.approx(2.0 * i_pos, rel=1e-6)


def test_pulse_only_returns_zero_and_set_lowers_resistance():
    params = MemristorParameters(noise_current=0.0, relax_rate=0.0)
    fresh = Simulation4200(params=params, seed=2, **_QUIET)
    r_fresh, err_fresh = fresh._execute_ex_command(_measure_ex(0.2))
    pulsed = Simulation4200(params=params, seed=2, **_QUIET)
    rc, err = pulsed._execute_ex_command(_only_ex(3.0, 0.2))
    r_set, err_set = pulsed._execute_ex_command(_measure_ex(0.2))
    assert err_fresh is None and err is None and err_set is None
    assert rc == 0
    assert r_fresh > 0 and r_set > 0
    assert r_set < r_fresh * 0.5


def test_unknown_ex_still_succeeds_without_data():
    sim = _sim()
    rc, err = sim._execute_ex_command("EX other_library other_command(1,2,)", wait_seconds=0.0)
    assert rc == 0 and err is None


def test_kxci_scripts_slow_pulse_on_sim_address():
    scripts = Keithley4200_KXCI_Scripts("SIM::4200", live_hiccups=False, wall_sleep=False)
    result = scripts.smu_slow_pulse_measure(
        pulse_voltage=1.0,
        pulse_width=0.001,
        enable_debug_output=False,
    )
    neg = scripts.smu_slow_pulse_measure(
        pulse_voltage=-1.0,
        pulse_width=0.001,
        initialize=False,
        enable_debug_output=False,
    )
    assert len(result["resistances"]) == 1
    resistance = result["resistances"][0]
    current = result["currents"][0]
    assert resistance > 0 and math.isfinite(resistance)
    assert current == pytest.approx(result["voltages"][0] / resistance, rel=1e-6)
    assert neg["currents"][0] < 0
    assert neg["currents"][0] == pytest.approx(neg["voltages"][0] / neg["resistances"][0], rel=1e-6)

    controller = scripts._get_controller()
    idn = controller.inst.query("*IDN?")
    assert "KEITHLEY" in idn and "4200A-SCS" in idn and "SIM" in idn
    assert controller.rm is None


def test_smu_endurance_one_cycle_two_reads():
    scripts = Keithley4200_KXCI_Scripts("SIM::4200", live_hiccups=False, wall_sleep=False)
    result = scripts.smu_endurance(
        num_cycles=1,
        set_duration=0.001,
        reset_duration=0.001,
        probe_duration=0.001,
        repeat_delay=0,
        enable_debug_output=False,
    )
    assert len(result["resistances"]) == 2
    assert all(r > 0 and math.isfinite(r) for r in result["resistances"])


def test_bias_timed_read_point_count():
    sim = _sim()
    data = sim.bias_timed_read(
        vforce=0.2,
        duration_s=1.0,
        sample_interval_s=0.1,
        ilimit=1e-3,
        num_points=7,
    )
    for key in ("timestamps", "voltages", "currents", "resistances"):
        assert key in data
    assert len(data["timestamps"]) == 7
    assert len(data["voltages"]) == len(data["currents"]) == len(data["resistances"]) == 7
    assert data["timestamps"][0] == 0.0
    assert data["timestamps"][1] == pytest.approx(0.1)

    inferred = sim.bias_timed_read(0.2, 0.5, 0.1, 1e-3)
    assert len(inferred["timestamps"]) == 5


def test_system_bias_timed_read_stays_on_sim():
    system = Keithley4200SMUSimSystem()
    assert system.connect("GPIB0::17::INSTR", live_hiccups=False, wall_sleep=False)
    assert str(system._address).upper().startswith("SIM")
    data = system.run_bias_timed_read(0.2, 0.5, 0.1, 1e-3, num_points=4)
    assert len(data["timestamps"]) == 4
    assert len(data["currents"]) == 4
    idn = system.get_idn()
    assert "SIM" in idn


def test_laser_emission_raises_current():
    link = get_laser_link()
    sim = _sim()
    sim.set_voltage(0.5, Icc=0.1)
    sim.enable_output(True)
    try:
        link.set_emitting(False, 0.0)
        off = abs(sim.measure_current())
        link.set_emitting(True, 1.0)
        on = abs(sim.measure_current())
        assert on >= off * 1.10
    finally:
        link.set_emitting(False)
        link.set_power_mw(0)


def test_pulse_ex_error_code_is_not_a_resistance():
    sim = _sim(faults=Simulation4200Faults(ex_error_code=-11))
    rc, err = sim._execute_ex_command(_measure_ex(1.0))
    assert rc == -11
    assert err is None
    assert not (isinstance(rc, (int, float)) and rc > 0 and math.isfinite(rc))


def test_pulse_honors_halt_and_disconnect_faults():
    halted = _sim(faults=Simulation4200Faults(halt=True))
    with pytest.raises(TimeoutError):
        halted._execute_ex_command(_measure_ex(1.0))

    dropped = _sim(faults=Simulation4200Faults(mid_sweep_disconnect=True))
    rc, err = dropped._execute_ex_command(_only_ex(1.0, 0.001))
    assert rc is None
    assert err is not None and "connection" in err.lower()
    assert not dropped._connected
