"""
Multiplexer routing and relay control for SampleGUI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from tkinter import messagebox

from Equipment.Multiplexers.Multiplexer_10_OUT.Multiplexer_Class import MultiplexerController
from Equipment.managers.multiplexer import MultiplexerManager
from gui.sample_gui.config import pin_mapping

if TYPE_CHECKING:
    from gui.sample_gui.main import SampleGUI


class RoutingController:
    """Multiplexer initialization and device routing."""

    def __init__(self, gui: "SampleGUI") -> None:
        self.gui = gui

    def update_multiplexer(self, event: Optional[Any] = None) -> None:
        gui = self.gui
        gui.multiplexer_type = gui.Multiplexer_type_var.get()

        try:
            if gui.multiplexer_type == "Pyswitchbox":
                gui.mpx_manager = MultiplexerManager.create(
                    "Pyswitchbox",
                    pin_mapping=pin_mapping,
                )
                gui.log_terminal("Initiated Pyswitchbox via MultiplexerManager", "SUCCESS")
                gui.mpx_status_label.config(
                    text=f"Multiplexer: {gui.multiplexer_type} Connected", fg="#4CAF50",
                )
            elif gui.multiplexer_type == "Electronic_Mpx":
                try:
                    gui.mpx = MultiplexerController(simulation_mode=False)
                    gui.log_terminal("Initiated Electronic_Mpx with real hardware", "SUCCESS")
                except Exception:
                    gui.log_terminal("Hardware not available, using simulation mode", "WARNING")
                    gui.mpx = MultiplexerController(simulation_mode=True)

                gui.mpx_manager = MultiplexerManager.create(
                    "Electronic_Mpx",
                    controller=gui.mpx,
                )
                gui.mpx_status_label.config(
                    text=f"Multiplexer: {gui.multiplexer_type} Connected", fg="#4CAF50",
                )
            elif gui.multiplexer_type == "Manual":
                gui.mpx_manager = None
                gui.log_terminal(
                    "Manual mode activated - no multiplexer routing, manual probe movement required",
                    "SUCCESS",
                )
                gui.mpx_status_label.config(text="Multiplexer: Manual Mode", fg="#FF9800")
            else:
                gui.log_terminal("Unknown multiplexer type", "ERROR")
                gui.mpx_status_label.config(text="Multiplexer: Unknown Type", fg="#F44336")
        except Exception as exc:
            gui.log_terminal(f"Error initializing multiplexer: {exc}", "ERROR")
            gui.mpx_status_label.config(text="Multiplexer: Error", fg="#F44336")

    def change_relays(self) -> None:
        """Route multiplexer to the current device."""
        gui = self.gui
        current_device = gui.device_list[gui.current_index]
        label = gui.get_device_label(current_device)

        if current_device not in gui.selected_devices:
            gui.log_terminal(f"Warning: Device {label} is not selected")
            response = messagebox.askyesno(
                "Device Not Selected",
                f"Device {label} is not in the selected list. Continue anyway?",
            )
            if not response:
                return

        if gui.multiplexer_type == "Manual":
            gui.log_terminal(
                f"Manual mode: Device {label} selected (manually move probes to this device)",
                "INFO",
            )
            self._sync_measurement_window()
        elif gui.mpx_manager is not None:
            gui.log_terminal(f"Routing to {label} via {gui.multiplexer_type}")
            success = gui.mpx_manager.route_to_device(current_device, gui.current_index)
            if success:
                gui.log_terminal(f"Successfully routed to {label}")
            else:
                gui.log_terminal(f"Failed to route to {label}")
            self._sync_measurement_window()
        else:
            gui.log_terminal("Multiplexer manager not initialized")
            print("Error: Multiplexer manager is None")

    def _sync_measurement_window(self) -> None:
        gui = self.gui
        if gui.measurement_window and hasattr(gui, "measuremnt_gui"):
            gui.measuremnt_gui.current_index = gui.current_index
            gui.measuremnt_gui.update_variables()
