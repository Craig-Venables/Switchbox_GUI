"""
Background Measurement Workers
==============================

Hosts threaded worker routines that were historically defined inside
`Measurement_GUI`.  Extracting these helpers keeps the GUI class lighter while
preserving existing behaviour.
"""

from __future__ import annotations

import threading
import time
from typing import Any, List

from tkinter import messagebox

from Measurments.data_utils import safe_measure_current


def start_manual_endurance(gui: Any) -> None:
    """Kick off manual endurance in a background worker thread."""
    if not getattr(gui, "connected", False):
        messagebox.showwarning("Warning", "Not connected to Keithley!")
        return
    threading.Thread(
        target=_manual_endurance_worker, args=(gui,), daemon=True
    ).start()


def start_manual_retention(gui: Any) -> None:
    """Kick off manual retention capture in a background worker thread."""
    if not getattr(gui, "connected", False):
        messagebox.showwarning("Warning", "Not connected to Keithley!")
        return

    try:
        total = max(1, gui.ret_points.get()) * max(
            0.001, gui.ret_every_s.get()
        )
        gui.ret_estimate_var.set(f"Total: ~{int(total)} s")
    except Exception:
        pass

    threading.Thread(
        target=_manual_retention_worker, args=(gui,), daemon=True
    ).start()


# ---------------------------------------------------------------------------
# Internal worker implementations
# ---------------------------------------------------------------------------


def _manual_endurance_worker(gui: Any) -> None:
    """Worker: alternates SET/RESET pulses and plots ON/OFF ratio."""
    try:
        set_v = gui.end_set_v.get()
        reset_v = gui.end_reset_v.get()
        width_s = max(0.001, gui.end_pulse_ms.get() / 1000.0)
        cycles = max(1, gui.end_cycles.get())
        read_v = gui.end_read_v.get()
        icc = gui.icc.get()

        gui.endurance_ratios = []
        gui.keithley.enable_output(True)
        for idx in range(cycles):
            if getattr(gui, "stop_measurement_flag", False):
                break
            gui.keithley.set_voltage(set_v, icc)
            time.sleep(width_s)

            gui.keithley.set_voltage(read_v, icc)
            time.sleep(0.01)
            i_on = safe_measure_current(gui.keithley)

            gui.keithley.set_voltage(reset_v, icc)
            time.sleep(width_s)

            gui.keithley.set_voltage(read_v, icc)
            time.sleep(0.01)
            i_off = safe_measure_current(gui.keithley)

            ratio = (abs(i_on) + 1e-12) / (abs(i_off) + 1e-12)
            gui.endurance_ratios.append(ratio)

            gui.ax_endurance.clear()
            gui.ax_endurance.set_title("Endurance (ON/OFF)")
            gui.ax_endurance.set_xlabel("Cycle")
            gui.ax_endurance.set_ylabel("ON/OFF Ratio")
            gui.ax_endurance.plot(
                range(1, len(gui.endurance_ratios) + 1),
                gui.endurance_ratios,
                marker="o",
            )
            gui.canvas_endurance.draw()
        gui.keithley.enable_output(False)
    except Exception as exc:
        print("Manual endurance error:", exc)


def _manual_retention_worker(gui: Any) -> None:
    """Worker: applies SET then samples current at READ V over time."""
    try:
        set_v = gui.ret_set_v.get()
        set_ms = max(0.001, gui.ret_set_ms.get() / 1000.0)
        read_v = gui.ret_read_v.get()

        times = _build_retention_schedule(gui)
        icc = gui.icc.get()

        gui.retention_times = []
        gui.retention_currents = []
        gui.keithley.enable_output(True)

        gui.keithley.set_voltage(set_v, icc)
        time.sleep(set_ms)

        t0 = time.time()
        for target in times:
            while (time.time() - t0) < target:
                time.sleep(0.01)

            gui.keithley.set_voltage(read_v, icc)
            time.sleep(0.01)
            current = safe_measure_current(gui.keithley)

            gui.retention_times.append(target)
            gui.retention_currents.append(abs(current))

            gui.ax_retention.clear()
            gui.ax_retention.set_title("Retention")
            gui.ax_retention.set_xlabel("Time (s)")
            gui.ax_retention.set_ylabel("Current (A)")
            gui.ax_retention.set_xscale("log")
            gui.ax_retention.set_yscale("log")
            gui.ax_retention.plot(
                gui.retention_times,
                gui.retention_currents,
                marker="x",
            )
            gui.canvas_retention.draw()
        gui.keithley.enable_output(False)
    except Exception as exc:
        print("Manual retention error:", exc)


def _build_retention_schedule(gui: Any) -> List[float]:
    try:
        every = max(0.001, gui.ret_every_s.get())
        points = max(1, gui.ret_points.get())
        return [every * i for i in range(1, points + 1)]
    except Exception:
        return [10 * i for i in range(1, 31)]


__all__ = ["start_manual_endurance", "start_manual_retention"]


