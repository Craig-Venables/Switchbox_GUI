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
    
    def start_endurance_thread(self, enabled: bool) -> None:
        """Start (or stop) the optional endurance plot thread."""
        if not enabled or "endurance" not in self.plot_panels.axes:
            self._stop_thread("endurance")
            self._stop_thread("endurance_current")
            return
        self._ensure_thread("endurance", self._update_endurance_plot)
        self._ensure_thread("endurance_current", self._update_endurance_current_plot)
    
    def start_retention_thread(self, enabled: bool) -> None:
        """Start (or stop) the optional retention plot thread."""
        if not enabled or "retention" not in self.plot_panels.axes:
            self._stop_thread("retention")
            return
        self._ensure_thread("retention", self._update_retention_plot)

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
            
            # Update red dot for most recent value
            recent_dot = self.plot_panels.recent_dots.get(key)
            if recent_dot is not None and len(x) > 0 and len(y) > 0:
                # Show red dot at the most recent point
                recent_dot.set_data([x[-1]], [y[-1]])
            elif recent_dot is not None:
                # Hide red dot if no data
                recent_dot.set_data([], [])
            
            ax.relim()
            ax.autoscale_view()
            canvas.draw()
            
            # Note: Graph activity terminal is only for "Run Full Sample Analysis" progress
            # Real-time plot updates are not logged to avoid spam
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
                    # Filter voltage: only show >= 0.1V (user requirement: don't go below 0.1V or -0.2V)
                    voltage_mask = abs_voltages >= 0.1
                    # Safety check: ensure abs_list and voltage_mask have matching lengths
                    if len(abs_list) == len(voltage_mask):
                        filtered_voltages = abs_voltages[voltage_mask]
                        filtered_currents = np.array(abs_list)[voltage_mask]
                        if len(filtered_voltages) > 0:
                            self._update_line("rt_logilogv", filtered_voltages.tolist(), filtered_currents.tolist())
                        else:
                            # If no data meets threshold, show empty plot
                            self._update_line("rt_logilogv", [], [])
                    else:
                        # Length mismatch - skip this update to avoid IndexError
                        self._update_line("rt_logilogv", [], [])
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
    
    def _update_endurance_plot(self) -> None:
        """Update endurance plot with ON/OFF ratios."""
        name = "endurance"
        while self._thread_running(name):
            if getattr(self.gui, "measuring", False):
                # Get endurance ratios from plot_panels
                ratios = list(getattr(self.plot_panels, "endurance_ratios", []))
                if ratios:
                    cycles = list(range(1, len(ratios) + 1))
                    # Use the plot_panels update method which handles the full plot setup
                    try:
                        self.plot_panels.update_endurance_plot(ratios)
                    except Exception:
                        pass
            time.sleep(self.interval_s)
    
    def _update_endurance_current_plot(self) -> None:
        """Update endurance current plot with ON and OFF currents over time."""
        name = "endurance_current"
        while self._thread_running(name):
            if getattr(self.gui, "measuring", False):
                # Get endurance current data from plot_panels
                on_times = list(getattr(self.plot_panels, "endurance_on_times", []))
                on_currents = list(getattr(self.plot_panels, "endurance_on_currents", []))
                off_times = list(getattr(self.plot_panels, "endurance_off_times", []))
                off_currents = list(getattr(self.plot_panels, "endurance_off_currents", []))
                
                if (on_times and on_currents) or (off_times and off_currents):
                    # Use the plot_panels update method which handles the full plot setup
                    try:
                        self.plot_panels.update_endurance_current_plot(
                            on_times, on_currents, off_times, off_currents
                        )
                    except Exception:
                        pass
            time.sleep(self.interval_s)
    
    def _update_retention_plot(self) -> None:
        """Update retention plot with time vs current."""
        name = "retention"
        while self._thread_running(name):
            if getattr(self.gui, "measuring", False):
                # Get retention data from plot_panels
                times = list(getattr(self.plot_panels, "retention_times", []))
                currents = list(getattr(self.plot_panels, "retention_currents", []))
                if times and currents and len(times) == len(currents):
                    # Use the plot_panels update method which handles the full plot setup
                    try:
                        self.plot_panels.update_retention_plot(times, currents)
                    except Exception:
                        pass
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

