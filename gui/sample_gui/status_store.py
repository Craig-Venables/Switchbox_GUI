"""
Device status and quick-scan persistence for SampleGUI.

Handles JSON/Excel save-load for device status and quick-scan result files.
UI updates remain the responsibility of SampleGUI; this module owns I/O.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from gui.sample_gui.config import BASE_DIR, resolve_default_save_root

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI


class StatusStore:
    """Persistence helpers for device status and quick-scan data."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui

    def get_quick_scan_storage_dir(self, sample: str) -> Path:
        if self.gui.current_device_name:
            try:
                return self.gui.get_device_folder()
            except ValueError:
                pass
        return BASE_DIR / "Data_maps" / sample

    def save_device_status(self) -> None:
        gui = self.gui
        if gui.current_device_name:
            try:
                save_dir = gui.get_device_folder()
            except ValueError:
                return
        else:
            sample = gui.sample_type_var.get()
            if not sample:
                return
            save_dir = resolve_default_save_root() / sample

        save_dir.mkdir(parents=True, exist_ok=True)
        json_path = save_dir / "device_status.json"
        try:
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(gui.device_status, f, indent=2)
        except Exception as exc:
            gui.log_terminal(f"Failed to save device status JSON: {exc}", "ERROR")

        self.save_device_status_excel(save_dir / "device_status.xlsx")

    def save_device_status_excel(self, path: Path) -> None:
        gui = self.gui
        try:
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Device", "Auto Classification", "Manual Status", "Last Current (A)",
                    "Test Voltage (V)", "Last Tested", "Measurement Count", "Notes",
                ])
                for device in gui.device_list:
                    label = gui.get_device_label(device)
                    status_info = gui.device_status.get(device, {})
                    writer.writerow([
                        label,
                        status_info.get("auto_classification", "unknown"),
                        status_info.get("manual_status", "undefined"),
                        f"{status_info.get('last_current_a', 0):.3e}" if status_info.get("last_current_a") else "",
                        status_info.get("test_voltage_v", ""),
                        status_info.get("last_tested", ""),
                        status_info.get("measurement_count", 0),
                        status_info.get("notes", ""),
                    ])
        except Exception as exc:
            gui.log_terminal(f"Failed to save Excel: {exc}", "ERROR")

    def load_device_status(self) -> None:
        gui = self.gui
        sample = gui.sample_type_var.get()
        if not sample:
            return

        json_path = resolve_default_save_root() / sample / "device_status.json"
        if not json_path.exists():
            gui.log_terminal("No saved device status found", "INFO")
            return

        try:
            with json_path.open("r", encoding="utf-8") as f:
                gui.device_status = json.load(f)
            gui.log_terminal(f"Loaded device status from {json_path.name}", "SUCCESS")

            if hasattr(gui, "device_status_labels"):
                for device, status_label in gui.device_status_labels.items():
                    status_info = gui.device_status.get(device, {})
                    manual_status = status_info.get("manual_status", "undefined")
                    icon = gui.status_icons.get(manual_status, "?")
                    color = gui._get_status_color(manual_status)
                    status_label.config(text=icon, fg=color)
        except Exception as exc:
            gui.log_terminal(f"Failed to load device status: {exc}", "ERROR")

    def default_device_status_entry(self) -> Dict[str, Any]:
        return {
            "auto_classification": "unknown",
            "manual_status": "undefined",
            "last_current_a": None,
            "test_voltage_v": None,
            "last_tested": datetime.now().isoformat(timespec="seconds"),
            "notes": "",
            "measurement_count": 0,
            "quick_scan_history": [],
        }
