"""4200 SMU sim + Oxxius sim through the real optical runner. No hardware."""

from __future__ import annotations

from Equipment.Laser_Controller.sim_link import get_laser_link
from Equipment.Laser_Controller.simulation_oxxius import SimulatedOxxius
from gui.pulse_testing_gui.optical_runner import _run_optical_4200
from Pulse_Testing.keithley4200_constants import (
    KEITHLEY4200_PMU_TIMING_SYSTEMS,
    KEITHLEY4200_SYSTEM_IDS,
)
from Pulse_Testing.systems.keithley4200_smu import Keithley4200SMUSimSystem


def _laser_off() -> None:
    link = get_laser_link()
    link.set_emitting(False)
    link.set_power_mw(0)


def test_smu_sim_is_registered_4200_adapter_not_pmu_timing():
    assert "keithley4200_smu_sim" in KEITHLEY4200_SYSTEM_IDS
    assert "keithley4200_smu_sim" not in KEITHLEY4200_PMU_TIMING_SYSTEMS


def test_optical_pulse_train_read_on_simulators():
    _laser_off()
    system = Keithley4200SMUSimSystem()
    laser = SimulatedOxxius(live_hiccups=False)
    try:
        assert system.connect("SIM::4200", live_hiccups=False, wall_sleep=True)
        # Default noise (~2e-7 A) is half the dark current, so a few samples
        # cannot show the 25% laser gain. Keep the device quiet for this check.
        system._scripts._get_controller().simulation.params.noise_current = 0.0
        laser.set_to_digital_power_control(1.0)
        result = _run_optical_4200(
            system,
            laser,
            "optical_pulse_train_read",
            {
                "duration_s": 0.30,
                "sample_interval_s": 0.05,
                "measurement_init_time_s": 0.0,
                "laser_delay_s": 0.08,
                "optical_on_ms": 100,
                "optical_off_ms": 50,
                "n_optical_pulses": 1,
                "read_voltage": 0.5,
                "clim": 1e-3,
                "optical_laser_power_mw": 1.0,
            },
        )
        timestamps = result["timestamps"]
        currents = result["currents"]
        intervals = result["laser_on_intervals"]
        assert timestamps
        assert len(currents) == len(timestamps)
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
        assert on_mean >= off_mean * 1.10
    finally:
        try:
            laser.close()
        except Exception:
            pass
        _laser_off()
