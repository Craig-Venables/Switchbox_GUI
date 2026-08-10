"""Simple matplotlib plotting for TSP GUI results."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def plot_results(ax, results: Any, plot_type: str = "time_series", title: str = "") -> None:
    ax.clear()
    if results is None:
        ax.text(0.5, 0.5, "No results", ha="center", va="center")
        ax.set_title(title or "Results")
        return

    # Multi-run optical sweeps: plot last run
    if isinstance(results, list):
        if not results:
            ax.text(0.5, 0.5, "No runs", ha="center", va="center")
            return
        results = results[-1]
        title = (title or "") + " (last run)"

    if not isinstance(results, dict):
        ax.text(0.5, 0.5, "Unsupported result type", ha="center", va="center")
        return

    try:
        if plot_type == "endurance":
            _plot_endurance(ax, results)
        elif plot_type == "width_vs_resistance":
            _plot_width(ax, results)
        elif plot_type == "pot_dep_cycle":
            _plot_pot_dep(ax, results)
        else:
            _plot_time_series(ax, results)
    except Exception as e:
        ax.clear()
        ax.text(0.5, 0.5, f"Plot error:\n{e}", ha="center", va="center", fontsize=8)

    if title:
        ax.set_title(title)
    ax.grid(True, alpha=0.3)


def _plot_time_series(ax, results: Dict[str, Any]) -> None:
    ts = results.get("timestamps")
    resistances = results.get("resistances")
    currents = results.get("currents")

    if ts and resistances and len(ts) == len(resistances):
        ax.plot(ts, resistances, ".-", label="R")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Resistance (Ohm)")
        ax.set_yscale("log")
    elif ts and currents and len(ts) == len(currents):
        ax.plot(ts, currents, ".-", label="I")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Current (A)")
    elif resistances:
        ax.plot(resistances, ".-", label="R")
        ax.set_xlabel("Index")
        ax.set_ylabel("Resistance (Ohm)")
        ax.set_yscale("log")
    elif currents:
        ax.plot(currents, ".-", label="I")
        ax.set_xlabel("Index")
        ax.set_ylabel("Current (A)")
    else:
        # Fallback: plot first numeric list found
        for key, val in results.items():
            if isinstance(val, (list, tuple)) and val and isinstance(val[0], (int, float)):
                ax.plot(val, ".-", label=key)
                ax.set_xlabel("Index")
                ax.set_ylabel(key)
                break
        else:
            ax.text(0.5, 0.5, "No plottable series", ha="center", va="center")
            return

    intervals = results.get("laser_on_intervals") or []
    for start, end in intervals:
        ax.axvspan(start, end, color="orange", alpha=0.25)
    if intervals:
        ax.legend(loc="best")


def _plot_endurance(ax, results: Dict[str, Any]) -> None:
    set_r = results.get("set_resistances") or results.get("resistances_set")
    reset_r = results.get("reset_resistances") or results.get("resistances_reset")
    if set_r:
        ax.semilogy(range(1, len(set_r) + 1), set_r, "o-", label="SET R")
    if reset_r:
        ax.semilogy(range(1, len(reset_r) + 1), reset_r, "s-", label="RESET R")
    if not set_r and not reset_r:
        _plot_time_series(ax, results)
        return
    ax.set_xlabel("Cycle")
    ax.set_ylabel("Resistance (Ohm)")
    ax.legend(loc="best")


def _plot_width(ax, results: Dict[str, Any]) -> None:
    widths = results.get("pulse_widths") or results.get("widths")
    resistances = results.get("resistances") or results.get("mean_resistances")
    if widths and resistances and len(widths) == len(resistances):
        ax.semilogx(widths, resistances, "o-")
        ax.set_xlabel("Pulse width (s)")
        ax.set_ylabel("Resistance (Ohm)")
        ax.set_yscale("log")
    else:
        _plot_time_series(ax, results)


def _plot_pot_dep(ax, results: Dict[str, Any]) -> None:
    resistances = results.get("resistances")
    if resistances:
        ax.semilogy(range(len(resistances)), resistances, ".-")
        ax.set_xlabel("Step")
        ax.set_ylabel("Resistance (Ohm)")
    else:
        _plot_time_series(ax, results)
