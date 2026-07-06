"""Device naming, persistence, and Device Manager tab logic for SampleGUI."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import tkinter as tk
from tkinter import messagebox

from gui.sample_gui.config import resolve_default_save_root

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI


class DeviceManagerController:
    """Current device metadata, tree list, and load/save."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui

    def get_folder(self, device_name: Optional[str] = None) -> Path:
        save_root = resolve_default_save_root()
        name = device_name or self.gui.current_device_name
        if not name:
            raise ValueError("No device name specified")
        return save_root / name

    def set_current_device(self) -> None:
        gui = self.gui
        device_name = gui.device_name_entry.get().strip()
        if not device_name:
            messagebox.showwarning("Device Name", "Please enter a device name (e.g., D104)")
            return

        cleaned_name = re.sub(r"[^A-Za-z0-9_\-\.\(\)% ]+", "_", device_name)
        if cleaned_name != device_name:
            messagebox.showinfo(
                "Device Name Adjusted",
                f"Some characters in '{device_name}' were not allowed.\n"
                f"The device name has been adjusted to:\n{cleaned_name}",
            )
            device_name = cleaned_name

        gui.current_device_name = device_name
        gui._notify_child_guis("device_name", device_name=device_name)

        device_folder = self.get_folder()
        device_folder.mkdir(parents=True, exist_ok=True)

        sample_type = gui.sample_type_var.get()
        gui.device_info = {
            "name": device_name,
            "sample_type": sample_type,
            "created": datetime.now().isoformat(timespec="seconds"),
            "last_modified": datetime.now().isoformat(timespec="seconds"),
            "notes": "",
        }

        self.save_device_info()
        gui.device_name_label.config(text=device_name, fg="#4CAF50")
        self.update_info_display()
        gui.log_terminal(f"Set current device to: {device_name}", "SUCCESS")
        self.refresh_device_list()
        if hasattr(gui, "reclassify_ctrl"):
            gui.reclassify_ctrl.update_menu_labels()

    def clear_current_device(self) -> None:
        gui = self.gui
        if not messagebox.askyesno("Clear Device", "Are you sure you want to clear the current device?"):
            return
        gui.current_device_name = None
        gui.device_info = {}
        gui.device_name_entry.delete(0, tk.END)
        gui.device_name_label.config(text="No Device", fg="#888888")
        self.update_info_display()
        gui.log_terminal("Cleared current device", "INFO")
        gui._notify_child_guis("device_name", device_name=None)
        if hasattr(gui, "reclassify_ctrl"):
            gui.reclassify_ctrl.update_menu_labels()

    def save_device_info(self) -> None:
        gui = self.gui
        if not gui.current_device_name:
            messagebox.showwarning("No Device", "No device is currently set.")
            return

        device_folder = self.get_folder()
        device_folder.mkdir(parents=True, exist_ok=True)
        gui.device_info["last_modified"] = datetime.now().isoformat(timespec="seconds")

        info_path = device_folder / "device_info.json"
        try:
            with info_path.open("w", encoding="utf-8") as f:
                json.dump(gui.device_info, f, indent=2)
            gui.log_terminal(f"Saved device info for {gui.current_device_name}", "SUCCESS")
        except Exception as exc:
            messagebox.showerror("Save Error", f"Failed to save device info: {exc}")
            gui.log_terminal(f"Error saving device info: {exc}", "ERROR")

    def load_selected_device(self) -> None:
        gui = self.gui
        selection = gui.device_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a device from the list.")
            return
        item = gui.device_tree.item(selection[0])
        self.load_device(item["values"][0])

    def load_device(self, device_name: str) -> None:
        gui = self.gui
        device_folder = self.get_folder(device_name)
        if not device_folder.exists():
            messagebox.showerror("Device Not Found", f"Device folder not found: {device_folder}")
            return

        info_path = device_folder / "device_info.json"
        if not info_path.exists():
            messagebox.showerror("Device Info Missing", f"Device info file not found: {info_path}")
            return

        try:
            with info_path.open("r", encoding="utf-8") as f:
                gui.device_info = json.load(f)

            gui.current_device_name = device_name
            gui.device_name_entry.delete(0, tk.END)
            gui.device_name_entry.insert(0, device_name)
            gui.device_name_label.config(text=device_name, fg="#4CAF50")
            gui._notify_child_guis("device_name", device_name=device_name)

            if "sample_type" in gui.device_info:
                gui.sample_type_var.set(gui.device_info["sample_type"])
                gui.update_dropdowns(None)

            status_path = device_folder / "device_status.json"
            if status_path.exists():
                with status_path.open("r", encoding="utf-8") as f:
                    gui.device_status = json.load(f)
                gui.log_terminal(f"Loaded device status for {device_name}", "SUCCESS")

            quick_scan_path = device_folder / "quick_scan.json"
            if quick_scan_path.exists():
                with quick_scan_path.open("r", encoding="utf-8") as f:
                    scan_data = json.load(f)
                results = {}
                for entry in scan_data.get("results", []):
                    key = entry.get("device_key")
                    current = entry.get("current_a")
                    if key is not None:
                        results[key] = current
                gui.quick_scan_results = results
                gui._redraw_quick_scan_overlay()
                gui.log_terminal(f"Loaded quick scan results for {device_name}", "SUCCESS")

            self.update_info_display()
            gui.log_terminal(f"Loaded device: {device_name}", "SUCCESS")

            if hasattr(gui, "reclassify_ctrl"):
                gui.reclassify_ctrl.update_menu_labels()

            if hasattr(gui, "device_status_labels"):
                for device, status_label in gui.device_status_labels.items():
                    status_info = gui.device_status.get(device, {})
                    manual_status = status_info.get("manual_status", "undefined")
                    icon = gui.status_icons.get(manual_status, "?")
                    color = gui._get_status_color(manual_status)
                    status_label.config(text=icon, fg=color)
        except Exception as exc:
            messagebox.showerror("Load Error", f"Failed to load device: {exc}")
            gui.log_terminal(f"Error loading device {device_name}: {exc}", "ERROR")

    def refresh_device_list(self) -> None:
        gui = self.gui
        for item in gui.device_tree.get_children():
            gui.device_tree.delete(item)

        save_root = resolve_default_save_root()
        if not save_root.exists():
            return

        filter_type = gui.device_filter_var.get()
        for device_folder in save_root.iterdir():
            if not device_folder.is_dir():
                continue
            info_path = device_folder / "device_info.json"
            if not info_path.exists():
                continue
            try:
                with info_path.open("r", encoding="utf-8") as f:
                    info = json.load(f)
                device_name = info.get("name", device_folder.name)
                sample_type = info.get("sample_type", "Unknown")
                last_modified = info.get("last_modified", "Unknown")
                if filter_type != "All" and sample_type != filter_type:
                    continue
                status = "Has Data" if (device_folder / "device_status.json").exists() else "New"
                gui.device_tree.insert(
                    "", "end", values=(device_name, sample_type, last_modified, status),
                )
            except Exception as exc:
                print(f"Error reading device {device_folder.name}: {exc}")

    def update_info_display(self) -> None:
        gui = self.gui
        gui.device_info_text.config(state=tk.NORMAL)
        gui.device_info_text.delete("1.0", tk.END)

        if not gui.current_device_name:
            gui.device_info_text.insert(
                "1.0",
                "No device currently set.\n\nEnter a device name and click 'Set Device' to begin.",
            )
        else:
            info_lines = [
                f"Device Name: {gui.device_info.get('name', 'Unknown')}",
                f"Sample Type: {gui.device_info.get('sample_type', 'Unknown')}",
                f"Created: {gui.device_info.get('created', 'Unknown')}",
                f"Last Modified: {gui.device_info.get('last_modified', 'Unknown')}",
                "",
            ]
            sample_name = gui.current_device_name
            try:
                notes_path = resolve_default_save_root() / sample_name / "notes.json"
                if notes_path.exists():
                    with notes_path.open("r", encoding="utf-8") as f:
                        notes_data = json.load(f)
                    sample_notes = notes_data.get("Sample_Notes", "")
                    if sample_notes:
                        info_lines.extend(["Sample Notes:", sample_notes, "", "=" * 50, ""])
                    info_lines.append("Device Notes:")
                    device_notes_dict = notes_data.get("device", {})
                    if device_notes_dict:
                        for device_id, device_notes in sorted(device_notes_dict.items()):
                            if device_notes.strip():
                                info_lines.extend([f"\n{device_id}:", device_notes, ""])
                    else:
                        info_lines.append("No device notes found.")
            except Exception as exc:
                print(f"Error loading notes from notes.json: {exc}")
                info_lines.append("Error loading notes from notes.json")

            gui.device_info_text.insert("1.0", "\n".join(info_lines))

        gui.device_info_text.config(state=tk.DISABLED)
