"""
Shared manual-test section order: test selection above parameters.
"""

from __future__ import annotations

from gui.pulse_testing_gui.ui.parameters import init_parameters_section, pack_parameters_section
from gui.pulse_testing_gui.ui.test_selection import build_test_selection_section
from gui.pulse_testing_gui.ui.status_section import build_status_section


def build_manual_test_sections(
    parent,
    gui,
    *,
    compact: bool = False,
    show_smu_range: bool = False,
    log_height: int = 4,
    start_log_collapsed: bool = False,
) -> None:
    """Test Selection → Test Parameters → Status."""
    init_parameters_section(parent, gui, compact=compact)
    build_test_selection_section(parent, gui, show_smu_range=show_smu_range, defer_populate=True)
    pack_parameters_section(gui, compact=compact)
    if hasattr(gui, "test_var") and gui.test_var.get():
        gui.on_test_selected(None)
    build_status_section(
        parent,
        gui,
        log_height=log_height,
        start_collapsed=start_log_collapsed,
    )
