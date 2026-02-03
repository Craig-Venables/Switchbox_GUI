"""
Custom Sweeps Logic
===================

Load/save and manage custom sweep methods and combinations.
Extracted from main.py for maintainability.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from tkinter import messagebox

# Project root (gui/measurement_gui/ -> gui -> root)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_custom_sweeps(path: str) -> Dict[str, Dict[str, Any]]:
    """Load custom measurement definitions from JSON (backward compatible)."""
    file_path = Path(path)
    if not file_path.exists():
        print(f"[Custom Sweeps] Config not found at {file_path}, using defaults.")
        return {}
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        print(f"[Custom Sweeps] Failed to load {file_path}: {exc}")
        return {}
    if not isinstance(data, dict):
        print(f"[Custom Sweeps] Invalid format in {file_path}; expected object at top level.")
        return {}
    return data


def load_custom_sweep_methods(gui: Any) -> None:
    """Load available custom sweep methods from Custom_Sweeps.json"""
    try:
        custom_sweeps_path = _PROJECT_ROOT / "Json_Files" / "Custom_Sweeps.json"
        if not custom_sweeps_path.exists():
            if hasattr(gui, "custom_sweep_status_label"):
                gui.custom_sweep_status_label.config(
                    text="✗ Custom_Sweeps.json not found", fg="#F44336"
                )
            messagebox.showerror(
                "File Not Found",
                f"Custom_Sweeps.json not found at:\n{custom_sweeps_path}",
            )
            return

        custom_sweeps = load_custom_sweeps(str(custom_sweeps_path))

        # Build list of method names (identifier or code_name)
        method_list = []
        for identifier, method_data in custom_sweeps.items():
            code_name = method_data.get("code_name", "")
            if code_name:
                display_name = f"{identifier} ({code_name})"
            else:
                display_name = identifier
            method_list.append(display_name)

        if not method_list:
            if hasattr(gui, "custom_sweep_status_label"):
                gui.custom_sweep_status_label.config(
                    text="✗ No methods found in file", fg="#F44336"
                )
            return

        # Update combobox
        if hasattr(gui, "custom_sweep_method_combo"):
            import tkinter as tk

            gui.custom_sweep_method_combo["values"] = method_list
            if method_list:
                gui.custom_sweep_method_combo.current(0)
                on_custom_sweep_method_selected(gui)

        # Store the mapping for later use
        gui.custom_sweeps_data = custom_sweeps
        gui.custom_sweeps_method_map = {}
        for identifier, method_data in custom_sweeps.items():
            code_name = method_data.get("code_name", "")
            display_name = (
                f"{identifier} ({code_name})" if code_name else identifier
            )
            gui.custom_sweeps_method_map[display_name] = {
                "identifier": identifier,
                "code_name": code_name,
                "data": method_data,
            }

        if hasattr(gui, "custom_sweep_status_label"):
            gui.custom_sweep_status_label.config(
                text=f"✓ Loaded {len(method_list)} method(s)", fg="#4CAF50"
            )

    except Exception as e:
        error_msg = f"Error loading custom sweep methods: {e}"
        print(f"[CUSTOM SWEEPS] {error_msg}")
        if hasattr(gui, "custom_sweep_status_label"):
            gui.custom_sweep_status_label.config(
                text=f"✗ {error_msg}", fg="#F44336"
            )
        messagebox.showerror("Error", error_msg)


def on_custom_sweep_method_selected(gui: Any) -> None:
    """Handle custom sweep method selection"""
    try:
        if not hasattr(gui, "custom_sweep_method_var") or not gui.custom_sweep_method_var.get():
            return

        load_custom_sweep_combinations(gui)

    except Exception as e:
        print(f"[CUSTOM SWEEPS] Error handling method selection: {e}")


def load_custom_sweep_combinations(gui: Any) -> None:
    """Load sweep combinations from test_configurations.json for selected method"""
    try:
        import tkinter as tk

        if not hasattr(gui, "custom_sweep_method_var") or not gui.custom_sweep_method_var.get():
            if hasattr(gui, "custom_sweep_combinations_listbox"):
                gui.custom_sweep_combinations_listbox.delete(0, tk.END)
            return

        selected_display = gui.custom_sweep_method_var.get()
        if not hasattr(gui, "custom_sweeps_method_map") or selected_display not in gui.custom_sweeps_method_map:
            return

        method_info = gui.custom_sweeps_method_map[selected_display]
        code_name = method_info["code_name"]

        test_config_path = _PROJECT_ROOT / "Json_Files" / "test_configurations.json"
        if not test_config_path.exists():
            if hasattr(gui, "custom_sweep_status_label"):
                gui.custom_sweep_status_label.config(
                    text="✗ test_configurations.json not found", fg="#F44336"
                )
            return

        with test_config_path.open("r", encoding="utf-8") as f:
            test_configs = json.load(f)

        if code_name not in test_configs:
            if hasattr(gui, "custom_sweep_combinations_listbox"):
                gui.custom_sweep_combinations_listbox.delete(0, tk.END)
                gui.custom_sweep_combinations_listbox.insert(
                    0, f"No combinations found for {code_name}"
                )
            if hasattr(gui, "custom_sweep_status_label"):
                gui.custom_sweep_status_label.config(
                    text=f"✗ No combinations for {code_name}", fg="#F44336"
                )
            return

        config = test_configs[code_name]
        combinations = config.get("sweep_combinations", [])

        gui.custom_sweep_combinations = [combo.copy() for combo in combinations]

        if hasattr(gui, "custom_sweep_combinations_listbox"):
            gui.custom_sweep_combinations_listbox.delete(0, tk.END)
            for combo in gui.custom_sweep_combinations:
                sweeps_str = ", ".join(map(str, combo.get("sweeps", [])))
                title = combo.get("title", "Untitled")
                display_text = f"{title} [Sweeps: {sweeps_str}]"
                gui.custom_sweep_combinations_listbox.insert(tk.END, display_text)

        if hasattr(gui, "custom_sweep_status_label"):
            gui.custom_sweep_status_label.config(
                text=f"✓ Loaded {len(combinations)} combination(s) for {code_name}",
                fg="#4CAF50",
            )

    except Exception as e:
        error_msg = f"Error loading combinations: {e}"
        print(f"[CUSTOM SWEEPS] {error_msg}")
        if hasattr(gui, "custom_sweep_status_label"):
            gui.custom_sweep_status_label.config(
                text=f"✗ {error_msg}", fg="#F44336"
            )


def add_sweep_combination(gui: Any) -> None:
    """Add a new sweep combination to the current list."""
    try:
        import tkinter as tk

        if not hasattr(gui, "custom_sweep_method_var") or not gui.custom_sweep_method_var.get():
            messagebox.showwarning(
                "No Method Selected", "Please select a method first"
            )
            return

        sweeps_str = gui.new_combination_sweeps_var.get().strip()
        if not sweeps_str:
            messagebox.showwarning(
                "Invalid Input",
                "Please enter sweep numbers (e.g., 1,2 or 1,2,3)",
            )
            return

        try:
            sweeps = [int(x.strip()) for x in sweeps_str.split(",")]
            if not sweeps:
                raise ValueError("No valid sweep numbers")
        except ValueError as e:
            messagebox.showerror(
                "Invalid Format",
                f"Invalid sweep numbers format. Use comma-separated numbers.\nError: {e}",
            )
            return

        title = gui.new_combination_title_var.get().strip()
        if not title:
            title = f"Combined sweeps {sweeps_str}"

        new_combo = {"sweeps": sweeps, "title": title}

        if not hasattr(gui, "custom_sweep_combinations"):
            gui.custom_sweep_combinations = []

        gui.custom_sweep_combinations.append(new_combo)

        if hasattr(gui, "custom_sweep_combinations_listbox"):
            sweeps_str_display = ", ".join(map(str, sweeps))
            display_text = f"{title} [Sweeps: {sweeps_str_display}]"
            gui.custom_sweep_combinations_listbox.insert(tk.END, display_text)

        gui.new_combination_sweeps_var.set("")
        gui.new_combination_title_var.set("")

        if hasattr(gui, "custom_sweep_status_label"):
            gui.custom_sweep_status_label.config(
                text=f"✓ Added combination: {title}",
                fg="#4CAF50",
            )

        print(f"[CUSTOM SWEEPS] Added combination: {title} - Sweeps: {sweeps}")

    except Exception as e:
        error_msg = f"Error adding combination: {e}"
        print(f"[CUSTOM SWEEPS] {error_msg}")
        messagebox.showerror("Error", error_msg)
        if hasattr(gui, "custom_sweep_status_label"):
            gui.custom_sweep_status_label.config(
                text=f"✗ {error_msg}", fg="#F44336"
            )


def edit_sweep_combination(gui: Any) -> None:
    """Edit the selected sweep combination."""
    try:
        if not hasattr(gui, "custom_sweep_combinations_listbox"):
            return

        selection = gui.custom_sweep_combinations_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a combination to edit"
            )
            return

        idx = selection[0]

        if not hasattr(gui, "custom_sweep_combinations") or idx >= len(
            gui.custom_sweep_combinations
        ):
            messagebox.showerror("Error", "Invalid selection")
            return

        combo = gui.custom_sweep_combinations[idx]

        sweeps_str = ", ".join(map(str, combo.get("sweeps", [])))
        gui.new_combination_sweeps_var.set(sweeps_str)
        gui.new_combination_title_var.set(combo.get("title", ""))

        delete_sweep_combination(gui, silent=True, index=idx)

        messagebox.showinfo(
            "Edit Mode",
            "Combination removed from list.\n"
            "Modify the values above and click 'Add Combination' to save changes.",
        )

    except Exception as e:
        error_msg = f"Error editing combination: {e}"
        print(f"[CUSTOM SWEEPS] {error_msg}")
        messagebox.showerror("Error", error_msg)


def delete_sweep_combination(
    gui: Any, silent: bool = False, index: int = None
) -> None:
    """Delete the selected sweep combination."""
    try:
        if not hasattr(gui, "custom_sweep_combinations_listbox"):
            return

        if index is None:
            selection = gui.custom_sweep_combinations_listbox.curselection()
            if not selection:
                if not silent:
                    messagebox.showwarning(
                        "No Selection",
                        "Please select a combination to delete",
                    )
                return
            idx = selection[0]
        else:
            idx = index

        if not hasattr(gui, "custom_sweep_combinations") or idx >= len(
            gui.custom_sweep_combinations
        ):
            if not silent:
                messagebox.showerror("Error", "Invalid selection")
            return

        if not silent:
            combo = gui.custom_sweep_combinations[idx]
            title = combo.get("title", "Untitled")
            if not messagebox.askyesno(
                "Confirm Delete", f"Delete combination: {title}?"
            ):
                return

        gui.custom_sweep_combinations.pop(idx)
        gui.custom_sweep_combinations_listbox.delete(idx)

        if hasattr(gui, "custom_sweep_status_label") and not silent:
            gui.custom_sweep_status_label.config(
                text="✓ Combination deleted",
                fg="#4CAF50",
            )

        print(f"[CUSTOM SWEEPS] Deleted combination at index {idx}")

    except Exception as e:
        error_msg = f"Error deleting combination: {e}"
        print(f"[CUSTOM SWEEPS] {error_msg}")
        if not silent:
            messagebox.showerror("Error", error_msg)


def save_sweep_combinations_to_json(gui: Any) -> None:
    """Save current sweep combinations to test_configurations.json"""
    try:
        if not hasattr(gui, "custom_sweep_method_var") or not gui.custom_sweep_method_var.get():
            messagebox.showwarning(
                "No Method Selected", "Please select a method first"
            )
            return

        if not hasattr(gui, "custom_sweep_combinations") or not gui.custom_sweep_combinations:
            messagebox.showwarning(
                "No Combinations",
                "No combinations to save. Add some combinations first.",
            )
            return

        selected_display = gui.custom_sweep_method_var.get()
        if not hasattr(gui, "custom_sweeps_method_map") or selected_display not in gui.custom_sweeps_method_map:
            messagebox.showerror("Error", "Invalid method selection")
            return

        method_info = gui.custom_sweeps_method_map[selected_display]
        code_name = method_info["code_name"]

        test_config_path = _PROJECT_ROOT / "Json_Files" / "test_configurations.json"
        if not test_config_path.exists():
            test_configs = {}
        else:
            with test_config_path.open("r", encoding="utf-8") as f:
                test_configs = json.load(f)

        if code_name not in test_configs:
            test_configs[code_name] = {}

        test_configs[code_name]["sweep_combinations"] = gui.custom_sweep_combinations

        if "main_sweep" not in test_configs[code_name]:
            test_configs[code_name]["main_sweep"] = None

        with test_config_path.open("w", encoding="utf-8") as f:
            json.dump(test_configs, f, indent=4, ensure_ascii=False)

        if hasattr(gui, "custom_sweep_status_label"):
            gui.custom_sweep_status_label.config(
                text=f"✓ Saved {len(gui.custom_sweep_combinations)} combination(s) to JSON",
                fg="#4CAF50",
            )

        messagebox.showinfo(
            "Saved",
            f"Successfully saved {len(gui.custom_sweep_combinations)} combination(s)\n"
            f"to test_configurations.json for method: {code_name}",
        )

        print(
            f"[CUSTOM SWEEPS] Saved {len(gui.custom_sweep_combinations)} combinations to {test_config_path}"
        )

    except Exception as e:
        import traceback

        error_msg = f"Error saving combinations: {e}"
        print(f"[CUSTOM SWEEPS] {error_msg}")
        traceback.print_exc()
        messagebox.showerror("Error", error_msg)
        if hasattr(gui, "custom_sweep_status_label"):
            gui.custom_sweep_status_label.config(
                text=f"✗ {error_msg}", fg="#F44336"
            )
