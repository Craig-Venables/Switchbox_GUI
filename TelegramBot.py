"""
TelegramBot Module

Purpose:
This module provides a simplified Telegram bot interface for sending notifications,
images, and interactive messages to a configured Telegram chat. The bot runs in a
separate thread with its own asyncio event loop to avoid blocking the main application.

Usage:
    from TelegramBot import TelegramBot
    
    # Initialize bot with token and chat ID
    bot = TelegramBot(token="YOUR_BOT_TOKEN", chat_id="YOUR_CHAT_ID")
    
    # Send simple messages
    bot.send_message("Measurement complete!")
    
    # Send images
    bot.send_image("path/to/plot.png", caption="IV Curve Results")
    
    # Ask interactive questions
    response = bot.ask_and_wait(
        question="Continue test?",
        choices={"1": "Yes", "2": "No", "3": "Skip"},
        timeout_s=60
    )
    
    # Graceful shutdown
    bot.shutdown()

Key Features:
- Thread-safe: runs in separate daemon thread with own event loop
- Non-blocking: all operations use async internally
- Automatic webhook cleanup: ensures long polling works properly
- Lazy initialization: only processes messages when waiting for replies
- Error resilient: failures don't crash the application
- Type hints: full type annotation support for IDE assistance

Dependencies:
- python-telegram-bot: Official Telegram Bot API library
"""

import asyncio
import threading
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError, NetworkError, TimedOut

# Configure logging for this module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramBot:
    """
    Simplified Telegram bot for sending notifications and receiving replies.
    
    This bot runs in a separate daemon thread with its own asyncio event loop,
    making all operations non-blocking for the main application. It handles
    message sending, image uploads, and interactive Q&A sessions.
    
    Attributes:
        token (str): Telegram Bot API token
        chat_id (str): Telegram Chat ID for sending messages
        bot (Bot): python-telegram-bot Bot instance
        loop (asyncio.AbstractEventLoop): Event loop for async operations
        thread (threading.Thread): Daemon thread running the event loop
        _last_update_id (int): Last processed update ID for polling
        _chat_id_int (Optional[int]): Normalized chat ID as integer
        _shutdown_flag (bool): Flag indicating if bot is shutting down
    """
    
    def __init__(self, token: str, chat_id: str) -> None:
        """
        Initialize TelegramBot with authentication credentials.

        Args:
            token: Telegram Bot API token from @BotFather
            chat_id: Telegram Chat ID where messages should be sent
            
        Raises:
            ValueError: If token or chat_id are empty or invalid
            TelegramError: If bot initialization fails
        """
        self.token = token
        self.chat_id = chat_id
        # Store stripped version if string type
        try:
            self.token = token.strip() if isinstance(token, str) else token
            self.chat_id = chat_id.strip() if isinstance(chat_id, str) else chat_id
        except AttributeError:
            pass  # Not string types, use as-is
        self.bot = Bot(token=self.token)
        self._shutdown_flag = False

        # Create a new event loop for the bot in a separate thread
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="TelegramBot")
        self.thread.start()
        
        # Wait briefly for thread to start
        time.sleep(0.1)

        # State for polling-based message reception
        self._last_update_id = 0
        try:
            # Normalize chat_id to int for efficient comparison
            self._chat_id_int = int(chat_id)
        except (ValueError, TypeError):
            self._chat_id_int = None

        # Initialize webhook cleanup and update tracking
        self._initialize_updates()

    def _initialize_updates(self) -> None:
        """
        Clean up webhooks and seed last update ID to avoid processing old messages.
        
        This ensures long polling works correctly even if a webhook was configured previously.
        """
        try:
            # Delete any existing webhook
            fut = asyncio.run_coroutine_threadsafe(
                self.bot.delete_webhook(drop_pending_updates=True), 
                self.loop
            )
            try:
                fut.result(timeout=5)
                logger.debug("Webhook cleanup successful")
            except asyncio.TimeoutError:
                logger.warning("Webhook cleanup timed out")
            except Exception as e:
                logger.warning(f"Webhook cleanup failed: {e}")
            
            # Get most recent updates to seed last_update_id
            fut2 = asyncio.run_coroutine_threadsafe(
                self.bot.get_updates(timeout=0), 
                self.loop
            )
            try:
                updates = fut2.result(timeout=5)
                if updates:
                    self._last_update_id = max(u.update_id for u in updates)
                    logger.info(f"Initialized with last_update_id={self._last_update_id}")
            except asyncio.TimeoutError:
                logger.warning("Update seeding timed out")
            except Exception as e:
                logger.warning(f"Update seeding failed: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize updates: {e}")

    def _run_loop(self) -> None:
        """
        Run the asyncio event loop in a separate daemon thread.
        
        This method blocks until shutdown is called. All async operations
        are scheduled on this event loop.
        """
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _send_message(self, text: str, max_retries: int = 3) -> bool:
        """
        Send a text message asynchronously with retry logic.
        
        Args:
            text: Message text to send (supports markdown formatting)
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if self._shutdown_flag:
            logger.warning("Bot is shutting down, message not sent")
            return False
            
        for attempt in range(max_retries):
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id, 
                    text=text, 
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"Message sent successfully: {text[:50]}...")
                return True
            except NetworkError as e:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Network error (attempt {attempt+1}/{max_retries}), "
                             f"retrying in {wait_time}s: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
            except TimedOut as e:
                logger.warning(f"Timeout (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
            except TelegramError as e:
                logger.error(f"Telegram API error: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error sending message: {e}")
                return False
        
        logger.error(f"Failed to send message after {max_retries} attempts")
        return False

    def send_message(self, text: str) -> None:
        """
        Public method to send a message (non-blocking).
        
        This method schedules the message sending in the bot's event loop
        and returns immediately. The actual sending happens asynchronously.
        
        Args:
            text: Message text to send
        """
        asyncio.run_coroutine_threadsafe(self._send_message(text), self.loop)

    async def _send_image(self, image_path: str, caption: str = "", max_retries: int = 3) -> bool:
        """
        Send an image asynchronously with retry logic.
        
        Args:
            image_path: Path to image file
            caption: Optional caption text
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if image was sent successfully, False otherwise
        """
        if self._shutdown_flag:
            logger.warning("Bot is shutting down, image not sent")
            return False
            
        if not Path(image_path).exists():
            logger.error(f"Image file not found: {image_path}")
            return False
            
        for attempt in range(max_retries):
            try:
                with open(image_path, "rb") as image:
                    await self.bot.send_photo(
                        chat_id=self.chat_id, 
                        photo=image, 
                        caption=caption if caption else None
                    )
                logger.info(f"Image sent successfully: {image_path}")
                return True
            except NetworkError as e:
                wait_time = 2 ** attempt
                logger.warning(f"Network error (attempt {attempt+1}/{max_retries}), "
                             f"retrying in {wait_time}s: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
            except TimedOut as e:
                logger.warning(f"Timeout (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
            except TelegramError as e:
                logger.error(f"Telegram API error: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to send image: {e}")
                return False
        
        logger.error(f"Failed to send image after {max_retries} attempts")
        return False

    def send_image(self, image_path: str, caption: str = "") -> None:
        """
        Public method to send an image (non-blocking).
        
        This method schedules the image upload in the bot's event loop
        and returns immediately.
        
        Args:
            image_path: Path to image file
            caption: Optional caption text
        """
        asyncio.run_coroutine_threadsafe(self._send_image(image_path, caption), self.loop)

    async def _ask_question(self, question: str, choices: Dict[str, str]) -> bool:
        """
        Send a question with predefined choices to the user.
        
        Args:
            question: The question text to display
            choices: Dictionary mapping choice keys to descriptions
            
        Returns:
            True if question was sent successfully, False otherwise
        """
        if not choices:
            logger.warning("No choices provided for question")
            return False
            
        choices_text = "\n".join([f"{k}: {v}" for k, v in choices.items()])
        message_text = f"{question}\n\n{choices_text}"
        
        try:
            await self._send_message(message_text, max_retries=1)
            logger.info(f"Question sent: {question[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send question: {e}")
            return False

    def ask_question(self, question: str, choices: Dict[str, str]) -> None:
        """
        Public method to ask a question (non-blocking).
        
        Args:
            question: The question text to display
            choices: Dictionary mapping choice keys to descriptions
        """
        asyncio.run_coroutine_threadsafe(self._ask_question(question, choices), self.loop)

    # ---------------- Simple reply listening (polling) -----------------
    def wait_for_text_reply(self, timeout_s: int = 300) -> Optional[str]:
        """
        Block and wait for a text reply in the configured chat via long polling.
        
        This method uses Telegram's getUpdates API with long polling to efficiently
        wait for new messages. It only returns messages from the configured chat_id.
        
        Args:
            timeout_s: Maximum time to wait for a reply in seconds (default 300)
            
        Returns:
            Message text if received, None on timeout or shutdown
        """
        if self._shutdown_flag:
            logger.warning("Bot is shutting down, not waiting for reply")
            return None
            
        deadline = time.time() + max(1, timeout_s)
        text: Optional[str] = None
        
        while time.time() < deadline and text is None and not self._shutdown_flag:
            try:
                # Use long polling to reduce API rate (runs in our bot loop)
                fut = asyncio.run_coroutine_threadsafe(
                    self.bot.get_updates(offset=self._last_update_id + 1, timeout=30),
                    self.loop,
                )
                updates = fut.result(timeout=35)
                
                for up in updates:
                    try:
                        # Update last processed ID
                        self._last_update_id = max(self._last_update_id, up.update_id)
                        
                        # Extract message
                        msg = getattr(up, "message", None)
                        if not msg:
                            continue
                        
                        # Verify chat ID matches
                        chat = getattr(msg, "chat", None)
                        if self._chat_id_int is not None and getattr(chat, "id", None) != self._chat_id_int:
                            continue
                        
                        # Extract text content
                        if getattr(msg, "text", None):
                            text = msg.text
                            logger.info(f"Received reply: {text[:50]}...")
                            break
                    except Exception as e:
                        # Skip malformed updates
                        logger.debug(f"Skipping malformed update: {e}")
                        continue
                        
            except asyncio.TimeoutError:
                # Expected when long polling times out, continue to next iteration
                continue
            except Exception as e:
                # Small backoff on unexpected errors
                logger.warning(f"Error waiting for reply: {e}")
                time.sleep(1)
        
        if text is None and not self._shutdown_flag:
            logger.info(f"No reply received within {timeout_s}s timeout")
        
        return text

    def ask_and_wait(self, question: str, choices: Dict[str, str], timeout_s: int = 300) -> Optional[str]:
        """
        Send a question with choices and wait for a text reply.
        
        This is a convenience method that combines ask_question and wait_for_text_reply
        into a single blocking call. It sends the question and then waits for the user's
        response.
        
        Args:
            question: The question text to display
            choices: Dictionary mapping choice keys to descriptions
            timeout_s: Maximum time to wait for a reply in seconds
            
        Returns:
            User's reply text, or None if timed out or shutdown
        """
        if self._shutdown_flag:
            logger.warning("Bot is shutting down, cannot ask and wait")
            return None
            
        try:
            self.ask_question(question, choices)
        except Exception as e:
            # Fallback: send plain message
            logger.warning(f"Failed to ask question with retry, trying plain message: {e}")
            try:
                choices_text = "\n".join([f"{k}: {v}" for k, v in choices.items()])
                self.send_message(f"{question}\n\n{choices_text}")
            except Exception as e2:
                logger.error(f"Failed to send fallback message: {e2}")
                return None
        
        return self.wait_for_text_reply(timeout_s=timeout_s)
    
    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully shutdown the bot and cleanup resources.
        
        This method stops the event loop, waits for pending operations,
        and ensures all resources are properly released.
        
        Args:
            timeout: Maximum time to wait for cleanup in seconds
        """
        if self._shutdown_flag:
            logger.warning("Bot already shutting down")
            return
            
        logger.info("Shutting down Telegram bot...")
        self._shutdown_flag = True
        
        # Stop the event loop
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        # Wait for thread to finish
        if self.thread.is_alive():
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                logger.warning("Thread did not terminate within timeout")
        
        logger.info("Telegram bot shutdown complete")
