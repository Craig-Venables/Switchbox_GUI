"""Save-path resolution and custom save-location UI for MeasurementGUI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, List

import tkinter as tk

if TYPE_CHECKING:
    from gui.measurement_gui.main import MeasurementGUI

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_default_save_root() -> Path:
    """Resolve the default Data_folder under OneDrive or local Documents."""
    home = Path.home()
    candidates: List[Path] = []

    for env_key in ("OneDriveCommercial", "OneDrive"):
        env_path = os.environ.get(env_key)
        if env_path:
            candidates.append(Path(env_path) / "Documents")

    candidates.append(home / "OneDrive - The University of Nottingham" / "Documents")
    candidates.append(home / "Documents")

    for documents_path in candidates:
        try:
            if not documents_path.parent.exists():
                continue
            documents_path.mkdir(parents=True, exist_ok=True)
            target = documents_path / "Data_folder"
            target.mkdir(parents=True, exist_ok=True)
            return target
        except Exception:
            continue

    fallback = home / "Documents" / "Data_folder"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


class SavePathController:
    """Custom save location toggle, config persistence, and path helpers."""

    def __init__(self, gui: "MeasurementGUI") -> None:
        self.gui = gui

    def on_custom_save_toggle(self) -> None:
        gui = self.gui
        if gui.use_custom_save_var.get():
            self.prompt_save_location()
        else:
            gui.save_path_entry.config(state="disabled")
            for widget in gui.save_path_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="disabled")
            gui.custom_save_location = None
            gui.custom_save_location_var.set("")
        self.save_config()

    def prompt_save_location(self) -> None:
        from tkinter import filedialog

        gui = self.gui
        folder = filedialog.askdirectory(
            title="Choose Custom Data Save Location",
            mustexist=False,
        )
        if folder:
            gui.custom_save_location = Path(folder)
            gui.custom_save_location_var.set(str(gui.custom_save_location))
            gui.save_path_entry.config(state="normal")
            for widget in gui.save_path_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="normal")
        else:
            gui.use_custom_save_var.set(False)
            gui.save_path_entry.config(state="disabled")
            for widget in gui.save_path_entry.master.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state="disabled")

    def browse_save_location(self) -> None:
        from tkinter import filedialog

        gui = self.gui
        folder = filedialog.askdirectory(
            title="Choose Data Save Location",
            mustexist=False,
        )
        if folder:
            gui.custom_save_location = Path(folder)
            gui.custom_save_location_var.set(str(gui.custom_save_location))
            self.save_config()

    def load_config(self) -> None:
        gui = self.gui
        config_file = _PROJECT_ROOT / "Json_Files" / "save_location_config.json"
        try:
            if not config_file.exists():
                return
            with config_file.open("r", encoding="utf-8") as f:
                config = json.load(f)
            gui.use_custom_save_var.set(False)
            custom_path = config.get("custom_save_path", "")
            gui.custom_save_location_var.set(custom_path if custom_path else "")
            if hasattr(gui, "analysis_enabled"):
                gui.analysis_enabled.set(config.get("analysis_enabled", False))
        except Exception as exc:
            print(f"Could not load save location config: {exc}")

    def save_config(self) -> None:
        gui = self.gui
        config_file = _PROJECT_ROOT / "Json_Files" / "save_location_config.json"
        try:
            config = {}
            if config_file.exists():
                with config_file.open("r", encoding="utf-8") as f:
                    config = json.load(f)
            config["use_custom_save"] = gui.use_custom_save_var.get()
            config["custom_save_path"] = (
                str(gui.custom_save_location) if gui.custom_save_location else ""
            )
            if hasattr(gui, "analysis_enabled"):
                config["analysis_enabled"] = gui.analysis_enabled.get()
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with config_file.open("w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as exc:
            print(f"Could not save save location config: {exc}")

    def get_base_save_path(self) -> str:
        gui = self.gui
        if gui.use_custom_save_var.get() and gui.custom_save_location:
            return str(gui.custom_save_location)
        return str(gui.default_save_root)

    def get_save_directory(
        self, sample_name: str, device_letter: str, device_number: str,
    ) -> str:
        device_path = (
            Path(self.get_base_save_path())
            / sample_name
            / device_letter
            / str(device_number)
        )
        device_path.mkdir(parents=True, exist_ok=True)
        return str(device_path)

    def get_sample_save_directory(self, sample_name: str) -> str:
        sample_path = Path(self.get_base_save_path()) / sample_name
        sample_path.mkdir(parents=True, exist_ok=True)
        return str(sample_path)
