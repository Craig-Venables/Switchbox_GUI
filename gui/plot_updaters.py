"""
Background plot updater scaffolding.
===================================

This module will host the real-time plotting threads that update matplotlib
figures while measurements run.  Extracting the logic from
`Measurement_GUI.py` keeps threading concerns away from widget code and
allows easier testing.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PlotUpdaters:
    """
    Placeholder class that will manage background plotting threads.

    The real implementations will be copied in during the refactor.  The
    scaffold ensures imports succeed and offers a consistent surface for the
    main GUI while we gradually migrate code.
    """

    plot_panels: object
    data_refs: Dict[str, object] = field(default_factory=dict)
    threads: Dict[str, threading.Thread] = field(default_factory=dict)
    running: bool = True

    def start_all_threads(self) -> None:
        raise NotImplementedError(
            "plot_updaters.start_all_threads is a scaffold; migration will provide the implementation."
        )

    def stop_all_threads(self) -> None:
        self.running = False
        for thread in self.threads.values():
            if thread.is_alive():
                thread.join(timeout=0.5)


def _self_test() -> Dict[str, bool]:
    """Exercise the scaffold without launching real threads."""
    updaters = PlotUpdaters(plot_panels=object())
    try:
        try:
            updaters.start_all_threads()
        except NotImplementedError:
            pass
    finally:
        updaters.stop_all_threads()
    return {"running": updaters.running, "thread_count": len(updaters.threads) == 0}


if __name__ == "__main__":  # pragma: no cover - manual scaffold check
    import json

    print(json.dumps(_self_test(), indent=2))

