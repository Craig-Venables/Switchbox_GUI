"""
Lightweight smoke tests for GUI package imports and tab registry.

Run: python -m gui.smoke_test

Does not require instrument drivers (pymeasure, pyvisa, etc.).
"""

from __future__ import annotations

import importlib
import sys


def test_tab_registry() -> None:
    from gui.measurement_gui.layout.tab_registry import TAB_REGISTRY, build_all_tabs

    assert len(TAB_REGISTRY) == 8
    ids = [spec.id for spec in TAB_REGISTRY]
    assert ids[0] == "measurements"
    assert "custom_sweeps" in ids
    assert callable(build_all_tabs)


def test_tool_registry() -> None:
    from gui.measurement_gui.tool_registry import DEFAULT_TOOLS, GuiToolRegistry

    registry = GuiToolRegistry()
    assert registry.get("display") is not None
    assert registry.get("led_testing") is not None
    assert len(DEFAULT_TOOLS) >= 2


def test_measurement_helpers() -> None:
    from gui.measurement_gui.connection_controller import ConnectionController
    from gui.measurement_gui.custom_measurement_runner import run_custom_measurement
    from gui.measurement_gui.lifecycle_controller import LifecycleController
    from gui.measurement_gui.save_path_controller import SavePathController, resolve_default_save_root
    from gui.measurement_gui.sample_gui_sync import SampleGuiSyncController
    from gui.measurement_gui.smu_adapter import SMUAdapter
    from gui.measurement_gui.system_config_controller import SystemConfigController

    assert callable(resolve_default_save_root)
    assert callable(run_custom_measurement)
    assert all(cls is not None for cls in (
        SavePathController, SampleGuiSyncController, ConnectionController,
        SystemConfigController, LifecycleController, SMUAdapter,
    ))


def test_sample_controllers() -> None:
    from gui.sample_gui.device_manager_controller import DeviceManagerController
    from gui.sample_gui.device_status_controller import DeviceStatusController
    from gui.sample_gui.quick_scan_controller import QuickScanController
    from gui.sample_gui.routing_controller import RoutingController
    from gui.sample_gui.selection_controller import SelectionController
    from gui.sample_gui.status_store import StatusStore
    from gui.sample_gui.telegram_controller import TelegramController
    from gui.sample_gui.terminal_log_controller import TerminalLogController

    assert all(
        cls is not None
        for cls in (
            DeviceManagerController,
            DeviceStatusController,
            QuickScanController,
            RoutingController,
            SelectionController,
            StatusStore,
            TelegramController,
            TerminalLogController,
        )
    )


def test_child_gui_registry() -> None:
    from gui.measurement_gui.child_gui_registry import DEFAULT_CHILD_GUIS, ChildGuiRegistry

    registry = ChildGuiRegistry()
    assert len(registry.specs) == len(DEFAULT_CHILD_GUIS)
    assert any(spec.tool_id == "pulse_testing" for spec in DEFAULT_CHILD_GUIS)


def test_child_gui_launchers() -> None:
    from gui.measurement_gui import child_gui_launchers

    assert callable(child_gui_launchers.open_pulse_testing_gui)
    assert callable(child_gui_launchers.resolve_sample_name)


def test_gui_state() -> None:
    from gui.measurement_gui.gui_state import MeasurementRuntimeState, PlotDisplayState

    runtime = MeasurementRuntimeState()
    assert runtime.measuring is False
    plot = PlotDisplayState()
    assert plot.pulse_history == []


def test_optional_full_imports() -> None:
    """Full GUI classes may require optional lab dependencies."""
    optional = (
        "gui.sample_gui",
        "gui.measurement_gui",
    )
    missing = []
    for mod in optional:
        try:
            importlib.import_module(mod)
        except ImportError as exc:
            missing.append(f"{mod}: {exc}")
    if missing:
        print("NOTE optional imports skipped (install requirements.txt for full check):")
        for line in missing:
            print(f"  - {line}")


def main() -> int:
    required = [
        test_tab_registry,
        test_tool_registry,
        test_child_gui_registry,
        test_child_gui_launchers,
        test_measurement_helpers,
        test_sample_controllers,
        test_gui_state,
    ]
    failed = 0
    for test in required:
        try:
            test()
            print(f"OK  {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    try:
        test_optional_full_imports()
        print("OK  test_optional_full_imports")
    except Exception as exc:
        print(f"NOTE test_optional_full_imports: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
