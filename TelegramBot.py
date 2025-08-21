import asyncio
import threading
import logging
from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)

class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        """
        Initializes the TelegramBot with a token and chat_id.

        :param token: Telegram Bot API token
        :param chat_id: Telegram Chat ID where messages should be sent
        """
        self.token = token
        self.chat_id = chat_id
        self.bot = Bot(token=self.token)

        # Create a new event loop for the bot
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()  # Start event loop in a new thread

        # State for simple polling-based replies
        self._last_update_id = 0
        try:
            # Normalize chat_id to int when possible for comparison
            self._chat_id_int = int(chat_id)
        except Exception:
            self._chat_id_int = None

        # Ensure long polling works even if a webhook was set previously
        try:
            fut = asyncio.run_coroutine_threadsafe(self.bot.delete_webhook(drop_pending_updates=True), self.loop)
            try:
                fut.result(timeout=5)
            except Exception:
                pass
            # Seed last update id to most recent to avoid processing backlog
            fut2 = asyncio.run_coroutine_threadsafe(self.bot.get_updates(timeout=0), self.loop)
            try:
                updates = fut2.result(timeout=5)
                if updates:
                    self._last_update_id = max(u.update_id for u in updates)
            except Exception:
                pass
        except Exception:
            pass

    def _run_loop(self):
        """Runs the asyncio event loop in a separate thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _send_message(self, text: str):
        """Sends a text message asynchronously to the Telegram chat."""
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
            logging.info(f"Message sent: {text}")
        except Exception as e:
            logging.error(f"Failed to send message: {e}")

    def send_message(self, text: str):
        """Public method to send a message, ensuring it's called in the correct event loop."""
        asyncio.run_coroutine_threadsafe(self._send_message(text), self.loop)

    async def _send_image(self, image_path: str, caption: str = ""):
        """Sends an image asynchronously to the Telegram chat."""
        try:
            with open(image_path, "rb") as image:
                await self.bot.send_photo(chat_id=self.chat_id, photo=image, caption=caption)
            logging.info(f"Image sent: {image_path}")
        except Exception as e:
            logging.error(f"Failed to send image: {e}")

    def send_image(self, image_path: str, caption: str = ""):
        """Public method to send an image, ensuring it's called in the correct event loop."""
        asyncio.run_coroutine_threadsafe(self._send_image(image_path, caption), self.loop)

    async def _ask_question(self, question: str, choices: dict):
        """
        Asks a question and waits for a response.

        :param question: The question to ask the user
        :param choices: A dictionary mapping choice numbers to responses
        """
        await self.bot.send_message(chat_id=self.chat_id, text=question + "\n\n" +
                                    "\n".join([f"{k}: {v}" for k, v in choices.items()]))
        logging.info(f"Question sent: {question}")

    def ask_question(self, question: str, choices: dict):
        """Public method to ask a question with predefined responses."""
        asyncio.run_coroutine_threadsafe(self._ask_question(question, choices), self.loop)

    # ---------------- Simple reply listening (polling) -----------------
    def wait_for_text_reply(self, timeout_s: int = 300) -> str | None:
        """
        Blocks and waits for a text reply in the configured chat via long polling.
        Returns the message text or None on timeout.
        """
        import time
        deadline = time.time() + max(1, timeout_s)
        text: str | None = None
        while time.time() < deadline and text is None:
            try:
                # Use long polling to reduce rate (run in our bot loop)
                fut = asyncio.run_coroutine_threadsafe(
                    self.bot.get_updates(offset=self._last_update_id + 1, timeout=30),
                    self.loop,
                )
                updates = fut.result(timeout=35)
                for up in updates:
                    try:
                        self._last_update_id = max(self._last_update_id, up.update_id)
                        msg = getattr(up, "message", None)
                        if not msg:
                            continue
                        chat = getattr(msg, "chat", None)
                        if self._chat_id_int is not None and getattr(chat, "id", None) != self._chat_id_int:
                            continue
                        if getattr(msg, "text", None):
                            text = msg.text
                            break
                    except Exception:
                        # Skip malformed updates
                        continue
            except Exception:
                # Small backoff on errors
                time.sleep(1)
        return text

    def ask_and_wait(self, question: str, choices: dict, timeout_s: int = 300) -> str | None:
        """
        Sends a question with choices, then waits for a single text reply.
        Returns the reply text (raw) or None if timed out.
        """
        try:
            self.ask_question(question, choices)
        except Exception:
            # Fallback: send plain message
            try:
                self.send_message(question + "\n\n" + "\n".join([f"{k}: {v}" for k, v in choices.items()]))
            except Exception:
                pass
        return self.wait_for_text_reply(timeout_s=timeout_s)
