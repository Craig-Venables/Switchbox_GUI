"""
Conditional Config Helpers
=========================

Load/save and update logic for conditional testing configuration.
Extracted from layout_builder for maintainability.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any


def update_conditional_testing_controls(builder: Any, gui: Any) -> None:
    """Enable/disable conditional testing controls."""
    # All controls are always enabled now (removed enable checkbox)
    pass


def update_final_test_controls(builder: Any, gui: Any) -> None:
    """Update final test controls based on enabled state and mode."""
    enabled = (
        gui.conditional_final_test_enabled.get()
        if hasattr(gui, "conditional_final_test_enabled")
        else False
    )
    state = tk.NORMAL if enabled else tk.DISABLED

    if hasattr(gui, "conditional_final_test_widgets"):
        widgets = gui.conditional_final_test_widgets
        widgets["mode_combo"].config(state=state)
        widgets["final_test_combo"].config(state=state)
        widgets["min_score_label"].config(state=state)
        widgets["min_score_spinbox"].config(state=state)

        # Update top_x visibility based on mode
        mode = (
            gui.conditional_final_test_mode.get()
            if hasattr(gui, "conditional_final_test_mode")
            else "top_x"
        )
        if mode == "top_x":
            widgets["top_x_label"].grid()
            widgets["top_x_spinbox"].config(state=state)
            widgets["top_x_spinbox"].grid()
        else:
            # For "all_above_score", hide top_x controls
            widgets["top_x_label"].grid_remove()
            widgets["top_x_spinbox"].grid_remove()


def load_conditional_config(builder: Any, gui: Any) -> None:
    """Load conditional testing configuration from JSON file."""
    if hasattr(gui, "_load_conditional_test_config"):
        config = gui._load_conditional_test_config()
        if config:
            if hasattr(gui, "conditional_basic_threshold"):
                gui.conditional_basic_threshold.set(
                    config.get("thresholds", {}).get("basic_memristive", 60)
                )
            if hasattr(gui, "conditional_high_quality_threshold"):
                gui.conditional_high_quality_threshold.set(
                    config.get("thresholds", {}).get("high_quality", 80)
                )
            if hasattr(gui, "conditional_re_evaluate"):
                gui.conditional_re_evaluate.set(
                    config.get("re_evaluate_during_test", {}).get("enabled", True)
                )
            if hasattr(gui, "conditional_include_memcapacitive"):
                gui.conditional_include_memcapacitive.set(
                    config.get("include_memcapacitive", True)
                )
            if hasattr(gui, "conditional_quick_test"):
                gui.conditional_quick_test.set(
                    config.get("quick_test", {}).get("custom_sweep_name", "")
                )
            if hasattr(gui, "conditional_basic_test"):
                gui.conditional_basic_test.set(
                    config.get("tests", {})
                    .get("basic_memristive", {})
                    .get("custom_sweep_name", "")
                )
            if hasattr(gui, "conditional_high_quality_test"):
                gui.conditional_high_quality_test.set(
                    config.get("tests", {})
                    .get("high_quality", {})
                    .get("custom_sweep_name", "")
                )

            # Load final test config
            final_test = config.get("final_test", {})
            if hasattr(gui, "conditional_final_test_enabled"):
                gui.conditional_final_test_enabled.set(
                    final_test.get("enabled", False)
                )
            if hasattr(gui, "conditional_final_test_mode"):
                gui.conditional_final_test_mode.set(
                    final_test.get("selection_mode", "top_x")
                )
            if hasattr(gui, "conditional_final_test_top_x"):
                gui.conditional_final_test_top_x.set(
                    final_test.get("top_x_count", 3)
                )
            if hasattr(gui, "conditional_final_test_min_score"):
                gui.conditional_final_test_min_score.set(
                    final_test.get("min_score_threshold", 80.0)
                )
            if hasattr(gui, "conditional_final_test_name"):
                gui.conditional_final_test_name.set(
                    final_test.get("custom_sweep_name", "")
                )

            messagebox.showinfo(
                "Config Loaded",
                "Conditional testing configuration loaded successfully.",
            )
            update_conditional_testing_controls(builder, gui)
            update_final_test_controls(builder, gui)


def save_conditional_config(builder: Any, gui: Any) -> None:
    """Save conditional testing configuration to JSON file."""
    if hasattr(gui, "_save_conditional_test_config"):
        config = {
            "quick_test": {
                "custom_sweep_name": (
                    gui.conditional_quick_test.get()
                    if hasattr(gui, "conditional_quick_test")
                    else ""
                ),
                "timeout_s": 300,
            },
            "thresholds": {
                "basic_memristive": (
                    gui.conditional_basic_threshold.get()
                    if hasattr(gui, "conditional_basic_threshold")
                    else 60
                ),
                "high_quality": (
                    gui.conditional_high_quality_threshold.get()
                    if hasattr(gui, "conditional_high_quality_threshold")
                    else 80
                ),
            },
            "re_evaluate_during_test": {
                "enabled": (
                    gui.conditional_re_evaluate.get()
                    if hasattr(gui, "conditional_re_evaluate")
                    else True
                )
            },
            "include_memcapacitive": (
                gui.conditional_include_memcapacitive.get()
                if hasattr(gui, "conditional_include_memcapacitive")
                else True
            ),
            "tests": {
                "basic_memristive": {
                    "custom_sweep_name": (
                        gui.conditional_basic_test.get()
                        if hasattr(gui, "conditional_basic_test")
                        else ""
                    )
                },
                "high_quality": {
                    "custom_sweep_name": (
                        gui.conditional_high_quality_test.get()
                        if hasattr(gui, "conditional_high_quality_test")
                        else ""
                    )
                },
            },
            "final_test": {
                "enabled": (
                    gui.conditional_final_test_enabled.get()
                    if hasattr(gui, "conditional_final_test_enabled")
                    else False
                ),
                "selection_mode": (
                    gui.conditional_final_test_mode.get()
                    if hasattr(gui, "conditional_final_test_mode")
                    else "top_x"
                ),
                "top_x_count": (
                    gui.conditional_final_test_top_x.get()
                    if hasattr(gui, "conditional_final_test_top_x")
                    else 3
                ),
                "min_score_threshold": (
                    gui.conditional_final_test_min_score.get()
                    if hasattr(gui, "conditional_final_test_min_score")
                    else 80.0
                ),
                "custom_sweep_name": (
                    gui.conditional_final_test_name.get()
                    if hasattr(gui, "conditional_final_test_name")
                    else ""
                ),
            },
        }
        if gui._save_conditional_test_config(config):
            messagebox.showinfo(
                "Config Saved",
                "Conditional testing configuration saved successfully.",
            )
