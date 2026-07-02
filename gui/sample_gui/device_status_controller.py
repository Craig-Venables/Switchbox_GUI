"""Device status marking, menus, and threshold classification for SampleGUI."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

import tkinter as tk
from tkinter import messagebox, ttk

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI


class DeviceStatusController:
    """Manual/auto device status UI and persistence triggers."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui

    @staticmethod
    def status_color(status: str) -> str:
        return {
            "working": "#4CAF50",
            "broken": "#F44336",
            "undefined": "#888888",
        }.get(status, "#888888")

    def show_menu(self, event: Any, device: str) -> None:
        gui = self.gui
        menu = tk.Menu(gui.root, tearoff=0)
        label = gui.get_device_label(device)

        menu.add_command(label=f"Device {label}", state=tk.DISABLED, font=("Segoe UI", 9, "bold"))
        menu.add_separator()
        menu.add_command(label="✓ Mark as Working", command=lambda: self.mark_device(device, "working", quick=True))
        menu.add_command(label="✗ Mark as Broken", command=lambda: self.mark_device(device, "broken", quick=True))
        menu.add_command(label="? Mark as Undefined", command=lambda: self.mark_device(device, "undefined", quick=True))
        menu.add_separator()
        menu.add_command(label="Add/Edit Note...", command=lambda: self.mark_device(device, None, quick=False))
        menu.add_separator()
        menu.add_command(label="View Status Info", command=lambda: self.show_info(device))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def mark_selected(self, status: str) -> None:
        gui = self.gui
        if not gui.selected_devices:
            messagebox.showwarning("No Selection", "No devices selected.")
            return
        for device in gui.selected_devices:
            self.mark_device(device, status, quick=True)
        gui.log_terminal(f"Marked {len(gui.selected_devices)} device(s) as {status}", "SUCCESS")

    def mark_device(self, device: str, status: Optional[str], quick: bool = True) -> None:
        gui = self.gui
        label = gui.get_device_label(device)

        if not quick:
            dialog = tk.Toplevel(gui.root)
            dialog.title(f"Device Status: {label}")
            dialog.geometry("400x300")
            dialog.transient(gui.root)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Device: {label}", font=("Segoe UI", 10, "bold")).pack(pady=10)
            status_frame = ttk.Frame(dialog)
            status_frame.pack(pady=10)
            ttk.Label(status_frame, text="Status:").grid(row=0, column=0, padx=5)
            status_var = tk.StringVar(value=status or "undefined")
            for col, (text, val) in enumerate(
                [("✓ Working", "working"), ("✗ Broken", "broken"), ("? Undefined", "undefined")], start=1,
            ):
                ttk.Radiobutton(status_frame, text=text, variable=status_var, value=val).grid(row=0, column=col, padx=5)

            ttk.Label(dialog, text="Notes:").pack(anchor="w", padx=20)
            notes_text = tk.Text(dialog, height=8, width=45, wrap=tk.WORD)
            notes_text.pack(padx=20, pady=5)
            existing_notes = gui.device_status.get(device, {}).get("notes", "")
            if existing_notes:
                notes_text.insert("1.0", existing_notes)

            def save_status() -> None:
                self.update_device(device, status_var.get(), notes=notes_text.get("1.0", tk.END).strip())
                dialog.destroy()

            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="Save", command=save_status, width=12).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=12).pack(side="left", padx=5)
            dialog.wait_window()
        elif status:
            self.update_device(device, status)

    def update_device(self, device: str, manual_status: str, notes: str = "") -> None:
        gui = self.gui
        label = gui.get_device_label(device)
        if device not in gui.device_status:
            gui.device_status[device] = gui.status_store.default_device_status_entry()
        gui.device_status[device]["manual_status"] = manual_status
        if notes:
            gui.device_status[device]["notes"] = notes
        gui.device_status[device]["last_tested"] = datetime.now().isoformat(timespec="seconds")

        if device in gui.device_status_labels:
            icon = gui.status_icons.get(manual_status, "?")
            gui.device_status_labels[device].config(
                text=icon, fg=self.status_color(manual_status),
            )
        gui.status_store.save_device_status()
        if notes:
            gui.log_terminal(f"Device {label}: Status updated to '{manual_status}' with notes (auto-saved)", "SUCCESS")
        else:
            gui.log_terminal(f"Device {label}: Status updated to '{manual_status}' (auto-saved)", "SUCCESS")
        gui.quick_scan_ctrl.redraw_overlay()

    def show_info(self, device: str) -> None:
        gui = self.gui
        label = gui.get_device_label(device)
        info = gui.device_status.get(device, {})
        last_current = info.get("last_current_a")
        test_voltage = info.get("test_voltage_v")
        messagebox.showinfo(
            f"Device Status: {label}",
            (
                f"Device: {label}\n\n"
                f"Auto Classification: {info.get('auto_classification', 'unknown')}\n"
                f"Manual Status: {info.get('manual_status', 'undefined')}\n"
                f"Last Current: {f'{last_current:.3e} A' if last_current else 'N/A'}\n"
                f"Test Voltage: {f'{test_voltage} V' if test_voltage else 'N/A'}\n"
                f"Last Tested: {info.get('last_tested', 'Never')}\n"
                f"Measurement Count: {info.get('measurement_count', 0)}\n\n"
                f"Notes:\n{info.get('notes', 'No notes')}"
            ),
        )

    def apply_threshold_to_undefined(self) -> None:
        gui = self.gui
        classified_count = 0
        for device in gui.device_list:
            if gui.device_status.get(device, {}).get("manual_status", "undefined") != "undefined":
                continue
            current = gui.quick_scan_results.get(device)
            if current is None:
                continue
            auto_class = "working" if current >= gui.quick_scan_threshold else "not-working"
            if device not in gui.device_status:
                entry = gui.status_store.default_device_status_entry()
                entry["auto_classification"] = auto_class
                entry["last_current_a"] = current
                entry["test_voltage_v"] = gui.quick_scan_voltage_var.get()
                gui.device_status[device] = entry
            else:
                gui.device_status[device]["auto_classification"] = auto_class
                gui.device_status[device]["last_current_a"] = current
                gui.device_status[device]["test_voltage_v"] = gui.quick_scan_voltage_var.get()
            classified_count += 1

        if classified_count > 0:
            gui.status_store.save_device_status()
            gui.quick_scan_ctrl.redraw_overlay()
            gui.log_terminal(f"Applied threshold to {classified_count} undefined device(s)", "SUCCESS")
        else:
            messagebox.showinfo("Threshold", "No undefined devices to classify.")

    def export_excel(self) -> None:
        gui = self.gui
        sample = gui.sample_type_var.get()
        if not sample:
            messagebox.showwarning("Export", "No sample selected.")
            return
        from gui.sample_gui.config import resolve_default_save_root

        sample_dir = resolve_default_save_root() / sample
        sample_dir.mkdir(parents=True, exist_ok=True)
        export_path = sample_dir / f"device_status_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        gui.status_store.save_device_status_excel(export_path)
        messagebox.showinfo("Export Complete", f"Device status exported to:\n{export_path}")
        gui.log_terminal(f"Exported device status to {export_path.name}", "SUCCESS")
