"""Electrical pulse test runner (Keithley2450_TSP_Scripts via system adapter)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .config import DATA_DIR, ensure_dirs
from .tests import OPTICAL_FUNCTIONS, convert_params_for_2450


ProgressCb = Optional[Callable[[str], None]]


def run_electrical_test(
    system,
    func_name: str,
    params: Dict[str, Any],
    progress: ProgressCb = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
    if func_name in OPTICAL_FUNCTIONS:
        return None, ValueError(f"{func_name} is optical — use optical_runner")
    if system is None or not system.is_connected():
        return None, RuntimeError("SMU not connected")

    script_params = convert_params_for_2450(dict(params))
    # Map GUI delay_between_cycles → delay_between for pot/dep scripts
    if "delay_between_cycles" in script_params and "delay_between" not in script_params:
        script_params["delay_between"] = script_params.pop("delay_between_cycles")
    elif "delay_between_cycles" in script_params:
        script_params.pop("delay_between_cycles")

    method = getattr(system, func_name, None)
    if method is None or not callable(method):
        return None, AttributeError(f"System has no method '{func_name}'")

    if progress:
        progress(f"Running {func_name}…")
    try:
        results = method(**script_params)
        if progress:
            progress(f"{func_name} complete")
        return results, None
    except Exception as e:
        return None, e


def save_results(
    results: Dict[str, Any],
    func_name: str,
    params: Dict[str, Any],
    folder: Optional[Path] = None,
) -> Path:
    ensure_dirs()
    out_dir = Path(folder) if folder else DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = out_dir / f"{stamp}_{func_name}"

    meta = {
        "function": func_name,
        "params": params,
        "saved_at": stamp,
    }
    json_path = Path(str(base) + ".json")
    payload = {"meta": meta, "results": _jsonable(results)}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    # Also write a simple CSV if time-series-like keys exist
    csv_path = Path(str(base) + ".csv")
    _maybe_write_csv(csv_path, results)
    return json_path


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    try:
        import numpy as np

        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.floating, np.integer)):
            return obj.item()
    except Exception:
        pass
    return str(obj)


def _maybe_write_csv(path: Path, results: Dict[str, Any]) -> None:
    keys = []
    for candidate in (
        "timestamps",
        "voltages",
        "currents",
        "resistances",
        "pulse_numbers",
        "cycle",
        "set_resistances",
        "reset_resistances",
    ):
        if candidate in results and isinstance(results[candidate], (list, tuple)):
            keys.append(candidate)
    if len(keys) < 1:
        return
    length = max(len(results[k]) for k in keys)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(",".join(keys) + "\n")
            for i in range(length):
                row = []
                for k in keys:
                    col = results[k]
                    row.append("" if i >= len(col) else str(col[i]))
                f.write(",".join(row) + "\n")
    except Exception:
        pass
