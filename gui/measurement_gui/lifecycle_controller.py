"""Application shutdown and instrument cleanup for MeasurementGUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui.measurement_gui.main import MeasurementGUI


class LifecycleController:
    """Graceful teardown of instruments and GUI resources on exit."""

    def __init__(self, gui: "MeasurementGUI") -> None:
        self.gui = gui

    def cleanup(self) -> None:
        """Attempt to gracefully shutdown connected instruments and clear flags.

        This method is registered with `atexit` to ensure the SMU/PSU/temp
        controllers are left in a safe state when the GUI exits. It performs
        best-effort cleanup and swallows exceptions so shutdown proceeds.
        """

        gui = self.gui
        try:
            if hasattr(gui, "plot_updaters"):
                gui.plot_updaters.stop_all_threads()
        except Exception:
            pass

        #  gui.keithley.shutdown()
        # # todo send comand to temp if connected to cool down to 0
        # if gui.itc_connected:
        #     gui.itc.set_temperature(0) # set temp controller tp 0 deg
        # if gui.psu_connected:
        #     gui.psu.disable_channel(1)
        #     gui.psu.disable_channel(2)
        #     gui.psu.close()
        try:
            if getattr(gui, 'keithley', None):
                gui.keithley.shutdown()
        except Exception:
            # Don't raise during process exit; just log to stdout where possible
            print("Warning: keithley.shutdown() failed during cleanup")

        # Clean up analysis stats window
        try:
            if hasattr(gui, 'analysis_stats_window') and gui.analysis_stats_window:
                gui.analysis_stats_window.destroy()
        except Exception:
            pass

        # If a temperature controller is connected, try to set it to 0°C
        try:
            if getattr(gui, 'itc_connected', False) and getattr(gui, 'itc', None):
                gui.itc.set_temperature(0)
        except Exception:
            print("Warning: could not reset temperature controller during cleanup")

        # Disable and close PSU channels if a PSU was connected
        try:
            if getattr(gui, 'psu_connected', False) and getattr(gui, 'psu', None):
                gui.psu.disable_channel(1)
                gui.psu.disable_channel(2)
                gui.psu.close()
        except Exception:
            pass

        # Disconnect laser/optical system if connected
        try:
            if hasattr(gui, 'optical') and gui.optical is not None:
                # Disable optical source first
                try:
                    gui.optical.set_enabled(False)
                except Exception:
                    pass
                # Close connection properly (restores laser to manual control mode)
                try:
                    gui.optical.close()
                    print("[OPTICAL] Laser/optical system disconnected and restored to manual control")
                except Exception as e:
                    print(f"[OPTICAL] Warning: Failed to close optical system: {e}")
        except Exception:
            print("Warning: Optical system cleanup failed")

        # Also try disconnect_laser method if it exists (for backward compatibility)
        try:
            if hasattr(gui, 'disconnect_laser'):
                gui.disconnect_laser()
        except Exception:
            pass

        print("safely turned everything off")
        # Reset runtime test flags
        gui.tests_running = False
        gui.abort_tests_flag = False
