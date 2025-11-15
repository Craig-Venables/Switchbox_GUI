"""
Background plot updater threads.
================================

`PlotUpdaters` manages the long-running threads that keep matplotlib figures
in sync with the live measurement buffers exposed by `MeasurementGUI`.  The
logic used to live directly inside the GUI class; extracting it makes the
threads easier to test and keeps Tk widget code focused on layout.
"""

from __future__ import annotations

# Standard library imports
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence

# Third-party imports
import numpy as np


PlotBuffers = Sequence[float]


@dataclass
class PlotUpdaters:
    """Manage background threads that update matplotlib plot panels."""

    gui: Any
    plot_panels: Any
    interval_s: float = 0.1
    threads: Dict[str, threading.Thread] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._thread_flags: Dict[str, bool] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------
    def start_all_threads(self) -> None:
        """Ensure the core plot updater threads are running."""
        for name, target in (
            ("iv", self._update_iv_plots),
            ("ct", self._update_current_time_plot),
        ):
            self._ensure_thread(name, target)

    def start_temperature_thread(self, enabled: bool) -> None:
        """Start (or stop) the optional temperature plot thread."""
        if not enabled or "tt_rt" not in self.plot_panels.lines:
            self._stop_thread("tt")
            return
        self._ensure_thread("tt", self._update_temperature_plot)

    def stop_all_threads(self) -> None:
        """Signal every updater thread to finish and wait for shutdown."""
        with self._lock:
            for name in list(self._thread_flags.keys()):
                self._thread_flags[name] = False

        for name, thread in list(self.threads.items()):
            if thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=0.5)
            self.threads.pop(name, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_thread(self, name: str, target: Any) -> None:
        with self._lock:
            thread = self.threads.get(name)
            if thread is not None and thread.is_alive():
                self._thread_flags[name] = True
                return
            self._thread_flags[name] = True
            thread = threading.Thread(
                target=target,
                name=f"PlotUpdater-{name}",
                daemon=True,
            )
            self.threads[name] = thread
            thread.start()

    def _stop_thread(self, name: str) -> None:
        with self._lock:
            self._thread_flags[name] = False
            thread = self.threads.get(name)
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        with self._lock:
            self.threads.pop(name, None)

    def _thread_running(self, name: str) -> bool:
        return self._thread_flags.get(name, False)

    def _update_line(self, key: str, x: Sequence[float], y: Sequence[float]) -> None:
        line = self.plot_panels.lines.get(key)
        if line is None:
            return
        ax = self.plot_panels.axes.get(key)
        canvas = self.plot_panels.canvases.get(key)
        if ax is None or canvas is None:
            return
        try:
            line.set_data(list(x), list(y))
            ax.relim()
            ax.autoscale_view()
            canvas.draw()
        except Exception:
            # Drawing errors (e.g., empty data) should not kill the thread.
            pass

    # ------------------------------------------------------------------
    # Thread targets
    # ------------------------------------------------------------------
    def _update_iv_plots(self) -> None:
        name = "iv"
        while self._thread_running(name):
            if getattr(self.gui, "measuring", False):
                v = list(self.gui.v_arr_disp)
                i = list(self.gui.c_arr_disp)
                n = min(len(v), len(i))
                if n > 0:
                    voltages = v[:n]
                    currents = np.array(i[:n], dtype=float)
                    self._update_line("rt_iv", voltages, currents.tolist())

                    abs_currents = np.abs(currents)
                    abs_currents[abs_currents == 0] = 1e-12
                    abs_list = abs_currents.tolist()
                    try:
                        self.gui.c_arr_disp_abs = abs_list
                    except Exception:
                        pass
                    self._update_line("rt_logiv", voltages, abs_list)

                    abs_voltages = np.abs(np.array(voltages, dtype=float))
                    abs_voltages[abs_voltages == 0] = 1e-12
                    self._update_line("rt_logilogv", abs_voltages.tolist(), abs_list)
            time.sleep(self.interval_s)

    def _update_current_time_plot(self) -> None:
        name = "ct"
        while self._thread_running(name):
            if getattr(self.gui, "measuring", False):
                t = list(self.gui.t_arr_disp)
                c = list(self.gui.c_arr_disp)
                n = min(len(t), len(c))
                if n > 0:
                    self._update_line("ct_rt", t[:n], c[:n])
            time.sleep(self.interval_s)

    def _update_temperature_plot(self) -> None:
        name = "tt"
        while self._thread_running(name):
            if getattr(self.gui, "measuring", False):
                t = list(self.gui.t_arr_disp)
                temps: List[float] = list(getattr(self.gui, "temp_time_disp", self.gui.c_arr_disp))
                n = min(len(t), len(temps))
                if n > 0:
                    self._update_line("tt_rt", t[:n], temps[:n])
            time.sleep(self.interval_s)


def _self_test() -> Dict[str, bool]:
    """Basic diagnostic to ensure the updater scaffolding works."""
    class _Dummy:
        measuring = True
        v_arr_disp: PlotBuffers = [0.0, 1.0]
        c_arr_disp: PlotBuffers = [0.0, 1.0]
        c_arr_disp_abs: PlotBuffers = [0.0, 1.0]
        t_arr_disp: PlotBuffers = [0.0, 1.0]
        r_arr_disp: PlotBuffers = [0.0, 1.0]
        temp_time_disp: PlotBuffers = [25.0, 26.0]

    class _DummyPanels:
        def __init__(self) -> None:
            self.lines = {}
            self.axes = {}
            self.canvases = {}

    panels = _DummyPanels()
    updaters = PlotUpdaters(gui=_Dummy(), plot_panels=panels)
    updaters.start_all_threads()
    updaters.stop_all_threads()
    return {"threads_stopped": len(updaters.threads) == 0}


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    import json

    print(json.dumps(_self_test(), indent=2))

