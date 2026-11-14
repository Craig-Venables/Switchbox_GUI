"""Registry consistency + dry-run of every pulse test on every system (no hardware).

The dry run calls each real system adapter (2450, 2400/2401, 4200 PMU, 4200 SMU) with the
GUI's default parameters, but swaps the instrument script object for a recorder that binds
the call against the real script method's signature. A parameter the script does not
accept fails here exactly as it would with ``TypeError`` on the bench.

Run:  py -m pytest Pulse_Testing/tests/test_registry.py -v
"""

import inspect
import os
import sys
from unittest.mock import MagicMock

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Instrument libraries are not needed for a dry run; stub them if this machine lacks them.
for _name in (
    "pymeasure", "pymeasure.instruments", "pymeasure.instruments.keithley",
    "pyvisa", "pyvisa.constants", "pyvisa.errors",
    "serial", "serial.tools", "serial.tools.list_ports",
):
    try:
        __import__(_name)
    except Exception:
        sys.modules[_name] = MagicMock()

from Pulse_Testing import test_registry as R  # noqa: E402
from Pulse_Testing.pmu_channel_wiring import PMU_INTERLEAVED_DUT_2CH  # noqa: E402
from Pulse_Testing.system_wrapper import SYSTEM_CLASSES  # noqa: E402
from Pulse_Testing.test_capabilities import is_test_supported  # noqa: E402
from Pulse_Testing.test_definitions import TEST_FUNCTIONS, get_test_definitions_for_gui  # noqa: E402
from Equipment.SMU_AND_PMU.keithley2400.scpi_scripts import Keithley2400_SCPI_Scripts  # noqa: E402
from Equipment.SMU_AND_PMU.keithley2450.tsp_scripts import Keithley2450_TSP_Scripts  # noqa: E402
from Equipment.SMU_AND_PMU.keithley4200.kxci_scripts import Keithley4200_KXCI_Scripts  # noqa: E402
from Equipment.SMU_AND_PMU.keithley2450.tsp_sim_scripts import Keithley2450_TSP_Sim_Scripts  # noqa: E402
from Pulse_Testing.systems.keithley2450 import Keithley2450SimSystem  # noqa: E402

# The GUI builds the simulator adapter itself; SystemWrapper only knows real instruments.
ADAPTER_CLASSES = dict(SYSTEM_CLASSES, keithley2450_sim=Keithley2450SimSystem)

PLOT_TYPES = {
    "time_series", "range_finder", "width_vs_resistance", "pot_dep_cycle", "endurance",
    "retention", "log_retention", "volatile_screening", "relaxation_reads", "relaxation_all",
    "relaxation", "voltage_sweep", "ispp", "threshold", "multilevel", "pulse_train",
}

# system id -> (script class, attribute the adapter keeps it in)
SCRIPT_SLOTS = {
    "keithley2450": (Keithley2450_TSP_Scripts, "test_scripts"),
    "keithley2450_sim": (Keithley2450_TSP_Sim_Scripts, "test_scripts"),
    "keithley2400": (Keithley2400_SCPI_Scripts, "test_scripts"),
    "keithley4200_pmu": (Keithley4200_KXCI_Scripts, "_scripts"),
    "keithley4200a": (Keithley4200_KXCI_Scripts, "_scripts"),
    "keithley4200_smu": (Keithley4200_KXCI_Scripts, "_scripts"),
    "keithley4200_smu_sim": (Keithley4200_KXCI_Scripts, "_scripts"),
}

_FAKE_RESULT = {"timestamps": [0.0], "voltages": [0.2], "currents": [1e-6], "resistances": [2e5]}


class _ScriptRecorder:
    """Stands in for the instrument script object; validates each call's kwargs.

    Kwargs that only land in a ``**kwargs`` catch-all are recorded as ignored: the
    script would run, but the user's setting would silently have no effect.
    """

    def __init__(self, script_cls):
        self._cls = script_cls
        self.calls = []
        self.ignored = []

    def __getattr__(self, name):
        target = getattr(self._cls, name, None)
        if target is None or not callable(target):
            return MagicMock()

        def _call(*args, **kwargs):
            sig = inspect.signature(target)
            sig.bind(None, *args, **kwargs)
            named = {n for n, p in sig.parameters.items() if p.kind != p.VAR_KEYWORD}
            self.ignored.extend(f"{name}({k})" for k in kwargs if k not in named)
            self.calls.append(name)
            return dict(_FAKE_RESULT)

        return _call


def _gui_value(info):
    value = info["default"]
    if info["type"] == "list" and isinstance(value, str):
        return [float(x) for x in value.split(",") if x.strip()]
    return value


def _gui_params(spec, system):
    """Parameters the pulse GUI would send for this test on this system (defaults)."""
    params = dict(TEST_FUNCTIONS[spec.display_name]["params"])
    extra = ["i_range"] if spec.function in PMU_INTERLEAVED_DUT_2CH else []
    names = R.instrument_params_for(spec, system, extra)
    return {n: _gui_value(params[n]) for n in names}


def _cases():
    for spec in R.visible_tests():
        if spec.runner != "system":
            continue
        for system in sorted(spec.systems & set(SCRIPT_SLOTS)):
            yield pytest.param(spec, system, id=f"{system}-{spec.function}-{spec.display_name}")


def test_registry_static_checks():
    assert R.validate_registry(SYSTEM_CLASSES, PLOT_TYPES) == []


def test_capabilities_match_registry():
    for spec in R.TESTS:
        for system in R.ALL_SYSTEMS:
            assert is_test_supported(system, spec.function) == (system in R.systems_for_function(spec.function))


def test_gui_lists_only_registered_systems():
    for system in R.ALL_SYSTEMS:
        for name, defn in get_test_definitions_for_gui(system).items():
            assert system in R.get_spec(name).systems


def test_optical_runner_knows_optical_tests():
    path = os.path.join(ROOT, "gui", "pulse_testing_gui", "optical_runner.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    for func in R.functions_with_runner("optical") | R.functions_with_runner("optical_sweep"):
        assert f"'{func}'" in src or f'"{func}"' in src, func


@pytest.mark.parametrize("spec,system", list(_cases()))
def test_dry_run_on_each_system(spec, system):
    script_cls, slot = SCRIPT_SLOTS[system]
    adapter = ADAPTER_CLASSES[system]()
    recorder = _ScriptRecorder(script_cls)
    setattr(adapter, slot, recorder)
    if hasattr(adapter, "_connected"):
        adapter._connected = True
    if spec.progress:
        params = dict(_gui_params(spec, system), progress_callback=lambda _r: None)
    else:
        params = _gui_params(spec, system)

    result = getattr(adapter, spec.function)(**params)

    assert recorder.calls, f"{system}.{spec.function} never reached its instrument script"
    assert not recorder.ignored, f"GUI params silently ignored by the script: {recorder.ignored}"
    assert isinstance(result, dict) and "timestamps" in result
