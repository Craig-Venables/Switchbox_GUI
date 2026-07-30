"""Reclassify saved measurements with current classification weights."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, List, Optional, Tuple

from analysis.reclassify_sample import (
    ReclassifyStats,
    count_measurement_files,
    discover_sample_dirs,
    get_weights_version,
    reclassify_sample,
)
from gui.sample_gui.config import resolve_default_save_root

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI


class ReclassifyController:
    """Run batch reclassification from Sample GUI."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui
        self._running = False
        self._idle_after_id: Optional[str] = None

    def update_menu_labels(self) -> None:
        """Refresh menubutton labels for current sample name and sample count."""
        menu = getattr(self.gui, "reclassify_menu", None)
        if menu is None:
            return
        menu.delete(0, "end")

        sample_name = getattr(self.gui, "current_device_name", None) or ""
        if sample_name:
            menu.add_command(
                label=f"Current sample ({sample_name})",
                command=self.reclassify_current,
            )
        else:
            menu.add_command(
                label="Current sample (set device first)",
                state=tk.DISABLED,
            )

        save_root = resolve_default_save_root()
        sample_dirs = discover_sample_dirs(save_root)
        count = len(sample_dirs)
        if count:
            menu.add_command(
                label=f"All samples ({count} in Data_folder)",
                command=self.reclassify_all,
            )
        else:
            menu.add_command(
                label="All samples (none found)",
                state=tk.DISABLED,
            )

    def reclassify_current(self) -> None:
        sample_name = getattr(self.gui, "current_device_name", None) or ""
        if not sample_name:
            messagebox.showwarning(
                "No Sample",
                "Set a device name (e.g. D104) in the Device Manager tab first.",
            )
            return
        sample_dir = str(resolve_default_save_root() / sample_name)
        self._confirm_and_run([(sample_name, sample_dir)])

    def reclassify_all(self) -> None:
        save_root = resolve_default_save_root()
        targets = discover_sample_dirs(save_root)
        if not targets:
            messagebox.showinfo(
                "No Samples",
                f"No sample folders with measurement data were found in:\n{save_root}",
            )
            return
        self._confirm_and_run(targets)

    def _confirm_and_run(self, targets: List[Tuple[str, str]]) -> None:
        if self._running:
            messagebox.showinfo("Busy", "Reclassification is already running.")
            return

        weights_ver = get_weights_version()
        total_files = sum(count_measurement_files(path, name) for name, path in targets)
        if total_files == 0:
            messagebox.showinfo(
                "No Files",
                "No measurement files were found in the selected sample folder(s).",
            )
            return

        if len(targets) == 1:
            name, _path = targets[0]
            prompt = (
                f"Reclassify {total_files} measurement file(s) in:\n{name}\n\n"
                f"Using classification weights v{weights_ver}.\n"
                "Progress will appear below the device map.\n\n"
                "Continue?"
            )
        else:
            names_preview = ", ".join(t[0] for t in targets[:8])
            if len(targets) > 8:
                names_preview += f", … (+{len(targets) - 8} more)"
            prompt = (
                f"Reclassify {total_files} file(s) across {len(targets)} samples:\n"
                f"{names_preview}\n\n"
                f"Using classification weights v{weights_ver}.\n"
                "This may take several minutes.\n\n"
                "Continue?"
            )

        if not messagebox.askyesno("Reclassify Classifications", prompt):
            return

        self._running = True
        self._cancel_idle_reset()
        self._set_controls_state(tk.DISABLED)
        self._show_progress(0, total_files)
        self._set_status(
            f"Starting reclassification — 0 / {total_files} files (weights v{weights_ver})…",
            busy=True,
        )
        self.gui.log_terminal(
            f"Starting reclassification: {total_files} file(s), "
            f"{len(targets)} sample(s), weights v{weights_ver}",
            "INFO",
        )

        def worker() -> None:
            combined = ReclassifyStats()
            file_offset = 0
            try:
                for sample_index, (sample_name, sample_dir) in enumerate(targets, start=1):
                    sample_file_count = count_measurement_files(sample_dir, sample_name)

                    def progress_fn(
                        done: int,
                        _total: int,
                        detail: str,
                        _offset: int = file_offset,
                        _global_total: int = total_files,
                        _si: int = sample_index,
                        _st: int = len(targets),
                        _sn: str = sample_name,
                    ) -> None:
                        global_done = _offset + done
                        pct = int(100 * global_done / _global_total) if _global_total else 0
                        status = (
                            f"Reclassifying sample {_si}/{_st} ({_sn}) — "
                            f"file {global_done} / {_global_total} ({pct}%)"
                        )
                        self._post_ui(global_done, _global_total, status, detail)

                    self._post_ui(
                        file_offset,
                        total_files,
                        f"Reclassifying sample {sample_index}/{len(targets)}: {sample_name}…",
                        "Scanning files…",
                    )

                    stats = reclassify_sample(
                        sample_dir,
                        sample_name,
                        progress_fn=progress_fn,
                    )
                    combined.merge(stats)
                    file_offset += sample_file_count

                self.gui.root.after(0, lambda: self._on_complete(combined, len(targets), total_files))
            except Exception as exc:
                self.gui.root.after(0, lambda: self._on_error(str(exc)))

        threading.Thread(target=worker, daemon=True, name="SampleReclassify").start()

    def _post_ui(self, done: int, total: int, status: str, detail: str = "") -> None:
        def apply() -> None:
            text = status
            if detail and not status.endswith(detail):
                text = f"{status} — {detail}"
            self._set_status(text, busy=True)
            self._show_progress(done, total)

        self.gui.root.after(0, apply)

    def _set_status(self, text: str, *, busy: bool = False) -> None:
        label = getattr(self.gui, "classification_action_status", None)
        if label is None:
            return
        label.config(
            text=text,
            fg="#1565C0" if busy else "#555555",
            font=("Segoe UI", 9, "bold" if busy else "normal"),
        )

    def _show_progress(self, value: int, maximum: int) -> None:
        bar = getattr(self.gui, "classification_progress", None)
        if bar is None:
            return
        if maximum <= 0:
            bar.grid_remove()
            return
        bar.config(maximum=maximum, value=min(value, maximum))
        bar.grid()

    def _hide_progress(self) -> None:
        bar = getattr(self.gui, "classification_progress", None)
        if bar is not None:
            bar.grid_remove()
            bar.config(value=0)

    def _set_controls_state(self, state: str) -> None:
        for attr in ("reclassify_menubutton", "classification_refresh_button"):
            widget = getattr(self.gui, attr, None)
            if widget is not None:
                try:
                    widget.config(state=state)
                except tk.TclError:
                    pass

    def _schedule_idle_status(self, message: str, delay_ms: int = 8000) -> None:
        self._cancel_idle_reset()

        def reset() -> None:
            self._idle_after_id = None
            weights_ver = get_weights_version()
            self._set_status(f"Ready · classification weights v{weights_ver}")

        self._idle_after_id = self.gui.root.after(delay_ms, reset)
        self._set_status(message)

    def _cancel_idle_reset(self) -> None:
        if self._idle_after_id is not None:
            try:
                self.gui.root.after_cancel(self._idle_after_id)
            except tk.TclError:
                pass
            self._idle_after_id = None

    def _on_complete(self, stats: ReclassifyStats, sample_count: int, total_files: int) -> None:
        self._running = False
        self._hide_progress()
        self._set_controls_state(tk.NORMAL)

        if hasattr(self.gui, "classification_overlay"):
            self.gui.classification_overlay.refresh()

        done_msg = (
            f"Done — {stats.reclassified_count}/{total_files} files updated, "
            f"{stats.type_changes} type change(s)"
        )
        if stats.errors:
            done_msg += f", {len(stats.errors)} error(s)"

        self.gui.log_terminal(done_msg, "SUCCESS")
        self._schedule_idle_status(done_msg)

        summary = (
            f"Reclassification complete.\n\n"
            f"Samples processed: {sample_count}\n"
            f"Files processed: {stats.total_files}\n"
            f"Successfully updated: {stats.reclassified_count}\n"
            f"Type changes: {stats.type_changes}"
        )
        if stats.errors:
            summary += f"\n\nErrors: {len(stats.errors)}\n"
            summary += "\n".join(stats.errors[:8])
            if len(stats.errors) > 8:
                summary += f"\n… and {len(stats.errors) - 8} more"

        messagebox.showinfo("Reclassification Complete", summary)

    def _on_error(self, message: str) -> None:
        self._running = False
        self._hide_progress()
        self._set_controls_state(tk.NORMAL)
        self.gui.log_terminal(f"Reclassification failed: {message}", "ERROR")
        self._schedule_idle_status(f"Failed — {message[:80]}")
        messagebox.showerror("Reclassification Error", message)
