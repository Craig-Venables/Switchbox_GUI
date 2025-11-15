"""
Notifications Package

This package contains notification services for the measurement system.
Currently includes Telegram bot integration for sending notifications and
receiving interactive responses.
"""

from Notifications.telegram_bot import TelegramBot

__all__ = ['TelegramBot']

