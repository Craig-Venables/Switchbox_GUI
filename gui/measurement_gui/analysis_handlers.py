"""
Analysis and Classification Handlers
====================================

Orchestration for IV analysis, classification, saving results, and retroactive
analysis. Extracted from main.py for maintainability.
"""

from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

DEBUG_ENABLED = False


def _debug_print(*args: Any, **kwargs: Any) -> None:
    if DEBUG_ENABLED:
        print(*args, **kwargs)


def format_analysis_value(value: Any, unit: str = "", precision: int = 3) -> str:
    """Format a numeric value for analysis output."""
    if value is None:
        return "N/A"
    try:
        if isinstance(value, (int, float)):
            if abs(value) >= 1e6:
                return f"{value/1e6:.{precision}f} M{unit}"
            elif abs(value) >= 1e3:
                return f"{value/1e3:.{precision}f} k{unit}"
            elif abs(value) < 1e-3 and abs(value) > 0:
                return f"{value*1e6:.{precision}f} μ{unit}"
            elif abs(value) < 1e-6 and abs(value) > 0:
                return f"{value*1e9:.{precision}f} n{unit}"
            else:
                return f"{value:.{precision}f} {unit}".strip()
        else:
            return str(value)
    except (ValueError, TypeError):
        return str(value) if value is not None else "N/A"


def run_analysis_sync(
    gui: Any,
    voltage: List[float],
    current: List[float],
    timestamps: Optional[List[float]],
    device_id: str,
    save_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Run analysis synchronously (blocking until complete)."""
    from analysis import quick_analyze

    try:
        if not (hasattr(gui, "analysis_enabled") and gui.analysis_enabled.get()):
            return None
        analysis_level = "full"
        print(f"[Conditional Testing] Running synchronous analysis on {len(voltage)} points...")
        analysis_data = quick_analyze(
            voltage=voltage,
            current=current,
            time=timestamps,
            analysis_level=analysis_level,
            device_id=device_id,
            save_directory=save_dir,
        )
        return analysis_data
    except Exception as exc:
        print(f"[Conditional Testing] Analysis failed: {exc}")
        import traceback
        traceback.print_exc()
        return None


def get_latest_analysis_for_device(gui: Any, device: str) -> Optional[Dict[str, Any]]:
    """Get the latest analysis result for a device."""
    if hasattr(gui, "_pending_analysis_results"):
        for key, result in gui._pending_analysis_results.items():
            if device in key:
                return result.get("analysis_data")
    try:
        save_dir = gui._get_save_directory(
            gui.sample_name_var.get(),
            gui.final_device_letter,
            gui.final_device_number,
        )
        analysis_dir = Path(save_dir) / "sample_analysis" / "analysis" / "sweeps" / device
        if analysis_dir.exists():
            json_files = list(analysis_dir.glob("*.json"))
            if json_files:
                latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
                with latest_file.open("r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception as exc:
        print(f"[Conditional Testing] Failed to load analysis for {device}: {exc}")
    return None
