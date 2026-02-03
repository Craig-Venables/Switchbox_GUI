"""
Notes Helpers
=============

Load, save, and manage device/sample notes from notes.json.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import COLOR_ERROR, COLOR_INFO, COLOR_SUCCESS, COLOR_WARNING


def get_sample_name(gui) -> Optional[str]:
    """Get the current sample name (e.g., D104)."""
    sample_name = None
    if hasattr(gui, "sample_gui") and gui.sample_gui:
        sample_name = getattr(gui.sample_gui, "current_device_name", None)
    if not sample_name and hasattr(gui, "sample_name_var"):
        try:
            sample_name = gui.sample_name_var.get().strip()
        except Exception:
            pass
    if not sample_name and hasattr(gui, "sample_gui") and gui.sample_gui:
        sample_type_var = getattr(gui.sample_gui, "sample_type_var", None)
        if sample_type_var and hasattr(sample_type_var, "get"):
            try:
                sample_name = sample_type_var.get()
            except Exception:
                pass
    return sample_name


def get_notes_file_path(gui, sample_name: str) -> Path:
    """Get the path to the notes JSON file for a sample."""
    save_root = Path(getattr(gui, "default_save_root", Path.home() / "Documents" / "Data_folder"))
    return save_root / sample_name / "notes.json"


def load_notes_data(gui, sample_name: str) -> dict:
    """Load the notes JSON file for a sample; return empty dict if not found."""
    notes_path = get_notes_file_path(gui, sample_name)
    if notes_path.exists():
        try:
            with notes_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading notes file: {e}")
            return {}
    return {"sample_name": sample_name, "Sample_Notes": "", "device": {}}


def save_notes_data(gui, sample_name: str, notes_data: dict) -> None:
    """Save the notes JSON file for a sample."""
    notes_path = get_notes_file_path(gui, sample_name)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_data["sample_name"] = sample_name
    if "device" not in notes_data:
        notes_data["device"] = {}
    if "Sample_Notes" not in notes_data:
        notes_data["Sample_Notes"] = ""
    try:
        with notes_path.open("w", encoding="utf-8") as f:
            json.dump(notes_data, f, indent=2)
    except Exception as e:
        print(f"Error saving notes file: {e}")
        raise


def get_previous_devices(gui) -> List[Dict[str, Any]]:
    """Get the previous two devices from the same sample (e.g., if on A2, show A1)."""
    previous_devices = []
    try:
        current_device_id = getattr(gui, "device_section_and_number", None)
        sample_name = get_sample_name(gui)
        if not current_device_id or not sample_name:
            return previous_devices
        device_list = getattr(gui, "device_list", [])
        if not device_list:
            return previous_devices
        current_index = None
        for idx, _ in enumerate(device_list):
            if hasattr(gui, "convert_to_name"):
                if gui.convert_to_name(idx) == current_device_id:
                    current_index = idx
                    break
        if current_index is None:
            return previous_devices
        save_root = Path(getattr(gui, "default_save_root", Path.home() / "Documents" / "Data_folder"))
        sample_folder = save_root / sample_name
        if not sample_folder.exists():
            return previous_devices
        for offset in range(1, 3):
            prev_index = current_index - offset
            if 0 <= prev_index < len(device_list) and hasattr(gui, "convert_to_name"):
                prev_device_id = gui.convert_to_name(prev_index)
                letter = prev_device_id[0] if prev_device_id else "A"
                number = prev_device_id[1:] if len(prev_device_id) > 1 else "1"
                device_folder = sample_folder / letter / number
                info_path = device_folder / "device_info.json"
                entry = {"name": prev_device_id, "folder": device_folder, "last_modified": "", "device_id": prev_device_id}
                if info_path.exists():
                    try:
                        with info_path.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                            entry["last_modified"] = data.get("last_modified", "")
                    except Exception:
                        pass
                previous_devices.append(entry)
    except Exception as e:
        print(f"Error getting previous devices: {e}")
    return previous_devices


def load_notes(builder: Any, gui) -> None:
    """Load device notes from notes.json."""
    if not hasattr(gui, "notes_text"):
        return
    try:
        gui.notes_text.config(undo=False)
        gui.notes_text.delete("1.0", tk.END)
        gui.master.update_idletasks()
    except Exception as e:
        print(f"Error clearing notes: {e}")
    try:
        device_id = getattr(gui, "device_section_and_number", None)
        sample_name = get_sample_name(gui)
        if device_id and sample_name:
            notes_data = load_notes_data(gui, sample_name)
            device_notes = notes_data.get("device", {}).get(device_id, "")
            if device_notes:
                gui.notes_text.insert("1.0", device_notes)
            gui.notes_status_label.config(text=f"Device: {device_id} (Sample: {sample_name})", fg=COLOR_INFO)
        elif device_id:
            gui.notes_status_label.config(text=f"Device: {device_id} (No sample name)", fg=COLOR_WARNING)
        else:
            gui.notes_status_label.config(text="No device selected", fg=COLOR_WARNING)
    except Exception as e:
        print(f"Error loading notes: {e}")
        import traceback

        traceback.print_exc()
        gui.notes_status_label.config(text=f"Error loading notes: {e}", fg=COLOR_ERROR)
    finally:
        try:
            gui.notes_text.config(undo=True)
            gui.notes_text.edit_reset()
        except Exception:
            pass


def save_notes(builder: Any, gui) -> None:
    """Save device notes to notes.json."""
    notes_content = gui.notes_text.get("1.0", tk.END).strip()
    try:
        device_id = getattr(gui, "device_section_and_number", None)
        sample_name = get_sample_name(gui)
        if not device_id or not sample_name:
            return
        notes_data = load_notes_data(gui, sample_name)
        if "device" not in notes_data:
            notes_data["device"] = {}
        notes_data["device"][device_id] = notes_content
        save_notes_data(gui, sample_name, notes_data)
        gui.notes_status_label.config(text=f"Device notes saved: {device_id}", fg=COLOR_SUCCESS)
        gui.master.after(3000, lambda: gui.notes_status_label.config(text=""))
    except Exception as e:
        print(f"Error saving device notes: {e}")
        import traceback

        traceback.print_exc()
        gui.notes_status_label.config(text=f"Error: {e}", fg=COLOR_ERROR)


def load_previous_device_notes(builder: Any, gui, device_info: Dict[str, Any], text_widget: tk.Text) -> None:
    """Load notes for a previous device from notes.json."""
    try:
        text_widget.config(undo=False)
        text_widget.delete("1.0", tk.END)
        device_id = device_info.get("name", "")
        sample_name = get_sample_name(gui)
        if device_id and sample_name:
            notes_data = load_notes_data(gui, sample_name)
            device_notes = notes_data.get("device", {}).get(device_id, "")
            if device_notes:
                text_widget.insert("1.0", device_notes)
        text_widget.config(undo=True)
        text_widget.edit_reset()
    except Exception as e:
        print(f"Error loading previous device notes: {e}")
        import traceback

        traceback.print_exc()
        try:
            text_widget.config(undo=True)
        except Exception:
            pass


def save_previous_device_notes(builder: Any, gui, device_info: Dict[str, Any], text_widget: tk.Text) -> None:
    """Save notes for a previous device to notes.json."""
    try:
        device_id = device_info.get("name", "")
        sample_name = get_sample_name(gui)
        if not device_id or not sample_name:
            return
        notes_content = text_widget.get("1.0", tk.END).strip()
        notes_data = load_notes_data(gui, sample_name)
        if "device" not in notes_data:
            notes_data["device"] = {}
        notes_data["device"][device_id] = notes_content
        save_notes_data(gui, sample_name, notes_data)
    except Exception as e:
        print(f"Error saving previous device notes: {e}")
        import traceback

        traceback.print_exc()


def load_sample_notes(builder: Any, gui) -> None:
    """Load sample notes from notes.json."""
    if not hasattr(gui, "sample_notes_text"):
        return
    gui.sample_notes_text.config(undo=False)
    gui.sample_notes_text.delete("1.0", tk.END)
    try:
        sample_name = get_sample_name(gui)
        if sample_name:
            notes_data = load_notes_data(gui, sample_name)
            sample_notes = notes_data.get("Sample_Notes", "")
            if sample_notes:
                gui.sample_notes_text.insert("1.0", sample_notes)
    except Exception as e:
        print(f"Error loading sample notes: {e}")
        import traceback

        traceback.print_exc()
    finally:
        try:
            gui.sample_notes_text.config(undo=True)
            gui.sample_notes_text.edit_reset()
        except Exception:
            pass


def save_sample_notes(builder: Any, gui) -> None:
    """Save sample notes to notes.json."""
    if not hasattr(gui, "sample_notes_text"):
        return
    notes_content = gui.sample_notes_text.get("1.0", tk.END).strip()
    try:
        sample_name = get_sample_name(gui)
        if not sample_name:
            return
        notes_data = load_notes_data(gui, sample_name)
        notes_data["Sample_Notes"] = notes_content
        save_notes_data(gui, sample_name, notes_data)
    except Exception as e:
        print(f"Error saving sample notes: {e}")
        import traceback

        traceback.print_exc()


def save_all_notes(builder: Any, gui) -> None:
    """Save all notes (device, previous device, and sample)."""
    save_notes(builder, gui)
    if hasattr(gui, "prev_device1_text") and gui.prev_device1_text:
        previous_devices = get_previous_devices(gui)
        if previous_devices:
            save_previous_device_notes(builder, gui, previous_devices[0], gui.prev_device1_text)
    save_sample_notes(builder, gui)
    if hasattr(gui, "notes_status_label"):
        gui.notes_status_label.config(text="All notes saved!", fg=COLOR_SUCCESS)
        gui.master.after(3000, lambda: gui.notes_status_label.config(text=""))


def auto_save_notes(builder: Any, gui) -> None:
    """Auto-save device notes without showing dialog."""
    try:
        save_notes(builder, gui)
    except Exception as e:
        print(f"Auto-save notes error: {e}")


def mark_notes_changed(gui) -> None:
    """Mark that notes have been changed (for auto-save detection)."""
    if hasattr(gui, "notes_text"):
        gui.notes_changed = True


def on_notes_key_release(builder: Any, gui) -> None:
    """Handle key release – mark changed and auto-save (debounced)."""
    mark_notes_changed(gui)
    if hasattr(gui, "_notes_save_timer"):
        gui.master.after_cancel(gui._notes_save_timer)
    gui._notes_save_timer = gui.master.after(500, lambda: auto_save_notes(builder, gui))


def mark_prev_device1_changed(gui) -> None:
    """Mark that previous device notes have been changed."""
    if hasattr(gui, "prev_device1_text") and gui.prev_device1_text:
        gui.prev_device1_changed = True


def mark_sample_notes_changed(gui) -> None:
    """Mark that sample notes have been changed."""
    if hasattr(gui, "sample_notes_text"):
        gui.sample_notes_changed = True


def insert_datetime(gui) -> None:
    """Insert current date and time at cursor position."""
    from datetime import datetime

    gui.notes_text.insert(tk.INSERT, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def insert_measurement_details(builder: Any, gui) -> None:
    """Insert current measurement details from Measurement GUI or TSP Testing GUI."""
    details = []
    tsp_details = builder._get_tsp_testing_details(gui) if hasattr(builder, "_get_tsp_testing_details") else []
    if tsp_details:
        details.append("=== Pulse Testing Details ===")
        details.extend(tsp_details)
        details.append("")
    meas_details = builder._get_measurement_gui_details(gui) if hasattr(builder, "_get_measurement_gui_details") else []
    if meas_details:
        if tsp_details:
            details.append("=== Measurement GUI Details ===")
        details.extend(meas_details)
    if not details:
        details.append("No active measurement parameters found.")
    gui.notes_text.insert(tk.INSERT, "\n".join(details) + "\n\n")


def toggle_bold(gui) -> None:
    """Toggle bold formatting for selected text or at cursor."""
    try:
        sel_start = gui.notes_text.index(tk.SEL_FIRST) if gui.notes_text.tag_ranges(tk.SEL) else gui.notes_text.index(tk.INSERT)
        sel_end = gui.notes_text.index(tk.SEL_LAST) if gui.notes_text.tag_ranges(tk.SEL) else gui.notes_text.index(tk.INSERT + " wordend")
        tags = gui.notes_text.tag_names(sel_start)
        if "bold" in tags:
            gui.notes_text.tag_remove("bold", sel_start, sel_end)
        else:
            gui.notes_text.tag_add("bold", sel_start, sel_end)
            gui.notes_text.tag_config("bold", font=("Consolas", 10, "bold"))
    except Exception:
        gui.notes_text.tag_add("bold", tk.INSERT)
        gui.notes_text.tag_config("bold", font=("Consolas", 10, "bold"))


def toggle_italic(gui) -> None:
    """Toggle italic formatting for selected text or at cursor."""
    try:
        sel_start = gui.notes_text.index(tk.SEL_FIRST) if gui.notes_text.tag_ranges(tk.SEL) else gui.notes_text.index(tk.INSERT)
        sel_end = gui.notes_text.index(tk.SEL_LAST) if gui.notes_text.tag_ranges(tk.SEL) else gui.notes_text.index(tk.INSERT + " wordend")
        tags = gui.notes_text.tag_names(sel_start)
        if "italic" in tags:
            gui.notes_text.tag_remove("italic", sel_start, sel_end)
        else:
            gui.notes_text.tag_add("italic", sel_start, sel_end)
            gui.notes_text.tag_config("italic", font=("Consolas", 10, "italic"))
    except Exception:
        gui.notes_text.tag_add("italic", tk.INSERT)
        gui.notes_text.tag_config("italic", font=("Consolas", 10, "italic"))


def setup_notes_keyboard_shortcuts(builder: Any, gui, tab: tk.Frame) -> None:
    """Setup keyboard shortcuts for Notes tab: Ctrl+S, Ctrl+Z, Ctrl+Y, Ctrl+D, Ctrl+B, Ctrl+I."""

    def get_focused_text_widget():
        focused = gui.master.focus_get()
        if focused == gui.notes_text:
            return gui.notes_text
        if hasattr(gui, "prev_device1_text") and gui.prev_device1_text and focused == gui.prev_device1_text:
            return gui.prev_device1_text
        if hasattr(gui, "sample_notes_text") and gui.sample_notes_text and focused == gui.sample_notes_text:
            return gui.sample_notes_text
        return None

    def on_save(event):
        text_widget = get_focused_text_widget()
        if text_widget == gui.notes_text:
            save_notes(builder, gui)
            if hasattr(gui, "notes_status_label"):
                original_text = gui.notes_status_label.cget("text")
                gui.notes_status_label.config(text="✓ Saved!", fg=COLOR_SUCCESS)
                gui.master.after(2000, lambda: gui.notes_status_label.config(text=original_text, fg=COLOR_INFO))
        elif text_widget == gui.prev_device1_text:
            previous_devices = get_previous_devices(gui)
            if previous_devices:
                save_previous_device_notes(builder, gui, previous_devices[0], gui.prev_device1_text)
        elif hasattr(gui, "sample_notes_text") and text_widget == gui.sample_notes_text:
            save_sample_notes(builder, gui)
        return "break"

    def on_undo(event):
        text_widget = get_focused_text_widget()
        if text_widget:
            try:
                text_widget.edit_undo()
            except tk.TclError:
                pass
        return "break"

    def on_redo(event):
        text_widget = get_focused_text_widget()
        if text_widget:
            try:
                text_widget.edit_redo()
            except tk.TclError:
                pass
        return "break"

    def on_datetime(event):
        insert_datetime(gui)
        return "break"

    gui.notes_text.bind("<Control-s>", on_save)
    gui.notes_text.bind("<Control-S>", on_save)
    gui.notes_text.bind("<Control-d>", on_datetime)
    gui.notes_text.bind("<Control-D>", on_datetime)
    gui.notes_text.bind("<Control-z>", on_undo)
    gui.notes_text.bind("<Control-Z>", on_undo)
    gui.notes_text.bind("<Control-y>", on_redo)
    gui.notes_text.bind("<Control-Y>", on_redo)
    def on_bold(e):
        toggle_bold(gui)
        return "break"

    def on_italic(e):
        toggle_italic(gui)
        return "break"

    gui.notes_text.bind("<Control-b>", on_bold)
    gui.notes_text.bind("<Control-B>", on_bold)
    gui.notes_text.bind("<Control-i>", on_italic)
    gui.notes_text.bind("<Control-I>", on_italic)

    if hasattr(gui, "prev_device1_text") and gui.prev_device1_text:
        gui.prev_device1_text.bind("<Control-s>", on_save)
        gui.prev_device1_text.bind("<Control-S>", on_save)
        gui.prev_device1_text.bind("<Control-z>", on_undo)
        gui.prev_device1_text.bind("<Control-Z>", on_undo)
        gui.prev_device1_text.bind("<Control-y>", on_redo)
        gui.prev_device1_text.bind("<Control-Y>", on_redo)

    if hasattr(gui, "sample_notes_text") and gui.sample_notes_text:
        gui.sample_notes_text.bind("<Control-s>", on_save)
        gui.sample_notes_text.bind("<Control-S>", on_save)
        gui.sample_notes_text.bind("<Control-z>", on_undo)
        gui.sample_notes_text.bind("<Control-Z>", on_undo)
        gui.sample_notes_text.bind("<Control-y>", on_redo)
        gui.sample_notes_text.bind("<Control-Y>", on_redo)


def start_auto_save_timer(builder: Any, gui) -> None:
    """Start the periodic auto-save timer (every 10 seconds)."""

    def check_and_save():
        try:
            if hasattr(gui, "notes_text") and hasattr(gui, "notes_changed"):
                current_content = gui.notes_text.get("1.0", tk.END)
                if hasattr(gui, "notes_last_saved") and current_content != gui.notes_last_saved:
                    auto_save_notes(builder, gui)
                    gui.notes_last_saved = current_content
                    gui.notes_changed = False
            if hasattr(gui, "prev_device1_text") and gui.prev_device1_text:
                current_content = gui.prev_device1_text.get("1.0", tk.END)
                if hasattr(gui, "prev_device1_last_saved") and current_content != gui.prev_device1_last_saved:
                    previous_devices = get_previous_devices(gui)
                    if previous_devices:
                        save_previous_device_notes(builder, gui, previous_devices[0], gui.prev_device1_text)
                        gui.prev_device1_last_saved = current_content
            if hasattr(gui, "sample_notes_text") and gui.sample_notes_text:
                current_content = gui.sample_notes_text.get("1.0", tk.END)
                if hasattr(gui, "sample_notes_last_saved") and current_content != gui.sample_notes_last_saved:
                    save_sample_notes(builder, gui)
                    gui.sample_notes_last_saved = current_content
                    gui.sample_notes_changed = False
        except Exception as e:
            print(f"Auto-save check error: {e}")
        if hasattr(gui, "master") and gui.master.winfo_exists():
            gui.master.after(10000, check_and_save)

    if hasattr(gui, "master"):
        gui.master.after(10000, check_and_save)


def start_device_change_polling(builder: Any, gui) -> None:
    """Poll for device changes and auto-reload device notes."""

    def check_device_change():
        try:
            current_device_id = getattr(gui, "device_section_and_number", None)
            if current_device_id:
                current_device_id = str(current_device_id).strip() or None
            if not hasattr(gui, "_last_polled_device_id"):
                gui._last_polled_device_id = current_device_id
            last_polled = gui._last_polled_device_id
            if last_polled:
                last_polled = str(last_polled).strip() or None
            device_changed = (current_device_id and last_polled and current_device_id != last_polled) or (
                current_device_id and not last_polled
            ) or (not current_device_id and last_polled)
            if device_changed:
                if last_polled and hasattr(gui, "notes_text"):
                    old_backup = gui.device_section_and_number
                    gui.device_section_and_number = last_polled
                    try:
                        save_notes(builder, gui)
                    finally:
                        gui.device_section_and_number = current_device_id
                    gui.master.update_idletasks()
                gui._last_polled_device_id = current_device_id
                if hasattr(gui, "notes_text"):
                    gui.notes_text.config(undo=False)
                    for _ in range(3):
                        gui.notes_text.delete("1.0", tk.END)
                        gui.master.update_idletasks()
                    gui.notes_text.delete("1.0", tk.END)
                    gui.master.update_idletasks()
                    gui.master.update()
                    load_notes(builder, gui)
                    gui.notes_last_saved = gui.notes_text.get("1.0", tk.END)
                    gui.notes_changed = False
                previous_devices = get_previous_devices(gui)
                if previous_devices and hasattr(gui, "prev_device1_text") and gui.prev_device1_text:
                    load_previous_device_notes(builder, gui, previous_devices[0], gui.prev_device1_text)
                    gui.prev_device1_last_saved = gui.prev_device1_text.get("1.0", tk.END)
                    prev1_frame = gui.prev_device1_text.master
                    if isinstance(prev1_frame, tk.LabelFrame):
                        prev1_frame.config(text=f"Previous Device: {previous_devices[0]['name']}")
                if hasattr(gui, "notes_status_label") and current_device_id:
                    gui.notes_status_label.config(text=f"Switched to device: {current_device_id}", fg=COLOR_INFO)
                    gui.master.after(3000, lambda: gui.notes_status_label.config(text=""))
        except Exception as e:
            print(f"Error polling device changes: {e}")
            import traceback

            traceback.print_exc()
        if hasattr(gui, "master") and gui.master.winfo_exists():
            gui.master.after(500, check_device_change)

    if hasattr(gui, "master"):
        gui.master.after(500, check_device_change)


def start_sample_change_polling(builder: Any, gui) -> None:
    """Poll for sample name changes and auto-reload sample notes."""

    def check_sample_change():
        try:
            current_sample_name = get_sample_name(gui) or None
            if not hasattr(gui, "_last_polled_sample_name"):
                gui._last_polled_sample_name = current_sample_name
            if current_sample_name != gui._last_polled_sample_name:
                if gui._last_polled_sample_name:
                    save_sample_notes(builder, gui)
                    gui.master.update_idletasks()
                gui._last_polled_sample_name = current_sample_name
                if hasattr(gui, "sample_notes_text"):
                    load_sample_notes(builder, gui)
                    gui.sample_notes_last_saved = gui.sample_notes_text.get("1.0", tk.END)
                    gui.sample_notes_changed = False
                sample_label = f"Sample Notes: {current_sample_name}" if current_sample_name else "Sample Notes"
                if hasattr(gui, "sample_notes_frame"):
                    gui.sample_notes_frame.config(text=sample_label)
                if hasattr(gui, "notes_status_label") and current_sample_name:
                    gui.notes_status_label.config(text=f"Switched to sample: {current_sample_name}", fg=COLOR_INFO)
                    gui.master.after(3000, lambda: gui.notes_status_label.config(text=""))
        except Exception as e:
            print(f"Error polling sample changes: {e}")
        if hasattr(gui, "master") and gui.master.winfo_exists():
            gui.master.after(1000, check_sample_change)

    if hasattr(gui, "master") and hasattr(gui, "sample_notes_text"):
        gui.master.after(1000, check_sample_change)
