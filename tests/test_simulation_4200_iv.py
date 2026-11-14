"""Fast tests for Keithley 4200A IV simulation (smu_ivsweep EX / GP path)."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

_SIM_PATH = (
    Path(__file__).resolve().parents[1]
    / "Equipment"
    / "SMU_AND_PMU"
    / "keithley4200"
    / "simulation_4200.py"
)
_spec = importlib.util.spec_from_file_location("simulation_4200_iv_under_test", _SIM_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["simulation_4200_iv_under_test"] = _mod
_spec.loader.exec_module(_mod)

GP_IMEAS = _mod.GP_IMEAS
GP_VFORCE = _mod.GP_VFORCE
MemristorParameters = _mod.MemristorParameters
Simulation4200 = _mod.Simulation4200
Simulation4200Faults = _mod.Simulation4200Faults
build_iv_sweep_voltages = _mod.build_iv_sweep_voltages


def _ex_cmd(
    vhigh: float = 2.0,
    vlow: float = -2.0,
    num_steps: int = 8,
    num_cycles: int = 1,
    step_delay: float = 0.001,
    ilimit: float = 1e-3,
    irange: float = 0.0,
    integration_time: float = 0.01,
    clarius_debug: int = 0,
) -> str:
    """Build EX string matching run_smu_vi_sweep.build_ex_command."""
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
        f"{irange}",
        f"{integration_time}",
        f"{clarius_debug}",
    ]
    return f"EX A_Iv_Sweep smu_ivsweep({','.join(params)})"


def test_build_iv_sweep_voltages_point_count():
    for num_steps in (4, 5, 8, 20):
        vs = build_iv_sweep_voltages(2.0, -2.0, num_steps)
        assert len(vs) == num_steps + 1
        assert vs[0] == pytest.approx(0.0)
        assert vs[-1] == pytest.approx(0.0)
        assert max(vs) == pytest.approx(2.0)
        assert min(vs) == pytest.approx(-2.0)


def test_smu_ivsweep_gp_slots_and_point_count():
    sim = Simulation4200(seed=1, params=MemristorParameters(noise_current=0.0))
    num_steps, num_cycles = 8, 2
    expected = (num_steps + 1) * num_cycles
    cmd = _ex_cmd(num_steps=num_steps, num_cycles=num_cycles, ilimit=0.1)
    rc, err = sim._execute_ex_command(cmd, wait_seconds=0.0)
    assert err is None
    assert rc == 0

    vforce = sim._query_gp(GP_VFORCE, expected)
    imeas = sim._query_gp(GP_IMEAS, expected)
    assert len(vforce) == expected
    assert len(imeas) == expected
    assert vforce[0] == pytest.approx(0.0)
    assert max(vforce) == pytest.approx(2.0)
    assert min(vforce) == pytest.approx(-2.0)


def test_compliance_clipping_at_ilimit():
    # Low RON so current would exceed ilimit without clipping
    params = MemristorParameters(ron=10.0, roff=20.0, noise_current=0.0, set_rate=0.0, reset_rate=0.0)
    sim = Simulation4200(seed=2, params=params)
    sim._state_w = 1.0  # fully LRS
    ilimit = 1e-3
    cmd = _ex_cmd(vhigh=5.0, vlow=-5.0, num_steps=8, ilimit=ilimit)
    rc, err = sim._execute_ex_command(cmd, wait_seconds=0.0)
    assert rc == 0 and err is None
    imeas = sim._query_gp(GP_IMEAS, 9)
    assert max(abs(i) for i in imeas) <= ilimit + 1e-12


def test_hysteresis_across_cycle():
    params = MemristorParameters(
        ron=1e3,
        roff=1e6,
        set_threshold=0.5,
        reset_threshold=0.5,
        set_rate=50.0,
        reset_rate=50.0,
        relax_rate=0.0,
        noise_current=0.0,
    )
    sim = Simulation4200(seed=3, params=params)
    sim._state_w = 0.2
    cmd = _ex_cmd(vhigh=2.0, vlow=-2.0, num_steps=8, step_delay=0.01, ilimit=0.1)
    rc, err = sim._execute_ex_command(cmd, wait_seconds=0.0)
    assert rc == 0 and err is None

    vforce = sim._query_gp(GP_VFORCE, 9)
    imeas = sim._query_gp(GP_IMEAS, 9)

    # Find rising and falling samples near ~1 V
    rising_i = None
    falling_i = None
    saw_peak = False
    for v, i in zip(vforce, imeas):
        if v >= 1.9:
            saw_peak = True
        if abs(v - 1.0) < 0.35:
            if not saw_peak and rising_i is None:
                rising_i = i
            elif saw_peak and falling_i is None:
                falling_i = i
    assert rising_i is not None and falling_i is not None
    # After SET at Vhigh, falling branch should be more conductive (|I| larger at same V)
    assert abs(falling_i) > abs(rising_i)


def test_validation_error_codes():
    sim = Simulation4200(seed=4)
    # Wrong array size vs (NumSteps+1)×NumCycles → -3
    params = ["2.0", "-2.0", "8", "1", "", "5", "", "5", "0.001", "0.001", "0.0", "0.01", "0"]
    rc, err = sim._execute_ex_command(f"EX A_Iv_Sweep smu_ivsweep({','.join(params)})", wait_seconds=0.0)
    assert err is None
    assert rc == -3

    # Invalid Vhigh (< 0) → -1
    params2 = ["-1.0", "-2.0", "8", "1", "", "9", "", "9", "0.001", "0.001", "0.0", "0.01", "0"]
    rc2, _ = sim._execute_ex_command(f"EX A_Iv_Sweep smu_ivsweep({','.join(params2)})", wait_seconds=0.0)
    assert rc2 == -1

    # NumSteps out of range → -5
    params3 = ["2.0", "-2.0", "2", "1", "", "3", "", "3", "0.001", "0.001", "0.0", "0.01", "0"]
    rc3, _ = sim._execute_ex_command(f"EX A_Iv_Sweep smu_ivsweep({','.join(params3)})", wait_seconds=0.0)
    assert rc3 == -5


def test_fault_halt_raises_timeout():
    sim = Simulation4200(faults=Simulation4200Faults(halt=True))
    with pytest.raises(TimeoutError):
        sim._execute_ex_command(_ex_cmd(), wait_seconds=0.0)


def test_fault_pause_injects_delay():
    sim = Simulation4200(faults=Simulation4200Faults(pause_s=0.05))
    t0 = time.perf_counter()
    rc, err = sim._execute_ex_command(_ex_cmd(num_steps=4), wait_seconds=0.0)
    elapsed = time.perf_counter() - t0
    assert rc == 0 and err is None
    assert elapsed >= 0.04


def test_fault_ex_error_code():
    sim = Simulation4200(faults=Simulation4200Faults(ex_error_code=-7))
    rc, err = sim._execute_ex_command(_ex_cmd(), wait_seconds=0.0)
    assert rc == -7
    assert err is None
    # No GP data written on injected error
    assert sim._query_gp(GP_VFORCE, 9) == [0.0] * 9


def test_fault_drop_gp():
    sim = Simulation4200(faults=Simulation4200Faults(drop_gp=True))
    rc, err = sim._execute_ex_command(_ex_cmd(num_steps=4), wait_seconds=0.0)
    assert rc == 0 and err is None
    with pytest.raises(RuntimeError, match="-980"):
        sim._query_gp(GP_IMEAS, 5)


def test_fault_truncated_gp():
    sim = Simulation4200(faults=Simulation4200Faults(truncate_gp_points=3))
    num_steps = 8
    expected = num_steps + 1
    rc, err = sim._execute_ex_command(_ex_cmd(num_steps=num_steps), wait_seconds=0.0)
    assert rc == 0 and err is None
    vforce = sim._query_gp(GP_VFORCE, expected)
    imeas = sim._query_gp(GP_IMEAS, expected)
    assert len(vforce) == 3
    assert len(imeas) == 3


def test_fault_mid_sweep_disconnect():
    sim = Simulation4200(faults=Simulation4200Faults(mid_sweep_disconnect=True))
    rc, err = sim._execute_ex_command(_ex_cmd(num_steps=8), wait_seconds=0.0)
    assert rc is None
    assert err is not None
    assert "disconnect" in err.lower()
    assert not sim._connected


def test_legacy_gp_aliases_populated():
    """Single-point wrapper historically queried GP 4/6; keep aliases filled."""
    sim = Simulation4200(seed=5, params=MemristorParameters(noise_current=0.0))
    rc, err = sim._execute_ex_command(_ex_cmd(num_steps=4), wait_seconds=0.0)
    assert rc == 0 and err is None
    assert sim._query_gp(4, 5) == sim._query_gp(GP_IMEAS, 5)
    assert sim._query_gp(6, 5) == sim._query_gp(GP_VFORCE, 5)
