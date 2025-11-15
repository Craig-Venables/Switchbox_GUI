"""
Telegram Coordinator
====================

Centralises all Telegram messaging helpers that were historically embedded
inside `Measurement_GUI`.  The coordinator keeps the GUI class lean while
exposing a small, well-documented surface for sending updates and triggering
post-measurement workflows.
"""

from __future__ import annotations

import threading
from typing import Any, Optional


class TelegramCoordinator:
    """Helper responsible for Telegram messaging for the measurement GUI."""

    def __init__(self, gui: Any) -> None:
        """
        Parameters
        ----------
        gui:
            Reference to the GUI instance providing Tk variables such as
            `get_messaged_var`, `token_var`, and `chatid_var`.  The coordinator
            treats this as a weak dependency so the module remains GUI-agnostic.
        """
        self.gui = gui
        self._bot: Optional[Any] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def is_enabled(self) -> bool:
        """Return ``True`` when Telegram messaging is fully configured."""
        try:
            return bool(
                getattr(self.gui, "get_messaged_var", None)
                and self.gui.get_messaged_var.get() == 1
                and getattr(self.gui, "token_var", None)
                and getattr(self.gui, "chatid_var", None)
                and self.gui.token_var.get().strip()
                and self.gui.chatid_var.get().strip()
            )
        except Exception:
            return False

    def send_message(self, text: str) -> None:
        """Best-effort attempt to send ``text`` to the configured chat."""
        bot = self._get_bot()
        if not bot:
            return
        try:
            bot.send_message(text)
        except Exception:
            pass

    def send_image(self, image_path: str, caption: str = "") -> None:
        """Send an image (if available) with an optional caption."""
        bot = self._get_bot()
        if not bot:
            return
        try:
            bot.send_image(image_path, caption)
        except Exception:
            pass

    def start_post_measurement_worker(
        self, save_dir: str, combined_path: Optional[str] = None
    ) -> None:
        """
        Launch a background worker that sends a completion summary and waits
        for follow-up commands.
        """
        if not self.is_enabled():
            return
        worker = threading.Thread(
            target=self._post_measurement_options_worker,
            args=(save_dir, combined_path),
            daemon=True,
        )
        worker.start()

    def reset_credentials(self) -> None:
        """Force the coordinator to recreate the bot on next use."""
        self._bot = None

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _get_bot(self) -> Optional[Any]:
        if not self.is_enabled():
            return None
        if self._bot is None:
            try:
                from Notifications import TelegramBot  # Local import to avoid hard dep at startup

                token = self.gui.token_var.get().strip()
                chat_id = self.gui.chatid_var.get().strip()
                self._bot = TelegramBot(token, chat_id)
            except Exception:
                self._bot = None
        return self._bot

    def _post_measurement_options_worker(
        self, save_dir: str, combined_path: Optional[str] = None
    ) -> None:
        """Background worker that sends a Telegram summary when enabled."""
        bot = self._get_bot()
        if not bot:
            return

        try:
            bot.send_message("Measurement finished")
        except Exception:
            pass

        if combined_path:
            try:
                bot.send_image(combined_path, caption="Summary (All + Final)")
            except Exception:
                pass

        try:
            bot.send_message(
                "Reply with 'Start' to run another normal measurement or 'End' to finish."
            )
            reply = bot.wait_for_text_reply(timeout_s=900)
        except Exception:
            reply = None

        if not reply:
            return

        r = reply.strip().lower()
        if r in {"start", "s"}:
            try:
                self.gui.master.after(0, self.gui.start_measurement)
            except Exception:
                pass
            return

        if r.startswith("end"):
            try:
                bot.send_message("Okay, ending session.")
            except Exception:
                pass


__all__ = ["TelegramCoordinator"]


