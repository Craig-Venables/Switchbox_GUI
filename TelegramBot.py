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
