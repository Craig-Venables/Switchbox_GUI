"""
Deterministic tab registration for the Measurement GUI notebook.

Add or reorder tabs by editing TAB_REGISTRY only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .tab_measurements import build_measurements_tab
from .tab_advanced_tests import build_advanced_tests_tab
from .tab_setup import build_setup_tab
from .tab_custom_measurements import build_custom_measurements_tab
from .tab_notes import build_notes_tab
from .tab_stats import build_stats_tab
from .tab_graphing import build_graphing_tab
from .tab_custom_sweeps import build_custom_sweeps_graphing_tab


@dataclass(frozen=True)
class TabSpec:
    """One notebook tab: stable id, visible label, builder callable."""

    id: str
    label: str
    builder: Callable[[Any, Any], None]


# Order here is the runtime tab order in the Measurement GUI.
TAB_REGISTRY: tuple[TabSpec, ...] = (
    TabSpec("measurements", "  Measurements  ", build_measurements_tab),
    TabSpec("advanced_tests", "  Advanced Tests  ", build_advanced_tests_tab),
    TabSpec("setup", "  Setup  ", build_setup_tab),
    TabSpec("custom_measurements", "  Custom Measurements  ", build_custom_measurements_tab),
    TabSpec("notes", "  Notes  ", build_notes_tab),
    TabSpec("stats", "  Stats  ", build_stats_tab),
    TabSpec("graphing", "  Graphing  ", build_graphing_tab),
    TabSpec("custom_sweeps", "  Custom Sweeps  ", build_custom_sweeps_graphing_tab),
)


def build_all_tabs(builder: Any, notebook: Any) -> None:
    """Register every tab from TAB_REGISTRY on the given notebook."""
    for spec in TAB_REGISTRY:
        spec.builder(builder, notebook)
